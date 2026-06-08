export const C = {
  paper: '#F7F3EA',
  ink: '#121316',
  muted: '#6F6A61',
  line: '#D8D0C2',
  blue: '#2F6FED',
  green: '#16A06A',
  amber: '#D98622',
  red: '#D84E4E',
  violet: '#6F5AE8',
  white: '#FFFFFF',
  softBlue: '#E7EEF9',
  softGreen: '#E6F3EC',
  softAmber: '#F6E8D4',
  dark: '#121316',
  dark2: '#1D2026',
};

export function bg(slide, ctx, fill = C.paper) {
  ctx.addShape(slide, { left: 0, top: 0, width: 1280, height: 720, fill, line: ctx.line(fill, 0) });
}

export function title(slide, ctx, kicker, claim, note, dark = false) {
  const color = dark ? C.white : C.ink;
  const muted = dark ? '#AEB5C2' : C.muted;
  ctx.addText(slide, { text: kicker, left: 68, top: 42, width: 420, height: 24, fontSize: 12, bold: true, color: C.blue, typeface: ctx.fonts.body, insets: { left: 0, right: 0, top: 0, bottom: 0 } });
  ctx.addText(slide, { text: claim, left: 66, top: 74, width: 880, height: 86, fontSize: 36, bold: true, color, typeface: ctx.fonts.title, insets: { left: 0, right: 0, top: 0, bottom: 0 } });
  if (note) ctx.addText(slide, { text: note, left: 68, top: 176, width: 780, height: 40, fontSize: 15, color: muted, typeface: ctx.fonts.body, insets: { left: 0, right: 0, top: 0, bottom: 0 } });
}

export function footer(slide, ctx, n, dark = false) {
  const color = dark ? '#8E96A3' : '#9B9488';
  ctx.addText(slide, { text: `AI Curriculum Creator / ${String(n).padStart(2, '0')}`, left: 68, top: 676, width: 300, height: 18, fontSize: 10, color, typeface: ctx.fonts.body, insets: { left: 0, right: 0, top: 0, bottom: 0 } });
}

export function node(slide, ctx, { x, y, w, h, label, sub = '', fill = C.white, stroke = C.line, accent = C.blue, dark = false }) {
  ctx.addShape(slide, { left: x, top: y, width: w, height: h, fill, line: ctx.line(stroke, 1) });
  ctx.addShape(slide, { left: x, top: y, width: 5, height: h, fill: accent, line: ctx.line(accent, 0) });
  ctx.addText(slide, { text: label, left: x + 18, top: y + 14, width: w - 28, height: 24, fontSize: 17, bold: true, color: dark ? C.white : C.ink, typeface: ctx.fonts.body, insets: { left: 0, right: 0, top: 0, bottom: 0 } });
  if (sub) ctx.addText(slide, { text: sub, left: x + 18, top: y + 46, width: w - 28, height: h - 66, fontSize: 12.5, color: dark ? '#AEB5C2' : C.muted, typeface: ctx.fonts.body, insets: { left: 0, right: 0, top: 0, bottom: 0 } });
}

export function hline(slide, ctx, x1, y, x2, color = C.line, thickness = 2) {
  ctx.addShape(slide, { left: x1, top: y, width: x2 - x1, height: thickness, fill: color, line: ctx.line(color, 0) });
}

export function vline(slide, ctx, x, y1, y2, color = C.line, thickness = 2) {
  ctx.addShape(slide, { left: x, top: y1, width: thickness, height: y2 - y1, fill: color, line: ctx.line(color, 0) });
}

export function dot(slide, ctx, x, y, color = C.blue, size = 10) {
  ctx.addShape(slide, { geometry: 'ellipse', left: x - size / 2, top: y - size / 2, width: size, height: size, fill: color, line: ctx.line(color, 0) });
}

export function pill(slide, ctx, text, x, y, w, fill, color = C.ink) {
  ctx.addShape(slide, { left: x, top: y, width: w, height: 30, fill, line: ctx.line(fill, 0) });
  ctx.addText(slide, { text, left: x + 10, top: y + 7, width: w - 20, height: 16, fontSize: 11.5, bold: true, color, align: 'center', typeface: ctx.fonts.body, insets: { left: 0, right: 0, top: 0, bottom: 0 } });
}

export function metric(slide, ctx, value, label, x, y, color = C.blue, dark = false) {
  ctx.addText(slide, { text: value, left: x, top: y, width: 160, height: 38, fontSize: 34, bold: true, color, typeface: ctx.fonts.title, insets: { left: 0, right: 0, top: 0, bottom: 0 } });
  ctx.addText(slide, { text: label, left: x, top: y + 54, width: 180, height: 34, fontSize: 12, color: dark ? '#AEB5C2' : C.muted, typeface: ctx.fonts.body, insets: { left: 0, right: 0, top: 0, bottom: 0 } });
}

export function miniTable(slide, ctx, rows, x, y, w, rowH = 42) {
  rows.forEach((r, i) => {
    const yy = y + i * rowH;
    ctx.addShape(slide, { left: x, top: yy, width: w, height: rowH - 1, fill: i === 0 ? C.dark : C.white, line: ctx.line(C.line, 1) });
    ctx.addText(slide, { text: r[0], left: x + 14, top: yy + 12, width: 170, height: 20, fontSize: 12.5, bold: i === 0, color: i === 0 ? C.white : C.ink, typeface: ctx.fonts.body, insets: { left: 0, right: 0, top: 0, bottom: 0 } });
    ctx.addText(slide, { text: r[1], left: x + 200, top: yy + 12, width: w - 220, height: 20, fontSize: 12.5, color: i === 0 ? C.white : C.muted, typeface: ctx.fonts.body, insets: { left: 0, right: 0, top: 0, bottom: 0 } });
  });
}
