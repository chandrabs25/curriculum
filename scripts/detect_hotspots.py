"""Detect population-level misunderstanding hotspot candidates from checkpoint evidence."""

from __future__ import annotations

import argparse

from curriculum_engine.database import repository_from_env
from curriculum_engine.hotspots import HotspotThresholds, detect_hotspot_candidates
from curriculum_engine.llm_clients import FireworksLLMClient


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-llm", action="store_true", help="Use deterministic wording instead of LLM summaries.")
    parser.add_argument("--min-attempts", type=int, default=8)
    parser.add_argument("--min-unique-learners", type=int, default=4)
    parser.add_argument("--min-distinct-questions", type=int, default=2)
    parser.add_argument("--min-rate", type=float, default=0.35)
    args = parser.parse_args()

    repository = repository_from_env()
    if repository is None:
        raise SystemExit("DATABASE_URL or SUPABASE_DB_URL is required")

    thresholds = HotspotThresholds(
        min_attempts=args.min_attempts,
        min_unique_learners=args.min_unique_learners,
        min_distinct_questions=args.min_distinct_questions,
        min_misconception_rate=args.min_rate,
    )
    candidates = detect_hotspot_candidates(
        repository.checkpoint_hotspot_evidence(),
        active_hotspots=repository.active_hotspots(),
        thresholds=thresholds,
        llm_client=None if args.no_llm else FireworksLLMClient(),
    )
    repository.save_hotspots(candidates)
    print(f"saved hotspot candidates: {len(candidates)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
