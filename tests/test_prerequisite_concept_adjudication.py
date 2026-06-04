from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/relationship_generation/14_adjudicate_prerequisite_concepts.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("prerequisite_concept_adjudication", SCRIPT)
assert SPEC and SPEC.loader
judge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(judge)


class PrerequisiteConceptAdjudicationTest(unittest.TestCase):
    def candidate(self) -> dict:
        return {
            "candidate_id": "candidate:1",
            "required_concept": {
                "concept_id": "concept:uniform_acceleration",
                "label": "Uniform Acceleration",
            },
            "candidate_taught_concept": {
                "concept_id": "concept:constant_acceleration",
                "label": "Constant Acceleration",
                "heuristic": "equivalent_terminology",
                "similarity": 1.0,
            },
        }

    def test_packet_includes_relationship_evidence(self) -> None:
        evidence = judge.evidence_index(
            [
                {
                    "type": "REQUIRES_CONCEPT",
                    "from_id": "section:2",
                    "to_id": "concept:uniform_acceleration",
                    "pedagogical_reason": "The equations assume uniform acceleration.",
                },
                {
                    "type": "TEACHES_CONCEPT",
                    "from_id": "section:1",
                    "to_id": "concept:constant_acceleration",
                    "teaching_evidence": "Acceleration remains constant.",
                },
            ]
        )

        packet = judge.review_packet(self.candidate(), evidence)

        self.assertEqual(packet["required_usage_evidence"][0]["section_id"], "section:2")
        self.assertEqual(packet["teaching_evidence"][0]["section_id"], "section:1")

    def test_merge_must_choose_supplied_concept_id(self) -> None:
        with self.assertRaises(ValueError):
            judge.validate_decision(
                self.candidate(),
                {
                    "decision": "merge",
                    "canonical_concept_id": "concept:other",
                    "reason": "same",
                    "confidence": 1,
                    "relationship": "same_concept",
                },
            )

    def test_keep_distinct_clears_canonical_choice(self) -> None:
        result = judge.validate_decision(
            self.candidate(),
            {
                "decision": "keep_distinct",
                "canonical_concept_id": "concept:constant_acceleration",
                "reason": "One is broader.",
                "confidence": 0.9,
                "relationship": "broader_narrower",
            },
        )

        self.assertEqual(result["canonical_concept_id"], "")
        self.assertEqual(result["decision"], "keep_distinct")

    def test_merge_requires_same_concept_relationship(self) -> None:
        with self.assertRaises(ValueError):
            judge.validate_decision(
                self.candidate(),
                {
                    "decision": "merge",
                    "canonical_concept_id": "concept:constant_acceleration",
                    "reason": "Incorrectly broader.",
                    "confidence": 0.9,
                    "relationship": "broader_narrower",
                },
            )

    def test_keep_distinct_rejects_same_concept_relationship(self) -> None:
        with self.assertRaises(ValueError):
            judge.validate_decision(
                self.candidate(),
                {
                    "decision": "keep_distinct",
                    "canonical_concept_id": "",
                    "reason": "Contradictory.",
                    "confidence": 0.9,
                    "relationship": "same_concept",
                },
            )


if __name__ == "__main__":
    unittest.main()
