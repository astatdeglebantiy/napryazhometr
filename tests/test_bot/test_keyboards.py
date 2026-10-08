from aiogram.types import InlineKeyboardMarkup
from bot.keyboards import get_status_keyboard

def test_status_keyboard_structure():
    kb: InlineKeyboardMarkup = get_status_keyboard()
    assert len(kb.inline_keyboard) == 1
    btn = kb.inline_keyboard[0][0]
    assert btn.text == "⚡️ Перевірити стан мережі"
    assert btn.callback_data == "/check_status"
