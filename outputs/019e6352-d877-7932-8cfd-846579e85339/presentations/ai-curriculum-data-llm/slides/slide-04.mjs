import { C, bg, title, footer, node, hline, vline, dot, pill } from './helpers.mjs';
export async function slide04(presentation, ctx) {
  const slide = presentation.slides.add(); bg(slide, ctx);
  title(slide, ctx, 'RETRIEVAL PATH', 'Semantic search is broad internally, then bounded before curriculum planning.', 'This keeps query understanding rich without allowing thirty loosely similar sections into the planner prompt.');
  const y = 250;
  const steps = [
    ['User query + subject', 'e.g. Biology + photosynthesis'],
    ['BGE-M3 embedding', 'Hugging Face Inference'],
    ['pgvector search', 'HNSW cosine + subject filter'],
    ['Bounded ranking', 'vector + evidence scoring'],
    ['Graph expansion', 'hard prerequisites + optional support'],
  ];
  steps.forEach((s, i) => node(slide, ctx, { x: 62 + i * 236, y, w: 190, h: 116, label: s[0], sub: s[1], fill: C.white, accent: [C.blue,C.violet,C.green,C.amber,C.red][i] }));
  for (let i=0;i<4;i++) hline(slide, ctx, 252 + i*236, y+58, 298 + i*236, C.line, 2);
  pill(slide, ctx, 'candidate pool ≈ 30', 240, 438, 170, C.softBlue, C.blue);
  pill(slide, ctx, 'target seeds ≤ 6', 482, 438, 150, C.softGreen, C.green);
  pill(slide, ctx, 'prerequisites are additional', 704, 438, 210, C.softAmber, C.amber);
  vline(slide, ctx, 702, 392, 514, C.line, 2); dot(slide, ctx, 702, 392, C.line, 8); dot(slide, ctx, 702, 514, C.line, 8);
  ctx.addText(slide, { text: 'Design consequence: retrieval quality is now a measurable data-engineering problem, not a model-vibes problem.', left: 110, top: 548, width: 920, height: 42, fontSize: 22, bold: true, color: C.ink, typeface: ctx.fonts.title, insets: {left:0,right:0,top:0,bottom:0} });
  footer(slide, ctx, 4);
  return slide;
}
