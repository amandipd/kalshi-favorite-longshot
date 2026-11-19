.PHONY: install ingest ingest-trades ingest-open ingest-summary trades-progress trades-watch clean analyze replicate-data replicate figures dashboard test test-study coverage all

# The whole study from Kalshi's public API, start to finish. No account or key
# is needed. The two downloads are resumable: rerun a target to pick up where
# an interrupted run stopped.
all: install ingest ingest-trades clean analyze replicate-data replicate figures test-study

install:
	pip install -r requirements.txt

# ---------------------------------------------------------------- main study

# Pass 1: settled markets of the pinned series (data/manifest/) -> data/raw/
ingest:
	python -m kalshi_calibration.ingest.kalshi

# Pass 2: each market's last trade 1, 6 and 24 hours before close -> data/raw_trades/
# The settled snapshot cannot supply an implied probability (docs/adr/003).
ingest-trades:
	python -m kalshi_calibration.ingest.trades

# Pass 3: each market's FIRST trade after it opened -> data/raw_trades/OPENFIRST/
# Separate research question, not part of the study pipeline: is a newly listed
# market mispriced before its book deepens? See research/opening_price/PREREG.md.
#
# No --window: that selects the fixed-window pass, which is only for the
# prereg's secondary test. Bare, it climbs the ladder, which is the one that
# can actually reach the open on a busy market (config.yaml explains why).
ingest-open:
	python -m kalshi_calibration.ingest.open_trades

# What pass 1 fetched, and how far pass 2 has got (works on a running pull).
ingest-summary:
	python -m kalshi_calibration.ingest.summary
trades-progress:
	python -m kalshi_calibration.ingest.trades_progress
trades-watch:
	python -m kalshi_calibration.ingest.trades_progress --watch

# raw -> interim -> processed, at the study's horizon (T-1h) and at T-6h for
# the horizon check.
clean:
	python -m kalshi_calibration.clean
	python -m kalshi_calibration.clean --horizon 6

# processed -> reports/*.csv and reports/summary.json. Deterministic: the same
# parquet and config.yaml give the same digits, bootstrap seed included.
analyze:
	python -m kalshi_calibration.analysis.report

# ---------------------------------------------------------------- replication

# Every 15-minute crypto, metals and energy market in the window, with its
# quotes each minute -> data/replication/ (about 1.5 hours; resumable).
replicate-data:
	python -m kalshi_calibration.replication.fetch

# data/replication/ -> reports/replication.json
replicate:
	python -m kalshi_calibration.replication.report

# ---------------------------------------------------------------- results

# reports/summary.json + reports/replication.json -> reports/figures/
figures:
	python -m kalshi_calibration.figures

# The key findings on one page at http://localhost:8080, from the same two files.
dashboard:
	python dashboard/server.py

# ---------------------------------------------------------------- tests

# Unit, integration and property-based (Hypothesis) tests. HYPOTHESIS_PROFILE=thorough multiplies the generated
# examples tenfold. `test-study` runs the study's own suite (tests/); `test` adds the bot and the 15-minute research.
# The bot's tests run on a copy of bot/ in a temporary folder, so they never write next to its code.
BOTCOPY = python -c "import os, shutil, tempfile; d = os.path.join(tempfile.mkdtemp(prefix='botcopy-'), 'bot'); shutil.copytree('bot', d, ignore=shutil.ignore_patterns('state', '.env', '*.db', '__pycache__', '.pytest_cache', '.hypothesis')); print(d)"

test-study:
	python -m pytest -q -p no:cacheprovider tests

test: test-study
	d="$$($(BOTCOPY))" && cd "$$d" && python -m pytest -q -p no:cacheprovider
	python -m pytest -q -p no:cacheprovider research/kalshi_15min/tests

# Line and branch coverage of the same three suites, one report (settings in pyproject.toml). Scripts the
# research tests start in their own process are measured too.
coverage:
	python -m coverage erase
	python -m coverage run -m pytest -q -p no:cacheprovider tests
	python -m coverage run -m pytest -q -p no:cacheprovider research/kalshi_15min/tests
	d="$$($(BOTCOPY))" && cd "$$d" && python -m coverage run --rcfile="$(CURDIR)/pyproject.toml" --source=. --omit="tests/*,*/tests/*,test_*.py,conftest.py" -m pytest -q -p no:cacheprovider && cd "$(CURDIR)" && python -m coverage combine . "$$d"
	python -m coverage report
