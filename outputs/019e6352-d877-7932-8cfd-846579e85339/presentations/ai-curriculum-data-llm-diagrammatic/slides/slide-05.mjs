import {C,bg,head,foot,box,arrow,chip,label,h,v,dot} from './helpers.mjs';
export async function slide05(presentation,ctx){const slide=presentation.slides.add();bg(slide,ctx);head(slide,ctx,'05 / CONCEPT EDGES','Section summaries become concept relationships');
box(slide,ctx,80,238,260,170,'section_summary row','section_id: 1.3\nsummary: ...\nkey_terms: ...\nconcept candidates: ...',C.white,C.blue);
h(slide,ctx,340,323,458,C.blue,2);dot(slide,ctx,458,323,C.blue,8);
box(slide,ctx,458,248,250,150,'Edge builder','maps labels to canonical IDs\nkeeps evidence\nadds confidence',C.softBlue,C.blue);
box(slide,ctx,838,184,330,112,'TEACHES_CONCEPT','from: section 1.3\nto: concept:significant_figures\nteaching_evidence preserved',C.softGreen,C.green);
box(slide,ctx,838,392,330,112,'REQUIRES_CONCEPT','from: section 1.3\nto: concept:measurement_precision\npedagogical_reason preserved',C.softAmber,C.amber);
v(slide,ctx,774,240,448,C.blue,2);h(slide,ctx,708,323,774,C.blue,2);
h(slide,ctx,774,240,838,C.green,2);dot(slide,ctx,838,240,C.green,8);
h(slide,ctx,774,448,838,C.amber,2);dot(slide,ctx,838,448,C.amber,8);
chip(slide,ctx,'accepted / review / rejected after confidence gating',426,548,420,C.dark,C.white);
label(slide,ctx,'section IDs and concept IDs stay exact',806,522,390,C.muted);
foot(slide,ctx,5);return slide;}
