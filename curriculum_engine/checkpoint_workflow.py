"""Checkpoint completion workflow with explicit durability semantics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .checkpoint_evaluation import CheckpointEvaluationLLMClient, evaluate_checkpoint
from .section_insights import generate_section_insights


class CheckpointStore(Protocol):
    def plan_belongs_to_learner(self, curriculum_plan_id: str, learner_id: str) -> bool: ...

    def get_module_design(
        self,
        curriculum_plan_id: str,
        module_id: str,
        *,
        learner_id: str | None = None,
    ) -> dict[str, Any] | None: ...

    def latest_section_insights(self, learner_id: str, section_ids: list[str]) -> list[dict[str, Any]]: ...

    def save_checkpoint_result(self, result: dict[str, Any]) -> str: ...

    def finalize_checkpoint_result(
        self,
        checkpoint_attempt_id: str,
        result: dict[str, Any],
        section_insights: list[dict[str, Any]],
    ) -> None: ...

    def update_checkpoint_result(self, checkpoint_attempt_id: str, result: dict[str, Any]) -> None: ...


@dataclass(frozen=True)
class CheckpointSubmission:
    curriculum_plan_id: str
    module_id: str
    learner_id: str
    answers: list[dict[str, str]]


class CheckpointAttemptWorkflow:
    """Evaluate one checkpoint and durably reconcile its section insights."""

    def __init__(self, store: CheckpointStore, llm_client: CheckpointEvaluationLLMClient):
        self.store = store
        self.llm_client = llm_client

    def submit(self, command: CheckpointSubmission) -> dict[str, Any]:
        design = self._owned_module_design(command)
        checkpoint_mcqs = list(design.get("checkpoint_mcqs") or [])
        if not checkpoint_mcqs:
            raise ValueError(f"Module design has no checkpoint_mcqs: {command.module_id}")

        design_metadata = design.get("metadata") if isinstance(design.get("metadata"), dict) else {}
        module_design_id = str(design_metadata.get("module_design_id") or "")
        if not module_design_id:
            raise ValueError(f"Stored module design has no module_design_id: {command.module_id}")

        evaluation = evaluate_checkpoint(
            self.llm_client,
            checkpoint_mcqs=checkpoint_mcqs,
            submitted_answers=command.answers,
        )
        result = _evaluated_result(command, module_design_id, checkpoint_mcqs, evaluation)
        section_ids = _dedupe(
            section_id
            for mcq in checkpoint_mcqs
            for section_id in (mcq.get("source_section_ids") or [])
        )
        existing_insights = self.store.latest_section_insights(command.learner_id, section_ids)
        attempt_id = self.store.save_checkpoint_result(result)

        try:
            section_insights = generate_section_insights(
                self.llm_client,
                learner_id=command.learner_id,
                curriculum_plan_id=command.curriculum_plan_id,
                module_id=command.module_id,
                question_results=result["question_results"],
                checkpoint_mcqs=checkpoint_mcqs,
                existing_section_insights=existing_insights,
            )
            result["section_insights"] = section_insights
            result["insight_generation_status"] = "complete"
            self.store.finalize_checkpoint_result(attempt_id, result, section_insights)
        except Exception as exc:
            result["section_insights"] = []
            result["insight_generation_status"] = "failed"
            result["insight_generation_error"] = str(exc)
            self.store.update_checkpoint_result(attempt_id, result)
        return result

    def _owned_module_design(self, command: CheckpointSubmission) -> dict[str, Any]:
        if not self.store.plan_belongs_to_learner(command.curriculum_plan_id, command.learner_id):
            raise KeyError(f"Unknown curriculum_plan_id: {command.curriculum_plan_id}")
        design = self.store.get_module_design(
            command.curriculum_plan_id,
            command.module_id,
            learner_id=command.learner_id,
        )
        if not design:
            raise KeyError(f"Module design not found: {command.module_id}")
        return design


def _evaluated_result(
    command: CheckpointSubmission,
    module_design_id: str,
    checkpoint_mcqs: list[dict[str, Any]],
    evaluation: dict[str, Any],
) -> dict[str, Any]:
    rows = evaluation["question_results"]
    weak_section_ids = _dedupe(
        section_id
        for row in rows
        if not row["is_correct"]
        for section_id in row["source_section_ids"]
    )
    weak_concept_ids = _dedupe(
        concept_id
        for row in rows
        if not row["is_correct"]
        for concept_id in row["tested_concept_ids"]
    )
    return {
        "learner_id": command.learner_id,
        "curriculum_plan_id": command.curriculum_plan_id,
        "module_id": command.module_id,
        "module_design_id": module_design_id,
        "score": evaluation["score"],
        "correct_count": sum(1 for row in rows if row["is_correct"]),
        "total_count": len(checkpoint_mcqs),
        "weak_section_ids": weak_section_ids,
        "weak_concept_ids": weak_concept_ids,
        "question_results": rows,
        "overall_feedback": evaluation["overall_feedback"],
        "section_insights": [],
        "insight_generation_status": "pending",
        "recommendation": evaluation["recommendation"],
    }


def _dedupe(values: Any) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if str(value)))
