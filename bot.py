import asyncio
import logging
from aiogram.client.bot import DefaultBotProperties
from aiogram import Bot, Dispatcher
import config
import database

from handlers import admin, user
from services.subscriptions import check_subscriptions


async def main():
    # Настройка логирования
    logging.basicConfig(level=logging.INFO)

    # Инициализация бота
    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()

    # Инициализация БД
    database.init_db()

    # Регистрация роутеров
    dp.include_router(admin.router)
    dp.include_router(user.router)

    # Фоновая задача для проверки истекших подписок
    asyncio.create_task(check_subscriptions(bot))

    # Запуск polling
    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
