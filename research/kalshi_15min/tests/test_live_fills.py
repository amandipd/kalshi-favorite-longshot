"""live_fills.py: the live bot's real orders, read from its ledger, set against the research data and its backtests.

Every ledger here is a temp one with bot.py's own tables (bot.connect), written the way the live bot writes it: an
order row holding Kalshi's request and answer, a bet when anything filled, one decision per market. No test opens the
real ledger: the module's default is pointed at a file that doesn't exist, and its sqlite3 refuses any database outside
pytest's temp folders.

read_ledger is checked on every kind of row the bot writes and for leaving the file exactly as it was; the fill table
(Kaplan-Meier over whole contracts) on the spec's worked examples; compare, replay and candidates on orders placed on
the synthetic history's own markets, with the backtest's picks rebuilt here from strategies_backtest's helpers, so
nothing hangs on a synthetic price; then main end to end.

    python -m pytest research/kalshi_15min/tests/test_live_fills.py -q
"""

from __future__ import annotations

import importlib
import json
import math
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import unquote

import pytest

from conftest import RESEARCH, ticker_for

UTC = timezone.utc
BANDS = [(0.90, 0.92, "90–91"), (0.92, 0.95, "92–94"), (0.95, 1.0, "95+")]
SIZES = [(1, 5, "1–5"), (6, 15, "6–15"), (16, 30, "16–30"), (31, None, "31+")]


def at(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def band_of(limit):
    return next(name for lo, hi, name in BANDS if lo <= limit < hi)


def size_of(want):
    return next(name for lo, hi, name in SIZES if lo <= want and (hi is None or want <= hi))


def roundtrip(x):
    return json.loads(json.dumps(x))


class TempOnly:
    """sqlite3 as live_fills sees it, refusing to open any database outside pytest's temp folders: a guard, so a wrong
    default can never reach a real ledger."""

    def __init__(self, real, base):
        self.real, self.base = real, str(Path(base).resolve()).replace("\\", "/").lower()

    def __getattr__(self, name):
        return getattr(self.real, name)

    def connect(self, database, *args, **kwargs):
        name = os.fspath(database)
        if name not in ("", ":memory:") and not name.startswith("file::memory:"):
            plain = unquote(name.split("?", 1)[0])
            if not plain.startswith("file:"):
                plain = os.path.abspath(plain)
            if self.base not in plain.replace("\\", "/").lower():
                raise AssertionError(f"live_fills opened a database outside the tests' temp folders: {name}")
        return self.real.connect(database, *args, **kwargs)


@pytest.fixture
def lf(study, monkeypatch, tmp_path, tmp_path_factory):
    """The module, imported once the synthetic history is the working directory (it imports strategies_backtest),
    with its default ledger moved to a file that doesn't exist and its sqlite3 kept to the temp folders."""
    mod = importlib.import_module("live_fills")
    assert Path(getattr(mod, "__file__", None) or "nowhere").resolve() == RESEARCH / "live_fills.py", \
        "the research script itself, not the lab's live_fills folder"
    monkeypatch.setattr(mod, "LEDGER", str(tmp_path / "absent" / "live-prod.db"))
    monkeypatch.setattr(mod, "sqlite3", TempOnly(sqlite3, tmp_path_factory.getbasetemp()), raising=False)
    return mod


@pytest.fixture(scope="module")
def windows(study):
    return study.strategies_backtest.load()[0]


@pytest.fixture
def written(study):
    """Where main writes live_fills.json (the synthetic history's folder). Removed afterwards: strategies_backtest
    reads that file at import, so it mustn't outlive the test."""
    out = study.dir / "live_fills.json"
    assert not out.exists()
    yield out
    out.unlink(missing_ok=True)


# ------------------------------------------------------------------ a ledger written the way the bot writes it


class Ledger:
    """A temp ledger with bot.py's own tables (bot.connect), written the way the live bot writes it."""

    def __init__(self, path):
        from kalshi_bot import bot
        self.bot, self.path = bot, Path(path)
        self.db = bot.connect(str(path))
        self.db.execute("INSERT OR REPLACE INTO meta VALUES ('start', '225.0')")

    def raw(self, ts, ticker, request, status, response, oid=None):
        """One orders row as given: a dict is written as JSON, a string as it is (to write JSON that doesn't parse)."""
        enc = lambda x: x if x is None or isinstance(x, str) else json.dumps(x)  # noqa: E731
        self.db.execute("INSERT INTO orders (id, ts, ticker, client_order_id, request, http_status, response)"
                        " VALUES (?,?,?,?,?,?,?)",
                        (oid, ts, ticker, self.bot.client_order_id(ticker), enc(request), status, enc(response)))

    def decide(self, ticker, ts, action, reason, yes_bid=None, yes_ask=None, side=None, price=None):
        self.db.execute("INSERT OR IGNORE INTO decisions (ts, ticker, series, yes_bid, yes_ask, fav_side, fav_price,"
                        " action, reason) VALUES (?,?,?,?,?,?,?,?,?)",
                        (ts, ticker, ticker.split("-")[0], yes_bid, yes_ask, side, price, action, reason))

    def order(self, ticker, side, limit, want, got, *, ts, price=None, won=None, fee=None, book="seen", status=201):
        """One immediate-or-cancel order (bot.order_body) and Kalshi's answer: `got` of `want` contracts at `price`
        on its own side (the limit unless given). When anything filled, its bet: open if `won` is None, else
        settled, with the fee Kalshi charged (`fee`, else the exact fee cut to 4 places). Its decision row carries
        the book the bot saw: by default its limit as the ask on its own side and 1c under it as the bid; a
        (yes_bid, yes_ask) pair as given (None, None for one with no prices, as the bot's reconcile writes);
        book=None writes no decision."""
        price = limit if price is None else price
        body = self.bot.order_body(ticker, side, limit, want)
        fee = math.floor(0.07 * got * price * (1 - price) * 10000) / 10000 if fee is None else fee
        answer = {"average_fee_paid": f"{fee / got if got else 0:.4f}", "client_order_id": body["client_order_id"],
                  "fill_count": f"{got:.2f}", "order_id": f"order-{ticker}", "remaining_count": "0.00",
                  "ts_ms": int(ts * 1000)}
        if got:   # Kalshi gives the average in YES terms, also for a NO buy
            answer["average_fill_price"] = f"{price if side == 'yes' else 1 - price:.4f}"
        self.raw(ts, ticker, body, status, answer)
        window = int(ts // 900 * 900)
        rec = SimpleNamespace(ticker=ticker, series=ticker.split("-")[0], side=side, limit=limit, want=float(want),
                              got=float(got), price=price if got else None, ts=ts, window=window,
                              fee=fee if got else None, won=won if got else None, pnl=None)
        if got:
            cost = got * price
            rec.pnl = None if won is None else (got if won else 0) - cost - fee
            other = "no" if side == "yes" else "yes"
            self.db.execute(
                "INSERT INTO bets (ticker, series, window_open, close_ts, side, price, contracts, cost, fee, placed_ts,"
                " order_id, client_order_id, status, result, payout, pnl, settled_ts) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (ticker, rec.series, window, window + 900, side, price, float(got), cost, fee, ts, f"order-{ticker}",
                 body["client_order_id"], "open" if won is None else "won" if won else "lost",
                 None if won is None else side if won else other, None if won is None else float(got) if won else 0.0,
                 rec.pnl, None if won is None else window + 905))
        if book is not None:
            if book == "seen":
                book = (round(limit - 0.01, 4), limit) if side == "yes" else (round(1 - limit, 4), round(1.01 - limit, 4))
            action, reason = (("bet", f"bought {side.upper()} {got:g} at {price * 100:.1f}c") if got
                              else ("skip", "not filled: nobody selling at that price"))
            self.decide(ticker, ts, action, reason, *book, side, limit)
        return rec

    def close(self):
        self.db.commit()
        self.db.close()
        return self.path


def parse_ledger(tmp_path):
    """One of each kind of orders row the bot writes, ids out of time order, plus a bet and a decision."""
    led = Ledger(tmp_path / "ledger" / "live-test.db")
    t = at("2026-10-11T23:30:00Z")
    wti, eth, btc = "KXWTI15M-26OCT112345-45", "KXETH15M-26OCT112345-00", "KXBTC15M-26OCT112345-00"
    body = led.bot.order_body

    def answer(ticker, fill, avg=None, **extra):
        a = {"average_fee_paid": "0.0027", "client_order_id": led.bot.client_order_id(ticker), "fill_count": fill,
             "order_id": f"order-{ticker}", "remaining_count": "0.00", "ts_ms": 1791776283441}
        return {**a, **({"average_fill_price": avg} if avg is not None else {}), **extra}
    # a YES buy: a bid at the YES price; 8 of 31 filled
    led.raw(t + 482, wti, body(wti, "yes", 0.959, 31), 201, answer(wti, "8.00", "0.9590"), oid=3)
    # a NO buy: a sell of YES ("ask") at 10c, so 90c on NO; all 12 filled at 10.3c YES, 89.7c on NO. Sent later
    # than the YES one, but its row has the lower id: rows come back by id
    led.raw(t + 900 + 482, eth, body(eth, "no", 0.90, 12), 201, answer(eth, "12.00", "0.1030"), oid=1)
    led.raw(t + 482, btc, body(btc, "yes", 0.97, 5), 201, answer(btc, "0.00"), oid=2)                # nothing filled
    led.raw(t + 483, "KXGOLD15M-X", body("KXGOLD15M-X", "yes", 0.95, 4), 400,
            {"error": {"code": "invalid_order", "message": "bad"}}, oid=4)                          # refused
    led.raw(t + 484, "KXGOLD15M-Y", body("KXGOLD15M-Y", "yes", 0.95, 4), 201, "{not json", oid=5)   # answer garbled
    led.raw(t + 485, "KXGOLD15M-Z", "{not json", 201, answer("KXGOLD15M-Z", "1.00", "0.9500"), oid=6)  # request too
    led.raw(t + 486, "KXGOLD15M-W", body("KXGOLD15M-W", "yes", 0.95, 4), None,
            json.dumps("network error: timed out"), oid=7)                                         # no answer
    # A cancel the bot logged in the orders table (bot.cancel). Not an order: the spec doesn't say, but it has no side
    # or count to read, so the natural reading is to leave it out with the other rows that aren't orders.
    led.raw(t + 487, wti, {"cancel": f"order-{wti}"}, 200, {"order": {"order_id": f"order-{wti}"}}, oid=8)
    led.raw(t + 488, "KXBTC15M-A", body("KXBTC15M-A", "yes", 0.93, 3), 200, answer("KXBTC15M-A", "3.00"),
            oid=9)                                                                                  # 200: filled, no price
    led.raw(t + 489, "KXBTC15M-B", body("KXBTC15M-B", "yes", 0.94, 6), 201,
            answer("KXBTC15M-B", None, "0.9400"), oid=10)                                          # no fill count: 0
    led.raw(t + 490, "KXBTC15M-C", body("KXBTC15M-C", "yes", 0.94, 6), 429, {"error": "too many"}, oid=11)
    led.db.execute("INSERT INTO bets (ticker, series, window_open, close_ts, side, price, contracts, cost, fee, placed_ts,"
                   " status, result, payout, pnl) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (wti, "KXWTI15M", t, t + 900, "yes", 0.959, 8.0, 7.672, 0.0216, t + 482, "won", "yes", 8.0, 0.3064))
    led.decide(wti, t + 482, "bet", "bought YES 8 at 95.9c ($29.76 a bet)", 0.95, 0.959, "yes", 0.959)
    return led.close()


PARSED = [  # what read_ledger makes of parse_ledger's rows, oldest id first
    {"id": 1, "ticker": "KXETH15M-26OCT112345-00", "series": "KXETH15M", "side": "no", "limit": 0.9, "want": 12.0,
     "got": 12.0, "price": 0.897},
    {"id": 2, "ticker": "KXBTC15M-26OCT112345-00", "series": "KXBTC15M", "side": "yes", "limit": 0.97, "want": 5.0,
     "got": 0.0, "price": None},
    {"id": 3, "ticker": "KXWTI15M-26OCT112345-45", "series": "KXWTI15M", "side": "yes", "limit": 0.959, "want": 31.0,
     "got": 8.0, "price": 0.959},
    {"id": 9, "ticker": "KXBTC15M-A", "series": "KXBTC15M", "side": "yes", "limit": 0.93, "want": 3.0, "got": 3.0,
     "price": None},
    {"id": 10, "ticker": "KXBTC15M-B", "series": "KXBTC15M", "side": "yes", "limit": 0.94, "want": 6.0, "got": 0.0,
     "price": None},
]


def test_the_test_ledger_has_the_bots_tables_and_rows(tmp_path):
    """The fixture on its own, read with plain sqlite3: bot.py's four tables and every row written."""
    path = parse_ledger(tmp_path)
    con = sqlite3.connect(path)
    try:
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"bets", "decisions", "orders", "meta"} <= tables
        assert [r[0] for r in con.execute("SELECT id FROM orders ORDER BY id")] == list(range(1, 12))
        req = json.loads(con.execute("SELECT request FROM orders WHERE id=3").fetchone()[0])
        assert (req["side"], req["count"], req["price"], req["time_in_force"]) == ("bid", "31", "0.9590", "immediate_or_cancel")
        assert json.loads(con.execute("SELECT request FROM orders WHERE id=1").fetchone()[0])["price"] == "0.1000"
        assert con.execute("SELECT COUNT(*) FROM bets").fetchone()[0] == 1
        assert con.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 1
    finally:
        con.close()


# ------------------------------------------------------------------ read_ledger


def test_constants(lf):
    assert lf.MIN_ORDERS == 15
    assert [tuple(b) for b in lf.BANDS] == BANDS
    assert [tuple(s) for s in lf.SIZES] == SIZES


def test_read_ledger_parses_each_order_on_its_own_side(lf, tmp_path):
    path = parse_ledger(tmp_path)
    orders, bets, decisions = lf.read_ledger(str(path))
    assert [o["ticker"] for o in orders] == [p["ticker"] for p in PARSED], \
        "accepted orders only (200 or 201 with a JSON answer), by id: not the refused, garbled, unanswered or cancel rows"
    for o, want in zip(orders, PARSED):
        for key in ("ticker", "series", "side", "want", "got"):
            assert o[key] == want[key], (want["id"], key)
        for key in ("limit", "price"):   # on the order's own side: a NO buy's limit and price are 1 - the YES price
            assert o[key] == (None if want[key] is None else pytest.approx(want[key], abs=1e-9)), (want["id"], key)
    assert isinstance(orders[2]["got"], float) and orders[2]["got"] == 8.0, 'Kalshi\'s "8.00"'
    t = at("2026-10-11T23:30:00Z")
    assert [o["ts"] for o in orders] == [t + 900 + 482, t + 482, t + 482, t + 488, t + 489], "the order row's own ts"
    assert set(bets) == {"KXWTI15M-26OCT112345-45"} and set(decisions) == {"KXWTI15M-26OCT112345-45"}
    bet, decision = bets["KXWTI15M-26OCT112345-45"], decisions["KXWTI15M-26OCT112345-45"]
    assert (bet["status"], bet["fee"], bet["pnl"], bet["contracts"]) == ("won", 0.0216, 0.3064, 8.0)
    assert (decision["yes_bid"], decision["yes_ask"], decision["action"]) == (0.95, 0.959, "bet")
    assert decision["reason"].startswith("bought YES 8")


def test_read_ledger_leaves_the_file_exactly_as_it_was(lf, tmp_path):
    path = parse_ledger(tmp_path)
    folder = path.parent
    before = (path.read_bytes(), os.stat(path).st_mtime_ns, sorted(p.name for p in folder.iterdir()))
    lf.read_ledger(path)
    lf.read_ledger(str(path))
    after = (path.read_bytes(), os.stat(path).st_mtime_ns, sorted(p.name for p in folder.iterdir()))
    assert after[0] == before[0], "byte for byte"
    assert after[1] == before[1], "its modified time too"
    assert after[2] == before[2] == ["live-test.db"], "no -wal, -journal or -shm file left beside it"
    path.rename(folder / "moved.db")   # closed at once: on Windows an open handle would refuse this


def test_a_missing_ledger_is_a_file_not_found_naming_it(lf, tmp_path):
    missing = tmp_path / "nowhere" / "live-prod.db"
    with pytest.raises(FileNotFoundError) as err:
        lf.read_ledger(str(missing))
    assert str(missing) in str(err.value) or err.value.filename == str(missing)
    assert not missing.parent.exists(), "nothing created looking for it"


# ------------------------------------------------------------------ outcome


def test_outcome_takes_the_bets_result_then_the_data(lf):
    o = {"ticker": "T", "side": "yes"}
    market = lambda yes: {"ticker": "T", "yes": yes}  # noqa: E731
    assert lf.outcome(o, {"T": {"status": "lost"}}, market(True)) is False, "a settled bet decides, whatever the data says"
    assert lf.outcome(o, {"T": {"status": "won"}}, None) is True
    assert lf.outcome(o, {"T": {"status": "open"}}, market(True)) is True, "not settled yet: the data"
    assert lf.outcome(o, {}, market(False)) is False
    assert lf.outcome({**o, "side": "no"}, {}, market(False)) is True
    assert lf.outcome({**o, "side": "no"}, {}, market(True)) is False
    assert lf.outcome(o, {}, None) is None and lf.outcome(o, {"T": {"status": "open"}}, None) is None


# ------------------------------------------------------------------ the fill table


def placed(want, got, series="KXBTC15M", n=1):
    """n orders as read_ledger gives them, for the fill table: `got` of `want` contracts each."""
    return [{"id": i, "ticker": f"{series}-26OCT01{i:04d}-00", "series": series, "ts": 1_791_000_000.0 + i,
             "side": "yes", "limit": 0.95, "want": float(want), "got": float(got), "price": 0.95 if got else None}
            for i in range(n)]


@pytest.mark.parametrize("orders, survival, fills", [
    # all filled in full: the book had at least 5 every time, so nothing is known past 5 and fills stop there
    (placed(5, 5, n=3), [1.0, 1.0, 1.0, 1.0, 1.0], {0: 0, 3: 3, 10: 5}),
    # nothing filled: D = 0 twice. The risk set is empty from k = 1, so the list stops there (the spec's "[0.0, ...]")
    (placed(4, 0, n=2), [0.0], {0: 0, 0.5: 0, 2: 0, 4: 0, 10: 0}),
    # one book showed exactly 4, one at least 10: half the books end at 4
    (placed(10, 4) + placed(10, 10), [1.0, 1.0, 1.0, 1.0, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
     {0: 0, 4: 4, 4.5: 4.25, 9.5: 6.75, 10: 7.0, 12.3: 7.0}),
])
def test_the_fill_table_on_the_worked_examples(lf, orders, survival, fills):
    model = lf.depth_model(orders)
    entry = model["all"]
    assert entry["survival"] == pytest.approx(survival, abs=1e-12)
    assert entry["orders"] == len(orders) and entry["maxWant"] == max(int(o["want"]) for o in orders)
    assert isinstance(entry["maxWant"], int)
    assert model["series"]["KXBTC15M"] == entry and model["groups"]["crypto"] == entry, "one series, one group"
    for c, expected in fills.items():
        assert lf.expected_fill(entry, c) == pytest.approx(expected, abs=1e-12), c


def test_the_survival_is_rounded_to_six_places(lf):
    """D = 1, D = 2 and one book of at least 3: P(D > 1) = 2/3, P(D > 2) = 1/3."""
    entry = lf.depth_model(placed(3, 1) + placed(3, 2) + placed(3, 3))["all"]
    assert entry["survival"] == [1.0, 0.666667, 0.333333]


def test_the_survival_stops_at_the_first_empty_risk_set(lf):
    """One order for 10 that got exactly 3: nothing is known past 3, so the list ends before maxWant."""
    entry = lf.depth_model(placed(10, 3))["all"]
    assert entry["survival"] == [1.0, 1.0, 1.0, 0.0] and entry["maxWant"] == 10
    assert lf.expected_fill(entry, 10) == 3.0


def test_expected_fill_sums_the_survival_up_to_the_order(lf):
    entry = {"orders": 1, "maxWant": 3, "survival": [0.8, 0.5, 0.25]}
    for c, expected in ((0, 0.0), (0.5, 0.4), (1, 0.8), (2.5, 1.3 + 0.125), (3, 1.55), (3.5, 1.55), (7, 1.55)):
        assert lf.expected_fill(entry, c) == pytest.approx(expected, abs=1e-12), c


def test_pick_falls_back_from_series_to_group_to_every_order(lf):
    """BTC has exactly MIN_ORDERS of its own; ETH 14, so it takes crypto's 29; gold 3, and metals has only those."""
    model = lf.depth_model(placed(5, 5, "KXBTC15M", 15) + placed(5, 0, "KXETH15M", 14) + placed(2, 1, "KXGOLD15M", 3))
    assert {k: e["orders"] for k, e in model["series"].items()} == {"KXBTC15M": 15, "KXETH15M": 14, "KXGOLD15M": 3}
    assert {k: e["orders"] for k, e in model["groups"].items()} == {"crypto": 29, "metals": 3}, "groups from universe.json"
    assert model["all"]["orders"] == 32
    assert model["series"]["KXBTC15M"]["survival"] == [1.0] * 5
    assert model["groups"]["crypto"]["survival"] == [round(15 / 29, 6)] * 5
    assert model["groups"]["metals"]["survival"] == [1.0, 0.0]
    assert model["all"]["survival"] == [0.5625, 0.46875, 0.46875, 0.46875, 0.46875]
    assert lf.pick(model, "KXBTC15M", "crypto") == model["series"]["KXBTC15M"]
    assert lf.pick(model, "KXETH15M", "crypto") == model["groups"]["crypto"]
    assert lf.pick(model, "KXGOLD15M", "metals") == model["all"]
    assert lf.pick(model, "KXNEW15M", "crypto") == model["groups"]["crypto"], "a series with no orders yet: its group's"
    assert lf.pick(model, "KXNEW15M", "rates") == model["all"]


# ------------------------------------------------------------------ compare


@pytest.fixture
def compare_case(study, windows, tmp_path):
    """Eight orders: six on the synthetic history's markets, one of each kind compare has to tell apart, and two on
    markets it doesn't have. With them, the history with one of those markets' minute-8 quote blanked, and a trade
    tape (sb.LIQUIDITY) for four of them plus two it must ignore (no ask to price the model at)."""
    sb = study.strategies_backtest
    used = set()

    def market(series, lo, hi):
        for t in sorted(windows):
            for m in windows[t]:
                side, top = sb.favourite(*m["q"][8])
                if side and m["series"] == series and lo <= top < hi and m["ticker"] not in used:
                    used.add(m["ticker"])
                    return SimpleNamespace(t=t, m=m, side=side, ask=sb.own_quote(m, side, 8)[1])
        raise AssertionError(f"the synthetic history has no {series} favourite at {lo}-{hi}")
    m1, m2 = market("KXBTC15M", 0.90, 0.915), market("KXBTC15M", 0.92, 0.945)
    m3, m4 = market("KXETH15M", 0.95, 0.998), market("KXGOLD15M", 0.95, 0.998)
    m5, m6 = market("KXBTC15M", 0.95, 0.998), market("KXETH15M", 0.92, 0.945)
    data_won = lambda x: (x.side == "yes") == x.m["yes"]  # noqa: E731
    later = datetime(2026, 10, 5, 12, 15, tzinfo=UTC)
    off_sol, off_btc = ticker_for("KXSOL15M", later), ticker_for("KXBTC15M", later)
    # (name, market or None, ticker, side, limit, want, got, price, the bet's result (None: open), expected outcome)
    specs = [
        ("o1", m1, None, m1.side, round(m1.ask + 0.001, 4), 3, 3, round(m1.ask - 0.001, 4), not data_won(m1), not data_won(m1)),
        ("o2", m2, None, m2.side, m2.ask, 15, 4, m2.ask, None, data_won(m2)),
        ("o3", m3, None, m3.side, round(m3.ask + 0.001, 4), 16, 0, None, None, data_won(m3)),
        ("o4", m4, None, m4.side, m4.ask, 31, 31, round(m4.ask - 0.01, 4), data_won(m4), data_won(m4)),
        ("o5", m5, None, m5.side, m5.ask, 30, 30, m5.ask, None, data_won(m5)),
        ("o6", m6, None, m6.side, m6.ask, 1, 0, None, None, data_won(m6)),
        ("o7", None, off_sol, "yes", 0.93, 5, 0, None, None, None),
        ("o8", None, off_btc, "no", 0.97, 6, 6, 0.965, False, False),
    ]
    led = Ledger(tmp_path / "ledger" / "live-test.db")
    recs = []
    for name, mk, ticker, side, limit, want, got, price, won, outcome in sorted(
            specs, key=lambda s: s[1].t if s[1] else at("2026-10-05T12:15:00Z")):   # sent in time order: ids follow ts
        ts = (mk.t if mk else at("2026-10-05T12:15:00Z")) + 482
        r = led.order(mk.m["ticker"] if mk else ticker, side, limit, want, got, ts=ts, price=price, won=won)
        r.name, r.outcome, r.mk = name, outcome, mk
        r.group = mk.m["group"] if mk else ("crypto" if r.series == "KXBTC15M" else "other")
        r.ask = None if mk is None or mk is m5 else mk.ask      # m5's quote is blanked below
        recs.append(r)
    led.close()
    blank = dict(m5.m, q={**m5.m["q"], 8: (None, None)})
    blanked = dict(windows)
    blanked[m5.t] = [blank if m is m5.m else m for m in windows[m5.t]]
    tape = {m1.m["ticker"]: [None, None, 1.0],                    # a quiet book: QUIET contracts, all 3 asked
            m2.m["ticker"]: [3.0, round(m2.ask + 0.01, 3), 0.0],  # the price ran away: none
            m3.m["ticker"]: [None, None, 20.0],                   # 16 of 16
            m6.m["ticker"]: [2.0, round(m6.ask + 0.01, 3), 0.0],  # ran away: none
            m5.m["ticker"]: [None, None, 5.0],                    # no ask at minute 8: no model
            off_btc: [None, None, 5.0]}                           # not in the data: no model
    expect_tape = {"o1": 3, "o2": 0, "o3": 16, "o6": 0}
    for r in recs:
        r.tape = expect_tape.get(r.name)
    return SimpleNamespace(path=led.path, orders=recs, by={r.name: r for r in recs}, windows=blanked, tape=tape)


def per_order(out, orders):
    """compare's per-order records: a list it returns under "orders" if it returns one, else the order dicts it was
    given, which it fills in place (the spec says it "adds" each field)."""
    return out.get("orders", orders) if isinstance(out, dict) else orders


def expected_row(key, recs):
    known = [r for r in recs if r.outcome is not None]
    asked, got = sum(r.want for r in recs), sum(r.got for r in recs)
    return {"key": key, "orders": len(recs), "none": sum(r.got == 0 for r in recs), "asked": asked, "got": got,
            "fillRate": got / asked,
            "filledWon": sum(bool(r.outcome) for r in known if r.got > 0), "filledN": sum(r.got > 0 for r in known),
            "missedWon": sum(bool(r.outcome) for r in known if r.got == 0), "missedN": sum(r.got == 0 for r in known)}


def test_the_compare_case_is_what_the_tests_say(study, compare_case, monkeypatch):
    """The fixture on its own: each market where it was meant to be, and the ledger holding all eight orders."""
    sb, c = study.strategies_backtest, compare_case
    assert [band_of(c.by[n].limit) for n in ("o1", "o2", "o3", "o4", "o5", "o6", "o7", "o8")] == \
        ["90–91", "92–94", "95+", "95+", "95+", "92–94", "92–94", "95+"]
    assert {size_of(r.want) for r in c.orders} == {"1–5", "6–15", "16–30", "31+"}
    monkeypatch.setattr(sb, "LIQUIDITY", c.tape)
    for name in ("o1", "o2", "o3", "o6"):
        r = c.by[name]
        assert sb.available(r.mk.m, r.ask, r.want) == r.tape, name
    con = sqlite3.connect(c.path)
    try:
        assert con.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 8
        assert con.execute("SELECT COUNT(*) FROM bets").fetchone()[0] == 5
        ids_by_ts = [r[0] for r in con.execute("SELECT id FROM orders ORDER BY ts, id")]
        assert ids_by_ts == sorted(ids_by_ts), "sent in time order"
    finally:
        con.close()


def test_compare_sets_each_order_against_the_data(lf, study, compare_case, monkeypatch):
    sb = study.strategies_backtest
    monkeypatch.setattr(sb, "LIQUIDITY", compare_case.tape)
    orders, bets, decisions = lf.read_ledger(str(compare_case.path))
    out = lf.compare(orders, bets, decisions, compare_case.windows)
    got = {o["ticker"]: o for o in per_order(out, orders)}
    assert len(got) == 8
    for r in compare_case.orders:
        o = got[r.ticker]
        assert o["group"] == r.group, r.name          # a series universe.json doesn't know is "other", as sb.load has it
        assert o["ask"] == r.ask, r.name              # the minute-8 ask on its own side; None off the data or unquoted
        if r.mk is not None and r.ask is not None:
            assert o["ask"] == sb.own_quote(r.mk.m, r.side, 8)[1]
        assert o["won"] is r.outcome, r.name          # o1's settled bet overrides the data; o7 is nowhere: None
        assert o["tape"] == r.tape, r.name            # sb.available at the ask; None with no tape or no ask


def test_compare_summary_counts_gaps_wins_and_fees(lf, study, compare_case):
    sb = study.strategies_backtest
    orders, bets, decisions = lf.read_ledger(str(compare_case.path))
    s = lf.compare(orders, bets, decisions, compare_case.windows)["summary"]
    assert (s["orders"], s["none"], s["partial"], s["full"]) == (8, 3, 1, 4)
    assert (s["asked"], s["got"]) == (107, 74) and s["fillRate"] == pytest.approx(74 / 107)
    first, last = min(r.ts for r in compare_case.orders), max(r.ts for r in compare_case.orders)
    for key, ts in (("from", first), ("to", last)):
        when = datetime.fromisoformat(s[key].replace("Z", "+00:00"))
        assert when.utcoffset() == timedelta(0) and when.timestamp() == ts, key
    assert s["dataEnd"] == study.history.end()
    # In cents a contract, weighted by contracts got. By construction: o1 filled 0.2c under its limit, which was 0.1c
    # over the ask; o4 1c under; o8 0.5c under (off the data); o3's limit 0.1c over its ask.
    g = s["gap"]
    assert g["fillVsLimit"] == pytest.approx(-34.6 / 74)    # o1, o2, o4, o5, o8
    assert g["limitVsAsk"] == pytest.approx(0.2 / 5)        # o1, o2, o3, o4, o6: unweighted
    assert g["fillVsAsk"] == pytest.approx(-31.3 / 38)      # o1, o2, o4: filled and quoted
    assert g["n"] == 3
    recs = compare_case.orders
    filled = [r for r in recs if r.got > 0 and r.outcome is not None]
    missed = [r for r in recs if r.got == 0 and r.outcome is not None]
    assert s["won"] == {"filled": [sum(r.outcome for r in filled), 5], "missed": [sum(r.outcome for r in missed), 2]}
    assert len(filled) == 5 and len(missed) == 2, "o7's outcome is unknown: left out"
    fills = [r for r in recs if r.got > 0]
    fee = s["fee"]
    assert fee["paid"] == pytest.approx(sum(r.fee for r in fills))
    assert fee["exact"] == pytest.approx(sum(0.07 * r.got * r.price * (1 - r.price) for r in fills))
    assert fee["rounded"] == pytest.approx(sum(sb.fee(r.got, r.price) for r in fills))
    assert fee["paid"] < fee["exact"] < fee["rounded"], "the three differ, so each is tested"


def test_compare_breaks_the_orders_down(lf, compare_case):
    orders, bets, decisions = lf.read_ledger(str(compare_case.path))
    out = lf.compare(orders, bets, decisions, compare_case.windows)
    recs = compare_case.orders
    for kind, key_of, keys in (("byBand", lambda r: band_of(r.limit), [b[2] for b in BANDS]),
                               ("bySize", lambda r: size_of(r.want), [s[2] for s in SIZES])):
        assert [row["key"] for row in out[kind]] == keys, kind
        for row in out[kind]:
            assert row == pytest.approx(expected_row(row["key"], [r for r in recs if key_of(r) == row["key"]])), (kind, row["key"])
    # The series key is the series as on the order (the ticker before its first "-"): the spec doesn't name it.
    series = out["bySeries"]
    assert {row["key"] for row in series} == {"KXBTC15M", "KXETH15M", "KXGOLD15M", "KXSOL15M"}
    assert [row["orders"] for row in series] == sorted((row["orders"] for row in series), reverse=True), "most first"
    assert series[0]["key"] == "KXBTC15M" and series[0]["orders"] == 4
    for row in series:
        assert row == pytest.approx(expected_row(row["key"], [r for r in recs if r.series == row["key"]]))
    groups = {row["key"]: row for row in out["byGroup"]}
    assert set(groups) == {"crypto", "metals", "other"}
    for key, row in groups.items():
        assert row == pytest.approx(expected_row(key, [r for r in recs if r.group == key]))


def test_compare_checks_the_tape_model_against_the_real_fills(lf, study, compare_case, monkeypatch):
    monkeypatch.setattr(study.strategies_backtest, "LIQUIDITY", compare_case.tape)
    orders, bets, decisions = lf.read_ledger(str(compare_case.path))
    tape = lf.compare(orders, bets, decisions, compare_case.windows)["tape"]
    assert (tape["orders"], tape["predicted"], tape["real"]) == (4, 19, 7), "o1, o2, o3, o6: 3 + 0 + 16 + 0 against 3 + 4"
    assert tape["table"] == {"model none/real none": 1, "model none/real some": 1,
                             "model some/real none": 1, "model some/real some": 1}


def test_compare_with_nothing_in_the_data_and_no_tape(lf, study, windows, tmp_path, monkeypatch):
    """Orders the data doesn't have: no ask, so no gap needs one; the fill-vs-limit gap still has its fills. Each gap
    is read as None when its own orders are none (the spec's "None if n == 0"). With no orders filled, it's None too."""
    monkeypatch.setattr(study.strategies_backtest, "LIQUIDITY", None)
    later = datetime(2026, 10, 6, 3, 0, tzinfo=UTC)
    led = Ledger(tmp_path / "ledger" / "live-test.db")
    led.order(ticker_for("KXBTC15M", later), "yes", 0.95, 4, 4, ts=later.timestamp() + 482, price=0.949, won=True)
    led.order(ticker_for("KXETH15M", later), "yes", 0.93, 5, 0, ts=later.timestamp() + 482)
    orders, bets, decisions = lf.read_ledger(str(led.close()))
    out = lf.compare(orders, bets, decisions, windows)
    s = out["summary"]
    assert s["gap"]["fillVsLimit"] == pytest.approx(-0.1)
    assert (s["gap"]["limitVsAsk"], s["gap"]["fillVsAsk"], s["gap"]["n"]) == (None, None, 0)
    assert s["won"] == {"filled": [1, 1], "missed": [0, 0]}, "the missed order's market is nowhere: unknown"
    recs = per_order(out, orders)
    assert [o["ask"] for o in recs] == [None, None] and [o["tape"] for o in recs] == [None, None]
    assert [o["won"] for o in recs] == [True, None], "the filled one's settled bet; the other is unknown"
    assert not out["tape"] or out["tape"]["orders"] == 0
    missed = [o for o in orders if o["got"] == 0]
    gap = lf.compare(missed, bets, decisions, windows)["summary"]["gap"]
    assert (gap["fillVsLimit"], gap["limitVsAsk"], gap["fillVsAsk"], gap["n"]) == (None, None, None, 0)


# ------------------------------------------------------------------ replay


def blacked_out(sb, t):
    return any(t < z and t + 900 > a for a, z in sb.LIVE[0]["blackouts"])


def rule(sb, t, m):
    """The live rule's pick of market m in window t, as sb.run makes it for sb.LIVE[0]: (side, top), or None."""
    live = sb.LIVE[0]
    if blacked_out(sb, t) or m["group"] not in live["groups"]:
        return None
    side, top = sb.favourite(*m["q"][live["minute"]])
    if side and live.get("lo", sb.LO) <= top <= live.get("hi", sb.HI) and not sb.skipped(live, m, side):
        return side, top
    return None


@pytest.fixture
def replay_case(study, windows, tmp_path):
    """The bot's orders from Sep 16: three of the live rule's picks bought on its side and one on the other; one
    market of each kind the rule passes over (out of the band, a warning sign, the Fed blackout, a group it doesn't
    trade), all filled and settled as the data says; and two on markets the data doesn't have, which got nothing,
    the first of them opening the replay. Five more of the rule's picks get the decisions the bot logs when it
    skips."""
    sb = study.strategies_backtest
    live = sb.LIVE[0]
    w0 = at("2026-09-16T00:00:00Z")
    covered = [t for t in sorted(windows) if t >= w0]
    picks = [(t, m, *p) for t in covered for m in windows[t] if (p := rule(sb, t, m))]
    assert len(picks) >= 9

    def first(test):
        for t in covered:
            for m in windows[t]:
                side, top = sb.favourite(*m["q"][live["minute"]])
                if side and test(t, m, side, top):
                    return t, m, side, top
        raise AssertionError("the synthetic history has no such market")
    band = lambda top: sb.LO <= top <= sb.HI  # noqa: E731
    edge = lambda m: m["group"] in live["groups"]  # noqa: E731
    skip = lambda m, side: sb.skipped(live, m, side)  # noqa: E731
    passed = {  # each fails exactly one of the rule's tests
        "outside": first(lambda t, m, s, top: not blacked_out(sb, t) and edge(m) and not band(top) and not skip(m, s)),
        "warning": first(lambda t, m, s, top: not blacked_out(sb, t) and edge(m) and band(top) and skip(m, s)),
        "blackout": first(lambda t, m, s, top: blacked_out(sb, t) and edge(m) and band(top) and not skip(m, s)),
        "other": first(lambda t, m, s, top: not blacked_out(sb, t) and not edge(m) and band(top) and not skip(m, s)),
    }
    sent = [(t, m, side, top) for t, m, side, top in picks[:3]]
    t, m, side, top = picks[3]
    sent.append((t, m, "no" if side == "yes" else "yes", 0.90))     # the bot saw the other side as the favourite
    sent += [(t, m, side, top if band(top) else 0.90) for t, m, side, top in passed.values()]
    led = Ledger(tmp_path / "ledger" / "live-test.db")
    gone = [led.order(ticker_for("KXBTC15M", datetime(2026, 9, 16, tzinfo=UTC), "ZZ"), "yes", 0.95, 10, 0, ts=w0 + 482)]
    fills = [led.order(m["ticker"], side, limit, 10, 10, ts=t + 482, won=(side == "yes") == m["yes"])
             for t, m, side, limit in sorted(sent, key=lambda x: x[0])]
    after = datetime(2026, 10, 5, 12, 30, tzinfo=UTC)                 # after the data ends
    gone.append(led.order(ticker_for("KXETH15M", after), "no", 0.93, 10, 0, ts=after.timestamp() + 482))
    reasons = [("halted", "halted: 3 orders failed in a row"),
               ("skip", "warning sign: its ask is 2.0c over its bid (2c or more)"),
               ("skip", "favorite at 89.5c is outside 90-99.9c"),
               ("skip", "couldn't read its minute-by-minute prices to check the warning signs"),   # not a sign: other
               ("skip", "order limit reached")]
    for (t, m, side, top), (action, reason) in zip(picks[4:9], reasons):
        led.decide(m["ticker"], t + 482, action, reason, *m["q"][8], side, top)
    return SimpleNamespace(path=led.close(), covered=covered, picks=picks, fills=fills, gone=gone, passed=passed)


def test_the_replay_case_is_what_the_tests_say(study, replay_case):
    sb, c = study.strategies_backtest, replay_case
    tickers = {m["ticker"] for _, m, _, _ in c.picks}
    assert not tickers & {m["ticker"] for _, m, _, _ in c.passed.values()}, "none of those four is a pick"
    assert len(c.fills) == 8 and all(f.got == f.want == 10 for f in c.fills)
    assert all(blacked_out(sb, t) == (k == "blackout") for k, (t, _, _, _) in c.passed.items())
    con = sqlite3.connect(c.path)
    try:
        first = con.execute("SELECT ticker, ts FROM orders ORDER BY id LIMIT 1").fetchone()
        assert first == (c.gone[0].ticker, c.covered[0] + 482), "the first order opens the replay at Sep 16 00:00"
        assert con.execute("SELECT COUNT(*) FROM decisions WHERE action != 'bet'").fetchone()[0] == 5 + 2
    finally:
        con.close()


def running(decisions):
    """The windows the bot was running in: those it logged a decision in (it logs one for every market it looks at,
    bought or not). The live bot ran Sep 28-30 and again from Oct 10, so the days between aren't the bot's to answer for."""
    return {d["ts"] // 900 * 900 for d in decisions.values()}


def test_replay_matches_the_backtests_picks_against_the_bots_orders(lf, study, windows, replay_case):
    sb, c = study.strategies_backtest, replay_case
    orders, bets, decisions = lf.read_ledger(str(c.path))
    r = lf.replay(orders, decisions, windows)
    # The data's windows from the first order's window on that the bot was running in (it logged a decision there):
    # the synthetic history has 8 a day, and the bot looked at only some of them.
    on = running(decisions)
    covered = [t for t in c.covered if t in on]
    assert 0 < len(covered) < len(c.covered), "the case has windows the bot wasn't running in"
    assert r["windows"] == len(covered)
    assert r["both"] == {"n": 4, "sameSide": 3}
    n = sum(t in on for t, _, _, _ in c.picks)
    assert n < len(c.picks), "and picks in them, which aren't counted against the bot"
    assert r["backtestOnly"]["n"] == n - 4
    assert r["backtestOnly"]["why"] == {"halted": 1, "warning sign": 1, "outside the band": 1, "other skip": 2,
                                        "no decision": n - 9}
    assert r["liveOnly"]["n"] == 6
    assert r["liveOnly"]["why"] == {"not in the data": 2, "outside the band at the candle": 1,
                                    "warning sign at the candle": 1, "blackout": 1, "other": 1}


def test_replay_prices_both_sides_at_10_dollars_a_bet(lf, study, windows, replay_case):
    """The backtest: every pick at its candle ask, filled in full ($10 / ask contracts, as sb.run's $10 accounts buy),
    with sb.fee. The live bot: each fill's real profit scaled to a $10 stake, so every bet weighs the same. Both in
    cents per $10 staked, as sb.run reports perBet."""
    sb, c = study.strategies_backtest, replay_case
    orders, bets, decisions = lf.read_ledger(str(c.path))
    per = lf.replay(orders, decisions, windows)["perBet"]
    on = running(decisions)
    mine = [(t, m, side, top) for t, m, side, top in c.picks if t in on]   # only the windows the bot was running in
    pnl = 0.0
    for _, m, side, top in mine:
        k = 10 / top
        pnl += (k if (side == "yes") == m["yes"] else 0.0) - 10 - sb.fee(k, top)
    assert per["backtest"] == pytest.approx(pnl / (10 * len(mine)) * 1000, rel=1e-9)
    assert per["backtestBets"] == len(mine) and per["liveBets"] == len(c.fills)
    # replay isn't given the bets, so the spec leaves open which record of the real fee it reads: the order's own
    # answer (average_fee_paid x contracts) or Kalshi's exact 0.07 x C x P x (1 - P). Here they and the bet's fee all
    # differ by under 0.06c per $10; weighting bets by their cost instead of $10 each would move it about 1c.
    live = [f.pnl / (f.got * f.price) * 10 for f in c.fills]
    assert per["live"] == pytest.approx(sum(live) / (10 * len(live)) * 1000, abs=0.06)
    cost_weighted = sum(f.pnl for f in c.fills) / sum(f.got * f.price for f in c.fills) * 1000
    assert abs(cost_weighted - sum(live) / (10 * len(live)) * 1000) > 0.5, "the case can tell the two weightings apart"
    # The markets both bought, side by side: what the backtest makes of them against what the bot really made, so the
    # gap is the fills alone (the price paid, the fee, the side), not which markets each picked.
    same = {f.ticker for f in c.fills} & {m["ticker"] for _, m, _, _ in mine}
    assert len(same) == 4
    bt = [((10 / top if (side == "yes") == m["yes"] else 0.0) - 10 - sb.fee(10 / top, top)) / 10
          for _, m, side, top in mine if m["ticker"] in same]
    lv = [f.pnl / (f.got * f.price) for f in c.fills if f.ticker in same]
    assert per["same"]["n"] == 4
    assert per["same"]["backtest"] == pytest.approx(sum(bt) / 4 * 1000, rel=1e-9)
    assert per["same"]["live"] == pytest.approx(sum(lv) / 4 * 1000, abs=0.06)


# ------------------------------------------------------------------ candidates


@pytest.fixture
def candidates_case(study, tmp_path):
    """The bot's orders in six windows, each a case for one of the Oct 11 lab's rules. Every fill is 10 contracts
    with a 4c fee, so each profit has two places and the totals round cleanly."""
    sb = study.strategies_backtest
    w = {k: at(s) for k, s in (("w1", "2026-09-28T12:30:00Z"), ("w2", "2026-09-28T13:00:00Z"),
                               ("w4", "2026-09-28T14:00:00Z"), ("w5", "2026-09-29T13:30:00Z"),
                               ("w6", "2026-10-03T13:30:00Z"), ("w7", "2026-09-29T13:45:00Z"))}
    led = Ledger(tmp_path / "ledger" / "live-test.db")
    rec = {}

    def put(name, series, side, limit, got, window, won=None, **kw):
        ticker = f"{series}-{datetime.fromtimestamp(w[window] + 900, UTC):%y%b%d%H%M}".upper() + f"-{name}"
        rec[name] = led.order(ticker, side, limit, 10, got, ts=w[window] + 482, won=won, fee=0.04, **kw)
    # w1, Monday 8:30 ET: six crypto orders, in the order the bot sent them (so ids rise down the list), all at the
    # same ts as one step sends them. Spreads from the decisions: C 0.5c; A, B and E 1c once rounded to 4 places
    # (0.96 - 0.95 is 0.0100...09 in floats, 0.94 - 0.93 is 0.00999...); D has no decision and F one with no
    # prices: no spread, last. Kept under 3 a window: C, then A (the dearest at 1c), then B (before E by id).
    put("B", "KXBTC15M", "yes", 0.94, 10, "w1", True, book=(0.93, 0.94))
    put("E", "KXETH15M", "yes", 0.94, 10, "w1", True, book=(0.93, 0.94))
    put("D", "KXBTC15M", "yes", 0.99, 0, "w1", book=None)
    put("C", "KXETH15M", "no", 0.96, 10, "w1", False, book=(0.04, 0.045))
    put("A", "KXBTC15M", "yes", 0.96, 10, "w1", False, book=(0.95, 0.96))
    put("F", "KXETH15M", "yes", 0.97, 10, "w1", False, book=(None, None))
    # w2, 9:00 ET: three crypto and a metals one, under the cap: nothing dropped
    put("G1", "KXBTC15M", "yes", 0.95, 10, "w2", True, book=(0.93, 0.95))
    put("G2", "KXETH15M", "yes", 0.96, 10, "w2", True, book=(0.93, 0.96))
    put("G3", "KXBTC15M", "no", 0.92, 10, "w2", False)
    put("G4", "KXGOLD15M", "yes", 0.95, 10, "w2", True)
    # w4, 10:00 ET: HYPE twice (a group universe.json doesn't have here, so never crypto's cap) and BTC
    put("H1", "KXHYPE15M", "yes", 0.95, 10, "w4", False)
    put("H2", "KXHYPE15M", "no", 0.93, 0, "w4")
    put("K1", "KXBTC15M", "yes", 0.97, 10, "w4", True)
    # w5, Tuesday 9:30 ET (13:30 UTC in summer time): the stock market's open
    put("S1", "KXBTC15M", "yes", 0.95, 10, "w5", True)
    put("S2", "KXGOLD15M", "no", 0.94, 10, "w5", False)
    put("S3", "KXETH15M", "yes", 0.96, 0, "w5")
    # w6, a Saturday at 9:30 ET, and w7, that Tuesday at 9:45: neither is skipped
    put("S4", "KXBTC15M", "yes", 0.95, 10, "w6", True)
    put("S5", "KXBTC15M", "yes", 0.93, 10, "w7", False)
    return SimpleNamespace(path=led.close(), rec=rec, w=w, hype={"H1", "H2"}, slot={"S1", "S2", "S3"},
                           cap={"E", "D", "F"})


def test_the_candidates_case_is_what_the_tests_say(study, candidates_case):
    sb, w = study.strategies_backtest, candidates_case.w
    assert [sb.slot(w[k]) for k in ("w1", "w2", "w4", "w5", "w6", "w7")] == ["08:30", "09:00", "10:00", "09:30", None, "09:45"]
    rec = candidates_case.rec
    assert all(rec[k].window == w["w1"] for k in "ABCDEF")
    assert sum(r.got > 0 for r in rec.values()) == 15 and rec["A"].pnl == pytest.approx(-9.64)


def test_candidates_count_the_live_bets_each_lab_rule_would_have_dropped(lf, study, candidates_case):
    sb, c = study.strategies_backtest, candidates_case
    orders, bets, decisions = lf.read_ledger(str(c.path))
    out = lf.candidates(orders, bets, decisions)

    def tally(names):
        rs = [c.rec[n] for n in names]
        fills = [r for r in rs if r.got > 0]
        return {"dropped": len(fills), "wins": sum(bool(r.won) for r in fills), "pnl": round(sum(r.pnl for r in fills), 2),
                "missed": sum(r.got == 0 for r in rs)}
    expect = {}
    for s in sb.LIVE:
        if s.get("role") != "candidate" or not any(s.get(k) for k in ("skipSeries", "skipSlots", "maxPer")):
            continue
        assert set(s.get("skipSeries") or ()) <= {"KXHYPE15M"} and set(s.get("skipSlots") or ()) <= {"09:30"} \
            and (s.get("maxPer") or {}) in ({}, {"crypto": 3}), "the cases here are written for the Oct 11 lab's rules"
        names = (c.hype if s.get("skipSeries") else set()) | (c.slot if s.get("skipSlots") else set()) \
            | (c.cap if s.get("maxPer") else set())
        expect[s["id"]] = {"name": s["name"], **tally(names)}
    assert {"livenh", "liveno", "livec3", "live3x"} <= set(expect)
    assert set(out) == set(expect), "one entry per candidate account"
    for sid, want in expect.items():
        assert out[sid] == {**want, "pnl": pytest.approx(want["pnl"], abs=1e-9)}, sid
    # by hand, for the four the lab made
    assert {k: out["livenh"][k] for k in ("dropped", "wins", "missed")} == {"dropped": 1, "wins": 0, "missed": 1}
    assert {k: out["liveno"][k] for k in ("dropped", "wins", "missed")} == {"dropped": 2, "wins": 1, "missed": 1}
    assert {k: out["livec3"][k] for k in ("dropped", "wins", "missed")} == {"dropped": 2, "wins": 1, "missed": 1}
    assert out["livec3"]["pnl"] == pytest.approx(0.56 - 9.74), "E (won at 94c) and F (lost at 97c), not A"
    assert {k: out["live3x"][k] for k in ("dropped", "wins", "missed")} == {"dropped": 5, "wins": 2, "missed": 3}


# ------------------------------------------------------------------ main


def test_main_writes_live_fills_json_and_reports(lf, study, windows, compare_case, written, capsys, monkeypatch):
    monkeypatch.setattr(study.strategies_backtest, "LIQUIDITY", compare_case.tape)   # so the report has a tape check
    before = compare_case.path.read_bytes()
    assert lf.main([str(compare_case.path)]) == 0
    out = json.loads(written.read_text(encoding="utf-8"))
    assert {"ledger", "summary", "byBand", "bySize", "bySeries", "byGroup", "tape", "depth", "replay", "candidates",
            "orders"} <= set(out)
    assert Path(out["ledger"]).name == compare_case.path.name
    orders, bets, decisions = lf.read_ledger(str(compare_case.path))
    c = lf.compare(orders, bets, decisions, windows)
    for key in ("summary", "byBand", "bySize", "bySeries", "byGroup", "tape"):
        assert out[key] == roundtrip(c[key]), key
    assert out["depth"] == roundtrip(lf.depth_model(orders))
    assert out["replay"] == roundtrip(lf.replay(orders, decisions, windows))
    assert out["candidates"] == roundtrip(lf.candidates(orders, bets, decisions))
    assert out["orders"] == roundtrip(per_order(c, orders))
    assert len(out["orders"]) == 8 and all({"ask", "won", "tape"} <= set(o) for o in out["orders"])
    assert compare_case.path.read_bytes() == before, "the ledger is only read"
    printed = capsys.readouterr().out
    assert printed.strip() and "fill" in printed.lower()
    assert "trade-tape model on 5 orders" in printed, "main reads the history whole: m5 keeps its minute-8 ask here"


def test_main_reports_a_ledger_with_nothing_in_the_data(lf, written, tmp_path, capsys):
    """Every order after the data ends: no ask, no gap against it, no backtest picks to replay. The report must still
    print (its None values included) and the file still be written."""
    later = datetime(2026, 10, 6, 3, 0, tzinfo=UTC)
    led = Ledger(tmp_path / "ledger" / "live-test.db")
    led.order(ticker_for("KXBTC15M", later), "yes", 0.95, 10, 4, ts=later.timestamp() + 482, won=True)
    led.order(ticker_for("KXETH15M", later), "no", 0.93, 10, 0, ts=later.timestamp() + 482)
    assert lf.main([str(led.close())]) == 0
    out = json.loads(written.read_text(encoding="utf-8"))
    assert out["summary"]["orders"] == 2 and out["summary"]["gap"]["n"] == 0 and out["summary"]["gap"]["fillVsAsk"] is None
    assert all(o["ask"] is None for o in out["orders"])
    r = out["replay"]
    assert r["windows"] == 0 and r["both"]["n"] == 0 and r["backtestOnly"]["n"] == 0
    assert r["liveOnly"] == {"n": 2, "why": {**{k: 0 for k in r["liveOnly"]["why"]}, "not in the data": 2}}
    assert r["perBet"]["backtest"] is None, "no picks: None, as sb.run reports perBet with nothing staked"
    assert capsys.readouterr().out.strip()


def test_main_without_a_ledger_says_so_and_exits_1(lf, written, tmp_path, capsys):
    missing = tmp_path / "nowhere.db"
    assert lf.main([str(missing)]) == 1
    printed = capsys.readouterr()
    assert "nowhere.db" in printed.out + printed.err, "the message names the file it looked for"
    assert not written.exists() and not missing.exists()
