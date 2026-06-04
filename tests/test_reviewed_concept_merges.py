from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts/relationship_generation"
sys.path.insert(0, str(SCRIPT_DIR))


def load_script(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


finalizer = load_script("finalize_prerequisite_reviews", "15_finalize_prerequisite_concept_reviews.py")
applicator = load_script("apply_reviewed_merges", "10_apply_manual_concept_merges.py")


class ReviewedConceptMergeTest(unittest.TestCase):
    def test_finalizer_overrides_scope_sensitive_and_inconsistent_pairs(self) -> None:
        decisions = [
            {
                "candidate_id": "one",
                "concept_ids": ["concept:electric_potential_difference", "concept:electrostatic_potential_difference"],
                "decision": "merge",
                "canonical_concept_id": "concept:electric_potential_difference",
                "relationship": "same_concept",
                "reason": "judge merge",
            },
            {
                "candidate_id": "two",
                "concept_ids": ["concept:macromolecules", "concept:micromolecules"],
                "decision": "keep_distinct",
                "canonical_concept_id": "",
                "relationship": "same_concept",
                "reason": "judge contradiction",
            },
        ]

        rows = finalizer.finalize_decisions(decisions, [], [])

        self.assertEqual(rows[0]["final_decision"], "keep_distinct")
        self.assertEqual(rows[0]["relationship"], "broader_narrower")
        self.assertEqual(rows[1]["relationship"], "related_distinct")

    def test_finalizer_chooses_canonical_by_teaching_then_raw_evidence(self) -> None:
        decisions = [
            {
                "candidate_id": "one",
                "concept_ids": ["concept:uniform_acceleration", "concept:constant_acceleration"],
                "decision": "merge",
                "relationship": "same_concept",
                "reason": "same",
            }
        ]
        relationships = [
            {"type": "TEACHES_CONCEPT", "to_id": "concept:constant_acceleration"},
            {"type": "TEACHES_CONCEPT", "to_id": "concept:constant_acceleration"},
        ]

        rows = finalizer.finalize_decisions(decisions, relationships, [])

        self.assertEqual(rows[0]["canonical_concept_id"], "concept:constant_acceleration")

    def test_applicator_preserves_selected_canonical_and_existing_aliases(self) -> None:
        concepts = [
            {
                "concept_id": "concept:active_site",
                "canonical_label": "Active Site",
                "normalized_label": "active_site",
                "definition": "site",
                "aliases": [],
                "subjects": ["biology"],
                "source_chapter_ids": ["chapter:1"],
                "source_unit_ids": ["section:1"],
                "source_raw_concept_ids": ["raw:1"],
                "confidence": 0.9,
            },
            {
                "concept_id": "concept:active_sites",
                "canonical_label": "Active Sites",
                "normalized_label": "active_sites",
                "definition": "A longer definition of active sites.",
                "aliases": [],
                "subjects": ["biology"],
                "source_chapter_ids": ["chapter:2"],
                "source_unit_ids": ["section:2"],
                "source_raw_concept_ids": ["raw:2"],
                "confidence": 0.95,
            },
        ]
        aliases = [{"alias": "enzyme_site", "canonical_concept_id": "concept:active_sites", "reason": "existing"}]
        decisions = [
            {
                "candidate_id": "one",
                "concept_ids": ["concept:active_site", "concept:active_sites"],
                "final_decision": "merge",
                "review_status": "approved",
                "canonical_concept_id": "concept:active_site",
                "relationship": "same_concept",
                "reason": "plural variant",
            }
        ]

        output, output_aliases, _, summary = applicator.build_outputs(concepts, aliases, decisions)

        self.assertEqual(summary["removed"], 1)
        self.assertEqual(output[0]["concept_id"], "concept:active_site")
        self.assertEqual(output[0]["canonical_label"], "Active Site")
        self.assertIn("Active Sites", output[0]["aliases"])
        self.assertTrue(any(row["alias"] == "enzyme_site" and row["canonical_concept_id"] == "concept:active_site" for row in output_aliases))

    def test_applicator_is_idempotent_after_merge(self) -> None:
        concepts = [{"concept_id": "concept:active_site", "canonical_label": "Active Site", "normalized_label": "active_site"}]
        decisions = [
            {
                "candidate_id": "one",
                "concept_ids": ["concept:active_site", "concept:active_sites"],
                "final_decision": "merge",
                "review_status": "approved",
                "canonical_concept_id": "concept:active_site",
                "relationship": "same_concept",
            }
        ]

        output, _, _, summary = applicator.build_outputs(concepts, [], decisions)

        self.assertEqual(output, concepts)
        self.assertEqual(summary["removed"], 0)
        self.assertEqual(summary["already_applied_members"], 1)

    def test_alias_collision_fails(self) -> None:
        with self.assertRaises(ValueError):
            applicator.remap_aliases(
                [
                    {"alias": "same", "canonical_concept_id": "concept:a"},
                    {"alias": "same", "canonical_concept_id": "concept:b"},
                ],
                {},
                {},
            )


if __name__ == "__main__":
    unittest.main()
