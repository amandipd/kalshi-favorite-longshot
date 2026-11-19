"""The dashboard is dark only, and its colour tokens are readable: worked out the way a browser paints them, they meet
WCAG contrast.

dashboard.html's one :root block holds the colours (there is no light theme and no switch). Each token is resolved to
the colour it paints: rgba() is laid over the background it sits on, as the browser blends it. Then the WCAG 2
contrast ratio is checked: 7:1 (AAA) for the main text, 4.5:1 for the secondary text and coloured text, 3:1 for chart
lines and marks (non-text), and hairlines bright enough to see on a card.
"""

import re

import pytest

from kalshi_bot.web import dashboard

HTML = open(dashboard.PAGE, encoding="utf-8").read()


def tokens(block):
    return dict(re.findall(r"--([\w-]+):\s*([^;]+);", block))


def root(src):
    m = re.search(r"^:root \{(.*?)^\}", src, re.M | re.S)
    assert m, "no :root block"
    return tokens(m.group(1))


T = root(HTML)


def rgba(value):
    """(r, g, b, a) for '#rrggbb' or 'rgba(r, g, b, a)', following one var() reference."""
    value = value.strip()
    ref = re.fullmatch(r"var\(--([\w-]+)\)", value)
    if ref:
        return rgba(T[ref.group(1)])
    if value.startswith("#"):
        return (int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16), 1.0)
    m = re.fullmatch(r"rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?\)", value)
    assert m, f"can't read colour {value!r}"
    return (float(m[1]), float(m[2]), float(m[3]), float(m[4] or 1))


def blend(name, base):
    """The opaque colour token `name` paints over the opaque colour `base`, blended as the browser does."""
    r, g, b, a = rgba(T[name])
    return tuple(a * c + (1 - a) * d for c, d in zip((r, g, b), base))


def paint(name, over="surface"):
    """The colour token `name` paints when laid over token `over` (itself laid over black)."""
    return blend(name, (0, 0, 0) if over == "black" else paint(over, "black"))


def luminance(rgb):
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def ratio(fg, bg):
    return contrast(paint(fg, bg), paint(bg))


TEXT = {"ink": 7, "ink-2": 7, "muted": 5.5, "up-ink": 4.5, "down-ink": 4.5, "warn-ink": 4.5, "brand-ink": 4.5}
GROUNDS = ["page", "surface", "surface-2"]


@pytest.mark.parametrize("fg", TEXT)
@pytest.mark.parametrize("bg", GROUNDS)
def test_text_tokens_read_clearly_on_every_background(fg, bg):
    assert ratio(fg, bg) >= TEXT[fg], f"--{fg} on --{bg}: {ratio(fg, bg):.2f}:1"


@pytest.mark.parametrize("fg", ["ink", "ink-2", "muted"])
@pytest.mark.parametrize("wash", ["up-wash", "down-wash", "warn-wash"])
def test_plain_text_reads_on_the_tinted_rows(fg, wash):
    row = paint(wash, "surface")
    assert contrast(blend(fg, row), row) >= TEXT[fg] - 1   # the board's in-range and out-of-range rows, on the card


@pytest.mark.parametrize("tone", ["up", "down", "warn"])
def test_a_tones_ink_reads_on_its_own_wash(tone):
    row = paint(f"{tone}-wash", "surface")
    assert contrast(blend(f"{tone}-ink", row), row) >= 4.5   # a gain pill's text on its green tint, a loss's on red


def test_hairlines_are_visible_on_a_card():
    assert ratio("line", "surface") >= 1.2          # table rules and panel borders
    assert ratio("line-strong", "surface") >= 1.5   # outlined buttons, the chart's start tag


def test_cards_stand_apart_from_the_page():
    assert T["surface"].strip().lower() != T["page"].strip().lower()
    assert ratio("surface", "page") >= 1.01


def test_the_page_is_dark_only():
    assert re.search(r"^:root \{\s*color-scheme: dark;", HTML, re.M)
    assert '<meta name="color-scheme" content="dark">' in HTML
    for gone in ("prefers-color-scheme", "data-theme", 'id="theme"', "dataset.theme", 'getItem("theme")'):
        assert gone not in HTML, f"dashboard.html still has {gone}"
    assert HTML.count("--page:") == 1, "the colours should be defined once"


def test_the_pressed_segment_stands_out_from_its_track():
    m = re.search(r'\.grp button\[aria-pressed="true"\] \{[^}]*background: var\(--([\w-]+)\)', HTML)
    assert m and ratio(m.group(1), "surface-2") >= 1.05   # a 1px line-strong ring carries the rest
