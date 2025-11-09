from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from models.constants import POPULAR_CITIES


def get_city_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    for city in POPULAR_CITIES:
        kb.insert(InlineKeyboardButton(city, callback_data=f"city:{city}"))
    return kb


def get_car_kb(cars_map: dict):
    kb = InlineKeyboardMarkup(row_width=1)
    for name, car_id in cars_map.items():
        kb.add(InlineKeyboardButton(name, callback_data=f"car:{car_id}"))
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="back:city"))
    return kb


def confirm_booking_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("✅ Да", callback_data="confirm:yes"),
        InlineKeyboardButton("❌ Нет", callback_data="confirm:no"),
    )
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="back:dates"))
    return kb


def date_from_kb():
    return InlineKeyboardMarkup().add(InlineKeyboardButton("⬅️ Назад", callback_data="back:car"))


def date_to_kb():
    return InlineKeyboardMarkup().add(InlineKeyboardButton("⬅️ Назад", callback_data="back:date_from"))


def kb_back():
    return InlineKeyboardMarkup().add(InlineKeyboardButton("⬅️ Назад", callback_data="cancel"))


def kb_confirm():
    return InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("✅ Да", callback_data="confirm_yes"),
        InlineKeyboardButton("❌ Нет", callback_data="confirm_no")
    )


def kb_skip_cancel():
    return InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("Пропустить", callback_data="skip"),
        InlineKeyboardButton("⬅️ Назад", callback_data="cancel")
    )


def cancel_kb():
    return InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Отмена", callback_data="cancel"))


def comment_kb():
    return InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("Пропустить", callback_data="skip_comment"),
        InlineKeyboardButton("❌ Отмена", callback_data="cancel")
    )


def user_type_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("Владелец (физ. лицо)", callback_data="user_type_owner_physical"),
        InlineKeyboardButton("Владелец (юр. лицо)", callback_data="user_type_owner_legal"),
        InlineKeyboardButton("Арендатор", callback_data="user_type_renter"),
        InlineKeyboardButton("❌ Отмена", callback_data="cancel_registration")
    )
    return keyboard


def cancel_keyboard():
    return InlineKeyboardMarkup().add(
        InlineKeyboardButton("⬅️ Назад", callback_data="cancel_registration")
    )


def payment_confirmation_kb(payment_id: int):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("✅ Подтвердить оплату", callback_data=f"pay_confirm_{payment_id}"),
        InlineKeyboardButton("❌ Отменить оплату", callback_data=f"pay_cancel_confirm_{payment_id}"),
    )
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="submenu_payments"))
    return kb


def date_from_kb():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="back:car"))
    return kb


def date_to_kb():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="back:date_from"))
    return kb
