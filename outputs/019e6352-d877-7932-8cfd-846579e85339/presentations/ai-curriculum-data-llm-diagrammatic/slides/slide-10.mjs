import {C,bg,head,foot,box,chip,h,v,dot} from './helpers.mjs';
export async function slide10(presentation,ctx){const slide=presentation.slides.add();bg(slide,ctx);head(slide,ctx,'10 / LEARNING FEEDBACK','Checkpoint answers become future personalization metadata');
box(slide,ctx,58,222,216,116,'Learner answers','question_id\nselected option',C.white,C.blue);
box(slide,ctx,332,222,220,116,'Stored MCQs','loaded by backend\nfrom module_design_id',C.softBlue,C.blue);
box(slide,ctx,610,222,220,116,'Deterministic scoring','correctness\nweak sections\nweak concepts',C.softGreen,C.green);
box(slide,ctx,888,222,260,116,'Insight LLM','current evidence\n+ latest prior insight',C.softAmber,C.amber);
h(slide,ctx,274,280,332,C.blue,2);dot(slide,ctx,332,280,C.blue,8);h(slide,ctx,552,280,610,C.green,2);dot(slide,ctx,610,280,C.green,8);h(slide,ctx,830,280,888,C.amber,2);dot(slide,ctx,888,280,C.amber,8);
box(slide,ctx,218,466,246,104,'Checkpoint record','attempt\nanswers\nscore',C.white,C.green);
box(slide,ctx,552,466,246,104,'Latest section insight','one active insight\nper learner + section',C.white,C.violet);
box(slide,ctx,886,466,246,104,'Future module packet','latest insight\n+ active hotspots',C.dark,C.violet,true);
v(slide,ctx,720,338,430,C.green,2);h(slide,ctx,341,430,720,C.green,2);v(slide,ctx,341,430,466,C.green,2);dot(slide,ctx,341,466,C.green,8);
v(slide,ctx,1018,338,430,C.amber,2);h(slide,ctx,675,430,1018,C.amber,2);v(slide,ctx,675,430,466,C.violet,2);dot(slide,ctx,675,466,C.violet,8);
h(slide,ctx,798,518,886,C.violet,2);dot(slide,ctx,886,518,C.violet,8);
chip(slide,ctx,'frontend sends answers, not MCQ definitions',98,382,330,C.softBlue,C.blue);
chip(slide,ctx,'old section insights become history',510,604,250,C.softViolet,C.violet);
chip(slide,ctx,'population hotspots use aggregate checkpoint evidence',802,604,360,C.softAmber,C.amber);
foot(slide,ctx,10);return slide;}
