"""The safety net in conftest.py: no test can reach the state/ folder beside the code, where the live bot keeps its
ledger and reads its halt switch (a halt.json left there by a test stops real trading). Every test starts pointed at
a throwaway state folder, whether or not it sets one itself.

    python -m pytest tests/test_guard.py -q
"""
import os

from kalshi_bot import bot
import conftest
from kalshi_bot.web import dashboard
from kalshi_bot import notify
from layout import BOT

BESIDE_THE_CODE = os.path.join(BOT, "state")   # the bot/ folder's own state/, beside the package


def test_a_test_that_sets_no_state_folder_gets_a_throwaway_one():
    assert os.path.normcase(os.path.abspath(bot.STATE)) != os.path.normcase(BESIDE_THE_CODE)
    assert os.path.basename(bot.STATE) == "state"            # still named state: paths built from it read the same


def test_a_halt_from_a_test_that_forgot_lands_in_the_throwaway_folder():
    bot.set_halt(bot.ts("2026-10-10T18:00:00Z"), "a test that forgot to set bot.STATE", "you")
    assert os.path.exists(os.path.join(bot.STATE, "halt.json"))
    assert not os.path.exists(os.path.join(BESIDE_THE_CODE, "halt.json")) or conftest.REAL_HALT_AT_START


def test_each_test_gets_its_own():
    """Nothing one test leaves in its state folder reaches the next (the halt above is gone)."""
    assert bot.halt_info() is None and not os.path.exists(bot.STATE)


def test_the_dashboard_and_notifier_follow_it():
    assert notify.memory_path("live-prod").startswith(bot.STATE)
    assert dashboard.modes() == []


def test_the_real_folder_is_checked_at_the_end_of_the_run():
    """And the run fails if a halt.json appeared beside the code anyway (a test running the bot as a script there)."""
    assert conftest.REAL_STATE == os.path.normcase(BESIDE_THE_CODE)
