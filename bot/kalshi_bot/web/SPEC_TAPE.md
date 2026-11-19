# The Tape page

A second dashboard page at `/tape`, served by `dashboard.py` beside the classic page at `/` (`dashboard.html`), which
it leaves unchanged. It shows everything the classic Live tab shows, in a dark trading-terminal layout, with the
bot's "tape" (every decision and every result, newest first) as the main panel. It was added on Nov 6, 2026.

## Files

All in `static/`, served by `dashboard.py` (the `/tape` route, and `ASSETS` for the scripts and styles):

| File | What |
|---|---|
| `tape.html` | markup, design tokens (CSS variables), the page shell and its layout |
| `tape_fmt.js` | shared formatters on `window.TapeFmt` (the same rules as dashboard.html's) |
| `tape.js`, `tape.css` | `window.Tape`: strip, bet grid, chart, tape feed, open bets, banners, nav, polling, wiring |
| `tape_panels.js`, `tape_panels.css` | `window.TapePanels`: live markets, orders, fill rate, by market, rules |

Load order in tape.html: `/tape_fmt.js`, `/tape_panels.js`, `/tape.js`. Styles: tokens inline in tape.html, then
`/tape.css`, `/tape_panels.css`. The tests are in `tests/test_tape_page.py`.

Every JS file loads in node with only `window = {}` defined (no `document`, no `fetch`): pure functions are put on
`window.Tape` / `window.TapePanels`, and anything touching the DOM, timers or the network runs only when
`typeof document !== "undefined"`. The tests load the files in node's `vm` and call the pure functions.

## Data

- `/api/state` (every 1 s; `?mode=` picks the account), built by `state()` in dashboard.py. Keys used: `mode, modes,
  live, env, now, clock, heartbeat, restartBot, halt, blackout, start, bankroll, unrealized, haltBase, limits, groups,
  wins, losses, need, winShare, fees, maxDrop, day, dayBets, staked, nextBet, curve, openBets, recentBets, bySeries,
  byPrice, decisions, orders, fills, fillsAll, fillsHour, fillsBySize, fillWindows, fillOff, fillsFast, errors, sim,
  kalshi` (kalshi only live). `decisions[].action` is "bet", "skip", or another word the bot logged (e.g. "halted");
  any other word is shown as is.
- `/api/research/live` (the live board; polled every 500 ms only while the Live markets tab is showing):
  `{now, stamp, live: {heartbeat, source, streamWhy, band, groups, markets: [...]}}`; each market has `ticker, series,
  group, label, yes_bid, yes_ask, last, favSide, favPrice, path [[minute, bid, ask]], ...`.
- `/api/balance` (every 2 s): `{value, gain, pct, paper, now, updated}` or `{error}`.
- `POST /api/halt` halts the bot. There is no resume from the page, ever.

How dashboard.html reads and words each of these is the reference (render, banners, scoreBlock, tick, positions,
method, fillTile/fillChart/fillsBlock, ordersBlock, more, boardBlock, the halt button and its click handler). The Tape
page keeps the same meaning and the same facts; its wording can be plainer.

## Layout (tape.html ids)

```
header.top   #brand  #modes (mode buttons + Live Research / Latency / Backtest / Classic view links)
             #navBal (balance chip)  #status (dot + text)  #haltTop (halt button)
#banners     (only when something needs attention)
#strip       one row of figures, scrolls sideways on a phone
main.main    .left  -> section.panel #lp: #ltabs (tab buttons) + #lpanel (the chosen tab's body)
                    -> section.panel #cp: #chartHead + #chart
             .right -> section.panel #tp: #tapeHead, #openNow, #filters, #feed
#foot
```

Left tabs, in order: **Every bet** (the grid; tape.js), **Live markets**, **Orders**, **Fill rate**, **By market**,
**Rules** (TapePanels). The chosen tab is kept in localStorage `tapeTab`.

## `window.Tape`: the pure functions the tests call

- `events(d)` -> array, newest first, of `{key, ts, kind, mkt, ticker, side, price, what, detail, pnl}`.
  Sources: `decisions` (kind = its action: "bet", "skip", or the other word), settled `recentBets` (kind "won" or
  "lost", ts = settled_ts, pnl), `errors` (kind "error"). A "bet" decision takes its fill from the matching
  `orders` row (same ticker) into `detail` ("filled 17 of 17", "got none: <error>"). `key` is unique and stable across
  refreshes. Skip reasons drop the leading "favorite at 61.0c is " so they read "outside 92-99.9c".
- `filter(events, f, mkt)` -> f is "all", "bets" (everything but skips) or "losses" (lost only); `mkt` (a symbol like
  "BTC") keeps only that market when given.
- `feedHtml(events, fresh)` -> the rows; every server string escaped; `fresh` is a Set of keys that get class "fresh".
- `openHtml(d, now)` -> the open bets pinned above the feed (market, side, price x contracts, value vs cost, settle
  time), or one quiet line when none: "No open bets. New ones are placed at minute 8 of each 15-minute window."
- `grid(d, now, board)` -> `{cols: [window start ts...], groups: [{group, rows: [{mkt, cells: [""|"won"|"lost"|"open"]}]}]}`.
  Columns run from the oldest bet in `recentBets`/`openBets` to the current window (at most the last 96 windows). Rows
  are every market in `bySeries`, `recentBets` or `openBets`, grouped crypto, metals, energy, then other
  (TapeFmt.groupOf, or the board's `group` when it has the market), A to Z within a group. Two bets in one cell: "lost"
  beats "open" beats "won".
- `gridHtml(g)` -> the grid; a market's name is a button (`data-mkt`) that filters the tape to it.
- `strip(d, opts)` -> array of `{label, value, sub}` (value/sub are HTML). opts: `{hideBal, now, running}`. Figures:
  account value (bot's books: bankroll + unrealized; with a live Kalshi account, `kalshi.value`), the simulation's
  value when `d.sim` exists (labelled "$1,000 simulation", its % change), today, since start, won and lost, win rate
  with "needs X", deepest fall, next bet, next entry (countdown). With hideBal the account's dollars give way to its
  % change.
- `countdown(d, now, running)` -> `{text, cls}`: "Halted" (down), "Not running" (down), "Blackout", "Entering now"
  (480 to 525 s into the window), else the time to the next minute-8 entry as "m:ss".
- `banners(d, now, running)` -> HTML for: halted (with `python bot.py --resume`), blackout, not running, cash outside
  Crypto & Commodities, book gap, low cash, restart note. The same facts as dashboard.html's render().
- `chartHtml(points, opts)` -> the account chart (area line, start baseline, last-value tag, red ticks where the value
  dropped by more than $1 between two points, i.e. a lost bet). Points are `[ts, value]`.

## `window.TapePanels`: each returns an HTML string

- `board(board, data, now, last)` -> live markets, one table per asset class (crypto, metals, energy, other), only the
  groups the bot trades (`data.groups`), favourite price highest first. Columns: market (links to Kalshi), favourite
  (side + price, with an "In range" tag while before minute 8 and inside the band), bid, ask, spread, this window's
  move, a small trend line. `last` is a Map the caller keeps (ticker -> last favourite); a changed price gets a class
  `fl-up` / `fl-down` / `fl-flip` and an arrow.
- `boardStatus(board, err, now)` -> `{kind: "on"|"warn"|"off"|"", text}`: Streaming, Polling, Stale (with age),
  Offline, Connecting; plus "minute N of 15".
- `orders(data)` -> the three summary lines (last hour, last 24 hours, all time), the orders table (placed, market,
  side and price, asked, filled, at the ask, result), fills by order size. Empty: it says how orders work.
- `fills(data, width)` -> the two tiles, the note, and the SVG chart with off-time bands.
- `markets(data)` -> by market (bets, won %, money bet, profit, profit per $1, coloured) and by price band (`byPrice`).
- `rules(data)` -> "What it buys", "How much", "How it orders", "When it stops", the stop-loss list, bot settings,
  next blackout, and the Kalshi account when `data.kalshi` exists.

## Look

A dark trading-terminal look. CSS variables defined in tape.html, and only these are used: `--abyss #050506` (page,
seams), `--panel #0e0e11`, `--raised #17171b`, `--slate 112,113,135` (used as `rgba(var(--slate), a)`), `--line`,
`--line-soft`, `--ink #fff`, `--ink-2 #cbcbd3`, `--muted #85869b`, `--win #00da80`, `--win-wash`, `--loss #ff3d5a`,
`--loss-wash`, `--warn #f0a63a`, `--warn-wash`, `--violet #5741d8`, `--violet-ink #9a8cff`, `--sans`, `--mono`, sizes
`--fs-10 --fs-12 --fs-14 --fs-16 --fs-20 --fs-28`, `--r-panel 2px`, `--r-btn 4px`, `--seam 4px`. Classes `.up` and
`.down` colour gains and losses; `.muted`, `.num` (mono, tabular figures) exist.

Panels butt together with 4 px dark seams; no shadows, no floating cards. Figures in tables are `--mono`. Words are
sentence case: no all-caps labels, no `text-transform: uppercase`, no letter-spaced labels. No meta strings joined with
" · " (commas or separate lines instead). No arrows on buttons or links. Every gain or loss carries a sign as well as a
colour. Keyboard focus is visible (tape.html sets `:focus-visible`). It respects `prefers-reduced-motion`. Phone width
(390 px) works with no sideways page scroll (a wide table scrolls inside its own box).

The page loads nothing from outside: no CDN, no web fonts, no remote images. Links to kalshi.com are fine.
