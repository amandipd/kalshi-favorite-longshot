# Fair-value pricing and settlement mechanics for Kalshi 15-minute up/down markets

Scope note: research done 2026-10-09 (US time; Kalshi API pulls were stamped about 2026-10-10 04:50 UTC). Kalshi's own API, contract-terms PDFs and CF Benchmarks methodology PDFs are primary sources. Blogs, vendor sites and GitHub READMEs are secondary and flagged as such. The bot under study enters at the end of minute 8, so **7 minutes (420 s) before close**.

## 1. Exactly how do the 15-minute markets settle (crypto, metals, energy)?

### Takeaway
Crypto 15-minute markets settle YES if the **simple average of the 60 one-second CF Benchmarks RTI values in the minute before close is at least the same 60-second average from the minute before open**. The strike (`floor_strike`) is fixed when the window opens, and a tie goes to YES. Metals and energy 15-minute markets settle on **Pyth**, not CF Benchmarks: a single **1-minute candle close at the close time**, with no averaging, compared with the candle close at open. With 7 minutes left, no part of the crypto averaging window is known yet. The strike, though, is already a known number.

### Cited findings
**Crypto (BTC, ETH, SOL, XRP, DOGE, BNB, HYPE, NEAR, ZEC)**
- Live rule text, settled market KXBTC15M-26OCT100045-45: "If the simple average of the sixty seconds of CF Benchmarks' BRTI before 12:45 AM EDT on Oct 10, 2026 is at least the simple average of the sixty seconds of CF Benchmarks' BRTI before 12:30 AM EDT on October 10, 2026, then the market resolves to Yes." The fields are `strike_type: greater_or_equal`, `floor_strike: 82594.41`, `expiration_value: 82605.32` and `result: yes`. Source: [Kalshi API, markets?series_ticker=KXBTC15M&status=settled](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXBTC15M&status=settled&limit=1)
- Secondary rule text: "At the last minute before expiration, 60 RTI prices are collected. The official and final value is the average of these prices, rounded to the nearest 2 decimal places." Source: [Kalshi API, same market](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXBTC15M&status=settled&limit=1); the same "important info" text appears in the series metadata. Source: [Kalshi API, series KXBTC15M](https://api.elections.kalshi.com/trade-api/v2/series/KXBTC15M)
- The rule text names an index per asset: BRTI (BTC), SOLUSDRTI, XRPUSDRTI, DOGEUSDRTI, BNBUSDRTI, NEARUSDRTI, ZECUSDRTI and HYPEUSDRTI. Each uses the identical "sixty seconds before close ≥ sixty seconds before open" structure. Source: [Kalshi API, settled markets per series, e.g. KXDOGE15M](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXDOGE15M&status=settled&limit=1)
- Rounding varies by asset (`custom_strike.round_digits`): BTC and BNB round to 2 decimals; SOL, XRP, NEAR, ZEC and HYPE to 4; DOGE to 7 (e.g. target $0.0862022). Source: [Kalshi API, settled markets per series](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXSOL15M&status=settled&limit=1)
- Example window: open 04:30Z, close 04:45Z, `expected_expiration_time` 04:50Z (5 minutes after close). Source: [Kalshi API](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXBTC15M&status=settled&limit=1)
- HYPE switched index streams. "Following our weekly maintenance window on Thursday, June 11th at 5:00 AM ET, all HYPE market settlements will transition from CF Benchmark's U_HYPEUSD_RTI stream to the HYPEUSD_RTI data stream." Source: [Kalshi API, series KXHYPE15M](https://api.elections.kalshi.com/trade-api/v2/series/KXHYPE15M)
- Generic CRYPTO contract terms: the Underlying is the spot price "according to a simple average of the CF <cryptocurrency> <index> for the 60 seconds prior to <time>". "Revisions to the Underlying made after Expiration will not be accounted for." "'At least X' means X or greater." Source Agency is CF Benchmarks. **"If no data is available or incomplete on the Expiration Date at the Expiration Time, then affected strikes resolve to No."** Position Accountability Level is $25,000 per strike per member. Source: [Kalshi CRYPTO contract terms PDF](https://assets.kalshi.com/contract_terms/CRYPTO.pdf)
- Kalshi help center: "a simple average of the CF Benchmarks index over the 60 seconds before the time named in the market's rules". 15-minute markets "compare the average from the minute before the market closes with the average from the minute before it opened". Index values fetched after expiration may reflect later CF revisions, and each market's contract terms govern. Source: [Kalshi Help: Crypto Markets](https://help.kalshi.com/en/articles/13823838-crypto-markets)
- The self-certification filing for these contracts was made under CFTC Reg. 40.2(a), with terms in Appendix A and confidential appendices. Source: [Kalshi product certification, CRYPTO](https://assets.kalshi.com/regulatory/product-certifications/CRYPTO.pdf)
- Fees: the series metadata gives `fee_type: quadratic` and `fee_multiplier: 1` for all of these series. Source: [Kalshi API, series KXBTC15M](https://api.elections.kalshi.com/trade-api/v2/series/KXBTC15M). A secondary source gives the taker fee as 0.07 × P × (1−P): about 1.75¢ at 50¢ and 0.63¢ at 90¢. Source: [PredictionMarketsPicks, Aug-Sep 2026](https://predictionmarketspicks.com/articles/how-kalshi-15-minute-markets-settle)

**How the CF RTI is built (what is being averaged)**
- CME CF Real Time Indices Methodology v17.0 (21 Sep 2026). Each RTI value is computed from a **consolidated order book** of constituent exchanges, not from trades. The steps are: aggregate the books with a dynamic order-size cap; **uncross** the consolidated book (added in v16.8, 29 Jun 2026); build the mid price-volume curve; find the "utilized depth", where the mid spread-volume curve stays within the deviation D (0.5% for BTC, 1% for ETH/SOL/XRP); then take an exponentially weighted (λ = 1/(0.3·v_T)) average of the mid price-volume curve. The result is effectively a depth-weighted mid, not a last trade. Source: [CF Benchmarks RTI Methodology v17.0](https://docs.cfbenchmarks.com/CME%20CF%20Real%20Time%20Indices%20Methodology.pdf)
- Effective time is **every 200 ms** for BRTI, ETHUSD_RTI, SOLUSD_RTI and XRPUSD_RTI (changed in v16.6, 18 May 2026), with a 10-second retrieval-lag threshold. Many other RTIs (e.g. NEAR, SUI) run every second with a 30-second threshold. Source: [CF RTI Methodology v17.0, §6.2](https://docs.cfbenchmarks.com/CME%20CF%20Real%20Time%20Indices%20Methodology.pdf)
- Contingencies: an exchange whose book is older than the lag threshold is dropped. An exchange whose mid deviates from the median of constituent mids by more than the "Potentially Erroneous Data Parameter" (5% for BTC/ETH/SOL, 10% for XRP/NEAR) is dropped until it is back within 50% of that threshold. If every book fails, **the RTI is not published for that second**. Source: [CF RTI Methodology v17.0, §5](https://docs.cfbenchmarks.com/CME%20CF%20Real%20Time%20Indices%20Methodology.pdf)
- CF states that because the RTI uses only order-book data, it is "both a Markov process and a martingale … the best prediction of the next … value is its current value". It explicitly contrasts this with trade-based indices, where "stale prices will be updated or … a price will drop out of a weighting window". Source: [CF RTI Methodology v17.0, §4.2](https://docs.cfbenchmarks.com/CME%20CF%20Real%20Time%20Indices%20Methodology.pdf)
- **BRTI constituents** (CME CF list v13.7, 24 Aug 2026): Bitstamp, Coinbase (including Pro/Prime), Kraken, Gemini, Bullish (added 30-Dec-24), Crypto.com (31-Mar-25) and LMAX Digital. itBit was suspended 27-Jul-26. **Binance is not a constituent.** Source: [CME CF Constituent Exchanges v13.7](https://docs.cfbenchmarks.com/CME%20CF%20Constituent%20Exchanges.pdf)
- RTI constituents for the other assets, from the same list and the CF (non-CME) list v10.3 (5 Oct 2026). Asterisked entries apply to reference rates or settlement prices only.
  - ETHUSD_RTI: Bitstamp, Kraken, Gemini, Coinbase, LMAX, Crypto.com, Bullish.
  - SOLUSD_RTI: Coinbase, Kraken, Gemini, LMAX, Bitstamp (from 14-Jul-25).
  - XRPUSD_RTI: Bitstamp, Kraken, LMAX, Coinbase.
  - NEARUSD_RTI: Coinbase, Kraken.
  - DOGEUSD_RTI: Coinbase, Gemini, Kraken.
  - **BNBUSD_RTI: Coinbase and Kraken only** (since 03-Nov-25).
  - **ZECUSD_RTI: Coinbase and Kraken** (Gemini suspended 08-Jun-26).
  - **HYPEUSD_RTI: Bitstamp, Coinbase, Kraken** (since 20-Apr-26).
  
  Sources: [CME CF Constituent Exchanges v13.7](https://docs.cfbenchmarks.com/CME%20CF%20Constituent%20Exchanges.pdf); [CF Constituent Exchanges v10.3](https://docs.cfbenchmarks.com/CF%20Constituent%20Exchanges.pdf)

**Metals and energy (gold, silver, platinum, palladium, copper, WTI, natural gas)**
- Settlement source in the series metadata: "Pyth - Gold" (`Metal.Index.1OZGOLD/USD`), "Pyth - Silver" (`Metal.Index.SILVER/USD`), "Pyth - WTI" (`Commodities.Index.PYTHOIL/USD`) and "Pyth - NATGAS" (`Commodities.Index.NATGAS/USD`). The contract terms are the generic COMMODITIES terms. Sources: [Kalshi API, series KXGOLD15M](https://api.elections.kalshi.com/trade-api/v2/series/KXGOLD15M); [KXWTI15M](https://api.elections.kalshi.com/trade-api/v2/series/KXWTI15M); [KXNATGAS15M](https://api.elections.kalshi.com/trade-api/v2/series/KXNATGAS15M)
- Gold rule: "If the close price of the 1-minute candlestick for Gold on Oct 9, 2026 at 5:00 PM EDT is at least the close price of the 1-minute Pyth GOLD candlestick at 4:45 PM EDT … resolves to Yes." The secondary rule adds: "the close price for the 1-minute candlestick at a given time is the price at the end of the immediately preceding one-minute interval … the candlestick timestamped 4:59 PM reflects trading during 4:59:00 PM to 4:59:59 PM and closes at 5:00:00 PM. If no data is published … the most recently available published data will be used." Source: [Kalshi API, KXGOLD15M settled](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXGOLD15M&status=settled&limit=1)
- WTI, natural gas, platinum and palladium rules state the strike as a literal number, e.g. "close price of the 1-minute candlestick for WTI Oil … at 12:00 AM EDT is at least 90.68". Silver and copper reference the open-time Pyth candle, like gold. Rounding is 2 decimals (gold, WTI), 3 (silver, platinum, palladium) or 5 (copper, natural gas). Sources: [Kalshi API, KXWTI15M settled](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXWTI15M&status=settled&limit=1); [KXPLATINUM15M](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXPLATINUM15M&status=settled&limit=1); [KXCOPPER15M](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXCOPPER15M&status=settled&limit=1)
- COMMODITIES terms: if no data is published for the time period and none is expected within a week, "the most recently available data will be used". A source-agency correction issued within 24 hours is honored, otherwise the original print is final. There is no void branch. Source: [Kalshi COMMODITIES contract terms PDF](https://assets.kalshi.com/contract_terms/COMMODITIES.pdf)
- Secondary (vendor analysis, not verified):
  - Metals and WTI 15-minute markets launched 3 Aug 2026.
  - On 199 of 199 consecutive WTI windows, `floor_strike` equaled the prior window's `expiration_value`.
  - Kalshi's named Pyth metal symbols are not in Pyth's public Hermes catalogue, and `PYTHOIL/USD` last published on 30 Mar 2026.
  - Settlement verdicts agreed 99.5% with the **front-month WTI future** over 200 windows (but only 49.7% with the WTI CFD), 99.5% with XAU/USD for gold and 99.0% with XAG/USD for silver.
  - KXWTI15M rolled from the October to the November contract during the 10 Sep session.
  
  Source: [PredictionMarketsPicks, "How Kalshi 15-Minute Markets Settle" (pub. 6 Aug 2026, upd. 28 Sep 2026)](https://predictionmarketspicks.com/articles/how-kalshi-15-minute-markets-settle)

### Inferences
- **Strike handling.** The strike is the pre-open 60-second average, and Kalshi publishes it as `floor_strike` at open. The bot should read `floor_strike` from the API rather than reconstruct it.
- **What is known at minute 8.** The settlement window is [T−60 s, T), so at T−420 s none of it has been observed yet. Any edge from a partly observed average exists only in the final minute. That is irrelevant to entry at minute 8, but matters for any late-entry or exit logic.
- **Data-outage tail risk.** Crypto contracts resolve **NO** if data is "not available or incomplete". That is a tail risk that only hurts YES-side favorites. It is tiny, but it is asymmetric. Commodities contracts instead fall back to the last available price.
- **Thin RTIs.** BNB, ZEC and NEAR RTIs use only two US exchanges (HYPE uses three), and none includes those coins' main venues (Binance, Hyperliquid). These indices can diverge from "global" prices and are noisier. A fair-value model for them must use Coinbase/Kraken prices as the proxy, not Binance.
- **Metals and energy have no averaging.** These markets settle on one print: the Pyth aggregate at the minute boundary. There is no averaging benefit, so the full 7 minutes of variance applies, plus a single-tick noise term. WTI appears to track the front-month CL future, including its roll.

### Gaps
- **Which 60 prints?** Kalshi says "60 RTI prices" (one per second), but BRTI/ETH/SOL/XRP have been computed every 200 ms since May 2026. Whether Kalshi samples the on-the-second value or something else was not verified.
- The full CFTC filing for the 15-minute crypto series was not found on cftc.gov, and the Appendix A in the generic certification is a template.
- The CF (non-CME) methodology for DOGE/BNB/ZEC/HYPE "Spot Rate" RTIs (calculation frequency, deviation parameters) was not confirmed. Only their constituent lists were.
- **Pyth.** No official Pyth documentation was found on how Kalshi's named metal/energy symbols are aggregated or what happens outside market hours. Pyth's aggregation page says "Pythnet is being shut down as part of the Pyth Core sunset" and points to Pyth Pro docs. Source: [Pyth docs](https://docs.pyth.network/price-feeds/core/how-pyth-works/price-aggregation). The public TradingView-style history endpoint `benchmarks.pyth.network/v1/shims/tradingview/history` returned HTTP 404 in a test on 2026-10-10 UTC, so the historical-candle source for backtesting metals is unresolved.
- Platinum and palladium series metadata (named Pyth symbol) were not pulled. Their rules were confirmed, but not the source symbol.

## 2. How should a ~7-minute binary be priced, and which volatility input works at 1-15-minute horizons?

### Takeaway
A zero-drift Gaussian digital, P(YES) = Φ(ln(S/K)/(σ√τ_eff)), is the right baseline. Use **τ_eff = τ − (2/3)·(60 s)**, i.e. 6.33 minutes at the bot's entry, to account for the 60-second arithmetic average. Add the proxy-error variance (spot proxy vs. RTI). The volatility should be a **realized vol from recent 1-minute (or noise-robust sub-minute) returns, scaled for time of day**, not 30-day implied vol. Fat tails matter at exactly the bot's prices. At equal variance, a fat-tailed distribution makes 90-95¢ favorites win *more* often than Gaussian implies and 99¢+ favorites win *less* often. The final mapping should therefore be empirically calibrated on settled outcomes.

### Cited findings
- Black-Scholes cash-or-nothing call = e^(−rT)·Φ(d₂), with d₂ = [ln(S/K) + (r − q − σ²/2)T]/(σ√T). Skew affects binaries "much more than vanillas" because a binary is the negative strike-derivative of a vanilla. Adjusted value = C_noskew − Vega × ∂σ/∂K. Source: [Wikipedia: Binary option](https://en.wikipedia.org/wiki/Binary_option)
- Averaged settlement: a geometric-average Asian option has a closed form with σ_G = σ/√3 over the averaging period. "An exact result for Asian options with arithmetic averaging … does not exist." Moment matching to a lognormal (Levy) is the standard approximation. Source: [Wikipedia: Asian option](https://en.wikipedia.org/wiki/Asian_option)
- A practitioner KXBTC15M model uses **P(YES) = Φ(gap / √(σ_1m² · r_eff + σ_proxy²))**, with r_eff = "minutes left minus ⅔" to account for the 60-second BRTI average, σ_1m = **60-minute realized volatility of 1-minute returns**, and σ_proxy = measured proxy error. The spot proxy is the mean of Coinbase and Bitstamp, which tracked Kalshi's settlement value with **RMSE $8.77**. Feed disagreement above $60 means no call. A Chronos-2 forecast challenger "tied" the simple vol model (Brier 0.1636 vs 0.1643 on the fit half). Source: [darup67/kalshi-btc-agent README (GitHub, Sep 2026)](https://github.com/darup67/kalshi-btc-agent)
- Another open-source KXBTC15M bot uses a zero-drift GBM digital: ln(S_T/S_0) ~ N(−½σ_h², σ_h²), σ_h = σ_per_second·√(seconds remaining), σ from "realized volatility of trailing 1-minute Coinbase closes". It says "any momentum estimate is mostly noise" at 15 minutes. It adds an XGBoost layer with Platt scaling and walk-forward validation (no numeric results in the README). Source: [SiddhaBasu/kalshi-bot README](https://github.com/SiddhaBasu/kalshi-bot)
- A third repo reportedly uses GBM with vol from trailing 1-second Binance samples over a 900-second window (search snippet only, not opened). Source: [brandononchain/kalshibot](https://github.com/brandononchain/kalshibot)
- **Fat tails, conditional on vol.** FX returns standardized by realized volatility are "very nearly Gaussian", while standardizing by GARCH/SV estimates leaves fat tails. Source: [Andersen, Bollerslev, Diebold & Labys, NBER w7488](https://www.nber.org/papers/w7488)
- BTC returns are heavily fat-tailed (one table reports daily-frequency kurtosis of 36.78), and part of the high-frequency kurtosis reflects microstructure noise. Source: [Understanding jumps in high frequency digital asset markets, arXiv 2110.09429](https://arxiv.org/pdf/2110.09429)
- **Volatility forecasting.** For Bitcoin, HAR models on realized variance from 5-minute returns beat GARCH one day ahead. Source: [HSE Economic Journal 2023](https://ej.hse.ru/en/2023-27-1/819340420.html). Note this is daily horizon. No study at 1-15-minute horizons was found.
- **Microstructure noise.** Naive realized variance breaks down at the highest sampling frequencies. The two-scales estimator (sparse plus dense grids) is consistent under noise. Source: [Zhang, Mykland & Aït-Sahalia, "A Tale of Two Time Scales" (JASA 2005), NBER w10111](https://www.nber.org/papers/w10111.pdf)
- **Range estimators.** Garman-Klass is ~7.4× as efficient as close-to-close, and Parkinson ~5× (secondary summary). Source: [Ryan O'Connell Finance](https://ryanoconnellfinance.com/historical-volatility-estimators/)
- **Implied vol.** Deribit DVOL is an annualized **30-day** implied vol built from the smile of near expiries. Sources: [Deribit Insights](https://insights.deribit.com/?p=1813); [Amberdata docs](https://docs.amberdata.io/docs/volatility-index). No listed option expires in 15 minutes, so short-horizon pricing must rely on realized vol (search-result summary of practitioner material). Source: [PredictionMarketsPicks KXBTC15M guide](https://predictionmarketspicks.com/articles/kalshi-bitcoin-15-minute-markets)
- **Option-buyer premium.** Short-dated option buyers pay the variance risk premium and lose on average even before costs, while sellers profit after fees. This is SPX 0DTE, a different venue. Source: [Beckmeyer, Branger & Gayda, "Retail Traders Love 0DTE Options… But Should They?" (SSRN 4404704, 2023), via secondary coverage](https://www.wealthmanagement.com/equities/retail-investors-are-in-love-with-same-day-options)

### Inferences
- **Averaging adjustment** (standard Brownian-motion algebra, derived here; it matches darup67's "minus ⅔"). Let the 60-second average end at T. From time t with τ = T − t, the variance of the average is σ²[(τ − L) + L/3] = σ²(τ − 2L/3) with L = 60 s. At the bot's entry τ = 7 min, so **τ_eff = 6.33 min**: about 9.5% less variance and about 4.9% smaller σ. That raises a favorite's fair probability by:

  | Price under naive τ = 7 min | Fair probability with τ_eff = 6.33 min |
  |---|---|
  | 90.0% | 91.1% |
  | 95.0% | 95.8% |
  | 99.0% | 99.3% |

  These shifts are **bigger than the bot's whole edge** (a few tenths of a cent). Getting τ_eff wrong would by itself flip skip/buy decisions.
- **Distances implied by price.** With τ_eff = 6.33 min, a 90¢ favorite implies the spot sits about **3.2 σ_1m** from the strike, 95¢ about 4.1 σ_1m and 99¢ about 5.9 σ_1m (σ_1m = 1-minute return σ in price units).
- **Fat-tail effect** (own calculation: unit-variance Student-t vs Gaussian at the same z).

  | Gaussian z | Gaussian P | Student-t P (df=4) | Student-t P (df=6) |
  |---|---|---|---|
  | 1.28 | 0.900 | 0.928 | 0.916 |
  | 1.645 | 0.950 | 0.960 | 0.955 |
  | 2.0 | 0.977 | 0.976 | 0.975 |
  | 2.33 | 0.990 | 0.985 | 0.985 |

  The crossover is near 97-98¢. If true tails are heavier than Gaussian, a Gaussian model will call 90-96¢ favorites *overpriced* when they are actually fair or cheap, and call 99¢+ favorites fair when they are overpriced. This matches the sign of the observed favorite-longshot bias in the 90¢+ bucket, and argues for an empirical calibration layer (isotonic or Platt on the model z) or a t / jump-diffusion kernel rather than raw Φ.
- **Volatility input.** Use σ from 1-minute returns of the RTI or proxy over a trailing 30-120 minutes. Blend it with a slower EWMA or HAR-style daily component and an hour-of-day multiplier. DVOL/√(365·24·60) can serve as a slow anchor or sanity bound, but it embeds the variance risk premium, so on average it should overstate short-horizon realized vol (an inference from the VRP literature, not measured here). If using 1-second data, use a two-scales or subsampled estimator, because the RTI is an order-book composite and is smoother than trades, but not noise-free.
- **Proxy error.** Add σ_proxy² to the variance. For BTC, darup67's $8.77 RMSE is roughly 1 bp at ~$82k, so it is small relative to 7-minute vol. For thin RTIs (BNB, ZEC, NEAR, HYPE), σ_proxy should be measured per asset and could be material.
- **Drift and skew.** Set drift to zero. The RTI is a martingale by construction per CF, and 7-minute drift is negligible. Skew/smile adjustments from listed options are not available at this horizon. Treat skew empirically, e.g. separate calibration for "favorite is YES/up" vs "favorite is NO/down".
- **Metals and energy.** Use τ_eff = τ (no averaging), an underlying proxy of COMEX/CME front-month futures or XAU/XAG spot, and per-asset vol. WTI vol must follow the front-month CL contract.

### Gaps
- No published study was found comparing EWMA, HAR, Parkinson/Garman-Klass and realized-vol estimators at **1-15-minute** horizons for crypto or metals. The daily-horizon literature (HAR > GARCH) may not transfer.
- Neither a numeric DVOL-to-short-horizon realized vol ratio nor how much the variance risk premium biases scaled DVOL at intraday horizons was verified.
- No source was found quantifying the kurtosis of standardized 5-10-minute BTC/alt returns, so the Student-t df to use is unverified and should be fitted on the bot's own data.
- The SiddhaBasu repo's numeric walk-forward results (Brier per fold, Platt vs clipping) live in files that were not opened. A search summary claimed Platt scaling improved Brier in only 3 of 9 folds, while clipping to [0.10, 0.90] improved it in 9 of 9, and that a backtest P&L gain came from assuming fills at model probability. This could not be confirmed from the README.

## 3. Does the averaging window or the composite index create predictable edges near close?

### Takeaway
At the bot's minute-8 entry there is **no averaging-window information edge**: the settlement minute has not started. The 60-second average mainly lowers effective variance (Q2) and makes the settlement much harder to manipulate. The RTI is designed to be a martingale and excludes Binance, so any "lag" edge from Binance leading would be sub-second to seconds. That is irrelevant at 7 minutes, except as a reason to read spot from a fast proxy rather than a slow API. The edge from a partly known average exists only inside the final 60 seconds.

### Cited findings
- CF: because the RTI uses order-book data only, it is a Markov process and a martingale. Trade-based indices instead show "predictability … due to the expectation that stale prices will be updated or that a price will drop out of a weighting window". Source: [CF RTI Methodology v17.0, §4.2](https://docs.cfbenchmarks.com/CME%20CF%20Real%20Time%20Indices%20Methodology.pdf)
- BRTI has no Binance input. Its constituents are Bitstamp, Coinbase, Kraken, Gemini, Bullish, Crypto.com and LMAX. Source: [CME CF Constituent Exchanges v13.7](https://docs.cfbenchmarks.com/CME%20CF%20Constituent%20Exchanges.pdf)
- Price discovery: Carol Alexander's analysis estimates ~70% of bitcoin price moves start on Binance, with Coinbase the largest share of the rest. The analysis is minute-level and the source is a secondary summary. Source: [Social Science International summary](https://www.socialscience.international/almost-all-bitcoin-price-transmission-comes-from-binance). One study puts the lead-lag between BTC spot and CME futures at about −0.057 s (milliseconds scale). Source: [Price Discovery in Cryptocurrency Markets, arXiv 2506.08718](https://arxiv.org/pdf/2506.08718)
- **Polymarket comparison (different oracle).** Polymarket's 5- and 15-minute BTC up/down contracts settle on a **single-instant** Chainlink Data Streams print, not an average. After the 5-minute contract launched (12 Feb 2026), Binance order flow in the **final ten seconds** spiked (~50% above pre-launch), with ~25% price reversal within 10 s in near-even cycles. The signature was "much attenuated for the fifteen-minute contract". The Binance mid sits ~2.5 bp from the oracle and finishes on the same side of the strike ~85% of the time. The authors note that an averaged or time-weighted reference "raises the manipulation cost roughly in proportion to the averaging window". Source: [Dai, Jia & Yu, "Settlement Manipulation in Prediction Markets", arXiv 2606.31675 (Jul 2026)](https://arxiv.org/pdf/2606.31675)
- Kalshi lists only a 15-minute crypto up/down contract, with no 5-minute equivalent (as of the paper's sample). Source: [Dai, Jia & Yu, arXiv 2606.31675](https://arxiv.org/pdf/2606.31675)
- An open-source Kalshi bot reportedly switches to "BRTI average tracking" in the final minute (search snippet, not opened). Source: [papabrosio/kalshi-btc-15min-trader](https://github.com/papabrosio/kalshi-btc-15min-trader)
- darup67 per-minute results (BTC, Sep 2026): late calls at **minute 13 lost −2.2¢ per contract** [CI −3.7, −0.7]. Minute 3 showed +6.3¢ (n=77, CI [−0.5, +12.4]), which the author calls only "a hypothesis". Source: [darup67/kalshi-btc-agent](https://github.com/darup67/kalshi-btc-agent)

### Inferences
- **What remains at minute 8.** The window has not started, so there is no averaging-window information edge to exploit. What remains is (a) correct τ_eff, (b) the strike being a lagged average, and (c) where the market currently sits relative to the strike.
- **The strike lags spot.** Because the strike is the 60-second average before open, at open the spot can already sit slightly above or below it. This is a real but tiny effect, and it is visible at minute 8 simply as spot vs `floor_strike`, which the model already uses.
- **Manipulation risk.** The 60-second average is a structural reason Kalshi's 15-minute markets should be less exposed to last-second pushes than Polymarket's single-print markets. Metals and energy (single Pyth candle close) are the exception and are more exposed in principle.
- **Thin RTIs.** For BNB, ZEC, NEAR and HYPE, the RTI is built from 2-3 US books, so it may lag the dominant venue more and show larger idiosyncratic jumps when one book is dropped by the deviation filter. A model using Binance or Hyperliquid prices would mis-measure the gap. Use the constituents.

### Gaps
- No measurement was found of the lead-lag between BRTI or other RTIs and Binance at second resolution, nor of how often thin RTIs (BNB, ZEC) drop a constituent under the deviation filter.
- No study was found of whether Kalshi 15-minute prices at minute 8 under- or over-react to spot moves, i.e. whether there is a measurable lag between Kalshi quotes and RTI moves.

## 4. Is there evidence that model-vs-market gaps in short-dated binaries are tradeable after fees?

### Takeaway
The best available evidence says **mostly no**: for Kalshi KXBTC15M and Polymarket BTC 15-minute markets, simple vol models and microstructure ML match but do not beat the market's own price, and gating on model confidence nets about zero after fees. The bot's existing edge (the favorite-longshot bias) is real across Kalshi. A model filter therefore probably cannot be justified by Brier score alone. It has to show, out of sample and inside the 90-99.9¢ band, that (p_model − ask) predicts realized return net of the 0.07·P·(1−P) fee.

### Cited findings
- **Kalshi KXBTC15M** (1,720 windows, 5-23 Sep 2026; gate chosen on the fit half, results on an untouched test half):
  - Kalshi mid Brier **0.1495** vs model **0.1522**.
  - Buying the called side at the ask after fees:

    | Model gate | Cushion | Hit rate | Avg ask | EV per contract |
    |---|---|---|---|---|
    | 0.85 | 1.04σ | 93.5% | 93¢ | **−0.8¢** |
    | 0.95 | 1.64σ | 97.6% | 96¢ | **+0.2¢** |
    | 0.99 | 2.33σ | 98.3% | 98¢ | **−0.5¢** |

  - The author's conclusions: "The calls are accurate, and the market already knows"; the tool "does not show an edge"; "an 81 ms decision loop buys nothing on a 15-minute contract".
  - Listed risks: proxy ≠ BRTI, one three-week regime, and fills worse than the ask.
  
  Source: [darup67/kalshi-btc-agent](https://github.com/darup67/kalshi-btc-agent)
- **Polymarket BTC 15-minute** (Feb-May 2026; 727 M rows synchronized with Binance): a walk-forward logistic model plus Platt scaling over 43 microstructure features scored AUC 0.8377, Brier 0.165 and ECE 0.026. The naive order-book mid prior scored AUC **0.8405**, Brier **0.163** and ECE 0.014. Simulated positive-EV trading netted **−0.116 payoff units per trade** with 1% fees and 0.5% slippage. Polymarket quotes responded to ≥5 bp Binance moves within a **median 347 ms**. Source: [Young, "OpenMarket", arXiv 2607.26245 (Jul/Aug 2026)](https://arxiv.org/html/2607.26245v1)
- **Polymarket fees.** Polymarket added dynamic taker fees to its 15-minute crypto markets to curb latency arbitrage, peaking near 50¢ (≈$1.56 on 100 shares at $0.50, about 3%). Reported peak figures conflict (≈3.15% vs ≈1.80%). Sources: [Finance Magnates](https://www.financemagnates.com/cryptocurrency/polymarket-introduces-dynamic-fees-to-curb-latency-arbitrage-in-short-term-crypto-markets/); [CoinMarketCap Academy](https://coinmarketcap.com/academy/article/polymarket-introduces-fees-on-15-minute-crypto-bets)
- **Lag claims.** Blog and vendor claims that Polymarket short crypto markets lag Binance by 30-90 seconds appeared in search snippets only. They are contradicted by the 347 ms median response measured in OpenMarket. Source: [Young, arXiv 2607.26245](https://arxiv.org/html/2607.26245v1)
- **Favorite-longshot bias on Kalshi.** Across Kalshi, low-price contracts win less often than needed to break even and high-price contracts do slightly better. Makers out-earn takers, both show the pattern, and later versions measure it after fees. Source: [Bürgi, Deng & Whelan, "Makers and Takers: The Economics of the Kalshi Prediction Market" (CEPR DP20631; UCD WP2025_19)](https://www.karlwhelan.com/Papers/Kalshi.pdf)
- **Polymarket longshot overpricing.** Low-probability Polymarket tokens have negative realized returns (not specific to crypto up/down markets). Source: [Polymarket-v1 Database, arXiv 2606.04217](https://arxiv.org/pdf/2606.04217)
- **Vendor figure.** Over 6,298 settled KXBTC15M windows, "buying the leading side" earned about +0.67¢ per contract before costs, while the average taker fee was about 1.55¢. This is a commercial source seen only in a search snippet. Source: [PredictionMarketsPicks / botforkalshi search results](https://predictionmarketspicks.com/articles/kalshi-bitcoin-15-minute-markets)
- **Different venue.** In SPX 0DTE options, buyers pay the variance risk premium and lose before costs, while sellers profit after fees. Source: [Beckmeyer, Branger & Gayda via secondary coverage](https://www.wealthmanagement.com/equities/retail-investors-are-in-love-with-same-day-options)

### Inferences
- **What darup67 does and does not test.** Its gating at a 0.95 model confidence (avg ask 96¢) is close to the bot's regime and found about +0.2¢ per contract. That is the same order as the bot's existing edge and is not distinguishable from zero. It shows that "model says confident" adds little beyond "price says confident". It does **not** test the bot's question: within market favorites at 90-99.9¢, whether p_model − ask sorts winners from losers. That test still needs to be run on the bot's own data.
- **Bar for adding the filter.** Since the market mid is already about as calibrated as the model, any filter gain will come from the residual disagreement tail: model much lower than ask (skip) or much higher (size up). Those cases are few, so statistical power will be the constraint. Expect to need thousands of favorite bets per bucket and time-clustered standard errors. Crypto assets move together, so the 9 simultaneous crypto markets are not independent.
- **Sources of residual mispricing to look for:**
  - Thin RTIs (BNB, ZEC, NEAR, HYPE), where retail may anchor on Binance prices that differ from the Coinbase/Kraken index.
  - Fat-tail regions (Q2 table).
  - Event windows: scheduled macro releases, EIA crude and natural gas storage reports, and the CME 5 PM ET metals break. Here the model should *skip*, not size up. (This is a hypothesis; none of these windows were tested in sources found.)

### Gaps
- No independent, peer-reviewed test was found of model-vs-market gaps specifically among **high-probability (90¢+) favorites** in Kalshi or Polymarket 15-minute markets.
- No evidence was found for metals or energy 15-minute markets at all; every source found concerns crypto.
- The Executable Arbitrage paper (arXiv 2608.00666) surfaced in search, but its findings were not read.

## 5. Practical implementation: data sources, latency, calibration and validation

### Takeaway
The bot already gets the strike (`floor_strike`) and, after settlement, the true 60-second settlement average (`expiration_value`) from Kalshi's market API. Those two fields give exact ground truth for calibrating a spot proxy and the model. The pieces still to add are:
- a live spot source: Kalshi's CF Benchmarks passthrough if entitled, otherwise a mean of the RTI constituents' mids, with Coinbase and Kraken in every crypto index;
- a stored history of spot at minute 8 plus trailing 1-minute returns;
- a time-split calibration that tests whether (p_model − ask) predicts net return within the 90-99.9¢ band.

Latency is a non-issue at a 7-minute horizon. Feed agreement and proxy error matter more.

### Cited findings
- **Kalshi CF Benchmarks passthrough.** `GET /trade-api/v2/cfbenchmarks/values?id=BRTI` returns the latest value, and `/cfbenchmarks/history/values` returns tick-level history (some indices are intra-second). Example IDs include BRTI, BNBUSD_RTI and SHIBUSD_RTI, and the reference table covers BTC, ETH, BNB, HYPE, NEAR, ZEC and others. Access needs standard Kalshi key signing **plus a specific entitlement**. Each call costs 50 read tokens (≈4 requests/s at the Basic tier's 200 tokens/s). There is no WebSocket via the passthrough, and `includeVerification` is ignored. Source: [Kalshi docs: CF Benchmarks REST passthrough](https://docs.kalshi.com/cfbenchmarks/rest-passthrough)
- **Ground-truth fields.** Settled markets expose `floor_strike`, `expiration_value`, `result`, `open_time`, `close_time` and `custom_strike.round_digits` (e.g. BTC 82594.41 → 82605.32, yes). Source: [Kalshi API, settled markets](https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXBTC15M&status=settled&limit=1)
- **Proxy quality.** Mean of Coinbase and Bitstamp vs Kalshi settlement value: RMSE $8.77 for BTC. Kraken serves as a third check, and the bot makes no call when feeds disagree by more than $60. Source: [darup67/kalshi-btc-agent](https://github.com/darup67/kalshi-btc-agent)
- **Constituents per index** (use these exchanges' USD books as the proxy): see Q1. Coinbase and Kraken appear in every relevant crypto RTI. Sources: [CME CF Constituent Exchanges v13.7](https://docs.cfbenchmarks.com/CME%20CF%20Constituent%20Exchanges.pdf); [CF Constituent Exchanges v10.3](https://docs.cfbenchmarks.com/CF%20Constituent%20Exchanges.pdf)
- **Validation practice from comparable projects:**
  - darup67 fits the gate on the first half and reports an untouched second half, with a 95% Wilson lower-bound gate rule. Source: [darup67](https://github.com/darup67/kalshi-btc-agent)
  - SiddhaBasu uses walk-forward folds by chronological window order (not k-fold), Platt scaling refit on out-of-sample predictions, and a feature-parity checker that caught two train/serve skew bugs. Source: [SiddhaBasu/kalshi-bot](https://github.com/SiddhaBasu/kalshi-bot)
  - OpenMarket uses pooled walk-forward with the market mid as the baseline, and reports AUC, Brier, log loss and ECE. Source: [arXiv 2607.26245](https://arxiv.org/html/2607.26245v1)
- **Metals and energy proxies** (secondary): XAU/USD and XAG/USD spot, and the front-month WTI future, agreed ~99-99.5% with settlement verdicts. Source: [PredictionMarketsPicks](https://predictionmarketspicks.com/articles/how-kalshi-15-minute-markets-settle)
- **Local repo data.** The project's 15-minute research CSVs (not published; `research/kalshi_15min/snapshots_all.csv`, 92,588 rows; `minutes_ext.csv`, 70,004 rows) contain Kalshi prices, bids, asks and outcomes per minute, but **no underlying spot prices or strikes**. Columns are `series, ticker, open_time, price_8min, yes_bid, yes_ask, price_7, resolved_yes` and `p1..p15, b1..b15, a1..a15`. Source: local files inspected 2026-10-09

### Inferences
Recommended build, in order:
1. **Backfill.** For every settled market in the sample (Jul 18 onward), pull `floor_strike` and `expiration_value` from the Kalshi API. Pull 1-minute candles for the constituent exchanges (Coinbase, Kraken, Bitstamp public REST), or CF tick history via the passthrough if entitled. From these, compute spot at T−420 s, trailing realized vol and the proxy error at T. Measure the per-asset proxy error as (proxy 60-second average at close) − `expiration_value`.
2. **Model.** Compute z = ln(S/K)/√(σ_1m²·τ_eff + σ_proxy²) with τ_eff = 6.33 min for crypto and 7 min for metals/energy. σ_1m comes from trailing 30-120-minute 1-minute returns with an hour-of-day multiplier. Map z to a probability by isotonic or Platt calibration fitted on older data. A Student-t kernel is also worth trying.
3. **Test.** On held-out later weeks, restrict to the bot's actual trades (favorite ask 90-99.9¢ at minute 8). Bucket by edge = p_cal − ask − fee, where fee = 0.07·ask·(1−ask). Check that realized (win − ask − fee) rises monotonically with edge, using standard errors clustered by 15-minute window (cross-asset correlation). Only deploy skip/size rules whose effect survives that test.
4. **Live guards.** Skip when feeds disagree, when a constituent book is stale, or when a scheduled release falls inside the window. Skip metals and energy windows that close at session breaks (e.g. the 5:00 PM ET gold/silver/copper candle, whose markets show `expected_expiration_time` about 5h45m later).

Latency is not a constraint: OpenMarket measured a 347 ms Polymarket quote response, and darup67 found speed irrelevant on a 15-minute contract. Polling the constituent exchanges once per second is ample for a minute-8 entry.

### Gaps
- Whether the passthrough entitlement is available to retail API users, and its real-world latency, were not verified.
- No working public historical source for Pyth 1-minute candles was confirmed (the TradingView shim returned 404). Metals and energy backtests may need COMEX/NYMEX futures or spot candles from another vendor as a proxy, accepting ~0.5-1% verdict disagreement (per the secondary source).
- Proxy RMSE for the alt RTIs (BNB, ZEC, NEAR, HYPE, DOGE, XRP, SOL) has not been measured in any source found. It must be measured from `expiration_value` before trusting the model on those series.
