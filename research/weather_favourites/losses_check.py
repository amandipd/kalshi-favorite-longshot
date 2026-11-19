"""Step 1 of reports/Kalshi weather forecast model edge.md: on the 33 city-days where a 6 PM daily-high favourite
lost (Oct 26 test), when did the settling degree - the official high - first become public?

A check, not a test: it can only kill the "stale evening price" idea, never prove it. The stop rule, fixed before
running: stop if most of the 33 are late warming (the high was set after the 6 PM checkpoint) or the degree was
never public before trading stopped.

Sources, all from the Iowa Environmental Mesonet (free; no Kalshi calls):
- METARs (hourly and special reports): the T-group temperature, the 6-hour maximum group (1sTTT) and the 24-hour
  group (4sTTTsTTT), public at their report time;
- DSM station summaries: the exact high so far and its minute, public at their issue time;
- CLI climate reports: the afternoon "valid as of" maximum, public at its issue time; and the time of the official
  high (local standard time) from the final report.

Each day falls in one class (classify): public before 6 PM; measured before 6 PM, public after; measured before
6 PM, never public before close; late warming after 6 PM. For the measured-before days it also reads our stored
Kalshi quotes: did the winning bracket reprice between the checkpoint and the close?

    python losses_check.py
"""
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check  # noqa: E402
import score  # noqa: E402

CACHE = os.path.join(HERE, "data", "iem")
ASOS = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
AFOS = "https://mesonet.agron.iastate.edu/cgi-bin/afos/retrieve.py"
OFFSET = {"NYC": -5, "PHL": -5, "DCA": -5, "BOS": -5, "MIA": -5, "ATL": -5, "MDW": -6, "MSY": -6,
          "LAX": -8, "SEA": -8, "SFO": -8}
CLASSES = ("public before 6 PM", "measured before 6 PM, public after", "measured before 6 PM, never public before close",
           "late warming after 6 PM")


def f(c):
    """Tenths-of-°C digits (sign, three digits) to whole °F."""
    return round(c * 9 / 5 + 32)


def tenths(sign, digits):
    return (-1 if sign == "1" else 1) * int(digits) / 10


def metar_groups(m):
    """{'temp', 'max6', 'max24'} in whole °F from a METAR's remarks; None where absent."""
    out = {"temp": None, "max6": None, "max24": None}
    if " RMK " not in m:
        return out
    for tok in m.split(" RMK ", 1)[1].split():
        if g := re.fullmatch(r"T([01])(\d{3})[01]\d{3}", tok):
            out["temp"] = f(tenths(*g.groups()))
        elif g := re.fullmatch(r"1([01])(\d{3})", tok):
            out["max6"] = f(tenths(*g.groups()))
        elif g := re.fullmatch(r"4([01])(\d{3})[01]\d{3}", tok):
            out["max24"] = f(tenths(*g.groups()))
    return out


def split_products(text):
    """One string per product in an IEM AFOS text dump (each starts with a WMO header line)."""
    starts = [m.start() for m in re.finditer(r"^[A-Z]{4}\d{2} [A-Z]{4} \d{6}", text, re.M)]
    return [text[a:b] for a, b in zip(starts, starts[1:] + [len(text)])]


def issued(text, year, month):
    """The product's issue time from its WMO header (day, hour, minute in UTC), in the given year and month."""
    d, h, mi = re.search(r"^[A-Z]{4}\d{2} [A-Z]{4} (\d{2})(\d{2})(\d{2})", text, re.M).groups()
    return int(datetime(year, month, int(d), int(h), int(mi), tzinfo=timezone.utc).timestamp())


def dsm(text, year, month):
    g = re.search(r"\bDS (?:(\d{4}) )?(\d{2})/\d{2} (-?\d{1,3})(\d{4})/", text)
    if not g:
        return None
    valid, day, mx, at = g.groups()
    return {"issued": issued(text, year, month), "day": int(day), "max": int(mx), "at": at, "final": valid is None}


def cli(text, year, month):
    g = re.search(r"^\s*MAXIMUM\s+(-?\d+)", text, re.M)
    if not g:
        return None
    return {"issued": issued(text, year, month), "max": int(g.group(1)), "preliminary": "VALID TODAY AS OF" in text}


def max_time(day, hhmm, offset):
    """UTC time of a CLI 'time of maximum' like '412 PM', given in local standard time (UTC + offset hours)."""
    t = datetime.strptime(hhmm.strip().rjust(7, "0"), "%I%M %p")
    local = datetime.fromisoformat(day).replace(hour=t.hour, minute=t.minute, tzinfo=timezone.utc)
    return int((local - timedelta(hours=offset)).timestamp())


def first_public(events, high, day):
    """(time, source) of the first event inside the climate day [start, end) showing the high or more."""
    hits = sorted((e["t"], e["source"]) for e in events if day[0] <= e["t"] < day[1] and e["value"] is not None
                  and e["value"] >= high)
    return hits[0] if hits else (None, None)


def classify(public, max_at, t):
    if max_at >= t:
        return CLASSES[3]
    if public is not None and public < t:
        return CLASSES[0]
    return CLASSES[1] if public is not None else CLASSES[2]


def cached(name, url, params):
    path = os.path.join(CACHE, name)
    if not os.path.exists(path):
        for i in range(5):
            time.sleep(1.0 + 3 * i)
            try:
                r = requests.get(url, params=params, timeout=60)
                r.raise_for_status()
                break
            except requests.RequestException:
                continue
        else:
            raise RuntimeError(f"IEM failed: {url} {params}")
        os.makedirs(CACHE, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(r.text)
    return open(path, encoding="utf-8").read()


def events_for(st, day0, day1):
    """Every public reading of the running high for station st between day0 and day1 (UTC timestamps)."""
    s = datetime.fromtimestamp(day0 - 3600, timezone.utc)
    e = datetime.fromtimestamp(day1 + 6 * 3600, timezone.utc)
    evs = []
    txt = cached(f"metar_{st}_{s:%Y%m%d}.csv", ASOS, {
        "station": st, "data": "metar", "tz": "Etc/UTC", "format": "onlycomma", "latlon": "no", "missing": "M",
        "direct": "no", "report_type": [3, 4], "sts": s.strftime("%Y-%m-%dT%H:%MZ"), "ets": e.strftime("%Y-%m-%dT%H:%MZ")})
    for line in txt.splitlines()[1:]:
        parts = line.split(",", 2)
        if len(parts) < 3:
            continue
        t = int(datetime.fromisoformat(parts[1] + ":00+00:00").timestamp())
        g = metar_groups(parts[2])
        evs.append({"t": t, "source": "hourly reading", "value": g["temp"]})
        if g["max6"] is not None and t - 6 * 3600 >= day0 - 600:      # the 6-hour window lies inside the day
            evs.append({"t": t, "source": "6-hour max group", "value": g["max6"]})
        if g["max24"] is not None:
            evs.append({"t": t, "source": "24-hour max group", "value": g["max24"]})
    for pil, parse, label in ((f"DSM{st}", dsm, "station summary (DSM)"), (f"CLI{st}", cli, "afternoon climate report")):
        txt = cached(f"{pil}_{s:%Y%m%d}.txt", AFOS, {"pil": pil, "sdate": s.strftime("%Y-%m-%d"),
                                                    "edate": e.strftime("%Y-%m-%d"), "fmt": "text", "limit": 40})
        for p in split_products(txt):
            iss_month = s if int(re.search(r"^[A-Z]{4}\d{2} [A-Z]{4} (\d{2})", p, re.M).group(1)) >= s.day else e
            x = parse(p, iss_month.year, iss_month.month)
            if x and not x.get("final") and (label != "afternoon climate report" or x["preliminary"]):
                evs.append({"t": x["issued"], "source": label, "value": x["max"]})
    return evs


def price_path(m, t, close):
    """The winning bracket's mid price at the checkpoint and at the last candle before the close."""
    cs = sorted(m["candles"])
    mid = lambda q: None if q is None or q[0] is None or q[1] is None else round((q[0] + q[1]) / 2, 3)
    return mid(score.quote_at(cs, t)), mid(score.quote_at(cs, close - 60))


def main():
    ms = [m for m in score.load() if m["series"] != "KXRAIN" and score.part(score.climate_date(m["event"])) in ("older", "recent")]
    st = check.stations(ms)
    cli_reports = check.load_cli()
    by_event = {}
    for m in ms:
        by_event.setdefault(m["event"], []).append(m)
    losing = sorted({m["event"] for m in ms if (b := score.bet(m, 6)) and not b["won"]}, key=score.climate_date)
    rows, counts = [], Counter()
    for e in losing:
        group = by_event[e]
        m0 = group[0]
        code, day = st[m0["ticker"]], score.climate_date(e).isoformat()
        off = OFFSET[code]
        day0 = int(datetime.fromisoformat(day + "T00:00:00+00:00").timestamp()) - off * 3600
        rec = cli_reports[code][day]
        high, t, close = int(rec["high"]), m0["close"] - 6 * 3600, m0["close"]
        max_at = max_time(day, rec["high_time"], off)
        evs = events_for(code, day0, day0 + 86400)
        when, src = first_public(evs, high, (day0, min(day0 + 86400, close)))
        known_at_t = max([x["value"] for x in evs if day0 <= x["t"] < t and x["value"] is not None], default=None)
        cls = classify(when, max_at, t)
        counts[cls] += 1
        win = next((x for x in group if x["result"] == "yes"), None)
        at_t, at_close = price_path(win, t, close) if win else (None, None)
        hm = lambda x: None if x is None else datetime.fromtimestamp(x + off * 3600, timezone.utc).strftime("%H:%M")
        rows.append({"event": e, "station": code, "high": high, "max at (LST)": hm(max_at), "checkpoint (LST)": hm(t),
                     "best public high at checkpoint": known_at_t, "first public (LST)": hm(when), "via": src,
                     "class": cls, "winner mid at checkpoint": at_t, "winner mid before close": at_close})
    for r in rows:
        print(f"{r['event']:<20} high {r['high']:>3} at {r['max at (LST)']}  checkpoint {r['checkpoint (LST)']}  "
              f"public high then {r['best public high at checkpoint']}  first public {r['first public (LST)']} "
              f"({r['via']})  winner {r['winner mid at checkpoint']} -> {r['winner mid before close']}  | {r['class']}")
    print("\n" + "\n".join(f"{counts[c]:>3}  {c}" for c in CLASSES))
    json.dump(rows, open(os.path.join(HERE, "data", "losses_check.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
