"""Finding this window's market without depending on the `status=open` filter.

On Oct 24, from about 15:53Z to 22:55Z, that filter matched nothing: Kalshi answered 200 with an empty list and
no error. An empty listing looks exactly like a quiet hour, so the live bot placed no bets for 27 windows and
said nothing about it, and then the filter started working again on its own with no restart. It was never
retired -- `open`, `unopened` and `settled` are still what /markets takes, and the initialized/active/finalized
in a market's own `status` field have never been filter values. The lesson is that the filter can stop matching,
so the listing here is built on the close time instead, which the fake below exercises both ways.

    python -m pytest tests/test_listing.py -q
"""
import pathlib

from kalshi_bot import bot, fast_entry
from kalshi_bot.web import dashboard
from test_bot import ENTRY, FakeKalshi, W, env, iso  # noqa: F401 (env is a fixture)


class BrokenFilterKalshi(FakeKalshi):
    """Kalshi as it answered through the Oct 24 outage: `status=open` comes back 200 with nothing in it, a
    market's own status name is refused as a filter (HTTP 400, which the client turns into None), and an
    unfiltered page is mostly future `initialized` markets with the live one far down it. Only a close-time
    range brings back the window's market.
    """
    AHEAD, BEHIND = 117, 82   # what a 15-minute series listed either side of the live market on Oct 24

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.asked = []   # the params of every /markets call, newest last
        self.skew = 0     # seconds the live market opens after its window does (0: on the window)

    def markets(self, **p):
        self.asked.append(p)
        if "series_ticker" not in p:
            return super().markets(**p)
        if p.get("status") == "open":
            return {"markets": []}        # the outage: 200 OK, an empty list, no error to see
        if "status" in p:
            return None                   # HTTP 400 "invalid status filter": the client answers None
        rows = self.page(p["series_ticker"])
        if p.get("min_close_ts") is not None:
            rows = [m for m in rows if bot.ts(m["close_time"]) >= p["min_close_ts"]]
        if p.get("max_close_ts") is not None:
            rows = [m for m in rows if bot.ts(m["close_time"]) <= p["max_close_ts"]]
        return {"markets": rows[:p.get("limit", 100)]}

    def page(self, s):
        """The series as Kalshi pages it: tomorrow's markets first, the live one only after them."""
        if s not in self.books:
            return []
        ahead = [{"ticker": f"{s}-F{k}", "status": "initialized", "open_time": iso(self.window + 900 * k),
                  "close_time": iso(self.window + 900 * (k + 1))} for k in range(1, self.AHEAD + 1)]
        live = [{"ticker": f"{s}-{self.suffix}", "status": "active", "open_time": iso(self.window + self.skew),
                 "close_time": iso(self.window + 900)}]
        behind = [{"ticker": f"{s}-P{k}", "status": "finalized", "open_time": iso(self.window - 900 * (k + 1)),
                   "close_time": iso(self.window - 900 * k)} for k in range(1, self.BEHIND + 1)]
        return ahead + live + behind


def listing(env, k=None, window=W):
    b = bot.Bot(k or BrokenFilterKalshi(), env, False)
    assert b.load_catalog()
    return b, b.listed(window)


# ------------------------------------------------------------------ the market is found
def test_it_finds_this_windows_market_while_the_status_filter_is_broken(env):
    """The bug: with status=open this came back empty and 27 windows passed unbet."""
    _, got = listing(env)
    assert [m["ticker"] for m in got] == ["KXBTC15M-A", "KXGOLD15M-A", "KXETH15M-A"]
    assert all(m["open"] == W and m["close"] == W + 900 for m in got)


def test_it_asks_by_close_time_and_sends_no_status_at_all(env):
    """Every status name Kalshi still takes is the wrong one for a live market, so the window's close time is
    what identifies it. The range must stay tight: an unfiltered page is thousands of markets, and this request
    sits on the path that gets orders out in about 124 ms."""
    k = BrokenFilterKalshi()
    listing(env, k)
    asked = [p for p in k.asked if "series_ticker" in p]
    assert len(asked) == 3
    for p in asked:
        assert "status" not in p
        assert p["min_close_ts"] <= W + 900 <= p["max_close_ts"]
        assert p["max_close_ts"] - p["min_close_ts"] <= 2    # this window's market, not a page of them
        assert p["limit"] <= 50


def test_dropping_the_filter_without_the_close_range_would_not_have_found_it(env):
    """Why the naive fix doesn't work: the live market is not in the first 50 of an unfiltered page."""
    k = BrokenFilterKalshi()
    page = k.markets(series_ticker="KXBTC15M", limit=50)["markets"]
    assert not any(m["status"] == "active" for m in page)


def test_a_market_that_closes_on_the_window_but_opened_elsewhere_is_skipped(env):
    """The open-time match is still the one that says this is the window's market."""
    k = BrokenFilterKalshi()
    k.skew = 300
    _, got = listing(env, k)
    assert got == []


def test_a_window_with_nothing_listed_comes_back_empty(env):
    k = BrokenFilterKalshi()
    k.window = W + 900           # the series lists the next window's markets, not this one's
    _, got = listing(env, k)
    assert got == []


# ------------------------------------------------------------------ an empty window is never silent
def test_a_window_that_lists_nothing_says_so(env, capsys):
    k = BrokenFilterKalshi()
    k.window = W + 900
    b = bot.Bot(k, env, False)
    b.step(ENTRY)
    out = capsys.readouterr().out
    assert "no markets" in out and "12:00" in out    # the window it missed, in ET


def test_it_says_so_once_a_window_not_once_a_poll(env, capsys):
    k = BrokenFilterKalshi()
    k.window = W + 900
    b = bot.Bot(k, env, False)
    for dt in range(0, 40, 3):                       # the whole grace, a poll every 3 s
        b.step(ENTRY + dt)
    assert capsys.readouterr().out.count("no markets") == 1
    assert b.empty == 1


def test_the_run_of_empty_windows_grows_and_a_window_that_lists_ends_it(env):
    k = BrokenFilterKalshi()
    k.window = W + 900
    b = bot.Bot(k, env, False)
    b.step(ENTRY)
    k.window, k.suffix = W + 900, "B"
    b.step(ENTRY + 900)                              # the next window does list: the run is over
    assert b.empty == 0


def test_the_run_counts_only_windows_that_listed_nothing(env):
    k = BrokenFilterKalshi()
    b = bot.Bot(k, env, False)
    for w in range(3):
        k.window = W + 900 * w + 900                 # always one window ahead: nothing ever lists
        b.step(ENTRY + 900 * w)
    assert b.empty == 3


def test_no_listing_anywhere_depends_on_the_status_filter():
    """Three places build this request: Bot.listed, fast_entry.MarkReader.listed and the dashboard's live feed.
    One of them left on status=open is one that goes quiet again the next time the filter stops matching."""
    for module in (bot, fast_entry, dashboard):
        src = pathlib.Path(module.__file__).read_text(encoding="utf-8")
        assert 'status="open"' not in src, module.__name__
