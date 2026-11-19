"""A bot that buys likely favourites in Kalshi's 15-minute markets, with its ledger, halts, alerts and dashboard.

    bot.py          the trading loop, its halts and its command line
    market.py       pure helpers: times, market groups, fees, order books, candles, order bodies
    ledger.py       the SQLite ledger each account keeps in state/
    kalshi.py       a small client for Kalshi's Trade API v2
    fast_entry.py   fast entry: every order of a window sent at minute 8 exactly, on Kalshi's clock
    notify.py       phone alerts through ntfy
    watchdog.py     a dead man's switch: a healthchecks.io ping while the loop runs
    stall_alert.py  an alarm when the bot stops looking at markets while still looking alive
    web/            the dashboard: its server and its pages
"""
