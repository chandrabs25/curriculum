import type { SectionLearningInsight } from "../types/curriculum";

export function readLatestSectionInsights(
  learnerId: string,
  sectionIds: string[]
): SectionLearningInsight[] {
  if (typeof window === "undefined") return [];
  const insights: SectionLearningInsight[] = [];
  const seen = new Set<string>();
  for (const sectionId of sectionIds) {
    if (seen.has(sectionId)) continue;
    seen.add(sectionId);
    const raw = localStorage.getItem(sectionInsightKey(learnerId, sectionId));
    if (!raw) continue;
    try {
      insights.push(JSON.parse(raw) as SectionLearningInsight);
    } catch {
      localStorage.removeItem(sectionInsightKey(learnerId, sectionId));
    }
  }
  return insights;
}

export function writeSectionInsights(insights: SectionLearningInsight[]): void {
  if (typeof window === "undefined") return;
  for (const insight of insights) {
    if (!insight.learner_id || !insight.section_id) continue;
    const latestKey = sectionInsightKey(insight.learner_id, insight.section_id);
    localStorage.setItem(latestKey, JSON.stringify(insight));
    appendSectionInsightHistory(insight);
  }
}

export function sectionIdsFromMcqs(
  mcqs: { source_section_ids: string[] }[]
): string[] {
  const ids: string[] = [];
  const seen = new Set<string>();
  for (const mcq of mcqs) {
    for (const sectionId of mcq.source_section_ids || []) {
      if (!sectionId || seen.has(sectionId)) continue;
      seen.add(sectionId);
      ids.push(sectionId);
    }
  }
  return ids;
}

function appendSectionInsightHistory(insight: SectionLearningInsight): void {
  const key = sectionInsightHistoryKey(insight.learner_id, insight.section_id);
  let history: SectionLearningInsight[] = [];
  const raw = localStorage.getItem(key);
  if (raw) {
    try {
      history = JSON.parse(raw) as SectionLearningInsight[];
    } catch {
      history = [];
    }
  }
  history = history.filter((row) => row.insight_id !== insight.insight_id);
  history.push(insight);
  localStorage.setItem(key, JSON.stringify(history.slice(-20)));
}

function sectionInsightKey(learnerId: string, sectionId: string): string {
  return `curriculum-section-insight-${learnerId}-${sectionId}`;
}

function sectionInsightHistoryKey(learnerId: string, sectionId: string): string {
  return `curriculum-section-insight-history-${learnerId}-${sectionId}`;
}
