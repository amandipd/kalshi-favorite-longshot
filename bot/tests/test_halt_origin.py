"""Who may press the dashboard's halt button: its own page, or a program on this computer (curl and the like send no
Origin). A page from anywhere else can't. Any web page can send a POST to localhost, and a browser names the page it
came from (its Origin), so without this check any site you had open could halt the bot. Halting is all the button
does, never resuming or trading, so this guards against a nuisance, not a loss.

    python -m pytest tests/test_halt_origin.py -q
"""
import json
import urllib.error
import urllib.request

import pytest

from kalshi_bot import bot
from test_dashboard_more import home, mode_db, serving  # noqa: F401 (home is a fixture)

REFUSED = {"error": "only the dashboard's own page can halt the bot"}


def post(base, origin=None, host=None):
    headers = {k: v for k, v in (("Origin", origin), ("Host", host)) if v is not None}
    try:
        with urllib.request.urlopen(urllib.request.Request(base + "/api/halt", method="POST", headers=headers), timeout=5) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def port(base):
    return base.rsplit(":", 1)[1]


@pytest.mark.parametrize("origin", ["https://example.com", "http://localhost.example.com", "null", "http://127.0.0.1:1",
                                    "file://"])
def test_a_page_from_anywhere_else_cant_halt_the_bot(home, origin):
    mode_db(home, "live-prod")
    with serving() as base:
        assert post(base, origin) == (403, REFUSED)
    assert bot.halt_info() is None


def test_a_site_that_points_its_own_name_at_this_computer_cant(home):
    """DNS rebinding: a site that resolves its name to 127.0.0.1, so its page and this server seem to share an address.
    Only a numeric address or localhost is this dashboard's own."""
    with serving() as base:
        p = port(base)
        assert post(base, f"http://evil.example:{p}", host=f"evil.example:{p}") == (403, REFUSED)
    assert bot.halt_info() is None


@pytest.mark.parametrize("name", ["127.0.0.1", "localhost", "[::1]", "192.168.1.20"])   # the last: --lan, from a phone
def test_its_own_page_can(home, name):
    mode_db(home, "live-prod")
    with serving() as base:
        p = port(base)
        status, body = post(base, f"http://{name}:{p}", host=f"{name}:{p}")
    assert status == 200 and body["halt"]["by"] == "you" and bot.halt_info()["reason"] == "halted from the dashboard"


def test_a_program_on_this_computer_can(home):
    with serving() as base:
        assert post(base)[0] == 200
    assert bot.halt_info()["by"] == "you"


def test_a_refused_press_is_refused_before_anything_is_read_or_written(home, monkeypatch):
    called = []
    monkeypatch.setattr(bot, "set_halt", lambda *a, **k: called.append(a))
    with serving() as base:
        post(base, "https://example.com")
    assert called == []
