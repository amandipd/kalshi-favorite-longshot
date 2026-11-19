# AI forecasting agents, news signals and order-flow signals on prediction markets

Notes as of 26 October 2026. Each finding gives its own date. Older items are labelled.

Plain words used throughout (repeated in place where they matter):
- Brier score = the average squared miss between a forecast and what happened. Lower is better. 0 is perfect. Always saying 50% scores 0.25.
- Calibration = whether a 70% forecast really comes true 70% of the time. ECE (expected calibration error) = the average gap between stated confidence and how often it came true.
- Adverse selection = getting picked off by someone who knows more than you.
- Kalshi taker fee = 7% x price x (1 - price) per contract. That is 1.75c per contract at 50c (3.5% of the money bet), 1.47c at 70c, 0.63c at 90c, and about 0.52c at 92c.

## Q1. Do the best AI forecasters beat market prices, match them, or lose? (benchmarks)

### Takeaway
On live Kalshi questions, the best AI models now sit slightly above the market price on accuracy, but the lead is tiny. On liquid-market questions elsewhere, AI alone still trails the market. AI blended with the market beats the market alone. Against human experts, AI has roughly caught up in 2026, but not clearly passed them. No benchmark reports trading profit clearly after Kalshi fees and the spread (the gap between the buy and sell price).

### Cited findings

**Prophet Arena (UChicago SIGMA lab with Kalshi; live, built on Kalshi markets)**
- The live leaderboard (last scored 25 Oct 2026) puts the "Market" row at an Arena score of 84.32. Arena score = Prophet Arena's 0-100 accuracy score, adjusted for how hard the events were; 100 is perfect. Source: [Prophet Arena leaderboard](https://www.prophetarena.co/leaderboard/forecast)
- All top 10 model setups score above the market, by 0.78 to 1.49 points. The top row is Claude Opus 5.5 (OpenCode harness) at 85.81 (give or take 0.63) on 363 events. Claude Fable 5 (Claude Code harness) scores 85.48 (give or take 0.42) on the largest sample, 2,026 events. The page gives no error range for the market row, so it cannot say if these gaps are beyond luck. Source: [Prophet Arena leaderboard](https://www.prophetarena.co/leaderboard/forecast)
- The same page shows a simulated "average return" where 100% means breaking even. Top-10 values run from 88.99% (a loss: DeepSeek V4.1 Flash) to 124.70% (Claude Fable 5). Two models that beat the market on accuracy still lost money in this simulation (GLM-5.3 at 93.77%, DeepSeek V4.1 Flash at 88.99%). The page does not say if fees or the spread are deducted. Source: [Prophet Arena leaderboard](https://www.prophetarena.co/leaderboard/forecast)
- An earlier snapshot (date unclear) used a different score, 1 minus Brier. There the Kalshi market scored 0.9460 and the top models about 0.948 to 0.949. That is a gap of about 0.002 to 0.003 in Brier terms. Source: [Prophet Arena leaderboard, via search summary](https://www.prophetarena.co/leaderboard/forecast)
- A 2025 summary (about a year old) said most AI forecasters beat the average human trader on Kalshi, but all were worse than the best humans. Source: [ML Safety Newsletter #16](https://x.com/ml_safety/article/1968005866562740251?lang=en)

**Prophet Arena paper: "When do prophets profit in prediction markets?" (arXiv, 7 July 2026)**
- Authors are from UChicago and NYU Shanghai, plus one from Kalshi Research. Source: [arXiv 2607.06166](https://arxiv.org/html/2607.06166v1)
- Main theory claim: a "proper" betting rule earns positive expected profit whenever the forecast beats the market on a proper scoring rule (such as Brier) and the market has enough depth (how much money you can trade before moving the price). Source: [arXiv 2607.06166](https://arxiv.org/html/2607.06166v1)
- Offline test on a 200-event shared subset of 2,418 Kalshi markets (sports, politics, economics, crypto). Results below. "Brier gap" = how much better the model scored than the market (positive = beat the market). Source: [arXiv 2607.06166](https://arxiv.org/html/2607.06166v1)

| Model | Brier gap vs market (plus = better than market) | Return with the paper's Brier-based bet sizing | Return with full Kelly (the bet size that grows money fastest if your odds are right) |
|---|---|---|---|
| Claude Opus 4.6 | +0.0016 | +22.1% | -99.9% (wiped out) |
| Gemini 3 | +0.0008 | +8.1% | -42.7% |
| GPT-5.2 (Base) | -0.0347 (worse than market) | +4.5% | -99.9% (wiped out) |
| LLaMA 4 Maverick | -0.0450 | -13.7% | -99.9% (wiped out) |
| Grok 4.1 Fast | -0.0462 | -11.6% | -99.9% (wiped out) |

- The offline test assumes "zero price impact" (your own trade does not move the price). The paper's return breakdown has no fee term. The excerpts read do not say whether fees were deducted offline. Source: [arXiv 2607.06166](https://arxiv.org/html/2607.06166v1)
- Only 2 of 5 models beat the market at all, and by very small margins (+0.0008 and +0.0016 Brier). Source: [arXiv 2607.06166](https://arxiv.org/html/2607.06166v1)

**ForecastBench (Forecasting Research Institute; live benchmark vs human superforecasters)**
- 16 July 2026: AI models have "likely reached parity" with superforecasters (top human forecasters). Top system Cassi AI is not distinguishable from superforecasters (a test of "equal accuracy" gives p = 0.41, meaning no real difference shown). Source: [FRI, 16 Jul 2026](https://forecastingresearch.substack.com/p/ai-models-have-likely-reached-parity)
- On ForecastBench's market questions, Cassi ranked above the superforecaster median for the first time. This compares AI to humans, not to the market price itself. Source: [FRI, 16 Jul 2026](https://forecastingresearch.substack.com/p/ai-models-have-likely-reached-parity)
- Caveat from FRI: superforecaster forecasts were last collected in 2024, so the comparison relies on an extrapolation that "grows less reliable over time." The ranges the true numbers are probably in (95% CIs) "overlap substantially." Source: [FRI, 16 Jul 2026](https://forecastingresearch.substack.com/p/ai-models-have-likely-reached-parity)
- Earlier (29 Jan 2026), superforecasters still led the best AI by 0.017 Brier points. FRI then projected parity in November 2026. Source: [FRI, earlier post (via search summary)](https://forecastingresearch.substack.com/p/llms-are-closing-the-gap-on-human)
- FRI rematch with fresh superforecaster forecasts started October 2026. No results yet. Source: [FRI on X](https://x.com/Research_FRI/status/2102411966103093386)

**AIA Forecaster (Bridgewater AIA Labs; arXiv Nov 2025)**
- Matches superforecasters on ForecastBench. On a harder benchmark built from liquid prediction markets, it "underperforms market consensus." Source: [arXiv 2511.07678](https://arxiv.org/abs/2511.07678)
- Live test, 15-26 Aug 2025 (over a year old): Brier 0.1002 on 64 markets. The authors say 64 markets is too few to tell it apart from the market. Source: [LessWrong, "AI Forecasting in 2026: What 11 Analyses Say"](https://www.lesswrong.com/posts/a82q6yd8zKpYk56cF/ai-forecasting-in-2026-what-11-analyses-say)

**KalshiBench (arXiv, 17 Dec 2025)**
- 300 Kalshi questions resolving after the models' training data ended. Five models tested (Claude Opus 4.5, GPT-5.2, DeepSeek-V3.2, Qwen3-235B, Kimi-K2). Source: [arXiv 2512.16030](https://arxiv.org/abs/2512.16030)
- Every model was overconfident. Best calibration: Claude Opus 4.5, ECE 0.120 (stated confidence off by 12 points on average). GPT-5.2-XHigh, with more reasoning, was much worse: ECE 0.395. Source: [arXiv 2512.16030](https://arxiv.org/abs/2512.16030)
- Only one model beat simply guessing the base rate (a positive "Brier skill score"). This compares to base rates, not to market prices. Source: [arXiv 2512.16030](https://arxiv.org/abs/2512.16030)

**Metaculus FutureEval bot tournaments (bots vs 10 Metaculus Pro forecasters)**
- Spring 2026 (Jan 7 to Apr 15): the top-10 bot team trailed the Pros by 1.25 points per question. The range the true gap is probably in (95% CI) is -4.87 to +2.37, so the gap could be zero. One-sided p = 0.247 (not beyond luck). 173 bots, 297 scored questions; Pros forecast 99 of them. Source: [LessWrong, FutureEval Spring results](https://www.lesswrong.com/posts/wZBbDqzfBjYG58CxK/futureeval-spring-results-pros-beat-bots-but-the-gap-is)
- Trend in the bot-minus-Pro score: -11.3 (Q3 2024), -8.9 (Q4 2024), -17.7 (Q1 2025), -20.0 (Q2 2025), -1.25 (Spring 2026). Pros have won every season so far. Source: [Metaculus on X](https://x.com/metaculus/status/2095608079991894293)
- 7 of the top 10 bot makers were hobbyists. Source: [LessWrong, FutureEval Spring results](https://www.lesswrong.com/posts/wZBbDqzfBjYG58CxK/futureeval-spring-results-pros-beat-bots-but-the-gap-is)
- These compare bots to humans, not to market prices.

**PolyBench (arXiv, 3 Apr 2026; Polymarket, simulated)**
- 38,666 Polymarket markets, 4,997 events, snapshots from one week (6-12 Feb 2026). Seven models. Simulated fills walk the order book from the best ask. Source: [arXiv 2604.14199](https://arxiv.org/html/2604.14199)
- Only 2 of 7 models made money: MiMo-V2-Flash +17.6% and Gemini-3-Flash +6.2% (on the paper's confidence-weighted return). The other five lost 9% to 25%. Sharpe ratios (return per unit of ups and downs) were all near zero (-0.22 to +0.02). Source: [arXiv 2604.14199](https://arxiv.org/html/2604.14199)
- Fees are not mentioned. Returns collapse at bigger lot sizes (up to $1,000). No comparison to the market price is given; the paper does not use Brier. Source: [arXiv 2604.14199](https://arxiv.org/html/2604.14199)

**Other 2026 papers**
- "Beyond Forecasting" (3 Jul 2026) says recent benchmarks show "a large gap" between good probability scores and actual trading results. Its Raven-Agent was the only tested policy with a positive return in a replay. Numbers are not on the abstract page. Source: [arXiv 2607.03015](https://arxiv.org/abs/2607.03015)
- Hindcast (15 Jul 2026) replays resolved Polymarket markets with leak-proof retrieval (only Reddit posts from before the forecast date). Retrieval helps most models "only where Reddit discussed the event beforehand." No numbers on the abstract page. Source: [arXiv 2607.14051](https://arxiv.org/abs/2607.14051)

### Inferences
- The AI edge over Kalshi prices is real on Prophet Arena's leaderboard, but small. About 1 to 1.5 points on a 0-100 scale, or about 0.002 Brier.
- Small accuracy edges do not reliably become profit. Two above-market models lost money in Prophet Arena's own simulation. GPT-5.2 made money while being less accurate than the market. This points to luck and bet selection mattering as much as accuracy.
- Full Kelly betting on an AI's own probability is ruinous. Four of five models went to -99.9%. This matters for a Kelly-based project: the AI's probabilities are too overconfident (see KalshiBench) to size bets on directly.
- Kalshi's fee is biggest near 50c (1.75c a contract, or 3.5% of the money bet). AI forecasting is most useful in uncertain, mid-priced markets. That is exactly where the fee bites hardest. An edge of 0.002 Brier is unlikely to clear 3.5% of stake plus the spread.
- None of this applies to 15-minute crypto markets. An LLM call takes seconds, and those markets move on spot price, not on reasoning about news.

### Gaps
- No benchmark states clearly that its returns are after Kalshi fees and after buying at the ask.
- Prophet Arena's leaderboard gives no error range for the market row, so "beats the market" is not tested for luck.
- The ForecastBench market-question result compares AI to humans, not to the market price. FRI's projected date for AI matching markets (said to be August 2026 in a secondary source) is unconfirmed.
- AIA Forecaster's market-consensus Brier was not found, only its own 0.1002.

## Q2. Real AI trading agents on Kalshi or Polymarket: documented money results

### Takeaway
There are only two documented real-money tests. One small Kalshi test made +80% on $200 in 26 days. One larger Kalshi test lost 16% to 31% per model on $10,000 each over 57 days. Everything else is vendor talk or paper trading. No test shows lasting profit after fees at any size.

### Cited findings

**Prophet Arena live test (real money, Kalshi, April/May 2026)**
- Gemini 3 with the Brier-based sizing rule. 26 trading days. Started with $200.00, ended at $360.67: +80.33%. Sharpe 3.35 (return per unit of ups and downs, annualised; a very high value). Source: [arXiv 2607.06166](https://arxiv.org/html/2607.06166v1)
- 1,605 forecasts, 396 trade signals, 236 filled. 129 markets. 2,657 contracts. Fees paid $26.31. Win rate 50.9%. Source: [arXiv 2607.06166](https://arxiv.org/html/2607.06166v1)
- Orders were limit orders placed at the ask (paying the spread). A market was skipped unless its price had moved at least 10c, "to limit exposure to trading fees." Source: [arXiv 2607.06166](https://arxiv.org/html/2607.06166v1)
- Markets were filtered to drop unclear resolution rules. Examples: weekly executive-order count, Strategic Petroleum Reserve level, Kirk Cousins's next team, Dallas rainfall. Source: [arXiv 2607.06166](https://arxiv.org/html/2607.06166v1)
- One author works at Kalshi Research. No conflict-of-interest note was found in the parts read. Source: [arXiv 2607.06166](https://arxiv.org/html/2607.06166v1)

**Prediction Arena (Arcada Labs + Harvard authors; arXiv, 28 Mar 2026)**
- Six models, $10,000 real money each, on Kalshi from 12 Jan to 9 Mar 2026 (57 days). 2,916 trades in total. Source: [arXiv 2604.07355](https://arxiv.org/html/2604.07355v1)
- Every model lost money on Kalshi:

| Model | Kalshi return, 57 days | Kalshi win rate (share of settled bets won) |
|---|---|---|
| glm-4.7 | -16.0% | 30.9% |
| grok-4-20-checkpoint | -20.0% | 51.9% |
| gpt-5.2 | -20.5% | 48.0% |
| claude-opus-4-5 | -25.9% | 41.0% |
| gemini-3-pro-preview | -30.5% | 28.8% |
| grok-4-1-fast-reasoning | -30.8% | 15.4% |

Source: [arXiv 2604.07355](https://arxiv.org/html/2604.07355v1)
- Weather markets made up 71% to 97% of each model's settled positions on Kalshi. Source: [arXiv 2604.07355](https://arxiv.org/html/2604.07355v1)
- Over the same window (9 Feb to 9 Mar), the average was -22.6% on Kalshi and -1.1% on Polymarket. The authors cannot tell if Polymarket did better from better market choice or better prices. Source: [arXiv 2604.07355](https://arxiv.org/html/2604.07355v1)
- The paper says fees were counted in the agents' trade checks. It does not clearly say whether reported returns are after fees. Source: [arXiv 2604.07355](https://arxiv.org/html/2604.07355v1)
- A later 3-day paper-money group (GPT-5.4, Claude Opus 4.6, GLM-5, Gemini 3.1) ranged from -4.09% to +1.22% on Kalshi. Too short to mean anything. Source: [arXiv 2604.07355](https://arxiv.org/html/2604.07355v1)

**Vendor and press claims (weak evidence)**
- Olas "Polystrat" agent on Polymarket (from Feb 2026): over 4,200 trades in a month and "returns as high as 376%" on single trades. That is a best single trade, before fees, not total profit. The article is built around an Olas co-founder's comments. Olas sells an AI agent platform. Source: [CoinDesk, 15 Mar 2026](https://www.coindesk.com/tech/2026/03/15/ai-agents-are-quietly-rewriting-prediction-market-trading)
- TurbineFi's blog claims 37% of Polystrat wallets ended positive, versus 7-13% for humans, and that AI runs 30%+ of Polymarket wallets. These are unsourced. TurbineFi is a vendor. Source: [TurbineFi blog](https://www.turbinefi.com/blog/how-to-compete-with-ai-agents-prediction-markets-2026)
- Polymarket now charges taker fees that peak near 50%: crypto 1.80%, economics 1.50%, finance and politics 1.00%, sports 0.75%; geopolitics is free (after the 30 Mar 2026 rollout). Older Polymarket agent results came before these fees. Source: [Pine Analytics](https://pineanalytics.substack.com/p/polymarket-fee-rollout)

### Inferences
- The +80% result is $160 of profit from 236 fills. One month and one model is far too small to tell skill from luck. A Kalshi employee co-wrote it.
- Fees in that live test were $26.31, which is 13% of the starting $200. Fees are a big share of results at this trade rate. (The ending balance is likely after fees, since it is an account value, but the paper excerpt does not say so.)
- The larger $60,000 Kalshi test lost money with every model. Most of its bets were weather markets. This fits the project's own finding that the daily-high weather favourite rule failed.
- Strong evidence for real AI trading profit on Kalshi after fees does not exist yet.

### Gaps
- No audited or on-chain-checked net profit for any commercial AI agent (Polystrat or others) was found.
- Prediction Arena gives no Brier scores, so it cannot say if losses came from bad forecasts or bad trading.
- No real-money AI agent result over more than 2 months was found.

## Q3. News and sentiment signals: do they lead prediction-market prices, and can a small trader act in time?

### Takeaway
No rigorous study shows that news or social-media sentiment predicts Kalshi or Polymarket price moves before the market adjusts. The best evidence says a small skilled group already trades fast on public news. A news-reading LLM bot also brings a new risk: planted articles can swing its forecasts.

### Cited findings
- A study of Polymarket's full trade record finds about 3% of accounts show lasting skill (judged against coin-flip simulations). These skilled traders "trade quickly on public news, such as an earnings announcement." They also buy underpriced favourites, sell overpriced longshots, and take pricing gaps. Sources: [SSRN blog on Gómez-Cram, Guo, Jensen and Kung, 29 Jun 2026](https://blog.ssrn.com/2026/06/29/a-closer-look-prediction-market-accuracy-crowd-wisdom-or-informed-minority-by-roberto-gomez-cram-yunhan-guo/); paper: [SSRN 6617059](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6617059)
- Kalshi says prices update "often within seconds" of breaking news. It gives no timing data. Kalshi is not a neutral source. Source: [Kalshi blog](https://news.kalshi.com/p/how-breaking-news-shifts-prediction-markets)
- Brazil's 2026 runoff: news coverage says prices moved 30-40 minutes ahead of the visible vote count. About $30,000 of selling would have cut 5 points from Bolsonaro's Polymarket price (a thin book). Before the vote, markets were wrong: Polymarket had Bolsonaro at 80.2%, Kalshi at 77.5%, and Lula won. These are press reports, not studies. Sources: [iTechGuides](https://itechguides.com/why-prediction-markets-got-the-brazilian-election-so-wrong); [Finance Magnates](https://www.financemagnates.com/trending/brazils-election-upset-tests-prediction-markets-pitch-to-brokers/)
- An open-source news bot for Kalshi and Polymarket (paper trading by default) measured headline-to-paper-fill time of 340-440 ms. On 5 stories, its RSS news feeds saw the story a median 32 minutes after the first X post (range -5 to +109 minutes). About 3 hours of live paper trading gave zero fills. A 20-trade shadow sample had no winners. The author sells nothing visible. One setup, tiny sample. Source: [GitHub: mehek-builds/prediction-market](https://github.com/mehek-builds/prediction-market)
- PolyBench fed seven LLMs a real-time news stream plus the order book. Only 2 of 7 made money in simulation, with fees not counted and near-zero Sharpe. Source: [arXiv 2604.14199](https://arxiv.org/html/2604.14199)
- "The Corroboration Illusion" (5 Sep 2026): one planted LLM-written article per question flipped 56% of forecasts across 50%. Five articles flipped 69-73% and moved forecasts by 13 to 22 points. Brier got worse, from 0.18 to 0.37. Every tested defence had a cheap way around it. Tested on 500 ForecastBench questions with open 7-8B models. Source: [arXiv 2609.22246](https://arxiv.org/abs/2609.22246)
- Hindcast: retrieval only helped where Reddit discussed the event beforehand. Source: [arXiv 2607.14051](https://arxiv.org/abs/2607.14051)
- No study was found that tests news or Twitter sentiment as a lead signal for Kalshi or Polymarket prices. The stock-market sentiment literature is mixed. Source: [search summary; see e.g. arXiv 1610.09225](https://arxiv.org/pdf/1610.09225)

### Inferences
- Speed matters more than reading. Wire and "squawk" accounts on X break news first. RSS is minutes late. A small bot reading RSS is likely trading on news the skilled 3% already priced.
- An LLM call adds seconds. Prices reportedly move within seconds. So an LLM news bot is a slow taker that pays the spread and the fee, the classic victim of adverse selection (getting picked off by someone who knows more).
- The poisoning result means a news-reading bot can be steered by anyone who publishes articles. That is a real risk with real money.

### Gaps
- No timestamped event study of Kalshi price moves around news releases was found. This would need tick data from Kalshi's API.
- No real-money results for any news or sentiment bot were found.

## Q4. Order-flow signals (order-book imbalance, trade size, one-sided runs) as a signal

### Takeaway
Order flow does carry information. One-sided flow predicts losses for market makers in Kalshi single-name markets. Large-trade imbalance predicted next returns across 2024 election venues. Skilled-account flow predicts outcomes on Polymarket, but that needs wallet identities that Kalshi does not show. No study reports a profitable order-flow strategy for an outside taker after fees.

### Cited findings

**Kalshi**
- Bartlett and O'Hara, "Adverse Selection in Prediction Markets: Evidence from Kalshi" (April 2026 working paper). Uses 41.6 million Kalshi trades. Sources: [SSRN 6615739](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6615739); [Stanford Law listing, 21 Apr 2026](https://law.stanford.edu/publications/adverse-selection-in-prediction-markets-evidence-from-kalshi/)
- Single-name markets show more informed price impact (prices move more after informed trades) than broad-based markets. Yet spreads there are only a little wider, and market makers earn about twice as much per contract. Source: [Stanford Law listing](https://law.stanford.edu/publications/adverse-selection-in-prediction-markets-evidence-from-kalshi/)
- Their explanation: traders "systematically overbet YES in markets that predominantly settle NO." This behavioural surplus pays for the adverse selection. Source: [Stanford Law listing](https://law.stanford.edu/publications/adverse-selection-in-prediction-markets-evidence-from-kalshi/)
- Using VPIN (a measure of how one-sided recent order flow is), one-sided flow predicts maker losses in single-name markets, but not in broad-based ones. Source: [Stanford Law listing](https://law.stanford.edu/publications/adverse-selection-in-prediction-markets-evidence-from-kalshi/)
- The Stanford page lists only Bartlett as author; SSRN lists Bartlett and O'Hara. Only the abstract was readable. No cent figures were found. Sources: [Stanford Law listing](https://law.stanford.edu/publications/adverse-selection-in-prediction-markets-evidence-from-kalshi/); [SSRN 6615739](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6615739)

**Cross-venue (2024 US election)**
- Ng and co-authors: Polymarket led Kalshi in price discovery (Polymarket prices predicted later Kalshi prices, not the reverse). The venue with more one-way flow from large trades tends to lead. "Net order imbalance from large trades strongly predicts subsequent returns." Source: [SSRN 5331995, revised Apr 2026 (via search summary)](https://papers.ssrn.com/abstract=5331995)
- Aktuğ and Torul (Apr 2026), nine political betting venues: Polymarket and Betfair together hold nearly 85% of the information share (who moves first). Polymarket leads at 5-minute steps, Betfair at 1-hour steps. Kalshi gained a non-trivial share within weeks of its October 2024 launch. Source: [Aktuğ and Torul (via search summary)](https://web.bogazici.edu.tr/torul/pridis.pdf)

**Polymarket**
- Gómez-Cram et al. (SSRN, Apr-Jun 2026): about 3.14% of accounts are "skilled winners." A third-party reproduction reports the paper's skilled order-imbalance results: next-period price change coefficient 2.05 (far too big to be luck, t = 12.8) and final outcome 7.77 (t = 9.6). The reproduction itself got smaller numbers: 1.13 (t = 11.7) and 4.04 (t = 11.8). Sources: [GitHub reproduction](https://github.com/JasonJSant/polymarket-skilled-traders); [SSRN 6617059](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6617059)
- A search summary of a related study (1.72 million accounts, 210,322 markets, 2023-2025) says flagged "insider" order imbalance predicts next price changes (about 2.5 times its noise, t = 2.54; just past the usual bar of 2) and final outcomes (t = 8.65). It also says market-maker flow predicts short-term moves but points the wrong way on final outcomes. Not opened; may be a different version of the same work. Sources: [OSC research grant paper (not opened, 403)](https://www.osc.ca/sites/default/files/2026-10/research-grant-competition-2026-who-wins-and-who-loses-in-prediction-markets.pdf); [KuCoin news summary](https://www.kucoin.com/news/flash/polymarket-study-reveals-only-3-14-of-1-72m-addresses-are-true-winners)
- A methods paper says the skill test cannot spot an insider from a single informed trade, and that pooling politics, sports and crypto makes a platform-wide "skilled" label unclear. Source: [arXiv 2605.02287](https://arxiv.org/abs/2605.02287)
- Large orders: quote changes grow with order size relative to displayed depth, over a 28-day sample. The link weakens a lot when episodes are strictly separated. Source: [ResearchGate, "Large Orders, Liquidity, and Price Adjustment in Prediction Markets" (via search summary)](https://www.researchgate.net/publication/414989876_Large_Orders_Liquidity_and_Price_Adjustment_in_Prediction_Markets)
- Data warning: guessing trade direction from Polymarket data has systematic errors. This badly distorts measures like VPIN and estimates of informed trading. Source: [Polymarket-v1 Database, arXiv 2606.04217 (via search summary)](https://arxiv.org/html/2606.04217v1)

**Short crypto contracts (relevant to the bot's market type)**
- Dai, Jia and Yu (June 2026): in five-minute Bitcoin contracts, spot-market order flow spikes at settlement time, then prices reverse sharply after settlement. This manipulation is "largely absent" in fifteen-minute contracts. Venue not confirmed from the snippet. Source: [arXiv 2606.31675 (via search summary)](https://arxiv.org/pdf/2606.31675)

**Adjacent, not prediction markets**
- Zhai (Aug 2026): on an unnamed exchange that shows a wallet ID on every order (17.1 billion messages, $84.3 billion taker volume), top wallets keep their rank across 10-day windows (rank correlation 0.52). Adding their live activity lifts one-second return prediction to 12.31% of variance explained, on data the model never saw while being built. That is far beyond luck (t = 9.2). No after-cost profit is reported. Source: [arXiv 2608.04373](https://arxiv.org/abs/2608.04373)
- Betfair: a Charles University thesis found most order-book features were not statistically significant predictors of fair price. Thesis, not peer-reviewed. Source: [Charles University repository (via search summary)](https://dspace.cuni.cz/handle/20.500.11956/175670)

### Inferences
- On Kalshi, accounts are anonymous. The Polymarket "follow the skilled wallet" signal cannot be built there. What a Kalshi bot can see is anonymous flow: one-sidedness, trade size and book imbalance.
- Bartlett and O'Hara's result is mainly a warning for market makers. It does not show that a taker following one-sided flow profits after the 7% x p x (1 - p) fee.
- The finding that YES is overbet in markets that mostly settle NO fits the project's favourite-longshot work. It is the same behavioural surplus seen from the maker's side.
- The settlement-manipulation result is a reason to stay on 15-minute crypto contracts rather than 5-minute ones.

### Gaps
- No published Kalshi study tests order-book imbalance or trade size as a short-term price predictor at the speed a bot would trade.
- No study gives an after-fee, out-of-sample profit (tested on data the rule never saw while being built) for an order-flow taker strategy on any prediction market.
- Exact effect sizes in Bartlett and O'Hara and in Ng et al. were not readable (paywall or 403).

## Q5. Ensembles: combining AI, markets, sportsbooks or polls into a better forecast and trading the odd venue out

### Takeaway
Blending an AI forecast with the market price beats the market alone in a few studies, by small Brier margins. Price leadership across venues is measured, with Polymarket leading Kalshi in 2024. No study reports measured trading profit from an ensemble strategy after fees.

### Cited findings
- AIA Forecaster blended with the market price. On the liquid-market set: blend Brier 0.106, market 0.111, AI alone 0.126 (blend best). On ForecastBench market questions: blend 0.079 versus AI alone 0.075 (blend slightly worse). The authors aimed for readable weights, not the best possible blend. Sources: [arXiv 2511.07678 (via search summary)](https://arxiv.org/pdf/2511.07678); abstract confirms the blend "outperforms consensus alone": [arXiv 2511.07678](https://arxiv.org/abs/2511.07678)
- Mention markets (will a word be said on an earnings call): market price mixed with an LLM update scored Brier 0.1392 versus 0.1441 for the market alone. The gain is largest for mid-range prices. Source: [arXiv 2602.21229 (via search summary)](https://arxiv.org/html/2602.21229v2)
- Merger completion forecasting: best model Brier 0.151 versus 0.199 for market-implied odds. Not a prediction market; market odds come from stock prices. Source: [arXiv 2607.09921 (via search summary)](https://arxiv.org/pdf/2607.09921)
- Price leadership: Polymarket led Kalshi in 2024; Polymarket and Betfair held about 85% of the information share across nine venues. Sources: [SSRN 5331995 (via search summary)](https://papers.ssrn.com/abstract=5331995); [Aktuğ and Torul (via search summary)](https://web.bogazici.edu.tr/torul/pridis.pdf)
- Metaculus bot makers: comparing one's bot to the Metaculus crowd forecast was weakly linked with worse scores (r = -0.32, p = 0.08, not beyond luck). Prompts tuned to match the crowd did worse live (+2.76 vs +4.71 per question, over about 350 questions). Source: [LessWrong, "AI Forecasting in 2026: What 11 Analyses Say"](https://www.lesswrong.com/posts/a82q6yd8zKpYk56cF/ai-forecasting-in-2026-what-11-analyses-say)

### Inferences
- The blend gains are about 0.005 Brier. That is small next to Kalshi's fee at mid prices (3.5% of the money bet at 50c).
- Trading the "outlier venue" is cross-venue arbitrage, which is already covered. The new piece is direction: in 2024, Kalshi tended to follow Polymarket, not lead it.
- The mid-price gain in the mention-market study points to the same problem as Q1: AI helps most where fees are highest.

### Gaps
- No study of combining Kalshi, Polymarket, sportsbooks and polls into one forecast and trading the outlier with measured after-fee profit was found.
- AIA's blend numbers come from a search summary of the PDF, not a direct read. Sample sizes for those sets were not found.
