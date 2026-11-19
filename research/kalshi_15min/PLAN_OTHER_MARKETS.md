# Plan: the favorites rule on Kalshi's other markets

Draft, Sep 29 2026. Status (Oct 9): step 1 of the data fetch is done (`python fetch_other.py list`
wrote `other_markets.json` on Sep 29). Step 2, `python fetch_other.py candles`, which writes the
`other_hours.csv` the analysis reads, hasn't been run. `other_markets.py` is written and tested on
synthetic data. No results yet.

Status (Oct 12): the data is in (markets closed Jul 23 – Sep 30) and the pass test has run once:
hourly temperature (10 and 30 min before) and daily AAA gas prices (1 and 2 h before) passed, with
caveats. See `other_markets_findings.md`. Depth check started Oct 12: the trade tape (depth_tape.py) says $10 traded
at the ask on only 8-45% of test-half bets, and capped at what traded the edge is +0.2-2.3c a bet; the live book
recorder (depth_books.py) runs until Oct 20 for the real answer.

## The idea

Buy the favorite when it costs 90–99.9¢, a fixed time before the market closes, and hold it to
settlement: the same rule the bot runs on 15-minute markets, moved to Kalshi's hourly, daily and
weekly markets. The 15-minute version breaks even at best (−0.4¢ a $10 bet with live-like fills, and
every account replayed from Jul 18 went broke), most likely because those markets are the most
contested on Kalshi: fast bots arbitrage them against the coin's spot price second by second. The bet
is that the same bias is bigger and less contested elsewhere.

## Why it might work

- **The bias is Kalshi-wide.** Over 300,000 Kalshi contracts, contracts above 50¢ earned a small
  positive return before fees and longshots lost over 60%, in every category tested ([Bürgi, Deng &
  Whelan][kalshi]). Their fitted lines put the pre-fee profit on a 95¢ contract near +1.6¢ in
  financials, +2.0¢ in climate and weather and +3.6¢ in crypto (Table 8; politics and entertainment
  show no clear slope).
- **Nobody has measured the hourly markets.** That study left out every market open under 24 hours,
  which is where Kalshi's biggest volume now is (hourly Bitcoin above/below alone: $243M since Jul 18).
- **Longer horizons, bigger bias.** The bias grows with time to expiry ([Page & Clemen][pc]), so a
  daily market bought hours before its close may be mispriced more than a 15-minute one at minute 8.
- **Late favorites pay takers.** On Betfair, taking the favorite late in a match is where takers
  profit ([Whelan][betfair]), the same shape of bet.

## Why it might not

- The bias is shrinking: the 2025 slope is the weakest in the Kalshi study.
- Hourly crypto settles on the same 60-second CF Benchmarks average as the 15-minute markets and draws
  the same bots.
- Most deep favorites in a strike ladder or temperature range have no one on the other side; a
  recorded 99¢ ask may have one contract behind it.
- The 15-minute rule was chosen on one month and failed on the month before it. The same mistake is
  easy to make on 200 series.

## What's available (Kalshi's catalog, Jul 18 – Sep 29)

683 hourly, daily and weekly series; 211 had markets close in the period: about 1 million markets,
202,000 of them traded. Fee multiplier 1 on almost all, including the 15-minute crypto series (the
README's open question on crypto fees: settled, it's 1). Only 159 of Kalshi's 14,494 series charge
maker fees.

| Candidate | Series | Volume since Jul 18 | Why | Watch for |
|---|---|---|---|---|
| Hourly crypto above/below and ranges | KXBTCD, KXETHD, KXBTC… (13) | $262M | Biggest volume on Kalshi; unstudied | Same bots and settlement as the 15-minute markets; every strike in an hour moves together |
| Daily weather | KXHIGHNY, KXHIGHMIA, KXRAIN… (44) | $116M | Retail-heavy; the bias is clear in weather; forecasts give a fair value later | Settles next morning on one NWS station's climate report |
| Esports maps | KXCS2MAP | $83M | Big volume; in-play favorites | Match-fixing and scheduling risk |
| Commodities, daily and hourly | KXWTI, KXGOLDD, KXSILVERH, KXBRENTD (9) | $51M | Same shape as the 15-minute metals and energy markets, longer horizon | Thin books on hourly |
| Economics daily | KXAAAGASD… (27) | $34M | Slow-moving underlying | Few markets a day |
| Stock indexes, hourly | KXINXU, KXNASDAQ100U (4) | $31M | Financials have a clear bias | Market hours only |

One helpful property of range markets: in a set of mutually exclusive ranges only one can settle YES,
so buying NO on several far ranges of the same event loses at most one of them.

## The backtest

1. **Data** (`fetch_other.py`). `list`: every settled market in those series, a week at a time
   (Kalshi's listing stops after about 30,000 markets). `candles`: each traded market's YES bid and
   ask for its last 60 minutes (hourly series) or 24 hours (daily and weekly), at the end of each
   minute or hour.
2. **Rule** (`other_markets.py`). At each checkpoint (45, 30, 20, 10, 5 minutes before the close of an
   hourly market; 12, 6, 3, 2, 1 hours before a daily or weekly one), buy the favorite if its ask is
   90–99.9¢. $10 a bet, taker fee with the series' own multiplier, filled 0.4¢ a contract worse than
   the recorded ask.
3. **Honest error bars.** 95% ranges clustered by close time, since markets that close together (an
   event's ranges, every crypto series at the top of the hour) win and lose together.
4. **A liquidity screen.** Every result also shown only where the bid was within 3¢ of the ask.
5. **Out of sample, decided in advance.** Choose categories and checkpoints on Jul 18 – Aug 31 only,
   then test those exact choices once on Sep 1 – Sep 29. Anything picked from the full table is a
   candidate, not a result.

### What counts as a pass

- At least +2¢ a $10 bet with live-like fills in **both** halves, and the 95% range above zero on the
  test half.
- At least 1,000 bets in the test half, from at least 5 different series or 20 different days.
- A survivable worst day at $10 a bet on $240 (under 30%).

## If something passes

1. **Depth check (1 week).** Log the full order book at each checkpoint for those series, to see
   whether $10 fills at the recorded ask. (This plan first said to extend the research paper trader,
   which was retired on Oct 9; the bot's dry run, `python bot.py`, reads live books without ordering
   and is the closer fit now.)
2. **Paper trade (2+ weeks)** with the live rule's halts and sizing, as its own account.
3. **Bot changes**, only then: series and checkpoint from config instead of the 15-minute schedule;
   fee multiplier per series; a cap per event and per close time in place of the per-window cap;
   settlement that can arrive the next morning (weather).
4. **A fair-value filter** for the category that passes: NWS forecasts for weather, the coin's
   distance to the strike and its volatility for hourly crypto. Skip favorites the model says are
   priced above their chance.

## Not in this plan

Selling early (never beat holding, `exit_timing.py`), resting limit orders (need the trade tape), and
Kalshi–Polymarket gaps (need Polymarket data, and fees take most of the gap).

[kalshi]: https://www2.gwu.edu/~forcpgm/2026-001.pdf
[pc]: https://academic.oup.com/ej/article-abstract/123/568/491/5079498
[betfair]: https://www.karlwhelan.com/Papers/Betfair.pdf
