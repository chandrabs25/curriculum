import { C, bg, title, footer, node, hline, dot, metric } from './helpers.mjs';
export async function slide01(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx, C.dark);
  title(slide, ctx, 'SYSTEM THESIS', 'The curriculum agent scales because LLMs are downstream of structured data.', 'The project is not a single prompt. It is a data pipeline, retrieval system, graph layer, and a set of bounded LLM decisions.', true);
  const y = 305;
  const items = [
    ['Clean corpus', 'NCERT JSON sections, summaries, concepts, exercises', C.blue],
    ['Graph + vectors', 'canonical concepts, relationships, pgvector index', C.green],
    ['LLM decisions', 'intent, ordering, module design, insight reconciliation', C.amber],
    ['Learning memory', 'checkpoint attempts, latest insights, hotspots', C.violet],
  ];
  items.forEach((it, i) => node(slide, ctx, { x: 74 + i * 292, y, w: 240, h: 116, label: it[0], sub: it[1], fill: C.dark2, stroke: '#333946', accent: it[2], dark: true }));
  hline(slide, ctx, 314, y + 58, 366, '#555F70', 2); hline(slide, ctx, 606, y + 58, 658, '#555F70', 2); hline(slide, ctx, 898, y + 58, 950, '#555F70', 2);
  dot(slide, ctx, 340, y + 59, C.blue, 9); dot(slide, ctx, 632, y + 59, C.green, 9); dot(slide, ctx, 924, y + 59, C.amber, 9);
  metric(slide, ctx, '73', 'usable chapters in runtime corpus', 84, 535, C.blue, true);
  metric(slide, ctx, '841', 'section embedding rows in pgvector', 314, 535, C.green, true);
  metric(slide, ctx, '4', 'LLM responsibilities, split by job', 566, 535, C.amber, true);
  metric(slide, ctx, '1', 'latest insight per learner-section', 818, 535, C.violet, true);
  footer(slide, ctx, 1, true);
  return slide;
}
