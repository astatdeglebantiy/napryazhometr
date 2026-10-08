from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

def get_status_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⚡️ Перевірити стан мережі",
                    callback_data="/check_status"
                )
            ]
        ]
    )
