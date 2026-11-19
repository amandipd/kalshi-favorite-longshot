"""Fetch the replication's data from Kalshi: every settled 15-minute market in the study window, with
its last trade, bid and ask at the end of each minute.

    python -m kalshi_calibration.replication.fetch          (make replicate-data; resumable)

Kalshi splits its data at a moving cutoff (GET /historical/cutoff). Markets settled before it are
served only by the /historical/* endpoints and newer ones only by the live endpoints, and the two
report candle prices in different fields. So each series is listed from both sides, and a market's
minute candles are read from the side that listed it: one batch request per 15-minute window on the
live side (a window's markets share an open and a close), one request per market on the historical
side. Every endpoint used is public; nothing here needs an account.

Output, in `replication.data_dir`:

    series.json   the 15-minute series in the studied groups, each with its group, and the cutoff
                  at the time of the run
    minutes.csv   one row per market: series, ticker, open_time, resolved_yes, then for minutes
                  1-15 the last trade (p), YES bid (b) and YES ask (a) at the end of the minute. A
                  minute with no candle carries the one before it forward.

A rerun fetches only markets not already in minutes.csv, so an interrupted run resumes.
"""

from __future__ import annotations

import csv
import json
import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from kalshi_calibration.config import Config, get_config
from kalshi_calibration.ingest.base import APIClient

logger = logging.getLogger(__name__)

MINUTES = range(1, 16)
FIELDS = (
    ["series", "ticker", "open_time", "resolved_yes"]
    + [f"p{k}" for k in MINUTES]
    + [f"b{k}" for k in MINUTES]
    + [f"a{k}" for k in MINUTES]
)
SERIES_FILE = "series.json"
MINUTES_FILE = "minutes.csv"
FREQUENCY = "fifteen_min"
PAGE_LIMIT = 1000


def group_of(ticker: str, category: str = "") -> str:
    """The group a 15-minute series belongs to. Markets in one group move together."""
    t = ticker.upper()
    if "CRYPTOLEAD" in t or "CRYPTOCOMP" in t:
        return "coin race"
    if any(x in t for x in ("GOLD", "SILVER", "PLATINUM", "PALLADIUM", "COPPER")):
        return "metals"
    if any(x in t for x in ("WTI", "BRENT", "NATGAS", "OIL")):
        return "energy"
    if any(x in t for x in ("EURUSD", "GBPUSD", "USDJPY")):
        return "fx"
    if "RATE" in t:
        return "rates"
    if "INX" in t or "NDQ" in t:
        return "stock index"
    return "crypto" if category == "Crypto" else category.lower() or "other"


def iso_ts(text: str) -> int:
    """Seconds since the epoch for an ISO time such as 2026-07-18T00:15:00Z."""
    return int(datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp())


def candle_close(block: dict[str, Any] | None) -> float | None:
    """A candle field's value at the end of its minute.

    Live candles call it `close_dollars` and historical ones `close`. A minute with no trade has no
    close for the price, only the last trade before it (`previous_dollars` / `previous`).
    """
    block = block or {}
    for key in ("close_dollars", "close"):
        if key in block:
            return None if block[key] is None else float(block[key])
    for key in ("previous_dollars", "previous"):
        if block.get(key) is not None:
            return float(block[key])
    return None


def minute_row(market: dict[str, str], open_ts: int, candles: list[dict[str, Any]]) -> dict[str, Any] | None:
    """A market's row for minutes.csv, or None when it has no candles at all."""
    by_minute = {(c["end_period_ts"] - open_ts) // 60: c for c in candles}
    if not by_minute:
        return None
    row: dict[str, Any] = {k: market[k] for k in ("series", "ticker", "open_time", "resolved_yes")}
    last: dict[str, float | None] = {"p": None, "b": None, "a": None}
    for k in MINUTES:
        candle = by_minute.get(k)
        if candle:
            for field, key in (("p", "price"), ("b", "yes_bid"), ("a", "yes_ask")):
                value = candle_close(candle.get(key))
                if value is not None:
                    last[field] = value
        for field in "pba":
            row[f"{field}{k}"] = "" if last[field] is None else last[field]
    return row


def repair_tail(path: Path) -> None:
    """Drop a half-written last line, which a run killed mid-write can leave behind."""
    if not path.exists() or path.stat().st_size == 0:
        return
    data = path.read_bytes()
    if not data.endswith(b"\n"):
        path.write_bytes(data[: data.rfind(b"\n") + 1])


def saved_tickers(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open(newline="") as fh:
        return {r["ticker"] for r in csv.DictReader(fh)}


class ReplicationFetcher(APIClient):
    """Builds data/replication/ from Kalshi's public API.

        with ReplicationFetcher(get_config()) as fetcher:
            print(fetcher.run())
    """

    def __init__(self, config: Config, data_dir: Path | None = None, **kwargs: Any) -> None:
        """
        Args:
            config: Validated config.yaml; its `replication` section sets the window and groups.
            data_dir: Override the output folder (tests use a tmp_path).
            **kwargs: Forwarded to APIClient, notably `transport` for an httpx.MockTransport.
        """
        if config.replication is None:
            raise ValueError("config.yaml has no `replication` section")
        super().__init__(
            base_url=config.kalshi_base_url,
            rate_limit_per_second=config.replication.rate_limit_per_second,
            retry=config.retry,
            **kwargs,
        )
        self.settings = config.replication
        self.data_dir = Path(data_dir) if data_dir is not None else Path(self.settings.data_dir)

    def series(self) -> list[dict[str, Any]]:
        """The 15-minute series in the studied groups, from Kalshi's series catalog."""
        out = []
        for s in self.get("/series").get("series", []):
            if s.get("frequency") != FREQUENCY or s["ticker"].upper().endswith("TEST"):
                continue
            group = group_of(s["ticker"], s.get("category", ""))
            if group in self.settings.groups:
                out.append({"ticker": s["ticker"], "title": s.get("title"), "category": s.get("category"),
                            "group": group, "fee_multiplier": s.get("fee_multiplier")})
        return sorted(out, key=lambda s: s["ticker"])

    def markets(self, series: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
        """{ticker: market} for every settled market in the window, tagged with the side that served it.

        A market listed by both sides is read from the live one.
        """
        start = f"{self.settings.start.isoformat()}T00:00:00Z"
        end = f"{self.settings.end.isoformat()}T00:00:00Z"
        found: dict[str, dict[str, str]] = {}
        for s in series:
            for source, endpoint in (("historical", "/historical/markets"), ("live", "/markets")):
                for _, page in self.paginate(endpoint, {"series_ticker": s["ticker"], "limit": PAGE_LIMIT}):
                    for m in page.get("markets", []):
                        if m.get("result") in ("yes", "no") and start <= m["open_time"] < end:
                            found[m["ticker"]] = {
                                "series": s["ticker"], "ticker": m["ticker"], "open_time": m["open_time"],
                                "resolved_yes": "1" if m["result"] == "yes" else "0", "source": source,
                            }
        return found

    def window_rows(self, open_time: str, markets: list[dict[str, str]]) -> list[dict[str, Any]]:
        """minutes.csv rows for one window's markets."""
        open_ts = iso_ts(open_time)
        span = {"start_ts": open_ts, "end_ts": open_ts + 900, "period_interval": 1}
        candles: dict[str, list[dict[str, Any]]] = {}
        live = [m["ticker"] for m in markets if m["source"] == "live"]
        if live:
            page = self.get("/markets/candlesticks", {"market_tickers": ",".join(live), **span})
            candles.update({x["market_ticker"]: x.get("candlesticks", []) for x in page.get("markets", [])})
        for m in markets:
            if m["source"] == "historical":
                page = self.get(f"/historical/markets/{m['ticker']}/candlesticks", span)
                candles[m["ticker"]] = page.get("candlesticks", [])
        rows = (minute_row(m, open_ts, candles.get(m["ticker"], [])) for m in markets)
        return [r for r in rows if r is not None]

    def run(self) -> dict[str, int]:
        """Fetch whatever minutes.csv is missing. Returns counts for the run."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        cutoff = self.get("/historical/cutoff")
        series = self.series()
        (self.data_dir / SERIES_FILE).write_text(json.dumps({
            "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "cutoff": cutoff, "series": series,
        }, indent=1), encoding="utf-8")

        markets = self.markets(series)
        out = self.data_dir / MINUTES_FILE
        repair_tail(out)
        have = saved_tickers(out)
        todo: dict[str, list[dict[str, str]]] = defaultdict(list)
        for m in markets.values():
            if m["ticker"] not in have:
                todo[m["open_time"]].append(m)
        n_todo = sum(len(v) for v in todo.values())
        print(f"{len(series)} series, {len(markets):,} settled markets in the window; {len(have):,} already "
              f"saved, fetching {n_todo:,} in {len(todo):,} windows", flush=True)

        written = failed = 0
        new_file = not out.exists()
        with out.open("a", newline="") as fh, ThreadPoolExecutor(self.settings.workers) as pool:
            writer = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
            if new_file:
                writer.writeheader()
            futures = {pool.submit(self.window_rows, t, ms): t for t, ms in sorted(todo.items())}
            for done, future in enumerate(as_completed(futures), 1):
                try:
                    rows = future.result()
                except Exception as exc:  # one failed window must not lose the others; a rerun retries it
                    failed += 1
                    logger.warning("event=window_failed open_time=%s error=%s", futures[future], exc)
                    continue
                writer.writerows(rows)
                fh.flush()
                written += len(rows)
                if done % 250 == 0:
                    print(f"  {done:,}/{len(todo):,} windows", flush=True)
        return {"series": len(series), "markets": len(markets), "already_saved": len(have),
                "written": written, "failed_windows": failed}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    # One log line per request is tens of thousands of lines here; keep the progress readable.
    for noisy in ("kalshi_calibration.ingest.base", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    with ReplicationFetcher(get_config()) as fetcher:
        counts = fetcher.run()
    print(", ".join(f"{k.replace('_', ' ')} {v:,}" for k, v in counts.items()))
    if counts["failed_windows"]:
        print("Some windows failed; run it again to fetch them.")


if __name__ == "__main__":
    main()
