"""Third ingestion pass: the price a market opened at.

    python -m kalshi_calibration.ingest.open_trades                 # every configured window
    python -m kalshi_calibration.ingest.open_trades --window 6      # just the first 6h

The first pass (`kalshi_calibration/ingest/kalshi.py`) gives one post-settlement snapshot per
market. The second (`kalshi_calibration/ingest/trades.py`) gives the last trade an hour before
close, which is the price the study treats as the market's forecast. Both sample
the *end* of a market's life.

This pass samples the *start*: the first trade at or after `open_time`. The
question it exists to answer is whether a newly listed market is mispriced
before its order book deepens, which nobody has measured on Kalshi. The
hypothesis, the bands, and the decision rule were fixed in advance in
research/opening_price/PREREG.md -- read that before reading any output of this
module, because the result it motivates was found by looking.

**Why this is harder than the T-1h pass.** `/historical/trades` returns
newest-first. The T-1h pass therefore asks for a single row and is done: row one
*is* the last trade before its cutoff. Here the trade we want is at the other
end of the feed -- the last row of the last page -- so we have to walk backwards
with the cursor. Two bounds make that terminate:

    min_ts = open_time              the walk cannot run off the start
    max_ts = open_time + window     the walk starts at the end of the window

A page that comes back **short** is the proof we reached the open: there was
nothing older left to return. A page that comes back **full** means older trades
exist that we have not seen, so the oldest row we hold is *not* the opening
trade. If the page cap runs out in that state the market is recorded with
`complete: false` and a null `first_trade`, because a market priced off the
wrong trade is worse than a market with no price -- the first contaminates the
sample quietly, the second is counted as an exclusion.

Layout, one JSONL file per series per window:

    data/raw_trades/kalshi/OPEN<window>h/<category>/<series>.jsonl

One line per market, as in the T-1h pass, and resumption likewise reads back the
tickers already present so a killed run resumes where it stopped.

Like both earlier passes this writes what the API returned and defers every
judgment to kalshi_calibration/clean.py -- including which of the stored trades becomes the
opening price. `keep_trades` oldest trades are kept rather than only the first,
so the choice between "the first print" and "an average of the first few" can be
made later without going back to the API.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from kalshi_calibration.config import Config, get_config
from kalshi_calibration.ingest.base import APIClient
from kalshi_calibration.ingest.trades import (
    TRADES_ENDPOINT,
    VENUE,
    _load_done,
    _parse_ts,
    iter_binary_markets,
)

logger = logging.getLogger(__name__)


def window_dirname(hours: float) -> str:
    """`1.0 -> 'OPEN1h'`, `0.5 -> 'OPEN0.5h'`. Stable, so the path is the resume key."""
    trimmed = int(hours) if float(hours).is_integer() else hours
    return f"OPEN{trimmed}h"


# The climbing pass writes one directory, not one per window, because it is
# answering one question -- what was the first trade -- rather than sweeping a
# parameter. The window it happened to find the answer in is recorded per
# market instead.
FIRST_TRADE_DIR = "OPENFIRST"


def _take_shard(
    by_series: dict[tuple[str, str], list[dict[str, Any]]], index: int, count: int
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    """The slice of the work belonging to shard `index` of `count`.

    Deals whole series, largest first, onto whichever shard is currently
    lightest. Series sizes are very uneven, so dealing round-robin by position
    would leave one worker with most of the markets. Whole series per shard is
    also what keeps two workers off the same output file.

    Deterministic: the same inputs always produce the same split, so a shard can
    be re-run or resumed on its own.
    """
    if not 0 <= index < count:
        raise ValueError(f"shard index {index} out of range for count {count}")

    loads = [0] * count
    picked: dict[tuple[str, str], list[dict[str, Any]]] = {}
    # Sort by size descending, then by name, so ties break the same way every run.
    for key in sorted(by_series, key=lambda k: (-len(by_series[k]), k)):
        lightest = min(range(count), key=lambda s: (loads[s], s))
        if lightest == index:
            picked[key] = by_series[key]
        loads[lightest] += len(by_series[key])
    return picked


@dataclass
class FirstTrade:
    """The outcome of climbing the ladder for one market.

    `complete` is the one field that matters for correctness. False means the
    walk never reached the open, so `trade` is None even if trades were seen:
    pricing a market off whichever trade happened to be oldest in a partial
    fetch would contaminate the study quietly, where a missing price is counted
    as an exclusion.
    """

    trade: dict[str, Any] | None
    trades: list[dict[str, Any]]
    window_hours: float
    complete: bool
    pages: int
    seen: int


@dataclass
class OpenStats:
    """What a window run did.

    Three of these counters are exclusions the prereg owes a number for, not
    failures:

    `no_trade`  the market did not trade at all inside its opening window. This
        is the retention question, and it is expected to be large for short
        windows -- a pilot market's first trade landed 1h 0m 35s after it
        opened.
    `no_open_time`  the snapshot carried no `open_time`, so there is no window
        to ask about.
    `incomplete`  the window held more trades than `max_pages` could walk back
        through, so the opening trade was never reached.
    """

    window_hours: float
    markets_total: int = 0
    fetched: int = 0
    skipped_cached: int = 0
    no_trade: int = 0
    no_open_time: int = 0
    incomplete: int = 0
    errors: int = 0
    pages: int = 0
    no_trade_per_category: dict[str, int] = field(default_factory=dict)

    def summary(self) -> str:
        pct = (100.0 * self.no_trade / self.fetched) if self.fetched else 0.0
        return (
            f"window={window_dirname(self.window_hours)} "
            f"markets={self.markets_total} fetched={self.fetched} "
            f"cached={self.skipped_cached} no_trade={self.no_trade} ({pct:.1f}% of fetched) "
            f"no_open_time={self.no_open_time} incomplete={self.incomplete} "
            f"pages={self.pages} errors={self.errors}"
        )


class KalshiOpenTradesClient(APIClient):
    """Prices every settled binary market at the open of one or more windows.

        with KalshiOpenTradesClient.from_config() as client:
            for stats in client.fetch_all_windows():
                print(stats.summary())
    """

    def __init__(
        self,
        config: Config,
        raw_dir: Path | None = None,
        open_trades_dir: Path | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            base_url=config.kalshi_base_url,
            rate_limit_per_second=config.rate_limit_per_second,
            retry=config.retry,
            **kwargs,
        )
        self.config = config
        self.settings = config.ingest.open_trades
        if self.settings is None:
            raise ValueError(
                "ingest.open_trades is not configured; add it to config.yaml "
                "(see kalshi_calibration/config.py OpenTradesConfig)"
            )
        self.raw_dir = Path(raw_dir) if raw_dir is not None else Path(config.ingest.raw_dir)
        root = (
            Path(open_trades_dir)
            if open_trades_dir is not None
            else Path(self.settings.open_trades_dir)
        )
        self.venue_dir = root / VENUE

    @classmethod
    def from_config(cls, **kwargs: Any) -> "KalshiOpenTradesClient":
        return cls(get_config(), **kwargs)

    def window_dir(self, hours: float) -> Path:
        return self.venue_dir / window_dirname(hours)

    def fetch_opening_window(
        self, ticker: str, open_at: datetime, hours: float
    ) -> tuple[list[dict[str, Any]], bool, int]:
        """Trades in `[open_at, open_at + hours]`, oldest first.

        Returns `(trades, complete, pages)`. `complete` is True when the walk
        ran out of trades rather than out of pages -- only then is `trades[0]`
        the market's genuine first trade.

        The feed is newest-first, so each page is older than the last and the
        accumulated list is reversed once at the end.
        """
        limit = self.settings.request_limit
        params: dict[str, Any] = {
            "ticker": ticker,
            "limit": limit,
            "min_ts": int(open_at.timestamp()),
            "max_ts": int((open_at + timedelta(hours=hours)).timestamp()),
        }

        newest_first: list[dict[str, Any]] = []
        cursor: str | None = None
        complete = False
        pages = 0

        for _ in range(self.settings.max_pages):
            payload = self.get(TRADES_ENDPOINT, {**params, **({"cursor": cursor} if cursor else {})})
            pages += 1
            page = payload.get("trades") or []
            newest_first.extend(page)

            # A short page means the feed is exhausted inside our bounds, which
            # is the only evidence that the oldest row we hold is the opening
            # trade. An absent cursor says the same thing.
            cursor = payload.get("cursor") or None
            if len(page) < limit or not cursor:
                complete = True
                break

        return list(reversed(newest_first)), complete, pages

    def fetch_window(self, hours: float) -> OpenStats:
        """Price every binary market at its first trade after `open_time`.

        Grouped by series so each series' JSONL is opened once and appended to
        as the run proceeds -- a killed run keeps everything already written.
        """
        stats = OpenStats(window_hours=hours)
        out_root = self.window_dir(hours)
        keep = self.settings.keep_trades

        by_series: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for market in iter_binary_markets(self.raw_dir):
            by_series.setdefault((market["category"], market["series"]), []).append(market)
            stats.markets_total += 1

        logger.info(
            "event=window_start window=%s markets=%d series=%d",
            window_dirname(hours),
            stats.markets_total,
            len(by_series),
        )

        for (category, series), markets in sorted(by_series.items()):
            out_path = out_root / category / f"{series}.jsonl"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            done = _load_done(out_path)

            pending = [m for m in markets if m["ticker"] not in done]
            stats.skipped_cached += len(markets) - len(pending)
            if not pending:
                continue

            with out_path.open("a", encoding="utf-8") as fh:
                for market in pending:
                    opened = _parse_ts(market.get("open_time"))
                    if opened is None:
                        # No window to ask about. Counted, and not written: a
                        # later re-ingest may supply the field, and a recorded
                        # null here would stop us ever asking.
                        stats.no_open_time += 1
                        continue

                    try:
                        trades, complete, pages = self.fetch_opening_window(
                            market["ticker"], opened, hours
                        )
                    except Exception as exc:  # noqa: BLE001 -- one bad market must not end the run
                        stats.errors += 1
                        logger.warning(
                            "event=open_fetch_failed ticker=%s error=%s", market["ticker"], exc
                        )
                        continue

                    stats.pages += pages
                    if not complete:
                        stats.incomplete += 1
                    elif not trades:
                        stats.no_trade += 1
                        stats.no_trade_per_category[category] = (
                            stats.no_trade_per_category.get(category, 0) + 1
                        )

                    fh.write(
                        json.dumps(
                            {
                                "ticker": market["ticker"],
                                "category": category,
                                "series": series,
                                "window_hours": hours,
                                "open_time": market["open_time"],
                                "close_time": market["close_time"],
                                "window_end_ts": (
                                    opened + timedelta(hours=hours)
                                ).isoformat(),
                                "fetched_at": datetime.now(timezone.utc).isoformat(),
                                # Null unless the walk proved it reached the
                                # open. clean.py reads this field and must never
                                # see a trade that merely happens to be the
                                # oldest one we managed to fetch.
                                "first_trade": trades[0] if (complete and trades) else None,
                                "trades": trades[:keep] if complete else [],
                                "trades_seen": len(trades),
                                "complete": complete,
                            }
                        )
                        + "\n"
                    )
                    stats.fetched += 1

                    if stats.fetched % 2000 == 0:
                        fh.flush()
                        os.fsync(fh.fileno())
                        logger.info("event=progress %s", stats.summary())

        logger.info("event=window_complete %s", stats.summary())
        return stats

    def fetch_all_windows(self, windows: list[float] | None = None) -> list[OpenStats]:
        """Run every configured window in order, primary first."""
        windows = windows or list(self.settings.window_hours)
        return [self.fetch_window(w) for w in windows]

    # -- the climbing ladder ------------------------------------------------

    def fetch_first_trade(self, ticker: str, open_at: datetime) -> FirstTrade:
        """The market's first trade, found by climbing the ladder.

        Starts at `ladder_start_hours` and moves in whichever direction the
        failure points:

            window was empty       -> widen, the market had not traded yet
            window was too busy    -> narrow, we could not walk back to the open

        It stops at the first window that both holds trades and was walked to
        the bottom. That window is nearly always quiet, because it is the window
        in which trading had only just started -- which is why this costs about
        one request where a single wide window costs tens.
        """
        ladder = list(self.settings.ladder_hours)
        start = ladder.index(self.settings.ladder_start_hours)
        pages = 0
        widest_tried = ladder[start]

        # Widen while the market simply has not traded yet.
        busy_at: int | None = None
        for i in range(start, len(ladder)):
            trades, complete, got = self.fetch_opening_window(ticker, open_at, ladder[i])
            pages += got
            widest_tried = ladder[i]
            if not complete:
                busy_at = i
                break
            if trades:
                return FirstTrade(
                    trades[0], trades, ladder[i], True, pages, len(trades)
                )

        if busy_at is None:
            # Ran off the top of the ladder: this market never traded inside the
            # widest window we are willing to call "the open".
            return FirstTrade(None, [], widest_tried, True, pages, 0)

        # Too busy to reach the open. Narrowing is the only move that helps --
        # a wider window holds strictly more trades to walk back through.
        for i in range(busy_at - 1, -1, -1):
            trades, complete, got = self.fetch_opening_window(ticker, open_at, ladder[i])
            pages += got
            if complete and trades:
                return FirstTrade(
                    trades[0], trades, ladder[i], True, pages, len(trades)
                )

        # Busy even at the narrowest rung. No price, and said so.
        return FirstTrade(None, [], ladder[0], False, pages, 0)

    def fetch_ladder(
        self,
        sample: int | None = None,
        seed: int = 0,
        shard: tuple[int, int] | None = None,
    ) -> OpenStats:
        """Find every binary market's first trade, climbing the ladder per market.

        One pass and one output directory. Because each record stores how long
        after the open its first trade landed, every window in the prereg's
        sweep becomes a comparison on that number rather than another fetch --
        so this replaces the four fixed-window passes rather than adding to them.

        Args:
            sample: Draw this many markets at random instead of taking all of
                them, so the run can be staged -- the primary test needs roughly
                27,000 markets, not 143,143. The draw is uniform over every
                market in the raw layer. It is deliberately *not* stratified by
                category and *not* filtered on anything a market did later:
                selecting on where a market ended up would leak the outcome into
                the sample. A sample larger than the universe is not an error.
            seed: Makes the draw reproducible. Record it with any result.
            shard: `(index, count)` to take only part of the work, for running
                several processes at once. The fetch is bound by network
                round-trips rather than by the rate limit -- one process idles
                near 9 requests a second against a ceiling around 20 -- so two
                workers roughly halve the wall clock. Shards are assigned by
                **series**, not by market, so each worker owns whole output
                files and two of them never append to the same JSONL. Series
                are dealt largest-first onto the lightest shard, because series
                sizes are very uneven (one Sports series can outweigh a whole
                category).
        """
        stats = OpenStats(window_hours=self.settings.ladder_start_hours)
        out_root = self.venue_dir / FIRST_TRADE_DIR
        keep = self.settings.keep_trades

        universe = list(iter_binary_markets(self.raw_dir))
        if sample is not None and sample < len(universe):
            universe = random.Random(seed).sample(universe, sample)

        by_series: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for market in universe:
            by_series.setdefault((market["category"], market["series"]), []).append(market)
            stats.markets_total += 1

        if shard is not None:
            by_series = _take_shard(by_series, *shard)
            stats.markets_total = sum(len(v) for v in by_series.values())

        logger.info(
            "event=ladder_start ladder=%s start=%s markets=%d series=%d sample=%s shard=%s",
            self.settings.ladder_hours,
            self.settings.ladder_start_hours,
            stats.markets_total,
            len(by_series),
            sample,
            shard,
        )

        for (category, series), markets in sorted(by_series.items()):
            out_path = out_root / category / f"{series}.jsonl"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            done = _load_done(out_path)

            pending = [m for m in markets if m["ticker"] not in done]
            stats.skipped_cached += len(markets) - len(pending)
            if not pending:
                continue

            with out_path.open("a", encoding="utf-8") as fh:
                for market in pending:
                    opened = _parse_ts(market.get("open_time"))
                    if opened is None:
                        stats.no_open_time += 1
                        continue

                    try:
                        found = self.fetch_first_trade(market["ticker"], opened)
                    except Exception as exc:  # noqa: BLE001 -- one bad market must not end the run
                        stats.errors += 1
                        logger.warning(
                            "event=open_fetch_failed ticker=%s error=%s", market["ticker"], exc
                        )
                        continue

                    stats.pages += found.pages
                    if not found.complete:
                        stats.incomplete += 1
                    elif found.trade is None:
                        stats.no_trade += 1
                        stats.no_trade_per_category[category] = (
                            stats.no_trade_per_category.get(category, 0) + 1
                        )

                    first_at = (
                        _parse_ts(found.trade.get("created_time")) if found.trade else None
                    )
                    fh.write(
                        json.dumps(
                            {
                                "ticker": market["ticker"],
                                "category": category,
                                "series": series,
                                "open_time": market["open_time"],
                                "close_time": market["close_time"],
                                "fetched_at": datetime.now(timezone.utc).isoformat(),
                                "first_trade": found.trade,
                                "trades": found.trades[:keep],
                                "trades_seen": found.seen,
                                "complete": found.complete,
                                # Which rung answered it, for the cost audit.
                                "window_hours_used": found.window_hours,
                                # The field that makes the prereg's window sweep
                                # free: every "did it trade within W" question
                                # is a comparison against this.
                                "seconds_after_open": (
                                    (first_at - opened).total_seconds()
                                    if first_at is not None
                                    else None
                                ),
                            }
                        )
                        + "\n"
                    )
                    stats.fetched += 1

                    if stats.fetched % 2000 == 0:
                        fh.flush()
                        os.fsync(fh.fileno())
                        logger.info("event=progress %s", stats.summary())

        logger.info("event=ladder_complete %s", stats.summary())
        return stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch the first trade after each settled market opened."
    )
    parser.add_argument(
        "--window",
        type=float,
        action="append",
        default=None,
        help=(
            "Run the FIXED-window pass at these hours after open, instead of the "
            "climbing ladder. Repeatable. Only needed for the prereg's secondary "
            "test (the last trade in a window); the ladder answers the primary one."
        ),
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        help="Fetch this many markets drawn at random, instead of all of them.",
    )
    parser.add_argument(
        "--seed", type=int, default=0, help="Seed for --sample. Record it with any result."
    )
    parser.add_argument(
        "--shard",
        default=None,
        metavar="I/N",
        help=(
            "Take only shard I of N, for running several workers at once. "
            "Shards own whole series, so workers never write the same file. "
            "Divide --rate between them to stay under the API ceiling."
        ),
    )
    parser.add_argument(
        "--rate",
        type=float,
        default=None,
        help=(
            "Override requests per second. With two workers use about 9 each: "
            "the unauthenticated ceiling is near 20/s for the whole account, "
            "not per process."
        ),
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )

    shard = None
    if args.shard:
        i, n = (int(x) for x in args.shard.split("/"))
        shard = (i, n)

    config = get_config()
    if args.rate is not None:
        config = config.model_copy(update={"rate_limit_per_second": args.rate})

    with KalshiOpenTradesClient(config) as client:
        if args.window:
            for stats in client.fetch_all_windows(args.window):
                print(stats.summary())
        else:
            print(
                client.fetch_ladder(
                    sample=args.sample, seed=args.seed, shard=shard
                ).summary()
            )


if __name__ == "__main__":
    main()
