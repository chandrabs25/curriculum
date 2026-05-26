#!/usr/bin/env python3
"""Validate refined relationship-generation artifacts."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path

from common import (
    RELATIONSHIP_TYPES,
    add_common_filters,
    ensure_repo_root,
    load_chapter_context,
    load_manifest,
    read_jsonl,
    unit_ids_from_chapter,
    exercise_ids_from_chapter,
    write_json,
)


def scoped_source_ids(args: argparse.Namespace) -> tuple[set[str], set[str], set[str], set[str]]:
    refs = load_manifest(
        args.manifest,
        subject=args.subject,
        grade=args.grade,
        chapter_id=args.chapter_id,
        limit=args.limit,
    )
    unit_ids: set[str] = set()
    exercise_ids: set[str] = set()
    section_ids: set[str] = set()
    chapter_ids: set[str] = set()
    for ref in refs:
        data = load_chapter_context(ref.path, max_chars=10**9)
        chapter_ids.add(ref.id)
        unit_ids.update(unit_ids_from_chapter(data))
        exercise_ids.update(exercise_ids_from_chapter(data))
        section_ids.update(section["id"] for section in data["chapter"].get("sections", []))
    return unit_ids, exercise_ids, section_ids, chapter_ids


def main() -> int:
    ensure_repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_filters(parser)
    args = parser.parse_args()

    _unit_ids, exercise_ids, section_ids, scoped_chapter_ids = scoped_source_ids(args)
    concepts = read_jsonl(args.artifact_dir / "canonical_concepts.jsonl")
    section_summaries = read_jsonl(args.artifact_dir / "section_summaries.jsonl")
    accepted = read_jsonl(args.artifact_dir / "accepted_relationships.jsonl")
    review = read_jsonl(args.artifact_dir / "review" / "relationships.jsonl")
    rejected = read_jsonl(args.artifact_dir / "rejected" / "relationships.jsonl")

    concept_ids = {c.get("concept_id") for c in concepts}
    scoped_section_summaries = [
        s for s in section_summaries
        if not scoped_chapter_ids or s.get("chapter_id") in scoped_chapter_ids
    ]
    scoped_accepted = [
        r for r in accepted
        if not scoped_chapter_ids or r.get("chapter_id") in scoped_chapter_ids
    ]
    summary_section_ids = {s.get("section_id") for s in scoped_section_summaries}
    errors: list[dict] = []
    warnings: list[dict] = []
    seen_edges = set()
    coverage = defaultdict(Counter)

    for concept in concepts:
        cid = concept.get("concept_id")
        if not cid or not str(cid).startswith("concept:"):
            errors.append({"kind": "invalid_concept_id", "concept": concept})
        if not concept.get("canonical_label"):
            errors.append({"kind": "missing_concept_label", "concept_id": cid})

    for sid in summary_section_ids:
        if sid not in section_ids:
            errors.append({"kind": "summary_for_unknown_section", "section_id": sid})

    missing_summaries = section_ids - summary_section_ids
    if missing_summaries:
        errors.append({"kind": "missing_section_summaries", "count": len(missing_summaries), "sample": sorted(missing_summaries)[:20]})

    for rel in scoped_accepted:
        rid = rel.get("relationship_id")
        rel_type = rel.get("type")
        from_id = rel.get("from_id")
        to_id = rel.get("to_id")
        if rel_type not in RELATIONSHIP_TYPES:
            errors.append({"kind": "invalid_relationship_type", "relationship_id": rid, "type": rel_type})
        if (rel_type, from_id, to_id) in seen_edges:
            errors.append({"kind": "duplicate_relationship", "relationship_id": rid})
        seen_edges.add((rel_type, from_id, to_id))
        if rel_type in {"DEPENDS_ON_UNIT", "REQUIRES_CONCEPT", "TEACHES_CONCEPT"} and from_id not in section_ids:
            errors.append({"kind": "dangling_from_section", "relationship_id": rid, "from_id": from_id})
        if rel_type in {"TESTS_UNIT", "TESTS_CONCEPT"} and from_id not in exercise_ids:
            errors.append({"kind": "dangling_from_exercise", "relationship_id": rid, "from_id": from_id})
        if rel_type in {"DEPENDS_ON_UNIT", "TESTS_UNIT"} and to_id not in section_ids:
            errors.append({"kind": "dangling_to_section", "relationship_id": rid, "to_id": to_id})
        if rel_type in {"REQUIRES_CONCEPT", "TEACHES_CONCEPT", "TESTS_CONCEPT"} and to_id not in concept_ids:
            errors.append({"kind": "dangling_to_concept", "relationship_id": rid, "to_id": to_id})
        evidence = rel.get("evidence") or {}
        if not evidence.get("text") or not evidence.get("reason"):
            errors.append({"kind": "missing_evidence", "relationship_id": rid})
        coverage[rel.get("chapter_id") or "unknown"][rel_type] += 1

    report = {
        "status": "ok" if not errors else "failed",
        "concept_count": len(concepts),
        "section_summary_count": len(scoped_section_summaries),
        "accepted_relationship_count": len(scoped_accepted),
        "review_relationship_count": len(review),
        "rejected_relationship_count": len(rejected),
        "relationship_count_by_type": dict(Counter(r.get("type") for r in scoped_accepted)),
        "chapter_coverage": {chapter: dict(counts) for chapter, counts in sorted(coverage.items())},
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors[:500],
        "warnings": warnings[:100],
    }
    write_json(args.artifact_dir / "validation_report.json", report)
    print(report["status"], f"errors={len(errors)} warnings={len(warnings)}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
