"""Fast entry wired into the bot (research/kalshi_15min/lab/fast_entry/timing.md).

The plan: in a "fast" window (fast_entry.arm flips each window's coin) the bot does its prep at 450 s: it lists the
window's markets and reads their minute-by-minute prices and the balance. At the mark (480 s on Kalshi's clock) it
skips the housekeeping, reads the order books, builds every order under the same rules, and reserves each one's cash
and place under the caps as it's built. Then it sends them all at once through fast_entry.send_all, with Kalshi's
"exchange_index" (the section the market trades in) on each, and records each answer with place(..., sent=) on its own
thread. A sent order that isn't what place() would have built halts. Kalshi's clock offset comes from the order
answers (ClockSync) or a time server (ntp_offset), and the main loop steps and sleeps on it (nap).

With fast_entry.START None, the off switch, the bot must behave exactly as before: no prep, today's sleeps, one order
at a time, no offset. (Live orders carry the exchange_index in every window since Oct 14.)

How: against a fake Kalshi that notes every call, in order and with its thread. fast_entry ships with START set and
EVERY on (every window fast, no coin: test_fast_live.py tests that); here every test starts from START None and the coin
(EVERY False), so the randomized path stays tested. The tests that need it set fast_entry.START to a day before the
windows they use, and arm() picks a fast window (FAST) and a normal one (NORMAL). fast_entry.ntp_offset is
always replaced, so no test reaches a time server. Sleeps are recorded, not slept, and nothing touches the network or
an account.

    python -m pytest tests/test_fast_entry_bot.py -q
"""
import collections
import inspect
import json
import threading
import types

import pytest
import requests

from kalshi_bot import bot
from kalshi_bot import fast_entry
from test_bot import THREE_DOLLAR_START, W, decisions, fake_bet, start_ledger
from test_cli import NOW, cli  # noqa: F401 (cli is a fixture)
from test_day_drop import open_bet
from test_flow import BTC, ETH, GOLD, NO98, YES96, bets, bot_for, fill, mk, slept  # noqa: F401 (slept: no real sleeps)
from test_reconcile import Recorded, record


@pytest.fixture
def env(tmp_path, monkeypatch):
    """test_bot.py's ledger, from $200: 1.5% of it is the $3 stake (3 contracts at 96c) these tests were written around."""
    return start_ledger(tmp_path, monkeypatch, THREE_DOLLAR_START)


START = W - 96 * 900        # the experiment's start in these tests: a day before W, so every window from W on has its coin


def first(kind):
    w = W
    while fast_entry.arm(w, START, every=False) != kind:   # the coin, whatever EVERY ships as
        w += 900
    return w


FAST, NORMAL = first("fast"), first("normal")
ENTRY_FAST = FAST + bot.MINUTE * 60 + 5
SOL = "KXSOL15M-A"
YES = {"yes_dollars": [["0.95", "100"]], "no_dollars": [["0.04", "50"]]}   # a YES favourite at 96c, as FakeKalshi's BTC
HOUSEKEEPING = {"series", "exchange_status", "markets", "list_orders", "order_history", "candlesticks", "balance"}
Call = collections.namedtuple("Call", "name thread detail")


class Spy(Recorded):
    """FakeKalshi (BTC: a YES favourite at 96c; GOLD: a NO favourite at 98c; ETH at 61c, outside the band) that notes
    every call it gets, in order and with the thread it came on. It's safe to call from many threads at once: a fast
    window reads books and sends orders in parallel. Each order gets ID "o-<ticker>" and fills in full at its own price
    unless the test scripts `order` or `fills`. A fill lookup by market alone finds nothing. A market in a series it
    doesn't list (SOL, in the tests that hand decide_window their markets) has a YES favourite's book at 96c.

    books: by series, as FakeKalshi's. section: the exchange index Kalshi gives Crypto & Commodities, in the exchange
    status and the balance. balances, candles: answers to give first (None for one that can't be read), then the usual.
    stamp(body): Kalshi's ts_ms to put in each order's answer."""

    def __init__(self, books=None, section=2, cash="100.0000", stamp=None, **kw):
        super().__init__(**kw)
        if books is not None:
            self.books = dict(books)
        self.section, self.crypto_cash, self.stamp = section, cash, stamp
        self.calls, self.lock, self.sent = [], threading.Lock(), {}
        self.balances, self.candles = [], []

    def note(self, name, **detail):
        with self.lock:
            self.calls.append(Call(name, threading.current_thread(), detail))

    def mark(self):
        """Where the calls so far end: names(mark) is everything after it."""
        return len(self.calls)

    def names(self, since=0):
        return [c.name for c in self.calls[since:]]

    def series(self):
        self.note("series")
        return {"series": [{"ticker": s, "frequency": "fifteen_min", "category": "Commodities" if "GOLD" in s else "Crypto",
                            "fee_multiplier": 1} for s in [*self.books, "KXCRYPTOLEAD15M"]]}

    def exchange_status(self):
        self.note("exchange_status")
        return {"exchange_active": True, "trading_active": True, "exchange_index_statuses": [
            {"exchange_index": 0, "description": "Default", "exchange_active": True, "trading_active": True},
            {"exchange_index": self.section, "description": "Crypto & Commodities", "exchange_active": True,
             "trading_active": True}]}

    def balance(self):
        self.note("balance")
        if self.balances:
            return self.balances.pop(0)
        return {"balance": 10000, "balance_breakdown": [{"exchange_index": 0, "balance": "0.0000"},
                                                        {"exchange_index": self.section, "balance": self.crypto_cash}]}

    def markets(self, **p):
        self.note("markets", **p)
        return super().markets(**p)

    def orderbook(self, ticker):
        self.note("orderbook", ticker=ticker)
        return {"orderbook_fp": self.books.get(ticker.split("-")[0], YES)}

    def candlesticks(self, tickers, start_ts, end_ts):
        self.note("candlesticks", tickers=tuple(tickers), start=start_ts, end=end_ts)
        if self.candles:
            return self.candles.pop(0)
        return super().candlesticks(tickers, start_ts, end_ts)

    def list_orders(self, **p):
        self.note("list_orders")
        return super().list_orders(**p)

    def order_history(self, min_ts, cursor=None):
        self.note("order_history")
        return super().order_history(min_ts, cursor)

    def create_order(self, body):
        self.note("create_order", body=body)
        oid = f"o-{body['ticker']}"
        with self.lock:
            self.orders.append(body)
            self.sent[oid] = body
            n = len(self.orders)
        if self.raises:
            raise self.raises
        if self.order is not None:
            return self.order(body, n) if callable(self.order) else self.order
        data = {"order_id": oid, "fill_count": body["count"] + ".00", "remaining_count": "0.00"}
        if self.stamp:
            data["ts_ms"] = self.stamp(body)
        return 201, data

    def fills(self, order_id=None, ticker=None, limit=100):
        self.note("fills", order_id=order_id, ticker=ticker)
        if self.fills_data is not None:
            p = {k: v for k, v in (("order_id", order_id), ("ticker", ticker)) if v}
            return self.fills_data(p) if callable(self.fills_data) else self.fills_data
        if order_id is None:
            return {"fills": []}
        body = self.sent[order_id]
        yes = float(body["price"]) + (self.bump if body["side"] == "bid" else -self.bump)
        return {"fills": [fill(int(body["count"]), yes, "yes" if body["side"] == "bid" else "no")]}


def no_order(body, n):
    pytest.fail("place() sent an order of its own")


def prep_for(*markets, cash=100.0):
    """What prepare() keeps for a window, written out: the markets as listed (no books), minute-by-minute prices with
    no quotes in them (so no warning sign fires), and the live cash."""
    return {"markets": [{k: v for k, v in m.items() if k != "book"} for m in markets],
            "history": {m["ticker"]: {} for m in markets}, "cash": cash}


def answer(body, status=201, fill_count=None, **extra):
    """What send_all hands back for one body that Kalshi answered."""
    data = {"order_id": "o1", "fill_count": fill_count or body["count"] + ".00", "remaining_count": "0.00", **extra}
    return {"body": body, "status": status, "data": data, "sent": FAST + 480.0, "answered": FAST + 480.1}


def started(fake, db, w=FAST, live=True, at=455):
    """A bot that has stepped into window w at `at` seconds (by default a fast window's prep)."""
    fake.window = w
    b = bot.Bot(fake, db, live)
    b.step(w + at)
    return b


def place_with(b, sent, ticker=BTC, side="yes", top=0.96, book=YES96):
    yb, ya = bot.top_of_book(book)[:2]
    return b.place(FAST + 480, mk(ticker, book, FAST), side, top, 3, 3.0, 1, 50.0, yb, ya, sent=sent)


def orders_rows(db):
    return [dict(r) for r in db.execute("SELECT * FROM orders ORDER BY id")]


# ------------------------------------------------------------------ fixtures
@pytest.fixture(autouse=True)
def off_and_the_coin(monkeypatch):
    """Every test starts with fast entry off (START None) and the coin (EVERY False); `on` sets the start."""
    monkeypatch.setattr(fast_entry, "START", None)
    monkeypatch.setattr(fast_entry, "EVERY", False)


@pytest.fixture
def on(monkeypatch):
    """The experiment running: every window from W on has its coin."""
    monkeypatch.setattr(fast_entry, "START", START)


@pytest.fixture(autouse=True)
def ntp(monkeypatch):
    """No test reaches a time server: fast_entry.ntp_offset is replaced. It gives `answers` in turn (None once they run
    out) and notes each call."""
    box = types.SimpleNamespace(calls=[], answers=[])

    def fake(*a, **kw):
        box.calls.append((a, kw))
        return box.answers.pop(0) if box.answers else None
    monkeypatch.setattr(fast_entry, "ntp_offset", fake, raising=False)
    return box


@pytest.fixture
def sends(monkeypatch):
    """Every call to fast_entry.send_all, its arguments bound by name. It still sends (through the real one); a test's
    `after(results)` may then change what comes back."""
    real = fast_entry.send_all
    box = types.SimpleNamespace(calls=[], after=None)

    def spy(*a, **kw):
        args = inspect.signature(real).bind(*a, **kw)
        args.apply_defaults()
        box.calls.append(dict(args.arguments))
        got = real(*a, **kw)
        if box.after:
            box.after(got)
        return got
    monkeypatch.setattr(fast_entry, "send_all", spy)
    return box


@pytest.fixture
def watch(monkeypatch):
    """Each call to Bot.place, as (ticker, sent, thread), and the thread of each call to Bot.fills_for."""
    box = types.SimpleNamespace(place=[], fills_for=[])
    real_place, real_fills_for = bot.Bot.place, bot.Bot.fills_for

    def place(self, *a, **kw):
        m = kw.get("m", a[1] if len(a) > 1 else None)
        box.place.append((m["ticker"], kw.get("sent", a[10] if len(a) > 10 else None), threading.current_thread()))
        return real_place(self, *a, **kw)

    def fills_for(self, *a, **kw):
        box.fills_for.append(threading.current_thread())
        return real_fills_for(self, *a, **kw)
    monkeypatch.setattr(bot.Bot, "place", place)
    monkeypatch.setattr(bot.Bot, "fills_for", fills_for)
    return box


# ------------------------------------------------------------------ the settings and a new bot
def test_the_constants():
    assert (bot.FAST_BURST, bot.FAST_SPACING, bot.NTP_EVERY) == (8, 0.1, 900)


def test_a_new_bot_has_nothing_prepared_no_time_server_reading_and_no_clock_samples(env):
    b = bot.Bot(Spy(), env, True)
    assert b.prepared == {} and b.ntp is None and b.last_ntp == 0.0
    assert isinstance(b.clocks, fast_entry.ClockSync) and len(b.clocks) == 0
    assert b.offset == 0.0


def test_a_window_is_fast_only_once_the_experiment_has_started_and_its_coin_says_so(env, monkeypatch):
    b = bot.Bot(Spy(), env, True)
    assert not b.fast(FAST) and not b.fast(NORMAL)          # START None: every window is normal
    monkeypatch.setattr(fast_entry, "START", START)
    assert b.fast(FAST) and not b.fast(NORMAL)
    for w in [W + 900 * i for i in range(20)]:
        assert b.fast(w) == (fast_entry.arm(w, START) == "fast")


# ------------------------------------------------------------------ order_body
@pytest.mark.parametrize("extra", [{}, {"exchange_index": None}])
def test_an_order_body_without_an_exchange_index_is_exactly_as_before(extra):
    assert bot.order_body(BTC, "yes", 0.97, 3, **extra) == {
        "ticker": BTC, "client_order_id": bot.client_order_id(BTC), "side": "bid", "count": "3", "price": "0.9700",
        "time_in_force": "immediate_or_cancel", "self_trade_prevention_type": "taker_at_cross",
        "cancel_order_on_pause": True}


@pytest.mark.parametrize("index, want", [(2, 2), ("2", 2), (5, 5), (0, 0)])   # 0 is Kalshi's Default section: still given
def test_an_order_body_with_an_exchange_index_carries_it_as_a_whole_number(index, want):
    body = bot.order_body(GOLD, "no", 0.99, 3, exchange_index=index)
    assert body == {**bot.order_body(GOLD, "no", 0.99, 3), "exchange_index": want}
    assert type(body["exchange_index"]) is int


# ------------------------------------------------------------------ the pieces prep and the mark share
def test_window_markets_is_the_listing_then_the_books(env):
    fake = Spy()
    b = bot_for(fake, env, False)
    since = fake.mark()
    listed = b.listed(W)
    assert sorted(m["ticker"] for m in listed) == [BTC, ETH, GOLD]
    btc = next(m for m in listed if m["ticker"] == BTC)
    assert (btc["series"], btc["open"], btc["close"]) == ("KXBTC15M", W, W + 900)
    assert "orderbook" not in fake.names(since)                       # a listing reads no book
    got = b.books([dict(m) for m in listed])
    assert fake.names(since).count("orderbook") == 3
    assert next(m for m in got if m["ticker"] == BTC)["book"] == {"yes": [(0.95, 100.0)], "no": [(0.04, 50.0)]}

    def plain(ms):
        return sorted((m["ticker"], m["series"], m["open"], m["close"], json.dumps(m["book"])) for m in ms)
    assert plain(got) == plain(b.window_markets(W))


def test_screen_uses_the_history_its_given_and_reads_the_prices_only_without_one(env):
    fake = Spy()
    b = bot_for(fake, env, False)
    btc = (mk(BTC, YES96), "yes", 0.96, 0.95, 0.96, 50.0)
    gold = (mk(GOLD, NO98), "no", 0.98, 0.02, 0.03, 40.0)
    since = fake.mark()
    kept = b.screen(ENTRY_FAST, FAST, [btc, gold], history={BTC: {6: (0.40, 0.45)}, GOLD: {}})
    assert [q[0]["ticker"] for q in kept] == [GOLD] and "candlesticks" not in fake.names(since)
    assert decisions(env)[BTC] == ("skip", "warning sign: it was 42.5c at minute 6, only just the favorite")
    assert [q[0]["ticker"] for q in b.screen(ENTRY_FAST, FAST, [gold])] == [GOLD]                 # none given: today's
    assert [q[0]["ticker"] for q in b.screen(ENTRY_FAST, FAST, [gold], history=None)] == [GOLD]   # None: the same
    assert fake.names(since).count("candlesticks") == 2



# ------------------------------------------------------------------ the clock offset
def test_the_offset_is_the_order_answers_from_5_samples_else_the_time_server_else_zero(env):
    """Kalshi's clock comes from its order answers (ClockSync), with a time server's reading as the
    first source (before any order has answered) and the fallback."""
    b = bot.Bot(Spy(), env, True)
    assert b.offset == 0.0
    b.ntp = 0.155
    assert b.offset == 0.155                                                 # the time server first ...
    b.ntp = 0.0
    assert b.offset == 0.0                                                   # ... even a reading of exactly 0
    b.ntp = 0.155
    for i in range(4):
        b.clocks.add(1000.0 + i, 1000.1 + i, (1000.05 + i + 0.2) * 1000)   # Kalshi 0.2 s ahead
    assert len(b.clocks) == 4 and b.offset == 0.155                          # too few answers to trust: still the server
    b.clocks.add(1004.0, 1004.1, 1004.25 * 1000)
    assert b.offset == pytest.approx(0.2)                                    # Kalshi's own clock from 5 answers on
    b.ntp = None
    assert b.offset == pytest.approx(0.2)


# ------------------------------------------------------------------ nap: how long the loop sleeps
@pytest.mark.parametrize("elapsed", [0.0, 0.4, 2.999, 3.0, 7.5])
@pytest.mark.parametrize("at", [100.25, 478.5])        # at 478.5 s FAST's mark is in reach, but with no START it's ignored
def test_with_no_start_nap_is_the_rest_of_the_poll(at, elapsed):
    s = FAST + at
    clock = lambda: s + elapsed   # noqa: E731
    assert bot.nap(s, 0.0, clock) == pytest.approx(max(0.0, bot.POLL - (clock() - s)), abs=1e-6)
    assert bot.nap(s, 0.155, clock) == pytest.approx(max(0.0, bot.POLL - elapsed), abs=1e-6)


def test_with_a_start_nap_wakes_at_a_fast_windows_mark_on_kalshis_clock(on):
    s = FAST + 478.5
    assert bot.nap(s, 0.0, lambda: s + 0.2) == pytest.approx(1.3, abs=1e-6)            # 480.0 - 478.7
    assert bot.nap(s, 0.155, lambda: s + 0.2) == pytest.approx(1.145, abs=1e-6)        # Kalshi's 480.0 is the PC's 479.845
    assert bot.nap(s, 0.0, lambda: s + 4.0) == 0.0                           # never negative
    assert bot.nap(FAST + 448, 0.0, lambda: FAST + 448) == pytest.approx(2.0, abs=1e-6)          # the prep, at 450 s
    assert bot.nap(NORMAL + 478.5, 0.0, lambda: NORMAL + 478.7) == pytest.approx(2.8, abs=1e-6)  # a normal window: the usual 3 s


def test_nap_reads_the_clock_when_it_is_called(monkeypatch):
    """The command-line tests fake the clock by swapping bot.time (test_cli.py), so nap with no clock must read
    bot.time.time when called, not a clock fixed when bot.py was loaded."""
    monkeypatch.setattr(bot, "time", types.SimpleNamespace(time=lambda: W + 101.0, monotonic=lambda: 0.0, sleep=lambda s: None))
    assert bot.nap(W + 100.0) == pytest.approx(2.0)


# ------------------------------------------------------------------ with no START, nothing changes
@pytest.mark.parametrize("at", [450, 455, 479])
def test_with_no_start_nothing_is_prepared(env, at):
    assert fast_entry.START is None
    fake = Spy()
    b = started(fake, env, FAST, at=at)
    assert b.prepared == {}
    assert not {"candlesticks", "orderbook", "balance", "create_order"} & set(fake.names())
    assert not [c for c in fake.calls if c.name == "markets" and "series_ticker" in c.detail]   # no listing either


@pytest.mark.parametrize("case", ["no start", "a normal window", "a fast window whose prep it missed"])
def test_these_windows_enter_the_way_the_bot_always_has(env, monkeypatch, sends, watch, case):
    """One order at a time, each sent by place() itself and followed by its fills, as today's bodies plus the
    exchange_index (Kalshi's section for the market: every live order carries it since Oct 14). A fast window whose
    prep it missed (a start at 485 s, say) goes this way too."""
    if case != "no start":
        monkeypatch.setattr(fast_entry, "START", START)
    w = NORMAL if case == "a normal window" else FAST
    fake = Spy()
    b = started(fake, env, w, at=485)
    assert sends.calls == []
    assert [n for n in fake.names() if n in ("create_order", "fills")] == ["create_order", "fills"] * 2
    assert sorted(fake.orders, key=lambda o: o["ticker"]) == [
        bot.order_body(BTC, "yes", bot.limit_for(0.96), 3, exchange_index=2),
        bot.order_body(GOLD, "no", bot.limit_for(0.98), 3, exchange_index=2)]
    assert sorted((t, s) for t, s, _ in watch.place) == [(BTC, None), (GOLD, None)]
    assert "candlesticks" in fake.names() and "balance" in fake.names()     # read at the mark, as today
    assert b.prepared == {} and set(bets(env)) == {BTC, GOLD}


def test_with_no_start_the_offset_stays_zero_whatever_the_answers_say(env):
    """Six orders whose answers all carry Kalshi's time: with no START none of it moves the bot's clock."""
    names = [f"KXT{i}15M" for i in range(6)]
    fake = Spy(books={s: YES for s in names}, stamp=lambda body: round((FAST + 485.3) * 1000))
    b = started(fake, env, FAST, at=485)
    assert len(fake.orders) == 6
    assert b.offset == 0.0 and b.ntp is None


# ------------------------------------------------------------------ the prep (450 s up to the mark)
def test_the_prep_lists_the_markets_reads_the_prices_and_the_balance_and_reads_no_book(env, on):
    fake = Spy()
    b = started(fake, env, FAST, at=455)
    names = fake.names()
    listed = sorted(c.detail["series_ticker"] for c in fake.calls if c.name == "markets" and "series_ticker" in c.detail)
    assert listed == ["KXBTC15M", "KXETH15M", "KXGOLD15M"]
    [candles] = [c for c in fake.calls if c.name == "candlesticks"]
    assert {BTC, GOLD} <= set(candles.detail["tickers"]) <= {BTC, GOLD, ETH}
    assert (candles.detail["start"], candles.detail["end"]) == (FAST, FAST + bot.MINUTE * 60)
    assert names.count("balance") == 1
    assert "orderbook" not in names and "create_order" not in names and fake.orders == []
    assert list(b.prepared) == [FAST]
    prep = b.prepared[FAST]
    assert sorted(m["ticker"] for m in prep["markets"]) == [BTC, ETH, GOLD]
    raw = Recorded.candlesticks(fake, list(candles.detail["tickers"]), FAST, FAST + bot.MINUTE * 60)   # (not noted)
    assert prep["history"] == bot.minute_quotes(raw, FAST)
    assert prep["cash"] == 100.0
    assert decisions(env) == {} and bets(env) == {} and b.done_window is None


def test_a_dry_runs_prep_reads_no_balance(env, on):
    fake = Spy()
    b = started(fake, env, FAST, live=False, at=455)
    assert b.prepared[FAST]["cash"] is None
    assert "balance" not in fake.names() and fake.names().count("candlesticks") == 1


@pytest.mark.parametrize("at, preps", [(449, False), (450, True), (466, True), (479.9, True), (480, False)])
def test_the_prep_runs_from_450_s_until_the_mark(env, on, at, preps):
    b = started(Spy(), env, FAST, live=False, at=at)
    assert (FAST in b.prepared) is preps


def test_the_prep_runs_once_a_window(env, on):
    fake = Spy()
    b = started(fake, env, FAST, at=455)
    b.step(FAST + 458)
    b.step(FAST + 461)
    assert fake.names().count("candlesticks") == 1 and fake.names().count("balance") == 1
    assert len([c for c in fake.calls if c.name == "markets" and "series_ticker" in c.detail]) == 3


def test_an_empty_listing_keeps_nothing_and_the_next_step_tries_again(env, on):
    fake = Spy()
    fake.window = FAST + 900                       # Kalshi lists nothing for this window yet
    b = bot.Bot(fake, env, True)
    b.step(FAST + 455)
    assert b.prepared == {} and "candlesticks" not in fake.names()
    fake.window = FAST                             # it catches up
    b.step(FAST + 458)
    assert list(b.prepared) == [FAST] and fake.names().count("candlesticks") == 1


def test_the_prep_keeps_only_the_current_window(env, on):
    fake = Spy()
    fake.window = FAST
    b = bot.Bot(fake, env, True)
    b.prepared = {FAST - 900: prep_for(mk(BTC, YES96, FAST - 900))}
    b.step(FAST + 455)
    assert list(b.prepared) == [FAST]


def test_a_normal_window_is_never_prepared(env, on):
    fake = Spy()
    b = started(fake, env, NORMAL, at=455)
    assert b.prepared == {} and "candlesticks" not in fake.names()


# ------------------------------------------------------------------ the mark (480 s, Kalshi's clock)
def test_the_mark_step_skips_the_housekeeping_and_never_lists_again(env, on, sends):
    """Every check is made due and a bet waits to settle, yet the mark step reads no catalog, status, listing,
    settlement, resting orders, order record, prices or balance: they ran at the prep and run again next step."""
    fake = Spy()
    open_bet(env, "KXBTC15M-OLD", FAST - 900, 3, 2.88)      # closed at FAST, no result yet: settle looks it up each step
    b = started(fake, env, FAST, at=455)
    assert [c for c in fake.calls if c.name == "markets" and "tickers" in c.detail]   # it did, at the prep
    b.last_catalog = b.last_status = b.last_sweep = b.last_reconcile = 0.0
    since = fake.mark()
    b.step(FAST + 480)
    assert not HOUSEKEEPING & set(fake.names(since))
    assert len(sends.calls) == 1 and set(bets(env)) == {"KXBTC15M-OLD", BTC, GOLD}
    assert b.done_window == FAST
    assert float(bot.get_meta(env, "heartbeat")) == FAST + 480 and env.in_transaction is False   # saved, as every step


def test_the_mark_step_reads_the_books_before_any_order(env, on, sends):
    fake = Spy()
    b = started(fake, env, FAST, at=455)
    since = fake.mark()
    b.step(FAST + 480)
    calls = fake.calls[since:]
    first_order = next(i for i, c in enumerate(calls) if c.name == "create_order")
    assert {c.detail["ticker"] for c in calls[:first_order] if c.name == "orderbook"} == {BTC, GOLD, ETH}
    assert len(sends.calls) == 1                           # (the fast way, not today's)


def test_every_order_goes_out_through_send_all_in_a_burst_then_spaced(env, on, sends):
    fake = Spy()
    b = started(fake, env, FAST, at=455)
    b.step(FAST + 480)
    [call] = sends.calls
    assert call["k"] is fake
    assert (call["workers"], call["spacing"], call["burst"]) == (bot.FAST_BURST, bot.FAST_SPACING, bot.FAST_BURST)
    assert sorted(x["ticker"] for x in call["bodies"]) == [BTC, GOLD]
    by_ticker = lambda o: o["ticker"]   # noqa: E731
    assert sorted(fake.orders, key=by_ticker) == sorted(call["bodies"], key=by_ticker)   # nothing sent outside it


@pytest.mark.parametrize("limit", ["1c over the ask", "at the ask"])
def test_a_fast_windows_yes_and_no_orders_go_out_at_the_limit_with_the_exchange_index(env, on, sends, monkeypatch, limit):
    """The bodies are order_body(ticker, side, limit_for(top), contracts, exchange_index=bot.section), with the section
    Kalshi's exchange status gave (5 here, to tell it from a hard-coded 2). Run again with limit_for returning the ask
    itself, as a switch inside it may: the bodies follow it and place() accepts them."""
    if limit == "at the ask":
        monkeypatch.setattr(bot, "limit_for", lambda top: top)
    fake = Spy(section=5)
    b = started(fake, env, FAST, at=455)
    b.step(FAST + 480)
    assert b.section == 5
    want = {BTC: bot.order_body(BTC, "yes", bot.limit_for(0.96), 3, exchange_index=5),
            GOLD: bot.order_body(GOLD, "no", bot.limit_for(0.98), 3, exchange_index=5)}
    got = {x["ticker"]: x for x in sends.calls[0]["bodies"]}
    assert got == want and all(type(x["exchange_index"]) is int for x in got.values())
    assert {r["ticker"]: json.loads(r["request"]) for r in orders_rows(env)} == want   # the ledger keeps what was sent
    assert bot.halt_info() is None and set(bets(env)) == {BTC, GOLD}
    assert bets(env)[BTC]["price"] == pytest.approx(bot.limit_for(0.96))              # the fake fills at the limit
    assert bets(env)[GOLD]["price"] == pytest.approx(bot.limit_for(0.98))


def test_the_mark_step_still_checks_the_halts_first(env, on, sends):
    fake = Spy()
    b = started(fake, env, FAST, at=455)
    for i in range(8):                                     # 8 bets lost in one window, settled since the prep
        fake_bet(env, i, FAST - 900, False, -0.01, settled=FAST + 470)
    since = fake.mark()
    b.step(FAST + 480)
    assert "8 bets lost in one window" in bot.halt_info()["reason"]
    assert not HOUSEKEEPING & set(fake.names(since))       # (the fast way: today's would read the prices again)
    assert fake.orders == [] and decisions(env)[BTC][0] == decisions(env)[GOLD][0] == "halted"


@pytest.mark.parametrize("env_name, stops", [("prod", True), ("demo", False)])
def test_the_mark_step_checks_the_700_dollar_stop_on_prod_only(env, on, sends, env_name, stops):
    """A loss settled since the prep takes a $1,000 account to $700: live on prod (the $700 stop, test_halt_floor.py)
    the mark halts before any order; on demo it trades."""
    bot.set_start(env, 1000.0)
    env.commit()
    fake = Spy()
    fake.env = env_name
    b = started(fake, env, FAST, at=455)
    fake_bet(env, 0, FAST - 900, False, -300.0, settled=FAST + 470)   # 30% in a day, over half the start: only the stop
    b.step(FAST + 480)
    if stops:
        assert bot.halt_info()["reason"] == "the account is down to $700.00, at or under the $700 stop"
        assert fake.orders == [] and sends.calls == [] and decisions(env)[BTC][0] == decisions(env)[GOLD][0] == "halted"
    else:
        assert bot.halt_info() is None and len(fake.orders) == 2 and len(sends.calls) == 1


def test_the_step_after_the_mark_does_the_housekeeping_and_orders_nothing_more(env, on, sends):
    fake = Spy()
    b = started(fake, env, FAST, at=455)
    b.step(FAST + 480)
    b.last_sweep = 0.0
    since = fake.mark()
    b.step(FAST + 483)
    assert "list_orders" in fake.names(since) and "create_order" not in fake.names(since)
    assert len(fake.orders) == 2 and len(sends.calls) == 1


def test_a_dry_run_fast_window_places_one_at_a_time_and_never_sends(env, on, sends, watch):
    fake = Spy()
    b = started(fake, env, FAST, live=False, at=455)
    since = fake.mark()
    b.step(FAST + 480)
    assert sends.calls == [] and fake.orders == []
    assert sorted((t, s) for t, s, _ in watch.place) == [(BTC, None), (GOLD, None)]
    assert "candlesticks" not in fake.names(since) and "balance" not in fake.names()    # the prep's prices; no balance
    assert decisions(env)[BTC][1].startswith("would buy YES 3") and set(bets(env)) == {BTC, GOLD}


# ------------------------------------------------------------------ when the prep came up short
def test_with_prices_and_cash_from_the_prep_the_mark_reads_neither(env, on, sends):
    fake = Spy()
    b = bot_for(fake, env, True)
    ms = [mk(BTC, YES96, FAST), mk(GOLD, NO98, FAST)]
    since = fake.mark()
    b.decide_window(FAST + 480, FAST, ms, prep=prep_for(*ms))
    assert not {"candlesticks", "balance"} & set(fake.names(since))
    assert len(sends.calls) == 1 and set(bets(env)) == {BTC, GOLD}


def test_no_prices_from_the_prep_means_it_reads_them_at_the_mark(env, on, sends):
    fake = Spy()
    b = bot_for(fake, env, True)
    ms = [mk(BTC, YES96, FAST), mk(GOLD, NO98, FAST)]
    since = fake.mark()
    b.decide_window(FAST + 480, FAST, ms, prep=dict(prep_for(*ms), history=None))
    [candles] = [c for c in fake.calls[since:] if c.name == "candlesticks"]
    assert sorted(candles.detail["tickers"]) == [BTC, GOLD]
    assert "balance" not in fake.names(since)
    assert len(sends.calls) == 1 and set(bets(env)) == {BTC, GOLD}


def test_no_cash_from_the_prep_means_it_reads_the_balance_at_the_mark(env, on, sends):
    fake = Spy()
    b = bot_for(fake, env, True)
    ms = [mk(BTC, YES96, FAST), mk(GOLD, NO98, FAST)]
    since = fake.mark()
    b.decide_window(FAST + 480, FAST, ms, prep=prep_for(*ms, cash=None))
    assert fake.names(since).count("balance") == 1 and "candlesticks" not in fake.names(since)
    assert len(sends.calls) == 1 and set(bets(env)) == {BTC, GOLD}


def test_a_prep_that_couldnt_read_the_prices_or_the_balance_still_enters_fast(env, on, sends):
    fake = Spy()
    fake.candles, fake.balances = [None], [None]           # both unreadable at the prep, fine again at the mark
    b = started(fake, env, FAST, at=455)
    assert b.prepared[FAST]["history"] is None and b.prepared[FAST]["cash"] is None
    since = fake.mark()
    b.step(FAST + 480)
    assert fake.names(since).count("candlesticks") == 1 and fake.names(since).count("balance") == 1
    assert len(sends.calls) == 1 and set(bets(env)) == {BTC, GOLD}


# ------------------------------------------------------------------ reserving as it builds
def test_live_cash_is_reserved_as_each_order_is_built(env, on, sends):
    """Cash in Kalshi's Crypto & Commodities section for two orders of three: the third is skipped with today's words,
    and only two go out."""
    need = 3 * bot.limit_for(0.96) + bot.taker_fee(3, 0.96)    # every contract at the limit, the fee at the ask it saw
    fake = Spy()
    b = bot_for(fake, env, True)
    ms = [mk(t, YES96, FAST) for t in (BTC, ETH, SOL)]
    b.decide_window(FAST + 480, FAST, ms, prep=prep_for(*ms, cash=round(2 * need + 1.0, 2)))
    [call] = sends.calls
    assert sorted(x["ticker"] for x in call["bodies"]) == [BTC, ETH] and len(fake.orders) == 2
    action, why = decisions(env)[SOL]
    assert action == "skip" and why.startswith("only $1.00 in Kalshi's Crypto & Commodities section")


def test_the_day_cap_counts_orders_as_they_are_built(env, on, sends):
    for i in range(bot.MAX_ORDERS_PER_DAY - 1):             # room for exactly one more today
        fake_bet(env, 100 + i, FAST - 900, True, 0.0, settled=FAST - 5)
    fake = Spy()
    b = bot_for(fake, env, True)
    ms = [mk(BTC, YES96, FAST), mk(GOLD, NO98, FAST)]
    b.decide_window(FAST + 480, FAST, ms, prep=prep_for(*ms))
    assert [x["ticker"] for x in sends.calls[0]["bodies"]] == [BTC] and len(fake.orders) == 1
    assert decisions(env)[GOLD] == ("skip", "order limit reached")


def test_the_window_cap_counts_orders_as_they_are_built(env, on, sends, monkeypatch):
    monkeypatch.setattr(bot, "MAX_ORDERS_PER_WINDOW", 2)
    fake = Spy()
    b = bot_for(fake, env, True)
    ms = [mk(t, YES96, FAST) for t in (BTC, ETH, SOL)]
    b.decide_window(FAST + 480, FAST, ms, prep=prep_for(*ms))
    assert sorted(x["ticker"] for x in sends.calls[0]["bodies"]) == [BTC, ETH] and len(fake.orders) == 2
    assert decisions(env)[SOL] == ("skip", "order limit reached")


# ------------------------------------------------------------------ place(..., sent=): recording an order already sent
def test_place_with_an_answer_records_it_and_sends_nothing(env):
    within = min(round(0.96 + 0.005, 4), bot.limit_for(0.96))
    fake = Spy(order=no_order, fills=lambda p: {"fills": [fill(3, within)]})
    b = bot_for(fake, env, True)
    body = bot.order_body(BTC, "yes", bot.limit_for(0.96), 3, exchange_index=2)
    sent = answer(body, ts_ms=round((FAST + 480.05) * 1000))
    assert place_with(b, sent) is True
    assert fake.orders == [] and "create_order" not in fake.names()
    [row] = orders_rows(env)
    assert (row["ticker"], row["http_status"], row["client_order_id"]) == (BTC, 201, bot.client_order_id(BTC))
    assert json.loads(row["request"]) == body and json.loads(row["response"]) == sent["data"]
    r = bets(env)[BTC]
    assert (r["contracts"], r["order_id"], r["side"]) == (3, "o1", "yes") and r["cost"] == pytest.approx(3 * within)
    assert [c.detail for c in fake.calls if c.name == "fills"] == [{"order_id": "o1", "ticker": None}]
    assert decisions(env)[BTC] == ("bet", f"bought YES 3 at {within * 100:.1f}c ($3.00 a bet)")
    assert bot.halt_info() is None and b.errors == 0


@pytest.mark.parametrize("found, bet", [([fill(3)], True), ([], False)])
def test_place_with_a_network_error_takes_the_existing_path(env, found, bet):
    """No answer from Kalshi: the order may have arrived, so it looks up the market's fills and records what bought;
    either way it counts toward the three-failures-in-a-row halt."""
    fake = Spy(order=no_order, fills=lambda p: {"fills": found})
    b = bot_for(fake, env, True)
    body = bot.order_body(BTC, "yes", bot.limit_for(0.96), 3, exchange_index=2)
    sent = {"body": body, "status": None, "data": "network error: connection reset", "sent": FAST + 480.0,
            "answered": FAST + 485.0}
    assert place_with(b, sent) is bet
    assert b.errors == 1 and fake.orders == []
    assert [c.detail for c in fake.calls if c.name == "fills"] == [{"order_id": None, "ticker": BTC}]
    [row] = orders_rows(env)
    assert row["http_status"] is None and json.loads(row["response"]) == "network error: connection reset"
    assert (BTC in bets(env)) is bet and decisions(env)[BTC][0] == "error"


def test_place_with_a_refusal_is_an_error(env):
    fake = Spy(order=no_order)
    b = bot_for(fake, env, True)
    body = bot.order_body(BTC, "yes", bot.limit_for(0.96), 3, exchange_index=2)
    sent = dict(answer(body), status=400, data={"error": {"code": "insufficient_balance"}})
    assert place_with(b, sent) is False
    action, why = decisions(env)[BTC]
    assert action == "error" and "order failed (400)" in why and b.errors == 1 and bets(env) == {}


@pytest.mark.parametrize("over", [False, True], ids=["within the limit", "over the limit"])
@pytest.mark.parametrize("ticker, side, top, book", [(BTC, "yes", 0.96, YES96), (GOLD, "no", 0.98, NO98)], ids=["yes", "no"])
def test_a_fill_over_the_ask_but_within_the_limit_doesnt_halt_and_one_over_the_limit_does(env, ticker, side, top, book, over):
    """Half a cent over the ask it saw is within the 1c limit; a hundredth of a cent over the limit isn't. (Should
    limit_for return the ask itself, "within" becomes the ask.)"""
    limit = bot.limit_for(top)
    paid = round(limit + 0.0001, 4) if over else min(round(top + 0.005, 4), limit)
    yes = paid if side == "yes" else round(1 - paid, 4)
    fake = Spy(order=no_order, fills=lambda p: {"fills": [fill(3, yes, side=side)]})
    b = bot_for(fake, env, True)
    assert place_with(b, answer(bot.order_body(ticker, side, limit, 3, exchange_index=2)), ticker, side, top, book) is True
    h = bot.halt_info()
    if over:
        assert h["reason"].startswith(f"unexpected fill on {ticker}: 3.0 at {paid:.4f}, asked 3 at {limit:.4f}")
    else:
        assert h is None
    r = bets(env)[ticker]
    assert r["contracts"] == 3 and r["price"] == pytest.approx(paid)    # the position is real either way


MISMATCHES = {
    "another market": (BTC, "yes", 0.96, YES96, lambda good: dict(good, ticker="KXBTC15M-B")),
    "the other side": (BTC, "yes", 0.96, YES96, lambda good: dict(good, side="ask")),
    "more contracts": (BTC, "yes", 0.96, YES96, lambda good: dict(good, count="4")),
    "fewer contracts": (BTC, "yes", 0.96, YES96, lambda good: dict(good, count="2")),
    "another price": (BTC, "yes", 0.96, YES96, lambda good: dict(good, price=f"{bot.limit_for(0.96) + 0.01:.4f}")),
    "another NO price": (GOLD, "no", 0.98, NO98, lambda good: dict(good, price="0.0050")),   # NO at 99.5c
}


@pytest.mark.parametrize("case", MISMATCHES)
def test_a_sent_order_that_isnt_what_place_would_build_halts_and_records_no_bet(env, case):
    """The condition: the sent body must be the ticker, side, count and price (limit_for(top) on its side)
    place() would have sent. If not, the orders row is still written, the decision is an error, the halt names the
    market, and no bet goes in: reconcile adds any fill from Kalshi's own record on its next pass."""
    ticker, side, top, book, change = MISMATCHES[case]
    good = bot.order_body(ticker, side, bot.limit_for(top), 3, exchange_index=2)
    bad = change(good)
    fake = Spy(order=no_order, fills=lambda p: {"fills": []})
    b = bot_for(fake, env, True)
    assert place_with(b, answer(bad), ticker, side, top, book) is False
    [row] = orders_rows(env)
    assert json.loads(row["request"]) == bad and row["http_status"] == 201
    assert decisions(env)[ticker][0] == "error"
    assert ticker in bot.halt_info()["reason"]
    assert bets(env) == {} and fake.orders == []


@pytest.mark.parametrize("index", [None, 2, 9])
def test_the_exchange_index_is_left_out_of_that_comparison(env, index):
    fake = Spy(order=no_order, fills=lambda p: {"fills": [fill(3, bot.limit_for(0.96))]})
    b = bot_for(fake, env, True)
    assert place_with(b, answer(bot.order_body(BTC, "yes", bot.limit_for(0.96), 3, exchange_index=index))) is True
    assert bot.halt_info() is None and bets(env)[BTC]["contracts"] == 3


def test_after_a_mismatch_reconcile_adds_the_bet_from_kalshis_record(env):
    fake = Spy(order=no_order, fills=lambda p: {"fills": [fill(4, 0.97)]})
    b = bot_for(fake, env, True)
    bad = dict(bot.order_body(BTC, "yes", bot.limit_for(0.96), 3, exchange_index=2), count="4")
    assert place_with(b, answer(bad, fill_count="4.00")) is False and bets(env) == {}
    fake.order_record = [record(BTC, count=4, price=0.97, created=FAST + 480)]
    b.reconcile(FAST + 540)
    r = bets(env)[BTC]
    assert (r["contracts"], r["side"], r["order_id"]) == (4.0, "yes", f"k-{BTC}") and r["cost"] == pytest.approx(3.88)
    action, why = decisions(env)[BTC]
    assert action == "bet" and "found in Kalshi's record of its orders" in why


def test_every_order_sent_is_recorded_even_after_an_earlier_one_halts(env, on, sends):
    """Once the burst is out, every answer is a real position: a halt from the first doesn't stop the second being
    recorded."""
    over = round(bot.limit_for(0.96) + 0.01, 4)
    looks = {f"o-{BTC}": [fill(3, over)], f"o-{GOLD}": [fill(3, round(1 - bot.limit_for(0.98), 4), side="no")]}
    fake = Spy(fills=lambda p: {"fills": looks[p["order_id"]]})
    b = bot_for(fake, env, True)
    ms = [mk(BTC, YES96, FAST), mk(GOLD, NO98, FAST)]
    b.decide_window(FAST + 480, FAST, ms, prep=prep_for(*ms))
    assert bot.halt_info()["reason"].startswith(f"unexpected fill on {BTC}")
    assert set(bets(env)) == {BTC, GOLD}


# ------------------------------------------------------------------ threads
def test_place_and_fills_for_run_only_on_the_bots_thread(env, on, sends, watch):
    """Only the HTTP calls run on other threads (send_all's and books()'): place(), fills_for() and every save stay on
    the bot's own thread. (SQLite would also refuse a save from another thread.)"""
    me = threading.current_thread()
    fake = Spy()
    b = started(fake, env, FAST, at=455)
    b.step(FAST + 480)
    assert len(watch.place) == 2 and all(s is not None and t is me for _, s, t in watch.place)
    assert watch.fills_for and all(t is me for t in watch.fills_for)
    looks = [c for c in fake.calls if c.name == "fills"]
    assert looks and all(c.thread is me for c in looks)
    assert any(c.thread is not me for c in fake.calls if c.name == "create_order")   # the orders went out on send_all's


# ------------------------------------------------------------------ Kalshi's clock from the answers
def test_each_answer_with_kalshis_time_adds_a_clock_sample(env, on, sends):
    """Two answers carry ts_ms, 155 ms past the middle of their round trips; the third order got no answer at all."""
    def order(body, n):
        if body["ticker"] == SOL:
            raise requests.ConnectionError("connection reset")
        return 201, {"order_id": f"o-{body['ticker']}", "fill_count": body["count"] + ".00", "remaining_count": "0.00"}

    def times(results):
        for i, r in enumerate(results):
            r["sent"], r["answered"] = 1000.0 + i, 1000.1 + i
            if isinstance(r["data"], dict):
                r["data"]["ts_ms"] = round((1000.05 + i + 0.155) * 1000)
    sends.after = times
    fake = Spy(order=order)
    b = bot_for(fake, env, True)
    ms = [mk(t, YES96, FAST) for t in (BTC, ETH, SOL)]
    b.decide_window(FAST + 480, FAST, ms, prep=prep_for(*ms))
    assert len(fake.orders) == 3 and set(bets(env)) == {BTC, ETH}
    assert len(b.clocks) == 2 and b.clocks.offset() == pytest.approx(0.155, abs=1e-6)
    assert b.offset == 0.0                                  # under 5 samples: not trusted yet
    assert decisions(env)[SOL][0] == "error"


# ------------------------------------------------------------------ the time server, from step()
def test_the_time_server_is_never_asked_with_no_start(env, ntp):
    fake = Spy()
    b = started(fake, env, NORMAL, live=False, at=100)
    b.step(NORMAL + 100 + bot.NTP_EVERY + 1)
    assert ntp.calls == [] and b.ntp is None


@pytest.mark.parametrize("at, asks", [(100, True), (439, True), (440, False), (455, False), (480, False), (525, False),
                                      (526, True), (899, True)])
@pytest.mark.parametrize("kind", ["fast", "normal"])
def test_the_time_server_is_asked_only_outside_the_prep_to_the_end_of_entry(env, on, ntp, at, asks, kind):
    """PREP - 10 to MINUTE x 60 + GRACE (440-525 s) is when the bot preps and enters: no half-second wait on a time
    server then, in any window."""
    ntp.answers = [0.155]
    b = started(Spy(), env, FAST if kind == "fast" else NORMAL, live=False, at=at)
    assert len(ntp.calls) == (1 if asks else 0)
    assert b.ntp == (0.155 if asks else None)
    if asks:
        assert b.offset == 0.155


def test_the_time_server_is_asked_every_ntp_every_seconds(env, on, ntp):
    ntp.answers = [0.15, 0.16]
    b = started(Spy(), env, NORMAL, live=False, at=100)
    assert len(ntp.calls) == 1 and b.ntp == 0.15
    b.step(NORMAL + 103)
    b.step(NORMAL + 100 + bot.NTP_EVERY - 1)
    assert len(ntp.calls) == 1
    b.step(NORMAL + 100 + bot.NTP_EVERY + 1)
    assert len(ntp.calls) == 2 and b.ntp == 0.16


def test_a_reading_that_fails_keeps_the_last_one(env, on, ntp):
    ntp.answers = [0.15, None]
    b = started(Spy(), env, NORMAL, live=False, at=100)
    b.step(NORMAL + 100 + bot.NTP_EVERY + 1)
    assert len(ntp.calls) == 2 and b.ntp == 0.15 and b.offset == 0.15


# ------------------------------------------------------------------ the main loop
def test_each_step_runs_on_kalshis_clock(cli, monkeypatch):
    monkeypatch.setattr(bot.Bot, "offset", property(lambda self: 0.155))
    steps = []
    monkeypatch.setattr(bot.Bot, "run_step", lambda self, now, carry_on=False: steps.append(now))
    bot.main(["--once"])
    assert steps == [pytest.approx(NOW + 0.155)]


def test_the_loop_sleeps_as_long_as_nap_says(cli, monkeypatch):
    monkeypatch.setattr(bot.Bot, "offset", property(lambda self: 0.155))
    monkeypatch.setattr(bot.Bot, "run_step", lambda self, now, carry_on=False: None)
    naps, slept = [], []

    def nap(started, offset=0.0, clock=None):
        naps.append((started, offset))
        return 1.25

    def sleep(s):
        slept.append(s)
        raise KeyboardInterrupt
    monkeypatch.setattr(bot, "nap", nap)
    monkeypatch.setattr(bot, "time", types.SimpleNamespace(monotonic=lambda: 0.0, time=lambda: NOW, sleep=sleep))
    with pytest.raises(KeyboardInterrupt):
        bot.main([])
    assert naps == [(NOW, pytest.approx(0.155))] and slept == [1.25]


def test_the_loop_wakes_at_a_fast_windows_mark(cli, on, monkeypatch):
    """1.5 s before FAST's mark the loop sleeps 1.5 s, not the usual 3."""
    slept = []

    def sleep(s):
        slept.append(s)
        raise KeyboardInterrupt
    monkeypatch.setattr(bot, "time", types.SimpleNamespace(monotonic=lambda: 0.0, time=lambda: FAST + 478.5, sleep=sleep))
    with pytest.raises(KeyboardInterrupt):
        bot.main([])
    assert slept == [pytest.approx(1.5)]
