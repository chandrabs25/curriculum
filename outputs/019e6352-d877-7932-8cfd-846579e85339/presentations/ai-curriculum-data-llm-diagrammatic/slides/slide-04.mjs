import {C,bg,head,foot,box,arrow,chip,dot,h,label} from './helpers.mjs';
export async function slide04(presentation,ctx){const slide=presentation.slides.add();bg(slide,ctx);head(slide,ctx,'04 / CONCEPT NORMALIZATION','Many labels collapse into one canonical concept ID');
box(slide,ctx,76,190,270,78,'significant figures','raw label from section 1.3',C.white,C.green);
box(slide,ctx,76,300,270,78,'significant digits','raw label from another section',C.white,C.green);
box(slide,ctx,76,410,270,78,'measurement precision','related, but not identical',C.white,C.amber);
h(slide,ctx,346,229,484,C.green,2);dot(slide,ctx,484,229,C.green,8);
h(slide,ctx,346,339,484,C.green,2);dot(slide,ctx,484,339,C.green,8);
h(slide,ctx,346,449,484,C.amber,2);dot(slide,ctx,484,449,C.amber,8);
box(slide,ctx,484,204,270,284,'Review gate','same concept?\nmerge if equivalent\nkeep distinct if broader/narrower',C.softBlue,C.blue);
box(slide,ctx,858,220,330,96,'concept:significant_figures','aliases: significant digits',C.softGreen,C.green);
box(slide,ctx,858,390,330,96,'concept:measurement_precision','separate canonical concept',C.softAmber,C.amber);
h(slide,ctx,754,268,858,C.green,2);dot(slide,ctx,858,268,C.green,8);
h(slide,ctx,754,438,858,C.amber,2);dot(slide,ctx,858,438,C.amber,8);
chip(slide,ctx,'canonical concept IDs become graph targets',466,506,330,C.dark,C.white);
label(slide,ctx,'review prevents accidental over-merging',846,516,330,C.muted);
foot(slide,ctx,4);return slide;}
