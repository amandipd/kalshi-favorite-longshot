"""A phone alert when the live bot stops working while still looking alive.

On Oct 24, 2026 Kalshi's `status=open` market filter matched nothing for about seven hours: the
bot's listing call came back 200 with an empty list and no error, so `listed()` returned nothing, `step()`
took its "nothing listed, try again next loop" branch, and the bot placed no bets for 27 windows. Nothing
caught it: the process was up, `meta.heartbeat` was fresh, no halt was set, the error log was empty, and the
healthchecks.io watchdog only ever proved the process was alive. The filter then started working again on
its own, with no restart -- it was never retired, which is the point: a dependency can fail for hours and
come back, and the only thing that makes that visible is watching the bot's output. The same silent gap had
already cost 6 windows on Oct 18.

This runs OUTSIDE bot.py on purpose. A tripwire inside the bot's own loop shares the loop's faults: if the
code that lists markets is broken, the code that would notice may be broken too. So this reads the bot's
records instead of trusting its code, read-only, and never writes to the ledger.

The signal is `decisions`, not `bets`. The bot writes a decision row for every market it looks at, every
window, even when it skips them all, so no decisions at all means it has stopped looking. A quiet market
can legitimately buy nothing for an hour (the longest real gap on record is 4 windows), so bets get a much
looser threshold of their own.

It stays quiet when the bot is halted (notify.py already alerts on halts) and during Kalshi's scheduled
Thursday 3-5 am ET maintenance, when there are legitimately no markets to list. A stopped loop is reported
even then, because maintenance does not explain the bot's own loop stopping.

    python -m kalshi_bot.stall_alert                 # check once: for a systemd timer or cron, every 5-15 min
    python -m kalshi_bot.stall_alert --dry-run       # say what it would send, send nothing
    python -m kalshi_bot.stall_alert --windows 12    # a looser stall threshold (default 8 windows, 2 hours)
"""
import argparse
import json
import os
import sqlite3
import time
from pathlib import Path

from kalshi_bot import bot, notify

HERE = bot.HERE   # the bot/ folder: its .env and state/

WINDOW = 900.0             # Kalshi's 15-minute window
STALL_WINDOWS = 8          # no market looked at for this many windows running: 2 hours, well past the 4-window
                           # longest real gap, so a quiet market never trips it
BET_WINDOWS = 24           # ... and nothing bought for this many (6 hours): a weaker signal, since the 92c
                           # floor can legitimately skip everything for a long stretch
HEARTBEAT_MAX = 300.0      # the bot writes meta.heartbeat every loop (seconds, so 5 minutes is many loops)
LEDGER_WAIT = 30.0         # the ledger can be held by a backup or a virus scanner: wait, as the bot does

# Its own memory of what it last said, so a standing fault is reported once. Beside state/, never inside it:
# state/ is the bot's own. (deploy/kalshi-stall-alert.service passes --seen to keep it outside the code folder.)
SEEN = os.path.join(HERE, "stall_alert.json")


def config(env=None):
    """The ntfy settings: .env beside the code, with NTFY_* from the environment on top, as notify.py reads
    them. The topic is never in this file: it is read at run time."""
    base = dict(env) if env is not None else bot.load_env()
    return {**base, **{k: v for k, v in os.environ.items() if k.startswith("NTFY_")}}


def open_ledger(path):
    """The bot's ledger, read-only: a bug here can never touch real trading."""
    db = sqlite3.connect(Path(path).as_uri() + "?mode=ro", uri=True, timeout=LEDGER_WAIT)
    db.row_factory = sqlite3.Row
    return db


def _one(db, sql):
    return db.execute(sql).fetchone()[0]


def look(db, now, halted=None, windows=STALL_WINDOWS, bet_windows=BET_WINDOWS, heartbeat_max=HEARTBEAT_MAX):
    """What is wrong, as {kind, title, message, priority}, or None when there is nothing to say.

    kinds: "dead" (the loop has stopped writing its heartbeat), "stalled" (the loop runs but has looked at
    no market for `windows` windows: the Oct 24 fault), "quiet" (it is looking but has bought nothing for
    `bet_windows`). A halt is notify.py's to report, and an untouched ledger has nothing to judge.
    """
    if halted:
        return None   # notify.py already alerts on halts, and a halted bot is meant to be idle

    beat = bot.get_meta(db, "heartbeat")
    last_decision = _one(db, "SELECT MAX(ts) FROM decisions")
    last_bet = _one(db, "SELECT MAX(placed_ts) FROM bets")
    if beat is None and last_decision is None:
        return None   # it has never run: nothing to judge

    if beat is not None and now - float(beat) > heartbeat_max:
        return {"kind": "dead", "title": "Bot loop stopped",
                "message": f"no heartbeat for {(now - float(beat)) / 60:.0f} min"
                           f" · last looked at a market {_ago(last_decision, now)}",
                "tags": ["rotating_light"], "priority": 5}

    # Below here the loop is running, so an empty window is about what Kalshi is giving it.
    if bot.scheduled_maintenance(now):
        return None   # Kalshi pauses Thursdays 3-5 am ET and lists nothing: an empty window is expected

    if last_decision is not None and now - last_decision > windows * WINDOW:
        missed = int((now - last_decision) / WINDOW)
        return {"kind": "stalled", "title": "Bot not looking at markets",
                "message": f"no market looked at for {missed} windows ({(now - last_decision) / 3600:.1f} h)"
                           f" · the loop is alive, so this is not a crash · last bet {_ago(last_bet, now)}",
                "tags": ["rotating_light"], "priority": 5}

    if last_bet is not None and now - last_bet > bet_windows * WINDOW:
        return {"kind": "quiet", "title": "Bot buying nothing",
                "message": f"looking at markets but nothing bought for {(now - last_bet) / 3600:.1f} h"
                           f" ({int((now - last_bet) / WINDOW)} windows)",
                "tags": ["warning"], "priority": 4}
    return None


def _ago(when, now):
    return "never" if when is None else f"{(now - when) / 3600:.1f} h ago"


def _read_seen(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _write_seen(path, data):
    """Best effort: a memory it cannot save means it may repeat itself, which is far better than going quiet."""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except OSError as e:
        notify.log(f"couldn't save what was sent ({e}); it may be sent again")


def check(cfg, db, now, seen_path=SEEN, dry_run=False, **kw):
    """Look, and send at most one message: a fault the last run did not report, or a recovery. True if it
    sent something. A push ntfy refused is not remembered, so the next run tries again. A fault already
    reported stays remembered through a halt and through maintenance, so neither reads as a recovery."""
    found = look(db, now, **kw)
    seen = _read_seen(seen_path)
    was = seen.get("kind")

    if found is None:
        # None means three different things: nothing is wrong, the bot is halted, or Kalshi is in its
        # Thursday maintenance. Only the first is a recovery. Saying "working again" while the fault still
        # stands, and forgetting it, is worse than saying nothing: the next run would start the count again.
        if not was or kw.get("halted") or bot.scheduled_maintenance(now):
            return False
        msg = {"title": "Bot working again", "message": "it is looking at markets again"
               f" · it had been {was} since {notify.clock(seen.get('since', now))}",
               "tags": ["white_check_mark"], "priority": 3}
        if dry_run:
            notify.log(f"would send: {msg['title']} - {msg['message']}")
            return True
        if not notify.send(cfg, msg, "stall"):
            return False
        _write_seen(seen_path, {})
        return True

    if was == found["kind"]:
        return False   # already said so; say it once
    if dry_run:
        notify.log(f"would send: {found['title']} - {found['message']}")
        return True
    if not notify.send(cfg, {k: v for k, v in found.items() if k != "kind"}, "stall"):
        return False
    _write_seen(seen_path, {"kind": found["kind"], "since": now})
    return True


def main(argv=None):
    ap = argparse.ArgumentParser(description="Alert by ntfy when the live bot stops working while looking alive.")
    ap.add_argument("--db", default=os.path.join(HERE, "state", "live-prod.db"), help="the bot's ledger (read-only)")
    ap.add_argument("--windows", type=int, default=STALL_WINDOWS, help=f"windows with no market looked at (default {STALL_WINDOWS})")
    ap.add_argument("--bet-windows", type=int, default=BET_WINDOWS, help=f"windows with nothing bought (default {BET_WINDOWS})")
    ap.add_argument("--heartbeat-max", type=float, default=HEARTBEAT_MAX, help=f"seconds without a heartbeat (default {HEARTBEAT_MAX:.0f})")
    ap.add_argument("--seen", default=SEEN, help="where it remembers what it last sent")
    ap.add_argument("--dry-run", action="store_true", help="say what it would send, send nothing")
    a = ap.parse_args(argv)

    cfg = config()
    if not a.dry_run and not cfg.get("NTFY_TOPIC"):
        print("No NTFY_TOPIC: add NTFY_TOPIC=<a long random name> to .env, and subscribe to it in the ntfy app.")
        return 2
    if not os.path.exists(a.db):
        print(f"no ledger at {a.db}: nothing to check")
        return 0
    now = time.time()
    db = open_ledger(a.db)
    found = look(db, now, halted=bot.halt_info(), windows=a.windows,
                 bet_windows=a.bet_windows, heartbeat_max=a.heartbeat_max)
    print(f"{bot.iso(now)} {'OK' if found is None else found['kind'] + ': ' + found['message']}")
    check(cfg, db, now, a.seen, dry_run=a.dry_run, halted=bot.halt_info(),
          windows=a.windows, bet_windows=a.bet_windows, heartbeat_max=a.heartbeat_max)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
