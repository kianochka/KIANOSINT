from aiogram.fsm.state import State, StatesGroup


class SearchStates(StatesGroup):
    waiting_username = State()
    waiting_phone = State()
    waiting_name = State()


class AdminStates(StatesGroup):
    waiting_broadcast_text = State()