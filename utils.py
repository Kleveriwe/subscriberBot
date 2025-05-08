from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def fmt_card(title: str, lines: list[str]) -> str:
    """
    Оформляет «карточку» сообщения: крупный заголовок + тело.
    """
    header = f"✨ <b>{title}</b> ✨"
    body = "\n".join(lines)
    return f"{header}\n\n{body}"


def fmt_field(emoji: str, label: str, value: str) -> str:
    """
    Создаёт строку вида:
    emoji <b>label:</b> value
    """
    return f"{emoji} <b>{label}:</b> {value}"


def make_keyboard(
        buttons: list[tuple[str, str]],
        row_width: int = 2
) -> InlineKeyboardMarkup:
    """
    Универсальный конструктор inline-клавиатуры.

    :param buttons: список кортежей (текст, callback_data или URL)
    :param row_width: максимальное число кнопок в строке
    """
    rows: list[list[InlineKeyboardButton]] = []
    chunk: list[InlineKeyboardButton] = []

    for text, target in buttons:
        if target.startswith("http"):
            btn = InlineKeyboardButton(text=text, url=target)
        else:
            btn = InlineKeyboardButton(text=text, callback_data=target)

        chunk.append(btn)
        if len(chunk) == row_width:
            rows.append(chunk)
            chunk = []

    if chunk:
        rows.append(chunk)

    return InlineKeyboardMarkup(inline_keyboard=rows)
