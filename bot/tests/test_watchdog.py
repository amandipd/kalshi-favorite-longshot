"""watchdog.py: the server's dead man's switch. A systemd timer runs it each minute; it pings healthchecks.io while the
bot's heartbeat is fresh, and pings its "/fail" address when it isn't.

Every test hands it a fake GET that records the address and timeout, and a fixed clock. The ledger is a real bot
ledger (bot.connect) in a throwaway folder, and is checked to be read only: same bytes, nothing made beside it, and a
missing one never created. Nothing here touches the network.

    python -m pytest tests/test_watchdog.py -q
"""
import inspect
import os
import runpy
import sqlite3
import threading
import time

import pytest
import requests

from kalshi_bot import bot
from kalshi_bot import watchdog
from layout import BOT

NOW = 1_791_660_000.0
URL = "https://hc-ping.com/00000000-test-check"


class Get:
    """A stand-in for requests.get: records each call, answers with a status, or raises what it's given."""
    def __init__(self, status=200, error=None):
        self.calls, self.status, self.error = [], status, error

    def __call__(self, url, timeout=None):
        self.calls.append((url, timeout))
        if self.error:
            raise self.error
        return type("Answer", (), {"status_code": self.status})()


@pytest.fixture
def ledger(tmp_path):
    """A real bot ledger with the bot's tables and no heartbeat yet."""
    path = tmp_path / "state" / "live-prod.db"
    db = bot.connect(str(path))
    db.commit()
    db.close()
    return path


def beat(path, value):
    db = sqlite3.connect(path)
    db.execute("INSERT OR REPLACE INTO meta VALUES ('heartbeat', ?)", (value,))
    db.commit()
    db.close()


def run(ledger, get, now=NOW, environ=None, env_file=None):
    return watchdog.main(get=get, clock=lambda: now, environ={"HEALTHCHECK_URL": URL} if environ is None else environ,
                         env_file=env_file or ledger.parent / "no.env", ledger=ledger)


# ------------------------------------------------------------------ where it looks, by default
def test_it_reads_the_live_ledger_and_the_env_file_beside_it():
    here = BOT                                         # the bot/ folder, one up from the package
    assert str(watchdog.LEDGER) == os.path.join(here, "state", "live-prod.db")
    assert str(watchdog.ENV_FILE) == os.path.join(here, ".env")
    assert (watchdog.FRESH, watchdog.TIMEOUT) == (120, 10)


def test_by_default_it_uses_the_real_network_and_clock():
    p = inspect.signature(watchdog.main).parameters
    assert p["get"].default is requests.get and p["clock"].default is time.time and p["environ"].default is os.environ
    assert p["env_file"].default == watchdog.ENV_FILE and p["ledger"].default == watchdog.LEDGER


# ------------------------------------------------------------------ the address
def test_the_address_comes_from_the_env_file_as_the_bot_reads_it(tmp_path):
    env = tmp_path / ".env"
    env.write_text("# a comment\n\nKALSHI_ENV=prod\nnot a setting\n  HEALTHCHECK_URL = 'https://hc-ping.com/abc'  \n",
                   encoding="utf-8")
    assert watchdog.healthcheck_url(env, {}) == "https://hc-ping.com/abc"


def test_the_last_line_wins_and_a_commented_one_is_ignored(tmp_path):
    env = tmp_path / ".env"
    env.write_text('HEALTHCHECK_URL="https://one"\n# HEALTHCHECK_URL=https://commented\nHEALTHCHECK_URL=https://two\n',
                   encoding="utf-8")
    assert watchdog.healthcheck_url(env, {}) == "https://two"


def test_a_real_environment_variable_wins_even_an_empty_one(tmp_path):
    env = tmp_path / ".env"
    env.write_text("HEALTHCHECK_URL=https://from-file\n", encoding="utf-8")
    assert watchdog.healthcheck_url(env, {"HEALTHCHECK_URL": " https://from-env "}) == "https://from-env"
    assert watchdog.healthcheck_url(env, {"HEALTHCHECK_URL": ""}) == ""


def test_no_address_anywhere_is_empty(tmp_path):
    assert watchdog.healthcheck_url(tmp_path / "missing.env", {}) == ""
    (tmp_path / ".env").write_text("KALSHI_ENV=prod\n", encoding="utf-8")
    assert watchdog.healthcheck_url(tmp_path / ".env", {}) == ""


@pytest.mark.parametrize("environ", [{}, {"HEALTHCHECK_URL": ""}, {"HEALTHCHECK_URL": "   "}])
def test_without_an_address_it_does_nothing_and_exits_0(ledger, capsys, environ):
    beat(ledger, NOW)
    get = Get()
    assert run(ledger, get, environ=environ) == 0
    assert get.calls == [] and "nothing to ping" in capsys.readouterr().out


def test_the_address_from_the_env_file_is_pinged(ledger, tmp_path):
    env = tmp_path / ".env"
    env.write_text(f"HEALTHCHECK_URL={URL}\n", encoding="utf-8")
    beat(ledger, NOW - 5)
    get = Get()
    assert run(ledger, get, environ={}, env_file=env) == 0
    assert get.calls == [(URL, 10)]


def test_a_trailing_slash_doesnt_double_up_before_fail(ledger):
    get = Get()
    assert run(ledger, get, environ={"HEALTHCHECK_URL": URL + "/"}) == 0
    assert get.calls == [(URL + "/fail", 10)]


# ------------------------------------------------------------------ the heartbeat
def test_the_heartbeat_is_read_from_the_bots_own_ledger(ledger):
    db = bot.connect(str(ledger))
    bot.set_meta(db, "heartbeat", NOW - 7.25)    # as Bot.step writes it
    db.commit()
    db.close()
    assert watchdog.heartbeat(ledger) == NOW - 7.25


def test_no_heartbeat_to_read_is_none(ledger, tmp_path):
    assert watchdog.heartbeat(ledger) is None                       # a ledger the bot hasn't looped on yet
    assert watchdog.heartbeat(tmp_path / "nowhere.db") is None      # no ledger at all
    assert not (tmp_path / "nowhere.db").exists()                   # and it isn't made
    empty = tmp_path / "empty.db"
    empty.write_bytes(b"")
    assert watchdog.heartbeat(empty) is None                        # no tables
    junk = tmp_path / "junk.db"
    junk.write_bytes(b"not a database" * 100)
    assert watchdog.heartbeat(junk) is None                         # not SQLite
    beat(ledger, "soon")
    assert watchdog.heartbeat(ledger) is None                       # not a number
    beat(ledger, None)
    assert watchdog.heartbeat(ledger) is None                       # NULL
    assert watchdog.heartbeat("relative.db") is None                # a path that isn't a file URI


def test_it_waits_out_the_bot_mid_commit(ledger):
    beat(ledger, NOW)
    writer = sqlite3.connect(ledger, check_same_thread=False)
    writer.execute("BEGIN EXCLUSIVE")              # the bot committing: readers have to wait
    later = threading.Timer(0.3, writer.commit)
    later.start()
    try:
        assert watchdog.heartbeat(ledger) == NOW
    finally:
        later.join()
        writer.close()


def test_it_never_writes_to_the_ledger(ledger):
    beat(ledger, NOW - 3)
    before, stamp, files = ledger.read_bytes(), ledger.stat().st_mtime_ns, sorted(os.listdir(ledger.parent))
    for now in (NOW, NOW + 600):
        assert run(ledger, Get(), now=now) == 0
    assert ledger.read_bytes() == before and ledger.stat().st_mtime_ns == stamp
    assert sorted(os.listdir(ledger.parent)) == files


# ------------------------------------------------------------------ the ping
@pytest.mark.parametrize("age, path", [(0, ""), (3, ""), (119.9, ""), (-30, ""),
                                       (120, "/fail"), (121, "/fail"), (3600, "/fail"), (-120, "/fail")])
def test_a_fresh_heartbeat_pings_and_a_stale_one_fails(ledger, capsys, age, path):
    beat(ledger, NOW - age)
    get = Get()
    assert run(ledger, get) == 0
    assert get.calls == [(URL + path, 10)]
    out = capsys.readouterr().out
    assert out.startswith("ok:" if path == "" else "FAIL:") and f"heartbeat {age:.0f} s old" in out
    assert "HTTP 200" in out and URL not in out                       # the address is a secret of sorts: not logged


def test_no_ledger_or_no_heartbeat_fails(ledger, tmp_path, capsys):
    for where in (ledger, tmp_path / "nowhere.db"):   # a ledger with no heartbeat yet, then no ledger at all
        get = Get()
        assert run(where, get) == 0
        assert get.calls == [(URL + "/fail", 10)]
        assert "FAIL: no heartbeat" in capsys.readouterr().out


@pytest.mark.parametrize("value", ["nan", "inf", "-inf"])
def test_a_heartbeat_that_isnt_a_real_time_fails(ledger, value):
    beat(ledger, value)
    get = Get()
    assert run(ledger, get) == 0
    assert get.calls == [(URL + "/fail", 10)]


def test_healthchecks_answering_an_error_is_still_exit_0(ledger, capsys):
    beat(ledger, NOW)
    assert run(ledger, Get(status=503)) == 0
    assert "HTTP 503" in capsys.readouterr().out


@pytest.mark.parametrize("error", [requests.ConnectionError(f"Max retries exceeded with url: {URL}"),
                                   requests.Timeout("read timed out"), requests.exceptions.InvalidURL("bad")])
def test_a_network_error_is_caught_and_exits_0(ledger, capsys, error):
    beat(ledger, NOW)
    get = Get(error=error)
    assert run(ledger, get) == 0
    assert get.calls == [(URL, 10)]                                   # one try: the next minute's run is the retry
    out = capsys.readouterr().out
    assert "unreachable" in out and type(error).__name__ in out and URL not in out


def test_run_as_a_script_it_exits_0(monkeypatch):
    monkeypatch.setenv("HEALTHCHECK_URL", "")      # set and empty: wins over any .env, so nothing is pinged
    monkeypatch.setattr(requests, "get", Get(error=AssertionError("no network in tests")))
    with pytest.raises(SystemExit) as e:
        runpy.run_path(watchdog.__file__, run_name="__main__")
    assert e.value.code == 0
