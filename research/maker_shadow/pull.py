"""The laptop's hourly copy of the maker shadow recorder's data: closed hour files come to the laptop, and each is
deleted from the server only once the laptop's copy is proven identical.

The recorder (maker_shadow.py, on the Ohio server) writes Kalshi's order book and trade feed to one gzip file an
hour, ws-YYYYMMDDTHH.txt.gz (ws-YYYYMMDDTHH.n.txt.gz after a restart within the hour), 110-225 MB each. The server's
disk is shared with the live bot, so copied files must not pile up there; but a file deleted before the laptop holds
a good copy is gone for good. Spec: SPEC.md, "pull.py: the laptop's hourly copy".

A run, from Task Scheduler every hour:

1. Takes <local>/pull.lock (it holds the pid). A lock older than LOCK_STALE, or whose pid isn't running, is stale
   and taken over; a live one means another run is still copying, so this one exits at once.
2. Reads the server's status.json for "writing", the hour file the recorder still has open.
3. Lists the server's hour files with their size and last change time, and the server's clock (no contents read).
   Only names matching NAME_RE count; anything else is ignored and never deleted. It skips the "writing" file; any
   file named for the server's current UTC hour (or later), even a closed one, since the recorder could still open
   another file of that hour and a name freed by a delete could be used twice; any file changed in the last MIN_AGE
   seconds (status.json is rewritten only every 30 s, so right after a recorder restart or the turn of the hour it
   can still name the old file); and, if status.json can't be read, the newest-named file too. Of the rest it takes
   the oldest MAX_HASH; the others wait for the next run, so a backlog clears a dozen files an hour, not all at once.
4. Oldest first, one file at a time: the server hashes it (SHA-256, one file per ssh call, at the lowest CPU and
   disk priority: nice, ionice). A file the laptop already has with the same SHA-256 is deleted on the server.
   Otherwise scp copies it to <name>.part, the copy's SHA-256 is checked against the server's, the .part is renamed
   to <name>, and the server's is deleted (rm -- <remote>/<name>). A failed hash, a mismatch or a failed copy
   removes any .part, keeps the server's, and moves on; three failed copies in a row end the run (the connection is
   likely gone). A laptop file of the same name with different contents is never overwritten: the copy goes to
   <name>.dup<n> and the server's is kept. Below MIN_FREE_GB free on the laptop it copies nothing new.
5. The recorder's logs, markets.jsonl, results.jsonl and events.jsonl, come over by their new bytes only (the
   recorder only appends to them). For each, one ssh call at the lowest priority gives the server's size and the
   SHA-256 of its first L bytes, L being the laptop copy's length. Equal to the laptop copy's SHA-256: the server's
   bytes from L on are fetched (through a .part whose length must be size - L) and appended. Not equal, or the
   server's is shorter: the server's folder was reset or the file rewritten. The laptop's copy is then never touched:
   the server's whole log goes to the next <stem>.reset<n>.jsonl (a WARNING in the log), and later runs add to the
   newest reset file by the same rule. maker_replay.py reads every markets*.jsonl and results*.jsonl. status.json,
   a snapshot, is copied whole over the laptop's (through .part and a rename). None of the four is ever deleted on
   the server: the recorder reads them back on restart.

Nothing that reads a file on the server (a hash, a copy, a log's check or its new bytes) starts in BUSY, the bot's
prep-to-deadline seconds of each 15-minute window: each such call waits them out first. The server's disk and CPU
are the live bot's too.

It never deletes anything on the laptop but its own .part files and lock, never overwrites a laptop log, never
deletes a server file whose laptop copy it hasn't just hashed, and never runs rm on a name that didn't match
NAME_RE. ssh and scp are Windows OpenSSH, run with the key, BatchMode (never a prompt), a 15 s connect timeout and no
compression. Every run appends to <local>/pull.log; when the server can't be reached (the laptop is offline, on a
bad hotspot, or the server is down) it logs that and exits 0, and the next hour tries again.

    python research/maker_shadow/pull.py          # the defaults below, into research/maker_shadow/data
    python research/maker_shadow/pull.py --host kalshi@recorder-host --key %USERPROFILE%\\.ssh\\recorder.pem
        --remote /home/kalshi/maker-shadow/data --local research/maker_shadow/data
"""
import argparse
import base64
import binascii
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from typing import NamedTuple

HERE = os.path.dirname(os.path.abspath(__file__))

SSH = r"C:\Windows\System32\OpenSSH\ssh.exe"
SCP = r"C:\Windows\System32\OpenSSH\scp.exe"
HOST = "kalshi@recorder-host"                                        # the recorder's server: user@host, or an ssh alias
KEY = os.path.join(os.path.expanduser("~"), ".ssh", "recorder.pem")
REMOTE = "/home/kalshi/maker-shadow/data"
LOCAL = os.path.join(HERE, "data")

NAME_RE = re.compile(r"^ws-(\d{8})T(\d{2})(?:\.(\d+))?\.txt\.gz$")
APPEND_ONLY = ("markets.jsonl", "results.jsonl", "events.jsonl")    # the recorder only ever appends to these
STATUS = "status.json"                                                # a snapshot, rewritten every 30 s
LOW = "nice -n 19 ionice -c3"                                         # the lowest CPU and disk priority

LOCK_STALE = 6 * 3600     # a lock this old is stale even if its pid looks alive (Windows reuses pids)
MIN_AGE = 45              # a file changed less than this many seconds ago (server clock) may still be open
MIN_FREE_GB = 20          # the laptop keeps at least this much disk free
MAX_FAILS = 3             # copies failed in a row before the run gives up
SSH_TIMEOUT = 60          # status.json, the listing, rm
HASH_TIMEOUT = 900        # one hour file's SHA-256 on the server, at the lowest disk priority
SMALL_TIMEOUT = 600       # a log's check, its new bytes, status.json (plus the size at COPY_FLOOR for a whole log)
COPY_FLOOR = 100_000      # an hour file's copy may take 300 s plus its size at this many bytes a second
# The server's disk and CPU are the live bot's too. Hashing reads every byte of a file, so a run hashes at most
# MAX_HASH files (about 3 GB), oldest first, one file per call at the lowest CPU and disk priority, and the rest wait
# for the next run. Nothing that reads a file on the server (a hash, a copy, a log's check or its new bytes) starts
# in BUSY, seconds into each 15-minute window (by the laptop's clock, with margin): the bot preps at 450 s, enters at
# 480 s, and sends no order after 600 s. Each such call waits it out first.
MAX_HASH = 12
WINDOW = 900
BUSY = (400, 620)

# run()'s return codes for what never reached the server: ssh's own failure code, a timeout, a missing program
SSH_FAILED = 255
TIMED_OUT = -1
NOT_STARTED = -2
OFFLINE = (SSH_FAILED, TIMED_OUT, NOT_STARTED)

SAFE_REMOTE = re.compile(r"^(/[A-Za-z0-9_][A-Za-z0-9._-]*)+$")    # absolute, plain characters only
SAFE_HOST = re.compile(r"^(?:[A-Za-z0-9_][A-Za-z0-9._-]*@)?[A-Za-z0-9][A-Za-z0-9.-]*$")

quote = shlex.quote


class Remote(NamedTuple):
    size: int
    mtime: float
    sha: str


# ---------------------------------------------------------------------------------------------------------------
# pure helpers


def hour_key(name):
    """Sort key for hour file names: by the hour in the name, then the .n suffix (none first)."""
    m = NAME_RE.fullmatch(name)
    return (m.group(1), m.group(2), int(m.group(3)) if m.group(3) else -1)


def name_hour(name):
    """Epoch seconds at the start of the UTC hour an hour file's name is for, or None when it is no real hour."""
    m = NAME_RE.fullmatch(name)
    try:
        return int(datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H").replace(tzinfo=timezone.utc).timestamp())
    except ValueError:
        return None


def parse_status(text):
    """(writing, ok) from status.json's text: ok is False when it isn't a JSON object with "writing" a str or None."""
    try:
        status = json.loads(text)
    except ValueError:
        return None, False
    if not isinstance(status, dict) or "writing" not in status:
        return None, False
    writing = status["writing"]
    if writing is not None and not isinstance(writing, str):
        return None, False
    return writing, True


SIZE_LINE = re.compile(r"^(\d+) (\d+(?:\.\d+)?) (.+)$")
HASH_LINE = re.compile(r"^([0-9a-f]{64}) [ *]\./(.+)$")     # "*" marks binary mode on some systems


def parse_listing(text):
    """(server_now, {name: Remote}) from the listing command's output with a hash call's output after it.

    The listing is `date +%s` (a line of digits), then `find -printf '%s %T@ %f\\n'` lines (size, last change, name);
    after it come `sha256sum` lines ("<hash>  ./<name>", or "<hash> *./<name>" in binary mode; sha256sum starts a
    line with a backslash when it had to escape the name). A name off NAME_RE, seen twice, or missing its size or
    hash is left out. server_now is None when there is no clock line, and then nothing in the listing is trusted.
    """
    now, sizes, hashes, twice = None, {}, {}, set()
    for line in text.splitlines():
        line = line.rstrip("\r")
        if now is None and line.isdigit():
            now = int(line)
            continue
        m = HASH_LINE.match(line)
        if m:
            sha, name = m.groups()
            if name in hashes:
                twice.add(name)
            hashes[name] = sha
            continue
        m = SIZE_LINE.match(line)
        if m:
            size, mtime, name = m.groups()
            if name in sizes:
                twice.add(name)
            sizes[name] = (int(size), float(mtime))
    if now is None:
        return None, {}
    files = {}
    for name, (size, mtime) in sizes.items():
        if NAME_RE.fullmatch(name) and name in hashes and name not in twice:
            files[name] = Remote(size, mtime, hashes[name])
    return now, files


def parse_sizes(text):
    """(server_now, {name: (size, mtime)}) from the listing command's output, before any hashing: names on NAME_RE,
    each seen once. server_now is None when there is no clock line, and then nothing in it is trusted."""
    now, sizes, twice = None, {}, set()
    for line in text.splitlines():
        line = line.rstrip("\r")
        if now is None and line.isdigit():
            now = int(line)
            continue
        m = SIZE_LINE.match(line)
        if m and not HASH_LINE.match(line):
            size, mtime, name = m.groups()
            if name in sizes:
                twice.add(name)
            sizes[name] = (int(size), float(mtime))
    if now is None:
        return None, {}
    return now, {n: v for n, v in sizes.items() if NAME_RE.fullmatch(n) and n not in twice}


PREFIX_HASH = re.compile(r"^([0-9a-f]{64}) [ *]-$")      # sha256sum of its input: "<hash>  -"


def parse_prefix(text):
    """(size, sha) from a log check's output: stat's size line, then sha256sum's "<hash>  -" line. None when the
    output isn't exactly those two lines."""
    lines = [line.rstrip("\r") for line in (text or "").splitlines() if line.strip()]
    if len(lines) != 2 or not lines[0].isdigit():
        return None
    m = PREFIX_HASH.match(lines[1])
    return (int(lines[0]), m.group(1)) if m else None


def decode_tail(text):
    """The bytes base64 printed (in lines), or None when the output isn't base64."""
    try:
        return base64.b64decode("".join((text or "").split()), validate=True)
    except (binascii.Error, ValueError):
        return None


def reset_name(name, n):
    """markets.jsonl, 2 -> markets.reset2.jsonl: where a reset server's log is kept on the laptop."""
    stem, ext = os.path.splitext(name)
    return f"{stem}.reset{n}{ext}"


def file_sha(path):
    with open(path, "rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def same(path, remote):
    """True when the laptop file at path is byte for byte the server's (size first, then SHA-256)."""
    return os.path.isfile(path) and os.path.getsize(path) == remote.size and file_sha(path) == remote.sha


def pid_alive(pid):
    """True when a process with this pid is running. Never os.kill on Windows: there it terminates the process."""
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.restype = ctypes.c_void_p
        handle = kernel32.OpenProcess(0x1000, False, pid)        # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return ctypes.get_last_error() == 5                   # access denied: it exists; else it doesn't
        try:
            code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(ctypes.c_void_p(handle), ctypes.byref(code)):
                return True
            return code.value == 259                              # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(ctypes.c_void_p(handle))
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OverflowError:
        return False
    return True


def free_bytes(path):
    return shutil.disk_usage(path).free


def run_process(args, timeout):
    """Runs a program with no window and no input. (returncode, stdout); on failure stderr is added, for the log.

    A timeout gives TIMED_OUT (the program is killed) and a program that can't start gives NOT_STARTED.
    """
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        p = subprocess.run(args, stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout, creationflags=flags)
    except subprocess.TimeoutExpired:
        return TIMED_OUT, f"timed out after {timeout:.0f} s"
    except OSError as e:
        return NOT_STARTED, f"could not start {args[0]}: {e}"
    out = p.stdout.decode("utf-8", "replace")
    if p.returncode != 0:
        out += p.stderr.decode("utf-8", "replace")
    return p.returncode, out


def check_config(host, remote):
    """The reason host or remote is unsafe to put on a command line, or None."""
    if not SAFE_HOST.fullmatch(host or ""):
        return f"refusing host {host!r}: expected user@host with plain characters"
    if not SAFE_REMOTE.fullmatch(remote or "") or any(p in (".", "..") for p in remote.split("/")):
        return f"refusing remote folder {remote!r}: expected an absolute path of plain characters, no . or .."
    return None


def tail(text, n=300):
    text = " ".join((text or "").split())
    return text[-n:] if text else "(no output)"


# ---------------------------------------------------------------------------------------------------------------
# a run


class Pull:
    def __init__(self, host=HOST, key=KEY, remote=REMOTE, local=LOCAL, ssh=SSH, scp=SCP, run=run_process,
                 now=time.time, pid_alive=pid_alive, free_bytes=free_bytes, clock=time.time, sleep=time.sleep):
        problem = check_config(host, remote)
        if problem:
            raise ValueError(problem)
        self.host, self.key, self.remote, self.local = host, key, remote.rstrip("/"), os.path.abspath(local)
        self.ssh_exe, self.scp_exe = ssh, scp
        self.run, self.now, self.pid_alive, self.free_bytes = run, now, pid_alive, free_bytes
        self.clock, self.sleep = clock, sleep    # for keeping out of the bot's busy minutes
        self.lock = os.path.join(self.local, "pull.lock")
        self.logfile = os.path.join(self.local, "pull.log")
        self.copied = self.deleted = self.kept = self.errors = 0
        self.bytes = 0

    # -- plumbing -----------------------------------------------------------------------------------------------
    def log(self, text):
        stamp = datetime.fromtimestamp(self.now()).astimezone().isoformat(timespec="seconds")
        line = f"{stamp} [{os.getpid()}] {text}\n"
        try:
            with open(self.logfile, "a", encoding="utf-8") as f:
                f.write(line)
        except OSError:
            pass
        try:
            print(line, end="")                  # nothing to print to under pythonw: print() then does nothing
        except (OSError, ValueError):
            pass

    def options(self):
        return ["-i", self.key, "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
                "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=4"]

    def ssh(self, command, timeout=SSH_TIMEOUT):
        return self.run([self.ssh_exe, *self.options(), self.host, command], timeout)

    def scp(self, name, dest, timeout):
        # OpenSSH 9's scp uses SFTP, which takes the path literally (no remote shell): the remote folder and the name
        # are plain characters only (check_config, NAME_RE, APPEND_ONLY, STATUS), so the path needs no quoting in
        # either mode. No -C: compressing would cost the server's CPU at normal priority, and the hour files are
        # gzip already.
        return self.run([self.scp_exe, *self.options(), "-q", f"{self.host}:{self.remote}/{name}", dest], timeout)

    def clear_of_bot(self, what):
        """Waits out the bot's busy minutes (BUSY) before something heavy on the server starts."""
        into = self.clock() % WINDOW
        if BUSY[0] <= into < BUSY[1]:
            wait = BUSY[1] - into
            self.log(f"waiting {wait:.0f} s before {what}: the bot is busy {BUSY[0]}-{BUSY[1]} s into each window")
            self.sleep(wait)

    def remove_part(self, path):
        assert path.endswith(".part"), path
        try:
            os.remove(path)
        except FileNotFoundError:
            pass

    # -- the lock -----------------------------------------------------------------------------------------------
    def take_lock(self):
        for _ in range(2):
            try:
                fd = os.open(self.lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                if not self.stale_lock():
                    return False
                try:
                    os.remove(self.lock)
                except FileNotFoundError:
                    pass
                continue
            with os.fdopen(fd, "w") as f:
                f.write(f"{os.getpid()}\n")
            return True
        return False

    def stale_lock(self):
        try:
            age = self.now() - os.path.getmtime(self.lock)
            with open(self.lock, encoding="utf-8", errors="replace") as f:
                text = f.read().strip()
        except FileNotFoundError:
            return True
        try:
            pid = int(text.split()[0])
        except (ValueError, IndexError):
            pid = None
        if age > LOCK_STALE:
            self.log(f"taking over a stale lock (pid {pid}, {age / 3600:.1f} h old)")
            return True
        if pid is None or not self.pid_alive(pid):
            self.log(f"taking over a stale lock (pid {pid} isn't running)")
            return True
        self.log(f"another run holds the lock (pid {pid}, since {age / 60:.0f} min ago): exiting")
        return False

    def release_lock(self):
        try:
            with open(self.lock, encoding="utf-8") as f:
                mine = f.read().split()[:1] == [str(os.getpid())]
            if mine:
                os.remove(self.lock)
        except (OSError, IndexError):
            pass

    # -- the run ------------------------------------------------------------------------------------------------
    def once(self):
        """One pull. 0 when it finished or the server couldn't be reached; 1 on a bug (logged with its traceback)."""
        os.makedirs(self.local, exist_ok=True)
        if not self.take_lock():
            return 0
        try:
            self.log(f"start: {self.host}:{self.remote} -> {self.local}")
            self.pull()
            self.log(f"done: copied {self.copied} hour files ({self.bytes / 1e6:.1f} MB), deleted {self.deleted} on "
                     f"the server, kept {self.kept} there, {self.errors} errors")
            return 0
        except Exception:
            self.log("error: " + traceback.format_exc().rstrip().replace("\n", "\n    "))
            return 1
        finally:
            self.release_lock()

    def offline(self, what, rc, out):
        why = "timed out" if rc == TIMED_OUT else f"rc {rc}"
        self.log(f"{what} failed ({why}): {tail(out)}. Server or laptop offline? Next hour tries again")

    def pull(self):
        self.clear_of_bot("the run")
        rc, out = self.ssh(f"cat -- {quote(self.remote + '/status.json')}")
        if rc in OFFLINE:
            return self.offline("ssh", rc, out)
        writing, status_ok = parse_status(out) if rc == 0 else (None, False)
        if not status_ok:
            self.log(f"status.json unreadable (rc {rc}: {tail(out, 120)}): the newest hour file will be skipped too")

        rc, listing = self.ssh(self.listing_command(), timeout=SSH_TIMEOUT)
        if rc in OFFLINE:
            return self.offline("listing", rc, listing)
        if rc != 0:
            self.errors += 1
            return self.log(f"listing failed (rc {rc}): {tail(listing)}")
        server_now, sizes = parse_sizes(listing)
        if server_now is None:
            self.errors += 1
            return self.log(f"listing unreadable: {tail(listing)}")

        names = sorted(sizes, key=hour_key)
        skip = {}
        if status_ok and writing in sizes:
            skip[writing] = "still being written"
        if not status_ok and names:
            skip[names[-1]] = "newest, and status.json unreadable"
        this_hour = server_now - server_now % 3600
        hour_label = datetime.fromtimestamp(this_hour, timezone.utc).strftime("%H:00 UTC")
        for name in names:
            if name in skip:
                continue
            start, age = name_hour(name), server_now - sizes[name][1]
            if start is None:
                skip[name] = "its name is no real hour"
            elif start >= this_hour:
                # even closed (a paused recorder, a restart), the recorder could open another file of this hour, and
                # a name freed here could then be used again
                skip[name] = f"named for the server's current hour ({hour_label}) or later, waits for the hour to end"
            elif age < MIN_AGE:
                skip[name] = f"changed {age:.0f} s ago, may still be open"
        for name, why in skip.items():
            self.log(f"skipped {name}: {why}")
        self.kept += len(skip)
        closed = [n for n in names if n not in skip]
        todo, later = closed[:MAX_HASH], closed[MAX_HASH:]
        if later:
            self.kept += len(later)
            self.log(f"left {len(later)} hour files for the next run (at most {MAX_HASH} a run)")

        fails = 0
        for name in todo:                          # one file at a time: hash it, then copy it, then the next
            self.clear_of_bot(f"hashing {name}")
            rc, out = self.ssh(self.hash_command(name), timeout=HASH_TIMEOUT)
            if rc in OFFLINE:
                return self.offline(f"hashing {name}", rc, out)
            remote = parse_listing(listing + "\n" + out)[1].get(name) if rc == 0 else None
            if remote is None:
                self.kept += 1
                self.errors += 1
                self.log(f"no hash for {name} (rc {rc}: {tail(out, 200)}): kept on the server")
                continue
            result = self.hour_file(name, remote)
            fails = fails + 1 if result == "failed" else 0
            if fails >= MAX_FAILS:
                return self.log(f"{fails} copies failed in a row: giving up this run, next hour tries again")
        for name in APPEND_ONLY:
            self.log_file(name)
        self.copy_small(STATUS, STATUS, timeout=SMALL_TIMEOUT)

    def listing_command(self):
        """The server's clock, then each hour file's size, last change and name. Reads no file contents."""
        return (f"cd {quote(self.remote)} && date +%s && "
                f"find . -maxdepth 1 -type f -name 'ws-*.txt.gz' -printf '%s %T@ %f\\n'")

    def hash_command(self, name):
        """SHA-256 of one hour file, at the lowest CPU and disk priority. The name has already matched NAME_RE."""
        assert NAME_RE.fullmatch(name), name
        return f"cd {quote(self.remote)} && {LOW} sha256sum -- {quote('./' + name)}"

    def hour_file(self, name, remote):
        """Copies one closed hour file and deletes the server's once the copy is proven. Returns what happened."""
        final = os.path.join(self.local, name)
        target = final
        if os.path.exists(final):
            if same(final, remote):
                self.delete_remote(name, final, remote)
                return "had"
            n = 1
            while os.path.exists(f"{final}.dup{n}"):
                if same(f"{final}.dup{n}", remote):
                    self.kept += 1
                    self.log(f"kept {name} on the server: the laptop has a different {name}; this one is already "
                             f"saved as {name}.dup{n}. Sort it out by hand")
                    return "dup"
                n += 1
            target = f"{final}.dup{n}"
        if self.free_bytes(self.local) - remote.size < MIN_FREE_GB * 1e9:
            self.kept += 1
            self.log(f"kept {name} on the server: the laptop is low on space "
                     f"({self.free_bytes(self.local) / 1e9:.1f} GB free, keeping {MIN_FREE_GB} GB)")
            return "space"

        part = final + ".part"
        self.clear_of_bot(f"copying {name}")
        started = time.monotonic()
        rc, out = self.scp(name, part, timeout=300 + remote.size / COPY_FLOOR)
        if rc != 0:
            self.remove_part(part)
            self.kept += 1
            self.errors += 1
            why = "timed out" if rc == TIMED_OUT else f"rc {rc}"
            self.log(f"copy of {name} failed ({why}): {tail(out)}; kept on the server")
            return "failed"
        if not same(part, remote):
            got = os.path.getsize(part) if os.path.exists(part) else None
            self.remove_part(part)
            self.kept += 1
            self.errors += 1
            self.log(f"hash mismatch on {name} (server {remote.size} bytes, laptop got {got}): copy removed, "
                     f"kept on the server")
            return "mismatch"
        if os.path.exists(target):                # appeared since the check above: never overwrite it
            self.remove_part(part)
            self.kept += 1
            self.errors += 1
            self.log(f"{target} appeared during the copy: copy removed, kept {name} on the server")
            return "failed"
        os.rename(part, target)
        self.copied += 1
        self.bytes += remote.size
        took = time.monotonic() - started
        if target != final:
            self.kept += 1
            self.log(f"copied {name} to {os.path.basename(target)}: the laptop's {name} is a different file, so it "
                     f"was left alone and the server's kept. Sort it out by hand")
            return "dup"
        self.log(f"copied {name} ({remote.size / 1e6:.1f} MB, {remote.size} bytes, {took:.0f} s)")
        self.delete_remote(name, final, remote)
        return "copied"

    def delete_remote(self, name, local_copy, remote):
        """rm -- <remote>/<name> on the server, only for a valid name whose laptop copy hashes to the server's."""
        if not NAME_RE.fullmatch(name):
            raise ValueError(f"refusing to delete {name!r}: not an hour file name")
        if not same(local_copy, remote):
            self.kept += 1
            self.errors += 1
            return self.log(f"not deleting {name}: the laptop's copy no longer matches")
        rc, out = self.ssh(f"rm -- {quote(self.remote + '/' + name)}")
        if rc == 0:
            self.deleted += 1
            return self.log(f"deleted {name} on the server")
        self.kept += 1
        self.errors += 1
        self.log(f"rm of {name} on the server failed (rc {rc}): {tail(out)}; the next run retries")

    # -- the recorder's logs and status.json --------------------------------------------------------------------
    def prefix_command(self, name, length):
        """The server log's size, then the SHA-256 of its first `length` bytes (the laptop copy's length), at the
        lowest priority. Reads no more than `length` bytes of it."""
        assert name in APPEND_ONLY, name
        f = quote(name)
        return (f"cd {quote(self.remote)} && stat -c %s -- {f} && "
                f"{LOW} head -c {int(length)} -- {f} | {LOW} sha256sum")

    def tail_command(self, name, start, count):
        """`count` bytes of the server's log from byte `start` (counting from 0), as base64, so the bytes come
        through ssh's text output exactly. head -c stops at the size the check gave, even if the log grew since."""
        assert name in APPEND_ONLY, name
        return (f"cd {quote(self.remote)} && {LOW} tail -c +{int(start) + 1} -- {quote(name)} | "
                f"head -c {int(count)} | base64")

    def newest_reset(self, name):
        """The highest n of the laptop's <stem>.reset<n>.jsonl files for this log, or 0 when there are none."""
        stem, ext = os.path.splitext(name)
        pattern = re.compile(re.escape(stem) + r"\.reset(\d+)" + re.escape(ext))
        found = [int(m.group(1)) for f in os.listdir(self.local) if (m := pattern.fullmatch(f))]
        return max(found, default=0)

    def log_file(self, name):
        """Brings the laptop's copy of one of the recorder's logs up to the server's, copying only the bytes it lacks.

        The laptop's copy is <name>, or after a reset the newest <stem>.reset<n>.jsonl. The server tells its log's
        size and the SHA-256 of its first L bytes, L being the laptop copy's length. Equal to the laptop copy's own
        SHA-256: the server's is the laptop's plus new lines, and only those are fetched and appended. Not equal, or
        the server's shorter: the server's was reset or rewritten, so the laptop's is never touched, and the server's
        whole log goes to the next <stem>.reset<n>.jsonl instead."""
        target = self.newest_reset(name)
        target = reset_name(name, target) if target else name
        path = os.path.join(self.local, target)
        have = os.path.getsize(path) if os.path.isfile(path) else 0
        mine = file_sha(path) if have else None
        self.clear_of_bot(f"checking {name}")
        rc, out = self.ssh(self.prefix_command(name, have), timeout=SMALL_TIMEOUT)
        answer = parse_prefix(out) if rc == 0 else None
        if answer is None:
            return self.log(f"check of {name} failed (rc {rc}): {tail(out, 200)}")
        size, theirs = answer
        if have == 0:                              # nothing on the laptop yet: the whole log
            return self.copy_small(name, target, timeout=SMALL_TIMEOUT + size / COPY_FLOOR)
        if size >= have and theirs == mine:
            if size > have:
                self.add_tail(name, target, have, size - have)
            return
        new = reset_name(name, self.newest_reset(name) + 1)
        self.errors += 1
        self.log(f"WARNING: the server's {name} ({size} bytes) does not start with the laptop's {target} "
                 f"({have} bytes): the server's folder was reset or the file rewritten. The laptop's {target} is "
                 f"left as it is; the server's whole {name} goes to {new}, and later runs add to that one")
        self.copy_small(name, new, timeout=SMALL_TIMEOUT + size / COPY_FLOOR)

    def add_tail(self, name, target, have, count):
        """Appends the server log's bytes from `have` on, `count` of them, to the laptop's `target`, through a .part
        whose length is checked first."""
        final = os.path.join(self.local, target)
        part = final + ".part"
        self.clear_of_bot(f"copying the end of {name}")
        rc, out = self.ssh(self.tail_command(name, have, count), timeout=SMALL_TIMEOUT + count / COPY_FLOOR)
        data = decode_tail(out) if rc == 0 else None
        if data is None:
            self.errors += 1
            return self.log(f"copy of the end of {name} failed (rc {rc}): {tail(out, 200)}; the next run tries again")
        with open(part, "wb") as f:
            f.write(data)
        got = os.path.getsize(part)
        if got != count:
            self.remove_part(part)
            self.errors += 1
            return self.log(f"the end of {name} came as {got} bytes, not {count}: not added to {target}, the next "
                            f"run tries again")
        with open(part, "rb") as src, open(final, "ab") as dst:
            shutil.copyfileobj(src, dst)
        self.remove_part(part)
        self.log(f"added {count} new bytes of {name} to {target} (now {have + count} bytes)")

    def copy_small(self, name, target, timeout):
        """scp of the server's whole `name` to the laptop's `target`, through <target>.part and a rename. status.json
        (a snapshot) replaces the laptop's; a log only goes where the laptop has no bytes of it."""
        final = os.path.join(self.local, target)
        part = final + ".part"
        self.clear_of_bot(f"copying {name}")
        rc, out = self.scp(name, part, timeout=timeout)
        if rc != 0:
            self.remove_part(part)
            return self.log(f"copy of {name} failed (rc {rc}): {tail(out, 200)}")
        if name in APPEND_ONLY and os.path.isfile(final) and os.path.getsize(final) > 0:
            self.remove_part(part)                 # appeared since the check: never overwrite a log
            self.errors += 1
            return self.log(f"{target} appeared during the copy of {name}: copy removed, the laptop's left alone")
        os.replace(part, final)
        if name in APPEND_ONLY:
            self.log(f"copied {name} whole to {target} ({os.path.getsize(final)} bytes)")


# ---------------------------------------------------------------------------------------------------------------
# command line


def parse_args(argv):
    ap = argparse.ArgumentParser(description="Copy the maker shadow recorder's closed hour files to the laptop.")
    ap.add_argument("--host", default=HOST)
    ap.add_argument("--key", default=KEY)
    ap.add_argument("--remote", default=REMOTE, help="the recorder's data folder on the server")
    ap.add_argument("--local", default=LOCAL, help="the laptop's data folder (pull.log and pull.lock go here)")
    ap.add_argument("--ssh", default=SSH)
    ap.add_argument("--scp", default=SCP)
    return ap.parse_args(argv)


def main(argv=None, run=run_process):
    a = parse_args(sys.argv[1:] if argv is None else argv)
    problem = check_config(a.host, a.remote)
    if problem:
        try:
            os.makedirs(a.local, exist_ok=True)
            with open(os.path.join(a.local, "pull.log"), "a", encoding="utf-8") as f:
                f.write(f"{datetime.now().astimezone().isoformat(timespec='seconds')} [{os.getpid()}] {problem}\n")
        except OSError:
            pass
        if sys.stderr:                           # None under pythonw
            print(problem, file=sys.stderr)
        return 2
    return Pull(host=a.host, key=a.key, remote=a.remote, local=a.local, ssh=a.ssh, scp=a.scp, run=run).once()


if __name__ == "__main__":
    sys.exit(main())
