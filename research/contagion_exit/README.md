# Sell the other coins when one turns

## Question

The bot buys crypto favourites at minute 8 of a 15-minute window and holds them to the close. Coins move together, so
several bets in one window can flip at once. When one held coin's favourite collapses during minutes 9 to 14, should
the bot sell its other crypto bets before they flip too? (An earlier test had already shown that selling a coin after
its own price collapses loses to holding. This one sells the coins that have not turned yet.)

Four versions (one or two coins turned, selling at 70 or 50 cents or less) and the pass bar (far from luck, better
than holding in both halves of the history, and still better after dropping the best day) were fixed in
`PREREG.md` before any result.

## How to run it

From this folder. It reads the strategy lab's past data, `../kalshi_15min/lab/markets.npz` (built by
`../kalshi_15min/lab/build_markets.py`; see `../kalshi_15min/README.md`).

    python contagion_exit.py               # prints every cell, writes contagion_exit.json

## What it found

It fails. Over 26,686 crypto bets from Dec 20, 2025 to Oct 8, 2026, no version came near the bar (the best was 0.17
on a scale where about 2 is the usual bar for "not luck"), and the two slightly positive versions turned negative
once their single best day was dropped. By the time one coin collapses, Kalshi has already marked the others down 4
to 10 cents in the same minute, and at that new price they win about as often as priced. Selling them then only pays
the spread and a second fee. The write-up is in `reports/` ("Sell the other coins when one turns Oct 28").
