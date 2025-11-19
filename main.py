from flask import Flask, request
import telebot
from telebot import types

# ====== Настройки ======
BOT_TOKEN = "8009524027:AAHTRgwiKnUi9AAh1_LTkekGZ-mRvNzH7dY"
OWNER_ID = 1470389051

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ====== База данных ======
reviews_db = {
    "admins": {
        "sherlock": {
            "display": "#Шерлок",
            "reviews": []
        }
    }
}

# ====== Команда старт ======
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Привет братик! Бот отзывов запущен, выбирай кнопку.")

# ====== Просмотр рейтинга ======
@bot.message_handler(func=lambda m: m.text == "📊 Посмотреть репутацию")
def show_ratings(message):
    txt = ""
    for k, info in reviews_db["admins"].items():
        reviews = info["reviews"]
        if not reviews:
            continue
        avg = round(sum(r["stars"] for r in reviews) / len(reviews), 2)
        txt += f"{info['display']} — {'⭐️'*int(avg)} ({avg})\n"
        for r in reviews:
            txt += f"   • {r['user']} — {'⭐️'*r['stars']} {r['text']}\n"
    bot.send_message(message.chat.id, txt or "Пока нет отзывов.")

# ====== Админ меню ======
@bot.message_handler(func=lambda m: m.text == "🛠 Админ-меню")
def admin_menu(message):
    if message.from_user.id != OWNER_ID:
        bot.send_message(message.chat.id, "⛔️ Нет доступа.")
        return
    kb = types.InlineKeyboardMarkup()
    for k, info in reviews_db["admins"].items():
        kb.add(types.InlineKeyboardButton(info["display"], callback_data=f"adm|{k}"))
    bot.send_message(message.chat.id, "Выберите администратора:", reply_markup=kb)

# ====== Callback ======
@bot.callback_query_handler(func=lambda c: True)
def admin_actions(call):
    bot.answer_callback_query(call.id)

# ====== Webhook ======
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = telebot.types.Update.de_json(request.data.decode("utf-8"))
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/")
def home():
    return "Bot is LIVE! 🔥"

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=f"https://telegram-review-bo.onrender.com/{BOT_TOKEN}")
    app.run(host="0.0.0.0", port=8080)
