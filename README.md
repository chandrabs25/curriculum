AI Curriculum Engine — Development Log


Assumption:
A POD has requested curriculum modules covering selected chapters from the Class 9 NCERT Science textbook. The current working scope includes Chapters 4, 6, 7, 8, 9, and 10 — the physics-related chapters — from which 192 atomic concepts have been extracted.

Monday, 25th May — Log:
Since I have already worked on AI personalisation and finding the hotspots in the curriculum using the insights generated during the test, I spent today researching ways to make it easier to create modules based on the concepts that are needed to be covered

Focus: Concept Clustering and Its Applications in Curriculum Design

The day was spent researching and experimenting with how embedding-based clustering of physics concepts could serve the curriculum engine, with the following three research questions driving the work:

1. Concept Ordering — Reducing Friction in Learning:  
Since concepts within the same embedding cluster are semantically similar, clustering provides a principled basis for determining the order in which concepts should be taught. Grouping related concepts together and sequencing them in order of increasing complexity minimises the cognitive load of switching between unrelated ideas. The hypothesis is that a student encounters less friction when related concepts are introduced in a cohesive sequence rather than scattered across disconnected modules.

2. Cross-Cluster Concept Links — A Recommendation Signal
Concepts that are semantically close but belong to different clusters (i.e., different chapters or topic groups) represent a natural opportunity for cross-domain recommendation. If a student has mastered concept X and concept Y is semantically near X but resides in another cluster, the student's established understanding of X can serve as a bridge when concept Y is introduced. This inter-cluster similarity can be surfaced as candidate links for curriculum designers, who can then validate and assign directionality (e.g., "X is a prerequisite for Y" vs. "X and Y are analogous"). The current research question is: can semantic similarity help curriculum creators make meaningful, evidence-backed relationships between concepts across chapters?

3. Tiered Assessment Design — Leveraging Clusters for Difficulty Scaffolding
Clustering also provides a natural scaffold for designing assessments at three tiers of difficulty:
Basic tier — questions that test a student on a single atomic concept from one cluster.
Intermediate tier — questions that require the student to reason across two or more related concepts from the same cluster, where the combination is semantically coherent.
Advanced tier — questions that require reasoning across concepts from different clusters, where the combination is validated as meaningful by curriculum designers using inter-cluster similarity as a guide.
The key constraint is that concepts are only combined in questions when the relationship between them is pedagogically meaningful — semantic similarity is used as a signal to help curriculum creators surface and verify these relationships, not as an automatic rule.

Key Finding: Does Clustering Add Value Over NCERT's Existing Chapter Structure?

1. An important conclusion from today's research: NCERT's chapter structure already provides a high-quality primary grouping of concepts. Embedding-based clustering is most valuable not as a replacement for that structure, but as a complementary analytical tool for:

2. Detecting cross-chapter concept relationships that the chapter structure does not make explicit.

3. Identifying near-duplicate or semantically overlapping concepts across chapters.

4. Informing tiered assessment design by surfacing which concepts are close enough to meaningfully combine in multi-concept questions.

The chapter structure drives the curriculum and the knowledge graph. Clustering drives the analytics, the recommendation layer, and the assessment blueprint.
