from aiogram.fsm.state import StatesGroup, State


class AddChannelState(StatesGroup):
    WAITING_USERNAME = State()  # Ожидаем @username, ссылку или ID канала
    WAITING_PAYMENT_INFO = State()  # Ожидаем реквизиты для оплаты


class AddTariffState(StatesGroup):
    WAITING_TITLE = State()  # Ожидаем название тарифа
    WAITING_DURATION = State()  # Ожидаем длительность (дней)
    WAITING_PRICE = State()  # Ожидаем цену (рублей)


class UserOrderState(StatesGroup):
    WAITING_CHANNEL_ID = State()  # Ожидаем ID канала (если не через deep-link)
    WAITING_SCREENSHOT = State()  # Ожидаем скриншот чека


class AdminRejectionState(StatesGroup):
    WAITING_REASON = State()  # Ожидаем текст причины отклонения


class UpdatePaymentState(StatesGroup):
    WAITING_NEW_PAYMENT_INFO = State()