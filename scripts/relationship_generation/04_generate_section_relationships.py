#!/usr/bin/env python3
"""Generate section-scoped concept and dependency relationships."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any

from common import (
    DEFAULT_MODEL,
    GeminiClient,
    add_common_filters,
    append_jsonl,
    completed_ids,
    ensure_repo_root,
    load_full_chapter,
    load_manifest,
    read_jsonl,
    relevant_concepts_for_text,
    reset_output_on_force,
    stable_hash,
    validate_confidence,
    write_error,
)


SECTION_CONCEPT_OUTPUT = "raw_section_concept_relationships.jsonl"
SECTION_DEPENDENCY_OUTPUT = "raw_section_dependency_relationships.jsonl"
RUN_OUTPUT = "section_relationship_runs.jsonl"


TEACHES_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "relationships": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "to_id": {"type": "string"},
                    "confidence": {"type": "number"},
                    "evidence": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "reason": {"type": "string"},
                        },
                        "required": ["text", "reason"],
                    },
                },
                "required": ["to_id", "confidence", "evidence"],
            },
        }
    },
    "required": ["relationships"],
}


PREREQUISITE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "relationships": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["REQUIRES_CONCEPT", "DEPENDS_ON_UNIT"]},
                    "to_id": {"type": "string"},
                    "confidence": {"type": "number"},
                    "evidence": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "reason": {"type": "string"},
                        },
                        "required": ["text", "reason"],
                    },
                },
                "required": ["type", "to_id", "confidence", "evidence"],
            },
        }
    },
    "required": ["relationships"],
}


def load_section_summaries(path) -> dict[str, dict[str, Any]]:
    return {row["section_id"]: row for row in read_jsonl(path) if row.get("section_id")}


def section_payload(chapter_id: str, section: dict[str, Any]) -> dict[str, Any]:
    return {
        "chapter_id": chapter_id,
        "section_id": section["id"],
        "section_number": section.get("number"),
        "title": section.get("title") or "",
        "content_text": section.get("content_text") or "",
        "subsections": [
            {
                "id": subsection["id"],
                "order": subsection.get("order"),
                "title": subsection.get("title") or "",
                "content_type": subsection.get("content_type") or "explanation",
                "content_text": subsection.get("content_text") or "",
                "worked_examples": subsection.get("worked_examples") or [],
                "diagrams": subsection.get("diagrams") or [],
                "tables": subsection.get("tables") or [],
            }
            for subsection in section.get("subsections", [])
        ],
    }


def chapter_skeleton(source: dict[str, Any], summaries: dict[str, dict[str, Any]], current_section_id: str) -> list[dict[str, Any]]:
    rows = []
    for section in source["chapter"].get("sections", []):
        if section["id"] == current_section_id:
            continue
        summary = summaries.get(section["id"]) or {}
        rows.append(
            {
                "section_id": section["id"],
                "section_number": section.get("number"),
                "title": section.get("title") or "",
                "summary": summary.get("summary", ""),
                "key_terms": summary.get("key_terms", []),
            }
        )
    return rows


def concept_registry(chapter_id: str, subject: str, concepts: list[dict[str, Any]], context_text: str) -> list[dict[str, Any]]:
    return relevant_concepts_for_text(chapter_id, subject, context_text, concepts, limit=100)


def missing_section_summary_ids(source: dict[str, Any], summaries: dict[str, dict[str, Any]]) -> list[str]:
    return sorted(
        section["id"]
        for section in source["chapter"].get("sections", [])
        if section["id"] not in summaries
    )


def build_teaches_prompt(current_section: dict[str, Any], concepts: list[dict[str, Any]]) -> str:
    return f"""Generate TEACHES_CONCEPT relationships for exactly one textbook SectionUnit.

Relationship meaning:
- TEACHES_CONCEPT: this SectionUnit explicitly introduces, defines, derives, explains, applies, practices, or substantially reinforces the concept.

Rules:
- Use only concept ids from canonical_concepts.
- Do not infer prerequisites here.
- Do not emit a concept merely because it is briefly mentioned.
- Every edge needs evidence copied from current_section and a reason.
- Use confidence >= 0.85 only when evidence is direct and specific.

canonical_concepts:
{json.dumps(concepts, ensure_ascii=False)}

current_section:
{json.dumps(current_section, ensure_ascii=False)}

Return JSON matching the requested schema."""


def build_prerequisite_prompt(
    current_section: dict[str, Any],
    other_sections: list[dict[str, Any]],
    concepts: list[dict[str, Any]],
) -> str:
    return f"""Generate prerequisite relationships for exactly one textbook SectionUnit.

Relationship meanings:
- REQUIRES_CONCEPT: current_section expects the learner to already understand the concept before studying it.
- DEPENDS_ON_UNIT: current_section should be learned after another SectionUnit in this chapter.

Rules:
- For REQUIRES_CONCEPT, use only concept ids from canonical_concepts.
- For DEPENDS_ON_UNIT, use only section_id values from other_section_skeleton.
- Do not create dependencies from document order alone.
- Do not mark a concept as required merely because current_section teaches it.
- Use other_section_skeleton only for chapter context; it intentionally contains summaries, not full text.
- Every edge needs evidence copied from current_section or a summary-backed reason.
- Use confidence >= 0.85 only when evidence is direct and specific.

canonical_concepts:
{json.dumps(concepts, ensure_ascii=False)}

current_section:
{json.dumps(current_section, ensure_ascii=False)}

other_section_skeleton:
{json.dumps(other_sections, ensure_ascii=False)}

Return JSON matching the requested schema."""


def relationship_row(
    *,
    chapter_id: str,
    section_id: str,
    rel_type: str,
    to_id: Any,
    confidence: Any,
    evidence: dict[str, Any],
    model: str,
) -> dict[str, Any]:
    row = {
        "chapter_id": chapter_id,
        "source_section_id": section_id,
        "type": rel_type,
        "from_id": section_id,
        "to_id": to_id,
        "confidence": validate_confidence(confidence),
        "evidence": {
            "unit_id": section_id,
            "text": str(evidence.get("text") or "")[:1200],
            "reason": str(evidence.get("reason") or "")[:800],
        },
        "generation": {"model": model, "script": "04_generate_section_relationships.py"},
    }
    row["relationship_id"] = stable_hash(row, "rel")
    return row


def normalize_teaches_rows(chapter_id: str, section_id: str, payload: dict[str, Any], model: str) -> list[dict[str, Any]]:
    rows = []
    for item in payload.get("relationships", []):
        rows.append(
            relationship_row(
                chapter_id=chapter_id,
                section_id=section_id,
                rel_type="TEACHES_CONCEPT",
                to_id=item.get("to_id"),
                confidence=item.get("confidence"),
                evidence=item.get("evidence") or {},
                model=model,
            )
        )
    return rows


def normalize_prerequisite_rows(
    chapter_id: str,
    section_id: str,
    payload: dict[str, Any],
    model: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    concept_rows = []
    dependency_rows = []
    for item in payload.get("relationships", []):
        rel_type = item.get("type")
        if rel_type not in {"REQUIRES_CONCEPT", "DEPENDS_ON_UNIT"}:
            continue
        row = relationship_row(
            chapter_id=chapter_id,
            section_id=section_id,
            rel_type=rel_type,
            to_id=item.get("to_id"),
            confidence=item.get("confidence"),
            evidence=item.get("evidence") or {},
            model=model,
        )
        if rel_type == "DEPENDS_ON_UNIT":
            dependency_rows.append(row)
        else:
            concept_rows.append(row)
    return concept_rows, dependency_rows


def run_marker(chapter_id: str, section_id: str, concept_count: int, dependency_count: int, model: str) -> dict[str, Any]:
    return {
        "chapter_id": chapter_id,
        "section_id": section_id,
        "relationship_count": concept_count + dependency_count,
        "concept_relationship_count": concept_count,
        "dependency_relationship_count": dependency_count,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "generation": {"model": model, "script": "04_generate_section_relationships.py"},
    }


def main() -> int:
    ensure_repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_filters(parser)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    concept_output = args.artifact_dir / SECTION_CONCEPT_OUTPUT
    dependency_output = args.artifact_dir / SECTION_DEPENDENCY_OUTPUT
    run_output = args.artifact_dir / RUN_OUTPUT
    for path in (concept_output, dependency_output, run_output):
        reset_output_on_force(path, args.force)

    done = set() if args.force else completed_ids(run_output, "section_id")
    summaries = load_section_summaries(args.artifact_dir / "section_summaries.jsonl")
    concepts = read_jsonl(args.artifact_dir / "canonical_concepts.jsonl")
    refs = load_manifest(args.manifest, subject=args.subject, grade=args.grade, chapter_id=args.chapter_id, limit=args.limit)
    client = None if args.dry_run else GeminiClient(args.model)
    concept_written = 0
    dependency_written = 0
    run_written = 0
    failures = 0

    for ref in refs:
        source = load_full_chapter(ref.path)
        missing = missing_section_summary_ids(source, summaries)
        if missing:
            failures += 1
            message = f"missing section summaries: {missing[:20]}"
            if not args.dry_run:
                write_error(args.artifact_dir / "errors.jsonl", stage="section_relationships", item_id=ref.id, error=message)
            print(f"{ref.id}: ERROR {message}")
            continue

        for section in source["chapter"].get("sections", []):
            section_id = section["id"]
            if section_id in done:
                continue
            current = section_payload(ref.id, section)
            skeleton = chapter_skeleton(source, summaries, section_id)
            context_text = json.dumps({"current": current, "skeleton": skeleton}, ensure_ascii=False)
            concept_subset = concept_registry(ref.id, ref.subject, concepts, context_text)
            teaches_prompt = build_teaches_prompt(current, concept_subset)
            prerequisite_prompt = build_prerequisite_prompt(current, skeleton, concept_subset)
            if args.dry_run:
                print("=== TEACHES PROMPT ===")
                print(teaches_prompt[:12000])
                print(f"\n[teaches prompt chars: {len(teaches_prompt)}]")
                print("\n=== PREREQUISITE PROMPT ===")
                print(prerequisite_prompt[:12000])
                print(f"\n[prerequisite prompt chars: {len(prerequisite_prompt)}]")
                return 0
            try:
                teaches_payload = client.generate_json(teaches_prompt, TEACHES_SCHEMA)
                prerequisite_payload = client.generate_json(prerequisite_prompt, PREREQUISITE_SCHEMA)
                teaches_rows = normalize_teaches_rows(ref.id, section_id, teaches_payload, args.model)
                require_rows, dependency_rows = normalize_prerequisite_rows(ref.id, section_id, prerequisite_payload, args.model)
                concept_count = append_jsonl(concept_output, [*teaches_rows, *require_rows])
                dependency_count = append_jsonl(dependency_output, dependency_rows)
                append_jsonl(run_output, [run_marker(ref.id, section_id, concept_count, dependency_count, args.model)])
                concept_written += concept_count
                dependency_written += dependency_count
                run_written += 1
                print(f"{section_id}: wrote {concept_count} concept edges and {dependency_count} dependency edges")
            except Exception as exc:
                failures += 1
                write_error(args.artifact_dir / "errors.jsonl", stage="section_relationships", item_id=section_id, error=str(exc))
                print(f"{section_id}: ERROR {exc}")

    print(f"done: wrote {concept_written} relationships to {concept_output}")
    print(f"done: wrote {dependency_written} relationships to {dependency_output}")
    print(f"done: wrote {run_written} completion markers to {run_output}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
