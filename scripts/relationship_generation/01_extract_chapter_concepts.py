#!/usr/bin/env python3
"""Extract raw concept candidates from content-only textbook chapters."""

from __future__ import annotations

import argparse
import json
from typing import Any

from common import (
    DEFAULT_MODEL,
    GeminiClient,
    add_common_filters,
    append_jsonl,
    completed_chapter_ids,
    concept_id_from_label,
    ensure_repo_root,
    load_chapter_context,
    load_manifest,
    normalize_label,
    stable_hash,
    validate_confidence,
    write_error,
)


OUTPUT_NAME = "raw_concepts.jsonl"


CONCEPT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "concepts": {
            "type": "array",
            "items": {
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
            },
        }
    },
    "required": ["concepts"],
}


def build_prompt(context: dict[str, Any]) -> str:
    return f"""You are extracting canonical textbook concepts for a curriculum knowledge graph.

Return only concepts that are explicitly taught, defined, explained, derived, applied, or repeatedly used in the chapter content.
Do not include generic words such as introduction, overview, summary, exercise, example, student, question.
Prefer precise concepts over vague umbrella concepts.
Each concept must include source evidence copied from the provided content.

For source_unit_ids, use section or subsection ids from the input. Prefer subsection ids when possible.

Chapter content JSON:
{json.dumps(context, ensure_ascii=False)}

Return JSON matching the requested schema."""


def normalize_rows(chapter: dict[str, Any], payload: dict[str, Any], model: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    valid_unit_ids = {
        chapter["chapter"]["id"],
        *[section["id"] for section in chapter["chapter"].get("sections", [])],
        *[
            subsection["id"]
            for section in chapter["chapter"].get("sections", [])
            for subsection in section.get("subsections", [])
        ],
    }
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
        base = {
            "chapter_id": chapter["id"],
            "subject": chapter["subject"],
            "grade": chapter["grade"],
            "chapter_title": chapter["chapter"]["title"],
            "label": label,
            "normalized_label": normalize_label(label),
            "candidate_concept_id": concept_id_from_label(label),
            "definition": str(item.get("definition") or "").strip(),
            "source_unit_ids": source_unit_ids,
            "evidence": evidence,
            "confidence": validate_confidence(item.get("confidence")),
            "generation": {"model": model, "script": "01_extract_chapter_concepts.py"},
        }
        base["raw_concept_id"] = stable_hash(base, "raw_concept")
        rows.append(base)
    return rows


def main() -> int:
    ensure_repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_filters(parser)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    output = args.artifact_dir / OUTPUT_NAME
    done = set() if args.force else completed_chapter_ids(output)
    refs = load_manifest(
        args.manifest,
        subject=args.subject,
        grade=args.grade,
        chapter_id=args.chapter_id,
        limit=args.limit,
    )
    client = None if args.dry_run else GeminiClient(args.model)

    written = 0
    for ref in refs:
        if ref.id in done:
            print(f"skip {ref.id} (already extracted)")
            continue
        context = load_chapter_context(ref.path)
        prompt = build_prompt(context)
        if args.dry_run:
            print(prompt[:4000])
            continue
        try:
            payload = client.generate_json(prompt, CONCEPT_SCHEMA)
            rows = normalize_rows(context, payload, args.model)
            written += append_jsonl(output, rows)
            print(f"{ref.id}: wrote {len(rows)} raw concepts")
        except Exception as exc:
            write_error(args.artifact_dir / "errors.jsonl", stage="extract_concepts", item_id=ref.id, error=str(exc))
            print(f"{ref.id}: ERROR {exc}")
    print(f"done: wrote {written} records to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
