import sqlite3
import time
import config


def get_connection():
    """
    Возвращает соединение с БД SQLite, с включёнными foreign_keys и row_factory.
    """
    conn = sqlite3.connect(config.DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """
    Создаёт таблицы, если их ещё нет.
    """
    with get_connection() as conn:
        c = conn.cursor()
        # Таблица каналов
        c.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                channel_id    INTEGER PRIMARY KEY,
                owner_id      INTEGER NOT NULL,
                title         TEXT    NOT NULL,
                payment_info  TEXT
            )
        """)
        # Таблица тарифов
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
        # Таблица заказов
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
        # Таблица подписок
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
        c.execute("""
                PRAGMA table_info(subscriptions)
            """)
        cols = [row[1] for row in c.fetchall()]  # извлечём список колонок
        if "reminded_1h" not in cols:
            c.execute("""
                    ALTER TABLE subscriptions
                    ADD COLUMN reminded_1h INTEGER NOT NULL DEFAULT 0
                """)
        conn.commit()


# -----------------------------
# Каналы
# -----------------------------

def add_or_update_channel(channel_id: int, owner_id: int, title: str, payment_info: str):
    """
    Вставляет новый канал или обновляет существующий
    с помощью INSERT OR REPLACE (работает на старых SQLite).
    """
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO channels(channel_id, owner_id, title, payment_info) "
            "VALUES (?, ?, ?, ?)",
            (channel_id, owner_id, title, payment_info)
        )
        conn.commit()


def get_channel(channel_id: int) -> dict | None:
    """
    Возвращает канал по ID или None.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT channel_id, owner_id, title, payment_info"
            " FROM channels WHERE channel_id = ?",
            (channel_id,)
        ).fetchone()
        return dict(row) if row else None


def list_channels_of_owner(owner_id: int) -> list[dict]:
    """
    Список каналов, зарегистрированных данным администратором.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT channel_id, owner_id, title FROM channels WHERE owner_id = ?",
            (owner_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def update_channel_payment_info(channel_id, new_info):
    with get_connection() as conn:
        conn.execute(
            "UPDATE channels SET payment_info = ? WHERE channel_id = ?",
            (new_info, channel_id)
        )
        conn.commit()

    return


def delete_channel(channel_id: int):
    """
    Удаляет канал по его ID.
    """
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM channels WHERE channel_id = ?",
            (channel_id,)
        )
        conn.commit()


# -----------------------------
# Тарифы
# -----------------------------

def add_tariff(channel_id: int, title: str, duration_days: int, price: int):
    """
    Добавляет новый тариф для канала.
    """
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO tariffs(channel_id, title, duration_days, price)"
            " VALUES (?, ?, ?, ?)",
            (channel_id, title, duration_days, price)
        )
        conn.commit()


def list_tariffs(channel_id: int) -> list[dict]:
    """
    Возвращает список тарифов для канала.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, channel_id, title, duration_days, price"
            " FROM tariffs WHERE channel_id = ? ORDER BY id",
            (channel_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def remove_tariff(tariff_id: int):
    """
    Удаляет тариф по его ID.
    """
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM tariffs WHERE id = ?",
            (tariff_id,)
        )
        conn.commit()


def get_tariff(tariff_id: int) -> dict | None:
    """
    Возвращает данные тарифа по ID или None.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, channel_id, title, duration_days, price"
            " FROM tariffs WHERE id = ?",
            (tariff_id,)
        ).fetchone()
        return dict(row) if row else None


# -----------------------------
# Заказы
# -----------------------------

def create_order(channel_id: int, user_id: int, tariff_id: int):
    """
    Создаёт новую заявку со статусом 'pending'.
    """
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO orders"
            " (channel_id, user_id, tariff_id, status, created_at)"
            " VALUES (?, ?, ?, 'pending', ?)",
            (channel_id, user_id, tariff_id, int(time.time()))
        )
        conn.commit()


def update_order_proof(channel_id: int, user_id: int, tariff_id: int, proof_photo_id: str):
    """
    Обновляет заявку, устанавливает proof_photo_id и переводит в статус 'awaiting'.
    """
    with get_connection() as conn:
        conn.execute(
            "UPDATE orders SET proof_photo_id = ?, status = 'awaiting'"
            " WHERE channel_id=? AND user_id=? AND tariff_id=? AND status='pending'",
            (proof_photo_id, channel_id, user_id, tariff_id)
        )
        conn.commit()


def approve_order(channel_id: int, user_id: int, tariff_id: int):
    """
    Меняет статус заявки на 'approved'.
    """
    with get_connection() as conn:
        conn.execute(
            "UPDATE orders SET status = 'approved'"
            " WHERE channel_id=? AND user_id=? AND tariff_id=?"
            " AND status IN ('pending','awaiting')",
            (channel_id, user_id, tariff_id)
        )
        conn.commit()


def reject_order(channel_id: int, user_id: int, tariff_id: int, reason: str):
    """
    Меняет статус заявки на 'rejected' и сохраняет причину.
    """
    with get_connection() as conn:
        conn.execute(
            "UPDATE orders SET status = 'rejected', rejection_reason = ?"
            " WHERE channel_id=? AND user_id=? AND tariff_id=?"
            " AND status IN ('pending','awaiting')",
            (reason, channel_id, user_id, tariff_id)
        )
        conn.commit()


# -----------------------------
# Подписки
# -----------------------------

def add_subscription(channel_id: int, user_id: int, duration_days: int):
    now = int(time.time())
    conn = get_connection()
    cursor = conn.cursor()

    # Смотрим, была ли уже подписка
    cursor.execute("""
        SELECT expire_at
        FROM subscriptions
        WHERE channel_id = ? AND user_id = ?
    """, (channel_id, user_id))
    row = cursor.fetchone()

    if row:
        old_expire = row["expire_at"]
        base = old_expire if old_expire > now else now
        new_expire = base + duration_days * 24 * 3600
        cursor.execute("""
            UPDATE subscriptions
               SET expire_at    = ?,
                   reminded_1h  = 0
             WHERE channel_id   = ?
               AND user_id      = ?
        """, (new_expire, channel_id, user_id))
    else:
        new_expire = now + duration_days * 24 * 3600
        cursor.execute("""
            INSERT INTO subscriptions(
                channel_id, user_id, expire_at, reminded_1h
            ) VALUES (?, ?, ?, 0)
        """, (channel_id, user_id, new_expire))

    conn.commit()
    conn.close()


def get_expired_subscriptions() -> list[tuple[int, int]]:
    """
    Возвращает список (channel_id, user_id) подписок, у которых истёк expire_at.
    """
    now = int(time.time())
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT channel_id, user_id FROM subscriptions WHERE expire_at < ?",
            (now,)
        ).fetchall()
        return [(r["channel_id"], r["user_id"]) for r in rows]


def remove_subscription(channel_id: int, user_id: int):
    """
    Удаляет запись о подписке.
    """
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM subscriptions WHERE channel_id=? AND user_id=?",
            (channel_id, user_id)
        )
        conn.commit()


def list_user_subscriptions(user_id: int) -> list[dict]:
    """
    Возвращает список активных подписок пользователя:
    [
      {
        "channel_id":   -1001234567890,
        "channel_title":"Мой Канал",
        "expire_at":    1700000000
      },
      …
    ]
    """
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT s.channel_id,
                   c.title     AS channel_title,
                   s.expire_at
            FROM subscriptions AS s
            JOIN channels AS c
              ON s.channel_id = c.channel_id
            WHERE s.user_id = ?
            ORDER BY s.expire_at ASC
        """, (user_id,)).fetchall()

    result = []
    for r in rows:
        result.append({
            "channel_id": r["channel_id"],
            "channel_title": r["channel_title"],
            "expire_at": r["expire_at"],
        })
    return result


def get_expiring_subscriptions_1h():
    """
    Возвращает подписки, у которых expire_at ∈ (now, now+1ч]
       и по которым ещё не слали напоминание (reminded_1h = 0).
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


def mark_subscription_reminded(channel_id: int, user_id: int):
    """
    Помечает подписку (channel_id, user_id)
    как уже получившую 1-часовое напоминание.
    """
    with get_connection() as conn:
        conn.execute("""
            UPDATE subscriptions
               SET reminded_1h = 1
             WHERE channel_id = ? AND user_id = ?
        """, (channel_id, user_id))
        conn.commit()
