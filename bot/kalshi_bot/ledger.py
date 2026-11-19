"""The bot's ledger: one SQLite file per account (state/<mode>.db) holding its bets, decisions, orders, fills,
paper measurements and settings (meta). The bankroll is the start plus every settled bet's P&L."""
import os
import sqlite3

DB_TIMEOUT = 30            # how long a read or save waits out a lock before it counts as locked (SQLite's own: 5 s)


def connect(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    db = sqlite3.connect(path, timeout=DB_TIMEOUT)
    db.row_factory = sqlite3.Row
    db.executescript("""
    CREATE TABLE IF NOT EXISTS bets (
        id INTEGER PRIMARY KEY, ticker TEXT UNIQUE, series TEXT, window_open REAL, close_ts REAL,
        side TEXT, price REAL, contracts REAL, cost REAL, fee REAL, placed_ts REAL,
        order_id TEXT, client_order_id TEXT, status TEXT, result TEXT, payout REAL, pnl REAL, settled_ts REAL);
    CREATE TABLE IF NOT EXISTS decisions (
        id INTEGER PRIMARY KEY, ts REAL, ticker TEXT UNIQUE, series TEXT, yes_bid REAL, yes_ask REAL,
        fav_side TEXT, fav_price REAL, action TEXT, reason TEXT);
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY, ts REAL, ticker TEXT, client_order_id TEXT, request TEXT, http_status INTEGER, response TEXT);
    CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
    CREATE TABLE IF NOT EXISTS fills (
        id INTEGER PRIMARY KEY, trade_id TEXT UNIQUE, order_id TEXT, ticker TEXT, side TEXT, price REAL, count REAL,
        fee REAL, ts REAL);
    CREATE TABLE IF NOT EXISTS shadow (
        id INTEGER PRIMARY KEY, kind TEXT, ticker TEXT, ts REAL, window_open REAL, close_ts REAL, series TEXT, side TEXT,
        seen REAL, limit_price REAL, asked REAL, filled REAL, lag REAL, extra REAL, cost REAL, fee REAL, status TEXT,
        result TEXT, pnl REAL, settled_ts REAL, UNIQUE(kind, ticker));
    """)
    db.commit()
    return db


def get_meta(db, key, default=None):
    row = db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row[0] if row else default


def set_meta(db, key, value):
    db.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (key, str(value)))


def set_start(db, amount):
    """Set the starting bankroll. The half-the-start halt measures from it, so an older reference goes."""
    set_meta(db, "start", amount)
    db.execute("DELETE FROM meta WHERE key='halt_base'")
    db.commit()


def rebase(db, cash, now):
    """Restart the books from `cash`, what the account now holds for these markets, keeping their history: the start
    becomes cash less the settled P&L, so the bankroll is cash and past results still count (and the P&L in dollars
    stays right). The halt tripwires start over from here, with the half-the-start floor at half of cash. Only with no
    bets open: their cost is out of the cash but not yet in the books. Returns the bankroll it had."""
    old = bankroll(db)
    set_meta(db, "start", round(cash - (old - float(get_meta(db, "start"))), 6))
    set_meta(db, "halt_base", cash)
    set_meta(db, "halt_seen", now)
    db.commit()
    return old


def bankroll(db, at=None):
    """Start plus settled P&L (open bets count at what they cost)."""
    q, args = "SELECT COALESCE(SUM(pnl),0) FROM bets WHERE status!='open'", []
    if at is not None:
        q, args = q + " AND settled_ts <= ?", [at]
    return float(get_meta(db, "start")) + db.execute(q, args).fetchone()[0]


def cash(db):
    return bankroll(db) - db.execute("SELECT COALESCE(SUM(cost+fee),0) FROM bets WHERE status='open'").fetchone()[0]
