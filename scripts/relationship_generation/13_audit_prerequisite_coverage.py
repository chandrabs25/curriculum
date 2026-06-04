#!/usr/bin/env python3
"""Audit required concepts that cannot form exact prerequisite section links."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from common import append_jsonl, ensure_repo_root, normalize_label, read_jsonl, similarity, stable_hash, write_json


EQUIVALENT_TERM_GROUPS = (
    {"uniform", "constant"},
    {"law", "equation"},
    {"centre", "center"},
    {"fertilisation", "fertilization"},
    {"polarisation", "polarization"},
    {"hybridisation", "hybridization"},
)


def tokens(label: str) -> set[str]:
    return {part for part in normalize_label(label).split("_") if part}


def semantic_key(label: str) -> tuple[str, ...]:
    canonical_terms: dict[str, str] = {}
    for group in EQUIVALENT_TERM_GROUPS:
        representative = sorted(group)[0]
        for term in group:
            canonical_terms[term] = representative
    return tuple(sorted(canonical_terms.get(token, token) for token in tokens(label)))


def concept_public_row(concept: dict[str, Any]) -> dict[str, Any]:
    return {
        "concept_id": concept.get("concept_id"),
        "label": concept.get("canonical_label"),
        "definition": concept.get("definition") or "",
        "subjects": concept.get("subjects") or [],
        "source_chapter_ids": concept.get("source_chapter_ids") or [],
    }


def candidate_score(required: dict[str, Any], taught: dict[str, Any]) -> tuple[float, str]:
    required_label = str(required.get("canonical_label") or "")
    taught_label = str(taught.get("canonical_label") or "")
    required_tokens = tokens(required_label)
    taught_tokens = tokens(taught_label)
    if semantic_key(required_label) == semantic_key(taught_label):
        return 1.0, "equivalent_terminology"
    label_similarity = similarity(required_label, taught_label)
    if label_similarity >= 0.92:
        return label_similarity, "high_label_similarity"
    if required_tokens and taught_tokens and (required_tokens < taught_tokens or taught_tokens < required_tokens):
        overlap = len(required_tokens & taught_tokens) / max(len(required_tokens), len(taught_tokens))
        return max(label_similarity, overlap), "token_subset_broader_or_narrower"
    return label_similarity, "label_similarity"


def classify_unmatched(required: dict[str, Any], taught_concepts: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    required_subjects = set(required.get("subjects") or [])
    candidates = []
    for taught in taught_concepts:
        taught_subjects = set(taught.get("subjects") or [])
        if required_subjects and taught_subjects and not required_subjects.intersection(taught_subjects):
            continue
        score, heuristic = candidate_score(required, taught)
        if score < 0.55:
            continue
        candidates.append(
            {
                **concept_public_row(taught),
                "similarity": round(score, 4),
                "heuristic": heuristic,
            }
        )
    candidates.sort(key=lambda row: (-float(row["similarity"]), str(row["concept_id"])))
    best = candidates[0] if candidates else None
    if best and best["heuristic"] in {"equivalent_terminology", "high_label_similarity"}:
        return "equivalent_candidate", candidates[:3]
    if best and best["heuristic"] == "token_subset_broader_or_narrower" and best["similarity"] >= 0.6:
        return "broader_or_narrower", candidates[:3]
    if best and best["similarity"] >= 0.72:
        return "unresolved", candidates[:3]
    return "external_prerequisite", candidates[:3]


def reviewed_distinct_pairs(decisions: list[dict[str, Any]]) -> dict[frozenset[str], dict[str, Any]]:
    return {
        frozenset(str(value) for value in row.get("concept_ids", []) if value): row
        for row in decisions
        if row.get("review_status") == "approved"
        and row.get("final_decision") == "keep_distinct"
        and len(set(row.get("concept_ids", []))) == 2
    }


def build_audit(
    concepts: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    finalized_decisions: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    concepts_by_id = {row["concept_id"]: row for row in concepts if row.get("concept_id")}
    taught_sections: dict[str, set[str]] = defaultdict(set)
    taught_chapters: dict[str, set[str]] = defaultdict(set)
    required_sections: dict[str, set[str]] = defaultdict(set)
    required_chapters: dict[str, set[str]] = defaultdict(set)
    dependency_count = 0
    for row in relationships:
        concept_id = str(row.get("to_id") or "")
        if row.get("type") == "TEACHES_CONCEPT":
            taught_sections[concept_id].add(str(row.get("from_id") or ""))
            taught_chapters[concept_id].add(str(row.get("chapter_id") or ""))
        elif row.get("type") == "REQUIRES_CONCEPT":
            required_sections[concept_id].add(str(row.get("from_id") or ""))
            required_chapters[concept_id].add(str(row.get("chapter_id") or ""))
        elif row.get("type") == "DEPENDS_ON_UNIT":
            dependency_count += 1

    taught_concepts = [concepts_by_id[cid] for cid in taught_sections if cid in concepts_by_id]
    classifications = Counter()
    reviewed_pairs = reviewed_distinct_pairs(finalized_decisions or [])
    audit_rows = []
    review_candidates = []
    for concept_id in sorted(required_sections):
        concept = concepts_by_id.get(concept_id, {"concept_id": concept_id, "canonical_label": concept_id})
        taught_anywhere = bool(taught_sections.get(concept_id))
        taught_same_chapter = bool(required_chapters[concept_id].intersection(taught_chapters.get(concept_id, set())))
        if taught_anywhere:
            classification = "taught_same_chapter" if taught_same_chapter else "taught_other_chapter"
            candidates: list[dict[str, Any]] = []
        else:
            classification, candidates = classify_unmatched(concept, taught_concepts)
            if candidates:
                reviewed = reviewed_pairs.get(frozenset({concept_id, str(candidates[0]["concept_id"])}))
                if reviewed:
                    classification = f"reviewed_{reviewed['relationship']}"
                    candidates[0]["reviewed_decision"] = {
                        "final_decision": reviewed["final_decision"],
                        "relationship": reviewed["relationship"],
                        "reason": reviewed.get("reason") or "",
                    }
        classifications[classification] += 1
        row = {
            **concept_public_row(concept),
            "classification": classification,
            "required_by_section_count": len(required_sections[concept_id]),
            "required_by_chapter_count": len(required_chapters[concept_id]),
            "taught_section_count": len(taught_sections.get(concept_id, set())),
            "taught_same_chapter": taught_same_chapter,
            "candidate_matches": candidates,
        }
        audit_rows.append(row)
        if classification == "equivalent_candidate":
            review_candidates.append(
                {
                    "candidate_id": stable_hash([concept_id, candidates[0]["concept_id"]], "prerequisite_concept_review"),
                    "required_concept": concept_public_row(concept),
                    "candidate_taught_concept": candidates[0],
                    "suggested_decision": "review_equivalence",
                    "reason": (
                        "The required concept is not taught under its current canonical ID, but a high-confidence "
                        "equivalent terminology candidate is taught. Review source evidence before merging or aliasing."
                    ),
                }
            )

    report = {
        "summary": {
            "required_concept_count": len(required_sections),
            "required_relationship_count": sum(len(rows) for rows in required_sections.values()),
            "required_concepts_taught_somewhere": sum(bool(taught_sections.get(cid)) for cid in required_sections),
            "required_concepts_taught_same_chapter": sum(
                bool(required_chapters[cid].intersection(taught_chapters.get(cid, set()))) for cid in required_sections
            ),
            "required_concepts_not_taught": sum(not bool(taught_sections.get(cid)) for cid in required_sections),
            "accepted_dependency_count": dependency_count,
            "classification_counts": dict(classifications),
            "review_equivalence_candidate_count": len(review_candidates),
        },
        "policy": {
            "exact_dependency_rule": "Dependencies are inferred only when REQUIRES_CONCEPT and TEACHES_CONCEPT share a reviewed canonical concept ID.",
            "equivalence_candidates": "Candidates require review; this audit never mutates canonical concepts or relationships.",
            "external_prerequisite": "No credible teaching concept match was found in the available corpus.",
            "reviewed_distinct": "Reviewed distinct pairs remain separate and are not returned to the equivalence queue.",
        },
        "required_concepts": audit_rows,
    }
    return report, review_candidates


def main() -> int:
    ensure_repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, default=Path("data/relationship_artifacts"))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    report_path = args.artifact_dir / "prerequisite_coverage_audit.json"
    review_path = args.artifact_dir / "review" / "prerequisite_concept_candidates.jsonl"
    if report_path.exists() and not args.force:
        print(f"{report_path} exists; pass --force to regenerate")
        return 0
    report_path.unlink(missing_ok=True)
    review_path.unlink(missing_ok=True)

    report, review_candidates = build_audit(
        read_jsonl(args.artifact_dir / "canonical_concepts.jsonl"),
        read_jsonl(args.artifact_dir / "accepted_relationships.jsonl"),
        read_jsonl(args.artifact_dir / "review" / "finalized_prerequisite_concept_decisions.jsonl"),
    )
    write_json(report_path, report)
    append_jsonl(review_path, review_candidates)
    print(report["summary"])
    print(f"wrote {report_path}")
    print(f"wrote {len(review_candidates)} review candidates to {review_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
