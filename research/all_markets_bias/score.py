"""Score the all-markets favourite map: bets at every checkpoint, train cells, candidates, and the once-only test read.

    python score.py train --labels half,1h     train cells and candidates for those checkpoints
    python score.py test  --labels half,1h     the test half, read once per label set (refuses a second read)
    python score.py describe                   calibration, Yes vs No, retention, money and today's spread

Rules come from PREREG.md via core.py. Output goes to data/ as JSON; the report quotes it.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

import core
import fetch

DATA = fetch.DATA


def _close(m):
    return m["_close"] if "_close" in m else core.ts(m["close_time"])


# ---------- bets ----------

def build_bets(markets, trades, partial, labels=None):
    """Every bet the rules make, and how many markets had each checkpoint (for retention)."""
    bets, seen = [], defaultdict(int)
    for m in markets:
        half = core.half_of(_close(m))
        tr = trades.get(m["ticker"], [])
        for label, t in m["cps"]:
            if labels is not None and label not in labels:
                continue
            seen[(m["category"], label)] += 1
            e = core.entry_at(tr, t)
            if e is None:
                continue
            won = m["result"] == e["side"]
            mult = m.get("fee_multiplier", 1)
            bets.append({"ticker": m["ticker"], "event": m["event_ticker"], "series": m["series"],
                         "category": m["category"], "half": half, "label": label, "price": e["price"],
                         "band": core.band_of(e["price"]), "side": e["side"], "won": won, "mult": mult,
                         "ret": core.return_per_dollar(e["price"], won, mult),
                         "profit": core.profit_cents(e["price"], won, mult), "money_near": e["money_near"],
                         "age": e["age"], "partial": bool(partial.get(m["ticker"], {}).get(label, False))})
    return bets, seen


def _page(rec):
    if not rec.get("page"):
        return None
    ep, (lo, hi, inc) = rec["page"]
    return ep, (-math.inf if lo is None else lo, hi, inc)


def record_labels(cps, rec, stage):
    """The checkpoints one fetched record prices. Stage 1: the stage-1 points, plus whatever its first page fully
    covers. Stage 2: the checkpoints it asked for."""
    if stage == 2:
        return set(rec.get("targeted", []))
    page = _page(rec)
    need = set(fetch.targets(cps, page, fetch.CUTOFF, 2))
    return {lab for lab, _ in cps if lab in fetch.STAGE1 or lab not in need}


def stream_bets(markets, recs1, recs2, labels=None):
    """build_bets, one fetched record at a time: each checkpoint is priced from the one record that covers it."""
    bets, seen = [], defaultdict(int)
    for stage, recs in ((1, recs1), (2, recs2)):
        for rec in recs:
            m = markets.get(rec["ticker"])
            if m is None:
                continue
            mine = record_labels(m["cps"], rec, stage)
            if labels is not None:
                mine &= labels
            if stage == 1:
                for lab, _ in m["cps"]:
                    if labels is None or lab in labels:
                        seen[(m["category"], lab)] += 1
            if mine:
                b, _ = build_bets([m], {m["ticker"]: rec["trades"]}, {m["ticker"]: rec.get("partial", {})}, mine)
                bets.extend(b)
    return bets, seen


def cells(bets, half):
    out = defaultdict(list)
    for b in bets:
        if b["half"] != half:
            continue
        out[("category", b["category"], b["label"])].append(b)
        out[("series", b["series"], b["label"])].append(b)
    return dict(out)


def candidates(bets):
    return {k for k, v in cells(bets, "train").items() if core.is_candidate(v)}


def _key(k):
    return "|".join(k)


def test_means(bets):
    out = {}
    for k, v in cells(bets, "test").items():
        s = core.stats(core.main_bets(v))
        if s["n"]:
            out[k] = (s["mean"], s["events"])
    return out


def is_lonely(means, key):
    kind, name, label = key
    scores = {lab: mean for (k, n, lab), (mean, ev) in means.items()
              if k == kind and n == name and ev >= core.MIN_EVENTS}
    return core.lonely(scores, label)


def read_test(bets, cand, out_path: Path):
    """Score each candidate on the test half. Writes once; a second read of the same file is refused."""
    if Path(out_path).exists():
        raise RuntimeError(f"{out_path} exists: the test half has already been read for these checkpoints")
    test_cells = cells(bets, "test")
    means = test_means(bets)
    res = {}
    for k in sorted(cand):
        r = core.pass_checks(test_cells.get(k, []), category=(k[0] == "category"))
        r["lonely"] = is_lonely(means, k) if r["passed"] else None
        res[k] = r
    Path(out_path).write_text(json.dumps({_key(k): v for k, v in res.items()}, indent=1, default=str))
    return res


# ---------- descriptions ----------

def calibration(bets):
    out = {}
    groups = defaultdict(list)
    for b in bets:
        if b["band"]:
            groups[(b["category"], b["half"], b["band"])].append(b)
    for k, v in groups.items():
        out[k] = {"n": len(v), "events": len({b["event"] for b in v}),
                  "mean_price": sum(b["price"] for b in v) / len(v),
                  "win_rate": sum(b["won"] for b in v) / len(v)}
    return out


def contracts_per_day(rows):
    """Contracts traded per day per series, over the listing after the archive line (complete for every series)."""
    lo = fetch.CUTOFF
    days = (core.WINDOW_END - lo) / 86400
    out = defaultdict(float)
    for m in rows:
        if lo <= core.ts(m["close_time"]) < core.WINDOW_END:
            out[m["series"]] += m["volume"]
    return {k: v / days for k, v in out.items()}


def left_label(seconds_left: float) -> str:
    label = "half"
    for name, hours in core.CHECKPOINTS:
        if seconds_left >= hours * core.H:
            label = name
    return label


def spread_rows(rows, series):
    out = []
    for r in rows:
        bid, ask = r["yes_bid"], r["yes_ask"]
        if not (0 < bid < ask < 100):
            continue
        fav_ask = ask if (bid + ask) / 2 > 50 else 100 - bid
        if not (70 <= fav_ask < 99):
            continue
        s = fetch.series_of(r["event_ticker"], series)
        out.append({"series": s, "category": series.get(s, {}).get("category") or "Unknown",
                    "spread": ask - bid, "fav_ask": fav_ask,
                    "left": left_label(core.ts(r["close_time"]) - r["at"])})
    return out


# ---------- loading ----------

def iter_jsonl(path: Path):
    if not path.exists():
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def load_bets(sample_file: str, labels):
    """Bets for the sample, streaming the trade files so millions of trades never sit in memory at once."""
    ms = {}
    for m in fetch.read_gz(DATA / sample_file):
        ms[m["ticker"]] = {"ticker": m["ticker"], "event_ticker": m["event_ticker"], "series": m["series"],
                           "category": m["category"], "result": m["result"], "close_time": m["close_time"],
                           "fee_multiplier": m["fee_multiplier"], "cps": [tuple(c) for c in m["cps"]]}
    return stream_bets(ms, iter_jsonl(DATA / "trades_s1.jsonl"), iter_jsonl(DATA / "trades_s2.jsonl"), labels)


def summary(s):
    return {k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in s.items()}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["train", "test", "describe"])
    ap.add_argument("--labels", default=None)
    ap.add_argument("--events", type=int, default=40)
    a = ap.parse_args(argv)
    labels = set(a.labels.split(",")) if a.labels else None
    tag = "all" if labels is None else "-".join(sorted(labels))
    bets, seen = load_bets(f"sample_e{a.events}.jsonl.gz", labels)
    if a.step == "train":
        tc = cells(bets, "train")
        cand = sorted(k for k, v in tc.items() if core.is_candidate(v))
        rows = {_key(k): summary(core.stats(core.main_bets(v))) for k, v in tc.items()}
        (DATA / f"train_{tag}.json").write_text(json.dumps({"cells": rows, "candidates": [_key(k) for k in cand]},
                                                           indent=1))
        print(f"{len(bets)} bets; {len(tc)} train cells; {len(cand)} candidates")
        for k in cand:
            s = rows[_key(k)]
            print(f"  {_key(k):60s} {s['mean'] * 100:+.2f}c per $1  events {s['events']}")
    elif a.step == "test":
        train = json.loads((DATA / f"train_{tag}.json").read_text())
        cand = {tuple(k.split("|")) for k in train["candidates"]}
        res = read_test(bets, cand, DATA / f"test_{tag}.json")
        means = {_key(k): {"mean": v[0], "events": v[1]} for k, v in test_means(bets).items()}
        (DATA / f"test_all_cells_{tag}.json").write_text(json.dumps(means, indent=1))
        print(f"{len(cand)} candidates read on test; {sum(r['passed'] for r in res.values())} passed; "
              f"luck alone would give about {core.expected_lucky_passes(len(cand)):.1f}")
        for k, r in sorted(res.items(), key=lambda kv: -kv[1]["stats"]["mean"] if kv[1]["stats"]["n"] else 0):
            s = r["stats"]
            if s["n"]:
                print(f"  {_key(k):60s} {s['mean'] * 100:+.2f}c per $1 [{s['lo'] * 100:+.2f}, {s['hi'] * 100:+.2f}] "
                      f"events {s['events']} passed {r['passed']}")
    else:
        series = fetch.load_series()
        cal = calibration(bets)
        sides = defaultdict(list)
        for b in core.main_bets(bets):
            sides[(b["category"], b["half"], b["label"], b["side"])].append(b)
        live = [m for p in sorted((DATA / "live").glob("*.jsonl.gz")) for m in fetch.read_gz(p)]
        spreads = []
        for p in sorted((DATA / "spread").glob("*.jsonl.gz")):
            spreads.extend(spread_rows(fetch.read_gz(p), series))
        by_sp = defaultdict(list)
        for r in spreads:
            by_sp[(r["category"], r["left"])].append(r["spread"])
            by_sp[("series:" + r["series"], r["left"])].append(r["spread"])
        priced = defaultdict(int)
        for b in bets:
            priced[(b["category"], b["label"])] += 1
        out = {
            "calibration": {"|".join(k): v for k, v in cal.items()},
            "sides": {"|".join(k): summary(core.stats(v)) for k, v in sides.items()},
            "retention": {"|".join(k): {"markets": n, "priced": priced[k]} for k, n in seen.items()},
            "contracts_per_day": contracts_per_day(live),
            "spread": {"|".join(k): {"n": len(v), "median": statistics.median(v)} for k, v in by_sp.items()},
            "money_near": {"|".join(k): {"median": statistics.median([b["money_near"] for b in v]),
                                         "total": sum(b["money_near"] for b in v)}
                           for k, v in cells(bets, "test").items() if v},
            "capped_series": [r["series"] for r in fetch.read_jsonl(DATA / "hist.jsonl") if r["capped"]],
        }
        (DATA / f"describe_{tag}.json").write_text(json.dumps(out, indent=1))
        print(f"described {len(bets)} bets")


if __name__ == "__main__":
    main()
