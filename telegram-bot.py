import os
import json
import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackContext, CallbackQueryHandler
from telegram.ext.filters import BaseFilter, Document as TelegramDocument
from docx import Document

# Отримуємо токен із змінних середовища
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")

# Ініціалізація даних
DATA_FILE = "bot_data.json"
ADMIN_PASSWORD = "admin123"

# Завантаження даних із JSON або ініціалізація початкових даних
def load_data():
    initial_data = {
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
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        data = initial_data
        save_data(data)
    return data

# Збереження даних у JSON
def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# Ініціалізація даних
data = load_data()
substitutions_df = pd.DataFrame(data["substitutions"])
alert_mode = data["alert_mode"]
users = data["users"]

# Перевірка пароля
def check_admin(password):
    return password == ADMIN_PASSWORD

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
        print(f"Отримані заголовки таблиці: {headers}")  # Додаємо логування
        
        # Перевіряємо, чи є потрібні заголовки
        required_headers = ["Дата", "Клас"] + [f"Урок {i}" for i in range(0, 8)]
        missing_headers = [h for h in required_headers if h not in headers]
        if missing_headers:
            raise ValueError(f"Відсутні необхідні стовпці: {missing_headers}")
        
        # Зчитуємо дані
        for row in table.rows[1:]:
            row_data = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if row_data:  # Пропускаємо порожні рядки
                # Доповнюємо рядок, якщо він коротший за кількість заголовків
                while len(row_data) < len(headers):
                    row_data.append("")
                data.append(row_data)
        
        return pd.DataFrame(data, columns=headers)
    except Exception as e:
        raise Exception(f"Помилка при зчитуванні таблиці: {str(e)}")

# Функція для старту бота
async def start(update: Update, context: CallbackContext) -> None:
    global users
    user_id = update.effective_user.id
    if user_id not in users:
        users.append(user_id)
        data["users"] = users
        save_data(data)

    keyboard = [
        [InlineKeyboardButton("Переглянути заміни", callback_data='view_subs')],
        [InlineKeyboardButton("Оновити таблицю (Адмін)", callback_data='update_subs')],
        [InlineKeyboardButton("Режим тривоги (Адмін)", callback_data='toggle_alert')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Вітаю! Я бот для перегляду замін уроків. Оберіть опцію:", reply_markup=reply_markup)

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
    global substitutions_df, alert_mode, data
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
                data["alert_mode"] = alert_mode
                save_data(data)
                status = "увімкнено" if alert_mode else "вимкнено"
                message = f"⚠️ Режим тривоги {status}! Навчання буде проводитися дистанційно." if alert_mode else "✅ Тривогу скасовано. Навчання повертається до звичайного режиму."
                await notify_users(context, message)
                await update.message.reply_text(f"Режим тривоги {status}.")
        else:
            await update.message.reply_text("Неправильний пароль! Спробуйте ще раз:")
        return

    # Обробка звичайного запиту
    if "які заміни" in message_text.lower():
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
    global substitutions_df, data
    if not context.user_data.get('is_admin'):
        await update.message.reply_text("Спочатку увійдіть у режим адміністратора, натиснувши 'Оновити таблицю (Адмін)' і ввівши пароль.")
        return

    if update.message.document and update.message.document.file_name.endswith('.docx'):
        file = await update.message.document.get_file()
        try:
            file_path = await file.download_to_drive()
            print(f"Завантажено файл: {file_path}")  # Додаємо логування
            new_df = extract_table_from_docx(file_path)
            required_columns = ["Дата", "Клас"] + [f"Урок {i}" for i in range(0, 8)]
            if not all(col in new_df.columns for col in required_columns):
                await update.message.reply_text("Формат таблиці не відповідає встановленому. Очікувані стовпці: " + ", ".join(required_columns))
                return
            substitutions_df = new_df
            data["substitutions"] = substitutions_df.to_dict()
            save_data(data)
            context.user_data.pop('is_admin')
            await update.message.reply_text("Таблицю успішно оновлено з .docx файлу!")
        except Exception as e:
            await update.message.reply_text(f"Помилка при обробці .docx файлу: {str(e)}")
        finally:
            if 'file_path' in locals():
                os.remove(file_path)  # Видаляємо тимчасовий файл
                print(f"Видалено тимчасовий файл: {file_path}")

# Запуск бота
def main() -> None:
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button, pattern='^(view_subs|update_subs|toggle_alert)$'))
    application.add_handler(CallbackQueryHandler(handle_class_selection, pattern='^class_'))
    application.add_handler(MessageHandler(BaseFilter(), handle_text))
    application.add_handler(MessageHandler(TelegramDocument(), handle_docx))

    application.run_polling()

if __name__ == '__main__':
    main()
