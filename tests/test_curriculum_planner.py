from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from curriculum_engine import (
    ArtifactStore,
    CurriculumGraph,
    CurriculumPlanner,
    CurriculumRetriever,
    LearnerConceptState,
    LearnerConceptStatus,
    OnboardingAnswers,
    PlannerRequest,
    TextbookStore,
)


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


class FakeLLM:
    def __init__(self, payload: dict[str, Any]):
        self.payload = payload
        self.prompt = ""
        self.schema = None

    def generate_json(self, prompt: str, schema: dict[str, Any] | None = None) -> dict[str, Any]:
        self.prompt = prompt
        self.schema = schema
        return self.payload


class CurriculumPlannerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        chapter_path = Path("data/textbook_sources/physics/grade_11/ch1.json")
        write_json(
            self.root / "data/textbook_sources/manifest.json",
            {
                "chapters": [
                    {
                        "id": "chapter:1",
                        "subject": "physics",
                        "grade": 11,
                        "chapter_number": 1,
                        "chapter_title": "Measurement",
                        "path": str(chapter_path),
                    }
                ]
            },
        )
        write_json(
            self.root / chapter_path,
            {
                "id": "chapter:1",
                "subject": "physics",
                "grade": 11,
                "chapter": {
                    "id": "chapter:1",
                    "title": "Measurement",
                    "sections": [
                        {"id": "section:1", "number": "1.1", "title": "Units", "content_text": "", "subsections": []},
                        {"id": "section:2", "number": "1.2", "title": "SI Units", "content_text": "", "subsections": []},
                    ],
                    "exercises": {"items": []},
                },
            },
        )
        write_jsonl(
            self.root / "data/relationship_artifacts/section_summaries.jsonl",
            [
                {"chapter_id": "chapter:1", "section_id": "section:1", "title": "Units", "summary": "Defines units.", "key_terms": ["unit"]},
                {"chapter_id": "chapter:1", "section_id": "section:2", "title": "SI Units", "summary": "Introduces SI units.", "key_terms": ["SI"]},
            ],
        )
        write_jsonl(
            self.root / "data/relationship_artifacts/canonical_concepts.jsonl",
            [
                {"concept_id": "concept:unit", "canonical_label": "Unit", "normalized_label": "unit", "aliases": []},
                {"concept_id": "concept:si_units", "canonical_label": "SI Units", "normalized_label": "si_units", "aliases": []},
            ],
        )
        write_jsonl(
            self.root / "data/relationship_artifacts/accepted_relationships.jsonl",
            [
                {"chapter_id": "chapter:1", "type": "TEACHES_CONCEPT", "from_id": "section:1", "to_id": "concept:unit"},
                {"chapter_id": "chapter:1", "type": "TEACHES_CONCEPT", "from_id": "section:2", "to_id": "concept:si_units"},
                {"chapter_id": "chapter:1", "type": "DEPENDS_ON_UNIT", "from_id": "section:2", "to_id": "section:1"},
            ],
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def planner(self, llm: FakeLLM) -> CurriculumPlanner:
        graph = CurriculumGraph(TextbookStore(self.root), ArtifactStore(self.root))
        return CurriculumPlanner(CurriculumRetriever(graph), llm)

    def onboarding(self) -> OnboardingAnswers:
        return OnboardingAnswers(
            subject="physics",
            topic="SI Units",
            current_level="beginner",
            confidence="low",
            learning_goal="understand measurement units",
            available_time="2 hours",
            preferred_learning_style="worked examples",
            deadline_or_pace="steady",
        )

    def test_planner_creates_curriculum_plan_from_llm_payload(self) -> None:
        llm = FakeLLM(
            {
                "modules": [
                    {
                        "title": "Build SI Unit Foundations",
                        "covered_concept_ids": ["concept:si_units"],
                        "source_section_ids": ["section:2", "section:missing"],
                        "activities": ["Read the SI section", "Make a unit table"],
                        "recommended_examples": [],
                        "recommended_exercises": [],
                        "milestone": "Explain base SI units.",
                        "expected_outcome": "Use SI units correctly.",
                        "estimated_time_minutes": 45,
                        "prerequisite_warnings": ["Review Units first."],
                        "personalization_note": "Low confidence: move carefully.",
                    }
                ]
            }
        )
        request = PlannerRequest(
            learner_id="learner:1",
            onboarding=self.onboarding(),
            learner_state=[
                LearnerConceptState(
                    concept_id="concept:si_units",
                    status=LearnerConceptStatus.PARTIAL,
                    confidence=0.8,
                    recency_weight=1.0,
                )
            ],
            grade=11,
        )

        plan = self.planner(llm).create_plan(request)

        self.assertEqual(plan.learner_id, "learner:1")
        self.assertEqual(plan.modules[0].title, "Build SI Unit Foundations")
        self.assertEqual(plan.modules[0].source_section_ids, ["section:2"])
        self.assertIn("learner_state", llm.prompt)
        self.assertIn("concept:si_units", llm.prompt)
        self.assertIsNotNone(llm.schema)

    def test_planner_falls_back_when_llm_returns_no_valid_modules(self) -> None:
        llm = FakeLLM({"modules": [{"title": "Invalid", "source_section_ids": ["unknown"]}]})
        request = PlannerRequest(
            learner_id="learner:1",
            onboarding=self.onboarding(),
            grade=11,
            max_modules=2,
        )

        plan = self.planner(llm).create_plan(request)

        self.assertTrue(plan.modules)
        self.assertEqual(plan.modules[0].source_section_ids, ["section:2"])
        self.assertIn("retrieved_section_ids", plan.metadata)


if __name__ == "__main__":
    unittest.main()
