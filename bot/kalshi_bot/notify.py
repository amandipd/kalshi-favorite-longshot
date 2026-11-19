"""Phone alerts through ntfy (ntfy.sh): a message when one of the bot's bets loses, so you can open that market and
look, when the bot halts, and when it stops running or starts again.

It runs beside the bot and only reads its records: the ledger (state/<mode>.db, opened read-only), with its losses and
the heartbeat the bot's loop writes, and the halt file (bot.halt_info()). So it needs no change to the bot and no
restart, and can never write to or lock what the bot trades from. Every NOTIFY_EVERY seconds it sends each loss and
halt it hasn't sent before, and a stop or start when the heartbeat goes quiet for STOPPED_AFTER seconds or comes back.
It remembers what it sent, losses by market (tickers are never reused; bet ids start again in a fresh ledger), in its
own file per account (memory_path). On its first look it only takes note of what's already there, so old news doesn't
arrive as a flood. Something is marked as sent once ntfy accepts it, so a failed send goes out on the next check; a
memory it couldn't save is saved on the next check, and nothing is sent twice meanwhile. It runs unattended, so a check
that fails (the ledger busy mid-commit, the halt file half-written, anything else) is logged and the next one goes on.
After the PC sleeps, the bot gets one check to beat again before it's called stopped. Only one notifier runs at a time
(it holds a localhost port), so no alert comes twice.

Install the ntfy app, subscribe to your topic on ntfy.sh, and put the topic in .env (NTFY_TOPIC=...). On ntfy's free
server the topic name is the only lock, so make it long and random.
    python -m kalshi_bot.notify                    # keep checking (from the bot/ folder)
    python -m kalshi_bot.notify --test             # send one message to see it arrive
    python -m kalshi_bot.notify --once             # one check (the first only takes note of what's there)
    pythonw -m kalshi_bot.notify --log state/notify.log    # no console: what it says goes to the file
"""
import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import requests

from kalshi_bot import bot

NOTIFY_EVERY = 5               # seconds between checks: an alert comes about this long after the bot settles a loss
STOPPED_AFTER = 60             # seconds without a heartbeat before the bot counts as stopped (the dashboard says 30)
LEDGER_WAIT = 1                # seconds to wait on a ledger the bot is committing to, well inside one check
NOTIFY_PORT = 47863            # the localhost port a running notifier holds, so a second one stops at once
SERVER = "https://ntfy.sh"
PREFIX = "Kalshi · "   # every title starts with this: the phone may get other servers' alerts too
# What reaches the phone. Since Oct 27, 2026: a lost bet and nothing else. Every other alert is still built, still
# logged and still tested; this line is the whole policy, so putting one back is one word.
#   "loss"  a bet settled against us          "halt"  the bot stopped itself
#   "run"   the loop stopped or came back     "stall" the outside alarm (stall_alert.py)
ALERTS = ("loss",)


# ------------------------------------------------------------------ the words, as the dashboard has them
def kalshi_url(ticker):
    """The 15-minute window's page on Kalshi (dashboard.html's kalshiUrl): /markets/{series}/{slug}/{event}."""
    p, s = ticker.split("-"), ticker.split("-")[0].lower()
    return f"https://kalshi.com/markets/{s}" if len(p) < 2 else f"https://kalshi.com/markets/{s}/{s}/{'-'.join(p[:2]).lower()}"


def title(series):
    """KXBTC15M -> 'BTC 15 min', as the page's sym() and title()."""
    s = (series or "").removeprefix("KX")
    return s.removesuffix("15M") + " 15 min"


def cents(p):
    """As the page's cents(): whole cents when within 0.05, else one decimal rounded as toFixed does (the exact value,
    ties up)."""
    c = p * 100
    if abs(c - round(c)) < 0.05:
        return f"{round(c)}¢"
    return f"{Decimal(c).quantize(Decimal('0.1'), ROUND_HALF_UP)}¢"


def dollars(v):
    """As the page's money(): a minus unless it rounds to nothing, cents rounded as toLocaleString does (the shortest
    decimal for the number, ties away from zero), thousands separated."""
    amount = Decimal(repr(abs(v))).quantize(Decimal("0.01"), ROUND_HALF_UP)
    return ("−$" if v < 0 and not abs(v) < 0.005 else "$") + f"{amount:,.2f}"


def count(n):
    """Contracts as the page writes them (${b.contracts}): 16, 0.03, 1234567, in full."""
    return str(int(n)) if n == int(n) else repr(n)


def clock(t):
    """A time of day in this machine's zone, as the dashboard shows times: '1:20 PM'."""
    return datetime.fromtimestamp(t).strftime("%I:%M %p").lstrip("0")


def loss_message(b):
    return {"title": f"Lost: {title(b['series'])}",
            "message": f"{b['side'].upper()} at {cents(b['price'])} × {count(b['contracts'])} · {dollars(b['pnl'])} · settled {clock(b['settled_ts'])}",
            "click": kalshi_url(b["ticker"]), "tags": ["chart_with_downwards_trend"], "priority": 3}


def halt_message(h):
    return {"title": "Bot halted", "message": f"{h['reason']} · {clock(bot.ts(h['ts']))} · no new orders until python bot.py --resume",
            "tags": ["warning"], "priority": 4}


def stopped_message(hb):
    return {"title": "Bot stopped", "message": f"no heartbeat{'' if hb is None else ' since ' + clock(hb)} · nothing is being bought",
            "tags": ["stop_sign"], "priority": 4}


def running_message(hb):
    return {"title": "Bot running", "message": f"heartbeat at {clock(hb)} · back to buying", "tags": ["white_check_mark"], "priority": 3}


def log(text):
    print(f"{bot.iso(time.time())} {text}", flush=True)


# ------------------------------------------------------------------ sending, and remembering what was sent
def send(cfg, msg, kind="loss"):
    """One message to the topic, as JSON so ¢ and − come through. True once ntfy has it. Its title is marked PREFIX
    (unless it already says Kalshi), on a copy: the caller's message is left as it was.

    kind says which alert this is (see ALERTS). One that isn't in ALERTS is dropped and counts as sent, so the
    caller writes it down and doesn't try it again every check. "test" always goes: it is someone asking whether
    ntfy works at all."""
    if kind != "test" and kind not in ALERTS:
        log(f"not sent ({kind} is off): {msg.get('title')}")
        return True
    if msg.get("title") and not msg["title"].startswith("Kalshi"):
        msg = {**msg, "title": PREFIX + msg["title"]}
    try:
        r = requests.post(cfg.get("NTFY_SERVER", SERVER).rstrip("/"), json={"topic": cfg["NTFY_TOPIC"], **msg}, timeout=10)
    except requests.RequestException as e:
        log(f"couldn't reach ntfy: {e}")
        return False
    if not 200 <= r.status_code < 300:
        log(f"ntfy said HTTP {r.status_code}")
        return False
    log(f"sent: {msg.get('title')}")
    return True


def memory_path(mode):
    """Each account remembers on its own: state/notify.json for the real-money one, notify-<mode>.json for others."""
    return os.path.join(bot.STATE, "notify.json" if mode == "live-prod" else f"notify-{mode}.json")


def load_sent(path):
    """What was sent before, or None if never run, unreadable or not the shape check() keeps: the next check then
    takes note instead of crashing or flooding. A memory from before the heartbeat alerts has no "running"."""
    try:
        with open(path, encoding="utf-8") as fh:
            sent = json.load(fh)
    except (OSError, ValueError):
        return None
    ok = (isinstance(sent, dict) and isinstance(sent.get("lost"), list) and all(isinstance(t, str) for t in sent["lost"])
          and "halt" in sent and (sent["halt"] is None or isinstance(sent["halt"], str))
          and (sent.get("running") is None or isinstance(sent["running"], bool)))
    return sent if ok else None


def save_sent(path, sent):
    with open(path + ".tmp", "w", encoding="utf-8") as fh:
        json.dump(sent, fh)
    os.replace(path + ".tmp", path)


def ledger(mode, query):
    """The rows `query` gives from the bot's ledger, read without ever writing; None before the bot has a ledger. A
    ledger the bot is mid-commit on, or one it hasn't made its tables in yet, raises: the check is tried again."""
    path = os.path.join(bot.STATE, mode + ".db")
    if not os.path.exists(path):
        return None
    db = sqlite3.connect(Path(path).as_uri() + "?mode=ro", uri=True, timeout=LEDGER_WAIT)
    db.row_factory = sqlite3.Row
    try:
        return db.execute(query).fetchall()
    finally:
        db.close()


def losses(mode):
    """The ledger's lost bets, oldest settlement first."""
    return ledger(mode, "SELECT * FROM bets WHERE status='lost' ORDER BY settled_ts, id") or []


def heartbeat(mode):
    """When the bot's loop last went round (bot.Bot.step() writes it every loop), or None if it never has."""
    rows = ledger(mode, "SELECT value FROM meta WHERE key='heartbeat'")
    return float(rows[0]["value"]) if rows else None


def check(cfg, mode, sent, now=None, just_woke=False):
    """One look at the records: send each loss and halt not sent before, and a stop or start, and return what has
    been sent now. With `sent` None (the first look) it sends nothing and just takes note. `just_woke` (the PC slept):
    a quiet heartbeat isn't called a stop yet, as the bot gets a check to beat again."""
    now = time.time() if now is None else now
    lost, h, hb = losses(mode), bot.halt_info(), heartbeat(mode)
    alive = hb is not None and now - hb < STOPPED_AFTER
    if sent is None:
        return {"lost": [b["ticker"] for b in lost], "halt": h["ts"] if h else None, "running": alive}
    sent = {"lost": list(sent["lost"]), "halt": sent["halt"], "running": sent.get("running")}
    for b in lost:
        if b["ticker"] not in sent["lost"] and send(cfg, loss_message(b)):
            sent["lost"].append(b["ticker"])
    if h and h["ts"] != sent["halt"] and send(cfg, halt_message(h), "halt"):
        sent["halt"] = h["ts"]
    if sent["running"] is None:                        # a memory from before the heartbeat alerts: take note quietly
        sent["running"] = alive
    elif sent["running"] and not alive and not just_woke:
        if send(cfg, stopped_message(hb), "run"):
            sent["running"] = False
    elif not sent["running"] and alive and send(cfg, running_message(hb), "run"):
        sent["running"] = True
    return sent


# ------------------------------------------------------------------ the command line
def take_lock():
    """Bind the notifier's localhost port, or None if another notifier has it (bot.hold_port, the bot's own lock)."""
    return bot.hold_port(NOTIFY_PORT)


def run(args):
    cfg = {**bot.load_env(), **{k: v for k, v in os.environ.items() if k.startswith("NTFY_")}}
    if not cfg.get("NTFY_TOPIC"):
        print("No NTFY_TOPIC: add NTFY_TOPIC=<a long random name> to .env, and subscribe to it in the ntfy app.")
        return 2
    if args.test:
        what = {"loss": "when one of the bot's bets loses", "halt": "when the bot halts",
                "run": "when it stops or starts", "stall": "when the outside alarm sees it stuck"}
        on = ", ".join(what[k] for k in ALERTS if k in what) or "nothing: every alert is switched off (ALERTS)"
        ok = send(cfg, {"title": "Kalshi alerts are on", "tags": ["white_check_mark"],
                        "message": f"You'll get a message here {on}."}, "test")
        print("Test message sent." if ok else "Test message couldn't be sent.")
        return 0 if ok else 1
    lock = take_lock()
    if lock is None:
        print("another notifier is already running, so this one stops: it would send every alert twice")
        return 0
    path = memory_path(args.mode)
    sent, unsaved, last = load_sent(path), False, None
    try:
        while True:
            started = time.monotonic()
            woke, last = last is not None and started - last > 3 * NOTIFY_EVERY, started
            try:
                now, ok = check(cfg, args.mode, sent, now=time.time(), just_woke=woke), True
            except Exception as e:                     # unattended: say what went wrong, and look again next time
                log(f"check failed: {e}")
                now, ok = sent, False
            if ok and (now != sent or unsaved):
                sent, unsaved = now, True              # what was sent counts even if saving it fails: never twice
                try:
                    save_sent(path, sent)
                    unsaved = False
                except OSError as e:
                    log(f"couldn't save {path}, will try again: {e}")
            if args.once:
                return 0 if ok and not unsaved else 1
            time.sleep(NOTIFY_EVERY)
    except KeyboardInterrupt:
        print("stopped", flush=True)
        return 0
    finally:
        lock.close()


def main(argv=None):
    a = argparse.ArgumentParser(description="Phone alerts through ntfy when a bet loses, the bot halts, or it stops or starts.")
    a.add_argument("--mode", default="live-prod", help="whose ledger to watch (default: the real-money one)")
    a.add_argument("--test", action="store_true", help="send one message and stop")
    a.add_argument("--once", action="store_true", help="check once and stop")
    a.add_argument("--log", help="append what it says to this file (for pythonw.exe, which has no console)")
    args = a.parse_args(argv)
    if not args.log:
        return run(args)
    console, sys.stdout = sys.stdout, open(args.log, "a", encoding="utf-8", buffering=1)
    try:
        return run(args)
    finally:
        out, sys.stdout = sys.stdout, console
        out.close()


if __name__ == "__main__":
    raise SystemExit(main())
