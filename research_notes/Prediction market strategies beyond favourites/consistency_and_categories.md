# Consistency between related contracts, and category biases (research as of 26 Oct 2026)

How to read these notes:
- "Gross" or "before fees" means Kalshi's fee and the spread are NOT taken off. "Net" means they are.
- Kalshi taker fee = 7% x price x (1 - price) per contract. At 50c that is 1.75c. At 90c or 10c it is 0.63c.
- "pp" = percentage points. A 40c contract that wins 37% of the time is 3 pp worse than its price.
- "Maker" = the trader whose order was resting in the book. "Taker" = the trader who crossed the spread to hit it. The bot is a taker.
- Strength labels: STRONG = large real-trade study or peer review. MEDIUM = careful but unrefereed preprint or open-source study. WEAK = vendor, one-day snapshot, or news summary.

---

## 1. Strike ladders and bracket sets on Kalshi: how often do they break the basic rules, and is it tradable after fees?

### Takeaway
Almost never in a form you can trade. The only Kalshi-specific measurements found (one open-source screen, one vendor scanner, both from September 2026) found zero real arbitrage left after the spread, depth and fees. Most "violations" are stale quotes or mid-price artifacts.

### Cited findings
- **Open-source bracket screen (MEDIUM, tiny sample).** One afternoon, 10 Sep 2026: 382 legs across 28 Kalshi events, polled once a minute for 85 minutes (2,380 event-minutes, 32,470 quotes). Source: [nnotyan/kalshi-bracket-pricing](https://github.com/nnotyan/kalshi-bracket-pricing)
  - A naive screen flagged 779 of 2,380 event-minutes (32.7%) as a Dutch book (a set of bets that pays more than it costs, whatever happens).
  - On competitively quoted events, 97.1% of flags were fake: 56.8% came from legs that do not cover every outcome, and 40.3% from stale quotes.
  - Only 6 event-minutes showed a real gross edge (profit per contract, before fees), and each was "smaller than the fee."
  - **Survivors after structure, staleness, depth and fees: 0**, at all five trade sizes tested.
  - Ladder check (a higher strike must not cost more than a lower one): **no violations** across three ladders in 85 minutes.
  - Summing the 80 rungs of a Bitcoin "above X" ladder against $1 gave a fake "$30.99 edge". The author calls this a category error. Ladders are not a set of outcomes that add to 100c.
  - Biggest real gap: a 14-leg GDP bracket (KXGDPYEAR-34) buyable at 98c for $1, so about 2c gross. After fees: **-4.25c at 1,000 contracts and -12c at one contract**. Quotes only; nothing traded.
  - Median half-spread per leg: 0.48c to 0.83c. The no-trade band (the range where nothing is profitable after costs) is 5c to 11c wide, growing with the number of legs.
  - Fee example: a three-way coin flip costs about 4.7c in fees to assemble (checks out: 3 x 1.56c). The same page says a 28-leg bracket costs about 0.7c; the project's own check with equal legs gives about 6.7c, so treat that figure with care.
  - Author sells nothing (MIT-licensed code). The author says the sample is too short to say how often real gaps occur. Fills were not tested.
- **Vendor ladder scanner (WEAK, one-day snapshot, sells subscriptions).** Measured live on 12 Sep 2026, pre-kickoff only. Source: [PredictionMarketsPicks ladder scanner](https://predictionmarketspicks.com/tools/ladder-scanner)
  - College football spread ladders: 105 of 1,809 neighbouring strike pairs were out of order **at mid-price** (5.8%). NFL: 1 of 349 (0.3%).
  - Pairs that could be locked in at the actual bid and ask (true arbitrage): **zero**, including across a full September Saturday board.
  - Mid-price inversions need resting orders to fill. That is market making, not taking.
  - No profit figures for the ladder tool. The site sells Pro plans ($111 first year, then $150/yr, or $14.99/mo) and has affiliate/referral links.
- **Kalshi's "Collateral Return" setting** changes the cash needed for bracket trades. In a group of mutually exclusive markets, buying No on two candidates costs $1.30, but Kalshi hands back $1 at once, because at most one can win. Max loss is $0.30. It is off by default. It is locked in at your first order in that event. It may stop you selling positions that already had collateral returned. Source: [Kalshi Help: Collateral Return](https://help.kalshi.com/trading/advanced-options/collateral-return)

### Inferences
- Fee hurdle for a two-leg ladder trade (buy Yes at the lower strike, buy No at the higher strike): near 50c, fees are about 1.75c per leg, so the inversion must beat about 3.5c at the asks. Near 90c/10c it must beat about 1.3c. Both screens found no executable inversions at all, so the hurdle is not even reached.
- For a fast taker bot, the realistic version is "notice one rung that is stale after the underlying moves", rather than "find a crossed book". That is speed trading on a ladder, which earlier notes already cover.
- Ladders exist in bulk for crypto (KXBTCD "above X") and brackets for crypto (KXBTC) and economics. These are the most heavily quoted by market makers, which is why they look clean.

### Gaps
- No study measures ladder or bracket violations on Kalshi over weeks or months. Both screens above cover one day.
- No measured, net-of-fees profit from Kalshi ladder or bracket arbitrage was found anywhere.
- A search snippet mentioned a non-monotonic H200 compute-price ladder on Kalshi (kineticalpha.com). It was not opened, so it is unverified.

---

## 2. Combinatorial and conditional arbitrage between different but linked markets

### Takeaway
The large studies are all on Polymarket. They find linked-market arbitrage is real but small, very short-lived (seconds), thin (30 to 40 shares at the best price), and taken mostly by a handful of fast accounts. The one Kalshi study of linked prices (parlays vs their legs) found parlays priced above their legs, but tested no strategy. No study of Kalshi cross-horizon (15-minute vs hourly vs daily) or Fed-cut vs rate-bracket consistency was found.

### Cited findings
- **Saguillo, Ghafouri, Kiffer, Suarez-Tangil, "Unravelling the Probabilistic Forest" (arXiv 2508.03474, Aug 2025; the IMDEA copy's file name suggests AFT 2025, not confirmed). MEDIUM-STRONG.** Polymarket, markets resolved 1 Apr 2024 to 1 Apr 2025: 8,659 single-condition and 1,578 multi-outcome markets (17,218 conditions). Sources: [arXiv HTML](https://arxiv.org/html/2508.03474v1); [abstract](https://arxiv.org/abs/2508.03474); [IMDEA PDF](https://suarez-tangil.networks.imdea.org/papers/2025aft-arbitrage.pdf)
  - Total extracted by all arbitrage types: about **$39.6M** (abstract says ~$40M).
  - Single market, Yes+No: about $5.90M from buying both below $1, $4.68M from selling both above $1.
  - Within a multi-outcome market: buying Yes ~$11.09M; buying No ~$17.31M.
  - **Combinatorial (across different markets): tiny.** An LLM flagged 1,576 dependent pairs in the 2024 US election group. Manual review kept only 13. Extracted profit on 4 pairs: ~$60.2K, ~$18.5K, ~$15.8K, ~$629, so about **$95K total, roughly 0.2% of all arbitrage profit**. (The paper is inconsistent on 11 vs 13 pairs.)
  - The LLM got many links wrong: swing state vs national results, popular vs electoral vote, Senate vs House.
  - Threshold: at least 5c profit per $1. No fees deducted (Polymarket charged none then). Prices are volume-weighted averages, not tested fills. Legs fill one at a time, so one leg can fill and the other miss.
- **Shi and Zhai, "Combinatorial Arbitrage in Prediction Markets" (arXiv 2610.23517, v1 16 Oct 2026, v3 20 Oct 2026; SSRN 7587019). MEDIUM (unrefereed, very new).** Polymarket only, 23 Jun to 3 Aug 2026 (42 days), ~745,000 contracts, full order-book replay. Sources: [arXiv abstract](https://arxiv.org/abs/2610.23517); [arXiv HTML](https://arxiv.org/html/2610.23517); [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7587019)
  - Found 1,942,133 logical links over more than 255,000 contracts. Types: "A implies B" (most common), "A and B cannot both happen", full partitions, and "A and B" combos.
  - Includes cross-horizon links, e.g. "BTC above X today" implies "BTC above lower X this month".
  - **Ideal arbitrageur, after spreads and fees, taking all displayed depth and reusing cash at resolution: $2.50M guaranteed profit, about 3.5% a week on $11.1M peak capital.** Taking only the first execution in each window: $1.10M.
  - Where the profit came from: Polymarket's own linked groups 34%; sports lines (spread/total ladders mapped to one score) **59%**; LLM-found links 7%.
  - **Median window length: 2.9 s (Polymarket groups), 6.3 s (sports lines), ~31 s (LLM-found links).**
  - Median depth: 40 shares at the best bid, 30 at the best ask. Median spread 8c.
  - Who takes it: 854 addresses; **the top 10 take 78%** of the windows that someone took. Median reaction about 3 s.
  - A 1-second order delay still keeps 79% of profit.
  - Simulation against recorded books, not the authors' own trades. Kalshi data not used (Kalshi does not show who traded).
  - Note: an early search summary quoted "2.2% of committed capital, 3.2% at resolution". Those numbers could not be found in the paper or abstract. The abstract says 3.5% a week.
- **Gebele, Mutzel, Matthes, "Executable Arbitrage and Market Efficiency in Prediction Markets" (arXiv 2608.00666, 1 Aug 2026). MEDIUM.** Polymarket multi-outcome events. Order-book sample 14 Apr to 19 May 2026; trader-level sample through 31 Dec 2025. Source: [arXiv HTML](https://arxiv.org/html/2608.00666v1)
  - Real realized arbitrage profit: about **$1.12M** total. About $1.086M came via Polymarket's "converter" (turning a set of No positions back into cash plus Yes positions, which frees capital). Only $32K came from holding a full set to resolution.
  - Fees and depth are included; spreads estimated.
  - Profitable gaps were almost all on the Yes side: 2,098 Yes-side episodes vs 36 No-side.
  - Median life of a timed episode: about 16 s. About 59% of episodes ran past the 50-minute window, so many lasted longer.
  - Kalshi's Collateral Return is described as the Kalshi version of capital recycling, but Kalshi was not measured.
- **Moshrefi, "Prices, Probabilities, and Parlays" (arXiv 2607.14430, 15 Jul 2026). MEDIUM.** The only linked-price study on Kalshi found. Source: [arXiv HTML](https://arxiv.org/html/2607.14430v1)
  - 12,639 cross-game Kalshi parlays with 2 to 11 legs, 29 Apr to 13 May 2026.
  - Parlay price divided by the product of its legs' prices (above 1 = parlay is dear): median 0.991 at 2 legs, 1.005 at 5, 1.066 at 8, 1.223 at 10 (n = 57), 1.305 at 11 (n = 12). About **3% markup per extra leg**.
  - Parlays won 2 to 10 pp less often than their price said. Example: a 30c parlay wins about 24% of the time.
  - Prices exclude fees. **No trading strategy or return was tested.**
- **Nechepurenko, "On-Demand Combinatorial Event Markets on Kalshi" (arXiv 2609.17610, Sep 2026). WEAK for trading (structure only).** Author is at a private firm (Devnull FZCO). Source: [arXiv PDF](https://arxiv.org/pdf/2609.17610)
  - 7,611,594 combo market tickers created in 7 days (15 to 22 Aug 2026). 94.8% were in one collection. Only 35.4% had any volume or open interest when checked.
  - Combo markets are made on demand when someone asks for that exact set of legs.

### Inferences
- Linked-market arbitrage pays most where links are mechanical (spread and total ladders on the same game). That is the same thing as question 1, and on Kalshi the September 2026 snapshots found nothing executable.
- The windows last seconds and are thin. A bot at Kalshi's own AWS region has the speed. But the 30 to 40 share depth caps profit per window at small dollars.
- Kalshi parlays priced above their legs (by about 3% per leg) suggests money for whoever SELLS parlays and hedges with legs. On Kalshi, parlay prices come from quotes by market makers. So this is market making, which earlier notes already cover.
- Kalshi cross-horizon crypto links (a 15-minute market vs the hourly or daily one on the same index) are the closest Kalshi version of the "today implies this month" links. In the Polymarket study, that kind of link was a small share of profit (LLM-found links: 7%).

### Gaps
- No study of Kalshi 15-minute vs hourly vs daily crypto consistency was found.
- No study of Kalshi "Fed cuts in December" vs the rate-level brackets was found. One study (see question 3) found Kalshi Fed, CPI and index brackets very well calibrated, which suggests little room.
- No study of "team wins title" vs "team wins each round" on Kalshi.
- No Kalshi study with real, net-of-fee arbitrage profits across linked markets.

---

## 3. Whole categories that are mispriced (other than favourites vs longshots)

### Takeaway
The strongest new evidence is a "Yes bias" (traders overpay for Yes) that is concentrated in "single-name" markets: mention markets, celebrity and company events, entertainment. A large 2026 study finds Yes in those markets priced 4.5 pp above how often it wins, and 8.6 pp in the 40c to 49c range. Economic, index and crypto bracket markets are almost perfectly calibrated. All of these numbers are before fees.

### Cited findings
- **Bartlett (Stanford) and O'Hara (Cornell), "Adverse Selection in Prediction Markets: Evidence from Kalshi" (first version 16 Apr 2026, this version 2 Jul 2026; NBER conference paper; SSRN 6615739). STRONG (large real-trade data, top authors; not yet published).** 41.6M trades, 478,167 Kalshi markets, July 2021 to 11 Mar 2026. **Ignores fees.** Sources: [NBER conference PDF](https://conference.nber.org/conf_papers/f243677.pdf); [Stanford Law page](https://law.stanford.edu/publications/adverse-selection-in-prediction-markets-evidence-from-kalshi/)
  - "Single-name" = about one company or person: earnings-call word mentions, Trump speech content, press-conference mentions, Super Bowl attendance, Spotify and Netflix rankings, IPOs. 15,516 markets.
  - "Broad-based" = economic data, indices, rates, crypto and FX ranges.
  - **Calibration (whether a 40c price really wins 40% of the time), first 80% of each market's trading life:**
    - Single-name: Yes priced **4.5 pp too high** on average (standard error 0.44, 6,386 markets).
    - Worst in the middle: contracts priced in the 40s won only **37%** of the time, 8.6 pp short.
    - Yes is overpriced "at every probability level", not just at the extremes.
    - Broad-based: just 0.2 pp off (standard error 0.11, 114,802 markets). Effectively fair.
  - By category (same measure, from the appendix): entertainment +3.1 pp; "other" +2.4 pp (partly mention-type markets); sports +1.3; politics +1.1 (wide error, 0.58); weather +1.0; broad-based +0.2.
  - Who buys Yes (volume-weighted): single-name takers buy Yes 60.9% of the time, but Yes settles only 32.5% of the time. Broad-based: 56.3% buy Yes, Yes settles 39.1%.
  - Makers earn 1.91c per contract on single-name and 0.82c on broad-based, before fees.
  - From the paper's Table 7 (maker P&L split by taker side and outcome), single-name markets, before fees:
    - Yes takers lost $18.22M on No-settling markets and won $8.31M on Yes-settling ones.
    - No takers won $11.97M on No-settling markets and lost $6.65M on Yes-settling ones.
  - The maker's "frequency edge" (winning more often) on single-name rose from near 0 in early 2024 to about +8c per contract by early 2026. Net maker profit stayed at 1c to 3c, because losses on informed flow grew too.
  - Fees named in the paper: Kalshi taker fees of 0.07c to 1.75c per contract; some maker fees from April 2025.
- **Wall Street Journal analysis of mention markets (Mehta, Long, Ostroff, 2026), as cited by Bartlett and O'Hara. MEDIUM (journalism, large sample).** Over 35,000 Kalshi mention markets: Yes bets priced at 50% won only about 40% of the time. The average Yes bettor lost roughly 11% of the stake. Cited in [Bartlett and O'Hara, NBER PDF](https://conference.nber.org/conf_papers/f243677.pdf); secondary summary at [CCN](https://www.ccn.com/news/crypto/kalshi-traders-outperform-day-traders-new-data-shows-who-actually-wins-more/)
- **Becker, "The Microstructure of Wealth Transfer in Prediction Markets" (2025). MEDIUM-STRONG (72.1M trades, open data; blog, not refereed). Gross of fees.** Kalshi, June 2021 to 25 Nov 2025: 7.68M markets, $18.26B volume. Markets under $100 volume dropped. Sources: [jbecker.dev](https://www.jbecker.dev/research/prediction-market-microstructure); [data and code](https://github.com/jon-becker/prediction-market-analysis)
  - Yes vs No: No beat Yes at 69 of 99 price levels, mostly at 1c to 10c and 91c to 99c.
  - At 1c: Yes returned -41%, No returned +23%.
  - Dollar-weighted: Yes buyers -1.02%, No buyers +0.83%.
  - Takers do 41% to 47% of Yes buying at 1c to 10c.
  - Early Kalshi (launch through 2023): takers made +2.0% and makers lost. This flipped after the 2024 election.

  Becker's taker returns by category (average return per trade for the taker, before fees):

  | Category | Taker return per trade (before fees) | Trades |
  |---|---|---|
  | Finance | -0.08% (about fair) | 4.4M |
  | Politics | -0.51% | 4.9M |
  | Sports | -1.11% | 43.6M |
  | Weather | -1.29% | 4.4M |
  | Crypto | -1.34% | 6.7M |
  | Entertainment | -2.40% | 1.5M |
  | Media | -3.64% | 0.6M |
  | World events | -3.66% | 0.2M |

- **Bürgi, Deng, Whelan, "Makers and Takers: The Economics of the Kalshi Prediction Market" (UCD working paper, Jan 2026; also CESifo and CEPR versions). STRONG (careful academic study; includes taker fees).** 313,972 Yes and No contracts, Kalshi launch to April 2025. Sources: [Whelan PDF](https://www.karlwhelan.com/Papers/Kalshi.pdf); [CESifo](https://www.ifo.de/en/cesifo/publications/2026/working-paper/makers-and-takers-economics-kalshi-prediction-market)
  - Contracts at 10c and under lost over 60% after fees. Above 70c: small but real positive returns after fees.
  - The favourite-longshot pattern appears in every category. It is weakest, and not statistically clear, in politics and entertainment. Strongest slope: crypto.
  - The bias is weaker in 2025 data.
- **Le, "Decomposing Crowd Wisdom: Domain-Specific Calibration Dynamics" (arXiv 2602.19520, v1 23 Feb 2026, v2 4 Aug 2026). MEDIUM.** 353M trades, 429,000 contracts on Kalshi and Polymarket. Source: [arXiv](https://arxiv.org/abs/2602.19520)
  - Clearest pattern: politics prices are squeezed toward 50% (favourites too cheap, longshots too dear). Holds on Polymarket too.
  - Big political trades on Kalshi squeeze prices further. Not robust on Polymarket.
  - About half of the raw variation is estimation noise. No trading test.
- **Tailor, open-source calibration study (2026). MEDIUM, sells nothing.** 16,533 Kalshi and 29,635 Polymarket markets, 2021 to 2026. Source: [hrishi-tailor/prediction-market-calibration](https://github.com/hrishi-tailor/prediction-market-calibration)
  - Kalshi politics is the most biased category (slope 1.28; above 1 means longshots too dear, favourites too cheap).
  - The bias lives in thin markets: least-traded third slope 1.18, most-traded third 1.02.
  - After spread and taker fee: buying longshots at the ask lost 89% per dollar at 0c to 2c and 34% at 10c to 20c. Buying favourites or fading longshots lost 0% to 2%.
  - A correction learned on markets before July 2025 did not beat market prices on later markets.
- **Conflict to flag:** Whelan finds the favourite-longshot pattern weakest in politics. Le and Tailor find politics the most squeezed. Different years (Whelan stops April 2025) and different measures.

### Inferences
- A rough "buy No" sum from Bartlett and O'Hara's Table 7: on single-name markets, No takers as a group netted about +$5.3M before fees (11.97 - 6.65). That is over roughly 100M No-taker contracts (39.1% of 259.9M), so **about 5c per contract before fees**. Yes takers netted about -$9.9M. This is the project's own arithmetic, not the paper's. It mixes informed No buyers (like the Bezos case) with everyone else. Treat it as an upper bound, not a forecast.
- Fee check for a No buy at 60c (Yes at 40c): 7% x 0.6 x 0.4 = 1.68c. If the 8.6 pp mid-range gap held at the price you pay, about 5c to 7c would be left per contract before spread. But the gap is measured at trade prices, and a taker pays the full spread.
- The main risk is adverse selection (getting picked off by someone who knows more). Single-name markets have the most informed trading of any Kalshi category. The Netflix case (question 4) shows a No-heavy position can be right for the wrong reason, or a Yes spike can be real.
- Fair categories (economics, indices, crypto brackets, Fed) look like poor hunting grounds for category bias. Weak categories: mentions, entertainment, media, world events.
- This fits the project's own experience: the edge is in favourites, which are often the No side in these long-shot-Yes markets.

### Gaps
- No study tests a real "buy No in mention markets" rule net of spread and fees, out of sample. A search for such a backtest found nothing.
- No category numbers found for box office, tweet counts, TSA counts or awards specifically. They may sit inside "entertainment", "media" or "other".
- Bartlett and O'Hara's Figure 7 mentions a single-name gap "reaching +10 to +18 percentage points by early 2026". The part that was read does not make clear which gap that is, so it is not used above.

---

## 4. Edges from reading the contract rules more carefully

### Takeaway
There is one well-documented Kalshi case where rule readers made money fast: the Netflix "Warner Bros" earnings-call market in January 2026. Other rule disputes show the risk side: Kalshi can settle at a pre-event price, and its review committee's decisions are final. Nothing found shows a repeatable, automated rule-reading strategy with measured profit.

### Cited findings
- **Netflix "Will Netflix say 'Warner Bros'?" (KXEARNINGSMENTIONNFLX-26JUN30-WARN), 20 Jan 2026. STRONG (from trade data in an academic paper).** Source: [Bartlett and O'Hara, NBER PDF](https://conference.nber.org/conf_papers/f243677.pdf)
  - About 3 minutes in, the co-CEO said "Warner Brothers". The Yes price jumped.
  - The rules needed the exact phrase "Warner Bros". Traders who knew this bought No.
  - Over 40 minutes, 210,000 No contracts overwhelmed 71,000 Yes. Yes fell from about 90c to below 40c.
  - Makers lost $85,407 during the call. The market's lifetime maker result was -$75,754.
- **Super Bowl guest markets, Feb 2026. STRONG (same paper).** Bezos market opened at 62c, briefly hit 95c, then fell to about 40c on informed No buying. The Wahlberg market opened near 77c and held until game day. Both settled No. Wahlberg takers were 58.9% Yes-heavy, paying 29c on average; makers earned $1.18M. Source: [Bartlett and O'Hara, NBER PDF](https://conference.nber.org/conf_papers/f243677.pdf)
- **Khamenei "out" market, Feb to Mar 2026. MEDIUM (news).** After US strikes on 28 Feb 2026, Kalshi used a "death carve-out" and settled the roughly $54M market at the pre-strike price, not Yes. Kalshi refunded fees and net losses as a goodwill step. A law firm looked at a class action. Sources: [Finance Magnates](https://www.financemagnates.com/fintech/khamenei-out-market-becomes-legal-headache-for-kalshi/); [Forbes](https://www.forbes.com/sites/jasonbrett/2026/03/12/kalshi-death-bet-lawsuit-sparks-push-to-ban-assassination-markets/); [Bitcoin.com](https://news.bitcoin.com/legal-storm-hits-kalshi-as-traders-claim-death-carveout-erased-their-winning-bets/)
- Kalshi then filed a rule making the death carve-out explicit. If no clean last price exists, its Outcome Review Committee sets a fair price. Decisions are final and cannot be appealed. Sources: [DeFi Rate](https://defirate.com/news/kalshi-codifies-death-settlement-rule-in-cftc-filing-amid-backlash-over-iran-market/); [Gaming America](https://gamingamerica.com/news/1044225/kalshi-makes-death-rule-official-after-controversial-khamenei-market)
- From June 2026, Kalshi refunds trading fees to users who lost on disputed settlements, but only for self-clearing members, not users who clear through a broker (FCM). Source: [Gaming America](https://gamingamerica.com/news/1075098/kalshi-will-now-refund-trading-fees-on-disputed-settlements)

### Inferences
- The Netflix gain went to people listening live AND knowing the exact rule text. A bot would need a live transcript plus a parser of each market's rule wording. That is possible but is a new build, and the cases are rare.
- Rule risk is a cost for any bot, not only a source of profit: settlement can be at a pre-event price, by committee, with no appeal.

### Gaps
- No systematic study counts how often Kalshi rule wording, not the real-world outcome, decided a market.
- Search results mentioned NFL season win-total markets graded wrongly in January 2026 (winners refunded their stake but not paid). The original source could not be pinned down, so it is not used above.

---

## 5. Newly listed markets: are they mispriced early, and do early traders profit?

### Takeaway
No outside study measures returns in a market's first hours. Indirect evidence points one way: Yes optimism is larger early in a market's life (in single-name markets) and fades as the close nears. That fits this project's finding that favourites at the very first trade are overpriced, only if the favourite at listing is the Yes side. It says nothing direct about thin 80c to 90c favourites later on.

### Cited findings
- Bartlett and O'Hara: in single-name markets, Yes is priced 4.4 pp too high over the first 70% of trading life and 4.5 pp over the first 80%, but only 2.3 pp over the full life. Late trades are already near the answer. Broad-based markets: 0.2 pp in both early windows. Source: [NBER PDF](https://conference.nber.org/conf_papers/f243677.pdf)
- Opening examples from the same paper: Bezos opened at 62c, Wahlberg at about 77c; both settled No. Source: [NBER PDF](https://conference.nber.org/conf_papers/f243677.pdf)
- Bürgi, Deng, Whelan: prices get more accurate as markets near the close. But the favourite-longshot slope is about the same from 0 to 10 days before close (coefficients 0.017 to 0.041, all statistically clear). Source: [Whelan PDF](https://www.karlwhelan.com/Papers/Kalshi.pdf)
- Tailor: bias lives in thin markets (least-traded third 1.18 vs most-traded third 1.02). New listings are usually thin. Source: [GitHub](https://github.com/hrishi-tailor/prediction-market-calibration)

### Inferences
- Early in a single-name or entertainment market, the No side looks like the better buy, before fees. That points the same way as "favourites overpriced at first trade" only when the favourite is Yes.
- The project's "thin 80c to 90c favourites +5c" in new listings is consistent with "thin markets carry more bias, and favourites are underpriced". No outside source tests that exact rule.

### Gaps
- No study of profit in a market's first hours on Kalshi or Polymarket was found.
- No source measures the spread at listing time, which this project also has not measured.
