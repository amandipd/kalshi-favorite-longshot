"""Every paper-trading strategy, backtested with the paper trader's own rules.

Strategy: the paper trader's accounts. At the end of minute 8 (minute 5 for one account), buy the
favourite - the side with the higher ask - of each market when that ask is 90-99.9c, and hold it to
settlement; crypto, metals and energy only. They differ in bet size ($10 flat, 1/24 of the bankroll,
3% a bet with a window's bets capped at 20%) and in taking at most one crypto bet a window. The paper
trader's "every market" test account is left out.

Replays every 15-minute window Kalshi has run, from the first on Dec 10, 2025 to the last full day fetched: the four
minute files history.py reads (minutes_pre.csv holds the crypto markets before Jul 18). Four periods are reported apart:
Dec 10 - Jul 17 and Jul 18 - Aug 23, which no rule was chosen on; Aug 24 - Sep 23, the month the rules were built on;
and Sep 24 on, which overlaps the live paper trade. At the end of each
strategy's entry minute the favourite is the side with the higher ask; a strategy bets when that
ask is 90-99.9c and the market's group is one it trades. The strategies, sizing rules, group
limits, $1 minimum and broke rule are the paper trader's (STRATEGIES below; the paper trader itself
was retired on Oct 9). Bets are fractional contracts, as the paper trader filled them;
the taker fee is rounded up to the cent per order. Results land when a window closes, before the
next window's entry minute, so every bet in a window is sized off the same bankroll.

Two more accounts exist only here, since the paper trader never sells: the $10 account and the live bot's
($100, 3% a bet, 20% a window, whole contracts), each selling a bet the first minute after entry (9 to 14, the
last before the close) that the favourite's own bid is under 90c, at that bid, paying the taker fee again.
Next to its "base" account, the same bets held, each records what selling did: how many it sold, how many of
those went on to win, what it saved on the losers and what it gave up on the winners.

Two fill assumptions:
  backtest   at the ask recorded at the end of the entry minute
  live       0.4c a contract worse: the gap between live fills and candle asks (rebuild test); a sale fills
             0.4c under the recorded bid the same way
Both fill every order in full. "The live bot · real liquidity" doesn't: its orders get only what Kalshi's trade tape
says the book had (liquidity.py, liquidity.json), at the recorded ask under either assumption. Nor do "The live bot ·
live fills" accounts (with live_fills.json from live_fills.py): each order gets what the live bot's real orders of its
size got in that market, at the recorded ask plus the gap its real fills paid over it, with the fee charged exactly.

Every account trades every window it can afford, with no pauses, from Jul 18 (under "scenarios", and "jul18" under
"starts"), from Dec 10 ("dec10") and from Aug 24 ("aug24"). Next to
them, backtest-only variants of the $10 account (VARIANTS), and each rule on its own at $10 a bet from a
bankroll that never runs out (edge()), so rules compare apart from their sizing.

Writes strategies.json (hourly bankroll per strategy and stats, each rule's edge under "edge", and each of the live
bot's own versions (MINE) replayed from every starting amount in CAPITALS under its entry's "capital") for the
write-up and the dashboard's Research tab.

    python strategies_backtest.py
"""
import csv
import json
import math
import os
from collections import defaultdict, deque
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import history
from history import strategy

# The accounts' rules. They were the paper trader's (paper/paper_trader.py, retired Oct 9 when paper trading
# stopped); they live here now, and risk_rules.py and stress_signals.py read them from here.
EDGE_GROUPS = ["crypto", "metals", "energy"]  # buying at the ask made money here in the backtest (all_markets.py)
#  "capped" defaults to what the live bot sizes at: 1.5% of the bankroll a bet, a window's bets together at most 10%
# (bot.py's CAP_PCT and WINDOW_CAP, halved from 3%/20% on Oct 15). The paper trader's own 3%/20% rule, and the 1% and
# 2% variants beside it, carry their numbers on themselves ("pct" and "windowCap") so their names stay true; the live
# and MINE accounts take these, and test_fuzz_research.py holds them to bot.stake_for at every bankroll and bet count.
CAP_PCT, WINDOW_CAP = 0.015, 0.10
PAPER_CAPS = {"pct": 0.03, "windowCap": 0.20}   # the paper trader's sizing, retired with it on Oct 9
STRATEGIES = [
    {"id": "m8", "name": "$10 a bet", "minute": 8, "role": "main", "sizing": "flat", "groups": EDGE_GROUPS},
    {"id": "m8k", "name": "1/24 of bankroll", "minute": 8, "role": "sizing", "sizing": "fraction", "groups": EDGE_GROUPS},
    {"id": "m8c", "name": "3% a bet, 20% a window", "minute": 8, "role": "sizing", "sizing": "capped", "groups": EDGE_GROUPS,
     **PAPER_CAPS},
    # the same rule at real-money size: $100, whole contracts only (Kalshi sells no fractions)
    {"id": "m8c100", "name": "3% a bet, 20% a window · $100", "minute": 8, "role": "real", "sizing": "capped",
     "groups": EDGE_GROUPS, "start": 100.0, "whole": True, **PAPER_CAPS},
    {"id": "m8g", "name": "1 crypto bet a window", "minute": 8, "role": "groups", "sizing": "flat", "groups": EDGE_GROUPS,
     "onePer": ["crypto"]},
    {"id": "m5", "name": "Minute 5", "minute": 5, "role": "shadow", "sizing": "flat", "groups": EDGE_GROUPS},
]
LO, HI = 0.90, 0.999
# The two warning signs' three numbers, as the live bot has them (bot.py's SPREAD, JUMP and the 0.5 in
# warning()). Each was chosen once in the October warning-sign work and never scored against an alternative.
# A strategy overrides one with "spreadCut", "jumpCut" or "flipCut"; None switches that one off, so
# THRESHOLD_SEARCH_PREREG.md can search them. Leaving them out must reproduce the live bot exactly.
SPREAD_CUT, JUMP_CUT, FLIP_CUT = 0.02, 0.10, 0.50
STAKE, START = 10.0, 240.0
FRACTION = 1 / 24
MIN_BET = 1.0     # about one contract at 90-99c; Kalshi sells whole contracts
FEE_ROOM = 0.10   # a bet also needs cash for its fee

SCENARIOS = {"backtest": 0.0, "live": 0.004}
EXIT = 0.90   # the exit accounts sell the first minute after entry that the favourite's own bid is under this
# Every paper strategy, the $100 account included: it starts from its own amount and buys whole contracts only. Then
# the exit accounts, which the paper trader doesn't run: each is its "base" account, selling under EXIT.
EXITS = [
    {"id": "m8x", "name": "$10 a bet · sell under 90¢", "minute": 8, "role": "exit", "sizing": "flat", "groups": EDGE_GROUPS,
     "exit": EXIT, "base": "m8"},
    {"id": "m8c100x", "name": "3% a bet, 20% a window · $100 · sell under 90¢", "minute": 8, "role": "exit", "sizing": "capped",
     "groups": EDGE_GROUPS, "start": 100.0, "whole": True, "exit": EXIT, "base": "m8c100", **PAPER_CAPS},
]
# Variants that exist only here, for the dashboard to compare: the $10 account with one thing changed (the price band,
# the entry minute, the markets, or skipping findings.py's warning signs), and the 3% account at other sizes. They were
# picked with Jul 18 - Sep 23 in view, so only Dec 10 - Jul 17 and the Sep 24-on days are a fair test of any of them.
VARIANTS = [{"minute": 8, "sizing": "flat", "groups": EDGE_GROUPS, "variant": True, **v} for v in (
    {"id": "vb85", "name": "$10 a bet · 85¢ and up", "role": "band", "lo": 0.85},
    {"id": "vb92", "name": "$10 a bet · 92¢ and up", "role": "band", "lo": 0.92},
    {"id": "vb95", "name": "$10 a bet · 95¢ and up", "role": "band", "lo": 0.95},
    {"id": "vt10", "name": "$10 a bet · minute 10", "role": "timing", "minute": 10},
    {"id": "vt12", "name": "$10 a bet · minute 12", "role": "timing", "minute": 12},
    {"id": "vgcr", "name": "$10 a bet · crypto only", "role": "markets", "groups": ["crypto"]},
    {"id": "vgme", "name": "$10 a bet · metals only", "role": "markets", "groups": ["metals"]},
    {"id": "vgen", "name": "$10 a bet · energy only", "role": "markets", "groups": ["energy"]},
    {"id": "vfsp", "name": "$10 a bet · skip 2¢+ spreads", "role": "filter", "skip": ["spread"]},
    {"id": "vfla", "name": "$10 a bet · skip late favorites", "role": "filter", "skip": ["late"]},
    {"id": "vfsl", "name": "$10 a bet · skip both", "role": "filter", "skip": ["spread", "late"]},
    {"id": "vc1", "name": "1% a bet, 20% a window", "role": "sizing", "sizing": "capped", "pct": 0.01, "windowCap": 0.20},
    {"id": "vc2", "name": "2% a bet, 20% a window", "role": "sizing", "sizing": "capped", "pct": 0.02, "windowCap": 0.20},
    {"id": "vcfsl", "name": "3% a bet, 20% a window · skip both", "role": "filter", "sizing": "capped", "skip": ["spread", "late"],
     **PAPER_CAPS},
)]
# The rule the real-money bot (bot/bot.py) trades since Oct 9, at its own size: 3% a bet, 20% a window, skipping both
# warning signs, whole contracts, no bets in a Fed decision's windows (2:00-3:30 pm ET), from a small $225 start,
# and no cap on an order's size (the bot dropped its $10 cap on Oct 10). Its halts are left out, so
# the replay trades every window. Checked window by window with live-like fills, its 35%-in-24-hours halt would have
# fired once from Dec 10, on Jul 8, 2026 (a 35.9% fall); from Jul 18 the worst 24 hours is 34.8%, just inside the
# line, and from Aug 24 31.5%. Its other two never would: the lowest from Dec 10 is $165 against a $112.50
# half-the-start floor, and no window lost more than 6 bets. Filled in full at the recorded ask it fires Jul 8, and from
# Jul 18 on Jul 30 (35.1%); with tape-limited fills it never does (worst 26%).
# The Fed's rate decisions in the history, each at 2:00 pm ET (federalreserve.gov/monetarypolicy/fomccalendars.htm).
FED_DAYS = ["2025-12-10", "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17", "2026-07-29", "2026-09-16"]
FED_WINDOWS = [tuple(datetime.fromisoformat(f"{d}T{hm}").replace(tzinfo=ZoneInfo("America/New_York")).timestamp()
                     for hm in ("14:00", "15:30")) for d in FED_DAYS]
LIVE = [{"id": "live", "name": "The live bot", "minute": 8, "role": "live", "sizing": "capped", "groups": EDGE_GROUPS,
         "skip": ["spread", "late"], "whole": True, "start": 225.0, "blackouts": FED_WINDOWS}]
# The same bot started with a round $500 instead.
LIVE.append({**LIVE[0], "id": "live500", "name": "The live bot · $500", "start": 500.0})
# Both again with the $10 order cap the bot traded under until Oct 10 (backtest only now): once 3% of the bankroll
# passes $10 (about $333), every bet stays $10, so bets stop growing with the bankroll.
LIVE += [{**LIVE[0], "id": "livecap", "name": "The live bot · $10 cap", "maxOrder": 10.0},
         {**LIVE[0], "id": "live500cap", "name": "The live bot · $500 · $10 cap", "start": 500.0, "maxOrder": 10.0}]
# The live bot again, with each order filled only as far as Kalshi's trade tape says it could have been (liquidity.py):
# nothing when the price ran away before its order landed (the first trade on its side within FRESH seconds of the
# order was above its price), and otherwise at most what others bought on its side at its price or better in the next
# 30 s, or QUIET contracts if more (the most a book with no trades around it has filled for the bot). Its fills are at
# the minute-8 ask in both scenarios: an immediate-or-cancel order never pays more than its limit. A market the tape
# doesn't cover fills in full, as the plain live bot's do: liquidity.json covers the bets from the start date its
# reduce was given (Jul 18 unless one is).
FRESH, QUIET = 10, 3
LIQUIDITY = json.load(open("liquidity.json", encoding="utf-8"))["markets"] if os.path.exists("liquidity.json") else None
if LIQUIDITY:
    LIVE.append({**LIVE[0], "id": "liveliq", "name": "The live bot · real liquidity", "liquidity": True})
# The Oct 11 strategy lab's candidates (lab/REPORT.md, lab/edge_map.md): the live bot with one change each, then all three.
#   skipSeries  leaves HYPE out: its favourites won as often as their price said (94.7% at a 94.8c ask), so the fee made
#               them a loss, -8.5c per $10 over 3,213 bets, in both halves of the history
#   skipSlots   no bets in the weekday windows opening at 9:30 ET, the US stock market's open: -40.9c per $10 over 416 bets,
#               flagged in September on Jul-Sep data and losing on Dec 10 - Jul 17 too
#   maxPer      at most 3 crypto bets a window, the tightest spreads kept: crypto favourites lose together (when one loses,
#               another in its window does 36% of the time), and the cap halves the worst window
CANDIDATE = {**LIVE[0], "role": "candidate", "variant": True}
LIVE += [{**CANDIDATE, "id": "livenh", "name": "The live bot · skip HYPE", "skipSeries": ["KXHYPE15M"]},
         {**CANDIDATE, "id": "liveno", "name": "The live bot · skip the 9:30 open", "skipSlots": ["09:30"]},
         {**CANDIDATE, "id": "livec3", "name": "The live bot · 3 crypto bets a window", "maxPer": {"crypto": 3}},
         {**CANDIDATE, "id": "live3x", "name": "The live bot · all three", "skipSeries": ["KXHYPE15M"], "skipSlots": ["09:30"],
          "maxPer": {"crypto": 3}}]
if LIQUIDITY:
    LIVE.append({**LIVE[-1], "id": "live3xliq", "name": "The live bot · all three · real liquidity", "liquidity": True})
# The live bot and all three again, each order filled the way the live bot's own real orders fill (live_fills.py, from
# its ledger): the contracts it can expect to get for its size from the fill table of its market (or of its group, or
# of every order, when its market has fewer than MIN_ORDERS live orders), at the minute-8 ask plus the gap its real
# fills paid over that ask, with Kalshi's fee charged exactly, as it charges the bot. The scenario's slip never reaches
# them. An expected fill can be part of a contract: it's the average over what the book had for the live orders.
MIN_ORDERS = 15
LIVE_FILLS = json.load(open("live_fills.json", encoding="utf-8")) if os.path.exists("live_fills.json") else None
if LIVE_FILLS:
    LIVE += [{**LIVE[0], "id": "livefit", "name": "The live bot · live fills", "liveFit": True},
             {**next(s for s in LIVE if s["id"] == "live3x"), "id": "live3xfit", "name": "The live bot · all three · live fills",
              "liveFit": True}]
# The live bot as it has really traded, one version per change (the bot's history), each from a simulated $2,000:
# the accounts the dashboard's backtest view shows. 1: 90c floor, at most $10 an order, no warning signs
# (Sep 28 - Oct 9); 2: skips both warning signs (Oct 9 - 10); 3: no order cap (Oct 10 - 14); 4: a 92c floor, after live
# 90-92c favourites lost 31 of 217 (since Oct 14), and beside a liquidity.json version 4 again with fills from the
# trade tape.
MINE_START = 2000.0
# Three more starting amounts on version 4's real-liquidity account, all simulated: a small account (SMALL), a round
# $1,000 and a large one (BIG), to show how the same rule scales when the order book is the limit.
MINE_START_SMALL = 850.0
MINE_START_BIG = 10000.0
MINE_START_1K = 1000.0
MINE_FLOOR = 700.0   # the bot's HALT_FLOOR; test_mine_accounts.py holds it to the bot's own


def mine_accounts(liquidity):
    # MINE_FLOOR is the bot's HALT_FLOOR, its $700 stop (Oct 15), which the live bot applies to the real-money
    # account only. The replays trade every window -- its halts are left out here, as the comment above LIVE says --
    # so the accounts carry the level and run() reports the first window the bankroll was at or under it ("floorHit").
    # The $225 and $500 live replays get no floor: they start under $700, where it would say nothing.
    bot = {**LIVE[0], "start": MINE_START, "role": "mine", "mine": True, "floor": MINE_FLOOR}
    out = [{**{k: v for k, v in bot.items() if k != "skip"}, "id": "mine1", "name": "Version 1 · 90¢, $10 orders",
            "lo": 0.90, "maxOrder": 10.0, "version": 1, "traded": "Sep 28 – Oct 9"},
           {**bot, "id": "mine2", "name": "Version 2 · skips warning signs", "lo": 0.90, "maxOrder": 10.0, "version": 2,
            "traded": "Oct 9 – 10"},
           {**bot, "id": "mine3", "name": "Version 3 · no order cap", "lo": 0.90, "version": 3, "traded": "Oct 10 – 14"},
           {**bot, "id": "mine4", "name": "Version 4 · 92¢ floor", "lo": 0.92, "version": 4, "traded": "since Oct 14",
            "now": True}]
    if liquidity:
        out.append({**out[-1], "id": "mine4liq", "name": "Version 4 · real liquidity", "liquidity": True})
        # The same account with $10,000 behind it. Not the $2,000 run times five: a 1.5% bet at
        # $10,000 is about 160 contracts, far past what the trade tape says the book held, so most of the extra size
        # never fills. The capital rows already showed that; this one also gets a bankroll curve, which they do not.
        # The $700 stop is left as the bot's own rather than scaled -- at $10,000 it is a 93% fall, so it never fires.
        out.append({**out[-1], "id": "mine4liq10k", "name": "Version 4 · real liquidity · $10,000",
                    "start": MINE_START_BIG})
        # A small account. The $700 stop bites on it: a 25% fall from $850 is under $700, so run() reports a floorHit
        # the bigger accounts never see. The replays trade every window, so it is reported rather than enforced.
        out.append({**out[-2], "id": "mine4liq850", "name": "Version 4 · real liquidity · $850",
                    "start": MINE_START_SMALL})
        # A round $1,000 for the dashboard's simulated-account view. The $700 stop again stays the bot's own rather
        # than scaled: from $1,000 it is a 30% fall, further off than from $850 but still close enough to fire.
        out.append({**out[-3], "id": "mine4liq1k", "name": "Version 4 · real liquidity · $1,000",
                    "start": MINE_START_1K})
    return out


MINE = mine_accounts(LIQUIDITY)
STRATS = STRATEGIES + EXITS + VARIANTS + LIVE + MINE
# The starting amounts the Historical Research tab's slider replays each MINE account from (capital(), main()'s
# "capital"): what the same rule would have made from $0 to $100,000.
CAPITALS = [0, 100, 250, 500, 1000, 2000, 3000, 5000, 7500, 10000, 15000, 20000, 25000, 35000, 50000, 75000, 100000]
EDGE_BANK = 1e9   # the edge runs: $10 a bet from a bankroll that can't run out, so every rule bets the whole history
HOUR = 3600
PERIODS = [("pre", "Dec 10 – Jul 17 · untouched", history.FIRST, history.JUL18),
           ("before", "Jul 18 – Aug 23 · untouched", history.JUL18, "2026-08-24T00:00:00Z"),
           ("build", "Aug 24 – Sep 23 · rules built here", "2026-08-24T00:00:00Z", "2026-09-24T00:00:00Z"),
           ("paper", "Sep 24 on · paper-trade days", "2026-09-24T00:00:00Z", history.end())]


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def load():
    """{open_ts: [market]} with each market's (bid, ask) at the end of every minute and its result."""
    with open("universe.json", encoding="utf-8") as fh:
        groups = {u["ticker"]: u["group"] for u in json.load(fh)["series"]}
    num = lambda x: float(x) if x != "" else None
    windows = defaultdict(list)
    seen = set()
    first, last = ts(PERIODS[0][2]), ts(PERIODS[-1][3]) - 900
    for path in history.FILES:
        if not os.path.exists(path):
            continue
        with open(path) as fh:
            for r in csv.DictReader(fh):
                if r["ticker"] in seen:
                    continue
                seen.add(r["ticker"])
                t = ts(r["open_time"])
                windows[t].append({"ticker": r["ticker"], "series": r["series"], "group": groups.get(r["series"], "other"), "yes": r["resolved_yes"] == "1",
                                   "q": {k: (num(r[f"b{k}"]), num(r[f"a{k}"])) for k in range(1, 16)}})
    return {t: ms for t, ms in windows.items() if first <= t <= last}, first, last


def favourite(bid, ask):
    if bid is None or ask is None:
        return None, None
    yes, no = ask, round(1 - bid, 4)
    if abs(yes - no) < 1e-9:
        return None, None
    return ("yes", yes) if yes > no else ("no", no)


def fee(contracts, price):
    return math.ceil(0.07 * contracts * price * (1 - price) * 100 - 1e-9) / 100


def sell_point(m, side, minute, below):
    """The first minute after entry, up to 14 (the last before the close), at whose end the favourite's own bid is under
    `below`: (minute, that bid), or (None, None) if it never is. A minute with no quote can't trigger a sale."""
    for k in range(minute + 1, 15):
        bid, ask = m["q"][k]
        if bid is None or ask is None:
            continue
        own = bid if side == "yes" else round(1 - ask, 4)
        if own < below:
            return k, own
    return None, None


def own_quote(m, side, k):
    """The favourite side's own (bid, ask) at the end of minute k, or None without both."""
    bid, ask = m["q"].get(k, (None, None))
    if bid is None or ask is None:
        return None
    return (bid, ask) if side == "yes" else (round(1 - ask, 4), round(1 - bid, 4))


def skipped(strat, m, side):
    """findings.py's warning signs, taken at the strategy's own entry minute M: "spread", the favourite's ask 2c or more
    over its bid at M; "late", its mid 50c or under at M-2 or M-1, or up 10c or more in minute M; "slow", under 70c at M-3."""
    M = strat["minute"]
    spread_cut = strat.get("spreadCut", SPREAD_CUT)
    jump_cut = strat.get("jumpCut", JUMP_CUT)
    flip_cut = strat.get("flipCut", FLIP_CUT)
    spread_cut = math.inf if spread_cut is None else spread_cut   # None: that part is off
    jump_cut = math.inf if jump_cut is None else jump_cut
    flip_cut = -1.0 if flip_cut is None else flip_cut             # no mid is ever under this

    def mid(k):
        q = own_quote(m, side, k)
        return None if q is None else (q[0] + q[1]) / 2
    for sign in strat.get("skip") or ():
        if sign == "spread":
            q = own_quote(m, side, M)
            if q and q[1] - q[0] >= spread_cut - 1e-9:
                return True
        elif sign == "late":
            now, before = mid(M), mid(M - 1)
            if (now is not None and before is not None and now - before >= jump_cut) or \
                    any(x is not None and x <= flip_cut for x in (mid(M - 2), before)):
                return True
        elif sign == "slow":
            x = mid(M - 3)
            if x is not None and x < 0.70:
                return True
    return False


def slot(t):
    """A window's opening time in New York as "HH:MM" on a weekday, None at weekends (skipSlots)."""
    e = datetime.fromtimestamp(t, ZoneInfo("America/New_York"))
    return f"{e:%H:%M}" if e.weekday() < 5 else None


def capped(chosen, caps, minute):
    """At most caps[group] of a group's candidates (maxPer): the tightest own spread at the entry minute first (to 4
    places, so float noise can't break a tie), then the dearest, then the order listed. The rest keep their order."""
    drop = set()
    for group, k in caps.items():
        mine = [(i, c) for i, c in enumerate(chosen) if c[0]["group"] == group]

        def rank(ic):
            i, (m, side, top) = ic
            q = own_quote(m, side, minute)
            return (round(q[1] - q[0], 4) if q else math.inf, -top, i)
        drop |= {i for i, _ in sorted(mine, key=rank)[k:]}
    return [c for i, c in enumerate(chosen) if i not in drop]


def available(m, top, want):
    """How many of `want` contracts at `top` the live bot's order would have got in market m (LIQUIDITY, above)."""
    first, price, seen = LIQUIDITY.get(m["ticker"], (None, None, None))
    if seen is None:   # no tape for it: filled in full, as before
        return want
    if first is not None and first <= FRESH and price > top + 1e-9:
        return 0
    return min(want, max(seen, QUIET))


def expected_fill(entry, c):
    """The contracts an order for c can expect from a fill table (live_fills.py): survival[k] is the chance the book had
    more than k at the bot's price, so their sum to c is what it gets on average. Never more than the table's live
    orders have shown: past its end, the whole sum."""
    s, i = entry["survival"], int(c)
    return sum(s[:i]) + (c - i) * s[i] if i < len(s) else sum(s)


def pick(depth, series, group):
    """A market's fill table: its own with MIN_ORDERS live orders or more, else its group's, else every order's."""
    for e in (depth["series"].get(series), depth["groups"].get(group)):
        if e and e["orders"] >= MIN_ORDERS:
            return e
    return depth["all"]


def stake_for(strat, bal, n=1):
    """A bet's size; an account with a "maxOrder" (the live bot's $10) never bets more than that on one order. A
    "capped" account bets "pct" of the bankroll with a window's n bets together at most "windowCap" of it, both
    defaulting to the live bot's, and floors to the cent exactly as bot.py's floor_cents does."""
    if strat["sizing"] == "flat":
        return STAKE
    pct, cap = strat.get("pct", CAP_PCT), strat.get("windowCap", WINDOW_CAP)
    raw = bal * FRACTION if strat["sizing"] == "fraction" else min(bal * pct, bal * cap / max(n, 1))
    return min(math.floor(raw * 100 + 1e-6) / 100, strat.get("maxOrder", math.inf))


def band_of(price):
    """The 2c price band a quote falls in, as its low whole cent: 92, 94, 96, 98. Same bins as byBand."""
    return int(price * 50) * 2


def band_stakes(strat, stake, n, bal, quotes):
    """A window's per-bet stakes. Without "bandWeights" every bet gets the flat `stake`, exactly as today.

    With them, the window's budget (n x the flat stake, which already respects WINDOW_CAP) is shared out in
    proportion to each bet's band weight, so a weighting moves money between bets and never changes the
    window's total. Each bet is still held under CAP_PCT of the bankroll and floored to the cent, and a bet
    whose share lands under MIN_BET is dropped rather than rounded up. A band with no weight listed keeps 1.0.

    The weight is looked up on the quote the bot sees, not the price it pays, because sizing is decided
    before the fill."""
    weights = strat.get("bandWeights")
    if not weights:
        return [stake] * n
    w = [float(weights.get(band_of(q), 1.0)) for q in quotes]
    total = sum(w)
    if total <= 0:
        return [0.0] * n
    budget, cap = n * stake, bal * strat.get("pct", CAP_PCT)
    out = []
    for wi in w:
        x = min(budget * wi / total, cap)
        x = math.floor(x * 100 + 1e-6) / 100
        out.append(x if x >= MIN_BET else 0.0)
    return out


def choose(strat, ms):
    """A window's bets, before sizing, and how many bets its stake is shared among: the favourites in the band, in the
    groups traded, past the warning signs, then onePer and maxPer. None of it depends on the bankroll."""
    cands = []
    lo, hi = strat.get("lo", LO), strat.get("hi", HI)
    for m in ms:
        if strat.get("groups") and m["group"] not in strat["groups"]:
            continue
        if m["series"] in (strat.get("skipSeries") or ()):
            continue
        side, top = favourite(*m["q"][strat["minute"]])
        if side and lo <= top <= hi and not skipped(strat, m, side):
            cands.append((m, side, top))
    chosen = cands
    if strat.get("onePer"):
        best = {}
        for c in cands:
            if c[0]["group"] in strat["onePer"] and (c[0]["group"] not in best or c[2] > best[c[0]["group"]][2]):
                best[c[0]["group"]] = c
        chosen = [c for c in cands if c[0]["group"] not in strat["onePer"]] + list(best.values())
    if strat.get("maxPer"):   # sized off the bets the window places (onePer sizes off every candidate)
        chosen = capped(chosen, strat["maxPer"], strat["minute"])
    return chosen, len(chosen) if strat.get("maxPer") else len(cands)


def run(strat, windows, slip, t0, hours, start_ts=None, memo=None):
    """start_ts: begin with the account's starting amount at this moment instead of the first window (the curve is
    empty before it). An account with a "start" begins with that instead of $240; one marked "whole" buys whole
    contracts only, as Kalshi sells them, so each bet rounds down. It trades every window until it's broke, with no
    pauses. An account with an "exit" sells a bet the first minute after entry its own bid is under that price
    (sell_point), at that bid less the slip, and pays the taker fee again. memo: {window open: choose()} for this rule
    and these windows, filled as it goes; runs of one rule from other amounts, fills or starts can share it, since
    choose() never looks at the bankroll (capital() does: picking the bets is most of a run's time)."""
    memo = {} if memo is None else memo
    if start_ts is not None:
        windows = {t: ms for t, ms in windows.items() if t >= start_ts}
    start = strat.get("start", START)
    bal = peak = start
    dd = worst = 0.0
    broke = None
    n = wins = 0
    staked = pnl_total = need_sum = 0.0
    by_hour = {}
    day_pnl = defaultdict(float)
    half_split = t0 + hours * HOUR / 2
    halves = [0.0, 0.0]
    recs = []  # (window open, bankroll before, pnl, [per-bet cents per $10])
    split = {"byGroup": {}, "byBand": {}, "bySeries": {}}  # settled bets by group, 2c price band and market
    exit_at = strat.get("exit")
    floor, floor_hit = strat.get("floor"), None   # watched only: a floor never skips a window or resizes a bet
    liq = {"asked": 0.0, "got": 0.0, "orders": 0, "missed": 0, "missedWon": 0, "partial": 0} if strat.get("liquidity") else None
    fit = LIVE_FILLS if strat.get("liveFit") else None
    fits = {"orders": 0, "asked": 0.0, "got": 0.0, "missed": 0} if fit else None
    gap = (fit["summary"]["gap"]["fillVsAsk"] or 0.0) / 100 if fit else None   # cents over the ask, as dollars
    ex ={"at": exit_at, "sold": 0, "soldWon": 0, "saved": 0.0, "gaveUp": 0.0, "byMinute": defaultdict(int)} if exit_at else None
    for t in sorted(windows):
        first = stake_for(strat, bal)
        if first < MIN_BET or bal < first + FEE_ROOM:  # the paper trader's broke rule
            broke = t
            break
        if any(t < z and t + 900 > a for a, z in strat.get("blackouts") or ()):   # no bets in a blackout window
            continue
        if strat.get("skipSlots") and slot(t) in strat["skipSlots"]:   # nor in a skipped weekday slot
            continue
        if t not in memo:
            memo[t] = choose(strat, windows[t])
        chosen, pool = memo[t]
        stake = stake_for(strat, bal, pool)
        cash, window_pnl, per_bet = bal, 0.0, []
        if stake >= MIN_BET:
            each = band_stakes(strat, stake, len(chosen), bal, [top for _, _, top in chosen])
            for (m, side, top), stake_i in zip(chosen, each):
                if stake_i <= 0:
                    continue
                price = top if liq else min(top + (gap if fit else slip), 0.999)
                c = math.floor(stake_i / price + 1e-9) if strat.get("whole") else stake_i / price
                if c <= 0:
                    continue
                if liq:   # only what the book had: the order may fill in part, or not at all
                    k = available(m, top, c)
                    liq["orders"] += 1
                    liq["asked"] += c
                    liq["got"] += k
                    liq["partial"] += 0 < k < c
                    if k <= 0:
                        liq["missed"] += 1
                        liq["missedWon"] += (side == "yes") == m["yes"]
                        continue
                    c = k
                elif fit:   # what live orders of its size got in this market
                    k = expected_fill(pick(fit["depth"], m["series"], m["group"]), c)
                    fits["orders"] += 1
                    fits["asked"] += c
                    fits["got"] += k
                    if k <= 0:
                        fits["missed"] += 1
                        continue
                    c = k
                cost, f = c * price, 0.07 * c * price * (1 - price) if fit else fee(c, price)
                if cash < cost + f:
                    continue
                cash -= cost + f
                won = (side == "yes") == m["yes"]
                p = (c if won else 0.0) - cost - f
                if exit_at:
                    k, bid = sell_point(m, side, strat["minute"], exit_at)
                    if k is not None:   # sold: what it fetched instead of what holding would have paid
                        px = max(bid - slip, 0.0)
                        sale = c * px - (fee(c, px) if px > 0 else 0.0) - cost - f
                        ex["sold"] += 1
                        ex["byMinute"][k] += 1
                        if won:
                            ex["soldWon"] += 1
                            ex["gaveUp"] += p - sale
                        else:
                            ex["saved"] += sale - p
                        p, won = sale, False   # a sold bet is never a win, whatever the market did after
                window_pnl += p
                per_bet.append(p / cost * 1000)
                n += 1
                wins += won
                staked += cost
                need_sum += (cost + f) / c
                for kind, key in (("byGroup", m["group"]), ("byBand", f"{int(price * 50) * 2}–{int(price * 50) * 2 + 2}"),
                                  ("bySeries", m["series"].replace("KX", "").replace("15M", ""))):
                    g = split[kind].setdefault(key, {"key": key, "n": 0, "wins": 0, "pnl": 0.0, "staked": 0.0})
                    g["n"] += 1
                    g["wins"] += won
                    g["pnl"] += p
                    g["staked"] += cost
                    if kind in ("bySeries", "byGroup"):
                        # Each market's own start, since Kalshi listed them years apart: gold in July, Brent in
                        # October. A shared start date flatters the newer ones. The same per asset class, which is
                        # what the Backtest tab marks on its chart. A price band has no start date, so byBand keeps
                        # the shape it had.
                        g["first"] = min(g.get("first", t), t)
        recs.append((t, bal, window_pnl, per_bet))
        bal += window_pnl
        pnl_total += window_pnl
        worst = min(worst, window_pnl)
        peak = max(peak, bal)
        dd = max(dd, 1 - bal / peak)
        close = t + 900
        if floor is not None and floor_hit is None and bal <= floor:   # where the real bot's stop would have fired
            floor_hit = close
        by_hour[int((close - t0) // HOUR)] = bal
        day_pnl[datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d")] += window_pnl
        halves[t >= half_split] += window_pnl
    curve, cur = [], start
    for h in range(hours):
        if (broke is not None and t0 + h * HOUR >= broke) or (start_ts is not None and t0 + (h + 1) * HOUR <= start_ts):
            curve.append(None)
            continue
        cur = by_hour.get(h, cur)
        curve.append(round(cur, 2))
    final = 0.0 if broke is not None else bal
    w24 = worst_24h(recs)
    return {
        "start": start, "final": round(final, 2), "ret": final / start - 1, "bets": n, "wins": wins,
        "winRate": wins / n if n else None, "need": need_sum / n if n else None,
        "perBet": pnl_total / staked * 1000 if staked else None,  # cents per $10 staked
        "maxDD": 1.0 if broke is not None else dd, "worstWindow": round(worst, 2),
        # the worst window as a share of the bankroll going into it (often not the same window as the worst in dollars)
        "worstWindowPct": min((p / b for _, b, p, _ in recs if b > 0), default=0.0),
        "worstDay": round(min(day_pnl.values()), 2) if day_pnl else 0.0, "losingDays": sum(v < 0 for v in day_pnl.values()),
        # the deepest fall from a high within any 24 hours (what the live bot's halt watches), in dollars, and when
        "worst24hPct": w24[0], "worst24h": w24[1],
        "worst24hAt": datetime.fromtimestamp(w24[2], timezone.utc).isoformat() if w24[2] is not None else None,
        "days": len(day_pnl), "halves": [round(x, 2) for x in halves],
        # with a "floor" (the live bot's $700 stop): the first window close the bankroll was at or under it, which is
        # where the real bot would have halted. Nothing here acts on it, so the curve runs on past it.
        "floorHit": datetime.fromtimestamp(floor_hit, timezone.utc).isoformat() if floor_hit is not None else None,
        "broke": datetime.fromtimestamp(broke, timezone.utc).isoformat() if broke is not None else None,
        "curve": curve,
        "periods": {k: period_stats(recs, ts(a), ts(b), broke) for k, _, a, b in PERIODS},
        # with an exit: bets sold, how many of those won anyway, $ saved on losers and given up on winners, sales by minute
        # with "liquidity": orders sent, contracts asked for and got, orders that got nothing (and how many of those
        # would have won) or only part
        "liquidity": liq and {**liq, "asked": round(liq["asked"], 2), "got": round(liq["got"], 2)},
        # with "liveFit": orders sent, contracts asked for and expected to fill, orders expected to get nothing
        "liveFit": fits and {**fits, "asked": round(fits["asked"], 2), "got": round(fits["got"], 2)},
        "exit": {**ex, "saved": round(ex["saved"], 2), "gaveUp": round(ex["gaveUp"], 2), "net": round(ex["saved"] - ex["gaveUp"], 2),
                 "byMinute": {str(k): v for k, v in sorted(ex["byMinute"].items())}} if ex else None,
        # bySeries and byGroup carry a first window. It is tallied as the epoch key and turned into ISO here,
        # once a market rather than once a bet, so it reads like worst24hAt and the other dates the payload has.
        **{kind: sorted(({**g, "pnl": round(g["pnl"], 2), "staked": round(g["staked"], 2),
                          **({"first": datetime.fromtimestamp(g["first"], timezone.utc).isoformat()}
                             if "first" in g else {})} for g in rows.values()),
                        key=lambda g: g["key"]) for kind, rows in split.items()},
    }


def worst_24h(recs):
    """The deepest fall from a high within any 24 hours, the way the live bot's halt measures it (bot.check_halts): at
    each window's close, against the most the bankroll held in the 24 hours up to it. A window's bets all settle at its
    close, so the bankroll held when those 24 hours began is the one going into the first window closing inside them.
    (share, dollars, close) of the deepest, the earliest on a tie; (0.0, 0.0, None) if it never fell."""
    best, highs = (0.0, 0.0, None), deque()   # highs: (close, bankroll going in), falling from front to back
    for t, b, p, _ in recs:
        close = t + 900
        while highs and highs[-1][1] <= b:
            highs.pop()
        highs.append((close, b))
        while highs[0][0] <= close - 24 * HOUR:
            highs.popleft()
        high = highs[0][1]
        if (b + p) / high - 1 < best[0]:
            best = ((b + p) / high - 1, round(b + p - high, 2), close)
    return best


def period_stats(recs, a, b, broke):
    """Stats over windows opening in [a, b): the bankroll carries on from before, so returns are relative to its start."""
    rs = [r for r in recs if a <= r[0] < b]
    if not rs:
        return None
    vals = [v for r in rs for v in r[3]]
    clusters = [r[3] for r in rs if r[3]]
    n = len(vals)
    mu = sum(vals) / n if n else None
    lo = hi = None
    if len(clusters) > 1 and n >= 30:
        resid = [sum(c) - mu * len(c) for c in clusters]
        se = (sum(x * x for x in resid) / (len(clusters) - 1)) ** 0.5 / ((n / len(clusters)) * math.sqrt(len(clusters)))
        lo, hi = mu - 1.96 * se, mu + 1.96 * se
    start = rs[0][1]
    bal = peak = start
    dd = 0.0
    for r in rs:
        bal += r[2]
        peak = max(peak, bal)
        dd = max(dd, 1 - bal / peak)
    return {"start": round(start, 2), "end": round(bal, 2), "pnl": round(bal - start, 2), "ret": bal / start - 1,
            "bets": n, "mu": mu, "lo": lo, "hi": hi, "maxDD": dd, "worstWindow": round(min(r[2] for r in rs), 2),
            "brokeHere": broke is not None and a <= broke < b}


def edge(strat, windows, slip, t0, hours):
    """A strategy's rule on its own: $10 a bet over the whole history from a bankroll that can't run out (EDGE_BANK), so
    rules compare on what they earn a bet, apart from their sizing and from going broke. Its curve is the running profit,
    and ddUsd the deepest fall in it, in dollars."""
    r = run({**strat, "sizing": "flat", "start": EDGE_BANK}, windows, slip, t0, hours)
    curve = [None if v is None else round(v - EDGE_BANK, 2) for v in r["curve"]]
    peak = dd = 0.0
    for v in curve:
        if v is not None:
            peak, dd = max(peak, v), max(dd, peak - v)
    keep = ("bets", "wins", "winRate", "need", "perBet", "worstWindow", "worstDay", "losingDays", "days", "exit",
            "byGroup", "byBand", "bySeries")
    return {**{k: r[k] for k in keep}, "pnl": round(r["final"] - EDGE_BANK, 2), "ddUsd": round(dd, 2), "curve": curve,
            "periods": {k: q and {x: q[x] for x in ("bets", "mu", "lo", "hi", "pnl", "worstWindow")}
                        for k, q in r["periods"].items()}}


def capital(strat, windows, slip, t0, hours, start_ts, own, memo):
    """The account replayed from each of CAPITALS with the same fills, start and windows as its own run `own`, which
    stands in for its own amount (the same call, so the same numbers, at no cost): the slider's rows. memo is run()'s,
    one per account. $0 isn't replayed: it can't place a $1 bet, and a return on $0 would divide by zero."""
    rows = []
    for c in CAPITALS:
        if c == 0:
            rows.append({"start": 0, "final": 0.0, "profit": 0.0, "ret": None, "maxDD": 0.0, "bets": 0, "broke": None})
            continue
        r = own if c == strat["start"] else run({**strat, "start": c}, windows, slip, t0, hours, start_ts, memo)
        rows.append({"start": c, "final": r["final"], "profit": round(r["final"] - c, 2), "ret": r["final"] / c - 1,
                     "maxDD": r["maxDD"], "bets": r["bets"], "broke": r["broke"]})
    return rows


def live_fills_entry():
    """What the live-fit accounts' entries in strategies.json say about the orders their fills come from (the Research
    tab's text): how many, over which dates, the share of contracts filled, the gap over the ask in cents, and how often
    the filled and the missed ones won, as [wins, orders with a known result]."""
    s = LIVE_FILLS["summary"]
    return {"orders": s["orders"], "from": s["from"], "to": s["to"], "fillRate": s["fillRate"],
            "fillVsAsk": s["gap"]["fillVsAsk"], "filledWon": s["won"]["filled"], "missedWon": s["won"]["missed"]}


def main():
    strategy(__doc__)
    windows, first, last = load()
    t0 = first
    hours = int((last + 900 - t0) // HOUR) + 1
    starts = {k: ts(a) for k, _, a, _ in PERIODS}   # the Jul 18 start is the "before" period's, Aug 24 the "build" one's
    out = {"t0": datetime.fromtimestamp(t0, timezone.utc).isoformat(), "hours": hours, "start": START,
           "periods": [{"key": k, "label": lab, "from": a, "to": b, "fromHour": max(0, int((ts(a) - t0) // HOUR)),
                        "toHour": min(hours - 1, int((ts(b) - t0) // HOUR))} for k, lab, a, b in PERIODS],
           "strategies": [{**{k: s.get(k) for k in ("id", "name", "minute", "role", "sizing", "groups", "onePer", "exit", "base", "skip",
                                                    "skipSeries", "skipSlots", "maxPer")},
                           "start": s.get("start", START), "whole": bool(s.get("whole")), "variant": bool(s.get("variant")),
                           "lo": s.get("lo", LO), "hi": s.get("hi", HI),
                           "pct": s.get("pct", CAP_PCT) if s["sizing"] == "capped" else None,
                           "windowCap": s.get("windowCap", WINDOW_CAP) if s["sizing"] == "capped" else None,
                           "maxOrder": s.get("maxOrder"), "floor": s.get("floor"),
                           "bandWeights": s.get("bandWeights"),
                           "blackouts": bool(s.get("blackouts")),
                           "liquidity": bool(s.get("liquidity")), "liveFit": bool(s.get("liveFit")),
                           "mine": bool(s.get("mine")), "version": s.get("version"), "traded": s.get("traded"),
                           "now": bool(s.get("now")),
                           **({"liveFills": live_fills_entry()} if s.get("liveFit") else {})} for s in STRATS],
           "scenarios": {}}
    print(f"{len(windows)} windows, {datetime.fromtimestamp(first, timezone.utc):%b %d} to {datetime.fromtimestamp(last, timezone.utc):%b %d}")
    for name, slip in SCENARIOS.items():
        out["scenarios"][name] = {}
        print(f"\n{name.upper()} fills, from Jul 18")
        for s in STRATS:
            r = run(s, windows, slip, t0, hours, starts["before"])
            out["scenarios"][name][s["id"]] = r
            state = f"broke {r['broke'][:10]}" if r["broke"] else f"${r['final']:,.0f}"
            print(f"  {s['name']:<24} {state:>12}  {r['ret']:+7.1%}  {r['bets']:6d} bets  per $10 {r['perBet'] or 0:+6.1f}c"
                  f"  worst drop {r['maxDD']:4.0%}  worst 24h {r['worst24hPct']:+6.1%}  worst 15m {r['worstWindow']:+8.2f}")
            if r["exit"]:
                x = r["exit"]
                print(f"      sold {x['sold']} under {x['at'] * 100:.0f}c ({x['soldWon']} would have won): saved ${x['saved']:,.2f} on losers,"
                      f" gave up ${x['gaveUp']:,.2f} on winners, net ${x['net']:+,.2f} against holding")
            for k, *_ in PERIODS:
                q = r["periods"][k]
                if q:
                    rng = f"({q['lo']:+5.1f} to {q['hi']:+5.1f})" if q["lo"] is not None else ""
                    print(f"      {k:<7} {q['bets']:5d} bets  per $10 {q['mu'] or 0:+6.1f}c {rng:<18} {q['ret']:+7.1%}  worst drop {q['maxDD']:4.0%}")
    # Each rule alone at $10 a bet, never broke: what it earns a bet in each period, apart from sizing.
    out["edge"] = {name: {s["id"]: edge(s, windows, slip, t0, hours) for s in STRATS} for name, slip in SCENARIOS.items()}
    print("\neach rule alone, $10 a bet over the whole history, live-like fills (per $10 bet by period):")
    for s in STRATS:
        e = out["edge"]["live"][s["id"]]
        per = "  ".join(f"{k} {q['mu']:+6.1f}c" if q and q["mu"] is not None else f"{k}      —" for k, q in e["periods"].items())
        print(f"  {s['name']:<46} {e['bets']:6d} bets  {e['perBet'] or 0:+6.1f}c  ${e['pnl']:+10,.2f}  {per}")
    # Two more starts: Dec 10, the first market, and Aug 24, after the untouched weeks from Jul 18 broke every strategy.
    out["starts"] = {"dec10": {name: {s["id"]: run(s, windows, slip, t0, hours) for s in STRATS} for name, slip in SCENARIOS.items()},
                     "jul18": out["scenarios"],
                     "aug24": {name: {s["id"]: run(s, windows, slip, t0, hours, starts["build"]) for s in STRATS}
                               for name, slip in SCENARIOS.items()}}
    for key, label in (("dec10", "Dec 10"), ("aug24", "Aug 24")):
        print(f"\nstarting {label} instead, live-like fills:")
        for s in STRATS:
            r = out["starts"][key]["live"][s["id"]]
            state = f"broke {r['broke'][:10]}" if r["broke"] else f"${r['final']:,.0f}"
            print(f"  {s['name']:<24} {state:>14}  per $10 {r['perBet'] or 0:+6.1f}c  worst drop {r['maxDD']:4.0%}"
                  + (f"  sold {r['exit']['sold']} ({r['exit']['soldWon']} would have won), net ${r['exit']['net']:+,.2f} vs holding" if r["exit"] else ""))
    # The MINE accounts from every amount on the slider, under both fills and from every start; every other entry gets
    # None. It rides on the strategy entries so the dashboard's replay() passes it through as it is.
    begins = {"dec10": None, "jul18": starts["before"], "aug24": starts["build"]}
    memos = {s["id"]: {} for s in MINE}
    caps = {s["id"]: {name: {key: capital(s, windows, slip, t0, hours, at, out["starts"][key][name][s["id"]], memos[s["id"]])
                             for key, at in begins.items()} for name, slip in SCENARIOS.items()} for s in MINE}
    for e in out["strategies"]:
        e["capital"] = caps.get(e["id"])
    print("\nthe bot's versions from other starting amounts, live-like fills from Dec 10 (profit, worst drop):")
    for s in MINE:
        rows = caps[s["id"]]["live"]["dec10"]
        print(f"  {s['name']:<30} " + "  ".join(f"${r['start']:,}: {'broke' if r['broke'] else format(r['profit'], '+,.0f')}"
                                                 f" {r['maxDD']:.0%}" for r in rows if r["start"] in (500, 2000, 10000, 100000)))
    with open("strategies.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh)


if __name__ == "__main__":
    main()
