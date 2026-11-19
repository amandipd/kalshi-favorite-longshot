"""The fill-rate chart leaves out the time the bot wasn't trading.

Added Oct 15, 2026: the time the bot wasn't active is left out of the fill rate, now and for later trades. The bot
auto-halted for about eight and a half hours that night (Kalshi unreachable), and had stopped or halted for shorter stretches before. It placed no orders then, so the tiles, the header
and the dashed averages, which only count orders, were never changed by it; but the line ran straight across each
stretch as if the bot had traded through it.

The server: dashboard.fill_off(rows, decisions) finds, between each two windows with a buy order (fill_windows' rows),
the windows the bot wasn't trading in: no decision logged (it wasn't running, or Kalshi listed nothing) or a 'halted'
one. Each gap with one gives a stretch [from, to, kind]: the first such window's start to the last one's end, "halted"
if a halt was logged in it, else "off". state() sends them as "fillOff", from the last 7 days' decisions.

The page: fillChart(rows, fast, W, off) breaks the line at each stretch (a new M, every point's value as before), draws a
hatched band over it (g.fr-off-g: a <title>, rect.fr-off, and a "halted" / "not trading" label when it fits), keeps the
hover columns out of it, and says how many it left out in its aria-label. fillsBlock() passes data.fillOff and adds a
sentence to the caption when a band is on the chart; the caption now says the 12 windows are ones the bot placed orders in.

    python -m pytest -q -p no:cacheprovider tests/test_fill_off.py tests/test_fill_chart.py
"""

import json
import re

import pytest

from kalshi_bot.web import dashboard
from test_dashboard_more import home, mode_db, order  # noqa: F401  (home is a fixture)
from test_fill_chart import (DAY, FAST, LIVE, W15, block, els, fr_rules, fr_decl, hovers, line_pts, node, num, piece,
                             scales, series, xv, yv)
from test_look import norm
from test_order_results import needs_node


def dec(w, action="skip", sec=480):
    """A decision the bot logged in window w (at minute 8 unless said)."""
    return (w + sec, action)


def r(w):
    """A fill_windows row: one order, 15 asked, 15 filled."""
    return [w, 1, 15.0, 15.0, 0]


# ------------------------------------------------------------------ the server: fill_off
def test_a_gap_the_bot_logged_nothing_in_is_off():
    rows = [r(LIVE), r(LIVE + 4 * W15)]
    assert dashboard.fill_off(rows, [dec(LIVE, "bet"), dec(LIVE + 4 * W15, "bet")]) == [[LIVE + W15, LIVE + 4 * W15, "off"]]


def test_a_halt_is_one_stretch_from_its_first_window_out_to_its_last():
    # between orders at 0 and 7: 1 quiet (skips), 2 silent, 3 halted, 4 only skips (nothing to bet while halted),
    # 5 halted, 6 quiet: the stretch is 2 to the end of 5, halted
    rows = [r(LIVE), r(LIVE + 7 * W15)]
    decisions = [dec(LIVE + W15), dec(LIVE + 3 * W15, "halted"), dec(LIVE + 3 * W15, "skip", 481),
                 dec(LIVE + 4 * W15), dec(LIVE + 5 * W15, "halted"), dec(LIVE + 6 * W15)]
    assert dashboard.fill_off(rows, decisions) == [[LIVE + 2 * W15, LIVE + 6 * W15, "halted"]]


def test_quiet_windows_the_bot_traded_through_are_not_left_out():
    rows = [r(LIVE), r(LIVE + 3 * W15)]
    assert dashboard.fill_off(rows, [dec(LIVE + W15), dec(LIVE + 2 * W15, "skip")]) == []


def test_next_door_windows_leave_nothing_out_and_neither_do_fewer_than_two():
    assert dashboard.fill_off([r(LIVE), r(LIVE + W15)], []) == []
    assert dashboard.fill_off([r(LIVE)], []) == [] and dashboard.fill_off([], [dec(LIVE, "halted")]) == []


def test_time_before_the_first_order_or_after_the_last_isnt_looked_at():
    rows = [r(LIVE), r(LIVE + W15)]
    assert dashboard.fill_off(rows, [dec(LIVE - 5 * W15, "halted"), dec(LIVE + 5 * W15, "halted")]) == []


def test_a_window_with_an_order_is_never_out_even_if_it_logged_a_halt():
    rows = [r(LIVE), r(LIVE + W15), r(LIVE + 2 * W15)]
    assert dashboard.fill_off(rows, [dec(LIVE + W15, "halted")]) == []


def test_a_decision_counts_for_its_window_whatever_its_second():
    rows = [r(LIVE), r(LIVE + 3 * W15)]
    assert dashboard.fill_off(rows, [(LIVE + W15, "skip"), (LIVE + 2 * W15 + 899.999, "skip")]) == []
    assert dashboard.fill_off(rows, [(LIVE + W15 + 899.999, "skip"), (LIVE + 2 * W15, "halted")]) == [
        [LIVE + 2 * W15, LIVE + 3 * W15, "halted"]]


def test_several_stretches_oldest_first_each_its_own_kind_and_decisions_in_any_order():
    rows = [r(LIVE), r(LIVE + 3 * W15), r(LIVE + 6 * W15), r(LIVE + 8 * W15)]
    decisions = [dec(LIVE + 7 * W15), dec(LIVE + 5 * W15, "halted"), dec(LIVE + 4 * W15), dec(LIVE + 2 * W15)]
    assert dashboard.fill_off(rows, decisions) == [[LIVE + W15, LIVE + 2 * W15, "off"], [LIVE + 5 * W15, LIVE + 6 * W15, "halted"]]


# ------------------------------------------------------------------ the server: state()
def decide(db, ts, ticker, action="skip"):
    db.execute("INSERT INTO decisions (ts, ticker, series, action, reason) VALUES (?,?,?,?,?)",
               (ts, ticker, ticker.split("-")[0], action, "x"))


def test_the_state_sends_the_stretches_the_chart_leaves_out(home):
    home.clock[0] = LIVE + DAY
    db = mode_db(home, "live-prod")
    order(db, LIVE + 480, "KXBTC15M-A")
    decide(db, LIVE + 480, "KXBTC15M-A", "bet")
    decide(db, LIVE + 2 * W15 + 480, "KXETH15M-H", "halted")                       # 1 silent, 2 halted, 3 silent
    order(db, LIVE + 4 * W15 + 480, "KXBTC15M-B")
    decide(db, LIVE + 4 * W15 + 480, "KXBTC15M-B", "bet")
    decide(db, LIVE + 5 * W15 + 480, "KXETH15M-Q")                                  # 5 quiet: traded through
    order(db, LIVE + 6 * W15 + 480, "KXBTC15M-C")
    db.commit()
    s = dashboard.state("live-prod")
    assert [w[0] for w in s["fillWindows"]] == [LIVE, LIVE + 4 * W15, LIVE + 6 * W15]
    assert s["fillOff"] == [[LIVE + W15, LIVE + 4 * W15, "halted"]]
    json.dumps(s["fillOff"])                                                         # the API sends JSON


def test_with_no_orders_nothing_is_left_out(home):
    home.clock[0] = LIVE + DAY
    db = mode_db(home, "live-prod")
    decide(db, LIVE + 480, "KXETH15M-H", "halted")
    db.commit()
    assert dashboard.state("live-prod")["fillOff"] == []


def test_only_the_charts_7_days_are_looked_at(home):
    home.clock[0] = LIVE + 8 * DAY
    db = mode_db(home, "live-prod")
    order(db, LIVE + 480, "KXBTC15M-OLD")                                            # 8 days old: off the chart
    order(db, LIVE + 4 * W15 + 480, "KXBTC15M-OLD2")
    order(db, LIVE + 7 * DAY + 480, "KXBTC15M-A")
    order(db, LIVE + 7 * DAY + 3 * W15 + 480, "KXBTC15M-B")
    decide(db, LIVE + 7 * DAY + W15 + 480, "KXETH15M-Q")
    db.commit()
    assert dashboard.state("live-prod")["fillOff"] == [[LIVE + 7 * DAY + 2 * W15, LIVE + 7 * DAY + 3 * W15, "off"]]


# ------------------------------------------------------------------ the page: the chart
def chart(rows, fast=None, w=720, off=None, args=4):
    """What fillChart draws, given the stretches (args=3: called the old way, without them)."""
    call = "fillChart(p.rows, p.fast, p.w)" if args == 3 else "fillChart(p.rows, p.fast, p.w, p.off)"
    return node("\n".join([piece("fillChart"), "const p = JSON.parse(require('fs').readFileSync(0, 'utf8'));",
                           f"process.stdout.write({call});"]), {"rows": rows, "fast": fast, "w": w, "off": off})


GAP = series(8, LIVE - 10 * W15) + series(8, LIVE + 6 * W15)       # LIVE-10..-3, then LIVE+6..+13: 8 windows with none
HALT = [LIVE - W15, LIVE + 5 * W15, "halted"]                        # (LIVE-2 was a quiet window: traded through)
THREE = series(5, LIVE - 10 * W15) + series(5, LIVE - 3 * W15) + series(5, LIVE + 5 * W15)
TWO = [[LIVE - 5 * W15, LIVE - 3 * W15, "off"], [LIVE + 2 * W15, LIVE + 5 * W15, "halted"]]


def subpaths(svg):
    ps = els(svg, "path", "fr-ln")
    assert len(ps) == 1, f"{len(ps)} path.fr-ln: the line stays one path"
    return [[(float(a), float(b)) for a, b in re.findall(r"(?:^|L)\s*(-?[\d.]+)[ ,]\s*(-?[\d.]+)", sub.strip())]
            for sub in ps[0].attrs["d"].split("M")[1:]]


def bands(svg):
    """[(rect, title, labels)] for each band, in order, after checking its markup."""
    out = []
    for g in els(svg, "g", "fr-off-g"):
        titles = [e for e in g.children() if e.tag == "title"]
        rects = [e for e in g.els() if e.tag == "rect" and e.has_class("fr-off")]
        assert len(titles) == 1 and len(rects) == 1, "a .fr-off-g holds one <title> and one rect.fr-off"
        out.append((rects[0], titles[0].text(), [t for t in g.els() if t.tag == "text" and t.has_class("fr-off-t")]))
    assert len(out) == len(els(svg, "rect", "fr-off")), "a rect.fr-off outside a .fr-off-g"
    return out


@needs_node
@pytest.mark.parametrize("off", [None, []], ids=["null", "empty"])
def test_without_stretches_the_chart_is_drawn_as_before(off):
    old = chart(GAP, FAST, args=3)
    assert chart(GAP, FAST, off=off) == old
    assert len(subpaths(old)) == 1 and not bands(old) and "fr-hatch" not in old and "Left out" not in old


@needs_node
def test_the_line_breaks_across_a_stretch_and_every_point_keeps_its_value():
    svg = chart(GAP, FAST, off=[HALT])
    parts = subpaths(svg)
    assert [len(p) for p in parts] == [8, 8]
    assert [pt for p in parts for pt in p] == pytest.approx(line_pts(chart(GAP, FAST)), abs=0.05)   # same points, unjoined


@needs_node
def test_two_stretches_break_it_twice():
    assert [len(p) for p in subpaths(chart(THREE, FAST, off=TWO))] == [5, 5, 5]


@needs_node
def test_a_hatched_band_over_the_stretch_the_plots_full_height():
    svg = chart(GAP, FAST, off=[HALT])
    x = xv(svg, GAP)
    y0, y100 = scales(svg)
    (rect, _, _), = bands(svg)
    left, w = num(rect.attrs["x"]), num(rect.attrs["width"])
    assert left == pytest.approx(x(HALT[0]), abs=0.6) and left + w == pytest.approx(x(HALT[1]), abs=0.6)
    assert num(rect.attrs["y"]) == pytest.approx(y100, abs=1) and num(rect.attrs["height"]) == pytest.approx(y0 - y100, abs=1)


@needs_node
@pytest.mark.parametrize("kind, said", [("halted", "Bot halted"), ("off", "Bot not trading")])
def test_the_band_says_what_happened_on_hover(kind, said):
    (_, title, _), = bands(chart(GAP, FAST, off=[[HALT[0], HALT[1], kind]]))
    assert title == f"{said}: Oct 14 4:45 PM to Oct 14 6:15 PM · left out of the line"


@needs_node
@pytest.mark.parametrize("kind, label", [("halted", "halted"), ("off", "not trading")])
def test_a_wide_band_is_labelled_at_its_middle_near_the_bottom(kind, label):
    svg = chart(GAP, FAST, off=[[HALT[0], HALT[1], kind]])                          # 6 windows: about 150px
    x = xv(svg, GAP)
    y0, _ = scales(svg)
    (_, _, labels), = bands(svg)
    assert [t.text() for t in labels] == [label] and labels[0].attrs.get("text-anchor") == "middle"
    assert num(labels[0].attrs["x"]) == pytest.approx((x(HALT[0]) + x(HALT[1])) / 2, abs=0.6)
    assert y0 - 14 <= num(labels[0].attrs["y"]) <= y0 - 2


@needs_node
def test_a_narrow_band_has_no_label():
    rows = series(8, LIVE - 10 * W15) + series(8, LIVE - W15)                      # one window with none: about 25px
    (_, title, labels), = bands(chart(rows, FAST, off=[[LIVE - 2 * W15, LIVE - W15, "halted"]]))
    assert labels == [] and title.startswith("Bot halted: ")


@needs_node
def test_hover_columns_stop_at_a_band_and_there_is_still_one_per_window():
    for rows, off in ((GAP, [HALT]), (THREE, TWO)):
        svg = chart(rows, FAST, off=off)
        hs, bs = hovers(svg), bands(svg)
        assert len(hs) == len(rows) and len(bs) == len(off)
        for rect, _ in hs:
            l, rr = num(rect.attrs["x"]), num(rect.attrs["x"]) + num(rect.attrs["width"])
            for band, _, _ in bs:
                bl, br = num(band.attrs["x"]), num(band.attrs["x"]) + num(band.attrs["width"])
                assert min(rr, br) - max(l, bl) <= 0.6, f"a hover column [{l}, {rr}] reaches into a band [{bl}, {br}]"


@needs_node
def test_the_band_sits_over_the_shading_and_under_the_gridlines_and_the_line():
    svg = chart(GAP, FAST, off=[HALT])
    assert svg.index('class="fr-after"') < svg.index('class="fr-off-g"') < svg.index('class="fr-grid"') < svg.index('class="fr-ln"')


@needs_node
def test_a_band_is_drawn_without_fast_entry_on_the_chart_too():
    assert len(bands(chart(GAP, None, off=[HALT]))) == 1


@needs_node
def test_the_hatch_is_a_pattern_in_the_charts_defs_only_when_a_band_is_drawn():
    svg = chart(GAP, FAST, off=[HALT])
    defs = els(svg, "defs")
    pats = [p for d in defs for p in d.els() if p.tag == "pattern" and p.attrs.get("id") == "fr-hatch"]
    assert len(pats) == 1 and pats[0].attrs.get("patternunits") == "userSpaceOnUse"
    assert "fr-hatch" not in chart(GAP, FAST, off=[])


@needs_node
@pytest.mark.parametrize("off", [[[LIVE + 20 * W15, LIVE + 22 * W15, "off"]], [[LIVE - 30 * W15, LIVE - 20 * W15, "halted"]],
                                 [[LIVE + W15, LIVE + W15, "off"]]], ids=["after", "before", "empty"])
def test_a_stretch_off_the_chart_or_empty_isnt_drawn(off):
    svg = chart(GAP, FAST, off=off)
    assert not bands(svg) and len(subpaths(svg)) == 1 and "fr-hatch" not in svg and "Left out" not in svg


@needs_node
def test_a_stretch_reaching_past_the_chart_is_clipped_to_it():
    svg = chart(GAP, FAST, off=[[LIVE - 2 * W15, LIVE + 40 * W15, "off"]])           # past the last window
    x = xv(svg, GAP)
    (rect, _, _), = bands(svg)
    assert num(rect.attrs["x"]) + num(rect.attrs["width"]) == pytest.approx(x(GAP[-1][0]), abs=0.6)
    assert len(subpaths(svg)) == 2


@needs_node
def test_the_summary_says_how_many_stretches_it_left_out():
    one = els(chart(GAP, FAST, off=[HALT]), "svg")[0].attrs["aria-label"]
    two = els(chart(THREE, FAST, off=TWO), "svg")[0].attrs["aria-label"]
    assert one.endswith(" Left out: 1 stretch when the bot wasn't trading.")
    assert two.endswith(" Left out: 2 stretches when the bot wasn't trading.")


@needs_node
def test_no_nan_with_a_band_on_a_one_window_chart_or_beside_the_only_window():
    for rows, off in (([[LIVE, 1, 15.0, 4.0, 0]], [[LIVE - W15, LIVE, "off"]]),
                      ([[LIVE, 1, 15.0, 4.0, 0], [LIVE + 3 * W15, 1, 0.0, 0.0, 1]], [[LIVE + W15, LIVE + 3 * W15, "halted"]])):
        out = chart(rows, FAST, off=off)
        assert "NaN" not in out and "Infinity" not in out and els(out, "svg")


# ------------------------------------------------------------------ the fold
CAPTION = ("The line is the share of contracts asked for that filled, over the last 12 windows the bot placed orders in "
           "(about 3 hours). Higher is better. The dashed lines are each period's average.")
BANDS_SAID = " Hatched bands are times the bot wasn't trading; they're left out."


def caption(state):
    out = json.loads(block(state))["fills"]
    notes = [e.text() for e in els(out, cls="sub-note")]
    assert len(notes) == 1
    return notes[0], out


@needs_node
def test_the_fold_draws_the_servers_stretches_and_says_so():
    note, out = caption({"fillWindows": GAP, "fillsFast": FAST, "fillOff": [HALT]})
    assert note == CAPTION + BANDS_SAID
    assert len(bands(out)) == 1


@needs_node
@pytest.mark.parametrize("state", [{"fillWindows": GAP, "fillsFast": FAST},
                                   {"fillWindows": GAP, "fillsFast": FAST, "fillOff": []},
                                   {"fillWindows": GAP, "fillsFast": FAST, "fillOff": [[LIVE + 20 * W15, LIVE + 22 * W15, "off"]]}],
                         ids=["old-server", "none", "off-the-chart"])
def test_no_bands_no_sentence(state):
    note, out = caption(state)
    assert note == CAPTION and not bands(out)


@needs_node
def test_the_tiles_and_header_dont_change_with_stretches():
    a = json.loads(block({"fillWindows": GAP, "fillsFast": FAST}))["fills"]
    b = json.loads(block({"fillWindows": GAP, "fillsFast": FAST, "fillOff": [HALT]}))["fills"]
    cut = lambda html: html[:html.index('class="sub-note"')]                       # the header and the tiles
    assert cut(a) == cut(b)


# ------------------------------------------------------------------ colours (test_look's parser)
def test_the_band_is_filled_with_the_hatch():
    assert fr_decl(".fr-off", "fill") == "url(#fr-hatch)"


def test_the_hatch_strokes_and_the_band_label_use_tokens():
    hatch = [dict(r.decls) for r in fr_rules() if any(".fr-hatch" in norm(p) for p in r.parts)]
    strokes = [d["stroke"] for d in hatch if "stroke" in d]
    assert strokes and all(s in ("var(--line-strong)", "var(--line)", "var(--muted)") for s in strokes), hatch
    assert fr_decl(".fr-off-t", "fill") in ("var(--muted)", "var(--ink-2)")
