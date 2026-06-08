import {C,bg,head,foot,box,chip,h,v,dot} from './helpers.mjs';
export async function slide09(presentation,ctx){const slide=presentation.slides.add();bg(slide,ctx);head(slide,ctx,'09 / MODULE DESIGN LLM','The second LLM designs one module at a time');
box(slide,ctx,64,210,240,126,'Planned module','module_id\nsource_section_ids\nlink_from_previous\nlink_to_next',C.white,C.blue);
box(slide,ctx,396,168,260,126,'Derive concepts','TEACHES_CONCEPT\nREQUIRES_CONCEPT\nbridge reasons',C.softGreen,C.green);
box(slide,ctx,396,358,260,126,'Add context','section summaries\nlatest insights\nactive hotspots\nMCQ target count',C.softAmber,C.amber);
box(slide,ctx,742,250,230,140,'Module design LLM','lesson blocks\nguided activity\nmisconception handling\ncheckpoint MCQs',C.softViolet,C.violet);
box(slide,ctx,1040,250,176,140,'Saved design','module_design_id\ncheckpoint_mcqs\nmetadata',C.white,C.violet);
h(slide,ctx,304,273,352,C.blue,2);v(slide,ctx,352,231,421,C.blue,2);h(slide,ctx,352,231,396,C.green,2);h(slide,ctx,352,421,396,C.amber,2);dot(slide,ctx,396,231,C.green,8);dot(slide,ctx,396,421,C.amber,8);
h(slide,ctx,656,231,690,C.green,2);v(slide,ctx,690,231,421,C.green,2);h(slide,ctx,656,421,690,C.amber,2);h(slide,ctx,690,320,742,C.violet,2);dot(slide,ctx,742,320,C.violet,8);
h(slide,ctx,972,320,1040,C.violet,2);dot(slide,ctx,1040,320,C.violet,8);
chip(slide,ctx,'full textbook text is not sent; summaries + graph reasoning are used',376,536,530,C.dark,C.white);
chip(slide,ctx,'module design call = how to teach this module',456,598,368,C.softViolet,C.violet);
foot(slide,ctx,9);return slide;}
