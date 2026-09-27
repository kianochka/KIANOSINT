from aiogram import Dispatcher

from bot.handlers import admin, history, menu, name, phone, profile, start, username


def register_handlers(dp: Dispatcher) -> None:
    dp.include_router(start.router)
    dp.include_router(menu.router)
    dp.include_router(profile.router)
    dp.include_router(history.router)
    dp.include_router(username.router)
    dp.include_router(phone.router)
    dp.include_router(name.router)
    dp.include_router(admin.router)