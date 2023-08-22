import asyncio
import datetime
import os
import psycopg2

from dotenv import load_dotenv
from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher, FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

load_dotenv('.env')

# Устанавливаем соединение с базой данных PostgreSQL
db_name = os.getenv("DB_NAME")
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT")
bot_token = os.getenv("BOT_TOKEN")

conn = psycopg2.connect(database=db_name, user=db_user, password=db_password, host=db_host, port=db_port)
cur = conn.cursor()

# Создаем объекты бота и диспетчера
bot = Bot(token=bot_token)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

admin_ids = [367150414]

formatted_date = None


# Обработчик команды /start
@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    if message.from_user.id in admin_ids:
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            types.InlineKeyboardButton(text="Барбер", callback_data="admin"),
            types.InlineKeyboardButton(text="Клиент", callback_data="client")
        )
        await message.answer("Под какой ролью хочешь зайти?", reply_markup=keyboard)
    else:
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            types.InlineKeyboardButton(text="✂️ Записаться на стрижку ✂️", callback_data="book_cut"),
            types.InlineKeyboardButton(text="📍 Узнать местоположение 📍", callback_data="get_location"),
            types.InlineKeyboardButton(text="💵 Узнать прайс-лист 💵", callback_data="get_price_list"),
            types.InlineKeyboardButton(text="📅 Мои записи 📅", callback_data="get_appointments")
        )
        bold_name = f"<b>{message.from_user.first_name}</b>"
        await message.answer(f"Добрый день, {bold_name}! Чем могу помочь? 🤔", reply_markup=keyboard, parse_mode="html")


@dp.callback_query_handler(lambda callback_query: callback_query.data == "admin")
async def admin_callback(query: types.CallbackQuery):
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        types.InlineKeyboardButton(text="✂️ Кто на сегодня записан ✂️", callback_data="today_book"))
    await bot.send_message(chat_id=query.from_user.id, text=f"Добрый день, *{query.from_user.first_name}*!", reply_markup=keyboard, parse_mode=types.ParseMode.MARKDOWN)


@dp.callback_query_handler(lambda callback_query: callback_query.data == "client")
async def client_callback(query: types.CallbackQuery):
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        types.InlineKeyboardButton(text="✂️ Записаться на стрижку ✂️", callback_data="book_cut"),
        types.InlineKeyboardButton(text="📍 Узнать местоположение 📍", callback_data="get_location"),
        types.InlineKeyboardButton(text="💵 Узнать прайс-лист 💵", callback_data="get_price_list"),
        types.InlineKeyboardButton(text="📅 Мои записи 📅", callback_data="get_appointments")
    )
    bold_name = f"<b>{query.from_user.first_name}</b>"
    await bot.send_message(chat_id=query.from_user.id, text=f"Добрый день, {bold_name}! Чем могу помочь? 🤔", reply_markup=keyboard, parse_mode="html")


# Обработчик нажатия кнопки "Кто на сегодня записан"
@dp.callback_query_handler(lambda callback_query: callback_query.data == "today_book")
async def today_book_callback(callback_query: types.CallbackQuery):
    if callback_query.from_user.id in admin_ids:
        today = datetime.date.today()
        cur.execute("SELECT time, user_name FROM schedule WHERE date = %s AND user_name IS NOT NULL", (today,))
        results = cur.fetchall()

        if results:
            info = [f"- {time} - {user_name}" for time, user_name in results]
            info_str = '\n'.join(info)
            await bot.send_message(callback_query.from_user.id, f"К тебе {today} придут:\n{info_str}")
        else:
            await bot.send_message(callback_query.from_user.id, f"На сегодня нет записей 🤷🏻‍♂️")


@dp.callback_query_handler(lambda query: query.data == "book_cut")
async def schedule_appointment(query: types.CallbackQuery):
    user_id = query.from_user.id
    cur.execute("SELECT COUNT(*) FROM schedule WHERE user_id = %s", (user_id,))
    count = cur.fetchone()[0]
    if count >= 3:
        cur.execute("SELECT date, time FROM schedule WHERE user_id = %s", (user_id,))
        appointments = cur.fetchall()
        message = "Вы уже записаны на 3 стрижки:\n"
        for appointment in appointments:
            appointment_date = appointment[0].strftime("%d.%m.%Y")
            appointment_time = appointment[1].strftime("%H:%M")
            message += f"• {appointment_date} в {appointment_time}\n"
        await bot.answer_callback_query(query.id)
        await bot.send_message(chat_id=query.message.chat.id, text=message)
    else:
        await bot.answer_callback_query(query.id)
        await bot.send_message(chat_id=query.message.chat.id,
                               text="На какую дату записать? 🧐 Я работаю по вторникам, средам, пятницам и субботам.")
        await bot.send_message(chat_id=query.message.chat.id,
                               text="_Пример даты: 01.08.2023_", parse_mode=types.ParseMode.MARKDOWN)


# Обработчик текстового сообщения с датой
@dp.message_handler(lambda message: message.text and "." in message.text)
async def check_available_hours(message: types.Message):
    global formatted_date
    date_str = message.text
    # Преобразование даты в формат ГГГГ-ММ-ДД
    date_str = datetime.datetime.strptime(date_str, "%d.%m.%Y")
    formatted_date = date_str.strftime("%Y-%m-%d")
    cur.execute("SELECT time FROM schedule WHERE date = %s AND is_available = TRUE", (formatted_date,))
    available_times = [row[0] for row in cur.fetchall()]

    if not available_times:
        await bot.send_message(chat_id=message.chat.id, text="На выбранную дату нет свободного времени 🤷🏻‍♂️, попробуй выбрать другую дату.")
        return

    # Формируем список кнопок на основе полученных данных
    keyboard = InlineKeyboardMarkup(row_width=3)
    for available_time in available_times:
        # Преобразование времени в строку
        time_str = available_time.strftime("%H:%M")
        # Добавление кнопки с временем
        button = InlineKeyboardButton(text=time_str, callback_data=f"book_cut_{time_str}")
        keyboard.add(button)

    # Отправляем сообщение с текстом и кнопками пользователю
    await bot.send_message(chat_id=message.chat.id, text="На какое время записать? 🤔", reply_markup=keyboard)


@dp.callback_query_handler(lambda query: query.data.startswith("book_cut_"))
async def confirm_appointment(query: types.CallbackQuery):
    user_id = query.from_user.id
    user_name = query.from_user.full_name
    tg_username = query.from_user.username
    user_first_name = query.from_user.first_name

    formatted_date_str = datetime.datetime.strptime(formatted_date, "%Y-%m-%d").strftime("%d.%m.%Y")

    time_str = query.data.split("_")[2]

    # Преобразование строки времени в объект datetime.time
    time = datetime.datetime.strptime(time_str, "%H:%M").time()

    # Преобразование времени обратно в формат чч:мм:сс
    formatted_time = time.strftime("%H:%M:%S")

    formatted_time_str = time.strftime("%H:%M")

    cur.execute("""
        UPDATE schedule SET is_available = FALSE, user_id = %s, user_name = %s, tg_username = %s WHERE date = %s AND time = %s
    """, (user_id, user_name, tg_username, formatted_date, formatted_time))

    conn.commit()

    await query.message.answer(f"*{user_first_name}*, вы успешно записались на стрижку *{formatted_date_str}* в *{formatted_time_str}*!", parse_mode=types.ParseMode.MARKDOWN)


# Обработчик выбора "Узнать местоположение"
@dp.callback_query_handler(lambda query: query.data == "get_location")
async def get_location(query: types.CallbackQuery):
    await bot.answer_callback_query(query.id)
    location_text = "📍 Местоположение:\nг. Владивосток, ул. Берёзовая, 20"
    location_url = "https://2gis.ru/vladivostok/directions/points/%7C131.893943%2C43.103735%3B70030076179627104?m=131.909635%2C43.117332%2F14.02"

    # Создаем инлайн-кнопку с ссылкой "Проложить маршрут"
    markup = types.InlineKeyboardMarkup()
    route_button = types.InlineKeyboardButton(text="Проложить маршрут", url=location_url)
    markup.add(route_button)

    await bot.send_message(query.from_user.id, text=location_text, reply_markup=markup)


# Обработчик выбора "Узнать прайс-лист"
@dp.callback_query_handler(lambda query: query.data == "get_price_list")
async def get_price_list(query: types.CallbackQuery):
    await bot.answer_callback_query(query.id)
    price_list = "Стрижка - 1500 ₽\nБорода - 1000 ₽\nКомплекс - 2200 ₽\nМаска - 500 ₽\nВоск - 200 ₽"
    await bot.send_message(query.from_user.id, text=price_list)


@dp.callback_query_handler(lambda query: query.data == "get_appointments")
async def get_appointments(query: types.CallbackQuery, state: FSMContext):
    user_id = query.from_user.id
    cur.execute("SELECT date, time FROM schedule WHERE user_id = %s", (user_id,))
    appointments = cur.fetchall()

    if not appointments:
        await query.message.answer("У вас пока нет записей на стрижку 🤷🏻‍♂️")
        return

    message_text = "Ваши записи на стрижку:\n\n"
    for appointment in appointments:
        date_str = appointment[0].strftime("%d.%m.%Y")
        time_str = appointment[1].strftime("%H:%M")
        message_text += f"• {date_str} в {time_str}\n"

    # Создайте инлайн-кнопки "Отменить запись" и "Назад"
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    cancel_button = types.InlineKeyboardButton("Отменить запись", callback_data="cancel_appointment")
    back_button = types.InlineKeyboardButton("Назад", callback_data="back")
    keyboard.add(cancel_button, back_button)

    # Сохраните текущее состояние пользователя
    await state.update_data(appointments=appointments)

    # Отправьте сообщение с записями и инлайн-кнопками
    await query.message.edit_text(message_text, reply_markup=keyboard)


@dp.callback_query_handler(lambda query: query.data == "cancel_appointment", state="*")
async def cancel_appointment(query: types.CallbackQuery, state: FSMContext):
    # Получите сохраненные данные состояния
    data = await state.get_data()
    appointments = data.get("appointments")

    if not appointments:
        await query.message.answer("У вас пока нет записей на стрижку 🤷🏻‍♂️")
        return

    # Создайте инлайн-кнопки для каждой записи на стрижку
    keyboard = types.InlineKeyboardMarkup()
    for i, appointment in enumerate(appointments):
        date_str = appointment[0].strftime("%d.%m.%Y")
        time_str = appointment[1].strftime("%H:%M")
        button = types.InlineKeyboardButton(f"{date_str} в {time_str}", callback_data=f"cancel_{i}")
        keyboard.add(button)

    # Сохраните текущее состояние пользователя
    await state.update_data(cancel=True)

    # Отправьте сообщение с инлайн-кнопками для выбора записи на отмену
    await query.message.answer("Выберите запись, которую хотите отменить:", reply_markup=keyboard)


@dp.callback_query_handler(lambda query: query.data.startswith("cancel_"), state="*")
async def confirm_cancel(query: types.CallbackQuery, state: FSMContext):
    # Получите сохраненные данные состояния
    data = await state.get_data()
    appointments = data.get("appointments")
    cancel = data.get("cancel")

    if not cancel or not appointments:
        return

    # Получите индекс записи на отмену из callback_data
    index = int(query.data.split("_")[1])

    # Обновите запись в базе данных, чтобы очистить данные и установить is_available в TRUE
    appointment = appointments[index]
    cur.execute("UPDATE schedule SET user_name = NULL, user_id = NULL, user_phone = NULL, is_available = TRUE WHERE date = %s AND time = %s", (appointment[0], appointment[1]))
    conn.commit()

    # Отправьте сообщение о успешной отмене записи
    date_str = appointment[0].strftime("%d.%m.%Y")
    time_str = appointment[1].strftime("%H:%M")
    await query.message.answer(f"Вы успешно отменили запись на *{date_str}* в *{time_str}*.", parse_mode=types.ParseMode.MARKDOWN)

    # Очистите сохраненные данные состояния
    await state.reset_state()


@dp.callback_query_handler(lambda query: query.data == "back")
async def back_handler(query: types.CallbackQuery):
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        types.InlineKeyboardButton(text="✂️ Записаться на стрижку ✂️", callback_data="book_cut"),
        types.InlineKeyboardButton(text="📍 Узнать местоположение 📍", callback_data="get_location"),
        types.InlineKeyboardButton(text="💵 Узнать прайс-лист 💵", callback_data="get_price_list"),
        types.InlineKeyboardButton(text="📅 Мои записи 📅", callback_data="get_appointments")
    )
    bold_name = f"<b>{query.from_user.first_name}</b>"
    await query.message.answer(f"Добрый день, {bold_name}! Чем могу помочь? 🤔", reply_markup=keyboard, parse_mode="html")


# Запуск бота
async def main():
    await dp.start_polling()


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
