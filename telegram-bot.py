import os
import re
import pandas as pd
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackContext, CallbackQueryHandler
from telegram.ext.filters import BaseFilter, Document as TelegramDocument
from docx import Document

# Отримуємо токен із змінних середовища
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")

# Ініціалізація початкових даних
INITIAL_DATA = {
    "substitutions": {
        "Дата": ["02.05.2025", "02.05.2025", "02.05.2025", "02.05.2025"],
        "Клас": ["6-А", "6-Б", "7-А", "7-Б"],
        "Урок 0": ["За.рл", "", "", ""],
        "Урок 1": ["", "Матем", "Теометр", "Фіз.л"],
        "Урок 2": ["", "", "Укр.м", "Укр.м"],
        "Урок 3": ["", "Муз.м", "", "Теометр"],
        "Урок 4": ["", "", "", "Нім.м"],
        "Урок 5": ["", "", "", ""],
        "Урок 6": ["", "", "", ""],
        "Урок 7": ["", "", "", ""]
    },
    "alert_mode": False,
    "users": []
}

# Глобальні змінні
substitutions_df = pd.DataFrame(INITIAL_DATA["substitutions"])
alert_mode = INITIAL_DATA["alert_mode"]
users = INITIAL_DATA["users"]
ADMIN_PASSWORD = "admin123"

# Перевірка пароля
def check_admin(password):
    return password == ADMIN_PASSWORD

# Очищення HTML-тегів із тексту
def clean_html_tags(text):
    if not isinstance(text, str):
        return ""
    cleaned = re.sub(r'<[^>]+>', '', text).strip()
    print(f"Очищено текст: '{text}' -> '{cleaned}'")
    return cleaned

# Функція для витягнення таблиці з .docx
def extract_table_from_docx(file_path):
    try:
        doc = Document(file_path)
        if not doc.tables:
            raise ValueError("У документі немає таблиць")
        
        # Беремо першу таблицю
        table = doc.tables[0]
        data = []
        # Отримуємо заголовки
        headers = [cell.text.strip() for cell in table.rows[0].cells if cell.text.strip()]
        print(f"Отримані заголовки таблиці: {headers}")
        
        # Перевіряємо, чи є потрібні заголовки
        required_headers = ["Дата", "Клас"] + [f"Урок {i}" for i in range(0, 8)]
        missing_headers = [h for h in required_headers if h not in headers]
        if missing_headers:
            raise ValueError(f"Відсутні необхідні стовпці: {missing_headers}")
        
        # Зчитуємо дані
        for row in table.rows[1:]:
            row_data = [clean_html_tags(cell.text) for cell in row.cells]
            if any(row_data):  # Пропускаємо повністю порожні рядки
                # Доповнюємо рядок, якщо він коротший за кількість заголовків
                while len(row_data) < len(headers):
                    row_data.append("")
                data.append(row_data)
        
        df = pd.DataFrame(data, columns=headers)
        print(f"Зчитана таблиця:\n{df.to_string()}")
        return df
    except Exception as e:
        raise Exception(f"Помилка при зчитуванні таблиці: {str(e)}")

# Функція для старту бота
async def start(update: Update, context: CallbackContext) -> None:
    global users
    user_id = update.effective_user.id
    if user_id not in users:
        users.append(user_id)

    keyboard = [
        [InlineKeyboardButton("Переглянути заміни", callback_data='view_subs')],
        [InlineKeyboardButton("Оновити таблицю (Адмін)", callback_data='update_subs')],
        [InlineKeyboardButton("Режим тривоги (Адмін)", callback_data='toggle_alert')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Вітаю! Я бот для перегляду замін уроків. Оберіть опцію:", reply_markup=reply_markup)

# Скидання даних до початкових (для адміна)
async def reset(update: Update, context: CallbackContext) -> None:
    context.user_data.clear()
    context.user_data['awaiting_password'] = True
    context.user_data['action'] = 'reset'
    await update.message.reply_text("Введіть пароль адміністратора для скидання даних:")

# Обробка кнопок
async def button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == 'view_subs':
        keyboard = [[InlineKeyboardButton(cls, callback_data=f'class_{cls}')] for cls in substitutions_df["Клас"].unique()]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Оберіть клас:", reply_markup=reply_markup)
    elif query.data == 'update_subs':
        context.user_data.clear()
        context.user_data['awaiting_password'] = True
        context.user_data['action'] = 'update_subs'
        await query.message.reply_text("Введіть пароль адміністратора:")
    elif query.data == 'toggle_alert':
        context.user_data.clear()
        context.user_data['awaiting_password'] = True
        context.user_data['action'] = 'toggle_alert'
        await query.message.reply_text("Введіть пароль адміністратора:")

# Обробка вибору класу
async def handle_class_selection(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    class_name = query.data.split('_')[1]
    print(f"Запит замін для класу: {class_name}")
    print(f"Поточна таблиця замін:\n{substitutions_df.to_string()}")
    class_subs = substitutions_df[substitutions_df["Клас"] == class_name]

    if class_subs.empty:
        await query.message.reply_text(f"Для класу {class_name} немає замін.")
        return

    response = f"Заміни для {class_name} на {class_subs['Дата'].iloc[0]}:\n"
    for col in [f"Урок {i}" for i in range(0, 8)]:
        value = class_subs[col].iloc[0]
        if value and value != "" and value != "-":
            response += f"{col}: {value}\n"
    if alert_mode:
        response += "\n⚠️ Увага: у зв’язку з тривогою навчання проводиться дистанційно!"
    await query.message.reply_text(response)

# Повідомлення всіх користувачів про тривогу
async def notify_users(context: CallbackContext, message: str):
    for user_id in users:
        try:
            await context.bot.send_message(chat_id=user_id, text=message)
        except Exception as e:
            print(f"Не вдалося надіслати повідомлення користувачу {user_id}: {e}")

# Обробка текстових повідомлень
async def handle_text(update: Update, context: CallbackContext) -> None:
    global substitutions_df, alert_mode, users
    message_text = update.message.text

    # Перевірка пароля для адміністратора
    if context.user_data.get('awaiting_password'):
        if check_admin(message_text):
            context.user_data['is_admin'] = True
            context.user_data.pop('awaiting_password')
            action = context.user_data.get('action')
            if action == 'update_subs':
                await update.message.reply_text("Пароль правильний! Надішліть .docx файл із таблицею.")
            elif action == 'toggle_alert':
                alert_mode = not alert_mode
                status = "увімкнено" if alert_mode else "вимкнено"
                message = f"⚠️ Режим тривоги {status}! Навчання буде проводитися дистанційно." if alert_mode else "✅ Тривогу скасовано. Навчання повертається до звичайного режиму."
                await notify_users(context, message)
                await update.message.reply_text(f"Режим тривоги {status}.")
            elif action == 'reset':
                substitutions_df = pd.DataFrame(INITIAL_DATA["substitutions"])
                alert_mode = INITIAL_DATA["alert_mode"]
                users = INITIAL_DATA["users"]
                await update.message.reply_text("Дані скинуто до початкових!")
        else:
            await update.message.reply_text("Неправильний пароль! Спробуйте ще раз:")
        return

    # Обробка звичайного запиту
    if "які заміни" in message_text.lower():
        print(f"Запит через текст: {message_text}")
        print(f"Поточна таблиця замін:\n{substitutions_df.to_string()}")
        for class_name in substitutions_df["Клас"].unique():
            if class_name.lower() in message_text.lower():
                class_subs = substitutions_df[substitutions_df["Клас"] == class_name]
                if class_subs.empty:
                    await update.message.reply_text(f"Для класу {class_name} немає замін.")
                    return
                response = f"Заміни для {class_name} на {class_subs['Дата'].iloc[0]}:\n"
                for col in [f"Урок {i}" for i in range(0, 8)]:
                    value = class_subs[col].iloc[0]
                    if value and value != "" and value != "-":
                        response += f"{col}: {value}\n"
                if alert_mode:
                    response += "\n⚠️ Увага: у зв’язку з тривогою навчання проводиться дистанційно!"
                await update.message.reply_text(response)
                return
        await update.message.reply_text("Будь ласка, вкажіть клас (наприклад, 'Які заміни в 6-А?').")
    else:
        await update.message.reply_text("Я розумію запити типу 'Які заміни в 6-А?'. Спробуйте ще раз!")

# Обробка .docx файлів
async def handle_docx(update: Update, context: CallbackContext) -> None:
    global substitutions_df
    if not context.user_data.get('is_admin'):
        await update.message.reply_text("Спочатку увійдіть у режим адміністратора, натиснувши 'Оновити таблицю (Адмін)' і ввівши пароль.")
        return

    if update.message.document and update.message.document.file_name.endswith('.docx'):
        file = await update.message.document.get_file()
        try:
            file_path = await file.download_to_drive()
            print(f"Завантажено файл: {file_path}")
            new_df = extract_table_from_docx(file_path)
            required_columns = ["Дата", "Клас"] + [f"Урок {i}" for i in range(0, 8)]
            if not all(col in new_df.columns for col in required_columns):
                await update.message.reply_text("Формат таблиці не відповідає встановленому. Очікувані стовпці: " + ", ".join(required_columns))
                return
            substitutions_df = new_df
            print(f"Оновлена таблиця замін:\n{substitutions_df.to_string()}")
            context.user_data.pop('is_admin')
            await update.message.reply_text("Таблицю успішно оновлено з .docx файлу!")
        except Exception as e:
            await update.message.reply_text(f"Помилка при обробці .docx файлу: {str(e)}")
        finally:
            if 'file_path' in locals():
                os.remove(file_path)
                print(f"Видалено тимчасовий файл: {file_path}")

# Запуск бота
async def async_main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("reset", reset))
    application.add_handler(CallbackQueryHandler(button, pattern='^(view_subs|update_subs|toggle_alert)$'))
    application.add_handler(CallbackQueryHandler(handle_class_selection, pattern='^class_'))
    application.add_handler(MessageHandler(BaseFilter(), handle_text))
    application.add_handler(MessageHandler(TelegramDocument(), handle_docx))

    # Затримка перед запуском polling
    print("Чекаємо 5 секунд перед запуском polling...")
    await asyncio.sleep(5)
    print("Запускаємо polling...")
    await application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    asyncio.run(async_main())
