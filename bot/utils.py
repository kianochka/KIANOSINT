from typing import Optional

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup


async def safe_edit(message, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None,
                    disable_web_page_preview: bool = False) -> bool:
    """edit_text, который молча игнорирует 'message is not modified'."""
    try:
        await message.edit_text(
            text,
            reply_markup=reply_markup,
            disable_web_page_preview=disable_web_page_preview,
        )
        return True
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            return False
        raise