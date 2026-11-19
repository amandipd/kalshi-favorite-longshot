"""Split the thin 80-90c favourite cell by side (Yes vs No favourite) and by category.

Same definitions as the Oct 25 new-listings check: price = Yes price 1h before close,
thin = lowest volume third over the whole sample, t clustered on event,
train/test cut at the 60th percentile of close time.
A No favourite at 80-90c is a Yes price of 10-20c; buying No earns p - y.
"""
import numpy as np
import pandas as pd

d = pd.read_parquet('data/processed/contracts.parquet')
d['y'] = d.outcome.astype(float)
d['series'] = d.ticker.str.split('-').str[0]
d['vq'] = pd.qcut(d.volume, 3, labels=['thin', 'mid', 'thick'], duplicates='drop')
cut = d.close_ts.quantile(0.60)

# edge for whoever buys the favourite side, per contract
yes_fav = d[(d.vq == 'thin') & (d.implied_price >= 0.80) & (d.implied_price < 0.90)].copy()
yes_fav['edge'] = yes_fav.y - yes_fav.implied_price
yes_fav['fav_price'] = yes_fav.implied_price
no_fav = d[(d.vq == 'thin') & (d.implied_price > 0.10) & (d.implied_price <= 0.20)].copy()
no_fav['edge'] = no_fav.implied_price - no_fav.y
no_fav['fav_price'] = 1 - no_fav.implied_price


def stats(s):
    if len(s) < 30:
        return f"n={len(s):>5}  too few"
    g = s.edge.groupby(s.event_ticker).sum()
    se = np.sqrt((g ** 2).sum()) / len(s)
    m = s.edge.mean()
    return (f"n={len(s):>5} events={s.event_ticker.nunique():>5} "
            f"fav price={s.fav_price.mean():.3f} won={(s.edge + s.fav_price).mean():.3f} "
            f"edge={m * 100:+6.2f}c t={m / se:5.2f}")


def report(name, cell):
    print(f"\n=== {name} ===")
    print("headline        ", stats(cell))
    print("train (pre-cut) ", stats(cell[cell.close_ts < cut]))
    print("test (post-cut) ", stats(cell[cell.close_ts >= cut]))
    big = cell.series.value_counts().index[:2].tolist()
    print(f"drop 2 biggest  ", stats(cell[~cell.series.isin(big)]), big)
    for cat, g in cell.groupby('category'):
        print(f"  {cat:<13} ", stats(g))
    nonsport = cell[cell.category != 'Sports']
    print("  all non-sports", stats(nonsport))
    print("  top series:", cell.series.value_counts().head(6).to_dict())


print("cut:", cut)
report("YES favourite, thin, 80-90c (the Oct 25 cell)", yes_fav)
report("NO favourite, thin, 80-90c (Yes priced 10-20c)", no_fav)

# Mirror check: two-team winner markets list one market per team, so team A
# "Yes at 85c" and team B "No at 85c" can be the same bet seen twice.
both = set(yes_fav.event_ticker) & set(no_fav.event_ticker)
print(f"\nevents in BOTH cells: {len(both)} "
      f"(of {yes_fav.event_ticker.nunique()} yes-fav, {no_fav.event_ticker.nunique()} no-fav)")
report("YES favourite, events NOT in the other cell", yes_fav[~yes_fav.event_ticker.isin(both)])
report("NO favourite, events NOT in the other cell", no_fav[~no_fav.event_ticker.isin(both)])

# Who set the price? A Yes taker trades at the Yes ask, so the No side would
# have cost more than 1 - price. Keep only prices a favourite buyer actually paid.
import json, pathlib
taker = {}
for f in pathlib.Path('data/raw_trades/kalshi/T1h').rglob('*.jsonl'):
    for line in f.open(encoding='utf-8'):
        r = json.loads(line)
        if r.get('trade'):
            taker[r['ticker']] = r['trade'].get('taker_side')
for name, cell, fav in [("YES favourite", yes_fav, 'yes'), ("NO favourite", no_fav, 'no')]:
    cell = cell.assign(taker=cell.ticker.map(taker))
    print(f"\n{name}: price set by", cell.taker.value_counts(dropna=False).to_dict())
    report(f"{name}, price paid by a favourite buyer", cell[cell.taker == fav])
    report(f"{name}, price paid by an underdog buyer", cell[(cell.taker.notna()) & (cell.taker != fav)])
