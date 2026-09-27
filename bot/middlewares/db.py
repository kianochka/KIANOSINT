from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from database.repos import get_or_create_user, touch_user
from database.session import SessionLocal


class DbMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Пытаемся достать from_user из любого типа апдейта.
        from_user = getattr(event, "from_user", None)

        if from_user is None:
            message = getattr(event, "message", None)
            callback = getattr(event, "callback_query", None)
            inline = getattr(event, "inline_query", None)

            if message is not None:
                from_user = message.from_user
            elif callback is not None:
                from_user = callback.from_user
            elif inline is not None:
                from_user = inline.from_user

        async with SessionLocal() as session:
            data["session"] = session
            if from_user is not None:
                user = await get_or_create_user(
                    session,
                    from_user.id,
                    username=from_user.username,
                    first_name=from_user.first_name,
                    last_name=from_user.last_name,
                )
                await touch_user(session, user)
                data["user"] = user
            return await handler(event, data)