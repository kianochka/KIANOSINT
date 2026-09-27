from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.keyboards.main import back_to_main
from bot.utils import safe_edit
from core.config import settings
from database.repos import count_searches_today

router = Router()


@router.callback_query(F.data == "menu:profile")
async def cb_profile(cb: CallbackQuery, session, user) -> None:
    today = await count_searches_today(session, user.id)
    is_admin = user.telegram_id == settings.admin_user_id
    text = (
        "👤 <b>Мой профиль</b>\n\n"
        "Имя: {}\n"
        "Username: @{}\n"
        "Telegram ID: <code>{}</code>\n\n"
        "📅 Поисков сегодня: {}\n"
        "🎚 План: {}\n"
        "🛠 Администратор: {}"
    ).format(
        user.first_name or "-",
        user.username or "-",
        user.telegram_id,
        today,
        user.plan,
        "Да" if is_admin else "Нет",
    )
    await safe_edit(cb.message, text, reply_markup=back_to_main())
    await cb.answer()