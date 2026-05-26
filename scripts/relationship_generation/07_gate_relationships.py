#!/usr/bin/env python3
"""Merge, validate, canonicalize, and confidence-gate split relationship artifacts."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Any

from common import (
    RELATIONSHIP_TYPES,
    all_source_ids_from_manifest,
    append_jsonl,
    concept_id_from_label,
    ensure_repo_root,
    read_jsonl,
    stable_hash,
    validate_confidence,
    write_json,
)


RAW_RELATIONSHIP_FILES = [
    "raw_unit_concept_relationships.jsonl",
    "raw_unit_dependency_relationships.jsonl",
    "raw_exercise_relationships.jsonl",
]


def load_raw_relationships(artifact_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for filename in RAW_RELATIONSHIP_FILES:
        path = artifact_dir / filename
        for row in read_jsonl(path):
            row.setdefault("source_file", filename)
            rows.append(row)
    return rows


def build_alias_map(concepts: list[dict[str, Any]], aliases: list[dict[str, Any]]) -> tuple[set[str], dict[str, str]]:
    canonical_ids = {c["concept_id"] for c in concepts if c.get("concept_id")}
    alias_to_canonical = {a["alias"]: a["canonical_concept_id"] for a in aliases if a.get("alias") and a.get("canonical_concept_id")}
    for concept in concepts:
        cid = concept.get("concept_id")
        if not cid:
            continue
        alias_to_canonical[concept.get("normalized_label", "")] = cid
        alias_to_canonical[str(concept.get("canonical_label", "")).lower()] = cid
        for alias in concept.get("aliases", []):
            alias_to_canonical[str(alias)] = cid
            alias_to_canonical[str(alias).replace(" ", "_").lower()] = cid
    return canonical_ids, alias_to_canonical


def canonicalize_concept_id(to_id: Any, canonical_ids: set[str], alias_to_canonical: dict[str, str]) -> str | None:
    if not to_id:
        return None
    text = str(to_id)
    if text in canonical_ids:
        return text
    no_prefix = text.replace("concept:", "")
    candidates = [
        no_prefix,
        no_prefix.lower(),
        no_prefix.replace(" ", "_").lower(),
        concept_id_from_label(no_prefix).replace("concept:", ""),
    ]
    for candidate in candidates:
        mapped = alias_to_canonical.get(candidate)
        if mapped in canonical_ids:
            return mapped
    return None


def main() -> int:
    ensure_repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, default=Path("data/relationship_artifacts"))
    parser.add_argument("--manifest", type=Path, default=Path("data/textbook_sources/manifest.json"))
    parser.add_argument("--accept-threshold", type=float, default=0.85)
    parser.add_argument("--review-threshold", type=float, default=0.65)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    accepted_path = args.artifact_dir / "accepted_relationships.jsonl"
    review_path = args.artifact_dir / "review" / "relationships.jsonl"
    rejected_path = args.artifact_dir / "rejected" / "relationships.jsonl"
    if accepted_path.exists() and not args.force:
        print(f"{accepted_path} exists; pass --force to regenerate")
        return 0
    for path in (accepted_path, review_path, rejected_path):
        path.unlink(missing_ok=True)

    raw = load_raw_relationships(args.artifact_dir)
    concepts = read_jsonl(args.artifact_dir / "canonical_concepts.jsonl")
    aliases = read_jsonl(args.artifact_dir / "concept_aliases.jsonl")
    canonical_ids, alias_to_canonical = build_alias_map(concepts, aliases)
    unit_ids, exercise_ids = all_source_ids_from_manifest(args.manifest)

    accepted: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any, Any]] = set()

    for row in raw:
        reasons: list[str] = []
        rel_type = row.get("type")
        from_id = row.get("from_id")
        to_id = row.get("to_id")
        confidence = validate_confidence(row.get("confidence"))

        if rel_type not in RELATIONSHIP_TYPES:
            reasons.append("invalid_relationship_type")

        if rel_type in {"DEPENDS_ON_UNIT", "REQUIRES_CONCEPT", "TEACHES_CONCEPT"} and from_id not in unit_ids:
            reasons.append("from_id_not_unit")
        if rel_type in {"TESTS_UNIT", "TESTS_CONCEPT"} and from_id not in exercise_ids:
            reasons.append("from_id_not_exercise")

        if rel_type in {"DEPENDS_ON_UNIT", "TESTS_UNIT"}:
            if to_id not in unit_ids:
                reasons.append("to_id_not_unit")
        if rel_type in {"REQUIRES_CONCEPT", "TEACHES_CONCEPT", "TESTS_CONCEPT"}:
            canonical_to = canonicalize_concept_id(to_id, canonical_ids, alias_to_canonical)
            if canonical_to:
                if canonical_to != to_id:
                    row["original_to_id"] = to_id
                    row["to_id"] = canonical_to
                    to_id = canonical_to
            else:
                reasons.append("to_id_not_canonical_concept")

        evidence = row.get("evidence") or {}
        if not evidence.get("text") or not evidence.get("reason"):
            reasons.append("missing_evidence")

        edge_key = (rel_type, from_id, to_id)
        if edge_key in seen:
            reasons.append("duplicate_edge")
        seen.add(edge_key)

        row["confidence"] = confidence
        row["gate_reasons"] = reasons
        row["relationship_id"] = stable_hash({"type": rel_type, "from": from_id, "to": to_id}, "rel")

        if reasons or confidence < args.review_threshold:
            rejected.append(row)
        elif confidence < args.accept_threshold:
            review.append(row)
        else:
            accepted.append(row)

    append_jsonl(accepted_path, accepted)
    append_jsonl(review_path, review)
    append_jsonl(rejected_path, rejected)
    summary = {
        "raw": len(raw),
        "raw_by_file": dict(Counter(row.get("source_file") for row in raw)),
        "accepted": len(accepted),
        "review": len(review),
        "rejected": len(rejected),
        "accepted_by_type": dict(Counter(r["type"] for r in accepted)),
        "review_by_type": dict(Counter(r["type"] for r in review)),
        "rejected_by_type": dict(Counter(r.get("type") for r in rejected)),
        "rejected_reasons": dict(Counter(reason for r in rejected for reason in r.get("gate_reasons", []))),
        "accept_threshold": args.accept_threshold,
        "review_threshold": args.review_threshold,
    }
    write_json(args.artifact_dir / "relationship_summary.json", summary)
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
