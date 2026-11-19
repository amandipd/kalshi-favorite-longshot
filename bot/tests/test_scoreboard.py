"""dashboard.html's scoreBlock(): the Live tab's scoreboard of winning against losing trades, run for real in node.

The hero shows it under the balance, whether the balance is shown or hidden (it holds no dollar figure): bets won and
lost, the win rate and the break-even rate. Both rates are per contract. The break-even (need) is the all-in cost per
settled contract, so the win rate beside it is the share of settled contracts that won (winShare); a per-bet rate
there made a winning bot look like a losing one (on Oct 10: 93.4% of bets against 95.0%, while 97.6% of contracts
won). It's cut out of the page with the helpers it uses and run on a state like /api/state's. Skipped without node.
"""

import json
import re
import shutil
import subprocess

import pytest

from kalshi_bot.web import dashboard

HTML = open(dashboard.PAGE, encoding="utf-8").read()
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(not NODE, reason="node isn't installed")


def piece(pattern):
    m = re.search(pattern, HTML, re.M | re.S)
    assert m, f"dashboard.html no longer has {pattern!r}"
    return m.group(0)


def score(wins, losses, **more):
    js = "\n".join([
        *(piece(rf"^const {name} = [^\n]*$") for name in ("esc", "pct", "winRate")),
        piece(r"^function scoreBlock\(d\) \{.*?^\}$"),
        "const d = JSON.parse(require('fs').readFileSync(0, 'utf8'));",
        "process.stdout.write(scoreBlock(d));",
    ])
    r = subprocess.run([NODE, "-e", js], input=json.dumps({"wins": wins, "losses": losses, **more}),
                       capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert r.returncode == 0, r.stderr
    return r.stdout


NOW_LIVE = {"winShare": 0.9759, "need": 0.9501}   # the live account on Oct 10: 137 bets won, 10 lost


@needs_node
def test_it_shows_the_wins_the_losses_the_win_rate_and_the_break_even():
    html = score(137, 10, **NOW_LIVE)
    assert re.search(r'<b class="up">137</b>\s*<span class="k">Won</span>', html)
    assert re.search(r'<b class="down">10</b>\s*<span class="k">Lost</span>', html)
    assert re.search(r'<b>97\.6%</b>\s*<span class="k">Win rate</span>', html)
    assert re.search(r'<b>95\.0%</b>\s*<span class="k">Break-even</span>', html)


@needs_node
def test_the_win_rate_counts_contracts_like_the_break_even_does():
    html = score(137, 10, **NOW_LIVE)
    assert "93.2%" not in html                                             # 137 of 147 bets: not comparable with need
    assert 'title="Share of contracts that won; break-even is per contract too"' in html


@needs_node
def test_the_bar_shows_the_win_rate_with_a_tick_at_the_break_even():
    html = score(137, 10, **NOW_LIVE)
    assert '<div class="sc-bar" aria-hidden="true"><i style="width:97.59%"></i><b class="sc-be" style="left:95.01%"></b></div>' in html


@needs_node
def test_it_says_the_record_in_words_for_screen_readers():
    assert 'aria-label="Record: 137 won, 10 lost; 97.6% of contracts won, break-even 95.0%"' in score(137, 10, **NOW_LIVE)


@needs_node
def test_a_state_from_before_the_restart_falls_back_to_bets():
    html = score(130, 10, need=0.95)                                       # no winShare yet: the per-bet rate, as before
    assert "<b>92.9%</b>" in html and 'style="width:92.86%"' in html


@needs_node
def test_with_no_break_even_there_is_no_tick():
    html = score(5, 0, winShare=1)
    assert "Break-even" not in html and "sc-be" not in html and "NaN" not in html


@needs_node
def test_no_losses_isnt_coloured_as_a_loss():
    html = score(5, 0, winShare=1, need=0.95)
    assert '<b class="up">5</b>' in html and "<b>0</b>" in html and 'class="down"' not in html
    assert "100.0%" in html and 'style="width:100%"' in html


@needs_node
def test_before_any_bet_settles_it_says_so():
    html = score(0, 0, winShare=None, need=None)
    assert "No bets settled yet" in html and "sc-bar" not in html and "NaN" not in html


def test_the_hero_shows_it_with_the_balance_shown_or_hidden():
    hero = piece(r'patch\("hero", `.*?`\);')
    # after the hidden/shown branches close, so both get it; it has no dollar figure to give the hidden balance away
    assert re.search(r"`\}\s*\$\{scoreBlock\(d\)\}`\);$", hero)
    assert "money(" not in piece(r"^function scoreBlock\(d\) \{.*?^\}$")


def test_the_other_win_rates_on_the_page_count_contracts_too():
    assert "of contracts won · needs ${pct(d.need)}" in HTML                # the Numbers row, beside the break-even
    assert "pct(d.wins / n)} won · needs" not in HTML
    # the Numbers row's one-line summary (the live-bot side panel, which also had one, is gone)
    assert "${d.wins}–${d.losses} · ${pct(winRate(d), 0)} won" in HTML


def test_it_has_its_styles_and_fits_a_phone():
    for sel in (".score {", ".sc b {", ".sc-bar {", ".sc-bar i {", ".sc-be {"):
        assert "\n" + sel in HTML, sel
    assert re.search(r"^\.score \{[^}]*grid-template-columns: repeat\(4, auto\)", HTML, re.M)
    assert re.search(r"^\.sc-bar \{[^}]*background: var\(--down\)", HTML, re.M)   # the losses' share
    assert re.search(r"^\.sc-bar i \{[^}]*background: var\(--up\)", HTML, re.M)    # the wins'
    assert re.search(r"\.score \{ gap: [^}]*\}", piece(r"^@media \(max-width: 560px\) \{.*?^\}$"))   # tighter on a phone
