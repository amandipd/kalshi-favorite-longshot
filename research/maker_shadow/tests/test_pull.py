"""Tests for pull.py, the laptop's hourly copy of the recorder's closed hour files.

No test starts a process or touches the network: pull.py runs ssh and scp through one injected
run(args, timeout) -> (returncode, output), and FakeServer below plays the server's side of it, with a dict of the
server's data folder (file name -> bytes). Every command is recorded, so the tests can check what would have run.

    python -m pytest research/maker_shadow/tests/test_pull.py -q
"""
import base64
import calendar
import fnmatch
import hashlib
import json
import os
import re
import shlex
import shutil

import pytest

import pull

REMOTE = "/home/kalshi/kalshi/maker-shadow/data"
HOST = "kalshi@recorder-host"
KEY = r"C:\keys\test-key.pem"
NOW = 1793000000                       # the server's clock in the fake (2026-10-26 07:33:20 UTC)
SSH = r"C:\Windows\System32\OpenSSH\ssh.exe"
SCP = r"C:\Windows\System32\OpenSSH\scp.exe"
SMALL = ("markets.jsonl", "results.jsonl", "events.jsonl", "status.json")
LOGS = ("markets.jsonl", "results.jsonl", "events.jsonl")     # the recorder only appends to these
LOW = ["nice", "-n", "19", "ionice", "-c3"]                     # lowest CPU and disk priority

T09 = "ws-20261025T09.txt.gz"
T10 = "ws-20261025T10.txt.gz"
T11 = "ws-20261025T11.txt.gz"
T12 = "ws-20261025T12.txt.gz"
T12_1 = "ws-20261025T12.1.txt.gz"
GOOD = re.compile(r"^ws-\d{8}T\d{2}(\.\d+)?\.txt\.gz$")
RM_FORM = re.compile(r"^rm -- " + re.escape(REMOTE) + r"/(ws-\d{8}T\d{2}(\.\d+)?\.txt\.gz)$")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def body(name, n=2000):
    return (name + " ").encode() * n


class FakeServer:
    """The server's side of ssh and scp. `files` is the data folder; `ages` is seconds since each file changed."""

    def __init__(self, files=None, status=None, ages=None, local=None, now=NOW):
        self.files = dict(files or {})
        if status is not None:
            self.files["status.json"] = status if isinstance(status, bytes) else json.dumps(status).encode()
        self.ages = dict(ages or {})
        self.now = now
        self.local = local                 # the laptop's folder, so rm can check what the laptop held at that moment
        self.calls = []                    # every args list run
        self.events = []                   # ("scp", name, dest) / ("rm", name) / ("cat", name) / ("list",)
        self.at_rm = {}                    # name -> (final file's bytes or None, .part exists) when rm arrived
        self.down = False                  # ssh can't connect (255)
        self.scp_fail = set()              # these names fail mid-copy (a partial .part is left)
        self.corrupt = set()               # these names arrive with one byte changed
        self.rm_fail = set()
        self.short_tail = set()            # these logs' new bytes arrive one byte short
        self.boom = False                  # raise from run(), like a bug
        self.clock = None                  # a Clock: each command then takes clock.step seconds of it
        self.started = []                  # (clock time, args) for each command, when there is a clock

    # -- run(args, timeout) -------------------------------------------------------------------------------------
    def __call__(self, args, timeout):
        assert isinstance(timeout, (int, float)) and timeout > 0
        self.calls.append(list(args))
        if self.clock is not None:
            self.started.append((self.clock.t, list(args)))
            self.clock.t += self.clock.step
        if self.boom:
            raise RuntimeError("boom")
        if self.down:
            return 255, "ssh: connect to host recorder-host port 22: Connection timed out\r\n"
        exe = os.path.basename(args[0]).lower()
        if exe == "ssh.exe":
            assert args[-2] == HOST
            return self.ssh(args[-1])
        if exe == "scp.exe":
            return self.scp(args[-2], args[-1])
        raise AssertionError(f"unexpected program {args[0]}")

    def name_of(self, path):
        assert path.startswith(REMOTE + "/"), path
        name = path[len(REMOTE) + 1:]
        assert "/" not in name, path
        return name

    def ssh(self, cmd):
        words = shlex.split(cmd)
        if words[:2] == ["cat", "--"] and len(words) == 3:
            name = self.name_of(words[2])
            self.events.append(("cat", name))
            if name not in self.files:
                return 1, f"cat: {words[2]}: No such file or directory\n"
            return 0, self.files[name].decode("utf-8", "replace")
        if words[:1] == ["rm"]:
            assert words[1] == "--" and len(words) == 3, cmd
            name = self.name_of(words[2])
            self.events.append(("rm", name))
            if self.local is not None:
                final = os.path.join(self.local, name)
                held = open(final, "rb").read() if os.path.exists(final) else None
                self.at_rm[name] = (held, os.path.exists(final + ".part"))
            if name in self.rm_fail or name not in self.files:
                return 1, f"rm: cannot remove '{words[2]}': Permission denied\n"
            del self.files[name]
            return 0, ""
        if words[:3] == ["cd", REMOTE, "&&"] and "stat" in words:
            return self.prefix(words[3:])
        if words[:3] == ["cd", REMOTE, "&&"] and "tail" in words:
            return self.tail(words[3:])
        if "sha256sum" in cmd:
            assert words[:3] == ["cd", REMOTE, "&&"], cmd
            names = [w[2:] if w.startswith("./") else w for w in words[words.index("--") + 1:]]
            self.events.append(("hash", tuple(names)))
            return 0, "".join(f"{sha(self.files[n])}  ./{n}\n" for n in names if n in self.files)
        if "find" in words and "date" in words:
            assert words[:3] == ["cd", REMOTE, "&&"], cmd
            self.events.append(("list",))
            return 0, self.listing()
        raise AssertionError(f"unexpected remote command {cmd!r}")

    def listing(self):
        """What `date +%s` and `find -printf '%s %T@ %f\\n'` print for the data folder (no hashes: those are asked
        for separately, a few files at a time)."""
        names = sorted(n for n in self.files if fnmatch.fnmatchcase(n, "ws-*.txt.gz"))
        lines = [str(self.now)]
        for n in names:
            lines.append(f"{len(self.files[n])} {self.now - self.ages.get(n, 3600)}.1234567890 {n}")
        return "\n".join(lines) + "\n"

    def prefix(self, rest):
        """`stat -c %s -- <log> && <LOW> head -c <L> -- <log> | <LOW> sha256sum`: the log's size, then the SHA-256
        of its first L bytes, as stat and sha256sum print them."""
        name, length = rest[4], rest[13]
        assert rest == ["stat", "-c", "%s", "--", name, "&&", *LOW, "head", "-c", length, "--", name, "|", *LOW,
                        "sha256sum"], rest
        assert name in LOGS and length.isdigit(), rest
        self.events.append(("prefix", name, int(length)))
        if name not in self.files:
            return 1, f"stat: cannot statx '{name}': No such file or directory\n"
        data = self.files[name]
        return 0, f"{len(data)}\n{sha(data[:int(length)])}  -\n"

    def tail(self, rest):
        """`<LOW> tail -c +<K> -- <log> | head -c <N> | base64`: N bytes from byte K (1-based), in base64 lines."""
        name, start, count = rest[9], rest[7], rest[13]
        assert rest == [*LOW, "tail", "-c", start, "--", name, "|", "head", "-c", count, "|", "base64"], rest
        assert name in LOGS and start[:1] == "+" and start[1:].isdigit() and count.isdigit(), rest
        k, n = int(start[1:]), int(count)
        self.events.append(("tail", name, k, n))
        data = self.files.get(name, b"")[k - 1:k - 1 + n]
        if name in self.short_tail:
            data = data[:-1]
        return 0, base64.encodebytes(data).decode()             # wrapped at 76 characters, as GNU base64 does

    def hashed(self):
        return [n for e in self.events if e[0] == "hash" for n in e[1]]

    def hash_calls(self):
        return [e[1] for e in self.events if e[0] == "hash"]

    def tails(self):
        return [e[1:] for e in self.events if e[0] == "tail"]

    def scp(self, src, dest):
        host, path = src.split(":", 1)
        assert host == HOST
        name = self.name_of(path)
        self.events.append(("scp", name, dest))
        if name not in self.files:
            return 1, f"scp: {path}: No such file or directory\n"
        data = self.files[name]
        if name in self.scp_fail:
            with open(dest, "wb") as f:
                f.write(data[: len(data) // 2])
            return 1, "client_loop: send disconnect: Connection reset\n"
        if name in self.corrupt:
            data = data[:-1] + bytes([data[-1] ^ 1])
        with open(dest, "wb") as f:
            f.write(data)
        return 0, ""

    # -- what happened ------------------------------------------------------------------------------------------
    def scps(self):
        return [e[1] for e in self.events if e[0] == "scp"]

    def rms(self):
        return [e[1] for e in self.events if e[0] == "rm"]


QUIET_TIME = 1793000000.0 - 1793000000.0 % 900 + 200    # 200 s into a window: clear of the bot's busy minutes


def no_sleep(seconds):
    raise AssertionError(f"slept {seconds} s outside the bot's busy minutes")


def make(tmp_path, server, **kw):
    local = str(tmp_path / "data")
    server.local = local
    kw.setdefault("clock", lambda: QUIET_TIME)
    kw.setdefault("sleep", no_sleep)
    return pull.Pull(host=HOST, key=KEY, remote=REMOTE, local=local, run=server, **kw), local


class Clock:
    """The laptop's clock over a run: every server command takes `step` seconds (FakeServer moves it on when given
    this clock), and sleep() moves it on by what was asked."""

    def __init__(self, start, step):
        self.t, self.step, self.slept = float(start), step, []

    def __call__(self):
        return self.t

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.t += seconds


def in_busy(t):
    return pull.BUSY[0] <= t % pull.WINDOW < pull.BUSY[1]


def reads_server_files(args):
    """True for a command that reads a file's contents on the server: any scp, and any ssh that hashes or reads
    bytes (sha256sum, head, tail). The status cat, the listing and rm don't."""
    if os.path.basename(args[0]).lower() == "scp.exe":
        return True
    return bool({"sha256sum", "head", "tail"} & set(shlex.split(args[-1])))


def hour_of(stamp):
    """Epoch seconds for "YYYYMMDDTHH" UTC."""
    return calendar.timegm((int(stamp[:4]), int(stamp[4:6]), int(stamp[6:8]), int(stamp[9:11]), 0, 0))


def log_text(local):
    path = os.path.join(local, "pull.log")
    return open(path, encoding="utf-8").read() if os.path.exists(path) else ""


def read(path):
    with open(path, "rb") as f:
        return f.read()


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def three_files():
    return {T10: body(T10), T11: body(T11), T12: body(T12)}


# ---------------------------------------------------------------------------------------------------------------
# names and order


def test_name_pattern():
    for good in (T10, T12_1, "ws-20261025T12.10.txt.gz"):
        assert pull.NAME_RE.fullmatch(good)
    for bad in ("ws-2026102T10.txt.gz", "ws-20261025T1.txt.gz", "ws-20261025T10.txt.gz.part",
                "ws-20261025T10.txt", "xws-20261025T10.txt.gz", "ws-20261025T10..txt.gz", "ws-20261025T10.a.txt.gz",
                "ws-20261025T10 copy.txt.gz", "../ws-20261025T10.txt.gz", "ws-20261025T10.txt.gz\n", "markets.jsonl",
                "ws-20261025T10.txt.gz;rm -rf ~"):
        assert not pull.NAME_RE.fullmatch(bad), bad


def test_hour_order_is_by_hour_then_suffix():
    names = ["ws-20261026T00.txt.gz", "ws-20261025T12.10.txt.gz", T12, "ws-20261025T12.2.txt.gz", T12_1, T09]
    assert sorted(names, key=pull.hour_key) == [T09, T12, T12_1, "ws-20261025T12.2.txt.gz",
                                                 "ws-20261025T12.10.txt.gz", "ws-20261026T00.txt.gz"]


def test_parse_listing_reads_the_real_format_and_ignores_junk():
    a, b = "a" * 64, "b" * 64
    out = ("1793000000\n"
           f"12345 1792996400.1234567890 {T10}\n"
           f"77 1792999990.0000000000 {T11}\n"
           f"9 1792996400.0 ws-20261025T10 copy.txt.gz\n"
           f"{a}  ./{T10}\n"
           f"{b}  ./{T11}\n"
           f"{'c' * 64}  ./ws-20261025T10 copy.txt.gz\n"
           f"\\{'d' * 64}  ./ws-20261025T13.txt.gz\\n\n"
           "garbage line\n")
    now, files = pull.parse_listing(out)
    assert now == 1793000000
    assert files == {T10: (12345, 1792996400.123456789, a), T11: (77, 1792999990.0, b)}


def test_parse_listing_takes_sha256sums_binary_mode_marker_too():
    # GNU sha256sum marks binary mode with "*" instead of the second space (Git Bash does; most Linux builds print two spaces)
    out = f"1793000000\n5000 1792975738.8465101000 {T10}\n{'e' * 64} *./{T10}\n"
    assert pull.parse_listing(out)[1] == {T10: (5000, 1792975738.8465101, "e" * 64)}


def test_parse_listing_without_a_clock_line_is_unreadable():
    assert pull.parse_listing(f"12345 1792996400.1 {T10}\n{'a' * 64}  ./{T10}\n")[0] is None


# ---------------------------------------------------------------------------------------------------------------
# the lock


def test_live_lock_exits_at_once(tmp_path):
    server = FakeServer(three_files(), {"writing": None})
    p, local = make(tmp_path, server, pid_alive=lambda pid: True)
    write(os.path.join(local, "pull.lock"), b"4242\n")
    assert p.once() == 0
    assert server.calls == []
    assert read(os.path.join(local, "pull.lock")) == b"4242\n"
    assert "4242" in log_text(local)


def test_stale_lock_by_age_is_taken_over(tmp_path):
    server = FakeServer(three_files(), {"writing": T12})
    p, local = make(tmp_path, server, pid_alive=lambda pid: True, now=lambda: 1793000000.0)
    lock = os.path.join(local, "pull.lock")
    write(lock, b"4242\n")
    os.utime(lock, (1793000000 - 7 * 3600, 1793000000 - 7 * 3600))
    assert p.once() == 0
    assert server.calls
    assert not os.path.exists(lock)


def test_lock_just_under_six_hours_old_is_still_live(tmp_path):
    server = FakeServer(three_files(), {"writing": T12})
    p, local = make(tmp_path, server, pid_alive=lambda pid: True, now=lambda: 1793000000.0)
    lock = os.path.join(local, "pull.lock")
    write(lock, b"4242\n")
    os.utime(lock, (1793000000 - 5.9 * 3600, 1793000000 - 5.9 * 3600))
    assert p.once() == 0
    assert server.calls == []


def test_stale_lock_by_dead_pid_is_taken_over(tmp_path):
    server = FakeServer(three_files(), {"writing": T12})
    seen = []
    p, local = make(tmp_path, server, pid_alive=lambda pid: seen.append(pid) or False)
    lock = os.path.join(local, "pull.lock")
    write(lock, b"4242\n")
    assert p.once() == 0
    assert 4242 in seen
    assert server.calls
    assert not os.path.exists(lock)


def test_lock_holds_our_pid_while_running(tmp_path):
    server = FakeServer(three_files(), {"writing": T12})
    p, local = make(tmp_path, server)
    held = []
    real = server.ssh
    server.ssh = lambda cmd: (held.append(read(os.path.join(local, "pull.lock"))), real(cmd))[1]
    assert p.once() == 0
    assert held and all(h.split()[0] == str(os.getpid()).encode() for h in held)


def test_lock_released_after_a_crash(tmp_path):
    server = FakeServer(three_files(), {"writing": T12})
    server.boom = True
    p, local = make(tmp_path, server)
    assert p.once() == 1
    assert not os.path.exists(os.path.join(local, "pull.lock"))
    assert "boom" in log_text(local)


def test_pid_alive_sees_this_process_without_os_kill(monkeypatch):
    if os.name == "nt":                     # os.kill(pid, 0) on Windows terminates the process
        monkeypatch.setattr(os, "kill", lambda *a: pytest.fail("os.kill called on Windows"))
    assert pull.pid_alive(os.getpid()) is True
    assert pull.pid_alive(2 ** 31 - 4) is False
    assert pull.pid_alive(0) is False


# ---------------------------------------------------------------------------------------------------------------
# which files are copied


def test_writing_file_from_status_is_skipped(tmp_path):
    server = FakeServer(three_files(), {"writing": T12, "rt": 1.0})
    p, local = make(tmp_path, server)
    assert p.once() == 0
    assert set(n for n in server.scps() if n.startswith("ws-")) == {T10, T11}
    assert sorted(server.rms()) == [T10, T11]
    assert T12 in server.files
    assert read(os.path.join(local, T10)) == body(T10)
    assert not os.path.exists(os.path.join(local, T12))


def test_status_unreadable_skips_the_newest_file(tmp_path):
    files = three_files()
    files[T12_1] = body(T12_1)
    server = FakeServer(files)                                   # no status.json on the server
    p, local = make(tmp_path, server)
    assert p.once() == 0
    assert set(n for n in server.scps() if n.startswith("ws-")) == {T10, T11, T12}
    assert T12_1 in server.files and T12_1 not in server.rms()
    assert "status.json" in log_text(local)


@pytest.mark.parametrize("status", [b"{not json", b"[1, 2]", json.dumps({"rt": 1}).encode(),
                                    json.dumps({"writing": 5}).encode()])
def test_status_without_a_usable_writing_skips_the_newest_file(tmp_path, status):
    server = FakeServer(three_files(), status)
    p, local = make(tmp_path, server)
    assert p.once() == 0
    assert set(n for n in server.scps() if n.startswith("ws-")) == {T10, T11}
    assert T12 in server.files


def test_writing_none_copies_every_closed_file(tmp_path):
    server = FakeServer(three_files(), {"writing": None, "paused": True})
    p, local = make(tmp_path, server)
    assert p.once() == 0
    assert sorted(server.rms()) == [T10, T11, T12]


def test_recently_changed_file_is_skipped_even_if_status_says_closed(tmp_path):
    # status.json is rewritten only every 30 s: right after a restart it can still name the old file
    files = three_files()
    files[T12_1] = body(T12_1)
    server = FakeServer(files, {"writing": T12}, ages={T12_1: 10})
    p, local = make(tmp_path, server)
    assert p.once() == 0
    assert T12_1 not in server.scps() and T12_1 not in server.rms()
    assert sorted(server.rms()) == [T10, T11]


def test_a_file_named_for_the_servers_current_hour_is_never_touched(tmp_path):
    # the recorder is paused and its file of this hour closed long ago, but it could still open another file of this
    # hour (a free name), so nothing named for this hour (or later) is hashed, copied or deleted until the hour is over
    T10_1, T25 = "ws-20261025T10.1.txt.gz", "ws-20261025T25.txt.gz"            # T25: no real hour
    files = {n: body(n) for n in (T09, T10, T10_1, T11, T25)}
    server = FakeServer(files, {"writing": None, "paused": True}, ages={T10: 1500, T10_1: 600, T11: 900},
                        now=hour_of("20261025T10") + 1800)                       # 10:30 UTC on the server
    p, local = make(tmp_path, server)
    assert p.once() == 0
    assert server.hashed() == [T09]
    assert [n for n in server.scps() if n.startswith("ws-")] == [T09] and server.rms() == [T09]
    for n in (T10, T10_1, T11, T25):
        assert n in server.files and not os.path.exists(os.path.join(local, n))
        assert f"skipped {n}" in log_text(local)
    assert "current hour" in log_text(local)


def test_at_the_hour_the_last_hours_file_still_waits_for_the_age_rule(tmp_path):
    ten = hour_of("20261025T10")
    server = FakeServer({T09: body(T09), T10: body(T10)}, {"writing": T10}, ages={T09: 20, T10: 5}, now=ten + 20)
    p, local = make(tmp_path, server)
    assert p.once() == 0                                                         # 10:00:20: T09 closed 20 s ago
    assert server.hashed() == [] and server.rms() == []
    assert f"skipped {T09}: changed 20 s ago" in log_text(local)
    server.now, server.ages = ten + 50, {T09: 50, T10: 2}
    p2, _ = make(tmp_path, server)
    assert p2.once() == 0                                                        # 10:00:50: now it may go
    assert server.hashed() == [T09] and server.rms() == [T09]
    assert T10 in server.files


def test_files_are_copied_oldest_first(tmp_path):
    files = {n: body(n) for n in ("ws-20261026T00.txt.gz", T12_1, T09, T12)}
    server = FakeServer(files, {"writing": None})
    p, local = make(tmp_path, server)
    assert p.once() == 0
    hours = [n for n in server.scps() if n.startswith("ws-")]
    assert hours == [T09, T12, T12_1, "ws-20261026T00.txt.gz"]


def test_names_off_the_pattern_are_ignored_and_never_removed(tmp_path):
    odd = ["ws-20261025T10 copy.txt.gz", "ws-2026102T10.txt.gz", "ws-20261025T10.bak.txt.gz",
           "ws-x.txt.gz", "notes.txt", "ws-20261025T10.txt.gz.part", "recorder.log"]
    files = three_files()
    files.update({n: b"keep me" for n in odd})
    server = FakeServer(files, {"writing": T12})
    p, local = make(tmp_path, server)
    assert p.once() == 0
    for n in odd:
        assert n in server.files
        assert n not in server.scps()
        assert n not in server.rms()
    assert sorted(server.rms()) == [T10, T11]


# ---------------------------------------------------------------------------------------------------------------
# copying and deleting


def test_fresh_copy_goes_through_part_then_rename_then_rm(tmp_path):
    server = FakeServer({T10: body(T10), T11: body(T11)}, {"writing": T11})
    p, local = make(tmp_path, server)
    assert p.once() == 0
    scp = [e for e in server.events if e[0] == "scp" and e[1] == T10]
    assert len(scp) == 1 and scp[0][2] == os.path.join(local, T10 + ".part")
    order = [e[:2] for e in server.events if e[1:2] == (T10,)]
    assert order == [("scp", T10), ("rm", T10)]
    held, part_left = server.at_rm[T10]
    assert held == body(T10) and not part_left               # renamed and complete before the rm went out
    assert read(os.path.join(local, T10)) == body(T10)
    assert not os.path.exists(os.path.join(local, T10 + ".part"))
    assert T10 not in server.files and T11 in server.files


def test_already_present_identical_file_is_removed_on_server_only(tmp_path):
    server = FakeServer({T10: body(T10), T11: body(T11)}, {"writing": T11})
    p, local = make(tmp_path, server)
    final = os.path.join(local, T10)
    write(final, body(T10))
    os.utime(final, (1700000000, 1700000000))
    assert p.once() == 0
    assert T10 not in server.scps()
    assert server.rms() == [T10]
    assert read(final) == body(T10)
    assert os.path.getmtime(final) == 1700000000


def test_failed_rm_keeps_the_server_copy_and_is_retried_next_run(tmp_path):
    server = FakeServer({T10: body(T10), T11: body(T11)}, {"writing": T11})
    server.rm_fail = {T10}
    p, local = make(tmp_path, server)
    assert p.once() == 0
    assert T10 in server.files and read(os.path.join(local, T10)) == body(T10)
    assert "rm" in log_text(local) or "delete" in log_text(local)
    server.rm_fail = set()
    p2, _ = make(tmp_path, server)
    assert p2.once() == 0
    assert T10 not in server.files
    assert server.scps().count(T10) == 1                     # not copied again


def test_hash_mismatch_removes_part_keeps_server_and_logs(tmp_path):
    server = FakeServer(three_files(), {"writing": T12})
    server.corrupt = {T10}
    p, local = make(tmp_path, server)
    assert p.once() == 0
    assert T10 in server.files and T10 not in server.rms()
    assert not os.path.exists(os.path.join(local, T10))
    assert not os.path.exists(os.path.join(local, T10 + ".part"))
    assert "mismatch" in log_text(local) and T10 in log_text(local)
    assert server.rms() == [T11]                              # and it moved on


def test_failed_copy_removes_part_keeps_server_and_logs(tmp_path):
    server = FakeServer(three_files(), {"writing": T12})
    server.scp_fail = {T10}
    p, local = make(tmp_path, server)
    assert p.once() == 0
    assert T10 in server.files and T10 not in server.rms()
    assert not os.path.exists(os.path.join(local, T10 + ".part"))
    assert not os.path.exists(os.path.join(local, T10))
    assert T10 in log_text(local)
    assert server.rms() == [T11]


def test_gives_up_after_three_failed_copies_in_a_row(tmp_path):
    files = {n: body(n) for n in (T09, T10, T11, T12, T12_1)}
    server = FakeServer(files, {"writing": None})
    server.scp_fail = set(files)
    p, local = make(tmp_path, server)
    assert p.once() == 0
    assert len(server.scps()) == 3
    assert server.rms() == []
    assert all(n in server.files for n in files)


def test_different_local_file_of_same_name_goes_to_dup(tmp_path):
    server = FakeServer({T10: body(T10), T11: body(T11)}, {"writing": T11})
    p, local = make(tmp_path, server)
    write(os.path.join(local, T10), b"an older, different T10")
    write(os.path.join(local, T10 + ".dup1"), b"another different T10")
    assert p.once() == 0
    assert read(os.path.join(local, T10)) == b"an older, different T10"
    assert read(os.path.join(local, T10 + ".dup1")) == b"another different T10"
    assert read(os.path.join(local, T10 + ".dup2")) == body(T10)
    assert T10 in server.files and T10 not in server.rms()
    assert "dup2" in log_text(local)


def test_dup_is_not_copied_again_next_run(tmp_path):
    server = FakeServer({T10: body(T10), T11: body(T11)}, {"writing": T11})
    p, local = make(tmp_path, server)
    write(os.path.join(local, T10), b"an older, different T10")
    assert p.once() == 0
    assert server.scps().count(T10) == 1
    p2, _ = make(tmp_path, server)
    assert p2.once() == 0
    assert server.scps().count(T10) == 1
    assert not os.path.exists(os.path.join(local, T10 + ".dup2"))
    assert T10 in server.files


def test_low_laptop_space_skips_copies_but_still_clears_verified_files(tmp_path):
    server = FakeServer({T10: body(T10), T11: body(T11), T12: body(T12)}, {"writing": T12})
    p, local = make(tmp_path, server, free_bytes=lambda path: 5 * 10 ** 9)
    write(os.path.join(local, T10), body(T10))
    assert p.once() == 0
    assert T11 not in server.scps()
    assert server.rms() == [T10]
    assert T11 in server.files
    assert "space" in log_text(local)


# ---------------------------------------------------------------------------------------------------------------
# the four small files


def test_small_files_come_whole_once_then_only_their_new_bytes_and_are_never_removed(tmp_path):
    files = {T10: body(T10), "markets.jsonl": b'{"ticker": "A"}\n', "results.jsonl": b'{"ticker": "A"}\n',
             "events.jsonl": b'{"event": "start"}\n'}
    server = FakeServer(files, {"writing": None, "messages": 1})
    p, local = make(tmp_path, server)
    assert p.once() == 0
    for name in SMALL:
        assert read(os.path.join(local, name)) == server.files[name]
        assert not os.path.exists(os.path.join(local, name + ".part"))
        assert name in server.files
        assert server.scps().count(name) == 1                    # nothing on the laptop yet: the whole file
    server.files["markets.jsonl"] += b'{"ticker": "B"}\n'
    server.files["events.jsonl"] += b'{"event": "drop"}\n{"event": "connect"}\n'
    server.files["status.json"] = json.dumps({"writing": None, "messages": 2}).encode()
    p2, _ = make(tmp_path, server)
    assert p2.once() == 0
    for name in SMALL:
        assert read(os.path.join(local, name)) == server.files[name]
        assert name in server.files
    for name in LOGS:
        assert server.scps().count(name) == 1                    # never copied whole again
    assert server.scps().count("status.json") == 2               # a snapshot: copied whole every run
    assert server.tails() == [("markets.jsonl", len(b'{"ticker": "A"}\n') + 1, len(b'{"ticker": "B"}\n')),
                              ("events.jsonl", len(b'{"event": "start"}\n') + 1,
                               len(b'{"event": "drop"}\n{"event": "connect"}\n'))]   # results.jsonl: nothing new
    small_scps = [e for e in server.events if e[0] == "scp" and e[1] in SMALL]
    assert all(e[2] == os.path.join(local, e[1] + ".part") for e in small_scps)
    assert not any(n in SMALL for n in server.rms())
    assert not [n for n in os.listdir(local) if n.endswith(".part")]


def test_log_check_asks_for_the_laptops_length_at_lowest_priority(tmp_path):
    # the fake checks the command's exact form: stat, then head -c <laptop length> | sha256sum, both niced
    server = FakeServer({"markets.jsonl": b"one\ntwo\n"}, {"writing": None})
    p, local = make(tmp_path, server)
    write(os.path.join(local, "markets.jsonl"), b"one\n")
    assert p.once() == 0
    assert ("prefix", "markets.jsonl", 4) in server.events
    assert server.tails() == [("markets.jsonl", 5, 4)]
    assert read(os.path.join(local, "markets.jsonl")) == b"one\ntwo\n"
    assert "markets.jsonl" not in server.scps()


def test_unchanged_log_is_checked_but_nothing_is_copied(tmp_path):
    server = FakeServer({"markets.jsonl": b"one\n"}, {"writing": None})
    p, local = make(tmp_path, server)
    final = os.path.join(local, "markets.jsonl")
    write(final, b"one\n")
    os.utime(final, (1700000000, 1700000000))
    assert p.once() == 0
    assert ("prefix", "markets.jsonl", 4) in server.events
    assert server.tails() == [] and "markets.jsonl" not in server.scps()
    assert os.path.getmtime(final) == 1700000000


def test_new_bytes_stop_at_the_size_the_server_gave_even_if_the_log_grew_since(tmp_path):
    server = FakeServer({"markets.jsonl": b"one\ntwo\n"}, {"writing": None})
    real = server.ssh

    def ssh(cmd):
        out = real(cmd)
        if shlex.split(cmd)[3:5] == ["stat", "-c"] and "markets.jsonl" in shlex.split(cmd):
            server.files["markets.jsonl"] += b"three\n"           # the recorder appends between the two calls
        return out
    server.ssh = ssh
    p, local = make(tmp_path, server)
    write(os.path.join(local, "markets.jsonl"), b"one\n")
    assert p.once() == 0
    assert read(os.path.join(local, "markets.jsonl")) == b"one\ntwo\n"
    server.ssh = real
    p2, _ = make(tmp_path, server)
    assert p2.once() == 0                                         # the next run takes the rest
    assert read(os.path.join(local, "markets.jsonl")) == b"one\ntwo\nthree\n"


def test_new_bytes_of_the_wrong_length_are_not_added(tmp_path):
    server = FakeServer({"markets.jsonl": b"one\ntwo\n"}, {"writing": None})
    server.short_tail = {"markets.jsonl"}
    p, local = make(tmp_path, server)
    write(os.path.join(local, "markets.jsonl"), b"one\n")
    assert p.once() == 0
    assert read(os.path.join(local, "markets.jsonl")) == b"one\n"
    assert not os.path.exists(os.path.join(local, "markets.jsonl.part"))
    assert "markets.jsonl" in log_text(local) and p.errors >= 1
    server.short_tail = set()
    p2, _ = make(tmp_path, server)
    assert p2.once() == 0
    assert read(os.path.join(local, "markets.jsonl")) == b"one\ntwo\n"


def test_no_copy_uses_ssh_compression(tmp_path):
    server, local, *_ = busy_run(tmp_path)
    assert [a for a in server.calls if os.path.basename(a[0]).lower() == "scp.exe"]
    assert not [a for a in server.calls if "-C" in a]


def test_missing_small_file_is_logged_and_the_rest_still_copied(tmp_path):
    server = FakeServer({"markets.jsonl": b"m\n", "events.jsonl": b"e\n"}, {"writing": None})
    p, local = make(tmp_path, server)
    assert p.once() == 0
    assert read(os.path.join(local, "markets.jsonl")) == b"m\n"
    assert read(os.path.join(local, "events.jsonl")) == b"e\n"
    assert not os.path.exists(os.path.join(local, "results.jsonl"))
    assert not os.path.exists(os.path.join(local, "results.jsonl.part"))
    assert "results.jsonl" in log_text(local)


def test_shorter_server_log_goes_to_a_reset_file_and_the_laptop_copy_is_untouched(tmp_path):
    # the recorder only appends to these, so a shorter one means the server's folder was reset: keep the history
    server = FakeServer({"markets.jsonl": b"one\n"}, {"writing": None})
    p, local = make(tmp_path, server)
    final = os.path.join(local, "markets.jsonl")
    write(final, b"one\ntwo\nthree\n")
    os.utime(final, (1700000000, 1700000000))
    write(os.path.join(local, "status.json"), b'{"writing": "something much longer than the new one"}')
    assert p.once() == 0
    assert read(final) == b"one\ntwo\nthree\n" and os.path.getmtime(final) == 1700000000
    assert read(os.path.join(local, "markets.reset1.jsonl")) == b"one\n"
    assert not [n for n in os.listdir(local) if n.endswith(".part")]
    assert read(os.path.join(local, "status.json")) == server.files["status.json"]   # a snapshot: always replaced
    text = log_text(local)
    assert "WARNING" in text and "markets.reset1.jsonl" in text and "reset" in text


def test_rewritten_server_log_never_overwrites_the_laptop_copy(tmp_path):
    # as long as the laptop's or longer, but it doesn't start with the laptop's bytes: rewritten, not appended to
    server = FakeServer({"markets.jsonl": b"uno\ndos\ntres\n", "results.jsonl": b"r1\n"}, {"writing": None})
    p, local = make(tmp_path, server)
    write(os.path.join(local, "markets.jsonl"), b"one\ntwo\n")
    write(os.path.join(local, "results.jsonl"), b"R1\n")                    # same length, different bytes
    assert p.once() == 0
    assert read(os.path.join(local, "markets.jsonl")) == b"one\ntwo\n"
    assert read(os.path.join(local, "markets.reset1.jsonl")) == b"uno\ndos\ntres\n"
    assert read(os.path.join(local, "results.jsonl")) == b"R1\n"
    assert read(os.path.join(local, "results.reset1.jsonl")) == b"r1\n"
    assert server.tails() == []
    assert "WARNING" in log_text(local)


def test_later_runs_add_to_the_newest_reset_file(tmp_path):
    server = FakeServer({"markets.jsonl": b"new1\n"}, {"writing": None})
    p, local = make(tmp_path, server)
    write(os.path.join(local, "markets.jsonl"), b"old1\nold2\n")
    assert p.once() == 0
    assert read(os.path.join(local, "markets.reset1.jsonl")) == b"new1\n"
    server.files["markets.jsonl"] += b"new2\n"
    p2, _ = make(tmp_path, server)
    assert p2.once() == 0
    assert read(os.path.join(local, "markets.jsonl")) == b"old1\nold2\n"
    assert read(os.path.join(local, "markets.reset1.jsonl")) == b"new1\nnew2\n"
    assert server.tails()[-1] == ("markets.jsonl", 6, 5)                     # only the new bytes
    assert server.scps().count("markets.jsonl") == 1
    server.files["markets.jsonl"] = b"again\n"                                # reset a second time
    p3, _ = make(tmp_path, server)
    assert p3.once() == 0
    assert read(os.path.join(local, "markets.jsonl")) == b"old1\nold2\n"
    assert read(os.path.join(local, "markets.reset1.jsonl")) == b"new1\nnew2\n"
    assert read(os.path.join(local, "markets.reset2.jsonl")) == b"again\n"
    assert "markets.reset2.jsonl" in log_text(local)


# ---------------------------------------------------------------------------------------------------------------
# offline and failures


def test_ssh_failure_logs_and_exits_zero(tmp_path):
    server = FakeServer(three_files(), {"writing": T12})
    server.down = True
    p, local = make(tmp_path, server)
    assert p.once() == 0
    assert len(server.calls) == 1                              # no scp, no rm after the first failure
    assert "Connection timed out" in log_text(local)
    assert not os.path.exists(os.path.join(local, "pull.lock"))


def test_listing_failure_logs_and_exits_zero(tmp_path):
    server = FakeServer(three_files(), {"writing": T12})
    real = server.ssh
    server.ssh = lambda cmd: (255, "Connection reset\n") if "sha256sum" in cmd else real(cmd)
    p, local = make(tmp_path, server)
    assert p.once() == 0
    assert server.scps() == [] and server.rms() == []
    assert "Connection reset" in log_text(local)


def test_timed_out_command_counts_as_offline(tmp_path, monkeypatch):
    monkeypatch.setattr(pull, "BUSY", (0, 0))                  # the real clock: never wait in a test
    calls = []

    def run(args, timeout):
        calls.append(args)
        return pull.TIMED_OUT, ""
    local = str(tmp_path / "data")
    p = pull.Pull(host=HOST, key=KEY, remote=REMOTE, local=local, run=run)
    assert p.once() == 0
    assert len(calls) == 1
    assert "timed out" in log_text(local).lower()


def test_missing_ssh_program_is_logged_not_raised(tmp_path):
    rc, out = pull.run_process([str(tmp_path / "no-such-ssh.exe"), "-V"], 5)
    assert rc == pull.NOT_STARTED and out


# ---------------------------------------------------------------------------------------------------------------
# going easy on the server: it shares its disk and CPU with the live bot


def backlog(n):
    """n closed hour files, a day's worth and more, oldest first by name."""
    names = [f"ws-202610{25 + h // 24:02d}T{h % 24:02d}.txt.gz" for h in range(n)]
    return names, {name: body(name, 50) for name in names}


def test_hashes_at_most_max_hash_files_a_run_oldest_first(tmp_path):
    names, files = backlog(pull.MAX_HASH + 5)
    server = FakeServer(files, {"writing": None})
    p, local = make(tmp_path, server)
    assert p.once() == 0
    assert server.hashed() == names[:pull.MAX_HASH]
    assert server.rms() == names[:pull.MAX_HASH]
    assert sorted(n for n in server.files if n.startswith("ws-")) == names[pull.MAX_HASH:]
    assert p.once() == 0                                          # the next run takes the rest
    assert not [n for n in server.files if n.startswith("ws-")]


def test_hashes_one_file_per_call_each_just_before_its_copy(tmp_path):
    names, files = backlog(pull.MAX_HASH + 5)
    server = FakeServer(files, {"writing": None})
    p, local = make(tmp_path, server)
    assert p.once() == 0
    assert server.hash_calls() == [(n,) for n in names[:pull.MAX_HASH]]
    order = [(e[0], e[1] if e[0] != "hash" else e[1][0]) for e in server.events if e[0] in ("hash", "scp", "rm")]
    first = [(kind, n) for kind, n in order if n in names[:2]]
    assert first == [("hash", names[0]), ("scp", names[0]), ("rm", names[0]),
                     ("hash", names[1]), ("scp", names[1]), ("rm", names[1])]


def test_a_file_that_cant_be_hashed_is_kept_and_the_rest_go_on(tmp_path):
    server = FakeServer({T10: body(T10), T11: body(T11)}, {"writing": None})
    real = server.ssh
    server.ssh = lambda cmd: ((1, f"sha256sum: ./{T10}: Input/output error\n")
                              if "sha256sum" in cmd and T10 in cmd else real(cmd))
    p, local = make(tmp_path, server)
    assert p.once() == 0
    assert T10 in server.files and T10 not in server.scps()
    assert server.rms() == [T11]
    assert "Input/output error" in log_text(local) and p.errors == 1


def test_open_and_recent_files_are_never_hashed(tmp_path):
    server = FakeServer({T10: body(T10), T11: body(T11), T12: body(T12)}, {"writing": T12}, ages={T11: 5})
    p, local = make(tmp_path, server)
    assert p.once() == 0
    assert server.hashed() == [T10]


def hour_hash_commands(server):
    """The ssh commands that hash hour files (the log checks hash too, but with stat and head)."""
    return [c[-1] for c in server.calls
            if c[0] == SSH and "sha256sum" in shlex.split(c[-1]) and "stat" not in shlex.split(c[-1])]


def test_the_listing_hashes_nothing_and_hashing_runs_at_lowest_priority(tmp_path):
    server = FakeServer({T10: body(T10), T11: body(T11)}, {"writing": None})
    p, local = make(tmp_path, server)
    assert p.once() == 0
    cmds = [c[-1] for c in server.calls if c[0] == SSH]
    listing = next(c for c in cmds if "find" in c.split())
    assert "sha256sum" not in listing
    hashing = hour_hash_commands(server)
    assert [shlex.split(c) for c in hashing] == [["cd", REMOTE, "&&", *LOW, "sha256sum", "--", "./" + n]
                                                 for n in (T10, T11)]


def test_no_hash_call_when_nothing_is_closed(tmp_path):
    server = FakeServer({T10: body(T10)}, {"writing": T10})
    p, local = make(tmp_path, server)
    assert p.once() == 0
    assert hour_hash_commands(server) == [] and server.hashed() == []


def test_waits_out_the_bots_busy_minutes_before_starting(tmp_path):
    server = FakeServer({T10: body(T10)}, {"writing": None})
    start = QUIET_TIME - 200 + 450                                # 450 s into a window: the bot enters at 480 s
    t, slept = [start], []

    def sleep(seconds):
        slept.append(seconds)
        t[0] += seconds
    p, local = make(tmp_path, server, clock=lambda: t[0], sleep=sleep)
    assert p.once() == 0
    assert slept and slept[0] == pytest.approx(pull.BUSY[1] - 450)
    assert server.rms() == [T10]
    assert "busy" in log_text(local)


def test_each_hour_file_waits_if_the_backlog_runs_into_the_busy_minutes(tmp_path):
    server = FakeServer({T10: body(T10), T11: body(T11)}, {"writing": None})
    base = QUIET_TIME - 200
    times = iter([base + 300, base + 300, base + 300, base + 500, base + 620, base + 620, base + 620])
    t, slept = [base + 300], []

    def clock():
        t[0] = next(times, t[0])
        return t[0]

    def sleep(seconds):
        slept.append(seconds)
    p, local = make(tmp_path, server, clock=clock, sleep=sleep)
    assert p.once() == 0
    assert slept == [pytest.approx(pull.BUSY[1] - 500)]
    assert server.rms() == [T10, T11]


@pytest.mark.parametrize("start", range(0, 900, 50))
def test_nothing_that_reads_a_server_file_starts_in_the_busy_minutes(tmp_path, start):
    # every command takes 70 s of the clock here, so a run crosses the busy minutes at some point whatever its start
    names, files = backlog(4)
    files.update({"markets.jsonl": b"m1\nm2\n", "results.jsonl": b"r1\n", "events.jsonl": b"e1\ne2\n"})
    server = FakeServer(files, {"writing": None})
    clock = Clock(QUIET_TIME - 200 + start, step=70)
    server.clock = clock
    p, local = make(tmp_path, server, clock=clock, sleep=clock.sleep)
    write(os.path.join(local, "markets.jsonl"), b"m1\n")           # so its new bytes are fetched too
    assert p.once() == 0
    heavy = [(t, args) for t, args in server.started if reads_server_files(args)]
    assert len(heavy) >= 4 + 4
    assert not [(t % pull.WINDOW, args[-1]) for t, args in heavy if in_busy(t)]
    assert server.rms() == names
    for name in LOGS:
        assert read(os.path.join(local, name)) == server.files[name]


def test_busy_minutes_cover_the_bots_prep_entry_and_order_deadline():
    assert pull.BUSY[0] <= 420 and pull.BUSY[1] >= 600


def test_log_records_start_copies_deletes_and_bytes(tmp_path):
    server = FakeServer({T10: body(T10), T11: body(T11)}, {"writing": T11})
    p, local = make(tmp_path, server)
    assert p.once() == 0
    text = log_text(local)
    assert "start" in text
    assert f"copied {T10}" in text
    assert f"deleted {T10}" in text
    assert str(len(body(T10))) in text or "MB" in text


# ---------------------------------------------------------------------------------------------------------------
# the safety rules, checked over one busy run


def busy_run(tmp_path):
    """One run with every case at once: fresh, identical, mismatch, failed copy, dup, odd names, small files."""
    T13, T14, T15 = "ws-20261025T13.txt.gz", "ws-20261025T14.txt.gz", "ws-20261025T15.txt.gz"
    files = {n: body(n) for n in (T09, T10, T11, T12, T12_1, T13, T14, T15)}
    files.update({"ws-20261025T10 copy.txt.gz": b"x", "notes.txt": b"x", "markets.jsonl": b"m\n",
                  "results.jsonl": b"r\n", "events.jsonl": b"e\n"})
    server = FakeServer(files, {"writing": T15}, ages={T14: 5})
    server.corrupt = {T11}
    server.scp_fail = {T12}
    p, local = make(tmp_path, server)
    write(os.path.join(local, T09), body(T09))                 # identical already
    write(os.path.join(local, T10), b"different T10")          # goes to dup
    write(os.path.join(local, "notes-of-mine.txt"), b"mine")
    write(os.path.join(local, "markets.jsonl"), b"")
    before = {n: read(os.path.join(local, n)) for n in os.listdir(local)}

    removed, renamed = [], []
    real_remove, real_unlink, real_rename, real_replace = os.remove, os.unlink, os.rename, os.replace

    def rec_remove(path, *a, **k):
        removed.append(str(path))
        return real_remove(path, *a, **k)

    def rec_unlink(path, *a, **k):
        removed.append(str(path))
        return real_unlink(path, *a, **k)

    def rec_rename(src, dst, *a, **k):
        renamed.append((str(src), str(dst), os.path.exists(dst)))
        return real_rename(src, dst, *a, **k)

    def rec_replace(src, dst, *a, **k):
        renamed.append((str(src), str(dst), os.path.exists(dst)))
        return real_replace(src, dst, *a, **k)

    def no_tree(*a, **k):
        raise AssertionError("rmtree called")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(os, "remove", rec_remove)
        mp.setattr(os, "unlink", rec_unlink)
        mp.setattr(os, "rename", rec_rename)
        mp.setattr(os, "replace", rec_replace)
        mp.setattr(os, "rmdir", no_tree)
        mp.setattr(shutil, "rmtree", no_tree)
        assert p.once() == 0
    return server, local, before, removed, renamed


def test_rm_is_only_ever_rm_dash_dash_remote_slash_valid_name(tmp_path):
    server, local, before, removed, renamed = busy_run(tmp_path)
    rm_cmds = [c[-1] for c in server.calls if os.path.basename(c[0]).lower() == "ssh.exe" and "rm" in c[-1].split()]
    assert rm_cmds
    for cmd in rm_cmds:
        m = RM_FORM.fullmatch(cmd)
        assert m, cmd
        held, part_left = server.at_rm[m.group(1)]
        assert held is not None and sha(held) == sha(body(m.group(1))) and not part_left
    assert sorted(server.rms()) == [T09, T12_1, "ws-20261025T13.txt.gz"]


def test_nothing_deleted_on_the_laptop_but_part_files_and_the_lock(tmp_path):
    server, local, before, removed, renamed = busy_run(tmp_path)
    for path in removed:
        assert path.endswith(".part") or os.path.basename(path) == "pull.lock", path
    for src, dst, existed in renamed:
        assert src.endswith(".part"), src
        if existed:
            assert os.path.basename(dst) in SMALL, dst
    for name, data in before.items():
        assert os.path.exists(os.path.join(local, name)), name
        if name not in SMALL:
            assert read(os.path.join(local, name)) == data, name
    assert not [n for n in os.listdir(local) if n.endswith(".part")]


# ---------------------------------------------------------------------------------------------------------------
# the command lines


def test_every_command_uses_the_key_batchmode_and_connecttimeout(tmp_path):
    server, local, *_ = busy_run(tmp_path)
    assert server.calls
    for args in server.calls:
        assert args[0] in (SSH, SCP)
        target = args.index(HOST) if args[0] == SSH else next(i for i, a in enumerate(args) if a.startswith(HOST + ":"))
        opts = args[1:target]
        pairs = list(zip(opts, opts[1:]))
        assert ("-i", KEY) in pairs
        assert ("-o", "BatchMode=yes") in pairs
        assert ("-o", "ConnectTimeout=15") in pairs
        if args[0] == SSH:
            assert target == len(args) - 2                     # one remote command string after the host
        else:
            assert args[-1].startswith(local) and args[-1].endswith(".part")


def test_remote_commands_quote_the_remote_path(tmp_path):
    server = FakeServer({T10: body(T10)}, {"writing": None})
    p, local = make(tmp_path, server)
    assert p.once() == 0
    cmds = [c[-1] for c in server.calls if c[0] == SSH]
    assert shlex.split(cmds[0]) == ["cat", "--", REMOTE + "/status.json"]
    assert shlex.split(cmds[1])[:3] == ["cd", REMOTE, "&&"]
    assert pull.quote("/a b/c'd") == "'/a b/c'\"'\"'d'"


@pytest.mark.parametrize("remote", ["relative/data", "/home/kalshi/da ta", "/home/kalshi/data; rm -rf ~",
                                    "/home/kalshi/$(id)", "/home/kalshi/data/../..", "/", ""])
def test_unsafe_remote_folder_is_refused_before_any_command(tmp_path, remote):
    server = FakeServer()
    rc = pull.main([f"--remote={remote}", "--local", str(tmp_path / "data"), "--key", KEY], run=server)
    assert rc == 2
    assert server.calls == []


@pytest.mark.parametrize("host", ["-oProxyCommand=calc", "kalshi@host name", "kalshi@host:22", ""])
def test_unsafe_host_is_refused_before_any_command(tmp_path, host):
    server = FakeServer()
    rc = pull.main([f"--host={host}", "--local", str(tmp_path / "data"), "--key", KEY], run=server)
    assert rc == 2
    assert server.calls == []


def test_cli_defaults():
    a = pull.parse_args([])
    assert a.host == "kalshi@recorder-host"
    assert a.key == os.path.join(os.path.expanduser("~"), ".ssh", "recorder.pem")
    assert a.remote == "/home/kalshi/maker-shadow/data"
    assert os.path.normcase(os.path.abspath(a.local)) == os.path.normcase(
        os.path.join(os.path.dirname(os.path.abspath(pull.__file__)), "data"))
    assert a.ssh == SSH and a.scp == SCP


def test_main_runs_a_whole_pull_through_the_injected_run(tmp_path, monkeypatch):
    monkeypatch.setattr(pull, "BUSY", (0, 0))                  # main uses the real clock: never wait in a test
    server = FakeServer({T10: body(T10), T11: body(T11)}, {"writing": T11})
    local = str(tmp_path / "data")
    server.local = local
    rc = pull.main(["--local", local, "--key", KEY, "--host", HOST, "--remote", REMOTE], run=server)
    assert rc == 0
    assert read(os.path.join(local, T10)) == body(T10)
    assert server.rms() == [T10]
