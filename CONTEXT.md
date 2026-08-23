# AI Curriculum Creator

This context describes the language used to turn textbook content into grounded,
adaptive learning paths. It distinguishes required learning order from optional
connections and individual evidence from population-level curriculum feedback.

## Learning Space

**Three-Dimensional Curriculum**:
A curriculum that supports textbook sequence, prerequisite travel, and conceptual reinforcement rather than following book order alone.
_Avoid_: Three-dimensional graph, 3D curriculum graph

**Textbook Sequence**:
The order in which chapters, sections, and subsections appear in the source textbook. It is a publication order, not proof of a learning dependency.
_Avoid_: Required sequence, prerequisite order

**Prerequisite Travel**:
Movement from a learning goal to earlier source sections that teach knowledge required for that goal.
_Avoid_: Backtracking, related content

**Conceptual Reinforcement**:
Movement to source sections that teach the same or closely connected concepts for comparison, transfer, or consolidation.
_Avoid_: Prerequisite, required detour

## Source Knowledge

**Curriculum Corpus**:
The supported collection of textbook content from which learning paths and module material may be grounded.
_Avoid_: Knowledge base, training data

**Source Section**:
A retrievable textbook learning unit with a stable source identifier. It may be a top-level textbook section or a separately indexed subsection.
_Avoid_: Chunk, node, unit

**Subsection**:
An atomic teaching passage nested inside a top-level textbook section. A subsection becomes a Source Section only when it is independently retrievable.
_Avoid_: Section

**Section Summary**:
A compact account of what a Source Section teaches, including its important terms and covered child content.
_Avoid_: Abstract, generated lesson

**Concept**:
A distinct idea, principle, method, or skill that can be taught, required, or assessed.
_Avoid_: Keyword, topic label

**Canonical Concept**:
The single identity chosen to represent one concept across variant labels and source occurrences.
_Avoid_: Raw concept, normalized keyword

**Concept Alias**:
An alternative label that resolves to a Canonical Concept without becoming a separate concept.
_Avoid_: Related concept, broader concept

## Relationships

**Teaches Concept**:
A directional relationship stating that a Source Section introduces, explains, derives, applies, or substantially reinforces a Canonical Concept.

**Requires Concept**:
A directional relationship stating that understanding a Canonical Concept is expected before studying a Source Section.
_Avoid_: Teaches Concept

**Hard Dependency**:
A required ordering relationship from a dependent Source Section to a prerequisite Source Section; the prerequisite must appear first in the Main Path.
_Avoid_: Related section, textbook predecessor

**Transfer Support**:
An optional bridge to a Source Section in another chapter or subject that teaches a concept required by the current section.
_Avoid_: Hard Dependency, mandatory prerequisite

**Conceptual Relation**:
An optional connection between Source Sections that teach the same Canonical Concept and can reinforce one another.
_Avoid_: Hard Dependency, prerequisite

**Relationship Evidence**:
The source-grounded explanation for why a relationship exists and what pedagogical role it serves.
_Avoid_: Confidence score, model rationale

## Learning Path

**Learning Goal**:
The learner's confirmed description of what they want to understand or be able to do.
_Avoid_: Raw query, topic

**Target Section**:
A Source Section directly selected as relevant to the Learning Goal.
_Avoid_: Prerequisite Section, Support Section

**Prerequisite Section**:
A Source Section included because a retained Target Section has a Hard Dependency on it.
_Avoid_: Earlier section, recommended reading

**Support Section**:
A Source Section offered through Transfer Support or a Conceptual Relation without becoming required learning.
_Avoid_: Prerequisite Section, required module

**Main Path**:
The required set of Target Sections and Prerequisite Sections from which the curriculum's ordered modules are formed.
_Avoid_: All retrieved sections, support path

**Next Step**:
A Source Section that depends on material in the current Main Path and is suitable for study after the current goal is completed.
_Avoid_: Next module, prerequisite

**Curriculum Plan**:
An ordered sequence of Planned Modules that serves one Learning Goal and preserves its source grounding.
_Avoid_: Lesson content, module design

**Planned Module**:
An ordered grouping of Main Path Source Sections with a module goal and explicit links to neighboring modules.
_Avoid_: Module Design, lesson

**Module Design**:
The learner-facing treatment of one Planned Module, including explanations, a guided activity, misconception handling, and diagnostic checkpoints.
_Avoid_: Curriculum Plan, source content

**Guided Activity**:
A learner action within a Module Design that applies or explores the module's concepts.
_Avoid_: Checkpoint, final assessment

## Evidence And Personalization

**Checkpoint MCQ**:
A diagnostic multiple-choice question attached to a Module Design and grounded to the Source Sections and Canonical Concepts it tests.
_Avoid_: Final assessment, ungrounded quiz question

**Checkpoint Attempt**:
One learner's submitted answers to the checkpoint questions of a particular Module Design.
_Avoid_: Assessment, curriculum completion

**Section Learning Insight**:
The current best interpretation of one learner's understanding of a Source Section, reconciled from checkpoint evidence and any prior insight for that section.
_Avoid_: Score, population hotspot

**Understanding Status**:
The learner's current evidence-backed state for a Source Section: competent, partially understood, misconception, or uncertain.
_Avoid_: Permanent ability, grade

**Superseded Insight**:
A historical Section Learning Insight replaced by newer evidence. It remains part of the learning trajectory but does not drive current personalization.
_Avoid_: Active insight, deleted insight

**Misunderstanding Hotspot**:
A recurring misconception pattern found across multiple learners' checkpoint answers for the same section, concept, and misconception tag.
_Avoid_: Individual insight, difficult section

**Evidence Window**:
The bounded set of checkpoint evidence used to judge a Misunderstanding Hotspot under a particular teaching treatment.
_Avoid_: All-time history

**Hotspot Guidance**:
Reviewed teaching guidance derived from an active Misunderstanding Hotspot and applied to future Module Designs for the affected Source Sections.
_Avoid_: Automatic textbook edit, learner insight
