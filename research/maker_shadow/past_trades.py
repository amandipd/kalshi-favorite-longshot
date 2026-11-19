"""Best-case maker test on the bot's past markets, from Kalshi's public trade history.

The bot is a taker: at minute 8 it buys the favourite's ask (92-99.9c, up to ask + 1c, taker fee). The question here:
would a maker do better? The pretend order rests a buy for the favourite at its own bid at the mark (L), 15
contracts, held to the close. Kalshi keeps every trade (not the order book), so the tape shows each seller of the
favourite after the mark: a taker who bought the other side. Two bounds on what our resting order would have got:

    best case   (front of the line)  every contract sold at a favourite price <= L fills us, up to the size
    worst case  (back of the line)   only contracts sold at a price < L fill us: those sellers went through our
                                     price, so every order at L, ours included, had already filled

A filled contract makes 1 - L if the favourite won and loses L if not (less a maker fee only where the series charges
one). The taker on the same market: the bot's real bet where it bet; elsewhere 15 contracts at the favourite's ask
with the taker fee.

    python past_trades.py measure 3        # pages per market: 3 sample markets of each series
    python past_trades.py fetch [MINUTES|-] [tierN ...] [KXSERIES ...]
                                           # the tape, mark to close, in fetch_order(), resumable; stops after
                                           # MINUTES; tierN fetches only that tier (tier_of); KX... skips a series
                                           # LEDGER_JSON=<path> names the bot ledger dump ({"decisions", "bets"})
    python past_trades.py results          # results of markets the bot did not bet on, and the series fee types
    python past_trades.py score            # scored.jsonl and summary.json in the data folder; prints the summary

Read-only: public GETs, no key, nothing ever placed or cancelled. The raw pages are cached gzipped under
data/past_trades/pages/ (gitignored).
"""
import gzip
import json
import math
import os
import sys
import threading
import time
from collections import defaultdict
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "data", "past_trades")
LEDGER = os.environ.get("LEDGER_JSON", "")
BASE = "https://external-api.kalshi.com/trade-api/v2"

OHIO = 1792127635      # the Ohio server's go-live: precise timing from here on
LO, HI = 0.92, 0.999   # the bot's band, on the favourite's ask
SIZE = 15              # contracts the pretend order rests for
WINDOW = 900
EPS = 1e-9
RATE = 2.5             # requests a second at most, all threads together (another fetcher shares the limit)
WORKERS = 2
EVERY = {"KXBTC15M": 5}   # BTC has ~9 pages a market: fetch one window in 5 first, the rest only if time allows

GROUPS = {"crypto": ("KXBTC15M", "KXETH15M", "KXSOL15M", "KXXRP15M", "KXDOGE15M", "KXBNB15M", "KXHYPE15M",
                     "KXNEAR15M", "KXZEC15M"),
          "metals": ("KXGOLD15M", "KXSILVER15M", "KXPLATINUM15M", "KXPALLADIUM15M", "KXCOPPER15M"),
          "energy": ("KXWTI15M", "KXNATGAS15M")}


# ------------------------------------------------------------------ the order and its market


def limit_of(d):
    """L: the favourite's own bid at the mark. A YES favourite's is the YES bid; a NO favourite's is 1 - the YES ask.
    None when there was no bid."""
    if d["fav_side"] == "yes":
        b = d.get("yes_bid")
        return round(b, 4) if b and b > 0 else None
    a = d.get("yes_ask")
    return round(1 - a, 4) if a is not None and a < 1 else None


def in_band(d, lo=LO, hi=HI):
    p = d.get("fav_price")
    return p is not None and lo - EPS <= p <= hi + EPS


def close_of(ts):
    return int(ts // WINDOW * WINDOW + WINDOW)


def band_of(p):
    if p < 0.95 - EPS:
        return "92-95c"
    if p < 0.98 - EPS:
        return "95-98c"
    return "98c+"


def group_of(series):
    for g, ss in GROUPS.items():
        if series in ss:
            return g
    return "other"


# ------------------------------------------------------------------ the tape


def ts_of(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def parse_trade(x):
    """(unix ts, YES price, NO price, contracts, taker side) of a REST trade."""
    yes = float(x["yes_price_dollars"])
    no = float(x["no_price_dollars"]) if x.get("no_price_dollars") is not None else round(1 - yes, 4)
    return (ts_of(x["created_time"]), yes, no, float(x["count_fp"]), x["taker_side"])


def fav_price_of(trade, fav_side):
    return trade[1] if fav_side == "yes" else trade[2]


def sellers(tape, fav_side, t0, t1):
    """[(ts, favourite price, contracts)] of the takers who sold the favourite (bought the other side), t0 < ts < t1,
    oldest first."""
    out = [(t[0], fav_price_of(t, fav_side), t[3]) for t in tape if t0 < t[0] < t1 and t[4] != fav_side]
    out.sort(key=lambda x: x[0])
    return out


def fill(sell, L, size, strict):
    """What a resting buy at L for `size` contracts gets from these sellers: {"filled", "first_ts", "full_ts"}.
    strict=False (best case) counts sales at L or below; strict=True (worst case) only sales below L."""
    got, first, full = 0.0, None, None
    for t, p, c in sell:
        if (p < L - 1e-6) if strict else (p <= L + 1e-6):
            take = min(c, size - got)
            if take <= 0:
                break
            got += take
            if first is None:
                first = t
            if got >= size - 1e-9:
                full = t
                break
    return {"filled": got, "first_ts": first, "full_ts": full}


def last_price(tape, fav_side, t):
    """The favourite's price at the last trade (either taker) at or before t; None if none."""
    best = None
    for x in tape:
        if x[0] <= t and (best is None or x[0] >= best[0]):
            best = x
    return None if best is None else fav_price_of(best, fav_side)


def after_fill(tape, fav_side, t, close):
    """The favourite's last trade price at t + 5, 30 and 60 s (never past the close) and the last before the close."""
    if t is None:
        return {"p5": None, "p30": None, "p60": None, "close": None}
    before = [x for x in tape if x[0] < close]
    return {f"p{k}": last_price(before, fav_side, min(t + k, close - 1e-6)) for k in (5, 30, 60)} | \
        {"close": last_price(before, fav_side, close - 1e-6)}


# ------------------------------------------------------------------ fees and scoring


def _up(x):
    """Rounded up to $0.0001, as Kalshi charges direct members."""
    return math.ceil(x * 10000 - 1e-6) / 10000 if x > 0 else 0.0


def taker_fee(c, p, mult=1.0):
    return _up(0.07 * mult * c * p * (1 - p))


def maker_fee(c, p, series_info):
    """Kalshi's maker fee (0.0175 x mult x c x p x (1 - p)) only on series whose fee type charges makers."""
    if not series_info or "maker" not in str(series_info.get("fee_type") or ""):
        return 0.0
    m = series_info.get("fee_multiplier")
    return _up(0.0175 * float(1 if m is None else m) * c * p * (1 - p))


def maker_pnl(c, L, won, fee=0.0):
    if c <= 0:
        return 0.0
    return c * ((1 - L) if won else -L) - fee


def taker_pnl(c, p, won, mult=1.0):
    return c * ((1 - p) if won else -p) - taker_fee(c, p, mult)


def cents_per_dollar(pnl, stake):
    return None if stake <= 0 else 100 * pnl / stake


def ratio_range(rows, z=1.96):
    """Cents of profit per dollar bet over rows {"window", "pnl", "stake"}, with a range counting each window once:
    the ratio's standard error from the window sums (linearised), times z. {"cpd", "se", "lo", "hi", "windows",
    "bets", "pnl", "stake"}; se None with fewer than two windows."""
    w = defaultdict(lambda: [0.0, 0.0])
    n = 0
    for r in rows:
        if r["stake"] > 0:
            w[r["window"]][0] += r["pnl"]
            w[r["window"]][1] += r["stake"]
            n += 1
    P = sum(v[0] for v in w.values())
    S = sum(v[1] for v in w.values())
    out = {"cpd": None, "se": None, "lo": None, "hi": None, "windows": len(w), "bets": n, "pnl": P, "stake": S}
    if S <= 0:
        return out
    R = P / S
    out["cpd"] = 100 * R
    G = len(w)
    if G >= 2:
        var = G / (G - 1) * sum((p - R * s) ** 2 for p, s in w.values()) / S ** 2
        out["se"] = 100 * math.sqrt(var)
        out["lo"], out["hi"] = out["cpd"] - z * out["se"], out["cpd"] + z * out["se"]
    return out


def diff_range(rows, z=1.96):
    """A minus B in cents per dollar bet, both measured on the same windows (rows {"window", "pnl_a", "stake_a",
    "pnl_b", "stake_b"}), with a range from the paired window sums. Windows with no stake on either side drop out."""
    w = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])
    for r in rows:
        if r["stake_a"] > 0 or r["stake_b"] > 0:
            v = w[r["window"]]
            v[0] += r["pnl_a"]; v[1] += r["stake_a"]; v[2] += r["pnl_b"]; v[3] += r["stake_b"]
    Pa, Sa, Pb, Sb = (sum(v[i] for v in w.values()) for i in range(4))
    out = {"diff": None, "se": None, "lo": None, "hi": None, "windows": len(w)}
    if Sa <= 0 or Sb <= 0:
        return out
    Ra, Rb = Pa / Sa, Pb / Sb
    out["diff"] = 100 * (Ra - Rb)
    G = len(w)
    if G >= 2:
        zs = [(v[0] - Ra * v[1]) / Sa - (v[2] - Rb * v[3]) / Sb for v in w.values()]
        out["se"] = 100 * math.sqrt(G / (G - 1) * sum(x * x for x in zs))
        out["lo"], out["hi"] = out["diff"] - z * out["se"], out["diff"] + z * out["se"]
    return out


def total_range(rows, z=1.96):
    """The total of rows {"window", "d"} (a dollar difference, say), with a range counting each window once:
    se = sqrt(G / (G - 1) * sum((d_g - mean)^2)) over the G window sums."""
    w = defaultdict(float)
    for r in rows:
        w[r["window"]] += r["d"]
    g = list(w.values())
    out = {"total": sum(g), "se": None, "lo": None, "hi": None, "windows": len(g)}
    if len(g) >= 2:
        m = sum(g) / len(g)
        out["se"] = math.sqrt(len(g) / (len(g) - 1) * sum((x - m) ** 2 for x in g))
        out["lo"], out["hi"] = out["total"] - z * out["se"], out["total"] + z * out["se"]
    return out


# ------------------------------------------------------------------ one market, scored


def score_market(d, tape, won, size=SIZE, series_info=None):
    """Both fill bounds for a resting buy of `size` at the favourite's bid, from the mark to the close."""
    L = limit_of(d)
    close = close_of(d["ts"])
    side = d["fav_side"]
    sell = sellers(tape, side, d["ts"], close) if L is not None else []
    out = {"L": L, "close": close, "sellers": sum(c for _, _, c in sell),
           "sellers_at_or_below": sum(c for _, p, c in sell if L is not None and p <= L + 1e-6)}
    for name, strict in (("best", False), ("worst", True)):
        f = fill(sell, L, size, strict) if L is not None else {"filled": 0.0, "first_ts": None, "full_ts": None}
        c = f["filled"]
        fee = maker_fee(c, L, series_info) if c > 0 else 0.0
        out[name] = {"filled": c, "full": f["full_ts"] is not None,
                     "first_after": None if f["first_ts"] is None else f["first_ts"] - d["ts"],
                     "full_after": None if f["full_ts"] is None else f["full_ts"] - d["ts"],
                     "pnl": maker_pnl(c, L, won, fee) if c > 0 else 0.0, "stake": c * L if c > 0 else 0.0,
                     "fee": fee, "after": after_fill(tape, side, f["first_ts"], close)}
    return out


def taker_of(d, bet, won, size=SIZE, real_size=True, mult=1.0):
    """The taker on the same market. The bot's real bet when it bet and the bet settled: its own pnl and cost
    (real_size), or its own average price for `size` contracts with the fee recomputed. Otherwise `size` contracts
    at the favourite's ask with the taker fee."""
    if bet and bet.get("status") in ("won", "lost") and bet.get("pnl") is not None:
        if real_size:
            return {"pnl": bet["pnl"], "stake": bet["cost"], "contracts": bet["contracts"], "real": True}
        p = bet["price"]
        return {"pnl": taker_pnl(size, p, won, mult), "stake": size * p, "contracts": size, "real": True}
    p = d["fav_price"]
    return {"pnl": taker_pnl(size, p, won, mult), "stake": size * p, "contracts": size, "real": False}


# ------------------------------------------------------------------ the cache


def _dir(root, ticker):
    return os.path.join(str(root), "pages", ticker)


def save_page(root, ticker, n, page):
    d = _dir(root, ticker)
    os.makedirs(d, exist_ok=True)
    tmp = os.path.join(d, f"p{n:04d}.json.gz.tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as fh:
        json.dump(page, fh, separators=(",", ":"))
    os.replace(tmp, os.path.join(d, f"p{n:04d}.json.gz"))


def mark_done(root, ticker, pages):
    d = _dir(root, ticker)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "done.json"), "w", encoding="utf-8") as fh:
        json.dump({"pages": pages}, fh)


def cached_pages(root, ticker):
    """(pages, the last page's cursor or None, done) of a ticker's cache."""
    d = _dir(root, ticker)
    if not os.path.isdir(d):
        return [], None, False
    names = sorted(f for f in os.listdir(d) if f.endswith(".json.gz"))
    pages = []
    for f in names:
        with gzip.open(os.path.join(d, f), "rt", encoding="utf-8") as fh:
            pages.append(json.load(fh))
    done = os.path.exists(os.path.join(d, "done.json"))
    cursor = pages[-1].get("cursor") if pages else None
    return pages, cursor or None, done


def fetch_market(root, ticker, min_ts, max_ts, get, max_pages=None):
    """The ticker's trades from min_ts to max_ts, from the cache, asking Kalshi (get(path, params)) for what is
    missing. (parsed tape, pages fetched now). Stops after max_pages new pages, leaving the cache resumable."""
    pages, cursor, done = cached_pages(root, ticker)
    fetched = 0
    if not done and pages and not cursor:
        mark_done(root, ticker, len(pages))
        done = True
    while not done:
        if max_pages is not None and fetched >= max_pages:
            break
        params = {"ticker": ticker, "min_ts": int(min_ts), "max_ts": int(max_ts), "limit": 1000}
        if cursor:
            params["cursor"] = cursor
        page = get("/markets/trades", params)
        if page is None:
            page = {"trades": [], "cursor": ""}
        save_page(root, ticker, len(pages), page)
        pages.append(page)
        fetched += 1
        cursor = page.get("cursor") or None
        if not cursor or not page.get("trades"):
            mark_done(root, ticker, len(pages))
            done = True
    tape = [parse_trade(x) for p in pages for x in (p.get("trades") or [])]
    return tape, fetched


# ------------------------------------------------------------------ which markets, in what order


def markets_by_priority(decisions):
    """One in-band decision per ticker (its bet if it had one), ordered: Ohio-era bets, Ohio-era others (skips,
    halts, errors), laptop-era bets, laptop-era others; oldest first within each."""
    by = {}
    for d in decisions:
        if not in_band(d):
            continue
        k = d["ticker"]
        if k not in by or (d["action"] == "bet" and by[k]["action"] != "bet"):
            by[k] = d

    def key(d):
        return (0 if d["ts"] >= OHIO else 1, 0 if d["action"] == "bet" else 1, d["ts"])
    return sorted(by.values(), key=key)


def sampled(d, every=None):
    """In the sample: a series in `every` keeps one window in every[series]; any other series keeps all."""
    n = (every or {}).get(d["series"])
    return not n or int(d["ts"] // WINDOW) % n == 0


def fetch_order(decisions, every=None):
    """markets_by_priority()'s markets in fetch order: Ohio-era bets in the sample, Ohio-era others in the sample,
    the rest of the Ohio era, the laptop era in the sample, the rest. Shuffled (by a hash of the ticker) within each
    tier, so a run stopped early still covers the whole date range."""
    import hashlib
    return sorted(markets_by_priority(decisions),
                  key=lambda d: (tier_of(d, every), hashlib.md5(d["ticker"].encode()).hexdigest()))


def tier_of(d, every=None):
    """0 Ohio-era bet in the sample, 1 Ohio-era other in the sample, 2 Ohio-era left out of the sample, 3 laptop era
    in the sample, 4 laptop era left out."""
    ohio, keep = d["ts"] >= OHIO, sampled(d, every)
    if ohio and keep:
        return 0 if d["action"] == "bet" else 1
    if ohio:
        return 2
    return 3 if keep else 4


# ------------------------------------------------------------------ Kalshi


class Getter:
    """Public GETs, at most RATE a second across threads; 429s and 5xx back off (everyone waits) and retry."""

    def __init__(self, rate=RATE):
        import requests
        self.requests = requests
        self.gap = 1 / rate
        self.lock = threading.Lock()
        self.next = 0.0
        self.local = threading.local()
        self.count = 0
        self.r429 = 0

    def __call__(self, path, params=None):
        if not hasattr(self.local, "s"):
            self.local.s = self.requests.Session()
        why = None
        for i in range(14):
            with self.lock:
                now = time.time()
                wait = self.next - now
                self.next = max(now, self.next) + self.gap
            if wait > 0:
                time.sleep(wait)
            try:
                r = self.local.s.get(BASE + path, params=params, timeout=20)
            except self.requests.RequestException as e:
                why = repr(e)
                time.sleep(2 ** min(i, 4))
                continue
            self.count += 1
            if r.status_code == 404:
                return None
            if r.status_code == 429 or r.status_code >= 500:
                why = f"HTTP {r.status_code}"
                self.r429 += r.status_code == 429
                back = min(0.5 * 2 ** i, 4)
                with self.lock:
                    self.next = max(self.next, time.time() + back)
                continue
            r.raise_for_status()
            return r.json()
        raise RuntimeError(f"gave up on {path} {params}: {why}")


def load_ledger(path=None):
    with open(path or LEDGER or os.path.join(ROOT, "ledger_decisions.json"), encoding="utf-8") as fh:
        return json.load(fh)


def measure(n_each):
    led = load_ledger()
    ms = [d for d in markets_by_priority(led["decisions"]) if d["ts"] >= OHIO]
    by = defaultdict(list)
    for d in ms:
        by[d["series"]].append(d)
    get = Getter()
    for s, xs in sorted(by.items()):
        step = max(1, len(xs) // (n_each + 1))
        for d in xs[step::step][:n_each]:
            t0 = time.time()
            tape, pages = fetch_market(ROOT, d["ticker"], int(d["ts"]), close_of(d["ts"]), get)
            print(f"{s:<15} {d['ticker']:<32} {len(tape):>7,} trades  {len(cached_pages(ROOT, d['ticker'])[0]):>3} pages"
                  f"  {time.time() - t0:5.1f}s", flush=True)
    print(f"requests {get.count}, 429s {get.r429}")


def fetch(minutes=None, skip=(), tiers=None):
    led = load_ledger()
    ms = [d for d in fetch_order(led["decisions"], EVERY) if d["series"] not in skip
          and (tiers is None or tier_of(d, EVERY) in tiers)]
    todo = [d for d in ms if not os.path.exists(os.path.join(_dir(ROOT, d["ticker"]), "done.json"))]
    print(f"{len(ms):,} in-band markets, {len(ms) - len(todo):,} already cached, {len(todo):,} to fetch", flush=True)
    get = Getter()
    stop = time.time() + minutes * 60 if minutes else None
    lock = threading.Lock()
    state = {"i": 0, "done": 0, "pages": 0}

    def work():
        while True:
            with lock:
                if state["i"] >= len(todo) or (stop and time.time() > stop):
                    return
                d = todo[state["i"]]
                state["i"] += 1
            try:
                _, pages = fetch_market(ROOT, d["ticker"], int(d["ts"]), close_of(d["ts"]), get)
            except Exception as e:   # one market failing must not stop the rest; it stays un-done for a rerun
                print(f"  {d['ticker']}: {e}", flush=True)
                continue
            with lock:
                state["done"] += 1
                state["pages"] += pages
                if state["done"] % 50 == 0:
                    print(f"{state['done']:,}/{len(todo):,} markets, {state['pages']:,} pages, {get.count:,} requests,"
                          f" {get.r429} 429s  ({d['ticker']})", flush=True)

    threads = [threading.Thread(target=work) for _ in range(WORKERS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    print(f"=== stopped: {state['done']:,} markets fetched, {state['pages']:,} pages, {get.count:,} requests,"
          f" {get.r429} 429s; {len(todo) - state['done']:,} left", flush=True)


def results():
    """Results of every in-band market without a settled bet, and the 16 series' fee types, into ROOT."""
    led = load_ledger()
    bets = {b["ticker"]: b for b in led["bets"]}
    path = os.path.join(ROOT, "results.json")
    have = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            have = json.load(fh)
    need = [d["ticker"] for d in markets_by_priority(led["decisions"])
            if d["ticker"] not in have and not (d["ticker"] in bets and bets[d["ticker"]]["status"] in ("won", "lost"))]
    get = Getter()
    print(f"{len(need):,} market results to ask for", flush=True)
    for i in range(0, len(need), 100):
        chunk = need[i:i + 100]
        d = get("/markets", {"tickers": ",".join(chunk), "limit": 1000})
        got = {m["ticker"]: m.get("result") for m in (d or {}).get("markets", [])}
        for t in chunk:
            if t not in got:   # not in the batch answer: ask for it alone
                m = get(f"/markets/{t}")
                got[t] = (m or {}).get("market", {}).get("result")
        have.update(got)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(have, fh)
    series = {}
    for ss in GROUPS.values():
        for s in ss:
            x = (get(f"/series/{s}") or {}).get("series", {})
            series[s] = {"fee_type": x.get("fee_type"), "fee_multiplier": x.get("fee_multiplier")}
    with open(os.path.join(ROOT, "series.json"), "w", encoding="utf-8") as fh:
        json.dump(series, fh, indent=1)
    print(json.dumps(series, indent=1))


# ------------------------------------------------------------------ scoring every market


def kind_of(d):
    if d["action"] == "bet":
        return "bet"
    r = d.get("reason") or ""
    if d["action"] == "skip":
        if r.startswith("not filled"):
            return "skip: nobody selling at the ask"
        if r.startswith("warning sign"):
            return "skip: warning sign"
        return "skip: other"
    return d["action"]


def load_tape(root, ticker):
    pages, _, done = cached_pages(root, ticker)
    return [parse_trade(x) for p in pages for x in (p.get("trades") or [])], done


def score_rows(root=ROOT, led=None):
    """A row per in-band market whose tape and result are in hand; and the counts of those left out, by why."""
    led = led or load_ledger()
    bets = {b["ticker"]: b for b in led["bets"]}
    with open(os.path.join(root, "results.json"), encoding="utf-8") as fh:
        res = json.load(fh)
    with open(os.path.join(root, "series.json"), encoding="utf-8") as fh:
        series = json.load(fh)
    rows, out = [], defaultdict(int)
    for d in markets_by_priority(led["decisions"]):
        t = d["ticker"]
        if not os.path.exists(os.path.join(_dir(root, t), "done.json")):
            out["tape not fetched"] += 1
            continue
        bet = bets.get(t)
        settled = bool(bet and bet.get("status") in ("won", "lost"))
        result = bet["result"] if settled else res.get(t)
        if result not in ("yes", "no"):
            out["no result"] += 1
            continue
        L = limit_of(d)
        if L is None:
            out["no bid at the mark"] += 1
            continue
        tape, _ = load_tape(root, t)
        won = result == d["fav_side"]
        info = series.get(d["series"])
        m = score_market(d, tape, won, SIZE, info)
        row = {"ticker": t, "series": d["series"], "group": group_of(d["series"]), "band": band_of(d["fav_price"]),
               "era": "ohio" if d["ts"] >= OHIO else "laptop", "kind": kind_of(d), "window": int(d["ts"] // WINDOW),
               "ts": d["ts"], "L": L, "ask": d["fav_price"], "won": won, "trades": len(tape),
               "sellers": m["sellers"], "sellers_at_or_below": m["sellers_at_or_below"],
               "best": m["best"], "worst": m["worst"],
               "base": after_fill(tape, d["fav_side"], d["ts"], m["close"]),
               "taker15": taker_of(d, bet, won, SIZE, real_size=False)}
        if settled:
            if bet["side"] != d["fav_side"]:
                out["bet side differs from the favourite (kept)"] += 1
            mb = score_market(d, tape, won, bet["contracts"], info)
            row["botsize"] = {k: {x: mb[k][x] for x in ("filled", "full", "pnl", "stake")} for k in ("best", "worst")}
            row["taker_real"] = taker_of(d, bet, won, SIZE, real_size=True)
        rows.append(row)
    return rows, dict(out)


def _mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else None


def _median(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def compare(rows, bound, taker="taker15", maker_key=None):
    """Maker (one bound) against the taker on the same markets: shares, win rates, cents per dollar with ranges,
    totals, and what the price did after the fill."""
    mk = (lambda r: r[bound]) if maker_key is None else (lambda r: r[maker_key][bound])
    rows = [r for r in rows if taker in r]
    filled = [r for r in rows if mk(r)["filled"] > 0]
    unf = [r for r in rows if mk(r)["filled"] <= 0]
    full = [r for r in rows if mk(r)["full"]]

    def one(xs, f):
        return [{"window": r["window"], "pnl": f(r)["pnl"], "stake": f(r)["stake"]} for r in xs]

    def pair(xs):
        return [{"window": r["window"], "pnl_a": mk(r)["pnl"], "stake_a": mk(r)["stake"],
                 "pnl_b": r[taker]["pnl"], "stake_b": r[taker]["stake"]} for r in xs]

    out = {"markets": len(rows), "windows": len({r["window"] for r in rows}),
           "any_fill": len(filled) / len(rows) if rows else None, "full_fill": len(full) / len(rows) if rows else None,
           "filled_n": len(filled), "win_filled": _mean(r["won"] for r in filled),
           "win_unfilled": _mean(r["won"] for r in unf), "win_all": _mean(r["won"] for r in rows),
           "contracts_filled_mean": _mean(mk(r)["filled"] for r in filled),
           "maker_filled": ratio_range(one(filled, mk)),
           "taker_same": ratio_range(one(filled, lambda r: r[taker])),
           "diff_same": diff_range(pair(filled)),
           "taker_all": ratio_range(one(rows, lambda r: r[taker])),
           "diff_all": diff_range(pair(rows)),
           "sold_at_or_below_median": _median(r["sellers_at_or_below"] for r in rows) if maker_key is None else None,
           "maker_total": sum(mk(r)["pnl"] for r in rows), "taker_total": sum(r[taker]["pnl"] for r in rows),
           "total_diff": total_range([{"window": r["window"], "d": mk(r)["pnl"] - r[taker]["pnl"]} for r in rows]),
           "maker_staked": sum(mk(r)["stake"] for r in rows), "taker_staked": sum(r[taker]["stake"] for r in rows)}
    if maker_key is None:
        out["first_fill_median_s"] = _median(r[bound]["first_after"] for r in filled)
        out["full_fill_median_s"] = _median(r[bound]["full_after"] for r in full)
        for k in ("p5", "p30", "p60", "close"):
            out[f"move_{k}"] = _mean(100 * (r[bound]["after"][k] - r["L"]) for r in filled
                                     if r[bound]["after"][k] is not None)
            out[f"base_{k}"] = _mean(100 * (r["base"][k] - r["L"]) for r in rows if r["base"][k] is not None)
        out["dropped_p60"] = _mean(r[bound]["after"]["p60"] < r["L"] - 0.005 for r in filled
                                   if r[bound]["after"]["p60"] is not None)
        out["base_dropped_p60"] = _mean(r["base"]["p60"] < r["L"] - 0.005 for r in rows if r["base"]["p60"] is not None)
    return out


def summarise(rows):
    scopes = {"ohio": [r for r in rows if r["era"] == "ohio"],
              "ohio bets": [r for r in rows if r["era"] == "ohio" and "taker_real" in r],
              "ohio not bet": [r for r in rows if r["era"] == "ohio" and r["kind"] != "bet"],
              "laptop": [r for r in rows if r["era"] == "laptop"],
              "laptop bets": [r for r in rows if r["era"] == "laptop" and "taker_real" in r]}
    for k in sorted({r["kind"] for r in rows if r["kind"] != "bet"}):
        scopes[f"ohio {k}"] = [r for r in rows if r["era"] == "ohio" and r["kind"] == k]
    out = {}
    for name, xs in scopes.items():
        if not xs:
            continue
        out[name] = {b: compare(xs, b) for b in ("best", "worst")}
        if name.endswith("bets"):
            out[name]["bot size"] = {b: compare(xs, b, taker="taker_real", maker_key="botsize") for b in ("best", "worst")}
            out[name]["bot win rate"] = _mean(r["won"] for r in xs)
            out[name]["bot real"] = ratio_range([{"window": r["window"], "pnl": r["taker_real"]["pnl"],
                                                  "stake": r["taker_real"]["stake"]} for r in xs])
        for split in ("band", "group"):
            out[name][split] = {}
            for v in sorted({r[split] for r in xs}):
                sub = [r for r in xs if r[split] == v]
                out[name][split][v] = {b: compare(sub, b) for b in ("best", "worst")}
    return out


def score(root=ROOT):
    rows, left = score_rows(root)
    with open(os.path.join(root, "scored.jsonl"), "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, separators=(",", ":")) + "\n")
    s = summarise(rows)
    s["left out"] = left
    s["rows"] = len(rows)
    with open(os.path.join(root, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(s, fh, indent=1)
    print(f"{len(rows):,} markets scored; left out: {left}")

    def f(x, n=1):
        return "-" if x is None else f"{x:+.{n}f}"
    for name in ("ohio", "ohio bets", "ohio not bet", "laptop"):
        if name not in s:
            continue
        for b in ("best", "worst"):
            c = s[name][b]
            mf, ts_, d = c["maker_filled"], c["taker_same"], c["diff_same"]
            print(f"{name:<14} {b:<5} n={c['markets']:>5} fill {c['any_fill']:.0%} full {c['full_fill']:.0%}"
                  f" win filled {c['win_filled'] or 0:.1%} unfilled {c['win_unfilled'] or 0:.1%} |"
                  f" maker {f(mf['cpd'], 2)} [{f(mf['lo'], 2)}, {f(mf['hi'], 2)}] taker same {f(ts_['cpd'], 2)}"
                  f" diff {f(d['diff'], 2)} [{f(d['lo'], 2)}, {f(d['hi'], 2)}] |"
                  f" $ maker {c['maker_total']:+.0f} taker {c['taker_total']:+.0f}"
                  f" | move60 {f(c['move_p60'], 2)}c (base {f(c['base_p60'], 2)})")


def main():
    a = sys.argv[1:]
    if a[:1] == ["measure"]:
        measure(int(a[1]) if len(a) > 1 else 3)
    elif a[:1] == ["fetch"]:
        skip = tuple(x for x in a[2:] if x.startswith("KX"))
        tiers = {int(x[4:]) for x in a[2:] if x.startswith("tier")} or None   # e.g. tier1: only that tier
        fetch(float(a[1]) if len(a) > 1 and a[1] != "-" else None, skip, tiers)
    elif a[:1] == ["results"]:
        results()
    elif a[:1] == ["score"]:
        score()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
