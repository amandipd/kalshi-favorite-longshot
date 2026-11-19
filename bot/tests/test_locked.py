"""Its records locked by another program (what stopped the live bot twice on Oct 10: "database is locked" at 6:00 pm
and again at 6:37 pm, each time with nothing else of the bot's running). A lock is waited out and retried, not a crash;
what couldn't be saved is kept and saved once the lock lets go; a lock that lasts LOCK_HALT seconds halts. Every lock
here is a real SQLite lock taken by a second connection, with the wait shortened so no test sleeps for long.

    python -m pytest tests/test_locked.py -q
"""
import sqlite3

import pytest

from kalshi_bot import bot
from kalshi_bot import ledger as ledger_module   # (the fixture below is named ledger)
from test_bot import ENTRY, W, FakeKalshi

NOW = W + 100   # minute 1 of a window: a step only settles and writes its heartbeat


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    """A live ledger whose lock waits are 50 ms, not 30 s, and the path to it for a second program to lock."""
    monkeypatch.setattr(bot, "STATE", str(tmp_path))
    monkeypatch.setattr(ledger_module, "DB_TIMEOUT", 0.05)
    bot._since.clear()
    path = str(tmp_path / "live-prod.db")
    db = bot.connect(path)
    bot.set_start(db, 100.0)
    return db, path


def holder(path, how):
    """Another program with the file: "write" holds it the way a writer does (nobody else may read or write);
    "read" holds it mid-read (others may read, but a commit has to wait)."""
    other = sqlite3.connect(path, timeout=0.05)
    if how == "write":
        other.execute("BEGIN EXCLUSIVE")
    else:
        other.execute("BEGIN")
        other.execute("SELECT * FROM meta").fetchall()
    return other


def saved(path, key="heartbeat"):
    """What another program reads from the file: only what the bot committed."""
    with sqlite3.connect(path) as db:
        row = db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row and float(row[0])


def test_its_ledger_waits_30_seconds_for_a_lock_not_sqlites_5(tmp_path):
    db = bot.connect(str(tmp_path / "live-prod.db"))
    assert ledger_module.DB_TIMEOUT == 30 and db.execute("PRAGMA busy_timeout").fetchone()[0] == 30_000


def test_the_lock_limits():
    assert bot.LOCK_HALT == 120     # 2 minutes: the Oct 10 locks each stopped it within a few seconds


@pytest.mark.parametrize("how", ["write", "read"])
def test_a_locked_ledger_is_retried_not_a_crash(ledger, capsys, how):
    db, path = ledger
    other = holder(path, how)
    b = bot.Bot(FakeKalshi(), db, live=True)
    b.run_step(NOW)                                   # no exception: a live bot used to stop here
    assert "records are locked" in capsys.readouterr().out and bot.halt_info() is None
    other.rollback()
    other.close()
    b.run_step(NOW + 3)
    assert saved(path) == NOW + 3 and b.locked_since is None


def test_what_a_locked_commit_couldnt_save_is_saved_when_the_lock_lets_go(ledger):
    """The entry minute: its bets went out and were noted, then the commit found the file held. They're kept, not
    lost, and saved by the next step's commit."""
    db, path = ledger
    other = holder(path, "read")
    fake = FakeKalshi()
    b = bot.Bot(fake, db, live=True)
    b.run_step(ENTRY)
    assert len(fake.orders) == 2
    other.rollback()
    other.close()
    b.run_step(ENTRY + 3)
    with sqlite3.connect(path) as fresh:
        assert sorted(r[0] for r in fresh.execute("SELECT ticker FROM bets")) == ["KXBTC15M-A", "KXGOLD15M-A"]
    assert len(fake.orders) == 2                       # and nothing went out twice


def test_a_lock_that_lasts_two_minutes_halts(ledger, capsys):
    db, path = ledger
    other = holder(path, "write")
    b = bot.Bot(FakeKalshi(), db, live=True)
    for t in (0, 30, 60, 119):
        b.run_step(NOW + t)
        assert bot.halt_info() is None
    b.run_step(NOW + 120)
    h = bot.halt_info()
    assert h["by"] == "auto" and "records have been locked for 2 minutes" in h["reason"]
    other.rollback()
    other.close()
    b.run_step(NOW + 123)                              # the lock let go: it saves again, and stays halted until --resume
    assert saved(path) == NOW + 123 and bot.halt_info() == h and b.locked_since is None


def test_the_two_minutes_start_over_after_any_step_that_saves(ledger):
    db, path = ledger
    b = bot.Bot(FakeKalshi(), db, live=True)
    other = holder(path, "write")
    b.run_step(NOW)
    b.run_step(NOW + 100)
    other.rollback()
    b.run_step(NOW + 110)                              # saved: the clock starts over
    other.execute("BEGIN EXCLUSIVE")
    b.run_step(NOW + 115)
    b.run_step(NOW + 200)
    assert bot.halt_info() is None                     # locked 85 s this time, 205 s since the first lock
    b.run_step(NOW + 235)
    assert bot.halt_info() is not None
    other.rollback()
    other.close()


def test_a_paper_account_waits_out_a_lock_but_never_halts_real_money(ledger):
    db, path = ledger
    other = holder(path, "write")
    b = bot.Bot(FakeKalshi(), db, live=False, halts=False)
    for t in (0, 60, 120, 600):
        b.run_step(NOW + t, carry_on=True)
    assert bot.halt_info() is None
    other.rollback()
    other.close()


def test_any_other_database_error_still_stops_a_live_or_dry_run(ledger, monkeypatch, capsys):
    db, _ = ledger
    b = bot.Bot(FakeKalshi(), db, live=True)

    def broken(now):
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(b, "step", broken)
    with pytest.raises(sqlite3.OperationalError):
        b.run_step(NOW)
    b.run_step(NOW, carry_on=True)                     # a paper account notes it and carries on, as before
    assert "error, carrying on: OperationalError('disk I/O error')" in capsys.readouterr().out


def test_the_live_loop_survives_a_lock(tmp_path, monkeypatch, capsys):
    """Through main(), as it runs: a lock on the first loop, gone by the second."""
    import types
    from test_cli import CliFake, KEYS
    monkeypatch.setattr(bot, "STATE", str(tmp_path))
    monkeypatch.setattr(ledger_module, "DB_TIMEOUT", 0.05)
    monkeypatch.setattr(bot, "load_env", lambda *a, **k: {"KALSHI_ENV": "demo", **KEYS})
    monkeypatch.setattr(bot, "Kalshi", lambda *a, **k: CliFake())
    path = str(tmp_path / "live-demo.db")
    bot.set_start(bot.connect(path), 100.0)
    other, loops, real_step = [], [], bot.Bot.step

    def step(self, now):
        if not loops:
            other.append(holder(path, "read"))       # another program opens the file as the first loop runs
        return real_step(self, now)

    def sleep(s):
        loops.append(s)
        if len(loops) == 1:
            other[0].rollback()
            other[0].close()
        else:
            raise KeyboardInterrupt

    monkeypatch.setattr(bot.Bot, "step", step)
    monkeypatch.setattr(bot, "time", types.SimpleNamespace(monotonic=lambda: 0.0, time=lambda: NOW, sleep=sleep))
    with pytest.raises(KeyboardInterrupt):
        bot.main(["--live"])
    assert len(loops) == 2 and "records are locked" in capsys.readouterr().out and saved(path) == NOW
