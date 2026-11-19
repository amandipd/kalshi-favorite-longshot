"""The replication on Kalshi's 15-minute markets.

    fetch.py     every settled market in the window, with its quotes each minute -> data/replication/
    dataset.py   those markets, read back
    stats.py     calibration, the Kelly fraction, the regime change and the stop rules
    report.py    all of it -> reports/replication.json, the dashboard's second input
"""
