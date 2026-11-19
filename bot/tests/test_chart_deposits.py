"""The Live chart in dollars without cliffs at deposits, the way brokerage apps draw it. On a live account the chart
used to draw Kalshi's raw value, so each deposit was a sheer step that dwarfed every bet and stretched the axis. Now money put in or taken out lifts (or lowers) the line before it instead:
each step is what the bets made, the line still ends at the account's real value (the Portfolio figure), and the
deposit is a marker on the line, not a jump in it.

dollarLine(pts, real) gives the value drawn at each of the chart's points ([t, value, money in or out, what]): on the
real account, the value plus all the money put in (less taken out) after that point; on the bot's own curve, the value.
The % view already left deposits out, and stays as it was. The tooltip shows the drawn value as "Account", and the
real balance then as "Then in the account" wherever the two differ.

dollarLine is cut out of the page and run in node, and chart() and bindChart() are run for real with the stand-in DOM
of test_loss_windows.py, reading the SVG they draw and the tooltips they fill in. Skipped without node.
    python -m pytest tests/test_chart_deposits.py -q
"""
import random
import re

import pytest

from test_loss_windows import CHART, C, H, M_B, M_T, helpers, needs_node, node, piece, plain, tags

T0 = C - 7200


# ------------------------------------------------------------------ dollarLine(): the values drawn
def with_dollar_line():
    """The page's helpers with dollarLine, which must be there (helpers() takes it only when it is)."""
    h = helpers()
    return h if re.search(r"^function dollarLine\(", h, re.M) else h + "\n" + piece(r"^function dollarLine\(.*?^\}$|^const dollarLine = [^\n]*$")


def lines(*calls):
    """dollarLine(pts, real) for each (pts, real), in one node process."""
    src = "\n".join([with_dollar_line(),
                     "const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));",
                     "process.stdout.write(JSON.stringify(input.map(([pts, real]) => dollarLine(pts, real))));"])
    return node(src, [list(c) for c in calls])


def line(pts, real=True):
    return lines((pts, real))[0]


def pts_of(start, *events, t=T0):
    """Real-account points from a value and events (change in value, money in or out, what), 10 minutes apart."""
    out, value = [[t, start, 0, "start"]], start
    for i, (dv, money, what) in enumerate(events, 1):
        value = round(value + dv, 4)
        out.append([t + 600 * i, value, money, what])
    return out


DEPOSIT = pts_of(500.0, (+10.0, 0, "1 won"), (+400.0, 400, "deposit"), (-5.0, 0, "1 lost"), (+15.0, 0, "2 won"))
SMOOTH = [900.0, 910.0, 910.0, 905.0, 920.0]          # each point before the $400 lifted by it


@needs_node
def test_a_deposit_lifts_the_line_before_it_instead_of_jumping_it():
    got = line(DEPOSIT)
    assert got == pytest.approx(SMOOTH)
    assert got[2] - got[1] == pytest.approx(0)                           # no step where the $400 came in ...
    assert got[-1] == pytest.approx(DEPOSIT[-1][1])                      # ... and it ends at the account's real value
    assert [g - p[1] for g, p in zip(got, DEPOSIT)] == pytest.approx([400, 400, 0, 0, 0])


@needs_node
def test_with_no_money_in_or_out_the_line_is_the_value():
    pts = pts_of(500.0, (+10.0, 0, "1 won"), (-5.0, 0, "1 lost"), (+0.37, 0, "now"))
    assert line(pts) == pytest.approx([p[1] for p in pts])


@needs_node
def test_a_withdrawal_lowers_the_line_before_it():
    pts = pts_of(500.0, (+10.0, 0, "1 won"), (-100.0, -100, "withdrawal"), (+3.0, 0, "1 won"))
    assert line(pts) == pytest.approx([400.0, 410.0, 410.0, 413.0])


@needs_node
def test_each_deposit_lifts_only_what_came_before_it():
    pts = pts_of(500.0, (+150.0, 150, "deposit"), (-12.0, 0, "1 lost"), (+250.0, 250, "deposit"), (+4.0, 0, "1 won"),
                 (+350.0, 350, "deposit"), (+1.5, 0, "1 won"))
    got = line(pts)
    assert got[0] == pytest.approx(500.0 + 750)
    assert [g - p[1] for g, p in zip(got, pts)] == pytest.approx([750, 600, 600, 350, 350, 0, 0])


@needs_node
def test_money_marked_on_the_first_point_is_ignored():
    """The first point is where the range starts: money in or out on it happened before the line does."""
    marked = [list(p) for p in DEPOSIT]
    marked[0][2] = 50
    assert line(marked) == pytest.approx(SMOOTH)


@needs_node
def test_the_bots_own_curve_is_drawn_as_it_is():
    pts = [[p[0], p[1], p[2], p[3]] for p in DEPOSIT]
    assert line(pts, real=False) == pytest.approx([p[1] for p in DEPOSIT])          # even with money marked on it
    assert line([[T0, 100.0], [T0 + 60, 97.0], [T0 + 120, 98.5]], real=False) == pytest.approx([100.0, 97.0, 98.5])


@needs_node
def test_it_leaves_the_points_alone():
    src = "\n".join([with_dollar_line(),
                     "const pts = JSON.parse(require('fs').readFileSync(0, 'utf8')), before = JSON.stringify(pts);",
                     "dollarLine(pts, true); dollarLine(pts, false);",
                     "process.stdout.write(JSON.stringify(JSON.stringify(pts) === before));"])
    assert node(src, DEPOSIT) is True


@needs_node
@pytest.mark.parametrize("pts", [[], [[T0, 500.0, 0, "start"]]], ids=["none", "one"])
def test_too_few_points(pts):
    assert line(pts) == pytest.approx([p[1] for p in pts])


def random_curve(rng):
    value = round(rng.uniform(50, 2000), 4)
    pts = [[T0, value, rng.choice([0, 0, 25]), "start"]]              # (money on the first point is ignored)
    for i in range(1, rng.randrange(2, 40)):
        money = rng.choice([0] * 6 + [round(rng.uniform(1, 500), 2), -round(rng.uniform(1, 200), 2)])
        dv = money + round(rng.uniform(-16, 4), 4)
        value = round(value + dv, 4)
        pts.append([T0 + 60 * i, value, money, "deposit" if money > 0 else "withdrawal" if money < 0 else "1 won"])
    return pts


@needs_node
def test_every_step_is_the_bets_alone_and_it_ends_at_the_real_value():
    rng = random.Random(1011)
    curves = [random_curve(rng) for _ in range(300)]
    for pts, got in zip(curves, lines(*((c, True) for c in curves))):
        assert got[-1] == pytest.approx(pts[-1][1], abs=1e-6)
        for i in range(1, len(pts)):
            assert got[i] - got[i - 1] == pytest.approx(pts[i][1] - pts[i - 1][1] - pts[i][2], abs=1e-6), (pts, i)


def typical_curve():
    """A typical live-account curve: small wins, a few $10-16 losses, and three made-up deposits."""
    rng, events, deposits = random.Random(11), [], {40: 150.0, 120: 250.0, 200: 350.0}
    for i in range(240):
        if i in deposits:
            events.append((deposits[i], deposits[i], "deposit"))
        elif rng.random() < 0.06:
            events.append((-round(rng.uniform(9, 16), 2), 0, "1 lost"))
        else:
            events.append((round(rng.uniform(0.2, 1.2), 2), 0, "1 won"))
    return pts_of(500.0, *events)


@needs_node
def test_on_a_typical_curve_the_biggest_step_is_a_bet_not_a_deposit():
    pts = typical_curve()
    raw = [abs(pts[i][1] - pts[i - 1][1]) for i in range(1, len(pts))]
    assert pts[1 + raw.index(max(raw))][3] == "deposit"                 # drawn raw, the $350 towers over every bet
    got = line(pts)
    steps = [abs(got[i] - got[i - 1]) for i in range(1, len(got))]
    biggest = 1 + steps.index(max(steps))
    assert re.search(r"\b(won|lost)\b", pts[biggest][3]) and max(steps) <= 16


# ------------------------------------------------------------------ chart(): what it draws
def draw(data, range_="all", unit="usd", keys=(), width=800):
    js = "\n".join([helpers(), piece(r"^function niceTicks\(lo, hi, n\) \{.*?^\}$"), piece(r"^function tableView\(pts, real\) \{.*?^\}$"),
                    piece(r"^function chart\(\) \{.*?^\}$"), piece(r"^function bindChart\(\) \{.*?^\}$"), CHART])
    return node(js, {"data": data, "range": range_, "width": width, "view": "chart", "unit": unit, "keys": list(keys)})


# the deposit curve with a point before it, so the 1H chart has a "1H AGO" start: the same five values either way
REAL = {"now": T0 + 2460, "start": 500.0, "curve": [], "kalshiCurve": [[T0 - 5000, 500.0, 0, "start"], *DEPOSIT[1:]]}
BOT = {"now": T0 + 2460, "start": 480.0, "kalshiCurve": None,
       "curve": [[T0 - 5000, 500.0], [T0 + 600, 510.0], [T0 + 1200, 497.0], [T0 + 1800, 492.0], [T0 + 2400, 507.0]]}


def path_ys(svg):
    d = re.search(r'<path class="ln" d="([^"]+)"', svg).group(1)
    return [float(y) for _, y in re.findall(r"[ML](-?[\d.]+),(-?[\d.]+)", d)]


def on_scale(ys, values):
    """The chart's y as a function of value, checked to put every drawn point at its value (to 0.15 px)."""
    lo, hi = values.index(min(values)), values.index(max(values))
    k = (ys[hi] - ys[lo]) / (values[hi] - values[lo])
    y = lambda v: ys[lo] + (v - values[lo]) * k                             # noqa: E731
    assert [y(v) for v in values] == pytest.approx(ys, abs=0.15), "the line isn't drawn at these values"
    return y


@needs_node
@pytest.mark.parametrize("range_", ["all", "1h"])
def test_the_real_account_is_drawn_without_a_cliff_at_the_deposit(range_):
    svg = draw(REAL, range_)["svg"]
    y = on_scale(path_ys(svg), SMOOTH)
    (dep,) = tags(svg, "circle", "dep")
    assert float(dep["cy"]) == pytest.approx(y(910.0), abs=0.15)          # the deposit marked on the smooth line
    assert ">$920.00</text>" in svg                                         # the tag at the end: the real value now


@needs_node
@pytest.mark.parametrize("range_, tag", [("all", "START"), ("1h", "1H AGO")])
def test_the_start_line_is_where_the_drawn_line_starts(range_, tag):
    svg = draw(REAL, range_)["svg"]
    y = on_scale(path_ys(svg), SMOOTH)
    (ref,) = tags(svg, "line", "ref")
    assert float(ref["y1"]) == pytest.approx(y(SMOOTH[0]), abs=0.15)      # $900, not the $500 before the deposit
    assert f">{tag}</text>" in svg


@needs_node
def test_a_deposit_no_longer_stretches_the_axis():
    svg = draw(REAL)["svg"]
    y = on_scale(path_ys(svg), SMOOTH)
    per_dollar = y(1.0) - y(0.0)
    grid = [SMOOTH[0] + (float(g["y1"]) - y(SMOOTH[0])) / per_dollar for g in tags(svg, "line", "grid-l")]
    assert len(grid) >= 2 and max(grid) - min(grid) < 50 and min(grid) > 850   # the bets' $20, not the $400 below


@needs_node
def test_the_biggest_step_drawn_is_a_bet():
    data = {"now": T0 + 600 * 241, "start": 500.0, "curve": [], "kalshiCurve": typical_curve()}
    ys = path_ys(draw(data)["svg"])
    steps = [abs(ys[i] - ys[i - 1]) for i in range(1, len(ys))]
    assert re.search(r"\b(won|lost)\b", data["kalshiCurve"][1 + steps.index(max(steps))][3])


@needs_node
def test_the_bots_own_curve_and_the_percent_view_are_as_they_were():
    svg = draw(BOT)["svg"]
    y = on_scale(path_ys(svg), [p[1] for p in BOT["curve"]])
    assert float(tags(svg, "line", "ref")[0]["y1"]) == pytest.approx(y(480.0), abs=0.15)   # from the bot's start
    svg = draw(REAL, unit="pct")["svg"]
    on_scale(path_ys(svg), [0.0, 2.0, 2.0, 1.0, 4.0])                     # % of $500, deposits left out as before


@needs_node
def test_screen_readers_hear_how_the_line_treats_deposits():
    label = re.search(r'<svg class="cv[^"]*"[^>]*aria-label="([^"]*)"', draw(REAL)["svg"]).group(1)
    assert label.startswith("Your Kalshi account's value, from $900.00 to $920.00: money put in or taken out lifts the"
                            " line before it rather than jumping it, so its rise is what the bets made. Deposits and"
                            " withdrawals are marked.")
    bot = re.search(r'<svg class="cv[^"]*"[^>]*aria-label="([^"]*)"', draw(BOT)["svg"]).group(1)
    assert bot.startswith("Bankroll after each settled bet, from $480.00 to $507.00.")


# ------------------------------------------------------------------ the tooltip
def rows(tip):
    """The tooltip's rows, label: value."""
    return {plain(k).strip(): plain(v or "").strip() for k, v in re.findall(r'<div class="t-row"><span>(.*?)</span>(?:<b[^>]*>(.*?)</b>)?', tip)}


@needs_node
def test_the_tooltip_gives_the_drawn_value_and_the_real_balance_then():
    tips = [rows(t) for t in draw(REAL, keys=["focus", "Home"] + ["ArrowRight"] * 4)["tips"]]
    now, first, won, deposit, lost, last = tips
    assert first["Account"] == "$900.00" and first["Then in the account"] == "$500.00"
    assert won["Account"] == "$910.00" and won["Then in the account"] == "$510.00"
    assert deposit["Account"] == "$910.00" and "Then in the account" not in deposit   # the same from here on
    assert deposit["Deposit"] == "+$400.00"
    assert lost["Account"] == "$905.00" and "Then in the account" not in lost
    assert now == last and now["Account"] == "$920.00" and "Then in the account" not in now
    assert now["Profit since start"] == "▲ +$20.00 · +4.0%"                 # the bets' $20 on $500, as before


@needs_node
def test_the_bots_own_tooltip_has_no_second_balance():
    tips = draw(BOT, keys=["focus", "Home", "ArrowRight"])["tips"]
    assert all("Then in the account" not in t for t in tips)
    assert rows(tips[1])["Bankroll"] == "$500.00"
