"""strategies_backtest.py's "live fills" accounts: orders filled the way the live bot's own real orders filled.

live_fills.py measures the bot's ledger and writes live_fills.json: a fill table per market (a Kaplan-Meier survival
curve: survival[k] is the chance the book held more than k contracts at the bot's price) and the gap in cents between
its real fill prices and the minute-8 candle ask. strategies_backtest reads the file at import, as it reads
liquidity.json, and only then adds "The live bot · live fills" and "The live bot · all three · live fills". Their
orders ask floor(stake / price) whole contracts and get the expected fill from the table, at the candle ask plus the
gap, with Kalshi's exact fee; the scenario's slip never reaches them.

`expected_fill()` and `pick()` are checked on the spec's worked examples, `run()` on hand-built windows whose fills can
be worked out by hand and on the synthetic history against a replay written here from the spec's formulas, then
`main()` twice in copies of the history: without a live_fills.json (nothing changes but a `liveFit: false` on each
entry) and with one (the two accounts, their fills and the fill stats copied into strategies.json). The second
reloads strategies_backtest inside its copy and reloads it again in the session's folder afterwards, so the other test
files never see a live_fills.json.
"""

from __future__ import annotations

import contextlib
import copy
import importlib
import io
import json
import math
import os
import shutil
from types import SimpleNamespace

import pytest

EDGE = ["crypto", "metals", "energy"]
T0 = 1_784_332_800  # 2026-07-18T00:00:00Z
FIT_IDS = ["livefit", "live3xfit"]
NAMES = {"livefit": "The live bot · live fills", "live3xfit": "The live bot · all three · live fills"}

# Fill tables, each the spec's worked example or one like it.
HALF = [1.0, 1.0, 1.0, 1.0, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5]   # orders (want 10, got 4) and (want 10, got 10)
FULL5 = [1.0] * 5                                           # (want 5, got 5) x3: never seen past 5
NONE = [0.0]                                                # (want 4, got 0) x2: the book never had any
THIRD = [1.0, 1.0, 1.0] + [0.333333] * 9                    # rounded to 6 places, as live_fills.json holds them


def entry(orders, max_want, survival):
    return {"orders": orders, "maxWant": max_want, "survival": survival}


# A small live_fills.json, shaped as live_fills.py writes it. Which table each synthetic market's orders use:
#   KXBTC15M   its own (20 orders)                                   HALF
#   KXETH15M   too few of its own (3 < 15): the crypto group's (23)  THIRD
#   KXGOLD15M  none of its own, metals has too few (2): every order  FULL5
#   KXWTI15M   none of its own, energy has exactly 15: energy's      NONE, so every WTI order is missed
FILLS = {
    "ledger": "live-test.db",
    "summary": {"orders": 40, "none": 11, "partial": 9, "full": 20, "asked": 400.0, "got": 220.0, "fillRate": 0.55,
                "from": "2026-09-28T03:23:05Z", "to": "2026-10-12T01:38:44Z", "dataEnd": "2026-10-02T00:00:00Z",
                "gap": {"fillVsLimit": -0.17, "limitVsAsk": 0.1, "fillVsAsk": -0.25, "n": 12},
                "won": {"filled": [27, 29], "missed": [10, 11]},
                "fee": {"paid": 1.23, "exact": 1.2, "rounded": 1.31}},
    "byBand": [], "bySize": [], "bySeries": [], "byGroup": [],
    "tape": {"orders": 0, "predicted": 0, "real": 0, "table": {}},
    "depth": {"all": entry(40, 5, FULL5),
              "groups": {"crypto": entry(23, 12, THIRD), "metals": entry(2, 5, FULL5), "energy": entry(15, 4, NONE)},
              "series": {"KXBTC15M": entry(20, 10, HALF), "KXETH15M": entry(3, 10, HALF)}},
    "replay": {}, "candidates": {}, "orders": [],
}
# strategies.json's "liveFills" on each live-fit entry, copied from the summary. filledWon / missedWon are the summary's
# won.filled / won.missed pairs as they stand, [wins, orders whose outcome is known], so the page can show both counts.
LIVE_FILLS_ENTRY = {"orders": 40, "from": "2026-09-28T03:23:05Z", "to": "2026-10-12T01:38:44Z", "fillRate": 0.55,
                    "fillVsAsk": -0.25, "filledWon": [27, 29], "missedWon": [10, 11]}


def fills(gap=-0.25):
    """FILLS with another fill-vs-ask gap in cents (None: no order had both a fill and a candle ask)."""
    f = copy.deepcopy(FILLS)
    f["summary"]["gap"]["fillVsAsk"] = gap
    return f


def spec_fill(survival, c):
    """The spec's expected fill, written apart from strategies_backtest's: whole contracts' survival summed, part of the
    next for a fractional order, and never more than the pool's live orders have shown."""
    i = int(c)
    return sum(survival[:i]) + (c - i) * survival[i] if i < len(survival) else sum(survival)


def spec_pick(model, series, group):
    s, g = model["series"].get(series), model["groups"].get(group)
    if s and s["orders"] >= 15:
        return s
    if g and g["orders"] >= 15:
        return g
    return model["all"]


def market(ticker, series="KXBTC15M", group="crypto", yes=True, q8=(0.95, 0.96)):
    """A market quoted (YES bid, YES ask) = q8 at the end of every minute."""
    return {"ticker": ticker, "series": series, "group": group, "yes": yes, "q": {k: q8 for k in range(1, 16)}}


def fitted_account(**extra):
    """$10 a bet in whole contracts, filled the way live orders fill."""
    return {"id": "f", "name": "test", "minute": 8, "sizing": "flat", "groups": EDGE, "whole": True, "liveFit": True,
            **extra}


def run(sb, strat, windows, slip=0.0, hours=1):
    return sb.run(strat, windows, slip, T0, hours)


def exact_fee(c, p):
    return 0.07 * c * p * (1 - p)


def rounded_fee(c, p):
    return math.ceil(0.07 * c * p * (1 - p) * 100 - 1e-9) / 100


def settle(bets, fee=exact_fee):
    """(pnl, staked, need) of bets given as (price, contracts got, won)."""
    pnl = sum((c if won else 0.0) - c * p - fee(c, p) for p, c, won in bets)
    staked = sum(c * p for p, c, _ in bets)
    need = sum((c * p + fee(c, p)) / c for p, c, _ in bets) / len(bets)
    return pnl, staked, need


# ------------------------------------------------------------------ expected_fill() and pick()


@pytest.mark.parametrize("survival, c, got", [
    (HALF, 10, 7.0),       # 4 contracts for certain, then a 50% chance at each of the next 6
    (HALF, 4.5, 4.25),     # a fractional order: half of the 5th contract's 50%
    (HALF, 4, 4.0),
    (HALF, 12, 7.0),       # past the table: no more than the pool's live orders have shown
    (HALF, 10.5, 7.0),
    (FULL5, 3, 3.0),
    (FULL5, 5, 5.0),
    (FULL5, 10, 5.0),      # every order filled in full, but none asked for more than 5
    (NONE, 4, 0.0),        # the book never had any
    (NONE, 1, 0.0),
    (NONE, 0.5, 0.0),
    (THIRD, 10, 5.333331),
    (HALF, 0, 0.0),        # an order for nothing gets nothing
    (FULL5, 0, 0.0),
    (NONE, 0, 0.0),
])
def test_expected_fill_on_the_worked_examples(study, survival, c, got):
    sb = study.strategies_backtest
    assert sb.expected_fill(entry(2, len(survival), survival), c) == pytest.approx(got, abs=1e-12)
    assert spec_fill(survival, c) == pytest.approx(got, abs=1e-12), "the replay below uses the same formula"


SERIES_T, GROUP_T, ALL_T = entry(15, 10, HALF), entry(15, 5, FULL5), entry(40, 12, THIRD)


@pytest.mark.parametrize("series_orders, group_orders, want", [
    (15, 15, "series"),    # 15 live orders are enough for a market's own table
    (14, 15, "group"),     # 14 aren't: its group's
    (14, 14, "all"),       # nor for the group: the table from every order
    (15, 0, "series"),
    (0, 15, "group"),
    (None, 15, "group"),   # a market with no live orders at all
    (None, None, "all"),   # ... in a group with none either
    (14, None, "all"),
])
def test_pick_falls_back_from_the_market_to_its_group_to_every_order(study, series_orders, group_orders, want):
    sb = study.strategies_backtest
    model = {"all": ALL_T, "groups": {}, "series": {}}
    if series_orders is not None:
        model["series"]["KXBTC15M"] = {**SERIES_T, "orders": series_orders}
    if group_orders is not None:
        model["groups"]["crypto"] = {**GROUP_T, "orders": group_orders}
    picked = sb.pick(model, "KXBTC15M", "crypto")
    tables = {"series": model["series"].get("KXBTC15M"), "group": model["groups"].get("crypto"), "all": ALL_T}
    assert picked == tables[want]
    assert spec_pick(model, "KXBTC15M", "crypto") == tables[want]


def test_pick_never_borrows_another_markets_table(study):
    sb = study.strategies_backtest
    model = {"all": ALL_T, "groups": {"crypto": entry(30, 5, FULL5)}, "series": {"KXETH15M": entry(30, 10, HALF)}}
    assert sb.pick(model, "KXBTC15M", "crypto") == model["groups"]["crypto"]
    assert sb.pick(model, "KXGOLD15M", "metals") == ALL_T


# ------------------------------------------------------------------ run(), by hand


def test_each_order_gets_its_expected_fill_at_the_ask_plus_the_gap(study, monkeypatch):
    """Four orders of 10 whole contracts ($10 a bet, at the candle ask less the -0.25c gap), each filled from its own
    table: BTC 7 of 10 (its own), ETH 5.333331 (the crypto group's), GOLD 5 (every order's), WTI nothing (energy's)."""
    sb = study.strategies_backtest
    monkeypatch.setattr(sb, "LIVE_FILLS", fills())
    window = [market("BTC", yes=True, q8=(0.95, 0.96)),                                  # YES at 96c, wins
              market("ETH", series="KXETH15M", yes=False, q8=(0.92, 0.93)),              # YES at 93c, loses
              market("GOLD", series="KXGOLD15M", group="metals", yes=False, q8=(0.045, 0.055)),  # NO at 95.5c, wins
              market("WTI", series="KXWTI15M", group="energy", yes=True, q8=(0.95, 0.96))]       # missed; would have won
    r = run(sb, fitted_account(), {T0: window})
    gap = -0.25 / 100
    price = {k: min(top + gap, 0.999) for k, top in (("BTC", 0.96), ("ETH", 0.93), ("GOLD", 0.955))}
    assert all(math.floor(10 / p) == 10 for p in price.values()), "each asks for 10 whole contracts"
    bets = [(price["BTC"], 7.0, True), (price["ETH"], 5.333331, False), (price["GOLD"], 5.0, True)]
    pnl, staked, need = settle(bets)
    assert r["liveFit"] == {"orders": 4, "asked": 40.0, "got": 17.33, "missed": 1}
    assert (r["bets"], r["wins"]) == (3, 2), "the order expected to get nothing is not a bet"
    assert r["final"] == round(240 + pnl, 2) == 235.53
    assert r["perBet"] == pytest.approx(pnl / staked * 1000, rel=1e-9)
    assert r["need"] == pytest.approx(need, rel=1e-12)
    # each class also carries the window it first traded in, which the Backtest tab marks on its chart (Oct 28)
    assert r["byGroup"] == [
        {"key": "crypto", "n": 2, "wins": 1, "pnl": round(settle(bets[:2])[0], 2),
         "staked": round(settle(bets[:2])[1], 2), "first": "2026-07-18T00:00:00+00:00"},
        {"key": "metals", "n": 1, "wins": 1, "pnl": round(settle(bets[2:])[0], 2),
         "staked": round(settle(bets[2:])[1], 2), "first": "2026-07-18T00:00:00+00:00"}]
    assert sorted(g["key"] for g in r["bySeries"]) == ["BTC", "ETH", "GOLD"]
    assert r["liquidity"] is None, "a live-fit account doesn't read the trade tape"


def test_the_fee_is_exact_not_rounded_up_to_the_cent(study, monkeypatch):
    """Live fees are charged to the fraction of a cent; the other accounts round each order's fee up."""
    sb = study.strategies_backtest
    monkeypatch.setattr(sb, "LIVE_FILLS", fills())
    window = [market("BTC", yes=True), market("ETH", series="KXETH15M", yes=False, q8=(0.92, 0.93))]
    r = run(sb, fitted_account(), {T0: window})
    bets = [(0.96 - 0.0025, 7.0, True), (0.93 - 0.0025, 5.333331, False)]
    exact, rounded = settle(bets), settle(bets, rounded_fee)
    assert r["final"] == round(240 + exact[0], 2) != round(240 + rounded[0], 2)
    assert r["perBet"] == pytest.approx(exact[0] / exact[1] * 1000, rel=1e-9)
    assert r["perBet"] != pytest.approx(rounded[0] / rounded[1] * 1000, rel=1e-6)
    assert r["need"] == pytest.approx(exact[2], rel=1e-12)


def test_the_price_never_passes_99_9c(study, monkeypatch):
    """A +0.5c gap: a 95c ask fills at 95.5c, a 99.8c one at 99.9c, not 100.3c."""
    sb = study.strategies_backtest
    monkeypatch.setattr(sb, "LIVE_FILLS", fills(0.5))
    window = [market("A", yes=True, q8=(0.99, 0.998)), market("B", yes=True, q8=(0.94, 0.95))]
    r = run(sb, fitted_account(), {T0: window})
    bets = [(0.999, 7.0, True), (0.955, 7.0, True)]
    pnl, staked, need = settle(bets)
    assert r["liveFit"] == {"orders": 2, "asked": 20.0, "got": 14.0, "missed": 0}
    assert r["final"] == round(240 + pnl, 2)
    assert r["need"] == pytest.approx(need, rel=1e-12)


def test_no_measured_gap_fills_at_the_candle_ask(study, monkeypatch):
    sb = study.strategies_backtest
    monkeypatch.setattr(sb, "LIVE_FILLS", fills(None))
    r = run(sb, fitted_account(), {T0: [market("BTC", yes=True, q8=(0.95, 0.96))]})
    pnl, staked, need = settle([(0.96, 7.0, True)])
    assert r["final"] == round(240 + pnl, 2) == 240.26
    assert r["need"] == pytest.approx(need, rel=1e-12)
    assert r["liveFit"] == {"orders": 1, "asked": 10.0, "got": 7.0, "missed": 0}


def test_an_order_expected_to_get_nothing_is_missed(study, monkeypatch):
    sb = study.strategies_backtest
    monkeypatch.setattr(sb, "LIVE_FILLS", fills())
    windows = {T0: [market("WTI", series="KXWTI15M", group="energy", yes=True)]}
    r = run(sb, fitted_account(), windows)
    assert r["liveFit"] == {"orders": 1, "asked": 10.0, "got": 0.0, "missed": 1}
    assert (r["bets"], r["final"], r["byGroup"], r["perBet"]) == (0, 240.0, [], None)


def test_the_slip_never_reaches_a_live_fit_account(study, monkeypatch):
    sb = study.strategies_backtest
    monkeypatch.setattr(sb, "LIVE_FILLS", fills())
    windows = {T0: [market("BTC", yes=True)], T0 + 900: [market("ETH", series="KXETH15M", yes=False)]}
    assert run(sb, fitted_account(), windows, 0.0) == run(sb, fitted_account(), windows, 0.004)


def test_other_accounts_carry_no_live_fit_record(study):
    sb = study.strategies_backtest
    r = run(sb, {**fitted_account(), "liveFit": False}, {T0: [market("BTC")]})
    assert r["liveFit"] is None
    assert run(sb, {k: v for k, v in fitted_account().items() if k != "liveFit"}, {T0: [market("BTC")]})["liveFit"] is None


# ------------------------------------------------------------------ run() on the synthetic history


def test_every_order_on_the_synthetic_history_gets_its_expected_fill(study, monkeypatch):
    """The live bot's rule at $10 a bet from a bankroll that can't run out, as edge() runs it, so every order the rule
    makes is sent: replayed here from the spec's formulas (spec_pick, spec_fill), apart from run()."""
    sb = study.strategies_backtest
    monkeypatch.setattr(sb, "LIVE_FILLS", fills())
    windows, first, last = sb.load()
    hours = int((last + 900 - first) // 3600) + 1
    strat = {**sb.LIVE[0], "id": "f", "liveFit": True, "sizing": "flat", "start": 1e9}
    r = sb.run(strat, windows, 0.004, first, hours)
    gap = FILLS["summary"]["gap"]["fillVsAsk"] / 100
    orders = asked = got = missed = bets = wins = 0
    pnl = staked = 0.0
    series = set()
    for t in sorted(windows):
        if any(t < z and t + 900 > a for a, z in sb.FED_WINDOWS):
            continue
        for m in windows[t]:
            if m["group"] not in EDGE:
                continue
            side, top = sb.favourite(*m["q"][8])
            if not side or not sb.LO <= top <= sb.HI or sb.skipped(strat, m, side):
                continue
            price = min(top + gap, 0.999)
            c = math.floor(10 / price + 1e-9)
            k = spec_fill(spec_pick(FILLS["depth"], m["series"], m["group"])["survival"], c)
            orders, asked, got = orders + 1, asked + c, got + k
            if k <= 0:
                missed += 1
                continue
            won = (side == "yes") == m["yes"]
            pnl += (k if won else 0.0) - k * price - exact_fee(k, price)
            staked += k * price
            bets, wins = bets + 1, wins + won
            series.add(m["series"].replace("KX", "").replace("15M", ""))
    assert bets > 0 and missed > 0 and 0 < got < asked, "the fixture exercises every case"
    assert r["liveFit"] == {"orders": orders, "asked": round(asked, 2), "got": round(got, 2), "missed": missed}
    assert (r["bets"], r["wins"]) == (bets, wins)
    assert r["perBet"] == pytest.approx(pnl / staked * 1000, rel=1e-9)
    assert sorted(g["key"] for g in r["bySeries"]) == sorted(series) and "WTI" not in series, "every WTI order missed"


# ------------------------------------------------------------------ the script, without and with a live_fills.json


def copy_history(study, folder):
    for name in ("universe.json", "minutes_30d.csv", "minutes_new.csv", "minutes_ext.csv", "minutes_pre.csv"):
        shutil.copy(study.dir / name, folder / name)
    return folder


def test_without_a_live_fills_file_there_is_nothing_to_fit(study):
    assert not (study.dir / "live_fills.json").exists()
    assert study.strategies_backtest.LIVE_FILLS is None


def test_without_a_live_fills_file_no_live_fit_account_exists(study):
    sb = study.strategies_backtest
    ids = [s["id"] for s in sb.STRATS]
    assert not set(FIT_IDS) & set(ids)
    assert not any(s.get("liveFit") for s in sb.STRATS)


@pytest.fixture(scope="module")
def plain(study, tmp_path_factory):
    """strategies.json from main() in a copy of the history with no live_fills.json."""
    folder = copy_history(study, tmp_path_factory.mktemp("no_live_fills"))
    home = os.getcwd()
    os.chdir(folder)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            study.strategies_backtest.main()
        return json.loads((folder / "strategies.json").read_text(encoding="utf-8"))
    finally:
        os.chdir(home)


def test_without_the_file_strategies_json_only_gains_live_fit_false(plain):
    for s in plain["strategies"]:
        assert s["liveFit"] is False and "liveFills" not in s, s["id"]
    for start in plain["starts"].values():
        for runs in start.values():
            assert all(r["liveFit"] is None for r in runs.values())


@pytest.fixture(scope="module")
def fitted(study, tmp_path_factory):
    """strategies_backtest reloaded in a copy of the history with FILLS as its live_fills.json; what it built, a run()
    of the live-fit account called directly, and main()'s strategies.json and printout there. The module is reloaded
    again in the session's folder (no live_fills.json) before anything else runs."""
    sb = study.strategies_backtest
    folder = copy_history(study, tmp_path_factory.mktemp("live_fills"))
    (folder / "live_fills.json").write_text(json.dumps(FILLS), encoding="utf-8")
    home = os.getcwd()
    os.chdir(folder)
    try:
        importlib.reload(sb)
        accounts = {s["id"]: copy.deepcopy(s) for s in sb.STRATS}
        windows, first, last = sb.load()
        hours = int((last + 900 - first) // 3600) + 1
        direct = None
        if "livefit" in accounts:
            direct = json.loads(json.dumps(sb.run(accounts["livefit"], windows, 0.004, first, hours,
                                                  sb.ts(study.history.JUL18))))
        ns = SimpleNamespace(live_fills=copy.deepcopy(getattr(sb, "LIVE_FILLS", "<strategies_backtest has no LIVE_FILLS>")),
                             accounts=accounts, ids=[s["id"] for s in sb.STRATS], live_ids=[s["id"] for s in sb.LIVE],
                             live0=copy.deepcopy(sb.LIVE[0]), direct=direct)
        with contextlib.redirect_stdout(io.StringIO()) as printed:
            sb.main()
        ns.stdout = printed.getvalue()
        ns.out = json.loads((folder / "strategies.json").read_text(encoding="utf-8"))
        return ns
    finally:
        os.chdir(home)
        importlib.reload(sb)


def test_the_file_is_read_whole_at_import(fitted):
    assert fitted.live_fills == FILLS


def test_a_live_fills_file_adds_the_two_live_fit_accounts(fitted):
    a = fitted.accounts
    assert [i for i in fitted.ids if a[i].get("liveFit")] == FIT_IDS, "only these two fill from the live orders"
    assert set(FIT_IDS) <= set(fitted.live_ids), "both are live-bot accounts (LIVE)"
    assert a["livefit"] == {**fitted.live0, "id": "livefit", "name": NAMES["livefit"], "liveFit": True}
    assert a["live3xfit"] == {**a["live3x"], "id": "live3xfit", "name": NAMES["live3xfit"], "liveFit": True}
    assert (a["livefit"]["role"], a["live3xfit"]["role"]) == ("live", "candidate")
    x = a["live3xfit"]
    assert (x["skipSeries"], x["skipSlots"], x["maxPer"]) == (["KXHYPE15M"], ["09:30"], {"crypto": 3})


def test_strategies_json_marks_the_live_fit_accounts_and_carries_their_fills(fitted):
    entries = {s["id"]: s for s in fitted.out["strategies"]}
    assert all(isinstance(s["liveFit"], bool) for s in fitted.out["strategies"])
    assert [i for i, s in entries.items() if s["liveFit"]] == FIT_IDS
    for sid in FIT_IDS:
        assert entries[sid]["name"] == NAMES[sid]
        assert entries[sid]["liveFills"] == LIVE_FILLS_ENTRY, sid
    assert all("liveFills" not in s for s in fitted.out["strategies"] if not s["liveFit"])
    strip = lambda s: {k: v for k, v in s.items() if k not in ("id", "name", "liveFit", "liveFills")}  # noqa: E731
    assert strip(entries["livefit"]) == strip(entries["live"]) and strip(entries["live3xfit"]) == strip(entries["live3x"])
    assert NAMES["livefit"] in fitted.stdout and NAMES["live3xfit"] in fitted.stdout


def test_the_live_fit_accounts_report_their_fills(fitted):
    starts = fitted.out["starts"]
    assert set(starts) == {"dec10", "jul18", "aug24"}
    for start in starts.values():
        for scenario, runs in start.items():
            for sid in FIT_IDS:
                r = runs[sid]
                q = r["liveFit"]
                assert set(q) == {"orders", "asked", "got", "missed"}, (sid, scenario)
                assert q["orders"] > 0 and 0 <= q["missed"] <= q["orders"] and q["got"] <= q["asked"]
                assert r["bets"] == q["orders"] - q["missed"], "every order expected to get something is a bet"
                assert r["liquidity"] is None
    every = [starts[k][s][sid]["liveFit"] for k in starts for s in ("backtest", "live") for sid in FIT_IDS]
    assert any(q["missed"] for q in every) and all(q["got"] < q["asked"] for q in every), \
        "WTI's orders miss and the other tables fill in part"
    for sid in FIT_IDS:
        for k in starts:
            assert starts[k]["backtest"][sid] == starts[k]["live"][sid], "the slip never reaches a live-fit account"
        assert fitted.out["edge"]["backtest"][sid] == fitted.out["edge"]["live"][sid]


def test_main_agrees_with_run_called_directly(fitted):
    assert fitted.direct is not None and fitted.direct == fitted.out["scenarios"]["live"]["livefit"]


def test_the_file_changes_nothing_else(fitted, plain):
    """Every other account, its entry and every number it reports, is what it is without the file."""
    assert [i for i in fitted.ids if i not in FIT_IDS] == [s["id"] for s in plain["strategies"]]
    entries = {s["id"]: s for s in fitted.out["strategies"]}
    for s in plain["strategies"]:
        assert entries[s["id"]] == s, s["id"]
    for k, start in plain["starts"].items():
        for scenario, runs in start.items():
            for sid, r in runs.items():
                assert fitted.out["starts"][k][scenario][sid] == r, (k, scenario, sid)
    for scenario, runs in plain["edge"].items():
        for sid, e in runs.items():
            assert fitted.out["edge"][scenario][sid] == e, (scenario, sid)


def test_the_session_module_is_back_to_no_live_fills(study, fitted):
    """After the reload in the copy, strategies_backtest is the session folder's again, for every other test file."""
    sb = study.strategies_backtest
    assert os.path.samefile(os.getcwd(), study.dir)
    assert getattr(sb, "LIVE_FILLS", None) is None and not set(FIT_IDS) & {s["id"] for s in sb.STRATS}
