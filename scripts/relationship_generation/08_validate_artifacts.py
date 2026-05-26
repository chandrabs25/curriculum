#!/usr/bin/env python3
"""Validate refined relationship-generation artifacts."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path

from common import (
    RELATIONSHIP_TYPES,
    all_source_ids_from_manifest,
    ensure_repo_root,
    read_jsonl,
    write_json,
)


def main() -> int:
    ensure_repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, default=Path("data/relationship_artifacts"))
    parser.add_argument("--manifest", type=Path, default=Path("data/textbook_sources/manifest.json"))
    args = parser.parse_args()

    unit_ids, exercise_ids = all_source_ids_from_manifest(args.manifest)
    concepts = read_jsonl(args.artifact_dir / "canonical_concepts.jsonl")
    summaries = read_jsonl(args.artifact_dir / "unit_summaries.jsonl")
    accepted = read_jsonl(args.artifact_dir / "accepted_relationships.jsonl")
    review = read_jsonl(args.artifact_dir / "review" / "relationships.jsonl")
    rejected = read_jsonl(args.artifact_dir / "rejected" / "relationships.jsonl")

    concept_ids = {c.get("concept_id") for c in concepts}
    summary_unit_ids = {s.get("unit_id") for s in summaries}
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

    for sid in summary_unit_ids:
        if sid not in unit_ids:
            errors.append({"kind": "summary_for_unknown_unit", "unit_id": sid})

    required_summary_unit_ids = {unit_id for unit_id in unit_ids if str(unit_id).count(":") > 3}
    missing_summaries = required_summary_unit_ids - summary_unit_ids
    if missing_summaries:
        warnings.append({"kind": "missing_unit_summaries", "count": len(missing_summaries), "sample": sorted(missing_summaries)[:20]})

    for rel in accepted:
        rid = rel.get("relationship_id")
        rel_type = rel.get("type")
        from_id = rel.get("from_id")
        to_id = rel.get("to_id")
        if rel_type not in RELATIONSHIP_TYPES:
            errors.append({"kind": "invalid_relationship_type", "relationship_id": rid, "type": rel_type})
        if (rel_type, from_id, to_id) in seen_edges:
            errors.append({"kind": "duplicate_relationship", "relationship_id": rid})
        seen_edges.add((rel_type, from_id, to_id))
        if rel_type in {"DEPENDS_ON_UNIT", "REQUIRES_CONCEPT", "TEACHES_CONCEPT"} and from_id not in unit_ids:
            errors.append({"kind": "dangling_from_unit", "relationship_id": rid, "from_id": from_id})
        if rel_type in {"TESTS_UNIT", "TESTS_CONCEPT"} and from_id not in exercise_ids:
            errors.append({"kind": "dangling_from_exercise", "relationship_id": rid, "from_id": from_id})
        if rel_type in {"DEPENDS_ON_UNIT", "TESTS_UNIT"} and to_id not in unit_ids:
            errors.append({"kind": "dangling_to_unit", "relationship_id": rid, "to_id": to_id})
        if rel_type in {"REQUIRES_CONCEPT", "TEACHES_CONCEPT", "TESTS_CONCEPT"} and to_id not in concept_ids:
            errors.append({"kind": "dangling_to_concept", "relationship_id": rid, "to_id": to_id})
        evidence = rel.get("evidence") or {}
        if not evidence.get("text") or not evidence.get("reason"):
            errors.append({"kind": "missing_evidence", "relationship_id": rid})
        coverage[rel.get("chapter_id") or "unknown"][rel_type] += 1

    report = {
        "status": "ok" if not errors else "failed",
        "concept_count": len(concepts),
        "unit_summary_count": len(summaries),
        "accepted_relationship_count": len(accepted),
        "review_relationship_count": len(review),
        "rejected_relationship_count": len(rejected),
        "relationship_count_by_type": dict(Counter(r.get("type") for r in accepted)),
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
