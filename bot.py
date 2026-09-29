import json
import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

TOKEN = "8845458932:AAHDQoXJN_LVVaqDw5WlB6yQf8Xj4Y-L5Qc"
ADMIN_ID = 7986354170

bot = telebot.TeleBot(TOKEN)
DB_FILE = "anime_db.json"
CONFIG_FILE = "config.json"

# Ma'lumotlar bazasini yuklash
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

# Foydalanuvchilar bazasini yuklash (Statistika va xabar tarqatish uchun)
def load_users():
    if os.path.exists("users.json"):
        try:
            with open("users.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_users(users):
    with open("users.json", "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

db = load_db()

# Admin uchun asosiy menyu tugmalari
def get_admin_keyboard():
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("➕ Anime qo'shish", callback_data="add_anime"),
        InlineKeyboardButton("📋 Animelar ro'yxati", callback_data="list_anime")
    )
    markup.row(
        InlineKeyboardButton("📊 Statistika", callback_data="stats"),
        InlineKeyboardButton("📢 Xabar tarqatish", callback_data="broadcast")
    )
    return markup

# Foydalanuvchi uchun doimiy pastki menyu (Reply keyboard)
def get_user_reply_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("🎬 Animelar ro'yxati"), KeyboardButton("ℹ️ Bot haqida"))
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    
    # Foydalanuvchini bazaga qo'shib borish
    users = load_users()
    if user_id not in users:
        users.append(user_id)
        save_users(users)
        
    if user_id == ADMIN_ID:
        bot.send_message(
            message.chat.id, 
            "Assalomu alaykum, Hurmatli Admin! Bot boshqaruv paneliga xush kelibsiz:", 
            reply_markup=get_admin_keyboard()
        )
    else:
        bot.send_message(
            message.chat.id,
            "👋 Assalomu alaykum! Botimizga xush kelibsiz.\n\nKerakli anime va qismlarni topish uchun pastdagi tugmalardan foydalaning:",
            reply_markup=get_user_reply_keyboard()
        )
        # Barcha animelarni foydalanuvchiga inline tugma qilib chiqaramiz
        show_user_anime_list(message.chat.id)

def show_user_anime_list(chat_id):
    if not db:
        bot.send_message(chat_id, "Hozircha animelar mavjud emas. Tez kunda qo'shiladi!")
        return
        
    markup = InlineKeyboardMarkup(row_width=1)
    for anime_name in db.keys():
        markup.add(InlineKeyboardButton(f"🎬 {anime_name}", callback_data=f"user_anime_{anime_name}"))
    bot.send_message(chat_id, "📺 Mavjud animelar ro'yxati:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "🎬 Animelar ro'yxati")
def user_list_handler(message):
    show_user_anime_list(message.chat.id)

@bot.message_handler(func=lambda message: message.text == "ℹ️ Bot haqida")
def about_bot(message):
    bot.send_message(message.chat.id, "🤖 Bu bot orqali sevimli animelaringizni qismma-qism topib tomosha qilishingiz mumkin.")

# Callback query'larni boshqarish (Admin va Foydalanuvchi tugmalari)
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    data = call.data
    
    if data == "add_anime" and user_id == ADMIN_ID:
        msg = bot.send_message(call.message.chat.id, "Anime nomini kiriting:")
        bot.register_next_step_handler(msg, process_anime_name)
        
    elif data == "list_anime" and user_id == ADMIN_ID:
        if not db:
            bot.answer_callback_query(call.id, "Hozircha animelar yo'q.")
            return
        markup = InlineKeyboardMarkup(row_width=1)
        for anime in db.keys():
            markup.add(InlineKeyboardButton(f"🗑 O'chirish: {anime}", callback_data=f"del_anime_{anime}"))
        markup.add(InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_home"))
        bot.edit_message_text("O'chirmoqchi bo'lgan animeni tanlang:", call.message.chat.id, call.message.message_id, reply_markup=markup)
        
    elif data == "stats" and user_id == ADMIN_ID:
        users = load_users()
        total_animes = len(db)
        text = f"📊 **Bot statistikasi:**\n\n👥 Foydalanuvchilar soni: {len(users)} ta\n🎬 Animelar soni: {total_animes} ta"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_home"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif data == "broadcast" and user_id == ADMIN_ID:
        msg = bot.send_message(call.message.chat.id, "Barcha foydalanuvchilarga yubormoqchi bo'lgan xabaringizni kiriting:")
        bot.register_next_step_handler(msg, process_broadcast)

    elif data == "admin_home" and user_id == ADMIN_ID:
        bot.edit_message_text("Admin boshqaruv paneli:", call.message.chat.id, call.message.message_id, reply_markup=get_admin_keyboard())

    elif data.startswith("del_anime_") and user_id == ADMIN_ID:
        anime_name = data.replace("del_anime_", "")
        if anime_name in db:
            del db[anime_name]
            save_db(db)
        bot.answer_callback_query(call.id, f"'{anime_name'}' o'chirildi!")
        bot.edit_message_text("Admin boshqaruv paneli:", call.message.chat.id, call.message.message_id, reply_markup=get_admin_keyboard())

    elif data.startswith("user_anime_"):
        anime_name = data.replace("user_anime_", "")
        if anime_name in db:
            markup = InlineKeyboardMarkup(row_width=2)
            # Qismlarni tartibli chiqarish (1-qism, 2-qism...)
            parts = sorted(db[anime_name].keys(), key=lambda x: int(x) if x.isdigit() else x)
            for part in parts:
                markup.add(InlineKeyboardButton(f"{part}-qism", callback_data=f"watch_{anime_name}_{part}"))
            markup.add(InlineKeyboardButton("⬅️ Orqaga", callback_data="user_back"))
            bot.edit_message_text(f"📺 **{anime_name}** - Qismlarni tanlang:", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif data.startswith("watch_"):
        parts_data = data.replace("watch_", "").split("_", 1)
        anime_name = parts_data[0]
        part = parts_data[1]
        if anime_name in db and part in db[anime_name]:
            file_id = db[anime_name][part]
            bot.send_video(call.message.chat.id, file_id, caption=f"🎬 {anime_name} - {part}-qism")

    elif data == "user_back":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        show_user_anime_list(call.message.chat.id)

# Admin uchun: Anime qo'shish bosqichlari
def process_anime_name(message):
    anime_name = message.text.strip()
    msg = bot.send_message(message.chat.id, f"'{anime_name}' uchun qism raqamini kiriting (masalan: 1):")
    bot.register_next_step_handler(msg, process_part_number, anime_name)

def process_part_number(message, anime_name):
    part = message.text.strip()
    msg = bot.send_message(message.chat.id, f"'{anime_name}' ning {part}-qismining **VIDEOSINI** yuboring:")
    bot.register_next_step_handler(msg, process_video_file, anime_name, part)

def process_video_file(message, anime_name, part):
    if message.video:
        file_id = message.video.file_id
        if anime_name not in db:
            db[anime_name] = {}
        db[anime_name][part] = file_id
        save_db(db)
        bot.send_message(message.chat.id, f"✅ Muvaffaqiyatli saqlandi!\n\nAnime: {anime_name}\nQism: {part}", reply_markup=get_admin_keyboard())
    else:
        bot.send_message(message.chat.id, "⚠️ Iltimos, faqat video fayl yuboring! Qaytadan urinib ko'ring.")

# Admin uchun: Xabar tarqatish (Broadcast)
def process_broadcast(message):
    text = message.text
    users = load_users()
    success = 0
    for uid in users:
        try:
            bot.send_message(uid, text)
            success += 1
        except Exception:
            pass
    bot.send_message(message.chat.id, f"📢 Xabar {success} ta foydalanuvchiga muvaffaqiyatli yuborildi!", reply_markup=get_admin_keyboard())

print("Bot ishga tushdi...")
bot.infinity_polling()
    
