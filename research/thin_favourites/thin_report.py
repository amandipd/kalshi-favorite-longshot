"""The thin-market recorder's verdict, held to the pass marks fixed in RECORDER_PREREG.md before any data.

For each recorded market that has closed it asks Kalshi once for the result, final volume and real close time (100
markets a call), and, for thin ones, the last trade at or before an hour before the close, the checkpoint price the
past study used. Those answers are cached in data/settled.json, so a rerun only asks about markets closed since.
Then it finds each thin 80-90c favourite's book nearest the checkpoint and scores the three pass marks on the No
favourites: what getting in costs over the checkpoint price, the dollars offered within a cent of the cheapest offer,
and whether markets that look thin at the checkpoint stay thin.

Run it from research/thin_favourites while the recorder runs if you like: it shares no state with it, and the two
together stay at about 6 requests a second.

    python thin_report.py
"""
import gzip
import json
import os
import re
import statistics
from collections import defaultdict

from thin_books import DATA, LOG, get, ts

THIN = 18_643     # final volume under this is thin: the past study's least-traded third, fixed in the pre-registration
CHECK = 3600      # the checkpoint: this many seconds before the market's real close
WINDOW = 600      # the book used is the nearest one within this many seconds of the checkpoint
NEAR = 0.01       # dollars on offer count up to this far above the cheapest offer
EXTRA, DOLLARS, EARLY, NEED = 0.03, 20.0, 0.80, 100   # the pass marks and the sample they need
CACHE = os.path.join(DATA, "settled.json")
DAY_FILE = re.compile(r"^(\w+)-(\d{4}-\d{2}-\d{2})\.jsonl(\.gz)?$")
SPORTS = {"KXNBA": "NBA", "KXNFL": "NFL", "KXNHL": "NHL", "KXNCAAMB": "college basketball"}


def sport(series):
    return next((v for k, v in SPORTS.items() if series.startswith(k)), "tennis")


# ------------------------------------------------------------------ reading the recording


def lines(folder, prefix):
    """Every line of prefix-<day>.jsonl(.gz), in day order; a line cut short is skipped."""
    names = sorted((m.group(2), n) for n in os.listdir(folder) if (m := DAY_FILE.match(n)) and m.group(1) == prefix)
    for _, name in names:
        path = os.path.join(folder, name)
        with (gzip.open(path, "rt", encoding="utf-8") if name.endswith(".gz") else open(path, encoding="utf-8")) as fh:
            for line in fh:
                try:
                    yield json.loads(line)
                except ValueError:
                    continue


def asks(book, side):
    """The offers to buy `side`, cheapest first, as [(price, contracts)]: the other side's bids at 1 - p."""
    bids = (book or {}).get("no_dollars" if side == "yes" else "yes_dollars") or []
    return sorted((round(1 - float(p), 4), float(n)) for p, n in bids)


def cost_in(book, side):
    """(cheapest offer, dollars offered up to NEAR above it); None with nothing offered."""
    a = asks(book, side)
    if not a:
        return None
    best = a[0][0]
    return best, sum(p * n for p, n in a if p <= best + NEAR + 1e-9)


def band(p):
    """The favourite at the checkpoint when it is priced 80-90c: ("yes", p) or ("no", 1 - p), else None."""
    if 0.80 <= p < 0.90:
        return "yes", p
    if 0.10 < p <= 0.20:
        return "no", 1 - p
    return None


def nearest(snaps, t, window=WINDOW):
    best = min(snaps, key=lambda s: abs(s[0] - t), default=None)
    return best if best is not None and abs(best[0] - t) <= window else None


def vol_at(listing, t):
    """The volume in the last listing line at or before t; None before the first."""
    v = None
    for x in listing:
        if x["at"] > t:
            break
        v = x["v"]
    return v


def lateness(log):
    """Each "most late" figure in the recorder's log, in order."""
    return [float(x) for x in re.findall(r"most late ([\d.]+)x", log)]


# ------------------------------------------------------------------ Kalshi, after the close


def settle(tickers, cache=CACHE, fetch=get):
    """{ticker: result, final volume, close, game time and, for thin markets, the checkpoint trade} for the settled
    ones among `tickers`. Each is asked once and kept in `cache`; one not settled yet is asked again next time."""
    have = {}
    if os.path.exists(cache):
        with open(cache, encoding="utf-8") as fh:
            have = json.load(fh)
    todo = [t for t in tickers if t not in have]
    try:
        for i in range(0, len(todo), 100):
            batch = todo[i:i + 100]
            found = {m["ticker"]: m for m in (fetch("/markets", {"tickers": ",".join(batch), "limit": 100}) or {})
                     .get("markets") or []}
            for t in batch:
                m = found.get(t) or ((fetch(f"/historical/markets/{t}") or {}).get("market") or {})
                if m.get("result") not in ("yes", "no"):
                    continue
                row = {"result": m["result"], "vol": float(m.get("volume_fp") or 0), "close": ts(m.get("close_time")),
                       "occ": ts(m.get("occurrence_datetime")), "cp_yes": None, "cp_taker": None, "cp_at": None}
                if row["vol"] < THIN and row["close"]:
                    q = {"ticker": t, "max_ts": row["close"] - CHECK, "limit": 1}
                    trades = (fetch("/markets/trades", q) or {}).get("trades") or \
                        (fetch("/historical/trades", q) or {}).get("trades") or []
                    if trades:
                        row.update(cp_yes=float(trades[0]["yes_price_dollars"]), cp_taker=trades[0].get("taker_side"),
                                   cp_at=ts(trades[0].get("created_time")))
                have[t] = row
    finally:   # what was learned is kept even if Kalshi stops answering part way
        with open(cache, "w", encoding="utf-8") as fh:
            json.dump(have, fh)
    return {t: have[t] for t in tickers if t in have}


# ------------------------------------------------------------------ scoring


def rows(settled, books, listing):
    """One row per settled market. qualifies: thin, an 80-90c favourite at the checkpoint, and a book within WINDOW
    of it. A qualifying book with no offer on the favourite's side is an infinite extra cost and $0 on offer."""
    out = []
    for t, s in settled.items():
        series = t.split("-")[0]
        cp = s["close"] - CHECK if s["close"] else None
        early = vol_at(listing.get(t, []), cp) if cp else None
        r = {"t": t, "s": series, "sport": sport(series), "thin": s["vol"] < THIN, "early_vol": early,
             "early_thin": early is not None and early < THIN, "qualifies": False, "side": None,
             "close_after_occ": s["close"] - s["occ"] if s["close"] and s.get("occ") else None}
        fav = band(s["cp_yes"]) if r["thin"] and s.get("cp_yes") is not None else None
        snap = nearest(books.get(t, []), cp) if fav else None
        if snap:
            side, price = fav
            c = cost_in(snap[1], side)
            r.update(qualifies=True, side=side, price=price, won=(s["result"] == side), gap=abs(snap[0] - cp),
                     extra=(c[0] - price) if c else float("inf"), dollars=c[1] if c else 0.0)
        out.append(r)
    return out


def side_stats(rs):
    if not rs:
        return {"n": 0, "extra": None, "dollars": None, "won": None, "price": None}
    return {"n": len(rs), "extra": statistics.median(r["extra"] for r in rs),
            "dollars": statistics.median(r["dollars"] for r in rs),
            "won": statistics.mean(r["won"] for r in rs), "price": statistics.mean(r["price"] for r in rs)}


def verdict(rs):
    no = [r for r in rs if r["qualifies"] and r["side"] == "no"]
    yes = [r for r in rs if r["qualifies"] and r["side"] == "yes"]
    early = [r for r in rs if r["early_thin"]]
    n, s = side_stats(no), (statistics.mean(r["thin"] for r in early) if early else None)
    marks = {"cost": n["extra"] is not None and n["extra"] <= EXTRA + 1e-9,
             "money": n["dollars"] is not None and n["dollars"] >= DOLLARS,
             "early": s is not None and s >= EARLY}
    by_sport = defaultdict(list)
    for r in no:
        by_sport[r["sport"]].append(r)
    closes = defaultdict(list)
    for r in rs:
        if r["close_after_occ"] is not None:
            closes[r["sport"]].append(r["close_after_occ"])
    return {"no": n, "yes": side_stats(yes), "early": {"n": len(early), "share": s}, "pass": marks,
            "verdict": "not enough data" if n["n"] < NEED else ("pass" if all(marks.values()) else "fail"),
            "no_by_sport": {k: side_stats(v) for k, v in sorted(by_sport.items())},
            "close_hours_after_game_time": {k: statistics.median(v) / 3600 for k, v in sorted(closes.items())}}


# ------------------------------------------------------------------ the report


def load(folder, settled):
    """Listing volumes for every market, and books only near the checkpoints that can qualify (the rest would not
    fit in memory over two weeks)."""
    listing = defaultdict(list)
    for x in lines(folder, "markets"):
        if x.get("k") == "m":
            listing[x["t"]].append({"at": x["at"], "v": x["v"]})
    want = {t: s["close"] - CHECK for t, s in settled.items()
            if s["vol"] < THIN and s.get("cp_yes") is not None and band(s["cp_yes"])}
    books = defaultdict(list)
    for b in lines(folder, "books"):
        cp = want.get(b["t"])
        if cp is not None and abs(b["at"] - cp) <= WINDOW:
            books[b["t"]].append((b["at"], b["book"]))
    return listing, books


def show(v, late):
    c = lambda x: "-" if x is None else ("none on offer" if x == float("inf") else f"{x * 100:+.1f} cents")
    d = lambda x: "-" if x is None else f"${x:,.0f}"
    pct = lambda x: "-" if x is None else f"{x:.0%}"
    ok = lambda b: "PASS" if b else "fail"
    no, yes, e = v["no"], v["yes"], v["early"]
    print(f"\nVERDICT: {v['verdict'].upper()}  ({no['n']} qualifying No favourites; {NEED} needed)\n")
    print(f"1. Cost to get in, typical market: {c(no['extra'])} over the checkpoint price"
          f" (pass: {EXTRA * 100:.0f} cents or less)  {ok(v['pass']['cost'])}")
    print(f"2. Money on offer within a cent of the cheapest offer, typical market: {d(no['dollars'])}"
          f" (pass: ${DOLLARS:.0f} or more)  {ok(v['pass']['money'])}")
    print(f"3. Markets thin at the checkpoint that stayed thin: {pct(e['share'])} of {e['n']}"
          f" (pass: {EARLY:.0%} or more)  {ok(v['pass']['early'])}")
    print("\nReported, not pass marks:")
    for name, s in (("No favourites", no), ("Yes favourites", yes)):
        if s["n"]:
            print(f"  {name}: {s['n']} markets, won {pct(s['won'])} at an average price of {s['price'] * 100:.0f}"
                  f" cents; extra cost {c(s['extra'])}; on offer {d(s['dollars'])}")
    for sp, s in v["no_by_sport"].items():
        print(f"  No favourites, {sp}: {s['n']} markets; extra cost {c(s['extra'])}; on offer {d(s['dollars'])}")
    for sp, h in v["close_hours_after_game_time"].items():
        print(f"  {sp}: markets typically closed {h:.1f} hours after the listed game time")
    if late:
        print(f"  The recorder ran up to {statistics.median(late):.1f}x behind its schedule in a typical listing,"
              f" {max(late):.1f}x at worst")


def main(folder=DATA):
    gone = sorted({x["t"] for x in lines(folder, "markets") if x.get("k") == "gone"})
    print(f"{len(gone):,} recorded markets have closed; asking Kalshi about the new ones (cached in {CACHE})", flush=True)
    settled = settle(gone)
    listing, books = load(folder, settled)
    v = verdict(rows(settled, books, listing))
    log = open(os.path.join(folder, LOG), encoding="utf-8").read() if os.path.exists(os.path.join(folder, LOG)) else ""
    show(v, lateness(log))
    with open(os.path.join(folder, "verdict.json"), "w", encoding="utf-8") as fh:
        json.dump(v, fh, indent=1, default=str)


if __name__ == "__main__":
    main()
