# Maker shadow test: spec (Oct 25, 2026)

## Why

The live bot is a **taker**: at minute 8 it buys the favourite at the ask (plus a 1c limit) and pays the taker fee.
Outside research says **makers** (traders whose resting orders wait to be filled) collect what takers lose. The Oct 11
lab test (`research/kalshi_15min/lab/maker.py`, REPORT.md 3d) said resting orders on favourites get picked off: filled
orders won 89-93% against 96% for the ask. But it only had minute-close quotes, so it could only see a fill when the
price itself fell to the order. It could not see sellers who hit a resting bid while the price stays put.

This test records Kalshi's real order book and trade tape for the bot's 16 markets, then replays them with a
pretend resting order at minute 8, to measure: how often it would fill, at what price, how fast, and what the price
did right after (the picked-off check).

**Nothing here trades.** No order, no cancel, no POST or DELETE anywhere. The live bot is not touched: separate
folder, separate process, no shared files except reading the bot's `.env` and key, no port, and no REST calls during
the bot's busy part of each window.

Two modules, each with its own test file:

- `maker_shadow.py`: the **recorder**. Runs on the server for weeks. Simple, robust, writes raw data.
- `maker_replay.py`: the **replay and report**. Offline, pure, run whenever. Can be re-run with new rules on the same
  raw data.

Both live in `research/maker_shadow/`. Tests in `research/maker_shadow/tests/`, run with
`python -m pytest research/maker_shadow/tests -q`. They must not use the network or the real key (an autouse
fixture makes any socket connection fail), and every test writes only inside its own `tmp_path`.

Kalshi's client: `from kalshi import Kalshi, load_key, sign`. Each module puts its own folder first on `sys.path`,
then `../../bot/kalshi_bot` (the repo's bot package), so on the server a copy of `kalshi.py` beside it is used, and in the repo
the bot's own is.

## Kalshi facts the code relies on

- A market's book on the WebSocket is two lists of **bids**: `yes` (bids for YES) and `no` (bids for NO). A YES ask at
  price p is a NO bid at 1 - p. So the best YES ask = 1 - best NO bid, and the best NO ask = 1 - best YES bid.
- `orderbook_snapshot` message: `{"type": "orderbook_snapshot", "sid": 7, "seq": 1, "msg": {"market_ticker": "T",
  "yes_dollars_fp": [["0.9200", "150.00"], ...], "no_dollars_fp": [["0.0500", "40.00"], ...]}}`. Either list may be
  missing (empty side). Prices and counts are strings.
- `orderbook_delta` message: `{"type": "orderbook_delta", "sid": 7, "seq": 2, "msg": {"market_ticker": "T",
  "price_dollars": "0.9300", "delta_fp": "-25.00", "side": "yes", "ts_ms": 1792972380123}}`. Add delta to that level;
  a level at 0 or below is gone.
- `trade` message: `{"type": "trade", "sid": 8, "seq": 5, "msg": {"trade_id": "...", "market_ticker": "T",
  "yes_price_dollars": "0.9300", "no_price_dollars": "0.0700", "count_fp": "12.00", "taker_side": "no",
  "ts_ms": 1792972381456}}`. `taker_side` is the side the taker **bought**. A taker who bought NO sold YES: the trade
  filled resting YES bids, printed at their YES price.
- `seq` counts up by 1 per subscription (`sid`). A jump means messages were lost.
- Other message types: `subscribed` (`msg.sid`), `unsubscribed`, `ok`, `error` (`msg.msg`). Anything else: keep, ignore.
- Prices can be sub-cent (fills at 0.984 have been seen). Counts can be fractional (0.03 contracts has been seen).
- Kalshi sends a Ping every 10 s; websocket-client's `recv()` answers it on its own.

## maker_shadow.py: the recorder

Constants (module level, tests may monkeypatch):

```
SERIES = ("KXBTC15M", "KXETH15M", "KXSOL15M", "KXXRP15M", "KXDOGE15M", "KXBNB15M", "KXHYPE15M", "KXNEAR15M",
          "KXZEC15M", "KXGOLD15M", "KXSILVER15M", "KXPLATINUM15M", "KXPALLADIUM15M", "KXCOPPER15M", "KXWTI15M",
          "KXNATGAS15M")
WS_URL = "wss://external-api-ws.kalshi.com/trade-api/ws/v2"
WS_PATH = "/trade-api/ws/v2"
WINDOW = 900
QUIET = (420, 600)     # seconds into a window with no REST calls at all: the bot preps at 450 s, enters at 480 s
LIST_AT = 15           # first try at listing a window's markets, seconds into it; retried every LIST_RETRY s until
LIST_RETRY = 30        #   every series has its market or the window is past QUIET[0]
RESULTS_AFTER = 120    # ask for a market's result once it closed this long ago ...
RESULTS_GIVE_UP = 6 * 3600   # ... and stop asking this long after it closed
REST_GAP = 0.5         # at least this many seconds between REST calls
REST_CONNECT = 0.5     # (added in review) a REST call's connect timeout, per address (the server is <1 ms from Kalshi)
REST_TIMEOUT = 3       #   and its read timeout. requests applies the connect timeout to each of the host's 8
REST_STOP = 60         #   addresses in turn and Kalshi.get tries 4 times, sleeping 1-4 s, so a call can last
                       #   4 x (8 x 0.5 + 3) + 10 = 38 s: no new REST call starts in the REST_STOP s before QUIET[0]
                       #   (rest_ok), and a listing round gives up at QUIET[0] - REST_STOP instead of QUIET[0]
REST_SLOW = 1          # (added in review) a REST call over this many seconds is logged: rest_slow
QUIET_SOCKET = 30      # a socket that has said nothing this long is dead: reconnect
RETRY = (1, 2, 5, 10, 30)    # seconds before each reconnect after a failure, then 30 s each time
AUTH_WAIT = 900        # (added in review) after a sign-in refused with 401 or 403, the wait before the next connect
STATUS_EVERY = 30
```

Pure helpers:

- `window_of(t)`: `t` rounded down to a multiple of WINDOW (UTC epoch seconds).
- `quiet(t)`: True when `QUIET[0] <= t - window_of(t) < QUIET[1]`.
- `hour_file(t)`: `"ws-YYYYMMDDTHH.txt.gz"` for the UTC hour containing `t`.
- `peek(text)`: `(type, sid, seq)` read from a raw message with regexes, without parsing the JSON (any of them None
  when absent). The recorder parses a message in full only when its type is `subscribed`, `unsubscribed`, `ok` or
  `error`: the feed is about 3,300 messages a second, so the common ones (`orderbook_delta`, `trade`) are only peeked.
- `read_env(path)`: dict of `KEY=VALUE` lines; blank lines and `#` comments skipped; surrounding quotes and spaces
  stripped from values. A missing file gives `{}`.
- `ws_headers(key_id, key, now_ms)`: the three handshake headers `KALSHI-ACCESS-KEY`, `KALSHI-ACCESS-TIMESTAMP`
  (str of now_ms), `KALSHI-ACCESS-SIGNATURE` = `sign(key, str(now_ms) + "GET" + WS_PATH)`.
- `window_markets(listing, series, window_open)`: from one `GET /markets` answer (`{"markets": [...]}`, or None),
  the markets whose `open_time` is within 1 s of window_open, as dicts with exactly: `ticker`, `series`, `open`,
  `close` (epoch floats from the ISO `open_time` / `close_time`, "Z" or "+00:00"), and `raw` (the market dict as
  Kalshi sent it, so tick size, fee fields and anything else are kept). Markets missing either time are skipped.
- `settled(market)`: `(result, status)` when a `GET /markets/{ticker}` answer's market has `result` in ("yes", "no"),
  else None.

`Recorder(out, client, connect, now=time.time, mono=time.monotonic, sleep=time.sleep, until=None)`:

- `out`: folder for every file it writes (created if missing). It never writes anywhere else.
- `client`: a `kalshi.Kalshi` (or a fake) used only for `markets(**params)` and `get(path)`. The recorder never
  calls anything else on it.
- `connect()`: returns an open socket-like object with `send(text)`, `recv()` (returns one text message, or raises
  `TimeoutError`-like `websocket.WebSocketTimeoutException` after ~1 s with nothing; the tests' fakes raise
  `TimeoutError`, and both must be treated as "nothing this second"), and `close()`. Any other exception from
  `connect`, `send` or `recv` means the socket is dead.
- `until`: epoch seconds; `run()` returns once `now() >= until`. None: forever.
- `now` is the wall clock: receive times, every `rt` written, the window, the hour, results timing and `until`.
  `mono` (added in review) is a monotonic clock for every timer: reconnect waits, flushes, status.json, space
  checks, REST_GAP, QUIET_SOCKET, RESUB_MIN, HEALTHY, STEP_MAX. A wall clock stepped back or forward can't freeze or
  rush them.

Behaviour of `run()` (a loop of `step()`; `step()` does one turn and is what most tests drive):

1. **Listing.** For the window containing now: from LIST_AT seconds in, and outside QUIET, list each series still
   without a market for this window: `client.markets(series_ticker=s, min_close_ts=int(window_open + WINDOW - 1),
   max_close_ts=int(window_open + WINDOW + 1), limit=50)`, at least REST_GAP s apart. Each market found is appended
   once to `markets.jsonl` with `"window_open"` added. Retry missing series every LIST_RETRY s until
   `QUIET[0] - REST_STOP`, then give up on them for this window. A failed listing (None) is logged to `events.jsonl`
   and retried. When it gives up, if it asked at all in that window, it logs `{"event": "not_listed",
   "window_open", "series": [every series still without a market], "rounds"}` once (nothing when none is missing).
2. **Subscribing.** When the window's market set changes (new markets found, or a new window), and the socket is up:
   unsubscribe every sid it holds (`{"id": n, "cmd": "unsubscribe", "params": {"sids": [...]}}`), then
   `{"id": n, "cmd": "subscribe", "params": {"channels": ["orderbook_delta", "trade"], "market_tickers": sorted}}`.
   Command ids count up from 1 per socket. Sids come from `subscribed` messages. Only the current window's markets
   are subscribed (the last window's markets closed at its end).
3. **Recording.** Every message received is written, exactly as Kalshi sent it, to the current hour file as one line:
   `f"{rt:.3f} {text}\n"` (rt: the receive time from now(); Kalshi's messages are single-line JSON). The hour file is
   a gzip stream written as it goes (`gzip.open(path, "wt", compresslevel=GZIP_LEVEL)`, GZIP_LEVEL = 3), flushed
   (`flush()`, a sync flush, so everything written so far can be read back) at least every FLUSH_EVERY = 5 s.
4. **Hour files.** When the UTC hour changes, the hour file is closed (a complete gzip) and the next one opened. A
   file is never appended to or overwritten: if the name is taken (a restart within the hour), it writes
   `ws-YYYYMMDDTHH.<n>.txt.gz` instead (n = 1, 2, ...). A crash leaves at most the last FLUSH_EVERY s unreadable.
   Closed files are what the laptop copies; the open one is listed in status.json as `"writing"`.
5. **Sequence gaps.** It tracks the last `seq` per `sid` (messages without a seq, like `subscribed`, aren't
   counted). If a message's seq isn't last + 1, it logs
   `{"event": "gap", "sid", "expected", "got"}` to events.jsonl and resubscribes the window's markets (unsubscribe all,
   subscribe again), which makes Kalshi send fresh snapshots. The first message of a sid sets its seq.
6. **Dead sockets.** On a connect/send/recv error, or QUIET_SOCKET s with no message at all while subscribed, it
   closes the socket (errors ignored), logs `{"event": "drop", "why"}`, and reconnects after RETRY waits (via
   `sleep`), then resubscribes. A connect failure logs `{"event": "connect_failed", "why"}`. A handshake refused with
   HTTP 401 or 403 (websocket-client's `WebSocketBadStatusException.status_code`, else a 401 or 403 in the message)
   logs `{"event": "auth_failed", "why"}` instead and waits AUTH_WAIT s before the next connect, not RETRY.
7. **Results.** Outside QUIET, for each market in markets.jsonl closed at least RESULTS_AFTER s ago and less than
   RESULTS_GIVE_UP ago, with no line yet in `results.jsonl`: `client.get(f"/markets/{ticker}")`, REST_GAP apart;
   when `settled()` gives a result, append `{"ticker", "result", "status", "rt"}` once. At most 40 result calls per
   step. After a restart it reads markets.jsonl and results.jsonl back, so it neither re-lists nor re-asks. Any REST
   call (listing or result) that took over REST_SLOW s logs `{"event": "rest_slow", "series" or "ticker", "seconds"}`.
8. **Status.** Every STATUS_EVERY s it rewrites `status.json` atomically (write a temp file in `out`, then
   `os.replace`): `{"rt", "connected": bool, "messages": count since start, "last_message_rt", "window_open",
   "markets": [tickers], "sids": [...], "drops": count, "gaps": count, "writing": the open hour file's name or None,
   "free_gb", "paused": bool}`.
9. **Events.** `events.jsonl` lines are `{"rt", "event", ...}`: `start`, `connect`, `drop`, `connect_failed`,
   `auth_failed`, `subscribe` (with the tickers), `gap`, `list_failed` (with the series), `not_listed`, `rest_slow`,
   `error` (an error message from Kalshi), `low_space`, `resume`.
10. **Low space.** Every SPACE_EVERY = 60 s it reads the free space of `out`'s disk (`shutil.disk_usage`, injectable
   as `free_bytes`). Below MIN_FREE_GB = 15 it closes the socket and the hour file, logs `low_space`, and records
   nothing until the free space is back above MIN_FREE_GB + 2, when it logs `resume`, reconnects and subscribes. The
   bot shares this disk; this is what keeps the recorder from ever filling it.

CLI: `python maker_shadow.py record --out DIR [--env-file PATH] [--until YYYY-MM-DD]`. The env file (default
`~/kalshi/bot/.env`) gives `KALSHI_API_KEY_ID` and `KALSHI_PRIVATE_KEY_PATH`; `connect` opens
`websocket.create_connection(WS_URL, header=ws_headers(...), timeout=10)` and sets a 1 s timeout. `--until` is
midnight UTC at the start of that date. The client is `Kalshi("prod", timeout=(REST_CONNECT, REST_TIMEOUT))` with no
key: REST calls are public GETs. Before the Recorder starts, it takes an exclusive lock on `<out>/recorder.lock`
(`fcntl.flock(LOCK_EX | LOCK_NB)` on Linux, `msvcrt.locking` on Windows; the OS lets go when the process ends, however
it ends) and writes its pid there. If another process holds it, it says so on stderr and exits 3, touching no other
file. The systemd unit also hides the bot's `state/` folder from it (`InaccessiblePaths`): it reads only the bot's
`.env` and key file.

## pull.py: the laptop's hourly copy

Runs on the laptop (Windows) every hour from Task Scheduler. It copies the recorder's closed hour files to the
laptop and deletes each from the server only once the laptop's copy is proven identical, so the server keeps only
what hasn't been copied yet.

`python research/maker_shadow/pull.py --host kalshi@recorder-host --key %USERPROFILE%\.ssh\recorder.pem
--remote /home/kalshi/maker-shadow/data --local research/maker_shadow/data`

- It runs Windows OpenSSH (`C:\Windows\System32\OpenSSH\ssh.exe` and `scp.exe`, overridable) with `-i <key> -o
  BatchMode=yes -o ConnectTimeout=15`, through one injectable `run(args, timeout) -> (returncode, stdout)`, so tests
  never start a process.
- **A run:**
  1. Take a lock (`<local>/pull.lock` holding the pid; a lock older than 6 h, or whose pid isn't running, is stale
     and taken over). Another live run: exit 0 at once.
  2. Read the remote `status.json` (`ssh host cat <remote>/status.json`) for `"writing"`, the open file.
  3. List the remote hour files with their sizes and change times, and the server's clock (`date +%s`; no contents
     read). Only names matching `^ws-\d{8}T\d{2}(\.\d+)?\.txt\.gz$` are considered; anything else is ignored. The
     `writing` file is skipped. So is any file named for the server's current UTC hour (or later), whatever
     status.json says: even closed, the recorder could still open another file of that hour, and a name freed by a
     delete could be used twice. So is any file changed in the last 45 s (this also covers the previous hour's file
     right after the hour turns). If status.json can't be read, the newest-named file is skipped too. Of the rest,
     the oldest MAX_HASH = 12 are taken; the others wait for the next run.
  4. One file at a time, oldest first: hash it on the server (one file per ssh call, at `nice -n 19 ionice -c3`).
     If the laptop already has it with the same SHA-256, delete it on the server. Otherwise `scp` it to
     `<local>/<name>.part`, check the local SHA-256 equals the remote one, rename it to `<name>`, then delete it on
     the server (`ssh host rm -- <remote>/<name>`). A failed hash or a mismatch deletes any `.part` file, keeps the
     server's, logs it, and moves on. An existing local file with a different SHA-256 is never overwritten: the copy
     goes to `<name>.dup<n>` and the server's is kept.
  5. The recorder only appends to `markets.jsonl`, `results.jsonl` and `events.jsonl`, so only their new bytes are
     copied. For each, one ssh call at `nice -n 19 ionice -c3` gives the server file's size S and the SHA-256 of its
     first L bytes, L being the laptop copy's length (`stat -c %s` and `head -c L | sha256sum`). If that equals the
     laptop copy's SHA-256, the bytes from L to S are fetched (`tail -c +L+1 | head -c S-L`, as base64 so they come
     through ssh exactly) into a `.part` file, its length is checked to be S - L, and they are appended. With no
     laptop copy yet, the whole file is copied (`scp`, through a `.part` file and a rename). If the hashes differ, or
     S < L, the server's file was reset or rewritten: the laptop's copy is never touched, the server's whole file is
     copied to the next free `<stem>.reset<n>.jsonl` (e.g. `markets.reset1.jsonl`) and a WARNING is logged; later
     runs append to the newest reset file by the same rule. `maker_replay.py` reads every `markets*.jsonl` and
     `results*.jsonl`. `status.json` is copied whole over the laptop's (through a `.part` file and a rename). None of
     the four is deleted on the server: the recorder reads them back on restart. No copy uses ssh compression.
  6. Nothing that reads a file on the server (each hash, each copy, each log check and its new bytes) starts during
     BUSY = 400-620 s into a 15-minute window: each such call waits it out first. The server's disk and CPU are the
     live bot's too.
- It never deletes anything on the laptop, never overwrites a laptop log, never deletes a server file it hasn't
  verified, and never runs `rm` on a name that didn't match the pattern.
- Each run appends to `<local>/pull.log`: start, files copied and deleted, bytes, errors. If ssh fails (the laptop is
  offline, or the server is), it logs that and exits 0; the next hour tries again.

## maker_replay.py: the replay and report

Pure and offline. Reads a data folder written by the recorder.

Constants: `LO, HI = 0.92, 0.999` (the bot's band), `MARK = 480`, `SIZE = 15` (contracts; the bot's median order
since the Ohio move), `CHECKS = (5, 30, 60)` (seconds after a first fill when the price is read again),
`TAKE_AFTER = 60` (the hybrid's wait), `TAKER_RATE = 0.07`.

- `read_lines(path)`: yields parsed JSON lines from a `.jsonl` or `.jsonl.gz` file. Bad lines are skipped. A
  truncated gzip (a crash) yields everything before the damage and stops without raising.
- `messages(folder)`: every `ws-*.txt.gz` in the folder, in time order (by the hour in the name, then the `.n`
  suffix, none first), yielding `(rt, msg)` from each `"<rt> <json>"` line. Bad lines are skipped; a truncated gzip
  yields what came before the damage.
- `Book`: one market's book.
  - `snapshot(msg_body)`: replaces both sides from `yes_dollars_fp` / `no_dollars_fp`; sets `ok = True`.
  - `delta(msg_body)`: adds `delta_fp` to `side` at `price_dollars`; a level at or under 1e-9 is removed.
  - `bid(side)`: best bid on "yes" or "no" (highest price), or None. `ask(side)`: `1 - bid(other side)`, or None.
  - `size(side, price)`: contracts bid on that side at that price (0 if none). Prices are compared rounded to 4 dp.
  - `mid(side)`: (bid + ask) / 2 for that side, or None if either is missing.
  - `ok`: False until the first snapshot, and after `invalidate()` until the next snapshot.
- `favourite(book)`: "yes" when the YES mid is 0.5 or more, else "no"; None when the YES mid is None.
- `taker_fee(contracts, price)`: `ceil(TAKER_RATE * contracts * price * (1 - price) * 10000 - 1e-9) / 10000`
  (Kalshi rounds an order's fee up to the next $0.0001; checked on the live ledger Oct 25).
- `Order`: a pretend resting buy of `side` at limit `L` for `size` contracts, posted at `t0` with `ahead` contracts
  queued before it at that price. `filled` (contracts so far), `fills` (list of `(rt, contracts)`), `done`.
  - `on_trade(body)`: taker bought `taker_side`; this order's side price is `yes_price_dollars` if side is "yes",
    else `no_price_dollars`. Only trades where the taker bought the **other** side can fill it. If that price is
    below L (by more than 1e-6), the whole count fills it (up to what's left): those takers reached prices below L,
    so they would have hit this order first. If it equals L (within 1e-6), the count first uses up `ahead`, and only
    the rest fills this order. Above L: nothing.
  - `on_delta(body, book)`: called after the book has applied the delta. On this order's side at L: `ahead` becomes
    `min(ahead, book.size(side, L))` (orders ahead that were cancelled are gone; new orders at L join behind it). On
    the other side, a positive delta at price q with `1 - q <= L + 1e-6` (someone put up a sell of this side at L or
    better, which would have traded with this order) fills it by the delta (up to what's left).
  - An order with nothing left is `done`; fills after that are ignored.
- `replay(folder, size=SIZE)`: replays every market in `markets.jsonl` and returns one row per market that had a
  usable book at its mark (`open + MARK`). Messages are applied in file order. A `gap` is not visible in the ws files
  directly, so the replay checks seq per sid itself: when a sid's seq jumps, every market whose book came from that
  sid is invalidated until its next snapshot (a market's sid is the sid of its last snapshot or delta). At the mark,
  using the book as it stood after the last message received before the mark:
  - skip the market (no row) if its book isn't `ok`, or it has no favourite, or the favourite has no bid or no ask;
  - row fields: `ticker`, `series`, `window_open`, `side` (the favourite), `bid`, `ask`, `spread` (ask - bid),
    `in_band` (`LO <= ask <= HI`), `result` (from results.jsonl, or None), `won` (result == side, or None), and
    `mid_6`, `mid_7` (the favourite side's mid at open + 360 s and + 420 s, None if unknown);
  - for in-band rows, three pretend orders, all `size` contracts, all held until the market's close:
    `join`: L = bid, ahead = book.size(side, bid);
    `tick`: L = bid + tick, ahead = 0, where tick is the market's tick size (from its `raw` fields
    `tick_size` (cents, int) or `price_level_structure`/`price_ranges` if present; default 0.01), only if L < ask;
    `cent`: L = bid + 0.01, ahead = 0, only if L < ask.
    Each order gives `orders[name] = {"L", "filled", "first_fill_rt", "fills", "mid_at_fill", "mid_after": {5: .., 30:
    .., 60: ..}, "mid_close"}`: the favourite side's mid at the first fill, at first fill + each CHECKS second (the book
    after the last message before that time; None if the market closed first), and at the last message before close.
    An order that can't be placed (tick or cent not under the ask) is None.
  - `taker`: buying `size` at the ask seen at the mark: `{"price": ask, "fee": taker_fee(size, ask)}` (it ignores
    depth; the bot's own fills can be compared from its ledger instead).
  - `hybrid` (join, then at mark + TAKE_AFTER buy what is still unfilled at the ask then, with the taker fee, if
    that ask is still in band): `{"maker_filled", "taker_filled", "taker_price", "fee"}`.
- `summarise(rows)`: per pretend order kind (join, tick, cent, hybrid) and for taker, over in-band rows with a known
  result: `markets`, `any_fill` (share with filled > 0), `full_fill` (share with filled >= size), `win_filled`,
  `win_unfilled` (win rates of markets where that order got some / no fill), `win_taker` (all in-band markets),
  `cents_per_dollar` (sum of profit / sum of cost, times 100, on what was filled; profit per contract is 1 - L if won
  else -L, minus fees where they apply; makers pay no fee), `mid_move` (mean of mid_after[k] - mid_at_fill for each
  k in CHECKS, over orders with both), `median_wait` (seconds from the mark to the first fill). Shares and rates are
  None when there's nothing to divide by.
- CLI: `python maker_replay.py report --data DIR [--out report.json]`: writes the rows and summary as JSON and
  prints a plain-words summary.
