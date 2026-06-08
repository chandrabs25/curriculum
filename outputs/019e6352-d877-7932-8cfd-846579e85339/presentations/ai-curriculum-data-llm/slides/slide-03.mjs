import { C, bg, title, footer, miniTable, node } from './helpers.mjs';
export async function slide03(presentation, ctx) {
  const slide = presentation.slides.add(); bg(slide, ctx);
  title(slide, ctx, 'GRAPH LAYER', 'Relationships make the curriculum explainable before an LLM sees it.', 'The graph separates hard sequence from optional support so the planner cannot confuse relatedness with prerequisites.');
  miniTable(slide, ctx, [
    ['Relationship', 'Planning meaning'],
    ['TEACHES_CONCEPT', 'A section introduces, derives, applies, or reinforces a concept.'],
    ['REQUIRES_CONCEPT', 'A section expects prior knowledge of a concept.'],
    ['DEPENDS_ON_UNIT', 'Hard ordering: target section should come after prerequisite section.'],
    ['TRANSFER_SUPPORTS_UNIT', 'Optional cross-chapter or cross-subject bridge.'],
    ['RELATED_BY_CONCEPT', 'Optional reinforcement; never mandatory sequence.'],
  ], 78, 230, 610, 50);
  node(slide, ctx, { x: 760, y: 238, w: 360, h: 94, label: 'Contract discipline', sub: 'Rows carry IDs, confidence, evidence text, and reasoning. Invalid or dangling IDs are rejected before runtime use.', fill: C.white, accent: C.blue });
  node(slide, ctx, { x: 760, y: 356, w: 360, h: 94, label: 'Canonical concepts', sub: 'Aliases and reviewed merges prevent synonym drift from breaking dependency inference.', fill: C.white, accent: C.green });
  node(slide, ctx, { x: 760, y: 474, w: 360, h: 94, label: 'Prompt safety', sub: 'LLMs receive relationship purpose labels, not a flat bag of “related sections.”', fill: C.white, accent: C.amber });
  footer(slide, ctx, 3);
  return slide;
}
