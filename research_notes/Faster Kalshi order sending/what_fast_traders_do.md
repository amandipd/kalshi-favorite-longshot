# What fast traders on Kalshi, Polymarket and Betfair do to get orders in quickly

Research date: 2026-10-15. Most sources are from 2026. Older items are flagged. Many "latency" pages online are written by VPS sellers (companies that rent servers). Their numbers are marked as vendor claims.

Venue legality note: "Polymarket" below means the **international** Polymarket CLOB (clob.polymarket.com), which blocks US users, unless it says **Polymarket US**. Polymarket US is the separate CFTC-regulated exchange (docs.polymarket.us). Only Kalshi and Polymarket US are US-legal options. Betfair is included only as a mature comparison.

## 1. What latencies do Kalshi bot builders report, and from what setups?

### Takeaway
The only hard measurement found: about **27 ms median order round trip** (order sent to exchange acknowledgment) from a New York-area host, with about 21 ms of that being network distance. Kalshi's servers are most likely in **AWS us-east-2 (Ohio)**, behind a CloudFront CDN. Home connections are usually quoted at 50-200 ms. Most of a slow bot's delay is avoidable software and connection overhead, not distance.

### Cited findings
- **Measured, Sept 2026 (GitHub "latency-expos", Kalshi KXBTC15M markets):** order ack round trip **27.3 ms p50 / 60.5 ms p99** through `api.elections.kalshi.com` (CloudFront). Going direct to `external-api.kalshi.com` gave **29.0 ms p50 / 35.9 ms p99** (slightly slower median, much better worst case). Host was in the NYC metro. About **21 ms** of TCP round trip was pure network to the exchange. Authors inferred, but did not test, that moving to us-east-2 would remove most of that 21 ms. Source: [latency-expos via search snippet](https://github.com/YLiu-101/latency-expos) (repo now returns 404; numbers come from search-index text, so treat as secondhand)
- Same study: **reconnecting cost 51 ms** on external-api; **idle gaps up to 6 s caused no penalty** (the kept-open connection stayed warm). Source: [latency-expos via search snippet](https://github.com/YLiu-101/latency-expos)
- Glassnode's latency monitor states Kalshi's API (`api.elections.kalshi.com`) sits behind AWS CloudFront and the **origin servers are in AWS us-east-2 (Ohio)**. It probes from Ashburn, Ohio, Chicago, San Jose and others, every 5 s. (No numbers shown on the About page; undated.) Source: [Glassnode Prediction Markets Latency](https://latency.glassnode.com/prediction-markets/about)
- Vendor claim (Apr-Jul 2026): Kalshi's matching engine is in us-east-2 Ohio, not Chicago or New York. **Chicago VPS to FIX engine ≈ 10 ms**; Chicago to public REST/WebSocket hosts ≈ 1 ms, but that 1 ms is only the nearby CloudFront edge, not the engine. Europe ≈ 80 ms+. Home 50-200 ms, with 300-500 ms spikes under congestion and 20-100 ms jitter (swings). Source: [TradoxVPS](https://tradoxvps.com/best-vps-for-kalshi-trading-bots/) (vendor; no method given)
- Conflicting vendor claim: 1.14 ms RTT from Chicago to `api.elections.kalshi.com`, presented as "servers in Chicago." Other sources say this is just the CDN edge. Sources: [QuantVPS](https://www.quantvps.com/blog/kalshi-servers-location); contradicted by [TradoxVPS](https://tradoxvps.com/best-vps-for-kalshi-trading-bots/) and [Glassnode](https://latency.glassnode.com/prediction-markets/about)
- Another VPS seller reports ~0.9-1.5 ms ping from Chicago (same CDN-edge caveat). Source: [tradingvps.io](https://tradingvps.io/kalshi-trading-bot-setup-tutorial-automate-your-prediction-market-trading/)
- A Kalshi bot provider's public status page showed a **24-hour median of ~172 ms** to Kalshi's API from its own servers (Oct 2, 2026; host location not stated). Source: [Bot for Kalshi status](https://www.botforkalshi.com/status)
- Third-party guide: Kalshi REST latency "50-200 ms"; WebSocket lower. Source: [AlphaScope](https://www.alphascope.app/blog/kalshi-api)
- One guide says the recommended production REST host is `external-api.kalshi.com`, with `api.elections.kalshi.com` kept for compatibility. Source: [Parlay Kalshi API guide](https://www.parlay.run/kalshi-api)
- FIX (an industry order protocol over a persistent connection) is the institutional low-latency path; access is by contacting Kalshi, not self-serve. Sources: [Zuplo/DEV Kalshi guide via search](https://dev.to/zuplo/kalshi-api-the-complete-developers-guide-1fo4); [TradoxVPS](https://tradoxvps.com/best-vps-for-kalshi-trading-bots/)
- **Rate limits (official, current):** token buckets. Most requests cost 10 tokens. **Basic tier Write = 100 tokens/s with only 1 s of burst** (≈10 orders/s, ≈10 orders at once). **Advanced = 300/s with 3 s burst** (≈90 orders in a burst). Advanced is self-serve via the "Upgrade Account API Usage Level" endpoint. Higher tiers (Expert 600 … Prestige 9,600) are earned by volume share. REST and FIX share the same buckets. A whole batch is rejected if it doesn't fit in the bucket. On a 429 there is no Retry-After header. Source: [Kalshi Rate Limits docs](https://docs.kalshi.com/getting_started/rate_limits)
- Older (pre-token) tier page said Basic 10 writes/s, Advanced 30, Premier 100. Superseded. Source: [Kalshi old readme docs](https://trading-api.readme.io/reference/tiers-and-rate-limits)

### Inferences
- If a home PC far from Ohio sees orders stamped 250-320 ms after the target, distance alone does not explain it. Fiber from a distant US city to Ohio is roughly 50-60 ms round trip (an estimate from geography, not a source), and the NYC study shows the exchange itself adds only a few ms (27.3 ms ack minus ~21 ms network ≈ 6 ms). So most of the 250-320 ms is likely local: reading the book first with REST (one full round trip), request signing, cold connections (TLS handshake ≈ 1-2 extra round trips; reconnect cost 51 ms in the study), sending orders one after another, Python overhead, and clock error.
- A cloud VM in us-east-2 (Ohio) is where the measurements point. It could cut network time to a few ms. A Chicago VPS is a decent second choice (~10 ms claimed).
- On the Basic tier, a burst of more than ~10 order requests at one instant would hit the Write bucket limit. Upgrading to Advanced (self-serve) triples the budget and gives a 3 s burst.

### Gaps
- No Reddit or Discord quotes with Kalshi order timings were found (searches returned none).
- No published measurement of "book change seen → order acknowledged" on Kalshi.
- No official Kalshi statement of server region or colocation offering was found.
- The latency-expos repo is gone; its full tables could not be read.

## 2. Do fast traders trigger from WebSocket feeds instead of polling REST? How much faster is it?

### Takeaway
Yes. Every serious guide and builder uses WebSocket (a kept-open connection where the exchange pushes updates) for market data and keeps REST only for orders and slow-changing info. No one published a clean Kalshi "WebSocket vs REST" timing number. The gain is mostly one saved round trip per decision plus no polling gaps.

### Cited findings
- Kalshi's docs are described as giving REST "no freshness guarantee"; WebSocket streams order-book deltas, tickers, trades and fills over one persistent connection, "far better than repeated REST polling." Source: [TradoxVPS](https://tradoxvps.com/best-vps-for-kalshi-trading-bots/) (vendor paraphrase of docs)
- Kalshi WebSocket limit: **5 concurrent WebSocket connections per user**, so multiplex subscriptions on one connection. Source: [search summary of Parlay/Zuplo guides](https://www.parlay.run/kalshi-api)
- Production lessons from a Go scanner reading both Kalshi and Polymarket books by WebSocket (dev.to, Oct 10, year not shown, likely 2026): trust the server's best bid/ask over your rebuilt book (~1% of deltas diverged); Kalshi `seq` is per subscription, so any gap means rebuild the whole subscription; Kalshi server pings must extend your read deadline or you get drops every 30-80 s during maintenance; snapshot resync averaged **89 ms** (max 119 ms); handshake needs RSA-PSS signed headers. Source: [Dozor, DEV](https://dev.to/dozor/streaming-polymarket-and-kalshi-order-books-over-websockets-7-lessons-from-production-3khf)
- Polymarket bot-building guide after Feb 2026 rule changes: REST polling is "completely outdated"; use WebSocket. Source: [BlockBeats translation of @_dominatos](https://en.theblockbeats.news/news/61326)
- A Polymarket Rust bot author planned to replace polling with WebSocket to cut signal detection lag from **~15 s to ~50 ms**. (Planned, not measured.) Source: [casatrick, DEV](https://dev.to/casatrick/my-polymarket-trading-bot-in-rust-after-typescript-kept-missing-fills-4ena)
- Polymarket US docs: the REST order-book endpoint is rate-limited; production apps should use the **gRPC Market Data Stream** (lower latency, no rate-limit concerns). Source: [Polymarket US docs](https://docs.polymarket.us/institutional/orderbook/overview)
- Betfair officially pitches its Exchange Stream API as "low latency access" to market data instead of polling. Source: [Betfair Stream API docs](https://docs.developer.betfair.com/display/1smk3cen4v3lu3yomq5qye0ni/Exchange+Stream+API)

### Inferences
- For a strategy that reads books at a fixed moment, a WebSocket-maintained local book removes the "read books via REST, then send orders" round trip. That alone could save one full network round trip (tens of ms from home) plus REST processing time per market read.
- Reading many markets by REST in sequence multiplies that cost. WebSocket gives all books already in memory at the target moment.

### Gaps
- No measured Kalshi WebSocket-vs-REST freshness or delay numbers found.
- No public data on how stale Kalshi REST order-book snapshots can be.

## 3. Competition at predictable moments: who wins, how fast books empty, being "sniped"

### Takeaway
Short crypto markets on Polymarket were a well-known bot battleground in late 2025-early 2026 (latency arbitrage against Binance/Coinbase prices). Polymarket responded with taker fees (Jan 2026), a changing taker delay, and TWAP settlement (Aug 2026). For Kalshi, academic work confirms informed, fast flow hurts slow quotes, but no source measured how fast Kalshi 15-minute books empty at a fixed moment.

### Cited findings
- **Polymarket 15-min crypto (Jan 2026):** bots exploited small lags between Polymarket odds and spot exchange prices; "at least one wallet" made thousands of such trades in a month; a social post claimed $313 → $414k in a month (unverified). Polymarket added dynamic taker fees to curb this. Source: [Finance Magnates, Jan 7 2026](https://www.financemagnates.com/cryptocurrency/polymarket-introduces-dynamic-fees-to-curb-latency-arbitrage-in-short-term-crypto-markets/)
- Fee size conflict: Finance Magnates says ~3.15% on a 50¢ contract; Polymarket's own changelog says taker fees on 15-min crypto peak at **1.56% at 50%** (Jan 5, 2026). Prefer the official figure. Sources: [Finance Magnates](https://www.financemagnates.com/cryptocurrency/polymarket-introduces-dynamic-fees-to-curb-latency-arbitrage-in-short-term-crypto-markets/); [Polymarket changelog](https://docs.polymarket.com/changelog.md)
- A taker arb bot said to have made **$515k in a month at 99% win rate** was declared "dead" after fees exceeded the exploitable spread (claim, unverified). Source: [BlockBeats](https://en.theblockbeats.news/news/61326)
- **Polymarket removed its 500 ms taker delay on crypto markets ~Feb 18, 2026, without warning.** Market makers who relied on that half-second to cancel stale quotes reported "irreparable damage"; speed-focused takers gained. Sources: [JesterTheGoose on X](https://x.com/Jesterthegoose/status/2024055036754686034/photo/1); [shtanga0x on X](https://x.com/shtanga0x/status/2024162647550107958); [Protos](https://protos.com/polymarket-ends-trading-loophole-for-bitcoin-quants/)
- Official later changes to the crypto taker delay: **250 ms → 50 ms (Aug 17, 2026)**, then **50 ms → 150 ms (Sep 4, 2026)**. Source: [Polymarket changelog](https://docs.polymarket.com/changelog.md)
- **TWAP settlement (Aug 7, 2026):** Polymarket crypto Up/Down markets now settle on a Chainlink time-weighted average over 30 s (5-min markets) or 60 s (15-min and 4-hour). Article claims ~$7.6M was lost to last-second manipulation before the fix. "Strategies built to win the last tick are structurally obsolete." Order execution itself is still a live order-book race. Source: [casatrick Substack, Aug 3 2026](https://casatrick.substack.com/p/polymarket-twap-latency-trading-bots)
- CNBC (Aug 1, 2026): full-time prediction-market traders use AI bots and even an antenna to beat streaming lag; one trader, Logan Sudeith, collected $250k in a month. (Read via search summary; page blocked to fetch.) Source: [CNBC](https://www.cnbc.com/2026/08/01/traders-go-full-time-on-prediction-markets-using-ai-bots-and-antennas.html)
- Low-volume markets are bot-dominated: ~70% of closed Polymarket markets saw under $10k volume (2021-May 2026). Source: [CNBC, Jul 2 2026](https://www.cnbc.com/2026/07/02/prediction-markets-mostly-have-thinly-traded-contracts-.html) (via search summary)
- A news-trading bot builder on Polymarket (Mar 17, 2026): a newswire feed arriving ~500 ms after release was "still too slow": the book was already swept. "I don't think we ever won on pure speed." Wins came only from edge cases (ambiguity, others hitting size limits). Project shelved. Source: [EventWaves Substack](https://eventwaves.substack.com/p/trying-to-build-a-low-latency-polymarket)
- **Kalshi, academic (Apr 21, 2026):** Bartlett (Stanford) & O'Hara (Cornell), 41.6M trades over 478,167 markets. Single-name markets show more informed price impact; makers earn about twice as much per contract there; one-sided order flow predicts maker losses in single-name markets but not broad ones. Source: [Stanford Law](https://law.stanford.edu/2026/04/21/adverse-selection-in-prediction-markets-evidence-from-kalshi/)
- Bloomberg data (secondhand): bots average ~89 trades per active day vs 2.2 for humans on Kalshi. Source: [TurbineFi blog](https://www.turbinefi.com/blog/why-prediction-market-trades-get-picked-off-2026) (vendor; secondary)
- Kalshi filed a CFTC proposal (~Dec 2025) allowing order delays; a spokesperson said it "is only a filing" and may not proceed. A Nov 2025 rule change says live-event order delays come with notice on the platform. Status unknown. Sources: [Gambling911](https://www.gambling911.com/prediction-markets/kalshi-delay-implementation-on-order-executions-120925); [CFTC filing Nov 26 2025](https://www.cftc.gov/filings/orgrules/rules11262533628.pdf)
- An open-source Kalshi BTC bot author claims Kalshi's 15-min order book takes "several seconds" to reflect Binance moves because it is thinner. (Author's claim.) Source: [brandononchain/kalshibot](https://github.com/brandononchain/kalshibot)

### Inferences
- At predictable moments, takers race takers. On Polymarket the exchange has repeatedly tuned the rules (fees, taker delay, TWAP) to blunt pure-speed taker edges. Kalshi has no taker delay in the found sources, so its race is decided by raw latency.
- If a few hundred ms "already swept" news books on Polymarket, then 250-320 ms after a well-known moment is likely slow versus the fastest Kalshi players, who are probably in the tens of ms.

### Gaps
- No source measured how fast Kalshi 15-minute crypto books empty after a fixed moment, or who takes the liquidity.
- No Reddit/Discord accounts of being sniped on Kalshi crypto markets were found.

## 4. Pre-positioning: resting limit orders before the moment vs immediate-or-cancel at the moment

### Takeaway
Mature venues and their bots lean toward **resting (maker) orders** placed early, because they get queue priority, lower or zero fees, and (on Betfair and Polymarket) skip delays that slow takers. The cost is **adverse selection** (getting filled exactly when the price has moved against you) and the need to cancel fast. Taker IOC orders sent at the moment avoid stale fills but must win a speed race.

### Cited findings
- On Kalshi (2021-Apr 2025, markets open ≥24 h), **makers earn higher returns than takers**; both show a favourite-longshot pattern (high-priced contracts return slightly positive), stronger for takers. Takers have more extreme beliefs and pay up rather than risk not getting matched. Source: [Bürgi, Deng & Whelan, Jan 2026, UCD](https://www.karlwhelan.com/Papers/Kalshi.pdf) (note: sample excludes markets open <24 h, so not the 15-min crypto markets)
- Stale resting quotes get picked off by informed flow; one-sided flow predicts maker losses in single-name Kalshi markets. Source: [Stanford Law, Apr 2026](https://law.stanford.edu/2026/04/21/adverse-selection-in-prediction-markets-evidence-from-kalshi/)
- Polymarket (after Feb 2026): makers pay no fees and get daily rebates funded by taker fees; a cancel/replace loop over **200 ms risks adverse selection**; target **<100 ms**; home Wi-Fi quoted at >150 ms vs <5 ms on a datacenter VPS. Suggested maker price 0.90-0.95 on the likely side (unverified strategy claim). Source: [BlockBeats](https://en.theblockbeats.news/news/61326)
- Removing Polymarket's 500 ms taker delay hurt makers who depended on that time to pull stale quotes. Source: [shtanga0x on X](https://x.com/shtanga0x/status/2024162647550107958)
- Polymarket added a **Heartbeats API** (Jan 6, 2026) for monitoring connection status and canceling orders, i.e. cancel-on-disconnect protection for resting orders. Cancel batches up to 1,000 order IDs (Jun 15, 2026). Source: [Polymarket changelog](https://docs.polymarket.com/changelog.md)
- Kalshi pricing of cancels: **batch cancel costs 2 tokens per order vs 10 to create**, making cancel-heavy resting strategies cheaper in rate-limit terms. Source: [Kalshi Rate Limits docs](https://docs.kalshi.com/getting_started/rate_limits)
- Post-only orders (rejected if they would match immediately) exist on Polymarket to guarantee maker status. Source: [Polymarket docs (via search)](https://docs.polymarket.com/trading/orders/create)
- **Betfair:** "passive" bets (those not immediately matched) are placed **without the in-play bet delay**; extended to tennis, baseball, American football, darts and basketball (Nov 2025); football trial cut the delay 5 s → 3 s. API shows which markets qualify via `betDelayModels`. Sources: [Betfair newsletter Nov 2025](https://betting.betfair.com/betfair-announcements/exchange-news/betfair-exchange-november-2025-newsletter-no-delays-on-passive-bets-basketball-and-darts-271025-1392.html); [Betfair developer support](https://support.developer.betfair.com/hc/en-us/articles/26791968420636-How-can-I-identify-markets-that-accept-passive-orders-via-the-Betfair-API)
- Bot-focused Betfair guides describe placing unmatched orders just outside the spread so they fill the moment the price arrives. Sources: [Bet Angel](https://www.betangel.com/betfair-passive-bet-delay/); [Predictology](https://www.predictology.co/blog/does-bet-delay-really-matter-in-2026-what-every-automated-bettor-needs-to-know/)
- Open-source Kalshi BTC 15-min bot uses limit orders inside the spread, one fill per window, hold to settlement. Source: [nepalanurag/kalshi-btc15m-bot](https://github.com/nepalanurag/kalshi-btc15m-bot)

### Inferences
- A hybrid is common in the sources: rest orders early at your price, then cancel fast if conditions change. That turns a speed race at the moment into a cancel-speed problem, which is easier if cancels are cheap (Kalshi: 2 tokens) and the bot watches a WebSocket feed.
- Resting early is only safe if the strategy's edge doesn't depend on information that appears exactly at the moment. If it does, resting orders become the "stale quotes" that faster traders pick off.

### Gaps
- No source on Kalshi's current maker vs taker fee on 15-min crypto markets was checked.
- No direct comparison of IOC-at-the-moment vs resting-early fill rates on any venue.

## 5. Polymarket CLOB: latency tips, server location, round trips, batch orders

### Takeaway
Polymarket's CLOB runs in **AWS eu-west-2 (London)**; Polymarket itself names **eu-west-1 (Dublin)** as the nearest region not geoblocked. From US-East it is ~90-110 ms. It supports 15-order batches, heartbeats, and cut matching latency in July 2026. The official SDKs are slow; Rust clients and kept-open connections are the main speed tricks. This is the **international** venue, not usable by US persons.

### Cited findings
- Official: primary servers **eu-west-2**; closest non-georestricted region **eu-west-1**. Sources: [Polymarket geoblock docs](https://docs.polymarket.com/developers/CLOB/geoblock); [Polymarket help](https://help.polymarket.com/en/articles/13364163-geographic-restrictions)
- Independent triangulation behind Cloudflare also points to eu-west-2. Sources: [William Entriken on X](https://x.com/fulldecent/status/2043928173620945299); [Glassnode](https://latency.glassnode.com/prediction-markets/about)
- Dublin ↔ London figures conflict: "<2 ms" vs "~11-12 ms on the AWS backbone." Sources: [NYC Servers](https://newyorkcityservers.com/blog/polymarket-server-location-latency-guide) vs [QuantVPS](https://www.quantvps.com/blog/polymarket-servers-location) (both vendors; 11-12 ms is more plausible)
- One trader found one London availability zone (mapped to eu-west-2c in their account) gave the best WebSocket delivery. Source: [LowEndTalk](https://lowendtalk.com/discussion/221260/looking-for-very-low-latency-london-server-for-polymarket) (anecdotal)
- Region measurements to `clob.polymarket.com` (2026, p50): Amsterdam ping ~1.2 ms / TTFB ~6 ms; Frankfurt ~16 ms TTFB; London ~19 ms; **US-East ~88 ms ping / ~110 ms TTFB**; Singapore ~195 ms. Author concludes "Amsterdam," which conflicts with official eu-west-2 (likely Cloudflare edge effect; author has an affiliate link). Source: [BlueWhale-Quant-Lab, DEV](https://dev.to/bluewhale-quant-lab/i-measured-polymarkets-api-latency-from-5-regions-heres-the-script-and-the-results-3mjm)
- Vendor targets: market making <5 ms round trip; news arbitrage <10 ms; cross-platform arb <15 ms. Source: [NYC Servers](https://newyorkcityservers.com/blog/polymarket-server-location-latency-guide) (vendor)
- Changelog: batch orders **5 per request (Jun 3, 2025) → 15 (Aug 21, 2025)**; POST /order 200/s sustained (Jun 1, 2026); **"async commit pipeline cuts matching latency" (Jul 2026)**; Heartbeats API (Jan 6, 2026); cancel up to 1,000 IDs (Jun 15, 2026); crypto taker delay 250 → 50 ms (Aug 17, 2026) → 150 ms (Sep 4, 2026). Source: [Polymarket changelog](https://docs.polymarket.com/changelog.md)
- Batch POST /orders burst 2,000 per 10 s (Jun 1, 2026); batch endpoint processes orders in parallel. Source: [Polymarket docs (via search)](https://docs.polymarket.com/cn/api-reference/endpoints/clob/post-orders.md)
- Sign orders first, submit later ("separate signing from submission"). This is useful for batches. Source: [Polymarket clob-client guide](https://mintlify.com/Polymarket/clob-client/guides/creating-orders)
- Official SDKs "initiate a lot of helpful, but slow network checks before placing a trade." Source: [EventWaves](https://eventwaves.substack.com/p/trying-to-build-a-low-latency-polymarket)
- Fee-enabled markets reject orders without `feeRateBps`; query fee via `GET /fee-rate`. Source: [BlockBeats](https://en.theblockbeats.news/news/61326)
- **Polymarket US** (CFTC-regulated, separate venue): gRPC market data stream recommended; order entry 30-400 req/s per firm by tier, batch methods 50 req/s with up to 20 operations each; tier set by volume share. Source: [Polymarket US rate limits](https://docs.polymarket.us/trader-guide/rate-limits) (via search summary). Third-party guide: orders not processed within **5 s** during high latency are rejected with "Global Rate Limit Exceeded." Source: [Predictefy blog](https://blog.predictefy.com/polymarket-us-api) (unverified). Said to be invite-only after a Dec 2025 launch (third-party claim, possibly outdated). Source: same as above

### Inferences
- For a US trader, the international Polymarket latency tips (London/Dublin hosting) don't apply legally. Polymarket US server location was not found.

### Gaps
- No official Polymarket US server region, colocation, or round-trip numbers found.
- One builder wrote Polymarket infra is "primarily US-east" ([casatrick](https://dev.to/casatrick/my-polymarket-trading-bot-in-rust-after-typescript-kept-missing-fills-4ena)); this conflicts with the official docs and is likely wrong (or confused with Polymarket US).
- The date the crypto taker delay went back to 250 ms (after its Feb 2026 removal) was not found.

## 6. Betfair Exchange: latency tips (mature comparison)

### Takeaway
Betfair's advice is old and simple: use the Stream API instead of polling, keep connections alive, compress, reuse one session. Servers are UK/Ireland-centric. Betfair deliberately slows in-play takers with a bet delay (several seconds) but lets passive (resting) bets skip it, which rewards pre-positioning over raw speed.

### Cited findings
- Official: set `Connection: keep-alive` on all requests to keep connections persistent and reduce latency; send `Accept-Encoding: gzip, deflate`. Source: [Betfair: Optimizing API Application Performance](https://betfair-developer-docs.atlassian.net/wiki/spaces/1smk3cen4v3lu3yomq5qye0ni/pages/2699882/Optimizing+API+Application+Performance)
- Official: one session can and should be shared across many calls and threads. Source: [Betfair Best Practice](https://betfair-developer-docs.atlassian.net/wiki/spaces/1smk3cen4v3lu3yomq5qye0ni/pages/2687730/Best+Practice)
- Official Stream API: "low latency access" to market data; a `status` field is null when up to date and 503 when downstream services are lagging. Source: [Betfair Stream API docs](https://docs.developer.betfair.com/display/1smk3cen4v3lu3yomq5qye0ni/Exchange+Stream+API)
- Forum (2017-2020, **old**): a Dublin server pinged api.betfair.com at ~2.5 ms until July 2017, then ~11 ms (poster suspects a load balancer was added); ~20 ms average from Azure (Jan 2020). A user said servers are in Dublin (uncited). Source: [Betfair developer forum](https://forum.developer.betfair.com/forum/sports-exchange-api/exchange-api/28553-latency-to-api-betfair-com) (via search summary; page blocked)
- Forum (2019, **old**): Stream `pt` (publish time) vs local PC clock differed by ~1.3 s; mixes network delay with clock error. Source: [Betfair forum: Stream API latency](https://forum.developer.betfair.com/forum/sports-exchange-api/exchange-api/27059-stream-api-latency) (via search summary)
- A benchmark project describes Betfair's infrastructure as UK-centric, with higher latency from us-east and Singapore than eu-west. Source: [ChainBench PR](https://github.com/ChainBench/OpenChainBench/pull/1699/files)
- betfairlightweight (popular Python client) has a "lightweight" mode that skips object creation to save time. Source: [search summary of betfairlightweight docs](https://docsearch.algolia.com/mcp/docs/repo/betcode-org/betfair)
- In-play bet delays and passive-bet exemption: see section 4. Source: [Betfair newsletter Nov 2025](https://betting.betfair.com/betfair-announcements/exchange-news/betfair-exchange-november-2025-newsletter-no-delays-on-passive-bets-basketball-and-darts-271025-1392.html)

### Inferences
- The mature-venue lesson: the exchange itself shapes the speed race. Betfair and Polymarket both add delays to takers in some markets to protect resting liquidity. Kalshi has filed for, but not confirmed, similar powers.

### Gaps
- No official Betfair data center location found; forum threads are 6-9 years old.
- No current (2025-2026) Betfair round-trip numbers from a named host.

## 7. Evidence that faster orders improve fill rates or profits

### Takeaway
Direct evidence is thin and mostly from single builders, but it points one way: cutting avoidable overhead (cold connections, DNS, logging) from ~340 ms to ~100 ms raised one Polymarket bot's "good fill" rate from 61% to 89%. Market-maker losses after Polymarket removed its 500 ms buffer show a few hundred ms matters a lot.

### Cited findings
- **Polymarket bot, TypeScript → Rust (2026, two weeks of parallel paper trading, 500 sampled trades):** per-order latency **340 ms → 101 ms** (Rust p95 148 ms, p99 187 ms; TS p99 680 ms). Fills within 0.5¢ of detected price **61% → 89%**; average slippage **5.3¢ → 1.1¢**; entry 75.4¢ → 71.2¢ (detected at 70.1¢). Win rate 71% → 73% (author says not significant). Time breakdown in TS: TLS handshake 89 ms, DNS 47 ms, sync logging 58 ms, network 94 ms. **Connection reuse (shared HTTP client, keep-alive, 20 idle connections per host) drove ~60% of the gain.** Network transit (~91-94 ms from Europe) was the only part they couldn't remove. Source: [casatrick, DEV](https://dev.to/casatrick/my-polymarket-trading-bot-in-rust-after-typescript-kept-missing-fills-4ena) (paper trading, single author)
- Same author: Python decision loop **48 ms median / 120 ms p99 → Rust ~654 µs median / 1.5 ms p99** on a $20/month VPS near Polymarket; "the REST call dominates"; "physical proximity to the exchange often matters more than code." (Internal numbers inconsistent: headline says 800 µs.) Source: [casatrick, DEV](https://dev.to/casatrick/building-a-low-latency-trading-bot-in-rust-from-48ms-to-800us-4n1i)
- Makers lost heavily when Polymarket removed the 500 ms taker delay. Source: [shtanga0x on X](https://x.com/shtanga0x/status/2024162647550107958)
- Cancel/replace slower than 200 ms risks adverse selection on Polymarket crypto markets (guidance, not measured). Source: [BlockBeats](https://en.theblockbeats.news/news/61326)
- Polymarket TWAP article: under TWAP, latency still matters for execution and oracle-lag trades; "sustaining low latency for 30-60 seconds straight" is the new challenge. Source: [casatrick Substack](https://casatrick.substack.com/p/polymarket-twap-latency-trading-bots)
- Vendor narrative (not data): in a Fed-decision market a residential Python bot "updated their quotes 340 milliseconds later" than a nearby bot. Source: [TradoxVPS](https://tradoxvps.com/best-vps-for-kalshi-trading-bots/)

### Inferences
- The 61% → 89% result is the closest public analogue to "orders that land later fill less." It came mostly from fixing connection setup and blocking work, not from moving servers.

### Gaps
- No Kalshi-specific study linking order latency to fill rate.
- No peer-reviewed work on latency and fill rates in prediction markets found.

## 8. Open-source Kalshi / Polymarket bots and clients with speed tricks

### Takeaway
Rust clients dominate the "fast" open-source space. Shared speed tricks: kept-open HTTP connections, async/concurrent requests, WebSocket-maintained books, integer prices, pre-signing, batch orders, and skipping slow SDK checks.

### Cited findings
- **DRADIS** (Rust, Kalshi + Polymarket): "low-latency" bot, evaluates markets every 50 ms, async multi-asset tasks, RSA-PSS signing for Kalshi. A PR adds measurement of tick timing and order placement round trips. Sources: [mbordash/DRADIS](https://github.com/mbordash/DRADIS); [DRADIS PR #4](https://github.com/whrit/DRADIS/pull/4)
- **kalshi-trading** (Rust crate): built for speed: integer prices (no floats), BTreeMap sorted book, parking_lot mutexes, REST + WebSocket + RSA-PSS. Source: [crates.io kalshi-trading](https://crates.io/crates/kalshi-trading)
- **kalshi-fast-rs**: async Rust, WebSocket parity incl. `user_orders`, retries with backoff. Source: [lib.rs kalshi-fast-rs](https://lib.rs/crates/kalshi-fast-rs)
- **kalshi-rust**: async (tokio) wrapper; older versions lacked complete WebSocket support. Source: [lib.rs kalshi-rust](https://lib.rs/crates/kalshi-rust)
- **polyfill-rs** ("fastest Polymarket Rust client"): fetch-markets mean **321.6 ms vs 409.3 ms** (polymarket-rs-client) **vs 1.366 s** (official Python client) = 4.2× faster than Python; parsing p50 0.5 ms; separates cold-start vs warm-connection timing. Self-reported, one machine; V1-era numbers. Sources: [floor-licker/polyfill-rs](https://github.com/floor-licker/polyfill-rs); [crates.io](https://crates.io/crates/polyfill-rs)
- **polymarket-rs-client**: create + EIP-712 sign order ~266.5 ms vs 1.127 s for the official Python client (no method given). Source: [TechieBoy/polymarket-rs-client](https://github.com/TechieBoy/polymarket-rs-client)
- Polymarket official SDK: sign separately, then submit in a batch (`postOrders`, up to 15). Sources: [Polymarket clob-client guide](https://mintlify.com/Polymarket/clob-client/guides/creating-orders); [Polymarket changelog](https://docs.polymarket.com/changelog.md)
- Kalshi batch create: up to 25 orders per batch in the docs example; batches save HTTP round trips but **not** rate-limit tokens (10 per order). Sources: [Kalshi Rate Limits docs](https://docs.kalshi.com/getting_started/rate_limits); [Kalshi batch-create docs](https://docs.kalshi.com/api-reference/orders/batch-create-orders-v2.md)
- Betfair: betfairlightweight "lightweight" mode; flumine event-driven framework built on it. Source: [betcode-org/flumine](https://github.com/betcode-org/flumine)

### Inferences
- For a Python bot, the cheapest wins in these sources are not a rewrite: one long-lived HTTP session (keep-alive, warm before the moment), concurrent sends (asyncio or threads) or one batch request instead of many sequential requests, a WebSocket-fed local book, and no blocking logging on the hot path. A Rust rewrite mostly matters after network distance is fixed.

### Gaps
- No open-source Kalshi bot was found that publishes measured end-to-end order timings.
- Benchmarks in client READMEs are self-reported and not independently checked.
