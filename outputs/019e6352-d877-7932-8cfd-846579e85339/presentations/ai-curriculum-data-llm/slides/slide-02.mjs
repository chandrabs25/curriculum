import { C, bg, title, footer, node, hline, dot, pill } from './helpers.mjs';
export async function slide02(presentation, ctx) {
  const slide = presentation.slides.add(); bg(slide, ctx);
  title(slide, ctx, 'CONTENT SUBSTRATE', 'The data pipeline turns textbook prose into reusable planning objects.', 'The runtime does not send full chapters to the planner; it sends compact artifacts generated from section-level source structure.');
  const xs = [70, 320, 570, 820, 1035];
  const labels = [
    ['Textbook JSON', 'chapters → sections → subsections, examples, tables, diagrams'],
    ['Section summaries', 'one compact summary per section-like curriculum unit'],
    ['Raw concepts', 'teaches/requires candidates with evidence and reason'],
    ['Canonical registry', 'normalized concept IDs plus aliases after review'],
    ['Runtime artifacts', 'relationships, section index, retrieval documents'],
  ];
  labels.forEach((l, i) => node(slide, ctx, { x: xs[i], y: 262, w: i === 4 ? 175 : 205, h: 132, label: l[0], sub: l[1], fill: C.white, accent: [C.blue,C.green,C.amber,C.violet,C.red][i] }));
  for (let i = 0; i < 4; i++) { hline(slide, ctx, xs[i] + (i===4?175:205), 328, xs[i+1], C.line, 2); dot(slide, ctx, xs[i+1]-6, 329, C.line, 7); }
  pill(slide, ctx, 'Generated offline / audited as JSONL', 103, 462, 260, C.softBlue, C.blue);
  pill(slide, ctx, 'Runtime reads packaged artifacts', 407, 462, 260, C.softGreen, C.green);
  pill(slide, ctx, 'No whole-chapter prompt bloat', 711, 462, 260, C.softAmber, C.amber);
  ctx.addText(slide, { text: 'Engineering implication: artifact quality and versioning matter as much as model quality, because every LLM call inherits this substrate.', left: 104, top: 545, width: 920, height: 52, fontSize: 22, bold: true, color: C.ink, typeface: ctx.fonts.title, insets: {left:0,right:0,top:0,bottom:0} });
  footer(slide, ctx, 2);
  return slide;
}
