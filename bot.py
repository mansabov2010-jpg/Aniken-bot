import json
import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

TOKEN = 8845458932:AAHb3PfSBb9AclEhAuRJgj6h0wGewFSxyUM

ADMIN_ID = 7986354170
FORCE_SUB_CHANNEL = "@AnikenChannel"

bot = telebot.TeleBot(TOKEN)
DB_FILE = "anime_db.json"
USERS_FILE = "users.json"
SCHEDULE_FILE = "schedule.json"

def load_data(file, default):
    if os.path.exists(file):
        try:
            with open(file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def save_data(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

db = load_data(DB_FILE, {})
users = load_data(USERS_FILE, [])
schedule_data = load_data(SCHEDULE_FILE, "Hozircha umumiy anime jadvallari kiritilmagan.")

def check_subscription(user_id):
    if not FORCE_SUB_CHANNEL:
        return True
    try:
        member = bot.get_chat_member(FORCE_SUB_CHANNEL, user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
    except Exception:
        pass
    return False

def get_admin_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("➕ Yeni anime bo'limi"), KeyboardButton("🔄 Mavjud animeni almashtirish"))
    markup.add(KeyboardButton("📅 Jadvalni yangilash"), KeyboardButton("📋 Animelar ro'yxati"))
    markup.add(KeyboardButton("📊 Statistika"), KeyboardButton("🚀 Start (Asosiy menyu)"))
    return markup

def get_user_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("🎬 Animelar ro'yxati"), KeyboardButton("🔍 Qidirish"))
    markup.add(KeyboardButton("📅 Anime jadvallari"), KeyboardButton("ℹ️ Bot haqida"))
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    if user_id not in users:
        users.append(user_id)
        save_data(USERS_FILE, users)
        
    if FORCE_SUB_CHANNEL and not check_subscription(user_id):
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📢 Kanalga obuna bo'lish", url=f"https://t.me/{FORCE_SUB_CHANNEL.replace('@', '')}"))
        markup.add(InlineKeyboardButton("✅ Obunani tekshirish", callback_data="check_sub"))
        bot.send_message(message.chat.id, f"⚠️ Botdan foydalanish uchun avval quyidagi kanalimizga obuna bo'ling:\n\n{FORCE_SUB_CHANNEL}", reply_markup=markup)
        return

    if user_id == ADMIN_ID:
        bot.send_message(message.chat.id, "✨ *Admin boshqaruv paneli:*", parse_mode="Markdown", reply_markup=get_admin_keyboard())
    else:
        bot.send_message(message.chat.id, "✨ *AniKen dunyosiga xush kelibsiz!*\n\n🎬 Eng sara animelarni tomosha qiling:", parse_mode="Markdown", reply_markup=get_user_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def callback_sub(call):
    if check_subscription(call.from_user.id):
        bot.answer_callback_query(call.id, "Rahmat! Obuna tasdiqlandi ✅")
        bot.delete_message(call.message.chat.id, call.message.message_id)
        send_welcome(call.message)
    else:
        bot.answer_callback_query(call.id, "Siz hali kanalga obuna bo'lmadingiz! ❌", show_alert=True)

@bot.message_handler(func=lambda message: message.text in ["🎬 Animelar ro'yxati", "🚀 Start (Asosiy menyu)"])
def show_anime_groups(message):
    if FORCE_SUB_CHANNEL and not check_subscription(message.from_user.id):
        send_welcome(message)
        return
    if not db:
        bot.send_message(message.chat.id, "Hozircha animelar mavjud emas.")
        return
    markup = InlineKeyboardMarkup(row_width=1)
    for anime_name in db.keys():
        markup.add(InlineKeyboardButton(f"📁 {anime_name}", callback_data=f"group_{anime_name}"))
    bot.send_message(message.chat.id, "📺 *Mavjud anime bo'limlari:*", parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "🔍 Qidirish")
def search_anime_prompt(message):
    if FORCE_SUB_CHANNEL and not check_subscription(message.from_user.id):
        send_welcome(message)
        return
    msg = bot.send_message(message.chat.id, "Qidirmoqchi bo'lgan anime nomini yozib yuboring (masalan: *Death note*):", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_search)

def process_search(message):
    query = message.text.strip().lower()
    found = [name for name in db.keys() if query in name.lower()]
    
    if not found:
        bot.send_message(message.chat.id, "❌ Bunday nomdagi anime topilmadi.", reply_markup=get_user_keyboard())
        return
        
    markup = InlineKeyboardMarkup(row_width=1)
    for anime_name in found:
        markup.add(InlineKeyboardButton(f"📁 {anime_name}", callback_data=f"group_{anime_name}"))
    bot.send_message(message.chat.id, "🔍 *Topilgan animelar:*", parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "📅 Anime jadvallari")
def show_schedule(message):
    if FORCE_SUB_CHANNEL and not check_subscription(message.from_user.id):
        send_welcome(message)
        return
    bot.send_message(message.chat.id, f"📅 *Barcha uchun umumiy anime jadvallari:*\n\n{schedule_data}", parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "ℹ️ Bot haqida")
def about_bot(message):
    bot.send_message(message.chat.id, "🤖 Bu bot orqali sevimli animelaringizni qismlarga bo'lingan holda osongina ko'rishingiz mumkin.")

# --- ADMIN FUNKSIYALARI ---
@bot.message_handler(func=lambda message: message.text == "➕ Yeni anime bo'limi" and message.from_user.id == ADMIN_ID)
def admin_add_anime(message):
    msg = bot.send_message(message.chat.id, "Yangi anime bo'limi nomini kiriting:")
    bot.register_next_step_handler(msg, step_anime_name)

def step_anime_name(message):
    anime_name = message.text.strip()
    msg = bot.send_message(message.chat.id, f"'{anime_name}' uchun qism raqamini kiriting (masalan: 1):")
    bot.register_next_step_handler(msg, step_part_num, anime_name)

def step_part_num(message, anime_name):
    part = message.text.strip()
    msg = bot.send_message(message.chat.id, f"'{anime_name}' ning {part}-qismining VIDEOSINI yuboring:")
    bot.register_next_step_handler(msg, step_save_video, anime_name, part)

def step_save_video(message, anime_name, part):
    if message.video:
        if anime_name not in db:
            db[anime_name] = {}
        db[anime_name][part] = message.video.file_id
        save_data(DB_FILE, db)
        bot.send_message(message.chat.id, f"✅ Muvaffaqiyatli saqlandi!", reply_markup=get_admin_keyboard())
    else:
        bot.send_message(message.chat.id, "⚠️ Iltimos, video yuboring!", reply_markup=get_admin_keyboard())

@bot.message_handler(func=lambda message: message.text == "🔄 Mavjud animeni almashtirish" and message.from_user.id == ADMIN_ID)
def admin_replace_anime(message):
    if not db:
        bot.send_message(message.chat.id, "Hozircha almashtirish uchun animelar yo'q.", reply_markup=get_admin_keyboard())
        return
    markup = InlineKeyboardMarkup(row_width=1)
    for anime in db.keys():
        markup.add(InlineKeyboardButton(f"✏️ Almashtirish: {anime}", callback_data=f"rep_{anime}"))
    bot.send_message(message.chat.id, "Almoqchi bo'lgan anime bo'limini tanlang:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "📅 Jadvalni yangilash" and message.from_user.id == ADMIN_ID)
def admin_update_schedule(message):
    msg = bot.send_message(message.chat.id, "Yangi anime jadvallari matnini yuboring:")
    bot.register_next_step_handler(msg, step_save_schedule)

def step_save_schedule(message):
    global schedule_data
    schedule_data = message.text
    save_data(SCHEDULE_FILE, schedule_data)
    bot.send_message(message.chat.id, "✅ Jadval muvaffaqiyatli yangilandi!", reply_markup=get_admin_keyboard())

@bot.message_handler(func=lambda message: message.text == "📋 Animelar ro'yxati" and message.from_user.id == ADMIN_ID)
def admin_list(message):
    if not db:
        bot.send_message(message.chat.id, "Animelar yo'q.", reply_markup=get_admin_keyboard())
        return
    markup = InlineKeyboardMarkup(row_width=1)
    for anime in db.keys():
        markup.add(InlineKeyboardButton(f"🗑 O'chirish: {anime}", callback_data=f"del_{anime}"))
    bot.send_message(message.chat.id, "O'chirmoqchi bo'lgan animeni tanlang:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "📊 Statistika" and message.from_user.id == ADMIN_ID)
def admin_stats(message):
    text = f"📊 *Statistika:*\n\n👥 Foydalanuvchilar: {len(users)} ta\n📁 Anime bo'limlari: {len(db)} ta"
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=get_admin_keyboard())

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    data = call.data
    
    if data.startswith("group_"):
        anime_name = data.replace("group_", "")
        if anime_name in db:
            total_parts = len(db[anime_name])
            # Siz xohlagan tartibda qismlar tugmalari 5 tadan qator bo'lib chiqadi
            markup = InlineKeyboardMarkup(row_width=5)
            parts = sorted(db[anime_name].keys(), key=lambda x: int(x) if x.isdigit() else x)
            
            buttons = [InlineKeyboardButton(f"{part}", callback_data=f"watch_{anime_name}_{part}") for part in parts]
            markup.add(*buttons)
            markup.add(InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_list"))
            
            bot.edit_message_text(
                f"🎬 *{anime_name}* — {total_parts} ta qism\n\nKerakli qismni tanlang:", 
                call.message.chat.id, 
                call.message.message_id, 
                parse_mode="Markdown", 
                reply_markup=markup
            )

    elif data.startswith("watch_"):
        parts_data = data.replace("watch_", "").split("_", 1)
        anime_name = parts_data[0]
        part = parts_data[1]
        if anime_name in db and part in db[anime_name]:
            bot.send_video(call.message.chat.id, db[anime_name][part], caption=f"🎬 {anime_name} — {part}-qism")

    elif data == "back_to_list":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        show_anime_groups(call.message)

    elif data.startswith("del_") and user_id == ADMIN_ID:
        anime_name = data.replace("del_", "")
        if anime_name in db:
            del db[anime_name]
            save_data(DB_FILE, db)
        bot.answer_callback_query(call.id, f"'{anime_name}' o'chirildi!")
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "Boshqaruv paneli:", reply_markup=get_admin_keyboard())

    elif data.startswith("rep_") and user_id == ADMIN_ID:
        anime_name = data.replace("rep_", "")
        msg = bot.send_message(call.message.chat.id, f"'{anime_name}' uchun yangi qism raqamini kiriting:")
        bot.register_next_step_handler(msg, step_part_num, anime_name)
        bot.delete_message(call.message.chat.id, call.message.message_id)

print("Bot ishga tushdi...")
bot.infinity_polling()
        
