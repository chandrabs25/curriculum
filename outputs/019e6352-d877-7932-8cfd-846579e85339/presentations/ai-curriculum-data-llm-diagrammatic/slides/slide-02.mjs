import {C,bg,head,foot,codeCard,box,arrow,chip,label} from './helpers.mjs';
export async function slide02(presentation,ctx){const slide=presentation.slides.add();bg(slide,ctx);head(slide,ctx,'02 / SOURCE INGESTION','Textbook JSON is converted into section-level LLM jobs');
codeCard(slide,ctx,64,190,330,360,'chapter.json',['{','  "chapter": {','    "sections": [','      {','        "id": "...:1.3",','        "title": "Significant Figures",','        "content_text": "...",','        "subsections": [...],','        "worked_examples": [...],','        "diagrams": [...],','        "tables": [...]','      }','    ]','  }','}']);
box(slide,ctx,492,238,250,94,'Section slicer','One top-level section at a time',C.white,C.blue);arrow(slide,ctx,394,370,492,370,C.blue);label(slide,ctx,'preserve source IDs',406,342,120,C.blue);
box(slide,ctx,828,180,310,82,'Current section','full text + subsections + examples',C.softBlue,C.blue);box(slide,ctx,828,302,310,82,'Chapter skeleton','other section titles + summaries only',C.softGreen,C.green);box(slide,ctx,828,424,310,82,'Prompt guard','no whole-chapter prompt bloat',C.softAmber,C.amber);
arrow(slide,ctx,742,285,828,221,C.line);arrow(slide,ctx,742,285,828,343,C.line);arrow(slide,ctx,742,285,828,465,C.line);
chip(slide,ctx,'Unit of extraction = section',492,386,250,C.dark,C.white);foot(slide,ctx,2);return slide;}
