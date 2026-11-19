# Liquidity-aware position sizing: participation limits, capacity, and adverse selection on fills

## 1. Participation and depth limits: what traders cap, and what impact models imply for small, thin books

### Takeaway
Participation caps are rules of thumb, not theory. Common defaults run 2-20% of volume: 10% is the usual target and 20% a typical hard cap. Backtest engines shrink "available volume" more over longer bars: 2% of a daily bar, 20% of a minute bar, 50% of a second bar or of top-of-book. Square-root and Almgren-Chriss impact models were fitted on continuous equity markets, at metaorder sizes (one large order split into many child orders) of about 0.1-10% of daily volume. For a one-shot IOC into a discrete prediction-market price ladder, the "impact function" is simply the visible ladder. So the working rule is to size against displayed depth at your limit price, not against your bankroll.

### Cited findings
**Participation rules of thumb (equities/brokers)**
- Interactive Brokers' percentage-of-volume (POV) algo uses a 10% participation target as its worked example, with a 1% floor and a 20% maximum ("setting the Maximum Target percentage to 20% would cap the sell order to never be more than 20%"). Source: [IBKR Campus, Price-Variant POV](https://www.interactivebrokers.com/campus/trading-lessons/price-variant-percentage-of-volume/)
- Execution-algo patent text gives 20% participation as an example optimum for one class of order profiles. It treats orders above 15% of average daily volume (ADV) as high-risk, executed with a minimum participation rate of 10%. Very small orders (under 0.01% of ADV) get a 2% minimum rate "to avoid unnecessary execution delays." These are one system's design choices, not an industry standard. Source: [US Patent 8296221](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/8296221)
- QuantConnect's LEAN backtester defines capacity as "how much capital a strategy can trade before the performance of the strategy degrades from market impact." It treats only a fraction of bar volume as available to the strategy: **2% of daily, 5% of hourly, 20% of minute, 50% of second/tick volume**. For crypto it uses the **average size at the best bid and ask**. It also applies a "fast-trading" discount (floored at 0.2) to repeated orders in the same security. Source: [QuantConnect docs, Capacity](https://www.quantconnect.com/docs/v2/lean-engine/statistics/capacity) (page undated)
- A practitioner HF-crypto study (pseudonymous Substack, Sep 30 2026) concludes: "Size orders against the book, not the account." On Binance, its net taker edge falls with size: **+2.8 bps at $1K, +2.7 bps at $10K, +1.7 bps at $100K**. On Hyperliquid, where spreads are 2-6 bps and books thin, "even $1K was negative." Capacity "depends on L2 depth at signal time." Source: [The Microstructure Lab, 2026](https://themicrostructurelab.substack.com/p/execution-simulation-for-hf-directional)
- A practitioner Polymarket-bot guide advises: "Treat quoted liquidity depth as a direct input into your Kelly fraction." If the book can't absorb the Kelly stake within a slippage tolerance, cut the position to what the book supports rather than spreading the full size across levels. A worse fill shrinks the payoff ratio *b* in the Kelly formula. Low authority (blog). Source: [casatrick Substack](https://casatrick.substack.com/p/polymarket-bot-position-sizing-kelly-criterion)

**Impact models**
- **Square-root law**: the average impact of a metaorder of total size Q scales as √Q. It is roughly independent of how many child orders it is split into and of execution time, "provided the participation rate is not too large." Source: [Bouchaud, Substack, Dec 2024](https://bouchaud.substack.com/p/the-square-root-law-of-market-impact)
- Bouchaud's 2018 slides note that strict √ impact is a large-participation result, while most empirical data covers Q/V ≈ 0.1-10% of daily volume. Source: [Bouchaud, FIPS 2018 slides](https://www.ma.imperial.ac.uk/~ajacquie/FIPS2018/Slides/LondonFIPS2018%20-%20Bouchaud.pdf)
- Durin, Rosenbaum & Szymanski (2023) separate "two square-root laws." Impact grows as √(executed volume) at a fixed participation rate. For a given volume, impact grows as √(participation rate γ) when γ is large. Smaller participation rates give a more linear dependence. Source: [arXiv 2311.18283](https://arxiv.org/pdf/2311.18283)
- Tóth et al. (2011, *Physical Review X*): the order book is V-shaped near the price. That "anomalously small local liquidity" breaks linear response and gives a "diverging impact of small orders," which is their explanation for the √ law. Source: [arXiv 1105.1694](https://arxiv.org/abs/1105.1694)
- Zarinelli, Treccani, Farmer & Lillo (2014): the √ formula fits well across only about two orders of magnitude of order size, and a logarithmic form fits better. Source: [arXiv 1412.2152](https://arxiv.org/pdf/1412.2152)
- **Almgren-Chriss** (Journal of Risk, usually cited as 2000; the DOI string reads 2001): impact is linear in trading rate and split into *temporary impact* (a per-trade liquidity cost that doesn't persist) and *permanent impact* (a lasting shift in the equilibrium price). Optimal schedules trade off expected cost against price-risk variance along an efficient frontier, which can be built explicitly under the linear model. Sources: [Wikipedia: Almgren-Chriss model](https://en.wikipedia.org/wiki/Almgren%E2%80%93Chriss_model); [DOI 10.21314/JOR.2001.041](https://www.doi.org/10.21314/JOR.2001.041)
- A Kelly-based CTA paper states the impact exponent is "normally a number around 0.5 depending on asset class and country." Source: [arXiv 1610.10029](https://arxiv.org/pdf/1610.10029)
- Kyle (1985): in the insider-trading auction model, price impact is linear in net order flow. The slope ("Kyle's lambda") is the inverse of market depth. Source: [Kyle 1985, Econometrica (JSTOR)](https://www.jstor.org/stable/1913210)

**Prediction-market depth shape**
- Polymarket (Dubach 2026, 600 markets over 52 days of tick data): top-of-book depth is a median **13.7% of top-10-level depth** (p10 3.3%, p90 42.8%). The profile looks closer to a uniform geometric grid than a top-heavy book. Median quoted spread is **222 bps (~2¢) at 0.80-0.90** and **53 bps at 0.90-1.00**, though the latter bin has only 4 markets. Depth falls only mildly toward resolution: about 6% less per tenfold reduction in time to close, with controls. Source: [arXiv 2604.24366](https://arxiv.org/html/2604.24366v1)
- For contrast, a constant-product AMM has slippage linear in size: 0.64% at $10K, 6.4% at $100K, 64% at $1M. A strategy can be profitable small and unprofitable large. Source: [arXiv 2603.29751](https://arxiv.org/pdf/2603.29751)

### Inferences
- A 15-minute binary with a fixed entry minute leaves almost no time to slice an order. Slicing over time is the main lever in Almgren-Chriss and POV algos, so those frameworks mostly don't apply. The cost of *n* contracts is just the sum over the ladder levels you consume: the ladder *is* the impact function, observed directly, with no need to estimate it from a √ law.
- An IOC's hard ceiling is 100% of displayed depth at or better than your limit price; anything beyond that is cancelled. The equity "≤10-20% of volume" rules exist to limit *permanent* impact on your own later child orders. A one-shot bet has no later child orders, so the binding cost is the *information content* of what you fill (Section 3), not permanent impact.
- QuantConnect's crypto treatment (capacity = average size at the best bid/ask) is the closest published default to the prediction-market case. It implies a baseline cap of roughly "average touch size" per order. A 60% fill ratio at the best ask says orders currently exceed that touch size about 40% of the time.

### Gaps
- No published participation-rate rule found for prediction markets or betting exchanges specifically (e.g. "≤X% of top-of-book").
- No fitted square-root/impact parameters for Kalshi or Polymarket. Dubach (2026) reports depth ratios but not dollar depth.
- The prefactor *Y* and σ-scaling of the √ law weren't extracted from primary text (the Bouchaud post omits them).

---

## 2. Capacity: how it is estimated, how professionals see profit stop scaling, and "capacity-constrained Kelly"

### Takeaway
Practitioners estimate capacity empirically. They re-run the backtest with size-dependent costs at rising capital levels and find where net Sharpe or dollar P&L peaks ("soft" capacity) and where net edge hits zero ("hard" capacity). No paper titled or formalised as "capacity-constrained Kelly" turned up. The standard treatment is to cap each stake at min(Kelly stake, what the book supports). Because log-growth is concave in the bet fraction, a binding cap just means betting below Kelly, which is safe. The closest formal literature is pari-mutuel Kelly with the "own-bet effect" (Isaacs 1953; Hausch-Ziemba), where your stake worsens your own odds.

### Cited findings
- Capacity estimation via backtest: simulate while "incrementally increasing trade sizes," with spread and depth assumptions, and find where returns deteriorate. *Soft capacity* is where performance starts declining but the strategy is still viable; *hard capacity* is where it shouldn't be deployed. Illustration: Sharpe 5 at $1M, 3 at $5M, 1 at $50M. Source: [DayTrading.com, updated Feb 2026](https://daytrading.com/trading-strategy-capacity)
- Concretum Group's procedure: run the strategy at reference AUMs of $10K, $20K, $50K, $100K, $500K and $1M with an I-Star impact model (a₁ = 708, a₂ = 0.55, a₃ = 0.71), and track net Sharpe. Capacity has three regions: a lower bound where fees dominate (~$20K), an **ideal AUM where net Sharpe peaks ($50K)**, and an upper bound where slippage needs better execution (~$100K). Splitting each order into 4 sub-orders, assumed to fill at the same price, raised the Sharpe-maximising AUM 10× to $500K. Source: [Concretum, 2025-26](https://concretumgroup.com/estimating-the-capacity-of-a-trading-strategy/)
- Frazzini, Israel & Moskowitz, "Trading Costs" (2018) used $1.7 trillion of live AQR executions across 21 markets over 19 years. Real costs were "an order of magnitude smaller" than prior estimates. They compute the fund size at which costs fully erode each anomaly's return (break-even capacity). Value and momentum scale better than size; short-term reversal is the most cost-constrained. Source: [SSRN 3229719](https://papers.ssrn.com/abstract=3229719)
- QuantConnect computes capacity from weekly snapshots: (available market dollar volume / number of trades) divided by the strategy's share of sales or buying power. The least-liquid security sets the value, then it is smoothed 0.66/0.33 across weeks. Source: [QuantConnect docs](https://www.quantconnect.com/docs/v2/lean-engine/statistics/capacity)
- One trader's anecdote: scalping strategies that worked at about 5 contracts "collapse north of 30 contracts" as cumulative execution costs erased the edge. Source: [Ryan Wright, Substack](https://ryanswright.substack.com/p/why-most-traders-fail-to-scale-their)
- MacLean, Thorp & Ziemba (2010), "Good and bad properties of the Kelly criterion":
  - In continuous time, betting exactly **2× Kelly gives zero growth** (just the risk-free rate). "It never pays to bet more than the Kelly strategy because then risk increases… and growth decreases."
  - "Long term growth maximizing investors should bet Kelly or less." Fractional Kelly is "simply a blend of Kelly and cash."
  - Errors in means vs. variances vs. covariances matter in a ratio of about **20:2:1** (Chopra-Ziemba).
  - [MacLean, Thorp & Ziemba 2010 (PDF)](https://www.stat.berkeley.edu/~aldous/157/Papers/Good_Bad_Kelly.pdf)
- Pari-mutuel Kelly with own-bet effect: Isaacs (1953) "accounted for our bettor's effect on the odds" with an algorithm for optimal wagers. Hausch-Ziemba racetrack models "take our bets into account" and are solved by nonlinear programming, with regression approximations. This is the closest formal analogue to capacity-limited Kelly. Source: [Efficiency of Racetrack Betting Markets, ch. listing](https://econpapers.repec.org/bookchap/wsiwschap/9789812819192_5f0012.htm)
- Practitioner framing: Kelly "assumes you can trade whatever size you want without affecting the price." The framework "provides no mechanism for incorporating these constraints directly," so they're imposed externally via fractional Kelly or hard position limits. Source: [Quantt, 2026](https://www.quantt.co.uk/resources/kelly-criterion-explained)
- With a per-bet transaction cost, the optimal Kelly fraction is **zero below a threshold edge** and shrinks with cost above it. Source: [arXiv 1801.06737, "At What Frequency Should the Kelly Bettor Bet?"](https://arxiv.org/pdf/1801.06737)
- Binary-contract Kelly: for a contract priced *p* paying $1 with belief *q*, **f = (q − p)/(1 − p)** of capital, ignoring fees and execution. Source: [Meister, arXiv 2412.14144 (Dec 2024)](https://arxiv.org/html/2412.14144v1)

### Inferences
- **Recognising that capacity binds** (a synthesis of the methods above): dollar P&L per bet stops rising as bankroll rises; percent growth per bet falls roughly as 1/bankroll; the fill ratio (contracts filled ÷ asked) falls; average fill price drifts above the touch. Any of these says extra bankroll has stopped earning.
- **Back-of-envelope capacity.** Let D be the contracts typically fillable at a positive *net* marginal edge, c_eff the all-in price, f the Kelly fraction actually used (fractional Kelly), and B the bankroll. Then **B_cap ≈ D · c_eff / f**. Above B_cap, each bet's stake is depth-limited and dollar P&L per bet ≈ D × (net edge per contract), independent of B. Illustrative only: D = 100, c_eff = $0.925, f = 0.077 (half of 0.154) gives B_cap ≈ $1,200.
- **Capped Kelly is still growth-optimal for that bet.** Expected log-growth is concave in f and increasing for f < f*. If the book caps the stake below f*·B, the best feasible stake is the cap. That gives no reason to *raise* the fraction elsewhere. For independent sequential bets, each bet's growth contribution is separate, so a binding cap on one bet doesn't call for overbetting the next.

### Gaps
- No source found for a formal "capacity-constrained Kelly" theorem beyond the pari-mutuel own-bet literature. The Isaacs/Levin closed forms weren't retrieved.
- Robot Wealth, Quantocracy and Ernie Chan capacity write-ups weren't found by search. Chan's *Quantitative Trading* discusses capacity, but no specific formula or number was retrieved.
- The Frazzini-Israel-Moskowitz break-even fund sizes (in $) weren't retrieved.

---

## 3. Adverse selection and the winner's curse on fills: what the literature says, and how to discount expected edge

### Takeaway
Adverse selection on fills is well documented. Fills happen disproportionately when the trade is wrong, and missed fills are disproportionately the winners. Theory (Glosten-Milgrom, Kyle) explains why quotes are priced to break even against informed flow. Empirics (Handa-Schwartz, Linnainmaa 2010, DeLise 2024, practitioner markouts, meaning returns measured just after a fill) show fill-conditional returns are worse than unconditional ones. The fix for sizing is to compute edge, and so Kelly, from the **fill-weighted** win rate (P(win | filled), weighted by contracts filled), not from the signal's overall win rate. At high contract prices Kelly is extremely sensitive to that rate.

### Cited findings
**Theory**
- Glosten & Milgrom (1985, *JFE* 14:71-100): traders with superior information produce a positive bid-ask spread even when the market maker is risk-neutral and earns zero expected profit. Transaction prices convey information, and how much of the spread reflects adverse selection shapes price dynamics. Source: [Glosten & Milgrom 1985 (PDF)](https://www.edegan.com/pdfs/Glosten%20Milgrom%20%281985%29%20-%20Bid%20Ask%20and%20Transaction%20Prices%20in%20a%20Specialist%20Market%20with%20Heterogeneously%20Informed%20Trades.pdf)
- Kyle (1985): informed traders hide in noise flow; prices move linearly with net order flow (lambda). Source: [JSTOR](https://www.jstor.org/stable/1913210)
- Limit-order design: *non-execution risk* (the opportunity cost of not filling) and *adverse selection* (being "picked off" because a resting order gives others an option to trade at a fixed price) pull in opposite directions. A more aggressive price reduces non-execution but raises adverse selection, and vice versa. Source: [arXiv 1610.00261](https://arxiv.org/abs/1610.00261)
- *Picking-off risk*: an unmonitored limit order may fill after the asset's value changes; the expected loss is the picking-off risk. Source: [limit-order-market study, UPenn reading list](https://www.cis.upenn.edu/~mkearns/finread/hollifield-liquid2.pdf)
- When a patient trader learns first that their order is in-the-money, they withdraw or revise it to avoid being picked off. Liquidity that is still there when you arrive is selected on what its owner *didn't* learn. Source: [J. Financial Markets, monitoring and limit-order risk](https://www.sciencedirect.com/science/article/abs/pii/S1386418108000207)
- A CEPR paper's framing (per search snippet; full text returned HTTP 403): "limit orders may be exposed to adverse selection, which we refer to as winner's curse." Source: [CEPR DP 2843](https://repec.cepr.org/repec/cpr/ceprdp/Dp2843.pdf)

**Empirics**
- Linnainmaa (2010, *Journal of Finance*), using all Finnish individual investors: poor post-trade returns, the disposition effect and contrarian trading "can be explained in large part by investors' use of limit orders," because limit orders "are price-contingent and suffer from adverse selection." Source: [IDEAS/RePEc](https://ideas.repec.org/a/bla/jfinan/v65y2010i4p1473-1506.html)
- Using NYSE TAQ/TORQ data: filled limit orders "suffer from adverse selection costs," and **unfilled limit orders have positive opportunity costs**, matching Handa & Schwartz (1996). This is a secondary source (patent text). Source: [US Patent 6493682](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/6493682)
- DeLise (2024), "The Negative Drift of a Limit Order Fill": fills are "costly and non-random," occurring during adverse price moves. Shown with a theoretical proof and a 10-year Treasury futures simulation. The effect size wasn't in the abstract. Source: [arXiv 2407.16527](https://arxiv.org/abs/2407.16527)
- Practitioner markouts (Binance): taker returns on signals where a passive order **would NOT have filled: +4.9 bps**; where it **would have filled: −4.3 bps**. "The fills that happen are the ones where your signal was wrong." Passive fill rates were 8-25%. Backtests that assume mid-to-mid execution with maker fees overstate P&L by an estimated **5-25 bps per trade**. Source: [The Microstructure Lab, 2026](https://themicrostructurelab.substack.com/p/execution-simulation-for-hf-directional)

**Prediction markets**
- Kalshi (Bürgi, Deng & Whelan, Jan 2026; 46,282 contracts, 2021-Apr 2025):
  - Average return was **−9.64% for Makers vs −31.46% for Takers**.
  - Makers buying contracts at **≥50¢ earned +2.6%** on average.
  - Contracts above 70¢ show "statistically significant, though small, positive post-fee returns." A 95¢ contract that wins 98% of the time returns +3.1% before fees.
  - Makers "must also be willing to cancel those orders if new evidence emerges."
  - [Kalshi paper (PDF)](https://www.karlwhelan.com/Papers/Kalshi.pdf); [SSRN 5502658](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5502658)
- Polymarket (Dubach 2026): a Glosten-Harris decomposition gives a median adverse-selection component of about **0** once on-chain trade directions are used. Feed-inferred directions match on-chain ground truth only about 59% of the time, and that sign error created "spurious adverse selection." Measured adverse selection is very sensitive to how trade direction is classified. Source: [arXiv 2604.24366](https://arxiv.org/html/2604.24366v1)
- Qin & Yang (Jun 2026): higher toxic-flow measures go with worse forecast calibration (higher Brier scores) on Polymarket. Spread-estimator choice materially changes estimated cost effects. Source: [arXiv 2606.04217](https://arxiv.org/html/2606.04217v1)

### Inferences
- **Why an IOC taker is adversely selected even though it "takes."** In Glosten-Milgrom the quoted ask already equals E[value | a buy arrives]. Your fill is conditioned on more than that: the size *still resting* when your order lands. When faster or better-informed traders saw the same opportunity, they cleared the level first, and you get a partial fill on the best bets. When nobody else wanted it, the level is intact, and you get a full fill on the worst bets. This matches the case described (unfilled contracts win more often).
- **How to discount edge (formulas derived here).**
  - Use the contract-weighted fill-conditional win rate: p_F = Σ(filled_i × win_i) / Σ filled_i.
  - If only the overall win rate p̄ (all orders as if fully filled), the fill share φ and the win rate of the unfilled portion p_U are known: p_F = (p̄ − (1−φ)·p_U) / φ.
  - Net edge per contract = p_F − c − fee(c), and Kelly f* = (p_F − c_eff)/(1 − c_eff), with c_eff = price + fee.
- **Sensitivity at favourite prices.** df*/dp = 1/(1 − c_eff), about 13 at a 92¢ price including fee. Each 1 pp error in the win rate moves the Kelly fraction about 13 pp of bankroll.
- **Worked example** (illustrative numbers; taker fee 0.07·P·(1−P) ≈ 0.52¢ at 92¢):
  - With p̄ = 0.95, φ = 0.6 and p_U = 0.97, p_F = 0.937.
  - Kelly falls from **0.33** (using 0.95) to **0.15** (using 0.937): a 2 pp gap between unfilled and average win rates cuts Kelly by more than half.
  - At 93¢ the same p_F leaves f* ≈ 0.03, nearly zero.
- Kalshi's maker-vs-taker return gap is evidence that *who provides liquidity matters*. It mixes fee and selection effects, so it isn't a clean estimate of taker adverse selection on short-dated crypto binaries.

### Gaps
- No published study of fill-conditional returns for IOC taker orders on Kalshi or Polymarket specifically. The Polymarket "≈0 adverse selection" result is for trade-level decomposition on the top-100 markets, not for latency-sensitive short-dated contracts.
- Harris (*Trading and Exchanges*) and O'Hara (*Market Microstructure Theory*) passages on limit orders as free options weren't retrieved.
- Budish-Cramton-Shim (2015) on stale-quote sniping is relevant to latency-driven fill selection but wasn't verified in this pass.
- The CEPR DP 2843 full text was inaccessible (403), so its authors and findings are unverified.

---

## 4. Order types: how takers and makers on prediction markets and sports exchanges handle thin books (IOC vs resting, "limit +1 tick", splitting)

### Takeaway
All three venues offer the same building blocks: Kalshi's IOC/FOK/GTC, Polymarket's FAK/FOK/GTC, and Betfair's FILL_OR_KILL with minFillSize. Betfair's design is notable: its FOK limit price caps the **volume-weighted average price** across levels walked, which is a built-in "walk the book but cap the average" order. For short-horizon edges, practitioner evidence favours taking (IOC/FAK) over resting: resting orders are adversely selected and decay alpha while they wait. "Limit +1 tick" should be judged as a separate, lower-edge tranche with its own Kelly fraction.

### Cited findings
**Kalshi**
- `time_in_force` ∈ {`fill_or_kill`, `good_till_canceled`, `immediate_or_cancel`}. For IOC, `remaining_count` "reflects the final state after unfilled contracts are canceled," and `fill_count` reports immediate fills. IOC can't be combined with `expiration_time`. `reduce_only` requires IOC. The spec doesn't describe FOK semantics or `post_only` in detail. Source: [Kalshi API, Create Order v2](https://docs.kalshi.com/api-reference/orders/create-order-v2.md)
- Fees: the taker fee is **$0.07 × C × P × (1−P)**, rounded up to the cent per order. Kalshi began charging Makers after April 2025. Source: [Bürgi, Deng & Whelan 2026](https://www.karlwhelan.com/Papers/Kalshi.pdf). The maker rate is **0.0175** (25% of taker). Source: [River Markets](https://www.rivermarkets.com/insights/kalshi-fees.html). Sources conflict on whether some categories (e.g. sports) have lower rates. Source: [botforkalshi](https://www.botforkalshi.com/blog/kalshi-fees-explained)
- Kalshi is quote-driven in practice: "All trades are offered by Makers and accepted by Takers." There were no institutionalised market makers in the IEM sense. Source: [Bürgi, Deng & Whelan 2026](https://www.karlwhelan.com/Papers/Kalshi.pdf). However, Susquehanna became Kalshi's first committed institutional market maker in April 2024. Source: [Business Wire, 2024](https://www.businesswire.com/news/home/20240403664852/en/Kalshi-Onboards-Its-First-Dedicated-Institutional-Market-Maker)
- Market-maker program terms: in designated contracts and hours, participants must quote continuous two-sided markets, keep maximum spreads and meet minimum quote sizes, in exchange for reduced fees and adjusted position limits. These terms ran Mar 11 2024 to Mar 11 2026 unless extended. Sources: [CFTC filing](https://www.cftc.gov/filings/orgrules/rules02262412176.pdf); [Kalshi help](https://help.kalshi.com/en/articles/13823819-how-to-become-a-market-maker-on-kalshi)

**Polymarket**
- FOK fills entirely and immediately or cancels. FAK fills what is available immediately and cancels the rest (the IOC equivalent). GTC rests until filled or cancelled. FOK/FAK market buys are specified in dollars. Source: [Polymarket docs, Orders overview](https://docs.polymarket.com/trading/orders/overview)

**Betfair**
- `FILL_OR_KILL` with optional `minFillSize`: the order matches only if at least `minFillSize` can be matched, and any remainder is cancelled immediately. The price on a FOK order is the **lower limit of the VWAP for the entire matched volume**. Example: price 5.4, size 10 might match £2 @ 5.5, £6 @ 5.4, £2 @ 5.3. Source: [Betfair API release notes, Aug 2016](https://betfair-developer-docs.atlassian.net/wiki/spaces/1smk3cen4v3lu3yomq5qye0ni/pages/2687154)
- NautilusTrader maps IOC to Betfair `FILL_OR_KILL` with `min_fill_size=0`, allowing partial fills. Source: [NautilusTrader docs](https://nautilustrader.io/docs/nightly/integrations/betfair/)
- Exchange advantage depends on liquidity: the finding that betting exchanges offer better odds than bookmakers "does not hold in illiquid markets." Source: [Flepp, Nüesch & Franck 2017](https://unifr.ch/tim/en/assets/public/uploads/Publication%20list/2017/Flepp_N%C3%BCesch_Franck_2017.pdf). An anecdotal report says that as liquidity fell, Australian racing markets on Betfair became worth betting into only in the final minutes. Source: [Asian Racing Report](https://asianracingreport.com/exchanging-fortunes-does-betfair-have-a-retail-future-in-australia/)

**Taker vs passive, and splitting**
- "If gross alpha is within about 2× the typical spread, taker execution is marginal and passive execution is likely to be adversely selected." Passive patience was capped at 5 s because 64% of alpha had materialised by then; longer patience did worse. TWAP and implementation-shortfall slicing were negative on every coin tested. Source: [The Microstructure Lab, 2026](https://themicrostructurelab.substack.com/p/execution-simulation-for-hf-directional)
- Splitting into 4 sub-orders raised the ideal AUM 10× in Concretum's equity test. That assumed each sub-order fills at the same price, which is optimistic. Source: [Concretum](https://concretumgroup.com/estimating-the-capacity-of-a-trading-strategy/)
- Polymarket NBA markets: median bid-ask spreads widen from pre-game to in-game to post-game. Source: [arXiv 2605.00864](https://arxiv.org/html/2605.00864v1)

### Inferences
- **"Limit +1¢" as a tranche decision.** An IOC priced at ask+1¢ on a price-time-priority book should fill the ask level first and then the +1¢ level. That is standard CLOB matching; the Kalshi spec excerpt doesn't state it explicitly. The +1¢ contracts are a different bet: a higher price, so lower edge, and possibly a different fill-conditional win rate. Worked numbers, illustrative with p = 0.95 and taker fees:
  - Net edge falls from ≈2.48¢ at 92¢ to ≈1.54¢ at 93¢ (−38%).
  - Tranche Kelly falls from 0.33 to 0.24.
  - Take the +1¢ level only if *its own* fill-conditional win rate clears c_eff ≈ 0.935 with margin.
- A Betfair-style VWAP cap is the cleanest way to express "walk the book, but only while the average stays edge-positive." On Kalshi or Polymarket it has to be replicated client-side: compute the ladder VWAP from the snapshot and set the IOC size and limit accordingly.
- **Resting the unfilled remainder.** Kalshi's maker fee is a quarter of the taker fee (≈0.13¢ vs ≈0.52¢ at 92¢), but resting on a short-dated binary near your decision time invites picking-off. Evidence from Sections 3-4 says passive fills come mostly when price moves against you, so the remainder's fee saving is likely outweighed unless measured otherwise.
- **Splitting across time** within a short fixed window trades a smaller per-clip impact for alpha decay and re-exposure to selection. It helps only if depth refills faster than the edge decays.

### Gaps
- No Kalshi or Polymarket doc found that states the price-improvement matching rule for a marketable IOC limit explicitly. Kalshi's FOK and `post_only` semantics aren't documented in the spec excerpt.
- No Betfair study with numeric depth-at-best statistics for favourites was found. Whelan's Betfair order-book paper exists but wasn't mined. Source: [Whelan, Betfair paper](https://www.karlwhelan.com/Papers/Betfair.pdf)
- No public data on Kalshi crypto 15-minute market depth at the touch, or on how quickly depth refills after a sweep.

---

## 5. Bankroll vs capacity: keep the fraction low when capacity binds?

### Takeaway
Yes. Kelly theory and the order-book evidence support (a) never exceeding the Kelly fraction computed on the **fill-conditional, net-of-fee** edge, (b) taking the depth cap when it binds and *not* raising the fraction to compensate, and (c) recognising that bigger orders add size mainly in deep-book states. Under adverse selection, deep-book states are disproportionately the losing ones, so the marginal contract's edge is below the average fill's. Fractional Kelly (≤½) is the standard hedge against the large estimation error in p_F at favourite prices.

### Cited findings
- "It never pays to bet more than the Kelly strategy because then risk increases… and growth decreases." 2× Kelly gives zero excess growth, and Kelly or less is the rule for growth-maximisers. Errors in the mean (edge) matter about 10-20× more than errors in variance. Source: [MacLean, Thorp & Ziemba 2010](https://www.stat.berkeley.edu/~aldous/157/Papers/Good_Bad_Kelly.pdf)
- With transaction costs, the optimal fraction is zero below a threshold edge and shrinks above it. Source: [arXiv 1801.06737](https://arxiv.org/pdf/1801.06737). With proportional costs, the growth-optimal policy has a no-trade band around the frictionless fraction. Source: [arXiv 1611.01280](https://arxiv.org/pdf/1611.01280)
- Practitioners impose liquidity constraints externally through fractional Kelly or hard caps. Source: [Quantt](https://www.quantt.co.uk/resources/kelly-criterion-explained). Cut to what the book supports rather than spreading the Kelly size across levels. Source: [casatrick Substack](https://casatrick.substack.com/p/polymarket-bot-position-sizing-kelly-criterion). "Size orders against the book, not the account." Source: [The Microstructure Lab](https://themicrostructurelab.substack.com/p/execution-simulation-for-hf-directional)
- In one sports-betting study, a 0.5 Kelly coefficient was the most profitable sizing tested. This is a single student study (Wharton, 2023). Source: [Beggy 2023](https://wsb.wharton.upenn.edu/wp-content/uploads/2023/05/Beggy_2023__Betting_Kelly.pdf)
- Own-bet effect: optimal pari-mutuel wagers fall when your bet moves the odds. Source: [Isaacs 1953 / Hausch-Ziemba, chapter listing](https://econpapers.repec.org/bookchap/wsiwschap/9789812819192_5f0012.htm)

### Inferences
- **Formal version of "bigger orders only add exposure to the fills that do happen"** (derived here):
  - Order q contracts by IOC. The fill is n = min(q, D), where D is the depth at your limit, a random variable possibly correlated with the outcome.
  - With per-contract payoff X = 1{win} − c_eff, wealth after the bet is B + n·X.
  - The first-order condition for q is E[ 1{D > q} · X / (B + qX) ] = 0. **Only states where the marginal contract actually fills enter the condition.**
  - So the optimal order size uses the win rate *conditional on depth exceeding q*: q*·c_eff/B ≈ (p_{D>q} − c_eff)/(1 − c_eff).
  - Under adverse selection, p_{D>q} falls as q rises (deep books = nobody else wanted it). The optimal order is therefore *smaller* than the Kelly size computed from the average fill's win rate, and much smaller than one computed from the signal's overall win rate.
- **What to measure live** to set q:
  - Bucket bets by fill ratio (e.g. <50%, 50-99%, 100% filled) and compare contract-weighted win rates.
  - If the 100%-filled bucket wins less, its rate is the relevant p for the marginal contracts, and the order cap should sit near the depth level where that bucket's net edge goes to zero.
  - Treat the +1¢ tranche the same way, as its own bucket.
- **When capacity binds, extra bankroll should sit idle**, not be pushed into a higher fraction. Above B_cap ≈ D·c_eff/f, raising f only raises q, which by the condition above adds contracts with lower, possibly negative, edge. The growth-safe response to more bankroll is more *independent* opportunities (more markets or windows), not larger orders into the same depth.
- **Practical rule synthesised from the sources:** order size = min( k · f*(p_F, c_eff) · B / c_eff , depth up to the worst price where marginal fill-conditional edge > 0 ), with k ≈ ¼-½. Recompute p_F from live fills only, never from candle-ask backtests, which include the unfilled winners.

### Gaps
- No published empirical study found that tests "keep the fraction low when capacity binds" against alternatives. The recommendation rests on Kelly theory plus the order-book evidence above.
- Concurrent, correlated bets in the same window (several markets at once) need joint Kelly sizing. That wasn't covered here.
- No source quantifies how fill-ratio buckets map to win rates on Kalshi; this has to come from the project's own fill logs.
