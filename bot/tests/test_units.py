"""bot.py's building blocks, one at a time: time and money helpers, .env parsing, market grouping, fees and
sizing, the database, the halt file, blackouts and maintenance hours, and the order-book and order helpers.

    python -m pytest tests/test_units.py -q
"""
import json
import os
import random
import sqlite3
import types
import uuid
from datetime import datetime, timezone

import pytest

from kalshi_bot import bot
from test_bot import W, env, fake_bet  # noqa: F401 (env is a fixture)


# ------------------------------------------------------------------ time and money
def test_ts_and_iso_round_trip():
    assert bot.iso(bot.ts("2026-09-28T16:00:00Z")) == "2026-09-28T16:00:00Z"
    assert bot.ts("2026-09-28T16:00:00Z") == bot.ts("2026-09-28T16:00:00+00:00")
    assert bot.ts("2026-09-28T16:00:00Z") == datetime(2026, 9, 28, 16, tzinfo=timezone.utc).timestamp()
    assert bot.ts("2026-09-28T12:00:00-04:00") == bot.ts("2026-09-28T16:00:00Z")  # any offset
    assert bot.iso(bot.ts("2026-09-28T16:00:00Z") + 0.9) == "2026-09-28T16:00:00Z"  # whole seconds


@pytest.mark.parametrize("x, want", [(2.0, 2.0), (1.999, 1.99), (0.29, 0.29), (0.07, 0.07), (2.8599999999, 2.86),
                                     (0.0, 0.0), (0.009, 0.0), (33.3333, 33.33)])
def test_floor_cents_rounds_down_but_not_on_float_noise(x, want):
    assert bot.floor_cents(x) == want


# ------------------------------------------------------------------ .env
@pytest.fixture
def clean_env(monkeypatch):
    for k in [k for k in os.environ if k.startswith("KALSHI_")]:
        monkeypatch.delenv(k)


def test_load_env_parses_the_file(tmp_path, clean_env):
    p = tmp_path / ".env"
    p.write_text("# a comment\n\nKALSHI_ENV=prod\n  KALSHI_API_KEY_ID = abc-123  \nKALSHI_PRIVATE_KEY_PATH=\"C:\\keys\\k.pem\"\n"
                 "OTHER='single quoted'\nno equals sign here\nWITH_EQ=a=b=c\n", encoding="utf-8")
    e = bot.load_env(str(p))
    assert e["KALSHI_ENV"] == "prod" and e["KALSHI_API_KEY_ID"] == "abc-123"
    assert e["KALSHI_PRIVATE_KEY_PATH"] == "C:\\keys\\k.pem"     # quotes stripped, backslashes kept
    assert e["OTHER"] == "single quoted" and e["WITH_EQ"] == "a=b=c"
    assert "# a comment" not in e and len(e) == 5


def test_the_real_environment_beats_the_file_but_only_for_kalshi_vars(tmp_path, clean_env, monkeypatch):
    p = tmp_path / ".env"
    p.write_text("KALSHI_ENV=demo\nKALSHI_API_KEY_ID=from-file\n", encoding="utf-8")
    monkeypatch.setenv("KALSHI_ENV", "prod")
    monkeypatch.setenv("UNRELATED_SECRET", "nope")
    e = bot.load_env(str(p))
    assert e["KALSHI_ENV"] == "prod" and e["KALSHI_API_KEY_ID"] == "from-file"
    assert "UNRELATED_SECRET" not in e


def test_load_env_without_a_file_uses_the_environment(tmp_path, clean_env, monkeypatch):
    monkeypatch.setenv("KALSHI_ENV", "prod")
    assert bot.load_env(str(tmp_path / "nope.env")) == {"KALSHI_ENV": "prod"}
    monkeypatch.delenv("KALSHI_ENV")
    assert bot.load_env(str(tmp_path / "nope.env")) == {}


# ------------------------------------------------------------------ grouping
@pytest.mark.parametrize("ticker, category, group", [
    ("KXCRYPTOLEAD15M", "Crypto", "coin race"), ("KXCRYPTOCOMP15M", "Crypto", "coin race"),
    ("KXGOLD15M", "Commodities", "metals"), ("KXSILVER15M", "", "metals"), ("KXPLATINUM15M", "", "metals"),
    ("KXPALLADIUM15M", "", "metals"), ("KXCOPPER15M", "", "metals"),
    ("KXWTI15M", "", "energy"), ("KXNATGAS15M", "", "energy"), ("KXOIL15M", "", "energy"),
    ("KXEURUSD15M", "", "fx"), ("KXGBPUSD15M", "", "fx"), ("KXUSDJPY15M", "", "fx"),
    ("KXRATECUT", "Economics", "rates"),
    ("KXINX15M", "", "stock index"), ("KXNDQ15M", "", "stock index"),
    ("KXBTC15M", "Crypto", "crypto"), ("KXHYPE15M", "Crypto", "crypto"),
    ("KXBTC15M", "", "other"), ("KXSOMETHING", "Weather", "weather"),
])
def test_group_of(ticker, category, group):
    assert bot.group_of(ticker, category) == group
    assert bot.group_of(ticker.lower(), category) == group  # case doesn't matter


def test_the_strategy_only_trades_crypto_metals_and_energy():
    assert bot.EDGE_GROUPS == ("crypto", "metals", "energy")
    for t in ("KXCRYPTOLEAD15M", "KXEURUSD15M", "KXINX15M"):
        assert bot.group_of(t, "Crypto") not in bot.EDGE_GROUPS


# ------------------------------------------------------------------ fees and sizing
@pytest.mark.parametrize("contracts, price, mult, fee", [
    (1, 0.50, 1.0, 0.02),      # 1.75c rounds up to 2c
    (3, 0.96, 1.0, 0.01),      # 0.81c rounds up to 1c
    (1, 0.99, 1.0, 0.01),      # 0.07c still costs a cent
    (10, 0.90, 1.0, 0.07),
    (100, 0.50, 1.0, 1.75),    # exactly 175c: float noise mustn't add a cent
    (2, 0.50, 2.0, 0.07),      # 7.000000000000001c mustn't become 8c
    (10, 0.90, 0.5, 0.04),     # a half-fee series
    (0, 0.50, 1.0, 0.0),
    (5, 1.00, 1.0, 0.0),       # nothing to lose at $1
])
def test_taker_fee_rounds_up_to_the_cent(contracts, price, mult, fee):
    assert bot.taker_fee(contracts, price, mult) == pytest.approx(fee)


def test_taker_fee_peaks_at_50c_and_is_never_negative():
    fees = [bot.taker_fee(10, p / 100) for p in range(0, 101)]
    assert max(fees) == fees[50] and min(fees) == 0.0


@pytest.mark.parametrize("bankroll, n, stake", [
    (100, 1, 1.50), (100, 0, 1.50), (100, 6, 1.50), (100, 7, 1.42), (100, 10, 1.00), (100, 20, 0.50),
    (1000, 1, 15.00), (10000, 5, 150.00), (10, 1, 0.15), (0, 1, 0.0),   # no $ cap since Oct 10
    (66.66, 1, 0.99), (66.67, 1, 1.00),                                  # where 1.5% reaches the $1 minimum
])
def test_stake_for(bankroll, n, stake):
    assert bot.stake_for(bankroll, n) == stake


def test_stake_for_never_breaks_its_own_limits():
    rng = random.Random(7)
    for _ in range(2000):
        bankroll, n = rng.uniform(1, 5000), rng.randint(1, 40)
        s = bot.stake_for(bankroll, n)
        assert 0 <= s
        assert s <= bankroll * bot.CAP_PCT + 1e-9            # 1.5% a bet ...
        assert s * n <= bankroll * bot.WINDOW_CAP + 1e-9     # ... and 10% a window
        assert round(s * 100, 6) == round(s * 100)           # whole cents


# ------------------------------------------------------------------ the database
def test_connect_creates_the_folder_the_tables_and_is_reusable(tmp_path):
    path = str(tmp_path / "a" / "b" / "x.db")
    db = bot.connect(path)
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"bets", "decisions", "orders", "meta"} <= tables
    bot.set_meta(db, "k", "v")
    db.commit()
    assert bot.connect(path).execute("SELECT value FROM meta WHERE key='k'").fetchone()[0] == "v"  # opening again keeps the data
    assert db.execute("SELECT 1").fetchone().keys() == ["1"]  # rows are addressable by name


def test_one_bet_and_one_decision_per_market(env):
    row = ("T-1", "S", 0, 900, "yes", 0.9, 1, 0.9, 0.01, 1, "open")
    q = "INSERT INTO bets (ticker, series, window_open, close_ts, side, price, contracts, cost, fee, placed_ts, status) VALUES (?,?,?,?,?,?,?,?,?,?,?)"
    env.execute(q, row)
    with pytest.raises(sqlite3.IntegrityError):
        env.execute(q, row)
    env.execute("INSERT INTO decisions (ts, ticker, action, reason) VALUES (1, 'T-1', 'bet', 'first')")
    env.execute("INSERT OR IGNORE INTO decisions (ts, ticker, action, reason) VALUES (2, 'T-1', 'skip', 'second')")
    assert env.execute("SELECT reason FROM decisions").fetchall()[0][0] == "first"


def test_meta_values_are_stored_as_text_and_replaced(env):
    assert bot.get_meta(env, "nothing") is None and bot.get_meta(env, "nothing", "dflt") == "dflt"
    bot.set_meta(env, "n", 5)
    bot.set_meta(env, "n", 6.5)
    assert bot.get_meta(env, "n") == "6.5"


def test_set_start_forgets_the_old_halt_reference(env):
    bot.set_meta(env, "halt_base", 60)
    bot.set_start(env, 250.0)
    assert bot.get_meta(env, "start") == "250.0" and bot.get_meta(env, "halt_base") is None


def test_bankroll_is_start_plus_settled_results_only(env):
    assert bot.bankroll(env) == 100.0
    fake_bet(env, 0, W, True, 0.5, settled=W + 1000)
    fake_bet(env, 1, W, False, -3.0, settled=W + 2000)
    fake_bet(env, 2, W, None, None, status="open")                  # open: counts for nothing yet
    assert bot.bankroll(env) == pytest.approx(97.5)
    assert bot.bankroll(env, at=W + 1500) == pytest.approx(100.5)   # as it stood between the two
    assert bot.bankroll(env, at=W + 1000) == pytest.approx(100.5)   # a bet settled at that instant is in
    assert bot.bankroll(env, at=W) == 100.0


def test_cash_is_the_bankroll_less_whats_riding_on_open_bets(env):
    fake_bet(env, 0, W, False, -3.0, settled=W + 1000)
    fake_bet(env, 1, W, None, None, status="open")                  # 2.85 cost + 0.01 fee
    fake_bet(env, 2, W, None, None, status="open")
    assert bot.cash(env) == pytest.approx(97.0 - 2 * 2.86)


# ------------------------------------------------------------------ the halt file
def test_no_halt_file_means_not_halted(env):
    assert bot.halt_info() is None and not os.path.exists(bot.halt_path())


def test_set_halt_writes_who_when_and_why_and_prints_it(env, capsys):
    bot.set_halt(W, "something odd", "you")
    assert bot.halt_info() == {"ts": "2026-09-28T16:00:00Z", "reason": "something odd", "by": "you"}
    out = capsys.readouterr().out
    assert "HALTED (you): something odd" in out and "python bot.py --resume" in out
    assert json.load(open(bot.halt_path(), encoding="utf-8"))["by"] == "you"


def test_set_halt_defaults_to_automatic_and_never_overwrites(env, capsys):
    bot.set_halt(W, "first")
    capsys.readouterr()
    bot.set_halt(W + 60, "second", "you")
    assert bot.halt_info()["reason"] == "first" and bot.halt_info()["by"] == "auto"
    assert capsys.readouterr().out == ""  # and says nothing


def test_set_halt_creates_the_state_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(bot, "STATE", str(tmp_path / "not" / "yet"))
    bot.set_halt(W, "x")
    assert bot.halt_info()["reason"] == "x"


def test_clear_halt_returns_what_it_cleared_and_re_arms_every_account(env, tmp_path):
    other = bot.connect(str(tmp_path / "other.db"))
    bot.set_start(other, 50.0)
    fake_bet(env, 0, W, False, -30.0, settled=W + 100)   # this account is at $70
    bot.set_halt(W, "why")
    was = bot.clear_halt(W + 500, [env, other])
    assert was["reason"] == "why" and bot.halt_info() is None
    assert float(bot.get_meta(env, "halt_seen")) == W + 500 and float(bot.get_meta(other, "halt_seen")) == W + 500
    assert float(bot.get_meta(env, "halt_base")) == 70.0     # half of what it's worth now, not of the start
    assert float(bot.get_meta(other, "halt_base")) == 50.0   # never above its start


def test_clear_halt_when_not_halted_still_re_arms_and_returns_none(env):
    assert bot.clear_halt(W, [env]) is None
    assert float(bot.get_meta(env, "halt_seen")) == W


# ------------------------------------------------------------------ blackouts and maintenance
@pytest.mark.parametrize("window, what", [
    ("2026-10-28T17:45:00Z", None),             # ends the second the blackout starts
    ("2026-10-28T18:00:00Z", "Fed decision"),   # first window inside
    ("2026-10-28T19:15:00Z", "Fed decision"),   # last window inside
    ("2026-10-28T19:30:00Z", None),             # starts the second it ends
    ("2026-10-28T18:30:00Z", "Fed decision"),
    ("2026-12-09T19:00:00Z", "Fed decision"),   # December is EST: 2 pm is 19:00 UTC
    ("2026-12-09T18:45:00Z", None),
    ("2026-09-28T16:00:00Z", None),
])
def test_blackout_windows(window, what):
    assert bot.blackout(bot.ts(window)) == what


def test_a_window_that_merely_overlaps_a_blackout_is_skipped(monkeypatch):
    monkeypatch.setattr(bot, "BLACKOUTS", [("2026-10-28T18:05:00Z", "2026-10-28T18:10:00Z", "brief")])
    assert bot.blackout(bot.ts("2026-10-28T18:00:00Z")) == "brief"


@pytest.mark.parametrize("utc, paused", [
    ("2026-10-01T06:59:59Z", False),   # Thu 2:59:59 am EDT
    ("2026-10-01T07:00:00Z", True),    # Thu 3:00 am EDT
    ("2026-10-01T08:00:00Z", True),
    ("2026-10-01T08:59:59Z", True),    # Thu 4:59:59 am EDT
    ("2026-10-01T09:00:00Z", False),   # Thu 5:00 am EDT
    ("2026-10-02T08:00:00Z", False),   # Friday 4 am
    ("2026-09-30T08:00:00Z", False),   # Wednesday 4 am
    ("2026-11-05T07:59:59Z", False),   # Thu 2:59:59 am EST: the clocks went back on Nov 1
    ("2026-11-05T08:00:00Z", True),    # Thu 3:00 am EST
])
def test_scheduled_maintenance_follows_new_york_time(utc, paused):
    assert bot.scheduled_maintenance(bot.ts(utc)) is paused


# ------------------------------------------------------------------ exchange status
CRYPTO = {"exchange_index": 2, "description": "Crypto & Commodities", "exchange_active": True, "trading_active": True}
DEFAULT = {"exchange_index": 0, "description": "Default", "exchange_active": True, "trading_active": True}


def status(*sections, **top):
    return {"exchange_active": True, "trading_active": True, "exchange_index_statuses": list(sections), **top}


@pytest.mark.parametrize("s, on", [
    (None, None), ({}, None),
    ({"exchange_active": True, "trading_active": True}, True),
    (status(CRYPTO, DEFAULT), True),
    (status(exchange_active=False), False),
    (status(trading_active=False), False),
    (status(dict(CRYPTO, trading_active=False)), False),
    (status(dict(CRYPTO, exchange_active=False)), False),
    (status(dict(DEFAULT, trading_active=False), CRYPTO), True),   # another section being down doesn't matter
    (status(dict(CRYPTO, description="CRYPTO markets", trading_active=False)), False),
    (status({"exchange_index": 9, "trading_active": False}), True),  # no description: can't be ours
    ({"exchange_active": True, "trading_active": True, "exchange_index_statuses": None}, True),
])
def test_trading_on(s, on):
    assert bot.trading_on(s) is on


def test_crypto_section_comes_from_the_status_and_defaults_to_2():
    assert bot.crypto_section(status(DEFAULT, dict(CRYPTO, exchange_index=7))) == 7
    assert bot.crypto_section(status(DEFAULT)) == 2
    assert bot.crypto_section(None) == 2 and bot.crypto_section({}) == 2


def test_a_crypto_entry_without_an_index_is_passed_over_not_a_crash():
    """Found by test_fuzz.py's schema review: a live run reads the status every minute, so a KeyError here would end it."""
    no_index = {k: v for k, v in CRYPTO.items() if k != "exchange_index"}
    assert bot.crypto_section(status(DEFAULT, no_index)) == 2
    assert bot.crypto_section(status(DEFAULT, dict(no_index, exchange_index=None))) == 2
    assert bot.crypto_section(status(no_index, dict(CRYPTO, exchange_index=5))) == 5   # a later entry that has one wins


@pytest.mark.parametrize("balance, section, cash", [
    (None, 2, None), ({}, 2, None), ({"no_balance": 1}, 2, None),
    ({"balance": 10000, "balance_breakdown": [{"exchange_index": 0, "balance": "1.5000"}, {"exchange_index": 2, "balance": "98.5000"}]}, 2, 98.5),
    ({"balance": 10000, "balance_breakdown": [{"exchange_index": 0, "balance": "100.0000"}]}, 2, 0.0),   # nothing in our section
    ({"balance": 5000}, 2, 50.0),                                    # no breakdown: the total
    ({"balance": 5000, "balance_breakdown": []}, 2, 50.0),
    ({"balance": 0}, 2, 0.0),
])
def test_usable_cash(balance, section, cash):
    assert bot.usable_cash(balance, section) == cash


# ------------------------------------------------------------------ order books
def test_parse_book_sorts_best_first_and_reads_strings():
    b = bot.parse_book({"orderbook_fp": {"yes_dollars": [["0.10", "5"], ["0.30", "2"], ["0.20", "1"]], "no_dollars": [["0.66", "9"]]}})
    assert b == {"yes": [(0.30, 2.0), (0.20, 1.0), (0.10, 5.0)], "no": [(0.66, 9.0)]}


@pytest.mark.parametrize("raw", [None, {}, {"orderbook": {}}, {"orderbook_fp": None}])
def test_parse_book_without_a_book_is_none(raw):
    assert bot.parse_book(raw) is None


def test_parse_book_tolerates_empty_or_missing_sides():
    assert bot.parse_book({"orderbook_fp": {}}) == {"yes": [], "no": []}
    assert bot.parse_book({"orderbook_fp": {"yes_dollars": None, "no_dollars": [["0.5", "1"]]}}) == {"yes": [], "no": [(0.5, 1.0)]}


@pytest.mark.parametrize("book", [None, {"yes": [], "no": []}, {"yes": [(0.9, 1.0)], "no": []}, {"yes": [], "no": [(0.1, 1.0)]}])
def test_top_of_book_with_a_side_missing_has_no_quotes(book):
    assert bot.top_of_book(book) == (None, None, 0.0, 0.0)


def test_top_of_book_uses_the_best_price_and_its_size():
    book = {"yes": [(0.95, 100.0), (0.90, 500.0)], "no": [(0.04, 50.0), (0.03, 999.0)]}
    assert bot.top_of_book(book) == (0.95, 0.96, 50.0, 100.0)  # the YES ask is the best NO bid seen from the other side


@pytest.mark.parametrize("yes_bid, yes_ask, want", [
    (None, None, (None, None)), (0.9, None, (None, None)), (None, 0.9, (None, None)),
    (0.95, 0.96, ("yes", 0.96)),           # YES is dearer: buy it at the ask
    (0.02, 0.03, ("no", 0.98)),            # NO is dearer: buy it at 1 - the YES bid
    (0.50, 0.50, (None, None)),            # a dead heat has no favourite
    (0.94, 0.96, ("yes", 0.96)),
    (0.10, 0.12, ("no", 0.90)),
    (0.49, 0.52, ("yes", 0.52)),
])
def test_favourite(yes_bid, yes_ask, want):
    assert bot.favourite(yes_bid, yes_ask) == want


# ------------------------------------------------------------------ orders
def test_client_order_id_is_a_stable_uuid_per_market():
    a = bot.client_order_id("KXBTC15M-26SEP281600-00")
    assert uuid.UUID(a).version == 5
    assert a == bot.client_order_id("KXBTC15M-26SEP281600-00")
    assert a != bot.client_order_id("KXBTC15M-26SEP281600-15")


def test_client_order_id_never_depends_on_the_clock_or_the_run(monkeypatch):
    """It is what stops a restart from ordering a market twice, so it must come out the same in every process
    and at every moment: pinned here, and checked against a clock that moves on every read."""
    assert bot.client_order_id("KXBTC15M-26SEP291815") == "f73e84ed-f548-5d20-b5b2-116971b253cb"
    assert bot.client_order_id("KXGOLD15M-A") == "babe0796-8ee0-5ba2-8933-e116190961a1"
    ticks = iter(range(10_000))
    monkeypatch.setattr(bot, "time", types.SimpleNamespace(time=lambda: next(ticks)))
    assert len({bot.client_order_id("KXBTC15M-26SEP291815") for _ in range(5)}) == 1


def test_order_body_for_yes_and_no():
    yes = bot.order_body("KXBTC15M-A", "yes", 0.96, 3.0)
    assert yes == {"ticker": "KXBTC15M-A", "client_order_id": bot.client_order_id("KXBTC15M-A"), "side": "bid", "count": "3",
                   "price": "0.9600", "time_in_force": "immediate_or_cancel", "self_trade_prevention_type": "taker_at_cross",
                   "cancel_order_on_pause": True}
    no = bot.order_body("KXGOLD15M-A", "no", 0.987, 1)
    assert (no["side"], no["price"], no["count"]) == ("ask", "0.0130", "1")


@pytest.mark.parametrize("side, price", [("yes", 0.90), ("yes", 0.999), ("no", 0.90), ("no", 0.999), ("no", 0.9)])
def test_every_order_is_immediate_or_cancel_and_priced_inside_the_book(side, price):
    body = bot.order_body("T", side, price, 2)
    assert body["time_in_force"] == "immediate_or_cancel" and 0 < float(body["price"]) < 1
    # what the order can cost per contract is the price it's given (the bot gives it the limit), never more
    cost = float(body["price"]) if side == "yes" else 1 - float(body["price"])
    assert cost == pytest.approx(price)
