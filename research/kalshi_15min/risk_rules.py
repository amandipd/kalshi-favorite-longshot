"""Taking profits out and stopping after losses, tested on every window since Dec 10, 2025.

Strategy: the minute-8 favourites rule - buy the favourite of every crypto, metals and energy market
when its ask is 90-99.9c, $10 a bet or 3% of the bankroll with a 20% window cap, filled 0.4c worse
than the recorded ask, held to settlement - run under each rule below for taking profit out, and each
stop or pause.

Two questions for the minute-8 favorites strategy (crypto, metals, energy; 90-99.9c; live-like
fills 0.4c worse than the recorded ask):

  1. How much of the profit to take out, and how often. Money taken out can't be lost later, but
     it also can't absorb a bad week or, with percentage sizing, compound.
  2. Whether a stop (stop or pause trading after a loss) protects the account or only gives up
     profit. A stop can only help if losses come in runs (Kaminski & Lo, "When do stop-loss rules
     stop losses?"), so the first output checks that.

Each rule is replayed on the real history three times (from Dec 10, the first market; from Jul 18, where
the history began before minutes_pre.csv; and from Aug 24, after the worst week) and on 400 made-up 90-day
histories stitched from random 5-day stretches of the real one from Jul 18 or from Aug 24, which keeps bad
stretches together. "Take-home" is what you would have at the end: everything
taken out plus the account. Every run starts with $240, like the paper accounts.

Pause rules read the $10 paper result, which keeps running while real bets are paused, so they
know when to resume.

    python risk_rules.py
"""
import csv
import json
import os
import random
from collections import defaultdict, deque

import history
import strategies_backtest as sb  # the accounts' rules and sizing constants
from strategies_backtest import favourite, fee, ts
from history import strategy

SLIP = 0.004        # live-like fills
DAY = 96            # 15-minute windows a day
RUNS, HORIZON, BLOCK = 400, 90, 5


def load():
    """[day][window] -> (bets, $10 pnl, $10 losses, $10 cash needed), bets being [(price, won)] for the
    minute-8 favourites in crypto, metals and energy. One entry per UTC day from history.FIRST's (empty for a day
    without markets), so since() can slice it by date."""
    with open("universe.json", encoding="utf-8") as fh:
        groups = {u["ticker"]: u["group"] for u in json.load(fh)["series"]}
    windows, seen = defaultdict(list), set()
    first, last = ts(history.FIRST), ts(history.end()) - 900
    for path in history.FILES:
        if not os.path.exists(path):
            continue
        with open(path) as fh:
            for r in csv.DictReader(fh):
                if r["ticker"] in seen:
                    continue
                seen.add(r["ticker"])
                t = ts(r["open_time"])
                if not first <= t <= last:
                    continue
                bets = windows[t]  # every window gets an entry, bets or not
                if groups.get(r["series"]) not in sb.EDGE_GROUPS or r["b8"] == "" or r["a8"] == "":
                    continue
                side, top = favourite(float(r["b8"]), float(r["a8"]))
                if side and sb.LO <= top <= sb.HI:
                    bets.append((min(top + SLIP, 0.999), (side == "yes") == (r["resolved_yes"] == "1")))
    days = defaultdict(list)
    for t in sorted(windows):
        bets = windows[t]
        pnl, losses = play(bets, sb.STAKE, 1e9)
        need = sum(sb.STAKE + fee(sb.STAKE / p, p) for p, _ in bets)
        days[int(t // 86400)].append((bets, pnl, losses, need))
    return [days[d] for d in range(int(first // 86400), max(days, default=int(first // 86400) - 1) + 1)]


def since(days, iso):
    """The days of load() from the UTC day of `iso` on."""
    return days[max(0, int(ts(iso) // 86400) - int(ts(history.FIRST) // 86400)):]


def play(bets, stake, cash):
    """(pnl, losses) for one window's bets at one stake, skipping bets the cash can't cover."""
    pnl, losses = 0.0, 0
    for price, won in bets:
        c = stake / price
        f = fee(c, price)
        if cash < stake + f:
            continue
        cash -= stake + f
        pnl += (c if won else 0.0) - stake - f
        losses += not won
    return pnl, losses


def cents(x):
    return int(x * 100 + 1e-6) / 100


def simulate(days, sizing="flat", take=None, stop=None):
    """One history under one rule. Returns take-home, taken out, the end state and bets placed.

    take: (every_days, how) with how "above:X" (take everything over $X) or "half" (half of the
          profit over the last high-water mark).
    stop: ("loss", X)   stop for good once total profit (taken + account - $240) is -$X or worse
          ("dd", d)     stop for good once the account is d below its peak
          ("day", X)    pause for the rest of the UTC day after a -$X day
          ("trail", X)  pause once the last 24 h of $10 paper results is -$X or worse;
                        resume once it is back above zero
          ("cluster", k, h)  after a window with k+ losses, pause h hours
    sizing: "flat" $10, "capped" 3% a bet and 20% a window, or ("floor", a, per, cap): a
            Grossman-Zhou floor at a x the peak, betting per of the cushion above it a bet and
            cap of it a window.
    """
    bal = peak = hw = sb.START
    taken = 0.0
    state = "on"  # on, paused, stopped, broke
    trail, trail_sum = deque(), 0.0
    cool = 0
    n = 0
    for di, day in enumerate(days):
        if take and di and di % take[0] == 0 and state in ("on", "paused"):
            kind, _, x = take[1].partition(":")
            if kind == "above" and bal > float(x):
                taken += bal - float(x)
                bal = float(x)
            elif kind == "half" and bal > hw:
                out = (bal - hw) / 2
                taken += out
                bal -= out
                hw = bal
        day_pnl = 0.0
        if state == "paused" and stop and stop[0] == "day":
            state = "on"
        for bets, paper, paper_losses, need in day:  # paper: the $10 result, whatever the real account does
            if state in ("stopped", "broke"):
                break
            trade = state == "on" and cool == 0
            if sizing == "flat":
                stake = sb.STAKE
            elif sizing == "capped":
                stake = cents(min(bal * sb.CAP_PCT, bal * sb.WINDOW_CAP / max(len(bets), 1)))
            else:
                _, a, per, cap = sizing
                cushion = bal - a * peak
                stake = cents(min(cushion * per, cushion * cap / max(len(bets), 1))) if cushion > 0 else 0.0
            if sizing in ("flat", "capped") and (stake < sb.MIN_BET or bal < stake + sb.FEE_ROOM):
                state = "broke"
                break
            if trade and bets and stake >= sb.MIN_BET:
                pnl = paper if sizing == "flat" and bal >= need else play(bets, stake, bal)[0]
                bal += pnl
                day_pnl += pnl * sb.STAKE / stake
                peak = max(peak, bal)
                n += len(bets)
            cool = max(0, cool - 1)
            trail.append(paper)
            trail_sum += paper
            if len(trail) > DAY:
                trail_sum -= trail.popleft()
            if not stop:
                continue
            kind = stop[0]
            if kind == "loss" and taken + bal - sb.START <= -stop[1]:
                state = "stopped"
            elif kind == "dd" and bal < (1 - stop[1]) * peak:
                state = "stopped"
            elif kind == "day" and state == "on" and day_pnl <= -stop[1]:
                state = "paused"
            elif kind == "trail":
                if state == "on" and trail_sum <= -stop[1]:
                    state = "paused"
                elif state == "paused" and trail_sum > 0:
                    state = "on"
            elif kind == "cluster" and paper_losses >= stop[1]:
                cool = stop[2] * 4
        if state in ("stopped", "broke"):
            break
    return {"home": taken + bal, "taken": taken, "state": state, "bets": n}


def block_paths(days, rng):
    starts = range(len(days) - BLOCK + 1)
    for _ in range(RUNS):
        path = []
        while len(path) < HORIZON:
            s = rng.choice(starts)
            path += days[s:s + BLOCK]
        yield path[:HORIZON]


def quantile(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))]


def momentum(days):
    """Do losses come in runs? Compares what follows a bad stretch with what follows any stretch."""
    flat = [(w[1], w[2], len(w[0])) for d in days for w in d]
    pnl = [x[0] for x in flat]
    nb = [x[2] for x in flat]

    def per_bet(i, j):
        b = sum(nb[i:j])
        return sum(pnl[i:j]) / b * 100 if b else None  # cents per $10 bet

    base = per_bet(0, len(pnl))
    print(f"all windows: {base:+.1f}c per $10 bet")
    # after a bad day (UTC), the next day
    daily = []
    i = 0
    for d in days:
        daily.append((sum(pnl[i:i + len(d)]), sum(nb[i:i + len(d)]), i, i + len(d)))
        i += len(d)
    after_bad = [per_bet(daily[k + 1][2], daily[k + 1][3]) for k in range(len(daily) - 1) if daily[k][0] < -30]
    after_good = [per_bet(daily[k + 1][2], daily[k + 1][3]) for k in range(len(daily) - 1) if daily[k][0] >= -30]
    avg = lambda xs: sum(x for x in xs if x is not None) / max(1, sum(x is not None for x in xs))
    print(f"day after a day worse than -$30 ({len(after_bad)} days): {avg(after_bad):+.1f}c;  after any other day ({len(after_good)}): {avg(after_good):+.1f}c")
    # after the last 24 h of $10 results reach -$X, the next 24 h (no overlap counted twice: next hit only after 24 h)
    for x in (30, 60):
        hits, k = [], DAY
        while k < len(pnl) - DAY:
            if sum(pnl[k - DAY:k]) <= -x:
                hits.append(per_bet(k, k + DAY))
                k += DAY
            else:
                k += 1
        print(f"next 24 h after the last 24 h hit -${x} ({len(hits)} times): {avg(hits):+.1f}c")
    # after a window with 3+ losses, the next 4 hours
    hits = [per_bet(k + 1, k + 17) for k, w in enumerate(flat) if w[1] >= 3 and k + 17 < len(flat)]
    print(f"next 4 h after a window with 3+ losses ({len(hits)} windows): {avg(hits):+.1f}c")


def worst_drop(days):
    """The largest peak-to-trough fall in dollars at $10 a bet, with no broke rule."""
    bal = peak = worst = 0.0
    for d in days:
        for w in d:
            bal += w[1]
            peak = max(peak, bal)
            worst = max(worst, peak - bal)
    return worst


def report(days, rules):
    """Each rule on the three real histories, then on made-up 90-day histories from two worlds: Jul 18 on (edge
    about zero) and Aug 24 on (edge about +4c a bet, as it has looked lately)."""
    jul18, aug24 = since(days, history.JUL18), since(days, "2026-08-24T00:00:00Z")
    worlds = {"zero": list(block_paths(jul18, random.Random(7))), "real": list(block_paths(aug24, random.Random(7)))}
    print(f"{'':<46}{'real history':^45}| {'if the edge is ~zero':^26}| {'if the edge is real (+4c)':^30}")
    print(f"{'rule':<46}{'from Dec 10':>15}{'from Jul 18':>15}{'from Aug 24':>15}| {'median':>8} {'below $240':>11}      |"
          f" {'median':>8} {'worst 10%':>10} {'below $240':>11}")
    for label, kw in rules:
        d, a, b = simulate(days, **kw), simulate(jul18, **kw), simulate(aug24, **kw)
        tag = lambda r: f"${r['home']:,.0f}" + ("*" if r["state"] in ("broke", "stopped") else " ")
        cols = []
        for w in ("zero", "real"):
            homes = [simulate(p, **kw)["home"] for p in worlds[w]]
            cols.append((quantile(homes, .5), quantile(homes, .1), sum(h < sb.START for h in homes) / RUNS))
        (zm, _, zb), (rm, r10, rb) = cols
        print(f"{label:<46}{tag(d):>15}{tag(a):>15}{tag(b):>15}| ${zm:>7,.0f} {zb:>10.0%}       | ${rm:>7,.0f} ${r10:>9,.0f} {rb:>10.0%}")
    print("  * broke or stopped. Take-home = everything taken out + what is left in the account, from $240.")


def main():
    strategy(__doc__)
    days = load()
    print(f"{len(days)} days, {sum(len(d) for d in days)} windows\n")
    print("DO LOSSES COME IN RUNS? ($10 bets)")
    momentum(days)
    print("\nTAKING PROFIT OUT")
    report(days, [
        ("$10 · never", {}),
        ("$10 · weekly, all above $240", {"take": (7, "above:240")}),
        ("$10 · weekly, all above $400", {"take": (7, "above:400")}),
        ("$10 · weekly, all above $600", {"take": (7, "above:600")}),
        ("$10 · weekly, half of new profit", {"take": (7, "half")}),
        ("3%+20% · never", {"sizing": "capped"}),
        ("3%+20% · weekly, all above $240", {"sizing": "capped", "take": (7, "above:240")}),
        ("3%+20% · weekly, half of new profit", {"sizing": "capped", "take": (7, "half")}),
        ("3%+20% · every 4 weeks, half of new profit", {"sizing": "capped", "take": (28, "half")}),
    ])
    print("\nCOMBINED")
    report(days, [
        ("$10 · weekly above $400 · stop at -$120", {"take": (7, "above:400"), "stop": ("loss", 120)}),
        ("$10 · weekly above $400 · stop at -$60", {"take": (7, "above:400"), "stop": ("loss", 60)}),
        ("3%+20% · weekly half · stop at -$120", {"sizing": "capped", "take": (7, "half"), "stop": ("loss", 120)}),
        ("3%+20% · every 4 weeks half · stop at -$120", {"sizing": "capped", "take": (28, "half"), "stop": ("loss", 120)}),
    ])
    print("\nSTOPS ($10 bets, nothing taken out)")
    report(days, [
        ("none", {}),
        ("stop for good at -$60", {"stop": ("loss", 60)}),
        ("stop for good at -$120", {"stop": ("loss", 120)}),
        ("stop for good 30% below the peak", {"stop": ("dd", 0.30)}),
        ("stop for good 50% below the peak", {"stop": ("dd", 0.50)}),
        ("pause rest of day after -$40", {"stop": ("day", 40)}),
        ("pause while last 24 h paper <= -$30", {"stop": ("trail", 30)}),
        ("pause while last 24 h paper <= -$60", {"stop": ("trail", 60)}),
        ("pause 4 h after a window with 3+ losses", {"stop": ("cluster", 3, 4)}),
    ])
    print("\nFLOOR THAT RISES WITH THE PEAK (Grossman-Zhou), nothing taken out")
    report(days, [
        ("floor 50% of peak · 6%/40% of cushion", {"sizing": ("floor", 0.5, 0.06, 0.40)}),
        ("floor 50% of peak · 8%/50% of cushion", {"sizing": ("floor", 0.5, 0.08, 0.50)}),
        ("floor 70% of peak · 10%/60% of cushion", {"sizing": ("floor", 0.7, 0.10, 0.60)}),
    ])


if __name__ == "__main__":
    main()
