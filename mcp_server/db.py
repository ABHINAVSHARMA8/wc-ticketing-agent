"""
Database access layer — SQLite via a proper connection context manager.
Connections are opened, committed/rolled back, and closed within each call.
Schema is initialised once via init_db() called at app startup.
"""

import contextlib
import logging
import os
import sqlite3

log = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "subscriptions.db")


# ── Connection context manager ────────────────────────────────────────────────

@contextlib.contextmanager
def _db():
    """Open a connection, commit on success, rollback + close on any error."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Schema setup (called once at startup) ────────────────────────────────────

def init_db() -> None:
    """Create tables and run any pending migrations. Call once at startup."""
    with _db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                email         TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS subscriptions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id        TEXT NOT NULL,
                user_email      TEXT NOT NULL,
                price_threshold REAL,
                notify_on       TEXT NOT NULL DEFAULT 'any',
                last_price      REAL NOT NULL,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(match_id, user_email)
            );

            CREATE TABLE IF NOT EXISTS price_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id    TEXT NOT NULL,
                price_usd   REAL NOT NULL,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Idempotent column migrations
        _add_column_if_missing(conn, "subscriptions", "event_title", "TEXT")
        _add_column_if_missing(conn, "subscriptions", "event_venue", "TEXT")
        _add_column_if_missing(conn, "subscriptions", "event_city",  "TEXT")
        _add_column_if_missing(conn, "subscriptions", "event_date",  "TEXT")

    log.info("Database ready: %s", DB_PATH)


def _add_column_if_missing(
    conn: sqlite3.Connection, table: str, column: str, col_type: str
) -> None:
    existing = {
        row[1]
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        log.info("Migration: added column %s.%s", table, column)


# ── Public API ────────────────────────────────────────────────────────────────

def upsert_subscription(
    match_id: str,
    user_email: str,
    last_price: float,
    price_threshold: float | None = None,
    notify_on: str = "any",
    event_title: str = "",
    event_venue: str = "",
    event_city: str = "",
    event_date: str = "",
) -> bool:
    """Insert or update a subscription. Returns True on success."""
    with _db() as conn:
        cur = conn.execute(
            """
            INSERT INTO subscriptions
                (match_id, user_email, price_threshold, notify_on, last_price,
                 event_title, event_venue, event_city, event_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(match_id, user_email) DO UPDATE SET
                price_threshold = excluded.price_threshold,
                notify_on       = excluded.notify_on,
                last_price      = excluded.last_price,
                event_title     = excluded.event_title,
                event_venue     = excluded.event_venue,
                event_city      = excluded.event_city,
                event_date      = excluded.event_date
            """,
            (match_id, user_email, price_threshold, notify_on, last_price,
             event_title, event_venue, event_city, event_date),
        )
        return cur.rowcount > 0


def get_subscriptions_for_user(user_email: str) -> list[dict]:
    with _db() as conn:
        rows = conn.execute(
            "SELECT * FROM subscriptions WHERE user_email = ? ORDER BY created_at DESC",
            (user_email,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_all_active_subscriptions() -> list[dict]:
    with _db() as conn:
        rows = conn.execute("SELECT * FROM subscriptions").fetchall()
    return [dict(r) for r in rows]


def update_last_price(subscription_id: int, new_price: float) -> None:
    with _db() as conn:
        conn.execute(
            "UPDATE subscriptions SET last_price = ? WHERE id = ?",
            (new_price, subscription_id),
        )


def delete_subscription(match_id: str, user_email: str) -> bool:
    with _db() as conn:
        cur = conn.execute(
            "DELETE FROM subscriptions WHERE match_id = ? AND user_email = ?",
            (match_id, user_email),
        )
    return cur.rowcount > 0


def create_user(email: str, password_hash: str) -> bool:
    """Insert a new user. Returns False if email already exists."""
    try:
        with _db() as conn:
            conn.execute(
                "INSERT INTO users (email, password_hash) VALUES (?, ?)",
                (email, password_hash),
            )
        return True
    except sqlite3.IntegrityError:
        return False


def get_user_by_email(email: str) -> dict | None:
    with _db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
    return dict(row) if row else None


def log_price(match_id: str, price: float) -> None:
    with _db() as conn:
        conn.execute(
            "INSERT INTO price_history (match_id, price_usd) VALUES (?, ?)",
            (match_id, price),
        )
