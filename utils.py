from typing import List, Tuple
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def fmt_card(title: str, lines: List[str]) -> str:
    """
    Форматирует «карточку» сообщения:
    — Заголовок (с эмодзи и жирным шрифтом)
    — Тело из списка строк.
    """
    header = f"✨ <b>{title}</b> ✨"
    body = "\n".join(lines)
    return f"{header}\n\n{body}"


def fmt_field(emoji: str, label: str, value: str) -> str:
    """
    Форматирует строку-поле:
    emoji + жирный label + value
    """
    return f"{emoji} <b>{label}:</b> {value}"


def make_keyboard(
    buttons: List[Tuple[str, str]],
    row_width: int = 2
) -> InlineKeyboardMarkup:
    """
    Создаёт InlineKeyboardMarkup из списка кнопок.

    :param buttons: список кортежей (текст кнопки, callback_data или URL)
    :param row_width: максимальное число кнопок в одном ряду
    :return: InlineKeyboardMarkup
    """
    keyboard: List[List[InlineKeyboardButton]] = []
    row: List[InlineKeyboardButton] = []

    for text, target in buttons:
        if target.startswith(("http://", "https://")):
            btn = InlineKeyboardButton(text=text, url=target)
        else:
            btn = InlineKeyboardButton(text=text, callback_data=target)

        row.append(btn)
        if len(row) >= row_width:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    return InlineKeyboardMarkup(inline_keyboard=keyboard)
