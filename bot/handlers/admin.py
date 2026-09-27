from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message,
)

from bot.states import AdminStates
from bot.utils import safe_edit
from core.config import settings
from database.repos import (
    all_user_ids,
    avg_duration_ms,
    count_searches,
    count_users,
    list_searches,
    list_source_health,
    list_users,
    searches_today,
    stats_by_type,
)
from sources.registry import registry

router = Router()


def _is_admin(uid: int) -> bool:
    return uid == settings.admin_user_id


def admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats")],
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin:users:0")],
        [InlineKeyboardButton(text="🔎 Поиски", callback_data="admin:searches:0")],
        [InlineKeyboardButton(text="🌐 Источники", callback_data="admin:sources")],
        [InlineKeyboardButton(text="🧪 System Health", callback_data="admin:health")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin:broadcast")],
        [InlineKeyboardButton(text="🔙 Меню", callback_data="menu:root")],
    ])


def back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Админ-панель", callback_data="admin:menu")],
    ])


@router.message(Command("admin"))
async def cmd_admin(message: Message, user) -> None:
    if not _is_admin(user.telegram_id):
        await message.answer("⛔️ Доступ запрещён.")
        return
    await message.answer("🛠 <b>Админ-панель</b>", reply_markup=admin_menu_kb())


@router.callback_query(F.data == "admin:menu")
async def cb_admin_menu(cb: CallbackQuery, user) -> None:
    if not _is_admin(user.telegram_id):
        await cb.answer("⛔️", show_alert=True)
        return
    await safe_edit(cb.message, "🛠 <b>Админ-панель</b>", reply_markup=admin_menu_kb())
    await cb.answer()


# ---------- Статистика ----------

@router.callback_query(F.data == "admin:stats")
async def cb_admin_stats(cb: CallbackQuery, session, user) -> None:
    if not _is_admin(user.telegram_id):
        await cb.answer("⛔️", show_alert=True)
        return

    users = await count_users(session)
    total = await count_searches(session)
    today = await searches_today(session)
    by_type = await stats_by_type(session)
    avg_ms = await avg_duration_ms(session)

    lines = [
        "📊 <b>Статистика</b>\n",
        "👥 Пользователей: <b>{}</b>".format(users),
        "🔎 Всего поисков: <b>{}</b>".format(total),
        "📅 Поисков сегодня: <b>{}</b>".format(today),
        "⏱ Среднее время: <b>{:.2f} сек</b>".format(avg_ms / 1000.0 if avg_ms else 0),
        "",
        "<b>По типам:</b>",
    ]
    for t in ("username", "phone", "name"):
        lines.append("  • {}: {}".format(t, by_type.get(t, 0)))
    for t, c in by_type.items():
        if t not in ("username", "phone", "name"):
            lines.append("  • {}: {}".format(t, c))

    await safe_edit(cb.message, "\n".join(lines), reply_markup=back_kb())
    await cb.answer()


# ---------- Пользователи ----------

PER_PAGE = 10


@router.callback_query(F.data.startswith("admin:users:"))
async def cb_admin_users(cb: CallbackQuery, session, user) -> None:
    if not _is_admin(user.telegram_id):
        await cb.answer("⛔️", show_alert=True)
        return
    page = int(cb.data.split(":")[2])
    total = await count_users(session)
    pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    page = max(0, min(page, pages - 1))

    users = await list_users(session, limit=PER_PAGE, offset=page * PER_PAGE)
    lines = ["👥 <b>Пользователи</b> ({}) — стр. {}/{}\n".format(total, page + 1, pages)]
    for u in users:
        name = (u.first_name or "") + ((" " + u.last_name) if u.last_name else "")
        name = name.strip() or "—"
        uname = "@{}".format(u.username) if u.username else "—"
        flag = "🛠 " if u.telegram_id == settings.admin_user_id else ""
        lines.append(
            "{}<b>{}</b>\n"
            "  ID: <code>{}</code>\n"
            "  {} | план: {} | с {}\n".format(
                flag, name, u.telegram_id, uname, u.plan,
                u.created_at.strftime("%d.%m.%Y"),
            )
        )
    if not users:
        lines.append("Пользователей нет.")

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data="admin:users:{}".format(page - 1)))
    if page < pages - 1:
        nav.append(InlineKeyboardButton(text="➡️", callback_data="admin:users:{}".format(page + 1)))
    nav.append(InlineKeyboardButton(text="🔙 Админ-панель", callback_data="admin:menu"))

    kb = InlineKeyboardMarkup(inline_keyboard=[nav])
    await safe_edit(cb.message, "\n".join(lines), reply_markup=kb, disable_web_page_preview=True)
    await cb.answer()


# ---------- Поиски ----------

@router.callback_query(F.data.startswith("admin:searches:"))
async def cb_admin_searches(cb: CallbackQuery, session, user) -> None:
    if not _is_admin(user.telegram_id):
        await cb.answer("⛔️", show_alert=True)
        return
    page = int(cb.data.split(":")[2])
    total = await count_searches(session)
    pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    page = max(0, min(page, pages - 1))

    rows = await list_searches(session, limit=PER_PAGE, offset=page * PER_PAGE)
    lines = ["🔎 <b>Поиски</b> ({}) — стр. {}/{}\n".format(total, page + 1, pages)]
    for s in rows:
        lines.append(
            "#{} [{}] <code>{}</code>\n"
            "  {} — найдено {}, ошибок {}, {:.1f}с\n".format(
                s.id, s.target_type, s.target_value,
                s.created_at.strftime("%d.%m %H:%M"),
                s.found_count, s.error_count, s.duration_ms / 1000.0,
            )
        )
    if not rows:
        lines.append("Поисков нет.")

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data="admin:searches:{}".format(page - 1)))
    if page < pages - 1:
        nav.append(InlineKeyboardButton(text="➡️", callback_data="admin:searches:{}".format(page + 1)))
    nav.append(InlineKeyboardButton(text="🔙 Админ-панель", callback_data="admin:menu"))

    kb = InlineKeyboardMarkup(inline_keyboard=[nav])
    await safe_edit(cb.message, "\n".join(lines), reply_markup=kb, disable_web_page_preview=True)
    await cb.answer()


# ---------- Источники ----------

@router.callback_query(F.data == "admin:sources")
async def cb_admin_sources(cb: CallbackQuery, user) -> None:
    if not _is_admin(user.telegram_id):
        await cb.answer("⛔️", show_alert=True)
        return
    srcs = registry.all()
    lines = ["🌐 <b>Источники</b> ({})\n".format(len(srcs))]
    for s in srcs:
        flag = "🟢" if s.is_configured() else "🟡"
        lines.append("{} {}".format(flag, s.name))
    await safe_edit(cb.message, "\n".join(lines), reply_markup=back_kb())
    await cb.answer()


# ---------- System Health ----------

@router.callback_query(F.data == "admin:health")
async def cb_admin_health(cb: CallbackQuery, session, user) -> None:
    if not _is_admin(user.telegram_id):
        await cb.answer("⛔️", show_alert=True)
        return

    rows = await list_source_health(session)
    if not rows:
        text = (
            "🧪 <b>System Health</b>\n\n"
            "Пока нет данных — health собирается после поисков.\n"
            "Прогони пару username-поисков, потом заходи сюда снова."
        )
        await safe_edit(cb.message, text, reply_markup=back_kb())
        await cb.answer()
        return

    lines = ["🧪 <b>System Health</b>\n"]
    for sh in rows[:40]:
        total = sh.success_count + sh.error_count
        rate = (sh.success_count / total * 100) if total else 0
        if rate >= 80:
            mark = "🟢"
        elif rate >= 40:
            mark = "🟡"
        else:
            mark = "🔴"
        lines.append(
            "{} <b>{}</b>\n"
            "  успех: {} | ошибок: {} | таймаутов: {}\n"
            "  средн.: {} мс\n".format(
                mark, sh.source,
                sh.success_count, sh.error_count, sh.timeout_count,
                sh.avg_response_ms,
            )
        )
    await safe_edit(cb.message, "\n".join(lines), reply_markup=back_kb())
    await cb.answer()


# ---------- Рассылка ----------

@router.callback_query(F.data == "admin:broadcast")
async def cb_admin_broadcast(cb: CallbackQuery, state: FSMContext, user) -> None:
    if not _is_admin(user.telegram_id):
        await cb.answer("⛔️", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_broadcast_text)
    await safe_edit(
        cb.message,
        "📢 <b>Рассылка</b>\n\n"
        "Отправь текст сообщения. Он уйдёт всем пользователям бота.\n\n"
        "Поддерживается HTML: &lt;b&gt;жирный&lt;/b&gt;, &lt;i&gt;курсив&lt;/i&gt;, &lt;a href=\"...\"&gt;ссылка&lt;/a&gt;.\n\n"
        "Отмена — /cancel",
        reply_markup=back_kb(),
    )
    await cb.answer()


@router.message(Command("cancel"))
async def cmd_cancel_broadcast(message: Message, state: FSMContext, user) -> None:
    if not _is_admin(user.telegram_id):
        return
    await state.clear()
    await message.answer("❌ Рассылка отменена.", reply_markup=admin_menu_kb())


@router.message(AdminStates.waiting_broadcast_text)
async def do_broadcast(message: Message, state: FSMContext, session, user) -> None:
    if not _is_admin(user.telegram_id):
        return
    text = (message.html_text or message.text or "").strip()
    if not text:
        await message.answer("⚠️ Пустое сообщение. Отправь текст или /cancel.")
        return

    await state.clear()
    user_ids = await all_user_ids(session)
    if not user_ids:
        await message.answer("👥 Нет пользователей для рассылки.")
        return

    status_msg = await message.answer(
        "📢 Рассылка запущена. Получателей: <b>{}</b>...".format(len(user_ids))
    )
    sent = 0
    failed = 0
    for uid in user_ids:
        try:
            await message.bot.send_message(uid, text, disable_web_page_preview=True)
            sent += 1
        except Exception:
            failed += 1
        # мягкий антифлуд
        import asyncio as _a
        await _a.sleep(0.05)

    await status_msg.edit_text(
        "✅ Рассылка завершена.\n\n"
        "Доставлено: <b>{}</b>\n"
        "Не доставлено: <b>{}</b>".format(sent, failed),
        reply_markup=admin_menu_kb(),
    )