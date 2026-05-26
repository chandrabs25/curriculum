#!/usr/bin/env python3
"""Generate TEACHES_CONCEPT and REQUIRES_CONCEPT edges for units."""

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
    load_unit_summaries,
    read_jsonl,
    relevant_concepts_for_text,
    stable_hash,
    validate_confidence,
    write_error,
)


OUTPUT_NAME = "raw_unit_concept_relationships.jsonl"


UNIT_CONCEPT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "relationships": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["TEACHES_CONCEPT", "REQUIRES_CONCEPT"]},
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


def build_prompt(unit: dict[str, Any], summary: dict[str, Any] | None, concepts: list[dict[str, Any]]) -> str:
    unit_payload = {
        "unit_id": unit["unit_id"],
        "unit_type": unit["unit_type"],
        "title": unit["title"],
        "content_type": unit["content_type"],
        "content_text": compact_text(unit.get("content_text") or "", 3200),
        "child_subsections": [
            {
                **child,
                "content_text": compact_text(child.get("content_text") or "", 800),
            }
            for child in unit.get("child_subsections", [])
        ],
        "worked_examples": unit.get("worked_examples", []),
        "diagrams": unit.get("diagrams", []),
        "tables": unit.get("tables", []),
        "summary": summary,
    }
    return f"""Generate concept relationships for exactly one textbook unit.

Relationship meanings:
- TEACHES_CONCEPT: this unit introduces, defines, explains, derives, applies, or substantially reinforces the concept.
- REQUIRES_CONCEPT: the student should already understand this concept before studying the unit.

Do not mark a concept as required merely because the unit teaches it.
Use only concept ids from the canonical concept registry.
Every edge needs direct evidence text and a reason.

Canonical concepts:
{json.dumps(concepts, ensure_ascii=False)}

Unit:
{json.dumps(unit_payload, ensure_ascii=False)}

Return JSON matching the requested schema."""


def normalize_rows(unit: dict[str, Any], payload: dict[str, Any], model: str) -> list[dict[str, Any]]:
    rows = []
    for item in payload.get("relationships", []):
        rel_type = item.get("type")
        if rel_type not in {"TEACHES_CONCEPT", "REQUIRES_CONCEPT"}:
            continue
        row = {
            "chapter_id": unit["chapter_id"],
            "type": rel_type,
            "from_id": unit["unit_id"],
            "to_id": item.get("to_id"),
            "confidence": validate_confidence(item.get("confidence")),
            "evidence": {
                "unit_id": unit["unit_id"],
                "text": str(item.get("evidence", {}).get("text") or "")[:1200],
                "reason": str(item.get("evidence", {}).get("reason") or "")[:800],
            },
            "generation": {"model": model, "script": "04_generate_unit_concept_edges.py"},
        }
        row["relationship_id"] = stable_hash(row, "rel")
        rows.append(row)
    return rows


def main() -> int:
    ensure_repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_filters(parser)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    output = args.artifact_dir / OUTPUT_NAME
    done = set() if args.force else completed_ids(output, "from_id")
    concepts = read_jsonl(args.artifact_dir / "canonical_concepts.jsonl")
    summaries = load_unit_summaries(args.artifact_dir / "unit_summaries.jsonl")
    refs = load_manifest(args.manifest, subject=args.subject, grade=args.grade, chapter_id=args.chapter_id, limit=args.limit)
    client = None if args.dry_run else GeminiClient(args.model)
    written = 0

    for ref in refs:
        chapter = load_full_chapter(ref.path)
        for unit in iter_units(chapter):
            if unit["unit_id"] in done:
                continue
            text = " ".join([unit.get("title", ""), unit.get("content_text", ""), json.dumps(summaries.get(unit["unit_id"], {}), ensure_ascii=False)])
            if unit.get("child_subsections"):
                text += " " + json.dumps(unit.get("child_subsections", []), ensure_ascii=False)
            concept_subset = relevant_concepts_for_text(ref.id, ref.subject, text, concepts, limit=100)
            prompt = build_prompt(unit, summaries.get(unit["unit_id"]), concept_subset)
            if args.dry_run:
                print(prompt[:5000])
                return 0
            try:
                payload = client.generate_json(prompt, UNIT_CONCEPT_SCHEMA)
                rows = normalize_rows(unit, payload, args.model)
                written += append_jsonl(output, rows)
                print(f"{unit['unit_id']}: wrote {len(rows)} unit-concept edges")
            except Exception as exc:
                write_error(args.artifact_dir / "errors.jsonl", stage="unit_concept_edges", item_id=unit["unit_id"], error=str(exc))
                print(f"{unit['unit_id']}: ERROR {exc}")

    print(f"done: wrote {written} relationships to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
