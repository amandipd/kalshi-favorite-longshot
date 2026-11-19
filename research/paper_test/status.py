"""Scores the paper (dry-run) bot's forward test from its ledger: cents of profit for every dollar bet, with a 95%
range that counts each 15-minute window once; losses against what the prices predicted; and the windows with 6 or
more losses. Reads the ledger read-only and writes nothing.

    python research/paper_test/status.py                      # bot/state/dry-prod.db
    python research/paper_test/status.py path/to/ledger.db
"""
import math
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.normpath(os.path.join(HERE, "..", "..", "bot", "state", "dry-prod.db"))
when = lambda t: datetime.fromtimestamp(float(t), timezone.utc).strftime("%b %d %H:%M UTC")


def ledger(path):
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def settled(db, since=0):
    return db.execute("SELECT window_open, pnl, cost + fee, status = 'won', price, settled_ts FROM bets "
                      "WHERE status != 'open' AND placed_ts >= ? ORDER BY settled_ts", (since,)).fetchall()


def edge(rows):
    """Cents of profit for every dollar bet, and its 95% range counting each 15-minute window once."""
    w = defaultdict(lambda: [0.0, 0.0])
    for t, p, s, *_ in rows:
        w[t][0] += p
        w[t][1] += s
    P, S, k = sum(v[0] for v in w.values()), sum(v[1] for v in w.values()), len(w)
    if k < 2:
        return P, S, None, None, None
    c = P / S
    se = math.sqrt(sum((v[0] - c * v[1]) ** 2 for v in w.values()) * k / (k - 1)) / S
    return P, S, c * 100, (c - 1.96 * se) * 100, (c + 1.96 * se) * 100


def main(path=LEDGER):
    paper = ledger(path)
    rows = settled(paper)
    still_open = paper.execute("SELECT COUNT(*) FROM bets WHERE status='open'").fetchone()[0]
    first = paper.execute("SELECT MIN(placed_ts) FROM bets").fetchone()[0]
    print(f"PAPER TEST, from {when(first) if first is not None else '-'}: {len(rows)} settled bets ({still_open} open)")
    P, S, c, lo, hi = edge(rows)
    if c is None:
        print("  too few settled bets yet")
    else:
        lost = sum(1 for r in rows if not r[3])
        predicted = sum(1 - r[4] for r in rows)
        print(f"  {c:+.2f} cents of profit for every dollar bet (probably between {lo:+.2f} and {hi:+.2f})")
        print(f"  lost {lost} where prices predicted {predicted:.1f}")
    piles = defaultdict(int)
    for t, _, _, won, *_ in rows:
        piles[t] += not won
    six = [when(t) for t, n in piles.items() if n >= 6]
    print(f"  windows with 6+ losses: {len(six)} {six if six else ''}")


if __name__ == "__main__":
    main(*sys.argv[1:2])
