# Thin-market recorder: pass marks, fixed before any data

Written 26 October 2026, before the recorder ran. Do not change these after
recording starts. If something here turns out to be unworkable, write the change
below under "Changes", with the date and the reason, before looking at results.

Plan: `RECORDER_PLAN.md`. Past result being checked: thin "No" favourites priced
80 to 90 cents made +8.1 cents per contract on prices a No buyer paid
(`reports/Yes vs No favourites split Oct 26.md`).

## Which markets count

A recorded market counts when all of these hold:

1. It is in one of the recorded series, and it settled Yes or No.
2. It is **thin**: its final volume over its whole life is under **18,643
   contracts**. That is the cut for the least-traded third in the past study
   sample. It is fixed here and not re-estimated.
3. **The checkpoint** is 60 minutes before the market actually closed. The
   price at the checkpoint is the last trade at or before it, fetched from
   Kalshi's trade history after the close, the same way the past study did.
4. That price puts the favourite at 80 to 90 cents:
   - Yes price from 0.80 up to (not including) 0.90: a **Yes favourite**.
   - Yes price above 0.10 up to 0.20: a **No favourite**.
5. A recorded order book exists within 10 minutes of the checkpoint. The nearest
   one is used.

**The main test is on No favourites.** Yes favourites are reported the same way,
but they don't decide the verdict.

## The three pass marks

All three must pass, on No favourites, or the idea is shelved.

1. **Cost to get in.** The extra cost is the cheapest offer on the favourite's
   side in the book, minus the favourite's checkpoint price. **Pass: the median
   extra cost is 3 cents or less.** With the fee of about 0.9 cents, that leaves
   at least about 4 cents of the past +8.1 cents.
2. **Money on offer.** Dollars offered on the favourite's side at prices up to
   1 cent above the cheapest offer. **Pass: the median is $20 or more.**
3. **Spotting thin early.** Take every recorded market (any price) whose volume
   so far was under 18,643 contracts at the checkpoint. Volume so far is from the
   last market listing at or before the checkpoint. **Pass: at least 80% of them
   end with final volume under 18,643.**

## Enough data

- The verdict needs at least **100** qualifying No-favourite markets.
- With fewer after two weeks, recording runs one more week, once. If it is still
  under 100, the verdict is "not enough data", not a pass.

## Reported, not pass marks

- Win rate against price for the qualifying markets. Two weeks is too short to
  judge profit, so this is a sanity check only.
- Everything above split by sport, and for Yes favourites.
- How long after each market's listed game time it actually closed, by sport.
  This is for designing an entry time a live bot can know in advance.
- How often the recorder fell behind its 5- and 30-minute schedule.

## Changes

- **27 Oct 2026, before any results were computed.** A qualifying market whose
  nearest book has no offer at all on the favourite's side counts as an
  infinite extra cost and $0 on offer. The original text didn't say. Leaving
  these out would hide exactly the markets you can't get into.
- **27 Oct 2026, note, not a rule change.** Recording had a gap from 01:31 to
  03:03 UTC on 27 Oct 2026. The laptop slept and the recorder was stopped,
  then restarted to the same end date. Markets whose checkpoint fell in the gap
  have no book and simply don't qualify (rule 5).
- **27 Oct 2026, note.** A second gap, 17:00 to 17:37 UTC on 27 Oct, for
  the same reason: the laptop went to sleep. Restarted to the same end date.
- **28 Oct 2026, note.** A watchdog task now restarts the recorder within about
  30 seconds of the laptop waking. Two more gaps, both while the laptop was
  asleep: 02:23 to 03:28 UTC on 28 Oct, and 05:24 to 17:33 UTC on 28 Oct.
  Order books were recorded for about 66% of the time to 28 Oct, 19:30 UTC.
