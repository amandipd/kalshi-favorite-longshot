"""edge_map.py: what it adds to common.py must match strategies_backtest's own functions.

common.py already reproduces strategies.json, so these check edge_map's own pieces on synthetic markets: the underdog
is the other side at its own ask, the crypto cap keeps the dearest or tightest bets in each window, and the sized
replay (3% a bet, 20% a window, whole contracts, from $500) is strategies_backtest.run()'s live bot to the cent.
Edge cases are set by hand: an ask of exactly 90c, a mid of exactly 50c, a jump of exactly 10c, a spread of exactly
2c, missing quotes, a Fed afternoon. strategies_backtest is imported in an empty folder with history.end() stubbed, so
nothing here reads the minute CSVs, liquidity.json or live_fills.json, and then everything is put back (see below).

    python -m pytest research/kalshi_15min/lab/test_edge_map.py -q
"""
import importlib
import os
import random
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

import numpy as np
import pytest

LAB = Path(__file__).resolve().parent
sys.path[:0] = [str(LAB), str(LAB.parent)]

import history  # noqa: E402
import common as C  # noqa: E402
import edge_map as em  # noqa: E402


def own_strategies_backtest():
    """strategies_backtest for this file alone. At import it reads the working folder: every minute CSV (history.end(),
    for PERIODS), liquidity.json and live_fills.json (accounts built from them). So it is imported in an empty folder
    with history.end() stubbed, and then the stub, the working folder and sys.modules are put back as they were.

    pytest imports this file while collecting, before any test runs. A copy left in sys.modules would be the one
    tests/conftest.py's study fixture gets back instead of importing its own in the synthetic history, and the stub
    would stay on history.end() for every test after this file. That, with band_weight_test.py collected as a test file
    (see python_files in pyproject.toml), failed 8 tests in tests/ on Nov 6, 2026."""
    real_end, home, had = history.end, os.getcwd(), "strategies_backtest" in sys.modules
    with tempfile.TemporaryDirectory() as empty:
        history.end = lambda: "2026-10-09T00:00:00Z"
        os.chdir(empty)
        try:
            return importlib.import_module("strategies_backtest")
        finally:
            os.chdir(home)
            history.end = real_end
            if not had:
                sys.modules.pop("strategies_backtest", None)


sb = own_strategies_backtest()

FED = sb.FED_WINDOWS[-1][0]                  # 2:00 pm ET on Sep 16, 2026
T0 = FED - 40 * 900                          # 10 hours before it, so a few windows fall in the blackout
GROUPS = ["crypto", "crypto", "crypto", "crypto", "metals", "energy"]


def synthetic(tmp, seed=7, windows=120, per=6):
    """(common.load() of the markets, strategies_backtest-style {open_ts: [market]})."""
    rnd = random.Random(seed)
    rows = []
    for w in range(windows):
        for j in range(per):
            mid = rnd.choice([0.5, 0.7, 0.85, 0.93, 0.95, 0.96, 0.97, 0.04, 0.1])
            bid, ask = [], []
            for k in range(15):
                mid = min(0.995, max(0.005, mid + rnd.gauss(0, 0.02) + (0.12 if rnd.random() < 0.03 else 0)))
                half = rnd.choice([0.0005, 0.002, 0.005, 0.01, 0.015, 0.03])
                b, a = round(max(mid - half, 0.0), 4), round(min(mid + half, 1.0), 4)
                if rnd.random() < 0.03:
                    b = a = None
                bid.append(b)
                ask.append(a)
            rows.append({"ticker": f"KX{w}-{j}", "series": f"KXS{j}", "group": GROUPS[j], "t": T0 + 900 * w,
                         "yes": rnd.random() < mid, "bid": bid, "ask": ask})
    r = rows[0]
    r["bid"][5:8], r["ask"][5:8] = [0.49, 0.80, 0.88], [0.51, 0.82, 0.90]        # mid 50c at M-2; ask exactly 90c
    rows[1]["bid"][6:8], rows[1]["ask"][6:8] = [0.82, 0.92], [0.84, 0.94]         # +10c in minute 8; spread exactly 2c
    rows[2]["bid"][7], rows[2]["ask"][7] = 0.04, 0.06                             # a NO favourite at 96c
    path = Path(tmp) / "markets.npz"
    np.savez(path, ticker=np.array([r["ticker"] for r in rows]), series=np.array([r["series"] for r in rows]),
             group=np.array([r["group"] for r in rows]), open_ts=np.array([r["t"] for r in rows], dtype=np.int64),
             yes=np.array([r["yes"] for r in rows], dtype=np.int8),
             bid=np.array([[np.nan if x is None else x for x in r["bid"]] for r in rows], dtype=np.float32),
             ask=np.array([[np.nan if x is None else x for x in r["ask"]] for r in rows], dtype=np.float32),
             last=np.zeros((len(rows), 15), dtype=np.float32))
    windows = defaultdict(list)
    for r in rows:
        windows[r["t"]].append({"ticker": r["ticker"], "series": r["series"], "group": r["group"], "yes": r["yes"],
                                "q": {k: (r["bid"][k - 1], r["ask"][k - 1]) for k in range(1, 16)}})
    return C.load(path=str(path)), dict(windows)


@pytest.fixture(scope="module")
def data(tmp_path_factory):
    return synthetic(tmp_path_factory.mktemp("lab"))


def hours(windows):
    return int((max(windows) + 900 - min(windows)) // sb.HOUR) + 1


def test_common_picks_the_reference_bets(data):
    d, windows = data
    want = []
    for t in sorted(windows):
        if any(t < z and t + 900 > a for a, z in sb.FED_WINDOWS):
            continue
        for m in windows[t]:
            side, top = sb.favourite(*m["q"][8])
            if side and sb.LO <= top <= sb.HI and not sb.skipped(sb.LIVE[0], m, side):
                want.append(m["ticker"])
    mask, _, _ = C.live_rule(d)
    assert sorted(d["ticker"][mask]) == sorted(want) and len(want) > 30
    i0, i1 = (int(np.flatnonzero(d["ticker"] == f"KX0-{j}")[0]) for j in range(2))
    plain = C.live_rule(d, skip=(), fed=False)[0]
    assert plain[i0] and not mask[i0] and plain[i1] and not mask[i1]


def test_the_underdog_is_the_other_side_at_its_own_ask(data):
    d, windows = data
    side_yes, top = C.favourite(d, 8)
    dog = em.underdog_ask(d, side_yes, 8)
    checked = 0
    for i in np.flatnonzero(~np.isnan(top)):
        m = next(m for m in windows[int(d["open_ts"][i])] if m["ticker"] == d["ticker"][i])
        q = sb.own_quote(m, "no" if side_yes[i] else "yes", 8)
        assert dog[i] == pytest.approx(q[1], abs=1e-12)
        checked += 1
    i2 = int(np.flatnonzero(d["ticker"] == "KX0-2")[0])
    assert not side_yes[i2] and top[i2] == 0.96 and dog[i2] == 0.06 and checked > 100


@pytest.mark.parametrize("pick, cap, kept", [("price", 2, [1, 3, 4]), ("spread", 2, [0, 2, 4]),
                                             ("price", 3, [1, 2, 3, 4]), ("price", None, [0, 1, 2, 3, 4])])
def test_a_crypto_cap_keeps_the_dearest_or_tightest(pick, cap, kept):
    d = {"group": np.array(["crypto", "crypto", "crypto", "crypto", "metals", "crypto"]),
         "open_ts": np.array([0, 0, 0, 0, 0, 900])}
    top = np.array([0.93, 0.97, 0.95, 0.96, 0.92, 0.91])
    spread = np.array([0.001, 0.01, 0.002, 0.005, 0.03, 0.01])
    mask = np.array([True] * 5 + [False])
    got = em.cap_mask(d, mask, top, spread, cap, pick)
    assert list(np.flatnonzero(got)) == kept                  # metals never capped; an unchosen market stays out


def test_the_sized_replay_is_the_live_bots(data):
    d, windows = data
    ref = sb.run({**sb.LIVE[0], "start": 500.0}, windows, sb.SCENARIOS["live"], min(windows), hours(windows))
    mask, side_yes, top = C.live_rule(d)
    got = em.replay(d, mask, top, C.won(d, side_yes), start=500.0)
    assert got["bets"] == ref["bets"] > 30
    assert got["final"] == pytest.approx(ref["final"], abs=1e-6)
    assert got["maxDD"] == pytest.approx(ref["maxDD"], abs=1e-9)
    assert got["worstWindow"] == pytest.approx(ref["worstWindow"], abs=1e-6)


def test_the_replay_of_one_crypto_bet_is_the_one_per_window_account(data):
    """strategies_backtest's "1 crypto bet a window" keeps the dearest crypto favourite; at $10 a bet the replay of the
    price-capped mask must place the same bets for the same money."""
    d, windows = data
    strat = {**sb.LIVE[0], "id": "x", "sizing": "flat", "whole": True, "start": sb.EDGE_BANK, "onePer": ["crypto"]}
    ref = sb.run(strat, windows, sb.SCENARIOS["live"], min(windows), hours(windows))
    mask, side_yes, top = C.live_rule(d)
    capped = em.cap_mask(d, mask, top, em.spread(d, side_yes, 8), 1, "price")
    pnl, cost = C.bet(top[capped], C.won(d, side_yes)[capped])
    assert len(pnl) == ref["bets"] and pnl.sum() == pytest.approx(ref["final"] - sb.EDGE_BANK, abs=0.005)   # run() rounds its final to the cent


@pytest.mark.parametrize("cap", [0.10, 0.06])
def test_a_smaller_window_cap_is_the_live_bots_with_that_cap(data, monkeypatch, cap):
    d, windows = data
    monkeypatch.setattr(sb, "WINDOW_CAP", cap)
    ref = sb.run({**sb.LIVE[0], "start": 500.0}, windows, sb.SCENARIOS["live"], min(windows), hours(windows))
    mask, side_yes, top = C.live_rule(d)
    got = em.replay(d, mask, top, C.won(d, side_yes), start=500.0, window_cap=cap)
    assert got["bets"] == ref["bets"] > 30 and got["final"] == pytest.approx(ref["final"], abs=1e-6)


def test_the_stock_open_window_is_the_weekday_one_opening_at_930_et():
    from datetime import datetime
    at = lambda s: int(datetime.fromisoformat(s).replace(tzinfo=C.ET).timestamp())
    d = {"open_ts": np.array([at("2026-03-02T09:30"), at("2026-03-02T09:15"), at("2026-03-02T09:45"),
                              at("2026-03-07T09:30"), at("2026-07-01T09:30"), at("2026-01-15T09:30")])}
    assert list(em.slot_mask(d, 9, 30)) == [True, False, False, False, True, True]   # Saturday out; EST and EDT both


def test_spreads_compare_at_4_places_so_a_1c_tie_goes_to_the_dearer(tmp_path):
    """0.94 - 0.93 is 0.0099999... and 0.96 - 0.95 is 0.0100000...09 in floats: both are 1c, so the dearer must win."""
    bid = np.array([[0.93] * 15, [0.95] * 15, [0.03] * 15], dtype=np.float32)
    ask = np.array([[0.94] * 15, [0.96] * 15, [0.04] * 15], dtype=np.float32)   # the third: a NO favourite at 97c, 1c
    path = tmp_path / "m.npz"
    np.savez(path, ticker=np.array(["a", "b", "c"]), series=np.array(["KXA15M", "KXB15M", "KXC15M"]),
             group=np.array(["crypto"] * 3), open_ts=np.zeros(3, dtype=np.int64), yes=np.ones(3, dtype=np.int8),
             bid=bid, ask=ask, last=ask)
    d = C.load(path=str(path))
    side_yes, top = C.favourite(d, 8)
    sp = em.spread(d, side_yes, 8)
    assert list(sp) == [0.01, 0.01, 0.01]
    assert list(np.flatnonzero(em.cap_mask(d, np.ones(3, bool), top, sp, 1, "spread"))) == [2]   # 97c beats 96c and 94c
    assert list(np.flatnonzero(em.cap_mask(d, np.array([True, True, False]), top, sp, 1, "spread"))) == [1]
