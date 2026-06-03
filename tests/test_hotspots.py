from __future__ import annotations

import unittest

from curriculum_engine.hotspots import HotspotThresholds, detect_hotspot_candidates


def evidence(
    learner: str,
    question: str,
    *,
    correct: bool,
    created_at: str = "2026-01-02T00:00:00+00:00",
    module_design_id: str = "module_design:v1",
) -> dict[str, object]:
    return {
        "learner_id": learner,
        "module_design_id": module_design_id,
        "created_at": created_at,
        "question_id": question,
        "is_correct": correct,
        "source_section_ids": ["section:2"],
        "tested_concept_ids": ["concept:si_units"],
        "diagnostic_purpose": "Checks quantity versus unit.",
        "misconception_tags": ["treats_units_as_quantities"],
    }


class HotspotDetectionTest(unittest.TestCase):
    def test_creates_candidate_from_current_checkpoint_evidence(self) -> None:
        rows = [
            evidence("learner:1", "q1", correct=False),
            evidence("learner:2", "q1", correct=False),
            evidence("learner:3", "q2", correct=False),
            evidence("learner:4", "q2", correct=False),
            evidence("learner:1", "q3", correct=True),
            evidence("learner:2", "q3", correct=True),
            evidence("learner:3", "q4", correct=True),
            evidence("learner:4", "q4", correct=True),
        ]

        candidates = detect_hotspot_candidates(rows)

        self.assertEqual(len(candidates), 1)
        hotspot = candidates[0]
        self.assertEqual(hotspot["section_id"], "section:2")
        self.assertEqual(hotspot["concept_id"], "concept:si_units")
        self.assertEqual(hotspot["misconception_tag"], "treats_units_as_quantities")
        self.assertEqual(hotspot["attempt_count"], 8)
        self.assertEqual(hotspot["wrong_count"], 4)
        self.assertEqual(hotspot["unique_learner_count"], 4)
        self.assertTrue(hotspot["proposed_guidance"])
        self.assertEqual(hotspot["reviewed_guidance"], "")
        self.assertNotIn("learner:1", str(hotspot))

    def test_requires_multiple_questions(self) -> None:
        rows = [evidence(f"learner:{index}", "q1", correct=False) for index in range(1, 9)]

        candidates = detect_hotspot_candidates(rows)

        self.assertEqual(candidates, [])

    def test_active_fix_resets_evidence_window(self) -> None:
        active = {
            "section_id": "section:2",
            "concept_id": "concept:si_units",
            "misconception_tag": "treats_units_as_quantities",
            "status": "active",
            "activated_at": "2026-01-05T00:00:00+00:00",
            "updated_at": "2026-01-07T00:00:00+00:00",
        }
        old_rows = [
            evidence(f"learner:{index}", "q1" if index <= 4 else "q2", correct=False, created_at="2026-01-02T00:00:00+00:00")
            for index in range(1, 9)
        ]
        new_rows = [
            evidence(f"learner:{index}", "q3" if index <= 2 else "q4", correct=False, created_at="2026-01-06T00:00:00+00:00")
            for index in range(1, 5)
        ]

        candidates = detect_hotspot_candidates(
            old_rows + new_rows,
            active_hotspots=[active],
            thresholds=HotspotThresholds(min_attempts=4, min_unique_learners=4, min_distinct_questions=2),
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["attempt_count"], 4)
        self.assertEqual(candidates[0]["evidence_window_start"], active["activated_at"])

    def test_missing_misconception_tags_do_not_create_unspecified_hotspot(self) -> None:
        rows = [evidence(f"learner:{index}", "q1" if index <= 4 else "q2", correct=False) for index in range(1, 9)]
        for row in rows:
            row["misconception_tags"] = []

        candidates = detect_hotspot_candidates(rows)

        self.assertEqual(candidates, [])


if __name__ == "__main__":
    unittest.main()
