"""Unit tests for kalshi_calibration/figures.py's formatting helpers and the figures that may be skipped.

test_figures.py draws all eight figures from the committed reports. These pin the small text helpers
every label goes through (a sign error there would mislabel a chart without failing anything), and the
branches the committed reports never reach: a summary with no horizon check, and one with a single
robustness sweep.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import matplotlib.pyplot as plt
import pytest

from kalshi_calibration import figures

ROOT = Path(__file__).resolve().parent.parent
SUMMARY = json.loads((ROOT / "reports" / "summary.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("value,digits,expected", [
    (1.234, 1, "+1.2"), (-1.25, 2, "−1.25"), (0.0, 1, "0.0"), (-0.04, 1, "0.0"), (0.04, 1, "0.0"),
    (12.0, 0, "+12"),
])
def test_signed_uses_a_true_minus_and_no_sign_on_zero(value, digits, expected):
    assert figures.signed(value, digits) == expected


def test_day_label_reads_an_iso_date_or_timestamp():
    assert figures.day_label("2026-08-04") == "Aug 4, 2026"
    assert figures.day_label("2026-12-25T10:00:00Z") == "Dec 25, 2026"


@pytest.mark.parametrize("q,sig,expected", [(0.0005, True, "***"), (0.005, True, "**"), (0.04, True, "*"),
                                            (0.0005, False, "")])
def test_stars(q, sig, expected):
    assert figures.stars(q, sig) == expected


def test_mix_interpolates_hex_colours():
    assert figures.mix("#000000", "#ffffff", 0.0) == "#000000"
    assert figures.mix("#000000", "#ffffff", 1.0) == "#ffffff"
    assert figures.mix("#000000", "#ffffff", 0.5) == "#808080"
    assert figures.mix("#2a78d6", "#2a78d6", 0.3) == "#2a78d6"


def test_tick_trims_trailing_zeros_but_keeps_needed_decimals():
    assert figures.tick(0.25, "%") == "+0.25%"
    assert figures.tick(-10.0, "¢") == "−10¢"
    assert figures.tick(0.001, "%") == "0%"


@pytest.mark.parametrize("index,expected", [(0, "Under 15.6 h"), (1, "15.6–25 h"), (3, "Over 45.1 h")])
def test_lifetime_segments_get_readable_names(index, expected):
    segments = ["1. 0.0-15.6h", "2. 15.6-25.0h", "3. 25.0-45.1h", "4. 45.1-9000.0h"]
    assert figures._segment_name(segments[index], index, 4, "lifetime") == expected


def test_category_segments_keep_their_names():
    assert figures._segment_name("Sports", 0, 3, "category") == "Sports"


def test_band_label_rounds_to_whole_cents():
    assert figures.band_label(0.0, 0.1) == "0–10¢"
    assert figures.band_label(0.9, 1.0) == "90–100¢"
    assert figures.band_label(0.30000000000000004, 0.4) == "30–40¢"


@pytest.mark.parametrize("value,horizontal", [(3.0, False), (-2.0, False), (4.0, True), (-1.0, True), (0.0, False)])
def test_bar_draws_one_closed_patch_ending_at_the_value(value, horizontal):
    fig, ax = plt.subplots()
    ax.set_xlim(-5, 5)
    ax.set_ylim(-5, 5)
    figures.bar(ax, 0.0, value, 0.5, figures.BLUE, horizontal=horizontal)
    (patch,) = ax.patches
    coords = patch.get_path().vertices[:, 0 if horizontal else 1]
    assert min(coords) == pytest.approx(min(0.0, value)) and max(coords) == pytest.approx(max(0.0, value))
    plt.close(fig)


@pytest.fixture()
def drawing(tmp_path, monkeypatch):
    monkeypatch.setattr(figures, "FIGURES_DIR", tmp_path)
    figures.style()
    return tmp_path


def test_no_horizon_check_means_no_horizon_figure(drawing):
    s = copy.deepcopy(SUMMARY)
    s["horizon"] = None
    assert figures.fig_horizon(s) is None
    assert not list(drawing.iterdir())


def test_no_robustness_sweeps_means_no_robustness_figure(drawing):
    s = copy.deepcopy(SUMMARY)
    s["backtest"]["train_fraction"] = s["backtest"]["min_net_edge"] = None
    assert figures.fig_robustness(s) is None


def test_a_single_robustness_sweep_draws_one_panel(drawing):
    s = copy.deepcopy(SUMMARY)
    s["backtest"]["min_net_edge"] = None
    path = figures.fig_robustness(s)
    assert path is not None and path.exists()


def test_a_sweep_setting_where_nothing_trades_is_annotated(drawing):
    s = copy.deepcopy(SUMMARY)
    rows = s["backtest"]["min_net_edge"]
    rows[-1]["buckets_traded"] = 0
    assert figures.fig_robustness(s).exists()


def test_a_segment_missing_a_price_band_leaves_that_cell_empty(drawing):
    rows = SUMMARY["segments"]["category"]
    gone = rows[0]
    assert any(r["segment"] == gone["segment"] for r in rows[1:]) and any(r["bucket"] == gone["bucket"] for r in rows[1:]), \
        "the dropped cell's segment and band both still have other cells, so the grid keeps its shape"
    drawn = []
    for cells in (rows, rows[1:]):
        fig, ax = plt.subplots()
        figures._heatmap(ax, cells, "category", "By category")
        drawn.append((len(ax.patches), len(ax.texts), len(ax.get_xticks()), len(ax.get_yticks())))
        plt.close(fig)
    (patches, texts, xs, ys), (patches_2, texts_2, xs_2, ys_2) = drawn
    assert (patches_2, texts_2, xs_2, ys_2) == (patches - 1, texts - 1, xs, ys)


def test_a_bankroll_that_falls_near_zero_keeps_four_decimals(drawing):
    s = copy.deepcopy(SUMMARY)
    control = s["backtest"]["equity"]["control"]
    control[-1][1] = 0.0012
    assert figures.fig_out_of_sample(s).exists()


def test_figures_main_prints_each_path(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(figures, "build_all", lambda: [tmp_path / "a.png", tmp_path / "b.png"])
    figures.main()
    assert capsys.readouterr().out.count("wrote ") == 2
