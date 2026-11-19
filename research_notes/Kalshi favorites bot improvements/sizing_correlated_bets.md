# Sizing a portfolio of simultaneous, correlated binary bets with a small, uncertain edge

Notes for the Kalshi favorites bot (0-16 bets of 90-99.9c favorites every 15 min; now 3% of bankroll a bet, 20% a window, $10 an order maximum, whole contracts; one-bet Kelly about 13.5%, 95% range 6-22%; P(another favorite in the window loses | one lost) about 33% vs 5% unconditional; worst window 11 of 14 lost).

**About the worked numbers.** Numbers marked "[own calc]" come from the project's own script written for these notes, not from a source. Setup: unconditional loss rate 5%; the average price is backed out from the one-bet Kelly figure. Kelly for a binary contract bought at price c that wins with probability p is f* = (p - c)/(1 - c). With p = 0.95 and f* = 0.135, that gives c = 0.9422, a +6.135% return on a win, and an edge of +0.83% per dollar staked. Losses in a window are joined by a one-factor Gaussian copula (each bet loses when sqrt(rho)·Z + sqrt(1-rho)·e < Phi^-1(0.05), with Z a common "crypto/market" shock shared by the window). rho is calibrated so that P(B loses | A lost) = 0.33. The objective, expected log growth per window E[log(1 + f·((n-K)·win - K))] with K the number of losses, is maximised exactly, integrating over Z with 120-node Gauss-Hermite quadrature (a numerical integration method). Bets in a window are treated as identical, and successive windows as independent. The script is reproducible from this description.

## 1. Kelly for many simultaneous bets, especially correlated binaries: exact and approximate solutions, and how correlation shrinks sizes

### Takeaway
No closed form exists for correlated simultaneous binaries. The exact answer comes from numerically maximising expected log wealth over the joint outcome distribution of the window, which is cheap for 16 bets with a factor model. Correlation, not the per-bet edge, sets the window's total stake. With independent bets, Kelly would put close to 100% of the bankroll into a 14-bet window. With the bot's measured correlation, the Kelly-optimal window total levels off at about 36-37% (about 2.6% a bet at n = 14) [own calc]. That makes "3% a bet, 20% a window" roughly 0.45-0.6x correlated Kelly.

### Cited findings
- **Thorp, two simultaneous independent bets (exact).** Growth is g(f1,f2) = p1p2·ln(1+f1+f2) + p1q2·ln(1+f1-f2) + q1p2·ln(1-f1+f2) + q1q2·ln(1-f1-f2). For identical even-money coins with edge m = p - q, the optimal stake on each is f* = m/(1+m^2), against f* = m when bet one after another. "Since the m_i are typically a few percent, the reduction factors are typically very close to 1." Source: [Thorp, The Kelly Criterion in Blackjack, Sports Betting and the Stock Market (2006/2007), §6](https://www.eecs.harvard.edu/cs286r/courses/fall12/papers/Thorpe_KellyCriterion2007.pdf)
- **Thorp, two correlated bets.** With identical payoffs, the optimal stake on each rises from m/2 (correlation +1) through m/(1+m^2) (correlation 0) to 1/2 (correlation -(1-m)/(1+m)). Blackjack hands at the same table have pairwise correlation of about 0.5, which "should substantially reduce the Kelly fraction per hand." Source: [Thorp 2006, §6, Example 6.2 and Table 5](https://www.eecs.harvard.edu/cs286r/courses/fall12/papers/Thorpe_KellyCriterion2007.pdf)
- **Covariance is not enough.** Thorp: "for an exact solution or an arbitrarily accurate numerical approximation to the simultaneous bet problem, covariance or correlation information is not enough. We need to use the entire joint distribution to construct the g function." Source: [Thorp 2006, §6](https://www.eecs.harvard.edu/cs286r/courses/fall12/papers/Thorpe_KellyCriterion2007.pdf)
- **Thorp's own sports bets.** They "were generally on different games and typically not numerous so they were approximately independent and the appropriate fractions were only moderately less than the corresponding single bet fractions." Source: [Thorp 2006, §6](https://www.eecs.harvard.edu/cs286r/courses/fall12/papers/Thorpe_KellyCriterion2007.pdf)
- **General Kelly gambling is a convex problem.** Maximise E log(r^T b) subject to 1^T b = 1, b >= 0, where r is the vector of returns over a finite set of joint outcomes and b is the stakes vector, cash included. That is a convex optimisation, solvable with standard tools. Sources: [Busseti, Ryu & Boyd, Risk-Constrained Kelly Gambling (2016)](https://arxiv.org/pdf/1603.06183); a worked CVXR implementation is at [CVXR Kelly example](https://cvxr.rbind.io/cvxr_examples/cvxr_kelly-strategy)
- **Exact cost and new algorithms.** Naive exact evaluation over joint outcomes costs O(2^N) for N simultaneous bets. Tepelyan & Lam (Bloomberg, Apr 2026) cut this to O(N) for independent bets with an integral transform, solving problems with hundreds of bets. For correlated bets they use decomposition into subproblems, giving lower and upper bounds on the optimal growth rate. No public code was identified. Source: [Tepelyan & Lam, arXiv 2604.24723](https://arxiv.org/abs/2604.24723)
- **Earlier algorithms.** Whitrow (2007, JRSS C) developed stochastic-gradient algorithms for log-utility staking on many simultaneous sports events, compared them with the simplex method, and framed this as a generalisation of Kelly staking. Source: [Whitrow 2007, RePEc listing](https://ideas.repec.org/a/bla/jorssc/v56y2007i5p607-623.html)
- **Low-edge, independent events.** Long (Mar 2026) shows that singles-only simultaneous Kelly stakes "deviate from the isolated one-event Kelly stakes only at cubic order." That explains Whitrow's observed near-proportionality, and it holds for independent events at low edge. Source: [Long, arXiv 2603.26620](https://arxiv.org/abs/2603.26620)
- **Mean-variance approximation.** A quadratic (Taylor) approximation of the log objective gives a mean-variance (Markowitz) problem: maximise E[rho^T b] - ½E[(rho^T b)^2] (rho = excess return). Source: [Busseti, Ryu & Boyd 2016, §6](https://arxiv.org/pdf/1603.06183)

### Inferences
- [own calc] **Calibration.** P(B loses | A lost) = 0.33 vs 0.05 implies a correlation of about 0.295 between the loss indicators (phi coefficient: (0.33·0.05 - 0.05^2)/(0.05·0.95)). In the Gaussian copula that is a latent correlation of 0.626.
- [own calc] **Exact correlated Kelly per bet (total for the window in brackets):**

  | n | independent | with correlation |
  |---|---|---|
  | 1 | 13.5% | 13.5% |
  | 2 | 13.48% (27%) | 10.2% (20.5%) |
  | 4 | 13.4% (54%) | 6.9% (27.5%) |
  | 8 | 12.5% (100%, cap binds) | 4.1% (33%) |
  | 14 | 7.1% (100%) | 2.6% (36.3%) |
  | 16 | 6.25% (100%) | 2.3% (36.9%) |

  Without correlation, Kelly would stake the whole bankroll on a 14-bet window. Correlation alone brings that down to about 36%.
- [own calc] **Rule of thumb.** For n equal bets with pairwise loss correlation rho, the correlated Kelly per bet is about f1/(1 + (n-1)·rho), and the window total is about n·f1/(1 + (n-1)·rho), which tends to f1/rho as n grows. Here f1 is the single-bet Kelly. With f1 = 13.5% and rho = 0.295 this gives 7.2% (n=4), 4.4% (n=8) and 2.8% (n=14). That is within about 4-8% of the exact values, and slightly too large because the loss tail is skewed. As a fast approximation it is good enough to set a window cap, but for the binding cap use the exact log-growth optimisation.
- [own calc] **The current rule as a fraction of correlated Kelly:**

  | n | per bet | multiple of Kelly | share of max growth |
  |---|---|---|---|
  | 4 | 3% | 0.44x | 66% |
  | 8 | 2.5% | 0.60x | 83% |
  | 14 | 1.43% | 0.55x | 78% |
  | 16 | 1.25% | 0.54x | 77% |

  Structurally, a window cap is the right kind of rule, because the correlated Kelly total levels off as n grows. The 3% per-bet cap does most of the shrinking for small n (0.44x at n=4), and the 20% window cap does it for large n.
- **Implementable replacement.** Each window, solve max over f of E[log(1 + sum_i f_i·R_i)] over the joint loss distribution, with per-bet prices and probabilities. That is 2^16 states at most, or do it analytically by conditioning on the common factor Z (given Z, losses are independent, and the window outcome is a sum of independent binaries). Then multiply by a safety fraction (see §2-3). For 16 bets this runs in milliseconds; no exotic algorithm is needed.

### Gaps
- No published closed form for n equicorrelated binaries was found. The f1/(1+(n-1)rho) shrink is a mean-variance heuristic derived here, checked only against the exact calculation above.
- No public multi-bet Kelly optimiser for correlated binaries was found (Tepelyan & Lam list no code). The CVXR example handles a general finite-outcome joint distribution.

## 2. Fractional Kelly and Kelly under parameter uncertainty: what fraction to use for small, noisy edges

### Takeaway
Uncertainty about the edge always argues for betting below Kelly. Half Kelly keeps about 3/4 of the growth and cuts P(ever losing half) from 1/2 to 1/8. Overestimating the edge is far more dangerous than underestimating it. The Baker-McHale shrink for sampling error alone is mild for this strategy (about 0.9x), but larger (about 0.7-0.8x) if the 6-22% interval ignored within-window clustering. The bigger threat is the edge going to zero in some periods. With an edge this thin, quarter- to half-Kelly of the correlated optimum is the defensible range.

### Cited findings
- **Fractional Kelly in a continuous approximation.** P(wealth ever falls to x of its start) = x^(2/c - 1) for fraction c of Kelly. Full Kelly: P(ever halve) = 1/2. Half Kelly: 1/8. Half Kelly has 3/4 of the growth rate, and P(double before halving) is 8/9 for half Kelly vs 2/3 for full. "Most people strongly prefer the increased safety and psychological comfort of 'half Kelly' (or some nearby value), in exchange for giving up 1/4 of their growth rate." Source: [Thorp 2006, §7.3 and eq. 7.13](https://www.eecs.harvard.edu/cs286r/courses/fall12/papers/Thorpe_KellyCriterion2007.pdf)
- **Overbetting with a wrong edge estimate.** If the true edge is half the estimate and you bet the estimated Kelly, growth is zero, with "increasingly wild oscillations". Betting 1.5x the estimated Kelly gives negative growth and ruin. Lesson: "To the extent m_e is an uncertain estimate of m_t, it is wise to assume m_t < m_e and to choose f < f_e by enough to prevent g <= 0." Source: [Thorp 2006, §7.3](https://www.eecs.harvard.edu/cs286r/courses/fall12/papers/Thorpe_KellyCriterion2007.pdf)
- **Growth vs safety table (blackjack, 2% edge), as a fraction of Kelly:**

  | Fraction of Kelly | P(double before halving) | Relative growth |
  |---|---|---|
  | 0.1 | 0.999 | 0.19 |
  | 0.3 | 0.98 | 0.51 |
  | 0.5 | 0.89 | 0.75 |
  | 0.7 | 0.78 | 0.91 |
  | 1.0 | 0.67 | 1.00 |
  | 1.5 | 0.56 | 0.75 |
  | 2.0 | 0.50 | 0.00 |

  Betting twice Kelly gives roughly zero growth. Source: [MacLean, Thorp & Ziemba, Good and Bad Properties of the Kelly Criterion (2010)](https://www.stat.berkeley.edu/~aldous/157/Papers/Good_Bad_Kelly.pdf)
- **Errors in means dominate.** Errors in means vs variances vs covariances matter about 20:2:1 (cash-equivalent loss; Chopra & Ziemba 1993). "Given the extreme sensitivity of E log calculations to errors in mean estimates, these estimates must be accurate and to be on the safe side, the size of the wagers should be reduced." Practitioners "sharply reduce risk as their drawdown increases." Source: [MacLean, Thorp & Ziemba 2010](https://www.stat.berkeley.edu/~aldous/157/Papers/Good_Bad_Kelly.pdf)
- **Slow statistical confirmation.** In coin tossing, telling a 1.0% edge from a 1.1% edge takes about two million trials for an 84% chance that one dominates. Source: [MacLean, Thorp & Ziemba 2010](https://www.stat.berkeley.edu/~aldous/157/Papers/Good_Bad_Kelly.pdf)
- **Baker & McHale (2013).** When p is estimated, the Kelly stake should be shrunk. Shrunken Kelly beat raw Kelly in simulation and in tennis betting data, and a "back of envelope" shrink estimate is provided. Sources: [Baker & McHale, Decision Analysis 10(3), 2013](https://pubsonline.informs.org/doi/fpi/10.1287/deca.2013.0271); [Salford repository](https://salford-repository.worktribe.com/output/1410355/optimal-betting-under-parameter-uncertainty-improving-the-kelly-criterion)
- **Rule of thumb (beta-posterior model).** Fraction of Kelly alpha = (p-q)^2/((p-q)^2 + sigma^2) = SR^2/(SR^2+1), where SR = edge / (standard deviation of the edge estimate). Under any uncertainty the growth curve "is always sloping down at k=1", so full Kelly is never optimal. This is informal commentary, and the formula's rendering on the page is garbled. Source: [LessWrong, "Never Go Full Kelly"](https://www.lesswrong.com/posts/TNWnK9g2EeRnQA8Dg/never-go-full-kelly)
- **Chance constraints for multi-outcome bets.** On horse races, a chance-constrained expected-log model performed best of the non-perfect-information models (total 18.48 vs 13.27 for 50% fractional Kelly and 18.13 for standard Kelly). Tighter constraints "dampen long term growth" and "will likely need to be calibrated in each application." Source: [Metel, Kelly betting on horse races with uncertainty, arXiv 1701.02814](https://ar5iv.arxiv.org/html/1701.02814)
- **Practitioner fractions (weak sources).** "Most funds use something in the range of 0.2 to 0.5 times Kelly". Source: [QuantVault (blog)](https://quantvault.org/problem-1426-kelly-criterion-and-execution-cost-models.html). Most bettors should use 25% of Kelly or less. Source: [TopEndSports calculator (commercial)](https://www.topendsports.com/sport/betting-tools/kelly-criterion-calculator.htm). Neither source is rigorous.

### Inferences
- [own calc] **Baker-McHale applied here.** A 95% range of 6-22% implies a standard error of the Kelly estimate of about (22-6)/3.92 = 4.1%. So SR = 13.5/4.1 = 3.3 and alpha = 3.3^2/(3.3^2+1) = 0.92.
  - If that interval was computed treating bets as independent, the true standard error is larger by sqrt(design effect), where design effect = 1 + (m-1)·rho for windows of m bets (a standard clustered-sampling correction).
  - With rho = 0.295: m = 8 gives 1.75x the standard error, SR = 1.9, alpha = 0.78. m = 14 gives 2.2x, SR = 1.5, alpha = 0.69.
  - Worth checking how the 6-22% interval was built. A window-level (cluster) bootstrap is the right way.
- [own calc] **Growth per window at n = 14 for each sizing, by true loss rate.** Break-even loss rate at c = 0.9422 is 5.78%. Sizes were set assuming a 5.0% loss rate.

  | True loss rate | Full | Half | Quarter |
  |---|---|---|---|
  | 4.5% | +3.7e-3 | +2.2e-3 | +1.2e-3 |
  | 5.0% (as assumed) | +1.61e-3 | +1.18e-3 (73% of max) | +0.67e-3 |
  | 5.3% | +0.36e-3 | +0.58e-3 | +0.38e-3 |
  | 5.78% (zero edge) | -1.64e-3 | -0.38e-3 | -0.09e-3 |

  - At 5.3%, the edge is 40% smaller than estimated and half beats full.
  - At zero edge, full Kelly loses 4x more than half and 18x more than quarter.
  - So when the edge "may be near zero in some periods", the downside of full Kelly is much larger than its upside.
- **Recommended fractions.** Apply a fraction of about 0.25-0.5 to the correlated Kelly in §1, not to the 13.5% single-bet Kelly. At n=14 that is about 0.65-1.3% a bet (9-18% for the window). At n=4 it is about 1.7-3.4% a bet. The current rule sits at the aggressive end of this range (0.44-0.6x).
- **Make the fraction depend on the evidence of recent edge.** For example, use a Bayesian posterior on the loss rate per market family, updated with a forgetting factor, so sizing shrinks automatically when realised loss rates approach break-even. That is a sizing response to estimated edge, not a stop-loss on P&L.

### Gaps
- The Baker-McHale full text could not be accessed to confirm their exact shrink formula. The SR^2/(SR^2+1) form is from a secondary, informal source.
- No source was found giving the fractions actual prediction-market or sports syndicates use. Practitioner numbers above come from blogs and commercial pages.

## 3. Drawdown-constrained sizing (Grossman-Zhou, Busseti-Ryu-Boyd risk-constrained Kelly, CPPI/floors) and how they compare

### Takeaway
Risk-constrained Kelly (RCK) is the most directly usable method. You add one convex constraint, E[(window return multiplier)^-lambda] <= 1 with lambda = log(beta)/log(alpha), and it guarantees P(wealth ever falls below alpha) < beta. In Boyd's example it beats fractional Kelly at the same drawdown risk. Grossman-Zhou/CPPI-style rules make exposure proportional to the cushion above a floor (a fixed or ratcheting fraction of peak). That is a smooth substitute for hard drawdown halts. For this bot, RCK with "P(ever lose half) < 5%" allows about 14% a window at n=14 and 11% at n=4 (about 0.39x correlated Kelly) [own calc].

### Cited findings
- **The RCK problem.** Maximise E log(r^T b) subject to 1^T b = 1, b >= 0, E(r^T b)^(-lambda) <= 1. "If our bet satisfies E(r^T b)^-lambda <= 1, then its drawdown risk Prob(W_min < alpha) [is] less than beta," with lambda = log beta / log alpha. The problem is convex. Source: [Busseti, Ryu & Boyd 2016, §4-5](https://arxiv.org/pdf/1603.06183)
- **One constraint bounds the whole curve.** Prob(W_min < alpha) < alpha^lambda for every alpha in (0,1). Example: alpha = 0.7, beta = 0.1 gives lambda = 6.46, which also caps P(losing half) at 0.5^6.46 = 0.011. Source: [Busseti, Ryu & Boyd 2016, §5.1](https://arxiv.org/pdf/1603.06183)
- **Light risk aversion.** As lambda goes to 0, the constraint becomes (lambda/2)·var log(r^T b) <= E log(r^T b), a limit on log-wealth variance relative to growth. For two outcomes, the RCK bet is a fractional Kelly bet, found by bisection. Source: [Busseti, Ryu & Boyd 2016, §5.2-5.3](https://arxiv.org/pdf/1603.06183)
- **Numbers (100-period simulation).**
  - Kelly: growth 0.062, drawdown risk P(W_min < 0.7) = 0.397.
  - RCK, lambda = 6.456: growth 0.043, risk 0.073.
  - RCK, lambda = 5.5: growth 0.047, risk 0.099.
  - Fractional Kelly at the same 0.1 risk: growth about 0.035.
  - The bound is "typically around 30% or so higher than the actual risk."
  - The quadratic approximation (QRCK) at matched risk had lower growth (0.044) than RCK.
  Source: [Busseti, Ryu & Boyd 2016, §7](https://arxiv.org/pdf/1603.06183)
- **Grossman & Zhou (1993).** The constraint is that wealth never falls below a fraction alpha of its running maximum, W_t >= alpha·M_t. The optimal risky exposure is proportional to the surplus W_t - alpha·M_t, a CPPI-like rule whose floor ratchets up with the peak. Sources: [Grossman & Zhou, Mathematical Finance 3(3):241-276, RePEc](https://ideas.repec.org/a/bla/mathfi/v3y1993i3p241-276.html); [Columbia PDF discussing drawdown minimisation](https://drupalgsb-test.paas.cc.columbia.edu/sites/default/files-efs/pubfiles/6358/drawdownminimization.pdf)
- **Extensions and a critique.** Cherny & Obłój generalised Grossman-Zhou to semimartingale markets, general utilities and non-linear drawdown functions. Klass & Nowicki (2005) argue "The Grossman and Zhou investment strategy is not always optimal" (only the title was seen). Source: [Cherny & Obłój, arXiv 1110.6289](https://ar5iv.arxiv.org/html/1110.6289)

### Inferences
- [own calc] **RCK applied per window to this bot.** Largest per-bet stake that satisfies the RCK guarantee, assuming independent windows and the copula model:

  | Constraint | lambda | n = 4 | n = 14 | Multiple of correlated Kelly |
  |---|---|---|---|---|
  | P(ever lose 50%) < 5% | 4.32 | 2.7% a bet (10.7%) | 1.0% a bet (14.3%) | 0.39x |
  | P(ever lose 50%) < 1% | 6.64 | 1.9% (7.5%) | 0.72% (10.0%) | about 0.28x |
  | P(ever lose 35%) < 5% | 6.95 | 1.8% (7.2%) | 0.69% (9.7%) | about 0.27x |
  | P(ever lose 20%) < 10% | 10.3 | 1.3% (5.1%) | 0.49% (6.8%) | 0.19x |

  - The current rule (12% at n=4, 20% at n=14) exceeds the "P(halve) < 5%" guarantee level. Because the bound is about 30% conservative, the true risk at those sizes may still be near 5-8%. That is an estimate, not checked by simulation.
- [own calc] **Cross-check with Thorp's formula.** At the current rule's about 0.55x Kelly, x^(2/c-1) gives P(ever halve from start) of about 16% and P(ever down 35%) of about 32% (continuous approximation, edge assumed known). At quarter Kelly the figures are 0.8% and 4.9%, consistent with the RCK row "lose 35% < 5%" at 0.27x.
- **Comparison for this bot:**
  - Fractional Kelly is simple but does not use the shape of the joint loss tail.
  - RCK is the same optimisation as §1 with one extra convex constraint, using the same window loss distribution. It directly encodes "P(hit the 50% halt) < beta" and spreads stake across bets better than a uniform fraction.
  - CPPI / Grossman-Zhou turns the hard "half the starting bankroll" halt into smooth de-risking. Risk per window = k × (W - F), where the floor F is either fixed (for example 50% of start) or ratcheting (alpha × peak). Bets shrink towards zero as the floor nears instead of stopping abruptly.
  - Combining them is natural: cap risk per window at min(RCK cap, k·(W - F)).
- **Gap risk with a floor.** With discrete jumps, a CPPI floor can be breached in a single window if the window's worst-case loss exceeds the cushion. Size so that the cap times the plausible worst window loss (all bets lost, or the empirical worst of 11/14) stays below the cushion. This is reasoning from how CPPI works; no source specific to binary bets was found.
- **Independence assumption.** RCK assumes independent, identically distributed windows. If windows within an hour or day share a volatility regime, risk is understated. Apply RCK to the distribution of daily or multi-window P&L (for example, resampled days), or raise lambda.

### Gaps
- The Grossman-Zhou paper's exact optimal-policy constants for log utility (for example whether exposure = Kelly fraction × surplus) and the growth-rate penalty were not obtained. Those details are unverified here.
- No head-to-head study comparing RCK, Grossman-Zhou and CPPI on short-dated binary portfolios was found.

## 4. Estimating the joint loss distribution of a window's bets (copulas, factor models, empirical resampling)

### Takeaway
A one-factor model is the natural structure: losses are independent once you condition on a common crypto/market shock. That is the Vasicek/Gaussian-copula model used for correlated loan defaults. Calibrated to the bot's 33%-vs-5% conditional loss rate, it gives a 0.6% chance that 11 or more of 14 favorites lose, consistent with the observed worst window. Independence would put that at about 1e-12. Use the factor model for sizing, check it against window-level empirical resampling, and consider fatter-tailed variants.

### Cited findings
- **Vasicek one-factor model.** Each obligor defaults when a latent variable, sqrt(rho)·common factor + sqrt(1-rho)·idiosyncratic, falls below a threshold. Higher rho fattens the tail of the portfolio loss distribution. A closed-form loss density exists for an infinitely granular, homogeneous pool, and it underlies Basel capital formulas. Sources: [vasicekfit R package manual (CRAN)](https://ftp.kaist.ac.kr/CRAN/web/packages/vasicekfit/refman/vasicekfit.html); [MetricGate overview](https://metricgate.com/docs/vasicek-credit-portfolio-loss/); [AcadiFi note on granularity](https://acadifi.com/community/vasicek-single-factor-credit-portfolio-model-granularity)
- **Large-pool loss CDF.** P(loss fraction <= x) = Phi((sqrt(1-rho)·Phi^-1(x) - Phi^-1(p))/sqrt(rho)). Its derivative is the density in the vasicekfit documentation. The CDF form is standard but was not shown verbatim in the sources fetched. Source: [vasicekfit manual](https://ftp.kaist.ac.kr/CRAN/web/packages/vasicekfit/refman/vasicekfit.html)
- **The whole joint distribution is needed.** Exact Kelly needs the entire joint distribution, not just correlations. Source: [Thorp 2006, §6](https://www.eecs.harvard.edu/cs286r/courses/fall12/papers/Thorpe_KellyCriterion2007.pdf)
- **RCK and QRCK both work from simulated outcomes.** They can be solved from Monte Carlo samples of return vectors, estimating moments or running stochastic gradient on samples. So an empirical or resampled window distribution can feed the optimiser directly. Source: [Busseti, Ryu & Boyd 2016, §5-6](https://arxiv.org/pdf/1603.06183)

### Inferences
- [own calc] **Model at n = 14.**
  - Distribution of the number of losses: 0 losses 75.9%, 1 10.2%, 2 4.6%, 3 2.7%, 4 1.8%, 5 1.3%, 6 0.9%, 7 0.7%.
  - P(8 or more of 14 lose) is about 2%. So the bot's "8+ losses in a window" halt would trigger in about 2% of full 14-bet windows even with no change in edge.
  - P(11 or more of 14) = 0.62%, vs 1.5e-12 under independence. The large-pool Vasicek formula at p = 0.05, rho = 0.626 gives P(loss fraction > 11/14) of about 0.36%.
  - So the observed 11/14 window is roughly a 1-in-160 event for a full window under the model: plausible, not a sign the model is broken. Whether it is too rare depends on how many 14-bet windows the backtest contains.
- **Recipe for the bot (layered):**
  1. *Factor model.* Per market family, estimate each bet's loss probability (from price and the edge model) and a factor loading. Use one crypto factor; possibly a second for metals/energy, or block loadings: high within crypto, lower across families. Calibrate loadings by matching conditional loss rates P(B loses | A loses) within and across families, as done above. Given the factor, the window outcome is a sum of independent binaries, which is fast and exact (quadrature over the factor, or a few hundred Monte Carlo draws).
  2. *Fatter tails.* A Gaussian copula has no tail dependence. A t-copula, or a two-regime mixture (a calm regime plus a rare "crash" regime with a high loss rate), matches bad clustering better. Fit the mixture weight to the observed frequency of windows with 50% or more losses.
  3. *Empirical check.* Resample whole historical windows (or whole hours or days, as a block bootstrap) to preserve within-window and short-run cross-window dependence. Compare the empirical tail, P(k or more losses | n), against the model, and size with whichever is more pessimistic.
- **Keep loss rates and edges separate from correlation.** Per the 20:2:1 finding (§2), errors in loss rates (means) hurt far more than errors in correlation. Put the most modelling care into the per-family loss rate and its drift over time, then the factor loading.

### Gaps
- No published work was found fitting copulas or factor models specifically to short-dated crypto up/down binaries or Kalshi markets.
- A t-copula or mixture fit was not verified numerically. That is a suggestion, not a tested result.

## 5. When stop-losses and drawdown halts help or hurt, and capacity: sizing when bigger orders fill worse

### Takeaway
Theory and evidence agree with the bot's backtests. If returns are independent and identically distributed (no momentum), a stop-loss can only lower expected return. It adds value only when losses predict further losses (momentum, or regime switches into negative edge). So halts should be tied to evidence that the edge has gone, such as realised loss rates near break-even, not to P&L alone. On capacity, Kelly sizing should use the edge net of fees and impact. Kalshi's taker fee is about half of this strategy's estimated edge per contract at 94c, and rounding up per order makes 1-2 contract orders unprofitable.

### Cited findings
- **Kaminski & Lo (2014).** Stop-loss rules are "predetermined policies that reduce a portfolio's exposure after reaching a certain threshold of cumulative losses." Under the random-walk hypothesis, simple 0/1 stop-loss rules reduce expected return; with momentum they can add value. On 1950-2004 US equity data (bonds as the stop-out asset), certain rules added 50-100 basis points a month during stop-out periods, which the authors link to regime switching and flights to quality. Sources: [Kaminski & Lo, J. Financial Markets 18:234-254, MIT DSpace record](https://dspace.mit.edu/handle/1721.1/114876); [working-paper abstract (SIFR, source of the random-walk/momentum and 50-100 bp figures, seen via search snippet)](https://swopec.hhs.se/sifrwp/abs/sifrwp0063.htm)
- **Lo & Remorov (2017).**
  - Tight stop-losses on individual US stocks (1964-2014) generally trail buy-and-hold because of trading costs. They can outperform when return autocorrelation is high enough, and the performance of tight stops depends roughly linearly on volatility and autocorrelation.
  - Wide stops can help assets that switch between bull and bear regimes, mainly by reducing downside volatility.
  - The downside-risk reduction is modest.
  Sources: [Lo & Remorov, MIT DSpace](https://dspace.mit.edu/handle/1721.1/107017); [CXO Advisory summary](https://www.cxoadvisory.com/equity-premium/stop-losses-on-stock-positions-in-depth)
- **Cutting risk in drawdowns.** Practitioners who want to protect capital "sharply reduce risk as their drawdown increases" because realised returns may differ from historical estimates. This is a rationale based on estimation error, not on momentum. Source: [MacLean, Thorp & Ziemba 2010](https://www.stat.berkeley.edu/~aldous/157/Papers/Good_Bad_Kelly.pdf)
- **Kalshi taker fee.** fee = round up(0.07 × C × P × (1 - P)) to the next cent, per order. Resting (maker) orders use 0.0175 in place of 0.07. Some products have their own schedules. Kalshi's published example: 100 contracts at $0.55 cost $1.74. Sources: [Allium, Kalshi fees](https://allium.so/blog/kalshi-fees-why-the-cost-peaks-near-50-cents/); [Kalshi fee schedule PDF](https://kalshi.com/docs/kalshi-fee-schedule.pdf)
- **Costs and capacity.** Execution costs that rise with size reduce the effective edge as you size up, so the true optimum is Kelly adjusted downward for impact, and capacity is limited. A linear impact model, delta-P = lambda·Q, is one option. Source: [QuantVault (blog, not rigorous)](https://quantvault.org/problem-1426-kelly-criterion-and-execution-cost-models.html)
- **Existing tooling.** Gnosis's prediction-market-agent library has a Kelly strategy that accounts for price impact (slippage), with a `max_price_impact` cap; 0.1 is suggested as "very conservative" for thin markets. Source: [Gnosis prediction-market-agent docs](https://www.mintlify.com/gnosis/prediction-market-agent/api/betting/kelly-betting)

### Inferences
- **Reading the bot's backtests through Kaminski-Lo.** "Stop-losses and pauses after ordinary losses only gave up profit" is what Kaminski-Lo predicts if window outcomes are roughly independent with a stable edge. A halt helps only if the loss rate after a loss is higher than usual, or the edge is negative during the halt.
  - Test this directly: the autocorrelation of window P&L, and the realised loss rate in the next N windows after a bad window, compared with the baseline.
  - Under the copula model, the "8+ losses" halt triggers in about 2% of full windows even when nothing has changed (§4). If the edge does not decay after such windows, that halt has a cost.
- **Better than P&L halts.** Two options:
  - Shrink size continuously with the posterior edge (§2).
  - A CPPI-style cushion (§3), so sizing falls smoothly as bankroll nears the floor.

  Keep the hard halts only as circuit breakers for faults: data feeds, exchange issues, model bugs, or a regime break detected by a loss-rate test. The "35% in 24 hours" halt is sensible as such a breaker, since a 35% day is far outside what the model allows at correct sizing.
- [own calc] **Fee arithmetic at the average price.** At c = $0.9422, p = 0.95:
  - Edge per contract is about $0.0078.
  - The taker fee before rounding is 0.07 × 0.94 × 0.06 = $0.0039 a contract, about half the edge.
  - With rounding up to the next cent per order: 1 contract pays $0.01, more than the whole edge. 3 contracts pay $0.02 (0.7% of $2.83 staked). 10 contracts pay $0.04 (0.42% of $9.42).
  - Near 99c the fee before rounding is tiny (0.07 × 0.99 × 0.01 = $0.0007 a contract), but rounding still charges at least $0.01 an order.
  - Implications: (a) check whether the 13.5% Kelly was measured net of fees. If gross, the net edge and the Kelly fraction roughly halve. (b) Skip bets whose stake is too small to cover the rounded-up fee, setting a minimum contracts-per-order threshold for each price. (c) Maker (resting) orders at 0.0175 would cut fees about 4x, if fill risk allows.
- **Sizing with a depth-dependent price (derived here, not from a source).** Buying n_j contracts at ask levels c_j gives wealth W_win = W + sum n_j(1 - c_j) if the bet wins and W_lose = W - sum n_j·c_j if it loses.
  - The next contract at price c raises expected log wealth only if p(1-c)/W_win > (1-p)c/W_lose, that is c < c_res = p·W_lose / (p·W_lose + (1-p)·W_win), a "Kelly reservation price".
  - Rule: walk up the book, buying while the ask is below c_res (net of fees). c_res starts at p and falls as the position grows.
  - For a correlated window, compute c_res from the window's joint distribution, conditioning on the bets already filled. Partial fills simply change the filled vector; re-solve the remaining stakes given it.
  - With the $10 order cap at a few hundred to a few thousand dollars of bankroll, impact on thin 15-minute books mainly matters for the most extreme favorites.

### Gaps
- No academic paper was found deriving Kelly sizing under order-book impact for binary prediction markets. The reservation-price rule above is derived here.
- No measurement of Kalshi 15-minute crypto book depth or partial-fill rates was found in this search.
- Kaminski & Lo's exact formulas could not be checked (the PDF fetch failed, HTTP 405). The random-walk vs momentum result is from the abstract and summaries.

## 6. Practitioner lessons from sports syndicates, "picking up pennies" option sellers and short-vol blowups

### Takeaway
The recurring pattern: strategies that win small amounts most of the time and lose large amounts rarely look safe for years, and then a single correlated tail event wipes them out. Contributing factors are sizing to recent calm, concentrated correlated short positions, and leverage. The bot's favorites are this type of payoff (win about 6%, lose 100%), but without leverage and with losses capped at the stake. The relevant lessons are to size to the stressed joint tail, not to recent calm, and never to raise risk to chase a return target.

### Cited findings
- **XIV, the inverse-VIX note (Feb 2018).**
  - Fell 96.3% on Feb 5, 2018, when the VIX rose 115.6%, its largest one-day gain ever.
  - Net asset value went from $115.55 to $4.22. It had $1.9B in assets the prior Friday.
  - Credit Suisse called an "acceleration event" because the intraday value fell to 20% or less of the prior day's close, a trigger the prospectus had disclosed.
  - ProShares' SVXY fell about 96.1% the same day.
  Source: [ETF.com, Inverse VIX ETN Shuts Down](https://www.etf.com/sections/news/inverse-vix-etn-shuts-down)
- **LJM Partners (Feb 2018).**
  - Sold out-of-the-money S&P 500 futures options on margin.
  - Its Preservation and Growth fund lost more than 80% in the week ended Feb 7, 2018.
  - The SEC alleged that LJM misled investors about its risk management and stress testing, and that from late 2017, in historically low volatility, it "increased the level of risk in the portfolios in order to chase return targets." The defendants settled without admitting or denying.
  Sources: [SEC press release 2021-89](https://www.sec.gov/news/press-release/2021-89); [Reuters via Business Standard](https://www.business-standard.com/amp/article/reuters/u-s-fund-that-lost-most-of-its-value-shuts-doors-to-new-investment-118020900219_1.html); [Opalesque, final judgments](https://www.opalesque.com/710182/SEC_issues_final_judgments_against_LJM_traders_and018.html)
- **OptionSellers.com (Nov 2018).**
  - Wrote naked commodity options for about 290 clients, concentrated in natural gas calls and crude oil puts.
  - Natural gas jumped about 20% in one day on Nov 14, 2018, to an intraday $4.93. INTL FCStone liquidated about 300 accounts.
  - Clients lost everything, and deficits owed to the broker were $35.3M.
  - Assets of about $150M are a blogger's estimate.
  Sources: [Early Retirement Now](https://earlyretirementnow.com/2018/12/18/the-optionsellers-debacle/); [Wolf Street](https://wolfstreet.com/2018/12/17/us-natural-gas-plunges-unwinds-spike-that-blew-up-hedge-fund/); [FA Magazine](https://www.fa-mag.com/news/wiped-out-fund-investors-seek-to-recoup-losses-from-broker-42210.html?section=)
- **Thorp's sports-betting test.**
  - A $50,000 bankroll made $123,000 profit in 101 days of Kelly-sized bets.
  - Simultaneous bets were on different games and so roughly independent, and their fractions were only moderately below single-bet Kelly.
  - Thorp stopped for operational reasons, including the risk of transporting cash.
  Source: [Thorp 2006, §6](https://www.eecs.harvard.edu/cs286r/courses/fall12/papers/Thorpe_KellyCriterion2007.pdf)
- **Bad luck even when sized correctly.** Even with positive-edge bets sized correctly, Kelly can produce poor outcomes. In one example, 700 bets with a 14% edge can turn $1,000 into $18, and half Kelly "does not help much" ($1,000 can still become $145). Source: [MacLean, Thorp & Ziemba 2010](https://www.stat.berkeley.edu/~aldous/157/Papers/Good_Bad_Kelly.pdf)
- **Large-favorite bets.** Kelly can call for huge stakes when the edge looks favorable and the chance of loss looks small; a 64% optimal wager on a 3-5 favorite is cited. Thorp and Ziemba "actually made this place and show bet and won with a low fractional Kelly wager." Source: [MacLean, Thorp & Ziemba 2010](https://www.stat.berkeley.edu/~aldous/157/Papers/Good_Bad_Kelly.pdf)

### Inferences
- **Mapping to the bot.** A 94c favorite is a short out-of-the-money option: it collects about 6% and risks 100%. LJM, XIV and OptionSellers failed through (a) correlated positions hit at once, (b) leverage or margin turning a large loss into a total one, and (c) sizing that grew in calm periods. The bot has no leverage and its loss is capped at the stake, so (b) does not apply. (a) is exactly the within-window clustering, and (c) applies if the edge estimate is updated from calm periods only.
- **Concrete lessons.**
  1. Set the window cap from a stressed joint distribution: copula with fat tails or the worst historical windows, plus an RCK constraint (§3), not from the average correlation.
  2. Do not increase the per-window fraction after long calm streaks. Let bankroll growth, not a rising fraction, raise dollar stakes.
  3. Treat a rise in a market family's loss rate as possible regime change and shrink that family's edge estimate. That is a size response, not a P&L stop.
  4. Cap exposure per family (for example crypto) across windows that are close in time, since one move can hit several consecutive windows.
- **Recommended sizing to replace "3% a bet, 20% a window"** (synthesis of §1-5; numbers are [own calc] under the model):
  1. Each window, compute the correlated-Kelly stakes f_K over the factor-model joint distribution.
  2. Apply a safety fraction k of 0.25-0.5. Use the low end when the posterior edge is weak or recent loss rates are near break-even.
  3. Add the RCK constraint, for example P(ever halve) < 5% (lambda of about 4.3).
  4. Add a CPPI cushion term: window risk at most m × (W - floor).
  5. Apply a fee- and depth-aware minimum and maximum order size (contracts at or below the reservation price; skip orders too small to cover the rounded-up fee).

  Under the model the result is about 2-3.5% a bet for small windows, levelling off at about 10-15% for a full window.

### Gaps
- No detailed public write-up by a sports syndicate or a prediction-market fund on sizing correlated simultaneous bets was found. Syndicate practice above is limited to Thorp's account.
- No reliable post-mortem on 0DTE (same-day expiry) option-selling blowups was found. The short-vol examples above are 2018 events.
- The LJM asset figures differ between sources ($700M+ vs $812M).
