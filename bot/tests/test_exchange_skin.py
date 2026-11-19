"""The exchange skin: a second look for the Live tab, switched from the navbar.

Added on Oct 30, 2026: the dashboard made to look like a market exchange. Settled as a skin you can
flip to rather than a replacement, the same information rather than new panels, and the Live tab only.

So this is a restyle and nothing else. Everything it needs already existed: the board already carries bid, ask
and spread columns and already flashes a row green or red when a price moves (flashOf, .fl-up / .fl-down). The
skin makes those louder and the rows denser; it adds no data and asks the server for nothing new.

What these tests hold it to:
  * it cannot reach the research tabs, which keep the reading look they have
  * it takes its colours from the page's tokens, so it follows light and dark like everything else
  * its sizes, spaces and radii come from the page's own scales, dense though it is
  * the choice survives a reload, and is applied before first paint so the wrong look never flashes up

The clean look's own rules (test_look.py) are deliberately NOT applied to this sheet: they encode one
aesthetic and this is a second one. Each look has its own contract -- that file's, and this one.

    python -m pytest tests/test_exchange_skin.py -q
"""
import os
import re

from kalshi_bot.web import dashboard
from test_live_research_page import own

HERE = os.path.dirname(os.path.abspath(dashboard.PAGE))
HTML = open(dashboard.PAGE, encoding="utf-8").read()
SCRIPT = re.search(r"<script>\n\"use strict\";(.*?)</script>", HTML, re.S).group(1)
SKIN = "exchange"

# the page's own scales; a dense look still keeps to them (test_look.py holds the clean look to the same table)
SPACES = {"0", "1px", "2px", "var(--sp-1)", "var(--sp-2)", "var(--sp-3)", "var(--sp-4)", "var(--sp-5)",
          "var(--sp-6)", "var(--sp-7)", "auto", "inherit"}
RADII = {"0", "var(--r-1)", "var(--r-2)", "var(--r-pill)", "50%", "inherit"}
SIZES = {"var(--fs-1)", "var(--fs-2)", "var(--fs-3)", "var(--fs-4)", "var(--fs-5)", "var(--fs-6)", "var(--fs-7)",
         "inherit", "1em", "100%"}


def css():
    """The skin's stylesheet with its comments taken out."""
    return re.sub(r"/\*.*?\*/", "", own("exchange.css"), flags=re.S)


def selectors():
    for block in re.findall(r"(?:^|\})\s*([^@{}]+)\{", css(), re.M):
        for sel in block.split(","):
            sel = sel.strip()
            if sel and not sel.startswith(("from", "to", "0%", "100%", "50%")):
                yield sel


def declarations():
    for body in re.findall(r"\{([^{}]*)\}", css()):
        for bit in body.split(";"):
            if ":" in bit:
                prop, _, val = bit.partition(":")
                yield prop.strip(), val.strip()


# ------------------------------------------------------------------ the sheet
def test_every_rule_is_behind_the_skin_switch():
    """With the skin off the page must look exactly as it does today, so no rule may apply unconditionally."""
    for sel in selectors():
        assert sel.startswith(f'[data-skin="{SKIN}"]'), sel


def test_it_cannot_reach_the_research_tabs():
    """The Live tab only: Live Research, Latency and Backtest keep the reading look they have."""
    for sel in selectors():
        for other in ("#liveresearch", "#latency", "#backtest", ".lr-", ".lat-", ".bt-"):
            assert other not in sel, f"{sel} reaches {other}"


def test_it_defines_no_colours_of_its_own():
    """Light and dark come from the page's tokens, so the skin follows the theme without a second palette."""
    assert "--" not in re.sub(r"var\(--[a-z0-9-]+\)", "", css())


def test_its_spaces_radii_and_sizes_come_from_the_pages_scales():
    bad = []
    for prop, val in declarations():
        if re.match(r"^(margin|padding|gap|row-gap|column-gap)(-[a-z]+)?$", prop):
            bad += [(prop, v) for v in val.split() if v not in SPACES]
        elif prop == "border-radius":
            bad += [(prop, v) for v in val.split() if v not in RADII]
        elif prop == "font-size":
            bad += [(prop, val)] if val not in SIZES else []
    assert not bad, f"off the scale: {bad}"


def test_the_numbers_are_set_in_the_pages_mono_face():
    """What makes a board read like an exchange is figures that line up, which is what --mono is for."""
    assert "var(--mono)" in css()


def test_the_price_flashes_are_louder_not_new():
    """The board already flashes a row when a price moves (flashOf). The skin restyles that; it does not add it."""
    assert "fl-up" in css() and "fl-down" in css()
    assert "flashOf" not in css()


# ------------------------------------------------------------------ the switch
def test_the_server_serves_the_skin():
    assert dashboard.ASSETS["/exchange.css"] == ("exchange.css", "text/css; charset=utf-8")


def test_the_page_loads_it():
    assert HTML.index('<link rel="stylesheet" href="/exchange.css">') < HTML.index("</head>")


def test_the_navbar_has_a_switch():
    assert 'id="skin"' in HTML
    btn = re.search(r'<button id="skin"[^>]*>', HTML).group(0)
    assert 'type="button"' in btn and "aria-label" in btn


def test_the_switch_is_remembered_and_applied_before_the_page_paints():
    """Read in the <head>, the way the theme is, so the wrong look never flashes up on a reload."""
    head = HTML.split("</head>")[0]
    early = re.search(r'localStorage\.getItem\("skin"\)', head)
    assert early, "the skin isn't read in the head"
    assert early.start() < head.index("<style>"), "it's read after the styles, so the wrong look can paint first"
    assert 'dataset.skin' in head


def test_clicking_it_flips_the_skin_and_stores_it():
    body = SCRIPT.split('$("skin").onclick')[1].split("\n};")[0]
    assert "dataset.skin" in body and 'store.set("skin"' in body
    assert "aria-pressed" in body


def test_it_does_not_disturb_the_theme_switch():
    """Light/dark and the skin are separate choices: either can be set without touching the other."""
    body = SCRIPT.split('$("skin").onclick')[1].split("\n};")[0]
    assert "dataset.theme" not in body and '"theme"' not in body
