"""Compact LLM planning packet for curriculum generation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .learning_path import LearningPathContext
from .models import OnboardingAnswers
from .retrieval import LearnerConceptState, LearnerConceptStatus, SectionRetrievalResult


SUMMARY_LIMIT = 420
REASON_LIMIT = 320
EVIDENCE_LIMIT = 260
PARALLEL_SUPPORT_CAP = 5
REINFORCEMENT_CAP = 5
NEXT_STEPS_CAP = 5
CROSS_CHAPTER_CAP = 5
TARGET_CHARS = 25_000
HARD_CAP_CHARS = 40_000
BROAD_SECTION_THRESHOLD = 10
TOP_RANKED_TARGET_LIMIT = 6


@dataclass(frozen=True)
class CurriculumPlanningPacket:
    data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return self.data

    def to_json(self) -> str:
        return json.dumps(self.data, ensure_ascii=False)


def build_curriculum_planning_packet(
    onboarding: OnboardingAnswers,
    learner_state: list[LearnerConceptState] | None,
    retrieved: list[SectionRetrievalResult],
    learning_path_context: LearningPathContext,
) -> CurriculumPlanningPacket:
    ctx = learning_path_context.to_dict()
    sections_by_id: dict[str, dict[str, Any]] = {}
    relationships = {
        "hard_dependencies": [],
        "parallel_support": [],
        "reinforcement": [],
        "next_steps": [],
        "cross_chapter_bridges": [],
    }

    retrieved_by_id = {
        item.section_id: {
            "score": item.score,
            "retrieval_reasons": item.reasons,
        }
        for item in retrieved
    }
    broad_selection = _broad_selection(ctx, retrieved_by_id)

    for row in _selected_main_path_rows(ctx, broad_selection):
        _add_section(sections_by_id, row, retrieved_by_id)
    if not broad_selection["active"]:
        for row in ctx.get("support_sections", []):
            _add_section(sections_by_id, row, retrieved_by_id)

    for row in _selected_hard_dependency_edges(ctx, broad_selection):
        relationships["hard_dependencies"].append(_section_link_row(row))

    if not broad_selection["active"]:
        _add_recommendation_bucket(
            relationships["parallel_support"],
            sections_by_id,
            ctx.get("parallel_support_paths", []),
            PARALLEL_SUPPORT_CAP,
            retrieved_by_id,
        )
        _add_recommendation_bucket(
            relationships["reinforcement"],
            sections_by_id,
            ctx.get("reinforcement_paths", []),
            REINFORCEMENT_CAP,
            retrieved_by_id,
        )
        _add_recommendation_bucket(
            relationships["next_steps"],
            sections_by_id,
            ctx.get("next_step_paths", []),
            NEXT_STEPS_CAP,
            retrieved_by_id,
        )
        _add_recommendation_bucket(
            relationships["cross_chapter_bridges"],
            sections_by_id,
            ctx.get("cross_chapter_bridges", []),
            CROSS_CHAPTER_CAP,
            retrieved_by_id,
        )

    packet = {
        "onboarding": _onboarding_row(onboarding),
        "learner_state": _learner_state_rows(learner_state or []),
        "prerequisite_check": ctx.get("prerequisite_check") or {"asked": False, "answers": []},
        "sections_by_id": dict(sorted(sections_by_id.items())),
        "main_path_section_ids": [
            row["section_id"]
            for row in _selected_main_path_rows(ctx, broad_selection)
            if row.get("section_id")
        ],
        "relationships": relationships,
        "relationship_policy": _planner_relationship_policy(ctx.get("relationship_policy") or {}),
    }
    packet["budget"] = _budget(packet, trimmed=broad_selection["active"], broad_selection=broad_selection)
    if packet["budget"]["estimated_chars"] > HARD_CAP_CHARS:
        _trim_to_budget(packet)
    packet["budget"] = _budget(
        packet,
        trimmed=packet.get("budget", {}).get("trimmed", False) or broad_selection["active"],
        broad_selection=broad_selection,
    )
    return CurriculumPlanningPacket(packet)


def _broad_selection(
    ctx: dict[str, Any],
    retrieved_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    all_section_ids = _context_section_ids(ctx)
    if len(all_section_ids) <= BROAD_SECTION_THRESHOLD:
        return {
            "active": False,
            "input_section_count": len(all_section_ids),
            "selected_target_section_ids": [
                row["section_id"] for row in ctx.get("target_sections", []) if row.get("section_id")
            ],
            "selected_prerequisite_section_ids": [
                row["section_id"] for row in ctx.get("prerequisite_sections", []) if row.get("section_id")
            ],
        }
    target_rows = [row for row in ctx.get("target_sections", []) if row.get("section_id")]
    ranked_targets = _ranked_section_rows(target_rows, retrieved_by_id)
    selected_target_ids = [row["section_id"] for row in ranked_targets[:TOP_RANKED_TARGET_LIMIT]]
    selected_prereq_ids = _hard_prerequisite_ids_for_targets(ctx, set(selected_target_ids))
    return {
        "active": True,
        "input_section_count": len(all_section_ids),
        "broad_section_threshold": BROAD_SECTION_THRESHOLD,
        "selected_target_limit": TOP_RANKED_TARGET_LIMIT,
        "selected_target_section_ids": selected_target_ids,
        "selected_prerequisite_section_ids": selected_prereq_ids,
    }


def _context_section_ids(ctx: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for bucket_name in (
        "main_path_sections",
        "target_sections",
        "prerequisite_sections",
        "support_sections",
        "parallel_support_paths",
        "reinforcement_paths",
        "next_step_paths",
        "cross_chapter_bridges",
    ):
        for row in ctx.get(bucket_name, []):
            section_id = row.get("section_id")
            if section_id:
                ids.add(section_id)
    for row in ctx.get("hard_dependency_edges", []):
        from_id = row.get("from_section_id")
        to_id = row.get("to_section_id")
        if from_id:
            ids.add(from_id)
        if to_id:
            ids.add(to_id)
    return ids


def _ranked_section_rows(
    rows: list[dict[str, Any]],
    retrieved_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    indexed_rows = list(enumerate(rows))
    return [
        row
        for _, row in sorted(
            indexed_rows,
            key=lambda item: (-_section_score(item[1], retrieved_by_id), item[0]),
        )
    ]


def _section_score(row: dict[str, Any], retrieved_by_id: dict[str, dict[str, Any]]) -> float:
    section_id = row.get("section_id")
    retrieved_score = retrieved_by_id.get(section_id, {}).get("score") if section_id else None
    if retrieved_score is not None:
        return float(retrieved_score)
    return float(row.get("score") or 0.0)


def _hard_prerequisite_ids_for_targets(ctx: dict[str, Any], selected_target_ids: set[str]) -> list[str]:
    prereq_ids = {
        str(row.get("to_section_id") or "")
        for row in ctx.get("hard_dependency_edges", [])
        if row.get("from_section_id") in selected_target_ids and row.get("to_section_id")
    }
    ordered = []
    for row in ctx.get("prerequisite_sections", []):
        section_id = row.get("section_id")
        if section_id in prereq_ids and section_id not in ordered:
            ordered.append(section_id)
    return ordered


def _selected_main_path_rows(ctx: dict[str, Any], broad_selection: dict[str, Any]) -> list[dict[str, Any]]:
    if not broad_selection["active"]:
        return list(ctx.get("main_path_sections", []))
    selected_prereq_ids = set(broad_selection.get("selected_prerequisite_section_ids") or [])
    selected_target_ids = broad_selection.get("selected_target_section_ids") or []
    prereq_rows = [
        row
        for row in ctx.get("prerequisite_sections", [])
        if row.get("section_id") in selected_prereq_ids
    ]
    target_by_id = {
        row.get("section_id"): row
        for row in ctx.get("target_sections", [])
        if row.get("section_id")
    }
    target_rows = [target_by_id[section_id] for section_id in selected_target_ids if section_id in target_by_id]
    return prereq_rows + target_rows


def _selected_hard_dependency_edges(ctx: dict[str, Any], broad_selection: dict[str, Any]) -> list[dict[str, Any]]:
    if not broad_selection["active"]:
        return list(ctx.get("hard_dependency_edges", []))
    selected_ids = set(broad_selection.get("selected_target_section_ids") or [])
    selected_ids.update(broad_selection.get("selected_prerequisite_section_ids") or [])
    return [
        row
        for row in ctx.get("hard_dependency_edges", [])
        if row.get("from_section_id") in selected_ids and row.get("to_section_id") in selected_ids
    ]


def _planner_relationship_policy(policy: dict[str, str]) -> dict[str, str]:
    return {
        key: value
        for key, value in policy.items()
        if key not in {"required_concepts", "teaches_concepts"}
    }


def _add_section(
    sections_by_id: dict[str, dict[str, Any]],
    row: dict[str, Any],
    retrieved_by_id: dict[str, dict[str, Any]],
) -> None:
    section_id = row.get("section_id")
    if not section_id or section_id in sections_by_id:
        return
    sections_by_id[section_id] = {
        "section_id": section_id,
        "chapter_id": row.get("chapter_id") or "",
        "title": row.get("title") or "",
        "summary": _compact(row.get("summary"), SUMMARY_LIMIT),
        "role": row.get("role") or "",
        **retrieved_by_id.get(section_id, {}),
    }


def _section_link_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "relationship_id": row.get("relationship_id"),
        "relationship_type": row.get("type") or row.get("relationship_type"),
        "from_section_id": row.get("from_section_id"),
        "to_section_id": row.get("to_section_id"),
        "bridge_concept_id": row.get("bridge_concept_id"),
        "confidence": row.get("confidence"),
        "evidence_text": _compact(row.get("evidence_text"), EVIDENCE_LIMIT),
        "evidence_reason": _compact(row.get("evidence_reason"), REASON_LIMIT),
        "planning_meaning": row.get("planning_meaning") or row.get("use_as") or "",
    }


def _add_recommendation_bucket(
    bucket: list[dict[str, Any]],
    sections_by_id: dict[str, dict[str, Any]],
    rows: list[dict[str, Any]],
    cap: int,
    retrieved_by_id: dict[str, dict[str, Any]],
) -> None:
    for row in _top_by_confidence(rows, cap):
        _add_section(sections_by_id, {**row, "role": "optional"}, retrieved_by_id)
        bucket.append(
            {
                "relationship_id": row.get("relationship_id"),
                "relationship_type": row.get("relationship_type"),
                "section_id": row.get("section_id"),
                "source_target_section_id": row.get("source_target_section_id"),
                "bridge_concept_id": row.get("bridge_concept_id"),
                "confidence": row.get("confidence"),
                "evidence_text": _compact(row.get("evidence_text"), EVIDENCE_LIMIT),
                "planning_meaning": row.get("planning_meaning") or "",
                "use_as": row.get("use_as") or "",
            }
        )


def _top_by_confidence(rows: list[dict[str, Any]], cap: int) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: float(row.get("confidence") or 0.0), reverse=True)[:cap]


def _compact(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _onboarding_row(onboarding: OnboardingAnswers) -> dict[str, Any]:
    return {
        "subject": onboarding.subject,
        "topic": onboarding.topic,
        "current_level": onboarding.current_level,
        "confidence": onboarding.confidence,
        "learning_goal": onboarding.learning_goal,
        "available_time": onboarding.available_time,
        "preferred_learning_style": onboarding.preferred_learning_style,
        "deadline_or_pace": onboarding.deadline_or_pace,
    }


def _learner_state_rows(learner_state: list[LearnerConceptState]) -> list[dict[str, Any]]:
    rows = []
    for state in learner_state:
        status = state.status.value if isinstance(state.status, LearnerConceptStatus) else str(state.status)
        rows.append(
            {
                "concept_id": state.concept_id,
                "status": status,
                "confidence": state.confidence,
                "recency_weight": state.recency_weight,
            }
        )
    return rows


def _budget(
    packet: dict[str, Any],
    *,
    trimmed: bool,
    broad_selection: dict[str, Any] | None = None,
) -> dict[str, Any]:
    budget = {
        "estimated_chars": len(json.dumps(packet, ensure_ascii=False)),
        "target_chars": TARGET_CHARS,
        "hard_cap_chars": HARD_CAP_CHARS,
        "trimmed": trimmed,
        "sent_section_count": len(packet.get("sections_by_id") or {}),
    }
    if broad_selection:
        budget.update(
            {
                "broad_section_selection": bool(broad_selection.get("active")),
                "input_section_count": broad_selection.get("input_section_count", 0),
                "selected_target_limit": broad_selection.get("selected_target_limit"),
                "selected_target_section_count": len(broad_selection.get("selected_target_section_ids") or []),
                "selected_prerequisite_section_count": len(
                    broad_selection.get("selected_prerequisite_section_ids") or []
                ),
            }
        )
    return budget


def _trim_to_budget(packet: dict[str, Any]) -> None:
    relationships = packet.get("relationships") or {}
    for bucket_name in ("reinforcement", "parallel_support", "cross_chapter_bridges", "next_steps"):
        bucket = relationships.get(bucket_name) or []
        while len(json.dumps(packet, ensure_ascii=False)) > HARD_CAP_CHARS and bucket:
            bucket.pop()
            packet["budget"] = _budget(packet, trimmed=True)
