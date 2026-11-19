"""strategies_backtest.py's "real liquidity" account: orders filled only as far as Kalshi's trade tape says they could be.

`available()` is checked on each case liquidity.json can hold, and `run()` on one hand-built window where every order's
fill can be worked out by hand: filled in full with no tape, nothing when the price ran away, part when the book was thin.
Then the script end to end with a liquidity.json beside the history, in its own process, since the account is only
added when the file is there at import.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RESEARCH = Path(__file__).resolve().parent.parent
EDGE = ["crypto", "metals", "energy"]
T0 = 1_784_332_800  # 2026-07-18T00:00:00Z


def fee(c, p):
    return math.ceil(0.07 * c * p * (1 - p) * 100 - 1e-9) / 100


def market(ticker, yes=True, q8=(0.94, 0.96)):
    return {"ticker": ticker, "series": "KXBTC15M", "group": "crypto", "yes": yes, "q": {k: q8 for k in range(1, 16)}}


def taped(**extra):
    """$10 a bet in whole contracts, filled only as far as the tape allows: 10 contracts at a 96c ask."""
    return {"id": "q", "name": "test", "minute": 8, "sizing": "flat", "groups": EDGE, "whole": True, "liquidity": True,
            **extra}


# ------------------------------------------------------------------ available()


@pytest.mark.parametrize("entry, want, got", [
    (None, 10, 10),                    # no tape for the market: filled in full, as the other accounts are
    ([None, None, 0.0], 10, 3),        # nobody traded on our side after the order: QUIET contracts
    ([None, None, 7.0], 10, 7),        # others bought 7 at our price or better: that many
    ([None, None, 25.0], 10, 10),      # ... but never more than the order asked for
    ([3.0, 0.97, 25.0], 10, 0),        # the first trade came 3 s after the order, above our 96c: the price ran away
    ([10.0, 0.97, 25.0], 10, 0),       # ... FRESH seconds is still too soon
    ([11.0, 0.97, 25.0], 10, 10),      # later than FRESH: the book had time to refill
    ([2.0, 0.96, 25.0], 10, 10),       # soon, but at our own price: not a runaway
    ([2.0, 0.95, 1.0], 2, 2),          # an order smaller than QUIET gets all of it
])
def test_available_fills_what_the_tape_allows(study, monkeypatch, entry, want, got):
    sb = study.strategies_backtest
    assert (sb.FRESH, sb.QUIET) == (10, 3), "the cases above are written for these"
    monkeypatch.setattr(sb, "LIQUIDITY", {} if entry is None else {"M": entry})
    assert sb.available({"ticker": "M"}, 0.96, want) == got


# ------------------------------------------------------------------ run(), by hand


def test_run_fills_each_order_only_as_far_as_the_tape_allows(study, monkeypatch):
    sb = study.strategies_backtest
    monkeypatch.setattr(sb, "LIQUIDITY", {
        "RAN": [3.0, 0.97, 0.0],       # missed, and it would have won
        "THIN": [12.0, 0.97, 4.0],     # 4 of 10
        "QUIET": [None, None, 1.0],    # 3 of 10
        "DEEP": [2.0, 0.96, 20.0],     # all 10
    })
    windows = {T0: [market("UNTAPED", yes=True), market("RAN", yes=True), market("THIN", yes=False),
                    market("QUIET", yes=True), market("DEEP", yes=True)]}
    r = sb.run(taped(), windows, 0.004, T0, 1)
    assert r["liquidity"] == {"asked": 50.0, "got": 27.0, "orders": 5, "missed": 1, "missedWon": 1, "partial": 2}
    pnl = lambda c, won: (c if won else 0) - c * 0.96 - fee(c, 0.96)  # noqa: E731
    # filled at the 96c ask itself, not 0.4c worse: an immediate-or-cancel order never pays more than its limit
    expected = pnl(10, True) + pnl(4, False) + pnl(3, True) + pnl(10, True)
    assert r["final"] == round(240 + expected, 2)
    assert (r["bets"], r["wins"]) == (4, 3), "the order that got nothing is not a bet"
    assert r["byGroup"][0]["staked"] == round(27 * 0.96, 2)


def test_the_slip_never_reaches_a_taped_account(study, monkeypatch):
    sb = study.strategies_backtest
    monkeypatch.setattr(sb, "LIQUIDITY", {})
    windows = {T0: [market("A", yes=True)], T0 + 900: [market("B", yes=False)]}
    assert sb.run(taped(), windows, 0.0, T0, 1) == sb.run(taped(), windows, 0.004, T0, 1)


def test_other_accounts_carry_no_liquidity_record(study):
    sb = study.strategies_backtest
    r = sb.run({**taped(), "liquidity": False}, {T0: [market("A")]}, 0.0, T0, 1)
    assert r["liquidity"] is None


# ------------------------------------------------------------------ the script, with a liquidity.json


@pytest.fixture(scope="module")
def with_tape(study, tmp_path_factory):
    """strategies_backtest.py run in a copy of the history with a liquidity.json: a third of the live rule's bets
    missed (the price ran away), a third thin (nobody else traded), the rest left off the file."""
    import liquidity
    bets = liquidity.bets()
    tape = {}
    for i, (ticker, _, _, top) in enumerate(bets):
        if i % 3 == 0:
            tape[ticker] = [1.0, round(top + 0.01, 3), 0.0]
        elif i % 3 == 1:
            tape[ticker] = [None, None, 1.0]
    folder = tmp_path_factory.mktemp("taped")
    for name in ("universe.json", "minutes_30d.csv", "minutes_new.csv", "minutes_ext.csv"):
        shutil.copy(study.dir / name, folder / name)
    (folder / "liquidity.json").write_text(json.dumps({"send": 482, "depth": 30, "markets": tape}), encoding="utf-8")
    env = dict(os.environ, PYTHONPATH=str(RESEARCH), PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, str(RESEARCH / "strategies_backtest.py")], cwd=folder, env=env,
                       capture_output=True, encoding="utf-8", timeout=600)
    assert r.returncode == 0, r.stderr[-2000:]
    out = json.loads((folder / "strategies.json").read_text(encoding="utf-8"))
    return out, r.stdout, tape


def test_a_liquidity_file_adds_the_real_liquidity_account(with_tape):
    out, stdout, _ = with_tape
    accounts = {s["id"]: s for s in out["strategies"]}
    assert "liveliq" in accounts and accounts["liveliq"]["liquidity"] is True
    assert [s["id"] for s in out["strategies"] if s["liquidity"]] == ["liveliq", "live3xliq", "mine4liq",
                                                                      "mine4liq10k", "mine4liq850", "mine4liq1k"],       "only those accounts read the tape: the live bot, the Oct 11 candidates' all-three account, and version 4 "         "from $2,000, $10,000, a small $850 and $1,000 (MINE)"
    live, liq = accounts["live"], accounts["liveliq"]
    for key in ("minute", "sizing", "groups", "skip", "start", "whole", "maxOrder", "blackouts"):
        assert liq[key] == live[key], f"the real-liquidity account is the live bot's rule ({key})"
    assert liq["maxOrder"] is None, "like the real bot since Oct 10, no order cap"
    assert "The live bot · real liquidity" in stdout


def test_a_liquidity_file_adds_all_three_candidates_with_real_liquidity(with_tape):
    """live3xliq is "The live bot · all three" (skip HYPE, skip the weekday 9:30 ET window, at most 3 crypto bets a
    window) with fills from the tape, appended last; it reports its fills like liveliq."""
    out, stdout, _ = with_tape
    ids = [s["id"] for s in out["strategies"]]
    accounts = {s["id"]: s for s in out["strategies"]}
    assert ids[ids.index("live3xliq") + 1:] == ["mine1", "mine2", "mine3", "mine4", "mine4liq",
                                                "mine4liq10k", "mine4liq850", "mine4liq1k"], "the last of LIVE, then MINE"
    assert ids.index("liveliq") < ids.index("livenh")
    x, liq = accounts["live3x"], accounts["live3xliq"]
    assert liq["name"] == "The live bot · all three · real liquidity" and liq["liquidity"] is True and not x["liquidity"]
    assert {k: v for k, v in liq.items() if k not in ("id", "name", "liquidity")} ==         {k: v for k, v in x.items() if k not in ("id", "name", "liquidity")}
    assert (liq["skipSeries"], liq["skipSlots"], liq["maxPer"]) == (["KXHYPE15M"], ["09:30"], {"crypto": 3})
    assert "The live bot · all three · real liquidity" in stdout
    for start in ("jul18", "aug24"):
        q = out["starts"][start]["live"]["live3xliq"]["liquidity"]
        assert q and q["orders"] > 0 and q["got"] <= q["asked"]


def test_the_real_liquidity_account_reports_its_fills(with_tape):
    out, _, tape = with_tape
    for start in ("jul18", "aug24"):
        for scenario in ("backtest", "live"):
            r = out["starts"][start][scenario]["liveliq"]
            q = r["liquidity"]
            assert q["orders"] > 0 and 0 < q["missed"] < q["orders"]
            assert 0 < q["got"] < q["asked"] and q["missedWon"] <= q["missed"]
            # Every order here asks 3 contracts: 1.5% of a bankroll that stays near its $225 start, at a 96c ask.
            # That is exactly the tape's QUIET floor, so a thin market fills all 3 and no order fills in part --
            # test_run_fills_each_order_only_as_far_as_the_tape_allows covers partial fills by hand ("THIN", 4 of 10).
            # If this breaks, the account's size changed: check it against bot.py before touching the number.
            assert q["asked"] == 3 * q["orders"] and q["got"] == 3 * (q["orders"] - q["missed"])
            assert q["partial"] == 0
            assert r["bets"] == q["orders"] - q["missed"], "every order that got something is a bet"
    for start in ("jul18", "aug24"):
        a, b = (out["starts"][start][s]["liveliq"] for s in ("backtest", "live"))
        assert a["final"] == b["final"] and a["liquidity"] == b["liquidity"], "fills at the ask under either scenario"
