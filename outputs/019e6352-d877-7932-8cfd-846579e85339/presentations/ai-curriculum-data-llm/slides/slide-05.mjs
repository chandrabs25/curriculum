import { C, bg, title, footer, node, hline } from './helpers.mjs';
export async function slide05(presentation, ctx) {
  const slide = presentation.slides.add(); bg(slide, ctx, C.dark);
  title(slide, ctx, 'LLM CALL SPLIT', 'Each model call owns one decision boundary, so failures are isolated.', 'The agent uses LLMs as typed workers: classify intent, order sections, design a module, reconcile insights.', true);
  const calls = [
    ['1 / Intent', 'GPT-OSS 120B', 'query + compact corpus clues', 'confirmed/refined learning intent'],
    ['2 / Planner', 'Kimi', 'selected sections + section links', 'ordered module sequence'],
    ['3 / Module design', 'Kimi', 'module summaries + concepts + insights', 'lesson blocks, activity, MCQs'],
    ['4 / Insight reconcile', 'Kimi', 'answers + scoring + prior insight', 'latest section understanding'],
  ];
  calls.forEach((c, i) => {
    const x = 76 + i * 292;
    node(slide, ctx, { x, y: 236, w: 240, h: 230, label: c[0], sub: `${c[1]}\n\nInput: ${c[2]}\n\nOutput: ${c[3]}`, fill: C.dark2, stroke: '#343A46', accent: [C.blue,C.green,C.amber,C.violet][i], dark: true });
    if (i < 3) hline(slide, ctx, x + 240, 350, x + 292, '#596273', 2);
  });
  ctx.addText(slide, { text: 'Why it scales: planner calls stay compact; module calls run lazily; checkpoint insight calls only run after assessment evidence exists.', left: 90, top: 548, width: 1040, height: 46, fontSize: 20, bold: true, color: C.white, typeface: ctx.fonts.title, insets: {left:0,right:0,top:0,bottom:0} });
  footer(slide, ctx, 5, true);
  return slide;
}
