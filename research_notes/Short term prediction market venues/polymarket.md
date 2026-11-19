# Polymarket short-term crypto "Up or Down" markets (international vs Polymarket US) as a second venue next to Kalshi, as of 13 Oct 2026

Bottom line:
- **International Polymarket (polymarket.com, CLOB on Polygon):** the deepest, most complete short-term family (5m, 15m, 1h, 4h, daily, on 7 to 8 coins). A US resident cannot use it. The US is "close-only" on both the website and the API, and orders from restricted regions are rejected. The latency check also fails for a US bot: servers are in London (eu-west-2), and crypto markets carry a deliberate 150 ms taker delay (a "speed bump": your marketable order is held before it can match).
- **Polymarket US (CFTC-regulated exchange, formerly QCEX):** legal for US residents, with state-level exceptions that are being fought in court. It lists **only BTC** Up/Down, in 15-minute and 1-hour windows (live since 22 Sep 2026). Fees are almost identical to Kalshi's. The retail API has REST plus push WebSockets for the order book and your own orders. Latency comes out **UNCLEAR, leaning PASS**: the setup matches Kalshi's, with no blockchain step, but no latency figures or hosting region are published.

## 1. Which short-term market families exist, and where (international vs Polymarket US)?

### Takeaway
International Polymarket lists crypto Up/Down markets in 5-minute, 15-minute, 1-hour, 4-hour, daily, weekly and monthly windows on BTC, ETH, SOL, XRP, DOGE, BNB, HYPE and ZEC, plus a few equity Up/Down markets such as a COIN daily. Polymarket US has only **BTC** Up/Down in 15-minute and 1-hour windows (launched 22 Sep 2026), plus BTC price-ladder markets.

### Cited findings
**International (polymarket.com)**
- The 15-minute Up/Down markets were first announced in a Polymarket X post: "15 minute up/down crypto polymarkets now live. Powered & secured by @Chainlink". The post is undated in the saved capture. Its ID suggests about Oct 2025, but that is not verified. Source: [Polymarket on X](https://x.com/Polymarket/status/1980296306200555911)
- By Jan 2026, the 15-minute family covered BTC, ETH, SOL and XRP. Source: [The Block, 6 Jan 2026](https://www.theblock.co/news/business/2026-01-06-polymarket-adds-taker-fees-to-15-minute-crypto-markets-to-fund-liquidity-rebates-384461)
- The live 15-minute event list (public Gamma API, read 13 Oct 2026) shows windows for Bitcoin, Ethereum, XRP and Dogecoin (Oct 13, 2:15-2:30 PM ET), plus Solana, Hyperliquid (HYPE), BNB and ZCash (ZEC) in August 2026 examples. Slugs follow `<coin>-updown-15m-<unix start>`. Source: [Gamma API, tag 15M](https://gamma-api.polymarket.com/events?tag_slug=15M&closed=false&limit=60)
- 5-minute markets launched on **12 Feb 2026**, BTC only at first, resolving on Chainlink BTC/USD. Sources: [Polymarket changelog](https://docs.polymarket.com/changelog/changelog); [CoinMarketCap Academy](https://coinmarketcap.com/academy/article/polymarket-debuts-5-minute-bitcoin-prediction-markets-with-instant-settlement)
- On 13 Oct 2026 the crypto hub navigation showed: 5 Min (7), 15 Min (7), 1 Hour (9), 4 Hours (7), Daily (11), Weekly (74), Monthly (22). The 5-minute FAQ names "Bitcoin Up or Down - October 13, 2:15PM-2:20PM ET" and an Ethereum equivalent. Sources: [polymarket.com/crypto/5M](https://polymarket.com/crypto/5M); [polymarket.com/crypto/15M](https://polymarket.com/crypto/15M)
- The hourly page lists BTC, XRP, DOGE, HYPE and BNB hourly Up/Down markets. This comes from a search-result summary; the page itself was not fetched. Source: [polymarket.com/crypto/hourly](https://polymarket.com/crypto/hourly)
- On 1 Mar 2026, the changelog extended taker fees "to all crypto markets (1H, 4H, daily, weekly)", which confirms that 4-hour and weekly crypto families exist. Source: [Polymarket changelog](https://docs.polymarket.com/changelog/changelog)
- Equity Up/Down markets exist. A COIN (Coinbase) daily Up/Down market resolved on a Pyth feed and traded only $106. This comes from a search-result summary. Source: [Polymarket COIN daily event](https://polymarket.com/event/coin-up-or-down-on-october-7-2026)
- FX reference prices were added on 29 Sep 2026: a `price.equity.twap` channel for **EUR/USD and USD/JPY**. On 2 Oct, `hypeusd` and `zecusd` were added to the crypto price feed. That points to FX and more coin markets, but no listed FX Up/Down product was confirmed. Source: [Polymarket changelog](https://docs.polymarket.com/changelog/changelog)
- Cadence: 15-minute windows run back to back around the clock, aligned to :00, :15, :30 and :45 ET. 5-minute windows likewise run all day (e.g. 4:20-4:25 AM ET). Sources: [Gamma API](https://gamma-api.polymarket.com/events?tag_slug=15M&closed=false&limit=60); [CoinMarketCap Academy](https://coinmarketcap.com/academy/article/polymarket-debuts-5-minute-bitcoin-prediction-markets-with-instant-settlement)

**Polymarket US (polymarket.us)**
- "Bitcoin Up or Down" 15-minute markets went live on the US app on **22 Sep 2026 at 12:00 PM ET**, running around the clock. "For now, Bitcoin is the only asset available in this format." Early cash-out is allowed. Source: [Crypto Briefing, 28 Sep 2026](https://cryptobriefing.com/polymarket-15-minute-bitcoin-markets-us/)
- First full week (22-29 Sep): 15-minute BTC traded about **$92M**, and 1-hour BTC traded **$8.74M**. Other BTC durations added another $682k. Source: [DeFi Rate, 30 Sep 2026](https://defirate.com/news/polymarket-us-15-minute-bitcoin-volume-hits-92m-in-first-full-week/)
- The official US docs describe four automated BTC families: Up/Down (15-minute and 60-minute windows), Above/Below ladders (hourly, daily at 5 PM ET, weekly on Friday at 5 PM ET), Price Range, and monthly One-Touch. "About 48 fifteen-minute and 24 hourly windows are open at any time." 15-minute windows are listed about 12 hours ahead and 1-hour windows about 24 hours ahead. Each window opens for trading about 90 seconds before it starts. Source: [Polymarket US Crypto FAQs](https://docs.polymarket.us/faqs/crypto-faqs.md)
- The US crypto schema names only `btc`. It says `5m` and `4h` "follow the same pattern and can appear in preprod before listing". Source: [Polymarket US Crypto Schema](https://docs.polymarket.us/trader-guide/crypto-schema.md)
- **Conflict:** the US docs still say the automated families are "listed in preprod" and that "Production currently carries the hand-listed Bitcoin markets". The changelog entry of 21 Sep 2026 gives no production date. Press and volume data show 15-minute and 1-hour BTC live from 22 Sep. Sources: [US Crypto Schema](https://docs.polymarket.us/trader-guide/crypto-schema.md); [US changelog](https://docs.polymarket.us/changelog) vs [DeFi Rate](https://defirate.com/news/polymarket-us-15-minute-bitcoin-volume-hits-92m-in-first-full-week/)

### Inferences
- For a US trader, the only reachable Polymarket short-term product today is **BTC 15-minute and 1-hour Up/Down on Polymarket US**. ETH, SOL, XRP and the 5-minute and 4-hour families are international-only. The docs suggest 5m and 4h BTC could come to the US later.
- Polymarket US's 15-minute BTC grid runs on the same ET quarter-hours as Kalshi's 15-minute crypto markets. That makes like-for-like comparison and cross-venue checks easy, but it also means the two venues' risk on the same window is closely correlated.

### Gaps
- No complete official list was found of which coins have international 5-minute and 4-hour markets. Pages show counts (7 each) but only name BTC and ETH.
- Whether an EUR/USD or USD/JPY Up/Down market is actually listed could not be confirmed.
- No official Polymarket US launch announcement or rule book entry was found for the 15-minute BTC market, only press reports and docs that still say "preprod".

## 2. Settlement: price source, exact rule, payout speed

### Takeaway
On the international site, the 5-minute, 15-minute and 4-hour markets settle on a **Chainlink Data Streams 60-second TWAP** (time-weighted average price: the average price over the final 60 seconds, not a single last tick). The rule is "Up" if close ≥ open. Hourly and daily markets settle on **Binance BTCUSDT candles**. Polymarket US's docs say BTC Up/Down settles on a **60-second simple average of CF Benchmarks' BRTI**, with ties going to Up. One press report instead says Chainlink, so the source is disputed. Both venues settle within about a minute.

### Cited findings
**International**
- 7 Aug 2026: "Crypto up/down markets resolve on Chainlink TWAP prices. 5-minute markets use a 30-second window; 15-minute and 4-hour markets use 60 seconds." From 14 Aug 2026 at 00:00 UTC, "5-minute crypto markets switch to a 60-second Chainlink TWAP". Source: [Polymarket changelog](https://docs.polymarket.com/changelog/changelog)
- A 15-minute BTC market (Oct 12, 8:00-8:15 PM ET) gives its resolution source as `https://data.chain.link/streams/btc-usd-twap-60s-streams`. Its rule: "Up" if the Chainlink-generated BTC TWAP at the end is at or above the start value. The rule states that only the Chainlink BTC/USD TWAP stream counts, not other sources or spot markets. Source: [Gamma API event](https://gamma-api.polymarket.com/events?slug=btc-updown-15m-1791849600)
- Before August, 15-minute markets used spot Chainlink streams (e.g. `sol-usd`). From October they use `-twap-60s-streams`. Source: [Gamma API, tag 15M](https://gamma-api.polymarket.com/events?tag_slug=15M&closed=false&limit=60)
- At the 5-minute launch, a market resolved "Up" if BTC's end-of-window price was ≥ the start price on Chainlink's BTC/USD stream. Source: [CoinMarketCap Academy](https://coinmarketcap.com/academy/article/polymarket-debuts-5-minute-bitcoin-prediction-markets-with-instant-settlement)
- **Hourly:** the market "resolves based on whether the closing price of the Bitcoin/USDT 1-hour candle beginning at 6:00PM ET on Binance … is greater than or equal to its opening price"; "if so, the outcome is 'Up'". The stated resolution source is Binance BTC_USDT. Source: [Polymarket hourly event, 1 Oct 2026](https://polymarket.com/event/bitcoin-up-or-down-october-1-2026-6pm-et)
- **Daily:** BTC daily Up/Down compared Binance 1-minute candle closes, and "if the final 'Close' price for both candles is exactly equal, the market resolves 50-50". This comes from a search-result summary; the page itself was not fetched. Source: [Polymarket daily event, 6 Jul 2026](https://polymarket.com/event/bitcoin-up-or-down-on-july-6-2026)
- **Speed:** the 15-minute window that ended 00:15:00 UTC shows `closedTime` 00:15:53 UTC and `umaResolutionStatus: resolved`. That is about 53 seconds from window end to resolution. Source: [Gamma API event](https://gamma-api.polymarket.com/events?slug=btc-updown-15m-1791849600)
- Since 28 Sep 2026, `/v2/resolutions` rows can include settlement time estimates. Source: [Polymarket changelog](https://docs.polymarket.com/changelog/changelog)

**Polymarket US**
- "All markets settle on CF Benchmarks' Bitcoin Real-Time Index (BRTI), published once per second." Up/Down uses the "simple average of the 60 BRTI prices in the interval [T − 60 s, T), rounded to two decimals", applied at both open and close. The open value is fixed a few seconds after the start and published as the "price to beat". The long side pays $1.00 if close ≥ open, and a tie settles **Up**. Up/Down windows "settle shortly after close, typically within a minute". If index data is incomplete, settlement is deferred. Sources: [Polymarket US Crypto FAQs](https://docs.polymarket.us/faqs/crypto-faqs.md); [US Crypto Schema](https://docs.polymarket.us/trader-guide/crypto-schema.md)
- **Conflict:** Crypto Briefing says the US 15-minute market resolves via "Chainlink's BTC/USD oracle". Source: [Crypto Briefing](https://cryptobriefing.com/polymarket-15-minute-bitcoin-markets-us/). The official docs say BRTI. Prefer the docs, but check the live market's rules page.

### Inferences
- Both venues use roughly a 60-second averaged close, not a last tick. A move in the final seconds shifts the settlement value by only a fraction of the move. That lowers last-second flip risk for a contract that is already deep in the money, compared with a single-print settlement. Check how Kalshi's 15-minute crypto settlement index compares.
- On the international site, the hourly market (Binance candle, close ≥ open) and the 15-minute market (Chainlink TWAP) use different sources and rules. Do not assume one model fits all families.

### Gaps
- Whether international winners are paid automatically or must "redeem" (an on-chain claim step), and how long that takes after `resolved`, was not confirmed.
- No official note was found on how Polymarket US credits payouts after settlement. The US FAQ says it "does not specify".

## 3. Fees, tick size, minimum order size

### Takeaway
On the international site, crypto taker fee = **0.07 × C × p × (1 − p)**: 0.63¢, 0.33¢ and 0.07¢ per contract at 90¢, 95¢ and 99¢. Makers pay nothing and share 20% of taker fees as rebates. On Polymarket US, Θ = **0.0695**, giving almost the same per-contract fees. The difference is that US fees are rounded to the nearest cent per order with banker's rounding (round half to even), so very small orders can pay $0. Tick size is 0.01 on Polymarket US; one international 15-minute market showed 0.001 with a 5-share minimum.

### Cited findings
**Fee history (international)**
- 5 Jan 2026: taker fees enabled on 15-minute crypto markets, "peaking at 1.56% at 50% probability", with daily USDC maker rebates. 12 Feb: 5-minute markets launched on the same curve. 1 Mar: fees extended to all crypto markets (1H, 4H, daily, weekly) created after 6 Mar. 30 Mar: "Fee Structure V2" with per-category rates. 31 Mar: fees to be read from the market's `feeSchedule`. 28 Apr: CLOB V2 makes pUSD the collateral and sets fees at match time, with no `feeRateBps` on orders. Source: [Polymarket changelog](https://docs.polymarket.com/changelog/changelog)
- Coverage in Jan 2026 said the fees were meant to curb latency arbitrage. Sources: [Finance Magnates](https://www.financemagnates.com/cryptocurrency/polymarket-introduces-dynamic-fees-to-curb-latency-arbitrage-in-short-term-crypto-markets/); [The Block](https://www.theblock.co/news/business/2026-01-06-polymarket-adds-taker-fees-to-15-minute-crypto-markets-to-fund-liquidity-rebates-384461)

**Current schedule (international)**
- "fee = C × feeRate × p × (1 − p)". Crypto taker rate 0.07, maker rate 0, maker rebate 20%. "Makers are never charged fees." Fees are rounded to 5 decimal places, with a minimum of 0.00001 USDC. Example: crypto at $0.95 costs $0.33 per 100 shares. Source: [Polymarket Trading Fees](https://docs.polymarket.com/trading/fees)
- A live 15-minute BTC market shows `feeSchedule {exponent 1, rate 0.07, takerOnly true, rebateRate 0.2}` and `feeType crypto_fees_v2`. Source: [Gamma API event](https://gamma-api.polymarket.com/events?slug=btc-updown-15m-1791849600)
- Maker rebates are fee-curve weighted and calculated per market, so you compete only with other makers in the same market. They are paid daily in pUSD, with a $1 minimum, and the percentage is "at the sole discretion of Polymarket". Source: [Maker Rebates Program](https://docs.polymarket.com/programs/maker-rebates)

**Polymarket US**
- Taker fee = Θ × C × p × (1 − p) with Θ = 0.0695 (0.10 for table tennis). Taker fees are unchanged in the 7 Oct 2026 schedule. Source: [Polymarket US Fee Schedule](https://docs.polymarket.us/fees)
- Maker rebate is currently a flat Θ = −0.0125 (a rebate of 0.0125 × C × p × (1 − p)). From **19 Oct 2026, 1 PM ET** it moves to tiers by prior-month maker volume: none below $10M, −0.0035 for $10M-$50M, −0.0070 for $50M-$200M, −0.0104 above $200M. The extra **weekly crypto maker rebate ends 15 Oct 2026, 8 AM ET**. Taker rebate (paid weekly) from 19 Oct: none below $250k of prior-month taker volume, then 3% / 5% / 10% / 15% / 30% by tier. Sources: [Polymarket US Fee Schedule](https://docs.polymarket.us/fees); [US changelog](https://docs.polymarket.us/changelog)
- "All fees and rebates are rounded to the nearest $0.01 using banker's rounding." Fees can round to $0.00 on small trades. Contracts trade from $0.01 to $0.99 with a $1.00 face value. Example: a 100-lot taker at $0.90 pays $0.63, and at $0.99 pays $0.07. Source: [Polymarket US Fee Schedule](https://docs.polymarket.us/fees)
- Third-party sites disagree on the US taker coefficient, citing 0.05 (effective 3 Apr 2026) or 0.06 (1 Jul 2026). The official page now says 0.0695. Sources: [Sacra](https://sacra.com/c/polymarket/); [OddsShopper](https://www.oddsshopper.com/articles/betting-101/polymarket-fees); [GitHub PR citing the 17 Sep 2026 schedule](https://github.com/ProgramComputer/marketcaster/pull/26)

**Fee per contract, computed from the formulas above (taker side)**

| Price | International crypto (0.07) | Polymarket US (0.0695) | Fee as % of price | Break-even win rate (p + fee) |
|---|---|---|---|---|
| 90¢ | 0.630¢ | 0.626¢ | ~0.70% | ~90.63% |
| 95¢ | 0.333¢ | 0.330¢ | ~0.35% | ~95.33% |
| 99¢ | 0.069¢ | 0.069¢ | ~0.07% | ~99.07% |

(At price p, the fee is about feeRate × p of the maximum gain (1 − p): roughly 6.3-6.9% of the upside.)

**Tick size and minimum order size**
- International: a closed 15-minute BTC market shows `orderPriceMinTickSize 0.001` and `orderMinSize 5` (shares). Liquidity-reward settings are `rewardsMinSize 50` and `rewardsMaxSpread 4.5`¢. Source: [Gamma API event](https://gamma-api.polymarket.com/events?slug=btc-updown-15m-1791849600)
- International tick sizes range from 0.1 down to 0.0001, can change during a market's life (announced by a `tick_size_change` message), and non-conforming orders are rejected. `min_order_size` is in shares. Sources: [Place Orders](https://docs.polymarket.com/trading/place-orders.md); [changelog, 23 Jul 2025](https://docs.polymarket.com/changelog/changelog)
- Polymarket US Up/Down: tick 0.01, minimum quantity 0.01 contract (fractional contracts), prices 0.01-0.99. Source: [US Crypto Schema](https://docs.polymarket.us/trader-guide/crypto-schema.md)

### Inferences
- Taker fees at 90-99¢ are essentially the same on Kalshi, Polymarket US and international Polymarket. Kalshi uses a 0.07 × p × (1 − p) shape, rounded up per order; that is from the project's own setup and was not re-verified here. **Rounding** is where the venues differ. Polymarket US rounds to the nearest cent, half to even, so at 99¢ any order under about 7 contracts pays $0 in fees, and at 95¢ an order of 1 contract pays $0. Kalshi rounds up, which costs more on small orders.
- Resting as a maker (post-only) avoids the fee entirely on both Polymarket venues and earns a rebate. On Polymarket US, the flat −0.0125 maker rebate ends 19 Oct for anyone under $10M a month of maker volume.
- The 0.001 tick seen on an international 15-minute market (if it holds at 90-99¢) allows finer pricing near 99¢ than a 1¢ tick. On Polymarket US the 0.01 tick means 99¢ is the highest bid below $1.

### Gaps
- Whether international crypto markets always list at a 0.001 tick or switch to it near extreme prices was not confirmed. The docs only say tick size can change.
- No Polymarket US crypto-specific fee override was found. The fee page applies the standard Θ to "all markets".

## 4. Liquidity: volume, depth at 90-99¢, who provides it, bots

### Takeaway
International 5-minute and 15-minute crypto markets traded about $153M a day combined by April 2026. Volume per window is uneven: a single overnight 15-minute BTC window traded about $34k, and alt-coin windows often have only $1-3k resting. Polymarket US's 15-minute BTC grew from $2.4M to $27.7M a day in its first week. **No published data on order-book depth at 90-99¢ near the close** was found. Market makers are paid through rebates and liquidity rewards, and latency-arbitrage bots are widely reported.

### Cited findings
- 5-minute and 15-minute crypto formats combined averaged about **$153M a day**, with more than $4B total (Chainlink-linked report, about Apr 2026). Source: [MEXC News](https://www.mexc.com/news/1014771)
- Single-window snapshots from the public Gamma API: BTC 15-minute (Oct 12, 8:00-8:15 PM ET) had a final volume of **$34,029**. Mid-window snapshots for Oct 13, 2:15-2:30 PM ET: BTC $6.6k volume / $12.2k liquidity, ETH $434 / $2,980, XRP $117 / $1,509. August examples: SOL $15.0k / $1.1k, HYPE $178 / $1.6k, BNB $189 / $29.3k. The BTC 15-minute series-level liquidity field read $747k. "Liquidity" here is Polymarket's resting-order measure, not depth at a given price. Sources: [Gamma API event](https://gamma-api.polymarket.com/events?slug=btc-updown-15m-1791849600); [Gamma API list](https://gamma-api.polymarket.com/events?tag_slug=15M&closed=false&limit=60)
- One BTC hourly window (1 Oct 2026, 6 PM ET) traded about $28.9k. Source: [Polymarket hourly event](https://polymarket.com/event/bitcoin-up-or-down-october-1-2026-6pm-et)
- **Polymarket US:** 15-minute BTC rose from $2.40M (23 Sep) to **$27.71M (29 Sep)** a day. By comparison, Kalshi's 15-minute markets made up about $7B, or 86%, of Kalshi's crypto volume over 1-28 Sep 2026. Source: [DeFi Rate](https://defirate.com/news/polymarket-us-15-minute-bitcoin-volume-hits-92m-in-first-full-week/)
- Polymarket US traded **$2.72B** notional in a single week (headline). Source: [Crypto Briefing](https://cryptobriefing.com/polymarket-us-weekly-volume-surge)
- Platform-wide records: $582M on 17 Jun 2026, and $698.8M on 11 Oct 2026, per a later report. These are all markets, not only crypto. Sources: [DeFi Rate tracker](https://defirate.com/prediction-markets/volume/polymarket/); search summary of [Crypto Briefing](https://cryptobriefing.com/polymarket-us-weekly-volume-surge)
- **Who provides liquidity (international):** maker rebates (20% of crypto taker fees, paid daily) and liquidity rewards (on the BTC 15-minute market, a minimum of 50 shares within 4.5¢ of the midpoint). Polymarket also offers co-location in eu-west-2 to "market makers and individual traders operating on their own account". Sources: [Maker Rebates](https://docs.polymarket.com/programs/maker-rebates); [Gamma API event](https://gamma-api.polymarket.com/events?slug=btc-updown-15m-1791849600); [Geoblock page](https://docs.polymarket.com/developers/CLOB/geoblock)
- **Who provides liquidity (US):** an approved Market Maker Program (contact institutional@qcex.com), a Liquidity Incentive Program, and a weekly crypto maker rebate that ends 15 Oct 2026. Sources: [US Market Maker Program](https://docs.polymarket.us/incentives/market-maker.md); [US Fee Schedule](https://docs.polymarket.us/fees)
- **Latency-arbitrage bots:** financial press describes a bot trading BTC, ETH and SOL 15-minute contracts by exploiting price lags against Binance and Coinbase, reportedly betting $4-5k a time at about a 98% win rate. That figure is unverified. Sources: [Finance Magnates, "Bot playground"](https://www.financemagnates.com/trending/prediction-markets-are-turning-into-a-bot-playground/); [Yahoo Finance](https://finance.yahoo.com/news/arbitrage-bots-dominate-polymarket-millions-100000888.html)
- An IMDEA Networks study (cited secondhand) estimated about **$40M** of arbitrage profit on Polymarket from Apr 2024 to Apr 2025. Arbitrage windows reportedly shrank from 12.3 s (2024) to 2.7 s (late 2025). Both figures come via vendor blogs and are not specific to Up/Down markets. Source: [QuantVPS](https://www.quantvps.com/blog/binance-to-polymarket-arbitrage-strategies); search summary
- Polymarket's own changes target these bots: taker fees (Jan 2026) and a taker delay on crypto markets (see section 6). Sources: [Finance Magnates](https://www.financemagnates.com/cryptocurrency/polymarket-introduces-dynamic-fees-to-curb-latency-arbitrage-in-short-term-crypto-markets/); [changelog](https://docs.polymarket.com/changelog/changelog)

### Inferences
- International BTC 15-minute windows can carry $10k-$35k+ each, but alt-coin windows are thin ($1-3k resting). Depth at 90-99¢ late in a window is probably a small fraction of that.
- Polymarket US's 15-minute BTC averaged about $290k per window on 29 Sep ($27.7M ÷ 96 windows), but only in its launch week, while incentives ran. The weekly crypto maker rebate ends 15 Oct and maker rebates are cut from 19 Oct, so depth may thin after that.

### Gaps
- No public source gives order-book depth at 90-99¢ in the final minutes of a window on either venue. Measuring it would need public order-book snapshots, which was outside the scope of this desk research.
- No concrete evidence (articles, repos or on-chain studies) was found of bots arbitraging Polymarket against Kalshi on the 15-minute crypto markets specifically.
- No Dune dashboard broken down by short-term crypto family was found.

## 5. API: connection, order types, authentication, wallet, retail access

### Takeaway
International: CLOB V2 at `clob.polymarket.com`. Orders are signed (EIP-712) by a Polygon wallet, collateral is pUSD, and the order types are GTC, GTD, FOK, FAK and post-only. It is reachable from the US only for closing positions. Polymarket US: a **self-service Retail API for any verified US account** (REST + WebSocket, keys created through the app), plus an institutional Exchange API (REST, gRPC, FIX) for brokers, FCMs and DMA firms. No wallet is needed; accounts are funded in USD.

### Cited findings
**International**
- CLOB V2 went live on 28 Apr 2026. V1 is unsupported, resting orders were wiped at cutover, pUSD replaced USDC.e as collateral, and builder codes became native. Source: [Polymarket changelog](https://docs.polymarket.com/changelog/changelog)
- Orders are signed as EIP-712 typed data on chain ID 137 (Polygon). Signature types: 0 EOA, 1 Proxy, 2 Safe, 3 Deposit Wallet. Limit orders are GTC or GTD; GTD orders expire one minute early as a safety margin. Market orders are FAK or FOK. Post-only is rejected if it would match. Batch orders take 1-15 per call. Order statuses are `live`, `matched`, `delayed` and `unmatched`. Source: [Place Orders](https://docs.polymarket.com/trading/place-orders.md)
- Post-only orders and a HeartBeats API arrived 6 Jan 2026. FAK arrived 28 May 2025. Source: [Polymarket changelog](https://docs.polymarket.com/changelog/changelog)
- The user WebSocket authenticates with CLOB API key, secret and passphrase (the "L2" credentials derived from the wallet). Source: [Real-Time Order Updates](https://docs.polymarket.com/trading/realtime-order-updates.md)
- The public Gamma API (`gamma-api.polymarket.com`) gives market metadata without authentication: fee schedule, tick, minimum size and resolution source. Source: [Gamma API event](https://gamma-api.polymarket.com/events?slug=btc-updown-15m-1791849600)

**Polymarket US**
- Two APIs. The **Exchange API** is for "DMA Participants, ISVs, IBs, and FCMs", over REST, gRPC and FIX, with "RSA auth via Auth0". The **Retail API** is for app users, "Personal accounts only", self-service keys, over REST and WebSocket. Deposits go through ACH via Aeropay or card/Apple Pay via Checkout. Source: [US API Overview](https://docs.polymarket.us/trader-guide/api-overview)
- The Retail API trades at `api.polymarket.us`, with public market data at `gateway.polymarket.us` (no key needed). Requests are signed with X-PM-Access-Key, X-PM-Timestamp and X-PM-Signature headers, with the timestamp within 30 s of server time. SDKs are Python and TypeScript. These details are partly secondhand (search summaries); one third-party guide says no sandbox is documented. Sources: [US API intro](https://docs.polymarket.us/api-reference/introduction); [Does Polymarket have an API?](https://docs.polymarket.us/learn/faq/api); [TradoxVPS](https://tradoxvps.com/polymarket-us-api/); [QuantVPS](https://www.quantvps.com/blog/polymarket-us-api-available)
- The WebSocket handshake uses the same three headers, with the signature computed over "timestamp + 'GET' + path". Source: [US WebSocket overview](https://docs.polymarket.us/api-reference/websocket/overview.md)
- Retail order types: market and limit. Time-in-force options: good-till-cancelled, "12am PT", start-of-game, and immediate-or-cancel. FOK, GTD and post-only are not documented on the retail order-types page. Institutional DAY and GTD orders exist (13 Sep 2026 changelog). Sources: [US Order Types](https://docs.polymarket.us/learn/trading/basics/order-types.md); [US changelog](https://docs.polymarket.us/changelog)
- RFQs and combos are open to all Retail API users with existing keys (1 Oct 2026). Source: [US changelog](https://docs.polymarket.us/changelog)

### Inferences
- Polymarket US is the only Polymarket API a US-based trader could legally use. Its retail API is close to Kalshi's model (signed REST plus WebSocket, USD funding), so the bot's venue layer could be adapted with modest work. Key differences: header-signed auth, fractional contracts, 0.01 tick, and no documented post-only flag on retail.

### Gaps
- It could not be confirmed whether the Polymarket US Retail API offers post-only or FOK, or whether retail users can get FIX or gRPC access.
- The exact Polymarket US key-creation flow (app versus polymarket.us/developer) was not verified on an official page.

## 6. Latency: pass/fail criterion (benchmark: Kalshi, REST orders plus a WebSocket for prices and fills)

### Takeaway
- **International Polymarket: FAIL** for a US-based trader. It is legally closed to US residents for new orders. Even on the technology alone it would be slower than Kalshi from a US host: primary servers are in **London (eu-west-2)**, and crypto markets carry a **150 ms taker speed bump**. Streaming is fine: there are push WebSockets for the book and your own fills.
- **Polymarket US: UNCLEAR, leaning PASS.** It has push WebSockets for the full book, trades and your own orders/positions; REST order entry; FIX and gRPC for institutions; a centralized exchange with no blockchain step; and no documented taker delay. But it publishes no order round-trip times, matching-engine location or hosting region. Its docs also describe a 5-second "latency stopgap" for overload periods.

### Cited findings
**International: streaming**
- Market WebSocket `wss://ws-subscriptions-clob.polymarket.com/ws/market` (no auth). Messages: `book`, `price_change`, `last_trade_price`, `tick_size_change`, plus optional `best_bid_ask`, `new_market` and `market_resolved`. The client sends PING every 10 s. Source: [Real-Time Data](https://docs.polymarket.com/market-data/realtime-data.md)
- User WebSocket `wss://ws-subscriptions-clob.polymarket.com/ws/user` sends `order` events (placement, update, cancel) and `trade` events. Trade statuses are MATCHED → MINED → CONFIRMED, plus RETRYING, FAILED and MATCHED_NOT_BROADCASTED. Missed messages are not replayed after a reconnect. Event timestamps are in milliseconds. Source: [Real-Time Order Updates](https://docs.polymarket.com/trading/realtime-order-updates.md)
- Reference prices (Chainlink, TWAP, equity) come from **PolyBolt** at `wss://ws-live-v2.polymarket.com/ws` (authenticated; launched 15 Sep 2026; the older RTDS feed is now legacy). Equity feeds update "up to five times per second". Since 2 Oct, `price.crypto` defaults to Chainlink. Sources: [Real-Time Data](https://docs.polymarket.com/market-data/realtime-data.md); [changelog](https://docs.polymarket.com/changelog/changelog)
- The Markets channel subscription limit of 100 tokens was removed in May 2025. Source: [changelog](https://docs.polymarket.com/changelog/changelog)

**International: order entry, matching, hosting**
- Orders are signed off-chain (EIP-712) and matched by the CLOB. "Settlement happens asynchronously after an order matches," on-chain on Polygon. Source: [Place Orders](https://docs.polymarket.com/trading/place-orders.md)
- Since 24 Jul 2026 (the "async commit pipeline"), POST /order returns `tradeIDs` rather than transaction hashes on FAK/FOK matches, so the order response no longer waits for the blockchain. Source: [changelog](https://docs.polymarket.com/changelog/changelog)
- Polygon PoS has 1-2 s block times and 2-5 s deterministic finality (Heimdall v2). This affects only settlement of matched trades, not order acknowledgement. Sources: [Polygon docs](https://docs.polygon.technology/pos/concepts/finality/finality); [Giugliano hardfork, Apr 2026](https://usethebitcoin.com/news/polygon-giugliano-hardfork-goes-live/)
- "Primary servers" run in **eu-west-2**; the closest non-restricted region is eu-west-1. Co-location in eu-west-2 is available after a KYC/KYB form to "market makers and individual traders operating on their own account", but not to Builder Program apps. Source: [Geoblock page](https://docs.polymarket.com/developers/CLOB/geoblock). An independent check through Cloudflare also concluded AWS eu-west-2 (London). Source: [X @fulldecent](https://x.com/fulldecent/status/2043928173620945299)
- A developer measured `clob.polymarket.com` from five regions (p50 time-to-first-byte): Amsterdam ~6 ms, London ~19 ms, **US-East (Virginia) ~110 ms** (TCP connect ~90 ms), Singapore ~195 ms. Caveats: this was a GET of `/`, not order placement; the Amsterdam result probably reflects a CDN edge; and the author sells a bot. Source: [dev.to latency test](https://dev.to/bluewhale-quant-lab/i-measured-polymarkets-api-latency-from-5-regions-heres-the-script-and-the-results-3mjm)

**International: built-in delays (the taker speed bump on crypto markets)**
- History: an undocumented ~500 ms taker delay was reportedly removed about 18 Feb 2026 (rumour). A 250 ms delay was reported rolling out from about 5 Jun 2026. Polymarket Devs announced a cut from **250 ms to 50 ms on 17 Aug 2026**. The changelog then records it rising **from 50 ms to 150 ms on 4 Sep 2026, 14:00 UTC**, which is the latest official value. Sources: [X @k1rallik](https://x.com/k1rallik/status/2024191701599080828); [X @sandmark_news](https://x.com/sandmark_news/status/2062118463813157315); [X @PolymarketDevs](https://x.com/PolymarketDevs/status/2089295325660172578); [changelog](https://docs.polymarket.com/changelog/changelog)
- Delayed orders return status `delayed`, tied to the market's `secondsDelay`. Source: [Place Orders](https://docs.polymarket.com/trading/place-orders.md)
- Oracle versus window: settlement uses a 60-second Chainlink TWAP for 5m, 15m and 4h windows (section 2). Source: [changelog](https://docs.polymarket.com/changelog/changelog)

**International: rate limits and FIX**
- POST /order: 500/s burst and 80/s sustained (8 Apr 2026), raised to 200/s sustained on 1 Jun 2026, with POST /orders at 200/s burst. Batch of up to 15 orders. DELETE /orders up to 1,000 IDs. Source: [changelog](https://docs.polymarket.com/changelog/changelog)
- No FIX interface was found in the international docs index. Source: [docs index](https://docs.polymarket.com/llms.txt)

**Polymarket US**
- Retail WebSockets: `/v1/ws/markets` sends MARKET_DATA ("full order book and market stats"), MARKET_DATA_LITE and TRADE. `/v1/ws/private` sends ORDER, POSITION and ACCOUNT_BALANCE updates, delivered in sequence with heartbeats. No update-frequency figures are given. Source: [US WebSocket overview](https://docs.polymarket.us/api-reference/websocket/overview.md)
- Retail rate limits: **25 requests/s** shared across most endpoints. HTTP 429 responses mean back off for at least 1 s. "During high latency, new orders and cancel/replace modifications are rejected if not processed within 5 seconds" with "Global Rate Limit Exceeded". This is not a true rate limit; pure cancels are exempt. Source: [US API rate limits](https://docs.polymarket.us/api-reference/rate-limits.md)
- Institutional limits: FIX order entry runs 35 / 150 / 300 / 500 messages/s per session (tiers 1-4, set by volume share). REST/gRPC `InsertOrder` runs 30 / 100 / 200 / 400 per second. gRPC allows at most 20 streams per firm. Public REST allows 20 requests/s per IP. Source: [US trader-guide rate limits](https://docs.polymarket.us/trader-guide/rate-limits)
- Exchange API (REST, gRPC, **FIX**) is for DMA participants, ISVs, IBs and FCMs; the Retail API is REST plus WebSocket only. Source: [US API Overview](https://docs.polymarket.us/trader-guide/api-overview)
- Hosting: a VPS vendor says connecting to the US gRPC endpoint takes about one round trip to **AWS us-east-1**. This is unverified and the source is commercial. Source: [TradingVPS](https://tradingvps.io/polymarket-us-api-trading-how-it-works-automation-vps-setup/) (search summary)
- Settlement index BRTI publishes once per second; settlement is a 60-second average. Source: [US Crypto FAQs](https://docs.polymarket.us/faqs/crypto-faqs.md)
- Weekly maintenance runs Thursdays 2:00-6:00 AM ET, and Up/Down windows that overlap maintenance are not listed. Sources: [US changelog](https://docs.polymarket.us/changelog); [US Crypto FAQs](https://docs.polymarket.us/faqs/crypto-faqs.md)

**Kalshi benchmark (for comparison)**
- Kalshi offers REST plus a WebSocket for market data and fills, and **FIX 4.4** (TLS required) for order entry. Sources: [Kalshi FIX connectivity](https://docs.kalshi.com/fix/connectivity); [Zuplo guide](https://zuplo.com/learning-center/kalshi-api.md)

### Inferences
- **International versus Kalshi: slower.** From a US-East host, the round trip is about 90-110 ms to the CLOB plus a 150 ms taker delay, so at least ~250 ms before a taker order can match, against Kalshi's US-hosted REST. Streaming parity is fine. Nothing in the order path waits on the blockchain anymore; only settlement does, at 2-5 s Polygon finality. The verdict is **FAIL** on legal access alone, and the latency profile does not change that.
- **Polymarket US versus Kalshi: probably similar.** The setup is the same (REST orders, push WebSocket for book and own orders, FIX for institutions), with a centralized order book, USD collateral, no blockchain step, and no documented taker delay. Retail REST is capped at 25 req/s, which is ample for a bot entering a few orders per window. The verdict stays **UNCLEAR, leaning PASS** until order-acknowledgement time and WebSocket fill latency are measured from a US host. Watch for the 5-second overload rejects during volatile periods.
- Polymarket US's MARKET_DATA message carries the "full order book". If it is a full snapshot rather than incremental updates, message size and parse time could matter. Not documented.

### Gaps
- Neither venue publishes order round-trip or matching-engine latency. No independent measurement of Polymarket US order-acknowledgement latency was found.
- Polymarket US's hosting region and colocation offering are not documented officially.
- It could not be confirmed whether Polymarket US applies any taker delay or speed bump to its crypto markets. None is documented.
- Update frequency and conflation (bundling of several book changes into one message) on either venue's book WebSocket are not documented.

## 7. US legality and access

### Takeaway
A US resident may legally trade only on **Polymarket US**. It is a CFTC-designated exchange (formerly QCEX), funded in USD, with ID-based KYC (identity checks), 18+ only, and some states restricted or contested (Nevada is the clearest exclusion; New York sued on 24 Sep 2026). The **international site blocks new US orders** on both the website and the API. Getting around the block (e.g. by VPN) is not an option and is not covered here.

### Cited findings
- International geoblock: "United States (US)" and US Minor Outlying Islands are **close-only on both frontend and API**: existing positions can be closed but no new positions opened. "Orders submitted from blocked regions will be rejected." Source: [Polymarket Geographic Restrictions](https://docs.polymarket.com/developers/CLOB/geoblock)
- Polymarket bought QCEX (QCX LLC), a CFTC-licensed exchange and clearinghouse, for $112M in Jul 2025. The CFTC issued an amended order of designation in late Nov 2025 allowing intermediated access through FCMs and brokers. Sources: [Crypto Briefing](https://cryptobriefing.com/polymarket-secures-cftc-nod-us-market-qcx-llc-acquisition-2/); [Bitget Academy](https://www.bitget.com/academy/polymarket-secures-cftc-approval-for-regulated-us-prediction-market-news) (search summaries)
- The US app rolled out to select (waitlisted) users in early Dec 2025, starting with sports. Source: [Bitcoin Magazine](https://bitcoinmagazine.com/markets/polymarket-rolls-out-us-app)
- The waitlist was reportedly dropped in May 2026. Access is on iOS, Android and web (web in beta), and government-ID KYC replaced the earlier wallet-only setup. These are secondary sources. Sources: [StartPolymarket](https://startpolymarket.com/countries/united-states/); [launchpoly](https://launchpoly.com/blog/is-polymarket-legal-us-2026)
- Funding is USD: ACH via Aeropay, or card/Apple Pay via Checkout. Source: [US API Overview](https://docs.polymarket.us/trader-guide/api-overview)
- **States (sources conflict):** Nevada is the most consistently reported exclusion; the App Store listing reportedly says trading is unavailable there. An October 2026 guide lists AZ, IL, MA, MD, MI, MT, NV and OH as blocked. Other guides say all states except Nevada. Minnesota's ban, signed May 2026, was enjoined by a federal court on 27 Jul 2026. The CFTC sued Arizona, Connecticut and Illinois on 2 Apr 2026. Sources: [OddsAssist](https://oddsassist.com/prediction-markets/polymarket-us-states/); [Lines.com](https://www.lines.com/guides/u-s-prediction-market-legal-status-state-by-state); [Saturday Down South](https://www.saturdaydownsouth.com/prediction-markets/polymarket-promo-code/legal-states/) (search summaries)
- New York sued Polymarket US two days after the 15-minute BTC launch, alleging an unlicensed gambling business; the complaint does not name the BTC product. Source: [Yahoo Finance](https://finance.yahoo.com/markets/crypto/articles/polymarket-rolls-bitcoin-bets-every-135006140.html)
- The official "Trading Restrictions" page covers only insider and conflict rules. It gives **no state list**, no age rule and no automated-trading rule. Source: [US Trading Restrictions](https://docs.polymarket.us/learn/trading/access-and-limits/trading-restrictions.md)

### Inferences
- The legal route is a Polymarket US retail account in an eligible state, using the Retail API. State-level risk, meaning sudden geofencing after a court ruling, is higher than on Kalshi only to the extent that the states target both venues. Both are CFTC-regulated exchanges facing similar suits.

### Gaps
- No official Polymarket US list of excluded states was found. Check the app's terms or eligibility screen for a given state.
- No official Polymarket US statement on whether automated or API trading has any extra eligibility rules beyond KYC was found.

## 8. Calibration, favourite-longshot bias, and late-favourite profitability

### Takeaway
The only study specific to short-term crypto (5-minute markets, 16 days) finds prices **well calibrated, including in the extreme tails**, to within about 1 percentage point. An apparent favourite-longshot bias (favourites winning more often than their price implies) disappears once correlated trades are handled correctly. Across all Polymarket crypto markets, buying at 90¢ or more returned about **+0.5-0.6% before fees** (2022 to Mar 2026). That is about the same size as the 0.35-0.70% taker fee at 90-95¢. No published study measures late-window favourite buying on these markets net of fees.

### Cited findings
- Gruener, "Calibrated but Not Sharp: Stated Probabilities in Five-Minute Crypto Markets on Polymarket" (SSRN, Jun 2026): about 14,800 five-minute contracts (BTC, ETH, SOL, DOGE) over 16 days, priced about one minute before close. Stated probabilities match outcomes "to within about one percentage point across the range, including in the extreme tails". The calibration slope (realized frequency regressed on price) is about 1.01. A larger, selected set of about 209k trades shows a favourite-longshot bias only when trades are wrongly treated as independent; it "vanishes under dependence-robust inference". A costless "which side is ahead at the snapshot" rule calls direction about 81% of the time against the market's 64%; this is a discrimination measure, not a profit test. Source: [SSRN 6863546](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6863546). The page returned 403 when fetched, so these details come from the abstract via search summaries.
- Cardozo & Rivero-Wildemauwe, "The Favorite-Longshot Bias in Prediction Markets: Evidence from Polymarket" (arXiv, 11 Sep 2026): about 588M trades, Nov 2022 to 29 Mar 2026, hold-to-resolution returns. In **Crypto**, favourites (≥ 90¢) returned **+0.643%** (equal-weighted by market) and **+0.537%** (dollar-weighted), while longshots (< 10¢) lost 14.8% and 12.6%. In the favourite tail overall, realized win frequency exceeds price by +0.27 to +0.82 percentage points. **Fees and rewards are excluded**, and there is no breakdown for 5m, 15m or other short-duration markets or for 90-99¢ alone. Source: [arXiv 2609.12878](https://arxiv.org/html/2609.12878v1)
- UpDownCharts: Polymarket's 15-minute BTC closed "Up" in 50% of 8,639 windows over 90 days, which is a base rate, not calibration. Source: [UpDownCharts](https://www.updowncharts.com/markets/bitcoin) (search summary)
- General Polymarket calibration repositories find slopes about 1.00-1.13, a mild favourite-longshot bias that is "not reliably tradable after costs". These are not specific to short-term crypto. Sources: [honest-odds](https://github.com/CH4RL3I/honest-odds); [wisdom-of-the-paid-crowd](https://github.com/dilaracgrl/wisdom-of-the-paid-crowd) (search summaries)
- An analysis of 377,736 graded wallets: win rate means nothing without entry price, and the median wallet's win rate roughly equals its price-implied probability. Source: [OVERROUND](https://www.overround.pro/guides/polymarket-win-rate)
- "The 1% problem" (Feb 2026, data 2021-2024): favourites priced 70-100% "beat expectations by 12.3 percentage points". This is not specific to short-term crypto, and the method is unclear, so treat it with caution. Source: [Delta Confidence](https://deltaconfidence.substack.com/p/the-1-problem)

### Inferences
- With the computed fees, break-even win rates are about 90.63%, 95.33% and 99.07% at 90¢, 95¢ and 99¢. The best available evidence (5-minute markets calibrated within ~1 pp; crypto favourites +0.5-0.6% before fees) suggests a **thin edge at best after taker fees on Polymarket**, similar to Kalshi's fee drag. Any edge would have to come from timing or selection, not from a structural mispricing of favourites.
- Polymarket's 60-second TWAP settlement (and BRTI averaging on the US venue) means a late-window favourite's outcome is partly locked in over the last minute. That should push calibration near expiry toward the price; the 5-minute study is consistent with this.

### Gaps
- No published study measures win rate versus price for 90-99¢ entries partway through 15-minute windows on Polymarket, on either venue, net of fees.
- No calibration study exists yet for Polymarket US's BRTI-settled BTC 15-minute markets, which are only three weeks old.
