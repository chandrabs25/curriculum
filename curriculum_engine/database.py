"""Postgres persistence for curriculum app state and pgvector retrieval."""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def database_url() -> str | None:
    return os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL")


def repository_from_env() -> "PostgresRepository | None":
    url = database_url()
    return PostgresRepository(url) if url else None


@dataclass
class PostgresRepository:
    url: str
    _pool: Any = field(init=False, repr=False)

    def __post_init__(self) -> None:
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool

        self._pool = ConnectionPool(
            conninfo=self.url,
            min_size=0,
            max_size=max(1, int(os.getenv("DATABASE_POOL_MAX_SIZE", "8"))),
            timeout=float(os.getenv("DATABASE_POOL_TIMEOUT_SECONDS", "10")),
            kwargs={
                "row_factory": dict_row,
                "prepare_threshold": None,
                "connect_timeout": int(os.getenv("DATABASE_CONNECT_TIMEOUT_SECONDS", "10")),
            },
            open=True,
        )

    def _connect(self):
        return self._pool.connection()

    def close(self) -> None:
        self._pool.close()

    def health(self) -> dict[str, Any]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("select count(*) as count from section_embedding_documents")
                row = cur.fetchone() or {"count": 0}
        return {"ok": True, "section_embedding_documents": int(row["count"])}

    def get_public_response_cache(self, cache_key: str) -> dict[str, Any] | None:
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        select response_payload
                        from public_response_cache
                        where cache_key = %s and expires_at > now()
                        """,
                        (cache_key,),
                    )
                    row = cur.fetchone()
        except Exception:
            return None
        return dict(row["response_payload"]) if row else None

    def set_public_response_cache(
        self,
        *,
        cache_key: str,
        cache_kind: str,
        response_payload: dict[str, Any],
        expires_at: str,
    ) -> None:
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        insert into public_response_cache(cache_key, cache_kind, response_payload, expires_at, updated_at)
                        values (%s, %s, %s::jsonb, %s::timestamptz, now())
                        on conflict (cache_key) do update set
                          cache_kind = excluded.cache_kind,
                          response_payload = excluded.response_payload,
                          expires_at = excluded.expires_at,
                          updated_at = now()
                        """,
                        (cache_key, cache_kind, _json(response_payload), expires_at),
                    )
        except Exception:
            return

    def upsert_user_profile(self, profile: dict[str, Any]) -> dict[str, Any] | None:
        user_id = str(profile.get("user_id") or "")
        if not user_id:
            return None
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into user_profiles(user_id, email, display_name, avatar_url, provider, updated_at, last_seen_at)
                    values (%s, nullif(%s, ''), %s, %s, %s, now(), now())
                    on conflict (user_id) do update set
                      email = coalesce(excluded.email, user_profiles.email),
                      display_name = excluded.display_name,
                      avatar_url = excluded.avatar_url,
                      provider = excluded.provider,
                      updated_at = case
                        when user_profiles.email is distinct from coalesce(excluded.email, user_profiles.email)
                          or user_profiles.display_name is distinct from excluded.display_name
                          or user_profiles.avatar_url is distinct from excluded.avatar_url
                          or user_profiles.provider is distinct from excluded.provider
                        then now() else user_profiles.updated_at
                      end,
                      last_seen_at = case
                        when user_profiles.last_seen_at < now() - interval '15 minutes'
                        then now() else user_profiles.last_seen_at
                      end
                    """,
                    (
                        user_id,
                        profile.get("email") or "",
                        profile.get("display_name") or "",
                        profile.get("avatar_url") or "",
                        profile.get("provider") or "google",
                    ),
                )
                cur.execute(
                    """
                    insert into learners(learner_id)
                    values (%s)
                    on conflict (learner_id) do nothing
                    """,
                    (user_id,),
                )
                cur.execute("select * from user_profiles where user_id = %s", (user_id,))
                row = cur.fetchone()
        return _profile_row(row) if row else None

    def get_user_profile(self, user_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("select * from user_profiles where user_id = %s", (user_id,))
                row = cur.fetchone()
        if not row:
            return None
        return _profile_row(row)

    def save_plan(self, plan: dict[str, Any]) -> None:
        learner_id = str(plan["learner_id"])
        plan_id = str(plan["curriculum_plan_id"])
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into curriculum_plans(curriculum_plan_id, learner_id, onboarding, metadata, mcq_allocation, created_at, updated_at)
                    values (%s, %s, %s::jsonb, %s::jsonb, %s::jsonb, coalesce(%s::timestamptz, now()), now())
                    on conflict (curriculum_plan_id) do update set
                      learner_id = excluded.learner_id,
                      onboarding = excluded.onboarding,
                      metadata = excluded.metadata,
                      mcq_allocation = excluded.mcq_allocation,
                      updated_at = now()
                    """,
                    (
                        plan_id,
                        learner_id,
                        _json(plan.get("onboarding") or {}),
                        _json(plan.get("metadata") or {}),
                        _json(plan.get("mcq_allocation") or {}),
                        plan.get("created_at"),
                    ),
                )
                for module in plan.get("modules") or []:
                    cur.execute(
                        """
                        insert into curriculum_modules(curriculum_plan_id, module_id, position, module_payload, updated_at)
                        values (%s, %s, %s, %s::jsonb, now())
                        on conflict (curriculum_plan_id, module_id) do update set
                          position = excluded.position,
                          module_payload = excluded.module_payload,
                          updated_at = now()
                        """,
                        (
                            plan_id,
                            module.get("module_id"),
                            int(module.get("position") or 0),
                            _json(module),
                        ),
                    )

    def get_plan(self, curriculum_plan_id: str, *, learner_id: str | None = None) -> dict[str, Any] | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                where = "where curriculum_plan_id = %s"
                params: tuple[Any, ...] = (curriculum_plan_id,)
                if learner_id:
                    where += " and learner_id = %s"
                    params = (curriculum_plan_id, learner_id)
                cur.execute(
                    f"""
                    select curriculum_plan_id, learner_id, onboarding, metadata, mcq_allocation, created_at
                    from curriculum_plans
                    {where}
                    """,
                    params,
                )
                plan = cur.fetchone()
                if not plan:
                    return None
                cur.execute(
                    """
                    select module_payload
                    from curriculum_modules
                    where curriculum_plan_id = %s
                    order by position asc
                    """,
                    (curriculum_plan_id,),
                )
                modules = [dict(row["module_payload"]) for row in cur.fetchall()]
        return {
            "curriculum_plan_id": plan["curriculum_plan_id"],
            "learner_id": plan["learner_id"],
            "onboarding": plan["onboarding"],
            "modules": modules,
            "created_at": plan["created_at"].isoformat() if plan.get("created_at") else None,
            "metadata": plan["metadata"] or {},
            "mcq_allocation": plan["mcq_allocation"] or {},
        }

    def list_plans(self, learner_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select p.curriculum_plan_id, p.learner_id, p.onboarding, p.metadata,
                           p.created_at, count(m.module_id) as module_count
                    from curriculum_plans p
                    left join curriculum_modules m on m.curriculum_plan_id = p.curriculum_plan_id
                    where p.learner_id = %s
                    group by p.curriculum_plan_id
                    order by p.created_at desc
                    limit %s
                    """,
                    (learner_id, int(limit)),
                )
                rows = cur.fetchall()
        plans = []
        for row in rows:
            onboarding = row["onboarding"] or {}
            plans.append(
                {
                    "curriculum_plan_id": row["curriculum_plan_id"],
                    "learner_id": row["learner_id"],
                    "topic": onboarding.get("topic") or "",
                    "subject": onboarding.get("subject") or "",
                    "module_count": int(row["module_count"] or 0),
                    "created_at": row["created_at"].isoformat() if row.get("created_at") else "",
                    "metadata": row["metadata"] or {},
                }
            )
        return plans

    def save_module_design(self, curriculum_plan_id: str, module_id: str, design: dict[str, Any]) -> None:
        metadata = design.get("metadata") if isinstance(design.get("metadata"), dict) else {}
        module_design_id = str(metadata.get("module_design_id") or design.get("module_design_id") or "")
        if not module_design_id:
            raise ValueError("module_design_id is required to save a module design")
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into module_designs(curriculum_plan_id, module_id, module_design_id, design_payload, updated_at)
                    values (%s, %s, %s, %s::jsonb, now())
                    on conflict (curriculum_plan_id, module_id) do update set
                      module_design_id = excluded.module_design_id,
                      design_payload = excluded.design_payload,
                      updated_at = now()
                    """,
                    (curriculum_plan_id, module_id, module_design_id, _json(design)),
                )
                if module_design_id:
                    cur.execute(
                        """
                        insert into module_design_versions(module_design_id, curriculum_plan_id, module_id, design_payload)
                        values (%s, %s, %s, %s::jsonb)
                        on conflict (module_design_id) do update set
                          design_payload = excluded.design_payload
                        """,
                        (module_design_id, curriculum_plan_id, module_id, _json(design)),
                    )

    def get_module_design(self, curriculum_plan_id: str, module_id: str, *, learner_id: str | None = None) -> dict[str, Any] | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                if learner_id:
                    cur.execute(
                        """
                        select d.module_design_id, d.design_payload
                        from module_designs d
                        join curriculum_plans p on p.curriculum_plan_id = d.curriculum_plan_id
                        where d.curriculum_plan_id = %s and d.module_id = %s and p.learner_id = %s
                        """,
                        (curriculum_plan_id, module_id, learner_id),
                    )
                else:
                    cur.execute(
                        """
                        select module_design_id, design_payload
                        from module_designs
                        where curriculum_plan_id = %s and module_id = %s
                        """,
                        (curriculum_plan_id, module_id),
                    )
                row = cur.fetchone()
        if not row:
            return None
        design = dict(row["design_payload"])
        metadata = design.get("metadata") if isinstance(design.get("metadata"), dict) else {}
        if row.get("module_design_id") and not metadata.get("module_design_id"):
            metadata["module_design_id"] = row["module_design_id"]
            design["metadata"] = metadata
        return design

    def plan_belongs_to_learner(self, curriculum_plan_id: str, learner_id: str) -> bool:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select 1
                    from curriculum_plans
                    where curriculum_plan_id = %s and learner_id = %s
                    limit 1
                    """,
                    (curriculum_plan_id, learner_id),
                )
                row = cur.fetchone()
        return bool(row)

    def latest_section_insights(self, learner_id: str, section_ids: list[str]) -> list[dict[str, Any]]:
        if not section_ids:
            return []
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select *
                    from section_learning_insights
                    where learner_id = %s and section_id = any(%s) and is_latest = true
                    order by created_at desc
                    """,
                    (learner_id, section_ids),
                )
                rows = cur.fetchall()
        return [_insight_row(row) for row in rows]

    @staticmethod
    def _save_section_insights(cur: Any, insights: list[dict[str, Any]]) -> None:
        for insight in insights:
            learner_id = str(insight.get("learner_id") or "")
            section_id = str(insight.get("section_id") or "")
            if not learner_id or not section_id:
                continue
            cur.execute(
                """
                update section_learning_insights
                set is_latest = false
                where learner_id = %s and section_id = %s and is_latest = true
                """,
                (learner_id, section_id),
            )
            cur.execute(
                """
                insert into section_learning_insights(
                  insight_id, learner_id, curriculum_plan_id, module_id, section_id,
                  current_status, understanding_summary, strengths, misconceptions_or_gaps,
                  recommended_adjustment, confidence, evidence_question_ids,
                  supersedes_insight_id, reconciliation_reason, is_latest, created_at
                )
                values (
                  %s, %s, %s, %s, %s,
                  %s, %s, %s::jsonb, %s::jsonb,
                  %s, %s, %s::jsonb,
                  %s, %s, true, coalesce(%s::timestamptz, now())
                )
                on conflict (insight_id) do update set
                  current_status = excluded.current_status,
                  understanding_summary = excluded.understanding_summary,
                  strengths = excluded.strengths,
                  misconceptions_or_gaps = excluded.misconceptions_or_gaps,
                  recommended_adjustment = excluded.recommended_adjustment,
                  confidence = excluded.confidence,
                  evidence_question_ids = excluded.evidence_question_ids,
                  reconciliation_reason = excluded.reconciliation_reason,
                  is_latest = true
                """,
                (
                    insight.get("insight_id"),
                    learner_id,
                    insight.get("curriculum_plan_id"),
                    insight.get("module_id"),
                    section_id,
                    insight.get("current_status") or "uncertain",
                    insight.get("understanding_summary") or "",
                    _json(insight.get("strengths") or []),
                    _json(insight.get("misconceptions_or_gaps") or []),
                    insight.get("recommended_adjustment") or "",
                    float(insight.get("confidence") or 0.0),
                    _json(insight.get("evidence_question_ids") or []),
                    insight.get("supersedes_insight_id"),
                    insight.get("reconciliation_reason") or "",
                    insight.get("created_at"),
                ),
            )

    def save_checkpoint_result(self, result: dict[str, Any]) -> str:
        attempt_id = "checkpoint_attempt:" + uuid.uuid4().hex[:16]
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into checkpoint_attempts(
                      checkpoint_attempt_id, learner_id, curriculum_plan_id, module_id,
                      module_design_id, score, correct_count, total_count, recommendation, result_payload
                    )
                    values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        attempt_id,
                        result.get("learner_id"),
                        result.get("curriculum_plan_id"),
                        result.get("module_id"),
                        result.get("module_design_id") or "",
                        float(result.get("score") or 0.0),
                        int(result.get("correct_count") or 0),
                        int(result.get("total_count") or 0),
                        result.get("recommendation") or "",
                        _json(result),
                    ),
                )
                for row in result.get("question_results") or []:
                    cur.execute(
                        """
                        insert into checkpoint_answers(
                          checkpoint_attempt_id, question_id, selected_option_id, correct_option_id, is_correct,
                          source_section_ids, tested_concept_ids, diagnostic_purpose, misconception_tags
                        )
                        values (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s::jsonb)
                        """,
                        (
                            attempt_id,
                            row.get("question_id"),
                            row.get("selected_option_id") or "",
                            row.get("correct_option_id") or "",
                            bool(row.get("is_correct")),
                            _json(row.get("source_section_ids") or []),
                            _json(row.get("tested_concept_ids") or []),
                            row.get("diagnostic_purpose") or "",
                            _json(row.get("misconception_tags") or []),
                        ),
                    )
        return attempt_id

    def update_checkpoint_result(self, checkpoint_attempt_id: str, result: dict[str, Any]) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update checkpoint_attempts
                    set result_payload = %s::jsonb
                    where checkpoint_attempt_id = %s
                    """,
                    (_json(result), checkpoint_attempt_id),
                )

    def finalize_checkpoint_result(
        self,
        checkpoint_attempt_id: str,
        result: dict[str, Any],
        section_insights: list[dict[str, Any]],
    ) -> None:
        """Commit reconciled insights and the completed attempt as one transaction."""
        with self._connect() as conn:
            with conn.cursor() as cur:
                self._save_section_insights(cur, section_insights)
                cur.execute(
                    """
                    update checkpoint_attempts
                    set result_payload = %s::jsonb
                    where checkpoint_attempt_id = %s
                    """,
                    (_json(result), checkpoint_attempt_id),
                )

    def get_plan_progress(self, curriculum_plan_id: str, *, learner_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select module_id, position
                    from curriculum_modules
                    where curriculum_plan_id = %s
                    order by position
                    """,
                    (curriculum_plan_id,),
                )
                modules = cur.fetchall()
                cur.execute(
                    """
                    select distinct on (module_id) module_id, recommendation, score, created_at
                    from checkpoint_attempts
                    where curriculum_plan_id = %s and learner_id = %s
                    order by module_id, created_at desc
                    """,
                    (curriculum_plan_id, learner_id),
                )
                latest_attempts = {row["module_id"]: row for row in cur.fetchall()}
        rows = []
        completed_module_ids = []
        for module in modules:
            module_id = str(module["module_id"])
            attempt = latest_attempts.get(module_id)
            completed = bool(attempt and attempt["recommendation"] == "continue")
            if completed:
                completed_module_ids.append(module_id)
            rows.append(
                {
                    "module_id": module_id,
                    "position": int(module["position"]),
                    "status": "completed" if completed else "needs_review" if attempt else "not_started",
                    "latest_score": float(attempt["score"]) if attempt else None,
                    "last_attempted_at": attempt["created_at"].isoformat() if attempt else None,
                }
            )
        total = len(rows)
        return {
            "curriculum_plan_id": curriculum_plan_id,
            "completed_module_ids": completed_module_ids,
            "completed_count": len(completed_module_ids),
            "total_count": total,
            "progress_percentage": round((len(completed_module_ids) / total) * 100) if total else 0,
            "modules": rows,
        }

    def checkpoint_hotspot_evidence(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select
                      a.learner_id,
                      a.module_design_id,
                      a.created_at,
                      q.question_id,
                      q.is_correct,
                      q.source_section_ids,
                      q.tested_concept_ids,
                      q.diagnostic_purpose,
                      q.misconception_tags
                    from checkpoint_answers q
                    join checkpoint_attempts a on a.checkpoint_attempt_id = q.checkpoint_attempt_id
                    """
                )
                rows = cur.fetchall()
        return [
            {
                "learner_id": row["learner_id"],
                "module_design_id": row["module_design_id"] or "",
                "created_at": row["created_at"].isoformat() if row.get("created_at") else "",
                "question_id": row["question_id"],
                "is_correct": bool(row["is_correct"]),
                "source_section_ids": row["source_section_ids"] or [],
                "tested_concept_ids": row["tested_concept_ids"] or [],
                "diagnostic_purpose": row["diagnostic_purpose"] or "",
                "misconception_tags": row["misconception_tags"] or [],
            }
            for row in rows
        ]

    def active_hotspots(self, section_ids: list[str] | None = None) -> list[dict[str, Any]]:
        where = "where status = 'active'"
        params: tuple[Any, ...] = ()
        if section_ids:
            where += " and section_id = any(%s)"
            params = (section_ids,)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(f"select * from section_misunderstanding_hotspots {where}", params)
                rows = cur.fetchall()
        return [_hotspot_row(row) for row in rows]

    def save_hotspots(self, hotspots: list[dict[str, Any]]) -> None:
        if not hotspots:
            return
        with self._connect() as conn:
            with conn.cursor() as cur:
                for hotspot in hotspots:
                    cur.execute(
                        """
                        insert into section_misunderstanding_hotspots(
                          hotspot_id, section_id, concept_id, misconception_tag,
                          evidence_window_start, evidence_window_end, module_design_ids,
                          attempt_count, wrong_count, unique_learner_count, distinct_question_count,
                          misconception_rate, diagnostic_summary, proposed_guidance, reviewed_guidance,
                          suggested_activity_adjustment, suggested_checkpoint_focus,
                          status, activated_at, created_at, updated_at
                        )
                        values (
                          %s, %s, %s, %s,
                          nullif(%s, '')::timestamptz, nullif(%s, '')::timestamptz, %s::jsonb,
                          %s, %s, %s, %s,
                          %s, %s, %s, %s,
                          %s, %s,
                          %s, nullif(%s, '')::timestamptz, coalesce(nullif(%s, '')::timestamptz, now()), now()
                        )
                        on conflict (hotspot_id) do update set
                          evidence_window_end = excluded.evidence_window_end,
                          module_design_ids = excluded.module_design_ids,
                          attempt_count = excluded.attempt_count,
                          wrong_count = excluded.wrong_count,
                          unique_learner_count = excluded.unique_learner_count,
                          distinct_question_count = excluded.distinct_question_count,
                          misconception_rate = excluded.misconception_rate,
                          diagnostic_summary = excluded.diagnostic_summary,
                          proposed_guidance = excluded.proposed_guidance,
                          reviewed_guidance = case
                            when section_misunderstanding_hotspots.status = 'active' then section_misunderstanding_hotspots.reviewed_guidance
                            when excluded.reviewed_guidance = '' then section_misunderstanding_hotspots.reviewed_guidance
                            else excluded.reviewed_guidance
                          end,
                          suggested_activity_adjustment = excluded.suggested_activity_adjustment,
                          suggested_checkpoint_focus = excluded.suggested_checkpoint_focus,
                          status = case
                            when section_misunderstanding_hotspots.status = 'active' then section_misunderstanding_hotspots.status
                            else excluded.status
                          end,
                          activated_at = coalesce(section_misunderstanding_hotspots.activated_at, excluded.activated_at),
                          updated_at = now()
                        """,
                        (
                            hotspot.get("hotspot_id"),
                            hotspot.get("section_id"),
                            hotspot.get("concept_id"),
                            hotspot.get("misconception_tag"),
                            hotspot.get("evidence_window_start") or "",
                            hotspot.get("evidence_window_end") or "",
                            _json(hotspot.get("module_design_ids") or []),
                            int(hotspot.get("attempt_count") or 0),
                            int(hotspot.get("wrong_count") or 0),
                            int(hotspot.get("unique_learner_count") or 0),
                            int(hotspot.get("distinct_question_count") or 0),
                            float(hotspot.get("misconception_rate") or 0.0),
                            hotspot.get("diagnostic_summary") or "",
                            hotspot.get("proposed_guidance") or "",
                            hotspot.get("reviewed_guidance") or "",
                            hotspot.get("suggested_activity_adjustment") or "",
                            hotspot.get("suggested_checkpoint_focus") or "",
                            hotspot.get("status") or "candidate",
                            hotspot.get("activated_at") or "",
                            hotspot.get("created_at") or "",
                        ),
                    )

    def update_hotspot_status(
        self,
        hotspot_id: str,
        status: str,
        *,
        reviewed_guidance: str | None = None,
        suggested_activity_adjustment: str | None = None,
        suggested_checkpoint_focus: str | None = None,
    ) -> None:
        if status not in {"candidate", "active", "rejected", "resolved", "superseded"}:
            raise ValueError(f"Invalid hotspot status: {status}")
        if status == "active" and not reviewed_guidance:
            raise ValueError("reviewed_guidance is required to activate a hotspot")
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update section_misunderstanding_hotspots
                    set status = %s,
                        reviewed_guidance = coalesce(%s, reviewed_guidance),
                        suggested_activity_adjustment = coalesce(%s, suggested_activity_adjustment),
                        suggested_checkpoint_focus = coalesce(%s, suggested_checkpoint_focus),
                        activated_at = case
                          when %s = 'active' then now()
                          else activated_at
                        end,
                        updated_at = now()
                    where hotspot_id = %s
                    """,
                    (status, reviewed_guidance, suggested_activity_adjustment, suggested_checkpoint_focus, status, hotspot_id),
                )

    def get_latest_checkpoint_result(self, curriculum_plan_id: str, module_id: str, *, learner_id: str | None = None) -> dict[str, Any] | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                where = "where curriculum_plan_id = %s and module_id = %s"
                params: tuple[Any, ...] = (curriculum_plan_id, module_id)
                if learner_id:
                    where += " and learner_id = %s"
                    params = (curriculum_plan_id, module_id, learner_id)
                cur.execute(
                    f"""
                    select result_payload
                    from checkpoint_attempts
                    {where}
                    order by created_at desc
                    limit 1
                    """,
                    params,
                )
                row = cur.fetchone()
        return dict(row["result_payload"]) if row else None

    def search_section_embeddings(
        self,
        query_vector: list[float],
        *,
        limit: int,
        subject: str | None = None,
        grade: int | None = None,
        chapter_id: str | None = None,
    ) -> list[dict[str, Any]]:
        where = []
        params: list[Any] = []
        if subject:
            where.append("subject = %s")
            params.append(subject)
        if grade is not None:
            where.append("grade = %s")
            params.append(int(grade))
        if chapter_id:
            where.append("chapter_id = %s")
            params.append(chapter_id)
        where_sql = f"where {' and '.join(where)}" if where else ""
        vector = _vector_literal(query_vector)
        query_params = [vector, *params, vector, int(limit)]
        sql = f"""
            select section_id, 1 - (embedding <=> %s::vector) as score
            from section_embedding_documents
            {where_sql}
            order by embedding <=> %s::vector
            limit %s
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, query_params)
                rows = cur.fetchall()
        return [{"section_id": row["section_id"], "score": float(row["score"])} for row in rows]

    # ------------------------------------------------------------------
    # Admin queries
    # ------------------------------------------------------------------

    def admin_dashboard_stats(self) -> dict[str, Any]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("select count(*) as c from learners")
                learner_count = int((cur.fetchone() or {"c": 0})["c"])

                cur.execute("select count(*) as c from curriculum_plans")
                plan_count = int((cur.fetchone() or {"c": 0})["c"])

                cur.execute("select count(*) as c from checkpoint_attempts")
                attempt_count = int((cur.fetchone() or {"c": 0})["c"])

                cur.execute("select count(*) as c from section_embedding_documents")
                embedding_count = int((cur.fetchone() or {"c": 0})["c"])

                cur.execute(
                    """
                    select status, count(*) as c
                    from section_misunderstanding_hotspots
                    group by status
                    """
                )
                hotspot_rows = cur.fetchall()
                hotspots_by_status = {row["status"]: int(row["c"]) for row in hotspot_rows}

        return {
            "learner_count": learner_count,
            "plan_count": plan_count,
            "checkpoint_attempt_count": attempt_count,
            "embedding_count": embedding_count,
            "hotspots_by_status": hotspots_by_status,
        }

    def admin_list_learners(
        self, *, limit: int = 50, offset: int = 0, search: str = ""
    ) -> dict[str, Any]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                where = ""
                params: list[Any] = []
                if search:
                    where = "where u.email ilike %s or u.display_name ilike %s"
                    pattern = f"%{search}%"
                    params = [pattern, pattern]

                cur.execute(
                    f"""
                    select u.user_id, u.email, u.display_name, u.avatar_url,
                           u.provider, u.role, u.created_at, u.last_seen_at,
                           count(distinct p.curriculum_plan_id) as plan_count,
                           count(distinct ca.checkpoint_attempt_id) as attempt_count
                    from user_profiles u
                    left join curriculum_plans p on p.learner_id = u.user_id
                    left join checkpoint_attempts ca on ca.learner_id = u.user_id
                    {where}
                    group by u.user_id
                    order by u.last_seen_at desc nulls last
                    limit %s offset %s
                    """,
                    [*params, limit, offset],
                )
                rows = cur.fetchall()

                count_params = list(params)
                cur.execute(
                    f"select count(*) as c from user_profiles u {where}",
                    count_params,
                )
                total = int((cur.fetchone() or {"c": 0})["c"])

        return {
            "learners": [
                {
                    "user_id": row["user_id"],
                    "email": row["email"] or "",
                    "display_name": row["display_name"] or "",
                    "avatar_url": row["avatar_url"] or "",
                    "provider": row["provider"] or "google",
                    "role": row.get("role") or "learner",
                    "created_at": row["created_at"].isoformat() if row.get("created_at") else "",
                    "last_seen_at": row["last_seen_at"].isoformat() if row.get("last_seen_at") else "",
                    "plan_count": int(row["plan_count"] or 0),
                    "attempt_count": int(row["attempt_count"] or 0),
                }
                for row in rows
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def admin_get_learner_detail(self, user_id: str) -> dict[str, Any] | None:
        profile = self.get_user_profile(user_id)
        if not profile:
            return None
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select curriculum_plan_id, onboarding, metadata, created_at,
                           (select count(*) from curriculum_modules m where m.curriculum_plan_id = p.curriculum_plan_id) as module_count
                    from curriculum_plans p
                    where learner_id = %s
                    order by created_at desc
                    """,
                    (user_id,),
                )
                plan_rows = cur.fetchall()

                cur.execute(
                    """
                    select checkpoint_attempt_id, curriculum_plan_id, module_id,
                           score, correct_count, total_count, recommendation, created_at
                    from checkpoint_attempts
                    where learner_id = %s
                    order by created_at desc
                    limit 50
                    """,
                    (user_id,),
                )
                checkpoint_rows = cur.fetchall()

        plans = []
        for row in plan_rows:
            onboarding = row["onboarding"] or {}
            plans.append({
                "curriculum_plan_id": row["curriculum_plan_id"],
                "topic": onboarding.get("topic") or "",
                "subject": onboarding.get("subject") or "",
                "module_count": int(row["module_count"] or 0),
                "created_at": row["created_at"].isoformat() if row.get("created_at") else "",
            })

        checkpoints = []
        for row in checkpoint_rows:
            checkpoints.append({
                "checkpoint_attempt_id": row["checkpoint_attempt_id"],
                "curriculum_plan_id": row["curriculum_plan_id"],
                "module_id": row["module_id"],
                "score": float(row["score"] or 0),
                "correct_count": int(row["correct_count"] or 0),
                "total_count": int(row["total_count"] or 0),
                "recommendation": row["recommendation"] or "",
                "created_at": row["created_at"].isoformat() if row.get("created_at") else "",
            })

        return {
            "profile": profile,
            "plans": plans,
            "checkpoints": checkpoints,
        }

    def admin_list_hotspots(
        self, *, status: str | None = None, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        where = ""
        params: list[Any] = []
        if status:
            where = "where status = %s"
            params = [status]
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    select *
                    from section_misunderstanding_hotspots
                    {where}
                    order by updated_at desc
                    limit %s offset %s
                    """,
                    [*params, limit, offset],
                )
                rows = cur.fetchall()

                cur.execute(
                    f"select count(*) as c from section_misunderstanding_hotspots {where}",
                    params,
                )
                total = int((cur.fetchone() or {"c": 0})["c"])

        return {
            "hotspots": [_hotspot_row(row) for row in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def admin_get_hotspot(self, hotspot_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select * from section_misunderstanding_hotspots where hotspot_id = %s",
                    (hotspot_id,),
                )
                row = cur.fetchone()
        if not row:
            return None
        return _hotspot_row(row)

    def admin_content_stats(self) -> dict[str, Any]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select coalesce(subject, 'unknown') as subject,
                           coalesce(grade, 0) as grade,
                           count(*) as section_count
                    from section_embedding_documents
                    group by subject, grade
                    order by subject, grade
                    """
                )
                by_subject_grade = [
                    {
                        "subject": row["subject"],
                        "grade": int(row["grade"]),
                        "section_count": int(row["section_count"]),
                    }
                    for row in cur.fetchall()
                ]

                cur.execute(
                    """
                    select chapter_id, count(*) as section_count
                    from section_embedding_documents
                    group by chapter_id
                    order by chapter_id
                    """
                )
                by_chapter = [
                    {"chapter_id": row["chapter_id"], "section_count": int(row["section_count"])}
                    for row in cur.fetchall()
                ]

        return {
            "by_subject_grade": by_subject_grade,
            "by_chapter": by_chapter,
            "total_sections": sum(row["section_count"] for row in by_subject_grade),
            "total_chapters": len(by_chapter),
        }

    def admin_checkpoint_analytics(self) -> dict[str, Any]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select count(*) as total_attempts,
                           avg(score) as avg_score,
                           count(*) filter (where score >= 0.7) as pass_count,
                           count(*) filter (where score < 0.7) as fail_count
                    from checkpoint_attempts
                    """
                )
                summary = cur.fetchone() or {}

                cur.execute(
                    """
                    select module_id,
                           count(*) as attempt_count,
                           avg(score) as avg_score,
                           min(score) as min_score,
                           max(score) as max_score
                    from checkpoint_attempts
                    group by module_id
                    order by avg(score) asc
                    limit 20
                    """
                )
                by_module = [
                    {
                        "module_id": row["module_id"],
                        "attempt_count": int(row["attempt_count"]),
                        "avg_score": round(float(row["avg_score"] or 0), 3),
                        "min_score": round(float(row["min_score"] or 0), 3),
                        "max_score": round(float(row["max_score"] or 0), 3),
                    }
                    for row in cur.fetchall()
                ]

                cur.execute(
                    """
                    select date_trunc('day', created_at)::date as day,
                           count(*) as attempts,
                           avg(score) as avg_score
                    from checkpoint_attempts
                    group by day
                    order by day desc
                    limit 30
                    """
                )
                daily = [
                    {
                        "day": str(row["day"]),
                        "attempts": int(row["attempts"]),
                        "avg_score": round(float(row["avg_score"] or 0), 3),
                    }
                    for row in cur.fetchall()
                ]

        total = int(summary.get("total_attempts") or 0)
        return {
            "total_attempts": total,
            "avg_score": round(float(summary.get("avg_score") or 0), 3) if total else 0,
            "pass_count": int(summary.get("pass_count") or 0),
            "fail_count": int(summary.get("fail_count") or 0),
            "pass_rate": round(int(summary.get("pass_count") or 0) / total, 3) if total else 0,
            "by_module": by_module,
            "daily": daily,
        }


def run_schema(database_url_value: str | None = None, *, schema_path: Path | str = "database/schema.sql") -> None:
    url = database_url_value or database_url()
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    repo = PostgresRepository(url)
    sql = Path(schema_path).read_text(encoding="utf-8")
    try:
        with repo._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
    finally:
        repo.close()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _profile_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_id": row["user_id"],
        "email": row["email"] or "",
        "display_name": row["display_name"] or "",
        "avatar_url": row["avatar_url"] or "",
        "provider": row["provider"] or "google",
        "role": row.get("role") or "learner",
        "created_at": row["created_at"].isoformat() if row.get("created_at") else "",
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else "",
        "last_seen_at": row["last_seen_at"].isoformat() if row.get("last_seen_at") else "",
    }


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{float(value):.9g}" for value in values) + "]"


def _insight_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "insight_id": row["insight_id"],
        "learner_id": row["learner_id"],
        "curriculum_plan_id": row["curriculum_plan_id"],
        "module_id": row["module_id"],
        "section_id": row["section_id"],
        "current_status": row["current_status"],
        "understanding_summary": row["understanding_summary"],
        "strengths": row["strengths"] or [],
        "misconceptions_or_gaps": row["misconceptions_or_gaps"] or [],
        "recommended_adjustment": row["recommended_adjustment"],
        "confidence": float(row["confidence"] or 0.0),
        "evidence_question_ids": row["evidence_question_ids"] or [],
        "supersedes_insight_id": row["supersedes_insight_id"],
        "reconciliation_reason": row["reconciliation_reason"],
        "created_at": row["created_at"].isoformat() if row.get("created_at") else "",
    }


def _hotspot_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "hotspot_id": row["hotspot_id"],
        "section_id": row["section_id"],
        "concept_id": row["concept_id"],
        "misconception_tag": row["misconception_tag"],
        "evidence_window_start": row["evidence_window_start"].isoformat() if row.get("evidence_window_start") else "",
        "evidence_window_end": row["evidence_window_end"].isoformat() if row.get("evidence_window_end") else "",
        "module_design_ids": row["module_design_ids"] or [],
        "attempt_count": int(row["attempt_count"] or 0),
        "wrong_count": int(row["wrong_count"] or 0),
        "unique_learner_count": int(row["unique_learner_count"] or 0),
        "distinct_question_count": int(row["distinct_question_count"] or 0),
        "misconception_rate": float(row["misconception_rate"] or 0.0),
        "diagnostic_summary": row["diagnostic_summary"] or "",
        "proposed_guidance": row["proposed_guidance"] or "",
        "reviewed_guidance": row["reviewed_guidance"] or "",
        "suggested_activity_adjustment": row["suggested_activity_adjustment"] or "",
        "suggested_checkpoint_focus": row["suggested_checkpoint_focus"] or "",
        "status": row["status"] or "candidate",
        "activated_at": row["activated_at"].isoformat() if row.get("activated_at") else "",
        "created_at": row["created_at"].isoformat() if row.get("created_at") else "",
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else "",
    }
