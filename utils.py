from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def fmt_card(title: str, lines: list[str]) -> str:
    header = f"✨ <b>{title}</b> ✨"
    body = "\n".join(lines)
    return f"{header}\n\n{body}"


def fmt_field(emoji: str, label: str, value: str) -> str:
    return f"{emoji} <b>{label}:</b> {value}"


def make_keyboard(
        buttons: list[tuple[str, str]],
        row_width: int = 2
) -> InlineKeyboardMarkup:
    rows, chunk = [], []
    for text, target in buttons:
        btn = (InlineKeyboardButton(text=text, url=target)
               if target.startswith("http")
               else InlineKeyboardButton(text=text, callback_data=target))
        chunk.append(btn)
        if len(chunk) == row_width:
            rows.append(chunk);
            chunk = []
    if chunk: rows.append(chunk)
    return InlineKeyboardMarkup(inline_keyboard=rows)
