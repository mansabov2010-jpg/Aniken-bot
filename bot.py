import os
import sqlite3
import urllib.parse
from flask import Flask
import threading
import telebot
from telebot import types

# --- KONFIGURATSIYA VA BAZA SOZLAMALARI ---
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "123456789"))
DATABASE_URL = os.environ.get("DATABASE_URL")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot ishlayapti!", 200

DB_FILE = "anime_bot.db"

def get_db_connection():
    if DATABASE_URL:
        import psycopg2
        return psycopg2.connect(DATABASE_URL, sslmode='require')
    else:
        return sqlite3.connect(DB_FILE)

def execute_query(query, params=(), fetchone=False, fetchall=False, commit=False):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # PostgreSQL va SQLite o'rtasidagi sintaksis moslashuvi
    if DATABASE_URL:
        query = query.replace('?', '%s')
        
    cursor.execute(query, params)
    
    result = None
    if fetchone:
        result = cursor.fetchone()
    elif fetchall:
        result = cursor.fetchall()
        
    if commit:
        conn.commit()
        
    cursor.close()
    conn.close()
    return result

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if DATABASE_URL:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY
            );
            CREATE TABLE IF NOT EXISTS channels (
                username TEXT PRIMARY KEY
            );
            CREATE TABLE IF NOT EXISTS animes (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                secret_name TEXT,
                code TEXT UNIQUE,
                info TEXT,
                photo TEXT,
                episodes_count TEXT,
                status TEXT,
                quality TEXT,
                genre TEXT,
                channel_name TEXT,
                views INT DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS parts (
                id SERIAL PRIMARY KEY,
                anime_id INT,
                part_num INT,
                video_id TEXT
            );
        ''')
    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY
            );
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS channels (
                username TEXT PRIMARY KEY
            );
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS animes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                secret_name TEXT,
                code TEXT UNIQUE,
                info TEXT,
                photo TEXT,
                episodes_count TEXT,
                status TEXT,
                quality TEXT,
                genre TEXT,
                channel_name TEXT,
                views INTEGER DEFAULT 0
            );
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS parts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                anime_id INTEGER,
                part_num INTEGER,
                video_id TEXT
            );
        ''')
    conn.commit()
    cursor.close()
    conn.close()

init_db()

# --- XOTIRA VA HOLATLAR ---
user_states = {}
temp_data = {}
bot_msg_history = {}

def add_bot_message_to_history(chat_id, message_id):
    if chat_id not in bot_msg_history:
        bot_msg_history[chat_id] = []
    bot_msg_history[chat_id].append(message_id)

def send_clean_message(chat_id, text, reply_markup=None, parse_mode="HTML", protect=False):
    msg = bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode, protect_content=protect)
    add_bot_message_to_history(chat_id, msg.message_id)
    return msg

def send_clean_photo(chat_id, photo, caption, reply_markup=None, parse_mode="HTML", protect=False):
    msg = bot.send_photo(chat_id, photo, caption=caption, reply_markup=reply_markup, parse_mode=parse_mode, protect_content=protect)
    add_bot_message_to_history(chat_id, msg.message_id)
    return msg

def check_sub(user_id):
    channels = execute_query("SELECT username FROM channels", fetchall=True) or []
    unsub = []
    for ch in channels:
        ch_name = ch[0]
        try:
            member = bot.get_chat_member(ch_name, user_id)
            if member.status in ['left', 'kicked']:
                unsub.append(ch_name)
        except Exception:
            unsub.append(ch_name)
    return True if not unsub else unsub

def get_sub_keyboard(unsub):
    markup = types.InlineKeyboardMarkup()
    for ch in unsub:
        url = f"https://t.me/{ch.replace('@', '')}"
        markup.add(types.InlineKeyboardButton(f"➕ Obuna bo'lish: {ch}", url=url))
    markup.add(types.InlineKeyboardButton("✅ Obunani tasdiqlash", callback_data="check_subscription"))
    return markup

def get_main_inline_menu(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔍 Anime izlash", callback_data="menu_search"),
        types.InlineKeyboardButton("📂 Mavjud animelar", callback_data="menu_available_page_1")
    )
    markup.add(
        types.InlineKeyboardButton("🔥 Ommabop animelar", callback_data="menu_recommended")
    )
    if user_id == ADMIN_ID:
        markup.add(
            types.InlineKeyboardButton("➕ Anime qo'shish", callback_data="admin_add_folder"),
            types.InlineKeyboardButton("🎬 Qism qo'shish", callback_data="admin_add_part")
        )
        markup.add(
            types.InlineKeyboardButton("🛠 Tahrirlash bo'limi", callback_data="admin_edit_menu"),
            types.InlineKeyboardButton("⚙️ Anime boshqaruvi", callback_data="admin_manage")
        )
        markup.add(
            types.InlineKeyboardButton("📢 Kanallar", callback_data="admin_channels"),
            types.InlineKeyboardButton("📊 Bot statistikasi", callback_data="admin_stats")
        )
    return markup

def get_search_inline_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📝 Nomi bo'yicha izlash", callback_data="search_by_name"),
        types.InlineKeyboardButton("🕵️ Yashirin nomi bo'yicha", callback_data="search_by_secret"),
        types.InlineKeyboardButton("🔢 Kodi bo'yicha izlash", callback_data="search_by_code"),
        types.InlineKeyboardButton("⬅️ Ortga", callback_data="back_to_main")
    )
    return markup

def get_available_animes_keyboard(page=1, action_type="show"):
    animes = execute_query("SELECT id, name FROM animes ORDER BY id DESC", fetchall=True) or []
    per_page = 10
    total_pages = (len(animes) + per_page - 1) // per_page if animes else 1
    page = max(1, min(page, total_pages))
    
    start = (page - 1) * per_page
    end = start + per_page
    current_animes = animes[start:end]
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for a_id, a_name in current_animes:
        if action_type == "show":
            cb = f"show_anime_{a_id}"
        elif action_type == "add_part":
            cb = f"select_anime_for_part_{a_id}"
        elif action_type == "edit_folder":
            cb = f"select_edit_folder_{a_id}"
        elif action_type == "admin_opt":
            cb = f"admin_anime_opt_{a_id}"
        else:
            cb = f"show_anime_{a_id}"
            
        markup.add(types.InlineKeyboardButton(f"🎬 {a_name}", callback_data=cb))
        
    nav_buttons = []
    if page > 1:
        nav_buttons.append(types.InlineKeyboardButton("⬅️ Orqaga", callback_data=f"menu_available_page_{page-1}"))
    if page < total_pages:
        nav_buttons.append(types.InlineKeyboardButton("Keyingisi ➡️", callback_data=f"menu_available_page_{page+1}"))
        
    if nav_buttons:
        markup.row(*nav_buttons)
        
    markup.add(types.InlineKeyboardButton("⬅️ Asosiy menyu", callback_data="back_to_main"))
    return markup

def get_recommended_animes_keyboard():
    animes = execute_query("SELECT id, name, views FROM animes ORDER BY views DESC LIMIT 10", fetchall=True) or []
    markup = types.InlineKeyboardMarkup(row_width=1)
    for a_id, a_name, views in animes:
        markup.add(types.InlineKeyboardButton(f"🔥 {a_name} ({views} ko'rish)", callback_data=f"show_anime_{a_id}"))
    markup.add(types.InlineKeyboardButton("⬅️ Asosiy menyu", callback_data="back_to_main"))
    return markup

def get_anime_folder_keyboard(anime_id, page=1):
    parts = execute_query("SELECT part_num FROM parts WHERE anime_id = ? ORDER BY part_num ASC", (anime_id,), fetchall=True) or []
    per_page = 10
    total_parts = len(parts)
    total_pages = (total_parts + per_page - 1) // per_page if total_parts else 1
    page = max(1, min(page, total_pages))
    
    start = (page - 1) * per_page
    end = start + per_page
    current_parts = parts[start:end]
    
    markup = types.InlineKeyboardMarkup(row_width=5)
    row = []
    for p in current_parts:
        p_num = p[0]
        row.append(types.InlineKeyboardButton(f"{p_num}-qism", callback_data=f"get_part_{anime_id}_{p_num}"))
        if len(row) == 5:
            markup.row(*row)
            row = []
    if row:
        markup.row(*row)
        
    nav_buttons = []
    if page > 1:
        nav_buttons.append(types.InlineKeyboardButton("⬅️ Oldingi", callback_data=f"page_{anime_id}_{page-1}"))
    if page < total_pages:
        nav_buttons.append(types.InlineKeyboardButton("Keyingi ➡️", callback_data=f"page_{anime_id}_{page+1}"))
    if nav_buttons:
        markup.row(*nav_buttons)
        
    markup.add(types.InlineKeyboardButton("⬅️ Asosiy menyuga qaytish", callback_data="back_to_main"))
    return markup

def format_anime_text(anime_data):
    # anime_data: name, secret_name, info, views, code, episodes_count, status, quality, genre, channel_name
    name, secret_name, info, views, code, ep_count, status, quality, genre, channel = anime_data
    return (
        f"🎬 <b>{name}</b>\n\n"
        f"🕵️ <b>Yashirin nomi:</b> <i>{secret_name or 'Mavjud emas'}</i>\n"
        f"🔢 <b>Kodi:</b> <code>{code}</code>\n"
        f"🎞 <b>Qismlar soni:</b> {ep_count or 'Noma\'lum'}\n"
        f"📌 <b>Status:</b> {status or 'Noma\'lum'}\n"
        f"💿 <b>Sifati:</b> {quality or '720p/1080p'}\n"
        f"🎭 <b>Janri:</b> {genre or 'Noma\'lum'}\n"
        f"📢 <b>Kanal:</b> {channel or 'Mavjud emas'}\n"
        f"👁 <b>Ko'rishlar soni:</b> {views}\n\n"
        f"📝 <b>Ma'lumot:</b> {info or 'Mavjud emas'}\n\n"
        f"⬇️ <b>Tomosha qilish uchun pastdagi qismlardan birini tanlang:</b>"
    )

def show_search_results(chat_id, results):
    if not results:
        send_clean_message(chat_id, "❌ Afsuski, hech qanday anime topilmadi.", reply_markup=get_main_inline_menu(chat_id))
        return
    markup = types.InlineKeyboardMarkup(row_width=1)
    for a_id, a_name in results:
        markup.add(types.InlineKeyboardButton(f"🎬 {a_name}", callback_data=f"show_anime_{a_id}"))
    markup.add(types.InlineKeyboardButton("⬅️ Asosiy menyu", callback_data="back_to_main"))
    send_clean_message(chat_id, "🔍 <b>Qidiruv natijalari:</b>", reply_markup=markup)

# --- INLINE QUERY HANDLER ---
@bot.inline_handler(func=lambda query: True)
def inline_query_handler(query):
    text = query.query.strip().lower()
    if not text:
        return
    results = execute_query(
        "SELECT id, name, secret_name, info, photo, code FROM animes WHERE LOWER(name) LIKE ? OR LOWER(secret_name) LIKE ? OR LOWER(code) = ?",
        (f"%{text}%", f"%{text}%", text),
        fetchall=True
    ) or []
    
    inline_results = []
    bot_info = bot.get_me()
    for item in results:
        a_id, name, secret_name, info, photo, code = item
        deeplink_url = f"https://t.me/{bot_info.username}?start=anime_{a_id}"
        desc = info[:100] if info else "Ma'lumot yo'q"
        
        reply_markup = types.InlineKeyboardMarkup()
        reply_markup.add(types.InlineKeyboardButton("🎬 Animeni tomosha qilish", url=deeplink_url))
        
        caption = (
            f"🎬 <b>{name}</b>\n"
            f"🕵️ Yashirin nom: <i>{secret_name}</i>\n\n"
            f"📝 {desc}\n\n"
            f"🔑 Kodi: <code>{code}</code>\n"
            f"⬇️ Animeni to'liq ko'rish uchun pastdagi tugmani bosing:"
        )
        
        if photo and photo.startswith("http"):
            res_item = types.InlineQueryResultPhoto(
                id=str(a_id),
                photo_url=photo,
                thumbnail_url=photo,
                title=name,
                description=f"Kodi: {code} | {secret_name}",
                caption=caption,
                parse_mode="HTML",
                reply_markup=reply_markup
            )
        else:
            res_item = types.InlineQueryResultArticle(
                id=str(a_id),
                title=name,
                description=f"Kodi: {code} | {secret_name}",
                input_message_content=types.InputTextMessageContent(caption, parse_mode="HTML"),
                reply_markup=reply_markup
            )
        inline_results.append(res_item)
        
    bot.answer_inline_query(query.id, inline_results[:20])

# --- /START VA ASOSIY BUYRUQLAR ---
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    execute_query("INSERT INTO users (user_id) VALUES (?) ON CONFLICT(user_id) DO NOTHING", (user_id,), commit=True)
    
    # Deeplink tekshiruvi (start=anime_ID)
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("anime_"):
        try:
            anime_id = int(args[1].replace("anime_", ""))
            unsub = check_sub(user_id)
            if unsub is not True:
                send_clean_message(chat_id, "⚠️ Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:", reply_markup=get_sub_keyboard(unsub))
                return
            
            anime = execute_query(
                "SELECT name, secret_name, info, views, code, episodes_count, status, quality, genre, channel_name, photo FROM animes WHERE id = ?",
                (anime_id,), fetchone=True
            )
            if anime:
                execute_query("UPDATE animes SET views = views + 1 WHERE id = ?", (anime_id,), commit=True)
                photo = anime[10]
                text = format_anime_text(anime[:10])
                markup = get_anime_folder_keyboard(anime_id, page=1)
                
                if photo:
                    send_clean_photo(chat_id, photo, text, reply_markup=markup, protect=True)
                else:
                    send_clean_message(chat_id, text, reply_markup=markup, protect=True)
                return
        except Exception:
            pass

    unsub = check_sub(user_id)
    if unsub is not True:
        send_clean_message(chat_id, "⚠️ Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:", reply_markup=get_sub_keyboard(unsub))
        return

    text = "👋 <b>Xush kelibsiz! Kerakli bo'limni tanlang:</b>"
    send_clean_message(chat_id, text, reply_markup=get_main_inline_menu(user_id))

# --- GURUHIY QIDIRUV (MAJBURIY OBUNA INTEGRATSIYASI BILAN) ---
@bot.message_handler(func=lambda message: message.chat.id < 0)
def group_messages(message):
    if not message.text:
        return
    
    text = message.text.strip().lower()
    if text.startswith("/anime"):
        query = text.replace("/anime", "").strip()
    else:
        return

    if not query:
        bot.reply_to(message, "⚠️ Anime nomini yozing. Masalan: <code>/anime Naruto</code>", parse_mode="HTML")
        return

    # Guruhda izlayotgan foydalanuvchining obunasini tekshirish
    unsub = check_sub(message.from_user.id)
    if unsub is not True:
        bot_info = bot.get_me()
        start_url = f"https://t.me/{bot_info.username}?start=sub_check"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔑 Obunani tasdiqlash uchun botga o'ting", url=start_url))
        bot.reply_to(message, "⚠️ <b>Guruhda anime izlash uchun ham kanallarga obuna bo'lishingiz shart!</b>", reply_markup=markup, parse_mode="HTML")
        return

    animes = execute_query(
        "SELECT id, name, secret_name, info, photo, code, quality FROM animes WHERE LOWER(name) LIKE ? OR LOWER(secret_name) LIKE ? OR LOWER(code) = ?",
        (f"%{query}%", f"%{query}%", query),
        fetchall=True
    ) or []

    if not animes:
        bot.reply_to(message, "❌ Afsuski, bunday anime topilmadi.")
        return

    bot_info = bot.get_me()
    for anime_id, name, secret_name, info, photo, code, quality in animes:
        deeplink_url = f"https://t.me/{bot_info.username}?start=anime_{anime_id}"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🎬 Anime tomosha qilish", url=deeplink_url))
        
        desc = info[:150] if info else "Ma'lumot yo'q"
        caption = (
            f"🎬 <b>{name}</b>\n"
            f"🕵️ Yashirin nom: <i>{secret_name}</i>\n"
            f"💿 Sifati: <b>{quality or '720p/1080p'}</b>\n\n"
            f"📝 {desc}\n\n"
            f"🔑 Kodi: <code>{code}</code>\n"
            f"⬇️ Animeni to'liq ko'rish uchun pastdagi tugmani bosing:"
        )
        
        if photo:
            bot.send_photo(message.chat.id, photo, caption=caption, reply_markup=markup, parse_mode="HTML")
        else:
            bot.send_message(message.chat.id, caption, reply_markup=markup, parse_mode="HTML")
        break

# --- SHAXSIY CHATDAGI MULOQOT VA QADAMMA-QADAM PROCESSLAR ---
@bot.message_handler(func=lambda message: True)
def main_messages(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    text_val = message.text.strip() if message.text else ""
    text_lower = text_val.lower()

    if chat_id < 0:
        return

    unsub = check_sub(user_id)
    if unsub is not True and not user_states.get(user_id):
        send_clean_message(chat_id, "⚠️ Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:", reply_markup=get_sub_keyboard(unsub))
        return

    state = user_states.get(user_id)

    # 1. Kanal qo'shish
    if state == "ADD_CHANNEL_WAIT" and user_id == ADMIN_ID:
        ch = text_val if text_val.startswith("@") else "@" + text_val
        try:
            execute_query("INSERT INTO channels (username) VALUES (?)", (ch,), commit=True)
            send_clean_message(chat_id, f"✅ {ch} kanali muvaffaqiyatli qo'shildi!", reply_markup=get_main_inline_menu(user_id))
        except Exception:
            send_clean_message(chat_id, "⚠️ Bu kanal allaqachon mavjud.", reply_markup=get_main_inline_menu(user_id))
        user_states.pop(user_id, None)
        return

    # 2. Yangi anime yaratish - Bosqichlar
    if user_id == ADMIN_ID:
        if state == "ADD_NAME":
            temp_data[user_id] = {"name": text_val}
            user_states[user_id] = "ADD_SECRET_NAME"
            send_clean_message(chat_id, "🕵️️ Anime uchun yashirin nom (kalit so'z) kiriting:")
            return

        elif state == "ADD_SECRET_NAME":
            temp_data[user_id]["secret_name"] = text_val
            user_states[user_id] = "ADD_CODE"
            send_clean_message(chat_id, "🔢 Anime uchun maxsus raqamli kod kiriting (masalan: 12):")
            return

        elif state == "ADD_CODE":
            temp_data[user_id]["code"] = text_lower
            user_states[user_id] = "ADD_EPISODES"
            send_clean_message(chat_id, "🎞 Anime necha qismdan iborat? (Masalan: 12, 24 yoki Noma'lum):")
            return

        elif state == "ADD_EPISODES":
            temp_data[user_id]["episodes_count"] = text_val
            user_states[user_id] = "ADD_STATUS"
            send_clean_message(chat_id, "📌 Anime statusini kiriting (Masalan: Davom etmoqda / Tugallangan):")
            return

        elif state == "ADD_STATUS":
            temp_data[user_id]["status"] = text_val
            user_states[user_id] = "ADD_QUALITY"
            send_clean_message(chat_id, "💿 Video sifatini kiriting (Masalan: 720p / 1080p):")
            return

        elif state == "ADD_QUALITY":
            temp_data[user_id]["quality"] = text_val
            user_states[user_id] = "ADD_GENRE"
            send_clean_message(chat_id, "🎭 Anime janrini kiriting (Masalan: Jangari, Sarguzasht):")
            return

        elif state == "ADD_GENRE":
            temp_data[user_id]["genre"] = text_val
            user_states[user_id] = "ADD_CHANNEL_NAME"
            send_clean_message(chat_id, "📢 Kanal nomini kiriting (Masalan: @AnimeKanal):")
            return

        elif state == "ADD_CHANNEL_NAME":
            temp_data[user_id]["channel_name"] = text_val
            user_states[user_id] = "ADD_INFO"
            send_clean_message(chat_id, "📝 Anime haqida qisqacha ma'lumot kiriting (o'tkazib yuborish uchun /skip):")
            return

        elif state == "ADD_INFO":
            info_text = text_val if text_val != "/skip" else "Ma'lumot mavjud emas"
            temp_data[user_id]["info"] = info_text
            user_states[user_id] = "ADD_PHOTO"
            send_clean_message(chat_id, "🖼 Muqova rasmini yuboring (o'tkazib yuborish uchun /skip):")
            return

        elif state == "ADMIN_EDIT_FOLDER_NAME":
            temp_data[user_id]["edit_name"] = text_val
            user_states[user_id] = "ADMIN_EDIT_FOLDER_CODE"
            send_clean_message(chat_id, "🔢 Endi jild uchun yangi kodni kiriting:")
            return

        elif state == "ADMIN_EDIT_FOLDER_CODE":
            anime_id = temp_data[user_id]["anime_id"]
            new_name = temp_data[user_id]["edit_name"]
            new_code = text_lower
            new_photo = temp_data[user_id].get("edit_photo", "")
            
            execute_query(
                "UPDATE animes SET name = ?, code = ?, photo = ? WHERE id = ?",
                (new_name, new_code, new_photo, anime_id),
                commit=True
            )
            user_states.pop(user_id, None)
            temp_data.pop(user_id, None)
            send_clean_message(chat_id, "✅ Jild muvaffaqiyatli tahrirlandi!", reply_markup=get_main_inline_menu(user_id))
            return

        elif state == "ADMIN_EDIT_PART_SEARCH":
            res = execute_query(
                "SELECT id, name FROM animes WHERE LOWER(name) LIKE ? OR LOWER(code) = ?",
                (f"%{text_lower}%", text_lower),
                fetchone=True
            )
            if res:
                temp_data[user_id] = {"anime_id": res[0], "anime_name": res[1]}
                user_states[user_id] = "ADMIN_EDIT_PART_NUM"
                send_clean_message(chat_id, f"✅ Anime topildi: <b>{res[1]}</b>\n\n🔢 Nechanchi qismni tahrirlamoqchisiz? (Faqat raqam kiriting):")
            else:
                send_clean_message(chat_id, "❌ Bunday anime topilmadi. Qaytadan nomini yoki kodini yuboring:")
            return

        elif state == "ADMIN_EDIT_PART_NUM":
            if not text_val.isdigit():
                send_clean_message(chat_id, "⚠️ Iltimos, faqat raqam kiriting:")
                return
            temp_data[user_id]["part_num"] = int(text_val)
            user_states[user_id] = "ADMIN_EDIT_PART_VIDEO"
            send_clean_message(chat_id, "📹 Endi ushbu qism uchun yangi videoni yuboring:")
            return

    # 3. Qidiruv so'rovlari
    if state == "SEARCH_NAME_WAIT":
        user_states.pop(user_id, None)
        results = execute_query("SELECT id, name FROM animes WHERE LOWER(name) LIKE ?", (f"%{text_lower}%",), fetchall=True) or []
        show_search_results(chat_id, results)
        return

    if state == "SEARCH_SECRET_WAIT":
        user_states.pop(user_id, None)
        results = execute_query("SELECT id, name FROM animes WHERE LOWER(secret_name) LIKE ?", (f"%{text_lower}%",), fetchall=True) or []
        show_search_results(chat_id, results)
        return

    if state == "SEARCH_CODE_WAIT":
        user_states.pop(user_id, None)
        results = execute_query("SELECT id, name FROM animes WHERE LOWER(code) = ?", (text_lower,), fetchall=True) or []
        show_search_results(chat_id, results)
        return

    # 4. Kod orqali bevosita topish
    q = "SELECT name, secret_name, info, views, code, episodes_count, status, quality, genre, channel_name, photo, id FROM animes WHERE LOWER(code) = ?"
    anime = execute_query(q, (text_lower,), fetchone=True)
    if anime:
        anime_id = anime[11]
        photo = anime[10]
        execute_query("UPDATE animes SET views = views + 1 WHERE id = ?", (anime_id,), commit=True)
        text = format_anime_text(anime[:10])
        markup = get_anime_folder_keyboard(anime_id, page=1)
        if photo:
            send_clean_photo(chat_id, photo, text, reply_markup=markup, parse_mode="HTML", protect=True)
        else:
            send_clean_message(chat_id, text, reply_markup=markup, parse_mode="HTML", protect=True)
        return

    send_clean_message(chat_id, "🤖 Kerakli bo'limni tanlang:", reply_markup=get_main_inline_menu(user_id))

# --- MEDIA HANDLER (RASM VA VIDEO QABUL QILISH) ---
@bot.message_handler(content_types=['photo', 'video', 'document'])
def handle_media(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    if chat_id < 0:
        return

    state = user_states.get(user_id)

    # Rasm qabul qilish (Yangi anime yaratish)
    if state == "ADD_PHOTO" and user_id == ADMIN_ID:
        photo_id = message.photo[-1].file_id if message.content_type == "photo" else ""
        d = temp_data[user_id]
        
        if DATABASE_URL:
            q = """INSERT INTO animes (name, secret_name, code, info, photo, episodes_count, status, quality, genre, channel_name)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id"""
            anime_id = execute_query(q, (d["name"], d["secret_name"], d["code"], d["info"], photo_id, d["episodes_count"], d["status"], d["quality"], d["genre"], d["channel_name"]), fetchone=True, commit=True)[0]
        else:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("""INSERT INTO animes (name, secret_name, code, info, photo, episodes_count, status, quality, genre, channel_name)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                           (d["name"], d["secret_name"], d["code"], d["info"], photo_id, d["episodes_count"], d["status"], d["quality"], d["genre"], d["channel_name"]))
            anime_id = cursor.lastrowid
            conn.commit()
            conn.close()

        temp_data[user_id] = {"anime_id": anime_id}
        user_states[user_id] = "ADD_AUTO_VIDEO"
        send_clean_message(chat_id, "✅ **Yangi anime yaratildi!** Endi ushbu anime uchun **1-qism videosini** yuboring:")
        return

    # Video qabul qilish (Avto qism qo'shish)
    if state == "ADD_AUTO_VIDEO" and user_id == ADMIN_ID:
        if message.content_type != "video":
            send_clean_message(chat_id, "⚠️ Iltimos, anime uchun to'g'ri video fayl yuboring:")
            return

        anime_id = temp_data[user_id]["anime_id"]
        video_id = message.video.file_id

        res = execute_query("SELECT MAX(part_num) FROM parts WHERE anime_id = ?", (anime_id,), fetchone=True)[0]
        next_part = 1 if res is None else res + 1

        execute_query("INSERT INTO parts (anime_id, part_num, video_id) VALUES (?, ?, ?)", (anime_id, next_part, video_id), commit=True)
        anime_name = execute_query("SELECT name FROM animes WHERE id = ?", (anime_id,), fetchone=True)[0]

        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("➕ Yana qism qo'shish", callback_data=f"add_next_auto_{anime_id}"),
            types.InlineKeyboardButton("✅ Tamomlash", callback_data="finish_adding")
        )

        send_clean_message(
            chat_id,
                  f"✅ <b>{anime_name}</b> animasiga <b>{next_part}-qism</b> qo'shildi! 🎬\n\nYana qism qo'shasizmi?",
            reply_markup=markup,
            parse_mode="HTML"
        )
        return

    # Jild rasmini tahrirlash uchun qabul qilish
    if state == "ADMIN_EDIT_FOLDER_PHOTO" and user_id == ADMIN_ID:
        photo_id = message.photo[-1].file_id if message.content_type == "photo" else ""
        temp_data[user_id]["edit_photo"] = photo_id
        user_states[user_id] = "ADMIN_EDIT_FOLDER_NAME"
        send_clean_message(chat_id, "✏️ Yangi jild nomini kiriting:")
        return

    # Qism videosini tahrirlash uchun qabul qilish
    if state == "ADMIN_EDIT_PART_VIDEO" and user_id == ADMIN_ID:
        if message.content_type != "video":
            send_clean_message(chat_id, "⚠️ Iltimos, anime uchun to'g'ri video fayl yuboring:")
            return

        anime_id = temp_data[user_id]["anime_id"]
        part_num = temp_data[user_id]["part_num"]
        video_id = message.video.file_id

        part_exists = execute_query("SELECT id FROM parts WHERE anime_id = ? AND part_num = ?", (anime_id, part_num), fetchone=True)
        if part_exists:
            execute_query("UPDATE parts SET video_id = ? WHERE anime_id = ? AND part_num = ?", (video_id, anime_id, part_num), commit=True)
        else:
            execute_query("INSERT INTO parts (anime_id, part_num, video_id) VALUES (?, ?, ?)", (anime_id, part_num, video_id), commit=True)

        user_states.pop(user_id, None)
        temp_data.pop(user_id, None)
        send_clean_message(chat_id, f"✅ {part_num}-qism muvaffaqiyatli saqlandi!", reply_markup=get_main_inline_menu(user_id))
        return

# --- CALLBACK QUERY HANDLER ---
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    data = call.data

    if data == "check_subscription":
        unsub = check_sub(user_id)
        if unsub is not True and unsub:
            bot.answer_callback_query(call.id, "❌ Hali hamma kanallarga a'zo bo'lmadingiz!", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "✅ Obuna tasdiqlandi!")
            send_clean_message(chat_id, "👋 Xush kelibsiz! Kerakli bo'limni tanlang:", reply_markup=get_main_inline_menu(user_id))

    elif data == "back_to_main":
        user_states.pop(user_id, None)
        temp_data.pop(user_id, None)
        bot.answer_callback_query(call.id)
        send_clean_message(chat_id, "👋 Kerakli bo'limni tanlang:", reply_markup=get_main_inline_menu(user_id))

    elif data == "menu_search":
        bot.answer_callback_query(call.id)
        send_clean_message(chat_id, "🔍 Izlash usulini tanlang:", reply_markup=get_search_inline_keyboard())

    elif data.startswith("menu_available_page_"):
        page = int(data.replace("menu_available_page_", ""))
        bot.answer_callback_query(call.id)
        send_clean_message(chat_id, f"📂 Mavjud anime jildlari ({page}-sahifa):", reply_markup=get_available_animes_keyboard(page=page, action_type="show"))

    elif data == "menu_recommended":
        bot.answer_callback_query(call.id)
        send_clean_message(chat_id, "🔥 Eng ko'p ko'rilgan animelar:", reply_markup=get_recommended_animes_keyboard())

    elif data == "admin_add_folder" and user_id == ADMIN_ID:
        user_states[user_id] = "ADD_NAME"
        temp_data[user_id] = {}
        bot.answer_callback_query(call.id)
        send_clean_message(chat_id, "✏️ Yangi anime nomini kiriting:")

    elif data == "admin_add_part" and user_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        send_clean_message(chat_id, "📂 Qaysi anime jildiga yangi qism qo'shmoqchisiz? Tanlang:", reply_markup=get_available_animes_keyboard(page=1, action_type="add_part"))

    elif data == "admin_edit_menu" and user_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📂 Jild tahrirlash", callback_data="admin_edit_folder"),
            types.InlineKeyboardButton("🎬 Qism tahrirlash", callback_data="admin_edit_part"),
            types.InlineKeyboardButton("⬅️ Asosiy menyu", callback_data="back_to_main")
        )
        send_clean_message(chat_id, "🛠 Tahrirlash bo'limini tanlang:", reply_markup=markup)

    elif data == "admin_edit_folder" and user_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        send_clean_message(chat_id, "📂 Tahrirlash uchun animeni tanlang:", reply_markup=get_available_animes_keyboard(page=1, action_type="edit_folder"))

    elif data.startswith("select_edit_folder_") and user_id == ADMIN_ID:
        anime_id = int(data.replace("select_edit_folder_", ""))
        bot.answer_callback_query(call.id)
        user_states[user_id] = "ADMIN_EDIT_FOLDER_PHOTO"
        temp_data[user_id] = {"anime_id": anime_id}
        send_clean_message(chat_id, "🖼 Yangi muqova rasmini yuboring (rasm kerak bo'lmasa /skip yuboring):")

    elif data == "admin_edit_part" and user_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        user_states[user_id] = "ADMIN_EDIT_PART_SEARCH"
        send_clean_message(chat_id, "🎬 Tahrirlamoqchi bo'lgan animening kodi yoki nomini kiriting:")

    elif data == "admin_manage" and user_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        send_clean_message(chat_id, "⚙️ Boshqarish uchun animeni tanlang:", reply_markup=get_available_animes_keyboard(page=1, action_type="admin_opt"))

    elif data == "admin_channels" and user_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        channels = [row[0] for row in execute_query("SELECT username FROM channels", fetchall=True) or []]
        bot_info = bot.get_me()
        add_group_url = f"https://t.me/{bot_info.username}?startgroup=true"

        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("➕ Kanal qo'shish", callback_data="add_channel"),
            types.InlineKeyboardButton("🤖 Botni guruhga qo'shish", url=add_group_url)
        )
        for ch in channels:
            markup.add(types.InlineKeyboardButton(f"❌ O'chirish: {ch}", callback_data=f"del_ch_{ch}"))
        markup.add(types.InlineKeyboardButton("⬅️ Asosiy menyu", callback_data="back_to_main"))

        ch_text = "\n".join(channels) if channels else "Hozircha kanallar yo'q"
        send_clean_message(chat_id, f"📢 <b>Kanallarni boshqarish bo'limi:</b>\n\nUlangan kanallar:\n{ch_text}", reply_markup=markup)

    elif data == "admin_stats" and user_id == ADMIN_ID:
        bot.answer_callback_query(call.id)
        total_users = execute_query("SELECT COUNT(*) FROM users", fetchone=True)[0]
        total_animes = execute_query("SELECT COUNT(*) FROM animes", fetchone=True)[0]
        total_parts = execute_query("SELECT COUNT(*) FROM parts", fetchone=True)[0]
        total_views = execute_query("SELECT SUM(views) FROM animes", fetchone=True)[0] or 0

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⬅️ Asosiy menyu", callback_data="back_to_main"))

        text = (
            f"📊 <b>Bot Statistikasi:</b>\n\n"
            f"👥 Jami foydalanuvchilar: <b>{total_users} ta</b>\n"
            f"📂 Jami anime jildlari: <b>{total_animes} ta</b>\n"
            f"🎬 Jami qismlar: <b>{total_parts} ta</b>\n"
            f"👁 Jami ko'rishlar: <b>{total_views} marta</b>"
        )
        send_clean_message(chat_id, text, reply_markup=markup)

    elif data == "add_channel" and user_id == ADMIN_ID:
        user_states[user_id] = "ADD_CHANNEL_WAIT"
        bot.answer_callback_query(call.id)
        send_clean_message(chat_id, "📢 Kanal username-ini yuboring (Masalan: @kanal_username):")

    elif data.startswith("del_ch_") and user_id == ADMIN_ID:
        ch_name = data.replace("del_ch_", "")
        execute_query("DELETE FROM channels WHERE username = ?", (ch_name,), commit=True)
        bot.answer_callback_query(call.id, f"{ch_name} o'chirildi!")
        send_clean_message(chat_id, f"✅ {ch_name} kanali o'chirildi!", reply_markup=get_main_inline_menu(user_id))

    elif data == "search_by_name":
        user_states[user_id] = "SEARCH_NAME_WAIT"
        bot.answer_callback_query(call.id)
        send_clean_message(chat_id, "✏️ Anime nomini yozing:")

    elif data == "search_by_secret":
        user_states[user_id] = "SEARCH_SECRET_WAIT"
        bot.answer_callback_query(call.id)
        send_clean_message(chat_id, "🕵️ Yashirin nomini yozing:")

    elif data == "search_by_code":
        user_states[user_id] = "SEARCH_CODE_WAIT"
        bot.answer_callback_query(call.id)
        send_clean_message(chat_id, "🔢 Anime kodini yozing:")

    elif data.startswith("select_anime_for_part_") and user_id == ADMIN_ID:
        anime_id = int(data.replace("select_anime_for_part_", ""))
        user_states[user_id] = "ADD_AUTO_VIDEO"
        temp_data[user_id] = {"anime_id": anime_id}
        bot.answer_callback_query(call.id)

        res = execute_query("SELECT MAX(part_num) FROM parts WHERE anime_id = ?", (anime_id,), fetchone=True)[0]
        next_num = 1 if res is None else res + 1
        an_name = execute_query("SELECT name FROM animes WHERE id = ?", (anime_id,), fetchone=True)[0]

        send_clean_message(chat_id, f"🎬 <b>{an_name}</b> uchun <b>{next_num}-qism</b> videosini yuboring:")

    elif data.startswith("admin_anime_opt_") and user_id == ADMIN_ID:
              anime_id = int(data.replace("admin_anime_opt_", ""))
        bot.answer_callback_query(call.id)
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("➕ Keyingi qismni qo'shish", callback_data=f"add_next_auto_{anime_id}"),
            types.InlineKeyboardButton("🗑 Animeni butunlay o'chirish", callback_data=f"delete_anime_{anime_id}"),
            types.InlineKeyboardButton("⬅️ Ortga", callback_data="admin_manage")
        )
        send_clean_message(chat_id, "⚙️ Tanlang:", reply_markup=markup)

    elif data.startswith("add_next_auto_") and user_id == ADMIN_ID:
        anime_id = int(data.replace("add_next_auto_", ""))
        user_states[user_id] = "ADD_AUTO_VIDEO"
        temp_data[user_id] = {"anime_id": anime_id}
        bot.answer_callback_query(call.id)

        res = execute_query("SELECT MAX(part_num) FROM parts WHERE anime_id = ?", (anime_id,), fetchone=True)[0]
        next_num = 1 if res is None else res + 1
        an_name = execute_query("SELECT name FROM animes WHERE id = ?", (anime_id,), fetchone=True)[0]

        send_clean_message(chat_id, f"🎬 <b>{an_name}</b> uchun <b>{next_num}-qism</b> videosini yuboring:")

    elif data == "finish_adding":
        bot.answer_callback_query(call.id, "Barcha qismlar saqlandi!")
        user_states.pop(user_id, None)
        temp_data.pop(user_id, None)
        send_clean_message(chat_id, "✅ Jarayon yakunlandi. Kerakli bo'limni tanlang:", reply_markup=get_main_inline_menu(user_id))

    elif data.startswith("delete_anime_") and user_id == ADMIN_ID:
        anime_id = int(data.replace("delete_anime_", ""))
        execute_query("DELETE FROM parts WHERE anime_id = ?", (anime_id,), commit=True)
        execute_query("DELETE FROM animes WHERE id = ?", (anime_id,), commit=True)
        bot.answer_callback_query(call.id, "Anime o'chirildi!")
        send_clean_message(chat_id, "🗑 Anime muvaffaqiyatli o'chirildi.", reply_markup=get_main_inline_menu(user_id))

    elif data.startswith("show_anime_"):
        anime_id = int(data.replace("show_anime_", ""))
        q = "SELECT name, secret_name, info, views, code, episodes_count, status, quality, genre, channel_name, photo FROM animes WHERE id = ?"
        anime = execute_query(q, (anime_id,), fetchone=True)

        if not anime:
            bot.answer_callback_query(call.id, "❌ Anime topilmadi!", show_alert=True)
            return

        execute_query("UPDATE animes SET views = views + 1 WHERE id = ?", (anime_id,), commit=True)
        photo = anime[10]
        text = format_anime_text(anime[:10])
        markup = get_anime_folder_keyboard(anime_id, page=1)
        bot.answer_callback_query(call.id)

        if photo:
            send_clean_photo(chat_id, photo, text, reply_markup=markup, protect=True)
        else:
            send_clean_message(chat_id, text, reply_markup=markup, protect=True)

    elif data.startswith("page_"):
        parts_data = data.replace("page_", "").split("_")
        anime_id = int(parts_data[0])
        page = int(parts_data[1])
        bot.answer_callback_query(call.id)

        markup = get_anime_folder_keyboard(anime_id, page=page)
        try:
            bot.edit_message_reply_markup(chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup)
        except Exception:
            pass

    elif data.startswith("get_part_"):
        parts_data = data.replace("get_part_", "").split("_")
        anime_id = int(parts_data[0])
        part_num = int(parts_data[1])

        part = execute_query("SELECT video_id FROM parts WHERE anime_id = ? AND part_num = ?", (anime_id, part_num), fetchone=True)
        bot.answer_callback_query(call.id)
        if part:
            bot.send_video(chat_id, part[0], caption=f"🎬 <b>{part_num}-qism</b>", parse_mode="HTML", protect_content=True)
        else:
            bot.answer_callback_query(call.id, "❌ Video topilmadi!", show_alert=True)

# --- BOTNI ISHGA TUSHIRISH ---
def run_telegram_bot():
    try:
        bot.remove_webhook()
        bot.infinity_polling()
    except Exception as e:
        print(f"Botda xatolik: {e}")

if __name__ == '__main__':
    bot_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    bot_thread.start()

    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
