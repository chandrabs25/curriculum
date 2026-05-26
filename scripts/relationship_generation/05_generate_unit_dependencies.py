#!/usr/bin/env python3
"""Generate DEPENDS_ON_UNIT relationships using compact chapter outlines."""

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
    ensure_repo_root,
    load_full_chapter,
    load_manifest,
    read_jsonl,
    stable_hash,
    validate_confidence,
    write_error,
)


OUTPUT_NAME = "raw_unit_dependency_relationships.jsonl"


DEPENDENCY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "relationships": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "from_id": {"type": "string"},
                    "to_id": {"type": "string"},
                    "confidence": {"type": "number"},
                    "evidence": {
                        "type": "object",
                        "properties": {
                            "unit_id": {"type": "string"},
                            "text": {"type": "string"},
                            "reason": {"type": "string"},
                        },
                        "required": ["unit_id", "text", "reason"],
                    },
                },
                "required": ["from_id", "to_id", "confidence", "evidence"],
            },
        }
    },
    "required": ["relationships"],
}


def chapter_outline(source: dict[str, Any], summaries: list[dict[str, Any]], unit_edges: list[dict[str, Any]]) -> dict[str, Any]:
    by_unit = {row["unit_id"]: row for row in summaries}
    concept_edges_by_unit: dict[str, list[dict[str, Any]]] = {}
    for edge in unit_edges:
        if edge.get("chapter_id") != source["id"]:
            continue
        concept_edges_by_unit.setdefault(edge.get("from_id"), []).append(
            {"type": edge.get("type"), "concept_id": edge.get("to_id"), "confidence": edge.get("confidence")}
        )

    sections = []
    for section in source["chapter"].get("sections", []):
        sec_summary = by_unit.get(section["id"], {})
        sec = {
            "id": section["id"],
            "number": section.get("number"),
            "title": section.get("title"),
            "summary": sec_summary.get("summary"),
            "concept_edges": concept_edges_by_unit.get(section["id"], []),
            "subsections": [],
        }
        for subsection in section.get("subsections", []):
            sub_summary = by_unit.get(subsection["id"], {})
            sec["subsections"].append(
                {
                    "id": subsection["id"],
                    "order": subsection.get("order"),
                    "title": subsection.get("title"),
                    "content_type": subsection.get("content_type"),
                    "summary": sub_summary.get("summary"),
                    "candidate_concept_ids": sub_summary.get("candidate_concept_ids", []),
                    "concept_edges": concept_edges_by_unit.get(subsection["id"], []),
                }
            )
        sections.append(sec)
    return {
        "chapter_id": source["id"],
        "chapter_title": source["chapter"].get("title"),
        "sections": sections,
    }


def build_prompt(outline: dict[str, Any]) -> str:
    return f"""Generate prerequisite unit dependencies for this chapter outline.

Relationship meaning:
- DEPENDS_ON_UNIT: from_id unit should be learned after to_id unit.

Use only unit ids in the outline. Do not create cross-chapter dependencies.
Prefer section-level edges unless a subsection dependency is clearly more precise.
Use compact summaries and concept edges as evidence; do not invent external prerequisites.

Chapter outline:
{json.dumps(outline, ensure_ascii=False)}

Return JSON matching the requested schema."""


def normalize_rows(chapter_id: str, payload: dict[str, Any], model: str) -> list[dict[str, Any]]:
    rows = []
    for item in payload.get("relationships", []):
        row = {
            "chapter_id": chapter_id,
            "type": "DEPENDS_ON_UNIT",
            "from_id": item.get("from_id"),
            "to_id": item.get("to_id"),
            "confidence": validate_confidence(item.get("confidence")),
            "evidence": {
                "unit_id": item.get("evidence", {}).get("unit_id") or item.get("from_id"),
                "text": str(item.get("evidence", {}).get("text") or "")[:1200],
                "reason": str(item.get("evidence", {}).get("reason") or "")[:800],
            },
            "generation": {"model": model, "script": "05_generate_unit_dependencies.py"},
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
    done = set() if args.force else completed_chapter_ids(output)
    summaries = read_jsonl(args.artifact_dir / "unit_summaries.jsonl")
    unit_edges = read_jsonl(args.artifact_dir / "raw_unit_concept_relationships.jsonl")
    refs = load_manifest(args.manifest, subject=args.subject, grade=args.grade, chapter_id=args.chapter_id, limit=args.limit)
    client = None if args.dry_run else GeminiClient(args.model)
    written = 0

    for ref in refs:
        if ref.id in done:
            continue
        source = load_full_chapter(ref.path)
        outline = chapter_outline(source, [s for s in summaries if s.get("chapter_id") == ref.id], unit_edges)
        prompt = build_prompt(outline)
        if args.dry_run:
            print(prompt[:5000])
            return 0
        try:
            payload = client.generate_json(prompt, DEPENDENCY_SCHEMA)
            rows = normalize_rows(ref.id, payload, args.model)
            written += append_jsonl(output, rows)
            print(f"{ref.id}: wrote {len(rows)} unit dependencies")
        except Exception as exc:
            write_error(args.artifact_dir / "errors.jsonl", stage="unit_dependencies", item_id=ref.id, error=str(exc))
            print(f"{ref.id}: ERROR {exc}")

    print(f"done: wrote {written} relationships to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
