from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.keyboards.main import back_to_main
from bot.utils import safe_edit
from database.repos import recent_searches

router = Router()


@router.callback_query(F.data == "menu:history")
async def cb_history(cb: CallbackQuery, session, user) -> None:
    rows = await recent_searches(session, user.id, limit=10)
    if not rows:
        text = "📚 <b>История</b>\n\nПока пусто."
    else:
        lines = ["📚 <b>История</b>\n"]
        for i, s in enumerate(rows, 1):
            dt = s.created_at.strftime("%d.%m.%Y %H:%M")
            lines.append(
                "{}. [{}] <code>{}</code> — {} ({})".format(
                    i, s.target_type, s.target_value, dt, s.status
                )
            )
        text = "\n".join(lines)
    await safe_edit(cb.message, text, reply_markup=back_to_main())
    await cb.answer()