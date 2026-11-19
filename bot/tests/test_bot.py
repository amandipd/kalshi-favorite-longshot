"""Tests against a fake Kalshi: nothing here touches the network or an account.

    python -m pytest tests/test_bot.py -q
"""
import base64

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ed25519, padding, rsa

from kalshi_bot import bot
from kalshi_bot.kalshi import Kalshi

W = bot.ts("2026-09-28T16:00:00Z")  # a window opening at noon ET
ENTRY = W + bot.MINUTE * 60 + 5


def iso(t):
    return bot.iso(t)


class FakeKalshi:
    """Two markets the strategy trades (BTC: YES favourite at 96c; GOLD: NO favourite at 98c), one it skips
    (ETH at 61c), and a Coin Race market it never looks at."""
    authed = True

    def __init__(self, order_status=201, fill_lag=False, fill_price_bump=0.0):
        self.orders, self.order_status, self.fill_lag, self.bump = [], order_status, fill_lag, fill_price_bump
        self.results = {}
        # Minute-by-minute prices, {ticker: {minute: (yes_bid, yes_ask)}}. A market not in here gets candles with no
        # quotes in them, so no warning sign can fire: the tests that aren't about the warning signs never trip one.
        self.history, self.candle_calls = {}, []
        self.resting, self.cancels = [], []   # orders the account has resting on the book; cancels sent
        self.order_record = []   # Kalshi's own record of the account's orders (GET /portfolio/orders), whatever the bot was told
        self.window, self.suffix = W, "A"  # the window being listed, and its markets' ticker suffix
        self.books = {  # by series
            "KXBTC15M": {"yes_dollars": [["0.95", "100"]], "no_dollars": [["0.04", "50"]]},
            "KXGOLD15M": {"yes_dollars": [["0.02", "80"]], "no_dollars": [["0.97", "40"]]},
            "KXETH15M": {"yes_dollars": [["0.60", "10"]], "no_dollars": [["0.38", "10"]]},
        }

    def series(self):
        return {"series": [{"ticker": t, "frequency": "fifteen_min", "category": c, "fee_multiplier": 1}
                           for t, c in (("KXBTC15M", "Crypto"), ("KXGOLD15M", "Commodities"), ("KXETH15M", "Crypto"),
                                        ("KXCRYPTOLEAD15M", "Crypto"))]}

    def markets(self, **p):
        if "series_ticker" in p:
            s = p["series_ticker"]
            return {"markets": [{"ticker": f"{s}-{self.suffix}", "open_time": iso(self.window),
                                 "close_time": iso(self.window + 900)}] if s in self.books else []}
        return {"markets": [{"ticker": t, "result": r, "settlement_ts": iso(W + 908)} for t, r in self.results.items()]}

    def orderbook(self, ticker):
        return {"orderbook_fp": self.books[ticker.split("-")[0]]}

    def candlesticks(self, tickers, start_ts, end_ts):
        self.candle_calls.append((tuple(tickers), start_ts, end_ts))
        dollars = lambda v: {} if v is None else {"close_dollars": f"{v:.4f}"}
        return {"markets": [{"market_ticker": t, "candlesticks": [
            {"end_period_ts": start_ts + k * 60, "yes_bid": dollars(self.history.get(t, {}).get(k, (None, None))[0]),
             "yes_ask": dollars(self.history.get(t, {}).get(k, (None, None))[1])}
            for k in range(1, int((end_ts - start_ts) // 60) + 1)]} for t in tickers]}

    def list_orders(self, **p):
        return {"orders": list(self.resting)}

    def order_history(self, min_ts, cursor=None):
        return {"orders": list(self.order_record), "cursor": ""}

    def cancel_order(self, order_id, ticker):
        self.cancels.append((order_id, ticker))
        self.resting = [o for o in self.resting if o["order_id"] != order_id]
        return 200, {"order_id": order_id, "reduced_by": "1.00"}

    crypto_cash = "100.0000"  # the Crypto & Commodities section; the Default section holds nothing

    def exchange_status(self):
        return {"exchange_active": True, "trading_active": True, "exchange_index_statuses": [
            {"exchange_index": 0, "description": "Default", "exchange_active": True, "trading_active": True},
            {"exchange_index": 2, "description": "Crypto & Commodities", "exchange_active": True, "trading_active": True}]}

    def balance(self):
        crypto = float(self.crypto_cash)
        return {"balance": 10000, "balance_breakdown": [{"exchange_index": 0, "balance": f"{100 - crypto:.4f}"},
                                                        {"exchange_index": 2, "balance": self.crypto_cash}]}

    def positions(self, **p):
        return {"market_positions": []}

    def create_order(self, body):
        self.orders.append(body)
        if self.order_status != 201:
            return self.order_status, {"error": {"code": "invalid_order"}}
        return 201, {"order_id": f"o{len(self.orders)}", "fill_count": body["count"] + ".00", "remaining_count": "0.00"}

    def fills(self, order_id=None, ticker=None, limit=100):
        if self.fill_lag:
            return {"fills": []}
        body = self.orders[int(order_id[1:]) - 1]
        yes = float(body["price"]) + (self.bump if body["side"] == "bid" else -self.bump)
        side = "yes" if body["side"] == "bid" else "no"
        return {"fills": [{"outcome_side": side, "count_fp": body["count"] + ".00", "yes_price_dollars": f"{yes:.4f}",
                           "no_price_dollars": f"{1 - yes:.4f}", "fee_cost": "0.0100"}]}


# A $200 ledger: 1.5% of it (CAP_PCT) is the $3 stake, 3 contracts at 96c, that the order tests (test_flow.py,
# test_shadow.py, test_limit_up.py and the like) were written around when the bot bet 3% of $100. Those files give their
# `env` this start; the tests about the halt lines and the bankroll keep the $100 one.
THREE_DOLLAR_START = 200.0


def start_ledger(tmp_path, monkeypatch, start=100.0):
    """A throwaway ledger from `start`, with the state folder (and its halt file) pointed beside it."""
    monkeypatch.setattr(bot, "STATE", str(tmp_path))
    bot._since.clear()
    db = bot.connect(str(tmp_path / "test.db"))
    bot.set_meta(db, "start", start)
    db.commit()
    return db


@pytest.fixture
def env(tmp_path, monkeypatch):
    return start_ledger(tmp_path, monkeypatch)


def run(db, fake, live, now=ENTRY):
    b = bot.Bot(fake, db, live)
    b.step(now)
    return b


def decisions(db):
    return {r["ticker"]: (r["action"], r["reason"]) for r in db.execute("SELECT * FROM decisions")}


# ------------------------------------------------------------------ signing
def test_rsa_signature_matches_kalshis_scheme():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    k = Kalshi("demo")
    k.key_id, k.key = "key-id", key
    h = k.headers("GET", "/portfolio/balance", now_ms=1790000000000)
    assert h["KALSHI-ACCESS-KEY"] == "key-id" and h["KALSHI-ACCESS-TIMESTAMP"] == "1790000000000"
    # timestamp + method + path with the /trade-api/v2 prefix, no query string
    key.public_key().verify(base64.b64decode(h["KALSHI-ACCESS-SIGNATURE"]), b"1790000000000GET/trade-api/v2/portfolio/balance",
                            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH), hashes.SHA256())


def test_ed25519_signature():
    key = ed25519.Ed25519PrivateKey.generate()
    k = Kalshi("prod")
    k.key_id, k.key = "key-id", key
    h = k.headers("POST", "/portfolio/events/orders", now_ms=1)
    key.public_key().verify(base64.b64decode(h["KALSHI-ACCESS-SIGNATURE"]), b"1POST/trade-api/v2/portfolio/events/orders")


# ------------------------------------------------------------------ pricing and sizing
def test_orders_are_ioc_whole_contracts_priced_from_the_yes_side():
    yes = bot.order_body("KXBTC15M-A", "yes", 0.96, 3)
    assert (yes["side"], yes["price"], yes["count"], yes["time_in_force"]) == ("bid", "0.9600", "3", "immediate_or_cancel")
    no = bot.order_body("KXGOLD15M-A", "no", 0.98, 3)
    assert (no["side"], no["price"]) == ("ask", "0.0200")  # buying NO at 98c = selling YES at 2c
    assert bot.client_order_id("X") == bot.client_order_id("X") != bot.client_order_id("Y")


def test_sizing_1_5pct_10pct_window_and_no_dollar_cap():
    assert (bot.CAP_PCT, bot.WINDOW_CAP) == (0.015, 0.10)   # halved from 3% and 20% on Oct 15
    assert bot.stake_for(100, 1) == 1.50
    assert bot.stake_for(100, 10) == 1.00  # 10% of $100 over 10 bets
    assert bot.stake_for(1000, 1) == 15.00  # 1.5% of $1,000: no $10 cap since Oct 10
    assert bot.stake_for(1000, 7) == 14.28  # 10% of $1,000 over 7 bets: the window cap binds from the 7th
    assert not hasattr(bot, "MAX_ORDER_DOLLARS")


def test_favourite_from_the_book():
    yb, ya, yes_size, no_size = bot.top_of_book(bot.parse_book({"orderbook_fp": {"yes_dollars": [["0.95", "100"]], "no_dollars": [["0.04", "50"]]}}))
    assert (yb, ya, yes_size, no_size) == (0.95, 0.96, 50.0, 100.0)
    assert bot.favourite(yb, ya) == ("yes", 0.96)
    assert bot.favourite(0.02, 0.03) == ("no", 0.98)


# ------------------------------------------------------------------ dry run and live
def test_dry_run_never_sends_an_order(env):
    fake = FakeKalshi()
    run(env, fake, live=False)
    d = decisions(env)
    assert fake.orders == []
    assert d["KXBTC15M-A"][0] == "bet" and d["KXGOLD15M-A"][0] == "bet"
    assert d["KXETH15M-A"][0] == "skip" and "KXCRYPTOLEAD15M-A" not in d
    bets = {b["ticker"]: b for b in env.execute("SELECT * FROM bets")}
    # $1.50 a bet (1.5% of $100) buys 1 contract at 96c or 98c
    assert bets["KXBTC15M-A"]["contracts"] == 1 and bets["KXBTC15M-A"]["side"] == "yes"
    assert bets["KXGOLD15M-A"]["contracts"] == 1 and bets["KXGOLD15M-A"]["side"] == "no"


def test_live_sends_ioc_orders_and_records_fills(env):
    fake = FakeKalshi()
    run(env, fake, live=True)
    assert [o["time_in_force"] for o in fake.orders] == ["immediate_or_cancel"] * 2
    bets = {b["ticker"]: b for b in env.execute("SELECT * FROM bets")}
    # The fake fills each order at its own price: the limit, 1c over the 96c and 98c it saw (LIMIT_UP; test_limit_up.py)
    assert bets["KXBTC15M-A"]["price"] == pytest.approx(0.97) and bets["KXBTC15M-A"]["fee"] == 0.01
    assert bets["KXGOLD15M-A"]["price"] == pytest.approx(0.99)
    assert env.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 2


def test_cash_outside_the_crypto_section_isnt_spent(env):
    fake = FakeKalshi()
    fake.crypto_cash = "0.0039"  # $100 in the account, all of it in the Default section
    run(env, fake, live=True)
    assert fake.orders == []
    assert "Crypto & Commodities section" in decisions(env)["KXBTC15M-A"][1]
    assert bot.usable_cash(fake.balance(), 2) == 0.0039
    assert bot.usable_cash({"balance": 5000}, 2) == 50.0  # no breakdown: the total


def test_transfer_to_the_crypto_section(monkeypatch):
    sent = {}
    k = Kalshi("prod")
    monkeypatch.setattr(k, "post", lambda path, body: sent.update(path=path, body=body) or (200, {"transfer_id": "t1"}))
    assert k.transfer(100.0, 0, 2) == (200, {"transfer_id": "t1"})
    assert sent["path"] == "/portfolio/intra_exchange_instance_transfer"
    assert sent["body"] == {"source": "event_contract", "destination": "event_contract", "amount": 1000000,
                            "source_exchange_shard": 0, "destination_exchange_shard": 2}
    assert bot.crypto_section(FakeKalshi().exchange_status()) == 2


def test_no_second_order_for_the_same_market(env):
    fake = FakeKalshi()
    run(env, fake, live=True)
    run(env, fake, live=True, now=ENTRY + 10)  # a restart inside the same entry minute
    assert len(fake.orders) == 2


def test_fills_that_lag_still_count(env):
    bot.set_start(env, THREE_DOLLAR_START)   # $3 a bet: 3 contracts each, so a count of 1 a bet can't pass
    env.commit()
    fake = FakeKalshi(fill_lag=True)
    run(env, fake, live=True)
    assert env.execute("SELECT SUM(contracts) FROM bets").fetchone()[0] == 6  # from the orders' own fill counts


def test_settles_from_market_results(env):
    fake = FakeKalshi()
    b = run(env, fake, live=False)
    fake.results = {"KXBTC15M-A": "yes", "KXGOLD15M-A": "yes"}  # BTC's YES wins, GOLD's NO loses
    b.settle(W + 920)
    bets = {r["ticker"]: r for r in env.execute("SELECT * FROM bets")}
    # 1 contract each ($1.50 a bet): BTC's pays $1 on 96c, GOLD's 98c is lost; 1c fee each
    assert bets["KXBTC15M-A"]["status"] == "won" and bets["KXBTC15M-A"]["pnl"] == pytest.approx(1 - 0.96 - 0.01)
    assert bets["KXGOLD15M-A"]["status"] == "lost" and bets["KXGOLD15M-A"]["pnl"] == pytest.approx(-0.98 - 0.01)


# ------------------------------------------------------------------ halts
def test_halt_stops_orders_and_logs_what_it_would_have_done(env):
    bot.set_halt(ENTRY - 60, "testing", "you")
    fake = FakeKalshi()
    run(env, fake, live=True)
    assert fake.orders == []
    assert decisions(env)["KXBTC15M-A"][0] == "halted"


def test_failed_orders_halt(env):
    fake = FakeKalshi(order_status=400)
    b = bot.Bot(fake, env, True)
    b.load_catalog()
    ms = [{"ticker": t, "series": t.split("-")[0], "open": W, "close": W + 900, "book": bot.parse_book(fake.orderbook(t))}
          for t in ("KXBTC15M-A", "KXBTC15M-0", "KXBTC15M-1", "KXGOLD15M-A")]
    b.trading = True
    b.decide_window(ENTRY, W, ms)
    assert len(fake.orders) == bot.MAX_ORDER_ERRORS  # the halt stopped the fourth
    assert "orders failed in a row" in bot.halt_info()["reason"]


def test_fill_worse_than_the_limit_halts(env):
    fake = FakeKalshi(fill_price_bump=0.01)
    run(env, fake, live=True)
    assert "unexpected fill" in bot.halt_info()["reason"]


def test_fed_blackout_skips_the_window(env):
    w = bot.ts("2026-10-28T18:15:00Z")
    fake = FakeKalshi()
    b = bot.Bot(fake, env, False)
    b.load_catalog()
    ms = [{"ticker": "KXBTC15M-A", "series": "KXBTC15M", "open": w, "close": w + 900, "book": bot.parse_book(fake.orderbook("KXBTC15M-A"))}]
    b.decide_window(w + 485, w, ms)
    assert decisions(env)["KXBTC15M-A"] == ("skip", "Fed decision blackout")


def fake_bet(db, i, window, won, pnl, settled=None, status=None, close=None):
    db.execute("INSERT INTO bets (ticker, series, window_open, close_ts, side, price, contracts, cost, fee, placed_ts, status, result, payout, pnl, settled_ts)"
               " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (f"T-{i}", "KXBTC15M", window, close or window + 900, "yes", 0.95, 3, 2.85, 0.01, window + 480,
                status or ("won" if won else "lost"), None if status == "open" else ("yes" if won else "no"),
                None if status == "open" else (3.0 if won else 0.0), None if status == "open" else pnl, None if status == "open" else settled))


def test_tripwires(env):
    now = W + 3000
    bot.check_halts(env, now, True)
    assert bot.halt_info() is None
    for i in range(8):
        fake_bet(env, i, W, False, -0.01, settled=now - 60)
    bot.check_halts(env, now, True)
    assert "8 bets lost in one window" in bot.halt_info()["reason"]


def test_half_the_start_and_resume_rearms(env):
    now = W + 3000
    fake_bet(env, 0, W, False, -55.0, settled=now - 60)
    bot.check_halts(env, now, True)
    assert "half of $100.00" in bot.halt_info()["reason"]
    bot.clear_halt(now, [env])
    bot.check_halts(env, now + 5, True)
    assert bot.halt_info() is None  # the floor is now half of $45


def test_day_drop(env):
    now = W + 3000
    fake_bet(env, 0, W, False, -36.0, settled=now - 60)
    bot.check_halts(env, now, True)
    assert "within 24 hours" in bot.halt_info()["reason"]


def test_late_settlement_and_unscheduled_pause_must_last_five_minutes(env):
    now = W + 5000
    fake_bet(env, 0, now - 4000, None, None, status="open", close=now - 2000)
    bot.check_halts(env, now, True)
    assert bot.halt_info() is None
    bot.check_halts(env, now + 301, True)
    assert "unsettled" in bot.halt_info()["reason"]


def test_kalshi_pause(env, monkeypatch):
    monkeypatch.setattr(bot, "scheduled_maintenance", lambda t: True)
    bot.check_halts(env, W, False)
    bot.check_halts(env, W + 400, False)
    assert bot.halt_info() is None  # Thursday 3-5 am ET maintenance
    monkeypatch.setattr(bot, "scheduled_maintenance", lambda t: False)
    bot._since.clear()
    bot.check_halts(env, W, False)
    bot.check_halts(env, W + 301, False)
    assert "paused trading" in bot.halt_info()["reason"]


def test_your_halt_command_blocks_live_orders_until_resume(env):
    fake = FakeKalshi()
    bot.main(["--halt", "checking the kill switch"])
    run(env, fake, live=True)
    assert fake.orders == [] and decisions(env)["KXBTC15M-A"][0] == "halted"
    bot.main(["--resume"])
    fake.window, fake.suffix = W + 900, "B"  # the next window
    run(env, fake, live=True, now=ENTRY + 900)
    assert len(fake.orders) == 2


def test_halts_are_checked_every_loop_not_only_at_entry(env):
    fake_bet(env, 0, W - 900, False, -55.0, settled=W - 5)
    run(env, FakeKalshi(), live=True, now=W + 100)  # minute 2: no betting, still checked
    assert "half of $100.00" in bot.halt_info()["reason"]


def test_a_new_start_resets_the_halt_reference(env):
    bot.set_start(env, 20.0)
    bot.clear_halt(W, [env])  # a resume while the start was $20 puts the floor at half of $20
    bot.set_start(env, 100.0)  # the deposit clears before the first bet: the floor must move with it
    fake_bet(env, 0, W, False, -52.0, settled=W + 1000)
    bot.check_halts(env, W + 1100, True)
    assert "half of $100.00" in bot.halt_info()["reason"]


def test_trading_status_and_maintenance_hours():
    assert bot.trading_on({"exchange_active": True, "trading_active": True}) is True
    assert bot.trading_on({"exchange_active": True, "trading_active": True, "exchange_index_statuses": [
        {"description": "Crypto & Commodities", "exchange_active": True, "trading_active": False}]}) is False
    assert bot.trading_on(None) is None
    assert bot.scheduled_maintenance(bot.ts("2026-10-01T08:00:00Z"))  # Thursday 4:00 am EDT
    assert not bot.scheduled_maintenance(bot.ts("2026-10-01T10:00:00Z"))
