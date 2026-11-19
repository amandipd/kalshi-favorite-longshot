# Kelly and fractional Kelly for small-edge, high-probability binary bets (92-99.9¢ contracts paying $1)

Notation used throughout: buy one contract at price **p**, it pays $1 if it wins. **q** is the true win probability. Edge = q − p. **f** is the share of the bankroll spent on contracts (the stake, which is fully lost on a loss). **c** is the fraction of Kelly (c = 0.5 is "half Kelly"). **G(f)** is the expected log growth per bet (the compounding rate: how fast the bankroll grows on a log scale):

G(f) = q·ln(1 + f·(1−p)/p) + (1−q)·ln(1 − f)

Numbers marked "computed" come from the project's own scripts (exact formulas above plus a 20,000-path Monte Carlo, numpy seed 12345): [`scripts/kelly_calc.py`](scripts/kelly_calc.py) and [`scripts/kelly_rck_corr.py`](scripts/kelly_rck_corr.py), next to this note. They are not cited literature, so their results are listed under Inferences.

## 1. Kelly for this bet: f* = (q − p)/(1 − p), and how sensitive it is as p → 1

### Takeaway
For a $1-payout contract bought at p, the Kelly stake is f* = (q−p)/(1−p), which equals **1 − (your loss probability ÷ the price-implied loss probability)**. A fixed 1-point edge therefore asks for a bigger stake the closer the price is to $1: 12.5% of bankroll at 92¢, 20% at 95¢, 50% at 98¢. The slope df*/dq = 1/(1−p) means a 1-point error in q moves the stake by 12.5, 20 or 50 points of bankroll at those prices.

### Cited findings
- General two-outcome Kelly: f* = (bp − q)/b for net odds b, win probability p and loss probability q (Thorp's notation). It is the fraction that maximises the expected log of wealth. Source: [Thorp 2006, "The Kelly Criterion in Blackjack, Sports Betting and the Stock Market", Handbook of Asset and Liability Management vol. 1, ch. 9, §2](https://wayback.archive-it.org/5456/20240920155724/https://www.eecs.harvard.edu/cs286r/courses/fall12/papers/Thorpe_KellyCriterion2007.pdf) (written 1997-98, published 2006)
- For an "all-or-nothing" prediction-market contract bought at price p, with subjective probability q and no borrowing, the log-utility optimum is f = (q − p)/(1 − p). Source: [Meister 2024, "Application of the Kelly Criterion to Prediction Markets", arXiv:2412.14144](https://arxiv.org/abs/2412.14144) (Dec 2024)
- In the one-asset two-valued payoff case, the Kelly wager is "the edge (expected return) divided by the odds". Source: [MacLean, Thorp & Ziemba 2010, "Good and bad properties of the Kelly criterion"](https://www.stat.berkeley.edu/~aldous/157/Papers/Good_Bad_Kelly.pdf) (Jan 2010; published in Quantitative Finance 10(7), 2010 and in The Kelly Capital Growth Investment Criterion, World Scientific, 2011)
- Listed "Bad property" of Kelly: "The bets may be a large fraction of current wealth when the wager is favorable and the risk of loss is very small." Their example is a 64% Kelly wager on a 3-5 favourite (Slew of Gold, 1984 Breeders' Cup), which Thorp and Ziemba actually bet "with a low fractional Kelly wager". Source: [MacLean, Thorp & Ziemba 2010](https://www.stat.berkeley.edu/~aldous/157/Papers/Good_Bad_Kelly.pdf)
- Near the optimum, the growth rate is flat: mis-sizing the fraction costs growth quadratically, while misjudging the probability costs linearly. Meister derives this with Kullback-Leibler divergence for biased coins: U(p, 2p−1+ε) − U(p, 2p−1) ≈ −ε²/(4p(1−p)). Source: [Meister 2024](https://arxiv.org/abs/2412.14144)

### Inferences
- **Derivation.** Net odds b = (1−p)/p. Then f* = q − (1−q)/b = (q − p)/(1 − p) = 1 − (1−q)/(1−p). The last form says the Kelly stake depends only on the **ratio of your loss rate to the market's implied loss rate**. Fees can be folded in by replacing p with the all-in cost per contract p′ = p + fee, giving f* = (q − p′)/(1 − p′).
- **Worked examples (computed):**

| p | q | edge | f* (Kelly stake) | loss-rate ratio (1−q)/(1−p) | G* per bet (log) | half-Kelly growth ÷ G* | quarter-Kelly growth ÷ G* | stake where growth hits 0, ÷ f* |
|---|---|---|---|---|---|---|---|---|
| 0.92 | 0.930 | 1.0 pt | **0.125** | 0.875 | 0.071% | 0.740 | 0.426 | 1.92× |
| 0.92 | 0.935 | 1.5 pt | **0.1875** | 0.812 | 0.163% | 0.734 | 0.420 | 1.88× |
| 0.95 | 0.960 | 1.0 pt | **0.20** | 0.800 | 0.113% | 0.732 | 0.418 | 1.86× |
| 0.95 | 0.965 | 1.5 pt | **0.30** | 0.700 | 0.263% | 0.721 | 0.407 | 1.78× |
| 0.98 | 0.990 | 1.0 pt | **0.50** | 0.500 | 0.312% | 0.693 | 0.381 | 1.60× |
| 0.98 | 0.995 | 1.5 pt | **0.75** | 0.250 | 0.818% | 0.640 | 0.338 | 1.31× |

- **Sensitivity (computed):** df*/dq = 1/(1−p). A 1-point error in q shifts f* by 12.5 points of bankroll at p = 0.92, 20 at 0.95, 50 at 0.98, 100 at 0.99, 200 at 0.995 and 1,000 at 0.999. Above p = 0.99, "edge = p + 1 point" is impossible because q would exceed 1. At the top of the 92-99.9¢ band, the edge has to be thought of as a loss-rate ratio, not as percentage points.
- These contracts break the usual continuous-time rules of thumb. The bet is strongly skewed: win small often, lose the whole stake rarely. Half Kelly keeps 64-74% of the maximum growth, not the 75% the continuous formula gives. Growth turns negative at **1.3-1.9× Kelly, not 2×**, and the gap widens as p and the edge rise.
- Absolute growth per bet is tiny: 0.07-0.8% log growth per bet even at full Kelly. Compounding comes from many bets, so the number of bets per day matters as much as the stake.

### Gaps
- Meister's paper derives the formula but gives no empirical sizing evidence for prediction markets.
- Kalshi's fee schedule was not collected here. The fee-adjusted formula above is a derivation, not a sourced value.

## 2. Fractional Kelly: growth vs drawdown (Thorp; MacLean-Ziemba-Blazenko; Busseti-Ryu-Boyd)

### Takeaway
In the continuous approximation, betting c × Kelly gives growth c(2−c) times the maximum. The probability of *ever* falling to fraction x of the starting bankroll is x^(2/c − 1). The chance of ever losing half is 1/2 at full Kelly, 1/8 at half Kelly and 1/128 at quarter Kelly, at a cost of 25% and 56% of growth. Busseti-Ryu-Boyd turn a drawdown limit into a convex constraint. For a two-outcome bet the answer is itself a fractional Kelly bet: "≤10% chance of ever losing half" works out to about 0.47-0.52× Kelly for these contracts (computed).

### Cited findings
- **Drawdown formula (Thorp eq. 7.13):** Prob(V(t, c·f*)/V0 ≤ x for some t) = x^(2/c − 1). Full Kelly: Prob = x. Half Kelly: x³. "The chance of ever losing half the starting capital is 1/2 for f = f* but only 1/8 for f = f*/2." Source: [Thorp 2006, §7.4](https://wayback.archive-it.org/5456/20240920155724/https://www.eecs.harvard.edu/cs286r/courses/fall12/papers/Thorpe_KellyCriterion2007.pdf)
- **Reach-before formula (Thorp eq. 7.11):** Prob(V reaches yV0 before xV0) = (1 − x^(2/c−1)) / (1 − (x/y)^(2/c−1)), for 0 < c < 2. Doubling before halving has probability 2/3 at full Kelly and 8/9 at half Kelly, and half Kelly has growth g(f*/2) = 0.75·g(f*). Source: [Thorp 2006, §7.4](https://wayback.archive-it.org/5456/20240920155724/https://www.eecs.harvard.edu/cs286r/courses/fall12/papers/Thorpe_KellyCriterion2007.pdf)
- Thorp: "most people strongly prefer the increased safety and psychological comfort of 'half Kelly' (or some nearby value), in exchange for giving up 1/4 of their growth rate." Also: "most cautious gamblers or investors who use Kelly find the frequency of substantial bankroll reduction to be uncomfortably large… they tend to prefer somewhat less than the full betting fraction… This also offers a margin of safety in case the betting situations are less favorable than believed." Source: [Thorp 2006, §3.2 and §7.4](https://wayback.archive-it.org/5456/20240920155724/https://www.eecs.harvard.edu/cs286r/courses/fall12/papers/Thorpe_KellyCriterion2007.pdf)
- **MacLean & Ziemba table** (blackjack, 2% edge, p = 0.51), via MacLean-Thorp-Ziemba. The table is consistent with the formulas above.

| Kelly fraction | 0.1 | 0.2 | 0.3 | 0.4 | 0.5 | 0.6 | 0.7 | 0.8 | 0.9 | 1.0 | 1.5 | 2.0 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P(double before halving) | .999 | .998 | .98 | .94 | .89 | .83 | .78 | .74 | .70 | .67 | .56 | .50 |
| Relative growth | .19 | .36 | .51 | .64 | .75 | .84 | .91 | .96 | .99 | 1.00 | .75 | 0.00 |

  Source: [MacLean, Thorp & Ziemba 2010, citing MacLean & Ziemba 1999](https://www.stat.berkeley.edu/~aldous/157/Papers/Good_Bad_Kelly.pdf)
- **Fractional Kelly = more risk-averse utility:** for lognormal assets, putting fraction f = 1/(1−α) in the Kelly portfolio and the rest in cash is optimal for negative power utility w^α/α (α < 0). "Half Kelly is α = −1 and quarter Kelly is α = −3." This is exact for lognormal returns and "approximately correct for other distributed assets". Source: [MacLean, Thorp & Ziemba 2010](https://www.stat.berkeley.edu/~aldous/157/Papers/Good_Bad_Kelly.pdf)
- Fractional Kelly as the growth-security trade-off originates in MacLean, Ziemba & Blazenko (1992), "Growth versus security in dynamic investment analysis", Management Science 38, 1562-85. MacLean-Sanegre-Zhao-Ziemba (2004) show how to choose the fraction so wealth stays above a growth path or drawdown limit with a given probability. Cited in [MacLean, Thorp & Ziemba 2010](https://www.stat.berkeley.edu/~aldous/157/Papers/Good_Bad_Kelly.pdf) (MZB 1992 not read directly)
- Fractional Kelly does not guarantee good short-run outcomes. In one example, 700 wagers each with a 14% edge (the least likely winner at 19%) can turn $1,000 into $18 at full Kelly, while 16.6% of the time it grows past $100,000. "Half Kelly does not help much as $1000 can become $145", and only 0.1% of half-Kelly runs pass $100,000. Source: [MacLean, Thorp & Ziemba 2010, citing Ziemba & Hausch](https://www.stat.berkeley.edu/~aldous/157/Papers/Good_Bad_Kelly.pdf)
- **Risk-constrained Kelly (RCK):** maximise E log(rᵀb) subject to E[(rᵀb)^(−λ)] ≤ 1 with λ = log β / log α. This guarantees Prob(W_min < α) < β, where W_min is the lowest wealth ever reached (start = 1). "For the two outcome case… the RCK bet is a fractional Kelly bet… for some f < 1", found by bisection on q(b₁P + 1 − b₁)^(−λ) + (1−q)(1−b₁)^(−λ) = 1. Sources: [Busseti, Ryu & Boyd 2016, "Risk-Constrained Kelly Gambling", arXiv:1603.06183](https://arxiv.org/abs/1603.06183); [PDF](https://web.stanford.edu/~boyd/papers/pdf/kelly.pdf) (arXiv preprint, March 2016)
- In their multi-outcome example (α = 0.7, β = 0.1, λ = 6.456), full Kelly had growth 0.062 and a 39.7% chance of a >30% drawdown. RCK had growth 0.043 with 7.3% risk, or 0.047 with 9.9% risk once λ was tuned. The fractional Kelly bet with the same 10% risk grew at about 0.035. With a continuous ("infinite outcome") return distribution, fractional Kelly performed "(essentially) the same" as RCK. The paper calls fractional Kelly an "ad hoc method". Source: [Busseti, Ryu & Boyd 2016](https://web.stanford.edu/~boyd/papers/pdf/kelly.pdf)
- Fractional Kelly cuts volatility linearly: the c-Kelly portfolio's volatility is c × the full-Kelly volatility. Source: [Rising & Wyner 2012, "Partial Kelly Portfolios and Shrinkage Estimators", IEEE ISIT 2012](https://faculty.wharton.upenn.edu/wp-content/uploads/2013/05/Wyner_2012_Partial_3.pdf)

### Inferences
- **Continuous-formula values:** relative growth c(2−c) is 1.00 / 0.75 / 0.4375 at c = 1 / ½ / ¼. P(ever ≤ 50% of start) = 0.5^(2/c−1) is 0.50 / 0.125 / 0.0078. P(double before halve) = (2^k − 1)/(2^k − 2^−k) with k = 2/c − 1 is 0.667 / 0.889 / 0.992.
- **Discrete Monte Carlo for these contracts (computed; q = p + 1 point; 20,000 paths).** "Ever ≤ 50% of start" is Thorp's measure. "50% peak-to-trough" means the bankroll halves from any running high, which is what a live account actually experiences.

| p | c | stake | P(ever ≤50% start), 1,000 bets | 5,000 bets | Thorp formula | P(50% peak-to-trough), 1,000 bets | 5,000 bets | median wealth after 1,000 bets |
|---|---|---|---|---|---|---|---|---|
| 0.92 | 1 | 12.5% | 0.35 | 0.46 | 0.50 | 0.88 | 1.00 | 2.0× |
| 0.92 | ½ | 6.25% | 0.060 | 0.10 | 0.125 | 0.19 | 0.75 | 1.7× |
| 0.92 | ¼ | 3.1% | 0.001 | 0.004 | 0.008 | 0.003 | 0.054 | 1.35× |
| 0.95 | 1 | 20% | 0.38 | 0.46 | 0.50 | 0.95 | 1.00 | 3.1× |
| 0.95 | ½ | 10% | 0.074 | 0.10 | 0.125 | 0.29 | 0.86 | 2.3× |
| 0.95 | ¼ | 5% | 0.002 | 0.005 | 0.008 | 0.007 | 0.077 | 1.6× |
| 0.98 | 1 | 50% | 0.37 | 0.39 | 0.50 | 1.00 | 1.00 | 22.6× |
| 0.98 | ½ | 25% | 0.063 | 0.061 | 0.125 | 0.46 | 0.96 | 8.7× |
| 0.98 | ¼ | 12.5% | 0.002 | 0.002 | 0.008 | 0.015 | 0.087 | 3.3× |

  - Thorp's formula is an upper bound over an infinite horizon for "ever losing half of the *starting* bankroll". The finite-horizon discrete numbers sit at or below it.
  - **Peak-to-trough halvings are near certain at full Kelly** and common at half Kelly over a few thousand bets. Only around quarter Kelly do they become rare (5-9% over 5,000 bets). Over an unlimited horizon any fixed fraction eventually has a 50% peak-to-trough drawdown, so the useful question is "how likely within the horizon that matters".
  - At p = 0.98, full Kelly stakes 50%, so a single loss halves the bankroll.
- **RCK applied to these contracts (computed):** the largest stake satisfying the Busseti-Ryu-Boyd bound, as a multiple of Kelly:

| p, q | P(ever lose 50%) < 10% | < 5% | P(ever lose 30%) < 10% | P(ever lose 20%) < 10% |
|---|---|---|---|---|
| 0.92, 0.930 | 0.47× | 0.39× | 0.28× | 0.18× |
| 0.95, 0.960 | 0.48× | 0.39× | 0.28× | 0.19× |
| 0.98, 0.990 | 0.52× | 0.43× | 0.32× | 0.21× |
| 0.98, 0.995 | 0.58× | 0.49× | 0.37× | 0.25× |

  These match Thorp's continuous formula: x^(2/c−1) = 0.1 at x = 0.5 gives c ≈ 0.46. In plain words, "half Kelly" is roughly a "10% chance of ever losing half" policy, and "quarter Kelly" is roughly a "10% chance of ever losing 25-30%" policy. Both statements assume the edge estimate is correct (see §3).

### Gaps
- MacLean, Ziemba & Blazenko (1992) could not be opened directly. Its content is cited second-hand through MacLean-Thorp-Ziemba (2010).
- No published drawdown table for discrete, strongly skewed 92-99¢ binary bets was found. The Monte Carlo above fills that gap but is the project's own computation.

## 3. Estimation error: uncertain edge, shrinkage Kelly, and the cost of overbetting

### Takeaway
Overestimating the edge is the dominant risk. Betting Kelly on an edge that is really half as big gives roughly zero growth, and anything beyond that loses. Benter says overestimating by 2× "is easily done in practice". The formal results (Baker-McHale 2013; Rising-Wyner 2012) say to shrink the bet by about edge² / (edge² + SE²), where SE is the standard error of the edge estimate. For a 1-point edge on 92-95¢ contracts estimated from 500-2,000 bets, that is about 0.4-0.85× Kelly. Model drift and backtest-to-live decay come on top of that, which is the case for half Kelly or less.

### Cited findings
- **Thorp on mis-estimated edge (§7.3, "The case for fractional Kelly"):** if you choose f = 0.5·f_e (half of the Kelly computed from your estimate m_e) and the true edge is m_t = 0.5·m_e, you lose nothing. "A disaster occurs when m_t = .5m_e but we choose f = 1.5f_e… Then g = −.75 and we will be ruined." Choosing f = f_e when m_t = 0.5·m_e gives g = 0, with "increasingly wild oscillations". His lessons: "To the extent m_e is an uncertain estimate of m_t, it is wise to assume m_t < m_e and to choose f < f_e by enough to prevent g ≤ 0", and "choosing f in the range 0.5f_e ≤ f < f_e offers protection against g ≤ 0 with a reduction of g that is likely to be no more than 25%". Source: [Thorp 2006, §7.3](https://wayback.archive-it.org/5456/20240920155724/https://www.eecs.harvard.edu/cs286r/courses/fall12/papers/Thorpe_KellyCriterion2007.pdf)
- Thorp: forecast excess returns "are more likely to be too high than too low. The tendency is to regress towards the mean." Even in blackjack, where odds can be computed, "m_t is likely to be at least somewhat less than m_e" because of fatigue, calculation errors, shuffling and similar effects. Source: [Thorp 2006, §7.3](https://wayback.archive-it.org/5456/20240920155724/https://www.eecs.harvard.edu/cs286r/courses/fall12/papers/Thorpe_KellyCriterion2007.pdf)
- Thorp's sports-betting trial deliberately used conservative expectation estimates "because… using too large an f* and overbetting is much more severely penalized than using too small an f* and underbetting." His conclusion: "to the extent that future probabilities are uncertain, long term compounders should further limit their investment fraction enough to prevent a significant risk of overbetting." Source: [Thorp 2006, §6 and §10](https://wayback.archive-it.org/5456/20240920155724/https://www.eecs.harvard.edu/cs286r/courses/fall12/papers/Thorpe_KellyCriterion2007.pdf)
- **2× Kelly:** in continuous time with geometric Brownian motion, "betting exactly double the Kelly criterion amount leads to a growth rate equal to the risk free rate" (attributed to Thorp 1997, Stutzer 1998, Janacek 1998). "It never pays to bet more than the Kelly strategy because then risk increases… and growth decreases." Source: [MacLean, Thorp & Ziemba 2010](https://www.stat.berkeley.edu/~aldous/157/Papers/Good_Bad_Kelly.pdf)
- **Errors in means dominate:** Chopra & Ziemba (1993) found errors in means, variances and covariances matter in roughly a 20 : 2 : 1 ratio, and the gap widens as risk aversion falls. Kelly (log utility) has low risk aversion, so it is especially exposed. "Given the extreme sensitivity of E log calculations to errors in mean estimates, these estimates must be accurate and to be on the safe side, the size of the wagers should be reduced." Source: [MacLean, Thorp & Ziemba 2010](https://www.stat.berkeley.edu/~aldous/157/Papers/Good_Bad_Kelly.pdf)
- **Baker & McHale (2013):** the Kelly criterion "ignores uncertainty in the probability of winning the bet and uses an estimated probability". To improve out-of-sample performance, the bet "should be shrunk in the presence of this parameter uncertainty". Shrunken bets beat raw Kelly in simulation and on tennis betting data. An approximate shrinkage factor gives a "back of envelope" correction. Sources: [Baker & McHale 2013, "Optimal Betting Under Parameter Uncertainty: Improving the Kelly Criterion", Decision Analysis 10(3):189-199](https://pubsonline.informs.org/doi/10.1287/deca.2013.0271); [IDEAS abstract](https://ideas.repec.org/a/inm/ordeca/v10y2013i3p189-199.html)
- Metel (2017) describes Baker & McHale as deriving "a shrinkage factor for two outcome gambling settings, which gives the optimal fraction of the Kelly amount to wager". Metel also notes that with estimated probabilities, "outcomes with overestimated values will consistently look more favourable than in reality, with larger wagers placed on them" (a selection bias). Source: [Metel 2017, "Kelly betting on horse races with uncertainty in probability estimates", arXiv:1701.02814](https://arxiv.org/abs/1701.02814)
- A secondary write-up gives the shrinkage coefficient as α = (p−q)² / ((p−q)² + σ²) = SR²/(SR² + 1), where SR is the Sharpe ratio (edge divided by its uncertainty), and says Baker & McHale model the posterior of p as a Beta distribution. Source: [SimonM 2021, "Never Go Full Kelly", LessWrong](https://www.lesswrong.com/posts/TNWnK9g2EeRnQA8Dg/never-go-full-kelly) (secondary; not checked against the paper)
- **Rising & Wyner (2012):** "the full Kelly portfolio formed from an estimator of the form r_f + (1−δ)μ̂ is identical to the (1−δ)-Kelly portfolio formed from μ̂" (Theorem V.1). The optimal shrinkage is δ* ≈ tr(Σ)/(n‖μ − r_f‖²) (Theorem V.2), so the optimal Kelly fraction is about 1 − (estimation variance ÷ edge²). They conclude "the fractional Kelly portfolio succeeds not because of reduced risk, but because of reduced estimation error." Source: [Rising & Wyner 2012](https://faculty.wharton.upenn.edu/wp-content/uploads/2013/05/Wyner_2012_Partial_3.pdf)
- Han, Yu & Mathew (2019) propose unbiased and shrinkage estimators of Kelly weights with an explicit shrinkage coefficient. Source: [Quantitative Finance 19(2):277-287, IDEAS](https://ideas.repec.org/a/taf/quantf/v19y2019i2p277-287.html) (abstract only)
- A commenter on the LessWrong post points out that if fractional Kelly is viewed as averaging your belief with the market's, it is full Kelly on the blended probability. Source: [LessWrong comment by abramdemski, 2021](https://www.lesswrong.com/posts/TNWnK9g2EeRnQA8Dg/never-go-full-kelly)

### Inferences
- **Bayesian Kelly for a binary bet.** G(f) is *linear in q*, so a Bayesian who is uncertain about q should bet full Kelly at the posterior mean q̄. Uncertainty on its own does not shrink the bet; it shrinks q̄ toward the prior. With a prior centred on the market price (edge 0, spread τ) and an observed edge ê with standard error s, the posterior mean edge is ê·τ²/(τ² + s²). The Bayesian bet is therefore that fraction of naive Kelly, which is the Rising-Wyner and Baker-McHale form under another name. (This derivation is the project's own and was not checked against Browne & Whitt 1996.)
- **Mis-sized bets (computed):** stake sized for a 1-point edge, growth per bet if the truth differs.

| p | true edge | full Kelly | ½ Kelly | ¼ Kelly |
|---|---|---|---|---|
| 0.95 | +1.0 pt | +0.113% | +0.083% | +0.047% |
| 0.95 | +0.5 pt | **−0.004%** | +0.027% (= the true optimum) | +0.020% |
| 0.95 | 0 | −0.121% | −0.028% | −0.007% |
| 0.95 | −0.5 pt | −0.238% | −0.083% | −0.034% |
| 0.98 | +0.5 pt | −0.040% | +0.070% (= the true optimum) | +0.051% |
| 0.98 | 0 | −0.391% | −0.077% | −0.017% |
| 0.92 | 0 | −0.074% | −0.018% | −0.004% |

  Per 1,000 bets at p = 0.95 with zero true edge, before fees: full Kelly ≈ e^−1.21 ≈ **−70%**, half ≈ −25%, quarter ≈ −6.6%. Halving the edge makes full Kelly a zero-growth bet, which matches Thorp's g = 0 case and Benter's warning.
- **How many bets it takes to know a 1-point edge (computed).** The standard error of a win rate is √(q(1−q)/N).
  - At p = 0.95 (q = 0.96), SE is 0.88 points at N = 500, 0.62 at 1,000, 0.44 at 2,000 and 0.28 at 5,000. A 2-SE edge needs about 1,540 bets; 3 SE needs about 3,460.
  - At p = 0.92 it needs about 2,600 and 5,900. At p = 0.98 it needs about 400 and 890.
  - Same point in loss counts: at q = 0.99 and N = 1,000 you expect about 10 losses. The exact Poisson 95% interval for 10 events is roughly 4.8-18.4, so the loss rate is 0.48-1.84% against a 2% implied rate. The Kelly stake 1 − ratio then ranges from about 0.08 to 0.76. **The Kelly stake rests on a rare-event count.**
- **Baker-McHale-style test on these contracts (computed).** The plug-in win rate comes from N bets, the true edge is 1 point, and the multiplier k on plug-in Kelly is chosen to maximise expected true growth.

| p | N | best k | growth at best k | growth at full plug-in | growth at ½ plug-in |
|---|---|---|---|---|---|
| 0.92 | 500 | 0.51 | 0.58 G* | **−0.09 G*** | 0.58 G* |
| 0.92 | 1,000 | 0.63 | 0.66 G* | 0.39 G* | 0.63 G* |
| 0.92 | 2,000 | 0.75 | 0.76 G* | 0.67 G* | 0.67 G* |
| 0.95 | 500 | 0.60 | 0.64 G* | 0.22 G* | 0.62 G* |
| 0.95 | 1,000 | 0.72 | 0.74 G* | 0.58 G* | 0.66 G* |
| 0.95 | 2,000 | 0.82 | 0.83 G* | 0.78 G* | 0.69 G* |
| 0.95 | 5,000 | 0.91 | 0.92 G* | 0.91 G* | 0.72 G* |
| 0.98 | 1,000 | 0.86 | 0.88 G* | 0.82 G* | 0.68 G* |

  The best k tracks edge²/(edge² + SE²) closely: 0.57 vs 0.60 at p = 0.95, N = 500, and 0.72 vs 0.72 at N = 1,000. This test assumes the **only** error is binomial sampling noise around a stable edge. Real edges also decay from backtest to live (overfitting, competition, regime change), and per Benter and Thorp almost all such errors push the edge down. The practical fraction should therefore sit below this "statistical-only" k. That puts half Kelly as a ceiling and quarter to half Kelly as a defensible range.

### Gaps
- Baker & McHale's full text could not be accessed (the repository returned 403). The exact form of their "back of envelope" shrinkage factor and its Beta-prior assumptions are second-hand, via LessWrong and Metel.
- Browne & Whitt (1996), "Portfolio choice and the Bayesian Kelly criterion", was not retrieved. The posterior-mean result above is the project's own derivation.
- No source was found that quantifies edge decay from backtest to live for prediction-market strategies specifically.

## 4. Fat tails and "picking up pennies" bets

### Takeaway
A binary contract's payoff is bounded (lose the stake or win 1−p), so Kelly already prices the ordinary left tail. The real tail risks are different. First, the small loss probability is itself badly estimated: it is a rare-event rate, and the Kelly stake is 1 minus a ratio of two small numbers. Second, simultaneous bets that lose together (one market move sinking several contracts) act like one larger bet. Third, events outside the model. The literature flags the first two but has little on high-probability binaries specifically.

### Cited findings
- MacLean-Thorp-Ziemba list as a "Bad property" that Kelly bets "may be a large fraction of current wealth when the wager is favorable and the risk of loss is very small". Examples: the 64% Slew of Gold bet and "the 74% future bet on the January effect" in MacLean, Ziemba & Blazenko (1992). They note Kelly "can be very risky in the short term" and that "Long Term Capital is one of many real world instances in which overbetting led to disaster." Source: [MacLean, Thorp & Ziemba 2010](https://www.stat.berkeley.edu/~aldous/157/Papers/Good_Bad_Kelly.pdf)
- Rising & Wyner say the shrinkage view of fractional Kelly is "more difficult to make… mathematically precise" for gambling "because the third and higher moments of the returns are not negligible as they are in daily stock prices" (i.e. skew and fat tails matter). Source: [Rising & Wyner 2012](https://faculty.wharton.upenn.edu/wp-content/uploads/2013/05/Wyner_2012_Partial_3.pdf)
- **Correlated simultaneous bets:**
  - For two independent simultaneous even-money bets with edge m, the optimal stake per bet is m/(1 + m²), only slightly below the sequential f* = m.
  - Blackjack hands at the same table have pairwise correlation of about 0.5, which "should substantially reduce the Kelly fraction per hand".
  - Thorp's sports bets "were generally on different games… so they were approximately independent".
  
  Source: [Thorp 2006, §6](https://wayback.archive-it.org/5456/20240920155724/https://www.eecs.harvard.edu/cs286r/courses/fall12/papers/Thorpe_KellyCriterion2007.pdf)
- Busseti-Ryu-Boyd's drawdown constraint E[(rᵀb)^(−λ)] ≤ 1 heavily penalises outcomes where wealth falls, since it raises returns to a large negative power. That makes it a natural tail-aware sizing rule. With a continuous return distribution it performed about the same as fractional Kelly. Source: [Busseti, Ryu & Boyd 2016](https://web.stanford.edu/~boyd/papers/pdf/kelly.pdf)
- Benter warns that "full Kelly betting is a 'rough ride', downswings during which more than 50% of total wealth is lost are a common occurrence." Source: [Benter 1994](https://gwern.net/doc/statistics/decision/1994-benter.pdf)
- A blog analysis finds Kelly applied to empirical return data "is rather optimistic in general but very sensitive to total losses", and that empirical tails miss losses that never occurred in the sample. Source: [R-bloggers 2016, "The Kelly Criterion in Applied Portfolio Selection"](https://www.r-bloggers.com/2016/12/the-kelly-criterion-in-applied-portfolio-selection/) (blog, lower quality)

### Inferences
- **The loss-ratio form makes the tail problem plain.** At 98¢ with a claimed 1% loss rate, Kelly says stake 50%. If the true loss rate is 2%, the edge is zero, and at a 50% stake each loss halves the bankroll. Underestimating a 1-2% event rate by a factor of 2 is easy with a few dozen observed losses (§3). For "pennies" bets, the dangerous error is underestimating the loss rate, not the size of the loss.
- **Correlated losses inside one settlement window (computed).** Three contracts settle together, each p = 0.95 with a marginal 4% loss chance. Some of that loss chance is a "common shock" that sinks all three at once (for example, one sharp crypto move).

| common-shock probability | optimal stake per contract | total stake in the window |
|---|---|---|
| 0 (independent) | 19.9% | 59.6% |
| 1% | 12.4% | 37.1% |
| 2% | 9.5% | 28.6% |
| 3% | 7.8% | 23.5% |
| 4% (perfectly correlated) | 6.7% | 20.0% (= one bet's Kelly) |

  Even modest correlation cuts the per-contract Kelly stake by 40-65%. Sizing each contract as if it were independent while their losses cluster is a form of overbetting.
- Fractional Kelly applied to the whole window (or a cap on total stake per window) is the simple fix. RCK applied to the joint outcome distribution is the principled one.

### Gaps
- **No primary academic source** was found analysing Kelly specifically for negatively skewed "picking up pennies in front of a steamroller" payoffs or short-volatility strategies. Searches returned only blogs and generic higher-moment portfolio papers. Jondeau & Rockinger 2006 (higher-moment expected-utility expansions) and Hsieh & Barmish 2017 ("On Kelly Betting: Some Limitations", arXiv:1710.01787) turned up but were not read.
- No empirical source was found on how often high-probability (≥95¢) prediction-market contracts fail in clusters.

## 5. In practice: what fractions practitioners use, and why

### Takeaway
Serious practitioners consistently bet below full Kelly: half Kelly is the common reference point, and Benter used 1/2 to 1/3. The stated reasons are, in order: edge overestimation (which only goes one way in practice), drawdown and psychological tolerance, withdrawals that shrink the effective bankroll, and correlated or simultaneous bets. Thorp used Kelly at his funds, but no primary source was found giving the exact fraction there.

### Cited findings
- **Benter (Hong Kong racing syndicate):** "betting the full amount recommended by the Kelly formula is unwise for a number of reasons." He gives three:
  1. "If one overestimates the advantage by more than a factor of two, Kelly betting will cause a negative rate of capital growth… many factors may cause one's real-time advantage to be less than past simulations would suggest, and very few can cause it to be greater. Overestimating the advantage by a factor of two is easily done in practice."
  2. "If it is known that regular withdrawals… will be made… one's effective wealth is less than their actual current wealth."
  3. "Full Kelly betting is a 'rough ride'."

  "A fractional Kelly betting strategy is advisable… (e.g. 1/2 or 1/3)." His live operation used "a conservative fractional Kelly betting strategy… throughout". Source: [Benter 1994, "Computer Based Horse Race Handicapping and Wagering Systems: A Report", in Efficiency of Racetrack Betting Markets](https://gwern.net/doc/statistics/decision/1994-benter.pdf)
- **Thorp:** "if you bet half the Kelly amount, you get about three-quarters of the return with half the volatility. So it is much more comfortable to trade. I believe that betting half Kelly is psychologically much better." Source: interview in Schwager, Hedge Fund Market Wizards (2012), quoted in [Bailey 2013, "Two tales of the Kelly formula", Mathematical Investor](https://mathinvestor.org/2013/10/two-tales-of-the-kelly-formula/). The same article says: "Practitioners regard the Kelly bet size as a red line that should never be crossed."
- **Thorp's fund record:** a convertible-hedging partnership began using "the Kelly criterion to allocate its assets" in November 1969. By 1998 it had compounded at about 20% a year with about 6% standard deviation and roughly zero market correlation, over about 1.25 million bets averaging $65,000. His report of player experience: "most people strongly prefer… 'half Kelly' (or some nearby value)". Source: [Thorp 2006, §9 and §7.4](https://wayback.archive-it.org/5456/20240920155724/https://www.eecs.harvard.edu/cs286r/courses/fall12/papers/Thorpe_KellyCriterion2007.pdf)
- **Ziemba / MacLean-Thorp-Ziemba:**
  - Their analysis suggests "Buffett seems to act similar to a fully Kelly bettor (subject to the constraint of no borrowing) and Keynes like a 80% Kelly bettor."
  - Thorp and Ziemba placed the Slew of Gold bet "with a low fractional Kelly wager" even though full Kelly said 64%.
  - "Practitioners who wish to protect capital above all, sharply reduce risk as their drawdown increases."
  
  Source: [MacLean, Thorp & Ziemba 2010](https://www.stat.berkeley.edu/~aldous/157/Papers/Good_Bad_Kelly.pdf)
- Metel (2017) says the fractional approach, read as "given an estimated upper bound of possible over betting, we correct by dividing all wagers by this amount", "has been endorsed and successfully used in practice by people such as Benter (1994) and Thorp (2006), with betting half the Kelly amount being popular amongst gamblers (Poundstone, 2005)". Source: [Metel 2017](https://arxiv.org/abs/1701.02814)
- Rising & Wyner: "In practice… partial Kelly strategies often outperform full Kelly strategies, and not just over very short horizons." Source: [Rising & Wyner 2012](https://faculty.wharton.upenn.edu/wp-content/uploads/2013/05/Wyner_2012_Partial_3.pdf)
- Busseti-Ryu-Boyd present RCK as a more principled replacement for the "ad hoc" fractional Kelly, with one risk-aversion setting tied to a stated drawdown goal. Source: [Busseti, Ryu & Boyd 2016](https://arxiv.org/abs/1603.06183)

### Inferences
- Applied to 92-99.9¢ contracts with a 1-1.5 point edge, the evidence points to the following:
  1. **Never above half Kelly** of the *estimated* edge. Benter's 2× rule and the computed zero-growth point at 1.3-1.9× Kelly both say the margin for error is smaller than the textbook 2×.
  2. **Quarter to half Kelly** when the edge comes from a backtest or from fewer than about 2,000 live bets (§3 table).
  3. **Size per settlement window, not per contract,** when contracts can lose together (§4).
  4. **Size from the loss-rate ratio,** with a conservative (upper-bound) loss rate. At 98-99.9¢ this matters more than any fixed fraction.
- Quarter Kelly at these prices still means stakes of 3-12% of bankroll per contract (3.1% at 92¢, 5% at 95¢, 12.5% at 98¢ for a 1-point edge). That is large next to typical sports-betting stakes, because favourites have big Kelly fractions (MacLean-Thorp-Ziemba's "Bad property").

### Gaps
- No primary source gives the Kelly fraction Thorp used at Princeton Newport Partners. Thorp's own paper says only that the partnership "decided to… use the Kelly criterion". Thorp's *A Man for All Markets* (2017) and the full Schwager interview were not consulted.
- Poundstone's *Fortune's Formula* (2005) was not read directly; its "half Kelly is popular" point is cited via Metel (2017).
- No credible practitioner write-up (quant trader or bettor) on sizing ≥92¢ prediction-market contracts specifically was found. The search results were vendor blogs and AI-generated "skill" pages, which were excluded.
