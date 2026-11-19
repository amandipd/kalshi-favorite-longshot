# Research

Studies that grew out of the main calibration study: does the favourite-longshot bias (cheap unlikely bets are
overpriced, heavy favourites underpriced) show up in Kalshi's short-term markets, and can it be traded after fees,
spreads and real fills? Each folder is one study with its own README, its scripts and, where it has them, its tests.
The longer write-ups of most of them are in `reports/`.

| Folder | Question | Outcome |
|---|---|---|
| `kalshi_15min/` | Does the bias exist in Kalshi's 15-minute crypto, metals and energy markets, and can buying heavy favourites pay after costs? | The main study. The bias is there; a rule that skips wide spreads and late price jumps made a small, positive profit per bet over ten months |
| `opening_price/` | Is a newly listed market's favourite underpriced at its first trade? | No. Favourites are overpriced at the open |
| `all_markets_bias/` | Where across every Kalshi series are favourites underpriced? | Pre-registered and coded; no result recorded here |
| `bias_recent/` | Has the bias faded in the most recent weeks? | No: Oct 9 to 29 matched the long-run past |
| `contagion_exit/` | When one crypto favourite collapses, should the bot sell its other crypto bets? | No. Every version lost to holding |
| `settle_average/` | Do favourites bought in a 15-minute crypto market's last minute win more often than priced? | No. A fresh test lost money |
| `maker_shadow/` | Would a resting order at the bid beat buying at the ask? | Unclear from past trades; a live recorder was built and trialled, then paused |
| `thin_favourites/` | Are thin, low-volume 80 to 90 cent favourites underpriced, and can a bot get in? | Shelved: quiet markets can't be spotted early enough |
| `weather_favourites/` | Does the favourite rule carry over to Kalshi's weather markets? | No for daily highs; daily rain too thin to judge |
| `polymarket_5min/` | Does the rule work on Polymarket US's 5-minute crypto markets? | Unclear; one variant passed a backtest but may peek ahead |
| `paper_test/` | How the paper (dry-run) bot scores its forward test | A scoring script only |

Several studies were pre-registered: the rule and the pass bar were written down (`PREREG*.md`) before any result
was read, and a later change is labelled as such in the report.

## Running the tests

From the repository root:

    python -m pytest -q -p no:cacheprovider research/kalshi_15min/tests
    python -m pytest -q -p no:cacheprovider research/kalshi_15min/lab/tests research/kalshi_15min/lab/test_edge_map.py
    python -m pytest -q -p no:cacheprovider research/all_markets_bias/tests research/maker_shadow/tests
    python -m pytest -q -p no:cacheprovider research/polymarket_5min/tests research/settle_average/tests
    python -m pytest -q -p no:cacheprovider research/thin_favourites/tests research/weather_favourites/tests

Run each line on its own: several studies have scripts and test files with the same names (`fetch.py`, `score.py`,
`test_score.py`), and they clash when one run collects them all. No test needs the network or any downloaded data. A few `kalshi_15min` tests import
the bot package (`bot/kalshi_bot`) and the study package (`kalshi_calibration`) to check that the research and the
bot compute fees and stakes the same way.

## Data

None of the downloaded data is in the repository. Every study fetches it from public APIs (Kalshi, Polymarket US,
Gemini, Coinbase, the Iowa Environmental Mesonet) with the scripts in its folder, and each README says how. The
fetches are polite and resumable but slow: the big 15-minute history takes most of a day. Files they write are
listed in `research/.gitignore` so they never get committed. Small result files that a README or the dashboard
quotes (JSON or text, well under 1 MB) are kept.

A few results came from the live bot's own order ledger, which is private and not included. Those numbers can be
read in the write-ups but not rebuilt from this repository.
