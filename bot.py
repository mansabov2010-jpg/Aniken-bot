import telebot
from telebot import types
import json
import os

# --- SOZLAMALAR ---
TOKEN = "YOUR_BOT_TOKEN_HERE"  # Bot tokeningizni yozing
ADMIN_ID = 123456789          # Telegram ID raqamingizni yozing

bot = telebot.TeleBot(TOKEN)
DB_FILE = "anime_database.json"

# --- MA'LUMOTLAR BAZASI ---
def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_db(db):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=4)

anime_db = load_db()
user_states = {}
temp_data = {}
user_last_messages = {}  # Foydalanuvchilarning eski xabarlarini saqlash uchun

# --- XABARLARNI O'CHIRISH FUNKSIYASI ---
def send_clean_message(chat_id, text, reply_markup=None, parse_mode=None):
    # Eski menyu/xabarni o'chirish
    if chat_id in user_last_messages:
        for msg_id in user_last_messages[chat_id]:
            try:
                bot.delete_message(chat_id, msg_id)
            except Exception:
                pass
        user_last_messages[chat_id] = []
    else:
        user_last_messages[chat_id] = []

    # Yangi xabarni yuborish va ID sini saqlab qo'yish
    msg = bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode)
    user_last_messages[chat_id].append(msg.message_id)
    return msg

def send_clean_photo(chat_id, photo, caption, reply_markup=None, parse_mode=None):
    if chat_id in user_last_messages:
        for msg_id in user_last_messages[chat_id]:
            try:
                bot.delete_message(chat_id, msg_id)
            except Exception:
                pass
        user_last_messages[chat_id] = []
    else:
        user_last_messages[chat_id] = []

    msg = bot.send_photo(chat_id, photo, caption=caption, reply_markup=reply_markup, parse_mode=parse_mode)
    user_last_messages[chat_id].append(msg.message_id)
    return msg

# --- TUGMALAR (KEYBOARDS) ---

def get_main_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🔍 Animelarni izlash", "📂 Mavjud animelar")
    markup.row("🔥 Tavsiya etiladigan animelar")
    if user_id == ADMIN_ID:
        markup.row("➕ Yangi anime qo'shish", "📊 Statistika")
    return markup

def get_search_inline_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📝 Nomi orqali", callback_data="search_by_name"),
        types.InlineKeyboardButton("🔢 Kodi orqali", callback_data="search_by_code")
    )
    return markup

def get_available_animes_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    if not anime_db:
        markup.add(types.InlineKeyboardButton("❌ Hozircha animelar yo'q", callback_data="none"))
    else:
        for key, anime in anime_db.items():
            parts_count = len(anime.get("parts", {}))
            btn_text = f"🎬 {anime['name']} ({parts_count}-qism)"
            markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"show_anime_{key}"))
    return markup

def get_recommended_animes_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    if not anime_db:
        markup.add(types.InlineKeyboardButton("❌ Hozircha animelar yo'q", callback_data="none"))
        return markup

    sorted_animes = sorted(anime_db.items(), key=lambda item: item[1].get("views", 0), reverse=True)
    
    for rank, (key, anime) in enumerate(sorted_animes, start=1):
        views = anime.get("views", 0)
        btn_text = f"{rank}. 🎬 {anime['name']} — 👁 {views} ta ko'rilgan"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"show_anime_{key}"))
    return markup

def get_anime_folder_keyboard(anime_key):
    markup = types.InlineKeyboardMarkup(row_width=5)
    anime = anime_db.get(anime_key, {})
    parts = anime.get("parts", {})

    sorted_part_numbers = sorted(parts.keys(), key=lambda x: int(x) if str(x).isdigit() else x)

    buttons = []
    for p in sorted_part_numbers:
        buttons.append(types.InlineKeyboardButton(text=str(p), callback_data=f"get_part_{anime_key}_{p}"))
    
    if buttons:
        markup.add(*buttons)

    markup.add(types.InlineKeyboardButton("⬅️ Ortga", callback_data="back_to_available"))
    return markup

# --- AMALLAR HANDLERLARI ---

@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    user_states.pop(user_id, None)
    temp_data.pop(user_id, None)
    
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass
        
    text = "👋 Xush kelibsiz! Kerakli bo'limni tanlang:"
    send_clean_message(message.chat.id, text, reply_markup=get_main_keyboard(user_id))

@bot.message_handler(func=lambda msg: msg.text == "🔍 Animelarni izlash")
def search_menu(message):
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass
    send_clean_message(
        message.chat.id, 
        "🔍 Animeni qanday usulda qidirmoqchisiz?", 
        reply_markup=get_search_inline_keyboard()
    )

@bot.message_handler(func=lambda msg: msg.text == "📂 Mavjud animelar")
def available_menu(message):
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass
    send_clean_message(
        message.chat.id, 
        "📂 Mavjud barcha anime jildlari:", 
        reply_markup=get_available_animes_keyboard()
    )

@bot.message_handler(func=lambda msg: msg.text == "🔥 Tavsiya etiladigan animelar")
def recommended_menu(message):
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass
    send_clean_message(
        message.chat.id, 
        "🔥 Eng ko'p izlangan va ko'rilgan animelar:", 
        reply_markup=get_recommended_animes_keyboard()
    )

@bot.message_handler(func=lambda msg: msg.text == "📊 Statistika" and msg.from_user.id == ADMIN_ID)
def stats_cmd(message):
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass
    total_animes = len(anime_db)
    total_parts = sum(len(a.get('parts', {})) for a in anime_db.values())
    total_views = sum(a.get('views', 0) for a in anime_db.values())
    
    text = (
        f"📊 <b>Bot Statistikasi:</b>\n\n"
        f"🎬 Jami anime jildlari: <b>{total_animes} ta</b>\n"
        f"🎞 Jami joylangan qismlar: <b>{total_parts} ta</b>\n"
        f"👁 Jami ko'rishlar soni: <b>{total_views} marta</b>"
    )
    send_clean_message(message.chat.id, text, parse_mode="HTML")

# --- ADMIN: YANGI ANIME QO'SHISH ---

@bot.message_handler(func=lambda msg: msg.text == "➕ Yangi anime qo'shish" and msg.from_user.id == ADMIN_ID)
def add_anime_start(message):
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass
    user_id = message.from_user.id
    user_states[user_id] = "ADD_NAME"
    temp_data[user_id] = {}
    send_clean_message(message.chat.id, "📝 Yangi anime nomini kiriting:")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == "ADD_NAME")
def process_name(message):
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass
    user_id = message.from_user.id
    temp_data[user_id]["name"] = message.text.strip()
    user_states[user_id] = "ADD_CODE"
    send_clean_message(message.chat.id, "🔢 Ushbu anime uchun yashirin nom yoki kod kiritng (masalan: 101 yoki deathnote):")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == "ADD_CODE")
def process_code(message):
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass
    user_id = message.from_user.id
    temp_data[user_id]["code"] = message.text.strip().lower()
    user_states[user_id] = "ADD_INFO"
    send_clean_message(message.chat.id, "📖 Anime haqida qisqacha ma'lumot kiriting (o'tkazib yuborish uchun /skip yuboring):")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == "ADD_INFO")
def process_info(message):
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass
    user_id = message.from_user.id
    info_text = message.text.strip() if message.text != "/skip" else "Ma'lumot mavjud emas"
    temp_data[user_id]["info"] = info_text
    user_states[user_id] = "ADD_PHOTO"
    send_clean_message(message.chat.id, "🖼 Anime muqova rasmini yuboring (o'tkazib yuborish uchun /skip yuboring):")

@bot.message_handler(content_types=['photo', 'text'], func=lambda msg: user_states.get(msg.from_user.id) == "ADD_PHOTO")
def process_photo(message):
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass
    user_id = message.from_user.id
    if message.content_type == 'photo':
        temp_data[user_id]["photo"] = message.photo[-1].file_id
    else:
        temp_data[user_id]["photo"] = None

    key = f"anime_{len(anime_db) + 1}"
    temp_data[user_id]["key"] = key
    
    anime_db[key] = {
        "name": temp_data[user_id]["name"],
        "code": temp_data[user_id]["code"],
        "info": temp_data[user_id]["info"],
        "photo": temp_data[user_id]["photo"],
        "views": 0,
        "parts": {}
    }
    save_db(anime_db)
    
    user_states[user_id] = "ADD_VIDEO"
    send_clean_message(message.chat.id, "✅ Jild yaratildi! Endi 1-qism uchun **video faylini** yuboring:")

@bot.message_handler(content_types=['video'], func=lambda msg: user_states.get(msg.from_user.id) == "ADD_VIDEO")
def process_video(message):
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass
    user_id = message.from_user.id
    temp_data[user_id]["last_video_id"] = message.video.file_id
    user_states[user_id] = "ADD_PART_NUM"
    send_clean_message(message.chat.id, "🔢 Ushbu video nechanchi qism? Raqamini kiriting (masalan: 1):")

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == "ADD_PART_NUM")
def process_part_num(message):
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass
    user_id = message.from_user.id
    part_num = message.text.strip()
    
    if not part_num.isdigit():
        send_clean_message(message.chat.id, "⚠️ Iltimos, faqat musbat raqam kiriting (masalan: 1, 2, 3):")
        return

    key = temp_data[user_id]["key"]
    video_id = temp_data[user_id]["last_video_id"]
    
    anime_db[key]["parts"][part_num] = video_id
    save_db(anime_db)
    
    user_states.pop(user_id, None)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("➕ Yana qism qo'shish", callback_data=f"add_more_{key}"),
        types.InlineKeyboardButton("✅ Tamomlash", callback_data="finish_add")
    )
    send_clean_message(message.chat.id, f"✅ {part_num}-qism saqlandi! Yana qism qo'shasizmi?", reply_markup=markup)

# --- QIDIRUV PROCESS HANDLERLARI ---

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == "SEARCH_NAME_WAIT")
def search_by_name_process(message):
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass
    query = message.text.strip().lower()
    user_states.pop(message.from_user.id, None)
    
    results = [k for k, v in anime_db.items() if query in v["name"].lower()]
    show_search_results(message.chat.id, results)

@bot.message_handler(func=lambda msg: user_states.get(msg.from_user.id) == "SEARCH_CODE_WAIT")
def search_by_code_process(message):
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass
    query = message.text.strip().lower()
    user_states.pop(message.from_user.id, None)
    
    results = [k for k, v in anime_db.items() if query == str(v.get("code", "")).lower()]
    show_search_results(message.chat.id, results)

def show_search_results(chat_id, results):
    if not results:
        send_clean_message(chat_id, "❌ Hech qanday anime topilmadi.")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for key in results:
        anime = anime_db[key]
        markup.add(types.InlineKeyboardButton(f"🎬 {anime['name']}", callback_data=f"show_anime_{key}"))
    
    send_clean_message(chat_id, "🔎 Topilgan animelar:", reply_markup=markup)

# --- CALLBACK QUERY HANDLER (TUGMALAR BOSILGANDA) ---

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    data = call.data

    if data == "search_by_name":
        user_states[user_id] = "SEARCH_NAME_WAIT"
        send_clean_message(call.message.chat.id, "📝 Izlamoqchi bo'lgan anime nomini yozing:")
        bot.answer_callback_query(call.id)

    elif data == "search_by_code":
        user_states[user_id] = "SEARCH_CODE_WAIT"
        send_clean_message(call.message.chat.id, "🔢 Anime kodini (yoki yashirin nomini) yozing:")
        bot.answer_callback_query(call.id)

    elif data.startswith("show_anime_"):
        anime_key = data.replace("show_anime_", "")
        if anime_key in anime_db:
            anime = anime_db[anime_key]
            caption = (
                f"🎬 <b>{anime['name']}</b>\n\n"
                f"📖 <b>Ma'lumot:</b> {anime.get('info', 'Mavjud emas')}\n"
                f"📌 <b>Kodi:</b> {anime.get('code', 'Yo\'q')}\n"
                f"🎞 <b>Mavjud qismlar soni:</b> {len(anime.get('parts', {}))} ta"
            )
            markup = get_anime_folder_keyboard(anime_key)

            if anime.get("photo"):
                send_clean_photo(call.message.chat.id, anime["photo"], caption=caption, parse_mode="HTML", reply_markup=markup)
            else:
                send_clean_message(call.message.chat.id, caption, parse_mode="HTML", reply_markup=markup)
        bot.answer_callback_query(call.id)

    elif data.startswith("get_part_"):
        _, _, anime_key, part_num = data.split("_")
        if anime_key in anime_db and part_num in anime_db[anime_key]["parts"]:
            anime = anime_db[anime_key]
            video_id = anime["parts"][part_num]
            
            anime_db[anime_key]["views"] = anime_db[anime_key].get("views", 0) + 1
            save_db(anime_db)

            caption = f"🎬 <b>{anime['name']}</b> - {part_num}-qism"
            # Video o'chirilmaydi, foydalanuvchida qoladi
            bot.send_video(call.message.chat.id, video_id, caption=caption, parse_mode="HTML")
            bot.answer_callback_query(call.id, text=f"{part_num}-qism yuborildi!")

    elif data.startswith("add_more_"):
        key = data.replace("add_more_", "")
        temp_data[user_id] = {"key": key}
        user_states[user_id] = "ADD_VIDEO"
        send_clean_message(call.message.chat.id, "📹 Navbatdagi qism video faylini yuboring:")
        bot.answer_callback_query(call.id)

    elif data == "finish_add":
        send_clean_message(call.message.chat.id, "🎉 Barcha qismlar muvaffaqiyatli saqlandi!", reply_markup=get_main_keyboard(user_id))
        bot.answer_callback_query(call.id)

    elif data == "back_to_available":
        send_clean_message(call.message.chat.id, "📂 Mavjud barcha anime jildlari:", reply_markup=get_available_animes_keyboard())
        bot.answer_callback_query(call.id)

# --- BOTNI ISHGA TUSHIRISH ---
if __name__ == "__main__":
    print("Bot muvaffaqiyatli ishga tushdi...")
    bot.infinity_polling()
