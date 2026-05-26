#!/usr/bin/env python3
"""Merge, validate, canonicalize, and confidence-gate split relationship artifacts."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from common import (
    RELATIONSHIP_TYPES,
    append_jsonl,
    concept_id_from_label,
    ensure_repo_root,
    exercise_ids_from_chapter,
    load_chapter_context,
    load_manifest,
    read_jsonl,
    stable_hash,
    validate_confidence,
    write_json,
)


def load_raw_relationships(artifact_dir: Path) -> list[dict[str, Any]]:
    # Load canonical concepts to map raw concepts to canonical concepts
    concepts = read_jsonl(artifact_dir / "canonical_concepts.jsonl")
    raw_to_canonical = {}
    for concept in concepts:
        cid = concept["concept_id"]
        for rcid in concept.get("source_raw_concept_ids", []):
            raw_to_canonical[rcid] = cid

    # Load raw concepts
    raw_concepts = read_jsonl(artifact_dir / "raw_concepts.jsonl")
    edges: list[dict[str, Any]] = []

    # Create TEACHES_CONCEPT and REQUIRES_CONCEPT edges
    for rc in raw_concepts:
        rcid = rc.get("raw_concept_id")
        cid = raw_to_canonical.get(rcid)
        if not cid:
            cid = f"concept:{rc.get('normalized_label')}"
        
        rel_type = "TEACHES_CONCEPT" if rc.get("relationship_type") == "teaches" else "REQUIRES_CONCEPT"
        evidence = rc.get("evidence", [])
        evidence_text = evidence[0].get("text", "") if evidence else ""
        evidence_reason = rc.get("reason") or rc.get("definition") or ""

        row = {
            "chapter_id": rc["chapter_id"],
            "type": rel_type,
            "from_id": rc["source_section_id"],
            "to_id": cid,
            "confidence": validate_confidence(rc.get("confidence")),
            "evidence": {
                "unit_id": rc["source_section_id"],
                "text": str(evidence_text)[:1200],
                "reason": str(evidence_reason)[:800],
            },
            "generation": rc.get("generation") or {"model": "unknown", "script": "07_gate_relationships.py"},
            "source_file": "raw_concepts.jsonl"
        }
        row["relationship_id"] = stable_hash({"type": rel_type, "from": row["from_id"], "to": row["to_id"]}, "rel")
        edges.append(row)

    # Programmatically infer DEPENDS_ON_UNIT edges within each chapter
    chapter_teaches = defaultdict(lambda: defaultdict(list))
    chapter_requires = defaultdict(lambda: defaultdict(list))

    for edge in edges:
        ch_id = edge["chapter_id"]
        cid = edge["to_id"]
        if edge["type"] == "TEACHES_CONCEPT":
            chapter_teaches[ch_id][cid].append(edge)
        elif edge["type"] == "REQUIRES_CONCEPT":
            chapter_requires[ch_id][cid].append(edge)

    for ch_id, requires_map in chapter_requires.items():
        teaches_map = chapter_teaches[ch_id]
        for cid, req_edges in requires_map.items():
            if cid in teaches_map:
                for req_edge in req_edges:
                    for teach_edge in teaches_map[cid]:
                        from_id = req_edge["from_id"]
                        to_id = teach_edge["from_id"]
                        if from_id == to_id:
                            continue
                        confidence = round(min(req_edge["confidence"], teach_edge["confidence"]), 4)
                        
                        reason = f"Unit {from_id} requires concept '{cid}' (Reason: {req_edge['evidence']['reason']}), which is taught in unit {to_id}."
                        text = f"Prerequisite requirement evidence: {req_edge['evidence']['text']}\nTeaches concept evidence: {teach_edge['evidence']['text']}"

                        dep_row = {
                            "chapter_id": ch_id,
                            "type": "DEPENDS_ON_UNIT",
                            "from_id": from_id,
                            "to_id": to_id,
                            "confidence": confidence,
                            "evidence": {
                                "unit_id": from_id,
                                "text": text[:1200],
                                "reason": reason[:800],
                            },
                            "generation": {"model": "programmatic", "script": "07_gate_relationships.py"},
                            "source_file": "programmatic_inference"
                        }
                        dep_row["relationship_id"] = stable_hash({"type": "DEPENDS_ON_UNIT", "from": from_id, "to": to_id}, "rel")
                        edges.append(dep_row)

    return edges


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


def all_section_and_exercise_ids(manifest_path: Path) -> tuple[set[str], set[str]]:
    section_ids: set[str] = set()
    exercise_ids: set[str] = set()
    for ref in load_manifest(manifest_path):
        data = load_chapter_context(ref.path, max_chars=10**9)
        section_ids.update(section["id"] for section in data["chapter"].get("sections", []))
        exercise_ids.update(exercise_ids_from_chapter(data))
    return section_ids, exercise_ids


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
    section_ids, exercise_ids = all_section_and_exercise_ids(args.manifest)
    raw_concept_types: dict[tuple[Any, Any], set[Any]] = {}
    for row in raw:
        if row.get("type") in {"TEACHES_CONCEPT", "REQUIRES_CONCEPT"}:
            raw_concept_types.setdefault((row.get("from_id"), row.get("to_id")), set()).add(row.get("type"))
    teach_require_conflicts = {
        key
        for key, types in raw_concept_types.items()
        if {"TEACHES_CONCEPT", "REQUIRES_CONCEPT"}.issubset(types)
    }

    accepted: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any, Any]] = set()

    for row in raw:
        reasons: list[str] = []
        review_reasons: list[str] = []
        rel_type = row.get("type")
        from_id = row.get("from_id")
        to_id = row.get("to_id")
        confidence = validate_confidence(row.get("confidence"))

        if rel_type not in RELATIONSHIP_TYPES:
            reasons.append("invalid_relationship_type")

        if rel_type in {"DEPENDS_ON_UNIT", "REQUIRES_CONCEPT", "TEACHES_CONCEPT"} and from_id not in section_ids:
            reasons.append("from_id_not_section")
        if rel_type in {"TESTS_UNIT", "TESTS_CONCEPT"} and from_id not in exercise_ids:
            reasons.append("from_id_not_exercise")

        if rel_type in {"DEPENDS_ON_UNIT", "TESTS_UNIT"}:
            if to_id not in section_ids:
                reasons.append("to_id_not_section")
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
        if rel_type in {"TEACHES_CONCEPT", "REQUIRES_CONCEPT"} and (from_id, to_id) in teach_require_conflicts:
            review_reasons.append("same_unit_teaches_and_requires_concept")

        edge_key = (rel_type, from_id, to_id)
        if edge_key in seen:
            reasons.append("duplicate_edge")
        seen.add(edge_key)

        row["confidence"] = confidence
        row["gate_reasons"] = reasons
        if review_reasons:
            row["review_reasons"] = review_reasons
        row["relationship_id"] = stable_hash({"type": rel_type, "from": from_id, "to": to_id}, "rel")

        if reasons or confidence < args.review_threshold:
            rejected.append(row)
        elif review_reasons or confidence < args.accept_threshold:
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
        "review_reasons": dict(Counter(reason for r in review for reason in r.get("review_reasons", []))),
        "rejected_reasons": dict(Counter(reason for r in rejected for reason in r.get("gate_reasons", []))),
        "accept_threshold": args.accept_threshold,
        "review_threshold": args.review_threshold,
    }
    write_json(args.artifact_dir / "relationship_summary.json", summary)
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
