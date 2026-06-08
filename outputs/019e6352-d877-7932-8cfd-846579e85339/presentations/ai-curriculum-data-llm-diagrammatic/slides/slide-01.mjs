import {C,bg,head,foot,box,chip,h,v,dot,label} from './helpers.mjs';
export async function slide01(presentation,ctx){const slide=presentation.slides.add();bg(slide,ctx);head(slide,ctx,'01 / WHY RELATIONSHIPS','A textbook is linear. A personalized curriculum is not.');

label(slide,ctx,'textbook gives one reading direction',126,164,320,C.muted);
h(slide,ctx,112,258,1146,C.line,4);
box(slide,ctx,104,210,146,96,'Section 1','next page',C.white,C.blue);
box(slide,ctx,314,210,146,96,'Section 2','next page',C.white,C.blue);
box(slide,ctx,524,210,146,96,'Section 3','next page',C.white,C.blue);
box(slide,ctx,734,210,146,96,'Section 4','next page',C.white,C.blue);
box(slide,ctx,944,210,146,96,'Section 5','next page',C.white,C.blue);
box(slide,ctx,1110,222,58,72,'...','',C.white,C.blue);

label(slide,ctx,'curriculum generation needs a map with more movement',444,374,420,C.muted);
box(slide,ctx,474,438,332,96,'Relationship layer','connects sections by meaning\ninstead of page order alone',C.dark,C.violet,true);

box(slide,ctx,80,438,288,96,'Dimension 2','prerequisite travel\nmove backward to what must be known',C.softGreen,C.green);
box(slide,ctx,912,438,288,96,'Dimension 3','similar-concept travel\nmove sideways to build intuition',C.softAmber,C.amber);

h(slide,ctx,368,486,474,C.green,3);dot(slide,ctx,474,486,C.green,10);
h(slide,ctx,806,486,912,C.amber,3);dot(slide,ctx,912,486,C.amber,10);
v(slide,ctx,640,306,438,C.blue,3);dot(slide,ctx,640,438,C.blue,10);

chip(slide,ctx,'relationship extraction turns textbook content into prerequisite paths and reinforcement paths',282,604,720,C.dark,C.white);
foot(slide,ctx,1);return slide;}
