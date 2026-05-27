from __future__ import annotations

import unittest

from curriculum_engine import OnboardingAnswers
from curriculum_engine.learning_path import LearningPathContext
from curriculum_engine.planning_packet import build_curriculum_planning_packet


class PlanningPacketTest(unittest.TestCase):
    def onboarding(self) -> OnboardingAnswers:
        return OnboardingAnswers(
            subject="physics",
            topic="SI Units",
            current_level="beginner",
            confidence="low",
            learning_goal="understand units",
            available_time="2 hours",
            preferred_learning_style="worked examples",
            deadline_or_pace="steady",
        )

    def context(self) -> LearningPathContext:
        long_text = "Long evidence. " * 80
        section = {
            "section_id": "section:2",
            "chapter_id": "chapter:1",
            "title": "SI Units",
            "summary": "Summary. " * 120,
            "role": "target",
            "teaches": [
                {
                    "relationship_id": "rel:t",
                    "concept_id": "concept:si_units",
                    "label": "SI Units",
                    "confidence": 0.95,
                    "teaching_evidence": long_text,
                }
            ],
            "requires": [
                {
                    "relationship_id": "rel:r",
                    "concept_id": "concept:unit",
                    "label": "Unit",
                    "confidence": 0.9,
                    "pedagogical_reason": long_text,
                }
            ],
        }
        support = {
            "section_id": "section:3",
            "chapter_id": "chapter:1",
            "title": "Dimensional Analysis",
            "summary": "Support summary.",
            "relationship_id": "rel:s",
            "relationship_type": "TRANSFER_SUPPORTS_UNIT",
            "source_target_section_id": "section:2",
            "bridge_concept_id": "concept:dimensional_analysis",
            "confidence": 0.9,
            "evidence_text": long_text,
            "planning_meaning": "optional bridge",
            "use_as": "optional support while studying the main module",
        }
        reinforcement = {
            **support,
            "section_id": "section:4",
            "relationship_id": "rel:rf",
            "relationship_type": "RELATED_BY_CONCEPT",
            "use_as": "extra practice or comparison after the core module",
        }
        next_step = {
            **support,
            "section_id": "section:5",
            "relationship_id": "rel:n",
            "relationship_type": "DEPENDS_ON_UNIT",
            "use_as": "recommended next section after completing the module",
        }
        return LearningPathContext(
            main_path_sections=[section],
            target_sections=[section],
            prerequisite_sections=[],
            support_sections=[],
            prerequisite_check={"asked": True, "answers": [{"concept_id": "concept:unit", "status": "known_well"}]},
            parallel_support_paths=[support],
            reinforcement_paths=[reinforcement],
            next_step_paths=[next_step],
            cross_chapter_bridges=[support],
            relationship_policy={"hard_dependencies": "must affect ordering"},
            required_concepts=[{**section["requires"][0], "section_id": "section:2"}],
            taught_concepts=[{**section["teaches"][0], "section_id": "section:2"}],
            hard_dependency_edges=[
                {
                    "relationship_id": "rel:d",
                    "type": "DEPENDS_ON_UNIT",
                    "from_section_id": "section:2",
                    "to_section_id": "section:1",
                    "bridge_concept_id": "concept:unit",
                    "confidence": 0.9,
                    "evidence_text": long_text,
                    "evidence_reason": long_text,
                    "planning_meaning": "to_section should be studied before from_section",
                }
            ],
            optional_support_edges=[],
            learner_adjustments=[],
        )

    def test_packet_dedupes_and_preserves_section_link_reasoning(self) -> None:
        packet = build_curriculum_planning_packet(self.onboarding(), [], [], self.context()).to_dict()

        self.assertEqual(list(packet["sections_by_id"]).count("section:2"), 1)
        self.assertNotIn("concepts_by_id", packet)
        self.assertNotIn("requires_concept", packet["relationships"])
        self.assertNotIn("teaches_concept", packet["relationships"])
        self.assertIn("evidence_reason", packet["relationships"]["hard_dependencies"][0])
        self.assertLessEqual(len(packet["sections_by_id"]["section:2"]["summary"]), 420)
        self.assertIn("estimated_chars", packet["budget"])


if __name__ == "__main__":
    unittest.main()
