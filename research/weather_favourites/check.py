"""PREREG.md's settlement check: each test market's settled value against the NWS daily climate report for its
station (Iowa Environmental Mesonet copy, data/cli/<station>.json from fetch.py cli). Kalshi's result still decides
every payoff; this only counts where the two disagree.

    python check.py
"""
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import score  # noqa: E402


def key(m):
    """What a market's station is shared with: the series for highs, the city for rain."""
    return m["series"] + ("-" + m["ticker"].rsplit("-", 1)[1] if m["series"] == "KXRAIN" else "")


def stations(ms):
    """{ticker: station}, filling markets whose listing had no rules text from others of the same series or city."""
    known = {key(m): m["station"] for m in ms if m.get("station")}
    return {m["ticker"]: m.get("station") or known.get(key(m)) for m in ms}


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def in_bracket(code, event_codes, high):
    """Whether a whole-degree high lands in bracket code: B64.5 is 64 to 65; a T bracket is the tail beyond the B
    brackets on its side (T66 above them means 67 or more, T61 below them means 60 or less)."""
    x = float(code[1:])
    if code[0] == "B":
        return x - 0.5 <= high <= x + 0.5
    mids = [float(c[1:]) for c in event_codes if c[0] == "B"]
    return high > x if not mids or x > max(mids) else high < x


def compare(ms, cli):
    """{'highs' | 'rain': {'checked', 'match', 'mismatch': [...], 'no report'}}. cli: {station: {date: record}}.
    Highs are checked once an event: by Kalshi's settled value, or where the listing has none, by whether the
    bracket that won holds the report's high. A rain trace ('T') is no rain."""
    st = stations(ms)
    events = defaultdict(list)
    for m in ms:
        if m["series"] != "KXRAIN":
            events[m["event"]].append(m)
    out = {f: {"checked": 0, "match": 0, "mismatch": [], "no report": 0} for f in ("highs", "rain")}
    done = set()
    for m in ms:
        f = "rain" if m["series"] == "KXRAIN" else "highs"
        unit = m["ticker"] if f == "rain" else m["event"]
        if unit in done:
            continue
        done.add(unit)
        rec = cli.get(st.get(m["ticker"]) or "", {}).get(score.climate_date(m["event"]).isoformat())
        if rec is None or (f == "highs" and num(rec.get("high")) is None) or (f == "rain" and rec.get("precip") in (None, "M")):
            out[f]["no report"] += 1
            continue
        if f == "highs":
            ev = events[m["event"]]
            value = next((num(x["value"]) for x in ev if num(x["value"]) is not None), None)
            won = [x["ticker"].rsplit("-", 1)[1] for x in ev if x["result"] == "yes"]
            if value is not None:
                ok, bad = value == num(rec["high"]), (m["event"], value, rec["high"])
            elif len(won) == 1:
                codes = [x["ticker"].rsplit("-", 1)[1] for x in ev]
                ok, bad = in_bracket(won[0], codes, num(rec["high"])), (m["event"], won[0], rec["high"])
            else:
                out[f]["no report"] += 1
                continue
            out[f]["checked"] += 1
        else:
            out[f]["checked"] += 1
            wet = rec["precip"] != "T" and num(rec["precip"]) > 0
            ok = (m["result"] == "yes") == wet
            bad = (m["ticker"], m["result"], rec["precip"])
        if ok:
            out[f]["match"] += 1
        else:
            out[f]["mismatch"].append(bad)
    return out


def load_cli():
    out = {}
    folder = os.path.join(HERE, "data", "cli")
    for name in os.listdir(folder):
        out[name[:-5]] = {r["valid"]: r for r in json.load(open(os.path.join(folder, name)))}
    return out


def main():
    ms = [m for m in score.load(os.path.join(HERE, "data", "listed.jsonl"))
          if score.part(score.climate_date(m["event"])) in ("older", "recent")]
    out = compare(ms, load_cli())
    for f, r in out.items():
        print(f"{f}: {r['checked']:,} checked, {r['match']:,} match, {len(r['mismatch']):,} differ, "
              f"{r['no report']:,} with no report")
        for x in r["mismatch"][:30]:
            print("   ", x)
    json.dump(out, open(os.path.join(HERE, "data", "settlement_check.json"), "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
