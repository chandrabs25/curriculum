#!/usr/bin/env python3
"""Normalize and deduplicate raw concept candidates into global concepts."""

from __future__ import annotations

import argparse
from collections import defaultdict
from typing import Any

from common import (
    DEFAULT_MODEL,
    GeminiClient,
    append_jsonl,
    concept_id_from_label,
    ensure_repo_root,
    normalize_label,
    read_jsonl,
    similarity,
    stable_hash,
    validate_confidence,
    write_json,
)


ADJUDICATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "decision": {"type": "string", "enum": ["same_concept", "broader_narrower", "related_distinct", "unrelated"]},
        "canonical_label": {"type": "string"},
        "broader_label": {"type": "string"},
        "narrower_label": {"type": "string"},
        "reason": {"type": "string"},
        "confidence": {"type": "number"},
    },
    "required": ["decision", "reason", "confidence"],
}


def build_prompt(a: dict[str, Any], b: dict[str, Any]) -> str:
    return f"""Decide whether these two textbook concepts should be merged in a curriculum knowledge graph.

Merge only if they mean the same concept. If one is broader than the other, do not merge.

Concept A:
label: {a['canonical_label']}
definition: {a['definition']}
aliases: {a['aliases']}

Concept B:
label: {b['canonical_label']}
definition: {b['definition']}
aliases: {b['aliases']}

Return JSON with decision, reason, confidence, and canonical_label if decision is same_concept."""


def concept_from_group(normalized_label: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    labels = [r["label"] for r in rows]
    canonical_label = sorted(labels, key=lambda s: (len(s), s.lower()))[0]
    definitions = [r.get("definition", "") for r in rows if r.get("definition")]
    subjects = sorted({r.get("subject") for r in rows if r.get("subject")})
    source_chapter_ids = sorted({r.get("chapter_id") for r in rows if r.get("chapter_id")})
    source_unit_ids = sorted({uid for r in rows for uid in r.get("source_unit_ids", [])})
    aliases = sorted({label for label in labels if normalize_label(label) != normalize_label(canonical_label)})
    concept = {
        "concept_id": f"concept:{normalized_label}",
        "canonical_label": canonical_label,
        "normalized_label": normalized_label,
        "definition": definitions[0] if definitions else "",
        "aliases": aliases,
        "subjects": subjects,
        "source_chapter_ids": source_chapter_ids,
        "source_unit_ids": source_unit_ids,
        "source_raw_concept_ids": sorted({r["raw_concept_id"] for r in rows}),
        "confidence": round(sum(float(r.get("confidence", 0.0)) for r in rows) / max(1, len(rows)), 4),
    }
    return concept


def merge_concepts(a: dict[str, Any], b: dict[str, Any], canonical_label: str | None = None) -> dict[str, Any]:
    label = canonical_label or a["canonical_label"]
    normalized = normalize_label(label)
    aliases = sorted(set(a.get("aliases", [])) | set(b.get("aliases", [])) | {a["canonical_label"], b["canonical_label"]} - {label})
    return {
        "concept_id": f"concept:{normalized}",
        "canonical_label": label,
        "normalized_label": normalized,
        "definition": a.get("definition") or b.get("definition") or "",
        "aliases": aliases,
        "subjects": sorted(set(a.get("subjects", [])) | set(b.get("subjects", []))),
        "source_chapter_ids": sorted(set(a.get("source_chapter_ids", [])) | set(b.get("source_chapter_ids", []))),
        "source_unit_ids": sorted(set(a.get("source_unit_ids", [])) | set(b.get("source_unit_ids", []))),
        "source_raw_concept_ids": sorted(set(a.get("source_raw_concept_ids", [])) | set(b.get("source_raw_concept_ids", []))),
        "confidence": round(max(float(a.get("confidence", 0.0)), float(b.get("confidence", 0.0))), 4),
    }


def main() -> int:
    ensure_repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", default="data/relationship_artifacts")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--use-gemini-adjudication", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    from pathlib import Path

    artifact_dir = Path(args.artifact_dir)
    raw_path = artifact_dir / "raw_concepts.jsonl"
    out_path = artifact_dir / "canonical_concepts.jsonl"
    alias_path = artifact_dir / "concept_aliases.jsonl"
    review_path = artifact_dir / "review" / "concept_merges.jsonl"
    summary_path = artifact_dir / "concept_summary.json"

    if out_path.exists() and not args.force:
        print(f"{out_path} exists; pass --force to regenerate")
        return 0

    raw_rows = read_jsonl(raw_path)
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in raw_rows:
        groups[normalize_label(row.get("label", ""))].append(row)

    concepts = [concept_from_group(label, rows) for label, rows in sorted(groups.items())]
    review_rows: list[dict[str, Any]] = []
    alias_rows: list[dict[str, Any]] = []

    # Close duplicates are blocked by first token to avoid all-pairs explosion.
    by_block: dict[str, list[int]] = defaultdict(list)
    for idx, concept in enumerate(concepts):
        block = concept["normalized_label"].split("_", 1)[0]
        by_block[block].append(idx)

    client = GeminiClient(args.model) if args.use_gemini_adjudication else None
    removed: set[int] = set()
    for block_ids in by_block.values():
        for pos, i in enumerate(block_ids):
            if i in removed:
                continue
            for j in block_ids[pos + 1:]:
                if j in removed:
                    continue
                score = similarity(concepts[i]["canonical_label"], concepts[j]["canonical_label"])
                if score < 0.82:
                    continue
                decision = {
                    "decision": "review",
                    "reason": "High string similarity; semantic merge not auto-applied without Gemini adjudication.",
                    "confidence": score,
                }
                if client:
                    try:
                        decision = client.generate_json(build_prompt(concepts[i], concepts[j]), ADJUDICATION_SCHEMA)
                    except Exception as exc:
                        decision = {"decision": "review", "reason": f"Gemini adjudication failed: {exc}", "confidence": score}
                if decision.get("decision") == "same_concept" and validate_confidence(decision.get("confidence")) >= 0.9:
                    concepts[i] = merge_concepts(concepts[i], concepts[j], decision.get("canonical_label") or concepts[i]["canonical_label"])
                    removed.add(j)
                    alias_rows.append(
                        {
                            "alias": concepts[j]["normalized_label"],
                            "canonical_concept_id": concepts[i]["concept_id"],
                            "reason": decision.get("reason"),
                            "confidence": validate_confidence(decision.get("confidence")),
                        }
                    )
                else:
                    review_rows.append(
                        {
                            "candidate_id": stable_hash([concepts[i]["concept_id"], concepts[j]["concept_id"]], "concept_merge"),
                            "concept_a": concepts[i],
                            "concept_b": concepts[j],
                            "string_similarity": round(score, 4),
                            "decision": decision,
                        }
                    )

    final_concepts = [c for idx, c in enumerate(concepts) if idx not in removed]
    out_path.unlink(missing_ok=True)
    alias_path.unlink(missing_ok=True)
    review_path.unlink(missing_ok=True)
    append_jsonl(out_path, final_concepts)
    append_jsonl(alias_path, alias_rows)
    append_jsonl(review_path, review_rows)
    write_json(
        summary_path,
        {
            "raw_concepts": len(raw_rows),
            "canonical_concepts": len(final_concepts),
            "aliases": len(alias_rows),
            "review_merges": len(review_rows),
        },
    )
    print(f"wrote {len(final_concepts)} canonical concepts to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
