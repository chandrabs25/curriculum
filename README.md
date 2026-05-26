# AI Curriculum Engine — Development Log

## Assumption

A POD has requested curriculum modules covering selected chapters from the Class 9 NCERT Science textbook. The current working scope includes Chapters 4, 6, 7, 8, 9, and 10 — the physics-related chapters — from which **192 atomic concepts** have been extracted.

---

# Monday, 25th May — Log

Since I have already worked on AI personalisation and identifying hotspots in the curriculum using the insights generated during tests, I spent today researching ways to make it easier to create curriculum modules based on the concepts that need to be covered.

---

# Focus: Concept Clustering and Its Applications in Curriculum Design

The day was spent researching and experimenting with how **embedding-based clustering of physics concepts** could support the curriculum engine, with the following three research questions driving the work:

---

## 1. Concept Ordering — Reducing Friction in Learning

Since concepts within the same embedding cluster are semantically similar, clustering provides a principled basis for determining the order in which concepts should be taught.

Grouping related concepts together and sequencing them in order of increasing complexity minimises the cognitive load caused by switching between unrelated ideas.

### Hypothesis

A student experiences less friction when related concepts are introduced in a cohesive sequence rather than being scattered across disconnected modules.

---

## 2. Cross-Cluster Concept Links — A Recommendation Signal

Concepts that are semantically close but belong to different clusters (i.e., different chapters or topic groups) represent a natural opportunity for cross-domain recommendation.

If a student has mastered concept **X**, and concept **Y** is semantically near **X** but resides in another cluster, the student's established understanding of **X** can serve as a bridge when concept **Y** is introduced.

This inter-cluster similarity can be surfaced as candidate links for curriculum designers, who can then validate and assign directionality, such as:

* “X is a prerequisite for Y”
* “X and Y are analogous”

### Research Question

Can semantic similarity help curriculum creators establish meaningful, evidence-backed relationships between concepts across chapters?

---

## 3. Tiered Assessment Design — Leveraging Clusters for Difficulty Scaffolding

Clustering also provides a natural scaffold for designing assessments at three tiers of difficulty.

### Basic Tier

Questions that test a student on a single atomic concept from one cluster.

### Intermediate Tier

Questions that require reasoning across two or more related concepts from the same cluster, where the combination is semantically coherent.

### Advanced Tier

Questions that require reasoning across concepts from different clusters, where the relationship is validated as meaningful by curriculum designers using inter-cluster similarity as a guide.

### Key Constraint

Concepts should only be combined in questions when the relationship between them is pedagogically meaningful.

Semantic similarity is used as a signal to help curriculum creators surface and verify these relationships — not as an automatic rule.

---

# Key Finding: Does Clustering Add Value Over NCERT's Existing Chapter Structure?

An important conclusion from today's research is that **NCERT's chapter structure already provides a strong primary grouping of concepts**.

Embedding-based clustering is most valuable **not as a replacement** for that structure, but as a complementary analytical layer for:

1. Detecting cross-chapter concept relationships that the chapter structure does not explicitly capture.

2. Identifying near-duplicate or semantically overlapping concepts across chapters.

3. Informing tiered assessment design by surfacing which concepts are close enough to meaningfully combine in multi-concept questions.

---

# Final Insight

* **The chapter structure** drives the curriculum and the knowledge graph.
* **Clustering** drives the analytics layer, recommendation layer, and assessment blueprint.

---
# 26th MAY

## Goal:

1. Create the NCERT content ready for it to act as a knowledge base on which AI creates modules (Using too much of the content from NCERT consumes a lot of tokens, so use the content for providing the skeleton around which modules should be made)
2. Create meaningful relationships between the concepts across the chapters to help the recommendation system and prerequisite checks(make an internal tool, for helping in the creation of these cross-chapter links)
3. Finalise the Onboarding questions.
4. Finalise the schemas (make sure the AI module personalisation is based on the onboarding questions and the students understanding of the semantically close concepts)
5. Implement most of the backend logic


---
## 3:00 pm:

I have just finished implementing the pipeline that would generate the knowledge base with relationships like TEACHES_CONCEPT, REQUIRES_CONCEPT, DEPENDS_ON_UNIT, etc., and the script would run in the background calling gemini api. Currently finalising the various typed models that are used across for module generation, assessments, and insight creation. I am using the doing the project on class 11 and 12 physics, chemistry and biology textbooks instead, because I already had the base content with me from my earlier project, but I had to redesign the way relationships are created to make it suitable for this project.

---

## 4:00 pm

I implemented a textbook ingestion pipeline that extracts section summaries, taught concepts, and required concepts using a single LLM call per section unit, saving thousands of API requests and keeping the execution fast. I then wrote the concept normalization logic to group these raw extractions into a global canonical concept registry, which allows us to natively bridge concepts across different subjects and grades. Finally, I built a programmatic relationship generator that automatically compiles the TEACHES_CONCEPT and REQUIRES_CONCEPT edges, and deterministically infers DEPENDS_ON_UNIT dependencies within each chapter by matching requirements and teachings on shared concepts, ensuring the graph is semantically consistent.

---

## 7:30pm

To make the graph artifacts usable by the application, I implemented the curriculum_engine querying and retrieval library. I built in-memory dictionary indexes cached in RAM via Python's @cached_property to ensure all graph lookups run in instant, $O(1)$ time instead of scanning lists linearly. I used these indexes to implement pathfinding algorithms that can trace prerequisites and dynamically map out remediation paths when a student struggles with specific concepts. I also added a token-based search indexing method over summaries and key terms to provide a robust, deterministic routing layer for module sequencing and assessment grading.
