"""
Database access layer — PostgreSQL via psycopg2.
Connections are opened, committed/rolled back, and closed within each call.
Schema is initialised once via init_db() called at app startup.
"""

import contextlib
import logging
import os

import psycopg2
import psycopg2.extras
from psycopg2 import IntegrityError

log = logging.getLogger(__name__)


# ── Connection context manager ────────────────────────────────────────────────

@contextlib.contextmanager
def _db():
    """Open a connection, commit on success, rollback + close on any error."""
    url = os.environ["DATABASE_URL"]
    # Render (and some other hosts) emit postgres:// — psycopg2 wants postgresql://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    conn = psycopg2.connect(url)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _cur(conn):
    """Return a RealDictCursor so rows behave like dicts."""
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


# ── Schema setup (called once at startup) ────────────────────────────────────

def init_db() -> None:
    """Create tables and run any pending migrations. Call once at startup."""
    with _db() as conn:
        cur = _cur(conn)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            SERIAL PRIMARY KEY,
                email         TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id              SERIAL PRIMARY KEY,
                match_id        TEXT NOT NULL,
                user_email      TEXT NOT NULL,
                price_threshold REAL,
                notify_on       TEXT NOT NULL DEFAULT 'any',
                last_price      REAL NOT NULL,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(match_id, user_email)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS price_history (
                id          SERIAL PRIMARY KEY,
                match_id    TEXT NOT NULL,
                price_usd   REAL NOT NULL,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Idempotent column migrations
        _add_column_if_missing(conn, "subscriptions", "event_title", "TEXT")
        _add_column_if_missing(conn, "subscriptions", "event_venue", "TEXT")
        _add_column_if_missing(conn, "subscriptions", "event_city",  "TEXT")
        _add_column_if_missing(conn, "subscriptions", "event_date",  "TEXT")

    log.info("Database ready")


def _add_column_if_missing(
    conn, table: str, column: str, col_type: str
) -> None:
    cur = _cur(conn)
    cur.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s
        """,
        (table, column),
    )
    if cur.fetchone() is None:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
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
        cur = _cur(conn)
        cur.execute(
            """
            INSERT INTO subscriptions
                (match_id, user_email, price_threshold, notify_on, last_price,
                 event_title, event_venue, event_city, event_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT(match_id, user_email) DO UPDATE SET
                price_threshold = EXCLUDED.price_threshold,
                notify_on       = EXCLUDED.notify_on,
                last_price      = EXCLUDED.last_price,
                event_title     = EXCLUDED.event_title,
                event_venue     = EXCLUDED.event_venue,
                event_city      = EXCLUDED.event_city,
                event_date      = EXCLUDED.event_date
            """,
            (match_id, user_email, price_threshold, notify_on, last_price,
             event_title, event_venue, event_city, event_date),
        )
        return cur.rowcount > 0


def get_subscriptions_for_user(user_email: str) -> list[dict]:
    with _db() as conn:
        cur = _cur(conn)
        cur.execute(
            "SELECT * FROM subscriptions WHERE user_email = %s"
            " ORDER BY created_at DESC",
            (user_email,),
        )
        return [dict(r) for r in cur.fetchall()]


def get_all_active_subscriptions() -> list[dict]:
    with _db() as conn:
        cur = _cur(conn)
        cur.execute("SELECT * FROM subscriptions")
        return [dict(r) for r in cur.fetchall()]


def update_last_price(subscription_id: int, new_price: float) -> None:
    with _db() as conn:
        cur = _cur(conn)
        cur.execute(
            "UPDATE subscriptions SET last_price = %s WHERE id = %s",
            (new_price, subscription_id),
        )


def delete_subscription(match_id: str, user_email: str) -> bool:
    with _db() as conn:
        cur = _cur(conn)
        cur.execute(
            "DELETE FROM subscriptions WHERE match_id = %s AND user_email = %s",
            (match_id, user_email),
        )
        return cur.rowcount > 0


def create_user(email: str, password_hash: str) -> bool:
    """Insert a new user. Returns False if email already exists."""
    try:
        with _db() as conn:
            cur = _cur(conn)
            cur.execute(
                "INSERT INTO users (email, password_hash) VALUES (%s, %s)",
                (email, password_hash),
            )
        return True
    except IntegrityError:
        return False


def get_user_by_email(email: str) -> dict | None:
    with _db() as conn:
        cur = _cur(conn)
        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        row = cur.fetchone()
    return dict(row) if row else None


def log_price(match_id: str, price: float) -> None:
    with _db() as conn:
        cur = _cur(conn)
        cur.execute(
            "INSERT INTO price_history (match_id, price_usd) VALUES (%s, %s)",
            (match_id, price),
        )
