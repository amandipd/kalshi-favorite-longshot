# Practitioner strategies, competition and edges on Kalshi and Polymarket short-dated crypto up/down markets

Research date: 2026-10-09. Evidence labels used below:
- **[primary]**: the exchange's own docs, regulatory filings, or a named-outlet news report with specific figures.
- **[study]**: a named academic or data study (sometimes reported second-hand).
- **[self-reported]**: an individual developer's or trader's own unaudited numbers.
- **[vendor]**: a site that sells bots, data or tools. Treat it as marketing.
- **[secondary/unverified]**: an aggregator or crypto-news repost with no primary record behind it.

Reddit could not be searched, so first-hand r/Kalshi and r/Polymarket threads are missing. Community sentiment below comes from blogs, DEV posts, Substack, and news pieces that quote traders and the Kalshi #crypto Discord.

## 1. What open-source bots and strategy writeups exist, and what do they do?

### Takeaway
Public Kalshi and Polymarket up/down bots fall into six types:
1. Late-window "settlement rider" or favorite entries.
2. Spot-vs-book fair-value models (GBM, Black-style, or multi-signal).
3. Both-sides pair arbitrage (YES + NO bought for under $1).
4. Arbitrage between Kalshi and Polymarket.
5. Momentum and mean reversion.
6. A few market-making modules.

Almost none publish audited live results. The best-documented operator of a strategy like ours is the Polymarket account "gabigol", which reportedly sweeps 94-99c asks in the last 2 minutes using about $2 clips spread across about 100K markets. It is a high-volume, small-ticket, taker business.

### Cited findings
**Kalshi GitHub bots (all self-described; none publish live P&L)**
- **reedjacobp/kalshi-trading-bot** (KXBTC15M) runs five strategies:
  - "Resolution Rider": the last 90 seconds, when the market strongly favors one side and BTC momentum confirms. Its stated hypothesis is "Final 90 seconds are dominated by settlement momentum."
  - "Favorite-Longshot Bias": fires when YES or NO is above 70c with at least 3 minutes left.
  - A 4-signal consensus, momentum, and mean reversion.
  - Sizing is 0.25x Kelly with a -$50 daily stop. Prices come from Coinbase and the order book from Crypto.com. No backtest or results are given. Source: [reedjacobp/kalshi-trading-bot](https://github.com/reedjacobp/kalshi-trading-bot)
- **hamad-khawaja/kalshi-trading-bot** (BTC/ETH 15-min) has a "Certainty Scalp" (last 3 minutes, implied probability of 85% or more, spot past strike) and a "Settlement Ride" (after minute 10, hold to settlement when the price is far from 0.50).
  - It also runs market making (5c minimum spread on BTC, 8c on ETH), a 16-signal heuristic model built on 33 features (Coinbase/Kraken prices, Kalshi book, Bybit funding and liquidations, Chainlink), and a GBM Monte Carlo.
  - Rules include "No directional trading 6 PM to 5 AM EST (low-volume, consistently unprofitable)" and no entries in the last 60 s.
  - The author's notes say cheap contracts "lose money" and markets are "unpredictable near settlement". No results; 104 commits. Source: [hamad-khawaja/kalshi-trading-bot](https://github.com/hamad-khawaja/kalshi-trading-bot)
- **brandononchain/kalshibot** has three parts:
  - A directional GBM fair value that trades when P(UP) differs from the Kalshi ask by at least 8%, only in the first 10 minutes.
  - Arbitrage against Polymarket when the Polymarket mid exceeds the Kalshi ask by at least 5%.
  - A dual-side YES+NO < $0.98 arbitrage, now disabled because "the two legs are submitted separately and are not atomic."
  - It claims Kalshi reprices with a "3-7 second lag relative to spot movements" and that Kalshi market makers lack spot-exchange low-latency infrastructure. Both claims are unmeasured.
  - Its README warns: "These code changes do not validate profitability"; the backtest is synthetic, not a replay of real books. Source: [brandononchain/kalshibot](https://github.com/brandononchain/kalshibot)
- Other KXBTC15M repos found by search:
  - **nepalanurag/kalshi-btc15m-bot**: RSI/volatility signals, limit orders inside the spread, one fill per window, hold to settlement.
  - **fabricio-sousa/mystic-bot**: a late-window "Done-Deal" entry confirmed by BTC momentum filters, with a stop-loss and a backtest PDF.
  - **Bh-Ayush/Kalshi-CryptoBot**: multi-exchange feeds; claims to be "Risk-averse and profitable", unverified.
  - **DeweyMarco/simple-kalshi-bot**: paper-trades three strategies.
  - **keubanks16/kalshi-bot**: runs on Cloudflare Workers.
  - mystic-bot and Kalshi-CryptoBot returned HTTP 404 when fetched on 2026-10-09, so they are now deleted or private. Sources: [search listing](https://github.com/fabricio-sousa/mystic-bot); [Bh-Ayush](https://github.com/Bh-Ayush/Kalshi-CryptoBot); [nepalanurag](https://github.com/nepalanurag/kalshi-btc15m-bot)

**Polymarket bots and reverse-engineered accounts**
- **"gabigol"** (Polymarket, reverse-engineered from public API data in a DEV post dated Jul 10; year not shown, likely 2026) [self-reported analysis]:
  - Convergence leg: "sweep 94-99¢ asks on the leading side" when 120 s or less remain.
  - Lottery leg: 3-30c underdogs with 60-280 s remaining.
  - Execution is "Taker-heavy (FOK-style clips on best ask)"; median notional about $1.92, max about $19.95, up to 7 buys per second.
  - Reported totals: about $308K cumulative PnL on about $20.6M volume across about 100K markets; about 60% per-market win rate; profit factor about 2.4x.
  - Risks the author lists: fee erosion on tight convergence clips ("rebates matter"), capital lock-up, and "regime shifts as more bots compete." Source: [DEV: Reverse-Engineering gabigol](https://dev.to/fatherson/reverse-engineering-gabigol-high-frequency-crypto-updown-farmer-on-polymarket-d0a)
- **"gabagool"** both-sides pair bots (e.g. strongca22-cpu/gabagool) buy YES when cheap and NO when cheap, so the pair costs under $1. Example: YES at 0.48 plus NO at 0.45 is a $0.93 pair. "Dump-and-hedge" variants buy the side that just dumped, then hedge when the combined cost falls below about 0.95. No verified profitability. Sources: [BrightCoding on gabagool](https://converter.brightcoding.dev/blog/strongca22-cpugabagool-a-polymarket-arbitrage-bot-for-risk-profit-trading); [Medium: Dump-and-Hedge Bot](https://medium.com/@utommy.abs/polymarket-15-minute-dump-and-hedge-bot-89018d7aa8fb)
- **0x8dxd** (Polymarket, Dec 2025-Jan 2026): reportedly turned $313 into roughly $414K-$512K in one month on BTC/ETH/SOL 15-min markets. The method was latency arbitrage: buying the side spot prices had already decided while Polymarket odds still sat near 50:50. The figures disagree between outlets and there is no primary record. [secondary/unverified]. Sources: [MEXC news 417346](https://www.mexc.com/news/417346); [MEXC news 671239](https://www.mexc.com/news/671239)
- **A freelance job spec** (Freelancehunt) asks for a Polymarket bot that enters "30-60 seconds before the closing of the 15-minute candle if the odds at that moment are 99 (0.99 probability) or higher." This shows retail demand for exactly this strategy. It is not evidence of profit. Source: [Freelancehunt listing](https://freelancehunt.com/en/project/torgovyiy-bot-dlya-polymarket/1579852.html)
- **Sellers of bot source code**, e.g. polymtradebot.com at $499, base their claims on reverse-engineering a single account. [vendor]. Source: [polymtradebot.com](https://polymtradebot.com/)

**Writeups with numbers (self-reported)**
- **manja316, DEV, "176 Trades on Polymarket"** (Mar 14; year not shown): 162 wins and 14 losses (92%), net P&L "about $2" over 8 days.
  - Binary arbitrage won 97% at $0.10-0.30 per trade and was "the only strategy that made money."
  - Late momentum was about 80% live versus 95.7% in backtest, with wins up to $2.90 and losses up to -$8.40.
  - "Late snipe" was net negative. Source: [DEV: 176 Trades](https://dev.to/manja316/176-trades-on-polymarket-what-my-bot-actually-made-its-not-what-you-think-3iib)
- **lkto1m, DEV** (5m/15m/1h framework, Jul 6; year not shown): 11,717 trades, 77% win rate, about 75% break-even, average entry "near 75 cents", all-time net only $292.
  - Hard cutoff: no entries after T-90 s.
  - Notes that in the final 10-15 s "MEV/latency-arb bots" take over and "spreads blow out." Source: [DEV: 11,717 trades](https://dev.to/lkto1m/my-polymarket-trading-bot-strategy-across-11717-trades-5m15m1h-framework-explained-3gbl)
- **Late momentum math** (Crypticorn): one author waits until minutes 8-12 and buys the side BTC has moved toward. He notes this is a "1:5.67 risk/reward ratio against you. You need to win 85% of the time just to break even." [vendor-ish blog]. Source: [Crypticorn: Polymarket 5-minute strategy](https://www.crypticorn.com/polymarket-5-minute-strategy/)

### Inferences
- Our minute-8, 90-99.9c favorite buy overlaps directly with at least three public archetypes:
  - reedjacobp's ">70c with ≥3 min left" FLB strategy.
  - hamad-khawaja's "Certainty Scalp" (≥85%, last 3 min, spot past strike).
  - gabigol-style 94-99c sweeps on Polymarket.
  - The public Kalshi versions mostly enter later (last 90 s to 3 min) than our minute 8 (7 min left). So the actors lifting our asks at minute 8 are more likely market makers repricing or model-based fair-value bots than these late-window riders.
- Public bots commonly add four filters we may lack:
  - Spot-past-strike confirmation measured in dollars or volatility units, not just price.
  - Quiet-hours blocks.
  - Distance-from-strike checks.
  - Real-time index proxies built from several exchanges.

### Gaps
- No GitHub repo or writeup found publishes audited live P&L for a Kalshi 15-minute favorite strategy.
- YouTube transcripts and X threads were not reachable in a form that could be cited.
- The mystic-bot backtest PDF could not be fetched because the repo now returns 404.

## 2. What do people report about results, competition and edge decay?

### Takeaway
The near-consensus among practitioners is:
- Pure latency arbitrage on Polymarket was killed in early 2026 by taker fees (Jan) and the removal of the 500 ms taker speed bump (Feb).
- On Kalshi, market makers reprice off the settlement index "within seconds."
- Directional and taker strategies mostly lose after costs. Durable profits sit with makers (rebates and the spread) or with very fast, very high-volume operators.

Self-reported positive results are tiny in dollar terms ($2, $292). The one large one (gabigol, about $308K) runs about 100K markets.

### Cited findings
- **OddsShopper's two-week live test** (real orders, hourly and 15-min Kalshi crypto books) found "no durable value".
  - Market makers "reprice off the same real-time indexes the contracts settle on, within seconds," so gaps close before a human can act.
  - Sniping stale quotes fails, and near-the-money directional calls lose to the 1-2c spread ("the house edge").
  - Conclusion: "the edge in a 15-minute market belongs to the spread, and the spread belongs to the market maker." Dated Oct 10, 2026, probably a timezone artifact relative to today's Oct 9. Source: [OddsShopper: Can You Actually Beat A 15-Minute Market?](https://www.oddsshopper.com/articles/prediction-markets/kalshi-15-minute-markets)
  - This contradicts brandononchain's unmeasured claim of a 3-7 s Kalshi lag. Source: [brandononchain/kalshibot](https://github.com/brandononchain/kalshibot)
- **TurbineFi backtest** (30 days to Apr 29, 2026, Kalshi BTC 15-min): of 4,904 strategies, 102 were profitable (2.1%) and the median return was -14.53%. The run modeled fees, order-book depth caps and next-candle fills.
  - An earlier Apr 20 run with no fees, no liquidity cap and same-candle fills showed 69.5% profitable with a +1.37% median. The cost model accounts for most of the gap.
  - "Panic-fade" was profitable in 93 of 96 variants; mean reversion in 0 of 432.
  - The worst 10 strategies used 2c targets, won 62-63% of trades and lost 75-78%. [vendor]. Source: [TurbineFi](https://www.turbinefi.com/blog/do-automated-trading-bots-make-money-prediction-markets-2026)
- **Polymarket taker fees**: added to 15-minute BTC/ETH/SOL/XRP markets around Jan 6, 2026 to fund daily USDC maker rebates. Fees are highest at 50% and fall toward 0 and 100%. Source: [The Block, Jan 6 2026](https://www.theblock.co/post/384461/polymarket-adds-taker-fees-to-15-minute-crypto-markets-to-fund-liquidity-rebates)
  - Commentary framed this as anti-latency-arb. Source: [Finance Magnates](https://www.financemagnates.com/cryptocurrency/polymarket-introduces-dynamic-fees-to-curb-latency-arbitrage-in-short-term-crypto-markets/)
- **Removal of the 500 ms speed bump** (Protos, Feb 20, 2026): Polymarket quietly removed its 500 ms delay on taker orders in crypto markets. The delay had let market makers adjust quotes before taker orders filled.
  - Trader quotes: "With the speed bump gone, latency is now the only moat," and "Was basically free money before."
  - Possible taker transactions per 5-min window rose from about 600 to "thousands or millions." Source: [Protos](https://protos.com/polymarket-ends-trading-loophole-for-bitcoin-quants/)
- **One maker-side bot after February** (lkto1m): its 7-day EV per trade went $0.031, $0.029, $0.028, then back to $0.031 by early March.
  - "Benchmark bots go silent": wallets that had traded dozens of 5-min markets hourly stopped.
  - The author raised his entry floor from 70c to 72c and added a "competition density check".
  - His view: "Always use limit orders"; maker rebates "made financial sense from the start." [self-reported]. Source: [DEV: February 2026 changed Polymarket](https://dev.to/lkto1m/february-2026-changed-polymarket-forever-heres-what-happened-to-my-bots-numbers-2fi5)
  - Guides published after these rule changes argue that "A profitable bot in 2026 must be a maker bot." [opinion]. Source: [JavaScript in Plain English](https://javascript.plainenglish.io/how-to-build-a-polymarket-trading-bot-in-2026-after-the-new-rules-edition-6dfe61452c85)
- **Maker vs taker on Kalshi** (Jonathan Becker's analysis of 72.1M Kalshi trades and $18.26B volume, as reported):
  - Takers average -1.12% per trade and makers +1.12%.
  - The taker edge was +2.0% in 2022.
  - The optimal mix moved from "60%+ taker" before Oct 2024 to "65-70% maker" after Q4 2024. [study, second-hand]. Source: [Paragraph: 72 million trades](https://paragraph.com/@polymarketwhale/game-theory-on-polymarket-the-5-formulas-tested-on-72-million-trades)
  - The American Prospect cites the same -1.12%/+1.12% split and says it was reversed early on, "before institutional liquidity providers" arrived.
  - A Roosevelt Institute analysis found takers lost $584M from July 2021 to mid-May 2026. Source: [American Prospect, Aug 26 2026](https://prospect.org/2026/08/26/house-always-wins-kalshi-prediction-markets/)
- **Bürgi, Deng & Whelan, "Makers and Takers"** (UCD/CESifo, 300K+ contracts): makers earn higher returns than takers, but both show a favorite-longshot pattern. "High-price contracts yield small positive returns." [study]. Source: [CESifo working paper](https://www.ifo.de/en/cesifo/publications/2025/working-paper/makers-and-takers-economics-kalshi-prediction-market)
- **Scale and fee pool (Bitcoin.com, Oct 7, 2026)**: Kalshi BTC 15-min traded 6.74B contracts in Sept 2026, for about $60.4M in taker fees (Predict Charts estimate). ETH 15-min traded 317M and gold 15-min 539M.
  - In the week to Oct 5, 15-min crypto, commodity and index markets produced $20.4M of Kalshi's $25.1M non-sports fees.
  - The estimates exclude rebates paid to market makers. Source: [Bitcoin.com News](https://news.bitcoin.com/igaming/kalshis-15-minute-gold-bets-top-ether-fast-markets-drive-fees/)
  - In July 2026, 15-min crypto did $4.75B in volume. Crypto rose from under 5% of Kalshi volume earlier in 2026 to 21% on Aug 4. Source: [The Event Horizon, Aug 6 2026](https://nexteventhorizon.substack.com/p/the-15-minute-ification-of-prediction-markets)
- **New retail distribution**: Coinbase launched Kalshi-operated 15-minute and 1-hour up/down markets on 10 assets around Oct 6, 2026, available in every US state except Nevada.
  - Conflict: Bitcoin.com cites a June 2026 newsletter already discussing "Coinbase's 15-minute crypto contracts," so October may be an expansion rather than a first launch. Sources: [DigitalToday citing The Defiant](https://www.digitaltoday.co.kr/en/view/111471/coinbase-launches-ultra-short-term-betting-market-will-bitcoin-rise-or-fall-in-15-minutes); [Bitcoin.com](https://news.bitcoin.com/igaming/kalshis-15-minute-gold-bets-top-ether-fast-markets-drive-fees/)
  - Robinhood also lists "BTC Up or Down - 15 minutes" (event dated Mar 9, 2026). Source: [Robinhood](https://www.robinhood.com/us/en/prediction-markets/crypto/events/btc-up-or-down-15-minutes-mar-09-2026-d07e84ce/)
- **Unverified bot-dominance headlines**: "bots consistently generating $5-10k daily" (KuCoin, undated, no records) and a "98% win rate" bot (Yahoo). [secondary/unverified]. Sources: [KuCoin insight](https://www.kucoin.com/news/insight/BTC/695f8764e781bf0007e01c10); [Yahoo Finance](https://finance.yahoo.com/news/arbitrage-bots-dominate-polymarket-millions-100000888.html)

### Inferences
- "Other traders take the ask before our order arrives" fits the reported picture: market makers and fast bots reprice off the settlement index within seconds.
  - A REST taker order sent after a minute-8 snapshot is structurally late to any stale 90-99c ask.
  - The fix is either more speed (WebSocket-driven, pre-signed, decided before the boundary) or switching to resting maker bids. The literature strongly favors the maker side.
- Taker fees at 90-95c (0.33-0.63c per contract on both venues) are the same size as our edge of a few tenths of a cent. A maker fill at the same price would change the economics more than any signal improvement. This depends on Kalshi's maker fee for these series, which is unresolved (Section 5).
- The Coinbase and Robinhood distribution brings more phone-based retail takers, the "buy when price above X" crowd described in Section 4. That flow is what feeds the favorite-longshot bias, and it may also attract more maker competition.

### Gaps
- No source quantifies bot share of Kalshi 15-min volume or how spreads have changed over time in these markets.
- Coverage of Kalshi-specific edge decay is anecdotal; the Polymarket evidence is better documented.
- Becker's original paper text could not be retrieved; figures come from second-hand reports.

## 3. Who provides liquidity in these markets, and what does that imply for a small retail bot?

### Takeaway
Liquidity on Kalshi comes from four groups:
- Susquehanna, Kalshi's first official market maker since April 2024, with reduced fees and higher position limits.
- Jump Trading, which takes equity in Kalshi and Polymarket in exchange for providing liquidity.
- Kalshi's own affiliate Kalshi Trading.
- Sportsbook operators (Flutter/FanDuel, DraftKings).

Under Kalshi's membership agreement, market makers get fee discounts and rebates, "order protections" and faster data. No source names the specific market makers in the 15-minute crypto books.

### Cited findings
- **Susquehanna (SIG)** became Kalshi's first official market maker under reduced fees and higher position limits, dating from April 2024. One secondary site claims "up to 30 times more depth"; that figure is unverified. Sources: [Tradermath](https://www.tradermath.org/articles/prediction-markets-trading-at-quant-firms); [American Prospect](https://prospect.org/2026/08/26/house-always-wins-kalshi-prediction-markets/)
- **Jump Trading** takes small equity stakes in Kalshi and Polymarket in exchange for liquidity (Bloomberg via CoinDesk, Feb 10, 2026). Its Kalshi stake is reportedly fixed, while its Polymarket stake can grow with the trading capacity it provides.
  - Jump's prediction-markets team is about 20 people. Source: [CoinDesk](https://www.coindesk.com/business/2026/02/10/jump-trading-to-take-small-stakes-in-polymarket-kalshi-bloomberg)
  - Jump doubled that team in July 2026. Source: [American Prospect](https://prospect.org/2026/08/26/house-always-wins-kalshi-prediction-markets/)
- **Kalshi Trading** (Kalshi's affiliate) quotes both sides on many markets. A late-2025 class action alleges it trades against customers.
  - Co-founder Luana Lopes Lara says it "receives no preferential access or treatment", "operates as a separate team", and is "not profitable". Sources: [Bloomberg Law](https://news.bloomberglaw.com/crypto/kalshi-market-maker-bets-against-consumers-lawsuit-alleges); [Yahoo/InGame](https://finance.yahoo.com/news/kalshi-co-founder-says-house-174507266.html)
- **Sportsbook operators**: Flutter (FanDuel) reported $6M of prediction-market market-making revenue in Q2 2026 and expects about $50M for 2026. DraftKings also makes markets. Source: [American Prospect](https://prospect.org/2026/08/26/house-always-wins-kalshi-prediction-markets/)
- **Market-maker perks**: Kalshi's membership agreement gives market makers fee discounts, rebates and revenue shares, plus order protections retail lacks. The agreement says these "tools may give market makers a trading advantage."
  - Market makers also get faster data feeds. Source: [American Prospect](https://prospect.org/2026/08/26/house-always-wins-kalshi-prediction-markets/)
- **Kalshi's institutional order-book feed** (Aug 12, 2026, via DoubleZero Edge): full Level 1 and Level 2 data over dedicated fiber, multicast.
  - Initial markets are sports and crypto perpetuals, not explicitly the 15-min markets. Sources: [The Block](https://theblock.co/news/markets/2026-08-12-kalshi-first-prediction-market-to-stream-full-order-books-via-doublezero-411589); [Crowdfund Insider](https://www.crowdfundinsider.com/2026/08/296623-kalshi-rolls-out-institutional-market-data-feed-via-doublezero-edge/)
- **Rebate programs (conflicting)**:
  - Kalshi's help center lists a Liquidity Incentive Program that scores resting orders every second by size and distance from the best price. It ran Sep 15, 2025 to Sep 1, 2026 and excludes market makers with existing agreements. Source: [Kalshi help: Liquidity Incentive Program](https://help.kalshi.com/incentive-programs/liquidity-incentive-program)
  - In Sept 2026, Kalshi's crypto lead IcoBeast said Kalshi runs "no rebate program for crypto prediction markets" (the perps rebate is separate). Source: [crypto.news, Sep 21 2026](https://crypto.news/kalshi-faces-wash-trading-claims-over-crypto-volume/)
  - These statements conflict with Bitcoin.com's note that fee estimates "exclude rebates Kalshi pays market makers", and with the agreement perks above. Bespoke market-maker agreements are probably not counted as a "program." Source: [Bitcoin.com](https://news.bitcoin.com/igaming/kalshis-15-minute-gold-bets-top-ether-fast-markets-drive-fees/)
- **A self-described market maker in these contracts**: the Bits, Bytes and Bets author (Apr 5, 2026) refers to "myself and the other market makers for these contracts". He prices them with Black-76 on an effective time to expiry that accounts for the TWAP. Source: [Substack: Problems with Probability](https://bitsbytesandbets.substack.com/p/problems-with-probability)
- **Polymarket liquidity**: makers get a 20% rebate of crypto taker fees, and makers are never charged. Source: [Polymarket docs: fees](https://docs.polymarket.com/trading/fees)
  - Polymarket has been recruiting an internal market-making team. Source: [Advisor Perspectives, Dec 2025](https://api.advisorperspectives.com/articles/2025/12/05/polymarket-recruiting-in-house-trades-customers)

### Inferences
- A small retail bot competes with firms that have fee advantages, special order protections and faster data. Taking stale quotes from them is a losing race.
- Our structural opening is the other side of the book: rest bids on the favorite and let the retail takers who chase favorites late, or market makers hedging combos and parlays, hit them.
  - The fee schedule and the risk of being picked off when spot moves against us both need checking.
- Kalshi lists "Combos" built on 15-min markets (kalshi.com/combos/15-min). Market makers who price those combos may hedge in the single-window books and take favorite asks. This is speculative and needs order-flow evidence. Source: [Kalshi combos 15-min page](https://kalshi.com/combos/15-min/15-min)

### Gaps
- No public source names the firms quoting KXBTC15M, ETH, gold or oil 15-min books, or their quoting behavior near expiry (e.g. pulling quotes).
- Whether the Liquidity Incentive Program was extended past Sep 1, 2026, and whether 15-min series were eligible, was not confirmed.

## 4. "Buying 90c+ favorites near expiry": evidence, blowups and risk lessons

### Takeaway
Aggregate Kalshi data supports a mild favorite-longshot bias: high-price contracts return slightly more than $1 per $1, e.g. "$1.02" at 90c. But practitioners warn about three things:
- Buyers of in-the-money binaries are short volatility.
- Taker fees and spread can make the strategy negative-EV even when the mid price is fair.
- Losses cluster in near-strike windows, where late flips are common.

Distance from strike, not contract price alone, best separates safe favorites from flip-prone ones.

### Cited findings
- **Aggregate calibration**: Becker's 72.1M Kalshi trades (as reported) show contracts above 80c win more often than price implies, and "every dollar in 90¢ contracts, you get back $1.02." Contracts at 1c return 43c per dollar to takers. [study, second-hand]. Source: [Paragraph: 72 million trades](https://paragraph.com/@polymarketwhale/game-theory-on-polymarket-the-5-formulas-tested-on-72-million-trades)
  - Bürgi, Deng & Whelan agree that high-price contracts yield "small positive returns." Source: [CESifo](https://www.ifo.de/en/cesifo/publications/2025/working-paper/makers-and-takers-economics-kalshi-prediction-market)
- **The short-volatility critique** ("Problems with Probability", Apr 5, 2026; the author says he makes markets in these contracts):
  - Traders in the Kalshi #crypto Discord run "buy when price above X and time to expiration below T", using market orders from phones.
  - It "makes money on the modal outcome, despite it being ridiculously negative in terms of expected value."
  - Worked example: 95c ask, 94c bid, 2 min left, 60-s TWAP, so the effective time to expiry is about 80 s. The effective cost after the 0.07·P·(1−P) fee is 0.953325.
  - Buyers effectively sell volatility "5-10 vol points below mid market."
  - At 90c the EV is worse, because fees scale with p(1−p).
  - Stop-loss exits cross a second spread at higher fees near 50c.
  - The strategy "relies on persistent and systematic overpricing of vol by multiple vol points."
  - Caveat: the same Substack's linked earlier post is labelled "pure, unfiltered parody". Source: [Substack](https://bitsbytesandbets.substack.com/p/problems-with-probability)
- **Late-flip data** (OddsShopper, "We Checked 200 Windows", Oct 8, 2026):
  - In 200 BTC 15-min windows from Sept 4-6, 31 flipped late. In 23 of those, the losing side was priced at 70c or more two minutes out.
  - "Wide" windows (finishing at least $50 from the line): 5 flips in 754 across seven samples from Sep 4 to Oct 8, each during a BTC move.
  - Examples: a window went from about 1c to 93c in its final 20 s and settled No, with 864-1,281 fills per 10-second bucket in the final 50 s (about 725K contracts). On Oct 7, about 1.63M contracts traded after T-2 min in a flip window.
  - Advice: avoid market orders in the final 2 min, avoid 50c, keep size small. Source: [OddsShopper: Are Kalshi's 15-Minute Bitcoin Markets Rigged?](https://www.oddsshopper.com/articles/prediction-markets/are-kalshi-15-minute-bitcoin-markets-rigged)
- **Settlement manipulation on Polymarket** (Stanford/SMU arXiv study, covered Aug 2026):
  - In 5-min BTC markets, 821 wallets made $8.2M by pushing Binance spot across the strike in the final seconds. 93% of non-market-maker losses fell on retail.
  - In manipulated windows a "near certain" bet was overturned "one time in three."
  - Little evidence was found in 15-min markets; longer windows make pushing costlier.
  - Polymarket moved to Chainlink TWAP settlement on Aug 7, 2026: 30 s for 5-min markets, 60 s for 15-min and 4-hour.
  - A 90% favorite still loses the full stake when flipped. TWAP "raises the cost" but doesn't eliminate manipulation; thin off-hours liquidity makes it cheaper. Sources: [crypto.news](https://crypto.news/polymarket-five-second-exploit-manipulation-twap-fix/); [Bitcoin Magazine](https://bitcoinmagazine.com/news/traders-took-8-2-million-from-polymarkets)
- **Execution blowups**:
  - Two one-legged arbitrage fills each lost $20.75 ($41.50 total), against typical arbitrage profits of $0.10-0.30. "One failed execution cost roughly 100 times the expected arb profit."
  - Lesson: compute the breakeven win rate before coding (about 85% at an 85c entry). Source: [DEV: 176 Trades](https://dev.to/manja316/176-trades-on-polymarket-what-my-bot-actually-made-its-not-what-you-think-3iib)
- **High win rate is not profit**: TurbineFi's worst strategies won 62-63% of trades yet lost 75-78%. [vendor]. Source: [TurbineFi](https://www.turbinefi.com/blog/do-automated-trading-bots-make-money-prediction-markets-2026)
- **Tail risk on near-certain shares**: disputes or black swans can drop 99c shares to 50c or 0, and "there is often no liquidity when this happens." [secondary]. Source: [Cryptonews: Polymarket strategies](https://cryptonews.com/cryptocurrency/polymarket-strategies/)
- **gabigol's 94-99c late sweeps** use about $2 clips across about 100K markets. The author warns that holding both sides "can lead to small win + full loss on the other leg." Source: [DEV: gabigol](https://dev.to/fatherson/reverse-engineering-gabigol-high-frequency-crypto-updown-farmer-on-polymarket-d0a)

### Inferences
- The OddsShopper wide-versus-near split suggests a cheap improvement: filter or size entries by spot distance from strike, scaled by recent volatility and time left (including the 60-s averaging window), rather than by contract price alone.
  - A 95c contract in a near-strike window carries much more flip risk than the price implies.
- Both the Black-76 critique and the FLB data point the same way. The edge exists only if the market overprices volatility at the top of the book, so an independent volatility-based fair value would let the bot skip 90-99c asks that are actually fair or rich.
- Practitioners like gabigol keep tickets tiny and spread across many markets. This is the sensible response to one-loss-wipes-many-wins payoffs: at 97c, one loss erases about 32 wins.
- For metals and energy windows, settlement sources differ: gold settles on Pyth, crypto on CF Benchmarks. Flip and manipulation risk may differ by series and by time of day. Source: [Bitcoin.com](https://news.bitcoin.com/igaming/kalshis-15-minute-gold-bets-top-ether-fast-markets-drive-fees/)

### Gaps
- No public dataset gives flip rates for 90-99c Kalshi favorites at minute 8 specifically. OddsShopper measured at T-2 min with a 70c threshold.
- No Kalshi-specific settlement-manipulation study was found; the evidence is Polymarket 5-min.
- No first-person "I blew up buying 99c favorites on Kalshi 15-min" story was found; Reddit was inaccessible.

## 5. Community tips on Kalshi API quirks, fills, latency, fees and settlement

### Takeaway
The main practical issues are:
- Token-bucket rate limits with no Retry-After headers.
- WebSocket sequence-gap handling.
- `client_order_id` reuse so retries don't duplicate orders.
- Limit orders that cross the book execute as taker.
- Fee rounding up to the cent.
- No native stop-loss orders.
- Spreads widest in the last 2 minutes.
- Settlement on a 60-second average of the CF Benchmarks real-time index, with ties going to Yes.

No settlement dispute for these markets was found; "rigged" complaints trace to near-strike volatility.

### Cited findings
- **Rate limits** (as of Sep 9, 2026), in tokens per second for read/write:

  | Tier | Read | Write |
  |---|---|---|
  | Basic | 200 | 100 |
  | Advanced | 300 | 300 |
  | Expert | 600 | 600 |
  | Premier | 1,000 | 1,000 |
  | Paragon | 2,000 | 2,000 |
  | Prime | 4,000 | 4,000 |
  | Prestige | 10,000 | 8,000 |

  - Most requests cost 10 tokens, so Basic is about 20 reads per second shared across the account.
  - Batch endpoints charge per item: 25 creates cost 250 tokens.
  - A 429 "is not a timed lockout"; there are no `Retry-After` or `X-RateLimit-*` headers.
  - Check your actual tier with `GET /account/limits`. [vendor guide citing docs]. Source: [botforkalshi: rate limits](https://www.botforkalshi.com/blog/kalshi-api-rate-limits)
- **WebSocket and order hygiene** (same source):
  - Sign `GET /trade-api/ws/v2` during the HTTP upgrade.
  - Track `seq` on deltas; on a gap, stop acting on the local book and wait for a fresh snapshot. Kalshi pings about every 10 s.
  - Don't place orders from inside the message handler.
  - Reuse one `client_order_id` across retries, because a timeout can come after Kalshi has accepted the order.
  - Reconcile from the fills endpoint.
  - A crossing limit order executes as a taker. Examples use `good_till_canceled` and `taker_at_cross` self-trade prevention. Source: [botforkalshi](https://www.botforkalshi.com/blog/kalshi-api-rate-limits)
- **Auth and hosts**: RSA-PSS SHA-256 over timestamp + method + path; 401s are usually clock skew. Source: [pm.wiki recipes](https://pm.wiki/id/learn/kalshi-api-python-recipes)
  - Prod is `api.elections.kalshi.com`; demo is `demo-api.kalshi.co`. Source: [hamad-khawaja](https://github.com/hamad-khawaja/kalshi-trading-bot)
  - brandononchain checks settlement at close + 60 s, retries every 30 s, and shuts down on any 401. Source: [brandononchain/kalshibot](https://github.com/brandononchain/kalshibot)
- **Fees**: the Kalshi taker fee is ceil(0.07 × C × P × (1−P)), peaking at 1.75c per contract at 50c.
  - Sources conflict on maker fees: "none for most markets", or "25% of taker" on certain series.
  - Fees "changed repeatedly through 2026." Sources: [defirate](https://defirate.com/?p=3623); [Oddpool](https://www.oddpool.com/research/prediction-market-fees-explained); [Bitcoin.com](https://news.bitcoin.com/igaming/kalshis-15-minute-gold-bets-top-ether-fast-markets-drive-fees/)
  - brandononchain says its 0.07 default "does not cover special fee multipliers." Source: [brandononchain/kalshibot](https://github.com/brandononchain/kalshibot)
  - Polymarket crypto now uses the same form, C × 0.07 × p(1−p): $0.63, $0.33 and $0.07 per 100 shares at 0.90, 0.95 and 0.99. Source: [Polymarket docs](https://docs.polymarket.com/trading/fees)
  - Earlier Polymarket coverage put the 15-min peak around 1.56% (or about 3% of trade value), so the schedule appears to have changed. Sources: [DEV: February 2026](https://dev.to/lkto1m/february-2026-changed-polymarket-forever-heres-what-happened-to-my-bots-numbers-2fi5); [The Block](https://www.theblock.co/post/384461/polymarket-adds-taker-fees-to-15-minute-crypto-markets-to-fund-liquidity-rebates)
- **No stop-loss orders**: "Kalshi doesn't offer stop loss orders (yet)" (Apr 2026), so manual exits cross a second spread. Source: [Substack](https://bitsbytesandbets.substack.com/p/problems-with-probability)
- **Settlement mechanics**:
  - All Kalshi crypto contracts settle on a 60-second average of CF Benchmarks RTIs, which print once per second. Source: [Kalshi help: Crypto Markets](https://help.kalshi.com/markets/popular-markets/crypto-markets)
  - The 15-min BTC contract resolves Yes if the 60-s BRTI average before close is at least the 60-s average before open, so ties go to Yes. Sources: [simplefunctions KXBTC15M contract](https://simplefunctions.dev/markets/KXBTC15M-26APR210930-30); [OddsShopper](https://www.oddsshopper.com/articles/prediction-markets/are-kalshi-15-minute-bitcoin-markets-rigged)
  - OddsShopper found every one of 200 checked windows matched the sign of Kalshi's published settlement value. It did not audit the 60 underlying prints. Source: [OddsShopper](https://www.oddsshopper.com/articles/prediction-markets/are-kalshi-15-minute-bitcoin-markets-rigged)
- **Polymarket oracle quirk**: Binance spot and the Chainlink oracle "can diverge by 0.3-0.5% for 15-30 seconds" in volatile periods. Source: [DEV: 11,717 trades](https://dev.to/lkto1m/my-polymarket-trading-bot-strategy-across-11717-trades-5m15m1h-framework-explained-3gbl)
  - Polymarket "settle[s] against Chainlink", not Binance. Source: [DEV: Chainlink not Binance](https://dev.to/lkto1m/why-my-polymarket-bot-watches-chainlink-not-binance-the-oracle-gap-that-changes-every-close-1e96)
- **Fill quirks on Polymarket**: FOK orders often fail on the thin underdog side, so detected arbitrage at about $0.02 per share doesn't execute. Source: [DEV: 176 Trades](https://dev.to/manja316/176-trades-on-polymarket-what-my-bot-actually-made-its-not-what-you-think-3iib)

### Inferences
- **Fee rounding surprise.** The Kalshi fee formula is rounded up to the cent per order, so a 1-contract buy at 95c pays 1c instead of the formula's 0.33c, and a 1-contract buy at 99c pays 1c instead of 0.07c. Small, frequent orders can pay several times the nominal fee and wipe out a few-tenths-of-a-cent edge.
  - Larger single orders amortize the rounding. Our bot should audit realized fee per contract against the formula.
- **Fair value should track the settlement index.** Kalshi settles on the multi-exchange CF Benchmarks BRTI, averaged over 60 s. A real-time BRTI proxy, built from its constituent exchanges, gives a closer fair value than a single venue. This is the Kalshi analogue of the Polymarket "watch Chainlink, not Binance" lesson.
- **Losing races is consistent with the rate limits.** At Basic tier (about 10 writes per second), a bot polling REST at minute 8 and then sending a taker order is slow by design.
  - Subscribe to WebSocket order-book deltas and decide on events.
  - Keep pre-built signed requests ready.
  - Or rest maker bids before minute 8.

### Gaps
- No primary Kalshi page confirming the current maker fee (or multiplier) for KXBTC15M or the metals and energy 15-min series was retrieved.
- No measured Kalshi order-entry latency figures were found.
- No documented settlement dispute or appeal for a Kalshi 15-min market was found.
- Launch date discrepancy: the project's working assumption was that Kalshi's 15-min crypto markets launched around mid-2026. But sources show KXBTC15M contracts trading in April 2026, Robinhood listing a Mar 9, 2026 window, and ETH 15-min volume estimated for January 2026. Sources: [simplefunctions](https://simplefunctions.dev/markets/KXBTC15M-26APR210930-30); [Robinhood](https://www.robinhood.com/us/en/prediction-markets/crypto/events/btc-up-or-down-15-minutes-mar-09-2026-d07e84ce/); [Bitcoin.com](https://news.bitcoin.com/igaming/kalshis-15-minute-gold-bets-top-ether-fast-markets-drive-fees/)
  - Gold 15-min first listed Jul 31, 2026, so metals and energy are the mid-2026 launches.
  - Polymarket's 15-min crypto markets were live by Oct 23, 2025. Source: [CoinSpot](https://coinspot.io/en/cryptocurrencies/polymarket-launched-15-minute-crypto-predictions-for-price-rise-or-fall/)
