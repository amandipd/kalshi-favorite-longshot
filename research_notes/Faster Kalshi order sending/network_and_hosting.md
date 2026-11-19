# Network path and hosting: how far the bot's orders travel to Kalshi, and how to shorten the trip

Researched Oct 15, 2026 (about 18:30 to 19:00 UTC). The project's own measurements were taken from the bot's Windows 11 PC on a home Wi-Fi connection far from Ohio, between 18:31 and 18:55 UTC. Only public, unauthenticated GETs, DNS lookups, pings, a traceroute and bare TCP connects were sent. No API key was used, and nothing went to an order endpoint. Earlier project measurements (Oct 11) are in [research/kalshi_15min/lab/fast_entry/kalshi_api.md](../../research/kalshi_15min/lab/fast_entry/kalshi_api.md); this file adds to them.

Words used below:
- **RTT (round-trip time):** how long a message takes to go there and back.
- **One-way delay:** about half the RTT. This is what decides when Kalshi stamps an order.
- **CDN (content delivery network):** a ring of "edge" servers near users that pass requests on to the real servers (the **origin**).
- **Jitter:** how much the delay jumps around from one message to the next.

## Where are Kalshi's API and matching engine physically?

### Takeaway
Kalshi's real servers are in **AWS us-east-2 (Ohio)**. The host the bot uses, `api.elections.kalshi.com`, is only an **Amazon CloudFront** edge (for this connection, one a few milliseconds away). It passes each order on to Ohio. Kalshi's docs now name a second host, `external-api.kalshi.com`, as the **recommended** one. It is an AWS load balancer in Ohio with no CDN in front. Kalshi offers no co-location (renting space next to the exchange) to retail traders.

### Cited findings
- **The bot's host is CloudFront.** `api.elections.kalshi.com` returned 4 A records (18.155.192.9, .53, .67, .79), with a 60 s TTL (how long DNS answers may be cached). AWS's own IP list (ip-ranges.json, dated 2026-10-15 15:47 UTC) puts all four in `18.154.0.0/15`, service **CLOUDFRONT**, region GLOBAL. Source: [own DNS lookup + AWS ip-ranges.json](https://ip-ranges.amazonaws.com/ip-ranges.json)
- The answers carried `Via: 1.1 … .cloudfront.net (CloudFront)`, `X-Cache: Hit from cloudfront` and an `X-Amz-Cf-Pop` header naming a nearby edge. The DNS zone is run by Amazon Route 53 (`ns-1795.awsdns-32.co.uk`). Source: [own request to /exchange/status](https://api.elections.kalshi.com/trade-api/v2/exchange/status)
- The traceroute goes from the test PC through its ISP's network and enters Amazon's network (54.240.243.155) at hop 6, about 3-5 ms out. It reaches the edge at hop 12, still 3-5 ms. Source: the project's own `tracert` to 18.155.192.9
- **The recommended host goes straight to Ohio.** `external-api.kalshi.com` and `external-api-ws.kalshi.com` are both DNS aliases (CNAMEs) for `elections-external-api-107430227.us-east-2.elb.amazonaws.com`. All 8 of its IPs (3.20.176.26, 18.118.172.233, 3.128.23.29, 77.112.86.204, 3.151.120.95, 18.189.169.88, 18.220.153.4, 3.132.50.144) fall in AWS **us-east-2 EC2** ranges. Its answers have no CloudFront headers. Sources: [own DNS lookup + AWS ip-ranges.json](https://ip-ranges.amazonaws.com/ip-ranges.json); same CNAME seen on Oct 11 in [kalshi_api.md §5](../../research/kalshi_15min/lab/fast_entry/kalshi_api.md)
- The name format `<name>-<number>.<region>.elb.amazonaws.com` matches an **Application Load Balancer** (ALB, AWS's HTTP load balancer). Its measured idle timeout of 60 s (below) equals the ALB default. Source: [AWS ALB attributes doc](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/edit-load-balancer-attributes.html)
- **Kalshi's docs recommend the direct host.** Kalshi's environments page lists `https://external-api.kalshi.com/trade-api/v2` as the "Recommended base URL" for production REST and `https://api.elections.kalshi.com/trade-api/v2` as "Also supported". It says: "The `external-api` hosts are dedicated to the external Trade API and are the recommended hosts for API traders. The existing shared hosts remain supported for compatibility with existing clients." For WebSocket it recommends `wss://external-api-ws.kalshi.com/trade-api/ws/v2`. Source: [Kalshi API environments](https://docs.kalshi.com/getting_started/api_environments.md)
- Kalshi's OpenAPI spec labels `external-api.kalshi.com` "Production Trade API server" and `api.elections.kalshi.com` "Production shared API server, also supported". Source: [Kalshi openapi.yaml](https://docs.kalshi.com/openapi.yaml)
- **The FIX hosts are in Ohio too.** FIX is the order protocol big trading firms use. `fix.elections.kalshi.com` → 3.138.235.220. `margin-mm.fix.elections.kalshi.com` → 3.151.134.59, 18.216.43.146, 3.20.28.167. `margin-marketdata.fix.elections.kalshi.com` → 18.224.188.227, 3.136.166.236, 18.218.248.17. The legacy `trading-api.kalshi.com` → 3.23.21.182, 3.146.121.81. All are us-east-2 EC2 ranges, with no CDN. Sources: [own DNS lookup + AWS ip-ranges.json](https://ip-ranges.amazonaws.com/ip-ranges.json); FIX host names from [Kalshi FIX connectivity](https://docs.kalshi.com/fix-margin/connectivity.md)
- The demo host `demo-api.kalshi.co` is also CloudFront (13.249.74.x, in CLOUDFRONT 13.249.0.0/16). Source: [own DNS lookup + AWS ip-ranges.json](https://ip-ranges.amazonaws.com/ip-ranges.json)
- Glassnode's latency monitor states: "Fully centralized order book at api.elections.kalshi.com, behind AWS CloudFront CDN. Origin servers are in AWS us-east-2 (Ohio)." (no date on the page). Source: [Glassnode prediction-markets about](https://latency.glassnode.com/prediction-markets/about)
- TradoxVPS (published Apr 4, 2026, updated Jul 24, 2026) puts the matching engine in "AWS us-east-2", "the Ohio region (Columbus / New Albany metro)". It says the REST/WebSocket hosts sit behind CloudFront, so a ~1 ms ping only reaches a CDN edge. It reports Chicago → Kalshi FIX "~10 ms round-trip". This is a seller of hosting, so it has a commercial interest. Source: [TradoxVPS](https://tradoxvps.com/best-vps-for-kalshi-trading-bots/)
- **Conflicting claim:** QuantVPS (Mar 2, 2026, updated Oct 12, 2026) says Kalshi's servers are "likely located in the Chicago metro area", based on "0 to 1ms" from its Chicago servers. It admits Kalshi "does not publicly share the precise locations of its servers." This is contradicted by the DNS and IP-range evidence above: a 1 ms answer from `api.elections` is a CloudFront edge, not the exchange. Sources: [QuantVPS](https://www.quantvps.com/blog/kalshi-servers-location); contradicted by [AWS ip-ranges.json](https://ip-ranges.amazonaws.com/ip-ranges.json) and [TradoxVPS](https://tradoxvps.com/best-vps-for-kalshi-trading-bots/)
- The project's Oct 11 note also records a bot-hosting blog (botforkalshi) that says us-east-1. That claim has no supporting evidence and conflicts with the DNS above. Source: [kalshi_api.md §5](../../research/kalshi_15min/lab/fast_entry/kalshi_api.md)
- **No co-location for retail.** The closest options are AWS **PrivateLink** (a private network link from your AWS account to Kalshi's) for "Members on the Premier tier or above", and **VPC peering** (joining your AWS network to Kalshi's) for "Prime tier or above". Both go through institutional@kalshi.com. Sources: [Kalshi API environments](https://docs.kalshi.com/getting_started/api_environments.md), [Kalshi FIX connectivity](https://docs.kalshi.com/fix-margin/connectivity.md)
- **Matching shards:** crypto and commodities trade on `exchange_index` 2, a separate matching engine. Kalshi says "Automatic routing will incur an additional latency cost" for orders that don't name their shard. Sources: [kalshi_api.md §5](../../research/kalshi_15min/lab/fast_entry/kalshi_api.md), citing [Kalshi exchange sharding](https://docs.kalshi.com/getting_started/exchange_sharding.md)
- **The bot uses the CloudFront host today.** `bot/kalshi_bot/kalshi.py` sets `"prod": "https://api.elections.kalshi.com/trade-api/v2"`. The dashboard's WebSocket already uses `wss://external-api-ws.kalshi.com/trade-api/ws/v2`. Sources: [bot/kalshi_bot/kalshi.py](../../bot/kalshi_bot/kalshi.py), [bot/kalshi_bot/web/dashboard.py](../../bot/kalshi_bot/web/dashboard.py)

### Inferences
- The matching engine is almost certainly in us-east-2. Every host that is not behind a CDN (REST load balancer, FIX order entry, FIX market data, legacy API) is in us-east-2. PrivateLink is a per-region AWS feature, which also fits one home region. No written statement of the region by Kalshi was found.
- An order sent to `api.elections` today goes: PC → nearby CloudFront edge (about 5 ms RTT) → across Amazon's private network to Ohio → the ALB → Kalshi's API servers → the shard 2 matching engine.
- CloudFront adds nothing useful for orders. Orders are never cached (CloudFront does not cache POSTs), so the edge is just one more hop.

### Gaps
- Kalshi has not publicly named its AWS region or Availability Zones (separate data-center buildings within a region). No job post, engineering blog or talk that states it was found.
- The path from Kalshi's API servers to the matching engine (and how long it takes inside Kalshi) is not public.

## What does the round trip cost from a home connection versus from cloud servers?

### Takeaway
From the test PC, a warm request (one on an already-open connection) to Kalshi's servers takes **about 80-96 ms through CloudFront** and **about 60 ms straight to the Ohio host**. The direct path was also far steadier: worst case 61 ms versus 128 ms. From a VM inside us-east-2, the network round trip to Kalshi should be **about 1-2 ms**. That is an estimate; it was not tested from inside AWS.

### Cited findings
- **This PC → CloudFront edge:** TCP connect RTT min 3.4 / median 5.3 / max 13.4 ms (n=8), and later 3.3 / 4.8 ms. ICMP ping min 3 / avg 4.9 / max 12 ms (n=30). The TLS 1.3 full handshake (the encryption setup) took 7.8-11.3 ms. Source: [own measurement, Python socket/ssl to api.elections.kalshi.com:443](https://api.elections.kalshi.com/trade-api/v2/exchange/status)
- **Warm requests answered at the edge** (cache hits on `/exchange/status`): 7-30 ms. Source: [own measurement](https://api.elections.kalshi.com/trade-api/v2/exchange/status)
- **Warm requests that went through to Kalshi** (cache misses, forced with a random query string, n=10): min 79.1 / **median 82.0** / max 127.8 ms. An earlier set of 4 gave 80-120 ms, and one natural miss took 172 ms. Source: [own measurement](https://api.elections.kalshi.com/trade-api/v2/exchange/status)
- **The same thing on Oct 11 (night):** order-book GETs through CloudFront (never cached) had median **96 ms**, min 84 ms, with spikes of 176 and 218 ms. Source: [kalshi_api.md §8](../../research/kalshi_15min/lab/fast_entry/kalshi_api.md)
- **This PC → `external-api.kalshi.com` (Ohio ALB, direct):** TCP connect RTT min 54.1 / median 57.3 ms (n=8). Warm GET `/exchange/status` (n=10, all reaching Kalshi, since there is no cache): min 57.4 / **median 59.5** / max **60.9 ms**. The TLS handshake took 59 ms. Source: [own measurement](https://external-api.kalshi.com/trade-api/v2/exchange/status)
- On Oct 11 at night the same TCP connect to the Ohio ALB measured median 93 ms, min 69 ms, with spikes of 160-210 ms. The project note blamed jitter on the local network. Source: [kalshi_api.md §7](../../research/kalshi_15min/lab/fast_entry/kalshi_api.md)
- **This PC → AWS's own endpoints in each region** (TCP connect to `dynamodb.<region>.amazonaws.com:443`, n=10, min / median / max):
  - us-east-2 (Ohio): 55.1 / 64.5 / 136.0 ms
  - us-east-1 (N. Virginia): 64.7 / 66.6 / 87.1 ms
  Source: [own measurement](https://dynamodb.us-east-2.amazonaws.com)
- **Between AWS regions:** us-east-1 ↔ us-east-2 is listed at about 13.9 ms (statistic and date not stated). Source: [economize.cloud us-east-1 vs us-east-2](https://www.economize.cloud/resources/aws/latency/us-east-1-vs-us-east-2/)
- **Inside one region:** AWS says Availability Zones are linked by "high-bandwidth, low-latency networking, over fully redundant, dedicated metro fiber", are "all within 100 km (60 miles) of each other", and fast enough "to accomplish synchronous replication". It gives no millisecond figure on that page. Source: [AWS Regions and AZs](https://aws.amazon.com/about-aws/global-infrastructure/regions_az/)
- **What other traders report:**
  - TradoxVPS: Chicago → Kalshi FIX "~10 ms round-trip"; Europe → engine "~80 ms or more"; home connections "50-200 ms normally, 300-500 ms during congestion"; a generic cloud VPS "10-50 ms". These are vendor numbers. Source: [TradoxVPS](https://tradoxvps.com/best-vps-for-kalshi-trading-bots/)
  - A search-engine summary of a GitHub study (`YLiu-101/latency-expos`, said to be from late Sep 2026) reported about 3,320 live order operations from a New York-area host, an order-acknowledgment p50 of about 27 ms, about 21 ms network RTT to Ohio, and the view that hosting in us-east-2 would remove most of the RTT. **The repo now returns 404**, so these numbers could not be checked. Source: [search summary of github.com/YLiu-101/latency-expos](https://github.com/YLiu-101/latency-expos) (404 on Oct 15, 2026)
  - No Reddit or Discord posts with measured Kalshi order latencies were found.
- **How the bot sends:** `FAST_BURST = 8` orders go at once. "No further batch goes out until its answers are back", and after that one order every `FAST_SPACING = 0.1` s. So each round trip also delays every order after the 8th. Source: [bot/kalshi_bot/bot.py](../../bot/kalshi_bot/bot.py)

### Inferences
- **Switching the bot to `external-api.kalshi.com` from home** saves about 22 ms per round trip at the median (82 → 60 ms). It saves about 65 ms in the worst case (128 → 61 ms). For the order stamp itself (one-way), that is roughly 10-20 ms earlier. A read made just before the orders (for example the order-book read at the mark) is a full round trip, so it saves the full ~22 ms too.
- Why the direct path is faster: the CloudFront path adds an extra stop. The edge has to process the request, then forward it over HTTP/1.1 on its own connection pool to Ohio. The occasional 128-218 ms spikes fit an edge server that had no warm connection to the origin and had to open one. That is a guess, not something that was proved.
- **On a us-east-2 VM**, the round trip to the ALB should drop from about 57-82 ms to about 1-2 ms plus Kalshi's own processing. The `/exchange/status` call took only about 2 ms beyond the bare TCP RTT (59.5 vs 57.3 ms), so Kalshi's front end is quick for simple calls. Compared with today's setup, that saves **about 30-40 ms one-way on each order**, plus **about 55-80 ms on every round trip** that comes before or between orders: the book read at the mark, and the wait before the second batch. In total, orders could be stamped **roughly 85-120 ms earlier** than now.
- The observed 0.25-0.32 s from target to stamp is much larger than the network share. About 40 ms is one-way order travel, plus about 80-100 ms if a book read comes first. That leaves an estimated 0.1-0.2 s somewhere else: the bot's own work, signing, thread start-up, clock error, or queueing inside Kalshi. Hosting alone cannot remove that part.
- us-east-1 (Virginia) is the wrong region. It is about 14 ms from Ohio, and from the test connection it is no closer than Ohio (66.6 vs 64.5 ms median).

### Gaps
- Nothing was measured from inside us-east-2, so the 1-2 ms figure is an estimate. A $5 test VM for an hour would confirm it.
- How long Kalshi takes to process an order (API → matching engine → reply) is not published. The 404'd GitHub study's ~27 ms p50 order-ack from New York (with ~21 ms RTT) hints at about 6 ms, but it could not be verified.
- All of today's numbers come from one 25-minute window around midday. Evening, peak-hour and on-the-minute burst behavior may differ. Oct 11 night readings were noticeably worse.

## Is it worth running the bot on a cloud VM near Kalshi? Which provider, region, cost, Windows or Linux, and the trade-offs?

### Takeaway
Yes, if earlier stamps are worth about $10-25 a month and a migration. An AWS VM in **us-east-2 (Ohio)** removes almost all network delay: about 85-120 ms earlier per window by the estimate above. It also brings a much better clock. A small **Linux** VM is cheapest and keeps the best time. **Windows** about doubles the price, and its default clock setting is loose. The cheap first step comes before any of this: switch to `external-api.kalshi.com` (saves about 22 ms per round trip from home, costs nothing).

### Cited findings
- **Lightsail prices** (AWS's simple fixed-price VMs; fetched Oct 15, 2026; US East (Ohio) is an offered region):
  - Linux with public IPv4: **$5**/mo (0.5 GB RAM, 2 vCPU, 20 GB SSD, 1 TB transfer), **$7**/mo (1 GB, 40 GB, 2 TB), **$12**/mo (2 GB, 60 GB, 3 TB), $24/mo (4 GB).
  - Windows: **$9.50**/mo (0.5 GB), **$14**/mo (1 GB), **$22**/mo (2 GB), $44/mo (4 GB).
  Source: [AWS Lightsail pricing](https://aws.amazon.com/lightsail/pricing/)
- **EC2 prices** (EC2 is AWS's regular, pay-by-the-hour VM service):
  - t4g.small (2 vCPU, 2 GiB, Arm) is about $0.0168/hour in N. Virginia, with us-east-2 at about $0.017. That is about $12/month before disk and public IP costs. This is an aggregator figure, not AWS's own page. AWS's T4g page lists a free trial of up to 750 hours a month until Dec 31, 2026. Sources: [aws-pricing.com t4g.small](https://aws-pricing.com/t4g.small.html), [AWS T4g](https://aws.amazon.com/ec2/instance-types/t4/)
  - t3.small: Linux $0.0208/hour. At the 2018 launch, Windows was $0.0393/hour versus $0.0209 for Linux, about 88% more. **These are old prices.** Sources: [AWS T3 launch blog (2018)](https://aws.amazon.com/blogs/aws/new-t3-instances-burstable-cost-effective-performance), [instances.vantage.sh t3.small](https://instances.vantage.sh/aws/ec2/t3.small?region=us-east-2)
- **Clock on a cloud VM:**
  - The Amazon Time Sync Service is at `169.254.169.123` (IPv4) and `fd00:ec2::123` (IPv6, Nitro only). It is free and runs on "satellite-connected and atomic reference clocks in each AWS Region". Sources: [AWS: precision clock and time sync](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/set-time.html), [AWS: configure local Time Sync](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/configure-ec2-ntp.html)
  - Accuracy: "typically … a clock error bound of under 100us using the NTP connection" and "under 40us" with the PTP hardware clock (Nov 16, 2023). Source: [AWS Compute Blog](https://aws.amazon.com/blogs/compute/its-about-time-microsecond-accurate-clocks-on-amazon-ec2-instances/)
  - **Linux:** Amazon Linux 2023 is set to use it by default. AWS's sample chrony output shows ±287-401 µs bounds and an RMS offset of about 83 µs. The PTP hardware clock (PHC) is "currently accessible on Linux instances only". Source: [AWS: configure local Time Sync](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/configure-ec2-ntp.html)
  - **Windows:** Windows AMIs (since Aug 2018) also use Time Sync by default. Their w32time settings are tuned "to keep any clock drift to within one second of accuracy": it adjusts every 120 s and checks the server only every 900 s (1024 s on Windows Server 2025). Source: [AWS: configure local Time Sync](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/configure-ec2-ntp.html)
  - June 30, 2026: microsecond-accurate time expanded to 26 more instance types in all commercial regions, through "Precision Time Placement Groups". us-east-2 also has legacy PHC access on M7a/M7g/M7i/R7*/I8g. Sources: [AWS What's New, Jun 2026](https://aws.amazon.com/about-aws/whats-new/2026/06/ec2-time-sync-precision-time-placement-group), [AWS: configure local Time Sync](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/configure-ec2-ntp.html)
- **Kalshi's private links need high tiers.** PrivateLink (Premier+) and VPC peering (Prime+) are not available to a retail tier. A retail VM reaches Kalshi over its public ALB. Source: [Kalshi API environments](https://docs.kalshi.com/getting_started/api_environments.md)
- **Commercial "Kalshi VPS" offers:** TradoxVPS sells Chicago machines at $39-$249/mo. QuantVPS markets Chicago. Both pitch Chicago, but Kalshi's servers are in Ohio, and Tradox's own figure is ~10 ms from Chicago versus about 1-2 ms (estimated) inside us-east-2. Sources: [TradoxVPS](https://tradoxvps.com/best-vps-for-kalshi-trading-bots/), [QuantVPS](https://www.quantvps.com/blog/kalshi-servers-location)
- The PC's clock is a known weak spot. The bot notes "the PC's clock drifts about 0.5 s a day", and it corrects itself with its own NTP offset and Kalshi's `ts_ms`. Sources: [bot/kalshi_bot/bot.py](../../bot/kalshi_bot/bot.py), [kalshi_api.md](../../research/kalshi_15min/lab/fast_entry/kalshi_api.md)

### Inferences
- **Best choice: AWS us-east-2.** It is the same region as Kalshi's ALB, so traffic stays inside AWS. Lightsail $7-12 Linux (1-2 GB) is enough for a Python bot with a handful of threads. EC2 t4g.small or t3.small (~$12-15/mo plus disk) is the more flexible option. Other clouds with Ohio data centers were not researched. AWS is the safe pick because its traffic to Kalshi never leaves Amazon's network.
- **Windows or Linux:** Linux costs about half as much on Lightsail ($12 vs $22 for 2 GB). It gets sub-millisecond time from chrony with no tuning. Windows' default is tuned only to about 1 s, though w32time can be tightened. The bot already keeps its own clock offset, so the OS clock matters less, but a steadier base clock helps. The catch: the setup at the time leaned on Windows (scheduled tasks, PowerShell, psutil checks). Moving to Linux means porting those parts. A Windows VM is the low-effort path.
- **Security of API keys:** the private key would sit on a machine on the internet. Sensible defaults (general suggestions, not from a source):
  - Use a new Kalshi key just for the VM, with the narrowest permissions Kalshi allows.
  - Allow SSH or RDP only from known IP addresses, using key-based login.
  - Encrypt the disk.
  - Never commit the key to a git repository.
  - Revoke the key at once if the VM is ever exposed.
- **Reliability:** a cloud VM avoids home power, Wi-Fi and ISP outages and the PC's sleep or update reboots. But it is a single machine that AWS can retire or that can fail. It needs its own monitoring (the existing phone alerts would have to run on, or watch, the VM). A Lightsail or EC2 snapshot makes rebuilding easy.
- **Hybrid option:** keep the dashboard and notifier at home and run only the order-sending bot in Ohio. That gives the latency win with the smallest move.
- **Size of the win:** the VM gives about 85-120 ms earlier stamps. Switching hosts from home gives about 15-30 ms. Whether that is worth $10-25/mo plus migration work depends on how much fill rate improves per 10 ms. Fill-rate data from other parts of this research should settle that.

### Gaps
- No official AWS page fetched gives the exact current us-east-2 on-demand EC2 price for Windows, nor the public-IPv4 address charge. Check the EC2 pricing page or calculator.
- It could not be confirmed which Kalshi key scopes exist (for example, whether a key can be limited to trading only). The Oct 11 note mentions a `read` + `write::trade` scope for FIX logon.
- Whether Lightsail's burstable CPUs ever slow down the burst of signing at the mark was not measured.

## Residential internet: how much do jitter, Wi-Fi and bufferbloat add?

### Takeaway
On a quiet line, home Wi-Fi adds only a few ms at the median, but it adds **spikes of 40-130+ ms**. Those spikes, not the average, are what hurt a timed burst. **Bufferbloat** (delay from overfull buffers in the router or modem when the link is busy) can add tens to hundreds of ms over Wi-Fi. A wired Ethernet cable and keeping the uplink idle at the mark are the cheap fixes.

### Cited findings
- The test PC is on **Wi-Fi** (a Wi-Fi 6E adapter on 5 GHz with a strong signal). Source: the project's own `Get-NetAdapter` / `netsh wlan show interfaces`, Oct 15, 2026
- Ping to the home gateway: min 2 / avg 9.2 / **max 72 ms** (n=30). Ping to the CloudFront edge: min 3 / avg 4.9 / max 12 ms (n=30). The traceroute's first hop showed 2-3 ms. Source: the project's own measurement, Oct 15, 2026
- TCP connects to AWS Ohio had a median of 64.5 ms but a **max of 136 ms** (n=10). CloudFront-to-origin GETs spiked to 128 and 172 ms. Source: the project's own measurement, Oct 15, 2026
- Oct 11: TCP connects to both the edge and the Ohio ALB "had spikes of 160-210 ms. That's jitter (uneven delay) on the local network". Source: [kalshi_api.md §7](../../research/kalshi_15min/lab/fast_entry/kalshi_api.md)
- Research on Wi-Fi bufferbloat: the default Linux Wi-Fi stack "can add several hundred milliseconds of latency under load". Queueing in the lower wireless layers is why ordinary queue management helps less on Wi-Fi than on wired links. Source: [Høiland-Jørgensen et al., "Ending the Anomaly" (arXiv 1703.00064)](https://arxiv.org/pdf/1703.00064)
- One home user with SQM (smart queue management, a router feature that keeps queues short) saw 0 ms of added latency under load on a wired connection. Over Wi-Fi, even on 5 GHz at close range, latency rose by more than 40 ms. This is a single anecdote. Source: [OpenWrt forum](https://forum.openwrt.org/t/bufferbloat-on-wifi/242519)
- Vendor claims for home connections: "50-200 ms normally, 300-500 ms during congestion" (TradoxVPS); "over 100ms on typical home internet" (QuantVPS). Both are unsourced marketing numbers, and they are worse than what the test PC measured on a quiet line. Sources: [TradoxVPS](https://tradoxvps.com/best-vps-for-kalshi-trading-bots/), [QuantVPS](https://www.quantvps.com/blog/kalshi-servers-location)

### Inferences
- The router ping (avg 9 ms, max 72 ms) points to Wi-Fi itself adding jitter. Treat this with care: many routers answer pings to themselves at low priority, which inflates these numbers.
- **Wired Ethernet** should cut the median by a few ms. More importantly, it should remove most 40-130 ms spikes. On a burst at a fixed moment, one spike can make a whole batch late.
- **Upload load:** background cloud sync and scheduled uploads from the same PC could fill the uplink queue at the mark and cause bufferbloat. Pausing heavy syncs at the mark, or turning on SQM on the router, would help. This was not measured.
- A cloud VM removes all of these home-network problems at once.

### Gaps
- No loaded-latency (bufferbloat) test, such as Waveform's, was run on this line. Ethernet was not compared with Wi-Fi on the test PC either, since there was no cable test.
- The home gateway (followed by link-local 169.254.x hops) looks like an ISP-managed gateway or network. Whether it supports SQM is unknown.

## Connection-level tuning: what does each change save per order?

### Takeaway
Once connections are warm, most protocol tweaks save almost nothing. The big wins are:
1. Use the direct `external-api` host.
2. Keep enough connections **warm right up to the mark**. The direct host drops idle connections after **60 s**, and a cold connection from home costs about **120 ms**.
3. Cut round trips. A batch-order request, or HTTP/2 over one connection, sends everything at once.

TCP_NODELAY is already on. TLS resumption and 0-RTT save nothing on warm connections. DNS only matters for new connections.

### Cited findings
- **Bot's HTTP stack today:** Python 3.12.10, requests 2.32.3, urllib3 2.7.0, OpenSSL 3.0.16. One `requests.Session()` with the default adapter. `DEFAULT_POOLSIZE = 10` connections kept per host, `DEFAULT_POOLBLOCK = False`. httpx is installed; the `h2` package (needed for HTTP/2) is not. Source: the project's own check of installed packages; [bot/kalshi_bot/kalshi.py](../../bot/kalshi_bot/kalshi.py); [requests HTTPAdapter docs](https://docs.python-requests.org:443/en/latest/_modules/requests/adapters/)
- **Pre-warming already exists.** Just before the mark, `warm()` sends `FAST_BURST` (8) `GET /exchange/status` requests on separate threads to open connections. The code says a connection opened at the mark "would cost its TLS handshake there, about 0.1-0.25 s". Source: [bot/kalshi_bot/bot.py](../../bot/kalshi_bot/bot.py)
- **Those warm-up calls never reach Kalshi.** On `api.elections`, `/exchange/status` is cached by CloudFront (`Cache-Control: public, max-age=1`, `X-Cache: Hit from cloudfront`). They warm PC ↔ edge connections only. The edge ↔ Ohio connections are CloudFront's own. Sources: [own measurement](https://api.elections.kalshi.com/trade-api/v2/exchange/status); [kalshi_api.md §7-8](../../research/kalshi_15min/lab/fast_entry/kalshi_api.md)
- **Cold connection cost, measured:**
  - To the CloudFront edge: TCP ~5 ms + TLS 1.3 ~8-11 ms, so **about 15 ms**.
  - To the Ohio ALB from home: TCP ~57 ms + TLS ~59 ms, so **about 116 ms**, plus DNS when the cache has expired.
  Source: [own measurement](https://external-api.kalshi.com/trade-api/v2/exchange/status)
- **Idle timeouts, measured** (one connection per idle length, Oct 15):
  - **CloudFront client connection:** still alive after 200 s of idle; the server closed it at **~240 s**.
  - **`external-api` ALB:** alive after 30 s; closed at **~60 s** (every test at 60 s or longer had already been closed).
  Source: [own measurement](https://external-api.kalshi.com/trade-api/v2/exchange/status)
- **ALB rules:**
  - "By default, Elastic Load Balancing sets the idle timeout value for your load balancer to 60 seconds" (range 1-4000 s).
  - "Application Load Balancers do not support HTTP/2 PING frames. These do not reset the connection idle timeout." So a keep-alive must be a real request.
  - "HTTP client keepalive duration" (the maximum age of a connection) defaults to **3600 s**. After that, the ALB answers one more request and then closes the connection.
  Source: [AWS ALB attributes](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/edit-load-balancer-attributes.html)
- **CloudFront rules:**
  - CloudFront keeps its connection to the origin open "for several seconds" (default keep-alive 5 s, configurable to 60 s, or up to 180 s with a quota increase). Kalshi's setting is unknown. Sources: [CloudFront custom origin behavior](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/RequestAndResponseBehaviorCustomOrigin.html), [AWS 2017 announcement](https://aws.amazon.com/about-aws/whats-new/2017/03/announcing-configure-read-timeout-and-keep-alive-timeout-values-for-your-amazon-cloudfront-custom-origins)
  - "CloudFront forwards requests to your custom origin using HTTP/1.1." So HTTP/2 between the PC and the edge never reaches Kalshi. Source: [CloudFront custom origin behavior](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/RequestAndResponseBehaviorCustomOrigin.html)
  - CloudFront does not retry POSTs that time out: it "drops the connection and doesn't try again". Source: [CloudFront custom origin behavior](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/RequestAndResponseBehaviorCustomOrigin.html)
- **HTTP/2 and TLS support, measured:** both hosts negotiated **TLS 1.3** (`TLS_AES_128_GCM_SHA256`) and accepted **`h2`** (HTTP/2) through ALPN (the step where client and server agree on a protocol). Neither sent an `Alt-Svc` header, so **HTTP/3 is not offered**. The `external-api` certificate is `*.kalshi.com`. Source: [own measurement](https://external-api.kalshi.com/trade-api/v2/exchange/status)
- **TLS resumption and 0-RTT:**
  - CloudFront has supported TLS 1.3 for viewers since Sep 2020, and TLS 1.3 session resumption since Jun 2022. Sources: [AWS 2020](https://aws.amazon.com/about-aws/whats-new/2020/09/cloudfront-tlsv1-3-support), [AWS 2022](https://aws.amazon.com/about-aws/whats-new/2022/06/amazon-cloudfront-supports-tls-1-3-session-resumption-viewer-connections/)
  - No source found says CloudFront accepts 0-RTT early data. In a local test, Python's `ssl` module did not resume a session.
  - A TLS 1.3 full handshake is already one round trip. Resumption without 0-RTT is also one round trip.
- **TCP_NODELAY (turning off Nagle's algorithm, which holds back small packets):** urllib3's default socket options on this PC are `[(6, 1, 1)]`, which means `IPPROTO_TCP, TCP_NODELAY, 1`, so Nagle is already off. This matters for Python: `http.client._send_output` sends the headers in one `send()` and the POST body in a separate one. With Nagle on, the body could wait for the server's acknowledgment of the headers. Source: the project's own check of urllib3 defaults; [CPython http/client.py (local copy)](https://github.com/python/cpython/blob/3.12/Lib/http/client.py); [urllib3 socket options discussion](https://github.com/psf/requests/issues/6354)
- **DNS:**
  - The edge host's A records have a 60 s TTL.
  - curl's lookup times from this PC were 12-122 ms when not cached.
  - urllib3 only looks up DNS when it opens a new connection, not for requests on a reused one.
  Source: the project's own measurement; [urllib3/requests adapter](https://docs.python-requests.org:443/en/latest/_modules/requests/adapters/)
- **Number of parallel connections:**
  - The requests pool keeps up to 10 connections per host. With `pool_block=False`, connections beyond that are opened and then thrown away after use.
  - `FAST_BURST = 8` fits inside 10.
  - The project's Oct 11 note found that `send_all`'s 8 threads "open up to 7 new TLS connections right at the mark" if not warmed.
  Sources: [requests HTTPAdapter](https://docs.python-requests.org:443/en/latest/_modules/requests/adapters/), [bot/kalshi_bot/bot.py](../../bot/kalshi_bot/bot.py), [kalshi_api.md](../../research/kalshi_15min/lab/fast_entry/kalshi_api.md)
- **Batch orders:**
  - `POST /portfolio/events/orders/batched` sends many orders in one request at 10 tokens per order. "The maximum batch size scales with your tier's write budget."
  - Each returned order has its own `error` and a `ts_ms` ("Matching engine timestamp at which the order was processed").
  - The docs don't say whether a batch is atomic (all-or-nothing) or in what order its orders run.
  Source: [Kalshi batch create orders v2](https://docs.kalshi.com/api-reference/orders/batch-create-orders-v2.md)
  - An older page said 20 orders per batch and "advanced access only". It conflicts with the v2 page. Source: [search summary of Kalshi docs](https://docs.kalshi.com/api-reference/portfolio/batch-create-orders)

### Inferences
Estimated savings per change, for orders from the test PC (based on the measurements above):

| Change | Saves on a warm path | Saves on a cold or unlucky path | Notes |
|---|---|---|---|
| Base URL → `external-api.kalshi.com` | ~22 ms per round trip at the median (~10-20 ms earlier stamp) | ~65 ms on the worst cases seen (128 → 61 ms) | One-line change, plus the shorter idle timeout below. |
| Keep connections warm into the mark | 0 | ~15 ms per connection (edge), ~116 ms (direct from home), ~2-3 ms (from an Ohio VM) | On `external-api`, warm within 60 s of the mark, or send a real request every 30-45 s. Make warm-ups reach Kalshi: an uncached public GET or an authenticated cheap read. |
| Batch endpoint (1 request) | Removes the wait before the second batch: one full round trip, ~60-80 ms from home | Needs only one warm connection | Costs the same tokens. Order inside a batch is undocumented. |
| HTTP/2 on one connection (httpx + h2) | ~0 compared with 8 warm HTTP/1.1 connections | Removes the risk of 7 cold handshakes; a single connection is easier to keep warm | Both hosts speak h2. Through CloudFront, the edge → origin leg is still HTTP/1.1. |
| More parallel connections (pool_maxsize > 10) | Only helps if more than 10 orders must go at once | Each extra connection must also be warm | Rate-limit tokens, not connections, cap the burst. |
| TLS 1.3 session resumption / 0-RTT | 0 | ≤1 RTT only on a cold connection, and 0-RTT isn't documented on CloudFront | Not worth the work. Warm connections are better. |
| TCP_NODELAY | 0 (already on) | Would matter only if a custom socket path dropped it | Keep it on. |
| DNS caching | 0 on reused connections | 10-120 ms on a new connection after the 60 s TTL | Moot if connections stay warm. Could pre-resolve. |
| `exchange_index: 2` on each order | Unknown | Kalshi says auto-routing "will incur an additional latency cost" | Software change, no network cost. |

- The single most important connection-level fact: **the direct host's 60 s idle timeout.** If the bot switches hosts and keeps warming only "just before the mark", that is fine. But any connection left idle for more than 60 s will be dead. urllib3 will notice and reconnect, paying about 116 ms from home at exactly the wrong moment.
- The current warm-ups to `api.elections` `/exchange/status` are CloudFront cache hits. They do not prove that the path to Kalshi is warm.
- Switching hosts also changes how much cold connections cost. Through CloudFront a cold connection is cheap (~15 ms), because TLS ends 5 ms away. Direct to Ohio from home it is expensive (~116 ms). From an Ohio VM it is cheap again (~2-3 ms). So "switch host" and "keep connections warm" must ship together, unless the bot moves to Ohio.

### Gaps
- CloudFront's client-side idle timeout (~240 s) comes from a single local test. No AWS page that states it was found.
- It was not tested whether a public, unauthenticated GET on `external-api` counts against the account's rate-limit tokens. The docs fetched don't say.
- HTTP/2 (httpx + h2) was not tested against Kalshi with real order POSTs, and it was not measured whether one h2 connection with 8-20 parallel requests is as fast as 8 warm HTTP/1.1 connections. The h2 connection probably ends at the ALB, so Kalshi's servers behind it may still get HTTP/1.1. This was not confirmed (unsourced).
- How Kalshi orders arrivals within a batch, or within the same millisecond, is undocumented.
