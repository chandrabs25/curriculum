import { C, bg, title, footer, node, hline, dot } from './helpers.mjs';
export async function slide10(presentation, ctx) {
  const slide = presentation.slides.add(); bg(slide, ctx);
  title(slide, ctx, 'EVALUATION ROADMAP', 'The next maturity jump is making every AI decision measurable.', 'The agent should be judged at retrieval, planning, module design, personalization, and system-cost layers.');
  const lanes = [
    ['Retrieval', 'Recall@6\nsubject leakage\nirrelevant section rate', C.blue],
    ['Planner', 'ordering correctness\ninvalid ID rate\nmodule bloat', C.green],
    ['Module design', 'MCQ validity\nactivity relevance\ngrounding failures', C.amber],
    ['Learning loop', 'insight accuracy\nremediation success\nhotspot precision', C.violet],
    ['System', 'p95 latency\ncache hit rate\nLLM cost per plan', C.red],
  ];
  lanes.forEach((l,i)=> {
    const x = 72 + i*230;
    node(slide, ctx, { x, y: 252, w: 184, h: 170, label: l[0], sub: l[1], fill: C.white, accent: l[2] });
    dot(slide, ctx, x+92, 484, l[2], 12);
    if (i<4) hline(slide, ctx, x+98, 484, x+230, C.line, 2);
  });
  ctx.addText(slide, { text: 'Practical evaluation set: 30–50 golden queries across Physics, Chemistry, and Biology, each with expected sections and forbidden sections.', left: 104, top: 548, width: 920, height: 48, fontSize: 22, bold: true, color: C.ink, typeface: ctx.fonts.title, insets: {left:0,right:0,top:0,bottom:0} });
  footer(slide, ctx, 10);
  return slide;
}
