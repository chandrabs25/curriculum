"""Build graph-aware planning context for curriculum generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .graph import CurriculumGraph
from .retrieval import LearnerConceptState, LearnerConceptStatus, SectionRetrievalResult


DIRECT_MATCH_REASONS = {
    "vector_match",
    "concept_match",
    "title_match",
    "key_term_match",
    "summary_match",
    "learner_misconception",
    "learner_partial",
    "learner_competency",
    "intent_grounding",
}


@dataclass(frozen=True)
class LearningPathContext:
    main_path_sections: list[dict[str, Any]]
    target_sections: list[dict[str, Any]]
    prerequisite_sections: list[dict[str, Any]]
    support_sections: list[dict[str, Any]]
    prerequisite_check: dict[str, Any]
    parallel_support_paths: list[dict[str, Any]]
    reinforcement_paths: list[dict[str, Any]]
    next_step_paths: list[dict[str, Any]]
    cross_chapter_bridges: list[dict[str, Any]]
    relationship_policy: dict[str, str]
    required_concepts: list[dict[str, Any]]
    taught_concepts: list[dict[str, Any]]
    hard_dependency_edges: list[dict[str, Any]]
    optional_support_edges: list[dict[str, Any]]
    learner_adjustments: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "main_path_sections": self.main_path_sections,
            "target_sections": self.target_sections,
            "prerequisite_sections": self.prerequisite_sections,
            "support_sections": self.support_sections,
            "prerequisite_check": self.prerequisite_check,
            "parallel_support_paths": self.parallel_support_paths,
            "reinforcement_paths": self.reinforcement_paths,
            "next_step_paths": self.next_step_paths,
            "cross_chapter_bridges": self.cross_chapter_bridges,
            "relationship_policy": self.relationship_policy,
            "required_concepts": self.required_concepts,
            "taught_concepts": self.taught_concepts,
            "hard_dependency_edges": self.hard_dependency_edges,
            "optional_support_edges": self.optional_support_edges,
            "learner_adjustments": self.learner_adjustments,
        }


def build_learning_path_context(
    graph: CurriculumGraph,
    retrieved: list[SectionRetrievalResult],
    learner_state: list[LearnerConceptState] | None = None,
    prerequisite_check: dict[str, Any] | None = None,
) -> LearningPathContext:
    retrieved_by_id = {item.section_id: item for item in retrieved}
    target_ids = [item.section_id for item in retrieved if _role_for_result(item) == "target"]
    prerequisite_ids = [item.section_id for item in retrieved if _role_for_result(item) == "prerequisite"]
    support_ids = [item.section_id for item in retrieved if _role_for_result(item) == "support"]

    hard_edges: list[dict[str, Any]] = []
    optional_edges: list[dict[str, Any]] = []
    next_step_edges: list[dict[str, Any]] = []
    for section_id in target_ids:
        for edge in graph.hard_dependency_edges_for_section(section_id):
            hard_edges.append(edge)
            _append_unique(prerequisite_ids, str(edge.get("to_section_id") or ""))
        for edge in graph.optional_support_edges_for_section(section_id):
            optional_edges.append(edge)
            support_id = _other_section_id(edge, section_id)
            _append_unique(support_ids, support_id)
        for edge in graph.dependent_edges_for_section(section_id):
            next_step_edges.append(edge)

    target_sections = [_section_context(graph, section_id, "target", retrieved_by_id.get(section_id)) for section_id in target_ids]
    prerequisite_sections = [
        _section_context(graph, section_id, "prerequisite", retrieved_by_id.get(section_id))
        for section_id in prerequisite_ids
        if section_id and section_id not in target_ids
    ]
    support_sections = [
        _section_context(graph, section_id, "support", retrieved_by_id.get(section_id))
        for section_id in support_ids
        if section_id and section_id not in target_ids and section_id not in prerequisite_ids
    ]
    main_path_sections = prerequisite_sections + target_sections
    parallel_support_paths = _path_rows(graph, optional_edges, target_ids, "TRANSFER_SUPPORTS_UNIT", "optional support while studying the main module")
    reinforcement_paths = _path_rows(graph, optional_edges, target_ids, "RELATED_BY_CONCEPT", "extra practice or comparison after the core module")
    next_step_paths = _next_step_rows(graph, next_step_edges, target_ids)
    cross_chapter_bridges = [
        row
        for row in parallel_support_paths
        if row.get("chapter_id") and row.get("source_target_chapter_id") and row.get("chapter_id") != row.get("source_target_chapter_id")
    ]
    main_concept_sections = target_sections + prerequisite_sections
    all_sections = main_concept_sections + support_sections
    return LearningPathContext(
        main_path_sections=main_path_sections,
        target_sections=target_sections,
        prerequisite_sections=prerequisite_sections,
        support_sections=support_sections,
        prerequisite_check=prerequisite_check or {"asked": False, "answers": []},
        parallel_support_paths=parallel_support_paths,
        reinforcement_paths=reinforcement_paths,
        next_step_paths=next_step_paths,
        cross_chapter_bridges=cross_chapter_bridges,
        relationship_policy=relationship_policy(),
        required_concepts=_concept_rows(main_concept_sections, "requires"),
        taught_concepts=_concept_rows(all_sections, "teaches"),
        hard_dependency_edges=hard_edges,
        optional_support_edges=optional_edges,
        learner_adjustments=_learner_adjustments(learner_state or []),
    )


def _section_context(
    graph: CurriculumGraph,
    section_id: str,
    role: str,
    retrieved: SectionRetrievalResult | None,
) -> dict[str, Any]:
    summary = graph.section_summaries_by_id.get(section_id, {})
    section = graph.sections_by_id.get(section_id, {})
    return {
        "section_id": section_id,
        "chapter_id": retrieved.chapter_id if retrieved else summary.get("chapter_id") or section.get("chapter_id") or "",
        "title": retrieved.title if retrieved else summary.get("title") or section.get("title") or "",
        "summary": retrieved.summary if retrieved else summary.get("summary") or "",
        "role": role,
        "retrieval_reasons": retrieved.reasons if retrieved else [],
        "score": retrieved.score if retrieved else 0.0,
        "teaches": graph.teaches_concept_details(section_id),
        "requires": graph.requires_concept_details(section_id),
    }


def _role_for_result(item: SectionRetrievalResult) -> str:
    reasons = set(item.reasons)
    if reasons & DIRECT_MATCH_REASONS:
        return "target"
    if "prerequisite" in reasons:
        return "prerequisite"
    if {"transfer_support", "related_concept"} & reasons:
        return "support"
    return "target"


def _other_section_id(edge: dict[str, Any], section_id: str) -> str:
    from_id = str(edge.get("from_section_id") or "")
    to_id = str(edge.get("to_section_id") or "")
    return to_id if from_id == section_id else from_id


def _append_unique(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)


def _concept_rows(sections: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    rows = []
    for section in sections:
        for concept in section.get(key) or []:
            rows.append({"section_id": section["section_id"], **concept})
    return rows


def relationship_policy() -> dict[str, str]:
    return {
        "hard_dependencies": "DEPENDS_ON_UNIT edges must affect ordering; to_section_id should appear before from_section_id.",
        "required_concepts": "REQUIRES_CONCEPT explains prerequisite warnings and checkpoint questions.",
        "teaches_concepts": "TEACHES_CONCEPT explains concept coverage and can reveal downstream next steps.",
        "transfer_support": "TRANSFER_SUPPORTS_UNIT is an optional bridge, not mandatory curriculum sequence.",
        "related_by_concept": "RELATED_BY_CONCEPT is reinforcement or comparison only, not a prerequisite.",
        "next_steps": "Next-step paths are suggested after completion, not before the main module.",
    }


def _path_rows(
    graph: CurriculumGraph,
    edges: list[dict[str, Any]],
    target_ids: list[str],
    rel_type: str,
    use_as: str,
) -> list[dict[str, Any]]:
    rows = []
    for edge in edges:
        if edge.get("type") != rel_type:
            continue
        target_id = _target_for_edge(edge, target_ids)
        section_id = _other_section_id(edge, target_id)
        row = _recommendation_row(graph, section_id, edge, use_as)
        row["source_target_section_id"] = target_id
        row["source_target_chapter_id"] = graph.sections_by_id.get(target_id, {}).get("chapter_id") or graph.section_summaries_by_id.get(target_id, {}).get("chapter_id")
        rows.append(row)
    return _dedupe_path_rows(rows)


def _next_step_rows(graph: CurriculumGraph, edges: list[dict[str, Any]], target_ids: list[str]) -> list[dict[str, Any]]:
    rows = []
    for edge in edges:
        section_id = str(edge.get("from_section_id") or "")
        if not section_id or section_id in target_ids:
            continue
        target_id = str(edge.get("to_section_id") or "")
        row = _recommendation_row(graph, section_id, edge, "recommended next section after completing the module")
        row["source_target_section_id"] = target_id
        row["source_target_chapter_id"] = graph.sections_by_id.get(target_id, {}).get("chapter_id") or graph.section_summaries_by_id.get(target_id, {}).get("chapter_id")
        rows.append(row)
    return _dedupe_path_rows(rows)


def _recommendation_row(
    graph: CurriculumGraph,
    section_id: str,
    edge: dict[str, Any],
    use_as: str,
) -> dict[str, Any]:
    summary = graph.section_summaries_by_id.get(section_id, {})
    section = graph.sections_by_id.get(section_id, {})
    return {
        "section_id": section_id,
        "chapter_id": summary.get("chapter_id") or section.get("chapter_id") or "",
        "title": summary.get("title") or section.get("title") or "",
        "summary": summary.get("summary") or "",
        "relationship_id": edge.get("relationship_id"),
        "relationship_type": edge.get("type"),
        "bridge_concept_id": edge.get("bridge_concept_id"),
        "confidence": edge.get("confidence"),
        "evidence_text": edge.get("evidence_text") or "",
        "planning_meaning": edge.get("planning_meaning") or "",
        "use_as": use_as,
    }


def _target_for_edge(edge: dict[str, Any], target_ids: list[str]) -> str:
    from_id = str(edge.get("from_section_id") or "")
    to_id = str(edge.get("to_section_id") or "")
    if from_id in target_ids:
        return from_id
    if to_id in target_ids:
        return to_id
    return from_id or to_id


def _dedupe_path_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    deduped = []
    for row in rows:
        key = (
            str(row.get("section_id") or ""),
            str(row.get("relationship_type") or ""),
            str(row.get("bridge_concept_id") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def _learner_adjustments(learner_state: list[LearnerConceptState]) -> list[dict[str, Any]]:
    rows = []
    for state in learner_state:
        status = state.status.value if isinstance(state.status, LearnerConceptStatus) else str(state.status)
        rows.append(
            {
                "concept_id": state.concept_id,
                "status": status,
                "confidence": state.confidence,
                "recency_weight": state.recency_weight,
                "planning_effect": _planning_effect(status),
            }
        )
    return rows


def _planning_effect(status: str) -> str:
    if status == LearnerConceptStatus.MISCONCEPTION.value:
        return "prioritize sections that teach or remediate this concept"
    if status == LearnerConceptStatus.PARTIAL.value:
        return "include practice or a lighter review for this concept"
    if status == LearnerConceptStatus.COMPETENT.value:
        return "shorten or skip basic treatment unless needed as a prerequisite"
    return "use as learner context"
