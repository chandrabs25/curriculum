#!/usr/bin/env python3
"""Apply explicit manual concept merge decisions to canonical concepts."""

from __future__ import annotations

import argparse
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common import append_jsonl, ensure_repo_root, normalize_label, read_jsonl, stable_hash, write_json


def choose_label(concepts: list[dict[str, Any]]) -> str:
    labels = [str(c.get("canonical_label") or "").strip() for c in concepts if c.get("canonical_label")]
    with_definition = [c for c in concepts if c.get("definition")]
    if with_definition:
        labels = [str(c.get("canonical_label") or "").strip() for c in with_definition if c.get("canonical_label")]
    return sorted(labels, key=lambda label: (len(normalize_label(label)), label.lower()))[0]


def merge_group(concepts: list[dict[str, Any]], reason: str) -> dict[str, Any]:
    label = choose_label(concepts)
    normalized = normalize_label(label)
    aliases = set()
    definitions = []
    for concept in concepts:
        current_label = concept.get("canonical_label")
        if current_label and normalize_label(current_label) != normalized:
            aliases.add(current_label)
        aliases.update(str(alias) for alias in concept.get("aliases", []) if alias)
        if concept.get("definition"):
            definitions.append(str(concept["definition"]))
    row = {
        "concept_id": f"concept:{normalized}",
        "canonical_label": label,
        "normalized_label": normalized,
        "definition": sorted(definitions, key=len, reverse=True)[0] if definitions else "",
        "aliases": sorted(aliases, key=str.lower),
        "subjects": sorted({subject for c in concepts for subject in c.get("subjects", [])}),
        "source_chapter_ids": sorted({cid for c in concepts for cid in c.get("source_chapter_ids", [])}),
        "source_unit_ids": sorted({uid for c in concepts for uid in c.get("source_unit_ids", [])}),
        "source_raw_concept_ids": sorted({rid for c in concepts for rid in c.get("source_raw_concept_ids", [])}),
        "confidence": round(max(float(c.get("confidence", 0.0)) for c in concepts), 4),
        "manual_merge": {
            "merged_from": sorted(c.get("concept_id") for c in concepts if c.get("concept_id")),
            "reason": reason,
            "applied_at": datetime.now(timezone.utc).isoformat(),
        },
    }
    return row


def find(parent: dict[str, str], item: str) -> str:
    parent.setdefault(item, item)
    if parent[item] != item:
        parent[item] = find(parent, parent[item])
    return parent[item]


def union(parent: dict[str, str], left: str, right: str) -> None:
    root_left = find(parent, left)
    root_right = find(parent, right)
    if root_left != root_right:
        parent[root_right] = root_left


def main() -> int:
    ensure_repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, default=Path("data/relationship_artifacts"))
    parser.add_argument(
        "--decisions",
        type=Path,
        default=Path("data/relationship_artifacts/review/manual_concept_merge_decisions.jsonl"),
    )
    args = parser.parse_args()

    concept_path = args.artifact_dir / "canonical_concepts.jsonl"
    alias_path = args.artifact_dir / "concept_aliases.jsonl"
    log_path = args.artifact_dir / "manual_concept_merge_log.jsonl"
    summary_path = args.artifact_dir / "manual_concept_merge_summary.json"
    concepts = read_jsonl(concept_path)
    decisions = read_jsonl(args.decisions)
    by_id = {concept["concept_id"]: concept for concept in concepts if concept.get("concept_id")}

    parent: dict[str, str] = {}
    accepted_decisions = []
    for decision in decisions:
        if decision.get("decision") != "merge":
            continue
        concept_ids = [cid for cid in decision.get("concept_ids", []) if cid in by_id]
        if len(concept_ids) < 2:
            continue
        first = concept_ids[0]
        for cid in concept_ids[1:]:
            union(parent, first, cid)
        accepted_decisions.append(decision)

    groups: dict[str, list[str]] = {}
    for cid in parent:
        groups.setdefault(find(parent, cid), []).append(cid)

    if not groups:
        print("no valid merge decisions found")
        return 0

    backup_path = concept_path.with_name(f"{concept_path.stem}_before_manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl")
    shutil.copy2(concept_path, backup_path)

    consumed = {cid for group in groups.values() for cid in group}
    merged_by_old_id: dict[str, str] = {}
    merged_rows: list[dict[str, Any]] = []
    log_rows: list[dict[str, Any]] = []
    for group_ids in groups.values():
        group_concepts = [by_id[cid] for cid in sorted(group_ids)]
        reasons = [
            str(decision.get("reason") or "manual merge")
            for decision in accepted_decisions
            if set(decision.get("concept_ids", [])).issubset(set(group_ids))
        ]
        merged = merge_group(group_concepts, "; ".join(reasons) or "manual merge")
        merged_rows.append(merged)
        for old_id in group_ids:
            merged_by_old_id[old_id] = merged["concept_id"]
        log_rows.append(
            {
                "merge_id": stable_hash(sorted(group_ids), "manual_concept_merge"),
                "decision": "merge",
                "merged_from": sorted(group_ids),
                "merged_to": merged["concept_id"],
                "canonical_label": merged["canonical_label"],
                "reason": merged["manual_merge"]["reason"],
            }
        )

    untouched = [concept for concept in concepts if concept.get("concept_id") not in consumed]
    final_rows = sorted([*untouched, *merged_rows], key=lambda row: row.get("concept_id", ""))
    concept_path.unlink(missing_ok=True)
    alias_path.unlink(missing_ok=True)
    append_jsonl(concept_path, final_rows)

    alias_rows = []
    for old_id, new_id in sorted(merged_by_old_id.items()):
        old = by_id[old_id]
        if old_id == new_id:
            continue
        alias_rows.append(
            {
                "alias": old.get("normalized_label"),
                "alias_label": old.get("canonical_label"),
                "canonical_concept_id": new_id,
                "reason": "manual_merge",
                "confidence": 1.0,
            }
        )
    append_jsonl(alias_path, alias_rows)
    append_jsonl(log_path, log_rows)
    write_json(
        summary_path,
        {
            "before": len(concepts),
            "after": len(final_rows),
            "removed": len(concepts) - len(final_rows),
            "merge_groups": len(groups),
            "alias_rows": len(alias_rows),
            "backup": str(backup_path),
        },
    )
    print(f"merged {len(groups)} groups; concepts {len(concepts)} -> {len(final_rows)}")
    print(f"backup: {backup_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
