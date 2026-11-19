"""Tests for maker_replay.py: the offline replay of the recorded Kalshi feed with pretend resting orders.

    python -m pytest research/maker_shadow/tests/test_maker_replay.py -q

Every test builds its own small message stream in tmp_path. Nothing here reads the real recording.

Readings of the spec (where SPEC.md is silent, or a literal reading would count fills the data doesn't prove):

1. A trade and its own book delta are one event, not two. Kalshi sends the book delta for a trade a few ms BEFORE
   the trade itself (85% of trades in the Oct 25 sample; same ts_ms in 99.85%, at most 41 ms apart). Read literally,
   on_delta would shrink `ahead` to the smaller level, and then on_trade would use up `ahead` again for the same
   contracts. That counts the queue's progress twice and gives the join order fills it never had. So a cut in `ahead`
   made by a delta at L is remembered, and a trade at L within PAIR seconds of it (by ts_ms, else by rt) first
   cancels that cut; only the rest of the trade uses up `ahead`. Either arrival order then gives the same answer,
   and this can only remove fills, never add one.
2. A new sell on the other side at or under L (the on_delta fill) first uses up `ahead`, then fills this order. In a
   consistent book `ahead` is already 0 by then, so this only matters when the data is odd.
3. While a market's book is not `ok` (after a gap or a hole), its deltas still update the book but are not passed to
   the orders: a broken book can't prove a fill or a shorter queue. Trades still count: they come on their own sid
   and each one proves a seller.
4. A market's book sid is the sid of its last snapshot. A delta from any other sid is ignored: it would come from a
   second subscription and would apply the same change twice.
5. Holes. Besides seq jumps, two things make every book unknown until its next snapshot: a silence of more than
   STALE = 30 s between messages (the recorder's own dead-socket limit, after which it resubscribes), and the start
   of a `ws-...<n>.txt.gz` file (a recorder restart). A seq jump is checked before reading any mark or check time that
   falls before that message. After the last message nothing is known, so a read after the end of the data is None.
6. "Before" is strict: the mark book is the book after the last message with rt < mark. The same goes for the
   check times and the close. Orders see messages with mark <= rt < close.
7. Any mid read from a book that isn't `ok` is None. mid_after[k] is None when first fill + k >= close.
8. Hybrid: the join order waits until mark + TAKE_AFTER, then is cancelled. Its maker part is the join's fills before
   then. The rest is bought at the ask at that time, if that ask is known and in band. Otherwise nothing more is
   bought, and the order does not keep waiting. taker_price is None when nothing was bought.
9. Tick size: `price_ranges` first (the real price grid: the step at the bid, read on the YES grid for a NO bid), then
   `tick_size` (cents), then `price_level_structure` "tapered_deci_cent" without ranges, then 0.01.
10. summarise: `markets` is the same for every kind (in-band rows with a known result). A tick or cent order that
    couldn't be placed counts as unfilled. An extra `placed` count says how many were placed. For the taker,
    any_fill = full_fill = 1, win_unfilled is None and median_wait is 0. The hybrid's `filled` is maker + taker part,
    and its mid_move is None.
11. Extra fields, on top of the spec's: rows get `open`, `close`, `mark`, `size`, `complete` (False when the data had
    a gap or hole between the mark and the close, or the book was unknown at the close, so fills may be missing; an
    empty book side is not lost data). `taker` gets `mid_at_fill` and `mid_after` (the mid at the mark and at
    mark + k: a baseline for the picked-off check). `hybrid` gets `first_fill_rt`. Summaries get `contracts` and
    `avg_price`.
12. Order.on_trade(body, rt=None) and Order.on_delta(body, book, rt=None) take the receive time for the fills list.
    Left out, ts_ms / 1000 is used. A message received before the order's t0 is ignored.
13. An event Kalshi stamps (ts_ms) before t0 can't fill the order or use up its queue, even when it arrives after t0:
    the order didn't exist yet. Seen on the real feed: a sale stamped 6 ms before the mark arrived 9 ms after it and,
    read literally, gave the join order an instant fill. A shrink of the level at L stamped before t0 still shortens
    the queue: the level really is smaller, the mark book just hadn't heard yet.
14. A trade with `is_block_trade` true never fills or moves the queue: it is arranged off the book, so it shows no
    seller who would have hit a resting bid. (None in the Oct 25 sample; real trades carry the field.)
15. A fresh snapshot while orders wait (after a gap) shortens each queue to what is bid at L now (Order.on_book), with
    the cut remembered for reading 1. It never fills: a level crossing L in a snapshot may have been counted already.
16. A crossed or locked book at the mark (ask <= bid) can't be real: no row, counted in stats["crossed"].
17. read_lines yields JSON objects only. A line holding other JSON (a number, a list) counts as a bad line.
18. A delta that can't be read (no price or count) makes that book unknown until its next snapshot.
19. replay(folder, size, workers=1) can split the hours across processes; replay_with_stats() also returns counts of
    messages, gaps, holes and odd data. The rows are the same either way.
"""
import gzip
import json
import os
import time

import pytest

import maker_replay as R

T0 = 1792972800.0          # 2026-10-26 00:00 UTC, a window open
MARK_T = T0 + 480
CLOSE = T0 + 900
A = "KXBTC15M-26OCT252015-15"
B = "KXETH15M-26OCT252015-15"
C = "KXSOL15M-26OCT252015-15"
D = "KXXRP15M-26OCT252015-15"
E = "KXDOGE15M-26OCT252015-15"
RANGES = {"price_level_structure": "tapered_deci_cent",
          "price_ranges": [{"start": "0.0000", "end": "0.1000", "step": "0.0010"},
                           {"start": "0.1000", "end": "0.9000", "step": "0.0100"},
                           {"start": "0.9000", "end": "1.0000", "step": "0.0010"}]}
approx = pytest.approx


# ---------------------------------------------------------------- builders

def body_snap(yes=(), no=(), t="T"):
    b = {"market_ticker": t}
    if yes:
        b["yes_dollars_fp"] = [[f"{p:.4f}", f"{c:.2f}"] for p, c in yes]
    if no:
        b["no_dollars_fp"] = [[f"{p:.4f}", f"{c:.2f}"] for p, c in no]
    return b


def body_delta(side, price, d, t="T", ts=None):
    b = {"market_ticker": t, "price_dollars": f"{price:.4f}", "delta_fp": f"{d:.2f}", "side": side}
    if ts is not None:
        b["ts_ms"] = ts
    return b


def body_trade(yes_price, count, taker, t="T", ts=None):
    b = {"trade_id": "x", "market_ticker": t, "yes_price_dollars": f"{yes_price:.4f}",
         "no_price_dollars": f"{1 - yes_price:.4f}", "count_fp": f"{count:.2f}", "taker_side": taker,
         "taker_outcome_side": taker, "taker_book_side": "bid" if taker == "yes" else "ask"}
    if ts is not None:
        b["ts_ms"] = ts
    return b


def book_of(yes=(), no=()):
    b = R.Book()
    b.snapshot(body_snap(yes, no))
    return b


def market(t, open_=T0, raw=None):
    return {"ticker": t, "series": t.split("-")[0], "open": open_, "close": open_ + 900, "raw": raw or {},
            "window_open": open_}


def result(t, res):
    return {"ticker": t, "result": res, "status": "finalized", "rt": CLOSE + 200}


class Feed:
    """A hand-built recording: messages at receive times, seq counted per sid as Kalshi does, written as the recorder
    writes them (gzip hour files of "<rt> <json>" lines, plus markets.jsonl and results.jsonl)."""

    def __init__(self):
        self.lines = []
        self.seq = {}

    def add(self, rt, msg):
        sid = msg.get("sid")
        if sid is not None and "seq" not in msg:
            self.seq[sid] = self.seq.get(sid, 0) + 1
            msg["seq"] = self.seq[sid]
        self.lines.append((rt, msg))

    def snap(self, rt, t, yes=(), no=(), sid=1):
        self.add(rt, {"type": "orderbook_snapshot", "sid": sid, "msg": body_snap(yes, no, t)})

    def delta(self, rt, t, side, price, d, sid=1, ts=None):
        self.add(rt, {"type": "orderbook_delta", "sid": sid,
                      "msg": body_delta(side, price, d, t, int(rt * 1000) if ts is None else ts)})

    def trade(self, rt, t, yes_price, count, taker, sid=2, ts=None):
        self.add(rt, {"type": "trade", "sid": sid,
                      "msg": body_trade(yes_price, count, taker, t, int(rt * 1000) if ts is None else ts)})

    def gap(self, sid, n=1):
        """Lose n messages on this sid: the next one jumps."""
        self.seq[sid] = self.seq.get(sid, 0) + n

    def write(self, folder, markets, results=(), until=CLOSE + 10, quiet=None, split=None):
        """Filler `ok` messages every 10 s from T0 to `until` keep the feed alive, as the real feed always is
        (skipped strictly inside `quiet`). From rt >= `split` on, lines go to a restart file (.1)."""
        rows = list(self.lines)
        t = T0
        while t <= until:
            if not (quiet and quiet[0] < t - T0 < quiet[1]):
                rows.append((t, {"type": "ok", "id": 0}))
            t += 10
        rows.sort(key=lambda x: x[0])
        files = {}
        for rt, msg in rows:
            name = time.strftime("ws-%Y%m%dT%H", time.gmtime(rt))
            if split is not None and rt >= split:
                name += ".1"
            files.setdefault(name + ".txt.gz", []).append(f"{rt:.3f} {json.dumps(msg)}\n")
        for name, lines in files.items():
            with gzip.open(os.path.join(folder, name), "wt", encoding="utf-8") as fh:
                fh.write("".join(lines))
        with open(os.path.join(folder, "markets.jsonl"), "w", encoding="utf-8") as fh:
            fh.writelines(json.dumps(m) + "\n" for m in markets)
        with open(os.path.join(folder, "results.jsonl"), "w", encoding="utf-8") as fh:
            fh.writelines(json.dumps(r) + "\n" for r in results)
        return str(folder)


def base(feed, t=A, rt=T0 + 20, sid=1):
    """The usual book: YES bids 95c x100 and 94c x50, NO bids 3c x40 and 2c x10. YES is the favourite, bid 95c,
    ask 97c (1 - 0.03), in band."""
    feed.snap(rt, t, yes=[(0.95, 100), (0.94, 50)], no=[(0.03, 40), (0.02, 10)], sid=sid)


def by_ticker(rows):
    return {r["ticker"]: r for r in rows}


def write_ws(path, lines):
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        fh.write("".join(line + "\n" for line in lines))


def truncated_gzip(path, first, second):
    """A gzip file as a crash leaves it: `first` lines sync-flushed, then `second` lines cut off part way."""
    fh = gzip.open(path, "wt", compresslevel=3)
    fh.write("".join(line + "\n" for line in first))
    fh.flush()
    size1 = os.path.getsize(path)
    fh.write("".join(line + "\n" for line in second))
    fh.flush()
    size2 = os.path.getsize(path)
    with open(path, "rb") as raw:
        data = raw.read()
    fh.close()
    with open(path, "wb") as raw:
        raw.write(data[:size1 + (size2 - size1) // 2])


# ---------------------------------------------------------------- read_lines and messages

def test_read_lines_plain_skips_bad_lines(tmp_path):
    p = tmp_path / "a.jsonl"
    p.write_text('{"a": 1}\nnot json\n\n{"b": 2}\n[1, 2]\n7\n{"c": 3}', encoding="utf-8")
    assert list(R.read_lines(str(p))) == [{"a": 1}, {"b": 2}, {"c": 3}]


def test_read_lines_gzip(tmp_path):
    p = tmp_path / "a.jsonl.gz"
    with gzip.open(p, "wt", encoding="utf-8") as fh:
        fh.write('{"a": 1}\n{oops\n{"b": 2}\n')
    assert list(R.read_lines(str(p))) == [{"a": 1}, {"b": 2}]


def test_read_lines_truncated_gzip_yields_what_came_before_and_does_not_raise(tmp_path):
    p = str(tmp_path / "a.jsonl.gz")
    truncated_gzip(p, [json.dumps({"i": i}) for i in range(500)], [json.dumps({"i": i}) for i in range(500, 1000)])
    got = [d["i"] for d in R.read_lines(p)]
    assert got[:500] == list(range(500))
    assert got == list(range(len(got))) and len(got) < 1000


def test_read_lines_missing_file_yields_nothing(tmp_path):
    assert list(R.read_lines(str(tmp_path / "nope.jsonl"))) == []


def test_messages_order_files_by_hour_then_restart_number(tmp_path):
    names = ["ws-20261026T01.txt.gz", "ws-20261026T00.10.txt.gz", "ws-20261026T00.2.txt.gz",
             "ws-20261026T00.txt.gz", "ws-20261025T23.1.txt.gz", "ws-20261026T00.1.txt.gz"]
    for i, n in enumerate(names):
        write_ws(tmp_path / n, [f'{1000 + i}.000 {{"type": "ok", "f": "{n}"}}'])
    for other in ("ws-20261026T02.txt.gz.part", "ws-20261026T03.txt.gz.dup1", "ws-2026102604.txt.gz"):
        write_ws(tmp_path / other, ['5.000 {"type": "ok", "f": "never"}'])
    (tmp_path / "markets.jsonl").write_text('{"ticker": "X"}\n', encoding="utf-8")
    got = [m["f"] for _, m in R.messages(str(tmp_path))]
    assert got == ["ws-20261025T23.1.txt.gz", "ws-20261026T00.txt.gz", "ws-20261026T00.1.txt.gz",
                   "ws-20261026T00.2.txt.gz", "ws-20261026T00.10.txt.gz", "ws-20261026T01.txt.gz"]


def test_messages_parse_rt_and_skip_bad_lines(tmp_path):
    write_ws(tmp_path / "ws-20261026T00.txt.gz",
             ['1792972801.250 {"type": "trade", "sid": 2}', "garbage", "1792972802.000 {not json",
              'x.y {"type": "ok"}', "", '1792972802.500 [1, 2]', '1792972803.5 {"type":"ok"}'])
    assert list(R.messages(str(tmp_path))) == [(1792972801.25, {"type": "trade", "sid": 2}),
                                               (1792972803.5, {"type": "ok"})]


def test_messages_truncated_file_yields_what_came_before_then_the_next_file(tmp_path):
    truncated_gzip(str(tmp_path / "ws-20261026T00.txt.gz"),
                   [f'{T0 + i:.3f} {{"type": "ok", "i": {i}}}' for i in range(300)],
                   [f'{T0 + i:.3f} {{"type": "ok", "i": {i}}}' for i in range(300, 600)])
    write_ws(tmp_path / "ws-20261026T00.1.txt.gz", [f'{T0 + 700:.3f} {{"type": "ok", "i": -1}}'])
    got = [m["i"] for _, m in R.messages(str(tmp_path))]
    assert got[:300] == list(range(300)) and got[-1] == -1
    assert got[:-1] == list(range(len(got) - 1)) and len(got) < 601


# ---------------------------------------------------------------- Book

def test_book_snapshot_gives_bids_asks_and_mids():
    b = book_of(yes=[(0.95, 100), (0.94, 50)], no=[(0.03, 40), (0.02, 10)])
    assert b.ok is True
    assert b.bid("yes") == approx(0.95) and b.bid("no") == approx(0.03)
    assert b.ask("yes") == approx(0.97) and b.ask("no") == approx(0.05)     # a YES ask is a NO bid at 1 - p
    assert b.mid("yes") == approx(0.96) and b.mid("no") == approx(0.04)
    assert b.size("yes", 0.95) == 100 and b.size("no", 0.02) == 10 and b.size("yes", 0.93) == 0


def test_new_book_is_empty_and_not_ok():
    b = R.Book()
    assert b.ok is False
    assert b.bid("yes") is None and b.ask("yes") is None and b.mid("no") is None and b.size("yes", 0.5) == 0


def test_book_missing_side_is_empty():
    b = book_of(yes=[(0.95, 100)])
    assert b.bid("no") is None and b.ask("yes") is None and b.mid("yes") is None
    assert b.ask("no") == approx(0.05) and b.mid("no") is None


def test_book_snapshot_replaces_both_sides():
    b = book_of(yes=[(0.95, 100)], no=[(0.03, 40)])
    b.snapshot(body_snap(no=[(0.10, 5)]))
    assert b.bid("yes") is None and b.size("yes", 0.95) == 0 and b.bid("no") == approx(0.10)


def test_book_delta_adds_and_removes_levels():
    b = book_of(yes=[(0.95, 100), (0.94, 50)], no=[(0.03, 40)])
    b.delta(body_delta("yes", 0.95, -100))
    assert b.size("yes", 0.95) == 0 and b.bid("yes") == approx(0.94)
    b.delta(body_delta("yes", 0.96, 5))
    assert b.bid("yes") == approx(0.96) and b.size("yes", 0.96) == 5
    b.delta(body_delta("yes", 0.94, -80))                        # below zero: gone
    b.delta(body_delta("yes", 0.96, -5))
    assert b.bid("yes") is None
    for d in ("0.10", "0.20", "-0.30"):                           # float dust under 1e-9 is gone too
        b.delta({"market_ticker": "T", "price_dollars": "0.5000", "delta_fp": d, "side": "no"})
    assert b.size("no", 0.5) == 0 and b.bid("no") == approx(0.03)


def test_book_prices_match_at_four_decimals():
    b = book_of(yes=[(0.984, 7)], no=[(0.005, 2)])
    assert b.size("yes", 0.984) == 7 and b.size("yes", 0.98400001) == 7
    b.delta({"market_ticker": "T", "price_dollars": "0.98400", "delta_fp": "3.03", "side": "yes"})
    assert b.size("yes", 0.984) == approx(10.03)
    assert b.ask("yes") == approx(0.995) and b.ask("no") == approx(0.016)


def test_book_invalidate_until_next_snapshot():
    b = book_of(yes=[(0.95, 100)], no=[(0.03, 40)])
    b.invalidate()
    assert b.ok is False
    b.delta(body_delta("yes", 0.95, 1))
    assert b.ok is False
    b.snapshot(body_snap(yes=[(0.95, 100)], no=[(0.03, 40)]))
    assert b.ok is True


def test_favourite_is_the_side_with_yes_mid_at_or_over_half():
    assert R.favourite(book_of(yes=[(0.95, 1)], no=[(0.03, 1)])) == "yes"
    assert R.favourite(book_of(yes=[(0.03, 1)], no=[(0.95, 1)])) == "no"
    assert R.favourite(book_of(yes=[(0.49, 1)], no=[(0.49, 1)])) == "yes"     # mid exactly 0.5
    assert R.favourite(book_of(yes=[(0.48, 1)], no=[(0.50, 1)])) == "no"      # mid 0.49
    assert R.favourite(book_of(yes=[(0.95, 1)])) is None
    assert R.favourite(R.Book()) is None


def test_taker_fee_rounds_up_to_a_hundredth_of_a_cent():
    assert R.taker_fee(15, 0.95) == approx(0.0499, abs=1e-12)     # 0.049875 -> 0.0499
    assert R.taker_fee(100, 0.5) == approx(1.75, abs=1e-12)       # exactly 1.75: float dust must not add a step
    assert R.taker_fee(1, 0.99) == approx(0.0007, abs=1e-12)      # 0.000693 -> 0.0007
    assert R.taker_fee(0, 0.9) == 0


def test_tick_at_reads_the_price_grid():
    assert R.tick_at(RANGES, "yes", 0.95) == approx(0.001)
    assert R.tick_at(RANGES, "yes", 0.50) == approx(0.01)
    assert R.tick_at(RANGES, "no", 0.95) == approx(0.001)         # NO bid 95c = YES ask 5c: the fine end
    assert R.tick_at(RANGES, "no", 0.10) == approx(0.01)          # YES 90c and just under: cents
    assert R.tick_at({"tick_size": 1}, "yes", 0.95) == approx(0.01)
    assert R.tick_at({"price_level_structure": "tapered_deci_cent"}, "yes", 0.95) == approx(0.001)
    assert R.tick_at({}, "yes", 0.95) == approx(0.01)
    assert R.tick_at(None, "no", 0.95) == approx(0.01)


# ---------------------------------------------------------------- Order.on_trade

def test_trade_where_the_taker_bought_our_side_never_fills():
    o = R.Order("yes", 0.95, 15, 0.0, 0)
    o.on_trade(body_trade(0.90, 10, "yes"), rt=1.0)
    assert o.filled == 0 and o.fills == [] and not o.done


def test_trade_below_the_limit_fills_the_whole_count_up_to_what_is_left():
    o = R.Order("yes", 0.95, 15, 0.0, ahead=500)                  # the queue doesn't matter below L
    o.on_trade(body_trade(0.94, 10, "no"), rt=5.0)
    assert o.filled == 10 and o.fills == [(5.0, 10)]
    o.on_trade(body_trade(0.9499, 10, "no"), rt=6.0)             # 0.0001 under is still under
    assert o.filled == 15 and o.fills == [(5.0, 10), (6.0, 5)] and o.done


def test_trade_at_the_limit_uses_up_the_queue_ahead_first():
    o = R.Order("yes", 0.95, 15, 0.0, ahead=10)
    o.on_trade(body_trade(0.95, 4, "no", ts=1000), rt=1.0)
    assert o.ahead == 6 and o.filled == 0
    o.on_trade(body_trade(0.95, 10, "no", ts=2000), rt=2.0)
    assert o.ahead == 0 and o.filled == 4 and o.fills == [(2.0, 4)]
    o.on_trade({"market_ticker": "T", "yes_price_dollars": "0.9500004", "no_price_dollars": "0.0499996",
                "count_fp": "3.00", "taker_side": "no", "ts_ms": 3000}, rt=3.0)   # within a millionth: at L
    assert o.filled == 7


def test_trade_above_the_limit_does_nothing():
    o = R.Order("yes", 0.95, 15, 0.0, 0)
    o.on_trade(body_trade(0.96, 10, "no"), rt=1.0)
    o.on_trade(body_trade(0.951, 10, "no"), rt=2.0)
    assert o.filled == 0


def test_no_side_order_reads_the_no_price():
    o = R.Order("no", 0.95, 15, 0.0, 0)
    o.on_trade(body_trade(0.06, 3, "yes"), rt=1.0)    # bought YES at 6c = sold NO at 94c, under our 95c
    assert o.filled == 3
    o.on_trade(body_trade(0.01, 3, "no"), rt=2.0)     # bought NO: a buyer of our side
    o.on_trade(body_trade(0.04, 3, "yes"), rt=3.0)    # sold NO at 96c: above our 95c
    assert o.filled == 3


def test_block_trades_never_fill():
    # a block trade is arranged off the book: it doesn't show a seller who would have hit a resting bid
    o = R.Order("yes", 0.95, 15, 0.0, ahead=3)
    b = body_trade(0.90, 8, "no")
    b["is_block_trade"] = True
    o.on_trade(b, rt=1.0)
    o.on_trade(dict(b, yes_price_dollars="0.9500", no_price_dollars="0.0500"), rt=2.0)
    assert o.filled == 0 and o.ahead == 3
    b["is_block_trade"] = False
    o.on_trade(b, rt=3.0)
    assert o.filled == 8


def test_fractional_counts_fill_fractionally():
    o = R.Order("yes", 0.95, 15, 0.0, 0)
    o.on_trade(body_trade(0.94, 0.03, "no"), rt=1.0)
    assert o.filled == approx(0.03)


def test_a_done_order_ignores_later_fills():
    book = book_of(yes=[(0.90, 1)], no=[(0.03, 40)])
    o = R.Order("yes", 0.95, 5, 0.0, 0)
    o.on_trade(body_trade(0.90, 8, "no"), rt=1.0)
    assert o.done and o.filled == 5
    o.on_trade(body_trade(0.90, 8, "no"), rt=2.0)
    d = body_delta("no", 0.05, 10)
    book.delta(d)
    o.on_delta(d, book, rt=3.0)
    assert o.fills == [(1.0, 5)] and o.filled == 5


def test_messages_before_the_order_was_posted_are_ignored():
    o = R.Order("yes", 0.95, 15, 100.0, 0)
    o.on_trade(body_trade(0.90, 8, "no"), rt=99.0)
    assert o.filled == 0
    o.on_trade(body_trade(0.90, 8, "no"), rt=100.0)
    assert o.filled == 8


def test_events_kalshi_stamps_before_the_order_was_posted_never_fill_it():
    # seen on the real feed: a sale stamped 6 ms before the mark arrived 9 ms after it
    o = R.Order("yes", 0.95, 15, 100.0, ahead=10)
    o.on_trade(body_trade(0.90, 8, "no", ts=99994), rt=100.009)
    o.on_trade(body_trade(0.95, 8, "no", ts=99995), rt=100.010)     # nor eats the queue
    assert o.filled == 0 and o.ahead == 10
    book = book_of(yes=[(0.90, 1)], no=[(0.03, 40)])
    body = body_delta("no", 0.05, 10, ts=99996)
    book.delta(body)
    o.on_delta(body, book, rt=100.011)
    assert o.filled == 0
    o.on_trade(body_trade(0.90, 8, "no", ts=100002), rt=100.012)
    assert o.filled == 8


def test_a_queue_cut_stamped_before_posting_still_counts():
    # the level really is smaller: the mark book just hadn't heard yet
    book = book_of(yes=[(0.95, 4)], no=[(0.03, 40)])
    o = R.Order("yes", 0.95, 15, 100.0, ahead=10)
    body = body_delta("yes", 0.95, -6, ts=99990)
    o.on_delta(body, book, rt=100.01)
    assert o.ahead == 4


def test_rt_defaults_to_the_message_time():
    o = R.Order("yes", 0.95, 15, 0.0, 0)
    o.on_trade(body_trade(0.90, 2, "no", ts=1792973290500))
    assert o.fills == [(approx(1792973290.5), 2)]


# ---------------------------------------------------------------- Order.on_delta

def test_delta_on_our_level_shrinks_the_queue_ahead_but_never_grows_it():
    book = book_of(yes=[(0.95, 100)], no=[(0.03, 40)])
    o = R.Order("yes", 0.95, 15, 0.0, ahead=100)

    def step(side, price, d):
        body = body_delta(side, price, d, ts=int(d * 1000) + 777)
        book.delta(body)
        o.on_delta(body, book, rt=1.0)

    step("yes", 0.95, -30)        # level 70: nobody was behind us, so the 30 cancelled were ahead
    assert o.ahead == 70
    step("yes", 0.95, 50)         # new orders at L join behind us
    assert o.ahead == 70
    step("yes", 0.95, -40)        # level 80: those could all have been behind us
    assert o.ahead == 70
    step("yes", 0.95, -75)        # level 5
    assert o.ahead == 5
    step("yes", 0.94, -10)        # another price on our side: nothing
    assert o.ahead == 5 and o.filled == 0


def test_new_sell_at_or_under_our_limit_fills_by_its_size():
    book = book_of(yes=[(0.95, 100)], no=[(0.03, 40)])
    o = R.Order("yes", 0.96, 15, 0.0, 0)                        # alone at 96c, a cent over the bid

    def step(side, price, d, rt):
        body = body_delta(side, price, d)
        book.delta(body)
        o.on_delta(body, book, rt=rt)

    step("no", 0.03, 20, 1.0)     # a YES ask at 97c: over our 96c
    assert o.filled == 0
    step("no", 0.04, 6, 2.0)      # a YES ask at 96c: it would have traded with us
    assert o.filled == 6 and o.fills == [(2.0, 6)]
    step("no", 0.04, -6, 3.0)     # a cancel on the other side: nothing
    assert o.filled == 6
    step("no", 0.05, 20, 4.0)     # a YES ask at 95c: under our 96c
    assert o.filled == 15 and o.done and o.fills == [(2.0, 6), (4.0, 9)]


def test_new_sell_first_fills_the_queue_ahead():
    book = book_of(yes=[(0.90, 1)], no=[(0.03, 40)])
    o = R.Order("yes", 0.95, 15, 0.0, ahead=4)
    body = body_delta("no", 0.05, 10)
    book.delta(body)
    o.on_delta(body, book, rt=1.0)
    assert o.ahead == 0 and o.filled == 6


@pytest.mark.parametrize("delta_first", [True, False])
def test_a_trade_and_its_own_book_delta_are_counted_once(delta_first):
    # 10 ahead of us at 95c, then 5 join behind us. A seller takes 12 at 95c: the 10 ahead fill, then 2 of ours.
    book = book_of(yes=[(0.95, 10)], no=[(0.03, 40)])
    o = R.Order("yes", 0.95, 15, 0.0, ahead=10)
    join = body_delta("yes", 0.95, 5, ts=1000)
    book.delta(join)
    o.on_delta(join, book, rt=1.0)
    d = body_delta("yes", 0.95, -12, ts=2000)
    t = body_trade(0.95, 12, "no", ts=2000)
    if delta_first:                       # how Kalshi usually sends it
        book.delta(d)
        o.on_delta(d, book, rt=2.001)
        o.on_trade(t, rt=2.002)
    else:
        o.on_trade(t, rt=2.001)
        book.delta(d)
        o.on_delta(d, book, rt=2.002)
    assert o.filled == approx(2) and o.ahead == approx(0)


def test_pairing_uses_receive_time_when_messages_have_no_ts():
    book = book_of(yes=[(0.95, 10)], no=[(0.03, 40)])
    o = R.Order("yes", 0.95, 15, 0.0, ahead=10)
    d = body_delta("yes", 0.95, -6)
    book.delta(d)
    o.on_delta(d, book, rt=2.000)
    assert o.ahead == 4
    o.on_trade(body_trade(0.95, 6, "no"), rt=2.010)       # the same 6: already out of the queue
    assert o.ahead == 4 and o.filled == 0


def test_a_cancel_ahead_still_moves_us_up_when_no_trade_follows():
    book = book_of(yes=[(0.95, 10)], no=[(0.03, 40)])
    o = R.Order("yes", 0.95, 15, 0.0, ahead=10)
    for body, rt in ((body_delta("yes", 0.95, -4, ts=1000), 1.0), (body_delta("yes", 0.95, 3, ts=1500), 1.5)):
        book.delta(body)
        o.on_delta(body, book, rt=rt)
    assert o.ahead == 6                                    # level 9: 6 ahead of us, 3 behind
    o.on_trade(body_trade(0.95, 7, "no", ts=9000), rt=9.0)
    assert o.filled == approx(1) and o.ahead == 0


# ---------------------------------------------------------------- replay

def test_replay_row_uses_the_book_from_the_last_message_before_the_mark(tmp_path):
    f = Feed()
    base(f)
    f.delta(MARK_T - 0.001, A, "yes", 0.955, 20)        # the last message before the mark counts
    f.delta(MARK_T, A, "yes", 0.96, 10)                 # one at the mark itself does not
    rows = R.replay(f.write(tmp_path, [market(A, raw=RANGES)], [result(A, "yes")]))
    assert len(rows) == 1
    r = rows[0]
    assert r["ticker"] == A and r["series"] == "KXBTC15M" and r["window_open"] == T0
    assert r["side"] == "yes" and r["bid"] == approx(0.955) and r["ask"] == approx(0.97)
    assert r["spread"] == approx(0.015) and r["in_band"] is True
    assert r["result"] == "yes" and r["won"] is True
    assert r["complete"] is True and r["mark"] == MARK_T and r["size"] == 15
    assert r["taker"]["price"] == approx(0.97) and r["taker"]["fee"] == approx(R.taker_fee(15, 0.97))
    assert set(r["orders"]) == {"join", "tick", "cent"}


def test_replay_skips_markets_without_a_usable_book_at_the_mark(tmp_path):
    f = Feed()
    f.trade(T0 + 100, A, 0.95, 5, "no")                                  # A: trades but never a book
    f.snap(T0 + 20, B, yes=[(0.95, 100)], sid=3)                          # B: no NO side, so no favourite
    base(f, C, sid=5)                                                     # C: its sid loses a message
    f.gap(5)
    f.delta(T0 + 300, C, "yes", 0.90, 1, sid=5)
    base(f, D, sid=7)                                                     # D: fine
    rows = R.replay(f.write(tmp_path, [market(t) for t in (A, B, C, D, E)]))   # E: never in the feed
    assert [r["ticker"] for r in rows] == [D]


def test_replay_a_new_snapshot_after_a_gap_makes_the_book_usable_again(tmp_path):
    f = Feed()
    base(f, A, sid=1)
    base(f, B, sid=3)
    f.gap(1)
    f.delta(T0 + 300, A, "yes", 0.90, 1, sid=1)      # A's sid jumps: A unknown, B untouched
    f.snap(T0 + 400, A, yes=[(0.96, 10)], no=[(0.02, 5)], sid=1)
    rows = by_ticker(R.replay(f.write(tmp_path, [market(A), market(B)])))
    assert set(rows) == {A, B}
    assert rows[A]["bid"] == approx(0.96) and rows[A]["ask"] == approx(0.98)


@pytest.mark.parametrize("no_bid, ask, in_band", [(0.08, 0.92, True), (0.001, 0.999, True), (0.081, 0.919, False),
                                                  (0.2, 0.8, False)])
def test_replay_in_band_is_the_bots_band(tmp_path, no_bid, ask, in_band):
    f = Feed()
    f.snap(T0 + 20, A, yes=[(0.75, 100)], no=[(no_bid, 40)])
    r = R.replay(f.write(tmp_path, [market(A)]))[0]
    assert r["ask"] == approx(ask) and r["in_band"] is in_band
    if not in_band:
        assert r["orders"] is None and r["taker"] is None and r["hybrid"] is None
    else:
        assert r["orders"]["join"]["L"] == approx(0.75)


def test_replay_join_tick_and_cent_limits(tmp_path):
    f = Feed()
    base(f, A, sid=1)                                                    # price grid: 0.1c steps over 90c
    base(f, B, sid=3)                                                    # tick_size 1 cent
    base(f, C, sid=5)                                                    # nothing said: 1 cent
    f.snap(T0 + 20, D, yes=[(0.95, 100)], no=[(0.049, 40)], sid=7)      # ask 95.1c: no room for tick or cent
    f.snap(T0 + 20, E, yes=[(0.04, 10)], no=[(0.95, 100), (0.90, 5)], sid=9)   # NO is the favourite
    mk = [market(A, raw=RANGES), market(B, raw={"tick_size": 1}), market(C), market(D, raw=RANGES),
          market(E, raw=RANGES)]
    rows = by_ticker(R.replay(f.write(tmp_path, mk, [result(E, "yes")])))
    o = rows[A]["orders"]
    assert o["join"]["L"] == approx(0.95) and o["tick"]["L"] == approx(0.951) and o["cent"]["L"] == approx(0.96)
    assert rows[B]["orders"]["tick"]["L"] == approx(0.96)
    assert rows[C]["orders"]["tick"]["L"] == approx(0.96)
    assert rows[D]["ask"] == approx(0.951) and rows[D]["orders"]["join"]["L"] == approx(0.95)
    assert rows[D]["orders"]["tick"] is None and rows[D]["orders"]["cent"] is None
    e = rows[E]
    assert e["side"] == "no" and e["bid"] == approx(0.95) and e["ask"] == approx(0.96)
    assert e["orders"]["tick"]["L"] == approx(0.951) and e["orders"]["cent"] is None
    assert e["result"] == "yes" and e["won"] is False
    assert rows[A]["result"] is None and rows[A]["won"] is None


def test_orders_land_LAND_seconds_after_the_mark():
    # the bot's orders reach Kalshi about 0.124 s after minute 8 (the Ohio server's median, Oct 2026)
    assert R.LAND == approx(0.124)


def test_nothing_in_the_first_LAND_seconds_fills_a_pretend_order(tmp_path):
    f = Feed()
    base(f)
    f.trade(MARK_T + 0.05, A, 0.90, 8, "no")            # a sale under every limit, before the order has landed
    f.trade(MARK_T + 0.30, A, 0.90, 5, "no")            # after it landed
    r = R.replay(f.write(tmp_path, [market(A)]))[0]
    assert r["orders"]["join"]["filled"] == approx(5)
    assert r["orders"]["join"]["first_fill_rt"] == approx(MARK_T + 0.30)


def test_the_join_queue_is_the_level_when_the_order_lands_not_at_the_mark(tmp_path):
    f = Feed()
    base(f)                                             # 100 bid at 95c at the mark
    f.delta(MARK_T + 0.05, A, "yes", 0.95, 30)          # 30 more join at 95c before ours lands: they're ahead of it
    f.trade(T0 + 500, A, 0.95, 129, "no")
    f.trade(T0 + 510, A, 0.95, 4, "no")
    r = R.replay(f.write(tmp_path, [market(A)]))[0]
    assert r["orders"]["join"]["filled"] == approx(3)   # 130 ahead: 129 + 1 eaten, then 3 for us


def test_replay_join_waits_behind_the_queue_at_the_mark(tmp_path):
    f = Feed()
    base(f)
    f.delta(MARK_T - 1, A, "yes", 0.95, 20)           # 120 at 95c when the order is placed
    f.trade(T0 + 500, A, 0.95, 119, "no")
    f.trade(T0 + 510, A, 0.95, 3, "no")
    r = R.replay(f.write(tmp_path, [market(A)]))[0]
    assert r["orders"]["join"]["filled"] == approx(2)
    assert r["orders"]["join"]["fills"] == [(T0 + 510, approx(2))]
    assert r["orders"]["cent"]["filled"] == approx(15)  # 96c: both trades were under it
    assert r["orders"]["cent"]["first_fill_rt"] == T0 + 500


def test_replay_fills_and_the_price_after_them(tmp_path):
    f = Feed()
    base(f)
    f.trade(T0 + 470, A, 0.90, 50, "no")               # before the mark: no order yet
    f.trade(T0 + 490, A, 0.94, 5, "no")                # under every limit: join, tick and cent get 5
    f.delta(T0 + 492, A, "no", 0.04, 10)               # YES ask 96c: fills the cent order (L 96c) by 10
    f.delta(T0 + 500, A, "yes", 0.955, 5)              # bid 95.5c
    f.delta(T0 + 540, A, "no", 0.04, -10)              # ask back to 97c
    f.delta(T0 + 800, A, "yes", 0.96, 1)               # bid 96c
    f.trade(T0 + 905, A, 0.90, 50, "no")               # after the close: too late
    r = R.replay(f.write(tmp_path, [market(A, raw=RANGES)]))[0]
    for name in ("join", "tick"):
        o = r["orders"][name]
        assert o["filled"] == approx(5) and o["fills"] == [(T0 + 490, approx(5))]
        assert o["first_fill_rt"] == T0 + 490
        assert o["mid_at_fill"] == approx(0.96)
        assert o["mid_after"] == {5: approx(0.955), 30: approx(0.9575), 60: approx(0.9625)}
        assert o["mid_close"] == approx(0.965)
    c = r["orders"]["cent"]
    assert c["filled"] == approx(15) and c["fills"] == [(T0 + 490, approx(5)), (T0 + 492, approx(10))]
    assert c["mid_at_fill"] == approx(0.96) and c["mid_after"][5] == approx(0.955)
    assert r["taker"]["mid_at_fill"] == approx(0.96)
    # the taker's baseline: the mid at mark + 5 s (485), + 30 s (510) and + 60 s (540: the move at 540 not yet in)
    assert r["taker"]["mid_after"] == {5: approx(0.96), 30: approx(0.9575), 60: approx(0.9575)}
    assert r["complete"] is True


def test_replay_unfilled_order_has_no_fill_values_but_has_the_close(tmp_path):
    f = Feed()
    base(f)
    r = R.replay(f.write(tmp_path, [market(A)]))[0]
    o = r["orders"]["join"]
    assert o["filled"] == 0 and o["fills"] == [] and o["first_fill_rt"] is None and o["mid_at_fill"] is None
    assert o["mid_after"] == {5: None, 30: None, 60: None} and o["mid_close"] == approx(0.96)


def test_replay_an_empty_side_at_the_close_is_not_lost_data(tmp_path):
    f = Feed()
    base(f)
    f.delta(T0 + 800, A, "no", 0.03, -40)
    f.delta(T0 + 801, A, "no", 0.02, -10)          # nobody sells YES any more: no ask, no mid
    r = R.replay(f.write(tmp_path, [market(A)]))[0]
    assert r["orders"]["join"]["mid_close"] is None and r["complete"] is True


def test_replay_price_checks_after_the_close_are_none(tmp_path):
    f = Feed()
    base(f)
    f.trade(T0 + 880, A, 0.94, 5, "no")
    r = R.replay(f.write(tmp_path, [market(A)]))[0]
    o = r["orders"]["join"]
    assert o["mid_after"][5] == approx(0.96) and o["mid_after"][30] is None and o["mid_after"][60] is None


def test_replay_mid_at_minutes_6_and_7(tmp_path):
    f = Feed()
    base(f, A, sid=1)
    f.delta(T0 + 400, A, "yes", 0.955, 1, sid=1)
    base(f, B, rt=T0 + 400, sid=3)                                            # B's book only from 400 s
    f.snap(T0 + 20, C, yes=[(0.04, 10)], no=[(0.95, 100)], sid=5)            # NO favourite: NO-side mids
    f.delta(T0 + 400, C, "yes", 0.02, 1, sid=5)
    rows = by_ticker(R.replay(f.write(tmp_path, [market(A), market(B), market(C)])))
    assert rows[A]["mid_6"] == approx(0.96) and rows[A]["mid_7"] == approx(0.9625)
    assert rows[B]["mid_6"] is None and rows[B]["mid_7"] == approx(0.96)
    assert rows[C]["side"] == "no" and rows[C]["mid_6"] == approx(0.955) and rows[C]["mid_7"] == approx(0.955)


def test_replay_gap_after_the_mark_stops_book_fills_until_a_new_snapshot(tmp_path):
    f = Feed()
    base(f, A, sid=1)
    base(f, C, sid=1)
    base(f, B, sid=3)
    f.gap(1)
    f.delta(T0 + 500, A, "yes", 0.94, 1, sid=1)            # sid 1 jumps: A and C unknown
    f.delta(T0 + 505, A, "yes", 0.95, -100, sid=1)          # A empties its 95c level ...
    f.delta(T0 + 510, A, "no", 0.05, 20, sid=1)             # ... and a seller offers at 95c: can't be proven
    f.trade(T0 + 520, A, 0.94, 3, "no")                     # a trade still proves a seller
    f.snap(T0 + 600, C, yes=[(0.94, 50)], no=[(0.03, 40)], sid=1)   # C known again (its 95c level is gone)
    f.delta(T0 + 610, C, "no", 0.05, 20, sid=1)             # a seller at 95c: fills C's join
    f.delta(T0 + 505, B, "yes", 0.95, -100, sid=3)          # B: same moves, no gap
    f.delta(T0 + 510, B, "no", 0.05, 20, sid=3)
    rows = by_ticker(R.replay(f.write(tmp_path, [market(A), market(B), market(C)])))
    a, b, c = rows[A], rows[B], rows[C]
    assert a["orders"]["join"]["filled"] == approx(3) and a["orders"]["join"]["mid_close"] is None
    assert a["complete"] is False
    assert b["orders"]["join"]["filled"] == approx(15) and b["complete"] is True
    assert b["orders"]["join"]["mid_close"] == approx(0.945)
    assert c["orders"]["join"]["filled"] == approx(15) and c["orders"]["join"]["fills"] == [(T0 + 610, approx(15))]
    assert c["complete"] is False and c["orders"]["join"]["mid_close"] == approx(0.945)


def test_replay_ignores_deltas_from_another_subscription(tmp_path):
    f = Feed()
    base(f, A, sid=1)
    f.delta(T0 + 400, A, "yes", 0.96, 10, sid=3)
    r = R.replay(f.write(tmp_path, [market(A)]))[0]
    assert r["bid"] == approx(0.95)


def test_replay_feed_silence_over_30s_hides_the_mark(tmp_path):
    f = Feed()
    base(f)
    rows = R.replay(f.write(tmp_path, [market(A)], quiet=(455, 485)))      # nothing from 450 s to 490 s
    assert rows == []


def test_the_quiet_start_of_a_window_is_not_a_hole(tmp_path):
    # seen in the Oct 25 server trial: the last window's markets close at 900 s, and the recorder subscribes the new
    # window's about 32 s later, so the feed says nothing for over 30 s while no market is open
    nxt = "KXBTC15M-26OCT252030-30"
    f = Feed()
    base(f)
    f.trade(T0 + 895, A, 0.94, 2, "no")
    base(f, t=nxt, rt=T0 + 900 + 33)
    rows, stats = R.replay_with_stats(f.write(tmp_path, [market(A), market(nxt, open_=T0 + 900)],
                                              until=T0 + 1810, quiet=(896, 932)))
    assert stats["holes"] == 0
    got = by_ticker(rows)
    assert got[A]["complete"] is True and got[nxt]["complete"] is True


def test_a_silence_while_a_market_is_open_is_still_a_hole(tmp_path):
    f = Feed()
    base(f)
    rows, stats = R.replay_with_stats(f.write(tmp_path, [market(A)], quiet=(505, 545)))
    assert stats["holes"] == 1 and rows[0]["complete"] is False


def test_replay_short_silence_is_fine(tmp_path):
    f = Feed()
    base(f)
    rows = R.replay(f.write(tmp_path, [market(A)], quiet=(455, 470)))      # 20 s
    assert len(rows) == 1 and rows[0]["complete"] is True


def test_replay_silence_after_the_mark_marks_the_row_incomplete(tmp_path):
    f = Feed()
    base(f)
    f.trade(T0 + 495, A, 0.94, 2, "no")
    r = R.replay(f.write(tmp_path, [market(A)], quiet=(505, 545)))[0]
    o = r["orders"]["join"]
    assert r["complete"] is False and o["filled"] == approx(2)
    assert o["mid_after"][5] == approx(0.96) and o["mid_after"][30] is None and o["mid_close"] is None


def test_replay_recorder_restart_file_makes_books_unknown(tmp_path):
    f = Feed()
    base(f)
    rows = R.replay(f.write(tmp_path, [market(A)], split=T0 + 475))
    assert rows == []
    (tmp_path / "x").mkdir()
    g = Feed()
    base(g)
    g.snap(T0 + 476, A, yes=[(0.95, 100)], no=[(0.04, 40)])               # the restarted recorder's snapshot
    rows = R.replay(g.write(tmp_path / "x", [market(A)], split=T0 + 475))
    assert len(rows) == 1 and rows[0]["ask"] == approx(0.96)


def test_replay_data_ending_before_the_close(tmp_path):
    f = Feed()
    base(f)
    f.trade(T0 + 600, A, 0.94, 4, "no")
    r = R.replay(f.write(tmp_path, [market(A)], until=T0 + 700))[0]
    assert r["orders"]["join"]["filled"] == approx(4)
    assert r["orders"]["join"]["mid_close"] is None and r["complete"] is False


def test_replay_hybrid(tmp_path):
    f = Feed()
    base(f, A, sid=1)                                   # A: 5 fill as a maker, then 10 bought at 96.5c
    f.trade(T0 + 500, A, 0.94, 5, "no")
    f.delta(T0 + 530, A, "no", 0.035, 10, sid=1)       # ask 96.5c, still over the join's 95c
    f.trade(T0 + 600, A, 0.94, 8, "no")                # after the switch: the join's, not the hybrid's
    base(f, B, sid=3)                                   # B: the favourite crashes; the rest is not bought
    f.delta(T0 + 505, B, "yes", 0.95, -100, sid=3)
    f.delta(T0 + 506, B, "yes", 0.94, -50, sid=3)
    f.delta(T0 + 507, B, "yes", 0.90, 10, sid=3)
    f.delta(T0 + 508, B, "no", 0.09, 10, sid=3)         # a seller at 91c: fills 10 of the join
    base(f, C, sid=5)                                   # C: no ask at the switch: nothing bought
    f.delta(T0 + 505, C, "no", 0.03, -40, sid=5)
    f.delta(T0 + 506, C, "no", 0.02, -10, sid=5)
    rows = by_ticker(R.replay(f.write(tmp_path, [market(A), market(B), market(C)])))
    h = rows[A]["hybrid"]
    assert h["maker_filled"] == approx(5) and h["taker_filled"] == approx(10)
    assert h["taker_price"] == approx(0.965) and h["fee"] == approx(R.taker_fee(10, 0.965))
    assert h["first_fill_rt"] == T0 + 500
    assert rows[A]["orders"]["join"]["filled"] == approx(13)
    h = rows[B]["hybrid"]
    assert h["maker_filled"] == approx(10) and h["taker_filled"] == 0 and h["taker_price"] is None
    assert h["fee"] == 0
    h = rows[C]["hybrid"]
    assert h["maker_filled"] == 0 and h["taker_filled"] == 0 and h["taker_price"] is None and h["fee"] == 0
    assert h["first_fill_rt"] is None


def test_replay_size(tmp_path):
    f = Feed()
    base(f)
    f.trade(T0 + 500, A, 0.94, 8, "no")
    r = R.replay(f.write(tmp_path, [market(A)]), size=5)[0]
    assert r["size"] == 5 and r["orders"]["join"]["filled"] == approx(5)
    assert r["taker"]["fee"] == approx(R.taker_fee(5, 0.97))
    assert r["hybrid"]["maker_filled"] == approx(5) and r["hybrid"]["taker_filled"] == 0


def test_replay_ignores_tickers_it_was_not_told_about(tmp_path):
    f = Feed()
    base(f, A, sid=1)
    base(f, "KXOTHER-1", sid=3)
    f.trade(T0 + 500, "KXOTHER-1", 0.90, 5, "no")
    rows = R.replay(f.write(tmp_path, [market(A)], [result("KXOTHER-1", "yes")]))
    assert [r["ticker"] for r in rows] == [A]


def test_replay_of_an_empty_folder(tmp_path):
    assert R.replay(str(tmp_path)) == []


def test_replay_reads_every_markets_and_results_file_a_reset_left(tmp_path):
    # pull.py keeps a reset server's logs beside the laptop's, as markets.reset<n>.jsonl and results.reset<n>.jsonl
    f = Feed()
    base(f, A, sid=1)
    base(f, B, sid=3)
    folder = f.write(tmp_path, [market(A)], [result(A, "yes")])
    extra = {"markets.reset1.jsonl": [market(A), market(B)], "results.reset1.jsonl": [result(B, "no"), result(A, "no")],
             "markets.reset2.jsonl.part": [market(C)]}                  # a half-copied file is not read
    for name, lines in extra.items():
        with open(os.path.join(folder, name), "w", encoding="utf-8") as fh:
            fh.writelines(json.dumps(x) + "\n" for x in lines)
    assert sorted(R.load_markets(folder)) == sorted([A, B])
    assert R.load_results(folder) == {A: "yes", B: "no"}                 # a ticker in two files: the first line wins
    rows = by_ticker(R.replay(folder))
    assert sorted(rows) == sorted([A, B])
    assert rows[A]["result"] == "yes" and rows[B]["result"] == "no"


def test_replay_in_parallel_by_hour_gives_the_same_rows(tmp_path):
    # three windows over two hour files; A's window closes exactly on the hour, so its close is read from the next
    # hour's file
    H = 3600
    f = Feed()
    for t, o, sid in ((C, T0, 1), (A, T0 + 2700, 3), (D, T0 + 2700, 7), (B, T0 + H, 5)):
        base(f, t, rt=o + 20, sid=sid)
        f.trade(o + 490, t, 0.94, 5, "no")
        f.delta(o + 880, t, "yes", 0.96, 1, sid=sid)
    f.gap(7)
    f.delta(T0 + H, D, "yes", 0.90, 1, sid=7)       # the next hour's first message says D's sid lost one
    folder = f.write(tmp_path, [market(C), market(A, T0 + 2700), market(D, T0 + 2700), market(B, T0 + H)],
                     [result(A, "yes")], until=T0 + H + 910)
    assert sorted(os.listdir(folder))[-2:] == ["ws-20261026T00.txt.gz", "ws-20261026T01.txt.gz"]
    one, s1 = R.replay_with_stats(folder)
    two, s2 = R.replay_with_stats(folder, workers=2)
    assert [r["ticker"] for r in one] == [C, A, D, B]
    assert two == one and s2["messages"] == s1["messages"] and s2["gaps"] == s1["gaps"] == 1
    assert s2["markets_listed"] == 4
    a, d = by_ticker(one)[A], by_ticker(one)[D]
    assert a["complete"] is True and a["orders"]["join"]["mid_close"] == approx(0.965)
    assert d["complete"] is False and d["orders"]["join"]["mid_close"] is None
    assert R.replay(folder, workers=2) == one


# ---------------------------------------------------------------- summarise

def order_out(L, filled, first=None, at=None, after=None):
    return {"L": L, "filled": filled, "first_fill_rt": first, "fills": [(first, filled)] if filled else [],
            "mid_at_fill": at, "mid_after": after or {5: None, 30: None, 60: None}, "mid_close": None}


def row_out(won, join, tick, cent, taker_price, hybrid, in_band=True, taker_after=None):
    taker = {"price": taker_price, "fee": R.taker_fee(15, taker_price)}
    if taker_after:
        taker.update(mid_at_fill=taker_after[0], mid_after=taker_after[1])
    return {"ticker": "T", "series": "S", "window_open": T0, "mark": MARK_T, "size": 15, "side": "yes",
            "bid": 0.95, "ask": taker_price, "spread": 0.02, "in_band": in_band,
            "result": None if won is None else ("yes" if won else "no"), "won": won, "mid_6": None, "mid_7": None,
            "orders": {"join": join, "tick": tick, "cent": cent} if in_band else None,
            "taker": taker if in_band else None, "hybrid": hybrid if in_band else None, "complete": True}


def hybrid_out(maker, taker, price, first):
    return {"maker_filled": maker, "taker_filled": taker, "taker_price": price,
            "fee": R.taker_fee(taker, price) if taker else 0.0, "first_fill_rt": first}


def sample_rows():
    r1 = row_out(True, order_out(0.95, 15, MARK_T + 10, 0.96, {5: 0.95, 30: 0.94, 60: 0.97}),
                 order_out(0.951, 0), None, 0.97, hybrid_out(15, 0, None, MARK_T + 10),
                 taker_after=(0.96, {5: 0.97, 30: None, 60: None}))
    r2 = row_out(False, order_out(0.95, 5, MARK_T + 30, 0.955, {5: 0.945, 30: None, 60: None}),
                 order_out(0.951, 15, MARK_T + 20), order_out(0.96, 15, MARK_T + 100), 0.97,
                 hybrid_out(5, 10, 0.96, MARK_T + 30))
    r3 = row_out(True, order_out(0.95, 0), None, None, 0.98, hybrid_out(0, 15, 0.97, MARK_T + 60))
    r4 = row_out(True, None, None, None, 0.91, None, in_band=False)          # out of band: left out
    r5 = row_out(None, order_out(0.95, 15, MARK_T + 1), None, None, 0.97,    # no result yet: left out
                 hybrid_out(15, 0, None, MARK_T + 1))
    return [r1, r2, r3, r4, r5]


def test_summarise_join():
    s = R.summarise(sample_rows())["join"]
    assert s["markets"] == 3
    assert s["any_fill"] == approx(2 / 3) and s["full_fill"] == approx(1 / 3)
    assert s["win_filled"] == approx(0.5) and s["win_unfilled"] == approx(1.0) and s["win_taker"] == approx(2 / 3)
    # makers pay no fee: cost 15 x 95c + 5 x 95c = $19; profit 15 x 5c - 5 x 95c = -$4
    assert s["cents_per_dollar"] == approx(-4 / 19 * 100)
    assert s["mid_move"] == {5: approx(-0.01), 30: approx(-0.02), 60: approx(0.01)}
    assert s["median_wait"] == approx(20)
    assert s["contracts"] == approx(20) and s["avg_price"] == approx(0.95)


def test_summarise_tick_and_cent_count_unplaced_orders_as_unfilled():
    s = R.summarise(sample_rows())
    t, c = s["tick"], s["cent"]
    assert t["markets"] == 3 and t["placed"] == 2 and c["placed"] == 1
    assert t["any_fill"] == approx(1 / 3) and t["full_fill"] == approx(1 / 3)
    assert t["win_filled"] == approx(0.0) and t["win_unfilled"] == approx(1.0)
    assert t["cents_per_dollar"] == approx(-100) and t["median_wait"] == approx(20)
    assert c["any_fill"] == approx(1 / 3) and c["median_wait"] == approx(100)
    assert t["mid_move"] == {5: None, 30: None, 60: None}


def test_summarise_taker_pays_the_fee():
    s = R.summarise(sample_rows())["taker"]
    fees = 2 * R.taker_fee(15, 0.97) + R.taker_fee(15, 0.98)
    profit = 15 * 0.03 - 15 * 0.97 + 15 * 0.02 - fees
    cost = 15 * 0.97 * 2 + 15 * 0.98
    assert s["markets"] == 3 and s["any_fill"] == 1 and s["full_fill"] == 1
    assert s["win_filled"] == approx(2 / 3) and s["win_unfilled"] is None and s["win_taker"] == approx(2 / 3)
    assert s["cents_per_dollar"] == approx(profit / cost * 100)
    assert s["mid_move"] == {5: approx(0.01), 30: None, 60: None}
    assert s["median_wait"] == 0


def test_summarise_hybrid_pays_the_fee_only_on_its_taker_part():
    s = R.summarise(sample_rows())["hybrid"]
    cost = 15 * 0.95 + (5 * 0.95 + 10 * 0.96) + 15 * 0.97
    profit = 15 * 0.05 + (-5 * 0.95 - 10 * 0.96 - R.taker_fee(10, 0.96)) + (15 * 0.03 - R.taker_fee(15, 0.97))
    assert s["markets"] == 3 and s["any_fill"] == approx(1) and s["full_fill"] == approx(1)
    assert s["win_filled"] == approx(2 / 3) and s["win_unfilled"] is None
    assert s["cents_per_dollar"] == approx(profit / cost * 100)
    assert s["median_wait"] == approx(30) and s["mid_move"] == {5: None, 30: None, 60: None}


def test_summarise_with_nothing_to_divide_gives_none():
    s = R.summarise([])
    for kind in ("join", "tick", "cent", "hybrid", "taker"):
        k = s[kind]
        assert k["markets"] == 0
        for field in ("any_fill", "full_fill", "win_filled", "win_unfilled", "win_taker", "cents_per_dollar",
                      "median_wait"):
            assert k[field] is None, (kind, field)
        assert k["mid_move"] == {5: None, 30: None, 60: None}
    rows = [row_out(True, order_out(0.95, 0), None, None, 0.97, hybrid_out(0, 15, 0.97, MARK_T + 60))]
    j = R.summarise(rows)["join"]
    assert j["any_fill"] == 0 and j["win_filled"] is None and j["cents_per_dollar"] is None
    assert j["median_wait"] is None and j["win_unfilled"] == 1


# ---------------------------------------------------------------- the report command

def test_report_writes_json_and_prints_plain_words(tmp_path, capsys):
    f = Feed()
    base(f)
    f.trade(T0 + 490, A, 0.94, 5, "no")
    folder = f.write(tmp_path, [market(A, raw=RANGES)], [result(A, "yes")])
    out = tmp_path / "out" / "r.json"
    assert R.main(["report", "--data", folder, "--out", str(out)]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["rows"][0]["ticker"] == A and data["rows"][0]["orders"]["join"]["filled"] == 5
    assert data["summary"]["join"]["markets"] == 1
    text = capsys.readouterr().out
    assert "fill share (how often the waiting order got any contracts)" in text
    assert "cents of profit for every dollar bet" in text
    assert R.main(["report", "--data", folder]) == 0                  # default: report.json in the data folder
    assert os.path.exists(os.path.join(folder, "report.json"))


def test_report_on_an_empty_folder_still_prints(tmp_path, capsys):
    assert R.main(["report", "--data", str(tmp_path), "--out", str(tmp_path / "r.json")]) == 0
    assert "no market" in capsys.readouterr().out.lower()
