import asyncio
import json
import time

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    BufferedInputFile, CallbackQuery, InlineKeyboardButton,
    InlineKeyboardMarkup, Message,
)

from bot.states import SearchStates
from bot.utils import safe_edit
from core.config import settings
from database.repos import count_searches_today, create_search, finish_search
from osint.name.engine import NameScanner, parse_name_input

router = Router()
LAST_NAME_RESULTS = {}


def render_name_summary(r) -> str:
    return (
        "🕵️ <b>KIANOSINT</b>\n\n"
        "🎯 Цель: <code>{}</code>\n\n"
        "🔎 Запросов выполнено: <b>{}</b>\n"
        "📄 Найдено упоминаний: <b>{}</b>\n"
        "✉️ Email: <b>{}</b>\n"
        "🌐 Сайтов: <b>{}</b>\n\n"
        "⚠️ Всё найденное — <b>возможные совпадения</b>.\n"
        "⚠️ Одинаковое имя не доказывает, что это один человек.\n"
        "⚠️ Используются только публичные источники."
    ).format(
        r.target_value,
        r.stats.sources_checked,
        len(r.findings),
        len(r.contacts.emails),
        len(r.contacts.websites),
    )


def name_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Упоминания", callback_data="name:sources:0")],
        [InlineKeyboardButton(text="📞 Контакты", callback_data="name:contacts")],
        [InlineKeyboardButton(text="📄 JSON", callback_data="name:json")],
        [InlineKeyboardButton(text="🔎 Новый поиск", callback_data="menu:root")],
    ])


@router.message(SearchStates.waiting_name)
async def do_name_search(message: Message, state: FSMContext, session, user) -> None:
    raw = (message.text or "").strip()
    name, context = parse_name_input(raw)
    if not name or len(name) < 2:
        await message.answer(
            "⚠️ Не понял имя. Пример: <code>Ivan Petrov</code>\n"
            "Можно добавить контекст через запятую: <code>Ivan Petrov, Moscow</code>"
        )
        return

    is_admin = user.telegram_id == settings.admin_user_id
    if not is_admin:
        used = await count_searches_today(session, user.id)
        if used >= settings.daily_search_limit:
            await message.answer(
                "🚫 Дневной лимит ({}) исчерпан. Попробуйте завтра.".format(settings.daily_search_limit)
            )
            return

    await state.clear()
    progress_msg = await message.answer(
        "👤 <b>KIANOSINT</b>\n\nИмя: <code>{}</code>\n\n⏳ Ищу публичные упоминания...".format(
            name + ((" | " + context) if context else "")
        )
    )
    search = await create_search(session, user.id, "name", raw)
    started = time.perf_counter()
    last_update = {"t": 0.0}

    async def on_progress(done: int, total: int, src: str) -> None:
        now = time.perf_counter()
        if now - last_update["t"] < 1.0 and done != total:
            return
        last_update["t"] = now
        try:
            await progress_msg.edit_text(
                "👤 <b>KIANOSINT</b>\n\nИмя: <code>{}</code>\n\n"
                "⏳ Запрос: <b>{} / {}</b>".format(name, done, total)
            )
        except Exception:
            pass

    try:
        result = await NameScanner().scan(raw, on_progress=on_progress)
    except Exception as e:
        await progress_msg.edit_text("⚠️ Некоторые источники временно недоступны. Попробуйте позже.")
        await finish_search(
            session, search, status="failed", sources_checked=0, found=0,
            errors=1, duration_ms=int((time.perf_counter() - started) * 1000),
            result_json={"error": str(e)[:300]},
        )
        return

    LAST_NAME_RESULTS[user.telegram_id] = result

    await finish_search(
        session, search, status="done",
        sources_checked=result.stats.sources_checked,
        found=result.stats.found, errors=result.stats.errors,
        duration_ms=int((time.perf_counter() - started) * 1000),
        result_json=json.loads(result.model_dump_json()),
    )

    await progress_msg.edit_text(render_name_summary(result), reply_markup=name_keyboard())


def _get_result(cb: CallbackQuery):
    return LAST_NAME_RESULTS.get(cb.from_user.id)


@router.callback_query(F.data.startswith("name:sources:"))
async def cb_name_sources(cb: CallbackQuery) -> None:
    r = _get_result(cb)
    if not r:
        await cb.answer("Нет активного поиска", show_alert=True)
        return
    page = int(cb.data.split(":")[2])
    items = r.findings
    per_page = 5
    pages = max(1, (len(items) + per_page - 1) // per_page)
    page = max(0, min(page, pages - 1))
    chunk = items[page * per_page:(page + 1) * per_page]
    lines = ["🌐 <b>УПОМИНАНИЯ {}/{}</b>\n".format(page + 1, pages)]
    for f in chunk:
        lines.append("• <b>{}</b>\n  {}\n  {}\n".format(
            (f.title or "—")[:80], f.url, (f.snippet or "")[:150]
        ))
    if not items:
        lines.append("Публичных совпадений не обнаружено.")
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data="name:sources:{}".format(page - 1)))
    if page < pages - 1:
        nav.append(InlineKeyboardButton(text="➡️", callback_data="name:sources:{}".format(page + 1)))
    kb = InlineKeyboardMarkup(
        inline_keyboard=[nav] if nav else [[InlineKeyboardButton(text="🔙 Назад", callback_data="name:contacts")]]
    )
    await safe_edit(cb.message, "\n".join(lines), reply_markup=kb, disable_web_page_preview=True)
    await cb.answer()


@router.callback_query(F.data == "name:contacts")
async def cb_name_contacts(cb: CallbackQuery) -> None:
    r = _get_result(cb)
    if not r:
        await cb.answer("Нет активного поиска", show_alert=True)
        return
    c = r.contacts
    lines = ["📞 <b>ПУБЛИЧНЫЕ КОНТАКТЫ (возможные совпадения)</b>\n"]
    if c.emails:
        lines.append("<b>Email:</b>")
        for p in c.emails:
            lines.append("• {}  ({})".format(p.value, p.source))
    if c.phones:
        lines.append("\n<b>Телефоны:</b>")
        for p in c.phones:
            lines.append("• {}  ({})".format(p.value, p.source))
    if c.websites:
        lines.append("\n<b>Сайты:</b>")
        for p in c.websites:
            lines.append("• {}  ({})".format(p.value, p.source))
    if len(lines) == 1:
        lines.append("Публичные контактные данные не обнаружены.")
    lines.append("\n⚠️ Эти контакты могут не принадлежать искомому человеку.")
    await safe_edit(cb.message, "\n".join(lines), reply_markup=name_keyboard(), disable_web_page_preview=True)
    await cb.answer()


@router.callback_query(F.data == "name:json")
async def cb_name_json(cb: CallbackQuery) -> None:
    r = _get_result(cb)
    if not r:
        await cb.answer("Нет активного поиска", show_alert=True)
        return
    data = json.dumps(json.loads(r.model_dump_json()), ensure_ascii=False, indent=2).encode()
    safe_name = r.target_value.replace(" ", "_").replace("|", "").strip("_")[:40]
    await cb.message.answer_document(
        BufferedInputFile(data, filename="kianosint_name_{}.json".format(safe_name))
    )
    await cb.answer()