# Speed and information edges on prediction markets (Polymarket, Kalshi), as of October 2026

Research notes. Every figure has a date. Findings from 2024 and 2025 are marked "older".
Words used below, in plain terms:
- **Latency**: delay. A "latency bot" trades in the gap between when a price moves on a big exchange and when the prediction market catches up.
- **Taker**: a trader whose order fills right away against an order already sitting on the book. **Maker** (market maker): a trader who leaves resting buy and sell orders on the book and earns the gap between them.
- **Taker fee**: a charge on taker orders. On both venues it is biggest when the price is near 50 cents.
- **Edge**: profit per contract, in cents.
- **Insider trading**: trading on secret information that belongs to someone else, such as an employer or the government.
- **Arbitrage**: buying and selling linked things at once to lock in a price gap.
- **Unverified**: nobody independent checked the number against the wallet's full trade history.

## 1. Latency bots on short-term crypto markets (Polymarket 5/15-minute, Kalshi 15-minute)

### Takeaway
Latency bots really did trade Polymarket's 15-minute crypto markets in late 2025. But the viral "$313 into $400,000+" wallet (0x8dxd) has never been independently checked. A later audit says it mostly bought both sides at once, like a market maker, rather than sniping stale prices. Polymarket's main response was a taker fee, starting 5 January 2026. No public, verified case of a latency bot on Kalshi was found. Kalshi accounts are not public, so nobody outside can check.

### Cited findings

**When the markets started and how they settle**
- Polymarket launched short-term crypto markets in October 2025. Kalshi launched its 15-minute crypto markets in December 2025 (article dated 13 March 2026). Source: [crypto.news via Bitget](https://www.bitget.com/news/detail/12560605263885)
- Polymarket's 5- and 15-minute bitcoin markets settle on Chainlink price data. Chainlink is an oracle, meaning the outside price feed used to decide the winner (20 February 2026). Source: [Protos](https://protos.com/polymarket-ends-trading-loophole-for-bitcoin-quants/)
- Kalshi's bitcoin and ether 15-minute markets settle on CF Benchmarks prices. Its 15-minute gold market settles on a Pyth Network feed (7 October 2026). Source: [Bitcoin.com News](https://news.bitcoin.com/igaming/kalshis-15-minute-gold-bets-top-ether-fast-markets-drive-fees/)

**The viral wallet 0x8dxd (all figures unverified)**
- Coverage says 0x8dxd started in December 2025 with $313. Source: [MEXC news repost](https://www.mexc.com/news/417346)
- Finance Magnates (7 January 2026) quoted a social media post saying a bot turned $313 into $414,000 in one month. The article did not check the figure. It also cited on-chain data showing at least one wallet made "thousands" of such trades in a month with a very high success rate. Source: [Finance Magnates](https://www.financemagnates.com/cryptocurrency/polymarket-introduces-dynamic-fees-to-curb-latency-arbitrage-in-short-term-crypto-markets/)
- Other reposts give higher, rising numbers: about $437,600 by 6 January 2026, then "nearly $512,000" for one month and over $550,000 all-time. Sources: [MEXC news](https://www.mexc.com/news/417999); [MEXC news](https://www.mexc.com/news/441034)
- An X post by "Blake.ETH" (early January 2026) claimed $313 became $359,000 in 29 days. It cited 5,637 trades, a 96.3% win rate, and "a 500ms-2s ghost where Binance moved but odds didn't". It said the bot ran on a "$20/mo VPS" (a cheap rented server). This is a social post, not an audit. Source: [X / Blake.ETH](https://x.com/BlakeNastri2403/status/2007315124089139208)
- One search-result summary also attributed "over 20,000 trades, earning $1.7 million" to 0x8dxd. That figure could not be tied to a named outlet, so treat it as rumour (search snippet, see Gaps).
- **Contradicting audit:** LeoLabs studied the top 40 Polymarket leaderboard wallets from January to March 2026. It describes 0x8dxd as a bitcoin 5- and 15-minute market maker. About 94% of its trades bought YES and NO at the same moment. It ran around the clock with a typical (median) position under $6. At least three other wallets ran the same pattern. **LeoLabs sells a paid quant product and course and uses affiliate links.** Source: [LeoLabs](https://leolabs.me/blog/pm-top20-strategy-patterns/en/)
- A separate bot reportedly turned $63 into about $131,000 in a month. It bought both sides early and then dropped the losing side (Finbold story, January 2026, reposted). Unverified. Source: [EliteTrader repost](https://elitetrader.com/et/threads/trading-bot-that-works.388228/latest)

**Other profit claims and who makes them**
- Yahoo Finance reported a bot with a 98% win rate on $4,000-$5,000 bets, and a $206,000 profit at an 85%+ win rate. It gave no checkable records. Source: [Yahoo Finance](https://finance.yahoo.com/news/arbitrage-bots-dominate-polymarket-millions-100000888.html)
- QuantVPS says Polymarket lags Binance by 30-90 seconds. **QuantVPS sells rented servers to traders.** No measurement is shown. Source: [QuantVPS](https://www.quantvps.com/blog/binance-to-polymarket-arbitrage-strategies)
- One site sells a Polymarket bot script for 5- and 15-minute bitcoin markets (a $499 script per one review). **Seller page.** Source: [polymtradebot](https://polymtradebot.com/blog/review-of-the-polymarket-trading-bot-script)
- Grokipedia (an AI-written wiki) repeats a "$50 to $435,000" account story. No source shown. Source: [Grokipedia](https://grokipedia.com/page/Latency_Arbitrage_on_Polymarket)

**First-hand results that contradict the hype**
- A developer's write-up of 176 settled trades: total profit was about $2. Its momentum strategy (betting the price keeps going) lost money. Buying both UP and DOWN for less than $1 combined did pay, because one side always pays $1, but the gain was tiny. The author worked out that the momentum bet needed about a 72% win rate just to break even. Source: [DEV Community](https://dev.to/manja316/176-trades-on-polymarket-what-my-bot-actually-made-its-not-what-you-think-3iib)
- LayerX tested a directional 15-minute strategy. It lost 37.81%. The only strategy it kept running was a risk-free "both sides add up to less than $1" arbitrage. Source: [LayerX](https://layerx.xyz/blog/polymarketbots)

**Kalshi**
- Kalshi's 15-minute bitcoin markets traded 6.74 billion contracts in September 2026. Estimated taker fees on them were about $60.4 million that month (Predict Charts estimate, before maker rebates). Source: [Bitcoin.com News, 7 Oct 2026](https://news.bitcoin.com/igaming/kalshis-15-minute-gold-bets-top-ether-fast-markets-drive-fees/)
- In the week to 5 October 2026, 15-minute markets (crypto, commodity, stock index) earned $20.4 million of Kalshi's $25.1 million non-sports fees, about 80%. Sports earned $73.5 million that week. Source: [Bitcoin.com News](https://news.bitcoin.com/igaming/kalshis-15-minute-gold-bets-top-ether-fast-markets-drive-fees/)
- Kalshi's fee formula is 0.07 × contracts × price × (1 − price). That peaks at about 1.75 cents per contract near 50 cents. Source: [Bitcoin.com News](https://news.bitcoin.com/igaming/kalshis-15-minute-gold-bets-top-ether-fast-markets-drive-fees/)
- TurbineFi backtested 4,904 Kalshi 15-minute bitcoin strategies (April 2026). Only 102 made money. Results shifted with the time window and fill assumptions. **TurbineFi is a bot vendor.** Source: [TurbineFi](https://www.turbinefi.com/blog/5000-strategy-backtest-kalshi-btc-15m)

### Inferences
- The "30-90 seconds behind Binance" claim does not fit the rest of the evidence. Traders and Protos talk about gaps of half a second to two seconds. A 30-second gap in a market full of bots would be closed almost at once. Treat it as sales copy.
- The best evidence (the LeoLabs pattern, the DEV write-up, LayerX) points the same way. The money in these markets mostly came from buying both sides below $1 and from making markets, not from pure speed sniping. 0x8dxd's "96% win rate" is what you would expect if most trades are paired YES+NO buys. A paired buy "wins" one leg every time.
- The "conflicting" Polymarket fee figures (1.56%, ~3%, 3.15%) mostly measure different things. A fee of 1.56 cents on a 50-cent share is 1.56% of the $1 payout, but about 3.1% of the 50 cents you paid. So the sources can all be right at once. See section 6.
- After Polymarket's March 2026 change, its peak crypto fee (1.80% of payout) sits very close to Kalshi's (about 1.75 cents per $1 contract). The two venues now charge about the same to take liquidity on fast crypto markets.

### Gaps
- No independent audit of 0x8dxd's full profit and loss was found. Nobody published its results after fees started on 5 January 2026.
- The "$1.7 million, 20,000+ trades" figure came from a search summary with no clear outlet.
- No public case of a latency bot on Kalshi. Kalshi does not publish per-account data, so outsiders cannot check.
- No venue-published figure was found on what share of 15-minute volume comes from bots.

## 2. News trading: breaking news, live sports feeds, election night, economic data, "mention" markets

### Takeaway
Speed on live events is real, but the hard numbers are small. The best-documented edges are physical: TV antennas that beat streaming delays, and timing a rehearsal with a stopwatch. A May 2026 study of NBA markets found arbitrage chances lasting about 3.6 seconds and worth only a few thousand dollars in a month. For election night 2024 (older), traders priced the result hours before TV networks. They did it by reading public early counts, not secret data. No hard evidence was found of bots profiting seconds after CPI or jobs releases on Kalshi.

### Cited findings

**Live sports and broadcast delay ("courtsiding")**
- Courtsiding means someone at the event trades on what they see before the TV feed shows it. The UK Gambling Commission says it is not cheating under section 42 of the Gambling Act 2005. It may still break the event's ticket terms. Source: [UK Gambling Commission](https://www.gamblingcommission.gov.uk/licensees-and-businesses/print/in-play-or-in-running-betting)
- For Super Bowl LX (February 2026), Stats Perform measured stream delays of up to 62 seconds. Peacock, the best streaming service, ran 48 seconds behind. Over-the-air broadcast ran 19 seconds behind. Source: [NPR via KPBS, 17 Feb 2026](https://www.kpbs.org/news/science-technology/2026/02/17/tv-antennas-and-super-bowl-rehearsals-how-prediction-market-traders-seek-an-edge)
- Traders bought TV antennas to get a split-second edge in live events, including markets on which words someone will say. A 21-year-old trader, Caden Booth, timed the national anthem rehearsal with a stopwatch and profited. Kalshi did more than $1 billion in volume on Super Bowl day, up 2,700% from the year before. Source: [NPR via KPBS, 17 Feb 2026](https://www.kpbs.org/news/science-technology/2026/02/17/tv-antennas-and-super-bowl-rehearsals-how-prediction-market-traders-seek-an-edge)
- An X post claims "Polymarket sports bots are making millions on a +45s livestream delay". **Unverified social post.** Source: [X / 0xMovez](https://x.com/0xMovez/status/2008298059059343819)
- Polymarket's defence: sports markets hold marketable orders (orders that would fill at once) for 3 seconds before matching. A 1-second delay was being tested on NBA and MLB. The order cannot be cancelled during the delay. Sources: [Polymarket Help Center](https://help.polymarket.com/en/articles/13364444-limit-orders); [Polymarket docs](https://docs.polymarket.com/concepts/order-lifecycle)
- Polymarket also cancels all resting limit orders when a game starts, so stale pre-game quotes cannot be picked off. Source: [Polymarket Help Center](https://help.polymarket.com/en/articles/13364444-limit-orders)
- **Academic test, NBA (UCLA authors, arXiv, April 2026):** 173 games, 4 February to 4 March 2026, over 75 million order-book snapshots. Only 7 single-market arbitrage chances appeared during games, lasting a median of 3.6 seconds. Profit was $210 with a $100 cap per chance, or $4,418 with no cap. Another 290 chances came from linked markets (moneyline vs spread), worth $560 capped or $2,033 uncapped. Depth was the limit. In 76.9% of chances, $100 could not be fully used. The average fillable size was about 14.8 shares. Snapshots came every 3.6 to 5.5 seconds, so faster chances were missed. Source: [arXiv 2605.00864](https://arxiv.org/html/2605.00864v1)
- That paper says Polymarket charged no fees on NBA markets. Pine Analytics says sports fees started 18 February 2026, inside the study window. The two sources conflict on fees for part of the sample. Sources: [arXiv 2605.00864](https://arxiv.org/html/2605.00864v1); [Pine Analytics](https://pineanalytics.substack.com/p/polymarket-fee-rollout)

**Top sports wallets (research or automation, not proven speed)**
- "swisstony" (sports): $4.96 million net profit on $494 million traded, fully automated. That is about 1 cent of profit for every dollar traded. "kch123": $10.35 million all-time, but down $479,000 in the 30 days to mid-March 2026. "fengdubiying": $3.13 million, mostly from concentrated League of Legends bets. **Source sells a quant course and uses affiliate links.** Source: [LeoLabs](https://leolabs.me/blog/pm-top20-strategy-patterns/en/)

**Election night 2024 (older)**
- Polymarket had Trump near 97% to win as midnight approached on the US East Coast, hours before the official calls. Source: [Sherwood News](https://www.sherwood.news/world/donald-trump-has-won-the-election-traders-were-betting-on-it-overnight/)
- Traders read early results in safe states and Florida and guessed the swing states would follow. Sources: [CryptoSlate](https://cryptoslate.com/polymarkets-accurate-forecast-of-trump-win-highlights-gaps-in-mainstream-media-pollsters/); [Haseeb Qureshi](https://haseebq.com/what-polymarket-got-right-that-the-experts-got-wrong/)
- Polymarket paid out after the AP, Fox and NBC calls. Source: [Fortune, 4 Nov 2024](https://fortune.com/2024/11/04/polymarket-presidential-election-prediction-market-bets-payout-inauguration)

**Economic data (CPI, jobs, Fed)**
- A Kalshi bot vendor says CPI comes out at 8:30 a.m. ET and Kalshi can lag futures markets for a short window after a print. It gives no timing data. It also warns most traders in these markets lose money. **Vendor blog.** Source: [botforkalshi](https://www.botforkalshi.com/blog/kalshi-economic-indicators-trading)
- Kalshi's own post says Fed "hold" odds jumped to 80% after the September 2026 jobs report. This shows a reprice, not how fast it happened. Sources: [Kalshi News](https://news.kalshi.com/p/fed-rate-hike-odds-plummet-october-after-september-jobs-miss); [Crypto Briefing](https://cryptobriefing.com/kalshi-fed-hold-odds-weak-jobs-report/)

**Mention markets (will a speaker say a word?)**
- Mention markets cover Fed press conferences, earnings calls (such as Palantir, Apple) and presidential speeches. Over $2.8 million traded on one Kalshi Powell market before a press conference (2026). Sources: [Bloomberg feature](https://www.bloomberg.com/features/2026-prediction-markets-polymarket-kalshi/); [DeFi Rate](https://defirate.com/prediction-markets/mention-markets/)
- Kalshi settles mention markets on official transcripts, not live TV. Polymarket uses a different source. Source: [DeFi Rate](https://defirate.com/prediction-markets/mention-markets/)
- The biggest documented mention-market profit is insider trading, not speed. Trump's former teleprompter operator, Gabriel Perez, made $107,539.02 using early access to speeches (December 2025 to February 2026). See section 4. Source: [Government Enforcement Report](https://www.governmentenforcementreport.com/2026/10/cftc-issues-staff-advisory-on-prediction-market-contracts-tied-to-individual-conduct/)

### Inferences
- In live sports, the documented speed edge is about broadcast delay (19 to 62 seconds), not microseconds. That is why Polymarket added a 3-second hold on sports orders. Anyone watching a stream is the slow side of that trade. In plain words, they are the ones getting picked off by someone who knows more (adverse selection).
- The NBA paper suggests that clean, risk-free in-game arbitrage is small and short. Most of the in-game money is likely in directional speed (knowing the score first), which the paper cannot see.
- Election night 2024 is better described as fast reading of public data than as a secret edge.

### Gaps
- No venue enforcement case against courtsiding on Kalshi or Polymarket was found.
- No measured study of how fast Kalshi prices move after CPI, jobs or Fed releases.
- A CNBC story (1 August 2026, "Traders go full-time on prediction markets using AI bots and antennas") could not be opened (blocked).
- No figures on total trader profit from earnings-call mention markets.

## 3. Private information edges from research: the "Théo" whale and others

### Takeaway
Théo (older, 2024) is the cleanest case of a legal research edge paying at huge scale. Blockchain analysis firm Chainalysis put his profit at about $78.7 million. He backed his view with his own "neighbor" polls. Profit estimates range from $48 million to $85 million depending on how many of his accounts are counted.

### Cited findings
- The trader called himself "Théo" and was identified by the Wall Street Journal. He is French and used several Polymarket accounts. Sources: [The Block, 7 Nov 2024 (older)](https://www.theblock.co/post/324996/french-polymarket-whale-us-election-profit-france-ban); [casino.org](https://www.casino.org/news/polymarket-whale-funded-neighbor-surveys-to-win-85m-on-trump/)
- **Method:** polls that asked people who their *neighbors* would vote for, not who they would vote for. The idea was to get around "shy Trump voters". These showed Trump doing better than normal polls. He commissioned a poll to confirm it. Source: [The Block](https://www.theblock.co/post/324996/french-polymarket-whale-us-election-profit-france-ban)
- **Size:** Polymarket said his four big accounts spent more than $45 million on a Trump win. One late-October wager was about $28 million. Sources: [The Block](https://www.theblock.co/post/324996/french-polymarket-whale-us-election-profit-france-ban); [casino.org](https://www.casino.org/news/polymarket-whale-funded-neighbor-surveys-to-win-85m-on-trump/)
- **Profit estimates (all November 2024, older):** Bloomberg first said $48 million from four accounts. Chainalysis said about $78.7 million net from nine accounts, matched by funding patterns, timing and cash-outs. A later count said about $85 million across 11 accounts. Sources: [The Block](https://www.theblock.co/post/324996/french-polymarket-whale-us-election-profit-france-ban); [The Free Press](https://www.thefp.com/p/french-whale-makes-85-million-on-polymarket-trump-win); [casino.org](https://www.casino.org/news/polymarket-whale-funded-neighbor-surveys-to-win-85m-on-trump/)
- He also called Trump's popular-vote win and the Pennsylvania, Michigan and Wisconsin flips. Source: [casino.org](https://www.casino.org/news/polymarket-whale-funded-neighbor-surveys-to-win-85m-on-trump/)
- Polymarket's October 2024 review found no evidence of market manipulation. France's gambling regulator (ANJ) said it was looking into Polymarket's operations. Source: [The Block](https://www.theblock.co/post/324996/french-polymarket-whale-us-election-profit-france-ban)
- LeoLabs groups some top wallets as "knowledge-based": few, high-conviction bets built on specialist research (Q1 2026 data). **Vendor source.** Source: [LeoLabs](https://leolabs.me/blog/pm-top20-strategy-patterns/en/)

### Inferences
- Théo's edge needed two things almost no one has: tens of millions of dollars, and a willingness to bet it on one night. His poll was cheap compared with the bet. The research mattered only because the market was deep enough to take $45 million+.
- His returns came from one event. That is one coin flip at huge size, not a repeatable strategy you can test.

### Gaps
- Nothing newer was found on Théo's legal status in France or later trading.
- No other well-sourced whale was found whose edge was legal private research with a confirmed profit figure. Most high-profit "information" cases in 2025-2026 are insider allegations (section 4).

## 4. Insider trading cases and allegations, and enforcement

### Takeaway
2026 is the year enforcement arrived. The US brought its first criminal and CFTC insider cases over prediction-market bets in April 2026 (the Maduro raid soldier, about $400,000). A Google engineer was charged in May 2026 (about $1.2 million). Kalshi has banned and fined traders since February 2026. A Columbia/Harvard paper estimates at least $143 million in suspicious profit on Polymarket from February 2024 to February 2026. Most single insiders made $30,000 to $1.2 million.

### Cited findings

**Summary of documented cases (money figures in US dollars)**

| Case (when) | Venue | Money made, plainly | Status as of Oct 2026 |
|---|---|---|---|
| Maduro raid soldier, Gannon Van Dyke (Dec 2025-Jan 2026) | Polymarket | Put in about $34,000, won about $404,000-$410,000 | Charged 23 Apr 2026; pleaded not guilty; trial set for about 7 Dec |
| Google "Year in Search", Michele Spagnuolo, "AlphaRaccoon" (Oct-Dec 2025) | Polymarket | About $1.2 million in winnings | Charged in New York, May 2026 |
| US strike on Iran, six new wallets (28 Feb 2026) | Polymarket | About $1-1.2 million in total; one wallet about $493,000-$553,000 | Not identified; reported CFTC probe |
| Teleprompter operator, Gabriel Perez (Dec 2025-Feb 2026) | Kalshi | $107,539 profit, all handed back plus $65,000 fine | CFTC settlement 28 Aug 2026; 3-year ban |
| Nobel Peace Prize leak (Oct 2025, older) | Polymarket | About $90,000 across three accounts | Norway probe; no result found |

**Maduro raid (Polymarket)**
- The account "Burdensome-Mix" joined weeks before the trade (NPR, 5 January 2026). Source: [NPR](https://npr.org/2026/01/05/nx-s1-5667232/polymarket-maduro-bet-insider-trading)
- DOJ charged Army special forces soldier Gannon Ken Van Dyke on 23 April 2026. Charges: unlawful use of confidential government information, theft of government information, commodities fraud, wire fraud, and an unlawful money transaction. Source: [US Department of Justice](https://www.justice.gov/opa/pr/us-soldier-charged-using-classified-information-profit-prediction-market-bets)
- Prosecutors say 13 bets of about $33,934 won about $409,881. Sources: [ABC News](https://abcnews.com/US/doj-arrests-soldier-made-400000-betting-maduros-removal/story?id=132325426); [CNBC](https://www.cnbc.com/2026/04/23/doj-soldier-polymarket-bets-venezuela-maduro.html)
- The CFTC says he bought over 436,000 "Yes" shares in "Maduro out by January 31, 2026?" between 30 December 2025 and 2 January 2026. It says he made over $404,000. This is the CFTC's first use of the "Eddie Murphy Rule", which bans trading on stolen government information. Source: [Foley & Lardner, 5 May 2026](https://www.foley.com/insights/publications/2026/05/insider-predicting-cftcs-first-action-and-how-we-got-here/)
- Polymarket says it flagged the trades itself and referred them to DOJ. Sources: [Axios](https://www.axios.com/2026/04/23/us-soldier-arrested-maduro-bet-polymarket); [ABC7](https://abc7ny.com/post/us-soldier-charged-using-intel-win-400k-maduro-raid-appear-court-nyc/18985601/)
- He pleaded not guilty on 28 April 2026 and was released on $250,000 bail. Source: [ABC7](https://abc7ny.com/post/us-soldier-charged-using-intel-win-400k-maduro-raid-appear-court-nyc/18985601/)
- Trial is tentatively set for 7 December 2026, per Inner City Press via Decrypt (single source). Source: [Decrypt](https://decrypt.co/?p=370571)
- Figures conflict: the Mitts/Ofir paper (March 2026, before charges) says about $485,000 from $38,500. Source: [Harvard Law School Forum](http://corpgov.law.harvard.edu/2026/03/25/from-iran-to-taylor-swift-informed-trading-in-prediction-markets/)

**Google "Year in Search" (Polymarket)**
- Michele Spagnuolo, 36, a Google engineer and Italian citizen living in Switzerland, was charged with using secret Google search data. He allegedly made about $1.2 million (TechCrunch, 27 May 2026). Source: [TechCrunch](https://techcrunch.com/2026/05/27/google-engineer-charged-with-insider-trading-after-making-1-2m-on-polymarket/)
- The "AlphaRaccoon" account allegedly risked about $2.75 million on Google markets from October to December 2025. It collected about $1.2 million after Google's 4 December 2025 announcement. One bet was on singer d4vd as most-searched person, which the market priced near zero. Google put him on leave. Source: [Gambling Insider](https://gamblinginsider.com/news/163425/google-polymarket-insider-trading-alpharaccoon-jpg)
- A blog's "$10K into $1M overnight" headline does not match the charging papers. Source: [DeFi Rate blog](https://defirate.com/?p=2578)

**US strike on Iran, 28 February 2026 (Polymarket)**
- Blockchain analysts Bubblemaps flagged six new wallets, mostly funded within 24 hours of the attack. They bought "Yes" hours before explosions in Tehran. Combined profit was about $1 million to $1.2 million. Sources: [CoinDesk](https://www.coindesk.com/markets/2026/02/28/suspected-insiders-make-over-usd1-2-million-on-polymarket-ahead-of-u-s-strike-on-iran); [The Block](https://www.theblock.co/post/391650/fresh-accounts-netted-1-million-on-polymarket-hours-before-us-airstrikes-on-iran-bubblemaps)
- One wallet turned about $61,000 into over $493,000 profit. Source: [The Block](https://www.theblock.co/post/391650/fresh-accounts-netted-1-million-on-polymarket-hours-before-us-airstrikes-on-iran-bubblemaps)
- The Mitts/Ofir paper names one account, "Magamyman", at about $553,000. Source: [Harvard Law School Forum](http://corpgov.law.harvard.edu/2026/03/25/from-iran-to-taylor-swift-informed-trading-in-prediction-markets/)
- The Iran market family had $529 million in volume, $90 million on the 28 February contract. Sources: [Bloomberg](https://www.bloomberg.com/news/articles/2026-02-28/polymarket-iran-bets-hit-529-million-as-new-wallets-draw-notice); [Forbes](https://www.forbes.com/sites/boazsobrado/2026/03/02/fresh-wallets-made-12m-on-polymarket-hours-before-iran-airstrikes/)
- Snopes confirmed the bets but found no public link to any official (3 March 2026). Source: [Snopes](https://www.snopes.com/news/2026/03/03/polymarket-bets-iran-strikes/)

**Israel (Polymarket)**
- Israel indicted an IDF reservist and a civilian on 12 February 2026 for betting on military operations with classified information. Charges include serious security offences, bribery and obstruction. Sources: [Reuters via Internazionale](https://www.internazionale.it/ultime-notizie-reuters/2026/02/12/israel-indicts-reservist-civilian-over-betting-on-military-operations); [The Block](https://www.theblock.co/post/389575/israeli-defense-reservist-civilian-indicted-over-alleged-insider-betting-on-polymarket-reports)
- Reports conflict on which operation (April 2024 or June 2025) and on rank (the Times of Israel says an Air Force major). Profit is not public. Source: [Times of Israel](https://www.timesofisrael.com/israeli-air-force-major-charged-with-using-classified-info-to-place-bets-on-polymarket/amp/)

**Nobel Peace Prize, October 2025 (older)**
- Maria Corina Machado's odds jumped from about 3.6% to over 70% hours before the announcement. Account "dirtycup" bet about $70,000 and made about $30,000. Three accounts made about $90,000 in total. The Nobel Institute opened a review. Sources: [Blockworks](https://blockworks.co/news/polymarket-nobel-probe); [The Block](https://www.theblock.co/post/374199/officials-probe-polymarket-over-suspicious-trades-predicting-nobel-peace-prize-winner-reports); [Decrypt](https://decrypt.co/343840/nobel-peace-prize-organizers-intestigating-polymarket-insider-trades?amp=1)

**Kalshi cases**
- February 2026: a California governor candidate bet about $200 on his own race. He got a 5-year ban and a fine of 10 times the trade. A MrBeast video editor bet about $4,000 on MrBeast YouTube markets. He got a 2-year ban. Sources: [Front Office Sports](https://frontofficesports.com/kalshi-bans-fines-2-traders-who-bet-on-inside-information/); [Axios](https://www.axios.com/2026/02/25/kalshi-insider-trading-suspension)
- The editor, Artem Kaptur, had "near-perfect trading success" on low-odds bets. Kalshi froze the account, so he could not withdraw. Fine: $20,397.58 (Kalshi notice) or about $20,000 (NPR). Sources: [TheWrap](https://www.thewrap.com/media-platforms/tv/mrbeast-editor-kalshi-insider-trading/); [NPR](https://www.npr.org/2026/02/25/nx-s1-5726050/kalshi-insider-trading-enforcement-actions)
- 22 April 2026: three congressional candidates were suspended for 5 years. Fines were $539.85, $784.20 and $6,229.30 (the last one stopped cooperating). Kalshi gave no profit figures. Sources: [Kalshi News](https://news.kalshi.com/p/kalshi-political-insider-trading-enforcement-update); [CNBC](https://www.cnbc.com/2026/04/22/kalshi-insider-trading-congress.html)
- Kalshi opened more than 150 insider-trading investigations in Q1 2026, blocked over 100 possible insider trades, and referred at least 20 cases to law enforcement. It added employer checks for high-risk markets. Source: [The Defiant](https://thedefiant.io/news/regulation/kalshi-insider-trading-investigations-q1-employer-checks)
- September 2026: Kalshi's first lifetime ban, for former congressman George Santos, plus a $71,356 penalty, for not cooperating. He bet on whether he would attend the State of the Union. He made $17,839.57. Under a separate CFTC deal he gives up the winnings, pays a $17,500 fine and takes a 3-year ban. (Syndicated single source.) Sources: [TNND via WJLA](https://wjla.com/news/nation-world/kalshi-permanently-bans-santos-over-bets-on-state-of-the-union-attendance-president-trump-new-york-republican-congress); [Prediction News](https://predictionnews.com/story/boise-state-public-radio-covers-prediction-markets-notes-kalshis-first-permanent)
- A North Carolina House candidate (Buckhout) got a 3-year ban and a $2,590 penalty (September 2026). Source: [Prediction News](https://predictionnews.com/story/boise-state-public-radio-covers-prediction-markets-notes-kalshis-first-permanent)
- Teleprompter case: Gabriel Perez traded presidential mention markets on Kalshi with advance copies of speeches (December 2025 to February 2026). The CFTC order of 28 August 2026: hand back $107,539.02 in profit, pay a $65,000 fine, 3-year ban. Kalshi helped the probe. Source: [Government Enforcement Report](https://www.governmentenforcementreport.com/2026/10/cftc-issues-staff-advisory-on-prediction-market-contracts-tied-to-individual-conduct/)

**Size of the problem (research)**
- Mitts (Columbia) and Ofir, "From Iran to Taylor Swift" (SSRN, March 2026): screened Polymarket from February 2024 to February 2026. That covered over 93,000 markets and nearly 50,000 wallets. They flagged 210,718 suspicious wallet-market pairs. Flagged traders won 69.9% of the time. A reshuffle test says that is far too big to be luck (over 60 standard deviations above chance). Sources: [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6426778); [Harvard Law School Forum](http://corpgov.law.harvard.edu/2026/03/25/from-iran-to-taylor-swift-informed-trading-in-prediction-markets/)
- Their estimate of suspicious profit is about $143 million. They call this a floor (the true number is probably higher). The screen only looks at buys, skips positions under $500, and cannot see hedges. No dataset has confirmed insider labels. Source: [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6426778)
- Other cases they list: "romanticpaul" on Taylor Swift's engagement, and an OpenAI browser launch. No profit figures. Source: [Harvard Law School Forum](http://corpgov.law.harvard.edu/2026/03/25/from-iran-to-taylor-swift-informed-trading-in-prediction-markets/)
- A Bloomberg analysis reportedly found about $200 million of flagged trades from 1 January to 30 June 2026. It appeared only in a search snippet; the page was blocked. Source: [Bloomberg graphics (not opened)](https://www.bloomberg.com/graphics/2026-polymarket-traders-who-knew-the-future/)

### Inferences
- Insiders make the biggest *percentage* returns in this whole topic. They bet on prices near zero, so $34,000 can become $400,000. But the sizes are small, and each case is one event.
- Detection is working better than insiders expect. Polymarket flagged Van Dyke itself. Kalshi froze the MrBeast editor's winnings. Public wallets on Polymarket make sleuthing easy.
- Kalshi fines so far are tiny ($540 to $71,356). The criminal cases (DOJ) are where the real risk is.

### Gaps
- No outcome yet for the Nobel probe, the Iran wallets, or the Israeli case's profit.
- Bloomberg's $200 million figure and Forbes' 11 May 2026 Iran article ("$18K a year") could not be opened.
- Whether the CFTC has opened a formal case on the Iran wallets is reported only second-hand.

## 5. Who wins: tech, data feeds, capital, and where the servers are

### Takeaway
On crypto speed, the winners sit next to the venue's servers. Polymarket runs in AWS London (eu-west-2). Kalshi runs in AWS Ohio (us-east-2). They read exchange prices directly and trade small sizes in very large numbers. Speed needs little money, but thin depth caps how much it can earn. Information edges are the reverse: little tech, but either secret access or, like Théo, very large capital.

### Cited findings
- Glassnode's latency monitor lists Polymarket's origin servers in AWS eu-west-2 (London), behind Cloudflare. It lists Kalshi's in AWS us-east-2 (Ohio), behind CloudFront. It says Polymarket traders often run servers in Dublin (AWS eu-west-1). Trading Polymarket is restricted in England and the Netherlands. Source: [Glassnode Latency Monitor](https://latency.glassnode.com/prediction-markets/about)
- A VPS seller also puts Polymarket in eu-west-2. It lists order rate limits of 3,500 per 10 seconds and cancels at 3,000 per 10 seconds. **Vendor.** Source: [QuantVPS](https://www.quantvps.com/blog/polymarket-servers-location)
- A latency guide reports book-update delays from one day of recording next to the servers. Kalshi's median is about 9.4 milliseconds. Polymarket's median is about 4 milliseconds, but the slowest 1 in 100 updates took about 43 milliseconds. It also says Kalshi was fastest to reach from AWS Ohio. (Taken from a search summary; the page was not opened.) Source: [cryptostruct](https://cryptostruct.com/guides/prediction-market-bot-latency)
- After Polymarket removed its 500-millisecond taker delay in February 2026, one trader said "latency is now the only moat" (moat meaning the thing that keeps rivals out). Source: [Protos](https://protos.com/polymarket-ends-trading-loophole-for-bitcoin-quants/)
- LeoLabs claims over 70% of crypto arbitrage profit goes to bots faster than 100 milliseconds. **Vendor claim, no data shown.** Source: [LeoLabs](https://leolabs.me/blog/pm-top20-strategy-patterns/en/)
- LeoLabs says a popular open-source market-making bot loses money, because it just steps one tick ahead of others with no pricing model of its own. Source: [LeoLabs](https://leolabs.me/blog/pm-top20-strategy-patterns/en/)
- Market maker Keyrock called the growth of 5- and 15-minute bitcoin markets "explosive" (March 2026). Source: [crypto.news via Bitget](https://www.bitget.com/news/detail/12560605263885)
- **Arbitrage across linked markets (older, April 2024 to April 2025):** IMDEA Networks and Oxford researchers estimated about $40 million in realized arbitrage profit on Polymarket. They found it in over 7,000 markets whose prices did not add up. They used AI language models to spot linked markets. Sources: [arXiv 2508.03474](https://arxiv.org/html/2508.03474v1); [Decrypt](https://decrypt.co/339958/40-million-free-money-glitch-crypto-prediction-markets)
- Capital examples: Théo spent over $45 million (2024, older). Van Dyke used about $34,000. One Iran wallet used about $61,000. AlphaRaccoon risked about $2.75 million. 0x8dxd reportedly started with $313 and had a typical position under $6. Sources: [The Block](https://www.theblock.co/post/324996/french-polymarket-whale-us-election-profit-france-ban); [ABC News](https://abcnews.com/US/doj-arrests-soldier-made-400000-betting-maduros-removal/story?id=132325426); [The Block](https://www.theblock.co/post/391650/fresh-accounts-netted-1-million-on-polymarket-hours-before-us-airstrikes-on-iran-bubblemaps); [Gambling Insider](https://gamblinginsider.com/news/163425/google-polymarket-insider-trading-alpharaccoon-jpg); [LeoLabs](https://leolabs.me/blog/pm-top20-strategy-patterns/en/)

### Inferences
- For Kalshi crypto, the venue's servers, its settlement feed (CF Benchmarks) and Kalshi's own fee all sit in the US. A bot in AWS Ohio is about as close as one can get. Being faster than that is not available to outsiders.
- Speed bots on these markets are many small trades. Depth (how much you can trade before moving the price) limits them, not money. That fits the NBA paper's 14.8-share average fill.

### Gaps
- Polymarket has not published its server location. Both sources are third parties.
- No venue was found that offers formal colocation (renting space inside its own data centre).
- The 9.4 ms and 4 ms figures could not be checked against an opened page.

## 6. Is the edge fading? How venues and regulators responded (2024 to 2026)

### Takeaway
Yes, for crypto latency on Polymarket. Taker fees started 5 January 2026 and spread to every category by 30 March 2026. In February 2026 Polymarket also quietly removed a 500-millisecond delay that had protected market makers. This shifted the game toward market making and pure speed. Volume did not collapse. Kalshi now earns most of its non-sports fees from these fast markets. Regulators moved from nothing to active cases in 2026.

### Cited findings

**Polymarket fees**
- Fees started on crypto markets on 5 January 2026, first on 15-minute contracts only. They expanded to all crypto timeframes by 6 March. Sports followed on 18 February. Almost all other categories followed on 30 March 2026. Source: [Pine Analytics, 25 Mar 2026](https://pineanalytics.substack.com/p/polymarket-fee-rollout)
- Peak crypto fee was 1.56% at launch, then 1.80% after 30 March. Sports went from 0.44% to 0.75%. Economics is 1.50% and politics 1.00%. Geopolitics is 0%. The blended average is about 0.76% of taker volume. Source: [Pine Analytics](https://pineanalytics.substack.com/p/polymarket-fee-rollout)
- Fees fund a Maker Rebates Program, paid daily in USDC to liquidity providers. Makers get back 20% of crypto fees, 25% in most categories and 50% in finance. Sources: [Pine Analytics](https://pineanalytics.substack.com/p/polymarket-fee-rollout); [The Block](https://www.theblock.co/post/384461/polymarket-adds-taker-fees-to-15-minute-crypto-markets-to-fund-liquidity-rebates)
- The stated aim was to "neutralise latency-based arbitrage strategies". Finance Magnates gave the peak as about 3.15% of a 50-cent contract's price (7 January 2026). Source: [Finance Magnates](https://www.financemagnates.com/cryptocurrency/polymarket-introduces-dynamic-fees-to-curb-latency-arbitrage-in-short-term-crypto-markets/)
- Worked example: 100 shares at $0.50 pays about $1.56 in fees. That is about 3% of the $50 cost. Sources: [KuCoin News](https://www.kucoin.com/news/flash/polymarket-introduces-taker-fees-for-15-minute-crypto-prediction-markets); [Cointelegraph via TradingView](https://www.tradingview.com/news/cointelegraph:e59c32089094b:0-polymarket-quietly-introduces-taker-fees-on-15-minute-crypto-markets/)
- Pine estimates about $160 million a day of taker volume, about $1.2 million a day of gross fees, and about $573,000 a day net to Polymarket (about $209 million a year), as of March 2026. Source: [Pine Analytics](https://pineanalytics.substack.com/p/polymarket-fee-rollout)

**The 500-millisecond delay**
- Polymarket used to hold taker orders for 500 milliseconds. That gave market makers time to pull stale quotes. It was removed quietly in February 2026 with "no announcement, no changelog". Source: [Protos, 20 Feb 2026](https://protos.com/polymarket-ends-trading-loophole-for-bitcoin-quants/)
- One guide dates it to 18 February 2026. It argues a profitable 2026 bot must be a maker bot, using zero maker fees and rebates. Source: [HTX news](https://www.htx.com/news/polymarket-new-rules-released-how-to-build-a-new-trading-bot-mkPMdTD8/)
- A developer said wallets that had traded dozens of 5-minute markets every hour simply stopped. Source: [DEV Community](https://dev.to/lkto1m/february-2026-changed-polymarket-forever-heres-what-happened-to-my-bots-numbers-2fi5)

**Volume after the changes**
- Short-term markets were over half of all crypto trading on Polymarket and Kalshi combined, about $70 million a day. Volume showed "no visible slowdown" after fees (13 March 2026). Source: [crypto.news via Bitget](https://www.bitget.com/news/detail/12560605263885)
- Polymarket crypto volume hit $100-120 million a day in early March, then settled at $73-100 million. Source: [Pine Analytics](https://pineanalytics.substack.com/p/polymarket-fee-rollout)
- Kalshi's 15-minute bitcoin markets did 6.74 billion contracts in September 2026. 15-minute markets made about 80% of its non-sports fees in early October 2026. Source: [Bitcoin.com News](https://news.bitcoin.com/igaming/kalshis-15-minute-gold-bets-top-ether-fast-markets-drive-fees/)

**Polymarket integrity rules**
- New insider rules on 23 March 2026. They ban trading on stolen confidential information or illegal tips, and betting by people who can influence the result. They sit in its Terms of Use and the Polymarket US Rulebook. Sources: [Bloomberg](https://www.bloomberg.com/news/articles/2026-03-23/polymarket-implements-new-insider-trading-rules-after-scrutiny); [Polymarket Market Integrity](https://integrity.polymarket.com/)
- This reversed CEO Shayne Coplan's earlier claim that insider trading is a "feature" (older remark). Source: [NextPredict](https://nextpredict.io/market-news/industry/polymarket-flips-insider-trading-stance-new-integrity-rules/)
- Polymarket added Chainalysis for surveillance, on top of an earlier Palantir deal. Source: [The Defiant](https://thedefiant.io/news/defi/polymarket-taps-chainalysis-to-police-insider-trading)
- CNN (21 August 2026) reported Polymarket referred "dozens" of possible military insider cases to DOJ. Search snippets cite 90+ referred accounts and 152 flagged accounts. The page could not be opened (blocked). Source: [CNN (not opened)](https://edition.cnn.com/2026/08/21/politics/polymarket-doj-military-prediction-market)
- The House Oversight Committee wrote to Coplan on 22 May 2026. It asked how Polymarket checks identity, blocks restricted countries and spots odd trading. Source: [House Oversight letter](https://oversight.house.gov/wp-content/uploads/2026/05/Polymarket-Prediction-Markets-Letter.pdf)

**CFTC and Congress**
- 25 February 2026: the CFTC's enforcement division put out an advisory after two Kalshi insider cases. It listed insider trading, wash trading (trading with yourself to fake volume) and manipulation as banned. Sources: [CFTC press release](https://www.cftc.gov/PressRoom/PressReleases/9185-26); [CRS](https://www.congress.gov/crs-product/LSB11406)
- March 2026: an early notice that the CFTC is considering new prediction-market rules. Comments were due 30 April 2026. Source: [predictionmarkets.us](https://predictionmarkets.us/articles/cftc-prediction-markets-rulemaking-2026)
- 31 March 2026: the enforcement director named insider trading as the first of five priorities. Source: [Sullivan & Cromwell](https://www.sullcrom.com/insights/memo/2026/April/CFTC-Updates-Enforcement-Priorities-Cooperation-Policy-Prediction-Markets-Insider-Trading)
- The CRS notes the CFTC has said its rule does not ban all trading on secret information. The ban covers information used in breach of a duty. Source: [CRS](https://www.congress.gov/crs-product/LSB11406)
- 13 August 2026: NPR reported a CFTC review of mention markets. Kalshi removed its sports mention markets during the review. Source: [NPR](https://www.npr.org/2026/08/13/nx-s1-5930689/cftc-probe-mention-markets-prediction-markets-kalshi)
- 22 September 2026: CFTC Staff Advisory 26-27 says mention markets may be "presumptively readily susceptible to manipulation". Exchanges must make a stronger case to list them. It does not ban them. Source: [Government Enforcement Report](https://www.governmentenforcementreport.com/2026/10/cftc-issues-staff-advisory-on-prediction-market-contracts-tied-to-individual-conduct/)
- H.R. 7004, the Public Integrity in Financial Prediction Markets Act of 2026, is pending. Mitts and Ofir say it would do little for the cases they found. Source: [Harvard Law School Forum](http://corpgov.law.harvard.edu/2026/03/25/from-iran-to-taylor-swift-informed-trading-in-prediction-markets/)
- Academy members who vote on the Oscars are barred from Oscars markets (a platform rule). Source: [Foley & Lardner](https://www.foley.com/insights/publications/2026/05/insider-predicting-cftcs-first-action-and-how-we-got-here/)

### Inferences
- The two Polymarket changes pull in opposite directions. The fee hurts takers, including latency bots. Removing the 500 ms delay helps the very fastest takers and hurts slow market makers. The result is fewer, faster players and more reward for being a maker.
- Kalshi has strong money reasons to keep fast crypto markets open. About 80% of its non-sports fees come from them. Expect tuning, not shutdown.
- Insider edges are fading for the obvious cases (government secrets, own-candidacy bets), because criminal charges now exist. Subtle research edges, like Théo's, remain legal under the CFTC's current view.

### Gaps
- A 45% drop in weekly 15-minute volume from 16 February 2026 appeared in a search snippet. It could not be tied to a named outlet, and it conflicts with crypto.news saying "no visible slowdown".
- No venue-published split of 5-minute vs 15-minute volume before and after fees.
- Kalshi reportedly filed to allow delays on some orders, and Crypto.com reportedly holds regular users' sports orders for 3 seconds while market makers trade with no pause. Both appeared only in a search summary without a clear outlet.
- Search snippets said Polymarket hired a former FBI official to build surveillance software. No citable outlet was found.
