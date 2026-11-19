"""Property-based tests for every parser that reads what Kalshi (or a killed run) left on disk.

The study's rule is that one odd record never aborts a long run: a bad timestamp becomes None, a bad price
becomes a counted drop, a half-written line is re-fetched. These feed the parsers arbitrary values and
arbitrarily truncated files and check that each one either parses or declines, never crashes, and that the
resume check and the progress dashboard always agree on what is done.

Two strict xfails record where a parser does NOT yet honour that rule; each flips to a failure once fixed.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from kalshi_calibration import clean
from kalshi_calibration.clean import PRICE_METHODS, compute_implied_price, load_horizon_trades
from kalshi_calibration.ingest import kalshi, trades
from kalshi_calibration.ingest.summary import _settlement_date
from kalshi_calibration.ingest.trades import _load_done
from kalshi_calibration.ingest.trades_progress import scan_horizon_file
from kalshi_calibration.replication.fetch import MINUTES, candle_close, minute_row

UTC = timezone.utc
json_scalars = st.none() | st.booleans() | st.integers() | st.floats() | st.text(max_size=30)
json_values = st.recursive(json_scalars, lambda inner: st.lists(inner, max_size=3)
                           | st.dictionaries(st.text(max_size=5), inner, max_size=3), max_leaves=6)

TEXT_PARSERS = {
    "kalshi": kalshi._parse_ts,
    "trades": trades._parse_ts,
    "clean": clean._parse_ts,
    "summary": lambda raw: _settlement_date({"settlement_ts": raw}),
}

# ------------------------------------------------------------------ timestamps

# Fixed offsets, as an ISO string carries: a named zone's local time inside a DST fold or gap compares unequal
# to every other zone's datetime (PEP 495), which would test Python's comparison rather than the parser.
iso_times = st.datetimes(min_value=datetime(1971, 1, 1), max_value=datetime(2099, 12, 31),
                         timezones=st.integers(-14 * 60, 14 * 60).map(lambda m: timezone(timedelta(minutes=m))))


@pytest.mark.parametrize("name", TEXT_PARSERS)
@given(raw=st.text(max_size=40) | st.none())
def test_no_text_crashes_a_timestamp_parser(name, raw):
    parsed = TEXT_PARSERS[name](raw)
    assert parsed is None or isinstance(parsed, datetime) or hasattr(parsed, "year")


@pytest.mark.parametrize("name", ["kalshi", "trades", "clean"])
@given(when=iso_times)
def test_every_iso_time_parses_to_the_same_instant_in_utc(name, when):
    text = when.isoformat()
    for spelling in (text, text.replace("+00:00", "Z")):
        parsed = TEXT_PARSERS[name](spelling)
        assert parsed == when and parsed.utcoffset().total_seconds() == 0


@given(when=iso_times)
def test_the_summary_reads_the_utc_settlement_day(when):
    assert _settlement_date({"settlement_ts": when.isoformat()}) == when.astimezone(UTC).date()


@pytest.mark.parametrize("name", ["trades", "clean", "summary"])
@given(raw=json_values.filter(lambda v: not isinstance(v, str)))
def test_a_non_text_timestamp_is_none_not_a_crash(name, raw):
    assert TEXT_PARSERS[name](raw) is None


@pytest.mark.xfail(strict=True, raises=AttributeError,
                   reason="bug: kalshi._parse_ts catches only ValueError, so a non-string settlement_ts aborts "
                          "the series walk; its siblings in trades.py and clean.py return None")
def test_kalshis_timestamp_parser_survives_a_non_text_value():
    assert kalshi._parse_ts(1767225600) is None


@given(raw=json_values)
def test_volume_never_crashes_the_series_ranking(raw):
    volume = kalshi._volume({"ticker": "S", "volume_fp": raw})
    assert isinstance(volume, float)
    try:
        expected = 0.0 if raw is None else float(raw)
    except (TypeError, ValueError):
        expected = 0.0
    assert volume == expected or (math.isnan(volume) and math.isnan(expected))


# ------------------------------------------------------------------ prices

market_fields = st.fixed_dictionaries({}, optional={
    "last_price_dollars": json_values, "previous_price_dollars": json_values,
    "yes_bid_dollars": json_values, "yes_ask_dollars": json_values,
})


@given(st.sampled_from(sorted(PRICE_METHODS)), market_fields,
       st.none() | st.fixed_dictionaries({}, optional={"yes_price_dollars": json_values}))
def test_a_price_is_a_probability_or_nothing(method, market, trade):
    price = compute_implied_price(market, method, trade)
    assert price is None or (isinstance(price, float) and 0.0 <= price <= 1.0)


@given(st.floats(0, 1), st.floats(0, 1))
def test_the_mid_is_between_the_quotes_unless_the_book_is_empty(bid, ask):
    mid = compute_implied_price({"yes_bid_dollars": str(bid), "yes_ask_dollars": str(ask)}, "bid_ask_mid")
    if bid <= 0.0 and ask >= 1.0:
        assert mid is None
    else:
        assert mid == pytest.approx((bid + ask) / 2)


@given(st.text(max_size=20).filter(lambda m: m not in PRICE_METHODS))
def test_an_unknown_price_method_is_refused(method):
    with pytest.raises(ValueError, match="unknown price_method"):
        compute_implied_price({}, method)


# ------------------------------------------------------------------ JSONL written by the horizon pass

records = st.lists(
    st.fixed_dictionaries({
        "ticker": st.text(alphabet="ABCDEFGHJK-0123456789", min_size=1, max_size=8),
        "trade": st.none() | st.fixed_dictionaries({"yes_price_dollars": st.sampled_from(["0.42", "0.07"])}),
    }),
    max_size=12,
)


@settings(max_examples=80)
@given(records, st.data())
def test_a_file_cut_off_at_any_byte_reads_back_as_its_complete_lines(tmp_path_factory, rows, data):
    root = tmp_path_factory.mktemp("trades")
    path = root / "kalshi" / "T1h" / "Econ" / "S.jsonl"
    path.parent.mkdir(parents=True)
    lines = [json.dumps(r) + "\n" for r in rows]
    blob = "".join(lines).encode("utf-8")
    cut = data.draw(st.integers(0, len(blob)))
    path.write_bytes(blob[:cut])

    complete, offset = [], 0
    for line, row in zip(lines, rows):
        end = offset + len(line.encode("utf-8"))
        if end - 1 <= cut:      # the JSON text is whole, with or without its newline
            complete.append(row)
        offset = end

    done = {r["ticker"] for r in complete}
    assert _load_done(path) == done
    tickers, no_trade = scan_horizon_file(path)
    assert tickers == done
    first_seen = {}
    for r in complete:
        first_seen.setdefault(r["ticker"], r)
    assert no_trade == sum(1 for r in first_seen.values() if r["trade"] is None)
    loaded = load_horizon_trades(root, 1)
    assert set(loaded) == done
    last = {r["ticker"]: r["trade"] for r in complete}
    assert loaded == last, "a ticker written twice keeps its latest record"


@settings(max_examples=60)
@given(st.lists(st.text(max_size=30), max_size=8))
def test_the_resume_check_and_the_dashboard_agree_on_any_text_file(tmp_path_factory, lines):
    """Arbitrary lines, as long as none parses to a JSON value that isn't an object (see the xfail below)."""
    def parses_to_non_object(line):
        try:   # as the readers see it: stripped first
            return not isinstance(json.loads(line.strip()), dict)
        except ValueError:
            return False

    lines = [line.replace("\n", " ") for line in lines if not parses_to_non_object(line.replace("\n", " "))]
    path = tmp_path_factory.mktemp("j") / "S.jsonl"
    path.write_text("".join(line + "\n" for line in lines), encoding="utf-8")
    assert _load_done(path) == scan_horizon_file(path)[0]


@pytest.mark.xfail(strict=True, raises=TypeError,
                   reason="bug: _load_done catches JSONDecodeError and KeyError but not the TypeError a valid "
                          "non-object JSON line raises; scan_horizon_file, documented as its mirror, skips it")
def test_a_valid_json_line_that_is_not_an_object_is_not_done(tmp_path):
    path = tmp_path / "S.jsonl"
    path.write_text('{"ticker": "A"}\n5\n', encoding="utf-8")
    assert _load_done(path) == scan_horizon_file(path)[0] == {"A"}


# ------------------------------------------------------------------ replication candles


@given(st.none() | st.dictionaries(st.sampled_from(["close", "close_dollars", "previous", "previous_dollars", "x"]),
                                   st.none() | st.floats(0, 1).map(lambda f: f"{f:.4f}"), max_size=4))
def test_a_candle_value_is_a_number_or_nothing(block):
    value = candle_close(block)
    assert value is None or 0.0 <= value <= 1.0


candles = st.lists(st.fixed_dictionaries({
    "minute": st.integers(0, 17),
    "price": st.none() | st.fixed_dictionaries({"close_dollars": st.none() | st.sampled_from(["0.10", "0.50", "0.95"])}),
    "yes_bid": st.fixed_dictionaries({"close_dollars": st.none() | st.sampled_from(["0.40", "0.93"])}),
    "yes_ask": st.fixed_dictionaries({"close_dollars": st.none() | st.sampled_from(["0.45", "0.96"])}),
}), max_size=10)


@given(candles)
def test_each_minute_carries_the_latest_quote_at_or_before_it(raw):
    open_ts = 1_780_000_000
    built = [{**{k: v for k, v in c.items() if k != "minute"}, "end_period_ts": open_ts + 60 * c["minute"]} for c in raw]
    market = {"series": "S", "ticker": "T", "open_time": "x", "resolved_yes": "1"}
    row = minute_row(market, open_ts, built)
    if not built:
        assert row is None
        return
    by_minute = {c["minute"]: c for c in raw}       # a later candle for the same minute wins, as in minute_row
    for field, key in (("p", "price"), ("b", "yes_bid"), ("a", "yes_ask")):
        latest = None
        for k in MINUTES:
            candle = by_minute.get(k)
            value = candle_close(candle.get(key)) if candle else None
            if value is not None:
                latest = value
            assert row[f"{field}{k}"] == ("" if latest is None else latest)
