"""The pure rules of the all-markets favourite map, exactly as PREREG.md fixes them.

Nothing here touches the network or reads an outcome to decide what to fetch. fetch.py calls these to decide
which trades to ask for; score.py calls them to price, bet and judge cells.

A trade is [unix ts, YES price in cents, contracts, taker side]. The taker bought the side named: at the YES price
for "yes", at 100 minus it for "no" (checked 28 Oct: Yes buyers pay about 1c over the No buyers next to them).
"""
from __future__ import annotations

import math
import random
from collections import defaultdict
from datetime import datetime, timezone

H = 3600
FRESH = 3600                       # an entry price may be at most 60 minutes old
CHECKPOINTS = (("1h", 1), ("2h", 2), ("4h", 4), ("8h", 8), ("12h", 12), ("24h", 24),
               ("2d", 48), ("3d", 72), ("7d", 168), ("14d", 336), ("30d", 720))
CHECKPOINT_LABELS = ("half",) + tuple(label for label, _ in CHECKPOINTS)
SHORT_LIFE = 2 * H                 # markets living under this also get their midpoint
MAIN_BANDS = ("70-80", "80-90", "90-95", "95-99")
MIN_EVENTS = 100
Z = 1.96
SEED = 20261029
LUCK = 0.025                       # chance a candidate's lower end lands above zero on test by luck


def ts(iso: str) -> float:
    """Unix seconds from Kalshi's ISO time, whatever the number of fraction digits."""
    s = iso.replace("Z", "+00:00")
    if "." in s:
        head, rest = s.split(".", 1)
        cut = next((i for i, ch in enumerate(rest) if not ch.isdigit()), len(rest))
        frac, tz = rest[:cut], rest[cut:]
        s = f"{head}.{(frac + '000000')[:6]}{tz}"
    d = datetime.fromisoformat(s)
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.timestamp()


WINDOW_START = ts("2025-11-01T00:00:00Z")
SPLIT = ts("2026-08-01T00:00:00Z")
WINDOW_END = ts("2026-10-28T00:00:00Z")


# ---------- fee and returns ----------

def fee_cents(price: float, mult: float) -> float:
    """Kalshi's taker fee per contract, unrounded: 0.07 x p x (1 - p) x the series multiplier, in cents."""
    p = price / 100
    return 100 * 0.07 * p * (1 - p) * mult


def profit_cents(price: float, won: bool, mult: float) -> float:
    """Payout less price less fee, per contract, in cents: the breakeven slippage of one bet."""
    return (100 if won else 0) - price - fee_cents(price, mult)


def return_per_dollar(price: float, won: bool, mult: float) -> float:
    """Profit on a $1 bet that buys at `price` and pays the fee: profit over what one contract cost."""
    return profit_cents(price, won, mult) / (price + fee_cents(price, mult))


# ---------- checkpoints ----------

def checkpoints(open_ts: float, close_ts: float) -> list[tuple[str, float]]:
    """Every checkpoint that falls after the market opened, in CHECKPOINT_LABELS order."""
    out = []
    if close_ts - open_ts < SHORT_LIFE:
        out.append(("half", open_ts + (close_ts - open_ts) / 2))
    for label, hours in CHECKPOINTS:
        t = close_ts - hours * H
        if t > open_ts:
            out.append((label, t))
    return out


# ---------- favourite and entry price ----------

def paid(trade) -> float:
    """What the buyer of this trade paid per contract, in cents."""
    return trade[1] if trade[3] == "yes" else 100 - trade[1]


def entry_at(trades, t: float, fresh: float = FRESH):
    """The bet at checkpoint t, or None.

    The favourite is the side the latest trade at or before t priced above 50c. The entry is the latest trade at
    or before t whose buyer took that side, at most `fresh` seconds old, at the price that buyer paid.
    """
    upto = sorted((x for x in trades if x[0] <= t), key=lambda x: x[0])
    if not upto:
        return None
    yes = upto[-1][1]
    if yes == 50:
        return None
    side = "yes" if yes > 50 else "no"
    for x in reversed(upto):
        if t - x[0] > fresh:
            return None
        if x[3] == side:
            price = paid(x)
            near = sum(y[2] * paid(y) / 100 for y in upto
                       if y[3] == side and t - y[0] <= fresh and paid(y) <= price + 1 + 1e-9)
            return {"side": side, "price": price, "age": t - x[0], "money_near": near, "last_yes": yes}
    return None


def parse_trade(raw: dict) -> list:
    """[ts, YES cents, contracts, taker side] from a Kalshi trade record, new dollar fields or old integer ones."""
    if raw.get("yes_price_dollars") is not None:
        yes = round(float(raw["yes_price_dollars"]) * 100, 4)
    else:
        yes = float(raw["yes_price"])
    n = float(raw["count_fp"]) if raw.get("count_fp") is not None else float(raw["count"])
    return [ts(raw["created_time"]), yes, n, raw["taker_side"]]


# ---------- bands, halves ----------

def band_of(price: float):
    if price < 50:
        return None
    for lo, hi, name in ((50, 60, "50-60"), (60, 70, "60-70"), (70, 80, "70-80"), (80, 90, "80-90"),
                         (90, 95, "90-95"), (95, 99, "95-99")):
        if lo <= price < hi:
            return name
    return "99+"


def half_of(close_ts: float):
    if WINDOW_START <= close_ts < SPLIT:
        return "train"
    if SPLIT <= close_ts < WINDOW_END:
        return "test"
    return None


# ---------- sampling ----------

def sample(markets, seed: int = SEED, max_events: int = 40, max_markets: int = 5) -> list[dict]:
    """Up to `max_events` random events per series and half, then up to `max_markets` random markets per event.

    Seeded on series, half and event ticker only, so it can never depend on a result or on input order.
    """
    groups = defaultdict(lambda: defaultdict(list))
    for m in markets:
        half = half_of(ts(m["close_time"]))
        if half is None:
            continue
        groups[(m["series"], half)][m["event_ticker"]].append(m)
    out = []
    for (series, half), events in sorted(groups.items()):
        names = sorted(events)
        random.Random(f"{seed}|{series}|{half}").shuffle(names)
        for event in names[:max_events]:
            ms = sorted(events[event], key=lambda m: m["ticker"])
            random.Random(f"{seed}|{series}|{half}|{event}").shuffle(ms)
            out.extend(ms[:max_markets])
    return sorted(out, key=lambda m: m["ticker"])


def sample_two_pass(rows, seed: int = SEED, max_events: int = 40, max_markets: int = 5) -> list[dict]:
    """The same draw as `sample`, reading the listing twice instead of holding millions of markets in memory.

    `rows` is a function returning a fresh iterator over the listing. Pass 1 records each series and half's events
    and draws them; pass 2 keeps only the drawn events' markets (the first copy of a repeated ticker).
    """
    events = defaultdict(set)
    for m in rows():
        half = half_of(ts(m["close_time"]))
        if half is not None:
            events[(m["series"], half)].add(m["event_ticker"])
    chosen = set()
    for (series, half), evs in events.items():
        names = sorted(evs)
        random.Random(f"{seed}|{series}|{half}").shuffle(names)
        chosen.update((series, half, e) for e in names[:max_events])
    del events
    groups, seen = defaultdict(list), set()
    for m in rows():
        half = half_of(ts(m["close_time"]))
        key = (m["series"], half, m["event_ticker"])
        if half is None or key not in chosen or m["ticker"] in seen:
            continue
        seen.add(m["ticker"])
        groups[key].append(m)
    out = []
    for (series, half, event), ms in sorted(groups.items()):
        ms = sorted(ms, key=lambda m: m["ticker"])
        random.Random(f"{seed}|{series}|{half}|{event}").shuffle(ms)
        out.extend(ms[:max_markets])
    return sorted(out, key=lambda m: m["ticker"])


# ---------- which trade requests a market needs ----------

def endpoints_for(t: float, cutoff: float) -> list[str]:
    """Which trade endpoints hold the window [t - FRESH, t]: trades before the archive line are historical only."""
    if t - FRESH >= cutoff:
        return ["live"]
    if t < cutoff:
        return ["historical"]
    return ["live", "historical"]


def coverage(oldest: float, t_max: float, complete: bool, endpoint: str, cutoff: float):
    """The span of time one page of trades fully describes: (low, high, low is inclusive)."""
    if complete:
        return (cutoff if endpoint == "live" else -math.inf, t_max, True)
    return (oldest, t_max, False)


def covers(cov, t: float) -> bool:
    lo, hi, inclusive = cov
    start = t - FRESH
    return t <= hi and (start >= lo if inclusive else start > lo)


# ---------- clustered ranges ----------

def cluster_stats(values, clusters) -> dict:
    """Mean with a cluster-robust standard error: bets on the same event count as one, not many."""
    n = len(values)
    if n == 0:
        return {"mean": math.nan, "se": math.nan, "lo": math.nan, "hi": math.nan, "n": 0, "events": 0}
    mean = sum(values) / n
    sums = defaultdict(float)
    for v, c in zip(values, clusters):
        sums[c] += v - mean
    g = len(sums)
    if g < 2:
        se = math.nan
    else:
        se = math.sqrt(g / (g - 1) * sum(s * s for s in sums.values()) / n ** 2)
    return {"mean": mean, "se": se, "lo": mean - Z * se, "hi": mean + Z * se, "n": n, "events": g}


def stats(bets) -> dict:
    return cluster_stats([b["ret"] for b in bets], [b["event"] for b in bets])


def _ok(s) -> bool:
    return s["n"] > 0 and s["mean"] > 0 and not math.isnan(s["lo"]) and s["lo"] > 0


# ---------- candidates and passes ----------

def main_bets(bets):
    return [b for b in bets if b["band"] in MAIN_BANDS]


def is_candidate(bets) -> bool:
    """Train half: 100+ events, mean above zero, lower end above zero."""
    s = stats(main_bets(bets))
    return s["events"] >= MIN_EVENTS and _ok(s)


def pass_checks(bets, category: bool) -> dict:
    """Test half, read once: every check in PREREG.md 'Pass', plus 'room to spare'."""
    bets = main_bets(bets)
    s = stats(bets)
    head = s["events"] >= MIN_EVENTS and _ok(s)
    loo = {band: stats([b for b in bets if b["band"] != band]) for band in MAIN_BANDS}
    band_loo = all(_ok(x) for x in loo.values())
    drop_biggest = None
    biggest = None
    if category:
        counts = defaultdict(int)
        for b in bets:
            counts[b["series"]] += 1
        if counts:
            biggest = max(sorted(counts), key=lambda k: counts[k])
            drop_biggest = _ok(stats([b for b in bets if b["series"] != biggest]))
        else:
            drop_biggest = False
    profit = (sum(profit_cents(b["price"], b["won"], b["mult"]) for b in bets) / len(bets)) if bets else math.nan
    passed = head and band_loo and (drop_biggest if category else True)
    return {"stats": s, "headline": head, "band_loo": band_loo, "loo": loo, "drop_biggest": drop_biggest,
            "biggest_series": biggest, "profit_per_contract": profit, "room_to_spare": bool(profit >= 1),
            "passed": bool(passed)}


def lonely(scores: dict, label: str) -> bool:
    """A pass whose scored neighbouring checkpoints all sit at or below zero. No scored neighbour: not flagged."""
    i = CHECKPOINT_LABELS.index(label)
    nbrs = [CHECKPOINT_LABELS[j] for j in (i - 1, i + 1) if 0 <= j < len(CHECKPOINT_LABELS)]
    present = [scores[k] for k in nbrs if k in scores]
    return bool(present) and all(v <= 0 for v in present)


def expected_lucky_passes(n_candidates: int) -> float:
    return LUCK * n_candidates
