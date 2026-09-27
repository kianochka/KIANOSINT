import asyncio
import json
import time
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.keyboards.main import result_menu
from bot.states import SearchStates
from bot.utils import safe_edit
from core.config import settings
from core.models import ScanResult
from database.repos import count_searches_today, create_search, finish_search
from osint.username.engine import UsernameScanner, normalize_username, validate_username

router = Router()
LAST_RESULTS = {}


def render_summary(r: ScanResult) -> str:
    s = r.stats
    return (
        "🕵️ <b>KIANOSINT</b>\n\n"
        "🎯 Цель: <code>@{}</code>\n\n"
        "📊 Источников настроено: <b>{}</b>\n"
        "📊 Источников проверено: <b>{}</b>\n"
        "✅ Найдено: <b>{}</b>\n"
        "⚠️ Недоступно: <b>{}</b>\n"
        "❌ Ошибок: <b>{}</b>\n\n"
        "📞 Публичных телефонов: <b>{}</b>\n"
        "✉️ Публичных email: <b>{}</b>\n"
        "🔗 Сигналов связи: <b>{}</b>\n\n"
        "⚠️ Данные собраны из открытых источников.\n"
        "⚠️ Совпадение username не является доказательством личности."
    ).format(
        r.target_value, s.sources_configured, s.sources_checked, s.found,
        s.unavailable, s.errors, len(r.contacts.phones),
        len(r.contacts.emails), len(r.correlations),
    )


@router.message(SearchStates.waiting_username)
async def do_username_search(message: Message, state: FSMContext, session, user) -> None:
    uname = normalize_username(message.text or "")
    if not validate_username(uname):
        await message.answer("⚠️ Некорректный username. Пример: <code>@example_user</code>")
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
        "🔎 <b>KIANOSINT</b>\n\nЦель: <code>@{}</code>\n\n⏳ Выполняю поиск...".format(uname)
    )
    search = await create_search(session, user.id, "username", uname)
    started = time.perf_counter()
    last_update = {"t": 0.0}

    async def on_progress(done: int, total: int, src: str) -> None:
        now = time.perf_counter()
        if now - last_update["t"] < 1.2 and done != total:
            return
        last_update["t"] = now
        try:
            await progress_msg.edit_text(
                "🔎 <b>KIANOSINT</b>\n\nЦель: <code>@{}</code>\n\n"
                "⏳ Проверено: <b>{} / {}</b>\nПоследний источник: {}".format(uname, done, total, src)
            )
        except Exception:
            pass

    try:
        result = await UsernameScanner().scan(uname, on_progress=on_progress)
    except Exception as e:
        await progress_msg.edit_text("⚠️ Некоторые источники временно недоступны. Попробуйте позже.")
        await finish_search(
            session, search, status="failed", sources_checked=0, found=0,
            errors=1, duration_ms=int((time.perf_counter() - started) * 1000),
            result_json={"error": str(e)[:300]},
        )
        return

    await progress_msg.edit_text("🧠 Анализирую связи...")
    await asyncio.sleep(0.2)
    LAST_RESULTS[user.telegram_id] = result

    await finish_search(
        session, search, status="done",
        sources_checked=result.stats.sources_checked,
        found=result.stats.found, errors=result.stats.errors,
        duration_ms=int((time.perf_counter() - started) * 1000),
        result_json=json.loads(result.model_dump_json()),
    )

    await progress_msg.edit_text(render_summary(result), reply_markup=result_menu())


def _get_result(cb: CallbackQuery):
    return LAST_RESULTS.get(cb.from_user.id)


@router.callback_query(F.data == "res:profile")
async def cb_res_profile(cb: CallbackQuery) -> None:
    r = _get_result(cb)
    if not r:
        await cb.answer("Нет активного поиска", show_alert=True)
        return
    profiles = sum(1 for f in r.findings if f.is_found)
    text = (
        "🕵️ <b>KIANOSINT</b>\n\n"
        "🎯 Цель: <code>@{}</code>\n\n"
        "📊 Найдено источников: <b>{}</b>\n"
        "🌐 Публичных профилей: <b>{}</b>\n"
        "📞 Телефонов: <b>{}</b>\n"
        "✉️ Email: <b>{}</b>\n"
        "🔗 Ссылок: <b>{}</b>\n"
        "🧩 Сигналов связи: <b>{}</b>\n\n"
        "⚠️ Данные собраны из открытых источников.\n"
        "⚠️ Совпадение username не является доказательством личности."
    ).format(
        r.target_value, r.stats.found, profiles,
        len(r.contacts.phones), len(r.contacts.emails),
        len(r.contacts.websites), len(r.correlations),
    )
    await safe_edit(cb.message, text, reply_markup=result_menu())
    await cb.answer()


@router.callback_query(F.data.startswith("res:sources:"))
async def cb_res_sources(cb: CallbackQuery) -> None:
    r = _get_result(cb)
    if not r:
        await cb.answer("Нет активного поиска", show_alert=True)
        return
    page = int(cb.data.split(":")[2])
    found = [f for f in r.findings if f.is_found]
    per_page = 5
    pages = max(1, (len(found) + per_page - 1) // per_page)
    page = max(0, min(page, pages - 1))
    chunk = found[page * per_page:(page + 1) * per_page]
    lines = ["🌐 <b>ИСТОЧНИКИ {}/{}</b>\n".format(page + 1, pages)]
    for f in chunk:
        lines.append("• <b>{}</b>\n  {}\n  Статус: найден\n".format(f.source, f.url))
    if not found:
        lines.append("Ничего не найдено.")
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data="res:sources:{}".format(page - 1)))
    if page < pages - 1:
        nav.append(InlineKeyboardButton(text="➡️", callback_data="res:sources:{}".format(page + 1)))
    kb = InlineKeyboardMarkup(
        inline_keyboard=[nav] if nav else [[InlineKeyboardButton(text="🔙 Профиль", callback_data="res:profile")]]
    )
    await safe_edit(cb.message, "\n".join(lines), reply_markup=kb, disable_web_page_preview=True)
    await cb.answer()


@router.callback_query(F.data == "res:corr")
async def cb_res_corr(cb: CallbackQuery) -> None:
    r = _get_result(cb)
    if not r:
        await cb.answer("Нет активного поиска", show_alert=True)
        return
    lines = ["🧩 <b>КОРРЕЛЯЦИЯ</b>\n"]
    if not r.correlations:
        lines.append("Связи не обнаружены.")
    for s in r.correlations:
        lines.append(
            "🔗 {} ↔ {}\n   {}\n   вес: {:.2f}\n".format(s.left_source, s.right_source, s.description, s.weight)
        )
    lines.append("\n⚠️ Сигнал связи не доказывает, что это один человек.")
    await safe_edit(cb.message, "\n".join(lines), reply_markup=result_menu())
    await cb.answer()


@router.callback_query(F.data == "res:contacts")
async def cb_res_contacts(cb: CallbackQuery) -> None:
    r = _get_result(cb)
    if not r:
        await cb.answer("Нет активного поиска", show_alert=True)
        return
    c = r.contacts
    lines = ["📞 <b>ПУБЛИЧНЫЕ КОНТАКТЫ</b>\n"]
    if c.phones:
        lines.append("<b>Телефоны:</b>")
        for p in c.phones:
            lines.append("• {}  ({})".format(p.value, p.source))
    if c.emails:
        lines.append("\n<b>Email:</b>")
        for p in c.emails:
            lines.append("• {}  ({})".format(p.value, p.source))
    if c.websites:
        lines.append("\n<b>Сайты:</b>")
        for p in c.websites:
            lines.append("• {}  ({})".format(p.value, p.source))
    if len(lines) == 1:
        lines.append("Публичные контактные данные не обнаружены.")
    await safe_edit(cb.message, "\n".join(lines), reply_markup=result_menu(), disable_web_page_preview=True)
    await cb.answer()


@router.callback_query(F.data == "res:ai")
async def cb_res_ai(cb: CallbackQuery) -> None:
    r = _get_result(cb)
    if not r:
        await cb.answer("Нет активного поиска", show_alert=True)
        return
    from ai.analyst import analyze
    text = await analyze(r)
    await safe_edit(cb.message, text, reply_markup=result_menu())
    await cb.answer()


@router.callback_query(F.data == "res:json")
async def cb_res_json(cb: CallbackQuery) -> None:
    r = _get_result(cb)
    if not r:
        await cb.answer("Нет активного поиска", show_alert=True)
        return
    data = json.dumps(json.loads(r.model_dump_json()), ensure_ascii=False, indent=2).encode()
    await cb.message.answer_document(BufferedInputFile(data, filename="kianosint_{}.json".format(r.target_value)))
    await cb.answer()


@router.callback_query(F.data == "res:report")
async def cb_res_report(cb: CallbackQuery) -> None:
    r = _get_result(cb)
    if not r:
        await cb.answer("Нет активного поиска", show_alert=True)
        return
    await cb.answer("Готовлю PDF...")
    try:
        from reports.pdf import render_pdf
        import tempfile, os
        path = render_pdf(r)
        with open(path, "rb") as f:
            data = f.read()
        try:
            os.unlink(path)
        except Exception:
            pass
        await cb.message.answer_document(
            BufferedInputFile(data, filename="kianosint_report.pdf")
        )
    except Exception as e:
        log_msg = f"PDF failed: {e}"
        try:
            import logging
            logging.getLogger(__name__).exception(log_msg)
        except Exception:
            pass
        await cb.message.answer(
            "⚠️ Не удалось собрать PDF. Отправляю текстовую версию."
        )
        from reports.text import render_report
        await cb.message.answer(render_report(r)[:4000])