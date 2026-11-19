"""notify.py: a phone alert through ntfy when one of the bot's bets loses, when the bot halts, and when it stops or
starts again, read from the bot's own records without ever writing to them.

Each test gets its own state folder with a real bot database (bot.connect) and a stand-in for requests.post that
records what would have been sent, or fails on demand. Nothing here touches the network. The words and links are
also checked against the page's own functions, run in node (skipped without node). The loop runs on a fake clock
(the `clock` fixture swaps notify's time module for one), so a test can let minutes pass, or put the PC to sleep for an
hour, at once. Every test points the one-notifier lock at a port of its own, since the real notifier holds the default.

The notifier runs unattended for days, under pythonw.exe with no console, so most of what's here is what can go wrong
between checks: the bot mid-write (its ledger locked, or halt.json half written), ntfy down or refusing, a memory file
it can't replace (a sync app or a virus scanner holding it), a ledger started over, another account watched, the PC
asleep, a second notifier started by mistake. None of them may stop the checks, flood the phone with old news, send an
alert twice, or lose one.
    python -m pytest tests/test_notify.py -q
"""

import json
import os
import re
import runpy
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
import types
from datetime import datetime
from pathlib import Path

import pytest

from kalshi_bot import bot
from kalshi_bot.web import dashboard
from kalshi_bot import notify
from layout import BOT

NOW = 1_791_660_000            # Oct 10 2026, 3:20 pm in New York
LOCAL = datetime.fromtimestamp(NOW).strftime("%I:%M %p").lstrip("0")   # times read in this machine's zone, as the dashboard's do
CFG = {"NTFY_TOPIC": "kalshi-test-topic"}
BTC, ETH, OLD = "KXBTC15M-26OCT101315-15", "KXETH15M-26OCT101330-30", "KXBTC15M-26OCT091315-15"
FAILS = {"raise": lambda: notify.requests.ConnectionError("no network"), "timeout": lambda: notify.requests.Timeout("read timed out"),
         "error": lambda: notify.requests.RequestException("boom"), "unicode": lambda: notify.requests.ConnectionError("réseau coupé − 5¢")}


@pytest.fixture
def home(tmp_path, monkeypatch):
    """An empty state folder, and ntfy stood in for: `sent` holds each JSON payload. Set `fail` to make sends fail:
    "raise", "timeout", "error" or "unicode" (requests exceptions), "status" (HTTP 429), or a function of the payload
    giving one. The one-notifier lock binds port 0, which is always free."""
    monkeypatch.setattr(bot, "STATE", str(tmp_path))
    monkeypatch.setattr(notify, "NOTIFY_PORT", 0, raising=False)
    # Shipped, only a lost bet is pushed (ALERTS). These tests are about whether each alert is worked out
    # correctly, so they turn them all on; what ships is pinned on its own, further down.
    monkeypatch.setattr(notify, "ALERTS", ("loss", "halt", "run", "stall"))
    box = types.SimpleNamespace(dir=tmp_path, sent=[], fail=None, urls=[])

    def post(url, json=None, timeout=None):
        box.urls.append((url, timeout))
        how = box.fail(json) if callable(box.fail) else box.fail
        if how in FAILS:
            raise FAILS[how]()
        if how == "status":
            return types.SimpleNamespace(status_code=429)
        box.sent.append(json)
        return types.SimpleNamespace(status_code=200)
    monkeypatch.setattr(notify.requests, "post", post)
    return box


def ledger(home, mode="live-prod"):
    return bot.connect(str(Path(bot.STATE) / f"{mode}.db"))


def add_bet(db, ticker, status, side="no", price=0.962, contracts=16.0, settled=NOW, fee=0.0941):
    cost = contracts * price
    pnl = None if status == "open" else (contracts - cost - fee if status == "won" else -(cost + fee))
    db.execute("INSERT INTO bets (ticker, series, window_open, close_ts, side, price, contracts, cost, fee, placed_ts, status, pnl,"
               " settled_ts) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (ticker, ticker.split("-")[0], settled - 900, settled, side, price, contracts, cost, fee, settled - 420, status, pnl,
                None if status == "open" else settled))
    db.commit()
    return db.execute("SELECT max(id) FROM bets").fetchone()[0]


def check(sent, **when):
    """One check of the real-money ledger; `when` is check()'s now= and just_woke=."""
    return notify.check(CFG, "live-prod", sent, **when)


def titles(home):
    return [m["title"] for m in home.sent]


def said(home):
    """Each message sent, as ntfy got it, less the topic."""
    return [{k: v for k, v in m.items() if k != "topic"} for m in home.sent]


def beat(db, t):
    """The bot's loop going round: its heartbeat, as bot.Bot.step() writes it."""
    bot.set_meta(db, "heartbeat", t)
    db.commit()


def memory(mode="live-prod"):
    return notify.load_sent(notify.memory_path(mode))


def hold(home):
    """The bot mid-commit: its ledger locked against readers until the returned function lets go."""
    w = sqlite3.connect(str(home.dir / "live-prod.db"), isolation_level=None)
    w.execute("BEGIN EXCLUSIVE")
    return lambda: (w.execute("ROLLBACK"), w.close())


# ------------------------------------------------------------------ what it says, and where the tap goes
@pytest.mark.parametrize("ticker, url", [
    ("KXBTC15M-26OCT101315-15", "https://kalshi.com/markets/kxbtc15m/kxbtc15m/kxbtc15m-26oct101315"),
    ("KXGOLD15M-26OCT101300-00", "https://kalshi.com/markets/kxgold15m/kxgold15m/kxgold15m-26oct101300"),
    ("KXBTC15M", "https://kalshi.com/markets/kxbtc15m"),
])
def test_the_link_opens_the_same_kalshi_page_the_dashboard_links_to(ticker, url):
    assert notify.kalshi_url(ticker) == url       # as kalshiUrl() in dashboard.html


def test_markets_are_named_as_on_the_dashboard():
    assert (notify.title("KXBTC15M"), notify.title("KXGOLD15M"), notify.title("")) == ("BTC 15 min", "GOLD 15 min", " 15 min")


def test_prices_and_money_read_as_on_the_dashboard():
    assert (notify.cents(0.962), notify.cents(0.94), notify.cents(0.9999)) == ("96.2¢", "94¢", "100¢")
    assert (notify.dollars(-15.4133), notify.dollars(2.5), notify.dollars(-0.001)) == ("−$15.41", "$2.50", "$0.00")
    assert notify.dollars(-30000.5) == "−$30,000.50"            # no order cap since Oct 10: big losses read in full


def test_times_are_local_with_no_leading_zero():
    assert notify.clock(NOW) == LOCAL and re.fullmatch(r"[1-9]\d?:\d\d [AP]M", LOCAL)


def test_a_loss_message_says_what_was_bought_what_it_cost_and_opens_the_market(home):
    db = ledger(home)
    add_bet(db, BTC, "lost")
    row = db.execute("SELECT * FROM bets").fetchone()
    msg = notify.loss_message(row)
    assert msg["title"] == "Lost: BTC 15 min"
    assert msg["message"] == f"NO at 96.2¢ × 16 · −$15.49 · settled {LOCAL}"
    assert msg["click"] == "https://kalshi.com/markets/kxbtc15m/kxbtc15m/kxbtc15m-26oct101315"
    assert msg["tags"] == ["chart_with_downwards_trend"] and msg["priority"] == 3


def test_the_loss_is_the_ledgers_own_pnl(home):
    db = ledger(home)
    add_bet(db, BTC, "lost")
    db.execute("UPDATE bets SET pnl = -15.00")                # whatever the bot booked, the phone says the same
    assert " · −$15.00 · " in notify.loss_message(db.execute("SELECT * FROM bets").fetchone())["message"]


@pytest.mark.parametrize("contracts, shown", [(0.03, "0.03"), (31250.0, "31250"), (12345.67, "12345.67"), (1234567.0, "1234567")])
def test_contracts_read_in_full_however_many_or_few(home, contracts, shown):
    db = ledger(home)
    add_bet(db, "KXHYPE15M-26OCT101115-15", "lost", side="yes", price=0.909, contracts=contracts, fee=0.0)
    assert notify.loss_message(db.execute("SELECT * FROM bets").fetchone())["message"].startswith(f"YES at 90.9¢ × {shown} · ")


def test_a_halt_message_says_why_and_is_high_priority():
    msg = notify.halt_message({"ts": bot.iso(NOW), "reason": "the last 24 hours lost 35% of the start", "by": "auto"})
    assert msg["title"] == "Bot halted" and msg["priority"] == 4 and msg["tags"] == ["warning"]
    assert msg["message"] == f"the last 24 hours lost 35% of the start · {LOCAL} · no new orders until python bot.py --resume"
    assert "click" not in msg                      # the dashboard is on localhost: a phone can't open it
    mine = notify.halt_message({"ts": bot.iso(NOW), "reason": "halted from the dashboard", "by": "you"})
    assert mine["message"].startswith(f"halted from the dashboard · {LOCAL}")


# ------------------------------------------------------------------ the same words as the page, run in node
NODE = shutil.which("node")
PAGE = open(dashboard.PAGE, encoding="utf-8").read()


def page_piece(pattern, flags=re.M):
    m = re.search(pattern, PAGE, flags)
    assert m, f"dashboard.html no longer has {pattern!r}"
    return m.group(0)


def on_the_page(calls):
    """Run the page's own formatters on `calls` ({name: [args, ...]}) in node; {name: [result, ...]} back."""
    src = "\n".join([*(page_piece(rf"^const {n} = .*$") for n in ("nf", "zero", "money", "cents", "sym", "title")),   # one line each
                     page_piece(r"^const kalshiUrl = .*?^\};$", re.M | re.S),
                     "const shown = (n) => `${n}`;",                    # how the page writes a bet's contracts: × ${b.contracts}
                     "const calls = JSON.parse(require('fs').readFileSync(0, 'utf8'));",
                     "const fns = { money, cents, title, kalshiUrl, shown };",
                     "process.stdout.write(JSON.stringify(Object.fromEntries(Object.entries(calls).map(([k, xs]) => [k, xs.map((x) => fns[k](x))]))));"])
    r = subprocess.run([NODE, "-e", src], input=json.dumps(calls), capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


TICKERS = ["KXBTC15M-26OCT101315-15", "KXGOLD15M-26OCT101300-00", "KXBTC15M", "kxeth15m-26oct101330-30", "KXETH15M-26OCT101330"]
SERIES = ["KXBTC15M", "KXGOLD15M", "KXWTI15M", "", None, "BTC15M", "KX15M", "KXKXBTC15M15M"]
PRICES = [0.962, 0.94, 0.9999, 0.5, 0.001, 0.955, 0.9625, 0.9675, 0.0125, 0.99949]      # 96.25¢ and the like: a tie to round
MONEY = [-15.4861, 2.5, -0.001, -0.005, -0.0049, 0.0, 2.125, -2.125, 0.125, -30000.5, -1234567.125]
CONTRACTS = [16.0, 0.03, 15.5, 31250.0, 12345.67, 1234567.0, 0.01]


@pytest.mark.skipif(not NODE, reason="node isn't installed")
def test_every_word_and_link_matches_what_the_page_would_show():
    js = on_the_page({"kalshiUrl": TICKERS, "title": SERIES, "cents": PRICES, "money": MONEY, "shown": CONTRACTS})
    assert [notify.kalshi_url(t) for t in TICKERS] == js["kalshiUrl"]
    assert [notify.title(s) for s in SERIES] == js["title"]                 # a missing series too, as the page's (series || "")
    assert [notify.cents(p) for p in PRICES] == js["cents"]                 # ties round up, as JavaScript's toFixed does
    assert [notify.dollars(v) for v in MONEY] == js["money"]                # ... and toLocaleString
    row = {"ticker": BTC, "series": "KXBTC15M", "side": "no", "price": 0.962, "pnl": -1.0, "settled_ts": NOW}
    assert [re.search(r" × (\S+) · ", notify.loss_message({**row, "contracts": c})["message"]).group(1) for c in CONTRACTS] == js["shown"]


# ------------------------------------------------------------------ sending
def test_it_sends_json_to_the_ntfy_server_so_unicode_comes_through(home):
    assert notify.send(CFG, {"title": "Lost: BTC 15 min", "message": "−$1 ¢"}) is True
    assert home.sent == [{"topic": "kalshi-test-topic", "title": "Kalshi · Lost: BTC 15 min", "message": "−$1 ¢"}]
    assert home.urls == [("https://ntfy.sh", 10)]


# ------------------------------------------------------------------ every title marked Kalshi, so it stands out from other topics
def test_the_mark_is_kalshi_and_a_middle_dot():
    assert notify.PREFIX == "Kalshi · "         # the word, a space, a middle dot (U+00B7), a space


def test_send_marks_the_title_and_leaves_the_message_it_was_given_alone(home):
    msg = {"title": "Bot halted", "message": "why · when", "tags": ["warning"], "priority": 4}
    given = json.loads(json.dumps(msg))
    assert notify.send(CFG, msg) is True and notify.send(CFG, msg) is True        # the same message twice: a retry
    assert said(home) == [{**given, "title": "Kalshi · Bot halted"}] * 2          # marked once each time, nothing else changed
    assert msg == given                                                            # the builder's own message isn't touched


def test_a_title_that_already_says_kalshi_isnt_marked_again(home):
    for t in ("Kalshi alerts are on", "Kalshi · Bot halted", "Bot halted"):
        notify.send(CFG, {"title": t, "message": "hi"})
    assert titles(home) == ["Kalshi alerts are on", "Kalshi · Bot halted", "Kalshi · Bot halted"]


def test_a_message_with_no_title_goes_as_it_is(home):
    notify.send(CFG, {"message": "hi", "tags": ["warning"]})
    notify.send(CFG, {"title": "Bot running", "message": "hi"})
    assert said(home) == [{"message": "hi", "tags": ["warning"]}, {"title": "Kalshi · Bot running", "message": "hi"}]   # no title made up


def test_every_alert_kind_reaches_the_phone_marked_kalshi(home):
    db = ledger(home)
    beat(db, NOW)
    sent = check(None, now=NOW)
    add_bet(db, BTC, "lost", settled=NOW + 30)
    bot.set_halt(NOW + 31, "8 bets lost in one window", "auto")
    sent = check(sent, now=NOW + 120)                # a loss, a halt, and then the bot went quiet ...
    beat(db, NOW + 200)
    check(sent, now=NOW + 201)                       # ... and came back
    assert titles(home) == ["Kalshi · Lost: BTC 15 min", "Kalshi · Bot halted", "Kalshi · Bot stopped", "Kalshi · Bot running"]
    built = [notify.loss_message(db.execute("SELECT * FROM bets").fetchone()), notify.halt_message(bot.halt_info()),
             notify.stopped_message(NOW), notify.running_message(NOW + 200)]
    assert [m["title"] for m in built] == ["Lost: BTC 15 min", "Bot halted", "Bot stopped", "Bot running"]   # the builders stay unmarked
    assert said(home) == [{**m, "title": "Kalshi · " + m["title"]} for m in built]   # only the title changes on the way out


def test_the_test_message_isnt_marked_twice_but_real_alerts_are(home, monkeypatch):
    with_env(monkeypatch, **CFG)
    assert notify.main(["--test"]) == 0
    db = ledger(home)
    add_bet(db, OLD, "lost")
    assert notify.main(["--once"]) == 0             # takes note
    add_bet(db, BTC, "lost")
    assert notify.main(["--once"]) == 0
    assert titles(home) == ["Kalshi alerts are on", "Kalshi · Lost: BTC 15 min"]


def test_another_ntfy_server_can_be_named(home):
    notify.send({**CFG, "NTFY_SERVER": "https://ntfy.example.org/"}, {"message": "hi"})
    assert home.urls[0][0] == "https://ntfy.example.org"


@pytest.mark.parametrize("how, why", [("raise", "no network"), ("timeout", "read timed out"), ("error", "boom"), ("status", "429")])
def test_a_send_that_fails_says_so_in_the_log(home, capsys, how, why):
    home.fail = how
    assert notify.send(CFG, {"title": "Lost: BTC 15 min", "message": "hi"}) is False
    assert why in capsys.readouterr().out


# ------------------------------------------------------------------ one check
def test_the_first_check_sends_nothing_and_remembers_what_is_already_there(home):
    db = ledger(home)
    add_bet(db, OLD, "lost")
    bot.set_halt(NOW, "an old halt", "auto")
    sent = check(None)
    assert home.sent == [] and sent == {"lost": [OLD], "halt": bot.iso(NOW), "running": False}   # losses by market: tickers are never reused


def test_a_new_loss_is_sent_once(home):
    db = ledger(home)
    sent = check(None)
    add_bet(db, BTC, "lost")
    sent = check(sent)
    assert titles(home) == ["Kalshi · Lost: BTC 15 min"] and sent["lost"] == [BTC]
    check(sent)
    assert len(home.sent) == 1                     # not again on the next check


@pytest.mark.parametrize("status", ["won", "open"])
def test_wins_and_open_bets_send_nothing(home, status):
    db = ledger(home)
    sent = check(None)
    add_bet(db, BTC, status)
    assert check(sent) == {"lost": [], "halt": None, "running": False} and home.sent == []


def test_a_bet_that_settles_lost_after_the_first_check_is_sent(home):
    db = ledger(home)
    add_bet(db, BTC, "open")
    sent = check(None)                              # open when it took note ...
    db.execute("UPDATE bets SET status='lost', pnl=-15.49, settled_ts=?", (NOW,))
    db.commit()
    check(sent)
    assert titles(home) == ["Kalshi · Lost: BTC 15 min"]     # ... so its loss is news


def test_several_losses_go_out_in_the_order_they_settled(home):
    db = ledger(home)
    sent = check(None)
    add_bet(db, ETH, "lost", settled=NOW + 900)
    add_bet(db, BTC, "lost", settled=NOW)
    check(sent)
    assert titles(home) == ["Kalshi · Lost: BTC 15 min", "Kalshi · Lost: ETH 15 min"]


def test_a_loss_that_couldnt_be_sent_goes_out_on_the_next_check(home):
    db = ledger(home)
    sent = check(None)
    add_bet(db, BTC, "lost")
    home.fail = "raise"
    sent = check(sent)
    assert sent["lost"] == [] and home.sent == []   # not marked as sent
    home.fail = None
    sent = check(sent)
    assert sent["lost"] == [BTC] and len(home.sent) == 1


def test_when_one_of_two_sends_fails_only_that_one_goes_again(home):
    db = ledger(home)
    sent = check(None)
    add_bet(db, BTC, "lost", settled=NOW)
    add_bet(db, ETH, "lost", settled=NOW + 900)
    home.fail = lambda msg: "status" if msg["title"].endswith("Lost: BTC 15 min") else None
    sent = check(sent)
    assert titles(home) == ["Kalshi · Lost: ETH 15 min"] and sent["lost"] == [ETH]
    home.fail = None
    sent = check(sent)
    assert titles(home) == ["Kalshi · Lost: ETH 15 min", "Kalshi · Lost: BTC 15 min"] and sorted(sent["lost"]) == [BTC, ETH]


def test_a_new_halt_is_sent_once_and_a_later_one_again(home):
    ledger(home)
    sent = check(None)
    bot.set_halt(NOW, "the last 24 hours lost 35% of the start", "auto")
    sent = check(sent)
    assert [(m["title"], m["priority"]) for m in home.sent] == [("Kalshi · Bot halted", 4)]
    sent = check(sent)
    assert len(home.sent) == 1                     # the same halt: once
    bot.clear_halt(NOW + 60, [])
    sent = check(sent)
    assert len(home.sent) == 1                     # resuming sends nothing
    bot.set_halt(NOW + 3600, "halted from the dashboard", "you")
    sent = check(sent)
    assert len(home.sent) == 2 and sent["halt"] == bot.iso(NOW + 3600)


def test_a_halt_that_couldnt_be_sent_goes_out_on_the_next_check(home):
    ledger(home)
    sent = check(None)
    bot.set_halt(NOW, "Kalshi is down", "auto")
    home.fail = "status"
    sent = check(sent)
    assert sent["halt"] is None
    home.fail = None
    assert check(sent)["halt"] == bot.iso(NOW)


def test_before_the_bot_has_a_ledger_it_waits_and_creates_nothing(home):
    assert check(None) == {"lost": [], "halt": None, "running": False}           # no ledger: not running, and nothing said
    assert check({"lost": [], "halt": None, "running": False}) == {"lost": [], "halt": None, "running": False}
    assert home.sent == [] and not (home.dir / "live-prod.db").exists()


def test_a_halt_before_the_bot_has_a_ledger_still_counts(home):
    bot.set_halt(NOW, "an old halt", "auto")                  # one halt file for every mode
    sent = check(None)
    assert sent == {"lost": [], "halt": bot.iso(NOW), "running": False} and home.sent == []
    bot.clear_halt(NOW + 60, [])
    bot.set_halt(NOW + 120, "Kalshi is down", "auto")
    check(sent)
    assert titles(home) == ["Kalshi · Bot halted"]


def test_a_ledger_started_over_still_alerts_on_its_new_losses(home):
    db = ledger(home)
    add_bet(db, OLD, "lost")
    sent = check(None)
    db.close()
    (home.dir / "live-prod.db").unlink()                       # a fresh ledger numbers its bets from 1 again ...
    add_bet(ledger(home), BTC, "lost")
    check(sent)
    assert titles(home) == ["Kalshi · Lost: BTC 15 min"]                # ... so bet ids can't be what it remembers


def test_a_state_folder_with_odd_characters_in_its_path_still_opens(home, monkeypatch):
    monkeypatch.setattr(bot, "STATE", str(home.dir / "my state #1 %20"))
    db = ledger(home)
    sent = check(None)
    add_bet(db, BTC, "lost")
    check(sent)
    assert titles(home) == ["Kalshi · Lost: BTC 15 min"]


def test_it_never_writes_to_the_bots_records(home):
    db = ledger(home)
    add_bet(db, BTC, "lost")
    beat(db, NOW)                                   # its heartbeat is read too
    db.close()
    bot.set_halt(NOW, "testing", "auto")
    before = {p.name: p.read_bytes() for p in home.dir.iterdir()}
    sent = check(None)
    add_db = ledger(home)
    add_bet(add_db, ETH, "lost")
    add_db.close()
    before["live-prod.db"] = (home.dir / "live-prod.db").read_bytes()
    check(sent)
    after = {p.name: p.read_bytes() for p in home.dir.iterdir()}
    assert after == before                          # the ledger and halt.json byte for byte, no journal left; check() itself saves nothing


def test_no_lock_is_left_on_the_ledger_after_a_check(home):
    db = ledger(home)
    add_bet(db, BTC, "lost")
    beat(db, NOW)
    sent = check(None)
    check({"lost": [], "halt": sent["halt"], "running": True})
    w = sqlite3.connect(str(home.dir / "live-prod.db"), timeout=0, isolation_level=None)
    w.execute("BEGIN EXCLUSIVE")                    # the bot can commit at once
    w.execute("ROLLBACK")
    w.close()


# ------------------------------------------------------------------ is the bot running? its heartbeat
def test_a_minute_without_a_heartbeat_is_a_stopped_bot():
    assert notify.STOPPED_AFTER == 60                # the dashboard says "Not running" after 30 s; a minute rides out a slow loop


def test_the_heartbeat_is_read_read_only(home):
    assert notify.heartbeat("live-prod") is None and not (home.dir / "live-prod.db").exists()   # no ledger: none, and none made
    db = ledger(home)
    assert notify.heartbeat("live-prod") is None     # a ledger the bot hasn't beaten in yet
    beat(db, NOW + 0.25)
    db.close()
    before = (home.dir / "live-prod.db").read_bytes()
    hb = notify.heartbeat("live-prod")
    assert hb == NOW + 0.25 and isinstance(hb, float)
    assert (home.dir / "live-prod.db").read_bytes() == before and sorted(p.name for p in home.dir.iterdir()) == ["live-prod.db"]
    w = sqlite3.connect(str(home.dir / "live-prod.db"), timeout=0, isolation_level=None)
    w.execute("BEGIN EXCLUSIVE")                     # no lock left
    w.execute("ROLLBACK")
    w.close()


def test_a_busy_or_half_made_ledger_has_its_heartbeat_read_next_time(home):
    db = ledger(home)
    beat(db, NOW)
    db.close()
    let_go = hold(home)
    try:
        with pytest.raises(sqlite3.Error):           # as losses() does: the check fails and is tried again
            notify.heartbeat("live-prod")
    finally:
        let_go()
    (home.dir / "live-demo.db").write_bytes(b"")
    with pytest.raises(sqlite3.Error):
        notify.heartbeat("live-demo")


@pytest.mark.parametrize("age, running", [(0, True), (59.9, True), (60, False), (3600, False), (-5, True)])
def test_the_first_look_notes_whether_the_bot_is_running_and_says_nothing(home, age, running):
    db = ledger(home)
    beat(db, NOW - age)                              # (-5: a heartbeat a little ahead of this clock)
    assert check(None, now=NOW)["running"] is running and home.sent == []


def test_a_bot_that_stops_is_reported_once(home):
    db = ledger(home)
    beat(db, NOW)
    sent = check(None, now=NOW)
    sent = check(sent, now=NOW + 59.9)
    assert home.sent == [] and sent["running"] is True
    sent = check(sent, now=NOW + 60)
    assert said(home) == [{"title": "Kalshi · Bot stopped", "message": f"no heartbeat since {LOCAL} · nothing is being bought",
                           "tags": ["stop_sign"], "priority": 4}]       # no link: the dashboard is on localhost
    assert sent["running"] is False
    check(sent, now=NOW + 3600)
    assert len(home.sent) == 1                       # once


def test_a_bot_that_starts_again_is_reported_once(home):
    db = ledger(home)
    beat(db, NOW - 3600)
    sent = check(None, now=NOW)
    assert sent["running"] is False and home.sent == []   # stopped when it first looked: nothing said
    beat(db, NOW + 100)
    sent = check(sent, now=NOW + 101)
    assert said(home) == [{"title": "Kalshi · Bot running", "message": f"heartbeat at {notify.clock(NOW + 100)} · back to buying",
                           "tags": ["white_check_mark"], "priority": 3}]
    assert sent["running"] is True
    beat(db, NOW + 104)
    check(sent, now=NOW + 105)
    assert len(home.sent) == 1


def test_a_bot_started_after_the_notifier_is_reported_running(home):
    sent = check(None, now=NOW)                      # no ledger yet
    db = ledger(home)
    sent = check(sent, now=NOW + 5)                  # a ledger, but no heartbeat yet: not running, nothing to say
    assert home.sent == [] and sent["running"] is False
    beat(db, NOW + 9)
    check(sent, now=NOW + 10)
    assert titles(home) == ["Kalshi · Bot running"]


def test_a_ledger_that_goes_away_is_a_stop_with_no_time_to_give(home):
    db = ledger(home)
    beat(db, NOW)
    sent = check(None, now=NOW)
    db.close()
    (home.dir / "live-prod.db").unlink()
    check(sent, now=NOW + 5)
    assert said(home) == [{"title": "Kalshi · Bot stopped", "message": "no heartbeat · nothing is being bought", "tags": ["stop_sign"],
                           "priority": 4}]


def test_a_halted_bot_is_not_a_stopped_one(home):
    db = ledger(home)
    beat(db, NOW)
    sent = check(None, now=NOW)
    bot.set_halt(NOW + 2, "the last 24 hours lost 35% of the start", "auto")
    beat(db, NOW + 3)                                # a halted bot keeps its loop, and its heartbeat, going
    sent = check(sent, now=NOW + 5)
    assert titles(home) == ["Kalshi · Bot halted"] and sent["running"] is True


def test_losses_a_halt_and_a_stop_in_one_check_each_go_out(home):
    db = ledger(home)
    beat(db, NOW)
    sent = check(None, now=NOW)
    add_bet(db, BTC, "lost", settled=NOW + 30)
    bot.set_halt(NOW + 31, "8 bets lost in one window", "auto")
    sent = check(sent, now=NOW + 120)                # ... and then the bot went quiet
    assert sorted(titles(home)) == ["Kalshi · Bot halted", "Kalshi · Bot stopped", "Kalshi · Lost: BTC 15 min"]
    assert sent == {"lost": [BTC], "halt": bot.iso(NOW + 31), "running": False}


@pytest.mark.parametrize("before, age, alert", [(True, 600, "Kalshi · Bot stopped"), (False, 0, "Kalshi · Bot running")])
def test_a_stop_or_start_alert_that_couldnt_be_sent_goes_out_on_the_next_check(home, before, age, alert):
    db = ledger(home)
    beat(db, NOW - age)
    home.fail = "status"
    sent = check({"lost": [], "halt": None, "running": before}, now=NOW)
    assert sent["running"] is before and home.sent == []   # unchanged, so it's tried again
    home.fail = None
    beat(db, NOW + 5 - age)
    sent = check(sent, now=NOW + 5)
    assert titles(home) == [alert] and sent["running"] is (not before)


@pytest.mark.parametrize("age, running", [(0, True), (600, False)])
@pytest.mark.parametrize("memory_running", ["absent", None])
def test_a_memory_from_before_the_heartbeat_takes_note_of_it_quietly(home, age, running, memory_running):
    db = ledger(home)
    beat(db, NOW - age)
    old = {"lost": [], "halt": None} if memory_running == "absent" else {"lost": [], "halt": None, "running": None}
    sent = check(old, now=NOW)                       # today's live notify.json has no "running"
    assert home.sent == [] and sent == {"lost": [], "halt": None, "running": running}
    beat(db, NOW + 1)
    check(sent, now=NOW + 2)
    assert titles(home) == ([] if running else ["Kalshi · Bot running"])


def test_just_after_the_pc_wakes_the_bot_gets_one_check_to_catch_up(home):
    db = ledger(home)
    beat(db, NOW)
    sent = check(None, now=NOW)
    sent = check(sent, now=NOW + 3600, just_woke=True)   # both slept an hour; the bot hasn't beaten since
    assert home.sent == [] and sent["running"] is True
    sent = check(sent, now=NOW + 3605)               # still silent a check later: stopped
    assert titles(home) == ["Kalshi · Bot stopped"] and sent["running"] is False


def test_a_bot_back_is_reported_even_on_waking(home):
    db = ledger(home)
    beat(db, NOW - 3600)
    sent = check(None, now=NOW)
    beat(db, NOW + 3600)
    check(sent, now=NOW + 3601, just_woke=True)
    assert titles(home) == ["Kalshi · Bot running"]


def test_without_a_time_it_goes_by_the_clock(home):
    db = ledger(home)
    beat(db, time.time())
    sent = check(None)
    assert sent["running"] is True
    beat(db, time.time() - 3600)
    check(sent)
    assert titles(home) == ["Kalshi · Bot stopped"]


# ------------------------------------------------------------------ memory between checks
def test_what_was_sent_is_remembered_across_restarts(home):
    path = notify.memory_path("live-prod")
    assert path == os.path.join(bot.STATE, "notify.json")
    assert notify.load_sent(path) is None           # never run: the first check will only take note
    notify.save_sent(path, {"lost": [BTC], "halt": None})
    assert notify.load_sent(path) == {"lost": [BTC], "halt": None}
    assert json.loads((home.dir / "notify.json").read_text()) == {"lost": [BTC], "halt": None}
    assert not (home.dir / "notify.json.tmp").exists()   # written whole, then swapped in


@pytest.mark.parametrize("text", ['{"lost": [], "halt": null}', '{"lost": [], "halt": null, "running": true}',
                                  '{"lost": [], "halt": null, "running": false}', '{"lost": [], "halt": null, "running": null}'])
def test_a_memory_with_or_without_running_is_kept(home, text):
    (home.dir / "notify.json").write_text(text)
    assert notify.load_sent(str(home.dir / "notify.json")) == json.loads(text)   # no "running": written before the heartbeat


@pytest.mark.parametrize("text", ["", "not json", "null", "[]", "{}", '{"lost": []}', '{"lost": 3, "halt": null}',
                                  '{"lost": [3], "halt": null}', '{"lost": [], "halt": 7}', '{"lost": [], "halt": null, "running": "yes"}',
                                  '{"lost": [], "halt": null, "running": 1}', '{"lost": [], "halt": null, "running": 0}'])
def test_a_memory_it_cant_use_starts_over_quietly(home, text):
    (home.dir / "notify.json").write_text(text)
    assert notify.load_sent(str(home.dir / "notify.json")) is None   # so the next check takes note instead of crashing or flooding


def test_each_account_keeps_its_own_memory(home, monkeypatch):
    with_env(monkeypatch, **CFG)
    assert notify.memory_path("live-demo") == os.path.join(bot.STATE, "notify-live-demo.json")
    demo, prod = ledger(home, "live-demo"), ledger(home)
    add_bet(demo, ETH, "lost")
    add_bet(prod, OLD, "lost")
    assert notify.main(["--once", "--mode", "live-demo"]) == 0
    assert notify.main(["--once"]) == 0            # the real account's first look: it takes note too, rather than flood
    assert home.sent == [] and memory("live-demo")["lost"] == [ETH] and memory()["lost"] == [OLD]
    add_bet(prod, BTC, "lost")
    add_bet(demo, BTC, "lost")                      # the same market lost on both: each account says so once
    notify.main(["--once"])
    notify.main(["--once", "--mode", "live-demo"])
    assert titles(home) == ["Kalshi · Lost: BTC 15 min", "Kalshi · Lost: BTC 15 min"]


# ------------------------------------------------------------------ the command line
def with_env(monkeypatch, **cfg):
    monkeypatch.setattr(bot, "load_env", lambda *a, **k: dict(cfg))


class Slept(float):
    """A step for run_loop: in that pause the PC slept this many seconds more."""


@pytest.fixture
def clock(monkeypatch):
    """notify's clock, faked: time() and monotonic() read `t` (from NOW); sleep(s) moves it on by s and then runs the
    next of `steps` (a function, or Slept(seconds) to move it on further), and the pause after the last step raises
    SystemExit("stop")."""
    c = types.SimpleNamespace(t=float(NOW), naps=[], steps=[])

    def sleep(s):
        c.naps.append(s)
        if len(c.naps) > len(c.steps):
            raise SystemExit("stop")
        c.t += s
        step = c.steps[len(c.naps) - 1]
        if isinstance(step, Slept):
            c.t += step
        else:
            step()
    monkeypatch.setattr(notify, "time", types.SimpleNamespace(time=lambda: c.t, monotonic=lambda: c.t, sleep=sleep))
    return c


def run_loop(clock, *steps, argv=()):
    """main()'s loop for len(steps) + 1 checks: steps[i] runs in the pause after check i + 1. Returns each pause's length."""
    clock.steps = list(steps)
    with pytest.raises(SystemExit, match="stop"):
        notify.main(list(argv))
    return clock.naps


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def can_take(port):
    """Whether another program could bind this localhost port now."""
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", port))
        except OSError:
            return False
        return True


@pytest.fixture
def taken(home, monkeypatch):
    """Another notifier already running: a localhost port already bound, which notify.py is pointed at."""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    monkeypatch.setattr(notify, "NOTIFY_PORT", s.getsockname()[1], raising=False)
    yield s.getsockname()[1]
    s.close()


def count_saves(monkeypatch, blocked=lambda: False):
    """Each memory save, in order; while `blocked()` it fails the way Windows does when another program holds the file."""
    real, saves = notify.save_sent, []

    def save(path, sent):
        saves.append(sent)
        if blocked():
            raise PermissionError(13, "The process cannot access the file because it is being used by another process", path)
        real(path, sent)
    monkeypatch.setattr(notify, "save_sent", save)
    return saves


def test_it_wont_start_without_a_topic(home, monkeypatch, capsys):
    with_env(monkeypatch)
    monkeypatch.delenv("NTFY_TOPIC", raising=False)
    assert notify.main([]) == 2
    assert "NTFY_TOPIC" in capsys.readouterr().out and home.sent == []


def test_the_topic_can_come_from_the_environment(home, monkeypatch):
    with_env(monkeypatch)
    monkeypatch.setenv("NTFY_TOPIC", "from-env")
    assert notify.main(["--test"]) == 0 and home.sent[0]["topic"] == "from-env"


def test_test_sends_one_message_and_says_whether_it_went(home, monkeypatch, capsys):
    with_env(monkeypatch, **CFG)
    assert notify.main(["--test"]) == 0
    assert home.sent[0]["title"] == "Kalshi alerts are on" and "sent" in capsys.readouterr().out
    home.fail = "raise"
    assert notify.main(["--test"]) == 1 and "couldn't" in capsys.readouterr().out
    assert not os.path.exists(notify.memory_path("live-prod"))   # a test message is no check


def test_once_takes_note_saves_and_stops(home, monkeypatch):
    with_env(monkeypatch, **CFG)
    add_bet(ledger(home), BTC, "lost")
    assert notify.main(["--once"]) == 0
    assert home.sent == [] and memory() == {"lost": [BTC], "halt": None, "running": False}


def test_once_after_that_sends_what_is_new(home, monkeypatch):
    with_env(monkeypatch, **CFG)
    db = ledger(home)
    add_bet(db, OLD, "lost")
    notify.main(["--once"])
    add_bet(db, BTC, "lost")
    assert notify.main(["--once"]) == 0
    assert titles(home) == ["Kalshi · Lost: BTC 15 min"] and memory()["lost"] == [OLD, BTC]


def test_a_check_that_finds_nothing_new_leaves_the_memory_untouched(home, monkeypatch):
    with_env(monkeypatch, **CFG)
    add_bet(ledger(home), OLD, "lost")
    assert notify.main(["--once"]) == 0
    path = Path(notify.memory_path("live-prod"))
    text = path.read_bytes()
    os.utime(path, ns=(1_000_000_000, 1_000_000_000))
    assert notify.main(["--once"]) == 0 and home.sent == []
    assert path.read_bytes() == text and path.stat().st_mtime_ns == 1_000_000_000   # not rewritten: no churn for a sync app


def test_the_loop_checks_every_few_seconds_and_saves_only_what_changed(home, clock, monkeypatch):
    with_env(monkeypatch, **CFG)
    db = ledger(home)
    saves = count_saves(monkeypatch)
    naps = run_loop(clock, lambda: add_bet(db, BTC, "lost"), lambda: None)   # settles between the first check and the second
    assert naps == [notify.NOTIFY_EVERY] * 3 and notify.NOTIFY_EVERY == 5
    assert titles(home) == ["Kalshi · Lost: BTC 15 min"]
    assert saves == [{"lost": [], "halt": None, "running": False},      # the first look, then the loss; the quiet third
                     {"lost": [BTC], "halt": None, "running": False}]   # check writes nothing


def test_the_first_look_is_saved_even_when_there_is_nothing_to_note(home, monkeypatch):
    with_env(monkeypatch, **CFG)
    assert notify.main(["--once"]) == 0
    assert memory() == {"lost": [], "halt": None, "running": False}   # so a loss before the next start is news, not history


def test_a_busy_ledger_is_read_on_a_later_check(home, clock, monkeypatch, capsys):
    with_env(monkeypatch, **CFG)
    db = ledger(home)
    add_bet(db, OLD, "lost")
    let_go = hold(home)
    saves = count_saves(monkeypatch)
    run_loop(clock, let_go, lambda: add_bet(db, BTC, "lost"))
    assert "locked" in capsys.readouterr().out                 # the first check couldn't read it, and said so ...
    assert saves[0] == {"lost": [OLD], "halt": None, "running": False}   # ... and wasn't taken as an empty ledger (that would flood)
    assert titles(home) == ["Kalshi · Lost: BTC 15 min"]                # the second took note, the third sent the new loss


def test_once_says_so_when_the_ledger_is_busy_and_doesnt_wait_past_the_next_check(home, monkeypatch, capsys):
    with_env(monkeypatch, **CFG)
    add_bet(ledger(home), OLD, "lost")
    let_go = hold(home)
    try:
        t = time.monotonic()
        assert notify.main(["--once"]) == 1
        assert time.monotonic() - t < notify.NOTIFY_EVERY
    finally:
        let_go()
    assert "locked" in capsys.readouterr().out and memory() is None and home.sent == []


def test_a_ledger_still_being_made_is_left_alone_and_read_later(home, monkeypatch):
    with_env(monkeypatch, **CFG)
    (home.dir / "live-prod.db").write_bytes(b"")       # the bot has the file but no tables yet
    assert notify.main(["--once"]) == 1
    assert (home.dir / "live-prod.db").read_bytes() == b"" and memory() is None
    add_bet(ledger(home), OLD, "lost")
    assert notify.main(["--once"]) == 0 and home.sent == [] and memory()["lost"] == [OLD]


def test_a_halt_file_that_cant_be_read_is_alerted_as_a_halt(home, clock, monkeypatch):
    """The bot writes its halt file whole now (set_halt swaps in a finished file), so half of one never comes from it.
    One that can't be read still means a halt, so it's sent; should it then read whole, that halt is sent too: an
    extra message is better than a halt the phone never hears about."""
    with_env(monkeypatch, **CFG)
    ledger(home)
    halt = home.dir / "halt.json"
    run_loop(clock, lambda: halt.write_text('{"ts": "2026-10-1'),             # cut off by something other than the bot
             lambda: halt.write_text(json.dumps({"ts": bot.iso(NOW), "reason": "Kalshi is down", "by": "auto"})))
    assert titles(home) == ["Kalshi · Bot halted", "Kalshi · Bot halted"]
    assert said(home)[0]["message"].startswith("halt.json couldn't be read, so it counts as a halt · ")
    assert said(home)[1]["message"].startswith("Kalshi is down · ")


def test_a_memory_it_cant_save_is_retried_and_nothing_is_sent_twice(home, clock, monkeypatch, capsys):
    with_env(monkeypatch, **CFG)
    db = ledger(home)
    blocked = []
    saves = count_saves(monkeypatch, blocked=lambda: bool(blocked))

    def loss_while_a_sync_app_holds_the_file():
        add_bet(db, BTC, "lost")
        blocked.append(True)
    run_loop(clock, loss_while_a_sync_app_holds_the_file, blocked.clear)
    assert titles(home) == ["Kalshi · Lost: BTC 15 min"]                # once, though saving it failed ...
    assert "being used by another process" in capsys.readouterr().out
    assert len(saves) == 3 and memory() == {"lost": [BTC], "halt": None, "running": False}   # ... and saved on the next check


def test_anything_else_that_goes_wrong_is_logged_and_the_checks_go_on(home, clock, monkeypatch, capsys):
    with_env(monkeypatch, **CFG)
    db = ledger(home)
    real, calls = notify.check, []

    def check_that_breaks_once(*a, **k):
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError("something nobody thought of")
        return real(*a, **k)
    monkeypatch.setattr(notify, "check", check_that_breaks_once)
    run_loop(clock, lambda: add_bet(db, BTC, "lost"), lambda: None)
    assert "something nobody thought of" in capsys.readouterr().out
    assert titles(home) == ["Kalshi · Lost: BTC 15 min"]


def test_ctrl_c_stops_it_with_a_word_and_lets_go_of_the_lock(home, clock, monkeypatch, capsys):
    with_env(monkeypatch, **CFG)
    port = free_port()
    monkeypatch.setattr(notify, "NOTIFY_PORT", port, raising=False)

    def ctrl_c():
        raise KeyboardInterrupt
    clock.steps = [ctrl_c]                                     # in its first pause
    try:
        assert notify.main([]) == 0
    except KeyboardInterrupt:
        pytest.fail("Ctrl+C escaped as a traceback")      # (and caught here, so it can't stop the rest of the suite)
    assert capsys.readouterr().out.rstrip().endswith("stopped")
    assert memory() == {"lost": [], "halt": None, "running": False}   # the check before it was kept
    assert can_take(port)


def test_it_runs_as_a_script(home, monkeypatch):
    """--test: the one mode that takes no lock, so the real notifier holding the default port doesn't matter here."""
    with_env(monkeypatch, **CFG)
    monkeypatch.setattr("sys.argv", ["notify.py", "--test"])
    with pytest.raises(SystemExit) as e:
        runpy.run_path(notify.__file__, run_name="__main__")
    assert e.value.code == 0 and titles(home) == ["Kalshi alerts are on"]


# ------------------------------------------------------------------ the loop and the heartbeat: the PC asleep
def test_waking_from_sleep_gives_the_bot_a_check_to_beat_again(home, clock, monkeypatch):
    with_env(monkeypatch, **CFG)
    db = ledger(home)
    beat(db, clock.t)
    run_loop(clock, Slept(3600), lambda: beat(db, clock.t))   # an hour asleep, then the bot's own loop beats again
    assert home.sent == []


def test_a_bot_still_silent_a_check_after_waking_is_reported(home, clock, monkeypatch):
    with_env(monkeypatch, **CFG)
    db = ledger(home)
    beat(db, clock.t)
    run_loop(clock, Slept(3600), lambda: None)
    assert titles(home) == ["Kalshi · Bot stopped"]


@pytest.mark.parametrize("slept, reported", [(10, True), (11, False)])
def test_more_than_three_checks_apart_is_waking_from_sleep(home, clock, monkeypatch, slept, reported):
    with_env(monkeypatch, **CFG)
    db = ledger(home)
    beat(db, clock.t - 50)                           # fresh at the first look, over a minute old at the next
    run_loop(clock, Slept(slept))                    # checks 5 + 10 = 15 s apart (3 checks' worth), or 16
    assert titles(home) == (["Kalshi · Bot stopped"] if reported else [])


# ------------------------------------------------------------------ --log: no console under pythonw.exe
def test_log_appends_everything_it_prints_to_a_file_in_utf8(home, monkeypatch):
    with_env(monkeypatch, **CFG)
    log = home.dir / "notify.log"
    log.write_text("earlier\n", encoding="utf-8")
    db = ledger(home)
    notify.main(["--once", "--log", str(log)])
    add_bet(db, BTC, "lost")
    home.fail = "unicode"
    notify.main(["--once", "--log", str(log)])
    home.fail = None
    notify.main(["--once", "--log", str(log)])
    text = log.read_text(encoding="utf-8")
    assert text.startswith("earlier\n") and "réseau coupé − 5¢" in text   # appended, in UTF-8
    assert "Lost: BTC 15 min" in text.splitlines()[-1]


def test_log_works_with_no_console_at_all(home, monkeypatch):
    with_env(monkeypatch, **CFG)
    monkeypatch.setattr(sys, "stdout", None)         # pythonw.exe: print() would go nowhere
    log = home.dir / "notify.log"
    assert notify.main(["--test", "--log", str(log)]) == 0
    text = log.read_text(encoding="utf-8")
    assert "Kalshi alerts are on" in text and "Test message sent." in text
    assert sys.stdout is None                        # put back as it was


def test_each_line_is_in_the_log_as_it_happens(home, clock, monkeypatch):
    with_env(monkeypatch, **CFG)
    db = ledger(home)
    log, seen = home.dir / "notify.log", []
    run_loop(clock, lambda: add_bet(db, BTC, "lost"), lambda: seen.append(log.read_text(encoding="utf-8")), argv=["--log", str(log)])
    assert "Lost: BTC 15 min" in seen[0]             # there while the loop still runs, not only when it stops
    log.unlink()                                     # and closed when the loop ended, here by an exception


def test_the_log_is_closed_and_printing_put_back_when_it_ends(home, monkeypatch, capsys):
    with_env(monkeypatch, **CFG)
    log = home.dir / "notify.log"
    assert notify.main(["--test", "--log", str(log)]) == 0
    log.unlink()                                     # Windows can't delete a file that's still open
    print("after")
    assert capsys.readouterr().out.endswith("after\n")


def test_a_missing_topic_is_said_in_the_log_too(home, monkeypatch):
    with_env(monkeypatch)
    monkeypatch.delenv("NTFY_TOPIC", raising=False)
    log = home.dir / "notify.log"
    assert notify.main(["--log", str(log)]) == 2
    assert "NTFY_TOPIC" in log.read_text(encoding="utf-8")


# ------------------------------------------------------------------ one notifier at a time
def test_the_lock_is_a_localhost_port_of_its_own():
    port = notify.NOTIFY_PORT                         # the real default (no `home` here)
    assert isinstance(port, int) and 1024 <= port <= 65535 and port not in (8080, 9000)   # not either dashboard's


def test_a_second_notifier_sends_nothing_and_says_why(home, taken, clock, monkeypatch, capsys):
    with_env(monkeypatch, **CFG)
    path = notify.memory_path("live-prod")
    notify.save_sent(path, {"lost": [], "halt": None, "running": False})
    add_bet(ledger(home), BTC, "lost")               # news the first notifier will send, so this one mustn't
    before = Path(path).read_bytes()
    assert notify.main(["--once"]) == 0
    assert "another notifier is already running" in capsys.readouterr().out
    log = home.dir / "notify.log"
    assert notify.main(["--log", str(log)]) == 0     # the loop too: it stops at once, without a pause (the clock would say)
    assert "another notifier is already running" in log.read_text(encoding="utf-8")
    assert home.sent == [] and Path(path).read_bytes() == before and clock.naps == []


def test_a_test_message_needs_no_lock(home, taken, monkeypatch):
    with_env(monkeypatch, **CFG)
    assert notify.main(["--test"]) == 0 and titles(home) == ["Kalshi alerts are on"]


def test_the_lock_is_held_while_it_runs_and_let_go_however_it_ends(home, clock, monkeypatch):
    with_env(monkeypatch, **CFG)
    port = free_port()
    monkeypatch.setattr(notify, "NOTIFY_PORT", port, raising=False)
    held = []
    run_loop(clock, lambda: held.append(can_take(port)))
    assert held == [False]                           # taken while it ran ...
    assert can_take(port)                            # ... let go when it ended, here by an exception
    assert notify.main(["--once"]) == 0 and can_take(port)   # and after a single check


def test_the_topic_stays_out_of_the_example_env():
    example = open(os.path.join(BOT, ".env.example"), encoding="utf-8").read()
    assert re.search(r"^NTFY_TOPIC=$", example, re.M) and "# NTFY_SERVER=https://ntfy.sh" in example


# ------------------------------------------------------------------ only a lost bet reaches the phone
# Since Oct 27, 2026: only a lost bet reaches the phone. ALERTS is the whole policy, and the
# `home` fixture above turns everything on, so these set it back to what ships.
def test_what_ships_is_losses_only():
    assert notify.ALERTS == ("loss",)


def test_every_other_kind_is_dropped_but_counts_as_sent(home, monkeypatch):
    monkeypatch.setattr(notify, "ALERTS", ("loss",))
    assert notify.send(CFG, {"title": "Lost: BTC 15 min", "message": "hi"}) is True
    assert titles(home) == ["Kalshi · Lost: BTC 15 min"]
    for kind in ("halt", "run", "stall"):
        assert notify.send(CFG, {"title": "nope", "message": "hi"}, kind) is True   # counted as sent ...
    assert len(home.sent) == 1                                                       # ... and never posted


def test_a_halt_is_not_pushed_and_is_not_retried_every_check(home, monkeypatch):
    monkeypatch.setattr(notify, "ALERTS", ("loss",))
    ledger(home)
    sent = check(None)
    bot.set_halt(NOW, "Kalshi is down", "auto")
    sent = check(sent)
    assert home.sent == []                        # nothing on the phone ...
    assert sent["halt"] == bot.iso(NOW)           # ... and written down, so it isn't tried again every 5 seconds


def test_a_lost_bet_still_gets_through(home, monkeypatch):
    monkeypatch.setattr(notify, "ALERTS", ("loss",))
    db = ledger(home)
    add_bet(db, BTC, "open")
    sent = check(None)
    db.execute("UPDATE bets SET status='lost', pnl=-15.49, settled_ts=?", (NOW,))
    db.commit()
    check(sent)
    assert titles(home) == ["Kalshi · Lost: BTC 15 min"]


def test_the_test_message_goes_even_with_every_alert_off(home, monkeypatch):
    """python -m kalshi_bot.notify --test is someone asking whether ntfy works at all, so it is never filtered."""
    monkeypatch.setattr(notify, "ALERTS", ())
    assert notify.send(CFG, {"title": "Kalshi alerts are on", "message": "hi"}, "test") is True
    assert len(home.sent) == 1
