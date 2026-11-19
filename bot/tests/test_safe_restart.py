"""When it is safe to restart the live bot, and when it is not.

The usual rule is to avoid :08-:09, :23-:24, :38-:39 and :53-:54 past the hour. Those are the entry minutes.
Written as minutes that rule is easy to check and easy to get wrong: on Oct 26, 2026 a deploy restarted the
bot at :37:52, which passed a minute-only check (:37 is not :38) and was eight seconds before the entry mark.
The window survived only because the new process started fast enough to catch it.

So the check is in seconds into the 15-minute window, not minutes, and it starts before the prep rather than
at the mark:

    450   a fast window's prep reads the window's prices (fast_entry.PREP)
    480   the mark, where the orders go out (bot.MINUTE * 60)
    525   the last moment an entry may still happen (+ bot.GRACE)
    600   the end of that rule's own window, minute 9

A restarting bot has to connect to Kalshi, read its catalog and be ready BEFORE the prep, so the unsafe band
opens STARTUP seconds earlier than the prep. It closes at 600 to cover that rule's minutes.

    python -m pytest tests/test_safe_restart.py -q
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "deploy"))

from kalshi_bot import bot                     # noqa: E402  (the live timings, to prove the copies here can't drift)
from kalshi_bot import fast_entry              # noqa: E402
import safe_restart            # noqa: E402

WINDOW = 900


def at(second, window=0):
    """An epoch time `second` seconds into a 15-minute window."""
    return window * WINDOW + second


# ------------------------------------------------------------------ the numbers must not drift from the bot's
def test_the_timings_are_the_bots_own():
    assert safe_restart.WINDOW == 900
    assert safe_restart.PREP == fast_entry.PREP == 450
    assert safe_restart.MARK == bot.MINUTE * 60 == 480
    assert safe_restart.GRACE == bot.GRACE == 45
    assert safe_restart.UNSAFE_FROM == safe_restart.PREP - safe_restart.STARTUP
    assert safe_restart.UNSAFE_TO >= safe_restart.MARK + safe_restart.GRACE   # past the last entry


# ------------------------------------------------------------------ the restart that prompted this
def test_the_oct_26_restart_would_have_been_refused():
    """09:37:52 PDT: 472 seconds into the window, 8 seconds before the mark. A minute-only check let it through."""
    assert not safe_restart.safe(at(472))
    assert safe_restart.into_window(at(472)) == 472


def test_a_minute_only_check_is_what_went_wrong():
    """Minute :37 is not one of the four the rule names, yet most of it is unsafe."""
    minute_37 = [s for s in range(37 * 60, 38 * 60) if not safe_restart.safe(at(s % WINDOW))]
    assert minute_37, "the whole of minute :37 looked safe, which is the bug"


# ------------------------------------------------------------------ the band itself
@pytest.mark.parametrize("second", [450, 460, 472, 480, 500, 525, 540, 599, 600])
def test_the_prep_the_mark_the_grace_and_minute_nine_are_all_unsafe(second):
    assert not safe_restart.safe(at(second))


@pytest.mark.parametrize("second", [0, 1, 100, 300, 389, 601, 700, 899])
def test_the_quiet_stretches_are_safe(second):
    assert safe_restart.safe(at(second))


def test_the_band_opens_a_full_startup_before_the_prep():
    assert not safe_restart.safe(at(safe_restart.PREP - safe_restart.STARTUP))
    assert safe_restart.safe(at(safe_restart.PREP - safe_restart.STARTUP - 1))


def test_the_unsafe_band_is_exactly_what_it_says():
    unsafe = {s for s in range(WINDOW) if not safe_restart.safe(at(s))}
    assert unsafe == set(range(safe_restart.UNSAFE_FROM, safe_restart.UNSAFE_TO + 1))
    assert len(unsafe) < WINDOW / 2, "more than half the window unsafe would make deploys painful"


def test_every_minute_the_ops_card_names_is_covered():
    """:08-:09, :23-:24, :38-:39, :53-:54 past the hour, every second of them."""
    for minute in (8, 9, 23, 24, 38, 39, 53, 54):
        for second in range(60):
            t = minute * 60 + second
            assert not safe_restart.safe(at(t % WINDOW)), (minute, second)


def test_it_holds_in_every_window_of_the_hour():
    for window in range(4):
        assert not safe_restart.safe(at(480, window))
        assert safe_restart.safe(at(60, window))


# ------------------------------------------------------------------ waiting
def test_it_waits_no_time_at_all_when_it_is_already_safe():
    assert safe_restart.wait_for(at(100)) == 0


def test_it_waits_just_past_the_band():
    assert safe_restart.wait_for(at(400)) == safe_restart.UNSAFE_TO + 1 - 400
    assert safe_restart.wait_for(at(472)) == safe_restart.UNSAFE_TO + 1 - 472
    for second in range(safe_restart.UNSAFE_FROM, safe_restart.UNSAFE_TO + 1):
        assert safe_restart.safe(at(second) + safe_restart.wait_for(at(second))), second


def test_the_longest_wait_is_the_whole_band():
    waits = [safe_restart.wait_for(at(s)) for s in range(WINDOW)]
    assert max(waits) == safe_restart.UNSAFE_TO + 1 - safe_restart.UNSAFE_FROM
    assert min(waits) == 0


# ------------------------------------------------------------------ the command line
def test_check_says_yes_or_no_and_sets_the_exit_code(capsys):
    assert safe_restart.main(["--check", "--at", str(at(100))]) == 0
    assert "safe" in capsys.readouterr().out.lower()
    assert safe_restart.main(["--check", "--at", str(at(472))]) == 1
    out = capsys.readouterr().out.lower()
    assert "not safe" in out and "472" in out


def test_waiting_with_at_says_how_long_rather_than_sleeping(capsys):
    assert safe_restart.main(["--at", str(at(472)), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert str(safe_restart.UNSAFE_TO + 1 - 472) in out


def test_at_a_safe_moment_it_says_so_and_waits_for_nothing(capsys, monkeypatch):
    monkeypatch.setattr(safe_restart.time, "sleep", lambda s: pytest.fail("slept at a safe moment"))
    assert safe_restart.main(["--at", str(at(100))]) == 0
    assert "safe to restart now (100s into the window)" in capsys.readouterr().out


def test_inside_the_band_it_sleeps_until_just_past_it_then_says_so(capsys, monkeypatch):
    """The deploy's own run, no --at: it really waits, the whole wait, once."""
    clock = {"t": at(472, window=7)}
    slept = []

    def sleep(s):
        slept.append(s)
        clock["t"] += s
    monkeypatch.setattr(safe_restart.time, "time", lambda: clock["t"])
    monkeypatch.setattr(safe_restart.time, "sleep", sleep)
    assert safe_restart.main([]) == 0
    assert slept == [safe_restart.UNSAFE_TO + 1 - 472]
    out = capsys.readouterr().out
    assert f"waiting {slept[0]}s" in out and f"safe to restart now ({safe_restart.UNSAFE_TO + 1}s into the window)" in out
    assert safe_restart.safe(clock["t"])
