"""The research scripts that do their work at import time, run whole as the README runs them: `python <script>.py`.

Seven read the synthetic history (by_band_fees, check_ab, compounding, sim_real, simulate, simulate2, thin). Three
call Kalshi (backtest_70pct, check_series, fetch_30d); they run against a stand-in `requests` module, put first on
the path, that answers like Kalshi's public API from canned data, so nothing touches the network. Each run is a
separate process, in a copy of the history, and must exit cleanly and print what the script reports.
"""

from __future__ import annotations

import csv
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import RESEARCH

STUB = '''"""A stand-in for requests: Kalshi's public API from canned data, never the network."""
from datetime import datetime, timedelta, timezone


class RequestException(Exception):
    pass


class HTTPError(RequestException):
    pass


class ConnectionError(RequestException):
    pass


class adapters:
    class HTTPAdapter:
        def __init__(self, *args, **kwargs):
            pass


class Response:
    def __init__(self, status, body):
        self.status_code, self._body = status, body

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise HTTPError(str(self.status_code))


NOW = datetime.now(timezone.utc).replace(second=0, microsecond=0)


def _markets(series):
    if series in ("KXADA15M", "KXTON15M"):
        return []
    out = []
    for i in range(3):
        opened = NOW - timedelta(days=2, minutes=15 * i)
        opened -= timedelta(minutes=opened.minute % 15)
        out.append({"ticker": f"{series}-{i}", "open_time": opened.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "result": "yes" if i % 2 == 0 else "no"})
    return out


def get(url, params=None, timeout=None, **kwargs):
    params = params or {}
    if url.endswith("/markets"):
        series = params.get("series_ticker", "")
        if series == "KXSPX15M":
            return Response(404, {"error": "not found"})
        return Response(200, {"markets": _markets(series)[: params.get("limit", 200)], "cursor": ""})
    if url.endswith("/candlesticks"):
        start, end = int(params["start_ts"]), int(params["end_ts"])
        return Response(200, {"candlesticks": [{"end_period_ts": start + 60 * k, "price": {"close_dollars": "0.70"},
                                                "volume_fp": "3"} for k in range(1, (end - start) // 60 + 1)]})
    return Response(404, {})


class Session:
    def get(self, url, params=None, timeout=None, **kwargs):
        return get(url, params, timeout)

    def mount(self, *args):
        pass
'''


@pytest.fixture(scope="module")
def workdir(study, tmp_path_factory):
    """A copy of the synthetic history with snapshots_all.csv built, and the stand-in requests module."""
    study.history.write_snapshots()
    folder = tmp_path_factory.mktemp("scripts")
    for name in ("snapshots_all.csv", "quotes_30d.csv", "universe.json", "minutes_30d.csv", "minutes_new.csv",
                 "minutes_ext.csv"):
        shutil.copy(study.dir / name, folder / name)
    stub = tmp_path_factory.mktemp("stub")
    (stub / "requests.py").write_text(STUB, encoding="utf-8")
    return folder, stub


def run(script, cwd, *path):
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(map(str, (*path, RESEARCH))), PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, str(RESEARCH / script)], cwd=cwd, env=env, capture_output=True,
                       encoding="utf-8", timeout=300)
    assert r.returncode == 0, r.stderr[-2000:]
    return r.stdout


@pytest.mark.parametrize("script,expected", [
    ("by_band_fees.py", "NET EDGE BY BAND"),
    ("check_ab.py", "profit per $10 bet"),
    ("compounding.py", "Qualifying trades"),
    ("sim_real.py", "HOW MUCH WORSE IS THE REAL ASK THAN THE LAST TRADE?"),
    ("simulate.py", "Period :"),
    ("simulate2.py", "Period:"),
    ("thin.py", "Bets (ask 90-99.9c, filled at ask):"),
])
def test_each_offline_script_runs_on_the_history(workdir, script, expected):
    folder, _ = workdir
    out = run(script, folder)
    assert expected in out
    if script != "thin.py":
        assert out.startswith("Strategy:") or "Strategy:" not in (RESEARCH / script).read_text(encoding="utf-8")


def test_check_series_reports_each_candidate(workdir, tmp_path):
    _, stub = workdir
    out = run("check_series.py", tmp_path, stub)
    assert "KXBTC15M EXISTS, sample: KXBTC15M-0 yes" in out
    assert "KXADA15M no settled markets found" in out and "KXSPX15M HTTP 404" in out
    assert "Confirmed with settled data:" in out and "'KXADA15M'" not in out.split("Confirmed")[-1]


def test_backtest_70pct_finds_the_band_and_its_ev(workdir, tmp_path):
    _, stub = workdir
    out = run("backtest_70pct.py", tmp_path, stub)
    assert "Total settled markets scanned: 48" in out
    assert "Contracts found priced 0.65-0.75 at minute 8: 48" in out
    assert "Win rate (actually resolved YES): 0.6667 (32/48)" in out and "By series:" in out


def test_fetch_30d_reuses_cached_snapshots_and_fetches_the_rest(workdir, tmp_path):
    _, stub = workdir
    with (tmp_path / "snapshots_8min.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["series", "ticker", "open_time", "price_8min", "volume_8min", "resolved_yes"])
        w.writeheader()
        w.writerow({"series": "KXBTC15M", "ticker": "KXBTC15M-0", "open_time": "cached", "price_8min": "0.11",
                    "volume_8min": "0", "resolved_yes": "0"})
    out = run("fetch_30d.py", tmp_path, stub)
    with (tmp_path / "snapshots_30d.csv").open() as fh:
        rows = {r["ticker"]: r for r in csv.DictReader(fh)}
    assert len(rows) == 48 and "(1 cached)" in out
    assert rows["KXBTC15M-0"]["price_8min"] == "0.11", "a cached snapshot is reused, not refetched"
    assert rows["KXETH15M-1"]["price_8min"] == "0.7"
