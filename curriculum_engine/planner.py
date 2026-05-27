"""LLM-assisted curriculum planning over retrieved textbook sections."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from .learning_path import LearningPathContext, build_learning_path_context
from .models import CurriculumModule, CurriculumPlan, OnboardingAnswers
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
                    "covered_concept_ids": {"type": "array", "items": {"type": "string"}},
                    "source_section_ids": {"type": "array", "items": {"type": "string"}},
                    "activities": {"type": "array", "items": {"type": "string"}},
                    "recommended_examples": {"type": "array", "items": {"type": "string"}},
                    "recommended_exercises": {"type": "array", "items": {"type": "string"}},
                    "milestone": {"type": "string"},
                    "expected_outcome": {"type": "string"},
                    "estimated_time_minutes": {"type": "integer"},
                    "prerequisite_warnings": {"type": "array", "items": {"type": "string"}},
                    "parallel_support_section_ids": {"type": "array", "items": {"type": "string"}},
                    "reinforcement_section_ids": {"type": "array", "items": {"type": "string"}},
                    "next_step_section_ids": {"type": "array", "items": {"type": "string"}},
                    "personalization_note": {"type": "string"},
                },
                "required": [
                    "title",
                    "covered_concept_ids",
                    "source_section_ids",
                    "activities",
                    "milestone",
                    "expected_outcome",
                    "estimated_time_minutes",
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
    max_modules: int = 6
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
        prompt = build_curriculum_prompt(request, retrieved, learning_path_context)
        payload = self.llm_client.generate_json(prompt, CURRICULUM_PLAN_SCHEMA)
        modules = modules_from_payload(
            payload,
            retrieved,
            learning_path_context=learning_path_context,
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
                "planner": "CurriculumPlanner",
            },
        )


def build_curriculum_prompt(
    request: PlannerRequest,
    retrieved: list[SectionRetrievalResult],
    learning_path_context: LearningPathContext,
) -> str:
    learner_state = [
        {
            "concept_id": state.concept_id,
            "status": str(state.status.value if hasattr(state.status, "value") else state.status),
            "confidence": state.confidence,
            "recency_weight": state.recency_weight,
        }
        for state in request.learner_state or []
    ]
    context = {
        "onboarding": {
            "subject": request.onboarding.subject,
            "topic": request.onboarding.topic,
            "current_level": request.onboarding.current_level,
            "confidence": request.onboarding.confidence,
            "learning_goal": request.onboarding.learning_goal,
            "available_time": request.onboarding.available_time,
            "preferred_learning_style": request.onboarding.preferred_learning_style,
            "deadline_or_pace": request.onboarding.deadline_or_pace,
        },
        "learner_state": learner_state,
        "learning_path_context": learning_path_context.to_dict(),
        "retrieved_sections": [
            {
                "section_id": item.section_id,
                "chapter_id": item.chapter_id,
                "title": item.title,
                "summary": item.summary,
                "matched_concept_ids": item.matched_concept_ids,
                "prerequisite_section_ids": item.prerequisite_section_ids,
                "retrieval_reasons": item.reasons,
                "score": item.score,
            }
            for item in retrieved
        ],
        "max_modules": request.max_modules,
    }
    return f"""Create a personalized curriculum plan from the grounded textbook sections.

Rules:
- Use only source_section_ids from retrieved_sections and learning_path_context sections.
- Build required modules only from learning_path_context.main_path_sections.
- Hard dependency edges affect order: to_section_id should be studied before from_section_id.
- Required concepts explain prerequisite warnings; use their pedagogical_reason when explaining foundations.
- Teaching evidence explains what each section contributes; use it to keep module outcomes grounded.
- Use parallel_support_paths only in parallel_support_section_ids or optional activities.
- Use reinforcement_paths only in reinforcement_section_ids or review/practice recommendations.
- Use next_step_paths only in next_step_section_ids as after-completion suggestions.
- Never treat RELATED_BY_CONCEPT or TRANSFER_SUPPORTS_UNIT as hard prerequisites.
- Keep modules small and teachable.
- Personalize using learner_state: misconceptions need remediation, partial understanding needs practice, competencies can move faster.
- Do not invent source ids or concept ids.
- Recommended examples/exercises may be empty because exercise mapping is deferred.
- Return JSON matching the schema.

Planning context:
{json.dumps(context, ensure_ascii=False)}
"""


def modules_from_payload(
    payload: dict[str, Any],
    retrieved: list[SectionRetrievalResult],
    *,
    learning_path_context: LearningPathContext | None = None,
    max_modules: int,
) -> list[CurriculumModule]:
    allowed_sections = {item.section_id for item in retrieved}
    main_path_sections = set(allowed_sections)
    parallel_support_sections: set[str] = set()
    reinforcement_sections: set[str] = set()
    next_step_sections: set[str] = set()
    if learning_path_context:
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
        module = CurriculumModule(
            module_id=f"module:{index}",
            title=str(item.get("title") or f"Module {index}"),
            covered_concept_ids=_str_list(item.get("covered_concept_ids")),
            source_section_ids=section_ids,
            activities=_str_list(item.get("activities")) or ["Read the source section and summarize the key ideas."],
            recommended_examples=_str_list(item.get("recommended_examples")),
            recommended_exercises=_str_list(item.get("recommended_exercises")),
            milestone=str(item.get("milestone") or "Complete the module checkpoint."),
            expected_outcome=str(item.get("expected_outcome") or "Explain the module concepts in your own words."),
            estimated_time_minutes=max(5, int(item.get("estimated_time_minutes") or 30)),
            prerequisite_warnings=_str_list(item.get("prerequisite_warnings")),
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
        return modules
    return fallback_modules(retrieved, max_modules=max_modules)


def fallback_modules(retrieved: list[SectionRetrievalResult], *, max_modules: int) -> list[CurriculumModule]:
    modules = []
    for index, item in enumerate(retrieved[:max_modules], 1):
        modules.append(
            CurriculumModule(
                module_id=f"module:{index}",
                title=item.title or f"Module {index}",
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
