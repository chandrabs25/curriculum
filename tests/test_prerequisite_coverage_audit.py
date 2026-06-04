from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/relationship_generation/13_audit_prerequisite_coverage.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("prerequisite_coverage_audit", SCRIPT)
assert SPEC and SPEC.loader
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


class PrerequisiteCoverageAuditTest(unittest.TestCase):
    def test_uniform_and_constant_acceleration_are_equivalence_candidates(self) -> None:
        required = {
            "concept_id": "concept:uniform_acceleration",
            "canonical_label": "Uniform Acceleration",
            "subjects": ["physics"],
        }
        taught = [
            {
                "concept_id": "concept:constant_acceleration",
                "canonical_label": "Constant Acceleration",
                "subjects": ["physics"],
            }
        ]

        classification, candidates = audit.classify_unmatched(required, taught)

        self.assertEqual(classification, "equivalent_candidate")
        self.assertEqual(candidates[0]["concept_id"], "concept:constant_acceleration")

    def test_derivative_without_credible_match_is_external(self) -> None:
        required = {
            "concept_id": "concept:derivative",
            "canonical_label": "Derivative",
            "subjects": ["physics"],
        }
        taught = [
            {
                "concept_id": "concept:constant_acceleration",
                "canonical_label": "Constant Acceleration",
                "subjects": ["physics"],
            }
        ]

        classification, _ = audit.classify_unmatched(required, taught)

        self.assertEqual(classification, "external_prerequisite")

    def test_audit_never_infers_fuzzy_dependencies(self) -> None:
        concepts = [
            {"concept_id": "concept:uniform_acceleration", "canonical_label": "Uniform Acceleration", "subjects": ["physics"]},
            {"concept_id": "concept:constant_acceleration", "canonical_label": "Constant Acceleration", "subjects": ["physics"]},
        ]
        relationships = [
            {
                "chapter_id": "chapter:1",
                "type": "REQUIRES_CONCEPT",
                "from_id": "section:2",
                "to_id": "concept:uniform_acceleration",
            },
            {
                "chapter_id": "chapter:1",
                "type": "TEACHES_CONCEPT",
                "from_id": "section:1",
                "to_id": "concept:constant_acceleration",
            },
        ]

        report, candidates = audit.build_audit(concepts, relationships)

        self.assertEqual(report["summary"]["accepted_dependency_count"], 0)
        self.assertEqual(len(candidates), 1)

    def test_reviewed_distinct_pair_is_not_requeued(self) -> None:
        concepts = [
            {"concept_id": "concept:electric_potential_difference", "canonical_label": "Electric Potential Difference", "subjects": ["physics"]},
            {"concept_id": "concept:electrostatic_potential_difference", "canonical_label": "Electrostatic Potential Difference", "subjects": ["physics"]},
        ]
        relationships = [
            {
                "chapter_id": "chapter:1",
                "type": "REQUIRES_CONCEPT",
                "from_id": "section:2",
                "to_id": "concept:electric_potential_difference",
            },
            {
                "chapter_id": "chapter:1",
                "type": "TEACHES_CONCEPT",
                "from_id": "section:1",
                "to_id": "concept:electrostatic_potential_difference",
            },
        ]
        decisions = [
            {
                "concept_ids": ["concept:electric_potential_difference", "concept:electrostatic_potential_difference"],
                "final_decision": "keep_distinct",
                "review_status": "approved",
                "relationship": "broader_narrower",
                "reason": "Static field is narrower.",
            }
        ]

        report, candidates = audit.build_audit(concepts, relationships, decisions)

        self.assertEqual(report["summary"]["classification_counts"]["reviewed_broader_narrower"], 1)
        self.assertEqual(candidates, [])


if __name__ == "__main__":
    unittest.main()
