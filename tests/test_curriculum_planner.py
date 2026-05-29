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
                        {"id": "section:3", "number": "1.3", "title": "Dimensional Analysis", "content_text": "", "subsections": []},
                        {"id": "section:4", "number": "1.4", "title": "Measurement Practice", "content_text": "", "subsections": []},
                        {"id": "section:5", "number": "1.5", "title": "Later Applications", "content_text": "", "subsections": []},
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
                {"chapter_id": "chapter:1", "section_id": "section:3", "title": "Dimensional Analysis", "summary": "Uses unit factors.", "key_terms": ["dimension"]},
                {"chapter_id": "chapter:1", "section_id": "section:4", "title": "Measurement Practice", "summary": "Practice with units.", "key_terms": ["practice"]},
                {"chapter_id": "chapter:1", "section_id": "section:5", "title": "Later Applications", "summary": "Apply the standard system in advanced problems.", "key_terms": ["application"]},
            ],
        )
        write_jsonl(
            self.root / "data/relationship_artifacts/canonical_concepts.jsonl",
            [
                {"concept_id": "concept:unit", "canonical_label": "Unit", "normalized_label": "unit", "aliases": []},
                {"concept_id": "concept:si_units", "canonical_label": "SI Units", "normalized_label": "si_units", "aliases": []},
                {"concept_id": "concept:dimensional_analysis", "canonical_label": "Dimensional Analysis", "normalized_label": "dimensional_analysis", "aliases": []},
            ],
        )
        write_jsonl(
            self.root / "data/relationship_artifacts/accepted_relationships.jsonl",
            [
                {"chapter_id": "chapter:1", "type": "TEACHES_CONCEPT", "from_id": "section:1", "to_id": "concept:unit"},
                {
                    "chapter_id": "chapter:1",
                    "type": "TEACHES_CONCEPT",
                    "from_id": "section:2",
                    "to_id": "concept:si_units",
                    "confidence": 0.95,
                    "evidence": {"text": "SI units are introduced.", "reason": "source evidence"},
                    "teaching_evidence": "SI units are introduced.",
                },
                {"chapter_id": "chapter:1", "type": "TEACHES_CONCEPT", "from_id": "section:3", "to_id": "concept:dimensional_analysis"},
                {"chapter_id": "chapter:1", "type": "TEACHES_CONCEPT", "from_id": "section:4", "to_id": "concept:unit"},
                {"chapter_id": "chapter:1", "type": "TEACHES_CONCEPT", "from_id": "section:5", "to_id": "concept:unit"},
                {
                    "chapter_id": "chapter:1",
                    "type": "REQUIRES_CONCEPT",
                    "from_id": "section:2",
                    "to_id": "concept:unit",
                    "confidence": 0.9,
                    "evidence": {"text": "Learners should understand units first.", "reason": "source reason"},
                    "pedagogical_reason": "Learners should understand units first.",
                },
                {
                    "chapter_id": "chapter:1",
                    "type": "DEPENDS_ON_UNIT",
                    "from_id": "section:2",
                    "to_id": "section:1",
                    "source_concept_id": "concept:unit",
                    "confidence": 0.9,
                    "evidence": {"text": "Section 2 requires units; section 1 teaches units.", "reason": "section dependency"},
                },
                {
                    "chapter_id": "chapter:1",
                    "type": "TRANSFER_SUPPORTS_UNIT",
                    "from_id": "section:2",
                    "to_id": "section:3",
                    "source_concept_id": "concept:dimensional_analysis",
                    "confidence": 0.9,
                    "evidence": {"text": "Dimensional analysis can support SI units.", "reason": "transfer support"},
                },
                {
                    "chapter_id": "chapter:1",
                    "type": "RELATED_BY_CONCEPT",
                    "from_id": "section:2",
                    "to_id": "section:4",
                    "source_concept_id": "concept:unit",
                    "confidence": 0.9,
                    "evidence": {"text": "Both sections discuss units.", "reason": "related concept"},
                },
                {
                    "chapter_id": "chapter:1",
                    "type": "DEPENDS_ON_UNIT",
                    "from_id": "section:5",
                    "to_id": "section:2",
                    "source_concept_id": "concept:si_units",
                    "confidence": 0.9,
                    "evidence": {"text": "Conversions depend on SI units.", "reason": "next step"},
                },
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
                        "module_id": "module:si",
                        "title": "Build SI Unit Foundations",
                        "module_goal": "Build a reliable base for SI unit use.",
                        "position": 2,
                        "depends_on_module_ids": ["module:intro", "module:missing"],
                        "link_from_previous": "Units prepare SI unit conventions.",
                        "link_to_next": "SI units support later applications.",
                        "source_section_ids": ["section:2", "section:missing"],
                        "parallel_support_section_ids": ["section:3", "section:missing"],
                        "reinforcement_section_ids": ["section:4"],
                        "next_step_section_ids": ["section:5"],
                        "prerequisite_warnings": ["Review Units first."],
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
            prerequisite_check={
                "asked": True,
                "answers": [
                    {
                        "concept_id": "concept:unit",
                        "status": "known_well",
                        "required_by_section_id": "section:2",
                    }
                ],
            },
            grade=11,
        )

        plan = self.planner(llm).create_plan(request)

        self.assertEqual(plan.learner_id, "learner:1")
        self.assertEqual(plan.modules[0].module_id, "module:si")
        self.assertEqual(plan.modules[0].title, "Build SI Unit Foundations")
        self.assertEqual(plan.modules[0].module_goal, "Build a reliable base for SI unit use.")
        self.assertEqual(plan.modules[0].position, 2)
        self.assertEqual(plan.modules[0].depends_on_module_ids, [])
        self.assertEqual(plan.modules[0].link_from_previous, "Units prepare SI unit conventions.")
        self.assertEqual(plan.modules[0].link_to_next, "SI units support later applications.")
        self.assertEqual(plan.modules[0].source_section_ids, ["section:2"])
        self.assertEqual(plan.modules[0].covered_concept_ids, ["concept:si_units"])
        self.assertEqual(plan.modules[0].parallel_support_section_ids, ["section:3"])
        self.assertEqual(plan.modules[0].reinforcement_section_ids, ["section:4"])
        self.assertEqual(plan.modules[0].next_step_section_ids, ["section:5"])
        self.assertIn("learner_state", llm.prompt)
        self.assertIn("Planning packet:", llm.prompt)
        self.assertIn("ordered curriculum module sequence", llm.prompt)
        self.assertIn("Do not produce concept IDs, activities", llm.prompt)
        self.assertIn("main_path_section_ids", llm.prompt)
        self.assertIn("parallel_support", llm.prompt)
        self.assertIn("reinforcement", llm.prompt)
        self.assertIn("next_steps", llm.prompt)
        self.assertNotIn("relationship_policy", llm.prompt)
        self.assertIn("known_well", llm.prompt)
        self.assertIn("Do not put optional support/reinforcement/next-step sections into source_section_ids", llm.prompt)
        self.assertIn("Concepts are intentionally omitted", llm.prompt)
        self.assertIn("current learning goal", llm.prompt)
        self.assertIn("do not use every ID just because it is present", llm.prompt)
        self.assertIn("do not drift to another subject or topic", llm.prompt)
        self.assertNotIn("Learners should understand units first.", llm.prompt)
        self.assertNotIn("SI units are introduced.", llm.prompt)
        self.assertNotIn('"learning_path_context"', llm.prompt)
        self.assertLess(llm.prompt.index("Planning packet:"), llm.prompt.index("Critical rules:"))
        self.assertIsNotNone(llm.schema)
        schema_props = llm.schema["properties"]["modules"]["items"]["properties"]
        self.assertNotIn("covered_concept_ids", schema_props)
        self.assertNotIn("activities", schema_props)
        self.assertNotIn("milestone", schema_props)
        self.assertNotIn("estimated_time_minutes", schema_props)
        self.assertEqual(PlannerRequest(learner_id="x", onboarding=self.onboarding()).max_modules, 10)
        self.assertIn("learning_path_context", plan.metadata)
        self.assertIn("planning_packet", plan.metadata)

    def test_planner_rejects_no_valid_modules(self) -> None:
        llm = FakeLLM({"modules": [{"title": "Invalid", "source_section_ids": ["unknown"]}]})
        request = PlannerRequest(
            learner_id="learner:1",
            onboarding=self.onboarding(),
            grade=11,
            max_modules=2,
        )

        with self.assertRaises(ValueError):
            self.planner(llm).create_plan(request)


if __name__ == "__main__":
    unittest.main()
