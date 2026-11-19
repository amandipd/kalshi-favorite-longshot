# Kalshi API facts for fast entry

Researched Oct 11, 2026 for the fast-entry design (now in `bot/kalshi_bot/fast_entry.py`). Each fact is tagged **confirmed** (stated in Kalshi's docs or
rulebook, or seen in our own measurement) or **uncertain** (inferred, third-party, or not documented). Sources are linked
at the end of each line.

## Summary: what matters for the design

1. **Rate limit:** on the Basic tier, 12 orders at once trips the limit. The write bucket holds 100 tokens, enough for 10 orders, and anything past that gets a 429. One free API call moves the account to Advanced, which allows bursts of 90 or more. Check the tier first with `GET /account/limits`.
2. **Batch create (`POST /portfolio/events/orders/batched`):** sends every order in one request. Each order gets its own `fill_count`, `ts_ms` and `error`. The whole batch is rejected if the bucket can't cover all of it, and the docs don't say what order the orders inside a batch run in.
3. **Two hidden delays:** first, parallel single orders each open a new TLS connection (about 100 ms or more each) unless the connections are warmed in advance. Second, orders without `exchange_index` are "auto-routed", which Kalshi says adds latency. The crypto markets are on shard 2.
4. **Our measurement wasn't the exchange:** `api.elections.kalshi.com` is a CloudFront CDN (a network of edge servers that sit in front of the real ones). Our 30 ms round trip only reached a nearby CloudFront edge. The real servers (`external-api.kalshi.com`) are an AWS load balancer in us-east-2 (Ohio), about 70-90 ms away from the home PC. Kalshi doesn't offer co-location.
5. **Clock:** Kalshi has no endpoint that returns the server time. `ts_ms` is the matching engine's wall-clock time when it processed the order, so `ClockSync` from `ts_ms` is the right approach. The HTTP `Date` header puts Kalshi's clock 0.10-0.17 s ahead of the home PC, which agrees with SNTP. Matching is price then time, with no documented speed bump or randomizing, so whoever reaches the matching engine first wins.

---

## 1. Rate limits

A **token bucket** is a counter that refills at a steady rate up to a cap. Each request spends tokens, and a request
that finds too few tokens is refused.

| Fact | Status | Source |
|---|---|---|
| The limiter is a token bucket that refills continuously, with "no fixed windows and no per-second resets". | confirmed | [rate_limits](https://docs.kalshi.com/getting_started/rate_limits) |
| Most requests cost 10 tokens, and a V2 single create costs 10. `GET /account/endpoint_costs` lists the exceptions. | confirmed | [rate_limits](https://docs.kalshi.com/getting_started/rate_limits), [create-order-v2](https://docs.kalshi.com/api-reference/orders/create-order-v2.md) |
| There are separate **Read** and **Write** buckets. Write covers placing, amending and cancelling orders, plus order groups. REST and FIX share the buckets. | confirmed | [rate_limits](https://docs.kalshi.com/getting_started/rate_limits) |
| Refill rates in tokens per second (read / write): Basic 200 / 100, Advanced 300 / 300, Expert 600 / 600, Premier 1,200 / 1,200, Paragon 2,400 / 2,400, Prime 4,800 / 4,800, Prestige 12,000 / 9,600. At 10 tokens an order, Basic allows 10 orders a second and Advanced allows 30. | confirmed | [rate_limits](https://docs.kalshi.com/getting_started/rate_limits) |
| Sep 24, 2026: the read and write limits for Premier, Paragon, Prime and Prestige rose 20%. The table above may or may not include that rise. | confirmed (entry) / uncertain (table) | [changelog](https://docs.kalshi.com/changelog/index.md) |
| **Burst size (how much the bucket holds):** Basic Write holds 1 s of budget (100 tokens, so 10 orders). Write buckets above Basic hold 3 s (Advanced holds 900 tokens, so 90 orders). | confirmed | [rate_limits](https://docs.kalshi.com/getting_started/rate_limits) |
| The `GET /account/limits` reference instead describes non-Basic write buckets as "two seconds" of budget. The two pages disagree, so read `bucket_capacity` from that endpoint. | uncertain | [get-account-api-limits](https://docs.kalshi.com/api-reference/account/get-account-api-limits.md) |
| **Tiers:** a new account starts on Basic. Advanced comes from `POST /account/api_usage_level/upgrade`, a permanent grant, if "at least 1 of the user's last 100 Predictions orders was created via API". This bot's account qualifies. The call costs 30 Write tokens. | confirmed | [upgrade endpoint](https://docs.kalshi.com/api-reference/account/upgrade-account-api-usage-level.md) |
| Expert and above are earned from trailing 30-day volume share (Expert needs 0.075% to earn it) or assigned by Kalshi. Volume is reviewed daily, and each grant lasts 30 days. | confirmed | [rate_limits](https://docs.kalshi.com/getting_started/rate_limits) |
| `GET /account/limits` returns `usage_tier`, plus `refill_rate` and `bucket_capacity` for the read and write buckets, and the grants. | confirmed | [get-account-api-limits](https://docs.kalshi.com/api-reference/account/get-account-api-limits.md) |
| The repo doesn't record which tier this account is on. | confirmed (searched the repo) | - |
| **429:** the body is `{"error": "too many requests"}`, with no `Retry-After` or `X-RateLimit-*` headers. There's no penalty or cooldown, and the next request succeeds once the bucket has refilled enough. | confirmed | [rate_limits](https://docs.kalshi.com/getting_started/rate_limits) |
| **A cancel counts as a write.** A single V2 cancel costs 10 tokens, a batch cancel costs 2 per order, and cancel-all costs the same as cancelling one order (since Sep 3, 2026). | confirmed | [rate_limits](https://docs.kalshi.com/getting_started/rate_limits), [changelog](https://docs.kalshi.com/changelog/index.md) |
| **Shard buckets:** a single order with `exchange_index` ≥ 1 is billed to that shard's Write bucket. An **auto-routed** order (`exchange_index` left out, which is what the bot sends today) "is billed to every shard's Write bucket". Batch creates and cancels always use the unscoped Write bucket. | confirmed | [rate_limits](https://docs.kalshi.com/getting_started/rate_limits), [exchange_sharding](https://docs.kalshi.com/getting_started/exchange_sharding.md) |
| **Per key, per account or per IP?** The docs don't say. They describe the tier as the account's ("the authenticated user's"), so the limit is most likely per account. | uncertain | [get-account-api-limits](https://docs.kalshi.com/api-reference/account/get-account-api-limits.md) |
| Only authenticated requests are described as costing tokens. Any limit on unauthenticated public GETs (the bot reads its order books that way) is undocumented. | uncertain | [rate_limits](https://docs.kalshi.com/getting_started/rate_limits) |

**Would 12 simultaneous orders trip the limit?** On **Basic, yes.** 12 × 10 = 120 tokens is more than the 100-token
bucket, so orders 11 and 12 get a 429 (the bucket refills 10 tokens per 0.1 s). A batch of 12 is rejected outright. On
**Advanced or above, no.** 120 tokens is well under 900.

## 2. Batch orders

| Fact | Status | Source |
|---|---|---|
| **V2 endpoint:** `POST /portfolio/events/orders/batched`, with a body of `{"orders": [CreateOrderV2Request, …]}`. Each item has the same fields as a single V2 create (`ticker`, `side`, `count`, `price`, `time_in_force`, `self_trade_prevention_type`, plus optional `client_order_id`, `exchange_index` and others). | confirmed | [batch-create-orders-v2](https://docs.kalshi.com/api-reference/orders/batch-create-orders-v2.md) |
| **Largest batch:** there's no fixed number. "The maximum batch size scales with your tier's write budget." In practice that means bucket capacity ÷ 10: 10 orders on Basic, 90 on Advanced. | confirmed (wording) / uncertain (exact cap) | [batch-create-orders-v2](https://docs.kalshi.com/api-reference/orders/batch-create-orders-v2.md), [rate_limits](https://docs.kalshi.com/getting_started/rate_limits) |
| **Cost:** 10 tokens per order, with no discount. "The whole batch must fit in the bucket at once, or the entire batch is rejected." | confirmed | [rate_limits](https://docs.kalshi.com/getting_started/rate_limits) |
| **Response:** each order gets its own entry with `order_id`, `client_order_id`, `fill_count`, `remaining_count`, `average_fill_price` and `average_fee_paid` (when something filled), `ts_ms`, and `error`. `ts_ms` is missing when that order errored. | confirmed | [batch-create-orders-v2](https://docs.kalshi.com/api-reference/orders/batch-create-orders-v2.md) |
| Errors are reported per order, so the batch isn't all-or-nothing once accepted. The docs don't say whether the orders run in array order or how close together. | uncertain | [batch-create-orders-v2](https://docs.kalshi.com/api-reference/orders/batch-create-orders-v2.md) |
| **Who can use it:** the V2 docs name no tier. The legacy batch endpoint stopped requiring Advanced on Nov 20, 2025, and restricted subaccount keys got access on Jul 30, 2026. | confirmed | [changelog](https://docs.kalshi.com/changelog/index.md) |
| **Legacy `POST /portfolio/orders/batched`:** the V2 endpoints arrived on Apr 22, 2026. From Jun 4, legacy calls cost 10× the V2 price, and the legacy write endpoints were deprecated between Jun 18 and 25, 2026. That page now returns 404 and isn't in the OpenAPI spec. Don't use it. | confirmed | [changelog](https://docs.kalshi.com/changelog/index.md), [openapi.yaml](https://docs.kalshi.com/openapi.yaml) |
| The old docs capped legacy batches at "20 orders per batch" for Advanced members. We only have that from a search snippet, because the page now redirects. | uncertain | [old readme.io page](https://trading-api.readme.io/reference/batchcreateorders-1) |
| Batch cancel (V2) is `DELETE /portfolio/events/orders/batched` and costs 2 tokens per order. Auto-routing needs each order's `market_ticker`. | confirmed | [openapi.yaml](https://docs.kalshi.com/openapi.yaml) |

## 3. The WebSocket order book

| Fact | Status | Source |
|---|---|---|
| **URL:** `wss://external-api-ws.kalshi.com/trade-api/ws/v2` is recommended. `wss://api.elections.kalshi.com/trade-api/ws/v2` is also supported. | confirmed | [api_environments](https://docs.kalshi.com/getting_started/api_environments.md) |
| **Auth:** every WebSocket connection needs an API key, even for public data. You send the usual three `KALSHI-ACCESS-*` headers during the handshake (the opening exchange), signing timestamp + `GET` + `/trade-api/ws/v2`. | confirmed | [websocket-connection](https://docs.kalshi.com/websockets/websocket-connection.md), [quick_start_websockets](https://docs.kalshi.com/getting_started/quick_start_websockets.md) |
| **Subscribe:** `{"id":1,"cmd":"subscribe","params":{"channels":["orderbook_delta"],"market_tickers":[…]}}`. You can later add or drop markets with `update_subscription` (`add_markets` / `delete_markets`), and `get_snapshot` re-sends a snapshot. | confirmed | [orderbook-updates](https://docs.kalshi.com/websockets/orderbook-updates.md) |
| **Snapshot, then deltas:** the channel first sends `orderbook_snapshot`, a "complete view of the order book's aggregated price levels", as `yes_dollars_fp` and `no_dollars_fp` lists of `[price, count]`. After that it sends `orderbook_delta` messages (`price_dollars`, `delta_fp`, `side`, `ts_ms`, plus `client_order_id` when the change was your own order). | confirmed | [orderbook-updates](https://docs.kalshi.com/websockets/orderbook-updates.md) |
| **Both sides:** the book lists only bids. A YES ask is 1 − the best NO bid, so the YES-bid and NO-bid lists together are both sides of the book. REST `GET /markets/{ticker}/orderbook` with `depth=0` (the default) returns every level. | confirmed | [orderbook_responses](https://docs.kalshi.com/getting_started/orderbook_responses.md), [get-market-orderbook](https://docs.kalshi.com/api-reference/market/get-market-orderbook.md) |
| The snapshot most likely carries every level, but the page says "complete view of aggregated levels" without saying "full depth". | uncertain | [orderbook-updates](https://docs.kalshi.com/websockets/orderbook-updates.md) |
| **Sequence numbers:** `seq` is a counter that "should be checked if you want to guarantee you received all the messages". `sid` identifies the subscription. The docs give no recovery steps. The standard method: keep the snapshot, add each delta to its price level (removing a level when it reaches 0), and on a `seq` gap ask for a new snapshot (`get_snapshot`) or resubscribe. | confirmed (fields) / uncertain (recovery) | [orderbook-updates](https://docs.kalshi.com/websockets/orderbook-updates.md) |
| **Timestamps:** `ts_ms` is when the change was recorded. Since Oct 1, 2026, `sending_ts_ms` is "when Kalshi queued this message at the network layer". | confirmed | [orderbook-updates](https://docs.kalshi.com/websockets/orderbook-updates.md), [changelog](https://docs.kalshi.com/changelog/index.md) |
| **Keep-alive:** Kalshi sends a Ping every 10 s and expects a Pong back. | confirmed | [connection-keep-alive](https://docs.kalshi.com/websockets/connection-keep-alive.md) |
| **Limits:** connections per user depend on the tier (the default was 200 in Sep 2025), up to 10k commands a second per session and 500k market subscriptions. Error 25 means the buffer overflowed during a burst. | confirmed | [changelog](https://docs.kalshi.com/changelog/index.md) |
| **Latency vs REST:** not documented. The feed pushes changes as they happen, so at 480 s the book is already on the PC and no round trip is needed. | uncertain | [quick_start_websockets](https://docs.kalshi.com/getting_started/quick_start_websockets.md) |
| A cheaper option on REST: `GET /markets/orderbooks?tickers=…` returns up to 100 books in one request. It may need auth. | confirmed (endpoint) / uncertain (auth) | [get-multiple-market-orderbooks](https://docs.kalshi.com/api-reference/market/get-multiple-market-orderbooks.md) |

## 4. Server time

| Fact | Status | Source |
|---|---|---|
| The API reference has **no server-time endpoint**. `GET /exchange/status` has no clock field. `GET /exchange/user_data_timestamp` is "when user data was last validated", not the current time. | confirmed (not in the docs) | [get-exchange-status](https://docs.kalshi.com/api-reference/exchange/get-exchange-status.md), [get-user-data-timestamp](https://docs.kalshi.com/api-reference/exchange/get-user-data-timestamp.md) |
| **`ts_ms` in a V2 order answer:** "Matching engine timestamp at which the order was processed, as Unix epoch milliseconds". The May 5, 2026 changelog calls it "the matching engine's wall-clock timestamp". So it's when the matching engine handled the order (matched it, or cancelled what was left of an IOC), on the engine's own clock, not when the gateway received it. | confirmed | [create-order-v2](https://docs.kalshi.com/api-reference/orders/create-order-v2.md), [changelog](https://docs.kalshi.com/changelog/index.md) |
| How the engine's clock is kept in sync (NTP or PTP) and how precise it is: not documented. | uncertain | - |
| **Other clocks:** every WebSocket message has `ts_ms` and `sending_ts_ms`, which is a clock reading that costs no requests. It gives offset plus one-way delay, so it's a bound rather than an exact offset. FIX reports carry `TransactTime`. The HTTP `Date` header is whole seconds only, and on `api.elections` it comes from CloudFront (§7). | confirmed (fields) / uncertain (Date source) | [orderbook-updates](https://docs.kalshi.com/websockets/orderbook-updates.md), [changelog](https://docs.kalshi.com/changelog/index.md) |
| How far `KALSHI-ACCESS-TIMESTAMP` may be from Kalshi's clock before a request is refused: not documented. | uncertain | [api_keys](https://docs.kalshi.com/getting_started/api_keys.md) |

## 5. Hosting and latency

| Fact | Status | Source |
|---|---|---|
| `api.elections.kalshi.com` (the host the bot uses) is **AWS CloudFront**. The answers carried `X-Cache: Hit from cloudfront`, `Via: … (CloudFront)`, an `X-Amz-Cf-Pop` header naming the edge, and `Cache-Control: public, max-age=1`. | confirmed (our headers) | measurement, §7 |
| `external-api.kalshi.com` and `external-api-ws.kalshi.com` (Kalshi's recommended hosts) are CNAMEs (DNS aliases) for `elections-external-api-107430227.us-east-2.elb.amazonaws.com`. That's an **AWS load balancer in us-east-2 (Ohio)**, with no CDN in front. | confirmed (DNS, Oct 11) | `Resolve-DnsName`, [api_environments](https://docs.kalshi.com/getting_started/api_environments.md) |
| The matching engine is most likely in us-east-2 too. Glassnode says "Origin servers are in AWS us-east-2 (Ohio)", and the FIX host resolves to 18.223.x and 18.119.x addresses. Kalshi doesn't publish its region. One bot-hosting blog says us-east-1. QuantVPS's "0-1 ms from Chicago" most likely measured a CloudFront edge, not the exchange. | uncertain | [Glassnode](https://latency.glassnode.com/prediction-markets/about), [botforkalshi](https://www.botforkalshi.com/blog/kalshi-bot-hosting-guide), [QuantVPS](https://www.quantvps.com/blog/kalshi-servers-location) |
| **Co-location:** Kalshi doesn't offer it. The closest options are AWS **PrivateLink** (a private link into Kalshi's network inside AWS, for Premier and above) and **VPC peering** (joining your AWS network to Kalshi's, for Prime and above). Both are arranged through institutional@kalshi.com. | confirmed | [api_environments](https://docs.kalshi.com/getting_started/api_environments.md), [fix/connectivity](https://docs.kalshi.com/fix/connectivity.md) |
| **FIX** (an order protocol traditional exchanges use, over a persistent connection): the order host is `mm.fix.elections.kalshi.com`, port 8228 for KalshiNR order entry. Retransmission (RT), drop copy and PT sessions need you to contact Kalshi. Only one FIX connection is allowed per API key, and FIX uses the same rate-limit buckets as REST. | confirmed | [fix/connectivity](https://docs.kalshi.com/fix/connectivity.md), [rate_limits](https://docs.kalshi.com/getting_started/rate_limits) |
| Whether a retail Basic or Advanced key can open a KalshiNR session without asking: the docs don't gate it by tier. Oct 8, 2026: FIX logon now accepts keys with `read` + `write::trade`. | uncertain | [fix/connectivity](https://docs.kalshi.com/fix/connectivity.md), [changelog](https://docs.kalshi.com/changelog/index.md) |
| **Shards:** crypto (and commodities) trade on **exchange_index 2**, a separate matching engine. "Automatic routing will incur an additional latency cost." | confirmed | [exchange_sharding](https://docs.kalshi.com/getting_started/exchange_sharding.md) |

## 6. IOC behaviour and fairness

| Fact | Status | Source |
|---|---|---|
| **Price then time priority:** orders match "first by price and then time priority … at the same price … from oldest to most recent" (Rule 5.7 in rulebook v1.13, Aug 2024; Rule 5.8 in the 2023 draft). Orders fill "or better", so an IOC buy works up from the cheapest ask until it reaches its limit. | confirmed | [CFTC filing 2024](https://cftc.gov/filings/orgrules/rules0726243839.pdf), [CFTC filing 2023](https://www.cftc.gov/filings/documents/2023/orgkexkalshiexhibitm231130.pdf) |
| **Speed bumps** (deliberate delays), randomizing, or batch auctions for orders that arrive together: none in the docs or the rulebook. In effect, the first order to reach the shard's matching engine takes the cheapest asks. How the engine orders arrivals within the same millisecond isn't documented. | confirmed (none documented) / uncertain (tie order) | same, plus [changelog](https://docs.kalshi.com/changelog/index.md) |
| IOC can't be combined with `expiration_time`. "For IOC orders, [`remaining_count`] reflects the final state after unfilled contracts are canceled." | confirmed | [create-order-v2](https://docs.kalshi.com/api-reference/orders/create-order-v2.md) |
| The balance check happens inside the matching engine, and each shard keeps its own cash. | confirmed | [exchange_sharding](https://docs.kalshi.com/getting_started/exchange_sharding.md) |
| Kalshi isn't responsible for orders delayed by "slowness of [a member's] Internet connection". | confirmed | rulebook v1.13 ([CFTC](https://cftc.gov/filings/orgrules/rules0726243839.pdf)) |
| **Bursts on the minute:** Kalshi doesn't mention them. Our own tape shows one at 480 s (`timing.md`). The only related item from Kalshi is the WebSocket "buffer overflow … during a message burst" error (May 12, 2026). | uncertain | [changelog](https://docs.kalshi.com/changelog/index.md) |

## 7. Live measurement (a home PC, Oct 11, 2026)

- **What was sent:**
  - 20 unauthenticated `GET https://api.elections.kalshi.com/trade-api/v2/exchange/status`, one every 0.57 s on one kept-open connection, 05:01:15-05:01:27 UTC on Oct 12. All returned 200, and no key was used.
  - DNS lookups of the four hosts.
  - 15 bare TCP connects (the network handshake only: no TLS, no HTTP request), one every 0.6 s, 05:11:07-05:11:18 UTC. These measure the round trip to the Ohio load balancer, because the GETs turned out to stop at the CDN.
  - Nothing was sent in the bot's trading minutes, and the scripts refused to send within 20 s of them.
- **HTTP round trip to the CloudFront edge:**
  - First request: 125.7 ms, which includes opening the connection.
  - Warm requests: median **30.4 ms**, min **23.5 ms**, max 96 ms.
  - Every answer was a CloudFront cache hit, so this measures the trip to the edge, not to Kalshi's servers.
- **TCP handshake:**
  - To the us-east-2 load balancer (`external-api.kalshi.com`, 10 connects): median **93 ms**, min **69 ms**.
  - To the CloudFront edge (5 connects): min 19 ms, median 59 ms.
  - Both had spikes of 160-210 ms. That's jitter (uneven delay) on the local network.
- **Clock:**
  - Each `Date` header narrows the offset, because the header is whole seconds and the 0.57 s spacing makes its ticks land at different points within a second.
  - Together the 20 headers put the server clock at **0.104-0.169 s ahead of the home PC**, using the midpoint of each request. SNTP says +0.150 to +0.158 s, which agrees.
- **What it means:**
  - An order (never cached) most likely takes about 70-100 ms round trip, about 35-50 ms each way, plus matching time, with occasional spikes of about 200 ms.
  - Opening a fresh TLS connection costs several round trips, roughly 150-250 ms to Ohio.

## What this means for the design

1. Call `GET /account/limits` once. If it says `basic`, call `POST /account/api_usage_level/upgrade` before turning on fast windows.
2. Use the batch endpoint, or else open enough connections ahead of time. `send_all`'s 8 threads on one `requests.Session` open up to 7 new TLS connections right at the mark. The session's pool holds up to 10 connections per host by default ([requests HTTPAdapter](https://requests.readthedocs.io/en/latest/api/#requests.adapters.HTTPAdapter)).
3. Add `"exchange_index": 2` (the bot's `self.section`) to single orders. This skips the auto-routing delay and bills only shard 2's bucket.
4. At the mark, use a book the bot already holds: either a WebSocket `orderbook_delta` book kept since prep, or one `GET /markets/orderbooks` request.
   - Checked in §8: REST order books from `api.elections.kalshi.com` are **not** cached. The market list **is** (up to 15 s).
   - `external-api.kalshi.com` has no CDN at all.
5. Keep `ClockSync` on `ts_ms`. It can also take a passive sample from each WebSocket message's `sending_ts_ms`.

## 8. Are REST order books cached? (follow-up test, Oct 11, 2026)

- **What was sent:** 12 unauthenticated GETs to `api.elections.kalshi.com`, 0.55 s or more apart, 05:15:16-05:15:24 UTC
  on Oct 12, on one kept-open connection, no key:
  - 1 × `GET /markets?series_ticker=KXBTC15M&status=open`
  - 11 × `GET /markets/{ticker}/orderbook`: 7 plain (the same URL repeated) and 4 with a random `?_cb=…` query string
    to bust the cache, interleaved.
- **Order books are not cached** (confirmed):
  - All 11 order-book answers said `X-Cache: Miss from cloudfront`, including plain repeats of the same URL 0.65 s
    apart through the same edge server (`Via` …40eef8a1…, the same `X-Amz-Cf-Pop` edge).
  - They carried no `Cache-Control` and no `Age` header. Each one went through to Kalshi's servers.
  - The cache-busting query string changed nothing: still a miss, with the same headers.
- **The market list is cached** (confirmed):
  - The answer said `X-Cache: Hit from cloudfront`, `Cache-Control: public, max-age=15`, `Age: 10`. So
    `GET /markets` can be up to 15 s old.
  - Here it returned only `KXBTC15M-26OCT120115-15`, a market that had **closed at 05:15:00 UTC**, 16 s before the
    request, even though the filter asked for `status=open`.
  - For the bot: list markets at prep (450 s), when even a 15 s-old list holds the current window. Don't trust a list
    read in the first seconds after a window opens.
  - The `/exchange/status` cache seen in §7 is `max-age=1`.
- **Comparing bodies told us nothing** (limitation):
  - Because the stale list pointed at a just-closed market, every book was empty (51 bytes, identical hash). Identical
    bodies here mean an empty book, not a cached one.
  - The headers settle the question, but the body test wasn't repeated on a live book, because the 12-request budget
    was spent.
- **Bonus, a real round trip to Kalshi's servers through CloudFront** (cache misses):
  - Plain requests: median **96 ms**, min **84 ms**.
  - All 11: median 108 ms, with spikes of 176 and 218 ms.
  - This is the best estimate so far of an order's network round trip on `api.elections` (§7 guessed 70-100 ms).
