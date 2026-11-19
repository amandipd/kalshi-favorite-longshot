"""How stale is the T-1h price in the thin 80-90c cells, by who set it?"""
import json, pathlib
import pandas as pd
d = pd.read_parquet('data/processed/contracts.parquet')
d['vq'] = pd.qcut(d.volume, 3, labels=['thin', 'mid', 'thick'], duplicates='drop')
rows = {}
for f in pathlib.Path('data/raw_trades/kalshi/T1h').rglob('*.jsonl'):
    for line in f.open(encoding='utf-8'):
        r = json.loads(line)
        if r.get('trade'):
            age = (pd.Timestamp(r['cutoff_ts']) - pd.Timestamp(r['trade']['created_time'])).total_seconds() / 60
            rows[r['ticker']] = (r['trade'].get('taker_side'), age)
d['taker'] = d.ticker.map(lambda t: rows.get(t, (None, None))[0])
d['age_min'] = d.ticker.map(lambda t: rows.get(t, (None, None))[1])
thin = d[d.vq == 'thin']
cells = {'YES fav': (thin[(thin.implied_price >= .8) & (thin.implied_price < .9)], 'yes'),
         'NO fav': (thin[(thin.implied_price > .1) & (thin.implied_price <= .2)], 'no')}
for name, (c, fav) in cells.items():
    c = c[c.taker == fav]
    y = c.outcome if fav == 'yes' else 1 - c.outcome
    p = c.implied_price if fav == 'yes' else 1 - c.implied_price
    c = c.assign(edge=y - p)
    print(f"{name} (paid by favourite buyer): price age minutes, median {c.age_min.median():.0f}, "
          f"75th pct {c.age_min.quantile(.75):.0f}")
    for lo, hi in [(0, 10), (10, 60), (60, 1e9)]:
        s = c[(c.age_min >= lo) & (c.age_min < hi)]
        print(f"   age {lo:>3}-{hi if hi < 1e9 else 'inf'} min: n={len(s):>4} edge={s.edge.mean()*100:+.2f}c")
