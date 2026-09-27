import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.handlers import register_handlers
from bot.middlewares.db import DbMiddleware
from core.config import settings
from database.session import init_db
from sources.registry import register_all


async def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    register_all()
    await init_db()

    bot = Bot(settings.telegram_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.update.middleware(DbMiddleware())
    register_handlers(dp)

    from sources.registry import registry
    logging.info("KIANOSINT started. Sources registered: %d", len(registry.all()))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())