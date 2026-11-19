"""The Kalshi client: key loading, signing, retries, and that an order is never sent twice.
Nothing here touches the network: the HTTP session is a stub returning real requests.Response objects.

    python -m pytest tests/test_kalshi.py -q
"""
import base64
import json

import pytest
import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, padding, rsa

from kalshi_bot import kalshi
from kalshi_bot.kalshi import Kalshi

PSS = padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH)


def resp(status=200, body=None, raw=None):
    r = requests.Response()
    r.status_code = status
    r.encoding = "utf-8"
    r._content = raw if raw is not None else json.dumps(body).encode()
    return r


class Http:
    """Plays back responses (or raises exceptions) in order, and remembers every call."""

    def __init__(self, *script):
        self.script, self.calls = list(script), []

    def _next(self):
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def get(self, url, params=None, timeout=None, headers=None):
        self.calls.append({"method": "GET", "url": url, "params": params, "timeout": timeout, "headers": headers})
        return self._next()

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append({"method": "POST", "url": url, "json": json, "timeout": timeout, "headers": headers})
        return self._next()

    def delete(self, url, params=None, headers=None, timeout=None):
        self.calls.append({"method": "DELETE", "url": url, "params": params, "timeout": timeout, "headers": headers})
        return self._next()


@pytest.fixture
def sleeps(monkeypatch):
    slept = []
    monkeypatch.setattr(kalshi.time, "sleep", lambda s: slept.append(s))
    return slept


def client(*script, env="demo", key=None):
    k = Kalshi(env)
    k.http = Http(*script)
    if key is not None:
        k.key_id, k.key = "key-id", key
    return k


@pytest.fixture
def rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


# ------------------------------------------------------------------ hosts and keys
def test_hosts_and_the_signed_prefix():
    assert Kalshi("prod").base == "https://external-api.kalshi.com/trade-api/v2"   # Kalshi's recommended base URL
    assert Kalshi("demo").base == "https://demo-api.kalshi.co/trade-api/v2"
    assert Kalshi("prod").prefix == Kalshi("demo").prefix == "/trade-api/v2"


def test_an_unknown_environment_is_refused():
    with pytest.raises(KeyError):
        Kalshi("staging")


def pem(key, encrypted=False):
    enc = serialization.BestAvailableEncryption(b"pw") if encrypted else serialization.NoEncryption()
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, enc)


def test_load_key_reads_rsa_and_ed25519_pem_files(tmp_path, rsa_key):
    (tmp_path / "rsa.pem").write_bytes(pem(rsa_key))
    ed = ed25519.Ed25519PrivateKey.generate()
    (tmp_path / "ed.pem").write_bytes(pem(ed))
    assert isinstance(kalshi.load_key(str(tmp_path / "rsa.pem")), rsa.RSAPrivateKey)
    assert isinstance(kalshi.load_key(str(tmp_path / "ed.pem")), ed25519.Ed25519PrivateKey)


def test_load_key_fails_loudly_on_a_bad_file(tmp_path, rsa_key):
    (tmp_path / "junk.pem").write_text("not a key")
    with pytest.raises(ValueError):
        kalshi.load_key(str(tmp_path / "junk.pem"))
    with pytest.raises(FileNotFoundError):
        kalshi.load_key(str(tmp_path / "missing.pem"))
    (tmp_path / "locked.pem").write_bytes(pem(rsa_key, encrypted=True))
    with pytest.raises(TypeError):  # a password-protected key isn't supported
        kalshi.load_key(str(tmp_path / "locked.pem"))


def test_the_client_loads_its_key_and_knows_when_it_can_sign(tmp_path, rsa_key):
    (tmp_path / "k.pem").write_bytes(pem(rsa_key))
    assert Kalshi("demo", "id", str(tmp_path / "k.pem")).authed
    assert not Kalshi("demo").authed                                  # no key at all
    assert not Kalshi("demo", key_id="id").authed                     # an ID without a key file
    assert not Kalshi("demo", key_path=str(tmp_path / "k.pem")).authed  # a key without an ID


# ------------------------------------------------------------------ signing
def test_sign_verifies_for_both_key_types(rsa_key):
    rsa_sig = base64.b64decode(kalshi.sign(rsa_key, "hello"))
    rsa_key.public_key().verify(rsa_sig, b"hello", PSS, hashes.SHA256())
    ed = ed25519.Ed25519PrivateKey.generate()
    ed.public_key().verify(base64.b64decode(kalshi.sign(ed, "hello")), b"hello")
    with pytest.raises(Exception):  # a signature for another message doesn't verify
        ed.public_key().verify(base64.b64decode(kalshi.sign(ed, "hello")), b"goodbye")


def test_headers_use_the_clock_when_no_time_is_given(monkeypatch):
    monkeypatch.setattr(kalshi.time, "time", lambda: 1790000000.123)
    k = client(key=ed25519.Ed25519PrivateKey.generate())
    h = k.headers("GET", "/portfolio/balance")
    assert h["KALSHI-ACCESS-TIMESTAMP"] == "1790000000123"
    assert h["KALSHI-ACCESS-KEY"] == "key-id"


def test_the_query_string_is_never_part_of_the_signed_path():
    """Kalshi signs the path without its query, so params go in `params`, not the path."""
    ed = ed25519.Ed25519PrivateKey.generate()
    k = client(resp(200, {}), key=ed)
    k.positions(count_filter="position")
    call = k.http.calls[0]
    ed.public_key().verify(base64.b64decode(call["headers"]["KALSHI-ACCESS-SIGNATURE"]),
                           (call["headers"]["KALSHI-ACCESS-TIMESTAMP"] + "GET/trade-api/v2/portfolio/positions").encode())
    assert call["params"] == {"count_filter": "position"} and "?" not in call["url"]


# ------------------------------------------------------------------ GET
def test_get_returns_the_json_and_passes_params_and_timeout():
    k = client(resp(200, {"ok": 1}))
    assert k.get("/x", {"a": 1}) == {"ok": 1}
    call = k.http.calls[0]
    assert call["url"] == k.base + "/x" and call["params"] == {"a": 1} and call["timeout"] == 10
    assert call["headers"] is None  # public data isn't signed


def test_get_signs_account_calls(rsa_key):
    k = client(resp(200, {}), key=rsa_key)
    k.get("/portfolio/balance", auth=True)
    assert set(k.http.calls[0]["headers"]) == {"KALSHI-ACCESS-KEY", "KALSHI-ACCESS-TIMESTAMP", "KALSHI-ACCESS-SIGNATURE"}


@pytest.mark.parametrize("status", [429, 500, 502, 503])
def test_get_retries_rate_limits_and_server_errors(status, sleeps):
    k = client(resp(status, raw=b"busy"), resp(status, raw=b"busy"), resp(200, {"ok": 1}))
    assert k.get("/x") == {"ok": 1}
    assert len(k.http.calls) == 3 and sleeps == [1, 2]  # it backs off a little longer each time


def test_get_gives_up_after_four_tries(sleeps):
    k = client(*[resp(503, raw=b"down")] * 4)
    assert k.get("/x") is None
    assert len(k.http.calls) == 4 and k.last_error == "HTTP 503"
    assert sleeps[:3] == [1, 2, 3]


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_get_doesnt_retry_a_refusal_and_says_why(status, sleeps):
    k = client(resp(status, raw=b'{"error": "nope"}'))
    assert k.get("/x") is None
    assert len(k.http.calls) == 1 and sleeps == []
    assert k.last_error == f'HTTP {status}: {{"error": "nope"}}'


def test_a_long_refusal_is_cut_to_300_characters():
    k = client(resp(400, raw=b"x" * 5000))
    k.get("/x")
    assert len(k.last_error) == len("HTTP 400: ") + 300


def test_get_retries_network_errors_then_reports_them(sleeps):
    k = client(requests.ConnectionError("reset"), requests.Timeout("slow"), resp(200, {"ok": 1}))
    assert k.get("/x") == {"ok": 1} and len(k.http.calls) == 3
    dead = client(*[requests.ConnectionError("offline")] * 4)
    assert dead.get("/x") is None and dead.last_error == "network error: offline"


def test_a_200_that_isnt_json_is_retried_not_crashed(sleeps):
    k = client(resp(200, raw=b"<html>maintenance</html>"), resp(200, {"ok": 1}))
    assert k.get("/x") == {"ok": 1}
    assert len(k.http.calls) == 2


# ------------------------------------------------------------------ POST
def test_post_signs_sends_json_and_returns_status_and_body(rsa_key):
    k = client(resp(201, {"order_id": "o1"}), key=rsa_key)
    assert k.post("/portfolio/events/orders", {"a": 1}) == (201, {"order_id": "o1"})
    call = k.http.calls[0]
    assert call["json"] == {"a": 1} and call["timeout"] == 10 and call["url"].endswith("/portfolio/events/orders")
    rsa_key.public_key().verify(base64.b64decode(call["headers"]["KALSHI-ACCESS-SIGNATURE"]),
                                (call["headers"]["KALSHI-ACCESS-TIMESTAMP"] + "POST/trade-api/v2/portfolio/events/orders").encode(),
                                PSS, hashes.SHA256())


def test_post_returns_the_text_when_the_body_isnt_json(rsa_key):
    assert client(resp(502, raw=b"bad gateway"), key=rsa_key).post("/p", {}) == (502, "bad gateway")


@pytest.mark.parametrize("status", [429, 500, 503])
def test_post_is_never_retried_whatever_comes_back(status, sleeps, rsa_key):
    k = client(resp(status, {"error": "x"}), resp(201, {"order_id": "second"}), key=rsa_key)
    assert k.post("/p", {}) == (status, {"error": "x"})
    assert len(k.http.calls) == 1 and sleeps == []


def test_post_lets_a_network_error_out_so_the_bot_can_check_for_a_fill(rsa_key):
    k = client(requests.ConnectionError("dropped"), resp(201, {}), key=rsa_key)
    with pytest.raises(requests.ConnectionError):
        k.post("/p", {})
    assert len(k.http.calls) == 1


# ------------------------------------------------------------------ the endpoints
@pytest.mark.parametrize("call, path, params, signed", [
    (lambda k: k.series(), "/series", None, False),
    (lambda k: k.markets(series_ticker="KXBTC15M", status="open"), "/markets", {"series_ticker": "KXBTC15M", "status": "open"}, False),
    (lambda k: k.orderbook("KXBTC15M-X"), "/markets/KXBTC15M-X/orderbook", None, False),
    (lambda k: k.exchange_status(), "/exchange/status", None, False),
    (lambda k: k.balance(), "/portfolio/balance", None, True),
    (lambda k: k.positions(count_filter="position"), "/portfolio/positions", {"count_filter": "position"}, True),
    (lambda k: k.fills(order_id="o1", limit=100), "/portfolio/fills", {"order_id": "o1", "limit": 100}, True),
])
def test_each_read_hits_its_path_and_signs_only_account_calls(call, path, params, signed, rsa_key):
    k = client(resp(200, {"ok": 1}), key=rsa_key)
    assert call(k) == {"ok": 1}
    got = k.http.calls[0]
    assert got["url"] == k.base + path and got["params"] == params and (got["headers"] is not None) is signed


def test_create_order_posts_the_body_to_the_orders_path(rsa_key):
    k = client(resp(201, {"order_id": "o1"}), key=rsa_key)
    assert k.create_order({"ticker": "T"}) == (201, {"order_id": "o1"})
    assert k.http.calls[0]["url"] == k.base + "/portfolio/events/orders" and k.http.calls[0]["json"] == {"ticker": "T"}


# ------------------------------------------------------------------ how long an order may take
def test_an_order_waits_3_seconds_to_connect_and_5_for_the_answer_not_the_reads_10(rsa_key):
    k = client(resp(201, {"order_id": "o1"}), resp(200, {}), key=rsa_key)
    k.create_order({"ticker": "T"})
    k.balance()
    assert k.http.calls[0]["timeout"] == (3.05, 5) and k.http.calls[1]["timeout"] == 10


def test_an_order_that_times_out_isnt_retried_and_the_timeout_reaches_the_bot(rsa_key):
    k = client(requests.ReadTimeout("no answer in 5s"), resp(201, {}), key=rsa_key)
    with pytest.raises(requests.ReadTimeout):
        k.create_order({"ticker": "T"})
    assert len(k.http.calls) == 1


def test_the_order_timeout_can_be_set():
    assert Kalshi("demo", order_timeout=(1, 2)).order_timeout == (1, 2)


# ------------------------------------------------------------------ the calls the bot's safeguards use
def test_candlesticks_asks_for_one_minute_candles_of_every_market_at_once(rsa_key):
    k = client(resp(200, {"markets": []}), key=rsa_key)
    assert k.candlesticks(["A-1", "B-1"], 1790000000.0, 1790000480.9) == {"markets": []}
    call = k.http.calls[0]
    assert call["url"] == k.base + "/markets/candlesticks" and call["headers"] is None   # public: no signature
    assert call["params"] == {"market_tickers": "A-1,B-1", "start_ts": 1790000000, "end_ts": 1790000480, "period_interval": 1}


def test_list_orders_is_a_signed_read(rsa_key):
    k = client(resp(200, {"orders": []}), key=rsa_key)
    assert k.list_orders(status="resting", limit=200) == {"orders": []}
    call = k.http.calls[0]
    assert call["url"] == k.base + "/portfolio/orders" and call["params"] == {"status": "resting", "limit": 200}
    assert call["headers"] is not None


def test_cancel_order_signs_a_delete_routed_by_the_market_with_the_order_timeout(rsa_key):
    k = client(resp(200, {"order_id": "o1", "reduced_by": "3.00"}), key=rsa_key)
    assert k.cancel_order("o1", "KXBTC15M-X") == (200, {"order_id": "o1", "reduced_by": "3.00"})
    call = k.http.calls[0]
    assert call["method"] == "DELETE" and call["url"] == k.base + "/portfolio/events/orders/o1"
    assert call["params"] == {"market_ticker": "KXBTC15M-X"} and call["timeout"] == (3.05, 5)
    # the signature covers the path, not the query string
    rsa_key.public_key().verify(base64.b64decode(call["headers"]["KALSHI-ACCESS-SIGNATURE"]),
                                (call["headers"]["KALSHI-ACCESS-TIMESTAMP"] + "DELETE/trade-api/v2/portfolio/events/orders/o1").encode(),
                                PSS, hashes.SHA256())


def test_a_cancel_with_no_body_returns_the_empty_text(rsa_key):
    assert client(resp(204, raw=b""), key=rsa_key).cancel_order("o1", "T") == (204, "")


def test_a_cancel_is_sent_once_and_a_network_error_reaches_the_bot(sleeps, rsa_key):
    k = client(requests.ConnectionError("down"), resp(200, {}), key=rsa_key)
    with pytest.raises(requests.ConnectionError):
        k.cancel_order("o1", "T")
    assert len(k.http.calls) == 1 and sleeps == []


@pytest.mark.parametrize("dollars, centicents", [(100.0, 1000000), (0.01, 100), (12.34, 123400), (99.99, 999900), (0.0, 0)])
def test_transfer_amounts_are_in_centicents(dollars, centicents, rsa_key):
    k = client(resp(200, {"transfer_id": "t1"}), key=rsa_key)
    assert k.transfer(dollars, 0, 2) == (200, {"transfer_id": "t1"})
    body = k.http.calls[0]["json"]
    assert body["amount"] == centicents and isinstance(body["amount"], int)
    assert (body["source_exchange_shard"], body["destination_exchange_shard"]) == (0, 2)
    assert k.http.calls[0]["url"].endswith("/portfolio/intra_exchange_instance_transfer")


def test_order_history_reads_every_order_since_a_time_a_page_at_a_time(rsa_key):
    """What the bot checks its records against: all its orders since then, whatever their status, 200 a page."""
    k = client(resp(200, {"orders": [], "cursor": "p2"}), resp(200, {"orders": []}), key=rsa_key)
    assert k.order_history(1790000000.7) == {"orders": [], "cursor": "p2"}
    assert k.order_history(1790000000, cursor="p2") == {"orders": []}
    first, second = k.http.calls
    assert first["url"] == k.base + "/portfolio/orders" and first["headers"] is not None
    assert first["params"] == {"min_ts": 1790000000, "limit": 200}
    assert second["params"] == {"min_ts": 1790000000, "limit": 200, "cursor": "p2"}
