#!/usr/bin/env python3
"""Use Kimi on Fireworks to adjudicate prerequisite concept review candidates."""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any

from common import append_jsonl, ensure_repo_root, read_jsonl, stable_hash, write_json

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from curriculum_engine.llm_clients import FIREWORKS_KIMI_K2P5, FireworksLLMClient  # noqa: E402


API_KEY_ENV = "FIREWORKS_CONCEPT_REVIEW_API_KEY"
DEFAULT_INPUT = Path("data/relationship_artifacts/review/prerequisite_concept_candidates.jsonl")
DEFAULT_OUTPUT = Path("data/relationship_artifacts/review/prerequisite_concept_llm_decisions.jsonl")
DEFAULT_ERRORS = Path("data/relationship_artifacts/errors/prerequisite_concept_llm_errors.jsonl")

DECISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "decision": {
            "type": "string",
            "enum": ["merge", "keep_distinct", "needs_evidence"],
        },
        "canonical_concept_id": {"type": "string"},
        "reason": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "relationship": {
            "type": "string",
            "enum": ["same_concept", "broader_narrower", "related_distinct", "unclear"],
        },
    },
    "required": ["decision", "canonical_concept_id", "reason", "confidence", "relationship"],
}


def evidence_index(relationships: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    index: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in relationships:
        rel_type = str(row.get("type") or "")
        concept_id = str(row.get("to_id") or "")
        if rel_type not in {"REQUIRES_CONCEPT", "TEACHES_CONCEPT"} or not concept_id:
            continue
        evidence = row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
        index[(rel_type, concept_id)].append(
            {
                "section_id": row.get("from_id"),
                "chapter_id": row.get("chapter_id"),
                "confidence": row.get("confidence"),
                "evidence_text": evidence.get("text") or "",
                "pedagogical_reason": row.get("pedagogical_reason") or "",
                "teaching_evidence": row.get("teaching_evidence") or "",
            }
        )
    return index


def review_packet(candidate: dict[str, Any], evidence: dict[tuple[str, str], list[dict[str, Any]]]) -> dict[str, Any]:
    required = candidate.get("required_concept") or {}
    taught = candidate.get("candidate_taught_concept") or {}
    required_id = str(required.get("concept_id") or "")
    taught_id = str(taught.get("concept_id") or "")
    return {
        "candidate_id": candidate.get("candidate_id"),
        "required_concept": required,
        "candidate_taught_concept": taught,
        "matching_heuristic": taught.get("heuristic"),
        "heuristic_similarity": taught.get("similarity"),
        "required_usage_evidence": evidence.get(("REQUIRES_CONCEPT", required_id), [])[:8],
        "teaching_evidence": evidence.get(("TEACHES_CONCEPT", taught_id), [])[:8],
    }


def build_prompt(packet: dict[str, Any]) -> str:
    return f"""You are reviewing canonical concepts for a textbook-grounded curriculum knowledge graph.

Decide whether the required concept and candidate taught concept mean exactly the same teachable concept.

Decision policy:
- merge: They are interchangeable in every provided context. Differences are only spelling, plurality, acronym ordering, or true synonymous terminology.
- keep_distinct: They are related, broader/narrower, an application/specialization, or require meaningfully different learner knowledge.
- needs_evidence: The supplied definitions and source evidence are insufficient or contradictory.
- Never merge merely because labels are similar.
- Prefer keep_distinct when one concept is broader or narrower.
- canonical_concept_id must be one of the two supplied concept IDs only when decision is merge; otherwise return an empty string.
- Give a concise pedagogical reason grounded in the supplied evidence.

REVIEW PACKET:
{json.dumps(packet, ensure_ascii=False, indent=2)}

FINAL TASK:
Return the decision, canonical_concept_id, reason, confidence, and relationship using the required JSON schema."""


def validate_decision(candidate: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    decision = str(payload.get("decision") or "")
    if decision not in {"merge", "keep_distinct", "needs_evidence"}:
        raise ValueError(f"invalid decision: {decision}")
    required_id = str((candidate.get("required_concept") or {}).get("concept_id") or "")
    taught_id = str((candidate.get("candidate_taught_concept") or {}).get("concept_id") or "")
    canonical_id = str(payload.get("canonical_concept_id") or "")
    relationship = str(payload.get("relationship") or "")
    if decision == "merge" and canonical_id not in {required_id, taught_id}:
        raise ValueError("merge decision must choose one supplied canonical concept ID")
    if decision == "merge" and relationship != "same_concept":
        raise ValueError("merge decision must use relationship= same_concept")
    if decision == "keep_distinct" and relationship == "same_concept":
        raise ValueError("keep_distinct decision cannot use relationship=same_concept")
    if decision != "merge":
        canonical_id = ""
    try:
        confidence = max(0.0, min(1.0, float(payload.get("confidence"))))
    except (TypeError, ValueError) as exc:
        raise ValueError("confidence must be numeric") from exc
    return {
        "candidate_id": candidate.get("candidate_id"),
        "concept_ids": [required_id, taught_id],
        "decision": decision,
        "canonical_concept_id": canonical_id,
        "relationship": relationship,
        "reason": str(payload.get("reason") or "").strip(),
        "confidence": round(confidence, 4),
        "judge": {
            "provider": "fireworks",
            "model": FIREWORKS_KIMI_K2P5,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        },
    }


def main() -> int:
    ensure_repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--errors", type=Path, default=DEFAULT_ERRORS)
    parser.add_argument("--relationships", type=Path, default=Path("data/relationship_artifacts/accepted_relationships.jsonl"))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Print one enriched prompt without calling Fireworks.")
    parser.add_argument("--max-tokens", type=int, default=900)
    args = parser.parse_args()

    api_key = os.getenv(API_KEY_ENV)
    if not args.dry_run and not api_key:
        raise SystemExit(
            f"{API_KEY_ENV} is not set. Export the separate review key before running this script."
        )

    candidates = read_jsonl(args.input)
    if not candidates:
        raise SystemExit(f"No candidates found in {args.input}")
    evidence = evidence_index(read_jsonl(args.relationships))
    if args.dry_run:
        print(build_prompt(review_packet(candidates[0], evidence)))
        return 0

    if args.force:
        args.output.unlink(missing_ok=True)
        args.errors.unlink(missing_ok=True)
    completed = {row.get("candidate_id") for row in read_jsonl(args.output)}
    pending = [row for row in candidates if row.get("candidate_id") not in completed]
    if args.limit is not None:
        pending = pending[: max(0, args.limit)]
    print(f"selected {len(candidates)} candidates, {len(pending)} pending")

    client = FireworksLLMClient(
        api_key=api_key,
        model=FIREWORKS_KIMI_K2P5,
        temperature=0.0,
        max_tokens=args.max_tokens,
    )
    counts: dict[str, int] = defaultdict(int)
    for candidate in pending:
        candidate_id = str(candidate.get("candidate_id") or "")
        packet = review_packet(candidate, evidence)
        try:
            payload = client.generate_json(build_prompt(packet), DECISION_SCHEMA)
            decision = validate_decision(candidate, payload)
            decision["review_packet_hash"] = stable_hash(packet, "review_packet")
            append_jsonl(args.output, [decision])
            counts[decision["decision"]] += 1
            print(f"{candidate_id}: {decision['decision']} ({decision['confidence']:.2f})")
        except Exception as exc:
            append_jsonl(
                args.errors,
                [
                    {
                        "candidate_id": candidate_id,
                        "error": str(exc),
                        "occurred_at": datetime.now(timezone.utc).isoformat(),
                    }
                ],
            )
            counts["errors"] += 1
            print(f"{candidate_id}: ERROR {exc}", file=sys.stderr)

    summary_path = args.output.with_name(f"{args.output.stem}_summary.json")
    write_json(
        summary_path,
        {
            "input_candidate_count": len(candidates),
            "completed_candidate_count": len(read_jsonl(args.output)),
            "pending_candidate_count": len(candidates) - len(read_jsonl(args.output)),
            "run_counts": dict(counts),
            "model": FIREWORKS_KIMI_K2P5,
            "api_key_env": API_KEY_ENV,
        },
    )
    print(dict(counts))
    return 1 if counts.get("errors") else 0


if __name__ == "__main__":
    raise SystemExit(main())
