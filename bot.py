import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.bot import DefaultBotProperties

import config
import database
from handlers import admin, user
from services.subscriptions import check_subscriptions

logging.basicConfig(level=logging.INFO)


async def main():
    # init DB
    database.init_db()

    # init bot & dispatcher
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML")
    )
    dp  = Dispatcher()

    # include routers
    dp.include_router(admin.router)
    dp.include_router(user.router)

    # start background task
    asyncio.create_task(check_subscriptions(bot))

    # start polling
    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
