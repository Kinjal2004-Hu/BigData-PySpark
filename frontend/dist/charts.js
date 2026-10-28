/* Minimal SVG chart builders with a restrained, print-friendly palette. */

const NS = "http://www.w3.org/2000/svg";
export const PALETTE = ["#315EFB", "#16856B", "#C58A25", "#D14D5B", "#7C5CFC", "#2AA1C9", "#667085", "#E38A5C"];

function svgEl(tag, attrs = {}, children = []) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "text") e.textContent = v;
    else e.setAttribute(k, v);
  }
  for (const c of children) e.appendChild(c);
  return e;
}

function niceTicks(min, max, count = 5) {
  if (min === max) { min -= 1; max += 1; }
  const span = max - min;
  const step0 = span / count;
  const mag = Math.pow(10, Math.floor(Math.log10(step0)));
  const norm = step0 / mag;
  const step = (norm >= 7.5 ? 10 : norm >= 3.5 ? 5 : norm >= 1.5 ? 2 : 1) * mag;
  const lo = Math.floor(min / step) * step;
  const hi = Math.ceil(max / step) * step;
  const ticks = [];
  for (let v = lo; v <= hi + step / 2; v += step) ticks.push(Number(v.toFixed(6)));
  return { lo, hi, ticks };
}

function fmtDefault(v) {
  if (Math.abs(v) >= 1e6) return (v / 1e6).toFixed(2) + "M";
  if (Math.abs(v) >= 1e3) return (v / 1e3).toFixed(1) + "K";
  return v % 1 === 0 ? String(v) : v.toFixed(1);
}

function axes({ W, H, mL, mR, mT, mB, xLabels, yTicks, yFmt, xFmt, xTitle, yTitle }) {
  const plotW = W - mL - mR;
  const plotH = H - mT - mB;
  const inner = svgEl("g", { transform: `translate(${mL},${mT})`, class: "axis" });

  // gridlines + y labels
  const kY = yTicks.length - 1;
  const yStep = plotH / kY;
  for (let i = 0; i < yTicks.length; i++) {
    const y = plotH - i * yStep;
    inner.appendChild(svgEl("line", { x1: 0, x2: plotW, y1: y, y2: y, stroke: "#E5E7EB", "stroke-width": i === 0 ? 1 : 0.7 }));
    inner.appendChild(svgEl("text", { x: -6, y: y + 3.5, "text-anchor": "end", text: yFmt(yTicks[i]) }));
  }

  // x labels
  const k = xLabels.length;
  const dx = k > 1 ? plotW / (k - 1) : insetX(plotW, xLines);
  xLabels.forEach((lab, i) => {
    let x, anchor;
    if (k > 1) { x = i * dx; anchor = "middle"; }
    else { x = plotW / 2; anchor = "middle"; }
    inner.appendChild(svgEl("text", { x, y: plotH + 16, "text-anchor": anchor, text: xFmt ? xFmt(lab) : lab }));
  });

  if (xTitle) inner.appendChild(svgEl("text", { x: plotW / 2, y: plotH + 30, "text-anchor": "middle", "font-size": 10.5, fill: "#667085", text: xTitle }));
  if (yTitle) inner.appendChild(svgEl("text", { x: -36, y: plotH / 2, "text-anchor": "middle", transform: `rotate(-90 -36 ${plotH / 2})`, "font-size": 10.5, fill: "#667085", text: yTitle }));
  return { plotW, plotH, inner };
}

function insetX(plotW, buckets) {
  return buckets > 1 ? plotW / buckets / 2 : plotW / 2;
}

function hoverTip(svg, content, x, y) {
  const tip = svgEl("g", { class: "tip" });
  const t = svgEl("text", { x, y, class: "bar-tip", "text-anchor": "middle", text: content });
  t.setAttribute("style", "paint-order: stroke; stroke: #ffffff; stroke-width: 4px; fill: #172B4D; font-size: 11px; font-weight:600;");
  tip.appendChild(t);
  svg.appendChild(tip);
  tip.remove();
  // recreate on parent hover via listeners
  return tip;
}

export function lineChart(container, data, opts = {}) {
  const el = document.createElement("div");
  el.className = "chart-wrap";
  container.appendChild(el);
  if (!data.length) { el.innerHTML = emptyNote(); return el; }
  const { yFmt = fmtDefault, xFmt, xTitle = "Date", yTitle = "Value", tipFmt, height = 230, color = PALETTE[0], area = true } = opts;
  const W = container.clientWidth || 560, H = height;
  const mL = 52, mR = 14, mT = 14, mB = 34;
  const vals = data.map(d => d.y);
  const { lo, hi, ticks } = niceTicks(Math.min(...vals), Math.max(...vals));
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("font-family", "inherit");
  const { plotW, plotH, inner } = axes({
    W, H, mL, mR, mT, mB, yTicks: ticks,
    xLabels: data.map(d => d.x), yFmt, xFmt, xTitle, yTitle,
  });
  svg.appendChild(inner);

  const X = i => (data.length > 1 ? (i * plotW) / (data.length - 1) : plotW / 2);
  const Y = v => plotH - ((v - lo) / (hi - lo)) * plotH;
  const p = data.map((d, i) => `${i === 0 ? "M" : "L"}${X(i).toFixed(2)},${Y(d.y).toFixed(2)}`).join(" ");
  if (area) {
    inner.appendChild(svgEl("path", {
      d: `${p} L${X(data.length - 1).toFixed(2)},${plotH} L${X(0).toFixed(2)},${plotH} Z`,
      fill: color, opacity: 0.08,
    }));
  }
  for (let i = 0; i < data.length; i++) {
    const c = svgEl("circle", { cx: X(i), cy: Y(data[i].y), r: 2.6, fill: "#fff", stroke: color, "stroke-width": 1.6 });
    const hit = svgEl("circle", { cx: X(i), cy: Y(data[i].y), r: 11, fill: "transparent", style: "cursor:pointer;" });
    hit.addEventListener("mousemove", ev => {
      c.setAttribute("fill", color);
      hoverTip(svg, (tipFmt ? tipFmt(data[i]) : `${data[i].x}: ${yFmt(data[i].y)}`), X(i), Y(data[i].y) - 10);
    });
    hit.addEventListener("mouseleave", () => { c.setAttribute("fill", "#fff"); svg.querySelectorAll("g.tip").forEach(g => g.remove()); });
    hit.appendChild(c.cloneNode(true));
    const frag = document.createDocumentFragment();
    frag.appendChild(hit); frag.appendChild(c);
    inner.appendChild(frag);
  }
  inner.appendChild(svgEl("path", { d: p, fill: "none", stroke: color, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round", "pointer-events": "none" }));

  el.appendChild(svg);
  return el;
}

export function barChart(container, data, opts = {}) {
  const el = document.createElement("div");
  el.className = "chart-wrap";
  container.appendChild(el);
  if (!data.length) { el.innerHTML = emptyNote(); return el; }
  const { yFmt = fmtDefault, xFmt, xTitle = "", yTitle = "Customers", tipFmt, colorBy, height = 230 } = opts;
  const W = container.clientWidth || 560, H = height;
  const mL = 52, mR = 14, mT = 14, mB = 34;
  const vals = data.map(d => d.y);
  const { lo, hi, ticks } = niceTicks(0, Math.max(...vals));
  const { plotW, plotH, inner } = axes(0, {
    W, H, mL, mR, mT, mB, yTicks: ticks, xLines: data.length,
    xLabels: data.map(d => d.x), yFmt, xFmt, xTitle, yTitle,
  });

  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.appendChild(inner);

  const bw = Math.min((plotW / data.length) * 0.62, 46);
  data.forEach((d, i) => {
    const cx = i * (plotW / data.length) + (plotW / data.length) / 2;
    const h = Math.max(((d.y - lo) / (hi - lo)) * plotH, d.y > 0 ? 2 : 0);
    const x = cx - bw / 2, y = plotH - h;
    const color = colorBy ? colorBy(i, d) : PALETTE[0];
    const rect = svgEl("rect", { x, y, width: bw, height: h, rx: 4, fill: color, opacity: 0.9 });
    const hit = svgEl("rect", { x: cx - plotW / data.length / 2, y: 0, width: plotW / data.length, height: plotH, fill: "transparent" });
    hit.addEventListener("mousemove", () => hoverTip(svg, tipFmt ? tipFmt(d) : `${d.x}: ${yFmt(d.y)}`, cx, Math.max(y - 8, 10)));
    hit.addEventListener("mouseleave", () => svg.querySelectorAll("g.tip").forEach(g => g.remove()));
    inner.appendChild(hit);
    inner.appendChild(rect);
  });

  el.appendChild(svg);
  return el;
}

export function hBarChart(container, data, opts = {}) {
  const el = document.createElement("div");
  el.className = "chart-wrap";
  container.appendChild(el);
  if (!data.length) { el.innerHTML = emptyNote(); return el; }
  const { yFmt = fmtDefault, tipFmt, height, colorFn = () => PALETTE[0], max: maxOverride } = opts;
  const W = container.clientWidth || 500;
  const H = height || 26 * data.length + 8;
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const mL = Math.max(84, (W * 0.2) | 0), mR = Math.min(72, (W * 0.16) | 0);
  const plotW = W - mL - mR;
  const rowH = (H - 4) / data.length;
  const max = maxOverride ?? Math.max(...data.map(d => d.y), 1e-9);
  data.forEach((d, i) => {
    const y = i * rowH + rowH / 2;
    const cy = y - 5.5, rh = 11;
    const w = Math.max((d.y / max) * plotW, d.y > 0 ? 2 : 0);
    svg.appendChild(svgEl("text", { x: mL - 8, y: cy + 9, "text-anchor": "end", "font-size": 11, fill: "#172B4D", text: d.x }));
    svg.appendChild(svgEl("rect", { x: mL, y: cy, width: plotW, height: rh, rx: 4, fill: "#EEF2F7" }));
    const bar = svgEl("rect", {
      x: mL, y: cy, width: w, height: rh, rx: 4, fill: colorFn(i, d), opacity: 0.92, class: "hbar",
    });
    bar.addEventListener("mousemove", ev => hoverTip(svg, tipFmt ? tipFmt(d) : `${d.x}: ${yFmt(d.y)}`, mL + w / 2, Math.max(cy - 6, 12)));
    bar.addEventListener("mouseleave", () => svg.querySelectorAll("g.tip").forEach(g => g.remove()));
    svg.appendChild(bar);
    svg.appendChild(svgEl("text", { x: W - mR + 8, y: cy + 9, "font-size": 11, fill: "#667085", "text-anchor": "start", text: yFmt(d.y) }));
  });
  el.appendChild(svg);
  return el;
}

export function donutChart(container, data, opts = {}) {
  const el = document.createElement("div");
  el.className = "chart-wrap";
  container.appendChild(el);
  if (!data.length) { el.innerHTML = emptyNote(); return el; }
  const { tipFmt, size = 210, centerTitle, centerSub } = opts;
  const W = size, H = size;
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const cx = W / 2, cy = H / 2, r = Math.min(W, H) / 2 - 6, rIn = r * 0.62;
  const total = data.reduce((a, d) => a + d.y, 0);
  let a0 = -Math.PI / 2;
  const arcs = [];
  data.forEach((d, i) => {
    const frac = d.y / total;
    const a1 = a0 + frac * Math.PI * 2;
    const large = a1 - a0 > Math.PI ? 1 : 0;
    const p0o = [cx + r * Math.cos(a0), cy + r * Math.sin(a0)];
    const p1o = [cx + r * Math.cos(a1), cy + r * Math.sin(a1)];
    const p1i = [cx + rIn * Math.cos(a1), cy + rIn * Math.sin(a1)];
    const p0i = [cx + rIn * Math.cos(a0), cy + rIn * Math.sin(a0)];
    const path = svgEl("path", {
      d: `M${p0o[0].toFixed(2)},${p0o[1].toFixed(2)} A${r},${r} 0 ${large} 1 ${p1o[0].toFixed(2)},${p1o[1].toFixed(2)} L${p1i[0].toFixed(2)},${p1i[1].toFixed(2)} A${rIn},${rIn} 0 ${large} 0 ${p0i[0].toFixed(2)},${p0i[1].toFixed(2)} Z`,
      fill: PALETTE[i % PALETTE.length], opacity: 0.92,
    });
    path.addEventListener("mousemove", () => hoverTip(svg, tipFmt ? tipFmt(d, frac) : `${d.x}: ${d.y} (${(frac * 100).toFixed(1)}%)`, cx, cy - rIn - 6));
    path.addEventListener("mouseleave", () => svg.querySelectorAll("g.tip").forEach(g => g.remove()));
    svg.appendChild(path);
    a0 = a1;
    arcs.push({ color: PALETTE[i % PALETTE.length] });
  });
  if (centerTitle) {
    svg.appendChild(svgEl("text", { x: cx, y: cy - 3, "text-anchor": "middle", "font-size": 17, "font-weight": "700", fill: "#172B4D", text: centerTitle }));
    svg.appendChild(svgEl("text", { x: cx, y: cy + 14, "text-anchor": "middle", "font-size": 10.5, fill: "#667085", text: centerSub || "" }));
  }
  el.appendChild(svg);
  el.appendChild(legend(data, opts.legendFmt));
  return el;
}

export function legend(data, legendFmt) {
  const lg = document.createElement("div");
  lg.className = "legend";
  data.forEach((d, i) => {
    const s = document.createElement("span");
    s.innerHTML = `<i style="background:${PALETTE[i % PALETTE.length]}"></i>${legendFmt ? legendFmt(d) : d.x}`;
    lg.appendChild(s);
  });
  return lg;
}

export function emptyNote(msg) {
  return `<div class="empty"><b>No data available</b>${msg || "Run an import and segmentation to populate this chart."}</div>`;
}

/* Grouped bars: series of metrics per segment, each metric scaled to its own max. */
export function groupedBars(container, data, opts = {}) {
  const el = document.createElement("div");
  el.className = "chart-wrap";
  container.appendChild(el);
  if (!data.length) { el.innerHTML = emptyNote(); return el; }
  const series = opts.series; // [{ key, label, color, fmt }]
  const W = container.clientWidth || 620, H = opts.height || 240;
  const mL = 52, mR = 14, mT = 14, mB = 40;
  const plotW = W - mL - mR, plotH = H - mT - mB;
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  // baseline axis
  const g = svgEl("g", { transform: `translate(${mL},${mT})`, class: "axis" });
  g.appendChild(svgEl("line", { x1: 0, x2: plotW, y1: plotH, y2: plotH, stroke: "#E5E7EB" }));
  const nSeg = data.length;
  const segW = plotW / nSeg;
  data.forEach((d, i) => {
    const cx = i * segW + segW / 2;
    const per = segW / (series.length + 1);
    series.forEach((s, si) => {
      const v = d[s.key];
      const vmax = Math.max(...data.map(x => x[s.key]), 1e-9);
      const h = (v / vmax) * (plotH - 24);
      const x = cx - segW / 2 + per * (si + 0.5);
      const rect = svgEl("rect", {
        x, y: plotH - h, width: per * 0.8, height: Math.max(h, v > 0 ? 2 : 0), rx: 3, fill: s.color, opacity: 0.92,
      });
      rect.addEventListener("mousemove", () =>
        hoverTip(svg, `${d.segment}: ${s.label} ${s.fmt ? s.fmt(v) : fmtDefault(v)}`, x + per * 0.4, Math.max(plotH - h - 8, 10)));
      rect.addEventListener("mouseleave", () => svg.querySelectorAll("g.tip").forEach(g => g.remove()));
      g.appendChild(rect);
    });
    g.appendChild(svgEl("text", { x: cx, y: plotH + 14, "text-anchor": "middle", text: d.segment }));
  });
  svg.appendChild(g);
  el.appendChild(svg);
  el.appendChild(legend(series.map(s => ({ x: s.label, y: 0 })) , (ld, i) => series[i].label));
  // recolor legend markers
  el.querySelectorAll(".legend i").forEach((n, i) => (n.style.background = series[i].color));
  return el;
}
