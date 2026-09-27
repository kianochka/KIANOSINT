from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot.keyboards.main import back_to_main, main_menu
from bot.states import SearchStates
from bot.utils import safe_edit
from core.config import settings

router = Router()


@router.callback_query(F.data == "menu:root")
async def cb_root(cb: CallbackQuery, user, state: FSMContext) -> None:
    await state.clear()
    is_admin = user.telegram_id == settings.admin_user_id
    await safe_edit(
        cb.message,
        "🕵️ <b>KIANOSINT</b>\n\nOSINT-поиск по публичным источникам.\n\nВыберите тип поиска:",
        reply_markup=main_menu(is_admin=is_admin),
    )
    await cb.answer()


@router.callback_query(F.data == "menu:username")
async def cb_username(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SearchStates.waiting_username)
    await safe_edit(
        cb.message,
        "🔎 <b>Username OSINT</b>\n\n"
        "Отправь username для поиска.\n\n"
        "Пример:\n<code>@username</code>\n\n"
        "KIANOSINT проверит публичные источники и соберёт найденные совпадения.",
        reply_markup=back_to_main(),
    )
    await cb.answer()


@router.callback_query(F.data == "menu:phone")
async def cb_phone(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SearchStates.waiting_phone)
    await safe_edit(
        cb.message,
        "📱 <b>Phone OSINT</b>\n\n"
        "Отправь номер в международном формате.\n\n"
        "Примеры:\n<code>+79991234567</code>\n<code>+48 123 456 789</code>\n\n"
        "Будут собраны только публичные упоминания номера: сайты, форумы, каталоги, "
        "объявления и открытые страницы.",
        reply_markup=back_to_main(),
    )
    await cb.answer()


@router.callback_query(F.data == "menu:name")
async def cb_name(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SearchStates.waiting_name)
    await safe_edit(
        cb.message,
        "👤 <b>Name OSINT</b>\n\n"
        "Отправь имя для поиска.\n\n"
        "Пример:\n<code>Ivan Petrov</code>\n\n"
        "Можно добавить контекст через запятую:\n"
        "<code>Ivan Petrov, Moscow, Russia</code>\n\n"
        "Все результаты помечаются как <b>возможные совпадения</b>.",
        reply_markup=back_to_main(),
    )
    await cb.answer()


@router.callback_query(F.data == "menu:help")
async def cb_help(cb: CallbackQuery) -> None:
    await safe_edit(
        cb.message,
        "ℹ️ <b>Помощь</b>\n\n"
        "KIANOSINT собирает <b>только публично доступные</b> данные из открытых источников.\n\n"
        "• Совпадение username не подтверждает личность.\n"
        "• Результат — набор evidence и сигналов связи, а не приговор.\n"
        "• Скрытые данные не извлекаются.\n"
        "• Если совпадений нет — это не значит, что данных не существует.",
        reply_markup=back_to_main(),
    )
    await cb.answer()