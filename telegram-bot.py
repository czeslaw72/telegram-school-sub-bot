import os
import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler

# Отримуємо токен з змінних середовища
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")

# Ініціалізація таблиці замін
initial_data = {
    "Дата": ["02.05.2025", "02.05.2025", "02.05.2025", "02.05.2025"],
    "Клас": ["6-А", "6-Б", "7-А", "7-Б"],
    "Урок 1": ["За.рл", "", "", ""],
    "Урок 2": ["", "Матем", "Теометр", "Фіз.л"],
    "Урок 3": ["", "", "Укр.м", "Укр.м"],
    "Урок 4": ["", "Муз.м", "", "Теометр"],
    "Урок 5": ["", "", "", "Нім.м"],
    "Урок 6": ["", "", "", ""],
    "Урок 7": ["", "", "", ""],
    "Урок 8": ["", "", "", ""]
}
substitutions_df = pd.DataFrame(initial_data)

# Пароль адміністратора
ADMIN_PASSWORD = "admin123"

# Перевірка пароля
def check_admin(password):
    return password == ADMIN_PASSWORD

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
    for col in [f"Урок {i}" for i in range(1, 9)]:
        value = class_subs[col].iloc[0]
        if value and value != "":
            response += f"{col}: {value}\n"
    await query.message.reply_text(response)

# Обробка текстових повідомлень
async def handle_message(update: Update, context: CallbackContext) -> None:
    global substitutions_df
    message_text = update.message.text

    # Перевірка пароля для адміністратора
    if context.user_data.get('awaiting_password'):
        if check_admin(message_text):
            context.user_data['is_admin'] = True
            context.user_data.pop('awaiting_password')
            await update.message.reply_text("Пароль правильний! Надішліть таблицю замін у форматі:\nДата,Клас,Урок 1,Урок 2,Урок 3,Урок 4,Урок 5,Урок 6,Урок 7,Урок 8\nПриклад:\n02.05.2025,6-А,За.рл,,,,,,,")
        else:
            await update.message.reply_text("Неправильний пароль! Спробуйте ще раз:")
        return

    # Оновлення таблиці адміністратором
    if context.user_data.get('is_admin'):
        try:
            lines = message_text.split('\n')
            data = [line.split(',') for line in lines]
            new_df = pd.DataFrame(data[1:], columns=data[0])
            required_columns = ["Дата", "Клас"] + [f"Урок {i}" for i in range(1, 9)]
            if not all(col in new_df.columns for col in required_columns):
                await update.message.reply_text("Таблиця повинна містити колонки: Дата, Клас, Урок 1–Урок 8!")
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
                for col in [f"Урок {i}" for i in range(1, 9)]:
                    value = class_subs[col].iloc[0]
                    if value and value != "":
                        response += f"{col}: {value}\n"
                await update.message.reply_text(response)
                return
        await update.message.reply_text("Будь ласка, вкажіть клас (наприклад, 'Які заміни в 6-А?').")
    else:
        await update.message.reply_text("Я розумію запити типу 'Які заміни в 6-А?'. Спробуйте ще раз!")

# Обробка введення пароля
async def handle_password(update: Update, context: CallbackContext) -> None:
    context.user_data['awaiting_password'] = True
    await handle_message(update, context)

# Запуск бота
def main() -> None:
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button, pattern='^(view_subs|update_subs)$'))
    application.add_handler(CallbackQueryHandler(handle_class_selection, pattern='^class_'))
    application.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    application.run_polling()

if __name__ == '__main__':
    main()
