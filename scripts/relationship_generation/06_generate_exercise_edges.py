#!/usr/bin/env python3
"""Generate TESTS_UNIT and TESTS_CONCEPT relationships for exercises."""

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
    iter_exercises,
    load_full_chapter,
    load_manifest,
    read_jsonl,
    stable_hash,
    validate_confidence,
    write_error,
)


OUTPUT_NAME = "raw_exercise_relationships.jsonl"


EXERCISE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "relationships": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["TESTS_UNIT", "TESTS_CONCEPT"]},
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


def candidate_context(chapter_id: str, summaries: list[dict[str, Any]], unit_edges: list[dict[str, Any]]) -> dict[str, Any]:
    concept_ids = sorted(
        {
            edge.get("to_id")
            for edge in unit_edges
            if edge.get("chapter_id") == chapter_id and edge.get("type") == "TEACHES_CONCEPT" and edge.get("to_id")
        }
    )
    return {
        "unit_summaries": [
            {
                "unit_id": row.get("unit_id"),
                "unit_type": row.get("unit_type"),
                "parent_section_id": row.get("parent_section_id"),
                "title": row.get("title"),
                "content_type": row.get("content_type"),
                "summary": row.get("summary"),
                "candidate_concept_ids": row.get("candidate_concept_ids", []),
            }
            for row in summaries
            if row.get("chapter_id") == chapter_id
        ],
        "chapter_teaches_concept_ids": concept_ids,
    }


def build_prompt(exercise: dict[str, Any], candidates: dict[str, Any]) -> str:
    exercise_payload = {
        "exercise_id": exercise["exercise_id"],
        "number": exercise.get("number"),
        "difficulty": exercise.get("difficulty"),
        "exercise_type": exercise.get("exercise_type"),
        "problem": compact_text(exercise.get("problem") or "", 2400),
    }
    return f"""Map this exercise to the textbook units and concepts it directly assesses.

Relationship meanings:
- TESTS_UNIT: the exercise directly assesses a section/subsection.
- TESTS_CONCEPT: the exercise directly assesses a canonical concept.

Use only unit ids and concept ids from the candidate context.
Prefer precise subsection targets when clear; use section targets for broad exercises.
Every edge needs evidence from the exercise text and a reason.

Exercise:
{json.dumps(exercise_payload, ensure_ascii=False)}

Candidate context:
{json.dumps(candidates, ensure_ascii=False)}

Return JSON matching the requested schema."""


def normalize_rows(exercise: dict[str, Any], payload: dict[str, Any], model: str) -> list[dict[str, Any]]:
    rows = []
    for item in payload.get("relationships", []):
        rel_type = item.get("type")
        if rel_type not in {"TESTS_UNIT", "TESTS_CONCEPT"}:
            continue
        row = {
            "chapter_id": exercise["chapter_id"],
            "type": rel_type,
            "from_id": exercise["exercise_id"],
            "to_id": item.get("to_id"),
            "confidence": validate_confidence(item.get("confidence")),
            "evidence": {
                "unit_id": exercise["exercise_id"],
                "text": str(item.get("evidence", {}).get("text") or "")[:1200],
                "reason": str(item.get("evidence", {}).get("reason") or "")[:800],
            },
            "generation": {"model": model, "script": "06_generate_exercise_edges.py"},
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
    summaries = read_jsonl(args.artifact_dir / "unit_summaries.jsonl")
    unit_edges = read_jsonl(args.artifact_dir / "raw_unit_concept_relationships.jsonl")
    refs = load_manifest(args.manifest, subject=args.subject, grade=args.grade, chapter_id=args.chapter_id, limit=args.limit)
    client = None if args.dry_run else GeminiClient(args.model)
    written = 0

    for ref in refs:
        source = load_full_chapter(ref.path)
        candidates = candidate_context(ref.id, summaries, unit_edges)
        for exercise in iter_exercises(source):
            if exercise["exercise_id"] in done:
                continue
            prompt = build_prompt(exercise, candidates)
            if args.dry_run:
                print(prompt[:5000])
                return 0
            try:
                payload = client.generate_json(prompt, EXERCISE_SCHEMA)
                rows = normalize_rows(exercise, payload, args.model)
                written += append_jsonl(output, rows)
                print(f"{exercise['exercise_id']}: wrote {len(rows)} exercise edges")
            except Exception as exc:
                write_error(args.artifact_dir / "errors.jsonl", stage="exercise_edges", item_id=exercise["exercise_id"], error=str(exc))
                print(f"{exercise['exercise_id']}: ERROR {exc}")

    print(f"done: wrote {written} relationships to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
