#!/usr/bin/env python3
"""Build deterministic section-concept and dependency links from raw concepts."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any

from common import (
    append_jsonl,
    concept_id_from_label,
    ensure_repo_root,
    is_curriculum_section_id,
    normalize_label,
    read_json,
    read_jsonl,
    stable_hash,
    validate_confidence,
    write_json,
)


OUTPUT_RELATIONSHIPS = "raw_section_concept_relationships.jsonl"
OUTPUT_DEPENDENCIES = "raw_section_dependency_relationships.jsonl"
OUTPUT_INDEX = "section_concept_index.json"


def canonical_maps(concepts: list[dict[str, Any]], aliases: list[dict[str, Any]]) -> tuple[set[str], dict[str, str]]:
    canonical_ids = {row["concept_id"] for row in concepts if row.get("concept_id")}
    lookup: dict[str, str] = {}
    for concept in concepts:
        concept_id = concept.get("concept_id")
        if not concept_id:
            continue
        values = {
            concept_id,
            concept_id.replace("concept:", ""),
            concept.get("normalized_label", ""),
            concept.get("canonical_label", ""),
            concept_id_from_label(str(concept.get("canonical_label", ""))).replace("concept:", ""),
        }
        values.update(str(alias) for alias in concept.get("aliases", []) if alias)
        for value in values:
            if value:
                lookup[str(value)] = concept_id
                lookup[normalize_label(str(value))] = concept_id
    for alias in aliases:
        canonical_id = alias.get("canonical_concept_id")
        if canonical_id not in canonical_ids:
            continue
        for key in (alias.get("alias"), alias.get("alias_label")):
            if key:
                lookup[str(key)] = canonical_id
                lookup[normalize_label(str(key))] = canonical_id
    return canonical_ids, lookup


def canonicalize_raw_concept(row: dict[str, Any], canonical_ids: set[str], lookup: dict[str, str]) -> str | None:
    candidates = [
        row.get("candidate_concept_id"),
        str(row.get("candidate_concept_id", "")).replace("concept:", ""),
        row.get("normalized_label"),
        row.get("label"),
        concept_id_from_label(str(row.get("label", ""))),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        text = str(candidate)
        if text in canonical_ids:
            return text
        for key in (text, normalize_label(text), text.replace("concept:", "")):
            mapped = lookup.get(key)
            if mapped in canonical_ids:
                return mapped
    return None


def relationship_row(section_id: str, concept_id: str, rows: list[dict[str, Any]], rel_type: str) -> dict[str, Any]:
    best = sorted(rows, key=lambda row: validate_confidence(row.get("confidence")), reverse=True)[0]
    evidence_items = [
        evidence
        for row in rows
        for evidence in row.get("evidence", [])
        if isinstance(evidence, dict) and evidence.get("text")
    ]
    best_reason = str(best.get("reason") or "").strip()
    source_evidence_text = str((evidence_items[0] if evidence_items else {}).get("text") or "").strip()
    if rel_type == "REQUIRES_CONCEPT":
        evidence_text = (best_reason or source_evidence_text or str(best.get("label") or ""))[:1200]
    else:
        evidence_text = (source_evidence_text or str(best.get("definition") or best.get("label") or ""))[:1200]
    labels = sorted({str(row.get("label")) for row in rows if row.get("label")}, key=str.lower)
    source_raw_ids = sorted({row["raw_concept_id"] for row in rows if row.get("raw_concept_id")})
    row = {
        "chapter_id": best.get("chapter_id"),
        "source_section_id": section_id,
        "type": rel_type,
        "from_id": section_id,
        "to_id": concept_id,
        "confidence": round(max(validate_confidence(row.get("confidence")) for row in rows), 4),
        "evidence": {
            "unit_id": section_id,
            "text": evidence_text,
            "reason": relationship_reason(rel_type),
        },
        "source_raw_concept_ids": source_raw_ids,
        "source_labels": labels,
        "generation": {"script": "12_build_section_concept_links.py", "method": "deterministic_raw_concept_mapping"},
    }
    if rel_type == "REQUIRES_CONCEPT":
        row["pedagogical_reason"] = evidence_text
    elif rel_type == "TEACHES_CONCEPT":
        row["teaching_evidence"] = evidence_text
    row["relationship_id"] = stable_hash(
        {"type": row["type"], "from_id": row["from_id"], "to_id": row["to_id"]},
        "rel",
    )
    return row


def relationship_reason(rel_type: str) -> str:
    if rel_type == "REQUIRES_CONCEPT":
        return "Derived from raw prerequisite concept candidates generated from this section's source text."
    return "Derived from raw taught concept candidates generated from this section's source text."


def dependency_row(require_row: dict[str, Any], teach_row: dict[str, Any], rel_type: str) -> dict[str, Any]:
    required_section_id = require_row["from_id"]
    teaching_section_id = teach_row["from_id"]
    concept_id = require_row["to_id"]
    confidence = round(min(validate_confidence(require_row.get("confidence")), validate_confidence(teach_row.get("confidence"))), 4)
    require_evidence = require_row.get("evidence") or {}
    teach_evidence = teach_row.get("evidence") or {}
    row = {
        "chapter_id": require_row.get("chapter_id"),
        "source_section_id": required_section_id,
        "type": rel_type,
        "from_id": required_section_id,
        "to_id": teaching_section_id,
        "confidence": confidence,
        "evidence": {
            "unit_id": required_section_id,
            "text": (
                f"Required concept evidence: {str(require_evidence.get('text') or '')}\n"
                f"Teaching evidence: {str(teach_evidence.get('text') or '')}"
            )[:1200],
            "reason": (
                dependency_reason(rel_type, required_section_id, teaching_section_id, concept_id)
            )[:800],
        },
        "source_concept_id": concept_id,
        "source_relationship_ids": [
            require_row.get("relationship_id"),
            teach_row.get("relationship_id"),
        ],
        "generation": {"script": "12_build_section_concept_links.py", "method": "deterministic_teaches_requires_join"},
    }
    row["relationship_id"] = stable_hash(
        {"type": row["type"], "from_id": row["from_id"], "to_id": row["to_id"], "concept_id": concept_id},
        "rel",
    )
    return row


def dependency_reason(rel_type: str, required_section_id: str, teaching_section_id: str, concept_id: str) -> str:
    if rel_type == "TRANSFER_SUPPORTS_UNIT":
        return (
            f"{teaching_section_id} teaches {concept_id}, which can support transfer into "
            f"{required_section_id}; this is a soft cross-chapter bridge, not a hard prerequisite."
        )
    return f"{required_section_id} requires {concept_id}, which is taught by {teaching_section_id}."


def related_row(left_row: dict[str, Any], right_row: dict[str, Any]) -> dict[str, Any]:
    left_id = left_row["from_id"]
    right_id = right_row["from_id"]
    concept_id = left_row["to_id"]
    confidence = round(min(validate_confidence(left_row.get("confidence")), validate_confidence(right_row.get("confidence"))), 4)
    left_evidence = left_row.get("evidence") or {}
    right_evidence = right_row.get("evidence") or {}
    row = {
        "chapter_id": left_row.get("chapter_id"),
        "source_section_id": left_id,
        "type": "RELATED_BY_CONCEPT",
        "from_id": left_id,
        "to_id": right_id,
        "confidence": confidence,
        "evidence": {
            "unit_id": left_id,
            "text": (
                f"First section evidence: {str(left_evidence.get('text') or '')}\n"
                f"Second section evidence: {str(right_evidence.get('text') or '')}"
            )[:1200],
            "reason": f"Both sections teach {concept_id}; this is a semantic overlap, not a prerequisite.",
        },
        "source_concept_id": concept_id,
        "source_relationship_ids": [
            left_row.get("relationship_id"),
            right_row.get("relationship_id"),
        ],
        "generation": {"script": "12_build_section_concept_links.py", "method": "deterministic_shared_teaches_join"},
    }
    row["relationship_id"] = stable_hash(
        {"type": row["type"], "from_id": row["from_id"], "to_id": row["to_id"], "concept_id": concept_id},
        "rel",
    )
    return row


def infer_section_links(concept_relationships: list[dict[str, Any]]) -> list[dict[str, Any]]:
    teaches: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    requires: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    teaches_by_concept: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in concept_relationships:
        key = (row.get("chapter_id"), row.get("to_id"))
        if row.get("type") == "TEACHES_CONCEPT":
            teaches[key].append(row)
            teaches_by_concept[row["to_id"]].append(row)
        elif row.get("type") == "REQUIRES_CONCEPT":
            requires[key].append(row)

    links: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for key, require_rows in sorted(requires.items()):
        chapter_id, concept_id = key
        teach_rows = teaches.get(key, [])
        for require_row in require_rows:
            for teach_row in teach_rows:
                if require_row["from_id"] == teach_row["from_id"]:
                    continue
                dedupe_key = ("DEPENDS_ON_UNIT", require_row["from_id"], teach_row["from_id"], require_row["to_id"])
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                links.append(dependency_row(require_row, teach_row, "DEPENDS_ON_UNIT"))

        for teach_row in teaches_by_concept.get(concept_id, []):
            if teach_row.get("chapter_id") == chapter_id:
                continue
            for require_row in require_rows:
                if require_row["from_id"] == teach_row["from_id"]:
                    continue
                dedupe_key = ("TRANSFER_SUPPORTS_UNIT", require_row["from_id"], teach_row["from_id"], require_row["to_id"])
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                links.append(dependency_row(require_row, teach_row, "TRANSFER_SUPPORTS_UNIT"))

    for concept_id, teach_rows in sorted(teaches_by_concept.items()):
        for left, right in combinations(sorted(teach_rows, key=lambda row: row["from_id"]), 2):
            if left["from_id"] == right["from_id"]:
                continue
            if left.get("chapter_id") == right.get("chapter_id"):
                continue
            dedupe_key = ("RELATED_BY_CONCEPT", left["from_id"], right["from_id"], concept_id)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            links.append(related_row(left, right))
    return links


def section_concept_index(relationships: list[dict[str, Any]], section_links: list[dict[str, Any]]) -> dict[str, Any]:
    section_to_concepts: dict[str, list[str]] = defaultdict(list)
    section_to_required_concepts: dict[str, list[str]] = defaultdict(list)
    concept_to_sections: dict[str, list[str]] = defaultdict(list)
    concept_to_requiring_sections: dict[str, list[str]] = defaultdict(list)
    chapter_sections_by_concept: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in relationships:
        section_id = row["from_id"]
        concept_id = row["to_id"]
        chapter_id = row["chapter_id"]
        if row["type"] == "TEACHES_CONCEPT":
            section_to_concepts[section_id].append(concept_id)
            concept_to_sections[concept_id].append(section_id)
            chapter_sections_by_concept[(chapter_id, concept_id)].append(section_id)
        elif row["type"] == "REQUIRES_CONCEPT":
            section_to_required_concepts[section_id].append(concept_id)
            concept_to_requiring_sections[concept_id].append(section_id)

    shared_links = []
    for (chapter_id, concept_id), section_ids in sorted(chapter_sections_by_concept.items()):
        unique_sections = sorted(set(section_ids))
        if len(unique_sections) < 2:
            continue
        for left, right in combinations(unique_sections, 2):
            shared_links.append(
                {
                    "chapter_id": chapter_id,
                    "from_section_id": left,
                    "to_section_id": right,
                    "concept_id": concept_id,
                    "link_type": "SHARES_TEACHES_CONCEPT",
                }
            )

    return {
        "section_count": len(section_to_concepts),
        "concept_count": len(concept_to_sections),
        "requiring_section_count": len(section_to_required_concepts),
        "required_concept_count": len(concept_to_requiring_sections),
        "section_link_count": len(section_links),
        "section_link_count_by_type": dict(Counter(row["type"] for row in section_links)),
        "shared_section_link_count": len(shared_links),
        "section_to_concepts": {key: sorted(set(values)) for key, values in sorted(section_to_concepts.items())},
        "section_to_required_concepts": {key: sorted(set(values)) for key, values in sorted(section_to_required_concepts.items())},
        "concept_to_sections": {key: sorted(set(values)) for key, values in sorted(concept_to_sections.items())},
        "concept_to_requiring_sections": {key: sorted(set(values)) for key, values in sorted(concept_to_requiring_sections.items())},
        "shared_section_links": shared_links,
        "section_links": [
            {
                "chapter_id": row["chapter_id"],
                "from_section_id": row["from_id"],
                "to_section_id": row["to_id"],
                "concept_id": row.get("source_concept_id"),
                "link_type": row["type"],
                "confidence": row.get("confidence"),
            }
            for row in section_links
        ],
    }


def main() -> int:
    ensure_repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, default=Path("data/relationship_artifacts"))
    parser.add_argument("--include-partial", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    relationship_path = args.artifact_dir / OUTPUT_RELATIONSHIPS
    dependency_path = args.artifact_dir / OUTPUT_DEPENDENCIES
    index_path = args.artifact_dir / OUTPUT_INDEX
    if relationship_path.exists() and not args.force:
        print(f"{relationship_path} exists; pass --force to regenerate")
        return 0
    relationship_path.unlink(missing_ok=True)
    dependency_path.unlink(missing_ok=True)
    index_path.unlink(missing_ok=True)

    usable_path = args.artifact_dir / "usable_chapters.json"
    usable_chapters = set()
    if usable_path.exists() and not args.include_partial:
        usable_chapters = set(read_json(usable_path).get("usable_chapter_ids", []))

    concepts = read_jsonl(args.artifact_dir / "canonical_concepts.jsonl")
    aliases = read_jsonl(args.artifact_dir / "concept_aliases.jsonl")
    raw_concepts = read_jsonl(args.artifact_dir / "raw_concepts.jsonl")
    canonical_ids, lookup = canonical_maps(concepts, aliases)

    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    skipped = Counter()
    for row in raw_concepts:
        chapter_id = row.get("chapter_id")
        if usable_chapters and chapter_id not in usable_chapters:
            skipped["outside_usable_chapters"] += 1
            continue
        raw_type = row.get("relationship_type", "teaches")
        if raw_type == "teaches":
            rel_type = "TEACHES_CONCEPT"
        elif raw_type == "requires":
            rel_type = "REQUIRES_CONCEPT"
        else:
            skipped["unknown_relationship_type"] += 1
            continue
        section_id = row.get("source_section_id")
        if not is_curriculum_section_id(section_id):
            skipped["non_curriculum_section"] += 1
            continue
        concept_id = canonicalize_raw_concept(row, canonical_ids, lookup)
        if not section_id:
            skipped["missing_section"] += 1
            continue
        if not concept_id:
            skipped["unmapped_concept"] += 1
            continue
        grouped[(rel_type, section_id, concept_id)].append(row)

    relationships = [
        relationship_row(section_id, concept_id, rows, rel_type)
        for (rel_type, section_id, concept_id), rows in sorted(grouped.items())
    ]
    section_links = infer_section_links(relationships)
    append_jsonl(relationship_path, relationships)
    append_jsonl(dependency_path, section_links)
    index = section_concept_index(relationships, section_links)
    index.update(
        {
            "relationship_count": len(relationships),
            "concept_relationship_count_by_type": dict(Counter(row["type"] for row in relationships)),
            "section_link_count": len(section_links),
            "section_link_count_by_type": dict(Counter(row["type"] for row in section_links)),
            "raw_concept_count": len(raw_concepts),
            "skipped": dict(skipped),
            "usable_only": bool(usable_chapters),
            "usable_chapter_count": len(usable_chapters),
        }
    )
    write_json(index_path, index)
    print(f"wrote {len(relationships)} concept links to {relationship_path}")
    print(f"wrote {len(section_links)} section links to {dependency_path}")
    print(f"wrote index to {index_path}")
    print(f"skipped={dict(skipped)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
