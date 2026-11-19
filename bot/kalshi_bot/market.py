"""Kalshi market data and orders, as pure functions: times, market groups, the taker fee, order books, the
one-minute candles the warning signs read, and the body of an order. Nothing here talks to Kalshi or touches the
ledger, and nothing reads the strategy's settings (those live in bot.py, where the tests change them)."""
import math
import uuid
from datetime import datetime, timezone


def ts(iso_str):
    return datetime.fromisoformat(iso_str.replace("Z", "+00:00")).timestamp()


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def floor_cents(x):
    return math.floor(x * 100 + 1e-6) / 100


def group_of(ticker, category=""):
    """Markets that move together share a group (as in research/kalshi_15min/fetch_all15.py)."""
    t = ticker.upper()
    if "CRYPTOLEAD" in t or "CRYPTOCOMP" in t:
        return "coin race"
    if any(x in t for x in ("GOLD", "SILVER", "PLATINUM", "PALLADIUM", "COPPER")):
        return "metals"
    if any(x in t for x in ("WTI", "BRENT", "NATGAS", "OIL")):
        return "energy"
    if any(x in t for x in ("EURUSD", "GBPUSD", "USDJPY")):
        return "fx"
    if "RATE" in t:
        return "rates"
    if "INX" in t or "NDQ" in t:
        return "stock index"
    return "crypto" if category == "Crypto" else category.lower() or "other"


def taker_fee(contracts, price, mult=1.0):
    """Kalshi's taker fee, rounded up to the cent per order."""
    return math.ceil(mult * 0.07 * contracts * price * (1 - price) * 100 - 1e-9) / 100


def parse_book(d):
    """GET /markets/{t}/orderbook -> YES and NO bids, best first."""
    book = (d or {}).get("orderbook_fp")
    if book is None:
        return None
    yes = sorted(((float(p), float(q)) for p, q in book.get("yes_dollars") or []), reverse=True)
    no = sorted(((float(p), float(q)) for p, q in book.get("no_dollars") or []), reverse=True)
    return {"yes": yes, "no": no}


def top_of_book(book):
    """(yes_bid, yes_ask, size at the YES ask, size at the NO ask). A YES ask is a NO bid seen from the other side."""
    if not book or not book["yes"] or not book["no"]:
        return None, None, 0.0, 0.0
    (yb, yb_size), (nb, nb_size) = book["yes"][0], book["no"][0]
    return yb, round(1 - nb, 4), nb_size, yb_size


def favourite(yes_bid, yes_ask):
    """The side priced higher, and what it costs to buy: YES at the ask, or NO at 1 - the YES bid."""
    if yes_bid is None or yes_ask is None:
        return None, None
    yes, no = yes_ask, round(1 - yes_bid, 4)
    if abs(yes - no) < 1e-9:
        return None, None
    return ("yes", yes) if yes > no else ("no", no)


def tick_down(price, ranges=None):
    """`price` lowered onto a price the market actually has, from the price_ranges in its listing.

    Kalshi gives each market its own steps. Two shapes trade here: linear_cent, whole cents the whole way
    (copper, platinum, palladium, natural gas), and tapered_deci_cent, tenths of a cent under 10c and over 90c
    (gold, silver, WTI and every crypto series). On a 99c favourite limit_for caps the limit at HI, 99.9c, which
    is a price on a tapered market and no price at all on a whole-cent one -- so those four refused the order,
    39 times, and each refusal counted towards the three-failures halt.

    It rounds down, never up: a limit is the most we agree to pay, so a lower one can't overpay and a higher one
    could. On a whole-cent market a 99c ask therefore sends 99c, which the ask it saw should still fill. With no
    ranges, or a shape whose numbers don't read, the limit is left as limit_for set it rather than guessed at."""
    for r in ranges or []:
        try:
            start, end, step = float(r["start"]), float(r["end"]), float(r["step"])
        except (KeyError, TypeError, ValueError):
            return round(price, 4)
        if step > 0 and start <= price <= end:
            steps = math.floor(round((price - start) / step, 6))
            return round(start + steps * step, 4)
    return round(price, 4)


def price_refused(status, data):
    """True when Kalshi refused the order's price itself: HTTP 400, error code invalid_price.

    It gets its own count rather than the ordinary one. The price is ours to fix and the market was never going to
    take it, so a handful of these says nothing about whether Kalshi or the network is healthy -- which is what the
    three-failures-in-a-row halt is for. Deliberately narrow: insufficient_balance has also come back 400 and may
    mean something real, and a 5xx is a server fault whatever it says about the price."""
    return (status == 400 and isinstance(data, dict)
            and ((data.get("error") or {}).get("code") if isinstance(data.get("error"), dict) else None) == "invalid_price")


def book_takes(book, side, limit, contracts, above=None):
    """The offers an order for `side` up to `limit` takes from this book, as (price, whole contracts): the cheapest
    first, at most `contracts` in all, passing over any at or under `above` if it's given. An offer to sell YES is a NO
    bid seen from the other side, and an offer to sell NO a YES bid."""
    offers = sorted((round(1 - p, 4), q) for p, q in (book or {}).get("no" if side == "yes" else "yes") or [])
    taken, filled = [], 0.0
    for price, size in offers:
        if filled >= contracts or price > limit + 1e-9:
            break
        if above is not None and price <= above + 1e-9:
            continue
        q = min(contracts - filled, math.floor(size + 1e-9))
        filled += q
        taken.append((price, q))
    return taken


def book_fill(book, side, limit, contracts, above=None):
    """(contracts, their total cost) an order for `side` up to `limit` gets from this book (book_takes). (0.0, 0.0) with
    no book."""
    taken = book_takes(book, side, limit, contracts, above)
    return sum((q for _, q in taken), 0.0), sum((q * price for price, q in taken), 0.0)


def own_mid(side, quote):
    """The favourite side's own mid price from a YES (bid, ask), or None without both."""
    if quote is None or quote[0] is None or quote[1] is None:
        return None
    mid = (quote[0] + quote[1]) / 2
    return round(mid if side == "yes" else 1 - mid, 6)


def minute_quotes(raw, window_open):
    """GET /markets/candlesticks -> {ticker: {minute: (yes_bid, yes_ask)}} at the end of each minute, a minute with no
    quote carrying the last one forward, as the research's minute files do (fetch_minutes.py). None if unreadable."""
    if not isinstance(raw, dict):
        return None

    def close(block):
        v = (block or {}).get("close_dollars", (block or {}).get("previous_dollars"))
        return None if v is None else float(v)
    out = {}
    for m in raw.get("markets") or []:
        by_minute = {int((c["end_period_ts"] - window_open) // 60): c for c in m.get("candlesticks") or []}
        if not by_minute:
            continue
        quotes, last = {}, [None, None]
        for k in range(1, max(by_minute) + 1):
            c = by_minute.get(k) or {}
            for i, key in enumerate(("yes_bid", "yes_ask")):
                v = close(c.get(key))
                if v is not None:
                    last[i] = v
            quotes[k] = (last[0], last[1])
        out[m["market_ticker"]] = quotes
    return out


def client_order_id(ticker):
    """The same ID for a market every time, so no market can get a second order, even after a restart."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"kalshi-favorites-bot/{ticker}"))


def order_body(ticker, side, price, contracts, exchange_index=None):
    """An immediate-or-cancel limit order for whole contracts, priced from the YES side (V2 orders). `price` is the
    most a contract of `side` may cost (its limit): buying YES is a bid at it; buying NO is selling YES at 1 - it.
    exchange_index: the section (exchange shard) to send it to, a whole number; left out, Kalshi routes it itself,
    which is slower and bills it to every shard's write bucket (Bot.section_of says where the bot's comes from)."""
    yes_price = price if side == "yes" else round(1 - price, 4)
    body = {"ticker": ticker, "client_order_id": client_order_id(ticker), "side": "bid" if side == "yes" else "ask",
            "count": str(int(contracts)), "price": f"{yes_price:.4f}", "time_in_force": "immediate_or_cancel",
            "self_trade_prevention_type": "taker_at_cross", "cancel_order_on_pause": True}
    if exchange_index is not None:
        body["exchange_index"] = int(exchange_index)
    return body
