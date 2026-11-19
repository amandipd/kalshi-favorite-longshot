"""price_floor.py: the live bot's rule with only its lowest price changed (90, 91, 92, 93 or 95c), on the synthetic history.

What it must get right: its lean loader gives the same replay as strategies_backtest's full one; each bet lands in the
price band it was bought in; the edge, break-even and 95% range (clustered by window) are the usual sums; fills limited
by the trade tape split the bets that filled from the ones that didn't; and price_floor.json holds every band, floor
and period the Research tab draws.

    python -m pytest research/kalshi_15min/tests/test_price_floor.py -q
"""
import importlib
import json
import math

import pytest


@pytest.fixture(scope="module")
def pf(study):
    return importlib.import_module("price_floor")


@pytest.fixture(scope="module")
def lean(pf):
    return pf.load()


def test_the_floors_and_bands(pf):
    assert pf.FLOORS == (0.90, 0.91, 0.92, 0.93, 0.95) and pf.START == 500.0
    assert pf.BANDS == ((90, 91), (92, 94), (95, 97), (98, 99))


@pytest.mark.parametrize("price, band", [(0.90, 0), (0.9075, 0), (0.91, 0), (0.9199999999, 1), (0.92, 1), (0.949, 1),
                                         (0.95, 2), (0.979, 2), (0.98, 3), (0.999, 3), (0.8999999999, 0), (0.89, None),
                                         (0.80, None)])
def test_a_price_falls_in_the_band_of_its_whole_cents(pf, price, band):
    assert pf.band_of(price) == band


def test_the_lean_loader_keeps_only_what_the_rule_reads(pf, lean, study):
    windows, first, last = lean
    full, ffirst, flast = study.strategies_backtest.load()
    assert (first, last) == (ffirst, flast) and set(windows) == set(full)        # every window, even one with no bets
    kept = [m for ms in windows.values() for m in ms]
    assert kept and all(set(m["q"]) == {6, 7, 8} and m["group"] in study.strategies_backtest.EDGE_GROUPS for m in kept)
    assert all(study.strategies_backtest.favourite(*m["q"][8])[1] >= min(pf.FLOORS) for m in kept)
    dup = study.data["duplicate"]                                                 # the first file read wins
    assert all(m["yes"] == (study.data["first_copy"]["resolved_yes"] == "1") for m in kept if m["ticker"] == dup["ticker"])


@pytest.mark.parametrize("lo", [0.90, 0.92, 0.95])
def test_the_lean_replay_is_the_full_one(pf, lean, study, lo):
    sb = study.strategies_backtest
    windows, first, last = lean
    full = sb.load()[0]
    hours = int((last + 900 - first) // sb.HOUR) + 1
    strat = {**sb.LIVE[0], "lo": lo, "start": pf.START}
    a, b = sb.run(strat, windows, 0.004, first, hours), sb.run(strat, full, 0.004, first, hours)
    assert a["bets"] == b["bets"] > 0 and a["final"] == b["final"] and a["maxDD"] == b["maxDD"]
    flat = {**sb.LIVE[0], "lo": lo, "sizing": "flat", "start": sb.EDGE_BANK}
    assert len(pf.bets(windows, lo)) == sb.run(flat, full, 0.004, first, hours)["bets"]   # every bet the rule places


def test_a_higher_floor_only_drops_bets(pf, lean):
    windows = lean[0]
    keys = [{(t, m["ticker"]) for t, top, won, m in pf.bets(windows, lo)} for lo in pf.FLOORS]
    assert all(b <= a for a, b in zip(keys, keys[1:])) and len(keys[0]) > len(keys[-1])
    assert all(top >= 0.95 - 1e-9 for _, top, _, _ in pf.bets(windows, 0.95))


def test_the_edge_of_a_few_bets(pf, study):
    fee = study.strategies_backtest.fee
    m = {"ticker": "X"}
    rows = [(100, 0.90, True, m), (100, 0.90, False, m), (200, 0.95, True, m)]
    e = pf.edge(rows, 0.0)
    p = [(10 / 0.9) - 10 - fee(10 / 0.9, 0.9), -10 - fee(10 / 0.9, 0.9), (10 / 0.95) - 10 - fee(10 / 0.95, 0.95)]
    mu = sum(p) / 3 * 100
    resid = [(p[0] + p[1]) * 100 - 2 * mu, p[2] * 100 - mu]
    se = math.sqrt(sum(x * x for x in resid) * 2 / 1) / 3
    need = (2 * (0.9 + fee(10 / 0.9, 0.9) / (10 / 0.9)) + 0.95 + fee(10 / 0.95, 0.95) / (10 / 0.95)) / 3
    assert e["n"] == 3 and e["win"] == pytest.approx(2 / 3) and e["need"] == pytest.approx(need)
    assert e["mu"] == pytest.approx(mu) and e["usd"] == pytest.approx(sum(p))
    assert (e["lo"], e["hi"]) == (pytest.approx(mu - 1.96 * se), pytest.approx(mu + 1.96 * se))


def test_the_edge_pays_the_slip_and_handles_one_window_or_none(pf):
    m = {"ticker": "X"}
    one = pf.edge([(1, 0.95, True, m)], 0.0)
    worse = pf.edge([(1, 0.95, True, m)], 0.004)
    assert worse["mu"] < one["mu"] and one["lo"] == one["hi"] == one["mu"]        # one window: no spread to measure
    assert pf.edge([(1, 0.998, True, m)], 0.004)["need"] <= 0.999 + 0.01           # the slip stops at 99.9c
    assert pf.edge([], 0.004) is None


def bands_by_key(out):
    return {b["key"]: b for b in out["bands"]}


@pytest.fixture(scope="module")
def built(pf, lean):
    return pf.build(*lean)


def test_every_band_by_period(pf, built, study):
    keys = [k for k, *_ in study.strategies_backtest.PERIODS] + ["all"]
    assert [p["key"] for p in built["periods"]] == keys
    assert [b["key"] for b in built["bands"]] == ["90-91", "92-94", "95-97", "98-99"]
    assert [b["label"] for b in built["bands"]] == ["90–91¢", "92–94¢", "95–97¢", "98–99¢"]
    b = bands_by_key(built)["90-91"]
    assert set(b["periods"]) <= set(keys) and b["periods"]["all"] == b["all"]
    assert sum(x["all"]["n"] for x in built["bands"]) == len(pf.bets(pf.load()[0], 0.90))
    assert sum(b["periods"][k]["n"] for k in keys[:-1] if b["periods"].get(k)) == b["all"]["n"]   # the periods split it


def test_every_floor_at_10_dollars_and_with_the_bots_bankroll(pf, built, study):
    keys = [p["key"] for p in built["periods"]]
    assert [f["lo"] for f in built["floors"]] == list(pf.FLOORS)
    for f in built["floors"]:
        assert f["edge"]["n"] == len(pf.bets(pf.load()[0], f["lo"]))
        for k in keys:
            r = f["runs"].get(k)
            if r is None:
                continue
            assert r["full"]["start"] == pf.START and set(r["full"]) == {"start", "final", "ret", "bets", "maxDD", "worstDay", "broke"}
            assert r["tape"] is None                                                # no trade tape in the synthetic study
    ns = [f["edge"]["n"] for f in built["floors"]]
    assert ns == sorted(ns, reverse=True)
    assert built["fills"] is None and built["slip"] == 0.004 and built["start"] == pf.START


def test_fills_limited_by_the_trade_tape(pf, lean, study, monkeypatch):
    sb = study.strategies_backtest
    rows = [r for r in pf.bets(lean[0], 0.90) if r[0] >= sb.ts(pf.TAPE_FROM)]
    a, b, c = [r for r in rows if pf.band_of(r[1]) == 0][:3]
    tape = {a[3]["ticker"]: (None, None, 5),                     # a quiet book: it fills
            b[3]["ticker"]: (2, b[1] + 0.02, 0),                 # the price ran away before the order landed: nothing
            c[3]["ticker"]: (40, c[1] + 0.02, 0)}                # a trade above it, but late: QUIET contracts still fill
    monkeypatch.setattr(sb, "LIQUIDITY", tape)
    out = pf.fills(rows)
    band = {x["key"]: x for x in out["bands"]}["90-91"]
    assert out["from"] == pf.TAPE_FROM and band["bets"] == 3 and band["filled"] == 2
    assert band["winFilled"] == pytest.approx((a[2] + c[2]) / 2) and band["winMissed"] == float(b[2])
    assert band["edge"]["n"] == 2
    empty = {x["key"]: x for x in out["bands"]}["98-99"]
    assert empty["bets"] == 0 and empty["winFilled"] is None and empty["edge"] is None
    monkeypatch.setattr(sb, "LIQUIDITY", None)
    assert pf.fills(rows) is None


def test_the_bankroll_runs_use_the_tape_when_there_is_one(pf, lean, study, monkeypatch):
    sb = study.strategies_backtest
    one = pf.bets(lean[0], 0.92)[0][3]["ticker"]
    monkeypatch.setattr(sb, "LIQUIDITY", {one: (None, None, 50)})  # a tape with one quiet book: every order still fills
    r = pf.runs(*lean)
    full, tape = r[0.92]["all"]["full"], r[0.92]["all"]["tape"]
    assert tape["bets"] == full["bets"] and tape["final"] != full["final"]   # filled at the ask itself, not 0.4c worse


def test_main_writes_price_floor_json(pf, study, capsys):
    pf.main()
    out = json.loads((study.dir / "price_floor.json").read_text(encoding="utf-8"))
    assert {"from", "to", "slip", "start", "periods", "bands", "fills", "floors"} <= set(out)
    assert out["to"] == study.history.end() and out["from"] == study.history.FIRST
    printed = capsys.readouterr().out
    assert "Strategy:" in printed and "price_floor.json" in printed
    first = (study.dir / "price_floor.json").read_text(encoding="utf-8")
    pf.main()
    assert (study.dir / "price_floor.json").read_text(encoding="utf-8") == first     # the same history gives the same file


def test_main_prints_the_fills_when_there_is_a_tape(pf, study, lean, monkeypatch, capsys):
    sb = study.strategies_backtest
    late = pf.bets(lean[0], 0.90)[-1][3]["ticker"]                # the last bet: inside the tape's stretch
    monkeypatch.setattr(sb, "LIQUIDITY", {late: (None, None, 50)})
    pf.main()
    printed = capsys.readouterr().out
    saved = json.loads((study.dir / "price_floor.json").read_text(encoding="utf-8"))
    assert "trade tape covers" in printed and saved["fills"]["from"] == pf.TAPE_FROM
    assert sum(b["bets"] for b in saved["fills"]["bands"]) == 1 and saved["floors"][0]["runs"]["all"]["tape"] is not None


def test_a_stretch_with_no_markets_and_a_missing_file(pf, study, monkeypatch, capsys):
    monkeypatch.setattr(study.strategies_backtest, "PERIODS", [("quiet", "Feb · nothing", "2026-02-01T00:00:00Z", "2026-03-01T00:00:00Z")])
    monkeypatch.setattr(study.history, "FILES", tuple(study.history.FILES) + ("minutes_missing.csv",))
    windows, first, last = pf.load()
    assert windows == {}
    out = pf.build(windows, first, last)
    assert [p["key"] for p in out["periods"]] == ["quiet", "all"]
    assert all(b["all"] is None for b in out["bands"]) and all(f["edge"] is None and f["runs"] == {} for f in out["floors"])
    pf.main()
    assert "no bets" in capsys.readouterr().out
