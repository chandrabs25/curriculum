#!/usr/bin/env python3
"""Generate compact summaries for each textbook section."""

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
    ensure_repo_root,
    load_full_chapter,
    load_manifest,
    reset_output_on_force,
    stable_hash,
    validate_confidence,
    write_error,
)


OUTPUT_NAME = "section_summaries.jsonl"


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
        "confidence": {"type": "number"},
    },
    "required": ["summary", "key_terms", "evidence_snippets", "confidence"],
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
    return f"""Create a compact curriculum-graph summary for this textbook section.

Summarize the section as a teaching unit. Use the section text, all subsection
content, worked examples, diagrams, and tables. Do not summarize any other
chapter section.

Key terms should be concise textbook terms that would help later concept extraction and relationship generation.
Evidence snippets must be copied from the provided section content or attached examples/diagrams/tables.

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


def main() -> int:
    ensure_repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_filters(parser)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    output = args.artifact_dir / OUTPUT_NAME
    reset_output_on_force(output, args.force)
    done = set() if args.force else completed_ids(output, "section_id")
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
                append_jsonl(output, [row])
                written += 1
                print(f"{section['id']}: wrote section summary")
            except Exception as exc:
                failures += 1
                write_error(args.artifact_dir / "errors.jsonl", stage="section_summary", item_id=section["id"], error=str(exc))
                print(f"{section['id']}: ERROR {exc}")

    print(f"done: wrote {written} section summaries to {output}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
