"""One bot at a time. On Oct 11 a second live bot was started while the hidden one still ran: both would have bought
the same markets with the same money and written to the same ledger, placing every bet twice. So a trading loop (a dry
run, --paper or --live) holds a localhost port while it runs, as the notifier does. A second one finds the port taken
and stops before it reads or writes anything that matters, and Windows frees the port the moment the first one's
process ends, however it ends, so a lock is never left behind to block a restart.

The commands that don't trade (--status, --halt, --resume, --check, --fund-crypto, --rebase) take no lock, so they
still work while the bot runs. Every test here points the lock at a port of its own (conftest.py points it at port 0,
which is always free), since the live bot holds the real one.
    python -m pytest tests/test_one_bot.py -q
"""
import os
import re
import socket
import subprocess
import sys
import types

import pytest

from kalshi_bot import bot, notify
from layout import copy_code
from test_bot import W, fake_bet
from test_cli import NOW, cli, db_at, exits, out  # noqa: F401 (cli is a fixture)
from test_notify import can_take, free_port

REFUSED = "another bot is already running"
STARTS = {"dry run": ["--once"], "paper": ["--paper", "--once"], "live on demo": ["--live", "--once"],
          "live on prod": ["--live", "--env", "prod", "--once"], "live on prod --yes": ["--live", "--env", "prod", "--yes", "--once"]}


def default(module, name):
    """A constant's value as written in the module's source: conftest.py and the tests patch the module's own."""
    m = re.search(rf"^{name} = (\d+)\b", open(module.__file__, encoding="utf-8").read(), re.M)
    assert m, f"{os.path.basename(module.__file__)} has no `{name} = <port>` line"
    return int(m.group(1))


@pytest.fixture
def taken(monkeypatch):
    """Another bot already running: a localhost port already bound, which bot.py is pointed at."""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    monkeypatch.setattr(bot, "BOT_PORT", s.getsockname()[1], raising=False)
    yield s.getsockname()[1]
    s.close()


@pytest.fixture
def port(monkeypatch):
    """A free port of this test's own for the lock, to see whether it's held."""
    p = free_port()
    monkeypatch.setattr(bot, "BOT_PORT", p, raising=False)
    return p


@pytest.fixture
def steps(monkeypatch):
    """Each loop step, run for real: `steps.seen` holds the times, and `steps.during` runs inside each one."""
    box = types.SimpleNamespace(seen=[], during=lambda: None)
    real = bot.Bot.step

    def step(self, now):
        box.seen.append(now)
        box.during()
        return real(self, now)
    monkeypatch.setattr(bot.Bot, "step", step)
    return box


def files(cli):
    return sorted(os.listdir(cli.dir))


# ------------------------------------------------------------------ the lock itself
def test_the_lock_is_a_localhost_port_of_its_own():
    p = default(bot, "BOT_PORT")
    assert 1024 <= p <= 65535
    assert p not in (default(notify, "NOTIFY_PORT"), 8080, 9000)      # not the notifier's, nor either dashboard's


def test_hold_port_binds_localhost_only_and_gives_none_when_the_port_is_taken():
    first = bot.hold_port(0)
    try:
        host, p = first.getsockname()
        assert host == "127.0.0.1"                                     # this PC only, never the network
        assert bot.hold_port(p) is None                                # a second holder is refused ...
        assert not can_take(p)                                         # ... and so is any other program
    finally:
        first.close()
    assert can_take(p)
    again = bot.hold_port(p)                                           # and once it's let go, it can be held again
    assert again is not None
    again.close()


def test_hold_port_never_sets_reuseaddr():
    """On Windows SO_REUSEADDR would let a second program bind the same port: then the lock would hold nothing."""
    s = bot.hold_port(0)
    try:
        assert s.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR) == 0
    finally:
        s.close()


def test_the_notifier_takes_its_lock_through_the_same_function(monkeypatch):
    held, sentinel = [], object()
    monkeypatch.setattr(bot, "hold_port", lambda p: (held.append(p), sentinel)[1], raising=False)
    monkeypatch.setattr(notify, "NOTIFY_PORT", 51234)
    assert notify.take_lock() is sentinel and held == [51234]


# ------------------------------------------------------------------ a second bot stops before it does anything
@pytest.mark.parametrize("argv", STARTS.values(), ids=STARTS.keys())
def test_a_second_bot_stops_at_once_and_says_why(cli, taken, steps, argv, capsys):
    msg = exits(argv)                                                  # (the cli fixture fails the test on any prompt)
    assert msg == (f"another bot is already running (it holds localhost port {taken}), so this one stops:"
                   " two would place every bet twice")
    assert files(cli) == []                                            # no ledger made
    assert steps.seen == [] and cli.fake.orders == []                  # no step run, no order placed
    assert not re.search(r"^(LIVE|paper|dry run) on ", out(capsys), re.M)   # not even its opening line


@pytest.mark.parametrize("name, argv", [("dry-demo", ["--once"]), ("paper-demo", ["--paper", "--once"]),
                                        ("live-demo", ["--live", "--once"])], ids=["dry run", "paper", "live"])
def test_a_second_bot_leaves_an_existing_ledger_exactly_as_it_was(cli, taken, steps, name, argv):
    db = db_at(cli, name)
    bot.set_start(db, 100.0)
    bot.set_meta(db, "heartbeat", NOW - 2)                             # the first bot, beating
    db.commit()
    db.close()
    cli.fake.crypto_cash = "250.0000"   # a live start re-reads its start from Kalshi until the first bet: not this one
    before = (cli.dir / f"{name}.db").read_bytes()
    assert REFUSED in exits(argv)
    assert (cli.dir / f"{name}.db").read_bytes() == before and files(cli) == [f"{name}.db"]   # no journal either
    after = db_at(cli, name)
    assert bot.get_meta(after, "start") == "100.0" and float(bot.get_meta(after, "heartbeat")) == NOW - 2


def test_a_second_bot_never_asks_you_to_type_live(cli, taken):
    cli.answers.append("LIVE")
    assert REFUSED in exits(["--live", "--env", "prod", "--once"])
    assert cli.answers == ["LIVE"]                                     # the prompt never came


# ------------------------------------------------------------------ what still works while the bot runs
def test_status_halt_and_resume_still_work_beside_a_running_bot(cli, taken, capsys):
    bot.set_start(db_at(cli, "live-demo"), 100.0)
    bot.main(["--status"])
    assert "not halted" in out(capsys)
    bot.main(["--halt", "from another window"])
    assert bot.halt_info()["reason"] == "from another window"
    bot.main(["--resume"])
    assert "resumed" in out(capsys) and bot.halt_info() is None


def test_check_fund_crypto_and_rebase_still_work_beside_a_running_bot(cli, taken, capsys):
    bot.main(["--check"])
    assert "connected to Kalshi demo" in out(capsys)
    cli.fake.crypto_cash = "50.0000"
    bot.main(["--fund-crypto", "10", "--yes"])
    assert cli.fake.transfers == [(10.0, 0, 2)]
    db = db_at(cli, "live-demo")
    bot.set_start(db, 40.0)
    db.commit()
    bot.main(["--rebase", "--yes"])
    assert "rebased: $40.00 -> $50.00" in out(capsys)
    assert not can_take(taken)                                         # and the first bot still holds its port


def test_the_key_check_still_comes_first(cli, taken):
    cli.fake.authed = False
    msg = exits(["--live", "--once"])
    assert "needs KALSHI_API_KEY_ID and KALSHI_PRIVATE_KEY_PATH" in msg and REFUSED not in msg
    cli.fake.authed, cli.fake.balance_result = True, None
    assert exits(["--live", "--once"]).startswith("couldn't read the demo account balance")


# ------------------------------------------------------------------ held while it runs, let go however it ends
@pytest.mark.parametrize("argv", [["--once"], ["--paper", "--once"], ["--live", "--once"]], ids=["dry run", "paper", "live"])
def test_the_port_is_held_while_the_loop_runs_and_let_go_after(cli, port, steps, argv):
    held = []
    steps.during = lambda: held.append(can_take(port))
    bot.main(argv)
    assert held == [False]                                             # taken while it ran ...
    assert can_take(port)                                              # ... and let go after its one step


def test_a_second_start_while_the_first_is_mid_step_is_refused(cli, port, steps):
    refused = []
    steps.during = lambda: refused.append(exits(["--once"])) if len(steps.seen) == 1 else None
    bot.main(["--once"])
    assert len(refused) == 1 and REFUSED in refused[0] and f"port {port}" in refused[0]
    assert len(steps.seen) == 1                                        # the second never stepped


# Each of these looks once while it's held (it must be), then once it has ended (it must be free).
def test_the_port_is_let_go_after_ctrl_c(cli, port, monkeypatch):
    held = []

    def ctrl_c(s):
        held.append(can_take(port))
        raise KeyboardInterrupt
    monkeypatch.setattr(bot, "time", types.SimpleNamespace(monotonic=lambda: 0.0, time=lambda: NOW, sleep=ctrl_c))
    with pytest.raises(KeyboardInterrupt):
        bot.main([])
    assert held == [False] and can_take(port)


def test_the_port_is_let_go_after_an_error_stops_a_real_account(cli, port, monkeypatch):
    held = []

    def broken(self, now):
        held.append(can_take(port))
        raise ValueError("odd reply")
    monkeypatch.setattr(bot.Bot, "step", broken)
    with pytest.raises(ValueError):
        bot.main(["--live", "--once"])
    assert held == [False] and can_take(port)


def test_the_port_is_let_go_when_a_paper_account_goes_broke(cli, port, monkeypatch, capsys):
    db = db_at(cli, "paper-demo")
    bot.set_start(db, 100.0)
    fake_bet(db, 0, W, False, -66.67, settled=W + 1)                   # $33.33 left: too little for a $1 bet
    db.commit()
    held, real = [], bot.broke
    monkeypatch.setattr(bot, "broke", lambda db: (held.append(can_take(port)), real(db))[1])
    bot.main(["--paper"])                                              # no --once: being broke is what ends it
    assert "broke:" in out(capsys)
    assert held == [False] and can_take(port)


def test_the_port_is_let_go_when_you_dont_type_live(cli, port, monkeypatch):
    held = []
    monkeypatch.setattr("builtins.input", lambda prompt="": (held.append(can_take(port)), "no")[1])
    assert exits(["--live", "--env", "prod"]) == "not started"
    assert held == [False] and can_take(port)                          # held from before it asked


def test_the_commands_that_dont_trade_never_hold_the_port(cli, monkeypatch):
    held = []
    monkeypatch.setattr(bot, "hold_port", lambda p: held.append(p), raising=False)
    db = db_at(cli, "live-demo")
    bot.set_start(db, 100.0)
    db.commit()
    for argv in (["--status"], ["--halt", "x"], ["--resume"], ["--check"], ["--fund-crypto", "--yes"], ["--rebase", "--yes"]):
        try:
            bot.main(argv)
        except SystemExit:
            pass                                                       # (--fund-crypto has nothing to move here)
    assert held == []


# ------------------------------------------------------------------ across real processes
def copy_with_port(tmp_path, p):
    core = copy_code(tmp_path)
    with open(core, "rb") as fh:
        src = fh.read()
    line = f"BOT_PORT = {default(bot, 'BOT_PORT')}".encode()
    assert src.count(line) == 1, "bot.py should set BOT_PORT on one line of its own"
    with open(core, "wb") as fh:
        fh.write(src.replace(line, f"BOT_PORT = {p}".encode()))
    return tmp_path


def test_a_bot_in_another_process_holding_the_port_stops_a_new_one(tmp_path):
    holder = subprocess.Popen([sys.executable, "-c", "import socket, sys, time\n"
                               "s = socket.socket(); s.bind(('127.0.0.1', 0)); print(s.getsockname()[1], flush=True)\n"
                               "time.sleep(120)"], stdout=subprocess.PIPE, text=True)
    try:
        p = int(holder.stdout.readline())
        copy = copy_with_port(tmp_path, p)
        env = {k: v for k, v in os.environ.items() if not k.startswith("KALSHI_")}
        env.update(PYTHONIOENCODING="utf-8", HTTPS_PROXY="http://127.0.0.1:9", HTTP_PROXY="http://127.0.0.1:9")  # no way out
        r = subprocess.run([sys.executable, str(copy / "bot.py")], cwd=copy, env=env, capture_output=True, text=True,
                           encoding="utf-8", timeout=30)
        assert r.returncode == 1
        assert f"another bot is already running (it holds localhost port {p})" in r.stderr
        assert r.stdout == "" and not os.path.exists(copy / "state" / "dry-demo.db")
    finally:
        holder.kill()
        holder.wait()
        holder.stdout.close()
    assert can_take(p)                                                 # its process gone, the port is free at once
