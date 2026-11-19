"""A dead man's switch for the bot: a ping to healthchecks.io each minute the bot is alive.

A systemd timer (deploy/kalshi-watchdog.timer) runs this once a minute. It reads the heartbeat the bot's
loop writes into its ledger (meta 'heartbeat', a unix time, every loop step), opened read only. If the heartbeat is
within FRESH seconds of now it pings HEALTHCHECK_URL; otherwise (stale, no ledger, no heartbeat, a ledger it can't
read) it pings HEALTHCHECK_URL + "/fail", healthchecks.io's way to say "down" at once. If the whole server dies, the
pings just stop and healthchecks.io raises the alarm when they're overdue: the bot's own alerts (notify.py) can't, as
they die with it.

HEALTHCHECK_URL comes from .env (KEY=VALUE lines, read as bot.load_env reads them); a real environment variable wins.
Unset or empty, the watchdog does nothing. It always exits 0, even when healthchecks.io can't be reached, so the timer
never flaps; the next minute's run is the retry.

    python -m kalshi_bot.watchdog       (from the bot/ folder)
"""
import os
import sqlite3
import time
from contextlib import closing
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent.parent   # the bot/ folder: its .env and state/
LEDGER = HERE / "state" / "live-prod.db"
ENV_FILE = HERE / ".env"
FRESH = 120        # seconds: a heartbeat this close to now means the bot's loop is going round
TIMEOUT = 10       # seconds to wait for healthchecks.io
LEDGER_WAIT = 5    # seconds to wait out the bot mid-commit before calling the ledger unreadable


def healthcheck_url(env_file=ENV_FILE, environ=os.environ):
    """HEALTHCHECK_URL from the real environment if it's set there (even empty), else from .env; "" if nowhere."""
    if "HEALTHCHECK_URL" in environ:
        return environ["HEALTHCHECK_URL"].strip()
    try:
        with open(env_file, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return ""
    url = ""
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            if k.strip() == "HEALTHCHECK_URL":
                url = v.strip().strip("\"'")
    return url


def heartbeat(ledger=LEDGER):
    """The bot's last heartbeat (a unix time) from its ledger, opened read only; None if there's none to read."""
    try:
        with closing(sqlite3.connect(Path(ledger).as_uri() + "?mode=ro", uri=True, timeout=LEDGER_WAIT)) as db:
            row = db.execute("SELECT value FROM meta WHERE key='heartbeat'").fetchone()
        return float(row[0]) if row else None
    except (sqlite3.Error, TypeError, ValueError):
        return None


def main(get=requests.get, clock=time.time, environ=os.environ, env_file=ENV_FILE, ledger=LEDGER):
    """One look and one ping. Always 0. The address isn't printed: anyone who has it can ping the check."""
    url = healthcheck_url(env_file, environ).rstrip("/")
    if not url:
        print("HEALTHCHECK_URL isn't set: nothing to ping")
        return 0
    beat = heartbeat(ledger)
    age = None if beat is None else clock() - beat
    alive = age is not None and abs(age) < FRESH     # NaN and infinity aren't; a clock stepped back is, for FRESH s
    seen = f"{'ok' if alive else 'FAIL'}: " + ("no heartbeat" if age is None else f"heartbeat {age:.0f} s old")
    try:
        answer = get(url if alive else url + "/fail", timeout=TIMEOUT)
        print(f"{seen}; healthchecks.io answered HTTP {answer.status_code}")
    except requests.RequestException as e:   # its message can hold the address: only its kind is printed
        print(f"{seen}; healthchecks.io unreachable ({type(e).__name__})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
