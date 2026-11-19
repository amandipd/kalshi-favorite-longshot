# Kalshi favourites bot

A trading bot for Kalshi's 15-minute markets. At minute 8 of every window it buys each favourite priced 92¢ to 99.9¢
in crypto, metals and energy markets, unless the favourite shows one of two warning signs (below). Each bet is 1.5% of
the bankroll, a window's bets together at most 10%, in whole contracts. The lowest price was raised from 90¢ on
Oct 14, 2026. A set of automatic halts stops it when something looks wrong.

It traded real money from Sep 28 to Nov 3, 2026, and on paper after that. It is no longer running. The research
behind the rule is in [`research/kalshi_15min`](../research/kalshi_15min/) in this repository.

The code is published as it ran. Nothing here is advice to trade, and the edge it was built on is not proven (see the
caveats below).

## What it buys

At the end of minute 8 it buys a favourite only if all of these hold:

| Check | Bound |
|---|---|
| Market group | crypto, metals or energy (Coin Race and FX spreads eat the edge) |
| Price | the favourite costs 92¢ to 99.9¢ at its ask (raised from 90¢ on Oct 14, 2026: live, the 90¢ to 92¢ favourites lost 31 of 217 bets against about 16 expected, while every dearer band made money; `research/kalshi_15min/live_losses.py`) |
| Spread | its ask is under 2¢ above its bid |
| Not late | its mid price was above 50¢ at minute 6 and at minute 7 |
| No jump | its mid price rose less than 10¢ during minute 8 |

The last three are the research's "skip both" rule (`findings.py`, `strategies_backtest.py`). The minute 6 and 7
prices come from Kalshi's one-minute candles, read the way the research read them. A minute with no quote can't
trigger a check, as in the backtest, but if the candles can't be read at all, or a market has none, it skips the bet
rather than trade unchecked. The 10% window cap counts only the favourites that pass.

Since Oct 14, 2026 every window is a fast entry (`fast_entry.py`): the bot reads the window's minute prices at 7.5
minutes, and at minute 8 exactly, on Kalshi's clock, it reads every order book and sends the window's orders together.

Read the research's caveats before putting money in:

- **The edge is not proven.** With live-like fills, the rule made +4.5¢ per $10 bet over every window from Dec 10,
  2025 to Oct 8, 2026 (95% range +1.8¢ to +7.3¢). But over Dec 10 to Jul 17, the seven months no rule was chosen on,
  it made only +1.7¢ (from -2.5¢ to +5.8¢), and its months ranged from -7.2¢ to +10.1¢.
- **Small accounts pay more.** Fees are rounded up on every order and contracts round down, which costs a small
  account noticeably more per dollar than a larger one.
- **Orders don't always fill.** The backtests fill every order in full at the recorded ask. Live, other traders often
  took the ask before the bot's order landed (`research/kalshi_15min/liquidity.py`).

## Layout

```
bot/
  bot.py                 starts the bot: python bot.py [options]
  dashboard.py           starts the dashboard: python dashboard.py
  kalshi_bot/            the package
    bot.py               the trading loop (class Bot), its halts and its command line
    market.py            pure helpers: times, market groups, the taker fee, order books, candles, order bodies
    ledger.py            the SQLite ledger each account keeps in state/
    kalshi.py            a small client for Kalshi's Trade API v2 (request signing, retries, endpoints)
    fast_entry.py        fast entry: wake-ups, Kalshi's clock, sending a window's orders together, the paper reader
    notify.py            phone alerts through ntfy
    watchdog.py          a dead man's switch: pings healthchecks.io while the loop runs
    stall_alert.py       an alert when the bot stops looking at markets while still looking alive
    web/
      dashboard.py       the dashboard's server: JSON from the bot's records, and the pages
      latency.py         the Latency tab's report
      SPEC_TAPE.md       notes on the Tape page
      static/            dashboard.html, tape.html and their JavaScript and CSS
  tests/                 the tests (pytest; the page tests run the JavaScript in node)
  deploy/                systemd units with placeholder paths, safe_restart.py, probe_latency.py
  requirements.txt
  .env.example           copy to .env and fill in
```

`state/` (the ledgers, the halt file, logs), `.env` and `keys/` live in this `bot/` folder and are ignored by git.

## Setup

Everything below runs from this `bot/` folder, with Python 3.11 or newer.

1. `pip install -r requirements.txt`
2. For a live run, create an API key at [kalshi.com/account/profile](https://kalshi.com/account/profile) under
   **API Keys**. Save the private key file right away, since Kalshi won't show it again, and put it in `keys/` in
   this folder or anywhere outside the repository. The demo exchange has its own accounts and keys: make one on
   [demo.kalshi.co](https://demo.kalshi.co) the same way.
3. Copy `.env.example` to `.env` and fill it in. A dry run needs no key at all.

## Running it

```bash
python bot.py --env prod                # dry run on real prices: no account needed, never sends an order
python bot.py --check                   # does the key work? shows the balance, places nothing
python bot.py --live                    # real orders on demo (KALSHI_ENV=demo): watch a few windows
python bot.py --live --env prod         # real money: asks you to type LIVE first
python bot.py --paper                   # paper account: ignores halts, runs until it's broke

python bot.py --halt "reason"           # stop every mode
python bot.py --resume                  # start again
python bot.py --status                  # every mode's account, and whether it's halted

python bot.py --fund-crypto [DOLLARS]   # move cash from Kalshi's Default section to Crypto & Commodities
python bot.py --rebase                  # restart the live books from the cash now in Crypto & Commodities
```

`python -m kalshi_bot` is the same as `python bot.py`. Without `--live` the bot reads real prices, simulates its fills
on a simulated $1,000 account and never sends an order. `--live` needs `KALSHI_API_KEY_ID` and
`KALSHI_PRIVATE_KEY_PATH` in `.env`; `KALSHI_ENV` (or `--env`) picks Kalshi's demo exchange, which uses fake money, or
prod.

The bot only bets what its own books say it has, starting at the account's balance on its first live run. Kalshi keeps
each section's cash apart and these markets can only use Crypto & Commodities, so money you add changes nothing until
you move it there (`--fund-crypto`) and restart the books from it (`--rebase --env prod`). A rebase keeps the history,
counted as if the new money had been there from the start, and won't run while a bet is open.

Only one bot can trade on a machine at a time, in any mode. While its loop runs it holds localhost port 47864, and a
second `python bot.py` finds the port taken and stops at once, before it touches the ledger. The commands that don't
trade (`--status`, `--halt`, `--resume`, `--check`, `--fund-crypto`, `--rebase`) still work while it runs.

## The dashboard

```bash
python dashboard.py                     # http://localhost:8080
python dashboard.py --lan               # also reachable from other machines on your network
python dashboard.py --port 9000         # another port
```

`python -m kalshi_bot.web` is the same. The dashboard only reads the bot's records, so starting or stopping it never
affects the bot. It can halt the bot but never resume it, and only its own page can press the halt button: any web
page can send a request to localhost, and the dashboard refuses one from another site.

Its tabs: **Live** (the account, its chart, open bets, orders and fill rates, the market board), **Live Research**
(experiments on the real bot as they ran), **Latency** (how soon after minute 8 the orders reached Kalshi) and
**Backtest** (the bot's rules replayed on every window each market has had, read from the research outputs,
which `research/kalshi_15min/strategies_backtest.py` rebuilds; they are not included here, so the tab starts empty).
A second page at `/tape` shows the Live tab in a dark trading-terminal layout (`kalshi_bot/web/SPEC_TAPE.md`).

The market board streams prices from Kalshi's WebSocket when `websocket-client` is installed and `.env` has a prod
key (Kalshi's WebSocket asks for a key even for public data; the dashboard only reads with it). Otherwise it polls
Kalshi once a second.

The Live Research tab follows experiments on the real bot as they run, one card each. The first was the +1¢ limit:
from Oct 12 to Oct 20, 2026 it ran on paper, measuring after each real order what a limit 1¢ higher would have bought
on top of what really filled. The extra cent took the contracts filled from about 60% to 96%, so since Oct 20 the limit
is live (`LIMIT_UP` in `kalshi_bot/bot.py` is 0.01) and the paper card keeps its final result. The second is fast entry
on paper: each real order paired with what an order sent at minute 8 exactly would have bought.

## Safety

- **Dry run by default.** Without `--live` it reads real prices and simulates fills, and never sends an order.
- **Demo first.** `KALSHI_ENV=demo` sends real orders to Kalshi's demo exchange, which uses fake money. Prod needs
  `KALSHI_ENV=prod` (or `--env prod`) and typing `LIVE` at a prompt.
- **Pays at most 1¢ over the ask it saw.** Every order is an immediate-or-cancel (IOC) limit order: it fills what it
  can at once and the rest is cancelled, so nothing waits on the book, and its limit is the most it will pay a
  contract. That limit is 1¢ over the ask it saw, at most 99.9¢, and it takes the cheapest offers first. By the time
  an order lands the ask has often ticked up: with the limit at the ask itself only about 60% of the contracts filled.
  The extra cent ran on paper first, Oct 12 to 20, 2026, with no money on it. It still sizes the order off the ask it
  saw, and its cash checks count every contract at the limit.
- **A fill over the limit halts everything.** So does a fill larger than the order.
- **Hard caps.** At most 20 orders a window and 600 a day, whatever the sizing says.
- **One order per market, ever.** The order ID comes from the market's ticker, and the bot checks its own records,
  so a restart can't double up.
- **Orders are never retried.** A retry could place the same order twice. After a network error it records whatever
  filled on that market before counting the order as failed.
- **No bet goes unrecorded.** Every minute (live) it checks Kalshi's record of its orders over the last 2 hours, and a
  day back after a start. An order of its own that bought contracts but isn't in its records is added, so the P&L,
  the window cap and the halts count it. Until that record has been read once since a start, it enters no window.
- **A locked ledger isn't a crash.** If another program holds its database (antivirus, a backup or a sync app), each
  read or save waits up to 30 s, and what a step couldn't save is saved by the next one. Locked for 2 minutes running,
  it halts.
- **Your key stays on your machine.** It's read from a file only the bot opens, and `.env`, `*.pem`, `keys/` and
  `state/` are all ignored by git.

## How long anything may take

The research tested prices at minute 8. Later prices are a different bet, and a slow or broken connection to Kalshi
must never leave an order out there. So every step has a limit:

| What | Limit | Then |
|---|---|---|
| Entering | only from the end of minute 8 to 45 s after | the window is skipped |
| Sending an order | no later than 60 s after minute 8 ends | the bet is skipped as too late |
| The order book it's priced on | read at most 15 s before the order | the bet is skipped |
| An order request | 3 s to connect, 5 s for Kalshi's answer, never retried | it reads that market's fills to see what happened |
| An order left resting | every 15 s (live) it looks for its own resting orders and cancels them | it halts |
| Kalshi's exchange status unreadable | no new bets while it can't confirm Kalshi is trading | after 5 minutes, it halts |
| Its own database locked | each read or save waits up to 30 s | after 2 minutes locked, it halts |

## Halts

A halt stops every mode (dry run, demo, prod) from placing orders until `python bot.py --resume`. Open bets still
settle, and each bet it would have placed is logged as `halted`. The one exception is the paper account (`--paper`),
which ignores halts and never triggers one.

| Halt when | Why that level |
|---|---|
| You run `--halt` | the kill switch ([FIA][fia]; [Knight Capital][knight] lost $440M in 45 minutes without one) |
| The account is worth half its start | cost nothing in the backtest while the edge held; keeps about half if the edge is gone |
| The real-money account is worth $700 or less (`HALT_FLOOR`) | a fixed stop for real money only; `--resume` alone doesn't clear it, only money added plus `--rebase` does |
| 8 or more bets lose in one window | the worst window on record, the Sep 16 Fed decision, lost 11; no other lost more than 7 |
| It falls 35% within 24 hours | just past the worst 24 hours on record for this rule at its own sizing |
| A bet is unsettled 30 minutes after its market closed, for 5 minutes | Kalshi settles in about 8 seconds; the slowest seen was 6 minutes |
| Kalshi pauses trading outside its Thursday 3 to 5 am ET maintenance, for 5 minutes | checked every minute at `GET /exchange/status` ([Kalshi][kd]) |
| Kalshi can't be reached, for 5 minutes | an outage that long needs a person to look |
| 3 windows running list no markets at all | an empty listing looks like a quiet hour; three in a row is a fault |
| One of its orders is found resting on the book | immediate-or-cancel orders never rest |
| 3 orders fail in a row, or a fill comes back worse than the order | something is wrong with the account, the key or the exchange |
| Its database stays locked by another program for 2 minutes | a lock that long needs a person to find the program holding it |

The halt file, `state/halt.json`, is written whole and then swapped in, so a crash mid-write never leaves half of one.
One that can't be read anyway still counts as a halt, and `--resume` removes it.

Ordinary losing streaks don't halt it. In the history, losses didn't come in runs, and stops that pause after ordinary
losses only gave up profit, as [Kaminski & Lo][kl] predict when losses don't persist.

**Blackouts:** no new orders from 2:00 to 3:30 pm ET on Fed decision days. Add new dates from the [FOMC calendar][fomc]
to `BLACKOUTS` in `kalshi_bot/bot.py`; `tests/test_blackouts.py` fails once the last one is under 60 days away.

## Alerts and the watchdog

`python -m kalshi_bot.notify` sends a message to your phone through [ntfy][ntfy] when one of the bot's bets loses. It
can also send halts, stops and starts: `ALERTS` in `kalshi_bot/notify.py` picks which. It only reads the bot's
records, never writes to them, and remembers what it sent in `state/notify.json`, so nothing arrives twice.

1. Install the ntfy app and subscribe to a new topic. On ntfy.sh's free server the topic name is the only lock, so
   make it long and random: `python -c "import secrets; print('kalshi-' + secrets.token_urlsafe(18))"`.
2. Put it in `.env` as `NTFY_TOPIC=...`. `NTFY_SERVER` names another ntfy server.

```bash
python -m kalshi_bot.notify --test      # send one test message and stop
python -m kalshi_bot.notify             # keep checking every 5 seconds; Ctrl+C stops it
```

`python -m kalshi_bot.watchdog` pings the healthchecks.io address in `HEALTHCHECK_URL` while the bot's heartbeat is
fresh, and its `/fail` address otherwise; run it once a minute from a timer. `python -m kalshi_bot.stall_alert` sends an
ntfy alert when the bot stops looking at markets while still looking alive; run it every 10 minutes. `deploy/` has
systemd units for all of these (see `deploy/README.md`).

## Tests

```bash
python -m pytest -q                     # from this bot/ folder: about 3,350 tests, a few minutes
```

They run against a fake Kalshi, a stand-in for ntfy and a temporary state folder, and never touch the network or an
account. `tests/conftest.py` points every test at a throwaway state folder even if it sets none, and fails the run if a
`halt.json` turns up in the real one. The page tests load the dashboard's JavaScript in node and skip themselves
without it. The property tests use [Hypothesis][hyp].

| Files | Cover |
|---|---|
| `test_kalshi.py` | key loading, request signing, retries and backoff, that an order is never sent twice, every endpoint |
| `test_units.py`, `test_fuzz.py` | fees, sizing, `.env`, market grouping, the database, the halt file, blackouts, order books and orders; property tests of the pure functions |
| `test_flow.py`, `test_bot.py`, `test_screen.py` | every reason a bet is skipped, every way an order can come back, settlement, the warning signs, the step loop |
| `test_halts.py`, `test_day_drop.py`, `test_halt_floor.py`, `test_halt_file.py`, `test_locked.py` | each halt on its exact line, the halt file, a locked database |
| `test_stops.py`, `test_reconcile.py`, `test_chaos.py` | deadlines, resting orders, bets missing from its records, and runs against a fake Kalshi that breaks at random |
| `test_cli.py`, `test_scripts.py`, `test_one_bot.py` | the command line, `bot.py` run as a script, one bot at a time across real processes |
| `test_limit_up.py`, `test_shadow.py`, `test_price_steps.py` | the +1¢ limit live and on paper, and each market's own price steps |
| `test_fast_entry.py`, `test_fast_entry_bot.py`, `test_fast_live.py`, `test_mark_reader.py`, `test_fast_shadow.py` | fast entry and its paper reader |
| `test_dashboard.py`, `test_dashboard_more.py`, `test_frontend.py`, `test_look.py` | every number the dashboard computes, each route, and the page itself |
| `test_live_research_api.py`, `test_shadow_api.py`, `test_fast_shadow_api.py` and their `_page` tests | the Live Research tab |
| `test_tape_page.py`, `test_latency_page.py`, `test_backtest_page.py` | the Tape page and the Latency and Backtest tabs |
| `test_notify.py`, `test_watchdog.py`, `test_stall_alert.py` | the alerts and the watchdog |
| `test_safe_restart.py`, `test_probe_latency.py` | the scripts in `deploy/` |
| `test_guard.py` | the safety net in `conftest.py`: no test can reach the real `state/` folder |

## Sources

- Kaminski & Lo, [When Do Stop-Loss Rules Stop Losses?][kl] (Journal of Financial Markets, 2014)
- FIA, [Best Practices for Automated Trading Risk Controls and System Safeguards][fia]
- SEC, [Knight Capital charged under the Market Access Rule][knight]
- Kalshi, [API keys and request signing][keys], [Maintenance and pauses][kd] and [Order direction][dir]
- Kalshi, [Create Order (V2)][create], [Cancel Order (V2)][cancel] and [Get Orders][getorders]
- Federal Reserve, [FOMC meeting calendar][fomc]

[kl]: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=968338
[fia]: https://www.fia.org/sites/default/files/2024-07/FIA_WP_AUTOMATED%20TRADING%20RISK%20CONTROLS_FINAL_0.pdf
[knight]: https://www.sec.gov/newsroom/press-releases/2013-222
[keys]: https://docs.kalshi.com/getting_started/api_keys
[kd]: https://docs.kalshi.com/getting_started/maintenance_and_pauses
[dir]: https://docs.kalshi.com/getting_started/order_direction
[create]: https://docs.kalshi.com/api-reference/orders/create-order-v2
[cancel]: https://docs.kalshi.com/api-reference/orders/cancel-order-v2
[getorders]: https://docs.kalshi.com/api-reference/orders/get-orders
[hyp]: https://hypothesis.readthedocs.io/
[ntfy]: https://ntfy.sh/
[fomc]: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
