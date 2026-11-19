# Data sources

Every endpoint this project reads, the gotchas each one carries, and what a
market record actually looks like. Verified against docs.kalshi.com and
exercised in `notebooks/00_api_scratch.ipynb`.

## Kalshi

**Base URL:** `https://external-api.kalshi.com/trade-api/v2` (config key
`kalshi_base_url`)

**Auth:** none. Every endpoint below is public read. Kalshi's authenticated
API-key scheme (RSA-PSS request signing) is required only for trading and for
portfolio endpoints, which the study never touches, so the study needs no
secret. The trading bot in `bot/` is the exception: it signs its account and
order calls with a key named in its own gitignored `bot/.env` (see
`bot/README.md`).

### The live / historical split -- the main gotcha

Kalshi serves settled markets from **two different API surfaces**:

- `/markets` -- the live surface. Recent activity, including recently settled
  markets.
- `/historical/markets` -- older data, migrated off the live surface.

The boundary between them is **a moving timestamp**, published by
`/historical/cutoff`. Data ages across it as Kalshi migrates.

**Why this matters.** Querying only `/markets` and assuming it holds
everything silently truncates the study to recent history -- and truncates it
by *settlement date*, which is not random with respect to anything being
measured. Half the sample would be missing with no error raised and no gap in
the data to notice.

**How this project handles it.** The ingestion client reads only the
historical surface, so the cutoff is the newest settlement it can see, and
`config.yaml`'s `date_range.end` is pinned to the cutoff observed during the
2026-08-05 exploration. Every run re-fetches the cutoff and writes it to
`data/raw/kalshi/_cutoff.json` before touching anything else -- that file is
the record of what "as much history as available" meant on the day of that
pull. The boundary does move: exploration on 2026-08-05 saw
`2026-06-06`; the production run on 2026-08-29 saw `2026-06-29`.

Reading only the historical surface means the ~3 most recent weeks of settled
markets are out of scope by construction. That is a deliberate trade: one
uniform surface with a recorded boundary beats stitching two surfaces with
different schemas together and having to argue the seam is clean.

### Endpoints used

| Endpoint | Purpose | Key params | Notes |
|---|---|---|---|
| `GET /historical/cutoff` | The live/historical boundary | -- | Fetched first on every run; saved to `_cutoff.json`. Returns several timestamps; `market_settled_ts` is the one that bounds this study. |
| `GET /series` | Enumerate a category's series | `category`, `include_volume=true` | `include_volume` is required for ranking -- without it `volume_fp` is absent. Not paginated; Economics returns all 772 series in one response. |
| `GET /historical/markets` | Settled markets in a series | `series_ticker`, `limit` (max 200), `cursor` | Cursor-paginated. Returns markets in **descending settlement order**, which is what lets a series walk stop once it passes the start of the window. |
| `GET /historical/trades` | A market's last trade before a moment (the second pass, `kalshi_calibration/ingest/trades.py`) | `ticker`, `max_ts`, `limit=1` | Newest first, so one row *is* the last trade at or before `max_ts`. One request per market per horizon. An empty list means no trade that early, recorded as an explicit null (ADR 003). |

### Pagination

Cursor-based: each response carries `cursor`, which is passed as a param to
get the next page. An empty or absent `cursor` means exhausted.

Two consequences the ingestion layer is built around: pages must be walked in
order (page N holds page N+1's cursor, so a cached page is still *read*), and
a series walk cannot be parallelised. See `docs/adr/002-ingestion-idempotency.md`.

### Rate limits

The unauthenticated "Basic" tier is a token bucket refilling at **200
tokens/sec**, with a default cost of **10 tokens per request** -- about 20
req/s. `config.yaml` sets `rate_limit_per_second: 15` for headroom. Breaches
return **429** with a `Retry-After` header, which `kalshi_calibration/ingest/base.py` honours
in preference to its own computed backoff.

### Series-level fields (`/series`)

| Field | Type | Notes |
|---|---|---|
| `ticker` | str | Series identifier, e.g. `KXFEDDECISION`. |
| `title` | str | Human label, e.g. "Fed meeting". |
| `volume_fp` | **str** | Total traded volume as a *decimal string* ("99935.00"). **Cast before comparing** -- sorting these lexicographically ranks "9917.00" above "10000000.00". |
| `frequency` | str enum | `custom`, `one_off`, `annual`, `monthly`, `weekly`, `daily`, `hourly`, `fifteen_min`. The **only** correct way to exclude sub-daily series -- matching the ticker string false-positives on Sports "1H" (First Half) markets. See `docs/journal.md`, 2026-08-05. |

### Market-level fields (`/historical/markets`)

The fields Phase 2 parsing depends on:

| Field | Type | Meaning |
|---|---|---|
| `ticker` | str | Unique contract id, e.g. `KXAAAGASD-26JUN28-3.920`. The dedup key. |
| `event_ticker` | str | Groups contracts resolving the same underlying event. |
| `title` / `yes_sub_title` | str | Question and the specific YES leg ("Above 3.920"). |
| `market_type` | str | `binary` for everything in scope. |
| `result` | str | Settlement: `yes`, `no`, or empty/`""` for voided. **This is the outcome.** |
| `status` | str | `finalized` for settled markets. |
| `settlement_ts` | str | RFC-3339 with a literal `Z`; `fromisoformat` needs the `Z` replaced with `+00:00`. |
| `open_time` / `close_time` / `expiration_time` | str | Same format. `close_time` bounds trading; `expiration_time` can be much later. |
| `last_price_dollars` | **str** | Last traded price, already in dollars (0-1), e.g. `"0.0100"`. |
| `previous_price_dollars` | str | Prior settlement-day reference price. |
| `yes_bid_dollars` / `yes_ask_dollars` | **str** | Best bid/ask on the YES leg. |
| `volume_fp` | **str** | Contracts traded over the market's life. |
| `open_interest_fp` | str | Open interest. |

**Every price and quantity is a decimal string, not a number.** Cast on read.

**A trap for the Phase 2 price decision:** on a settled market the book is
gone -- the record above shows `yes_bid_dollars: "0.0000"` and
`yes_ask_dollars: "1.0000"`, a maximally wide quote that is not a price at
all. A bid-ask mid computed from a settled snapshot returns 0.50 for every
contract regardless of what the market believed. `/historical/markets` gives
one post-settlement snapshot, not a time series, so `last_price_dollars` is
the only usable implied price available from this endpoint. That constraint,
not preference, drives ADR 003.

## Kalshi, for the 15-minute replication

`kalshi_calibration/replication/fetch.py` (`make replicate-data`) reads every settled
15-minute market in `config.yaml`'s `replication` window, with its last trade,
bid and ask at the end of each minute. All public, no auth.

| Endpoint | Purpose | Notes |
|---|---|---|
| `GET /historical/cutoff` | Which side of the live/historical split a market is on | Saved in `data/replication/series.json`. |
| `GET /series` | The 15-minute series | Kept when `frequency` is `fifteen_min` and the ticker doesn't end in `TEST`. The group (crypto, metals, energy, ...) comes from the ticker. Every series lists a `fee_multiplier` of 1, crypto included. |
| `GET /historical/markets` and `GET /markets` | Settled markets per series, from both sides of the cutoff | A market listed by both is read from the live side. |
| `GET /markets/candlesticks` | One-minute candles for live-side markets | One batch request per 15-minute window (`market_tickers`, `start_ts`, `end_ts`, `period_interval=1`). |
| `GET /historical/markets/{ticker}/candlesticks` | One-minute candles for historical-side markets | One request per market. Answers 429 above about 6 requests a second (measured 2026-10-06), so `replication.rate_limit_per_second` is 5 and a full rebuild takes about 1.5 hours. |

**The two sides name the candle fields differently.** Live candles carry
`close_dollars` (or `previous_dollars` for a minute with no trade); historical
ones carry `close` (or `previous`). A minute with no candle at all carries the
previous minute's quote forward.

The scripts in `research/kalshi_15min/` read the same endpoints through their
own small request helpers (most share `backtest_large.get`). `liquidity.py`
also reads the trade tape, `/markets/trades` and `/historical/trades`, around
each of the bot's entries.

## Polymarket (stretch, never ingested)

**Base URL:** `https://gamma-api.polymarket.com`. Public read, no auth. There
is no config key for it yet, and `kalshi_calibration/ingest/polymarket.py` is a one-line stub.
The plan was for it to subclass the same `APIClient` and write to
`data/raw/polymarket/` under the same layering rules, so adding it would not
change any layer downstream. Prices there are quoted 0-1 already. ADR 004
found no NO-framed contracts on Kalshi (every market states its proposition
affirmatively); Polymarket's framing would need the same check before the two
venues could be pooled.
