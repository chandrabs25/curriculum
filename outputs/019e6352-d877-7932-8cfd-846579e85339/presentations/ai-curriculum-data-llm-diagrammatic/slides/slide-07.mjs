import {C,bg,head,foot,box,chip,h,v,dot} from './helpers.mjs';
export async function slide07(presentation,ctx){const slide=presentation.slides.add();bg(slide,ctx,C.dark);head(slide,ctx,'07 / RETRIEVAL PACKET','Runtime retrieval combines vector matches with graph expansion',true);
const panel='#151922';
box(slide,ctx,58,262,190,128,'Learning request','subject filter\n+ refined intent',panel,C.blue,true);
box(slide,ctx,302,206,210,110,'Query embedding','BGE-M3 vector\n1024 dimensions',panel,C.violet,true);
box(slide,ctx,574,206,210,110,'pgvector search','subject-scoped\ntop candidate pool',panel,C.violet,true);
box(slide,ctx,846,206,210,110,'Rank gate','vector score\nevidence score\nmax target seeds',panel,C.amber,true);
box(slide,ctx,454,426,250,110,'Graph expansion','DEPENDS_ON_UNIT\nTRANSFER_SUPPORTS_UNIT\nRELATED_BY_CONCEPT',panel,C.green,true);
box(slide,ctx,806,402,318,158,'Planner packet','selected target IDs\nhard prerequisites\noptional buckets\nsection-link reasons',panel,C.red,true);
h(slide,ctx,248,326,280,C.blue,2);v(slide,ctx,280,261,326,C.blue,2);h(slide,ctx,280,261,302,C.blue,2);dot(slide,ctx,302,261,C.blue,8);
h(slide,ctx,512,261,574,C.violet,2);dot(slide,ctx,574,261,C.violet,8);
h(slide,ctx,784,261,846,C.violet,2);dot(slide,ctx,846,261,C.violet,8);
v(slide,ctx,951,316,360,C.amber,2);h(slide,ctx,579,360,951,C.amber,2);v(slide,ctx,579,360,426,C.green,2);dot(slide,ctx,579,426,C.green,8);
h(slide,ctx,704,481,806,C.green,2);dot(slide,ctx,806,481,C.green,8);
chip(slide,ctx,'candidate pool can be broad',322,356,220,C.softViolet,C.violet);
chip(slide,ctx,'planner packet stays bounded',840,594,244,C.softAmber,C.amber);
chip(slide,ctx,'no full textbook text in this call',468,610,300,C.dark,C.white);
foot(slide,ctx,7,true);return slide;}
