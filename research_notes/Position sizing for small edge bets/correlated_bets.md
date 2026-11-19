# Sizing many simultaneous, correlated bets: multi-bet Kelly and caps on correlated groups

Case: up to ~10 crypto "up/down in 15 minutes" favourites per window (BTC, ETH, SOL, XRP, DOGE, ...), all settling at the same moment; P(another favourite in the window loses | one lost) ≈ 36%; plus a few metals and energy contracts. Current rule: 3% of bankroll per bet, 20% of bankroll summed over a window.

Notation used below: *c* = contract price, *p* = true win probability, *q* = 1 − *p*, *b* = (1 − *c*)/*c* = net odds (profit per $1 staked on a win). Single-bet Kelly fraction for a binary contract: f₁ = (p − c)/(1 − c).

## 1. Simultaneous Kelly: how does Kelly extend to bets that settle together, and how does the fraction per bet shrink with n and correlation?

### Takeaway
Simultaneous Kelly means maximising the expected log of wealth over the **joint** outcome distribution of all bets in the window; there is no closed form beyond a few bets, so it is solved numerically. Per-bet stakes shrink only slightly for independent small-edge bets. They shrink a lot under positive correlation: at correlation 1 the whole cluster is one bet, and with pairwise correlation ρ the cluster behaves like about n/(1+(n−1)ρ) independent bets. That number tops out at 1/ρ however many bets you add.

### Cited findings
- **Thorp, two simultaneous independent bets (Example 6.1):** for two independent favourable coins with edges m₁, m₂ (m = p − q), the optimal fractions are f₁* = m₁(1 − m₂²)/(1 − m₁²m₂²) and f₂* = m₂(1 − m₁²)/(1 − m₁²m₂²). With equal edges this is f* = m/(1 + m²) per bet when the bets are simultaneous, versus f* = m when they are sequential. Thorp notes that "since the mᵢ are typically a few percent, the reduction factors are typically very close to 1." Source: [Thorp 2006, "The Kelly Criterion in Blackjack, Sports Betting, and the Stock Market", Handbook of Asset and Liability Management ch. 9, pp. 402-404](https://www.gwern.net/doc/statistics/decision/2006-thorp.pdf)
- **Thorp, two correlated bets (Example 6.2, Table 5):** for two identical favourable coins whose correlation runs from +1 down to −(1 − m)/(1 + m), the per-bet Kelly fraction rises from m/2, through m/(1 + m²) at zero correlation, to 1/2. At correlation +1 each bet gets half the single-bet Kelly, so the pair together equals **one** Kelly bet. Source: [Thorp 2006, pp. 404-405](https://www.gwern.net/doc/statistics/decision/2006-thorp.pdf)
- **Correlation alone is not enough (Thorp):** "for an exact solution or an arbitrarily accurate numerical approximation to the simultaneous bet problem, covariance or correlation information is not enough. We need to use the entire joint distribution to construct the g function." Source: [Thorp 2006, p. 405](https://www.gwern.net/doc/statistics/decision/2006-thorp.pdf)
- **Thorp's live sports-betting practice:** in 1994 his team placed 5-15 bets a day, about $20,000 of action a day at ~6% expectation, and grew a $50,000 bankroll by $123,000 in 101 days. "Our simultaneous sports bets were generally on different games and typically not numerous so they were approximately independent and the appropriate fractions were only moderately less than the corresponding single bet fractions." He contrasts this with blackjack hands at the same table, which have "a pairwise correlation that has been estimated at .5 (Griffin, 1979, p. 142). This should substantially reduce the Kelly fraction per hand." Source: [Thorp 2006, pp. 402-404](https://www.gwern.net/doc/statistics/decision/2006-thorp.pdf)
- **Thorp's multi-asset (continuous) form:** with mean excess returns M − R and covariance matrix C, growth g∞ = r + Fᵀ(M − R) − FᵀCF/2 is maximised at F* = C⁻¹(M − R). Uncorrelated assets reduce to fᵢ* = (mᵢ − r)/sᵢ². He also lists the practical constraints: per-position limits fᵢ ≤ Mᵢ and a total limit Σ|fᵢ| ≤ M. Source: [Thorp 2006, pp. 406, 418-419](https://www.gwern.net/doc/statistics/decision/2006-thorp.pdf)
- **No analytic solution beyond 4 bets:** for M simultaneous games G = ⟨ln[1 + Σ fᵢRᵢ]⟩. This has "no analytical solution for M ≥ 5" and "can be maximized by numerical techniques (Whitrow, 2007) or by analytical approximations." Source: [Medo, Yeung & Zhang 2009, "How to quantify the influence of correlations on investment diversification", International Review of Financial Analysis (arXiv 0805.3397)](https://arxiv.org/pdf/0805.3397)
- **Effective number of bets (Medo et al.):** to first order (expanding 1/(1+x) ≈ 1 − x, valid when returns per period are small), the optimal Kelly fractions solve Σⱼ fⱼ⟨RᵢRⱼ⟩ = ⟨Rᵢ⟩. For identical bets this gives f* = μ(C⁻¹1)/(σ² + μ² Σᵢⱼ(C⁻¹)ᵢⱼ). The total Kelly stake on M correlated bets equals that of m_ef uncorrelated bets, where m_ef = Σᵢⱼ(C⁻¹)ᵢⱼ (Eq. 18). With uniform pairwise correlation C this is **m_ef = M / (1 + (M − 1)C)**, which tends to **1/C** as M → ∞: "diversification into arbitrarily many assets with mutual correlation C is equivalent to investment in only 1/C uncorrelated assets." For a block-diagonal structure (independent clusters) the effective sizes add: m_ef = m_ef(C₁) + … + m_ef(C_N) (Eq. 9). Source: [Medo et al. 2009](https://arxiv.org/pdf/0805.3397)
- **Accuracy of that approximation:** Medo et al. checked Eq. 19 against exact numerical Kelly for binary bets (M = 10, correlation induced through a hidden common factor). It "performs well" for p ≤ 0.60. At p = 0.70 it deviates for C ∈ (0.1, 0.4), where more than 80% of wealth is invested. Source: [Medo et al. 2009, §3.2, Fig. 1](https://arxiv.org/pdf/0805.3397)
- **Whitrow (2007):** "The problem of optimizing a number of simultaneous bets is considered, using primarily log-utility. Stochastic gradient-based algorithms for solving this problem are developed and compared with the simplex method. The solutions may be regarded as a multi-bet extension of the Kelly criterion." It has two worked examples using real sports bookmaker odds, and notes the method applies to general portfolio optimisation. Published in J. Royal Statistical Society Series C 56(5):607-623, 2007, doi 10.1111/j.1467-9876.2007.00594.x. Source: [IDEAS/RePEc record of Whitrow 2007](https://ideas.repec.org/a/bla/jorssc/v56y2007i5p607-623.html)
- **Whitrow's near-proportionality explained (2026 preprint):** for *independent* multi-outcome events, Long (2026) proves the Kelly optimiser factorises event by event. With parlays forbidden (singles only), stakes deviate from isolated one-event Kelly stakes "only at cubic order" in the edge, and the growth cost of forbidding parlays is O(ε⁴). He presents this as the explanation of "Whitrow's empirical near-proportionality phenomenon": simultaneous singles stakes are nearly proportional to stand-alone Kelly stakes. The paper is not peer reviewed. Source: [Long 2026, "Optimal Parlay Wagering and Whitrow Asymptotics", arXiv 2603.26620](https://arxiv.org/abs/2603.26620)
- **A practitioner library's split:** `penaltyblog` offers a "simultaneous" mode, where a numerical optimiser maximises portfolio log growth over all bets jointly, and an "independent" mode, which sizes each bet at its own Kelly and then scales all of them down proportionally to fit `max_total_stake`. The docs call the independent mode "less optimal but faster." Its scope is mutually exclusive outcomes of one match. Source: [penaltyblog docs, "Bet Sizing"](https://penaltyblog.readthedocs.io/en/latest/betting/bet_size.html)

### Inferences
- Thorp's two-bet result already contains the key design rule. At correlation 1, n bets = one bet: the **window total**, not each bet, should be about one single-bet Kelly. At correlation 0 with small edges, each bet keeps roughly its own Kelly size. The real case sits in between, and Medo's m_ef = n/(1 + (n − 1)ρ) interpolates between the two.
- For this case, the 36% conditional loss rate converts to a binary (phi) correlation of about 0.33 when q ≈ 4-5%. Then m_ef = 10/(1 + 9·0.33) ≈ 2.5, and the ceiling is 1/0.33 ≈ 3. Ten correlated crypto favourites therefore carry about as much diversification as **2.5-3 independent bets**.
- The "small-edge" shrinkage results (Thorp's m/(1+m²), Long's cubic-order result) assume the Kelly fractions themselves are small. Favourites bought at 90-95¢ have small edges in cents, but large single-bet Kelly fractions (about 29-43% at 93¢ with 2-3¢ of edge; see Q5) because the odds are short. So even *independent* simultaneous bets interact strongly here, and in the model below the total hits the 100%-of-bankroll cash limit by about 5 bets.

### Gaps
- Whitrow's full text (paywalled) was not read, so his specific numerical examples and stake ratios are not reported here; only the abstract is confirmed.
- MacLean-Ziemba-specific results on correlated multi-asset Kelly were not read in full (see Q3 for MacLean-Thorp-Ziemba 2010 on fractional Kelly).

## 2. Copula / Monte Carlo: how do practitioners estimate correlation of binary outcomes and solve for the sizes?

### Takeaway
The standard workflow has three steps. First, build a joint outcome model: a one-factor Gaussian (or Student-t) copula on latent variables thresholded to the market-implied marginals, or a mixture/"regime" model. Second, generate scenarios by enumerating all 2ⁿ outcomes for small n, or by Monte Carlo. Third, maximise expected log wealth over those scenarios as a convex programme, optionally with a drawdown constraint (Busseti-Ryu-Boyd). Two caveats matter. Binary correlation is not the same as latent correlation. And underestimating correlation is much costlier than overestimating it.

### Cited findings
- **Kelly as a convex programme:** for finitely many outcome scenarios rᵢ with probabilities πᵢ, Kelly is "maximize Σᵢ πᵢ log(rᵢᵀb) subject to 1ᵀb = 1, b ≥ 0". The problem is convex and "readily solved" with CVX/CVXPY/Convex.jl. For infinite or sampled distributions, use projected stochastic gradient with the unbiased gradient estimate r/(rᵀb). Source: [Busseti, Ryu & Boyd 2016, "Risk-Constrained Kelly Gambling", Journal of Investing 25(3) (arXiv 1603.06183)](https://web.stanford.edu/~boyd/papers/pdf/kelly.pdf)
- **Risk-constrained Kelly (RCK):** add the constraint E[(rᵀb)^(−λ)] ≤ 1 with λ = log β / log α. This guarantees Prob(W_min < α) < β, i.e. the chance that wealth ever falls below fraction α of its start is under β. For finite scenarios the constraint is log Σᵢ exp(log πᵢ − λ log(rᵢᵀb)) ≤ 0, a log-sum-exp form and still convex. Example: α = 0.7, β = 0.1 gives λ = 6.46, which also implies P(ever losing half) ≤ 0.5^6.46 ≈ 1.1%. Source: [Busseti et al. 2016, §3-5](https://web.stanford.edu/~boyd/papers/pdf/kelly.pdf)
- **RCK beats fractional Kelly at equal risk:** with 19 risky bets and 100 outcomes, full Kelly had growth 0.062 per period but a 39.7% chance of a 30% drawdown. RCK (λ = 5.5) had growth 0.047 at 9.9% drawdown risk. "the Kelly fractional bet that achieves our risk bound 0.1 has a growth rate around 0.035, compared with RCK, which has a growth rate 0.047." The drawdown bound typically ran about 30% above the Monte Carlo-measured risk. A quadratic approximation (QRCK) is tied to Markowitz mean-variance but did worse than RCK. Source: [Busseti et al. 2016, §7.1, Tables 1-2](https://web.stanford.edu/~boyd/papers/pdf/kelly.pdf)
- **Joint binary Kelly scales as 2ᴺ:** "Placing several bets at once generally requires numerical optimization over the joint outcome space," naively O(2ᴺ). For independent bets an integral transform cuts objective evaluation to O(N), handling hundreds of bets. For the general (correlated) case, decomposing into sub-problems gives lower and upper bounds on the optimal growth rate. The authors tested on prediction-market-inspired synthetic data (2026 preprint). Source: [Tepelyan & Lam 2026, "Efficient Multivariate Kelly Optimization Reveals Sigmoidal Scaling Laws", arXiv 2604.24723](https://arxiv.org/abs/2604.24723)
- **Pitfalls of Gaussian-threshold (copula) models for binaries:** setting the latent Gaussian correlations equal to the target Bernoulli correlations "is generally incorrect" after thresholding. Tetrachoric calibration (solving for the latent correlation that reproduces each target binary correlation) is exact only if the calibrated matrix is positive semidefinite. The authors instead solve a linear programme over the joint Bernoulli probability mass function, which either matches the targets exactly or certifies they are infeasible (2026 preprint). Source: [Wong & Ben Chaouch 2026, "A Practical Guide to Simulating Correlated Binary Outcomes", arXiv 2607.16801](https://arxiv.org/abs/2607.16801)
- **Hidden-factor construction for correlated binaries:** Medo et al. induce equal pairwise correlation C among binary bets via a hidden binary asset h, with P(+i | +h) = p + (1 − p)√C and P(−i | −h) = 1 − p + p√C. Conditional on h the bets are independent, so the joint distribution is a two-state mixture. Source: [Medo et al. 2009, Eq. 21-22](https://arxiv.org/pdf/0805.3397)
- **Mis-estimating correlation is asymmetric:** with true C = 0.2 and p = 0.55, "underestimation of correlations (C′ < C) decreases investment performance dramatically"; "a naive investor supposing zero correlations can even end up with diminishing wealth. By contrast, a similar overestimation of C results in only a mild decrease of the growth rate." Source: [Medo et al. 2009, §3.2, Fig. 2](https://arxiv.org/pdf/0805.3397)
- **Cluster (sector) averaging to tame noise:** with assets grouped into sectors, replace the full correlation matrix by average intra-sector and inter-sector correlations C̃ and solve for one fraction per sector. Then m_ef = Σ_IJ (C̃⁻¹)_IJ. Large correlation matrices estimated from finite data are noisy, citing Laloux et al. 1999. Source: [Medo et al. 2009, §3.3, §4.2](https://arxiv.org/pdf/0805.3397)
- **Overbetting is worse than underbetting:** "using too large an f* and overbetting is much more severely penalized than using too small an f* and underbetting". Thorp's sports-betting edge estimates "were deliberately chosen to be conservative" for this reason. Source: [Thorp 2006, p. 402](https://www.gwern.net/doc/statistics/decision/2006-thorp.pdf)
- **Tail dependence:** a non-peer-reviewed quant toolkit notes that the Gaussian copula has zero tail dependence (joint extreme moves are modelled as near-impossible), whereas a Student-t copula has positive tail dependence. Source: a practitioner's write-up (not linked) (low-authority source; the property itself is standard copula theory)

### Inferences
- A practical recipe for one 15-minute window:
  1. **Marginals:** per-contract win probability p̂ᵢ from the model or backtest.
  2. **Dependence:** estimate the pairwise co-loss rate P(both lose) from historical windows, i.e. the 36% conditional times the marginal. Convert it to a phi correlation, (P₁₁ − qᵢqⱼ)/√(qᵢpᵢqⱼpⱼ), and then to a latent (tetrachoric) correlation. With q = 5%, 36% conditional gives phi ≈ 0.33 and latent ρ ≈ 0.66. One common factor ("crypto beta" in the window) plus idiosyncratic noise is the natural structure: BTC drives the alts.
  3. **Scenarios:** enumerate all 2ⁿ loss patterns. With n ≤ 13 this is at most 8,192 scenarios, which is trivial; no Monte Carlo is needed.
  4. **Solve:** maximise Σ π_s log(1 + R_s·f) in CVXPY, with per-bet bounds, a cluster-sum bound and optionally the RCK drawdown constraint.
- Following Medo's asymmetry result, if the co-loss estimate is uncertain, round it **up** rather than down.
- Thorp's "need the entire joint distribution" warning matters most for multi-loss tails (3+ of 10 losing together). It can be stress-tested by fitting a second model with the same pairwise statistics but fatter joint tails (a beta-binomial or t-copula) and checking whether the sizes change. In the model below they barely changed (Q5).

### Gaps
- No published estimate of the joint-loss structure for Kalshi 15-minute crypto contracts was found. The 36% figure is the project's own measurement.
- No peer-reviewed paper was found that specifically applies copula plus Kelly to prediction-market contracts. The 2026 arXiv papers above are preprints, and the hackathon-style "copula + quasi-Monte Carlo" project pages found in search were not used as evidence.

## 3. Cap rules: what heuristics are used for correlated groups?

### Takeaway
The common heuristics share one idea: **cap the correlated group as if it were one position**. Banks do this with the Basel "group of connected counterparties" limit, and Thorp's correlation-1 limit says the same thing. Rules then add a per-name cap inside the group (as in UCITS 5/10/40) and use fractional Kelly to absorb estimation error. Sports-betting guidance on per-game or per-day caps exists, but it is mostly informal blog advice (e.g. "divide Kelly by number of concurrent bets; cap total exposure ~25%") with no derivation.

### Cited findings
- **Basel large-exposure limit treats a correlated group as one counterparty:** a bank's total exposure to a single counterparty *or a group of connected counterparties* must not exceed 25% of Tier 1 capital (15% between G-SIBs, the global systemically important banks). A "large exposure" is anything ≥ 10% of Tier 1. The limit applies to "groups of connected counterparties (ie counterparties that are interdependent and likely to fail simultaneously)". It has been in force since 1 Jan 2019. Sources: [BCBS press release, Apr 2014](https://www.bis.org/press/p140415.htm); [BIS FSI summary, Large exposures standard](https://www.bis.org/fsi/fsisummaries/lex.htm)
- **UCITS 5/10/40 is a two-tier per-name and aggregate rule:** a UCITS fund may hold up to 5% of assets in one issuer. That can rise to 10% per issuer, provided all holdings above 5% together total ≤ 40% of the fund (UCITS Directive Art. 52). Sources: [Open Exam Prep, CISI study guide "UCITS & AIFMD"](https://open-exam-prep.com/study-guides/cisi-icwim/collective-investment-schemes/ucits-and-aifmd-regimes); [Legal500, index-tracking UCITS](https://www.legal500.com/intelligence/ireland/wealth-management/index-tracking-ucits) (secondary sources; the primary text is the Directive)
- **Fractional Kelly as the default safety margin:** "half Kelly" has 3/4 of the full-Kelly growth rate. P(doubling before halving) rises from 2/3 to 8/9, and the chance of *ever* losing half the bankroll falls from 1/2 to 1/8. Thorp reports that most players and teams "strongly prefer" about half Kelly. Source: [Thorp 2006, §7.3, pp. 414-415](https://www.gwern.net/doc/statistics/decision/2006-thorp.pdf)
- **Kelly bets can be very large in favourable short-term situations:** fractional Kelly (blending Kelly with cash) is "significantly less risky" while keeping "a significant part of the upside". Sources: [MacLean, Thorp & Ziemba 2010, "Long-term capital growth: the good and bad properties of the Kelly and fractional Kelly capital growth criteria", Quantitative Finance 10(7)](https://escholarship.org/content/qt5mr5k8qj/qt5mr5k8qj.pdf); [Berkeley copy](https://www.stat.berkeley.edu/~aldous/157/Papers/Good_Bad_Kelly.pdf)
- **Blackjack:** teams and advantage players "often bet a fraction of the Kelly optimal". Chin (2019) estimates historical Kelly fractions for portfolios of correlated bets with a multivariate geometric Brownian motion model. Source: [Chin 2019, "Kelly fraction estimation for multiple correlated bets", UNLV Int'l Conference on Gambling & Risk Taking](https://oasis.library.unlv.edu/gaming_institute/2019/May28/57)
- **Sports-betting rule of thumb (low-authority):** "Divide Kelly suggestion by number of concurrent bets; account for correlation between bets; consider limiting total exposure to 25%." Source: [TopEndSports Kelly calculator page](https://www.topendsports.com/sports-betting/tools/kelly-criterion-calculator/) (affiliate/guide site, no derivation)
- **Same-game parlay guides (low-authority):** treat correlated same-game parlays as "a small, capped allocation" (1-2% of a unit), with some bettors capping parlay exposure at 5-10% of weekly turnover. Books price correlated legs ~15% short of independent multiplication. Source: [DeucesCracked, same-game parlay correlation guide](https://www.deucescracked.com/blog/same-game-parlay-strategy-correlation-guide) (blog; heuristics, not derived)
- **Max positions per cluster: diversification saturates.** With uniform correlation, m_ef → 1/C. For stocks, even-weight diversification benefits are "exhausted already with a portfolio of ten assets" (Elton & Gruber 1977, as summarised by Medo et al.). Source: [Medo et al. 2009, §4.2](https://arxiv.org/pdf/0805.3397)

### Inferences
- **"Treat the cluster as one bet"** is the correlation-1 limit (Thorp Table 5). It is conservative for ρ ≈ 0.33: the true Kelly window total is about 2-2.5× a single-bet Kelly, not 1× (see Q5). As a *cap* it is reasonable, and it is the Basel logic.
- **A max number of positions per cluster** has theoretical support beyond saturation. Correlated joint Kelly drives the *weakest* bets in a correlated cluster to zero; in the 10-contract example in Q5, only the top 5 by edge get any stake. A position-count cap that keeps the best k bets approximates this, **provided the edge ranking is reliable**. If edge estimates are noisy, ranking adds selection bias (the top-ranked edges are the most overestimated ones), which argues for k a bit above 1/ρ rather than below it.
- **Per-event or per-day caps** in sports betting are the same idea at a different granularity: cap exposure to a shared driver, such as one game or one news cycle. Here the shared driver is the window's crypto move, so the right "event" is the 15-minute window per asset class.
- **Independent clusters should get separate budgets.** Medo's block result (m_ef adds across independent blocks) means metals and energy contracts that are roughly independent of crypto should *not* share the crypto window's sum cap. Counting them against it understates the diversification they add.

### Gaps
- No authoritative, quantitative per-game or per-day cap from a recognised sports-betting quant (e.g. a published syndicate rule) was found. Available sources are blogs or affiliate pages.
- Pinnacle's own articles on simultaneous Kelly did not surface in search.

## 4. Sum cap vs per-bet cap: how should a 20% window cap compare with a 3% per-bet cap? Is "20% ÷ n per bet" sound, and what is better?

### Takeaway
A fixed sum cap plus a fixed per-bet cap makes the **Kelly multiple vary about 3× with the number of bets**. The rule is very conservative (~0.1× Kelly) when one bet is open and much more aggressive (~0.3× Kelly) when 8-10 correlated bets are open. Theory says the window total should grow with n only like n/(1 + (n−1)ρ): ×1.4 at 2 bets, ×2.2-2.5 at 10, never above ×3. Splitting the sum cap equally ("20% ÷ n") is only right if all bets have equal edge. Within a binding cap the growth-optimal allocation fills the **highest-edge bets first** (up to the per-bet cap) and leaves the weakest at zero.

### Cited findings
- Kelly window total vs n (theory): the total Kelly stake on n correlated bets equals m_ef = n/(1+(n−1)ρ) uncorrelated bets' worth, saturating at 1/ρ. Source: [Medo et al. 2009, Eq. 17-19](https://arxiv.org/pdf/0805.3397).
- Correlation 1 gives per-bet = single Kelly / n, so the cluster total equals one Kelly bet. Source: [Thorp 2006, Table 5](https://www.gwern.net/doc/statistics/decision/2006-thorp.pdf).
- Per-name plus aggregate caps are standard (UCITS 5/10/40; Thorp lists fᵢ ≤ Mᵢ and Σ|fᵢ| ≤ M as typical constraints added to the Kelly optimisation). Sources: [Thorp 2006, p. 406](https://www.gwern.net/doc/statistics/decision/2006-thorp.pdf); [Open Exam Prep UCITS guide](https://open-exam-prep.com/study-guides/cisi-icwim/collective-investment-schemes/ucits-and-aifmd-regimes).
- Scaling all bets proportionally to fit a total cap is a recognised but "less optimal" shortcut versus jointly optimising under the cap. Source: [penaltyblog docs](https://penaltyblog.readthedocs.io/en/latest/betting/bet_size.html).
- Directly constraining drawdown probability yields better growth than uniformly scaling Kelly (0.047 vs 0.035 at the same 10% risk of a 30% drawdown). Source: [Busseti et al. 2016](https://web.stanford.edu/~boyd/papers/pdf/kelly.pdf).

### Inferences
(Numbers from the project's own model in Q5: 93¢ contracts, latent one-factor correlation calibrated to P(lose | other lost) = 0.36.)
- **The implied Kelly multiple of the 3%/20% rule.** Equal-edge case, p = 0.95 (2¢ edge). Correlated-Kelly window totals are 28.6% (n = 1), 47.8% (n = 3), 55.1% (n = 5), 60.1% (n = 8) and 62.0% (n = 10). The rule's totals are 3%, 9%, 15%, 20% and 20%. That is **0.10×, 0.19×, 0.27×, 0.33× and 0.32× Kelly**, so the effective risk appetite triples as the window fills.
- **What "consistent fractional Kelly" would look like.** Fix one multiple λ and set the window total to λ × correlated-Kelly total(n). Then:
  - If 3% is right for a lone bet (λ ≈ 0.105), a full 10-bet window should total only ~6.5% (~0.65% each).
  - If 20% is right for a full window (λ ≈ 0.32), a lone bet deserves ~9%.
  
  Which λ is right is a risk-preference call; the current rule mixes both.
- **A simple closed-form replacement for "÷ n".** In the deep-fractional regime, per-bet size ≈ (lone-bet size) / (1 + (n − 1)ρ), with ρ the binary (phi) correlation ≈ 0.33. The divisor is 1.33 at n = 2, 1.66 at n = 3, 2.3 at n = 5 and 4.0 at n = 10, versus n itself under "÷ n". The exact correlated-Kelly ratios from the model are a bit smaller: the per-bet Kelly at n = 10 is 0.22× the lone-bet Kelly versus 1/4.0 = 0.25. So the formula is a slightly generous approximation.
- **"Size the window as one bet at its Kelly fraction under correlation."** This is exactly the joint-Kelly total from the Q5 model, scaled by λ. It is sound. Its advantage over a fixed 20% sum cap is that the window total responds to n and ρ.
- **Splitting within the window.** With unequal edges, "20% ÷ n" wastes growth. In the heterogeneous example (Q5) the growth-optimal allocation under 3%/20% caps is 3% on the six best, 2% on the seventh and 0 on the three weakest. It earns **+27% more log growth per window than equal 2% stakes**, with similar tail risk. Kelly-proportional scaling to 20% recovers about 70% of that gain.
- **Metals and energy.** If they are roughly independent of crypto, they deserve their own budget. Under joint Kelly their stakes barely change when crypto bets are added, and vice versa.

### Gaps
- The model assumes a single exchangeable crypto factor. In reality BTC/ETH probably co-move more tightly than BTC/DOGE, and correlation probably rises in volatile windows. Both would push the correct per-bet sizes in full windows lower than shown.
- No source gives a "correct" fractional-Kelly λ for this bettor; that depends on drawdown tolerance (RCK makes it explicit via α, β).

## 5. The sizes themselves: worked numbers for many correlated small-edge binary bets

### Takeaway
For 90-95¢ favourites with 2-3¢ of true edge, full Kelly is enormous: 29-43% of bankroll on a lone bet, and 55-81% for a 5-10-bet correlated window. So the 3%/20% caps are already deep fractional Kelly (roughly 0.07-0.33×). Correlation at the project's measured level cuts the Kelly window total by roughly 25-45% versus independence, more as n grows (independent Kelly hits the 100% cash limit by n ≈ 3-5). Per-bet Kelly falls about 4.6-5.3× from 1 to 10 bets. Within a capped window, concentrating on the best edges beats equal splitting.

### Cited findings
- Published worked numbers for *many* correlated binary bets are scarce. Medo et al. (Fig. 1) plot m_ef vs C for M = 10 binary bets at p = 0.60 and 0.70 against the analytical curve m_ef = 10/(1 + 9C). That curve gives 10 at C = 0, ≈ 3.6 at C = 0.2 and ≈ 2.2 at C = 0.4, and the numerical Kelly results track it at p = 0.60. Source: [Medo et al. 2009](https://arxiv.org/pdf/0805.3397)
- Busseti et al.: 19 risky bets with full Kelly gave growth 0.062 per period with a 39.7% chance of a 30% drawdown within 100 periods, versus RCK with 0.047 growth and 9.9% risk. Source: [Busseti et al. 2016](https://web.stanford.edu/~boyd/papers/pdf/kelly.pdf)
- Thorp: two bets with correlation 1 get m/2 each; uncorrelated, m/(1 + m²) each. Source: [Thorp 2006](https://www.gwern.net/doc/statistics/decision/2006-thorp.pdf)
- penaltyblog's joint-Kelly example on three mutually exclusive outcomes (odds 2.5/3.2/2.8, p = 0.55/0.25/0.20) stakes 27.17%, 3.26% and 0%, a 30.43% total. Source: [penaltyblog docs](https://penaltyblog.readthedocs.io/en/latest/betting/bet_size.html)

### Inferences
These are **the project's own calculations**, not from a source. They are illustrative, not the bot's live edge.

**Model.** n contracts bought at c = 0.93 (net odds b = 0.0753), true win probability p. The dependence is a one-factor Gaussian copula: latent correlation 0.663 (p = 0.95) or 0.688 (p = 0.96), calibrated so that P(another loses | one lost) = 0.36, which equals phi ≈ 0.33. Kelly maximises E log wealth over the exact loss-count distribution, with no leverage (total ≤ 100%). A beta-binomial model with the same marginal and the same 36% pairwise statistic gave Kelly sizes within ~3% of the Gaussian copula's (e.g. n = 10, p = 0.95: 6.32% vs 6.20% per bet). In this case the pairwise statistic pins down most of the answer.

**Equal edges, p = 0.95 (2¢ edge; lone-bet Kelly f₁ = 28.6%)**

| n | Kelly/bet, independent | Kelly/bet, correlated | Kelly window total, correlated | m_ef (Medo) | 3%/20% rule total | rule as × Kelly |
|---|---|---|---|---|---|---|
| 1 | 28.6% | 28.6% | 28.6% | 1.00 | 3% | 0.10 |
| 2 | 28.2% | 20.5% | 41.0% | 1.51 | 6% | 0.15 |
| 3 | 27.8% | 15.9% | 47.8% | 1.82 | 9% | 0.19 |
| 5 | 20.0%* | 11.0% | 55.1% | 2.17 | 15% | 0.27 |
| 8 | 12.5%* | 7.5% | 60.1% | 2.44 | 20% | 0.33 |
| 10 | 10.0%* | 6.2% | 62.0% | 2.54 | 20% | 0.32 |

\*Bound by the 100% cash limit.

At p = 0.96 (3¢ edge, f₁ = 42.9%), the correlated Kelly per bet is 29.4% / 22.2% / 14.9% / 9.9% / 8.1% for n = 2 / 3 / 5 / 8 / 10, with window totals 59% / 67% / 74% / 80% / 81%. The 3%/20% rule is then 0.07× Kelly at n = 1 and 0.25× at n = 10.

**Growth per window at n = 10, p = 0.95 (expected log growth ×10⁻⁴):** full correlated Kelly 77.6; 3% each uncapped (30% total) 53.4; 3%/20% rule (2% each) 38.3. The rule keeps ~49% of the maximum growth. That matches the fractional-Kelly rule of thumb growth ≈ (2λ − λ²) × max at λ ≈ 0.32, which predicts 54%. Assuming independence instead of the true correlation would set the window at the 100% cash limit, more than 1.6× the correlated Kelly total. That is overbetting, which Thorp and Medo both flag as the costly direction.

**Loss clustering implied by the 36% figure (n = 10, p = 0.95):** P(0 losses) = 0.80 correlated vs 0.60 independent; P(≥ 5 of 10 lose) = 3.1% correlated vs 0.006% independent. Losses arrive in bunches, so the per-window loss distribution, not the per-bet one, drives drawdowns.

**Unequal edges, 10 contracts at 93¢, edges 3.0, 2.8, 2.5, 2.3, 2.0, 1.8, 1.5, 1.3, 1.0, 0.5¢ (same copula):**

| Allocation | Stakes (best → worst edge) | Total | Log growth/window ×10⁻⁴ | P(window loss ≥ 15%) |
|---|---|---|---|---|
| Correlated joint Kelly | 24.7, 19.7, 12.6, 8.1, 1.6, 0, 0, 0, 0, 0 % | 66.8% | 119.6 | 7.3% |
| Half correlated Kelly | half of above | 33.4% | 82.7 | 3.0% |
| 3% each (no sum cap) | 3% × 10 | 30% | 49.1 | 2.2% |
| **Growth-optimal under 3%/20% caps** | 3, 3, 3, 3, 3, 3, 2, 0, 0, 0 % | 20% | **44.9** | 0.72% |
| Kelly-proportional scaled to 20% | ∝ lone-bet Kelly | 20% | 42.3 | 0.78% |
| Equal split (20% ÷ 10) | 2% × 10 | 20% | 35.4 | 0.87% |

(Independent joint Kelly, for contrast, stakes 27.3 / 23.7 / 18.3 / 14.8 / 9.4 / 5.9 / 0.6 / 0 / 0 / 0%, which hits the 100% cash limit.)

**Takeaways from the numbers:**
1. Correlation drops the weakest half of the cluster from the Kelly portfolio entirely.
2. Under the existing caps, "fill the best edges first" beats "÷ n" by ~27% in growth with lower tail risk.
3. Everything hinges on the edge ranking being right. If the low-edge contracts' edges are overstated, dropping them helps even more; if the ranking is noise, equal split is the safer default.

### Gaps
- No published source gives worked Kelly sizes for ~10 correlated short-odds binary contracts. The tables above are the project's model output and depend on the assumed edges (2-3¢), the single-factor exchangeable structure and the 36% co-loss figure.
- Multi-window drawdown probabilities (e.g. the chance of a 30% drawdown over a month of 96 windows a day) were not simulated. The RCK formulation (Q2) is the principled way to set the caps to a target such as "P(ever down 30%) < 10%".
- The effect of edge-estimation error (Bayesian/shrunk edges) on the optimal within-window allocation was not quantified.
