"""The 35%-in-24-hours halt, hammered: the exact line, the rolling day, peaks, resumes, a brute-force
cross-check on random accounts, and whole runs through Bot.step. Nothing here touches the network.

    python -m pytest tests/test_day_drop.py -q
"""
import os
import random
from fractions import Fraction

import pytest

from kalshi_bot import bot
from test_bot import ENTRY, W, FakeKalshi, decisions, env, fake_bet  # noqa: F401 (env is a fixture)

DAY = 86400
NOW = W + 200_000  # a "now" with more than a day of history behind it
LINE = Fraction(7, 20)  # 35%


def settle_bet(db, i, pnl, settled):
    """A settled bet in a window of its own, so the 8-losses-in-a-window halt can never be the one that fires."""
    fake_bet(db, i, W + 900 * i, pnl > 0, pnl, settled=settled)


def open_bet(db, ticker, window, contracts, cost, fee=0.05, side="yes"):
    db.execute("INSERT INTO bets (ticker, series, window_open, close_ts, side, price, contracts, cost, fee, placed_ts, status)"
               " VALUES (?,?,?,?,?,?,?,?,?,?, 'open')",
               (ticker, ticker.split("-")[0], window, window + 900, side, cost / contracts, contracts, cost, fee, window + 480))


def check(db, now=NOW):
    bot.check_halts(db, now, True)
    return bot.halt_info()


# ------------------------------------------------------------------ the line itself
def test_the_line_is_35_percent():
    assert bot.HALT_DAY_DROP == 0.35


@pytest.mark.parametrize("loss, halts", [(0.01, False), (5, False), (20.0, False), (34.0, False), (34.99, False),
                                         (35.0, True), (35.01, True), (40.0, True), (49.0, True)])
def test_one_loss_against_the_line(env, loss, halts):
    settle_bet(env, 0, -loss, NOW - 60)
    h = check(env)
    assert (h is not None) is halts
    if halts:
        assert h["reason"] == f"the account fell {loss / 100:.0%} within 24 hours"


@pytest.mark.parametrize("start", [1.0, 7.77, 37.13, 99.99, 100.0039, 250.5, 1234.56, 99999.99])
def test_exactly_35_percent_halts_at_any_account_size(env, start):
    """Float noise must not let a drop of exactly 35% slip under the line."""
    bot.set_start(env, start)
    env.commit()
    settle_bet(env, 0, -float(Fraction(str(start)) * LINE), NOW - 60)
    assert check(env) is not None


@pytest.mark.parametrize("start", [1.0, 7.77, 37.13, 100.0039, 250.5, 1234.56])
def test_just_under_35_percent_doesnt_halt_at_any_account_size(env, start):
    bot.set_start(env, start)
    env.commit()
    settle_bet(env, 0, -float(Fraction(str(start)) * Fraction(3499, 10000)), NOW - 60)  # 34.99%
    assert check(env) is None


def test_the_line_is_read_when_it_matters(env, monkeypatch):
    monkeypatch.setattr(bot, "HALT_DAY_DROP", 0.10)
    settle_bet(env, 0, -10.0, NOW - 60)
    assert check(env) is not None


def test_nothing_settled_no_halt_and_wins_never_halt(env):
    assert check(env) is None
    settle_bet(env, 0, +500.0, NOW - 60)
    assert check(env) is None


# ------------------------------------------------------------------ losses add up
def test_small_losses_add_up_and_cross_the_line_exactly_once(env):
    for i in range(1, 36):
        t = NOW - 3600 + 60 * i
        settle_bet(env, i, -1.0, t)
        bot.check_halts(env, t + 1, True)
        assert (bot.halt_info() is not None) == (i >= 35), f"after {i} losses of $1 on $100"
    assert bot.halt_info()["reason"] == "the account fell 35% within 24 hours"


def test_a_halt_keeps_its_first_reason(env):
    settle_bet(env, 0, -36.0, NOW - 120)
    first = check(env)
    settle_bet(env, 1, -10.0, NOW - 60)
    assert check(env, NOW + 500) == first  # not rewritten by a later, bigger drop


# ------------------------------------------------------------------ peaks, recoveries, open bets
def test_measured_from_the_peak_not_the_start(env):
    settle_bet(env, 0, +60.0, NOW - 7200)   # 160
    settle_bet(env, 1, -55.9, NOW - 3600)   # 104.1: 34.94% off the peak
    assert check(env) is None
    settle_bet(env, 2, -0.2, NOW - 60)      # 103.9: 35.06% off the peak
    assert check(env, NOW) is not None
    assert bot.bankroll(env) > 100          # halted while still above where it started


def test_a_recovery_doesnt_erase_the_drop(env):
    settle_bet(env, 0, -36.0, NOW - 120)    # touched $64 ...
    settle_bet(env, 1, +15.0, NOW - 60)     # ... and is back at $79 by the time anyone looks
    assert check(env) is not None


def test_a_win_after_the_peak_moves_the_peak_up(env):
    settle_bet(env, 0, -10.0, NOW - 300)    # 90 (10% off the start)
    settle_bet(env, 1, +20.0, NOW - 200)    # 110: a new peak
    assert check(env) is None
    settle_bet(env, 2, -37.4, NOW - 100)    # 72.6: 34% off 110
    assert check(env) is None
    settle_bet(env, 3, -1.1, NOW - 50)      # 71.5: exactly 35% off 110
    assert check(env) is not None


def test_open_bets_are_not_losses_until_they_settle(env):
    open_bet(env, "OPEN-1", W, contracts=90, cost=85.0)  # $85 riding on one bet
    assert check(env) is None


# ------------------------------------------------------------------ the rolling day
@pytest.mark.parametrize("age, halts", [(DAY + 3600, False), (DAY + 1, False), (DAY, False), (DAY - 1, True), (60, True)])
def test_only_the_last_24_hours_count(env, age, halts):
    """A -40 loss: outside the day it is just where the day starts, inside it is a 40% drop."""
    settle_bet(env, 0, -40.0, NOW - age)
    assert (check(env) is not None) is halts


@pytest.mark.parametrize("at, halts", [(NOW, True), (NOW + 20, False)])
def test_a_loss_ages_out_of_the_day(env, at, halts):
    settle_bet(env, 0, -20.0, NOW - DAY + 10)   # 20% ...
    settle_bet(env, 1, -20.0, NOW - 100)        # ... and 20 more
    assert (check(env, at) is not None) is halts  # 40% together at NOW; 20 s later the first has aged out (25%)


def test_an_old_peak_is_only_the_starting_point(env):
    settle_bet(env, 0, +50.0, NOW - DAY - 3600)   # 150, more than a day ago
    settle_bet(env, 1, -52.0, NOW - 60)           # 98: 34.67% off 150
    assert check(env) is None
    settle_bet(env, 2, -0.6, NOW - 30)            # 97.4: 35.07% off 150
    assert check(env) is not None


# ------------------------------------------------------------------ resume
def test_resume_starts_the_day_over(env):
    settle_bet(env, 0, -36.0, NOW - 120)
    assert check(env) is not None
    bot.clear_halt(NOW, [env])
    assert bot.halt_info() is None
    settle_bet(env, 1, -22.3, NOW + 60)        # 22.3 of the $64 it resumed at: 34.84%
    assert check(env, NOW + 61) is None
    settle_bet(env, 2, -0.2, NOW + 120)        # 35.16%
    assert check(env, NOW + 121)["reason"] == "the account fell 35% within 24 hours"


# ------------------------------------------------------------------ brute force
def worst_drop(start, bets, now):
    """Largest fall from any earlier balance to any later one inside the day, in exact arithmetic."""
    since = now - DAY
    base = Fraction(start) + sum(Fraction(p) for t, p in bets if t <= since)
    path, bal = [base], base
    for _, p in sorted((t, p) for t, p in bets if t > since):
        bal += Fraction(p)
        path.append(bal)
    if min(path) <= 0:
        return None
    return max(1 - path[j] / path[i] for i in range(len(path)) for j in range(i, len(path)))


def test_agrees_with_a_brute_force_on_random_accounts(env, monkeypatch):
    monkeypatch.setattr(bot, "HALT_DEPOSIT", -1)  # only the 24-hour rule is under test
    rng = random.Random(20260929)
    halted = tried = 0
    for _ in range(600):
        env.execute("DELETE FROM bets")
        try:
            os.remove(bot.halt_path())
        except FileNotFoundError:
            pass
        bot._since.clear()
        n = rng.randint(0, 25)
        times = rng.sample(range(int(NOW) - 30 * 3600, int(NOW)), n)
        bets = [(t, round(rng.uniform(0.02, 0.4), 2) if rng.random() < 0.7 else -round(rng.uniform(1, 16), 2)) for t in times]
        expected = worst_drop(Fraction(100), bets, NOW)
        if expected is None or abs(expected - LINE) < Fraction(1, 10**7):
            continue  # a ruined account, or a hair from the line where float rounding is allowed to differ
        for i, (t, p) in enumerate(bets):
            settle_bet(env, i, p, t)
        env.commit()
        h = check(env)
        tried += 1
        halted += h is not None
        assert (h is not None) == (expected >= LINE), (float(expected), bets)
        if h:
            assert "within 24 hours" in h["reason"]
    assert tried > 500 and 100 < halted < tried - 100  # both outcomes were really exercised


# ------------------------------------------------------------------ whole runs through Bot.step
class Sim(FakeKalshi):
    """Settles at the market's close, as Kalshi does, so a run over many windows keeps sensible times."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.close = {}

    def markets(self, **p):
        if "series_ticker" in p:
            d = super().markets(**p)
            for m in d["markets"]:
                self.close[m["ticker"]] = bot.ts(m["close_time"])
            return d
        return {"markets": [{"ticker": t, "result": r, "settlement_ts": bot.iso(self.close[t])} for t, r in self.results.items()]}


class Many(Sim):
    """n crypto markets, every one a 96c YES favourite."""

    def __init__(self, n, **kw):
        super().__init__(**kw)
        self.names = [f"KXT{i}15M" for i in range(n)]
        self.books = {s: {"yes_dollars": [["0.95", "100"]], "no_dollars": [["0.04", "50"]]} for s in self.names}

    def series(self):
        return {"series": [{"ticker": s, "frequency": "fifteen_min", "category": "Crypto", "fee_multiplier": 1} for s in self.names]}


def play(db, fake, windows, losing):
    """Windows in a row, stepped like the real loop: at minute 8, then just after the close. Every bet in
    the windows `losing` names loses. Returns the orders placed in each window."""
    b = bot.Bot(fake, db, True)
    per_window = []
    for k in range(windows):
        w = W + 900 * k
        fake.window, fake.suffix = w, f"S{k}"
        before = len(fake.orders)
        b.step(w + 485)
        per_window.append(len(fake.orders) - before)
        fake.results.update(losing(k))
        b.step(w + 920)
    return per_window


def test_a_losing_streak_stops_the_bot_at_35_percent(env):
    """From $1,000, so its 1.5% bets stay over the $1 minimum all the way down to the 35% line. (From $100 they'd fall
    under it at $66.67, just before the line at $65, and it would stop betting without halting.)"""
    bot.set_start(env, 1000.0)
    env.commit()
    fake = Sim()
    per = play(env, fake, 20, lambda k: {f"KXBTC15M-S{k}": "no", f"KXGOLD15M-S{k}": "yes"})  # both bets lose, every window
    assert "within 24 hours" in bot.halt_info()["reason"]
    stop = per.index(0)
    assert stop >= 2 and sum(per[stop:]) == 0, per  # trading, then not one order after the halt
    assert decisions(env)[f"KXBTC15M-S{stop}"][0] == "halted"
    rows = env.execute("SELECT SUM(pnl) p FROM bets GROUP BY window_open ORDER BY window_open").fetchall()
    after = 1000 + sum(r["p"] for r in rows)
    before = after - rows[-1]["p"]
    assert after <= 650 < before  # it crossed on the last window it lost, and not a window earlier


def test_wins_in_between_keep_it_trading_until_the_drop_is_real(env):
    fake = Sim()
    per = play(env, fake, 4, lambda k: {f"KXBTC15M-S{k}": "no", f"KXGOLD15M-S{k}": "yes"} if k < 3  # three losing windows ...
               else {f"KXBTC15M-S{k}": "yes", f"KXGOLD15M-S{k}": "no"})                           # ... then a winning one
    assert bot.halt_info() is None and all(per), per  # three losing windows in a row is ~6%, not 35%


def test_one_full_size_window_that_loses_everything_still_stops_it(env):
    """Ten bets is the 10% window cap: they cost 9.7% of the account. The 24-hour rule lets that one go,
    and the 8-losses-in-a-window rule is what catches it."""
    fake = Many(10)
    per = play(env, fake, 3, lambda k: {f"{s}-S{k}": "no" for s in fake.names})
    assert per == [10, 0, 0]
    assert bot.halt_info()["reason"].startswith("10 bets lost in one window")


def test_losses_settling_in_the_entry_minute_stop_that_windows_orders(env):
    """A bot that was off (or Kalshi settling slowly) settles the last window's losses in the very step
    that would place this window's orders: they must count before those orders go out."""
    prev = W - 900
    for i in range(3):
        open_bet(env, f"OLD-{i}", prev, contracts=13, cost=12.5)  # three big bets: 37.5% of the account
    fake = FakeKalshi()
    fake.results = {"OLD-0": "no", "OLD-1": "no", "OLD-2": "no"}  # all three YES bets lose
    bot.Bot(fake, env, True).step(ENTRY)
    assert "within 24 hours" in bot.halt_info()["reason"]
    assert fake.orders == []
    assert decisions(env)["KXBTC15M-A"][0] == "halted"
