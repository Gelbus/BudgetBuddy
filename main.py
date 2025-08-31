import logging
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.types.callback_query import CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from bot_config import TOKEN, INCOME_CATEGORIES, EXPENSE_CATEGORIES

import psycopg

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Замените на ваш токен от BotFather


# Инициализация бота, хранилища и диспетчера
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# Определение состояний FSM
class FinanceStates(StatesGroup):
    waiting_for_amount = State()  # Ожидание ввода суммы
    waiting_for_category_type = State()  # Ожидание выбора типа операции (доход/расход)
    waiting_for_income_category = State()  # Ожидание выбора категории дохода
    waiting_for_expense_category = State()  # Ожидание выбора категории расхода


# ==================== ОБРАБОТЧИК КОМАНДЫ /START ====================
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext) -> None:
    """Обработчик команды /start. Сбрасывает состояние и показывает главное меню."""
    await state.clear()  # Сброс любого предыдущего состояния
    builder = ReplyKeyboardBuilder()
    builder.add(types.KeyboardButton(text="Ввести доход 💰"))
    builder.add(types.KeyboardButton(text="Ввести расход 📉"))
    builder.adjust(2)  # Располагаем кнопки в 2 колонки
    keyboard = builder.as_markup(resize_keyboard=True)

    await message.answer(
        "Добро пожаловать в бот для учета финансов!\nВыберите действие:",
        reply_markup=keyboard
    )


# ==================== ОБРАБОТКА ВЫБОРА ОПЕРАЦИИ (ДОХОД/РАСХОД) ====================
@dp.message(F.text.in_(["Ввести доход 💰", "Ввести расход 📉"]))
async def process_operation_choice(message: types.Message, state: FSMContext):
    """Обрабатывает нажатие на кнопку 'Ввести доход' или 'Ввести расход'."""
    operation_type = "income" if message.text == "Ввести доход 💰" else "expense"

    # Сохраняем тип операции в состоянии
    await state.update_data(operation_type=operation_type)

    # Переходим в состояние ожидания ввода суммы
    await state.set_state(FinanceStates.waiting_for_amount)
    await message.answer(
        "Введите сумму:",
        reply_markup=types.ReplyKeyboardRemove()  # Убираем обычную клавиатуру
    )


# ==================== ОБРАБОТКА ВВЕДЕННОЙ СУММЫ ====================
@dp.message(FinanceStates.waiting_for_amount, F.text.regexp(r'^\d+$'))
async def process_amount(message: types.Message, state: FSMContext):
    """Обрабатывает введенную сумму и запрашивает категорию."""
    amount = int(message.text)

    # Сохраняем сумму в состоянии
    await state.update_data(amount=amount)

    # Получаем сохраненный тип операции
    data = await state.get_data()
    operation_type = data.get('operation_type')

    # В зависимости от типа операции показываем соответствующие инлайн-кнопки
    if operation_type == "income":
        await show_income_categories(message, state)
    else:
        await show_expense_categories(message, state)


@dp.message(FinanceStates.waiting_for_amount)
async def process_amount_invalid(message: types.Message):
    """Обрабатывает неверный ввод суммы."""
    await message.answer("Пожалуйста, введите сумму цифрами.")


# ==================== ПОКАЗ КАТЕГОРИЙ ДОХОДА ====================
async def show_income_categories(message: types.Message, state: FSMContext):
    """Показывает инлайн-кнопки с категориями доходов."""
    await state.set_state(FinanceStates.waiting_for_income_category)
    builder = InlineKeyboardBuilder()

    for category in INCOME_CATEGORIES:
        builder.button(text=category, callback_data=f"income_{category}")

    builder.adjust(2)  # Располагаем кнопки по 2 в ряд
    keyboard = builder.as_markup()

    await message.answer("Выберите категорию дохода:", reply_markup=keyboard)


# ==================== ПОКАЗ КАТЕГОРИЙ РАСХОДА ====================
async def show_expense_categories(message: types.Message, state: FSMContext):
    """Показывает инлайн-кнопки с категориями расходов."""
    await state.set_state(FinanceStates.waiting_for_expense_category)
    builder = InlineKeyboardBuilder()

    for category in EXPENSE_CATEGORIES:
        builder.button(text=category, callback_data=f"expense_{category}")

    builder.adjust(2)  # Располагаем кнопки по 2 в ряд
    keyboard = builder.as_markup()

    await message.answer("Выберите категорию расхода:", reply_markup=keyboard)


# ==================== ОБРАБОТКА ВЫБОРА КАТЕГОРИИ ДОХОДА ====================
@dp.callback_query(FinanceStates.waiting_for_income_category, F.data.startswith("income_"))
async def process_income_category(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает выбор категории дохода."""
    category = callback.data.replace("income_", "")

    # Получаем все данные из состояния
    data = await state.get_data()
    amount = data.get('amount')
    operation_type = data.get('operation_type')

    # Здесь будет ваша логика сохранения в БД
    # Например: save_to_db(callback.from_user.id, operation_type, amount, category)

    await callback.message.edit_text(
        f"✅ Доход {amount} руб. в категории '{category}' записан.\n\n"
        f"*Место для вашего кода работы с БД*"
    )
    await callback.answer()

    # Показываем главное меню again
    await show_main_menu(callback.message, state)


# ==================== ОБРАБОТКА ВЫБОРА КАТЕГОРИИ РАСХОДА ====================
@dp.callback_query(FinanceStates.waiting_for_expense_category, F.data.startswith("expense_"))
async def process_expense_category(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает выбор категории расхода."""
    category = callback.data.replace("expense_", "")

    # Получаем все данные из состояния
    data = await state.get_data()
    amount = data.get('amount')
    operation_type = data.get('operation_type')

    # Здесь будет ваша логика сохранения в БД
    # Например: save_to_db(callback.from_user.id, operation_type, amount, category)

    await callback.message.edit_text(
        f"✅ Расход {amount} руб. в категории '{category}' записан.\n\n"
        f"*Место для вашего кода работы с БД*"
    )
    await callback.answer()

    # Показываем главное меню again
    await show_main_menu(callback.message, state)


# ==================== ПОКАЗ ГЛАВНОГО МЕНЮ ====================
async def show_main_menu(message: types.Message, state: FSMContext):
    """Показывает главное меню с кнопками."""
    await state.clear()
    builder = ReplyKeyboardBuilder()
    builder.add(types.KeyboardButton(text="Ввести доход 💰"))
    builder.add(types.KeyboardButton(text="Ввести расход 📉"))
    builder.adjust(2)
    keyboard = builder.as_markup(resize_keyboard=True)

    await message.answer("Выберите действие:", reply_markup=keyboard)


# ==================== ЗАПУСК БОТА ====================
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())