import sqlite3
from contextlib import contextmanager
from typing import Iterator

from .config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    display_name  TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    salt          TEXT NOT NULL,
    avatar        TEXT NOT NULL DEFAULT 'fox',
    theme         TEXT NOT NULL DEFAULT 'light',
    report_currency TEXT NOT NULL DEFAULT 'BYN',
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS accounts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    kind       TEXT NOT NULL,              -- income | card | cash | savings
    owner_id   INTEGER REFERENCES users(id) ON DELETE SET NULL, -- NULL = общий (копилка)
    currency   TEXT NOT NULL DEFAULT 'BYN',-- BYN | USD
    icon       TEXT NOT NULL DEFAULT 'wallet',
    color      TEXT NOT NULL DEFAULT '#6366f1',
    goal_amount REAL NOT NULL DEFAULT 0,       -- цель по сумме (только копилка); 0 = без цели
    sort_order INTEGER NOT NULL DEFAULT 0,
    archived   INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    icon        TEXT NOT NULL DEFAULT 'shopping-cart',
    color       TEXT NOT NULL DEFAULT '#6366f1',
    monthly_limit  REAL NOT NULL DEFAULT 0,     -- 0 = без лимита
    limit_currency TEXT NOT NULL DEFAULT 'BYN',
    sort_order  INTEGER NOT NULL DEFAULT 0,
    archived    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS transactions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    type            TEXT NOT NULL,          -- income | expense | transfer | debt_payment
    amount          REAL NOT NULL,          -- в валюте account_id
    currency        TEXT NOT NULL,          -- валюта amount
    account_id      INTEGER REFERENCES accounts(id) ON DELETE CASCADE,     -- income:dest, expense/debt_payment:src, transfer:src
    dest_account_id INTEGER REFERENCES accounts(id) ON DELETE CASCADE,     -- только transfer
    dest_amount     REAL,                   -- transfer: сумма в валюте dest; debt_payment: сумма в валюте долга
    dest_currency   TEXT,                   -- transfer/debt_payment
    rate_used       REAL,                   -- если была конвертация (USD<->BYN)
    rate_at         REAL,                   -- курс USD->BYN на дату операции (снимок для статистики)
    category_id     INTEGER REFERENCES categories(id) ON DELETE SET NULL,  -- только expense
    debt_id         INTEGER REFERENCES debts(id) ON DELETE CASCADE,        -- только debt_payment
    note            TEXT NOT NULL DEFAULT '',
    occurred_at     TEXT NOT NULL,          -- YYYY-MM-DD
    created_by      INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS debts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    kind            TEXT NOT NULL DEFAULT 'credit',  -- debt | credit | leasing
    creditor        TEXT NOT NULL DEFAULT '',        -- кому/куда платить
    currency        TEXT NOT NULL DEFAULT 'BYN',     -- BYN | USD
    total_amount    REAL NOT NULL DEFAULT 0,         -- полная сумма
    remaining_start REAL NOT NULL DEFAULT 0,         -- остаток на момент добавления
    monthly_payment REAL NOT NULL DEFAULT 0,         -- ежемесячный платёж (справочно)
    icon            TEXT NOT NULL DEFAULT 'landmark',
    color           TEXT NOT NULL DEFAULT '#f43f5e',
    note            TEXT NOT NULL DEFAULT '',
    pay_day         INTEGER NOT NULL DEFAULT 0,  -- 0 = не задан, иначе день месяца
    sort_order      INTEGER NOT NULL DEFAULT 0,
    archived        INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS rates (
    rate_date  TEXT PRIMARY KEY,   -- YYYY-MM-DD
    usd_byn    REAL NOT NULL,      -- 1 USD = usd_byn BYN
    fetched_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_tx_occurred ON transactions(occurred_at);
CREATE INDEX IF NOT EXISTS idx_tx_type ON transactions(type);
"""


def _migrate(conn: sqlite3.Connection) -> None:
    """Лёгкие миграции для баз, созданных до появления новых полей."""
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(transactions)")}
    if "debt_id" not in cols:
        conn.execute("ALTER TABLE transactions ADD COLUMN debt_id INTEGER REFERENCES debts(id)")
    # индекс создаём после того, как колонка гарантированно существует
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tx_debt ON transactions(debt_id)")

    if "rate_at" not in cols:
        conn.execute("ALTER TABLE transactions ADD COLUMN rate_at REAL")
        # Бэкфилл: курс на дату операции (или ближайший ранее известный, иначе последний).
        conn.execute(
            """
            UPDATE transactions
            SET rate_at = COALESCE(
                (SELECT r.usd_byn FROM rates r
                 WHERE r.rate_date <= transactions.occurred_at
                 ORDER BY r.rate_date DESC LIMIT 1),
                (SELECT r.usd_byn FROM rates r ORDER BY r.rate_date DESC LIMIT 1)
            )
            WHERE rate_at IS NULL
            """
        )

    acc_cols = {row["name"] for row in conn.execute("PRAGMA table_info(accounts)")}
    if "goal_amount" not in acc_cols:
        conn.execute("ALTER TABLE accounts ADD COLUMN goal_amount REAL NOT NULL DEFAULT 0")

    cat_cols = {row["name"] for row in conn.execute("PRAGMA table_info(categories)")}
    if "monthly_limit" not in cat_cols:
        conn.execute("ALTER TABLE categories ADD COLUMN monthly_limit REAL NOT NULL DEFAULT 0")
        conn.execute("ALTER TABLE categories ADD COLUMN limit_currency TEXT NOT NULL DEFAULT 'BYN'")

    debt_cols = {row["name"] for row in conn.execute("PRAGMA table_info(debts)")}
    if "pay_day" not in debt_cols:
        conn.execute("ALTER TABLE debts ADD COLUMN pay_day INTEGER NOT NULL DEFAULT 0")


def init_db() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        _migrate(conn)
        conn.commit()


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(settings.db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    try:
        yield conn
    finally:
        conn.close()
