"""skipped_edge.py: the live entry rule replayed on the 15-minute series the bot skips.

The rule's money is what matters here, so these tests pin the economics a bet at a time -- the
favourite the rule picks, the price floor it respects, the fee it pays, and the cents per dollar
staked it reports -- against hand-worked numbers, on minute files built in a temporary folder.
Nothing here reads the real CSVs or touches the network.
"""

from __future__ import annotations

import csv
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

RESEARCH = Path(__file__).resolve().parent.parent
for path in (RESEARCH, RESEARCH.parent.parent):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

UTC = timezone.utc
MINUTES = range(1, 16)
FIELDS = (["series", "ticker", "open_time", "resolved_yes"]
          + [f"p{k}" for k in MINUTES] + [f"b{k}" for k in MINUTES] + [f"a{k}" for k in MINUTES])
START = datetime(2026, 10, 1, 12, tzinfo=UTC)


def row(series, n, yes, bid, ask, minute=8):
    """One market whose quotes sit at (bid, ask) from `minute` on, settling YES when `yes`."""
    opened = START + timedelta(minutes=15 * n)
    r = {"series": series, "ticker": f"{series}-{n:04d}", "open_time": opened.strftime("%Y-%m-%dT%H:%M:%SZ"),
         "resolved_yes": "1" if yes else "0"}
    for k in MINUTES:
        quoted = k >= minute
        r[f"p{k}"] = ask if quoted else ""
        r[f"b{k}"] = bid if quoted else ""
        r[f"a{k}"] = ask if quoted else ""
    return r


def write(folder, rows, name="minutes_skipped.csv"):
    with open(folder / name, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


@pytest.fixture()
def here(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "universe.json").write_text('{"series": []}', encoding="utf-8")
    return tmp_path


@pytest.fixture()
def mod(here):
    import skipped_edge
    import importlib
    return importlib.reload(skipped_edge)


# ---------------------------------------------------------------- one bet at a time


def test_one_winning_bet_earns_the_spread_less_the_fee(mod, here):
    """$10 on a 95c YES favourite that settles YES: 10.5263 contracts, a 4c fee, 48.63c profit."""
    write(here, [row("KXEURUSD15M", 1, yes=True, bid=0.94, ask=0.95)])
    r = mod.replay(["KXEURUSD15M"])
    assert r["bets"] == 1 and r["wins"] == 1
    assert r["contracts"] == pytest.approx(10 / 0.95, rel=1e-9)
    assert r["fees"] == pytest.approx(0.04)
    # the report rounds money to the cent and cents per dollar to three places, as the rest of the research does
    assert r["pnl"] == pytest.approx(10 / 0.95 - 10 - 0.04, abs=5e-3)
    assert r["centsPerDollar"] == pytest.approx((10 / 0.95 - 10 - 0.04) * 10, abs=5e-4)


def test_a_loss_costs_the_whole_stake_and_the_fee(mod, here):
    write(here, [row("KXEURUSD15M", 1, yes=False, bid=0.94, ask=0.95)])
    r = mod.replay(["KXEURUSD15M"])
    assert r["bets"] == 1 and r["wins"] == 0
    assert r["pnl"] == pytest.approx(-10 - 0.04, abs=5e-3)


def test_the_no_side_can_be_the_favourite(mod, here):
    """A 3c YES bid makes NO the 97c favourite; settling NO wins it."""
    write(here, [row("KXEURUSD15M", 1, yes=False, bid=0.03, ask=0.04)])
    r = mod.replay(["KXEURUSD15M"])
    assert r["bets"] == 1 and r["wins"] == 1
    assert r["bySide"]["no"]["bets"] == 1


def test_the_price_floor_skips_cheap_favourites(mod, here):
    """The live rule's floor is 92c: an 80c favourite is no bet, a 92c one is."""
    write(here, [row("KXEURUSD15M", 1, yes=True, bid=0.79, ask=0.80),
                 row("KXEURUSD15M", 2, yes=True, bid=0.91, ask=0.92)])
    r = mod.replay(["KXEURUSD15M"])
    assert r["bets"] == 1
    assert r["bySeries"]["KXEURUSD15M"]["bets"] == 1


def test_a_market_with_no_quote_at_entry_is_skipped(mod, here):
    write(here, [row("KXEURUSD15M", 1, yes=True, bid=0.94, ask=0.95, minute=12)])
    assert mod.replay(["KXEURUSD15M"])["bets"] == 0


def test_a_dead_heat_is_no_favourite(mod, here):
    """Both sides at 50c: the rule has no favourite to buy."""
    write(here, [row("KXEURUSD15M", 1, yes=True, bid=0.50, ask=0.50)])
    assert mod.replay(["KXEURUSD15M"])["bets"] == 0


# ---------------------------------------------------------------- the report


def test_cents_per_dollar_and_its_t_stat_come_from_the_bets(mod, here):
    """Nine 95c winners and one loser: the mean and t-stat of cents per $1 staked, by hand."""
    rows = [row("KXEURUSD15M", n, yes=n > 1, bid=0.94, ask=0.95) for n in range(1, 11)]
    write(here, rows)
    r = mod.replay(["KXEURUSD15M"])
    win, lose = (10 / 0.95 - 10 - 0.04) * 10, (-10 - 0.04) * 10
    each = [lose] + [win] * 9
    mu = sum(each) / 10
    sd = math.sqrt(sum((x - mu) ** 2 for x in each) / 9)
    assert r["bets"] == 10 and r["wins"] == 9
    assert r["centsPerDollar"] == pytest.approx(mu, abs=5e-4)
    assert r["t"] == pytest.approx(mu / (sd / math.sqrt(10)), abs=5e-3)


def test_bands_and_groups_split_the_bets(mod, here):
    write(here, [row("KXEURUSD15M", 1, yes=True, bid=0.92, ask=0.93),
                 row("KXCRYPTOLEAD15M", 2, yes=True, bid=0.97, ask=0.98)])
    r = mod.replay(["KXEURUSD15M", "KXCRYPTOLEAD15M"])
    assert r["byGroup"]["fx"]["bets"] == 1
    assert r["byGroup"]["coin race"]["bets"] == 1
    assert r["byBand"]["92-94"]["bets"] == 1
    assert r["byBand"]["98-100"]["bets"] == 1


def test_an_unknown_series_reports_no_bets(mod, here):
    write(here, [row("KXEURUSD15M", 1, yes=True, bid=0.94, ask=0.95)])
    r = mod.replay(["KXNOSUCH15M"])
    assert r["bets"] == 0 and r["centsPerDollar"] is None and r["t"] is None


# ---------------------------------------------------------------- the live fill gap


def test_the_live_slip_is_paid_on_top_of_the_ask(mod, here):
    """Live fills landed 0.4c over the candle ask (live_fills.py), so the rule can be charged that gap."""
    write(here, [row("KXEURUSD15M", 1, yes=True, bid=0.94, ask=0.95)])
    r = mod.replay(["KXEURUSD15M"], slip=0.004)
    assert r["slip"] == 0.004
    assert r["contracts"] == pytest.approx(10 / 0.954, rel=1e-9)
    assert r["bets"] == 1 and r["byBand"]["94-96"]["bets"] == 1


def test_the_slip_never_pays_over_the_ceiling(mod, here):
    """A 99.9c favourite is already Kalshi's dearest quote; the gap cannot push the price past it."""
    write(here, [row("KXEURUSD15M", 1, yes=True, bid=0.998, ask=0.999)])
    r = mod.replay(["KXEURUSD15M"], slip=0.004)
    assert r["contracts"] == pytest.approx(10 / 0.999, rel=1e-9)


def test_the_floor_is_judged_on_the_quote_not_the_slipped_price(mod, here):
    """The bot decides on what it sees: a 92c ask is a bet even though it pays 92.4c."""
    write(here, [row("KXEURUSD15M", 1, yes=True, bid=0.91, ask=0.92)])
    assert mod.replay(["KXEURUSD15M"], slip=0.004)["bets"] == 1


# ---------------------------------------------------------------- how a window's bets land together


def test_a_window_with_several_bets_reports_its_own_loss(mod, here):
    """Coin Race runs five markets a window and exactly one settles YES, so a window's bets move together:
    the report says how many bets a window takes and the worst window's loss."""
    rows = [row(f"KXCRYPTOLEAD15M", 1, yes=False, bid=0.02, ask=0.03) for _ in range(1)]
    rows = []
    for k in range(5):                      # one window, five markets, the last one leading
        r = row("KXCRYPTOLEAD15M", 1, yes=k == 4, bid=0.02, ask=0.03)
        r["ticker"] = f"KXCRYPTOLEAD15M-0001-{k}"
        rows.append(r)
    write(here, rows)
    r = mod.replay(["KXCRYPTOLEAD15M"])
    assert r["bets"] == 5 and r["losses"] == 1  # all five bought NO at 98c; the leader's NO lost
    assert r["windows"] == 1
    assert r["betsPerWindow"] == pytest.approx(5.0)
    assert r["worstWindow"] == pytest.approx(r["pnl"], abs=5e-3)


# ---------------------------------------------------------------- how wide the market is at entry


def test_the_entry_spread_is_reported(mod, here):
    """A wide market is a thin one: the candles' own bid-ask gap at entry, in cents, per series and group."""
    write(here, [row("KXEURUSD15M", 1, yes=True, bid=0.90, ask=0.95),
                 row("KXEURUSD15M", 2, yes=True, bid=0.94, ask=0.95)])
    r = mod.replay(["KXEURUSD15M"])
    assert r["bets"] == 2
    assert r["spread"] == pytest.approx(3.0, abs=5e-3)           # (5c + 1c) / 2
    assert r["bySeries"]["KXEURUSD15M"]["spread"] == pytest.approx(3.0, abs=5e-3)
    assert r["byGroup"]["fx"]["spread"] == pytest.approx(3.0, abs=5e-3)


# ---------------------------------------------------------------- the two warning signs the live bot skips


def quotes(series, n, yes, path):
    """One market whose favourite's (bid, ask) follows `path`, a {minute: (bid, ask)} for minutes 6-8."""
    r = row(series, n, yes=yes, bid=0.94, ask=0.95)
    for k, q in path.items():
        r[f"b{k}"], r[f"a{k}"] = ("", "") if q is None else q
        r[f"p{k}"] = "" if q is None else q[1]
    return r


def test_a_wide_market_at_entry_is_skipped(mod, here):
    """"spread": the favourite's ask 2c or more over its bid at minute 8 -- a thin book."""
    write(here, [quotes("KXEURUSD15M", 1, True, {6: (0.93, 0.94), 7: (0.93, 0.94), 8: (0.93, 0.95)})])
    assert mod.replay(["KXEURUSD15M"])["bets"] == 1
    assert mod.replay(["KXEURUSD15M"], skip=["spread"])["bets"] == 0


def test_a_one_cent_spread_still_trades(mod, here):
    write(here, [quotes("KXEURUSD15M", 1, True, {6: (0.93, 0.94), 7: (0.93, 0.94), 8: (0.94, 0.95)})])
    assert mod.replay(["KXEURUSD15M"], skip=["spread"])["bets"] == 1


def test_a_favourite_that_jumped_ten_cents_is_skipped(mod, here):
    """"late": its mid up 10c or more in minute 8."""
    write(here, [quotes("KXEURUSD15M", 1, True, {6: (0.80, 0.81), 7: (0.80, 0.81), 8: (0.94, 0.95)})])
    assert mod.replay(["KXEURUSD15M"], skip=["late"])["bets"] == 0


def test_a_favourite_that_was_a_coin_flip_is_skipped(mod, here):
    """"late" again: its mid 50c or under a minute or two before entry."""
    write(here, [quotes("KXEURUSD15M", 1, True, {6: (0.44, 0.45), 7: (0.88, 0.89), 8: (0.94, 0.95)})])
    assert mod.replay(["KXEURUSD15M"], skip=["late"])["bets"] == 0


def test_a_steady_favourite_passes_both_signs(mod, here):
    write(here, [quotes("KXEURUSD15M", 1, True, {6: (0.90, 0.91), 7: (0.92, 0.93), 8: (0.94, 0.95)})])
    r = mod.replay(["KXEURUSD15M"], skip=["spread", "late"])
    assert r["bets"] == 1 and r["skip"] == ["spread", "late"]


def test_the_no_sides_own_quote_decides_the_signs(mod, here):
    """NO at 95c is a 4c-wide market when the YES quote is 1c/5c, so the spread sign catches it."""
    write(here, [quotes("KXEURUSD15M", 1, False, {6: (0.04, 0.05), 7: (0.04, 0.05), 8: (0.01, 0.05)})])
    r = mod.replay(["KXEURUSD15M"])
    assert r["bets"] == 1 and r["bySide"]["no"]["bets"] == 1
    assert mod.replay(["KXEURUSD15M"], skip=["spread"])["bets"] == 0


def test_a_missing_earlier_quote_cannot_trigger_late(mod, here):
    write(here, [quotes("KXEURUSD15M", 1, True, {6: None, 7: None, 8: (0.94, 0.95)})])
    assert mod.replay(["KXEURUSD15M"], skip=["late"])["bets"] == 1
