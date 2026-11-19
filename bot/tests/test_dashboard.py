"""The dashboard's numbers, from a made-up account: nothing here touches the network.

    python -m pytest tests/test_dashboard.py -q
"""
import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from kalshi_bot import bot
from kalshi_bot.web import dashboard

T = bot.ts("2026-09-28T16:00:00Z")


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setattr(bot, "STATE", str(tmp_path))
    monkeypatch.setattr(dashboard, "marks", lambda env, tickers: {"KXBTC15M-OPEN": (0.97, 0.98), "KXGOLD15M-OPEN": (0.01, 0.02)})
    monkeypatch.setattr(dashboard, "account", lambda env: {"total": 100.0, "crypto": 100.0, "positions": 2})
    monkeypatch.setattr(dashboard, "history", lambda env, since: None)   # never the real account's records
    dashboard._cache.clear()
    db = bot.connect(str(tmp_path / "live-prod.db"))
    bot.set_start(db, 100.0)
    rows = [  # ticker, side, price, contracts, status, pnl, settled
        ("KXBTC15M-1", "yes", 0.96, 3, "won", 3 - 2.88 - 0.01, T + 900),
        ("KXETH15M-1", "no", 0.95, 3, "lost", -2.85 - 0.01, T + 900),
        ("KXGOLD15M-2", "yes", 0.97, 3, "won", 3 - 2.91 - 0.01, T + 1800),
        ("KXBTC15M-OPEN", "yes", 0.95, 3, "open", None, None),
        ("KXGOLD15M-OPEN", "no", 0.97, 3, "open", None, None),
    ]
    for i, (t, side, p, c, status, pnl, settled) in enumerate(rows):
        db.execute("INSERT INTO bets (ticker, series, window_open, close_ts, side, price, contracts, cost, fee, placed_ts, status, pnl, settled_ts)"
                   " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (t, t.split("-")[0], T + i, T + 900 * (i + 1), side, p, c, c * p, 0.01, T + 480 + i, status, pnl, settled))
    db.execute("INSERT INTO decisions (ts, ticker, series, action, reason) VALUES (?, 'KXETH15M-X', 'KXETH15M', 'skip', 'favorite at 61.0c is outside 90-99.9c')", (T,))
    db.commit()
    return db


def test_account_numbers(state):
    s = dashboard.state("live-prod")
    assert s["bankroll"] == pytest.approx(100 + 0.11 - 2.86 + 0.08)
    assert (s["wins"], s["losses"], len(s["openBets"])) == (2, 1, 2)
    # open bets at what they'd sell for now: YES at the bid (97c), NO at 1 - the YES ask (98c)
    btc, gold = sorted(s["openBets"], key=lambda b: b["ticker"])
    assert btc["mark"] == 0.97 and btc["unrealized"] == pytest.approx(3 * 0.97 - 2.85 - 0.01)
    assert gold["mark"] == 0.98 and gold["unrealized"] == pytest.approx(3 * 0.98 - 2.91 - 0.01)
    assert [round(v, 2) for _, v in s["curve"]] == [100.0, 100.11, 97.25, 97.33]
    assert s["maxDrop"] == pytest.approx(1 - 97.25 / 100.11)
    assert s["kalshi"]["crypto"] == 100.0 and s["decisions"][0]["action"] == "skip"


def test_the_page_can_halt_but_not_resume(state):
    server = ThreadingHTTPServer(("127.0.0.1", 0), dashboard.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        assert json.load(urllib.request.urlopen(base + "/api/state"))["mode"] == "live-prod"
        assert json.load(urllib.request.urlopen(base + "/api/state?mode=../../etc"))["mode"] == "live-prod"  # only real modes
        assert b"Favorites Bot" in urllib.request.urlopen(base + "/").read()
        urllib.request.urlopen(urllib.request.Request(base + "/api/halt", method="POST"))
        assert bot.halt_info()["reason"] == "halted from the dashboard"
        with pytest.raises(urllib.error.HTTPError):  # there's no way to resume from the page
            urllib.request.urlopen(urllib.request.Request(base + "/api/resume", method="POST"))
    finally:
        server.shutdown()
