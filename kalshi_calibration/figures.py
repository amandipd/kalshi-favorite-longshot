"""`make figures`: the write-up's eight figures, drawn from reports/summary.json and
reports/replication.json.

The figures read the same two files as the findings dashboard, so a chart, the dashboard and the
printed report always show the same numbers; nothing is computed here beyond changing units.

One visual system across all eight (and the dashboard):

    colour has one job      polarity: red where the market charged more than the contract was
                            worth (overpriced), blue where it charged less, grey where the gap is
                            not significant. Two-series figures name their series in a legend.
    never colour alone      significance also shows as stars or as filled vs hollow markers, and
                            every figure's numbers are in a table (reports/*.csv, the dashboard).
    thin marks              bars under half their band with a rounded end at the value, 2px lines,
                            markers ringed in the surface colour, solid hairline grid, one y-axis.

The blue/red pair passes the colour-vision checks against this surface (worst-pair CVD delta-E 21.6,
normal-vision 32.3, both poles above 3:1 contrast).

    python -m kalshi_calibration.figures
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # no display on a headless run
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.lines import Line2D
from matplotlib.patches import PathPatch, Patch, Rectangle
from matplotlib.path import Path as MplPath
from matplotlib.transforms import offset_copy

SUMMARY_PATH = Path("reports/summary.json")
REPLICATION_PATH = Path("reports/replication.json")
FIGURES_DIR = Path("reports/figures")
DPI = 200

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
BLUE = "#2a78d6"     # underpriced; the strategy
RED = "#e34948"      # overpriced; the control
ORANGE = "#eb6834"   # the second horizon
NEUTRAL = "#f0efec"  # the diverging midpoint: "no gap"
NOT_SIG = "#c3c2b7"
HEAT_CAP = 8.0       # cents at which a heatmap cell reaches full colour
MINUS = "−"
CENT = "¢"


# ------------------------------------------------------------------ formatting

def signed(value: float, digits: int) -> str:
    text = f"{abs(value):.{digits}f}"
    if float(text) == 0:
        return text
    return ("+" if value > 0 else MINUS) + text


def band_label(low: float, high: float) -> str:
    return f"{round(low * 100)}–{round(high * 100)}{CENT}"


def day_label(iso: str) -> str:
    d = date.fromisoformat(iso[:10])
    return f"{d:%b} {d.day}, {d.year}"


def stars(q: float, significant: bool) -> str:
    if not significant:
        return ""
    return "***" if q < 0.001 else "**" if q < 0.01 else "*"


# ------------------------------------------------------------------ chrome

def style() -> None:
    plt.rcParams.update({
        "figure.dpi": 100,
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "font.family": "sans-serif",
        "font.sans-serif": ["Segoe UI", "Helvetica Neue", "Arial", "DejaVu Sans"],
        "font.size": 9.5,
        "text.color": INK,
        "axes.edgecolor": AXIS,
        "axes.linewidth": 0.8,
        "axes.labelcolor": INK_2,
        "axes.labelsize": 9.5,
        "axes.titlesize": 10.5,
        "axes.titlecolor": INK,
        "axes.titlelocation": "left",
        "axes.titlepad": 8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "grid.linestyle": "-",
        "xtick.color": AXIS,
        "ytick.color": AXIS,
        "xtick.labelcolor": INK_2,
        "ytick.labelcolor": INK_2,
        "xtick.major.size": 0,
        "ytick.major.size": 0,
        "legend.frameon": False,
        "legend.fontsize": 9,
        "legend.labelcolor": INK_2,
    })


def figure(width: float, height: float, headline: str, sub: str, ncols: int = 1,
           above: str | None = None, **kw: Any):
    """A figure with a left-aligned headline and subtitle above the plot area.

    `above` reserves room between the subtitle and the plot for a "legend" row or panel "titles".
    """
    fig, axes = plt.subplots(1, ncols, figsize=(width, height), **kw)
    top = fig.transFigure
    fig.text(0.012, 1, headline, transform=offset_copy(top, fig, y=-20, units="points"),
             fontsize=13, fontweight="semibold", color=INK, va="baseline")
    fig.text(0.012, 1, sub, transform=offset_copy(top, fig, y=-35, units="points"),
             fontsize=9.5, color=INK_2, va="top", linespacing=1.45)
    header_pt = 35 + 14 * (sub.count("\n") + 1) + 12 + (24 if above else 0)
    fig.subplots_adjust(top=1 - header_pt / (height * 72), left=0.08, right=0.97, bottom=0.13)
    return fig, axes


def save(fig, name: str) -> Path:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIGURES_DIR / name
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    return path


def tick(value: float, unit: str) -> str:
    """An axis label: signed, as few decimals as the value needs (2.5 stays 2.5, 2.0 becomes 2)."""
    text = f"{abs(value):.2f}".rstrip("0").rstrip(".")
    return ("" if text == "0" else "+" if value > 0 else MINUS) + text + unit


def cents_axis(ax, axis: str = "y") -> None:
    fmt = mticker.FuncFormatter(lambda v, _: tick(v, CENT))
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(fmt)


def zero_line(ax, axis: str = "y") -> None:
    (ax.axhline if axis == "y" else ax.axvline)(0, color=AXIS, linewidth=1.1, zorder=2)


def _radius(ax, px: float = 4.0) -> tuple[float, float]:
    """4 screen pixels as data units, (x, y): rounding that looks the same at any axis scale."""
    box = ax.get_window_extent()
    (x0, x1), (y0, y1) = ax.get_xlim(), ax.get_ylim()
    return px * abs(x1 - x0) / box.width, px * abs(y1 - y0) / box.height


def bar(ax, center: float, value: float, width: float, color: str, horizontal: bool = False,
        base: float = 0.0) -> None:
    """A bar from `base` to `value`, square at the base and rounded at the value end.

    Set the axis limits first: the rounding is sized from them.
    """
    rx, ry = _radius(ax)
    r_along, r_across = (rx, ry) if horizontal else (ry, rx)
    s = 1 if value >= base else -1
    ra, rc = min(r_along, abs(value - base)), min(r_across, width / 2)
    a, b = center - width / 2, center + width / 2
    pts = [(a, base), (a, value - s * ra), (a, value), (a + rc, value), (b - rc, value),
           (b, value), (b, value - s * ra), (b, base), (a, base)]
    codes = [MplPath.MOVETO, MplPath.LINETO, MplPath.CURVE3, MplPath.CURVE3, MplPath.LINETO,
             MplPath.CURVE3, MplPath.CURVE3, MplPath.LINETO, MplPath.CLOSEPOLY]
    verts = [(v, c) for c, v in pts] if horizontal else pts
    ax.add_patch(PathPatch(MplPath(verts, codes), facecolor=color, edgecolor="none", zorder=3))


def whisker(ax, x: float, lo: float, hi: float, cap: float) -> None:
    ax.plot([x, x], [lo, hi], color=INK_2, linewidth=1.1, zorder=4, solid_capstyle="butt")
    for y in (lo, hi):
        ax.plot([x - cap, x + cap], [y, y], color=INK_2, linewidth=1.1, zorder=4)


def mix(a: str, b: str, t: float) -> str:
    pa = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    pb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(pa, pb))


def legend_row(ax, handles: list) -> None:
    """The legend as one row just above the plot, in the room `figure(above="legend")` keeps."""
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(0, 1.0), ncol=len(handles),
              handlelength=1.4, handleheight=0.9, columnspacing=1.8, borderaxespad=0.5)


# ------------------------------------------------------------------ shared forms

def gap_bars(ax, rows: list[dict], ylabel: str) -> None:
    """Won minus price by band, as rounded bars with interval whiskers and optional stars."""
    lo = min([0.0] + [r["lo"] for r in rows])
    hi = max([0.0] + [r["hi"] for r in rows])
    pad = (hi - lo) * 0.14
    ax.set_xlim(-0.6, len(rows) - 0.4)
    ax.set_ylim(lo - pad, hi + pad)
    ax.grid(axis="x", visible=False)
    for i, r in enumerate(rows):
        bar(ax, i, r["gap"], 0.36, r["color"])
        whisker(ax, i, r["lo"], r["hi"], cap=0.09)
        if r.get("stars"):
            y = r["hi"] + pad * 0.18 if r["gap"] >= 0 else r["lo"] - pad * 0.18
            ax.text(i, y, r["stars"], ha="center", va="bottom" if r["gap"] >= 0 else "top",
                    fontsize=9, color=INK, fontweight="bold")
    zero_line(ax)
    ax.set_xticks(range(len(rows)), [r["label"] for r in rows])
    ax.set_ylabel(ylabel)
    cents_axis(ax)


# ------------------------------------------------------------------ the figures

def fig_calibration(s: dict) -> Path:
    b, rows = s["brier"], s["calibration"]
    fig, ax = figure(
        6.4, 6.5, "Kalshi prices are close to honest probabilities",
        f"{s['data']['contracts']:,} settled contracts, each priced one hour before close. Brier score "
        f"{b['brier']:.4f}, of which\nmiscalibration (reliability) is {b['reliability']:.5f}: "
        f"{b['reliability'] / b['brier']:.1%}. Each point is a 10{CENT} band.",
    )
    fig.subplots_adjust(left=0.12, bottom=0.1)
    ax.plot([0, 100], [0, 100], color=AXIS, linewidth=1.1, zorder=2)
    ax.text(70, 66, "perfect calibration", rotation=45, rotation_mode="anchor", color=MUTED, fontsize=9,
            ha="center", va="top", transform_rotates_text=True)
    x = [r["mean_price"] * 100 for r in rows]
    y = [r["realized_freq"] * 100 for r in rows]
    ax.plot(x, y, color=INK, linewidth=2, solid_joinstyle="round", zorder=3)
    ax.plot(x, y, "o", color=INK, markersize=8, markeredgecolor=SURFACE, markeredgewidth=1.6, zorder=4)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.set_aspect("equal")
    ticks = range(0, 101, 20)
    ax.set_xticks(ticks, [f"{t}{CENT}" for t in ticks])
    ax.set_yticks(ticks, [f"{t}%" for t in ticks])
    ax.set_xlabel("Price one hour before close")
    ax.set_ylabel("Share that resolved YES")
    return save(fig, "fig1_calibration.png")


def fig_bias_by_band(s: dict) -> Path:
    rows = []
    for r in s["calibration"]:
        tone = NOT_SIG if not r["significant"] else RED if r["bias"] < 0 else BLUE
        rows.append({"label": band_label(r["bucket_low"], r["bucket_high"]), "gap": r["bias"] * 100,
                     "lo": (r["ci_low"] - r["mean_price"]) * 100, "hi": (r["ci_high"] - r["mean_price"]) * 100,
                     "color": tone, "stars": stars(r["q_value"], r["significant"])})
    sig = sum(r["significant"] for r in s["calibration"])
    fig, ax = figure(
        8.4, 5.0, "Long shots are overpriced and favorites underpriced",
        f"How often each 10{CENT} band's contracts won, minus their price. Whiskers: 95% interval clustered by "
        f"event. {sig} of {len(rows)} bands are\nsignificant after the Benjamini–Hochberg correction "
        f"(* q < 0.05, ** q < 0.01, *** q < 0.001).", above="legend",
    )
    gap_bars(ax, rows, "Won minus price")
    ax.set_xlabel("Price one hour before close")
    legend_row(ax, [Patch(color=RED, label="Overpriced"), Patch(color=BLUE, label="Underpriced"),
                    Patch(color=NOT_SIG, label="Not significant")])
    return save(fig, "fig2_bias_by_band.png")


def _segment_name(segment: str, index: int, count: int, view: str) -> str:
    if view != "lifetime":
        return segment
    lo, hi = segment.split(". ", 1)[-1].rstrip("h").split("-")
    lo, hi = float(lo), float(hi)
    if index == 0:
        return f"Under {hi:g} h"
    if index == count - 1:
        return f"Over {lo:g} h"
    return f"{lo:g}–{hi:g} h"


def _heatmap(ax, rows: list[dict], view: str, title: str) -> None:
    segments = list(dict.fromkeys(r["segment"] for r in rows))
    bands = sorted({(r["bucket"], r["bucket_low"], r["bucket_high"]) for r in rows})
    ax.set_xlim(0, len(bands))
    ax.set_ylim(len(segments), 0)
    ax.grid(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_visible(False)
    gap = 0.035
    for si, seg in enumerate(segments):
        for bi, (bucket, _, _) in enumerate(bands):
            r = next((x for x in rows if x["segment"] == seg and x["bucket"] == bucket), None)
            if r is None:
                continue
            cell = dict(xy=(bi + gap, si + gap), width=1 - 2 * gap, height=1 - 2 * gap)
            if r["underpowered"]:
                ax.add_patch(Rectangle(**cell, facecolor=SURFACE, edgecolor=GRID, linewidth=0.9))
                ax.text(bi + 0.5, si + 0.5, "thin", ha="center", va="center", color=MUTED, fontsize=8.5)
                continue
            c = r["bias"] * 100
            t = min(1.0, abs(c) / HEAT_CAP) * (1.0 if r["significant"] else 0.3)
            ax.add_patch(Rectangle(**cell, facecolor=mix(NEUTRAL, RED if c < 0 else BLUE, t), edgecolor="none"))
            ink = "#ffffff" if t > 0.6 else INK if r["significant"] else INK_2
            ax.text(bi + 0.5, si + 0.5, signed(c, 1), ha="center", va="center", color=ink, fontsize=9,
                    fontweight="semibold" if r["significant"] else "normal")
    ax.set_xticks([i + 0.5 for i in range(len(bands))], [band_label(lo, hi) for _, lo, hi in bands])
    ax.set_yticks([i + 0.5 for i in range(len(segments))],
                  [_segment_name(seg, i, len(segments), view) for i, seg in enumerate(segments)])
    ax.tick_params(axis="both", length=0, pad=5)
    ax.set_title(title)


def fig_segments(s: dict) -> Path:
    fig, (left, right) = figure(
        10.2, 4.6, "The bias is strongest in short-lived markets",
        f"Won minus price, in cents, by 20{CENT} price band. Faded cells are not significant after one "
        f"Benjamini–Hochberg correction across every cell;\n“thin” cells have too few events to "
        f"test. Colour reaches full strength at ±{HEAT_CAP:g}{CENT}.",
        ncols=2, above="titles",
    )
    fig.subplots_adjust(left=0.11, right=0.98, wspace=0.32, bottom=0.12)
    _heatmap(left, s["segments"]["lifetime"], "lifetime", "By how long the market was open")
    _heatmap(right, s["segments"]["category"], "category", "By category")
    return save(fig, "fig3_bias_by_segment.png")


def fig_horizon(s: dict) -> Path | None:
    h = s.get("horizon")
    if not h:
        return None
    g = h["regression"]
    series = [(f"{h['late_hours']:g} hour before close", h["late"], INK, "-"),
              (f"{h['early_hours']:g} hours before close", h["early"], ORANGE, (0, (4, 2.5)))]
    n = sum(r["n"] for r in h["late"])
    fig, ax = figure(
        8.4, 5.0, "The bias is only measurable near the close",
        f"The same {n:,} contracts priced at two horizons. Given the one-hour price, the six-hour price adds almost "
        f"nothing:\nits weight falls from {g['early_alone']['coef']:.3f} alone to {g['both']['early']['coef']:.3f} "
        f"with both in the model. Filled: significant after Benjamini–Hochberg.", above="legend",
    )
    bands = h["late"]
    every = [((r["ci_low"] - r["mean_price"]) * 100, (r["ci_high"] - r["mean_price"]) * 100)
             for _, rows, _, _ in series for r in rows]
    lo, hi = min(0, *(a for a, _ in every)), max(0, *(b for _, b in every))
    pad = (hi - lo) * 0.1
    ax.set_xlim(-0.6, len(bands) - 0.4)
    ax.set_ylim(lo - pad, hi + pad)
    ax.grid(axis="x", visible=False)
    zero_line(ax)
    handles = []
    for k, (name, rows, color, dash) in enumerate(series):
        xs = [i + (-0.12 if k == 0 else 0.12) for i in range(len(rows))]
        ys = [r["bias"] * 100 for r in rows]
        ax.plot(xs, ys, color=color, linewidth=2, linestyle=dash, zorder=3, alpha=0.85)
        for x, r in zip(xs, rows):
            ax.plot([x, x], [(r["ci_low"] - r["mean_price"]) * 100, (r["ci_high"] - r["mean_price"]) * 100],
                    color=color, linewidth=1.1, zorder=3)
            ax.plot(x, r["bias"] * 100, "o", markersize=8, zorder=5, markeredgewidth=1.8,
                    markerfacecolor=color if r["significant"] else SURFACE, markeredgecolor=color)
        handles.append(Line2D([], [], color=color, linewidth=2, linestyle=dash, marker="o", markersize=7,
                              markerfacecolor=color, label=name))
    handles.append(Line2D([], [], linestyle="none", marker="o", markersize=7, markerfacecolor=SURFACE,
                          markeredgecolor=INK_2, markeredgewidth=1.6, label="Hollow: not significant"))
    ax.set_xticks(range(len(bands)), [band_label(r["bucket_low"], r["bucket_high"]) for r in bands])
    ax.set_ylabel("Won minus price")
    ax.set_xlabel("Price band")
    cents_axis(ax)
    legend_row(ax, handles)
    return save(fig, "fig4_horizon.png")


def fig_out_of_sample(s: dict) -> Path:
    bt = s["backtest"]
    st, ct = bt["strategy"], bt["control"]
    curves = [("Bias strategy", bt["equity"]["strategy"], BLUE, "-"),
              ("Control: the opposite bets", bt["equity"]["control"], RED, (0, (5, 3)))]
    last = bt["equity"]["strategy"][-1][0]
    fig, ax = figure(
        8.4, 5.0, "The bias beats fees out of sample; betting against it goes broke",
        f"Bankroll by settlement day, {day_label(bt['split'])} – {day_label(last)}, after estimating each band's "
        f"bias on the {bt['train']:,} earlier contracts.\nHalf-Kelly sizing and Kalshi's taker fee. Return on money "
        f"deployed: {signed(st['roi'] * 100, 2)}% for the strategy, {signed(ct['roi'] * 100, 1)}% for the control.",
        above="legend",
    )
    fig.subplots_adjust(right=0.86)
    ax.axhline(1.0, color=AXIS, linewidth=1.1, zorder=2)
    handles = []
    for name, points, color, dash in curves:
        xs = [date.fromisoformat(d) for d, _ in points]
        ys = [v for _, v in points]
        ax.plot(xs, ys, color=color, linewidth=2, linestyle=dash, solid_joinstyle="round", zorder=3)
        ax.plot(xs[-1], ys[-1], "o", color=color, markersize=8, markeredgecolor=SURFACE, markeredgewidth=1.6,
                zorder=4, clip_on=False)
        value = f"{ys[-1]:.2f}×" if ys[-1] >= 0.01 else f"{ys[-1]:.4f}×"
        ax.annotate(value, (xs[-1], ys[-1]), xytext=(8, 0), textcoords="offset points", va="center",
                    color=INK, fontsize=9.5, fontweight="semibold", annotation_clip=False)
        handles.append(Line2D([], [], color=color, linewidth=2, linestyle=dash, label=name))
    ax.set_ylim(bottom=0)
    first = date.fromisoformat(bt["equity"]["strategy"][0][0])
    ax.set_xlim(first, date.fromisoformat(last))
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:g}×"))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO, interval=1))
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{mdates.num2date(v):%b} {mdates.num2date(v).day}"))
    ax.set_ylabel("Bankroll (start = 1×)")
    legend_row(ax, handles)
    return save(fig, "fig5_out_of_sample.png")


def fig_robustness(s: dict) -> Path | None:
    bt = s["backtest"]
    sweeps = [("train_fraction", "Share of the data used to estimate the bias",
               lambda v: f"{v * 100:.0f}%"),
              ("min_net_edge", "Net edge a band must clear to be traded",
               lambda v: f"{v * 100:g}{CENT}")]
    sweeps = [x for x in sweeps if bt.get(x[0])]
    if not sweeps:
        return None
    fig, axes = figure(
        10.2, 4.6, "The result doesn't hinge on the choices behind it",
        "Out-of-sample return on money deployed as each choice is moved, with everything else fixed. The strategy "
        "stays\npositive and the control negative at every setting where any band clears the bar.",
        ncols=len(sweeps), above="titles", sharey=True,
    )
    axes = axes if len(sweeps) > 1 else [axes]
    fig.subplots_adjust(wspace=0.12, left=0.07)
    for ax, (key, title, fmt) in zip(axes, sweeps):
        rows = bt[key]
        xs = list(range(len(rows)))
        zero_line(ax)
        for name, field, color in (("Bias strategy", "roi", BLUE), ("Control: the opposite bets", "control_roi", RED)):
            ys = [r[field] * 100 for r in rows]
            ax.plot(xs, ys, color=color, linewidth=2, zorder=3, label=name)
            ax.plot(xs, ys, "o", color=color, markersize=8, markeredgecolor=SURFACE, markeredgewidth=1.6, zorder=4)
        for x, r in zip(xs, rows):
            if r["buckets_traded"] == 0:
                ax.annotate("no band\nclears it", (x, 0), xytext=(0, 10), textcoords="offset points",
                            ha="center", va="bottom", fontsize=8, color=MUTED)
        ax.set_xticks(xs, [fmt(r["threshold"]) for r in rows])
        ax.set_xlim(-0.5, len(rows) - 0.5)
        ax.grid(axis="x", visible=False)
        ax.set_title(title)
    axes[0].yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: tick(v, "%")))
    axes[0].set_ylabel("Return on money deployed")
    fig.legend(handles=[Line2D([], [], color=BLUE, linewidth=2, marker="o", label="Bias strategy"),
                        Line2D([], [], color=RED, linewidth=2, marker="o", label="Control: the opposite bets")],
               loc="lower right", bbox_to_anchor=(0.97, 0.0), ncol=2, handlelength=1.6)
    fig.subplots_adjust(bottom=0.2)
    return save(fig, "fig6_robustness.png")


def fig_replication(r: dict) -> Path:
    rows = []
    for c in r["calibration"]:
        excludes = c["lo"] > c["price"] or c["hi"] < c["price"]
        tone = NOT_SIG if not excludes else RED if c["gap"] < 0 else BLUE
        rows.append({"label": band_label(c["low"], c["high"]), "gap": c["gap"] * 100,
                     "lo": (c["lo"] - c["price"]) * 100, "hi": (c["hi"] - c["price"]) * 100, "color": tone})
    w = r["window"]
    top = r["calibration"][-1]
    fig, ax = figure(
        8.4, 5.0, "The same shape on markets that last 15 minutes",
        f"{r['markets']:,} crypto, metals and energy markets, {day_label(w['start'])} – {day_label(w['end'])}, "
        f"each priced at minute {r['settings']['entry_minute']}. Whiskers: 95% Wilson interval; grey where it\n"
        f"includes the price. At {band_label(top['low'], top['high'])}, contracts won {top['actual']:.1%} of the "
        f"time against {top['price']:.1%} priced.", above="legend",
    )
    gap_bars(ax, rows, "Won minus price")
    ax.set_xlabel(f"Price at minute {r['settings']['entry_minute']}")
    legend_row(ax, [Patch(color=RED, label="Overpriced"), Patch(color=BLUE, label="Underpriced"),
                    Patch(color=NOT_SIG, label="Interval includes the price")])
    return save(fig, "fig7_replication.png")


def _hbars(ax, labels: list[str], values: list[float], fmt, title: str) -> None:
    lo, hi = min([0.0] + values), max([0.0] + values)
    pad = (hi - lo) * 0.28
    ax.set_xlim(lo - (pad if lo < 0 else 0), hi + (pad if hi > 0 else pad * 0.15))
    ax.set_ylim(len(values) - 0.4, -0.6)
    ax.grid(axis="y", visible=False)
    zero_line(ax, "x")
    for i, v in enumerate(values):
        bar(ax, i, v, 0.46, BLUE if v > 0 else RED, horizontal=True)
        ax.annotate(fmt(v), (v, i), xytext=(6 if v >= 0 else -6, 0), textcoords="offset points",
                    ha="left" if v >= 0 else "right", va="center", color=INK, fontsize=9.5, fontweight="semibold")
    ax.set_yticks(range(len(labels)), labels)
    ax.tick_params(axis="y", pad=6)
    ax.set_title(title)


def fig_kelly_and_stops(r: dict) -> Path:
    s = r["settings"]
    k = r["kelly"]
    after = [row["after"] for row in r["stops"]]
    w = r["window"]
    fig, (left, right) = figure(
        10.2, 4.6, "But the growth-optimal bet is zero, and selling early only loses more",
        f"Left: one-bet Kelly fraction f* = (q − c) / (1 − c) for the "
        f"{s['favourite_low'] * 100:g}–{s['favourite_high'] * 100:g}{CENT} favorites at minute "
        f"{s['entry_minute']}, where q is how often they won and c their all-in cost.\nRight: change in profit from "
        f"selling a ${s['stake']:g} bet at the first bid at or under each level instead of holding it, "
        f"{day_label(w['split'])} – {day_label(w['end'])}.",
        ncols=2, above="titles",
    )
    fig.subplots_adjust(left=0.17, right=0.97, wspace=0.62, bottom=0.12)
    _hbars(left, [x["label"] for x in k], [x["kelly"] * 100 for x in k], lambda v: signed(v, 1) + "%",
           "Share of bankroll to bet")
    left.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: tick(v, "%")))
    _hbars(right, [f"Sell at ≤ {row['level'] * 100:g}{CENT}" for row in r["stops"]],
           [x["delta"] for x in after], lambda v: ("" if round(v) >= 0 else MINUS) + f"${abs(v):,.0f}",
           "Selling early against holding")
    right.xaxis.set_major_formatter(mticker.FuncFormatter(
        lambda v, _: ("" if v >= 0 else MINUS) + f"${abs(v):,.0f}"))
    return save(fig, "fig8_kelly_and_stops.png")


def build_all() -> list[Path]:
    style()
    made: list[Path | None] = []
    if SUMMARY_PATH.exists():
        s = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
        made += [fig_calibration(s), fig_bias_by_band(s), fig_segments(s), fig_horizon(s),
                 fig_out_of_sample(s), fig_robustness(s)]
    else:
        print(f"{SUMMARY_PATH} is missing; run `make analyze` for figures 1-6")
    if REPLICATION_PATH.exists():
        r = json.loads(REPLICATION_PATH.read_text(encoding="utf-8"))
        made += [fig_replication(r), fig_kelly_and_stops(r)]
    else:
        print(f"{REPLICATION_PATH} is missing; run `make replicate` for figures 7-8")
    return [p for p in made if p is not None]


def main() -> None:
    for path in build_all():
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
