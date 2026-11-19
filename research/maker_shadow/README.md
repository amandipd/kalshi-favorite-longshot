# Maker shadow: waiting at the bid instead of buying the ask

## Question

The bot is a taker: at minute 8 it buys the favourite at the ask and pays the taker fee. Would a maker version, a
resting buy order at the favourite's bid, do better? A maker pays a lower price and, on most of these markets, no
fee, but it misses the markets where nobody sells to it, and it can be picked off (filled by someone who knows
more).

## The pieces

- `past_trades.py`: a best and worst case from Kalshi's public trade history. A pretend 15-contract order rests at
  the bid at the mark. Best case, it is first in line and every seller at or below its price fills it; worst case,
  it is last in line and only sellers who went through its price fill it.
- `maker_shadow.py`: a recorder of the order book and trade feed for the bot's 16 markets, straight from Kalshi's
  WebSocket, one gzip file an hour. It has no order code and makes no REST calls in the seconds when the bot
  trades. Design: `SPEC.md`.
- `maker_replay.py`: replays the recording with a pretend resting order at minute 8: how often it fills, at what
  price, how fast, and what the price did next.
- `pull.py`: copies the recorder's closed hour files from the server to a local folder, deleting each from the
  server only once the local copy's SHA-256 matches. Its host, key and folders are placeholders; pass your own with
  `--host`, `--key`, `--remote` and `--local`.
- `deploy/kalshi-maker-shadow.service`: an example systemd unit that runs the recorder at low priority, writing only
  inside its own folder and unable to see the bot's state. Its paths are placeholders too.

## How to run it

From the repository root. `past_trades.py` reads only public data; with `LEDGER_JSON` it also uses a dump of the
bot's own decisions and bets, which is private and not included.

    python research/maker_shadow/past_trades.py fetch       # the trade tape after each mark, cached in data/
    python research/maker_shadow/past_trades.py results
    python research/maker_shadow/past_trades.py score
    python research/maker_shadow/maker_shadow.py record --out data --until YYYY-MM-DD     # needs a Kalshi API key
    python research/maker_shadow/maker_replay.py report --data research/maker_shadow/data

Tests (no network, no key): `python -m pytest -q -p no:cacheprovider research/maker_shadow/tests`. The recorder
imports the bot's Kalshi client from `bot/kalshi_bot/kalshi.py`.

## What it found

From the trade history (Oct 25, 2026, 1,697 past markets at 15 contracts): no clear win. The best case made about
16% more money than buying the ask, and the worst case about 24% less. Getting picked off was real but small: filled orders won 96.6% to 97.0% of the time against
97.3% for all markets. Where the truth sits depends on the queue at the bid, which only a recording of the live
order book can show. The write-up is in `reports/` ("Maker best case Oct 25").

A 40-minute trial of the recorder on the bot's own server worked (6.2 million messages, none lost, about 137 MB of
memory and 3.65 GB of data a day), but it used about 14% of a processor core and the cloud host then took back 7 to
15% of the server's processor time in the seconds around each minute boundary, minute 8 included. So it could not
share a server with the bot. The plan was a separate small server for about three weeks; it was paused before that
and never run, so there is no maker result.
