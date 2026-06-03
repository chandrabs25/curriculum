create extension if not exists vector schema extensions;

create table if not exists user_profiles (
  user_id text primary key,
  email text unique,
  display_name text not null default '',
  avatar_url text not null default '',
  provider text not null default 'google',
  role text not null default 'learner' check (role in ('learner', 'admin')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now()
);

create table if not exists learners (
  learner_id text primary key,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

insert into user_profiles(user_id, email, display_name, provider)
select learner_id, null, '', 'google'
from learners
on conflict (user_id) do nothing;

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'learners_user_profile_fk'
  ) then
    alter table learners
      add constraint learners_user_profile_fk
      foreign key (learner_id)
      references user_profiles(user_id)
      on delete cascade;
  end if;
end $$;

create table if not exists section_embedding_documents (
  section_id text primary key,
  chapter_id text not null,
  subject text,
  grade integer,
  title text not null,
  embedding_text text not null,
  taught_concept_ids jsonb not null default '[]'::jsonb,
  required_concept_ids jsonb not null default '[]'::jsonb,
  embedding vector(1024) not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists section_embedding_documents_embedding_idx
on section_embedding_documents
using hnsw (embedding vector_cosine_ops);

create index if not exists section_embedding_documents_subject_grade_idx
on section_embedding_documents(subject, grade);

create table if not exists curriculum_plans (
  curriculum_plan_id text primary key,
  learner_id text not null references learners(learner_id) on delete cascade,
  onboarding jsonb not null,
  metadata jsonb not null default '{}'::jsonb,
  mcq_allocation jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists curriculum_modules (
  module_id text not null,
  curriculum_plan_id text not null references curriculum_plans(curriculum_plan_id) on delete cascade,
  position integer not null,
  module_payload jsonb not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (curriculum_plan_id, module_id)
);

create table if not exists module_designs (
  curriculum_plan_id text not null references curriculum_plans(curriculum_plan_id) on delete cascade,
  module_id text not null,
  module_design_id text not null,
  design_payload jsonb not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (curriculum_plan_id, module_id),
  foreign key (curriculum_plan_id, module_id)
    references curriculum_modules(curriculum_plan_id, module_id)
    on delete cascade
);

create table if not exists module_design_versions (
  module_design_id text primary key,
  curriculum_plan_id text not null references curriculum_plans(curriculum_plan_id) on delete cascade,
  module_id text not null,
  design_payload jsonb not null,
  created_at timestamptz not null default now(),
  foreign key (curriculum_plan_id, module_id)
    references curriculum_modules(curriculum_plan_id, module_id)
    on delete cascade
);

create table if not exists checkpoint_attempts (
  checkpoint_attempt_id text primary key,
  learner_id text not null references learners(learner_id) on delete cascade,
  curriculum_plan_id text not null references curriculum_plans(curriculum_plan_id) on delete cascade,
  module_id text not null,
  module_design_id text not null,
  score double precision not null,
  correct_count integer not null,
  total_count integer not null,
  recommendation text not null,
  result_payload jsonb not null,
  created_at timestamptz not null default now()
);

create table if not exists checkpoint_answers (
  checkpoint_attempt_id text not null references checkpoint_attempts(checkpoint_attempt_id) on delete cascade,
  question_id text not null,
  selected_option text not null,
  correct_option text not null,
  is_correct boolean not null,
  source_section_ids jsonb not null default '[]'::jsonb,
  tested_concept_ids jsonb not null default '[]'::jsonb,
  diagnostic_purpose text not null default '',
  misconception_tags jsonb not null default '[]'::jsonb,
  primary key (checkpoint_attempt_id, question_id)
);

create table if not exists section_learning_insights (
  insight_id text primary key,
  learner_id text not null references learners(learner_id) on delete cascade,
  curriculum_plan_id text not null references curriculum_plans(curriculum_plan_id) on delete cascade,
  module_id text not null,
  section_id text not null,
  current_status text not null,
  understanding_summary text not null,
  strengths jsonb not null default '[]'::jsonb,
  misconceptions_or_gaps jsonb not null default '[]'::jsonb,
  recommended_adjustment text not null default '',
  confidence double precision not null default 0,
  evidence_question_ids jsonb not null default '[]'::jsonb,
  supersedes_insight_id text,
  reconciliation_reason text not null default '',
  is_latest boolean not null default true,
  created_at timestamptz not null default now()
);

create unique index if not exists section_learning_insights_latest_idx
on section_learning_insights(learner_id, section_id)
where is_latest;

create table if not exists section_misunderstanding_hotspots (
  hotspot_id text primary key,
  section_id text not null,
  concept_id text not null,
  misconception_tag text not null,
  evidence_window_start timestamptz,
  evidence_window_end timestamptz,
  module_design_ids jsonb not null default '[]'::jsonb,
  attempt_count integer not null default 0,
  wrong_count integer not null default 0,
  unique_learner_count integer not null default 0,
  distinct_question_count integer not null default 0,
  misconception_rate double precision not null default 0,
  diagnostic_summary text not null default '',
  proposed_guidance text not null default '',
  reviewed_guidance text not null default '',
  suggested_activity_adjustment text not null default '',
  suggested_checkpoint_focus text not null default '',
  status text not null default 'candidate',
  activated_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists section_misunderstanding_hotspots_section_status_idx
on section_misunderstanding_hotspots(section_id, status);

alter table module_designs
add column if not exists module_design_id text not null default '';

alter table checkpoint_attempts
add column if not exists module_design_id text not null default '';

alter table section_misunderstanding_hotspots
add column if not exists activated_at timestamptz;

alter table section_misunderstanding_hotspots
add column if not exists proposed_guidance text not null default '';
