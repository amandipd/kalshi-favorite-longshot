# Thin-market recorder: plan (not built)

Written 26 October 2026. Nothing built, nothing running.

## Why

Thin "No" favourites priced 80 to 90 cents earned about 8 cents of profit per
contract on past data (see `reports/Yes vs No favourites split Oct 26.md`).
"Thin" means the market traded little over its life.

That number used prices someone else paid. We have never seen the real order
book in these markets. The order book is the list of prices people are
offering, and how much money sits at each. So we don't know three things:

1. **What it costs us to get in.** If the cheapest offer is more than about
   3 cents above the last paid price, most of the profit is gone.
2. **How much money fits.** A thin market may only have a few dollars on offer.
3. **Whether a bot can spot "thin" in advance.** The past test used total volume
   over the market's whole life, which is hindsight.

The recorder answers those three. It trades nothing.

## One timing fact that shapes the design

Sports markets seem to close around when the game ends, not at a fixed time. A
sample NBA spread market closed at 9:55 pm Eastern on game night. So "one hour
before close" in the past data likely means **about an hour before the game
ends**, which is mid-game. The recorder will confirm this.

A live bot can't know when a game will end. So the recorder also logs game start
(when trading picks up) and the real close. Then we can test an entry rule a bot
can actually use, like "a set time after the game starts".

## What it records

**Which markets.** Open markets in the series that made up the past result and
are in season now. A scan on 26 October found about 1,900 open markets:

- NBA spreads and totals (about 620 open)
- NFL spreads (about 360) and NHL spreads (about 70)
- Tennis: ITF men and women, ATP Challenger, ATP, WTA (about 530)
- College men's basketball games, from 3 November (about 300)

MLB is done for the year, so its spreads and totals drop out.

**What, for each market:**

- The top 10 price levels on both sides of the order book, with the money at each
- Last trade price, time, and who set it (a Yes buyer or a No buyer)
- Volume so far
- When trading picks up (game start), when the market closes, and the result

**How often:**

- Every 5 minutes for "hot" markets. Hot means either side is priced 75 to 95
  cents, or the game looks live.
- Every 30 minutes for everything else.
- Once more after close, for final volume, close time and result.

## Where it runs

**A local machine**, as a background process, like the 12 October depth recorder.

- Kalshi's market data needs no account key. A test on 26 October got order
  books back without one. So no key is used and no account is touched.
- It stays off the bot's server. The maker trial showed a recorder there slows
  the server right when the bot places orders.
- It does not touch the bot, `bot/state/`, or any live process.

**Safety limits:**

- At most 3 requests a second. Past notes say to keep everything on one machine
  under 8 a second combined, because other fetches share the same limit.
- If Kalshi says "too many requests", it waits and retries. Every failure is
  logged, not silently skipped.
- It resumes where it left off if the machine sleeps or restarts.
- The machine must stay awake, or the recorder must be restarted after sleep.

**Other option:** the small separate server planned for the maker recorder.
It could host both. It was never set up.

**Disk:** about 1 to 2 GB over two weeks, zipped daily. The data stays out of
git.

## How long

**Two weeks.** Build and test about 28 October. Record about 29 October to
12 November. Report by about 14 November.

- That gives an estimated 300 or more thin favourites in the 80 to 90 cent band
  with full order books. That's enough for the three questions.
- It finishes well before the 6-week test ends on 27 November. So the answer is
  ready when we're allowed to change things.

## How it gets built

- Reuse the design of `research/kalshi_15min/depth_books.py`, which worked:
  public data only, a rate cap, resume after a stop, one line of data per book.
- Tests first, as usual.
- Before any data comes in, write down the pass marks in a separate file. That
  stops us moving the goalposts after seeing results.

## Pass marks (to be fixed before recording)

Proposed. Pass on all three, or the idea is shelved:

1. **Cost to get in.** On thin favourites at 80 to 90 cents, the cheapest offer
   on the favourite's side sits at most 3 cents above the last paid price, in a
   typical market. With Kalshi's fee of about 0.9 cents, that leaves at least
   3 cents of profit per contract.
2. **Money on offer.** A typical market has at least $20 on offer within 1 cent
   of the cheapest price.
3. **Spotting thin early.** Of markets that look thin about an hour before the
   end (by volume so far), at least 8 in 10 still end up thin.

Also reported, not a pass mark: how many thin favourites won, against their
price. It's two weeks of data, so it's too small to judge the profit itself.

## What it does not do

- No orders, no account key, no bot changes.
- Nothing goes live before 27 November, whatever the result.
- Mention markets are not covered. Those need a separate pull of Kalshi's
  history.
