export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };
export type JsonRecord = { [key: string]: JsonValue };

export type LearnerConceptStatus = "competent" | "partial" | "misconception" | string;
export type CheckpointRecommendation = "continue" | "review_module" | string;
export type Difficulty = "easy" | "medium" | "hard" | string;

export interface OnboardingPayload {
  subject: string;
  topic: string;
  current_level: string;
  confidence: string;
  learning_goal: string;
  available_time: string;
  preferred_learning_style: string;
  deadline_or_pace: string;
}

export interface LearnerConceptStatePayload {
  concept_id: string;
  status: LearnerConceptStatus;
  confidence: number;
  recency_weight: number;
}

export interface CurriculumQueryPayload {
  learner_id: string;
  onboarding: OnboardingPayload;
  learner_state: LearnerConceptStatePayload[];
  prerequisite_check: PrerequisiteCheckPayload | null;
  subject: string | null;
  grade: number | null;
  chapter_id: string | null;
  max_modules: number;
  retrieval_limit: number;
}

export interface IntentClassifyPayload {
  query: string;
  subject: string | null;
  grade: number | null;
  chapter_id: string | null;
  candidate_limit: number;
}

export interface ConfirmedIntent {
  label: string;
  user_facing_summary: string;
  refined_query: string;
}

export interface IntentOption {
  label: string;
  user_facing_description: string;
  refined_query: string;
}

export interface IntentClassificationPacket {
  original_query: string;
  matched_concepts: {
    concept_id: string;
    label: string;
  }[];
  candidate_sections: {
    section_id: string;
    title: string;
    subject: string | null;
    grade: number | null;
    chapter_id: string;
    reasons: string[];
    matched_concept_ids: string[];
  }[];
  instructions: Record<string, string>;
}

export interface IntentClassificationResponse {
  status: "confirmed" | "needs_clarification";
  original_query: string;
  needs_user_choice: boolean;
  question: string;
  confirmed_intent: ConfirmedIntent | null;
  options: IntentOption[];
  classification_packet: IntentClassificationPacket;
}

export interface ChapterOption {
  id: string;
  subject: string;
  grade: number;
  chapter_number: number;
  chapter_title: string;
  path: string;
}

export interface OptionsResponse {
  subjects: string[];
  grades: number[];
  chapters: ChapterOption[];
}

export type OptionResponse = OptionsResponse;

export interface HealthResponse {
  ok: boolean;
  usable_chapters: number;
  section_summaries: number;
}

export interface RetrievedSection {
  section_id: string;
  chapter_id: string;
  title: string;
  summary: string;
  score: number;
  matched_concept_ids: string[];
  prerequisite_section_ids: string[];
  reasons: string[];
  subject: string | null;
  grade: number | null;
}

export interface PrerequisiteQuestion {
  question_id: string;
  concept_id: string;
  required_by_section_id: string;
  label: string;
  question: string;
  pedagogical_reason: string;
  options: string[];
}

export interface PrerequisiteAnswer {
  concept_id: string;
  status: "known_well" | "somewhat_known" | "unfamiliar" | string;
  required_by_section_id: string;
}

export interface PrerequisiteCheckPayload {
  asked: boolean;
  answers: PrerequisiteAnswer[];
}

export interface SectionContext {
  section_id: string;
  chapter_id: string;
  title: string;
  summary: string;
  role: string;
  retrieval_reasons?: string[];
  score?: number;
  teaches?: ConceptRelationshipDetail[];
  requires?: ConceptRelationshipDetail[];
}

export interface ConceptRelationshipDetail {
  concept_id: string;
  label?: string;
  confidence?: number;
  teaching_evidence?: string;
  pedagogical_reason?: string;
  evidence_text?: string;
  evidence_reason?: string;
}

export interface SectionRelationshipRow {
  relationship_id?: string | null;
  relationship_type?: string;
  type?: string;
  from_section_id?: string;
  to_section_id?: string;
  section_id?: string;
  source_target_section_id?: string;
  source_target_chapter_id?: string;
  bridge_concept_id?: string | null;
  confidence?: number | null;
  evidence_text?: string;
  evidence_reason?: string;
  planning_meaning?: string;
  use_as?: string;
  chapter_id?: string;
  title?: string;
  summary?: string;
}

export interface LearningPathContext {
  main_path_sections: SectionContext[];
  target_sections: SectionContext[];
  prerequisite_sections: SectionContext[];
  support_sections: SectionContext[];
  prerequisite_check: PrerequisiteCheckPayload;
  parallel_support_paths: SectionRelationshipRow[];
  reinforcement_paths: SectionRelationshipRow[];
  next_step_paths: SectionRelationshipRow[];
  cross_chapter_bridges: SectionRelationshipRow[];
  relationship_policy: Record<string, string>;
  required_concepts: ConceptRelationshipDetail[];
  taught_concepts: ConceptRelationshipDetail[];
  hard_dependency_edges: SectionRelationshipRow[];
  optional_support_edges: SectionRelationshipRow[];
  learner_adjustments: JsonRecord[];
}

export interface PlanningPacketSection {
  section_id: string;
  chapter_id: string;
  title: string;
  summary: string;
  role: string;
  score?: number;
  retrieval_reasons?: string[];
  matched_concept_ids?: string[];
}

export interface CurriculumPlanningPacket {
  onboarding: OnboardingPayload;
  learner_state?: LearnerConceptStatePayload[];
  prerequisite_check?: PrerequisiteCheckPayload;
  sections_by_id: Record<string, PlanningPacketSection>;
  main_path_section_ids: string[];
  relationships: {
    hard_dependencies: SectionRelationshipRow[];
    parallel_support: SectionRelationshipRow[];
    reinforcement: SectionRelationshipRow[];
    next_steps: SectionRelationshipRow[];
  };
  budget: {
    estimated_chars: number;
    target_chars: number;
    hard_cap_chars: number;
    trimmed: boolean;
  };
}

export interface RetrievalPreviewResponse {
  retrieved_sections: RetrievedSection[];
  prerequisite_questions: PrerequisiteQuestion[];
  learning_path_context: LearningPathContext;
  planning_packet: CurriculumPlanningPacket;
}

export interface PlannedModulePayload {
  module_id: string;
  title: string;
  module_goal: string;
  position: number;
  covered_concept_ids: string[];
  source_section_ids: string[];
  prerequisite_warnings: string[];
  depends_on_module_ids: string[];
  link_from_previous: string;
  link_to_next: string;
  parallel_support_section_ids: string[];
  reinforcement_section_ids: string[];
  next_step_section_ids: string[];
}

export interface CurriculumPlanPayload {
  curriculum_plan_id: string;
  learner_id: string;
  onboarding: OnboardingPayload;
  modules: PlannedModulePayload[];
  created_at?: string;
  metadata: {
    grade?: string | number;
    retrieved_section_ids?: string[];
    learning_path_context?: LearningPathContext;
    planning_packet?: CurriculumPlanningPacket;
    planner?: string;
    [key: string]: JsonValue | LearningPathContext | CurriculumPlanningPacket | undefined;
  };
  mcq_allocation?: Record<string, number>;
}

export interface ModuleDesignPayload {
  plan: CurriculumPlanPayload;
  module_id: string;
  learner_state: LearnerConceptStatePayload[];
  section_insights?: SectionLearningInsight[];
}

export interface LessonSection {
  heading: string;
  body: string;
  source_section_ids: string[];
  concept_ids: string[];
}

export interface ModuleCheckpointMCQ {
  question_id: string;
  question: string;
  options: string[];
  correct_option: string;
  explanation: string;
  tested_concept_ids: string[];
  source_section_ids: string[];
  difficulty: Difficulty;
  diagnostic_purpose: string;
  misconception_tags: string[];
}

export interface ExpandedCurriculumModulePayload {
  module_id: string;
  title: string;
  module_goal: string;
  source_section_ids: string[];
  concept_ids: string[];
  larger_goal_alignment: string;
  transition_from_previous: string;
  transition_to_next: string;
  lesson_sections: LessonSection[];
  guided_activity: string;
  common_misconceptions: string[];
  checkpoint_mcqs: ModuleCheckpointMCQ[];
  metadata: {
    module_expansion_packet?: ModuleExpansionPacket;
    source_mode?: "summary" | string;
    [key: string]: JsonValue | ModuleExpansionPacket | undefined;
  };
}

export interface ModuleExpansionPacket {
  source_mode: "summary";
  onboarding: OnboardingPayload;
  learner_state: LearnerConceptStatePayload[];
  module: PlannedModulePayload;
  previous_module: CompactModulePayload | null;
  next_module: CompactModulePayload | null;
  relationship_reasoning: {
    requires_concept: SectionRelationshipRow[];
    teaches_concept: SectionRelationshipRow[];
    hard_dependencies: SectionRelationshipRow[];
    parallel_support: SectionRelationshipRow[];
    reinforcement: SectionRelationshipRow[];
    next_steps: SectionRelationshipRow[];
  };
  target_concepts: ConceptRelationshipDetail[];
  learner_section_insights: SectionLearningInsight[];
  source_sections: SourceSectionSummary[];
  mcq_target_count: number;
  budget: {
    estimated_chars: number;
  };
}

export interface CompactModulePayload {
  module_id: string;
  title: string;
  module_goal: string;
  source_section_ids: string[];
  covered_concept_ids: string[];
  link_from_previous: string;
  link_to_next: string;
}

export interface SourceSectionSummary {
  section_id: string;
  chapter_id: string;
  section_number?: string;
  title: string;
  summary: string;
  key_terms: string[];
  candidate_concept_ids: string[];
  covered_subsection_ids: string[];
  resource_counts: {
    subsections: number;
    worked_examples: number;
    diagrams: number;
    tables: number;
  };
}

export interface CheckpointAnswerPayload {
  question_id: string;
  selected_option: string;
}

export interface CheckpointSubmitPayload {
  learner_id: string;
  curriculum_plan_id: string;
  module_id: string;
  checkpoint_mcqs: ModuleCheckpointMCQ[];
  answers: CheckpointAnswerPayload[];
  existing_section_insights?: SectionLearningInsight[];
}

export interface CheckpointQuestionResult {
  question_id: string;
  selected_option: string;
  correct_option: string;
  is_correct: boolean;
  source_section_ids: string[];
  tested_concept_ids: string[];
  diagnostic_purpose: string;
  misconception_tags: string[];
}

export interface InsightEvent {
  learner_id: string;
  type: "COMPETENCY" | "MISCONCEPTION" | string;
  concept_id: string;
  module_id: string;
  question_id: string;
  source_section_ids: string[];
  diagnostic_purpose: string;
  misconception_tags: string[];
  confidence: number;
}

export interface SectionLearningInsight {
  insight_id: string;
  learner_id: string;
  curriculum_plan_id: string;
  module_id: string;
  section_id: string;
  understanding_summary: string;
  current_status: "competent" | "partial_understanding" | "misconception" | "uncertain" | string;
  strengths: string[];
  misconceptions_or_gaps: string[];
  recommended_adjustment: string;
  confidence: number;
  evidence_question_ids: string[];
  supersedes_insight_id?: string | null;
  reconciliation_reason: string;
  created_at: string;
}

export interface CheckpointResultPayload {
  learner_id: string;
  curriculum_plan_id: string;
  module_id: string;
  score: number;
  correct_count: number;
  total_count: number;
  weak_section_ids: string[];
  weak_concept_ids: string[];
  question_results: CheckpointQuestionResult[];
  insight_events: InsightEvent[];
  section_insights: SectionLearningInsight[];
  recommendation: CheckpointRecommendation;
}
