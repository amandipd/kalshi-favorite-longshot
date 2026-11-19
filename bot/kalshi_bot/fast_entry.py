"""Fast entry: the second live experiment, a separate experiment from the +1c limit.

The bot's orders land a median 2.4 s after minute 8 starts, by when other traders have taken half the volume at its
limit (research/kalshi_15min/lab/fast_entry/timing.md). Fast entry would send them at the mark itself: 480.0 s into the
window on Kalshi's clock, not the PC's.

It ran on paper first: MarkReader, a thread of its own, reads every listed market's order book at exactly the mark, on
Kalshi's clock from NTP (ntp_offset), and the bot pairs each real order with what an instant order could have bought in
that book, as a 'fast' shadow row. bot.py starts it only while live fast entry is off (START None).

Since Oct 14, 2026 it is live in every window: from START, with EVERY on, every window is fast, with
no coin. The helpers: each window's arm (EVERY, or a coin flipped from a hash of its open time), the prep and mark
wake-ups, Kalshi's clock from order answers, sending every order at once, and report(), which compares the arms.
START None is the off switch: every window normal, as before. bot.py imports this module, so it never imports the bot.
report() only reads the bot's ledger, and MarkReader only does HTTP.

    python -m pytest tests/test_fast_entry.py tests/test_mark_reader.py tests/test_fast_entry_ntp.py -q
"""
import hashlib
import json
import math
import socket
import statistics
import struct
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import requests

SALT = "fast-entry-1"      # the coin's seed: a new salt flips a new set of coins
START = 1791936000         # the first fast window (its open time): 2026-10-14 00:00:00 UTC; None: off, every window normal
EVERY = True               # every window from START is fast: the A/B coin was dropped on Oct 14. False: the coin
PREP = 450                 # a fast window's prep, seconds into the window ...
MARK = 480                 # ... and its mark, minute 8, both on Kalshi's clock
MIN_WINDOWS = 60           # the verdict waits for this many windows with orders in each arm
NTP_HOSTS = ("time.windows.com", "time.google.com", "time.cloudflare.com")
NTP_ERA = 2208988800       # seconds from 1900, where NTP counts from, to 1970, where time.time() does


# ------------------------------------------------------------------ the coin and the clock
def arm(window_open, start=START, salt=SALT, every=None):
    """'fast' or 'normal' for the window opening at window_open. Every window is normal with no start, and so is one
    opening before it. From the start, every window is fast with `every` (EVERY, read when called, unless given);
    without it a coin decides: fast when the first byte of sha256("<salt>:<window>") is odd."""
    w = int(window_open)
    if start is None or w < start:
        return "normal"
    if EVERY if every is None else every:
        return "fast"
    return "fast" if hashlib.sha256(f"{salt}:{w}".encode()).digest()[0] & 1 else "normal"


def next_wake(now, start=START, poll=3.0, prep=PREP, mark=MARK, offset=0.0, salt=SALT):
    """When the loop's next step should start, in local time: now + poll, or sooner for the prep or mark of a fast window
    (this one or the next) that falls strictly between. The events are on Kalshi's clock: server = local + offset."""
    server = now + offset
    w = server - server % 900
    events = [win + at - offset for win in (w, w + 900) if arm(win, start, salt) == "fast" for at in (prep, mark)]
    return min([t for t in events if now < t < now + poll], default=now + poll)


class ClockSync:
    """Kalshi's clock less the PC's, from the ts_ms in its order answers: the median of the last `keep` samples."""

    def __init__(self, keep=50):
        self.samples = deque(maxlen=keep)

    def add(self, sent, received, server_ms):
        """One answer: Kalshi's time less the middle of the round trip. Skipped with no usable ts_ms, when it was
        answered before it was sent (the PC's clock jumped), or over a 2 s round trip, which says too little."""
        try:
            server = float(server_ms) / 1000
        except (TypeError, ValueError):
            return
        if 0 <= received - sent <= 2:
            self.samples.append(server - (sent + received) / 2)

    def offset(self):
        return statistics.median(self.samples) if self.samples else 0.0

    def __len__(self):
        return len(self.samples)


def ntp_offset(hosts=NTP_HOSTS, timeout=0.5, sock=socket.socket, clock=time.time):
    """How far real time is ahead of this PC's clock, in seconds, by SNTP: one 48-byte UDP request (first byte 0x1B) to
    port 123 of every host at once, and the median of ((t1 - t0) + (t2 - t3)) / 2 over the hosts that sent a whole
    reply. t0 and t3 are the PC's clock when the request left and the reply came; t1 and t2 the server's when it got
    the request and sent the reply. A host that times out, fails or answers short is passed over: None with no reply."""
    def ask(host):
        try:
            with sock(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(timeout)
                t0 = clock()
                s.sendto(b"\x1b" + bytes(47), (host, 123))
                data, t3 = s.recv(1024), clock()
        except OSError:            # a timeout, a name that won't resolve, a network that's down
            return None
        if len(data) < 48:
            return None
        t1, t2 = (sec + frac / 2 ** 32 - NTP_ERA for sec, frac in struct.iter_unpack("!II", data[32:48]))
        return ((t1 - t0) + (t2 - t3)) / 2

    with ThreadPoolExecutor(max(1, len(hosts))) as pool:
        got = [x for x in pool.map(ask, hosts) if x is not None]
    return statistics.median(got) if got else None


# ------------------------------------------------------------------ the paper fast entry: the books at the mark
class MarkReader(threading.Thread):
    """A daemon thread, on a public Kalshi client of its own, that lists each window's markets at list_at and reads all
    their order books at once at the mark, both on Kalshi's clock: the PC's plus an offset from ntp, refreshed every
    ntp_every s but never while it lists or reads. The bot picks a window's books up with books(window_open). It only
    does HTTP, and run() logs and swallows every error, so it can never take the bot down."""

    def __init__(self, client, series_fn, list_at=470, mark=MARK, ntp_every=900, clock=time.time, sleep=time.sleep,
                 ntp=None, keep=4):
        super().__init__(name="mark-reader", daemon=True)
        self.client, self.series_fn, self.list_at, self.mark = client, series_fn, list_at, mark
        self.ntp_every, self.clock, self.sleep, self.ntp, self.keep = ntp_every, clock, sleep, ntp or ntp_offset, keep
        self.offset, self.asked = 0.0, -math.inf   # Kalshi's clock less the PC's; when it last asked ntp (Kalshi's)
        self.stop, self.lock = threading.Event(), threading.Lock()
        self.store = {}            # {window: {ticker: (raw, answered)}}

    def now(self):
        """Kalshi's time."""
        return self.clock() + self.offset

    def wait(self, t):
        """Sleep until Kalshi's clock reads t, again whenever a sleep ends early."""
        while (left := t - self.now()) > 0:
            self.sleep(left)

    def refresh_clock(self, now):
        """Ask ntp for the offset if ntp_every s have passed since it last asked (by now, Kalshi's time), but never from
        10 s before list_at to 5 s after the mark. True if it asked; a None answer keeps the old offset."""
        if self.list_at - 10 <= now % 900 <= self.mark + 5 or now - self.asked < self.ntp_every:
            return False
        self.asked = now           # before asking, so an ntp that raises can't hold up the windows
        if (got := self.ntp()) is not None:
            self.offset = got
        return True

    def listed(self, window_open):
        """The window's tickers in series_fn()'s series: the markets opening within 1 s of it. A series whose listing
        fails is skipped, and so is a market with no readable open_time.

        Asked for by close time, the way bot.Bot.listed asks and for the same reason: `status=open` matched nothing
        for about seven hours on Oct 24, answering 200 with an empty list. A window's market is the one closing at
        its end, so the close time finds it whether or not that filter is working."""
        tickers = []
        close = int(window_open) + 900
        for s in self.series_fn():
            try:
                d = self.client.markets(series_ticker=s, min_close_ts=close - 1, max_close_ts=close + 1, limit=50)
            except Exception:
                continue
            for m in (d or {}).get("markets", []):
                try:
                    if abs(datetime.fromisoformat(m["open_time"].replace("Z", "+00:00")).timestamp() - window_open) < 1:
                        tickers.append(m["ticker"])
                except (KeyError, AttributeError, ValueError):
                    pass
        return tickers

    def read_book(self, ticker):
        """(ticker, (its raw book, or None if the read failed, and when the answer came on Kalshi's clock))."""
        try:
            raw = self.client.orderbook(ticker)
        except Exception:
            raw = None
        return ticker, (raw, self.now())

    def run_window(self, window_open):
        """One window: list at list_at, then read every listed book at the mark, 8 at a time, and keep the window's
        {ticker: (raw, answered)}, which it returns. None, keeping nothing, when nothing was listed or it is over 2 s
        past the mark (too late to say what an instant order could have bought)."""
        self.wait(window_open + self.list_at)
        tickers = self.listed(window_open)
        mark = window_open + self.mark
        self.wait(mark)
        if not tickers or self.now() - mark > 2:
            return None
        with ThreadPoolExecutor(8) as pool:
            got = dict(pool.map(self.read_book, tickers))
        with self.lock:
            self.store[window_open] = got
            while len(self.store) > self.keep:
                del self.store[min(self.store)]
        return dict(got)

    def books(self, window_open):
        """A copy of the window's books, or {}."""
        with self.lock:
            return dict(self.store.get(window_open, {}))

    def run(self):
        """Window after window until stop is set: the clock refreshed when due, then the next window whose list_at hasn't
        passed on Kalshi's clock, then a wait until 6 s after its mark, past the stretch where it won't refresh. An error
        is logged and it goes on a second later."""
        while not self.stop.is_set():
            try:
                self.refresh_clock(self.now())
                now = self.now()
                window = now - now % 900 + (900 if now % 900 > self.list_at else 0)
                self.run_window(window)
                self.wait(window + self.mark + 6)
            except Exception as e:
                stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.clock()))
                print(f"{stamp} mark reader error, carrying on: {e!r}", flush=True)
                self.sleep(1)


# ------------------------------------------------------------------ sending
def send_all(k, bodies, workers=8, spacing=0.0, burst=1, clock=time.time):
    """Send every body once with k.create_order, on `workers` threads at once, never retrying. Send i starts no sooner
    than max(0, i - burst + 1) * spacing s after the first: the first `burst` go together, then one every `spacing`,
    to stay inside Kalshi's write rate limit (on Basic, about burst=8 and spacing=0.1). Returns one {"body", "status",
    "data", "sent", "answered"} per body, in order, with the times read from `clock`. A network error is status None."""
    burst = max(1, burst)
    first, started = [], threading.Event()

    def send(i, body):
        hold = max(0, i - burst + 1) * spacing
        if hold > 0:
            started.wait()
            # perf_counter: time.time() and time.monotonic() only tick every 15.6 ms on Windows
            while (left := first[0] + hold - time.perf_counter()) > 0:
                time.sleep(left)
        if i == 0:
            first.append(time.perf_counter())
            started.set()
        sent = clock()
        try:
            status, data = k.create_order(body)
        except requests.RequestException as e:   # the order may or may not have reached Kalshi
            status, data = None, f"network error: {e}"
        return {"body": body, "status": status, "data": data, "sent": sent, "answered": clock()}

    with ThreadPoolExecutor(max(1, workers)) as pool:
        return list(pool.map(send, range(len(bodies)), bodies))


def answer_of(response):
    """Kalshi's answer as a dict, whether as it came or as the ledger stores it (JSON text); None if it isn't one."""
    if isinstance(response, str):
        try:
            response = json.loads(response)
        except ValueError:
            return None
    return response if isinstance(response, dict) else None


def landing(response, window_open, mark=MARK):
    """When Kalshi stamped the order (its answer's ts_ms), in seconds after the mark, to the millisecond; or None."""
    try:
        return round(float((answer_of(response) or {}).get("ts_ms")) / 1000 - window_open - mark, 3)
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------ the report
def ratio_se(pairs):
    """Σnum ÷ Σden over (num, den) clusters, and its standard error clustered by them:
    √(J/(J−1) · Σ(numⱼ − R·denⱼ)²) ÷ Σden. (None, None) with nothing to divide by; no standard error with one cluster."""
    num, den = sum(n for n, _ in pairs), sum(d for _, d in pairs)
    if not den:
        return None, None
    r, j = num / den, len(pairs)
    if j < 2:
        return r, None
    return r, math.sqrt(j / (j - 1) * sum((n - r * d) ** 2 for n, d in pairs)) / den


def by_window(rows):
    """(Σnum, Σden) for each window in (window, num, den) rows."""
    sums = {}
    for w, num, den in rows:
        n, d = sums.get(w, (0, 0))
        sums[w] = (n + num, d + den)
    return list(sums.values())


def quantile(xs, q):
    """The q quantile of the sorted list xs, interpolated at q·(n − 1); None for an empty one."""
    if not xs:
        return None
    i = q * (len(xs) - 1)
    lo = int(i)
    return xs[lo] + (i - lo) * (xs[min(lo + 1, len(xs) - 1)] - xs[lo])


def base_of(body, filled, seen, fills):
    """The contracts an accepted order bought at or under the ask it saw (seen): all it filled when its limit (the price
    on the side it bought) was no higher, else what its own fills [(price, count)] bought there. None when that can't
    be known: something filled with no ask seen, or a limit over it with no fills rows. Nothing filled is 0."""
    if not filled:
        return 0.0
    if seen is None:
        return None
    limit = float(body["price"]) if body["side"] == "bid" else 1 - float(body["price"])   # an ask buys NO
    if limit <= seen + 1e-9:
        return filled
    return sum(count for price, count in fills if price <= seen + 1e-9) if fills else None


def group(orders, errors, bets, paid):
    """One group's summary from its accepted orders (window, asked, filled, landing, base: None when unknown), its count
    of refused ones, its settled bets (window, won, pnl, cost) and what its bets paid over the asks seen (window, over,
    contracts). Every standard error is clustered by window."""
    known = [(w, base, asked) for w, asked, _, _, base in orders if base is not None]
    base_share, base_se = ratio_se(by_window(known))
    fill_share, fill_se = ratio_se(by_window((w, filled, asked) for w, asked, filled, *_ in orders))
    per_ten, ten_se = ratio_se(by_window((w, 1000 * pnl, cost) for w, _, pnl, cost in bets))   # cents per $10
    over, over_se = ratio_se(by_window(paid))
    times = sorted(t for *_, t, _ in orders if t is not None)
    none = sum(filled == 0 for _, _, filled, *_ in orders)
    return {"orders": len(orders), "errors": errors, "windows": len({w for w, *_ in orders}),
            "asked": sum(asked for _, asked, *_ in orders), "filled": sum(filled for _, _, filled, *_ in orders),
            "fillShare": fill_share, "fillShareSe": fill_se,
            "anyShare": (len(orders) - none) / len(orders) if orders else None, "none": none,
            "landing": {"median": quantile(times, 0.5), "p10": quantile(times, 0.1), "p90": quantile(times, 0.9)},
            "settled": len(bets), "won": sum(won for _, won, _, _ in bets), "pnl": sum(pnl for *_, pnl, _ in bets),
            "cost": sum(cost for *_, cost in bets), "perTen": per_ten, "perTenSe": ten_se,
            "baseShare": base_share, "baseShareSe": base_se, "unknown": len(orders) - len(known),
            "overPaid": over, "overPaidSe": over_se}


def difference(fast, normal, key):
    """fast less normal in `key`, its standard error and z (no z over a zero standard error)."""
    d = None if fast[key] is None or normal[key] is None else fast[key] - normal[key]
    a, b = fast[key + "Se"], normal[key + "Se"]
    se = None if a is None or b is None else math.hypot(a, b)
    return {key: d, key + "Se": se, key + "Z": d / se if se else None}


def report(db, start=START, salt=SALT, mark=MARK):
    """The experiment so far, from the bot's orders, bets, decisions and fills (it only reads): for the windows before
    the start and for each arm, what was asked and filled, how much of it at or under the ask the bot saw (the base
    share, the primary outcome), when the orders landed, what the bets paid over the asks seen and how the settled
    ones did; then fast less normal and a verdict on the base share. An order counts once Kalshi accepted it (HTTP 2xx
    with an answer), a bet only through an accepted order for its market; cancels aren't orders. A ledger from before
    the fills table still works."""
    seen = {ticker: price for ticker, price in db.execute("SELECT ticker, fav_price FROM decisions")}
    fills = {}   # each order's own fills, by Kalshi's order ID
    if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='fills'").fetchone():
        for order_id, price, count in db.execute("SELECT order_id, price, count FROM fills WHERE order_id IS NOT NULL"):
            fills.setdefault(order_id, []).append((price, count))
    parts = {name: {"orders": [], "errors": 0, "bets": [], "paid": []} for name in ("before", "fast", "normal")}
    where = {}   # each accepted order's market: its group and window
    for ts, ticker, request, status, response in db.execute(
            "SELECT ts, ticker, request, http_status, response FROM orders ORDER BY id"):
        body = json.loads(request)
        if "cancel" in body:
            continue
        window = ts - ts % 900
        name = "before" if start is None or window < start else arm(window, start, salt)
        answer = answer_of(response) if status is not None and 200 <= status < 300 else None
        if answer is None:
            parts[name]["errors"] += 1
            continue
        filled = float(answer.get("fill_count") or 0)
        parts[name]["orders"].append((window, float(body["count"]), filled, landing(answer, window, mark),
                                      base_of(body, filled, seen.get(ticker), fills.get(answer.get("order_id")))))
        where[ticker] = name, window
    for ticker, status, pnl, cost, contracts in db.execute(
            "SELECT ticker, status, pnl, cost, contracts FROM bets ORDER BY id"):
        if ticker not in where:
            continue
        name, window = where[ticker]
        if status != "open":
            parts[name]["bets"].append((window, status == "won", pnl, cost))
        if seen.get(ticker) is not None:   # settled or open: what it paid is known either way
            parts[name]["paid"].append((window, cost - contracts * seen[ticker], contracts))
    groups = {name: group(**p) for name, p in parts.items()}
    fast, normal = groups["fast"], groups["normal"]
    diff = {}
    for key in ("fillShare", "perTen", "baseShare", "overPaid"):
        diff.update(difference(fast, normal, key))
    z = diff["baseShareZ"]
    if start is None:
        verdict = "not started"
    elif min(fast["windows"], normal["windows"]) < MIN_WINDOWS:
        verdict = "too early"
    elif z is None or abs(z) < 2:
        verdict = "no clear difference"
    else:
        verdict = "fast fills more" if z > 0 else "fast fills less"
    return {"start": start, "salt": salt, "mark": mark, "minWindows": MIN_WINDOWS, "groups": groups, "diff": diff,
            "verdict": verdict, "primary": "baseShare"}
