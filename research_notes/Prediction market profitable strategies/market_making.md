# Market making and liquidity rewards on prediction markets (Kalshi, Polymarket, exchange-style venues)

Research notes, written 25 Oct 2026. Every figure has a date. Older findings are marked "older".

Plain words used throughout:
- **Maker**: a trader whose resting order sits on the book and gets filled later. They post the price.
- **Taker**: a trader who hits a resting order right away. They accept the posted price.
- **Spread**: the gap between the best buy and sell price. It is what it costs a taker to get in, and what a maker hopes to earn.
- **Adverse selection**: getting picked off by someone who knows more than you, such as a trader who has already seen the news.
- **Inventory risk**: the risk of being stuck holding a position that moves against you.
- **Favourite-longshot bias**: cheap unlikely bets are overpriced, and heavy favourites are underpriced.
- **Liquidity rewards / incentives**: cash an exchange pays makers for keeping orders on the book.
- **Rebate**: part of a fee handed back to a trader.

Source-quality flags: several pages below sell bots, servers (VPS), courses, paid newsletters, or use affiliate links. They are marked **[sells something]**. A few pages could not be opened in full (blocked, or PDF text not readable). Claims taken only from a search-result summary are marked **[snippet only]**.

---

## 1. Makers vs takers on Kalshi: what return did each earn, and how does it vary by price?

### Takeaway
On Kalshi, makers do clearly better than takers, and both do worst on cheap longshots. In the main academic paper (Bürgi, Deng and Whelan, data 2021 to April 2025), the average contract lost about 20% before fees and 22% after. Takers lost about 32% per contract on average and makers about 10%. Contracts priced above 50 cents earned a small, statistically real, positive return. A second, money-weighted study reports takers lose about 1.12% per trade and makers gain about 1.12%. That pattern only appeared once professional firms arrived.

### Cited findings
**Bürgi, Deng and Whelan, "Makers and Takers: The Economics of the Kalshi Prediction Market" (older first version 2025; updated Feb 2026)**
- Versions and dates: UCD Centre for Economic Research WP2025_19 (2025); CESifo Working Paper 12122 (2025); CEPR Discussion Paper 20631; GWU Center for Economic Research working paper 2026-001 (Feb 2026, apparently retitled "Makers or Takers"); MPRA paper 126350. Sources: [UCD WP2025_19](https://www.ucd.ie/economics/t4media/WP2025_19.pdf); [ifo/CESifo 2025](https://www.ifo.de/en/cesifo/publications/2025/working-paper/makers-and-takers-economics-kalshi-prediction-market); [ifo/CESifo 2026](https://www.ifo.de/en/cesifo/publications/2026/working-paper/makers-and-takers-economics-kalshi-prediction-market); [CEPR DP20631](https://cepr.org/publications/dp20631); [GWU 2026-001](https://www2.gwu.edu/~forcpgm/2026-001.pdf); [MPRA](https://mpra.ub.uni-muenchen.de/126350/1/MPRA_paper_126350.pdf)
- Data: Kalshi trades from 2021 to April 2025. One write-up of the Feb 2026 version gives 46,282 contracts across 12,403 events. Source: [Navnoor Bawa Research, 2026](https://www.navnoorbawaresearch.com/p/kalshi-publishes-one-liquidity-subsidy) **[sells something: paid Patreon]**
- Conflict on sample size: the CEPR abstract says "over 300,000 contracts". Which count is right is not settled; the gap may be versions or counting method (contracts vs trades). Sources: [CEPR DP20631](https://cepr.org/publications/dp20631); contrast [Navnoor Bawa Research](https://www.navnoorbawaresearch.com/p/kalshi-publishes-one-liquidity-subsidy)
- Overall return: about minus 20% per contract before fees. About minus 22% after Kalshi's fees. Sources: [Karl Whelan paper PDF](https://www.karlwhelan.com/Papers/Kalshi.pdf); [UCD WP2025_19](https://www.ucd.ie/economics/t4media/WP2025_19.pdf) **[snippet only: figures from search summaries of these PDFs; PDF text was not readable]**
- By price: buyers of contracts under 10 cents lose more than 60% of their money on average. Contracts above 50 cents earn a small positive return that is statistically significant (unlikely to be luck). Sources: [Karl Whelan paper PDF](https://www.karlwhelan.com/Papers/Kalshi.pdf); [Navnoor Bawa Research](https://www.navnoorbawaresearch.com/p/kalshi-publishes-one-liquidity-subsidy) **[snippet only for the PDF]**
- Makers vs takers: takers lose almost 32% per contract on average; makers lose about 10%. Both show the favourite-longshot pattern, but it is much stronger for takers, who lose far more on longshots. Source: [VoxEU column by the authors](https://cepr.org/voxeu/columns/economics-kalshi-prediction-market) **[snippet only: the VoxEU page returned "403 Forbidden"; the 32%/10% figures came through two separate search summaries]**
- Their explanation: makers are fairly well-informed traders who seek positive returns after fees but are slightly over-optimistic. Takers suffer a "winner's curse" (the one who accepts the offer tends to be the one who over-rates the bet). The model fits once people over-estimate small probabilities a little. Sources: [CEPR DP20631](https://cepr.org/publications/dp20631); [Karl Whelan paper PDF](https://www.karlwhelan.com/Papers/Kalshi.pdf) **[snippet only]**
- Trend: the authors report some evidence that the price bias is shrinking over time. Source: [Karl Whelan paper PDF](https://www.karlwhelan.com/Papers/Kalshi.pdf) **[snippet only]**
- Conclusion: Kalshi prices are informative but should not be read as unbiased probabilities. Source: [CEPR DP20631](https://cepr.org/publications/dp20631)

**Jon Becker, "The Microstructure of Wealth Transfer in Prediction Markets" (2025-2026)**
- Reported result: takers lost an average of 1.12% per trade; makers gained an average of 1.12%. The pattern was reversed in Kalshi's early days, before institutional liquidity providers (professional firms paid to quote) joined. Source: [The American Prospect, 26 Aug 2026](https://prospect.org/2026/08/26/house-always-wins-kalshi-prediction-markets/)
- The study's data tools are on GitHub ("prediction-market-analysis"). One site using that method covers 3,587 Kalshi markets from June 2021 to November 2025 and reports a median spread of 2.4 cents and "spreads compressed 43% while volume rose 166%". It is unclear whether those numbers are Becker's or the site's own. Source: [StockAlarm Predict research page](https://pro.stockalarm.io/predict/research)
- No price-level breakdown from the Becker study was found.

**Bartlett and O'Hara, "Adverse Selection in Prediction Markets: Evidence from Kalshi" (SSRN, 21 Apr 2026)**
- Sample: 41.6 million Kalshi trades. Source: [Stanford Law summary, 21 Apr 2026](https://law.stanford.edu/2026/04/21/adverse-selection-in-prediction-markets-evidence-from-kalshi/)
- "Single-name" markets (one event, like one game) show more informed price impact than "broad-based" markets (like an index level). In single-name markets, effective spreads (what takers really pay) are only modestly wider, but market makers earn twice as much per contract. Sources: [Stanford Law summary](https://law.stanford.edu/2026/04/21/adverse-selection-in-prediction-markets-evidence-from-kalshi/); [SSRN 6615739](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6615739) (SSRN page was blocked; abstract via the Stanford summary)
- One-sided order flow (a run of trades all on one side, a sign of informed traders) predicts maker losses in single-name markets, but not in broad-based ones. Source: [Stanford Law summary](https://law.stanford.edu/2026/04/21/adverse-selection-in-prediction-markets-evidence-from-kalshi/)
- Traders systematically over-bet YES in markets that mostly settle NO. Source: [Stanford Law summary](https://law.stanford.edu/2026/04/21/adverse-selection-in-prediction-markets-evidence-from-kalshi/)

**Roosevelt Institute (published 7 Jul 2026)**
- Kalshi takers lost an estimated $583.5 million net, from launch (July 2021) to 15 May 2026. Source: [Roosevelt Institute](https://rooseveltinstitute.org/?p=22369)
- By category: sports $371.6M (over two-thirds); "exotics" including most parlays over $100M; mention markets over $16M. Source: [Roosevelt Institute](https://rooseveltinstitute.org/?p=22369)
- Data: over 400 million trades, over $32 billion of volume, mean bet $75.20. Data came from a Dune snapshot taken before public access was removed. 63.2% of taker revenue went to 6.3% of matched orders (orders of $200 or more). Source: [Roosevelt Institute](https://rooseveltinstitute.org/?p=22369)
- Kalshi's reply: the study confuses "maker/taker" with "professional/casual" and is a basic error. Source: [Casino.org](https://www.casino.org/news/kalshi-rebuffs-think-tank-claim-regular-traders-lost-584-million-on-platform/)

**Other dated numbers on who loses**
- Bottom-quartile Kalshi users lost an average of 28 cents per dollar bet, vs 11 cents at other gambling sites (Bloomberg, 4 Feb 2026, analyst Jordan Bender). Source: [The American Prospect](https://prospect.org/2026/08/26/house-always-wins-kalshi-prediction-markets/)
- Retail lost $117 million to market makers on Kalshi "combos" (parlays) from January to April 2026 (Sportico). Dune then pulled the data behind a $40,000 paywall. Source: [The American Prospect](https://prospect.org/2026/08/26/house-always-wins-kalshi-prediction-markets/)
- Parlay takers, InGame's own analysis (updated 20 Oct 2026): Kalshi takers lost $340M after fees since early Sept 2026 (about 14.4% of stakes) and over $870M since parlays launched in Sept 2025. Kalshi took $336M in parlay fees since Sept 2025. Polymarket US takers lost $69.6M after fees (15.4%). DraftKings' exchange (DKeX, first trades 26 Aug) takers lost $60.8M after fees (25.8%). Source: [InGame, 20 Oct 2026](https://www.ingame.com/parlay-takers-lose-dkex-polymarket-us/)
- WSJ: more than 70% of Polymarket users are losing money; a Kalshi spokeswoman said losing users outnumber winners 2.9 to 1. Source: [Yahoo Finance / WSJ](https://finance.yahoo.com/markets/options/articles/prediction-markets-hit-milestones-most-042140220.html) **[snippet only]**

### Inferences
- The two headline numbers measure different things. Bürgi et al. average the percent return per contract, so cheap longshots (where percent losses are huge) dominate. That is why even makers show minus 10%. Becker's plus/minus 1.12% looks like a per-trade, money-style measure. Both say the same thing: money flows from takers to makers.
- "Makers lose 10% on average" does not mean market making loses money in dollars. A maker who buys a 5-cent longshot and loses 60% loses only a few cents. A maker who sells it gains those cents.
- The above-50-cent result matches this project's own finding that favourites are slightly underpriced. Being the maker on the favourite side would earn both the spread and the favourite premium, if fills are not adversely selected.
- Bartlett and O'Hara suggest single-game markets (like sports) pay makers more because they are riskier. Broad-based markets (index, crypto price ranges) have less informed flow but thinner margins.

### Gaps
- The full Bürgi et al. tables could not be read, so the exact maker and taker return for each price band (e.g. 80-90 cents, 90-99 cents) is missing. The PDFs did not yield readable text, and the VoxEU column was blocked.
- It is not confirmed whether the Feb 2026 GWU version changed the 32%/10% numbers.
- No price-band breakdown found for the Becker study. Its 1.12% figure is second-hand, via The American Prospect.
- No exact numbers from Bartlett and O'Hara on how much makers earn per contract (only "twice as much" in single-name markets).

---

## 2. Polymarket liquidity rewards, Polymarket holding rewards, and Kalshi interest

### Takeaway
Polymarket pays makers daily from per-market reward pools. Scoring is by a squared closeness-to-midpoint formula that favours two-sided quotes. Total reward budgets were large in the 2024 election season, then cut. They were about $300k a month by Aug 2025. Since Jan-Mar 2026 Polymarket also charges taker fees and hands 15-25% back to makers as rebates. Holding rewards pay 4.00% a year on a short list of long-dated markets. Kalshi pays interest on cash and positions; its help pages list 3.25%, 3.50% and 4.05% at different times.

### Cited findings
**How Polymarket liquidity rewards pay (official docs, current Oct 2026)**
- Any maker posting resting limit orders is automatically eligible. Rewards go to maker addresses daily at midnight UTC. Minimum payout is $1; smaller amounts are not paid. Source: [Polymarket docs: Liquidity Rewards](https://docs.polymarket.com/programs/liquidity-rewards)
- A day that earns under $1 is not paid and does not roll over to the next day. Source: [Polymarket Help Center](https://help.polymarket.com/en/articles/13364466-liquidity-rewards) **[snippet only]**
- Each market sets its own max qualifying spread, min order size, and reward pool. Source: [Polymarket docs](https://docs.polymarket.com/programs/liquidity-rewards)
- Order score = ((v − s) / v)² × b. Here v is the max spread allowed (in cents from the midpoint), s is the order's distance from the midpoint, and b is a multiplier. So an order at the midpoint scores fully, and the score falls off as a square. Source: [Polymarket docs](https://docs.polymarket.com/programs/liquidity-rewards)
- Two-sided quoting: the score takes the smaller of the bid side and ask side. If the midpoint is between 10 and 90 cents, one-sided quotes still score, but divided by 3. Below 10 cents or above 90 cents, only two-sided quotes score. Source: [Polymarket docs](https://docs.polymarket.com/programs/liquidity-rewards)
- The book is sampled once a minute at a random second (up to 1,440 samples per UTC day). Your share of the day's total score times the market's pool is your reward. Source: [Polymarket docs](https://docs.polymarket.com/programs/liquidity-rewards)
- Rewards can be "native" (Polymarket's) or "sponsored" (paid by a third party). Source: [Polymarket docs](https://docs.polymarket.com/programs/liquidity-rewards)

**How much Polymarket pays out**
- Crypto price-average (TWAP) markets got $1M of extra rewards for one August (year not shown; likely 2026). 5-minute markets $550k (BTC $300k); 15-minute markets $350k (BTC $225k); 4-hour markets $100k. These were caps, not actual payouts. The program has ended. Source: [Polymarket docs](https://docs.polymarket.com/programs/liquidity-rewards)
- Polymarket's monthly reward spend was about $300k as of 25 Aug 2025 (older), corrected down from an earlier $600k estimate. Source: [Adhi Rajaprabhakaran Substack, 25 Aug 2025](https://ufoholdings.substack.com/p/kalshis-new-liquidity-incentives) (author is a former Kalshi Trading trader; sells nothing, promotes his Substack)
- A third-party leaderboard claims about $33.5M paid to about 182,068 wallets since November 2023. Not verified against Polymarket data. Source: [PolyScalping LP leaderboard](https://polyscalping.org/leaderboard/lp) **[snippet only; unverified]**
- One guide claims a "$5M+ monthly" pool; this did not match Polymarket's own docs. Source: [startpolymarket.com reward-farming guide](https://startpolymarket.com/strategies/reward-farming/) **[sells something / affiliate-style]**

**How rewards changed, 2024-2026**
- After the Nov 2024 US election, Polymarket's total liquidity rewards dropped sharply, making reward farming less profitable (trader interview, 28 May 2025, older). Source: [The Oracle (Polymarket newsletter), 28 May 2025](https://news.polymarket.com/p/automated-market-making-on-polymarket)
- 6 Jan 2026: Polymarket added taker-only fees to 15-minute up/down crypto markets (BTC, ETH, SOL, XRP). Fees are highest at 50 cents and fall toward 0 and 100. The fees fund a Maker Rebates Program paid daily. The Block read the docs as "fees may reach up to 3%". Source: [The Block, 6 Jan 2026](https://www.theblock.co/post/384461/polymarket-adds-taker-fees-to-15-minute-crypto-markets-to-fund-liquidity-rebates)
- Feb 2026 docs: rebate share 20% (15-min crypto), 20% (5-min crypto), 25% (some sports). Source: [Polymarket taker-rebates/fees docs](https://docs.polymarket.com/trading/taker-rebates) **[snippet only]**
- "Fee Structure V2", effective 30 Mar 2026: taker fees spread to most categories. Crypto 0.07, sports 0.03, finance/politics/mentions/tech 0.04, economics/culture/weather/other 0.05. Geopolitics stays fee-free. Source: [Sacra: Polymarket](https://www.sacra.com/c/polymarket/) **[snippet only]**
- Current maker rebate docs (Oct 2026): taker fee = shares × fee rate × p × (1 − p), where p is the price. Fee rates: crypto 0.07, sports 0.05, finance/politics/mentions/tech 0.04, economics/culture/weather/other 0.05, geopolitics 0. Maker rebate share: crypto 20%, sports 15%, everything else 25%. Rebates are split per market by each maker's share of filled fee-weighted volume. Paid daily in pUSD once accrued above $1. Polymarket can change the share at its "sole discretion". Source: [Polymarket docs: Maker Rebates Program](https://docs.polymarket.com/polymarket-learn/trading/maker-rebates-program)
- Conflict: the sports taker fee is 0.03 in Sacra's V2 summary and 0.05 in the current docs table. Probably a later change; not confirmed. Sources: [Sacra](https://www.sacra.com/c/polymarket/); [Polymarket docs](https://docs.polymarket.com/polymarket-learn/trading/maker-rebates-program)
- A taker-rebate tier program (based on 30-day weighted volume, paid daily) went live 28 or 29 May 2026; the docs' versions disagree on the day. Source: [Polymarket docs: taker rebates](https://docs.polymarket.com/trading/taker-rebates) **[snippet only]**

**Polymarket holding rewards (interest-like yield)**
- Polymarket pays a variable 4.00% a year on total position value in certain markets. Position value uses the latest mid-price. It is sampled at a random time each hour and paid daily. Source: [Polymarket docs: Holding Rewards](https://docs.polymarket.com/polymarket-learn/trading/holding-rewards)
- Eligible markets are a small hand-picked set of long-dated political markets, such as the 2028 presidential race, 2026 House and Senate control, and leader-exit markets. Funded by the Polymarket Treasury. Polymarket may cap total payouts at any time. Sources: [Polymarket docs: Holding Rewards](https://docs.polymarket.com/polymarket-learn/trading/holding-rewards); [Quantcha](https://quantcha.com/news/?p=618)

**Kalshi interest on cash and positions**
- Kalshi pays interest (APY, the yearly rate) on the net value of the whole portfolio, cash plus positions. It accrues on the value at 12am ET each day and is paid in the first week of the next month. Only eligible US accounts with $250 or more. The rate can change at any time. Sources: [Kalshi Help: APY on Kalshi](https://help.kalshi.com/en/articles/13823847-apy-on-kalshi); [Kalshi FAQ: Interest](https://help.kalshi.com/faq/interest-apy-on-kalshi)
- Rate: different help-page versions show 3.25%, 3.50% and 4.05%. The 4.05% page says accrual started "Thursday, October 10th" with no year (10 Oct was a Thursday in 2024, so likely older). A 2026 commentary says Kalshi pays 3.25% on all positions and cash. Sources: [Kalshi FAQ](https://help.kalshi.com/faq/interest-apy-on-kalshi); [Quantcha](https://quantcha.com/news/?p=618)

### Inferences
- The squared scoring means rewards go mostly to the tightest, biggest, always-on quotes. A part-time or wide quote earns almost nothing.
- The two-sided rule below 10 cents and above 90 cents matters for favourites. To earn rewards on a 92-cent favourite you must also quote the other side.
- Since Jan-Mar 2026, Polymarket has moved from paying makers from its treasury to paying them from taker fees. That makes rewards depend on volume, not marketing budgets.
- Kalshi's interest on positions lowers the cost of holding long-dated inventory, which helps makers in slow markets. It does little for 15-minute markets.

### Gaps
- No official figure for total Polymarket liquidity rewards paid per month or per year in 2025-2026.
- No official list of the top reward earners. The rewards endpoint is per address, so a full on-chain tally would be needed.
- No start date found for holding rewards, and no current (Oct 2026) Kalshi interest rate confirmed from a dated official page.

---

## 3. Kalshi's market maker program and designated market makers (SIG and others)

### Takeaway
Kalshi runs several paid programs for liquidity. Its own affiliate, Kalshi Trading, also makes markets. Susquehanna (SIG) became the first outside market maker in April 2024. Jump, DRW and others followed in 2026. The key terms (exact fee cuts, rebates, revenue share) are filed with the CFTC as confidential. Only caps are public: up to $1,000 per market per day in the open tier, and $50,000 per series per week in the market-maker tier. No venue publishes what makers actually earn.

### Cited findings
**Who the market makers are**
- Kalshi Trading is Kalshi's own affiliated market maker. Critics note it profits when customers on the other side lose. Source: [The American Prospect, 26 Aug 2026](https://prospect.org/2026/08/26/house-always-wins-kalshi-prediction-markets/)
- Susquehanna International Group (SIG) became Kalshi's first outside market maker in April 2024. Susquehanna also backs a new prediction exchange with Robinhood. Sources: [The American Prospect](https://prospect.org/2026/08/26/house-always-wins-kalshi-prediction-markets/); [Robinhood newsroom, 25 Nov 2025](https://www.robinhood.com/us/en/newsroom/robinhood-prediction-markets-joint-venture/) **[snippet only for Robinhood]**
- Aug 2026: SIG to provide pricing and liquidity for block trades that Cantor Fitzgerald brings to Kalshi. Source: [CNBC, 19 Aug 2026](https://www.cnbc.com/2026/08/19/hedge-funds-are-about-to-jump-in-big-to-prediction-markets.html) **[snippet only]**
- Jump Trading took equity stakes in Kalshi and Polymarket around Feb 2026 in exchange for market making. It doubled its prediction-market team to about 20 people in 2026. By May 2026 it had provided Kalshi's first institutional block-trade liquidity. Source: [Crypto Briefing, 16 Jul 2026](https://cryptobriefing.com/jump-trading-prediction-markets-wall-street/)
- DRW and SIG both have dedicated prediction-market teams. Source: [Crypto Briefing](https://cryptobriefing.com/jump-trading-prediction-markets-wall-street/)
- Kalshi and other venues mostly do not disclose who their market makers are. Source: [The American Prospect](https://prospect.org/2026/08/26/house-always-wins-kalshi-prediction-markets/)
- Sportsbooks as makers: Flutter (FanDuel's parent) reported $6M of prediction-market market-making revenue in Q2 2026 and expects $50M for 2026. DraftKings says it makes markets on singles and combos "at a profit" on three exchanges (Q2 2026 letter). Source: [The American Prospect](https://prospect.org/2026/08/26/house-always-wins-kalshi-prediction-markets/)

**Kalshi's public terms**
- Market Maker Program (help page dated 28 Apr 2026): designated makers give steady two-sided quotes and must meet quoting and volume rules (numbers not public). Approval depends on financial resources, trading experience and reputation. Benefits: "reduced fees" and "adjusted position limits" (bigger allowed positions). About 88 products are covered, such as KXBTC, KXETH, KXINX, KXNBA, KXNFLGAME, KXCPI, KXFED. Each must be quoted 98% of every hour. Makers carry their own trading risk. Source: [Kalshi Help: How to become a market maker](https://help.kalshi.com/en/articles/13823819-how-to-become-a-market-maker-on-kalshi)
- Kalshi's member agreement allows market makers "discounts on fees, rebates on fees, revenue share from fees, and other monetary benefits". It also describes risk tools that "may give market makers a trading advantage" over others. Source: [The American Prospect](https://prospect.org/2026/08/26/house-always-wins-kalshi-prediction-markets/)
- Liquidity Incentive Program (open to members): ran 15 Sep 2025 to 1 Sep 2026. Makers earn a share of each market's reward pool by liquidity provided. Target size 100 to 20,000 contracts. Each market shows its schedule on its page. Source: [Kalshi Help: Liquidity Incentive Program](https://help.kalshi.com/en/articles/13823851-liquidity-incentive-program)
- How it scores (Aug 2025 filing, older): score = size × discount factor ^ (ticks from best price). Snapshots are taken at a random moment every second, and orders must be live the whole second. So flickering quotes earn little. Kalshi Trading and SIG were described as not eligible for these rewards. Source: [Adhi Rajaprabhakaran Substack, 25 Aug 2025](https://ufoholdings.substack.com/p/kalshis-new-liquidity-incentives)
- CFTC filings show per-market reward maximums are in a confidential appendix. Source: [CFTC filing, Oct 2026](https://www.cftc.gov/filings/orgrules/rules10142633803.pdf) **[snippet only: PDF not read]**
- Liquidity Provider Program (filed 4 May 2026, runs to Dec 2027): only for members with a signed Market Maker Agreement. Pay set by reverse auction (makers bid how little they need). Open-tier cap $1,000 per market per day; market-maker-tier cap $50,000 per series per week. Source: [Navnoor Bawa Research, citing CFTC filings](https://www.navnoorbawaresearch.com/p/kalshi-publishes-one-liquidity-subsidy) **[sells something: paid Patreon]**
- Market Maker Program pays "predetermined incentives". The amounts sit in "Confidential Appendix C". Maker order protections require a minimum share of maker volume, set between 1% and 7% on a website, not in the filing. Source: [Navnoor Bawa Research](https://www.navnoorbawaresearch.com/p/kalshi-publishes-one-liquidity-subsidy)
- Volume Incentive Program: rewards on trades between 3 and 97 cents, capped at $0.005 per contract per participant. It was refiled 4 Aug 2026 to run to Sept 2027. A 28 Sep 2026 notice then ended it, effective no earlier than 13 Oct 2026, amid scrutiny. Sources: [Navnoor Bawa Research](https://www.navnoorbawaresearch.com/p/kalshi-publishes-one-liquidity-subsidy); [Crypto Briefing](https://cryptobriefing.com/kalshi-ends-volume-incentive-program/); [Gambling.com](https://www.gambling.com/us/news/kalshi-end-volume-incentive-program-october-13) **[snippet only for the end date]**
- That $0.005 cap is bigger than Kalshi's taker fee below about 7.7 cents and above about 92.3 cents (author's own maths). So at the extremes the reward could exceed the fee paid. Source: [Navnoor Bawa Research](https://www.navnoorbawaresearch.com/p/kalshi-publishes-one-liquidity-subsidy)
- Temporary Perpetual Fee Rebate Program (CFTC filing 24 Jun 2026, effective on or after 9 Jul 2026): pays back fees in eligible perpetual markets. It refers to a "Spring 2025 Market Maker Program" and limits stacking both. Source: [CFTC filing, 24 Jun 2026](https://cftc.gov/filings/orgrules/rules0625267305.pdf) **[snippet only]**
- Regulator: CFTC staff advisory on incentive programs 12 Aug 2026; amendment deadline 14 Sep 2026 (CFTC Letter 26-23); comments on affiliate rules closed 5 Oct 2026. Source: [Navnoor Bawa Research](https://www.navnoorbawaresearch.com/p/kalshi-publishes-one-liquidity-subsidy)
- Other venues also hide terms: Polymarket US (QCX LLC) filed its incentive appendix as confidential "in perpetuity" on 5 Mar 2026; rates can change on 7 days' notice. ForecastEx filed its programs as confidential exhibits on 2 Mar 2026. Source: [Navnoor Bawa Research](https://www.navnoorbawaresearch.com/p/kalshi-publishes-one-liquidity-subsidy). Polymarket US's own page gives no terms; firms apply at institutional@qcex.com. Source: [Polymarket US docs](https://docs.polymarket.us/incentives/market-maker)
- Secondary sites claim market-maker rebates "up to 1%" capped at $7,000 a week, or about 0.5 cents per contract. These conflict and neither is from Kalshi. Source: [kalshibacktest.com](https://kalshibacktest.com/resources/what-is-kalshi-market-maker) **[sells something; snippet only]**

**Profits**
- No venue publishes what makers actually earned from these programs. Only the caps are public. Source: [Navnoor Bawa Research](https://www.navnoorbawaresearch.com/p/kalshi-publishes-one-liquidity-subsidy)
- A class action in Oregon names Kalshi and Susquehanna. It calls Kalshi a "banked house" built so market makers profit at others' expense. These are a litigant's claims. Source: [The American Prospect](https://prospect.org/2026/08/26/house-always-wins-kalshi-prediction-markets/)

### Inferences
- The best public number for maker profits is the flip side of taker losses: about $583.5M from 2021 to May 2026 (Roosevelt). That is before rebates and incentives, and Kalshi disputes it.
- Flutter's $50M 2026 forecast suggests a large maker can make tens of millions a year, mainly on sports.
- Kalshi's programs layer on top of each other: fee cuts, rebates, per-market pools, and volume rewards. Small makers see only the open-tier pools.

### Gaps
- SIG's actual contract terms, fee cuts and profits are not public. They sit in confidential CFTC appendices.
- No published payout totals for the Liquidity Incentive Program.
- A claim that Kalshi's own market-making desk is "not profitable" (said to be Luana Lopes Lara, via Bloomberg) appeared only in a search summary with no clear source. Treat as unconfirmed.

---

## 4. Risks: adverse selection, inventory, jumps at resolution, and documented blow-ups

### Takeaway
The main risk is getting picked off. Someone who has seen the news first hits your stale order. Kalshi data shows this is real in single-event markets, and Polymarket's 15-minute crypto markets are a known pick-off zone. The clearest documented maker loss found is a two-hour window on 21 Aug (likely 2026). Polymarket US parlay takers made $9.4M after fees on $4.4M of stakes, which InGame blames on maker mispricing. No named firm with a published dollar blow-up was found.

### Cited findings
- Kalshi, 41.6 million trades: one-sided order flow (a run of informed trades) predicts maker losses in single-name markets, but not broad-based ones. Source: [Stanford Law summary of Bartlett and O'Hara, 21 Apr 2026](https://law.stanford.edu/2026/04/21/adverse-selection-in-prediction-markets-evidence-from-kalshi/)
- Crypto markets: a trader can grab a slightly stale Kalshi quote when spot prices move on other exchanges. CNBC also reported that Kalshi does not let market makers requote if prices change. That second point is unclear and may be garbled. Source: [CNBC, 30 Sep 2026](https://www.cnbc.com/2026/09/30/kalshi-polymarket-trading-volume-scrutiny.html) **[snippet only: page blocked]**
- Parlay maker loss: on 21 Aug, Polymarket US parlay takers profited $9.4M after fees on $4.4M of stakes. InGame puts this down to possible maker mispricing between 10am and 12pm ET. Without that day, taker losses would be 17.7% of stakes instead of 15.4%. Source: [InGame, updated 20 Oct 2026](https://www.ingame.com/parlay-takers-lose-dkex-polymarket-us/)
- Takers on Polymarket US parlays were net profitable over their whole history until 12 Sep, then turned negative. Source: [InGame](https://www.ingame.com/parlay-takers-lose-dkex-polymarket-us/)
- A Polymarket reward farmer named his main risk as being "stuck with a bad position when news hits". He stuck to low-volatility markets for that reason (older, May 2025). Source: [The Oracle, 28 May 2025](https://news.polymarket.com/p/automated-market-making-on-polymarket)
- Kalshi's ex-trader notes that makers slow to move quotes on news "get picked off". Source: [Adhi Rajaprabhakaran Substack, 25 Aug 2025](https://ufoholdings.substack.com/p/kalshis-new-liquidity-incentives)
- Kalshi says designated makers "assume trading risk and may face losses like any other participant". Source: [Kalshi Help](https://help.kalshi.com/en/articles/13823819-how-to-become-a-market-maker-on-kalshi)
- The open-source poly-maker bot (README, 2026) warns that market making on Polymarket "is competitive and can lose money". Its inventory exits rely on limit sells, since the merge path "isn't wired yet". Source: [GitHub: warproxxx/poly-maker](https://github.com/warproxxx/poly-maker)
- Practitioner guide claim: a weather maker picked off just before a forecast model update can lose more on one trade than on 10 spread captures. Source: [TurbineFi blog](https://www.turbinefi.com/blog/why-prediction-market-trades-get-picked-off-2026) **[sells something: trading tool vendor; snippet only]**
- Wash trading (fake volume) can inflate reward-driven volume. A May 2026 arXiv study of 600 Polymarket markets and 6.4 million trades found a median wash share of 0.97%, with up to 22.2% in the worst market. Treated as a lower bound. Source: [Navnoor Bawa Research, citing arXiv](https://www.navnoorbawaresearch.com/p/kalshi-publishes-one-liquidity-subsidy)

### Inferences
- Resolution jumps are the extreme case of adverse selection. A binary contract goes to 0 or 100, so a resting order left near the end is a free option for anyone who knows the result.
- For 15-minute crypto markets, the pick-off risk is mostly speed. The underlying price (BTC spot) moves elsewhere first, and stale quotes get hit within milliseconds.
- Polymarket's switch to taker fees on 15-minute crypto in Jan 2026 makes picking off stale quotes cost more. That protects makers, though The Block did not state that as the reason.

### Gaps
- No named market-making firm with a published dollar loss or blow-up was found on Kalshi or Polymarket.
- The 21 Aug parlay event has no named maker and no stated year (Polymarket US parlays launched 11 Aug, likely 2026).
- No hard data on how often resting orders get hit right before resolution.

---

## 5. Can a small retail trader profitably make markets, or do firms dominate? What capital and tech are needed?

### Takeaway
A small trader can still earn rewards, but the documented wins are old, self-reported, and came during a reward boom. The best case is one trader who turned $10,000 into $200 a day, then $700-800 a day at peak, in 2024. He stopped when rewards were cut after the election. Today firms with exchange deals (better fees, bigger limits, extra pools) take the best share. A small maker needs a bot that quotes all day and pulls quotes fast on news.

### Cited findings
- @defiance_cr started with $10,000 and earned about $200 a day, scaling to "$700-800 per day of profit at its peak". He stopped after the 2024 election when rewards fell. Self-reported, unverified, older (published 28 May 2025). Source: [The Oracle (Polymarket's own newsletter), 28 May 2025](https://news.polymarket.com/p/automated-market-making-on-polymarket)
- Guides repeat "$200-800 per day on about $50K" and "$10-200 per $10K per day". These look like marketing copy with no data behind them. Sources: [polymarkets.co.il guide](https://polymarkets.co.il/en/guide/liquidity-rewards/) **[affiliate-style guide]**; [startpolymarket.com](https://startpolymarket.com/strategies/reward-farming/) **[affiliate-style]**; [TradoxVPS](https://tradoxvps.com/polymarket-liquidity-rewards/) **[sells servers]**
- The poly-maker open-source bot calls itself a "research harness, not a guaranteed-profitable product". It ranks markets by reward plus rebate income against volatility and spread risk. It needs a funded wallet, and suggests paper mode first, then small size. No profit figures. Last updated around Apr 2026. Source: [GitHub: warproxxx/poly-maker](https://github.com/warproxxx/poly-maker)
- Kalshi's ex-trader says the ideal reward farmer has subject knowledge, keeps quotes up all market hours, manages news risk, and can automate quote updates. He predicted small makers could earn "six figures a month" from Kalshi rewards. That was a forecast, not a result (Aug 2025, older). Source: [Adhi Rajaprabhakaran Substack, 25 Aug 2025](https://ufoholdings.substack.com/p/kalshis-new-liquidity-incentives)
- Flickering quotes earn little on Kalshi: a quote live for about 0.1 seconds catches only about 10% of snapshots. Source: [Adhi Rajaprabhakaran Substack](https://ufoholdings.substack.com/p/kalshis-new-liquidity-incentives)
- Once you hold a big share of a market's pool, "you are primarily competing against yourself", so returns per dollar fall. Source: [poly-maker docs, via search](https://github.com/warproxxx/poly-maker) **[snippet only]**
- Kalshi's designated program requires 98% uptime per hour across covered products and a review of financial resources. Source: [Kalshi Help](https://help.kalshi.com/en/articles/13823819-how-to-become-a-market-maker-on-kalshi)
- Kalshi's Liquidity Provider Program (May 2026) is only for firms with a signed Market Maker Agreement. Maker-tier pools ($50,000 per series per week) are far bigger than the open tier ($1,000 per market per day). Source: [Navnoor Bawa Research](https://www.navnoorbawaresearch.com/p/kalshi-publishes-one-liquidity-subsidy) **[sells something]**
- Maker-protection perks need 1% to 7% of all maker volume. That caps how many members can qualify: about 14 at 7%, 33 at 3% (author's maths). Source: [Navnoor Bawa Research](https://www.navnoorbawaresearch.com/p/kalshi-publishes-one-liquidity-subsidy)
- The Roosevelt study says anyone can be a maker in theory, but professionals dominate in practice. Source: [Roosevelt Institute, 7 Jul 2026](https://rooseveltinstitute.org/?p=22369)
- Polymarket: 84.1% of wallets unprofitable overall (all users, not just makers; Apr 2026). Source: [DropsTab](https://news.dropstab.com/research/polymarket-how-to-make-money) **[snippet only]**

### Inferences
- The realistic small-maker niche is quiet markets with reward pools that firms skip. These are low-volatility, slow-news markets where a part-time bot will not get picked off much.
- Rewards are now partly funded by taker fees (Polymarket since 2026). So a small maker's rewards depend on real volume in that market, not a fixed budget.
- For this project: the bot ran on a server next to Kalshi (AWS us-east-2), which helped speed. But quoting 15-minute crypto means racing firms on stale-quote risk. That is the hardest niche for a small maker.

### Gaps
- No verified, recent (2026) P&L from a small or retail market maker on Kalshi or Polymarket.
- No public minimum capital for Kalshi's designated program.
- No data on what share of Polymarket rewards go to the top wallets.

---

## 6. Is the edge shrinking as professional firms enter?

### Takeaway
Yes, mostly. Spreads have tightened, the price bias is shrinking, rewards were cut after 2024, and firms like Jump, SIG and DRW have built teams. Kalshi also ended its volume rewards in Oct 2026 under regulator scrutiny. But per-trade maker profits are still positive. Taker losses grew in dollars because volume exploded, especially in sports parlays.

### Cited findings
- Bürgi et al. find some evidence the price bias is shrinking over time (data to April 2025). Source: [Karl Whelan paper PDF](https://www.karlwhelan.com/Papers/Kalshi.pdf) **[snippet only]**
- Becker: makers lost to takers in Kalshi's early days. Makers only started winning once institutional liquidity providers came in. Source: [The American Prospect, 26 Aug 2026](https://prospect.org/2026/08/26/house-always-wins-kalshi-prediction-markets/)
- Kalshi data from June 2021 to Nov 2025: "spreads compressed 43% while volume rose 166%"; median spread 2.4 cents. Who measured this is unclear. Source: [StockAlarm Predict research page](https://pro.stockalarm.io/predict/research)
- Polymarket rewards were cut sharply after the 2024 election. Source: [The Oracle, 28 May 2025](https://news.polymarket.com/p/automated-market-making-on-polymarket)
- Jump doubled its team to about 20 in 2026 and took stakes in Kalshi and Polymarket for market making (around Feb 2026). The author says market making "is getting crowded" and cross-venue arbitrage "will compress quickly" (opinion). Source: [Crypto Briefing, 16 Jul 2026](https://cryptobriefing.com/jump-trading-prediction-markets-wall-street/)
- Hedge funds were "about to jump in big" (Aug 2026). Source: [CNBC, 19 Aug 2026](https://www.cnbc.com/2026/08/19/hedge-funds-are-about-to-jump-in-big-to-prediction-markets.html) **[snippet only]**
- Susquehanna is building a full prediction-market business (Bloomberg video, 6 Jun 2026). Source: [Bloomberg](https://www.bloomberg.com/news/videos/2026-06-06/why-susquehanna-is-building-a-prediction-market-business-video) **[snippet only]**
- DRW is reported to be hiring traders at base pay up to $200,000. Institutional players are said to hold under 5% of open interest (money in open positions). Neither was confirmed in a primary source. Source: [Tradermath](https://www.tradermath.org/articles/prediction-markets-trading-at-quant-firms) **[snippet only; sells courses/interview prep]**
- Volume grew hugely: over $50 billion combined monthly volume across platforms during the 2026 FIFA World Cup. Source: [Crypto Briefing](https://cryptobriefing.com/jump-trading-prediction-markets-wall-street/)
- Kalshi's share was over 80% of weekly prediction-market volume (DeFi Rate data, cited Aug 2026). Source: [The American Prospect](https://prospect.org/2026/08/26/house-always-wins-kalshi-prediction-markets/)
- Rules tightening: the CFTC advisory on incentive programs (12 Aug 2026) and Kalshi ending its Volume Incentive Program (no earlier than 13 Oct 2026). Sources: [Navnoor Bawa Research](https://www.navnoorbawaresearch.com/p/kalshi-publishes-one-liquidity-subsidy); [Crypto Briefing](https://cryptobriefing.com/kalshi-ends-volume-incentive-program/) **[snippet only]**
- New venues still pay makers well at first. Parlay takers lose 14-26% of stakes on Kalshi, Polymarket US and DKeX (Oct 2026), well above single-game losses. Source: [InGame, 20 Oct 2026](https://www.ingame.com/parlay-takers-lose-dkex-polymarket-us/)

### Inferences
- The edge is moving, not vanishing. Mature single markets (crypto, index, big games) are tight and run by firms. New, complex or thin products (parlays, new listings, niche series) still pay makers a lot, for a while.
- Rewards are trending from a fixed budget toward a share of taker fees, under closer regulator watch. The 2024 Polymarket reward boom is unlikely to come back in the same form.

### Gaps
- No clean time series of Kalshi or Polymarket spreads by year from a primary source.
- No public numbers on how profit per contract for makers changed after SIG (2024) and Jump (2026) arrived.
