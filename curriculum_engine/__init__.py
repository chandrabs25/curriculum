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
from .llm_clients import (
    FIREWORKS_BASE_URL,
    FIREWORKS_DEEPSEEK_V4_PRO,
    FireworksAPIError,
    FireworksLLMClient,
    parse_llm_json,
)
from .models import (
    Assessment,
    AssessmentItem,
    CurriculumModule,
    CurriculumPlan,
    ExpandedCurriculumModule,
    LearningInsight,
    ModuleCheckpointMCQ,
    OnboardingAnswers,
    PlannedCurriculumModule,
)
from .module_expansion import (
    MODULE_EXPANSION_SCHEMA,
    ModuleExpander,
    ModuleExpansionLLMClient,
    ModuleExpansionPacket,
    build_module_expansion_packet,
    build_module_expansion_prompt,
    expanded_module_from_payload,
    fetch_full_source_sections,
)
from .planning_packet import CurriculumPlanningPacket, build_curriculum_planning_packet
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
    "CurriculumPlanningPacket",
    "CurriculumPlanner",
    "CurriculumRetriever",
    "DEFAULT_INDEX_DIR",
    "DEFAULT_MODEL_DIR",
    "FIREWORKS_BASE_URL",
    "FIREWORKS_DEEPSEEK_V4_PRO",
    "FireworksAPIError",
    "FireworksLLMClient",
    "LearningInsight",
    "LearningPathContext",
    "LearnerConceptState",
    "LearnerConceptStatus",
    "MODULE_EXPANSION_SCHEMA",
    "ExpandedCurriculumModule",
    "ModuleCheckpointMCQ",
    "ModuleExpander",
    "ModuleExpansionLLMClient",
    "ModuleExpansionPacket",
    "OnboardingAnswers",
    "PlannedCurriculumModule",
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
    "build_module_expansion_packet",
    "build_module_expansion_prompt",
    "build_curriculum_planning_packet",
    "build_section_documents",
    "expanded_module_from_payload",
    "fetch_full_source_sections",
    "parse_llm_json",
]
