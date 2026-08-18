-- Explicitly discard generated learning state before incompatible contract migrations.
-- User profiles, learners, vector documents, source content, and graph artifacts are preserved.

truncate table curriculum_plans cascade;
truncate table section_misunderstanding_hotspots;
