from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from curriculum_engine.api import CurriculumAPIService, create_app
from curriculum_engine.auth import AuthUser, StaticAuthVerifier
from curriculum_engine.llm_clients import FireworksAPIError


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


class FakeLLM:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def generate_json(self, prompt: str, schema: dict[str, Any] | None = None) -> dict[str, Any]:
        self.prompts.append(prompt)
        if schema and "needs_user_choice" in schema.get("properties", {}):
            return {
                "needs_user_choice": False,
                "question": "",
                "confirmed_label": "Learn SI units",
                "confirmed_summary": "You want to learn SI measurement standards.",
                "refined_query": "SI units and measurement standards",
                "options": [],
            }
        if schema and "modules" in schema.get("properties", {}):
            return {
                "modules": [
                    {
                        "module_id": "module:si",
                        "title": "SI Unit Foundations",
                        "module_goal": "Use SI units with confidence.",
                        "position": 1,
                        "depends_on_module_ids": [],
                        "link_from_previous": "",
                        "link_to_next": "Use SI units in applications.",
                        "source_section_ids": ["section:2"],
                        "prerequisite_warnings": ["Review units first."],
                        "parallel_support_section_ids": ["section:3"],
                        "reinforcement_section_ids": [],
                        "next_step_section_ids": [],
                    }
                ]
            }
        if schema and "section_insights" in schema.get("properties", {}):
            return {
                "section_insights": [
                    {
                        "section_id": "section:2",
                        "understanding_summary": "The learner understands SI units as shared standards.",
                        "current_status": "competent",
                        "strengths": ["Recognizes SI units as standards."],
                        "misconceptions_or_gaps": [],
                        "recommended_adjustment": "Keep explanations concise and move toward applications.",
                        "confidence": 0.9,
                        "evidence_question_ids": ["module:si:q1"],
                        "supersedes_insight_id": "section_insight:old",
                        "reconciliation_reason": "New correct answers supersede the prior partial insight.",
                    }
                ]
            }
        if schema and "question_results" in schema.get("properties", {}) and "score" in schema.get("properties", {}):
            question_ids = list(dict.fromkeys(re.findall(r'"question_id":\s*"(module:[^"]+)"', prompt)))
            return {
                "score": 1.0,
                "recommendation": "continue",
                "overall_feedback": "The submitted responses show a sound understanding of SI units.",
                "question_results": [
                    {
                        "question_id": question_id,
                        "is_correct": True,
                        "feedback": "The selected response matches the supplied answer-key evidence.",
                    }
                    for question_id in question_ids
                ],
            }
        count_match = re.search(r'"mcq_target_count":\s*(\d+)', prompt)
        count = int(count_match.group(1)) if count_match else 1
        return {
            "title": "SI Unit Foundations",
            "module_goal": "Use SI units with confidence.",
            "larger_goal_alignment": "This supports the learner's measurement goal.",
            "transition_from_previous": "",
            "transition_to_next": "This prepares applications.",
            "lesson_sections": [
                {
                    "heading": "SI units",
                    "body": "Use SI units as shared measurement standards.",
                    "source_section_ids": ["section:2"],
                    "concept_ids": ["concept:si_units"],
                }
            ],
            "guided_activity": "Make a table of common SI base units.",
            "common_misconceptions": ["Treating a quantity as the same thing as its unit."],
            "checkpoint_mcqs": [
                {
                    "question_id": f"module:si:q{index}",
                    "question": f"Which statement about SI units is correct? {index}",
                    "options": [
                        {"option_id": "A", "text": "SI units create shared standards"},
                        {"option_id": "B", "text": "SI units remove measurement"},
                        {"option_id": "C", "text": "SI units replace physical quantities"},
                        {"option_id": "D", "text": "SI units avoid calculations"},
                    ],
                    "correct_option_id": "A",
                    "explanation": "SI units are shared measurement standards.",
                    "tested_concept_ids": ["concept:si_units"],
                    "source_section_ids": ["section:2"],
                    "difficulty": "medium",
                    "diagnostic_purpose": "Checks whether the learner understands SI units as standards.",
                    "misconception_tags": ["treats_units_as_quantities"],
                }
                for index in range(1, count + 1)
            ],
        }


class FakeRepository:
    def __init__(self) -> None:
        self.plans: dict[str, dict[str, Any]] = {}
        self.module_designs: dict[tuple[str, str], dict[str, Any]] = {}
        self.section_insights: dict[tuple[str, str], dict[str, Any]] = {}
        self.hotspots: list[dict[str, Any]] = []
        self.checkpoint_results: dict[tuple[str, str, str], dict[str, Any]] = {}
        self.profiles: dict[str, dict[str, Any]] = {}
        self.public_cache: dict[str, dict[str, Any]] = {}

    def upsert_user_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        user_id = str(profile["user_id"])
        existing = self.profiles.get(user_id, {})
        merged = {
            **profile,
            "role": existing.get("role") or profile.get("role") or "learner",
        }
        self.profiles[user_id] = dict(merged)
        return json.loads(json.dumps(merged))

    def get_user_profile(self, user_id: str) -> dict[str, Any] | None:
        profile = self.profiles.get(user_id)
        return json.loads(json.dumps(profile)) if profile else None

    def get_public_response_cache(self, cache_key: str) -> dict[str, Any] | None:
        row = self.public_cache.get(cache_key)
        return json.loads(json.dumps(row)) if row else None

    def set_public_response_cache(
        self,
        *,
        cache_key: str,
        cache_kind: str,
        response_payload: dict[str, Any],
        expires_at: str,
    ) -> None:
        self.public_cache[cache_key] = json.loads(json.dumps(response_payload))

    def save_plan(self, plan: dict[str, Any]) -> None:
        self.plans[str(plan["curriculum_plan_id"])] = json.loads(json.dumps(plan))

    def health(self) -> dict[str, Any]:
        return {"ok": True, "section_embedding_documents": 0}

    def get_plan(self, curriculum_plan_id: str, *, learner_id: str | None = None) -> dict[str, Any] | None:
        plan = self.plans.get(curriculum_plan_id)
        if not plan or (learner_id and plan.get("learner_id") != learner_id):
            return None
        return json.loads(json.dumps(plan))

    def list_plans(self, learner_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
        rows = [row for row in self.plans.values() if row.get("learner_id") == learner_id]
        return [
            {
                "curriculum_plan_id": row["curriculum_plan_id"],
                "learner_id": row["learner_id"],
                "topic": row["onboarding"].get("topic") or "",
                "subject": row["onboarding"].get("subject") or "",
                "module_count": len(row.get("modules") or []),
                "created_at": row.get("created_at") or "",
                "metadata": row.get("metadata") or {},
            }
            for row in rows[:limit]
        ]

    def save_module_design(self, curriculum_plan_id: str, module_id: str, design: dict[str, Any]) -> None:
        self.module_designs[(curriculum_plan_id, module_id)] = json.loads(json.dumps(design))

    def get_module_design(self, curriculum_plan_id: str, module_id: str, *, learner_id: str | None = None) -> dict[str, Any] | None:
        if learner_id and not self.plan_belongs_to_learner(curriculum_plan_id, learner_id):
            return None
        design = self.module_designs.get((curriculum_plan_id, module_id))
        return json.loads(json.dumps(design)) if design else None

    def plan_belongs_to_learner(self, curriculum_plan_id: str, learner_id: str) -> bool:
        plan = self.plans.get(curriculum_plan_id)
        return bool(plan and plan.get("learner_id") == learner_id)

    def latest_section_insights(self, learner_id: str, section_ids: list[str]) -> list[dict[str, Any]]:
        rows = []
        for section_id in section_ids:
            insight = self.section_insights.get((learner_id, section_id))
            if insight:
                rows.append(json.loads(json.dumps(insight)))
        return rows

    def save_section_insights(self, insights: list[dict[str, Any]]) -> None:
        for insight in insights:
            self.section_insights[(insight["learner_id"], insight["section_id"])] = json.loads(json.dumps(insight))

    def active_hotspots(self, section_ids: list[str] | None = None) -> list[dict[str, Any]]:
        allowed = set(section_ids or [])
        rows = [
            row
            for row in self.hotspots
            if row.get("status") == "active" and (not allowed or row.get("section_id") in allowed)
        ]
        return json.loads(json.dumps(rows))

    def save_checkpoint_result(self, result: dict[str, Any]) -> str:
        key = (result["learner_id"], result["curriculum_plan_id"], result["module_id"])
        self.checkpoint_results[key] = json.loads(json.dumps(result))
        return "checkpoint_attempt:test"

    def update_checkpoint_result(self, checkpoint_attempt_id: str, result: dict[str, Any]) -> None:
        del checkpoint_attempt_id
        key = (result["learner_id"], result["curriculum_plan_id"], result["module_id"])
        self.checkpoint_results[key] = json.loads(json.dumps(result))

    def get_plan_progress(self, curriculum_plan_id: str, *, learner_id: str) -> dict[str, Any]:
        plan = self.get_plan(curriculum_plan_id, learner_id=learner_id) or {}
        modules = sorted(plan.get("modules") or [], key=lambda row: row.get("position") or 0)
        completed = []
        rows = []
        for module in modules:
            module_id = module["module_id"]
            result = self.checkpoint_results.get((learner_id, curriculum_plan_id, module_id))
            is_complete = bool(result and result.get("recommendation") == "continue")
            if is_complete:
                completed.append(module_id)
            rows.append(
                {
                    "module_id": module_id,
                    "position": module["position"],
                    "status": "completed" if is_complete else "needs_review" if result else "not_started",
                    "latest_score": result.get("score") if result else None,
                    "last_attempted_at": None,
                }
            )
        return {
            "curriculum_plan_id": curriculum_plan_id,
            "completed_module_ids": completed,
            "completed_count": len(completed),
            "total_count": len(modules),
            "progress_percentage": round(len(completed) / len(modules) * 100) if modules else 0,
            "modules": rows,
        }

    def get_latest_checkpoint_result(
        self,
        curriculum_plan_id: str,
        module_id: str,
        *,
        learner_id: str | None = None,
    ) -> dict[str, Any] | None:
        if learner_id is None:
            return None
        row = self.checkpoint_results.get((learner_id, curriculum_plan_id, module_id))
        return json.loads(json.dumps(row)) if row else None


class APITest(unittest.TestCase):
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
                        {"id": "section:3", "number": "1.3", "title": "Applications", "content_text": "", "subsections": []},
                    ],
                    "exercises": {"items": []},
                },
            },
        )
        write_json(
            self.root / "data/relationship_artifacts/usable_chapters.json",
            {"usable_chapter_ids": ["chapter:1"]},
        )
        write_jsonl(
            self.root / "data/relationship_artifacts/section_summaries.jsonl",
            [
                {"chapter_id": "chapter:1", "section_id": "section:1", "title": "Units", "summary": "Defines units.", "key_terms": ["unit"]},
                {"chapter_id": "chapter:1", "section_id": "section:2", "title": "SI Units", "summary": "Introduces SI units.", "key_terms": ["SI"]},
                {"chapter_id": "chapter:1", "section_id": "section:3", "title": "Applications", "summary": "Applies SI units.", "key_terms": ["application"]},
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
                {
                    "chapter_id": "chapter:1",
                    "type": "TEACHES_CONCEPT",
                    "from_id": "section:2",
                    "to_id": "concept:si_units",
                    "teaching_evidence": "SI units are introduced.",
                },
                {
                    "chapter_id": "chapter:1",
                    "type": "REQUIRES_CONCEPT",
                    "from_id": "section:2",
                    "to_id": "concept:unit",
                    "pedagogical_reason": "Learners should understand units first.",
                },
                {
                    "chapter_id": "chapter:1",
                    "type": "DEPENDS_ON_UNIT",
                    "from_id": "section:2",
                    "to_id": "section:1",
                    "source_concept_id": "concept:unit",
                    "evidence": {"text": "SI units depend on units.", "reason": "dependency"},
                },
                {
                    "chapter_id": "chapter:1",
                    "type": "TRANSFER_SUPPORTS_UNIT",
                    "from_id": "section:2",
                    "to_id": "section:3",
                    "source_concept_id": "concept:si_units",
                    "evidence": {"text": "Applications support SI units.", "reason": "support"},
                },
            ],
        )
        self.fake_llm = FakeLLM()
        self.repository = FakeRepository()
        self.repository.section_insights[("learner:1", "section:2")] = {
            "insight_id": "section_insight:old",
            "learner_id": "learner:1",
            "curriculum_plan_id": "curriculum_plan:old",
            "module_id": "module:old",
            "section_id": "section:2",
            "understanding_summary": "The learner had partial understanding of SI units.",
            "current_status": "partial_understanding",
            "strengths": [],
            "misconceptions_or_gaps": ["Confuses quantities and units."],
            "recommended_adjustment": "Review SI units carefully.",
            "confidence": 0.7,
            "evidence_question_ids": ["old:q1"],
            "reconciliation_reason": "Prior checkpoint evidence.",
            "created_at": "2026-01-01T00:00:00+00:00",
        }
        self.repository.hotspots.append(
            {
                "hotspot_id": "section_hotspot:si",
                "section_id": "section:2",
                "concept_id": "concept:si_units",
                "misconception_tag": "treats_units_as_quantities",
                "diagnostic_summary": "Many learners treat units as quantities.",
                "reviewed_guidance": "Contrast physical quantities with their measurement units.",
                "suggested_activity_adjustment": "Ask learners to sort examples into quantity and unit.",
                "suggested_checkpoint_focus": "Test quantity-versus-unit distinction.",
                "misconception_rate": 0.5,
                "status": "active",
            }
        )
        service = CurriculumAPIService(
            root=self.root,
            use_vector=False,
            llm_client=self.fake_llm,
            intent_llm_client=self.fake_llm,
            repository=self.repository,  # type: ignore[arg-type]
            auth_verifier=StaticAuthVerifier(AuthUser(user_id="learner:1", email="learner@example.com", role="admin")),
        )
        self.client = TestClient(create_app(service))
        self.auth_headers = {"Authorization": "Bearer test-token"}

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def query_payload(self) -> dict[str, Any]:
        return {
            "onboarding": {
                "subject": "physics",
                "topic": "SI Units",
                "current_level": "beginner",
                "confidence": "low",
                "learning_goal": "solve measurement problems",
                "available_time": "2 hours",
                "preferred_learning_style": "worked examples",
                "deadline_or_pace": "steady",
            },
            "grade": 11,
        }

    def test_me_profile_upserts_authenticated_user(self) -> None:
        response = self.client.get("/api/me/profile", headers=self.auth_headers)

        self.assertEqual(response.status_code, 200)
        profile = response.json()["profile"]
        self.assertEqual(profile["user_id"], "learner:1")
        self.assertEqual(profile["email"], "learner@example.com")
        self.assertEqual(profile["role"], "learner")
        self.assertIn("learner:1", self.repository.profiles)

    def test_me_profile_requires_bearer_token(self) -> None:
        response = self.client.get("/api/me/profile")

        self.assertEqual(response.status_code, 401)

    def test_existing_admin_role_is_preserved_after_profile_sync(self) -> None:
        self.repository.profiles["learner:1"] = {
            "user_id": "learner:1",
            "email": "old@example.com",
            "display_name": "Existing Admin",
            "avatar_url": "",
            "provider": "google",
            "role": "admin",
        }

        response = self.client.get("/api/me/profile", headers=self.auth_headers)

        self.assertEqual(response.status_code, 200)
        profile = response.json()["profile"]
        self.assertEqual(profile["email"], "learner@example.com")
        self.assertEqual(profile["role"], "admin")

    def test_admin_check_uses_database_role_not_verified_token_role(self) -> None:
        response = self.client.get("/api/admin/check", headers=self.auth_headers)

        self.assertEqual(response.status_code, 403)

    def test_admin_check_allows_database_admin_role(self) -> None:
        self.repository.profiles["learner:1"] = {
            "user_id": "learner:1",
            "email": "learner@example.com",
            "display_name": "Admin Learner",
            "avatar_url": "",
            "provider": "google",
            "role": "admin",
        }

        response = self.client.get("/api/admin/check", headers=self.auth_headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["role"], "admin")

    def test_retrieval_preview_endpoint(self) -> None:
        response = self.client.post("/api/retrieval/preview", json=self.query_payload())

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["retrieved_sections"])
        self.assertIn("planning_packet", data)
        self.assertEqual(data["prerequisite_questions"], [])

    def test_intent_classification_endpoint(self) -> None:
        response = self.client.post("/api/intent/classify", json={"query": "SI Units", "grade": 11})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "confirmed")
        self.assertFalse(data["needs_user_choice"])
        self.assertEqual(data["confirmed_intent"]["refined_query"], "SI units and measurement standards")
        self.assertIn("classification_packet", data)

    def test_intent_classification_uses_public_cache_for_same_request(self) -> None:
        first = self.client.post("/api/intent/classify", json={"query": "I want to learn SI Units", "subject": "physics", "grade": 11})
        second = self.client.post("/api/intent/classify", json={"query": "learn si units", "subject": "physics", "grade": 11})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(len(self.fake_llm.prompts), 1)

    def test_intent_cache_is_scoped_by_subject(self) -> None:
        first = self.client.post("/api/intent/classify", json={"query": "SI Units", "subject": "physics", "grade": 11})
        second = self.client.post("/api/intent/classify", json={"query": "SI Units", "subject": "chemistry", "grade": 11})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(len(self.fake_llm.prompts), 2)

    def test_retrieval_preview_stores_public_cache_entry(self) -> None:
        first = self.client.post("/api/retrieval/preview", json=self.query_payload())
        cache_entries_after_first = len(self.repository.public_cache)
        second = self.client.post("/api/retrieval/preview", json=self.query_payload())

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(cache_entries_after_first, 1)
        self.assertEqual(len(self.repository.public_cache), 1)
        self.assertEqual(first.json()["planning_packet"], second.json()["planning_packet"])

    def test_curriculum_plan_cache_reuses_template_with_fresh_guest_ids(self) -> None:
        first = self.client.post("/api/curriculum/plan", json=self.query_payload())
        second = self.client.post("/api/curriculum/plan", json=self.query_payload())

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertNotEqual(first.json()["curriculum_plan_id"], second.json()["curriculum_plan_id"])
        planner_prompts = [prompt for prompt in self.fake_llm.prompts if "Now create the ordered curriculum module sequence" in prompt]
        self.assertEqual(len(planner_prompts), 1)

    def test_fireworks_overload_returns_provider_status(self) -> None:
        class OverloadedLLM:
            def generate_json(self, prompt: str, schema: dict[str, Any] | None = None) -> dict[str, Any]:
                raise FireworksAPIError("Fireworks API error 503: service overloaded", status_code=503)

        service = CurriculumAPIService(
            root=self.root,
            use_vector=False,
            llm_client=OverloadedLLM(),
            intent_llm_client=OverloadedLLM(),
            repository=self.repository,  # type: ignore[arg-type]
            auth_verifier=StaticAuthVerifier(AuthUser(user_id="learner:1", email="learner@example.com", role="admin")),
        )
        client = TestClient(create_app(service))

        response = client.post("/api/intent/classify", json={"query": "SI Units", "grade": 11})

        self.assertEqual(response.status_code, 503)
        self.assertIn("service overloaded", response.json()["detail"])

    def test_plan_module_design_and_checkpoint_submit_endpoints(self) -> None:
        plan_response = self.client.post("/api/curriculum/plan", json=self.query_payload())
        self.assertEqual(plan_response.status_code, 200)
        plan = plan_response.json()
        self.assertEqual(plan["learner_id"], "guest")
        self.assertEqual(plan["modules"][0]["module_id"], "module:si")
        self.assertIn("mcq_allocation", plan)
        self.assertNotIn(plan["curriculum_plan_id"], self.repository.plans)

        design_response = self.client.post(
            "/api/modules/design",
            json={"curriculum_plan_id": plan["curriculum_plan_id"], "module_id": "module:si", "plan": plan},
            headers=self.auth_headers,
        )
        self.assertEqual(design_response.status_code, 200)
        self.assertEqual(self.repository.plans[plan["curriculum_plan_id"]]["learner_id"], "learner:1")
        module = design_response.json()
        self.assertEqual(len(module["checkpoint_mcqs"]), plan["mcq_allocation"]["module:si"])
        self.assertTrue(module["metadata"]["module_design_id"].startswith("module_design:"))
        packet = module["metadata"]["module_expansion_packet"]
        self.assertEqual(packet["section_hotspots"][0]["hotspot_id"], "section_hotspot:si")

        submit_response = self.client.post(
            "/api/checkpoints/submit",
            json={
                "curriculum_plan_id": plan["curriculum_plan_id"],
                "module_id": "module:si",
                "answers": [
                    {"question_id": mcq["question_id"], "selected_option_id": "A"}
                    for mcq in module["checkpoint_mcqs"]
                ],
            },
            headers=self.auth_headers,
        )
        self.assertEqual(submit_response.status_code, 200)
        result = submit_response.json()
        self.assertEqual(result["score"], 1.0)
        self.assertEqual(result["module_design_id"], module["metadata"]["module_design_id"])
        self.assertEqual(result["overall_feedback"], "The submitted responses show a sound understanding of SI units.")
        self.assertEqual(result["insight_generation_status"], "complete")
        self.assertEqual(result["section_insights"][0]["section_id"], "section:2")
        self.assertEqual(result["section_insights"][0]["supersedes_insight_id"], "section_insight:old")
        self.assertTrue(any("existing_section_insights" in prompt for prompt in self.fake_llm.prompts))

        progress_response = self.client.get(
            f"/api/curriculum/plans/{plan['curriculum_plan_id']}/progress",
            headers=self.auth_headers,
        )
        self.assertEqual(progress_response.status_code, 200)
        self.assertEqual(progress_response.json()["completed_module_ids"], ["module:si"])

    def test_module_design_claims_matching_guest_plan_payload(self) -> None:
        plan_response = self.client.post("/api/curriculum/plan", json=self.query_payload())
        self.assertEqual(plan_response.status_code, 200)
        plan = plan_response.json()

        response = self.client.post(
            "/api/modules/design",
            json={"curriculum_plan_id": plan["curriculum_plan_id"], "module_id": "module:si", "plan": plan},
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.repository.plans[plan["curriculum_plan_id"]]["learner_id"], "learner:1")

    def test_module_design_rejects_mismatched_guest_plan_payload(self) -> None:
        plan_response = self.client.post("/api/curriculum/plan", json=self.query_payload())
        self.assertEqual(plan_response.status_code, 200)
        plan = plan_response.json()

        response = self.client.post(
            "/api/modules/design",
            json={"curriculum_plan_id": "curriculum_plan:other", "module_id": "module:si", "plan": plan},
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 422)

    def test_module_design_does_not_claim_plan_owned_by_another_user(self) -> None:
        plan_response = self.client.post("/api/curriculum/plan", json=self.query_payload())
        self.assertEqual(plan_response.status_code, 200)
        plan = plan_response.json()
        stored = dict(plan)
        stored["learner_id"] = "learner:other"
        self.repository.save_plan(stored)

        response = self.client.post(
            "/api/modules/design",
            json={"curriculum_plan_id": plan["curriculum_plan_id"], "module_id": "module:si", "plan": plan},
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.repository.plans[plan["curriculum_plan_id"]]["learner_id"], "learner:other")

    def test_checkpoint_submit_rejects_client_owned_mcq_payload(self) -> None:
        plan_response = self.client.post("/api/curriculum/plan", json=self.query_payload())
        plan = plan_response.json()
        design_response = self.client.post(
            "/api/modules/design",
            json={"curriculum_plan_id": plan["curriculum_plan_id"], "module_id": "module:si", "plan": plan},
            headers=self.auth_headers,
        )
        module = design_response.json()

        response = self.client.post(
            "/api/checkpoints/submit",
            json={
                "curriculum_plan_id": plan["curriculum_plan_id"],
                "module_id": "module:si",
                "checkpoint_mcqs": module["checkpoint_mcqs"],
                "answers": [
                    {"question_id": mcq["question_id"], "selected_option_id": "A"}
                    for mcq in module["checkpoint_mcqs"]
                ],
            },
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 422)

    def test_checkpoint_submit_requires_stored_module_design(self) -> None:
        plan_response = self.client.post("/api/curriculum/plan", json=self.query_payload())
        plan = plan_response.json()
        claimed = dict(plan)
        claimed["learner_id"] = "learner:1"
        self.repository.save_plan(claimed)

        response = self.client.post(
            "/api/checkpoints/submit",
            json={
                "curriculum_plan_id": plan["curriculum_plan_id"],
                "module_id": "module:si",
                "answers": [{"question_id": "module:si:q1", "selected_option_id": "A"}],
            },
            headers=self.auth_headers,
        )

        self.assertEqual(response.status_code, 404)

    def test_base_schema_does_not_delete_anonymous_demo_data(self) -> None:
        schema = (Path(__file__).resolve().parents[1] / "database/schema.sql").read_text(encoding="utf-8").lower()

        self.assertNotIn("delete from learners", schema)
        self.assertIn("alter table user_profiles enable row level security", schema)
        self.assertIn("alter table checkpoint_answers enable row level security", schema)
        self.assertIn("selected_option_id text not null", schema)
        self.assertIn("correct_option_id text not null", schema)


if __name__ == "__main__":
    unittest.main()
