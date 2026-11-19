# Firm risk limits and drawdown control: what professional practice says for a small automated bettor

Case being judged: a small automated bot (a small bankroll) that already halts on (a) a 35% fall within 24 hours, (b) loss of half its starting bankroll, (c) 3 failed orders in a row. Research date: Oct 14, 2026.

## Firm limits: what do prop and HFT firms actually use?

### Takeaway
Published prop and multi-manager limits are far tighter than the bot's: daily loss limits of about 2-5% of capital, hard account stops of about 4-10%, and a "cut size in half at about −5%, stop at about −7.5%" step-down at the best-known pod shop. HFT firms' own P&L limits are not public. What is public (FIA) is the structure: per-strategy and firm-wide position limits, automatic disabling after repeated fills, and a kill switch, all enforced before an order goes out.

### Cited findings
- **Millennium (multi-manager "pod" fund), reported rule:** "Millennium portfolio managers who lose 5% of the capital allocated to them typically have their capital halved. If they lose another 2.5%, they're usually fired." eFinancialCareers (Dec 5, 2025) attributes this to a WSJ report from 2025, and the fund did not confirm it. Source: [eFinancialCareers, 2025](https://www.efinancialcareers.com/news/pratik-madhvani-glen-scheinberg)
- Other secondary accounts put Millennium's "liquidate and dismiss" level between 7.5% and 10%, or at 5-7% of allocated capital. These are less authoritative than the WSJ-based report. Sources: [Quant Enthusiasts Substack](https://youngandcalculated.substack.com/p/what-senior-pms-at-multi-managers); [Hedgeweek](https://www.hedgeweek.com/millennium-posts-rare-monthly-loss-amid-index-rebalancing-trades/)
- **FTMO (retail prop firm), official rules page:**
  - 2-Step: Maximum Daily Loss = 5% of initial capital, reset at 00:00 CE(S)T from that day's starting balance. Maximum Loss = a static 10% below initial capital (e.g., $90,000 on $100,000).
  - 1-Step: Maximum Daily Loss = 3% of initial capital. Maximum Loss = 10% trailing from the highest end-of-day balance; it can rise but never fall.
  - Both limits are measured on equity, "Balance + Open Positions P/L ± Swaps - Commissions", so open-position losses count.
  - [FTMO Trading Objectives, accessed 2026](https://ftmo.com/en/trading-objectives/)
- **Topstep (futures prop firm), $50K account:**
  - Daily Loss Limit (DLL) = $1,000 (2%). It is $2,000 on $100K and $3,000 on $150K.
  - When net P&L hits the DLL, open positions are flattened, pending orders are cancelled, and there are "no new trades until 5 PM CT next session".
  - Hitting the DLL is not a rule violation. The DLL is optional in the Combine and Express Funded Account and automatic in the Live Funded Account. Source: [Topstep Help Center, accessed 2026](https://help.topstep.com/en/articles/10490293-daily-loss-limit-in-the-trading-combine-and-express-funded-account)
  - Maximum Loss Limit = $2,000 (4%) on $50K. It trails the end-of-day balance high. Source: [TradersPost summary of Topstep rules](https://blog.traderspost.io/article/how-to-get-funded-with-topstep). Sources conflict on whether the trailing is end-of-day or intraday. Source: [propfirmsfinder](https://propfirmsfinder.com/prop-firm/topstep/)
- **FIA (futures industry body), Nov 2010, *Recommendations for Risk Controls for Trading Firms*** (Principal Traders Group, i.e. the prop/HFT firms):
  - Firms "should establish and automatically enforce pre-trade risk limits that are appropriate for the firms' capital base, clearing arrangements, trading style, experience, and risk tolerance… such as position size and order size… set at several levels of aggregation… implemented in multiple independent pre-trade components."
  - The same document also recommends price collars, a "Repeated Automated Execution Throttle" ("after a configurable number of repeated executions the system should be disabled until a human re-enables it"), an outbound message-rate limit, market-data reasonability checks, and a manual "kill button" that "disables the system's ability to trade and cancels all resting orders".
  - Under "Trading Interruptions": monitor heartbeats (periodic are-you-alive signals between components). If connectivity is lost, the system "should be disabled and working orders cancelled".
  - [FIA PTG, 2010](https://www.fia.org/sites/default/files/2020-04/Trading_Best_Pratices%20-%20published.pdf)
- **FIA (July 2024), *Best Practices for Automated Trading Risk Controls and System Safeguards*:**
  - Maximum intraday position limits are "generally set by instrument, by individual trader, group of traders and/or for the whole firm". Checks must count working orders as well as filled positions.
  - Limits should be managed by "authorized staff independent of trading activities".
  - Repeated-execution limits "should be set by the automated trader", and the strategy "should be disabled until an authorized person re-enables it".
  - [FIA, 2024](https://fia.org/sites/default/files/2024-07/FIA_WP_AUTOMATED%20TRADING%20RISK%20CONTROLS_FINAL_0.pdf)
- **Industry practice (unverified):** a search summary reported that an FIA survey found all responding FCMs (futures brokers) use some form of kill switch or other means to stop order submission. The underlying document was not opened. The likely source is the FIA presentation to the CFTC Technology Advisory Committee, 2019. Source: [CFTC TAC 2019 FIA presentation](https://cftc.gov/media/2746/TAC100319_FIA/download)

### Inferences
- The bot's 35%-in-24h halt is about 7x FTMO's 5% daily limit and about 17x Topstep's 2%. Its "half the starting bankroll" stop (50%) is about 5x FTMO's 10% maximum loss and about 7x Millennium's reported 7.5% exit. By professional standards these are catastrophe stops (last-resort shutdowns), not risk-budget limits.
- The Millennium pattern is a simple, adoptable "step-down" rule: at −X% from the high-water mark (the running equity peak), halve the stake; at −1.5X%, stop and require a human review.
- Prop "daily loss limit" mechanics worth copying: count unsettled positions at their worst-case value, flatten or cancel on breach, block new orders until the next session, and keep the daily stop separate from the account-level stop.
- The bot's "3 failed orders in a row" halt is the same kind of control as FIA's repeated-execution throttle and heartbeat/disconnect rules. FIA's version adds that a human must re-enable it, plus the companion checks the bot may lack: max order size, price collar, message rate, and stale market data.

### Gaps
- No public source gives actual intraday P&L limits (as % of capital) at HFT firms such as Jump, Citadel Securities or Virtu. These are proprietary, and FIA documents deliberately avoid numeric limits.
- Millennium figures are press-reported and unconfirmed by the firm.
- Topstep's trailing-MLL mechanics conflict across secondary sources. The Topstep MLL help article could not be opened directly.

## Regulatory frameworks: 15c3-5, CFTC and FIA practice, kill switches, Knight Capital

### Takeaway
US regulation requires automated, pre-trade, hard-blocking controls on credit/capital exposure and erroneous or duplicate orders, under the firm's direct control and reviewed at least yearly (SEC 15c3-5, 2010). The CFTC chose a principles-based route (Reg AT proposal withdrawn 2020; Electronic Trading Risk Principles for exchanges adopted Dec 2020). Knight Capital (2012, about $460M lost in 45 minutes) shows what goes wrong without an aggregate exposure check that blocks orders automatically, and when alerts don't force action.

### Cited findings
- **SEC Rule 15c3-5 (Market Access Rule), 17 CFR 240.15c3-5:**
  - (c)(1)(i): prevent the entry of orders that exceed pre-set credit or capital thresholds, in aggregate for each customer and the firm (optionally by sector or security), by rejecting them.
  - (c)(1)(ii): "Prevent the entry of erroneous orders, by rejecting orders that exceed appropriate price or size parameters, on an order-by-order basis or over a short period of time, or that indicate duplicative orders."
  - (c)(2)(iv): surveillance staff must receive immediate post-trade execution reports.
  - (e)(1): review "no less frequently than annually", under documented written procedures.
  - [LII / 17 CFR 240.15c3-5](https://www.law.cornell.edu/cfr/text/17/240.15c3-5)
- The rule was adopted in November 2010. The controls must be automated, pre-trade, and under the broker-dealer's "direct and exclusive control". "Naked" sponsored access with no pre-trade controls is prohibited. SEC staff FAQs followed in April 2014. Sources: [WilmerHale, 2014](https://www.wilmerhale.com/insights/client-alerts/sec-staff-issues-first-set-of-faqs-on-rule-15c3-5-risk-management-controls-for-brokers-or-dealers-with-market-access); [FINRA 2022 exam report](https://www.finra.org/rules-guidance/guidance/reports/2022-finras-examination-and-risk-monitoring-program/market-access-rule)
- **Knight Capital, Aug 1, 2012 (SEC order Oct 16, 2013):**
  - What happened: defective dormant code in its router was triggered by a faulty deployment. In the first 45 minutes after the open it sent "more than 4 million orders" while trying to fill 212 customer orders, traded over 397 million shares, built "several billion dollars in unwanted positions" and lost over $460 million.
  - Ignored warnings: 97 automated emails flagged the error before the open and were not acted on.
  - SEC findings: Knight's controls "could not prevent the entry of orders that exceeded the firm's pre-set aggregate capital thresholds". The receiving account was not linked to firm-wide automated exposure controls. Written incident-response procedures were inadequate. Reviews inventoried controls rather than examining risks.
  - Penalty: $12M, the first enforcement action under 15c3-5.
  - [SEC press release 2013-222](https://www.sec.gov/news/press-release/2013-222)
- **CFTC Regulation AT:**
  - Proposed 2015 and revised 2016. It would have required "AT Persons" to register and implement pre-trade risk controls, and to give the CFTC source code without a subpoena.
  - Withdrawn June 25, 2020 (3-2 vote) and replaced by a narrower principles-based proposal (85 FR 42761, July 15, 2020). Source: [Davis Polk, 2020](https://davispolk.com/insights/client-update/cftc-withdraws-reg-proposal-proposes-principles-based-electronic-trading)
- **CFTC Electronic Trading Risk Principles**, adopted Dec 8, 2020 (4-1). Designated contract markets (DCMs, i.e. CFTC-regulated exchanges) must:
  1. have rules for participants to "prevent, detect, and mitigate" disruptions and anomalies;
  2. apply exchange-based pre-trade risk controls to all electronic orders;
  3. promptly notify the CFTC of significant disruptions.
  - [CFTC Release 8331-20, 2020](https://www.cftc.gov/PressRoom/PressReleases/8331-20); [Sullivan & Cromwell, 2020](https://www.sullcrom.com/insights/memo/2020/December/2020-12-16-CFTC-Electronic-Trading-Rules)
- **FIA 2024 kill-switch design:**
  - A kill switch "immediately disables all trading activity… typically preventing the ability to enter new orders and cancelling all working orders".
  - It is a last resort: "invoked based on a qualitative decision taken as a last resort when other actions have failed", and "a final backstop for the pre-trade risk functionality".
  - Firms are "encouraged to build their own kill switch functionality into their trading applications… on a sufficiently granular level to identify individual trading systems".
  - The trader "should not be able to override a kill switch invoked by the broker". The UI should show "explicit warnings… of the consequences of activating the kill switch".
  - [FIA, 2024](https://fia.org/sites/default/files/2024-07/FIA_WP_AUTOMATED%20TRADING%20RISK%20CONTROLS_FINAL_0.pdf)
- **FIA 2024, other controls relevant to a small bot:**
  - "Systems should prevent orders from being placed in cases where no order size limits have been set". This is a fail-closed rule: no limit configured means no order.
  - A market-data reasonability check should use "time since the last update… previous price, bid/offer spread or deviation from an average price". If data looks stale, "any orders should be blocked while the deviation is investigated".
  - Use cancel-on-disconnect, and use drop-copy reconciliation (comparing your own fill records against the venue's independent copy).
  - [FIA, 2024](https://fia.org/sites/default/files/2024-07/FIA_WP_AUTOMATED%20TRADING%20RISK%20CONTROLS_FINAL_0.pdf)
- Kill switches can sit at the participant, clearing-firm or platform level, and platform switches do not replace each member firm's own controls (Citadel comment to CFTC, as summarized by FIA). Source: [FIA special report on CFTC concept release](https://fia.org/fia/articles/fia-special-report-cftc-issues-concept-release-automated-trading)

### Inferences
- 15c3-5 applies to securities broker-dealers, not to a retail Kalshi account. As a design template it maps directly onto a bot:
  - a hard aggregate-exposure cap (total open stake across all markets), checked before every order and including working orders;
  - per-order price and size bounds;
  - duplicate-order detection;
  - an automatic block rather than just an alert.
- Kalshi is itself a CFTC-designated contract market (general background knowledge, not verified here), so the 2020 Risk Principles put exchange-side pre-trade controls on it. Those protect the exchange, not the bot's bankroll.
- Knight's lessons for a one-person bot:
  - An alert that only notifies (Knight's 97 emails, or a phone push) is not a control. The breach condition must stop order flow by itself.
  - The exposure check must run independently of the strategy code path, in FIA's words "multiple independent pre-trade components".
  - Remove dead code paths, and verify the deployed version after every restart.
- A kill switch should do two things: (1) cancel all resting orders and (2) block new orders until a human re-enables trading, with a visible, deliberate reset. A halt that resumes on its own, for example after a 24-hour window rolls off, is a "pause", not a kill switch.

### Gaps
- The SEC's full Knight cease-and-desist order could not be opened (only the press release). The order's detailed timeline of when staff tried to stop the router is not captured here.
- The detailed 2015/2016 Reg AT control list (message-rate limits, order cancellation systems) is not confirmed from a primary source in these notes.

## Drawdown-control sizing theory: Grossman-Zhou, CPPI, CDaR, drawdown-adjusted Kelly

### Takeaway
Theory gives a clear answer to "how should size shrink as the account falls from its peak". Grossman-Zhou says to bet in proportion to the cushion above a floor that trails the high-water mark, so size shrinks linearly to zero as the drawdown approaches the maximum allowed. Thorp's fractional-Kelly formula and Busseti-Ryu-Boyd's risk-constrained Kelly turn "probability of ever losing X%" into a Kelly fraction. For high-priced binary contracts, the answer is roughly 0.1-0.4 of full Kelly, depending on the drawdown tolerance.

### Cited findings
- **Grossman & Zhou (1993), *Optimal Investment Strategies for Controlling Drawdowns*, Mathematical Finance 3(3):241-276:**
  - The investor wants never to lose more than a fixed % of peak wealth: W_t ≥ α·M_t, where M_t is the running maximum.
  - For CRRA (constant relative risk aversion) utility, the optimal risky allocation is proportional to the surplus W_t − α·M_t.
  - Because the floor moves with the peak, risky holdings fall as wealth nears the floor. Contrast this with CPPI's fixed floor.
  - [RePEc/IDEAS](https://ideas.repec.org/a/bla/mathfi/v3y1993i3p241-276.html)
- Later caveats on Grossman-Zhou:
  - Klass & Nowicki (2005) showed the strategy loses its optimal long-run growth property in discrete time.
  - With transaction costs it is hard to implement near the drawdown limit.
  - Cherny & Obłój showed the problem is equivalent to an unconstrained one with a modified utility.
  - [Lund University record, Klass & Nowicki](https://lup.lub.lu.se/record/223851); [ar5iv 1110.6289](https://ar5iv.arxiv.org/html/1110.6289)
- **CPPI (constant proportion portfolio insurance):** the cushion is C = max(V − F, 0), and risky exposure is E = min(m·C, V).
  - The multiplier m is conventionally set to 100 ÷ (the crash size, in %, being insured against).
  - A drop larger than 1/m between rebalances breaches the floor ("gap risk"). Typical m is 3-6 (non-authoritative).
  - Origins: Perold (1986); Black & Jones (1987); Black & Perold.
  - [Wikipedia: CPPI](https://en.wikipedia.org/wiki/Constant_proportion_portfolio_insurance)
- **Chekhlov, Uryasev & Zabarankin (2005), *Drawdown Measure in Portfolio Optimization*, IJTAF 8(1):13-58:**
  - Defines Conditional Drawdown (CDD/CDaR) as the mean of the worst (1−α)·100% drawdowns.
  - Maximum drawdown (α→1) and average drawdown (α=0) are its limiting cases.
  - First presented as CDaR in a 2003/2004 chapter.
  - [RePEc/IDEAS](https://ideas.repec.org/a/wsi/ijtafx/v08y2005i01ns0219024905002767.html); [Stevens chapter record](https://researchwith.stevens.edu/en/publications/portfolio-optimization-with-drawdown-constraints/)
  - In Palomar's portfolio-optimization text, a backtest of CDaR-type portfolios on S&P 500 stocks did not outperform the simple global-minimum-variance benchmark. Source: [Palomar, Portfolio Optimization, §10.5](https://bookdown.org/palomar/portfoliooptimizationbook/10.5-drawdown-portfolios.html)
- **Thorp (2006), "The Kelly Criterion in Blackjack, Sports Betting and the Stock Market"** (Handbook of Asset and Liability Management, ch. 9):
  - Eq. 7.13 (continuous approximation): P(wealth ever falls to fraction x of the start | bet c × Kelly) = x^(2/c − 1).
  - At full Kelly this is x, so P(ever halving) = 1/2. At half Kelly it is x³, so P(ever halving) = 1/8.
  - Half Kelly gives 3/4 of the growth rate. In general, growth relative to the maximum is c(2 − c).
  - P(doubling before halving) is 2/3 at full Kelly and 8/9 at half Kelly.
  - Thorp: "most people strongly prefer the increased safety and psychological comfort of 'half Kelly' (or some nearby value), in exchange for giving up 1/4 of their growth rate". Section 7.3 shows that half Kelly loses nothing if the true edge is only half the estimate. Thorp gives growth in units of m_e²/2s², where m_e is the estimated mean edge and s² the variance: at half Kelly growth is 0.25, the maximum possible in that case. At the estimate (true edge = estimate) half Kelly gets 0.75. Overbetting is much more harmful than underbetting. By the same quadratic, full Kelly would get zero growth if the true edge were half the estimate (arithmetic added here, not Thorp's).
  - [Thorp 2006 PDF (gwern mirror)](https://www.gwern.net/doc/statistics/decision/2006-thorp.pdf)
- **Busseti, Ryu & Boyd (2016), *Risk-Constrained Kelly Gambling*, J. Investing 25(3):**
  - Maximize E log(rᵀb) subject to P(W_min < α) < β. Example: α=0.7, β=0.1 means "probability of experiencing more than 30% drawdown is only 10%".
  - Tractable sufficient condition: E[(rᵀb)^(−λ)] ≤ 1 with λ = log β / log α, which guarantees P(W_min < α) < β.
  - The resulting bets outperform fractional-Kelly bets at the same drawdown risk or growth rate.
  - [arXiv 1603.06183](https://arxiv.org/pdf/1603.06183); [Stanford page](https://web.stanford.edu/~boyd/papers/kelly.html)
- **Kaminski & Lo (2014), *When Do Stop-Loss Rules Stop Losses?*, J. Financial Markets 18:234-254:**
  - Under the random-walk hypothesis (returns i.i.d., i.e. independent with no regime changes), simple 0/1 stop-loss rules always reduce expected return.
  - They add value only when returns have momentum or regime persistence. In monthly US equity data 1950-2004, some stop-loss rules added 50-100 bp/month during stop-out periods.
  - [MIT DSpace](https://dspace.mit.edu/handle/1721.1/114876); [SIFR working paper](https://swopec.hhs.se/sifrwp/abs/sifrwp0063.htm)

### Inferences
- **Grossman-Zhou rewritten in drawdown terms** (algebra added here, not from the paper). Let D = current drawdown from peak and D_max = 1 − α:
  - Exposure as a fraction of current wealth = k·(D_max − D)/(1 − D).
  - At the peak this is k·D_max, and it falls smoothly to 0 at D = D_max.
  - Example with D_max = 35% (the bot's existing threshold) and 5% of bankroll staked at the peak (k = 0.143), on an illustrative $2,000 peak:

    | Equity | $2,000 | $1,900 | $1,800 | $1,700 | $1,600 | $1,500 | $1,400 | $1,300 |
    |---|---|---|---|---|---|---|---|---|
    | Stake budget | $100 (5.0%) | $86 (4.5%) | $71 (4.0%) | $57 (3.4%) | $43 (2.7%) | $29 (1.9%) | $14 (1.0%) | $0 |

  - This is a continuous version of the Millennium halve-then-stop rule.
- **CPPI gap risk for binary bets.** A binary contract can lose 100% of its stake in one settlement, so the "crash size" is 100% and the CPPI multiplier on total simultaneously open stake must be ≤ 1 to guarantee the floor.
  - Concretely: the sum of stakes that can all lose together in one window must not exceed the cushion (equity − floor).
  - With k = 0.143 per bet, up to about 7 fully correlated bets per window keep the floor intact.
- **Closed-form drawdown-to-Kelly-fraction rule** (derived here from Thorp eq. 7.13). Setting x^(2/c−1) = β gives c = 2/(1 + ln β / ln α).
  - 35% max drawdown with ≤10% lifetime probability: c ≈ 0.32 of Kelly.
  - 20% max drawdown with ≤10% probability: c ≈ 0.18.
  - 10% max drawdown with ≤10% probability: c ≈ 0.09.
- **P(ever touching a level) from Thorp's formula**, starting from the current peak:

  | Kelly fraction | Ever −35% | Ever −50% | Ever −20% | Ever −10% |
  |---|---|---|---|---|
  | Full Kelly | 65% | 50% | 80% | 90% |
  | Half Kelly | 27% | 12.5% | 51% | 73% |
  | Quarter Kelly | 4.9% | 0.8% | 21% | 48% |
  | 0.1 Kelly | 0.03% | ≈0% | 1.4% | 14% |

  - So a 5%/day prop-style limit implies betting well under quarter Kelly, or accepting that the limit will trip regularly.
  - Caveats: continuous approximation, infinite horizon, edge known exactly.
- **Risk-constrained Kelly for one repeated binary contract** (the project's own calculation; buy at p, true win probability q; full Kelly f* = (q − p)/(1 − p)):
  - With p = 0.93 and q = 0.96, f* = 43% of bankroll per bet.
  - RCK gives about 36% of Kelly (54% of max growth) for α=0.65, β=0.10.
  - About 20% of Kelly (33% of growth) for α=0.8, β=0.10.
  - About 10% of Kelly (17% of growth) for α=0.9, β=0.10.
  - The same ratios held for p=0.92/q=0.95 and p=0.95/q=0.97.
  - These assume q is known. At q = 0.95 rather than 0.96, f* drops from 43% to 29%, and at q = p it is zero. Estimation error in q is the dominant risk, which argues for the low end of these fractions (Thorp's argument).
- **Kaminski-Lo implication.** If the bot's edge is stable (i.i.d.), drawdown halts cost growth. They pay off only when a drawdown signals the edge has decayed, the regime has changed, or there is a bug.
  - So the halts should be designed as model-break detectors: pause, review, resume at reduced size.
  - They should not be permanent shutdowns or something that triggers routinely.

### Gaps
- No peer-reviewed source was found that defines a standard "drawdown-adjusted Kelly" formula under that name. The closest rigorous results are Grossman-Zhou (cushion sizing), Thorp eq. 7.13 (fractional Kelly vs ruin-to-x) and Busseti-Ryu-Boyd (RCK).
- The full Chekhlov et al. 2005 text was not read, only abstracts and bibliographic records.
- Ernest Chan's specific treatment (CPPI applied to Kelly with a max-drawdown sub-account, in *Algorithmic Trading*, 2013) could not be verified from his own text. The only verified Chan point is a forum report that he advises retail traders to use half Kelly ([NexusFi](https://nexusfi.com/showthread.php?p=876809)), which is weak.

## Volatility targeting and risk budgets: how they're set and how they translate to a bettor

### Takeaway
Systematic funds set one risk number: an annualized volatility target, typically around 16-37% for a single-strategy futures system and capped at half-Kelly (Kelly-optimal annual vol ≈ the Sharpe ratio). They scale positions by recent volatility, which mainly shrinks left-tail losses (the worst outcomes). Banks set tail budgets with Expected Shortfall at 97.5% (the average of the worst 2.5% outcomes). For a binary-contract bettor the cleanest equivalents are (1) a hard cap on total stake that can lose together in one 15-minute window, which is the exact worst case, and (2) a daily-volatility budget built from the binary variance √(q(1−q))/p per $ staked.

### Cited findings
- **Carver, *Systematic Trading* (2015):**
  - Risk appetite is set with "a single figure… an expected standard deviation, which I call the volatility target", an annualized cash vol target.
  - "Using the full Kelly criteria is far too aggressive"; "It's far better to Half-Kelly and set your risk at half the optimal."
  - The highest vol target he would advocate for his own system is 37%, for about 45 instruments and a back-tested Sharpe of about 1.0. Back-tested Sharpe should be multiplied by about 0.75 out of sample.
  - Realistic Sharpe ratios "rarely exceed 1.0".
  - [CXO Advisory notes on Systematic Trading](https://www.cxoadvisory.com/big-ideas/a-few-notes-on-systematic-trading)
- **Carver's open-source system pysystemtrade** defaults to percentage_vol_target: 16.0 (16% annualized) and notional capital of $1,000,000. Its volatility lookback is 35 days, and its portfolio "risk overlay" limits ship commented out. Source: [pysystemtrade defaults.yaml](https://raw.githubusercontent.com/robcarver17/pysystemtrade/master/sysdata/config/defaults.yaml)
- A Monte Carlo rule of thumb (CFA Institute comment, non-authoritative): the Kelly-optimal vol target is about the Sharpe ratio (Sharpe 0.5 → 50% vol, Sharpe 1 → 100%), and "you would need to halve that". Source: [CFA Institute comment](https://rpc.cfainstitute.org/comment/reply/node/142841/field_comments/37096). This is consistent with Carver's 37% ≈ ½ × 0.75 × Sharpe 1.0.
- **Harvey, Hoyle, Korgaonkar, Rattray, Sargaison & Van Hemert (2018), *The Impact of Volatility Targeting*, J. Portfolio Management** (60 assets, daily data from 1926):
  - Vol targeting barely changes Sharpe for bonds, FX and commodities, but "reduces the likelihood of extreme returns, across all asset classes".
  - The reason: left-tail events "typically occur at times of elevated volatility, when a target-volatility portfolio has a relatively small notional exposure".
  - [Duke PDF](https://people.duke.edu/~charvey/Research/Published_Papers/P135_The_impact_of.pdf); [Alpha Architect summary](https://alphaarchitect.com/volatility-targeting-improves-risk-adjusted-returns/)
- **Basel FRTB (bank trading-book capital rules):** they replace 10-day 99% VaR with 97.5% Expected Shortfall, calibrated to a stressed period. Under normality, 97.5% ES ≈ μ + 2.338σ vs 99% VaR ≈ μ + 2.326σ, but ES is much larger with fat tails. Sources: [Bank Policy Institute](https://bpi.com/why-is-the-frtb-expected-shortfall-calculation-designed-as-it-is/); [AnalystPrep FRTB notes](https://analystprep.com/study-notes/frm/part-2/operational-and-integrated-risk-management/fundamental-review-of-the-trading-book-frtb)
- **Half-Kelly trade-off:** half volatility for 3/4 of the growth. Source: [Thorp 2006](https://www.gwern.net/doc/statistics/decision/2006-thorp.pdf)

### Inferences
- **Daily vol target.** Annual vol ÷ 16 (√256 trading days) gives daily vol. A 16-37% annual target is therefore about 1.0-2.3% of bankroll per day, or about $20-$46/day on an illustrative $2,000 bankroll. Crypto 15-minute markets run every day, so √365 ≈ 19 is arguably the right divisor (about 0.8-1.9%/day).
- **Volatility of a binary contract.** Bought at price p with win probability q, the P&L SD per $ staked is √(q(1−q))/p (derived here). Examples:
  - p=0.93, q=0.96: 0.21
  - p=0.93, q=0.95: 0.23
  - p=0.95, q=0.97: 0.18
- **Turning the daily target into a per-window stake cap.** If the stakes in one window are treated as perfectly correlated (likely for crypto contracts settling on the same 15-minute move) and windows as independent, then daily SD ≈ 0.21 × S_w × √N, where S_w is the total stake per window and N the windows traded per day.
  - Example: N = 40 and a $40/day target give S_w ≈ $40 / (0.21 × 6.3) ≈ $30 per window.
  - This is illustrative, not fitted to the bot.
- **"Worst 15-minute window" budget.** For binary bets the worst case is exact, not statistical: the whole stake in a window can go to zero. "Cap the expected worst 15-minute window at X% of bankroll" therefore becomes "total stake across correlated contracts in one window ≤ X% of current equity" (the CPPI m ≤ 1 logic above).
  - An ES-style version: compute the 97.5% ES of window P&L from history (the average of the worst 2.5% of windows) and keep it ≤ X%.
  - Pairing it with a daily limit: setting the window cap at half the daily loss limit means two complete wipeouts are needed to trip the daily stop.
- **Vol-scaling for the bettor.** The binary-bet analogue of Harvey et al. is to cut stakes when the underlying (e.g., BTC 15-minute realized vol) is elevated, because the favourite's loss probability rises then. This needs a backtest before adoption.

### Gaps
- A specific "25%" vol target in Carver's book could not be verified. Only the 37% ceiling (via CXO) and pysystemtrade's 16% default are verified.
- No source covers volatility targeting specifically for binary or prediction-market contracts. The translation above is the project's own derivation.
- The Basel Committee's primary FRTB text (MAR33) was not opened. The ES figures come from secondary FRM/BPI material.

## Typical numbers: max acceptable drawdown at small funds and prop shops, and the sizing that follows

### Takeaway
Public reference points cluster tightly:

| Venue | Daily stop | Total stop |
|---|---|---|
| Retail prop | 2-5% | 4-10% |
| Multi-manager pods (reported) | none reported | halve at −5%, out at −7.5% |
| Systematic futures (Carver) | none | sized for 16-37% annual vol at ≤ half Kelly |

No reliable public survey gives a "typical maximum drawdown" for small funds. Thorp's formula shows that a 10% hard stop is only rarely hit at about 0.1 Kelly (lifetime chance about 14%; at quarter Kelly it is about 48%). The bot's 35%/50% stops are consistent with roughly a third to half of Kelly.

### Cited findings
- **FTMO:** 5% daily / 10% maximum (2-Step); 3% daily / 10% trailing (1-Step). Source: [FTMO](https://ftmo.com/en/trading-objectives/)
- **Topstep $50K:** $1,000 daily (2%) / $2,000 maximum (4%). Sources: [Topstep Help Center](https://help.topstep.com/en/articles/10490293-daily-loss-limit-in-the-trading-combine-and-express-funded-account); [TradersPost](https://blog.traderspost.io/article/how-to-get-funded-with-topstep)
- **Millennium (reported):** −5% → capital halved; a further −2.5% (total about −7.5%) → usually fired. Source: [eFinancialCareers, 2025](https://www.efinancialcareers.com/news/pratik-madhvani-glen-scheinberg)
- **Carver:** half-Kelly, about a 37% annual vol ceiling for a diversified Sharpe-≈1 system. Source: [CXO Advisory](https://www.cxoadvisory.com/big-ideas/a-few-notes-on-systematic-trading). pysystemtrade default 16%. Source: [pysystemtrade](https://raw.githubusercontent.com/robcarver17/pysystemtrade/master/sysdata/config/defaults.yaml)
- **Thorp:** full Kelly has a 50% chance of ever halving; half Kelly 12.5%. Practitioners prefer about half Kelly. Source: [Thorp 2006](https://www.gwern.net/doc/statistics/decision/2006-thorp.pdf)
- **Busseti-Ryu-Boyd:** their worked example frames the constraint as "probability of experiencing more than 30% drawdown is only 10%". Source: [arXiv 1603.06183](https://arxiv.org/pdf/1603.06183)
- Hedge-fund investors have "very low tolerance for drawdown". This is an anecdotal blog claim, not survey data. Source: [R-bloggers, 2014](https://www.r-bloggers.com/2014/12/risk-as-a-survival-variable/)

### Inferences
**What a small bot could adopt.** This synthesis is the project's own, not a source's recommendation.

1. **Keep the existing three halts as catastrophe stops.** The 35%-in-24h and 50%-of-starting-bankroll stops sit where full Kelly would trip them about 50-65% of the time, so they protect against ruin, not against ordinary bad runs.
   - Change their behaviour to "cancel all resting orders + block new orders until a human resets" (FIA kill-switch definition), rather than resuming automatically when a 24-hour window rolls off.
2. **Add a professional-style layer inside them:**
   - (a) a daily loss limit of about 5-10% of start-of-day equity, counting open positions at their worst case (stake at risk). It should flatten/cancel and block until the next session, like FTMO/Topstep.
   - (b) a high-water-mark step-down: about −10% from peak → halve stakes; about −20% → stop pending review. This is the Millennium pattern scaled up for a higher-variance binary book.
   - (c) or, in place of (b), the continuous Grossman-Zhou cushion rule: stake ∝ (equity − 0.65 × peak), which shrinks size linearly to zero at −35%.
3. **Size so the stops rarely bind.** Using c ≈ 2/(1 + ln β / ln α):
   - a 20% drawdown at ≤10% lifetime probability needs about 0.18 Kelly;
   - a 35% drawdown at ≤10% needs about 0.32 Kelly;
   - given uncertainty in the win probability q, prefer the lower figure.
4. **Add a window exposure cap.** The sum of stakes on correlated contracts in one 15-minute window should be ≤ the CPPI cushion, and ≤ about half the daily loss limit. For binary bets, "worst window" = total window stake.
5. **Fill in the FIA/15c3-5 pre-trade checks the 3-failed-orders rule doesn't cover:**
   - max order size, failing closed if no limit is configured;
   - a price collar versus the current book;
   - duplicate-order detection;
   - an aggregate open-exposure check that includes working orders, run in a separate code path;
   - a stale-market-data block (time since last update, spread);
   - heartbeat/cancel-on-disconnect;
   - reconciliation of local fills against the venue's records (drop-copy style);
   - a repeated-execution throttle that needs a human to re-enable.
6. **Treat halts as model-break detectors (Kaminski-Lo).** Log every trigger and compare post-trigger performance with the backtest before resuming, rather than tuning the thresholds for return.

### Gaps
- No reliable public data on typical maximum-drawdown tolerances at small or emerging hedge funds or CTAs (e.g., redemption triggers). Searches returned only anecdotes. Allocator due-diligence surveys were not reached.
- No public HFT P&L-limit numbers.
- The suggested 5-10% daily and −10%/−20% step-down levels are the project's own extrapolations from prop and pod numbers adjusted for the binary book's higher per-bet variance. They are not taken from any source and should be backtested against the bot's own loss history before adoption.
