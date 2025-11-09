import os
import json
import threading
from datetime import datetime
from flask import Flask
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
import telebot
from telebot import types as tele_types

# ==============================
# 🔹 Настройки для обоих ботов
# ==============================

# --- Бот "Шепот сердец"
SHEPOT_TOKEN = "8445444619:AAFdR4jF1IQJzEFlL_DsJ-JTxT9nwkwwC58"
ADMIN_CHAT_ID = -1003120877184  # ID группы администраторов

# --- Бот отзывов
REVIEWS_TOKEN = "7974881474:AAHOzEfo2pOxDdznJK-ED9tGikw6Yl7jZDY"
OWNER_ID = 1470389051
DATA_FILE = "reviews_data.json"

# Flask сервер (для Render)
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Оба бота запущены и работают!"

# ====================================================
# 🔸 БОТ 1 — «Шепот сердец» (aiogram)
# ====================================================

shepot_bot = Bot(token=SHEPOT_TOKEN)
dp = Dispatcher(shepot_bot)

@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    await message.answer(
        "👋 Привет!\n"
        "Я — бот *Шепот сердец 💌*\n\n"
        "Можешь написать своё сообщение — администратор скоро тебе ответит.",
        parse_mode="Markdown"
    )

@dp.message_handler(content_types=types.ContentType.ANY)
async def forward_to_admins(message: types.Message):
    user_id = message.from_user.id
    username = f"@{message.from_user.username}" if message.from_user.username else "без_юзернейма"
    text = f"📩 Сообщение от {username} (ID: {user_id}):\n\n{message.text or '[не текстовое сообщение]'}"
    await shepot_bot.send_message(ADMIN_CHAT_ID, text)

@dp.message_handler(lambda msg: msg.chat.id == ADMIN_CHAT_ID and msg.reply_to_message)
async def reply_to_user(message: types.Message):
    try:
        original = message.reply_to_message.text
        user_id = int(original.split('ID:')[1].split(')')[0])
        await shepot_bot.send_message(user_id, message.text)
    except Exception as e:
        await message.reply(f"⚠️ Ошибка: {e}")

def run_shepot():
    executor.start_polling(dp, skip_updates=True)

# ====================================================
# 🔸 БОТ 2 — «Отзывы» (telebot)
# ====================================================

reviews_bot = telebot.TeleBot(REVIEWS_TOKEN)

if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        reviews_db = json.load(f)
else:
    reviews_db = {"admins": {}, "pending": {}}

def save_db():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(reviews_db, f, ensure_ascii=False, indent=2)

def normalize_tag(tag: str) -> str:
    return tag.strip().lower()

def ensure_admin_exists(tag_raw: str):
    key = normalize_tag(tag_raw)
    if key not in reviews_db["admins"]:
        reviews_db["admins"][key] = {"display": tag_raw.strip(), "reviews": []}
        save_db()
    else:
        reviews_db["admins"][key]["display"] = tag_raw.strip()
        save_db()
    return key

def is_owner(uid):
    return str(uid) == str(OWNER_ID)

@reviews_bot.message_handler(commands=['start'])
def start_cmd(message):
    kb = tele_types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("⭐ Оставить отзыв", "📊 Посмотреть репутацию")
    if is_owner(message.from_user.id):
        kb.add("🛠️ Админ-меню")
    reviews_bot.send_message(message.chat.id,
                     "👋 Привет! Я бот для отзывов.\n\n"
                     "— Нажми «⭐ Оставить отзыв», чтобы оценить администратора.\n"
                     "— Нажми «📊 Посмотреть репутацию», чтобы увидеть оценки и отзывы.",
                     reply_markup=kb)

@reviews_bot.message_handler(func=lambda m: m.text == "⭐ Оставить отзыв")
def rate_start(message):
    reviews_bot.send_message(message.chat.id, "Введите хэштег администратора, начиная с # (например, #Шерлок)")
    reviews_bot.register_next_step_handler(message, rate_admin)

def rate_admin(message):
    tag = message.text.strip()
    if not tag.startswith("#"):
        reviews_bot.send_message(message.chat.id, "⚠️ Хэштег должен начинаться с #. Пример: #Шерлок")
        return
    key = ensure_admin_exists(tag)
    kb = tele_types.InlineKeyboardMarkup(row_width=5)
    for i in range(1, 6):
        kb.add(tele_types.InlineKeyboardButton("⭐" * i, callback_data=f"rate|{key}|{i}"))
    reviews_bot.send_message(message.chat.id, f"Вы выбрали {tag}. Выберите количество звёзд:", reply_markup=kb)

@reviews_bot.callback_query_handler(func=lambda c: c.data.startswith("rate|"))
def rate_callback(call):
    _, key, stars = call.data.split("|")
    stars = int(stars)
    user_id = str(call.from_user.id)
    reviews_db["pending"][user_id] = {"key": key, "stars": stars}
    save_db()
    reviews_bot.send_message(call.message.chat.id, "Теперь напишите текст отзыва или «-» чтобы пропустить:")
    reviews_bot.answer_callback_query(call.id)

@reviews_bot.message_handler(func=lambda m: str(m.from_user.id) in reviews_db.get("pending", {}))
def save_review(message):
    user_id = str(message.from_user.id)
    p = reviews_db["pending"].pop(user_id)
    key, stars = p["key"], p["stars"]
    text = "" if message.text.strip() == "-" else message.text.strip()
    entry = {
        "user": message.from_user.username or f"id{message.from_user.id}",
        "stars": stars,
        "text": text,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    reviews_db["admins"][key]["reviews"].append(entry)
    save_db()
    reviews_bot.send_message(message.chat.id, f"✅ Отзыв сохранён! {'⭐'*stars}")

@reviews_bot.message_handler(func=lambda m: m.text == "📊 Посмотреть репутацию")
def show_ratings(message):
    if not reviews_db["admins"]:
        reviews_bot.send_message(message.chat.id, "Пока что нет отзывов.")
        return
    txt = ""
    for k, info in reviews_db["admins"].items():
        reviews = info["reviews"]
        if not reviews:
            continue
        avg = round(sum(r["stars"] for r in reviews) / len(reviews), 2)
        txt += f"{info['display']} — {'⭐'*int(avg)} ({avg})\n"
        for r in reviews:
            user = r['user']
            stars = '⭐' * r['stars']
            text = f" — {r['text']}" if r['text'] else ""
            txt += f"   • {user}: {stars}{text}\n"
        txt += "\n"
    reviews_bot.send_message(message.chat.id, txt or "Пока нет отзывов.")

def run_reviews():
    reviews_bot.infinity_polling(timeout=60, long_polling_timeout=60)

# ====================================================
# 🔸 Запуск ОБОИХ ботов
# ====================================================

if __name__ == "__main__":
    threading.Thread(target=run_shepot).start()
    threading.Thread(target=run_reviews).start()
    app.run(host="0.0.0.0", port=8080)
