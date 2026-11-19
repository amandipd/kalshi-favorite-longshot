"""A week of order books on Gemini Predictions and Polymarket US: how deep their 90-99c favourites are, and whether
those favourites win more often than their price says.

The bot trades Kalshi's 15-minute crypto markets: around minute 8 of 15 it buys the favourite at 90-99c and holds it
to settlement. Two other US-legal venues list short crypto markets with a public API (reports/Short term prediction
market venues.md): Gemini Predictions (5-minute, 15-minute and hourly Up/Down markets on BTC, ETH, SOL and XRP) and
Polymarket US (BTC Up/Down, 15-minute and 1-hour). Nobody publishes their order-book depth at 90-99c, or how often
their favourites win, so this records their public books for a week and then reports both.

Strategy: the bot's rule carried over to the two venues. At each checkpoint of a window (its minute-of-15
equivalent; the bot buys at checkpoint 9, with minute 8 elapsed), buy the favourite - YES when the mid of the YES
book is 50c or more, else NO - when its ask is 90-99c, $10 a bet, paying up to the ask plus 1c, with the venue's
taker fee, and hold it to settlement.

Both books are YES books. On Gemini a NO is bought by selling YES, so the NO ask is 1 - the best YES bid and the
contracts on offer there are that bid's; Polymarket US's "offers" are the YES asks and its bids the YES bids.

record: every REFRESH seconds it lists both venues' markets in the kept families (Gemini's 5m, 15m and hourly Up/Down
series, but not the daily, weekly and monthly ladders that share the hourly series' name; Polymarket US's
cpc-btc-updown-15m and -1h slugs). While a market's window runs it reads the market's book every STEP seconds (15 s
for Gemini's 5-minute markets up to 120 s for its hourly ones) and appends it to venue_books.jsonl, a line a book:
the market, when the book was asked for (t), when the venue's data is from (data_t: t on Gemini, whose books are
live; Last-Modified, else t - Age, on Polymarket US, whose books Cloudflare caches for up to 30 s), and the best
LEVELS levels of each side as [price, contracts]. A market a venue stops listing is still read until its window ends,
so one failed listing loses nothing. Every RESULTS_EVERY seconds it collects settlements: Gemini's first RESULT_PAGES
pages of recently-settled, and Polymarket US's markets one at a time once a window has been over for SETTLE_AFTER
seconds; each new one is appended to venue_results.jsonl.

Gentle: public GETs only, no key, and book reads at most RATE a second per venue (1.5 on Gemini, 1 on Polymarket
US). Fully listed, that is about 0.43 book reads a second on Gemini (four coins' 5m, 15m and hourly markets) and 0.05
on Polymarket US, plus a listing every 2 minutes and a results pass every 10. These hosts aren't Kalshi's, so
there's no quiet window around the bot's entry. One thread: a venue that stops answering holds the loop for up to
~31 s of retries per request, and the next pick goes to the other venue.

Resumable: the results already in venue_results.jsonl are read at the start and never written twice, and the
Polymarket US markets already in venue_books.jsonl are still asked for their results; books just append. Failures,
listing counts when they change, and a line per results pass (books written and failed since the last) go to
venue_books.log.

report: per venue, family and checkpoint with bets, the books (the first one read in each market's checkpoint), the
bets (the favourite at 90-99c), the median spread, the median dollars offered at the favourite's ask, the share of
bets whose $10, $25, $50 and $100 orders would have filled in full at up to the ask plus 1c, and over the settled bets
the win rate against the mean price, the z-score of the wins and the profit per $10 order after the fee, buying only
what the book held. Every (venue, family, checkpoint), bets or not, is also written to venue_books_report.json.

    python venue_books.py record        # a week; record 2 for two days. Leave it running.
    python venue_books.py report
"""
import json
import math
import os
import re
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import ROUND_CEILING, ROUND_HALF_EVEN, Decimal
from email.utils import parsedate_to_datetime

import requests

from history import strategy

GEMINI, PMUS = "https://api.gemini.com", "https://gateway.polymarket.us"
STEP = {("gemini", "5m"): 15, ("gemini", "15m"): 30, ("gemini", "1h"): 120,   # seconds between reads of a book
        ("pmus", "15m"): 30, ("pmus", "1h"): 60}
RATE = {"gemini": 1.5, "pmus": 1.0}   # book reads a second, at most, per venue
REFRESH = 120          # seconds between listings
RESULTS_EVERY = 600    # seconds between result passes
RESULT_PAGES = 3       # pages of Gemini's recently-settled (newest first) read per pass
SETTLE_AFTER = 120     # seconds after a Polymarket US window ends before its result is asked for
LEVELS = 10            # book levels kept per side
LO, HI = 0.90, 0.99    # a bet: the favourite's ask in [LO, HI] (inclusive, compared after rounding to 4 places)
UP = 0.01              # orders may pay up to the ask plus a cent
STAKES = (10, 25, 50, 100)
UNIT = 10              # the order, in dollars, whose profit the report counts
FULL = 0.999           # a fill of this share of the stake or more is full
FEE = {"gemini": 0.07, "pmus": 0.0695}   # taker fee: rate x contracts x p x (1 - p)
TRIES = 6
TIMEOUT = 10           # seconds a request may take
WEEK = 7 * 86400
OUT, RESULTS, LOG = "venue_books.jsonl", "venue_results.jsonl", "venue_books.log"
REPORT = "venue_books_report.json"

EVENTS, SETTLED = "/v1/prediction-markets/events", "/v1/prediction-markets/events/recently-settled"
GEMINI_PAGE, PMUS_PAGE = 100, 200
GEMINI_FAMILIES = (("05M", "5m"), ("15M", "15m"), ("1H", "1h"))   # series suffix: family (1h needs the hourly tag)
PMUS_SLUG = re.compile(r"^cpc-btc-updown-(15m|1h)-")
PMUS_SPAN = (3600, 3 * 3600)   # Polymarket US is listed for markets ending from an hour ago to 3 hours ahead
OPEN, RESOLVED = "MARKET_STATUS_OPEN", "MARKET_STATUS_RESOLVED"
CENT = Decimal("0.01")


def iso(t):
    """ISO "YYYY-MM-DDTHH:MM:SSZ" of unix seconds."""
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def epoch(s):
    """Unix seconds of an ISO time, with or without milliseconds and "Z" (UTC either way)."""
    d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp()


def stamp(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


def num(x):
    """float(x), or None for a missing value."""
    return None if x in (None, "") else float(x)


# ------------------------------------------------------------------ the venues

_session = requests.Session()


def get(base, path, params=None):
    """(JSON, headers) of GET base + path; (None, None) for a 404, at once. 429s, 5xx and dropped connections are
    tried again after 1, 2, 4, 8 and 16 s (TRIES tries in all), then it gives up with an error. The headers are
    requests' own, so any case reads them."""
    why = None
    for i in range(TRIES):
        if i:
            time.sleep(2 ** (i - 1))
        try:
            r = _session.get(base + path, params=params, timeout=TIMEOUT)
        except requests.RequestException as e:
            why = repr(e)
            continue
        if r.status_code == 404:
            return None, None
        if r.status_code == 429 or r.status_code >= 500:
            why = f"HTTP {r.status_code}"
            continue
        r.raise_for_status()
        return r.json(), r.headers
    raise RuntimeError(f"gave up on {base}{path} {params or ''}: {why}")


def total(page):
    """A Gemini page's pagination total (0 without one)."""
    return int(((page or {}).get("pagination") or {}).get("total") or 0)


def family(event):
    """(family, coin) of a Gemini event, or (None, None) for one left out. Series "BTC05M" is BTC's 5m and "BTC15M"
    its 15m; "BTC1H" is its 1h only when tagged hourly, since the same series carries the daily and weekly ladders."""
    series = event.get("series") or ""
    tags = {t.get("slug") for t in event.get("eventTags") or []}
    for suffix, fam in GEMINI_FAMILIES:
        if series.endswith(suffix) and (fam != "1h" or "hourly" in tags):
            return fam, series[:-len(suffix)]
    return None, None


MALFORMED = (KeyError, TypeError, ValueError, AttributeError)   # a field missing or unparseable: skip that one item


def gemini_markets(payload):
    """The markets on one page of Gemini's events: one per open contract of each active event in a kept family.
    A contract that can't be read (no symbol, no start, a bad time) is skipped, not the page: the run is unattended."""
    out = []
    for ev in (payload or {}).get("data") or []:
        fam, coin = family(ev)
        if fam is None or ev.get("status") != "active":
            continue
        for c in ev.get("contracts") or []:
            if c.get("marketState") != "open":
                continue
            try:
                out.append({"v": "gemini", "fam": fam, "sym": c["instrumentSymbol"], "coin": coin,
                            "start": epoch(ev["startTime"]), "end": epoch(c.get("expiryDate") or ev["expiryDate"]),
                            "strike": num((c.get("strike") or {}).get("value"))})
            except MALFORMED:
                continue
    return out


def pmus_markets(payload):
    """The open BTC Up/Down 15m and 1h markets on one page of Polymarket US's markets; one that can't be read is skipped."""
    out = []
    for m in (payload or {}).get("markets") or []:
        hit = PMUS_SLUG.match(m.get("slug") or "")
        if not hit or m.get("status") != OPEN:
            continue
        terms = m.get("assetPriceTerms") or {}
        try:
            out.append({"v": "pmus", "fam": hit.group(1), "sym": m["slug"], "coin": "BTC",
                        "start": epoch(terms["windowStart"]), "end": epoch(terms["windowEnd"]),
                        "strike": num((terms.get("priceToBeat") or {}).get("value"))})
        except MALFORMED:
            continue
    return out


def gemini_listing():
    """Every kept Gemini market, over all the pages of its crypto events."""
    out, offset = [], 0
    while True:
        data, _ = get(GEMINI, EVENTS, {"category": "crypto", "limit": GEMINI_PAGE, "offset": offset})
        out += gemini_markets(data)
        offset += GEMINI_PAGE
        if offset >= total(data):
            return out


def pmus_listing(now):
    """Every kept Polymarket US market ending from an hour before `now` to 3 hours after, over all the pages."""
    params = {"active": "true", "closed": "false", "endDateMin": iso(now - PMUS_SPAN[0]),
              "endDateMax": iso(now + PMUS_SPAN[1]), "limit": PMUS_PAGE}
    out, offset = [], 0
    while True:
        data, _ = get(PMUS, "/v1/markets", {**params, "offset": offset})
        out += pmus_markets(data)
        if len((data or {}).get("markets") or []) < PMUS_PAGE:
            return out
        offset += PMUS_PAGE


def listing(now):
    """{sym: market} of both venues' markets that haven't ended by `now`. A venue that fails is logged and left out."""
    out = {}
    for found in (attempt(now, "listing gemini", gemini_listing), attempt(now, "listing pmus", pmus_listing, now)):
        out.update({m["sym"]: m for m in found or [] if m["end"] > now})
    return out


def gemini_results(payload):
    """The results on one page of Gemini's recently-settled, for the contracts in the kept families."""
    out = []
    for ev in (payload or {}).get("data") or []:
        if family(ev)[0] is None:
            continue
        for c in ev.get("contracts") or []:
            if c.get("resolutionSide") in ("yes", "no"):
                out.append({"v": "gemini", "sym": c["instrumentSymbol"], "yes": c["resolutionSide"] == "yes",
                            "settle": num(c.get("settlementValue")),
                            "strike": num((c.get("strike") or {}).get("value"))})
    return out


def pmus_result(payload):
    """The result of the first market in a Polymarket US markets payload, or None until it has resolved to YES
    ("[\"1\",\"0\"]") or NO ("[\"0\",\"1\"]"). Any other outcome (none yet, or a split) is None too, so it's asked
    again rather than written as a NO."""
    m = ((payload or {}).get("markets") or [{}])[0]
    prices = json.loads(m.get("outcomePrices") or "[]") if m.get("status") == RESOLVED else []
    if [float(x) for x in prices] not in ([1.0, 0.0], [0.0, 1.0]):
        return None
    terms = m.get("assetPriceTerms") or {}
    return {"v": "pmus", "sym": m["slug"], "yes": float(prices[0]) == 1.0,
            "settle": num((terms.get("settlementPrice") or {}).get("value")),
            "strike": num((terms.get("priceToBeat") or {}).get("value"))}


def gemini_settled():
    """Gemini's results on the first RESULT_PAGES pages of recently-settled (fewer when its total says so)."""
    out = []
    for page in range(RESULT_PAGES):
        data, _ = get(GEMINI, SETTLED, {"limit": GEMINI_PAGE, "offset": page * GEMINI_PAGE})
        out += gemini_results(data)
        if (page + 1) * GEMINI_PAGE >= total(data):
            break
    return out


def pmus_settled(sym):
    """A Polymarket US market's result, or None while it has none."""
    return pmus_result(get(PMUS, "/v1/markets", {"slug": sym})[0])


# ------------------------------------------------------------------ the book


def best(levels, high_first):
    """[price, contracts] floats, best first, without the empty levels, LEVELS at most."""
    kept = ([float(p), float(q)] for p, q in levels)
    return sorted((x for x in kept if x[1] > 0), reverse=high_first)[:LEVELS]


def data_time(headers, now):
    """When a Polymarket US book is from: Last-Modified, else now - Age, else now."""
    h = headers or {}
    if h.get("Last-Modified"):
        return parsedate_to_datetime(h["Last-Modified"]).timestamp()
    if h.get("Age"):
        return now - float(h["Age"])
    return now


def parse_book(v, payload, headers, now):
    """{"bids", "asks", "data_t"} of a venue's book: YES bids high to low, YES asks low to high, as [price,
    contracts] floats; None for a payload with no book."""
    if v == "pmus":
        payload = (payload or {}).get("marketData")
    if not payload:
        return None
    if v == "gemini":
        bids = [(x["price"], x["amount"]) for x in payload.get("bids") or []]
        asks = [(x["price"], x["amount"]) for x in payload.get("asks") or []]
        data_t = now
    else:
        bids = [(x["px"]["value"], x["qty"]) for x in payload.get("bids") or []]
        asks = [(x["px"]["value"], x["qty"]) for x in payload.get("offers") or []]
        data_t = data_time(headers, now)
    return {"bids": best(bids, True), "asks": best(asks, False), "data_t": float(data_t)}


def read_book(m, t):
    """Market m's book, asked for at t; raises when the venue has none, so the caller logs it."""
    if m["v"] == "gemini":
        data, headers = get(GEMINI, f"/v1/book/{m['sym']}")
    else:
        data, headers = get(PMUS, f"/v1/markets/{m['sym']}/book")
    book = parse_book(m["v"], data, headers, t)
    if book is None:
        raise LookupError("no book")
    return book


def favourite(bids, asks):
    """(side, its ask): YES when YES's chance (the mid, or the one side there is) is 50c or more, else NO, whose ask
    is 1 - the best YES bid. The ask is None when that side has nothing on offer; (None, None) for an empty book."""
    bid = max((p for p, _ in bids), default=None)
    ask = min((p for p, _ in asks), default=None)
    quotes = [x for x in (bid, ask) if x is not None]
    if not quotes:
        return None, None
    if sum(quotes) / len(quotes) >= 0.5:
        return "yes", None if ask is None else round(ask, 4)
    return "no", None if bid is None else round(1 - bid, 4)


def offered(side, bids, asks, limit):
    """[[price, contracts]] on offer for `side` at `limit` or less, cheapest first; NO's are the YES bids at 1 - p.
    Prices are compared to 4 places, so 0.95 + 0.01 <= 0.96 holds."""
    if side == "yes":
        levels = [[round(p, 4), q] for p, q in asks]
    else:
        levels = [[round(1 - p, 4), q] for p, q in bids]
    return sorted(x for x in levels if x[0] <= round(limit, 4))


def walk(levels, dollars):
    """(contracts, cost) of spending up to `dollars` on the levels cheapest first; the last one taken is taken in
    part, so cost is `dollars` whenever the book is deep enough."""
    c = cost = 0.0
    for p, q in levels:
        take = min(q, max(0.0, dollars - cost) / p)
        c, cost = c + take, cost + take * p
    return c, cost


def fee(v, contracts, price):
    """The taker fee in dollars: FEE[v] x contracts x p x (1 - p), rounded up to the cent on Gemini and to the
    nearest cent (half to even) on Polymarket US. It is rounded to 9 places first, so float dust (0.0700000001)
    doesn't move a cent."""
    raw = Decimal(repr(round(FEE[v] * contracts * price * (1 - price), 9)))
    return float(raw.quantize(CENT, rounding=ROUND_CEILING if v == "gemini" else ROUND_HALF_EVEN))


# ------------------------------------------------------------------ what the books say


def checkpoint(rec):
    """1-15: the minute-of-15 equivalent of a book's data time in its window (checkpoint 9 is minute 8 elapsed)."""
    k = rec["data_t"] - rec["start"]
    return max(1, min(15, int(k / ((rec["end"] - rec["start"]) / 15)) + 1))


def row(rec):
    """One recorded book as the rule sees it (rows says what each field is)."""
    bids, asks = rec["bids"], rec["asks"]
    side, price = favourite(bids, asks)
    bet = price is not None and LO <= price <= HI
    fill, unit = {}, None
    if bet:
        levels = offered(side, bids, asks, price + UP)
        fill = {s: min(1.0, walk(levels, s)[1] / s) for s in STAKES}
        c, cost = walk(levels, UNIT)
        unit = {"contracts": c, "cost": cost, "fee": fee(rec["v"], c, cost / c)} if c else None
    return {"v": rec["v"], "fam": rec["fam"], "sym": rec["sym"], "coin": rec["coin"], "cp": checkpoint(rec),
            "data_t": rec["data_t"], "side": side, "price": price, "bet": bet,
            "spread": round(min(asks)[0] - max(bids)[0], 4) if bids and asks else None,
            "at_ask": sum(p * q for p, q in offered(side, bids, asks, price)) if price is not None else 0.0,
            "fill": fill, "pnl_unit": unit}


def rows(records):
    """A row per (venue, family, market, checkpoint), from the first book (by data_t) in it. side and price: the
    favourite and its ask; bet: that ask is LO-HI; spread: the YES ask - the YES bid; at_ask: dollars on offer at the
    favourite's ask; fill: {stake: the share of it buyable at up to the ask + UP} for bets; pnl_unit: the UNIT order's
    contracts, cost and fee there, None when not a bet or nothing fills. Any iterable of records, read once."""
    first = {}
    for rec in records:
        r = row(rec)
        key = (r["v"], r["fam"], r["sym"], r["cp"])
        first[key] = min(first.get(key, r), r, key=lambda x: x["data_t"])   # the earlier wins, the one held on a tie
    return list(first.values())


def mean(xs):
    return sum(xs) / len(xs) if xs else None


def median(xs):
    return statistics.median(xs) if xs else None


def per10(unit, won):
    """Profit per $10 of a filled order after its fee: (payout - cost - fee) / cost x 10."""
    return ((unit["contracts"] if won else 0.0) - unit["cost"] - unit["fee"]) / unit["cost"] * 10


def summarise(rows, results):
    """{(venue, family, checkpoint): stats} for every key with rows, Gemini's families first, checkpoints in order.
    results: {sym: result}. Fills and the median at the ask are over the bets; win rate, mean price, z and pnl10
    over the settled bets. z = (wins - the sum of the prices) / sqrt(the sum of p(1 - p)): how many standard
    deviations the favourites won above (or below) what their prices implied."""
    groups = defaultdict(list)
    for r in rows:
        groups[(r["v"], r["fam"], r["cp"])].append(r)
    order = {vf: i for i, vf in enumerate(STEP)}
    out = {}
    for key in sorted(groups, key=lambda k: (order.get(k[:2], len(order)), k)):
        rs = groups[key]
        bets = [r for r in rs if r["bet"]]
        done = [(r, (r["side"] == "yes") == results[r["sym"]]["yes"]) for r in bets if r["sym"] in results]
        prices = [r["price"] for r, _ in done]
        wins, var = sum(won for _, won in done), sum(p * (1 - p) for p in prices)
        out[key] = {"books": len(rs), "bets": len(bets),
                    "median_spread": median([r["spread"] for r in rs if r["spread"] is not None]),
                    "median_at_ask": median([r["at_ask"] for r in bets]),
                    "fill": {s: mean([r["fill"][s] >= FULL - 1e-9 for r in bets]) for s in STAKES},
                    "settled": len(done), "wins": wins, "win_rate": mean([won for _, won in done]),
                    "mean_price": mean(prices),
                    "z": (wins - sum(prices)) / math.sqrt(var) if var > 0 else None,
                    "pnl10": mean([per10(r["pnl_unit"], won) for r, won in done if r["pnl_unit"]])}
    return out


def report(summary):
    """Print a line per (venue, family, checkpoint) with bets."""
    pct = lambda x, d=0: "-" if x is None else f"{x:.{d}%}"
    print(f"\n{'':<16}{'':>7} {'':>6} {'median':>7} {'median $':>9}   {'filled in full':^23}   {'':>7} "
          f"{'win rate':>16} {'':>6} {'per $10':>8}")
    print(f"{'venue  fam  cp':<16}{'books':>7} {'bets':>6} {'spread':>7} {'at ask':>9}   "
          f"{'$10':>5} {'$25':>5} {'$50':>5} {'$100':>5}   {'settled':>7} {'vs price':>16} {'z':>6} {'after fee':>8}")
    for (v, fam, cp), s in summary.items():
        if not s["bets"]:
            continue
        spread = "-" if s["median_spread"] is None else f"{s['median_spread'] * 100:.1f}c"
        at = "-" if s["median_at_ask"] is None else f"${s['median_at_ask']:,.0f}"
        won = f"{pct(s['win_rate'], 1)} vs {pct(s['mean_price'], 1)}"
        z = "-" if s["z"] is None else f"{s['z']:+.2f}"
        pnl = "-" if s["pnl10"] is None else f"{s['pnl10'] * 100:+.1f}c"
        print(f"{v:<7}{fam:>4}{cp:>4} {s['books']:>7,} {s['bets']:>6,} {spread:>7} {at:>9}   "
              + " ".join(f"{pct(s['fill'][k]):>5}" for k in STAKES)
              + f"   {s['settled']:>7,} {won:>16} {z:>6} {pnl:>8}")
    print("\nBets: the favourite at 90-99c. Spread: YES ask - YES bid. At ask: dollars offered at the favourite's ask."
          " Filled in full: the order got 99.9% of its dollars at up to the ask + 1c. Win rate vs price: how often the"
          " settled bets won against the mean price paid. z: the z-score of the wins, (wins - the sum of the prices)"
          " / sqrt(the sum of p(1 - p)), i.e. how many standard deviations the favourites beat their prices by."
          " Per $10 after fee: a $10 order that buys only what the book held up to the ask + 1c, less the taker fee.")


# ------------------------------------------------------------------ record


def load(path):
    """The JSON lines of `path`, one at a time (none without the file); a line cut short by a stopped run is
    skipped."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            yield rec


def log(t, msg):
    line = f"{stamp(t)}  {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def attempt(t, what, fn, *args):
    """fn(*args), or None once its error is logged as `what` failing at t: one bad request never stops the run."""
    try:
        return fn(*args)
    except Exception as e:
        log(t, f"{what} failed: {e!r}")
        return None


def due(market, now, last):
    """True when `market`'s window runs at `now` and its book wasn't read (at `last`) in the last STEP seconds."""
    return market["start"] <= now < market["end"] and (
        last is None or now - last >= STEP[(market["v"], market["fam"])])


def next_due(market, last):
    """When `market` is next due, given {sym: last read}."""
    t = last.get(market["sym"])
    return market["start"] if t is None else t + STEP[(market["v"], market["fam"])]


def results_pass(t, have, ends, fh):
    """Append each new result to fh and to `have` ({sym}); returns how many. Gemini's come from recently-settled;
    Polymarket US's are asked for one market at a time, each in `ends` ({sym: end}) with no result yet whose window
    ended SETTLE_AFTER seconds before t or more."""
    found = attempt(t, "gemini results", gemini_settled) or []
    found += [attempt(t, f"{s}: result", pmus_settled, s)
              for s, end in ends.items() if s not in have and t - end >= SETTLE_AFTER]
    n = 0
    for r in found:
        if r and r["sym"] not in have:
            have.add(r["sym"])
            fh.write(json.dumps(r) + "\n")
            n += 1
    fh.flush()
    return n


def record(until=None, now=time.time, sleep=time.sleep):
    """Read every due book into OUT, and the results into RESULTS, until `until` (a week from the start without one).
    Waits only with `sleep`, 5 s at a time at most, waking when the next book, listing or results pass is due."""
    start = now()
    until = start + WEEK if until is None else until
    have = {r["sym"] for r in load(RESULTS)}
    ends = {r["sym"]: r["end"] for r in load(OUT) if r.get("v") == "pmus"}   # Polymarket US markets to settle
    log(start, f"recording books to {OUT} until {stamp(until)}; {len(have):,} results already in {RESULTS},"
               f" {len(ends):,} Polymarket US markets already recorded")
    markets, last, free = {}, {}, dict.fromkeys(RATE, -math.inf)   # free: when each venue may next be read
    listed = settled = -math.inf
    counts, books, failed = None, 0, 0
    with open(OUT, "a", encoding="utf-8") as out, open(RESULTS, "a", encoding="utf-8") as res:
        while now() < until:
            t = now()
            if t - listed >= REFRESH:
                listed = t
                markets = {s: m for s, m in markets.items() if m["end"] > t}   # kept if a venue fails to list
                markets.update(listing(t))
                ends.update((s, m["end"]) for s, m in markets.items() if m["v"] == "pmus")
                if Counter(f"{m['v']} {m['fam']}" for m in markets.values()) != counts:   # logged when they change
                    counts = Counter(f"{m['v']} {m['fam']}" for m in markets.values())
                    log(t, f"{len(markets)} markets listed or running"
                           f" ({', '.join(f'{k} {n}' for k, n in sorted(counts.items())) or 'none'})")
            if t - settled >= RESULTS_EVERY:
                n = results_pass(t, have, ends, res)
                log(t, f"results: {n} new, {len(have):,} in all; {books:,} books written and {failed:,} failed"
                       " since the last pass")
                settled, books, failed = t, 0, 0
            t = now()
            live = [m for m in markets.values() if t < m["end"]]
            ready = [m for m in live if t >= free[m["v"]] and due(m, t, last.get(m["sym"]))]
            if ready:
                # the venue read longest ago first, so one venue's slow retries can't starve the other; then the
                # market due longest
                m = min(ready, key=lambda m: (free[m["v"]], next_due(m, last)))
                last[m["sym"]], free[m["v"]] = t, t + 1 / RATE[m["v"]]
                book = attempt(t, f"{m['sym']}: book", read_book, m, t)
                if book is None:
                    failed += 1
                    continue
                data_t = round(book["data_t"], 3)
                out.write(json.dumps({**m, "t": round(t, 3), "data_t": data_t, "k": data_t - m["start"],
                                      "bids": book["bids"], "asks": book["asks"]}, separators=(",", ":")) + "\n")
                out.flush()
                books += 1
                continue
            soon = [(max(next_due(m, last), free[m["v"]]), m["end"]) for m in live]
            wake = min([listed + REFRESH, settled + RESULTS_EVERY, until] + [w for w, end in soon if w < end])
            sleep(min(5.0, max(0.001, wake - t)))   # 1 ms at least, so float dust can't spin the loop
    log(now(), f"stopped: the end of the run ({stamp(until)})")


# ------------------------------------------------------------------ main


def main(argv=None):
    """record [days] | report. Anything else prints the usage and returns 2."""
    args = sys.argv[1:] if argv is None else list(argv)
    if args[:1] == ["record"]:
        record(until=time.time() + float(args[1]) * 86400 if len(args) > 1 else None)
    elif args[:1] == ["report"]:
        strategy(__doc__)
        rs = rows(load(OUT))
        results = {r["sym"]: r for r in load(RESULTS)}
        print(f"{OUT}: {len(rs):,} books, the first of each market's checkpoint; {RESULTS}: {len(results):,} results")
        summary = summarise(rs, results)
        report(summary)
        with open(REPORT, "w", encoding="utf-8") as fh:
            json.dump([{"v": v, "fam": fam, "cp": cp, **s} for (v, fam, cp), s in summary.items()], fh, indent=1)
        print(f"\nAll {len(summary)} (venue, family, checkpoint) entries, bets or not, are in {REPORT}.")
    else:
        print("usage: python venue_books.py record [days] | report", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
