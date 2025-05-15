import database
import states
import time
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from utils import fmt_card, fmt_field, make_keyboard

router = Router()

# -----------------------------
# Шаблоны и константы
# -----------------------------

BACK = ("⬅️ Назад", None)  # callback_data заполняется динамически
CANCEL = ("❌ Отмена", "cancel_admin")


# -----------------------------
# Помощник для разбора callback_data вида "<cmd>_<channel>[_<item>]"
# -----------------------------
def parse_cd(data: str, prefix: str, parts: int = 1):
    """
    Убирает префикс и разбивает по "_", возвращает список частей.
    """
    payload = data.removeprefix(prefix)
    items = payload.split("_", parts)
    if len(items) < parts:
        raise ValueError
    return items


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
            "3️⃣ В канале вызовите команду /id для получения ID."
        ]
    )
    kb = make_keyboard([
        ("📡 Указать канал", "enter_admin_channel"),
        CANCEL
    ], row_width=1)
    await state.clear()
    await message.answer(text, reply_markup=kb, parse_mode="HTML")
    await state.set_state(states.AddChannelState.WAITING_USERNAME)


@router.callback_query(F.data == "cancel_admin")
async def cancel_admin(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.answer()


@router.callback_query(F.data == "enter_admin_channel")
async def enter_admin_channel(callback: types.CallbackQuery, state: FSMContext):
    text = fmt_card(
        "Укажите канал",
        ["Отправьте @username, ссылку t.me/... или числовой ID канала."]
    )
    kb = make_keyboard([
        ("⬅️ Назад", "add_my_channel"),
        CANCEL
    ], row_width=1)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()
    await state.set_state(states.AddChannelState.WAITING_USERNAME)


@router.message(states.AddChannelState.WAITING_USERNAME)
async def process_channel_username(message: types.Message, state: FSMContext):
    raw = message.text.strip()
    cleaned = raw.replace("https://t.me/", "").replace("t.me/", "")
    try:
        chat = await message.bot.get_chat(cleaned)
        me = await message.bot.me()
        member = await message.bot.get_chat_member(chat.id, me.id)
        if member.status not in ("administrator", "creator"):
            raise PermissionError
    except PermissionError:
        return await message.answer("❗ Бот не администратор в этом канале.", parse_mode="HTML")
    except Exception:
        return await message.answer("❗ Не удалось получить информацию о канале.", parse_mode="HTML")

    # Сохраняем данные и просим реквизиты
    await state.update_data(
        channel_id=chat.id,
        channel_title=chat.title,
        owner_id=message.from_user.id
    )
    text = fmt_card(
        "Реквизиты для оплаты",
        [f"Канал: <b>{chat.title}</b> (ID: <code>{chat.id}</code>)",
         "Отправьте реквизиты (номер карты, QIWI и т.п.)."]
    )
    kb = make_keyboard([
        ("⬅️ Назад", "add_my_channel"),
        CANCEL
    ], row_width=1)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")
    await state.set_state(states.AddChannelState.WAITING_PAYMENT_INFO)


@router.message(states.AddChannelState.WAITING_PAYMENT_INFO)
async def process_payment_info(message: types.Message, state: FSMContext):
    data = await state.get_data()
    channel_id = data["channel_id"]
    database.add_or_update_channel(
        channel_id,
        data["owner_id"],
        data["channel_title"],
        message.text.strip()
    )

    deep_link = f"https://t.me/{(await message.bot.me()).username}?start={channel_id}"
    text = fmt_card(
        "Канал сохранён",
        [
            f"Канал: <b>{data['channel_title']}</b> (ID: <code>{channel_id}</code>)",
            f"Реквизиты: {message.text.strip()}",
            f"Ссылка для пользователей: <code>{deep_link}</code>"
        ]
    )
    kb = make_keyboard([
        ("➡️ Меню канала", f"channel_menu_{channel_id}"),
        CANCEL
    ], row_width=1)

    await message.answer(text, reply_markup=kb, parse_mode="HTML")
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
    kb = make_keyboard([(ch["title"], f"channel_menu_{ch['channel_id']}") for ch in channels], row_width=1)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("channel_menu_"))
async def channel_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    channel_id = int(parse_cd(callback.data, "channel_menu_")[0])
    ch = database.get_channel(channel_id)
    payment = f"<code>{ch['payment_info'] or '—'}</code>"
    deep_link = f"https://t.me/{(await callback.bot.me()).username}?start={channel_id}"

    lines = [
        fmt_field("🆔", "ID канала", str(channel_id)),
        fmt_field("🛒", "Реквизиты", payment),
        fmt_field("🔗", "Ссылка для пользователей", f"<code>{deep_link}</code>")
    ]
    text = fmt_card("Меню канала", lines)

    kb = make_keyboard([
        ("🔄 Обновить реквизиты", f"update_payment_info_{channel_id}"),
        ("➕ Добавить тариф", f"add_tariff_{channel_id}"),
        ("📄 Список тарифов", f"list_tariffs_{channel_id}"),
        ("🗑 Удалить канал", f"del_channel_{channel_id}"),
        ("❌ Закрыть", "close_menu"),
    ], row_width=2)

    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# -----------------------------
# Обновление реквизитов
# -----------------------------
@router.callback_query(F.data.startswith("update_payment_info_"))
async def update_payment_info_start(callback: types.CallbackQuery, state: FSMContext):
    channel_id = int(parse_cd(callback.data, "update_payment_info_")[0])
    await state.set_state(states.UpdatePaymentState.WAITING_NEW_PAYMENT_INFO)
    await state.update_data(channel_id=channel_id)

    text = fmt_card("Обновить реквизиты", ["Отправьте новые реквизиты для оплаты."])
    kb = make_keyboard([
        ("⬅️ Назад", f"channel_menu_{channel_id}"),
        CANCEL
    ], row_width=1)

    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.message(states.UpdatePaymentState.WAITING_NEW_PAYMENT_INFO, F.text)
async def process_new_payment_info(message: types.Message, state: FSMContext):
    data = await state.get_data()
    channel_id = data["channel_id"]
    new_info = message.text.strip()

    database.update_channel_payment_info(channel_id, new_info)

    text = fmt_card("Реквизиты обновлены", [f"Новые реквизиты: {new_info}"])
    kb = make_keyboard([("⬅️ Назад в меню", f"channel_menu_{channel_id}")], row_width=1)

    await message.answer(text, reply_markup=kb, parse_mode="HTML")
    await state.clear()


# -----------------------------
# Удаление канала
# -----------------------------
@router.callback_query(F.data.startswith("del_channel_"))
async def del_channel(callback: types.CallbackQuery, state: FSMContext):
    channel_id = int(parse_cd(callback.data, "del_channel_")[0])
    database.delete_channel(channel_id)
    await callback.message.edit_text("ℹ️ Канал удалён.", parse_mode="HTML")
    await callback.answer()
    await state.clear()


# -----------------------------
# Управление тарифами
# -----------------------------
@router.callback_query(F.data.startswith("add_tariff_"))
async def add_tariff_start(callback: types.CallbackQuery, state: FSMContext):
    channel_id = int(parse_cd(callback.data, "add_tariff_")[0])
    ch = database.get_channel(channel_id)
    if not ch or ch["owner_id"] != callback.from_user.id:
        return await callback.answer("🚫 Доступ запрещён", show_alert=True)

    await state.update_data(channel_id=channel_id)
    await state.set_state(states.AddTariffState.WAITING_TITLE)

    text = fmt_card("Добавить тариф", ["Введите название:"])
    kb = make_keyboard([
        ("⬅️ Назад", f"channel_menu_{channel_id}"),
        CANCEL
    ], row_width=1)

    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.message(states.AddTariffState.WAITING_TITLE)
async def add_tariff_title(message: types.Message, state: FSMContext):
    title = message.text.strip()
    await state.update_data(tariff_title=title)
    data = await state.get_data()

    text = fmt_card("Добавить тариф", ["Введите длительность (дни):"])
    kb = make_keyboard([
        ("⬅️ Назад", f"add_tariff_{data['channel_id']}"),
        CANCEL
    ], row_width=1)

    await message.answer(text, reply_markup=kb, parse_mode="HTML")
    await state.set_state(states.AddTariffState.WAITING_DURATION)


@router.message(states.AddTariffState.WAITING_DURATION)
async def add_tariff_duration(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("❗ Введите целое число.", parse_mode="HTML")

    await state.update_data(duration_days=int(message.text))
    data = await state.get_data()

    text = fmt_card("Добавить тариф", ["Введите цену (₽):"])
    kb = make_keyboard([
        ("⬅️ Назад", f"add_tariff_{data['channel_id']}"),
        CANCEL
    ], row_width=1)

    await message.answer(text, reply_markup=kb, parse_mode="HTML")
    await state.set_state(states.AddTariffState.WAITING_PRICE)


@router.message(states.AddTariffState.WAITING_PRICE)
async def add_tariff_price(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("❗ Введите корректную цену.", parse_mode="HTML")

    data = await state.get_data()
    database.add_tariff(
        data["channel_id"],
        data["tariff_title"],
        data["duration_days"],
        int(message.text)
    )

    text = fmt_card("Добавить тариф",
                    [f"«{data['tariff_title']}» — {data['duration_days']} дн за {message.text}₽ добавлен."])
    kb = make_keyboard([
        ("⬅️ Назад в меню", f"channel_menu_{data['channel_id']}"),
        CANCEL
    ], row_width=1)

    await message.answer(text, reply_markup=kb, parse_mode="HTML")
    await state.clear()


@router.callback_query(F.data.startswith("list_tariffs_"))
async def list_tariffs(callback: types.CallbackQuery):
    channel_id = int(parse_cd(callback.data, "list_tariffs_")[0])
    ch = database.get_channel(channel_id)
    if not ch or ch["owner_id"] != callback.from_user.id:
        return await callback.answer("🚫 Доступ запрещён", show_alert=True)

    tariffs = database.list_tariffs(channel_id)
    if not tariffs:
        return await callback.message.edit_text("ℹ️ Нет тарифов.", parse_mode="HTML")

    lines = [fmt_field("💎", t["title"], f"{t['duration_days']} дн — {t['price']}₽") for t in tariffs]
    text = fmt_card("Список тарифов", lines)

    kb = make_keyboard(
        [(f"❌ Удалить «{t['title']}»", f"del_tariff_{channel_id}_{t['id']}") for t in tariffs] +
        [("⬅️ Назад в меню", f"channel_menu_{channel_id}")],
        row_width=1
    )
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("del_tariff_"))
async def del_tariff(callback: types.CallbackQuery):
    parts = parse_cd(callback.data, "del_tariff_", parts=2)
    channel_id, tariff_id = map(int, parts)
    ch = database.get_channel(channel_id)
    if not ch or ch["owner_id"] != callback.from_user.id:
        return await callback.answer("🚫 Доступ запрещён", show_alert=True)

    database.remove_tariff(tariff_id)
    await callback.answer("✅ Тариф удалён", show_alert=True)
    # Обновляем список
    await list_tariffs(callback)


# -----------------------------
# Обработка заявок
# -----------------------------
@router.callback_query(F.data.startswith("approve_"))
async def on_approve(callback: types.CallbackQuery):
    try:
        channel_id, user_id, tariff_id = map(int, parse_cd(callback.data, "approve_", parts=3))
    except ValueError:
        return await callback.answer("❗ Неверные параметры", show_alert=True)

    database.approve_order(channel_id, user_id, tariff_id)
    tariff = database.get_tariff(tariff_id)
    database.add_subscription(channel_id, user_id, tariff["duration_days"])

    invite = await callback.bot.create_chat_invite_link(
        chat_id=channel_id,
        expire_date=int(time.time()) + tariff["duration_days"] * 86400,
        member_limit=1
    )

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
    try:
        channel_id, user_id, tariff_id = map(int, parse_cd(callback.data, "reject_silent_", parts=3))
    except ValueError:
        return await callback.answer("❗ Неверные параметры", show_alert=True)

    database.reject_order(channel_id, user_id, tariff_id, reason="Отклонено без оповещения")
    await callback.answer("✅ Заявка отклонена без оповещения", show_alert=True)
    await callback.message.delete()


@router.callback_query(F.data.startswith("reject_") & ~F.data.startswith("reject_silent_"))
async def on_reject(callback: types.CallbackQuery, state: FSMContext):
    try:
        channel_id, user_id, tariff_id = map(int, parse_cd(callback.data, "reject_", parts=3))
    except ValueError:
        return await callback.answer("❗ Неверные параметры", show_alert=True)

    await state.update_data(
        channel_id=channel_id,
        user_id=user_id,
        tariff_id=tariff_id,
        admin_chat_id=callback.message.chat.id,
        admin_msg_id=callback.message.message_id
    )
    text = fmt_card("Укажите причину отклонения", ["Напишите текст причины."])
    kb = make_keyboard([CANCEL], row_width=1)

    await callback.message.edit_caption(text, parse_mode="HTML", reply_markup=kb)
    await state.set_state(states.AdminRejectionState.WAITING_REASON)
    await callback.answer()


@router.message(states.AdminRejectionState.WAITING_REASON)
async def process_reject_reason(message: types.Message, state: FSMContext):
    data = await state.get_data()
    reason = message.text.strip()
    database.reject_order(data["channel_id"], data["user_id"], data["tariff_id"], reason=reason)

    # Уведомляем пользователя
    await message.bot.send_message(
        data["user_id"],
        fmt_card("Заявка отклонена", [f"Причина: {reason}"]),
        parse_mode="HTML"
    )
    # Удаляем админское сообщение
    await message.bot.delete_message(data["admin_chat_id"], data["admin_msg_id"])

    await message.answer("✅ Пользователь уведомлён", parse_mode="HTML")
    await state.clear()


# -----------------------------
# Получение ID
# -----------------------------
@router.message(Command("id"))
async def cmd_id(message: types.Message):
    chat = message.chat
    if chat.type in ("channel", "supergroup"):
        await message.bot.send_message(
            message.from_user.id,
            fmt_card("ID чата", [f"{chat.title} — ID: <code>{chat.id}</code>"]),
            parse_mode="HTML"
        )
        await message.delete()
    else:
        await message.answer("❗ Используйте эту команду в канале.", parse_mode="HTML")
