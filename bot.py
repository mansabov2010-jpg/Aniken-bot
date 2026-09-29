import json
import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

TOKEN = "8845458932:AAHDQOxJN_LVVaqDw1iur0nKWNAbFjhSp1w"
ADMIN_ID = 7986354170

bot = telebot.TeleBot(TOKEN)
DB_FILE = "anime_db.json"
USERS_FILE = "users.json"

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

db = load_db()

# Admin uchun boshqaruv menyusi
def get_admin_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("➕ Yeni anime bo'limi"), KeyboardButton("🔄 Mavjud animeni almashtirish"))
    markup.add(KeyboardButton("🔍 Nomi orqali qidirish"), KeyboardButton("🔢 Kod orqali qidirish"))
    markup.add(KeyboardButton("📋 Animelar ro'yxati"), KeyboardButton("📊 Statistika"))
    return markup

# Oddiy foydalanuvchi menyusi
def get_user_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("🚀 Start (Asosiy menyu)"))
    markup.add(KeyboardButton("🎬 Animelar ro'yxati"), KeyboardButton("ℹ️ Bot haqida"))
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    users = load_users()
    if user_id not in users:
        users.append(user_id)
        save_users(users)
        
    if user_id == ADMIN_ID:
        bot.send_message(
            message.chat.id,
            "✨ *AniKen dunyosiga xush kelibsiz!*\n\nSalom Admin! Kerakli bo'limni tanlang:",
            parse_mode="Markdown",
            reply_markup=get_admin_keyboard()
        )
    else:
        bot.send_message(
            message.chat.id,
            "✨ *AniKen dunyosiga xush kelibsiz!*\n\n🎬 Bu yerda siz eng sara anime va animatsion filmlarni eng yuqori sifatda topishingiz mumkin.\n💖 Sizning har bir tashrifingiz biz uchun katta quvonch, har doim biz bilan birga bo'ling!\n\nBotdan foydalanish uchun pastdagi tugmani bosing:",
            parse_mode="Markdown",
            reply_markup=get_user_keyboard()
        )

@bot.message_handler(func=lambda message: message.text in ["🚀 Start (Asosiy menyu)", "🎬 Animelar ro'yxati"])
def show_anime_groups(message):
    if not db:
        bot.send_message(message.chat.id, "Hozircha animelar mavjud emas.")
        return
    
    markup = InlineKeyboardMarkup(row_width=1)
    for anime_name in db.keys():
        markup.add(InlineKeyboardButton(f"📁 {anime_name}", callback_data=f"group_{anime_name}"))
    bot.send_message(message.chat.id, "📺 *Mavjud anime bo'limlari va jildlari:*", parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "ℹ️ Bot haqida")
def about_bot(message):
    bot.send_message(message.chat.id, "🤖 Bu bot orqali sevimli animelaringizni guruhlar va qismlarga bo'lingan holda osongina topib tomosha qilishingiz mumkin.")

# Admin bo'limlari
@bot.message_handler(func=lambda message: message.text == "➕ Yeni anime bo'limi" and message.from_user.id == ADMIN_ID)
def admin_add_anime(message):
    msg = bot.send_message(message.chat.id, "Yangi anime bo'limi nomini kiriting (masalan: *Death note (1 fasl)*):", parse_mode="Markdown")
    bot.register_next_step_handler(msg, step_anime_name)

def step_anime_name(message):
    anime_name = message.text.strip()
    msg = bot.send_message(message.chat.id, f"'{anime_name}' uchun qism raqamini kiriting (masalan: 1):")
    bot.register_next_step_handler(msg, step_part_num, anime_name)

def step_part_num(message, anime_name):
    part = message.text.strip()
    msg = bot.send_message(message.chat.id, f"'{anime_name}' ning {part}-qismining *VIDEOSINI* yuboring:", parse_mode="Markdown")
    bot.register_next_step_handler(msg, step_save_video, anime_name, part)

def step_save_video(message, anime_name, part):
    if message.video:
        file_id = message.video.file_id
        if anime_name not in db:
            db[anime_name] = {}
        db[anime_name][part] = file_id
        save_db(db)
        bot.send_message(message.chat.id, f"✅ Muvaffaqiyatli saqlandi!\n\nBo'lim: {anime_name}\nQism: {part}", reply_markup=get_admin_keyboard())
    else:
        bot.send_message(message.chat.id, "⚠️ Iltimos, faqat video fayl yuboring!", reply_markup=get_admin_keyboard())

@bot.message_handler(func=lambda message: message.text == "📋 Animelar ro'yxati" and message.from_user.id == ADMIN_ID)
def admin_list(message):
    if not db:
        bot.send_message(message.chat.id, "Hozircha animelar yo'q.", reply_markup=get_admin_keyboard())
        return
    markup = InlineKeyboardMarkup(row_width=1)
    for anime in db.keys():
        markup.add(InlineKeyboardButton(f"🗑 O'chirish: {anime}", callback_data=f"del_{anime}"))
    bot.send_message(message.chat.id, "O'chirmoqchi bo'lgan anime bo'limini tanlang:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "📊 Statistika" and message.from_user.id == ADMIN_ID)
def admin_stats(message):
    users = load_users()
    text = f"📊 *Bot statistikasi:*\n\n👥 Foydalanuvchilar: {len(users)} ta\n📁 Anime bo'limlari: {len(db)} ta"
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=get_admin_keyboard())

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    data = call.data
    
    if data.startswith("group_"):
        anime_name = data.replace("group_", "")
        if anime_name in db:
            markup = InlineKeyboardMarkup(row_width=2)
            parts = sorted(db[anime_name].keys(), key=lambda x: int(x) if x.isdigit() else x)
            for part in parts:
                markup.add(InlineKeyboardButton(f"{part}-qism", callback_data=f"watch_{anime_name}_{part}"))
            markup.add(InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_list"))
            bot.edit_message_text(f"📺 *{anime_name}* — qismlarni tanlang:", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif data.startswith("watch_"):
        parts_data = data.replace("watch_", "").split("_", 1)
        anime_name = parts_data[0]
        part = parts_data[1]
        if anime_name in db and part in db[anime_name]:
            file_id = db[anime_name][part]
            bot.send_video(call.message.chat.id, file_id, caption=f"🎬 {anime_name} — {part}-qism")

    elif data == "back_to_list":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        show_anime_groups(call.message)

    elif data.startswith("del_") and user_id == ADMIN_ID:
        anime_name = data.replace("del_", "")
        if anime_name in db:
            del db[anime_name]
            save_db(db)
        bot.answer_callback_query(call.id, f"'{anime_name}' o'chirildi!")
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "Boshqaruv paneli:", reply_markup=get_admin_keyboard())

print("Bot ishga tushdi...")
bot.infinity_polling()
                    
