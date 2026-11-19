"""stall_alert.py: a phone alert when the live bot stops working while still looking alive.

Why this exists: on Oct 24, 2026 Kalshi's `status=open` market filter matched nothing for about seven
hours. The bot's listing call came back 200 with an empty list and no error, so `listed()` returned nothing,
`step()` took its "nothing listed, try again next loop" branch, and the bot placed no bets for 27 windows.
Nothing noticed: the process was up, the heartbeat was fresh, no halt was set, the error log was empty, and
the healthchecks.io watchdog only ever proved the process was alive. The filter then recovered on its own
with no restart; it was never retired. The same silent gap had already cost 6 windows on Oct 18.

So this alert runs OUTSIDE bot.py, on the bot's records rather than its code: if the bot's own loop is
broken, a tripwire inside that loop is broken too. It reads the ledger read-only and never writes to it.

The signal is `decisions`, not `bets`. The bot writes a decision row for every market it looks at, every
window, even when it skips them all, so no decisions at all means it is not looking. A quiet market can
legitimately produce no BETS for an hour (the longest real gap on record is 4 windows), which is why bets
get a much looser threshold of their own.

What must not happen: an alert during Kalshi's scheduled Thursday maintenance, an alert while the bot is
halted (notify.py already owns halts), the same alert twice, a missed recovery, a recovery reported because
the bot halted or Kalshi went into maintenance while the fault still stood, or any write to the ledger.
    python -m pytest tests/test_stall_alert.py -q
"""

import sqlite3
import types
from datetime import datetime
from pathlib import Path

import pytest

from kalshi_bot import bot
from kalshi_bot import stall_alert

NOW = 1_791_660_000                                     # Oct 10 2026, 3:20 pm in New York: not a maintenance window
WINDOW = 900.0
CFG = {"NTFY_TOPIC": "kalshi-test-topic"}
BTC, ETH = "KXBTC15M-26OCT101315-15", "KXETH15M-26OCT101330-30"


def thursday_maintenance():
    """A Thursday 3-5 am ET instant, when Kalshi pauses and lists nothing."""
    return datetime(2026, 10, 22, 3, 30, tzinfo=bot.ET).timestamp()


@pytest.fixture
def ledger(tmp_path):
    """A real bot ledger, with the bot own schema."""
    db = bot.connect(str(tmp_path / "state" / "live-prod.db"))
    bot.set_meta(db, "start", 1000.0)
    db.commit()
    return db


def decide(db, ts, ticker=BTC):
    db.execute("INSERT OR IGNORE INTO decisions (ts, ticker, series, action, reason) VALUES (?,?,?,?,?)",
               (ts, ticker, ticker.split("-")[0], "skip", "favorite outside the band"))
    db.commit()


def place(db, ts, ticker=ETH):
    db.execute("INSERT OR IGNORE INTO bets (ticker, series, window_open, close_ts, side, price, contracts,"
               " cost, fee, placed_ts, status) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
               (ticker, ticker.split("-")[0], ts - 480, ts + 420, "yes", 0.96, 10, 9.6, 0.02, ts, "open"))
    db.commit()


def beat(db, ts):
    bot.set_meta(db, "heartbeat", ts)
    db.commit()


# ------------------------------------------------------------------ what counts as trouble
def test_a_quiet_market_is_not_a_stall(ledger):
    """Decisions every window but no bets for an hour: the 92c floor skipping everything is normal."""
    beat(ledger, NOW - 2)
    for i in range(8):
        decide(ledger, NOW - i * WINDOW, "KXBTC15M-26OCT10-%d" % i)
    place(ledger, NOW - 6 * WINDOW)
    assert stall_alert.look(ledger, NOW) is None


def test_no_decisions_for_eight_windows_alerts(ledger):
    """Oct 24 failure exactly: process alive, heartbeat fresh, no halt, nothing looked at for 2 hours."""
    beat(ledger, NOW - 2)
    decide(ledger, NOW - 9 * WINDOW)
    place(ledger, NOW - 9 * WINDOW)
    found = stall_alert.look(ledger, NOW)
    assert found and found["kind"] == "stalled"
    assert "window" in found["message"].lower()


def test_a_fresh_heartbeat_does_not_excuse_a_stall(ledger):
    """The heartbeat is what fooled the watchdog on Oct 24: it must not suppress the stall alert."""
    beat(ledger, NOW)
    decide(ledger, NOW - 20 * WINDOW)
    assert stall_alert.look(ledger, NOW)["kind"] == "stalled"


def test_stale_heartbeat_alerts(ledger):
    """The loop itself has stopped: a different fault, and worth saying so."""
    beat(ledger, NOW - 3600)
    decide(ledger, NOW - 2)
    assert stall_alert.look(ledger, NOW)["kind"] == "dead"


def test_no_bets_for_a_long_time_alerts_even_while_looking(ledger):
    """Decisions are being written but nothing has been bought for six hours: worth a look."""
    beat(ledger, NOW - 2)
    for i in range(30):
        decide(ledger, NOW - i * WINDOW, "KXBTC15M-26OCT10-%d" % i)
    place(ledger, NOW - 30 * WINDOW)
    assert stall_alert.look(ledger, NOW)["kind"] == "quiet"


# ------------------------------------------------------------------ what must stay silent
def test_a_halt_is_left_to_notify(ledger):
    """notify.py already alerts on halts; this must not double up, however long the bot has been idle."""
    beat(ledger, NOW - 2)
    decide(ledger, NOW - 20 * WINDOW)
    assert stall_alert.look(ledger, NOW, halted={"reason": "8 bets lost in one window"}) is None


def test_scheduled_maintenance_is_not_a_stall(ledger):
    """Kalshi pauses Thursdays 3-5 am ET and lists nothing: an empty window there is expected."""
    now = thursday_maintenance()
    beat(ledger, now - 2)
    decide(ledger, now - 20 * WINDOW)
    assert stall_alert.look(ledger, now) is None


def test_maintenance_still_reports_a_dead_loop(ledger):
    """Maintenance explains no markets; it does not explain the bot own loop stopping."""
    now = thursday_maintenance()
    beat(ledger, now - 3600)
    decide(ledger, now - 2)
    assert stall_alert.look(ledger, now)["kind"] == "dead"


def test_an_empty_ledger_says_nothing(ledger):
    """Before the bot first run there is nothing to judge: no alert, no crash."""
    assert stall_alert.look(ledger, NOW) is None


# ------------------------------------------------------------------ sending, once
def test_alerts_once_then_stays_quiet(ledger, tmp_path, monkeypatch):
    sent = []
    monkeypatch.setattr(stall_alert.notify, "send", lambda cfg, msg, kind=None: sent.append(msg) or True)
    beat(ledger, NOW - 2)
    decide(ledger, NOW - 20 * WINDOW)
    seen = tmp_path / "stall_alert.json"
    assert stall_alert.check(CFG, ledger, NOW, str(seen)) is True
    assert stall_alert.check(CFG, ledger, NOW + 60, str(seen)) is False
    assert len(sent) == 1


def test_recovery_is_announced(ledger, tmp_path, monkeypatch):
    sent = []
    monkeypatch.setattr(stall_alert.notify, "send", lambda cfg, msg, kind=None: sent.append(msg) or True)
    seen = tmp_path / "stall_alert.json"
    beat(ledger, NOW - 2)
    decide(ledger, NOW - 20 * WINDOW)
    stall_alert.check(CFG, ledger, NOW, str(seen))
    decide(ledger, NOW + 60, "KXBTC15M-26OCT101400-00")           # it starts looking again
    assert stall_alert.check(CFG, ledger, NOW + 120, str(seen)) is True
    assert len(sent) == 2 and "again" in sent[1]["message"].lower()


def test_ntfy_failing_leaves_it_unsent(ledger, tmp_path, monkeypatch):
    """A refused push must not be remembered as sent, or the next run would stay quiet about a live fault."""
    monkeypatch.setattr(stall_alert.notify, "send", lambda cfg, msg, kind=None: False)
    beat(ledger, NOW - 2)
    decide(ledger, NOW - 20 * WINDOW)
    seen = tmp_path / "stall_alert.json"
    assert stall_alert.check(CFG, ledger, NOW, str(seen)) is False
    sent = []
    monkeypatch.setattr(stall_alert.notify, "send", lambda cfg, msg, kind=None: sent.append(msg) or True)
    assert stall_alert.check(CFG, ledger, NOW + 60, str(seen)) is True


# ------------------------------------------------------------------ it must never disturb the bot
def test_it_never_writes_to_the_ledger(tmp_path):
    """The live ledger is the bot own: opened read-only, so a bug here can never corrupt real trading."""
    path = tmp_path / "state" / "live-prod.db"
    db = bot.connect(str(path))
    bot.set_meta(db, "start", 1000.0)
    db.commit()
    db.close()
    ro = stall_alert.open_ledger(str(path))
    with pytest.raises(sqlite3.OperationalError):
        ro.execute("INSERT INTO meta (key, value) VALUES ('x','y')")


def test_the_topic_is_never_in_the_code():
    """The ntfy topic is read from .env at run time and never copied into code."""
    source = Path(stall_alert.__file__).read_text(encoding="utf-8")
    assert "ntfy.sh/" not in source, "no hard-coded topic URL"
    cfg = stall_alert.config({"NTFY_TOPIC": "from-env"})
    assert cfg["NTFY_TOPIC"] == "from-env"


def test_a_halt_or_maintenance_is_not_a_recovery(ledger, tmp_path, monkeypatch):
    """look() answers None for three different reasons and only one of them is good news. A bot that is
    still not looking at markets must not be reported as working again just because it halted, or because
    Kalshi went into its Thursday maintenance -- that clears the memory and starts the count over."""
    sent = []
    monkeypatch.setattr(stall_alert.notify, "send", lambda cfg, msg, kind=None: (sent.append(msg), True)[1])
    seen = str(tmp_path / "seen.json")
    beat(ledger, NOW - 2)
    decide(ledger, NOW - 9 * WINDOW)
    assert stall_alert.check(CFG, ledger, NOW, seen) and sent[-1]["title"] == "Bot not looking at markets"

    monkeypatch.setattr(stall_alert.bot, "scheduled_maintenance", lambda t: True)
    assert stall_alert.check(CFG, ledger, NOW + 60, seen) is False          # still stalled: say nothing
    monkeypatch.setattr(stall_alert.bot, "scheduled_maintenance", lambda t: False)
    halt = {"reason": "the account fell 35% within 24 hours", "ts": "t", "by": "auto"}
    assert stall_alert.check(CFG, ledger, NOW + 120, seen, halted=halt) is False
    assert [m["title"] for m in sent] == ["Bot not looking at markets"]     # nothing more was sent
    assert stall_alert._read_seen(seen)["kind"] == "stalled"                # and the fault is remembered

    decide(ledger, NOW + 180, "KXBTC15M-26OCT101345-45")                    # it really is looking again
    beat(ledger, NOW + 180)
    assert stall_alert.check(CFG, ledger, NOW + 240, seen)
    assert sent[-1]["title"] == "Bot working again"


# ------------------------------------------------------------------ a dry run, a refused push, a memory it can't save
def test_a_fault_in_a_dry_run_is_said_not_sent_and_not_remembered(ledger, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(stall_alert.notify, "send", lambda *a, **kw: pytest.fail("a dry run sent a push"))
    beat(ledger, NOW - 2)
    decide(ledger, NOW - 20 * WINDOW)
    seen = tmp_path / "seen.json"
    assert stall_alert.check(CFG, ledger, NOW, str(seen), dry_run=True) is True
    assert "would send: Bot not looking at markets" in capsys.readouterr().out
    assert not seen.exists()                                                # nothing remembered: the real run still says it


def test_a_recovery_in_a_dry_run_is_said_not_sent_and_the_fault_is_kept(ledger, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(stall_alert.notify, "send", lambda *a, **kw: pytest.fail("a dry run sent a push"))
    seen = tmp_path / "seen.json"
    stall_alert._write_seen(str(seen), {"kind": "stalled", "since": NOW - 3600})
    beat(ledger, NOW - 2)
    decide(ledger, NOW - 60)
    assert stall_alert.check(CFG, ledger, NOW, str(seen), dry_run=True) is True
    assert "would send: Bot working again" in capsys.readouterr().out
    assert stall_alert._read_seen(str(seen))["kind"] == "stalled"


def test_a_recovery_ntfy_refuses_is_tried_again_next_run(ledger, tmp_path, monkeypatch):
    """The same rule as a fault's push: one ntfy refused isn't remembered as said."""
    seen = tmp_path / "seen.json"
    stall_alert._write_seen(str(seen), {"kind": "dead", "since": NOW - 3600})
    beat(ledger, NOW - 2)
    decide(ledger, NOW - 60)
    monkeypatch.setattr(stall_alert.notify, "send", lambda *a, **kw: False)
    assert stall_alert.check(CFG, ledger, NOW, str(seen)) is False
    assert stall_alert._read_seen(str(seen))["kind"] == "dead"
    sent = []
    monkeypatch.setattr(stall_alert.notify, "send", lambda cfg, msg, kind=None: sent.append(msg) or True)
    beat(ledger, NOW + 598)                                                 # ten minutes on, still alive and looking
    decide(ledger, NOW + 540, "KXBTC15M-26OCT101330-30")
    assert stall_alert.check(CFG, ledger, NOW + 600, str(seen)) is True
    assert [m["title"] for m in sent] == ["Bot working again"] and stall_alert._read_seen(str(seen)) == {}


def test_a_memory_it_cant_save_is_said_and_never_a_crash(tmp_path, capsys):
    blocker = tmp_path / "a-file"
    blocker.write_text("not a folder")
    stall_alert._write_seen(str(blocker / "seen.json"), {"kind": "stalled", "since": NOW})
    assert "couldn't save what was sent" in capsys.readouterr().out


# ------------------------------------------------------------------ the command line (the 10-minute timer's run)
@pytest.fixture
def cli(ledger, tmp_path, monkeypatch):
    """main()'s run on a ledger stalled for 20 windows, with the topic set and every push recorded."""
    monkeypatch.setattr(stall_alert, "config", lambda env=None: dict(CFG))
    sent = []
    monkeypatch.setattr(stall_alert.notify, "send", lambda cfg, msg, kind=None: sent.append(msg) or True)
    monkeypatch.setattr(stall_alert.time, "time", lambda: NOW)
    beat(ledger, NOW - 2)
    decide(ledger, NOW - 20 * WINDOW)
    db = str(tmp_path / "state" / "live-prod.db")
    return types.SimpleNamespace(args=["--db", db, "--seen", str(tmp_path / "seen.json")], sent=sent, db=db)


def test_the_timers_run_says_what_it_found_and_pushes_it_once(cli, capsys):
    assert stall_alert.main(cli.args) == 0
    assert "stalled: " in capsys.readouterr().out
    assert [m["title"] for m in cli.sent] == ["Bot not looking at markets"]
    assert stall_alert.main(cli.args) == 0 and len(cli.sent) == 1          # said once


def test_the_timers_run_on_a_healthy_bot_says_ok_and_sends_nothing(cli, ledger, capsys):
    decide(ledger, NOW - 60, "KXBTC15M-26OCT101300-00")
    assert stall_alert.main(cli.args) == 0
    assert capsys.readouterr().out.strip().endswith(" OK") and cli.sent == []


def test_a_dry_run_from_the_command_line_sends_nothing(cli, capsys):
    assert stall_alert.main(cli.args + ["--dry-run"]) == 0
    assert "would send: Bot not looking at markets" in capsys.readouterr().out and cli.sent == []


def test_without_a_topic_it_says_how_to_set_one_and_exits_2(cli, monkeypatch, capsys):
    monkeypatch.setattr(stall_alert, "config", lambda env=None: {})
    assert stall_alert.main(cli.args) == 2
    assert "NTFY_TOPIC" in capsys.readouterr().out and cli.sent == []


def test_without_a_ledger_there_is_nothing_to_check(cli, tmp_path, capsys):
    assert stall_alert.main(["--db", str(tmp_path / "none.db"), "--seen", str(tmp_path / "seen.json")]) == 0
    assert "nothing to check" in capsys.readouterr().out and cli.sent == []
