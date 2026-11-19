"""Minute-8 favorites on Kalshi's 15-minute markets: 1.5% a bet, 10% a window, skipping two warning signs, with halts.

At minute 8 of every 15-minute window it buys each 92-99.9c favourite in crypto, metals and energy,
sized at 1.5% of its bankroll with a window's bets together capped at 10%, in whole contracts, with an
immediate-or-cancel limit order 1c over the best ask it just saw on the book (at most 99.9c): it takes the
cheapest offers first and never pays more than that limit. The +1c was measured on paper first, Oct 12-20, 2026
(SHADOW_UP, the shadow table's 'limitup' rows), which stop once it's live.
Since Oct 14, 2026 every window is a fast entry (fast_entry.py, from fast_entry.START): it reads the
window's minute-by-minute prices at 450 s and, at minute 8 exactly on Kalshi's clock, reads every
book and sends the window's orders together, not one at a time seconds later. Each order is also
paired on paper with what that book offered (the shadow table's 'fast' rows; with fast entry off, a
background reader reads every book at minute 8 exactly for that).
It skips a favourite whose ask is 2c or more over its bid, or that only just became the favourite
(50c or under at minute 6 or 7, or up 10c or more in minute 8): the research's "skip both" rule.
The research and paper trading behind every number here: research/kalshi_15min in this repo.

    python bot.py                   dry run: real prices, simulated fills, no orders (the default)
    python bot.py --paper           a dry run that ignores halts and keeps going until it's broke
    python bot.py --check           check the API key: show the balance, place nothing
    python bot.py --live            real orders on KALSHI_ENV (demo unless it says prod)
    python bot.py --halt [reason]   stop every mode from placing orders until --resume
    python bot.py --resume | --status
    python bot.py --fund-crypto     move cash from Kalshi's Default section to Crypto & Commodities
    python bot.py --rebase          restart the live books from the cash now in Crypto & Commodities (money you've added)
"""
import argparse
import glob
import json
import math
import os
import socket
import sqlite3
import sys
import time
import zoneinfo
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import requests

from kalshi_bot.kalshi import Kalshi
from kalshi_bot.ledger import bankroll, cash, connect, get_meta, rebase, set_meta, set_start
from kalshi_bot.market import (book_fill, book_takes, client_order_id, favourite, floor_cents, group_of, iso,
                               minute_quotes, order_body, own_mid, parse_book, price_refused, taker_fee, tick_down,
                               top_of_book, ts)

# The bot/ folder, one up from this package: its .env, keys/ and state/ (the ledgers and the halt file) live there.
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(HERE, "state")

# ------------------------------------------------------------------ the strategy
MINUTE = 8                 # enter at minute 8 of each window
# Buy the favourite when it costs LO-HI (92-99.9c). LO was 0.90 until Oct 14, 2026: live, 90-92c favourites lost 31
# of 217 bets against about 16 expected and lost money while every dearer band made it
# (research/kalshi_15min/live_losses.py).
LO, HI = 0.92, 0.999
LIMIT_UP = 0.01            # live: how far over the ask it saw its immediate-or-cancel limit sits, capped at HI: the
                           # "+1c limit" (research/kalshi_15min/lab/fills.py). Live since Oct 20, 2026, after 8 days on
                           # paper (SHADOW_UP); 0 puts the limit back at the ask
SHADOW_UP = 0.01           # paper: after each live order it measures what a limit this far over the ask would have
                           # bought, from the book read right after the order (the shadow table; Live Research tab).
                           # Nothing once LIMIT_UP reaches it: the real order has already tried those offers
EDGE_GROUPS = ("crypto", "metals", "energy")  # Coin Race and FX spreads eat the edge
# Series inside those groups that the bot deliberately leaves alone. KXBRENT15M really is energy -- group_of
# matched WTI, NATGAS and OIL but not BRENT, so it used to fall into the "commodities" catch-all and was
# skipped by accident. The label is right now, which is why the exclusion has to be written down: Kalshi
# listed it on Oct 21, 2026, it had produced 3 bets under the live rule, and adding a market mid-test would have
# changed the rule being tested. It was left out until there was a month of it to score.
NOT_TRADED = ("KXBRENT15M",)
# KXADA15M, KXBCH15M and KXTON15M are listed by Kalshi and have never opened a market, so every window pays
# three calls for nothing. Filtering them out on the catalog refresh was tried on Oct 24 and backed out: the
# obvious check ("does this series have a market now?") marks every metals and energy series dead outside
# their trading hours, since those do not run around the clock, and the bot would then stop asking for them
# until the next refresh. A safe version has to ask whether a series has EVER had a market, which is a
# different call; the gain is one round of parallel listing calls, so it was not worth the risk mid-test.
CAP_PCT = 0.015            # 1.5% of the bankroll a bet (half of the old 3%, Oct 15) ...
WINDOW_CAP = 0.10          # ... and a window's bets together at most 10% of it
MIN_BET = 1.0
GRACE = 45                 # seconds into minute 8 it may still enter
# The warning signs it skips (research/kalshi_15min/findings.py; "skip both" in strategies_backtest.py):
SPREAD_MAX = 0.02          # the favourite's ask 2c or more over its bid at entry: a thin, uncertain market
LATE_MID = 0.50            # the favourite 50c or under at minute 6 or 7 ...
JUMP = 0.10                # ... or up 10c or more in minute 8: it only just became the favourite
LOOKBACK = (6, 7)          # the minutes the late check reads

# ------------------------------------------------------------------ safety limits
# No cap on an order's size (the $10 one was removed on Oct 10): CAP_PCT a bet, WINDOW_CAP a window and the balance check bound it.
MAX_ORDERS_PER_WINDOW = 20
MAX_ORDERS_PER_DAY = 600
MAX_ORDER_ERRORS = 3       # halt after this many failed orders in a row
MAX_PRICE_ERRORS = 6       # ... and after this many refused for their price in a row (tick_down should mean never).
                           # Above the four whole-cent series one window can hold, so the pattern that prompted the
                           # fix can't fire it, while a price rule that refused everything shows up inside one window.
# How long anything may take. Prices at minute 8 are what the research tested; later, they're a different bet.
ORDER_DEADLINE = 60        # no order goes out more than this many seconds after minute 8 ends (the end of minute 9)
BOOK_MAX_AGE = 15          # ... or on an order book read more than this many seconds before
SHADOW_WAIT = 10           # paper: once a window's orders are out, the most it waits, all told, on their book reads
RESTING_EVERY = 15         # live: how often it looks for its own orders left resting on the book
RECONCILE_EVERY = 60       # live: how often it checks Kalshi's record of its orders for bets missing from its own ...
RECONCILE_BACK = 7200      # ... over the last 2 hours (a day back on its first check after a start)
DRY_RUN_START = 1000.0     # the dry run's simulated account; live starts from the account's balance

# ------------------------------------------------------------------ fast entry (fast_entry.py, live since Oct 14)
# A fast window preps at fast_entry.PREP (450 s) and enters at the mark, minute 8 exactly on Kalshi's clock, its orders
# sent together in batches: Kalshi's Basic write bucket holds 10 orders and refills 10 a second
# (research/kalshi_15min/lab/fast_entry/kalshi_api.md), and a 429 (refused for rate) is never retried.
FAST_BURST = 8             # orders sent at once, a batch: no further batch goes out until its answers are back
FAST_SPACING = 0.1         # ... and past a batch's first, one every this many seconds (the bucket's refill)
NTP_EVERY = 900            # how often it asks a time server for real time: the PC's clock drifts about 0.5 s a day
CLOCK_SAMPLES = 5          # Kalshi's clock is its order answers' (ts_ms) once it has this many, else the time server's
CLOCK_KEEP = 10            # ... the median of the last this many: about a window's, so a PC clock being set right
                           # is followed within a window or so

# ------------------------------------------------------------------ halts
# A halt stops new orders until --resume; open bets still settle. Each level sits just past the worst
# the history has seen, so it fires on the unusual, not on an ordinary bad day (research README).
HALT_DEPOSIT = 0.50        # worth half its start or less
HALT_FLOOR = 700.0         # ... or worth $700 or less: a fixed stop for the real-money account only (prod, live)
HALT_WINDOW_LOSSES = 8     # 8+ bets lost in one window (only the Sep 16 Fed decision did: 11)
HALT_DAY_DROP = 0.35       # down 35%+ within 24 hours: just past the worst on record for this rule with no order cap
                           # (34.8% from Jul 18, 31.5% from Aug 24; from Dec 10 it would have fired once, Jul 8 at 35.9%);
                           # 20% sat inside a single window's 20% cap and halted it on ordinary bad windows
HALT_SETTLE_LAG = 1800     # a bet unsettled 30 minutes after its market closed ...
HALT_PERSIST = 300         # ... or Kalshi paused outside maintenance, for 5 minutes running
HALT_EMPTY_WINDOWS = 3     # ... or 3 windows running (45 minutes) listed no markets at all: see Bot.nothing_listed
LOCK_HALT = 120            # its records locked by another program for 2 minutes running (antivirus, a backup, a sync app)
# No new orders in windows that overlap these (UTC). Fed decisions: 2:00 pm ET, press conference 2:30.
# Add each FOMC date: federalreserve.gov/monetarypolicy/fomccalendars.htm
# 2:00-3:30 pm ET is 18:00-19:30 UTC in summer time, 19:00-20:30 in winter. The 2027 dates are tentative until the
# meeting before each one confirms it. test_blackouts.py fails once the last is under 60 days away.
BLACKOUTS = [
    ("2026-10-28T18:00:00Z", "2026-10-28T19:30:00Z", "Fed decision"),
    ("2026-12-09T19:00:00Z", "2026-12-09T20:30:00Z", "Fed decision"),
    ("2027-01-27T19:00:00Z", "2027-01-27T20:30:00Z", "Fed decision"),
    ("2027-03-17T18:00:00Z", "2027-03-17T19:30:00Z", "Fed decision"),
    ("2027-04-28T18:00:00Z", "2027-04-28T19:30:00Z", "Fed decision"),
    ("2027-06-09T18:00:00Z", "2027-06-09T19:30:00Z", "Fed decision"),
    ("2027-07-28T18:00:00Z", "2027-07-28T19:30:00Z", "Fed decision"),
    ("2027-09-15T18:00:00Z", "2027-09-15T19:30:00Z", "Fed decision"),
    ("2027-10-27T18:00:00Z", "2027-10-27T19:30:00Z", "Fed decision"),
    ("2027-12-08T19:00:00Z", "2027-12-08T20:30:00Z", "Fed decision"),
]

POLL = 3.0
STATUS_EVERY = 60.0
CATALOG_EVERY = 3600.0
ET = zoneinfo.ZoneInfo("America/New_York")


def load_env(path=os.path.join(HERE, ".env")):
    """KEY=VALUE lines from .env; the real environment wins."""
    env = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip().strip("\"'")
    env.update({k: v for k, v in os.environ.items() if k.startswith("KALSHI_")})
    return env


def stake_for(bankroll, n):
    """CAP_PCT of the bankroll, a window's n bets together at most WINDOW_CAP of it. No cap on an order's size since Oct 10."""
    return floor_cents(min(bankroll * CAP_PCT, bankroll * WINDOW_CAP / max(n, 1)))


# ------------------------------------------------------------------ halts
# One halt file for every mode (dry run, demo, prod): a halt stops them all, including a mode that
# hasn't run yet, until --resume. Only a paper account (--paper) ignores it, and never writes it.
def halt_path():
    return os.path.join(STATE, "halt.json")


def halt_info():
    """The halt in force, or None. halt.json is only written for a halt, so one that can't be read (garbled, edited
    by hand, held by another program) still counts, dated by its last change; --resume removes it."""
    when = time.time()
    try:
        with open(halt_path(), encoding="utf-8") as fh:
            when = os.fstat(fh.fileno()).st_mtime
            h = json.load(fh)
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        h = None
    if isinstance(h, dict) and all(isinstance(h.get(k), str) for k in ("ts", "reason", "by")):
        return h
    return {"ts": iso(when), "reason": "halt.json couldn't be read, so it counts as a halt", "by": "unknown"}


def set_halt(now, reason, by="auto"):
    if halt_info():
        return
    os.makedirs(STATE, exist_ok=True)
    tmp = halt_path() + ".tmp"   # written whole beside it, then swapped in: a crash mid-write leaves no half file
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"ts": iso(now), "reason": reason, "by": by}, fh)
    os.replace(tmp, halt_path())
    print(f"{iso(now)} HALTED ({by}): {reason}. No new orders until: python bot.py --resume", flush=True)


def clear_halt(now, dbs):
    """Resume. Each account's tripwires start over: only results from now on count, and its
    half-the-start floor becomes half of what it's worth now if that is lower."""
    h = halt_info()
    if h:
        os.remove(halt_path())
    for db in dbs:
        set_meta(db, "halt_seen", now)
        set_meta(db, "halt_base", min(float(get_meta(db, "start")), bankroll(db)))
        db.commit()
    return h


def blackout(window_open):
    for a, b, what in BLACKOUTS:
        if window_open < ts(b) and window_open + 900 > ts(a):
            return what
    return None


def scheduled_maintenance(now):
    """Kalshi's weekly maintenance: Thursdays 3:00-5:00 am ET, trading paused."""
    et = datetime.fromtimestamp(now, ET)
    return et.weekday() == 3 and 3 <= et.hour < 5


def trading_on(status):
    """From GET /exchange/status: False if trading is off overall or for crypto & commodities, None if unknown."""
    if not status:
        return None
    if not status.get("exchange_active", True) or not status.get("trading_active", True):
        return False
    for x in status.get("exchange_index_statuses") or []:
        if "crypto" in (x.get("description") or "").lower() and not (x.get("exchange_active") and x.get("trading_active")):
            return False
    return True


def crypto_section(status):
    """The section (exchange index) Crypto & Commodities markets trade in, from GET /exchange/status. An entry
    without an index is passed over rather than crash a live run on every status read."""
    for x in (status or {}).get("exchange_index_statuses") or []:
        if "crypto" in (x.get("description") or "").lower() and x.get("exchange_index") is not None:
            return x["exchange_index"]
    return 2  # what Kalshi reports today


def usable_cash(balance, section):
    """Dollars an order in these markets can use. Kalshi keeps each section's cash apart and an order can
    only use its market's section, so it's that section's cash, not the account total."""
    if not balance or "balance" not in balance:
        return None
    parts = balance.get("balance_breakdown")
    if parts:
        return next((float(x["balance"]) for x in parts if x.get("exchange_index") == section), 0.0)
    return balance["balance"] / 100  # no breakdown (a key limited to one section): the total is that section


# condition -> when it was first seen, for the ones that must last HALT_PERSIST; and "off" -> when trading was
# last seen off, which holds back the two conditions a pause explains (see check_halts).
_since = {}


def check_halts(db, now, trading=None, reachable=True, floor=0.0, empty=0):
    """trading: from the exchange status (None if unknown). reachable: False while that status can't be read at all.
    floor: halt once worth this or less (HALT_FLOOR for live prod; 0 for dry runs, paper and demo, whose books are
    play money and share the halt file). empty: windows running that listed no markets (Bot.empty)."""
    if trading is False:   # noted even while halted: a pause it slept through still excuses what follows (Oct 29)
        _since["off"] = now
    if halt_info():
        return
    seen = float(get_meta(db, "halt_seen", 0))
    base = float(get_meta(db, "halt_base", get_meta(db, "start")))
    worth = bankroll(db)
    if worth <= base * HALT_DEPOSIT:
        return set_halt(now, f"the account is down to ${worth:.2f}, half of ${base:.2f} or less")
    if floor and worth <= floor:
        return set_halt(now, f"the account is down to ${worth:.2f}, at or under the ${floor:.0f} stop")
    for w, lost in db.execute("SELECT window_open, SUM(status='lost') FROM bets WHERE status!='open'"
                              " GROUP BY window_open HAVING MAX(settled_ts) > ?", (max(seen, now - 3600),)):
        if lost >= HALT_WINDOW_LOSSES:
            return set_halt(now, f"{lost} bets lost in one window ({datetime.fromtimestamp(w, ET):%b %d %H:%M} ET)")
    since = max(seen, now - 86400)
    bal = peak = bankroll(db, at=since)
    for (pnl,) in db.execute("SELECT pnl FROM bets WHERE status!='open' AND settled_ts > ? ORDER BY settled_ts", (since,)):
        bal += pnl
        peak = max(peak, bal)
        if bal <= peak * (1 - HALT_DAY_DROP):
            return set_halt(now, f"the account fell {1 - bal / peak:.0%} within 24 hours")
    # While Kalshi isn't trading, nothing settles and a window may list nothing, so neither counts as a fault: not
    # during the pause, and not for HALT_SETTLE_LAG after it, because a bet whose market closed inside the pause only
    # gets its 30 minutes to settle once trading is back. That covers the Thursday 3-5 am ET maintenance (which
    # halted the bot every week it held a bet into 3:00 am), and holidays and unplanned outages with it. An
    # unscheduled pause still halts on its own below, and a bet stuck while Kalshi is trading still halts.
    trading_now = trading is not False and now - _since.get("off", 0) >= HALT_SETTLE_LAG
    if trading_now and empty >= HALT_EMPTY_WINDOWS:
        return set_halt(now, f"{empty} windows running listed no markets: nothing has been bet in {empty * 15} minutes")
    late = db.execute("SELECT COUNT(*) FROM bets WHERE status='open' AND close_ts < ?",
                      (now - HALT_SETTLE_LAG,)).fetchone()[0] if trading_now else 0
    paused = trading is False and not scheduled_maintenance(now)
    for key, on, why in (("late", late > 0, f"{late} bets still unsettled 30+ minutes after their market closed"),
                         ("paused", paused, "Kalshi paused trading outside its scheduled maintenance"),
                         ("down", not reachable, "Kalshi unreachable: its exchange status couldn't be read for 5 minutes")):
        if not on:
            _since.pop(key, None)
        elif now - _since.setdefault(key, now) >= HALT_PERSIST:
            return set_halt(now, why)


# ------------------------------------------------------------------ the order's limit
def limit_for(top):
    """The most its order pays a contract: LIMIT_UP over the ask it saw, never past 99.9c (HI). LIMIT_UP is 1c live
    since Oct 20, 2026: by the time its order lands the ask has often ticked up, and on paper (SHADOW_UP) the extra cent
    took the contracts filled from about 60% to 96%."""
    return min(round(top + LIMIT_UP, 4), HI)


# ------------------------------------------------------------------ the warning signs
def warning(side, yes_bid, yes_ask, history):
    """Why to skip this favourite, or None. history: {minute: (yes_bid, yes_ask)} for this market. A minute with no
    quote can't trigger a check, as in the backtest; prices are rounded so a 10.0c jump counts as 10c."""
    spread = round(yes_ask - yes_bid, 6)
    if spread >= SPREAD_MAX:
        return f"warning sign: its ask is {spread * 100:.1f}c over its bid (2c or more)"
    for k in LOOKBACK:
        mid = own_mid(side, history.get(k))
        if mid is not None and mid <= LATE_MID:
            return f"warning sign: it was {mid * 100:.1f}c at minute {k}, only just the favorite"
    before, now = own_mid(side, history.get(MINUTE - 1)), own_mid(side, (yes_bid, yes_ask))
    if before is not None and round(now - before, 6) >= JUMP:
        return f"warning sign: it jumped {(now - before) * 100:.1f}c in minute {MINUTE}"
    return None


def fast_entry_module():
    """fast_entry.py, imported here when first needed rather than at the top: bot.py still runs from a copy of the
    package without it (test_scripts.py), and then this is None and every window is normal, as before fast entry."""
    try:
        import kalshi_bot.fast_entry as fast_entry
    except ImportError:
        return None
    return fast_entry


# ------------------------------------------------------------------ the bot
class Bot:
    def __init__(self, k, db, live, halts=True):
        self.k, self.db, self.live = k, db, live
        self.floor = HALT_FLOOR if live and getattr(k, "env", None) == "prod" else 0.0   # the $700 stop: real money only
        self.halts = halts  # False for a paper account: it trades through every halt until it's broke
        self.universe = {}  # series -> {"group", "fee"}
        self.trading = None
        self.reachable = True  # False while Kalshi's exchange status can't be read at all
        self.section = 2  # Kalshi's Crypto & Commodities section, refreshed from the exchange status
        self.errors = 0
        self.price_errors = 0   # orders refused for their price in a row (price_refused); its own halt line
        self.last_catalog = self.last_status = self.last_sweep = self.last_reconcile = 0.0
        self.reconciled = False   # True once it has read Kalshi's record of its orders since it started
        self.locked_since = None  # when its records were first found locked, while they still are
        self.done_window = None
        self.empty = 0        # windows running that listed no markets ...
        self.missed = None    # ... and the last one said out loud, so it's said once a window, not once a poll
        self.unsure = None    # the last window it didn't enter because Kalshi's record of its orders was still unread
        # A stopwatch for the deadlines: `now` is when the step began, and the step's calls to Kalshi take real time.
        self.clock, self.mark = time.monotonic, None
        self.pool = ThreadPoolExecutor(max_workers=4)   # live: reads each order's book again in the background (shadow)
        self.reader = None   # live: reads every order book at minute 8 exactly (start_reader; fast_shadow)
        self.fe = fast_entry_module()   # fast entry's helpers; None without fast_entry.py beside it: every window normal
        self.prepared = {}   # a fast window's prep, the current window's only: {window_open: {"markets", "history", "cash"}}
        self.warmed, self.warming = None, []   # the window whose connections it last opened before the mark (warm), and how
        # Kalshi's clock less the PC's (offset): from its order answers, else a time server's reading of real time
        self.clocks = self.fe.ClockSync(keep=CLOCK_KEEP) if self.fe else None
        self.ntp, self.last_ntp = None, 0.0

    def elapsed(self):
        """Seconds since this step began (0 outside a step)."""
        return 0.0 if self.mark is None else self.clock() - self.mark

    def halt(self):
        """The halt in force, if this account obeys halts."""
        return halt_info() if self.halts else None

    @property
    def offset(self):
        """Kalshi's clock less the PC's, in seconds: the median of what its last order answers said (their ts_ms) once
        there are CLOCK_SAMPLES of them, else a time server's last reading (the first source, before any order has
        answered), else 0. The loop's steps and wake-ups run on the PC's clock plus this."""
        if self.clocks is not None and len(self.clocks) >= CLOCK_SAMPLES:
            return self.clocks.offset()
        return 0.0 if self.ntp is None else self.ntp

    def fast(self, window_open):
        """Whether this window enters fast (fast_entry.arm): as shipped, every window from fast_entry.START."""
        return self.fe is not None and self.fe.arm(window_open, self.fe.START) == "fast"

    def section_of(self, m):
        """The exchange_index an order on market m carries: the market's own section, from its listing (Kalshi's docs
        call a market's exchange_index the authoritative source), else self.section, the one the exchange status gives
        Crypto & Commodities (2 today). It only names where the order goes, with no change to whose cash it uses:
        left out, Kalshi routes it there itself, more slowly, and bills it to every section's write bucket."""
        return m.get("exchange_index", self.section)

    def limit_on(self, m, top):
        """The limit for an order in this market: the live rule (limit_for), lowered onto a price the market has."""
        return tick_down(limit_for(top), m.get("price_ranges"))

    def log(self, now, m, action, reason, side=None, price=None, yb=None, ya=None):
        self.db.execute("INSERT OR IGNORE INTO decisions (ts, ticker, series, yes_bid, yes_ask, fav_side, fav_price, action, reason)"
                        " VALUES (?,?,?,?,?,?,?,?,?)", (now, m["ticker"], m["series"], yb, ya, side, price, action, reason))
        print(f"{iso(now)} {m['ticker']:<32} {action:<7} {reason}", flush=True)

    def load_catalog(self):
        d = self.k.series()
        if not d:
            return False
        self.universe = {s["ticker"]: {"group": group_of(s["ticker"], s.get("category") or ""),
                                       "fee": float(s.get("fee_multiplier") or 1.0)}
                         for s in d.get("series", []) if s.get("frequency") == "fifteen_min" and not s["ticker"].endswith("TEST")}
        return True

    def edge_series(self):
        """The series in the groups the strategy trades, in the catalog's order: the ones window_markets lists, and the
        ones the paper fast entry's reader reads, which asks afresh every window from its own thread (load_catalog swaps
        the whole catalog, never changes it in place)."""
        return [s for s, u in self.universe.items() if u["group"] in EDGE_GROUPS and s not in NOT_TRADED]

    def window_markets(self, window_open):
        """This window's markets in the groups the strategy trades, each with its live order book."""
        return self.books(self.listed(window_open))

    def listed(self, window_open):
        """This window's markets in the groups the strategy trades, as Kalshi lists them (no books yet), each with the
        section it trades in when the listing gives one as a whole number.

        Asked for by close time rather than by `status=open`. On Oct 24 that filter matched nothing for about seven
        hours: Kalshi kept answering 200 with an empty list, which reads exactly like a quiet hour, and the bot placed
        no bets for 27 windows before the filter started working again on its own. It is still a filter Kalshi takes
        (`open`, `unopened`, `settled`; the initialized/active/finalized in a market's own `status` field are not
        filter values and never were), so this is not a migration -- it is a listing that doesn't depend on it.
        A window's market is the one closing at its end, so a one-second range round that returns the one market per
        series. Asking with no range at all would page through thousands of future markets on the path that gets
        orders out in about 124 ms, and the open-time match below is still what says a market is this window's."""
        series = self.edge_series()
        close = int(window_open) + 900
        with ThreadPoolExecutor(max_workers=8) as pool:
            listed = list(pool.map(lambda s: self.k.markets(series_ticker=s, min_close_ts=close - 1,
                                                            max_close_ts=close + 1, limit=50), series))
        return [{"ticker": m["ticker"], "series": s, "open": ts(m["open_time"]), "close": ts(m["close_time"]),
                 **({"exchange_index": m["exchange_index"]} if type(m.get("exchange_index")) is int else {}),
                 **({"price_ranges": m["price_ranges"]} if isinstance(m.get("price_ranges"), list) else {})}
                for s, d in zip(series, listed) for m in (d or {}).get("markets", [])
                if abs(ts(m["open_time"]) - window_open) < 1]

    def books(self, markets):
        """These markets, each with its live order book, read 8 at a time: as Kalshi sent it and parsed."""
        with ThreadPoolExecutor(max_workers=8) as pool:
            for m, raw in zip(markets, pool.map(lambda m: self.k.orderbook(m["ticker"]), markets)):
                m["raw"], m["book"], m["read"] = raw, parse_book(raw), self.elapsed()   # when, into the step, it was read
        return markets

    def prepare(self, now, window_open):
        """A fast window's prep, from fast_entry.PREP (450 s): its markets as listed, their minute-by-minute prices for
        the warning signs (minute 7's are final at 420 s) and, live, Kalshi's cash for these markets, kept for the mark
        (the current window's only). It reads no book and sends no order. With nothing listed (a quiet hour, Kalshi
        unreachable) it keeps nothing and the next step tries again; prices or cash it couldn't read are None, and the
        mark reads them itself."""
        markets = self.listed(window_open)
        if not markets:
            return
        raw = self.k.candlesticks([m["ticker"] for m in markets], window_open, window_open + MINUTE * 60)
        held = usable_cash(self.k.balance(), self.section) if self.live else None
        self.prepared = {window_open: {"markets": markets, "history": minute_quotes(raw, window_open), "cash": held}}

    def warm(self, window_open):
        """Just before a fast window's mark, opens the connections its book reads and orders go out on: FAST_BURST cheap
        requests at once (the exchange status) on threads of their own, their answers unused. A connection opened at
        the mark would cost its TLS handshake there, about 0.1-0.25 s (kalshi_api.md). It doesn't wait for them, so a
        slow Kalshi can't hold the mark up."""
        self.warmed = window_open
        pool = ThreadPoolExecutor(max_workers=FAST_BURST)
        self.warming = [pool.submit(self.k.exchange_status) for _ in range(FAST_BURST)]
        pool.shutdown(wait=False)   # its threads end once their requests have; the step goes on now

    def decide_window(self, now, window_open, markets, prep=None):
        """Every favourite of the window, decided: skipped (and why), or bought. Without prep, each order goes out and
        is recorded before the next is built, as before fast entry. prep: a fast window's, from prepare() (the
        minute-by-minute prices and Kalshi's cash read at 450 s, None where a read failed): every order is built first
        under the same checks, in the same order and with the same words, each holding back its cash (the books' and
        Kalshi's) and its place under the caps as it's built, and then live they go out together (send())."""
        decided = {r[0] for r in self.db.execute("SELECT ticker FROM decisions")}
        quals = []
        for m in markets:
            if m["ticker"] in decided:
                continue
            yb, ya, ask_size, no_size = top_of_book(m["book"])
            side, top = favourite(yb, ya)
            if m["book"] is None:
                self.log(now, m, "skip", "order book unavailable")
            elif side is None:
                self.log(now, m, "skip", "no quotes", yb=yb, ya=ya)
            elif not LO <= top <= HI:
                self.log(now, m, "skip", f"favorite at {top * 100:.1f}c is outside {LO * 100:g}-{HI * 100:g}c", side, top, yb, ya)
            else:
                quals.append((m, side, top, yb, ya, ask_size if side == "yes" else no_size))
        if quals:
            quals = self.screen(now, window_open, quals, history=(prep or {}).get("history"))
        if not quals:
            return
        why = None
        if h := self.halt():
            why, action = f"halted: {h['reason']}", "halted"
        elif what := blackout(window_open):
            why, action = f"{what} blackout", "skip"
        elif self.trading is False:
            why, action = "Kalshi has trading paused", "skip"
        elif self.trading is None:
            why, action = "couldn't confirm Kalshi is trading: its exchange status is unreadable", "skip"
        bal, n = bankroll(self.db), len(quals)   # the window cap counts only the favourites that passed the screen
        stake = stake_for(bal, n)
        if why is None and stake < MIN_BET:
            why, action = f"bet size ${stake:.2f} is under the $1 minimum", "skip"
        live_cash = None
        if why is None and self.live:
            live_cash = (prep or {}).get("cash")   # a fast window's, read at its prep
            if live_cash is None:
                live_cash = usable_cash(self.k.balance(), self.section)
            if live_cash is None:
                why, action = "couldn't read the account balance", "skip"
        if why:
            for m, side, top, yb, ya, _ in quals:
                self.log(now, m, action, why, side, top, yb, ya)
            return
        today = self.db.execute("SELECT COUNT(*) FROM bets WHERE placed_ts > ?", (now - 86400,)).fetchone()[0]
        held = None if prep is None else cash(self.db)   # fast: the books' cash, less what each order built holds back
        reads = []   # live: each order's book, read again right after it went out, for the paper +1c (shadow)
        orders = []   # fast: the orders built, to go out together
        for i, (m, side, top, yb, ya, size) in enumerate(quals):
            if i >= MAX_ORDERS_PER_WINDOW or today >= MAX_ORDERS_PER_DAY:
                self.log(now, m, "skip", "order limit reached", side, top, yb, ya)
                continue
            # Kalshi may be slow: each earlier order, the book, the history can all take seconds. Past these, skip.
            if self.stale(now, window_open, m, side, top, yb, ya):
                continue
            if h := self.halt():  # a failed order earlier in this window can halt
                self.log(now, m, "halted", f"halted: {h['reason']}", side, top, yb, ya)
                continue
            c = math.floor(stake / top + 1e-9)   # sized off the ask it saw, as the research sized its bets
            # The most it can cost: every contract at the limit, the fee at the ask it saw (past 50c the fee falls as the
            # price rises, so the seen ask's is the larger).
            need = c * self.limit_on(m, top) + taker_fee(c, top, self.universe.get(m["series"], {}).get("fee", 1.0))
            if c < 1 or (cash(self.db) if held is None else held) < need:
                self.log(now, m, "skip", "bankroll too low", side, top, yb, ya)
                continue
            if live_cash is not None and live_cash < need:
                self.log(now, m, "skip", f"only ${live_cash:.2f} in Kalshi's Crypto & Commodities section"
                         " (python bot.py --fund-crypto moves cash there)", side, top, yb, ya)
                continue
            if held is not None:   # fast: its cash and its place under the caps held back now; it goes out below
                orders.append((m, side, top, c, yb, ya, size))
                held -= need
                today += 1
                if live_cash is not None:
                    live_cash -= need
                continue
            placed = self.place(now, m, side, top, c, stake, n, size, yb, ya)
            if self.live:   # whatever came of the order; in the background, so the next order isn't kept waiting
                reads.append((m, side, top, c, self.pool.submit(self.read_book, m["ticker"])))
            if placed:
                today += 1
                if live_cash is not None:
                    live_cash -= need
        if not self.live:   # a dry run's fast window: each placed in turn, as ever, with nothing to send
            for m, side, top, c, yb, ya, size in orders:
                self.place(now, m, side, top, c, stake, n, size, yb, ya)
        elif orders:
            reads = self.send(now, orders, stake, n)
        self.shadow(now, window_open, reads)
        if prep is None:
            self.fast_shadow(now, window_open, reads)
        else:   # paired with the books it read at the mark itself: the paper reader is off while fast entry is on
            self.fast_shadow(now, window_open, reads,
                             {m["ticker"]: (m.get("raw"), now + m.get("read", 0.0)) for m in markets})

    def stale(self, now, window_open, m, side, top, yb, ya):
        """Whether it's now too late for an order on market m (ORDER_DEADLINE), or m's book too old to price one on
        (BOOK_MAX_AGE), by the stopwatch: if so the skip is logged. Checked as each order is built, and again for a fast
        window's later batch once the batch before it is back, as Kalshi can take seconds over each."""
        late = now + self.elapsed() - (window_open + MINUTE * 60)
        if late > ORDER_DEADLINE:
            self.log(now, m, "skip", f"too late: {late:.0f}s after minute {MINUTE} ended, past the {ORDER_DEADLINE}s deadline",
                     side, top, yb, ya)
            return True
        age = self.elapsed() - m.get("read", self.elapsed())
        if age > BOOK_MAX_AGE:
            self.log(now, m, "skip", f"its order book was read {age:.0f}s ago, over {BOOK_MAX_AGE}s", side, top, yb, ya)
            return True
        return False

    def send(self, now, orders, stake, n):
        """A fast window's live orders, built and held back: sent through fast_entry.send_all in batches of at most
        FAST_BURST, in the order built. The first batch goes at once; a later one, an order every FAST_SPACING s (Kalshi's
        write bucket refills about that fast), only once the batch before it is back. Its failures are counted in a
        row in send order, as place() counts them, and three halt, so past a failure no more than the batch already
        out can go out. Then each answer is recorded in send order, on this thread, with place(..., sent=): its
        orders row, its fills, its bet, and the error and unexpected-fill halts. What never went out for a halt is logged
        as halted. A later batch's orders are checked again for the deadline and their books' age (stale) once the batch
        before is back: one past either is skipped, never sent. Each answer with Kalshi's time (ts_ms) adds a clock
        sample. Returns the paper +1c's reads: each order's book, read again in the background right after its batch
        came back."""
        sent, reads, failed, refused, h, done = [], [], self.errors, self.price_errors, None, 0
        for first in range(0, len(orders), FAST_BURST):
            if first and (h := self.halt()):   # three failures in a row in the batch before, or any other halt
                break
            done = first + FAST_BURST   # the orders up to here have gone out or been skipped
            batch = [o for o in orders[first:done]
                     if not (first and self.stale(now, o[0]["open"], o[0], o[1], o[2], o[4], o[5]))]
            if not batch:
                continue
            bodies = [order_body(m["ticker"], side, self.limit_on(m, top), c, exchange_index=self.section_of(m))
                      for m, side, top, c, *_ in batch]
            answers = self.fe.send_all(self.k, bodies, workers=FAST_BURST, spacing=FAST_SPACING,
                                       burst=1 if first else FAST_BURST)
            for (m, side, top, c, *_), s in zip(batch, answers):
                reads.append((m, side, top, c, self.pool.submit(self.read_book, m["ticker"])))
                if s["status"] in (200, 201) and isinstance(s["data"], dict):
                    failed = refused = 0
                elif price_refused(s["status"], s["data"]):
                    refused += 1                 # its own count: the market never had that price (price_refused)
                else:
                    failed += 1
                if failed >= MAX_ORDER_ERRORS:   # (place() halts on it too as it records them, in this order)
                    set_halt(now, f"{failed} orders failed in a row")
                elif refused >= MAX_PRICE_ERRORS:
                    set_halt(now, f"{refused} orders refused for their price in a row")
            sent += zip(batch, answers)
        for (m, side, top, c, yb, ya, size), s in sent:
            if isinstance(s["data"], dict):
                self.clocks.add(s["sent"], s["answered"], s["data"].get("ts_ms"))
            self.place(now, m, side, top, c, stake, n, size, yb, ya, sent=s)
        for m, side, top, c, yb, ya, size in orders[done:] if h else ():
            self.log(now, m, "halted", f"halted: {h['reason']}", side, top, yb, ya)
        return reads

    def read_book(self, ticker):
        """(a market's raw order book or None, when into the step it answered). It runs on a background thread, so it
        only asks Kalshi: the ledger belongs to the bot's own thread."""
        return self.k.orderbook(ticker), self.elapsed()

    def shadow(self, now, window_open, reads):
        """The +1c on paper, once a window's orders are all out: for each live order, what a limit SHADOW_UP over the ask
        it saw would have bought on top of what really filled (its bet's contracts), from the book read right after it.
        The extra contracts are the offers dearer than that ask and within the paper limit, cheapest first, up to the
        contracts the real order didn't get; their fee is their unrounded share of Kalshi's. A read that failed, took too
        long or brought no book is kept as 'unread'. It never places, cancels or changes an order or a bet. Nothing once
        the live limit reaches the paper one (LIMIT_UP >= SHADOW_UP): the real order has already tried those offers."""
        if LIMIT_UP >= SHADOW_UP:
            return
        deadline = self.clock() + SHADOW_WAIT
        for m, side, top, c, read in reads:
            bet = self.db.execute("SELECT contracts FROM bets WHERE ticker=?", (m["ticker"],)).fetchone()
            filled = bet[0] if bet else 0.0
            limit = tick_down(min(round(top + SHADOW_UP, 4), HI), m.get("price_ranges"))
            mult = self.universe.get(m["series"], {}).get("fee", 1.0)
            lag = measured = None
            try:
                raw, at = read.result(timeout=max(deadline - self.clock(), 0.01))
                lag = now + at - (window_open + MINUTE * 60)   # how long after minute 8 the book answered
                book = parse_book(raw)
                if book is not None:   # the extra contracts, their cost and their fee (Kalshi's, unrounded)
                    taken = book_takes(book, side, limit, max(c - filled, 0), above=top)
                    measured = (sum(q for _, q in taken), sum(q * p for p, q in taken),
                                0.07 * mult * sum(q * p * (1 - p) for p, q in taken))
            except Exception:   # it raised, ran out of time, or brought something that isn't a book
                pass
            extra, cost, fee = measured or (None, None, None)
            self.record_shadow(now, "limitup", m, window_open, side, top, limit, c, filled, lag, extra, cost, fee,
                               "open" if measured else "unread")

    def fast_shadow(self, now, window_open, reads, books=None):
        """Fast entry on paper, once a window's orders are all out: each live order paired with what an order sent at
        minute 8 exactly would have bought, from the book the reader (fast_entry.MarkReader) read at that instant.
        Its ask is the cheapest offer then on the real order's side, its limit limit_for's (the live rule), and it
        takes the offers up to that limit, cheapest first, up to every contract the real order asked for; their fee
        is their unrounded share of Kalshi's. An empty side, or an ask outside LO-HI (92-99.9c), bought nothing. A book the
        reader didn't get, couldn't read or garbled, or a reader that raised, is kept as 'unread'. Nothing without a
        reader or live orders. It never places, cancels or changes an order or a bet. books: a fast window's own, read
        at the mark ({ticker: (raw book, when it answered on Kalshi's clock)}), in place of the reader's."""
        if books is None and self.reader is None or not reads:
            return
        if books is None:
            try:
                books = self.reader.books(window_open)   # {ticker: (raw book, when it answered on Kalshi's clock)}
            except Exception:   # its thread died, or something odd: every order of the window is unread
                books = {}
        for m, side, top, c, _ in reads:
            bet = self.db.execute("SELECT contracts FROM bets WHERE ticker=?", (m["ticker"],)).fetchone()
            filled = bet[0] if bet else 0.0
            mult = self.universe.get(m["series"], {}).get("fee", 1.0)
            seen = limit = lag = measured = None
            try:
                raw, answered = books[m["ticker"]]
                lag = answered - (window_open + MINUTE * 60)   # how long after minute 8 the mark's book answered
                book = parse_book(raw)
                if book is not None:
                    bids = book["no" if side == "yes" else "yes"]   # an offer to sell one side is a bid on the other
                    seen = round(1 - bids[0][0], 4) if bids else None   # its ask at the mark: 1 - the best bid
                    measured = (0.0, 0.0, 0.0)   # an empty side, or an ask the rule wouldn't buy: nothing bought
                    if seen is not None and LO <= seen <= HI:   # the contracts, their cost and fee (Kalshi's, unrounded)
                        limit = limit_for(seen)
                        taken = book_takes(book, side, limit, c)
                        measured = (sum(q for _, q in taken), sum(q * p for p, q in taken),
                                    0.07 * mult * sum(q * p * (1 - p) for p, q in taken))
            except Exception:   # not read, a garbled entry or answer time, or something that isn't a book
                seen = limit = measured = None
            extra, cost, fee = measured or (None, None, None)
            self.record_shadow(now, "fast", m, window_open, side, seen, limit, c, filled, lag, extra, cost, fee,
                               "open" if measured else "unread")

    def record_shadow(self, now, kind, m, window_open, side, seen, limit_price, asked, filled, lag, extra, cost, fee, status):
        """One paper measurement (kind: which experiment) of a market: one row per kind and market, and a repeat never
        overwrites it. The step loop's commit saves it."""
        self.db.execute("INSERT OR IGNORE INTO shadow (kind, ticker, ts, window_open, close_ts, series, side, seen, limit_price,"
                        " asked, filled, lag, extra, cost, fee, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (kind, m["ticker"], now, window_open, m["close"], m["series"], side, seen, limit_price, asked,
                         filled, lag, extra, cost, fee, status))

    def screen(self, now, window_open, quals, history=None):
        """The favourites that show no warning sign; the rest are logged as skips. Every one is skipped if the
        minute-by-minute prices can't be read, or a market has none: the bot doesn't bet on a check it couldn't make.
        history: the prices a fast window's prep read ({ticker: {minute: (yes_bid, yes_ask)}}); without them it reads
        them now."""
        if history is None:
            raw = self.k.candlesticks([q[0]["ticker"] for q in quals], window_open, window_open + MINUTE * 60)
            history = minute_quotes(raw, window_open)
        kept = []
        for m, side, top, yb, ya, size in quals:
            if history is None:
                why = "couldn't read its minute-by-minute prices to check the warning signs"
            elif m["ticker"] not in history:
                why = "no minute-by-minute prices to check the warning signs"
            else:
                why = warning(side, yb, ya, history[m["ticker"]])
            if why:
                self.log(now, m, "skip", why, side, top, yb, ya)
            else:
                kept.append((m, side, top, yb, ya, size))
        return kept

    def place(self, now, m, side, top, contracts, stake, n, top_size, yb, ya, sent=None):
        """One order, its limit from limit_for (the ask it saw, while LIMIT_UP is 0). Dry run: filled from the book's
        cheapest offers up to that limit. Live: sent to Kalshi (with its exchange_index: section_of), recorded from its
        fills. sent: a fast window's order that send() already sent, what send_all brought back for it: recorded the
        same way, so long as it is the order place() would have sent, its exchange_index aside. If it isn't, its orders
        row is written and it halts, naming the market, with no bet: reconcile adds any fill from Kalshi's record."""
        limit = self.limit_on(m, top)
        body = order_body(m["ticker"], side, limit, contracts, exchange_index=self.section_of(m))
        mult = self.universe.get(m["series"], {}).get("fee", 1.0)
        order_id = None
        if not self.live:
            if m.get("book") is None:   # no book to walk: what was offered at the ask it saw
                filled = min(contracts, math.floor(top_size + 1e-9))
                cost = filled * top
            else:
                filled, cost = book_fill(m["book"], side, limit, contracts)
            fee = taker_fee(filled, cost / filled, mult) if filled else 0.0
        else:
            if sent is not None:
                body, status, data = sent["body"], sent["status"], sent["data"]
            else:
                try:
                    status, data = self.k.create_order(body)
                except requests.RequestException as e:  # the order may or may not have reached Kalshi
                    status, data = None, f"network error: {e}"
            self.db.execute("INSERT INTO orders (ts, ticker, client_order_id, request, http_status, response) VALUES (?,?,?,?,?,?)",
                            (now, m["ticker"], body["client_order_id"], json.dumps(body), status, json.dumps(data)))
            if sent is not None and {k: v for k, v in body.items() if k != "exchange_index"} != \
                    order_body(m["ticker"], side, limit, contracts):
                self.log(now, m, "error", f"the order sent isn't the one it built: {json.dumps(body)[:120]}", side, top, yb, ya)
                set_halt(now, f"the order sent on {m['ticker']} isn't the one it built; check it on kalshi.com")
                return False
            if status is None:  # the order may have reached Kalshi: record whatever filled before calling it failed
                filled, cost, fee = self.fills_for(ticker=m["ticker"], side=side)
            elif status not in (200, 201) or not isinstance(data, dict):
                filled = None
            else:
                # The order's own fill count is the authority; its fills give the exact prices and fees, and can
                # take a moment to appear. Until they do, count the contracts at our limit price.
                order_id = data.get("order_id")
                want = float(data.get("fill_count") or 0)
                if float(data.get("remaining_count") or 0) > 0:   # immediate-or-cancel should never rest: take it off
                    self.cancel(now, order_id, m["ticker"], f"order on {m['ticker']} came back with "
                                f"{float(data['remaining_count']):g} contracts resting on the book")
                filled, cost, fee = 0.0, 0.0, 0.0
                for attempt in range(3 if want > 0 else 0):
                    filled, cost, fee = self.fills_for(order_id=order_id, side=side)
                    if filled is not None and filled + 1e-9 >= want:
                        break
                    time.sleep(0.5)
                if want > 0 and (filled is None or filled + 1e-9 < want):
                    filled, cost, fee = want, want * limit, taker_fee(want, limit, mult)
            failed = filled is None or status is None
            refused = failed and price_refused(status, data)
            if not failed:
                self.errors = self.price_errors = 0
            elif refused:
                self.price_errors += 1     # its own count, so ordinary luck in the send order can't halt the bot
            else:
                self.errors += 1
            if failed:
                self.log(now, m, "error", f"order failed ({status}): {str(data)[:120]}", side, top, yb, ya)
                if self.errors >= MAX_ORDER_ERRORS:
                    set_halt(now, f"{self.errors} orders failed in a row")
                elif self.price_errors >= MAX_PRICE_ERRORS:
                    set_halt(now, f"{self.price_errors} orders refused for their price in a row")
                if not filled:
                    return False
            # Past the limit, or more than it asked, halts (with LIMIT_UP set, over the ask but within the limit is normal).
            if filled > contracts + 1e-9 or (filled and cost / filled > limit + 1e-6):
                set_halt(now, f"unexpected fill on {m['ticker']}: {filled} at {cost / filled:.4f}, asked {contracts} at {limit:.4f}")
        if filled <= 0:
            self.log(now, m, "skip", "not filled: nobody selling at that price", side, top, yb, ya)
            return False
        self.db.execute("INSERT OR IGNORE INTO bets (ticker, series, window_open, close_ts, side, price, contracts, cost, fee,"
                        " placed_ts, order_id, client_order_id, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?, 'open')",
                        (m["ticker"], m["series"], m["open"], m["close"], side, cost / filled, filled, cost, fee, now,
                         order_id, body["client_order_id"]))
        cap = f" (window cap: {n} bets)" if n * CAP_PCT > WINDOW_CAP else ""
        self.log(now, m, "bet", f"{'bought' if self.live else 'would buy'} {side.upper()} {filled:.0f} at {cost / filled * 100:.1f}c"
                 f" (${stake:.2f} a bet{cap})", side, top, yb, ya)
        return True

    def fills_for(self, side, order_id=None, ticker=None):
        """(contracts, cost, fees) from Kalshi's fills for an order or a market; None if it couldn't be read. Each fill it
        counts is kept in the fills table once, by its trade ID, so the dashboard can tell what each price bought; the
        step loop's commit saves them."""
        params = {"order_id": order_id} if order_id else {"ticker": ticker}
        d = self.k.fills(**params, limit=100)
        if d is None:
            return None, None, None
        contracts = cost = fee = 0.0
        for f in d.get("fills", []):
            if f.get("outcome_side", side) != side:
                continue
            c = float(f["count_fp"])
            price = float(f["yes_price_dollars"] if side == "yes" else f["no_price_dollars"])
            paid = float(f.get("fee_cost") or 0)
            contracts += c
            cost += c * price
            fee += paid
            if trade_id := f.get("trade_id") or f.get("fill_id"):   # nothing to key it by: counted, not kept
                self.db.execute("INSERT OR IGNORE INTO fills (trade_id, order_id, ticker, side, price, count, fee, ts)"
                                " VALUES (?,?,?,?,?,?,?,?)",
                                (trade_id, f.get("order_id") or order_id, f.get("ticker") or f.get("market_ticker") or ticker,
                                 side, price, c, paid, ts(f["created_time"]) if f.get("created_time") else None))
        return contracts, cost, fee

    def cancel(self, now, order_id, ticker, why):
        """Take one of its orders off the book, and halt: its orders are immediate-or-cancel, so one left resting means
        Kalshi didn't treat it as one. If the cancel fails, the next sweep tries again. True if it went through."""
        try:
            status, data = self.k.cancel_order(order_id, ticker)
        except requests.RequestException as e:
            status, data = None, f"network error: {e}"
        self.db.execute("INSERT INTO orders (ts, ticker, client_order_id, request, http_status, response) VALUES (?,?,?,?,?,?)",
                        (now, ticker, client_order_id(ticker), json.dumps({"cancel": order_id}), status, json.dumps(data)))
        ok = status in (200, 204)
        done = "cancelled it" if ok else (f"couldn't cancel it ({'no answer from Kalshi' if status is None else f'HTTP {status}'}):"
                                          f" it tries again every {RESTING_EVERY}s; check kalshi.com")
        print(f"{iso(now)} {ticker:<32} cancel  {why}; {done}", flush=True)
        set_halt(now, f"{why}; {done}")
        return ok

    def sweep(self, now):
        """Live: every RESTING_EVERY seconds, cancel any of its own orders resting on the book (orders it didn't place,
        such as ones made by hand on kalshi.com, are left alone). It runs while halted too, so nothing stays queued."""
        if not self.live or now - self.last_sweep < RESTING_EVERY:
            return
        self.last_sweep = now
        d = self.k.list_orders(status="resting", limit=200)
        for o in (d or {}).get("orders") or []:   # unreadable: Kalshi being down halts on its own ("down")
            if o.get("client_order_id") == client_order_id(o.get("ticker", "")):
                self.cancel(now, o["order_id"], o["ticker"], f"order on {o['ticker']} was left resting on the book")

    def reconcile(self, now):
        """Live: every RECONCILE_EVERY seconds, its own orders that bought contracts but are missing from its records
        (an order whose answer was lost and that filled anyway, or a crash before it saved one) are added from Kalshi's
        record of its orders, so the P&L, the window cap and the halts count them. It runs while halted too."""
        if not self.live or now - self.last_reconcile < RECONCILE_EVERY:
            return
        self.last_reconcile = now
        back = RECONCILE_BACK if self.reconciled else 86400
        orders, cursor = [], None
        for _ in range(25):   # 200 a page: a day of its orders is about 3
            d = self.k.order_history(now - back, cursor)
            if d is None:
                return
            orders += d.get("orders") or []
            cursor = d.get("cursor")
            if not cursor:
                break
        self.reconciled = True
        known = {r[0] for r in self.db.execute("SELECT ticker FROM bets")}
        ours = [o for o in orders if o.get("client_order_id") == client_order_id(o.get("ticker", ""))]
        missing = {o["ticker"]: o for o in ours
                   if o.get("ticker") not in known
                   and float(o.get("fill_count_fp") or 0) > 0 and o.get("outcome_side") in ("yes", "no") and o.get("created_time")}
        # One that bought nothing, in a market it has no decision on (a crash before it saved one): decided now, so the
        # market is never sent a second order.
        decided = {r[0] for r in self.db.execute("SELECT ticker FROM decisions")}
        for t in sorted({o["ticker"] for o in ours if not float(o.get("fill_count_fp") or 0)} - decided - set(missing) - known):
            why = "an order already went out on it and bought nothing: found in Kalshi's record of its orders, missing from its own"
            self.db.execute("INSERT OR IGNORE INTO decisions (ts, ticker, series, action, reason) VALUES (?,?,?,'skip',?)",
                            (now, t, t.split("-")[0], why))
            print(f"{iso(now)} {t:<32} skip    {why}", flush=True)
        tickers = sorted(missing)
        times = {}
        for i in range(0, len(tickers), 50):
            d = self.k.markets(tickers=",".join(tickers[i:i + 50]), limit=100)
            times.update({m["ticker"]: (ts(m["open_time"]), ts(m["close_time"])) for m in (d or {}).get("markets", [])
                          if m.get("open_time") and m.get("close_time")})
        for t in tickers:
            if t not in times:   # its market couldn't be looked up: the next check tries again, decided meanwhile
                why = ("an order of its own already bought here (found in Kalshi's record of its orders): its bet goes in"
                       " once its market can be looked up")
                self.db.execute("INSERT OR IGNORE INTO decisions (ts, ticker, series, action, reason) VALUES (?,?,?,'skip',?)",
                                (now, t, t.split("-")[0], why))
                continue
            o, (opened, closes) = missing[t], times[t]
            side, filled = o["outcome_side"], float(o["fill_count_fp"])
            cost = float(o.get("taker_fill_cost_dollars") or 0) + float(o.get("maker_fill_cost_dollars") or 0)
            fee = float(o.get("taker_fees_dollars") or 0) + float(o.get("maker_fees_dollars") or 0)
            self.db.execute("INSERT OR IGNORE INTO bets (ticker, series, window_open, close_ts, side, price, contracts, cost, fee,"
                            " placed_ts, order_id, client_order_id, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?, 'open')",
                            (t, t.split("-")[0], opened, closes, side, cost / filled, filled, cost, fee, ts(o["created_time"]),
                             o.get("order_id"), o["client_order_id"]))
            why = (f"bought {filled:g} {side.upper()} at {cost / filled * 100:.1f}c: found in Kalshi's record of its orders,"
                   " missing from its own")
            self.db.execute("INSERT INTO decisions (ts, ticker, series, fav_side, fav_price, action, reason) VALUES (?,?,?,?,?,'bet',?)"
                            " ON CONFLICT(ticker) DO UPDATE SET action='bet', reason=excluded.reason",
                            (now, t, t.split("-")[0], side, cost / filled, why))
            print(f"{iso(now)} {t:<32} bet     {why}", flush=True)

    def settle(self, now):
        """Open bets, and open paper rows of every kind (shadow), whose markets have closed: looked up together and
        settled from each market's result. A paper row's P&L is its extra contracts' as if they had been bought; an
        unread one is never settled."""
        open_bets = self.db.execute("SELECT * FROM bets WHERE status='open' AND close_ts <= ?", (now - 2,)).fetchall()
        paper = self.db.execute("SELECT * FROM shadow WHERE status='open' AND close_ts <= ?", (now - 2,)).fetchall()
        tickers = list(dict.fromkeys([b["ticker"] for b in open_bets] + [p["ticker"] for p in paper]))   # each once
        results = {}
        for i in range(0, len(tickers), 50):
            d = self.k.markets(tickers=",".join(tickers[i:i + 50]), limit=100)
            for raw in (d or {}).get("markets", []):
                if raw.get("result") in ("yes", "no"):
                    results[raw["ticker"]] = (raw["result"], ts(raw["settlement_ts"]) if raw.get("settlement_ts") else now)
        for b in open_bets:
            if b["ticker"] in results:
                r, when = results[b["ticker"]]
                payout = b["contracts"] if b["side"] == r else 0.0
                self.db.execute("UPDATE bets SET status=?, result=?, payout=?, pnl=?, settled_ts=? WHERE id=?",
                                ("won" if payout else "lost", r, payout, payout - b["cost"] - b["fee"], max(when, b["placed_ts"]), b["id"]))
        for p in paper:
            if p["ticker"] in results:
                r, when = results[p["ticker"]]
                self.db.execute("UPDATE shadow SET status='settled', result=?, pnl=?, settled_ts=? WHERE id=?",
                                (r, (p["extra"] if p["side"] == r else 0.0) - p["cost"] - p["fee"], when, p["id"]))

    def nothing_listed(self, now, window_open):
        """A window Kalshi listed no markets for. Said out loud and counted, once a window rather than once a poll:
        an empty listing is indistinguishable from a quiet hour, and that silence is what let a listing filter that
        had stopped matching cost 27 windows on Oct 24 with nothing in the log. HALT_EMPTY_WINDOWS running halts it."""
        if self.missed == window_open:
            return
        self.missed, self.empty = window_open, self.empty + 1
        print(f"{iso(now)} no markets listed for the {datetime.fromtimestamp(window_open, ET):%H:%M} ET window"
              f" ({len(self.edge_series())} series asked, {self.empty} windows running)", flush=True)

    def unconfirmed(self, now, window_open):
        """A window it doesn't enter: live, and since it started it hasn't been able to read Kalshi's record of its
        orders, so an order it sent just before a restart, and never saved, could go out a second time (reconcile tries
        that record again within a minute). Said once a window, not once a poll."""
        if self.unsure != window_open:
            self.unsure = window_open
            print(f"{iso(now)} not entering the {datetime.fromtimestamp(window_open, ET):%H:%M} ET window: Kalshi's record of"
                  " its orders hasn't been read since it started, and an order sent just before a restart mustn't go out"
                  " twice", flush=True)

    def step(self, now):
        """One step of the loop, at `now` on Kalshi's clock. In a fast window: the housekeeping and the prep at 450 s,
        nothing but a warm-up until the mark, then at the mark only the halts, the books and the orders; the
        housekeeping runs again the step after, once the orders are out. Any other step: the housekeeping, then the
        entry when minute 8 has come, or a fast window's prep in its slot."""
        self.mark = self.clock()
        window_open = now - now % 900
        into = now - window_open
        due = MINUTE * 60 <= into <= MINUTE * 60 + GRACE and self.done_window != window_open
        prep = self.prepared.get(window_open)
        if self.live and not self.reconciled:   # since its start, Kalshi's record of its orders unread: the housekeeping
            prep = None                         # (and its look at that record) first, and no entry until it has read
        if prep is not None and due:   # a fast window's mark
            if self.halts:   # losses settled since the prep count first
                check_halts(self.db, now, self.trading, self.reachable, self.floor, self.empty)
            self.done_window, self.empty = window_open, 0
            self.decide_window(now, window_open, self.books([dict(m) for m in prep["markets"]]), prep)
        elif prep is not None and into < MINUTE * 60:   # from its prep to its mark: nothing that could hold the mark up
            if into >= MINUTE * 60 - POLL and self.warmed != window_open:   # the last poll before it
                self.warm(window_open)
        else:
            if now - self.last_catalog > CATALOG_EVERY and self.load_catalog():
                self.last_catalog = now
            if now - self.last_status > STATUS_EVERY:
                status = self.k.exchange_status()
                self.last_status, self.trading, self.reachable = now, trading_on(status), status is not None
                if status:
                    self.section = crypto_section(status)
            self.settle(now)
            self.sweep(now)
            self.reconcile(now)   # before any entry: a bet a crash didn't save mustn't be placed again
            if self.halts:  # a paper account's losses must never halt the real one
                check_halts(self.db, now, self.trading, self.reachable, self.floor, self.empty)  # before any entry: losses that just settled count first
            self.sync_clock(now, into)
            if due and self.live and not self.reconciled:
                self.unconfirmed(now, window_open)
            elif due:   # as before fast entry, and a fast window whose prep was missed (a start at 470 s, say)
                markets = self.window_markets(window_open)
                if markets:
                    self.done_window, self.empty = window_open, 0
                    self.decide_window(now, window_open, markets)
                else:   # Kalshi listed nothing: try again next loop, but never in silence
                    self.nothing_listed(now, window_open)
            elif self.fast(window_open) and self.fe.PREP <= into < MINUTE * 60:
                self.prepare(now, window_open)
        set_meta(self.db, "heartbeat", now)
        self.db.commit()
        self.mark = None

    def sync_clock(self, now, into):
        """While fast entry is on, a time server's reading of how far real time is ahead of the PC's clock
        (fast_entry.ntp_offset, up to half a second), every NTP_EVERY s but never from 10 s before the prep to the end of
        entry (into: seconds into the window). A reading that fails keeps the last one."""
        if self.fe is None or self.fe.START is None or now - self.last_ntp < NTP_EVERY \
                or self.fe.PREP - 10 <= into <= MINUTE * 60 + GRACE:
            return
        self.last_ntp = now
        got = self.fe.ntp_offset()
        if got is not None:
            self.ntp = got

    def run_step(self, now, carry_on=False):
        """One step. Its records found locked by another program isn't a crash: what the step couldn't save stays in
        hand and goes in with the next save, and a lock lasting LOCK_HALT seconds halts. Any other error stops a dry
        or live run; carry_on (a paper account) logs it and goes on."""
        try:
            self.step(now)
        except sqlite3.OperationalError as e:
            if "locked" not in str(e):
                return self.failed(now, e, carry_on)
            self.locked_since = self.locked_since or now
            print(f"{iso(now)} its records are locked by another program ({e}); it tries again next loop", flush=True)
            if self.halts and now - self.locked_since >= LOCK_HALT:
                set_halt(now, f"its records have been locked for {(now - self.locked_since) / 60:.0f} minutes by another"
                              " program (antivirus, a backup or a sync app holding state/)")
            return
        except Exception as e:
            return self.failed(now, e, carry_on)
        self.locked_since = None

    @staticmethod
    def failed(now, e, carry_on):
        if not carry_on:
            raise e
        print(f"{iso(now)} error, carrying on: {e!r}", flush=True)


# ------------------------------------------------------------------ command line
BOT_PORT = 47864           # the localhost port a trading loop holds while it runs, so a second bot stops at once
                           # (notify.py holds 47863; the dashboards serve on 8080 and 9000)


def hold_port(port):
    """Bind this localhost port and keep it, or None if another program has it: one running copy at a time. Windows
    lets the port go the moment the process ends, however it ends, so a crash never leaves it held. No SO_REUSEADDR:
    on Windows it would let a second copy bind the port too."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
    except OSError:
        s.close()
        return None
    return s


def state_path(live, env, paper=False):
    return os.path.join(STATE, f"{'live' if live else 'paper' if paper else 'dry'}-{env}.db")


def broke(db):
    """Where a paper account stops: nothing left riding and too little for a $1 bet at CAP_PCT (under MIN_BET / CAP_PCT)."""
    return stake_for(bankroll(db), 1) < MIN_BET and not db.execute("SELECT 1 FROM bets WHERE status='open'").fetchone()


def status_line(db):
    start, bal = float(get_meta(db, "start")), bankroll(db)
    r = db.execute("SELECT COUNT(*), SUM(status='won'), SUM(status='lost'), SUM(status='open') FROM bets").fetchone()
    return f"${bal:.2f} settled from ${start:.2f} ({bal / start - 1:+.1%}) · {r[1] or 0} won, {r[2] or 0} lost, {r[3] or 0} open"


def nap(started, offset=0.0, clock=None):
    """How long the loop sleeps after a step that began at `started` (the PC's clock): until the next poll, or sooner for
    a fast window's prep or mark (fast_entry.next_wake), which are on Kalshi's clock: the PC's plus offset. Never
    negative. With fast entry off (START None) or without fast_entry.py, the rest of the 3 s poll, as ever. The clock is
    read when it's called (time.time unless given)."""
    fe = fast_entry_module()
    wake = started + POLL if fe is None else fe.next_wake(started, fe.START, POLL, offset=offset)
    return max(0.0, wake - (clock or time.time)())


def start_reader(bot, env):
    """For a live run: the paper fast entry's reader (fast_entry.MarkReader), a background thread on a public Kalshi
    client of its own (no key: it only reads order books) that reads every order book of the window at minute 8
    exactly, for fast_shadow(). Started and handed to the bot. Without fast_entry.py beside bot.py, or with a reader
    that won't build or start, it says so and returns None, and the bot trades as ever: a paper experiment must never
    keep real trading from starting."""
    try:
        import kalshi_bot.fast_entry as fast_entry   # here, not at the top: bot.py still runs without fast_entry.py
    except ImportError:
        print("fast_entry.py isn't beside bot.py: no paper fast entry", flush=True)
        return None
    try:
        reader = fast_entry.MarkReader(Kalshi(env), bot.edge_series)
        reader.start()
    except Exception as e:
        print(f"no paper fast entry: its reader wouldn't start ({e})", flush=True)
        return None
    bot.reader = reader
    print("paper fast entry: in the background it reads every order book at minute 8 exactly, to see what an order sent"
          " that instant would have bought", flush=True)
    return reader


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--live", action="store_true", help="place real orders (default: dry run, no orders)")
    ap.add_argument("--paper", action="store_true",
                    help="a dry run with its own $100 account that ignores every halt and keeps going until it's broke")
    ap.add_argument("--env", choices=("demo", "prod"), help="Kalshi environment (default: KALSHI_ENV, else demo)")
    ap.add_argument("--yes", action="store_true", help="skip the confirmation prompt for --live on prod")
    ap.add_argument("--check", action="store_true", help="check the API key: show the balance, place nothing")
    ap.add_argument("--halt", nargs="?", const="stopped by hand", help="stop every mode from placing orders")
    ap.add_argument("--resume", action="store_true", help="lift a halt")
    ap.add_argument("--status", action="store_true", help="show every mode's account and halt")
    ap.add_argument("--fund-crypto", nargs="?", const="all", metavar="DOLLARS",
                    help="move cash from Kalshi's Default section to Crypto & Commodities, where these markets"
                         " trade (all of it unless you give an amount); asks you to confirm")
    ap.add_argument("--rebase", action="store_true",
                    help="restart the live bot's books from the cash now in Crypto & Commodities, keeping its history:"
                         " for money you've added (only with no bets open); asks you to confirm")
    ap.add_argument("--once", action="store_true", help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    if a.paper and a.live:
        ap.error("--paper never places orders: leave out --live")
    cfg = load_env()
    env = a.env or cfg.get("KALSHI_ENV", "demo")
    now = time.time()

    if a.halt is not None or a.resume or a.status:  # one halt for every mode; `--halt ""` is still a halt
        dbs = {os.path.basename(p): connect(p) for p in sorted(glob.glob(os.path.join(STATE, "*.db")))}
        dbs = {name: db for name, db in dbs.items() if get_meta(db, "start") is not None}
        if a.halt is not None:
            set_halt(now, a.halt or "stopped by hand", "you")
        elif a.resume:
            h = clear_halt(now, dbs.values())
            print(f"resumed (was halted since {h['ts']}: {h['reason']})" if h else "wasn't halted")
        h = halt_info()
        print(f"HALTED since {h['ts']} ({h['by']}): {h['reason']}" if h else "not halted")
        for name, db in dbs.items():
            print(f"  {name:<16} {status_line(db)}")
        nxt = next(((x, w) for x, y, w in BLACKOUTS if ts(y) > now), None)
        print(f"next blackout: {nxt[1]}, {datetime.fromtimestamp(ts(nxt[0]), ET):%a %b %d %I:%M %p} ET" if nxt else "no blackouts scheduled")
        return

    key_id, key_path = cfg.get("KALSHI_API_KEY_ID"), cfg.get("KALSHI_PRIVATE_KEY_PATH")
    k = Kalshi(env, key_id, key_path) if key_id and key_path else Kalshi(env)

    if a.check or a.live or a.fund_crypto or a.rebase:
        if not k.authed:
            sys.exit("needs KALSHI_API_KEY_ID and KALSHI_PRIVATE_KEY_PATH in .env (see .env.example)")
        b = k.balance()
        if not b or "balance" not in b:
            sys.exit(f"couldn't read the {env} account balance. Kalshi said: {k.last_error}\n"
                     f"Check the key ID and key file, and that the key was made on {'demo.kalshi.co' if env == 'demo' else 'kalshi.com'}"
                     f" (KALSHI_ENV={env}): demo and real accounts have separate keys.")
        section = crypto_section(k.exchange_status())
        avail = usable_cash(b, section)  # what the bot can bet with: Crypto & Commodities only
        pos = k.positions(count_filter="position")
        print(f"connected to Kalshi {env}: ${b['balance'] / 100:.2f} in the account, ${avail:.2f} of it in the Crypto &"
              f" Commodities section these markets trade in · {len((pos or {}).get('market_positions') or [])} open positions")
        if avail < MIN_BET / CAP_PCT:
            print(f"  The bot needs at least ${MIN_BET / CAP_PCT:.0f} in Crypto & Commodities to place a $1 bet."
                  f" Move cash there with: python bot.py --fund-crypto")
        if a.fund_crypto:
            default = next((float(x["balance"]) for x in b.get("balance_breakdown") or [] if x.get("exchange_index") == 0), 0.0)
            amount = floor_cents(default if a.fund_crypto == "all" else float(a.fund_crypto))
            if amount <= 0 or amount > default + 1e-9:
                sys.exit(f"the Default section has ${default:.2f}: can't move ${amount:.2f}")
            if not a.yes and input(f"Move ${amount:.2f} from Default to Crypto & Commodities? Type MOVE: ").strip() != "MOVE":
                sys.exit("nothing moved")
            status, data = k.transfer(amount, 0, section)
            if status not in (200, 201):
                sys.exit(f"Kalshi refused the transfer ({status}): {data}")
            print(f"transfer {data.get('transfer_id')} sent. Kalshi processes it in the background: check in a minute"
                  " with python bot.py --check")
            return
        if a.rebase:
            path = state_path(True, env)
            if not os.path.exists(path) or get_meta(connect(path), "start") is None:
                sys.exit(f"no {env} ledger yet: its first live run starts from the cash in Crypto & Commodities")
            db = connect(path)
            if db.execute("SELECT 1 FROM bets WHERE status='open'").fetchone():
                sys.exit("it has bets still open: run --rebase once they settle")
            old = bankroll(db)
            print(f"the {env} ledger holds ${old:.2f}; Crypto & Commodities holds ${avail:.2f}")
            elsewhere = sum(float(x["balance"]) for x in b.get("balance_breakdown") or [] if x.get("exchange_index") != section)
            if elsewhere >= 0.01:
                print(f"  ${elsewhere:.2f} more is in other sections, which the bot can't bet from. To count it, move it first"
                      " with: python bot.py --fund-crypto")
            if abs(avail - old) < 0.005:
                print("they match: nothing to change")
                return
            if not a.yes and input(f"Restart the bot's books from ${avail:.2f}? Type REBASE: ").strip() != "REBASE":
                sys.exit("nothing changed")
            rebase(db, avail, now)
            print(f"rebased: ${old:.2f} -> ${avail:.2f}, history kept · bets about ${stake_for(avail, 1):.2f} · halts if it falls"
                  f" {HALT_DAY_DROP:.0%} within 24 hours or reaches ${max(avail * HALT_DEPOSIT, HALT_FLOOR if env == 'prod' else 0.0):.2f}")
            if h := halt_info():
                print(f"still halted ({h['reason']}): it places nothing until python bot.py --resume")
            return
        if a.check:
            return

    # One trading loop at a time, in any mode: two would place every bet twice. Taken before the ledger is touched or
    # anything is said, so a second bot stops having done nothing; let go however this one ends.
    lock = hold_port(BOT_PORT)
    if lock is None:
        sys.exit(f"another bot is already running (it holds localhost port {BOT_PORT}), so this one stops:"
                 " two would place every bet twice")
    try:
        path = state_path(a.live, env, a.paper)
        db = connect(path)
        # The starting bankroll is the available balance, read again at every live start until the first bet,
        # so money that hadn't cleared yet (a new deposit) isn't left out for good.
        first_bet = db.execute("SELECT COUNT(*) FROM bets").fetchone()[0] == 0
        if get_meta(db, "start") is None or (a.live and first_bet):
            set_start(db, avail if a.live else DRY_RUN_START)
        print(f"{'LIVE' if a.live else 'paper' if a.paper else 'dry run'} on {env} · {status_line(db)}")
        if (h := halt_info()) and a.paper:
            print(f"Real money is halted ({h['reason']}). This paper account ignores halts and keeps trading.")
        elif h:
            print(f"HALTED since {h['ts']}: {h['reason']}. It will log what it would do but place nothing until --resume.")
        print(f"{CAP_PCT:.1%} a bet, {WINDOW_CAP:.0%} a window, whole contracts, no cap on an order, skipping 2c+ spreads and late"
              f" favorites · next bet about ${stake_for(bankroll(db), 1):.2f}" + (" · no stop-losses: it runs until it's broke" if a.paper else ""))
        if a.live and env == "prod" and not a.yes:
            if input("Real money. Type LIVE to start placing orders: ").strip() != "LIVE":
                sys.exit("not started")

        bot = Bot(k, db, a.live, halts=not a.paper)
        # A dry run or a paper account sends no real orders to pair. While fast entry is on, every window's orders are
        # paired with the books the bot itself read at the mark, and a reader would only compete with it for reads.
        if a.live and (bot.fe is None or bot.fe.START is None):
            start_reader(bot, env)
        while True:
            started = time.time()
            if a.paper and broke(db):
                print(f"{iso(started)} broke: ${bankroll(db):.2f} left, too little for a $1 bet at {CAP_PCT:.1%}. The paper account has"
                      f" stopped. To start it again from ${DRY_RUN_START:.0f}, delete {path}", flush=True)
                return
            # On Kalshi's clock; a paper account runs until it's broke, not until Kalshi sends something odd
            bot.run_step(started + bot.offset, carry_on=a.paper)
            if a.once:
                break
            time.sleep(nap(started, bot.offset))
    finally:
        lock.close()


def cli():
    """The command line (python bot.py, python -m kalshi_bot): main(), with Ctrl+C a polite stop, not a traceback."""
    try:
        main()
    except KeyboardInterrupt:
        print("stopped", flush=True)


if __name__ == "__main__":
    cli()

