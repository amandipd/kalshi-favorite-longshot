"""The Live tab's "restart pending" note: the Oct 12 changes (the paper +1¢, the Live Research tab) start only after the
dashboard and the bot are restarted, so the page shows a reminder until they are.

The server says whether the real-money ledger is still the bot's old one (restartBot: it has no shadow table yet, which
the new bot.py adds when it starts). A dashboard that hasn't been restarted doesn't send restartBot at all, so the page
asks for both restarts; a restarted one asks for the bot alone while the ledger is old; then the note goes away by itself.
restartNote() is cut out of dashboard.html and run in node; the tests skip themselves without node.

    python -m pytest tests/test_restart_note.py -q
"""
import json
import os
import re
import shutil
import subprocess

import pytest

from kalshi_bot.web import dashboard
from test_dashboard_more import home, mode_db  # noqa: F401 (home is a fixture)

HTML = open(dashboard.PAGE, encoding="utf-8").read()
NODE = shutil.which("node")
MINUTES = ":08–:09, :23–:24, :38–:39 or :53–:54"


def piece(src, pattern):
    m = re.search(pattern, src, re.M | re.S)
    assert m, f"dashboard.html no longer has {pattern!r}"
    return m.group(0)


def note(d):
    """restartNote(d) run for real in node."""
    if not NODE:
        pytest.skip("node isn't installed")
    js = "\n".join([piece(HTML, r"^const esc = [^\n]*$"), piece(HTML, r"^function restartNote\(d\) \{.*?^\}$"),
                    "process.stdout.write(restartNote(JSON.parse(require('fs').readFileSync(0, 'utf8'))));"])
    r = subprocess.run([NODE, "-e", js], input=json.dumps(d), capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert r.returncode == 0, r.stderr
    return r.stdout


# ------------------------------------------------------------------ the server


def test_an_old_ledger_needs_the_bot_restarted(home):
    db = mode_db(home, "live-prod")
    assert dashboard.state("live-prod")["restartBot"] is False         # bot.connect() made the shadow table: restarted
    db.execute("DROP TABLE shadow")                                     # the ledger as the bot running before Oct 12 left it
    db.commit()
    assert dashboard.state("live-prod")["restartBot"] is True


def test_only_the_real_money_ledger_asks_for_a_restart(home):
    db = mode_db(home, "live-demo")
    db.execute("DROP TABLE shadow")
    db.commit()
    assert dashboard.state("live-demo")["restartBot"] is False


# ------------------------------------------------------------------ the page


def test_a_dashboard_not_yet_restarted_asks_for_both_restarts():
    text = note({"mode": "live-prod"})                                  # the old server sends no restartBot
    assert "Restart pending" in text and "python dashboard.py" in text and "python bot.py --live --env prod" in text
    assert MINUTES in text and "goes away by itself" in text
    assert text.index("python dashboard.py") < text.index("python bot.py")   # the dashboard first, then the bot
    assert 'class="note warn"' in text and 'role="status"' in text


def test_a_restarted_dashboard_asks_only_for_the_bot():
    text = note({"mode": "live-prod", "restartBot": True})
    assert "Restart the bot" in text and "python bot.py --live --env prod" in text and MINUTES in text
    assert "python dashboard.py" not in text and "goes away by itself" in text


@pytest.mark.parametrize("d", [{"mode": "live-prod", "restartBot": False}, {"mode": "live-demo"},
                               {"mode": "live-demo", "restartBot": True}, {"mode": "dry"}])
def test_no_note_once_both_have_restarted_or_on_another_account(d):
    assert note(d) == ""


def test_the_live_tab_shows_the_note_among_its_banners():
    render = piece(HTML, r"^function render\(\) \{.*?^\}$")
    assert "restartNote(d)" in render
    assert render.index("restartNote(d)") < render.index('patch("banners"')
