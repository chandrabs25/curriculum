import { C, bg, title, footer, node, metric } from './helpers.mjs';
export async function slide09(presentation, ctx) {
  const slide = presentation.slides.add(); bg(slide, ctx, C.dark);
  title(slide, ctx, 'SCALE CONTROLS', 'The scaling strategy is to cap context, cache public work, and persist expensive LLM outputs.', 'Most scaling risks are not CPU-bound; they are provider latency, token cost, retrieval noise, and database growth.', true);
  const controls = [
    ['Context caps', '≤ 6 target sections, optional buckets capped separately', C.blue],
    ['Public cache', 'intent, retrieval preview, guest plan templates', C.green],
    ['pgvector index', 'HNSW cosine vector index + subject/grade filter', C.violet],
    ['Persisted designs', 'module design reused unless force_regenerate', C.amber],
    ['Validation gates', 'schema parsing, ID checks, relationship gating', C.red],
    ['RLS + backend gateway', 'browser cannot directly read app tables', C.green],
  ];
  controls.forEach((c,i)=> node(slide, ctx, { x: 76 + (i%3)*374, y: 234 + Math.floor(i/3)*150, w: 310, h: 104, label: c[0], sub: c[1], fill: C.dark2, stroke: '#333946', accent: c[2], dark: true }));
  metric(slide, ctx, 'p95', 'latency by endpoint and provider', 96, 552, C.blue, true);
  metric(slide, ctx, '$/plan', 'LLM + embedding cost per curriculum', 350, 552, C.green, true);
  metric(slide, ctx, 'hit%', 'cache effectiveness by kind', 632, 552, C.amber, true);
  metric(slide, ctx, 'fail%', 'schema/provider failure visibility', 880, 552, C.red, true);
  footer(slide, ctx, 9, true);
  return slide;
}
