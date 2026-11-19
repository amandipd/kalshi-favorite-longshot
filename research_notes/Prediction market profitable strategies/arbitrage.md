# Arbitrage on prediction markets: what people run, and what it really makes

Notes checked on 25 Oct 2026. Every figure has a date. Older findings are marked "older".

Plain words used throughout:
- **Arbitrage**: a set of trades that locks in a profit whatever the outcome.
- **Spread**: the gap between the buy and sell price. It is what it costs to get in.
- **Depth**: how much money you can trade before moving the price.
- **Slippage**: filling worse than the price you aimed at.
- **Taker fee**: the charge for trading against an order already sitting on the book. On Kalshi and Polymarket it is biggest near 50c.
- **Maker**: the trader whose order was already resting on the book. Makers often pay no fee or get a rebate (money back).
- **Resolution-rule mismatch**: two venues settle the "same" question differently because their rules are worded differently.
- **NegRisk market**: Polymarket's name for a market with several outcomes where exactly one wins (for example, "Who wins the election?").

Source quality key used below:
- **[Paper]** academic paper with on-chain or order-book data.
- **[News]** news outlet.
- **[Commentary]** a single writer's blog or Substack.
- **[Vendor]** a site that sells bots, scanners, courses, or uses affiliate links. Treat its numbers as marketing.
- **[Internal]** this project's own tests.

---

## 1. Within-one-market arbitrage (buying every outcome for less than $1)

### Takeaway
The biggest study found about $40 million of this kind of profit taken on Polymarket from April 2024 to April 2025 (an estimate, not audited). A 2026 follow-up using a stricter method found only about $0.3 million in that same year, so the true figure is somewhere in a very wide range. Gaps now close in seconds, and Polymarket's 2026 fees raised the bar.

### Cited findings

**The main paper: Saguillo et al. (older: Aug 2025, data Apr 2024 to Apr 2025)**
- Title "Unravelling the Probabilistic Forest: Arbitrage in Prediction Markets". Authors Oriol Saguillo, Vahid Ghafouri, Lucianna Kiffer, Guillermo Suarez-Tangil (IMDEA Networks). arXiv 2508.03474, posted 5 Aug 2025. Only one version exists. **[Paper]**. Source: [arXiv abstract](https://arxiv.org/abs/2508.03474)
- It was peer-reviewed and published at the AFT 2025 conference (LIPIcs vol. 354). **[Paper]**. Source: [Dagstuhl DROPS](https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.AFT.2025.27)
- Headline: about $40 million of "realized" arbitrage profit taken from Polymarket. **[Paper]**. Source: [arXiv abstract](https://arxiv.org/abs/2508.03474)
- Data: markets that settled 1 Apr 2024 to 1 Apr 2025. On-chain blocks from 1 Jan 2024 to 1 Apr 2025. About 86 million bids. **[Paper]**. Source: [arXiv full text](https://arxiv.org/html/2508.03474v1)
- Sample: 8,659 single-question (YES/NO) markets and 1,578 multi-outcome markets. That is 17,218 conditions in all. **[Paper]**. Source: [arXiv full text](https://arxiv.org/html/2508.03474v1)
- How often a gap appeared: 7,051 of 17,218 conditions (about 41%) had at least one moment where YES + NO was off from $1 by more than 2 cents. 662 of 1,578 multi-outcome markets (about 42%) had at least one gap, about 100 per market on average. **[Paper]**. Source: [arXiv full text](https://arxiv.org/html/2508.03474v1)
- Rules for counting a gap: the price sum had to be more than 2 cents away from $1. For whole markets, the profit had to be at least 5 cents per dollar. Markets were skipped when any outcome was above 95% likely. **[Paper]**. Source: [arXiv full text](https://arxiv.org/html/2508.03474v1)
- Profit split, as the paper reports it **[Paper]**. Source: [arXiv full text](https://arxiv.org/html/2508.03474v1):
  - YES/NO markets: buying both for under $1 made $5.90 million. Selling both for over $1 made $4.68 million. Together, about $10.58 million.
  - Multi-outcome markets (rebalancing every outcome): buy all YES $11.09 million, buy all NO $17.31 million, sell YES $0.61 million, sell NO $4,264. Together, about $29.0 million.
  - Arbitrage between linked markets: $95,157 in total (see section 2).
  - Stated total: $39,587,585.
- The parts add to about $39.69 million, a little more than the stated total. The paper's numbers do not quite match each other. **[Paper, project's own check]**. Source: [arXiv full text](https://arxiv.org/html/2508.03474v1)
- Fees: none were counted, because Polymarket charged no trading fee in that period. **[Paper]**. Source: [arXiv full text](https://arxiv.org/html/2508.03474v1)
- Where the money came from: politics, led by the 2024 US election, made most of the profit taken. Sports had the most gaps in every month except around the election. Crypto had the largest one-off gaps. **[Paper]**. Source: [arXiv full text](https://arxiv.org/html/2508.03474v1)
- Gaps showed up mostly at uncertain moments and when the book was thin (low depth). **[Paper]**. Source: [arXiv full text](https://arxiv.org/html/2508.03474v1)
- Extreme single case: one account (@Tutaaa91) bought YES and NO for under 2 cents each and made $58,983 in one trade. **[Paper]**. Source: [arXiv full text](https://arxiv.org/html/2508.03474v1)
- Risk the paper names: the two legs are not filled together in one step, so a leg can miss. Averaged prices also blur the true profit. **[Paper]**. Source: [arXiv full text](https://arxiv.org/html/2508.03474v1)
- Odd detail to treat with care: the paper gives a median profit "around $0.60" per dollar for YES/NO gaps. That looks far too high to be typical, and may be a typo or a different measure. **[Paper]**. Source: [arXiv full text](https://arxiv.org/html/2508.03474v1)

**The 2026 follow-up that shrinks the $40 million: Gebele, Mutzel and Matthes (1 Aug 2026)**
- Title "Executable Arbitrage and Market Efficiency in Prediction Markets", TU Munich, arXiv 2608.00666. It separates gaps that look like free money from gaps the Polymarket system actually lets you cash in. **[Paper]**. Source: [arXiv](https://arxiv.org/html/2608.00666v1)
- Data: 32,702 events and 259 million trades listed up to 31 Dec 2025. A sample of full order books (every resting order) from 14 Apr to 19 May 2026. **[Paper]**. Source: [arXiv](https://arxiv.org/html/2608.00666v1)
- Total profit it could tie to these trades: about $1.12 million, across all of Polymarket's order-book history to the end of 2025. About 97% ($1.086 million) came through Polymarket's "converter" tool. The converter turns a set of NO shares into cash plus YES shares before the market settles. **[Paper]**. Source: [arXiv](https://arxiv.org/html/2608.00666v1)
- Same one-year window as Saguillo (Apr 2024 to Apr 2025): only $291,424. The authors say the two papers measure different things. **[Paper]**. Source: [arXiv](https://arxiv.org/html/2608.00666v1)
- They left out one odd cluster: 75 conversions on 12 Dec 2025, worth about $381,748. **[Paper]**. Source: [arXiv](https://arxiv.org/html/2608.00666v1)
- Most cashable gaps sat on the YES side: 2,098 positive YES-side episodes against 36 NO-side ones. The system can turn NO sets into cash, but has no reverse tool for YES sets. **[Paper]**. Source: [arXiv](https://arxiv.org/html/2608.00666v1)
- How fast gaps closed (Apr to May 2026): the median gap lasted 16.15 seconds (253 YES-side gaps). Another 366 of 624 gaps (58.7%) ran past the edges of the recording windows, so their length is unknown. **[Paper]**. Source: [arXiv](https://arxiv.org/html/2608.00666v1)
- Costs: the paper subtracts fees and assumes you pay the taker fee every time. It ignores gas (the blockchain's charge per transaction) because Polymarket's relayer pays it. **[Paper]**. Source: [arXiv](https://arxiv.org/html/2608.00666v1)

**Short crypto markets (5 and 15 minutes), 2025 to 2026**
- CoinDesk (21 Feb 2026) relays an X post about a bot that bought YES and NO below $1 in 5-minute BTC and ETH markets. It reportedly made nearly $150,000 over 8,894 trades, about $16.80 per trade. The figure is unverified and has no dates. **[News relaying social media]**. Source: [CoinDesk](https://www.coindesk.com/markets/2026/02/21/how-ai-is-helping-retail-traders-exploit-prediction-market-glitches-to-make-easy-money)
- Same article: these gaps "often" last milliseconds. Depth in 5-minute BTC markets is about $5,000 to $15,000 per side in busy sessions. A $100,000 trade would use up all of it. **[News]**. Source: [CoinDesk](https://www.coindesk.com/markets/2026/02/21/how-ai-is-helping-retail-traders-exploit-prediction-market-glitches-to-make-easy-money)
- Polymarket added a taker fee to its 15-minute crypto markets in early January 2026. Reports say the goal was to blunt fast bots that had thrived when trading was free. **[News]**. Sources: [The Block](https://www.theblock.co/post/384461/polymarket-adds-taker-fees-to-15-minute-crypto-markets-to-fund-liquidity-rebates); [Cointelegraph](https://cointelegraph.com/news/polymarket-quietly-adds-taker-fees-15-minute-crypto-markets)
- Note: the famous "wallet 0x8dxd turned about $313 into $414,000 to $438,000" story (Dec 2025 to Jan 2026) is not true arbitrage. It is speed betting: buying the side Binance and Coinbase prices had already settled before Polymarket's price caught up. Reported figures differ by source and are unaudited. **[News, secondhand]**. Sources: [Finance Magnates, 16 Mar 2026](https://www.financemagnates.com/trending/prediction-markets-are-turning-into-a-bot-playground/); [MEXC news repost](https://www.mexc.com/news/417346)

**PredictIt (older: 2016 to 2022)**
- Eric Zitzewitz, NBER working paper 35845 (Oct 2026), on PredictIt 2016 to 2022. Bid prices across a market's outcomes "often persistently" added to more than 110 cents. That meant a sure profit even after fees. The $850 cap per contract held back the arbitrage traders who would have closed it. **[Paper]**. Source: [NBER](https://www.nber.org/papers/w35845)

### Inferences
- The $40 million is best read as a ceiling, not a measured profit. A stricter method on the same year finds about 1/136th of it ($291K). The truth likely sits between the two, and nobody has audited it.
- About three quarters of the $40 million came from multi-outcome markets, not simple YES/NO pairs. Those markets have more legs, so they are easier to misprice and harder to fill.
- The gaps cluster when books are thin. So the dollar size of any one gap is small, even when the percentage looks big.
- Polymarket ran with no trading fee during the main study. Its 2026 fees (section 3) now take up to 1 to 1.75 cents per share at 50c, per leg. That alone wipes out many of the 2-cent gaps the 2025 paper counted.

### Gaps
- No study gives the full spread of sizes of these gaps in cents, after fees, for 2026.
- No audited P&L (profit and loss) exists for any named within-market arbitrage wallet. The $150K bot and similar stories are social-media claims.
- No Saguillo et al. follow-up by the same authors was found.

---

## 2. Linked-market (combinatorial or logical) arbitrage

### Takeaway
This is the most talked-about kind and the smallest in measured profit. The 2025 paper found only about $95,000 taken across 13 confirmed pairs of linked markets in a year. Most "linked" pairs that software flagged turned out not to be truly linked.

### Cited findings
- What it is: two markets whose answers depend on each other, priced in a way that cannot both be right. Example: "wins the popular vote" against "wins the presidency". **[Paper]**. Source: [arXiv full text](https://arxiv.org/html/2508.03474v1)
- Saguillo et al. (older: Aug 2025) used an AI language model (DeepSeek-R1-Distill-Qwen-32B) to find linked pairs. It flagged 1,576 pairs as linked. Only 13 survived a manual check. **[Paper]**. Source: [arXiv full text](https://arxiv.org/html/2508.03474v1)
- The model gave fully usable answers for only 81.45% of 128 multi-outcome markets tested. It sometimes got stuck in loops. **[Paper]**. Source: [arXiv full text](https://arxiv.org/html/2508.03474v1)
- Realized profit across the confirmed pairs: $95,157 in total. The best pair made $60,237. The others made $18,472, $15,819, and $629. **[Paper]**. Source: [arXiv full text](https://arxiv.org/html/2508.03474v1)
- The "popular vote vs presidency" pair had 6,630 gap moments. But most were in thin books, with an average best profit of about $100 each (under about 2,000 shares). **[Paper]**. Source: [arXiv full text](https://arxiv.org/html/2508.03474v1)
- Only 5 of 11 election pairs showed any executed arbitrage. (The paper says 13 pairs in one place and 11 in another.) **[Paper]**. Source: [arXiv full text](https://arxiv.org/html/2508.03474v1)
- Across venues, Gebele and Matthes (5 Jan 2026) found 1,645 sets of events where one is a narrower version of another ("subset" links), and 1,123 multi-outcome sets spanning 2,771 markets. Data ran to 15 to 22 Aug 2025. **[Paper]**. Source: [arXiv 2601.01706](https://arxiv.org/html/2601.01706v1)
- A 2026 research tool, PolySwarm (arXiv 2604.03888), uses several AI agents to look for gaps between related markets and between a market and its opposite. It is a framework, not a profit record. **[Paper]**. Source: [arXiv 2604.03888](https://arxiv.org/html/2604.03888v1)

### Inferences
- The hard part is not the maths. It is deciding whether two markets truly depend on each other under their exact rules. Software gets this wrong most of the time (13 real out of 1,576 flagged).
- Date-ladder markets ("by March", "by June", "by December") should be the cleanest case, since a later date must be at least as likely. But no study was found that measures profit on them alone.

### Gaps
- No measured profit for date-ladder or "state vs national" arbitrage outside the 2024 election pairs.
- No 2026 update on linked-market profit after Polymarket's fees.

---

## 3. Cross-venue arbitrage (Kalshi, Polymarket, PredictIt, Betfair, sportsbooks)

### Takeaway
Price gaps between venues are real and slow to close: typically 2 to 4% on matched markets (to Aug 2025). They stay open because the contracts are not truly the same. Rules, settlement sources, fees, access limits and locked-up cash eat most of it. There are documented cases where venues settled the "same" event differently, which would have hurt a two-sided hedge.

### Cited findings

**How big the gaps are**
- Gebele and Matthes (TU Munich, 5 Jan 2026), "Semantic Non-Fungibility and Violations of the Law of One Price". They covered 102,275 events on 10 venues, including Polymarket, Kalshi and PredictIt, from 2018 to Aug 2025. **[Paper]**. Source: [arXiv 2601.01706](https://arxiv.org/html/2601.01706v1)
- About 6% of events are linked to an event on another venue. About 8% of Polymarket's markets have a twin elsewhere, against about 2% of Kalshi's. **[Paper]**. Source: [arXiv 2601.01706](https://arxiv.org/html/2601.01706v1)
- For the most heavily traded twins, the median gap after counting what it costs to trade was 2 to 4% away from equal prices. Gaps had to last at least an hour to count. Many pairs stayed apart for nearly their whole shared life. **[Paper]**. Source: [arXiv 2601.01706](https://arxiv.org/html/2601.01706v1)
- Returns if held to settlement: many gaps implied small yearly returns, but a big share implied over 200% a year. A simple rule from 2022 that always took the best twin gap and held it returned 1,218.66% in total over 800 days. That was from only 15 trades, so it is a small sample. **[Paper]**. Source: [arXiv 2601.01706](https://arxiv.org/html/2601.01706v1)
- The authors' reason: venues lack a shared, checkable identity for an event. So prices are set venue by venue, not across the whole market. **[Paper]**. Source: [arXiv 2601.01706](https://arxiv.org/html/2601.01706v1)

**2024 US election (older: Nov 2024)**
- Polymarket had over $3.3 billion traded and Kalshi over $1 billion. Before the networks called the race, the gap after trading costs averaged about 3 cents and held at up to 7 cents for long stretches. **[Paper]**. Source: [arXiv 2601.01706](https://arxiv.org/html/2601.01706v1)
- Why it was not risk-free: Polymarket and Limitless settled on the media networks' call. Kalshi and Myriad settled on the inauguration. Kalshi charged no fee on that market. **[Paper]**. Source: [arXiv 2601.01706](https://arxiv.org/html/2601.01706v1)

**Cases where venues settled differently, or rules shifted**
- Government shutdown market (older: Dec 2024). Polymarket settled YES even though no shutdown happened. Kalshi settled NO. Source is one commentator; no primary record was found. **[Commentary]**. Source: [Michael Wenye Li, 27 May 2025](https://michaellwy.substack.com/p/prediction-markets-cant-agree-on)
- Same case: the dispute centred on a "rule clarification" Polymarket added after heavy trading. It brought in a 20 Dec 2024 midnight deadline. **[Commentary, secondhand]**. Sources: [Michael Wenye Li](https://michaellwy.substack.com/p/wisdom-of-crowds-or-collective-delusion); [Monad blog](https://monad.xyz/blog/prediction-market-disputes)
- US Bitcoin Reserve (older: May 2025). Polymarket YES was at 51% while Kalshi's similar market was at 37%. Kalshi NO (63%) plus Polymarket YES (51%) added to 114%. But the rules differed. Polymarket took "credible reporting". Kalshi needed confirmation from the White House or the New York Times. **[Commentary]**. Source: [Michael Wenye Li](https://michaellwy.substack.com/p/prediction-markets-cant-agree-on)
- Cardi B at the Super Bowl halftime show (Feb 2026). Kalshi called it unclear and settled at the last traded price: 26 cents for YES, 74 cents for NO. Kalshi's market had over $47 million traded. Polymarket first settled YES, with over $5 million on Cardi B. That went to a UMA token-holder vote (UMA is the outside voting system Polymarket uses to settle disputes). **[News]**. Sources: [Front Office Sports, 10 Feb 2026](https://frontofficesports.com/article/cardi-b-is-a-cautionary-tale-for-prediction-markets/); [WTOP/AP, 11 Feb 2026](https://wtop.com/sports/2026/02/cardi-bs-cameo-in-bad-bunnys-super-bowl-halftime-show-leads-to-dispute-on-prediction-markets/)
- Same case: Polymarket added a note after the event saying taking part without singing counted. Traders disputed it. A Kalshi YES holder filed a complaint with the CFTC (the US regulator) seeking $3,700. **[News]**. Sources: [Front Office Sports](https://frontofficesports.com/article/cardi-b-is-a-cautionary-tale-for-prediction-markets/); [WTOP/AP](https://wtop.com/sports/2026/02/cardi-bs-cameo-in-bad-bunnys-super-bowl-halftime-show-leads-to-dispute-on-prediction-markets/)
- Venezuela "invasion" (Jan 2026). After US forces captured Maduro on 3 Jan 2026, Polymarket ruled it was not an "invasion" under its wording ("operations intended to establish control"). The 31 Jan contract settled NO, with about $8.4 million traded. About $10.5 million sat across the family of these markets. **[News]**. Sources: [Quartz](https://qz.com/polymarket-says-us-raid-venezuela-not-invasion); [DeFi Rate](https://defirate.com/?p=3283); [Gambling Insider](https://www.gamblinginsider.com/?p=101486)
- "Khamenei out" (Mar 2026). Kalshi used a "death carve-out" rule. It halted the market and settled at the last price before the news, not at YES. The market had over $50 million traded. A class action in California seeks $54 million. Plaintiffs say the carve-out was not in the user-facing rules summary. **[News]**. Sources: [Decrypt](https://decrypt.co/360293/kalshi-sued-refusing-pay-out-prediction-market-iran-leader-death); [Cointelegraph](https://cointelegraph.com/news/kalshi-sued-khamenei-trade-carveout); [Finance Magnates](https://www.financemagnates.com/fintech/khamenei-out-market-becomes-legal-headache-for-kalshi/)

**Fees and costs by venue (checked Oct 2026 unless marked)**

| Venue | Fee rule, in plain words | Biggest bite | Source |
|---|---|---|---|
| Kalshi | Taker pays 0.07 × contracts × price × (1 − price), rounded up to the next cent. Most markets charge makers nothing. Some series charge makers a quarter of that (0.0175). | About 1.75c per contract at 50c (some tables show 2c after rounding) | [next.io](https://next.io/prediction-markets/kalshi/fees/); [SailGP guide](https://sailgp.com/prediction-markets/kalshi/fees); [Kalshi fee PDF](https://kalshi.com/docs/kalshi-fee-schedule.pdf) |
| Polymarket (global) | Taker pays rate × shares × price × (1 − price). Rate: crypto 0.07, sports 0.05, politics/finance/tech 0.04, geopolitics 0. Makers pay nothing and get 15 to 25% back. | Per share at 50c: crypto 1.75c, sports 1.25c, politics 1.0c | [Polymarket docs](https://docs.polymarket.com/trading/fees) |
| Polymarket US (CFTC-regulated app) | Same shape. Taker rate raised from 0.06 to 0.0695 on 17 Sep 2026, per a summary of the CFTC filing (the filing itself was not opened) | About 1.7c per contract at 50c (the project's calculation) | [CFTC filing](https://www.cftc.gov/filings/orgrules/rules09212628660.pdf) |
| PredictIt | 10% of profit on each winning trade, plus 5% of every withdrawal. Cap of $3,500 per contract (was $850). | About $15.50 on a $100 profit, cashed out | [Casino.org](https://www.casino.org/us/predictions/predictit/); [WSN](https://www.wsn.com/prediction-markets/predictit/) |
| Betfair Exchange | Commission on net winnings per market. Plus an "Expert Fee" since 6 Jan 2025: 20% of gross profit for £25k-£100k a year, 40% above £100k. | Expert Fee hits exactly the steady winners an arbitrage trader becomes | [Racing Post](https://racingpost.com/news/britain/betfair-exchange-to-introduce-new-commission-system-for-2025-as-premium-charge-is-dropped-a7wbg0v4GCAJ) |

- Polymarket's fee timeline in 2026: 15-minute crypto fees on 5 Jan. Sports fees on 18 Feb. All crypto timeframes by 6 Mar. Nearly every category on 30 Mar, with geopolitics left free. **[Commentary/analyst]**. Source: [Pine Analytics, 25 Mar 2026](https://pineanalytics.substack.com/p/polymarket-fee-rollout)
- Conflict on the sports rate. Pine Analytics and Sacra put sports at 0.03 from 30 Mar 2026 (0.75% at 50c). Polymarket's docs page, read in Oct 2026, shows 0.05 (1.25% at 50c). So the rate was likely raised after March. **[Analyst vs official]**. Sources: [Pine Analytics](https://pineanalytics.substack.com/p/polymarket-fee-rollout); [Sacra](https://www.sacra.com/c/polymarket/); [Polymarket docs](https://docs.polymarket.com/trading/fees)
- Polymarket fee revenue: about $1.2 million a day gross on about $160 million a day of taker trading. That is about 0.76% of taker volume on average (Mar 2026 estimate). **[Analyst]**. Source: [Pine Analytics](https://pineanalytics.substack.com/p/polymarket-fee-rollout)
- Betfair's standard base rate: Betfair's own page could not be opened (it returned an error). The old "Premium Charge" went as high as 60%. **[News]**. Source: [Racing Post](https://racingpost.com/news/britain/betfair-exchange-to-introduce-new-commission-system-for-2025-as-premium-charge-is-dropped-a7wbg0v4GCAJ)

**Cash locked until settlement**
- Kalshi pays interest on both cash and open positions. Its help pages have shown 3.25%, 3.50% and 4.05% a year at different times. You need at least $250 to be paid. **[Official]**. Source: [Kalshi help](https://help.kalshi.com/navigating-the-exchange/your-portfolio/apy-on-kalshi)
- Polymarket pays a 4.00% yearly "holding reward" only on a short list of long-dated political and geopolitical markets (for example, the 2028 presidential race). **[Official]**. Source: [Polymarket docs](https://docs.polymarket.com/polymarket-learn/trading/holding-rewards)

**Prediction markets vs sportsbooks**
- An analysis from Citizens (a bank's research desk), reported in Sep 2025, found Kalshi's NFL pre-game prices 8% worse than FanDuel's and 6% worse than DraftKings's, after Kalshi's fees. **[News]**. Source: [Yogonet, 9 Sep 2025](https://www.yogonet.com/international/news/2025/09/09/115258-kalshi-trading-hits-441m-in-first-nfl-week-but-analysts-flag-pricing-gap-with-sportsbooks)
- By Oct 2026 this had flipped on single-game bets. The built-in house cut (called "vig") was 4.28% on Kalshi, 4.41% on FanDuel and 4.47% on DraftKings. On parlays (several bets combined), Kalshi's cut was higher: 26.5% against 23.2%. **[News]**. Source: [RotoWire, 5 Oct 2026](https://www.rotowire.com/article/kalshi-beats-draftkings-fanduel-on-nfl-week-1-pricing-134248)
- Kalshi's average fee in that analysis was $1.62 per 100 contracts. **[News]**. Source: [RotoWire](https://www.rotowire.com/article/kalshi-beats-draftkings-fanduel-on-nfl-week-1-pricing-134248)

**This project's own test (Oct 2026)**
- Kalshi vs Polymarket US, 15-minute BTC up/down, 13 to 16 Oct 2026. Both venues settled the same way in 206 of 206 windows. But in Polymarket US's first days (22 to 24 Sep), 1 of 209 windows settled opposite, which would lose both legs. **[Internal]**. Source: the project's own Kalshi vs Polymarket US comparison (Oct 2026).
- Same test: Polymarket's public price feed was cached, with a median age of 15 seconds. That stale data made 30% of pairs look profitable. With fresh data (under 5 seconds old), only about 20% were positive after fees. The median pair lost 0.8 to 1.4 cents. Arbitrage was not proven. **[Internal]**. Source: the project's own comparison (Oct 2026).

**Vendor claims on cross-venue gaps (low trust)**
- Vendor guides say a 13-cent gross gap often nets 8 to 10 cents, while a 4-cent gap is often a loss after fees on both sides. These are not measured. **[Vendor]**. Sources: [Laika Labs](https://laikalabs.ai/prediction-markets/polymarket-kalshi-arbitrage-guide); [ClawArbs](https://clawarbs.com/blog/kalshi-vs-polymarket-arbitrage/)
- One vendor warns that Polymarket's Fed markets use "change buckets" while Kalshi uses a rate ladder. So a 4-cent Fed "gap" may not be a true twin. **[Vendor]**. Source: [NYC Servers guide](https://newyorkcityservers.com/blog/prediction-market-arbitrage-guide)

### Inferences
- A rule mismatch can cut either way. Take the Cardi B case. A hedger holding Kalshi NO plus Polymarket YES would have been paid 74c + $1 = $1.74 on a roughly $1 outlay. The reverse hedge (Kalshi YES plus Polymarket NO) would have got back only 26c. So the "arbitrage" turns into a bet on how each venue reads its rules.
- Kalshi's habit of settling at the last traded price in unclear cases (Cardi B, Khamenei) is a risk that a YES/NO pair across venues cannot hedge.
- Fees now apply on both main venues. A two-leg trade near 50c pays about 1.75c on Kalshi plus 1 to 1.75c on Polymarket. That is about 3 to 3.5 cents per $1 pair before any spread. Most gaps under about 4 cents near 50c are gone after costs. Near 90c+ the fees are much smaller (about 0.6c per leg on Kalshi).
- Interest on Kalshi (about 4% a year) softens the cost of locked cash on that leg. Polymarket pays it only on a few markets. Over a year-long political market, lost interest on the Polymarket leg alone is about 4 cents per $1.
- Sportsbooks charge about 4.3 to 4.5% each way on single games in 2026. So a true book-vs-exchange arbitrage is rare. Sportsbooks also limit accounts that win steadily, though no source was found measuring this for prediction-market hedgers.

### Gaps
- No academic study of net, after-fee profit from Kalshi-vs-Polymarket arbitrage in 2026 (after Polymarket's fees started).
- No documented case was found of a named trader losing money on a cross-venue hedge because of a rule mismatch. Mismatch cases are reported, but the losers are not.
- The Dec 2024 shutdown split has only one commentator source.
- Not confirmed: how Polymarket settled its own Khamenei market, or the final UMA vote on Cardi B.
- Withdrawal limits and deposit fees on Kalshi and Polymarket were not confirmed.

---

## 4. Tools and services that sell arbitrage scanning

### Takeaway
Many sites sell scanners or bots. None publish audited results. The best warning comes from a scanner seller and from this project's own test: most scanners use stale or "last trade" prices you cannot actually trade at.

### Cited findings
- Oddpool (Kalshi + Polymarket scanner): free tier, Pro about $30 a month or $200 a year, Premium $100 a month with API access. It claims "hundreds of arbitrage opportunities every week". It also claims one trade can pay more than the monthly fee. These are the seller's own claims. **[Vendor]**. Sources: [Oddpool pricing](https://www.oddpool.com/pricing); [QuickNode listing](https://quicknode.com/builders-guide/tools/oddpool-by-oddpool-inc)
- A Polymarket scanner on Apify says almost every scanner works from last-trade or mid prices that you can never trade at. **[Vendor, self-interested but useful]**. Source: [Apify Real-Arb Scanner](https://apify.com/ebag73/polymarket-arb-scanner)
- Eventarb: a multi-venue spread calculator. One directory lists only one review for it. **[Directory]**. Source: [pm.wiki](https://pm.wiki/compare/eventarb-vs-polyscalping)
- Other scanner and bot sellers seen: PredictMarketCap, Prediction.com, ClawArbs, PolyCopy, Laika Labs, Kairos, PolyTraderBot, polbots.com ("123 bots compared by ROI"). All sell tools or carry affiliate links. **[Vendor]**. Sources: [PredictMarketCap](https://predictmarketcap.com/arbitrage); [Prediction.com](https://prediction.com/arbitrage); [ClawArbs](https://clawarbs.com/blog/polymarket-arbitrage-bot/); [polbots.com](https://polbots.com/)
- Bot sellers advertise "$10 to $50 a day risk-free on $10,000" and "2 to 5% edges on sports". These are not measured results. **[Vendor]**. Source: [ClawArbs](https://clawarbs.com/blog/best-polymarket-trading-bot/)
- Some paid bots claim to copy an account that "scaled $68 into $1.5M". Unverified sales pages. **[Vendor]**. Source: [polymtradebot.com](https://polymtradebot.com/)
- Self-reported dev blogs claim results such as "$130k+" from YES + NO mispricing. They are not audited and often link to paid code. **[Self-reported]**. Source: [DEV Community](https://dev.to/cryptomoonday/how-my-polymarket-arbitrage-bot-made-130k-using-simple-yes-no-mispricing-2gd1)

### Inferences
- A scanner's "opportunity" count is worth little unless it uses the live order book (all resting orders, with depth), both venues' fees, and fresh data. This project's own test showed stale data alone turned a losing trade into a 30% "hit rate".
- If a scanner's claims were true at scale, the 2026 paper's measured cashable profit (about $1.1 million across all Polymarket history) would be far larger.

### Gaps
- No independent test of any paid scanner's past alerts against real fills.

---

## 5. Who wins: bots, funds, or individuals? How much speed and cash?

### Takeaway
Profits are lopsided. In 2024 to 2025 the top 10 accounts took about a fifth of all within-Polymarket arbitrage profit. Bots hold most top leaderboard spots. Big trading firms are now paid to make markets on both main venues. Speed matters for in-venue gaps (seconds or less). Thin books cap how much cash any one trader can use.

### Cited findings
- Saguillo et al. (older: Apr 2024 to Apr 2025): the top account made $2,009,632 over 4,049 transactions, about 5.1% of the total. That is about $496 per transaction. The top 10 accounts made about $8.18 million, about 20.7%. Some accounts show bot-like volume. **[Paper]**. Source: [arXiv full text](https://arxiv.org/html/2508.03474v1)
- A review of Polymarket's public leaderboard (Mar 2026) found 14 of the 20 most profitable wallets were bots. It does not say who did the review. **[News, secondhand]**. Source: [Finance Magnates, 16 Mar 2026](https://www.financemagnates.com/trending/prediction-markets-are-turning-into-a-bot-playground/)
- A study of 95 million Polymarket transactions (Apr 2024 to Dec 2025) found only 0.51% of wallets made over $1,000 profit. It is attributed to Thorsten Meyer, but it is mostly seen as syndicated reposts, with unclear methods. **[Unclear origin]**. Sources: [The Idea Magazine](https://theideamagazine.com/business-industry/are-polymarket-trading-bots-actually-profitable-the-math-behind-2026-s-predictio/); [KuCoin news](https://www.kucoin.com/news/flash/polymarket-2025-six-core-profit-strategies-revealed-from-95m-on-chain-transactions)
- Susquehanna (SIG) said in April 2024 that it makes markets on Kalshi. Jump Trading is taking small stakes in both Kalshi and Polymarket in return for providing liquidity (Bloomberg, via The Block). DRW is hiring for a prediction-market desk (2026). **[News]**. Sources: [The Block](https://www.theblock.co/post/389086/jump-trading-to-serve-as-polymarket-and-kalshi-market-maker-in-exchange-for-stake-bloomberg); [Decrypt](https://decrypt.co/357519/jump-trading-earn-stakes-polymarket-kalshi?amp=1); [TraderMath](https://www.tradermath.org/articles/prediction-markets-trading-at-quant-firms)
- A June 2026 industry note says firms run cross-venue arbitrage, market-structure arbitrage and news-driven strategies. No number was found for how much of their activity is arbitrage. **[Industry note]**. Source: [Cobo](https://website.sandbox.cobo.com/agentic-wallet/news/prediction-markets-go-institutional-quant-giants-and-market-makers-build)
- Speed: within-Polymarket gaps you can cash in had a median life of about 16 seconds in Apr to May 2026. **[Paper]**. Source: [arXiv 2608.00666](https://arxiv.org/html/2608.00666v1)
- Cross-venue gaps are slower: the 2026 study counted those lasting over an hour. **[Paper]**. Source: [arXiv 2601.01706](https://arxiv.org/html/2601.01706v1)
- Cash limit: depth in 5-minute BTC markets on Polymarket is about $5,000 to $15,000 per side. **[News]**. Source: [CoinDesk](https://www.coindesk.com/markets/2026/02/21/how-ai-is-helping-retail-traders-exploit-prediction-market-glitches-to-make-easy-money)
- The 2024 election linked pairs averaged about $100 of best profit per gap. **[Paper]**. Source: [arXiv full text](https://arxiv.org/html/2508.03474v1)
- Gas: on markets with many outcomes, the proposed tool's gas cost rises from about 0.70 million to 25.32 million units across 5 to 196 outcomes. That limits big multi-outcome trades. **[Paper]**. Source: [arXiv 2608.00666](https://arxiv.org/html/2608.00666v1)
- Access: the Kalshi-Polymarket pair is closed to many traders. US users mostly cannot use global Polymarket, and Kalshi is US-focused. **[Vendor]**. Source: [NYC Servers guide](https://newyorkcityservers.com/blog/prediction-market-arbitrage-guide)

### Inferences
- In-venue gaps go to bots that see the order book first. A human clicking cannot compete with a 16-second median life.
- Cross-venue gaps last longer. But catching them needs accounts on both venues, legal access to both, cash parked on both until settlement, and someone who reads both rulebooks. Those needs favour firms, not speed.
- The top account's roughly $500 per transaction (2024 to 2025) points to many small, steady wins, not a few big ones.

### Gaps
- No public P&L from any named firm's arbitrage book.
- No figure for the share of Polymarket or Kalshi volume that comes from arbitrage bots.

---

## 6. Is the edge fading (2024 to 2026)?

### Takeaway
Yes, for simple in-venue arbitrage. Gaps now close in seconds, and Polymarket added fees through Jan to Mar 2026 that eat most 1 to 2 cent gaps. Cross-venue gaps of 2 to 4% persisted to Aug 2025. But they persist because they are not risk-free, and 2026 brought fees and more rule disputes.

### Cited findings
- Older picture (PredictIt 2016 to 2022): price sums often stayed above 110 cents for long periods, because a $850 cap kept arbitrage traders small. **[Paper]**. Source: [NBER w35845](https://www.nber.org/papers/w35845)
- 2024 to 2025 (Polymarket, fee-free): gaps appeared in about 41% of conditions. They clustered in thin, uncertain moments, and the authors grouped bids into roughly one-hour windows. **[Paper]**. Source: [arXiv full text](https://arxiv.org/html/2508.03474v1)
- Apr to May 2026: the median cashable in-venue gap lasted about 16 seconds. **[Paper]**. Source: [arXiv 2608.00666](https://arxiv.org/html/2608.00666v1)
- Polymarket brought in taker fees step by step from 5 Jan to 30 Mar 2026. The first ones were aimed at fast bots in 15-minute crypto markets. **[Analyst/News]**. Sources: [Pine Analytics](https://pineanalytics.substack.com/p/polymarket-fee-rollout); [The Block](https://www.theblock.co/post/384461/polymarket-adds-taker-fees-to-15-minute-crypto-markets-to-fund-liquidity-rebates)
- Sports volume on Polymarket still rose after fees, from $100-150 million a day to $150-250 million a day (early 2026). **[Analyst]**. Source: [Pine Analytics](https://pineanalytics.substack.com/p/polymarket-fee-rollout)
- Cross-venue: gaps between the most heavily traded twin markets shrank "only gradually" as trading grew (to Aug 2025). **[Paper]**. Source: [arXiv 2601.01706](https://arxiv.org/html/2601.01706v1)
- Vendor claim: cross-venue windows fell from about 12.3 seconds (2024) to about 2.7 seconds (early 2026). No data behind it. **[Vendor]**. Sources: [Medium / ILLUMINATION](https://medium.com/illumination/beyond-simple-arbitrage-4-polymarket-strategies-bots-actually-profit-from-in-2026-ddacc92c5b4f); [TurbineFi](https://www.turbinefi.com/blog/prediction-market-arbitrage-latency-speed-2026)
- Another unverified figure: "only about 1% of election arbitrage chances were taken", credited to the Saguillo paper. It does not appear in the parts of the paper that were read. **[Secondhand]**. Source: [search summary of arXiv 2508.03474; not confirmed](https://arxiv.org/html/2508.03474v1)
- CoinDesk (Feb 2026): as more competitors arrive, "spreads tighten" and speed "becomes decisive". **[News]**. Source: [CoinDesk](https://www.coindesk.com/markets/2026/02/21/how-ai-is-helping-retail-traders-exploit-prediction-market-glitches-to-make-easy-money)
- Platforms are moving to pay makers. Polymarket now gives makers 15 to 25% of taker fees back, and big firms (SIG, Jump) are paid to make markets. **[Official/News]**. Sources: [Polymarket docs](https://docs.polymarket.com/trading/fees); [The Block](https://www.theblock.co/post/389086/jump-trading-to-serve-as-polymarket-and-kalshi-market-maker-in-exchange-for-stake-bloomberg)

### Inferences
- The free-money era on Polymarket (no fees, thin books, 2024 election) looks like the peak. The $40 million estimate covers that unusual year.
- What is left in 2026 falls into three groups:
  1. In-venue gaps lasting seconds, taken by bots, now taxed by fees.
  2. Cross-venue gaps lasting hours to months, which are really bets on rule wording.
  3. Maker strategies that earn rebates (money back on fees), rather than pure arbitrage.
- For this project: its own Oct 2026 test of Kalshi vs Polymarket US on 15-minute BTC found no proven arbitrage after fees. That matches the outside evidence.

### Gaps
- No study tracks the same arbitrage measure month by month from 2024 into late 2026.
- No published measure of how Polymarket's 2026 fees changed the number or size of in-venue gaps.
