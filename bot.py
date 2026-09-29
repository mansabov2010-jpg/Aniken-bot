import json
import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, BotCommand

TOKEN = "8845458932:AAHDQoXJN_LVVaqDw1iuoI1B2h-l9J0v170"
ADMIN_ID = 7986354170

bot = telebot.TeleBot(TOKEN)
DB_FILE = "anime_db.json"
CONFIG_FILE = "config.json"

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

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_config(data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

db = load_db()
config = load_config()

user_state = {}
user_data = {}
user_last_bot_msg = {}

def set_bot_commands():
    try:
        bot.set_my_commands([
            BotCommand("start", "Botni ishga tushirish / Asosiy menyu")
        ])
    except Exception:
        pass

set_bot_commands()

def is_subscribed(user_id):
    channel = config.get("channel")
    if not channel:
        return True
    try:
        chat_member = bot.get_chat_member(channel, user_id)
        if chat_member.status in ['member', 'administrator', 'creator']:
            return True
    except Exception:
        pass
    return False

def get_sub_markup():
    channel = config.get("channel")
    markup = InlineKeyboardMarkup()
    if channel:
        url = f"https://t.me/{channel.replace('@', '')}"
        markup.add(InlineKeyboardButton("📢 Kanalga obuna bo'lish", url=url))
        markup.add(InlineKeyboardButton("✅ Obunani tekshirish", callback_data="check_sub"))
    return markup

def delete_last_msg(chat_id):
    if chat_id in user_last_bot_msg:
        try:
            bot.delete_message(chat_id, user_last_bot_msg[chat_id])
        except Exception:
            pass

def send_persistent(chat_id, text, reply_markup=None):
    delete_last_msg(chat_id)
    msg = bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode="Markdown")
    user_last_bot_msg[chat_id] = msg.message_id

def get_main_menu(user_id):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    if user_id == ADMIN_ID:
        markup.add(KeyboardButton("➕ Yangi anime bo'limi"), KeyboardButton("🔄 Mavjud animeni almashtirish"))
        markup.add(KeyboardButton("🔍 Nomi orqali qidirish"), KeyboardButton("🔢 Kod orqali qidirish"))
        markup.add(KeyboardButton("📁 Jildlar bo'yicha ko'rish"), KeyboardButton("📢 Majburiy kanalni sozlash"))
    else:
        markup.add(KeyboardButton("🔍 Nomi orqali qidirish"), KeyboardButton("🔢 Kod orqali qidirish"))
        markup.add(KeyboardButton("📁 Jildlar bo'yicha ko'rish"))
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    if not is_subscribed(user_id):
        bot.send_message(
            message.chat.id,
            "⚠️ Botdan foydalanish uchun quyidagi kanalimizga obuna bo'lishingiz kerak:",
            reply_markup=get_sub_markup()
        )
        return

    if user_id == ADMIN_ID:
        send_persistent(message.chat.id, "🎛 **Admin boshqaruv paneli:**", reply_markup=get_main_menu(user_id))
    else:
        welcome_text = (
            "✨ *AniKen dunyosiga xush kelibsiz!*\n\n"
            "🎬 Bu yerda siz eng sara anime va animatsion filmlarni yuqori sifatda topishingiz mumkin.\n"
            "Kerakli bo'limni tanlash uchun pastdagi tugmalardan foydalaning:"
        )
        send_persistent(message.chat.id, welcome_text, reply_markup=get_main_menu(user_id))

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def check_subscription(call):
    if is_subscribed(call.from_user.id):
        bot.answer_callback_query(call.id, "Rahmat, obuna tasdiqlandi! ✅")
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        send_welcome(call.message)
    else:
        bot.answer_callback_query(call.id, "Siz hali kanalga obuna bo'lmadingiz! ❌", show_alert=True)

@bot.message_handler(func=lambda message: not is_subscribed(message.from_user.id))
def block_unsubscribed(message):
    bot.send_message(
        message.chat.id,
        "⚠️ Botdan foydalanish uchun avval kanalga obuna bo'ling!",
        reply_markup=get_sub_markup()
    )

@bot.message_handler(func=lambda message: message.text == "📢 Majburiy kanalni sozlash" and message.from_user.id == ADMIN_ID)
def set_channel_prompt(message):
    user_state[message.from_user.id] = "waiting_for_channel"
    send_persistent(message.chat.id, "📢 Kerakli kanal username'sini yuboring (masalan: `@kanal_nomi`):")

@bot.message_handler(func=lambda message: message.text == "📁 Jildlar bo'yicha ko'rish")
def show_folders(message):
    db = load_db()
    if not db:
        send_persistent(message.chat.id, "📭 Hozircha bazada animelar mavjud emas.")
        return
    
    folders = set()
    for anime in db.values():
        folders.add(anime.get("folder", "Boshqa"))
    
    markup = InlineKeyboardMarkup()
    for folder in sorted(folders):
        markup.add(InlineKeyboardButton(f"📁 {folder}", callback_data=f"folder_{folder}"))
    
    send_persistent(message.chat.id, "📂 **Mavjud jildlar ro'yxati:**", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("folder_"))
def show_folder_contents(call):
    folder_name = call.data.replace("folder_", "", 1)
    db = load_db()
    
    markup = InlineKeyboardMarkup()
    items = []
    for code, anime in db.items():
        if anime.get("folder", "Boshqa") == folder_name:
            items.append((int(code) if code.isdigit() else code, code, anime))
    
    # Tartib raqami bo'yicha saralash
    try:
        items.sort(key=lambda x: int(x[1]))
    except Exception:
        pass

    for _, code, anime in items:
        # Endi tugmada faqat qism raqami yoki qisqacha ko'rsatiladi
        btn_text = f"{anime.get('part', code)}-qism"
        markup.add(InlineKeyboardButton(btn_text, callback_data=f"anime_{code}"))
    
    markup.add(InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_folders"))
    
    try:
        bot.edit_message_text(f"📁 **{folder_name}** jildidagi animelar:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    except Exception:
        pass

@bot.callback_query_handler(func=lambda call: call.data == "back_to_folders")
def back_to_folders_handler(call):
    db = load_db()
    folders = set()
    for anime in db.values():
        folders.add(anime.get("folder", "Boshqa"))
    
    markup = InlineKeyboardMarkup()
    for folder in sorted(folders):
        markup.add(InlineKeyboardButton(f"📁 {folder}", callback_data=f"folder_{folder}"))
    
    try:
        bot.edit_message_text("📂 **Mavjud jildlar ro'yxati:**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
    except Exception:
        pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("anime_"))
def show_anime_detail(call):
    code = call.data.replace("anime_", "", 1)
    db = load_db()
    anime = db.get(code)
    if not anime:
        bot.answer_callback_query(call.id, "Anime topilmadi!", show_alert=True)
        return
    
    text = f"🎬 **Nomi:** {anime['name']}\n🔢 **Kodi:** {code}\n📁 **Jild:** {anime.get('folder', 'Boshqa')}"
    if anime.get('video'):
        try:
            bot.send_video(call.message.chat.id, anime['video'], caption=text, parse_mode="Markdown")
            return
        except Exception:
            pass
    bot.send_message(call.message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "➕ Yangi anime bo'limi" and message.from_user.id == ADMIN_ID)
def add_anime_start(message):
    user_state[message.from_user.id] = "add_name"
    send_persistent(message.chat.id, "✍️ Anime nomini yuboring:")

@bot.message_handler(func=lambda message: message.text == "🔄 Mavjud animeni almashtirish" and message.from_user.id == ADMIN_ID)
def change_anime_start(message):
    user_state[message.from_user.id] = "change_code"
    send_persistent(message.chat.id, "🔢 Almashtirmoqchi bo'lgan anime kodini kiriting:")

@bot.message_handler(func=lambda message: message.text == "🔢 Kod orqali qidirish")
def search_by_code_prompt(message):
    user_state[message.from_user.id] = "search_code"
    send_persistent(message.chat.id, "🔢 Qidirilayotgan anime kodini yuboring:")

@bot.message_handler(func=lambda message: message.text == "🔍 Nomi orqali qidirish")
def search_by_name_prompt(message):
    user_state[message.from_user.id] = "search_name"
    send_persistent(message.chat.id, "🔍 Anime nomining bir qismini yuboring:")

@bot.message_handler(func=lambda message: message.from_user.id in user_state)
def handle_states(message):
    user_id = message.from_user.id
    state = user_state.get(user_id)
    db = load_db()

    if state == "waiting_for_channel":
        config["channel"] = message.text.strip()
        save_config(config)
        user_state.pop(user_id, None)
        send_persistent(message.chat.id, f"✅ Majburiy kanal muvaffaqiyatli o'rnatildi: {config['channel']}", reply_markup=get_main_menu(user_id))

    elif state == "add_name":
        user_data[user_id] = {"name": message.text, "keywords": message.text.lower().split()}
        user_state[user_id] = "add_folder"
        send_persistent(message.chat.id, "📁 Ushbu anime qaysi jildga tegishli bo'lsin? (Masalan: Death note):")

    elif state == "add_folder":
        user_data[user_id]["folder"] = message.text.strip()
        user_state[user_id] = "add_part"
        send_persistent(message.chat.id, "🔢 Bu nechanchi qism? (Masalan: 1, 2 yoki 3):")

    elif state == "add_part":
        user_data[user_id]["part"] = message.text.strip()
        user_state[user_id] = "add_code"
        send_persistent(message.chat.id, "🔢 Anime uchun unikal kod raqamini kiriting:")

    elif state == "add_code":
        code = message.text.strip()
        user_data[user_id]["code"] = code
        user_state[user_id] = "add_video"
        send_persistent(message.chat.id, "📹 Endi anime videosini (fayl yoki video tarzida) yuboring:")

    elif state == "add_video":
        video_id = None
        if message.video:
            video_id = message.video.file_id
        elif message.document:
            video_id = message.document.file_id
        
        if not video_id:
            send_persistent(message.chat.id, "❌ Iltimos, video yoki video fayl yuboring!")
            return

        data = user_data[user_id]
        code = data["code"]
        db[code] = {
            "name": data["name"],
            "keywords": data["keywords"],
            "folder": data["folder"],
            "part": data["part"],
            "code": code,
            "video": video_id
        }
        save_db(db)
        user_state.pop(user_id, None)
        user_data.pop(user_id, None)
        send_persistent(message.chat.id, f"✅ Anime muvaffaqiyatli qo'shildi! (Kod: {code})", reply_markup=get_main_menu(user_id))

    elif state == "change_code":
        code = message.text.strip()
        if code not in db:
            send_persistent(message.chat.id, "❌ Bunday kodli anime topilmadi. Qaytadan kiriting:")
            return
        user_data[user_id] = {"change_code": code}
        user_state[user_id] = "change_video"
        send_persistent(message.chat.id, f"📹 '{db[code]['name']}' uchun yangi videoni yuboring:")

    elif state == "change_video":
        video_id = None
        if message.video:
            video_id = message.video.file_id
        elif message.document:
            video_id = message.document.file_id
        
        if not video_id:
            send_persistent(message.chat.id, "❌ Iltimos, video yuboring!")
            return

        code = user_data[user_id]["change_code"]
        db[code]["video"] = video_id
        save_db(db)
        user_state.pop(user_id, None)
        user_data.pop(user_id, None)
        send_persistent(message.chat.id, f"✅ {code}-kodli anime videosi muvaffaqiyatli almashtirildi!", reply_markup=get_main_menu(user_id))

    elif state == "search_code":
        code = message.text.strip()
        user_state.pop(user_id, None)
        anime = db.get(code)
        if not anime:
            send_persistent(message.chat.id, "❌ Bunday kodli anime topilmadi.", reply_markup=get_main_menu(user_id))
            return
        text = f"🎬 **Nomi:** {anime['name']}\n🔢 **Kodi:** {code}\n📁 **Jild:** {anime.get('folder', 'Boshqa')}"
        if anime.get('video'):
            try:
                bot.send_video(message.chat.id, anime['video'], caption=text, parse_mode="Markdown")
                return
            except Exception:
                pass
        send_persistent(message.chat.id, text, reply_markup=get_main_menu(user_id))

    elif state == "search_name":
        query = message.text.strip().lower()
        user_state.pop(user_id, None)
        found = []
        for code, anime in db.items():
            if any(query in kw for kw in anime.get("keywords", [])) or query in anime["name"].lower():
                found.append((code, anime))
        
        if not found:
            send_persistent(message.chat.id, "❌ Bunday nomdagi anime topilmadi.", reply_markup=get_main_menu(user_id))
            return
        
        text = "🔍 **Topilgan animelar:**\n\n"
        for code, anime in found:
            text += f"• {anime['name']} (Kod: {code})\n"
        send_persistent(message.chat.id, text, reply_markup=get_main_menu(user_id))

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    send_persistent(message.chat.id, "Iltimos, menyudagi tugmalardan foydalaning:", reply_markup=get_main_menu(message.from_user.id))

print("Bot ishga tushdi...")
bot.infinity_polling()
                      
