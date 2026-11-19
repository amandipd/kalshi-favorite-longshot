"""strategies_backtest.py's MINE accounts: the live bot as it has really traded, one version per change, for the
Historical Research tab (since removed), which showed only these when strategies.json had any.

The tab shows only the live bot's own rule, one version per change it went through (90c, then 92c, and so on), each
from the same simulated $2,000.

The versions, from the bot's history (each the live bot's rule, 3% a bet, 20% a window, whole contracts, the Fed
blackouts, minute 8, crypto/metals/energy), each from a simulated $2,000:
  1  Sep 28 - Oct 9    90c floor, at most $10 an order, no warning signs
  2  Oct 9 - 10        skips both warning signs (2c+ spreads, late or jumpy favourites)
  3  Oct 10 - 14       no order cap
  4  since Oct 14      92c floor: the bot running now
and, beside a liquidity.json, version 4 again filled only as far as Kalshi's trade tape says the book had.
"""

from __future__ import annotations

import math

import pytest

EDGE = ["crypto", "metals", "energy"]
T0 = 1_784_332_800  # 2026-07-18T00:00:00Z
IDS = ["mine1", "mine2", "mine3", "mine4"]
NAMES = {"mine1": "Version 1 · 90¢, $10 orders", "mine2": "Version 2 · skips warning signs",
         "mine3": "Version 3 · no order cap", "mine4": "Version 4 · 92¢ floor", "mine4liq": "Version 4 · real liquidity"}
TRADED = {"mine1": "Sep 28 – Oct 9", "mine2": "Oct 9 – 10", "mine3": "Oct 10 – 14", "mine4": "since Oct 14",
          "mine4liq": "since Oct 14"}
# What each version changes against the live bot's own account (strategies_backtest.LIVE[0])
RULE = {"mine1": {"lo": 0.90, "maxOrder": 10.0, "skip": None}, "mine2": {"lo": 0.90, "maxOrder": 10.0},
        "mine3": {"lo": 0.90}, "mine4": {"lo": 0.92}}
# what a version may hold that the $225 live replay does not; "floor" is the real-money $700 stop, which only the
# accounts that start from $2,000 carry (test_the_real_money_accounts_carry_the_bots_700_dollar_stop)
OWN = ("id", "name", "start", "role", "lo", "maxOrder", "skip", "mine", "version", "traded", "now", "liquidity",
       "floor")


def test_version_four_also_runs_from_ten_thousand(study):
    """Added Oct 28, 2026.

    It is a real second run, not the $2,000 one times five. Under real fills a 1.5% bet at $10,000 is about 160
    contracts, far more than Kalshi's trade tape says the book held, so most of the extra size never fills. The
    existing capital rows already said so -- $2,000 made +$1,246 and $10,000 only +$1,887 -- but those rows carry
    no bankroll curve, and the tab draws one.

    Everything except the starting amount is the same account, the $700 stop included. At $10,000 that stop is a
    93% fall, so it never fires; it is kept because it is the bot's own rule, not scaled to flatter the run.
    """
    sb = study.strategies_backtest
    built = {s["id"]: s for s in sb.mine_accounts({"X": [None, None, 1.0]})}   # a stand-in trade tape
    assert "mine4liq10k" in built, "the $10,000 account isn't built"
    big, base = built["mine4liq10k"], built["mine4liq"]
    assert big["start"] == 10000.0 and base["start"] == 2000.0
    from kalshi_bot import bot
    assert big["floor"] == base["floor"] == bot.HALT_FLOOR   # $700, the bot's own, not scaled to the bigger account
    ignore = ("id", "name", "start")
    assert {k: v for k, v in big.items() if k not in ignore} == {k: v for k, v in base.items() if k not in ignore}


def test_version_four_also_runs_from_a_small_account(study):
    """A simulated $850 account beside the $2,000 one. The $700 stop bites here and nowhere else: a 25% fall from
    $850 is under $700, while the same fall from $2,000 is not.
    """
    sb = study.strategies_backtest
    built = {s["id"]: s for s in sb.mine_accounts({"X": [None, None, 1.0]})}
    assert "mine4liq850" in built, "the $850 account isn't built"
    real, base = built["mine4liq850"], built["mine4liq"]
    assert real["start"] == 850.0 == sb.MINE_START_SMALL
    assert real["floor"] == base["floor"], "it carries the bot's own $700 stop, which matters most here"
    ignore = ("id", "name", "start")
    assert {k: v for k, v in real.items() if k not in ignore} == {k: v for k, v in base.items() if k not in ignore}


def test_version_four_also_runs_from_one_thousand(study):
    """A dashboard view of a simulated $1,000 account since the markets opened.

    Like the $10,000 run it is a what-if, worth drawing because $1,000 is a round amount a reader can picture
    putting in. Everything except the starting amount is the mine4liq account, the
    $700 stop included: from $1,000 that stop is a 30% fall, further off than the $850 line's 18% but still
    close enough to fire in a bad stretch.
    """
    sb = study.strategies_backtest
    built = {s["id"]: s for s in sb.mine_accounts({"X": [None, None, 1.0]})}
    assert "mine4liq1k" in built, "the $1,000 account isn't built"
    small, base = built["mine4liq1k"], built["mine4liq"]
    assert small["start"] == 1000.0 == sb.MINE_START_1K
    assert small["floor"] == base["floor"], "the bot's own $700 stop, not scaled down with the account"
    ignore = ("id", "name", "start")
    assert {k: v for k, v in small.items() if k not in ignore} == {k: v for k, v in base.items() if k not in ignore}


def test_the_four_amounts_run_smallest_first(study):
    """$850, $1,000, $2,000, $10,000: the tab draws them in this order and overlays all four on one chart."""
    sb = study.strategies_backtest
    built = sb.mine_accounts({"X": [None, None, 1.0]})
    got = [s["start"] for s in built if s["id"].startswith("mine4liq")]
    assert sorted(got) == [850.0, 1000.0, 2000.0, 10000.0]


def market(yes=True, q8=(0.94, 0.96), series="KXBTC15M", group="crypto"):
    """A market quoted (bid, ask) = q8 at every minute of the window."""
    return {"ticker": f"{series}-{q8}-{yes}", "series": series, "group": group, "yes": yes,
            "q": {k: q8 for k in range(1, 16)}}


def fee(c, p):
    return math.ceil(0.07 * c * p * (1 - p) * 100 - 1e-9) / 100


def accounts(sb):
    return {s["id"]: s for s in sb.STRATS}


def run(sb, sid, window):
    return sb.run(accounts(sb)[sid], {T0: window}, 0.0, T0, 2)


# ------------------------------------------------------------------ the accounts


def test_the_versions_come_last_in_order_after_every_other_account(study):
    sb = study.strategies_backtest
    want = IDS + (["mine4liq"] if sb.LIQUIDITY else [])
    assert [s["id"] for s in sb.MINE] == want
    assert [s["id"] for s in sb.STRATS][-len(want):] == want
    assert sb.STRATS[:-len(want)] == sb.STRATEGIES + sb.EXITS + sb.VARIANTS + sb.LIVE, "nothing else moves or goes"


def test_every_version_is_the_live_bot_from_2000_dollars(study):
    sb = study.strategies_backtest
    live = sb.LIVE[0]
    for s in sb.MINE:
        assert (s["start"], s["role"], s["mine"]) == (2000.0, "mine", True), s["id"]
        assert (s["minute"], s["sizing"], s["groups"], s["whole"], s["blackouts"]) == \
            (8, "capped", EDGE, True, sb.FED_WINDOWS), s["id"]
        assert {k: v for k, v in s.items() if k not in OWN} == {k: v for k, v in live.items() if k not in OWN}, s["id"]
        assert s.get("hi", sb.HI) == 0.999, s["id"]
        # they are the bot, so they carry no sizing of their own: they take CAP_PCT and WINDOW_CAP, which
        # test_version_4_is_the_bot_running_now holds to bot.stake_for
        assert "pct" not in s and "windowCap" not in s, s["id"]
    assert sb.MINE_START == 2000.0


@pytest.mark.parametrize("sid", IDS)
def test_each_version_changes_what_the_bot_changed(study, sid):
    s = accounts(study.strategies_backtest)[sid]
    rule = RULE[sid]
    assert s["lo"] == rule["lo"]
    assert s.get("maxOrder") == rule.get("maxOrder")
    assert s.get("skip") == rule.get("skip", ["spread", "late"])
    assert (s["name"], s["version"], s["traded"]) == (NAMES[sid], IDS.index(sid) + 1, TRADED[sid])
    assert bool(s.get("now")) == (sid == "mine4"), "only version 4 runs now"
    assert not s.get("liquidity") and not s.get("liveFit") and not s.get("variant")


def test_version_4_is_the_bot_running_now(study):
    """Its floor, top price, warning signs and sizing are bot.py's own: if the live bot changes, this says so."""
    from kalshi_bot import bot
    sb = study.strategies_backtest
    s = accounts(sb)["mine4"]
    assert (s["lo"], s.get("hi", sb.HI), s["minute"]) == (bot.LO, bot.HI, bot.MINUTE)
    assert sorted(s["skip"]) == ["late", "spread"] and "maxOrder" not in s
    for bankroll, n in ((2000.0, 1), (2000.0, 9), (333.0, 1), (5000.0, 3), (100.0, 10)):
        assert sb.stake_for(s, bankroll, n) == pytest.approx(bot.stake_for(bankroll, n))


def test_the_real_liquidity_twin_is_version_4_reading_the_tape(study):
    """mine_accounts(LIQUIDITY) builds MINE at import: the twin only beside a liquidity.json, version 4 otherwise."""
    sb = study.strategies_backtest
    twin = {**accounts(sb)["mine4"], "id": "mine4liq", "name": NAMES["mine4liq"], "liquidity": True}
    built = sb.mine_accounts({"X": [None, None, 1.0]})
    # then the $10,000, $850 and $1,000 amounts
    assert [s["id"] for s in built] == IDS + ["mine4liq", "mine4liq10k", "mine4liq850", "mine4liq1k"]
    assert built[-4] == twin
    assert [s["id"] for s in sb.mine_accounts(None)] == IDS and [s["id"] for s in sb.mine_accounts({})] == IDS
    assert sb.MINE == sb.mine_accounts(sb.LIQUIDITY)


# ------------------------------------------------------------------ what each version bets


def test_the_92c_floor_leaves_out_a_91c_favourite_the_90c_versions_buy(study):
    sb = study.strategies_backtest
    window = [market(q8=(0.905, 0.91)), market(q8=(0.935, 0.94), series="KXETH15M")]
    assert run(sb, "mine3", window)["bets"] == 2
    assert run(sb, "mine4", window)["bets"] == 1


def test_version_1_buys_a_2c_spread_the_later_versions_skip(study):
    sb = study.strategies_backtest
    window = [market(q8=(0.93, 0.95))]   # its ask exactly 2c over its bid: the spread warning sign
    assert run(sb, "mine1", window)["bets"] == 1
    for sid in ("mine2", "mine3", "mine4"):
        assert run(sb, sid, window)["bets"] == 0, sid


def test_versions_1_and_2_bet_10_dollars_and_3_and_4_bet_1_and_a_half_percent_of_2000(study):
    sb = study.strategies_backtest
    window = [market(yes=True, q8=(0.955, 0.96))]
    for sid, stake in (("mine1", 10.0), ("mine2", 10.0), ("mine3", 30.0), ("mine4", 30.0)):
        c = math.floor(stake / 0.96 + 1e-9)
        r = run(sb, sid, window)
        assert r["start"] == 2000.0 and r["bets"] == 1, sid
        assert r["final"] == round(2000.0 + c - c * 0.96 - fee(c, 0.96), 2), sid


# ------------------------------------------------------------------ strategies.json, for the tab


@pytest.fixture(scope="module")
def strategies(study):
    import json
    study.strategies_backtest.main()
    with open("strategies.json", encoding="utf-8") as fh:
        return json.load(fh)


def test_main_marks_the_versions_for_the_tab(study, strategies):
    out = {s["id"]: s for s in strategies["strategies"]}
    want = [s["id"] for s in study.strategies_backtest.MINE]
    assert [sid for sid, s in out.items() if s["mine"]] == want
    for sid in want:
        s = out[sid]
        assert (s["start"], s["role"], s["version"], s["traded"], s["now"]) == \
            (2000.0, "mine", 4 if sid == "mine4liq" else IDS.index(sid) + 1, TRADED[sid], sid.startswith("mine4"))
        assert s["lo"] == (0.92 if sid.startswith("mine4") else 0.90) and s["name"] == NAMES[sid]
        assert s["maxOrder"] == (10.0 if sid in ("mine1", "mine2") else None)
        assert s["skip"] == (None if sid == "mine1" else ["spread", "late"])
    for sid, s in out.items():
        if sid not in want:
            assert (s["mine"], s["version"], s["traded"], s["now"]) == (False, None, None, False), sid


def test_every_version_is_replayed_under_both_fills_from_every_start(study, strategies):
    want = [s["id"] for s in study.strategies_backtest.MINE]
    for start in strategies["starts"].values():
        for runs in start.values():
            for sid in want:
                assert runs[sid]["start"] == 2000.0 and len(runs[sid]["curve"]) == strategies["hours"], sid
    for sid in want:
        assert sid in strategies["edge"]["live"] and sid in strategies["edge"]["backtest"]


# ------------------------------------------------------------------ starting capital, for the tab's slider
# A slider for the starting amount, from $0 up to $100,000. Each
# version is replayed again from each amount, with the same fills, start date and windows as its own $2,000 run.

CAPITALS = [0, 100, 250, 500, 1000, 2000, 3000, 5000, 7500, 10000, 15000, 20000, 25000, 35000, 50000, 75000, 100000]
FILLS, STARTS = ("live", "backtest"), ("dec10", "jul18", "aug24")
ROW = {"start", "final", "profit", "ret", "maxDD", "bets", "broke"}
ZERO = {"start": 0, "final": 0.0, "profit": 0.0, "ret": None, "maxDD": 0.0, "bets": 0, "broke": None}


def capital(strategies):
    return {s["id"]: s["capital"] for s in strategies["strategies"] if s["mine"]}


def at(rows, c):
    return rows[CAPITALS.index(c)]


def test_the_capitals_run_from_0_to_100000(study):
    assert study.strategies_backtest.CAPITALS == CAPITALS


def test_every_version_has_a_row_per_capital_for_each_fills_and_start(study, strategies):
    caps = capital(strategies)
    assert list(caps) == [s["id"] for s in study.strategies_backtest.MINE]
    for sid, cap in caps.items():
        assert set(cap) == set(FILLS), sid
        for fills in FILLS:
            assert set(cap[fills]) == set(STARTS), (sid, fills)
            for start, rows in cap[fills].items():
                assert [r["start"] for r in rows] == CAPITALS, (sid, fills, start)
                assert all(set(r) == ROW for r in rows), (sid, fills, start)


def test_the_2000_dollar_row_is_the_versions_own_run(strategies):
    """The same replay as the version's own entry under "starts": same fills, same start date, same $2,000."""
    for sid, cap in capital(strategies).items():
        for fills in FILLS:
            for start in STARTS:
                own, row = strategies["starts"][start][fills][sid], at(cap[fills][start], 2000)
                assert {k: row[k] for k in ("final", "maxDD", "bets", "broke")} == \
                    {k: own[k] for k in ("final", "maxDD", "bets", "broke")}, (sid, fills, start)


def test_every_other_row_is_the_version_replayed_from_that_amount(study, strategies):
    """run({**s, "start": c}) with main()'s own windows, fills, hours and start dates, whatever main() does to make
    these runs cheaper."""
    sb = study.strategies_backtest
    windows, first, last = sb.load()
    hours = int((last + 900 - first) // sb.HOUR) + 1
    begins = {"dec10": None, "jul18": sb.ts(sb.PERIODS[1][2]), "aug24": sb.ts(sb.PERIODS[2][2])}
    caps = capital(strategies)
    for s in sb.MINE:
        for fills, slip in sb.SCENARIOS.items():
            for start, at_ts in begins.items():
                for c in (100, 100000):
                    r = sb.run({**s, "start": c}, windows, slip, first, hours, at_ts)
                    row = at(caps[s["id"]][fills][start], c)
                    assert {k: row[k] for k in ("final", "maxDD", "bets", "broke")} == \
                        {k: r[k] for k in ("final", "maxDD", "bets", "broke")}, (s["id"], fills, start, c)


def test_nothing_ventured_nothing_gained_at_0(strategies):
    """$0 can't place a $1 bet, so it isn't replayed (a return on $0 would divide by zero)."""
    for sid, cap in capital(strategies).items():
        for fills in FILLS:
            for start in STARTS:
                assert at(cap[fills][start], 0) == ZERO, (sid, fills, start)


def test_profit_and_return_follow_from_the_start_and_the_end(strategies):
    for sid, cap in capital(strategies).items():
        for fills in FILLS:
            for start in STARTS:
                for r in cap[fills][start][1:]:
                    assert r["profit"] == round(r["final"] - r["start"], 2), (sid, fills, start, r["start"])
                    assert r["ret"] == r["final"] / r["start"] - 1, (sid, fills, start, r["start"])
                    if r["broke"]:
                        assert (r["final"], r["maxDD"]) == (0.0, 1.0), (sid, fills, start, r["start"])


def test_the_other_accounts_carry_no_capital(strategies):
    for s in strategies["strategies"]:
        if not s["mine"]:
            assert "capital" in s and s["capital"] is None, s["id"]


def test_a_10_dollar_cap_stops_the_profit_growing_with_the_capital(strategies):
    """At $2,000, 3% is $60, so the $10 cap already binds: from $100,000, versions 1 and 2 place the same $10 bets and
    win or lose about what they did from $2,000, not 50 times it. Version 3, with no cap, bets 3% from any amount: its
    return hardly moves with the capital (whole contracts round a little differently), so its profit is close to 50
    times. (Ratios, so the sign of the synthetic history's profit doesn't matter.)"""
    caps = capital(strategies)
    for fills in FILLS:
        for sid in ("mine1", "mine2"):
            small, big = at(caps[sid][fills]["dec10"], 2000), at(caps[sid][fills]["dec10"], 100000)
            assert small["profit"] != 0 and abs(big["profit"]) < 2 * abs(small["profit"]), (sid, fills)
        small, big = at(caps["mine3"][fills]["dec10"], 2000), at(caps["mine3"][fills]["dec10"], 100000)
        assert not small["broke"] and not big["broke"], fills
        assert 40 < big["profit"] / small["profit"] < 60, fills


# ------------------------------------------------------------------ the $700 stop, reported not enforced


def many(sb, strat, yes, n):
    """`strat` run over n windows, each holding one market settling `yes`, from its own start."""
    windows = {}
    for i in range(n):
        m = dict(market(yes=yes, q8=(0.955, 0.96)))
        m["ticker"] = f"M{i}"
        windows[T0 + 900 * i] = [m]
    return sb.run(strat, windows, 0.0, T0, 24 * n)


def test_the_real_money_accounts_carry_the_bots_700_dollar_stop(study):
    """bot.HALT_FLOOR: the live bot halts at or under $700, real money only. The replays trade every window, as they
    do for its other halts, so the accounts carry the level and run() reports when it would first have fired."""
    from kalshi_bot import bot
    sb = study.strategies_backtest
    for s in sb.MINE:
        assert s["floor"] == bot.HALT_FLOOR == 700.0, s["id"]
    for s in sb.LIVE:                       # the $225 and $500 replays start below it, so it would say nothing
        assert "floor" not in s, s["id"]


def test_the_stop_is_reported_and_changes_no_bet(study):
    """A floor only watches: the same account with and without it places the same bets for the same money."""
    sb = study.strategies_backtest
    base = {"id": "f", "minute": 8, "sizing": "capped", "groups": EDGE, "start": 1000.0, "whole": True}
    plain = many(sb, dict(base), yes=False, n=40)           # losers, so the bankroll falls
    stopped = many(sb, {**base, "floor": 900.0}, yes=False, n=40)
    assert plain["bets"] > 0 and plain["final"] < 900.0
    assert (stopped["bets"], stopped["final"]) == (plain["bets"], plain["final"])
    assert plain["floorHit"] is None, "no floor, nothing to report"
    assert stopped["floorHit"] is not None, "it fell under $900 and the account says when"


def test_a_floor_never_reached_reports_nothing(study):
    sb = study.strategies_backtest
    r = many(sb, {"id": "f", "minute": 8, "sizing": "capped", "groups": EDGE, "start": 1000.0, "whole": True,
                  "floor": 700.0}, yes=True, n=10)
    assert r["bets"] == 10 and r["final"] > 1000.0 and r["floorHit"] is None
