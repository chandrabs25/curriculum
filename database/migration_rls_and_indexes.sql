-- ============================================================
-- Migration: Enable RLS + Add missing FK indexes
-- Date: 2024-06-03
-- ============================================================

-- ============================================================
-- 1. ENABLE ROW LEVEL SECURITY ON ALL PUBLIC TABLES
--
-- The backend connects via psycopg as the `postgres` superuser,
-- which bypasses RLS automatically. These policies block
-- unauthorized access through Supabase's Data API (PostgREST).
-- No permissive policies are added since all legitimate access
-- goes through the backend API.
-- ============================================================

alter table user_profiles enable row level security;
alter table learners enable row level security;
alter table section_embedding_documents enable row level security;
alter table curriculum_plans enable row level security;
alter table curriculum_modules enable row level security;
alter table module_designs enable row level security;
alter table module_design_versions enable row level security;
alter table checkpoint_attempts enable row level security;
alter table checkpoint_answers enable row level security;
alter table section_learning_insights enable row level security;
alter table section_misunderstanding_hotspots enable row level security;
alter table public_response_cache enable row level security;

-- ============================================================
-- 2. ADD INDEXES ON UNINDEXED FOREIGN KEY COLUMNS
--
-- Foreign keys without indexes cause sequential scans on
-- cascade deletes and join queries.
-- ============================================================

-- curriculum_plans.learner_id -> learners(learner_id)
create index if not exists idx_curriculum_plans_learner_id
on curriculum_plans(learner_id);

-- module_design_versions.curriculum_plan_id -> curriculum_plans
-- module_design_versions.(curriculum_plan_id, module_id) -> curriculum_modules
create index if not exists idx_module_design_versions_plan_module
on module_design_versions(curriculum_plan_id, module_id);

-- checkpoint_attempts.learner_id -> learners
create index if not exists idx_checkpoint_attempts_learner_id
on checkpoint_attempts(learner_id);

-- checkpoint_attempts.curriculum_plan_id -> curriculum_plans
create index if not exists idx_checkpoint_attempts_plan_id
on checkpoint_attempts(curriculum_plan_id);

-- checkpoint_answers.checkpoint_attempt_id -> checkpoint_attempts
-- (already part of PK, but adding standalone index for FK lookups)
-- Actually the PK (checkpoint_attempt_id, question_id) covers this.
-- Skipped.

-- section_learning_insights.learner_id -> learners
-- (partially covered by the partial unique index, but only for is_latest=true)
create index if not exists idx_section_learning_insights_learner_id
on section_learning_insights(learner_id);

-- section_learning_insights.curriculum_plan_id -> curriculum_plans
create index if not exists idx_section_learning_insights_plan_id
on section_learning_insights(curriculum_plan_id);
