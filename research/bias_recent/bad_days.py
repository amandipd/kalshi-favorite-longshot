"""Were the live bot's last two weeks (Oct 20 - Nov 3 2026) replicated by the rule on Kalshi's own prices, and did the
past data have days and two-week stretches as bad? The rule as in score.py (lab/common.live_rule at 92c, $10 bets at
the recorded ask, fee included).

    python bad_days.py <live pull json>
"""
import csv
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import score as S  # noqa: E402

C = S.C
PT = ZoneInfo("America/Los_Angeles")
day_of = lambda t: datetime.fromtimestamp(float(t), PT).date()


def load_all_recent():
    """recent_minutes.csv + recent_minutes_nov.csv, de-duplicated by ticker, in score.load_recent's shape."""
    rows, seen = [], set()
    for name in ("recent_minutes.csv", "recent_minutes_nov.csv"):
        for r in csv.DictReader(open(os.path.join(HERE, name))):
            if r["ticker"] not in seen:
                seen.add(r["ticker"])
                rows.append(r)
    num = lambda v: float(v) if v != "" else np.nan
    d = {"ticker": np.array([r["ticker"] for r in rows]), "series": np.array([r["series"] for r in rows]),
         "group": np.array([S.GROUPS[r["series"]] for r in rows]),
         "open_ts": np.array([int(datetime.fromisoformat(r["open_time"].replace("Z", "+00:00")).timestamp())
                              for r in rows]),
         "yes": np.array([r["resolved_yes"] == "1" for r in rows], dtype=np.int8)}
    for k, p in (("bid", "b"), ("ask", "a"), ("last", "p")):
        d[k] = np.round(np.array([[num(r[f"{p}{m}"]) for m in range(1, 16)] for r in rows], dtype=np.float64), 4)
    return d


def daily(t, pnl, cost, won, price):
    out = defaultdict(lambda: [0, 0, 0.0, 0.0, 0.0])   # bets, lost, predicted, pnl, staked
    for i in range(len(t)):
        r = out[day_of(t[i])]
        r[0] += 1; r[1] += (not won[i]); r[2] += 1 - price[i]; r[3] += pnl[i]; r[4] += cost[i]
    return out


def main():
    rb = S.bets(load_all_recent())
    live = [b for b in json.load(open(sys.argv[1]))["bets"] if b["status"] in ("won", "lost")]
    rd = daily(rb["t"], rb["pnl"], rb["cost"], rb["won"], rb["price"])
    ld = daily([b["window_open"] for b in live], [b["pnl"] for b in live], [b["cost"] + b["fee"] for b in live],
               [b["status"] == "won" for b in live], [b["price"] for b in live])
    first, last = datetime(2026, 10, 20).date(), datetime(2026, 11, 3).date()
    print("DAY BY DAY, PT: the rule on Kalshi's prices | the live bot   (bets, lost vs predicted, cents per $1)")
    tot = {"rule": [0, 0, 0.0, 0.0, 0.0], "live": [0, 0, 0.0, 0.0, 0.0]}
    dday = first
    while dday <= last:
        r, l = rd.get(dday, [0, 0, 0, 0, 1e-9]), ld.get(dday, [0, 0, 0, 0, 1e-9])
        for k, v in (("rule", r), ("live", l)):
            tot[k] = [a + b for a, b in zip(tot[k], v)]
        print(f"  {dday:%a %b %d}  rule {r[0]:>4} {r[1]:>3} vs {r[2]:5.1f} {r[3] / r[4] * 100:+6.2f}c | "
              f"live {l[0]:>4} {l[1]:>3} vs {l[2]:5.1f} {l[3] / l[4] * 100:+6.2f}c  ${l[3]:+8.2f}")
        dday += timedelta(days=1)
    for k, v in tot.items():
        print(f"  TOTAL {k}: {v[0]} bets, lost {v[1]} vs {v[2]:.1f}, {v[3] / v[4] * 100:+.2f}c per $1, ${v[3]:+.2f} at its sizes")
    worst_live = min((v[3] / v[4] * 100, d) for d, v in ld.items() if d >= first and v[0] > 50)
    print(f"  worst live day {worst_live[1]}: {worst_live[0]:+.2f}c per $1")

    # the past: days and 14-day stretches
    pb = S.bets(C.load())
    pdd = daily(pb["t"], pb["pnl"], pb["cost"], pb["won"], pb["price"])
    for k, v in rd.items():          # recent days not in the past file
        if k not in pdd:
            pdd[k] = v
    days = sorted(d for d, v in pdd.items() if v[0] >= 50)
    cents = {d: pdd[d][3] / pdd[d][4] * 100 for d in days}
    excess = {d: pdd[d][1] - pdd[d][2] for d in days}
    for lab, since in (("whole history", datetime(2025, 12, 20).date()), ("since Jul 18", datetime(2026, 7, 18).date()),
                       ("since Aug 24", datetime(2026, 8, 24).date())):
        ds = [d for d in days if since <= d < first]
        c = np.array([cents[d] for d in ds])
        print(f"\nPAST DAYS ({lab}, to Oct 19, days with 50+ bets): {len(ds)} days; losing days {np.mean(c < 0):.0%}; "
              f"days at {worst_live[0]:.2f}c or worse: {int((c <= worst_live[0]).sum())} ({np.mean(c <= worst_live[0]):.1%})")
        for dd in sorted(ds, key=lambda d: cents[d])[:5]:
            v = pdd[dd]
            print(f"    {dd:%a %b %d %Y}: {v[0]} bets, lost {v[1]} vs {v[2]:.1f}, {cents[dd]:+.2f}c per $1")
        # 15-day stretches (Oct 20 - Nov 3 is 15 days), rolling by day
        st = []
        for i in range(len(ds) - 14):
            win = ds[i:i + 15]
            if (win[-1] - win[0]).days != 14:
                continue
            p = sum(pdd[d][3] for d in win); s = sum(pdd[d][4] for d in win)
            st.append(p / s * 100)
        st = np.array(st)
        rule_now = tot["rule"][3] / tot["rule"][4] * 100
        live_now = tot["live"][3] / tot["live"][4] * 100
        print(f"  15-day stretches: {len(st)}; losing {np.mean(st < 0):.0%}; as bad as the rule's {rule_now:+.2f}c: "
              f"{np.mean(st <= rule_now):.0%}; as bad as live {live_now:+.2f}c: {np.mean(st <= live_now):.0%}; "
              f"worst {st.min():+.2f}c; median {np.median(st):+.2f}c")

    # pile-ups: windows with 6+ losses, any market type; metals windows with 3+ losses
    def pileups(b, lo, hi):
        sel = (b["t"] >= lo) & (b["t"] < hi)
        w = defaultdict(lambda: [0, 0])
        for t, won, g in zip(b["t"][sel], b["won"][sel], b["group"][sel]):
            w[t][0] += not won; w[t][1] += (not won) and g == "metals"
        days_n = (hi - lo) / 86400
        six = sum(1 for v in w.values() if v[0] >= 6); met = sum(1 for v in w.values() if v[1] >= 3)
        return six, met, days_n
    aug24, oct20 = C.PERIODS[2][2], datetime(2026, 10, 20, tzinfo=PT).timestamp()
    for lab, b, lo, hi in (("past Aug 24 - Oct 8", pb, aug24, C.PERIODS[3][3]),
                           ("past whole history", pb, pb["t"].min(), C.PERIODS[3][3]),
                           ("recent Oct 9 - 19", rb, rb["t"].min(), oct20), ("recent Oct 20 - Nov 3", rb, oct20, rb["t"].max() + 900)):
        six, met, n = pileups(b, lo, hi)
        print(f"PILE-UPS {lab}: windows with 6+ losses {six} ({six / n * 7:.2f} a week); "
              f"windows with 3+ metals losses {met} ({met / n * 7:.2f} a week); {n:.0f} days")


if __name__ == "__main__":
    main()
