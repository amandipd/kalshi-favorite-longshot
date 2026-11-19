"""Tests for kalshi_calibration/figures.py: every figure draws from the committed reports, and a missing report is skipped."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from kalshi_calibration import figures

ROOT = Path(__file__).resolve().parent.parent


def test_every_figure_draws_from_the_reports(tmp_path, monkeypatch):
    monkeypatch.setattr(figures, "FIGURES_DIR", tmp_path)
    monkeypatch.setattr(figures, "SUMMARY_PATH", ROOT / "reports" / "summary.json")
    monkeypatch.setattr(figures, "REPLICATION_PATH", ROOT / "reports" / "replication.json")
    made = figures.build_all()
    assert [p.name for p in made] == [
        "fig1_calibration.png", "fig2_bias_by_band.png", "fig3_bias_by_segment.png", "fig4_horizon.png",
        "fig5_out_of_sample.png", "fig6_robustness.png", "fig7_replication.png", "fig8_kelly_and_stops.png",
    ]
    for path in made:
        with Image.open(path) as im:
            assert im.width >= 1200 and im.height >= 900


def test_a_missing_report_skips_its_figures(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(figures, "FIGURES_DIR", tmp_path)
    monkeypatch.setattr(figures, "SUMMARY_PATH", tmp_path / "none.json")
    monkeypatch.setattr(figures, "REPLICATION_PATH", tmp_path / "none.json")
    assert figures.build_all() == []
    assert "make analyze" in capsys.readouterr().out


def test_axis_labels_are_signed_and_keep_only_the_decimals_they_need():
    assert figures.tick(2.5, "%") == "+2.5%"
    assert figures.tick(-7.5, "%") == "−7.5%"
    assert figures.tick(2.0, "¢") == "+2¢"
    assert figures.tick(0.0, "¢") == "0¢"


def test_band_labels_read_in_cents():
    assert figures.band_label(0.3, 0.4) == "30–40¢"
