from aiogram import Router, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext

import database
import states
from datetime import datetime, timezone, timedelta
from utils import fmt_card, fmt_field, make_keyboard

router = Router()


# -----------------------------
# Пользовательский поток
# -----------------------------
@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()

    text = message.text or ""
    parts = text.split(maxsplit=1)

    if len(parts) > 1:
        try:
            channel_id = int(parts[1])
        except ValueError:
            return await message.answer(
                "❗ Некорректный ID канала. Убедитесь, что у вас ссылка вида\n"
                "`https://t.me/YourBot?start=-123456789`",
                parse_mode="Markdown"
            )
        return await show_tariffs_for_channel(message, channel_id)

    # 2) Просто /start — показываем все три опции сразу
    bot_username = (await message.bot.me()).username
    greeting = fmt_card(
        "Привет!",
        [
            "Я занимаюсь продажей подписок.",
            "",
            fmt_field("➕", "Добавить свой канал", "для продажи подписок"),
        ]
    )
    kb = make_keyboard([
        ("➕ Добавить канал", "start_add_channel"),
    ], row_width=1)

    await message.answer(greeting, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data == "start_add_channel")
async def start_add_channel(callback: types.CallbackQuery):
    await callback.answer()
    # Перенаправляем пользователя на команду /add_my_channel
    await callback.message.answer(
        "Чтобы зарегистрировать свой канал и настроить тарифы, используйте команду:\n"
        "/add_my_channel",
        parse_mode="HTML"
    )


@router.callback_query(F.data == "enter_channel")
async def enter_channel(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    prompt = fmt_card(
        "Ввод ID канала",
        ["Пожалуйста, отправьте числовой ID канала."]
    )
    kb = make_keyboard([("⬅️ Назад", "start")], row_width=1)
    await callback.message.edit_text(prompt, parse_mode="HTML", reply_markup=kb)
    await state.set_state(states.UserOrderState.WAITING_CHANNEL_ID)


@router.message(states.UserOrderState.WAITING_CHANNEL_ID)
async def process_channel_id(message: types.Message, state: FSMContext):
    text = message.text.strip()
    try:
        channel_id = int(text)
    except ValueError:
        return await message.answer("❗ Введите только числовой ID канала.")
    await state.clear()
    return await show_tariffs_for_channel(message, channel_id)


async def show_tariffs_for_channel(message: types.Message, channel_id: int):
    channel = database.get_channel(channel_id)
    if not channel:
        return await message.answer("❗ Канал не найден. Попробуйте другой ID.", parse_mode="HTML")
    tariffs = database.list_tariffs(channel_id)
    if not tariffs:
        return await message.answer("ℹ️ В этом канале нет тарифов.", parse_mode="HTML")

    lines = [fmt_field("💎", t["title"], f"{t['duration_days']} дн — {t['price']}₽") for t in tariffs]
    text = fmt_card(f"Тарифы канала «{channel['title']}»", lines)
    kb = make_keyboard(
        [(f"{t['title']}", f"buy_{channel_id}_{t['id']}") for t in tariffs],
        row_width=1
    )
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("buy_"))
async def callback_buy(callback: types.CallbackQuery, state: FSMContext):
    # Разбираем callback_data вида buy_{channel_id}_{tariff_id}
    raw = callback.data.removeprefix("buy_")
    try:
        channel_str, tariff_str = raw.split("_", 1)
        channel_id = int(channel_str)
        tariff_id = int(tariff_str)
    except Exception:
        return await callback.answer("❗ Ошибка данных", show_alert=True)

    user_id = callback.from_user.id
    # Создаём заявку
    database.create_order(channel_id, user_id, tariff_id)
    channel = database.get_channel(channel_id)
    tariff = database.get_tariff(tariff_id)
    # payment = channel.get("payment_info", "")
    lines = [
        f"Реквизиты: <code>{channel['payment_info']}</code>",
        "",
        fmt_field("🛒", "Тариф", tariff['title']),
        fmt_field("⏳", "Срок", f"{tariff['duration_days']} дн"),
        fmt_field("💰", "Цена", f"{tariff['price']}₽"),
        "",
        "Отправьте скриншот чека после оплаты."
    ]
    text = fmt_card("Оплата", lines)
    kb = make_keyboard([("⬅️ Назад", "start")], row_width=1)
    await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()
    await state.set_state(states.UserOrderState.WAITING_SCREENSHOT)
    await state.update_data(channel_id=channel_id, tariff_id=tariff_id)


@router.message(states.UserOrderState.WAITING_SCREENSHOT, F.photo)
async def receive_screenshot(message: types.Message, state: FSMContext):
    data = await state.get_data()
    channel_id = data.get("channel_id")
    tariff_id = data.get("tariff_id")
    user_id = message.from_user.id
    photo_id = message.photo[-1].file_id

    # Обновляем заявку
    database.update_order_proof(channel_id, user_id, tariff_id, proof_photo_id=photo_id)

    # Уведомляем админа
    channel = database.get_channel(channel_id)
    tariff = database.get_tariff(tariff_id)
    owner = channel["owner_id"]
    mention = (
        f"@{message.from_user.username}" if message.from_user.username
        else f"<a href='tg://user?id={user_id}'>Пользователь</a>"
    )
    lines = [
        f"Заявка от {mention} (ID: <code>{user_id}</code>)",
        fmt_field("📦", "Тариф", tariff['title']),
        fmt_field("⏳", "Срок", f"{tariff['duration_days']} дн"),
        fmt_field("💰", "Цена", f"{tariff['price']}₽")
    ]
    text = fmt_card("Новая заявка", lines)
    kb = make_keyboard([
        ("✅ Подтвердить", f"approve_{channel_id}_{user_id}_{tariff_id}"),
        ("❌ Отклонить", f"reject_{channel_id}_{user_id}_{tariff_id}"),
        ("🙊 Без оповещения", f"reject_silent_{channel_id}_{user_id}_{tariff_id}")
    ], row_width=1)
    await message.bot.send_photo(owner, photo_id, caption=text, parse_mode="HTML", reply_markup=kb)
    await message.answer("✅ Ваш чек отправлен на проверку.")
    await state.clear()


@router.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Действие отменено.")


@router.message(Command("me"))
async def cmd_me(message: types.Message):
    user_id = message.from_user.id
    subs = database.list_user_subscriptions(user_id)
    if not subs:
        return await message.answer(
            "ℹ️ У вас нет активных подписок.",
            parse_mode="HTML"
        )

    # Формируем строки для каждой подписки
    lines = []
    buttons = []
    now_ts = int(datetime.now(tz=timezone.utc).timestamp())
    for s in subs:
        exp_ts = s["expire_at"]
        # Форматируем дату и дни до окончания
        exp_dt = datetime.fromtimestamp(exp_ts, tz=timezone.utc)
        # нужно +3 часа, потому что в UTC+3
        exp_dt += timedelta(hours=3)
        days_left = max((exp_ts - now_ts) // 86400, 0)
        hours_left = (exp_ts - now_ts) // 3600
        if days_left > 0:
            exp_dt_str = f"{days_left} дн"
            if days_left > 1:
                exp_dt_str += "я"
        else:
            exp_dt_str = f"{hours_left % 24} ч"
        lines.append(
            fmt_field("📺", s["channel_title"],
                      f"до {exp_dt.strftime('%d.%m.%Y %H:%M')} ({exp_dt_str})")
        )

    text = fmt_card("Ваши активные подписки", lines)
    await message.answer(text, parse_mode="HTML")
