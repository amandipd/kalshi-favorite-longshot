"""Is it safe to restart the live bot right now, and if not, wait until it is.

    python deploy/safe_restart.py --check            # say yes or no; exit 1 if it is not safe
    python deploy/safe_restart.py && sudo systemctl restart kalshi-bot      # wait, then restart
    python deploy/safe_restart.py --at 1793032672 --dry-run                 # what it would say at that moment

The usual rule is to avoid :08-:09, :23-:24, :38-:39 and :53-:54 past the hour. Those are the entry minutes.
Written as minutes that rule is easy to check by hand and easy to get wrong, because a 15-minute window does
not care about the clock's minutes. On Oct 26, 2026 a deploy restarted the bot at :37:52 against a minute-only
check -- :37 is none of the four -- which was eight seconds before the entry mark. The window survived only
because the new process happened to be ready in time.

So this works in seconds into the 15-minute window, and opens the unsafe band before the prep rather than at
the mark:

    450   a fast window's prep reads the window's minute-by-minute prices (fast_entry.PREP)
    480   the mark, where every order goes out at once (bot.MINUTE * 60)
    525   the last moment an entry may still happen (+ bot.GRACE)
    600   the end of that rule's own window, minute 9

A bot that has just started has to take the one-bot lock, read Kalshi's exchange status and load its catalog
before it can prep a window, so the band opens STARTUP seconds ahead of the prep. The one measurement we have
says it is ready in well under that: restarted at :37:52 on Oct 26, it caught the :38:00 entry in full. STARTUP
is deliberately much larger than that, because the cost of being wrong is a missed window and the cost of being
careful is waiting a couple of minutes.

The timings are copied here rather than imported: a script in deploy/ runs with deploy/ on its path, not the
folder above it, as probe_latency.py does. tests/test_safe_restart.py imports the real bot and fails if any of
these copies drifts from it.
"""
import argparse
import time

WINDOW = 900        # Kalshi's 15-minute window
PREP = 450          # fast_entry.PREP: a fast window's prep, seconds into the window
MARK = 480          # bot.MINUTE * 60: the entry mark
GRACE = 45          # bot.GRACE: how long after the mark an entry may still happen
STARTUP = 60        # headroom for a fresh bot to be ready before the prep

UNSAFE_FROM = PREP - STARTUP        # 390
UNSAFE_TO = 600                     # through minute 9, so that rule's own window is covered end to end


def into_window(now):
    """Seconds into the current 15-minute window."""
    return int(now) % WINDOW


def safe(now):
    """True when a restart started at `now` cannot disturb a window's prep or its entry."""
    return not UNSAFE_FROM <= into_window(now) <= UNSAFE_TO


def wait_for(now):
    """Seconds to wait before restarting: 0 when it is already safe, else just past the band."""
    return 0 if safe(now) else UNSAFE_TO + 1 - into_window(now)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Wait until it is safe to restart the live bot.")
    ap.add_argument("--check", action="store_true", help="say whether now is safe and exit; 1 if it is not")
    ap.add_argument("--at", type=float, help="judge this epoch time instead of now")
    ap.add_argument("--dry-run", action="store_true", help="say how long it would wait, and don't wait")
    a = ap.parse_args(argv)
    now = a.at if a.at is not None else time.time()
    into = into_window(now)
    if a.check:
        print(f"safe to restart ({into}s into the window)" if safe(now) else
              f"NOT safe to restart: {into}s into the window, inside {UNSAFE_FROM}-{UNSAFE_TO}s"
              f" (the prep at {PREP}s, the mark at {MARK}s, entries until {MARK + GRACE}s)")
        return 0 if safe(now) else 1
    seconds = wait_for(now)
    if not seconds:
        print(f"safe to restart now ({into}s into the window)")
        return 0
    print(f"{into}s into the window, inside {UNSAFE_FROM}-{UNSAFE_TO}s: waiting {seconds}s")
    if not a.dry_run:
        time.sleep(seconds)
        print(f"safe to restart now ({into_window(time.time())}s into the window)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
