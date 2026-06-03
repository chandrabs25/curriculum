"""FastAPI surface for the current curriculum creator workflow."""

from __future__ import annotations

import os
import uuid
import logging
from dataclasses import asdict, is_dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from .artifacts import ArtifactStore, TextbookStore
from .auth import AuthError, AuthUser, AuthVerifier, SupabaseAuthVerifier
from .database import PostgresRepository, repository_from_env
from .graph import CurriculumGraph
from .intent import INTENT_OUTPUT_MAX_TOKENS, IntentClassifier
from .learning_path import build_learning_path_context
from .llm_clients import FIREWORKS_GPT_OSS_120B, FireworksLLMClient
from .models import CurriculumPlan, OnboardingAnswers, PlannedCurriculumModule
from .module_expansion import ModuleExpander, allocate_module_mcq_targets
from .planner import CurriculumPlanner, PlannerRequest
from .planning_packet import build_curriculum_planning_packet
from .retrieval import CurriculumRetriever, LearnerConceptState
from .section_insights import generate_section_insights
from .vector_index import SectionVectorIndex, PgVectorSectionIndex, HFInferenceEmbeddingModel


LOGGER = logging.getLogger(__name__)


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
    onboarding: OnboardingPayload
    learner_state: list[LearnerConceptStatePayload] = Field(default_factory=list)
    prerequisite_check: dict[str, Any] | None = None
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
    mcq_allocation: dict[str, int] = Field(default_factory=dict)


class ModuleDesignPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    curriculum_plan_id: str
    module_id: str
    learner_state: list[LearnerConceptStatePayload] = Field(default_factory=list)
    force_regenerate: bool = False


class CheckpointAnswerPayload(BaseModel):
    question_id: str
    selected_option: str


class CheckpointSubmitPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    curriculum_plan_id: str
    module_id: str
    answers: list[CheckpointAnswerPayload]


class CurriculumAPIService:
    def __init__(
        self,
        *,
        root: Path | str = ".",
        use_vector: bool = False,
        llm_client: Any | None = None,
        intent_llm_client: Any | None = None,
        repository: PostgresRepository | None = None,
        auth_verifier: AuthVerifier | None = None,
    ):
        self.root = Path(root)
        self.repository = repository if repository is not None else repository_from_env()
        self.vector_backend = os.getenv("CURRICULUM_VECTOR_BACKEND", "file").strip().lower()
        self.graph = CurriculumGraph(
            TextbookStore(self.root),
            ArtifactStore(self.root),
            usable_only=True,
        )
        self.retriever = CurriculumRetriever(
            self.graph,
            vector_index=_load_vector_index(
                self.root,
                use_vector=use_vector,
                vector_backend=self.vector_backend,
                repository=self.repository,
            ),
        )
        self.use_vector = bool(self.retriever.vector_index)
        self.llm_client = llm_client or FireworksLLMClient()
        self.intent_llm_client = intent_llm_client or FireworksLLMClient(
            model=FIREWORKS_GPT_OSS_120B,
            max_tokens=INTENT_OUTPUT_MAX_TOKENS,
            temperature=0.0,
        )
        self.auth_verifier = auth_verifier or SupabaseAuthVerifier.from_env()

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
            "prerequisite_questions": [],
            "learning_path_context": context.to_dict(),
            "planning_packet": planning_packet.to_dict(),
        }

    def create_plan(self, payload: CurriculumQueryPayload, *, user_id: str) -> dict[str, Any]:
        planner = CurriculumPlanner(self.retriever, self.llm_client)
        plan = planner.create_plan(
            PlannerRequest(
                learner_id=user_id,
                onboarding=_onboarding(payload.onboarding),
                learner_state=_learner_state(payload.learner_state),
                prerequisite_check=payload.prerequisite_check,
                subject=payload.subject,
                grade=payload.grade,
                chapter_id=payload.chapter_id,
                max_modules=payload.max_modules,
                retrieval_limit=payload.retrieval_limit,
            )
        )
        plan_row = _plan_row(plan)
        plan_row["mcq_allocation"] = allocate_module_mcq_targets(plan)
        if self.repository:
            self.repository.save_plan(plan_row)
        return plan_row

    def design_module(self, payload: ModuleDesignPayload, *, user_id: str) -> dict[str, Any]:
        if not self.repository:
            raise RuntimeError("Database persistence is required for module design")
        plan_payload = self.get_plan_payload(payload.curriculum_plan_id, learner_id=user_id)
        if not plan_payload:
            raise KeyError(f"Unknown curriculum_plan_id: {payload.curriculum_plan_id}")
        plan_payload.learner_id = user_id
        if not payload.force_regenerate:
            existing = self.repository.get_module_design(plan_payload.curriculum_plan_id, payload.module_id, learner_id=user_id)
            if existing:
                return existing
        plan = _plan_from_payload(plan_payload)
        expander = ModuleExpander(self.graph, self.llm_client)
        module = next((row for row in plan.modules if row.module_id == payload.module_id), None)
        if not module:
            raise KeyError(f"Unknown module_id: {payload.module_id}")
        section_insights = self.repository.latest_section_insights(plan.learner_id, module.source_section_ids)
        section_hotspots = self.repository.active_hotspots(module.source_section_ids)
        expanded = expander.expand_module(
            plan,
            payload.module_id,
            learner_state=_learner_state(payload.learner_state),
            section_insights=section_insights,
            section_hotspots=section_hotspots,
        )
        row = _jsonable(expanded)
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        metadata["module_design_id"] = "module_design:" + uuid.uuid4().hex[:16]
        row["metadata"] = metadata
        self.repository.save_module_design(plan.curriculum_plan_id, payload.module_id, row)
        return row

    def get_plan_payload(self, curriculum_plan_id: str, *, learner_id: str | None = None) -> CurriculumPlanPayload | None:
        if not self.repository:
            return None
        row = self.repository.get_plan(curriculum_plan_id, learner_id=learner_id)
        return CurriculumPlanPayload(**row) if row else None

    def list_plans(self, learner_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
        if not self.repository:
            return []
        return self.repository.list_plans(learner_id, limit=limit)

    def latest_section_insights(self, learner_id: str, section_ids: list[str]) -> list[dict[str, Any]]:
        if not self.repository:
            return []
        return self.repository.latest_section_insights(learner_id, section_ids)

    def submit_checkpoint(self, payload: CheckpointSubmitPayload, *, user_id: str) -> dict[str, Any]:
        if not self.repository:
            raise RuntimeError("Database persistence is required for checkpoint submission")
        if not self.repository.plan_belongs_to_learner(payload.curriculum_plan_id, user_id):
            raise KeyError(f"Unknown curriculum_plan_id: {payload.curriculum_plan_id}")
        design = self.repository.get_module_design(payload.curriculum_plan_id, payload.module_id, learner_id=user_id)
        if not design:
            raise KeyError(f"Module design not found: {payload.module_id}")
        checkpoint_mcqs = list((design or {}).get("checkpoint_mcqs") or [])
        if not checkpoint_mcqs:
            raise ValueError(f"Module design has no checkpoint_mcqs: {payload.module_id}")
        design_metadata = design.get("metadata") if isinstance(design.get("metadata"), dict) else {}
        module_design_id = str(design_metadata.get("module_design_id") or "")
        if not module_design_id:
            raise ValueError(f"Stored module design has no module_design_id: {payload.module_id}")
        answer_by_id = {answer.question_id: answer.selected_option for answer in payload.answers}
        rows = []
        correct_count = 0
        weak_section_ids: list[str] = []
        weak_concept_ids: list[str] = []
        insight_events: list[dict[str, Any]] = []
        for mcq in checkpoint_mcqs:
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
                        "learner_id": user_id,
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
        total = len(checkpoint_mcqs)
        score = correct_count / total if total else 0.0
        section_ids = _dedupe([sid for mcq in checkpoint_mcqs for sid in (mcq.get("source_section_ids") or [])])
        existing_insights = self.repository.latest_section_insights(user_id, section_ids)
        section_insights = generate_section_insights(
            self.llm_client,
            learner_id=user_id,
            curriculum_plan_id=payload.curriculum_plan_id,
            module_id=payload.module_id,
            question_results=rows,
            checkpoint_mcqs=checkpoint_mcqs,
            existing_section_insights=existing_insights,
        )
        result = {
            "learner_id": user_id,
            "curriculum_plan_id": payload.curriculum_plan_id,
            "module_id": payload.module_id,
            "module_design_id": module_design_id,
            "score": score,
            "correct_count": correct_count,
            "total_count": total,
            "weak_section_ids": _dedupe(weak_section_ids),
            "weak_concept_ids": _dedupe(weak_concept_ids),
            "question_results": rows,
            "insight_events": insight_events,
            "section_insights": section_insights,
            "recommendation": "continue" if score >= 0.7 else "review_module",
        }
        self.repository.save_checkpoint_result(result)
        self.repository.save_section_insights(section_insights)
        return result

    def latest_checkpoint_result(self, curriculum_plan_id: str, module_id: str, *, user_id: str) -> dict[str, Any] | None:
        if not self.repository:
            return None
        return self.repository.get_latest_checkpoint_result(curriculum_plan_id, module_id, learner_id=user_id)


def _cors_allowed_origins() -> list[str]:
    origins = [
        origin.strip()
        for origin in os.getenv("CORS_ALLOW_ORIGINS", "").split(",")
        if origin.strip()
    ]
    return origins or ["http://localhost:3000", "http://127.0.0.1:3000"]


def create_app(service: CurriculumAPIService | None = None) -> FastAPI:
    app = FastAPI(title="AI Curriculum Creator API")
    cors_origins = _cors_allowed_origins()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.service = service

    def service_dep() -> CurriculumAPIService:
        return app.state.service or default_service()

    def current_user(
        authorization: str | None = Header(default=None),
        svc: CurriculumAPIService = Depends(service_dep),
    ) -> AuthUser:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="Missing bearer token")
        token = authorization.split(" ", 1)[1].strip()
        try:
            user = svc.auth_verifier.verify(token)
        except AuthError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        if svc.repository:
            svc.repository.upsert_user_profile(user.to_profile())
        return user

    @app.get("/health")
    def health(svc: CurriculumAPIService = Depends(service_dep)) -> dict[str, Any]:
        db_health = None
        if svc.repository:
            db_health = svc.repository.health()
        if svc.vector_backend == "pgvector" and not svc.repository:
            raise HTTPException(status_code=503, detail="CURRICULUM_VECTOR_BACKEND=pgvector requires DATABASE_URL")
        if svc.vector_backend == "pgvector" and not svc.use_vector:
            raise HTTPException(status_code=503, detail="pgvector backend is configured but vector search is not available")
        return {
            "ok": True,
            "vector_enabled": svc.use_vector,
            "vector_backend": svc.vector_backend if svc.use_vector else "disabled",
            "database_enabled": bool(svc.repository),
            "database": db_health,
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
    def curriculum_plan(
        payload: CurriculumQueryPayload,
        user: AuthUser = Depends(current_user),
        svc: CurriculumAPIService = Depends(service_dep),
    ) -> dict[str, Any]:
        return _handle_api(lambda: svc.create_plan(payload, user_id=user.user_id))

    @app.get("/api/curriculum/plans/{curriculum_plan_id}")
    def get_curriculum_plan(
        curriculum_plan_id: str,
        user: AuthUser = Depends(current_user),
        svc: CurriculumAPIService = Depends(service_dep),
    ) -> dict[str, Any]:
        plan = svc.get_plan_payload(curriculum_plan_id, learner_id=user.user_id)
        if not plan:
            raise HTTPException(status_code=404, detail=f"Unknown curriculum_plan_id: {curriculum_plan_id}")
        return plan.model_dump()

    @app.get("/api/me/plans")
    def list_curriculum_plans(
        limit: int = 20,
        user: AuthUser = Depends(current_user),
        svc: CurriculumAPIService = Depends(service_dep),
    ) -> dict[str, Any]:
        return {"plans": svc.list_plans(user.user_id, limit=max(1, min(limit, 50)))}

    @app.get("/api/me/section-insights")
    def latest_section_insights(
        section_ids: str = "",
        user: AuthUser = Depends(current_user),
        svc: CurriculumAPIService = Depends(service_dep),
    ) -> dict[str, Any]:
        ids = _dedupe([item.strip() for item in section_ids.split(",") if item.strip()])
        return {"section_insights": svc.latest_section_insights(user.user_id, ids)}

    @app.post("/api/modules/design")
    def module_design(
        payload: ModuleDesignPayload,
        user: AuthUser = Depends(current_user),
        svc: CurriculumAPIService = Depends(service_dep),
    ) -> dict[str, Any]:
        return _handle_api(lambda: svc.design_module(payload, user_id=user.user_id))

    @app.get("/api/curriculum/plans/{curriculum_plan_id}/modules/{module_id}/design")
    def get_module_design(
        curriculum_plan_id: str,
        module_id: str,
        user: AuthUser = Depends(current_user),
        svc: CurriculumAPIService = Depends(service_dep),
    ) -> dict[str, Any]:
        if not svc.repository:
            raise HTTPException(status_code=404, detail="Database persistence is not enabled")
        design = svc.repository.get_module_design(curriculum_plan_id, module_id, learner_id=user.user_id)
        if not design:
            raise HTTPException(status_code=404, detail=f"Module design not found: {module_id}")
        return design

    @app.post("/api/checkpoints/submit")
    def checkpoint_submit(
        payload: CheckpointSubmitPayload,
        user: AuthUser = Depends(current_user),
        svc: CurriculumAPIService = Depends(service_dep),
    ) -> dict[str, Any]:
        return _handle_api(lambda: svc.submit_checkpoint(payload, user_id=user.user_id))

    @app.get("/api/curriculum/plans/{curriculum_plan_id}/modules/{module_id}/checkpoint/latest")
    def latest_checkpoint(
        curriculum_plan_id: str,
        module_id: str,
        user: AuthUser = Depends(current_user),
        svc: CurriculumAPIService = Depends(service_dep),
    ) -> dict[str, Any]:
        result = svc.latest_checkpoint_result(curriculum_plan_id, module_id, user_id=user.user_id)
        if not result:
            raise HTTPException(status_code=404, detail="Checkpoint result not found")
        return result

    # -- Admin routes -------------------------------------------------------
    from .admin_api import mount_admin_routes

    mount_admin_routes(app, current_user_dep=current_user, service_dep=service_dep)

    return app


@lru_cache(maxsize=1)
def default_service() -> CurriculumAPIService:
    use_vector = os.getenv("CURRICULUM_USE_VECTOR", "0").strip().lower() in {"1", "true", "yes", "on"}
    return CurriculumAPIService(root=Path.cwd(), use_vector=use_vector)


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
    except Exception as exc:
        LOGGER.exception("Unhandled API error")
        raise HTTPException(status_code=500, detail="Internal API error") from exc


def _retrieve_for_payload(
    retriever: CurriculumRetriever,
    payload: CurriculumQueryPayload,
    onboarding: OnboardingAnswers,
    learner_state: list[LearnerConceptState],
) -> list[Any]:
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


def _load_vector_index(
    root: Path,
    *,
    use_vector: bool,
    vector_backend: str = "file",
    repository: PostgresRepository | None = None,
) -> SectionVectorIndex | PgVectorSectionIndex | None:
    if not use_vector:
        return None
    if vector_backend == "pgvector":
        if not repository:
            raise RuntimeError("CURRICULUM_VECTOR_BACKEND=pgvector requires DATABASE_URL")
        return PgVectorSectionIndex(repository=repository, embedding_model=HFInferenceEmbeddingModel())
    index = SectionVectorIndex.load(root)
    if not index:
        return None
    return index.with_embedding_model(HFInferenceEmbeddingModel())


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
