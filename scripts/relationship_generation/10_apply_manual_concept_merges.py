#!/usr/bin/env python3
"""Safely replay explicitly finalized concept merge decisions."""

from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common import ensure_repo_root, normalize_label, read_jsonl, stable_hash, write_json


DEFAULT_DECISIONS = Path("data/relationship_artifacts/review/finalized_prerequisite_concept_decisions.jsonl")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def approved_merges(decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merges = []
    for decision in decisions:
        if decision.get("review_status") != "approved" or decision.get("final_decision") != "merge":
            continue
        concept_ids = [str(value) for value in decision.get("concept_ids", []) if value]
        canonical_id = str(decision.get("canonical_concept_id") or "")
        if len(set(concept_ids)) != 2:
            raise ValueError(f"{decision.get('candidate_id')}: merge requires exactly two distinct concept IDs")
        if canonical_id not in concept_ids:
            raise ValueError(f"{decision.get('candidate_id')}: canonical concept must be one of concept_ids")
        if decision.get("relationship") != "same_concept":
            raise ValueError(f"{decision.get('candidate_id')}: approved merge must use relationship= same_concept")
        merges.append(decision)
    return merges


def build_merge_map(merges: list[dict[str, Any]]) -> dict[str, str]:
    merge_map: dict[str, str] = {}
    for decision in merges:
        canonical_id = str(decision["canonical_concept_id"])
        for concept_id in decision["concept_ids"]:
            existing = merge_map.get(str(concept_id))
            if existing and existing != canonical_id:
                raise ValueError(f"conflicting canonical selections for {concept_id}: {existing} and {canonical_id}")
            merge_map[str(concept_id)] = canonical_id
    for concept_id, canonical_id in merge_map.items():
        if canonical_id in merge_map and merge_map[canonical_id] != canonical_id:
            raise ValueError(f"canonical concept {canonical_id} is also mapped to {merge_map[canonical_id]}")
    return merge_map


def merge_concept_rows(canonical: dict[str, Any], removed: list[dict[str, Any]], reasons: list[str]) -> dict[str, Any]:
    concepts = [canonical, *removed]
    canonical_label = str(canonical.get("canonical_label") or "")
    canonical_normalized = str(canonical.get("normalized_label") or normalize_label(canonical_label))
    aliases = {
        str(alias)
        for concept in concepts
        for alias in concept.get("aliases", [])
        if alias
    }
    aliases.update(
        str(concept.get("canonical_label"))
        for concept in removed
        if concept.get("canonical_label")
    )
    aliases.discard(canonical_label)
    definitions = [str(concept["definition"]) for concept in concepts if concept.get("definition")]
    row = {
        **canonical,
        "concept_id": canonical["concept_id"],
        "canonical_label": canonical_label,
        "normalized_label": canonical_normalized,
        "definition": max(definitions, key=len) if definitions else "",
        "aliases": sorted(aliases, key=str.lower),
        "subjects": sorted({value for concept in concepts for value in concept.get("subjects", [])}),
        "source_chapter_ids": sorted({value for concept in concepts for value in concept.get("source_chapter_ids", [])}),
        "source_unit_ids": sorted({value for concept in concepts for value in concept.get("source_unit_ids", [])}),
        "source_raw_concept_ids": sorted(
            {value for concept in concepts for value in concept.get("source_raw_concept_ids", [])}
        ),
        "confidence": round(max(float(concept.get("confidence", 0.0)) for concept in concepts), 4),
        "manual_merge": {
            "merged_from": sorted(str(concept["concept_id"]) for concept in removed),
            "reason": "; ".join(reason for reason in reasons if reason),
            "applied_at": datetime.now(timezone.utc).isoformat(),
        },
    }
    return row


def remap_aliases(
    existing_aliases: list[dict[str, Any]],
    by_id: dict[str, dict[str, Any]],
    merge_map: dict[str, str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for alias in existing_aliases:
        target = str(alias.get("canonical_concept_id") or "")
        rows.append({**alias, "canonical_concept_id": merge_map.get(target, target)})
    for old_id, canonical_id in merge_map.items():
        if old_id == canonical_id or old_id not in by_id:
            continue
        old = by_id[old_id]
        for alias_value, alias_label in (
            (old.get("normalized_label"), old.get("canonical_label")),
            (old_id.replace("concept:", ""), old.get("canonical_label")),
        ):
            if alias_value:
                rows.append(
                    {
                        "alias": str(alias_value),
                        "alias_label": str(alias_label or ""),
                        "canonical_concept_id": canonical_id,
                        "reason": "approved_concept_merge",
                        "confidence": 1.0,
                    }
                )

    aliases_by_key: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = normalize_label(str(row.get("alias") or row.get("alias_label") or ""))
        if not key:
            continue
        existing = aliases_by_key.get(key)
        if existing and existing.get("canonical_concept_id") != row.get("canonical_concept_id"):
            raise ValueError(
                f"alias collision for {key}: {existing.get('canonical_concept_id')} and {row.get('canonical_concept_id')}"
            )
        aliases_by_key[key] = row
    return [aliases_by_key[key] for key in sorted(aliases_by_key)]


def build_outputs(
    concepts: list[dict[str, Any]],
    aliases: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    merges = approved_merges(decisions)
    merge_map = build_merge_map(merges)
    by_id = {str(concept["concept_id"]): concept for concept in concepts if concept.get("concept_id")}
    reasons_by_canonical: dict[str, list[str]] = {}
    for decision in merges:
        reasons_by_canonical.setdefault(str(decision["canonical_concept_id"]), []).append(str(decision.get("reason") or ""))

    grouped_removed: dict[str, list[dict[str, Any]]] = {}
    already_applied = 0
    for old_id, canonical_id in merge_map.items():
        if old_id == canonical_id:
            continue
        if old_id not in by_id:
            if canonical_id in by_id:
                already_applied += 1
                continue
            raise ValueError(f"neither removed concept {old_id} nor canonical concept {canonical_id} exists")
        if canonical_id not in by_id:
            raise ValueError(f"selected canonical concept does not exist: {canonical_id}")
        grouped_removed.setdefault(canonical_id, []).append(by_id[old_id])

    consumed = {str(concept["concept_id"]) for rows in grouped_removed.values() for concept in rows}
    output_concepts = [concept for concept in concepts if str(concept.get("concept_id")) not in consumed]
    output_by_id = {str(concept["concept_id"]): concept for concept in output_concepts}
    log_rows = []
    for canonical_id, removed in grouped_removed.items():
        merged = merge_concept_rows(output_by_id[canonical_id], removed, reasons_by_canonical.get(canonical_id, []))
        output_by_id[canonical_id] = merged
        log_rows.append(
            {
                "merge_id": stable_hash([canonical_id, sorted(str(row["concept_id"]) for row in removed)], "manual_concept_merge"),
                "decision": "merge",
                "merged_from": sorted(str(row["concept_id"]) for row in removed),
                "merged_to": canonical_id,
                "reason": merged["manual_merge"]["reason"],
            }
        )
    output_concepts = sorted(output_by_id.values(), key=lambda row: str(row.get("concept_id") or ""))
    output_aliases = remap_aliases(aliases, by_id, merge_map)
    summary = {
        "before": len(concepts),
        "after": len(output_concepts),
        "removed": len(concepts) - len(output_concepts),
        "approved_merge_decisions": len(merges),
        "applied_merge_groups": len(grouped_removed),
        "already_applied_members": already_applied,
        "aliases_before": len(aliases),
        "aliases_after": len(output_aliases),
    }
    return output_concepts, output_aliases, log_rows, summary


def main() -> int:
    ensure_repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, default=Path("data/relationship_artifacts"))
    parser.add_argument("--decisions", type=Path, default=DEFAULT_DECISIONS)
    parser.add_argument("--apply", action="store_true", help="Write the reviewed merge results. Without this flag, only report a dry run.")
    args = parser.parse_args()

    concept_path = args.artifact_dir / "canonical_concepts.jsonl"
    alias_path = args.artifact_dir / "concept_aliases.jsonl"
    concepts, aliases, decisions = read_jsonl(concept_path), read_jsonl(alias_path), read_jsonl(args.decisions)
    output_concepts, output_aliases, log_rows, summary = build_outputs(concepts, aliases, decisions)
    summary["mode"] = "apply" if args.apply else "dry_run"
    print(summary)
    if not args.apply:
        return 0
    if summary["removed"] == 0:
        print("reviewed merges are already applied; no files changed")
        return 0

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    concept_backup = concept_path.with_name(f"{concept_path.stem}_before_reviewed_merge_{timestamp}.jsonl")
    alias_backup = alias_path.with_name(f"{alias_path.stem}_before_reviewed_merge_{timestamp}.jsonl")
    shutil.copy2(concept_path, concept_backup)
    shutil.copy2(alias_path, alias_backup)
    write_jsonl(concept_path, output_concepts)
    write_jsonl(alias_path, output_aliases)
    write_jsonl(args.artifact_dir / "manual_concept_merge_log.jsonl", log_rows)
    write_json(
        args.artifact_dir / "manual_concept_merge_summary.json",
        {**summary, "concept_backup": str(concept_backup), "alias_backup": str(alias_backup)},
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
