"""The $700 stop (HALT_FLOOR, Oct 15): the real-money account halts once it's worth $700 or less.

Only a live bot on prod has it: Bot.floor is HALT_FLOOR when the bot is live and its Kalshi client's env is "prod",
else 0. Dry runs, paper accounts and demo keep $100 play books and share state/halt.json with the live bot, so a $700
line there would halt real trading; they get no floor. check_halts takes the floor as an argument (0, its default, is
none) and checks it right after the half-the-start line, so when both are crossed the half-the-start reason is the one
given. The --rebase message names the line the new books halt at: the larger of half the cash and, on prod, $700.

Nothing here touches the network or an account.

    python -m pytest tests/test_halt_floor.py -q
"""
import pytest

from kalshi_bot import bot
from kalshi_bot.kalshi import Kalshi
from test_bot import ENTRY, W, FakeKalshi, decisions, env, fake_bet, run  # noqa: F401 (env is a fixture)
from test_cli import cli, ledger, out  # noqa: F401 (cli is a fixture)

NOW = W + 3000
OLD = W - 3 * 86400   # a loss this old is past the 24-hour drop and the one-window count: only the lines can fire
REASON = "the account is down to ${:.2f}, at or under the $700 stop"


class Prod(FakeKalshi):
    env = "prod"


class Demo(FakeKalshi):
    env = "demo"


def worth(db, dollars, start=1000.0):
    """Books that started at `start` and are worth `dollars` now, after one loss settled three days ago."""
    bot.set_start(db, start)
    if dollars != start:
        fake_bet(db, 0, OLD, False, dollars - start, settled=OLD + 900)
    db.commit()
    assert bot.bankroll(db) == pytest.approx(dollars)
    return db


def check(db, now=NOW, **kw):
    bot.check_halts(db, now, True, True, **kw)
    return bot.halt_info()


# ------------------------------------------------------------------ the line itself
def test_the_stop_is_700_dollars():
    assert bot.HALT_FLOOR == 700.0


@pytest.mark.parametrize("dollars, halts", [
    (700.00, True),     # exactly $700: at the stop
    (699.99, True),
    (650.00, True),
    (700.01, False),    # a cent over it: trading on
    (1000.00, False),
])
def test_it_halts_at_700_dollars_or_less_and_not_a_cent_over(env, dollars, halts):
    h = check(worth(env, dollars), floor=bot.HALT_FLOOR)
    if halts:
        assert h["reason"] == REASON.format(dollars) and h["by"] == "auto"
    else:
        assert h is None


def test_the_reason_reads_as_the_user_will_see_it(env):
    assert check(worth(env, 700.0), floor=bot.HALT_FLOOR)["reason"] == "the account is down to $700.00, at or under the $700 stop"


@pytest.mark.parametrize("kw", [{}, {"floor": 0.0}, {"floor": 0}])
def test_no_floor_means_no_stop(env, kw):
    """check_halts' default floor, 0, is none: $650 of a $1,000 start is over half of it, so nothing halts."""
    assert check(worth(env, 650.0), **kw) is None


def test_the_half_the_start_line_is_checked_first(env):
    """From $1,400 both lines are $700: the half-the-start reason is the one given."""
    h = check(worth(env, 700.0, start=1400.0), floor=bot.HALT_FLOOR)
    assert h["reason"] == "the account is down to $700.00, half of $1400.00 or less"


def test_a_halt_already_in_force_is_left_as_it_is(env):
    bot.set_halt(NOW - 60, "by hand", "you")
    assert check(worth(env, 650.0), floor=bot.HALT_FLOOR)["reason"] == "by hand"


def test_a_resume_doesnt_move_the_stop(env):
    """A resume moves the half-the-start line down to half of what the account is worth then, but $700 stays $700:
    at $700 or less the next check halts again. Only money in (and --rebase) takes it back over the line."""
    worth(env, 690.0)
    assert check(env, floor=bot.HALT_FLOOR)["reason"] == REASON.format(690.0)
    bot.clear_halt(NOW + 10, [env])
    assert check(env, NOW + 20) is None                                      # without the floor, the resume holds
    assert check(env, NOW + 30, floor=bot.HALT_FLOOR)["reason"] == REASON.format(690.0)


# ------------------------------------------------------------------ which bots have it
@pytest.mark.parametrize("k, live, halts, floor", [
    (Prod(), True, True, 700.0),           # live prod: real money
    (Demo(), True, True, 0.0),             # live demo: play money
    (Prod(), False, True, 0.0),            # a dry run, even pointed at prod
    (Prod(), False, False, 0.0),           # a paper account, even pointed at prod
    (Demo(), False, True, 0.0),
    (FakeKalshi(), True, True, 0.0),       # a client that names no environment
])
def test_only_a_live_prod_bot_has_the_stop(env, k, live, halts, floor):
    assert bot.Bot(k, env, live, halts=halts).floor == floor


def test_the_real_client_names_its_environment():
    """Bot reads the client's env attribute: the real Kalshi client must have it, or prod would run with no stop."""
    assert bot.Bot(Kalshi("prod"), None, True).floor == bot.HALT_FLOOR
    assert bot.Bot(Kalshi("demo"), None, True).floor == 0.0
    assert bot.Bot(Kalshi("prod"), None, False).floor == 0.0


# ------------------------------------------------------------------ through the step loop
def test_a_live_prod_bot_at_700_dollars_halts_before_its_orders(env):
    fake = Prod()
    b = run(worth(env, 700.0), fake, live=True)
    assert b.floor == bot.HALT_FLOOR
    assert bot.halt_info()["reason"] == REASON.format(700.0)
    assert fake.orders == [] and decisions(env)["KXBTC15M-A"][0] == decisions(env)["KXGOLD15M-A"][0] == "halted"


def test_a_live_prod_bot_halts_outside_the_entry_minute_too(env):
    """The halts are checked every loop: minute 2 places nothing, but the stop still fires."""
    fake = Prod()
    run(worth(env, 650.0), fake, live=True, now=W + 100)
    assert bot.halt_info()["reason"] == REASON.format(650.0) and fake.orders == []


def test_a_live_prod_bot_a_cent_over_the_stop_trades(env):
    fake = Prod()
    run(worth(env, 700.01), fake, live=True)
    assert bot.halt_info() is None and [o["ticker"] for o in fake.orders] == ["KXBTC15M-A", "KXGOLD15M-A"]


@pytest.mark.parametrize("dollars", [100.0, 650.0])   # a fresh $100 play book, and one that fell under $700
@pytest.mark.parametrize("make, live, halts, sends", [
    (Demo, True, True, True),       # live on demo: real orders to the demo exchange
    (Prod, False, True, False),     # a dry run on prod
    (Demo, False, True, False),     # a dry run on demo
    (Prod, False, False, False),    # a paper account on prod
])
def test_a_play_money_account_under_700_dollars_never_halts_from_the_floor(env, dollars, make, live, halts, sends):
    """Its halt would be the live bot's: they share state/halt.json."""
    fake = make()
    b = bot.Bot(fake, worth(env, dollars, start=dollars), live, halts=halts)
    b.step(ENTRY)
    assert b.floor == 0.0 and bot.halt_info() is None
    assert decisions(env)["KXBTC15M-A"][0] == decisions(env)["KXGOLD15M-A"][0] == "bet"
    assert len(fake.orders) == (2 if sends else 0)


# ------------------------------------------------------------------ --rebase says where the new books halt
@pytest.mark.parametrize("cash, line", [
    ("1000.0000", "$700.00"),    # half of it is $500: the $700 stop is the higher line
    ("1399.9800", "$700.00"),    # half is $699.99
    ("1400.0000", "$700.00"),    # half is $700: the same line
    ("2000.0000", "$1000.00"),   # half is $1,000: over the stop
])
def test_a_prod_rebase_names_the_higher_of_half_the_cash_and_the_stop(cli, capsys, cash, line):
    ledger(cli, name="live-prod")
    cli.fake.crypto_cash = cash
    bot.main(["--rebase", "--env", "prod", "--yes"])
    avail = float(cash)
    assert (f"rebased: $84.92 -> ${avail:.2f}, history kept · bets about ${bot.stake_for(avail, 1):.2f} · halts if it"
            f" falls 35% within 24 hours or reaches {line}") in out(capsys)


def test_a_demo_rebase_names_half_the_cash_however_low(cli, capsys):
    ledger(cli)
    cli.fake.crypto_cash = "1000.0000"
    bot.main(["--rebase", "--yes"])
    assert ("rebased: $84.92 -> $1000.00, history kept · bets about $15.00 · halts if it falls 35% within 24 hours or"
            " reaches $500.00") in out(capsys)
