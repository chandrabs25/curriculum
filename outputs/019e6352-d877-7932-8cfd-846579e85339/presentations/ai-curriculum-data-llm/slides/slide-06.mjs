import { C, bg, title, footer, node, miniTable } from './helpers.mjs';
export async function slide06(presentation, ctx) {
  const slide = presentation.slides.add(); bg(slide, ctx);
  title(slide, ctx, 'PLANNER PACKET', 'The first LLM receives ordering evidence, not the entire knowledge graph.', 'Planner inputs are deliberately slim: sections, hard links, optional link buckets, and policy. Concepts move to module design.');
  miniTable(slide, ctx, [
    ['Included in planner', 'Reason'],
    ['sections_by_id', 'Titles and summaries give the planner semantic units.'],
    ['main_path_section_ids', 'Controls what can become required modules.'],
    ['hard dependencies', 'Defines mandatory ordering.'],
    ['optional links', 'Supports “alongside / reinforce / next” recommendations.'],
    ['relationship_policy', 'Prevents optional links from becoming prerequisites.'],
  ], 78, 220, 520, 48);
  miniTable(slide, ctx, [
    ['Excluded from planner', 'Reason'],
    ['full source text', 'Fetched later by ID only when needed.'],
    ['bulk concepts', 'Derived backend-side for each module.'],
    ['old learner insight history', 'Only latest section insight matters.'],
    ['raw artifact dumps', 'Too large and easy for LLMs to misuse.'],
  ], 672, 220, 520, 48);
  node(slide, ctx, { x: 256, y: 548, w: 760, h: 62, label: 'Lost-in-the-middle control', sub: 'Large packet sits in the middle; final task, rules, and JSON schema appear at the end of the prompt.', fill: C.softBlue, stroke: '#C6D6F2', accent: C.blue });
  footer(slide, ctx, 6);
  return slide;
}
