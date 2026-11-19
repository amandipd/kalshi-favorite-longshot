"""The replication's statistics, as pure functions of the markets.

    calibration   every market at its last trade at the entry minute, in 10c bands: how often YES won
                  against the price, with a 95% Wilson interval
    favourites    each market's favourite at the entry minute, the side with the higher ask, when that
                  ask is in the configured range (90-99.9c)
    kelly         the one-bet Kelly fraction for those favourites, f* = (q - c) / (1 - c)
    regime        profit per bet before and after the split day
    stop_rule     selling a favourite the first minute its bid is at or under a level, against holding

Every bet is `stake` dollars of whole-or-fractional contracts filled at the ask plus `slippage`, and
pays Kalshi's taker fee on the price paid, rounded up to the cent per order.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from kalshi_calibration.config import ReplicationConfig
from kalshi_calibration.replication.dataset import Market, day_ts

Z = 1.96  # two-sided 95%
MAX_PRICE = 0.999  # Kalshi's highest tick: a fill can't cost more


def wilson(k: int, n: int, z: float = Z) -> tuple[float, float]:
    """Wilson score interval for k successes in n, well-behaved near 0 and 1."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))
    return (centre - half, centre + half)


def calibration(markets: Iterable[Market], minute: int) -> list[dict]:
    """Per 10c band of the last trade at `minute`: markets, mean price, YES rate, gap and its interval."""
    bands: dict[int, list[tuple[float, bool]]] = defaultdict(list)
    for m in markets:
        price = m.last[minute]
        if price is not None:
            bands[min(int(price * 10), 9)].append((price, m.yes))
    out = []
    for band in sorted(bands):
        rows = bands[band]
        n, k = len(rows), sum(won for _, won in rows)
        price = sum(p for p, _ in rows) / n
        lo, hi = wilson(k, n)
        out.append({"band": band, "low": band / 10, "high": (band + 1) / 10, "n": n, "price": price,
                    "actual": k / n, "gap": k / n - price, "lo": lo, "hi": hi})
    return out


def order_fee(contracts: float, price: float, coefficient: float, multiplier: float = 1.0) -> float:
    """Kalshi's taker fee for one order, ceil(m * k * C * P * (1 - P)) to the cent."""
    return math.ceil(multiplier * coefficient * contracts * price * (1 - price) * 100 - 1e-9) / 100


@dataclass(frozen=True)
class Bet:
    """A favourite bought at the entry minute.

    `quotes[k]` is the favourite's own (bid, ask) at the end of minute k, None if either side was
    missing; index 0 is unused.
    """

    open_ts: int
    series: str
    group: str
    side: str
    ask: float
    won: bool
    quotes: tuple[tuple[float, float] | None, ...]


def favourite(bid: float | None, ask: float | None) -> tuple[str, float] | None:
    """The side with the higher ask and that ask: YES costs the YES ask, NO costs 1 - the YES bid."""
    if bid is None or ask is None:
        return None
    yes, no = ask, round(1 - bid, 4)
    if abs(yes - no) < 1e-9:
        return None
    return ("yes", yes) if yes > no else ("no", no)


def own_quotes(side: str, bid: float | None, ask: float | None) -> tuple[float, float] | None:
    """A side's own (bid, ask) from the YES bid and ask."""
    if bid is None or ask is None:
        return None
    return (bid, ask) if side == "yes" else (round(1 - ask, 4), round(1 - bid, 4))


def favourites(markets: Iterable[Market], settings: ReplicationConfig) -> list[Bet]:
    """Every market whose favourite's ask at the entry minute is in [favourite_low, favourite_high]."""
    k = settings.entry_minute
    out = []
    for m in markets:
        fav = favourite(m.bid[k], m.ask[k])
        if fav is None or not settings.favourite_low <= fav[1] <= settings.favourite_high:
            continue
        side, ask = fav
        quotes = (None,) + tuple(own_quotes(side, m.bid[j], m.ask[j]) for j in range(1, 15))
        out.append(Bet(open_ts=m.open_ts, series=m.series, group=m.group, side=side, ask=ask,
                       won=(side == "yes") == m.yes, quotes=quotes))
    return out


def fill_price(bet: Bet, slippage: float) -> float:
    return min(bet.ask + slippage, MAX_PRICE)


def held(bet: Bet, fill: float, stake: float, coefficient: float, multiplier: float = 1.0) -> float:
    """Profit of a `stake` bet filled at `fill` and held to settlement, after the fee."""
    contracts = stake / fill
    return (contracts if bet.won else 0.0) - stake - order_fee(contracts, fill, coefficient, multiplier)


def kelly(bets: list[Bet], stake: float, slippage: float, coefficient: float,
          crypto_multiplier: float = 1.0) -> dict:
    """The one-bet Kelly fraction f* = (q - c) / (1 - c).

    q is how often the favourite won; c its average all-in cost per contract, the fill price plus
    the fee per contract on a `stake` order. Crypto markets pay `crypto_multiplier` times the fee.
    """
    if not bets:
        return {"bets": 0, "win": None, "cost": None, "kelly": None}
    q = sum(b.won for b in bets) / len(bets)
    costs = []
    for b in bets:
        fill = fill_price(b, slippage)
        contracts = stake / fill
        multiplier = crypto_multiplier if b.group == "crypto" else 1.0
        costs.append(fill + order_fee(contracts, fill, coefficient, multiplier) / contracts)
    cost = sum(costs) / len(costs)
    return {"bets": len(bets), "win": q, "cost": cost, "kelly": (q - cost) / (1 - cost)}


def kelly_table(bets: list[Bet], settings: ReplicationConfig, coefficient: float) -> list[dict]:
    """Kelly under three fills: as recorded; live-like (+slippage); live-like with the crypto fee raised."""
    scenarios = (
        ("recorded", "Recorded prices", 0.0, 1.0),
        ("live", f"+{settings.slippage * 100:g}¢ a contract", settings.slippage, 1.0),
        ("stress", f"+{settings.slippage * 100:g}¢ and {settings.stress_fee_multiplier:g}× crypto fee",
         settings.slippage, settings.stress_fee_multiplier),
    )
    return [{"scenario": key, "label": label, "slippage": slip, "crypto_fee_multiplier": mult,
             **kelly(bets, settings.stake, slip, coefficient, mult)}
            for key, label, slip, mult in scenarios]


def periods(bets: list[Bet], settings: ReplicationConfig) -> dict[str, list[Bet]]:
    """The bets before and after the split day."""
    split = day_ts(settings.split)
    return {"before": [b for b in bets if b.open_ts < split], "after": [b for b in bets if b.open_ts >= split]}


def regime(bets: list[Bet], settings: ReplicationConfig, coefficient: float) -> dict[str, dict]:
    """Bets, share lost, total profit and profit per bet (in cents) with live-like fills, per period."""
    out = {}
    for name, group in periods(bets, settings).items():
        total = sum(held(b, fill_price(b, settings.slippage), settings.stake, coefficient) for b in group)
        out[name] = {"bets": len(group),
                     "lost": sum(not b.won for b in group) / len(group) if group else None,
                     "total": total,
                     "per_bet_cents": total / len(group) * 100 if group else None}
    return out


def stop_rule(bets: list[Bet], level: float, settings: ReplicationConfig, coefficient: float) -> dict:
    """Sell each bet at its bid the first minute after entry (to minute 14) that the bid is at or under
    `level`, paying the fee again, instead of holding it. Positive `delta` means selling did better.
    `saved` is what selling recovered on bets that lost; `gave_up` what it cost on bets that won."""
    delta = saved = gave_up = 0.0
    sold = sold_won = 0
    for b in bets:
        minute = next((k for k in range(settings.entry_minute + 1, 15)
                       if b.quotes[k] is not None and b.quotes[k][0] <= level), None)
        if minute is None:
            continue
        fill = fill_price(b, settings.slippage)
        contracts = settings.stake / fill
        bid = b.quotes[minute][0]
        proceeds = contracts * bid - (order_fee(contracts, bid, coefficient) if bid > 0 else 0.0)
        cost = settings.stake + order_fee(contracts, fill, coefficient)
        change = (proceeds - cost) - held(b, fill, settings.stake, coefficient)
        delta += change
        sold += 1
        if b.won:
            sold_won += 1
            gave_up -= change
        else:
            saved += change
    return {"delta": delta, "sold": sold, "sold_won": sold_won, "saved": saved, "gave_up": gave_up}


def stop_table(bets: list[Bet], settings: ReplicationConfig, coefficient: float) -> list[dict]:
    split = periods(bets, settings)
    return [{"level": level, **{name: stop_rule(group, level, settings, coefficient) for name, group in split.items()}}
            for level in settings.stops]
