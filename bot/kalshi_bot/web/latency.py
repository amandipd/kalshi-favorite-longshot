"""How fast the live bot's orders reach Kalshi, for the dashboard's Latency tab (/api/latency, latency.js).

Added Oct 15, 2026, and cut down the same day to the current setup only: with less than a week of data for each, a
comparison of setups said little. So the tab shows fast entry on the server in Ohio, from the moment it went live
(SINCE), and nothing compares it with the setups before it.

An order's landing is how long after its window's minute-8 mark (480 s in) Kalshi stamped it. The stamp is Kalshi's
own (ts_ms in its answer, on its clock), so this PC's clock doesn't move it. The ledger's own ts is the PC's and isn't
used. An order Kalshi refused carries no stamp and is left out.

SETUP says what the current setup does, in plain words; figures() gives its orders' figures. WHERE (where the time goes
in a fast window now) and NEXT (what could come next) are estimates from reports/Faster Kalshi order sending.md and the
server's own latency probe (deploy/probe_latency.py), Oct 15.
Everything here only reads the ledger it's handed.
"""
import json

from kalshi_bot import fast_entry

MARK = 480   # the minute-8 mark, in seconds into the 15-minute window

# The server in Ohio (AWS us-east-2, Kalshi's region) went live: its bot started Oct 16, 2026, 05:13:55 UTC. The fast
# entry before it (from Oct 14, 21:04:44 UTC) ran from a home computer far from Kalshi and doesn't count: the tab is the
# setup now.
SINCE = 1792127635

SETUP = {"title": "Fast entry",
         "what": "The bot wakes at minute 8 on Kalshi's clock. It reads the prices it needs at 7.5 minutes and opens "
                 "its connections in the last moments ahead of the mark. At the mark it reads every order book and "
                 "sends all of a window's orders together, each naming its exchange section (exchange_index). It runs "
                 "on a server in Ohio, in the same Amazon region as Kalshi."}

# Where the time goes in a fast window now, in ms: estimates. The server's probe of Kalshi, Oct 15: a round trip of 3.9 ms
# median, 4.6 ms at most (50 requests); nothing timed inside a real burst yet.
WHERE = [
    {"step": "Wake up", "lo": 0, "hi": 1, "what": "Linux timers fire within about a millisecond, on a clock synced to Amazon's to within 0.01 ms."},
    {"step": "Read books, first 8", "lo": 4, "hi": 10, "what": "One round trip to Kalshi, inside Amazon's Ohio region."},
    {"step": "Read books, next 8", "lo": 4, "hi": 10, "what": "Each window has 16 markets and the bot reads 8 at a time, so it waits for a second round trip."},
    {"step": "Decide, sign and build", "lo": 2, "hi": 5, "what": "Checking the rules, signing each request and building the orders."},
    {"step": "Order trip to Kalshi", "lo": 2, "hi": 3, "what": "Half a round trip: the order travelling one way, within Ohio."},
]

# What could come next, ranked (reports/Faster Kalshi order sending.md, with the live ledger's check), and what's done.
NEXT = [
    {"title": "Time each step", "what": "Log how long each step of a real burst takes, so the next change aims at the right one.",
     "saves": "Finds the gap", "status": "Not built"},
    {"title": "Read all 16 books at once", "what": "One wave of book reads instead of two: 16 connections, opened before the mark.",
     "saves": "4–10 ms", "status": "Not built"},
    {"title": "Read only books that can qualify", "what": "Skip markets whose minute-7 price can't qualify, so 16 reads become a few.",
     "saves": "A few ms", "status": "Not built"},
    {"title": "Kalshi's direct address", "what": "The bot sends to external-api.kalshi.com, straight to Kalshi in Ohio.",
     "saves": "0–30 ms, fewer spikes", "status": "Done"},
    {"title": "A server in Ohio", "what": "The bot runs on a small cloud server in Ohio, next to Kalshi's, since Oct 15.",
     "saves": "85–120 ms", "status": "Done"},
]


def num(v):
    """A number from Kalshi's answer (they come as strings: "31.00"), or None."""
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x and abs(x) != float("inf") else None


def as_dict(text):
    try:
        v = json.loads(text) if isinstance(text, str) else None
    except ValueError:
        return None
    return v if isinstance(v, dict) else None


def orders(db):
    """Every order Kalshi stamped, oldest first: [stamp (s), landing (s after its window's minute-8 mark), share of the
    contracts asked that filled, contracts asked], to the millisecond and the tenth of a percent. The share is None
    when the fill or the size can't be read, and the size None when it isn't a positive number."""
    if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='orders'").fetchone():
        return []
    out = []
    for req, resp in db.execute("SELECT request, response FROM orders"):
        answer = as_dict(resp) or {}
        ms = num(answer.get("ts_ms"))
        if ms is None:
            continue
        stamp = ms / 1000
        window = stamp - stamp % 900
        asked, filled = num((as_dict(req) or {}).get("count")), num(answer.get("fill_count"))
        asked = asked if asked and asked > 0 else None
        share = round(filled / asked, 3) if asked and filled is not None else None
        out.append([round(stamp, 3), round(stamp - window - MARK, 3), share, None if asked is None else round(asked, 2)])
    return sorted(out, key=lambda r: r[0])


def filled(rows):
    """The share of these orders' contracts that filled, by contract (orders whose fill or size can't be read left out)."""
    known = [r for r in rows if r[2] is not None and r[3]]
    asked = sum(r[3] for r in known)
    return round(sum(r[2] * r[3] for r in known) / asked, 3) if asked else None


def rnd(v):
    return None if v is None else round(v, 3)


def figures(rows):
    """The figures of these orders() rows: how many, the windows they fell in, their median landing, the median of each
    window's first order, their slow tail (the 95th percentile: 1 in 20 was slower) and the share of their contracts
    that filled. With no rows, the counts are 0 and the rest None."""
    firsts = {}
    for r in rows:
        firsts.setdefault(r[0] - r[0] % 900, r[1])   # rows come oldest first: a window's first order is its first row
    lands = sorted(r[1] for r in rows)
    return {"orders": len(rows), "windows": len(firsts), "median": rnd(fast_entry.quantile(lands, 0.5)),
            "first": rnd(fast_entry.quantile(sorted(firsts.values()), 0.5)), "p95": rnd(fast_entry.quantile(lands, 0.95)),
            "filled": filled(rows)}


def report(db):
    """The tab's reply, from a ledger opened read-only: the current setup's orders (those Kalshi stamped since SINCE)
    and their figures, what the setup does, where the time goes now and what could come next."""
    rows = [o for o in orders(db) if o[0] >= SINCE]
    return {"mark": MARK, "since": SINCE, "setup": SETUP, "orders": rows, "figures": figures(rows), "where": WHERE,
            "next": NEXT}
