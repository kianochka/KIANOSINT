from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu(is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🔎 Username OSINT", callback_data="menu:username")],
        [InlineKeyboardButton(text="📱 Phone OSINT", callback_data="menu:phone")],
        [InlineKeyboardButton(text="👤 Name OSINT", callback_data="menu:name")],
        [InlineKeyboardButton(text="📚 История", callback_data="menu:history"),
         InlineKeyboardButton(text="👤 Мой профиль", callback_data="menu:profile")],
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="menu:help")],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton(text="🛠 Админ-панель", callback_data="admin:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_to_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Меню", callback_data="menu:root")]])


def result_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Профиль", callback_data="res:profile"),
         InlineKeyboardButton(text="🌐 Источники", callback_data="res:sources:0")],
        [InlineKeyboardButton(text="🧩 Корреляция", callback_data="res:corr"),
         InlineKeyboardButton(text="📞 Контакты", callback_data="res:contacts")],
        [InlineKeyboardButton(text="🤖 AI Анализ", callback_data="res:ai"),
         InlineKeyboardButton(text="📄 JSON", callback_data="res:json")],
        [InlineKeyboardButton(text="📑 Полный отчёт", callback_data="res:report")],
        [InlineKeyboardButton(text="🔎 Новый поиск", callback_data="menu:root")],
    ])