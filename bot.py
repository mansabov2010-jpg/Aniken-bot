import os
import sqlite3
import threading
import time

from flask import Flask
import telebot
from telebot import types

# ============================================================
# SOZLAMALAR
# ============================================================

TOKEN = os.environ.get('BOT_TOKEN', '8987164421:AAHIKjTCtB4781Ns53b3WSHk5xgAWOXTtQ8')
bot = telebot.TeleBot(TOKEN)

# Adminlarning Telegram ID raqamlari
ADMIN_IDS = [7637155944,7986354170]

# ============================================================
# SOZLAMALAR
# ============================================================

TOKEN = os.environ.get('BOT_TOKEN', 'SIZNING_BOT_TOKENINGIZ')
bot = telebot.TeleBot(TOKEN)

# Adminlarning Telegram ID raqamlari
ADMIN_IDS = [123456789]

# ============================================================
# MA'LUMOTLAR BAZASINI YARATISH VA BOSHQARISH
# ============================================================
def init_db():
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    cursor = conn.cursor()
    
    # Foydalanuvchilar va ularning state (holat) lari jadvali
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            state TEXT DEFAULT NULL
        )
    ''')
    
    # Vaqtinchalik wizard (anime qo'shish) ma'lumotlari jadvali
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS temp_anime_data (
            user_id INTEGER PRIMARY KEY,
            channel_name TEXT,
            channel_link TEXT,
            title TEXT,
            hidden_names TEXT,
            code TEXT,
            photo_id TEXT,
            episodes TEXT,
            genre TEXT
        )
    ''')
    
    # Majburiy obuna kanallari jadvali
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS force_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_username TEXT,
            channel_link TEXT
        )
    ''')
    
    # Animelar jadvali
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS animes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_name TEXT,
            channel_link TEXT,
            title TEXT,
            hidden_names TEXT,
            code TEXT UNIQUE,
            photo_id TEXT,
            episodes TEXT,
            genre TEXT,
            description TEXT,
            views INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Bazadan state olish
def get_user_state(user_id):
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT state FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

# Bazaga state yozish
def set_user_state(user_id, state):
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO users (user_id, state) VALUES (?, ?)", (user_id, state))
    conn.commit()
    conn.close()

# Render 24/7 keep-alive Flask server
app = Flask('')

@app.route('/')
def home():
    return "Ani Kenbot ishlamoqda!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run)
    t.daemon = True
    t.start()


# ============================================================
# MAJBURIY OBUNANI TEKSHIRISH
# ============================================================
def check_subscription(user_id):
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT channel_username, channel_link FROM force_channels")
    channels = cursor.fetchall()
    conn.close()
    
    if not channels:
        return True, []
        
    not_subscribed = []
    for ch_username, ch_link in channels:
        try:
            member = bot.get_chat_member(ch_username, user_id)
            if member.status not in ['creator', 'administrator', 'member']:
                not_subscribed.append((ch_username, ch_link))
        except Exception:
            continue
            
    if not_subscribed:
        return False, not_subscribed
    return True, []


# ============================================================
# MENYU TUGMALARI
# ============================================================
def get_admin_markup():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔍 Anime izlash", callback_data="search_menu"),
        types.InlineKeyboardButton("📂 Mavjud animelar", callback_data="anime_list"),
        types.InlineKeyboardButton("🔥 Qaynoq", callback_data="hot_animes"),
        types.InlineKeyboardButton("⏰ Yangi", callback_data="recent_animes"),
        types.InlineKeyboardButton("⭐ Top", callback_data="top_animes"),
        types.InlineKeyboardButton("📢 Kanal qo'shish", callback_data="add_force_channel"),
        types.InlineKeyboardButton("🗑 Kanalni o'chirish", callback_data="del_force_channel"),
        types.InlineKeyboardButton("🎬 Anime qo'shish", callback_data="add_anime"),
        types.InlineKeyboardButton("🗑 Animeni o'chirish", callback_data="del_anime_menu"),
        types.InlineKeyboardButton("📤 Xabar yuborish", callback_data="admin_broadcast"),
        types.InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")
    )
    return markup


def get_user_markup():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔍 Anime izlash", callback_data="search_menu"),
        types.InlineKeyboardButton("📂 Mavjud animelar", callback_data="anime_list"),
        types.InlineKeyboardButton("🔥 Qaynoq", callback_data="hot_animes"),
        types.InlineKeyboardButton("⏰ Yangi", callback_data="recent_animes"),
        types.InlineKeyboardButton("⭐ Top", callback_data="top_animes")
    )
    return markup


# ============================================================
# /START BUYrug'i
# ============================================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    set_user_state(user_id, None)
    
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, state) VALUES (?, NULL)", (user_id,))
    conn.commit()
    conn.close()
    
    if user_id not in ADMIN_IDS:
        is_sub, unsubs = check_subscription(user_id)
        if not is_sub:
            markup = types.InlineKeyboardMarkup(row_width=1)
            for ch_username, ch_link in unsubs:
                markup.add(types.InlineKeyboardButton(f"📢 Kanalga obuna bo'lish", url=ch_link))
            markup.add(types.InlineKeyboardButton("🔄 Obunani tekshirish", callback_data="check_sub"))
            
            bot.send_message(message.chat.id, 
                             "⚠️ **Diqqat!** Botdan foydalanish uchun quyidagi kanalga obuna bo'lishingiz shart:", 
                             reply_markup=markup, parse_mode="Markdown")
            return

    if user_id in ADMIN_IDS:
        bot.send_message(message.chat.id, "👑 **Admin boshqaruv paneli:**", reply_markup=get_admin_markup(), parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, "✨ **Asosiy menyu:**", reply_markup=get_user_markup(), parse_mode="Markdown")


# ============================================================
# CALLBACK TUGMALAR
# ============================================================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    
    if call.data == "check_sub":
        is_sub, _ = check_subscription(user_id)
        if not is_sub:
            bot.answer_callback_query(call.id, "❌ Siz hali hamma kanallarga obuna bo'lmadingiz!", show_alert=True)
            return
        bot.answer_callback_query(call.id, "✅ Muvaffaqiyatli obuna bo'ldingiz!")
        
        if user_id in ADMIN_IDS:
            bot.edit_message_text("👑 **Admin boshqaruv paneli:**", call.message.chat.id, call.message.message_id, reply_markup=get_admin_markup(), parse_mode="Markdown")
        else:
            bot.edit_message_text("✨ **Botdan foydalanishingiz mumkin:**", call.message.chat.id, call.message.message_id, reply_markup=get_user_markup(), parse_mode="Markdown")
        return

    if user_id not in ADMIN_IDS:
        is_sub, _ = check_subscription(user_id)
        if not is_sub:
            bot.answer_callback_query(call.id, "⚠️ Avval kanalga obuna bo'ling!", show_alert=True)
            return

    if call.data == "search_menu":
        bot.answer_callback_query(call.id)
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🔢 Kod orqali izlash", callback_data="search_by_code"),
            types.InlineKeyboardButton("🔤 Nomi orqali izlash", callback_data="search_by_name"),
            types.InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")
        )
        bot.edit_message_text("🔍 **Qidirish usulini tanlang:**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif call.data == "search_by_code":
        bot.answer_callback_query(call.id)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="search_menu"))
        bot.edit_message_text("🔢 **Anime kodini yuboring:**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        set_user_state(user_id, "waiting_for_code_search")

    elif call.data == "search_by_name":
        bot.answer_callback_query(call.id)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="search_menu"))
        bot.edit_message_text("🔤 **Anime nomini yuboring:**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        set_user_state(user_id, "waiting_for_name_search")
        
    elif call.data == "anime_list":
        bot.answer_callback_query(call.id)
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT title, code FROM animes ORDER BY id DESC LIMIT 15")
        rows = cursor.fetchall()
        conn.close()
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        if not rows:
            markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main"))
            bot.edit_message_text("📂 **Hozircha animelar yo'q.**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
            return
            
        for title, code in rows:
            markup.add(types.InlineKeyboardButton(f"🎬 {title} (Kod: {code})", callback_data=f"show_anime_{code}"))
        markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main"))
        bot.edit_message_text("📂 **Mavjud animelar:**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif call.data.startswith("show_anime_"):
        bot.answer_callback_query(call.id)
        code = call.data.split("_")[2]
        
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT channel_name, channel_link, title, code, photo_id, episodes, genre, description FROM animes WHERE code = ?", (code,))
        row = cursor.fetchone()
        
        if row:
            ch_name, ch_link, title, code, photo_id, episodes, genre, description = row
            cursor.execute("UPDATE animes SET views = views + 1 WHERE code = ?", (code,))
            conn.commit()
            conn.close()
            
            caption = f"🎬 **Anime:** {title}\n🔢 **Kod:** {code}\n📢 **Kanal:** {ch_name}\n🧩 **Qismlar:** {episodes}\n🎭 **Janr:** {genre}\n\n📖 **Ma'lumot:**\n{description}"
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton(f"📺 {ch_name}", url=ch_link))
            markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="anime_list"))
            
            bot.delete_message(call.message.chat.id, call.message.message_id)
            if photo_id:
                bot.send_photo(call.message.chat.id, photo_id, caption=caption, reply_markup=markup, parse_mode="Markdown")
            else:
                bot.send_message(call.message.chat.id, caption, reply_markup=markup, parse_mode="Markdown")
        else:
            conn.close()
            bot.answer_callback_query(call.id, "Anime topilmadi!", show_alert=True)

    elif call.data == "hot_animes" or call.data == "top_animes":
        bot.answer_callback_query(call.id)
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT title, code FROM animes ORDER BY views DESC LIMIT 5")
        rows = cursor.fetchall()
        conn.close()
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        if not rows:
            markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main"))
            bot.edit_message_text("🔥 **Hozircha ma'lumot yo'q.**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
            return
            
        for title, code in rows:
            markup.add(types.InlineKeyboardButton(f"⭐ {title} (Kod: {code})", callback_data=f"show_anime_{code}"))
        markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main"))
        bot.edit_message_text("🔥 **Top / Qaynoq animelar:**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif call.data == "recent_animes":
        bot.answer_callback_query(call.id)
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT title, code FROM animes ORDER BY id DESC LIMIT 5")
        rows = cursor.fetchall()
        conn.close()
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        if not rows:
            markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main"))
            bot.edit_message_text("⏰ **Yangi animelar yo'q.**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
            return
            
        for title, code in rows:
            markup.add(types.InlineKeyboardButton(f"⏰ {title} (Kod: {code})", callback_data=f"show_anime_{code}"))
        markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main"))
        bot.edit_message_text("⏰ **Oxirgi qo'shilganlar:**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif call.data == "back_to_main":
        bot.answer_callback_query(call.id)
        set_user_state(user_id, None)
        
        if user_id in ADMIN_IDS:
            bot.edit_message_text("👑 **Admin paneli:**", call.message.chat.id, call.message.message_id, reply_markup=get_admin_markup(), parse_mode="Markdown")
        else:
            bot.edit_message_text("✨ **Asosiy menyu:**", call.message.chat.id, call.message.message_id, reply_markup=get_user_markup(), parse_mode="Markdown")

    elif call.data == "add_force_channel" and user_id in ADMIN_IDS:
        bot.answer_callback_query(call.id)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main"))
        bot.edit_message_text("📢 **Kanal username'ini yuboring** (masalan: `@kanal`):", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        set_user_state(user_id, "waiting_force_username")

    elif call.data == "del_force_channel" and user_id in ADMIN_IDS:
        bot.answer_callback_query(call.id)
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT id, channel_username FROM force_channels")
        channels = cursor.fetchall()
        conn.close()
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        if not channels:
            markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main"))
            bot.edit_message_text("📂 **Kanallar yo'q.**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
            return
            
        for ch_id, ch_uname in channels:
            markup.add(types.InlineKeyboardButton(f"❌ O'chirish: {ch_uname}", callback_data=f"remove_force_{ch_id}"))
        markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main"))
        bot.edit_message_text("🗑 **O'chirish uchun kanalni tanlang:**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif call.data.startswith("remove_force_") and user_id in ADMIN_IDS:
        bot.answer_callback_query(call.id)
        ch_id = call.data.split("_")[2]
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM force_channels WHERE id = ?", (ch_id,))
        conn.commit()
        conn.close()
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main"))
        bot.edit_message_text("✅ **Kanal o'chirildi!**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif call.data == "add_anime" and user_id in ADMIN_IDS:
        bot.answer_callback_query(call.id)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main"))
        bot.edit_message_text("📢 **1-qadam:** Anime joylanadigan kanal nomini kiriting:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        set_user_state(user_id, "waiting_anime_channel_name")

    elif call.data == "del_anime_menu" and user_id in ADMIN_IDS:
        bot.answer_callback_query(call.id)
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, code FROM animes ORDER BY id DESC LIMIT 15")
        rows = cursor.fetchall()
        conn.close()
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        if not rows:
            markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main"))
            bot.edit_message_text("📂 **Animelar yo'q.**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
            return
            
        for a_id, title, code in rows:
            markup.add(types.InlineKeyboardButton(f"❌ O'chirish: {title} ({code})", callback_data=f"remove_anime_{a_id}"))
        markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main"))
        bot.edit_message_text("🗑 **O'chirish uchun animeni tanlang:**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif call.data.startswith("remove_anime_") and user_id in ADMIN_IDS:
        bot.answer_callback_query(call.id)
        a_id = call.data.split("_")[2]
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM animes WHERE id = ?", (a_id,))
        conn.commit()
        conn.close()
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main"))
        bot.edit_message_text("✅ **Anime o'chirildi!**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif call.data == "admin_broadcast" and user_id in ADMIN_IDS:
        bot.answer_callback_query(call.id)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main"))
        bot.edit_message_text("📤 **Tarqatish uchun xabarni yuboring:**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        set_user_state(user_id, "waiting_broadcast_message")

    elif call.data == "admin_stats" and user_id in ADMIN_IDS:
        bot.answer_callback_query(call.id)
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM animes")
        anime_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM force_channels")
        force_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        conn.close()
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main"))
        text = f"📊 **Statistika:**\n\n- Animelar: {anime_count}\n- Kanallar: {force_count}\n- Foydalanuvchilar: {user_count}"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")


# ============================================================
# XABARLAR VA WIZARD BOSQICHLARI (BAZA ORQALI)
# ============================================================
@bot.message_handler(func=lambda message: True, content_types=['text', 'photo', 'video', 'document'])
def handle_messages(message):
    user_id = message.from_user.id
    
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, state) VALUES (?, NULL)", (user_id,))
    conn.commit()
    conn.close()

    if user_id not in ADMIN_IDS:
        is_sub, unsubs = check_subscription(user_id)
        if not is_sub:
            markup = types.InlineKeyboardMarkup(row_width=1)
            for ch_username, ch_link in unsubs:
                markup.add(types.InlineKeyboardButton(f"📢 Kanalga obuna bo'lish", url=ch_link))
            markup.add(types.InlineKeyboardButton("🔄 Obunani tekshirish", callback_data="check_sub"))
            bot.reply_to(message, "⚠️ **Diqqat!** Botdan foydalanish uchun quyidagi kanalga obuna bo'lishingiz shart:", reply_markup=markup, parse_mode="Markdown")
            return

    state = get_user_state(user_id)
    markup_back = types.InlineKeyboardMarkup()
    markup_back.add(types.InlineKeyboardButton("🔙 Asosiy menyu", callback_data="back_to_main"))
    
    if state == "waiting_broadcast_message":
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        all_users = cursor.fetchall()
        conn.close()
        
        success = 0
        for (u_id,) in all_users:
            try:
                bot.copy_message(chat_id=u_id, from_chat_id=message.chat.id, message_id=message.message_id)
                success += 1
                time.sleep(0.03)
            except Exception:
                pass
                
        bot.reply_to(message, f"✅ **Xabar {success} ta foydalanuvchiga yuborildi!**", reply_markup=markup_back, parse_mode="Markdown")
        set_user_state(user_id, None)

    elif state == "waiting_force_username":
        if not message.text:
            bot.reply_to(message, "Kanal username'ini yuboring.")
            return
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO temp_anime_data (user_id, channel_name) VALUES (?, ?)", (user_id, message.text.strip()))
        conn.commit()
        conn.close()
        
        bot.reply_to(message, "🔗 Kanal havolasini yuboring:", reply_markup=markup_back)
        set_user_state(user_id, "waiting_force_link")
        
    elif state == "waiting_force_link":
        if not message.text:
            bot.reply_to(message, "Havolani yuboring.")
            return
        ch_link = message.text.strip()
        
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT channel_name FROM temp_anime_data WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        ch_uname = row[0] if row else "@kanal"
        
        cursor.execute("INSERT INTO force_channels (channel_username, channel_link) VALUES (?, ?)", (ch_uname, ch_link))
        cursor.execute("DELETE FROM temp_anime_data WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        
        bot.reply_to(message, f"✅ Kanal muvaffaqiyatli qo'shildi!", reply_markup=markup_back)
        set_user_state(user_id, None)

    # --- ANIME QO'SHISH WIZARD BOSQICHLARI ---
    elif state == "waiting_anime_channel_name":
        if not message.text:
            bot.reply_to(message, "Kanal nomini yuboring.")
            return
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO temp_anime_data (user_id, channel_name) VALUES (?, ?)", (user_id, message.text.strip()))
        conn.commit()
        conn.close()
        
        bot.reply_to(message, "🔗 **2-qadam:** Kanal havolasini yuboring:", reply_markup=markup_back, parse_mode="Markdown")
        set_user_state(user_id, "waiting_anime_channel_link")

    elif state == "waiting_anime_channel_link":
        if not message.text:
            bot.reply_to(message, "Kanal havolasini yuboring.")
            return
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("UPDATE temp_anime_data SET channel_link = ? WHERE user_id = ?", (message.text.strip(), user_id))
        conn.commit()
        conn.close()
        
        bot.reply_to(message, "🎬 **3-qadam:** Animening to'liq nomini kiriting:", reply_markup=markup_back, parse_mode="Markdown")
        set_user_state(user_id, "waiting_anime_title")

    elif state == "waiting_anime_title":
        if not message.text:
            bot.reply_to(message, "Anime nomini yuboring.")
            return
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("UPDATE temp_anime_data SET title = ? WHERE user_id = ?", (message.text.strip(), user_id))
        conn.commit()
        conn.close()
        
        bot.reply_to(message, "🔤 **4-qadam:** Yashirin nomlarni yuboring (vergul bilan):", reply_markup=markup_back, parse_mode="Markdown")
        set_user_state(user_id, "waiting_anime_hidden")

    elif state == "waiting_anime_hidden":
        if not message.text:
            bot.reply_to(message, "Yashirin nomlarni yuboring.")
            return
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("UPDATE temp_anime_data SET hidden_names = ? WHERE user_id = ?", (message.text.strip(), user_id))
        conn.commit()
        conn.close()
        
        bot.reply_to(message, "🔢 **5-qadam:** Anime kodini (raqam) yuboring:", reply_markup=markup_back, parse_mode="Markdown")
        set_user_state(user_id, "waiting_anime_code")

    elif state == "waiting_anime_code":
        if not message.text:
            bot.reply_to(message, "Kod yuboring.")
            return
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("UPDATE temp_anime_data SET code = ? WHERE user_id = ?", (message.text.strip(), user_id))
        conn.commit()
        conn.close()
        
        bot.reply_to(message, "🖼 **6-qadam:** Anime rasmini (posterini) yuboring:", reply_markup=markup_back, parse_mode="Markdown")
        set_user_state(user_id, "waiting_anime_photo")

    elif state == "waiting_anime_photo":
        if not message.photo:
            bot.reply_to(message, "❌ Rasm yuborishingiz kerak!")
            return
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("UPDATE temp_anime_data SET photo_id = ? WHERE user_id = ?", (message.photo[-1].file_id, user_id))
        conn.commit()
        conn.close()
        
        bot.reply_to(message, "🧩 **7-qadam:** Qismlarini yuboring (masalan: 1-12 qism):", reply_markup=markup_back, parse_mode="Markdown")
        set_user_state(user_id, "waiting_anime_episodes")

    elif state == "waiting_anime_episodes":
        if not message.text:
            bot.reply_to(message, "Qismlarini yuboring.")
            return
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("UPDATE temp_anime_data SET episodes = ? WHERE user_id = ?", (message.text.strip(), user_id))
        conn.commit()
        conn.close()
        
        bot.reply_to(message, "🎭 **8-qadam:** Janrini yuboring:", reply_markup=markup_back, parse_mode="Markdown")
        set_user_state(user_id, "waiting_anime_genre")

    elif state == "waiting_anime_genre":
        if not message.text:
            bot.reply_to(message, "Janrni yuboring.")
            return
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("UPDATE temp_anime_data SET genre = ? WHERE user_id = ?", (message.text.strip(), user_id))
        conn.commit()
        conn.close()
        
        bot.reply_to(message, "📖 **9-qadam:** Anime haqida qisqacha tavsif yuboring:", reply_markup=markup_back, parse_mode="Markdown")
        set_user_state(user_id, "waiting_anime_description")

    elif state == "waiting_anime_description":
        if not message.text:
            bot.reply_to(message, "Tavsifni yuboring.")
            return
        
        desc = message.text.strip()
        
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT channel_name, channel_link, title, hidden_names, code, photo_id, episodes, genre FROM temp_anime_data WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        
        if row:
            ch_name, ch_link, title, hidden, code, photo_id, episodes, genre = row
            try:
                cursor.execute("""
                    INSERT INTO animes (channel_name, channel_link, title, hidden_names, code, photo_id, episodes, genre, description) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (ch_name, ch_link, title, hidden, code, photo_id, episodes, genre, desc))
                conn.commit()
                bot.reply_to(message, f"🎉 **'{title}' animasi muvaffaqiyatli saqlandi!**", reply_markup=markup_back, parse_mode="Markdown")
            except sqlite3.IntegrityError:
                bot.reply_to(message, "❌ Xatolik: Bu kod band qilingan!", reply_markup=markup_back)
            
            cursor.execute("DELETE FROM temp_anime_data WHERE user_id = ?", (user_id,))
            conn.commit()
        
        conn.close()
        set_user_state(user_id, None)

    elif state == "waiting_for_code_search":
        if not message.text:
            bot.reply_to(message, "Kodni yuboring.")
            return
        code_input = message.text.strip()
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT channel_name, channel_link, title, code, photo_id, episodes, genre, description FROM animes WHERE code = ?", (code_input,))
        row = cursor.fetchone()
        
        markup = types.InlineKeyboardMarkup()
        if row:
            ch_name, ch_link, title, code, photo_id, episodes, genre, description = row
            cursor.execute("UPDATE animes SET views = views + 1 WHERE code = ?", (code_input,))
            conn.commit()
            conn.close()
            
            caption = f"🎬 **Anime:** {title}\n🔢 **Kod:** {code}\n📢 **Kanal:** {ch_name}\n🧩 **Qismlar:** {episodes}\n🎭 **Janr:** {genre}\n\n📖 **Ma'lumot:**\n{description}"
            markup.add(types.InlineKeyboardButton(f"📺 {ch_name}", url=ch_link))
            markup.add(types.InlineKeyboardButton("🔙 Asosiy menyu", callback_data="back_to_main"))
            
            if photo_id:
                bot.send_photo(message.chat.id, photo_id, caption=caption, reply_markup=markup, parse_mode="Markdown")
            else:
                bot.send_message(message.chat.id, caption, reply_markup=markup, parse_mode="Markdown")
        else:
            conn.close()
            markup.add(types.InlineKeyboardButton("🔙 Asosiy menyu", callback_data="back_to_main"))
            bot.reply_to(message, "❌ Bunday kodli anime topilmadi.", reply_markup=markup)
            
        set_user_state(user_id, None)

    elif state == "waiting_for_name_search":
        if not message.text:
            bot.reply_to(message, "Nomini yuboring.")
            return
        query = message.text.lower().strip()
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT title, code FROM animes WHERE LOWER(title) LIKE ? OR LOWER(hidden_names) LIKE ?", 
                       (f'%{query}%', f'%{query}%'))
        rows = cursor.fetchall()
        conn.close()
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        if not rows:
            markup.add(types.InlineKeyboardButton("🔙 Asosiy menyu", callback_data="back_to_main"))
            bot.reply_to(message, "❌ Bu nomdagi anime topilmadi.", reply_markup=markup)
        else:
            for title, code in rows:
                markup.add(types.InlineKeyboardButton(f"🎬 {title} (Kod: {code})", callback_data=f"show_anime_{code}"))
            markup.add(types.InlineKeyboardButton("🔙 Asosiy menyu", callback_data="back_to_main"))
            bot.reply_to(message, f"🔍 **Topilgan natijalar:**", reply_markup=markup, parse_mode="Markdown")
            
        set_user_state(user_id, None)

    else:
        if user_id in ADMIN_IDS:
            bot.reply_to(message, "👑 **Admin boshqaruv paneli:**", reply_markup=get_admin_markup(), parse_mode="Markdown")
        else:
            bot.reply_to(message, "✨ **Asosiy menyu:**", reply_markup=get_user_markup(), parse_mode="Markdown")


# ============================================================
# BOTNI ISHGA TUSHIRISH
# ============================================================
if __name__ == "__main__":
    print("Bot ishga tushmoqda...")
    try:
        keep_alive()
        print("Web server ishga tushdi.")
    except Exception as e:
        print(f"Xatolik: {e}")

    time.sleep(2)

    while True:
        try:
            bot.remove_webhook()
            time.sleep(1)
            print("Polling boshlandi...")
            bot.infinity_polling(skip_pending=True, timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"Xatolik: {e}")
            time.sleep(5)
