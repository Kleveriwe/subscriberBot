import asyncio
import database
import logging
import time
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import Tuple, List


async def check_subscriptions(bot: Bot, interval: int = 60) -> None:
    """
    Фоновая задача, которая каждые `interval` секунд:
      1) Удаляет полностью истёкшие подписки (бан + разбан).
      2) Отправляет напоминания за 1 час до окончания подписки.
    """
    while True:
        now = int(time.time())

        # 1) Удаляем полностью истёкшие подписки
        expired: List[Tuple[int, int]] = database.get_expired_subscriptions()
        for channel_id, user_id in expired:
            try:
                await bot.ban_chat_member(chat_id=channel_id, user_id=user_id, revoke_messages=False)
                await bot.unban_chat_member(chat_id=channel_id, user_id=user_id)
                logging.info(f"[Expired] Removed user {user_id} from channel {channel_id}")
            except Exception as e:
                logging.error(f"Failed to remove user {user_id} from channel {channel_id}: {e}")
            finally:
                database.remove_subscription(channel_id, user_id)

        # 2) Отправляем напоминания за 1 час до окончания (если ещё не отправляли)
        soon: List[Tuple[int, int, int]] = database.get_expiring_subscriptions_1h()
        for channel_id, user_id, expire_at in soon:
            await send_1h_notice(bot, channel_id, user_id, expire_at)
            database.mark_subscription_reminded(channel_id, user_id)

        await asyncio.sleep(interval)


async def send_1h_notice(bot: Bot, channel_id: int, user_id: int, expire_at: int) -> None:
    """
    Отправляет одному пользователю уведомление о том,
    что до окончания подписки на данный канал осталось ≤1 час,
    вместе с кнопкой «Продлить подписку».
    """
    # Узнаём название канала
    ch = database.get_channel(channel_id)
    title = ch["title"] if ch else f"ID {channel_id}"

    # Форматируем время окончания
    dt_str = time.strftime("%d.%m.%Y %H:%M", time.localtime(expire_at))

    text = (
        f"⏰ Ваша подписка на канал «{title}» истекает через 1 час.\n"
        f"📅 <b>Дата окончания:</b> {dt_str}\n\n"
        "Чтобы продлить — нажмите кнопку ниже."
    )

    # Генерируем deep-link на /start=<channel_id>
    bot_username = (await bot.me()).username
    deep_link = f"https://t.me/{bot_username}?start={channel_id}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Продлить подписку", url=deep_link)]
    ])

    try:
        await bot.send_message(chat_id=user_id, text=text, parse_mode="HTML", reply_markup=kb)
        logging.info(f"[Reminder 1h] Sent reminder to user {user_id} for channel {channel_id}")
    except Exception as e:
        logging.error(f"Failed to send 1h reminder to {user_id} for channel {channel_id}: {e}")
