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
from osint.phone.engine import PhoneScanner, normalize_phone, phone_meta

router = Router()
LAST_PHONE_RESULTS = {}


def render_phone_summary(r) -> str:
    meta = phone_meta(r.target_value) if r.target_value else {}
    return (
        "🕵️ <b>KIANOSINT</b>\n\n"
        "🎯 Номер: <code>{}</code>\n\n"
        "🌍 Страна: <b>{}</b>\n"
        "📍 Локация: <b>{}</b>\n"
        "🏢 Оператор: <b>{}</b>\n"
        "📱 Тип: <b>{}</b>\n"
        "✅ Валидный: <b>{}</b>\n\n"
        "🔎 Публичных упоминаний: <b>{}</b>\n"
        "✉️ Email: <b>{}</b>\n"
        "🌐 Сайтов: <b>{}</b>\n\n"
        "⚠️ Если совпадений нет — это не значит, что номера не существует.\n"
        "⚠️ Используются только публичные источники."
    ).format(
        r.target_value,
        meta.get("country") or "—",
        meta.get("location") or "—",
        meta.get("carrier") or "—",
        meta.get("type") or "—",
        "да" if meta.get("is_valid") else "нет",
        max(0, len(r.findings) - 1),
        len(r.contacts.emails),
        len(r.contacts.websites),
    )


def phone_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Упоминания", callback_data="phone:sources:0")],
        [InlineKeyboardButton(text="📞 Инфо о номере", callback_data="phone:info")],
        [InlineKeyboardButton(text="📄 JSON", callback_data="phone:json")],
        [InlineKeyboardButton(text="🔎 Новый поиск", callback_data="menu:root")],
    ])


@router.message(SearchStates.waiting_phone)
async def do_phone_search(message: Message, state: FSMContext, session, user) -> None:
    raw = (message.text or "").strip()
    e164 = normalize_phone(raw)
    if e164 is None:
        await message.answer(
            "⚠️ Не удалось распознать номер.\n"
            "Отправь в международном формате, например: <code>+79991234567</code>"
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
        "📱 <b>KIANOSINT</b>\n\nНомер: <code>{}</code>\n\n⏳ Ищу публичные упоминания...".format(e164)
    )
    search = await create_search(session, user.id, "phone", e164)
    started = time.perf_counter()
    last_update = {"t": 0.0}

    async def on_progress(done: int, total: int, src: str) -> None:
        now = time.perf_counter()
        if now - last_update["t"] < 1.0 and done != total:
            return
        last_update["t"] = now
        try:
            await progress_msg.edit_text(
                "📱 <b>KIANOSINT</b>\n\nНомер: <code>{}</code>\n\n"
                "⏳ Этап: <b>{} / {}</b>\nИсточник: {}".format(e164, done, total, src)
            )
        except Exception:
            pass

    try:
        result = await PhoneScanner().scan(e164, on_progress=on_progress)
    except Exception as e:
        await progress_msg.edit_text("⚠️ Некоторые источники временно недоступны. Попробуйте позже.")
        await finish_search(
            session, search, status="failed", sources_checked=0, found=0,
            errors=1, duration_ms=int((time.perf_counter() - started) * 1000),
            result_json={"error": str(e)[:300]},
        )
        return

    LAST_PHONE_RESULTS[user.telegram_id] = result

    await finish_search(
        session, search, status="done",
        sources_checked=result.stats.sources_checked,
        found=result.stats.found, errors=result.stats.errors,
        duration_ms=int((time.perf_counter() - started) * 1000),
        result_json=json.loads(result.model_dump_json()),
    )

    await progress_msg.edit_text(render_phone_summary(result), reply_markup=phone_keyboard())


def _get_result(cb: CallbackQuery):
    return LAST_PHONE_RESULTS.get(cb.from_user.id)


@router.callback_query(F.data == "phone:info")
async def cb_phone_info(cb: CallbackQuery) -> None:
    r = _get_result(cb)
    if not r:
        await cb.answer("Нет активного поиска", show_alert=True)
        return
    meta = phone_meta(r.target_value)
    tz = ", ".join(meta.get("timezones") or []) or "—"
    text = (
        "📞 <b>Информация о номере</b>\n\n"
        "Номер (E.164): <code>{}</code>\n"
        "Национальный: <code>{}</code>\n"
        "Международный: <code>{}</code>\n\n"
        "🌍 Страна: {}\n"
        "📍 Локация: {}\n"
        "🏢 Оператор: {}\n"
        "📱 Тип: {}\n"
        "🕒 Часовые пояса: {}\n"
        "✅ Валидный: {}"
    ).format(
        r.target_value,
        meta.get("national") or "—",
        meta.get("international") or "—",
        meta.get("country") or "—",
        meta.get("location") or "—",
        meta.get("carrier") or "—",
        meta.get("type") or "—",
        tz,
        "да" if meta.get("is_valid") else "нет",
    )
    await safe_edit(cb.message, text, reply_markup=phone_keyboard())
    await cb.answer()


@router.callback_query(F.data.startswith("phone:sources:"))
async def cb_phone_sources(cb: CallbackQuery) -> None:
    r = _get_result(cb)
    if not r:
        await cb.answer("Нет активного поиска", show_alert=True)
        return
    page = int(cb.data.split(":")[2])
    items = [f for f in r.findings if f.url]
    per_page = 5
    pages = max(1, (len(items) + per_page - 1) // per_page)
    page = max(0, min(page, pages - 1))
    chunk = items[page * per_page:(page + 1) * per_page]
    lines = ["🌐 <b>ПУБЛИЧНЫЕ УПОМИНАНИЯ {}/{}</b>\n".format(page + 1, pages)]
    for f in chunk:
        lines.append("• <b>{}</b>\n  {}\n  {}".format(
            f.title or f.source, f.url, (f.snippet or "")[:200]
        ))
    if not items:
        lines.append("Публичных совпадений не обнаружено.")
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data="phone:sources:{}".format(page - 1)))
    if page < pages - 1:
        nav.append(InlineKeyboardButton(text="➡️", callback_data="phone:sources:{}".format(page + 1)))
    kb = InlineKeyboardMarkup(
        inline_keyboard=[nav] if nav else [[InlineKeyboardButton(text="🔙 Назад", callback_data="phone:info")]]
    )
    await safe_edit(cb.message, "\n".join(lines), reply_markup=kb, disable_web_page_preview=True)
    await cb.answer()


@router.callback_query(F.data == "phone:json")
async def cb_phone_json(cb: CallbackQuery) -> None:
    r = _get_result(cb)
    if not r:
        await cb.answer("Нет активного поиска", show_alert=True)
        return
    data = json.dumps(json.loads(r.model_dump_json()), ensure_ascii=False, indent=2).encode()
    await cb.message.answer_document(
        BufferedInputFile(data, filename="kianosint_phone_{}.json".format(r.target_value.replace("+", "")))
    )
    await cb.answer()