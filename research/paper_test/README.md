# Paper test

## Question

After the live bot stopped placing real orders on Nov 3, 2026, a dry-run copy of it kept making the same decisions
on paper, to see whether the 15-minute favourite rule still earns its edge going forward. The pass bar was set
before the paper run began.

## How to run it

`status.py` reads the dry-run bot's ledger (a SQLite file, opened read-only) and prints the paper test's numbers:
cents of profit for every dollar bet, with a 95% range that counts each 15-minute window once; how many bets lost
against how many the prices predicted; and the windows with six or more losses.

    python research/paper_test/status.py                       # bot/state/dry-prod.db
    python research/paper_test/status.py path/to/ledger.db

The ledger is not included in this repository.

## What it found

No result is recorded here.
