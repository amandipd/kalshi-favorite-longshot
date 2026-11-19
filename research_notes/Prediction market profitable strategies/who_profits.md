# Who actually makes money on prediction markets (as of 25 Oct 2026)

Plain words used throughout:
- **Maker**: a trader who posts a resting order and waits for someone to hit it. Market makers do this on both sides.
- **Taker**: a trader who hits an order already on the book. Most retail users are takers.
- **Realized P&L**: profit or loss on positions that were sold or settled. Open bets are left out.
- **Redemption**: cashing in winning shares after a market settles.
- **Wallet / address**: one Polymarket account on the blockchain. One person can own many, so wallet counts are not people counts.
- **In-sample**: scored on the same data used to pick the rule or the wallet. Flatters results.
- **Out-of-sample**: scored on data the rule never saw while being built. The honest test.
- **Persistence**: whether last month's winners keep winning next month.
- **Vendor flag**: the source sells a product (copy-trading bot, terminal, course, surveillance). Treat its numbers with care.

---

## 1. What share of traders profit, and how concentrated are the profits?

### Takeaway
Every large study since late 2024 says the same thing. Most Polymarket wallets lose (roughly 70% to 84%, depending on method). A tiny group takes most of the profit: the top 1% of winners take about 75% to 85% of gains, and the top 0.1% take one half to two thirds. Kalshi says about 2 in 3 of its users lose; outside estimates of long-run winners are far lower (about 2% to 5%).

### Cited findings

**Polymarket: share profitable (newest first)**
- Andrey Sergeenkov, independent on-chain researcher. Data as of 1 Apr 2026. 2.5 million addresses. 84.1% lost money. Fewer than 16% had any positive return. Only 2% made over $1,000 lifetime. Only 840 addresses (0.033%) made over $100,000. Sources: [TechFlow summary, 8 Apr 2026](https://www.techflowpost.com/en-US/article/31018); [KuCoin flash](https://www.kucoin.com/news/flash/84-of-polymarket-traders-are-losing-money-0-033-capture-majority-profits)
- Sergeenkov says the loss rate rose from about 70% (earlier studies) to 84% mainly because he also counted "splits" and "merges" (ways of creating and redeeming share pairs) that earlier studies missed. Source: [TechFlow](https://www.techflowpost.com/en-US/article/31018)
- Sergeenkov monthly tiers (average month): 1.25% of addresses made over $1,000 that month; 0.26% (about 6,600) over $5,000; 0.13% (3,250) over $10,000. Of the about 6,600 who made over $5,000 in a month, 53% were active for only one month. Only 2.6% traded continuously for over a year. Source: [TechFlow](https://www.techflowpost.com/en-US/article/31018)
- Wall Street Journal analysis, early May 2026. 1.6 million accounts active since Nov 2022. More than 70% lose money. Just 0.1% of accounts (fewer than 2,000) captured 67% of all profits, nearly $500 million. The bottom 10% of traders are down about $4,000 each on average. Sources: [Benzinga on WSJ](https://www.benzinga.com/markets/prediction-markets/26/05/52251195/0-1-of-polymarket-accounts-take-home-67-of-all-profits-investigation-finds); [WSJ on X](https://x.com/WSJ/status/2051121338253754495); [Crypto Times, 5 May 2026](https://www.cryptotimes.io/2026/05/05/wsj-just-0-1-of-polymarket-accounts-captured-67-of-all-profits/)
- Akey, Grégoire, Harvie, Martineau, "Who Wins and Who Loses in Prediction Markets? Evidence from Polymarket" (HEC Montréal, Toronto, ESSEC; CEPR DP21615; SSRN 6443103). Latest version: 588 million trades, $67 billion volume. About 69% (68.8%) of users end with a loss. The top 1% of winners capture 76.5% of profits. The top 1% of losers carry 68.1% of losses. Sources: [CEPR listing](https://cepr.org/publications/dp21615); [SSRN](https://dx.doi.org/10.2139/ssrn.6443103); [search summary of latest version via OSC PDF](https://www.osc.ca/sites/default/files/2026-10/research-grant-competition-2026-who-wins-and-who-loses-in-prediction-markets.pdf)
- Same paper, earlier draft (reported 15 Apr 2026): 1.4 million users, $20 billion, 70 million trades, 2022 to 2025. About 71% lose. Top 1% take about 84% of gains. Top 0.1% take nearly 60%. Average user places about 63% of trades at extreme prices. Longshot buyers and heavy traders are more likely to lose. Source: [Globe and Mail, 15 Apr 2026](https://www.theglobeandmail.com/investing/personal-finance/article-the-investors-profiting-from-prediction-markets-the-top-1-of-course/)
- Conflict: the top-0.1% share differs across versions and reports (51.2% in the OSC-hosted version per a search summary; 58.5% in a secondary blog; "nearly 60%" in the Globe draft). The PDF could not be opened (403 error). Sources: [OSC PDF](https://www.osc.ca/sites/default/files/2026-10/research-grant-competition-2026-who-wins-and-who-loses-in-prediction-markets.pdf); [Globe and Mail](https://www.theglobeandmail.com/investing/personal-finance/article-the-investors-profiting-from-prediction-markets-the-top-1-of-course/)
- Bloomberg analysis, 28 Apr 2026. Every active wallet from Jan 2025 to Apr 2026. More than 100,000 wallets lost at least $1,000, nearly double the number that gained $1,000. About 800 "bot-like" wallets each made over $100,000, about $131 million in total. Strip them out and everyone else is down a combined $131 million, roughly a mirror image. Sources: [Newser on Bloomberg, 10 May 2026](https://www.newser.com/story/388532/polymarkets-biggest-winners-arent-human.html); [Finance Magnates on Bloomberg](https://www.financemagnates.com/fintech/100000-polymarket-wallets-lost-at-least-1000-bloomberg-analysis-shows/)
- DeFi Oasis on-chain analysis, data to 28 Dec 2025 (OLDER). 1,733,785 addresses. About 70% show realized losses, about 30% realized profits. Fewer than 0.04% of addresses hold over 70% of realized profits (stated as about $3.7 billion). Making $1,000 puts you in the top 4.9%. 63.5% of addresses lost between $0 and $1,000. About 140 to 149 addresses lost over $1 million each. Sources: [Finance Magnates](https://www.financemagnates.com/forex/70-of-prediction-market-traders-are-capital-donors-matching-cfd-losses); [DeFi Rate](https://defirate.com/news/polymarkets-loss-stats-hide-a-different-reality/); [Coin360](https://coin360.com/news/polymarket-traders-losses-profit-concentration-2026-predictions)
- Thorsten Meyer on-chain study (OLDER, Apr 2024 to Dec 2025, 86 to 95 million transactions): only 0.51% of wallets made over $1,000. Non-academic and syndicated across many low-quality sites; the transaction count differs between reprints. Source: [Idea Magazine reprint](https://theideamagazine.com/business-industry/are-polymarket-trading-bots-actually-profitable-the-math-behind-2026-s-predictio/) (via search summary; not opened)
- Conflict on "share over $1,000": 0.51% (Meyer), 2% (Sergeenkov), 4.9% (DeFi Oasis). Different time spans, methods and wallet filters. Not comparable.
- Layerhub snapshot, Oct 2024 (OLDEST, before the election settled). 171,113 wallets. 12.7% (21,730) profitable. Only 2,138 made over $1,000. Sources: [Decrypt, Nov 2024](https://decrypt.co/290625/most-polymarket-traders-have-lost-money); [Cryptometer](https://www.cryptometer.io/news/only-12-7-of-polymarket-users-report-profits/)
- Solidus Labs, Polymarket politics markets only, Dec 2025 to Feb 2026 (reported 29 Apr 2026). 0.55% of profitable maker wallets took 50% of maker gains. 0.26% of winning taker wallets took nearly the same share. About $8 million of about $16 million went to each group. About 15% of volume in some markets looked like wash trading (trading with yourself). Vendor flag: Solidus sells the HALO surveillance tool and has a deal with Kalshi. Source: [CoinDesk, 29 Apr 2026](https://www.coindesk.com/markets/2026/04/29/a-tiny-group-is-winning-on-polymarket-as-under-1-of-wallets-take-half-the-profits)
- A London Business School and Yale paper (cited by CoinDesk) found about 3% of Polymarket traders drive most price discovery. Source: [CoinDesk](https://www.coindesk.com/markets/2026/04/29/a-tiny-group-is-winning-on-polymarket-as-under-1-of-wallets-take-half-the-profits)
- Vultax, 18 Jun to 14 Jul 2026, 9,902 wallets with closed trades. Top 1% of winners (36 wallets) took 43.9% of realized gains. Top 10% (351 wallets) took 79.5%. Vendor flag: sells a trading terminal and copy-trading calculator. Data flaw: it excludes settlement payouts, so it shows $783,051 of gains against only $15,371 of losses. That undercounts losses badly. Source: [Vultax, 11 Sep 2026, updated 25 Oct 2026](https://vultax.com/research/best-polymarket-traders-leaderboards)
- Vultax activity split, July 2026: one-trade wallets were profitable 12.2% of the time; 6 to 20 trades, 63.7%; 100+ trades, 65.9%. Same caveat on undercounted losses. Source: [Vultax](https://vultax.com/research/best-polymarket-traders-leaderboards)
- Polycopy (copy-trading app, vendor flag): about 23% of wallets with at least five resolved trades show positive lifetime realized P&L. Source: [Polycopy](https://polycopy.app/best-polymarket-traders) (via search summary; not opened)
- Filtered sample: 77.9% of 1,508 wallets that placed a $25,000+ bet are net profitable. Big bettors only; does not generalize. Source: [USLuck repost of Reddit OC](https://www.usluck.com/899299/oc-77-9-of-the-1508-polymarket-wallets-that-have-placed-a-25000-bet-are-net-profitable/)

**Kalshi: share profitable**
- Kalshi's own numbers, all 2026. May (to WSJ): 2.9 unprofitable users for every profitable one, using the past month only. That implies about 26% profitable that month. June: COO Luana Lopes Lara said about 70% of prediction-market users lose, versus 95% in other gambling. July (to Axios): CEO Tarek Mansour said "⅔ of people on Kalshi lose money." Source: [How Gambling Works Substack](https://howgamblingworks.substack.com/p/are-30-of-kalshi-users-really-profitable)
- Conflict: one search summary of the WSJ story says the "2.9 to 1" line came from a Polymarket spokeswoman. The Substack says Kalshi gave it. Check the WSJ original. Sources: [search summary of WSJ coverage](https://finance.yahoo.com/markets/options/articles/prediction-markets-hit-milestones-most-042140220.html); [Substack](https://howgamblingworks.substack.com/p/are-30-of-kalshi-users-really-profitable)
- Critique of the monthly figure: 31 days of $100 red bets on single-zero roulette gives a 43.97% chance of a winning month. So 26% winning on Kalshi in a month is worse than roulette. A 50/50 Kalshi contract has about −3.4% expected return after taker fees, versus −2.7% per roulette spin. Source: [How Gambling Works](https://howgamblingworks.substack.com/p/are-30-of-kalshi-users-really-profitable)
- Informal poll of more than a dozen traders, staff and analysts: long-run share of profitable Kalshi users is 1% to 10%, mostly 2% to 5%. For regular users nobody guessed above 1%. One journalist's poll, not a study. Source: [How Gambling Works](https://howgamblingworks.substack.com/p/are-30-of-kalshi-users-really-profitable)
- Roosevelt Institute (Lipton and Odusola, 7 Jul 2026). Kalshi from launch (Jul 2021) to 15 May 2026: over 400 million trades, over $32 billion volume, mean bet $75.20. Net retail (taker) losses: $583.5 million. Sports: $371.6 million. Exotics: over $100 million. Mention markets: $16 million. Parlays Jan to Apr 2026: about $117 million (Sportico). 63.2% of all taker winnings came from just 6.3% of matched orders (those worth $200+). Median prediction-market user loses 8% of the amount bet, versus 5% at sportsbooks. Source: [Roosevelt Institute](https://rooseveltinstitute.org/blog/since-kalshis-launch-ordinary-users-have-lost-half-a-billion-dollars/)
- Note on direction: a fetched summary of the Roosevelt page said wealth flows "from makers to takers." Becker's data (below) and the $583.5 million taker loss both say the flow is from takers to makers. Treat the summary wording as an error and check the original.
- WSJ (May 2026): in Kalshi "mention" markets, the average "yes" bettor loses 11% of what they bet. Source: [Crypto Times on WSJ](https://www.cryptotimes.io/2026/05/05/wsj-just-0-1-of-polymarket-accounts-captured-67-of-all-profits/)
- Data access: Dune switched off its public Kalshi tables on 15 May 2026, two days after a Sportico story on parlay losses. Kalshi data now sits behind a $40,000 paywall (from 20 May 2026). Dune denies a link to the story. Independent Kalshi studies are now harder. Source: [Roosevelt Institute](https://rooseveltinstitute.org/blog/since-kalshis-launch-ordinary-users-have-lost-half-a-billion-dollars/)
- Rivo (vendor flag: $9/week subscription and a bot builder with live copying): of 15,808 Kalshi traders it tracks with 10+ settled bets, 35% are in profit, and the top tenth holds 81% of profit. Only traders with public profiles; this figure came from a search excerpt, and the page was not opened. Source: [Rivo learn page](https://rivo.markets/learn/how-to-make-money-on-kalshi)

### Inferences
- The "share who profit" number swings from 12.7% to 35% mostly because of method. Studies that count small or one-off users, splits/merges, and settlement losses land at 16% or below. Studies that filter for active or large traders land higher.
- Concentration is the stable finding. Every method puts most of the profit in well under 1% of wallets.
- Big monthly earners mostly vanish. Over half of $5,000-a-month wallets were active only one month (Sergeenkov). That points to luck or one-off events, not repeatable skill.
- Kalshi's "1 in 3.9 profitable" is a one-month number. Over a year, the share is almost surely much lower.

### Gaps
- No independent, full-population Kalshi study after Dune's paywall (May 2026). Kalshi has no public wallet data.
- Wallet counts overstate the number of people. No study links wallets to real people.
- The final published version of the Akey et al. paper could not be opened (403). The top-0.1% figure stays unresolved.
- The original Bloomberg and WSJ articles could not be opened (paywalled or 403). Figures come from secondary reports.

---

## 2. What do the top Polymarket leaderboard traders actually do?

### Takeaway
Top earners fall into four groups. (1) Liquidity providers and high-frequency bots that post resting orders and earn small amounts on huge volume. (2) Research-heavy event traders like Domer. (3) A few huge one-off directional bets, like the 2024 "Trump whale." (4) Arbitrage bots and, at the edges, suspected insiders. The academic evidence says winners mostly use limit orders (makers), and losers mostly use market orders (takers).

### Cited findings

**What the data says winners do**
- Akey et al. (2026): successful traders provide liquidity with limit orders that resolve in their favour. Losing traders take liquidity with market orders. Insider trading is unlikely to explain the biggest winners. Sources: [CEPR](https://cepr.org/publications/dp21615); [SSRN](https://dx.doi.org/10.2139/ssrn.6443103)
- Bloomberg (28 Apr 2026): the about 800 wallets that made $100,000+ trade more often, in more markets, and enter earlier at better prices. Source: [Newser on Bloomberg](https://www.newser.com/story/388532/polymarkets-biggest-winners-arent-human.html)
- Unconfirmed secondary claim: the top 1% of bot accounts took over 80% of profits; retail picked the right side about 55% of the time versus about 52% for bots. That would mean bots win on price and timing, not on better forecasts. It was not confirmed against Bloomberg. Source: [Cryptorank summary via search](https://cryptorank.io/news/feed/490b8-polymarket-users-lose-money-bots)
- Arbitrage: IMDEA Networks study (Saguillo, Ghafouri, Kiffer, Suarez-Tangil; AFT conference, Oct 2025) of Apr 2024 to Apr 2025. About $40 million in realized arbitrage profit. Two kinds: inside one market (prices of all outcomes not adding to $1) and across linked markets. One wallet made about $2 million over 4,049 trades (about $496 a trade). Sources: [arXiv](https://arxiv.org/html/2508.03474v1); [IMDEA](https://networks.imdea.org/whatsnew/events-agenda/unravelling-the-probabilistic-forest-arbitrage-in-prediction-markets/); [TechFlow for the per-wallet figure](https://www.techflowpost.com/en-US/article/31018)

**Leaderboard audits (blog analyses, treat as indicative)**
- Leolabs audit of the top 20 sports and top 20 crypto wallets, Jan to Mar 2026, 100,000+ trades. 14 of 18 sports wallets only buy and hold to settlement. 3 of the top 5 crypto wallets are market-making bots. At least 3 separate wallets run the same Bitcoin 5- and 15-minute pattern. Claims over 70% of crypto arbitrage profit goes to bots with under 100 milliseconds of delay. Source: [Leolabs](https://leolabs.me/blog/pm-top20-strategy-patterns/en/)
- Leolabs examples: "swisstony" traded $494 million for a 1% return, about $4.96 million profit, 353 orders in 30 minutes. "kch123" (sports #1) had $10.35 million lifetime profit but lost $479,000 in the 30 days to mid-March 2026, with a 15-win, 33-loss week. "fengdubiying" got 93.6% of its money from redemptions; largest position $1.58 million. A crypto market maker ("0x8dxd") had 94% balanced trades and a median position under $6. Source: [Leolabs](https://leolabs.me/blog/pm-top20-strategy-patterns/en/)
- Deadspin (11 Jun 2026; affiliate-style page) top Polymarket sports traders: swisstony about 54% win rate on about 216,000 sports bets, about $9.5 million profit. RN1 55%, $9.49 million. GamblingIsAllYouNeed 53.3%, $4.78 million, about 98,300 positions. Countryside 48.7%, about $3.5 million. Figures from Polymarket profiles, not audited. Source: [Deadspin](https://deadspin.com/prediction-markets/trending/top-5-best-prediction-market-sports-traders/)
- Leaderboard leaders as of late Oct 2026 (snapshots, conflicting): Rivo lists "joseph00677" at $12.4 million (updated 23 Oct 2026); Polymarket's own board showed "BreakTheBank" at about $7.1 million. Sources: [Rivo](https://rivo.markets/polymarket-leaderboard); [Polymarket leaderboard](https://polymarket.com/leaderboard)
- One profile says swisstony compares DraftKings odds with Polymarket and buys when Polymarket is cheaper. Unverified. Source: [search summary of profile sites](https://www.predictengine.ai/blog/top-sports-bettors-polymarket)

**Domer (Polymarket "ImJustKen" / "JustKen")**
- Oct 2024 interview (OLDER): #1 all-time on Polymarket by volume and profit at the time. Over 5,000 markets and nearly $300 million volume. Most of his trades are his resting orders being filled, not orders he sends at market. All manual. Sizes bets to edge: no edge, no bet; small edge, small bet. Likes brand-new or unprecedented markets where nobody has a head start. Says medium bets in thin markets are riskiest. Loses slightly more bets than he wins but makes more money than he loses. Says arbitrage gets competed away fast. Source: [On Chain Times, 9 Oct 2024](https://www.onchaintimes.com/a-chat-with-domer-the-1-trader-on-polymarket/)
- Jan 2026 interview: nearly 10,000 predictions, $2.5 million+ net profit, about $100,000 made 22 to 28 Dec 2025. About 8,000 of his bets are small. Reviews hundreds of markets a day; nine in ten look fairly priced. Calls his method "opinion arbitrage." Aims to be right about 60% of the time. For big bets, he contacts people involved in the event. Uses Twitter and Discord alert bots, still trades by hand, hopes to automate within a year. Source: [MetaMask, 13 Jan 2026](https://metamask.io/news/advanced-prediction-market-trading-strategies)
- Conflict: "nearly $300 million volume" (2024) and "$2.5 million+ profit" (2026) come from different dates; the 2024 piece gives no profit total.

**"Théo," the 2024 election whale (OLDER)**
- French trader, self-described ex-banker. Bet that polls underrated Trump. Paid a major US pollster to run "neighbor polls" (asking who your neighbours will vote for, to get around shy voters). Started with four accounts and over $30 million in bets. Chainalysis later linked nine accounts and put net profit near $79 million. Other reports say $47 million or $85 million. Sources: [The Block](https://www.theblock.co/post/324996/polymarket-whale-us-election-profit-france-ban); [Casino.org](https://www.casino.org/news/polymarket-whale-funded-neighbor-surveys-to-win-85m-on-trump/); [The Free Press](https://thefp.com/p/french-whale-makes-85-million-on-polymarket-trump-win); [Cointelegraph](https://cointelegraph.com/news/top-polymarket-whale-profits-20-m-trump-victory)

**Suspected insiders (2026)**
- US strikes on Iran, 28 Feb 2026: six wallets, mostly funded within 24 hours, bought "yes" hours before. Combined net profit $989,191. Biggest made over $493,000 from about $61,000. Flagged by Bubblemaps; "insider" is inferred from timing. Source: [The Block](https://www.theblock.co/post/391650/fresh-accounts-netted-1-million-on-polymarket-hours-before-us-airstrikes-on-iran-bubblemaps)
- Iran ceasefire, Apr 2026: at least 50 accounts placed large "yes" bets before the announcement. One wallet created that morning bet about $72,000 at an average 8.8 cents. Source: [Anchorage Daily News / AP, 8 Apr 2026](https://www.adn.com/nation-world/2026/04/08/newly-created-polymarket-accounts-bet-big-on-iran-ceasefire-in-the-hours-before-trumps-announcement/)
- Maduro capture, Jan 2026: new accounts made hundreds of thousands of dollars; one turned $5,800 into $75,000. Source: [Cointelegraph](https://cointelegraph.com/news/trump-venezuela-leaker-jail-polymarket-accounts-go-quiet)

### Inferences
- By 2026 the biggest lifetime profits come from volume, not genius. Win rates near 49% to 55% on tens of thousands of bets mean thin edges times huge size.
- Lifetime leaderboard profit hides recent losses (kch123) and mixes styles. A high rank says little about whether the edge still works.
- Domer is the clearest example of a durable human edge. His process is research plus resting orders plus edge-sized bets, across thousands of markets.
- Insider-style gains are real but small next to bot and market-maker profits.

### Gaps
- No public breakdown of total profit by strategy type (market making vs arbitrage vs directional).
- No verified owner identities for the big bot wallets. Bloomberg named no firms.
- Leolabs' per-wallet audit verdicts were not listed in the article.

---

## 3. Kalshi top traders and Kalshi's own statements

### Takeaway
Kalshi has no public wallet data, so evidence is thin. It points the same way as Polymarket. Takers lose about 1.1% per trade on average and makers gain about the same. Professional market makers (Susquehanna, Jump) now sit on the other side. A few public stars exist, such as an inflation trader with over $2 million.

### Cited findings
- Becker, "The Microstructure of Wealth Transfer in Prediction Markets" (SSRN 7217640). Kalshi data to 25 Nov 2025: 72.1 million trades, $18.26 billion. Takers average −1.12% per trade; makers +1.12%. Takers lose at 80 of 99 price levels. The paper says makers win by soaking up biased order flow, not by forecasting better. Sources: [jbecker.dev](https://www.jbecker.dev/research/prediction-market-microstructure); [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7217640)
- Becker, longshot bias (cheap unlikely bets are overpriced). 5-cent contracts won 4.18% of the time. 95-cent contracts won 95.83%. At 1 cent, "yes" has about −41% expected value and "no" about +23%. "No" beats "yes" at 69 of 99 price levels. Source: [jbecker.dev](https://www.jbecker.dev/research/prediction-market-microstructure)
- Becker, maker-minus-taker gap by category (percentage points per trade): Finance 0.17, Politics 1.02, Sports 2.23, Weather 2.57, Crypto 2.69, Entertainment 4.79, Media 7.28, World Events 7.32. Source: [jbecker.dev](https://www.jbecker.dev/research/prediction-market-microstructure)
- Independent Kalshi papers agree: makers earn more than takers; both show a favourite-longshot pattern, stronger for takers. Sources: [UCD working paper WP2025_19](https://www.ucd.ie/economics/t4media/WP2025_19.pdf); [GWU working paper 2026-001](https://www2.gwu.edu/~forcpgm/2026-001.pdf)
- Brian Golden (Bloomberg, 13 Oct 2026): 44-year-old former theatre director trading from a Los Angeles garage, "not a math guy." Over $2 million profit on Kalshi economic contracts, more than three times the next public account in that category, per Kalshi dashboards Bloomberg reviewed. Sources: [Bloomberg](https://www.bloomberg.com/news/features/2026-10-13/kalshi-s-top-inflation-trader-beats-wall-street-banks-from-his-garage); [Prediction News](https://predictionnews.com/story/former-theater-director-becomes-top-inflation-trader-on-kalshi) (both via search summary; pages blocked)
- Kalshi CEO Mansour (Bloomberg TV, 24 Oct 2026): retail "Kalshi Street" is beating Wall Street at forecasting inflation. Kalshi plans CPI futures for December 2026. Source: [search summary of Bloomberg coverage](https://www.bloomberg.com/news/articles/2026-10-23/kalshi-courts-wall-street-in-bid-to-be-the-inflation-exchange-with-cpi-futures)
- Rivo's Kalshi leaderboard (vendor flag), 25 Oct 2026: top 200 public traders made about $12.6 million combined. #1 "BWmarkets" +$951,000 (mostly college football and baseball). Leaders by category are mostly sports (NFL, NBA, soccer, tennis, parlays). Only public profiles; traders with a losing last 90 days are dropped, so it is biased toward winners. Source: [Rivo Kalshi leaderboard](https://rivo.markets/kalshi-leaderboard)
- Kalshi Trading, the in-house market maker: co-founder Lopes Lara said on 28 Nov 2025 it is "not profitable" and is under 6% of sports making volume. InGame estimates about $310 million of sports trades in Nov 2025. Susquehanna is believed to be the largest outside market maker. Source: [InGame, 1 Dec 2025](https://www.ingame.com/kalshi-in-house-trading-arm-not-profitable/)
- Kalshi's statements on who profits: see Question 1 (2.9 to 1 monthly ratio; "⅔ lose"; "~70% lose vs 95% in gambling"). Source: [How Gambling Works](https://howgamblingworks.substack.com/p/are-30-of-kalshi-users-really-profitable)
- Roosevelt: Kalshi takes about 90% of US prediction-market volume (May 2026: Kalshi $6.2 billion a month vs Polymarket US $718.2 million). Sports is the biggest category by trade count (about 280 million of 400 million trades). Source: [Roosevelt Institute](https://rooseveltinstitute.org/blog/since-kalshis-launch-ordinary-users-have-lost-half-a-billion-dollars/)

### Inferences
- On Kalshi, the market maker seat is where the steady money is. A retail taker starts about 1.1% behind on average, plus fees.
- The gap is smallest in finance contracts (0.17 points). Those are the markets where a skilled outsider like Golden can compete.
- Buying the favourite side, or "no" on longshots, is where takers lose least.

### Gaps
- No full-population data on Kalshi user profitability after May 2026.
- No interviews found with Kalshi's top sports traders.
- Susquehanna's and Jump's profit or volume shares on Kalshi are not public.

---

## 4. Does copy trading (mirroring top wallets) work?

### Takeaway
The delay cost of copying is smaller than people think. One test found a copier 1 to 2 minutes late keeps about 78% of the leader's profit. The real problem is picking wallets. Past winners barely repeat. The best wallets (market makers, bots) can't be copied. Out-of-sample evidence is thin and mixed. Nearly all copy-trading content is written by people who sell copy tools.

### Cited findings
- Polbots test, 15 Oct 2026. Says it sells no copy trading but lists paid tools (e.g. Whalidate from $49/month). Started with 407 wallets from top-100 leaderboards. Filters: still active, not a market maker, human pace (200 fills a day or fewer), 30+ markets, up over 90 days and all-time. 36 passed; 33 could be replayed over 30 days. Source: [Polbots](https://polbots.com/guides/does-polymarket-copy-trading-work)
- Polbots delay cost (in-sample): median extra cost 0.7 cents a share near-instant, 0.8 cents at 1 to 2 minutes and at 5 minutes. Copier kept 82%, 78% and 75% of the leader's profit. 21 of 33 were profitable for copiers at every delay. Leaders made 5.5% on $22.6 million of buys; copiers made 3.8% at 1 to 2 minutes and 3.3% at 5 minutes. Price impact and partial fills were not modelled. Source: [Polbots](https://polbots.com/guides/does-polymarket-copy-trading-work)
- Polbots forward test (out-of-sample, lists built 30 days earlier): pooled returns +15.3%, +15.8%, +10.3%, −5.3% across four overlapping runs. One wallet drove the +10.3% run; without it the rest returned −1.7%. Authors say the forward evidence is "too thin." Source: [Polbots](https://polbots.com/guides/does-polymarket-copy-trading-work)
- Polbots: 126 market makers in the set earned $3.75 million in rebates and $1.12 million in rewards over 90 days. Copiers can't capture that. Source: [Polbots](https://polbots.com/guides/does-polymarket-copy-trading-work)
- Persistence, population-wide (Vultax, vendor flag): from Mar 2025 to Mar 2026, a winning month was followed by another winning month only 41% to 51% of the time. Near a coin flip. Among very active wallets (10+ trades both months, 184 wallets) it was 90.5%, but that is a survivor-heavy group over two months. Source: [Vultax](https://vultax.com/research/best-polymarket-traders-leaderboards)
- Persistence, academic: monthly performance is "modestly persistent," which "may reflect selection rather than skill." Source: [CEPR DP21615](https://cepr.org/publications/dp21615) (via search summary)
- Persistence, on-chain: 53% of wallets that made $5,000+ in a month were active only that one month. Source: [TechFlow on Sergeenkov](https://www.techflowpost.com/en-US/article/31018)
- Slippage example: a guide shows the leader buying at 34 cents and copiers filling at 47 cents in a thin market. Source: [StartPolymarket](https://startpolymarket.com/strategies/copy-trading/) (via search summary)
- Crowding: when many people copy the same whale, entry prices rise with each wave, so late copiers earn far less on the same correct call. A whale who goes viral becomes a worse target. Vendor blog. Source: [Ratio](https://ratio.you/blog/crowding-copy-trade-polymarket-whale-game-theory)
- Baiting: guides describe a whale making a visible buy, letting copiers pile in, then selling into them. Some whales reportedly place misleading trades to shake off copiers. No documented case found. Source: [search summary of copy-trading guides](https://medium.com/@0xmega/how-to-copytrade-on-polymarket-full-beginners-guide-d4a398b896e9)
- Front-running: faster bots can fill within milliseconds of a leader's trade, ahead of copiers. Source: [search summary of copy-trading guides](https://startpolymarket.com/strategies/copy-trading/)
- Misleading labels: a wallet that looked like a "volatility seller" made most of its money from redemptions. An "economics market maker" had 982 buys and zero sells. Leaderboards show no risk, no drawdown and no sign of whether the edge still works. Source: [Leolabs](https://leolabs.me/blog/pm-top20-strategy-patterns/en/)
- Domer on copiers (Oct 2024): many people copy him, but many quit after a losing trade. He loses slightly more bets than he wins. Source: [On Chain Times](https://www.onchaintimes.com/a-chat-with-domer-the-1-trader-on-polymarket/)
- Polymarket has no built-in copy feature; all tools are third party. Vendor flags: Polycopy, PolySyncer, CopyOdds, Whalidate, Rivo (bot builder with live copying), Stand (0.5% copy fee). Sources: [PolySyncer](https://www.polysyncer.com/); [CopyOdds](https://polymart.app/copyodds); [Whalidate](https://polymart.app/whalidate); [Rivo](https://rivo.markets/kalshi-leaderboard)

### Inferences
- Copying fails mainly on selection, not speed. Most wallets that look great over 30 days are lucky or one-event winners.
- Copiers inherit a wallet's taker-side trades but not its maker rebates or its hedges. So the copied return is worse than the leader's real return.
- Copying a market maker or a sub-second arbitrage bot is impossible. They are often the top of the leaderboard.
- Copiers of a known wallet may become the liquidity that wallet sells into.

### Gaps
- No independent, audited study of live copy-trading accounts after slippage and fees.
- No documented case of a whale deliberately baiting copiers.
- No study measuring how many top wallets hedge on another venue (e.g. Kalshi), which would make their Polymarket P&L look better or worse than it is.
- Polbots' forward test is four overlapping runs. Too few to settle the question.

---

## 5. Betfair: what the long record shows

### Takeaway
Betfair's own pricing tells the story. It has had to add special charges for a tiny group of very profitable accounts since 2008: under 0.5% of members at first. In 2025 it replaced the Premium Charge with an "Expert Fee" of up to 40% of profits. In one year (2012), about a quarter of active customers ended in profit. Long-run winners are far fewer.

### Cited findings
- Betfair launched in 2000. The Premium Charge started in Sept 2008. Accounts that paid commission below 20% of gross profits, after 250+ markets, had to pay extra up to 20%. Betfair said under 0.5% of members would be affected. Sources: [Wikipedia: Betfair](https://en.wikipedia.org/wiki/Betfair) (citing The Independent and Racing Post, 2008); [Racing Post, 18 Dec 2024](https://racingpost.com/news/britain/betfair-exchange-to-introduce-new-commission-system-for-2025-as-premium-charge-is-dropped-a7wbg0v4GCAJ)
- June 2011: Betfair raised the charge to up to 60% for some very profitable, frequent users. It "was met by outrage." The Guardian said Betfair could no longer present itself as a neutral exchange "where winners are welcome." Source: [Wikipedia: Betfair](https://en.wikipedia.org/wiki/Betfair) (citing The Guardian, 2008 and 2011)
- Premium Charge payments were not refunded if an account later turned unprofitable. Source: [Wikipedia: Betfair](https://en.wikipedia.org/wiki/Betfair)
- Expert Fee from 6 Jan 2025, based on gross profit over a rolling 52 weeks: under £25,000, nothing extra; £25,000 to £100,000, 20%; over £100,000, 40%. Betfair says it is paid by "a very small number of the most profitable customers." It also claims 80% of players see lower fees and 50% pay no extra fees (company claim; unclear base group). Source: [Racing Post, 18 Dec 2024](https://racingpost.com/news/britain/betfair-exchange-to-introduce-new-commission-system-for-2025-as-premium-charge-is-dropped-a7wbg0v4GCAJ)
- Betfair 2012 Annual Report: "almost 200,000" customers were net winners in the last financial year, about a quarter of active customers. One-year company figure, not long-run. Source: [Betfair Annual Report 2012](https://media.investis.com/B/Betfair/PDFs/Annual-Reports/Betfair_Annual_Report_2012.pdf) (via search summary)
- Betfair says it needs long-term winning traders because they provide the liquidity that recreational users trade against. Source: [Traderline explainer](https://traderline.com/education/betfair-premium-charge-explained) (vendor flag: trading software/education)
- A CEPR paper using Betfair soccer bets predicts and tests that makers (who post odds) earn more than takers (who accept them). Same pattern as Kalshi. Source: [CEPR DP20633](https://cepr.org/publications/dp20633) (abstract via search; page blocked)
- Conflict: one search summary claimed Betfair said only 0.1% of its 3.8 million users would pay the charge. Wikipedia says under 0.5%. No source for the 0.1% figure was found. Source: [Wikipedia: Betfair](https://en.wikipedia.org/wiki/Betfair)
- Thresholds and rates differ across explainer sites (20% to 60% top rate; £1,000 or £250,000 lifetime floors). Several of these sites sell trading courses (e.g. Caan Berry). Use Betfair's own terms or the Racing Post. Sources: [Betfairsquare](https://betfairsquare.com/guides/betfair-premium-charge); [Caan Berry](https://caanberry.com/betfair-premium-charge-how-its-calculated/)

### Inferences
- Betfair's 25-year record shows a stable, tiny class of long-run winners: pro traders, market makers and modellers. It was small enough (under 0.5%) that Betfair could tax it heavily without hurting volume.
- An exchange charging its best customers up to 60% shows they had a lasting edge over everyone else. That is the likely long-run path for Kalshi and Polymarket, too.
- One-year "a quarter in profit" (Betfair 2012) matches Kalshi's "1 in 3.9 per month." Short windows make far more people look like winners than truly are.

### Gaps
- No independent study of Betfair account profits over many years.
- Betfair has not published how many customers pay the Expert Fee.
- The Betfair maker/taker paper could not be opened to get its numbers.

---

## 6. How has the profitable crowd changed from 2024 to 2026?

### Takeaway
In 2021 to 2023, Kalshi takers actually made money, because the other side was mostly amateurs. After Kalshi's legal win and the 2024 election boom, professional market makers arrived and the flow reversed. By 2026, profits on both venues go mainly to market makers and high-frequency bots. Firms like Susquehanna and Jump now provide liquidity, sometimes for equity. The 2024 headline winners were a few big directional bettors. The 2026 winners are mostly machines.

### Cited findings
- Becker: on Kalshi from 2021 to 2023, takers averaged +2.0% and makers −2.0%. After the 2024 election, makers were ahead by 2.5 points: a 5.3-point swing. Kalshi beat the CFTC in court in Oct 2024. Quarterly volume rose from $30 million (Q3 2024) to $820 million (Q4 2024). Pre-2024 makers were "likely unsophisticated individuals"; post-2024 makers look professional. Source: [jbecker.dev](https://www.jbecker.dev/research/prediction-market-microstructure)
- Susquehanna became Kalshi's first dedicated institutional market maker in 2024. Sources: [search summary of trade press](https://www.tradermath.org/articles/prediction-markets-trading-at-quant-firms); [InGame](https://www.ingame.com/kalshi-in-house-trading-arm-not-profitable/)
- Jump Trading, Feb 2026: to take equity in Kalshi (fixed) and Polymarket (scaling over time) in return for providing liquidity. Jump doubled its prediction-market team to about 20 in 2026. DRW, Wintermute and Akuna are also building desks. DRW/Akuna details are less well sourced. Sources: [The Block on Bloomberg](https://www.theblock.co/post/389086/jump-trading-to-serve-as-polymarket-and-kalshi-market-maker-in-exchange-for-stake-bloomberg); [Crypto Briefing](https://cryptobriefing.com/jump-trading-prediction-markets-wall-street/); [TraderMath](https://www.tradermath.org/articles/prediction-markets-trading-at-quant-firms)
- Polymarket added taker-only fees to 15-minute crypto markets in early Jan 2026 to fund daily maker rebates. Fees peak at 50 cents (about 3% of trade value in Polymarket's example) and shrink toward 0 and 100 cents. Later extended to 5-minute crypto, NCAAB and Serie A. Commentators expected pure-taker bots to shrink and maker bots to grow; no measured result was found. Sources: [The Block](https://www.theblock.co/post/384461/polymarket-adds-taker-fees-to-15-minute-crypto-markets-to-fund-liquidity-rebates); [Polymarket docs](https://docs.polymarket.com/developers/market-makers/maker-rebates-program); [Cointelegraph](https://cointelegraph.com/news/polymarket-quietly-adds-taker-fees-15-minute-crypto-markets)
- Bloomberg, Apr 2026: about 800 bot-like wallets took about $131 million since Jan 2025, matching retail's net loss. Source: [Newser on Bloomberg](https://www.newser.com/story/388532/polymarkets-biggest-winners-arent-human.html)
- 2024 (OLDER): the top profits were directional election bets. Théo's accounts made about $79 million (Chainalysis). Domer was #1 all-time by manual research. Sources: [The Block](https://www.theblock.co/post/324996/polymarket-whale-us-election-profit-france-ban); [On Chain Times](https://www.onchaintimes.com/a-chat-with-domer-the-1-trader-on-polymarket/)
- 2026: sports leaderboard leaders place tens to hundreds of thousands of bets (swisstony about 216,000) at 49% to 55% win rates. Top crypto wallets are mostly market-making bots. Sources: [Deadspin](https://deadspin.com/prediction-markets/trending/top-5-best-prediction-market-sports-traders/); [Leolabs](https://leolabs.me/blog/pm-top20-strategy-patterns/en/)
- Loss rates rose as studies got more complete and the user base grew: 87.3% unprofitable wallets (Oct 2024 snapshot, pre-settlement), about 70% (Dec 2025), 84.1% (Apr 2026). Method changes explain much of the rise. Sources: [Decrypt](https://decrypt.co/290625/most-polymarket-traders-have-lost-money); [Finance Magnates](https://www.financemagnates.com/forex/70-of-prediction-market-traders-are-capital-donors-matching-cfd-losses); [TechFlow](https://www.techflowpost.com/en-US/article/31018)
- Scale in 2026: Polymarket about 462,600 monthly active traders and about $9.8 billion 30-day volume (Token Terminal, Apr 2026). Kalshi about $6.2 billion a month in May 2026 and an annualised pace near $1 trillion by Oct 2026. Sources: [TechFlow](https://www.techflowpost.com/en-US/article/31018); [Roosevelt Institute](https://rooseveltinstitute.org/blog/since-kalshis-launch-ordinary-users-have-lost-half-a-billion-dollars/); [search summary of Bloomberg coverage](https://www.bloomberg.com/news/articles/2026-10-23/kalshi-courts-wall-street-in-bid-to-be-the-inflation-exchange-with-cpi-futures)
- Insider-style trading grew as a political issue in 2026 (Maduro, Iran strikes, Iran ceasefire). Bipartisan bills would extend insider-trading law to prediction markets. Source: [Anchorage Daily News / AP](https://www.adn.com/nation-world/2026/04/08/newly-created-polymarket-accounts-bet-big-on-iran-ceasefire-in-the-hours-before-trumps-announcement/)

### Inferences
- The same arc as Betfair, but faster. Early on, amateurs face amateurs and some takers win. Once volume is big enough, pros take the maker seat and takers pay them.
- Taker fees plus maker rebates (Polymarket 2026) push more profit toward market makers. Pure taker strategies now need a bigger edge to survive.
- A human edge still exists in niches where pros' models are weak: thin, new or unusual markets (Domer), and specialist topics like CPI (Golden).

### Gaps
- No before-and-after data on how Polymarket's 2026 taker fees changed bot profits.
- No public data on market makers' actual profits on either venue (except Kalshi Trading "not profitable").
- No study tracks the same set of wallets across 2024 to 2026 to show who left and who stayed.
