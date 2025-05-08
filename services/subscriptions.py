import asyncio
import logging
import time

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import database
import config


async def check_subscriptions(bot: Bot, interval: int = 60):
    while True:
        now = int(time.time())

        # 1) Удаляем истёкшие
        expired = database.get_expired_subscriptions()
        for channel_id, user_id in expired:
            ...  # ваша текущая логика бана/убана
            database.remove_subscription(channel_id, user_id)

        # 2) Берем подписки, которым осталось ≤1ч и reminder ещё не отправлен
        soon = database.get_expiring_subscriptions_1h()
        for channel_id, user_id, expire_at in soon:
            await send_1h_notice(bot, channel_id, user_id, expire_at)
            # Помечаем, что напоминание отправлено
            database.mark_subscription_reminded(channel_id, user_id)

        await asyncio.sleep(interval)


async def send_1h_notice(bot: Bot, channel_id: int, user_id: int, expire_at: int):
    """
    Отправляет пользователю уведомление, что до окончания подписки
    в канале осталось ≤1 часа, с кнопкой «Продлить подписку».
    """
    # Получаем информацию о канале
    ch = database.get_channel(channel_id)
    title = ch["title"] if ch else f"ID {channel_id}"

    # Форматируем время окончания
    dt_str = time.strftime("%d.%m.%Y %H:%M", time.localtime(expire_at))

    # Собираем текст уведомления
    text = (
        f"⏰ Ваша подписка на канал «{title}» истекает через 1 час.\n"
        f"📅 <b>Дата окончания:</b> {dt_str}\n\n"
        "Чтобы продлить подписку, нажмите кнопку ниже."
    )

    # Генерируем deep-link на /start=<channel_id>
    bot_username = (await bot.me()).username
    deep_link = f"https://t.me/{bot_username}?start={channel_id}"

    # Клавиатура с кнопкой «Продлить подписку»
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Продлить подписку", url=deep_link)]
    ])

    # Отправляем уведомление
    try:
        await bot.send_message(
            chat_id=user_id,
            text=text,
            parse_mode="HTML",
            reply_markup=kb
        )
        logging.info(f"[Reminder 1h] Sent renewal notice to user {user_id} for channel {channel_id}")
    except Exception as e:
        logging.error(f"Failed to send 1h reminder to {user_id} for channel {channel_id}: {e}")
