"""Tests for the findings dashboard: the server's routes and the page's contract with the two reports."""

from __future__ import annotations

import json
import re
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dashboard"))
import server  # noqa: E402

PAGE = (ROOT / "dashboard" / "index.html").read_text(encoding="utf-8")
SCRIPT = PAGE[PAGE.index("<script>"):PAGE.rindex("</script>")]


def test_findings_reads_both_files_and_names_the_command_for_a_missing_one(tmp_path):
    study = tmp_path / "summary.json"
    study.write_text(json.dumps({"ok": 1}))
    out = server.findings({"study": study, "replication": tmp_path / "absent.json"})
    assert out["study"] == {"ok": 1}
    assert out["replication"] is None
    assert out["missing"] == {"replication": server.BUILD["replication"]}


def test_a_corrupt_file_counts_as_missing(tmp_path):
    bad = tmp_path / "summary.json"
    bad.write_text("{not json")
    assert server.findings({"study": bad})["missing"] == {"study": server.BUILD["study"]}


@pytest.fixture()
def running(tmp_path, monkeypatch):
    (tmp_path / "summary.json").write_text(json.dumps({"generated": "x"}))
    monkeypatch.setattr(server, "SOURCES", {"study": tmp_path / "summary.json",
                                            "replication": tmp_path / "absent.json"})
    httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def get(url):
    with urllib.request.urlopen(url, timeout=5) as r:
        return r.status, dict(r.headers), r.read()


def test_the_server_serves_the_page_and_the_findings(running):
    status, headers, body = get(running + "/")
    assert status == 200 and headers["Content-Type"].startswith("text/html")
    assert b"<title>Kalshi Calibration Findings</title>" in body
    assert headers["Cache-Control"] == "no-store" and "default-src 'self'" in headers["Content-Security-Policy"]

    status, headers, body = get(running + "/api/findings?x=1")
    data = json.loads(body)
    assert data["study"] == {"generated": "x"} and data["replication"] is None and "replication" in data["missing"]


def test_any_other_path_is_a_404(running):
    with pytest.raises(urllib.error.HTTPError) as err:
        get(running + "/../config.yaml")
    assert err.value.code == 404


def test_the_page_loads_nothing_from_anywhere_else():
    assert not re.search(r"""(src|href)\s*=\s*["']https?://""", PAGE)
    assert "@import" not in PAGE and "url(http" not in PAGE
    assert re.findall(r"fetch\(\"([^\"]+)\"", SCRIPT) == ["/api/findings"]


def test_the_page_reads_only_fields_the_reports_carry():
    """Every top-level field the script reads from either report exists in the committed report."""
    for var, path in (("S", ROOT / "reports" / "summary.json"), ("R", ROOT / "reports" / "replication.json")):
        report = json.loads(path.read_text(encoding="utf-8"))
        used = set(re.findall(rf"\b{var}\.(\w+)", SCRIPT))
        assert used, var
        assert used <= set(report), (var, used - set(report))

