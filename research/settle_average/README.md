# Last-minute favourites (the settle-average idea)

## Question

Kalshi's 15-minute bitcoin and ether markets pay on the average of the CF Benchmarks index over the last 60 seconds,
and trading stays open through that minute. Part of the answer is already fixed while people still trade, so a
price that reads only the live index should overstate the risk. If that shows in the prices, favourites bought in
the last minute should win more often than they cost, after the taker fee.

Two pre-registered steps, each with its pass bar written before any data was read:

- Step 1 (`PREREG.md`): Sep 1 to Oct 25, 2026, four main cells (30 and 10 seconds left, favourites at 90 to 95 and
  95 to 98 cents).
- The fresh test (`PREREG_FRESH.md`): a pattern step 1 found only after looking, scored once on Dec 2025 to Aug
  2026, which step 1 never saw.

## How to run it

From this folder. It reads Kalshi's public trade tape (no key) and caches it as a gzip file a day in `tape/` and
`tape_old/`, which are not committed.

    python last_minute.py fetch            # step 1's tape (resumable)
    python last_minute.py report           # no requests; writes last_minute.json
    python last_minute.py fetch-old        # the fresh test's tape (resumable)
    python last_minute.py fresh            # no requests; writes fresh.json

`report.txt` and `fresh_report.txt` are the printed output of the two scoring runs.

Tests (no network): `python -m pytest -q -p no:cacheprovider research/settle_average/tests` from the repository
root.

## What it found

Step 1 ended "in between": its four main cells were positive but not far from luck. Pooled across the averaging
minute, favourites priced 80 to 98 cents made about 2.0 cents per contract after the fee, but that pattern was found
after seeing the results. The fresh test then failed it clearly: on the nine earlier months the same rule lost 1.5
cents per contract after the fee (about 1.6 cents for every dollar bet), far from luck on the losing side (t about
minus 4.5). By the pre-set bar a fail closes the idea, so step 2 (recording live order books) was never started.
The write-ups are in `reports/` ("Last-minute favourites check Oct 26" and "Last-minute favourites fresh test
Oct 29").
