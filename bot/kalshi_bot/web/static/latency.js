/*
 * The Latency tab: how long after minute 8 starts the live bot's orders reach Kalshi, for the current setup only.
 * Added Oct 15, 2026, and cut down the same day to the current setup only: with less than a week of data for each, a
 * comparison of setups said little.
 *
 * It draws /api/latency (latency.py): the current setup's orders, those Kalshi stamped since it went live ("since"), as
 * [stamp, landing in s after the minute-8 mark, share filled, contracts asked]; their figures ("figures"); what the
 * setup does ("setup"); where the time goes now ("where", estimates in ms) and what could come next ("next"). Nothing
 * compares it with the setups that ran earlier. Top to bottom, each part a fold:
 *
 *   Order speed     The setup's figures (median landing, each window's first order, the slowest 1 in 20, contracts
 *                   filled, how many orders and windows, since when), what the setup does, then a chart: one dot per
 *                   order on a plain seconds scale from zero, with the median and the slowest 1 in 20 as lines. The
 *                   x-axis is the orders in turn, so hours without trading take no room.
 *   Where the time  The steps of a fast window now and their estimated cost, against the measured first order.
 *   goes now
 *   What's next     The ranked ideas from the Oct 15 research, none built yet.
 *   Terms           The words used, in plain words.
 *
 * It reads /api/latency every 15 seconds while its tab and the browser tab are on screen (new orders come once a
 * window), and uses the page's own helpers (esc, pct, count, hhmm, patch, $, fold, foldsButton).
 * latencyHtml(reply) only turns a reply into markup, with no reads of the page, so the tests can run it in node.
 */
(() => {
"use strict";

// ------------------------------------------------------------------ state
const EVERY = 15000;   // ms between reads while the tab is on screen; the server caches its answer for 10 s
let last = null, busy = false, readAt = 0;   // last: null before the first answer, {httpStatus}, {error}, or the reply

// Each fold's key and whether it opens on a first visit; a viewer's own choice sticks (the page's fold helpers).
const FOLD = { "lat.chart": true, "lat.where": false, "lat.next": false, "lat.terms": false };
const KEYS = Object.keys(FOLD);

// ------------------------------------------------------------------ formatting: a missing number is a dash, never NaN
const ok = (v) => typeof v === "number" && isFinite(v);
const obj = (v) => v && typeof v === "object" && !Array.isArray(v) ? v : null;
const list = (v) => Array.isArray(v) ? v : [];
const secs = (v) => ok(v) ? (Math.abs(v) >= 10 ? v.toFixed(1) : v.toFixed(2)) + " s" : "—";   // "0.35 s", "3.95 s"
const share = (v) => ok(v) ? pct(v, 0) : "—";
const many = (n, word) => ok(n) ? `${count(n)} ${word}${n === 1 ? "" : "s"}` : "—";            // "6 orders", "1 window"
const day = (t) => new Date(t * 1000).toLocaleDateString([], { month: "short", day: "numeric" });
const notice = (html, cls = "") => `<div class="lr-alert${cls ? " " + cls : ""}" role="status">${html}</div>`;
const kpi = (k, v, s = "") => `<div class="lr-kpi"><span class="lr-k">${k}</span><span class="lr-v">${v}</span>${s ? `<span class="lr-s">${s}</span>` : ""}</div>`;
const sub = (s) => s ? `<span class="lr-sub">${s}</span>` : "";
const cell = (v) => `<td class="lr-num${v === "—" ? " lr-muted" : ""}">${v}</td>`;

// ------------------------------------------------------------------ the tab
function head(r) {
  const n = r ? list(r.orders).length : 0;
  const stamp = r ? `${count(n)} order${n === 1 ? "" : "s"} · read ${ok(r.now) ? hhmm(r.now) : "—"} · every 15 s` : "";
  const tools = (stamp ? `<span class="lr-stamp">${stamp}</span>` : "") + (r ? foldsButton(KEYS, FOLD) : "");
  return `<header class="lr-head"><div class="lr-title"><h2>Latency</h2><p>How long after minute 8 starts each live order`
    + ` of the current setup reaches Kalshi, by Kalshi's own stamp.</p></div>${tools ? `<div class="lr-tools">${tools}</div>` : ""}</header>`;
}

window.latencyHtml = (reply) => {
  if (reply == null) return head() + `<p class="lr-wait">Loading the order times…</p>`;
  const r = obj(reply);
  if (!r) return head() + notice(`<b>An answer this tab can't read.</b> ${esc(JSON.stringify(reply))}`);
  if (r.httpStatus != null) {
    return head() + notice(`<b>Restart the dashboard</b> to see Latency. Its server answered HTTP ${esc(r.httpStatus)} for this`
      + ` tab's data: a dashboard started before the tab was added doesn't know the route yet.`, "warn");
  }
  if (r.error != null) return head() + notice(`<b>No order times to show.</b> ${esc(r.error)}`);
  const orders = list(r.orders).filter((o) => Array.isArray(o) && ok(o[0]) && ok(o[1]));
  const f = obj(r.figures);
  return head(r) + speed(r, orders, f) + where(list(r.where).map(obj).filter(Boolean), f) + next(list(r.next).map(obj).filter(Boolean)) + terms();
};

// ------------------------------------------------------------------ order speed: the figures, the setup, the chart
function speed(r, orders, f) {
  const s = obj(r.setup), since = ok(r.since) ? `${day(r.since)}, ${hhmm(r.since)}` : "";   // "Oct 14, 2:04 PM", even on the day
  const figures = f && orders.length ? `<div class="lr-kpis">`
    + kpi("Landing, median", secs(f.median), "after minute 8")
    + kpi("Each window’s first order", secs(f.first), "median")
    + kpi("Slowest 1 in 20", secs(f.p95), "95th percentile")
    + kpi("Contracts filled", share(f.filled), "of those the bot asked for")
    + kpi("So far", many(f.orders, "order"), `in ${many(f.windows, "window")}${since ? `, since ${since}` : ""}`)
    + `</div>` : "";
  const what = s ? `<p class="lr-lede">${s.title ? `<b>${esc(s.title)}.</b> ` : ""}${esc(s.what)}</p>` : "";
  const top = figures || what ? `<div class="lr-top">${figures}${what}</div>` : "";
  const body = top + (orders.length ? `<div class="lr-pb">${chart(orders, f)}</div>`
    : `<p class="lr-wait">No orders yet: the chart starts with the current setup's first live order.</p>`);
  return fold("lat.chart", "Order speed", body, f && ok(f.median) ? `${secs(f.median)} median` : "", "", FOLD["lat.chart"]);
}

// The chart: 960 x 300 units, scaled to the page's width (on a phone it keeps 600 px and scrolls sideways in its box).
const VW = 960, VH = 300, L = 44, R = 12, T = 16, B = 28, PW = VW - L - R, PH = VH - T - B;
// The scale runs in plain seconds from 0 up to the first of these tops that reaches the slowest order, 60 s at most,
// with a labelled line every step.
const SCALES = [[0.5, 0.1], [1, 0.2], [2, 0.5], [5, 1], [10, 2.5], [20, 5], [60, 10]];
const f1 = (v) => +v.toFixed(1);
const tick = (v) => `${+v.toFixed(3)} s`;   // "0 s", "0.5 s", "1 s", "2.5 s": no trailing zeros

function chart(orders, f) {
  const n = orders.length, slowest = orders.reduce((a, o) => Math.max(a, o[1]), -Infinity);
  const low = orders.some((o) => o[1] < 0);
  const [top, step] = SCALES.find(([t]) => t >= slowest) || SCALES[SCALES.length - 1];
  const yOf = (v) => f1(T + PH * (1 - Math.min(top, Math.max(0, v)) / top));   // anything off the scale sits on its edge
  const xOf = (i) => f1(L + PW * (i + 0.5) / n), edge = (i) => f1(L + PW * i / n);
  const grid = Array.from({ length: Math.round(top / step) + 1 }, (_, i) => i * step).map((t) =>
    `<line class="lat-grid" x1="${L}" x2="${L + PW}" y1="${yOf(t)}" y2="${yOf(t)}"/>`
    + `<text class="lat-ax" x="${L - 6}" y="${yOf(t) + 4}" text-anchor="end">${tick(t)}</text>`).join("");
  const dots = orders.map((o, i) => `<circle class="lat-dot" cx="${xOf(i)}" cy="${yOf(o[1])}" r="1.8"/>`).join("");
  // a level across the plot, labelled at its right end: the median's label under its line, the slow tail's over it,
  // so the two stay apart however close they are
  const level = (cls, v, label, under) => {
    if (!ok(v)) return "";
    const y = yOf(v), ty = under ? Math.min(T + PH - 4, y + 14) : Math.max(T + 11, y - 5);
    return `<line class="${cls}" x1="${L}" x2="${L + PW}" y1="${y}" y2="${y}"/>`
      + `<text class="lat-lbl" x="${L + PW - 6}" y="${f1(ty)}" text-anchor="end">${esc(label)}</text>`;
  };
  const med = f && ok(f.median), tail = f && ok(f.p95);
  const levels = (tail ? level("lat-p95", f.p95, `1 in 20 slower than ${secs(f.p95)}`, false) : "")
    + (med ? level("lat-med", f.median, `median ${secs(f.median)}`, true) : "");
  const lines = med && tail ? " The solid line is the median (half the orders landed sooner) and the dashed line the slowest 1 in 20."
    : med ? " The line is the median: half the orders landed sooner." : tail ? " The dashed line is the slowest 1 in 20." : "";
  // day labels under the axis, centred on the day's orders, at most one per 64 units and none past either edge
  const days = [];
  orders.forEach((o, i) => {
    const k = new Date(o[0] * 1000).toDateString(), d = days[days.length - 1];
    if (d && d.k === k) d.last = i; else days.push({ k, first: i, last: i, t: o[0] });
  });
  let lastX = -Infinity;
  const labels = days.map((d) => {
    const x = Math.min(VW - R - 24, Math.max(L + 24, f1((edge(d.first) + edge(d.last + 1)) / 2)));
    if (x - lastX < 64) return "";
    lastX = x;
    return `<text class="lat-ax" x="${x}" y="${VH - 8}" text-anchor="middle">${esc(day(d.t))}</text>`;
  }).join("");
  const span = days.length > 1 ? `from ${day(orders[0][0])} to ${day(orders[n - 1][0])}` : `on ${day(orders[0][0])}`;
  const said = `Landing times of ${many(n, "order")} ${span}` + (med ? `, median ${secs(f.median)}` : "") + ".";
  const edges = (slowest > top ? ` Anything slower than ${tick(top)} sits on the top edge.` : "")
    + (low ? " An order Kalshi stamped a moment ahead of minute 8 sits on the zero line." : "");
  return `<figure class="lat-fig"><div class="lat-scroll"><svg class="lat-chart" viewBox="0 0 ${VW} ${VH}" role="img" aria-label="${esc(said)}">`
    + `<rect class="lat-plot" x="${L}" y="${T}" width="${PW}" height="${PH}"/>${grid}${dots}${levels}${labels}</svg></div>`
    + `<figcaption class="lr-note">Each dot is one order, in the order they went out: how many seconds after minute 8 Kalshi`
    + ` stamped it.${lines} The scale is plain seconds from zero, and hours without trading take no room.${edges}</figcaption></figure>`;
}

// ------------------------------------------------------------------ where the time goes now (estimates)
function where(rows, f) {
  const lo = rows.reduce((a, w) => a + (ok(w.lo) ? w.lo : 0), 0), hi = rows.reduce((a, w) => a + (ok(w.hi) ? w.hi : 0), 0);
  const ms = (a, b) => `${count(a)}–${count(b)} ms`;
  const body = `<p class="lr-lede">Estimates from the Oct 15 research: round trips timed from this PC, nothing timed inside a real`
    + ` order burst yet. They add up to <b>${ms(lo, hi)}</b>${f && ok(f.first) ? `, against <b>${secs(f.first)}</b> measured for each window's first order` : ""}.</p>`
    + `<div class="lr-tw"><table class="lr-t"><thead><tr><th scope="col">Step</th><th scope="col" class="lr-num">Estimate</th></tr></thead><tbody>`
    + rows.map((w) => `<tr><th scope="row">${esc(w.step)}${sub(esc(w.what))}</th>${cell(ok(w.lo) && ok(w.hi) ? ms(w.lo, w.hi) : "—")}</tr>`).join("")
    + `</tbody></table></div>`;
  return fold("lat.where", "Where the time goes now", `<div class="lr-pb">${body}</div>`, `about ${ms(lo, hi)}`, "", FOLD["lat.where"]);
}

// ------------------------------------------------------------------ what's next
function next(rows) {
  const body = `<p class="lr-lede">Ranked by time saved for the cost and effort, from the Oct 15 research.`
    + ` None of them is built; a change to the bot takes effect only after a restart.</p>`
    + `<div class="lr-tw"><table class="lr-t"><thead><tr><th scope="col">Idea</th><th scope="col" class="lr-num">Saves</th>`
    + `<th scope="col" class="lr-num">Status</th></tr></thead><tbody>`
    + rows.map((x) => `<tr><th scope="row">${esc(x.title)}${sub(esc(x.what))}</th>${cell(esc(x.saves ?? "—"))}${cell(esc(x.status ?? "—"))}</tr>`).join("")
    + `</tbody></table></div>`;
  return fold("lat.next", "What’s next", `<div class="lr-pb">${body}</div>`, `${count(rows.length)} idea${rows.length === 1 ? "" : "s"}`, "", FOLD["lat.next"]);
}

// ------------------------------------------------------------------ terms
const TERMS = [
  ["Landing", "How long after minute 8 starts Kalshi stamps an order. The bot means to order at the minute-8 mark, 480 seconds into each 15-minute window."],
  ["Kalshi's stamp", "The time Kalshi writes on each order it accepts, on its own clock. The chart uses it, so this PC's clock can't move the figures."],
  ["Median", "The middle order: half landed sooner, half later."],
  ["Slowest 1 in 20", "The 95th percentile: 1 order in 20 landed later than this."],
  ["First order", "The first order of each window. The window's other orders wait their turn behind it."],
  ["Contracts filled", "The share of the contracts the bot asked for that it got. Orders that land later find less left at the price."],
];
const terms = () => fold("lat.terms", "Terms", `<dl class="lr-dl">${TERMS.map(([t, d]) => `<dt>${t}</dt><dd>${d}</dd>`).join("")}</dl>`,
  `${TERMS.length} terms, in plain words`, "", FOLD["lat.terms"]);

// ------------------------------------------------------------------ drawing and polling
const draw = () => patch("latency", window.latencyHtml(last));

async function refresh() {
  if (busy || Date.now() - readAt < EVERY - 500) return;
  busy = true; readAt = Date.now();
  try {
    const r = await fetch("/api/latency", { cache: "no-store" });
    last = r.ok ? await r.json().catch((e) => ({ error: "The dashboard's answer isn't readable: " + e.message })) : { httpStatus: r.status };
  } catch (e) {
    last = { error: "Can't reach the dashboard's server: " + ((e && e.message) || e) };
  }
  busy = false;
  draw();
}

// The page calls this on its refresh (every second) while the tab is open: draw the last answer at once, then read a new one.
window.latencyView = () => { draw(); refresh(); };

setInterval(() => { if (!$("latency").hidden && !document.hidden) refresh(); }, EVERY);
if (page === "latency" && data) window.latencyView();   // the page drew before this script arrived
})();
