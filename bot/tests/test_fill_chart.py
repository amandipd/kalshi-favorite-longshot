"""A fill-rate chart on the Live tab: is live fast entry filling more than before?

A chart of how many orders filled, to monitor it. Fast entry went live at the bot restart at 21:04 UTC on Oct 14,
2026, so its first window was the 21:00 UTC one.

The server: dashboard.fill_windows(orders) counts buy orders per 15-minute window (ts - ts % 900), as fill_counts counts
them (a missing count asks 0; a refused or unanswered order filled 0 and got none): [window, orders, asked, filled,
none], oldest first, windows with an order only. state() sends "fillWindows", the last FILL_CHART_DAYS (7) days of them,
and "fillsFast": {"live": FAST_LIVE, "before": the FILL_BEFORE_DAYS (4) days before it, "after": everything since}, each
as fill_counts counts it.

The page: a "Fill rate" fold (live.fills, open at first) between Live markets and Orders. Its header meta says how
fast entry has filled since it went live and in the 4 days before, so it shows while folded. The first version (a dot
per window, two lines and a legend) was hard to read, so the body
leads with the answer, two tiles: contracts filled, and orders that got nothing, each since fast entry, what it was in
the 4 days before, and the change in points (green when it got better: more filled, fewer got nothing). Under them a
one-line caption and fillChart(rows, fast, W): one line, the share of contracts filled over the last 12 windows the
bot placed orders in (about 3 hours), on 0-100% gridlines; broken where it wasn't trading (test_fill_off.py); each period's average as a dashed level line labelled "before: 59%" / "since: 70%"; the
fast-entry period shaded with a marker where it starts; and a hover column per window whose <title> gives that window's
figures. No per-window dots, no got-none line, no legend (the labels say it). The colour is a token, --series-1 (a
blue checked for contrast), defined for light and dark in dashboard.html's :root blocks.

The page's pieces are cut out of dashboard.html and run in node with the time zone fixed and the clock fixed (so "today"
in when() is a known day; skipped without node). The geometry is read back from the svg: the gridlines give the y scale
(100% at the top one, 0% at the bottom one), the line's first and last points the x scale.

    python -m pytest -q -p no:cacheprovider tests/test_fill_chart.py
"""

import json
import os
import re
import subprocess

import pytest

from kalshi_bot.web import dashboard
from test_dashboard_more import home, mode_db, order  # noqa: F401  (home is a fixture)
from test_folds_live import Tree, decl, fold_helper, golden, missing, run
from test_look import RULES, norm
from test_order_results import HTML, NODE, SCRIPT, needs_node

DAY, W15 = 86400, 900
LIVE = 1792011600                       # Oct 14, 2026, 21:00 UTC = 2:00 PM PT (5:00 PM in the tests' New York time)
TODAY_MS = (LIVE + DAY) * 1000          # the page's clock in the node tests: Oct 15, so when() writes "Oct 14 5:00 PM"
EMPTY = {"orders": 0, "asked": 0, "filled": 0, "none": 0}


def o(ts, asked, filled):
    """A buy order as order_row reads it (filled None: refused or unanswered)."""
    return {"ts": ts, "ticker": "KXBTC15M-A", "series": "KXBTC15M", "side": "yes", "price": 0.95,
            "asked": asked, "filled": filled, "error": None if filled is not None else "insufficient balance"}


# ------------------------------------------------------------------ the server
def test_fast_entry_went_live_with_the_2_pm_pt_window_of_oct_14():
    assert dashboard.FAST_LIVE == LIVE and LIVE % W15 == 0
    assert (dashboard.FILL_CHART_DAYS, dashboard.FILL_BEFORE_DAYS) == (7, 4)


def test_fill_windows_counts_each_windows_orders_as_fill_counts_does():
    w = LIVE
    rows = dashboard.fill_windows([o(w + 480, 15, 15.0), o(w + 480.2, 10, 2.5), o(w + 481, 12, 0.0),   # one window
                                   o(w + 482, 15, None),                                             # refused: got none
                                   o(w + W15 + 480, None, 0.0),                                      # no count: asks 0
                                   o(w + 3 * W15 + 480, 20, 20.0)])                                  # a window later
    assert rows == [[w, 4, 52.0, 17.5, 2], [w + W15, 1, 0.0, 0.0, 1], [w + 3 * W15, 1, 20.0, 20.0, 0]]


def test_fill_windows_come_oldest_first_and_only_windows_with_an_order():
    w = LIVE
    rows = dashboard.fill_windows([o(w + 2 * W15 + 480, 5, 5.0), o(w + 480, 5, 1.0), o(w + 2 * W15 + 481, 5, 0.0)])
    assert [r[0] for r in rows] == [w, w + 2 * W15] and dashboard.fill_windows([]) == []


def test_a_window_starts_on_its_quarter_hour_whatever_the_orders_second():
    rows = dashboard.fill_windows([o(LIVE + 899.999, 5, 5.0), o(LIVE + 900.0, 5, 5.0)])
    assert [r[0] for r in rows] == [LIVE, LIVE + W15]


def the_ledger(home):
    """Buy orders around fast entry's go-live, and the state an hour and a half after it."""
    home.clock[0] = LIVE + 5400
    db = mode_db(home, "live-prod")
    order(db, LIVE - 8 * DAY + 480, "KXBTC15M-LONGAGO", response='{"fill_count": "15.00"}')      # 8 days: in neither
    order(db, LIVE - 5 * DAY + 480, "KXBTC15M-D5", response='{"fill_count": "15.00"}')           # 5 days: before's out
    order(db, LIVE - 4 * DAY, "KXETH15M-D4", response='{"fill_count": "9.00"}')                  # 4 days exactly: before
    order(db, LIVE - 600, "KXSOL15M-LAST", response='{"fill_count": "0.00"}')                    # the last slow window
    order(db, LIVE - 590, "KXXRP15M-LAST", status=400, response='{"error": {"message": "insufficient balance"}}')
    order(db, LIVE + 480, "KXBTC15M-F1", response='{"fill_count": "12.00"}')                     # fast: 2:08 PM PT
    order(db, LIVE + 480.1, "KXETH15M-F1", count="16", response='{"fill_count": "16.00"}')
    order(db, LIVE + W15 + 480, "KXSOL15M-F2", response='{"fill_count": "0.00"}')
    order(db, LIVE + 4 * W15 + 480, "KXXRP15M-FUTURE", response='{"fill_count": "15.00"}')        # (after now: still counted)
    db.commit()
    return dashboard.state("live-prod")


def test_the_state_sends_fast_entrys_before_and_after(home):
    s = the_ledger(home)
    assert s["fillsFast"] == {"live": LIVE,
                              "before": {"orders": 3, "asked": 45.0, "filled": 9.0, "none": 2},       # D4, SOL, XRP
                              "after": {"orders": 4, "asked": 61.0, "filled": 43.0, "none": 1}}       # F1 ×2, F2, FUTURE


def test_the_state_sends_the_last_7_days_windows(home):
    s = the_ledger(home)
    assert s["fillWindows"] == [[LIVE - 5 * DAY, 1, 15.0, 15.0, 0], [LIVE - 4 * DAY, 1, 15.0, 9.0, 0],
                                [LIVE - W15, 2, 30.0, 0.0, 2], [LIVE, 2, 31.0, 28.0, 0], [LIVE + W15, 1, 15.0, 0.0, 1],
                                [LIVE + 4 * W15, 1, 15.0, 15.0, 0]]
    json.dumps(s["fillWindows"]), json.dumps(s["fillsFast"])                                       # the API sends JSON


def test_an_order_exactly_7_days_old_is_on_the_chart_and_one_a_second_older_isnt(home):
    home.clock[0] = LIVE + DAY
    db = mode_db(home, "live-prod")
    order(db, LIVE + DAY - 7 * DAY, "KXBTC15M-EDGE")
    order(db, LIVE + DAY - 7 * DAY - 1, "KXETH15M-OLDER")
    db.commit()
    assert [r[0] for r in dashboard.state("live-prod")["fillWindows"]] == [LIVE - 6 * DAY]


def test_with_no_buy_orders_the_chart_is_empty_and_both_sides_are_zero(home):
    home.clock[0] = LIVE + 3600
    mode_db(home, "live-prod").commit()
    s = dashboard.state("live-prod")
    assert s["fillWindows"] == [] and s["fillsFast"] == {"live": LIVE, "before": EMPTY, "after": EMPTY}


def test_every_order_counts_not_just_the_ones_listed(home):
    home.clock[0] = LIVE + DAY
    db = mode_db(home, "live-prod")
    for i in range(40):
        order(db, LIVE + i * W15 + 480, f"KXBTC15M-{i:02d}")                                       # 4 of 15 each
    db.commit()
    s = dashboard.state("live-prod")
    assert len(s["fillWindows"]) == 40 and s["fillsFast"]["after"] == {"orders": 40, "asked": 600.0, "filled": 160.0, "none": 0}


# ------------------------------------------------------------------ the page: in node
def piece(name):
    src = decl(SCRIPT, name)
    assert src, f"dashboard.html has no top-level {name}"
    return src


PRELUDE = [
    f"const RealDate = Date; Date = class extends RealDate {{ constructor(...a) {{ super(...(a.length ? a : [{TODAY_MS}])); }} "
    f"static now() {{ return {TODAY_MS}; }} }};",
]
HELPERS = ["esc", "nf", "zero", "pct", "count", "hhmm", "when", "ICON_LIST", "emptyState"]
# fillChart, fillsBlock and anything else of theirs at the top level: every function or const named fill... or FILL...
FILL = re.findall(r"^(?:function|const|let) ((?:fill|FILL)\w*)\b", SCRIPT, re.M)


def node(body, payload):
    js = "\n".join([*PRELUDE, *(piece(n) for n in HELPERS), *(piece(n) for n in FILL if n not in ("fillChart", "fillsBlock")), body])
    r = subprocess.run([NODE, "-e", js], input=json.dumps(payload), capture_output=True, text=True, encoding="utf-8",
                       timeout=30, env={**os.environ, "TZ": "America/New_York", "LANG": "en_US.UTF-8", "LC_ALL": "en_US.UTF-8"})
    assert r.returncode == 0, r.stderr
    return r.stdout.replace(" ", " ").replace("\xa0", " ")


def chart(rows, fast=None, w=720):
    """What fillChart(rows, fast, W) draws."""
    return node("\n".join([piece("fillChart"),
                           "const p = JSON.parse(require('fs').readFileSync(0, 'utf8'));",
                           "process.stdout.write(fillChart(p.rows, p.fast, p.w));"]), {"rows": rows, "fast": fast, "w": w})


def block(state, width=720):
    """What fillsBlock() writes for a state (its fold, through the page's own fold helper)."""
    return node("\n".join([piece("fillChart"), piece("fillsBlock"), fold_helper(SCRIPT),
                           "const out = {}; function patch(id, html) { out[id] = html; return true; }",
                           f"const $ = (id) => ({{ clientWidth: {width} }});",
                           "const data = JSON.parse(require('fs').readFileSync(0, 'utf8'));",
                           "fillsBlock();",
                           "process.stdout.write(JSON.stringify(out));"]), state)


def fold_of(state):
    out = json.loads(block(state))
    assert list(out) == ["fills"], f"fillsBlock patched {list(out)}"
    root = Tree(out["fills"]).root
    sec = root.children()[0]
    head = [e for e in sec.children() if e.has_class("fold-h")][0]
    body = [e for e in sec.children() if e.has_class("fold-body")][0]
    metas = [e for e in head.els() if e.tag == "span" and e.has_class("fold-m")]
    meta = metas[0] if metas else None
    lines = [s.text() for s in meta.els() if s.has_class("fm-ln")] if meta else []
    return sec, head, body, (lines or ([meta.text()] if meta and meta.text() else [])), out["fills"]


def els(markup, tag=None, cls=None):
    return [e for e in Tree(markup).root.els() if (tag is None or e.tag == tag) and (cls is None or e.has_class(cls))]


def num(v):
    return float(v)


def scales(svg):
    """(y of 0%, y of 100%) from the gridlines, after checking there are five, labelled."""
    grid = els(svg, "line", "fr-grid")
    assert len(grid) == 5, f"{len(grid)} .fr-grid lines, not 5 (0, 25, 50, 75, 100%)"
    ys = sorted({num(g.attrs["y1"]) for g in grid})
    assert len(ys) == 5 and all(num(g.attrs["y1"]) == num(g.attrs["y2"]) for g in grid), "the gridlines aren't 5 levels"
    labels = [t.text() for t in els(svg, "text")]
    for lab in ("0%", "25%", "50%", "75%", "100%"):
        assert lab in labels, f"no {lab} label"
    return ys[-1], ys[0]


def yv(svg):
    y0, y100 = scales(svg)
    return lambda share: y0 + (y100 - y0) * share


def dots(svg):
    """[(cx, cy, title)] for each dot, in order, after checking its markup."""
    out = []
    for g in els(svg, "g", "fr-pt"):
        titles = [e for e in g.children() if e.tag == "title"]
        circles = [e for e in g.els() if e.tag == "circle" and e.has_class("fr-dot")]
        assert len(titles) == 1 and len(circles) == 1, "a .fr-pt holds one <title> and one circle.fr-dot"
        out.append((num(circles[0].attrs["cx"]), num(circles[0].attrs["cy"]), titles[0].text()))
    return out


def path_points(svg, cls):
    ps = els(svg, "path", cls)
    assert len(ps) == 1, f"{len(ps)} path.{cls}"
    return [(float(a), float(b)) for a, b in re.findall(r"[ML]\s*(-?[\d.]+)[ ,]\s*(-?[\d.]+)", ps[0].attrs["d"])]


def rolling(rows, k=12):
    fill, none, kept = [], [], [r for r in rows if r[2] > 0]
    for i in range(len(kept)):
        last = kept[max(0, i - k + 1):i + 1]
        fill.append(sum(r[3] for r in last) / sum(r[2] for r in last))
    for i in range(len(rows)):
        last = rows[max(0, i - k + 1):i + 1]
        none.append(sum(r[4] for r in last) / sum(r[1] for r in last))
    return fill, none


def series(n=20, start=LIVE - 10 * W15):
    """n windows, one a quarter hour, fills climbing; every 7th window's orders all got none."""
    out = []
    for i in range(n):
        orders, asked = 3 + i % 4, 15.0 * (3 + i % 4)
        filled = 0.0 if i % 7 == 3 else round(asked * (0.3 + 0.03 * i), 2)
        none = orders if i % 7 == 3 else i % 2
        out.append([start + i * W15, orders, asked, filled, none])
    return out


FAST = {"live": LIVE, "before": {"orders": 1234, "asked": 20000, "filled": 12000, "none": 309},
        "after": {"orders": 40, "asked": 700, "filled": 504, "none": 4}}


# ------------------------------------------------------------------ the chart
def line_pts(svg):
    return path_points(svg, "fr-ln")


def xv(svg, rows):
    """x of a time, from the line's first and last points (the first and last windows that asked for something)."""
    pts, kept = line_pts(svg), [r for r in rows if r[2] > 0]
    (x0, _), (x1, _), t0, t1 = pts[0], pts[-1], kept[0][0], kept[-1][0]
    return lambda t: x0 + (x1 - x0) * (t - t0) / (t1 - t0)


@needs_node
def test_one_line_the_last_12_windows_share_of_contracts_filled():
    rows = series(30)
    svg = chart(rows, FAST)
    y, pts = yv(svg), line_pts(svg)
    fill, _ = rolling(rows)
    assert len(pts) == len(fill) == len(rows)
    for (px, py), want in zip(pts, fill):
        assert py == pytest.approx(y(want), abs=0.6)


@needs_node
def test_the_line_runs_left_to_right_in_time_from_edge_to_edge_of_the_plot():
    rows = series()
    rows = rows[:5] + rows[9:]                                                     # a gap: four windows with no order
    svg = chart(rows)
    pts, grid = line_pts(svg), els(svg, "line", "fr-grid")
    x0, x1 = pts[0][0], pts[-1][0]
    for (px, _), r in zip(pts, rows):
        assert (px - x0) / (x1 - x0) == pytest.approx((r[0] - rows[0][0]) / (rows[-1][0] - rows[0][0]), abs=0.005)
    assert x0 == pytest.approx(min(num(g.attrs["x1"]) for g in grid), abs=1)     # the plot's left edge ...
    assert x1 == pytest.approx(max(num(g.attrs["x2"]) for g in grid), abs=1)     # ... to its right


@needs_node
def test_no_dots_no_got_none_line_and_no_legend():
    out = chart(series(30), FAST)
    assert not els(out, "circle", "fr-dot") and not els(out, "path", "fr-none") and not els(out, cls="fr-key")


@needs_node
def test_a_window_that_asked_for_nothing_has_no_point_on_the_line():
    rows = [[LIVE, 2, 30.0, 15.0, 0], [LIVE + W15, 1, 0.0, 0.0, 1], [LIVE + 2 * W15, 1, 15.0, 15.0, 0]]
    svg = chart(rows)
    assert len(line_pts(svg)) == 2 and line_pts(svg)[1][1] == pytest.approx(yv(svg)(30 / 45), abs=0.6)


def hovers(svg):
    """[(rect, title)] for each hover column, in order, after checking its markup."""
    out = []
    for g in els(svg, "g", "fr-pt"):
        titles = [e for e in g.children() if e.tag == "title"]
        rects = [e for e in g.els() if e.tag == "rect" and e.has_class("fr-hit")]
        assert len(titles) == 1 and len(rects) == 1, "a .fr-pt holds one <title> and one rect.fr-hit"
        out.append((rects[0], titles[0].text()))
    return out


@needs_node
def test_a_hover_column_per_window_over_the_whole_plot_height():
    rows = series()
    svg = chart(rows, FAST)
    hs, x = hovers(svg), xv(svg, rows)
    y0, y100 = scales(svg)
    assert len(hs) == len(rows)
    for (rect, _), r in zip(hs, rows):
        left, w = num(rect.attrs["x"]), num(rect.attrs["width"])
        assert left - 0.6 <= x(r[0]) <= left + w + 0.6                            # its window is inside it
        assert num(rect.attrs["y"]) == pytest.approx(y100, abs=1) and num(rect.attrs["height"]) == pytest.approx(y0 - y100, abs=1)


@needs_node
def test_the_hover_gives_the_windows_figures_and_the_lines_value():
    rows = [[LIVE, 2, 30.0, 12.5, 1], [LIVE + W15, 1, 15.0, 15.0, 0]]
    assert [h[1] for h in hovers(chart(rows))] == [
        "Oct 14 5:00 PM window: 12.50 of 30 contracts filled (42%) · 1 of 2 orders got none · last 12 windows: 42%",
        "Oct 14 5:15 PM window: 15 of 15 contracts filled (100%) · 0 of 1 orders got none · last 12 windows: 61%"]


@needs_node
def test_a_marker_and_shading_where_fast_entry_went_live():
    rows = series()                                                                # 10 windows before, 10 from LIVE
    svg = chart(rows, FAST)
    x = xv(svg, rows)
    marks = els(svg, "line", "fr-mark")
    assert len(marks) == 1 and num(marks[0].attrs["x1"]) == pytest.approx(x(LIVE), abs=0.6) == num(marks[0].attrs["x2"])
    assert [t.text() for t in els(svg, "text", "fr-mark-t")] == ["fast entry"]
    shade = els(svg, "rect", "fr-after")
    assert len(shade) == 1
    left, w = num(shade[0].attrs["x"]), num(shade[0].attrs["width"])
    assert left == pytest.approx(x(LIVE), abs=0.6) and left + w == pytest.approx(x(rows[-1][0]), abs=0.6)


def avgs(svg):
    return [(num(a.attrs["x1"]), num(a.attrs["x2"]), num(a.attrs["y1"]), num(a.attrs["y2"])) for a in els(svg, "line", "fr-avg")]


@needs_node
def test_each_periods_average_is_a_level_line_across_its_part_of_the_chart():
    rows = series()
    svg = chart(rows, FAST)
    x, y = xv(svg, rows), yv(svg)
    (bx1, bx2, by1, by2), (ax1, ax2, ay1, ay2) = avgs(svg)                         # before, then since
    assert (bx1, bx2) == (pytest.approx(x(rows[0][0]), abs=0.6), pytest.approx(x(LIVE), abs=0.6))   # (4 days reach past the left)
    assert by1 == by2 == pytest.approx(y(12000 / 20000), abs=0.6)                  # 60%
    assert (ax1, ax2) == (pytest.approx(x(LIVE), abs=0.6), pytest.approx(x(rows[-1][0]), abs=0.6))
    assert ay1 == ay2 == pytest.approx(y(504 / 700), abs=0.6)                      # 72%
    assert [t.text() for t in els(svg, "text", "fr-avg-t")] == ["before: 60%", "since: 72%"]


@needs_node
def test_the_before_average_starts_4_days_before_go_live_when_the_chart_reaches_further_back():
    rows = series(40, LIVE - 5 * DAY) + series(10, LIVE)                           # five days back
    svg = chart(rows, FAST)
    x = xv(svg, rows)
    assert avgs(svg)[0][0] == pytest.approx(x(LIVE - 4 * DAY), abs=0.6)


@needs_node
def test_no_before_average_when_nothing_was_asked_before():
    svg = chart(series(), {**FAST, "before": EMPTY})
    assert len(avgs(svg)) == 1 and [t.text() for t in els(svg, "text", "fr-avg-t")] == ["since: 72%"]


@needs_node
@pytest.mark.parametrize("start, fast", [(LIVE + W15, FAST), (LIVE - 30 * W15, FAST), (LIVE - 10 * W15, None)],
                         ids=["all-after", "all-before", "no-fast"])
def test_no_marker_shading_or_averages_when_go_live_is_off_the_chart_or_unknown(start, fast):
    svg = chart(series(10, start), fast)                                           # all-before ends at LIVE - 21 windows
    assert not els(svg, "line", "fr-mark") and not els(svg, "rect", "fr-after") and not avgs(svg)
    assert "fast entry" not in svg


@needs_node
def test_the_marker_shows_when_go_live_is_the_first_or_the_last_window():
    assert els(chart(series(10, LIVE), FAST), "line", "fr-mark")
    assert els(chart(series(10, LIVE - 9 * W15), FAST), "line", "fr-mark")


@needs_node
def test_the_svg_is_one_image_with_a_spoken_summary():
    rows = series()
    svg = els(chart(rows, FAST), "svg")
    assert len(svg) == 1 and svg[0].has_class("fr") and svg[0].attrs.get("role") == "img"
    label = svg[0].attrs["aria-label"]
    assert label.startswith(f"Share of contracts filled in each 15-minute window: 20 windows, Oct 14 2:30 PM to Oct 14 7:15 PM.")
    assert "Since fast entry: 72% of contracts filled and 10% of orders got none; the 4 days before: 60% and 25%." in label
    vb = svg[0].attrs["viewbox"].split()
    assert vb[:2] == ["0", "0"] and vb[2] == svg[0].attrs["width"] == "720"


@needs_node
def test_the_summary_leaves_out_an_empty_before():
    label = els(chart(series(), {**FAST, "before": EMPTY}), "svg")[0].attrs["aria-label"]
    assert "Since fast entry: 72% of contracts filled and 10% of orders got none." in label and "before" not in label


@needs_node
@pytest.mark.parametrize("rows", [[[LIVE, 1, 15.0, 4.0, 0]], [[LIVE, 1, 0.0, 0.0, 1]]], ids=["one-window", "nothing-asked"])
def test_one_window_draws_without_nan(rows):
    out = chart(rows, FAST)
    assert "NaN" not in out and "Infinity" not in out and els(out, "svg")


@needs_node
def test_the_chart_takes_the_width_its_given():
    for w in (300, 1100):
        out = chart(series(), FAST, w)
        svg = els(out, "svg")[0]
        assert svg.attrs["width"] == str(w) and svg.attrs["viewbox"].split()[2] == str(w)
        assert max(p[0] for p in line_pts(out)) < w


# ------------------------------------------------------------------ the fold
STATE = {"fillWindows": series(), "fillsFast": FAST}


@needs_node
def test_the_fold_is_fill_rate_open_at_first_with_the_chart_in_its_body():
    sec, head, body, lines, markup = fold_of(STATE)
    assert sec.attrs.get("data-fold-key") == "live.fills" and sec.attrs.get("data-open") == "true"
    assert "Fill rate" in head.text()
    assert [e for e in body.els() if e.tag == "svg" and e.has_class("fr")]


def tiles(body):
    """Each headline tile: (label, value, sub line, delta, the delta's classes)."""
    boxes = [e for e in body.els() if e.has_class("fr-tiles")]
    if not boxes:
        return []
    assert len(boxes) == 1
    out = []
    for tile in boxes[0].children():
        assert tile.has_class("fr-tile"), f"a .fr-tiles child is <{tile.tag} class={tile.attrs.get('class')!r}>"
        part = lambda c: [e for e in tile.els() if e.has_class(c)]
        (tl,), (tv,), (ts,), td = part("fr-tl"), part("fr-tv"), part("fr-ts"), part("fr-td")
        out.append((tl.text(), tv.text(), ts.text(), td[0].text() if td else None,
                    set(td[0].attrs.get("class", "").split()) - {"fr-td"} if td else None))
    return out


@needs_node
def test_two_tiles_lead_with_the_answer_before_the_chart():
    _, _, body, _, markup = fold_of(STATE)
    assert tiles(body) == [("Contracts filled", "72%", "since fast entry · was 60%", "▲ 12 pts", {"up"}),
                           ("Orders that got nothing", "10%", "since fast entry · was 25%", "▼ 15 pts", {"up"})]
    assert markup.index('class="fr-tiles"') < markup.index('class="sub-note"') < markup.index("<svg")


@needs_node
def test_the_caption_says_what_the_line_is_and_which_way_is_better():
    _, _, body, _, _ = fold_of(STATE)
    notes = [e.text() for e in body.els() if e.has_class("sub-note")]
    assert notes == ["The line is the share of contracts asked for that filled, over the last 12 windows the bot placed orders in "
                     "(about 3 hours). Higher is better. The dashed lines are each period's average."]   # (test_fill_off.py)


@needs_node
@pytest.mark.parametrize("before, after, filled, got_none", [
    ({"orders": 10, "asked": 100, "filled": 70, "none": 1}, {"orders": 10, "asked": 100, "filled": 60, "none": 3},
     ("60%", "▼ 10 pts", {"down"}), ("30%", "▲ 20 pts", {"down"})),                 # worse on both: red
    ({"orders": 10, "asked": 100, "filled": 60, "none": 2}, {"orders": 10, "asked": 100, "filled": 61, "none": 2},
     ("61%", "▲ 1 pt", {"up"}), ("20%", "no change", {"muted"})),                   # one point; none at all
    ({"orders": 3, "asked": 300, "filled": 200.4, "none": 1}, {"orders": 3, "asked": 300, "filled": 199.6, "none": 1},
     ("67%", "no change", {"muted"}), ("33%", "no change", {"muted"})),              # 66.8% and 66.5%: the rounded figures
], ids=["worse", "one-point", "rounded-same"])
def test_the_change_is_in_whole_points_of_the_rounded_figures_coloured_by_better_or_worse(before, after, filled, got_none):
    _, _, body, _, _ = fold_of({**STATE, "fillsFast": {"live": LIVE, "before": before, "after": after}})
    (_, fv, _, fd, ft), (_, nv, _, nd, nt) = tiles(body)
    assert (fv, fd, ft) == filled and (nv, nd, nt) == got_none


@needs_node
def test_with_nothing_before_the_tiles_have_no_was_and_no_change():
    _, _, body, _, _ = fold_of({**STATE, "fillsFast": {**FAST, "before": EMPTY}})
    assert tiles(body) == [("Contracts filled", "72%", "since fast entry", None, None),
                           ("Orders that got nothing", "10%", "since fast entry", None, None)]


@needs_node
@pytest.mark.parametrize("state", [{**STATE, "fillsFast": {**FAST, "after": EMPTY}}, {"fillWindows": series()}],
                         ids=["no-orders-since", "no-fast-figures"])
def test_no_tiles_without_orders_since_fast_entry(state):
    _, _, body, _, _ = fold_of(state)
    assert tiles(body) == [] and [e for e in body.els() if e.tag == "svg" and e.has_class("fr")]


@needs_node
def test_the_header_says_since_fast_entry_and_the_4_days_before():
    *_, lines, _ = fold_of(STATE)
    assert lines == ["since fast entry (Oct 14 5:00 PM): 72% of contracts filled · 10% of orders got none · 40 orders",
                     "the 4 days before: 60% filled · 25% got none · 1,234 orders"]


@needs_node
def test_with_no_orders_since_fast_entry_the_header_says_so():
    *_, lines, _ = fold_of({**STATE, "fillsFast": {**FAST, "after": EMPTY}})
    assert lines == ["fast entry live since Oct 14 5:00 PM: no orders yet", "the 4 days before: 60% filled · 25% got none · 1,234 orders"]


@needs_node
def test_with_nothing_before_the_header_is_the_one_line():
    *_, lines, _ = fold_of({**STATE, "fillsFast": {**FAST, "before": EMPTY}})
    assert lines == ["since fast entry (Oct 14 5:00 PM): 72% of contracts filled · 10% of orders got none · 40 orders"]


@needs_node
def test_an_old_server_gets_a_quiet_line_and_no_meta():
    _, _, body, lines, _ = fold_of({})
    assert lines == [] and "The fill-rate chart starts once the dashboard restarts" in body.text()
    assert not [e for e in body.els() if e.tag == "svg" and e.has_class("fr")]


@needs_node
def test_no_orders_in_the_last_7_days_says_so():
    _, _, body, _, _ = fold_of({"fillWindows": [], "fillsFast": {"live": LIVE, "before": EMPTY, "after": EMPTY}})
    assert "No buy orders in the last 7 days" in body.text() and not [e for e in body.els() if e.tag == "svg" and e.has_class("fr")]


@needs_node
def test_the_chart_is_as_wide_as_the_section():
    out = json.loads(block(STATE, width=1000))["fills"]
    assert els(out, "svg", "fr")[0].attrs["width"] == "1000"
    out = json.loads(block(STATE, width=200))["fills"]
    assert els(out, "svg", "fr")[0].attrs["width"] == "300"                     # never narrower than 300


# ------------------------------------------------------------------ the page around it
def test_the_section_sits_between_live_markets_and_orders_and_hides_on_the_research_tabs():
    assert HTML.index('<section id="board"') < HTML.index('<section id="fills" aria-label="Fill rate: contracts filled per window"></section>') < HTML.index('<section id="orders"')
    hidden = re.search(r'for \(const id of \[([^\]]*)\]\) \$\(id\)\.hidden = other;', SCRIPT)   # other: Live Research or Latency
    assert hidden and '"fills"' in hidden.group(1)
    empty = re.search(r'function renderEmpty\(\) \{.*?for \(const id of \[([^\]]*)\]\) patch\(id, ""\);', SCRIPT, re.S)
    assert empty and '"fills"' in empty.group(1)


def test_the_fold_is_in_the_fold_table_open_and_render_draws_it():
    folds = re.search(r"^const FOLDS = \{(.*?)^\};", SCRIPT, re.S | re.M).group(1)
    assert '"live.fills": true' in folds
    assert folds.index('"live.board"') < folds.index('"live.fills"') < folds.index('"live.orders"')   # Open all's order
    r = decl(SCRIPT, "render")
    assert "fillsBlock();" in r and r.index("fillsBlock();") < r.index("ordersBlock();")


@needs_node
def test_the_live_tab_draws_the_fold_between_live_markets_and_orders_and_loses_no_word():
    g = golden()
    page = run(inputs={**g, "state": {**g["state"], "fillWindows": series(), "fillsFast": FAST}})[0]
    keys = page.fold_keys()
    assert keys.index("live.board") < keys.index("live.fills") < keys.index("live.orders")
    f = page.fold("live.fills")
    assert f.shown and "since fast entry" in f.meta and "Contracts filled" in f.body.text() and "Higher is better" in f.body.text()
    assert not missing(page), f"words of today's Live tab are gone: {missing(page)}"


@needs_node
def test_the_live_tab_from_an_old_server_still_draws_the_fold():
    page = run()[0]                                                                # the baseline's state: no fill data
    assert "starts once the dashboard restarts" in page.fold("live.fills").body.text()


# ------------------------------------------------------------------ colours and marks (test_look's parser)
def test_the_line_colour_is_a_token():
    roots = [r for r in RULES if r.sheet == "dashboard.html" and ":root" in norm(r.selector)]
    got = [(r.media, norm(r.selector), v) for r in roots for p, v in r.decls if p == "--series-1"]
    assert got == [("", ":root", "#3987e5")], f"--series-1 isn't #3987e5 in the one :root: {got}"


def fr_rules():
    return [r for r in RULES if r.sheet == "dashboard.html" and any(re.search(r"\.fr(?:-[\w-]+)?\b", p) for p in r.parts)]


def fr_decl(cls, prop):
    vals = [dict(r.decls)[prop] for r in fr_rules() if prop in dict(r.decls) and any(norm(p).endswith(cls) for p in r.parts)]
    assert vals, f"no rule ending {cls} sets {prop}"
    return vals[-1]


def test_the_line_is_2px_in_the_series_colour():
    assert fr_decl(".fr-ln", "stroke") == "var(--series-1)" and fr_decl(".fr-ln", "stroke-width") in ("2", "2px")
    assert fr_decl(".fr-ln", "fill") == "none"


def test_the_averages_are_dashed_ink_and_the_gridlines_solid_hairlines():
    assert fr_decl(".fr-avg", "stroke") in ("var(--ink-2)", "var(--ink)", "var(--muted)")
    assert fr_decl(".fr-avg", "stroke-dasharray") not in ("", "none")
    assert fr_decl(".fr-avg-t", "fill") in ("var(--ink-2)", "var(--ink)")
    assert fr_decl(".fr-grid", "stroke") == "var(--line)" and fr_decl(".fr-grid", "stroke-width") in ("1", "1px")
    assert not [r for r in fr_rules() if any(norm(p).endswith(".fr-grid") for p in r.parts) and "stroke-dasharray" in dict(r.decls)]
    assert fr_decl(".fr-mark-t", "fill") in ("var(--ink-2)", "var(--ink)", "var(--muted)")


def test_the_shading_is_a_faint_wash():
    fill = fr_decl(".fr-after", "fill")
    if fill == "var(--series-1)":
        assert float(fr_decl(".fr-after", "fill-opacity")) <= 0.12
    else:
        assert fill in ("var(--hover)", "var(--surface-2)", "var(--up-wash)")


def test_the_tiles_values_use_the_type_scale():
    font = fr_decl(".fr-tv", "font")
    assert "var(--fs-5)" in font or "var(--fs-6)" in font


def test_no_raw_colour_in_the_charts_rules():
    raw = [(r.selector, p, v) for r in fr_rules() for p, v in r.decls
           if re.search(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?)\(", v)]
    assert not raw, raw
