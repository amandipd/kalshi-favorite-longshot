# What a 3-crypto-bet cap would have done to the live test (Oct 28)

**Short answer: it would have cost money. With the cap since the live start, profit would be about $47 instead of $190. The bets it drops are mostly winners. It would have softened the two worst windows, but the deepest fall (the worst drop from a peak) would have been deeper, not shallower. Don't add it.**

## What was replayed

- **The rule** (from the Oct 11 research, `research/kalshi_15min/lab/edge_map.py`): in each window, keep at most 3 crypto bets. Keep the 3 with the smallest spread (the gap between the buy and sell price), then the highest price. Metals and energy bets are untouched.
- **The data:** every live bet from the live start (Oct 15) to Oct 28, 6:31 PM ET, 2,718 bets, all settled. The spread is the one the bot recorded when it placed each order. Live ledger, read-only.
- **Two versions:**
  - **A:** the dropped bets are simply not placed. The other bets stay exactly as they were.
  - **B:** the same, but the kept bets get bigger, as the bot's own rule would make them. Each bet is 1.5% of the account, or less when a window has many bets (10% of the account split across them). Fewer bets means bigger ones. This assumes the bigger orders fill just as well.

## The result, whole test

- **230 of 788 windows** had 4 or more crypto bets, so the cap would have changed them. It drops **720 bets**.
- **Actual:** won 2,638 bets ($1,401), lost 80 ($1,211). **Net +$190.27**, or +0.49 cents of profit for every dollar bet.
- **With the cap (A):** won 1,931 ($1,115), lost 67 ($1,068). **Net +$46.75**, or +0.16 cents for every dollar bet.
- **With the cap and bigger kept bets (B):** net +$48.48. About the same as A.
- **The 720 dropped bets:** 707 won ($286) and 13 lost ($142). **Net +$143.52**, or +1.56 cents for every dollar bet. They lost 13 where prices predicted 23. They were some of the best bets.

**So the wins do drop a lot.** Dollars won fall by 20%. Dollars lost fall by only 12%. Each dropped win is small (about $0.40), but there were 707 of them.

## Since Oct 20 (the setup being judged)

- **Actual:** net +$7.94, about break-even.
- **With the cap:** net −$105.61, or −0.51 cents for every dollar bet.
- **The dropped bets:** 490 won, 9 lost, net +$113.55.

## Did it at least make the ride smoother?

Only in the worst windows. Overall, no.

- **Worst single window:** −$73.98 (Oct 22, 9:30 PM ET) becomes −$54.43 (Oct 28, 5:15 PM ET, which had only 3 crypto bets, so the cap changes nothing there).
- **The two crypto-wide windows:**
  - Oct 21, 4:30 AM: the cap keeps HYPE (won), XRP (lost) and BTC (lost). It drops 3 losers and 1 winner.
  - Oct 22, 9:30 PM: the cap keeps HYPE (lost), SOL (lost) and BTC (won). It drops 5 losers and 1 winner.
  - These two windows are where the cap helps. It saves about $70 here.
- **Everywhere else, it only drops winners.** Outside those two windows, the dropped bets lost just 5 times in about 700 bets.
- **Deepest fall:** $138 actual becomes $199 with the cap. It gets worse, because the profit from the dropped bets was cushioning the bad stretches.
- **Worst 24 hours:** −$93 actual becomes −$120 with the cap.

## Why it worked in the Oct 11 backtest but not here

- **The bot's sizing changed after that research.** The research was run when the bot could put up to 20% of the account into one window. On Oct 15 that dropped to 10%. When a window has many bets, each bet now shrinks so the total stays under 10%.
- **The 10% window limit already does most of the cap's job.** The same research found that a smaller window limit (9%) gave the same worst window as the 3-bet cap (both about −9% of the account). The bot now runs at 10%. So the cap mostly just drops bets.
- **The research said the dropped bets made about nothing.** Live, they made +1.56 cents for every dollar bet. That is partly luck in 13 days. But even at "about nothing", dropping them removes wins and losses together and leaves profit lower.
- **The Oct 13 live check already pointed this way:** on the first 774 live bets, the cap would have dropped +$79.

## What to do

- **Don't add the cap.** It costs profit and the 10% window limit already caps the damage from crowded windows.
- **The crypto-wide windows stay a cost of the strategy.** Over the test, the worst one cost about 6% of the account. The bot halts on a 35% drop within 24 hours, so it is far from that.

Script: `cap3.py`, a one-off script not in the repo (data `capbets.json`). Analysis only. Nothing in `bot/` or the live server was touched.
