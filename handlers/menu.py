from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

class MenuFSM(StatesGroup):
    waiting_for_confirmation = State()

def main_menu_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🚗 Добавить автомобиль", callback_data="cmd_add_car"),
        InlineKeyboardButton("📋 Мои автомобили", callback_data="cmd_my_cars"),
        InlineKeyboardButton("📅 Забронировать авто", callback_data="cmd_book"),
        InlineKeyboardButton("📝 Оставить отзыв", callback_data="cmd_review"),
        InlineKeyboardButton("⭐️ Просмотреть отзывы", callback_data="cmd_reviews"),
        InlineKeyboardButton("📄 Договоры", callback_data="submenu_contracts"),
        InlineKeyboardButton("💳 Оплата", callback_data="submenu_payments"),
    )
    return kb

def contracts_menu_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("📄 Создать / получить договор", callback_data="cmd_contract"),
        InlineKeyboardButton("❌ Аннулировать договор", callback_data="cmd_cancel_contract"),
        InlineKeyboardButton("⬅️ Назад", callback_data="back_main"),
    )
    return kb

def payments_menu_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("💳 Оплатить бронирование", callback_data="pay_start"),
        InlineKeyboardButton("❌ Отменить оплату", callback_data="pay_cancel"),
        InlineKeyboardButton("⬅️ Назад", callback_data="back_main"),
    )
    return kb

async def process_menu_callbacks(callback: types.CallbackQuery, state: FSMContext):
    data = callback.data

    if data == "back_main":
        await callback.message.edit_text("Главное меню:", reply_markup=main_menu_kb())
        await state.finish()
        await callback.answer()
        return

    if data == "submenu_contracts":
        await callback.message.edit_text("Меню договоров:", reply_markup=contracts_menu_kb())
        await callback.answer()
        return

    if data == "submenu_payments":
        await callback.message.edit_text("Меню оплат:", reply_markup=payments_menu_kb())
        await callback.answer()
        return

    if data == "pay_start":
        await callback.message.edit_text(
            "Вы хотите оплатить последнее бронирование?\nПодтвердите действие:",
            reply_markup=InlineKeyboardMarkup(row_width=2).add(
                InlineKeyboardButton("✅ Да", callback_data="pay_confirm"),
                InlineKeyboardButton("❌ Нет", callback_data="pay_decline"),
            )
        )
        await MenuFSM.waiting_for_confirmation.set()
        await callback.answer()
        return

    if data == "pay_cancel":
        await callback.message.edit_text(
            "Вы хотите отменить оплату последнего бронирования?\nПодтвердите действие:",
            reply_markup=InlineKeyboardMarkup(row_width=2).add(
                InlineKeyboardButton("✅ Да", callback_data="pay_cancel_confirm"),
                InlineKeyboardButton("❌ Нет", callback_data="pay_cancel_decline"),
            )
        )
        await MenuFSM.waiting_for_confirmation.set()
        await callback.answer()
        return

    # команды без подтверждения
    cmd_map = {
        "cmd_add_car": "/add_car",
        "cmd_my_cars": "/my_cars",
        "cmd_book": "/book",
        "cmd_review": "/review",
        "cmd_reviews": "/reviews",
        "cmd_contract": "/contract",
        "cmd_cancel_contract": "/cancel_contract",
        "cmd_pay": "/pay",
        "cmd_pay_cancel": "/pay_cancel",
    }

    if data in cmd_map:
        await callback.message.delete()
        await callback.message.answer(cmd_map[data])
        await state.finish()
        await callback.answer()
        return

    await callback.answer("Неизвестная команда.", show_alert=True)

async def confirmation_handler(callback: types.CallbackQuery, state: FSMContext):
    data = callback.data

    if data == "pay_confirm":
        await callback.message.edit_text("Обрабатываем оплату...")
        await process_payment(callback)
        await state.finish()

    elif data == "pay_decline":
        await callback.message.edit_text("Оплата отменена.")
        await state.finish()

    elif data == "pay_cancel_confirm":
        await callback.message.edit_text("Обрабатываем отмену оплаты...")
        await process_payment_cancellation(callback)
        await state.finish()

    elif data == "pay_cancel_decline":
        await callback.message.edit_text("Отмена оплаты отменена.")
        await state.finish()

    else:
        await callback.answer()

async def process_payment(callback: types.CallbackQuery):
    await callback.message.answer("Оплата успешно проведена! Спасибо.")
    await callback.answer()

async def process_payment_cancellation(callback: types.CallbackQuery):
    # Логика отмены оплаты, возврата денег, обновление статуса
    await callback.message.answer("Оплата успешно отменена.")
    await callback.answer()

async def menu_command(message: types.Message):
    await message.answer("Главное меню:", reply_markup=main_menu_kb())


def register_menu_handlers(dp: Dispatcher):
    dp.register_message_handler(menu_command, commands=["menu"], state="*")
    dp.register_callback_query_handler(process_menu_callbacks, state="*")
    dp.register_callback_query_handler(confirmation_handler, state=MenuFSM.waiting_for_confirmation)