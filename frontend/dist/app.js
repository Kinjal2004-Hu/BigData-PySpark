import { lineChart, barChart, hBarChart, donutChart, groupedBars, PALETTE, emptyNote } from "/charts.js";

/* ---------------- helpers ---------------- */
const $ = (sel, r = document) => r.querySelector(sel);
const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const api = async path => {
  const r = await fetch(`/api/v1${path}`);
  if (!r.ok) {
    const j = await r.json().catch(() => ({}));
    throw new Error(typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail || r.statusText));
  }
  return r.json();
};
const money = v => "$" + Number(v ?? 0).toLocaleString("en-US", { maximumFractionDigits: 0 });
const moneyP = v => "$" + Number(v ?? 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const num = v => Number(v ?? 0).toLocaleString("en-US");
const pct = v => (v ?? 0).toFixed(1) + "%";
const dt = v => (v ? new Date(v.replace(" ", "T") + (v.includes("Z") ? "" : "Z")).toLocaleString("en-GB", { day: "2-digit", month: "short", year: "2-digit", hour: "2-digit", minute: "2-digit" }) : "—");
const dtShort = v => (v ? new Date(String(v).replace(" ", "T")).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "2-digit" }) : "—");
const isDate = v => typeof v === "string" && /^\d{4}-\d{2}-\d{2}/.test(v);
const fmtCell = v => (v == null || v === "" ? "—" : isDate(v) ? dt(v) : typeof v === "number" ? v.toLocaleString("en-US") : esc(v));
const toast = (msg, cls = "") => {
  const t = document.createElement("div");
  t.className = "toast " + cls;
  t.textContent = msg;
  $("#toasts").appendChild(t);
  setTimeout(() => t.remove(), 4000);
};

const SEG_COLORS = { "Champions": "#16856B", "Loyal Customers": "#315EFB", "Potential Loyalists": "#7C5CFC", "New Customers": "#2AA1C9", "At Risk": "#C58A25", "Hibernating": "#D14D5B", "Dormant": "#9AA3B2", "Emerging": "#E38A5C" };
const segColor = name => SEG_COLORS[name] || PALETTE[3];
const scoreColor = s => (s >= 12 ? "#16856B" : s >= 9 ? "#315EFB" : s >= 7 ? "#C58A25" : "#D14D5B");

const ICON = {
  grid: "M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z",
  users: "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM23 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8",
  layers: "M12 2 2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5",
  chart: "M18 20V10M12 20V4M6 20v-6",
  upload: "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12",
  cpu: "M4 4h16v16H4zM9 9h6v6H9M2 9h2M2 15h2M20 9h2M20 15h2M9 2v2M15 2v2M9 20v2M15 20v2",
  gear: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a7.6 7.6 0 0 0 .1 1l2 1.6-2 3.4-2.4-1a7.6 7.6 0 0 0-1.7 1l-.4 2.6h-4l-.4-2.6a7.6 7.6 0 0 0-1.7-1l-2.4 1-2-3.4 2-1.6a7.6 7.6 0 0 0-.1-1 7.6 7.6 0 0 0 .1-1l-2-1.6 2-3.4 2.4 1a7.6 7.6 0 0 0 1.7-1l.4-2.6h4l.4 2.6a7.6 7.6 0 0 0 1.7 1l2.4-1 2 3.4-2 1.6a7.6 7.6 0 0 0 .1 1z",
  bell: "M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 0 1-3.4 0",
  refresh: "M23 4v6h-6M1 20v-6h6M3.5 9a9 9 0 0 1 14.9-3.4L23 10M1 14l4.6 4.4A9 9 0 0 0 20.5 15",
  dl: "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3",
  search: "M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16zM21 21l-4.3-4.3",
  back: "M15 18l-6-6 6-6",
};
const svgi = (k, cls = "") => `<svg class="${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="${ICON[k]}"/></svg>`;

const NAV = [
  ["Overview", "#/", "grid"],
  ["Customers", "#/customers", "users"],
  ["Segments", "#/segments", "layers"],
  ["Analytics", "#/analytics", "chart"],
  ["Data Import", "#/import", "upload"],
  ["Processing Jobs", "#/jobs", "cpu"],
  ["Settings", "#/settings", "gear"],
];

/* ---------------- app state ---------------- */
const state = { range: "all", ds: null, health: null };

async function loadHealth() {
  try { state.health = await api("/health"); } catch { state.health = null; }
}

function renderSidebar() {
  const route = location.hash.split("/")[1] || "";
  const activeKey = ({ "": "Overview", customers: "Customers", segments: "Segments", analytics: "Analytics", import: "Data Import", jobs: "Processing Jobs", settings: "Settings" }[route] || "Overview").toLowerCase();
  $("#sidebar").innerHTML = `
    <div class="logo">
      <div class="mark">${svgi("chart", "m")}</div>
      <div class="word">CustomerIQ<small>PURCHASE ANALYTICS</small></div>
    </div>
    <nav class="nav">${NAV.map(([label, href, icon]) => `
      <a href="${href}" class="${label.toLowerCase() === activeKey ? "active" : ""}">${svgi(icon)}${label}</a>`).join("")}
    </nav>
    <div class="workspace">
      <div class="avatar">KO</div>
      <div class="who"><b>Retail Workspace</b><span>Local development</span></div>
    </div>`;
}

function renderTopbar(page, sub) {
  const h = state.health || {};
  const done = h.last_processed;
  $("#topbar").innerHTML = `
    <button class="icon-btn menu-btn" onclick="document.getElementById('sidebar').classList.toggle('open')">${svgi("grid")}</button>
    <div class="crumb"><div class="page">${page}</div><div class="sub">${sub || "CustomerIQ"}</div></div>
    <div class="spacer"></div>
    <select class="ctl" id="rangeSel" title="Global date range">
      <option value="all" ${state.range === "all" ? "selected" : ""}>All time</option>
      <option value="30" ${state.range === "30" ? "selected" : ""}>Last 30 days</option>
      <option value="90" ${state.range === "90" ? "selected" : ""}>Last 90 days</option>
      <option value="180" ${state.range === "180" ? "selected" : ""}>Last 180 days</option>
      <option value="365" ${state.range === "365" ? "selected" : ""}>Last 365 days</option>
    </select>
    <div class="meta" title="Last successful processing">${done ? '<span class="dot"></span>' : '<span class="dot warn"></span>'}<span>${done ? "Processed " + dt(done) : "Not processed yet"}</span></div>
    <button class="icon-btn" id="refreshBtn" title="Refresh data">${svgi("refresh")}</button>
    <button class="icon-btn" id="bellBtn" title="Notifications">${svgi("bell")}</button>`;
  $("#refreshBtn").onclick = () => router(true);
  $("#rangeSel").onchange = e => { state.range = e.target.value; router(); };
  $("#bellBtn").onclick = async () => {
    const acts = await api("/dashboard/activity?limit=6").catch(() => []);
    toast(acts.length ? `Latest: ${acts[0].event}` : "No activity recorded", "");
  };
}

function card(title, hint, body, tight = false, head = "") {
  return `<section class="card">
    <div class="card-h"><h3>${title}</h3><span class="hint">${hint || ""}</span><div style="margin-left:auto">${head}</div></div>
    <div class="card-b ${tight ? "tight" : ""}">${body}</div></section>`;
}
const skeleton = h => `<div class="skeleton" style="height:${h}px"></div>`;

/* ---------------- pages ---------------- */
async function pageOverview() {
  const days = state.range === "all" ? null : Number(state.range);
  const s = await api("/dashboard/summary");
  const acts = await api("/dashboard/activity?limit=8");
  const trend = await api(`/analytics/revenue-trend${days ? `?days=${days}` : ""}`);
  const dist = await api("/analytics/segment-distribution");
  const rev = await api("/analytics/segment-revenue");
  const freq = await api("/analytics/purchase-frequency");
  const rfm = await api("/analytics/rfm-overview");

  const kpiHTML = s.kpis.map(k => {
    const delta = k.delta == null ? "" : `<div class="delta ${k.delta >= 0 ? "up" : "down"}">${k.delta >= 0 ? "▲" : "▼"} ${Math.abs(k.delta)}% ${k.delta_label ? esc(k.delta_label) : ""}</div>`;
    return `<div class="card kpi"><div class="label">${esc(k.label)}</div><div class="value">${esc(k.formatted)}</div>${delta}</div>`;
  }).join("");

  return `
  <div class="grid kpis">${kpiHTML}</div>
  ${s.total_revenue === 0 ? `<div class="notice">No processed dataset yet — import a CSV in <a href="#/import">Data Import</a> to populate the dashboard.</div>` : ""}
  <div class="grid rows2">
    ${card("Revenue Trend", "Monthly revenue from valid purchases", `<div id="chTrend">${skeleton(200)}</div>`)}
    ${card("Customer Segment Distribution", "Customers per K-Means segment", `<div id="chDist" style="display:flex;justify-content:center">${skeleton(210)}</div>`)}
  </div>
  <div class="grid rows2" style="margin-top:14px">
    ${card("Revenue by Segment", "Highest-revenue segments ranked", `<div id="chRev">${skeleton(210)}</div>`)}
    ${card("Purchase Frequency", "Orders per customer (histogram)", `<div id="chFreq">${skeleton(210)}</div>`)}
  </div>
  <div class="grid rows2" style="margin-top:14px">
    ${card("RFM Overview by Segment", "Average recency / frequency / monetary", `<div id="chRfm">${skeleton(230)}</div>`)}
    ${card("Recent Activity", "Latest imports, jobs and events", "", true)}
  </div>`;
}

function fillOverviewCharts(s, trend, dist, rev, freq, rfm) {
  const t = trend.map(p => ({ x: p.period, y: p.revenue }));
  lineChart($("#chTrend"), t, { yFmt: money, xFmt: x => x.slice(2), xTitle: "Month", yTitle: "Revenue ($)", tipFmt: d => `${d.x}: ${moneyP(d.y)}`, height: 220 });

  donutChart($("#chDist"), dist.map(d => ({ x: d.name, y: d.customers })), {
    centerTitle: num(s.total_customers), centerSub: "customers",
    tipFmt: (d, f) => `${d.x}: ${num(d.y)} (${(f * 100).toFixed(1)}%)`, size: 220,
  }).then; // sync
  $("#chDist").querySelectorAll(".legend i").forEach((n, i) => (n.style.background = segColor(dist[i] && dist[i].name || i)));

  hBarChart($("#chRev"), rev.map(d => ({ x: d.name, y: d.revenue })), {
    yFmt: money, colorFn: (i, d) => segColor(d.x), tipFmt: d => `${d.x}: ${moneyP(d.y)} (${d.pct}%)`,
  });

  barChart($("#chFreq"), freq.map(d => ({ x: d.bucket, y: d.customers })), { xTitle: "Orders per customer", yTitle: "Customers", yFmt: num });

  groupedBars($("#chRfm"), rfm.map(r => ({ segment: r.segment, avg_recency: r.avg_recency, avg_frequency: r.avg_frequency, avg_monetary: r.avg_monetary })), {
    series: [
      { key: "avg_monetary", label: "Monetary ($)", color: "#315EFB", fmt: money },
      { key: "avg_frequency", label: "Frequency", color: "#16856B", fmt: v => v.toFixed(1) },
      { key: "avg_recency", label: "Recency (days)", color: "#C58A25", fmt: v => v.toFixed(0) + "d" },
    ], height: 220,
  });

  const tb = $("#activityBody");
  if (tb) tb.innerHTML = acts.map(a => `<tr>
      <td>${esc(a.event)}</td><td>${esc(a.target || "—")}</td>
      <td>${a.status === "failed" ? '<span class="status-dot failed"></span>Failed' : a.status === "info" ? "Info" : '<span class="status-dot completed"></span>Success'}</td>
      <td class="r num">${dt(a.created_at)}</td></tr>`).join("") || `<tr><td colspan="4"><div class="empty"><b>No activity yet</b>Operations will appear here.</div></td></tr>`;
}

async function pageSegments() {
  const segs = await api("/analytics/segments-overview");
  if (!segs.length) return `<div class="card"><div class="empty"><b>No segments yet</b>Run segmentation from the <a href="#/import">Data Import</a> workflow.</div></div>`;
  return `
  <div class="grid rows2" style="margin-bottom:14px">
    ${card("Customer Count by Segment", "", `<div id="chDist2">${skeleton(200)}</div>`)}
    ${card("Revenue Contribution", "", `<div id="chRev2">${skeleton(200)}</div>`)}
  </div>
  <h3 style="margin:18px 0 10px;font-size:14px">Segment profiles</h3>
  <div class="seg-grid">
    ${segs.map(sg => `
      <div class="card seg-card">
        <h4><span class="cd" style="width:9px;height:9px;border-radius:50%;background:${segColor(sg.name)};display:inline-block"></span>
        ${esc(sg.name)} <span style="font-weight:500;color:var(--muted);font-size:11px">cluster ${sg.cluster_id}</span></h4>
        <div class="desc">${esc(sg.description || "")}</div>
        <div class="stats">
          <div class="s"><div class="k">Customers</div><div class="v">${num(sg.customer_count)} (${pct(sg.pct_of_customers)})</div></div>
          <div class="s"><div class="k">Revenue</div><div class="v">${money(sg.revenue)} (${pct(sg.pct_of_revenue)})</div></div>
          <div class="s"><div class="k">Avg Spend</div><div class="v">${moneyP(sg.avg_spend)}</div></div>
          <div class="s"><div class="k">Avg Frequency</div><div class="v">${sg.avg_frequency.toFixed(1)}</div></div>
          <div class="s"><div class="k">Avg Recency</div><div class="v">${sg.avg_recency.toFixed(0)} days</div></div>
          <div class="s"><div class="k">Avg Order Value</div><div class="v">${moneyP(sg.pct_of_revenue && (sg.revenue / Math.max(1, sg.customer_count) / Math.max(1, sg.avg_frequency)) || 0)}</div></div>
        </div>
        <div class="bar"><i style="width:${Math.min(sg.pct_of_customers, 100)}%;background:${segColor(sg.name)}"></i></div>
      </div>`).join("")}
  </div>`;
}

async function pageCustomersList() {
  return `
  <div class="toolbar">
    <input id="fSearch" class="ctl" style="width:180px" placeholder="Search customer ID…">
    <label class="inline">Segment <select id="fSeg" class="ctl" style="width:150px"></select></label>
    <label class="inline">RFM score <select id="fScore" class="ctl" style="width:90px"><option value="">All</option>${[15,14,13,12,11,10,9,8,7,6,5,4,3].map(s=>`<option value="${s}">${s}</option>`).join("")}</select></label>
    <label class="inline">Sort <select id="fSort" class="ctl"><option value="monetary">Monetary</option><option value="frequency">Frequency</option><option value="recency">Recency</option><option value="last_purchase">Last purchase</option><option value="customer_id">Customer ID</option></select>
    <select id="fOrder" class="ctl"><option value="desc">Desc</option><option value="asc">Asc</option></select></label>
    <div class="grow"></div>
    <button class="btn" id="exportBtn">${svgi("dl")}Export CSV</button>
  </div>
  <section class="card">
    <table class="table">
      <thead><tr><th>Customer ID</th><th>Last Purchase</th><th class="r">Recency (d)</th><th class="r">Frequency</th><th class="r">Monetary</th><th>Segment</th><th class="r">RFM Score</th></tr></thead>
      <tbody id="rows">${`<tr><td colspan="7">${skeleton(240)}</td></tr>`}</tbody>
    </table>
    <div class="pager" id="pager"></div>
  </section>`;
}

async function fillCustomersList(page = 1, filters = {}) {
  const segs = await api("/segments");
  const segSel = $("#fSeg");
  if (segSel && !segSel.options.length) segSel.innerHTML = `<option value="">All segments</option>` + segs.map(s => `<option value="${esc(s.id)}">${esc(s.name)}</option>`).join("");
  if (segSel && filters.segment) segSel.value = filters.segment;
  if ($("#fSearch") && !$("#fSearch").value) $("#fSearch").value = filters.search || "";

  const q = new URLSearchParams(Object.entries({ page, page_size: 25, ...filters }).filter(([, v]) => v !== "" && v != null));
  const res = await api("/customers?" + q);
  $("#rows").innerHTML = res.items.length ? res.items.map(c => `<tr class="clickable" onclick="location.hash='#/customers/${esc(c.customer_id)}'">
      <td style="font-weight:600">${esc(c.customer_id)}</td>
      <td>${dt(c.last_purchase)}</td>
      <td class="r num">${c.recency_days ?? "—"}</td>
      <td class="r num">${num(c.frequency)}</td>
      <td class="r num">${moneyP(c.monetary)}</td>
      <td>${c.segment_name ? `<span class="badge"><span class="cd" style="background:${segColor(c.segment_name)}"></span>${esc(c.segment_name)}</span>` : "—"}</td>
      <td class="r"><span class="score-chip" style="background:${scoreColor(c.rfm_score || 0)}">${c.rfm_score ?? "—"}</span></td>
    </tr>`).join("") : `<tr><td colspan="7"><div class="empty"><b>No customers match</b>Adjust the filters or run segmentation.</div></td></tr>`;
  const pages = Math.ceil(res.total / res.page_size);
  $("#pager").innerHTML = `
    <span>Showing ${(res.page - 1) * res.page_size + 1}–${Math.min(res.total, res.page * res.page_size)} of ${num(res.total)} customers</span>
    ${pages > 1 && res.page > 1 ? `<button class="btn" data-pg="${res.page - 1}">‹ Prev</button>` : ""}
    <span>Page ${res.page} / ${pages}</span>
    ${pages > 1 && res.page < pages ? `<button class="btn" data-pg="${res.page + 1}">Next ›</button>` : ""}`;
  $("#pager").querySelectorAll("[data-pg]").forEach(b => (b.onclick = () => fillCustomersList(Number(b.dataset.pg), filters)));
}

async function pageCustomerDetail(id) {
  let c;
  try { c = await api(`/customers/${encodeURIComponent(id)}`); }
  catch (e) { return `<div class="notice">Customer not found — ${esc(e.message)}</div>`; }
  const tx = await api(`/customers/${encodeURIComponent(id)}/transactions?limit=60`);
  const trend = await api(`/customers/${encodeURIComponent(id)}/spending-trend`);
  return `
  <div class="crumbs"><a href="#/customers">Customers</a> <span>/</span> <span>${esc(id)}</span></div>
  <div class="grid rows2">
    ${card(`Customer ${esc(id)}`, c.segment_name || "", `
      <div class="dl-inline">
        <div class="d"><div class="k">Segment</div><div class="v">${c.segment_name ? `<span class="badge"><span class="cd" style="background:${segColor(c.segment_name)}"></span>${esc(c.segment_name)}</span>` : "—"}</div></div>
        <div class="d"><div class="k">RFM Score</div><div class="v"><span class="score-chip" style="background:${scoreColor(c.rfm_score || 0)}">${c.rfm_score ?? "—"}</span></div></div>
        <div class="d"><div class="k">Country</div><div class="v">${esc(c.country || "—")}</div></div>
        <div class="d"><div class="k">Cluster</div><div class="v">#${c.cluster_id ?? "—"} <span style="color:var(--muted);font-weight:500;font-size:11px">(K-Means)</span></div></div>
      </div>
      <div class="dl-inline" style="margin-top:12px">
        <div class="d"><div class="k">Recency (days)</div><div class="v">${c.recency_days ?? "—"}</div></div>
        <div class="d"><div class="k">Frequency (orders)</div><div class="v">${num(c.frequency ?? c.order_count)}</div></div>
        <div class="d"><div class="k">Monetary</div><div class="v">${moneyP(c.monetary)}</div></div>
      </div>`)}
    ${card("Purchase Summary", "", `
      <div class="dl-inline">
        <div class="d"><div class="k">Total Spend</div><div class="v">${moneyP(c.total_spend)}</div></div>
        <div class="d"><div class="k">Orders</div><div class="v">${num(c.order_count)}</div></div>
        <div class="d"><div class="k">Avg Order Value</div><div class="v">${moneyP(c.avg_order_value)}</div></div>
        <div class="d"><div class="k">First Purchase</div><div class="v">${dt(c.first_purchase)}</div></div>
        <div class="d"><div class="k">Last Purchase</div><div class="v">${dt(c.last_purchase)}</div></div>
      </div>`)}
  </div>
  ${trend.length >= 2 ? `<div style="margin-top:14px">${card("Spending Trend", "Monthly spend", `<div id="chSpend">${skeleton(180)}</div>`)}</div>` : ""}
  <div style="margin-top:14px" id="txCard">${card("Purchase History", `Most recent ${tx.length} order lines (of available)`, `<div id="txBody">${skeleton(220)}</div>`, true)}</div>`;

}

async function pageAnalytics() {
  const [trend, acq, rep, freq, mon, rfmScore, recency, countries] = await Promise.all([
    api("/analytics/revenue-trend"), api("/analytics/acquisition"), api("/analytics/repeat-vs-onetime"),
    api("/analytics/purchase-frequency"), api("/analytics/monetary-distribution"),
    api("/analytics/rfm-score-distribution"), api("/analytics/recency-distribution"), api("/analytics/country-analysis"),
  ]);
  return `
  <div class="grid rows2">
    ${card("Monthly Revenue Trend", "All valid purchases", `<div id="aTrend">${skeleton(210)}</div>`)}
    ${card("Customer Acquisition", "New customers by first purchase month", `<div id="aAcq">${skeleton(210)}</div>`)}
  </div>
  <div class="grid rows2" style="margin-top:14px">
    ${card("Repeat vs One-time Customers", `${pct(rep.repeat_pct)} of customers repeat`, `<div id="aRep">${skeleton(190)}</div>`)}
    ${card("Purchase Frequency Distribution", "Orders per customer", `<div id="aFreq">${skeleton(210)}</div>`)}
  </div>
  <div class="grid rows2" style="margin-top:14px">
    ${card("Monetary Value Distribution", "Total spend per customer", `<div id="aMon">${skeleton(210)}</div>`)}
    ${card("RFM Score Distribution", "Score = R + F + M quintiles (3–15)", `<div id="aScore">${skeleton(210)}</div>`)}
  </div>
  <div class="grid rows2" style="margin-top:14px">
    ${card("Customer Inactivity Analysis", "Days since last purchase", `<div id="aInact">${skeleton(200)}</div>`)}
    ${card("Revenue by Country", countries.length ? "Top countries by revenue" : "Dataset has no country data", `<div id="aCountry">${skeleton(200)}</div>`)}
  </div>`;
}

async function pageImport() {
  const quality = await api("/dashboard/summary");
  const jobs = await api("/jobs?job_type=import&limit=3");
  const dsList = await api("/datasets");
  return `
  <div class="imp-grid">
    <div>
      ${card("1 · Upload CSV", `Up to 512 MB · streamed to disk`, `
        <div class="dropzone" id="drop">
          ${svgi("upload")}
          <b>Click to choose or drop a file</b>
          <small>InvoiceNo, StockCode, Description, Quantity, InvoiceDate, UnitPrice, CustomerID, Country</small>
        </div>
        <input type="file" id="file" accept=".csv" style="display:none">
        <p style="font-size:11.5px;color:var(--muted);margin:10px 0 0">Preview shows the first 10 rows. Full validation runs in the processing job — including duplicates, dates, quantities, prices and cancellations.</p>
      `, false, `<span id="upState"></span>`)}
      <div style="margin-top:14px">
        ${card("Sample dataset", "Deterministic synthetic retail data", `
          <p style="margin:0 0 12px;font-size:12.5px;color:var(--muted)">No file? Use the bundled demo dataset (~105k transactions, 4,300 customers, seeded data-quality issues).</p>
          <button class="btn" id="useSample">Use demo dataset</button>
        `)}
      </div>
    </div>
    <div>
      <div id="previewCard" class="hidden"></div>
      ${card("2 · Column mapping", "", `
        <div id="mapping"><div class="empty"><b>Waiting for upload</b>Upload a CSV to configure the transaction schema mapping.</div></div>
      `)}
      <div style="margin-top:14px">
        ${card("3 · Data quality", "Last import validation results", `
          ${dsList.status && dsList[0] ? "" : ""}
          <div id="quality"><div class="empty"><b>No import yet</b>Statistics appear after the first import completes.</div></div>
        `)}
      </div>
    </div>
  </div>`;
}

async function pageJobs() {
  const ds = await api("/datasets");
  const jobs = await api("/jobs?limit=50");
  return `
  <div class="grid rows2" style="margin-bottom:14px">
    ${card("Run segmentation", "K-Means via PySpark MLlib (seed 42)", `
      <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
        <label class="inline">Dataset
          <select id="runDs" class="ctl" style="width:220px">${ds.map(d => `<option value="${esc(d.id)}">${esc(d.name)} (${d.status})</option>`).join("")}</select>
        </label>
        <label class="inline">Clusters k <input id="runK" class="ctl" type="number" min="2" max="20" value="6" style="width:64px"></label>
        <button class="btn primary" id="runSeg">Run K-Means</button>
        <span style="font-size:11.5px;color:var(--muted)">Reference date = latest purchase + 1 day (reproducible)</span>
      </div>`)}
    ${card("Job lifecycle", "pending → running → completed / failed", `
      <div style="display:flex;gap:16px;font-size:12px;color:var(--muted)">
        <span><span class="status-dot completed"></span>Completed</span>
        <span><span class="status-dot running"></span>Running</span>
        <span><span class="status-dot pending"></span>Pending</span>
        <span><span class="status-dot failed"></span>Failed</span>
        <span>Auto-refreshes every 3 s while jobs are running</span>
      </div>`)}
  </div>
  <section class="card"><table class="table">
    <thead><tr><th>Job ID</th><th>Dataset</th><th>Type</th><th>Status</th><th>Stage</th><th class="r">Records</th><th>Started</th><th>Finished</th><th></th></tr></thead>
    <tbody id="jobRows">${jobs.length ? "" : `<tr><td colspan="9"><div class="empty"><b>No jobs yet</b>Runs appear here.</div></td></tr>`}</tbody>
  </table></section>`;
}

async function fillJobRows() {
  const jobs = await api("/jobs?limit=50");
  const tb = $("#jobRows");
  if (!tb) return false;
  tb.innerHTML = jobs.map(j => `<tr>
      <td style="font-weight:600" title="${esc(j.id)}">${esc(j.id.slice(0, 8))}…</td>
      <td>${esc(j.dataset_name || j.dataset_id?.slice(0, 8) || "—")}</td>
      <td><span class="badge blue">${esc(j.job_type)}</span></td>
      <td><span class="status-dot ${esc(j.status)}"></span>${esc(j.status)}</td>
      <td style="font-size:12px;color:var(--muted);max-width:210px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${esc(j.stage || "")}">${esc(j.stage || "—")}</td>
      <td class="r num">${j.records_processed ? num(j.records_processed) : "—"}</td>
      <td>${dt(j.started_at)}</td><td>${dt(j.finished_at)}</td>
      <td>${j.status === "failed" && j.job_type === "segmentation" ? `<button class="btn" data-retry="${esc(j.id)}">Retry</button>` : ""}</td>
    </tr>
    ${j.error_summary ? `<tr><td colspan="9" style="background:#fdf6f7;color:#b13a48;font-size:12px;padding:7px 14px">⚠ ${esc(j.error_summary)}</td></tr>` : ""}`).join("");
  tb.querySelectorAll("[data-retry]").forEach(b => (b.onclick = async () => {
    const r = await fetch(`/api/v1/jobs/${b.dataset.retry}/retry`, { method: "POST" });
    if (r.ok) { toast("Job queued for retry", "ok"); fillJobRows(); } else toast((await r.json().catch(() => ({}))).detail || "Retry failed", "err");
  }));
  return jobs.some(j => j.status === "pending" || j.status === "running");
}

async function pageSettings() {
  const h = state.health;
  return `
  ${card("Workspace", "Local development instance", `
    <div class="dl-inline">
      <div class="d"><div class="k">Workspace</div><div class="v">Retail</div></div>
      <div class="d"><div class="k">Environment</div><div class="v" style="font-size:12.5px">local · no external APIs</div></div>
      <div class="d"><div class="k">API version</div><div class="v">${esc(h?.version || "—")}</div></div>
      <div class="d"><div class="k">Database</div><div class="v">${esc(h?.database || "—")}</div></div>
      <div class="d"><div class="k">Active dataset</div><div class="v" style="font-size:12.5px">${esc((h?.active_dataset || "").slice(0, 12) || "—")}…</div></div>
    </div>`)}
  <div class="grid rows2" style="margin-top:14px">
    ${card("Segmentation configuration", "Defaults used by new segmentation runs", `
      <div class="dl-inline">
        <div class="d"><div class="k">Algorithm</div><div class="v">K-Means — PySpark MLlib</div></div>
        <div class="d"><div class="k">Default k</div><div class="v">6</div></div>
        <div class="d"><div class="k">Random seed</div><div class="v num">42</div></div>
        <div class="d"><div class="k">Features</div><div class="v" style="font-size:12px">Recency · log1p(Frequency) · log1p(Monetary)</div></div>
        <div class="d"><div class="k">Scaling</div><div class="v">StandardScaler (mean/std)</div></div>
        <div class="d"><div class="k">Evaluation</div><div class="v">Silhouette score</div></div>
      </div>`)}
    ${card("Validation policy", "Applied consistently at import", `
      <ul style="margin:0;padding-left:18px;font-size:12.5px;color:var(--muted);line-height:1.8">
        <li>Exact duplicate rows: excluded (keep first), counted</li>
        <li>Unparseable invoice dates: excluded, counted</li>
        <li>Quantity ≤ 0 or negative price: excluded, counted</li>
        <li>Missing CustomerID: excluded from customer analysis, counted</li>
        <li>Cancellations/returns (InvoiceNo starting 'C'): excluded from RFM, counted</li>
        <li>Reference date: latest valid purchase + 1 day</li>
      </ul>`)}
  </div>`;
}

/* ---------------- router ---------------- */
const routes = {
  "/": { title: "Overview", sub: "Purchase analytics & segmentation", render: () => pageOverview(), after: null },
  "/customers": { title: "Customers", sub: "Search, filter and inspect customers", render: () => pageCustomersList() },
  "/segments": { title: "Segments", sub: "K-Means segments with RFM profiles", render: () => pageSegments() },
  "/analytics": { title: "Analytics", sub: "Trends, distributions and cohorts", render: () => pageAnalytics() },
  "/import": { title: "Data Import", sub: "Upload, map, validate and import CSV", render: () => pageImport() },
  "/jobs": { title: "Processing Jobs", sub: "Import and segmentation runs", render: () => pageJobs() },
  "/settings": { title: "Settings", sub: "Workspace and pipeline configuration", render: () => pageSettings() },
};

let lastOverviewData = null;
let jobTimer = null;

async function route() {
  const [pathPart, arg] = location.hash.slice(2).split("/");
  const key = "/" + pathPart;
  clearInterval(jobTimer); jobTimer = null;
  $("#content").innerHTML = `<div class="skeleton" style="height:120px"></div>`;
  renderSidebar();
  await loadHealth();

  try {
    if (key === "/customers" && arg) {
      renderTopbar("Customer detail", arg);
      const c = await api(`/customers/${encodeURIComponent(arg)}`);
      $("#content").innerHTML = `<div class="crumbs"><a href="#/customers">Customers</a> <span>/</span> <span>${esc(arg)}</span></div>` + await pageCustomerDetail(arg);
      const sp = await api(`/customers/${encodeURIComponent(arg)}/spending-trend`).catch(() => []);
      if (sp.length >= 2) lineChart($("#chSpend"), sp.map(p => ({ x: p.month, y: p.spend })), { yFmt: money, xTitle: "Month", yTitle: "Spend ($)", tipFmt: d => `${d.x}: ${moneyP(d.y)}`, height: 190 });
      const tx = await api(`/customers/${encodeURIComponent(arg)}/transactions?limit=80`).catch(() => []);
      $("#txBody").innerHTML = `<table class="table"><thead><tr><th>Invoice</th><th>Date</th><th>Product</th><th class="r">Qty</th><th class="r">Unit Price</th><th class="r">Revenue</th><th>Country</th></tr></thead><tbody>` +
        (tx.length ? tx.map(t => `<tr><td>${esc(t.invoice_no)}</td><td>${dt(t.invoice_date)}</td><td>${esc((t.description || "").slice(0, 42))}</td><td class="r num">${t.quantity}</td><td class="r num">${moneyP(t.unit_price)}</td><td class="r num">${moneyP(t.revenue)}</td><td style="color:var(--muted)">${esc(t.country)}</td></tr>`).join("") : `<tr><td colspan="7"><div class="empty"><b>No purchase history</b>for this customer in the dataset.</div></td></tr>`) + `</tbody></table>`;
    } else {
      const r = routes[key] || routes["/"];
      renderTopbar(r.title, r.sub);
      $("#content").innerHTML = await r.render();
      if (key === "/") { renderAfter(); }
      if (key === "/customers") await refreshCustomers(1);
      if (key === "/segments") renderSegmentsCharts();
      if (key === "/analytics") renderAnalyticsCharts();
      if (key === "/jobs") { fillJobRows(); jobTimer = setInterval(async () => { const busy = await fillJobRows(); if (!busy && jobTimer) { clearInterval(jobTimer); jobTimer = null; } }, 3000); }
      if (key === "/import") wireImport();
    }
  } catch (e) {
    $("#content").innerHTML = `<div class="notice">Could not load data — ${esc(e.message)}</div>`;
  }
}
window.addEventListener("hashchange", route);

/* dynamic chart fillers */
async function renderAfter() {
  try {
    const s = await api("/dashboard/summary");
    const trend = await api(`/analytics/revenue-trend${state.range === "all" ? "" : `?days=${state.range}`}`);
    const [dist, rev, freq, rfm, acts] = await Promise.all([
      api("/analytics/segment-distribution"), api("/analytics/segment-revenue"),
      api("/analytics/purchase-frequency"), api("/analytics/rfm-overview"), api("/dashboard/activity?limit=8"),
    ]);
    lineChart($("#chTrend"), trend.map(p => ({ x: p.period, y: p.revenue })), { yFmt: money, xFmt: x => x.slice(2), xTitle: "Month", yTitle: "Revenue", tipFmt: d => `${d.x}: ${moneyP(d.y)}` });
    donutChart($("#chDist"), dist.map(d => ({ x: d.name, y: d.customers })), { centerTitle: num(s.total_customers), centerSub: "customers", tipFmt: (d, f) => `${d.x}: ${num(d.y)} (${(f * 100).toFixed(1)}%)` });
    $("#chDist").querySelector(".legend")?.remove();
    $("#chDist").appendChild(document.createRange().createContextualFragment(`<div class="legend">${dist.map(d => `<span><i style="background:${segColor(d.name)}"></i>${esc(d.name)} (${d.pct}%)</span>`).join("")}</div>`).firstChild);
    hBarChart($("#chRev"), rev.map(d => ({ x: d.name, y: d.revenue })), { colorFn: (i, d) => segColor(d.x), tipFmt: d => `${d.x}: ${moneyP(d.y)} (${d.pct}%)` });
    barChart($("#chFreq"), freq.map(d => ({ x: d.bucket, y: d.customers })), { xTitle: "Orders per customer", yTitle: "Customers" });
    groupedBars($("#chRfm"), rfm.map(x => ({ segment: x.segment, avg_recency: x.avg_recency, avg_frequency: x.avg_frequency, avg_monetary: x.avg_monetary })), {
      series: [
        { key: "avg_monetary", label: "Monetary $", color: "#315EFB", fmt: money },
        { key: "avg_frequency", label: "Frequency", color: "#16856B", fmt: v => v.toFixed(1) },
        { key: "avg_recency", label: "Recency (days)", color: "#C58A25", fmt: v => v.toFixed(0) },
      ],
    });
    const tb = $("#activityBody"); if (tb) tb.parentNode.replaceChild(card2Activity(acts), tb.closest(".card-b" ) || tb);
    // simpler: just replace activity card content
    const actWrap = document.createElement("div"); actWrap.innerHTML = activityTable(acts);
    const oldCard = tb ? tb.closest(".card") : null;
    if (oldCard) oldCard.innerHTML = `<div class="card-h"><h3>Recent Activity</h3><span class="hint">Latest imports, jobs and events</span></div><div class="card-b tight">${activityTable(acts)}</div>`;
  } catch (e) { /* charts fail-safe */ }
}
function activityTable(acts) {
  return `<table class="table"><thead><tr><th style="width:38%">Event</th><th>Target</th><th>Status</th><th class="r">Timestamp</th></tr></thead><tbody>` +
    (acts.length ? acts.map(a => `<tr><td>${esc(a.event)}</td><td style="color:var(--muted)">${esc(a.target || "—")}</td><td>${a.status === "failed" ? '<span class="status-dot failed"></span>failed' : a.status === "info" ? 'info' : '<span class="status-dot completed"></span>success'}</td><td class="r num">${dt(a.created_at)}</td></tr>`).join("")
      : `<tr><td colspan="4"><div class="empty"><b>No activity yet</b>Job and import events appear here.</div></td></tr>`) + `</tbody></table>`;
}
function card2Activity(acts) { return document.createElement("div"); }

async function refreshCustomers(page = 1) {
  const filters = {
    search: $("#fSearch")?.value || "", segment: $("#fSeg")?.value || "",
    rfm_score: $("#fScore")?.value || "", sort: $("#fSort")?.value || "monetary", order: $("#fOrder")?.value || "desc",
  };
  try { await fillCustomersList(page, filters); } catch (e) { $("#rows").innerHTML = `<tr><td colspan="7"><div class="notice" style="margin:12px">${esc(e.message)}</div></td></tr>`; }
}

function renderSegmentsCharts() {
  api("/analytics/segment-distribution").then(dist => {
    $("#chDist2") && donutChart($("#chDist2"), dist.map(d => ({ x: d.name, y: d.customers })), { centerTitle: num(dist.reduce((a, d) => a + d.customers, 0)), centerSub: "customers", tipFmt: (d, f) => `${d.x}: ${num(d.y)} (${(f * 100).toFixed(1)}%)` });
    const el = $("#chDist2"); if (el) { el.querySelectorAll(".legend .marker").forEach((n, i) => {}); }
    const lg = $("#chDist2 .legend"); if (lg) lg.querySelectorAll("i").forEach((n, i) => (n.style.background = segColor(dist[i].name)));
  });
  api("/analytics/segment-revenue").then(rev => {
    $("#chRev2") && hBarChart($("#chRev2"), rev.map(d => ({ x: d.name, y: d.revenue })), { colorFn: (i, d) => segColor(d.x), tipFmt: d => `${d.x}: ${moneyP(d.y)} (${d.pct}%)` });
  });
}

async function renderAnalyticsCharts() {
  const [trend, acq, rep, freq, mon, scores, inact, countries] = await Promise.all([
    api("/analytics/revenue-trend"), api("/analytics/acquisition"), api("/analytics/repeat-vs-onetime"),
    api("/analytics/purchase-frequency"), api("/analytics/monetary-distribution"),
    api("/analytics/rfm-score-distribution"), api("/analytics/recency-distribution"), api("/analytics/country-analysis"),
  ]);
  lineChart($("#aTrend"), trend.map(p => ({ x: p.period, y: p.revenue })), { yFmt: money, xFmt: x => x.slice(2), xTitle: "Month", yTitle: "Revenue", tipFmt: d => `${d.x}: ${moneyP(d.y)}` });
  barChart($("#aAcq"), acq.map(a => ({ x: a.month, y: a.new_customers })), { xTitle: "First purchase month", yTitle: "New customers" });
  donutChart($("#aRep"), [{ x: "Repeat", y: rep.repeat_customers }, { x: "One-time", y: rep.one_time_customers }], { centerTitle: pct(rep.repeat_pct), centerSub: "repeat customers", tipFmt: d => `${d.x}: ${num(d.y)}` });
  $("#aRep .legend i").forEach ? null : null; // markers recolored below
  const lr = $("#aRep .legend"); if (lr) { lr.querySelectorAll("i").forEach(n => (n.style.background = "#315EFB")); }
  barChart($("#aFreq"), freq.map(d => ({ x: d.bucket, y: d.customers })), { xTitle: "Orders per customer", yTitle: "Customers" });
  barChart($("#aMon"), mon.map(d => ({ x: d.bucket, y: d.customers })), { xTitle: "Total spend per customer", yTitle: "Customers", yFmt: num });
  barChart($("#aScore"), scores.map(d => ({ x: String(d.score), y: d.customers })), { xTitle: "RFM score (3–15)", yTitle: "Customers", colorBy: i => scoreColor(scores[i].score) });
  barChart($("#aInact"), inact.map(d => ({ x: d.bucket, y: d.customers })), { xTitle: "Days since last purchase", yTitle: "Customers" });
  if (countries.length) hBarChart($("#aCountry"), countries.map(c => ({ x: c.country, y: c.revenue })), { tipFmt: d => `${d.x}: ${moneyP(d.y)} · ${num(d.customers)} customers` });
  else $("#aCountry").innerHTML = emptyNote("This dataset has no country column.");
}

/* ---------------- import wiring ---------------- */
function wireImport() {
  const dz = $("#drop"), file = $("#file");
  if (!dz) return;
  dz.onclick = () => file.click();
  dz.ondragover = e => { e.preventDefault(); dz.classList.add("drag"); };
  dz.ondragleave = () => dz.classList.remove("drag");
  dz.ondrop = e => { e.preventDefault(); dz.classList.remove("drag"); if (e.dataTransfer.files[0]) uploadFile(e.dataTransfer.files[0]); };
  file.onchange = () => file.files[0] && uploadFile(file.files[0]);
  $("#useSample").onclick = () => fetch("/api/v1/datasets/load-sample", { method: "POST" }).then(r => r.json()).then(async j => {
    if (j.detail) throw new Error(j.detail);
    showPreview(j);
  }).catch(e => toast(e.message, "err"));
}

async function uploadFile(f) {
  $("#upState").textContent = "Uploading…";
  const fd = new FormData(); fd.append("file", f);
  try {
    const r = await fetch("/api/v1/datasets/upload", { method: "POST", body: fd });
    const j = await r.json();
    if (!r.ok) throw new Error(j.detail || r.statusText);
    $("#upState").textContent = `${f.name} · ${(f.size / 1024 / 1024).toFixed(1)} MB`;
    toast("File uploaded — review the mapping", "ok");
    showPreview(j);
  } catch (e) { $("#upState").textContent = ""; toast(e.message, "err"); }
}

let lastPreview = null;
function showPreview(j) {
  lastPreview = j;
  const REQUIRED = [["invoice_no", "Invoice number"], ["stock_code", "Stock / product code"], ["description", "Description"], ["quantity", "Quantity"], ["invoice_date", "Invoice date"], ["unit_price", "Unit price"], ["customer_id", "Customer ID"], ["country", "Country"]];
  $("#mapping").innerHTML = `<div class="mapping-row"><div class="tgt">Name<small>dataset label</small></div><input class="ctl" id="dsName" value="${esc(j.filename.replace(/\.csv$/i, ""))}"></div>` +
    REQUIRED.map(([k, label]) => `<div class="mapping-row"><div class="tgt">${esc(label)}<small>target: ${k}</small></div>
      <select class="ctl mapsel" data-tgt="${k}"><option value="">(not mapped)</option>${j.columns.map(c => `<option value="${esc(c)}" ${j.detected_mapping[k] === c ? "selected" : ""}>${esc(c)}</option>`).join("")}</select></div>`).join("") +
    `<div style="display:flex;gap:10px;align-items:center;margin-top:12px;flex-wrap:wrap">
      <label class="inline">Duplicate policy <select id="dedupe" class="ctl"><option value="keep_first">keep first (recommended)</option><option value="keep_all">keep all (report only)</option></select></label>
      <div class="grow"></div>
      <button class="btn primary" id="confirmImport">${svgi("cpu")}Validate & process</button>
    </div>`;
  $("#previewCard").className = "";
  $("#previewCard").outerHTML = card("File preview", `${j.filename} · ${(j.file_size / 1024 / 1024).toFixed(1)} MB`, `
    <div style="overflow-x:auto"><table class="table" style="font-size:12px">
      <thead><tr>${j.columns.map(c => `<th>${esc(c)}</th>`).join("")}</tr></thead>
      <tbody>${j.rows.slice(0, 10).map(r => `<tr>${r.map(v => `<td>${esc(String(v ?? "").slice(0, 24))}</td>`).join("")}</tr>`).join("")}</tbody>
    </table></div>`);
  $("#confirmImport").onclick = confirmImport;
}
async function confirmImport() {
  const mapping = {};
  document.querySelectorAll(".mapsel").forEach(s => (mapping[s.dataset.tgt] = s.value));
  const missing = ["invoice_no", "quantity", "invoice_date", "unit_price", "customer_id"].filter(k => !mapping[k]);
  if (missing.length) { toast(`Missing mapping: ${missing.join(", ")}`, "err"); return; }
  const r = await fetch("/api/v1/datasets/confirm", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dataset_id: lastPreview.dataset_id, column_mapping: mapping, dedupe_policy: $("#dedupe").value, name: $("#dsName").value || null }),
  });
  const j = await r.json();
  if (!r.ok) { toast(typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail), "err"); return; }
  toast("Import job queued", "ok");
  location.hash = "#/jobs";
}

/* sample loader endpoint (adds a local file fast) */
route();
setInterval(async () => {
  if ((location.hash || "#/") === "#/") { const b = $("#bellBtn"); if (b) b.style.color = "#D14D5B"; }
}, 15000);
window.addEventListener("persist", () => {});
