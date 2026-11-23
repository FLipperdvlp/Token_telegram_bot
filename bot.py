import asyncio
import logging
from aiogram import Bot, Dispatcher
from config import load_config
from database import Store
from handlers import admin, user

async def main():
    logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')
    config = load_config()
    store = Store(config.database_path)
    await store.initialize()
    logging.warning('FileBind: запуск. Для остановки нажмите Ctrl+C. Не запускайте вторую копию бота.')
    bot = Bot(token=config.bot_token)
    dp = Dispatcher()
    dp.include_router(admin.router)
    dp.include_router(user.router)
    try:
        await dp.start_polling(bot, config=config, store=store)
    finally:
        await bot.session.close()

if __name__ == '__main__':
    asyncio.run(main())
