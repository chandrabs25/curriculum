#!/usr/bin/env python3
"""Generate compact summaries and raw concept candidates for each section."""

from __future__ import annotations

import argparse
import json
from typing import Any

from common import (
    DEFAULT_MODEL,
    GeminiClient,
    add_common_filters,
    append_jsonl,
    completed_ids,
    concept_id_from_label,
    ensure_repo_root,
    load_full_chapter,
    load_manifest,
    normalize_label,
    reset_output_on_force,
    stable_hash,
    validate_confidence,
    write_error,
)


SUMMARY_OUTPUT_NAME = "section_summaries.jsonl"
CONCEPT_OUTPUT_NAME = "raw_concepts.jsonl"


_CONCEPT_ITEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "label": {"type": "string"},
        "definition": {"type": "string"},
        "source_unit_ids": {"type": "array", "items": {"type": "string"}},
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "unit_id": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["unit_id", "text"],
            },
        },
        "confidence": {"type": "number"},
    },
    "required": ["label", "definition", "source_unit_ids", "evidence", "confidence"],
}

_REQUIRES_CONCEPT_ITEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "label": {"type": "string"},
        "reason": {"type": "string"},
        "confidence": {"type": "number"},
    },
    "required": ["label", "reason", "confidence"],
}

SECTION_SUMMARY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "key_terms": {"type": "array", "items": {"type": "string"}},
        "evidence_snippets": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
        "concepts": {"type": "array", "items": _CONCEPT_ITEM_SCHEMA},
        "requires_concepts": {"type": "array", "items": _REQUIRES_CONCEPT_ITEM_SCHEMA},
        "confidence": {"type": "number"},
    },
    "required": ["summary", "key_terms", "evidence_snippets", "concepts", "requires_concepts", "confidence"],
}


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


def build_prompt(section: dict[str, Any]) -> str:
    return f"""Create a compact curriculum-graph summary, taught concept candidates, and prerequisite concept candidates for this textbook section.

Summarize the section as a teaching unit. Use the section text, all subsection
content, worked examples, diagrams, and tables. Do not summarize any other
chapter section.

Key terms should be concise textbook terms that would help later concept extraction and relationship generation.
Evidence snippets must be copied from the provided section content or attached examples/diagrams/tables.

CRITICAL CONSTRAINTS for performance and correctness:
- Keep the overall summary extremely concise (at most 2-3 sentences).
- Extract at most 5-6 primary taught concepts. Do not extract low-level details.
- Keep evidence snippets brief (at most 150 characters per snippet).
- Keep requires_concepts list to only the absolute necessary prerequisites.

For concepts (taught):
- Return only concepts explicitly taught, defined, explained, derived, applied, practiced, or substantially reinforced in this section.
- Do not include generic words such as introduction, overview, summary, exercise, example, student, question, activity.
- Prefer precise textbook concepts over vague umbrella concepts.
- Use source_unit_ids from the provided section_id or subsection ids only. Prefer subsection ids when possible.
- Each concept must include evidence copied from this section content.
- These are raw candidates; later stages will normalize aliases into canonical concepts.

For requires_concepts (prerequisites):
- Return concepts the learner must already understand before studying this section.
- These are concepts assumed as prior knowledge, not concepts taught here.
- Do not list a concept as required if this section introduces or teaches it from scratch.
- Each entry needs a reason explaining why the concept is a prerequisite.
- Use precise textbook concept labels, not vague terms.
- Omit if the section is introductory and has no real prerequisites.

Section:
{json.dumps(section, ensure_ascii=False)}

Return JSON matching the requested schema."""



def row_from_payload(
    *,
    chapter_id: str,
    section: dict[str, Any],
    payload: dict[str, Any],
    model: str,
) -> dict[str, Any]:
    snippets = [
        {"text": str(item.get("text") or "")[:800]}
        for item in payload.get("evidence_snippets", [])
        if isinstance(item, dict) and item.get("text")
    ]
    return {
        "section_summary_id": stable_hash({"section_id": section["id"], "stage": "section_summary"}, "section_summary"),
        "chapter_id": chapter_id,
        "section_id": section["id"],
        "section_number": section.get("number"),
        "title": section.get("title") or "",
        "summary": str(payload.get("summary") or "").strip(),
        "key_terms": [str(term).strip() for term in payload.get("key_terms", []) if str(term).strip()],
        "covered_subsection_ids": [subsection["id"] for subsection in section.get("subsections", [])],
        "evidence_snippets": snippets,
        "confidence": validate_confidence(payload.get("confidence")),
        "generation": {"model": model, "script": "03_generate_section_summaries.py"},
    }


def concept_rows_from_payload(
    *,
    ref: Any,
    section: dict[str, Any],
    payload: dict[str, Any],
    model: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Extract teaches and requires concept rows from the LLM payload.

    Returns (teaches_rows, requires_rows).
    """
    valid_unit_ids = {section["id"], *[subsection["id"] for subsection in section.get("subsections", [])]}

    # --- Teaches concepts ---
    teaches_rows: list[dict[str, Any]] = []
    for item in payload.get("concepts", []):
        label = str(item.get("label") or "").strip()
        if not label:
            continue
        source_unit_ids = [
            uid for uid in item.get("source_unit_ids", [])
            if isinstance(uid, str) and uid in valid_unit_ids
        ]
        evidence = [
            {"unit_id": ev.get("unit_id"), "text": str(ev.get("text") or "")[:1000]}
            for ev in item.get("evidence", [])
            if isinstance(ev, dict) and ev.get("unit_id") in valid_unit_ids and ev.get("text")
        ]
        if not source_unit_ids and evidence:
            source_unit_ids = sorted({ev["unit_id"] for ev in evidence})
        if not source_unit_ids or not evidence:
            continue
        row = {
            "chapter_id": ref.id,
            "subject": ref.subject,
            "grade": ref.grade,
            "chapter_title": ref.chapter_title,
            "source_section_id": section["id"],
            "relationship_type": "teaches",
            "label": label,
            "normalized_label": normalize_label(label),
            "candidate_concept_id": concept_id_from_label(label),
            "definition": str(item.get("definition") or "").strip(),
            "source_unit_ids": source_unit_ids,
            "evidence": evidence,
            "confidence": validate_confidence(item.get("confidence")),
            "generation": {"model": model, "script": "03_generate_section_summaries.py"},
        }
        row["raw_concept_id"] = stable_hash(row, "raw_concept")
        teaches_rows.append(row)

    # --- Requires concepts ---
    requires_rows: list[dict[str, Any]] = []
    for item in payload.get("requires_concepts", []):
        label = str(item.get("label") or "").strip()
        reason = str(item.get("reason") or "").strip()
        if not label:
            continue
        row = {
            "chapter_id": ref.id,
            "subject": ref.subject,
            "grade": ref.grade,
            "chapter_title": ref.chapter_title,
            "source_section_id": section["id"],
            "relationship_type": "requires",
            "label": label,
            "normalized_label": normalize_label(label),
            "candidate_concept_id": concept_id_from_label(label),
            "definition": "",
            "reason": reason,
            "source_unit_ids": [section["id"]],
            "evidence": [{"unit_id": section["id"], "text": reason[:1000]}],
            "confidence": validate_confidence(item.get("confidence")),
            "generation": {"model": model, "script": "03_generate_section_summaries.py"},
        }
        row["raw_concept_id"] = stable_hash(row, "raw_concept")
        requires_rows.append(row)

    return teaches_rows, requires_rows


def main() -> int:
    ensure_repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_filters(parser)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    summary_output = args.artifact_dir / SUMMARY_OUTPUT_NAME
    concept_output = args.artifact_dir / CONCEPT_OUTPUT_NAME
    reset_output_on_force(summary_output, args.force)
    reset_output_on_force(concept_output, args.force)
    done = set() if args.force else completed_ids(summary_output, "section_id")
    refs = load_manifest(args.manifest, subject=args.subject, grade=args.grade, chapter_id=args.chapter_id, limit=args.limit)
    client = None if args.dry_run else GeminiClient(args.model)
    total_sections = sum(len(load_full_chapter(ref.path)["chapter"].get("sections", [])) for ref in refs)
    pending_sections = 0
    for ref in refs:
        chapter = load_full_chapter(ref.path)
        pending_sections += sum(
            1
            for section in chapter["chapter"].get("sections", [])
            if section["id"] not in done
        )
    print(
        f"selected {len(refs)} chapters, {total_sections} sections "
        f"({pending_sections} pending)",
        flush=True,
    )
    written = 0
    failures = 0

    for ref in refs:
        chapter = load_full_chapter(ref.path)
        for section in chapter["chapter"].get("sections", []):
            if section["id"] in done:
                continue
            payload = section_payload(ref.id, section)
            prompt = build_prompt(payload)
            if args.dry_run:
                print(prompt[:12000])
                print(f"\n[prompt chars: {len(prompt)}]")
                return 0
            try:
                summary_payload = client.generate_json(prompt, SECTION_SUMMARY_SCHEMA)
                row = row_from_payload(chapter_id=ref.id, section=section, payload=summary_payload, model=args.model)
                teaches_rows, requires_rows = concept_rows_from_payload(ref=ref, section=section, payload=summary_payload, model=args.model)
                append_jsonl(summary_output, [row])
                append_jsonl(concept_output, teaches_rows + requires_rows)
                written += 1
                print(
                    f"{section['id']}: wrote summary, "
                    f"{len(teaches_rows)} teaches concepts, "
                    f"{len(requires_rows)} requires concepts"
                )
            except Exception as exc:
                failures += 1
                write_error(args.artifact_dir / "errors.jsonl", stage="section_summary", item_id=section["id"], error=str(exc))
                print(f"{section['id']}: ERROR {exc}")

    print(f"done: wrote {written} section summaries to {summary_output}")
    print(f"done: raw concepts written to {concept_output}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
