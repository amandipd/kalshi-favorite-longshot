"""A small client for Kalshi's Trade API v2: public market data, and signed account calls.

Signing follows docs.kalshi.com/getting_started/api_keys: every account request carries the key ID,
a millisecond timestamp, and a signature of timestamp + method + path (with the /trade-api/v2
prefix, without the query string), RSA-PSS with SHA-256 or Ed25519, base64-encoded.
"""
import base64
import time
from urllib.parse import urlparse

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, padding

# prod: Kalshi's recommended base URL (docs.kalshi.com/getting_started/api_environments); its load balancer is in AWS
# us-east-2 (Ohio). Requests are signed on the path only, so the host doesn't change the signature.
HOSTS = {
    "prod": "https://external-api.kalshi.com/trade-api/v2",
    "demo": "https://demo-api.kalshi.co/trade-api/v2",
}
ORDER_TIMEOUT = (3.05, 5)   # an order or a cancel: seconds to connect, seconds for Kalshi's answer


def load_key(path):
    with open(path, "rb") as fh:
        return serialization.load_pem_private_key(fh.read(), password=None)


def sign(key, text):
    msg = text.encode("utf-8")
    if isinstance(key, ed25519.Ed25519PrivateKey):
        sig = key.sign(msg)
    else:
        sig = key.sign(msg, padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
                       hashes.SHA256())
    return base64.b64encode(sig).decode("ascii")


class Kalshi:
    def __init__(self, env="demo", key_id=None, key_path=None, timeout=10, order_timeout=ORDER_TIMEOUT):
        self.env = env
        self.base = HOSTS[env]
        self.prefix = urlparse(self.base).path  # "/trade-api/v2": part of the signed path
        self.key_id = key_id
        self.key = load_key(key_path) if key_path else None
        self.timeout = timeout
        # Orders and cancels wait less: (seconds to connect, seconds for the answer). An order that took longer
        # would reach the book after the prices it was sized on; the bot then reads its fills to see what happened.
        self.order_timeout = order_timeout
        self.http = requests.Session()
        self.last_error = None  # what Kalshi said about the last request it refused

    @property
    def authed(self):
        return bool(self.key_id and self.key)

    def headers(self, method, path, now_ms=None):
        stamp = str(now_ms if now_ms is not None else int(time.time() * 1000))
        return {"KALSHI-ACCESS-KEY": self.key_id, "KALSHI-ACCESS-TIMESTAMP": stamp,
                "KALSHI-ACCESS-SIGNATURE": sign(self.key, stamp + method + self.prefix + path)}

    def get(self, path, params=None, auth=False):
        """GET, retried on rate limits, server errors and network errors; None if it keeps failing.
        A refusal (bad key, wrong environment, not found) isn't retried: last_error says why."""
        for attempt in range(4):
            try:
                r = self.http.get(self.base + path, params=params, timeout=self.timeout,
                                  headers=self.headers("GET", path) if auth else None)
                if r.status_code == 429 or r.status_code >= 500:
                    self.last_error = f"HTTP {r.status_code}"
                    time.sleep(1 + attempt)
                    continue
                if r.status_code >= 400:
                    self.last_error = f"HTTP {r.status_code}: {r.text[:300]}"
                    return None
                return r.json()
            except requests.RequestException as e:
                self.last_error = f"network error: {e}"
                time.sleep(1 + attempt)
        return None

    def post(self, path, body, timeout=None):
        """One signed POST, never retried: a retry could place the same order twice. (status, body)."""
        r = self.http.post(self.base + path, json=body, headers=self.headers("POST", path), timeout=timeout or self.timeout)
        return self.answer(r)

    def delete(self, path, params=None):
        """One signed DELETE, with the order timeout. (status, body); a 204 has an empty body."""
        r = self.http.delete(self.base + path, params=params, headers=self.headers("DELETE", path), timeout=self.order_timeout)
        return self.answer(r)

    @staticmethod
    def answer(r):
        try:
            return r.status_code, r.json()
        except ValueError:
            return r.status_code, r.text

    # public market data
    def series(self):
        return self.get("/series")

    def markets(self, **params):
        return self.get("/markets", params)

    def orderbook(self, ticker):
        return self.get(f"/markets/{ticker}/orderbook")

    def exchange_status(self):
        return self.get("/exchange/status")

    def candlesticks(self, tickers, start_ts, end_ts):
        """One-minute candles for markets that share a window, in one request: each minute's closing YES bid and ask."""
        return self.get("/markets/candlesticks", {"market_tickers": ",".join(tickers), "start_ts": int(start_ts),
                                                  "end_ts": int(end_ts), "period_interval": 1})

    # the account
    def balance(self):
        return self.get("/portfolio/balance", auth=True)

    def positions(self, **params):
        return self.get("/portfolio/positions", params, auth=True)

    def fills(self, **params):
        return self.get("/portfolio/fills", params, auth=True)

    def list_orders(self, **params):
        return self.get("/portfolio/orders", params, auth=True)

    def order_history(self, min_ts, cursor=None):
        """Every order placed since min_ts, whatever its status, 200 a page; cursor: the next page."""
        return self.get("/portfolio/orders", {"min_ts": int(min_ts), "limit": 200, **({"cursor": cursor} if cursor else {})},
                        auth=True)

    def create_order(self, body):
        return self.post("/portfolio/events/orders", body, timeout=self.order_timeout)

    def cancel_order(self, order_id, ticker):
        """Cancel one order (V2). The ticker lets Kalshi route it to the market's section: an order ID alone can't."""
        return self.delete(f"/portfolio/events/orders/{order_id}", {"market_ticker": ticker})

    def transfer(self, dollars, from_section, to_section):
        """Move cash between sections (exchange indexes) of the same account. Kalshi keeps each section's
        cash apart, and an order can only use its market's section. Processed asynchronously."""
        return self.post("/portfolio/intra_exchange_instance_transfer", {
            "source": "event_contract", "destination": "event_contract",
            "amount": int(round(dollars * 10000)),  # centicents
            "source_exchange_shard": from_section, "destination_exchange_shard": to_section})
