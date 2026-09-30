import telebot
from telebot import types
import json
import os
import time

# --- SOZLAMALAR ---
# Token va ADMIN_ID ni muhit o'zgaruvchilaridan oladi, topilmasa standart qiymatni ishlatadi
TOKEN = os.getenv("BOT_TOKEN", "8248154561:AAFTHK0CPVJGB2zY5r5zT9-hbz70DPwcYW0")
ADMIN_ID = int(os.getenv("ADMIN_ID", 7986354170))

bot = telebot.TeleBot(TOKEN)
DB_FILE = "anime_database.json"

# --- MA'LUMOTLAR BAZASI ---
def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"animes": {}, "channels": [], "users": []}
    return {"animes": {}, "channels": [], "users": []}

def save_db(db):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=4)

db_data = load_db()
if "channels" not in db_data: db_data["channels"] = []
if "users" not in db_data: db_data["users"] = []
if "animes" not in db_data: db_data["animes"] = {}

user_states = {}
temp_data = {}
user_last_messages = {}

# --- XABARLARNI TOZALASH FUNKSIYALARI ---
def send_clean_message(chat_id, text, reply_markup=None, parse_mode=None):
    if chat_id in user_last_messages:
        for msg_id in user_last_messages[chat_id]:
            try:
                bot.delete_message(chat_id, msg_id)
            except Exception:
                pass
        user_last_messages[chat_id] = []
    else:
        user_last_messages[chat_id] = []

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

# --- MAJBURIY OBUNANI TEKSHIRISH ---
def check_sub(user_id):
    if user_id == ADMIN_ID:
        return True
    unsubscribed = []
    for ch in db_data.get("channels", []):
        try:
            member = bot.get_chat_member(ch, user_id)
            if member.status in ['left', 'kicked']:
                unsubscribed.append(ch)
        except Exception:
            pass
    return unsubscribed

def get_sub_keyboard(unsubscribed_channels):
    markup = types.InlineKeyboardMarkup(row_width=1)
    for ch in unsubscribed_channels:
        url = f"https://t.me/{ch.replace('@', '')}"
        markup.add(types.InlineKeyboardButton(f"📢 Kanalga a'zo bo'lish", url=url))
    markup.add(types.InlineKeyboardButton("✅ Obunani tekshirish", callback_data="check_subscription"))
    return markup

# --- TUGMALAR (KEYBOARDS) ---
def get_main_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🔍 Animelarni izlash", "📂 Mavjud animelar")
    markup.row("🔥 Tavsiya etiladigan animelar")
    if user_id == ADMIN_ID:
        markup.row("➕ Yangi anime qo'shish", "📢 Kanallarni boshqarish")
        markup.row("📊 Statistika")
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
    animes = db_data.get("animes", {})
    if not animes:
        markup.add(types.InlineKeyboardButton("❌ Hozircha animelar yo'q", callback_data="none"))
    else:
        for key, anime in animes.items():
            parts_count = len(anime.get("parts", {}))
            btn_text = f"🎬 {anime['name']} ({parts_count}-qism)"
            markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"show_anime_{key}"))
    return markup

def get_recommended_animes_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    animes = db_data.get("animes", {})
    if not animes:
        markup.add(types.InlineKeyboardButton("❌ Hozircha animelar yo'q", callback_data="none"))
        return markup

    sorted_animes = sorted(animes.items(), key=lambda item: item[1].get("views", 0), reverse=True)
    
    for rank, (key, anime) in enumerate(sorted_animes, start=1):
        views = anime.get("views", 0)
        btn_text = f"{rank}. 🎬 {anime['name']} — 👁 {views} ko'rilgan"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"show_anime_{key}"))
    return markup

def get_anime_folder_keyboard(anime_key):
    markup = types.InlineKeyboardMarkup(row_width=5)
    anime = db_data["animes"].get(anime_key, {})
    parts = anime.get("parts", {})

    sorted_part_numbers = sorted(parts.keys(), key=lambda x: int(x) if str(x).isdigit() else x)

    buttons = []
    for p in sorted_part_numbers:
        buttons.append(types.InlineKeyboardButton(text=str(p), callback_data=f"get_part_{anime_key}_{p}"))
    
    if buttons:
        markup.add(*buttons)

    markup.add(types.InlineKeyboardButton("⬅ Ortga", callback_data="back_to_available"))
    return markup

# --- HANDLERLAR ---
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    if user_id not in db_data["users"]:
        db_data["users"].append(user_id)
        save_db(db_data)

    user_states.pop(user_id, None)
    temp_data.pop(user_id, None)
    
    try: bot.delete_message(message.chat.id, message.message_id)
    except: pass
        
    unsub = check_sub(user_id)
    if unsub is not True and unsub:
        text = "⚠️ Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:"
        send_clean_message(message.chat.id, text, reply_markup=get_sub_keyboard(unsub))
        return

    text = "👋 Xush kelibsiz! Kerakli bo'limni tanlang:"
    send_clean_message(message.chat.id, text, reply_markup=get_main_keyboard(user_id))

@bot.message_handler(func=lambda msg: True)
def main_messages(message):
    user_id = message.from_user.id
    try: bot.delete_message(message.chat.id, message.message_id)
    except: pass

    # Obunani tekshirish
    unsub = check_sub(user_id)
    if unsub is not True and unsub:
        text = "⚠️ Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:"
        send_clean_message(message.chat.id, text, reply_markup=get_sub_keyboard(unsub))
        return

    state = user_states.get(user_id)

    # --- ADMIN: KANAL QO'SHISH ---
    if state == "ADD_CHANNEL_WAIT" and user_id == ADMIN_ID:
        ch = message.text.strip()
        if not ch.startswith("@"): ch = "@" + ch
        if ch not in db_data["channels"]:
            db_data["channels"].append(ch)
            save_db(db_data)
            send_clean_message(message.chat.id, f"✅ {ch} kanali ro'yxatga qo'shildi!", reply_markup=get_main_keyboard(user_id))
        else:
            send_clean_message(message.chat.id, "⚠️️ Bu kanal allaqachon qo'shilgan.", reply_markup=get_main_keyboard(user_id))
        user_states.pop(user_id, None)
        return

    # --- QIDIRUV PROCESS ---
    if state == "SEARCH_NAME_WAIT":
        query = message.text.strip().lower()
        user_states.pop(user_id, None)
        results = [k for k, v in db_data["animes"].items() if query in v["name"].lower()]
        show_search_results(message.chat.id, results)
        return

    if state == "SEARCH_CODE_WAIT":
        query = message.text.strip().lower()
        user_states.pop(user_id, None)
        results = [k for k, v in db_data["animes"].items() if query == str(v.get("code", "")).lower()]
        show_search_results(message.chat.id, results)
        return

    # --- ADMIN: ANIME QO'SHISH PROCESS ---
    if state == "ADD_NAME" and user_id == ADMIN_ID:
        temp_data[user_id]["name"] = message.text.strip()
        user_states[user_id] = "ADD_CODE"
        send_clean_message(message.chat.id, "🔢 Anime uchun kod/yashirin nom kiriting:")
        return

    if state == "ADD_CODE" and user_id == ADMIN_ID:
        temp_data[user_id]["code"] = message.text.strip().lower()
        user_states[user_id] = "ADD_INFO"
        send_clean_message(message.chat.id, "📖 Anime haqida ma'lumot kiriting (o'tkazib yuborish uchun /skip):")
        return

    if state == "ADD_INFO" and user_id == ADMIN_ID:
        info_text = message.text.strip() if message.text != "/skip" else "Ma'lumot mavjud emas"
        temp_data[user_id]["info"] = info_text
        user_states[user_id] = "ADD_PHOTO"
        send_clean_message(message.chat.id, "🖼 Muqova rasmini yuboring (o'tkazib yuborish uchun /skip):")
        return

    if state == "ADD_PHOTO" and user_id == ADMIN_ID and message.text == "/skip":
        key = f"anime_{len(db_data['animes']) + 1}"
        temp_data[user_id]["key"] = key
        
        db_data["animes"][key] = {
            "name": temp_data[user_id]["name"],
            "code": temp_data[user_id]["code"],
            "info": temp_data[user_id]["info"],
            "photo": None,
            "views": 0,
            "parts": {}
        }
        save_db(db_data)
        user_states[user_id] = "ADD_VIDEO"
        send_clean_message(message.chat.id, "✅ Jild yaratildi! Endi 1-qism uchun **video faylini** yuboring:")
        return

    if state == "ADD_PART_NUM" and user_id == ADMIN_ID:
        part_num = message.text.strip()
        if not part_num.isdigit():
            send_clean_message(message.chat.id, "⚠️ Faqat musbat raqam kiriting:")
            return
        key = temp_data[user_id]["key"]
        video_id = temp_data[user_id]["last_video_id"]
        db_data["animes"][key]["parts"][part_num] = video_id
        save_db(db_data)
        user_states.pop(user_id, None)

        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("➕ Yana qism qo'shish", callback_data=f"add_more_{key}"),
            types.InlineKeyboardButton("✅ Tamomlash", callback_data="finish_add")
        )
        send_clean_message(message.chat.id, f"✅ {part_num}-qism saqlandi! Yana qism qo'shasizmi?", reply_markup=markup)
        return

    # --- MENYU TUGMALARI ---
    if message.text == "🔍 Animelarni izlash":
        send_clean_message(message.chat.id, "🔍 Izlash usulini tanlang:", reply_markup=get_search_inline_keyboard())
    elif message.text == "📂 Mavjud animelar":
        send_clean_message(message.chat.id, "📂 Mavjud anime jildlari:", reply_markup=get_available_animes_keyboard())
    elif message.text == "🔥 Tavsiya etiladigan animelar":
        send_clean_message(message.chat.id, "🔥 Eng ko'p ko'rilgan animelar:", reply_markup=get_recommended_animes_keyboard())
    elif message.text == "➕ Yangi anime qo'shish" and user_id == ADMIN_ID:
        user_states[user_id] = "ADD_NAME"
        temp_data[user_id] = {}
        send_clean_message(message.chat.id, "📝 Yangi anime nomini kiriting:")
    elif message.text == "📢 Kanallarni boshqarish" and user_id == ADMIN_ID:
        channels_text = "\n".join(db_data["channels"]) if db_data["channels"] else "Hozircha kanallar yo'q"
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("➕ Kanal qo'shish", callback_data="add_channel"))
        if db_data["channels"]:
            markup.add(types.InlineKeyboardButton("🗑 Kanallarni tozalash", callback_data="clear_channels"))
        send_clean_message(message.chat.id, f"📢 **Ulangan kanallar:**\n\n{channels_text}", reply_markup=markup, parse_mode="Markdown")
    elif message.text == "📊 Statistika" and user_id == ADMIN_ID:
        total_animes = len(db_data["animes"])
        total_parts = sum(len(a.get('parts', {})) for a in db_data["animes"].values())
        total_views = sum(a.get('views', 0) for a in db_data["animes"].values())
        total_users = len(db_data.get("users", []))
        text = (
            f"📊 <b>Bot Statistikasi:</b>\n\n"
            f"👥 Jami foydalanuvchilar: <b>{total_users} ta</b>\n"
            f"🎬 Jami anime jildlari: <b>{total_animes} ta</b>\n"
            f"🎞 Jami qismlar: <b>{total_parts} ta</b>\n"
            f"👁 Jami ko'rishlar: <b>{total_views} marta</b>"
        )
        send_clean_message(message.chat.id, text, parse_mode="HTML")

# --- MEDIALAR UCHUN HANDLER ---
@bot.message_handler(content_types=['photo', 'video'])
def handle_media(message):
    user_id = message.from_user.id
    try: bot.delete_message(message.chat.id, message.message_id)
    except: pass

    state = user_states.get(user_id)

    if state == "ADD_PHOTO" and user_id == ADMIN_ID:
        temp_data[user_id]["photo"] = message.photo[-1].file_id if message.content_type == 'photo' else None
        key = f"anime_{len(db_data['animes']) + 1}"
        temp_data[user_id]["key"] = key
        
        db_data["animes"][key] = {
            "name": temp_data[user_id]["name"],
            "code": temp_data[user_id]["code"],
            "info": temp_data[user_id]["info"],
            "photo": temp_data[user_id]["photo"],
            "views": 0,
            "parts": {}
        }
        save_db(db_data)
        user_states[user_id] = "ADD_VIDEO"
        send_clean_message(message.chat.id, "✅ Jild yaratildi! Endi 1-qism uchun **video faylini** yuboring:")
        return

    if state == "ADD_VIDEO" and user_id == ADMIN_ID and message.content_type == 'video':
        temp_data[user_id]["last_video_id"] = message.video.file_id
        user_states[user_id] = "ADD_PART_NUM"
        send_clean_message(message.chat.id, "🔢 Ushbu video nechanchi qism? Raqamini kiriting:")
        return

def show_search_results(chat_id, results):
    if not results:
        send_clean_message(chat_id, "❌ Hech qanday anime topilmadi.")
        return
    markup = types.InlineKeyboardMarkup(row_width=1)
    for key in results:
        anime = db_data["animes"][key]
        markup.add(types.InlineKeyboardButton(f"🎬 {anime['name']}", callback_data=f"show_anime_{key}"))
    send_clean_message(chat_id, "🔎 Topilgan animelar:", reply_markup=markup)

# --- CALLBACK QUERY HANDLER ---
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    data = call.data

    if data == "check_subscription":
        unsub = check_sub(user_id)
        if unsub is not True and unsub:
            bot.answer_callback_query(call.id, "❌ Hali hamma kanallarga a'zo bo'lmadingiz!", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "✅ Obuna tasdiqlandi!")
            send_clean_message(call.message.chat.id, "👋 Xush kelibsiz! Kerakli bo'limni tanlang:", reply_markup=get_main_keyboard(user_id))

    elif data == "add_channel" and user_id == ADMIN_ID:
        user_states[user_id] = "ADD_CHANNEL_WAIT"
        send_clean_message(call.message.chat.id, "📢 Kanal username-ini yuboring (Masalan: @kanal_username):")
        bot.answer_callback_query(call.id)

    elif data == "clear_channels" and user_id == ADMIN_ID:
        db_data["channels"] = []
        save_db(db_data)
        send_clean_message(call.message.chat.id, "✅ Barcha majburiy kanallar o'chirib tashlandi!")
        bot.answer_callback_query(call.id)

    elif data == "search_by_name":
        user_states[user_id] = "SEARCH_NAME_WAIT"
        send_clean_message(call.message.chat.id, "📝 Anime nomini yozing:")
        bot.answer_callback_query(call.id)

    elif data == "search_by_code":
        user_states[user_id] = "SEARCH_CODE_WAIT"
        send_clean_message(call.message.chat.id, "🔢 Anime kodini yozing:")
        bot.answer_callback_query(call.id)

    elif data.startswith("show_anime_"):
        anime_key = data.replace("show_anime_", "")
        if anime_key in db_data["animes"]:
            anime = db_data["animes"][anime_key]
            caption = (
                f"🎬 <b>{anime['name']}</b>\n\n"
                f"📖 <b>Ma'lumot:</b> {anime.get('info', 'Mavjud emas')}\n"
                f"📌 <b>Kodi:</b> {anime.get('code', 'Yo\'q')}\n"
                f"🎞 <b>Mavjud qismlar:</b> {len(anime.get('parts', {}))} ta"
            )
            markup = get_anime_folder_keyboard(anime_key)
            if anime.get("photo"):
                send_clean_photo(call.message.chat.id, anime["photo"], caption=caption, parse_mode="HTML", reply_markup=markup)
            else:
                send_clean_message(call.message.chat.id, caption, parse_mode="HTML", reply_markup=markup)
        bot.answer_callback_query(call.id)

    elif data.startswith("get_part_"):
        _, _, anime_key, part_num = data.split("_")
        if anime_key in db_data["animes"] and part_num in db_data["animes"][anime_key]["parts"]:
            anime = db_data["animes"][anime_key]
            video_id = anime["parts"][part_num]
            db_data["animes"][anime_key]["views"] = db_data["animes"][anime_key].get("views", 0) + 1
            save_db(db_data)
            caption = f"🎬 <b>{anime['name']}</b> - {part_num}-qism"
            bot.send_video(call.message.chat.id, video_id, caption=caption, parse_mode="HTML")
            bot.answer_callback_query(call.id, text=f"{part_num}-qism yuborildi!")

    elif data.startswith("add_more_") and user_id == ADMIN_ID:
        key = data.replace("add_more_", "")
        temp_data[user_id] = {"key": key}
        user_states[user_id] = "ADD_VIDEO"
        send_clean_message(call.message.chat.id, "📹 Navbatdagi qism video faylini yuboring:")
        bot.answer_callback_query(call.id)

    elif data == "finish_add" and user_id == ADMIN_ID:
        send_clean_message(call.message.chat.id, "🎉 Barcha qismlar saqlandi!", reply_markup=get_main_keyboard(user_id))
        bot.answer_callback_query(call.id)

    elif data == "back_to_available":
        send_clean_message(call.message.chat.id, "📂 Mavjud anime jildlari:", reply_markup=get_available_animes_keyboard())
        bot.answer_callback_query(call.id)

# --- BOTNI ISHGA TUSHIRISH ---
if __name__ == "__main__":
    try:
        bot.remove_webhook()
        time.sleep(1)
    except Exception:
        pass
    print("Bot muvaffaqiyatli ishga tushdi...")
    bot.infinity_polling(skip_pending=True)
                
