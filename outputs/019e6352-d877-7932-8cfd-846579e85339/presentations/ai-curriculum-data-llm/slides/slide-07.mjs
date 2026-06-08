import { C, bg, title, footer, node, hline, vline, dot } from './helpers.mjs';
export async function slide07(presentation, ctx) {
  const slide = presentation.slides.add(); bg(slide, ctx);
  title(slide, ctx, 'RUNTIME PERSISTENCE', 'Supabase stores learning state; packaged artifacts store curriculum truth.', 'The split keeps source artifacts auditable while learner-owned state stays durable and scoped by authenticated user ID.');
  node(slide, ctx, { x: 78, y: 232, w: 280, h: 110, label: 'Identity', sub: 'user_profiles\nlearners\nrole = learner/admin', fill: C.white, accent: C.blue });
  node(slide, ctx, { x: 486, y: 204, w: 300, h: 90, label: 'Plans + modules', sub: 'curriculum_plans\ncurriculum_modules', fill: C.white, accent: C.green });
  node(slide, ctx, { x: 486, y: 324, w: 300, h: 90, label: 'Module designs', sub: 'module_designs\nmodule_design_versions', fill: C.white, accent: C.amber });
  node(slide, ctx, { x: 486, y: 444, w: 300, h: 90, label: 'Checkpoint evidence', sub: 'checkpoint_attempts\ncheckpoint_answers', fill: C.white, accent: C.red });
  node(slide, ctx, { x: 910, y: 236, w: 280, h: 100, label: 'Personalization', sub: 'section_learning_insights\nlatest unique index', fill: C.white, accent: C.violet });
  node(slide, ctx, { x: 910, y: 394, w: 280, h: 100, label: 'Population overlays', sub: 'section_misunderstanding_hotspots\nactive reviewed guidance', fill: C.white, accent: C.green });
  hline(slide, ctx, 358, 287, 486, C.line, 2); vline(slide, ctx, 636, 294, 444, C.line, 2); hline(slide, ctx, 786, 489, 910, C.line, 2); hline(slide, ctx, 786, 369, 910, C.line, 2);
  dot(slide, ctx, 636, 294, C.green, 8); dot(slide, ctx, 636, 414, C.amber, 8); dot(slide, ctx, 636, 534, C.red, 8);
  footer(slide, ctx, 7);
  return slide;
}
