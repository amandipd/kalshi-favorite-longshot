# Kalshi API features that affect order speed

Researched Oct 15, 2026 (18:20-18:45 UTC). Most facts come straight from Kalshi's docs, downloaded as Markdown (docs.kalshi.com/*.md, llms.txt, llms-full.txt, changelog). Two read-only checks were also run: Kalshi's public endpoint-cost list and a TLS/HTTP-version handshake. Both were unauthenticated and sent at 18:34 UTC, outside the bot's trading minutes.

- **[NEW]** marks a fact that is missing from, or contradicts, `research/kalshi_15min/lab/fast_entry/kalshi_api.md` (Oct 11, 2026).
- Facts without the tag confirm what that file already says. They are listed briefly so this file stands on its own.
- Every date is the date Kalshi gave for the change. Facts from before 2025 are flagged.

---

## 1. WebSocket API: channels, order entry, snapshot + delta mechanics

### Takeaway
Kalshi's WebSocket only carries data. You **cannot place or cancel orders over it**. Orders go over REST or FIX only. It has 13 channels and 4 commands. The order book arrives as one full snapshot, then deltas (small change messages), each with a `seq` counter. New since Oct 11: a 5-per-second stream of the CF Benchmarks crypto index on the same socket, optional compression, and new fields on the `user_orders` channel.

### Cited findings
- **No order commands [NEW].** The only client commands are `subscribe`, `unsubscribe`, `list_subscriptions` and `update_subscription`. None of them creates or cancels orders. "All communication happens through this single connection", and "authentication is required to establish the connection" even for public channels. Source: [WebSocket Connection](https://docs.kalshi.com/websockets/websocket-connection)
- **Channel list [NEW]** (from the `subscribe` command's list of allowed values):
  - Market data: `orderbook_delta`, `ticker`, `trade`, `market_lifecycle_v2`, `multivariate_market_lifecycle`.
  - Your own account: `fill`, `market_positions`, `order_group_updates`, `user_orders`.
  - Quotes and requests for quotes: `communications`.
  - Outside price feeds: `cfbenchmarks_value`, `cfbenchmarks_value_5hz`, `pyth_value`.
  - Source: [WebSocket Connection](https://docs.kalshi.com/websockets/websocket-connection)
- **Snapshot, then deltas.** The `orderbook_delta` channel "sends `orderbook_snapshot` first, then incremental `orderbook_delta` updates". It supports `update_subscription` with the actions `add_markets`, `delete_markets` and `get_snapshot`. "`get_snapshot` returns an `orderbook_snapshot` for the requested `market_tickers` without modifying the subscription." Source: [Orderbook Updates](https://docs.kalshi.com/websockets/orderbook-updates)
- **Sequence numbers.** `seq` is a "Sequential number that should be checked if you want to guarantee you received all the messages. Used for snapshot/delta consistency". `sid` identifies the subscription. The docs give no steps for recovering from a gap. Source: [Orderbook Updates](https://docs.kalshi.com/websockets/orderbook-updates)
- **`use_yes_price` flag [NEW].** This is an option on the order-book subscription.
  - When it is true, the NO side of `orderbook_delta` and `orderbook_snapshot` is quoted in YES prices, "so a single `price_dollars` scale applies to both sides". The default is false.
  - Kalshi says: "The default will be flipped to `true` in a future release, and the flag will then be removed entirely". It will announce the dates before each step.
  - Any code that builds the book from deltas will have to handle this change.
  - Source: [WebSocket Connection](https://docs.kalshi.com/websockets/websocket-connection)
- **Limits:**
  - **Connections per user:** "limited by usage tier. The default limit begins at 200" (Sep 18, 2025).
  - **Market subscriptions:** at most 500k per session (Jun 18, 2026).
  - **Commands:** at most 10k per second (Jun 18, 2026).
  - **Message size:** the limit is 64 MiB (Sep 24, 2026).
  - Source: [Changelog](https://docs.kalshi.com/changelog)
- **Error codes [NEW detail]:**
  - 18: Command timeout.
  - 25: Subscription buffer overflow. "The subscription's outbound buffer was exceeded". Since May 12, 2026, Kalshi's advice is to subscribe to fewer markets or read the socket faster.
  - 26: Subscription market limit exceeded.
  - 27: Too many requests. "The subscription exceeded its command rate limit".
  - Sources: [WebSocket Connection](https://docs.kalshi.com/websockets/websocket-connection), [Changelog](https://docs.kalshi.com/changelog)
- **Compression [NEW].** Sep 24, 2026: public WebSocket connections support RFC 7692 `permessage-deflate` compression, but only when the client offers it during the handshake. "Clients can choose to remain uncompressed by omitting `permessage-deflate`". Source: [Changelog](https://docs.kalshi.com/changelog)
- **Race-condition fix [NEW].** Sep 17, 2026: "Fixed a race that could skip events arriving immediately after a `subscribed` response". Source: [Changelog](https://docs.kalshi.com/changelog)
- **Send timestamp.** Oct 1, 2026: every WebSocket message carries `sending_ts_ms`, the moment Kalshi queued it for sending. Source: [Changelog](https://docs.kalshi.com/changelog)
- **The `user_orders` channel [NEW]** ("Real-time order created and updated notifications"):
  - Its fields include `fill_count_fp`, `remaining_count_fp`, `created_ts_ms`, `last_updated_ts_ms`, `last_update_reason`, `exchange_index`, `client_order_id` and `sending_ts_ms`.
  - `exchange_index` was added Aug 27, 2026.
  - `last_update_reason` was added Oct 1, 2026.
  - Sources: [User Orders](https://docs.kalshi.com/websockets/user-orders), [Changelog](https://docs.kalshi.com/changelog)
- **The 5 Hz CF Benchmarks channel [NEW].**
  - Sep 3, 2026: the new `cfbenchmarks_value_5hz` channel "streams CF Benchmarks index values at up to 5 updates per second". It covers indices "the vendor publishes at 200ms granularity (currently BRTI, ETHUSD_RTI, SOLUSD_RTI, XRPUSD_RTI, and DOGEUSD_RTI)".
  - Each message carries the raw vendor frame, the parsed value, and "When Kalshi received the upstream frame (unix ms)".
  - Other coins are published once per second on `cfbenchmarks_value`. That list includes BNB, HYPE, NEAR, SUI, BCH, LTC, LINK, SHIB, ADA, AAVE and others. That channel also carries trailing 60-second and "quarter-hour final-minute averages".
  - Sources: [CF Benchmarks 5Hz](https://docs.kalshi.com/websockets/cfbenchmarks-value-5hz), [CF Benchmarks Value](https://docs.kalshi.com/websockets/cfbenchmarks-value), [Changelog](https://docs.kalshi.com/changelog)
- **Prices of the outside feeds:**
  - **Pyth:** the `pyth_value` channel (metals, commodities, FX) costs **$1,000/month** after a 7-day free trial. Source: [Pyth Value Feed](https://docs.kalshi.com/websockets/pyth-value)
  - **CF Benchmarks over WebSocket:** the pages state no price.
  - **CF Benchmarks over REST:** the `GET /cfbenchmarks` passthrough costs 50 tokens a call. Source: [live endpoint_costs, Oct 15, 2026](https://external-api.kalshi.com/trade-api/v2/account/endpoint_costs)
- **Kalshi's own tips** for the WebSocket: "Subscribe only to markets you need", "Implement message buffering for high-frequency updates", "Cache initial orderbook state before applying updates". Source: [Quick Start: WebSockets](https://docs.kalshi.com/getting_started/quick_start_websockets)

### Inferences
- The WebSocket can only speed up the *read* step. With a live book already in memory at the target moment, the bot skips one REST round trip before it sends. The earlier measurement put that round trip at a median of about 96 ms from the bot's home PC. The WebSocket cannot shorten the order trip itself.
- To keep CPU work off the critical path, don't offer `permessage-deflate` (that is, connect uncompressed). The gain is small.
- The 5 Hz index channel delivers the CF Benchmarks index on the socket that already carries the books. That helps only if the bot's decision uses the spot index. Its delay compared with CF Benchmarks' own feed is unknown.
- Because `user_orders` and `fill` report fills over a channel the bot already holds open, the bot doesn't need a REST poll to confirm what happened. That doesn't speed up the orders themselves.

### Gaps
- Kalshi publishes no latency comparison between WebSocket and REST.
- The docs give no recovery procedure for a `seq` gap. It's also unclear whether `seq` counts per subscription or per market.
- No price is stated for the CF Benchmarks WebSocket channels.
- The dates for flipping the `use_yes_price` default are not yet announced.

---

## 2. FIX API: version, access, requirements, latency

### Takeaway
Kalshi offers FIX. FIX is the order protocol traditional exchanges use, run over one long-lived connection. Kalshi uses version **FIXT.1.1 / FIX50SP2**. The current docs say only "Members on the Premier tier or above have FIX access by default". They don't say how Basic or Advanced accounts get access. FIX has no batch order message, draws from the same rate-limit buckets as REST, and Kalshi claims no latency advantage for it.

### Cited findings
- **Version and access [NEW].** "Kalshi's FIX implementation uses **FIXT.1.1** with application version **FIX50SP2**. Members on the Premier tier or above have FIX access by default." Sources: [FIX Common Components](https://docs.kalshi.com/fix/common-components); same wording on the rendered [docs.kalshi.com/fix](https://docs.kalshi.com/fix)
- **Older wording (uncertain).** A search-engine summary of the FIX spec page says: "For all other tiers, contact institutional@kalshi.com to inquire about access." That sentence is not on the current page and appears only in the search summary. Source: [docs.kalshi.com/fix (search snippet)](https://docs.kalshi.com/fix)
- **Key permissions.** Oct 8, 2026: "FIX logon now accepts API keys with `read` and `write::trade`, not only parent `write`." Source: [Changelog](https://docs.kalshi.com/changelog)
- **Order-entry host `mm.fix.elections.kalshi.com`:**

  | Session | Port | Who can use it |
  |---|---|---|
  | KalshiNR (orders, no retransmission) | 8228 | No "contact us" note |
  | KalshiRT (orders, with retransmission) | 8230 | Contact institutional@kalshi.com |
  | Drop copy | 8229 | Gated |
  | Post-trade | 8231 | Contact institutional@kalshi.com |
  | RFQ (request for quote) | 8232 | Not stated |

  - **Market-data host:** `marketdata.fix.elections.kalshi.com`, port 8233 (`KalshiMD`).
  - **Demo hosts:** `fix.demo.kalshi.co` and `marketdata.fix.demo.kalshi.co`.
  - Source: [FIX Connectivity](https://docs.kalshi.com/fix/connectivity)
- **TLS [NEW].** You need TLS 1.2 or higher (encryption on the connection). "Cipher suites follow AWS Network Load Balancer TLS policies", which suggests the FIX gateway sits behind an AWS Network Load Balancer. There is "Only one FIX connection ... per API key." Source: [FIX Connectivity](https://docs.kalshi.com/fix/connectivity)
- **Signing happens once, at logon [NEW].**
  - The Logon message carries a signature in `RawData` (tag 96), Ed25519 or RSA-PSS, over `SendingTime, MsgType, MsgSeqNum, SenderCompID, TargetCompID`.
  - "SendingTime must be within 30 seconds of the server's current time".
  - The docs describe no per-order signature after logon.
  - Source: [FIX Authentication](https://docs.kalshi.com/fix/authentication)
- **Session rules:**
  - Heartbeats (keep-alive messages) default to every 30 s, and the interval must be more than 3 s.
  - KalshiNR must log on with `ResetSeqNumFlag=Y`.
  - Useful logon flags: `CancelOrdersOnDisconnect` (8013), `SkipPendingExecReports` (21011), `EnableIocCancelReport` (21007) and `AlwaysEmitNewBeforeTrade` (21026, added Apr 28, 2026 in v1.0.22).
  - Source: [FIX Authentication](https://docs.kalshi.com/fix/authentication), [Changelog](https://docs.kalshi.com/changelog)
- **Order fields:**
  - `TimeInForce` (59): `0`=Day, `1`=GTC (good till cancelled), `3`=IOC (immediate or cancel), `4`=FOK (fill or kill), `6`=GTD (good till date). "Past GTD dates are treated as IOC."
  - `ExecInst` (18): `6`=Post Only, `E`=Reduce Only (IOC only).
  - `ExDestination` (100) picks the shard. It has been supported since Jun 25, 2026.
  - Source: [FIX Order Entry](https://docs.kalshi.com/fix/order-entry), [Changelog](https://docs.kalshi.com/changelog)
- **No batch message [NEW].** The order-entry page documents New Order Single (35=D), Cancel (35=F), Cancel/Replace (35=G) and Mass Cancel (35=q). It has no New Order List (35=E). "Mass Cancel Request (35=q) is limited to 1 request/second." Sources: [FIX Order Entry](https://docs.kalshi.com/fix/order-entry), [FIX Connectivity](https://docs.kalshi.com/fix/connectivity)
- **Same rate limits as REST.** "FIX application messages use the same token model, token costs, and Read/Write buckets as the equivalent REST API operations." Logon is rate-limited separately. Source: [FIX Connectivity](https://docs.kalshi.com/fix/connectivity)
- **FIX market data [NEW]:**
  - May 28, 2026 (v1.0.28): the `KalshiMD` session sends book snapshots (35=W) and incremental updates (35=X).
  - A request can name up to 1,000 symbols. A session can hold 100,000 subscriptions (raised Sep 3, 2026).
  - Since Sep 3, 2026, incremental updates carry your `ClOrdID` (your order ID) when your own order changed the level.
  - May 29, 2026: added market status messages.
  - Sources: [FIX Market Data](https://docs.kalshi.com/fix/market-data), [Changelog](https://docs.kalshi.com/changelog)
- **Listener sessions.** A listener session is a read-only live copy of your execution reports, on a separate key. It was added Jun 26, 2025 (v1.0.12). Source: [Listener Sessions](https://docs.kalshi.com/fix/listener-sessions)
- **Replay needs approval.** Since Sep 17, 2026, historical replay (`35=U1`) on KalshiNR and KalshiDC needs Kalshi to allowlist the account. "NR users can log in and trade without replay access." Sources: [FIX Connectivity](https://docs.kalshi.com/fix/connectivity), [Changelog](https://docs.kalshi.com/changelog)
- **No latency claim.** Neither the FIX pages nor any other docs page states a FIX latency figure. A search of the full docs found only one latency statement, about auto-routing (§5). Source: [llms-full.txt](https://docs.kalshi.com/llms-full.txt)

### Inferences
- FIX's main edges are mechanical:
  - One persistent TLS connection.
  - No HTTP headers or JSON on each order.
  - No signature on each order, because only the logon is signed.
  - Twenty New Order Single messages can go back to back on one socket.
- Those savings are likely a few milliseconds of CPU. The 70-90 ms network path from the test machine's home connection to us-east-2 is far larger. Kalshi publishes no FIX-vs-REST figure.
- For a Basic or Advanced retail account, FIX is **not clearly available on your own**. The docs promise it only to Premier and above. The way to find out is a logon attempt on the demo gateway (`fix.demo.kalshi.co:8228`), or emailing institutional@kalshi.com.

### Gaps
- It's unclear whether a production Basic or Advanced key can log on to KalshiNR. The docs neither say so nor forbid it.
- No measured FIX-vs-REST order latency was found, from Kalshi or anyone else.
- It's unclear whether the FIX gateway shares a region or path with the REST load balancer.

---

## 3. Batch orders: endpoint, size, tier, rate-limit cost, per-order results

### Takeaway
The endpoint is `POST /portfolio/events/orders/batched` (V2).
- **Size:** there is no fixed maximum. It "scales with your tier's write budget", so 10 orders on Basic and 90 on Advanced.
- **Cost:** each order costs the usual 10 tokens, and the whole batch must fit in the bucket at once.
- **Bucket [NEW]:** a batch always bills the **unscoped** Write bucket (the account-wide one, not a shard's), even when each order sets `exchange_index`.
- **Results:** each order gets its own result with fills, `ts_ms` and any error.
- **Access:** open to every tier since Nov 20, 2025.

### Cited findings
- **Endpoint.** "Endpoint for submitting a batch of event-market orders using the V2 request/response shape. The maximum batch size scales with your tier's write budget". The request body is `{"orders": [CreateOrderV2Request, ...]}`. The OpenAPI spec version was 3.34.0 on Oct 15, 2026. Source: [Batch Create Orders (V2)](https://docs.kalshi.com/api-reference/orders/batch-create-orders-v2)
- **Cost.** "10 tokens per order in the batch", "billed per item." Also: "A batch request costs the same as making each call individually ... The whole batch must fit in the bucket at once. A 25-order create batch needs 250 tokens available when it arrives, or the entire batch is rejected." Sources: [Batch Create Orders (V2)](https://docs.kalshi.com/api-reference/orders/batch-create-orders-v2), [Rate Limits](https://docs.kalshi.com/getting_started/rate_limits)
- **Which bucket [NEW].** "**Batch REST** creates and cancels always bill their total per-order cost to your unscoped Write bucket, regardless of `exchange_index`." Sources: [Rate Limits](https://docs.kalshi.com/getting_started/rate_limits); repeated in [Exchange Sharding FAQ](https://docs.kalshi.com/getting_started/exchange_sharding)
- **Per-order results.** Each result has `order_id`, `client_order_id`, `fill_count`, `remaining_count`, `average_fill_price` and `average_fee_paid` (only when something filled), `ts_ms` and `error`. `ts_ms` is the "Matching engine timestamp at which the order was processed ... Absent when the request errored." Source: [Batch Create Orders (V2)](https://docs.kalshi.com/api-reference/orders/batch-create-orders-v2)
- **Item fields.** Each order takes the same fields as a single create:
  - Required: `ticker`, `side` (bid/ask), `count`, `price`, `time_in_force` (`fill_or_kill` | `good_till_canceled` | `immediate_or_cancel`) and `self_trade_prevention_type` (`taker_at_cross` | `maker`).
  - Optional: `client_order_id`, `post_only`, `reduce_only`, `cancel_order_on_pause`, `order_group_id`, `subaccount` and `exchange_index`.
  - Source: [Batch Create Orders (V2)](https://docs.kalshi.com/api-reference/orders/batch-create-orders-v2)
- **Batch cancel [NEW].** `DELETE /portfolio/events/orders/batched` costs **2 tokens per order**. Sources: [live endpoint_costs, Oct 15, 2026](https://external-api.kalshi.com/trade-api/v2/account/endpoint_costs), [Rate Limits](https://docs.kalshi.com/getting_started/rate_limits)
- **Who may use it, over time:**

  | Date | Change |
  |---|---|
  | Aug 13, 2025 | Batch endpoints opened to every tier in demo only. Production still needed Advanced. |
  | Oct 24, 2025 | Batch create returns `"post only cross"` details, the same as single orders. |
  | Nov 14, 2025 | Kalshi announced batch create would become generally available (release Nov 20, 2025). "Advanced API access is no longer a prerequisite." |
  | Dec 1, 2025 | Batch cancel also opened to every tier (release Dec 4, 2025). |
  | Apr 22, 2026 | V2 batch endpoints released. |
  | May 25, 2026 | Legacy batch cost raised from 10 to 15. |
  | Jun 1, 2026 | Raised to 50. |
  | Jun 4, 2026 | Raised to 100 (10× the V2 cost). |
  | Jun 18-25, 2026 | Legacy endpoints deprecated. |
  | Jul 30, 2026 | API keys restricted to one subaccount may batch. |

  Source: [Changelog](https://docs.kalshi.com/changelog)
- **Old size cap (pre-2025, uncertain).** The old readme.io docs capped legacy batches at 20 orders. That figure comes only from an earlier search snippet, quoted in the existing note. Source: [old readme.io page](https://trading-api.readme.io/reference/batchcreateorders-1)

### Inferences
- **Batch size by tier.** A Basic Write bucket holds 100 tokens, so one batch carries at most **10 orders**. On Advanced, the bucket holds 900 tokens, so a batch can carry 90.
- **[NEW, untested] About 20 orders at once on Basic.** The docs bill two kinds of orders to two different buckets:
  - Single orders with `exchange_index: 2` go to the shard-2 Write bucket, and "each shard's bucket carries your full tier budget".
  - Batches go to the unscoped bucket.

  The bot's single orders already set `exchange_index`, so its unscoped Write bucket appears to sit idle. In principle, a Basic account could fire **10 single orders with `exchange_index: 2` and one batch of 10** at the same moment, about 20 orders, with no 0.1 s pacing. This follows from Kalshi's stated billing rules. It has not been tested, so test it in demo first. Upgrading to Advanced (§4) makes it unnecessary.
- **One request for many orders.** A batch needs one HTTP request, one signature and one network trip, however many orders it holds. That removes the gap between the singles.
- **Unknowns about batch order.** The order in which a batch's items reach the matching engine is undocumented. The per-order `ts_ms` values would show it after the fact.

### Gaps
- The exact largest batch per tier isn't documented. It is only tied to "write budget".
- Whether items run in array order, all at once, or one by one isn't documented.
- Whether one batch may mix orders for different shards isn't documented.
- How fast a batch is processed compared with the same orders sent singly isn't documented.

---

## 4. Rate-limit tiers: names, exact limits, how to qualify

### Takeaway
There are seven public tiers: Basic, Advanced, Expert, Premier, Paragon, Prime and Prestige. The docs also mention an unlisted "Market Maker" usage level. **Basic → Advanced is self-serve and permanent: one API call.** That raises the burst from 10 orders to 90. Expert and above come only from trading-volume share or a Kalshi grant.

### Cited findings
- **Budgets (tokens per second, Oct 15, 2026):**

  | Tier | Read | Write |
  |---|---|---|
  | Basic | 200 | 100 |
  | Advanced | 300 | 300 |
  | Expert | 600 | 600 |
  | Premier | 1,200 | 1,200 |
  | Paragon | 2,400 | 2,400 |
  | Prime | 4,800 | 4,800 |
  | Prestige | 12,000 | 9,600 |

  Most requests, including a single order create, cost 10 tokens. Source: [Rate Limits and Tiers](https://docs.kalshi.com/getting_started/rate_limits)
- **Recent rise.** Sep 24, 2026: "Predictions read and write rate limits are increasing 20% for Premier, Paragon, Prime, and Prestige." Source: [Changelog](https://docs.kalshi.com/changelog)
- **Bucket sizes (how much you can spend at once) [NEW detail].**
  - "Basic and Advanced Predictions Read buckets, and Write buckets above the Basic tier, hold up to **three seconds of budget**."
  - "Predictions Read buckets above Advanced, Perps Read buckets, and Basic-tier Write buckets hold one second of budget."
  - So a Basic **Read** bucket holds 600 tokens (60 reads in one burst), and a Basic **Write** bucket holds 100 tokens (10 orders).
  - Source: [Rate Limits and Tiers](https://docs.kalshi.com/getting_started/rate_limits)
- **Conflicting statements:**
  - The `GET /account/limits` reference says write buckets at non-Basic tiers hold "two seconds". Source: [Get Account API Limits](https://docs.kalshi.com/api-reference/account/get-account-api-limits)
  - The Apr 30, 2026 changelog example shows `"usage_tier": "advanced"` with write `refill_rate` 100 and `bucket_capacity` 200. That doesn't match the current table. Source: [Changelog](https://docs.kalshi.com/changelog)
- **Tier names.** "Public Predictions tiers include Basic, Advanced, Expert, Premier, Paragon, Prime, and Prestige." Source: [Get Account API Limits](https://docs.kalshi.com/api-reference/account/get-account-api-limits)
- **Unlisted Market Maker level [NEW].** The Create API Key endpoint "allows users with Premier or Market Maker API usage levels to create API keys by providing their own ... public key". Source: [Create API Key](https://docs.kalshi.com/api-reference/api-keys/create-api-key)
- **How to qualify:**
  - **Basic:** "complete account signup".
  - **Advanced:** call the upgrade endpoint.
  - **Expert and above:** "earned automatically from your trading volume ... or assigned by Kalshi."
  - Source: [Rate Limits and Tiers](https://docs.kalshi.com/getting_started/rate_limits)
- **The upgrade call.** `POST /account/api_usage_level/upgrade` "Grants a permanent Advanced API usage-level grant ... Criteria: at least 1 of the user's last 100 Predictions orders was created via API." It costs 30 tokens. Self-promotion was added Jun 11, 2026. Sources: [Upgrade Account API Usage Level](https://docs.kalshi.com/api-reference/account/upgrade-account-api-usage-level), [Changelog](https://docs.kalshi.com/changelog)
- **Volume tiers.**
  - Formula: "volume share = your trailing 30-day volume ÷ (previous month's exchange volume × 2)". Your 30-day volume counts both maker and taker sides.
  - Earn / Keep thresholds:

    | Tier | Earn | Keep |
    |---|---|---|
    | Expert | 0.075% | 0.05% |
    | Premier | 0.125% | 0.10% |
    | Paragon | 0.25% | 0.20% |
    | Prime | 0.50% | 0.40% |
    | Prestige | 1.00% | 0.80% |

  - Kalshi reviews volume daily. Each grant lasts 30 days.
  - Source: [Rate Limits and Tiers](https://docs.kalshi.com/getting_started/rate_limits)
- **Thresholds halved [NEW].** Jun 25, 2026: "Qualification requirements for all tiers has been halved." Source: [Changelog](https://docs.kalshi.com/changelog)
- **Progress endpoint [NEW].** `GET /account/api_usage_level/volume_progress` (Jun 11, 2026) reports your trailing 30-day volume and the earn and keep goals for each volume tier. Sources: [Volume Progress](https://docs.kalshi.com/api-reference/account/get-account-api-usage-level-volume-progress), [Changelog](https://docs.kalshi.com/changelog)
- **Live endpoint costs [NEW; contradicts the existing note].** On Oct 15, 2026, `GET /account/endpoint_costs` returned:
  - `default_cost` 10.
  - **Single V2 cancel `DELETE /portfolio/events/orders/:order_id` = 2.** The existing note said 10.
  - Cancel-all `DELETE /portfolio/events/orders` = 2. Batch cancel = 2 per order.
  - `GET /portfolio/orders/:order_id` = 2.
  - Upgrade = 30. `GET /cfbenchmarks` = 50.
  - Order create and order-book GETs aren't listed, so they cost the default 10.
  - Source: [endpoint_costs](https://external-api.kalshi.com/trade-api/v2/account/endpoint_costs) (public, fetched 18:34 UTC)
- **Cancel-all.** Sep 3, 2026: "Cancel-all requests now consume the same number of write tokens as cancelling one order". Source: [Changelog](https://docs.kalshi.com/changelog)
- **When you hit the limit:**
  - You get a 429 with `{"error": "too many requests"}`, with no `Retry-After` header. "There is no penalty or cooldown."
  - Writes may burst above the per-second budget since Apr 23, 2026.
  - The token system and the Paragon tier date from Apr 23, 2026.
  - Sources: [Rate Limits and Tiers](https://docs.kalshi.com/getting_started/rate_limits), [Changelog](https://docs.kalshi.com/changelog)

### Inferences
- **Advanced fixes the burst limit.** On Advanced, the bot could send 20 orders in one batch or 20 parallel singles: 200 tokens against a 900-token bucket. The 8-then-0.1-s pacing would no longer be needed. This is the cheapest documented speed lever.
- **Expert is very likely out of reach** for a small retail account. It needs 0.075% of twice the previous month's total exchange volume, even after the Jun 2026 halving.
- **Read the real numbers from the API.** The docs disagree on bucket size, so read `bucket_capacity` from `GET /account/limits` rather than trusting either page.
- **The table likely includes the Sep 24 rise.** The Premier-and-up figures are all exactly 1.2× round numbers (1,000 → 1,200 … 10,000 → 12,000 and 8,000 → 9,600).

### Gaps
- What the "Market Maker" usage level grants, and how to get it, isn't documented.
- Whether limits apply per API key, per account or per IP is still undocumented.
- Kalshi's monthly exchange volume, needed to turn the share thresholds into contract counts, wasn't looked up.

---

## 5. exchange_index / sharding / account sections: routing and speed

### Takeaway
Kalshi runs several matching engines, called shards. Crypto and commodities trade on **shard 2**. Sending `exchange_index` explicitly skips auto-routing, and Kalshi says auto-routing "will incur an additional latency cost". That is the **only latency statement anywhere in Kalshi's docs**. Each shard also has its own Write bucket and its own cash balance.

### Cited findings
- **What shards are.** "Kalshi splits trading across multiple matching engines to scale capacity. Exchange instances correspond to specific categories". Source: [Exchange Sharding](https://docs.kalshi.com/getting_started/exchange_sharding)
- **Shard map:**
  - Shard 0: everything not listed below.
  - Shard 1: Exotics (combos).
  - Shard 2: Crypto, and Commodities (commodities since 12:00 PM ET, Sep 10, 2026).
  - Shard 3: Sports (Tennis, Baseball, Basketball).
  - Aug 24, 2026: "Crypto, Tennis, and Baseball will be provisioned on dedicated exchange instances."
  - Sources: [Exchange Sharding](https://docs.kalshi.com/getting_started/exchange_sharding), [Changelog](https://docs.kalshi.com/changelog)
- **Routing rules.** "If `exchange_index >= 0`, routes directly to the target exchange. If `exchange_index` is `-1`, auto-routes using the required `market_ticker`. If `exchange_index` is omitted and `market_ticker` is provided, auto-routes". Auto-routing became the default on Aug 27, 2026. Sources: [Exchange Sharding](https://docs.kalshi.com/getting_started/exchange_sharding), [Changelog](https://docs.kalshi.com/changelog)
- **The latency statement.** "Automatic routing will incur an additional latency cost." This is the only latency claim in llms-full.txt, apart from an unrelated weather item. Source: [Exchange Sharding FAQ](https://docs.kalshi.com/getting_started/exchange_sharding)
- **Billing.**
  - "Auto-routed single REST order writes are billed to the unscoped Write bucket and every nonzero shard's Write bucket."
  - Single REST writes with `exchange_index >= 1` bill that shard's bucket only.
  - Batches bill only the unscoped bucket.
  - Source: [Exchange Sharding FAQ](https://docs.kalshi.com/getting_started/exchange_sharding), [Rate Limits](https://docs.kalshi.com/getting_started/rate_limits)
- **Cash per shard.**
  - "Kalshi's collateralization checks run within the matching engine. Programmatic traders normally need to fund the relevant exchange shard before placing an order."
  - Only App and Web orders move cash between shards automatically.
  - You can opt in to auto-rebalancing, which runs "Every 10 seconds" against a target split. The `/portfolio/target_balance_allocation` endpoints were added Aug 20, 2026.
  - Source: [Exchange Sharding](https://docs.kalshi.com/getting_started/exchange_sharding), [Changelog](https://docs.kalshi.com/changelog)
- **Other shard facts:**
  - "Order groups do not function across exchange instances."
  - "There is currently no plan to migrate any live market to a new exchange instance."
  - Source: [Exchange Sharding FAQ](https://docs.kalshi.com/getting_started/exchange_sharding)
- **Status per shard [NEW].** `GET /exchange/status` returns `exchange_index_statuses`, one entry per shard with `trading_active` (Jul 2, 2026), and each entry has a `description` (Aug 13, 2026). `GET /series` exposes `exchange_index` (Jul 30, 2026). Source: [Changelog](https://docs.kalshi.com/changelog)

### Inferences
- The bot already does the documented fastest thing: `exchange_index: 2` on every order. Kalshi offers no further routing lever.
- The shard-2 balance must cover the orders. An unfunded shard means rejections, not delay.

### Gaps
- How big the auto-routing delay is (milliseconds) is undocumented.
- Whether shards run in different data centres or availability zones is undocumented.

---

## 6. Signing: Ed25519 vs RSA-PSS

### Takeaway
Since **Sep 24, 2026**, Kalshi accepts **Ed25519** keys on REST, WebSocket and FIX. Ed25519 is a fast type of digital signature. Kalshi now recommends it because of its "lower signing cost than RSA-PSS". The signature covers only the timestamp, method and path, not the order body.

### Cited findings
- **The two key types [NEW].**
  - Ed25519 is "(recommended) ... Lower signing cost than RSA-PSS; 64-byte signatures".
  - RSA is 2048-bit, signed with "RSA-PSS with SHA-256", for "Clients limited to RSA-PSS, including SDK versions before 3.31.0".
  - "Kalshi selects the verification algorithm from the registered public key".
  - Source: [API Keys](https://docs.kalshi.com/getting_started/api_keys)
- **What gets signed.** "The signature is the base64 encoding of the signed concatenation of the timestamp, the HTTP method and the path." The path is signed without its query string. The request body is not part of the signed text. Sources: [API Keys](https://docs.kalshi.com/getting_started/api_keys), [API Environments](https://docs.kalshi.com/getting_started/api_environments)
- **Dates [NEW]:**
  - Sep 24, 2026: Ed25519 is supported "on REST, WebSocket and FIX (`RawData`)".
  - Oct 1, 2026: the web app's "Create New API Key" dialog generates Ed25519 by default.
  - `POST /api_keys/generate` "still defaults to `rsa` when `key_type` is omitted".
  - Python and TypeScript SDKs support Ed25519 from 3.31.0.
  - Sources: [Changelog](https://docs.kalshi.com/changelog), [SDKs](https://docs.kalshi.com/sdks/overview)
- **Getting a key.** In the web profile, anyone can paste a public key or have Kalshi generate one. The `POST /api_keys` API route that registers your own public key is described as for "Premier or Market Maker API usage levels". Sources: [API Keys](https://docs.kalshi.com/getting_started/api_keys), [Create API Key](https://docs.kalshi.com/api-reference/api-keys/create-api-key)
- **Kalshi's SDK advice.** "SDKs are updated periodically and may lag the API. Active traders should treat the REST OpenAPI specification ... as the source of truth ... we recommend generating your own client". Source: [Kalshi SDKs](https://docs.kalshi.com/sdks/overview)

### Inferences
- An Ed25519 key cuts the CPU time spent signing each order. Kalshi gives no figure.
- Because the body isn't signed, the bot can compute headers before the target moment, since they depend only on timestamp + `POST` + path.
  - That takes signing off the critical path whatever the key type.
  - The catch: Kalshi doesn't document how stale a REST timestamp may be, or whether it rejects reused signatures (replay protection). Test in demo before relying on it.

### Gaps
- Kalshi gives no signing-time figures (ms per signature) for either key type. Measure them locally (the companion note on the Python client has local figures).
- How far the REST timestamp may drift is undocumented. For FIX logon it is 30 s.

---

## 7. Hosting, data centre, matching-engine latency, colocation, faster-access programs

### Takeaway
Kalshi documents **no region, data centre, matching-engine latency figure or colocation**. Colocation means renting space right next to the exchange's servers. The closest products are AWS **PrivateLink** (Premier and up) and **VPC peering** (Prime and up). Both only help traffic that already starts inside AWS. The Market Maker Program offers fees and position limits, not speed. A low-latency multicast data feed exists for institutions, but it covers sports and crypto perpetual futures, and it is data only.

### Cited findings
- **Recommended hosts.** May 7, 2026: Kalshi added "dedicated external Trade API hosts" `external-api.kalshi.com` and `external-api-ws.kalshi.com`, "recommended hosts for API traders". The shared hosts stay "supported for compatibility". Sources: [API Environments](https://docs.kalshi.com/getting_started/api_environments), [Changelog](https://docs.kalshi.com/changelog)
- **Private connectivity.**
  - "Members on the Premier tier or above can contact institutional@kalshi.com to provision PrivateLink endpoints". With PrivateLink, "traffic is routed entirely within the AWS backbone".
  - Aug 20, 2026: "Members on the Prime tier or above can contact institutional@kalshi.com to discuss VPC peering for production WebSocket and FIX connectivity".
  - Sources: [API Environments](https://docs.kalshi.com/getting_started/api_environments), [FIX Connectivity](https://docs.kalshi.com/fix/connectivity), [Changelog](https://docs.kalshi.com/changelog)
- **Region (third party, not Kalshi).** Glassnode's latency monitor says Kalshi's "origin servers are in AWS us-east-2 (Ohio)" behind CloudFront. It publishes no Kalshi latency numbers and no page date. Source: [Glassnode Latency Monitor](https://latency.glassnode.com/prediction-markets/about)
- **Chicago claim (low reliability).** A VPS vendor claims a 1.14 ms round trip from Chicago in Feb 2026. That most likely measured a CloudFront edge (see the existing note). Source: [QuantVPS](https://www.quantvps.com/blog/kalshi-servers-location)
- **Market Maker Program [NEW].**
  - Help article dated Apr 28, 2026: market makers "may receive reduced fees and certain adjusted position limits". In return they must give "consistent, two-sided liquidity", meaning they keep both a buy and a sell quote up, and meet quoting and volume requirements.
  - Status follows a review of "financial resources, trading experience, and business reputation".
  - The article says nothing about API speed, rate limits, FIX or colocation.
  - Source: [Kalshi Help: Market Maker Program](https://help.kalshi.com/en/articles/13823819-how-to-become-a-market-maker-on-kalshi)
- **Older market-maker terms (pre-2025, from a search summary).** A 2024 CFTC filing describes a market-maker program that ran from Mar 11, 2024 to Mar 11, 2026 unless extended. The filing itself was not read. Source: [CFTC filing (search result)](https://www.cftc.gov/filings/orgrules/rules02262412174.pdf)
- **Multicast data feed [NEW].** Finance Magnates, Aug 12, 2026: Kalshi launched a "multicast" Level 1 and Level 2 order-book feed, built with DoubleZero Edge, a low-latency network provider.
  - It covers **sports contracts and crypto perpetual futures**, offered "through Kalshi Research" to institutional market makers and systematic firms.
  - It is market data only: "not another execution channel".
  - Kalshi waives its data-revenue share for the first year. No price is given.
  - This is a secondary source. No matching Kalshi docs page or changelog entry was found.
  - Source: [Finance Magnates](https://www.financemagnates.com/fintech/kalshi-launches-real-time-level-2-data-feed-for-institutional-traders)
- **No published SLA (third party).** Kalshi publishes no millisecond latency figure and no public SLA (service-level agreement). Source: [codex.io benchmark](https://www.codex.io/blog/prediction-market-apis-benchmark) (third-party blog, search summary)

### Inferences
- A retail Basic or Advanced account has **no** Kalshi program that gives faster access. Every speed product is gated at Premier, Prime or institutional level, or is data-only.
- The only network lever left is where the bot runs, which the companion note on network and hosting covers. PrivateLink and VPC peering both assume a client inside AWS. That points the same way: us-east-2.

### Gaps
- Kalshi gives no official region, matching-engine location, or engine processing time.
- Whether the DoubleZero multicast feed will cover event contracts such as 15-minute crypto markets is unknown.

---

## 8. 2025-2026 changelog items and order types that bear on order speed

### Takeaway
The big speed-relevant changes since 2025 are these. Batches opened to all tiers (Nov 2025). V2 order endpoints arrived with matching-engine `ts_ms` (Apr-May 2026). The token buckets now allow bursts (Apr 2026). Advanced became self-serve and tier thresholds were halved (Jun 2026). Crypto moved to its own shard and auto-routing became the default (Aug 2026). Ed25519 arrived (Sep 2026), and so did `sending_ts_ms` (Oct 2026). IOC, FOK, post-only and order groups all exist. There is no new "faster" order type.

### Cited findings
- **Changes by date:**

  | Date | Change | Source |
  |---|---|---|
  | Nov 20, 2025 | Batch create open to every tier. Batch cancel followed Dec 4, 2025. | [Changelog](https://docs.kalshi.com/changelog) |
  | Nov 21, 2025 | IOC breaking change. Past `expiration_ts` is rejected instead of being turned into IOC, and IOC can't be combined with `expiration_ts`. "you must now explicitly set `time_in_force: "immediate_or_cancel"`". | [Changelog](https://docs.kalshi.com/changelog) |
  | Jan 22/28, 2026 | `GET /account/limits` added. | [Changelog](https://docs.kalshi.com/changelog) |
  | Apr 22, 2026 | V2 order endpoints `/portfolio/events/orders*` added. | [Changelog](https://docs.kalshi.com/changelog) |
  | Apr 23, 2026 | New token rate limits, write bursts allowed, Paragon tier added. | [Changelog](https://docs.kalshi.com/changelog) |
  | Apr 22, 2026 | `GET /account/endpoint_costs` added. | [Changelog](https://docs.kalshi.com/changelog) |
  | Apr 28, 2026 | FIX v1.0.22 adds `AlwaysEmitNewBeforeTrade`. | [Changelog](https://docs.kalshi.com/changelog) |
  | May 5, 2026 | V2 order responses include `ts_ms`, "the matching engine's wall-clock timestamp". | [Changelog](https://docs.kalshi.com/changelog) |
  | May 12, 2026 | Decrease accepts `reduce_by`. WebSocket error 25 (buffer overflow) defined. | [Changelog](https://docs.kalshi.com/changelog) |
  | May 25-Jun 25, 2026 | Legacy order endpoints get 1.5×, 5× and then 10× token costs, then are deprecated. | [Changelog](https://docs.kalshi.com/changelog) |
  | May 28-29, 2026 | FIX market-data session (KalshiMD). | [Changelog](https://docs.kalshi.com/changelog) |
  | Jun 11, 2026 | Self-upgrade to Advanced and the volume-progress endpoint. | [Changelog](https://docs.kalshi.com/changelog) |
  | Jun 18, 2026 | WebSocket limits: 500k subscriptions, 10k commands/s. | [Changelog](https://docs.kalshi.com/changelog) |
  | Jun 25, 2026 | Tier thresholds halved. FIX gets `ExDestination`. | [Changelog](https://docs.kalshi.com/changelog) |
  | Aug 20, 2026 | VPC peering for Prime and up (WebSocket and FIX). | [Changelog](https://docs.kalshi.com/changelog) |
  | Aug 24-27, 2026 | Crypto gets its own shard. Auto-routing becomes the default. `user_orders` gains `exchange_index`. | [Changelog](https://docs.kalshi.com/changelog) |
  | Sep 3, 2026 | 5 Hz CF Benchmarks channel. Cancel-all costs one cancel. Amend returns `remaining_count`. | [Changelog](https://docs.kalshi.com/changelog) |
  | Sep 17, 2026 | WebSocket post-subscribe race fixed. | [Changelog](https://docs.kalshi.com/changelog) |
  | Sep 24, 2026 | Ed25519 keys. +20% limits for Premier and up. WebSocket compression. | [Changelog](https://docs.kalshi.com/changelog) |
  | Oct 1, 2026 | `sending_ts_ms` on all WebSocket messages. Ed25519 is the web default. | [Changelog](https://docs.kalshi.com/changelog) |
  | Oct 8, 2026 | FIX logon accepts `read` + `write::trade` keys. | [Changelog](https://docs.kalshi.com/changelog) |

- **Order options (V2 create):**
  - `time_in_force` ∈ {`fill_or_kill`, `good_till_canceled`, `immediate_or_cancel`}. "`GTT` is not a valid API value".
  - `post_only` (boolean).
  - `self_trade_prevention_type` ∈ {`taker_at_cross`, `maker`} is **required**.
  - `reduce_only` "rejected unless time_in_force is immediate_or_cancel".
  - Also `cancel_order_on_pause` and `order_group_id`.
  - Source: [Create Order (V2)](https://docs.kalshi.com/api-reference/orders/create-order-v2), [Batch Create (V2)](https://docs.kalshi.com/api-reference/orders/batch-create-orders-v2)
- **Order groups.** These give "automatic order cancellation when a contracts limit is reached within a rolling 15-second window". The limit can be 1 to 1,000,000 contracts. Source: [Order Groups](https://docs.kalshi.com/getting_started/order_groups)
- **Maintenance.** Every Thursday, 3:00-5:00 AM ET, there is a trading pause. Orders can't be placed during it, but they can be cancelled. Source: [Maintenance and Pauses](https://docs.kalshi.com/getting_started/maintenance_and_pauses)
- **Upcoming change (date not yet set).** `use_yes_price` will become the default for WebSocket order books and then be removed (see §1). One unrelated item is dated ahead: Oct 22, 2026, Margin funding. Sources: [WebSocket Connection](https://docs.kalshi.com/websockets/websocket-connection), [Changelog](https://docs.kalshi.com/changelog)

### Inferences
- No 2025-2026 item adds a faster order path for retail accounts. The speed levers are all old features used better: Advanced tier, batch, explicit shard, a warmed connection, and Ed25519.
- FOK (fill or kill: fill the whole order now or cancel all of it) is available. It changes how an order fills, not how fast it travels.

### Gaps
- None beyond those already listed.

---

## 9. HTTP/2 on the API hosts

### Takeaway
The docs never mention HTTP/2. A live handshake check on Oct 15, 2026 showed that **both REST hosts negotiate HTTP/2 (`h2`) over TLS 1.3**. HTTP/2 lets one connection carry many requests at the same time.

### Cited findings
- **No mention in the docs.** A search of the full docs found no mention of "HTTP/2", "http2" or "multiplex". The only keep-alive guidance is the WebSocket ping (Kalshi pings every 10 s). Sources: [llms-full.txt](https://docs.kalshi.com/llms-full.txt), [Connection Keep-Alive](https://docs.kalshi.com/websockets/connection-keep-alive)
- **Own measurement [NEW]** (Oct 15, 2026, 18:34 UTC; `openssl s_client -alpn h2,http/1.1`, connection handshake only):
  - `external-api.kalshi.com` → `ALPN protocol: h2`, TLSv1.3, TLS_AES_128_GCM_SHA256.
  - `api.elections.kalshi.com` (CloudFront) → `ALPN protocol: h2`, TLSv1.3.
  - `external-api-ws.kalshi.com` → offers `h2`, and falls back to `http/1.1` when that is all the client offers.
  - ALPN is the step in the TLS handshake where the two sides agree which HTTP version to use. This shows the hosts *offer* HTTP/2. It isn't a statement from Kalshi.
  - Source: the project's own check, no URL

### Inferences
- Python's `requests` speaks only HTTP/1.1, so it sends one request at a time per connection. Firing 20 orders at once therefore needs 20 open connections, or they queue.
- An HTTP/2 client (for example `httpx` with `http2=True`) could send all 20 orders together on **one** already-warm TLS connection. That avoids the per-connection setup cost the existing note flagged at about 100 ms or more.
- This hasn't been tested against Kalshi. Possible issues include server-side limits on parallel streams and how the load balancer spreads streams.

### Gaps
- Kalshi doesn't document a parallel-stream limit or whether it supports HTTP/2 for API traffic, beyond what the handshake check shows.
- No timing comparison between HTTP/2 and HTTP/1.1 against Kalshi was run.
