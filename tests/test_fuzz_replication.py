"""Property-based tests for kalshi_calibration/replication/: the 15-minute replication's statistics and its data file.

The hand-worked cases in test_replication.py fix each formula. These check the bookkeeping around them on
generated markets and bets: a fee rounds up to the cent and never down, a favourite costs at least half a
dollar, a stop rule's change in profit is exactly what it saved less what it gave up, a looser stop never
sells fewer bets, and a market written to minutes.csv reads back as the same market.
"""

from __future__ import annotations

import csv
import json
import math
from datetime import date, datetime, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from kalshi_calibration.analysis.statistics import wilson_interval
from kalshi_calibration.replication.dataset import Market, day_ts, load_markets
from kalshi_calibration.replication.fetch import FIELDS, MINUTES
from kalshi_calibration.replication.stats import (
    Bet,
    calibration,
    favourite,
    favourites,
    held,
    kelly,
    order_fee,
    own_quotes,
    periods,
    regime,
    stop_rule,
    wilson,
)
from test_replication import SETTINGS

K = 0.07
cents = st.integers(1, 999).map(lambda c: c / 1000)
quote = st.none() | st.tuples(cents, cents).map(lambda q: (min(q), max(q)))


# ------------------------------------------------------------------ intervals and fees


@given(st.integers(1, 5000).flatmap(lambda n: st.tuples(st.integers(0, n), st.just(n))))
def test_the_replications_wilson_matches_the_studys(kn):
    k, n = kn
    lo, hi = wilson(k, n)
    ref = wilson_interval(k, n, 0.95)
    assert lo == pytest.approx(ref[0], abs=5e-4) and hi == pytest.approx(ref[1], abs=5e-4)
    assert lo - 1e-12 <= k / n <= hi + 1e-12


@given(st.floats(0, 5000), st.floats(0, 1), st.floats(1, 3))
def test_an_order_fee_rounds_up_to_the_cent_and_never_down(contracts, price, mult):
    exact = mult * K * contracts * price * (1 - price)
    fee = order_fee(contracts, price, K, mult)
    assert round(fee * 100) == pytest.approx(fee * 100, abs=1e-6)
    assert exact - 1e-9 <= fee < exact + 0.01 + 1e-9


@given(st.floats(0, 5000), st.floats(0, 5000), st.floats(0, 1))
def test_a_bigger_order_never_pays_less(a, b, price):
    small, large = sorted((a, b))
    assert order_fee(small, price, K) <= order_fee(large, price, K)


# ------------------------------------------------------------------ favourites


@given(cents, cents)
def test_a_favourite_costs_at_least_half_a_dollar_on_an_uncrossed_book(a, b):
    bid, ask = min(a, b), max(a, b)
    fav = favourite(bid, ask)
    if fav is not None:
        side, price = fav
        assert price >= 0.5 - 1e-9 and side in ("yes", "no")
        assert price == (ask if side == "yes" else round(1 - bid, 4))


@given(st.sampled_from(["yes", "no"]), cents, cents)
def test_a_sides_own_book_is_never_crossed(side, a, b):
    bid, ask = min(a, b), max(a, b)
    own_bid, own_ask = own_quotes(side, bid, ask)
    assert own_bid <= own_ask + 1e-12
    assert own_ask - own_bid == pytest.approx(ask - bid, abs=1e-9)


@st.composite
def markets(draw, n_max=20):
    out = []
    for i in range(draw(st.integers(0, n_max))):
        quotes = draw(st.lists(quote, min_size=15, max_size=15))
        last = draw(st.lists(st.none() | cents, min_size=15, max_size=15))
        out.append(Market(series="KXBTC15M", ticker=f"T{i}", group=draw(st.sampled_from(["crypto", "metals"])),
                          open_ts=day_ts(date(2026, 8, 1)) + 900 * draw(st.integers(0, 6000)),
                          yes=draw(st.booleans()), last=(None, *last),
                          bid=(None, *(q[0] if q else None for q in quotes)),
                          ask=(None, *(q[1] if q else None for q in quotes))))
    return out


@given(markets())
def test_favourites_are_in_range_and_won_iff_their_side_settled(ms):
    expected = []
    for m in ms:
        fav = favourite(m.bid[SETTINGS.entry_minute], m.ask[SETTINGS.entry_minute])
        if fav and SETTINGS.favourite_low <= fav[1] <= SETTINGS.favourite_high:
            expected.append((m.open_ts, fav[0], fav[1], (fav[0] == "yes") == m.yes))
    bets = favourites(ms, SETTINGS)
    assert [(b.open_ts, b.side, b.ask, b.won) for b in bets] == expected
    for b in bets:
        assert len(b.quotes) == 15 and b.quotes[0] is None


@given(markets(), st.integers(1, 15))
def test_calibration_counts_every_market_with_a_trade_at_that_minute(ms, minute):
    table = calibration(ms, minute)
    assert sum(row["n"] for row in table) == sum(1 for m in ms if m.last[minute] is not None)
    for row in table:
        assert 0 <= row["band"] <= 9 and 0.0 <= row["actual"] <= 1.0
        assert row["gap"] == pytest.approx(row["actual"] - row["price"])
        assert row["lo"] <= row["actual"] + 1e-12 <= row["hi"] + 2e-12


# ------------------------------------------------------------------ bets


@st.composite
def bets(draw, n_max=25):
    out = []
    for _ in range(draw(st.integers(0, n_max))):
        quotes = draw(st.lists(quote, min_size=14, max_size=14))
        out.append(Bet(open_ts=day_ts(SETTINGS.split) + 900 * draw(st.integers(-3000, 3000)), series="S",
                       group=draw(st.sampled_from(["crypto", "metals", "energy"])), side="yes",
                       ask=draw(st.integers(900, 999).map(lambda c: c / 1000)), won=draw(st.booleans()),
                       quotes=(None, *quotes)))
    return out


@given(bets(), st.floats(0.05, 0.99))
def test_a_stop_rules_change_is_what_it_saved_less_what_it_gave_up(bs, level):
    out = stop_rule(bs, level, SETTINGS, K)
    assert out["delta"] == pytest.approx(out["saved"] - out["gave_up"], abs=1e-9)
    assert 0 <= out["sold_won"] <= out["sold"] <= len(bs)
    if out["sold"] == 0:
        assert out["delta"] == out["saved"] == out["gave_up"] == 0.0


@given(bets(), st.floats(0.05, 0.99), st.floats(0.05, 0.99))
def test_a_looser_stop_never_sells_fewer_bets(bs, a, b):
    tight, loose = sorted((a, b))
    assert stop_rule(bs, tight, SETTINGS, K)["sold"] <= stop_rule(bs, loose, SETTINGS, K)["sold"]


@given(bets())
def test_the_split_partitions_the_bets_and_regime_counts_them(bs):
    split = periods(bs, SETTINGS)
    assert len(split["before"]) + len(split["after"]) == len(bs)
    r = regime(bs, SETTINGS, K)
    assert r["before"]["bets"] + r["after"]["bets"] == len(bs)
    for p in r.values():
        if p["bets"]:
            assert 0 <= p["lost"] <= 1 and p["per_bet_cents"] == pytest.approx(p["total"] / p["bets"] * 100)


@given(bets(n_max=10).filter(bool), st.floats(1, 100), st.floats(0, 0.01))
def test_a_win_always_beats_a_loss_and_kelly_is_bounded(bs, stake, slip):
    b = bs[0]
    fill = min(b.ask + slip, 0.999)
    win = held(Bet(**{**b.__dict__, "won": True}), fill, stake, K)
    lose = held(Bet(**{**b.__dict__, "won": False}), fill, stake, K)
    assert win > lose and lose == pytest.approx(-stake - order_fee(stake / fill, fill, K))
    k = kelly(bs, stake, slip, K)
    assert 0.0 < k["cost"] < 1.0 + 0.01 and k["kelly"] <= 1.0 + 1e-12
    assert k["kelly"] == pytest.approx((k["win"] - k["cost"]) / (1 - k["cost"]))


# ------------------------------------------------------------------ minutes.csv round trip


@settings(max_examples=40)
@given(st.lists(st.tuples(st.sampled_from(["KXBTC15M", "KXGOLD15M", "KXCRYPTOLEAD15M"]),
                          st.integers(-10, 8000), st.booleans(), st.lists(st.none() | cents, min_size=45, max_size=45)),
                max_size=12))
def test_a_market_written_to_minutes_csv_reads_back_unchanged(tmp_path_factory, rows):
    folder = tmp_path_factory.mktemp("rep")
    groups = {"KXBTC15M": "crypto", "KXGOLD15M": "metals", "KXCRYPTOLEAD15M": "coin race"}
    (folder / "series.json").write_text(json.dumps({"series": [{"ticker": t, "group": g} for t, g in groups.items()]}))
    start = day_ts(SETTINGS.start)
    written = []
    with (folder / "minutes.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for i, (series, slot, yes, values) in enumerate(rows):
            open_ts = start + 900 * slot
            row = {"series": series, "ticker": f"T{i}", "resolved_yes": "1" if yes else "0",
                   "open_time": datetime.fromtimestamp(open_ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
            for j, k in enumerate(MINUTES):
                for f, offset in (("p", 0), ("b", 15), ("a", 30)):
                    v = values[offset + j]
                    row[f"{f}{k}"] = "" if v is None else v
            w.writerow(row)
            written.append((row, open_ts, yes, values))

    loaded = load_markets(SETTINGS, folder)
    end = day_ts(SETTINGS.end)
    expected = [(r, ts, yes, v) for r, ts, yes, v in written
                if groups[r["series"]] in SETTINGS.groups and start <= ts < end]
    assert sorted(m.ticker for m in loaded) == sorted(r["ticker"] for r, *_ in expected)
    assert [m.open_ts for m in loaded] == sorted(m.open_ts for m in loaded)
    by_ticker = {m.ticker: m for m in loaded}
    for r, ts, yes, values in expected:
        m = by_ticker[r["ticker"]]
        assert m.open_ts == ts and m.yes == yes and m.group == groups[r["series"]]
        assert list(m.last[1:]) == values[:15] and list(m.bid[1:]) == values[15:30] and list(m.ask[1:]) == values[30:]
        assert all(v is None or not math.isnan(v) for v in m.last[1:])
