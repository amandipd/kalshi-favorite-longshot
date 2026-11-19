"""How big should each bet be? Sizing the minute-8, 90c+ favourites strategy on every day since Dec 10, 2025.

Strategy: at minute 8 of each window, buy the favourite of every crypto, metals and energy market
whose ask is 90-99.9c, in whole contracts, and hold it to settlement - sized by each rule below.

Flat $10 bets make roughly the same dollars every month, so the return shrinks as
the bankroll grows. Betting a fixed percentage of the bankroll compounds instead,
but bets in the same window are placed together and lose together (up to 11 of
16 in one window), so the usual one-bet-at-a-time Kelly formula overstates the
safe size. This replays every day since Dec 10 at each percentage and resamples whole days
(keeping each day's windows together) to see the spread of possible months.

Every bet buys whole contracts at the minute-8 ask plus a fill penalty, pays the
taker fee rounded up to the cent, and is sized off the bankroll before the window
(results land when the window closes). A bankroll too small for a $1 bet is broke.

Rules: flat $10; a percentage of the bankroll; and a percentage with a cap on the
whole window (if a window has many bets, each is shrunk so their total stays
under the cap), which targets the correlated-loss risk directly.

Scenarios:
  backtest   the ask as recorded, 1x fee
  realistic  +0.4c a contract (live fills vs candle asks, from the rebuild test), 1x fee
  stress     +0.4c a contract and a 2x crypto fee multiplier

    python sizing.py
"""
import json
import math
import random
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

from minutes import CRYPTO, load
from history import strategy

START = 240.0
LO, HI = 0.90, 0.9991
PCTS = [0.01, 0.015, 0.02, 0.03, 1 / 24, 0.06, 0.08, 0.10]
WINDOW_CAPS = [(0.03, 0.20), (1 / 24, 0.20), (0.06, 0.20), (0.06, 0.30)]
SCENARIOS = {"backtest": (0.0, 1.0), "realistic": (0.004, 1.0), "stress": (0.004, 2.0)}
PATHS = 400


def days_of_windows():
    """[[window bets]] per UTC day; a bet is (ask, won, crypto)."""
    by_w = defaultdict(list)
    for t, series, fill, won in load()[8]:
        if LO <= fill < HI:
            by_w[t].append((fill, won, series in CRYPTO))
    by_day = defaultdict(list)
    for t in sorted(by_w):
        by_day[t[:10]].append(by_w[t])
    return [by_day[d] for d in sorted(by_day)]


def fee(contracts, price, crypto, mult):
    return math.ceil((mult if crypto else 1.0) * 0.07 * contracts * price * (1 - price) * 100 - 1e-9) / 100


def run(days, pct, slip, mult, wcap=None):
    """One path. pct=None means flat $10 bets; wcap caps a window's total stake as a share of the bankroll.
    Returns (final, max drawdown, worst window as % of bankroll, broke)."""
    bal = peak = START
    dd = worst = 0.0
    for day in days:
        for window in day:
            base = 10.0 if pct is None else pct * bal
            if base < 1.0 or bal < base:  # the same broke rule as the paper trader
                return 0.0, 1.0, worst, True
            # A busy window shrinks each bet (bets too small for one contract are skipped).
            stake = min(base, wcap * bal / len(window)) if wcap else base
            avail, pnl = bal, 0.0
            for ask, won, crypto in window:
                price = min(ask + slip, 0.999)
                c = math.floor(stake / price)
                if c < 1:
                    continue
                f = fee(c, price, crypto, mult)
                if avail < c * price + f:
                    continue
                avail -= c * price + f
                pnl += (c * (1 - price) if won else -c * price) - f
            worst = min(worst, pnl / bal)
            bal += pnl
            peak = max(peak, bal)
            dd = max(dd, 1 - bal / peak)
    return bal, dd, worst, False


def quantile(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))]


def study(args):
    days, pct, name, wcap, horizon = args
    slip, mult = SCENARIOS[name]
    hist = run(days, pct, slip, mult, wcap)
    rng = random.Random(7)
    sims = [run([rng.choice(days) for _ in range(horizon)], pct, slip, mult, wcap) for _ in range(PATHS)]
    finals = [s[0] for s in sims]
    return {"pct": pct, "scenario": name, "wcap": wcap, "horizon": horizon, "hist": hist,
            "p10": quantile(finals, 0.10), "p50": quantile(finals, 0.50), "p90": quantile(finals, 0.90),
            "loss": sum(f < START for f in finals) / PATHS,
            "dd50": sum(s[1] >= 0.5 for s in sims) / PATHS,
            "broke": sum(s[3] for s in sims) / PATHS,
            "ddmed": quantile([s[1] for s in sims], 0.5)}


def kelly_single(days, slip, mult):
    """Kelly fraction if each bet were the only one: (q - cost) / (1 - cost), cost = price + fee per contract."""
    bets = [b for d in days for w in d for b in w]
    q = sum(b[1] for b in bets) / len(bets)
    cost = sum(min(b[0] + slip, 0.999) + fee(10.0 / b[0], b[0], b[2], mult) / (10.0 / b[0]) for b in bets) / len(bets)
    return q, cost, (q - cost) / (1 - cost)


def label(pct, wcap=None):
    base = "flat $10" if pct is None else ("1/24" if abs(pct - 1 / 24) < 1e-9 else f"{pct * 100:g}%")
    return base + (f", window<={wcap * 100:g}%" if wcap else "")


def main():
    strategy(__doc__)
    days = days_of_windows()
    per_window = [len(w) for d in days for w in d if w]
    print(f"{len(days)} days, {sum(per_window)} bets in {len(per_window)} windows with a bet;"
          f" bets per such window: mean {sum(per_window) / len(per_window):.1f}, max {max(per_window)}")
    for name, (slip, mult) in SCENARIOS.items():
        q, cost, k = kelly_single(days, slip, mult)
        print(f"  one-bet Kelly, {name}: win {q:.2%}, all-in cost {cost:.2%} -> {k:.1%} of bankroll per bet")

    rules = [(None, None)] + [(p, None) for p in PCTS] + WINDOW_CAPS
    jobs = [(days, p, name, w, h) for h in (30, 90) for name in SCENARIOS for p, w in rules
            if h == 30 or name != "backtest"]
    with ProcessPoolExecutor() as pool:
        results = list(pool.map(study, jobs))
    with open("sizing.json", "w", encoding="utf-8") as fh:
        json.dump([{**{k: v for k, v in r.items() if k != "hist"}, "label": label(r["pct"], r["wcap"]),
                    "actual": dict(zip(("final", "maxDrop", "worstWindow", "broke"), r["hist"]))} for r in results], fh, indent=1)

    for h in (30, 90):
        for name in SCENARIOS:
            rows = [r for r in results if r["scenario"] == name and r["horizon"] == h]
            if not rows:
                continue
            print(f"\n{name.upper()}, {h} days from $240. {PATHS} resampled runs"
                  + ("; 'actual' = the real history in order." if h == 30 else "."))
            print(f"{'rule':>24} | {'actual':>9} {'max drop':>8} {'worst 15m':>9} | {'bad (10%)':>10} {'median':>10}"
                  f" {'good (90%)':>11} | {'P(loss)':>7} {'P(-50%)':>7} {'P(broke)':>8}")
            for r in rows:
                f, dd, worst, broke = r["hist"]
                hist = (f"{'BROKE' if broke else f'${f:,.0f}':>9} {dd:>8.0%} {worst:>9.0%}" if h == 30 else " " * 28)
                print(f"{label(r['pct'], r['wcap']):>24} | {hist} | ${r['p10']:>9,.0f} ${r['p50']:>9,.0f}"
                      f" ${r['p90']:>10,.0f} | {r['loss']:>7.0%} {r['dd50']:>7.0%} {r['broke']:>8.0%}")


if __name__ == "__main__":
    main()
