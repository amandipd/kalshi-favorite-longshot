"""Watchdog for thin_books.py: if the recorder isn't running and its end hasn't come, start it again to the same end.

A Windows machine going to sleep kills the recorder (twice by 27 Oct, both at the moment of sleep). A Windows
scheduled task ran this with pythonw every 5 minutes, at logon and on wake, so a gap lasts
minutes, not hours. It starts the recorder through WMI, as the hand restarts did, so the recorder isn't tied to this
short-lived process. Restarts are logged to data/thin_books.log; a run that finds the recorder alive writes nothing.
From END on it does nothing, and the task's triggers end the next day.

    pythonw keep_running.py
"""
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

from thin_books import DATA, log, stamp

END = datetime(2026, 11, 9, 21, 42, 55, tzinfo=timezone.utc).timestamp()   # the end the recorder was first given
HERE = os.path.dirname(os.path.abspath(__file__))
NO_WINDOW = 0x08000000   # CREATE_NO_WINDOW: PowerShell runs without flashing a console


def ps(script):
    return subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True,
                          text=True, timeout=60, creationflags=NO_WINDOW)


def decide(now, is_running):
    if now >= END:
        return "over"
    return "running" if is_running else "start"


def running():
    out = ps("Get-CimInstance Win32_Process -Filter \"Name='python.exe' or Name='pythonw.exe'\""
             " | ForEach-Object { $_.CommandLine }").stdout
    return any("thin_books.py record" in line for line in out.splitlines())


def command(now, python):
    days = round((END - now) / 86400, 5)
    return (f'cmd.exe /c ""{python}" thin_books.py record {days}'
            ' >> data\\thin_books.out.log 2>> data\\thin_books.err.log"')


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
    if decide(now, running()) != "start":
        return
    python = os.path.join(os.path.dirname(sys.executable), "python.exe")
    code = start(command(now, python))
    folder = os.path.join(HERE, DATA)
    if code == 0:
        log(folder, now, f"watchdog: the recorder wasn't running; restarted it to {stamp(END)}")
    else:
        log(folder, now, f"watchdog: the recorder wasn't running and the restart failed (WMI returned {code})")


if __name__ == "__main__":
    main()
