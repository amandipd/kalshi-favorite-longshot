# Faster Kalshi order sending: the Python client on Windows

Scope: client-side changes only (the Python program and the Windows PC). Written 2026-10-15.

About the "local test" sources below. These are numbers measured on the bot's own Windows PC on 2026-10-15, around 18:32-18:36 UTC. Setup: Windows 11, Python 3.12.10, requests 2.32.3, urllib3 2.7.0, cryptography 50.0.1. The tests used throwaway keys and public, unsigned GET requests only. No orders were sent and nothing in `bot/` was touched. The test scripts were throwaway local scripts and are not in the repo:
- `microbench.py` (CPU costs, clocks, sleep)
- `netprobe.py` and `bookcache.py` (network round trips, CDN cache)

The local network numbers are single samples from one moment. They are a rough guide, not a benchmark.

## Ranked summary: which client-side changes save the most milliseconds?

### Takeaway
From this PC, a warm round trip to Kalshi's servers takes about 61-64 ms. That means about 30 ms one way. So the network explains only about 95 ms of the 250-320 ms delay: one book-read round trip plus one order trip. The other roughly 150-220 ms is most likely on the client side or inside Kalshi, and it has not been measured yet. Logging each step with exact timestamps comes first. After that, the biggest likely wins, in order:
1. Read all the order books in one wave.
2. Wake up on time (a precise clock plus a short busy-wait).
3. Make sure no order or book read opens a new connection.
4. Build and sign requests before the moment.
5. Switch to Ed25519 keys.
Changing the HTTP library, the JSON library, or the threading model saves at most a few ms.

### Cited findings
- **The network floor.** A warm GET for an order book (not cached by the CDN) took 61-64 ms round trip, and the first one took 82 ms. A request answered from the CloudFront edge cache took 8-12 ms. The edge was a nearby PoP. A PoP is a point of presence: a CDN server site. So the trip from the edge to Kalshi's origin server is about 50-55 ms of each round trip. Source: [Local test, netprobe.py / bookcache.py, 2026-10-15]
- **A cold connection costs more.** DNS (looking up the server's address) took 47 ms with curl. The TCP connect took 8-18 ms and the TLS handshake 6-19 ms. TLS was version 1.3, and the server offered HTTP/2 through ALPN, the step where client and server agree on a protocol. So a brand-new connection adds about 15-40 ms, plus up to about 47 ms more if the DNS answer is no longer cached. Source: [Local test, curl 8.21.0 `-w` and Python `ssl`, 2026-10-15]
- **The bot's own estimate is too high.** A bot docstring says a connection opened at the mark "would cost its TLS handshake there, about 0.1-0.25 s". The local test measured 15-40 ms for TCP+TLS to the CloudFront edge. Source: `bot/kalshi_bot/bot.py` lines 626-634 (`warm`) vs [Local test, 2026-10-15]
- **Signing.** RSA-PSS 2048 signing took 493 µs. Ed25519 signing took 28 µs. Source: [Local test, microbench.py]
- **Building a request.** `requests.Session.prepare_request` for a JSON POST took 276 µs. `json.dumps` of a small order-sized dict took 1.7 µs. Source: [Local test, microbench.py]
- **Waking up late.** `time.sleep` overshoots its target. The median overshoot was 0.44-0.56 ms. The p99 (the worst 1 in 100) was 4.5-10.5 ms, and the maximum was 13 ms. Source: [Local test, microbench.py]
- **Python 3.12's wall clock is coarse on Windows.** In Python 3.12, `time.time()` uses `GetSystemTimeAsFileTime()`, which reports a resolution of 15.625 ms. On this PC it actually ticked every 2.0 ms, because some other program had raised the timer rate. Source: [Local test, microbench.py]; Python 3.13 changes this, see [What's New in Python 3.13](https://docs.python.org/3/whatsnew/3.13.html)

### Inferences
Ranked by likely ms saved per burst. All of these are estimates.

1. **Log every phase first (saves 0 ms by itself, but finds the missing ~150-220 ms).** Record `perf_counter()` at each step: the wake-up, the halt check, the start and end of each book read, the decision, and the sign, send and answer of each order. Anchor these to the wall clock once. Python 3.12's `time.time()` is too coarse for this job.
2. **Read all books in one wave (about 60-65 ms saved for each extra wave).** `Bot.books()` reads 8 books at a time (`bot/kalshi_bot/bot.py` lines 606-611). With more than 8 books, each extra wave costs one more origin round trip. Three changes go together:
   - Use as many threads as books.
   - Raise `pool_maxsize` to at least that number with `HTTPAdapter(pool_maxsize=N)`.
   - Warm the same number of connections.
   Pitfall: with more than 10 threads on the default adapter, the extra connections are opened fresh and thrown away after use. Each one pays the 15-40 ms handshake every time. Kalshi's read rate limit also applies.
3. **Wake on time (about 0-25 ms saved, typically 5-10 ms).** The main loop does one `time.sleep(nap(...))`, where `nap` is computed from `time.time()` (`bot/kalshi_bot/bot.py` lines 1189-1196 and 1353-1362). Two things make the wake-up late:
   - The coarse clock: up to one tick, which is 15.6 ms at the default timer rate.
   - Sleep overshoot: up to about 10 ms at p99.
   The fix: sleep until about 20 ms before the target, then busy-wait. A busy-wait is a loop that keeps checking a precise clock (`perf_counter`, anchored to the wall clock) instead of sleeping. Another option is Python 3.13+, where `time.time()` has 1 µs resolution.
4. **Never open a connection during the burst (0 ms if already warm, 15-90 ms if not).** The bot already warms 8 connections in the last poll before the mark (`bot/kalshi_bot/bot.py` lines 626-634 and 1090-1092). Turn on urllib3 debug logging and check for "Starting new HTTPS connection" lines at the mark. That shows whether any book read or order still opens a fresh socket.
5. **Build and sign requests before the moment (about 1-5 ms saved, mostly on the later orders in a batch).** With the GIL, 8 threads each spending about 0.8 ms on preparing plus signing means the 8th order leaves several ms after the 1st. The GIL (global interpreter lock) lets only one thread run Python code at a time. The signature covers only the timestamp, method and path, not the body. So one signature could serve every order sent in the same millisecond. Kalshi's timestamp tolerance and replay rules are not documented, so test this on demo first.
6. **Switch to Ed25519 (about 2-4 ms saved on the last order of an 8-order batch).** Signing drops from 493 µs to 28 µs per order. In the local test, 64 RSA signs took 37 ms on 1 thread and 19 ms on 8 threads. So RSA work only partly runs in parallel.
7. **Smaller items (each under about 1-2 ms):**
   - Switching from requests to urllib3 directly, aiohttp, curl_cffi or niquests.
   - Switching to orjson.
   - Switching to asyncio or free-threaded Python.
   - HTTP/2, which saves nothing once 8 HTTP/1.1 connections are already warm.
8. **Network hygiene (0 ms on average, but it can remove rare spikes of tens of ms).** Use wired Ethernet rather than Wi-Fi. Turn off adapter power saving. Nagle's algorithm (a TCP feature that holds back small packets) is already turned off by urllib3.

### Gaps
- The local tests did not split the 250-320 ms into its parts. That needs per-phase logging inside the bot, which this research could not run.
- Kalshi's own processing time for an order POST is unknown. It may be longer than a book GET.
- CloudFront keeps its own connections from the edge to Kalshi's origin. If those have gone idle (the default idle timeout is 5 s, adjustable up to 60 s), an order may pay an extra edge-to-origin handshake. The client cannot control or see this. See [AWS CloudFront announcement, 2017](https://aws.amazon.com/about-aws/whats-new/2017/03/announcing-configure-read-timeout-and-keep-alive-timeout-values-for-your-amazon-cloudfront-custom-origins).
- Kalshi has a batch-order endpoint, which might bypass the 0.1 s spacing between orders. It is API-side and out of scope here, and its access rules were not checked.

## Per-request overhead of Python HTTP clients (requests, httpx h1/h2, aiohttp, urllib3, pycurl, curl_cffi, niquests)

### Takeaway
No neutral, recent benchmark measures per-request latency for all of these libraries against a real remote server. The numbers that exist are mostly from vendors or bloggers, and they conflict. On this PC, the client-side CPU cost per request in `requests` is well under 1 ms. A round trip is about 62 ms. So changing the library can save at most a few ms per burst.

### Cited findings
- The pyreqwest benchmark compares urllib3 (sync), aiohttp, httpx, rnet, niquests, ry, curl_cffi and pyreqwest. It ran on an Apple M3 Max with Python 3.14, using HTTP/1.1 with TLS against a local embedded server. Its latency results are only in chart images. The one text table counts garbage collections, the times Python pauses to clean up memory: pyreqwest 22-25, curl_cffi 62, aiohttp 377, urllib3 427, httpx 772, niquests 1260. The page has no date beyond "© 2026". Source: [pyreqwest benchmarks.md](https://github.com/MarkusSintonen/pyreqwest/blob/main/docs/benchmarks.md)
- A DEV Community post that promotes niquests says 1000 requests to httpbingo.org took 0.551 s with niquests, 2.087 s with httpx and 1.351 s with aiohttp. That test is about many requests over one shared session (multiplexing), not single-request latency. Source: [DEV Community, "Python's HTTP Client Gap"](https://dev.to/romdevin/pythons-http-client-gap-addressing-requests-library-stagnation-with-modern-alternatives-1a81)
- niquests features: HTTP/2 by default, HTTP/3 over QUIC where the platform supports it, multiplexed requests, thread-safe use, and drop-in compatibility (`import niquests as requests`). Its README benchmark numbers are only in a GIF. Source: [niquests README](https://github.com/jawah/niquests)
- curl_cffi claims to be "much faster than requests/httpx, on par with aiohttp/pycurl". It also offers browser TLS fingerprint impersonation. Source: [curl_cffi on PyPI](https://pypi.org/project/curl-cffi/0.6.2)
- NVIDIA's NeMo Gym team says httpcore's connection pool (used by httpx) takes O(n²) time in the number of queued requests, meaning it slows down with the square of the queue length. In September 2025 they saw about 16,000 concurrent requests hang for 40 minutes, and they switched to aiohttp. This matters only at very high concurrency, not for 20 requests. Source: [NVIDIA NeMo Gym engineering note](https://docs.nvidia.com/nemo/gym/main/infrastructure/engineering-notes/aiohttp-vs-httpx)
- httpx's docs say HTTP/2 is off by default. They describe its benefit as multiplexing: many concurrent requests over one TCP connection, "typically more useful in async contexts". They give no speed numbers, and they call HTTP/1.1 the more "battle-hardened" option. Source: [HTTPX HTTP/2 docs](https://www.python-httpx.org/http2/)
- urllib3's docs showed a banner saying it is "fundraising for HTTP/2 support". So urllib3, and therefore requests, speaks HTTP/1.1 only. Source: [urllib3 advanced usage](https://urllib3.readthedocs.io/en/stable/advanced-usage.html)
- Kalshi's API host (behind CloudFront) chose `h2` when a client offered it through ALPN. It sent no `alt-svc` header, so it does not advertise HTTP/3. Source: [Local test, netprobe.py, 2026-10-15]
- On this PC, `requests.Session.prepare_request` (build a POST with JSON and 3 headers) took 276 µs per call. Source: [Local test, microbench.py]

### Inferences
- The client-side work in `requests` is probably about 0.3 ms to prepare plus some send and parse time, under about 1 ms per request in total. Under the GIL, 8 threads do this one at a time, so a burst of 8 spends a few ms on it. A faster library might save about 1-5 ms per burst. That is small next to a 60 ms round trip.
- HTTP/2 lets one warm connection carry all 20 requests. Its real value is that only one connection needs warming. If the bot already keeps 8 warm HTTP/1.1 connections, HTTP/2 saves about 0 ms. Python HTTP/2 stacks (h2 in pure Python) also add CPU work per request.
- No library makes the network faster. The ~31 ms one-way trip to Kalshi's origin stays the same.

### Gaps
- No independent 2024-2026 benchmark gives the per-request latency (in µs or ms) of requests vs curl_cffi vs niquests vs aiohttp against a remote TLS server on Windows. The pyreqwest charts would need to be opened as images.
- pycurl was not benchmarked in any source found.

## Is one requests.Session safe and fast across threads? (pool_maxsize, pool_block)

### Takeaway
requests has never promised that a Session is thread-safe. Sharing one Session across threads is common, and it works for plain requests like these (no cookies, no redirects). Because the pool does not block by default, more threads than `pool_maxsize` (default 10) don't wait. Each extra thread opens a fresh connection and pays the full handshake, and urllib3 then throws that connection away. So keep threads ≤ pool size, and warm that many connections.

### Cited findings
- requests issue #2766, "Document threading contract for Session class". A maintainer said in 2016 that "the entire Session class needs auditing for thread safety". It was closed on May 19, 2024, with "Closing this until a separate threading issue is shown in Requests". No official guarantee was ever given. Source: [psf/requests#2766](https://github.com/psf/requests/issues/2766)
- urllib3: "This means that `maxsize` does not determine the maximum number of connections that can be open to a particular host." Extra connections beyond `maxsize` are made but "will not be saved". With `block=True`, "there can be at most `maxsize` connections open... Any new requests will block until a connection is available." Source: [urllib3 advanced usage](https://urllib3.readthedocs.io/en/stable/advanced-usage.html)
- requests' `HTTPAdapter` defaults to `pool_connections=10` and `pool_maxsize=10`. Source: [laike9m, "Requests' secret: pool_connections and pool_maxsize"](https://laike9m.com/blog/requests-secret-pool_connections-and-pool_maxsize,89/)
- The log message "Connection pool is full, discarding connection" means more connections were in use than `maxsize`. The common fix is a larger pool. Source: [yelp/threat_intel#49](https://github.com/yelp/threat_intel/issues/49)
- A new connection to Kalshi's edge cost 15-40 ms on this PC (TCP plus TLS 1.3). Source: [Local test, 2026-10-15]

### Inferences
- The bot's order send uses 8 workers on a default pool of 10, so the order connections fit. `Bot.books()` also uses 8 threads. If threads are ever raised above 10, set `HTTPAdapter(pool_maxsize=N, pool_block=False)` on the Session. Otherwise the extra connections pay 15-40 ms every time, because they are dropped after use.
- `pool_block=True` would make extra threads wait for a free connection, roughly one more round trip (~60 ms) each. That is worse for a burst.
- Thread-safety risk is low here, because the bot sends no cookies and gets no redirects. The known risks in Session are in those shared parts.

### Gaps
- No source measured lock contention inside urllib3's pool with 8-20 threads. It is likely microseconds, but that is unconfirmed.

## Threads vs asyncio for a burst of ~20; GIL; Python 3.13/3.14 free-threaded

### Takeaway
For 8-20 requests, threads and asyncio give about the same latency. The waiting is network time, and the CPU work in each request is under 1 ms. asyncio on Python 3.12 Windows has a trap: its timers run on a 15.6 ms clock. Free-threaded Python 3.14 removes the GIL, but that saves only the few ms of serialized CPU work. It also costs 5-10% in single-thread speed and needs C extensions that support it.

### Cited findings
- On Windows before Python 3.13, `time.monotonic()` used `GetTickCount64()`, which has 15.6 ms resolution. In 3.13 it switched to `QueryPerformanceCounter()`, with 1 µs resolution. Source: [What's New in Python 3.13](https://docs.python.org/3/whatsnew/3.13.html)
- A Python Discourse thread notes that the asyncio event loop's timing is still limited to a 15.625 ms clock on Windows, because the loop uses `time.monotonic()`. Faster `sleep()` doesn't fix asyncio scheduling. Source: [Discourse: Higher resolution timers on Windows?](https://discuss.python.org/t/higher-resolution-timers-on-windows/16153)
- Local: `time.monotonic` uses `GetTickCount64()` with resolution 0.015625 s, and it was seen ticking every 16.0 ms on Python 3.12.10. Source: [Local test, microbench.py]
- PEP 779 was accepted on 16 June 2025. It made the free-threaded build "officially supported" in 3.14. Reported single-thread overhead is about 5-10% in 3.14. A C extension that hasn't opted in silently turns the GIL back on. Source: [pydevtools: What is PEP 779](https://pydevtools.com/handbook/explanation/what-is-pep-779/)
- Local: 64 RSA-2048 signs took 37 ms on 1 thread and 19 ms on 8 threads. So `cryptography` RSA signing only partly runs in parallel under the GIL. Source: [Local test, microbench.py]

### Inferences
- With threads, Python code from the 8 workers still runs one piece at a time, about 0.8 ms per order (sign plus prepare). Moving signing and preparing before the mark removes most of that, and costs less than switching to free-threading.
- If asyncio is used on Python 3.12 Windows, don't trust `loop.call_at` to fire at a precise moment. Its clock ticks in 15.6 ms steps.

### Gaps
- Whether `cryptography` 50.x and `requests`/`urllib3` ship free-threaded (3.14t) Windows wheels without turning the GIL back on was not checked.

## Cost of signing: RSA-PSS 2048 vs Ed25519; base64; can signatures be precomputed?

### Takeaway
On this PC, RSA-PSS 2048 costs about 0.49 ms per signature and Ed25519 about 0.03 ms (about 18 times faster). Base64 is about 1 µs. Kalshi signs only timestamp + method + path, not the body. So every order sent in the same millisecond needs the same signature, and it could be made ahead of time. That is untested against Kalshi's timestamp and replay checks.

### Cited findings
- RSA-2048 PSS (MGF1-SHA256, salt = digest length) sign: 493 µs. Ed25519 sign: 28 µs. Base64 of a 256-byte signature: 0.87 µs. Source: [Local test, microbench.py, cryptography 50.0.1]
- A 2026 benchmark from a different stack (Rust/WASM on Apple M4) found RSA-2048 sign at 3.21 ms and Ed25519 sign at 15.1 µs. RSA is likewise orders of magnitude slower there. Source: [00f.net, "ed25519 wasm signatures", 2026-06-17](https://00f.net/2026/06/17/ed25519-wasm-signatures/)
- Kalshi signs "the timestamp, HTTP method, and path" with query parameters removed. "RSA keys use RSA-PSS with SHA-256; Ed25519 keys sign the message directly." The timestamp is "Current time in milliseconds". The docs give no tolerance window for clock skew or expiry. Source: [Kalshi docs: Quick start, authenticated requests](https://docs.kalshi.com/getting_started/quick_start_authenticated_requests)
- The bot signs inside each request call (`Kalshi.headers` → `sign`), using `time.time()` for the timestamp. Source: `bot/kalshi_bot/kalshi.py` lines 27-34 and 55-58

### Inferences
- Switching to an Ed25519 key saves about 0.47 ms per order. Across an 8-order batch, partly serialized by the GIL, the last order probably leaves about 2-4 ms sooner.
- Precomputing: before the mark, compute one signature for the planned send time, then reuse it for every POST in the batch. This takes signing off the critical path completely. The risks:
  - Kalshi's allowed skew is unknown.
  - Kalshi might reject reused or identical timestamp+signature pairs as replays.
  - A timestamp in the future might be refused.
  Test this on demo before going live.

### Gaps
- Kalshi's timestamp tolerance, and whether it accepts several requests with the same timestamp and signature, are undocumented.

## JSON cost (json vs orjson) and building requests ahead of time

### Takeaway
JSON encoding is not a bottleneck: `json.dumps` of an order body takes about 1.7 µs. Request preparation in `requests` is about 160 times more costly (276 µs). Preparing requests before the moment and sending them with `Session.send` is the useful change. orjson is not.

### Cited findings
- `json.dumps` of a small order-sized dict: 1.70 µs. orjson was not installed, so it was not measured. Source: [Local test, microbench.py]
- `Session.prepare_request(Request("POST", url, json=..., headers=...))`: 276.5 µs per call. Source: [Local test, microbench.py]

### Inferences
- orjson could save at most about 1.7 µs per order. That rounds to 0 ms.
- Build `requests.Request` objects and prepare them (`s.prepare_request`) before the mark. At the mark, only set the timestamp and signature headers (or use a precomputed signature), then call `s.send(prepped, timeout=...)`. This removes about 0.28 ms of GIL-held work per order from the critical path, about 2 ms for the last of 8.

### Gaps
- No outside benchmark was found that times requests' `Session.send` alone, apart from preparation.

## Windows timing: the 15.6 ms tick, time.sleep on 3.11+, timeBeginPeriod, busy-waiting, firing at an exact moment

### Takeaway
On Python 3.11+, `time.sleep` uses a high-resolution waitable timer. Its median overshoot here was about 0.5 ms, but rare overshoots reached 10-13 ms. On Python 3.12, `time.time()` and `time.monotonic()` are still coarse clocks (nominally 15.6 ms). The reliable way to fire at an exact moment: sleep until about 20 ms before the target, then busy-wait on `perf_counter()` anchored to the wall clock. Or move to Python 3.13+, where `time.time()` is precise.

### Cited findings
- Python 3.11 changed `time.sleep()` on Windows to use a waitable timer. bpo-45429 added `CREATE_WAITABLE_TIMER_HIGH_RESOLUTION`, going "from 1 ms in 3.10 to under 1 ms in 3.11". Sources: [CPython commit 55868f1 (bpo-45429), mirror](https://code.everydayimshuflin.com/greg/cpython/commit/55868f1a335cd3853938082a5b25cfba66563135); [CPython commit 58f8adf (bpo-21302), mirror](https://git.joshthomas.dev/mirrors/cpython/commit/58f8adfda3c2b42f654a55500e8e3a6433cb95f2)
- Python 3.13: `time.time()` now uses `GetSystemTimePreciseAsFileTime()` (1 µs) instead of `GetSystemTimeAsFileTime()` (15.6 ms). `time.monotonic()` now uses `QueryPerformanceCounter()`. Source: [What's New in Python 3.13](https://docs.python.org/3/whatsnew/3.13.html)
- Since Windows 10 version 2004, `timeBeginPeriod` no longer changes the global timer resolution. Each process gets its own. Since Windows 11, a window-owning process that is minimized, fully covered, or otherwise invisible or inaudible gets no guarantee of better than the default resolution. Source: [Microsoft Learn: timeBeginPeriod](https://learn.microsoft.com/en-us/windows/win32/api/timeapi/nf-timeapi-timebeginperiod)
- The `win-precise-time` package offers sub-millisecond sleep and needs Windows 10 version 1803 or later. Source: [win-precise-time docs](https://win-precise-time.readthedocs.io/en/latest/_sources/index.rst.txt)
- Local, Python 3.12.10: `time.time` reports `GetSystemTimeAsFileTime()` with resolution 0.015625 s, but was seen ticking every 2.0 ms. `time.monotonic` was seen ticking every 16.0 ms. `perf_counter` uses `QueryPerformanceCounter()` with resolution 1e-07 s. Source: [Local test, microbench.py]
- Local `time.sleep` overshoot (100 samples each, in ms, as median / p99 / max): sleep(0.1 ms) 0.44 / 4.48 / 4.79; sleep(1 ms) 0.55 / 10.49 / 12.23; sleep(5 ms) 0.53 / 6.41 / 7.42; sleep(20 ms) 0.56 / 8.71 / 13.09. Source: [Local test, microbench.py]
- The bot's main loop sleeps once until the next wake time, worked out from `time.time()` (`nap`). It reads `started = time.time()` after waking. Source: `bot/kalshi_bot/bot.py` lines 1189-1196 and 1353-1362. `send_all` already spaces later orders with `perf_counter`. Source: `bot/kalshi_bot/fast_entry.py` lines 221-229

### Inferences
- How the 2 ms observed tick of `time.time()` happened: some other process had raised the system timer rate. Windows 11 can drop that boost when the requesting window is minimized or hidden. So on Python 3.12, the bot's wake-up can be late by up to about 15.6 ms (one clock tick) plus the sleep overshoot (p99 about 10 ms).
- A recipe that works on Windows 11 with Python 3.12:
  1. Once, record `wall0 = time.time()` and `pc0 = perf_counter()`. Better: take `wall0` right after a tick, or use `GetSystemTimePreciseAsFileTime` through ctypes.
  2. Compute the target in `perf_counter` units.
  3. `time.sleep(left - 0.02)`.
  4. Then spin `while perf_counter() < target: pass`.
  The spin costs one CPU core for about 20 ms and holds the GIL. Spin only in the thread that fires, and only for the last stretch.
- Python 3.13+ removes the coarse `time.time()` problem without any code changes.

### Gaps
- Whether the bot's process actually gets 1-2 ms timer resolution while it runs as a background console or scheduled task was not checked.

## Clock sync on Windows: w32time vs third-party NTP (Meinberg) vs chrony

### Takeaway
Microsoft supports up to 1 ms accuracy with w32time only on Windows 10/Server 2016+, with special settings, a good stratum-1 source and a low, symmetric network delay. The default setup is meant only for Kerberos-level accuracy, which is loose. Over the home internet, expect several ms of error at best. Old reports for Meinberg NTP on Windows range from a few ms to about 30 ms, with occasional jumps into the hundreds. No 2024-2026 head-to-head measurement on Windows 11 was found.

### Cited findings
- "While we support accuracy up to 1 ms on Windows 10 or Windows Server 2016, most customers don't require highly accurate time." The default is for "Kerberos version 5" and "loosely accurate time". The high-accuracy settings are: MinPollInterval 6 and MaxPollInterval 6 (64 s), UpdateInterval 100, SpecialPollInterval 64, FrequencyCorrectRate 2, UtilizeSslTimeData 0. Page dated 2025-02-25. Source: [Microsoft Learn: Configuring systems for high accuracy](https://learn.microsoft.com/en-us/windows-server/networking/windows-time-service/configuring-systems-for-high-accuracy)
- The 1 ms, 50 ms and 1 s targets need an accurate, stable stratum-1 source. Network asymmetry and high CPU load harm accuracy. Source: [Microsoft Learn: Support boundary for high-accuracy time](https://learn.microsoft.com/windows-server/networking/windows-time-service/support-boundary)
- A 2019 time-nuts thread: Meinberg's NTP on an older Windows showed offsets of about 30 ms, with jumps into the hundreds. A Windows 8 test against internet servers showed −3 to +5.5 ms, and Windows 7 showed 10-20 ms. The NTP installers turn off w32time. Source: [time-nuts, Sept 2019](https://febo.com/pipermail/time-nuts_lists.febo.com/2019-September/097673.html)
- The bot measures its own offset to "Kalshi's clock". It uses SNTP, the simple form of NTP: it takes the median of several servers and refreshes every 900 s. The code comment says the PC's clock "drifts about 0.5 s a day". Source: `bot/kalshi_bot/fast_entry.py` lines 95-109 and 113-145; `bot/kalshi_bot/bot.py` line 88

### Inferences
- The SNTP offset's error is limited by how lopsided the path is: at most about half the round trip (a few ms to the NTP servers). That is likely smaller than the error from a 900 s refresh against a drift of 0.5 s per day (about 5 ms per 900 s).
- `bot.py` also says the offset can come "from its order answers" (line 539). An offset taken from Kalshi's order timestamps includes the one-way network delay plus Kalshi's processing time. That would bias the offset by about 30 ms or more. Worth checking how ClockSync handles this.
- chrony is the usual Linux answer, but it is Linux-only for a Windows PC. Not checked further.

### Gaps
- No 2024-2026 measurements of w32time (high-accuracy settings) vs Meinberg NTP vs other Windows NTP clients on Windows 11 over a home internet link.
- Kalshi does not publish what clock its order timestamps use.

## Measuring where the time goes: DNS, connect, TLS, send, server, first byte

### Takeaway
Three tools split a request into phases: curl `-w`, httpx/httpcore trace hooks, and urllib3 debug logs. On this PC they show that a warm request to Kalshi's origin is about 62 ms, and that a new connection adds about 15-40 ms (more with a DNS lookup). The bot should log `perf_counter` per phase in its live run. That is where the unexplained ~150-220 ms is.

### Cited findings
- curl `-w` variables: `time_namelookup` (DNS), `time_connect` (TCP), `time_appconnect` (TLS done), `time_starttransfer` (first byte), `time_total`. Example from this PC to `/exchange/status`, cumulative seconds, cold: DNS 0.047, TCP 0.055, TLS 0.075, first byte 0.082. On the reused connection: first byte 0.009 (a CDN cache hit). Source: [curl man page, -w](https://curl.se/docs/manpage.html#-w); [Local test, curl 8.21.0 Schannel, 2026-10-15]
- Windows' own curl.exe (8.21.0, Schannel) does not support `--http2`: "the installed libcurl version does not support this". Source: [Local test]
- httpcore's `trace` extension reports events with `.started`, `.complete` and `.failed` callbacks: `connection.connect_tcp`, `connection.start_tls`, `http11.send_request_headers`, `http11.receive_response_headers`, and the `http2.*` equivalents. Event names may change between versions. Source: [httpx extensions docs](https://github.com/encode/httpx/blob/master/docs/advanced/extensions.md)
- requests' `Response.elapsed` measures from sending the request until the response headers are parsed. Source: [requests API docs](https://requests.readthedocs.io/en/latest/api/#requests.Response.elapsed)
- Responses carry `X-Cache` (Hit or Miss from cloudfront) and `X-Amz-Cf-Pop`. `/exchange/status` is cached (`Cache-Control: public, max-age=1`), and so is `/markets` (`max-age=15`). Order book GETs were all "Miss" with no Cache-Control, so they always reach the origin. Source: [Local test, netprobe.py / bookcache.py]

### Inferences
- Phases to log in the bot, all with `perf_counter`:
  - The planned mark, and the actual wake time.
  - The halt check, start and end.
  - The start and end of each book read, and its thread.
  - The end of the decision.
  - For each order: sign start and end, send start, response headers.
  - Kalshi's order `created_time`.
  The gap from send start to `created_time`, minus the offset, is one-way time plus Kalshi's processing.
- Turning on `logging.getLogger("urllib3").setLevel(logging.DEBUG)` prints "Starting new HTTPS connection" each time a new socket opens. That is a cheap way to catch cold connections at the mark.
- Wireshark on the PC can time stamp the SYN (the first TCP packet), the ClientHello (the first TLS message) and the request packets. It can't see inside TLS, but packet timing alone is enough.
- The bot's warm-up calls `exchange_status`, which CloudFront answers from its cache. That warms the PC-to-edge connections, which is what the client controls. It does not test the edge-to-origin path.

### Gaps
- No live per-phase timing of the bot's actual burst was captured. That needs code changes, which were out of scope for read-only research.

## Windows network stack: Nagle, NIC and Wi-Fi power saving

### Takeaway
Nagle's algorithm is already off: urllib3 and Python's http.client both set TCP_NODELAY. Wi-Fi and adapter power saving can cause latency spikes, but the evidence is anecdotal. The safe advice is a wired Ethernet link, adapter power saving off, and the power plan's wireless setting on Maximum Performance.

### Cited findings
- urllib3's `HTTPConnection.default_socket_options` is `[(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)]`, which turns off Nagle's algorithm. Source: [urllib3 connection reference](https://urllib3.readthedocs.io/en/2.3.0/reference/urllib3.connection.html)
- Nagle's algorithm combined with delayed ACK (when the receiver waits before confirming data) causes about 50 ms delays on Linux when a program makes small writes one after another. CPython's http.client also sets the option. Source: [encode/httpcore PR #651](https://github.com/encode/httpcore/pull/651)
- Turning off "Allow the computer to turn off this device to save power" and setting the wireless adapter to Maximum Performance are common fixes for lag spikes. Some adapters have a second power-saving setting. No rigorous tests were found. Sources: [GeekRewind, Windows 11 Wi-Fi power saving](https://geekrewind.com/stop-your-wi-fi-adapter-from-saving-power-in-windows-11/); [NETGEAR community thread](https://community.netgear.com/t5/WiFi-Adapters/Random-ping-lag-spikes/td-p/1625123)
- One Microsoft Q&A case had ping spikes every 20 seconds that the power setting alone did not fix. Source: [Microsoft Q&A](https://learn.microsoft.com/en-us/answers/questions/2202686/ping-spikes-nearly-exactly-every-20-seconds)

### Inferences
- The local edge round trip of 8-12 ms suggests a good link, but whether the PC is on Wi-Fi or Ethernet is unknown. If it is on Wi-Fi, a wired link removes a common source of rare spikes of tens of ms. It does not change the median.
- Interrupt moderation and other NIC settings matter at the microsecond level. They are not worth changing for a link with a 60 ms round trip.

### Gaps
- No 2024-2026 measurements were found of the latency cost of Windows 11 Wi-Fi power saving vs Ethernet. The PC's adapter type was not checked.
