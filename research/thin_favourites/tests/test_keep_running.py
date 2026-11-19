"""keep_running.py: the watchdog the scheduled task runs every 5 minutes, at logon and on wake.

Offline: PowerShell is faked (keep_running.ps monkeypatched). The contract:

- decide(now, is_running) is "over" from END on, else "running" or "start".
- running() is True when any python.exe/pythonw.exe command line holds "thin_books.py record".
- command(now, python) runs thin_books.py record for the days left to END, through cmd.exe so its output and
  errors go to data/thin_books.out.log and .err.log, as the first starts did.
- main() starts the recorder (through WMI, so it isn't tied to the watchdog) and logs that it did, only on "start".

    python -m pytest research/thin_favourites/tests -q
"""
import types

import pytest

import keep_running as kr

END = kr.END


def test_decide():
    assert kr.decide(END - 3600, False) == "start"
    assert kr.decide(END - 3600, True) == "running"
    assert kr.decide(END, False) == "over"
    assert kr.decide(END + 10, True) == "over"


def fake_ps(monkeypatch, out):
    calls = []

    def ps(script):
        calls.append(script)
        return types.SimpleNamespace(stdout=out, returncode=0)
    monkeypatch.setattr(kr, "ps", ps)
    return calls


def test_running_reads_command_lines(monkeypatch):
    fake_ps(monkeypatch, 'C:\\py\\python.exe  thin_books.py record 13.17\r\nC:\\py\\python.exe other.py\r\n')
    assert kr.running() is True
    fake_ps(monkeypatch, 'C:\\py\\python.exe other.py\r\n\r\n')
    assert kr.running() is False
    fake_ps(monkeypatch, "")
    assert kr.running() is False


def test_command_runs_to_the_same_end():
    c = kr.command(END - 2 * 86400, r"C:\py\python.exe")
    assert c.startswith('cmd.exe /c ""C:\\py\\python.exe" thin_books.py record 2.0 ')
    assert ">> data\\thin_books.out.log 2>> data\\thin_books.err.log" in c


def test_main_starts_only_when_needed(monkeypatch, tmp_path):
    started, logged = [], []
    monkeypatch.setattr(kr, "start", lambda cmd: started.append(cmd) or 0)
    monkeypatch.setattr(kr, "log", lambda folder, t, msg: logged.append(msg))
    monkeypatch.setattr(kr.time, "time", lambda: END - 86400)

    monkeypatch.setattr(kr, "running", lambda: True)
    kr.main()
    assert started == [] and logged == []

    monkeypatch.setattr(kr, "running", lambda: False)
    kr.main()
    assert len(started) == 1 and "record 1.0 " in started[0]
    assert len(logged) == 1 and "restarted" in logged[0]

    started.clear(), logged.clear()
    monkeypatch.setattr(kr.time, "time", lambda: END + 1)
    kr.main()
    assert started == [] and logged == []


def test_main_logs_a_failed_start(monkeypatch):
    logged = []
    monkeypatch.setattr(kr, "start", lambda cmd: 9)
    monkeypatch.setattr(kr, "log", lambda folder, t, msg: logged.append(msg))
    monkeypatch.setattr(kr, "running", lambda: False)
    monkeypatch.setattr(kr.time, "time", lambda: END - 86400)
    kr.main()
    assert len(logged) == 1 and "failed" in logged[0] and "9" in logged[0]
