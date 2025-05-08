import config
import time
import sqlite3
from typing import Optional, List, Tuple, Dict, Any



def get_connection() -> sqlite3.Connection:
    """
    Создаёт и возвращает соединение с БД SQLite,
    с включёнными foreign_keys и row_factory=Row.
    """
    conn = sqlite3.connect(config.DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """
    Создаёт все таблицы, если они ещё не существуют,
    и добавляет колонку reminded_1h в subscriptions при необходимости.
    """
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
                reminded_1h   INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(channel_id, user_id),
                FOREIGN KEY(channel_id) REFERENCES channels(channel_id)
                    ON DELETE CASCADE
            )
        """)
        # Нет нужды отдельно ALTER TABLE для reminded_1h,
        # если сразу создаём с DEFAULT 0.


# -----------------------------
# Каналы
# -----------------------------

def add_or_update_channel(channel_id: int, owner_id: int, title: str, payment_info: str) -> None:
    """
    Вставляет или обновляет канал.
    """
    with get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO channels(
                channel_id, owner_id, title, payment_info
            ) VALUES (?, ?, ?, ?)
        """, (channel_id, owner_id, title, payment_info))


def get_channel(channel_id: int) -> Optional[Dict[str, Any]]:
    """
    Возвращает запись из channels или None.
    """
    with get_connection() as conn:
        row = conn.execute("""
            SELECT channel_id, owner_id, title, payment_info
              FROM channels
             WHERE channel_id = ?
        """, (channel_id,)).fetchone()
    return dict(row) if row else None


def list_channels_of_owner(owner_id: int) -> List[Dict[str, Any]]:
    """
    Список всех каналов, принадлежащих owner_id.
    """
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT channel_id, owner_id, title
              FROM channels
             WHERE owner_id = ?
        """, (owner_id,)).fetchall()
    return [dict(r) for r in rows]


def update_channel_payment_info(channel_id: int, payment_info: str) -> None:
    """
    Обновляет поле payment_info у указанного канала.
    """
    with get_connection() as conn:
        conn.execute("""
            UPDATE channels
               SET payment_info = ?
             WHERE channel_id = ?
        """, (payment_info, channel_id))


def delete_channel(channel_id: int) -> None:
    """
    Удаляет канал (и каскадно все связанные тарифы, заказы, подписки).
    """
    with get_connection() as conn:
        conn.execute("""
            DELETE FROM channels
             WHERE channel_id = ?
        """, (channel_id,))


# -----------------------------
# Тарифы
# -----------------------------

def add_tariff(channel_id: int, title: str, duration_days: int, price: int) -> None:
    """
    Добавляет тариф к указанному каналу.
    """
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO tariffs(channel_id, title, duration_days, price)
            VALUES (?, ?, ?, ?)
        """, (channel_id, title, duration_days, price))


def list_tariffs(channel_id: int) -> List[Dict[str, Any]]:
    """
    Список тарифов для channel_id.
    """
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id, channel_id, title, duration_days, price
              FROM tariffs
             WHERE channel_id = ?
             ORDER BY id ASC
        """, (channel_id,)).fetchall()
    return [dict(r) for r in rows]


def remove_tariff(tariff_id: int) -> None:
    """
    Удаляет тариф по ID.
    """
    with get_connection() as conn:
        conn.execute("""
            DELETE FROM tariffs
             WHERE id = ?
        """, (tariff_id,))


def get_tariff(tariff_id: int) -> Optional[Dict[str, Any]]:
    """
    Возвращает тариф или None.
    """
    with get_connection() as conn:
        row = conn.execute("""
            SELECT id, channel_id, title, duration_days, price
            FROM tariffs
            WHERE id = ?
        """, (tariff_id,)).fetchone()
    return dict(row) if row else None


# -----------------------------
# Заказы
# -----------------------------

def create_order(channel_id: int, user_id: int, tariff_id: int) -> None:
    """
    Создаёт новую заявку в status='pending'.
    """
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO orders(channel_id, user_id, tariff_id, status, created_at)
            VALUES (?, ?, ?, 'pending', ?)
        """, (channel_id, user_id, tariff_id, int(time.time())))


def update_order_proof(channel_id: int, user_id: int, tariff_id: int, proof_photo_id: str) -> None:
    """
    Сохраняет proof_photo_id и переводит заявку в 'awaiting'.
    """
    with get_connection() as conn:
        conn.execute("""
            UPDATE orders
               SET proof_photo_id = ?, status = 'awaiting'
             WHERE channel_id=? AND user_id=? AND tariff_id=? AND status='pending'
        """, (proof_photo_id, channel_id, user_id, tariff_id))


def approve_order(channel_id: int, user_id: int, tariff_id: int) -> None:
    """
    Переводит заявку в status='approved'.
    """
    with get_connection() as conn:
        conn.execute("""
            UPDATE orders
               SET status = 'approved'
             WHERE channel_id=? AND user_id=? AND tariff_id=?
               AND status IN ('pending','awaiting')
        """, (channel_id, user_id, tariff_id))


def reject_order(channel_id: int, user_id: int, tariff_id: int, reason: str) -> None:
    """
    Отмечает заявку как rejected и сохраняет reason.
    """
    with get_connection() as conn:
        conn.execute("""
            UPDATE orders
               SET status = 'rejected', rejection_reason = ?
             WHERE channel_id=? AND user_id=? AND tariff_id=?
               AND status IN ('pending','awaiting')
        """, (reason, channel_id, user_id, tariff_id))


# -----------------------------
# Подписки
# -----------------------------

def add_subscription(channel_id: int, user_id: int, duration_days: int) -> None:
    """
    Добавляет или продлевает подписку,
    сбрасывая reminded_1h в 0 при продлении.
    """
    now = int(time.time())
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT expire_at
              FROM subscriptions
             WHERE channel_id=? AND user_id=?
        """, (channel_id, user_id))
        row = cur.fetchone()

        if row:
            old = row["expire_at"]
            base = old if old > now else now
            new_expire = base + duration_days * 86400
            cur.execute("""
                UPDATE subscriptions
                   SET expire_at   = ?, reminded_1h = 0
                 WHERE channel_id = ? AND user_id = ?
            """, (new_expire, channel_id, user_id))
        else:
            new_expire = now + duration_days * 86400
            cur.execute("""
                INSERT INTO subscriptions(
                    channel_id, user_id, expire_at, reminded_1h
                ) VALUES (?, ?, ?, 0)
            """, (channel_id, user_id, new_expire))


def get_expired_subscriptions() -> List[Tuple[int, int]]:
    """
    Подписки, у которых expire_at < now.
    """
    now = int(time.time())
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT channel_id, user_id
              FROM subscriptions
             WHERE expire_at < ?
        """, (now,)).fetchall()
    return [(r["channel_id"], r["user_id"]) for r in rows]


def remove_subscription(channel_id: int, user_id: int) -> None:
    """
    Удаляет запись о подписке.
    """
    with get_connection() as conn:
        conn.execute("""
            DELETE FROM subscriptions
             WHERE channel_id=? AND user_id=?
        """, (channel_id, user_id))


def list_user_subscriptions(user_id: int) -> List[Dict[str, Any]]:
    """
    Активные подписки пользователя (joined with channel titles).
    """
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT s.channel_id,
                   c.title     AS channel_title,
                   s.expire_at
              FROM subscriptions AS s
              JOIN channels      AS c
                ON s.channel_id = c.channel_id
             WHERE s.user_id = ?
             ORDER BY s.expire_at ASC
        """, (user_id,)).fetchall()
    return [{"channel_id": r["channel_id"],
             "channel_title": r["channel_title"],
             "expire_at": r["expire_at"]}
            for r in rows]


def get_expiring_subscriptions_1h() -> List[Tuple[int, int, int]]:
    """
    Подписки с expire_at ∈ (now, now+1ч] и reminded_1h = 0.
    """
    now = int(time.time())
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT channel_id, user_id, expire_at
              FROM subscriptions
             WHERE expire_at > ?
               AND expire_at <= ?
               AND reminded_1h = 0
        """, (now, now + 3600)).fetchall()
    return [(r["channel_id"], r["user_id"], r["expire_at"]) for r in rows]


def mark_subscription_reminded(channel_id: int, user_id: int) -> None:
    """
    Помечает reminded_1h = 1, чтобы не слать повторно.
    """
    with get_connection() as conn:
        conn.execute("""
            UPDATE subscriptions
               SET reminded_1h = 1
             WHERE channel_id = ? AND user_id = ?
        """, (channel_id, user_id))
