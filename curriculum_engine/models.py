"""Typed domain models for curriculum generation and personalization."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class InsightType(str, Enum):
    COMPETENCY = "COMPETENCY"
    PARTIAL_UNDERSTANDING = "PARTIAL_UNDERSTANDING"
    MISCONCEPTION = "MISCONCEPTION"


class AssessmentOutcome(str, Enum):
    PASSED = "PASSED"
    REASSESSMENT_REQUIRED = "REASSESSMENT_REQUIRED"
    RELEARNING_REQUIRED = "RELEARNING_REQUIRED"


class AssessmentItemType(str, Enum):
    MCQ = "MCQ"
    SHORT_ANSWER = "SHORT_ANSWER"
    SCENARIO = "SCENARIO"


@dataclass(frozen=True)
class OnboardingAnswers:
    subject: str
    topic: str
    current_level: str
    confidence: str
    learning_goal: str
    available_time: str
    preferred_learning_style: str
    deadline_or_pace: str


@dataclass(frozen=True)
class PlannedCurriculumModule:
    module_id: str
    title: str
    module_goal: str
    position: int
    covered_concept_ids: list[str]
    source_section_ids: list[str]
    prerequisite_warnings: list[str] = field(default_factory=list)
    depends_on_module_ids: list[str] = field(default_factory=list)
    link_from_previous: str = ""
    link_to_next: str = ""
    parallel_support_section_ids: list[str] = field(default_factory=list)
    reinforcement_section_ids: list[str] = field(default_factory=list)
    next_step_section_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ModuleCheckpointMCQ:
    question_id: str
    question: str
    options: list[str]
    correct_option: str
    explanation: str
    tested_concept_ids: list[str]
    source_section_ids: list[str]
    difficulty: str
    diagnostic_purpose: str
    misconception_tags: list[str]


@dataclass(frozen=True)
class ExpandedCurriculumModule:
    module_id: str
    title: str
    module_goal: str
    source_section_ids: list[str]
    concept_ids: list[str]
    larger_goal_alignment: str
    transition_from_previous: str
    transition_to_next: str
    lesson_sections: list[dict[str, Any]]
    guided_activity: str
    common_misconceptions: list[str]
    checkpoint_mcqs: list[ModuleCheckpointMCQ]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CurriculumPlan:
    curriculum_plan_id: str
    learner_id: str
    onboarding: OnboardingAnswers
    modules: list[PlannedCurriculumModule]
    created_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AssessmentItem:
    assessment_item_id: str
    item_type: AssessmentItemType
    prompt: str
    source_section_ids: list[str]
    tested_concept_ids: list[str]
    rubric: str
    options: list[str] = field(default_factory=list)
    answer_key: str = ""


@dataclass(frozen=True)
class Assessment:
    assessment_id: str
    curriculum_plan_id: str
    items: list[AssessmentItem]
    outcome: AssessmentOutcome | None = None
    score: float | None = None
    feedback: str = ""
    weak_concept_ids: list[str] = field(default_factory=list)
    revisit_section_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class LearningInsight:
    insight_id: str
    learner_id: str
    insight_type: InsightType
    concept_id: str
    content: str
    confidence: float
    created_at: datetime
    is_active: bool
    source_section_id: str | None = None
    assessment_item_id: str | None = None
    supersedes: str | None = None
