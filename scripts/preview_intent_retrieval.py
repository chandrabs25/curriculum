#!/usr/bin/env python
"""Print section-title clues retrieved before intent-classification LLM."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from curriculum_engine.api import default_service  # noqa: E402
from curriculum_engine.intent import build_intent_classification_packet  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Preview subject-filtered section matches before intent LLM classification."
    )
    parser.add_argument("query", help="Learner query, for example: gravity")
    parser.add_argument(
        "--subject",
        choices=["physics", "chemistry", "biology"],
        required=True,
        help="Subject filter applied to semantic retrieval.",
    )
    parser.add_argument("--grade", type=int, choices=[11, 12], help="Optional grade filter.")
    parser.add_argument("--chapter-id", help="Optional chapter ID filter.")
    parser.add_argument("--limit", type=int, default=12, help="Candidate limit before clue filtering.")
    parser.add_argument("--json", action="store_true", help="Print the full intent packet as JSON.")
    args = parser.parse_args()

    svc = default_service()
    packet = build_intent_classification_packet(
        svc.graph,
        svc.retriever,
        args.query,
        subject=args.subject,
        grade=args.grade,
        chapter_id=args.chapter_id,
        limit=args.limit,
    ).to_dict()

    if args.json:
        print(json.dumps(packet, indent=2, ensure_ascii=False))
        return 0

    print(f"Query: {args.query}")
    print(f"Subject filter: {args.subject}")
    if args.grade:
        print(f"Grade filter: {args.grade}")
    if args.chapter_id:
        print(f"Chapter filter: {args.chapter_id}")
    print("\nMatched section titles before intent LLM:\n")

    rows = packet.get("candidate_sections") or []
    if not rows:
        print("No candidate section clues matched.")
        return 0

    for index, row in enumerate(rows, 1):
        title = row.get("title") or "(untitled)"
        section_id = row.get("section_id") or ""
        subject = row.get("subject") or ""
        grade = row.get("grade") or ""
        reasons = ", ".join(row.get("reasons") or [])
        print(f"{index}. {title}")
        print(f"   {section_id} | {subject} {grade}")
        print(f"   reasons: {reasons}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
