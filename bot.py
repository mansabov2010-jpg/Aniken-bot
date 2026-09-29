import json
import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

TOKEN = "8845458932:AAHb3PfSBb9AclEhAuRJgj6h0wGewFSxyUM"
ADMIN_ID = 7986354170

bot = telebot.TeleBot(TOKEN)
DB_FILE = "anime_db.json"
USERS_FILE = "users.json"
SCHEDULE_FILE = "schedule.json"
SETTINGS_FILE = "settings.json"

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
settings = load_data(SETTINGS_FILE, {"force_sub": None})

def check_subscription(user_id):
    if user_id == ADMIN_ID:
        return True
    channel = settings.get("force_sub")
    if not channel:
        return True
    try:
        member = bot.get_chat_member(channel, user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
    except Exception:
        pass
    return False

def get_admin_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("➕ Yeni anime bo'limi"), KeyboardButton("🔄 Mavjud animeni almashtirish"))
    markup.add(KeyboardButton("📢 Majburiy kanal"), KeyboardButton("📅 Jadvalni yangilash"))
    markup.add(KeyboardButton("📋 Animelar ro'yxati"), KeyboardButton("📊 Statistika"))
    markup.add(KeyboardButton("🚀 Start (Asosiy menyu)"))
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
        
    force_channel = settings.get("force_sub")
    if force_channel and not check_subscription(user_id):
        markup = InlineKeyboardMarkup()
        clean_channel = force_channel.replace('@', '')
        if "t.me/" in force_channel:
            markup.add(InlineKeyboardButton("📢 Kanalga obuna bo'lish", url=force_channel))
        else:
            markup.add(InlineKeyboardButton("📢 Kanalga obuna bo'lish", url=f"https://t.me/{clean_channel}"))
        markup.add(InlineKeyboardButton("✅ Obunani tekshirish", callback_data="check_sub"))
        bot.send_message(message.chat.id, f"⚠️ Botdan foydalanish uchun avval quyidagi kanalimizga obuna bo'ling:\n\n{force_channel}", reply_markup=markup)
        return

    if user_id == ADMIN_ID:
        bot.send_message(message.chat.id, "✨ *Admin boshqaruv paneli:*", parse_mode="Markdown", reply_markup=get_admin_keyboard())
    else:
        bot.send_message(message.chat.id, "✨ *AniKen dunyosiga xush kelibsiz!*\n\n🎬 Eng sara animelarni tomosha qiling:", parse_mode="Markdown", reply_markup=get_user_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def callback_sub(call):
    if check_subscription(call.from_user.id):
        bot.answer_callback_query(call.id, "Rahmat! Obuna tasdiqlandi ✅")
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        send_welcome(call.message)
    else:
        bot.answer_callback_query(call.id, "Siz hali kanalga obuna bo'lmadingiz! ❌", show_alert=True)

@bot.message_handler(func=lambda message: message.text in ["🎬 Animelar ro'yxati", "🚀 Start (Asosiy menyu)"])
def show_anime_groups(message):
    if not check_subscription(message.from_user.id):
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
    if not check_subscription(message.from_user.id):
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
    if not check_subscription(message.from_user.id):
        send_welcome(message)
        return
    bot.send_message(message.chat.id, f"📅 *Barcha uchun umumiy anime jadvallari:*\n\n{schedule_data}", parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "ℹ️ Bot haqida")
def about_bot(message):
    bot.send_message(message.chat.id, "🤖 Bu bot orqali sevimli animelaringizni qismlarga bo'lingan holda osongina ko'rishingiz mumkin.")

# --- ADMIN FUNKSIYALARI ---
@bot.message_handler(func=lambda message: message.text == "📢 Majburiy kanal" and message.from_user.id == ADMIN_ID)
def admin_force_sub_menu(message):
    current = settings.get("force_sub")
    text = f"📢 *Majburiy obuna sozlamasi*\n\nHozirgi kanal: `{current if current else 'O\'rnatilmagan (O\'chiq)'}`\n\nYangi kanal username yoki havolasini yuboring (masalan: `@KanalNomi` yoki `https://t.me/...`)\nAgar majburiy obunani o'chirmoqchi bo'lsangiz: `ochirish` deb yuboring."
    msg = bot.send_message(message.chat.id, text, parse_mode="Markdown")
    bot.register_next_step_handler(msg, save_force_sub_channel)

def save_force_sub_channel(message):
    global settings
    text = message.text.strip()
    if text.lower() == "ochirish":
        settings["force_sub"] = None
        save_data(SETTINGS_FILE, settings)
        bot.send_message(message.chat.id, "✅ Majburiy obuna muvaffaqiyatli o'chirildi!", reply_markup=get_admin_keyboard())
        return
    
    settings["force_sub"] = text
    save_data(SETTINGS_FILE, settings)
    bot.send_message(message.chat.id, f"✅ Majburiy kanal o'rnatildi: {text}\n\n*Eslatma:* Botni o'sha kanalga admin qilganingizga ishonch hosil qiling!", parse_mode="Markdown", reply_markup=get_admin_keyboard())

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
    current_channel = settings.get("force_sub")
    text = f"📊 *Statistika:*\n\n👥 Foydalanuvchilar: {len(users)} ta\n📁 Anime bo'limlari: {len(db)} ta\n📢 Majburiy kanal: `{current_channel if current_channel else 'O\'rnatilmagan'}`"
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=get_admin_keyboard())

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    data = call.data
    
    if data.startswith("group_"):
        anime_name = data.replace("group_", "")
        if anime_name in db:
            total_parts = len(db[anime_name])
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
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        show_anime_groups(call.message)

    elif data.startswith("del_") and user_id == ADMIN_ID:
        anime_name = data.replace("del_", "")
        if anime_name in db:
            del db[anime_name]
            save_data(DB_FILE, db)
        bot.answer_callback_query(call.id, f"'{anime_name}' o'chirildi!")
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        bot.send_message(call.message.chat.id, "Boshqaruv paneli:", reply_markup=get_admin_keyboard())

    elif data.startswith("rep_") and user_id == ADMIN_ID:
        anime_name = data.replace("rep_", "")
        msg = bot.send_message(call.message.chat.id, f"'{anime_name}' uchun yangi qism raqamini kiriting:")
        bot.register_next_step_handler(msg, step_part_num, anime_name)
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass

print("Bot ishga tushdi...")
bot.infinity_polling()
    
