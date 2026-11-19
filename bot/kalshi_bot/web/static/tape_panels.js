// The Tape page's detail panels (SPEC_TAPE.md, Nov 6, 2026): the left panel's Live markets, Orders, Fill rate, By market
// and Rules tabs, ported from dashboard.html (boardBlock/flashOf/sparkOf, ordersBlock, fillsBlock/fillTile/fillChart,
// more(), method()) to the Tape page's trading-terminal look. Same facts and rules as the old page; plainer words.
// Every function here returns an HTML string (boardStatus an object) and touches nothing else: no document, no fetch, no
// timers, no storage. So node can load this after tape_fmt.js with only `window = {}` (test_tape_page.py), and tape.js
// decides where the strings go. tape_panels.css styles them; every class starts "tp-" (the board's flash classes
// fl-up / fl-down / fl-flip are named by the spec and only styled under .tp-br).
(function (root) {
  "use strict";
  // TapeFmt's helpers, looked up when called, so the load order between the two files can't bite
  const fmt = (k) => (...a) => root.TapeFmt[k](...a);
  const esc = fmt("esc"), money = fmt("money"), signed = fmt("signed"), pct = fmt("pct"), limitPct = fmt("limitPct"),
    tone = fmt("tone"), cents = fmt("cents"), hhmm = fmt("hhmm"), day = fmt("day"), when = fmt("when"), count = fmt("count"),
    sym = fmt("sym"), symOf = fmt("symOf"), kalshiUrl = fmt("kalshiUrl"), groupOf = fmt("groupOf");
  const GROUPS = () => root.TapeFmt.GROUPS;

  // ---------------------------------------------------------------- shared bits
  const fin = (v) => v != null && v !== "" && isFinite(Number(v));
  const cnt = (v) => fin(v) ? count(Number(v)) : "—";
  // Kalshi fills fractions of a contract: whole numbers plain, the rest to two places (thousands with commas either way)
  const num = (v) => !fin(v) ? "—" : Number.isInteger(Number(v)) ? count(Number(v))
    : Number(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const share = (a, b) => fin(a) && fin(b) && Number(b) ? Number(a) / Number(b) : null;   // nothing to share out: "—", never NaN
  const plural = (n, one, many) => (n === 1 ? one : many || one + "s");
  const cap = (s) => { s = String(s ?? ""); return s.charAt(0).toUpperCase() + s.slice(1); };
  const SIDES = { yes: "Yes", no: "No" };
  // the bot's limits: the server's (state()'s limits) over TapeFmt's defaults; a value the server leaves null keeps the default
  const limitsOf = (d) => {
    const L = Object.assign({}, root.TapeFmt.LIMITS), s = d && d.limits;
    if (s && typeof s === "object") for (const k of Object.keys(s)) if (fin(s[k])) L[k] = Number(s[k]);
    return L;
  };
  // a market's name, linking to its 15-minute window on Kalshi (a series alone links to the series)
  const mk = (ticker, text) => `<a class="tp-mk" href="${esc(kalshiUrl(ticker))}" target="_blank" rel="noopener" title="${esc(text)} on Kalshi, opens a new tab">${esc(text)}</a>`;
  const side = (s, price) => SIDES[s] ? `<span class="tp-side">${SIDES[s]}</span>${price == null ? "" : ` <span class="tp-px">${cents(price)}</span>`}` : `<span class="muted">—</span>`;
  const sub = (html, cls) => (html ? `<span class="tp-s${cls ? " " + cls : ""}">${html}</span>` : "");
  const empty = (text, note) => `<div class="tp-empty"><p>${text}</p>${note ? `<p class="tp-empty-s">${note}</p>` : ""}</div>`;
  const PAPER = "Paper mode sends no orders to Kalshi.";
  // a table in its own sideways-scrolling box, so a wide one never scrolls the page. head: [label, class, title]
  const table = (head, rows, label, cls) => `<div class="tp-wrap"><table class="tp-t${cls ? " " + cls : ""}"${label ? ` aria-label="${esc(label)}"` : ""}>`
    + `<thead><tr>${head.map(([h, c, t, a]) => `<th scope="col"${c ? ` class="${c}"` : ""}${t ? ` title="${esc(t)}"` : ""}${a || ""}>${h}</th>`).join("")}</tr></thead>`
    + `<tbody>${rows.join("")}</tbody></table></div>`;
  // a cell; one with nothing in it yet keeps its "—" but mutes it, so the blanks recede
  const td = (html, cls) => { const c = [cls, html === "—" ? "muted" : ""].filter(Boolean).join(" "); return `<td${c ? ` class="${c}"` : ""}>${html}</td>`; };
  const signedCents = (c, dp) => !fin(c) ? "—" : (Math.abs(c) < 0.5 * Math.pow(10, -dp) ? "" : c > 0 ? "+" : "−") + Math.abs(c).toFixed(dp) + "¢";
  const toneOf = (c, dp) => !fin(c) || Math.abs(c) < 0.5 * Math.pow(10, -dp) ? "" : c > 0 ? "up" : "down";
  const nowOf = (now, d) => (fin(now) ? Number(now) : d && fin(d.now) ? Number(d.now) : Date.now() / 1000);

  // ---------------------------------------------------------------- live markets: an exchange board
  // The markets the bot trades, straight from Kalshi (/api/research/live): one table per asset class, the favourite's
  // price highest first. A favourite inside the bot's buying range before its minute-8 entry is tagged "In range"; after
  // the entry nothing more is bought in the window, so the tag goes.
  const BOARD_FRESH = 10;   // seconds: prices older than this show as stale
  // The favourite at the last draw, per market (the caller's Map): a change since then flashes its row, with an arrow.
  function flashOf(m, last) {
    const prev = last.get(m.ticker), now = m.favSide ? { side: m.favSide, px: m.favPrice } : null;
    last.set(m.ticker, now);
    if (!prev || !now || (prev.side === now.side && prev.px === now.px)) return "";
    return prev.side !== now.side ? "flip" : now.px > prev.px ? "up" : "down";
  }
  // The favourite side's price through the window so far: each minute's closing mid, then now. x spans the 15 minutes.
  function sparkOf(m, t) {
    const flip = m.favSide === "no", mid = (b, a) => (!fin(b) || !fin(a) ? null : flip ? 1 - (b + a) / 2 : (b + a) / 2);
    const pts = (Array.isArray(m.path) ? m.path : []).filter((p) => Array.isArray(p) && fin(p[0])).map((p) => [Number(p[0]), mid(p[1], p[2])]).filter((p) => p[1] != null);
    const cur = mid(m.yes_bid, m.yes_ask);
    if (cur != null) pts.push([Math.max((t % 900) / 60, pts.length ? pts[pts.length - 1][0] : 0), cur]);
    if (pts.length < 2) return `<svg class="tp-spark" viewBox="0 0 84 20" aria-hidden="true"></svg>`;
    const vs = pts.map((p) => p[1]), c = (Math.min(...vs) + Math.max(...vs)) / 2, span = Math.max(Math.max(...vs) - Math.min(...vs), 0.1);   // at least a 10¢ range
    const x = (m_) => (Math.min(Math.max(m_, 0), 15) / 15 * 82 + 1).toFixed(1), y = (v) => (10 - (v - c) / span * 17).toFixed(1);
    const end = pts[pts.length - 1];
    return `<svg class="tp-spark" viewBox="0 0 84 20" aria-hidden="true"><path d="${pts.map((p, i) => `${i ? "L" : "M"}${x(p[0])} ${y(p[1])}`).join("")}"/>`
      + `<circle cx="${x(end[0])}" cy="${y(end[1])}" r="1.8"/></svg>`;
  }

  function board(bd, data, now, last) {
    const lv = bd && bd.live, t = nowOf(now, bd), s = ((t % 900) + 900) % 900, L = limitsOf(data);
    const memo = last && typeof last.get === "function" && typeof last.set === "function" ? last : new Map();
    const traded = new Set(data && Array.isArray(data.groups) && data.groups.length ? data.groups : Object.keys(GROUPS()));
    // the band: what the bot enforces (data.limits), else what the board says, else the defaults
    const band = lv && Array.isArray(lv.band) && fin(lv.band[0]) && fin(lv.band[1]) ? lv.band.map(Number) : null;
    const [lo, hi] = (data && data.limits && fin(data.limits.lo) && fin(data.limits.hi)) || !band ? [L.lo, L.hi] : band;
    const buying = s < L.minute * 60;
    // only what the bot trades, highest favourite price first (re-sorted on every read); no price yet sorts last
    const ms = (lv && Array.isArray(lv.markets) ? lv.markets : []).filter((m) => m && m.ticker)
      .map((m) => Object.assign({}, m, { group: m.group || groupOf(symOf(m.ticker)) }))
      .filter((m) => traded.has(m.group))
      .sort((a, b) => (fin(b.favPrice) ? b.favPrice : -1) - (fin(a.favPrice) ? a.favPrice : -1) || String(a.label).localeCompare(String(b.label)));
    if (!ms.length) return `<div class="tp tp-board">${empty(!lv ? "Connecting to Kalshi's live markets…" : "None of the bot's markets is open right now.")}</div>`;
    const range = `${cents(lo)} to ${cents(hi)}`;
    const row = (m) => {
      const fl = flashOf(m, memo), sd = SIDES[m.favSide] ? m.favSide : "", px = fin(m.favPrice) ? Number(m.favPrice) : null;
      const inRange = buying && px != null && px >= lo - 1e-9 && px <= hi + 1e-9;
      // the favourite side's own bid and ask: a No favourite's are the Yes book turned over
      const [bid, ask] = sd === "no" ? [fin(m.yes_ask) ? 1 - m.yes_ask : null, fin(m.yes_bid) ? 1 - m.yes_bid : null] : [fin(m.yes_bid) ? m.yes_bid : null, fin(m.yes_ask) ? m.yes_ask : null];
      const first = Array.isArray(m.path) && m.path.length > 1 && Array.isArray(m.path[0]) ? m.path[0] : null;   // the window's first minute: one point is no move yet
      const mid = fin(m.yes_bid) && fin(m.yes_ask) ? (m.yes_bid + m.yes_ask) / 2 : fin(m.last) ? Number(m.last) : null;
      const ch = first && fin(first[1]) && fin(first[2]) && mid != null ? (mid - (first[1] + first[2]) / 2) * (sd === "no" ? -1 : 1) * 100 : null;   // in cents
      const tick = !fl ? "" : `<i class="tp-tick ${fl === "up" ? "up" : fl === "down" ? "down" : "tp-flip"}" role="img" aria-label="${fl === "flip" ? "The favourite switched sides" : fl === "up" ? "Up" : "Down"} since the last read">${fl === "up" ? "▲" : fl === "down" ? "▼" : "⇄"}</i>`;
      const fav = !sd ? "—" : `<span class="tp-fav"><span class="tp-side">${SIDES[sd]}</span><span class="tp-px">${cents(px)}</span>${tick}`
        + (inRange ? `<span class="tp-in" title="Inside the bot's ${range} buying range, before its minute-${L.minute} entry">In range</span>` : "") + `</span>`;
      return `<tr class="tp-br${inRange ? " tp-inr" : ""}${fl ? " fl-" + fl : ""}">`
        + td(mk(m.ticker, m.label || symOf(m.ticker)), "tp-l") + td(fav, "tp-l")
        + td(cents(bid), "tp-hs") + td(cents(ask), "tp-hs") + td(bid != null && ask != null ? cents(ask - bid) : "—", "tp-hs")
        + td(ch == null || Math.abs(ch) < 0.05 ? "—" : signedCents(ch, 1), toneOf(ch, 1)) + td(sparkOf(m, t), "tp-hs tp-tr") + `</tr>`;
    };
    // one table per asset class: crypto, metals, energy, then any other by name
    const known = Object.keys(GROUPS()), rank = (g) => { const i = known.indexOf(g); return i < 0 ? known.length : i; };
    const gs = [...new Set(ms.map((m) => m.group))].sort((a, b) => rank(a) - rank(b) || String(a).localeCompare(String(b)));
    const head = [["Market", "tp-l"], ["Favourite", "tp-l", "The likely side and its price; highest first", ' aria-sort="descending"'],
      ["Bid", "tp-hs", "The best price someone will pay for the favourite"], ["Ask", "tp-hs", "The cheapest the favourite is on offer"],
      ["Spread", "tp-hs", "The gap between the favourite's bid and ask: what it costs to get in"],
      ["This window", "", "How far the favourite's price has moved since the window's first minute"], ["Trend", "tp-hs tp-tr", "The favourite's price through this window"]];
    const group = (g) => {
      const mine = ms.filter((m) => m.group === g), name = GROUPS()[g] || esc(cap(g));
      return `<section class="tp-bg"><h3 class="tp-gh">${name} <span class="tp-n">${mine.length}</span></h3>${table(head, mine.map(row), name + " markets", "tp-bt")}</section>`;
    };
    return `<div class="tp tp-board"><p class="tp-note">Favourites priced ${range} are in the bot's buying range until minute ${L.minute}, when it buys.</p>`
      + `<div class="tp-bgs">${gs.map(group).join("")}</div></div>`;
  }

  // Where the board's prices come from, and how fresh they are: streaming (live), polled once a second, stale, or the
  // dashboard's server unreachable; then the minute of the 15-minute window.
  function boardStatus(bd, err, now) {
    const lv = bd && bd.live, t = nowOf(now, bd), s = ((t % 900) + 900) % 900;
    const hbRaw = lv && lv.heartbeat, hb = hbRaw == null ? null : fin(hbRaw) ? Number(hbRaw) : Date.parse(hbRaw) / 1000;
    const age = hb == null || !isFinite(hb) ? null : Math.max(0, t - hb), stream = !!lv && lv.source === "stream";
    const [kind, text] = err ? ["off", "Offline"] : age == null ? ["", "Connecting"]
      : age < BOARD_FRESH ? (stream ? ["on", "Streaming"] : ["warn", "Polling"])
      : ["warn", "Stale, " + (age < 90 ? Math.round(age) + "s" : Math.round(age / 60) + "m")];
    return { kind, text: `${text}, minute ${Math.min(15, Math.floor(s / 60) + 1)} of 15` };
  }

  // ---------------------------------------------------------------- orders: what each asked for, what filled, how it did
  // Every order is immediate-or-cancel, its limit the ask the bot saw (or limits.limitUp over it): it gets what the book
  // offers up to that limit, cheapest first, and the rest is cancelled at once, so an order fills in full, in part, or not
  // at all. What filled became a bet, which won, lost, or hasn't settled yet; an order that got nothing has no result.
  // Beside it, what the book offered when the bot read it at minute 8 (atAsk: contracts at its price; plusOne: those within
  // 1¢ over it just after), so a miss reads at a glance: nothing on offer, on offer but taken first, or the price moved up.
  const RESULTS = { won: ["up", "Won"], lost: ["down", "Lost"], open: ["muted", "Open"] };   // only these words
  function orders(d) {
    d = d || {};
    const L = limitsOf(d), list = (Array.isArray(d.orders) ? d.orders : []).filter((o) => o && typeof o === "object"), at = nowOf(null, d);
    if (!list.length) {
      return `<div class="tp tp-orders">${empty(`No orders yet. Each goes in at minute ${esc(L.minute)} as immediate-or-cancel: it fills what the book offers up to its limit, and the rest is cancelled.`,
        d.live === false ? PAPER : "")}</div>`;
    }
    // how the orders filled: the last hour (none if the day had none), the last 24 hours, then every buy order in the ledger;
    // a line the data doesn't carry is left out
    const said = (label, c) => `${label}: ${num(c.filled)} of ${num(c.asked)} contracts filled (${pct(share(c.filled, c.asked), 0)}), ${cnt(c.none)} of ${cnt(c.orders)} orders got none`;
    const F = d.fills, H = d.fillsHour, A = d.fillsAll, has = (c) => c && typeof c === "object";
    const hour = has(H) && has(F) && F.asked > 0 ? (H.asked > 0 ? said("Last hour", H) : "None in the last hour") : "";
    const dayL = has(F) ? (F.asked > 0 ? said("Last 24 hours", F) : "None in the last 24 hours") : "";
    const all = has(A) && A.asked > 0 ? said(`All time${fin(A.since) ? ` (since ${day(A.since)})` : ""}`, A) : "";
    const meta = [hour, dayL, all].filter(Boolean);
    const reads = list.some((o) => "atAsk" in o);   // a server from before the book reads sends none: no column
    const rows = list.map((o) => {
      const asked = fin(o.asked) ? Number(o.asked) : null, filled = fin(o.filled) ? Number(o.filled) : null;
      const fTone = filled == null || filled === 0 ? "tp-none" : asked != null && filled < asked ? "tp-part" : "";
      const fSub = filled == null ? esc(o.error || "got none") : filled === 0 ? "got none" : asked ? pct(filled / asked, 0) + " filled" : "";
      const [rTone, rWord] = RESULTS[o.result] || ["muted", "—"];
      const rSub = o.result === "open" ? (fin(o.close_ts) ? `settles ${hhmm(o.close_ts)}` : "") : RESULTS[o.result] && fin(o.pnl) ? signed(Number(o.pnl)) : "";
      const w = fin(o.ts) ? Number(o.ts) - (Number(o.ts) % 900) : null;
      return `<tr>`
        + td(fin(o.ts) ? `${when(o.ts, at)}${sub(`${hhmm(w)} window`)}` : "—", "tp-l")
        + td(mk(o.ticker || o.series || "", sym(o.series || String(o.ticker || "").split("-")[0]) || "—"), "tp-l")
        + td(side(o.side, fin(o.price) ? Number(o.price) : null), "tp-l")
        + td(num(asked), "tp-hs")
        + `<td class="${fTone}">${num(filled)}${asked == null ? "" : `<span class="tp-os"> of ${num(asked)}</span>`}${sub(fSub)}</td>`
        + (!reads ? "" : o.atAsk == null ? td("—") : td(`${num(o.atAsk)}${o.plusOne == null ? "" : sub(`+${num(o.plusOne)} within 1¢`)}`))
        + `<td class="${rTone}">${rWord}${sub(rSub, rTone === "muted" ? "" : rTone)}</td></tr>`;   // a profit or loss keeps its colour under the word
    });
    const head = [["Placed", "tp-l"], ["Market", "tp-l"], ["Side and price", "tp-l"], ["Asked", "tp-hs", "Contracts the order asked for"],
      ["Filled", "", "Contracts it got"], ...(reads ? [["At the ask", "", "Contracts on offer at its price when the bot read the book at minute " + L.minute]] : []), ["Result"]];
    // every buy order by its size: if bigger orders fill less, the bot is outgrowing what the books offer at 90-99¢
    const S = (Array.isArray(d.fillsBySize) ? d.fillsBySize : []).filter((g) => g && typeof g === "object");
    const bar = (f) => `<span class="tp-bar" aria-hidden="true"><i style="width:${Math.round(Math.min(Math.max(f, 0), 1) * 100)}%"></i></span>`;
    const sizes = !S.length ? "" : `<section class="tp-sec"><h3 class="tp-sh">Fills by order size</h3>`
      + `<p class="tp-note">Every buy order so far, by how many contracts it asked for. If bigger orders fill less, the bot is outgrowing what's offered at <span class="tp-nw">90–99¢</span>. Orders Kalshi refused aren't counted.</p>`
      + table([["Contracts asked", "tp-l"], ["Orders"], ["Contracts filled"], ["Got none", "", "Share of orders that got no contracts"]], S.map((g) => {
        const f = share(g.filled, g.asked) || 0;
        return `<tr>${td(esc(g.label), "tp-l")}${td(cnt(g.orders))}<td>${bar(f)}<span class="tp-szp">${pct(f, 0)}</span>${sub(`${num(g.filled)} of ${num(g.asked)}`)}</td>${td(pct(share(g.none, g.orders) || 0, 0))}</tr>`;
      }), "Fills by order size", "tp-szt") + `</section>`;
    return `<div class="tp tp-orders">${meta.length ? `<p class="tp-meta">${meta.map((l) => `<span>${l}</span>`).join("")}</p>` : ""}`
      + table(head, rows, "Orders, newest first", "tp-ot") + sizes + `</div>`;
  }

  // ---------------------------------------------------------------- fill rate: is fast entry filling more than before?
  // Two tiles lead with the answer, contracts filled and orders that got nothing since fast entry, against the
  // FILL_BEFORE_DAYS before it. Under them one line from fillWindows ([window, orders, asked, filled, none] for each
  // 15-minute window with a buy order in the last 7 days, oldest first): the share of contracts filled over the last
  // FILL_ROLL windows that asked for any. fillOff are the stretches between those windows the bot wasn't trading in
  // ([from, to, "halted" or "off"]): the line breaks across each and a hatched band covers it, so off time is never drawn
  // as if it traded through.
  const FILL_ROLL = 12;          // the windows the line is taken over: 3 hours
  const FILL_BEFORE_DAYS = 4;    // the "before fast entry" span, as the server's FILL_BEFORE_DAYS
  // fillOff's stretches cut to the chart's span [t0, t1], and only those with any time left: the ones it draws
  const offIn = (off, t0, t1) => (Array.isArray(off) ? off : []).filter((s) => Array.isArray(s) && fin(s[0]) && fin(s[1]))
    .map(([f, t, k]) => [Math.max(f, t0), Math.min(t, t1), k]).filter((s) => s[1] > s[0]);
  // A headline tile: the share since fast entry, what it was before, and the change in whole points between the two
  // figures as shown, green when it got better (up for contracts filled, down for orders that got nothing).
  function fillTile(label, now, was, upIsBetter) {
    const fig = (v) => +(v * 100).toFixed(0), diff = now == null || was == null ? null : fig(now) - fig(was);
    const cls = !diff ? "muted" : (diff > 0) === upIsBetter ? "up" : "down";
    const say = !diff ? "no change" : `${diff > 0 ? "▲" : "▼"} ${Math.abs(diff)} ${plural(Math.abs(diff), "point")}`;
    return `<div class="tp-tile"><span class="tp-tl">${label}</span><b class="tp-tv">${pct(now, 0)}</b>${diff == null ? "" : `<span class="tp-td ${cls}">${say}</span>`}`
      + `<span class="tp-ts">since fast entry${was == null ? "" : `, was ${pct(was, 0)}`}</span></div>`;
  }
  function fillChart(rows, fast, W, off, at) {
    const w_ = (t) => when(t, at);
    const t0 = rows[0][0], t1 = rows[rows.length - 1][0], on = !!fast && t0 <= fast.live && fast.live <= t1, offs = offIn(off, t0, t1);
    const A = on && fast.after, B = on && fast.before, a = on ? share(A.filled, A.asked) : null, b = on ? share(B.filled, B.asked) : null;
    const H = 200, M = { t: 18, r: a == null ? 16 : 84, b: 24, l: 48 }, rx = W - M.r, by = H - M.b, f1 = (v) => v.toFixed(1);   // the right margin: the since label
    const x = (t) => M.l + (t1 === t0 ? 0 : (t - t0) / (t1 - t0)) * (rx - M.l), y = (v) => M.t + (1 - v) * (by - M.t);
    const wide = (s) => s.length * 6.6;   // about how far the chart's text runs, to keep labels apart
    // the line: each window that asked for any, at the share filled over the last FILL_ROLL such windows up to it, picked
    // up afresh (a new M) after each stretch left out instead of running across it
    const asked = rows.filter((r) => r[2] > 0);
    const roll = new Map(asked.map((r, i) => { const last = asked.slice(Math.max(0, i - FILL_ROLL + 1), i + 1); return [r, last.reduce((s, q) => s + q[3], 0) / last.reduce((s, q) => s + q[2], 0)]; }));
    const line = asked.map((r, i) => `${!i || offs.some((s) => asked[i - 1][0] <= s[0] && s[0] < r[0]) ? "M" : "L"}${f1(x(r[0]))},${f1(y(roll.get(r)))}`).join(" ");
    const levels = [0, 0.25, 0.5, 0.75, 1];
    const grid = levels.map((v) => `<line class="tp-fr-grid" x1="${M.l}" x2="${f1(rx)}" y1="${f1(y(v))}" y2="${f1(y(v))}"/>`).join("");
    const yl = levels.map((v) => `<text x="${M.l - 8}" y="${f1(y(v) + 4)}" text-anchor="end">${pct(v, 0)}</text>`).join("");
    // times along the bottom, as many as fit apart (the first starts at the left edge, the last ends at the right, the rest
    // on the quarter hour); where even two don't, the last ends at the far right
    const apart = (ts) => ts.map((t, i) => { const w = wide(w_(t)), p = x(t); return i === 0 ? [p, p + w] : i === ts.length - 1 ? [p - w, p] : [p - w / 2, p + w / 2]; })
      .every((s, i, all) => !i || s[0] - all[i - 1][1] >= 12);
    let xt = t1 > t0 ? [t0, t1] : [t0];
    for (let k = 5; k > 2 && t1 > t0; k--) {
      const ts = Array.from({ length: k }, (_, i) => (i && i < k - 1 ? Math.round((t0 + (t1 - t0) * i / (k - 1)) / 900) * 900 : i ? t1 : t0));
      if (apart(ts)) { xt = ts; break; }
    }
    const shove = xt.length === 2 && !apart(xt);
    const xl = xt.map((t, i) => { const end = i > 0 && i === xt.length - 1; return `<text x="${f1(end && shove ? W - 16 : x(t))}" y="${H - 6}" text-anchor="${end ? "end" : i ? "middle" : "start"}">${w_(t)}</text>`; }).join("");
    // fast entry, when it went live on the chart: its period shaded, a marker where it starts (the flag above the plot,
    // turned left near the right edge), and each period's average as a dashed level line, the FILL_BEFORE_DAYS before it
    // (as far back as the chart goes), then since. The before label sits at its line's end by the marker (right of it when
    // there's no room), above the dashed line or under it, whichever the line crosses less there; the since label in the
    // right margin.
    const X = on ? x(fast.live) : 0, flag = X + 4 + wide("fast entry") > W - 8;
    let shade = "", mark = "", avg = "", avgT = "";
    if (on) {
      shade = `<rect class="tp-fr-after" x="${f1(X)}" y="${M.t}" width="${f1(Math.max(0, rx - X))}" height="${by - M.t}"/>`;
      mark = `<line class="tp-fr-mark" x1="${f1(X)}" x2="${f1(X)}" y1="4" y2="${by}"/><text class="tp-fr-mark-t" x="${f1(flag ? X - 4 : X + 4)}" y="12" text-anchor="${flag ? "end" : "start"}">fast entry</text>`;
      if (b != null) {
        const yb = y(b), s = `before: ${pct(b, 0)}`, room = X - 6 - wide(s) >= M.l, [l, r] = room ? [X - 6 - wide(s), X - 6] : [X + 6, X + 6 + wide(s)];
        const hits = (lo, hi) => asked.filter((q) => { const px = x(q[0]), py = y(roll.get(q)); return px >= l && px <= r && py >= lo && py <= hi; }).length;
        const under = yb - 16 < M.t || (yb + 18 <= by && hits(yb + 3, yb + 18) < hits(yb - 16, yb - 2));
        avg += `<line class="tp-fr-avg" x1="${f1(x(Math.max(t0, fast.live - FILL_BEFORE_DAYS * 86400)))}" x2="${f1(X)}" y1="${f1(yb)}" y2="${f1(yb)}"/>`;
        avgT += `<text class="tp-fr-avg-t" x="${f1(room ? X - 6 : X + 6)}" y="${f1(under ? yb + 14 : yb - 6)}" text-anchor="${room ? "end" : "start"}">${s}</text>`;
      }
      if (a != null) {
        avg += `<line class="tp-fr-avg" x1="${f1(X)}" x2="${f1(rx)}" y1="${f1(y(a))}" y2="${f1(y(a))}"/>`;
        avgT += `<text class="tp-fr-avg-t" x="${f1(rx + 6)}" y="${f1(y(a) + 4)}">since: ${pct(a, 0)}</text>`;
      }
    }
    // each stretch left out: a hatched band over the plot's height, whose title says what happened, labelled at its foot
    // when the word fits
    const hatch = offs.length ? `<defs><pattern id="tp-fr-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line class="tp-fr-hatch" x1="3" x2="3" y1="0" y2="6"/></pattern></defs>` : "";
    const bands = offs.map(([f, t, k]) => {
      const l = x(f), w = x(t) - l, s = k === "halted" ? "halted" : "not trading";
      return `<g class="tp-fr-off-g"><title>Bot ${s}: ${w_(f)} to ${w_(t)}, left out of the line</title><rect class="tp-fr-off" x="${f1(l)}" y="${M.t}" width="${f1(w)}" height="${by - M.t}"/>`
        + `${w >= wide(s) + 8 ? `<text class="tp-fr-off-t" x="${f1(l + w / 2)}" y="${by - 6}" text-anchor="middle">${s}</text>` : ""}</g>`;
    }).join("");
    // under the pointer, a column per window (halfway to its neighbours, but never into a band), whose title gives its figures
    const xs = rows.map((r) => x(r[0]));
    const cols = rows.map((r, i) => {
      const l = Math.max(i ? (xs[i - 1] + xs[i]) / 2 : M.l, ...offs.filter((s) => s[1] <= r[0]).map((s) => x(s[1])));
      const rr = Math.min(i < rows.length - 1 ? (xs[i] + xs[i + 1]) / 2 : rx, ...offs.filter((s) => s[0] >= r[0]).map((s) => x(s[0]))), v = roll.get(r);
      return `<g class="tp-fr-pt"><title>${w_(r[0])} window: ${num(r[3])} of ${num(r[2])} contracts filled${r[2] ? ` (${pct(r[3] / r[2], 0)})` : ""}, ${cnt(r[4])} of ${cnt(r[1])} orders got none`
        + `${v == null ? "" : `; last ${FILL_ROLL} windows: ${pct(v, 0)}`}</title><rect class="tp-fr-hit" x="${f1(l)}" y="${M.t}" width="${f1(Math.max(0, rr - l))}" height="${by - M.t}"/></g>`;
    }).join("");
    const say = `Share of contracts filled in each 15-minute window: ${count(rows.length)} ${plural(rows.length, "window")}, ${w_(t0)} to ${w_(t1)}.`
      + (!on ? "" : (A.orders ? ` Since fast entry: ${pct(a, 0)} of contracts filled and ${pct(share(A.none, A.orders), 0)} of orders got none` : " Since fast entry: no orders yet")
        + (B.orders ? `; the ${FILL_BEFORE_DAYS} days before: ${pct(b, 0)} and ${pct(share(B.none, B.orders), 0)}` : "") + ".")
      + (offs.length ? ` Left out: ${offs.length} ${plural(offs.length, "stretch", "stretches")} when the bot wasn't trading.` : "");
    return `<svg class="tp-fr" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="${esc(say)}">${hatch}${shade}${bands}${grid}${mark}${avg}`
      + `<path class="tp-fr-ln" d="${line}"/>${avgT}<g class="tp-fr-axis">${yl}${xl}</g>${cols}</svg>`;
  }

  function fills(d, width) {
    d = d || {};
    const at = nowOf(null, d), R = Array.isArray(d.fillWindows) ? d.fillWindows.filter((r) => Array.isArray(r) && r.length >= 5 && r.every(fin)).map((r) => r.map(Number)) : null;
    const FF = d.fillsFast, F = FF && fin(FF.live) && FF.after && FF.before ? FF : null, A = F && F.after, B = F && F.before;
    const W = Math.max(300, Math.floor(fin(width) ? Number(width) : 640));
    // what fast entry has filled since it went live, and in the FILL_BEFORE_DAYS before it
    const after = !F ? "" : A.orders ? `Since fast entry (${when(F.live, at)}): ${cnt(A.orders)} ${plural(A.orders, "order")}, ${pct(share(A.filled, A.asked), 0)} of contracts filled, ${pct(share(A.none, A.orders), 0)} of orders got none`
      : `Fast entry live since ${when(F.live, at)}: no orders yet`;
    const before = B && B.orders ? `The ${FILL_BEFORE_DAYS} days before: ${cnt(B.orders)} ${plural(B.orders, "order")}, ${pct(share(B.filled, B.asked), 0)} filled, ${pct(share(B.none, B.orders), 0)} got none` : "";
    const meta = (R && R.length) || (A && A.orders) || (B && B.orders) ? [after, before].filter(Boolean) : [];
    const metaHtml = meta.length ? `<p class="tp-meta">${meta.map((l) => `<span>${l}</span>`).join("")}</p>` : "";
    let body;
    if (!R) body = empty("The fill-rate chart starts once the dashboard restarts");   // a server from before the chart sends no fillWindows
    else if (!R.length) body = metaHtml + empty("No buy orders in the last 7 days", d.live === false ? PAPER : "");
    else {
      const was = (x, of) => (B && B.orders ? share(x, of) : null);
      const tiles = A && A.orders ? `<div class="tp-tiles">${fillTile("Contracts filled", share(A.filled, A.asked), was(B.filled, B.asked), true)}`
        + `${fillTile("Orders that got nothing", share(A.none, A.orders), was(B.none, B.orders), false)}</div>` : "";
      const dashed = F && R[0][0] <= F.live && F.live <= R[R.length - 1][0] && (A.asked > 0 || B.asked > 0);   // fillChart draws an average
      const hatched = offIn(d.fillOff, R[0][0], R[R.length - 1][0]).length;   // fillChart draws a band
      body = tiles + metaHtml + `<p class="tp-note">The line is the share of contracts asked for that filled, over the last ${FILL_ROLL} windows the bot placed orders in (about ${FILL_ROLL / 4} hours). `
        + `Higher is better.${dashed ? " The dashed lines are each period's average." : ""}${hatched ? " Hatched bands are times the bot wasn't trading; they're left out." : ""}</p>`
        + fillChart(R, F, W, d.fillOff, at);
    }
    return `<div class="tp tp-fills">${body}</div>`;
  }

  // ---------------------------------------------------------------- by market and by price band
  // Profit per $1 is the cents of profit for every dollar bet (profit over cost); profit is after Kalshi's fees.
  const perDollar = (pnl, staked) => (fin(pnl) && fin(staked) && Number(staked) ? Number(pnl) / Number(staked) * 100 : null);
  const PER = "Cents of profit for every dollar bet";
  function markets(d) {
    d = d || {};
    const S = (Array.isArray(d.bySeries) ? d.bySeries : []).filter((s) => s && typeof s === "object" && s.series);
    const P = (Array.isArray(d.byPrice) ? d.byPrice : []).filter((b) => b && typeof b === "object");
    const won = (w, n) => pct(share(w, n), 1);
    const money_ = (v) => (fin(v) ? Number(v) : null);
    const byMarket = !S.length ? empty("No settled bets yet.") : table(
      [["Market", "tp-l"], ["Asset class", "tp-l tp-hs"], ["Bets"], ["Won", "", "Share of bets won"], ["Money bet", "tp-hs", "What the bets cost"],
        ["Profit", "", "After fees"], ["Profit per $1", "", PER]],
      S.slice().sort((a, b) => (money_(b.pnl) ?? -Infinity) - (money_(a.pnl) ?? -Infinity) || String(a.series).localeCompare(String(b.series))).map((s) => {
        const pnl = money_(s.pnl), c = perDollar(s.pnl, s.staked), g = groupOf(sym(s.series));
        return `<tr>${td(mk(s.series, sym(s.series)), "tp-l")}${td(GROUPS()[g] || "Other", "tp-l tp-hs tp-ac")}${td(cnt(s.n))}${td(won(s.wins, s.n))}`
          + `${td(money(money_(s.staked)), "tp-hs")}${td(signed(pnl), tone(pnl))}${td(signedCents(c, 2), toneOf(c, 2))}</tr>`;
      }), "By market, most profit first", "tp-mt");
    const fees = fin(d.fees) ? (() => {
      const bets = (fin(d.wins) ? Number(d.wins) : 0) + (fin(d.losses) ? Number(d.losses) : 0) + (Array.isArray(d.openBets) ? d.openBets.length : 0);
      return `<p class="tp-note">Profit is after Kalshi's fees: ${money(Number(d.fees))} so far${bets ? `, ${money(Number(d.fees) / bets)} a bet` : ""}.</p>`;
    })() : "";
    const byBand = !P.length ? empty("No settled bets yet.") : table(
      [["Band", "tp-l", "The favourite's price when the bot decided"], ["Bets"], ["Won", "", "Share of bets won"], ["Profit", "", "After fees"], ["Profit per $1", "", PER]],
      P.map((b) => {
        const pnl = money_(b.pnl), c = perDollar(b.pnl, b.staked);
        return `<tr>${td(esc(b.label || b.key || "—"), "tp-l")}${td(cnt(b.n))}${td(won(b.wins, b.n))}${td(signed(pnl), tone(pnl))}${td(signedCents(c, 2), toneOf(c, 2))}</tr>`;
      }), "By price band", "tp-pt");
    return `<div class="tp tp-markets"><div class="tp-cols">`
      + `<section class="tp-sec"><h3 class="tp-sh">By market <span class="tp-n">${S.length}</span></h3>${byMarket}${S.length ? fees : ""}</section>`
      + `<section class="tp-sec"><h3 class="tp-sh">By price band</h3>`
      + (P.length ? `<p class="tp-note">A band pays when its bets win more often than their price: a 93¢ favourite has to win about 93% of the time to break even.</p>` : "")
      + `${byBand}</section></div></div>`;
  }

  // ---------------------------------------------------------------- rules: how it trades, its stops, its settings
  function rules(d) {
    d = d || {};
    const L = limitsOf(d), m = L.minute, min = (s) => Math.round(s / 60);
    const g = (Array.isArray(d.groups) ? d.groups : []).map(esc), groups = g.length < 2 ? g.join("") : g.slice(0, -1).join(", ") + " and " + g[g.length - 1];
    const parts = [
      ["What it buys", [
        `At the end of <b>minute ${m}</b> of every 15-minute window (entering within ${L.grace}s), it looks at each ${groups ? groups + " market" : "market it trades"}.`,
        `It buys the <b>favourite</b>, the side (Yes or No) that costs more, only if it costs <b>${cents(L.lo)} to ${cents(L.hi)}</b>.`,
        `It skips the favourite if its ask is <b>${cents(L.spreadMax)} or more over its bid</b>, if it was <b>${cents(L.lateMid)} or under at minute ${m - 2} or ${m - 1}</b>,`
          + ` or if it <b>rose ${cents(L.jump)} or more during minute ${m}</b>.`,
      ]],
      ["How much", [
        `<b>${limitPct(L.betPct)} of the bankroll</b> a bet, and a window's bets together at most <b>${limitPct(L.windowPct)}</b>. No cap on an order's size;`
          + ` whole contracts only, and no bet under $1.`,
        `It <b>holds every bet to the close</b>: $1 a contract if the favourite wins, nothing if it loses. It never sells early.`,
      ]],
      ["How it orders", [
        // live: at the ask it saw until bot.LIMIT_UP is set over 0; the +1¢ meanwhile runs on paper (bot.SHADOW_UP)
        L.limitUp > 0
          ? `An <b>immediate-or-cancel</b> limit order ${cents(L.limitUp)} over the best price it just saw on the book (at most ${cents(L.hi)}): it takes the cheapest offers first, never pays more than that limit, and nothing waits on the book.`
          : `An <b>immediate-or-cancel</b> limit order at the best price it just saw on the book: it never pays more, and nothing waits on the book.`
            + (L.shadowUp > 0 ? ` On paper it also measures what a limit ${cents(L.shadowUp)} higher would have bought (the Live Research page).` : ""),
        `No order later than <b>${L.orderDeadline}s after minute ${m}</b>, or on a book read more than <b>${L.bookMaxAge}s</b> before. Each order gets`
          + ` ${Math.round(L.orderConnect)}s to connect and ${Math.round(L.orderAnswer)}s for an answer, and is never retried.`,
        `At most ${L.ordersPerWindow} orders a window and ${L.ordersPerDay} a day. Any of its orders found resting on the book is cancelled within ${L.restingEvery}s.`,
      ]],
      ["When it stops", [
        `It <b>halts</b> when any stop-loss below trips, and places nothing more until <code>python bot.py --resume</code> is run.`,
        `It skips a window during a Fed-decision blackout, or whenever it can't confirm Kalshi is trading.`,
      ]],
    ];
    const method = `<div class="tp-method">${parts.map(([h, items]) => `<section class="tp-rg"><h3>${h}</h3><ul>${items.map((x) => `<li>${x}</li>`).join("")}</ul></section>`).join("")}</div>`;
    // the stop-losses: each halts the bot; while it's halted they're paused (nothing trades anyway)
    const base = fin(d.haltBase) && Number(d.haltBase) ? Number(d.haltBase) : fin(d.start) ? Number(d.start) : null;
    const stops = [
      [`Down ${pct(L.dayDrop, 0)} within 24 hours`, "measured from the day's peak"],
      ["Account at half its start", base == null ? "" : `${money(base * L.halfStart)} or less`],
      [`${L.windowLosses}+ bets lost in one window`, ""],
      [`A bet unsettled ${min(L.settleLag)} min after its close`, `for ${min(L.persist)} minutes running`],
      ["Kalshi pauses trading", `outside maintenance, for ${min(L.persist)} minutes`],
      ["Kalshi unreachable", `its exchange status unreadable for ${min(L.persist)} minutes`],
      [`${L.orderErrors} orders fail in a row`, "or a fill worse than the limit"],
      ["One of its orders left resting on the book", "cancelled at once"],
    ];
    const halted = !!d.halt;
    const stopList = `<section class="tp-sec"><h3 class="tp-sh">Stop-losses <span class="tp-hn">${halted ? "paused while halted" : `${stops.length} armed`}</span></h3>`
      + `<ul class="tp-stops">${stops.map(([t, s]) => `<li><span>${t}${s ? `<span class="tp-s">${s}</span>` : ""}</span><span class="tp-st${halted ? " tp-off" : ""}">${halted ? "Paused" : "Armed"}</span></li>`).join("")}</ul></section>`;
    // the bot's settings, and the next Fed-decision blackout (a blackout on now is the banners' to say)
    const kv = (k, v) => `<div class="tp-kv"><span class="tp-k">${k}</span><span class="tp-v">${v}</span></div>`;
    const bo = d.blackout, next = bo && typeof bo === "object" && !bo.active && fin(bo.from) && fin(bo.to)
      ? `<b>${esc(bo.what || "Blackout")}</b><span class="tp-s">${day(bo.from)}, ${hhmm(bo.from)}–${hhmm(bo.to)}</span>` : "";
    const settings = `<section class="tp-sec"><h3 class="tp-sh">Bot settings</h3>`
      + kv("Next bet", `<b class="num">${money(fin(d.nextBet) ? Number(d.nextBet) : null)}</b><span class="tp-s">${limitPct(L.betPct)} of the bankroll, no cap on an order</span>`)
      + kv("Window cap", `<b class="num">${limitPct(L.windowPct)}</b><span class="tp-s">${fin(d.bankroll) ? money(Number(d.bankroll) * L.windowPct) + " across a window's bets" : "of the bankroll across a window's bets"}</span>`)
      + kv("Order limits", `<b class="num">${L.ordersPerWindow}</b> a window, <b class="num">${L.ordersPerDay}</b> a day`)
      + (next ? kv("Next blackout", next) : "") + `</section>`;
    // your real Kalshi account (live modes only): the cash the bot can bet, all cash, open positions, the total
    const k = d.kalshi && typeof d.kalshi === "object" ? d.kalshi : null;
    const nm = (v) => money(fin(v) ? Number(v) : null);
    const account = !k ? "" : `<section class="tp-sec"><h3 class="tp-sh">Kalshi account${k.error ? ` <span class="tp-hn">unavailable</span>` : ""}</h3>`
      + (k.error ? `<p class="tp-note">${esc(k.error)}</p>`
        : kv("Crypto &amp; Commodities cash", `<b class="num">${nm(k.crypto)}</b><span class="tp-s">the only cash the bot can bet</span>`)
          + kv("All cash, every section", `<b class="num">${nm(k.total)}</b>`)
          + kv("Open positions", `<b class="num">${cnt(k.positions)}</b>${fin(k.held) ? `<span class="tp-s">worth ${nm(k.held)}</span>` : ""}`)
          + (fin(k.value) ? kv("Account value", `<b class="num">${nm(k.value)}</b>`) : ""))
      + `</section>`;
    return `<div class="tp tp-rules">${method}<div class="tp-secs">${stopList}${settings}${account}</div></div>`;
  }

  root.TapePanels = { board, boardStatus, orders, fills, markets, rules };
})(typeof window !== "undefined" ? window : globalThis);
