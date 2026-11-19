"""Read the opening-price fetch and report it in the order the prereg demands.

    python research/opening_price/analyze_opening.py      (from the repository root)

Reports retention and the dropout comparison BEFORE any edge number, because a
sample selected on whether a market traded early is the most likely way this
whole exercise misleads us -- the same shape of trap as the pinned-price problem
that forced the T-1h horizon in the first place (docs/adr/003).

Then scores the **train half only**. research/opening_price/PREREG.md commits to
scoring the test half exactly once, later, and only if the train half justifies
it. This script will not print a test-half edge; that is deliberate, not an
oversight.

Outcomes come from the raw layer rather than data/processed/contracts.parquet,
so this sample is not narrowed by the study's own T-1h exclusion (about 30% of
markets have no trade an hour before close, and those are exactly the thin
markets the hypothesis is about).
"""

from __future__ import annotations

import json
import statistics
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

RAW = Path("data/raw/kalshi")
OPENED = Path("data/raw_trades/kalshi/OPENFIRST")
BINARY = {"yes", "no"}
# Kalshi's taker fee, as verified against the CFTC rule filing and used in
# kalshi_calibration/strategy/backtest.py. Per contract, so no ceiling applied here.
FEE_COEFFICIENT = 0.07


def load_outcomes() -> pd.DataFrame:
    """ticker -> how it settled, plus what we need to cluster and split on."""
    rows = {}
    for cat in sorted(p for p in RAW.iterdir() if p.is_dir()):
        for sd in sorted(p for p in cat.iterdir() if p.is_dir()):
            for pg in sorted(sd.glob("page_*.json")):
                for m in json.loads(pg.read_text(encoding="utf-8")).get("markets", []):
                    t = m.get("ticker")
                    if not t or t in rows or m.get("result") not in BINARY:
                        continue
                    rows[t] = {
                        "ticker": t,
                        "event_ticker": m.get("event_ticker"),
                        "category": cat.name,
                        "series": sd.name,
                        "outcome": 1.0 if m["result"] == "yes" else 0.0,
                        "close_time": m.get("close_time"),
                        "open_time": m.get("open_time"),
                    }
    return pd.DataFrame(rows.values())


def load_opened() -> pd.DataFrame:
    rows = []
    for f in OPENED.rglob("*.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            ft = r.get("first_trade")
            rows.append(
                {
                    "ticker": r["ticker"],
                    "open_price": float(ft["yes_price_dollars"]) if ft else np.nan,
                    "seconds_after_open": r.get("seconds_after_open"),
                    "trades_seen": r.get("trades_seen", 0),
                    "window_hours_used": r.get("window_hours_used"),
                    "complete": r.get("complete", False),
                }
            )
    return pd.DataFrame(rows)


def clustered_se(df: pd.DataFrame, price_col: str) -> float:
    """Standard error of the mean gap, clustering on event (Liang-Zeger).

    Contracts on one event are not independent draws -- a 250-runner field is
    one outcome expressed 250 times -- so treating them as independent would
    make every interval too narrow.
    """
    resid = df.outcome - df[price_col]
    per_event = resid.groupby(df.event_ticker).sum()
    return float(np.sqrt((per_event**2).sum()) / len(df))


def band_table(df: pd.DataFrame, label: str, price_col: str = "open_price") -> None:
    bands = [(0.60, 0.80), (0.80, 0.90), (0.90, 0.95), (0.95, 1.00)]
    print(f"\n--- {label}  (n={len(df):,}) ---")
    print(
        f"{'band':>11} {'markets':>8} {'events':>7} {'priced':>7} {'won':>7} "
        f"{'gross':>8} {'fee':>6} {'net':>8} {'t':>6}"
    )
    for lo, hi in bands:
        s = df[(df[price_col] >= lo) & (df[price_col] < hi)]
        if len(s) < 60:
            print(f"{f'{lo:.2f}-{hi:.2f}':>11} {len(s):>8}   too thin to read")
            continue
        p = s[price_col].mean()
        gross = s.outcome.mean() - p
        fee = FEE_COEFFICIENT * p * (1 - p)
        se = clustered_se(s, price_col)
        t = gross / se if se else float("nan")
        print(
            f"{f'{lo:.2f}-{hi:.2f}':>11} {len(s):>8,} {s.event_ticker.nunique():>7,} "
            f"{p:>7.3f} {s.outcome.mean():>7.3f} {gross*100:>7.2f}c {fee*100:>5.2f}c "
            f"{(gross-fee)*100:>7.2f}c {t:>6.2f}"
        )


def main() -> None:
    opened = load_opened()
    if opened.empty:
        print("nothing fetched yet")
        return
    outcomes = load_outcomes()
    d = opened.merge(outcomes, on="ticker", how="inner")
    d["close_ts"] = pd.to_datetime(d.close_time, format="mixed", utc=True)
    d["priced"] = d.open_price.notna()

    print("=" * 74)
    print("1. RETENTION -- the share of markets we got a usable opening price for")
    print("=" * 74)
    print(f"fetched            : {len(opened):,}")
    print(f"matched an outcome : {len(d):,}")
    print(f"priced             : {d.priced.sum():,} = {100*d.priced.mean():.1f}%")
    print(f"never traded early : {(~d.priced & d.complete).sum():,}")
    print(f"never reached open : {(~d.priced & ~d.complete).sum():,}")

    print("\nby category:")
    for cat, g in sorted(d.groupby("category")):
        print(f"  {cat:<12} {int(g.priced.sum()):>6,}/{len(g):<7,} = {100*g.priced.mean():>5.1f}%")

    print("\n" + "=" * 74)
    print("2. DO THE DROPOUTS DIFFER FROM THE KEEPERS? (the bias check)")
    print("=" * 74)
    kept, lost = d[d.priced], d[~d.priced]
    print(f"{'':<22} {'priced':>12} {'not priced':>12}")
    print(f"{'markets':<22} {len(kept):>12,} {len(lost):>12,}")
    print(f"{'won (base rate)':<22} {kept.outcome.mean():>12.3f} {lost.outcome.mean():>12.3f}")
    if len(lost):
        print("\ntop series among the dropouts:")
        for s, k in Counter(lost.series).most_common(6):
            share = 100 * k / max(1, (d.series == s).sum())
            print(f"  {s:<22} {k:>6,}  ({share:.0f}% of that series)")

    print("\n" + "=" * 74)
    print("3. HOW LONG AFTER THE OPEN DID THE FIRST TRADE LAND?")
    print("=" * 74)
    mins = sorted(kept.seconds_after_open.dropna() / 60)
    if mins:
        print(
            f"  median {statistics.median(mins):,.0f} min"
            f" | 25% {mins[len(mins)//4]:,.0f} | 75% {mins[3*len(mins)//4]:,.0f}"
        )
        for w in (0.25, 1, 6, 24, 72):
            inside = sum(1 for x in mins if x <= w * 60)
            print(f"  traded within {w:>5}h: {inside:>7,} = {100*inside/len(d):>5.1f}% of all")

    print("\n" + "=" * 74)
    print("4. THE TRAIN HALF ONLY -- the test half is NOT scored here")
    print("=" * 74)
    cut = d.close_ts.quantile(0.60)
    train = kept[kept.close_ts < cut].copy()
    print(f"split at the 60th percentile of close date: {cut}")
    print(f"train markets priced: {len(train):,}   (test half held back: "
          f"{len(kept[kept.close_ts >= cut]):,})")

    band_table(train, "ALL train markets, at the OPENING price")

    # The prereg bans whole-life volume as a filter, because it is not knowable
    # at entry. Trades per hour in the opening window is, and unlike a raw count
    # it is comparable across markets that were answered at different windows.
    train["trades_per_hour"] = train.trades_seen / train.window_hours_used
    try:
        train["liq"] = pd.qcut(
            train.trades_per_hour, 3, labels=["thin", "mid", "thick"], duplicates="drop"
        )
        for q in ("thin", "thick"):
            band_table(train[train.liq == q], f"train, {q} (trades per hour in the opening window)")
    except ValueError:
        print("\n(not enough spread in trades-per-hour to cut terciles yet)")

    # Secondary proxy: a market that took a long time to trade at all is thin by
    # definition, and the delay is observable at entry.
    try:
        train["slow"] = pd.qcut(
            train.seconds_after_open, 3, labels=["fast", "mid", "slow"], duplicates="drop"
        )
        for q in ("slow", "fast"):
            band_table(train[train.slow == q], f"train, {q} to first trade")
    except ValueError:
        pass

    print("\n" + "=" * 74)
    print("For comparison only -- the SAME train markets at the T-1h price, which")
    print("is where the +5.1c that motivated this was measured.")
    print("=" * 74)
    proc = Path("data/processed/contracts.parquet")
    if proc.exists():
        t1 = pd.read_parquet(proc)[["ticker", "implied_price"]]
        cmp_df = train.merge(t1, on="ticker", how="inner")
        if len(cmp_df) > 200:
            band_table(cmp_df, "train, at the T-1h price", price_col="implied_price")
        else:
            print(f"only {len(cmp_df)} train markets have a T-1h price; skipping")


if __name__ == "__main__":
    main()
