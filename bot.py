import os
import sqlite3
import threading
from urllib.parse import urlparse
from flask import Flask
import telebot
from telebot import types

# PostgreSQL kutubxonasini yuklash
try:
    import psycopg2
except ImportError:
    psycopg2 = None

# --- SOZLAMALAR ---
TOKEN = os.environ.get(
    "BOT_TOKEN", "8987164421:AAHUuwzB_GBn70KPk0cxQdIiXNV5weN_6jw"
)
ADMIN_ID = int(os.environ.get("ADMIN_ID", "7986354170"))
DATABASE_URL = os.environ.get("DATABASE_URL", None)
DB_FILE = "bot_data.db"

bot = telebot.TeleBot(TOKEN)

# --- FLASK VEB-SERVER ---
app = Flask(__name__)


@app.route("/")
def home():
    return "Bot is running and alive!"


def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))


def keep_alive():
    t = threading.Thread(target=run_web)
    t.daemon = True
    t.start()


# --- BOTNING MENYU BUYRUQLARI ---
def set_bot_commands():
    commands = [
        types.BotCommand("start", "Botni ishga tushirish va asosiy menyu"),
        types.BotCommand("anime", "Anime qidirish"),
    ]
    try:
        bot.set_my_commands(
            commands, scope=types.BotCommandScopeAllPrivateChats()
        )
        bot.set_my_commands(
            commands, scope=types.BotCommandScopeAllGroupChats()
        )
    except Exception:
        pass
        # --- MA'LUMOTLAR BAZASI MANTIG'I (PostgreSQL & SQLite) ---
def get_db_connection():
    if DATABASE_URL and psycopg2:
        parsed_url = urlparse(DATABASE_URL)
        username = parsed_url.username
        password = parsed_url.password
        database = parsed_url.path[1:]
        hostname = parsed_url.hostname
        port = parsed_url.port
        return psycopg2.connect(
            database=database,
            user=username,
            password=password,
            host=hostname,
            port=port,
            sslmode="require",
        )
    else:
        return sqlite3.connect(DB_FILE)


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    is_postgres = DATABASE_URL and psycopg2

    if is_postgres:
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS users (user_id BIGINT PRIMARY KEY)"
        )
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS channels (username TEXT PRIMARY KEY)"
        )
        cursor.execute("""CREATE TABLE IF NOT EXISTS animes (
            id SERIAL PRIMARY KEY,
            name TEXT,
            secret_name TEXT,
            code TEXT,
            info TEXT,
            photo TEXT,
            episodes_count TEXT DEFAULT 'Noma''lum',
            status TEXT DEFAULT 'Davom etmoqda',
            quality TEXT DEFAULT '720p',
            genre TEXT DEFAULT 'Noma''lum',
            channel_name TEXT DEFAULT 'Noma''lum',
            views INTEGER DEFAULT 0
        )""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS parts (
            id SERIAL PRIMARY KEY,
            anime_id INTEGER,
            part_num INTEGER,
            video_id TEXT
        )""")
    else:
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)"
        )
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS channels (username TEXT PRIMARY KEY)"
        )
        cursor.execute("""CREATE TABLE IF NOT EXISTS animes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            secret_name TEXT,
            code TEXT,
            info TEXT,
            photo TEXT,
            episodes_count TEXT DEFAULT 'Noma''lum',
            status TEXT DEFAULT 'Davom etmoqda',
            quality TEXT DEFAULT '720p',
            genre TEXT DEFAULT 'Noma''lum',
            channel_name TEXT DEFAULT 'Noma''lum',
            views INTEGER DEFAULT 0
        )""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS parts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            anime_id INTEGER,
            part_num INTEGER,
            video_id TEXT
        )""")
    conn.commit()
    conn.close()


def execute_query(
    query, params=(), fetchone=False, fetchall=False, commit=False
):
    conn = get_db_connection()
    cursor = conn.cursor()

    if DATABASE_URL and psycopg2:
        query = query.replace("?", "%s")
    else:
        query = query.replace("%s", "?")

    cursor.execute(query, params)
    result = None
    if fetchone:
        result = cursor.fetchone()
    elif fetchall:
        result = cursor.fetchall()

    if commit:
        conn.commit()
    conn.close()
    return result


init_db()
set_bot_commands()

user_states = {}
temp_data = {}
user_last_messages = {}


# --- XABARLARNI TOZALASH MANTIG'I ---
def add_bot_message_to_history(chat_id, msg_id, protect=False):
    if chat_id < 0:
        return
    if chat_id not in user_last_messages:
        user_last_messages[chat_id] = []
    user_last_messages[chat_id].append({"msg_id": msg_id, "protect": protect})

    unprotected = [m for m in user_last_messages[chat_id] if not m["protect"]]
    while len(unprotected) > 2:
        old_item = unprotected.pop(0)
        user_last_messages[chat_id].remove(old_item)
        try:
            bot.delete_message(chat_id, old_item["msg_id"])
        except Exception:
            pass


def send_clean_message(
    chat_id, text, reply_markup=None, parse_mode=None, protect=False
):
    msg = bot.send_message(
        chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode
    )
    add_bot_message_to_history(chat_id, msg.message_id, protect=protect)
    return msg


def send_clean_photo(
    chat_id, photo, caption, reply_markup=None, parse_mode=None, protect=False
):
    msg = bot.send_photo(
        chat_id,
        photo,
        caption=caption,
        reply_markup=reply_markup,
        parse_mode=parse_mode,
    )
    add_bot_message_to_history(chat_id, msg.message_id, protect=protect)
    return msg
        # --- MAJBURIY OBUNA ---
def check_sub(user_id):
    if user_id == ADMIN_ID:
        return True
    channels = [
        row[0]
        for row in execute_query(
            "SELECT username FROM channels", fetchall=True
        )
        or []
    ]
    if not channels:
        return True
    unsubscribed = []
    for ch in channels:
        try:
            member = bot.get_chat_member(ch, user_id)
            if member.status in ["left", "kicked"]:
                unsubscribed.append(ch)
        except Exception:
            pass
    return unsubscribed if unsubscribed else True


def get_sub_keyboard(unsubscribed_channels):
    markup = types.InlineKeyboardMarkup(row_width=1)
    for ch in unsubscribed_channels:
        clean_ch = ch.replace("@", "")
        url = f"https://t.me/{clean_ch}"
        markup.add(
            types.InlineKeyboardButton(f"📢 Kanalga a'zo bo'lish", url=url)
        )
    markup.add(
        types.InlineKeyboardButton(
            "✅ Obunani tekshirish", callback_data="check_subscription"
        )
    )
    return markup


# --- INLINE MENYULAR ---
def get_main_inline_menu(user_id):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(
            "🔍 Animelarni izlash", callback_data="menu_search"
        ),
        types.InlineKeyboardButton(
            "📁 Mavjud animelar", callback_data="menu_available_page_1"
        ),
        types.InlineKeyboardButton(
            "🔥 Tavsiya etiladigan animelar", callback_data="menu_recommended"
        ),
    )

    if user_id == ADMIN_ID:
        markup.add(
            types.InlineKeyboardButton(
                "➕ Yangi anime qo'shish", callback_data="admin_add_folder"
            ),
            types.InlineKeyboardButton(
                "📁 Mavjud jildga qism qo'shish",
                callback_data="admin_add_part",
            ),
            types.InlineKeyboardButton(
                "✏️ Anime jildlarini tahrirlash",
                callback_data="admin_edit_menu",
            ),
            types.InlineKeyboardButton(
                "📢 Kanallarni boshqarish", callback_data="admin_channels"
            ),
            types.InlineKeyboardButton(
                "📊 Statistika", callback_data="admin_stats"
            ),
            types.InlineKeyboardButton(
                "⚙️ Animelarni boshqarish", callback_data="admin_manage"
            ),
        )
    return markup


def get_search_inline_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(
            "📝 Nomi orqali", callback_data="search_by_name"
        ),
        types.InlineKeyboardButton(
            "🔢 Kodi orqali", callback_data="search_by_code"
        ),
        types.InlineKeyboardButton(
            "🔙 Asosiy menyu", callback_data="back_to_main"
        ),
    )
    return markup
def get_available_animes_keyboard(page=1, action_type="show"):
    markup = types.InlineKeyboardMarkup(row_width=1)
    animes = (
        execute_query(
            "SELECT id, name FROM animes ORDER BY id DESC", fetchall=True
        )
        or []
    )

    if not animes:
        markup.add(
            types.InlineKeyboardButton(
                "❌ Hozircha animelar yo'q", callback_data="none"
            )
        )
        markup.add(
            types.InlineKeyboardButton(
                "🔙 Asosiy menyu", callback_data="back_to_main"
            )
        )
        return markup

    items_per_page = 15
    total_pages = (len(animes) + items_per_page - 1) // items_per_page
    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    current_animes = animes[start_idx:end_idx]

    for anime_id, name in current_animes:
        parts_count = (
            execute_query(
                "SELECT COUNT(*) FROM parts WHERE anime_id = ?",
                (anime_id,),
                fetchone=True,
            )[0]
            or 0
        )
        btn_text = f"📁 {name} ({parts_count}-qism)"

        if action_type == "add_part":
            cb = f"select_anime_for_part_{anime_id}"
        elif action_type == "admin_opt":
            cb = f"admin_anime_opt_{anime_id}"
        elif action_type == "edit_folder":
            cb = f"select_edit_folder_{anime_id}"
        else:
            cb = f"show_anime_{anime_id}"

        markup.add(types.InlineKeyboardButton(btn_text, callback_data=cb))

    nav_buttons = []
    if page > 1:
        nav_buttons.append(
            types.InlineKeyboardButton(
                "◀️", callback_data=f"menu_available_page_{page-1}"
            )
        )
    nav_buttons.append(
        types.InlineKeyboardButton(
            f"📄 {page}/{total_pages}", callback_data="none"
        )
    )
    if page < total_pages:
        nav_buttons.append(
            types.InlineKeyboardButton(
                "▶️", callback_data=f"menu_available_page_{page+1}"
            )
        )

    markup.row(*nav_buttons)
    markup.add(
        types.InlineKeyboardButton(
            "🏠 Asosiy menyu", callback_data="back_to_main"
        )
    )
    return markup


def get_recommended_animes_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    animes = (
        execute_query(
            "SELECT id, name, views FROM animes ORDER BY views DESC LIMIT 10",
            fetchall=True,
        )
        or []
    )

    if not animes:
        markup.add(
            types.InlineKeyboardButton(
                "❌ Hozircha animelar yo'q", callback_data="none"
            )
        )
        markup.add(
            types.InlineKeyboardButton(
                "🔙 Asosiy menyu", callback_data="back_to_main"
            )
        )
        return markup

    for rank, (anime_id, name, views) in enumerate(animes, start=1):
        btn_text = f"#{rank}. 🎬 {name} – 👀 {views} ko'rilgan"
        markup.add(
            types.InlineKeyboardButton(
                btn_text, callback_data=f"show_anime_{anime_id}"
            )
        )
    markup.add(
        types.InlineKeyboardButton(
            "🔙 Asosiy menyu", callback_data="back_to_main"
        )
    )
    return markup


def get_anime_folder_keyboard(anime_id, page=1):
    markup = types.InlineKeyboardMarkup(row_width=5)
    parts_res = (
        execute_query(
            "SELECT part_num FROM parts WHERE anime_id = ? ORDER BY part_num ASC",
            (anime_id,),
            fetchall=True,
        )
        or []
    )
    parts = [row[0] for row in parts_res]

    items_per_page = 15
    total_pages = (len(parts) + items_per_page - 1) // items_per_page
    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    current_parts = parts[start_idx:end_idx]

    buttons = []
    for p in current_parts:
        buttons.append(
            types.InlineKeyboardButton(
                text=str(p), callback_data=f"get_part_{anime_id}_{p}"
            )
        )

    if buttons:
        markup.add(*buttons)

    nav_buttons = []
    if page > 1:
        nav_buttons.append(
            types.InlineKeyboardButton(
                "◀️", callback_data=f"page_{anime_id}_{page-1}"
            )
        )
    nav_buttons.append(
        types.InlineKeyboardButton(
            f"❌", callback_data="menu_available_page_1"
        )
    )
    if page < total_pages:
        nav_buttons.append(
            types.InlineKeyboardButton(
                "▶️", callback_data=f"page_{anime_id}_{page+1}"
            )
        )

    markup.add(*nav_buttons)
    markup.add(
        types.InlineKeyboardButton(
            "🏠 Asosiy menyu", callback_data="back_to_main"
        )
    )
    return markup
def format_anime_text(anime_data, bot_username=""):
    (
        name,
        secret_name,
        info,
        views,
        code,
        episodes_count,
        status,
        quality,
        genre,
        channel_name,
    ) = anime_data

    formatted_text = (
        f"🎬 <b>{name}</b>\n\n"
        f"┣ 🎬 Qism: {episodes_count}\n"
        f"┣ 🌐 Holati: {status}\n"
        f"┣ 💻 Sifat - {quality}\n"
        f"┣ 🎭 Janrlari: {genre}\n"
        f"┗ 📢 Kanal: {channel_name}\n\n"
        f"📖 <b>Mazmuni:</b>\n{info}\n\n"
        f"🔥 Botimiz: @{bot_username}\n"
        f"🔥 Anime ID: {code}\n"
        f"🔥 Reyting: ⭐ 5/5\n"
        f"🔥 Link: https://t.me/{bot_username}?start=anime_{code}\n\n"
        f"✨ **YUKLAB OLISH** ✨"
    )
    return formatted_text


def show_search_results(chat_id, results):
    if not results:
        send_clean_message(chat_id, "❌ Afsuski, bunday anime topilmadi.")
        return
    markup = types.InlineKeyboardMarkup(row_width=1)
    for anime_id, name in results:
        markup.add(
            types.InlineKeyboardButton(
                f"🎬 {name}", callback_data=f"show_anime_{anime_id}"
            )
        )
    markup.add(
        types.InlineKeyboardButton(
            "🏠 Asosiy menyu", callback_data="back_to_main"
        )
    )
    send_clean_message(chat_id, "🔍 Topilgan animelar:", reply_markup=markup)


@bot.inline_handler(func=lambda query: True)
def inline_query_handler(query):
    text = query.query.strip().lower()
    if text:
        animes = (
            execute_query(
                "SELECT id, name, secret_name, info, photo, code FROM animes WHERE LOWER(name) LIKE ? OR LOWER(secret_name) LIKE ? OR LOWER(code) = ?",
                (f"%{text}%", f"%{text}%", text),
                fetchall=True,
            )
            or []
        )
    else:
        animes = (
            execute_query(
                "SELECT id, name, secret_name, info, photo, code FROM animes LIMIT 10",
                fetchall=True,
            )
            or []
        )

    results = []
    bot_info = bot.get_me()
    bot_username = bot_info.username

    for anime_id, name, secret_name, info, photo, code in animes:
        deeplink_url = f"https://t.me/{bot_username}?start=anime_{anime_id}"
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(
            types.InlineKeyboardButton(
                "✨ TOMOSHA QILISH ✨", url=deeplink_url
            )
        )

        description = info[:100] if info else "Ma'lumot yo'q"
        thumb_url = (
            photo
            if photo
            else "https://cdn-icons-png.flaticon.com/512/3163/3163613.png"
        )

        results.append(
            types.InlineQueryResultArticle(
                id=str(anime_id),
                title=f"🎬 {name}",
                description=f"🔑 Kodi: {code} | {description}",
                thumb_url=thumb_url,
                input_message_content=types.InputTextMessageContent(
                    f"🎬 <b>{name}</b>\n\n🔑 Kodi: <code>{code}</code>\n\n📖 {info}\n\n✨ Animeni ko'rish uchun pastdagi tugmani bosing:",
                    parse_mode="HTML",
                ),
                reply_markup=keyboard,
            )
        )

    bot.answer_inline_query(query.id, results, cache_time=1)
@bot.message_handler(commands=["start"])
def start_cmd(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if chat_id < 0:
        bot.reply_to(
            message,
            "🤖 Bot faol holatda! Animelarni qidirish uchun /anime [Nomi] deb yozing yoki shaxsiy chatga o'ting.",
        )
        return

    unsub = check_sub(user_id)
    if unsub is not True and unsub:
        text = "⚠️ Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:"
        send_clean_message(chat_id, text, reply_markup=get_sub_keyboard(unsub))
        return

    query = (
        "INSERT INTO users (user_id) VALUES (%s) ON CONFLICT DO NOTHING"
        if DATABASE_URL
        else "INSERT OR IGNORE INTO users (user_id) VALUES (?)"
    )
    execute_query(query, (user_id,), commit=True)

    user_states.pop(user_id, None)
    temp_data.pop(user_id, None)

    args = message.text.split()
    if len(args) > 1 and args[1].startswith("anime_"):
        try:
            anime_id = int(args[1].replace("anime_", ""))
            q = (
                "SELECT name, secret_name, info, views, code, episodes_count, status,"
                " quality, genre, channel_name, photo FROM animes WHERE id = ?"
            )
            anime = execute_query(q, (anime_id,), fetchone=True)
            if anime:
                execute_query(
                    "UPDATE animes SET views = views + 1 WHERE id = ?",
                    (anime_id,),
                    commit=True,
                )
                photo = anime[10]
                bot_username = bot.get_me().username
                text = format_anime_text(anime[:10], bot_username)
                markup = get_anime_folder_keyboard(anime_id, page=1)
                if photo:
                    send_clean_photo(
                        chat_id,
                        photo,
                        text,
                        reply_markup=markup,
                        parse_mode="HTML",
                        protect=True,
                    )
                else:
                    send_clean_message(
                        chat_id,
                        text,
                        reply_markup=markup,
                        parse_mode="HTML",
                        protect=True,
                    )
                return
        except Exception:
            pass

    text = "👋 Xush kelibsiz! Kerakli bo'limni tanlang:"
    send_clean_message(chat_id, text, reply_markup=get_main_inline_menu(user_id))


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
        bot.reply_to(message, "⚠️ Anime nomini yozing. Masalan: /anime Naruto")
        return

    animes = (
        execute_query(
            "SELECT id, name, secret_name, info, photo, code FROM animes WHERE LOWER(name) LIKE ? OR LOWER(secret_name) LIKE ? OR LOWER(code) = ?",
            (f"%{query}%", f"%{query}%", query),
            fetchall=True,
        )
        or []
    )

    if not animes:
        bot.reply_to(message, "❌ Afsuski, bunday anime topilmadi.")
        return

    bot_info = bot.get_me()
    bot_username = bot_info.username

    for anime_id, name, secret_name, info, photo, code in animes:
        deeplink_url = f"https://t.me/{bot_username}?start=anime_{anime_id}"
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton(
                "✨ TOMOSHA QILISH ✨", url=deeplink_url
            )
        )

        desc = info[:150] if info else "Ma'lumot yo'q"
        caption = (
            f"🎬 <b>{name}</b>\n\n"
            f"📖 {desc}\n\n🔑 Kodi: <code>{code}</code>\n\n📥 Animeni to'liq ko'rish uchun pastdagi tugmani bosing:"
        )

        if photo:
            bot.send_photo(
                message.chat.id,
                photo,
                caption=caption,
                reply_markup=markup,
                parse_mode="HTML",
            )
        else:
            bot.send_message(
                message.chat.id,
                caption,
                reply_markup=markup,
                parse_mode="HTML",
            )
        break


@bot.message_handler(func=lambda message: True)
def main_messages(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    text_val = message.text.strip() if message.text else ""
    text_lower = text_val.lower()

    if chat_id < 0:
        return

    unsub = check_sub(user_id)
    if unsub is not True and unsub:
        text = "⚠️ Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:"
        send_clean_message(chat_id, text, reply_markup=get_sub_keyboard(unsub))
        return

    state = user_states.get(user_id)

    if state == "ADD_CHANNEL_WAIT" and user_id == ADMIN_ID:
        ch = text_val if text_val.startswith("@") else "@" + text_val
        try:
            execute_query(
                "INSERT INTO channels (username) VALUES (?)", (ch,), commit=True
            )
            send_clean_message(
                chat_id,
                f"✅ {ch} kanali qo'shildi!",
                reply_markup=get_main_inline_menu(user_id),
            )
        except Exception:
            send_clean_message(
                chat_id,
                "⚠️ Bu kanal allaqachon mavjud.",
                reply_markup=get_main_inline_menu(user_id),
            )
        user_states.pop(user_id, None)
        return

    if user_id == ADMIN_ID:
        if state == "ADD_NAME":
            temp_data[user_id] = {"name": text_val}
            user_states[user_id] = "ADD_SECRET_NAME"
            send_clean_message(
                chat_id, "🕵️ Anime uchun yashirin nom (kalit so'z) kiriting:"
            )
            return
        elif state == "ADD_SECRET_NAME":
            temp_data[user_id]["secret_name"] = text_val
            user_states[user_id] = "ADD_CODE"
            send_clean_message(
                chat_id,
                "🔑 Anime uchun maxsus raqamli kod kiriting (masalan: 12):",
            )
            return
        elif state == "ADD_CODE":
            temp_data[user_id]["code"] = text_lower
            user_states[user_id] = "ADD_EPISODES"
            send_clean_message(
                chat_id,
                "🍿 Anime necha qismdan iborat? (Masalan: 12 yoki 24 / Noma'lum):",
            )
            return
        elif state == "ADD_EPISODES":
            temp_data[user_id]["episodes_count"] = text_val
            user_states[user_id] = "ADD_STATUS"
            send_clean_message(
                chat_id,
                "🌐 Anime statusini kiriting (Masalan: Davom etmoqda / Tugallangan):",
            )
            return
        elif state == "ADD_STATUS":
            temp_data[user_id]["status"] = text_val
            user_states[user_id] = "ADD_QUALITY"
            send_clean_message(
                chat_id, "💻 Video sifatini kiriting (Masalan: 720p / 1080p):"
            )
            return
        elif state == "ADD_QUALITY":
            temp_data[user_id]["quality"] = text_val
            user_states[user_id] = "ADD_GENRE"
            send_clean_message(
                chat_id, "🎭 Anime janrini kiriting (Masalan: Jangari, Sarguzasht):"
            )
            return
        elif state == "ADD_GENRE":
            temp_data[user_id]["genre"] = text_val
            user_states[user_id] = "ADD_CHANNEL_NAME"
            send_clean_message(
                chat_id, "📢 Kanal nomini kiriting (Masalan: @AnimeKanal):"
            )
            return
        elif state == "ADD_CHANNEL_NAME":
            temp_data[user_id]["channel_name"] = text_val
            user_states[user_id] = "ADD_INFO"
            send_clean_message(
                chat_id,
                "📖 Anime haqida qisqacha ma'lumot kiriting (o'tkazib yuborish uchun /skip):",
            )
            return
        elif state == "ADD_INFO":
            info_text = (
                text_val if text_val != "/skip" else "Ma'lumot mavjud emas"
            )
            temp_data[user_id]["info"] = info_text
            user_states[user_id] = "ADD_PHOTO"
            send_clean_message(
                chat_id,
                "🖼️ Muqova rasmini yuboring (o'tkazib yuborish uchun /skip):",
            )
            return
        elif state == "ADD_PHOTO":
            photo_id = (
                message.photo[-1].file_id
                if message.photo
                else (None if text_val == "/skip" else text_val)
            )
            data = temp_data.get(user_id, {})
            try:
                if DATABASE_URL and psycopg2:
                    execute_query(
                        "INSERT INTO animes (name, secret_name, code, episodes_count, status, quality, genre, channel_name, info, photo) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (
                            data.get("name"),
                            data.get("secret_name"),
                            data.get("code"),
                            data.get("episodes_count"),
                            data.get("status"),
                            data.get("quality"),
                            data.get("genre"),
                            data.get("channel_name"),
                            data.get("info"),
                            photo_id,
                        ),
                        commit=True,
                    )
                else:
                    execute_query(
                        "INSERT INTO animes (name, secret_name, code, episodes_count, status, quality, genre, channel_name, info, photo) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            data.get("name"),
                            data.get("secret_name"),
                            data.get("code"),
                            data.get("episodes_count"),
                            data.get("status"),
                            data.get("quality"),
                            data.get("genre"),
                            data.get("channel_name"),
                            data.get("info"),
                            photo_id,
                        ),
                        commit=True,
                    )
                send_clean_message(
                    chat_id,
                    "✅ Anime jildi muvaffaqiyatli qo'shildi!",
                    reply_markup=get_main_inline_menu(user_id),
                )
            except Exception as e:
                send_clean_message(
                    chat_id,
                    f"⚠️ Xatolik yuz berdi: {e}",
                    reply_markup=get_main_inline_menu(user_id),
                )
            user_states.pop(user_id, None)
            temp_data.pop(user_id, None)
            return

        elif state == "ADD_PART_NUM":
            if not text_val.isdigit():
                send_clean_message(chat_id, "⚠️ Iltimos, faqat raqam kiriting:")
                return
            temp_data[user_id]["part_num"] = int(text_val)
            user_states[user_id] = "ADD_PART_VIDEO"
            send_clean_message(
                chat_id,
                "📤 Endi ushbu qism uchun video (fayl yoki video xabar) yuboring:",
            )
            return

        elif state == "ADMIN_EDIT_FOLDER_NAME":
            temp_data[user_id]["edit_name"] = text_val
            user_states[user_id] = "ADMIN_EDIT_FOLDER_CODE"
            send_clean_message(
                chat_id, "🔑 Endi jild uchun yangi kodni kiriting:"
            )
            return

        elif state == "ADMIN_EDIT_FOLDER_CODE":
            anime_id = temp_data[user_id]["anime_id"]
            new_name = temp_data[user_id]["edit_name"]
            new_code = text_lower
            new_photo = temp_data[user_id].get("edit_photo", "")

            execute_query(
                "UPDATE animes SET name = ?, code = ?, photo = ? WHERE id = ?",
                (new_name, new_code, new_photo, anime_id),
                commit=True,
            )

            user_states.pop(user_id, None)
            temp_data.pop(user_id, None)
            send_clean_message(
                chat_id,
                "✅ Jild muvaffaqiyatli tahrirlandi!",
                reply_markup=get_main_inline_menu(user_id),
            )
            return

        elif state == "ADMIN_EDIT_PART_SEARCH":
            res = execute_query(
                "SELECT id, name FROM animes WHERE LOWER(name) LIKE ? OR LOWER(code) = ?",
                (f"%{text_lower}%", text_lower),
                fetchone=True,
            )
            if res:
                temp_data[user_id] = {
                    "anime_id": res[0],
                    "anime_name": res[1],
                }
                user_states[user_id] = "ADMIN_EDIT_PART_NUM"
                send_clean_message(
                    chat_id,
                    f"✅ Anime topildi: **{res[1]}**\n\n🔢 Nechanchi qismni tahrirlamoqchisiz? (Faqat raqam kiriting):",
                )
            else:
                send_clean_message(
                    chat_id,
                    "❌ Bunday anime topilmadi. Qaytadan nomini yoki kodini yuboring:",
                )
            return

        elif state == "ADMIN_EDIT_PART_NUM":
            if not text_val.isdigit():
                send_clean_message(chat_id, "⚠️ Iltimos, faqat raqam kiriting:")
                return
            temp_data[user_id]["part_num"] = int(text_val)
            user_states[user_id] = "ADMIN_EDIT_PART_VIDEO"
            send_clean_message(
                chat_id, "📤 Endi ushbu qism uchun yangi videoni yuboring:"
            )
            return

    if user_id == ADMIN_ID and message.content_type in ["video", "document"]:
        video_id = (
            message.video.file_id
            if message.content_type == "video"
            else message.document.file_id
        )
        if state == "ADD_PART_VIDEO":
            anime_id = temp_data[user_id]["anime_id"]
            part_num = temp_data[user_id]["part_num"]
            try:
                if DATABASE_URL and psycopg2:
                    execute_query(
                        "INSERT INTO parts (anime_id, part_num, video_id) VALUES (%s, %s, %s)",
                        (anime_id, part_num, video_id),
                        commit=True,
                    )
                else:
                    execute_query(
                        "INSERT INTO parts (anime_id, part_num, video_id) VALUES (?, ?, ?)",
                        (anime_id, part_num, video_id),
                        commit=True,
                    )
                send_clean_message(
                    chat_id,
                    f"✅ {part_num}-qism muvaffaqiyatli qo'shildi!",
                    reply_markup=get_main_inline_menu(user_id),
                )
            except Exception as e:
                send_clean_message(
                    chat_id,
                    f"⚠️ Xatolik: {e}",
                    reply_markup=get_main_inline_menu(user_id),
                )
            user_states.pop(user_id, None)
            temp_data.pop(user_id, None)
            return

        elif state == "ADMIN_EDIT_PART_VIDEO":
            anime_id = temp_data[user_id]["anime_id"]
            part_num = temp_data[user_id]["part_num"]
            execute_query(
                "UPDATE parts SET video_id = ? WHERE anime_id = ? AND part_num = ?",
                (video_id, anime_id, part_num),
                commit=True,
            )
            user_states.pop(user_id, None)
            temp_data.pop(user_id, None)
            send_clean_message(
                chat_id,
                "✅ Qism videosi muvaffaqiyatli yangilandi!",
                reply_markup=get_main_inline_menu(user_id),
            )
            return

    if state == "SEARCH_NAME":
        animes = (
            execute_query(
                "SELECT id, name FROM animes WHERE LOWER(name) LIKE ? OR LOWER(secret_name) LIKE ?",
                (f"%{text_lower}%", f"%{text_lower}%"),
                fetchall=True,
            )
            or []
        )
        user_states.pop(user_id, None)
        show_search_results(chat_id, animes)
        return

    elif state == "SEARCH_CODE":
        animes = (
            execute_query(
                "SELECT id, name FROM animes WHERE LOWER(code) = ?",
                (text_lower,),
                fetchall=True,
            )
            or []
        )
        user_states.pop(user_id, None)
        show_search_results(chat_id, animes)
        return

    send_clean_message(
        chat_id,
        "❓ Noma'lum buyruq. Asosiy menyudan foydalaning:",
        reply_markup=get_main_inline_menu(user_id),
            )
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    data = call.data

    unsub = check_sub(user_id)
    if unsub is not True and unsub:
        try:
            bot.answer_callback_query(
                call.id,
                "⚠️ Botdan foydalanish uchun kanallarga a'zo bo'ling!",
                show_alert=True,
            )
        except Exception:
            pass
        return

    if data == "check_subscription":
        unsub = check_sub(user_id)
        if unsub is not True and unsub:
            try:
                bot.answer_callback_query(
                    call.id,
                    "❌ Hali hamma kanalga a'zo bo'lmadingiz!",
                    show_alert=True,
                )
            except Exception:
                pass
        else:
            try:
                bot.delete_message(chat_id, call.message.message_id)
            except Exception:
                pass
            send_clean_message(
                chat_id,
                "✅ Rahmat! Obuna tasdiqlandi. Kerakli bo'limni tanlang:",
                reply_markup=get_main_inline_menu(user_id),
            )
        return

    elif data == "back_to_main":
        user_states.pop(user_id, None)
        temp_data.pop(user_id, None)
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except Exception:
            pass
        send_clean_message(
            chat_id,
            "🏠 Asosiy menyu:",
            reply_markup=get_main_inline_menu(user_id),
        )
        return

    elif data == "menu_search":
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except Exception:
            pass
        send_clean_message(
            chat_id,
            "🔍 Qidirish turini tanlang:",
            reply_markup=get_search_inline_keyboard(),
        )
        return

    elif data.startswith("menu_available_page_"):
        page = int(data.replace("menu_available_page_", ""))
        try:
            bot.edit_message_text(
                "📁 Mavjud animelar ro'yxati:",
                chat_id,
                call.message.message_id,
                reply_markup=get_available_animes_keyboard(
                    page, action_type="show"
                ),
            )
        except Exception:
            try:
                bot.delete_message(chat_id, call.message.message_id)
            except Exception:
                pass
            send_clean_message(
                chat_id,
                "📁 Mavjud animelar ro'yxati:",
                reply_markup=get_available_animes_keyboard(
                    page, action_type="show"
                ),
            )
        return

    elif data == "menu_recommended":
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except Exception:
            pass
        send_clean_message(
            chat_id,
            "🔥 Eng ko'p ko'rilgan tavsiya etiladigan animelar:",
            reply_markup=get_recommended_animes_keyboard(),
        )
        return

    elif data == "search_by_name":
        user_states[user_id] = "SEARCH_NAME"
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except Exception:
            pass
        send_clean_message(chat_id, "📝 Qidirilayotgan anime nomini yuboring:")
        return

    elif data == "search_by_code":
        user_states[user_id] = "SEARCH_CODE"
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except Exception:
            pass
        send_clean_message(chat_id, "🔢 Anime kodini yuboring:")
        return

    elif data.startswith("show_anime_"):
        anime_id = int(data.replace("show_anime_", ""))
        q = (
            "SELECT name, secret_name, info, views, code, episodes_count, status,"
            " quality, genre, channel_name, photo FROM animes WHERE id = ?"
        )
        anime = execute_query(q, (anime_id,), fetchone=True)
        if anime:
            execute_query(
                "UPDATE animes SET views = views + 1 WHERE id = ?",
                (anime_id,),
                commit=True,
            )
            photo = anime[10]
            bot_username = bot.get_me().username
            text = format_anime_text(anime[:10], bot_username)
            markup = get_anime_folder_keyboard(anime_id, page=1)
            try:
                bot.delete_message(chat_id, call.message.message_id)
            except Exception:
                pass
            if photo:
                send_clean_photo(
                    chat_id,
                    photo,
                    text,
                    reply_markup=markup,
                    parse_mode="HTML",
                    protect=True,
                )
            else:
                send_clean_message(
                    chat_id,
                    text,
                    reply_markup=markup,
                    parse_mode="HTML",
                    protect=True,
                )
        return

    elif data.startswith("page_"):
        parts = data.split("_")
        anime_id = int(parts[1])
        page = int(parts[2])
        markup = get_anime_folder_keyboard(anime_id, page=page)
        try:
            bot.edit_message_reply_markup(
                chat_id, call.message.message_id, reply_markup=markup
            )
        except Exception:
            pass
        return

    elif data.startswith("get_part_"):
        parts = data.split("_")
        anime_id = int(parts[2])
        part_num = int(parts[3])

        res = execute_query(
            "SELECT video_id FROM parts WHERE anime_id = ? AND part_num = ?",
            (anime_id, part_num),
            fetchone=True,
        )
        if res and res[0]:
            try:
                bot.send_video(chat_id, res[0], caption=f"🎬 {part_num}-qism")
            except Exception:
                try:
                    bot.send_document(
                        chat_id, res[0], caption=f"🎬 {part_num}-qism"
                    )
                except Exception:
                    bot.answer_callback_query(
                        call.id,
                        "⚠️ Videoni yuborishda xatolik yuz berdi!",
                        show_alert=True,
                    )
        else:
            bot.answer_callback_query(
                call.id, "❌ Bu qism hali yuklanmagan!", show_alert=True
            )
        return

    # ADMIN PANEL CALLBACKLARI
    if user_id == ADMIN_ID:
        if data == "admin_add_folder":
            user_states[user_id] = "ADD_NAME"
            temp_data[user_id] = {}
            try:
                bot.delete_message(chat_id, call.message.message_id)
            except Exception:
                pass
            send_clean_message(chat_id, "➕ Yangi anime nomini kiriting:")
            return

        elif data == "admin_add_part":
            try:
                bot.delete_message(chat_id, call.message.message_id)
            except Exception:
                pass
            send_clean_message(
                chat_id,
                "📁 Qaysi animega qism qo'shmoqchisiz? Quyidagilardan birini tanlang:",
                reply_markup=get_available_animes_keyboard(
                    1, action_type="add_part"
                ),
            )
            return

        elif data.startswith("select_anime_for_part_"):
            anime_id = int(data.replace("select_anime_for_part_", ""))
            res = execute_query(
                "SELECT name FROM animes WHERE id = ?",
                (anime_id,),
                fetchone=True,
            )
            if res:
                temp_data[user_id] = {"anime_id": anime_id}
                user_states[user_id] = "ADD_PART_NUM"
                try:
                    bot.delete_message(chat_id, call.message.message_id)
                except Exception:
                    pass
                send_clean_message(
                    chat_id,
                    f"✅ Tanlangan anime: **{res[0]}**\n\n🔢 Nechanchi qismni qo'shmoqchisiz? (Faqat raqam kiriting):",
                )
            return

        elif data == "admin_channels":
            channels = [
                row[0]
                for row in execute_query(
                    "SELECT username FROM channels", fetchall=True
                )
                or []
            ]
            markup = types.InlineKeyboardMarkup(row_width=1)
            for ch in channels:
                markup.add(
                    types.InlineKeyboardButton(
                        f"❌ O'chirish: {ch}", callback_data=f"del_channel_{ch}"
                    )
                )
            markup.add(
                types.InlineKeyboardButton(
                    "➕ Kanal qo'shish", callback_data="add_channel_btn"
                )
            )
            markup.add(
                types.InlineKeyboardButton(
                    "🔙 Asosiy menyu", callback_data="back_to_main"
                )
            )
            try:
                bot.edit_message_text(
                    "📢 Majburiy obuna kanallari:",
                    chat_id,
                    call.message.message_id,
                    reply_markup=markup,
                )
            except Exception:
                try:
                    bot.delete_message(chat_id, call.message.message_id)
                except Exception:
                    pass
                send_clean_message(
                    chat_id,
                    "📢 Majburiy obuna kanallari:",
                    reply_markup=markup,
                )
            return

        elif data == "add_channel_btn":
            user_states[user_id] = "ADD_CHANNEL_WAIT"
            try:
                bot.delete_message(chat_id, call.message.message_id)
            except Exception:
                pass
            send_clean_message(
                chat_id,
                "📢 Kanal username'ini yuboring (Masalan: @kanal_nomi yoki kanal_nomi):",
            )
            return

        elif data.startswith("del_channel_"):
            ch = data.replace("del_channel_", "")
            execute_query(
                "DELETE FROM channels WHERE username = ?", (ch,), commit=True
            )
            bot.answer_callback_query(
                call.id, f"✅ {ch} o'chirildi!", show_alert=True
            )
            callback_handler(
                types.CallbackQuery(
                    id=call.id,
                    from_user=call.from_user,
                    json={},
                    message=call.message,
                    data="admin_channels",
                )
            )
            return

        elif data == "admin_stats":
            users_count = (
                execute_query("SELECT COUNT(*) FROM users", fetchone=True)[0]
                or 0
            )
            animes_count = (
                execute_query("SELECT COUNT(*) FROM animes", fetchone=True)[0]
                or 0
            )
            parts_count = (
                execute_query("SELECT COUNT(*) FROM parts", fetchone=True)[0]
                or 0
            )

            text = (
                f"📊 **Bot statistikasi:**\n\n"
                f"👤 Foydalanuvchilar: <b>{users_count}</b> ta\n"
                f"📁 Animelar (jildlar): <b>{animes_count}</b> ta\n"
                f"🎬 Jami qismlar: <b>{parts_count}</b> ta"
            )
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton(
                    "🔙 Asosiy menyu", callback_data="back_to_main"
                )
            )
            try:
                bot.edit_message_text(
                    text,
                    chat_id,
                    call.message.message_id,
                    reply_markup=markup,
                    parse_mode="HTML",
                )
            except Exception:
                try:
                    bot.delete_message(chat_id, call.message.message_id)
                except Exception:
                    pass
                send_clean_message(
                    chat_id, text, reply_markup=markup, parse_mode="HTML"
                )
            return

        elif data == "admin_manage":
            try:
                bot.delete_message(chat_id, call.message.message_id)
            except Exception:
                pass
            send_clean_message(
                chat_id,
                "⚙ Boshqarish uchun animeni tanlang:",
                reply_markup=get_available_animes_keyboard(
                    1, action_type="admin_opt"
                ),
            )
            return

        elif data.startswith("admin_anime_opt_"):
            anime_id = int(data.replace("admin_anime_opt_", ""))
            res = execute_query(
                "SELECT name FROM animes WHERE id = ?",
                (anime_id,),
                fetchone=True,
            )
            name = res[0] if res else "Anime"

            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton(
                    "🗑️ Anime jildini o'chirish",
                    callback_data=f"admin_del_folder_{anime_id}",
                ),
                types.InlineKeyboardButton(
                    "🔙 Orqaga", callback_data="admin_manage"
                ),
            )
            try:
                bot.edit_message_text(
                    f"⚙️ Anime: **{name}**\nAmalni tanlang:",
                    chat_id,
                    call.message.message_id,
                    reply_markup=markup,
                    parse_mode="HTML",
                )
            except Exception:
                pass
            return

        elif data.startswith("admin_del_folder_"):
            anime_id = int(data.replace("admin_del_folder_", ""))
            execute_query(
                "DELETE FROM parts WHERE anime_id = ?",
                (anime_id,),
                commit=True,
            )
            execute_query(
                "DELETE FROM animes WHERE id = ?", (anime_id,), commit=True
            )
            bot.answer_callback_query(
                call.id,
                "✅ Anime va uning barcha qismlari o'chirildi!",
                show_alert=True,
            )
            try:
                bot.delete_message(chat_id, call.message.message_id)
            except Exception:
                pass
            send_clean_message(
                chat_id,
                "✅ Muvaffaqiyatli o'chirildi!",
                reply_markup=get_main_inline_menu(user_id),
            )
            return

        elif data == "admin_edit_menu":
            try:
                bot.delete_message(chat_id, call.message.message_id)
            except Exception:
                pass
            send_clean_message(
                chat_id,
                "✏️ Tahrirlash uchun animeni tanlang:",
                reply_markup=get_available_animes_keyboard(
                    1, action_type="edit_folder"
                ),
            )
            return

        elif data.startswith("select_edit_folder_"):
            anime_id = int(data.replace("select_edit_folder_", ""))
            res = execute_query(
                "SELECT name, code FROM animes WHERE id = ?",
                (anime_id,),
                fetchone=True,
            )
            if res:
                temp_data[user_id] = {"anime_id": anime_id}
                user_states[user_id] = "ADMIN_EDIT_FOLDER_NAME"
                try:
                    bot.delete_message(chat_id, call.message.message_id)
                except Exception:
                    pass
                send_clean_message(
                    chat_id,
                    f"✏️ Tanlangan anime: **{res[0]}** (Kodi: {res[1]})\n\nJild uchun yangi nomni kiriting:",
                )
            return


# --- BOTNI ISHGA TUSHIRISH ---
if __name__ == "__main__":
    keep_alive()
    print("Bot muvaffaqiyatli ishga tushdi!")
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            print(f"Polling xatosi: {e}")
