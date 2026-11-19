# Polymarket 5-minute crypto markets: can the bot's strategy move there?

*Nov 8, 2026. The question: can the existing strategy be copied into Polymarket's 5-minute crypto markets?
Web research plus our own past notes. Nothing was built, run or traded.*

## The short answer

**Maybe, but not by copying it as is. It needs its own test first.**

- Polymarket's US exchange (the legal one for US residents) **did launch 5-minute markets** on BTC, ETH, SOL and
  XRP around Oct 27–28. So the market exists now. On Oct 18 it did not.
- The bot's profit never came from "buy the favourite (the likely side) at 92c or more". It came from the **two
  filters** that skip some of those bets. Without the filters, the same rule **lost money**: it lost about 1.4
  cents for every dollar bet (−1.37c/$1) on the older half of our data.
- Both filters, and the minute-8 entry time, were tuned on Kalshi's **15-minute** windows. In a 5-minute window
  they mean something different. So "copy the strategy" really means "build a 5-minute version and test it".
- We have **no past data at all** for 5-minute markets in our own files. Kalshi has nothing shorter than 15
  minutes, and our 10 months of history are all 15-minute.

## What the 5-minute markets are

- **Where:** Polymarket US (run by QCX LLC, a CFTC-regulated exchange). Same app and API as its 15-minute markets.
- **Coins:** BTC, ETH, SOL, XRP. These are 4 of the coins the bot already bets on Kalshi.
- **How they work:** will the coin end the 5 minutes above where it started? The right side pays $1 a contract.
  That is 288 windows a day for each coin, against 96 for 15-minute markets.
- **Settlement (how the answer is decided):** Polymarket US's rule filings name **CF Benchmarks** as the price
  source. That is the same source family as Kalshi's, and its 15-minute markets matched Kalshi in 206 of 206 BTC
  windows (Oct 16 check). One news report says Chainlink instead. **Not yet confirmed for the 5-minute markets.**
- **The international version** (closed to US residents) has run 5-minute BTC since Feb 2026. It settles on a
  **30-second average** price at the end, not 60 seconds. A shorter average means a few seconds of price moves at
  the close matter more. A Stanford study (July 2026) said this makes the 5-minute markets easier to push around
  at settlement.

## Why it can't just be copied

1. **The edge lives in the filters.** The 92c floor alone loses money. The spread filter (skip if the gap between
   the buy and sell price is over 2c) and the late-jump filter (skip if the price jumped 10c late) are what turn it
   positive. Their numbers were tuned on 15-minute windows.
2. **The entry time has no 5-minute twin.** The bot buys at minute 8 of 15, just past halfway. In a 5-minute
   window that would be about minute 2.5 to 3. Whether the favourite-longshot bias (cheap unlikely bets overpriced,
   heavy favourites underpriced) shows up there at all is unknown.
3. **Costs are different.**
   - Polymarket US prices move in **1-cent steps** above 90c. Kalshi's move in 0.1-cent steps there. So the
     spread filter would behave differently.
   - Its **taker fee** (the charge for buying at the posted price) uses its own formula, rounded to the cent.
   - On the 15-minute markets, Polymarket US favourites cost about **0.3c more** than the same Kalshi bet.
     With an edge (profit per contract) of only about 1c, that gap matters.
4. **Very little US data so far.** The US 5-minute markets are about 12 days old. The international ones have about
   9 months, but with different traders, a different settlement source and different fees. They are a hint, not
   proof.
5. **The bot can't talk to Polymarket.** It only speaks Kalshi. Trading on Polymarket US needs:
   - an account and an API key,
   - a new order client built and tested,
   - a check that Polymarket US accepts orders from the server's state (never confirmed).
6. **The strategy itself is on paper right now.** Real money stopped on Nov 3. The paper run's first checkpoint
   is **Dec 15** (the test plan). Putting real money on a new venue before that checkpoint would
   skip the bar we set.

## The test I'd run (nothing started)

Same method as every other test here: write the rules and the pass bar down first, then score once.

1. **Pull the data (read-only).** Polymarket US's public price history for its 5-minute markets, all 4 coins,
   since launch. Also the international 5-minute history since Feb, as a bigger sample. Reading public data is fine.
   Trading the international site is not an option for a US resident.
2. **Check settlement.** Every third 5-minute window ends exactly on a 15-minute mark. At those marks, compare
   Polymarket's 5-minute result values with Kalshi's 15-minute values. If they match, the price source is the same.
3. **Write the pre-registration (the rules, fixed in advance).**
   - Entry time: just past halfway, about minute 2.5 to 3.
   - Filters: the same two, scaled to 5 minutes.
   - Costs: Polymarket's real fee and its 1-cent steps.
4. **Run it with a train/test split.** Build on the older days and score once on the newer days. The rule never
   sees the newer days while it is being built.
5. **Check depth.** How much money sits at the favourite's price, so we know how big a bet can be.

**Suggested pass bar (to agree before any score is read):**

- On the held-out days (data the rule never saw while being built), profit stays above about **+0.5 cents for
  every dollar bet** after fees.
- The range the true number is probably in sits above zero. Bets in the same window count as one, because they
  move together.
- The result survives dropping its biggest contributor (one coin or one day).

**If it passes:** run it on paper first, like the Kalshi paper run. Real money would be a separate decision, and not
before the Dec 15 checkpoint.

## Sources

- [Polymarket US adds 5-minute BTC, ETH, SOL and XRP markets (FinanceFeeds)](https://financefeeds.com/polymarket-launches-five-minute-btc-eth-sol-and-xrp-prediction-markets-on-us-app/)
- [Polymarket US launches 5-minute crypto up or down markets (Crypto Briefing)](https://cryptobriefing.com/polymarket-us-five-minute-crypto-markets/)
- [Polymarket launches 5-minute markets on its US app (Prediction News)](https://predictionnews.com/story/polymarket-launches-5-minute-crypto-up-down-markets-on-us-app)
- [Polymarket US 5-minute markets amid CFTC review (Coin Edition)](https://coinedition.com/polymarket-us-launches-5-minute-btc-eth-sol-xrp-markets-amid-cftc-probe/)
- [Stanford study on 5-minute market settlement (Cointelegraph)](https://cointelegraph.com/news/stanford-study-5-minute-bitcoin-prediction-markets-enable-settlement-manipulation)
- [Polymarket's TWAP settlement upgrade (Crypto Briefing)](https://cryptobriefing.com/polymarket-twap-upgrade-liquidity-rewards/)
- Polymarket US (QCX LLC) rule filings at the CFTC, for example [this Oct 20 filing](https://www.cftc.gov/filings/orgrules/rules10202635268.pdf).
  The search summary drew "CF Benchmarks" and "5-minute periods allowed" from these filings, but did not say which
  filing holds which line. Not read in full.
- Our own: `reports/Short-term crypto venues update Oct 18.md`, `reports/Kalshi vs Polymarket US BTC.md`,
  `research/kalshi_15min/THRESHOLD_SEARCH_PREREG.md`, `research/kalshi_15min/FILTER_SEARCH_PREREG.md`.
