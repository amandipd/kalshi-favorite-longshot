"""Two cleanups: Brent is energy, and series that have never launched are not asked for every window.

**Brent.** `group_of` matched WTI, NATGAS and OIL but not BRENT, so Kalshi's KXBRENT15M (listed Oct 21, 2026)
fell into the `commodities` catch-all and was skipped by accident rather than on purpose. The label is now
right -- but labelling it energy puts it in EDGE_GROUPS, which would start trading it. It had three bets'
worth of evidence under the live rule, and adding a market mid-test would have changed the rule being tested, so it sits
in NOT_TRADED instead: the label is correct, the decision is explicit, and the bets placed are unchanged.

**Dead series.** Not done, on purpose. Filtering out the three series Kalshi lists that have never opened a
market was tried and backed out -- see the note beside NOT_TRADED in bot.py. The obvious check marks every
metals and energy series dead outside their trading hours, and 47 tests in this suite depend on the old
behaviour, which is a lot of churn for one round of listing calls. So the verdict is discarded unless something came back live, and a series whose check
errors stays in.

    python -m pytest tests/test_series_filter.py -q
"""
from kalshi_bot import bot


# ------------------------------------------------------------------ Brent is energy


def test_brent_is_energy_not_the_commodities_catch_all():
    assert bot.group_of("KXBRENT15M", "Commodities") == "energy"
    assert bot.group_of("KXWTI15M", "Commodities") == "energy", "the ones that already worked still do"
    assert bot.group_of("KXNATGAS15M", "Commodities") == "energy"


def test_the_other_group_labels_are_untouched():
    for ticker, cat, want in (("KXGOLD15M", "Commodities", "metals"), ("KXBTC15M", "Crypto", "crypto"),
                              ("KXCRYPTOLEAD15M", "Crypto", "coin race"), ("KXEURUSD15M", "Financials", "fx"),
                              ("KX10YRRATE15M", "Financials", "rates"), ("KXINX15M", "Financials", "stock index")):
        assert bot.group_of(ticker, cat) == want, ticker


def test_brent_is_in_the_traded_groups_but_deliberately_not_traded():
    """The whole point of the fix: the label is right and the exclusion is visible, so nobody re-finds this
    as a bug. Energy is traded, Brent is not, and it says so in one place."""
    assert bot.group_of("KXBRENT15M", "Commodities") in bot.EDGE_GROUPS
    assert "KXBRENT15M" in bot.NOT_TRADED
