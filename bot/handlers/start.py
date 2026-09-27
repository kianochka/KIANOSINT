from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from bot.keyboards.main import main_menu
from core.config import settings

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, user) -> None:
    is_admin = user.telegram_id == settings.admin_user_id
    text = ("🕵️ <b>KIANOSINT</b>\n\n"
            "OSINT-поиск по публичным источникам.\n\n"
            "Выберите тип поиска:")
    await message.answer(text, reply_markup=main_menu(is_admin=is_admin))