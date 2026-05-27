#!/usr/bin/env python3
"""Build a usable-corpus index from the current generated artifacts."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from common import ensure_repo_root, is_curriculum_section_id, load_full_chapter, load_manifest, read_jsonl, write_json


def chapter_summary_rows(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_chapter: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        chapter_id = row.get("chapter_id")
        if chapter_id:
            by_chapter[chapter_id].append(row)
    return dict(by_chapter)


def concept_counts_by_chapter(rows: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in rows:
        chapter_id = row.get("chapter_id")
        if chapter_id:
            counts[chapter_id] += 1
    return counts


def main() -> int:
    ensure_repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("data/textbook_sources/manifest.json"))
    parser.add_argument("--artifact-dir", type=Path, default=Path("data/relationship_artifacts"))
    parser.add_argument("--output", type=Path, default=Path("data/relationship_artifacts/usable_chapters.json"))
    parser.add_argument("--subject", choices=["physics", "chemistry", "biology"])
    parser.add_argument("--grade", type=int, choices=[11, 12])
    parser.add_argument("--allow-duplicates", action="store_true")
    args = parser.parse_args()

    refs = load_manifest(args.manifest, subject=args.subject, grade=args.grade)
    summaries_by_chapter = chapter_summary_rows(read_jsonl(args.artifact_dir / "section_summaries.jsonl"))
    raw_concept_counts = concept_counts_by_chapter(read_jsonl(args.artifact_dir / "raw_concepts.jsonl"))
    canonical_concepts = read_jsonl(args.artifact_dir / "canonical_concepts.jsonl")

    chapters: list[dict[str, Any]] = []
    usable_chapter_ids: list[str] = []
    partial_chapter_ids: list[str] = []
    missing_chapter_ids: list[str] = []
    duplicate_chapter_ids: list[str] = []

    for ref in refs:
        source = load_full_chapter(ref.path)
        excluded_section_ids = [
            section["id"]
            for section in source["chapter"].get("sections", [])
            if not is_curriculum_section_id(section["id"])
        ]
        expected_ids = [
            section["id"]
            for section in source["chapter"].get("sections", [])
            if is_curriculum_section_id(section["id"])
        ]
        expected_set = set(expected_ids)
        summary_rows = summaries_by_chapter.get(ref.id, [])
        summary_ids = [
            row.get("section_id")
            for row in summary_rows
            if row.get("section_id") and is_curriculum_section_id(row.get("section_id"))
        ]
        summary_set = set(summary_ids)
        duplicate_section_ids = sorted(section_id for section_id, count in Counter(summary_ids).items() if count > 1)
        missing_section_ids = sorted(expected_set - summary_set)
        unknown_section_ids = sorted(summary_set - expected_set)
        is_complete = not missing_section_ids and not unknown_section_ids
        has_duplicates = bool(duplicate_section_ids)
        is_usable = is_complete and (args.allow_duplicates or not has_duplicates)

        status = "usable" if is_usable else "partial"
        if not summary_rows:
            status = "missing"
        elif has_duplicates and not args.allow_duplicates:
            status = "duplicate_review"

        if is_usable:
            usable_chapter_ids.append(ref.id)
        elif status == "missing":
            missing_chapter_ids.append(ref.id)
        else:
            partial_chapter_ids.append(ref.id)
        if has_duplicates:
            duplicate_chapter_ids.append(ref.id)

        chapters.append(
            {
                "chapter_id": ref.id,
                "subject": ref.subject,
                "grade": ref.grade,
                "chapter_number": ref.chapter_number,
                "chapter_title": ref.chapter_title,
                "status": status,
                "usable": is_usable,
                "expected_section_count": len(expected_ids),
                "summary_row_count": len(summary_rows),
                "unique_summary_section_count": len(summary_set),
                "raw_concept_count": raw_concept_counts.get(ref.id, 0),
                "missing_section_ids": missing_section_ids,
                "unknown_section_ids": unknown_section_ids,
                "duplicate_section_ids": duplicate_section_ids,
                "excluded_non_curriculum_section_ids": excluded_section_ids,
            }
        )

    report = {
        "status": "ok",
        "source_chapter_count": len(refs),
        "source_section_count": sum(chapter["expected_section_count"] for chapter in chapters),
        "summary_row_count": sum(chapter["summary_row_count"] for chapter in chapters),
        "unique_summary_section_count": sum(chapter["unique_summary_section_count"] for chapter in chapters),
        "raw_concept_count": sum(raw_concept_counts.values()),
        "canonical_concept_count": len(canonical_concepts),
        "usable_chapter_count": len(usable_chapter_ids),
        "usable_section_count": sum(chapter["expected_section_count"] for chapter in chapters if chapter["usable"]),
        "partial_chapter_count": len(partial_chapter_ids),
        "missing_chapter_count": len(missing_chapter_ids),
        "duplicate_chapter_count": len(duplicate_chapter_ids),
        "excluded_non_curriculum_section_count": sum(len(chapter["excluded_non_curriculum_section_ids"]) for chapter in chapters),
        "usable_chapter_ids": usable_chapter_ids,
        "partial_chapter_ids": partial_chapter_ids,
        "missing_chapter_ids": missing_chapter_ids,
        "duplicate_chapter_ids": duplicate_chapter_ids,
        "chapters": chapters,
        "notes": [
            "Only chapters with all expected sections summarized and no unknown sections are marked usable.",
            "Duplicate summary rows require review unless --allow-duplicates is set.",
        ],
    }
    write_json(args.output, report)
    print(
        f"usable chapters={report['usable_chapter_count']} "
        f"usable sections={report['usable_section_count']} "
        f"partial={report['partial_chapter_count']} "
        f"missing={report['missing_chapter_count']} "
        f"duplicates={report['duplicate_chapter_count']}"
    )
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
