import database
import states
from aiogram import Router, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from datetime import datetime, timezone, timedelta
from utils import fmt_card, fmt_field, make_keyboard

router = Router()


# -----------------------------
# Помощник для разбора callback_data
# -----------------------------
def parse_cd(data: str, prefix: str, parts: int = 1) -> list[str]:
    """
    Убирает префикс и разбивает строку по '_' не более чем на parts элементов.
    """
    payload = data.removeprefix(prefix)
    items = payload.split("_", parts)
    if len(items) < parts:
        raise ValueError(f"Bad callback_data: {data}")
    return items


# -----------------------------
# /start
# -----------------------------
@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()

    # Если deep-link с ID: /start <channel_id>
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        try:
            channel_id = int(args[1])
            return await show_tariffs_for_channel(message, channel_id)
        except ValueError:
            return await message.answer(
                "❗ Некорректный ID канала.\n"
                "Используйте ссылку вида:\n"
                "`https://t.me/YourBot?start=-123456789`",
                parse_mode="Markdown"
            )

    # Обычное приветствие
    bot_username = (await message.bot.me()).username
    text = fmt_card(
        "Привет!",
        [
            "Я помогу вам купить доступ в закрытый канал.",
            "",
            fmt_field("➕", "Добавить канал", "для продажи собственных подписок"),
        ]
    )
    kb = make_keyboard([
        ("➕ Добавить канал", "start_add_channel"),
    ], row_width=1)
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data == "start_add_channel")
async def start_add_channel(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "Чтобы зарегистрировать свой канал и настроить тарифы, используйте команду:\n"
        "/add_my_channel",
        parse_mode="HTML"
    )


# -----------------------------
# Ввод ID вручную
# -----------------------------
@router.callback_query(F.data == "enter_channel")
async def enter_channel(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    text = fmt_card("Ввод ID канала", ["Пожалуйста, отправьте числовой ID канала."])
    kb = make_keyboard([("⬅️ Назад", "start")], row_width=1)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await state.set_state(states.UserOrderState.WAITING_CHANNEL_ID)


@router.message(states.UserOrderState.WAITING_CHANNEL_ID)
async def process_channel_id(message: types.Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit() and not (text.startswith("-") and text[1:].isdigit()):
        return await message.answer("❗ Введите корректный числовой ID канала.")
    channel_id = int(text)
    await state.clear()
    await show_tariffs_for_channel(message, channel_id)


# -----------------------------
# Показ тарифов
# -----------------------------
async def show_tariffs_for_channel(message: types.Message, channel_id: int):
    channel = database.get_channel(channel_id)
    if not channel:
        return await message.answer("❗ Канал не найден. Проверьте ID.", parse_mode="HTML")

    tariffs = database.list_tariffs(channel_id)
    if not tariffs:
        return await message.answer("ℹ️ В этом канале нет доступных тарифов.", parse_mode="HTML")

    lines = [fmt_field("💎", t["title"], f"{t['duration_days']} дн — {t['price']}₽") for t in tariffs]
    text = fmt_card(f"Тарифы «{channel['title']}»", lines)
    kb = make_keyboard(
        [(t["title"], f"buy_{channel_id}_{t['id']}") for t in tariffs],
        row_width=1
    )
    await message.answer(text, parse_mode="HTML", reply_markup=kb)

@router.callback_query(F.data.startswith("back_to_tariffs_"))
async def back_to_tariffs(callback: types.CallbackQuery, state: FSMContext):
    # Извлекаем channel_id
    channel_id = int(callback.data.removeprefix("back_to_tariffs_"))

    # Убираем «часики» и удаляем текущее сообщение
    await callback.answer()
    await callback.message.delete()

    # Сбрасывать состояние не нужно,
    # просто выводим снова список тарифов
    await show_tariffs_for_channel(callback.message, channel_id)

# -----------------------------
# Покупка тарифа
# -----------------------------
@router.callback_query(F.data.startswith("buy_"))
async def callback_buy(callback: types.CallbackQuery, state: FSMContext):
    try:
        channel_str, tariff_str = parse_cd(callback.data, prefix="buy_", parts=2)
        channel_id = int(channel_str)
        tariff_id = int(tariff_str)
    except Exception:
        return await callback.answer("❗ Ошибка данных", show_alert=True)

    user_id = callback.from_user.id
    database.create_order(channel_id, user_id, tariff_id)

    channel = database.get_channel(channel_id)
    tariff = database.get_tariff(tariff_id)
    lines = [
        f"Реквизиты: <code>{channel['payment_info']}</code>",
        "",
        fmt_field("🛒", "Тариф", tariff["title"]),
        fmt_field("⏳", "Срок", f"{tariff['duration_days']} дн"),
        fmt_field("💰", "Цена", f"{tariff['price']}₽"),
        "",
        "После оплаты отправьте скриншот чека."
    ]
    text = fmt_card("Оплата", lines)
    kb = make_keyboard([("⬅️ Назад", f"back_to_tariffs_{channel_id}")], row_width=1)

    await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()
    await state.set_state(states.UserOrderState.WAITING_SCREENSHOT)
    await state.update_data(channel_id=channel_id, tariff_id=tariff_id)


# -----------------------------
# Приём скриншота
# -----------------------------
@router.message(states.UserOrderState.WAITING_SCREENSHOT, F.photo)
async def receive_screenshot(message: types.Message, state: FSMContext):
    data = await state.get_data()
    channel_id = data["channel_id"]
    tariff_id = data["tariff_id"]
    user_id = message.from_user.id
    photo = message.photo[-1].file_id

    database.update_order_proof(channel_id, user_id, tariff_id, proof_photo_id=photo)

    channel = database.get_channel(channel_id)
    tariff = database.get_tariff(tariff_id)
    owner_id = channel["owner_id"]
    mention = (f"@{message.from_user.username}"
               if message.from_user.username
               else f"<a href='tg://user?id={user_id}'>Пользователь</a>")

    lines = [
        f"Заявка от {mention} (ID: <code>{user_id}</code>)",
        fmt_field("📦", "Тариф", tariff["title"]),
        fmt_field("⏳", "Срок", f"{tariff['duration_days']} дн"),
        fmt_field("💰", "Цена", f"{tariff['price']}₽"),
    ]
    text = fmt_card("Новая заявка", lines)
    kb = make_keyboard([
        ("✅ Подтвердить", f"approve_{channel_id}_{user_id}_{tariff_id}"),
        ("❌ Отклонить", f"reject_{channel_id}_{user_id}_{tariff_id}"),
        ("🙊 Без оповещения", f"reject_silent_{channel_id}_{user_id}_{tariff_id}")
    ], row_width=1)

    await message.bot.send_photo(owner_id, photo, caption=text,
                                 parse_mode="HTML", reply_markup=kb)
    await message.answer("✅ Ваш чек отправлен на проверку.", parse_mode="HTML")
    await state.clear()


# -----------------------------
# /cancel
# -----------------------------
@router.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Действие отменено.", parse_mode="HTML")


# -----------------------------
# /me — Личный кабинет
# -----------------------------
@router.message(Command("me"))
async def cmd_me(message: types.Message):
    user_id = message.from_user.id
    subs = database.list_user_subscriptions(user_id)
    if not subs:
        return await message.answer("ℹ️ У вас нет активных подписок.", parse_mode="HTML")

    now_ts = int(datetime.now(tz=timezone.utc).timestamp())
    lines = []
    for s in subs:
        exp_ts = s["expire_at"]
        exp_dt = datetime.fromtimestamp(exp_ts, tz=timezone.utc) + timedelta(hours=3)
        delta = exp_ts - now_ts
        days_left = delta // 86400
        hours_left = (delta % 86400) // 3600
        if days_left > 0:
            rem = f"{days_left} дн"
        else:
            rem = f"{hours_left} ч"
        lines.append(fmt_field("📺", s["channel_title"],
                               f"до {exp_dt.strftime('%d.%m.%Y %H:%M')} ({rem})"))

    text = fmt_card("Ваши подписки", lines)
    await message.answer(text, parse_mode="HTML")
