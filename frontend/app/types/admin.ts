// Admin-specific TypeScript types

export interface AdminDashboard {
  learner_count: number;
  plan_count: number;
  checkpoint_attempt_count: number;
  embedding_count: number;
  hotspots_by_status: Record<string, number>;
}

export interface AdminLearnerRow {
  user_id: string;
  email: string;
  display_name: string;
  avatar_url: string;
  provider: string;
  created_at: string;
  last_seen_at: string;
  plan_count: number;
  attempt_count: number;
}

export interface PaginatedLearners {
  learners: AdminLearnerRow[];
  total: number;
  limit: number;
  offset: number;
}

export interface LearnerPlanRow {
  curriculum_plan_id: string;
  topic: string;
  subject: string;
  module_count: number;
  created_at: string;
}

export interface LearnerCheckpointRow {
  checkpoint_attempt_id: string;
  curriculum_plan_id: string;
  module_id: string;
  score: number;
  correct_count: number;
  total_count: number;
  recommendation: string;
  created_at: string;
}

export interface LearnerProfile {
  user_id: string;
  email: string;
  display_name: string;
  avatar_url: string;
  provider: string;
  created_at: string;
  updated_at: string;
  last_seen_at: string;
}

export interface LearnerDetail {
  profile: LearnerProfile;
  plans: LearnerPlanRow[];
  checkpoints: LearnerCheckpointRow[];
}

export interface HotspotRow {
  hotspot_id: string;
  section_id: string;
  concept_id: string;
  misconception_tag: string;
  evidence_window_start: string;
  evidence_window_end: string;
  module_design_ids: string[];
  attempt_count: number;
  wrong_count: number;
  unique_learner_count: number;
  distinct_question_count: number;
  misconception_rate: number;
  diagnostic_summary: string;
  proposed_guidance: string;
  reviewed_guidance: string;
  suggested_activity_adjustment: string;
  suggested_checkpoint_focus: string;
  status: string;
  activated_at: string;
  created_at: string;
  updated_at: string;
}

export interface PaginatedHotspots {
  hotspots: HotspotRow[];
  total: number;
  limit: number;
  offset: number;
}

export interface HotspotStatusPayload {
  status: string;
  reviewed_guidance?: string;
  suggested_activity_adjustment?: string;
  suggested_checkpoint_focus?: string;
}

export interface SubjectGradeRow {
  subject: string;
  grade: number;
  section_count: number;
}

export interface ChapterRow {
  chapter_id: string;
  section_count: number;
}

export interface ContentStats {
  by_subject_grade: SubjectGradeRow[];
  by_chapter: ChapterRow[];
  total_sections: number;
  total_chapters: number;
}

export interface ModuleAnalyticsRow {
  module_id: string;
  attempt_count: number;
  avg_score: number;
  min_score: number;
  max_score: number;
}

export interface DailyAnalyticsRow {
  day: string;
  attempts: number;
  avg_score: number;
}

export interface CheckpointAnalytics {
  total_attempts: number;
  avg_score: number;
  pass_count: number;
  fail_count: number;
  pass_rate: number;
  by_module: ModuleAnalyticsRow[];
  daily: DailyAnalyticsRow[];
}
