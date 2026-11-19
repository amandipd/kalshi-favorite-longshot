"""bot.py runs the way you run it: as scripts, from a throwaway copy of the code so they can
never reach the real state/ folder, .env or key. Nothing here touches the network.

    python -m pytest tests/test_scripts.py -q
"""
import argparse
import os
import re
import runpy
import socket
import subprocess
import sys

import pytest

from kalshi_bot import bot, kalshi
from layout import BOT, copy_code


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def copy(tmp_path, monkeypatch):
    """The copy's one-bot lock is a free port of its own, so its bot runs even while the live bot holds the real one
    (test_one_bot.py checks the line it rewrites is there)."""
    core = copy_code(tmp_path)
    with open(core, "rb") as fh:
        src = fh.read()
    with open(core, "wb") as fh:
        fh.write(re.sub(rb"^BOT_PORT = \d+", b"BOT_PORT = %d" % free_port(), src, count=1, flags=re.M))
    for k in [k for k in os.environ if k.startswith("KALSHI_")]:
        monkeypatch.delenv(k)
    return tmp_path


def run(copy, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("KALSHI_")}
    env["PYTHONIOENCODING"] = "utf-8"
    p = subprocess.run([sys.executable, str(copy / "bot.py"), *args], cwd=copy, env=env, capture_output=True,
                       text=True, encoding="utf-8", timeout=60)
    return p.returncode, p.stdout, p.stderr


def test_the_kill_switch_works_across_separate_processes(copy):
    """--halt in one terminal is seen by --status and --resume in others, through state/halt.json."""
    assert run(copy, "--status")[1].splitlines()[0] == "not halted"
    code, out, _ = run(copy, "--halt", "stepping away")
    assert code == 0 and "HALTED (you): stepping away" in out
    assert os.path.exists(copy / "state" / "halt.json")
    assert "HALTED since" in run(copy, "--status")[1] and "stepping away" in run(copy, "--status")[1]
    code, out, _ = run(copy, "--resume")
    assert code == 0 and "resumed (was halted since" in out and "not halted" in out
    assert not os.path.exists(copy / "state" / "halt.json")
    assert "not halted" in run(copy, "--status")[1]


def test_an_empty_reason_still_halts_from_the_shell(copy):
    code, out, _ = run(copy, "--halt", "")
    assert code == 0 and "HALTED" in out and "stopped by hand" in out
    assert os.path.exists(copy / "state" / "halt.json") and not os.path.exists(copy / "state" / "dry-demo.db")  # it never started a bot


def test_a_live_run_without_a_key_stops_with_a_clear_message(copy):
    for flag in ("--live", "--check", "--fund-crypto"):
        code, _, err = run(copy, flag)
        assert code == 1 and "needs KALSHI_API_KEY_ID and KALSHI_PRIVATE_KEY_PATH in .env" in err, flag
    assert not os.path.exists(copy / "state")  # and nothing was created


def test_an_unknown_flag_or_environment_is_an_error(copy):
    assert run(copy, "--nonsense")[0] == 2
    code, _, err = run(copy, "--env", "staging")
    assert code == 2 and "invalid choice" in err


def test_help_describes_every_mode(copy):
    code, out, _ = run(copy, "--help")
    assert code == 0
    for flag in ("--live", "--check", "--halt", "--resume", "--status", "--fund-crypto", "--env", "--yes"):
        assert flag in out
    assert "--once" not in out  # that one is for tests


def test_ctrl_c_stops_the_bot_politely(copy, monkeypatch, capsys):
    monkeypatch.setattr(kalshi.Kalshi, "get", lambda self, *a, **k: None)      # Kalshi unreachable: no network
    monkeypatch.setattr("time.sleep", lambda s: (_ for _ in ()).throw(KeyboardInterrupt))
    monkeypatch.setattr("sys.argv", ["bot.py"])
    runpy.run_path(str(copy / "kalshi_bot" / "bot.py"), run_name="__main__")   # the copy's own: returns, not raises
    out = capsys.readouterr().out
    assert out.startswith("dry run on demo") and out.rstrip().endswith("stopped")
    assert os.path.exists(copy / "state" / "dry-demo.db")


@pytest.mark.parametrize("script", ["the module", "the front door"])
def test_ctrl_c_is_caught_in_bot_py_itself(monkeypatch, capsys, script):
    """The same handler, run from the real kalshi_bot/bot.py so coverage sees it, and from the bot.py beside the package
    that starts it. It's interrupted while reading the command line, before it can touch state/, .env or a key."""
    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", lambda self, *a, **k: (_ for _ in ()).throw(KeyboardInterrupt))
    runpy.run_path(bot.__file__ if script == "the module" else os.path.join(BOT, "bot.py"), run_name="__main__")
    assert capsys.readouterr().out == "stopped\n"
