export const C = {
  paper:'#F7F3EA', ink:'#141414', muted:'#746F66', line:'#D7CFC0',
  blue:'#2F6FED', green:'#16A06A', amber:'#D98622', violet:'#6F5AE8', red:'#D84E4E',
  softBlue:'#E7EEF9', softGreen:'#E6F3EC', softAmber:'#F7E9D5', softViolet:'#ECE8FA', softRed:'#F7E0DE',
  dark:'#111318', white:'#FFFFFF'
};
export function bg(slide,ctx,fill=C.paper){ctx.addShape(slide,{left:0,top:0,width:1280,height:720,fill,line:ctx.line(fill,0)});}
export function head(slide,ctx,kicker,title,dark=false){
 const color=dark?C.white:C.ink;
 ctx.addText(slide,{text:kicker,left:56,top:38,width:260,height:20,fontSize:11,bold:true,color:C.blue,typeface:ctx.fonts.body,insets:{left:0,right:0,top:0,bottom:0}});
 ctx.addText(slide,{text:title,left:56,top:64,width:920,height:76,fontSize:34,bold:true,color,typeface:ctx.fonts.title,insets:{left:0,right:0,top:0,bottom:0}});
}
export function foot(slide,ctx,n,dark=false){ctx.addText(slide,{text:`${String(n).padStart(2,'0')} / AI Curriculum Creator`,left:56,top:676,width:220,height:16,fontSize:9,color:dark?'#8D95A3':'#9B9488',typeface:ctx.fonts.body,insets:{left:0,right:0,top:0,bottom:0}});}
export function box(slide,ctx,x,y,w,h,label,sub='',fill=C.white,accent=C.blue,dark=false){
 ctx.addShape(slide,{left:x,top:y,width:w,height:h,fill,line:ctx.line(dark?'#39404D':C.line,1)});
 ctx.addShape(slide,{left:x,top:y,width:6,height:h,fill:accent,line:ctx.line(accent,0)});
 ctx.addText(slide,{text:label,left:x+18,top:y+14,width:w-30,height:24,fontSize:17,bold:true,color:dark?C.white:C.ink,typeface:ctx.fonts.body,insets:{left:0,right:0,top:0,bottom:0}});
 if(sub)ctx.addText(slide,{text:sub,left:x+18,top:y+45,width:w-30,height:Math.max(16,h-56),fontSize:12.2,color:dark?'#B9C0CC':C.muted,typeface:ctx.fonts.body,insets:{left:0,right:0,top:0,bottom:0}});
}
export function small(slide,ctx,x,y,w,h,label,fill=C.white,accent=C.blue){
 ctx.addShape(slide,{left:x,top:y,width:w,height:h,fill,line:ctx.line(C.line,1)});
 ctx.addText(slide,{text:label,left:x+10,top:y+10,width:w-20,height:h-20,fontSize:13,bold:true,color:C.ink,align:'center',valign:'middle',typeface:ctx.fonts.body,insets:{left:0,right:0,top:0,bottom:0}});
 ctx.addShape(slide,{left:x,top:y+h-5,width:w,height:5,fill:accent,line:ctx.line(accent,0)});
}
export function line(slide,ctx,x1,y1,x2,y2,color=C.line,t=2){
 const left=Math.min(x1,x2), top=Math.min(y1,y2), w=Math.max(Math.abs(x2-x1),t), h=Math.max(Math.abs(y2-y1),t);
 ctx.addShape(slide,{left,top,width:w,height:h,fill:color,line:ctx.line(color,0)});
}
export function h(slide,ctx,x1,y,x2,color=C.line,t=2){ctx.addShape(slide,{left:x1,top:y,width:x2-x1,height:t,fill:color,line:ctx.line(color,0)});}
export function v(slide,ctx,x,y1,y2,color=C.line,t=2){ctx.addShape(slide,{left:x,top:y1,width:t,height:y2-y1,fill:color,line:ctx.line(color,0)});}
export function dot(slide,ctx,x,y,color=C.blue,s=10){ctx.addShape(slide,{geometry:'ellipse',left:x-s/2,top:y-s/2,width:s,height:s,fill:color,line:ctx.line(color,0)});}
export function arrow(slide,ctx,x1,y1,x2,y2,color=C.line){h(slide,ctx,x1,y1,x2,color,2); dot(slide,ctx,x2,y2,color,8);}
export function label(slide,ctx,text,x,y,w=160,color=C.muted){ctx.addText(slide,{text,left:x,top:y,width:w,height:18,fontSize:10.5,bold:true,color,align:'center',typeface:ctx.fonts.body,insets:{left:0,right:0,top:0,bottom:0}});}
export function codeCard(slide,ctx,x,y,w,h,title,lines){
 ctx.addShape(slide,{left:x,top:y,width:w,height:h,fill:'#101318',line:ctx.line('#303642',1)});
 ctx.addText(slide,{text:title,left:x+18,top:y+14,width:w-36,height:20,fontSize:13,bold:true,color:'#8CB4FF',typeface:ctx.fonts.mono,insets:{left:0,right:0,top:0,bottom:0}});
 ctx.addText(slide,{text:lines.join('\n'),left:x+18,top:y+48,width:w-36,height:h-58,fontSize:12,color:'#DCE3EE',typeface:ctx.fonts.mono,insets:{left:0,right:0,top:0,bottom:0}});
}
export function chip(slide,ctx,text,x,y,w,fill,color){ctx.addShape(slide,{left:x,top:y,width:w,height:28,fill,line:ctx.line(fill,0)});ctx.addText(slide,{text,left:x+8,top:y+7,width:w-16,height:14,fontSize:10.5,bold:true,color,align:'center',typeface:ctx.fonts.body,insets:{left:0,right:0,top:0,bottom:0}});}
