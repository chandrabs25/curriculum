import {C,bg,head,foot,box,h,dot} from './helpers.mjs';
export async function slide06(presentation,ctx){const slide=presentation.slides.add();bg(slide,ctx);head(slide,ctx,'06 / SECTION LINKS','Concept bridges create three section-to-section edge types');
box(slide,ctx,72,170,218,82,'Section A','TEACHES X\nsame chapter',C.white,C.green);
box(slide,ctx,72,330,218,82,'Section A','TEACHES X\nother chapter',C.white,C.green);
box(slide,ctx,72,490,218,82,'Section A','TEACHES X',C.white,C.green);
box(slide,ctx,370,170,190,82,'Join key','same concept X',C.white,C.blue);
box(slide,ctx,370,330,190,82,'Join key','same concept X',C.white,C.blue);
box(slide,ctx,370,490,190,82,'Join key','same concept X',C.white,C.blue);
box(slide,ctx,640,170,218,82,'Section B','REQUIRES X',C.white,C.amber);
box(slide,ctx,640,330,218,82,'Section B','REQUIRES X',C.white,C.amber);
box(slide,ctx,640,490,218,82,'Section C','TEACHES X',C.white,C.green);
box(slide,ctx,900,160,306,102,'DEPENDS_ON_UNIT','from B -> to A\nstudy A before B',C.dark,C.blue,true);
box(slide,ctx,900,320,306,102,'TRANSFER_SUPPORTS_UNIT','from B -> to A\noptional bridge',C.dark,C.green,true);
box(slide,ctx,900,480,306,102,'RELATED_BY_CONCEPT','from A -> to C\nreinforcement only',C.dark,C.amber,true);
[[290,370,640,900,211,C.blue],[290,370,640,900,371,C.green],[290,370,640,900,531,C.amber]].forEach(([x1,x2,x3,x4,y,color])=>{h(slide,ctx,x1,y,x2,color,2);dot(slide,ctx,x2,y,color,8);h(slide,ctx,560,y,x3,color,2);dot(slide,ctx,x3,y,color,8);h(slide,ctx,858,y,x4,color,2);dot(slide,ctx,x4,y,color,8);});
foot(slide,ctx,6);return slide;}
