import os
import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackContext, CallbackQueryHandler
from telegram.ext.filters import BaseFilter, Document as TelegramDocument
from docx import Document

# Отримуємо токен і URL з змінних середовища
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "https://your-service-name.onrender.com")

# Ініціалізація таблиці замін
initial_data = {
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
}
substitutions_df = pd.DataFrame(initial_data)

# Пароль адміністратора
ADMIN_PASSWORD = "admin123"

# Перевірка пароля
def check_admin(password):
    return password == ADMIN_PASSWORD

# Функція для витягнення таблиці з .docx
def extract_table_from_docx(file_path):
    doc = Document(file_path)
    table = doc.tables[0]  # Беремо першу таблицю
    data = []
    headers = [cell.text.strip() for cell in table.rows[0].cells if cell.text.strip()]
    for row in table.rows[1:]:
        row_data = [cell.text.strip() for cell in row.cells if cell.text.strip()]
        if row_data:  # Пропускаємо порожні рядки
            data.append(row_data)
    return pd.DataFrame(data, columns=headers)

# Функція для старту бота
async def start(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [InlineKeyboardButton("Переглянути заміни", callback_data='view_subs')],
        [InlineKeyboardButton("Оновити таблицю (Адмін)", callback_data='update_subs')]
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
        if value and value != "":
            response += f"{col}: {value}\n"
    await query.message.reply_text(response)

# Обробка текстових повідомлень
async def handle_text(update: Update, context: CallbackContext) -> None:
    global substitutions_df
    print(f"User data: {context.user_data}")
    message_text = update.message.text

    # Перевірка пароля для адміністратора
    if context.user_data.get('awaiting_password'):
        if check_admin(message_text):
            context.user_data['is_admin'] = True
            context.user_data.pop('awaiting_password')
            await update.message.reply_text("Пароль правильний! Надішліть .docx файл із таблицею.")
        else:
            await update.message.reply_text("Неправильний пароль! Спробуйте ще раз:")
        return

    # Оновлення таблиці текстом (для сумісності)
    if context.user_data.get('is_admin'):
        print("Admin mode active, processing table update")
        if message_text is None or not message_text.strip():
            await update.message.reply_text("Надішліть таблицю у форматі:\nДата,Клас,Урок 0,Урок 1,Урок 2,Урок 3,Урок 4,Урок 5,Урок 6,Урок 7\nПриклад:\n02.05.2025,6-А,Матем,,,,,,,")
            return
        try:
            lines = message_text.split('\n')
            data = [line.split(',') for line in lines]
            new_df = pd.DataFrame(data[1:], columns=data[0])
            required_columns = ["Дата", "Клас"] + [f"Урок {i}" for i in range(0, 8)]
            if not all(col in new_df.columns for col in required_columns):
                await update.message.reply_text("Формат таблиці не відповідає встановленому")
                return
            substitutions_df = new_df
            context.user_data.pop('is_admin')
            await update.message.reply_text("Таблицю успішно оновлено!")
        except Exception as e:
            await update.message.reply_text(f"Помилка при оновленні таблиці: {str(e)}")
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
                    if value and value != "":
                        response += f"{col}: {value}\n"
                await update.message.reply_text(response)
                return
        await update.message.reply_text("Будь ласка, вкажіть клас (наприклад, 'Які заміни в 6-А?').")
    else:
        await update.message.reply_text("Я розумію запити типу 'Які заміни в 6-А?'. Спробуйте ще раз!")

# Обробка .docx файлів
async def handle_docx(update: Update, context: CallbackContext) -> None:
    global substitutions_df
    print(f"User data: {context.user_data}")

    if not context.user_data.get('is_admin'):
        await update.message.reply_text("Спочатку увійдіть у режим адміністратора, натиснувши 'Оновити таблицю (Адмін)' і ввівши пароль.")
        return

    if update.message.document and update.message.document.file_name.endswith('.docx'):
        file = await update.message.document.get_file()
        file_path = await file.download_to_drive()
        try:
            new_df = extract_table_from_docx(file_path)
            required_columns = ["Дата", "Клас"] + [f"Урок {i}" for i in range(0, 8)]
            if not all(col in new_df.columns for col in required_columns):
                await update.message.reply_text("Формат таблиці не відповідає встановленому")
                return
            substitutions_df = new_df
            context.user_data.pop('is_admin')
            await update.message.reply_text("Таблицю успішно оновлено з .docx файлу!")
        except Exception as e:
            await update.message.reply_text(f"Помилка при обробці .docx файлу: {str(e)}")
        finally:
            import os
            os.remove(file_path)  # Видаляємо тимчасовий файл

# Запуск бота
def main() -> None:
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button, pattern='^(view_subs|update_subs)$'))
    application.add_handler(CallbackQueryHandler(handle_class_selection, pattern='^class_'))
    application.add_handler(MessageHandler(BaseFilter(), handle_text))
    application.add_handler(MessageHandler(TelegramDocument(), handle_docx))

    # Налаштування Webhook
    application.run_webhook(
        listen="0.0.0.0",
        port=8000,  # Порт, який використовується на Render
        url_path=TOKEN,
        webhook_url=f"{WEBHOOK_URL}/{TOKEN}"
    )

if __name__ == '__main__':
    main()
