"""Pull what the all-markets favourite map needs from Kalshi's public API, gently, resumably.

    python fetch.py series                  every series, its category and fee multiplier
    python fetch.py list-live               settled markets after the archive line, exchange-wide, a day at a time
    python fetch.py list-hist               archived markets, per series, newest first, 25 pages at most
    python fetch.py sample [--events 40]    the pre-registered random sample (never reads a result)
    python fetch.py trades --stage 1|2 [--max N]
                                            stage 1: the 1-hour and midpoint checkpoints; stage 2: the rest
    python fetch.py spread                  one sweep of every open market's best bid and ask

Every step skips what is already on disk. Output goes to data/ (git-ignored). Rules come from PREREG.md via
core.py.

Rate: other jobs on the same machine shared Kalshi's ~20 reads a second. This runs at 2 a second while pull_gap.py is
running and 4 otherwise, halves for five minutes after any "too many requests", and data/rate.txt (a number)
overrides both.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import random
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

import core

BASE = "https://api.elections.kalshi.com/trade-api/v2"
HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
CUTOFF = core.ts("2026-08-29T00:00:00Z")      # GET /historical/cutoff on 28 Oct: markets and trades before this are archived
HIST_PAGES = 25
HIST_LIMIT = 200                              # /historical/markets answers a 1000-market page with a 429
LIVE_LIMIT = 1000
PAGE_A_LIMIT = 1000
TARGET_LIMIT = 200
STAGE1 = ("half", "1h")
LIVE_FROM = "2026-08-01"


# ---------- pure helpers (tested) ----------

def series_of(event_ticker: str, known) -> str:
    prefix = event_ticker.split("-")[0]
    if prefix in known:
        return prefix
    if "KX" + prefix in known:
        return "KX" + prefix
    return prefix


def compact_market(raw: dict, series: str) -> dict:
    return {"ticker": raw["ticker"], "event_ticker": raw["event_ticker"], "series": series,
            "open_time": raw.get("open_time"), "close_time": raw["close_time"], "result": raw.get("result", ""),
            "market_type": raw.get("market_type"), "volume": float(raw.get("volume_fp") or raw.get("volume") or 0),
            "mve": bool(raw.get("mve_collection_ticker"))}


def keep_market(m: dict) -> bool:
    return (m["market_type"] == "binary" and m["result"] in ("yes", "no") and not m["mve"]
            and m.get("open_time") is not None and core.half_of(core.ts(m["close_time"])) is not None)


def page_coverage(trades, endpoint: str, t_max: float, limit: int, cursor, cutoff: float):
    complete = (not cursor) or len(trades) < limit
    oldest = min((x[0] for x in trades), default=t_max)
    return core.coverage(oldest, t_max, complete, endpoint, cutoff)


def targets(cps, page, cutoff: float, stage: int) -> list[str]:
    """Checkpoints in this stage that the first page does not fully cover, so each needs its own request."""
    out = []
    for label, t in cps:
        if (label in STAGE1) != (stage == 1):
            continue
        eps = core.endpoints_for(t, cutoff)
        if page is not None and eps == [page[0]] and core.covers(page[1], t):
            continue
        out.append(label)
    return out


def in_windows(trades, points):
    return [x for x in trades if any(t - core.FRESH <= x[0] <= t for _, t in points)]


def trade_request(endpoint: str, ticker: str, t: float, cutoff: float, limit: int):
    if endpoint == "live":
        return "/markets/trades", {"ticker": ticker, "max_ts": int(t) + 1, "limit": limit}
    return "/historical/trades", {"ticker": ticker, "max_ts": min(int(t) + 1, int(cutoff)), "limit": limit}


# ---------- pacing and requests ----------

class Pacer:
    """One shared clock for every thread: at most `rate()` requests a second, slower after a 429."""

    def __init__(self):
        self.lock = threading.Lock()
        self.next_at = 0.0
        self.base = 2.0
        self.penalty_until = 0.0
        self.count = 0
        self.r429 = 0

    def rate(self) -> float:
        override = DATA / "rate.txt"
        r = self.base
        try:
            if override.exists():
                r = float(override.read_text().strip())
        except (OSError, ValueError):
            pass
        if time.time() < self.penalty_until:
            r = max(0.5, r / 2)
        return r

    def wait(self):
        with self.lock:
            now = time.time()
            at = max(now, self.next_at)
            self.next_at = at + 1 / self.rate()
            self.count += 1
        if at > now:
            time.sleep(at - now)

    def hit_429(self):
        with self.lock:
            self.r429 += 1
            self.penalty_until = time.time() + 300
            self.next_at = max(self.next_at, time.time() + 10)


PACER = Pacer()
_local = threading.local()


def pull_gap_running() -> bool:
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | "
                              "Select-Object -ExpandProperty CommandLine"],
                             capture_output=True, text=True, timeout=60).stdout
        return "pull_gap.py" in out
    except Exception:
        return True


def watch_rate():
    def loop():
        while True:
            PACER.base = 2.0 if pull_gap_running() else 4.0
            time.sleep(300)
    threading.Thread(target=loop, daemon=True).start()


def get(path: str, params: dict):
    """A gentle public GET. Rides out runs of 429s (Kalshi has refused for 6+ minutes at a stretch) with pauses
    capped at 60 seconds, for up to about 4 hours; gives up on other failures after 12 tries."""
    import requests
    s = getattr(_local, "s", None)
    if s is None:
        s = _local.s = requests.Session()
    fails, n429, waited = 0, 0, 0.0
    while fails < 12 and waited < 4 * 3600:
        PACER.wait()
        try:
            r = s.get(BASE + path, params=params, timeout=60)
        except Exception:
            fails += 1
            time.sleep(min(60, 3 * fails))
            continue
        if r.status_code == 429:
            PACER.hit_429()
            n429 += 1
            pause = min(60, 10 * n429)
            waited += pause
            time.sleep(pause)
            continue
        if r.status_code >= 500:
            fails += 1
            time.sleep(min(60, 5 * fails))
            continue
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"gave up on {path} {params}")


def log(msg: str):
    print(f"{datetime.now():%H:%M:%S} {msg}", flush=True)


def write_gz(path: Path, rows):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    tmp.replace(path)


def read_gz(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def read_jsonl(path: Path):
    if not path.exists():
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass                     # a line cut off by a crash; it is fetched again
    return out


def done_tickers(path: Path) -> set:
    """Tickers already in a trades file, read a line at a time."""
    out = set()
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    out.add(json.loads(line)["ticker"])
                except (json.JSONDecodeError, KeyError):
                    pass
    return out


# ---------- steps ----------

def step_series():
    d = get("/series", {"include_volume": "true"})
    rows = [{"ticker": x["ticker"], "category": x.get("category"), "frequency": x.get("frequency"),
             "fee_type": x.get("fee_type"), "fee_multiplier": x.get("fee_multiplier"),
             "volume": float(x.get("volume_fp") or 0), "title": x.get("title")} for x in d["series"]]
    write_gz(DATA / "series.json.gz", rows)
    log(f"{len(rows)} series")


def load_series():
    return {x["ticker"]: x for x in read_gz(DATA / "series.json.gz")}


def listable(series: dict):
    return sorted(t for t, x in series.items() if not t.startswith("KXMVE") and x["volume"] > 0)


def step_list_live():
    known = set(load_series())
    out = DATA / "live"
    out.mkdir(parents=True, exist_ok=True)
    day = datetime.fromisoformat(LIVE_FROM).replace(tzinfo=timezone.utc)
    end = datetime.fromtimestamp(core.WINDOW_END, timezone.utc)
    while day < end:
        path = out / f"{day:%Y-%m-%d}.jsonl.gz"
        if not path.exists():
            lo = int(day.timestamp())
            rows, cursor, pages = [], None, 0
            while True:
                p = {"status": "settled", "mve_filter": "exclude", "min_close_ts": lo, "max_close_ts": lo + 86399,
                     "limit": LIVE_LIMIT}
                if cursor:
                    p["cursor"] = cursor
                d = get("/markets", p)
                pages += 1
                for m in d.get("markets", []):
                    rows.append(compact_market(m, series_of(m["event_ticker"], known)))
                cursor = d.get("cursor")
                if not cursor or not d.get("markets"):
                    break
            write_gz(path, rows)
            log(f"live {day:%Y-%m-%d}: {len(rows)} markets, {pages} pages")
        day += timedelta(days=1)


def hist_one(series: str):
    rows, cursor, pages, capped = [], None, 0, False
    while True:
        # Kalshi refuses series_ticker together with mve_filter; combos are dropped by series name and mve flag.
        p = {"series_ticker": series, "limit": HIST_LIMIT}
        if cursor:
            p["cursor"] = cursor
        d = get("/historical/markets", p) or {}
        pages += 1
        ms = d.get("markets", [])
        rows.extend(compact_market(m, series) for m in ms)
        cursor = d.get("cursor")
        if not cursor or not ms:
            break
        if min(core.ts(m["close_time"]) for m in ms) < core.WINDOW_START:
            break
        if pages >= HIST_PAGES:
            capped = True
            break
    return {"series": series, "pages": pages, "capped": capped,
            "markets": [m for m in rows if core.half_of(core.ts(m["close_time"])) is not None]}


def step_list_hist(workers: int = 8):
    path = DATA / "hist.jsonl"
    done = {r["series"] for r in read_jsonl(path)}
    todo = [s for s in listable(load_series()) if s not in done]
    log(f"historical listing: {len(done)} series done, {len(todo)} to go")
    lock = threading.Lock()
    n = 0
    with ThreadPoolExecutor(workers) as ex, open(path, "a", encoding="utf-8") as f:
        futs = {ex.submit(hist_one, s): s for s in todo}
        for fut in as_completed(futs):
            try:
                r = fut.result()
            except Exception as e:
                log(f"  skipped {futs[fut]} for now ({e}); a re-run picks it up")
                continue
            with lock:
                f.write(json.dumps(r) + "\n")
                f.flush()
                n += 1
                if n % 250 == 0:
                    log(f"  {n}/{len(todo)} series, {PACER.count} requests, {PACER.r429} too-many-requests")


def iter_markets(known):
    """Every kept market from both listings, archived copy first, one at a time (millions do not fit in memory)."""
    with open(DATA / "hist.jsonl", encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            for m in r["markets"]:
                if keep_market(m) and not m["series"].startswith("KXMVE"):
                    yield m
    for path in sorted((DATA / "live").glob("*.jsonl.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                m = json.loads(line)
                if m["series"] not in known:
                    m["series"] = series_of(m["event_ticker"], known)
                if keep_market(m) and not m["series"].startswith("KXMVE"):
                    yield m


def step_sample(max_events: int):
    series = load_series()
    known = set(series)
    n = sum(1 for _ in iter_markets(known))
    got = core.sample_two_pass(lambda: iter_markets(known), seed=core.SEED, max_events=max_events)
    ms = range(n)
    for m in got:
        x = series.get(m["series"], {})
        m["category"] = x.get("category") or "Unknown"
        m["fee_multiplier"] = x.get("fee_multiplier") if x.get("fee_multiplier") is not None else 1
        m["cps"] = core.checkpoints(core.ts(m["open_time"]), core.ts(m["close_time"]))
    write_gz(DATA / f"sample_e{max_events}.jsonl.gz", got)
    req1 = sum(1 for m in got if m["cps"])
    log(f"{len(ms)} kept markets listed; sample of {len(got)} markets, {req1} with a checkpoint "
        f"({max_events} events per series and half)")


def fetch_trades(ticker: str, endpoint: str, t: float, limit: int):
    path, params = trade_request(endpoint, ticker, t, CUTOFF, limit)
    d = get(path, params) or {}
    raw = d.get("trades", [])
    rows = {}
    for x in raw:
        p = core.parse_trade(x)
        if p[0] <= t:
            rows[x.get("trade_id") or (p[0], p[1], p[2], p[3])] = p
    return rows, len(raw), d.get("cursor")


def market_stage(m: dict, stage: int, prior: dict | None):
    cps = [tuple(c) for c in m["cps"]]
    trades, req, partial = {}, 0, {}
    page = None
    if stage == 1 and cps:
        t_new = max(t for _, t in cps)
        ep = "live" if t_new >= CUTOFF else "historical"
        rows, n_raw, cursor = fetch_trades(m["ticker"], ep, t_new, PAGE_A_LIMIT)
        req += 1
        trades.update(rows)
        page = (ep, page_coverage(list(rows.values()), ep, t_new, PAGE_A_LIMIT, cursor, CUTOFF))
    elif prior is not None and prior.get("page"):
        ep, cov = prior["page"]
        page = (ep, tuple(cov))
    asked = targets(cps, page, CUTOFF, stage)
    for label in asked:
        t = dict(cps)[label]
        for ep in core.endpoints_for(t, CUTOFF):
            rows, n_raw, cursor = fetch_trades(m["ticker"], ep, t, TARGET_LIMIT)
            req += 1
            trades.update(rows)
            oldest = min((x[0] for x in rows.values()), default=t)
            if n_raw >= TARGET_LIMIT and oldest > t - core.FRESH:
                partial[label] = True
    kept = in_windows(sorted(trades.values()), cps)
    out = {"ticker": m["ticker"], "stage": stage, "req": req, "partial": partial, "targeted": asked, "trades": kept}
    if page is not None:
        lo, hi, inc = page[1]
        out["page"] = [page[0], [None if lo == -math.inf else lo, hi, inc]]
    return out


def step_trades(stage: int, max_n: int | None, workers: int, sample_file: str):
    ms = read_gz(DATA / sample_file)
    path = DATA / f"trades_s{stage}.jsonl"
    done = done_tickers(path)
    prior = {}
    if stage == 2:
        # only each stage-1 record's first-page span: its trades stay on disk
        with open(DATA / "trades_s1.jsonl", encoding="utf-8") as f1:
            for line in f1:
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                page = None
                if r.get("page"):
                    ep, (lo, hi, inc) = r["page"]
                    page = [ep, [-math.inf if lo is None else lo, hi, inc]]
                prior[r["ticker"]] = {"page": page}
        ms = [m for m in ms if m["ticker"] in prior]
    todo = [m for m in ms if m["ticker"] not in done]
    random.Random(core.SEED).shuffle(todo)          # so a partial pull is a random part of the sample
    if max_n is not None:
        todo = todo[:max(0, max_n - len(done))]
    log(f"stage {stage}: {len(done)} markets done, {len(todo)} to go")
    t0, req0, n, reqs = time.time(), PACER.count, 0, 0
    lock = threading.Lock()
    with ThreadPoolExecutor(workers) as ex, open(path, "a", encoding="utf-8") as f:
        futs = {ex.submit(market_stage, m, stage, prior.get(m["ticker"])): m["ticker"] for m in todo}
        for fut in as_completed(futs):
            try:
                r = fut.result()
            except Exception as e:
                log(f"  skipped {futs[fut]} for now ({e}); a re-run picks it up")
                continue
            with lock:
                f.write(json.dumps(r) + "\n")
                f.flush()
                n += 1
                reqs += r["req"]
                if n % 500 == 0 or n == len(todo):
                    el = time.time() - t0
                    log(f"  {n}/{len(todo)} markets, {reqs / n:.2f} requests each, "
                        f"{(PACER.count - req0) / max(el, 1):.2f} a second, {PACER.r429} too-many-requests, "
                        f"about {(len(todo) - n) * el / n / 3600:.1f} h left")


def step_spread():
    out = DATA / "spread"
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc)
    rows, cursor, pages = [], None, 0
    while True:
        p = {"status": "open", "mve_filter": "exclude", "limit": LIVE_LIMIT}
        if cursor:
            p["cursor"] = cursor
        d = get("/markets", p)
        pages += 1
        for m in d.get("markets", []):
            rows.append({"ticker": m["ticker"], "event_ticker": m["event_ticker"], "close_time": m["close_time"],
                         "yes_bid": float(m.get("yes_bid_dollars") or 0) * 100,
                         "yes_ask": float(m.get("yes_ask_dollars") or 0) * 100,
                         "volume": float(m.get("volume_fp") or 0), "at": stamp.timestamp()})
        cursor = d.get("cursor")
        if not cursor or not d.get("markets"):
            break
        if pages % 100 == 0:
            log(f"  spread sweep: {pages} pages, {len(rows)} markets")
    write_gz(out / f"{stamp:%Y%m%dT%H%M}.jsonl.gz", rows)
    log(f"spread sweep: {len(rows)} open markets, {pages} pages")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["series", "list-live", "list-hist", "sample", "trades", "spread"])
    ap.add_argument("--stage", type=int, default=1)
    ap.add_argument("--max", type=int, default=None)
    ap.add_argument("--events", type=int, default=40)
    ap.add_argument("--workers", type=int, default=12)
    a = ap.parse_args(argv)
    DATA.mkdir(exist_ok=True)
    if sys.platform == "win32":
        # Ask Windows not to idle-sleep while this process runs (ES_CONTINUOUS | ES_SYSTEM_REQUIRED). Ends with it.
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
    PACER.base = 2.0 if pull_gap_running() else 4.0
    watch_rate()
    log(f"{a.step}: pacing at {PACER.rate():g} a second")
    if a.step == "series":
        step_series()
    elif a.step == "list-live":
        step_list_live()
    elif a.step == "list-hist":
        step_list_hist(workers=min(a.workers, 8))
    elif a.step == "sample":
        step_sample(a.events)
    elif a.step == "trades":
        step_trades(a.stage, a.max, a.workers, f"sample_e{a.events}.jsonl.gz")
    elif a.step == "spread":
        step_spread()
    log(f"done: {PACER.count} requests, {PACER.r429} too-many-requests")


if __name__ == "__main__":
    sys.exit(main())
