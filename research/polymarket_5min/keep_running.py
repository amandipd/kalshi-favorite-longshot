"""Watchdog for forward.py: if the recorder isn't running and it hasn't finished, start it again.

A Windows machine going to sleep kills a recorder (research/thin_favourites learned this in Oct). A Windows scheduled
task ran this with pythonw every 5 minutes, at logon and on wake. It starts the recorder through WMI, so the recorder
isn't tied to this short-lived process or to the console that launched it. Restarts are
logged to forward.log; a run that finds the recorder alive writes nothing. Once forward_done.json exists, or from
HARD_END on, it does nothing, and the task's triggers end the next day.

    pythonw keep_running.py
"""
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from forward import DONE, log  # noqa: E402

HARD_END = datetime(2026, 11, 21, tzinfo=timezone.utc).timestamp()   # 7 days after the start, plus a margin
NO_WINDOW = 0x08000000


def ps(script):
    return subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True,
                          text=True, timeout=60, creationflags=NO_WINDOW)


def decide(now, is_running, done):
    if done or now >= HARD_END:
        return "over"
    return "running" if is_running else "start"


def running():
    out = ps("Get-CimInstance Win32_Process -Filter \"Name='python.exe' or Name='pythonw.exe'\""
             " | ForEach-Object { $_.CommandLine }").stdout
    return any("forward.py record" in line for line in out.splitlines())


def start(cmd):
    """Start `cmd` through WMI with its window hidden; WMI's return value (0 is success)."""
    out = ps("$s = New-CimInstance -ClassName Win32_ProcessStartup -ClientOnly -Property @{ShowWindow=[uint16]0}; "
             f"$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{{CommandLine='{cmd}';"
             f" CurrentDirectory='{HERE}'; ProcessStartupInformation=$s}}; $r.ReturnValue").stdout
    try:
        return int(out.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return -1


def main():
    now = time.time()
    if decide(now, running(), os.path.exists(os.path.join(HERE, DONE))) != "start":
        return
    python = os.path.join(os.path.dirname(sys.executable), "python.exe")
    code = start(f'cmd.exe /c ""{python}" forward.py record >> forward.out.log 2>> forward.err.log"')
    log("watchdog: the recorder wasn't running; restarted it" if code == 0
        else f"watchdog: the recorder wasn't running and the restart failed (WMI returned {code})")


if __name__ == "__main__":
    main()
