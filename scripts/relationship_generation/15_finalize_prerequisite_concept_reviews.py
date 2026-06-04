#!/usr/bin/env python3
"""Finalize Kimi prerequisite concept judgments into explicit reviewed decisions."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common import append_jsonl, ensure_repo_root, read_jsonl, write_json


DEFAULT_INPUT = Path("data/relationship_artifacts/review/prerequisite_concept_llm_decisions.jsonl")
DEFAULT_OUTPUT = Path("data/relationship_artifacts/review/finalized_prerequisite_concept_decisions.jsonl")

DISTINCT_OVERRIDES: dict[frozenset[str], tuple[str, str]] = {
    frozenset({"concept:electric_potential_difference", "concept:electrostatic_potential_difference"}): (
        "broader_narrower",
        "Electric potential difference is broader than electrostatic potential difference; preserve the scope distinction.",
    ),
    frozenset({"concept:work_done_in_an_electric_field", "concept:work_done_in_an_electrostatic_field"}): (
        "broader_narrower",
        "Work in an electric field is broader than work in the electrostatic special case; preserve the scope distinction.",
    ),
    frozenset({"concept:macromolecules", "concept:micromolecules"}): (
        "related_distinct",
        "Macromolecules and micromolecules are complementary but distinct biomolecule categories.",
    ),
}


def evidence_counts(relationships: list[dict[str, Any]], raw_concepts: list[dict[str, Any]]) -> tuple[Counter[str], Counter[str]]:
    teaches = Counter(
        str(row.get("to_id"))
        for row in relationships
        if row.get("type") == "TEACHES_CONCEPT" and row.get("to_id")
    )
    raw = Counter(
        str(row.get("candidate_concept_id"))
        for row in raw_concepts
        if row.get("candidate_concept_id")
    )
    return teaches, raw


def singular_preference(concept_id: str) -> int:
    tail = concept_id.replace("concept:", "").rsplit("_", 1)[-1]
    return 0 if tail.endswith("s") and not tail.endswith("ss") else 1


def choose_canonical_id(concept_ids: list[str], teaches: Counter[str], raw: Counter[str]) -> str:
    return max(
        concept_ids,
        key=lambda concept_id: (
            teaches[concept_id],
            raw[concept_id],
            singular_preference(concept_id),
            -len(concept_id),
            concept_id,
        ),
    )


def finalize_decisions(
    decisions: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    raw_concepts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    teaches, raw = evidence_counts(relationships, raw_concepts)
    finalized_at = datetime.now(timezone.utc).isoformat()
    rows = []
    seen_pairs: set[frozenset[str]] = set()
    for decision in decisions:
        concept_ids = [str(value) for value in decision.get("concept_ids", []) if value]
        pair = frozenset(concept_ids)
        if len(pair) != 2:
            raise ValueError(f"{decision.get('candidate_id')}: expected exactly two distinct concept IDs")
        if pair in seen_pairs:
            raise ValueError(f"duplicate reviewed concept pair: {sorted(pair)}")
        seen_pairs.add(pair)

        final_decision = str(decision.get("decision") or "")
        relationship = str(decision.get("relationship") or "")
        reason = str(decision.get("reason") or "")
        if pair in DISTINCT_OVERRIDES:
            final_decision = "keep_distinct"
            relationship, reason = DISTINCT_OVERRIDES[pair]
        if final_decision == "merge":
            relationship = "same_concept"
            canonical_id = choose_canonical_id(concept_ids, teaches, raw)
        elif final_decision == "keep_distinct":
            canonical_id = ""
            if relationship == "same_concept":
                raise ValueError(f"{decision.get('candidate_id')}: keep_distinct cannot be same_concept")
        else:
            raise ValueError(f"{decision.get('candidate_id')}: unresolved decision {final_decision!r}")

        rows.append(
            {
                "candidate_id": decision.get("candidate_id"),
                "concept_ids": concept_ids,
                "final_decision": final_decision,
                "review_status": "approved",
                "canonical_concept_id": canonical_id,
                "relationship": relationship,
                "reason": reason,
                "source_judgment": {
                    "decision": decision.get("decision"),
                    "relationship": decision.get("relationship"),
                    "canonical_concept_id": decision.get("canonical_concept_id"),
                    "reason": decision.get("reason"),
                    "confidence": decision.get("confidence"),
                    "judge": decision.get("judge"),
                    "review_packet_hash": decision.get("review_packet_hash"),
                },
                "canonical_selection_evidence": {
                    concept_id: {
                        "teaches_relationship_count": teaches[concept_id],
                        "raw_concept_count": raw[concept_id],
                        "singular_preference": singular_preference(concept_id),
                    }
                    for concept_id in concept_ids
                },
                "finalized_at": finalized_at,
            }
        )
    return rows


def main() -> int:
    ensure_repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--artifact-dir", type=Path, default=Path("data/relationship_artifacts"))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--expect-merge-count", type=int)
    parser.add_argument("--expect-distinct-count", type=int)
    args = parser.parse_args()

    if args.output.exists() and not args.force:
        raise SystemExit(f"{args.output} exists; pass --force to regenerate")
    rows = finalize_decisions(
        read_jsonl(args.input),
        read_jsonl(args.artifact_dir / "accepted_relationships.jsonl"),
        read_jsonl(args.artifact_dir / "raw_concepts.jsonl"),
    )
    counts = Counter(row["final_decision"] for row in rows)
    if args.expect_merge_count is not None and counts["merge"] != args.expect_merge_count:
        raise SystemExit(f"expected {args.expect_merge_count} merges, found {counts['merge']}")
    if args.expect_distinct_count is not None and counts["keep_distinct"] != args.expect_distinct_count:
        raise SystemExit(f"expected {args.expect_distinct_count} distinct decisions, found {counts['keep_distinct']}")
    args.output.unlink(missing_ok=True)
    append_jsonl(args.output, rows)
    write_json(
        args.output.with_name(f"{args.output.stem}_summary.json"),
        {"decision_counts": dict(counts), "total": len(rows), "output": str(args.output)},
    )
    print({"decision_counts": dict(counts), "total": len(rows)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
