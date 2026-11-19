"""The replication's markets, read back from data/replication/ (written by kalshi_calibration/replication/fetch.py)."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from pathlib import Path

from kalshi_calibration.config import ReplicationConfig
from kalshi_calibration.replication.fetch import MINUTES, MINUTES_FILE, SERIES_FILE, iso_ts


@dataclass(frozen=True)
class Market:
    """One settled 15-minute market.

    `last`, `bid` and `ask` are indexed by minute (index 0 is unused and None): the last trade and
    the YES bid and ask at the end of that minute, None when nothing had traded or been quoted yet.
    """

    series: str
    ticker: str
    group: str
    open_ts: int
    yes: bool
    last: tuple[float | None, ...]
    bid: tuple[float | None, ...]
    ask: tuple[float | None, ...]


def day_ts(day: date) -> int:
    """Midnight UTC at the start of `day`, in seconds."""
    return int(datetime.combine(day, time(), tzinfo=timezone.utc).timestamp())


def _num(text: str) -> float | None:
    return float(text) if text != "" else None


def parse_row(row: dict[str, str], group: str) -> Market:
    def minutes(prefix: str) -> tuple[float | None, ...]:
        return (None,) + tuple(_num(row[f"{prefix}{k}"]) for k in MINUTES)

    return Market(series=row["series"], ticker=row["ticker"], group=group, open_ts=iso_ts(row["open_time"]),
                  yes=row["resolved_yes"] == "1", last=minutes("p"), bid=minutes("b"), ask=minutes("a"))


def load_markets(settings: ReplicationConfig, data_dir: Path | None = None) -> list[Market]:
    """Every market in the studied groups that opened in the window, once each, in time order."""
    folder = Path(data_dir) if data_dir is not None else Path(settings.data_dir)
    if not (folder / MINUTES_FILE).exists():
        raise FileNotFoundError(f"{folder / MINUTES_FILE} is missing; run `make replicate-data` first")
    catalog = json.loads((folder / SERIES_FILE).read_text(encoding="utf-8"))["series"]
    groups = {s["ticker"]: s["group"] for s in catalog}
    start, end = day_ts(settings.start), day_ts(settings.end)
    out, seen = [], set()
    with (folder / MINUTES_FILE).open(newline="") as fh:
        for row in csv.DictReader(fh):
            group = groups.get(row["series"])
            if row["ticker"] in seen or group not in settings.groups:
                continue
            market = parse_row(row, group)
            if start <= market.open_ts < end:
                seen.add(row["ticker"])
                out.append(market)
    return sorted(out, key=lambda m: (m.open_ts, m.series))
