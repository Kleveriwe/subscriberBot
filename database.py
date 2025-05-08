import sqlite3
import time
import config


def get_connection():
    conn = sqlite3.connect(config.DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                channel_id    INTEGER PRIMARY KEY,
                owner_id      INTEGER NOT NULL,
                title         TEXT    NOT NULL,
                payment_info  TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS tariffs (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id     INTEGER NOT NULL,
                title          TEXT    NOT NULL,
                duration_days  INTEGER NOT NULL,
                price          INTEGER NOT NULL,
                FOREIGN KEY(channel_id) REFERENCES channels(channel_id)
                    ON DELETE CASCADE
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id        INTEGER NOT NULL,
                user_id           INTEGER NOT NULL,
                tariff_id         INTEGER NOT NULL,
                status            TEXT    NOT NULL,
                proof_photo_id    TEXT,
                rejection_reason  TEXT,
                created_at        INTEGER NOT NULL,
                FOREIGN KEY(channel_id) REFERENCES channels(channel_id),
                FOREIGN KEY(tariff_id)  REFERENCES tariffs(id)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                channel_id    INTEGER NOT NULL,
                user_id       INTEGER NOT NULL,
                expire_at     INTEGER NOT NULL,
                PRIMARY KEY(channel_id, user_id),
                FOREIGN KEY(channel_id) REFERENCES channels(channel_id)
                    ON DELETE CASCADE
            )
        """)
        conn.commit()


# Примеры CRUD:

def add_or_update_channel(channel_id: int, owner_id: int, title: str, payment_info: str):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO channels(channel_id, owner_id, title, payment_info)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(channel_id) DO UPDATE
              SET owner_id = excluded.owner_id,
                  title = excluded.title,
                  payment_info = excluded.payment_info
        """, (channel_id, owner_id, title, payment_info))
        conn.commit()


def get_channel(channel_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT channel_id, owner_id, title, payment_info "
            "FROM channels WHERE channel_id = ?", (channel_id,)
        ).fetchone()
        return dict(row) if row else None

# Дополним остальными функциями по аналогии...
