"""Read live.jsonl (live.py): when each minute's history point appears and stops changing, and the depth on offer at
the favourite's ask near minute 3. Prices only; no result is read. Writes live_report.json.

    python live_report.py [live.jsonl] [live_report.json]
"""
import json
import os
import sys
import statistics as st
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))


def main(src="live.jsonl", dst="live_report.json"):
    seen = defaultdict(list)          # (slug, stamp) -> [(w, (long, short))]
    books = []
    with open(os.path.join(HERE, src)) as f:
        for line in f:
            r = json.loads(line)
            if r["k"] == "h":
                for t, lp, sp in r["pts"]:
                    seen[(r["slug"], t)].append((r["w"], (lp, sp)))
            elif r["k"] == "book":
                books.append(r)
    first, settled, polls = defaultdict(list), defaultdict(list), defaultdict(int)
    for (slug, t), obs in seen.items():
        obs.sort()
        if not 0 <= t <= 240 or obs[0][0] > t + 60:      # only points first seen while their minute was running
            continue
        first[t].append(obs[0][0] - t)
        last_change = obs[0][0]
        for (w0, v0), (w1, v1) in zip(obs, obs[1:]):
            if v1 != v0:
                last_change = w1
        settled[t].append(last_change - t)
        polls[t] += len(obs)
    timing = {}
    for t in sorted(first):
        timing[t] = {"points": len(first[t]), "first_seen_after_stamp_s": round(st.median(first[t]), 1),
                     "last_change_after_stamp_s": round(st.median(settled[t]), 1),
                     "last_change_p90_s": round(sorted(settled[t])[int(0.9 * (len(settled[t]) - 1))], 1)}
        print(t, timing[t])

    depth = []
    for b in books:
        if not b["asks"] or not b["bids"]:
            continue
        ask = min(b["asks"])                      # [price, contracts], the Yes ask
        bid = max(b["bids"])                      # the Yes bid; the No ask is 1 - it
        yes_fav = ask[0] > round(1 - bid[0], 4)
        top = ask[0] if yes_fav else round(1 - bid[0], 4)
        at_top = ask[1] if yes_fav else bid[1]
        within = (sum(q for p, q in b["asks"] if p <= ask[0] + 0.0101) if yes_fav
                  else sum(q for p, q in b["bids"] if p >= bid[0] - 0.0101))
        depth.append({"slug": b["slug"], "book_age_at_read_s": None if b["bt"] is None else round(b["w"] - b["bt"], 1),
                      "book_time_s": b["bt"], "fav": "yes" if yes_fav else "no", "top": top,
                      "contracts_at_top": at_top, "contracts_within_1c": within, "dollars_at_top": round(at_top * top, 2)})
    fav = [x for x in depth if 0.92 <= x["top"] <= 0.99]
    summary = {"books": len(depth), "favourite_92_99": len(fav)}
    if fav:
        summary["median_dollars_at_top"] = st.median(x["dollars_at_top"] for x in fav)
        summary["min_dollars_at_top"] = min(x["dollars_at_top"] for x in fav)
        summary["median_contracts_within_1c"] = st.median(x["contracts_within_1c"] for x in fav)
    print(summary)
    with open(os.path.join(HERE, dst), "w") as f:
        json.dump({"timing": timing, "depth_summary": summary, "depth": depth}, f, indent=1)


if __name__ == "__main__":
    main(*sys.argv[1:3])
