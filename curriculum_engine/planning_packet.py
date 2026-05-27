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
            "matched_concept_ids": item.matched_concept_ids,
        }
        for item in retrieved
    }

    for row in ctx.get("main_path_sections", []):
        _add_section(sections_by_id, row, retrieved_by_id)
    for row in ctx.get("support_sections", []):
        _add_section(sections_by_id, row, retrieved_by_id)

    for row in ctx.get("hard_dependency_edges", []):
        relationships["hard_dependencies"].append(_section_link_row(row))

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
        "main_path_section_ids": [row["section_id"] for row in ctx.get("main_path_sections", []) if row.get("section_id")],
        "relationships": relationships,
        "relationship_policy": ctx.get("relationship_policy") or {},
    }
    packet["budget"] = _budget(packet, trimmed=False)
    if packet["budget"]["estimated_chars"] > HARD_CAP_CHARS:
        _trim_to_budget(packet)
    packet["budget"] = _budget(packet, trimmed=packet.get("budget", {}).get("trimmed", False))
    return CurriculumPlanningPacket(packet)


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


def _budget(packet: dict[str, Any], *, trimmed: bool) -> dict[str, Any]:
    return {
        "estimated_chars": len(json.dumps(packet, ensure_ascii=False)),
        "target_chars": TARGET_CHARS,
        "hard_cap_chars": HARD_CAP_CHARS,
        "trimmed": trimmed,
    }


def _trim_to_budget(packet: dict[str, Any]) -> None:
    relationships = packet.get("relationships") or {}
    for bucket_name in ("reinforcement", "parallel_support", "cross_chapter_bridges", "next_steps"):
        bucket = relationships.get(bucket_name) or []
        while len(json.dumps(packet, ensure_ascii=False)) > HARD_CAP_CHARS and bucket:
            bucket.pop()
            packet["budget"] = _budget(packet, trimmed=True)
