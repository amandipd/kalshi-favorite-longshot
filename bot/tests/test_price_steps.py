"""Prices a market actually has, and what happens when Kalshi refuses one.

Kalshi gives every market its own price steps, in the listing: `price_level_structure` names the shape and
`price_ranges` gives the steps. Two shapes matter here, both measured from the live API on Oct 26, 2026:

    linear_cent        [0.0000-1.0000 step 0.0100]                       whole cents only
                       KXCOPPER15M, KXPLATINUM15M, KXPALLADIUM15M, KXNATGAS15M
    tapered_deci_cent  [0.0000-0.1000 step 0.0010] [0.1000-0.9000 step 0.0100] [0.9000-1.0000 step 0.0010]
                       KXGOLD15M, KXSILVER15M, KXWTI15M, and every crypto 15M series

On a 99c favourite limit_for caps the limit at HI, 99.9c. That is a real price on a tapered market and no price
at all on a whole-cent one, so those four series refused the order: 39 times in the live ledger (platinum 14,
copper 13, palladium 10, natural gas 2), 21 sent as 0.9990 on the YES side and 18 as 0.0010 on the NO side.
Each refusal counted towards the three-failures-in-a-row halt, and three in one window has already happened
three times (Oct 21, 22 and 26). None halted, only because a crypto order succeeded in between each time.

So: the limit is lowered to a price the market has, and a refused price gets its own count, with a higher
limit than the ordinary one so a rule that refuses everything still stops the bot.

    python -m pytest tests/test_price_steps.py -q
"""
import pytest

from kalshi_bot import bot
from test_bot import ENTRY, FakeKalshi, W, decisions, env  # noqa: F401 (env is a fixture)

# The two shapes, exactly as Kalshi sends them: dollar strings, like the rest of its prices.
CENTS = [{"start": "0.0000", "end": "1.0000", "step": "0.0100"}]
TENTHS = [{"start": "0.0000", "end": "0.1000", "step": "0.0010"},
          {"start": "0.1000", "end": "0.9000", "step": "0.0100"},
          {"start": "0.9000", "end": "1.0000", "step": "0.0010"}]

BOOK_99 = {"yes": [(0.98, 100.0)], "no": [(0.01, 100.0)]}      # the YES ask is 1 - 0.01 = 99c: the failing case
BOOK_96 = {"yes": [(0.95, 100.0)], "no": [(0.04, 100.0)]}      # a 96c ask, where nothing was ever refused


# ------------------------------------------------------------------ lowering the limit onto a real price
def test_a_99c_ask_on_a_whole_cent_market_sends_99c_not_99_9c():
    """The bug: limit_for caps at 99.9c, which these four series do not have."""
    assert bot.limit_for(0.99) == 0.999
    assert bot.tick_down(0.999, CENTS) == 0.99


def test_a_99c_ask_on_a_tenths_market_still_sends_99_9c():
    """The markets that were working must not change."""
    assert bot.tick_down(0.999, TENTHS) == 0.999


def test_the_no_side_price_is_one_the_market_has_too(ranges=None):
    """An order for NO is written as selling YES at 1 - the limit, so that price must be real as well.
    18 of the 39 refusals were NO bets sent at 0.0010."""
    for ranges, limit, yes in ((CENTS, 0.99, 0.01), (TENTHS, 0.999, 0.001)):
        lim = bot.tick_down(bot.limit_for(0.99), ranges)
        body = bot.order_body("KXX-A", "no", lim, 3)
        assert lim == limit
        assert body["price"] == f"{yes:.4f}"
        assert bot.tick_down(float(body["price"]), ranges) == pytest.approx(yes)   # already a real price


def test_it_only_ever_rounds_down():
    """A limit is the most we agree to pay. Rounding up could overpay; rounding down cannot."""
    for ranges in (CENTS, TENTHS):
        for m in range(round(bot.LO * 1000), 1001):
            price = m / 1000
            got = bot.tick_down(price, ranges)
            assert got <= price + 1e-9, (ranges is CENTS, price, got)
            assert got == round(got, 4)


def test_every_price_it_may_send_is_one_the_market_has():
    """Over the whole band it buys in, on both shapes: the limit it sends, and the YES price that limit
    becomes on a NO bet, are both on the market's own steps."""
    for ranges, step in ((CENTS, 0.01), (TENTHS, 0.001)):
        for m in range(round(bot.LO * 1000), 1000):
            lim = bot.tick_down(bot.limit_for(m / 1000), ranges)
            for price in (lim, round(1 - lim, 4)):
                assert abs(price / step - round(price / step)) < 1e-6, (ranges is CENTS, m, price)


def test_a_listing_with_no_price_rules_is_left_alone():
    """An older listing, or a shape we have never seen: keep what limit_for said rather than guess."""
    for ranges in (None, [], [{"start": "x", "end": "y", "step": "z"}]):
        assert bot.tick_down(0.999, ranges) == 0.999


def test_a_price_below_every_range_is_left_alone():
    assert bot.tick_down(0.999, [{"start": "0.0000", "end": "0.5000", "step": "0.0100"}]) == 0.999


# ------------------------------------------------------------------ the rules come off the listing
class Priced(FakeKalshi):
    """Kalshi as it really lists markets: each one carries its own price steps."""

    def __init__(self, *a, ranges=None, error_code="invalid_order", **kw):
        super().__init__(*a, **kw)
        self.ranges, self.error_code = ranges if ranges is not None else CENTS, error_code

    def markets(self, **p):
        d = super().markets(**p)
        if "series_ticker" in p:
            for m in d.get("markets", []):
                m["price_level_structure"] = "linear_cent" if self.ranges is CENTS else "tapered_deci_cent"
                m["price_ranges"] = self.ranges
        return d

    def create_order(self, body):
        self.orders.append(body)
        if self.order_status != 201:
            return self.order_status, {"error": {"code": self.error_code}}
        return 201, {"order_id": f"o{len(self.orders)}", "fill_count": body["count"] + ".00", "remaining_count": "0.00"}


def test_listed_keeps_each_markets_price_rules(env):
    b = bot.Bot(Priced(), env, False)
    assert b.load_catalog()
    got = b.listed(W)
    assert got and all(m["price_ranges"] == CENTS for m in got)


def test_a_listing_without_the_rules_just_has_no_key(env):
    b = bot.Bot(FakeKalshi(), env, False)      # the plain fake sends no price rules
    assert b.load_catalog()
    assert all("price_ranges" not in m for m in b.listed(W))


def test_the_order_it_sends_to_a_whole_cent_market_is_whole_cents(env):
    """End to end: a 99c favourite on a whole-cent market, and the price on the wire."""
    fake = Priced(ranges=CENTS)
    b = bot.Bot(fake, env, True)
    b.load_catalog()
    b.trading = True
    b.decide_window(ENTRY, W, [{"ticker": "KXBTC15M-A", "series": "KXBTC15M", "open": W, "close": W + 900,
                                "book": BOOK_99, "price_ranges": CENTS}])
    assert fake.orders and fake.orders[0]["price"] == "0.9900"


def test_the_order_it_sends_to_a_tenths_market_keeps_the_extra_tenth(env):
    fake = Priced(ranges=TENTHS)
    b = bot.Bot(fake, env, True)
    b.load_catalog()
    b.trading = True
    b.decide_window(ENTRY, W, [{"ticker": "KXBTC15M-A", "series": "KXBTC15M", "open": W, "close": W + 900,
                                "book": BOOK_99, "price_ranges": TENTHS}])
    assert fake.orders and fake.orders[0]["price"] == "0.9990"


# ------------------------------------------------------------------ a refused price has its own count
def test_a_refused_price_is_recognised():
    assert bot.price_refused(400, {"error": {"code": "invalid_price"}})
    assert not bot.price_refused(400, {"error": {"code": "insufficient_balance"}})   # may mean something real
    assert not bot.price_refused(400, {"error": {"code": "invalid_order"}})
    assert not bot.price_refused(201, {"order_id": "o1"})
    assert not bot.price_refused(None, "network error")
    assert not bot.price_refused(500, {"error": {"code": "invalid_price"}})          # a server fault, not our price


def window(b, now, w, n, book=BOOK_99, ranges=CENTS):
    """One window of `n` markets, each a 99c favourite. The tickers carry the window, because decide_window
    passes over any ticker it has already decided -- a market trades in one window and no other."""
    b.trading = True
    b.decide_window(now, w, [{"ticker": f"KXBTC15M-{int(w)}-{i}", "series": "KXBTC15M", "open": w,
                              "close": w + 900, "book": book, "price_ranges": ranges} for i in range(n)])


def test_refused_prices_do_not_halt_at_three(env):
    """The latent halt: three refusals in one window has happened three times already."""
    fake = Priced(order_status=400, error_code="invalid_price")
    b = bot.Bot(fake, env, True)
    b.load_catalog()
    window(b, ENTRY, W, 4)
    assert len(fake.orders) == 4                  # all four tried, nothing stopped
    assert bot.halt_info() is None
    assert b.errors == 0 and b.price_errors == 4


def test_enough_refused_prices_in_a_row_still_halt(env):
    """The backstop: if the price rule ever refused everything, this is what catches it. Set above the four
    whole-cent markets one window can hold, so the real pattern can never fire it."""
    assert bot.MAX_PRICE_ERRORS > 4
    fake = Priced(order_status=400, error_code="invalid_price")
    b = bot.Bot(fake, env, True)
    b.load_catalog()
    window(b, ENTRY, W, bot.MAX_PRICE_ERRORS + 2)
    assert len(fake.orders) == bot.MAX_PRICE_ERRORS       # the halt stopped the rest
    assert bot.halt_info()["reason"] == f"{bot.MAX_PRICE_ERRORS} orders refused for their price in a row"


def test_a_real_failure_still_halts_at_three(env):
    """The cover that must not be lost."""
    fake = Priced(order_status=400, error_code="invalid_order")
    b = bot.Bot(fake, env, True)
    b.load_catalog()
    window(b, ENTRY, W, 5)
    assert len(fake.orders) == bot.MAX_ORDER_ERRORS
    assert bot.halt_info()["reason"] == f"{bot.MAX_ORDER_ERRORS} orders failed in a row"


def test_an_order_that_works_clears_both_counts(env):
    fake = Priced(order_status=400, error_code="invalid_price")
    b = bot.Bot(fake, env, True)
    b.load_catalog()
    window(b, ENTRY, W, 2)
    assert b.price_errors == 2
    fake.order_status = 201                                    # the next order works
    window(b, ENTRY + 900, W + 900, 1, book=BOOK_96)
    assert b.price_errors == 0 and b.errors == 0
    assert bot.halt_info() is None
