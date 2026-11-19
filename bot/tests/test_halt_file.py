"""The halt file when it isn't whole: cut off by a crash mid-write, emptied, garbled, or not the shape the bot writes.
halt.json is only ever written for a halt, so any halt.json counts as one, and a halt being written is never left
half done. Before this, an unreadable file raised an error, which stops a live bot, and stopped it again on every
restart until someone deleted the file.

    python -m pytest tests/test_halt_file.py -q
"""
import json
import os

import pytest

from kalshi_bot import bot
from test_bot import ENTRY, W, FakeKalshi, decisions
from test_flow import BTC, YES96, bot_for, mk

UNREADABLE = "halt.json couldn't be read, so it counts as a halt"


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setattr(bot, "STATE", str(tmp_path))
    bot._since.clear()
    return tmp_path


def write(state, raw, mtime=W):
    p = state / "halt.json"
    p.write_bytes(raw)
    os.utime(p, (mtime, mtime))
    return p


@pytest.mark.parametrize("raw", [
    b"",                                                        # created, then the process died before writing
    b'{"ts": "2026-10-10T18:00:00Z", "reas',                    # cut off mid-write
    b"\xff\xfe not text",                                       # garbled
    b"null", b"[]", b'"halted"', b"7",                          # JSON, but not a halt
    b'{"ts": "2026-10-10T18:00:00Z"}',                          # missing its reason
    b'{"ts": "2026-10-10T18:00:00Z", "reason": 5, "by": "you"}',
])
def test_an_unreadable_halt_file_is_still_a_halt(state, raw):
    write(state, raw)
    assert bot.halt_info() == {"ts": bot.iso(W), "reason": UNREADABLE, "by": "unknown"}   # dated by the file's last change


def test_a_whole_halt_file_reads_as_written(state):
    h = {"ts": "2026-10-10T18:00:00Z", "reason": "testing", "by": "you"}
    write(state, json.dumps(h).encode())
    assert bot.halt_info() == h


def test_a_file_it_isnt_allowed_to_open_is_still_a_halt(state, monkeypatch):
    """Another program holding it (antivirus mid-scan): it exists, so a halt was meant."""
    write(state, b"{}")
    real_open = open

    def held(path, *a, **k):
        if str(path).endswith("halt.json"):
            raise PermissionError(13, "in use")
        return real_open(path, *a, **k)

    with monkeypatch.context() as m:
        m.setattr("builtins.open", held)
        h = bot.halt_info()
    assert (h["reason"], h["by"]) == (UNREADABLE, "unknown") and bot.ts(h["ts"]) > W   # dated now: its age can't be read


def test_the_bot_obeys_an_unreadable_halt_instead_of_crashing(state):
    write(state, b"")
    db = bot.connect(str(state / "live-prod.db"))
    bot.set_meta(db, "start", 100.0)
    fake = FakeKalshi()
    bot_for(fake, db, True).decide_window(ENTRY, W, [mk(BTC, YES96)])
    assert decisions(db)[BTC] == ("halted", f"halted: {UNREADABLE}") and fake.orders == []


def test_resume_clears_an_unreadable_halt(state):
    write(state, b'{"ts": "2026-')
    assert bot.clear_halt(ENTRY, [])["reason"] == UNREADABLE
    assert not (state / "halt.json").exists() and bot.halt_info() is None


def test_a_new_halt_never_replaces_an_unreadable_one(state):
    p = write(state, b"")
    bot.set_halt(ENTRY, "8 bets lost in one window")
    assert p.read_bytes() == b"" and bot.halt_info()["reason"] == UNREADABLE


def test_a_halt_cut_off_mid_write_leaves_no_half_file(state, monkeypatch):
    """The process dies while writing: the halt file is either whole or not there, never half written."""
    def dies(obj, fh, **k):
        fh.write('{"ts": "2026-')
        raise KeyboardInterrupt

    monkeypatch.setattr(bot.json, "dump", dies)
    with pytest.raises(KeyboardInterrupt):
        bot.set_halt(ENTRY, "testing")
    assert not (state / "halt.json").exists()


def test_a_halt_is_written_whole_and_leaves_nothing_beside_it(state):
    bot.set_halt(ENTRY, "testing", "you")
    assert sorted(os.listdir(state)) == ["halt.json"]
    assert json.loads((state / "halt.json").read_text(encoding="utf-8")) == {"ts": bot.iso(ENTRY), "reason": "testing", "by": "you"}


def test_a_leftover_from_a_halt_cut_off_mid_write_doesnt_block_the_next(state):
    (state / "halt.json.tmp").write_text('{"ts": "2026-', encoding="utf-8")
    bot.set_halt(ENTRY, "testing", "you")
    assert bot.halt_info()["reason"] == "testing" and sorted(os.listdir(state)) == ["halt.json"]
