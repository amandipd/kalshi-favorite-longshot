"""The findings dashboard: one page of the study's key statistical results.

Serves dashboard/index.html and /api/findings, which returns two files exactly as they are on disk:

    reports/summary.json         written by `make analyze`
    reports/replication.json     written by `make replicate`

Nothing is computed here, so the page cannot disagree with the printed report. A file that has not been built
comes back as null with the command that builds it, and the page says so instead of failing.

    python dashboard/server.py               # http://localhost:8080
    python dashboard/server.py --port 9000
"""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PAGE = HERE / "index.html"
SOURCES = {
    "study": ROOT / "reports" / "summary.json",
    "replication": ROOT / "reports" / "replication.json",
}
BUILD = {
    "study": "make analyze",
    "replication": "make replicate-data && make replicate",
}
HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    # The page is self-contained: no script, style or font from anywhere else.
    "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; "
                               "style-src 'self' 'unsafe-inline'; img-src 'self' data:",
}


def findings(sources=None):
    """{"study": ..., "replication": ..., "missing": {name: command that builds it}}."""
    out = {"missing": {}}
    for name, path in (sources or SOURCES).items():
        try:
            out[name] = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            out[name] = None
            out["missing"][name] = BUILD.get(name, "")
    return out


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        route = self.path.split("?", 1)[0]
        if route in ("/", "/index.html"):
            body, kind = PAGE.read_bytes(), "text/html; charset=utf-8"
        elif route == "/api/findings":
            body, kind = json.dumps(findings()).encode("utf-8"), "application/json"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        for key, value in HEADERS.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args(argv)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Findings dashboard at http://localhost:{server.server_address[1]}  (Ctrl+C to stop)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
