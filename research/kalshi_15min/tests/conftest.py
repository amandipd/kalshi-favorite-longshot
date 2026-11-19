"""Shared fixtures for the 15-minute research's tests: a synthetic market history every script can run on.

The research scripts read their data from the working directory -- universe.json and the four minute files
-- and several compute dates from it at import time (strategies_backtest.PERIODS calls history.end()). So
the session builds one seeded, synthetic history in a temporary folder, moves into it, and only then imports
the research modules. Nothing here reads the real CSVs or touches the network.

The synthetic market is shaped like the real one where the scripts care:

    76 days from Jul 18, 2026, eight windows a day (including the 8:30, 9:30, 10:00 and 2:00 pm ET slots
    and the two Fed decision afternoons the research marks), six series across crypto, metals, energy, FX
    and Coin Race; prices that random-walk in log-odds with occasional jumps, so favourites form, crash and
    recover inside a window; a favourite-longshot tilt in how they settle; a few markets with no quotes
    before minute 4, a few with no trade by minute 8, and one market repeated across two minute files.
    Before Jul 18, as in the real history, only crypto: BTC and ETH for a week in January (Eastern winter
    time) and the week before Jul 18, in minutes_pre.csv.

    python -m pytest research/kalshi_15min/tests -q
"""

from __future__ import annotations

import csv
import importlib
import json
import math
import os
import random
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

RESEARCH = Path(__file__).resolve().parent.parent
REPO = RESEARCH.parent.parent
for path in (RESEARCH, REPO, REPO / "bot"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

UTC = timezone.utc
FIRST_DAY = date(2026, 7, 18)
DAYS = 76                                                      # Jul 18 .. Oct 1
PRE_DAYS = [date(2026, 1, 12) + timedelta(days=k) for k in range(7)] + [date(2026, 7, 11) + timedelta(days=k) for k in range(7)]
PRE_SERIES = ("KXBTC15M", "KXETH15M")                          # crypto only before Jul 18
SLOTS = ["00:00", "03:15", "07:30", "12:30", "13:30", "14:00", "18:00", "21:45"]   # UTC
SERIES = [  # ticker, group, category, file it lives in when not in minutes_30d.csv
    ("KXBTC15M", "crypto", "Crypto", "ext"),
    ("KXETH15M", "crypto", "Crypto", "ext"),
    ("KXGOLD15M", "metals", "Commodities", "ext"),
    ("KXWTI15M", "energy", "Commodities", "ext"),
    ("KXEURUSD15M", "fx", "Financials", "new"),
    ("KXCRYPTOLEAD15M", "coin race", "Crypto", "new"),
]
MINUTES = range(1, 16)
FIELDS = (["series", "ticker", "open_time", "resolved_yes"]
          + [f"p{k}" for k in MINUTES] + [f"b{k}" for k in MINUTES] + [f"a{k}" for k in MINUTES])
THIRTY_DAYS = (datetime(2026, 8, 24, tzinfo=UTC), datetime(2026, 9, 24, tzinfo=UTC))


def iso(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def ticker_for(series: str, opened: datetime, suffix: str = "00") -> str:
    close = opened + timedelta(minutes=15)
    return f"{series}-{close:%y%b%d%H%M}".upper() + f"-{suffix}"


def market_row(rng: random.Random, series: str, ticker: str, opened: datetime) -> dict:
    """One market's minute-file row: last trade, YES bid and YES ask at the end of each minute, and its result."""
    x = math.log((p0 := rng.uniform(0.25, 0.75)) / (1 - p0))
    row = {"series": series, "ticker": ticker, "open_time": iso(opened)}
    blank_until = 4 if rng.random() < 0.04 else 0            # no quotes yet in the first minutes
    no_trade_by_8 = rng.random() < 0.02
    for k in MINUTES:
        late = k > 8                                          # after entry the market mostly settles down ...
        x += rng.gauss(0, 0.3 if late else 0.55)
        if rng.random() < (0.025 if late else 0.06):
            x += rng.gauss(0, 2.5)                            # ... but news can still flip the favourite in a minute
        p = sigmoid(x)
        spread = rng.choice([0.01, 0.01, 0.01, 0.02, 0.03, 0.05])
        bid = min(max(round(p - spread / 2, 3), 0.001), 0.998)
        ask = min(max(round(p + spread / 2, 3), bid + 0.001), 0.999)
        last = min(max(round(p, 3), 0.001), 0.999)
        blank = k < blank_until
        row[f"b{k}"] = "" if blank else bid
        row[f"a{k}"] = "" if blank else round(ask, 3)
        row[f"p{k}"] = "" if blank or (no_trade_by_8 and k <= 8) else last
    # Like the real history: favourites settle worse than their price before Aug 24 and better after it.
    tilt = 1.15 if opened < THIRTY_DAYS[0] else 2.0
    row["resolved_yes"] = "1" if rng.random() < sigmoid(tilt * x) else "0"
    return row


def build_history(folder: Path, seed: int = 2026) -> dict:
    """Write universe.json and the four minute files into `folder`. Returns what was written, for assertions."""
    rng = random.Random(seed)
    rows = {"30d": [], "new": [], "ext": [], "pre": []}
    for day in range(DAYS):
        d = FIRST_DAY + timedelta(days=day)
        for slot in SLOTS:
            h, m = map(int, slot.split(":"))
            opened = datetime(d.year, d.month, d.day, h, m, tzinfo=UTC)
            for series, group, _, home in SERIES:
                suffixes = ["BTC", "ETH"] if group == "coin race" else ["00"]
                for suffix in suffixes:
                    row = market_row(rng, series, ticker_for(series, opened, suffix), opened)
                    in_30d = home == "ext" and THIRTY_DAYS[0] <= opened < THIRTY_DAYS[1]
                    rows["30d" if in_30d else home].append(row)
    pre_rng = random.Random(seed + 1)                         # its own draws, so the markets from Jul 18 stay the same
    for d in PRE_DAYS:
        for slot in SLOTS:
            h, m = map(int, slot.split(":"))
            opened = datetime(d.year, d.month, d.day, h, m, tzinfo=UTC)
            for series in PRE_SERIES:
                rows["pre"].append(market_row(pre_rng, series, ticker_for(series, opened), opened))
    # One market recorded twice, as happens when two fetches overlap: the first file read must win.
    duplicate = dict(rows["30d"][0], resolved_yes="0" if rows["30d"][0]["resolved_yes"] == "1" else "1")
    rows["ext"].append(duplicate)
    for name, file_rows in rows.items():
        with (folder / f"minutes_{name}.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(file_rows)
    universe = [{"ticker": s, "title": f"{s} 15-minute", "group": g, "status": "live", "markets": 1, "first": None,
                 "last": None, "feeMultiplier": 1, "inOriginal": s not in ("KXEURUSD15M", "KXCRYPTOLEAD15M")}
                for s, g, _, _ in SERIES]
    universe.append({"ticker": "KX10YRRATE15M", "title": "rates", "group": "rates", "status": "not launched",
                     "markets": 0, "first": None, "last": None, "feeMultiplier": 1, "inOriginal": False})
    (folder / "universe.json").write_text(json.dumps({"fetched": "2026-10-02T00:00:00Z", "series": universe}),
                                          encoding="utf-8")
    every = rows["30d"] + rows["new"] + rows["ext"][:-1] + rows["pre"]
    return {"rows": every, "duplicate": duplicate, "first_copy": rows["30d"][0]}


def build_quotes(folder: Path, rows: list[dict]) -> None:
    """quotes_30d.csv (fetch_quotes.py's columns) for the month it covers: favourites at 85c and up."""
    rng = random.Random(7)
    with (folder / "quotes_30d.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["series", "ticker", "open_time", "price_8min", "yes_bid", "yes_ask",
                                           "vol_0_8", "vol_min8", "mins_since_trade", "oi_8", "price_7", "resolved_yes"])
        w.writeheader()
        for r in rows:
            opened = datetime.fromisoformat(r["open_time"].replace("Z", "+00:00"))
            if not THIRTY_DAYS[0] <= opened < THIRTY_DAYS[1] or r["p8"] == "" or r["b8"] == "":
                continue
            if max(float(r["p8"]), 1 - float(r["p8"])) < 0.85:
                continue
            w.writerow({"series": r["series"], "ticker": r["ticker"], "open_time": r["open_time"], "price_8min": r["p8"],
                        "yes_bid": r["b8"], "yes_ask": r["a8"], "vol_0_8": rng.randint(0, 5000),
                        "vol_min8": rng.randint(0, 300), "mins_since_trade": rng.choice(["", 0, 0, 1, 2, 5]),
                        "oi_8": rng.randint(0, 9000), "price_7": r["p7"], "resolved_yes": r["resolved_yes"]})


def build_other_markets(folder: Path) -> None:
    """other_markets.json and other_hours.csv (fetch_other.py) for two hourly and one daily series."""
    rng = random.Random(11)
    series, rows = [], []
    for name, freq, unit, cat in (("KXBTCD", "hourly", "min", "Crypto"), ("KXINXU", "hourly", "min", "Financials"),
                                  ("KXHIGHNY", "daily", "hour", "Climate")):
        markets = []
        for i in range(260):
            close = datetime(2026, 7, 19, tzinfo=UTC) + timedelta(hours=7 * i + (3 if freq == "daily" else 0))
            ticker = f"{name}-{i:04d}"
            result = "yes" if rng.random() < 0.5 else "no"
            markets.append({"ticker": ticker, "event": f"{name}-E{i // 4}", "open": iso(close - timedelta(hours=1)),
                            "close": iso(close), "result": result, "volume": "100"})
            row = {"series": name, "ticker": ticker, "event": f"{name}-E{i // 4}", "close": iso(close),
                   "result": result, "volume": "100", "unit": unit}
            p = rng.uniform(0.85, 0.999) if rng.random() < 0.7 else rng.uniform(0.01, 0.99)
            for k in range(61):
                b, a = max(0.0, round(p - rng.choice([0.005, 0.01, 0.05]), 3)), min(1.0, round(p + 0.005, 3))
                row[f"b{k}"], row[f"a{k}"] = b, a
            rows.append(row)
        series.append({"series": name, "title": name, "category": cat, "frequency": freq, "fee_type": "quadratic",
                       "fee_multiplier": 1 if name != "KXBTCD" else None, "markets": markets})
    (folder / "other_markets.json").write_text(json.dumps(series), encoding="utf-8")
    fields = ["series", "ticker", "event", "close", "result", "volume", "unit"] + [f"{x}{k}" for k in range(61) for x in "ba"]
    with (folder / "other_hours.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


@pytest.fixture(scope="session")
def study(tmp_path_factory):
    """The synthetic history, the working directory moved into it for the whole session, and the research
    modules imported from there. Yields a namespace: `.dir`, `.data` (what was written) and each module."""
    folder = tmp_path_factory.mktemp("kalshi_15min")
    data = build_history(folder)
    build_quotes(folder, data["rows"])
    build_other_markets(folder)
    old = os.getcwd()
    os.chdir(folder)
    names = ["history", "minutes", "analyze", "exit_timing", "strategies_backtest", "findings", "sizing", "by_month",
             "risk_rules", "stress_signals", "all_markets", "other_markets", "key_stats", "fetch_all15",
             "fetch_minutes", "fetch_history", "fetch_other", "fetch_quotes", "backtest_large",
             "filter_search"]
    mods = {n: importlib.import_module(n) for n in names}
    try:
        yield SimpleNamespace(dir=folder, data=data, **mods)
    finally:
        os.chdir(old)
