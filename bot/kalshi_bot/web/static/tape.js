// The Tape page (SPEC_TAPE.md, Nov 6, 2026): the bot's account in a dark trading-terminal layout, with the tape,
// every decision and every result newest first, as the main event. Two halves:
//   1. window.Tape: pure functions that turn /api/state into the page's pieces (the tape's events, the bet grid, the
//      strip of figures, the countdown, the banners, the open bets, the chart). Nothing in them touches the page, the
//      network or a timer, so node loads this file with only `window = {}` and the tests (test_tape_page.py) call them.
//   2. The page wiring, only in a browser: polling, drawing into tape.html's regions, clicks, the halt button.
// Formatting comes from window.TapeFmt (tape_fmt.js, loaded first); the detail panels from window.TapePanels.
(function (root) {
  "use strict";
  const F = () => root.TapeFmt;                     // read when called: tape_fmt.js loads first
  const W15 = 900;                                  // a window: 15 minutes
  const limitsOf = (d) => Object.assign({}, F().LIMITS, (d && d.limits) || {});
  const isRunning = (d, now) => !!(d && d.heartbeat != null && now - d.heartbeat < 30);
  const asSet = (s) => s && typeof s.has === "function" ? s : new Set(Array.isArray(s) ? s : []);
  const cap = (s) => { s = String(s || ""); return s ? s[0].toUpperCase() + s.slice(1) : ""; };
  const sideWord = (s) => s === "yes" ? "Yes" : s === "no" ? "No" : cap(s);
  const nOf = (v) => v == null ? "—" : Number.isInteger(+v) ? String(+v) : (+v).toFixed(2);   // Kalshi fills fractions
  const f1 = (v) => (Math.round(v * 10) / 10).toString();
  const kindClass = (k) => String(k || "").toLowerCase().replace(/[^a-z0-9-]/g, "") || "other";

  // ------------------------------------------------------------------ the tape: every decision and every result
  // Where one bet decision's order stands, from the orders list (same ticker; one buy order a market and window).
  function fillWords(o) {
    if (!o) return null;
    if (o.filled == null) return "got none: " + (o.error || "no answer from Kalshi");
    return `filled ${nOf(o.filled)} of ${nOf(o.asked)}`;
  }
  // What a failed order's answer said: Kalshi's message when the answer is its JSON, else the start of the raw text.
  function errorWords(r) {
    let msg = "";
    try {
      const j = JSON.parse(r.response);
      const e = j && (j.error || j);
      msg = typeof e === "string" ? e : (e && (e.message || e.code)) || "";
    } catch (err) { msg = ""; }
    if (!msg) msg = String(r.response || "").slice(0, 120);
    const head = r.http_status == null ? "no answer from Kalshi" : "HTTP " + r.http_status;
    return msg ? head + ": " + msg : head;
  }
  // At one moment, results first, then failed orders, bets, any other word, and skips last.
  const RANK = { lost: 0, won: 1, error: 2, bet: 3, skip: 5 };
  const rank = (k) => k in RANK ? RANK[k] : 4;

  function events(d) {
    const T = F(), out = [], used = new Map();
    const keyOf = (k) => { const n = used.get(k) || 0; used.set(k, n + 1); return n ? k + "#" + n : k; };
    const orders = new Map();
    for (const o of (d && d.orders) || []) if (o && o.ticker && !orders.has(o.ticker)) orders.set(o.ticker, o);   // newest first
    for (const r of (d && d.decisions) || []) {
      const kind = String(r.action || "other"), ticker = r.ticker || "";
      const reason = String(r.reason || "");
      let what = kind, detail = reason;
      if (kind === "bet") {
        what = r.fav_side ? "Bet " + sideWord(r.fav_side) : "Bet";
        detail = fillWords(orders.get(ticker)) || reason;
      } else if (kind === "skip") {
        what = "Skip";
        detail = reason.replace(/^favorite at [\d.]+c is /, "");
      }
      out.push({ key: keyOf("d:" + (ticker || r.ts)), ts: +r.ts || 0, kind, mkt: T.symOf(ticker || r.series), ticker,
                 side: r.fav_side || null, price: r.fav_price ?? null, what, detail, pnl: null });
    }
    for (const b of (d && d.recentBets) || []) {
      if (!b || b.settled_ts == null || b.status === "open") continue;
      const kind = String(b.status), won = kind === "won", lost = kind === "lost";
      // keyed by ticker, not id: a market's window has one bet (bets.ticker is UNIQUE)
      out.push({ key: keyOf("b:" + (b.ticker || b.id)), ts: +b.settled_ts, kind, mkt: T.symOf(b.ticker || b.series), ticker: b.ticker || "",
                 side: b.side || null, price: b.price ?? null, what: won ? "Won" : lost ? "Lost" : cap(kind),
                 detail: `${T.signed(b.pnl)} on ${nOf(b.contracts)} contract${+b.contracts === 1 ? "" : "s"}`, pnl: b.pnl ?? null });
    }
    for (const r of (d && d.errors) || []) {
      out.push({ key: keyOf("e:" + r.ts + ":" + (r.ticker || "")), ts: +r.ts || 0, kind: "error", mkt: T.symOf(r.ticker), ticker: r.ticker || "",
                 side: null, price: null, what: "Error", detail: errorWords(r), pnl: null });
    }
    return out.map((e, i) => [e, i]).sort((a, b) => b[0].ts - a[0].ts || rank(a[0].kind) - rank(b[0].kind) || a[1] - b[1]).map((x) => x[0]);
  }

  // f: "all", "bets" (everything but skips) or "losses" (lost bets only); mkt: one market's symbol, or none for all.
  function filter(evs, f, mkt) {
    return (evs || []).filter((e) => (f === "bets" ? e.kind !== "skip" : f === "losses" ? e.kind === "lost" : true) && (!mkt || e.mkt === mkt));
  }

  // The rows, newest first: time, market, what, price, detail. A quiet date line where the day changes (and above the
  // first row when it isn't today), since the time column has no date. fresh: the keys that just arrived.
  function feedHtml(evs, fresh) {
    const T = F(), fr = asSet(fresh);
    if (!evs || !evs.length) return `<p class="t-empty">Nothing on the tape yet.</p>`;
    let html = "", day = new Date().toDateString();
    for (const e of evs) {
      const dd = new Date(e.ts * 1000).toDateString();
      if (dd !== day) { html += `<div class="tday">${T.esc(T.day(e.ts))}</div>`; day = dd; }
      html += `<div class="tr ${kindClass(e.kind)}${fr.has(e.key) ? " fresh" : ""}" data-key="${T.esc(e.key)}">`
        + `<span class="t">${T.hhmm(e.ts)}</span><span class="m" title="${T.esc(e.ticker)}">${T.esc(e.mkt)}</span>`
        + `<span class="e">${T.esc(e.what)}</span><span class="p">${e.price == null ? `<span class="muted">—</span>` : T.cents(e.price)}</span>`
        + `<span class="why" title="${T.esc(e.detail)}">${T.esc(e.detail)}</span></div>`;
    }
    return html;
  }

  // ------------------------------------------------------------------ the open bets, pinned above the tape
  // now: the moment the countdowns are read at; none leaves them for the page's 1 s tick to fill.
  function openHtml(d, now) {
    const T = F(), L = limitsOf(d), bets = (d && d.openBets) || [];
    if (!bets.length) return `<p class="on-none">No open bets. New ones are placed at minute ${L.minute} of each 15-minute window.</p>`;
    const u = d.unrealized;
    const rows = bets.slice().sort((a, b) => (a.close_ts || 0) - (b.close_ts || 0) || String(a.ticker).localeCompare(String(b.ticker))).map((b) => {
      const left = now == null || b.close_ts == null ? "" : b.close_ts - now > 0 ? "in " + T.clock(b.close_ts - now) : "settling";
      return `<div class="on-r"><a class="m" href="${T.esc(T.kalshiUrl(b.ticker))}" target="_blank" rel="noopener" title="${T.esc(b.ticker)} on Kalshi">${T.esc(T.symOf(b.ticker || b.series))}</a>`
        + `<span class="sz">${sideWord(b.side)} ${T.cents(b.price)} × ${nOf(b.contracts)}</span>`
        + `<span class="pl ${b.unrealized == null ? "muted" : T.tone(b.unrealized)}" title="What it's worth now, less what it cost">${b.unrealized == null ? "—" : T.signed(b.unrealized)}</span>`
        + `<span class="cl"><span class="cl-t">settles ${b.close_ts == null ? "—" : T.hhmm(b.close_ts)}, </span><span class="cl-in" data-close="${b.close_ts == null ? "" : b.close_ts}">${left}</span></span></div>`;
    }).join("");
    return `<div class="on-h"><span>Open bets <span class="num">${bets.length}</span></span>`
      + `<span>worth <span class="${T.tone(u)}">${T.signed(u || 0)}</span> vs cost</span></div><div class="on-list">${rows}</div>`;
  }

  // ------------------------------------------------------------------ every bet, by market and 15-minute window
  const GROUP_ORDER = ["crypto", "metals", "energy"];
  const groupRank = (g) => GROUP_ORDER.includes(g) ? GROUP_ORDER.indexOf(g) : g === "other" ? 9 : 5;
  const CELL_RANK = { "": 0, won: 1, open: 2, lost: 3 };   // two bets in one cell: lost beats open beats won

  function grid(d, now, board) {
    const T = F();
    now = now ?? (d && d.now) ?? Date.now() / 1000;
    const bets = [...((d && d.recentBets) || []), ...((d && d.openBets) || [])].filter((b) => b && (b.window_open != null || b.placed_ts != null));
    const winOf = (b) => Math.floor((b.window_open != null ? b.window_open : b.placed_ts) / W15) * W15;
    const live = (board && (board.live ? board.live.markets : board.markets)) || [];
    const boardGroup = new Map(live.filter((m) => m && m.group).map((m) => [T.sym(m.series || String(m.ticker || "").split("-")[0]), m.group]));
    const names = new Set();
    for (const s of (d && d.bySeries) || []) names.add(T.sym(s.series));
    for (const b of bets) names.add(T.symOf(b.ticker || b.series));
    names.delete("");
    let cols = [];
    if (bets.length) {
      const ws = bets.map(winOf), last = Math.max(Math.floor(now / W15) * W15, ...ws);
      const first = Math.max(Math.min(...ws), last - 95 * W15);
      for (let t = first; t <= last; t += W15) cols.push(t);
    }
    const at = new Map(cols.map((t, i) => [t, i]));
    const rows = new Map([...names].map((m) => {
      const r = { mkt: m, cells: cols.map(() => "") };
      Object.defineProperty(r, "tips", { value: cols.map(() => []), enumerable: false });   // for gridHtml's titles only
      return [m, r];
    }));
    for (const b of bets) {
      const r = rows.get(T.symOf(b.ticker || b.series)), i = at.get(winOf(b));
      if (!r || i == null) continue;
      const st = b.status === "open" ? "open" : b.status === "won" || b.status === "lost" ? b.status : "";
      if (!st) continue;
      if (CELL_RANK[st] > CELL_RANK[r.cells[i]]) r.cells[i] = st;
      r.tips[i].push(`${sideWord(b.side)} ${T.cents(b.price)} × ${nOf(b.contracts)}: ${st === "open" ? "open" : st + " " + T.signed(b.pnl)}`);
    }
    const byGroup = new Map();
    for (const r of rows.values()) {
      const g = boardGroup.get(r.mkt) || T.groupOf(r.mkt);
      if (!byGroup.has(g)) byGroup.set(g, []);
      byGroup.get(g).push(r);
    }
    const groups = [...byGroup.keys()].sort((a, b) => groupRank(a) - groupRank(b) || a.localeCompare(b))
      .map((g) => ({ group: g, rows: byGroup.get(g).sort((a, b) => a.mkt.localeCompare(b.mkt)) }));
    return { cols, groups };
  }

  // The grid: a market's name is a button that filters the tape to it (sel: the market picked, if any). Hours are
  // marked along the top, midnight with its date.
  function gridHtml(g, sel) {
    const T = F(), cols = (g && g.cols) || [], groups = (g && g.groups) || [];
    if (!cols.length) return `<p class="g-empty">No bets yet. Each one shows here as a square, green if it won and red if it lost.</p>`;
    const tally = { won: 0, lost: 0, open: 0 };
    for (const grp of groups) for (const r of grp.rows) for (const c of r.cells) if (c) tally[c]++;
    const hour = (t) => {
      const dt = new Date(t * 1000);
      if (dt.getMinutes() !== 0) return "";
      return dt.getHours() === 0 ? T.day(t) : T.hhmm(t).replace(":00", "");
    };
    // one flex row per market, its name pinned at the left while the cells scroll under it
    let html = `<div class="gr gr-h"><span class="gm"></span>` + cols.map((t, i) => `<span class="gh">${i < cols.length - 2 ? T.esc(hour(t)) : ""}</span>`).join("") + `</div>`;
    for (const grp of groups) {
      html += `<div class="gg"><span>${T.esc(T.GROUPS[grp.group] || cap(grp.group))}</span></div>`;
      for (const r of grp.rows) {
        const on = sel === r.mkt;
        html += `<div class="gr"><button type="button" class="gm${on ? " on" : ""}" data-mkt="${T.esc(r.mkt)}" aria-pressed="${on}" title="Show only ${T.esc(r.mkt)} on the tape">${T.esc(r.mkt)}</button>`
          + r.cells.map((c, i) => {
            const tip = c ? `${r.mkt}, ${T.when(cols[i])} window: ${(r.tips && r.tips[i] && r.tips[i].join("; ")) || c}` : "";
            return `<span class="c${c ? " " + c : ""}"${tip ? ` title="${T.esc(tip)}"` : ""}></span>`;
          }).join("") + `</div>`;
      }
    }
    const span = `${T.when(cols[0])} to ${T.when(cols[cols.length - 1] + W15)}, ${cols.length} window${cols.length === 1 ? "" : "s"}`;
    return `<div class="gtop"><span>${T.esc(span)}</span><span class="muted">Pick a market to see only its rows on the tape.</span></div>`
      + `<div class="gwrap"><div class="g" role="group" aria-label="Every bet in the last ${cols.length} windows: ${tally.won} won, ${tally.lost} lost, ${tally.open} open">${html}</div></div>`
      + `<div class="gkey"><span><i class="c won"></i>Won</span><span><i class="c lost"></i>Lost</span><span><i class="c open"></i>Open</span><span><i class="c"></i>No bet</span></div>`;
  }

  // ------------------------------------------------------------------ the countdown to the next entry
  function countdown(d, now, running) {
    const T = F(), L = limitsOf(d);
    now = now ?? (d && d.now) ?? Date.now() / 1000;
    running = running ?? isRunning(d, now);
    const s = ((now % W15) + W15) % W15, at = L.minute * 60;
    if (d && d.halt) return { text: "Halted", cls: "down" };
    if (!running) return { text: "Not running", cls: "down" };
    if (d && d.blackout && d.blackout.active) return { text: "Blackout", cls: "" };
    if (s >= at && s <= at + L.grace) return { text: "Entering now", cls: "" };
    return { text: T.clock(Math.ceil(s < at ? at - s : W15 + at - s)), cls: "" };
  }

  // ------------------------------------------------------------------ the strip: the account at a glance
  // [{label, value, sub}], value and sub as HTML. opts: {hideBal, now, running}. With the balance hidden the account's
  // dollars give way to its change since the start, and "Since start" (the same figure) is left out.
  function strip(d, opts) {
    const T = F(), o = opts || {}, L = limitsOf(d);
    const now = o.now ?? d.now, run = o.running ?? isRunning(d, now);
    const equity = (d.bankroll || 0) + (d.unrealized || 0);
    const acct = d.kalshi && !d.kalshi.error && d.kalshi.value != null ? d.kalshi : null;
    const put = Math.round((d.start || 0) * 100) / 100, p = Math.round((Math.round(equity * 100) / 100 - put) * 100) / 100;
    const r = d.start ? p / d.start : null, rp = r == null ? null : Math.round(r * 1000) / 10;   // rp: the % as shown
    const toned = (shown, text) => `<span class="${T.tone(shown)}">${text}</span>`;   // coloured as the figure shows
    const out = [];
    const name = T.label(d.mode) + " account";
    out.push(o.hideBal
      ? { label: name, value: toned(rp, T.spct(r)), sub: "since the start, balance hidden" }
      : { label: name, value: T.money(acct ? acct.value : equity), sub: acct ? "live from Kalshi" : "the bot's books" });
    const sim = d.sim && d.sim.value != null ? d.sim : null;
    if (sim) {
      const sr = sim.start ? sim.value / sim.start - 1 : null, srp = sr == null ? null : Math.round(sr * 1000) / 10;
      const t0 = Date.parse(sim.t0);   // read in UTC: t0 is midnight UTC, still the day before west of London
      const since = isNaN(t0) ? "" : "since " + new Date(t0).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
      out.push(o.hideBal
        ? { label: `${T.money(sim.start, 0)} simulation`, value: toned(srp, T.spct(sr)), sub: since }
        : { label: `${T.money(sim.start, 0)} simulation`, value: T.money(sim.value), sub: toned(srp, T.spct(sr)) + (since ? " " + since : "") });
    }
    out.push({ label: "Last 24 hours", value: toned(d.day, T.signed(d.day)),
               sub: `${T.count(d.dayBets || 0)} bet${d.dayBets === 1 ? "" : "s"} placed` });
    if (!o.hideBal) out.push({ label: "Since start", value: toned(p, T.signed(p)), sub: `${toned(rp, T.spct(r))} on ${T.money(put)}` });
    const n = (d.wins || 0) + (d.losses || 0);
    out.push({ label: "Won and lost", value: `<span${d.wins ? ' class="up"' : ""}>${T.count(d.wins || 0)}</span>, <span${d.losses ? ' class="down"' : ""}>${T.count(d.losses || 0)}</span>`,
               sub: n ? "settled bets" : "none settled yet" });
    const w = d.winShare ?? (n ? d.wins / n : null);
    out.push({ label: "Win rate", value: w == null ? "—" : T.pct(w), sub: d.need == null ? "per contract" : `needs ${T.pct(d.need)}` });
    out.push({ label: "Deepest fall", value: T.pct(d.maxDrop || 0), sub: `from a peak; it stops at ${T.pct(L.dayDrop, 0)} in a day` });
    out.push({ label: "Next bet", value: d.nextBet == null ? "—" : T.money(d.nextBet), sub: `${T.limitPct(L.betPct)} of the account` });
    const cd = countdown(d, now, run);
    out.push({ label: "Next entry", value: `<span class="cd${cd.cls ? " " + cd.cls : ""}" data-cd>${T.esc(cd.text)}</span>`, sub: `minute ${L.minute} of each window` });
    return out;
  }
  function stripHtml(items) {
    const T = F();
    return (items || []).map((x) => `<div class="sf"><span class="sl">${T.esc(x.label)}</span><span class="sv">${x.value}</span>${x.sub ? `<span class="ss">${x.sub}</span>` : ""}</div>`).join("");
  }

  // ------------------------------------------------------------------ banners: only what needs attention
  // The same facts as the classic page's (dashboard.html render()): a halt, a blackout, the bot not running, cash the bot
  // can't bet from, Kalshi and the books apart, low cash, a restart owed. hideBal keeps dollar amounts out of them.
  function banners(d, now, running, hideBal) {
    const T = F(), L = limitsOf(d);
    now = now ?? d.now;
    running = running ?? isRunning(d, now);
    const b = [], code = (s) => `<code>${s}</code>`;
    const equity = (d.bankroll || 0) + (d.unrealized || 0);
    const acct = d.kalshi && !d.kalshi.error && d.kalshi.value != null ? d.kalshi : null;
    if (d.halt) {
      const t = Date.parse(d.halt.ts) / 1000;
      b.push(`<div class="note" role="alert"><b>Trading halted</b>${isNaN(t) ? "" : " since " + T.when(t, now)}: ${T.esc(d.halt.reason)}. `
        + `No new orders until you run ${code("python bot.py --resume")}. Open bets still settle.</div>`);
    } else if (d.blackout && d.blackout.active) {
      b.push(`<div class="note warn" role="status"><b>${T.esc(d.blackout.what)} blackout</b> No new bets until ${T.hhmm(d.blackout.to)}.</div>`);
    }
    if (!running) {
      const cmd = "python bot.py" + (d.live ? " --live" + (d.env === "prod" ? " --env prod" : "") : "");
      b.push(`<div class="note warn" role="status"><b>Bot not running</b> ${d.heartbeat ? "Last seen " + T.when(d.heartbeat, now) + ". " : ""}`
        + `Nothing is being bought. Start it with ${code(cmd)}.</div>`);
    }
    const idle = acct && acct.crypto != null ? acct.total - acct.crypto : 0;   // cash in sections the bot can't bet from
    if (idle >= 0.01) b.push(`<div class="note warn" role="status"><b>${hideBal ? "Some cash" : T.money(idle)} outside Crypto &amp; Commodities</b> `
      + `It's in another section of your Kalshi account, which the bot can't bet from. Move it with ${code("python bot.py --fund-crypto")}.</div>`);
    if (d.live && acct && !((d.openBets || []).length) && (acct.held || 0) < 0.005) {   // Kalshi and the books apart, nothing riding
      const gap = Math.round(((acct.crypto != null ? acct.crypto : acct.total) - equity) * 100) / 100, more = gap > 0;
      if (Math.abs(gap) >= 1) b.push(`<div class="note warn" role="status"><b>Kalshi holds ${hideBal ? "" : T.money(Math.abs(gap)) + " "}${more ? "more" : "less"} than the bot's books</b> `
        + `If you ${more ? "added money" : "took money out"}, run ${code("python bot.py --rebase")} so it counts as ${more ? "put in, not profit" : "taken out, not a loss"}.</div>`);
    }
    if (d.live && d.kalshi && d.kalshi.crypto != null && d.kalshi.crypto < L.minCash) b.push(`<div class="note warn" role="status"><b>Low cash for these markets</b> `
      + `${T.money(d.kalshi.crypto)} in Kalshi's Crypto &amp; Commodities section, under the ${T.money(L.minCash, 0)} or so a $1 bet needs. Move cash there with ${code("python bot.py --fund-crypto")}.</div>`);
    if (d.mode === "live-prod" && d.restartBot !== false) {
      const how = `in the bot's own window press Ctrl+C, then run ${code("python bot.py --live --env prod")}, but not in minutes :08–:09, :23–:24, :38–:39 or :53–:54 of the hour (an entry may be under way)`;
      b.push(d.restartBot === undefined
        ? `<div class="note warn" role="status"><b>Restart pending</b> The Oct 12 changes (the +1¢ limit measured on paper, the Live Research tab) start after a restart. First the dashboard: stop it and run ${code("python dashboard.py")}. Then the bot: ${how}. This note goes away by itself once both have restarted.</div>`
        : `<div class="note warn" role="status"><b>Restart the bot</b> Its Oct 12 changes (the +1¢ limit measured on paper) start after a restart: ${how}. This note goes away by itself once it has.</div>`);
    }
    return b.join("");
  }

  // ------------------------------------------------------------------ the account chart
  // About n round steps from lo to hi: the round step (1, 2, 2.5 or 5 times a power of ten) nearest the even split, so a
  // short chart still gets a few labels rather than jumping from $50 apart to $100.
  function niceTicks(lo, hi, n) {
    const raw = (hi - lo || 1) / n, mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).reduce((a, s) => Math.abs(Math.log(s / raw)) < Math.abs(Math.log(a / raw)) ? s : a);
    const out = [];
    for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(10));
    return { ticks: out, step };
  }
  // ---- the long view's asset classes (added Nov 8, 2026: when each asset class, metals for one, came in)
  // Each class's first bet, and each market's, come from the simulation's own replay (state()'s sim.groups and
  // sim.markets, ISO strings). The day is read off the string itself, as backtest.js reads it, so midnight UTC on
  // Dec 20 never shows as Dec 19 west of London.
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const isoDay = (iso) => { const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || "")); return m && MONTHS[+m[2] - 1] ? `${MONTHS[+m[2] - 1]} ${+m[3]}` : ""; };
  const isoTs = (iso) => { const t = Date.parse(String(iso || "")); return isFinite(t) ? t / 1000 : null; };
  const CLASS_TONE = { crypto: 1, metals: 2, energy: 3 };
  const BAND_H = 10, BAND_GAP = 3, RIB_TOP = 7, MERGE = 2 * 86400;   // classes within two days share a rule
  const andList = (xs) => xs.length < 2 ? xs.join("") : xs.slice(0, -1).join(", ") + " and " + xs[xs.length - 1];
  // The classes on the chart: [{key, t, day}] for every class whose first bet came before the line ends, oldest first.
  function classesIn(classes, t1) {
    return (classes || []).filter((c) => c && c.key != null).map((c) => ({ key: String(c.key), t: isoTs(c.first), day: isoDay(c.first) }))
      .filter((c) => c.t != null && c.t <= t1).sort((a, b) => a.t - b.t);
  }
  // The marks themselves, given the plot's x scale: a rule (with its label) for each run of classes starting inside the
  // plot, a band under the plot for every class from its first bet to the right edge, and on each band a notch for each
  // day one of its markets had its first bet, named on hover. Returns {rules, bands, notches, say}.
  function classMarks(T, cls, markets, x, t0, t1, M, rx, by) {
    const out = { rules: "", bands: "", notches: "", say: "" };
    if (!cls.length) return out;
    // rules: classes starting after the line does, merged when they start within MERGE of each other
    const runs = [];
    for (const c of cls.filter((k) => k.t > t0)) {
      const r = runs[runs.length - 1];
      if (r && c.t - r.t < MERGE) r.names.push(c.key); else runs.push({ t: c.t, day: c.day, names: [c.key] });
    }
    let lastX = -Infinity, row = 0;
    out.rules = runs.map((r) => {
      const px = f1(x(r.t)), label = `${cap(andList(r.names))}, ${r.day}`;
      row = px - lastX < 150 ? (row + 1) % 2 : 0;
      lastX = px;
      const end = px > rx - label.length * 6.4 - 8;   // near the right edge the label hangs off the left of its rule
      return `<line class="ch-cls" x1="${px}" x2="${px}" y1="${M.t}" y2="${by}"/>`
        + `<text class="ch-cls-t" x="${end ? px - 5 : px + 5}" y="${M.t + 10 + row * 13}"${end ? ' text-anchor="end"' : ""}>${T.esc(label)}</text>`;
    }).join("");
    // bands: one row a class, in the order they came
    const rowY = (i) => by + RIB_TOP + i * (BAND_H + BAND_GAP);
    out.bands = cls.map((c, i) => {
      const bx = Math.max(M.l, x(c.t)), y = rowY(i), name = cap(c.key);
      const room = rx - bx > name.length * 6.4 + 10;
      return `<rect class="ch-band ch-b${CLASS_TONE[c.key] || 4}" x="${f1(bx)}" y="${y}" width="${f1(Math.max(1, rx - bx))}" height="${BAND_H}" rx="2">`
        + `<title>${T.esc(name)}: first bet ${T.esc(c.day)}</title></rect>`
        + `<text class="ch-band-t" x="${f1(room ? bx + 5 : bx - 5)}" y="${y + BAND_H - 2}"${room ? "" : ' text-anchor="end"'}>${T.esc(name)}</text>`;
    }).join("");
    // notches: each market's first bet on its class's band, one per class and day, inside the line's span
    const rowOf = new Map(cls.map((c, i) => [c.key, i])), days = new Map();
    for (const m of markets || []) {
      if (!m || m.key == null) continue;
      const t = isoTs(m.first), g = T.groupOf(String(m.key)), day = isoDay(m.first);
      if (t == null || t < t0 || t > t1 || !rowOf.has(g)) continue;
      const k = g + "|" + day, at = days.get(k);
      if (at) { at.names.push(String(m.key)); at.t = Math.min(at.t, t); } else days.set(k, { g, day, t, names: [String(m.key)] });
    }
    out.notches = [...days.values()].map((n) => {
      const px = f1(x(n.t)), y = rowY(rowOf.get(n.g));
      return `<g class="ch-mk"><rect x="${f1(px - 3)}" y="${y - 2}" width="6" height="${BAND_H + 4}"/><line x1="${px}" x2="${px}" y1="${y - 2}" y2="${y + BAND_H + 2}"/>`
        + `<title>${T.esc(n.names.sort().join(", "))}: first bet ${T.esc(n.day)}</title></g>`;
    }).join("");
    out.say = ` The lines and bands mark each asset class's first bet: ${cls.map((c) => `${cap(c.key)} ${c.day}`).join(", ")}.`;
    return out;
  }
  // The dates along the bottom: hours for a day or two, days for a few weeks, months for the long view.
  function axisDate(T, t, span, now) {
    if (span > 120 * 86400) return new Date(t * 1000).toLocaleDateString("en-US", { month: "short", year: "numeric" });
    if (span > 3 * 86400) return T.day(t);
    return T.when(t, now);
  }

  // points: [[ts, value], ...]. opts: {w, h (px), base (the dashed line), baseLabel ("Start"), label (what the line is),
  // losses (false: no red ticks), now (for the dates), empty (the text with under two points), classes and markets
  // (the long view's [{key, first}]: a rule and a band for each asset class, a notch for each market)}. The SVG is drawn
  // at its real size, so text and dots never stretch; the page redraws it when its box changes size.
  function chartHtml(points, opts) {
    const T = F(), o = opts || {};
    const pts = (points || []).filter((p) => p && p[1] != null && isFinite(p[0]) && isFinite(p[1]));
    if (pts.length < 2) return `<p class="ch-empty">${T.esc(o.empty || "The line starts with the first settled bet.")}</p>`;
    const W = Math.max(260, Math.floor(o.w || 640)), H = Math.max(120, Math.floor(o.h || 220));
    const t0 = pts[0][0], t1 = pts[pts.length - 1][0], last = pts[pts.length - 1][1];
    const cls = classesIn(o.classes, t1);   // the bands go under the plot, so the plot gives up their height
    // the top keeps room for a rule's label only when one is drawn
    const M = { t: cls.some((c) => c.t > t0) ? 30 : 12, r: 78, b: 24 + (cls.length ? RIB_TOP + cls.length * (BAND_H + BAND_GAP) : 0), l: 10 }, rx = W - M.r, by = H - M.b;
    const base = o.base != null && isFinite(o.base) ? +o.base : pts[0][1];
    const vs = pts.map((p) => p[1]).concat([base]);
    let lo = Math.min(...vs), hi = Math.max(...vs);
    const pad = Math.max((hi - lo) * 0.12, 0.5); lo -= pad; hi += pad;
    const x = (t) => M.l + (t1 === t0 ? 0 : (t - t0) / (t1 - t0)) * (rx - M.l);
    const y = (v) => M.t + (1 - (v - lo) / (hi - lo)) * (by - M.t);
    const { ticks, step } = niceTicks(lo, hi, Math.max(2, Math.round((by - M.t) / 48)));
    const dp = Number.isInteger(+step.toFixed(9)) ? 0 : 2;
    const up = last >= base, ly = y(last), yb = y(base);
    const line = pts.map((p, i) => `${i ? "L" : "M"}${f1(x(p[0]))},${f1(y(p[1]))}`).join("");
    const area = `${line}L${f1(x(t1))},${by}L${f1(x(t0))},${by}Z`;
    const tagY = Math.min(Math.max(ly, M.t + 9), by - 9);
    const baseY = Math.abs(yb - tagY) < 20 ? (yb <= tagY ? tagY - 20 : tagY + 20) : yb;   // the base label steps aside from the tag
    const grid = ticks.map((v) => {
      const ty = y(v);
      return `<line class="ch-grid" x1="${M.l}" x2="${rx}" y1="${f1(ty)}" y2="${f1(ty)}"/>`
        + (Math.abs(ty - tagY) < 16 || Math.abs(ty - baseY) < 16 || ty < M.t || ty > by ? "" : `<text class="ch-y" x="${rx + 8}" y="${f1(ty + 3.5)}">${T.money(v, dp)}</text>`);
    }).join("");
    const xs = W < 480 ? [t0, t1] : [t0, (t0 + t1) / 2, t1];
    const xl = xs.map((t, i) => `<text class="ch-x" x="${f1(x(t))}" y="${H - 7}" text-anchor="${i === 0 ? "start" : i === xs.length - 1 ? "end" : "middle"}">${T.esc(axisDate(T, t, t1 - t0, o.now))}</text>`).join("");
    const cm = classMarks(T, cls, o.markets, x, t0, t1, M, rx, by);
    let drops = 0;
    const losses = o.losses === false ? "" : pts.map((p, i) => {
      if (!i || !(p[1] < pts[i - 1][1] - 1)) return "";
      drops++;
      const px = f1(x(p[0]));
      return `<line x1="${px}" x2="${px}" y1="${by}" y2="${by - 7}"><title>${T.esc(T.when(p[0], o.now))}: ${T.signed(p[1] - pts[i - 1][1])}</title></line>`;
    }).join("");
    const what = o.label || "Account value";
    const say = `${what}, from ${T.money(pts[0][1])} to ${T.money(last)}, ${T.when(t0, o.now)} to ${T.when(t1, o.now)}.`
      + (drops ? ` ${drops} drop${drops === 1 ? "" : "s"} of more than $1 marked in red along the bottom.` : "") + cm.say;
    const svg = `<svg class="cv ${up ? "up" : "down"}" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="${T.esc(say)}"`
      + ` data-l="${M.l}" data-r="${rx}" data-top="${M.t}" data-bot="${by}" data-t0="${t0}" data-t1="${t1}" data-lo="${lo}" data-hi="${hi}">`
      + `<defs><linearGradient id="tape-wash" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="currentColor" stop-opacity=".2"/><stop offset="1" stop-color="currentColor" stop-opacity="0"/></linearGradient></defs>`
      + grid + cm.rules + `<line class="ch-base" x1="${M.l}" x2="${rx}" y1="${f1(yb)}" y2="${f1(yb)}"/>`
      + `<text class="ch-base-t" x="${rx + 8}" y="${f1(baseY + 3.5)}">${T.esc(o.baseLabel || "Start")}</text>`
      + `<path class="ch-area" d="${area}" fill="url(#tape-wash)"/><path class="ch-line" d="${line}"/>`
      + (losses ? `<g class="ch-loss">${losses}</g>` : "")
      + (cm.bands ? `<g class="ch-rib">${cm.bands}${cm.notches}</g>` : "")
      + `<circle class="ch-dot" cx="${f1(x(t1))}" cy="${f1(ly)}" r="3"/>`
      + `<rect class="ch-tag" x="${rx + 4}" y="${f1(tagY - 9)}" width="${M.r - 8}" height="18" rx="2"/>`
      + `<text class="ch-tag-t" x="${rx + 4 + (M.r - 8) / 2}" y="${f1(tagY + 3.5)}" text-anchor="middle">${T.money(last)}</text>`
      + xl
      + `<line class="ch-xh" x1="0" x2="0" y1="${M.t}" y2="${by}" visibility="hidden"/><circle class="ch-hd" r="3.5" cx="0" cy="0" visibility="hidden"/>`
      + `</svg>`;
    return `<div class="ch-box">${svg}<div class="ch-tip" hidden></div></div>`;
  }

  root.Tape = { events, filter, feedHtml, openHtml, grid, gridHtml, strip, stripHtml, countdown, banners, chartHtml, niceTicks, isRunning };
})(typeof window !== "undefined" ? window : globalThis);

// ====================================================================== the page wiring (a browser only)
if (typeof document !== "undefined") (function () {
  "use strict";
  const Tape = window.Tape, T = window.TapeFmt;
  const $ = (id) => document.getElementById(id);
  const store = { get: (k) => { try { return localStorage.getItem(k); } catch (e) { return null; } },
                  set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) { /* private window: not kept */ } } };
  const TABS = [["bets", "Every bet"], ["board", "Live markets"], ["orders", "Orders"], ["fills", "Fill rate"], ["markets", "By market"], ["rules", "Rules"]];
  const FILTERS = [["all", "Everything"], ["bets", "Bets and results"], ["losses", "Losses"]];
  const RANGES = [["1d", "1D", 86400, "A day ago"], ["1w", "1W", 604800, "A week ago"], ["all", "All", 0, "Start"]];
  // the long view (since markets opened) is the simulation, one point every few hours: a day of it is noise, so months
  const SIM_RANGES = [["1m", "1M", 30 * 86400, "A month ago"], ["3m", "3M", 91 * 86400, "3 months ago"], ["all", "All", 0, "Start"]];
  const FEED_MAX = 300;
  const NONE = `<p class="lp-none">This panel isn't available yet.</p>`;
  const pick = (v, list, dflt) => list.some((x) => x[0] === v) ? v : dflt;

  let data = null, mode = store.get("mode"), skew = 0, running = false;
  let armed = false, armTimer = null, halting = 0;   // halting: when the halt was sent, until a reading taken after it
  let hideBal = store.get("hideBal") === "1";
  let tab = pick(store.get("tapeTab"), TABS, "bets");
  let feedF = pick(store.get("tapeFilter"), FILTERS, "all");
  let range = pick(store.get("tapeRange"), RANGES, "all");
  let simRange = pick(store.get("tapeSimRange"), SIM_RANGES, "all");
  let which = store.get("tapeChart") === "sim" ? "sim" : "bot";
  let mkt = null;                      // the market the tape is filtered to, from the grid
  let known = null;                    // every event key seen so far; null until the first draw (which staggers in)
  let board = null, boardErr = false, boardBusy = false;
  const lastFav = new Map();           // the live board's last favourite per market, for its flashes (TapePanels.board)
  let bal = null, balStale = false, balBusy = false;
  let chartModel = null, chartSig = "";
  const nowS = () => Date.now() / 1000 + skew;

  // Write a region only when its markup changed, so the 1 s refresh never disturbs hover, focus or scroll. Focus inside
  // a rewritten region goes back to the control that had it.
  const shown = new Map();
  const focusSel = (a) => {
    if (a.id) return "#" + CSS.escape(a.id);
    for (const at of a.attributes) if (at.name.startsWith("data-")) return `[${at.name}="${CSS.escape(at.value)}"]`;
    return null;
  };
  function patch(id, html) {
    const el = $(id);
    if (!el || shown.get(id) === html) return false;
    shown.set(id, html);
    const a = document.activeElement, sel = a && a !== document.body && el.contains(a) ? focusSel(a) : null;
    el.innerHTML = html;
    if (sel) { const b = el.querySelector(sel); if (b) b.focus({ preventScroll: true }); }
    return true;
  }

  // ---------------------------------------------------------------- reading the state
  let loading = false;
  async function load() {
    if (loading) return;
    loading = true;
    const asked = mode, sent = Date.now();
    try {
      const r = await fetch("/api/state" + (mode ? "?mode=" + encodeURIComponent(mode) : ""), { cache: "no-store" });
      if (!r.ok) throw new Error("HTTP " + r.status);
      const d = await r.json();
      if (mode !== asked) return;      // the viewer picked another account meanwhile: its own reading comes next
      data = d;
      skew = (d.now || Date.now() / 1000) - Date.now() / 1000;
      if (halting && sent > halting) halting = 0;
      document.body.classList.remove("offline");
      render();
    } catch (e) {
      document.body.classList.add("offline");          // keep the last picture, dimmed, rather than blanking it
      status("off", "Can't reach the dashboard's server");
    } finally {
      loading = false;
    }
  }

  function status(kind, text) {
    patch("status", `<span class="dot ${kind}" aria-hidden="true"></span><span class="st">${T.esc(text)}</span>`);
  }

  // ---------------------------------------------------------------- drawing
  function render() {
    const d = data;
    patch("modes", modesHtml());
    if (!d.modes || !d.modes.length) return renderEmpty();
    mode = d.mode;
    const now = nowS();
    running = Tape.isRunning(d, d.now);
    if (d.halt) status("warn", "Halted");
    else if (running) status("on", "Running");
    else status("off", "Not running");
    patch("haltTop", haltButton());
    patch("banners", Tape.banners(d, d.now, running, hideBal));
    patch("strip", Tape.stripHtml(Tape.strip(d, { hideBal, now, running })));
    renderLeft();
    renderChart();
    renderTape();
    const ck = d.clock, off = ck && ck.synced && typeof ck.offset === "number" ? ck.offset : null;
    patch("foot", `Updated ${T.hhmm(d.now)}. Refreshes every second. ` + (off == null ? "Clock from this PC."
      : `<span title="This PC's clock is ${Math.abs(off).toFixed(3)} s ${off >= 0 ? "behind" : "ahead"}">Clock set to internet time.</span>`));
    tick();
  }

  function renderEmpty() {
    status("off", "The bot hasn't run yet");
    for (const id of ["haltTop", "banners", "strip", "chartHead", "chart", "openNow", "filters", "foot"]) patch(id, "");
    patch("tapeHead", `<h2>Tape</h2>`);
    patch("feed", `<p class="t-empty">The tape starts with the bot's first decision.</p>`);
    patch("ltabs", "");
    patch("lpanel", `<div class="empty"><b>Nothing to show yet</b><span>Run the bot once and its account appears here: `
      + `<code>python bot.py</code> for a paper run, or <code>python bot.py --live</code>.</span></div>`);
  }

  function modesHtml() {
    const ms = (data && data.modes) || [];
    return ms.map((m) => `<button type="button" class="nav-b" data-mode="${T.esc(m)}" aria-current="${data && m === data.mode}">${T.esc(T.label(m))}</button>`).join("")
      + [["liveresearch", "Live Research"], ["latency", "Latency"], ["backtest", "Backtest"], ["account", "Classic view"]]
        .map(([p, l]) => `<button type="button" class="nav-b" data-page="${p}">${l}</button>`).join("");
  }

  // One halt button, always in reach: two taps, so a stray touch can't halt it. There is no resume button.
  function haltButton() {
    if (data && data.halt) return `<button class="halt-btn" type="button" disabled>Halted</button>`;
    if (halting) return `<button class="halt-btn arm" type="button" disabled>Halting…</button>`;
    return `<button class="halt-btn${armed ? " arm" : ""}" type="button" data-halt>${armed ? "Tap again to halt" : "Halt trading"}</button>`;
  }

  // ---- the left panel: its tabs, and the chosen tab's body
  function renderLeft() {
    if (!data || !data.modes || !data.modes.length) return;
    patch("ltabs", TABS.map(([k, l]) => `<button type="button" class="lt" role="tab" id="tab-${k}" data-tab="${k}" aria-selected="${k === tab}"`
      + ` aria-controls="lpanel" tabindex="${k === tab ? 0 : -1}">${l}</button>`).join(""));
    const lp = $("lpanel");
    if (lp) lp.setAttribute("aria-labelledby", "tab-" + tab);
    let html;
    if (tab === "bets") html = Tape.gridHtml(Tape.grid(data, nowS(), board), mkt);
    else {
      const P = window.TapePanels, fn = P && P[tab];
      if (typeof fn !== "function") html = NONE;
      else {
        try {
          if (tab === "board") {
            const st = typeof P.boardStatus === "function" ? P.boardStatus(board, boardErr, nowS()) : null;
            html = (st && st.text ? `<div class="lp-head"><span class="bstat"><span class="dot ${T.esc(st.kind || "")}" aria-hidden="true"></span>${T.esc(st.text)}</span></div>` : "")
              + fn(board, data, nowS(), lastFav);
          } else if (tab === "fills") html = fn(data, Math.max(300, Math.floor(((lp && lp.clientWidth) || 640) - 32)));
          else html = fn(data);
        } catch (e) {
          console.error("Tape panel " + tab, e);
          html = NONE;
        }
      }
    }
    patchGrid(html);
  }
  // The grid scrolls sideways inside its own box: kept at the newest windows (the right end) unless the viewer has
  // scrolled away from it, and their place kept when it redraws.
  function patchGrid(html) {
    const old = document.querySelector("#lpanel .gwrap");
    const atEnd = !old || old.scrollLeft + old.clientWidth >= old.scrollWidth - 4, left = old ? old.scrollLeft : 0;
    if (!patch("lpanel", html)) return;
    const w = document.querySelector("#lpanel .gwrap");
    if (w) w.scrollLeft = atEnd ? w.scrollWidth : left;
  }

  // ---- the chart: the paper bot's books or the $1,000 simulation, over a range
  function chartPoints(d) {
    const sim = d.sim && d.sim.curve && d.sim.curve.length ? d.sim : null;
    if (which === "sim" && sim) {
      const t0 = Date.parse(sim.t0) / 1000, st = (sim.step || 1) * 3600;
      return { pts: sim.curve.map((v, i) => [t0 + i * st, v]).filter((p) => p[1] != null), base: sim.start, sim: true };
    }
    return { pts: (d.curve || []).map((p) => [p[0], p[1]]), base: d.start, sim: false };
  }
  function renderChart() {
    const d = data, sim = d.sim && d.sim.curve && d.sim.curve.length ? d.sim : null;
    const useSim = which === "sim" && !!sim;
    let { pts, base } = chartPoints(d);
    // each view keeps its own range: days and a week for the paper bot, months for the long view
    const LIST = useSim ? SIM_RANGES : RANGES, cur = useSim ? simRange : range;
    const R = LIST.find((r) => r[0] === cur), secs = R[2];
    const ref = useSim ? (pts.length ? pts[pts.length - 1][0] : 0) : Math.floor(nowS() / 60) * 60;
    if (secs) {
      const cut = ref - secs, before = pts.filter((p) => p[0] < cut);
      pts = pts.filter((p) => p[0] >= cut);
      if (before.length) pts.unshift([cut, before[before.length - 1][1]]);
      if (pts.length === 1) pts.push([ref, pts[0][1]]);   // nothing settled in the range: a flat line to now
      if (pts.length) base = pts[0][1];
    }
    // the long view is the $1,000 simulation: the bot's rules replayed since Kalshi's first 15-minute market
    const opened = useSim ? new Date(Date.parse(sim.t0)).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" }) : "";
    const title = useSim ? `${T.money(sim.start, 0)} simulation` : `${T.label(d.mode)} account`;
    const last = pts.length ? pts[pts.length - 1][1] : null, ch = last == null || base == null ? null : last - base;
    const r = ch == null || !base ? null : ch / base, rp = r == null ? null : Math.round(r * 1000) / 10;
    const when = secs ? `since ${R[3].toLowerCase()}` : useSim ? `since ${opened}` : "since the start";
    const head = `<div class="chh-l"><h2>${T.esc(title)}</h2>`
      + (last == null ? "" : (hideBal ? "" : `<span class="chh-v">${T.money(last)}</span>`)
        + `<span class="chh-c"><span class="${T.tone(rp)}">${hideBal ? "" : T.signed(ch) + ", "}${T.spct(r)}</span> <span class="muted">${when}</span></span>`) + `</div>`
      + `<div class="chh-r">`
      + (sim ? `<div class="seg" role="group" aria-label="Which account">`
        + `<button type="button" data-chart="bot" aria-pressed="${!useSim}">Paper bot</button>`
        + `<button type="button" data-chart="sim" aria-pressed="${useSim}">Since markets opened</button></div>` : "")
      + `<div class="seg" role="group" aria-label="Time range">${LIST.map(([k, l]) => `<button type="button" data-range="${k}" aria-pressed="${k === cur}">${l}</button>`).join("")}</div>`
      + `</div>`
      + (useSim ? `<p class="chh-n">The bot's rules replayed from ${T.money(sim.start, 0)} on real prices and real book depth. `
        + `Lines and bands show when each asset class had its first bet; hover a notch for each market's.</p>` : "");
    patch("chartHead", head);
    const box = $("chart");
    if (!box) return;
    const w = Math.floor(box.clientWidth) || 640, h = Math.floor(box.clientHeight) || 220;
    const lastP = pts[pts.length - 1];
    const groups = useSim ? sim.groups || [] : [], markets = useSim ? sim.markets || [] : [];
    const sig = [which, cur, useSim, w, h, pts.length, lastP && lastP[0], lastP && lastP[1], pts[0] && pts[0][0], base,
                 groups.length, markets.length].join("|");
    if (sig === chartSig && shown.has("chart")) return;   // nothing new to draw: no work, and a hover stays put
    chartSig = sig;
    const html = Tape.chartHtml(pts, { w, h, base, baseLabel: R[3], now: nowS(), losses: !useSim,
      classes: groups, markets: markets,
      label: useSim ? "The simulated account's value since markets opened, every few hours" : "The account's value after each settled bet",
      empty: secs ? "Nothing settled in this range." : "The line starts with the first settled bet." });
    chartModel = pts.length >= 2 ? { pts, sim: useSim } : null;
    patch("chart", html);
  }
  // Hovering the chart: a crosshair and the value at the nearest point.
  function chartHover(e) {
    const svg = document.querySelector("#chart svg.cv"), tip = document.querySelector("#chart .ch-tip");
    if (!svg || !tip || !chartModel) return;
    const xh = svg.querySelector(".ch-xh"), hd = svg.querySelector(".ch-hd"), ds = svg.dataset;
    const box = svg.getBoundingClientRect(), l = +ds.l, rr = +ds.r, t0 = +ds.t0, t1 = +ds.t1, lo = +ds.lo, hi = +ds.hi, top = +ds.top, bot = +ds.bot;
    const px = e.clientX - box.left;
    if (px < l - 4 || px > rr + 4) return chartLeave();
    const t = t0 + ((Math.min(Math.max(px, l), rr) - l) / (rr - l || 1)) * (t1 - t0);
    const P = chartModel.pts;
    let i = 0;
    for (let j = 1; j < P.length; j++) if (Math.abs(P[j][0] - t) < Math.abs(P[i][0] - t)) i = j;
    const p = P[i], x = l + (t1 === t0 ? 0 : (p[0] - t0) / (t1 - t0)) * (rr - l), y = top + (1 - (p[1] - lo) / (hi - lo)) * (bot - top);
    xh.setAttribute("x1", x); xh.setAttribute("x2", x); xh.setAttribute("visibility", "visible");
    hd.setAttribute("cx", x); hd.setAttribute("cy", y); hd.setAttribute("visibility", "visible");
    const ch = i ? p[1] - P[i - 1][1] : null;
    tip.innerHTML = `<span>${T.esc(T.when(p[0], nowS()))}</span><b>${T.money(p[1])}</b>`
      + (ch == null || chartModel.sim ? "" : `<span class="${T.tone(ch)}">${T.signed(ch)}</span>`);
    tip.hidden = false;
    const tw = tip.offsetWidth;
    tip.style.left = Math.max(0, Math.min(x + 10, rr - tw)) + "px";
    tip.style.top = Math.max(0, y - 34) + "px";
  }
  function chartLeave() {
    const svg = document.querySelector("#chart svg.cv"), tip = document.querySelector("#chart .ch-tip");
    if (svg) { svg.querySelector(".ch-xh").setAttribute("visibility", "hidden"); svg.querySelector(".ch-hd").setAttribute("visibility", "hidden"); }
    if (tip) tip.hidden = true;
  }

  // ---- the tape: open bets, the filter chips, the feed
  function renderTape() {
    const d = data;
    patch("tapeHead", `<h2>Tape</h2><span class="muted">Newest first</span>`);
    patch("openNow", Tape.openHtml(d, null));   // the countdowns are the tick's, so this redraws only when the bets change
    patch("filters", `<div class="chips" role="group" aria-label="Show on the tape">`
      + FILTERS.map(([k, l]) => `<button type="button" class="chip-f" data-filter="${k}" aria-pressed="${k === feedF}">${l}</button>`).join("")
      + (mkt ? `<button type="button" class="chip-m" data-clear-mkt aria-label="Show every market again">${T.esc(mkt)} only, clear</button>` : "")
      + `</div><div class="th" aria-hidden="true"><span>Time</span><span>Market</span><span>What</span><span>Price</span><span>Detail</span></div>`);
    const all = Tape.events(d), rows = Tape.filter(all, feedF, mkt), list = rows.slice(0, FEED_MAX);
    const first = known == null, fresh = new Set();
    if (first) list.slice(0, 6).forEach((e) => fresh.add(e.key));
    else list.forEach((e) => { if (!known.has(e.key)) fresh.add(e.key); });
    known = known || new Set();
    all.forEach((e) => known.add(e.key));
    let html;
    if (!list.length) html = `<p class="t-empty">${emptyFeed()}</p>`;
    else html = Tape.feedHtml(list, fresh)
      + `<p class="t-end">${rows.length > FEED_MAX ? `The newest ${FEED_MAX} of ${rows.length}. ` : ""}The tape keeps the last 200 decisions and the last 150 settled bets.</p>`;
    patchFeed(html, first);
  }
  function emptyFeed() {
    const m = mkt ? T.esc(mkt) + " " : "";
    if (feedF === "losses") return `No ${m}losses among the last 150 settled bets.`;
    if (feedF === "bets") return `No ${m}bets or results yet.`;
    return mkt ? `Nothing for ${T.esc(mkt)} on the tape yet.` : "Nothing on the tape yet.";
  }
  // New rows arrive at the top: while the viewer is scrolled down the feed, the row they're reading stays where it is.
  function patchFeed(html, first) {
    const box = $("feed");
    if (!box || shown.get("feed") === html) return;
    let anchor = null;
    if (box.scrollTop > 0) {
      const top = box.getBoundingClientRect().top;
      const row = [...box.querySelectorAll(".tr")].find((r) => r.getBoundingClientRect().bottom > top);
      if (row) anchor = { key: row.dataset.key, off: row.getBoundingClientRect().top - top };
    }
    patch("feed", html);
    if (anchor) {
      const row = box.querySelector(`.tr[data-key="${CSS.escape(anchor.key)}"]`);
      if (row) box.scrollTop += row.getBoundingClientRect().top - box.getBoundingClientRect().top - anchor.off;
    }
    // the first draw: the top rows come in one after another, oldest first (the page's one motion)
    const fr = [...box.querySelectorAll(".tr.fresh")];
    if (first) fr.forEach((el, i) => { el.style.animationDelay = (fr.length - 1 - i) * 90 + "ms"; });
  }

  // ---- every second: the countdowns, without a redraw
  function tick() {
    if (!data || !data.modes || !data.modes.length) return;
    const now = nowS();
    document.querySelectorAll("[data-close]").forEach((c) => {
      if (!c.dataset.close) return;
      const left = +c.dataset.close - now, text = left > 0 ? "in " + T.clock(left) : "settling";
      if (c.textContent !== text) c.textContent = text;
    });
    const cd = Tape.countdown(data, now, running), cls = "cd" + (cd.cls ? " " + cd.cls : "");
    document.querySelectorAll("[data-cd]").forEach((c) => {
      if (c.textContent !== cd.text) c.textContent = cd.text;
      if (c.className !== cls) c.className = cls;
    });
  }

  // ---------------------------------------------------------------- the live board, only while its tab shows
  async function pollBoard(force) {
    if (boardBusy || document.hidden || (tab !== "board" && !force)) return;
    boardBusy = true;
    try {
      const r = await fetch("/api/research/live", { cache: "no-store" });
      if (!r.ok) throw new Error("HTTP " + r.status);
      board = await r.json();
      boardErr = false;
    } catch (e) { boardErr = true; }
    boardBusy = false;
    if (tab === "board" && data) renderLeft();
  }

  // ---------------------------------------------------------------- the balance in the header, every 2 seconds
  const eyeIcon = (off) => `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">`
    + `<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>${off ? `<path d="M4 4l16 16"/>` : ""}</svg>`;
  function navBalance() {
    const ok = !!bal && bal.value != null, r = ok ? bal.pct : null, rp = r == null ? null : Math.round(r * 1000) / 10;
    patch("navBal", (ok && bal.paper ? `<span class="chip" title="The paper bot's simulated account, not real money">Paper</span>` : "")
      + (ok && !hideBal ? `<b class="nb-v">${T.money(bal.value)}</b>` : "")
      + (ok && r != null ? `<span class="nb-p ${T.tone(rp)}" title="Change since the start">${T.arrow(rp)}${T.spct(r)}</span>` : "")
      + `<button class="eye" type="button" data-bal aria-pressed="${hideBal}" aria-label="Hide balance" title="${hideBal ? "Show" : "Hide"} balance">${eyeIcon(hideBal)}</button>`);
    const nb = $("navBal");
    if (nb) nb.classList.toggle("stale", balStale);
  }
  async function pollBalance() {
    if (balBusy) return;                               // one request at a time: a slow answer never stacks up
    balBusy = true;
    try {
      const r = await fetch("/api/balance" + (mode ? "?mode=" + encodeURIComponent(mode) : ""), { cache: "no-store" });
      if (!r.ok) throw new Error("HTTP " + r.status);
      const b = await r.json();
      if (b.error) throw new Error(b.error);
      bal = b; balStale = false;
    } catch (e) { balStale = true; }
    balBusy = false;
    navBalance();
  }

  // ---------------------------------------------------------------- clicks and keys
  document.addEventListener("click", async (e) => {
    const t = e.target.closest("button");
    if (!t) return;
    if (t.dataset.mode) {
      if (t.dataset.mode === mode) return;
      mode = t.dataset.mode; store.set("mode", mode);
      known = null; mkt = null; chartSig = ""; bal = null;
      load(); pollBalance();
    } else if (t.dataset.page) {                       // the classic page's tabs: it opens on the one picked
      store.set("page", t.dataset.page);
      if (mode) store.set("mode", mode);
      location.href = "/";
    } else if (t.dataset.tab) {
      selectTab(t.dataset.tab);
    } else if (t.dataset.filter) {
      feedF = t.dataset.filter; store.set("tapeFilter", feedF);
      if (data) renderTape();
    } else if (t.dataset.mkt) {
      mkt = mkt === t.dataset.mkt ? null : t.dataset.mkt;
      if (data) { renderTape(); renderLeft(); }
    } else if ("clearMkt" in t.dataset) {
      mkt = null;
      if (data) { renderTape(); renderLeft(); }
    } else if (t.dataset.chart) {
      which = t.dataset.chart; store.set("tapeChart", which);
      if (data) renderChart();
    } else if (t.dataset.range) {
      const sim = which === "sim" && data && data.sim && data.sim.curve && data.sim.curve.length;
      if (sim) { simRange = pick(t.dataset.range, SIM_RANGES, "all"); store.set("tapeSimRange", simRange); }
      else { range = pick(t.dataset.range, RANGES, "all"); store.set("tapeRange", range); }
      if (data) renderChart();
    } else if ("bal" in t.dataset) {
      hideBal = !hideBal; store.set("hideBal", hideBal ? "1" : "0");   // one setting with the classic page
      navBalance();
      if (data && data.modes && data.modes.length) render();
    } else if ("halt" in t.dataset) {
      if (!armed) {
        armed = true; patch("haltTop", haltButton());
        armTimer = setTimeout(() => { armed = false; patch("haltTop", haltButton()); }, 4000);
        return;
      }
      clearTimeout(armTimer); armed = false;
      halting = Date.now(); patch("haltTop", haltButton());
      try { await fetch("/api/halt", { method: "POST" }); } catch (err) { /* the next reading says whether it took */ }
      halting = Date.now();                            // only a reading sent after the answer can clear it
      load();
      setTimeout(() => { if (halting) { halting = 0; if (data) patch("haltTop", haltButton()); } }, 10000);
    }
  });
  function selectTab(k) {
    if (!TABS.some((x) => x[0] === k)) return;
    tab = k; store.set("tapeTab", tab);
    renderLeft();
    if (tab === "board") pollBoard();
  }
  // The tabs: left and right arrows move between them, Home and End to the ends.
  document.addEventListener("keydown", (e) => {
    const t = e.target.closest && e.target.closest("#ltabs [data-tab]");
    if (!t) return;
    const i = TABS.findIndex((x) => x[0] === t.dataset.tab);
    const j = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: TABS.length - 1 }[e.key];
    if (j == null) return;
    e.preventDefault();
    selectTab(TABS[(j + TABS.length) % TABS.length][0]);
    const b = document.querySelector(`#ltabs [data-tab="${TABS[(j + TABS.length) % TABS.length][0]}"]`);
    if (b) b.focus();
  });
  const chartBox = $("chart");
  if (chartBox) {
    chartBox.addEventListener("pointermove", chartHover);
    chartBox.addEventListener("pointerleave", chartLeave);
  }
  // Redraw the chart when its box changes size, and the fill-rate panel when the left panel's width does.
  let lastSize = "", lastLeft = 0, sizeTimer = null;
  if (window.ResizeObserver) {
    if (chartBox) new ResizeObserver(() => {
      const s = Math.floor(chartBox.clientWidth) + "x" + Math.floor(chartBox.clientHeight);
      if (s === lastSize) return;
      lastSize = s;
      clearTimeout(sizeTimer);
      sizeTimer = setTimeout(() => { if (data && data.modes && data.modes.length) renderChart(); }, 60);
    }).observe(chartBox);
    const lp = $("lpanel");
    if (lp) new ResizeObserver(() => {
      const w = Math.floor(lp.clientWidth);
      if (w === lastLeft) return;
      lastLeft = w;
      if (tab === "fills" && data && data.modes && data.modes.length) renderLeft();
    }).observe(lp);
  } else addEventListener("resize", () => { if (data && data.modes && data.modes.length) { renderChart(); renderLeft(); } });

  load();
  setInterval(load, 1000);
  setInterval(tick, 1000);
  pollBalance();
  setInterval(pollBalance, 2000);
  pollBoard(true);                                     // once, so the grid knows each open market's asset class
  setInterval(pollBoard, 500);
})();
