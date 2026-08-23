from __future__ import annotations

import copy
import unittest
from typing import Any

from curriculum_engine.checkpoint_workflow import CheckpointAttemptWorkflow, CheckpointSubmission


def checkpoint_design() -> dict[str, Any]:
    return {
        "metadata": {"module_design_id": "module_design:1"},
        "checkpoint_mcqs": [
            {
                "question_id": "module:1:q1",
                "question": "Which statement is correct?",
                "options": [
                    {"option_id": "A", "text": "Correct statement"},
                    {"option_id": "B", "text": "Incorrect statement"},
                    {"option_id": "C", "text": "Another incorrect statement"},
                    {"option_id": "D", "text": "A final incorrect statement"},
                ],
                "correct_option_id": "A",
                "explanation": "Option A follows the section evidence.",
                "source_section_ids": ["section:1"],
                "tested_concept_ids": ["concept:1"],
                "diagnostic_purpose": "Checks the core distinction.",
                "misconception_tags": ["confuses_core_distinction"],
            }
        ],
    }


class WorkflowLLM:
    def __init__(self, *, fail_insights: bool = False):
        self.fail_insights = fail_insights

    def generate_json(self, prompt: str, schema: dict[str, Any] | None = None) -> dict[str, Any]:
        if schema and "question_results" in schema.get("properties", {}):
            return {
                "score": 1.0,
                "recommendation": "continue",
                "overall_feedback": "The learner answered correctly.",
                "question_results": [
                    {"question_id": "module:1:q1", "is_correct": True, "feedback": "Correct."}
                ],
            }
        if self.fail_insights:
            raise RuntimeError("insight provider unavailable")
        return {
            "section_insights": [
                {
                    "section_id": "section:1",
                    "understanding_summary": "The learner understands the distinction.",
                    "current_status": "competent",
                    "strengths": ["Selected the supported answer."],
                    "misconceptions_or_gaps": [],
                    "recommended_adjustment": "Continue to applications.",
                    "confidence": 0.9,
                    "evidence_question_ids": ["module:1:q1"],
                    "supersedes_insight_id": "",
                    "reconciliation_reason": "The latest evidence is correct.",
                }
            ]
        }


class WorkflowStore:
    def __init__(self, *, fail_finalize: bool = False) -> None:
        self.design = checkpoint_design()
        self.fail_finalize = fail_finalize
        self.results: dict[str, dict[str, Any]] = {}
        self.insights: list[dict[str, Any]] = []
        self.finalize_calls = 0
        self.update_calls = 0

    def plan_belongs_to_learner(self, curriculum_plan_id: str, learner_id: str) -> bool:
        return curriculum_plan_id == "plan:1" and learner_id == "learner:1"

    def get_module_design(
        self,
        curriculum_plan_id: str,
        module_id: str,
        *,
        learner_id: str | None = None,
    ) -> dict[str, Any] | None:
        if curriculum_plan_id == "plan:1" and module_id == "module:1" and learner_id == "learner:1":
            return copy.deepcopy(self.design)
        return None

    def latest_section_insights(self, learner_id: str, section_ids: list[str]) -> list[dict[str, Any]]:
        return []

    def save_checkpoint_result(self, result: dict[str, Any]) -> str:
        self.results["attempt:1"] = copy.deepcopy(result)
        return "attempt:1"

    def finalize_checkpoint_result(
        self,
        checkpoint_attempt_id: str,
        result: dict[str, Any],
        section_insights: list[dict[str, Any]],
    ) -> None:
        self.finalize_calls += 1
        if self.fail_finalize:
            raise RuntimeError("database transaction failed")
        self.insights = copy.deepcopy(section_insights)
        self.results[checkpoint_attempt_id] = copy.deepcopy(result)

    def update_checkpoint_result(self, checkpoint_attempt_id: str, result: dict[str, Any]) -> None:
        self.update_calls += 1
        self.results[checkpoint_attempt_id] = copy.deepcopy(result)


def submission() -> CheckpointSubmission:
    return CheckpointSubmission(
        curriculum_plan_id="plan:1",
        module_id="module:1",
        learner_id="learner:1",
        answers=[{"question_id": "module:1:q1", "selected_option_id": "A"}],
    )


class CheckpointAttemptWorkflowTest(unittest.TestCase):
    def test_completes_attempt_and_insights_through_one_finalize_operation(self) -> None:
        store = WorkflowStore()
        workflow = CheckpointAttemptWorkflow(store, WorkflowLLM())

        result = workflow.submit(submission())

        self.assertEqual(result["insight_generation_status"], "complete")
        self.assertEqual(result["module_design_id"], "module_design:1")
        self.assertEqual(store.finalize_calls, 1)
        self.assertEqual(store.update_calls, 0)
        self.assertEqual(store.insights[0]["section_id"], "section:1")
        self.assertEqual(store.results["attempt:1"]["section_insights"], store.insights)

    def test_preserves_evaluation_when_insight_generation_fails(self) -> None:
        store = WorkflowStore()
        workflow = CheckpointAttemptWorkflow(store, WorkflowLLM(fail_insights=True))

        result = workflow.submit(submission())

        self.assertEqual(result["score"], 1.0)
        self.assertEqual(result["insight_generation_status"], "failed")
        self.assertIn("insight provider unavailable", result["insight_generation_error"])
        self.assertEqual(store.finalize_calls, 0)
        self.assertEqual(store.update_calls, 1)
        self.assertEqual(store.insights, [])

    def test_records_enrichment_failure_when_atomic_finalize_fails(self) -> None:
        store = WorkflowStore(fail_finalize=True)
        workflow = CheckpointAttemptWorkflow(store, WorkflowLLM())

        result = workflow.submit(submission())

        self.assertEqual(result["score"], 1.0)
        self.assertEqual(result["insight_generation_status"], "failed")
        self.assertIn("database transaction failed", result["insight_generation_error"])
        self.assertEqual(store.finalize_calls, 1)
        self.assertEqual(store.update_calls, 1)
        self.assertEqual(store.insights, [])

    def test_rejects_a_plan_not_owned_by_the_learner(self) -> None:
        store = WorkflowStore()
        workflow = CheckpointAttemptWorkflow(store, WorkflowLLM())
        command = CheckpointSubmission(
            curriculum_plan_id="plan:other",
            module_id="module:1",
            learner_id="learner:1",
            answers=[],
        )

        with self.assertRaisesRegex(KeyError, "Unknown curriculum_plan_id"):
            workflow.submit(command)


if __name__ == "__main__":
    unittest.main()
