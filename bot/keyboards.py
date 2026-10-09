from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

import messages

CALLBACK_CHECK_STATUS = "/check_status"


def get_status_keyboard() -> InlineKeyboardMarkup:
    """Constructs the inline keyboard with the network status check button."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=messages.BTN_CHECK_STATUS,
                    callback_data=CALLBACK_CHECK_STATUS,
                )
            ]
        ]
    )
