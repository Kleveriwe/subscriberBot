import asyncio
import config
import database
import logging

from aiogram import Bot, Dispatcher
from handlers import admin, user
from services.subscriptions import check_subscriptions


async def main():
    logging.basicConfig(level=logging.INFO)
    bot = Bot(token=config.BOT_TOKEN, defaults={"parse_mode": "HTML"})
    dp = Dispatcher()
    database.init_db()
    dp.include_router(admin.router)
    dp.include_router(user.router)
    # фон
    asyncio.create_task(check_subscriptions(bot))
    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
