"""The Backtest tab: the live bot's own rules, replayed on every window each market has ever had.

Added on Oct 28, 2026: a tab with the bot's exact strategy, tested since each of the markets opened. It is deliberately
smaller than the Historical Research tab that left on Oct 15 (four views, five bot
versions, a capital slider): one view, one account, and a row per market measured from that market's own first window.

The account it draws is the research backtest's "mine4liq" — version 4's rules, which are the live bot's today (92c
floor, 1.5% a bet, 10% a window, the $700 stop, both warning signs, minute 8, Fed blackouts), with each order filled
only as far as Kalshi's trade tape says it could have been. That last part is why it is the one worth showing: with
every order filled in full the same rules read about +3,400%, and capped at real book depth they read about +63%.

The tab's own file is loaded in node and handed studies shaped like /api/research, so these tests check what it says,
not how it lays it out. The node tests skip themselves without node.

    python -m pytest tests/test_backtest_page.py -q
"""
import json
import math
import os
import re
import subprocess

import pytest

from kalshi_bot.web import dashboard
from test_live_research_page import (CUTTER, HELPERS, HERE, NODE, code, needs_node, norm, own, piece, text,
                                     top_level)

HTML = open(os.path.join(HERE, "dashboard.html"), encoding="utf-8").read()
SCRIPT = re.search(r"<script>\n\"use strict\";(.*?)</script>", HTML, re.S).group(1)

TAB, FILE = "backtest", "backtest.js"
ENTRY, MARKUP = "window.backtestView", "window.backtestHtml"


def body(signature):
    assert signature in SCRIPT, f"dashboard.html no longer has {signature!r}"
    return SCRIPT.split(signature)[1].split("\n}\n")[0]


# ------------------------------------------------------------------ a study shaped like /api/research
def series(key, n, wins, pnl, staked, first):
    return {"key": key, "n": n, "wins": wins, "pnl": pnl, "staked": staked, "first": first}


MARKETS = [series("BTC", 695, 676, 335.60, 21318.57, "2025-12-10T00:00:00+00:00"),
           series("HYPE", 1127, 1077, -411.96, 22565.53, "2026-03-18T00:00:00+00:00"),
           series("GOLD", 462, 451, 262.75, 13725.92, "2026-07-31T19:00:00+00:00"),
           series("BRENT", 12, 12, 4.10, 240.00, "2026-10-21T13:00:00+00:00")]


# A bankroll curve with a dip in it, so the chart has a real shape and a fall below the starting amount to show.
# It has to span the whole replay, Dec 2025 to Oct 2026, or the asset-class markers fall outside the chart and
# never get drawn: 1,280 points six hours apart, which is what the real study carries after thinning.
POINTS = 1280


def curve_of(start, end, dip=0.12):
    """start to end with one dip below the starting amount a third of the way along."""
    out = []
    for i in range(POINTS):
        f = i / (POINTS - 1)
        sag = -dip * math.sin(math.pi * min(1.0, f / 0.45)) if f < 0.45 else 0.0
        out.append(round(start * (1 + sag) + (end - start) * f * f, 2))
    out[0], out[-1] = start, end
    return out


CURVE = curve_of(2000.0, 3253.70)
CURVE_BIG = curve_of(10000.0, 11887.0)


# The asset classes, each from the window it was first bet in. Kalshi listed them a long way apart, which is why
# the chart marks them: the line changes shape when a new one arrives.
GROUPS = [{"key": "crypto", "n": 9000, "wins": 8700, "pnl": 300.0, "staked": 60000.0,
           "first": "2025-12-10T00:00:00+00:00"},
          {"key": "metals", "n": 1000, "wins": 975, "pnl": 120.0, "staked": 8000.0,
           "first": "2026-07-31T19:00:00+00:00"},
          {"key": "energy", "n": 365, "wins": 356, "pnl": 60.0, "staked": 3000.0,
           "first": "2026-10-21T13:00:00+00:00"}]


def run_of(**over):
    r = {"start": 2000.0, "final": 3253.70, "ret": 0.62684774, "bets": 10365, "wins": 10045,
         "winRate": 0.9691268693, "perBet": 5.5254747, "maxDD": 0.1742151286, "worst24h": -220.97,
         "bySeries": MARKETS, "byGroup": GROUPS, "byBand": [], "curve": CURVE}
    r.update(over)
    return r


CURVE_REAL = curve_of(750.25, 1385.0, 0.19)


def real_run(**over):
    """The simulated $850 account (mine4liq850, added Oct 28). The $700 stop bites on this one and on
    no other: its dip is under the floor, where the same fall from $2,000 is not."""
    r = run_of(start=750.25, final=1385.0, ret=0.6269, perBet=5.52, maxDD=0.2247, curve=CURVE_REAL,
               floorHit="2026-03-02T14:15:00+00:00")
    r.update(over)
    return r


def big_run(**over):
    """The same rules from $10,000 (mine4liq10k, added Oct 28): five times the money, nowhere near five times the
    profit, because the trade tape cannot fill a 1.5% bet that big."""
    r = run_of(start=10000.0, final=11887.0, ret=0.1887, perBet=1.9, maxDD=0.2362, curve=CURVE_BIG)
    r.update(over)
    return r


def study(**over):
    liq = {"lo": 0.92, "hi": 0.999, "pct": 0.015, "windowCap": 0.1, "floor": 700.0, "liquidity": True}
    s = {"stamp": 1_793_000_000.0,
         "replay": {"t0": "2025-12-10T00:00:00+00:00", "hours": 7345, "step": 6, "start": 240.0, "periods": [],
                    "strategies": [{"id": "mine4liq", "name": "Version 4 · real liquidity", **liq},
                                   {"id": "mine4liq10k", "name": "Version 4 · real liquidity · $10,000", **liq},
                                   {"id": "mine4liq850",
                                    "name": "Version 4 · real liquidity · starting amount", **liq}],
                    "runs": {"live": {"dec10": {"mine4liq": run_of(), "mine4liq10k": big_run(),
                                                "mine4liq850": real_run()}}}, "edge": {}}}
    s.update(over)
    return s


# ------------------------------------------------------------------ the file itself
@needs_node
def test_backtest_js_parses():
    own(FILE)
    r = subprocess.run([NODE, "--check", os.path.join(HERE, FILE)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_it_is_one_closure_with_a_pure_markup_function_and_a_view():
    js = own(FILE)
    assert "(() => {" in js and '"use strict";' in js and js.rstrip().endswith("})();")
    assert f"{MARKUP} = " in js and f"{ENTRY} = " in js
    assert re.search(rf'patch\("{TAB}", (window\.)?backtestHtml\(', js)


def test_it_reads_only_the_research_routes_and_never_a_cached_copy():
    js = code(own(FILE))
    routes = set(re.findall(r'"(/api/[^"]*)"', js))      # named at the call sites, whatever reads them
    assert routes and routes <= {"/api/research", "/api/research/stamp"}
    assert js.count('cache: "no-store"') >= 1


def test_it_asks_the_stamp_before_refetching_the_big_study():
    """The study is megabytes and only changes when the backtest is run again."""
    js = code(own(FILE))
    assert js.index('"/api/research/stamp"') < js.index('"/api/research"')


def test_the_styles_cant_reach_the_account_pages():
    css = re.sub(r"/\*.*?\*/", "", own("backtest.css"), flags=re.S)   # the prose in a comment isn't a selector
    for rule in re.findall(r"(^|\})\s*([^@{}]+)\{", css, re.M):
        for sel in rule[1].split(","):
            sel = sel.strip()
            if sel and not sel.startswith(("/*", "from", "to", "0%", "100%")):
                assert sel.startswith(f"#{TAB}") or ".bt-" in sel, sel


def test_the_styles_define_no_colours_of_their_own():
    """Light and dark come from the page's tokens (test_look.py holds those to one place)."""
    css = re.sub(r"/\*.*?\*/", "", own("backtest.css"), flags=re.S)   # a dashed separator is not a colour
    assert "--" not in re.sub(r"var\(--[a-z0-9-]+\)", "", css)


# ------------------------------------------------------------------ what it says
RUNNER = r"""
const vm = require("vm");
const fs = require("fs");
const __input = fs.readFileSync(0, "utf8");
const __in = JSON.parse(__input);
const ctx = { console, JSON, Math, Number, String, Object, Array, Date, isNaN, parseFloat, parseInt };
ctx.globalThis = ctx;
ctx.window = ctx;
ctx.__els = {};
ctx.$ = (id) => ctx.__els[id] || (ctx.__els[id] = { id, hidden: false, innerHTML: "" });
ctx.patch = (id, html) => { ctx.$(id).innerHTML = html; return true; };
ctx.store = { get: () => null, set: () => {} };
ctx.page = __in.page;
ctx.data = null;
ctx.document = { hidden: false, addEventListener() {}, querySelector: () => null };
ctx.fetch = () => Promise.reject(new Error("no fetch in the markup test"));
ctx.setInterval = () => 0;
ctx.clearInterval = () => {};
vm.createContext(ctx);
vm.runInContext(__in.pageJs, ctx, { filename: "page.js" });
vm.runInContext(fs.readFileSync(__in.file, "utf8"), ctx, { filename: __in.file });
const out = __in.studies.map((s) => ctx.window.backtestHtml(s));
process.stdout.write(JSON.stringify({ out }));
"""


def helpers_js():
    """The page's own formatters, cut out of dashboard.html the way the Live Research tests cut them."""
    names = ", ".join(HELPERS)
    cut = "\n".join([*(piece(rf"^const {n} = [^\n]*$") for n in ("esc", "nf", "zero", "money", "signed", "pct", "spct",
                                                                 "tone", "cents", "hhmm", "sym", "count")),
                     piece(r"^const when = \(t\) => \{.*?^\};$")])
    return f"""
const {{ {names} }} = (() => {{
{cut}
return {{ {names} }};
}})();
"""


def drawn(*studies, page=TAB):
    if not NODE:
        pytest.skip("node isn't installed")
    own(FILE)
    payload = {"pageJs": helpers_js(), "file": os.path.join(HERE, FILE), "studies": list(studies), "page": page}
    r = subprocess.run([NODE, "-e", RUNNER], input=json.dumps(payload), capture_output=True, text=True,
                       encoding="utf-8", timeout=60, env={**os.environ, "TZ": "America/New_York"})
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)["out"]


def says(markup, s):
    return norm(s) in norm(text(markup))


@needs_node
def test_with_no_study_yet_it_says_so_rather_than_showing_nothing():
    assert says(drawn(None)[0], "Loading")


@needs_node
def test_an_unreadable_study_says_the_backtest_has_not_been_run():
    out = drawn(study(replay=None))[0]
    assert says(out, "strategies_backtest.py")


@needs_node
def test_it_names_the_rules_it_replays():
    """Someone reading this tab has to know which rules produced the numbers."""
    out = drawn(study())[0]
    for words in ("92", "1.5%", "10%", "700", "minute 8"):
        assert says(out, words), words


@needs_node
def test_it_says_the_fills_are_capped_by_the_real_book():
    out = drawn(study())[0]
    assert says(out, "trade tape") or says(out, "order book")


@needs_node
def test_every_market_shows_its_own_first_window():
    """The whole point of the tab: gold from July, Brent from October, not one shared start date."""
    out = drawn(study())[0]
    for words in ("Dec 2025", "Mar 2026", "Jul 2026", "Oct 2026"):
        assert says(out, words), words


@needs_node
def test_each_market_shows_its_bets_and_its_profit_per_dollar():
    out = drawn(study())[0]
    assert says(out, "1,127")                      # HYPE's bets, grouped
    assert "−1.83" in text(out) or "-1.83" in text(out)   # its cents per dollar staked
    assert says(out, "+1.57")                      # BTC's


@needs_node
def test_a_market_that_loses_money_is_marked_as_such():
    out = drawn(study())[0]
    assert re.search(r'class="[^"]*\bdown\b', out), "a losing market is not toned down"


@needs_node
def test_a_thin_market_is_called_thin_rather_than_shown_as_a_finding():
    """Brent has 12 bets here. A number that precise from 12 bets would mislead."""
    out = drawn(study())[0]
    assert says(out, "too few") or says(out, "thin")


@needs_node
def test_the_overall_line_shows_what_the_rules_made():
    out = drawn(study())[0]
    assert says(out, "10,365") and says(out, "$3,253.70") and says(out, "+0.55")


@needs_node
def test_it_says_the_extra_cent_is_not_modelled():
    """The live bot bids a cent over the ask it saw; the replay fills at the ask, so the tab must not claim it."""
    assert says(drawn(study())[0], "cent")


@needs_node
def test_a_strategy_name_from_the_server_is_escaped():
    s = study()
    for strat in s["replay"]["strategies"]:
        strat["name"] = '<img src=x onerror=alert(1)>'
    out = drawn(s)[0]
    assert "<img" not in out and "&lt;img" in out


# ------------------------------------------------------------------ the server's side
def test_the_server_serves_the_tabs_two_files():
    assert dashboard.ASSETS["/backtest.js"] == ("backtest.js", "text/javascript; charset=utf-8")
    assert dashboard.ASSETS["/backtest.css"] == ("backtest.css", "text/css; charset=utf-8")


def test_the_page_loads_them_after_its_own_script_and_styles():
    assert HTML.index('<link rel="stylesheet" href="/backtest.css">') < HTML.index("</head>")
    assert HTML.index('<script src="/backtest.js"></script>') > HTML.index("</script>\n")
    assert HTML.index('<script src="/live_research.js"></script>') < HTML.index('<script src="/backtest.js">')


def test_it_has_its_own_section_last_in_main():
    main = HTML.split("<main")[1].split("</main>")[0]
    sec = f'<section id="{TAB}" aria-label="Backtest" hidden></section>'
    assert sec in main and main.index('id="latency"') < main.index(sec)


def test_the_nav_has_a_backtest_button():
    r = body("function render() {")
    assert f'data-page="{TAB}"' in r and ">Backtest</button>" in r


def test_on_its_tab_the_account_hides_and_only_this_tab_draws():
    r = body("function render() {")
    assert f'$("{TAB}").hidden = !bt;' in r
    assert "backtestView" in body("function render() {") or "backtestView" in SCRIPT


# ------------------------------------------------------------------ $10,000 beside $2,000 (added Oct 28)
@needs_node
def test_it_shows_both_starting_amounts():
    out = drawn(study())[0]
    assert says(out, "$2,000") and says(out, "$10,000")


@needs_node
def test_it_says_five_times_the_money_is_not_five_times_the_profit():
    """The finding, and the reason the tab shows two amounts at all: $2,000 made +$1,253.70 and $10,000 only
    +$1,887, because a 1.5% bet at $10,000 is more contracts than the trade tape says the book held."""
    out = drawn(study())[0]
    assert says(out, "+$1,253.70") and says(out, "+$1,887.00")
    assert says(out, "fill") or says(out, "depth"), "it doesn't say why the bigger account gains so little"


@needs_node
def test_the_bigger_account_is_not_shown_as_the_better_one():
    """Its return is far lower, and the tab has to show that rather than only the bigger pile of dollars."""
    out = drawn(study())[0]
    assert says(out, "+62.7%") and says(out, "+18.9%")


@needs_node
def test_with_only_the_2000_account_it_still_draws():
    """A strategies.json written before the $10,000 account existed."""
    s = study()
    del s["replay"]["runs"]["live"]["dec10"]["mine4liq10k"]
    out = drawn(s)[0]
    assert says(out, "10,365") and not says(out, "$10,000")


# ------------------------------------------------------------------ the bankroll chart (added Oct 28)
@needs_node
def test_it_draws_a_bankroll_chart():
    out = drawn(study())[0]
    assert "<svg" in out and "viewBox" in out
    assert out.count("<polyline") >= 2, "both accounts should have a line"


@needs_node
def test_the_chart_tells_a_screen_reader_what_it_shows():
    svg = re.search(r"<svg[^>]*>", drawn(study())[0])
    assert svg and 'role="img"' in svg.group(0) and "aria-label" in svg.group(0)


@needs_node
def test_the_chart_is_drawn_in_percent_so_the_two_lines_can_be_compared():
    """In dollars the $2,000 line is a flat squiggle under the $10,000 one, and the shapes can't be compared."""
    out = drawn(study())[0]
    cap = re.search(r"<figcaption.*?</figcaption>", out, re.S)
    assert cap, "the chart has no caption"
    said = text(cap.group(0))
    assert "%" in said or "percentage" in said or "per cent" in said
    assert "%" in text(out), "no percentage scale on the chart itself"


@needs_node
def test_a_run_with_no_curve_leaves_the_chart_out_rather_than_drawing_an_empty_one():
    s = study()
    for r in s["replay"]["runs"]["live"]["dec10"].values():
        r["curve"] = None
    out = drawn(s)[0]
    assert "<svg" not in out
    assert says(out, "10,365"), "the figures should still be there"


@needs_node
def test_the_chart_marks_the_line_the_money_started_at():
    """A rule across at nothing grown, so a dip under the starting amount is plain."""
    assert says(drawn(study())[0], "started")


def test_the_chart_has_styles_of_its_own():
    """The .lr-* sheet it borrows has no chart classes, so these have to be the tab's."""
    css = re.sub(r"/\*.*?\*/", "", own("backtest.css"), flags=re.S)
    assert ".bt-" in css


# ------------------------------------------------------------------ the simulated $850 account (added Oct 28)
@needs_node
def test_it_shows_the_850_dollar_account_beside_the_what_ifs():
    """Beside the $2,000 and $10,000 what-ifs, a third, smaller account: the one the $700 stop bites on."""
    out = drawn(study())[0]
    for words in ("$750.25", "$2,000", "$10,000"):
        assert says(out, words), words


@needs_node
def test_the_small_amount_is_named_as_the_starting_amount():
    out = drawn(study())[0]
    assert says(out, "starting amount")


@needs_node
def test_all_three_amounts_are_overlaid_on_the_one_chart():
    """One graph, not three."""
    out = drawn(study())[0]
    assert out.count("<svg") == 1, "there should be one chart, not one per amount"
    assert out.count("<polyline") >= 3, "each amount needs its own line on it"


@needs_node
def test_the_three_lines_are_told_apart():
    out = drawn(study())[0]
    classes = set(re.findall(r'<polyline class="bt-line ([a-z0-9-]+)"', out))
    assert len(classes) == 3, f"the lines share styling: {classes}"


@needs_node
def test_it_says_where_the_700_stop_would_have_fired():
    """It bites on the $850 account and on no other, which is the reason to show that amount."""
    out = drawn(study())[0]
    assert says(out, "$700")
    assert says(out, "Mar 2026") or says(out, "2026-03-02") or says(out, "stop")


@needs_node
def test_an_account_the_stop_never_touched_is_not_said_to_have_hit_it():
    s = study()
    s["replay"]["runs"]["live"]["dec10"]["mine4liq850"]["floorHit"] = None
    out = drawn(s)[0]
    # "Mar 2026" is also a market's first window further down, so read the accounts table's own rows
    first = re.search(r"<tbody>(.*?)</tbody>", out, re.S).group(1)
    assert "Mar 2026" not in first and first.count("never") == 3


def test_the_server_passes_the_stop_date_through():
    """dashboard.py keeps only RUN_STATS out of each run; without floorHit the tab can't say the stop fired."""
    assert "floorHit" in dashboard.RUN_STATS


# ------------------------------------------------------------------ where each asset class started (Oct 28)
@needs_node
def test_the_chart_marks_where_each_asset_class_started_trading():
    """Kalshi listed crypto in Dec 2025, metals in Jul 2026 and energy in Oct 2026. The line changes shape when
    one arrives, and without a marker there is nothing on the chart saying why."""
    out = drawn(study())[0]
    fig = re.search(r"<figure.*?</figure>", out, re.S).group(0).lower()   # the caption may capitalise one
    for group in ("crypto", "metals", "energy"):
        assert group in fig, f"{group} is not accounted for on the chart"


@needs_node
def test_a_marker_is_a_rule_on_the_chart_not_just_a_word():
    out = drawn(study())[0]
    # One rule for each class that arrives after the chart begins. The one that was there from the first window
    # gets no rule -- it would sit on the axis and read as a border -- so the caption names it instead.
    assert out.count('class="bt-mark"') == 2, "metals and energy each need a rule, not only a label"
    assert "crypto" in text(re.search(r"<figcaption.*?</figcaption>", out, re.S).group(0)).lower()


@needs_node
def test_the_caption_says_what_the_markers_are():
    out = drawn(study())[0]
    cap = text(re.search(r"<figcaption.*?</figcaption>", out, re.S).group(0))
    assert "started" in cap or "listed" in cap


@needs_node
def test_the_first_asset_class_is_not_marked_on_the_chart_edge():
    """Crypto starts at the replay's own first window, where a rule would sit on the axis and read as a border."""
    out = drawn(study())[0]
    svg = re.search(r"<svg.*?</svg>", out, re.S).group(0)
    xs = [float(x) for x in re.findall(r'<line class="bt-mark" x1="([0-9.]+)"', svg)]
    assert xs and min(xs) > 52, f"a marker sits on or left of the axis: {xs}"


@needs_node
def test_a_study_with_no_asset_class_dates_still_draws_the_chart():
    """strategies.json written before byGroup carried a first window."""
    s = study()
    for r in s["replay"]["runs"]["live"]["dec10"].values():
        r["byGroup"] = [{k: v for k, v in g.items() if k != "first"} for g in GROUPS]
    out = drawn(s)[0]
    assert "<svg" in out and 'class="bt-mark"' not in out


@needs_node
def test_asset_class_names_from_the_server_are_escaped():
    s = study()
    for r in s["replay"]["runs"]["live"]["dec10"].values():
        r["byGroup"] = [{**GROUPS[0], "key": "<script>x</script>"}]
    out = drawn(s)[0]
    assert "<script>x" not in out


# ------------------------------------------------------------------ the shaded bands under the chart (Oct 28)
@needs_node
def test_each_asset_class_gets_a_shaded_band():
    """A window showing when each kind of market was open. The rules say when one
    started; the bands show the stretch each was trading over, which is what you read along."""
    out = drawn(study())[0]
    bands = re.findall(r'<rect class="bt-band[^"]*"[^>]*>', out)
    assert len(bands) == 3, f"one band per asset class, got {len(bands)}"


@needs_node
def test_a_band_runs_from_its_own_start_to_the_right_edge():
    """Kalshi has never stopped listing one of these, so every band ends at the last window drawn."""
    out = drawn(study())[0]
    bands = re.findall(r'<rect class="bt-band[^"]*" x="([0-9.]+)" y="[0-9.]+" width="([0-9.]+)"', out)
    assert len(bands) == 3
    ends = {round(float(x) + float(w), 1) for x, w in bands}
    assert len(ends) == 1, f"the bands end at different places: {ends}"
    starts = sorted(float(x) for x, _ in bands)
    assert starts[0] < starts[1] < starts[2], "the three should start at different times"


@needs_node
def test_every_band_is_named():
    out = drawn(study())[0]
    svg = re.search(r"<svg.*?</svg>", out, re.S).group(0).lower()
    for group in ("crypto", "metals", "energy"):
        assert f">{group}<" in svg, f"{group}'s band has no label"


@needs_node
def test_the_bands_sit_under_the_plot_not_over_the_lines():
    """Shading across the curves would muddy them; the ribbon goes below."""
    out = drawn(study())[0]
    plot = re.search(r'<rect class="bt-plot" x="[0-9.]+" y="([0-9.]+)" width="[0-9.]+" height="([0-9.]+)"', out)
    floor = float(plot.group(1)) + float(plot.group(2))
    ys = [float(y) for y in re.findall(r'<rect class="bt-band[^"]*" x="[0-9.]+" y="([0-9.]+)"', out)]
    assert ys and min(ys) >= floor, f"a band overlaps the plot (plot ends {floor}, band at {min(ys)})"


@needs_node
def test_the_chart_grows_to_fit_the_bands():
    out = drawn(study())[0]
    box = re.search(r'viewBox="0 0 ([0-9.]+) ([0-9.]+)"', out)
    assert float(box.group(2)) > 300, "the viewBox did not make room for the ribbon"


@needs_node
def test_without_dates_there_are_no_bands_and_the_chart_still_draws():
    s = study()
    for r in s["replay"]["runs"]["live"]["dec10"].values():
        r["byGroup"] = [{k: v for k, v in g.items() if k != "first"} for g in GROUPS]
    out = drawn(s)[0]
    assert "<svg" in out and "bt-band" not in out


def test_the_bands_are_styled_by_the_tabs_own_sheet():
    css = re.sub(r"/\*.*?\*/", "", own("backtest.css"), flags=re.S)
    assert ".bt-band" in css
