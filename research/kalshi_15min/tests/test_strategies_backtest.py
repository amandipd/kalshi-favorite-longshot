"""strategies_backtest.py: every paper account replayed over the history, the file the dashboard's Research tab reads.

`run()` is checked on hand-built windows whose profit can be worked out by hand -- a win and a loss at a known
ask, the broke rule, whole contracts, one crypto bet a window, selling under 90c -- and then `main()` end to end
on the synthetic history, against the structure the dashboard reads and against `run()` called directly.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone

import pytest

EDGE = ["crypto", "metals", "energy"]
T0 = 1_784_332_800  # 2026-07-18T00:00:00Z


def market(yes=True, q8=(0.94, 0.96), series="KXBTC15M", group="crypto", **minutes):
    """A market quoted (bid, ask) = q8 at every minute, except minutes given as m9=(bid, ask) and so on."""
    q = {k: q8 for k in range(1, 16)}
    q.update({int(k[1:]): v for k, v in minutes.items()})
    return {"series": series, "group": group, "yes": yes, "q": q}


def flat(**extra):
    return {"id": "t", "name": "test", "minute": 8, "sizing": "flat", "groups": EDGE, **extra}


def fee(c, p):
    return math.ceil(0.07 * c * p * (1 - p) * 100 - 1e-9) / 100


# ------------------------------------------------------------------ helpers


def test_ts_reads_a_z_time(study):
    assert study.strategies_backtest.ts("2026-07-18T00:00:00Z") == T0


def test_favourite_and_fee_match_the_live_bot(study):
    from kalshi_bot import bot
    sb = study.strategies_backtest
    for bid, ask in ((0.94, 0.96), (0.03, 0.05), (0.49, 0.51), (None, 0.5)):
        got = sb.favourite(bid, ask)
        assert got == (bot.favourite(bid, ask) if bid is not None else (None, None))
    assert sb.fee(10 / 0.96, 0.96) == fee(10 / 0.96, 0.96) == bot.taker_fee(10 / 0.96, 0.96) == 0.03


def test_sell_point_is_the_first_minute_after_entry_under_the_line(study):
    sb = study.strategies_backtest
    m = market(m9=(0.91, 0.93), m10=(0.85, 0.87), m11=(0.20, 0.30), m15=(0.0, 0.01))
    assert sb.sell_point(m, "yes", 8, 0.90) == (10, 0.85)
    assert sb.sell_point(m, "yes", 8, 0.10) == (None, None)        # minute 15 is the close: never a sale
    no = market(q8=(0.03, 0.05), m12=(0.40, 0.45))                  # a NO position's bid is 1 - the YES ask
    assert sb.sell_point(no, "no", 8, 0.90) == (12, 0.55)
    gap = market(m9=(None, 0.5), m10=(0.5, None))
    assert sb.sell_point(gap, "yes", 8, 0.90) == (None, None)        # a minute missing a quote can't sell


def test_own_quote(study):
    sb = study.strategies_backtest
    m = market(q8=(0.03, 0.05), m7=(None, 0.5))
    assert sb.own_quote(m, "yes", 8) == (0.03, 0.05)
    assert sb.own_quote(m, "no", 8) == (0.95, 0.97)
    assert sb.own_quote(m, "yes", 7) is None and sb.own_quote(m, "yes", 99) is None


@pytest.mark.parametrize("skip,quotes,expected", [
    (["spread"], {"m8": (0.94, 0.96)}, True),                       # exactly 2c
    (["spread"], {"m8": (0.945, 0.96)}, False),
    (["late"], {"m6": (0.49, 0.51)}, True),                         # 50c at minute 6
    (["late"], {"m7": (0.83, 0.85)}, True),                         # up 11c in minute 8 (84c -> 95c)
    (["late"], {"m7": (0.86, 0.88)}, False),
    (["slow"], {"m5": (0.60, 0.62)}, True),
    (["slow"], {"m5": (0.70, 0.72)}, False),
    ([], {"m6": (0.1, 0.2)}, False),
])
def test_each_warning_sign(study, skip, quotes, expected):
    m = market(q8=(0.945, 0.955), **quotes)
    assert study.strategies_backtest.skipped(flat(skip=skip), m, "yes") is expected


@pytest.mark.xfail(strict=True, reason="bug: the late-favourite rule compares an unrounded float difference with "
                   "0.10, so an exact 10c jump (85c -> 95c mid) computes as 0.0999... and is not skipped; bot.warning "
                   "rounds to 6 places and skips it, so the backtest and the live bot disagree on exact 10c jumps")
def test_an_exact_10c_jump_in_minute_8_is_a_late_favourite(study):
    m = market(q8=(0.945, 0.955), m7=(0.84, 0.86))
    assert study.strategies_backtest.skipped(flat(skip=["late"]), m, "yes") is True


def test_stake_for_each_sizing_rule(study):
    sb = study.strategies_backtest
    assert sb.stake_for(flat(), 1e6) == sb.STAKE
    assert sb.stake_for({"sizing": "fraction"}, 240.0) == 10.0
    assert sb.stake_for({"sizing": "capped"}, 240.0) == 3.6              # 1.5% of $240, the live bot's
    assert sb.stake_for({"sizing": "capped"}, 240.0, n=10) == 2.4        # 10% of $240 shared by 10 bets
    assert sb.stake_for({"sizing": "capped", "pct": 0.01}, 1000.0) == 10.0
    assert sb.stake_for({"sizing": "capped"}, 33.33) == 0.49             # floored to the cent, as bot.py floors it
    # an account can carry both numbers: the paper trader's 3% a bet, 20% a window
    assert sb.stake_for({"sizing": "capped", **sb.PAPER_CAPS}, 240.0) == 7.2
    assert sb.stake_for({"sizing": "capped", **sb.PAPER_CAPS}, 240.0, n=10) == 4.8
    assert sb.stake_for({"sizing": "capped", "windowCap": 0.20}, 240.0, n=10) == 3.6   # the per-bet cap binds first


def test_the_live_accounts_size_like_the_real_bot_with_capped_copies(study):
    """The main live replay is the bot as it trades since Oct 10, with no order cap; the $10 cap it had until then
    lives on in two copies, the same rule otherwise."""
    from kalshi_bot import bot
    sb = study.strategies_backtest
    accounts = {s["id"]: s for s in sb.STRATS}
    live, live500 = accounts["live"], accounts["live500"]
    assert "maxOrder" not in live and "maxOrder" not in live500
    assert (live["start"], live500["start"]) == (225.0, 500.0)
    for bankroll, n in ((225.0, 1), (333.0, 1), (1000.0, 1), (5000.0, 3), (100.0, 10)):
        assert sb.stake_for(live, bankroll, n) == pytest.approx(bot.stake_for(bankroll, n))
    assert sb.stake_for(live, 1000.0) == 15.0   # 1.5%, the bot's own since Oct 15
    same = lambda s: {k: v for k, v in s.items() if k not in ("id", "name", "start", "maxOrder")}
    for sid, start in (("livecap", 225.0), ("live500cap", 500.0)):
        s = accounts[sid]
        assert s["maxOrder"] == 10.0 and s["start"] == start and same(s) == same(live), sid
        assert sb.stake_for(s, 1000.0) == 10.0
    assert "livenc" not in accounts and "live500nc" not in accounts   # the uncapped copies are the main accounts now
    # (liveliq exists only beside a liquidity.json: test_real_liquidity.py checks it has no cap either; every bankroll
    # and bet count is in test_fuzz_research.py)


# ------------------------------------------------------------------ run(), by hand


def run(study, strat, windows, slip=0.0, hours=2, **kw):
    return study.strategies_backtest.run(strat, windows, slip, T0, hours, **kw)


def test_a_win_and_a_loss_at_a_known_ask(study):
    windows = {T0: [market(yes=True)], T0 + 900: [market(yes=False)]}
    r = run(study, flat(), windows)
    c = 10 / 0.96
    win, loss = c - 10 - fee(c, 0.96), -10 - fee(c, 0.96)
    assert (r["bets"], r["wins"]) == (2, 1)
    assert r["final"] == round(240 + win + loss, 2) and r["broke"] is None
    assert r["perBet"] == pytest.approx((win + loss) / 20 * 1000)
    assert r["need"] == pytest.approx((10 + fee(c, 0.96)) / c)
    assert r["worstWindow"] == round(loss, 2) and r["losingDays"] == 1 and r["days"] == 1
    assert len(r["curve"]) == 2 and r["curve"][0] == round(240 + win + loss, 2)
    assert r["byGroup"] == [{"key": "crypto", "n": 2, "wins": 1, "pnl": round(win + loss, 2), "staked": 20.0,
                             "first": "2026-07-18T00:00:00+00:00"}]
    assert r["byBand"][0]["key"] == "96–98" and r["bySeries"][0]["key"] == "BTC"


def test_each_market_records_the_first_window_it_was_bet_in(study):
    """The per-market view needs each market's own start, not the whole store's: Kalshi listed gold in
    July and Brent in October, so a shared start date would flatter the newer ones."""
    windows = {T0: [market(series="KXBTC15M")],
               T0 + 900: [market(series="KXETH15M"), market(series="KXBTC15M")]}
    r = run(study, flat(), windows)
    assert {g["key"]: g["first"] for g in r["bySeries"]} == {"BTC": "2026-07-18T00:00:00+00:00",
                                                             "ETH": "2026-07-18T00:15:00+00:00"}


def test_the_market_and_group_tallies_carry_a_first_window_and_the_band_one_does_not(study):
    """The Backtest tab marks on its chart where each asset class started trading (Oct 28), which needs the group's
    own first window. A price band has no start date to speak of, so byBand keeps the shape it had."""
    r = run(study, flat(), {T0: [market()]})
    assert set(r["byGroup"][0]) == {"key", "n", "wins", "pnl", "staked", "first"}
    assert set(r["byBand"][0]) == {"key", "n", "wins", "pnl", "staked"}
    assert set(r["bySeries"][0]) == {"key", "n", "wins", "pnl", "staked", "first"}


def test_each_asset_class_records_the_first_window_it_was_bet_in(study):
    """Crypto from the start, metals only once Kalshi listed them: the chart's markers come from these."""
    windows = {T0: [market(series="KXBTC15M", group="crypto")],
               T0 + 900: [market(series="KXGOLD15M", group="metals"),
                          market(series="KXETH15M", group="crypto")]}
    r = run(study, flat(), windows)
    assert {g["key"]: g["first"] for g in r["byGroup"]} == {"crypto": "2026-07-18T00:00:00+00:00",
                                                            "metals": "2026-07-18T00:15:00+00:00"}


def test_live_fills_cost_the_slip_on_every_contract(study):
    windows = {T0: [market(yes=True)]}
    r = run(study, flat(), windows, slip=0.004)
    c = 10 / 0.964
    assert r["final"] == round(240 + c - 10 - fee(c, 0.964), 2)


def test_markets_outside_the_band_or_the_groups_are_not_bet(study):
    windows = {T0: [market(q8=(0.6, 0.62)), market(group="fx", series="KXEURUSD15M"), market(q8=(0.999, 1.0))]}
    assert run(study, flat(), windows)["bets"] == 0
    assert run(study, flat(groups=None), {T0: [market(group="fx", series="KXEURUSD15M")]})["bets"] == 1


def test_an_account_too_small_for_a_bet_is_broke_and_stops(study):
    windows = {T0: [market()], T0 + 900: [market()]}
    r = run(study, flat(start=5.0), windows)
    assert r["broke"] == "2026-07-18T00:00:00+00:00" and r["final"] == 0.0 and r["maxDD"] == 1.0 and r["bets"] == 0
    assert r["curve"] == [None, None]


def test_whole_contracts_round_each_bet_down(study):
    strat = {"id": "w", "minute": 8, "sizing": "capped", "groups": EDGE, "start": 200.0, "whole": True}
    r = run(study, strat, {T0: [market(yes=True)]})
    # 1.5% of $200 is $3 a bet, and $3 at 96c buys 3 whole contracts, not 3.125
    assert r["final"] == round(200 + 3 - 3 * 0.96 - fee(3, 0.96), 2)


def test_one_crypto_bet_a_window_takes_the_highest_priced(study):
    strat = flat(onePer=["crypto"])
    windows = {T0: [market(q8=(0.93, 0.95), yes=False), market(q8=(0.96, 0.97), yes=True),
                    market(q8=(0.94, 0.96), series="KXGOLD15M", group="metals")]}
    r = run(study, strat, windows)
    assert r["bets"] == 2 and r["wins"] == 2


def test_the_window_cap_shares_10_percent_among_the_window(study):
    strat = {"id": "c", "minute": 8, "sizing": "capped", "groups": EDGE}
    windows = {T0: [market(yes=True) for _ in range(10)]}
    r = run(study, strat, windows)
    c = 2.4 / 0.96                       # 10% of $240 over 10 bets, each under the 1.5% a bet
    assert r["final"] == round(240 + 10 * (c - 2.4 - fee(c, 0.96)), 2)


def test_an_exit_account_sells_under_the_line_and_accounts_for_it(study):
    strat = flat(exit=0.90)
    winner_sold = market(yes=True, m10=(0.85, 0.87))
    loser_sold = market(yes=False, m9=(0.50, 0.52))
    loser_held = market(yes=False)
    r = run(study, strat, {T0: [winner_sold, loser_sold, loser_held]})
    c = 10 / 0.96
    held_win, held_loss = c - 10 - fee(c, 0.96), -10 - fee(c, 0.96)
    sale = lambda px: c * px - fee(c, px) - 10 - fee(c, 0.96)  # noqa: E731
    x = r["exit"]
    assert (x["sold"], x["soldWon"], x["at"]) == (2, 1, 0.90)
    assert x["gaveUp"] == round(held_win - sale(0.85), 2) and x["saved"] == round(sale(0.50) - held_loss, 2)
    assert x["net"] == round(x["saved"] - x["gaveUp"], 2) and x["byMinute"] == {"9": 1, "10": 1}
    assert r["wins"] == 0, "a sold bet is never a win"
    assert r["final"] == round(240 + sale(0.85) + sale(0.50) + held_loss, 2)


def test_a_late_start_leaves_the_curve_empty_before_it(study):
    windows = {T0: [market()], T0 + 3600: [market()]}
    r = run(study, flat(), windows, hours=3, start_ts=T0 + 3600)
    assert r["bets"] == 1 and r["curve"][0] is None and r["curve"][1] is not None


def test_period_stats_carry_the_bankroll_on(study):
    ps = study.strategies_backtest.period_stats
    recs = [(T0, 240.0, 5.0, [10.0]), (T0 + 900, 245.0, -15.0, [-20.0, 5.0])]
    s = ps(recs, T0, T0 + 1800, None)
    assert (s["start"], s["end"], s["pnl"], s["bets"]) == (240.0, 230.0, -10.0, 3)
    assert s["mu"] == pytest.approx(-5 / 3) and s["lo"] is None and not s["brokeHere"]
    assert ps(recs, T0 + 5000, T0 + 9000, None) is None
    assert ps(recs, T0, T0 + 1800, T0 + 900)["brokeHere"]


def test_edge_is_the_rule_alone_at_10_dollars_from_an_endless_bankroll(study):
    windows = {T0: [market(yes=True)], T0 + 900: [market(yes=False)]}
    e = study.strategies_backtest.edge({"id": "c", "minute": 8, "sizing": "capped", "groups": EDGE}, windows, 0.0, T0, 2)
    c = 10 / 0.96
    assert e["pnl"] == round(c - 10 - fee(c, 0.96) + -10 - fee(c, 0.96), 2) and e["bets"] == 2
    assert e["ddUsd"] == -e["pnl"] and e["curve"][-1] == e["pnl"]   # the deepest fall from the $0 start


# ------------------------------------------------------------------ the synthetic history, end to end


def test_load_reads_every_window_once_inside_the_periods(study):
    sb = study.strategies_backtest
    windows, first, last = sb.load()
    assert first == sb.ts(study.history.FIRST) == sb.ts("2025-12-10T00:00:00Z") and last == sb.ts(study.history.end()) - 900
    assert min(windows) < sb.ts(study.history.JUL18), "minutes_pre.csv is read too"
    assert sum(len(ms) for ms in windows.values()) == len(study.data["rows"])
    assert all(first <= t <= last for t in windows)


@pytest.fixture(scope="module")
def strategies(study):
    study.strategies_backtest.main()
    with open("strategies.json", encoding="utf-8") as fh:
        return json.load(fh)


def test_main_writes_every_account_under_both_fills_and_all_three_starts(study, strategies):
    ids = [s["id"] for s in study.strategies_backtest.STRATS]
    assert [s["id"] for s in strategies["strategies"]] == ids and len(ids) == len(set(ids))
    assert set(strategies["scenarios"]) == {"backtest", "live"}
    assert set(strategies["starts"]) == {"dec10", "jul18", "aug24"} and strategies["starts"]["jul18"] == strategies["scenarios"]
    assert strategies["t0"] == "2025-12-10T00:00:00+00:00"
    assert [p["key"] for p in strategies["periods"]] == ["pre", "before", "build", "paper"]
    for start in strategies["starts"].values():
        for runs in start.values():
            assert set(runs) == set(ids)
            for r in runs.values():
                assert len(r["curve"]) == strategies["hours"]
                assert set(r["periods"]) == {"pre", "before", "build", "paper"}
    assert set(strategies["edge"]["live"]) == set(ids)


def test_both_outcomes_happen_on_the_synthetic_history(strategies):
    broke = [r["broke"] is not None for r in strategies["scenarios"]["live"].values()]
    assert any(broke) and not all(broke)


def test_main_agrees_with_run_called_directly(study, strategies):
    sb = study.strategies_backtest
    windows, first, last = sb.load()
    hours = int((last + 900 - first) // 3600) + 1
    strat = next(s for s in sb.STRATS if s["id"] == "m8")
    assert sb.run(strat, windows, 0.004, first, hours, sb.ts(study.history.JUL18)) == strategies["scenarios"]["live"]["m8"]
    assert sb.run(strat, windows, 0.004, first, hours) == strategies["starts"]["dec10"]["live"]["m8"]


def test_the_same_rule_makes_the_same_bets_under_either_fill(strategies):
    for sid, e in strategies["edge"]["backtest"].items():
        assert e["bets"] == strategies["edge"]["live"][sid]["bets"], sid


def test_exit_accounts_name_their_base_account(study, strategies):
    for s in strategies["strategies"]:
        if s.get("base"):
            assert s["base"] in strategies["scenarios"]["live"] and s["exit"] == study.strategies_backtest.EXIT
            x = strategies["scenarios"]["live"][s["id"]]["exit"]
            assert x["net"] == pytest.approx(x["saved"] - x["gaveUp"], abs=0.011) and x["soldWon"] <= x["sold"]


def test_the_jul18_start_is_the_history_from_jul18_alone(study, strategies):
    """Adding the months before Jul 18 must not move a number the Jul 18 replays reported before: each one equals a
    replay of the windows from Jul 18 alone, its hourly curve shifted to start on Dec 10 with no values before."""
    sb = study.strategies_backtest
    windows, first, last = sb.load()
    jul18 = sb.ts(study.history.JUL18)
    later = {t: ms for t, ms in windows.items() if t >= jul18}
    hours = int((last + 900 - jul18) // 3600) + 1
    skip = int((jul18 - first) // 3600)
    for sid in ("m8", "m8c", "live", "m8x"):
        strat = next(s for s in sb.STRATS if s["id"] == sid)
        alone = sb.run(strat, later, 0.004, jul18, hours)
        r = strategies["scenarios"]["live"][sid]
        assert r["curve"][:skip] == [None] * skip and r["curve"][skip:] == alone["curve"], sid
        assert r["periods"]["pre"] is None and r["periods"] == alone["periods"], sid
        for key in alone:
            if key not in ("curve", "periods", "halves"):   # halves split the whole span, which now starts on Dec 10
                assert r[key] == alone[key], (sid, key)


def test_only_the_dec10_start_bets_before_jul18(study, strategies):
    pre = lambda r: (r["periods"]["pre"] or {}).get("bets", 0)  # noqa: E731
    assert pre(strategies["starts"]["dec10"]["live"]["m8"]) > 0
    assert all(pre(r) == 0 for k in ("jul18", "aug24") for r in strategies["starts"][k]["live"].values())
    assert strategies["starts"]["dec10"]["live"]["m8"]["bets"] > strategies["scenarios"]["live"]["m8"]["bets"]


def test_every_fed_decision_is_blacked_out_at_2pm_new_york_time(study):
    sb = study.strategies_backtest
    assert sb.FED_DAYS == ["2025-12-10", "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17", "2026-07-29", "2026-09-16"]
    utc = [datetime.fromtimestamp(a, timezone.utc).strftime("%Y-%m-%d %H:%M") for a, _ in sb.FED_WINDOWS]
    # 2:00 pm ET is 19:00 UTC in winter (EST) and 18:00 UTC from Mar 8 (EDT)
    assert utc == ["2025-12-10 19:00", "2026-01-28 19:00", "2026-03-18 18:00", "2026-04-29 18:00", "2026-06-17 18:00",
                   "2026-07-29 18:00", "2026-09-16 18:00"]
    assert all(z - a == 5400 for a, z in sb.FED_WINDOWS), "2:00 to 3:30 pm"


# ------------------------------------------------------------------ the Oct 11 strategy-lab candidates (lab/edge_map.md)
# skipSeries leaves whole markets out; skipSlots skips the weekday windows opening at given ET times, as a blackout
# does; maxPer keeps at most K of a group's candidates a window, the tightest own spread first (to 4 places), then
# the dearest, then the order listed, and sizes the window off the bets it places.

CANDIDATES = {"livenh": ("The live bot · skip HYPE", {"skipSeries": ["KXHYPE15M"]}),
              "liveno": ("The live bot · skip the 9:30 open", {"skipSlots": ["09:30"]}),
              "livec3": ("The live bot · 3 crypto bets a window", {"maxPer": {"crypto": 3}}),
              "live3x": ("The live bot · all three", {"skipSeries": ["KXHYPE15M"], "skipSlots": ["09:30"],
                                                       "maxPer": {"crypto": 3}})}
NEW_KEYS = ("skipSeries", "skipSlots", "maxPer")


def et(s):
    """A New York wall-clock time as a UTC timestamp, daylight saving included."""
    from zoneinfo import ZoneInfo
    return datetime.fromisoformat(s).replace(tzinfo=ZoneInfo("America/New_York")).timestamp()


def run_at(study, strat, windows, slip=0.0):
    t0 = min(windows)
    return study.strategies_backtest.run(strat, windows, slip, t0, int((max(windows) + 900 - t0) // 3600) + 1)


def keys(r):
    return sorted(g["key"] for g in r["bySeries"])


def test_skip_series_leaves_those_markets_out(study):
    windows = {T0: [market(series="KXHYPE15M"), market(series="KXBTC15M")]}
    assert run(study, flat(), windows)["bets"] == 2
    r = run(study, flat(skipSeries=["KXHYPE15M"]), windows)
    assert r["bets"] == 1 and keys(r) == ["BTC"]


@pytest.mark.parametrize("when, bets", [
    ("2026-07-20T09:30", 0),    # a Monday, 9:30 ET (EDT): skipped
    ("2026-07-20T09:45", 1),    # the next window that Monday still bets
    ("2026-07-20T09:15", 1),    # ... and the one before
    ("2026-07-18T09:30", 1),    # a Saturday at 9:30: weekends are unaffected
    ("2026-03-02T09:30", 0),    # a Monday before Mar 8 (EST, 14:30 UTC)
    ("2026-03-09T09:30", 0),    # the Monday after (EDT, 13:30 UTC)
    ("2026-03-09T10:30", 1),    # 14:30 UTC that Monday is 10:30 ET now: it bets
])
def test_skip_slots_skips_the_weekday_windows_opening_then_in_new_york(study, when, bets):
    windows = {et(when): [market(yes=False)]}
    r = run_at(study, flat(skipSlots=["09:30"]), windows)
    assert r["bets"] == bets
    if not bets:   # skipped the way a blackout is: nothing placed, the bankroll untouched
        assert r["final"] == 240.0 and r["worstWindow"] == 0.0
    assert run_at(study, flat(), windows)["bets"] == 1


def test_skip_slots_only_touches_its_own_windows_in_a_mixed_history(study):
    times = ["2026-03-02T09:30", "2026-03-02T09:45", "2026-03-07T09:30", "2026-03-09T09:30", "2026-03-09T10:30"]
    windows = {et(s): [market()] for s in times}
    assert run_at(study, flat(skipSlots=["09:30"]), windows)["bets"] == 3


def test_max_per_keeps_the_tightest_spreads_then_the_dearest(study):
    """5 crypto favourites and 1 metals one qualify; at most 3 crypto: C and E (0.5c spreads), then B over A at 1c --
    0.96 - 0.95 and 0.94 - 0.93 differ only in float noise, so the dearer B wins the tie. D is dearest but widest."""
    window = [market(series="KXA15M", q8=(0.93, 0.94)),              # 1c (0.00999... in floats), 94c
              market(series="KXB15M", q8=(0.95, 0.96)),              # 1c (0.01000...09 in floats), 96c
              market(series="KXC15M", q8=(0.03, 0.035), yes=False),  # a NO favourite: own (96.5, 97), 0.5c, 97c
              market(series="KXD15M", q8=(0.975, 0.99)),             # 1.5c, 99c
              market(series="KXE15M", q8=(0.945, 0.95)),             # 0.5c, 95c
              market(series="KXGOLD15M", group="metals", q8=(0.91, 0.92))]   # never capped
    strat = flat(skip=["spread", "late"], maxPer={"crypto": 3})
    r = run(study, strat, {T0: window})
    assert r["bets"] == 4 and keys(r) == ["B", "C", "E", "GOLD"]
    assert run(study, flat(skip=["spread", "late"]), {T0: window})["bets"] == 6


def test_max_per_breaks_a_full_tie_by_the_order_listed(study):
    window = [market(series=f"KXC{i}15M") for i in range(1, 6)]
    assert keys(run(study, flat(maxPer={"crypto": 3}), {T0: window})) == ["C1", "C2", "C3"]


def test_max_per_sizes_the_window_off_the_bets_it_places(study):
    """10 candidates would share 10% (1% each); capped to 3 crypto + 1 metals the window places 4, so each gets the
    full 1.5% a bet."""
    sb = study.strategies_backtest
    strat = {"id": "c", "minute": 8, "sizing": "capped", "groups": EDGE, "maxPer": {"crypto": 3}}
    window = [market(series=f"KXC{i}15M") for i in range(1, 10)] + [market(series="KXGOLD15M", group="metals")]
    r = run(study, strat, {T0: window})
    stake = sb.stake_for(strat, 240.0, 4)
    assert stake == 3.6 and sb.stake_for(strat, 240.0, 10) == 2.4
    c = stake / 0.96
    assert r["bets"] == 4 and r["final"] == round(240 + 4 * (c - stake - fee(c, 0.96)), 2)


@pytest.mark.parametrize("sizing", ["flat", "capped"])
def test_max_per_changes_nothing_when_a_window_is_under_the_cap(study, sizing):
    window = [market(series=f"KXC{i}15M", q8=(0.93 + i / 100, 0.94 + i / 100)) for i in range(3)]
    window.append(market(series="KXGOLD15M", group="metals"))
    base = {"id": "c", "minute": 8, "sizing": sizing, "groups": EDGE}
    windows = {T0: window, T0 + 900: window[:2]}
    assert run(study, {**base, "maxPer": {"crypto": 3}}, windows) == run(study, base, windows)


def test_one_per_still_sizes_off_every_candidate(study):
    """onePer is left as it was: its window is sized off all the candidates, not the bets it places."""
    sb = study.strategies_backtest
    strat = {"id": "g", "minute": 8, "sizing": "capped", "groups": EDGE, "onePer": ["crypto"]}
    window = [market(series=f"KXC{i}15M") for i in range(1, 11)]
    stake = sb.stake_for(strat, 240.0, 10)
    c = stake / 0.96
    assert run(study, strat, {T0: window})["final"] == round(240 + c - stake - fee(c, 0.96), 2)


def test_the_candidates_are_the_live_bot_with_one_change(study):
    sb = study.strategies_backtest
    ids = [s["id"] for s in sb.LIVE]
    want = list(CANDIDATES) + (["live3xliq"] if sb.LIQUIDITY else [])
    assert ids[-len(want):] == want, "appended to LIVE after liveliq"
    assert ("liveliq" in ids) == bool(sb.LIQUIDITY) and ("live3xliq" in ids) == bool(sb.LIQUIDITY)
    accounts = {s["id"]: s for s in sb.STRATS}
    live = sb.LIVE[0]
    for sid, (name, extra) in CANDIDATES.items():
        s = accounts[sid]
        assert s == {**live, "id": sid, "name": name, "role": "candidate", "variant": True, **extra}, sid
        assert (s["start"], s["sizing"], s["whole"], s["skip"], s["blackouts"]) == \
            (225.0, "capped", True, ["spread", "late"], sb.FED_WINDOWS)


def test_main_writes_the_candidates_fields(study, strategies):
    out = {s["id"]: s for s in strategies["strategies"]}
    assert all(set(NEW_KEYS) <= set(s) for s in strategies["strategies"]), "every entry carries the three keys"
    assert all(out["live"][k] is None for k in NEW_KEYS)
    for sid, (_, extra) in CANDIDATES.items():
        assert {k: out[sid][k] for k in NEW_KEYS} == {k: extra.get(k) for k in NEW_KEYS}, sid
        assert out[sid]["role"] == "candidate" and out[sid]["variant"] is True


@pytest.mark.parametrize("sid", ["live", "live3x"])
def test_the_live_bot_and_all_three_match_the_strategy_labs_replay(study, strategies, sid):
    """The lab's edge_map.replay (numpy, written apart from run()) on the same history: the live rule (for "live3x" minus
    HYPE and the weekday 9:30 ET windows, at most 3 crypto bets a window by spread), then the bot's sizing from $225."""
    import sys
    from pathlib import Path

    import numpy as np
    lab = str(Path(__file__).resolve().parent.parent / "lab")
    if lab not in sys.path:
        sys.path.insert(0, lab)
    import common as C
    import edge_map as em
    sb = study.strategies_backtest
    windows, _, _ = sb.load()
    ms = [(t, m) for t in sorted(windows) for m in windows[t]]
    num = lambda x: np.nan if x is None else x  # noqa: E731
    d = {"ticker": np.array([m["ticker"] for _, m in ms]), "series": np.array([m["series"] for _, m in ms]),
         "group": np.array([m["group"] for _, m in ms]), "open_ts": np.array([t for t, _ in ms], dtype=np.int64),
         "yes": np.array([m["yes"] for _, m in ms], dtype=np.int8),
         "bid": np.array([[num(m["q"][k][0]) for k in range(1, 16)] for _, m in ms], dtype=np.float64),
         "ask": np.array([[num(m["q"][k][1]) for k in range(1, 16)] for _, m in ms], dtype=np.float64)}
    keep = np.isin(d["group"], C.EDGE_GROUPS)
    d = {k: v[keep] for k, v in d.items()}
    mask, side_yes, top = C.live_rule(d)
    if sid == "live3x":
        mask &= (d["series"] != "KXHYPE15M") & ~em.slot_mask(d, 9, 30)
        mask = em.cap_mask(d, mask, top, em.spread(d, side_yes, 8), 3, "spread")
    lab_run = em.replay(d, mask, top, C.won(d, side_yes), start=225.0)
    r = strategies["starts"]["dec10"]["live"][sid]
    assert lab_run["bets"] == r["bets"] > 0 and lab_run["final"] == pytest.approx(r["final"], abs=0.005)
    assert lab_run["maxDD"] == pytest.approx(r["maxDD"], abs=1e-9)
