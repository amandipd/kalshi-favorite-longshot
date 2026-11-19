"""fetch_spot.py's pure helpers: request chunking and turning Coinbase candles into a dense minute grid."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fetch_spot  # noqa: E402
import fetch_strikes  # noqa: E402


def test_chunks_cover_range_without_gaps_or_overlap():
    t0, t1 = 1_000_020, 1_000_020 + 60 * 1000          # 1000 minutes
    cs = fetch_spot.chunks(t0, t1)
    assert cs[0][0] == t0 and cs[-1][1] == t1 - 60     # last minute start is t1 - 60
    for (a, b), (c, _) in zip(cs, cs[1:]):
        assert c == b + 60                              # next chunk starts the minute after
    assert all((b - a) // 60 + 1 <= 300 for a, b in cs)
    assert sum((b - a) // 60 + 1 for a, b in cs) == 1000


def test_to_grid_places_forward_fills_and_drops_out_of_range():
    t0 = 6000
    # Coinbase rows: [time, low, high, open, close, volume], newest first
    rows = [[t0 + 240, 9, 11, 10, 10.5, 2.0],
            [t0 + 120, 7, 9, 8, 8.5, 1.0],
            [t0 + 60, 5, 7, 6, 6.5, 1.0],
            [t0 + 9999 * 60, 1, 1, 1, 1, 1.0],          # outside the grid
            [t0 + 60, 5, 7, 6, 6.5, 1.0]]               # duplicate
    g = fetch_spot.to_grid(rows, t0, 6)
    assert math.isnan(g["close"][0])                    # nothing before the first candle
    assert list(g["close"][1:]) == [6.5, 8.5, 8.5, 10.5, 10.5]
    assert list(g["have"]) == [False, True, True, False, True, False]
    assert g["avg"][1] == (5 + 7 + 6 + 6.5) / 4
    assert g["avg"][3] == 8.5                            # a quiet minute averages at the carried close
    assert g["vol"][3] == 0


def test_strike_row_parses_numbers_and_missing():
    m = {"ticker": "KXBTC15M-X", "open_time": "2026-08-11T23:30:00Z", "floor_strike": 63538.11,
         "expiration_value": "63581.35", "result": "yes"}
    assert fetch_strikes.strike_row(m) == ("KXBTC15M-X", 1786491000, 63538.11, 63581.35, 1)
    r = fetch_strikes.strike_row({"ticker": "Y", "open_time": "2026-08-11T23:30:00Z", "result": "no"})
    assert math.isnan(r[2]) and math.isnan(r[3]) and r[4] == 0


def test_strike_row_reads_thousands_commas():
    r = fetch_strikes.strike_row({"ticker": "Z", "open_time": "2026-08-11T23:30:00Z", "floor_strike": "77,362.10",
                                  "expiration_value": "77,400.00", "result": "yes"})
    assert r[2:] == (77362.1, 77400.0, 1)
