import {C,bg,head,foot,box,arrow,chip,codeCard,label,h,v,dot} from './helpers.mjs';
export async function slide03(presentation,ctx){const slide=presentation.slides.add();bg(slide,ctx,C.dark);head(slide,ctx,'03 / EXTRACTION LLM','One LLM call produces summary, teaches, requires, and reasoning',true);
codeCard(slide,ctx,70,190,280,330,'current section JSON',['{','  "section_id": "1.3",','  "title": "Significant Figures",','  "content_text": "...",','  "subsections": [...],','  "worked_examples": [...],','  "diagrams": [...]','}']);
chip(slide,ctx,'chapter skeleton: summaries only',102,545,220,C.softBlue,C.blue);
arrow(slide,ctx,350,355,470,355,C.blue);
box(slide,ctx,470,260,230,190,'LLM extractor','reads one full section\nreturns strict JSON\nkeeps evidence + reason',C.dark,C.amber,true);
arrow(slide,ctx,700,355,790,355,C.amber);
v(slide,ctx,790,230,498,C.amber,2);dot(slide,ctx,790,230,C.amber,8);dot(slide,ctx,790,320,C.amber,8);dot(slide,ctx,790,408,C.amber,8);dot(slide,ctx,790,498,C.amber,8);
h(slide,ctx,790,230,860,C.amber,2);h(slide,ctx,790,320,860,C.amber,2);h(slide,ctx,790,408,860,C.amber,2);h(slide,ctx,790,498,860,C.amber,2);
box(slide,ctx,860,184,310,74,'section_summary','short summary + key terms',C.dark,C.blue,true);
box(slide,ctx,860,274,310,74,'TEACHES_CONCEPT','what this section teaches',C.dark,C.green,true);
box(slide,ctx,860,362,310,74,'REQUIRES_CONCEPT','what learner should know first',C.dark,C.amber,true);
box(slide,ctx,860,452,310,74,'reasoning + evidence','why the edge exists',C.dark,C.violet,true);
label(slide,ctx,'only the current section has full text',76,152,270,'#B9C0CC');
label(slide,ctx,'outputs become auditable graph artifacts',858,548,318,'#B9C0CC');
foot(slide,ctx,3,true);return slide;}
