#!/usr/bin/env python3
"""Prepare high-precision manual concept merge candidates."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from common import append_jsonl, ensure_repo_root, normalize_label, read_jsonl, similarity, stable_hash, write_json


TRIVIAL_TOKENS = {"a", "an", "the"}


def singularize_token(token: str) -> str:
    if len(token) > 3 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 3 and token.endswith("es") and not token.endswith(("ses", "xes")):
        return token[:-2]
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def merge_key(label: str) -> str:
    tokens = [
        singularize_token(token)
        for token in normalize_label(label).split("_")
        if token and token not in TRIVIAL_TOKENS
    ]
    return "_".join(tokens)


def public_concept(concept: dict[str, Any]) -> dict[str, Any]:
    return {
        "concept_id": concept.get("concept_id"),
        "canonical_label": concept.get("canonical_label"),
        "normalized_label": concept.get("normalized_label"),
        "definition": concept.get("definition", ""),
        "subjects": concept.get("subjects", []),
        "source_chapter_ids_count": len(concept.get("source_chapter_ids", [])),
        "source_unit_ids_count": len(concept.get("source_unit_ids", [])),
    }


def main() -> int:
    ensure_repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, default=Path("data/relationship_artifacts"))
    parser.add_argument("--min-label-similarity", type=float, default=0.92)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    concepts = read_jsonl(args.artifact_dir / "canonical_concepts.jsonl")
    output = args.artifact_dir / "review" / "manual_concept_merge_candidates.jsonl"
    summary = args.artifact_dir / "review" / "manual_concept_merge_candidates_summary.json"
    if output.exists() and not args.force:
        print(f"{output} exists; pass --force to regenerate")
        return 0
    output.unlink(missing_ok=True)

    buckets: dict[str, list[dict[str, Any]]] = {}
    for concept in concepts:
        key = merge_key(concept.get("canonical_label", ""))
        if key:
            buckets.setdefault(key, []).append(concept)

    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for key, rows in sorted(buckets.items()):
        if len(rows) < 2:
            continue
        rows = sorted(rows, key=lambda row: row.get("concept_id", ""))
        for idx, left in enumerate(rows):
            for right in rows[idx + 1:]:
                left_id = left.get("concept_id")
                right_id = right.get("concept_id")
                pair = tuple(sorted([left_id, right_id]))
                if pair in seen:
                    continue
                seen.add(pair)
                score = similarity(left.get("canonical_label", ""), right.get("canonical_label", ""))
                if score < args.min_label_similarity:
                    continue
                candidates.append(
                    {
                        "candidate_id": stable_hash(pair, "manual_concept_merge"),
                        "concept_a": public_concept(left),
                        "concept_b": public_concept(right),
                        "heuristic": "plural_or_trivial_wording",
                        "label_similarity": round(score, 4),
                        "suggested_decision": "merge",
                        "notes": "High-precision candidate; review definitions and sources before merging.",
                    }
                )

    append_jsonl(output, candidates)
    write_json(
        summary,
        {
            "concepts": len(concepts),
            "candidates": len(candidates),
            "min_label_similarity": args.min_label_similarity,
            "output": str(output),
        },
    )
    print(f"wrote {len(candidates)} candidates to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
