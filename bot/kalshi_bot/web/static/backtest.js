// The Backtest tab: the live bot's own rules, replayed on every window each market has ever had.
//
// Added on Oct 28, 2026, in three steps: the bot's exact rules tested since each market opened, then the same rules
// from $10,000 as well, then a bankroll chart like the Live tab's. Deliberately smaller than the Historical Research
// tab that left on Oct 15: no capital slider, no five versions, no four views.
//
// The account is the research backtest's "mine4liq": version 4's rules, which are the live bot's today, with each
// order filled only as far as Kalshi's trade tape says it could have been. Beside it, "mine4liq10k" is the same
// rules from $10,000. That pair is the point of showing two amounts at all: five times the money makes nowhere
// near five times the profit, because a 1.5% bet at $10,000 is more contracts than the book held.
//
// The chart is drawn in per cent grown rather than dollars. In dollars the $2,000 line is a flat squiggle along
// the bottom under the $10,000 one and the two shapes cannot be compared; from a shared zero they can.
//
// It borrows Live Research's header, figures, notes and table classes (.lr-*, from live_research.css) so the tabs
// read alike, and the page's own formatters (esc, money, signed, cents, count, pct, spct, tone). backtestHtml() is
// pure markup so the tests can run it in node; backtestView() draws what it has, then asks for anything newer.
(() => {
  "use strict";

  const STAMP_EVERY = 5000;   // ms: at most this often, ask whether the research file changed
  const THIN = 200;           // bets below which a market's figure is noise, not a finding
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const DASH = "—";
  // The three accounts the tab draws, smallest first, all of them what-ifs. mine4liq850 is a simulated $850 account,
  // the only one the bot's $700 stop bites on, which is why it is marked; the other two are $2,000 and $10,000.
  const ACCOUNTS = [{ id: "mine4liq850", line: "bt-l1", marked: true },
                    { id: "mine4liq", line: "bt-l2" },
                    { id: "mine4liq10k", line: "bt-l3" }];

  const R = { study: null, stamp: null, last: 0, busy: false, failed: false };

  // The month a market's first window fell in, read off the ISO string rather than through Date, so a UTC
  // midnight cannot slide back into the evening before in whatever zone the browser is in.
  const month = (iso) => {
    const m = /^(\d{4})-(\d{2})/.exec(String(iso || ""));
    return m && MONTHS[+m[2] - 1] ? `${MONTHS[+m[2] - 1]} ${m[1]}` : DASH;
  };
  // A signed figure to two places, signed the way the page signs money (U+2212 for minus, no sign for nothing).
  const sign2 = (v) => v == null ? DASH
    : (Math.abs(v) < 0.005 ? "" : v > 0 ? "+" : "−") + Math.abs(v).toFixed(2);
  // Cents of profit for every dollar staked. perBet is cents per $10 staked, so a tenth of it.
  const perDollar = (perBet) => perBet == null ? DASH : sign2(perBet / 10);

  const note = (b, s) => `<p class="lr-note"><b>${b}</b> ${s}</p>`;
  const cap = (w) => String(w || "").charAt(0).toUpperCase() + String(w || "").slice(1);
  // A starting amount as it should read: the cents only when there are any, so "$750.25" but "$10,000".
  const amt = (v) => money(v, v != null && Math.abs(v * 100 - Math.round(v / 1) * 100) > 0.5 ? 2 : 0);

  // The accounts this tab draws, in order, each with the strategy that describes it. Missing ones are left out, so
  // a strategies.json written before the $10,000 account existed still draws.
  function pick(study) {
    const rep = study && study.replay;
    if (!rep || !rep.runs) return null;
    for (const fills of ["live", "backtest"]) {
      for (const from of ["dec10", "jul18", "aug24"]) {
        const at = rep.runs[fills] && rep.runs[fills][from];
        if (!at || !at.mine4liq) continue;
        const strats = rep.strategies || [];
        return {
          fills,
          got: ACCOUNTS.filter((a) => at[a.id]).map((a) => ({ ...a, run: at[a.id],
            strat: strats.find((s) => s.id === a.id) || null })),
        };
      }
    }
    return null;
  }

  // Read the rules off the strategy the file describes, so the words cannot drift from what was replayed.
  function rulesLine(s) {
    const d = s || {};
    const floor = d.lo == null ? "92¢" : cents(d.lo);
    const bet = d.pct == null ? "1.5%" : pct(d.pct, 1);
    const win = d.windowCap == null ? "10%" : pct(d.windowCap, 0);
    const stop = d.floor == null ? "$700" : money(d.floor, 0);
    return `At minute 8 of every 15-minute window it buys the favourite when that favourite costs ${floor} or more, `
      + `stakes ${bet} of the account on each bet, caps a single window's bets together at ${win}, skips a market `
      + `whose ask sits 2¢ or more above its bid and one that has only just become the favourite, sits out Fed `
      + `decisions, and stops for good if the account ever falls to ${stop}.`;
  }

  // ------------------------------------------------------------------ the two amounts, side by side
  function accountRows(got) {
    return got.map(({ run, line, marked }) => {
      const profit = run.final == null || run.start == null ? null : run.final - run.start;
      return `<tr${marked ? ' class="lr-key"' : ""}><th scope="row"><span class="bt-key ${line}"></span>`
        + `${amt(run.start)}${marked ? ` <span class="lr-sub">starting amount</span>` : ""}</th>`
        + `<td class="lr-num">${money(run.final)}</td>`
        + `<td class="lr-num ${tone(profit)}"><b>${signed(profit)}</b></td>`
        + `<td class="lr-num ${tone(run.ret)}">${spct(run.ret)}</td>`
        + `<td class="lr-num ${tone(run.perBet)}">${perDollar(run.perBet)}</td>`
        + `<td class="lr-num">${pct(run.maxDD, 0)}</td>`
        + `<td class="lr-num ${run.floorHit ? "down" : "lr-muted"}">`
        + (run.floorHit ? month(run.floorHit) : "never") + `</td></tr>`;
    }).join("");
  }

  function accountTable(got) {
    return `<div class="lr-tw"><table class="lr-t"><thead><tr>`
      + `<th scope="col">Started with</th>`
      + `<th scope="col" class="lr-num">Ended with</th>`
      + `<th scope="col" class="lr-num">Profit</th>`
      + `<th scope="col" class="lr-num">Return</th>`
      + `<th scope="col" class="lr-num">Cents per dollar staked</th>`
      + `<th scope="col" class="lr-num">Deepest fall</th>`
      + `<th scope="col" class="lr-num">Hit the $700 stop</th>`
      + `</tr></thead><tbody>${accountRows(got)}</tbody></table></div>`;
  }

  // More money does not buy proportionally more profit, because the bet size is a share of the account while the
  // book's depth is not. How far short it falls is worked out from the two runs rather than written into the
  // sentence: an earlier version said "the profit barely moves", which was true of the data it was written
  // against and wrong three weeks later.
  function sizeNote(small, big, smallGain, bigGain) {
    if (!small || !big || !small.run.start || !smallGain || smallGain <= 0 || bigGain == null) return "";
    const moneyX = big.run.start / small.run.start, profitX = bigGain / smallGain;
    const times = (v) =>
      `${Math.abs(v - Math.round(v)) < 0.05 || v >= 10 ? Math.round(v) : v.toFixed(1)} times`;
    return note(`${amt(big.run.start)} is ${times(moneyX)} the money but ${times(profitX)} the profit`,
      `It turned ${signed(smallGain)} into ${signed(bigGain)}. The bet size is a share of the account while the `
      + `order book's depth is not, so at ${amt(big.run.start)} each order asks for far more contracts than `
      + `Kalshi's trade tape says the book held, and the part that cannot fill earns nothing. The return on the `
      + `money falls from ${spct(small.run.ret)} to ${spct(big.run.ret)}.`);
  }

  // What the $700 stop means at each amount on the page. It is a fixed number of dollars rather than a share of
  // the account, so the same stop is a different rule at each one: a fifth of the smallest and almost all of the
  // biggest. Built from the accounts actually drawn, so it can never name an amount the tab is not showing.
  function stopNote(got, strat) {
    const floor = strat && strat.floor;
    if (!floor || !got.length) return "";
    const said = got.filter((a) => a.run.start).map((a) =>
      `from ${amt(a.run.start)} a fall of ${pct((a.run.start - floor) / a.run.start, 0)}`);
    const hit = got.filter((a) => a.run.floorHit);
    return note(hit.length === 1 ? `Only ${amt(hit[0].run.start)} ever reaches your ${money(floor, 0)} stop`
      : `What your ${money(floor, 0)} stop means at each amount`,
      `The stop is a fixed ${money(floor, 0)} rather than a share of the account, so it is a different rule at `
      + `every starting amount: ${said.join(", ")}. The replays trade every window rather than halting, so the `
      + `last column is when the stop would first have fired, not when the account stopped.`);
  }

  // ------------------------------------------------------------------ the bankroll chart
  const VW = 960, PLOT_H = 300, L = 52, RG = 14, T = 16, B = 30, PW = VW - L - RG, PH = PLOT_H - T - B;
  const BAND_H = 11, BAND_GAP = 3, RIBBON_TOP = 6;   // the shaded band each asset class gets, under the plot
  const f1 = (v) => +v.toFixed(1);
  // A gridline step that gives 4 to 8 lines over the range, from the 1-2-5 ladder in percentage points.
  const STEPS = [1, 2, 5, 10, 20, 25, 50, 100, 200, 500];

  function scale(lo, hi) {
    const span = Math.max(hi - lo, 1);
    const step = STEPS.find((s) => span / s <= 7) || STEPS[STEPS.length - 1];
    return { lo: Math.floor(lo / step) * step, hi: Math.ceil(hi / step) * step, step };
  }

  // Where each asset class first traded, as rules down the plot. Kalshi listed them a long way apart -- crypto
  // from the first 15-minute market, metals in the summer, energy later still -- and the line changes shape when
  // one arrives, so without these there is nothing on the chart saying why. A class that was there from the very
  // first window gets no rule: it would sit on the axis and read as a border, so the caption names it instead.
  function marks(groups, xAt) {
    const dated = (groups || []).filter((g) => g.first).map((g) => ({ key: g.key, x: xAt(g.first) }))
      .filter((g) => g.x != null).sort((a, b) => a.x - b.x);
    const inside = dated.filter((g) => g.x > L + 2 && g.x < L + PW - 2);
    const atStart = dated.filter((g) => g.x <= L + 2).map((g) => g.key);
    let lastX = -Infinity, row = 0;
    const drawn = inside.map((g) => {
      row = g.x - lastX < 90 ? (row + 1) % 2 : 0;   // a label close behind the last one drops to a second row
      lastX = g.x;
      // near the right edge the label is hung off the left of its rule instead, or it runs out of the plot
      const near = g.x > L + PW - 8 - g.key.length * 7;
      return `<line class="bt-mark" x1="${g.x}" x2="${g.x}" y1="${T}" y2="${T + PH}"/>`
        + `<text class="bt-mlbl" x="${near ? g.x - 4 : g.x + 4}" y="${T + 11 + row * 13}"`
        + `${near ? ' text-anchor="end"' : ""}>${esc(g.key)}</text>`;
    }).join("");
    // The ribbon: one shaded band a class, from where it started to the right edge, in the order they arrived.
    // A rule says when one opened; the band is the stretch it was trading over, which is what you read along.
    const right = L + PW;
    const bands = dated.map((g, i) => {
      const x = Math.max(L, g.x), y = T + PH + RIBBON_TOP + i * (BAND_H + BAND_GAP);
      // A band that starts near the right edge is too short to hold its own name, so the name goes outside it,
      // to the left of where it begins. Otherwise the last class to be listed reads as "ener".
      const room = right - x > g.key.length * 6.5 + 10;
      return `<rect class="bt-band bt-bd${(i % 3) + 1}" x="${f1(x)}" y="${y}" width="${f1(right - x)}"`
        + ` height="${BAND_H}" rx="2"/>`
        + `<text class="bt-blbl" x="${f1(room ? x + 5 : x - 5)}" y="${y + BAND_H - 2.5}"`
        + `${room ? "" : ' text-anchor="end"'}>${esc(g.key)}</text>`;
    }).join("");
    const height = dated.length ? RIBBON_TOP + dated.length * (BAND_H + BAND_GAP) : 0;
    return { drawn, atStart, bands, height, inside: inside.map((g) => g.key),
             all: dated.map((g) => g.key) };
  }

  function chart(got, rep) {
    // each account's curve as per cent grown from its own start, so both lines begin at zero
    const lines = got.map(({ run, line, marked }) => ({
      line,
      marked,
      start: run.start,
      pts: (run.curve || []).map((v, i) => v == null || !run.start ? null : [i, (v / run.start - 1) * 100]),
    })).filter((l) => l.pts.some(Boolean));
    if (!lines.length) return "";
    const all = lines.flatMap((l) => l.pts.filter(Boolean).map((p) => p[1]));
    const n = Math.max(...lines.map((l) => l.pts.length));
    const y = scale(Math.min(0, ...all), Math.max(0, ...all));
    const yOf = (v) => f1(T + PH * (1 - (v - y.lo) / (y.hi - y.lo)));
    const xOf = (i) => f1(L + PW * (n < 2 ? 0.5 : i / (n - 1)));
    // an ISO date to a position along the plot, through the same index-to-x the curves use
    const t0ms = Date.parse(rep && rep.t0), stepMs = ((rep && rep.step) || 1) * 3600e3;
    const xAt = (iso) => {
      const at = Date.parse(iso);
      if (!isFinite(t0ms) || !isFinite(at) || n < 2) return null;
      const i = (at - t0ms) / stepMs;
      return i < 0 || i > n - 1 ? null : xOf(i);
    };
    const mk = marks(got[0] && got[0].run.byGroup, xAt);
    const vh = PLOT_H + mk.height;   // the chart grows downwards to make room for the ribbon
    const grid = [];
    for (let v = y.lo; v <= y.hi + 1e-9; v += y.step) {
      grid.push(`<line class="${Math.abs(v) < 1e-9 ? "bt-zero" : "bt-grid"}" x1="${L}" x2="${L + PW}"`
        + ` y1="${yOf(v)}" y2="${yOf(v)}"/>`
        + `<text class="bt-ax" x="${L - 7}" y="${yOf(v) + 4}" text-anchor="end">${v > 0 ? "+" : ""}${v}%</text>`);
    }
    const paths = lines.map((l) => {
      // a gap in the curve (before the account started, or once it broke) breaks the line rather than bridging it
      const runs = [];
      let cur = [];
      for (const p of l.pts) {
        if (p) cur.push(`${xOf(p[0])},${yOf(p[1])}`);
        else if (cur.length) { runs.push(cur); cur = []; }
      }
      if (cur.length) runs.push(cur);
      return runs.map((r) => `<polyline class="bt-line ${l.line}" points="${r.join(" ")}"/>`).join("");
    }).join("");
    // month labels along the bottom, from the replay's own start, at most one per 70 units
    const t0 = Date.parse(rep && rep.t0) || null, step = (rep && rep.step) || 1;
    let monthMarks = "", lastX = -Infinity;
    if (t0) {
      let seen = "";
      for (let i = 0; i < n; i++) {
        const d = new Date(t0 + i * step * 3600e3), key = `${d.getUTCFullYear()}-${d.getUTCMonth()}`;
        if (key === seen) continue;
        seen = key;
        const x = xOf(i);
        if (x - lastX < 70 || x > L + PW - 20) continue;
        lastX = x;
        monthMarks += `<text class="bt-ax" x="${x}" y="${vh - 9}" text-anchor="middle">`
          + `${MONTHS[d.getUTCMonth()]}${d.getUTCMonth() === 0 ? " " + d.getUTCFullYear() : ""}</text>`;
      }
    }
    const names = lines.map((l) => amt(l.start)).join(" and ");
    const said = `How ${names} grew, in per cent, over every window the replay covers.`;
    const key = lines.map((l) => `<span class="bt-ki"><span class="bt-key ${l.line}"></span>`
      + `${amt(l.start)}${l.marked ? " (starting amount)" : ""}</span>`).join("");
    return `<figure class="bt-fig"><div class="bt-scroll">`
      + `<svg class="bt-chart" viewBox="0 0 ${VW} ${vh}" role="img" aria-label="${esc(said)}">`
      + `<rect class="bt-plot" x="${L}" y="${T}" width="${PW}" height="${PH}"/>`
      + `${grid.join("")}${mk.drawn}${paths}${mk.bands}${monthMarks}</svg></div>`
      + `<div class="bt-keys">${key}</div>`
      + `<figcaption class="lr-note">Each line is one account's value, as a percentage of what it started with, so`
      + ` the two can be compared on one scale. The heavier line across the middle is where each of them started:`
      + ` below it the account is down on its starting amount. Dollars would put the smaller account in a flat squiggle`
      + ` under the bigger one.`
      + (mk.all.length ? ` The shaded bands under it are the stretch each kind of market was trading over, and`
        + ` the upright rules are where Kalshi started listing a new one: ` : "")
      + (mk.inside.length ? ``
        + `${mk.inside.map((k) => esc(k)).join(", ")}`
        + (mk.atStart.length ? `. ${mk.atStart.map((k) => esc(cap(k))).join(" and ")} had been trading from the `
          + `first window, so it has no rule.` : `.`) : "")
      + `</figcaption></figure>`;
  }

  // ------------------------------------------------------------------ per market
  function marketRows(rows) {
    return rows.slice().sort((a, b) => (b.n || 0) - (a.n || 0)).map((g) => {
      const thin = (g.n || 0) < THIN;
      const share = g.staked ? g.pnl / g.staked : null;
      return `<tr><th scope="row">${esc(g.key)}</th>`
        + `<td class="lr-num">${month(g.first)}</td>`
        + `<td class="lr-num">${count(g.n || 0)}</td>`
        + `<td class="lr-num">${g.n ? pct((g.wins || 0) / g.n, 1) : DASH}</td>`
        + `<td class="lr-num ${thin ? "lr-muted" : tone(share)}">`
        + (thin ? `<span class="lr-sub">too few to tell</span>`
          : `<b>${g.staked ? sign2(g.pnl / g.staked * 100) : DASH}</b>`) + `</td></tr>`;
    }).join("");
  }

  // ------------------------------------------------------------------ the whole tab
  // Every word it shows is built here, the empty states included, so the tests can read all of them without a
  // browser. `failed` is true when the last read of the research data did not come back.
  window.backtestHtml = (study, failed) => {
    const head = (lede) => `<header class="lr-head"><div class="lr-title">`
      + `<h2>Your rules, on every window each market has had</h2><p>${lede}</p></div></header>`;
    if (!study) {
      return failed
        ? head("Can't read the research data.")
          + note("Can't read the research data", "The dashboard answered, but <code>/api/research</code> did not.")
        : head("Loading the backtest.") + note("Loading", "Reading the replay.");
    }
    const picked = pick(study);
    if (!picked) {
      return head("The replay hasn't been run against this data yet.")
        + note("No backtest yet", "Run <code>python strategies_backtest.py</code> in "
          + "<code>research/kalshi_15min</code>, then reload this page.");
    }
    const { got, fills } = picked;
    // Looked up by id, not by position: the order on the page is smallest amount first, but the note below
    // compares the $2,000 and $10,000 what-ifs, and the prose and the per-market table come off whichever
    // account is really there -- the $850 account when the backtest has it, else the $2,000.
    const by = (id) => got.find((a) => a.id === id) || null;
    const base = by("mine4liq850") || got[0];
    const small = by("mine4liq"), big = by("mine4liq10k");
    const rows = base.run.bySeries || [];
    const thin = rows.filter((g) => (g.n || 0) < THIN).length;
    const gain = (a) => a && a.run.final != null && a.run.start != null ? a.run.final - a.run.start : null;
    const bigGain = gain(big), baseGain = gain(small);
    return head(`Every 15-minute window the data store holds — ${count(base.run.bets || 0)} bets — with `
      + `each market counted from its own first window rather than from one shared date. Kalshi listed them months `
      + `apart, and a shared start date flatters the newest ones.`)
      + `<p class="lr-lede"><b>The rules:</b> ${esc((base.strat && base.strat.name) || "the live bot's rules")}. `
      + `${rulesLine(base.strat)}</p>`
      + `<p class="lr-lede"><b>How the fills are modelled:</b> each order is filled only as far as Kalshi's trade `
      + `tape says the order book really offered at that moment, so these are the realistic figures rather than the `
      + `flattering ones. The live bot bids a cent over the ask it sees, which lifts how much of an order fills; `
      + `this replay fills at the ask, so that extra cent is not counted here. `
      + (fills === "live" ? "" : "These fills are the recorded ask rather than the tape. ")
      + `</p>`
      + accountTable(got)
      + sizeNote(small, big, baseGain, bigGain)
      + stopNote(got, base.strat)
      + chart(got, study.replay)
      + `<p class="lr-lede"><b>Each market on its own</b>, from the ${amt(base.run.start)} account.</p>`
      + `<div class="lr-tw"><table class="lr-t"><thead><tr>`
      + `<th scope="col">Market</th>`
      + `<th scope="col" class="lr-num">First window</th>`
      + `<th scope="col" class="lr-num">Bets</th>`
      + `<th scope="col" class="lr-num">Won</th>`
      + `<th scope="col" class="lr-num">Cents per dollar staked</th>`
      + `</tr></thead><tbody>`
      + (marketRows(rows) || `<tr><td colspan="5">No bets in this replay.</td></tr>`)
      + `</tbody></table></div>`
      + (thin ? note("A thin market is not a finding",
        `${count(thin)} of these markets ${thin === 1 ? "has" : "have"} fewer than ${count(THIN)} bets, so no `
        + `figure is shown for ${thin === 1 ? "it" : "them"}. A number to two decimal places out of a handful of `
        + `bets reads like a result and is mostly luck.`) : "");
  };

  // ------------------------------------------------------------------ the data
  const getJSON = async (url) => {
    const r = await fetch(url, { cache: "no-store" });
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  };

  // The study runs to megabytes and only changes when the backtest is run again, so the small stamp route is
  // asked first and the study refetched only when it has moved. A server without that route answers 404, and
  // then the study is fetched once, while there is none on screen.
  async function refresh() {
    if (R.busy) return;
    R.busy = true;
    try {
      const stamp = await getJSON("/api/research/stamp").then((x) => x && x.stamp, () => null);
      if (!R.study || (stamp != null && stamp !== R.stamp)) {
        const study = await getJSON("/api/research");
        R.study = study;
        R.stamp = stamp == null ? study.stamp : stamp;
      }
      R.failed = false;
    } catch (e) {
      R.failed = true;            // whatever was last drawn stays on screen
    }
    R.busy = false;
    R.last = Date.now();
    draw();
  }

  const draw = () => patch("backtest", window.backtestHtml(R.study, R.failed));

  // The page calls this on its own refresh while this tab is open, so the tab keeps no timer of its own.
  window.backtestView = () => {
    draw();
    if (Date.now() - R.last > STAMP_EVERY) refresh();
  };

  if (page === "backtest") window.backtestView();   // the page had already drawn when this script arrived
})();
