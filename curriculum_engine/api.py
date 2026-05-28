"""FastAPI surface for the current curriculum creator workflow."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .artifacts import ArtifactStore, TextbookStore
from .graph import CurriculumGraph
from .intent import INTENT_OUTPUT_MAX_TOKENS, IntentClassifier
from .learning_path import build_learning_path_context
from .llm_clients import FIREWORKS_GPT_OSS_120B, FireworksLLMClient
from .models import CurriculumPlan, OnboardingAnswers, PlannedCurriculumModule
from .module_expansion import ModuleExpander, allocate_module_mcq_targets
from .planner import CurriculumPlanner, PlannerRequest
from .planning_packet import build_curriculum_planning_packet
from .retrieval import CurriculumRetriever, LearnerConceptState
from .vector_index import DEFAULT_MODEL_DIR, SectionVectorIndex, SentenceTransformerEmbeddingModel


class OnboardingPayload(BaseModel):
    subject: str = ""
    topic: str
    current_level: str = ""
    confidence: str = ""
    learning_goal: str = ""
    available_time: str = ""
    preferred_learning_style: str = ""
    deadline_or_pace: str = ""


class LearnerConceptStatePayload(BaseModel):
    concept_id: str
    status: str
    confidence: float = 1.0
    recency_weight: float = 1.0


class CurriculumQueryPayload(BaseModel):
    learner_id: str = "anonymous"
    onboarding: OnboardingPayload
    learner_state: list[LearnerConceptStatePayload] = Field(default_factory=list)
    prerequisite_check: dict[str, Any] | None = None
    intent_grounding_section_ids: list[str] = Field(default_factory=list)
    subject: str | None = None
    grade: int | None = None
    chapter_id: str | None = None
    max_modules: int = 10
    retrieval_limit: int = 12


class IntentClassifyPayload(BaseModel):
    query: str
    subject: str | None = None
    grade: int | None = None
    chapter_id: str | None = None
    candidate_limit: int = 12


class PlannedModulePayload(BaseModel):
    module_id: str
    title: str
    module_goal: str
    position: int
    covered_concept_ids: list[str] = Field(default_factory=list)
    source_section_ids: list[str]
    prerequisite_warnings: list[str] = Field(default_factory=list)
    depends_on_module_ids: list[str] = Field(default_factory=list)
    link_from_previous: str = ""
    link_to_next: str = ""
    parallel_support_section_ids: list[str] = Field(default_factory=list)
    reinforcement_section_ids: list[str] = Field(default_factory=list)
    next_step_section_ids: list[str] = Field(default_factory=list)


class CurriculumPlanPayload(BaseModel):
    curriculum_plan_id: str
    learner_id: str
    onboarding: OnboardingPayload
    modules: list[PlannedModulePayload]
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModuleDesignPayload(BaseModel):
    plan: CurriculumPlanPayload
    module_id: str
    learner_state: list[LearnerConceptStatePayload] = Field(default_factory=list)


class CheckpointAnswerPayload(BaseModel):
    question_id: str
    selected_option: str


class CheckpointSubmitPayload(BaseModel):
    learner_id: str
    curriculum_plan_id: str
    module_id: str
    checkpoint_mcqs: list[dict[str, Any]]
    answers: list[CheckpointAnswerPayload]


class CurriculumAPIService:
    def __init__(
        self,
        *,
        root: Path | str = ".",
        use_vector: bool = False,
        llm_client: Any | None = None,
        intent_llm_client: Any | None = None,
    ):
        self.root = Path(root)
        self.graph = CurriculumGraph(
            TextbookStore(self.root),
            ArtifactStore(self.root),
            usable_only=True,
        )
        self.retriever = CurriculumRetriever(self.graph, vector_index=_load_vector_index(self.root, use_vector=use_vector))
        self.llm_client = llm_client or FireworksLLMClient()
        self.intent_llm_client = intent_llm_client or FireworksLLMClient(
            model=FIREWORKS_GPT_OSS_120B,
            max_tokens=INTENT_OUTPUT_MAX_TOKENS,
            temperature=0.0,
        )

    def classify_intent(self, payload: IntentClassifyPayload) -> dict[str, Any]:
        classifier = IntentClassifier(self.graph, self.retriever, self.intent_llm_client)
        return classifier.classify(
            payload.query,
            subject=payload.subject,
            grade=payload.grade,
            chapter_id=payload.chapter_id,
            limit=payload.candidate_limit,
        )

    def retrieval_preview(self, payload: CurriculumQueryPayload) -> dict[str, Any]:
        onboarding = _onboarding(payload.onboarding)
        learner_state = _learner_state(payload.learner_state)
        retrieved = _retrieve_for_payload(self.retriever, payload, onboarding, learner_state)
        context = build_learning_path_context(
            self.graph,
            retrieved,
            learner_state=learner_state,
            prerequisite_check=payload.prerequisite_check,
        )
        planning_packet = build_curriculum_planning_packet(onboarding, learner_state, retrieved, context)
        return {
            "retrieved_sections": [_retrieval_row(row) for row in retrieved],
            "prerequisite_questions": _prerequisite_questions(context.to_dict()),
            "learning_path_context": context.to_dict(),
            "planning_packet": planning_packet.to_dict(),
        }

    def create_plan(self, payload: CurriculumQueryPayload) -> dict[str, Any]:
        planner = CurriculumPlanner(self.retriever, self.llm_client)
        plan = planner.create_plan(
            PlannerRequest(
                learner_id=payload.learner_id,
                onboarding=_onboarding(payload.onboarding),
                learner_state=_learner_state(payload.learner_state),
                prerequisite_check=payload.prerequisite_check,
                intent_grounding_section_ids=payload.intent_grounding_section_ids,
                subject=payload.subject,
                grade=payload.grade,
                chapter_id=payload.chapter_id,
                max_modules=payload.max_modules,
                retrieval_limit=payload.retrieval_limit,
            )
        )
        plan_row = _plan_row(plan)
        plan_row["mcq_allocation"] = allocate_module_mcq_targets(plan)
        return plan_row

    def design_module(self, payload: ModuleDesignPayload) -> dict[str, Any]:
        plan = _plan_from_payload(payload.plan)
        expander = ModuleExpander(self.graph, self.llm_client)
        expanded = expander.expand_module(
            plan,
            payload.module_id,
            learner_state=_learner_state(payload.learner_state),
        )
        return _jsonable(expanded)

    def submit_checkpoint(self, payload: CheckpointSubmitPayload) -> dict[str, Any]:
        answer_by_id = {answer.question_id: answer.selected_option for answer in payload.answers}
        rows = []
        correct_count = 0
        weak_section_ids: list[str] = []
        weak_concept_ids: list[str] = []
        insight_events: list[dict[str, Any]] = []
        for mcq in payload.checkpoint_mcqs:
            question_id = str(mcq.get("question_id") or "")
            selected = answer_by_id.get(question_id, "")
            correct = selected == str(mcq.get("correct_option") or "")
            correct_count += 1 if correct else 0
            source_section_ids = [str(item) for item in mcq.get("source_section_ids") or []]
            tested_concept_ids = [str(item) for item in mcq.get("tested_concept_ids") or []]
            if not correct:
                weak_section_ids.extend(source_section_ids)
                weak_concept_ids.extend(tested_concept_ids)
            insight_type = "COMPETENCY" if correct else "MISCONCEPTION"
            for concept_id in tested_concept_ids:
                insight_events.append(
                    {
                        "learner_id": payload.learner_id,
                        "type": insight_type,
                        "concept_id": concept_id,
                        "module_id": payload.module_id,
                        "question_id": question_id,
                        "source_section_ids": source_section_ids,
                        "diagnostic_purpose": mcq.get("diagnostic_purpose") or "",
                        "misconception_tags": mcq.get("misconception_tags") or [],
                        "confidence": 0.8 if correct else 0.7,
                    }
                )
            rows.append(
                {
                    "question_id": question_id,
                    "selected_option": selected,
                    "correct_option": mcq.get("correct_option"),
                    "is_correct": correct,
                    "source_section_ids": source_section_ids,
                    "tested_concept_ids": tested_concept_ids,
                    "diagnostic_purpose": mcq.get("diagnostic_purpose") or "",
                    "misconception_tags": mcq.get("misconception_tags") or [],
                }
            )
        total = len(payload.checkpoint_mcqs)
        score = correct_count / total if total else 0.0
        return {
            "learner_id": payload.learner_id,
            "curriculum_plan_id": payload.curriculum_plan_id,
            "module_id": payload.module_id,
            "score": score,
            "correct_count": correct_count,
            "total_count": total,
            "weak_section_ids": _dedupe(weak_section_ids),
            "weak_concept_ids": _dedupe(weak_concept_ids),
            "question_results": rows,
            "insight_events": insight_events,
            "recommendation": "continue" if score >= 0.7 else "review_module",
        }


def create_app(service: CurriculumAPIService | None = None) -> FastAPI:
    app = FastAPI(title="AI Curriculum Creator API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.service = service

    def service_dep() -> CurriculumAPIService:
        return app.state.service or default_service()

    @app.get("/health")
    def health(svc: CurriculumAPIService = Depends(service_dep)) -> dict[str, Any]:
        return {
            "ok": True,
            "usable_chapters": len(svc.graph.usable_chapter_ids),
            "section_summaries": len(svc.graph.section_summaries_by_id),
        }

    @app.get("/api/options")
    def options(svc: CurriculumAPIService = Depends(service_dep)) -> dict[str, Any]:
        refs = svc.graph.textbooks.chapter_refs()
        return {
            "subjects": sorted({row.get("subject") for row in refs if row.get("subject")}),
            "grades": sorted({int(row.get("grade")) for row in refs if row.get("grade") is not None}),
            "chapters": refs,
        }

    @app.post("/api/intent/classify")
    def classify_intent(payload: IntentClassifyPayload, svc: CurriculumAPIService = Depends(service_dep)) -> dict[str, Any]:
        return _handle_api(lambda: svc.classify_intent(payload))

    @app.post("/api/retrieval/preview")
    def retrieval_preview(payload: CurriculumQueryPayload, svc: CurriculumAPIService = Depends(service_dep)) -> dict[str, Any]:
        return _handle_api(lambda: svc.retrieval_preview(payload))

    @app.post("/api/curriculum/plan")
    def curriculum_plan(payload: CurriculumQueryPayload, svc: CurriculumAPIService = Depends(service_dep)) -> dict[str, Any]:
        return _handle_api(lambda: svc.create_plan(payload))

    @app.post("/api/modules/design")
    def module_design(payload: ModuleDesignPayload, svc: CurriculumAPIService = Depends(service_dep)) -> dict[str, Any]:
        return _handle_api(lambda: svc.design_module(payload))

    @app.post("/api/checkpoints/submit")
    def checkpoint_submit(payload: CheckpointSubmitPayload, svc: CurriculumAPIService = Depends(service_dep)) -> dict[str, Any]:
        return _handle_api(lambda: svc.submit_checkpoint(payload))

    return app


@lru_cache(maxsize=1)
def default_service() -> CurriculumAPIService:
    return CurriculumAPIService(root=Path.cwd(), use_vector=False)


app = create_app()


def _handle_api(fn: Any) -> Any:
    try:
        return fn()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _retrieve_for_payload(
    retriever: CurriculumRetriever,
    payload: CurriculumQueryPayload,
    onboarding: OnboardingAnswers,
    learner_state: list[LearnerConceptState],
) -> list[Any]:
    grounded = retriever.results_for_section_ids(payload.intent_grounding_section_ids)
    if grounded:
        return grounded[: payload.retrieval_limit]
    return retriever.search(
        onboarding.topic,
        subject=payload.subject or _blank_to_none(onboarding.subject),
        grade=payload.grade,
        chapter_id=payload.chapter_id,
        learner_state=learner_state,
        limit=payload.retrieval_limit,
        include_prerequisites=True,
    )


def _onboarding(payload: OnboardingPayload) -> OnboardingAnswers:
    return OnboardingAnswers(**payload.model_dump())


def _learner_state(rows: list[LearnerConceptStatePayload]) -> list[LearnerConceptState]:
    return [LearnerConceptState(**row.model_dump()) for row in rows]


def _load_vector_index(root: Path, *, use_vector: bool) -> SectionVectorIndex | None:
    if not use_vector:
        return None
    index = SectionVectorIndex.load(root)
    if not index:
        return None
    return index.with_embedding_model(SentenceTransformerEmbeddingModel(DEFAULT_MODEL_DIR))


def _retrieval_row(row: Any) -> dict[str, Any]:
    return {
        "section_id": row.section_id,
        "chapter_id": row.chapter_id,
        "title": row.title,
        "summary": row.summary,
        "score": row.score,
        "matched_concept_ids": row.matched_concept_ids,
        "prerequisite_section_ids": row.prerequisite_section_ids,
        "reasons": row.reasons,
        "subject": row.subject,
        "grade": row.grade,
    }


def _prerequisite_questions(context: dict[str, Any]) -> list[dict[str, Any]]:
    questions = []
    seen: set[tuple[str, str]] = set()
    for row in context.get("required_concepts") or []:
        concept_id = str(row.get("concept_id") or "")
        section_id = str(row.get("section_id") or "")
        if not concept_id or not section_id or (concept_id, section_id) in seen:
            continue
        seen.add((concept_id, section_id))
        label = row.get("label") or concept_id.replace("concept:", "").replace("_", " ")
        questions.append(
            {
                "question_id": f"prereq:{section_id}:{concept_id}",
                "concept_id": concept_id,
                "required_by_section_id": section_id,
                "label": label,
                "question": f"How comfortable are you with {label}?",
                "pedagogical_reason": row.get("pedagogical_reason") or "",
                "options": ["known_well", "somewhat_known", "unfamiliar"],
            }
        )
    return questions


def _plan_row(plan: CurriculumPlan) -> dict[str, Any]:
    return {
        "curriculum_plan_id": plan.curriculum_plan_id,
        "learner_id": plan.learner_id,
        "onboarding": _jsonable(plan.onboarding),
        "modules": [_jsonable(module) for module in plan.modules],
        "created_at": plan.created_at.isoformat(),
        "metadata": plan.metadata,
    }


def _plan_from_payload(payload: CurriculumPlanPayload) -> CurriculumPlan:
    from datetime import datetime, timezone

    return CurriculumPlan(
        curriculum_plan_id=payload.curriculum_plan_id,
        learner_id=payload.learner_id,
        onboarding=_onboarding(payload.onboarding),
        modules=[PlannedCurriculumModule(**row.model_dump()) for row in payload.modules],
        created_at=datetime.now(timezone.utc),
        metadata=payload.metadata,
    )


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _jsonable(row) for key, row in asdict(value).items()}
    if isinstance(value, list):
        return [_jsonable(row) for row in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(row) for key, row in value.items()}
    return value


def _blank_to_none(value: str) -> str | None:
    value = (value or "").strip()
    return value or None


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    ordered = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered
