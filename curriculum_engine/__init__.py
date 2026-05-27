"""Core backend primitives for the AI curriculum creator."""

from .artifacts import ArtifactStore, TextbookStore
from .contracts import (
    ArtifactValidationError,
    CanonicalConceptArtifact,
    RawConceptArtifact,
    RawConceptRelationshipType,
    RelationshipArtifact,
    RelationshipType,
    SectionSummaryArtifact,
)
from .graph import CurriculumGraph
from .learning_path import LearningPathContext, build_learning_path_context
from .models import (
    Assessment,
    AssessmentItem,
    CurriculumModule,
    CurriculumPlan,
    LearningInsight,
    OnboardingAnswers,
)
from .planner import (
    CURRICULUM_PLAN_SCHEMA,
    CurriculumLLMClient,
    CurriculumPlanner,
    PlannerRequest,
)
from .retrieval import (
    CurriculumRetriever,
    LearnerConceptState,
    LearnerConceptStatus,
    SectionRetrievalResult,
)
from .vector_index import (
    DEFAULT_INDEX_DIR,
    DEFAULT_MODEL_DIR,
    SectionDocument,
    SectionVectorIndex,
    VectorSearchResult,
    build_section_documents,
)

__all__ = [
    "ArtifactStore",
    "ArtifactValidationError",
    "Assessment",
    "AssessmentItem",
    "CanonicalConceptArtifact",
    "CURRICULUM_PLAN_SCHEMA",
    "CurriculumGraph",
    "CurriculumLLMClient",
    "CurriculumModule",
    "CurriculumPlan",
    "CurriculumPlanner",
    "CurriculumRetriever",
    "DEFAULT_INDEX_DIR",
    "DEFAULT_MODEL_DIR",
    "LearningInsight",
    "LearningPathContext",
    "LearnerConceptState",
    "LearnerConceptStatus",
    "OnboardingAnswers",
    "PlannerRequest",
    "RawConceptArtifact",
    "RawConceptRelationshipType",
    "RelationshipArtifact",
    "RelationshipType",
    "SectionDocument",
    "SectionRetrievalResult",
    "SectionSummaryArtifact",
    "SectionVectorIndex",
    "TextbookStore",
    "VectorSearchResult",
    "build_learning_path_context",
    "build_section_documents",
]
