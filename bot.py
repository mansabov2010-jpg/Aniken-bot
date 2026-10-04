import os
import sqlite3
import threading
import time
from urllib.parse import urlparse

from flask import Flask
import telebot
from telebot import types

try:
    import psycopg2
except ImportError:
    psycopg2 = None


# =========================================================
# SOZLAMALAR
# =========================================================

TOKEN = os.environ.get('BOT_TOKEN', '8987164421:AAHIKjTCtB4781Ns53b3WSHk5xgAWOXTtQ8')

if not TOKEN:
    raise RuntimeError(
        "BOT_TOKEN environment variable topilmadi!"
    )

ADMIN_ID = int(os.environ.get("ADMIN_ID", "7986354170"))

DATABASE_URL = os.environ.get("DATABASE_URL", None)

DB_FILE = "bot_data.db"


bot = telebot.TeleBot(TOKEN)

app = Flask(__name__)


# =========================================================
# WEB SERVER
# =========================================================

@app.route("/")
def home():
    return "Bot is running and alive!"


def run_web():
    port = int(os.environ.get("PORT", "10000"))

    app.run(
        host="0.0.0.0",
        port=port
    )


def keep_alive():
    t = threading.Thread(
        target=run_web,
        daemon=True
    )
    t.start()


# =========================================================
# BOT COMMANDS
# =========================================================

def set_bot_commands():
    commands = [
        types.BotCommand(
            "start",
            "Botni ishga tushirish va asosiy menyu"
        ),
        types.BotCommand(
            "anime",
            "Anime qidirish"
        ),
        types.BotCommand(
            "animekod",
            "Kod orqali anime olish"
        ),
    ]

    try:
        bot.set_my_commands(
            commands,
            scope=types.BotCommandScopeAllPrivateChats()
        )

        bot.set_my_commands(
            commands,
            scope=types.BotCommandScopeAllGroupChats()
        )

    except Exception as e:
        print(f"Bot commands xatoligi: {e}")


# =========================================================
# DATABASE
# =========================================================

def get_db_connection():
    if DATABASE_URL and psycopg2:
        parsed_url = urlparse(DATABASE_URL)

        return psycopg2.connect(
            database=parsed_url.path[1:],
            user=parsed_url.username,
            password=parsed_url.password,
            host=parsed_url.hostname,
            port=parsed_url.port,
            sslmode="require",
        )

    return sqlite3.connect(
        DB_FILE,
        timeout=30
    )


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    is_postgres = bool(DATABASE_URL and psycopg2)

    try:

        if is_postgres:

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS channels (
                    username TEXT PRIMARY KEY
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS animes (
                    id SERIAL PRIMARY KEY,
                    name TEXT,
                    sub_name TEXT,
                    hidden_name TEXT,
                    code TEXT,
                    info TEXT,
                    photo TEXT,
                    episodes_count TEXT DEFAULT 'Noma''lum',
                    status TEXT DEFAULT 'Tugallangan',
                    quality TEXT DEFAULT '720p, 1080p',
                    genre TEXT DEFAULT 'Drama, Isekai, fantastik',
                    channel_name TEXT DEFAULT '@AniRem_Org',
                    views INTEGER DEFAULT 0
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS parts (
                    id SERIAL PRIMARY KEY,
                    anime_id INTEGER,
                    part_num INTEGER,
                    video_id TEXT
                )
            """)

        else:

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS channels (
                    username TEXT PRIMARY KEY
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS animes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    sub_name TEXT,
                    hidden_name TEXT,
                    code TEXT,
                    info TEXT,
                    photo TEXT,
                    episodes_count TEXT DEFAULT 'Noma''lum',
                    status TEXT DEFAULT 'Tugallangan',
                    quality TEXT DEFAULT '720p, 1080p',
                    genre TEXT DEFAULT 'Drama, Isekai, fantastik',
                    channel_name TEXT DEFAULT '@AniRem_Org',
                    views INTEGER DEFAULT 0
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS parts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    anime_id INTEGER,
                    part_num INTEGER,
                    video_id TEXT
                )
            """)

        conn.commit()

    except Exception as e:
        conn.rollback()
        print(f"Database init xatoligi: {e}")
        raise

    finally:
        conn.close()


def execute_query(
    query,
    params=(),
    fetchone=False,
    fetchall=False,
    commit=False
):
    is_postgres = bool(DATABASE_URL and psycopg2)

    conn = None

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        if is_postgres:
            query = query.replace("?", "%s")
        else:
            query = query.replace("%s", "?")

        cursor.execute(
            query,
            params
        )

        result = None

        if fetchone:
            result = cursor.fetchone()

        elif fetchall:
            result = cursor.fetchall()

        if commit:
            conn.commit()

        return result

    except Exception as e:

        print(f"DB Error: {e}")

        if conn and commit:
            try:
                conn.rollback()
            except Exception:
                pass

        return None

    finally:

        if conn:
            conn.close()


# =========================================================
# DATABASE START
# =========================================================

init_db()


# =========================================================
# STATES
# =========================================================

user_states = {}

temp_data = {}


# =========================================================
# SUBSCRIPTION CHECK
# =========================================================

def check_sub(user_id):

    if user_id == ADMIN_ID:
        return True

    rows = execute_query(
        "SELECT username FROM channels",
        fetchall=True
    )

    channels = []

    if rows:
        channels = [
            row[0]
            for row in rows
        ]

    if not channels:
        return True

    unsubscribed = []

    for channel in channels:

        try:

            member = bot.get_chat_member(
                channel,
                user_id
            )

            if member.status in ["left", "kicked"]:
                unsubscribed.append(channel)

        except Exception as e:

            print(
                f"Obuna tekshirish xatoligi "
                f"{channel}: {e}"
            )

            # Kanalni tekshirib bo'lmasa,
            # foydalanuvchini avtomatik bloklamaymiz.
            continue

    return unsubscribed if unsubscribed else True


def get_sub_keyboard(unsubscribed_channels):

    markup = types.InlineKeyboardMarkup(
        row_width=1
    )

    for channel in unsubscribed_channels:

        clean_channel = channel.replace(
            "@",
            ""
        )

        url = f"https://t.me/{clean_channel}"

        markup.add(
            types.InlineKeyboardButton(
                "📢 Kanalga a'zo bo'lish",
                url=url
            )
        )

    markup.add(
        types.InlineKeyboardButton(
            "✅ Obunani tekshirish",
            callback_data="check_subscription"
        )
    )

    return markup


# =========================================================
# MAIN MENU
# =========================================================

def get_main_inline_menu(user_id):

    markup = types.InlineKeyboardMarkup(
        row_width=2
    )

    markup.add(
        types.InlineKeyboardButton(
            "🔍 Animelarni izlash",
            callback_data="menu_search"
        ),
        types.InlineKeyboardButton(
            "📁 Mavjud animelar",
            callback_data="menu_available_page_1"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "🔥 Tavsiya etiladigan",
            callback_data="menu_recommended"
        )
    )

    if user_id == ADMIN_ID:

        markup.add(
            types.InlineKeyboardButton(
                "➕ Anime qo'shish",
                callback_data="admin_add_folder"
            ),
            types.InlineKeyboardButton(
                "➕ Qism qo'shish",
                callback_data="admin_add_part"
            )
        )

        markup.add(
            types.InlineKeyboardButton(
                "✏️ Tahrirlash",
                callback_data="admin_edit_menu"
            ),
            types.InlineKeyboardButton(
                "⚙️ Kanallar",
                callback_data="admin_channels"
            )
        )

        markup.add(
            types.InlineKeyboardButton(
                "📊 Statistika",
                callback_data="admin_stats"
            ),
            types.InlineKeyboardButton(
                "🗑 Boshqarish",
                callback_data="admin_manage"
            )
        )

    return markup


# =========================================================
# SEARCH MENU
# =========================================================

def get_search_inline_keyboard():

    markup = types.InlineKeyboardMarkup(
        row_width=1
    )

    markup.add(
        types.InlineKeyboardButton(
            "🔤 Nomi orqali",
            callback_data="search_by_name"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "🔢 Kodi orqali",
            callback_data="search_by_code"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "🔙 Asosiy menyu",
            callback_data="back_to_main"
        )
    )

    return markup


# =========================================================
# AVAILABLE ANIMES
# =========================================================

def get_available_animes_keyboard(
    page=1,
    action_type="show"
):

    markup = types.InlineKeyboardMarkup(
        row_width=1
    )

    animes = (
        execute_query(
            """
            SELECT id, name
            FROM animes
            ORDER BY id DESC
            """,
            fetchall=True
        )
        or []
    )

    if not animes:

        markup.add(
            types.InlineKeyboardButton(
                "❌ Hozircha animelar yo'q",
                callback_data="none"
            )
        )

        if action_type in [
            "add_part",
            "admin_opt",
            "edit_folder"
        ]:

            markup.add(
                types.InlineKeyboardButton(
                    "🔙 Orqaga",
                    callback_data="back_to_admin_menu"
                )
            )

        else:

            markup.add(
                types.InlineKeyboardButton(
                    "🔙 Asosiy menyu",
                    callback_data="back_to_main"
                )
            )

        return markup

    items_per_page = 15

    total_pages = (
        len(animes) + items_per_page - 1
    ) // items_per_page

    page = max(
        1,
        min(page, total_pages)
    )

    start_idx = (
        page - 1
    ) * items_per_page

    end_idx = start_idx + items_per_page

    current_animes = animes[
        start_idx:end_idx
    ]

    for anime_id, name in current_animes:

        result = execute_query(
            """
            SELECT COUNT(*)
            FROM parts
            WHERE anime_id = ?
            """,
            (anime_id,),
            fetchone=True
        )

        parts_count = (
            result[0]
            if result
            else 0
        )

        btn_text = (
            f"📁 {name} "
            f"({parts_count}-qism)"
        )

        if action_type == "add_part":

            callback = (
                f"select_anime_for_part_{anime_id}"
            )

        elif action_type == "admin_opt":

            callback = (
                f"admin_anime_opt_{anime_id}"
            )

        elif action_type == "edit_folder":

            callback = (
                f"select_edit_folder_{anime_id}"
            )

        else:

            callback = (
                f"show_anime_{anime_id}"
            )

        markup.add(
            types.InlineKeyboardButton(
                btn_text,
                callback_data=callback
            )
        )

    nav_buttons = []

    if page > 1:

        nav_buttons.append(
            types.InlineKeyboardButton(
                "◀️",
                callback_data=(
                    f"menu_available_page_{page - 1}"
                )
            )
        )

    nav_buttons.append(
        types.InlineKeyboardButton(
            f"{page}/{total_pages}",
            callback_data="none"
        )
    )

    if page < total_pages:

        nav_buttons.append(
            types.InlineKeyboardButton(
                "▶️",
                callback_data=(
                    f"menu_available_page_{page + 1}"
                )
            )
        )

    markup.row(
        *nav_buttons
    )

    if action_type in [
        "add_part",
        "admin_opt",
        "edit_folder"
    ]:

        markup.add(
            types.InlineKeyboardButton(
                "🔙 Orqaga",
                callback_data="back_to_admin_menu"
            )
        )

    else:

        markup.add(
            types.InlineKeyboardButton(
                "🔙 Asosiy menyu",
                callback_data="back_to_main"
            )
        )

    return markup


# =========================================================
# RECOMMENDED
# =========================================================

def get_recommended_animes_keyboard():

    markup = types.InlineKeyboardMarkup(
        row_width=1
    )

    animes = (
        execute_query(
            """
            SELECT id, name, views
            FROM animes
            ORDER BY views DESC
            LIMIT 10
            """,
            fetchall=True
        )
        or []
    )

    if not animes:

        markup.add(
            types.InlineKeyboardButton(
                "❌ Hozircha animelar yo'q",
                callback_data="none"
            )
        )

        markup.add(
            types.InlineKeyboardButton(
                "🔙 Asosiy menyu",
                callback_data="back_to_main"
            )
        )

        return markup

    for rank, (
        anime_id,
        name,
        views
    ) in enumerate(
        animes,
        start=1
    ):

        markup.add(
            types.InlineKeyboardButton(
                f"#{rank}. 🎬 {name} - "
                f"{views} marta ko'rilgan",
                callback_data=(
                    f"show_anime_{anime_id}"
                )
            )
        )

    markup.add(
        types.InlineKeyboardButton(
            "🔙 Asosiy menyu",
            callback_data="back_to_main"
        )
    )

    return markup


# =========================================================
# ANIME PARTS
# =========================================================

def get_anime_folder_keyboard(
    anime_id,
    page=1
):

    markup = types.InlineKeyboardMarkup(
        row_width=6
    )

    parts_res = (
        execute_query(
            """
            SELECT part_num
            FROM parts
            WHERE anime_id = ?
            ORDER BY part_num ASC
            """,
            (anime_id,),
            fetchall=True
        )
        or []
    )

    parts = [
        row[0]
        for row in parts_res
    ]

    if not parts:

        markup.add(
            types.InlineKeyboardButton(
                "❌ Hozircha qismlar mavjud emas",
                callback_data="none"
            )
        )

        markup.add(
            types.InlineKeyboardButton(
                "🔙 Asosiy menyu",
                callback_data="back_to_main"
            )
        )

        return markup

    items_per_page = 18

    total_pages = (
        len(parts) + items_per_page - 1
    ) // items_per_page

    page = max(
        1,
        min(page, total_pages)
    )

    start_idx = (
        page - 1
    ) * items_per_page

    end_idx = start_idx + items_per_page

    current_parts = parts[
        start_idx:end_idx
    ]

    buttons = []

    for part_num in current_parts:

        buttons.append(
            types.InlineKeyboardButton(
                str(part_num),
                callback_data=(
                    f"get_part_{anime_id}_{part_num}"
                )
            )
        )

    if buttons:
        markup.add(
            *buttons
        )

    nav_buttons = []

    if page > 1:

        nav_buttons.append(
            types.InlineKeyboardButton(
                "⬅️",
                callback_data=(
                    f"page_{anime_id}_{page - 1}"
                )
            )
        )

    nav_buttons.append(
        types.InlineKeyboardButton(
            "❌",
            callback_data="none"
        )
    )

    if page < total_pages:

        nav_buttons.append(
            types.InlineKeyboardButton(
                "➡️",
                callback_data=(
                    f"page_{anime_id}_{page + 1}"
                )
            )
        )

    markup.row(
        *nav_buttons
    )

    markup.add(
        types.InlineKeyboardButton(
            "🔙 Asosiy menyu",
            callback_data="back_to_main"
        )
    )

    return markup


# =========================================================
# ANIME TEXT
# =========================================================

def format_anime_text(
    anime_data,
    bot_username=""
):

    (
        name,
        sub_name,
        hidden_name,
        info,
        views,
        code,
        episodes_count,
        status,
        quality,
        genre,
        channel_name
    ) = anime_data

    bot_link = (
        f"https://t.me/{bot_username}"
        f"?start=anime_{code}"
    )

    formatted_text = (
        f"<i>{name}</i>\n\n"
        f"┣ 🎬 <b>Qism: {episodes_count}</b>\n"
        f"┣ 🌐 <b>Holati: {status}</b>\n"
        f"┣ 💻 <b>Sifat: {quality}</b>\n"
        f"┣ 🎭 <b>Janrlari: {genre}</b>\n"
        f"┗ 📢 <b>Kanal: {channel_name}</b>\n\n"
        f"🔥 <b>Botimiz: @{bot_username}</b>\n"
        f"🔥 <b>Anime ID: "
        f"<tg-spoiler>{code}</tg-spoiler></b>\n"
        f"🔥 <b>Reyting: / 5</b>\n"
        f"🔥 <b>Link:</b> "
        f"<code>{bot_link}</code>"
    )

    return formatted_text


# =========================================================
# START
# =========================================================

@bot.message_handler(commands=["start"])
def send_start(message):

    user_id = message.from_user.id

    user_states.pop(
        user_id,
        None
    )

    temp_data.pop(
        user_id,
        None
    )

    # Foydalanuvchini saqlash
    execute_query(
        """
        INSERT INTO users (user_id)
        VALUES (?)
        """,
        (user_id,),
        commit=True
    )

    args = message.text.split()

    # Deep link
    if (
        len(args) > 1
        and args[1].startswith("anime_")
    ):

        try:

            code = args[1].split(
                "_",
                1
            )[1]

            anime = execute_query(
                """
                SELECT
                    id,
                    name,
                    sub_name,
                    hidden_name,
                    info,
                    views,
                    code,
                    episodes_count,
                    status,
                    quality,
                    genre,
                    channel_name,
                    photo
                FROM animes
                WHERE code = ?
                """,
                (code,),
                fetchone=True
            )

            if anime:

                anime_id = anime[0]

                execute_query(
                    """
                    UPDATE animes
                    SET views = views + 1
                    WHERE id = ?
                    """,
                    (anime_id,),
                    commit=True
                )

                markup = (
                    types.InlineKeyboardMarkup(
                        row_width=1
                    )
                )

                markup.add(
                    types.InlineKeyboardButton(
                        "✨ TOMOSHA QILISH ✨",
                        callback_data=(
                            f"watch_anime_{anime_id}"
                        )
                    )
                )

                bot_username = (
                    bot.get_me().username
                )

                anime_data = anime[1:12]

                text = format_anime_text(
                    anime_data,
                    bot_username
                )

                photo = anime[12]

                if photo:

                    bot.send_photo(
                        message.chat.id,
                        photo,
                        caption=text,
                        reply_markup=markup,
                        parse_mode="HTML",
                        protect_content=True
                    )

                else:

                    bot.send_message(
                        message.chat.id,
                        text,
                        reply_markup=markup,
                        parse_mode="HTML",
                        protect_content=True
                    )

                return

        except Exception as e:

            print(
                f"Deep link xatoligi: {e}"
            )

    # Obuna
    sub_res = check_sub(
        user_id
    )

    if sub_res != True:

        markup = get_sub_keyboard(
            sub_res
        )

        bot.send_message(
            message.chat.id,
            "⚠️ Botdan foydalanish uchun "
            "quyidagi kanallarga obuna "
            "bo'lishingiz kerak:",
            reply_markup=markup
        )

        return

    markup = get_main_inline_menu(
        user_id
    )

    bot.send_message(
        message.chat.id,
        "🏠 **Asosiy menyu**\n\n"
        "Kerakli bo'limni tanlang:",
        reply_markup=markup,
        parse_mode="Markdown"
    )


# =========================================================
# /ANIME
# =========================================================

@bot.message_handler(commands=["anime"])
def cmd_anime(message):

    user_id = message.from_user.id

    user_states.pop(
        user_id,
        None
    )

    temp_data.pop(
        user_id,
        None
    )

    sub_res = check_sub(
        user_id
    )

    if sub_res != True:

        bot.send_message(
            message.chat.id,
            "⚠️ Botdan foydalanish uchun "
            "quyidagi kanallarga obuna "
            "bo'lishingiz kerak:",
            reply_markup=get_sub_keyboard(
                sub_res
            )
        )

        return

    bot.send_message(
        message.chat.id,
        "🔍 **Anime qidirish usulini tanlang:**",
        reply_markup=get_search_inline_keyboard(),
        parse_mode="Markdown"
    )


# =========================================================
# /ANIMEKOD
# =========================================================

@bot.message_handler(commands=["animekod"])
def cmd_animekod(message):

    args = message.text.split()

    if len(args) < 2:

        bot.reply_to(
            message,
            "⚠️ Iltimos, kodni kiriting! "
            "Masalan: <code>/animekod 1</code>",
            parse_mode="HTML"
        )

        return

    code = args[1].strip()

    anime = execute_query(
        """
        SELECT
            id,
            name,
            sub_name,
            hidden_name,
            info,
            views,
            code,
            episodes_count,
            status,
            quality,
            genre,
            channel_name,
            photo
        FROM animes
        WHERE code = ?
        """,
        (code,),
        fetchone=True
    )

    if not anime:

        bot.reply_to(
            message,
            "❌ Bu kod bo'yicha hech qanday "
            "anime topilmadi."
        )

        return

    anime_id = anime[0]

    execute_query(
        """
        UPDATE animes
        SET views = views + 1
        WHERE id = ?
        """,
        (anime_id,),
        commit=True
    )

    bot_username = bot.get_me().username

    anime_data = anime[1:12]

    text = format_anime_text(
        anime_data,
        bot_username
    )

    photo = anime[12]

    markup = types.InlineKeyboardMarkup(
        row_width=1
    )

    markup.add(
        types.InlineKeyboardButton(
            "✨ YUKLAB OLISH ✨",
            url=(
                f"https://t.me/"
                f"{bot_username}"
                f"?start=anime_{code}"
            )
        )
    )

    if photo:

        bot.send_photo(
            message.chat.id,
            photo,
            caption=text,
            reply_markup=markup,
            parse_mode="HTML"
        )

    else:

        bot.send_message(
            message.chat.id,
            text,
            reply_markup=markup,
            parse_mode="HTML"
        )


# =========================================================
# CALLBACK HANDLER
# =========================================================

@bot.callback_query_handler(
    func=lambda call: True
)
def callback_handler(call):

    user_id = call.from_user.id

    chat_id = call.message.chat.id

    data = call.data

    # -----------------------------------------------------
    # EMPTY BUTTON
    # -----------------------------------------------------

    if data == "none":

        bot.answer_callback_query(
            call.id
        )

        return

    # -----------------------------------------------------
    # SUBSCRIPTION
    # -----------------------------------------------------

    if data == "check_subscription":

        sub_res = check_sub(
            user_id
        )

        if sub_res == True:

            bot.answer_callback_query(
                call.id,
                "✅ Obuna tasdiqlandi!"
            )

            try:
                bot.delete_message(
                    chat_id,
                    call.message.message_id
                )
            except Exception:
                pass

            bot.send_message(
                chat_id,
                "🏠 **Asosiy menyu**\n\n"
                "Kerakli bo'limni tanlang:",
                reply_markup=get_main_inline_menu(
                    user_id
                ),
                parse_mode="Markdown"
            )

        else:

            bot.answer_callback_query(
                call.id,
                "❌ Siz hali barcha "
                "kanallarga obuna bo'lmagansiz!",
                show_alert=True
            )

        return

    # -----------------------------------------------------
    # SUBSCRIPTION GUARD
    # -----------------------------------------------------

    sub_res = check_sub(
        user_id
    )

    if sub_res != True:

        try:

            bot.edit_message_text(
                "⚠️ Botdan foydalanish uchun "
                "quyidagi kanallarga obuna "
                "bo'lishingiz kerak:",
                chat_id,
                call.message.message_id,
                reply_markup=get_sub_keyboard(
                    sub_res
                )
            )

        except Exception:
            pass

        return

    # -----------------------------------------------------
    # BACK TO MAIN
    # -----------------------------------------------------

    if data == "back_to_main":

        user_states.pop(
            user_id,
            None
        )

        temp_data.pop(
            user_id,
            None
        )

        bot.answer_callback_query(
            call.id
        )

        try:
            bot.delete_message(
                chat_id,
                call.message.message_id
            )
        except Exception:
            pass

        bot.send_message(
            chat_id,
            "🏠 **Asosiy menyu**\n\n"
            "Kerakli bo'limni tanlang:",
            reply_markup=get_main_inline_menu(
                user_id
            ),
          parse_mode="Markdown"
    )
    return


# ============================================================
# ADMIN MENU
# ============================================================

    if data == "back_to_admin_menu":
        user_states.pop(user_id, None)
        temp_data.pop(user_id, None)

        bot.answer_callback_query(call.id)

        try:
            bot.edit_message_text(
                "🏠 **Asosiy menyu**\n\nKerakli bo'limni tanlang:",
                chat_id,
                call.message.message_id,
                reply_markup=get_main_inline_menu(user_id),
                parse_mode="Markdown"
            )
        except Exception:
            pass


    elif data == "menu_search":
        bot.answer_callback_query(call.id)

        try:
            bot.edit_message_text(
                "🔍 **Anime qidirish usulini tanlang:**",
                chat_id,
                call.message.message_id,
                reply_markup=get_search_inline_keyboard(),
                parse_mode="Markdown"
            )
        except Exception:
            pass


    elif data == "menu_recommended":
        bot.answer_callback_query(call.id)

        try:
            bot.edit_message_text(
                "🔥 **Tavsiya etiladigan top animelar jadvali:**",
                chat_id,
                call.message.message_id,
                reply_markup=get_recommended_animes_keyboard(),
                parse_mode="Markdown"
            )
        except Exception:
            pass


    elif data.startswith("menu_available_page_"):
        page = int(data.split("_")[3])

        bot.answer_callback_query(call.id)

        markup = get_available_animes_keyboard(
            page,
            action_type="show"
        )

        try:
            bot.edit_message_text(
                "📁 **Mavjud animelar ro'yxati:**",
                chat_id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode="Markdown"
            )
        except Exception:
            pass


    # ========================================================
    # ANIME KO'RISH
    # ========================================================

    elif data.startswith("show_anime_"):
        anime_id = int(data.split("_")[2])

        bot.answer_callback_query(call.id)

        anime = execute_query(
            """
            SELECT id, name, sub_name, hidden_name, info, views, code,
                   episodes_count, status, quality, genre,
                   channel_name, photo
            FROM animes
            WHERE id = ?
            """,
            (anime_id,),
            fetchone=True
        )

        if anime:
            execute_query(
                "UPDATE animes SET views = views + 1 WHERE id = ?",
                (anime_id,),
                commit=True
            )

            markup = types.InlineKeyboardMarkup(row_width=1)

            markup.add(
                types.InlineKeyboardButton(
                    "✨ TOMOSHA QILISH ✨",
                    callback_data=f"watch_anime_{anime_id}"
                )
            )

            bot_username = bot.get_me().username

            text = format_anime_text(
                anime[1:12],
                bot_username
            )

            photo = anime[12]

            try:
                bot.delete_message(
                    chat_id,
                    call.message.message_id
                )
            except Exception:
                pass

            if photo:
                bot.send_photo(
                    chat_id,
                    photo,
                    caption=text,
                    reply_markup=markup,
                    parse_mode="HTML",
                    protect_content=True
                )
            else:
                bot.send_message(
                    chat_id,
                    text,
                    reply_markup=markup,
                    parse_mode="HTML",
                    protect_content=True
                )


    elif data.startswith("watch_anime_"):
        anime_id = int(data.split("_")[2])

        bot.answer_callback_query(call.id)

        try:
            bot.edit_message_reply_markup(
                chat_id,
                call.message.message_id,
                reply_markup=get_anime_folder_keyboard(
                    anime_id,
                    page=1
                )
            )
        except Exception:
            pass


    elif data.startswith("page_"):
        parts = data.split("_")

        anime_id = int(parts[1])
        page = int(parts[2])

        bot.answer_callback_query(call.id)

        try:
            bot.edit_message_reply_markup(
                chat_id,
                call.message.message_id,
                reply_markup=get_anime_folder_keyboard(
                    anime_id,
                    page=page
                )
            )
        except Exception:
            pass


    elif data.startswith("get_part_"):
        parts = data.split("_")

        anime_id = int(parts[2])
        part_num = int(parts[3])

        bot.answer_callback_query(call.id)

        part = execute_query(
            """
            SELECT video_id
            FROM parts
            WHERE anime_id = ? AND part_num = ?
            """,
            (anime_id, part_num),
            fetchone=True
        )

        if part and part[0]:
            try:
                bot.send_video(
                    chat_id,
                    part[0],
                    caption=f"{part_num}-qism",
                    protect_content=True
                )
            except Exception:
                bot.send_message(
                    chat_id,
                    f"❌ {part_num}-qism videosini yuborishda xatolik yuz berdi."
                )
        else:
            bot.answer_callback_query(
                call.id,
                "❌ Bu qism topilmadi!",
                show_alert=True
            )


    # ========================================================
    # QIDIRUV
    # ========================================================

    elif data == "search_by_name":
        bot.answer_callback_query(call.id)

        user_states[user_id] = "WAITING_SEARCH_NAME"

        markup = types.InlineKeyboardMarkup()

        markup.add(
            types.InlineKeyboardButton(
                "🔙 Orqaga",
                callback_data="menu_search"
            )
        )

        try:
            bot.edit_message_text(
                "🔤 Qidirilayotgan anime nomini "
                "(yoki kalit so'zni) kiriting:",
                chat_id,
                call.message.message_id,
                reply_markup=markup
            )
        except Exception:
            pass


    elif data == "search_by_code":
        bot.answer_callback_query(call.id)

        user_states[user_id] = "WAITING_SEARCH_CODE"

        markup = types.InlineKeyboardMarkup()

        markup.add(
            types.InlineKeyboardButton(
                "🔙 Orqaga",
                callback_data="menu_search"
            )
        )

        try:
            bot.edit_message_text(
                "🔢 Qidirilayotgan anime kodini kiriting:",
                chat_id,
                call.message.message_id,
                reply_markup=markup
            )
        except Exception:
            pass


    # ========================================================
    # ADMIN - ANIME QO'SHISH
    # ========================================================

    elif data == "admin_add_folder" and user_id == ADMIN_ID:

        bot.answer_callback_query(call.id)

        user_states[user_id] = "ADD_NAME"
        temp_data[user_id] = {}

        try:
            bot.delete_message(
                chat_id,
                call.message.message_id
            )
        except Exception:
            pass

        markup = types.InlineKeyboardMarkup()

        markup.add(
            types.InlineKeyboardButton(
                "🔙 Orqaga",
                callback_data="back_to_admin_menu"
            )
        )

        bot.send_message(
            chat_id,
            "🎬 **Animening asosiy nomini kiriting:**",
            reply_markup=markup,
            parse_mode="Markdown"
        )


    # ========================================================
    # ADMIN - QISM QO'SHISH
    # ========================================================

    elif data == "admin_add_part" and user_id == ADMIN_ID:

        bot.answer_callback_query(call.id)

        try:
            bot.edit_message_text(
                "📁 Qaysi animega qism qo'shmoqchisiz? "
                "Animeni tanlang:",
                chat_id,
                call.message.message_id,
                reply_markup=get_available_animes_keyboard(
                    page=1,
                    action_type="add_part"
                )
            )
        except Exception:
            pass


    elif data.startswith("select_anime_for_part_") and user_id == ADMIN_ID:

        anime_id = int(data.split("_")[4])

        bot.answer_callback_query(call.id)

        last_part_res = execute_query(
            """
            SELECT MAX(part_num)
            FROM parts
            WHERE anime_id = ?
            """,
            (anime_id,),
            fetchone=True
        )

        max_part = (
            last_part_res[0]
            if last_part_res and last_part_res[0] is not None
            else 0
        )

        next_part_num = max_part + 1

        user_states[user_id] = "ADD_PART_VIDEO"

        temp_data[user_id] = {
            "anime_id": anime_id,
            "next_part_num": next_part_num
        }

        try:
            bot.delete_message(
                chat_id,
                call.message.message_id
            )
        except Exception:
            pass

        markup = types.InlineKeyboardMarkup(row_width=1)

        markup.add(
            types.InlineKeyboardButton(
                "✅ Tamom",
                callback_data="finish_adding_parts"
            ),
            types.InlineKeyboardButton(
                "🔙 Orqaga",
                callback_data="admin_add_part"
            )
        )

        bot.send_message(
            chat_id,
            f"🎥 Tanlangan anime uchun navbatdagi qism: "
            f"**{next_part_num}-qism**.\n\n"
            f"Videoni yuboring:",
            reply_markup=markup,
            parse_mode="Markdown"
        )


    elif data == "finish_adding_parts" and user_id == ADMIN_ID:

        bot.answer_callback_query(
            call.id,
            "✅ Qismlarni qo'shish yakunlandi!"
        )

        user_states.pop(user_id, None)
        temp_data.pop(user_id, None)

        try:
            bot.delete_message(
                chat_id,
                call.message.message_id
            )
        except Exception:
            pass

        bot.send_message(
            chat_id,
            "🏠 **Asosiy menyu**\n\nKerakli bo'limni tanlang:",
            reply_markup=get_main_inline_menu(user_id),
            parse_mode="Markdown"
        )


    # ========================================================
    # ADMIN - TAHRIRLASH
    # ========================================================

    elif data == "admin_edit_menu" and user_id == ADMIN_ID:

        bot.answer_callback_query(call.id)

        try:
            bot.edit_message_text(
                "✏️ Tahrirlash uchun animeni tanlang:",
                chat_id,
                call.message.message_id,
                reply_markup=get_available_animes_keyboard(
                    page=1,
                    action_type="edit_folder"
                )
            )
        except Exception:
            pass


    elif data.startswith("select_edit_folder_") and user_id == ADMIN_ID:

        anime_id = int(data.split("_")[3])

        bot.answer_callback_query(call.id)

        anime = execute_query(
            "SELECT name FROM animes WHERE id = ?",
            (anime_id,),
            fetchone=True
        )

        anime_name = anime[0] if anime else "Anime"

        markup = types.InlineKeyboardMarkup()

        markup.add(
            types.InlineKeyboardButton(
                "🔙 Orqaga",
                callback_data="admin_edit_menu"
            )
        )

        try:
            bot.edit_message_text(
                f"✏️ **{anime_name}** tanlandi.",
                chat_id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode="Markdown"
            )
        except Exception:
            pass


    # ========================================================
    # ADMIN - KANALLAR
    # ========================================================

    elif data == "admin_channels" and user_id == ADMIN_ID:

        bot.answer_callback_query(call.id)

        rows = execute_query(
            "SELECT username FROM channels",
            fetchall=True
        )

        ch_list = (
            "\n".join([r[0] for r in rows])
            if rows
            else "Hozircha kanallar yo'q."
        )

        markup = types.InlineKeyboardMarkup(row_width=1)

        markup.add(
            types.InlineKeyboardButton(
                "➕ Kanal qo'shish",
                callback_data="admin_add_channel"
            ),
            types.InlineKeyboardButton(
                "🗑 Kanalni o'chirish",
                callback_data="admin_del_channel"
            ),
            types.InlineKeyboardButton(
                "🔙 Orqaga",
                callback_data="back_to_admin_menu"
            )
        )

        try:
            bot.edit_message_text(
                f"📢 **Majburiy obuna kanallari:**\n\n{ch_list}",
                chat_id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode="Markdown"
            )
        except Exception:
            pass


    elif data == "admin_add_channel" and user_id == ADMIN_ID:

        bot.answer_callback_query(call.id)

        user_states[user_id] = "ADD_CHANNEL_NAME"

        try:
            bot.delete_message(
                chat_id,
                call.message.message_id
            )
        except Exception:
            pass

        markup = types.InlineKeyboardMarkup()

        markup.add(
            types.InlineKeyboardButton(
                "🔙 Orqaga",
                callback_data="admin_channels"
            )
        )

        bot.send_message(
            chat_id,
            "📢 Qo'shiladigan kanal username'ini yuboring "
            "(Masalan: @AnimeKanal):",
            reply_markup=markup
        )


    elif data == "admin_del_channel" and user_id == ADMIN_ID:

        bot.answer_callback_query(call.id)

        user_states[user_id] = "DEL_CHANNEL_NAME"

        try:
            bot.delete_message(
                chat_id,
                call.message.message_id
            )
        except Exception:
            pass

        markup = types.InlineKeyboardMarkup()

        markup.add(
            types.InlineKeyboardButton(
                "🔙 Orqaga",
                callback_data="admin_channels"
            )
        )

        bot.send_message(
            chat_id,
            "🗑 O'chiriladigan kanal username'ini yuboring "
            "(Masalan: @AnimeKanal):",
            reply_markup=markup
        )


    # ========================================================
    # ADMIN - STATISTIKA
    # ========================================================

    elif data == "admin_stats" and user_id == ADMIN_ID:

        bot.answer_callback_query(call.id)

        users_count = execute_query(
            "SELECT COUNT(*) FROM users",
            fetchone=True
        )[0] or 0

        animes_count = execute_query(
            "SELECT COUNT(*) FROM animes",
            fetchone=True
        )[0] or 0

        parts_count = execute_query(
            "SELECT COUNT(*) FROM parts",
            fetchone=True
        )[0] or 0

        top_viewed = execute_query(
            """
            SELECT name, views
            FROM animes
            ORDER BY views DESC
            LIMIT 3
            """,
            fetchall=True
        ) or []

        top_viewed_text = (
            "\n".join(
                [
                    f"• {row[0]} — {row[1]} marta"
                    for row in top_viewed
                ]
            )
            or "Ma'lumot yo'q"
        )

        oldest_animes = execute_query(
            """
            SELECT name
            FROM animes
            ORDER BY id ASC
            LIMIT 3
            """,
            fetchall=True
        ) or []

        oldest_text = (
            "\n".join(
                [
                    f"• {row[0]}"
                    for row in oldest_animes
                ]
            )
            or "Ma'lumot yo'q"
        )

        text = (
            f"📊 **Botning statistikasi:**\n\n"
            f"👥 **Foydalanuvchilar:** {users_count} ta\n"
            f"🎬 **Animelar:** {animes_count} ta\n"
            f"📁 **Qismlar:** {parts_count} ta\n\n"
            f"🔥 **Top 3 anime:**\n"
            f"{top_viewed_text}\n\n"
            f"📌 **Birinchilar:**\n"
            f"{oldest_text}"
        )

        markup = types.InlineKeyboardMarkup()

        markup.add(
            types.InlineKeyboardButton(
                "🔙 Orqaga",
                callback_data="back_to_admin_menu"
            )
        )

        try:
            bot.edit_message_text(
                text,
                chat_id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode="Markdown"
            )
        except Exception:
            pass


    # ========================================================
    # ADMIN - BOSHQARISH
    # ========================================================

    elif data == "admin_manage" and user_id == ADMIN_ID:

        bot.answer_callback_query(call.id)

        try:
            bot.edit_message_text(
                "🗑 Boshqarish yoki qismini o'chirish "
                "uchun animeni tanlang:",
                chat_id,
                call.message.message_id,
                reply_markup=get_available_animes_keyboard(
                    page=1,
                    action_type="admin_opt"
                )
            )
        except Exception:
            pass


    elif data.startswith("admin_anime_opt_") and user_id == ADMIN_ID:

        anime_id = int(data.split("_")[3])

        bot.answer_callback_query(call.id)

        parts_res = execute_query(
            """
            SELECT part_num
            FROM parts
            WHERE anime_id = ?
            ORDER BY part_num ASC
            """,
            (anime_id,),
            fetchall=True
        ) or []

        parts = [row[0] for row in parts_res]

        markup = types.InlineKeyboardMarkup(row_width=6)

        buttons = [
            types.InlineKeyboardButton(
                f"❌ {p}",
                callback_data=f"del_part_{anime_id}_{p}"
            )
            for p in parts
        ]

        if buttons:
            markup.add(*buttons)

        markup.add(
            types.InlineKeyboardButton(
                "🗑 Animeni to'liq o'chirish",
                callback_data=f"confirm_del_anime_{anime_id}"
            ),
            types.InlineKeyboardButton(
                "🔙 Orqaga",
                callback_data="admin_manage"
            )
        )

        anime = execute_query(
            "SELECT name FROM animes WHERE id = ?",
            (anime_id,),
            fetchone=True
        )

        anime_name = anime[0] if anime else "Anime"

        try:
            bot.edit_message_text(
                f"⚙ **{anime_name}** bo'yicha "
                f"qismni o'chiring yoki animeni to'liq o'chiring:",
                chat_id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode="Markdown"
            )
        except Exception:
            pass


    # ========================================================
    # QISMNI O'CHIRISH
    # ========================================================

    elif data.startswith("del_part_") and user_id == ADMIN_ID:

        parts_data = data.split("_")

        anime_id = int(parts_data[2])
        part_num = int(parts_data[3])

        bot.answer_callback_query(call.id)

        execute_query(
            """
            DELETE FROM parts
            WHERE anime_id = ? AND part_num = ?
            """,
            (anime_id, part_num),
            commit=True
        )

        markup = types.InlineKeyboardMarkup(row_width=1)

        markup.add(
            types.InlineKeyboardButton(
                "➕ O'rniga video qo'shish",
                callback_data=f"replace_part_{anime_id}_{part_num}"
            ),
            types.InlineKeyboardButton(
                "📭 Orqaga",
                callback_data="admin_manage"
            )
        )

        try:
            bot.edit_message_text(
                f"✅ **{part_num}-qism** o'chirildi.",
                chat_id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode="Markdown"
            )
        except Exception:
            pass


    # ========================================================
    # QISMNI ALMASHTIRISH
    # ========================================================

    elif data.startswith("replace_part_") and user_id == ADMIN_ID:

        parts_data = data.split("_")

        anime_id = int(parts_data[2])
        part_num = int(parts_data[3])

        bot.answer_callback_query(call.id)

        user_states[user_id] = "REPLACE_PART_VIDEO"

        temp_data[user_id] = {
            "anime_id": anime_id,
            "part_num": part_num
        }

        try:
            bot.delete_message(
                chat_id,
                call.message.message_id
            )
        except Exception:
            pass

        bot.send_message(
            chat_id,
            f"🎥 **{part_num}-qism** o'rniga "
            f"yangi videoni yuboring:",
            parse_mode="Markdown"
        )


    # ========================================================
    # ANIMENI TO'LIQ O'CHIRISH
    # ========================================================

    elif data.startswith("confirm_del_anime_") and user_id == ADMIN_ID:

        anime_id = int(data.split("_")[3])

        bot.answer_callback_query(call.id)

        execute_query(
            "DELETE FROM parts WHERE anime_id = ?",
            (anime_id,),
            commit=True
        )

        execute_query(
            "DELETE FROM animes WHERE id = ?",
            (anime_id,),
            commit=True
        )

        markup = types.InlineKeyboardMarkup()

        markup.add(
            types.InlineKeyboardButton(
                "🔙 Orqaga",
                callback_data="admin_manage"
            )
        )

        try:
            bot.edit_message_text(
                "✅ Anime va uning qismlari o'chirib yuborildi!",
                chat_id,
                call.message.message_id,
                reply_markup=markup
            )
        except Exception:
            pass


# ============================================================
# XABARLARNI QABUL QILISH
# ============================================================

@bot.message_handler(
    content_types=["text", "photo", "video"]
)
def handle_messages(message):

    if message.chat.type != "private":
        return

    user_id = message.from_user.id
    chat_id = message.chat.id

    state = user_states.get(user_id)

    if not state:
        return

    # --------------------------------------------------------
    # BUYRUQLARNI BU HANDLERDA QAYTA ISHLAMAYMIZ
    # --------------------------------------------------------

    if message.text and message.text.startswith("/"):
        return

    text = message.text.strip() if message.text else ""


    # ========================================================
    # QIDIRUV - NOM BO'YICHA
    # ========================================================

    if state == "WAITING_SEARCH_NAME":

        query = text.lower()

        if not query:
            bot.send_message(
                chat_id,
                "⚠️ Anime nomini kiriting."
            )
            return

        is_postgres = DATABASE_URL and psycopg2

        animes = execute_query(
            """
            SELECT id, name
            FROM animes
            WHERE LOWER(name) LIKE ?
               OR LOWER(sub_name) LIKE ?
               OR LOWER(hidden_name) LIKE ?
            ORDER BY id DESC
            """,
            (
                f"%{query}%",
                f"%{query}%",
                f"%{query}%"
            ),
            fetchall=True
        ) or []

        if not animes:
            bot.send_message(
                chat_id,
                "❌ Hech qanday anime topilmadi."
            )
            return

        markup = types.InlineKeyboardMarkup(
            row_width=1
        )

        for anime_id, name in animes:
            markup.add(
                types.InlineKeyboardButton(
                    f"🎬 {name}",
                    callback_data=f"show_anime_{anime_id}"
                )
            )

        bot.send_message(
            chat_id,
            "🔍 **Topilgan animelar:**",
            reply_markup=markup,
            parse_mode="Markdown"
        )

        return


    # ========================================================
    # QIDIRUV - KOD BO'YICHA
    # ========================================================

    if state == "WAITING_SEARCH_CODE":

        user_states.pop(user_id, None)

        anime = execute_query(
            """
            SELECT id, name, sub_name, hidden_name, info, views, code,
                   episodes_count, status, quality, genre,
                   channel_name, photo
            FROM animes
            WHERE code = ?
            """,
            (text,),
            fetchone=True
        )

        if not anime:
            bot.send_message(
                chat_id,
                "❌ Bu kod bo'yicha hech qanday anime topilmadi."
            )
            return

        anime_id = anime[0]

        execute_query(
            "UPDATE animes SET views = views + 1 WHERE id = ?",
            (anime_id,),
            commit=True
        )

        markup = types.InlineKeyboardMarkup(row_width=1)

        markup.add(
            types.InlineKeyboardButton(
                "✨ TOMOSHA QILISH ✨",
                callback_data=f"watch_anime_{anime_id}"
            )
        )

        bot_username = bot.get_me().username

        formatted_text = format_anime_text(
            anime[1:12],
            bot_username
        )

        photo = anime[12]

        if photo:
            bot.send_photo(
                chat_id,
                photo,
                caption=formatted_text,
                reply_markup=markup,
                parse_mode="HTML",
                protect_content=True
            )
        else:
            bot.send_message(
                chat_id,
                formatted_text,
                reply_markup=markup,
                parse_mode="HTML",
                protect_content=True
            )

        return


    # ========================================================
    # ADMIN - ANIME ASOSIY NOMI
    # ========================================================

    if user_id == ADMIN_ID and state == "ADD_NAME":

        if not text:
            bot.send_message(
                chat_id,
                "⚠️ Anime nomi bo'sh bo'lmasligi kerak. "
                "Qaytadan kiriting:"
            )
            return

        temp_data.setdefault(user_id, {})

        temp_data[user_id]["name"] = text

        user_states[user_id] = "ADD_SUB_NAME"

        bot.send_message(
            chat_id,
            "🏷 **Animening qo'shimcha nomini kiriting:**",
            parse_mode="Markdown"
        )

        return


    # ========================================================
    # ADMIN - QO'SHIMCHA NOM
    # ========================================================

    if user_id == ADMIN_ID and state == "ADD_SUB_NAME":

        temp_data.setdefault(user_id, {})

        temp_data[user_id]["sub_name"] = text

        user_states[user_id] = "ADD_HIDDEN_NAME"

        bot.send_message(
            chat_id,
            "🔑 **Yashirin nomlarini "
            "(kalit so'zlar) kiriting:**",
            parse_mode="Markdown"
        )

        return


    # ========================================================
    # ADMIN - YASHIRIN NOM
    # ========================================================

    if user_id == ADMIN_ID and state == "ADD_HIDDEN_NAME":

        temp_data.setdefault(user_id, {})

        temp_data[user_id]["hidden_name"] = text

        user_states[user_id] = "ADD_CODE"

        bot.send_message(
            chat_id,
            "🔢 **Anime kodini kiriting:**",
            parse_mode="Markdown"
        )

        return


    # ========================================================
    # ADMIN - ANIME KODI
    # ========================================================

    if user_id == ADMIN_ID and state == "ADD_CODE":

        if not text:
            bot.send_message(
                chat_id,
                "⚠️ Kod bo'sh bo'lmasligi kerak. "
                "Qaytadan kiriting:"
            )
            return

        temp_data.setdefault(user_id, {})

        temp_data[user_id]["code"] = text

        user_states[user_id] = "ADD_EPISODES"

        bot.send_message(
            chat_id,
            "🎬 **Qism sonini kiriting "
            "(masalan: 12 yoki Tugallangan):**",
            parse_mode="Markdown"
        )

        return


    # ========================================================
    # ADMIN - QISM SONI
    # ========================================================

    if user_id == ADMIN_ID and state == "ADD_EPISODES":

        temp_data.setdefault(user_id, {})

        temp_data[user_id]["episodes_count"] = text

        user_states[user_id] = "ADD_STATUS"

        bot.send_message(
            chat_id,
            "🎬 **Anime statusini kiriting "
            "(masalan: Davom etmoqda yoki Tugallangan):**",
            parse_mode="Markdown"
        )

        return


    # ========================================================
    # ADMIN - STATUS
    # ========================================================

    if user_id == ADMIN_ID and state == "ADD_STATUS":

        temp_data.setdefault(user_id, {})

        temp_data[user_id]["status"] = text

        user_states[user_id] = "ADD_CHANNEL"

        bot.send_message(
            chat_id,
            "📢 **Kanal nomini kiriting "
            "(masalan: @AniRem_Org):**",
            parse_mode="Markdown"
        )

        return


    # ========================================================
    # ADMIN - KANAL NOMI
    # ========================================================

    if user_id == ADMIN_ID and state == "ADD_CHANNEL":

        ch_username = text.strip()

        if ch_username == "/skip":
            ch_username = "@AniRem_Org"

        elif not ch_username.startswith("@"):
            ch_username = "@" + ch_username

        temp_data.setdefault(user_id, {})

        # Anime uchun kanal nomini ham saqlaymiz
        temp_data[user_id]["channel_name"] = ch_username

        # Kanalni majburiy obuna ro'yxatiga qo'shamiz
        execute_query(
            """
            INSERT INTO channels (username)
            VALUES (?)
            ON CONFLICT (username) DO NOTHING
            """
            if (DATABASE_URL and psycopg2)
            else
            """
            INSERT OR IGNORE INTO channels (username)
            VALUES (?)
            """,
            (ch_username,),
            commit=True
        )

        user_states[user_id] = "ADD_INFO"

        bot.send_message(
            chat_id,
            "📖 **Ma'lumot kiriting** "
            "(o'tkazish uchun /skip):",
            parse_mode="Markdown"
        )

        return


    # ========================================================
    # ADMIN - MA'LUMOT
    # ========================================================

    if user_id == ADMIN_ID and state == "ADD_INFO":

        info_text = (
            "Ma'lumot mavjud emas"
            if text == "/skip"
            else text
        )

        temp_data.setdefault(user_id, {})

        temp_data[user_id]["info"] = info_text

        user_states[user_id] = "ADD_PHOTO"

        bot.send_message(
            chat_id,
            "🖼 **Rasm yuboring "
            "(fayl yoki havola):**",
            parse_mode="Markdown"
        )

        return


    # ========================================================
    # ADMIN - KANAL QO'SHISH
    # ========================================================

    if user_id == ADMIN_ID and state == "ADD_CHANNEL_NAME":

        ch_username = text.strip()

        if not ch_username.startswith("@"):
            ch_username = "@" + ch_username

        execute_query(
            """
            INSERT INTO channels (username)
            VALUES (?)
            ON CONFLICT (username) DO NOTHING
            """
            if (DATABASE_URL and psycopg2)
            else
            """
            INSERT OR IGNORE INTO channels (username)
            VALUES (?)
            """,
            (ch_username,),
            commit=True
        )

        user_states.pop(user_id, None)

        bot.send_message(
            chat_id,
            f"✅ Kanal qo'shildi: {ch_username}"
        )

        return


    # ========================================================
    # ADMIN - KANAL O'CHIRISH
    # ========================================================

    if user_id == ADMIN_ID and state == "DEL_CHANNEL_NAME":

        ch_username = text.strip()

        if not ch_username.startswith("@"):
            ch_username = "@" + ch_username

        execute_query(
            "DELETE FROM channels WHERE username = ?",
            (ch_username,),
            commit=True
        )

        user_states.pop(user_id, None)

        bot.send_message(
            chat_id,
            f"🗑 Kanal o'chirildi: {ch_username}"
        )

        return


    # ========================================================
    # ADMIN - RASM QABUL QILISH
    # ========================================================

    if user_id == ADMIN_ID and state == "ADD_PHOTO":

        photo_id = ""

        # Telegram rasmi
        if message.photo:
            photo_id = message.photo[-1].file_id

        # Rasm URL manzili
        elif message.text:
            photo_id = message.text.strip()

        else:
            bot.send_message(
                chat_id,
                "⚠️ Iltimos, rasm yuboring yoki "
                "rasm havolasini yuboring."
            )
            return

        d = temp_data.get(user_id, {})

        if not d.get("name"):
            bot.send_message(
                chat_id,
                "❌ Anime ma'lumotlari topilmadi. "
                "Anime qo'shishni boshidan boshlang."
            )

            user_states.pop(user_id, None)
            temp_data.pop(user_id, None)

            return

        execute_query(
            """
            INSERT INTO animes (
                name,
                sub_name,
                hidden_name,
                code,
                info,
                photo,
                episodes_count,
                status,
                quality,
                genre,
                channel_name,
                views
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                d.get("name"),
                d.get("sub_name", ""),
                d.get("hidden_name", ""),
                d.get("code"),
                d.get(
                    "info",
                    "Ma'lumot kiritilmagan"
                ),
                photo_id,
                d.get(
                    "episodes_count",
                    "Noma'lum"
                ),
                d.get(
                    "status",
                    "Tugallangan"
                ),
                d.get(
                    "quality",
                    "720p, 1080p"
                ),
                d.get(
                    "genre",
                    "Drama, Isekai, fantastik"
                ),
                d.get(
                    "channel_name",
                    "@AniRem_Org"
                ),
                0
            ),
            commit=True
        )

        # Eng oxirgi qo'shilgan animeni olamiz
        last_anime = execute_query(
            """
            SELECT id
            FROM animes
            ORDER BY id DESC
            LIMIT 1
            """,
            fetchone=True
        )

        if not last_anime:
            bot.send_message(
                chat_id,
                "❌ Anime bazaga saqlanmadi. "
                "Database xatosini tekshiring."
            )
            return

        anime_id = last_anime[0]

        user_states[user_id] = "ADD_PART_VIDEO"

        temp_data[user_id] = {
            "anime_id": anime_id,
            "next_part_num": 1
        }

        markup = types.InlineKeyboardMarkup()

        markup.add(
            types.InlineKeyboardButton(
                "✅ Tamom",
                callback_data="finish_adding_parts"
            )
        )

        bot.send_message(
            chat_id,
            "✅ **Anime bazaga qo'shildi!**\n\n"
            "🎬 Endi **1-qismni** yuboring:",
            reply_markup=markup,
            parse_mode="Markdown"
        )

        return


    # ========================================================
    # ADMIN - YANGI QISM QO'SHISH
    # ========================================================

    if user_id == ADMIN_ID and state == "ADD_PART_VIDEO":

        if not message.video:

            bot.send_message(
                chat_id,
                "⚠️ Iltimos, video yuboring.\n\n"
                "Agar qismlarni qo'shishni tugatmoqchi "
                "bo'lsangiz, **✅ Tamom** tugmasini bosing.",
                parse_mode="Markdown"
            )

            return

        video_id = message.video.file_id

        d = temp_data.get(user_id, {})

        anime_id = d.get("anime_id")
        part_num = d.get(
            "next_part_num",
            1
        )

        if not anime_id:
            bot.send_message(
                chat_id,
                "❌ Anime topilmadi. "
                "Qism qo'shishni qaytadan boshlang."
            )

            user_states.pop(user_id, None)
            temp_data.pop(user_id, None)

            return

        execute_query(
            """
            INSERT INTO parts (
                anime_id,
                part_num,
                video_id
            )
            VALUES (?, ?, ?)
            """,
            (
                anime_id,
                part_num,
                video_id
            ),
            commit=True
        )

        next_part = part_num + 1

        temp_data[user_id]["next_part_num"] = next_part

        markup = types.InlineKeyboardMarkup()

        markup.add(
            types.InlineKeyboardButton(
                "✅ Tamom",
                callback_data="finish_adding_parts"
            )
        )

        bot.send_message(
            chat_id,
            f"✅ **{part_num}-qism saqlandi!**\n\n"
            f"🎥 Endi **{next_part}-qismni** yuboring:",
            reply_markup=markup,
            parse_mode="Markdown"
        )

        return


    # ========================================================
    # ADMIN - QISMNI ALMASHTIRISH
    # ========================================================

    if user_id == ADMIN_ID and state == "REPLACE_PART_VIDEO":

        if not message.video:
            bot.send_message(
                chat_id,
                "⚠️ Iltimos, yangi videoni yuboring."
            )
            return

        video_id = message.video.file_id

        d = temp_data.get(user_id, {})

        anime_id = d.get("anime_id")
        part_num = d.get("part_num")

        if not anime_id or not part_num:
            bot.send_message(
                chat_id,
                "❌ Qism ma'lumotlari topilmadi."
            )

            user_states.pop(user_id, None)
            temp_data.pop(user_id, None)

            return

        execute_query(
            """
            INSERT INTO parts (
                anime_id,
                part_num,
                video_id
            )
            VALUES (?, ?, ?)
            """,
            (
                anime_id,
                part_num,
                video_id
            ),
            commit=True
        )

        user_states.pop(user_id, None)
        temp_data.pop(user_id, None)

        markup = types.InlineKeyboardMarkup()

        markup.add(
            types.InlineKeyboardButton(
                "🔙 Boshqarishga qaytish",
                callback_data="admin_manage"
            )
        )

        bot.send_message(
            chat_id,
            f"✅ **{part_num}-qism** o'rniga "
            f"yangi video qo'shildi!",
            reply_markup=markup,
            parse_mode="Markdown"
        )

        return

# ============================================================
# BOTNI ISHGA TUSHIRISH
# ============================================================

if __name__ == "__main__":

    print("Bot ishga tushmoqda...")

    try:
        keep_alive()
    except Exception as e:
        print(f"Web server ishga tushirish xatosi: {e}")

    time.sleep(2)

    while True:

        try:
            bot.remove_webhook()

            time.sleep(1)

            print("Polling boshlandi...")

            bot.infinity_polling(
                skip_pending=True,
                timeout=60,
                long_polling_timeout=60
            )

        except Exception as e:

            print(
                f"Polling xatoligi: {e}"
            )

            time.sleep(5)
