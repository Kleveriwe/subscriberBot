from aiogram.fsm.state import StatesGroup, State


class AddChannelState(StatesGroup):
    waiting_username = State()  # ввод ссылки/ID канала
    waiting_payment_info = State()  # ввод реквизитов


class AddTariffState(StatesGroup):
    WAITING_TITLE = State()  # название тарифа
    WAITING_DURATION = State()  # дни
    WAITING_PRICE = State()  # цена


class UserOrderState(StatesGroup):
    WAITING_CHANNEL_ID = State()  # ввод ID канала (если не deep-link)
    WAITING_SCREENSHOT = State()  # ожидание чека


class AdminRejectionState(StatesGroup):
    WAITING_REASON = State()  # ввод причины отклонения
