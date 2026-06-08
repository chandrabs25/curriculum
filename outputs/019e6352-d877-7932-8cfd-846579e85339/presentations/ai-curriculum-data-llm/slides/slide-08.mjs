import { C, bg, title, footer, node, hline, vline, dot, pill } from './helpers.mjs';
export async function slide08(presentation, ctx) {
  const slide = presentation.slides.add(); bg(slide, ctx);
  title(slide, ctx, 'PERSONALIZATION LOOP', 'Checkpoint MCQs become section-level memory that changes future module design.', 'The system does not personalize from vague chat history; it personalizes from answer evidence mapped to section and concept IDs.');
  const steps = [
    ['Designed module', 'lesson blocks + guided activity + MCQs'],
    ['Checkpoint answers', 'selected options with source section IDs'],
    ['Deterministic scoring', 'correctness, weak areas, recommendation'],
    ['LLM reconciliation', 'latest insight per tested section'],
    ['Regenerated module', 'uses latest insight + active hotspot guidance'],
  ];
  steps.forEach((s,i)=> node(slide, ctx, { x: 72 + i*228, y: 258 + (i%2)*78, w: 182, h: 108, label: s[0], sub: s[1], fill: C.white, accent: [C.blue,C.amber,C.green,C.violet,C.red][i] }));
  for(let i=0;i<4;i++) hline(slide, ctx, 254+i*228, 313+(i%2)*78, 300+i*228, C.line, 2);
  vline(slide, ctx, 1162, 360, 516, C.line, 2); hline(slide, ctx, 163, 516, 1164, C.line, 2); vline(slide, ctx, 163, 366, 516, C.line, 2);
  dot(slide, ctx, 163, 366, C.blue, 10); dot(slide, ctx, 1164, 360, C.red, 10);
  pill(slide, ctx, 'latest insight only', 306, 552, 170, C.softBlue, C.blue);
  pill(slide, ctx, 'history preserved, not prompted', 510, 552, 220, C.softGreen, C.green);
  pill(slide, ctx, 'hotspots reviewed before use', 764, 552, 220, C.softAmber, C.amber);
  footer(slide, ctx, 8);
  return slide;
}
