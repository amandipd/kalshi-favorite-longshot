"""The Live tab's losing windows: on the 1H and 6H charts, each 15-minute window that lost money is shaded, with the
share of the balance it took, so the losses show as the chunks they came in. Run for real in node.

lossWindows(pts, real) finds them on the chart's own points: each settlement's change, less any money put in or taken
out, counts toward the window its market closed at (a settlement comes after the close, up to about 15 minutes late),
and only windows that lost on net are kept, each with the balance before it. chart() draws them as bands under the line,
with faint dividers at every window, and bindChart() adds a "This window" row to the tooltip of each settlement in one.
chart() and bindChart() are cut out of the page with the helpers they use; the DOM they touch is stood in for, so a test
reads the SVG the chart drew and each tooltip it filled in. Skipped without node.
"""

import json
import re
import shutil
import subprocess

import pytest

from kalshi_bot.web import dashboard
from test_dark_theme import T, blend, contrast, paint, rgba

HTML = open(dashboard.PAGE, encoding="utf-8").read()
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(not NODE, reason="node isn't installed")

NOW = 1_791_660_000
C = NOW // 900 * 900                       # a window boundary: the window C - 900 .. C closes at C
M_T, M_B, M_L, M_R, H = 12, 26, 2, 76, 230  # chart()'s margins and height


def piece(pattern, flags=re.M | re.S):
    m = re.search(pattern, HTML, flags)
    assert m, f"dashboard.html no longer has {pattern!r}"
    return m.group(0)


def helpers():
    one_line = ("esc", "nf", "zero", "money", "signed", "pct", "spct", "tone", "arrow", "hhmm", "happened", "LOSS_RANGES")
    # dollarLine: the real account's $ line with deposits smoothed out (Oct 11, test_chart_deposits.py), which chart()
    # calls once it's there; taken when the page has it, so these tests run before and after it
    smooth = re.search(r"^function dollarLine\(.*?^\}$", HTML, re.M | re.S)
    return "\n".join([*(piece(rf"^const {n} = [^\n]*$", re.M) for n in one_line), piece(r"^const when = .*?^\};$"),
                      piece(r"^function lossWindows\(pts, real\) \{.*?^\}$"), smooth.group(0) if smooth else ""])


def node(js, payload):
    r = subprocess.run([NODE, "-e", js], input=json.dumps(payload), capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def losses(pts, real=True):
    return node(helpers() + "\nconst input = JSON.parse(require('fs').readFileSync(0, 'utf8'));"
                            "\nprocess.stdout.write(JSON.stringify(lossWindows(input.pts, input.real)));", {"pts": pts, "real": real})


CHART = r"""
const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));
let data = input.data, range = input.range, view = input.view, unit = input.unit;
let running = false, hovering = false, cm = null, drawn = null;
const els = {};
function el(name) {
  return els[name] || (els[name] = { attrs: {}, on: {}, style: {}, hidden: true, innerHTML: "", offsetWidth: 220, offsetHeight: 90,
    setAttribute(k, v) { this.attrs[k] = v; }, addEventListener(k, f) { this.on[k] = f; }, blur() {},
    getBoundingClientRect() { return { left: 0, top: 0, width: input.width, height: 230 }; },
    ownerSVGElement: { getBoundingClientRect() { return { left: 0, top: 0 }; } } });
}
const $ = (id) => id === "chart" ? { clientWidth: input.width, querySelector: (sel) => el(sel) } : el(id);
const innerWidth = 1400;
const patch = (id, html) => { drawn = html; return true; };
const emptyState = (text) => `<empty>${text}</empty>`;
chart();
const tips = [];
for (const k of input.keys) {
  if (k === "focus") els["#hit"].on.focus(); else els["#hit"].on.keydown({ key: k, preventDefault() {} });
  tips.push(el("tip").innerHTML);
}
process.stdout.write(JSON.stringify({ svg: drawn, tips }));
"""


def draw(data, range_, width=800, view="chart", keys=()):
    """chart() on `data` (an /api/state), then the tooltip after each of `keys` ("focus", or a key pressed on the chart)."""
    js = "\n".join([helpers(), piece(r"^function niceTicks\(lo, hi, n\) \{.*?^\}$"), piece(r"^function tableView\(pts, real\) \{.*?^\}$"),
                    piece(r"^function chart\(\) \{.*?^\}$"), piece(r"^function bindChart\(\) \{.*?^\}$"), CHART])
    return node(js, {"data": data, "range": range_, "width": width, "view": view, "unit": "usd", "keys": list(keys)})


def tags(svg, name, cls):
    return [dict(re.findall(r'([\w-]+)="([^"]*)"', t)) for t in re.findall(rf'<{name}\b[^>]*\bclass="{cls}"[^>]*>', svg)]


def labels(svg):
    return [(dict(re.findall(r'([\w-]+)="([^"]*)"', a)), text) for a, text in re.findall(r'<text\b([^>]*\bclass="lw-t"[^>]*)>(.*?)</text>', svg)]


def plain(html):
    return re.sub(r"<[^>]+>", "", html)


def scale(t0, t1, width=800):
    return lambda t: M_L + (t - t0) / (t1 - t0) * (width - M_L - M_R)


def curve(t, value, *events):
    """The real account's points as dashboard.history() makes them, [t, value, money in or out, what], from a first
    point and events (t, change in value, money in or out, what)."""
    pts = [[t, value, 0, "start"]]
    for t, dv, money, what in events:
        value = round(value + dv, 4)
        pts.append([t, value, money, what])
    return pts


def window(open_, pnl, before):
    return {"open": open_, "close": open_ + 900, "pnl": pytest.approx(pnl), "before": pytest.approx(before),
            "pct": pytest.approx(pnl / before)}


# ------------------------------------------------------------------ lossWindows(): which windows lost, and how much
@needs_node
def test_a_windows_settlements_add_up_with_the_balance_before_its_first():
    pts = curve(C - 3600, 1000.0, (C - 900 + 8, -20.00, 0, "1 lost"),     # window C - 1800 .. C - 900
                (C - 900 + 370, +4.59, 0, "1 won"),                        # ... settled 6 minutes after its close
                (C - 900 + 400, +1.00, 0, "1 won"))
    assert losses(pts) == [window(C - 1800, -14.41, 1000.0)]


@needs_node
def test_a_window_whose_wins_outweigh_its_loss_isnt_a_losing_one():
    pts = curve(C - 3600, 1000.0, (C + 8, -3.00, 0, "1 lost"), (C + 60, +5.00, 0, "1 won"))
    assert losses(pts) == []


@needs_node
def test_a_loss_that_rounds_to_nothing_isnt_one():
    assert losses(curve(C - 3600, 1000.0, (C + 8, -0.004, 0, "1 lost"))) == []          # under half a cent
    assert losses(curve(C - 3600, 1000.0, (C + 8, -0.006, 0, "1 lost"))) == [window(C - 900, -0.006, 1000.0)]


@pytest.mark.parametrize("late", [0, 1, 360, 899])
@needs_node
def test_a_settlement_belongs_to_the_window_its_market_closed_at(late):
    assert losses(curve(C - 3600, 1000.0, (C + late, -10.0, 0, "1 lost"))) == [window(C - 900, -10.0, 1000.0)]


@needs_node
def test_15_minutes_after_the_close_is_the_next_window():
    assert losses(curve(C - 3600, 1000.0, (C + 900, -10.0, 0, "1 lost"))) == [window(C, -10.0, 1000.0)]


@needs_node
def test_only_settlements_count():
    pts = [[C - 1000, 500.00, 0, ""],                     # the range's first point, put in where the range starts
           [C - 900 + 30, 499.90, 0, "2 bets placed"],    # fees on bets placed: not a settlement
           [C - 900 + 60, 999.90, 500, "deposit"],
           [C + 10, 989.90, 0, "1 lost"],                 # the one settlement: window C - 900 .. C
           [C + 40, 789.90, -200, "withdrawal"],
           [C + 100, 700.00, 0, "now"]]                   # what the open bets are worth now: a mark, not a result
    assert losses(pts) == [window(C - 900, -10.0, 999.90)]


@needs_node
def test_money_in_or_out_at_a_settlement_point_never_counts():
    pts = [[C - 3600, 999.90, 0, "start"], [C + 10, 1489.90, 500, "1 lost"]]          # +500 in, 10 lost
    assert losses(pts) == [window(C - 900, -10.0, 999.90)]


@needs_node
def test_a_point_where_bets_both_won_and_lost_is_a_settlement():
    pts = curve(C - 3600, 1000.0, (C + 10, -12.0, 0, "1 won · 2 lost"), (C + 905, -4.10, 0, "1 lost · 1 bet placed"))
    assert losses(pts) == [window(C - 900, -12.0, 1000.0), window(C, -4.10, 988.0)]   # a point counts in full


@needs_node
def test_on_the_bots_own_curve_every_point_after_the_first_is_a_settled_bet():
    pts = [[C - 3600, 100.0], [C + 10, 97.0], [C + 300, 98.5], [C + 905, 99.0]]      # [t, bankroll]: no money, no what
    assert losses(pts, real=False) == [window(C - 900, -1.5, 100.0)]                   # C .. C + 900 gained 0.50


@needs_node
def test_losing_windows_come_in_order():
    pts = curve(C - 3600, 1000.0, (C - 900 + 8, -5.0, 0, "1 lost"), (C + 8, +1.0, 0, "1 won"), (C + 900 + 8, -7.0, 0, "1 lost"))
    assert [w["open"] for w in losses(pts)] == [C - 1800, C]


@pytest.mark.parametrize("pts", [[], [[C, 1000.0, 0, "start"]]])
@needs_node
def test_too_few_points_have_no_windows(pts):
    assert losses(pts) == []


# ------------------------------------------------------------------ the bands on the chart
N1 = C + 1200                                         # 1H: from C - 2400 to the last settlement, C + 9
BOT = {"now": N1, "start": 529.55, "kalshiCurve": None, "curve": [
    [C - 5000, 529.55],                              # before the range: the range starts from this value
    [C - 1800 + 5, 524.25],                          # window C - 2700 .. C - 1800, which began before the range: −5.30
    [C - 900 + 8, 504.25],                           # window C - 1800 .. C - 900: −20.00 ...
    [C - 900 + 370, 508.84],                         # ... and +4.59: −15.41 from 524.25, −2.9%
    [C + 9, 510.84]]}                                # window C - 900 .. C: +2.00, not a losing one
REAL = {"now": N1, "start": 529.55, "curve": [], "kalshiCurve": [
    [C - 5000, 529.55, 0, "start"],
    [C - 1800 + 5, 524.25, 0, "1 lost"],             # −5.30, −1.0%
    [C - 1500, 524.15, 0, "1 bet placed"],
    [C - 1200, 1024.15, 500, "deposit"],
    [C - 900 + 8, 1004.15, 0, "1 lost"],             # −20.00 ...
    [C - 900 + 370, 1008.74, 0, "1 won"],            # ... +4.59: −15.41 from 1024.15, −1.5%
    [N1, 1000.00, 0, "now"]]}


@pytest.mark.parametrize("data, t1", [(BOT, C + 9), (REAL, N1)], ids=["bot", "real"])
@needs_node
def test_each_losing_window_is_shaded_the_full_height_of_the_plot(data, t1):
    svg = draw(data, "1h")["svg"]
    t0 = N1 - 3600
    x = scale(t0, t1)
    bands = tags(svg, "rect", "lw")
    assert len(bands) == 2                                                   # the winning window isn't shaded
    for band, (a, b) in zip(bands, [(t0, C - 1800), (C - 1800, C - 900)]):  # the first is cut at the range's start
        assert float(band["x"]) == pytest.approx(x(a), abs=0.11)
        assert float(band["width"]) == pytest.approx(x(b) - x(a), abs=0.11)
        assert (float(band["y"]), float(band["height"])) == pytest.approx((M_T, H - M_T - M_B))
    assert svg.index('class="lw"') < svg.index('class="ln"')                # under the line, not over it


@needs_node
def test_faint_dividers_mark_every_window_inside_the_range():
    svg = draw(BOT, "1h")["svg"]
    x = scale(N1 - 3600, C + 9)
    lines = tags(svg, "line", "wl")
    assert [float(ln["x1"]) for ln in lines] == pytest.approx([x(C - 1800), x(C - 900), x(C)], abs=0.11)
    assert all(ln["x1"] == ln["x2"] for ln in lines)
    assert svg.index('class="wl"') < svg.index('class="ln"')


@needs_node
def test_6h_shades_and_divides_too():
    svg = draw(BOT, "6h")["svg"]                     # all of BOT is inside 6 hours: from C - 5000 to C + 9
    x = scale(C - 5000, C + 9)
    assert [float(ln["x1"]) for ln in tags(svg, "line", "wl")] == pytest.approx([x(C - 900 * k) for k in (5, 4, 3, 2, 1, 0)], abs=0.11)
    assert len(tags(svg, "rect", "lw")) == 2


@needs_node
def test_each_band_wide_enough_is_labelled_with_the_share_of_the_balance_it_lost():
    svg = draw(BOT, "1h")["svg"]
    x = scale(N1 - 3600, C + 9)
    got = labels(svg)
    assert [text for _, text in got] == ["−1.0%", "−2.9%"]                  # −5.30 of 529.55; −15.41 of 524.25
    for (attrs, _), (a, b) in zip(got, [(N1 - 3600, C - 1800), (C - 1800, C - 900)]):
        assert attrs.get("text-anchor") == "middle" and float(attrs["x"]) == pytest.approx((x(a) + x(b)) / 2, abs=1)
        assert M_T < float(attrs["y"]) <= M_T + 30                           # near the top of the band


@pytest.mark.parametrize("visible, labelled", [(91, True), (88, False)])
@needs_node
def test_a_band_under_34_px_wide_has_no_label(visible, labelled):
    """The range starts `visible` seconds before the first losing window closes, so only that much of it shows:
    34.6 px of the 722 px plot, or 33.5."""
    now = C + 1800 - visible
    svg = draw({**BOT, "now": now}, "1h")["svg"]
    x = scale(now - 3600, C + 9)
    first = tags(svg, "rect", "lw")[0]
    assert float(first["width"]) == pytest.approx(x(C - 1800) - x(now - 3600), abs=0.11)
    assert [text for _, text in labels(svg)] == (["−1.0%", "−2.9%"] if labelled else ["−2.9%"])


@pytest.mark.parametrize("range_", ["1d", "all"])
@needs_node
def test_the_longer_ranges_stay_as_they_were(range_):
    svg = draw(BOT, range_)["svg"]
    assert 'class="lw"' not in svg and 'class="wl"' not in svg and 'class="lw-t"' not in svg and "losing window" not in svg


@needs_node
def test_the_table_view_draws_no_bands():
    html = draw(BOT, "1h", view="table")["svg"]
    assert "<table>" in html and 'class="lw"' not in html and 'class="wl"' not in html


@pytest.mark.parametrize("data, said", [
    (BOT, " 2 losing windows in this range, the worst −2.9% of the balance."),
    (REAL, " 2 losing windows in this range, the worst −1.5% of the balance."),
    ({**BOT, "curve": BOT["curve"][:2]}, " 1 losing window in this range, the worst −1.0% of the balance."),
], ids=["bot", "real", "one"])
@needs_node
def test_screen_readers_hear_how_many_windows_lost_and_the_worst(data, said):
    label = re.search(r'<svg class="cv[^"]*"[^>]*aria-label="([^"]*)"', draw(data, "1h")["svg"]).group(1)
    assert said in label


@needs_node
def test_a_range_with_no_losing_window_says_nothing_of_them_but_still_divides():
    calm = {**BOT, "curve": [[C - 5000, 529.55], [C - 900 + 8, 531.0], [C + 9, 533.0]]}
    svg = draw(calm, "1h")["svg"]
    assert "losing window" not in svg and 'class="lw"' not in svg and 'class="lw-t"' not in svg
    assert tags(svg, "line", "wl")


# ------------------------------------------------------------------ the tooltip
def window_row(tip):
    m = re.search(r"This window\s*(.*?)(?:$|\n|<)", plain(tip.replace("</b>", "\n")))
    return m and m.group(1).strip()


@needs_node
def test_a_settlement_in_a_losing_window_says_what_the_window_lost():
    tips = draw(BOT, "1h", keys=["focus", "Home"] + ["ArrowRight"] * 4)["tips"]
    rows = [window_row(t) for t in tips]                # the last point, then the first, then each in turn
    assert rows == [None, None, "▼ −$5.30 · −1.0% of the balance", "▼ −$15.41 · −2.9% of the balance",
                    "▼ −$15.41 · −2.9% of the balance", None]
    assert "This bet" in tips[3]                        # the bet's own row stays


@needs_node
def test_on_the_real_account_only_settlements_get_the_row():
    tips = draw(REAL, "1h", keys=["focus", "Home"] + ["ArrowRight"] * 6)["tips"]
    rows = [window_row(t) for t in tips]                # now, the range's start, lost, bet placed, deposit, lost, won, now
    assert rows == [None, None, "▼ −$5.30 · −1.0% of the balance", None, None, "▼ −$15.41 · −1.5% of the balance",
                    "▼ −$15.41 · −1.5% of the balance", None]


# ------------------------------------------------------------------ how they look
def rule(selector):
    m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", HTML)
    assert m, f"dashboard.html has no {selector} rule"
    return m.group(1)


def test_the_band_is_a_faint_red():
    body = rule(".cv .lw")
    assert re.search(r"fill:\s*var\(--down\)", body)
    opacity = float(re.search(r"(?<![-\w])(?:fill-)?opacity:\s*([\d.]+)", body).group(1))
    assert 0.05 <= opacity <= 0.2


def test_the_dividers_are_faint_dashed_lines():
    body = rule(".cv .wl")
    assert re.search(r"stroke:\s*var\(--line\)", body) and "stroke-dasharray" in body


def test_the_label_is_red_text_that_reads_on_its_band():
    body = rule(".cv .lw-t")
    assert re.search(r"fill:\s*var\(--down-ink\)", body)
    size = float(re.search(r"(\d+(?:\.\d+)?)px", body).group(1))
    assert 10 <= size <= 12
    opacity = float(re.search(r"(?<![-\w])(?:fill-)?opacity:\s*([\d.]+)", rule(".cv .lw")).group(1))
    r, g, b, a = rgba(T["down"])
    page = paint("page")                                 # the chart sits straight on the page
    band = tuple(a * opacity * c + (1 - a * opacity) * d for c, d in zip((r, g, b), page))
    assert contrast(blend("down-ink", band), band) >= 4.5   # WCAG AA for text
