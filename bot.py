import os
import sqlite3
import threading
import time
import html
from urllib.parse import urlparse

from flask import Flask
import telebot
from telebot import types

try:
    import psycopg2
except ImportError:
    psycopg2 = None


# ============================================================
# SOZLAMALAR
# ============================================================

TOKEN = os.environ.get('BOT_TOKEN', '8987164421:AAHIKjTCtB4781Ns53b3WSHk5xgAWOXTtQ8')
bot = telebot.TeleBot(TOKEN)

# 2 nafar adminning Telegram ID raqamlari (o'zingiznikiga o'zgartiring)
ADMIN_IDS = [7986354170, 7986354170]

# Foydalanuvchilarning holatini (state) saqlash uchun lug'at
user_states = {}

# Ma'lumotlar bazasini yaratish / ulanish
def init_db():
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    cursor = conn.cursor()
    
    # Foydalanuvchilar jadvali (Broadcast uchun)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY
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

# Render 24/7 ishlashi uchun Flask web server
app = Flask('')

@app.route('/')
def home():
    return "Ani Kenbot muvaffaqiyatli ishlamoqda!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run)
    t.daemon = True
    t.start()


# ============================================================
# MAJBURIY OBUNANI TEKSHIRISH FUNKSIYASI
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
            not_subscribed.append((ch_username, ch_link))
            
    if not_subscribed:
        return False, not_subscribed
    return True, []


# ============================================================
# BOT BUYRUQLARI VA INLINE MENYULAR
# ============================================================

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    user_states.pop(user_id, None)  # Xotirani tozalash
    
    # Foydalanuvchini bazaga qo'shish
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
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
                             "⚠️ Diqqat! Botimizdan foydalanish uchun quyidagi kanal(lar)ga obuna bo'lishingiz shart.\n\nObuna bo'lgandan so'ng '🔄 Obunani tekshirish' tugmasini bosing:", 
                             reply_markup=markup, parse_mode="Markdown")
            return

    markup = types.InlineKeyboardMarkup(row_width=2)
    if user_id in ADMIN_IDS:
        btn_add_force = types.InlineKeyboardButton("📢 Majburiy kanal qo'shish", callback_data="add_force_channel")
        btn_del_force = types.InlineKeyboardButton("🗑 Majburiy kanalni o'chirish", callback_data="del_force_channel")
        btn_add_anime = types.InlineKeyboardButton("🎬 Anime qo'shish", callback_data="add_anime")
        btn_del_anime = types.InlineKeyboardButton("🗑 Animeni o'chirish", callback_data="del_anime_menu")
        btn_broadcast = types.InlineKeyboardButton("📤 Xabar yuborish", callback_data="admin_broadcast")
        btn_stats = types.InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")
        
        markup.add(btn_add_force, btn_del_force)
        markup.add(btn_add_anime, btn_del_anime)
        markup.add(btn_broadcast, btn_stats)
        
        bot.send_message(message.chat.id, "👑 Xush kelibsiz, Admin! Boshqaruv paneli:", reply_markup=markup, parse_mode="Markdown")
    else:
        btn_search = types.InlineKeyboardButton("🔍 Anime izlash", callback_data="search_menu")
        btn_list = types.InlineKeyboardButton("📂 Mavjud animelar", callback_data="anime_list")
        btn_hot = types.InlineKeyboardButton("🔥 Qaynoq / Yangi", callback_data="hot_animes")
        btn_recent = types.InlineKeyboardButton("⏰ Oxirgi qo'shilganlar", callback_data="recent_animes")
        btn_top = types.InlineKeyboardButton("⭐ Top animelar", callback_data="top_animes")
        
        markup.add(btn_search, btn_list)
        markup.add(btn_hot, btn_recent)
        markup.add(btn_top)
        
        bot.send_message(message.chat.id, "✨ Assalomu alaykum! Ani Kenbot'ga xush kelibsiz.\n\nKerakli bo'limni tanlang:", reply_markup=markup, parse_mode="Markdown")


# Callback tugmalar bilan ishlash
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    
    if call.data == "check_sub":
        is_sub, unsubs = check_subscription(user_id)
        if not is_sub:
            bot.answer_callback_query(call.id, "❌ Siz hali hamma kanallarga obuna bo'lmadingiz!", show_alert=True)
            return
        bot.answer_callback_query(call.id, "✅ Muvaffaqiyatli obuna bo'ldingiz!")
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_search = types.InlineKeyboardButton("🔍 Anime izlash", callback_data="search_menu")
        btn_list = types.InlineKeyboardButton("📂 Mavjud animelar", callback_data="anime_list")
        btn_hot = types.InlineKeyboardButton("🔥 Qaynoq / Yangi", callback_data="hot_animes")
        btn_recent = types.InlineKeyboardButton("⏰ Oxirgi qo'shilganlar", callback_data="recent_animes")
        btn_top = types.InlineKeyboardButton("⭐ Top animelar", callback_data="top_animes")
        markup.add(btn_search, btn_list, btn_hot, btn_recent, btn_top)
        bot.edit_message_text("✨ Rahmat! Endi botdan to'liq foydalanishingiz mumkin:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        return

    if user_id not in ADMIN_IDS:
        is_sub, unsubs = check_subscription(user_id)
        if not is_sub:
            bot.answer_callback_query(call.id, "⚠️ Avval kanalga obuna bo'ling!", show_alert=True)
            return
            
    if call.data == "search_menu":          
        bot.answer_callback_query(call.id)
        markup = types.InlineKeyboardMarkup(row_width=1)
        btn_code = types.InlineKeyboardButton("🔢 Kod orqali izlash", callback_data="search_by_code")
        btn_name = types.InlineKeyboardButton("🔤 Nomi orqali izlash", callback_data="search_by_name")
        btn_back = types.InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")
        markup.add(btn_code, btn_name, btn_back)
        bot.edit_message_text("🔍 Qidirish usulini tanlang:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif call.data == "search_by_code":
        bot.answer_callback_query(call.id)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="search_menu"))
        bot.edit_message_text("🔢 Marhamat, anime kodini yuboring (masalan: 101):", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        user_states[user_id] = "waiting_for_code_search"

    elif call.data == "search_by_name":
        bot.answer_callback_query(call.id)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="search_menu"))
        bot.edit_message_text("🔤 Animening to'liq yoki yashirin nomini yuboring:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        user_states[user_id] = "waiting_for_name_search"
        
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
            bot.edit_message_text("📂 Hozircha bazada animelar mavjud emas.", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
            return
            
        text = "📂 Mavjud animelar katalogi:\n"
        for title, code in rows:
            markup.add(types.InlineKeyboardButton(f"🎬 {title} (Kod: {code})", callback_data=f"show_anime_{code}"))
        markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

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
            
            caption = f"🎬 Anime: {title}\n" \
                      f"🔢 Kod: {code}\n" \
                      f"📢 Kanal: {ch_name}\n" \
                      f"🧩 Qismlari: {episodes}\n" \
                      f"🎭 Janri: {genre}\n\n" \
                      f"📖 Ma'lumot:\n{description}"
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton(f"📺 {ch_name} kanaliga o'tish", url=ch_link))
            markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="anime_list"))
            
            bot.delete_message(call.message.chat.id, call.message.message_id)
            if photo_id:
                bot.send_photo(call.message.chat.id, photo_id, caption=caption, reply_markup=markup, parse_mode="Markdown")
            else:
                bot.send_message(call.message.chat.id, caption, reply_markup=markup, parse_mode="Markdown")
        else:
            conn.close()
            bot.answer_callback_query(call.id, "Anime topilmadi!", show_alert=True)

    elif call.data == "hot_animes":
        bot.answer_callback_query(call.id)
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT title, code FROM animes ORDER BY views DESC LIMIT 5")
        rows = cursor.fetchall()
        conn.close()
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        if not rows:
            markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main"))
            bot.edit_message_text("🔥 Hozircha qaynoq animelar yo'q.", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
            return
            
        text = "🔥 Eng qaynoq va ko'p ko'rilgan animelar:\n"
        for title, code in rows:
            markup.add(types.InlineKeyboardButton(f"🔥 {title} (Kod: {code})", callback_data=f"show_anime_{code}"))
        markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

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
            bot.edit_message_text("⏰ Hozircha yangi animelar qo'shilmagan.", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
            return
            
        text = "⏰ Oxirgi qo'shilgan animelar:\n"
        for title, code in rows:
            markup.add(types.InlineKeyboardButton(f"⏰ {title} (Kod: {code})", callback_data=f"show_anime_{code}"))
        markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif call.data == "top_animes":
        bot.answer_callback_query(call.id)
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT title, code FROM animes ORDER BY views DESC LIMIT 5")
        rows = cursor.fetchall()
        conn.close()
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        if not rows:
            markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main"))
            bot.edit_message_text("⭐ Hozircha top animelar ro'yxati bo'sh.", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
            return
            
        text = "⭐ Reytingi eng baland Top animelar:\n"
        for title, code in rows:
            markup.add(types.InlineKeyboardButton(f"⭐ {title} (Kod: {code})", callback_data=f"show_anime_{code}"))
        markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        
    elif call.data == "back_to_main":
        bot.answer_callback_query(call.id)
        user_states.pop(user_id, None)
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        if user_id in ADMIN_IDS:
            btn_add_force = types.InlineKeyboardButton("📢 Majburiy kanal qo'shish", callback_data="add_force_channel")
            btn_del_force = types.InlineKeyboardButton("🗑 Majburiy kanalni o'chirish", callback_data="del_force_channel")
            btn_add_anime = types.InlineKeyboardButton("🎬 Anime qo'shish", callback_data="add_anime")
            btn_del_anime = types.InlineKeyboardButton("🗑 Animeni o'chirish", callback_data="del_anime_menu")
            btn_broadcast = types.InlineKeyboardButton("📤 Xabar yuborish", callback_data="admin_broadcast")
            btn_stats = types.InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")
            
            markup.add(btn_add_force, btn_del_force)
            markup.add(btn_add_anime, btn_del_anime)
            markup.add(btn_broadcast, btn_stats)
            bot.edit_message_text("👑 Admin boshqaruv paneli:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        else:
            btn_search = types.InlineKeyboardButton("🔍 Anime izlash", callback_data="search_menu")
            btn_list = types.InlineKeyboardButton("📂 Mavjud animelar", callback_data="anime_list")
            btn_hot = types.InlineKeyboardButton("🔥 Qaynoq / Yangi", callback_data="hot_animes")
            btn_recent = types.InlineKeyboardButton("⏰ Oxirgi qo'shilganlar", callback_data="recent_animes")
            btn_top = types.InlineKeyboardButton("⭐ Top animelar", callback_data="top_animes")
            markup.add(btn_search, btn_list, btn_hot, btn_recent, btn_top)
            bot.edit_message_text("✨ Kerakli bo'limni tanlang:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    # Admin boshqaruv bo'limlari
    elif call.data == "add_force_channel" and user_id in ADMIN_IDS:
        bot.answer_callback_query(call.id)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main"))
        bot.edit_message_text("📢 Majburiy obuna uchun kanal usernamesini yuboring (masalan: @kanal_nomi):", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        user_states[user_id] = "waiting_force_username"

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
            bot.edit_message_text("📂 Majburiy obuna kanallari mavjud emas.", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
            return
            
        for ch_id, ch_uname in channels:
            markup.add(types.InlineKeyboardButton(f"❌ O'chirish: {ch_uname}", callback_data=f"remove_force_{ch_id}"))
        markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main"))
        bot.edit_message_text("🗑 O'chirmoqchi bo'lgan majburiy kanalni tanlang:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

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
        bot.edit_message_text("✅ Majburiy kanal muvaffaqiyatli o'chirildi!", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        
    elif call.data == "add_anime" and user_id in ADMIN_IDS:
        bot.answer_callback_query(call.id)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main"))
        bot.edit_message_text("📢 1-qadam: Anime joylanadigan kanal nomini kiriting:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        user_states[user_id] = "waiting_anime_channel_name"

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
            bot.edit_message_text("📂 O'chirish uchun animelar mavjud emas.", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
            return
            
        for a_id, title, code in rows:
            markup.add(types.InlineKeyboardButton(f"❌ O'chirish: {title} (Kod: {code})", callback_data=f"remove_anime_{a_id}"))
        markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main"))
        bot.edit_message_text("🗑 O'chirmoqchi bo'lgan animeni tanlang:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

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
        bot.edit_message_text("✅ Anime bazadan muvaffaqiyatli o'chirildi!", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

    elif call.data == "admin_broadcast" and user_id in ADMIN_IDS:
        bot.answer_callback_query(call.id)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main"))
        bot.edit_message_text("📤 Obunachilarga yubormoqchi bo'lgan xabaringizni (matn, rasm yoki video) yuboring:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        user_states[user_id] = "waiting_broadcast_message"

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
        text = f"📊 Bot statistikasi:\n\n- Jami animelar: {anime_count} ta\n- Majburiy kanallar: {force_count} ta\n- Obunachilar: {user_count} ta"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
# Oddiy xabarlarni va bosqichlarni uzluksiz boshqarish
@bot.message_handler(func=lambda message: True, content_types=['text', 'photo', 'video', 'document'])
def handle_messages(message):
    user_id = message.from_user.id
    
    # Bazaga foydalanuvchini qo'shish
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

    if user_id not in ADMIN_IDS:
        is_sub, unsubs = check_subscription(user_id)
        if not is_sub:
            markup = types.InlineKeyboardMarkup(row_width=1)
            for ch_username, ch_link in unsubs:
                markup.add(types.InlineKeyboardButton(f"📢 Kanalga obuna bo'lish", url=ch_link))
            markup.add(types.InlineKeyboardButton("🔄 Obunani tekshirish", callback_data="check_sub"))
            bot.reply_to(message, "⚠️ Diqqat! Botdan foydalanish uchun avval ko'rsatilgan kanalga obuna bo'lishingiz kerak!", reply_markup=markup, parse_mode="Markdown")
            return

    state = user_states.get(user_id)
    markup_back = types.InlineKeyboardMarkup()
    markup_back.add(types.InlineKeyboardButton("🔙 Asosiy menyuga qaytish", callback_data="back_to_main"))
    
    # Broadcast xabar tarqatish
    if state == "waiting_broadcast_message":
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        all_users = cursor.fetchall()
        conn.close()
        
        success = 0
        failed = 0
        for (u_id,) in all_users:
            try:
                bot.copy_message(chat_id=u_id, from_chat_id=message.chat.id, message_id=message.message_id)
                success += 1
                time.sleep(0.04)
            except Exception:
                failed += 1
                
        bot.reply_to(message, f"✅ Xabar muvaffaqiyatli tarqatildi!\n\n- Yetib bordi: {success} ta\n- Xatolik: {failed} ta", reply_markup=markup_back, parse_mode="Markdown")
        user_states.pop(user_id, None)

    # Majburiy kanal qo'shish
    elif state == "waiting_force_username":
        if not message.text:
            bot.reply_to(message, "Iltimos, kanal username'ini yuboring.")
            return
        user_states[f"force_uname_{user_id}"] = message.text.strip()
        bot.reply_to(message, "🔗 Endi o'sha kanalning havolasini (linkini) yuboring:", reply_markup=markup_back)
        user_states[user_id] = "waiting_force_link"
        
    elif state == "waiting_force_link":
        if not message.text:
            bot.reply_to(message, "Iltimos, havolani yuboring.")
            return
        ch_uname = user_states.get(f"force_uname_{user_id}")
        ch_link = message.text.strip()
        
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO force_channels (channel_username, channel_link) VALUES (?, ?)", (ch_uname, ch_link))
        conn.commit()
        conn.close()
        
        bot.reply_to(message, f"✅ Muvaffaqiyatli! Majburiy obuna uchun '{ch_uname}' kanali qo'shildi.", reply_markup=markup_back)
        user_states.pop(user_id, None)

    # Anime qo'shish bosqichlari
    elif state == "waiting_anime_channel_name":
        if not message.text:
            bot.reply_to(message, "Iltimos, kanal nomini yuboring.")
            return
        user_states[f"anime_ch_name_{user_id}"] = message.text
        bot.reply_to(message, "🔗 2-qadam: O'sha kanalning linkini yuboring:", reply_markup=markup_back, parse_mode="Markdown")
        user_states[user_id] = "waiting_anime_channel_link"

    elif state == "waiting_anime_channel_link":
        if not message.text:
            bot.reply_to(message, "Iltimos, kanal linkini yuboring.")
            return
        user_states[f"anime_ch_link_{user_id}"] = message.text
        bot.reply_to(message, "🎬 3-qadam: Animening to'liq nomini kiriting:", reply_markup=markup_back, parse_mode="Markdown")
        user_states[user_id] = "waiting_anime_title"

    elif state == "waiting_anime_title":
        if not message.text:
            bot.reply_to(message, "Iltimos, anime nomini yuboring.")
            return
        user_states[f"anime_title_{user_id}"] = message.text
        bot.reply_to(message, "🔤 4-qadam: Animening yashirin yoki muqobil nomlarini yuboring (vergul bilan):", reply_markup=markup_back, parse_mode="Markdown")
        user_states[user_id] = "waiting_anime_hidden"

    elif state == "waiting_anime_hidden":
        if not message.text:
            bot.reply_to(message, "Iltimos, yashirin nomlarni yuboring.")
            return
        user_states[f"anime_hidden_{user_id}"] = message.text
        bot.reply_to(message, "🔢 5-qadam: Anime uchun maxsus kod (raqam) yuboring (masalan: 101):", reply_markup=markup_back, parse_mode="Markdown")
        user_states[user_id] = "waiting_anime_code"

    elif state == "waiting_anime_code":
        if not message.text:
            bot.reply_to(message, "Iltimos, raqamli kod yuboring.")
            return
        user_states[f"anime_code_{user_id}"] = message.text
        bot.reply_to(message, "🖼 6-qadam: Animening rasmini (posterini) yuboring:", reply_markup=markup_back, parse_mode="Markdown")
        user_states[user_id] = "waiting_anime_photo"

    elif state == "waiting_anime_photo":
        if not message.photo:
            bot.reply_to(message, "❌ Iltimos, rasm (foto) yuboring!")
            return
        user_states[f"anime_photo_{user_id}"] = message.photo[-1].file_id
        bot.reply_to(message, "🧩 7-qadam: Animening qismlarini yuboring (masalan: 1-12 qism):", reply_markup=markup_back, parse_mode="Markdown")
        user_states[user_id] = "waiting_anime_episodes"

    elif state == "waiting_anime_episodes":
        if not message.text:
            bot.reply_to(message, "Iltimos, qismlarini yuboring.")
            return
        user_states[f"anime_episodes_{user_id}"] = message.text
        bot.reply_to(message, "🎭 8-qadam: Animening janrini yuboring (masalan: Jangari, Romantika):", reply_markup=markup_back, parse_mode="Markdown")
        user_states[user_id] = "waiting_anime_genre"

    elif state == "waiting_anime_genre":
        if not message.text:
            bot.reply_to(message, "Iltimos, janrni yuboring.")
            return
        user_states[f"anime_genre_{user_id}"] = message.text
        bot.reply_to(message, "📖 9-qadam: Anime haqida qisqacha ma'lumot (tavsif) yuboring:", reply_markup=markup_back, parse_mode="Markdown")
        user_states[user_id] = "waiting_anime_description"

    elif state == "waiting_anime_description":
        if not message.text:
            bot.reply_to(message, "Iltimos, tavsifni yuboring.")
            return
        
        ch_name = user_states.get(f"anime_ch_name_{user_id}")
        ch_link = user_states.get(f"anime_ch_link_{user_id}")
        title = user_states.get(f"anime_title_{user_id}")
        hidden = user_states.get(f"anime_hidden_{user_id}")
        code = user_states.get(f"anime_code_{user_id}")
        photo_id = user_states.get(f"anime_photo_{user_id}")
        episodes = user_states.get(f"anime_episodes_{user_id}")
        genre = user_states.get(f"anime_genre_{user_id}")
        desc = message.text
        
        try:
            conn = sqlite3.connect('bot_database.db', check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO animes (channel_name, channel_link, title, hidden_names, code, photo_id, episodes, genre, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (ch_name, ch_link, title, hidden, code, photo_id, episodes, genre, desc))
            conn.commit()
            conn.close()
            bot.reply_to(message, f"🎉 Tabriklayman! '{title}' animasi (Kod: {code}, Kanal: {ch_name}) muvaffaqiyatli saqlandi.", reply_markup=markup_back)
        except sqlite3.IntegrityError:
            bot.reply_to(message, "❌ Xatolik: Bu kod allaqachon band qilingan. Iltimos, boshqa raqam kiriting.", reply_markup=markup_back)
            
        user_states.pop(user_id, None)

    # Kod orqali izlash
    elif state == "waiting_for_code_search":
        if not message.text:
            bot.reply_to(message, "Iltimos, kodni yuboring.")
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
            
            caption = f"🎬 Anime: {title}\n" \
                      f"🔢 Kod: {code}\n" \
                      f"📢 Kanal: {ch_name}\n" \
                      f"🧩 Qismlari: {episodes}\n" \
                      f"🎭 Janri: {genre}\n\n" \
                      f"📖 Ma'lumot:\n{description}"
            
            markup.add(types.InlineKeyboardButton(f"📺 {ch_name} kanaliga o'tish", url=ch_link))
            markup.add(types.InlineKeyboardButton("🔙 Asosiy menyu", callback_data="back_to_main"))
            
            if photo_id:
                bot.send_photo(message.chat.id, photo_id, caption=caption, reply_markup=markup, parse_mode="Markdown")
            else:
                bot.send_message(message.chat.id, caption, reply_markup=markup, parse_mode="Markdown")
        else:
            conn.close()
            markup.add(types.InlineKeyboardButton("🔙 Asosiy menyu", callback_data="back_to_main"))
            bot.reply_to(message, "❌ Kechirasiz, bunday kodga ega anime mavjud emas.", reply_markup=markup)
            
        user_states.pop(user_id, None)

    # Nomi orqali izlash
    elif state == "waiting_for_name_search":
        if not message.text:
            bot.reply_to(message, "Iltimos, nomini yuboring.")
            return
        query = message.text.lower().strip()
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT title, code FROM animes WHERE LOWER(title) LIKE ? OR LOWER(hidden_names) LIKE ?", 
                       (f'%{query}%', f'%{query}%'))
        rows = cursor.fetchall()
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        if not rows:
            markup.add(types.InlineKeyboardButton("🔙 Asosiy menyu", callback_data="back_to_main"))
            bot.reply_to(message, "❌ Kechirasiz, bu nomdagi anime topilmadi.", reply_markup=markup)
        else:
            text = f"🔍 '{message.text}' bo'yicha qidiruv natijalari:\n"
            for title, code in rows:
                markup.add(types.InlineKeyboardButton(f"🎬 {title} (Kod: {code})", callback_data=f"show_anime_{code}"))
            markup.add(types.InlineKeyboardButton("🔙 Asosiy menyu", callback_data="back_to_main"))
            bot.reply_to(message, text, reply_markup=markup, parse_mode="Markdown")
            
        conn.close()
        user_states.pop(user_id, None)

    else:
        bot.reply_to(message, "✨ Bot uzluksiz ishlamoqda. Asosiy menyuga qaytish uchun pastdagi tugmadan foydalaning.", reply_markup=markup_back)
        # ============================================================
# BOTNI ISHGA TUSHIRISH
# ============================================================

if __name__ == "__main__":
    print("Bot ishga tushmoqda...")

    try:
        keep_alive()
        print("Web server ishga tushdi.")
    except Exception as e:
        print(f"Web server xatosi: {e}")

    time.sleep(2)

    while True:
        try:
            bot.remove_webhook()
            time.sleep(1)

            print("Polling boshlandi...")

            bot.infinity_polling(
                skip_pending=True,
                timeout=60,
                long_polling_timeout=60,
            )

        except Exception as e:
            print(f"Polling xatoligi: {e}")
            time.sleep(5)
