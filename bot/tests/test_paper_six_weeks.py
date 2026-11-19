"""The +1¢ limit on paper runs 6 weeks.

On Oct 15, 2026 the live strategy was set to run unchanged for 6 weeks (the clock restarted at the Ohio server's
go-live, Oct 16, 05:14 UTC), and the paper +1¢ was extended to match. The paper +1¢ (the shadow table's 'limitup' rows, measured by
the bot on every live order) was to give its verdict at 1,000 orders, about to be reached. Now its verdict waits for a
date, dashboard.SHADOW_UNTIL, Nov 27, 2026, 08:00 UTC (6 weeks from the go-live): until then it's "too early" however many orders are measured,
and after it the 95% range decides as before ("thin" when there's no range to read). The shadow block and its verdict
carry "until" in place of "target"; the live +1¢ card (off) keeps its 1,000-order target. The Live Research page shows
the paper card's run by the date: "N orders · until Nov 27" in its header and a bar of the days gone, with no
"of 1,000"; a reply from an older server (with "target") still draws as before. The bot doesn't change.

Server tests build ledgers as test_shadow_api.py does; page tests draw replies in node as test_shadow_page.py does.
The node tests skip themselves without node.

    python -m pytest tests/test_paper_six_weeks.py -q
"""
import datetime as dt
import re
import time
import zoneinfo

import pytest

from kalshi_bot.web import dashboard
from test_dashboard_more import home  # noqa: F401  (a fixture)
from test_live_research_api import W1, W2, W3, W4
from test_shadow_api import measured, paid, paper_ledger, shadow_of
from test_shadow_page import NOW, SHADOW, TODAY, drawn, needs_node, paper, summary, text

UNTIL = 1795766400   # Nov 27, 2026, 08:00 UTC: 6 weeks from the Ohio server's go-live (Oct 16, 05:14 UTC)
LA = zoneinfo.ZoneInfo("America/Los_Angeles")
TOO_EARLY = "Too early to tell: {n} orders measured on paper so far. The verdict comes on Nov 27, after 6 weeks."
THIN = "Not enough extra contracts to tell yet: {n} orders measured on paper."
HELPING = "On paper the extra cent pays: the extra contracts made money, and their 95% range is above zero."
NO_DIFFERENCE = "No clear difference on paper: the extra contracts' 95% range includes zero."


def ahead(monkeypatch):
    """Before the date, whenever the tests run."""
    monkeypatch.setattr(dashboard, "SHADOW_UNTIL", time.time() + 86400)


def past(monkeypatch):
    monkeypatch.setattr(dashboard, "SHADOW_UNTIL", time.time() - 1)


def helping_ledger(home):
    db = paper_ledger(home)
    paid(db, W1 + 482, "KXBTC15M-1", W1, 5, "yes")
    paid(db, W2 + 482, "KXBTC15M-2", W2, 5, "yes")
    paid(db, W3 + 482, "KXBTC15M-3", W3, 4, "no", seen=0.96, side="no")
    db.commit()
    db.close()


# ------------------------------------------------------------------ the server
def test_the_paper_cent_runs_until_nov_27():
    """6 weeks from the Ohio server's go-live (Oct 16, 2026, 05:13:55 UTC), to the Pacific-time midnight after."""
    assert dashboard.SHADOW_UNTIL == UNTIL
    assert dt.datetime.fromtimestamp(UNTIL, LA) == dt.datetime(2026, 11, 27, tzinfo=LA)
    go_live = dt.datetime(2026, 10, 15, 22, 13, 55, tzinfo=LA)
    assert dt.timedelta(0) < dt.datetime.fromtimestamp(UNTIL, LA) - (go_live + dt.timedelta(weeks=6)) < dt.timedelta(hours=2)
    assert dashboard.LIVE_RESEARCH_TARGET == 1000                       # the live card's target is unchanged


def test_the_shadow_block_carries_the_date_not_an_order_target(home, monkeypatch):
    ahead(monkeypatch)
    measured(home).close()
    s = shadow_of()
    assert s["until"] == dashboard.SHADOW_UNTIL and "target" not in s
    assert s["verdict"]["until"] == dashboard.SHADOW_UNTIL and "target" not in s["verdict"]


def test_before_the_date_its_too_early_however_many_orders(home, monkeypatch):
    ahead(monkeypatch)
    monkeypatch.setattr(dashboard, "LIVE_RESEARCH_TARGET", 1)        # the old order target no longer decides
    helping_ledger(home)                                              # a range wholly above zero: still too early
    v = shadow_of()["verdict"]
    assert v == {"state": "too-early", "text": TOO_EARLY.format(n=3), "orders": 3, "until": dashboard.SHADOW_UNTIL}


def test_after_the_date_the_range_decides(home, monkeypatch):
    past(monkeypatch)
    helping_ledger(home)
    v = shadow_of()["verdict"]
    assert v["state"] == "helping" and v["text"] == HELPING and v["orders"] == 3


def test_after_the_date_a_range_across_zero_is_no_difference(home, monkeypatch):
    past(monkeypatch)
    measured(home).close()
    v = shadow_of()["verdict"]
    assert v["state"] == "no-difference" and v["text"] == NO_DIFFERENCE and v["orders"] == 8


def test_after_the_date_without_a_range_its_thin(home, monkeypatch):
    past(monkeypatch)
    db = paper_ledger(home)
    paid(db, W1 + 482, "KXBTC15M-1", W1, 5, "yes")
    paid(db, W2 + 482, "KXBTC15M-2", W2, 5, None)                    # open: one settled window, no standard error
    db.commit()
    db.close()
    v = shadow_of()["verdict"]
    assert v == {"state": "thin", "text": THIN.format(n=2), "orders": 2, "until": dashboard.SHADOW_UNTIL}


def test_before_anything_is_measured_its_still_waiting(home, monkeypatch):
    ahead(monkeypatch)
    paper_ledger(home).close()
    v = shadow_of()["verdict"]
    assert v["state"] == "waiting" and v["until"] == dashboard.SHADOW_UNTIL


def test_the_live_cards_verdict_keeps_its_order_target(home, monkeypatch):
    ahead(monkeypatch)
    measured(home).close()
    r = dashboard.live_research("live-prod")
    assert r["target"] == 1000 and r["verdict"]["target"] == 1000 and r["verdict"]["state"] == "waiting"   # LIMIT_UP is on


# ------------------------------------------------------------------ the page
P_UNTIL = NOW + 30 * 86400
NEW = {k: v for k, v in SHADOW.items() if k != "target"}
NEW = {**NEW, "until": P_UNTIL, "verdict": {"state": "too-early", "text": TOO_EARLY.format(n=412).replace("Nov 27", "the day"),
                                             "orders": 412, "until": P_UNTIL}}
REPLY = {**TODAY, "shadow": NEW}


def day(t):
    d = dt.datetime.fromtimestamp(t, LA)
    return f"{d:%b} {d.day}"


@needs_node
def test_the_card_runs_by_the_date_not_an_order_count():
    c = paper(drawn(REPLY)[0])
    s = text(summary(c))
    assert day(P_UNTIL) in s, s                                        # "until Dec 10"-style: the day it ends
    assert not re.search(r"of\s*1,?000", s), s                         # no order target any more
    assert re.search(r"412\s+orders", s), s
    assert "lr-bar" in summary(c)


@needs_node
def test_the_bar_is_the_share_of_the_run_gone():
    started = NEW["started"]
    gone = (NOW - started) / (P_UNTIL - started)
    c = summary(paper(drawn(REPLY)[0]))
    widths = [float(w) for w in re.findall(r'class="lr-bar"[^>]*>\s*<i style="width:([\d.]+)%"', c)]
    assert widths and abs(widths[0] - gone * 100) < 0.2, (widths, gone * 100)


@needs_node
def test_the_header_says_how_many_orders_and_until_when():
    c = paper(drawn(REPLY)[0])
    head = re.search(r'<span class="lr-prog">(.*?)</span>', c, re.S)
    assert head and "412 orders" in text(head.group(1)) and day(P_UNTIL) in text(head.group(1)), head and head.group(1)


@needs_node
def test_the_server_words_its_verdict_and_thin_has_a_chip():
    thin = {**NEW, "verdict": {"state": "thin", "text": THIN.format(n=412), "orders": 412, "until": P_UNTIL}}
    c = paper(drawn({**TODAY, "shadow": thin})[0])
    assert THIN.format(n=412) in text(c) and "Not enough to tell" in text(c)


@needs_node
def test_an_older_servers_order_target_still_draws_as_before():
    c = text(summary(paper(drawn(TODAY)[0])))
    assert re.search(r"412\s*of\s*1,?000", c), c
