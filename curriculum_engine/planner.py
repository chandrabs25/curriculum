"""LLM-assisted curriculum planning over retrieved textbook sections."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Protocol

from .learning_path import LearningPathContext, build_learning_path_context
from .models import CurriculumModule, CurriculumPlan, OnboardingAnswers
from .planning_packet import CurriculumPlanningPacket, build_curriculum_planning_packet
from .retrieval import CurriculumRetriever, LearnerConceptState, SectionRetrievalResult


class CurriculumLLMClient(Protocol):
    def generate_json(self, prompt: str, schema: dict[str, Any] | None = None) -> dict[str, Any]:
        """Return a JSON-compatible response for the curriculum planning prompt."""


CURRICULUM_PLAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "modules": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "module_id": {"type": "string"},
                    "module_goal": {"type": "string"},
                    "position": {"type": "integer"},
                    "depends_on_module_ids": {"type": "array", "items": {"type": "string"}},
                    "link_from_previous": {"type": "string"},
                    "link_to_next": {"type": "string"},
                    "source_section_ids": {"type": "array", "items": {"type": "string"}},
                    "prerequisite_warnings": {"type": "array", "items": {"type": "string"}},
                    "parallel_support_section_ids": {"type": "array", "items": {"type": "string"}},
                    "reinforcement_section_ids": {"type": "array", "items": {"type": "string"}},
                    "next_step_section_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "title",
                    "module_goal",
                    "position",
                    "source_section_ids",
                ],
            },
        }
    },
    "required": ["modules"],
}


@dataclass(frozen=True)
class PlannerRequest:
    learner_id: str
    onboarding: OnboardingAnswers
    learner_state: list[LearnerConceptState] | None = None
    prerequisite_check: dict[str, Any] | None = None
    subject: str | None = None
    grade: int | None = None
    chapter_id: str | None = None
    max_modules: int = 10
    retrieval_limit: int = 12


@dataclass
class CurriculumPlanner:
    retriever: CurriculumRetriever
    llm_client: CurriculumLLMClient

    def create_plan(self, request: PlannerRequest) -> CurriculumPlan:
        retrieved = self.retriever.search(
            request.onboarding.topic,
            subject=request.subject or _blank_to_none(request.onboarding.subject),
            grade=request.grade,
            chapter_id=request.chapter_id,
            learner_state=request.learner_state,
            limit=request.retrieval_limit,
            include_prerequisites=True,
        )
        learning_path_context = build_learning_path_context(
            self.retriever.graph,
            retrieved,
            learner_state=request.learner_state,
            prerequisite_check=request.prerequisite_check,
        )
        planning_packet = build_curriculum_planning_packet(
            request.onboarding,
            request.learner_state,
            retrieved,
            learning_path_context,
        )
        prompt = build_curriculum_prompt(planning_packet)
        payload = self.llm_client.generate_json(prompt, CURRICULUM_PLAN_SCHEMA)
        modules = modules_from_payload(
            payload,
            retrieved,
            planning_packet=planning_packet,
            retriever=self.retriever,
            max_modules=request.max_modules,
        )
        plan_id = stable_plan_id(request, modules)
        return CurriculumPlan(
            curriculum_plan_id=plan_id,
            learner_id=request.learner_id,
            onboarding=request.onboarding,
            modules=modules,
            created_at=datetime.now(timezone.utc),
            metadata={
                "retrieved_section_ids": [item.section_id for item in retrieved],
                "learning_path_context": learning_path_context.to_dict(),
                "planning_packet": planning_packet.to_dict(),
                "planner": "CurriculumPlanner",
            },
        )


def build_curriculum_prompt(planning_packet: CurriculumPlanningPacket) -> str:
    schema_example = {
        "modules": [
            {
                "module_id": "module:1",
                "title": "string",
                "module_goal": "string",
                "position": 1,
                "depends_on_module_ids": ["module:0"],
                "link_from_previous": "string",
                "link_to_next": "string",
                "source_section_ids": ["string"],
                "prerequisite_warnings": ["string"],
                "parallel_support_section_ids": ["string"],
                "reinforcement_section_ids": ["string"],
                "next_step_section_ids": ["string"],
            }
        ]
    }
    return f"""You are an AI curriculum planner.

The backend has already retrieved textbook sections, resolved section relationships, and classified relationships by purpose.

Relationship meanings:
- DEPENDS_ON_UNIT: required ordering. to_section_id must be studied before from_section_id.
- TRANSFER_SUPPORTS_UNIT: optional support bridge only.
- RELATED_BY_CONCEPT: reinforcement/comparison only.
- next_steps: after-completion recommendations only.

Planning packet:
{planning_packet.to_json()}

Now create the ordered curriculum module sequence.

Critical rules:
- Return JSON only.
- Use only section IDs present in planning_packet.
- Build required modules only from planning_packet.main_path_section_ids.
- Do not put optional support/reinforcement/next-step sections into source_section_ids.
- Use relationships.parallel_support only in parallel_support_section_ids or optional activities.
- Use relationships.reinforcement only in reinforcement_section_ids or review/practice recommendations.
- Use relationships.next_steps only in next_step_section_ids as after-completion suggestions.
- Respect DEPENDS_ON_UNIT hard dependency ordering.
- Use hard dependency evidence_reason to explain prerequisite warnings and ordering.
- Concepts are intentionally omitted from this first planner call except bridge_concept_id on section links.
- Do not produce concept IDs, activities, examples, exercises, milestones, detailed teaching content, or assessments.
- Make each module a coherent ordering unit for a later module-design LLM call.
- Put modules in the sequence the learner should follow.
- Explain why each module follows from the previous module and prepares the next module.
- Do not invent source ids, concept ids, examples, exercises, or relationships.

Required JSON shape:
{json.dumps(schema_example, ensure_ascii=False)}
"""


def modules_from_payload(
    payload: dict[str, Any],
    retrieved: list[SectionRetrievalResult],
    *,
    learning_path_context: LearningPathContext | None = None,
    planning_packet: CurriculumPlanningPacket | None = None,
    retriever: CurriculumRetriever | None = None,
    max_modules: int,
) -> list[CurriculumModule]:
    allowed_sections = {item.section_id for item in retrieved}
    main_path_sections = set(allowed_sections)
    parallel_support_sections: set[str] = set()
    reinforcement_sections: set[str] = set()
    next_step_sections: set[str] = set()
    if planning_packet:
        packet = planning_packet.to_dict()
        main_path_sections = set(packet.get("main_path_section_ids") or [])
        relationships = packet.get("relationships") or {}
        parallel_support_sections = _section_ids_from_rows(relationships.get("parallel_support") or [])
        reinforcement_sections = _section_ids_from_rows(relationships.get("reinforcement") or [])
        next_step_sections = _section_ids_from_rows(relationships.get("next_steps") or [])
        allowed_sections.update(main_path_sections)
        allowed_sections.update(parallel_support_sections)
        allowed_sections.update(reinforcement_sections)
        allowed_sections.update(next_step_sections)
    elif learning_path_context:
        context = learning_path_context.to_dict()
        main_path_sections = _section_ids_from_rows(context.get("main_path_sections") or [])
        parallel_support_sections = _section_ids_from_rows(context.get("parallel_support_paths") or [])
        reinforcement_sections = _section_ids_from_rows(context.get("reinforcement_paths") or [])
        next_step_sections = _section_ids_from_rows(context.get("next_step_paths") or [])
        allowed_sections.update(main_path_sections)
        allowed_sections.update(parallel_support_sections)
        allowed_sections.update(reinforcement_sections)
        allowed_sections.update(next_step_sections)
    modules: list[CurriculumModule] = []
    for index, item in enumerate(payload.get("modules", [])[:max_modules], 1):
        if not isinstance(item, dict):
            continue
        section_ids = [
            section_id
            for section_id in _str_list(item.get("source_section_ids"))
            if section_id in main_path_sections
        ]
        if not section_ids:
            continue
        module_id = str(item.get("module_id") or f"module:{index}")
        module = CurriculumModule(
            module_id=module_id,
            title=str(item.get("title") or f"Module {index}"),
            module_goal=str(item.get("module_goal") or f"Learn {item.get('title') or f'Module {index}'}"),
            position=max(1, int(item.get("position") or index)),
            covered_concept_ids=_covered_concepts_for_sections(retriever, section_ids),
            source_section_ids=section_ids,
            activities=["Design-stage activity pending."],
            recommended_examples=[],
            recommended_exercises=[],
            milestone="Complete the module design checkpoint.",
            expected_outcome=str(item.get("module_goal") or "Understand the ordered module section."),
            estimated_time_minutes=30,
            prerequisite_warnings=_str_list(item.get("prerequisite_warnings")),
            depends_on_module_ids=_str_list(item.get("depends_on_module_ids")),
            link_from_previous=str(item.get("link_from_previous") or ""),
            link_to_next=str(item.get("link_to_next") or ""),
            parallel_support_section_ids=[
                section_id
                for section_id in _str_list(item.get("parallel_support_section_ids"))
                if section_id in parallel_support_sections
            ],
            reinforcement_section_ids=[
                section_id
                for section_id in _str_list(item.get("reinforcement_section_ids"))
                if section_id in reinforcement_sections
            ],
            next_step_section_ids=[
                section_id
                for section_id in _str_list(item.get("next_step_section_ids"))
                if section_id in next_step_sections
            ],
            personalization_note=str(item.get("personalization_note") or ""),
        )
        modules.append(module)
    if modules:
        valid_module_ids = {module.module_id for module in modules}
        return [
            replace(
                module,
                depends_on_module_ids=[
                    module_id for module_id in module.depends_on_module_ids if module_id in valid_module_ids
                ],
            )
            for module in sorted(modules, key=lambda module: module.position)
        ]
    return fallback_modules(retrieved, max_modules=max_modules)


def fallback_modules(retrieved: list[SectionRetrievalResult], *, max_modules: int) -> list[CurriculumModule]:
    modules = []
    for index, item in enumerate(retrieved[:max_modules], 1):
        modules.append(
            CurriculumModule(
                module_id=f"module:{index}",
                title=item.title or f"Module {index}",
                module_goal=item.summary or f"Understand {item.title or item.section_id}.",
                position=index,
                covered_concept_ids=item.matched_concept_ids,
                source_section_ids=[item.section_id],
                activities=["Read the section, write a short summary, and solve a self-check question."],
                recommended_examples=[],
                recommended_exercises=[],
                milestone=f"Complete {item.title or item.section_id}.",
                expected_outcome=item.summary or "Understand the selected section.",
                estimated_time_minutes=30,
                prerequisite_warnings=[
                    f"Review prerequisite section {section_id} first."
                    for section_id in item.prerequisite_section_ids
                ],
                personalization_note=", ".join(item.reasons),
            )
        )
    return modules


def stable_plan_id(request: PlannerRequest, modules: list[CurriculumModule]) -> str:
    raw = json.dumps(
        {
            "learner_id": request.learner_id,
            "topic": request.onboarding.topic,
            "sections": [section_id for module in modules for section_id in module.source_section_ids],
        },
        sort_keys=True,
    )
    import hashlib

    return "curriculum_plan:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _blank_to_none(value: str) -> str | None:
    value = (value or "").strip()
    return value or None


def _str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _section_ids_from_rows(rows: list[dict[str, Any]]) -> set[str]:
    return {str(row.get("section_id")) for row in rows if row.get("section_id")}


def _covered_concepts_for_sections(retriever: CurriculumRetriever | None, section_ids: list[str]) -> list[str]:
    if not retriever:
        return []
    concept_ids: list[str] = []
    for section_id in section_ids:
        concept_ids.extend(retriever.graph.concepts_taught_by_section(section_id))
    seen = set()
    ordered = []
    for concept_id in concept_ids:
        if concept_id not in seen:
            seen.add(concept_id)
            ordered.append(concept_id)
    return ordered
