"""Chaos: the live bot as it trades (fast entry in every window, as fast_entry ships), run window after window against
a fake Kalshi that breaks in a different way each window, chosen at random: down altogether, slow, orders timing out
(some of them filled anyway), refused, rate limited, filling nothing or half, left resting on the book, listing
nothing, its record of orders unreadable, a market that never settles as yes or no; and on top of that the bot itself
crashing between sending a window's orders and saving them (systemd starts it again 30 s later), and a person running
--resume some windows after each halt. Each seed is one run of WINDOWS windows.

Whatever breaks, after every step these hold (the README's promises, under Safety and "How long anything may take"):
1. no market gets a second order once one has reached Kalshi (after a crash, one that Kalshi refused or that never
   reached it may be tried again: Kalshi holds one order at most either way);
2. no order goes out while a halt is in force;
3. no order goes out later than 60 s after minute 8 ends (ORDER_DEADLINE), or on an order book read more than 15 s
   before it went out (BOOK_MAX_AGE), by the bot's own stopwatch;
4. at most 20 orders go out a window;
5. no order of its own is left resting on the book at the end of a window Kalshi answered in;
6. every contract Kalshi sold the bot is in its ledger by the end of a window Kalshi answered in, and the ledger
   holds no contract Kalshi didn't sell it;
7. a bet whose market came back with a result other than yes or no is never counted as won or lost;
and no step raises: each of these failures is one the bot says it handles.

FAST_SPACING is 0 here: it only paces orders to Kalshi's write rate, and with sleeps recorded rather than slept, the
pacing would spin on the real clock. Nothing here touches the network or an account.

    python -m pytest tests/test_chaos.py -q
    CHAOS_SEEDS=300 python -m pytest tests/test_chaos.py -q        (more runs)
"""
import collections
import os
import random

import pytest
import requests

from kalshi_bot import bot
from kalshi_bot import fast_entry
from test_bot import start_ledger
from test_fast_entry_bot import Spy, ntp  # noqa: F401 (ntp: no test reaches a time server)
from test_flow import fill, slept  # noqa: F401 (slept: no real sleeps)
from test_reconcile import record
from test_stops import Clock

SEEDS = int(os.environ.get("CHAOS_SEEDS", "40"))
WINDOWS = 24
V = fast_entry.START + 40 * 900      # Oct 14, 2026, 6:00 am ET: no maintenance, no blackout in the next 24 windows
START = 2000.0                       # 1.5% of it, or 10% of it over 10 favourites, buys whole contracts at 96c
# Ten favourites a window, every one a YES favourite at 96c: the orders go out in two batches (FAST_BURST is 8).
SERIES = ["KXBTC15M", "KXETH15M", "KXSOL15M", "KXXRP15M", "KXDOGE15M", "KXBNB15M", "KXHYPE15M",
          "KXGOLD15M", "KXSILVER15M", "KXWTI15M"]
YES = {"yes_dollars": [["0.95", "100"]], "no_dollars": [["0.04", "50"]]}
# A step every minute, and the ones fast entry wakes for: the prep (450 s), the warm-up (477 s), the mark (480 s).
STEPS = [0, 60, 120, 180, 240, 300, 360, 420, 450, 477, 480, 483, 500, 540, 600, 660, 720, 780, 840, 890]
OUTCOMES = ("fill", "timeout", "timeout_filled", "refused", "rate_limited", "no_fill", "partial", "resting")
MODES = ("fine", "fine", "fine", "down", "slow", "slow", "empty", "history_down", "void", "mixed") + OUTCOMES
REFUSED = {"error": {"code": "insufficient_balance", "message": "insufficient balance"}}
LIMITED = {"error": {"code": "too_many_requests", "message": "too many requests"}}


class Crash(BaseException):
    """The bot's process dying mid-step: nothing the step hasn't committed is saved."""


class Chaos(Spy):
    """Spy (every call noted) whose window `mode` decides how Kalshi answers. Kalshi's own truth is kept apart from
    what it tells the bot: `truth`, the contracts it really sold the bot in each market, and order_record, its record of
    the bot's orders (GET /portfolio/orders), which a lost answer doesn't change."""

    def __init__(self, rng):
        super().__init__(books={s: YES for s in SERIES}, cash="100000.0000")
        self.rng, self.mode, self.now, self.bot, self.clock = rng, "fine", 0.0, None, None
        self.truth, self.filled, self.lagging, self.window_of, self.sends, self.read_at = {}, {}, set(), {}, [], {}
        self.reached, self.repeats = set(), []   # markets an order of its has reached Kalshi in; orders sent after one

    def down(self):
        """Kalshi down: every read gives None. Slow, one read in ten runs out of retries and gives None too."""
        return self.mode == "down" or (self.mode == "slow" and self.rng.random() < 0.1)

    # ---- reads: None, as Kalshi.get gives once its retries run out, when Kalshi is down
    def series(self):
        return None if self.down() else super().series()

    def exchange_status(self):
        return None if self.down() else super().exchange_status()

    def balance(self):
        return None if self.down() else super().balance()

    def orderbook(self, ticker):
        with self.lock:   # the last read of a market's book before its order is the one it's priced on (a book read
            self.read_at[ticker] = self.now + self.bot.elapsed()   # again after it, for the paper +1c, comes later)
        return None if self.down() else super().orderbook(ticker)

    def candlesticks(self, tickers, start_ts, end_ts):
        return None if self.down() else super().candlesticks(tickers, start_ts, end_ts)

    def list_orders(self, **p):
        return None if self.down() else super().list_orders(**p)

    def order_history(self, min_ts, cursor=None):
        return None if self.down() or self.mode == "history_down" else super().order_history(min_ts, cursor)

    def markets(self, **p):
        if self.down():
            return None
        if "tickers" in p:   # settle and reconcile look markets up by ticker; Kalshi settles about 8 s after the close
            found = []
            for t in p["tickers"].split(","):
                w = self.window_of[t]
                m = {"ticker": t, "open_time": bot.iso(w), "close_time": bot.iso(w + 900)}
                if self.now >= w + 908 and t in self.results:
                    m.update(result=self.results[t], settlement_ts=bot.iso(w + 908))
                found.append(m)
            return {"markets": found}
        if self.mode == "empty":
            return {"markets": []}
        return super().markets(**p)

    def fills(self, order_id=None, ticker=None, limit=100):
        if self.down():
            return None
        oid = order_id or f"o-{ticker}"
        if order_id is None and ticker in self.lagging:   # a fill that hasn't shown up yet when looked up by market
            return {"fills": []}
        got = self.filled.get(oid, 0)
        if not got:
            return {"fills": []}
        return {"fills": [fill(got, float(self.sent[oid]["price"]))]}

    # ---- writes
    def create_order(self, body):
        self.note("create_order", body=body)
        t, n = body["ticker"], int(body["count"])
        oid = f"o-{t}"
        with self.lock:
            self.orders.append(body)
            self.sent[oid] = body
            sent_at = self.now + self.bot.elapsed()   # and the age, now, of the book it's priced on
            self.sends.append((t, sent_at, bot.halt_info() is not None, sent_at - self.read_at[t]))
            if t in self.reached:
                self.repeats.append(t)
        if self.mode == "down":
            raise requests.ConnectionError("chaos: Kalshi is down")
        how = self.rng.choice(OUTCOMES) if self.mode == "mixed" else self.mode
        if how not in ("refused", "rate_limited"):
            with self.lock:
                self.reached.add(t)
        # what Kalshi really sells it: in full when nothing is wrong with the orders ("fine", "slow", "empty" ...)
        got = {"fill": n, "timeout_filled": n, "partial": n // 2, "resting": n // 2}.get(how, 0 if how in OUTCOMES else n)
        if got:
            with self.lock:
                self.truth[t] = self.truth.get(t, 0) + got
                self.filled[oid] = got
        if how not in ("refused", "rate_limited"):   # it reached Kalshi: in its record, "canceled" if it bought nothing
            with self.lock:
                self.order_record.append(record(t, "yes", got, float(body["price"]), created=self.now))
        if how == "resting":
            with self.lock:
                self.resting.append({"order_id": oid, "client_order_id": body["client_order_id"], "ticker": t,
                                     "remaining_count_fp": f"{n - got}.00"})
        if how in ("timeout", "timeout_filled"):
            if how == "timeout_filled" and self.rng.random() < 0.5:
                self.lagging.add(t)
            raise requests.ReadTimeout("chaos: no answer in 5 s")
        if how == "refused":
            return 400, REFUSED
        if how == "rate_limited":
            return 429, LIMITED
        return 201, {"order_id": oid, "fill_count": f"{got}.00",
                     "remaining_count": f"{n - got if how == 'resting' else 0}.00"}

    def cancel_order(self, order_id, ticker):
        if self.mode == "down":
            raise requests.ConnectionError("chaos: Kalshi is down")
        return super().cancel_order(order_id, ticker)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(bot, "FAST_SPACING", 0.0)
    return start_ledger(tmp_path, monkeypatch, START)


def booted(fake, db):
    """A bot process starting: a new Bot, on a stopwatch the fake can move, with nothing kept in memory from before."""
    bot._since.clear()
    b = bot.Bot(fake, db, True)
    b.clock = Clock()
    fake.bot, fake.clock = b, b.clock
    return b


def ledger(db):
    return {r["ticker"]: r for r in db.execute("SELECT * FROM bets")}


@pytest.mark.parametrize("seed", range(SEEDS))
def test_whatever_kalshi_does_the_safety_rules_hold(env, monkeypatch, seed):
    rng = random.Random(seed)
    fake = Chaos(rng)
    b = booted(fake, env)
    crash = {"armed": False}
    real_place = bot.Bot.place

    def place(self, *a, **kw):   # the crash: after the window's orders went out, before the first is saved
        if crash["armed"] and kw.get("sent") is not None:
            crash["armed"] = False
            raise Crash()
        return real_place(self, *a, **kw)
    monkeypatch.setattr(bot.Bot, "place", place)

    # Slow: calls made together finish together, once the slowest is back, so the time is added per group. The mark's
    # book reads, up to 50 s (a read that keeps timing out, its retries' sleeps and all), though half the time up to 20 s:
    # the books' 15 s limit is where a slow batch matters; each batch of orders, up to 8.05 s (3.05 s to connect and 5
    # for the answer, then the order timeout gives up).
    real_books, real_send_all = bot.Bot.books, fast_entry.send_all

    def books(self, markets):
        got = real_books(self, markets)
        if fake.mode == "slow" and markets:
            self.clock.add(rng.uniform(0, rng.choice((20, 50))))
        return got

    def send_all(k, bodies, **kw):
        got = real_send_all(k, bodies, **kw)
        if fake.mode == "slow":
            fake.clock.add(rng.uniform(0, 8.05))
        return got
    monkeypatch.setattr(bot.Bot, "books", books)
    monkeypatch.setattr(fast_entry, "send_all", send_all)

    unsettled, halted_since, story = {}, None, []
    for k in range(WINDOWS):
        w = V + 900 * k
        mode = rng.choice(MODES)
        story.append(mode)
        fake.mode, fake.window, fake.suffix = mode, w, f"W{k}"
        for s in SERIES:
            t = f"{s}-W{k}"
            fake.window_of[t] = w
            if mode == "void":
                fake.results[t] = rng.choice(["", "void", "scalar"])
                unsettled[t] = k
            else:
                fake.results[t] = "yes" if rng.random() < 0.95 else "no"
        for t, since in list(unsettled.items()):   # 4 windows on, Kalshi settles it after all (or a person fixes it)
            if k - since >= 4:
                fake.results[t] = "yes"
                del unsettled[t]
        crash["armed"] = mode not in ("down", "empty") and rng.random() < 0.15
        if bot.halt_info():   # a person resumes a halt some windows after it fired
            halted_since = k if halted_since is None else halted_since
            if k - halted_since >= rng.randint(1, 3):
                bot.clear_halt(w, [env])
                halted_since = None
        steps, i = list(STEPS), 0
        if mode == "slow" and rng.random() < 0.5:   # a loop slow enough to reach the mark late, within its 45 s grace
            steps = [s for s in STEPS if s < 480] + [480 + rng.uniform(0, bot.GRACE)] + [s for s in STEPS if s > 525]
        while i < len(steps):
            at, i = steps[i], i + 1
            now = w + at
            fake.now = now
            was_halted = bot.halt_info() is not None
            before = len(fake.sends)
            try:
                b.step(now)
            except Crash:
                env.rollback()                      # the step's saves die with the process
                b = booted(fake, env)               # systemd starts it again 30 s later (RestartSec=30)
                steps, i = [at + 30] + [s for s in STEPS if s > at + 30], 0
                continue
            where = f"seed {seed}, window {k} ({mode}), {at} s; windows so far: {story}"
            new = fake.sends[before:]
            # 1. one order per market, once one has reached Kalshi
            assert not fake.repeats, f"a second order on {fake.repeats}: {where}"
            # 2. nothing while halted
            assert not (was_halted and new), f"{len(new)} orders went out while halted: {where}"
            assert not any(h for _, _, h, _ in new), f"an order went out after a halt fired: {where}"
            # 3. nothing past the deadline, and nothing priced on a book read more than 15 s before it went out
            for t, sent_at, _, age in new:
                late = sent_at - (fake.window_of[t] + bot.MINUTE * 60)
                assert late <= bot.ORDER_DEADLINE + 1e-6, f"{t} sent {late:.1f}s after minute 8 ended: {where}"
                assert age <= bot.BOOK_MAX_AGE + 1e-6, f"{t} sent on a book read {age:.1f}s before: {where}"
            # 4. at most 20 a window
            per_window = collections.Counter(fake.window_of[t] for t, *_ in fake.sends)
            assert max(per_window.values(), default=0) <= bot.MAX_ORDERS_PER_WINDOW, where
        where = f"seed {seed}, end of window {k} ({mode}); windows so far: {story}"
        if mode not in ("down", "slow"):
            # 5. nothing of its own left resting
            assert not fake.resting, f"left resting: {fake.resting}: {where}"
            # 6. its ledger is Kalshi's truth, both ways, once Kalshi's record of its orders could be read
            if mode != "history_down":
                held = {t: r["contracts"] for t, r in ledger(env).items() if r["contracts"] > 0}
                assert held == fake.truth, f"ledger {held} vs Kalshi {fake.truth}: {where}"
        # 7. a result other than yes or no never settles a bet
        for t, r in ledger(env).items():
            if fake.results.get(t) not in ("yes", "no"):
                assert r["status"] == "open", f"{t} came back {fake.results.get(t)!r} and was marked {r['status']}: {where}"
