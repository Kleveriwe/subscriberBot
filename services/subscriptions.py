import asyncio, logging, database


async def check_subscriptions(bot, interval: int = 30):
    while True:
        await asyncio.sleep(interval)
        expired = database.get_expired_subscriptions()
        for channel_id, user_id in expired:
            try:
                await bot.ban_chat_member(channel_id, user_id, revoke_messages=False)
                await bot.unban_chat_member(channel_id, user_id)
                logging.info(f"Удалил {user_id} из {channel_id} по истечении подписки")
            except Exception as e:
                logging.error(f"Ошибка снятия подписки {user_id}: {e}")
            else:
                database.remove_subscription(channel_id, user_id)
