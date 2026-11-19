"""The Fed decision blackouts: each one 2:00-3:30 pm ET on a decision day, whatever the clocks say, and the list
reaching at least 60 days ahead. Past its end the bot trades straight through a Fed decision, so the last test is a
reminder, on the real clock, that fails in time to add the next year's dates
(federalreserve.gov/monetarypolicy/fomccalendars.htm).

    python -m pytest tests/test_blackouts.py -q
"""
import time
from datetime import datetime

from kalshi_bot import bot


def test_every_blackout_is_2_to_3_30_pm_et_on_a_wednesday():
    """Summer and winter alike: 18:00 UTC from March to early November, 19:00 UTC in winter."""
    for start, end, what in bot.BLACKOUTS:
        a, b = (datetime.fromtimestamp(bot.ts(x), bot.ET) for x in (start, end))
        assert (what, f"{a:%a %H:%M}", f"{b:%a %H:%M}", a.date()) == ("Fed decision", "Wed 14:00", "Wed 15:30", b.date()), start


def test_the_list_is_in_order_with_no_repeats():
    starts = [bot.ts(a) for a, _, _ in bot.BLACKOUTS]
    assert starts == sorted(set(starts))


def test_the_blackouts_reach_at_least_60_days_ahead():
    """Once this fails, add the next year's Fed decisions to BLACKOUTS in bot.py."""
    left = (bot.ts(bot.BLACKOUTS[-1][1]) - time.time()) / 86400
    assert left >= 60, f"the last Fed blackout on the list is {left:.0f} days away: add the next year's"
