from __future__ import annotations

import json
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts/relationship_generation/12_build_section_concept_links.py"
sys.path.insert(0, str(SCRIPT_PATH.parent))
SPEC = importlib.util.spec_from_file_location("section_concept_links", SCRIPT_PATH)
links = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(links)


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


class SectionConceptLinkTest(unittest.TestCase):
    def raw_concept(self, *, raw_id: str, section_id: str, relationship_type: str, confidence: float = 0.95) -> dict:
        return {
            "raw_concept_id": raw_id,
            "chapter_id": "chapter:1",
            "source_section_id": section_id,
            "relationship_type": relationship_type,
            "label": "Unit",
            "normalized_label": "unit",
            "candidate_concept_id": "concept:unit",
            "definition": "A measurement standard.",
            "reason": "The section assumes units.",
            "source_unit_ids": [section_id],
            "evidence": [{"unit_id": section_id, "text": "unit evidence"}],
            "confidence": confidence,
        }

    def test_teaches_and_requires_map_to_relationship_types(self) -> None:
        teaches = links.relationship_row("section:1", "concept:unit", [self.raw_concept(raw_id="raw:1", section_id="section:1", relationship_type="teaches")], "TEACHES_CONCEPT")
        requires = links.relationship_row("section:2", "concept:unit", [self.raw_concept(raw_id="raw:2", section_id="section:2", relationship_type="requires")], "REQUIRES_CONCEPT")

        self.assertEqual(teaches["type"], "TEACHES_CONCEPT")
        self.assertEqual(requires["type"], "REQUIRES_CONCEPT")
        self.assertEqual(teaches["from_id"], "section:1")
        self.assertEqual(requires["to_id"], "concept:unit")
        self.assertEqual(teaches["teaching_evidence"], "unit evidence")
        self.assertEqual(requires["pedagogical_reason"], "The section assumes units.")
        self.assertEqual(requires["evidence"]["text"], "The section assumes units.")

    def test_teaches_requires_join_infers_dependency(self) -> None:
        teaches = links.relationship_row("section:1", "concept:unit", [self.raw_concept(raw_id="raw:1", section_id="section:1", relationship_type="teaches", confidence=0.9)], "TEACHES_CONCEPT")
        requires = links.relationship_row("section:2", "concept:unit", [self.raw_concept(raw_id="raw:2", section_id="section:2", relationship_type="requires", confidence=0.8)], "REQUIRES_CONCEPT")

        dependencies = links.infer_section_links([teaches, requires])

        self.assertEqual(len(dependencies), 1)
        self.assertEqual(dependencies[0]["type"], "DEPENDS_ON_UNIT")
        self.assertEqual(dependencies[0]["from_id"], "section:2")
        self.assertEqual(dependencies[0]["to_id"], "section:1")
        self.assertEqual(dependencies[0]["source_concept_id"], "concept:unit")
        self.assertEqual(dependencies[0]["confidence"], 0.8)

    def test_self_dependency_is_not_emitted(self) -> None:
        teaches = links.relationship_row("section:1", "concept:unit", [self.raw_concept(raw_id="raw:1", section_id="section:1", relationship_type="teaches")], "TEACHES_CONCEPT")
        requires = links.relationship_row("section:1", "concept:unit", [self.raw_concept(raw_id="raw:2", section_id="section:1", relationship_type="requires")], "REQUIRES_CONCEPT")

        self.assertEqual(links.infer_section_links([teaches, requires]), [])

    def test_cross_chapter_requires_infers_transfer_support(self) -> None:
        teaches = links.relationship_row("section:1", "concept:unit", [self.raw_concept(raw_id="raw:1", section_id="section:1", relationship_type="teaches")], "TEACHES_CONCEPT")
        requires = links.relationship_row("section:2", "concept:unit", [{**self.raw_concept(raw_id="raw:2", section_id="section:2", relationship_type="requires"), "chapter_id": "chapter:2"}], "REQUIRES_CONCEPT")

        links_out = links.infer_section_links([teaches, requires])

        self.assertEqual(len(links_out), 1)
        self.assertEqual(links_out[0]["type"], "TRANSFER_SUPPORTS_UNIT")
        self.assertEqual(links_out[0]["from_id"], "section:2")
        self.assertEqual(links_out[0]["to_id"], "section:1")

    def test_cross_chapter_teaches_infers_related_by_concept(self) -> None:
        left = links.relationship_row("section:1", "concept:unit", [self.raw_concept(raw_id="raw:1", section_id="section:1", relationship_type="teaches")], "TEACHES_CONCEPT")
        right = links.relationship_row("section:2", "concept:unit", [{**self.raw_concept(raw_id="raw:2", section_id="section:2", relationship_type="teaches"), "chapter_id": "chapter:2"}], "TEACHES_CONCEPT")

        links_out = links.infer_section_links([left, right])

        self.assertEqual(len(links_out), 1)
        self.assertEqual(links_out[0]["type"], "RELATED_BY_CONCEPT")
        self.assertEqual(links_out[0]["source_concept_id"], "concept:unit")

    def test_cli_skips_partial_chapters_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact_dir = root / "data/relationship_artifacts"
            write_json(artifact_dir / "usable_chapters.json", {"usable_chapter_ids": ["chapter:1"]})
            write_jsonl(
                artifact_dir / "canonical_concepts.jsonl",
                [{"concept_id": "concept:unit", "canonical_label": "Unit", "normalized_label": "unit", "aliases": []}],
            )
            write_jsonl(artifact_dir / "concept_aliases.jsonl", [])
            write_jsonl(
                artifact_dir / "raw_concepts.jsonl",
                [
                    self.raw_concept(raw_id="raw:1", section_id="section:1", relationship_type="teaches"),
                    {**self.raw_concept(raw_id="raw:2", section_id="section:2", relationship_type="teaches"), "chapter_id": "chapter:2"},
                    self.raw_concept(raw_id="raw:3", section_id="section:Summary", relationship_type="teaches"),
                ],
            )

            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--artifact-dir",
                    str(artifact_dir),
                    "--force",
                ],
                cwd=Path(__file__).resolve().parents[1],
                check=True,
            )

            rows = read_jsonl(artifact_dir / "raw_section_concept_relationships.jsonl")
            self.assertEqual([row["from_id"] for row in rows], ["section:1"])


if __name__ == "__main__":
    unittest.main()
