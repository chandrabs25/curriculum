import {C,bg,head,foot,box,chip,h,dot} from './helpers.mjs';
export async function slide08(presentation,ctx){const slide=presentation.slides.add();bg(slide,ctx);head(slide,ctx,'08 / PLANNER LLM','The first LLM only decides sequence and ordering');
box(slide,ctx,76,218,270,144,'Planning packet','selected section IDs\nsection summaries\nhard dependencies\noptional buckets\nrelationship policy',C.white,C.blue);
box(slide,ctx,496,218,270,144,'Planner LLM','groups sections into modules\norders the modules\nexplains transitions',C.softBlue,C.blue);
box(slide,ctx,916,218,270,144,'Ordered module plan','module_id\nposition\nsource_section_ids\nlink_to_next',C.white,C.blue);
h(slide,ctx,346,290,496,C.blue,2);dot(slide,ctx,496,290,C.blue,8);
h(slide,ctx,766,290,916,C.blue,2);dot(slide,ctx,916,290,C.blue,8);
box(slide,ctx,118,474,246,96,'Not asked here','concept IDs\nactivities\nMCQs\nteaching content',C.softRed,C.red);
box(slide,ctx,514,474,246,96,'Output contract','IDs only\nmain path only\noptional IDs separate',C.softAmber,C.amber);
box(slide,ctx,910,474,246,96,'Backend validates','source_section_ids\nmain_path membership\nmodule cap',C.softGreen,C.green);
chip(slide,ctx,'planner call = what to study, in what order, and why',394,608,488,C.dark,C.white);
foot(slide,ctx,8);return slide;}
