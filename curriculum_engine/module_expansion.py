"""Compact module design packets and prompts for planned curriculum modules."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from .artifacts import ArtifactStore, TextbookStore
from .graph import CurriculumGraph
from .models import (
    CurriculumPlan,
    ExpandedCurriculumModule,
    ModuleCheckpointMCQ,
    OnboardingAnswers,
    PlannedCurriculumModule,
)
from .retrieval import LearnerConceptState, LearnerConceptStatus


class ModuleExpansionLLMClient(Protocol):
    def generate_json(self, prompt: str, schema: dict[str, Any] | None = None) -> dict[str, Any]:
        """Return a JSON-compatible response for a module design prompt."""


MODULE_EXPANSION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "module_goal": {"type": "string"},
        "larger_goal_alignment": {"type": "string"},
        "transition_from_previous": {"type": "string"},
        "transition_to_next": {"type": "string"},
        "lesson_sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "heading": {"type": "string"},
                    "body": {"type": "string"},
                    "source_section_ids": {"type": "array", "items": {"type": "string"}},
                    "concept_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["heading", "body", "source_section_ids"],
            },
        },
        "guided_activity": {"type": "string"},
        "common_misconceptions": {"type": "array", "items": {"type": "string"}},
        "checkpoint_mcq": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "options": {"type": "array", "items": {"type": "string"}},
                "correct_option": {"type": "string"},
                "explanation": {"type": "string"},
                "tested_concept_ids": {"type": "array", "items": {"type": "string"}},
                "source_section_ids": {"type": "array", "items": {"type": "string"}},
            },
            "required": [
                "question",
                "options",
                "correct_option",
                "explanation",
                "tested_concept_ids",
                "source_section_ids",
            ],
        },
    },
    "required": [
        "title",
        "module_goal",
        "larger_goal_alignment",
        "lesson_sections",
        "guided_activity",
        "checkpoint_mcq",
    ],
}


@dataclass(frozen=True)
class ModuleExpansionPacket:
    data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return self.data

    def to_json(self) -> str:
        return json.dumps(self.data, ensure_ascii=False)


@dataclass
class ModuleExpander:
    textbook_store: TextbookStore | CurriculumGraph
    llm_client: ModuleExpansionLLMClient

    def expand_module(
        self,
        plan: CurriculumPlan,
        module_id: str,
        *,
        learner_state: list[LearnerConceptState] | None = None,
    ) -> ExpandedCurriculumModule:
        module = _module_by_id(plan, module_id)
        packet = build_module_expansion_packet(
            self.textbook_store,
            plan,
            module,
            learner_state=learner_state,
        )
        prompt = build_module_expansion_prompt(packet)
        payload = self.llm_client.generate_json(prompt, MODULE_EXPANSION_SCHEMA)
        return expanded_module_from_payload(payload, module, packet)


def build_module_expansion_packet(
    textbook_store: TextbookStore | CurriculumGraph,
    plan: CurriculumPlan,
    module: PlannedCurriculumModule,
    *,
    learner_state: list[LearnerConceptState] | None = None,
) -> ModuleExpansionPacket:
    graph = _as_graph(textbook_store)
    previous_module = _neighbor_module(plan, module.position - 1)
    next_module = _neighbor_module(plan, module.position + 1)
    planning_packet = plan.metadata.get("planning_packet") or {}
    packet = {
        "source_mode": "summary",
        "onboarding": _onboarding_row(plan.onboarding),
        "learner_state": _learner_state_rows(learner_state or []),
        "module": _module_row(module),
        "previous_module": _compact_module_row(previous_module),
        "next_module": _compact_module_row(next_module),
        "relationship_reasoning": _relationship_reasoning_for_module(planning_packet, module),
        "target_concepts": _target_concept_rows(graph, module, planning_packet),
        "source_sections": [_summary_section_row(graph, section_id) for section_id in module.source_section_ids],
    }
    packet["budget"] = {"estimated_chars": len(json.dumps(packet, ensure_ascii=False))}
    return ModuleExpansionPacket(packet)


def fetch_full_source_sections(
    textbook_store: TextbookStore | CurriculumGraph,
    section_ids: list[str],
) -> list[dict[str, Any]]:
    graph = _as_graph(textbook_store)
    return [_full_source_section_row(graph.textbooks.get_section(section_id)) for section_id in section_ids]


def build_module_expansion_prompt(packet: ModuleExpansionPacket) -> str:
    schema_example = {
        "title": "string",
        "module_goal": "string",
        "larger_goal_alignment": "string",
        "transition_from_previous": "string",
        "transition_to_next": "string",
        "lesson_sections": [
            {
                "heading": "string",
                "body": "string",
                "source_section_ids": ["string"],
                "concept_ids": ["string"],
            }
        ],
        "guided_activity": "string",
        "common_misconceptions": ["string"],
        "checkpoint_mcq": {
            "question": "string",
            "options": ["A. string", "B. string", "C. string", "D. string"],
            "correct_option": "A",
            "explanation": "string",
            "tested_concept_ids": ["string"],
            "source_section_ids": ["string"],
        },
    }
    return f"""You are designing one planned curriculum module into learner-facing structure.

The planner has already chosen the module order. Your job is to design this module using compact summaries, target concepts, relationship reasoning, learner preferences, and the larger learning goal.

Module design packet:
{packet.to_json()}

Now design the module.

Critical rules:
- Return JSON only.
- Use only source section IDs and concept IDs present in the module design packet.
- Treat source_sections as summaries, not full textbook text.
- Ground explanations and the checkpoint MCQ draft in source summaries, target concepts, and relationship reasoning.
- Explain how this module serves onboarding.topic and onboarding.learning_goal.
- Explain how this module connects from the previous module and prepares the next module when those modules exist.
- Create exactly one checkpoint_mcq draft with four options.
- The MCQ is a lightweight module checkpoint draft, not a final source-verified assessment item.
- Do not invent source sections, concepts, textbook facts, or final assessment claims.

Required JSON shape:
{json.dumps(schema_example, ensure_ascii=False)}
"""


def expanded_module_from_payload(
    payload: dict[str, Any],
    module: PlannedCurriculumModule,
    packet: ModuleExpansionPacket,
) -> ExpandedCurriculumModule:
    packet_data = packet.to_dict()
    allowed_sections = {section["section_id"] for section in packet_data.get("source_sections", [])}
    allowed_concepts = {
        str(row.get("concept_id"))
        for row in packet_data.get("target_concepts", [])
        if row.get("concept_id")
    }
    lesson_sections = []
    for row in payload.get("lesson_sections", []):
        if not isinstance(row, dict):
            continue
        source_section_ids = [section_id for section_id in _str_list(row.get("source_section_ids")) if section_id in allowed_sections]
        if not source_section_ids:
            source_section_ids = list(module.source_section_ids)
        lesson_sections.append(
            {
                "heading": str(row.get("heading") or "Lesson"),
                "body": str(row.get("body") or ""),
                "source_section_ids": source_section_ids,
                "concept_ids": [concept_id for concept_id in _str_list(row.get("concept_ids")) if concept_id in allowed_concepts],
            }
        )
    mcq_payload = payload.get("checkpoint_mcq") if isinstance(payload.get("checkpoint_mcq"), dict) else {}
    options = _str_list(mcq_payload.get("options"))[:4]
    mcq = ModuleCheckpointMCQ(
        question=str(mcq_payload.get("question") or "Which statement best matches the module content?"),
        options=options,
        correct_option=str(mcq_payload.get("correct_option") or (options[0][:1] if options else "A")),
        explanation=str(mcq_payload.get("explanation") or ""),
        tested_concept_ids=[concept_id for concept_id in _str_list(mcq_payload.get("tested_concept_ids")) if concept_id in allowed_concepts],
        source_section_ids=[
            section_id for section_id in _str_list(mcq_payload.get("source_section_ids")) if section_id in allowed_sections
        ]
        or list(module.source_section_ids),
    )
    return ExpandedCurriculumModule(
        module_id=module.module_id,
        title=str(payload.get("title") or module.title),
        module_goal=str(payload.get("module_goal") or module.module_goal),
        source_section_ids=module.source_section_ids,
        concept_ids=module.covered_concept_ids,
        larger_goal_alignment=str(payload.get("larger_goal_alignment") or ""),
        transition_from_previous=str(payload.get("transition_from_previous") or module.link_from_previous),
        transition_to_next=str(payload.get("transition_to_next") or module.link_to_next),
        lesson_sections=lesson_sections,
        guided_activity=str(payload.get("guided_activity") or ""),
        common_misconceptions=_str_list(payload.get("common_misconceptions")),
        checkpoint_mcq=mcq,
        metadata={"module_expansion_packet": packet_data, "source_mode": packet_data.get("source_mode")},
    )


def _as_graph(textbook_store: TextbookStore | CurriculumGraph) -> CurriculumGraph:
    if isinstance(textbook_store, CurriculumGraph):
        return textbook_store
    return CurriculumGraph(textbook_store, ArtifactStore(textbook_store.root))


def _module_by_id(plan: CurriculumPlan, module_id: str) -> PlannedCurriculumModule:
    for module in plan.modules:
        if module.module_id == module_id:
            return module
    raise KeyError(f"Unknown module_id: {module_id}")


def _neighbor_module(plan: CurriculumPlan, position: int) -> PlannedCurriculumModule | None:
    for module in plan.modules:
        if module.position == position:
            return module
    return None


def _module_row(module: PlannedCurriculumModule) -> dict[str, Any]:
    return {
        "module_id": module.module_id,
        "title": module.title,
        "module_goal": module.module_goal,
        "position": module.position,
        "covered_concept_ids": module.covered_concept_ids,
        "source_section_ids": module.source_section_ids,
        "depends_on_module_ids": module.depends_on_module_ids,
        "link_from_previous": module.link_from_previous,
        "link_to_next": module.link_to_next,
        "prerequisite_warnings": module.prerequisite_warnings,
        "personalization_note": module.personalization_note,
    }


def _compact_module_row(module: PlannedCurriculumModule | None) -> dict[str, Any] | None:
    if not module:
        return None
    return {
        "module_id": module.module_id,
        "title": module.title,
        "module_goal": module.module_goal,
        "source_section_ids": module.source_section_ids,
        "covered_concept_ids": module.covered_concept_ids,
        "link_from_previous": module.link_from_previous,
        "link_to_next": module.link_to_next,
    }


def _relationship_reasoning_for_module(
    planning_packet: dict[str, Any],
    module: PlannedCurriculumModule,
) -> dict[str, Any]:
    relationships = planning_packet.get("relationships") or {}
    source_sections = set(module.source_section_ids)
    concept_ids = set(module.covered_concept_ids)
    return {
        "requires_concept": [
            row
            for row in relationships.get("requires_concept", [])
            if row.get("from_section_id") in source_sections or row.get("to_concept_id") in concept_ids
        ],
        "teaches_concept": [
            row
            for row in relationships.get("teaches_concept", [])
            if row.get("from_section_id") in source_sections or row.get("to_concept_id") in concept_ids
        ],
        "hard_dependencies": [
            row
            for row in relationships.get("hard_dependencies", [])
            if row.get("from_section_id") in source_sections or row.get("to_section_id") in source_sections
        ],
        "parallel_support": [
            row for row in relationships.get("parallel_support", []) if row.get("section_id") in module.parallel_support_section_ids
        ],
        "reinforcement": [
            row for row in relationships.get("reinforcement", []) if row.get("section_id") in module.reinforcement_section_ids
        ],
        "next_steps": [
            row for row in relationships.get("next_steps", []) if row.get("section_id") in module.next_step_section_ids
        ],
    }


def _target_concept_rows(
    graph: CurriculumGraph,
    module: PlannedCurriculumModule,
    planning_packet: dict[str, Any],
) -> list[dict[str, Any]]:
    concepts_by_id = planning_packet.get("concepts_by_id") or {}
    details_by_concept: dict[str, dict[str, Any]] = {}
    for section_id in module.source_section_ids:
        for detail in graph.teaches_concept_details(section_id):
            concept_id = detail.get("concept_id")
            if concept_id:
                details_by_concept.setdefault(concept_id, {}).update({"teaching_evidence": detail.get("teaching_evidence")})
                details_by_concept[concept_id].setdefault("label", detail.get("label"))
        for detail in graph.requires_concept_details(section_id):
            concept_id = detail.get("concept_id")
            if concept_id:
                details_by_concept.setdefault(concept_id, {}).update({"pedagogical_reason": detail.get("pedagogical_reason")})
                details_by_concept[concept_id].setdefault("label", detail.get("label"))
    rows = []
    for concept_id in _dedupe(
        module.covered_concept_ids
        + list(details_by_concept)
        + [row.get("to_concept_id") for row in _relationship_reasoning_for_module(planning_packet, module).get("teaches_concept", []) if row.get("to_concept_id")]
        + [row.get("to_concept_id") for row in _relationship_reasoning_for_module(planning_packet, module).get("requires_concept", []) if row.get("to_concept_id")]
    ):
        concept = graph.concepts_by_id.get(concept_id) or concepts_by_id.get(concept_id) or {}
        rows.append(
            {
                "concept_id": concept_id,
                "label": concept.get("canonical_label") or details_by_concept.get(concept_id, {}).get("label") or concept.get("label") or concept.get("normalized_label") or concept_id,
                "teaching_evidence": details_by_concept.get(concept_id, {}).get("teaching_evidence") or "",
                "pedagogical_reason": details_by_concept.get(concept_id, {}).get("pedagogical_reason") or "",
            }
        )
    return rows


def _summary_section_row(graph: CurriculumGraph, section_id: str) -> dict[str, Any]:
    summary = graph.section_summaries_by_id.get(section_id, {})
    section = graph.sections_by_id.get(section_id, {})
    return {
        "section_id": section_id,
        "chapter_id": summary.get("chapter_id") or section.get("chapter_id"),
        "section_number": summary.get("section_number") or section.get("number"),
        "title": summary.get("title") or section.get("title") or "",
        "summary": summary.get("summary") or "",
        "key_terms": summary.get("key_terms") or [],
        "candidate_concept_ids": summary.get("candidate_concept_ids") or [],
        "covered_subsection_ids": summary.get("covered_subsection_ids") or [],
        "resource_counts": _resource_counts(section),
    }


def _resource_counts(section: dict[str, Any]) -> dict[str, int]:
    subsections = section.get("subsections") or []
    return {
        "subsections": len(subsections),
        "worked_examples": len(section.get("worked_examples") or [])
        + sum(len(row.get("worked_examples") or []) for row in subsections),
        "diagrams": len(section.get("diagrams") or []) + sum(len(row.get("diagrams") or []) for row in subsections),
        "tables": len(section.get("tables") or []) + sum(len(row.get("tables") or []) for row in subsections),
    }


def _full_source_section_row(section: dict[str, Any]) -> dict[str, Any]:
    return {
        "section_id": section.get("id"),
        "chapter_id": section.get("chapter_id"),
        "subject": section.get("subject"),
        "grade": section.get("grade"),
        "section_number": section.get("number"),
        "title": section.get("title"),
        "content_text": section.get("content_text") or "",
        "worked_examples": section.get("worked_examples") or [],
        "diagrams": section.get("diagrams") or [],
        "tables": section.get("tables") or [],
        "subsections": [_subsection_row(row) for row in section.get("subsections", [])],
    }


def _subsection_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "subsection_id": row.get("id"),
        "title": row.get("title"),
        "content_type": row.get("content_type"),
        "content_text": row.get("content_text") or "",
        "worked_examples": row.get("worked_examples") or [],
        "diagrams": row.get("diagrams") or [],
        "tables": row.get("tables") or [],
    }


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
                "last_seen_at": state.last_seen_at.isoformat() if state.last_seen_at else None,
            }
        )
    return rows


def _str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    ordered = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered
