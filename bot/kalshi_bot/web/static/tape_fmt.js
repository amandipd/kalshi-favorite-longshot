// The Tape page's shared formatting helpers (Nov 6, 2026): the same rules as dashboard.html's own, so a number reads the
// same on both pages. Loaded first by tape.html; tape_panels.js and tape.js build on window.TapeFmt. Nothing here
// touches the page, so node can load it for the tests (test_tape_page.py).
(function (root) {
  "use strict";
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const nf = (v, dp = 2) => Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: dp, maximumFractionDigits: dp });
  const zero = (v, dp = 2) => Math.abs(v) < 0.5 * Math.pow(10, -dp);            // rounds to nothing: no sign, no colour
  const money = (v, dp = 2) => v == null ? "—" : (v < 0 && !zero(v, dp) ? "−$" : "$") + nf(v, dp);
  const signed = (v, dp = 2) => v == null ? "—" : (zero(v, dp) ? "" : v > 0 ? "+" : "−") + "$" + nf(v, dp);
  const pct = (v, dp = 1) => v == null ? "—" : (v * 100).toFixed(dp) + "%";
  const spct = (v, dp = 1) => v == null ? "—" : (zero(v * 100, dp) ? "" : v > 0 ? "+" : "−") + Math.abs(v * 100).toFixed(dp) + "%";
  const limitPct = (v) => v == null ? "—" : +(v * 100).toFixed(1) + "%";   // a limit as set: 1.5%, 10%
  const tone = (v) => v == null || zero(v) ? "" : v > 0 ? "up" : "down";      // the CSS classes .up and .down
  const arrow = (v) => tone(v) === "up" ? "▲ " : tone(v) === "down" ? "▼ " : "";
  const cents = (p) => p == null ? "—" : (Math.abs(p * 100 - Math.round(p * 100)) < 0.05 ? String(Math.round(p * 100)) : (p * 100).toFixed(1)) + "¢";
  const hhmm = (t) => new Date(t * 1000).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  const hms = (t) => new Date(t * 1000).toLocaleTimeString([], { hour: "numeric", minute: "2-digit", second: "2-digit" });
  const day = (t) => new Date(t * 1000).toLocaleDateString([], { month: "short", day: "numeric" });
  const when = (t, now) => {    // today's times plain; other days with the date first
    const d = new Date(t * 1000), today = now == null ? new Date() : new Date(now * 1000);
    return d.toDateString() === today.toDateString() ? hhmm(t) : day(t) + " " + hhmm(t);
  };
  const count = (n) => Number(n).toLocaleString("en-US");
  const clock = (s) => `${Math.floor(Math.max(0, s) / 60)}:${String(Math.floor(Math.max(0, s) % 60)).padStart(2, "0")}`;
  const sym = (series) => String(series || "").replace(/^KX/, "").replace(/15M$/, "");   // KXBTC15M -> BTC
  const symOf = (ticker) => sym(String(ticker || "").split("-")[0]);
  // The 15-minute window's page on Kalshi: /markets/{series}/{slug}/{event}; Kalshi fixes the slug if it's off.
  const kalshiUrl = (ticker) => {
    const p = String(ticker || "").split("-"), s = p[0].toLowerCase();
    return p.length < 2 ? `https://kalshi.com/markets/${s}` : `https://kalshi.com/markets/${s}/${s}/${p.slice(0, 2).join("-").toLowerCase()}`;
  };
  const label = (m) => ({ "live-prod": "Live", "live-demo": "Demo", "dry-prod": "Paper" })[m] || m;
  // Which asset class a market is in. The live board says so for the markets open now; this covers the rest.
  const GROUPS = { crypto: "Crypto", metals: "Metals", energy: "Energy" };
  const CLASS = {
    BTC: "crypto", ETH: "crypto", SOL: "crypto", XRP: "crypto", DOGE: "crypto", BNB: "crypto", HYPE: "crypto", NEAR: "crypto", ZEC: "crypto",
    GOLD: "metals", SILVER: "metals", COPPER: "metals", PLATINUM: "metals", PALLADIUM: "metals",
    WTI: "energy", BRENT: "energy", NATGAS: "energy",
  };
  const groupOf = (s) => CLASS[s] || "other";
  // The bot's limits, only until the server says what it enforces (state()'s limits), as dashboard.html's LIMITS.
  const LIMITS = { betPct: 0.015, windowPct: 0.10, ordersPerWindow: 20, ordersPerDay: 600, minCash: 67, dayDrop: 0.35, halfStart: 0.5,
                   windowLosses: 8, settleLag: 1800, persist: 300, orderErrors: 3,
                   minute: 8, lo: 0.92, hi: 0.999, limitUp: 0, shadowUp: 0.01, grace: 45, spreadMax: 0.02, lateMid: 0.50, jump: 0.10, orderDeadline: 60, bookMaxAge: 15,
                   restingEvery: 15, orderConnect: 3.05, orderAnswer: 5 };
  root.TapeFmt = { esc, nf, zero, money, signed, pct, spct, limitPct, tone, arrow, cents, hhmm, hms, day, when, count, clock, sym, symOf,
                   kalshiUrl, label, GROUPS, CLASS, groupOf, LIMITS };
})(typeof window !== "undefined" ? window : globalThis);
