from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

import database
import states
import time
from utils import fmt_card, fmt_field, make_keyboard

router = Router()


# -----------------------------
# Регистрация канала
# -----------------------------
@router.message(Command("add_my_channel"))
async def cmd_add_my_channel(message: types.Message, state: FSMContext):
    text = fmt_card(
        "Регистрация канала",
        [
            "1️⃣ Добавьте бота администратором в ваш канал.",
            "2️⃣ Нажмите кнопку ниже и отправьте ссылку или ID канала.",
            "3️⃣ Внутри канала вызовите команду /id, чтобы получить ID канала."
        ]
    )
    kb = make_keyboard([
        ("📡 Указать канал", "enter_admin_channel"),
        ("❌ Отмена", "cancel_admin")
    ], row_width=1)
    await message.answer(text, parse_mode="HTML", reply_markup=kb)
    await state.set_state(states.AddChannelState.waiting_username)


@router.callback_query(F.data == "cancel_admin")
async def cancel_admin(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.answer()


@router.callback_query(F.data == "enter_admin_channel")
async def enter_admin_channel(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    text = fmt_card(
        "Укажите канал",
        ["Отправьте @username, ссылку или числовой ID канала."]
    )
    kb = make_keyboard([
        ("⬅️ Назад", "add_my_channel"),
        ("❌ Отмена", "cancel_admin")
    ], row_width=1)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await state.set_state(states.AddChannelState.waiting_username)


@router.message(states.AddChannelState.waiting_username)
async def process_channel_username(message: types.Message, state: FSMContext):
    raw = message.text.strip()
    cleaned = raw.replace("https://t.me/", "").replace("t.me/", "").strip()
    try:
        chat = await message.bot.get_chat(cleaned)
        bot_id = (await message.bot.me()).id
        member = await message.bot.get_chat_member(chat.id, bot_id)
        if member.status not in ("administrator", "creator"):
            return await message.answer("❗ Бот не является администратором в этом канале.", parse_mode="HTML")
    except Exception:
        return await message.answer(
            "❗ Не удалось получить информацию о канале. Проверьте права и данные.",
            parse_mode="HTML"
        )

    await state.update_data(
        channel_id=chat.id,
        channel_title=chat.title,
        owner_id=message.from_user.id
    )
    text = fmt_card(
        "Реквизиты для оплаты",
        [
            f"Канал: <b>{chat.title}</b> (ID: <code>{chat.id}</code>)",
            "Отправьте реквизиты: номер карты, QIWI и т.п."
        ]
    )
    kb = make_keyboard([
        ("⬅️ Назад", "add_my_channel"),
        ("❌ Отмена", "cancel_admin")
    ], row_width=1)
    await message.answer(text, parse_mode="HTML", reply_markup=kb)
    await state.set_state(states.AddChannelState.waiting_payment_info)


@router.message(states.AddChannelState.waiting_payment_info)
async def process_payment_info(message: types.Message, state: FSMContext):
    data = await state.get_data()
    channel_id = data["channel_id"]
    owner_id = data["owner_id"]
    title = data["channel_title"]
    payment = message.text.strip()

    database.add_or_update_channel(channel_id, owner_id, title, payment)

    deep_link = f"https://t.me/{(await message.bot.me()).username}?start={channel_id}"
    text = fmt_card(
        "Канал сохранён",
        [
            f"Канал: <b>{title}</b> (ID: <code>{channel_id}</code>)",
            f"Реквизиты: {payment}",
            f"Ссылка для пользователя: <code>{deep_link}</code>"
        ]
    )
    kb = make_keyboard([
        ("➡️ Меню канала", f"channel_menu_{channel_id}"),
        ("❌ Отмена", "cancel_admin")
    ], row_width=1)
    await message.answer(text, parse_mode="HTML", reply_markup=kb)
    await state.clear()


# -----------------------------
# Меню каналов
# -----------------------------
@router.message(Command("my_channels"))
async def cmd_my_channels(message: types.Message):
    owner_id = message.from_user.id
    channels = database.list_channels_of_owner(owner_id)
    if not channels:
        return await message.answer("ℹ️ У вас нет зарегистрированных каналов.", parse_mode="HTML")

    lines = [fmt_field("•", ch["title"], f"ID: <code>{ch['channel_id']}</code>") for ch in channels]
    text = fmt_card("Ваши каналы", lines)
    kb = make_keyboard([(ch['title'], f"channel_menu_{ch['channel_id']}") for ch in channels], row_width=1)
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("channel_menu_"))
async def channel_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    channel_id = int(callback.data.split("_", 2)[2])
    # Основное меню канала
    deep_link = f"https://t.me/{(await callback.bot.me()).username}?start={channel_id}"
    lines = [fmt_field("🆔", "ID канала", str(channel_id)),
             fmt_field("🔗", "Ссылка для пользователя", f"<code>{deep_link}</code>")]
    text = fmt_card("Меню канала", lines)
    kb = make_keyboard([
        ("➕ Добавить тариф", f"add_tariff_{channel_id}"),
        ("📄 Список тарифов", f"list_tariffs_{channel_id}"),
        ("❌ Закрыть", "close_menu")
    ], row_width=1)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "close_menu")
async def close_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.answer()


# -----------------------------
# Управление тарифами
# -----------------------------
@router.callback_query(F.data.startswith("add_tariff_"))
async def add_tariff_start(callback: types.CallbackQuery, state: FSMContext):
    raw = callback.data.removeprefix("add_tariff_")
    try:
        channel_id = int(raw)
    except ValueError:
        return await callback.answer("🚫 Некорректный ID канала", show_alert=True)
    ch = database.get_channel(channel_id)
    if not ch or ch["owner_id"] != callback.from_user.id:
        return await callback.answer("🚫 Доступ запрещён", show_alert=True)
    await state.update_data(channel_id=channel_id)
    text = fmt_card("Добавить тариф", ["Введите название тарифа:"])
    kb = make_keyboard([("⬅️ Назад", f"channel_menu_{channel_id}"), ("❌ Отмена", "close_menu")], row_width=1)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await state.set_state(states.AddTariffState.WAITING_TITLE)
    await callback.answer()


@router.message(states.AddTariffState.WAITING_TITLE)
async def add_tariff_title(message: types.Message, state: FSMContext):
    title = message.text.strip()
    data = await state.get_data()
    channel_id = data["channel_id"]
    await state.update_data(tariff_title=title)
    text = fmt_card("Добавить тариф", ["Введите количество дней:"])
    kb = make_keyboard([("⬅️ Назад", f"add_tariff_{channel_id}"), ("❌ Отмена", "close_menu")], row_width=1)
    await message.answer(text, parse_mode="HTML", reply_markup=kb)
    await state.set_state(states.AddTariffState.WAITING_DURATION)


@router.message(states.AddTariffState.WAITING_DURATION)
async def add_tariff_duration(message: types.Message, state: FSMContext):
    if not message.text.strip().isdigit():
        return await message.answer("❗ Введите целое число дней.")
    duration = int(message.text.strip())
    data = await state.get_data()
    channel_id = data["channel_id"]
    await state.update_data(duration_days=duration)
    text = fmt_card("Добавить тариф", ["Введите цену (в рублях):"])
    kb = make_keyboard([("⬅️ Назад", f"add_tariff_{channel_id}"), ("❌ Отмена", "close_menu")], row_width=1)
    await message.answer(text, parse_mode="HTML", reply_markup=kb)
    await state.set_state(states.AddTariffState.WAITING_PRICE)


@router.message(states.AddTariffState.WAITING_PRICE)
async def add_tariff_price(message: types.Message, state: FSMContext):
    if not message.text.strip().isdigit():
        return await message.answer("❗ Введите корректную цену.")
    price = int(message.text.strip())
    data = await state.get_data()
    channel_id = data["channel_id"]
    title = data["tariff_title"]
    duration = data["duration_days"]

    database.add_tariff(channel_id, title, duration, price)
    text = fmt_card("Добавить тариф", [f"Тариф добавлен: {title} — {duration} дн за {price}₽"])
    kb = make_keyboard([("⬅️ Назад в меню", f"channel_menu_{channel_id}"), ("❌ Отмена", "close_menu")], row_width=1)
    await message.answer(text, parse_mode="HTML", reply_markup=kb)
    await state.clear()


@router.callback_query(F.data.startswith("list_tariffs_"))
async def list_tariffs(callback: types.CallbackQuery):
    channel_id = int(callback.data.split("_", 2)[2])
    ch = database.get_channel(channel_id)
    if not ch or ch["owner_id"] != callback.from_user.id:
        return await callback.answer("🚫 Доступ запрещён", show_alert=True)
    tariffs = database.list_tariffs(channel_id)
    if not tariffs:
        return await callback.message.edit_text("ℹ️ Нет тарифов для этого канала.")
    lines = [fmt_field("💎", t["title"], f"{t['duration_days']} дн — {t['price']}₽") for t in tariffs]
    text = fmt_card("Список тарифов", lines)
    kb = make_keyboard(
        [(f"❌ Удалить {t['title']}", f"del_tariff_{channel_id}_{t['id']}") for t in tariffs] +
        [("⬅️ Назад в меню", f"channel_menu_{channel_id}")],
        row_width=1
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("del_tariff_"))
async def del_tariff(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    channel_id, tariff_id = int(parts[2]), int(parts[3])
    ch = database.get_channel(channel_id)
    if not ch or ch["owner_id"] != callback.from_user.id:
        return await callback.answer("🚫 Доступ запрещён", show_alert=True)
    database.remove_tariff(tariff_id)
    await callback.answer("✅ Тариф удалён")
    # обновить список
    return await list_tariffs(callback)


# -----------------------------
# Модерация заявок
# -----------------------------
@router.callback_query(F.data.startswith("approve_"))
async def on_approve(callback: types.CallbackQuery):
    """Подтверждение заявки"""
    raw = callback.data.removeprefix("approve_")
    try:
        channel_str, user_str, tariff_str = raw.split("_", 2)
        channel_id = int(channel_str)
        user_id = int(user_str)
        tariff_id = int(tariff_str)
    except Exception:
        return await callback.answer("❗ Неверные параметры", show_alert=True)

    # Обновляем статус заказа
    database.approve_order(channel_id, user_id, tariff_id)
    # Добавляем подписку
    tariff = database.get_tariff(tariff_id)
    database.add_subscription(channel_id, user_id, tariff["duration_days"])
    # Генерируем приглашение
    expire = int(time.time()) + tariff["duration_days"] * 86400
    invite = await callback.bot.create_chat_invite_link(
        chat_id=channel_id,
        expire_date=expire,
        member_limit=1
    )
    # Отправляем ссылку пользователю
    await callback.bot.send_message(
        user_id,
        fmt_card("Заявка одобрена", [
            f"Тариф: <b>{tariff['title']}</b>",
            f"Срок: {tariff['duration_days']} дн",
            f"Ваша ссылка: {invite.invite_link}"
        ]),
        parse_mode="HTML"
    )
    await callback.answer("✅ Заявка подтверждена", show_alert=True)
    await callback.message.delete()


@router.callback_query(F.data.startswith("reject_silent_"))
async def on_reject_silent(callback: types.CallbackQuery):
    """Отклонение без оповещения"""
    raw = callback.data.removeprefix("reject_silent_")
    try:
        channel_str, user_str, tariff_str = raw.split("_", 2)
        channel_id = int(channel_str)
        user_id = int(user_str)
        tariff_id = int(tariff_str)
    except Exception:
        return await callback.answer("❗ Неверные параметры", show_alert=True)

    database.reject_order(channel_id, user_id, tariff_id, reason="Отклонено без оповещения")
    await callback.answer("✅ Заявка отклонена без оповещения", show_alert=True)
    await callback.message.delete()


@router.callback_query(F.data.startswith("reject_") & ~F.data.startswith("reject_silent_"))
async def on_reject(callback: types.CallbackQuery, state: FSMContext):
    """Отклонение с запросом причины"""
    raw = callback.data.removeprefix("reject_")
    try:
        channel_str, user_str, tariff_str = raw.split("_", 2)
        channel_id = int(channel_str)
        user_id = int(user_str)
        tariff_id = int(tariff_str)
    except Exception:
        return await callback.answer("❗ Неверные параметры", show_alert=True)

    # Сохраняем данные для ввода причины
    await state.update_data(
        channel_id=channel_id,
        user_id=user_id,
        tariff_id=tariff_id,
        admin_msg_id=callback.message.message_id,
        admin_chat_id=callback.message.chat.id
    )
    # Просим ввести причину
    await callback.message.edit_caption(
        caption=fmt_card("Укажите причину отклонения", ["Напишите текст причины."]),
        parse_mode="HTML",
        reply_markup=make_keyboard([("❌ Отмена", "close_menu")], row_width=1)
    )
    await state.set_state(states.AdminRejectionState.WAITING_REASON)
    await callback.answer()


@router.message(states.AdminRejectionState.WAITING_REASON)
async def process_reject_reason(message: types.Message, state: FSMContext):
    data = await state.get_data()
    reason = message.text.strip()
    channel_id = data["channel_id"]
    user_id = data["user_id"]
    tariff_id = data["tariff_id"]

    database.reject_order(channel_id, user_id, tariff_id, reason=reason)
    # Уведомляем пользователя
    await message.bot.send_message(
        user_id,
        fmt_card("Заявка отклонена", [f"Причина: {reason}"]),
        parse_mode="HTML"
    )
    # Удаляем админское сообщение с кнопками
    await message.bot.delete_message(data["admin_chat_id"], data["admin_msg_id"])
    await message.answer("✅ Пользователь уведомлён об отклонении.")
    await state.clear()


@router.message(Command("id"))
async def cmd_id(message: Message):
    chat = message.chat
    bot = message.bot
    if chat.type in ("channel", "supergroup"):
        channel_id = chat.id
        await bot.send_message(
            chat_id=message.from_user.id,
            text=f"✅ ID канала <b>{chat.title}</b> (ID: <code>{channel_id}</code>)",
            parse_mode="HTML"
        )
    else:
        await bot.send_message(
            chat_id=message.from_user.id,
            text="❗ Команда доступна только в каналах и группах."
        )

    await message.delete()
