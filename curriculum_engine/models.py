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
class CurriculumModule:
    module_id: str
    title: str
    covered_concept_ids: list[str]
    source_section_ids: list[str]
    activities: list[str]
    recommended_examples: list[str]
    recommended_exercises: list[str]
    milestone: str
    expected_outcome: str
    estimated_time_minutes: int
    prerequisite_warnings: list[str] = field(default_factory=list)
    personalization_note: str = ""


@dataclass(frozen=True)
class CurriculumPlan:
    curriculum_plan_id: str
    learner_id: str
    onboarding: OnboardingAnswers
    modules: list[CurriculumModule]
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
