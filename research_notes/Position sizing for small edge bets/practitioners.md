# How practitioners actually size bets: syndicates, sports-betting pros, Betfair traders, and prediction-market traders (Kalshi, Polymarket)

Research date: 2026-10-14. Evidence labels used throughout:
- **[Primary]**: the person's or firm's own words, an exchange filing, or a peer-reviewed or working paper read directly.
- **[Secondary]**: reputable press or a book summary reporting on the primary.
- **[Anecdote]**: single-trader claims, X/Twitter threads relayed by crypto press, forum or blog posts, or on-chain figures that could not be verified.

---

## 1. Syndicates and named operators (Benter, Woods, Walters, Voulgaris, Starlizard/Bloom, Computer Group)

### Takeaway
The best-documented case is Bill Benter. In his own 1994 paper he calls full Kelly "unwise" and recommends a fractional Kelly of about 1/2 or 1/3. He gives three reasons: edge estimates are easily wrong by a factor of two, withdrawals shrink effective wealth, and full Kelly routinely brings drawdowns of more than 50%. He also says a successful operation soon finds that market impact, not bankroll, caps every bet. Billy Walters' published rule is a 1% unit with a hard cap of 3 units (about 3% of bankroll) per event, scaled by edge. For Voulgaris, Starlizard and the Computer Group, no per-bet sizing is published, only turnover and profit figures.

### Cited findings

**Bill Benter (Hong Kong racing): his 1994 paper, read from the scanned original**
- [Primary] Benter on Kelly: "In the author's experience, betting the full amount recommended by the Kelly formula is unwise for a number of reasons. Firstly, accurate estimation of the advantage of the bets is critical; if one overestimates the advantage by more than a factor of two, Kelly betting will cause a negative rate of capital growth. (As a practical matter, many factors may cause one's real-time advantage to be less than past simulations would suggest, and very few can cause it to be greater. Overestimating the advantage by a factor of two is easily done in practice.)" Source: [Benter, "Computer Based Horse Race Handicapping and Wagering Systems: A Report", 1994; reprinted in *Efficiency of Racetrack Betting Markets* (2008), p.191](https://www.gwern.net/doc/statistics/decision/1994-benter.pdf)
- [Primary] Benter's second and third reasons: "if it is known that regular withdrawals from the betting bankroll will be made for paying expenses or taking profits, then one's effective wealth is less than their actual current wealth. Thirdly, full Kelly betting is a 'rough ride', downswings during which more than 50% of total wealth is lost are a common occurrence. For these and other reasons, a fractional Kelly betting strategy is advisable, that is, a strategy wherein one bets some fraction of the recommended Kelly bet (e.g. 1/2 or 1/3)." Source: [Benter 1994, p.191](https://www.gwern.net/doc/statistics/decision/1994-benter.pdf)
- [Primary] Market impact caps bet size before bankroll does. "Even if the bettor possesses infinite wealth, there is a maximum bet producing the greatest expected profit, any amount beyond which lowers the expected profit." In his worked example (a $100,000 pool, a horse with a 6% model probability at a 20.0 dividend, so a 1.20 expected return), the profit-maximising bet is only **$416**, for an expected profit of **$39.60**. Betting **2/3 of that maximum ($277) still earns $35.5, which is 90% of the maximum profit**. Source: [Benter 1994, p.191](https://www.gwern.net/doc/statistics/decision/1994-benter.pdf)
- [Primary] "a successful betting operation will soon find that all of its bets are *pool-size-limited*. As a rule of thumb, as the bettor's wealth approaches the total pool size, the dominant factor limiting bet size becomes the effect of the bet on the dividend, not the bettor's wealth." Source: [Benter 1994, p.191](https://www.gwern.net/doc/statistics/decision/1994-benter.pdf)
- [Primary] Capacity ceiling: his simulations put the "maximum expected profit achievable, as a percentage of total per-race turnover" at **0.25-0.5%**, even with an effectively infinite bankroll, and "unlikely that this value could exceed 1.5 per cent". A start-up with a bankroll of about half the per-race turnover might win **0.1-0.2% of total track turnover**. Source: [Benter 1994, p.195](https://www.gwern.net/doc/statistics/decision/1994-benter.pdf)
- [Primary] What he actually ran: "A conservative fractional Kelly betting strategy was employed throughout, with wagers being placed on all positive expectation bets available in both normal and exotic pools (except place and show bets)." Hong Kong pools were above US$10M of turnover per race, he bet about **470 races a year**, and the track take was about 19%. "Four of the five seasons resulted in net profits, the loss incurred during the losing season being approximately **20% of starting capital**." Source: [Benter 1994, p.195](https://www.gwern.net/doc/statistics/decision/1994-benter.pdf)
- [Primary] Minimum-edge filters: Ziemba & Hausch (1987) suggest a minimum advantage of 10% before betting, to absorb model bias. Benter instead advocates "correcting the probabilities first and then calculating the betting advantage". Source: [Benter 1994, note 1, p.197](https://www.gwern.net/doc/statistics/decision/1994-benter.pdf)
- [Secondary] Early drawdown: in their first Hong Kong season (1985-86), Benter and Alan Woods "had lost $120,000 of their $150,000 stake", an 80% drawdown. Benter later won about $600k (c. 1988-89) and about $3M (1990-91) after he began using public odds as a model input. The teams were "up more than $50 million" in 1997, and Benter concedes the operations "probably made close to a billion dollars overall". In the November 2001 Triple Trio he "spent HK$1.6 million on the 51,000 combinations". Source: [Kit Chellel, Bloomberg Businessweek, May 2018 (course mirror)](https://sites.oxy.edu/lengyel/m150/Horse%20race%20betting%20%282018%29/The%20Gambler%20Who%20Cracked%20the%20Horse-Racing%20Code%20-%20Bloomberg.htm)
- [Secondary] Later academic summaries describe Benter's use of Kelly as fractional Kelly plus limits from his own market impact. Source: [KellyBench, arXiv 2604.27865 (2026)](https://arxiv.org/pdf/2604.27865). Another paper says fractional Kelly "has been endorsed and successfully used in practice by people such as" Benter and Thorp, and that half Kelly is "popular amongst gamblers" (citing Poundstone 2005). Source: [arXiv 1701.02814 (2017)](https://ar5iv.arxiv.org/html/1701.02814)

**Billy Walters**
- [Secondary, from his 2023 book *Gambler*] Maximum single-event bet: **3% of bankroll** (3 units), bet in half-unit steps from **0.5 to 3 units**, with size rising with perceived edge. Set the bankroll on the assumption that "you'll lose it all". Protecting the bankroll ranks above nearly everything else, and he warns against betting no-edge games to chase losses. Source: [Covers.com summary of *Gambler*, updated Aug 30, 2023](https://www.covers.com/guides/betting-tips-from-pro-sports-bettor-billy-walters)
- [Secondary] Book summary: a unit is 1% of bankroll. In the summary's worked example, a 1-2 point edge gets about half a unit (0.5%), while a 14-point discrepancy between Walters' number and the line justifies the 3-unit maximum. Source: [Shortform summary of *Gambler*](https://www.shortform.com/blog/billy-walters-sports-betting/)

**Haralabos Voulgaris (NBA)**
- [Primary, 2008] "I started out with an average bet size of around $30 bucks… Prior to making my one large bet I had already been betting for about 3-5 years." No bankroll or sizing rule is given. Source: [ESPN TrueHoop Q&A, June 13, 2008](https://www.espn.com/blog/truehoop/post/_/id/4974/following-up-with-haralabos-voulgaris)
- [Anecdote/Secondary] He reportedly put his life savings (about $70,000) on the Lakers to win the 1999-2000 NBA title, a deliberately concentrated, non-Kelly bet. Later volume of about $1M a day is claimed in blogs but unverified. Source: [Casino.org profile](https://www.casino.org/blog/wild-life-worlds-best-nba-bettor/)

**Starlizard / Tony Bloom**
- [Secondary] Bloom supplies most of the syndicate's betting money. Starlizard Consulting (set up in 2006) builds the models. Staff reportedly receive a free stake in the syndicate, with payouts "of up to £500,000 every six months". Alleged profits of about £600m a year are disputed by Bloom's lawyers as an "irrelevant exaggeration". In one court case the profit split was 60% syndicate / 33% / 7% on an account held in a third party's name, which shows betting is spread through other people's accounts. Sources: [Gambling Insider](https://www.gamblinginsider.com/news/105962/tony-bloom-denies-17-5m-betting-syndicate-claim); [iGaming Expert](https://igamingexpert.com/regions/europe/brighton-slams-guardian-gambling-reports/)

**The Computer Group (1980s, Michael Kent and Ivan Mindlin)**
- [Secondary] Kent claims that in the 1983 college football season "$23 million in wagers netted a profit of $3 million", about 13% on turnover. Their edges were "slight statistical anomalies in point spreads", so they "had to bet a great deal of money to profit", spread across offices and many bettors. They sometimes "middled" moving lines. Sources: [Wikipedia: Michael Kent](https://en.wikipedia.org/wiki/Michael_Kent_(computer_specialist)); [Must Be Moose Substack](https://mustbemoose.substack.com/p/the-computer-group-the-nerds-who)

### Inferences
- Benter's "overestimate the edge by 2x and full Kelly gives negative growth" is exact for Kelly. Expected log growth at bet size f is about f·edge − f²·variance/2, which reaches zero at twice the Kelly fraction. Betting 1/2 or 1/3 Kelly therefore protects against exactly the error he says is "easily done in practice".
- Benter's market-impact example has a direct analogue in order books. The expected-profit-versus-size curve is flat near its peak (2/3 of the size gives 90% of the profit). Trimming size to stay well inside visible depth costs little expected value and cuts slippage and adverse-fill risk.
- The named pros cluster at about 1-3% of bankroll per event (Walters), or "conservative fractional Kelly" plus liquidity caps (Benter). The exceptions are early-career all-in bets (Voulgaris), and those are survivorship stories, not practice to copy.

### Gaps
- Benter's exact operating fraction (1/2 vs 1/3 vs less) is not stated. The paper says only "conservative fractional Kelly", recommending "e.g. 1/2 or 1/3".
- No published per-bet sizing or bankroll fraction was found for Starlizard, Voulgaris, or the Computer Group, only turnover and profit claims.
- Walters' *Gambler* was not read directly. The 1%-unit and 3%-cap figures come from two consistent book summaries.

---

## 2. Common practice: what sports-betting educators and quants recommend (Pinnacle/Buchdahl, Unabated, academic reviews)

### Takeaway
The standard advice is flat 1% units, or fractional Kelly at 1/4 to 1/2 (Unabated suggests at least dividing by four), with 1/8 Kelly for very uncertain edges. Buchdahl's simulations show why. For a 2.5% edge, full Kelly has about a 10% chance of halving the bankroll, half Kelly about 1%, and third Kelly under 0.1%. Believing the edge is 5% when it is really 2.5% turns the strategy into "a coin-tossing machine".

### Cited findings
- [Primary, Buchdahl] Simulation: 1,000 point-spread bets at -110 (1.909) with a 2.5% EV, giving a full-Kelly stake of 2.75%. The most likely growth is about 1.41x. The probability of ending below the start is about **34%** for full Kelly, against about 18% for flat stakes of the same size. Source: [Joseph Buchdahl, "The Pitfalls of using Kelly Staking in Sports Betting", football-data.co.uk](https://www.football-data.co.uk/blog/kelly_staking.php)
- [Primary, Buchdahl] Overestimating the edge: believing 5% EV when it is 2.5% means staking 5.5% instead of 2.75%. That makes it "a coin-tossing machine": the most likely outcome is roughly break-even, and the chance of losing at least 90% of the bankroll rises above **8%** (from under 0.1%). A 3x overestimate gives a 66% chance of loss. Source: [Buchdahl, football-data.co.uk](https://www.football-data.co.uk/blog/kelly_staking.php)
- [Primary, Buchdahl] Fractions at a true 2.5% EV:
  - Half Kelly raises the probability of profit from 66% to 73% and cuts the most likely growth from 41% to 29%.
  - Half Kelly cuts the chance of halving the bankroll from about **10% to about 1%**.
  - Third Kelly cuts it to **under 0.1%**.
  
  His advice: "If in doubt, use a fractional Kelly plan" (half, quarter or eighth). Source: [Buchdahl, football-data.co.uk](https://www.football-data.co.uk/blog/kelly_staking.php)
- [Secondary, search-snippet level: Pinnacle pages are JavaScript-rendered and would not load in full] Pinnacle's fractional-Kelly article compares full, 1/2, 1/4 and 1/8 Kelly: a run of ten straight losses that cut the bankroll by 30% under full Kelly cost only **3.75% under eighth Kelly**. A later Pinnacle "posterior Kelly" piece suggests a prior Kelly fraction near **0.50** as a starting point, to be updated as results come in. Sources: [Pinnacle, "Applying the fractional Kelly Criterion to sports betting"](https://www.pinnacle.com/betting-resources/en/betting-strategy/revisiting-the-kelly-criterion-part-2-fractional-kelly/gbd27z9nljvgflgg); [Pinnacle, "Staking with an unknown edge"](https://pinnacle.com/en/betting-articles/educational/staking-when-you-dont-know-your-edge/qw3jfdm2rwbzumjp)
- [Primary, Unabated] "Typically 1 percent is the norm" for flat staking, which is recommended when you are unsure of your edge. For Kelly they recommend "betting just a half or a quarter of the full Kelly stake". Their advice is to double projected time-to-target to allow for uncertainty, because underbetting costs only "slower bankroll growth" while overbetting raises the "risk of ruin". Worked example: a 4% edge, 1% stakes and 10 bets a day double the bankroll in about 180 days. Source: [Unabated, "How To Build A Sports Betting Bankroll" (c. 2026)](https://unabated.com/articles/how-to-build-a-sports-betting-bankroll)
- [Primary, Unabated] Other Unabated pages say to divide Kelly by at least four (quarter Kelly), with third Kelly as the more aggressive option. They also note that for player props Kelly may not be the best method, because limits bind first. Sources: [Unabated, "Sports Betting Bankroll Management: Five Misconceptions"](https://unabated.com/articles/misconceptions-about-bankroll-management); [Unabated articles index via search](https://unabated.com/articles/how-to-win-at-sports-betting)
- [Primary, academic] "Replacing the actual values with estimates leads to overbetting" (MacLean et al., 1992); fractional Kelly is the usual fix. Source: [arXiv 1701.02814](https://ar5iv.arxiv.org/html/1701.02814). A 2023 experimental review of betting strategies found an adaptive variant of fractional Kelly "a very suitable choice across a wide range of settings". Source: [Uhrín et al., "Optimal sports betting strategies in practice: an experimental review"](https://paperswithcode.com/paper/optimal-sports-betting-strategies-in-practice)
- [Secondary] Practitioners commonly use Pinnacle's de-vigged price as the "fair" probability input for Kelly. Many tool vendors say most pros use 25% Kelly or less. These are vendor pages, so treat them as convention, not evidence. Source: [OddsPapi blog](https://oddspapi.io/blog/?p=2898)

### Inferences
- The consensus range, 1/4 to 1/2 Kelly with a hard per-bet cap of about 1-3%, is calibrated for sports edges of about 2-5% at near-even odds. At those odds full Kelly is only about 2-8% of bankroll anyway, so a 1/4-1/2 fraction lands at about 1-3%. It is the same range as Walters' units.
- The asymmetry these educators stress (underbetting costs a little growth, overbetting risks ruin) is the main argument for sizing a strategy with a short live record at 1/4 Kelly or less until the edge estimate tightens.

### Gaps
- The full text of Pinnacle's Kelly articles would not load, so the 30% vs 3.75% and the "prior near 0.50" figures come from search snippets.
- No published survey was found of the Kelly fractions professional bettors actually use. All "most pros use X" statements are educator assertions.

---

## 3. Betfair traders and bots: sizing against liquidity

### Takeaway
On Betfair, liquidity, not Kelly, sets the size. Pro traders say pre-off horse-racing stakes in the thousands of pounds visibly move the price, and in-play exit liquidity can vanish within seconds. One leading trader (2010) put about £20k through a horse race against £50-70k on a big football match. The exchange also taxes big winners directly: the premium charge was up to 60%, and the Expert Fee (from January 2025) is 20-40% of 52-week gross profit above £25k. That fee caps how far a profitable strategy can scale.

### Cited findings
- [Secondary, 2010] Peter Webb (Bet Angel) "puts around £20,000 into individual horse races, and on major football matches he can put £50,000 to £70,000 through the market", because football prices move less abruptly. Source: [The Register, Dec 6, 2010](https://www.theregister.com/2010/12/06/channel_man_turns_over_quarter_billion_on_betfair/)
- [Anecdote, trader blog, Aug 19, 2024] A professional race trader "often stakes multiple thousands of pounds" per bet. He trades only a handful of races a day, because racing liquidity is far thinner than football or cricket. Big stakes must go in pre-race, they "inevitably" move the price, so he accepts worse odds or bets at shorter odds that absorb more liquidity. In-play, prices can move against a position "within seconds" with little liquidity left to exit. He rarely lets a trade run to the result. The post cites one £80k month. The author himself prefers high-liquidity football and cricket for scaling. Source: [Anyman Trading Substack, "The 5 figure horse trader"](https://anymantrading.substack.com/p/the-5-figure-horse-trader)
- [Secondary] Liquidity is not the same as volume. Total matched volume overstates what can be matched at a given price; one trader notes some stakes "dwarf an entire individual race's liquidity". Source: [The Racing Forum thread](https://theracingforum.co.uk/forums/topic/where-is-the-money-on-exchanges/) (forum, low authority)
- [Primary, academic] Kelly sizing extended to exchanges has to handle commission and "the variability of market size", both of which Kelly's original formula ignores. Source: [IMA Journal (2013), "Kelly's fractional staking updated for betting exchanges"](https://iaorifors.com/paper/81367)
- [Secondary] Betfair's premium charge began in 2008 at 20% for the most profitable customers, rising to up to **60%** from 2011. It was replaced from **Jan 6, 2025** by the "Expert Fee" on 52-week gross profit: none below £25k, **20%** on £25k-£100k, **40%** above £100k. Sources: [Racing Post](https://racingpost.com/news/britain/betfair-exchange-to-introduce-new-commission-system-for-2025-as-premium-charge-is-dropped-a7wbg0v4GCAJ); [Wikipedia: Betfair](https://en.wikipedia.org/wiki/Betfair)

### Inferences
- Betfair traders size per trade by the visible queue at their price and by exit liquidity. The bankroll fraction is secondary. This matches Benter's "pool-size-limited" point carried over to an order book.
- Profit-based fees (Betfair's Expert Fee, and taker fees on Polymarket and Kalshi) mean the edge after costs, and so the Kelly fraction, shrinks as a strategy scales.

### Gaps
- No documented rule of thumb such as "stake at most X% of matched volume or queue depth" from a named Betfair professional was found. The evidence is qualitative.
- No public material was found on how Betfair bot operators size, beyond generic Kelly-for-exchanges papers.

---

## 4. Prediction markets: pro traders, market makers (SIG on Kalshi), and the 2024-2026 bots on 15-minute crypto markets

### Takeaway
Little sizing rulebook is published for prediction markets. The documented evidence is about who wins and loses, plus exchange rules. Large studies of Polymarket (Akey et al. 2026; Gómez-Cram et al.; Galaxy 2026) find a tiny, mostly automated, liquidity-providing minority capturing most profits. On Kalshi, makers do much better than takers, and contracts priced above about 50-70¢ show small but significant positive returns. Kalshi market makers like Susquehanna (SIG) get adjusted position limits and lower fees, but can still take large one-game losses. The 15-minute crypto bot wave (late 2025 to 2026) was latency-driven, and Polymarket answered it with taker fees in January 2026.

### Cited findings

**Kalshi: who earns what, by price (most directly relevant evidence on favourites)**
- [Primary] Data: 313,972 traded contract prices across 46,282 Kalshi contracts, 2021 to April 2025. Average loss rates for contracts at or below 10¢ are **over 60%**. Returns are "small positive" for contracts **above 50c**, and for contracts **above 70c** there is "statistically significant, though small, positive post-fee returns". Example: "A 95c contract that wins 98% of the time has a pre-fee average return of 3.1%." Source: [Bürgi, Deng & Whelan, "Makers and Takers: The Economics of the Kalshi Prediction Market" (2025/26)](https://www.karlwhelan.com/Papers/Kalshi.pdf)
- [Primary] Makers averaged **−9.64%** against **−31.46%** for takers. "On average, Makers who buy contracts costing 50c and over earn a **2.6%** rate of return." There is some evidence the favourite-longshot bias weakened in 2025 data. Sources: [Bürgi, Deng & Whelan](https://www.karlwhelan.com/Papers/Kalshi.pdf); also [CEPR DP20631](https://cepr.org/publications/dp20631)

**Kalshi market makers and limits**
- [Primary] Susquehanna Government Products (SIG) became Kalshi's first dedicated institutional market maker in April 2024. Sources: [Business Wire, Apr 3, 2024](https://www.businesswire.com/news/home/20240403664852/en/Kalshi-Onboards-Its-First-Dedicated-Institutional-Market-Maker); [Bloomberg, Apr 3, 2024](https://www.bloomberg.com/news/articles/2024-04-03/susquehanna-starts-trading-desk-for-event-contracts-on-kalshi)
- [Primary] Kalshi's market maker programme: status follows review of "financial resources, trading experience, and business reputation". Members must provide "consistent, two-sided liquidity" under quoting and volume requirements, including 98% availability in each 1-hour increment on listed products (KXBTC, KXETH, KXINX, sports, KXCPI, KXFED…). In return they may get "reduced fees and certain adjusted position limits". No numbers are published. Source: [Kalshi Help Center: Market Maker Program](https://help.kalshi.com/markets/market-maker-program)
- [Primary] Kalshi Rule 5.14(a) originally imposed **$25,000 position limits on all contracts**. The February 2023 amendment tied limits to each contract's terms instead. Source: [CFTC filing, Feb 2023](https://www.cftc.gov/filings/orgrules/rule022123kexdcm002.pdf)
- [Secondary] SIG is believed to be Kalshi's largest market maker. In the Knicks' NBA Finals Game 4 comeback (June 10, 2026) it reportedly took its biggest-ever sports loss; Jeff Yass: "it was a tough day." Market makers as a group lost about **$22.4M pre-fee** on that game, mostly from takers buying the Knicks in-game at about **5% odds**. Market makers traded $119.9M against $87.0M for takers. Source: [InGame, June 11, 2026](https://ingame.com/susquehanna-biggest-sports-kalshi-volume-knicks)

**Polymarket: who wins**
- [Primary per abstract; Secondary for figures] Akey, Grégoire, Harvie & Martineau, "Who Wins and Who Loses in Prediction Markets? Evidence from Polymarket" (SSRN, 2026):
  - Winners tend to provide liquidity with limit orders; losers take liquidity with market orders.
  - Long-shot betting is linked to concentrated losses.
  - The top 1% capture **76.5%** of profits in the SSRN version. Press reports of an earlier draft said **84%**, so the versions differ.
  - About 1,200 users (0.05%) took more than half of profits ($591M).
  
  Sources: [HEC seminar page](https://www.hec.edu/en/faculty-research/events/who-wins-and-who-loses-prediction-markets-evidence-polymarket); [Washington Post via Yahoo, May 11, 2026](https://finance.yahoo.com/markets/crypto/articles/weve-calculated-your-chances-of-winning-money-on-polymarket-155955143.html); [GIGAZINE, May 25, 2026](https://gigazine.net/gsc_news/en/20260525-polymarket-win-or-lose/)
- [Secondary] Gómez-Cram, Guo, Kung & Jensen (LBS/Yale): 1.72M accounts; only **3.14%** are "skilled winners", and together with market makers they account for over 30% of revenue. Source: [KuCoin news summary](https://www.kucoin.com/news/flash/3-14-of-polymarket-traders-account-for-30-of-profits-67-of-users-bear-all-losses)
- [Secondary] Galaxy Research (Oct 2026): **69.2%** of about 2.9M retail accounts finished below break-even. Accounts with more than 50 orders per active day (treated as bots, 125,429 accounts) made 80.8% of orders and finished **$246.8M ahead**. Only 25.1% of sports specialists were profitable. Source: [BeInCrypto via Yahoo, Oct 1, 2026](https://finance.yahoo.com/markets/crypto/articles/69-retail-polymarket-traders-finish-045227939.html)

**Named Polymarket traders**
- [Secondary] "Théo" (Fredi9999 and other accounts), 2024 US election: more than **$45M** across four accounts per Polymarket, mostly on Trump "Yes". Profit was about $79M per Chainalysis (9 accounts) or about $85M per Bloomberg (11 accounts). He based his view on private "neighbor effect" polling. This was extreme conviction sizing on one outcome, not Kelly-style diversification. Sources: [The Block](https://www.theblock.co/post/324996/french-polymarket-whale-us-election-profit-france-ban); [DL News](https://dlnews.com/articles/defi/4-crypto-whales-are-skewing-trump-polymarket-election-bet/)
- [Secondary/Anecdote] Domer: described as the #1 Polymarket trader by volume, trading political markets since 2007 with a poker background, reported at nearly $4M profit across Polymarket and Kalshi (April 2026). A podcast episode covers "bet sizing… and links to the Kelly Criterion", but the episode pages do not say what his answer was. Third-party notes say he avoids or sizes down in "mention" markets, where one person can sway the outcome. Sources: [Confessions of a Market Maker ep. listing](https://www.castfox.net/podcast/confessions-of-a-market-maker-86953/episode/the-4m-political-bettor-domer-on-18-years-of-beating-the-market-18676); [Chat With Traders](https://chatwithtraders.com/?p=3502); [thendobetter notes](https://www.thendobetter.com/investing/tag/Domer)

**15-minute (and 5-minute) crypto markets: bots and arbitrage, 2025-2026**
- [Anecdote, on-chain figures relayed by press] Wallet "0x8dxd" reportedly started in December 2025 with **$313** and reached about **$414k-$438k** profit by early January 2026, trading only BTC/ETH/SOL 15-minute up/down markets. Its reported edge was **latency**: Polymarket prices lagged confirmed spot moves on Binance and Coinbase. A 98% win rate is cited. Sources: [andrew.ooo](https://andrew.ooo/posts/ai-trading-bots-polymarket-profits/); [MEXC/Finbold](https://www.mexc.com/news/433308); [BeInCrypto](https://beincrypto.com/arbitrage-bots-polymarket-humans/)
- [Primary/Secondary] In January 2026 Polymarket added **taker-only fees** to 15-minute crypto markets (BTC, ETH, SOL, XRP). The fee curve peaks near 50¢: for a 100-share taker trade at $0.50 the fee is about $1.56, just over 3%. Proceeds fund daily maker rebates. Reports say the aim was to neutralise latency arbitrage. Sources: [The Block](https://www.theblock.co/post/384461/polymarket-adds-taker-fees-to-15-minute-crypto-markets-to-fund-liquidity-rebates); [Cointelegraph](https://cointelegraph.com/news/polymarket-quietly-adds-taker-fees-15-minute-crypto-markets)
- [Secondary] Short-duration crypto markets (5-minute and 15-minute) reportedly made up more than half of all crypto trading on Polymarket and Kalshi. Source: [MEXC news](https://www.mexc.com/news/923042)
- [Anecdote] An open-source Kalshi 15-minute bot buys YES and NO together when the combined ask is under $1. Its README includes a user report that it "lost me $100" on default settings. Source: [GitHub: seanrobenalt/kalshi-bot](https://github.com/seanrobenalt/kalshi-bot)

### Inferences
- The documented winners in both venues are mostly makers or automated liquidity providers, and their edge is spread capture plus favourite-longshot pricing. A taker buying favourites starts from the worse side of the Kalshi maker/taker gap. Even so, the Kalshi data shows takers buying high-priced contracts were roughly break-even to slightly positive after fees, unlike takers buying longshots.
- The SIG Knicks loss shows that the "safe" side of a 95¢ in-game price can lose millions in one event, even for the most sophisticated market maker. Professional market makers survive such days because each game is a small share of capital spread across thousands of markets.
- Latency-driven 15-minute edges were capped by fees within weeks of becoming public, a sign that such edges decay quickly. Position size should probably be planned against a shrinking edge, not a stable one.

### Gaps
- No first-hand interview was found in which a Kalshi or Polymarket professional states a numerical sizing rule (fraction of bankroll, Kelly multiple). Domer's podcast discusses Kelly, but the transcript could not be accessed.
- No position sizes, inventory limits or risk limits were found for SIG or other Kalshi market makers. The programme's adjusted position limits are not published.
- No verified per-trade size data was found for the 15-minute crypto bots. Press figures are total PnL from on-chain trackers and are unaudited.

---

## 5. Favourite-buying and "bond" strategies (buying 90-99¢ outcomes): how are they sized?

### Takeaway
Nobody publishes a quantitative sizing rule for Polymarket "bonding". Guides say only "size assuming a loss will eventually occur" and spread across uncorrelated markets. They stress that at 95¢ one loss erases about 19 wins. The best price-bucket evidence (Kalshi, 2021-2025) shows high-priced contracts have a small positive expected return: about +3% pre-fee in the 95¢ example, and significant but small post-fee for prices above 70¢. Polymarket shows a similar favourite-longshot tilt, with favourites slightly underpriced.

### Cited findings
- [Secondary, guide] "Bonding" means buying outcomes priced around $0.93-$0.99 and holding to resolution. Returns by entry price:
  - $0.99 → about 1.0%
  - $0.97 → about 3.1%
  - $0.95 → about 5.3%
  - $0.93 → about 7.5%
  
  The guide gives no percentage-of-bankroll rule. It says "Size your positions assuming a loss will eventually occur", to work backward from what you can afford to lose on any single bond, and to diversify across "several uncorrelated markets". At $0.95 one loss wipes out about 19 wins; with 100 bonds at $0.95 expect about five failures. Other risks it lists: resolution wording narrower than the headline, disputed resolutions, capital locked up by delayed resolution, liquidity. Source: [startpolymarket.com, "Bonding", Tom Hill, updated Mar 25, 2026](https://startpolymarket.com/strategies/bonding/)
- [Primary] Kalshi: contracts above 70¢ earn statistically significant but small positive post-fee returns. A 95¢ contract that wins 98% of the time returns 3.1% pre-fee. Makers buying contracts at 50¢ and above average +2.6%. Source: [Bürgi, Deng & Whelan](https://www.karlwhelan.com/Papers/Kalshi.pdf)
- [Secondary] Polymarket's accuracy dashboard reports 98.5% accuracy 4 hours before resolution, and a community summary says the dashboard shows traders "overbet longshots and underbet favorites". Sources: [Polymarket accuracy mirror](https://polymarket.206.189.21.72.sslip.io/accuracy); [pm.wiki](https://pm.wiki/zh/projects/alexmccullough)
- [Secondary, blog with code] Across 161,638 Polymarket and Kalshi contracts, 72% resolved NO (92.6% for range contracts). The author found a "bet NO on everything" approach doesn't work, and calls the favourite-longshot bias "slight", too small to beat costs for most traders. Source: [Delta Confidence, "Nothing ever happens", Feb 12, 2026](https://deltaconfidence.substack.com/p/nothing-ever-happens)

### Inferences
- **Kelly on a high-priced binary is huge and fragile.** For a contract costing c that pays $1 with true probability p, full Kelly is f* = (p − c)/(1 − c). At c = 0.92 and p = 0.94, f* = 0.02/0.08 = **25% of bankroll**. If the true p is 0.92, f* = 0. A 2-percentage-point error in p moves Kelly from 0 to 25%, and the loss when wrong is 100% of the stake. This is Benter's factor-of-two warning at its most extreme. Calibration error of a point or two is normal, so practitioners' 1/4 to 1/8 Kelly and per-event caps (Walters' 3%; the 3-5% per event suggested after the beachboy4 loss below) matter more here than at even odds. (The project's own calculation; standard Kelly formula.)
- Many favourite-buys open at the same time on correlated underlyings (for example several crypto 15-minute markets sharing one spot move, or several "No" contracts on one geopolitical theme) behave like one big bet. Per-bet caps alone do not cap total exposure, so a per-window or per-theme cap is the relevant limit.
- Because the edge per bet is a few percent of the stake and losses are total, results depend heavily on loss-rate estimates from small samples. One extra loss per 100 bets at 92¢ moves the return by about 1.1 points, which is the size of the whole edge.

### Gaps
- No published, wallet-level study of Polymarket bond traders was found (their sizes, bankroll fractions, realised returns or drawdowns).
- No peer-reviewed Polymarket return-by-price-bucket table comparable to the Kalshi paper was found.
- The claim, from a search summary, that a University of Toronto-linked study found losers "disproportionately trade at extreme prices" ("below 10¢ or above 90¢") could not be confirmed from any page opened during this research. Treat it as unverified.

---

## 6. Documented failures: oversizing high-probability ("steamroller") bets

### Takeaway
The losses clearly documented in prediction markets are mostly concentration failures: one position or theme that was a large share of the account. The near-certain side can lose through a sudden real-world event, such as an Iran strike that ended a two-month run of "No" profits, or a last-second field goal against a position that had traded near 99¢. It can also lose through resolution and oracle risk: the Zelensky-suit market reversed from Yes to No after disputes, and a rules clarification sent a MicroStrategy market to zero. Most figures come from Lookonchain or crypto press, not audited data.

### Cited findings
- [Anecdote, Lookonchain via crypto press, Feb 2026] Account "anoin123" reportedly built more than **$2M** of gains over about two months by repeatedly betting against a US-Israel strike on Iran, then lost about **$6.5M in a single day** when the strike happened, for a net loss of about $4.5M. The article itself says the figure "still needs verification". Source: [CryptoAdventure, Feb 28, 2026](https://cryptoadventure.com/polymarket-whales-6-5m-wipeout-sparks-biggest-loss-talk/)
- [Anecdote, Lookonchain via BeInCrypto, Jan 5, 2026] Trader "beachboy4" lost more than **$2M in 35 days**:
  - Average bet was about **$400,000**; 53 bets with a 51% win rate.
  - One position (Liverpool to win, bought at $0.66 for $1.58M) caused about **79%** of the loss.
  - Lookonchain called buying at high prices the "worst payoff structure" (gains capped, full downside).
  - The article suggests capping exposure to any one event at **3-5% of capital**.
  
  Sources: [BeInCrypto via Yahoo](https://finance.yahoo.com/news/trader-lost-2-million-polymarket-133015895.html); [BeInCrypto original](https://beincrypto.com/polymarket-trader-loss-risk-management/)
- [Anecdote] A whale holding about $146.7k of Eagles "Yes" (623,449 shares bought at about 23¢) saw the shares trade near **99¢**, never sold, and lost everything when Jacksonville won 19-17 on a 57-yard field goal as time expired (London game). Article date not confirmed. Source: [Bitcoin.com News](https://news.bitcoin.com/igaming/polymarket-whale-loses-147k-eagles-bet-after-a-last-second-57-yard-kick/)
- [Secondary] Kalshi, June 10, 2026: market makers lost about $22.4M pre-fee in one NBA Finals game when takers' roughly 5%-odds in-game Knicks bets won. This is the professional version of being short the steamroller. Source: [InGame](https://ingame.com/susquehanna-biggest-sports-kalshi-volume-knicks)
- [Secondary] Resolution risk, the Zelensky "suit" market (about $237-242M volume): it first resolved "Yes", then after nine days of disputes flipped to "No" (July 2025). Critics noted UMA had ruled a similar outfit "not a suit" in May. Manipulation claims remain unproven. Sources: [Decrypt](https://decrypt.co/329210/polymarket-rules-no-237m-controversial-bet-over-zelenskyys?amp=1); [The Defiant](https://thedefiant.io/news/nfts-and-web3/polymarket-controversy-heats-up-after-the-zelenskyy-suit-market-resolves)
- [Secondary] How UMA resolution works: anyone can propose an outcome with a $750 USDC bond, there is a 2-hour dispute window, and token holders vote on disputes. A WSJ analysis found at least 60% of active UMA voters could be linked to Polymarket accounts, and in more than 300 disputes voters held positions in the disputed market. Polymarket says only about 0.2% of bets reach arbitration. A price near 99¢ during a dispute is not settlement. Sources: [Orrery research](https://orrery.me/research/uma-disputes-explained); [NexusFi](https://nexusfi.com/a/prediction-markets/polymarket-uma-oracle-dispute); [KuCoin news](https://www.kucoin.com/news/flash/polymarket-disputes-ruled-by-mysterious-uma-token-holders)
- [Anecdote] One trader says he lost **$500k** on a $175M MicroStrategy/BTC market. A Polymarket clarification tied resolution to when a sale was *confirmed*, not when it happened, and the price collapsed to near zero. Source: [DeFi Rate](https://defirate.com/news/polymarket-trader-loses-500k-loss-after-rules-change-microstrategy-btc-market/)
- [Secondary] Losses are concentrated: a Bloomberg analysis found more than 100,000 Polymarket wallets lost at least $1,000, nearly double the number that gained that much. Source: [Finance Magnates](https://www.financemagnates.com/fintech/100000-polymarket-wallets-lost-at-least-1000-bloomberg-analysis-shows/)

### Inferences
- In every case the trigger was one event or theme (an Iran strike, one football match, one resolution ruling) that made up a large share of the account. Fractional Kelly with a per-event or per-theme cap is the documented antidote, from Benter's 1/2-1/3 Kelly to Walters' 3% cap and the 3-5% per-event cap suggested after beachboy4.
- Two separate tail risks sit on high-probability contracts: outcome risk (the event happens) and resolution or oracle risk (the outcome is ruled differently). On Kalshi, which settles from defined data sources rather than token-holder votes, the second is smaller but not zero. That differs from Polymarket's UMA process (inference from the sources above).
- The "pennies before a steamroller" pattern shows up as a long run of small gains (anoin123's two months, a bond guide's "19 wins per loss") ended by one loss larger than the run. Sizing should therefore be judged on the worst plausible single day, not on the average.

### Gaps
- No case found was documented with an audited bankroll, so "fraction of bankroll lost" cannot be computed for any named Polymarket failure.
- No documented Kalshi retail case of a large loss on 95-99¢ favourites was found. The Kalshi example above is on the market-maker side.
- Several dates (the Eagles game) and figures (anoin123's $6.5M) are unconfirmed in the sources themselves.
