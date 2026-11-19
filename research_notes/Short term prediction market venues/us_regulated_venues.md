# US-regulated (CFTC) short-term event-contract venues other than Kalshi and Polymarket (state as of October 2026)

Scope: US venues and front ends that list short-dated (5-minute to 1-day) binary or event contracts on crypto, stock indices, FX or commodities. Kalshi is used only as a benchmark. Research date: 13 Oct 2026. Anything dated before 2026 is labelled. Secondary or affiliate sources are flagged.

Verdict legend used below (the project's judgement, not a source claim):
- **Own book**: the venue runs its own CFTC-designated contract market (DCM, a licensed futures exchange) order book for the contract.
- **Router**: a broker or app front end that sends orders to another exchange's book, usually Kalshi's.
- **Latency PASS** means a documented retail programmatic API with order entry plus a push stream (WebSocket, FIX or gRPC) of prices and own fills, sent straight to the exchange, with no known speed bump. **FAIL** means there is no retail API, the venue is app-only, or it is a broker hop in front of Kalshi's book, which makes it slower than Kalshi by construction. **UNCLEAR** means an API exists but key latency facts are missing.

---

## Q1. Which venues run their own order book for short-dated contracts, and which only route to Kalshi?

### Takeaway
As of Oct 2026, only three venues have their own retail-reachable book with sub-daily crypto contracts: **Gemini Titan** (5-min, 15-min, hourly, daily and longer crypto), **Crypto.com Derivatives North America (CDNA, formerly Nadex)** (5-min, 15-min, 1-hour, 4-hour, daily and weekly crypto, plus 20-min, 2-hour and daily index contracts) and **CME** (daily $100 event contracts; hourly $1 contracts sold mainly through FanDuel Predicts). **Coinbase and Webull route to Kalshi.** **Robinhood** is a multi-venue router: Kalshi, ForecastEx, its own Rothera, and now Nadex/CDNA. Its 15-minute BTC contract is a Kalshi contract. DraftKings (DKeX), Underdog (UDX) and Rothera run their own books but are sports-led, with app-only access.

### Cited findings
**Crypto.com / CDNA (formerly Nadex): own book**
- CDNA is the d/b/a of "North American Derivatives Exchange, Inc." In April 2026 it self-certified BTC, ETH, LTC, XRP, BCH, CRO and SOL "Event Contracts" as swaps on the coin's price at a set time. ETH was to list "no later than April 4, 2026". Sources: [CFTC filing, CDNA ETH, 1 Apr 2026](https://www.cftc.gov/sites/default/files/filings/ptc/26/04/ptc04012642983.pdf); [CDNA SOL certification](https://www.cftc.gov/filings/ptc/ptc0411261189.pdf)
- Nadex retired its own Nadex.com platform. The notice says new applications stopped, deposits were suspended on "Friday, Dec 06th, 2025" and trading on Nadex.com was disabled on "Friday, Dec 20th, 2025". Products continue as "Crypto Derivatives" and "Prediction Markets" in the Crypto.com app, "powered by Crypto.com | Derivatives North America (Nadex)." Caveat: the notice's weekday labels fit 2024, not 2025, so the year may be a typo. Source: [Nadex notice](https://origin-website-prod.nadex.com/notices/cdna-transitions-to-crypto-com-app/); a secondary source repeats "Binary options trades were disabled on the platform on 20 December 2025" (updated 10 Jun 2026). Source: [binaryoptions.net](https://www.binaryoptions.net/nadex)
- Crypto.com also runs "OG", a predictions-only app on the same CFTC-registered exchange and clearinghouse, launched Feb 2026. Sources: [SBC Americas, 3 Feb 2026](https://sbcamericas.com/2026/02/03/cryptocom-prediction-market-platform-og/); [Bloomberg Government](https://news.bgov.com/crypto/crypto-com-launches-predictions-only-platform-before-super-bowl)
- CDNA white-labels its exchange to others: Underdog (earlier sports markets), Fanatics Markets, Truth Predict, High Roller, and Prospect Markets (Sep 2026). Sources: [Prediction News](https://predictionnews.com/story/prospect-markets-signs-deal-with-og-prediction-markets-and-crypto-com-for-us-spo); [SBC Americas](https://sbcamericas.com/2026/02/03/cryptocom-prediction-market-platform-og/)

**Robinhood: router to several venues, including its own Rothera JV**
- Robinhood's event contracts are offered by Robinhood Derivatives, LLC "through either KalshiEX LLC, ForecastEX, LLC, Rothera Exchange and Clearing LLC, or North American Derivatives Exchange, Inc." Sources: [Robinhood support](https://www.robinhood.com/us/en/support/articles/robinhood-event-contracts/); same text on the [Robinhood BTC 15-min page, 13 Oct 2026](https://robinhood.com/us/en/prediction-markets/crypto/events/btc-15-min-83-13207-target-oct-13-2026/)
- The Robinhood "BTC 15 min" contract (13 Oct 2026, 1:45-2:00 PM EDT) settles on CF Benchmarks' BRTI (Bitcoin Real Time Index). It resolves Yes if the 60-second BRTI average before 2:00 PM is at least the 60-second average before 1:45 PM. Its terms link points to a Kalshi PDF. Trading runs "24 hours a day, except Thursday 3AM-5AM ET". Source: [Robinhood contract page](https://robinhood.com/us/en/prediction-markets/crypto/events/btc-15-min-83-13207-target-oct-13-2026/)
- Rothera history: Robinhood and Susquehanna announced the JV in Nov 2025, bought MIAXdx in Jan 2026, renamed it Rothera, and launched it in late May / early June 2026 with World Cup and baseball contracts. Sources: [CNBC, 5 Jun 2026](https://www.cnbc.com/2026/06/05/deutsche-bank-says-robinhoods-prediction-market-could-boost-its-stock.html); [Robinhood newsroom](https://robinhood.com/us/en/newsroom/the-world-cup-is-now-trading-on-robinhood-and-rothera/); [Finimize](https://finimize.com/content/robinhood-and-susquehanna-quietly-built-a-new-prediction-market-venue)
- Rothera works only through FCMs (futures commission merchants, the brokers that hold customer accounts). Under its "FCM-intermediated participant model … Customers interact with the Company exclusively through an FCM Participant". Source: [Rothera fee filing, 5 May 2026](https://cdn.prod.website-files.com/69a0b2d56634068be7fbbf2a/69fa6d5e7f1440875b946a71_20260505%20-%20Rothera%20Fee%20Schedule%20Filing.pdf)
- Robinhood says Rothera will take "most, but far from all" of its flow, and the CEO says customers should be "routed to where they would get the best value". Source: [InGame](https://www.ingame.com/robinhood-rothera-earnings-call/). Rothera's digital-asset event contracts are described only as planned (secondary). Source: [Coingape](https://coingape.com/block-of-fame/pulse/rothera-robinhoods-prediction-market-empire-is-quietly-taking-shape/)
- In July 2026 Robinhood was reported to be in talks to add Crypto.com contracts (WSJ via The Block). Source: [The Block](https://www.theblock.co/post/409665). The Defiant reports that Robinhood took stakes in Crypto.com and OG.com and routes football contracts there; this could not be dated or corroborated. Source: [The Defiant](https://thedefiant.io/news/tradfi-and-fintech/robinhood-takes-stakes-in-crypto-com-and-og-com-as-it-routes-football-contracts)

**Coinbase: router to Kalshi**
- Coinbase launched prediction markets in all 50 states in late Jan 2026 with Kalshi. It "will source its order flow from Kalshi," the same model as Robinhood. Source: [CoinDesk, 27 Jan 2026](https://www.coindesk.com/markets/2026/01/27/coinbase-rolls-out-prediction-market-to-u-s-customers)
- Coinbase added short-dated up-or-down contracts on BTC, ETH and 8 other tokens. "Kalshi lists the contracts and already runs the same 15-minute markets on its own exchange" (undated). Source: [The Defiant](https://thedefiant.io/news/defi/coinbase-launches-15-minute-and-hourly-crypto-price-markets)
- Coinbase agreed in Dec 2025 to buy The Clearing Company, an applicant to become a DCO (derivatives clearing organization, a clearinghouse). Source: [Bloomberg Gov, 22 Dec 2025](https://news.bgov.com/mergers-and-acquisitions/coinbase-acquires-the-clearing-company-in-prediction-market-push). A single secondary source claims Coinbase now lays its own "crypto binaries" over Kalshi's menu. No Coinbase Derivatives self-certification for event or binary contracts was found. Source: [laikalabs (secondary, unverified)](https://laikalabs.ai/prediction-markets/coinbase-prediction-markets)

**Webull: router to Kalshi**
- Webull added Kalshi's hourly BTC and ETH contracts (above/below) for US users in June 2025 (2025, older). Sources: [Webull news](https://www.webull.com/news/12966524716819456); [FX News Group](https://fxnewsgroup.com/forex-news/cryptocurrency/webull-adds-kalshis-cryptocurrency-hourly-contracts-to-list-of-trading-instruments/)

**Interactive Brokers ForecastEx / ForecastTrader: own book (IBKR affiliate), no short-dated crypto found**
- ForecastEx LLC is "both the exchange that lists the product and the clearinghouse." Contracts must be bought through a ForecastEx member. Source: [ForecastEx KID, 10 Sep 2025](https://data.forecastex.com/regulatory/KIDS/ForecastExKeyInformationDocument.pdf)
- The only BTC contract found was year-end: "Will Bitcoin's price exceed $85,000 on December 31, 2025 at 4pm CT" (Nov 2025). Source: [IBKR Campus](https://www.interactivebrokers.eu/campus/traders-insight/forecastex-experiences-active-trading-weekend-nov-24-2025/)

**CME Group: own book (Globex), two product lines**
- (a) **Legacy CME event contracts** on futures: daily expiry, $100 payout, priced $1-$99, max order 250 contracts. The BTC version settles on the CME CF BRR daily settlement. Sources: [IBKR TWS API docs](https://www.interactivebrokers.com/docs/tws-api/doc/event-trading/introduction/cme-event-contracts); [CME spec page](https://cmegroup.com/activetrader/event-contracts/contract-specifications-for-event-contracts.html); [CF Benchmarks](https://www.cfbenchmarks.com/blog/cme-btc-event-contracts-simplified-access-to-the-brr-liquidity-complex). A 2023 filing had a $20 BTC version (2023, outdated).
- (b) **CME-FanDuel "FanDuel Predicts"** launched 22 Dec 2025 in 5 states. Contracts are priced $0.01-$0.99, with financial contracts (S&P 500, Nasdaq-100, oil, gas, gold, crypto, GDP, CPI) "in all 50 states". Sources: [CME press release, 22 Dec 2025](https://www.cmegroup.com/media-room/press-releases/2025/12/22/fanduel-and-cme-group-launch-fanduel-predicts.html); [DeFi Rate](https://defirate.com/?p=3025)
- CME's CEO described roughly 60-minute contracts, "three events a day for gold, three events a day for crude oil, three events a day for the S&P 500, for treasuries," five days a week (Oct 2025, pre-launch). Source: [InGame, 2 Oct 2025](https://www.ingame.com/fanduel-cme-prediction-platform-microbetting-hourly/)
- Aug 2026: FanDuel moved sports and novelty contracts to Crypto.com. "Financial derivatives remain with CME, including contracts tied to major equity indexes". Sources: [Casino.org, 6 Aug 2026](https://www.casino.org/news/fanduel-moving-sports-event-contracts-to-crypto-com/); [Bloomberg, 5 Aug 2026](https://www.bloomberg.com/news/articles/2026-08-05/cme-fanduel-venture-falters-as-prediction-startups-race-ahead); [Sportico](https://www.sportico.com/business/sports-betting/2026/fanduel-cme-prediction-market-crypto-nadex-1234941188/)

**Gemini (Gemini Titan DCM): own book**
- Gemini Predictions went live 15 Dec 2025 on its own CFTC-licensed exchange (Gemini Titan). Source: [Gemini blog](https://www.gemini.com/blog/gemini-predictions-tm-is-now-live). Since April 2026 it has cleared through its own clearinghouse (secondary). Sources: [PredictMarkets](https://predictmarkets.com/gemini-predictions/); [DeFi Rate](https://defirate.com/?p=18415)

**DraftKings (Railbird → DKeX): own book since June 2026**
- DraftKings bought Railbird, a CFTC DCM, in Oct 2025 and launched DKeX on 26 Jun 2026. Before that it routed through CME and Crypto.com. Sources: [Las Vegas Sun, 26 Jun 2026](https://lasvegassun.com/news/2026/jun/26/draftkings-launches-proprietary-exchange-to-bolste/); [The Block](https://www.theblock.co/amp/post/406375/draftkings-launches-own-prediction-markets-exchange-consumer-volume-exceeds-3-billion)
- One review says the app offers "financial prediction markets featuring CME E-mini S&P 500 and CME E-mini Nasdaq futures" and BTC/ETH price-level contracts. It is an affiliate source, and it doesn't say which exchange lists them. Source: [SailGP guide](https://sailgp.com/prediction-markets/draftkings-predict)

**Underdog / PrizePicks / Truth Predict**
- Underdog bought Aristotle Exchange, a CFTC DCM, in March 2026 and launched its in-house UDX in July 2026. It added Kalshi contracts in April 2026; its earlier sports markets ran on Crypto.com. Source: [SBC Americas, 20 Jul 2026](https://sbcamericas.com/2026/07/20/underdog-prediction-market-exchange/)
- PrizePicks prediction markets run on Kalshi's exchange. Source: [Legal Sports Report](https://www.legalsportsreport.com/prediction-markets/underdog-predict-vs-prizepicks-predict/)
- Truth Predict (Trump Media) runs on CDNA. As of July 2026 it was still in testing, and a Feb 2026 SEC filing said the company was "still evaluating whether the prediction market is economically feasible". Sources: [Action Network, Jul 2026](https://www.actionnetwork.com/online-sports-betting/reviews/truth-predict); [The Block, Oct 2025](https://www.theblock.co/post/376547/trump-backed-truth-social-jumps-into-prediction-markets-with-crypto-com)

**Not CFTC, but relevant: Cboe Predicts (SEC-regulated)**
- Launched 23 Jun 2026 as binary options on the Mini-S&P 500 (XSP), symbols XSPBW and XSPBX, paying $100 or $0. Only 0-day and 1-day expiries; cleared by OCC; first broker Interactive Brokers, with Schwab to follow. Sources: [Cboe IR](https://ir.cboe.com/news/news-details/2026/Cboe-Introduces-Cboe-Predicts-Launching-First-Products-in-New-Prediction-Markets-Suite/); [The Block](https://theblock.co/post/405930/cboe-launches-prediction-market-suite)

**Newer or pending DCMs (2025-2026)**
- Novig received DCM approval in June 2026 (sports). Source: [SBC Americas](https://sbcamericas.com/2026/06/17/novig-prediction-market-cftc-approval/)
- CNBC (via secondary) reports that the CFTC approved six new DCMs in 2026 and that Blockchain.com (pending) joined 11 other 2026 applicants. K&L Gates counts 12 new DCMs designated since 1 Jan 2025. Sources: [CNBC, 9 Oct 2026](https://www.cnbc.com/2026/10/09/blockchain-com-cftc-prediction-markets.html); [Decrypt](https://decrypt.co/380612/blockchain-cftc-prediction-markets-crypto-derivatives?amp=1); [K&L Gates, 24 Aug 2026](https://www.klgates.com/thought-leadership/2026-Mid-Year-Prediction-Market-Report-Uncertainty-Prevails-Amidst-Extraordinary-Federal-Action-8-24-2026)
- Kraken completed its ~$100M purchase of Small Exchange (a DCM) and "eyes" US prediction markets. No live product was found as of Sep 2026. Source: [iGaming Today, 14 Sep 2026](https://www.igamingtoday.com/kraken-completes-100m-acquisition-of-small-exchanges-eyes-us-prediction-market-entry/)

### Inferences
- Only Gemini, CDNA and CME add genuinely new liquidity and prices for short crypto or index binaries. Coinbase, Webull and PrizePicks are Kalshi front ends, and so is Robinhood for its crypto 15-minute contracts. Their prices are Kalshi's book plus a broker fee.
- Robinhood now spans four venues. Which venue a given contract uses must be checked per contract; the crypto 15-minute contract is Kalshi's (identical rule text, Kalshi terms PDF).
- FanDuel Predicts (CME) is the only route to CME's hourly $1 financial contracts that could be confirmed. CME's own legacy daily $100 event contracts are reachable through ordinary futures brokers (IBKR, NinjaTrader).

### Gaps
- Whether CDNA's crypto Event Contracts in the Crypto.com app use a "price at window start" strike (up/down from open) or fixed strikes for 5-min, 15-min and 1-hour. The spec says "n/a - single strike" for those durations (Q2).
- Which venue lists Robinhood's hourly crypto contracts (if any), and whether any Robinhood crypto contracts route to Rothera or CDNA.
- Whether DKeX lists its own crypto or index contracts, or still sources them elsewhere.
- No official CFTC DCM list was found for an authoritative count of 2026 designations.

---

## Q2. Contract specs: durations, underlyings, strike structure, settlement, tick and payout

### Takeaway
Gemini and CDNA both list 5-minute, 15-minute and hourly crypto contracts with $1 payouts and 1¢ ticks (Gemini's tick is not confirmed). Gemini's short contracts are "UP" (at or above the opening price). CDNA's are single-strike "Strike Options" plus UpDown touch-bracket contracts, settled on a trimmed 60-second average of venue midpoints. CDNA (ex-Nadex) also lists 20-minute and 2-hour contracts on US index futures. CME's daily event contracts pay $100 and settle on futures or BRR settlement prices.

### Cited findings
**Gemini Titan (crypto)**
- Durations offered: 5-minute, 15-minute, hourly, daily, weekly, monthly. Assets: BTC, ETH, XRP, SOL, Zcash. Monthly high/low "touch" contracts were added on 28 Apr 2026. Sources: [Cryptonomist, 28 Apr 2026](https://en.cryptonomist.ch/2026/04/28/bitcoin-predictions-contracts/); [Gemini blog, 28 Apr 2026](https://www.gemini.com/blog/gemini-releases-new-trading-options-for-bitcoin-maxis)
- Ticker documentation: 5-minute (`05M`) and 15-minute (`15M`) contracts are type "UP": "resolves YES if the underlying asset's price is at or above the strike price at expiry." The strike "is the asset's price at the start of the contract window." Daily and longer contracts use `HI{PRICE}`, meaning at or above a fixed strike. Example tickers: `GEMI-BTC05M2602251745-UP`, `GEMI-BTC2603230800-HI105000`. Underlyings in the docs: BTC, ETH, SOL, XRP. Source: [Gemini dev docs](https://developer.gemini.com/prediction-markets/tickers-crypto)
- For up/down contracts the strike value is "null until the strike is captured at availableAt time" (via GET …/events/{eventTicker}/strike). Source: [Gemini dev docs, Markets](https://developer.gemini.com/prediction-markets-spec/markets)
- Settlement index: not named in the docs that could be accessed.

**CDNA / Crypto.com (crypto)**
- Durations: 5 minutes, 15 minutes, 1 hour, 4 hours, daily, weekly. Underlyings: BTC, ETH, LTC, BCH, DOGE, AVAX, LINK, DOT, SHIB, XLM, HBAR, CRO, SOL, ADA, XRP, ONDO, SEI. "Strike Options" have 1 strike ("n/a - single strike") at 5 min, 15 min and 1 hour, and 9 strikes at 4 hours, daily and weekly. BTC strike widths are 200, 500 and 1,000 for those three. Contract value $1, tick 0.01 = $0.01, cash-settled on "Nadex BTC … indices." Trading runs "24/7", opening 4:50 AM ET Saturday. "UpDown Options" (4 contracts each; BTC range $500) "expire early if the floor or ceiling is touched". Source: [nadex.com/crypto (page © 2026)](https://www.nadex.com/crypto/)
- 2026 certification terms: price band $0.01-$0.99, notional $1, tick $0.01; at least one dedicated market maker; position limit 2,500,000 contracts (market makers 25,000,000 per strike). Settlement (Expiration Value) is a per-second index: take all bid/ask midpoints from Lukka or ICE (Blockstream) in the 60 seconds before the calculation time (minimum 25), drop the top and bottom 20%, and average the rest. "Trading will be available at all times outside of any maintenance windows". Source: [CFTC filing, CDNA ETH, 1 Apr 2026](https://www.cftc.gov/sites/default/files/filings/ptc/26/04/ptc04012642983.pdf)
- An older CDNA filing (Apr 2023, possibly outdated) listed intraday 2-hour BTC contracts expiring 8 PM to 4 AM with 9 strikes, and daily BTC contracts expiring 5 PM Mon-Thu. Source: [CFTC filing, 2023](https://www.cftc.gov/sites/default/files/filings/ptc/23/04/ptc041023368.pdf)

**CDNA (ex-Nadex) stock-index event contracts**
- US 500 (CME E-mini S&P), US Tech 100 (E-mini Nasdaq), Wall St 30 (E-mini Dow) and US SmallCap 2000 (E-mini Russell): 20-minute contracts (15 strikes, expiring Mon-Fri 10:00-16:00 ET), 2-hour contracts (15 strikes, hourly 10:00-16:00 plus 17:00 Mon-Thu) and daily contracts (21 strikes, 16:15 ET). US 500 strike widths are 3 / 2 (20-min), 6 (2-hour) and 12 (daily). Tick 0.01 = $0.01; position limit 2,500,000. Source: [nadex.com stock-index specs](https://www.nadex.com/contract-specs-stock-index/)
- Conflict: an undated Nadex learning page still says "your payout amount is $100.00," with durations of "five-minute, twenty-minute, two-hour, daily, and weekly". Source: [Nadex learning page](https://www.nadex.com/learning/how-to-trade-event-contracts/). The $0.01 tick and $0.02 fee (Q3) imply the current contracts are $1.
- The Nadex home page offers "Event contracts" ("Will this market be above this price at this time?") and weekly "Knock-outs" on forex, stock indices and commodities. It does not mention legacy binaries or call spreads. Source: [nadex.com](https://www.nadex.com/)

**Robinhood / Kalshi (benchmark crypto 15-min)**
- Up/down on BRTI: compares the 60-second average at the window end with the 60-second average at the window start; pays $1. The quote displayed in tenths of a cent (bid 0.9¢ / ask 1.0¢). Source: [Robinhood BTC 15-min page](https://robinhood.com/us/en/prediction-markets/crypto/events/btc-15-min-83-13207-target-oct-13-2026/)

**Webull / Kalshi hourly crypto (2025)**
- Hourly BTC and ETH above/below contracts (June 2025). Source: [FX News Group](https://fxnewsgroup.com/forex-news/cryptocurrency/webull-adds-kalshis-cryptocurrency-hourly-contracts-to-list-of-trading-instruments/)

**CME**
- Legacy event contracts: $100 payout, price $1-$99 in $1 increments, daily expiry on the trade date. BTC settles on the daily BRR (CME CF Bitcoin Reference Rate); max order 250. Sources: [IBKR docs](https://www.interactivebrokers.com/docs/tws-api/doc/event-trading/introduction/cme-event-contracts); [CME spec page](https://cmegroup.com/activetrader/event-contracts/contract-specifications-for-event-contracts.html); [CF Benchmarks](https://www.cfbenchmarks.com/blog/cme-btc-event-contracts-simplified-access-to-the-brr-liquidity-complex)
- FanDuel Predicts (CME) contracts: $0.01-$0.99 per $1. Hourly design: about 60 minutes, roughly 3 per day per asset, above/below a level (e.g., gold above $3,700) (Oct 2025 description). Sources: [CME PR, 22 Dec 2025](https://www.cmegroup.com/media-room/press-releases/2025/12/22/fanduel-and-cme-group-launch-fanduel-predicts.html); [InGame, Oct 2025](https://www.ingame.com/fanduel-cme-prediction-platform-microbetting-hourly/)

**ForecastEx**
- Bids $0.02-$0.99. A Yes bid and a No bid are paired when they sum to exactly $1.01; the winner gets $1.00. Positions earn an "Incentive Coupon" (interest at the Effective Fed Funds rate; 4.33% in the example). You exit only by buying the opposite side. Fully collateralised. Source: [ForecastEx KID](https://data.forecastex.com/regulatory/KIDS/ForecastExKeyInformationDocument.pdf)

**Rothera**
- Sports contracts: $1 notional, $0.01 tick, $0.01-$0.99 price band (secondary summary of a filing). Source: [CFTC filing, Oct 2026](https://www.cftc.gov/filings/ptc/ptc10022631096.pdf). Its fee schedule still lists legacy MIAXdx "Binary Range Contracts (including … BTCRB)". Source: [Rothera fee filing](https://cdn.prod.website-files.com/69a0b2d56634068be7fbbf2a/69fa6d5e7f1440875b946a71_20260505%20-%20Rothera%20Fee%20Schedule%20Filing.pdf)

**Cboe XSP binaries (SEC)**
- $100 or $0 payout; Yes pays if XSP settles at or above the strike; 0-day and 1-day expiries only. Source: [The Block](https://theblock.co/post/405930/cboe-launches-prediction-market-suite)

### Inferences
- Gemini's 5-minute and 15-minute "UP" contracts are structurally the closest match to Kalshi's 15-minute up/down. Late in the window they become deep in- or out-of-the-money binaries on whether price stays at or above the opening print.
- CDNA's 5-minute, 15-minute and 1-hour Strike Options also have a single strike, probably set near the price at listing (the "n/a - single strike" spec). CDNA's settlement (trimmed mean of midpoints from Lukka/ICE over 60 seconds) differs from BRTI, so the same move can settle differently than on Kalshi.
- CDNA's US-index 20-minute and 2-hour contracts are the only sub-daily index binaries found at a CFTC venue reachable by retail, apart from FanDuel's hourly CME contracts.

### Gaps
- Gemini's settlement index and source, and its tick size.
- CDNA's live strike-setting rule for the 5-min, 15-min and 1-hour contracts. Whether 5-minute index and FX event contracts still exist after the Dec 2025 platform move.
- Live FanDuel Predicts hourly schedule and settlement source as of Oct 2026.

---

## Q3. Fees per contract, with the cost at 90¢, 95¢ and 99¢ on a $1 payout

### Takeaway
Gemini's fee scales with p×(1−p), the same shape as Kalshi's: a taker pays about 7% of the maximum profit at every price. CDNA's flat $0.02 per contract wipes out favourites: 20% of profit at 90¢, 40% at 95¢, and a guaranteed loss at 99¢. Robinhood adds a capped p×(1−p) commission on top of the exchange fee. DKeX's $0.02 taker fee is as punitive as CDNA's; its makers pay only $0.0025.

### Cited findings
- **Gemini Titan** (contracts listed on or after 18 Mar 2026): "Taker Fee = Taker Rate × C × P × (1 − P)", taker rate 0.07, maker rate 0.0175. "Fees are rounded up to the next cent." "There are no settlement fees." Example: taker, 100 contracts at $0.90 → $0.63. Cancelling maker orders is free. Source: [Gemini fee page](https://www.gemini.com/fees/predictions). Older contracts used maker 0.01 / taker 0.05. Source: [Gemini legacy fee page](https://www.gemini.com/fees/predictions-2026-03-18). Maker rebates are a share of taker fees ("All other markets" 0.30 from 18 Mar 2026), capped at 5% of fill notional and paid daily. Source: [Gemini maker rebate program](https://developer.gemini.com/prediction-markets/maker-rebate-program)
- **CDNA / Nadex**: event contracts carry a "$0.02 trading fee per contract" to enter or exit, with "No settlement fee" whether in or out of the money. Knock-outs cost $1 per contract plus a $1 settlement fee. Source: [nadex.com/pricing](https://www.nadex.com/pricing/). Crypto.com's own page agrees: "For markets that use a $1 contract size, there is a $0.02 trade fee, and no other fees". Source: [Crypto.com Prediction learn page](https://crypto.com/us/prediction/learn/understanding-prediction-event-contract-payout-structure-on-cryptocom). Conflict: an affiliate review cites $0-$0.20 per contract ($0.10 exchange plus $0.10 technology fee), probably for other contract sizes or partner apps. Source: [DeFi Rate](https://defirate.com/prediction-markets/crypto-com/)
- **Robinhood**: the commission is "k × p × (1 − p) × c", with k = 10% (5% with Gold), "capped at $0.01 per contract." The exchange fee "can be up to $0.01 per contract" and varies by venue. Example: 100 contracts at $0.90 → $0.45 (Gold) or $0.90 commission. Source: [Robinhood support](https://www.robinhood.com/us/en/support/articles/robinhood-event-contracts/). Conflict: the 15-min BTC page showed "$0.00 commissions and fees" with "Additional fees apply". Source: [Robinhood BTC 15-min page](https://robinhood.com/us/en/prediction-markets/crypto/events/btc-15-min-83-13207-target-oct-13-2026/)
- **Rothera** (exchange fee behind Robinhood): "Order fees = MAX(round(k × p × (1 − p) × c, 2), 0.01)", with k currently 0.000 for retail, professional and market-maker participants. Rothera may raise k without notice provided the fee stays under $1 per contract. Source: [Rothera fee filing, 5 May 2026](https://cdn.prod.website-files.com/69a0b2d56634068be7fbbf2a/69fa6d5e7f1440875b946a71_20260505%20-%20Rothera%20Fee%20Schedule%20Filing.pdf). Rothera's fees are reported as capped at 1¢ per contract, below "Kalshi's maximum of 2 cents per contract" (secondary). Source: [CLEATZ](https://cleatz.com/rothera-prediction-markets/)
- **ForecastEx**: "ForecastEx collects $1.01 upon execution and pays out $1.00 … The additional $0.01 is retained as ForecastEx's fee" per matched pair. The KID cost table also states "Exchange fee USD 0.005 per contract". Source: [ForecastEx KID](https://data.forecastex.com/regulatory/KIDS/ForecastExKeyInformationDocument.pdf). IBKR is reported to charge no commission (secondary). Source: [NextPredict](https://nextpredict.io/platforms/forecastex/)
- **DraftKings DKeX** (secondary): "For contracts valued between $0.20 and $0.96, takers face a $0.02 per-contract charge." Prices outside that band pay "reduced fees" (the article also says $0.005-$0.01). Makers pay "$0.0025 … regardless of price". Source: [Parameter, 1 Jul 2026](https://parameter.io/draftkings-debuts-dkex-platform-to-compete-in-prediction-markets-space/)
- **CME legacy event contracts**: costs are commissions plus routing, clearing and exchange fees charged on top of the premium (the specific per-contract fee was not retrieved). Source: [IBKR docs](https://www.interactivebrokers.com/docs/tws-api/doc/event-trading/introduction/cme-event-contracts)

### Cost at 90¢, 95¢ and 99¢, per $1 contract held to settlement (the project's own arithmetic from the formulas above)

| Venue / fee | 90¢ | 95¢ | 99¢ | Fee as % of max profit (1−p) |
|---|---|---|---|---|
| Gemini taker 0.07·p(1−p) | $0.0063 | $0.0033 | $0.0007 | 6.3% / 6.7% / 6.9% |
| Gemini maker 0.0175·p(1−p) | $0.0016 | $0.0008 | $0.0002 | 1.6% / 1.7% / 1.7% |
| CDNA/Crypto.com flat entry | $0.02 | $0.02 | $0.02 | 20% / 40% / **200%** |
| Robinhood commission (non-Gold) | $0.0090 | $0.0048 | $0.0010 | 9% / 9.5% / 9.9% (plus exchange fee ≤$0.01) |
| Robinhood commission (Gold) | $0.0045 | $0.0024 | $0.0005 | 4.5% / 4.75% / 4.95% (plus exchange fee) |
| ForecastEx (~$0.005 per side) | $0.005 | $0.005 | $0.005 | 5% / 10% / 50% |
| DKeX taker | $0.02 | $0.02 | $0.005-0.01 | 20% / 40% / 50-100% |
| DKeX maker | $0.0025 | $0.0025 | $0.0025 | 2.5% / 5% / 25% |

Break-even win rate (price plus fee): Gemini taker 90.63% / 95.33% / 99.07%. CDNA 92% / 97% / 101%, which is impossible at 99¢.

### Inferences
- Under p×(1−p) fees (Gemini, Robinhood's commission, Rothera's formula, Kalshi), the cost as a share of the maximum gain is roughly the rate × p. It is nearly flat across 90-99¢, so favourites are not penalised. Flat per-contract fees (CDNA, DKeX taker, ForecastEx) grow without limit relative to the gain as p → 1. They make 97-99¢ buys uneconomic.
- Gemini rounds fees up to the next cent per order. So a 1-contract order at 99¢ pays $0.01, the entire maximum profit. Orders need size (about 15 or more contracts at 99¢ taker) before rounding stops dominating.
- Rothera's $0.01 minimum per order, even with k = 0, works the same way: a flat cost per order, not per contract.

### Gaps
- Gemini's exact rounding unit: per order, per fill, or per day.
- CME legacy event contract exchange fees, and FanDuel Predicts fees.
- Cboe XSP binary exchange fees.
- Current CDNA fee for Crypto.com app or OG users, if it differs from the $0.02 Nadex schedule.
- Kalshi's current fee schedule was not re-verified in this pass.

---

## Q4. Liquidity: volumes, market makers, spreads near expiry

### Takeaway
Hard volume data for short-dated crypto contracts outside Kalshi is scarce. Gemini's whole prediction business is small (about $0.5M revenue in Q2 2026), though it tripled its contracted market makers. CDNA commits at least one dedicated market maker per crypto contract. Rothera's volume is large, but mostly sports routed from Robinhood. No published spreads near expiry were found for any non-Kalshi venue.

### Cited findings
- Gemini Q1 2026: prediction market revenue $0.4M, about 20K users since launch, April volume +78% month on month. Source: [Gemini Q1 2026 release](https://investors.gemini.com/news-releases/news-release-details/gemini-reports-first-quarter-2026-results-and-announces-100). Q2 2026: volume +93% QoQ, revenue +18% to about $524K (about 1% of $45.5M total), over 225M contracts cumulatively, "tripled its contracted market makers". Sources: [Finance Magnates](https://www.financemagnates.com/cryptocurrency/exchange/gemini-calls-the-segment-that-brought-in-500000-its-biggest-growth-opportunity/); [The Block, 13 Aug 2026](https://theblock.co/news/business/2026-08-13-gemini-shares-slide-108-million-loss-winklevoss-says-we-still-have-work-to-do-411775)
- CDNA: "The Exchange has at least one dedicated Market Maker who is committed to providing liquidity for the Contract," quoting two-sided under a Market Maker Agreement. Source: [CFTC filing, CDNA ETH, Apr 2026](https://www.cftc.gov/sites/default/files/filings/ptc/26/04/ptc04012642983.pdf)
- Rothera: about 3.5B contracts and $17M revenue in Q2 2026; about 2.1B contracts in June (secondary). Sources: [Crypto Briefing](https://cryptobriefing.com/rothera-powers-robinhood-prediction-market/); [The Block data](https://www.theblock.co/data/decentralized-finance/prediction-markets/rothera-monthly-volume)
- DraftKings Predictions: about $3.4B annualised consumer volume at the DKeX launch. Source: [The Block](https://www.theblock.co/amp/post/406375/draftkings-launches-own-prediction-markets-exchange-consumer-volume-exceeds-3-billion)
- FanDuel / CME: Flutter called the product "behind schedule." FanDuel expects "approximately $50 million of revenue from market making this year". Sources: [Casino.org, Aug 2026](https://www.casino.org/news/fanduel-moving-sports-event-contracts-to-crypto-com/); [Sportico](https://www.sportico.com/business/sports-betting/2026/fanduel-cme-prediction-market-crypto-nadex-1234941188/)
- Coinbase: prediction contracts and revenue +106% QoQ in Q2 2026 (secondary, unverified). Source: [JustGamers](https://www.justgamers.net/prediction-markets/coinbases/)
- Context: a 5-minute BTC market on Polymarket drew over $60M in a single day (Mar 2026). Source: [Fortune, 16 Mar 2026](https://www.fortune.com/2026/03/16/betting-on-5-minute-swings-on-bitcoin-price-are-the-hot-new-thing-on-prediction-markets)

### Inferences
- CDNA and Gemini liquidity in the last minutes of a 5- or 15-minute window probably comes from one or a few contracted market makers. Depth at 90-99¢ may be thin and set by the market maker, unlike Kalshi's multi-participant book. Worth checking with Gemini's public, no-key market-data endpoints before committing.

### Gaps
- Per-product volume and open interest for Gemini or CDNA short-dated crypto, and spreads near expiry: no published figures found.
- Names of the market makers on Gemini or CDNA.

---

## Q5. API access and latency, pass/fail per venue (benchmark: Kalshi)

### Takeaway
**Only Gemini Titan clearly PASSES**: a retail REST plus WebSocket API that goes straight to its own DCM book, much like Kalshi. CME event contracts PASS on infrastructure through futures-broker APIs, but they are daily $100 contracts, not short windows. Webull has a real event API but FAILS as a venue, because it is a broker hop onto Kalshi's book. **CDNA (Crypto.com), Robinhood/Rothera, Coinbase, DKeX, Underdog, PrizePicks, FanDuel Predicts and Truth Predict FAIL**: they are app-only, with no retail API found. IBKR ForecastEx and Cboe Predicts are UNCLEAR.

### Cited findings
**Benchmark: Kalshi**
- Per-second token budgets: Basic 200 read / 100 write (granted on signup); Advanced 300 / 300 (by API call); Premier 1,200 / 1,200 and Prime 4,800 / 4,800 (by trading-volume share). "REST and FIX requests draw from the same buckets". Source: [Kalshi rate limits](https://docs.kalshi.com/getting_started/rate_limits)
- WebSocket private channels include `orderbook_delta` and `fill`; public channels include ticker and trade. Source: [Kalshi WebSocket docs](https://docs.kalshi.com/getting_started/websocket_connection). FIX 4.4 is available to institutional users (third-party claim). Source: [Zuplo](https://zuplo.com/blog/2025/04/02/kalshi-api)

**Gemini Titan**
- REST is "Authenticated REST endpoints for placing and managing orders." WebSocket streams carry "prices, depth, order events, and positions." "For active trading and market making, prefer Prediction Markets WebSocket streams." Auth uses API keys or OAuth 2.0. A sandbox runs at api.sandbox.gemini.com; production is api.gemini.com. Source: [Gemini Prediction Markets API](https://developer.gemini.com/prediction-markets-spec)
- Public market-data REST needs no key. WebSocket auth uses account-scoped keys with time-based nonces. Trading keys need NewOrder and CancelOrder permissions, and the terms must be accepted before the first live order. Source: [Gemini getting started / trading quickstart](https://developer.gemini.com/prediction-markets/trading-quickstart)
- General Gemini REST limits: public 120 requests/min (recommended ≤1/s); private 600 requests/min (recommended ≤5/s); burst of 5 queued. It could not be confirmed that these apply unchanged to prediction-market endpoints. Source: [Gemini rate limits](https://developer.gemini.com/rate-limit)

**CDNA / Crypto.com / Nadex**
- No API is mentioned on Nadex product, pricing or home pages. Sources: [nadex.com/crypto](https://www.nadex.com/crypto/); [nadex.com/pricing](https://www.nadex.com/pricing/). Searches for a Crypto.com or CDNA prediction API found none; products are delivered in the Crypto.com app and OG. Source: [SBC Americas](https://sbcamericas.com/2026/02/03/cryptocom-prediction-market-platform-og/)

**Robinhood / Rothera**
- The Robinhood event-contracts page mentions no API; its footer's crypto trading API is not tied to event contracts. Source: [Robinhood support](https://www.robinhood.com/us/en/support/articles/robinhood-event-contracts/). Rothera admits customers only through an FCM. Source: [Rothera fee filing](https://cdn.prod.website-files.com/69a0b2d56634068be7fbbf2a/69fa6d5e7f1440875b946a71_20260505%20-%20Rothera%20Fee%20Schedule%20Filing.pdf)

**Coinbase**
- The Advanced Trade API covers "Spot crypto and CFTC-regulated US futures." Prediction markets are not listed. Source: [Coinbase Advanced Trade API](https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/overview)

**Webull (routes to Kalshi)**
- Event Trading API over HTTP (prod api.webull.com, plus a test environment). LIMIT is the only order type; time in force DAY, GTC, IOC, GTD or FOK. "Trade Event Subscription" pushes order and position changes. An Event trading account must first be opened in the app. Source: [Webull event-contract API](https://developer.webull.com/apis/docs/trade-api/event-contract)
- Changelog: 28 Mar 2026, "Event contracts now support quote, snapshot, and tick data subscription in the Data Streaming API." Trading events are delivered over gRPC (Jul 2026). A per-endpoint Rate Limits page was added on 14 Aug 2026. Event Snapshot and Depth endpoints were added in Jan 2026. Source: [Webull changelog](https://developer.webull.com/apis/docs/changelog/)

**IBKR ForecastEx and CME event contracts**
- In the TWS API, ForecastEx contracts are defined as SecType "OPT" on Exchange "FORECASTX"; Yes = call, No = put. Sources: [IBKR ForecastEx contract example](https://www.interactivebrokers.com/docs/tws-api/doc/event-trading/contract-definition-discovery/forecast-ex-contract-example); [IBKR Campus event contracts](https://www.interactivebrokers.com/campus/ibkr-api-page/event-contracts/)
- TWS API pacing: maximum requests per second = market-data lines ÷ 2 (default 50 msg/s). Exceeding it three times ends the session. FIX through IB Gateway allows 250 msg/s. Source: [IBKR pacing docs](https://www.interactivebrokers.com/docs/tws-api/doc/pacing-limitations/introduction)
- CME Globex matching engines sit in Aurora, IL, with customer co-location (servers placed next to the engine). Source: [CME co-location](https://www.cmegroup.com/solutions/co-location.html)

**App-only venues (no API found)**
- DKeX lives in the DraftKings app. Source: [Las Vegas Sun](https://lasvegassun.com/news/2026/jun/26/draftkings-launches-proprietary-exchange-to-bolste/). Underdog UDX / PrizePicks. Source: [SBC Americas](https://sbcamericas.com/2026/07/20/underdog-prediction-market-exchange/). FanDuel Predicts is a standalone app. Source: [CME PR](https://www.cmegroup.com/media-room/press-releases/2025/12/22/fanduel-and-cme-group-launch-fanduel-predicts.html). Truth Predict sits inside Truth Social. Source: [The Block](https://www.theblock.co/post/376547/trump-backed-truth-social-jumps-into-prediction-markets-with-crypto-com)

### Inferences: latency verdict per venue

| Venue | Retail API? | Push stream (book / own fills) | Order path | vs Kalshi | Verdict |
|---|---|---|---|---|---|
| **Gemini Titan** | Yes (REST + WebSocket, key or OAuth) | Yes: prices, depth, order events, positions | Direct to its own DCM | Similar architecture; lower documented REST limits (5 rps private, if they apply); host region unknown | **PASS** |
| **CDNA / Crypto.com (ex-Nadex)** | None found | None found | Crypto.com app / OG | Slower (manual only) | **FAIL** |
| **Robinhood** (Kalshi / ForecastEx / Rothera / CDNA) | No event-contract API | No | Broker app → venue | Slower | **FAIL** |
| **Rothera** | FCM-only; no retail access except via Robinhood | n/a | Via FCM | n/a | **FAIL** |
| **Coinbase** (Kalshi) | No (Advanced Trade excludes predictions) | No | App → Kalshi | Slower | **FAIL** |
| **Webull** (Kalshi) | Yes (REST, LIMIT only) | Quotes, ticks via Data Streaming; trade events via gRPC; depth REST snapshot | Broker middleware → Kalshi | Strictly slower than Kalshi direct; same book | **FAIL** (adds a hop, no new liquidity) |
| **IBKR ForecastEx** | Yes (TWS API / IB Gateway; FIX) | Yes (TWS streaming quotes, order and execution callbacks) | Client → TWS/Gateway → IBKR → ForecastEx | Probably slower (gateway hop); no published round-trip times; 50 msg/s default | **UNCLEAR** (API works, but no short-dated crypto product found) |
| **CME legacy event contracts** | Yes, through futures-broker APIs (IBKR TWS; brokers offering Globex access) | Yes (broker or Globex market data) | Broker → CME Globex (Aurora co-location possible) | Potentially faster (co-location, FIX) | **PASS** for infrastructure; product is daily $100 only |
| **FanDuel Predicts** (CME hourly) | No | No | App | Slower | **FAIL** |
| **DraftKings DKeX** | None found | none | App | Slower | **FAIL** |
| **Underdog UDX / PrizePicks / Truth Predict** | None found | none | App | Slower | **FAIL** |
| **Cboe Predicts XSP binaries** (SEC) | Likely through IBKR's options API (not confirmed for XSPBW/XSPBX) | Likely | Broker → Cboe | Unknown | **UNCLEAR** |

- No venue documented a deliberate speed bump. The CDNA filing describes a "cap-check" pre-trade collateral check on every order, which is standard and not a delay. Source: [CFTC filing, CDNA ETH](https://www.cftc.gov/sites/default/files/filings/ptc/26/04/ptc04012642983.pdf).

### Gaps
- No venue publishes round-trip times or matching-engine host regions for prediction contracts: Gemini (AWS region not found), Kalshi, CDNA.
- Gemini rate limits specific to prediction markets and WebSocket order entry: docs referenced but not retrieved (404 on the specific page).
- Whether CDNA offers FIX or API access to direct institutional members. Old Nadex had member types, but no current API document was found.
- Whether IBKR's API can trade Cboe XSPBW/XSPBX and CME's new $1 prediction contracts.

---

## Q6. Access: KYC, state restrictions, minimums and retail eligibility

### Takeaway
Crypto and financial event contracts are broadly available to US retail on all these venues. State fights target sports contracts (Nevada, Maryland, Michigan, New York). New York looks like the most likely exclusion for crypto-adjacent apps.

### Cited findings
- Robinhood: 18+, individual brokerage account, US resident. "Maryland and Nevada residents can't trade sports event contracts." "Michigan residents can't open new sports event contracts as of September 9, 2026." Source: [Robinhood support](https://www.robinhood.com/us/en/support/articles/robinhood-event-contracts/)
- Gemini: launched in all US states (Dec 2025). Source: [Crypto Briefing](https://cryptobriefing.com/gemini-predictions-market-launch/?rand=59535). Conflict: a state tracker lists 8 excluded states, including AZ, IL and MD (secondary). Source: [DeFi Rate states](https://defirate.com/prediction-markets/states/). Withdrawals by ACH or wire only. Source: [Gemini Predictions review](https://www.gamingtoday.com/prediction-markets/gemini/)
- CDNA / Crypto.com: event contracts in 49 states plus DC, excluding New York (Oct 2025, secondary). Source: [DeFi Rate](https://defirate.com/?p=1584). "CDNA membership required". Source: [SailGP guide, 5 Oct 2026](https://sailgp.com/prediction-markets/crypto/5-minute-markets). Nadex sites are "not directed at residents outside of the United States". Source: [nadex.com](https://www.nadex.com/)
- Coinbase: all 50 states at launch (Jan 2026). Source: [CoinDesk](https://www.coindesk.com/markets/2026/01/27/coinbase-rolls-out-prediction-market-to-u-s-customers). Nevada later excluded, and New York sued in Apr 2026 (secondary, unverified). Source: [JustGamers](https://www.justgamers.net/prediction-markets/coinbases/)
- FanDuel Predicts: financial contracts "in all 50 states"; sports only where online sports betting isn't legal. Source: [DeFi Rate](https://defirate.com/?p=3025)
- ForecastEx: "only available to eligible clients of Interactive Brokers LLC" and IBKR affiliates. Source: [IBKR Campus](https://www.interactivebrokers.eu/campus/traders-insight/forecastex-experiences-active-trading-weekend-nov-24-2025/)
- Webull API: an Event trading account must be opened in the app and agreements signed; Sports needs an extra agreement. Source: [Webull API docs](https://developer.webull.com/apis/docs/trade-api/event-contract)
- Regulatory backdrop: the CFTC proposed amendments to Rule 40.11 (which event contracts may be listed) on 10 Jun 2026; comments closed 27 Jul 2026. Sources: [Ropes & Gray](https://www.ropesgray.com/en/insights/alerts/2026/06/rewriting-the-rulebook-cftc-proposes-rule-changes-for-prediction-market-contracts); [CFTC proposed rule](https://www.cftc.gov/LawRegulation/FederalRegister/proposedrules/2026-05105.html). Nevada treats sports event contracts as wagering and restricted Kalshi there (Mar 2026). Source: [iGaming Business](https://igamingbusiness.com/legal-compliance/kalshi-nevada-temporary-restriction-march-2026/)

### Inferences
- A US retail trader can open Gemini Predictions (KYC through a Gemini account) and run bots on it, provided their state is not excluded. CDNA crypto contracts are retail-available but manual-only.

### Gaps
- Account minimums: none found for Gemini, CDNA or Robinhood event contracts.
- Gemini's official excluded-state list: none published.

---

## Q7. Pricing efficiency and favourite-longshot bias (favourites winning more or less often than their price implies)

### Takeaway
No peer-reviewed calibration study was found for Nadex, CDNA, Gemini, Rothera or ForecastEx. The best evidence comes from Kalshi: favourites win slightly more often than their price implies and earn small positive returns, while takers lose far more than makers. Nadex academic coverage is limited to pricing and trading-method papers, not efficiency tests.

### Cited findings
- Kalshi (300,000+ contracts): prices become more accurate near close but show a favourite-longshot bias. "High-price contracts win more often and earn small positive returns." Takers lose about 32% on average versus about 10% for makers (2025 working paper). Sources: [Bürgi, Deng & Whelan, UCD WP25/19](https://www.ucd.ie/economics/t4media/WP2025_19.pdf); [CEPR VoxEU](https://cepr.org/voxeu/columns/economics-kalshi-prediction-market)
- Nadex: the only academic hit was "Trading Binary Options Using Expected Profit and Loss Metrics," which uses Nadex data to illustrate implied drift and volatility for picking trades. It is a trading-method paper, not an efficiency test. Source: [OUCI record](https://ouci.dntb.gov.ua/en/works/4NQnoLe7/)
- General glossary claim: heavy favourites "trade slightly below" their hit rate, and fees and spreads near the price boundaries sustain the bias (weak source). Source: [pm.wiki](https://pm.wiki/es/data/glossary/longshot-bias)

### Inferences
- Any favourite edge seen on Kalshi will not carry over automatically to Gemini or CDNA. Their books are thinner and market-maker-led, and CDNA's flat $0.02 fee alone exceeds the edge at 95¢ and above.

### Gaps
- No calibration data for Gemini, CDNA, CME event contracts or Cboe XSP binaries. The expectation that Nadex had academic coverage was not confirmed by any paper found here.
