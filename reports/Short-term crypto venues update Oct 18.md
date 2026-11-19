# Short-term crypto venues: Oct 18 update

*Updates `Short term prediction market venues.md` (Oct 13). Covers every crypto contract shorter than about an hour (1, 5, 10, 15 and 30 minutes). Web research Oct 18, plus our own check of Gemini's recorded books against Kalshi (Oct 13–16).*

## The answer

**For a US resident running a bot, the only real option besides Kalshi is still Polymarket US**, and it now covers 4 of the bot's coins. Everything else is in one of these groups:

- **Offshore:** closed to US residents.
- **Resellers:** they just pass orders into Kalshi's own book.
- **Too thin or too dear:** Gemini.
- **Killed by fees:** Crypto.com's flat 2¢ a contract.

No US venue offers a usable **5-minute** market for this strategy.

## US venues with their own order book

| Venue | Short windows | Same settlement as Kalshi? | Verdict |
|---|---|---|---|
| **Polymarket US** | 15 min on **BTC, ETH, SOL, XRP** (ETH/SOL/XRP added about Oct 15); 1 h and daily too. No 5 min yet | **Yes.** Same CF Benchmarks indexes, same 60-second average. BTC matched in 206 of 206 windows | **Only real option.** BTC favourites cost about 0.3¢ more but the books are much deeper. Extra capacity, not new bets. Ohio: the Oct 16 state order covers sports only; no crypto block found (not confirmed) |
| **Gemini Predictions** | 5 and 15 min on BTC, ETH, SOL, XRP | **No.** It settles on the Lukka index. Final values differed by a median $2.72, and **4 of 224 BTC windows came out opposite** | **Fails.** Spreads of 7–10¢, about $10 on offer at the favourite's price, and the favourite about **3¢ dearer** than on Kalshi |
| **Crypto.com / OG** (ex-Nadex) | 5 min to weekly on many coins | Own index | **Fails on fees.** A flat $0.02 a contract makes 99¢ favourites a sure loss. A new order-book screen launched Oct 15, and a third-party trading API was announced with no date |

**Kalshi itself:**
- Nothing shorter than 15 minutes.
- It lists 15-minute FX (5 currency pairs). The bot skips those on purpose, because their costs eat the edge.
- Its 15-minute stock-index series exist but have no markets.

## Resellers (same Kalshi book, nothing new)

- **Robinhood:** Kalshi's BTC/XRP 15-minute markets. Its own exchange, Rothera, is sports only.
- **Coinbase:** Kalshi's 15-minute markets on 10 coins.
- **tastytrade:** Kalshi's crypto markets.
- **Webull:** has an API, but orders still land in Kalshi's book after an extra hop.
- **DraftKings:** resells Crypto.com's 5-minute BTC/ETH markets, so it carries the same 2¢ fee problem.

## Offshore: closed to US residents

| Venue | Short windows | Notes |
|---|---|---|
| Polymarket (international) | 5 and 15 min on 8 coins | Order book and API; London servers |
| Limitless (Base) | 5 and 15 min, BTC/ETH | US licence still pending |
| OKX Event Contracts | 5 and 15 min, BTC/ETH/SOL, plus gold | Order book and API (newly found) |
| Gate Event Contracts | 5 min to 4 h on 7 coins; 5/15-min stocks | Newly found |
| Bybit Odds | 5 and 15 min, BTC/ETH | Fixed payouts set by market makers; a tie loses (newly found) |
| Binance Event Contracts | 10 and 30 min, BTC/ETH | App only, fixed payouts (newly found) |
| Myriad (BNB Chain) | Rolling 5-minute markets | Newly found |
| Hyperliquid | Daily only | Nothing shorter |

Using these from the US would break their terms, and the CFTC has fined venues for serving US users. **Not an option.**

**On-chain betting pools** (Overtime "speed markets" at 1 minute and up, PancakeSwap 5-minute rounds) take 3–17% of each bet. That's far more than the edge.

## What changed since Oct 13

1. **Polymarket US added ETH, SOL and XRP** 15-minute markets, on the same indexes as Kalshi.
2. **Polymarket US maker rebates end Oct 19** for anyone under $10M a month. The taker fee is unchanged, so this doesn't affect a taker bot.
3. **Gemini's index is now public:** Lukka. That explains the price differences we measured.
4. **Crypto.com got an order-book screen** and an announced third-party API. Its 2¢ fee still rules it out.
5. **No new US exchange with short contracts.** Limitless is still pending, Blockchain.com filed about Oct 9, and Kraken hasn't launched.

## Not verified

- Polymarket US access from Ohio.
- The exact ETH/SOL/XRP launch date.
- Whether OKX, Bybit, Gate and Binance block US users (assumed, as is usual).
- Webull, CME, FanDuel and Cboe weren't rechecked.
