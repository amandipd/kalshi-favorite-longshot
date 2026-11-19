/*
 * The Live Research tab: experiments the live bot is running, measured from its own ledger as its orders fill and
 * settle. The backtests replay the past; this tab follows a change to the real bot as it happens.
 * It is a list of cards, one per experiment, each drawn by one function in CARDS from the same reply. Today:
 *
 *   The +1¢ limit,  The bot buys with an immediate-or-cancel order (it takes what the book offers at once and cancels
 *   on paper        the rest), its limit (the most it will pay) at the ask it saw at minute 8. The order lands ~2.4 s
 *                   after the bot reads the book, the price has often ticked up by then, and only 55% of the contracts
 *                   it asked for were filling. So right after each real order the bot reads the book again and counts
 *                   what a limit 1¢ higher would have bought on top of the real fill (reply.shadow, the ledger's shadow
 *                   table), then settles those extra contracts on paper. No real money rides on them.
 *
 *   Fast entry,     The same orders sent sooner. Real orders land a median 2.4 s after minute 8 starts, by when other
 *   on paper        traders have taken much of what was offered at the limit. So in the background the bot reads every
 *                   order book at minute 8 exactly (480.0 s into the window, on Kalshi's clock) and pairs each real order
 *                   with what an order sent at that instant, with the same limit rule, would have bought (reply.fastShadow,
 *                   the shadow table's 'fast' rows), then settles those on paper. Real orders keep their timing. It is
 *                   the best case: an order from this PC would land 0.1-0.2 s after minute 8 at the soonest.
 *
 *   The +1¢ limit   The same cent with real money, once bot.LIMIT_UP is set above 0: how much more fills, and whether
 *   experiment      the extra contracts (those bought above the ask it saw) make money once they settle. While the
 *                   live limit is off (verdict "off") its card shows only its status and the fill rates so far.
 *
 * Every card folds, with the page's shared fold helpers (fold, foldsButton: dashboard.html). A card's
 * header keeps its title, its verdict's chip and how far along it is in view while it's folded; open, it shows the
 * verdict and the strip of figures, then "How it's measured" (what the card measures and its caveat, closed at first)
 * and its panels, each a fold of its own under lr.<card>.<panel>. Terms fold too, and the page's one Open all / Close
 * all sits in its header beside the ledger stamp. Nothing is left out of a folded body: it's only hidden.
 *
 * It reads /api/live-research every 2 seconds while its tab and the browser tab are on screen, and uses the page's
 * own helpers (esc, money, signed, pct, tone, cents, count, when, hhmm, sym, patch, $). liveResearchHtml(reply) only
 * turns a reply into markup, with no reads of the page, so the tests can run it in node.
 */
(() => {
"use strict";

// ------------------------------------------------------------------ state
const EVERY = 2000;   // ms between reads while the tab is on screen; the server caches its answer for 2 s too
let last = null, busy = false, readAt = 0;   // last: null before the first answer, {httpStatus}, {error}, or the reply

// ------------------------------------------------------------------ formatting: a missing number is a dash, never NaN
const Z = 1.96;                                                    // a 95% range is ±1.96 standard errors
const ok = (v) => typeof v === "number" && isFinite(v);
const qty = (v) => ok(v) ? count(Number.isInteger(v) ? v : +v.toFixed(2)) : "—";   // Kalshi fills fractions of a contract
const share = (v, dp = 1) => ok(v) ? pct(v, dp) : "—";
const px = (v) => ok(v) ? cents(v) : "—";
const usd = (v) => ok(v) ? signed(v) : "—";
const cash = (v) => ok(v) ? money(v) : "—";
const time = (t) => ok(t) ? when(t) : "—";
const secs = (v) => ok(v) ? v.toFixed(1) + " s" : "—";            // seconds, to a tenth: "2.4 s"
const over = (v) => ok(v) && v > 0 ? cents(v) : "";                // a step over the ask ("1¢"), or "" when there's none
const sign = (v) => Math.abs(v) < 0.05 ? "" : v > 0 ? "+" : "−";
const end = (v) => sign(v) + Math.abs(v).toFixed(1);               // one decimal, signed: "+28.6", "−4.0"
const ten = (v) => ok(v) ? end(v) + "¢" : "—";                     // ¢ per $10 staked: "+12.3¢"
const ci = (g) => ok(g.perTen) && ok(g.se) ? `(${end(g.perTen - Z * g.se)} to ${end(g.perTen + Z * g.se)})` : "";
const both = (a) => Array.isArray(a) && ok(a[0]) && ok(a[1]);       // a [min, max] prediction
const tone2 = (v) => ok(v) && Math.abs(v) >= 0.05 ? (v > 0 ? "up" : "down") : "";   // a figure shown to one decimal
const toneUsd = (v) => ok(v) ? tone(v) : "";                      // dollars, to the cent
const span = (s) => s < 5400 ? Math.max(1, Math.round(s / 60)) + " min" : s < 172800 ? (s / 3600).toFixed(1) + " h" : (s / 86400).toFixed(1) + " days";
const obj = (v) => v && typeof v === "object" && !Array.isArray(v) ? v : null;
const orders = (v) => `${qty(v)} order${v === 1 ? "" : "s"}`;
const perContract = (g) => ok(g.pnl) && ok(g.settled) && g.settled > 0 ? end(g.pnl / g.settled * 100) + "¢" : "—";

// building blocks; a panel is a fold (dashboard.html's fold(key, title, body, meta, cls))
const kpi =(k, v, s = "") => `<div class="lr-kpi"><span class="lr-k">${k}</span><span class="lr-v">${v}</span>${s ? `<span class="lr-s">${s}</span>` : ""}</div>`;
const sub = (s) => s ? `<span class="lr-sub">${s}</span>` : "";
const table = (head, rows, cls = "") => `<div class="lr-tw"><table class="lr-t${cls ? " " + cls : ""}"><thead><tr>`
  + head.map(([h, c]) => `<th scope="col"${c ? ` class="${c}"` : ""}>${h}</th>`).join("") + `</tr></thead><tbody>${rows.join("")}</tbody></table></div>`;
// A table cell; one that holds only a dash (no figure yet) also gets .lr-muted, so a blank recedes. Its text is unchanged.
const cell = (html, cls = "") => {
  const c = cls.split(/\s+/).filter(Boolean);
  if (String(html).replace(/<[^>]*>/g, "") === "—" && !c.includes("lr-muted")) c.push("lr-muted");
  return `<td${c.length ? ` class="${c.join(" ")}"` : ""}>${html}</td>`;
};
const row = (label, gloss, cells, cls = "") => `<tr${cls ? ` class="${cls}"` : ""}><th scope="row">${label}${sub(gloss)}</th>`
  + cells.map((c) => cell(c, "lr-num")).join("") + `</tr>`;
const notice = (html, cls = "") => `<div class="lr-alert${cls ? " " + cls : ""}" role="status">${html}</div>`;
const NOT_STARTED = "Not started yet: the bot sends +1¢ limits from its next restart.";
const NOT_RECORDING = "Not recording yet: the bot measures the paper +1¢ from its next restart.";
const NOT_RECORDING_FAST = "Not recording yet: the bot reads the order books at minute 8 exactly from its next restart.";

// The server's words for a verdict and an order's result, and how each reads here; anything else is shown as sent.
const STATES = new Map([["waiting", ["", "Not started"]], ["off", ["", "Off"]], ["too-early", ["warn", "Too early to tell"]],
                        ["helping", ["up", "▲ Paying"]], ["hurting", ["down", "▼ Losing money"]], ["no-difference", ["", "No clear difference"]]]);
const PAPER_STATES = new Map([["waiting", ["", "Not recording"]], ["too-early", ["warn", "Too early to tell"]], ["helping", ["up", "▲ Paying on paper"]],
                              ["hurting", ["down", "▼ Losing on paper"]], ["no-difference", ["", "No clear difference"]],
                              ["thin", ["warn", "Not enough to tell"]]]);
const FAST_STATES = new Map([["waiting", ["", "Not recording"]], ["too-early", ["warn", "Too early to tell"]], ["faster-fills-more", ["up", "▲ Fills more"]],
                             ["faster-fills-less", ["down", "▼ Fills less"]], ["no-difference", ["", "No clear difference"]]]);
const RESULTS = new Map([["won", ["up", "Won"]], ["lost", ["down", "Lost"]], ["open", ["lr-muted", "Open"]]]);
const SIDES = new Map([["yes", "yes"], ["no", "no"]]);
const chip = (V, words) => {
  const [cls, label] = words.get(V.state) || ["", V.state == null ? "—" : esc(V.state)];
  return `<span class="lr-chip${cls ? " " + cls : ""}">${label}</span>`;
};

// How far along a verdict is: n of its target orders, as a figure and a bar.
const progress = (n, target, what) => {
  const done = ok(n) && ok(target) && target > 0 ? Math.min(1, Math.max(0, n / target)) : 0;
  return kpi("Orders so far", `${qty(n)} of ${qty(target)}`, `<span class="lr-bar" aria-hidden="true"><i style="width:${(done * 100).toFixed(1)}%"></i></span>`
    + `the verdict waits for ${qty(target)} ${what}`);
};
// ... or a run that ends on a date (until): the day it ends, a bar of the time gone since it started (at now), and
// which day of the run it is.
const day = (t) => new Date(t * 1000).toLocaleDateString([], { month: "short", day: "numeric" });   // "Nov 26", local time
const runUntil = (started, until, now) => {
  const all = until - started, on = ok(started) && ok(now) && all > 0;
  const gone = on ? Math.min(1, Math.max(0, (now - started) / all)) : 0, days = Math.ceil(all / 86400);
  const at = on ? `day ${qty(Math.min(days, Math.max(1, Math.floor((now - started) / 86400) + 1)))} of ${qty(days)} · ` : "";
  return kpi("Runs until", day(until), `<span class="lr-bar" aria-hidden="true"><i style="width:${(gone * 100).toFixed(1)}%"></i></span>`
    + `${at}the verdict comes then`);
};

// An experiment's card: one fold whose header, in view while it's folded, holds its title, its verdict's chip and how
// far along it is ("412 of 1,000 orders"). Open: the verdict and its figures (top), then "How it's measured" (about:
// what the card measures, and its caveat) and the card's panels, each a fold of its own. dflt: open at first or not,
// where the card decides (the live +1¢ opens once it's on); else FOLDS says.
const ABOUT = "How it’s measured";
const cardHead = (label, n, target) => label + (ok(n) && ok(target) && target > 0 ? `<span class="lr-prog">${qty(n)} of ${qty(target)} orders</span>` : "");
const expCard = (exp, key, title, head, top, about, panels = "", dflt) => `<article class="lr-card" data-exp="${exp}">`
  + fold(key, title, `<div class="lr-top">${top}</div>${fold(key + ".about", ABOUT, `<div class="lr-pb">${about}</div>`)}${panels}`, head, "lr-exp", dflt)
  + `</article>`;
// A folded panel's header line: its key figures, those there are ("56.0% → 71.6% filled · +7.4¢ per $10").
const says = (...parts) => parts.filter(Boolean).join(" · ");
const filled = (a, b) => ok(a) ? `${share(a)}${ok(b) ? ` → ${share(b)}` : ""} filled` : "";
const perTenSays = (v, what = "") => ok(v) ? `${what}<span class="${tone2(v)}">${ten(v)}</span> per $10` : "";

// ------------------------------------------------------------------ the tab
// The tab's name, the ledger it reads, and the page's one Open all / Close all for the folds drawn on it (keys).
function head(r, keys = [], dflts = {}) {
  const stamp = r ? `${esc(r.mode ?? "")} ledger · read ${ok(r.now) ? hhmm(r.now) : "—"} · every 2 s` : "";
  const tools = (stamp ? `<span class="lr-stamp">${stamp}</span>` : "") + (keys.length ? foldsButton(keys, dflts) : "");
  return `<header class="lr-head"><div class="lr-title"><h2>Live Research</h2><p>Experiments the live bot is running, on paper or with`
    + ` real money, measured from its own ledger as its orders fill and settle.</p></div>${tools ? `<div class="lr-tools">${tools}</div>` : ""}</header>`;
}

// A card that throws is replaced by a note, so one experiment's surprise can't blank the others.
function drawCard(card, r) {
  try { return card(r); }
  catch (e) { return `<article class="lr-card">${notice(`<b>This experiment's card couldn't be drawn.</b> ${esc((e && e.message) || e)}`)}</article>`; }
}

window.liveResearchHtml = (reply) => {
  if (reply == null) return head() + `<p class="lr-wait">Loading the live experiments…</p>`;
  const r = obj(reply);
  if (!r) return head() + notice(`<b>An answer this tab can't read.</b> ${esc(JSON.stringify(reply))}`);
  if (r.httpStatus != null) {
    return head() + notice(`<b>Restart the dashboard</b> to see Live Research. Its server answered HTTP ${esc(r.httpStatus)} for this`
      + ` tab's data: a dashboard started before the tab was added doesn't know the route yet, and a restart also clears a server error.`, "warn");
  }
  if (r.error != null) return head() + notice(`<b>No live research to show.</b> ${esc(r.error)}`);
  // the folds drawn, read back from the markup (server words are escaped, so only the page's own attributes match), for
  // the page's Open all / Close all; the live +1¢ card opens by default once it's on, as limitCard draws it
  const body = CARDS.map((card) => drawCard(card, r)).join("") + terms();
  const keys = [...body.matchAll(/ data-fold-key="([a-z0-9.-]+)"/g)].map((m) => m[1]);
  return head(r, keys, { "lr.limit": (obj(r.verdict) || {}).state !== "off" }) + body;
};

// ------------------------------------------------------------------ the +1¢ limit, on paper
// reply.shadow: null (or missing) while the ledger has no shadow table, i.e. until the bot's next restart.
function shadowCard(r) {
  const S = obj(r.shadow);
  if (!S) return paperCard(r, null);
  const G = obj(S.group) || {}, P = obj(r.predictions) || {};
  const extra = `<b>${ten(G.perTen)}</b>${sub(ci(G))}`, pnl = `${usd(G.pnl)}${sub(`${qty(G.contracts)} contracts, ${orders(G.orders)}`)}`;
  return paperCard(r, S, paperExtra(S, G)
    + predictions(P, "lr.shadow.pred", "Predictions vs paper", `On paper${sub("so far")}`,
                  [`${share(S.fillShare)}${sub("real orders")}`, `<b>${share(S.fillShareWith)}</b>`, "—", "—", extra, perContract(G), share(G.winRate), pnl],
                  " The On paper column is this card's, from the book read right after each real order; it follows only the extra"
                  + " contracts to settlement, so it has no figure for the rows about every contract.")
    + paperRows(S.rows));
}

// The card: its name, the server's verdict in its own words, how far along it is, and (in How it's measured) what it
// counts and what a paper measurement can't show; then its panels.
function paperCard(r, S, panels = "") {
  const V = obj(S && S.verdict) || {}, up = over(S && S.limitUp) || over(r.shadowUp);
  const lede = `<p class="lr-lede">Real orders go at the ask the bot saw. Right after each one, the bot reads the order book again and
        counts what a limit ${up || "a cent"} higher would have bought on top of what really filled: the <b>extra contracts</b>. They're
        followed to the market's close and settled on paper, with no money on them.</p>`;
  const card = (header, top, caveat = "") => expCard("shadow", "lr.shadow", "The +1¢ limit, on paper", header, top, lede + caveat, panels);
  if (!S) return card(`<span class="lr-chip">Not recording</span>`, `<p class="lr-verdict">${NOT_RECORDING}</p>`);
  // its run: to a date (until, from Oct 15), or to a number of orders (target) as an older server sends it
  const on = ok(S.started), n = ok(V.orders) ? V.orders : S.orders, until = ok(S.until) ? S.until : null;
  const target = ok(V.target) ? V.target : S.target;
  const ran = on && ok(r.now) ? `running ${span(Math.max(0, r.now - S.started))}` : "";
  const unread = ok(S.unread) && S.unread > 0 ? ` · ${qty(S.unread)} book read${S.unread === 1 ? "" : "s"} failed and ${S.unread === 1 ? "is" : "are"} left out` : "";
  const label = chip(V, PAPER_STATES);
  const prog = until === null ? cardHead(label, n, target) : label + `<span class="lr-prog">${ok(n) ? orders(n) + " · " : ""}until ${day(until)}</span>`;
  return card(prog, `<p class="lr-verdict">${V.text == null ? "—" : esc(V.text)}</p>
      <div class="lr-kpis">
        ${kpi("Started", on ? time(S.started) : "Not yet", on ? `the first paper measurement${ran ? " · " + ran : ""}` : "from the bot's next restart")}
        ${until === null ? progress(n, target, "orders measured on paper") : runUntil(S.started, until, r.now)}
        ${kpi("Book read", secs(S.lag), `after minute 8, the median${unread}`)}
        ${kpi("Paper limit", up ? `ask + ${up}` : "—", "over the ask it saw, at most 99.9¢")}
      </div>`,
    `<p class="lr-note lr-caveat"><b>What paper can't show.</b> The book is read a moment after the real order, so some offers may have
        gone, or new ones arrived, in between. And it can't show whether other traders would have beaten the bot to those offers: a
        real order ${up || "a cent"} higher might get fewer of them.</p>`);
}

// The real fill against the fill with the extra cent, and how the extra contracts are doing.
function paperExtra(S, G) {
  const title = "What the extra cent would have bought";
  if (!(ok(S.orders) && S.orders > 0)) {
    return fold("lr.shadow.extra", title, `<div class="lr-pb"><p class="lr-wait">Nothing measured on paper yet. Each real order is measured right after it`
      + ` goes in, at minute 8 of each 15-minute window.</p></div>`);
  }
  const all = ok(S.filled) && ok(S.extra) ? S.filled + S.extra : null;
  const won = ok(G.winRate) ? `<span class="${ok(G.breakEven) ? (G.winRate >= G.breakEven ? "up" : "down") : ""}">${share(G.winRate)}</span>`
    + sub(`needs ${share(G.breakEven)}${ok(G.settled) && G.settled > 0 ? ` · ${qty(G.won)} of ${qty(G.settled)} settled` : ""}`) : "—";
  const rows = [
    row("Fill share, real", "filled ÷ asked for, with the limit at the ask it saw", [`<b>${share(S.fillShare)}</b>${sub(`${qty(S.filled)} of ${qty(S.asked)} contracts`)}`]),
    row("Fill share with the extra cent", "the real fills plus the extra contracts", [`<b>${share(S.fillShareWith)}</b>${sub(`${qty(all)} of ${qty(S.asked)} contracts`)}`], "lr-key"),
    row("Extra contracts", "only the extra cent would have bought these", [`${qty(S.extra)}${sub(`in ${orders(S.ordersWithExtra)}`)}`]),
    row("Unfilled ones caught", "share of the contracts the real orders asked for but didn't get", [`${share(S.extraShare)}${sub(`${qty(S.extra)} of ${qty(S.remaining)}`)}`]),
    row("Their avg price", "per extra contract", [`${px(G.avgPrice)}${sub(ok(G.fee) ? `fees ${cash(G.fee)}` : "")}`]),
    row("Won", "against break-even: price plus fee", [won]),
    row("P&amp;L", "settled extra contracts", [`<span class="${toneUsd(G.pnl)}">${usd(G.pnl)}</span>${sub(ok(G.staked) && G.staked > 0 ? `on ${cash(G.staked)} staked` : "")}`]),
    row("¢ per $10", "with its 95% range", [`<b class="${tone2(G.perTen)}">${ten(G.perTen)}</b>${sub(ci(G) || (ok(G.perTen) ? "no range yet: needs settled bets in 2+ windows" : ""))}`
      + sub(ok(G.windows) && G.windows > 0 ? `${qty(G.windows)} window${G.windows === 1 ? "" : "s"}` : "")], "lr-key"),
  ];
  return fold("lr.shadow.extra", title, `<div class="lr-pb">
      <p class="lr-lede">The extra contracts are the test: they only pay if they win more often than their price plus fee. The verdict
        rides on their ¢ per $10: when its 95% range sits above zero, the cent is paying.</p>
      ${table([["", ""], [`So far${sub("on paper")}`, "lr-num"]], rows)}
      ${rangePlot([["Extra", G]])}
    </div>`, says(filled(S.fillShare, S.fillShareWith), perTenSays(G.perTen, "extra ")));
}

// The paper measurements, newest first: what each real order saw, asked for and got, and what the extra cent would have added.
function paperRows(list) {
  const O = Array.isArray(list) ? list.filter(obj) : [];
  const rows = O.map((o) => {
    const ticker = String(o.ticker ?? ""), side = SIDES.get(o.side) || "", extra = ok(o.extra) ? o.extra : null;
    const [rc, rw] = RESULTS.get(o.result) || (o.result == null ? ["lr-muted", "—"] : ["", esc(o.result)]);
    const got = ok(o.filled) && ok(o.asked) && o.asked > 0 ? share(o.filled / o.asked, 0) + " filled" : "";
    return `<tr>${cell(time(o.ts), "lr-when")}<td><b>${esc(sym(ticker.split("-")[0]))}</b><span class="lr-sub lr-tk">${esc(ticker)}</span></td>`
      + cell(o.side == null ? "—" : `<span class="lr-side ${side}">${esc(o.side)}</span>`)
      + cell(px(o.seen), "lr-num") + cell(px(o.limit), "lr-num") + cell(qty(o.asked), "lr-num")
      + cell(`${qty(o.filled)}${sub(got)}`, "lr-num") + cell(extra > 0 ? `<b>${qty(extra)}</b>` : qty(extra), "lr-num")
      + cell(extra > 0 ? px(o.avgPrice) : "—", "lr-num") + cell(secs(o.lag), "lr-num")
      + cell(rw, `lr-num ${extra === 0 ? "lr-muted" : rc}`) + `</tr>`;   // with nothing extra, its result moves nothing on paper
  });
  const body = rows.length
    ? table([["Measured"], ["Market"], ["Side"], ["Ask it saw", "lr-num"], ["Paper limit", "lr-num"], ["Asked", "lr-num"],
             [`Filled${sub("real")}`, "lr-num"], [`Extra${sub("on paper")}`, "lr-num"], [`Their avg price${sub("extra contracts")}`, "lr-num"],
             [`Book read${sub("after minute 8")}`, "lr-num"], ["Result", "lr-num"]], rows, "lr-orders")
    : `<p class="lr-wait">No paper measurements yet. One is made right after each real order, at minute 8 of each 15-minute window.</p>`;
  return fold("lr.shadow.latest", `Latest paper measurements<span class="lr-n">${rows.length}</span>`, `<div class="lr-flush">${body}</div>`,
              rows.length ? "newest first" : "");
}

// ------------------------------------------------------------------ fast entry, on paper
// reply.fastShadow: null (or missing) while the ledger has no shadow table; its pairs start with the bot's next restart.
function fastShadowCard(r) {
  const S = obj(r.fastShadow);
  return fastCard(r, S, S ? fastVersus(S) + fastRows(S.rows) : "");
}

// The card: its name, the server's verdict in its own words, how far along it is, how soon after minute 8 the books
// answered, and (in How it's measured) what it pairs and why the real gain would be smaller than this; then its panels.
function fastCard(r, S, panels = "") {
  const V = obj(S && S.verdict) || {};
  const lede = `<p class="lr-lede">Real orders keep their timing: they land about 2.4 s after minute 8 starts, by when other traders have
        taken some of the offers. In the background the bot reads every order book at minute 8 exactly (480.0 s into the window, on
        Kalshi's clock) and counts what an order sent at that instant, with the same limit rule, would have bought. Each real order is
        <b>paired</b> with that order on paper: no order is placed and no money rides on it.</p>`;
  const card = (label, n, target, top, caveat = "") => expCard("fastshadow", "lr.fast", "Fast entry, on paper", cardHead(label, n, target),
    top, lede + caveat, panels);
  if (!S) return card(`<span class="lr-chip">Not recording</span>`, null, null, `<p class="lr-verdict">${NOT_RECORDING_FAST}</p>`);
  const on = ok(S.started), n = ok(V.orders) ? V.orders : S.orders, target = ok(V.target) ? V.target : S.target;
  const ran = on && ok(r.now) ? `running ${span(Math.max(0, r.now - S.started))}` : "";
  const L = obj(S.lag) || {}, gone = ok(S.unread) && S.unread > 0 ? S.unread : 0;
  const p90 = ok(L.p90) ? ` · 90% within ${secs(L.p90)}` : "";
  const unread = gone ? ` · ${qty(gone)} book${gone === 1 ? "" : "s"} couldn't be read and ${gone === 1 ? "is" : "are"} left out` : "";
  return card(chip(V, FAST_STATES), n, target, `<p class="lr-verdict">${V.text == null ? "—" : esc(V.text)}</p>
      <div class="lr-kpis">
        ${kpi("Started", on ? time(S.started) : "Not yet", on ? `the first pair${ran ? " · " + ran : ""}` : "from the bot's next restart")}
        ${progress(n, target, "orders paired on paper")}
        ${kpi("Book read", secs(L.median), `after minute 8, the median${p90}${unread}`)}
      </div>`,
    `<p class="lr-note lr-caveat"><b>This is the best case.</b> Other traders' orders start landing 10–30 ms after minute 8, and an
        order from this PC would land about 0.1–0.2 s after it, by when some of these offers may be gone. So the real gain would be
        smaller.</p>`);
}

// Real orders against their twins at minute 8: how much each filled, the difference with its 95% range, the share of the
// real misses the book at minute 8 still had, the asks each saw, the prices each paid, and how each did once settled.
function fastVersus(S) {
  const title = "Real orders against orders at minute 8";
  if (!(ok(S.orders) && S.orders > 0)) {
    return fold("lr.fast.vs", title, `<div class="lr-pb"><p class="lr-wait">Nothing paired yet. Each real order is paired as it goes in, at minute 8`
      + ` of each 15-minute window.</p></div>`);
  }
  const P = obj(S.pnl) || {}, R = obj(P.real) || {}, F = obj(P.paper) || {};
  const of = (n) => sub(`${qty(n)} of ${qty(S.asked)} contracts`);
  const d = ok(S.diff) ? S.diff * 100 : null, se = ok(S.diffSe) ? S.diffSe * 100 : null;   // in percentage points
  const diff = d == null ? "—" : `<b class="${tone2(d)}">${end(d)} pts</b>`
    + sub(se == null ? "no range yet: needs pairs in 2+ windows" : `(${end(d - Z * se)} to ${end(d + Z * se)})`);
  const pnl = (g) => `<span class="${toneUsd(g.pnl)}">${usd(g.pnl)}</span>${sub(ok(g.staked) && g.staked > 0 ? `on ${cash(g.staked)} staked` : "")}`;
  const perTen = (g) => `<b class="${tone2(g.perTen)}">${ten(g.perTen)}</b>${sub(ci(g) || (ok(g.perTen) ? "no range yet: needs settled bets in 2+ windows" : ""))}`;
  const settled = ok(P.settled) ? `${qty(P.settled)} settled pair${P.settled === 1 ? "" : "s"}` : "settled markets";
  const rows = [
    row("Fill share", "filled ÷ asked for", [`<b>${share(S.realShare)}</b>${of(S.filled)}`, `<b>${share(S.fastShare)}</b>${of(S.extra)}`]),
    row("The difference", "at minute 8 minus real, in percentage points (pts), with its 95% range", ["", diff], "lr-key"),
    row("Misses caught", "of the contracts real orders asked for but didn't get, the share an order at minute 8 would have got", ["—", share(S.caught)]),
    row("Ask it saw", "on average", [px(S.realSeen), px(S.fastSeen)]),
    row("Price paid", "on average, per contract", [px(S.realAvg), px(S.fastAvg)]),
    row("P&amp;L", settled, [pnl(R), pnl(F)]),
    row("¢ per $10", "with its 95% range", [perTen(R), perTen(F)]),
  ];
  return fold("lr.fast.vs", title, `<div class="lr-pb">
      <p class="lr-lede">Each real order beside its twin at minute 8: the same market, side and contracts asked for, its limit set by the
        same rule from the ask at that instant. The verdict rides on <b>the difference</b> in fill share: when its 95% range sits above
        zero, orders sent at minute 8 exactly would fill more.</p>
      ${table([["", ""], [`Real${sub("~2.4 s after minute 8")}`, "lr-num"], [`At minute 8${sub("on paper")}`, "lr-num"]], rows)}
    </div>`, says(filled(S.realShare, S.fastShare), d == null ? "" : `<span class="${tone2(d)}">${end(d)} pts</span>`));
}

// The pairs, newest first: what each real order saw and got, beside what an order sent at minute 8 would have.
function fastRows(list) {
  const O = Array.isArray(list) ? list.filter(obj) : [];
  const rows = O.map((o) => {
    const ticker = String(o.ticker ?? ""), side = SIDES.get(o.side) || "", extra = ok(o.extra) ? o.extra : null;
    const [rc, rw] = RESULTS.get(o.result) || (o.result == null ? ["lr-muted", "—"] : ["", esc(o.result)]);
    const got = (n) => ok(n) && ok(o.asked) && o.asked > 0 ? share(n / o.asked, 0) + " filled" : "";
    // nothing at minute 8: the book had no offers on that side, or its ask was outside the prices the bot buys at
    const none = extra === 0 && o.seen == null ? "no offers" : "", skip = extra === 0 && ok(o.seen) && o.limit == null ? "no buy at that ask" : "";
    return `<tr>${cell(time(o.ts), "lr-when")}<td><b>${esc(sym(ticker.split("-")[0]))}</b><span class="lr-sub lr-tk">${esc(ticker)}</span></td>`
      + cell(o.side == null ? "—" : `<span class="lr-side ${side}">${esc(o.side)}</span>`)
      + cell(px(o.seenReal), "lr-num") + cell(`${px(o.seen)}${sub(none)}`, "lr-num") + cell(`${px(o.limit)}${sub(skip)}`, "lr-num")
      + cell(qty(o.asked), "lr-num") + cell(`${qty(o.filled)}${sub(got(o.filled))}`, "lr-num")
      + cell(`${extra > 0 ? `<b>${qty(extra)}</b>` : qty(extra)}${sub(got(extra))}`, "lr-num")
      + cell(extra > 0 ? px(o.avgPrice) : "—", "lr-num") + cell(secs(o.lag), "lr-num")
      + cell(`${rw}${sub(extra > 0 && ok(o.pnl) ? `${usd(o.pnl)} on paper` : "")}`, `lr-num ${rc}`) + `</tr>`;
  });
  const body = rows.length
    ? table([["Measured"], ["Market"], ["Side"], [`Ask it saw${sub("real order")}`, "lr-num"], [`Ask at minute 8${sub("on paper")}`, "lr-num"],
             [`Limit${sub("at minute 8")}`, "lr-num"], ["Asked", "lr-num"], [`Filled${sub("real")}`, "lr-num"], [`Filled${sub("at minute 8")}`, "lr-num"],
             [`Its avg price${sub("at minute 8")}`, "lr-num"], [`Book read${sub("after minute 8")}`, "lr-num"], ["Result", "lr-num"]], rows, "lr-orders")
    : `<p class="lr-wait">No pairs yet. One is made as each real order goes in, at minute 8 of each 15-minute window.</p>`;
  return fold("lr.fast.latest", `Latest pairs<span class="lr-n">${rows.length}</span>`, `<div class="lr-flush">${body}</div>`, rows.length ? "newest first" : "");
}

// ------------------------------------------------------------------ the +1¢ limit experiment, with real money
function limitCard(r) {
  const A = obj(r.arms) || {}, B = obj(A.before) || {}, D = obj(A.during) || {}, S = obj(r.split) || {}, V = obj(r.verdict) || {};
  const on = ok(r.started);
  // off: the live limit is at the ask (LIMIT_UP 0), so every order is in the before arm and the other panels would be empty;
  // the card starts folded (FOLDS), its chip saying "Off"
  if (V.state === "off") return offStatus(r, V, fillRates(B, D, on, true));
  const X = obj(S.extra) || {}, live = (v) => on ? v : "—";
  return status(r, V, D, on, fillRates(B, D, on) + extraCent(S, on, r.fillsRecorded)
    + predictions(obj(r.predictions) || {}, "lr.limit.pred", "Predictions vs live", `Live${sub(on ? "this experiment, so far" : "not started")}`,
                  [share(B.fillShare), live(`<b>${share(D.fillShare)}</b>`), ten(B.perTen), live(ten(D.perTen)), live(`<b>${ten(X.perTen)}</b>${sub(ci(X))}`),
                   live(perContract(X)), live(share(X.winRate)), live(`${usd(X.pnl)}${sub(`${qty(X.contracts)} contracts, ${orders(X.orders)}`)}`)])
    + latest(r.orders, on));
}

const fillsKpi = (r) => kpi("Each fill recorded", r.fillsRecorded ? "Yes" : "Not yet", r.fillsRecorded ? "so each contract splits into base and extra"
  : "from the bot's next restart; until then its contracts can't be split");

// The card, while it runs: its name, the server's verdict in its own words, how far along it is, (in How it's measured)
// what the cent is for, then its panels. It opens by default while it's on.
function status(r, V, D, on, panels) {
  const n = ok(V.orders) ? V.orders : D.orders, target = ok(V.target) ? V.target : r.target;
  const ran = on && ok(r.started) && ok(r.now) ? `running ${span(Math.max(0, r.now - r.started))}` : "";
  const up = over(r.limitUp), atAsk = r.limitUp === 0;   // atAsk: the live limit is at the ask (LIMIT_UP 0), so no "+0¢" anywhere
  const why = `to catch contracts whose price ticked up in the ~2.4 s its order takes to land`;
  const lede = atAsk && on
    ? `While this ran, the bot's immediate-or-cancel buy set its limit a cent over the ask it saw, ${why}. The live limit is back at
        the ask now, so no new orders join it.`
    : atAsk
      ? `The bot's immediate-or-cancel buy would set its limit a cent over the ask it saw, ${why}. The live limit is at the ask for now.`
      : `The bot's immediate-or-cancel buy now sets its limit ${up || "a cent"} over the ask it saw (at most 99.9¢), ${why}. Does the extra
        cent buy contracts that make money?`;
  return expCard("limitup", "lr.limit", "The +1¢ limit experiment", cardHead(chip(V, STATES), n, target),
    `<p class="lr-verdict">${V.text == null ? "—" : esc(V.text)}</p>
      <div class="lr-kpis">
        ${kpi("Started", on ? time(r.started) : "Not yet", on ? `the first order with the +1¢ limit${ran ? " · " + ran : ""}` : "from the bot's next restart")}
        ${progress(n, target, "orders with the +1¢ limit")}
        ${kpi("Limit", up ? `ask + ${up}` : atAsk ? "At the ask" : "—", atAsk ? "the live +1¢ is off now" : "over the ask it saw, at most 99.9¢")}
        ${fillsKpi(r)}
      </div>`, `<p class="lr-lede">${lede}</p>`, panels, true);
}

// Off: real orders go at the ask the bot saw, and the paper card measures the cent instead. Nothing here reads "+0¢".
function offStatus(r, V, panels) {
  const paper = over(r.shadowUp);
  return expCard("limitup", "lr.limit", "The +1¢ limit experiment", chip(V, STATES),
    `<p class="lr-verdict">${V.text == null ? "—" : esc(V.text)}</p>
      <div class="lr-kpis">
        ${kpi("Live limit", "At the ask", "a real order never pays more than the ask it saw")}
        ${kpi("On paper", paper ? `ask + ${paper}` : "—", "measured in the card above, with no money on it")}
        ${fillsKpi(r)}
      </div>`,
    `<p class="lr-lede">This is the cent with real money: the bot's immediate-or-cancel buy would set its limit ${paper || "a cent"} over the
        ask it saw, to catch contracts whose price ticked up in the ~2.4 s its order takes to land. It goes live when bot.py's
        <code>LIMIT_UP</code> (how far over the ask the live limit sits) is set above zero and the bot restarts.</p>`, panels);
}

// Before the experiment against with it: how much of each order filled. Off, there is only before.
function fillRates(B, D, on, off = false) {
  const rows = [
    ["Orders", "accepted buy orders", (a) => qty(a.orders)],
    ["Contracts asked for", "", (a) => qty(a.asked)],
    ["Contracts filled", "", (a) => qty(a.filled)],
    ["Fill share", "filled ÷ asked for", (a) => `<b>${share(a.fillShare)}</b>`],
    ["Got none", "orders, and their share", (a) => byOrder(a, "none")],
    ["Part-filled", "", (a) => byOrder(a, "partial")],
    ["Filled in full", "", (a) => byOrder(a, "full")],
    ["Ask it saw", "on average", (a) => px(a.avgSeen)],
    ["Price paid", "on average, per contract", (a) => px(a.avgPaid)],
    ["Settled contracts won", "", (a) => ok(a.settled) && a.settled > 0 ? `${qty(a.won)} of ${qty(a.settled)}${sub(share(a.won / a.settled))}` : "—"],
    ["P&amp;L", "settled bets", (a) => `<span class="${toneUsd(a.pnl)}">${usd(a.pnl)}</span>`],
    ["¢ per $10", "with its 95% range", (a) => `<span class="${tone2(a.perTen)}">${ten(a.perTen)}</span>${sub(ci(a))}`],
  ].map(([label, gloss, f]) => row(label, gloss, off ? [f(B)] : [f(B), on ? f(D) : "—"]));
  if (off) {
    return fold("lr.limit.fills", "Fill rates", `<div class="lr-pb">
      <p class="lr-lede">Every real order so far went in with its limit at the ask it saw: this is the fill share the extra cent is meant to
        raise. Once the live +1¢ is on, its orders get a column of their own beside these.</p>
      ${table([["", ""], [`Every order so far${sub("limit = the ask it saw")}`, "lr-num"]], rows)}
    </div>`, filled(B.fillShare));
  }
  return fold("lr.limit.fills", "Fill rates", `<div class="lr-pb">
      <p class="lr-lede">Before is every order until the first +1¢ limit, when the limit was the ask it saw. The two run on different days,
        so their P&amp;L differs for reasons besides the limit; the extra contracts' own results are the cleaner test.</p>
      ${table([["", ""], [`Before${sub("limit = the ask it saw")}`, "lr-num"], [`With +1¢${sub(on ? "limit 1¢ over it" : "not started")}`, "lr-num"]], rows)}
    </div>`, filled(B.fillShare, on ? D.fillShare : null));
}

const byOrder = (a, k) => ok(a[k]) ? `${qty(a[k])}${sub(ok(a.orders) && a.orders > 0 ? share(a[k] / a.orders, 0) : "")}` : "—";

// The fills with the +1¢ limit, split by price: base (at or under the ask it saw), extra (over it), unknown (not recorded).
function extraCent(S, on, recorded) {
  if (!on) return fold("lr.limit.extra", "What the extra cent bought", `<div class="lr-pb"><p class="lr-lede">${NOT_STARTED} From then each contract`
    + ` bought above the ask it saw counts here as an extra one, and its results show whether the cent pays.</p></div>`);
  const base = obj(S.base) || {}, extra = obj(S.extra) || {}, unknown = obj(S.unknown) || {};
  const group = (name, gloss, g, cls) => row(name, gloss, [
    `${qty(g.contracts)}${sub(orders(g.orders))}`,
    px(g.avgPrice),
    ok(g.winRate) ? `<span class="${ok(g.breakEven) ? (g.winRate >= g.breakEven ? "up" : "down") : ""}">${share(g.winRate)}</span>${sub(`needs ${share(g.breakEven)}`)}` : "—",
    `<span class="${toneUsd(g.pnl)}">${usd(g.pnl)}</span>${sub(ok(g.settled) ? `${qty(g.settled)} settled` : "")}`,
    `<b class="${tone2(g.perTen)}">${ten(g.perTen)}</b>${sub(ci(g) || (ok(g.perTen) ? "no range yet: needs settled bets in 2+ windows" : ""))}`
      + sub(ok(g.windows) && g.windows > 0 ? `${qty(g.windows)} window${g.windows === 1 ? "" : "s"}` : ""),
  ], cls);
  const rows = [
    group("Base", "at or under the ask it saw: it would have got these anyway", base),
    group("Extra", "over the ask it saw, up to the limit: only the extra cent bought these", extra, "lr-key"),
    row("Unknown", "filled before each fill was recorded, so they can't be split", [`${qty(unknown.contracts)}${sub(orders(unknown.orders))}`, "—", "—", "—", "—"]),
  ];
  return fold("lr.limit.extra", "What the extra cent bought", `<div class="lr-pb">
      <p class="lr-lede">Every contract bought with the +1¢ limit, split by its price. The verdict rides on the <b>extra</b> contracts'
        ¢ per $10: when its 95% range sits above zero, the cent is paying.</p>
      ${recorded ? "" : `<p class="lr-note">The ledger doesn't record each fill yet (it will from the bot's next restart), so every contract so far is unknown.</p>`}
      ${table([["", ""], ["Contracts", "lr-num"], ["Avg price", "lr-num"], [`Won${sub("vs break-even")}`, "lr-num"], ["P&amp;L", "lr-num"],
               [`¢ per $10${sub("95% range")}`, "lr-num"]], rows)}
      ${rangePlot([["Base", base], ["Extra", extra]])}
    </div>`, perTenSays(extra.perTen, "extra "));
}

// ¢ per $10 as a dot, its 95% range as a bar, against zero: a range clear of zero is a result, one across it may be luck.
function rangePlot(groups) {
  const have = groups.filter(([, g]) => ok(g.perTen));
  if (!have.length) return "";
  const ends = (g) => ok(g.se) ? [g.perTen - Z * g.se, g.perTen + Z * g.se] : [g.perTen, g.perTen];
  const lim = Math.max(5, Math.ceil(Math.max(...have.flatMap(([, g]) => ends(g).map(Math.abs))) / 5) * 5);
  const x = (v) => (50 + (v / lim) * 50).toFixed(2) + "%";
  const rows = have.map(([name, g]) => {
    const [lo, hi] = ends(g), cls = !ok(g.se) ? "" : lo > 0 ? "up" : hi < 0 ? "down" : "";
    const says = `${name}: ${ten(g.perTen)} per $10${ok(g.se) ? `, 95% range ${end(lo)} to ${end(hi)}` : ", no range yet"}`;
    return `<div class="lr-prow" title="${says}"><span class="lr-plab">${name}</span><span class="lr-track"><i class="lr-zero"></i>`
      + (ok(g.se) ? `<i class="lr-whisk ${cls}" style="left:${x(lo)};width:${((hi - lo) / lim * 50).toFixed(2)}%"></i>` : "")
      + `<i class="lr-dot ${cls}" style="left:${x(g.perTen)}"></i></span><span class="lr-pval">${ten(g.perTen)}</span></div>`;
  });
  return `<figure class="lr-plot" aria-label="¢ per $10 with its 95% range, against zero">${rows.join("")}`
    + `<div class="lr-prow lr-axis" aria-hidden="true"><span></span><span class="lr-ticks"><span>−${lim}¢</span><span>0</span><span>+${lim}¢</span></span><span></span></div>`
    + `<figcaption class="lr-note">Dot: ¢ per $10. Bar: its 95% range. Green when the whole range is above zero, red when below.</figcaption></figure>`;
}

// What the research predicted, beside what a card measured: `mine` heads the card's own column and `cells` fills it, one
// per line below, so each prediction shares a row with its measurement. A prediction file that's missing is left out,
// and said so. Both cards use it, the paper +1¢ and the live one; `more` ends the lede with the card's own sentence.
function predictions(P, key, title, mine, cells, more = "") {
  const H = obj(P.history), L = obj(P.live), rng = (a, f) => both(a) ? `${f(a[0])} to ${f(a[1])}` : "—";
  const lines = [   // [measure, gloss, history, live-fills replay]; the card's own cell comes from `cells`
    ["Contracts filled, before", "share of those asked for", H && share(H.fillBefore), L && share(L.fillBefore)],
    ["Contracts filled, with +1¢", "", H && rng(H.fillDuring, share), L && "—"],
    ["¢ per $10, before", "every contract", H && ten(H.perTenBefore), L && "—"],
    ["¢ per $10, with +1¢", "every contract", H && rng(H.perTenDuring, end) + (both(H.perTenDuring) ? "¢" : ""), L && "—"],
    ["Extra contracts: ¢ per $10", "", H && rng(H.extraPerTen, end) + (both(H.extraPerTen) ? "¢" : ""), L && "—"],
    ["Extra contracts: per contract", "P&amp;L ÷ contracts", H && "—", L && (ok(L.perContractCents) ? end(L.perContractCents) + "¢" : "—")],
    ["Extra contracts won", "share of contracts", H && "—", L && share(L.winRate)],
    ["Extra contracts: P&amp;L", "with its 95% range", H && "—",
     L && `${usd(L.pnl)}${sub(ok(L.pnl) && ok(L.pnlSe) ? `${usd(L.pnl - Z * L.pnlSe)} to ${usd(L.pnl + Z * L.pnlSe)}` : "")}`
       + sub(`${qty(L.contracts)} contracts, ${orders(L.orders)}`)],
  ];
  const cols = [[`History${sub(H ? `${ok(H.size) ? `$${H.size}` : "$30"} orders on the trade tape` : "")}`, H],
                [`Live-fills replay${sub("the bot's own orders, 1¢ higher")}`, L],
                [mine, true]];
  const keep = cols.map(([, c], i) => [c, i]).filter(([c]) => c).map(([, i]) => i);
  const rows = lines.map(([m, gloss, h, l], i) => row(m, gloss, keep.map((k) => [h, l, cells[i]][k] || "—")));
  const gone = [!H && "the history prediction (research/kalshi_15min/lab/fills.json)", !L && "the live-fills replay (research/kalshi_15min/lab/live_fills/live_fills.json)"].filter(Boolean);
  const src = [H && H.source != null && `History: <code>${esc(H.source)}</code>`, L && L.source != null && `Replay: <code>${esc(L.source)}</code>`].filter(Boolean);
  return fold(key, title, `<div class="lr-pb">
      <p class="lr-lede">History replays every live-rule bet since Dec 10 on Kalshi's trade tape; its ranges run from the strictest
        reading of the tape to the loosest. The live-fills replay asks what a 1¢ higher limit would have bought for the bot's own
        orders, counting trades in the 30 s after each.${more}</p>
      ${table([["", ""], ...keep.map((i) => [cols[i][0], "lr-num"])], rows)}
      ${gone.length ? `<p class="lr-note"><b>Unavailable:</b> ${gone.join("; ")}. The file is missing or unreadable.</p>` : ""}
      ${src.length ? `<p class="lr-note">${src.join(" · ")}</p>` : ""}
    </div>`);
}

// The orders sent with the +1¢ limit, newest first: what each saw, its limit, what it asked for and got, and how it did.
function latest(list, on) {
  const O = Array.isArray(list) ? list.filter(obj) : [];
  const rows = O.map((o) => {
    const ticker = String(o.ticker ?? ""), side = SIDES.get(o.side) || "";
    const [rc, rw] = RESULTS.get(o.result) || (o.result == null ? ["lr-muted", "—"] : ["", esc(o.result)]);
    const got = ok(o.filled) && ok(o.asked) && o.asked > 0 ? share(o.filled / o.asked, 0) + " filled" : "";
    const split = ok(o.base) && ok(o.extra) ? `${qty(o.base)} · ${qty(o.extra)}` : ok(o.filled) && o.filled > 0 ? "unknown" : "—";
    return `<tr>${cell(time(o.ts), "lr-when")}<td><b>${esc(sym(ticker.split("-")[0]))}</b><span class="lr-sub lr-tk">${esc(ticker)}</span></td>`
      + cell(o.side == null ? "—" : `<span class="lr-side ${side}">${esc(o.side)}</span>`)
      + cell(px(o.seen), "lr-num") + cell(px(o.limit), "lr-num") + cell(qty(o.asked), "lr-num")
      + cell(`${qty(o.filled)}${sub(got)}`, `lr-num ${!ok(o.filled) || o.filled === 0 ? "down" : ok(o.asked) && o.filled >= o.asked ? "up" : "part"}`)
      + cell(split, "lr-num") + cell(px(o.avgPaid), "lr-num") + cell(rw, `lr-num ${rc}`) + `</tr>`;
  });
  const body = rows.length
    ? table([["Placed"], ["Market"], ["Side"], ["Ask it saw", "lr-num"], ["Limit", "lr-num"], ["Asked", "lr-num"], ["Filled", "lr-num"],
             [`Base · extra${sub("contracts")}`, "lr-num"], ["Avg paid", "lr-num"], ["Result", "lr-num"]], rows, "lr-orders")
    : `<p class="lr-wait">${on ? "No orders with the +1¢ limit yet. They go in at minute 8 of each 15-minute window." : NOT_STARTED}</p>`;
  return fold("lr.limit.latest", `Latest experiment orders<span class="lr-n">${rows.length}</span>`, `<div class="lr-flush">${body}</div>`,
              rows.length ? "newest first" : "");
}

// ------------------------------------------------------------------ the experiments, one card each: the paper ones first
const CARDS = [shadowCard, fastShadowCard, limitCard];

// ------------------------------------------------------------------ terms, in plain words
const TERMS = [
  ["Immediate-or-cancel order", "An order that takes whatever the book offers at once, up to its limit, and cancels the rest: nothing waits on the book. It fills in full, in part, or not at all."],
  ["Limit", "The most the order will pay for a contract. Live, it's the ask the bot saw. The +1¢ experiment puts it 1¢ over that (at most 99.9¢): on paper for now, and with real money once bot.py's LIMIT_UP is set above zero."],
  ["The ask it saw", "The cheapest offer on the book when the bot read it at minute 8. The order lands about 2.4 s later, and by then the price has often ticked up."],
  ["On paper", "Measured without an order or any money. Right after each real order the bot reads the book again, counts what a limit 1¢ higher would have bought on top of the real fill, and settles those contracts when the market closes. The book can change in the moment between the order and the read, so it's an estimate."],
  ["Fast entry", "Sending the minute-8 orders at minute 8 exactly (480.0 s into the window, on Kalshi's clock) rather than about 2.4 s later, when they land now. On paper for now: at that instant the bot reads every order book and counts what an order sent then would have bought, with no order placed and no money on it."],
  ["Book read", "How soon after minute 8 began the bot got an order book back. The paper +1¢ reads each book right after the real order; fast entry asks for every book at minute 8 exactly, so its figure is how close to that instant the answer came."],
  ["Fill share", "Contracts filled ÷ contracts asked for."],
  ["Base and extra contracts", "Base contracts cost the ask it saw or less: the bot would have got them anyway. Extra contracts cost more, up to the limit: only the extra cent bought them (on paper, would have bought them). Unknown ones filled before the bot recorded each fill, so they can't be split."],
  ["Break-even", "The win rate a contract needs to pay for itself: its price plus its fee. A winner pays $1, so a contract that cost 96.2¢ all-in has to win 96.2% of the time."],
  ["¢ per $10", "Profit per $10 staked, in cents: P&amp;L ÷ money staked × $10, over settled bets. +12.3¢ means each $10 bet made 12.3¢ on average."],
  ["95% range, clustered by window", "¢ per $10 ± 1.96 standard errors: where the true figure most likely sits. The standard error (how much the average would wobble if the experiment ran again) is clustered by window: bets in the same 15-minute window win or lose together, so each window counts once rather than each bet. A range that includes zero means the result could still be luck."],
];
const terms = () => fold("lr.terms", "Terms", `<dl class="lr-dl">${TERMS.map(([t, d]) => `<dt>${t}</dt><dd>${d}</dd>`).join("")}</dl>`,
                         `${TERMS.length} terms, in plain words`, "lr-terms");

// ------------------------------------------------------------------ drawing and polling
const draw = () => patch("liveresearch", window.liveResearchHtml(last));

// One read at a time, and none within half a second of the 2-second beat: the page's own refresh (every second) and
// this poll both ask.
async function refresh() {
  if (busy || Date.now() - readAt < EVERY - 500) return;
  busy = true; readAt = Date.now();
  try {
    const r = await fetch("/api/live-research", { cache: "no-store" });
    // not OK: a dashboard started before the route existed (404), or a server error
    last = r.ok ? await r.json().catch((e) => ({ error: "The dashboard's answer isn't readable: " + e.message })) : { httpStatus: r.status };
  } catch (e) {
    last = { error: "Can't reach the dashboard's server: " + ((e && e.message) || e) };
  }
  busy = false;
  draw();
}

// The page calls this on its refresh (every second) while the tab is open: draw the last answer at once, then read a new one.
window.liveResearchView = () => { draw(); refresh(); };

setInterval(() => { if (!$("liveresearch").hidden && !document.hidden) refresh(); }, EVERY);
if (page === "liveresearch" && data) window.liveResearchView();   // the page drew before this script arrived
})();
