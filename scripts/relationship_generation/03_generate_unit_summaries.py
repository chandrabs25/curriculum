#!/usr/bin/env python3
"""Generate compact summaries for each section/subsection unit."""

from __future__ import annotations

import argparse
import json
from typing import Any

from common import (
    DEFAULT_MODEL,
    GeminiClient,
    add_common_filters,
    append_jsonl,
    compact_text,
    completed_ids,
    ensure_repo_root,
    iter_units,
    load_full_chapter,
    load_manifest,
    read_jsonl,
    relevant_concepts_for_text,
    stable_hash,
    validate_confidence,
    write_error,
)


OUTPUT_NAME = "unit_summaries.jsonl"


SUMMARY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "key_terms": {"type": "array", "items": {"type": "string"}},
        "candidate_concept_ids": {"type": "array", "items": {"type": "string"}},
        "evidence_snippets": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
        "confidence": {"type": "number"},
    },
    "required": ["summary", "key_terms", "candidate_concept_ids", "evidence_snippets", "confidence"],
}


def unit_prompt(unit: dict[str, Any], concepts: list[dict[str, Any]]) -> str:
    unit_payload = {
        "unit_id": unit["unit_id"],
        "unit_type": unit["unit_type"],
        "title": unit["title"],
        "content_type": unit["content_type"],
        "content_text": compact_text(unit.get("content_text") or "", 2500),
        "child_subsections": [
            {
                **child,
                "content_text": compact_text(child.get("content_text") or "", 700),
            }
            for child in unit.get("child_subsections", [])
        ],
        "worked_examples": unit.get("worked_examples", []),
        "diagrams": unit.get("diagrams", []),
        "tables": unit.get("tables", []),
    }
    return f"""Create a compact curriculum-graph summary for this textbook unit.

Use the canonical concept registry only for candidate_concept_ids. If no concept fits, return an empty list.
Evidence snippets must be copied from the unit content or attached examples/diagrams/tables.

Canonical concepts:
{json.dumps(concepts, ensure_ascii=False)}

Unit:
{json.dumps(unit_payload, ensure_ascii=False)}

Return JSON matching the requested schema."""


def row_from_payload(unit: dict[str, Any], payload: dict[str, Any], model: str) -> dict[str, Any]:
    concept_ids = [
        str(cid)
        for cid in payload.get("candidate_concept_ids", [])
        if isinstance(cid, str) and cid.startswith("concept:")
    ]
    snippets = [
        {"text": str(item.get("text") or "")[:800]}
        for item in payload.get("evidence_snippets", [])
        if isinstance(item, dict) and item.get("text")
    ]
    row = {
        "unit_summary_id": stable_hash({"unit_id": unit["unit_id"], "stage": "summary"}, "unit_summary"),
        "unit_id": unit["unit_id"],
        "chapter_id": unit["chapter_id"],
        "unit_type": unit["unit_type"],
        "parent_section_id": unit.get("parent_section_id"),
        "title": unit["title"],
        "content_type": unit["content_type"],
        "summary": str(payload.get("summary") or "").strip(),
        "key_terms": [str(term).strip() for term in payload.get("key_terms", []) if str(term).strip()],
        "candidate_concept_ids": concept_ids,
        "evidence_snippets": snippets,
        "confidence": validate_confidence(payload.get("confidence")),
        "generation": {"model": model, "script": "03_generate_unit_summaries.py"},
    }
    return row


def main() -> int:
    ensure_repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_filters(parser)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    output = args.artifact_dir / OUTPUT_NAME
    done = set() if args.force else completed_ids(output, "unit_id")
    concepts = read_jsonl(args.artifact_dir / "canonical_concepts.jsonl")
    refs = load_manifest(args.manifest, subject=args.subject, grade=args.grade, chapter_id=args.chapter_id, limit=args.limit)
    client = None if args.dry_run else GeminiClient(args.model)
    written = 0

    for ref in refs:
        chapter = load_full_chapter(ref.path)
        for unit in iter_units(chapter):
            if unit["unit_id"] in done:
                continue
            context_text = " ".join(
                [
                    unit.get("title", ""),
                    unit.get("content_text", ""),
                    json.dumps(unit.get("child_subsections", []), ensure_ascii=False),
                    json.dumps(unit.get("worked_examples", []), ensure_ascii=False),
                ]
            )
            concept_subset = relevant_concepts_for_text(ref.id, ref.subject, context_text, concepts, limit=80)
            prompt = unit_prompt(unit, concept_subset)
            if args.dry_run:
                print(prompt[:5000])
                return 0
            try:
                payload = client.generate_json(prompt, SUMMARY_SCHEMA)
                row = row_from_payload(unit, payload, args.model)
                append_jsonl(output, [row])
                written += 1
                print(f"{unit['unit_id']}: wrote summary")
            except Exception as exc:
                write_error(args.artifact_dir / "errors.jsonl", stage="unit_summary", item_id=unit["unit_id"], error=str(exc))
                print(f"{unit['unit_id']}: ERROR {exc}")

    print(f"done: wrote {written} summaries to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
