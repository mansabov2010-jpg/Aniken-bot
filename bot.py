import os
import sqlite3
import threading
import time
from flask import Flask
import telebot
from telebot import types

# --- SOZLAMALAR ---
TOKEN = "8987164421:AAE6XMCpHqNRIzio-xfp2IueJoKtQK_ZIbc"
ADMIN_ID = 7986354170

bot = telebot.TeleBot(TOKEN)
DB_FILE = "bot_data.db"

# --- FLASK VEB-SERVER (Render uchun) ---
app = Flask(__name__)


@app.route("/")
def home():
  return "Bot is running!"


def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

def keep_alive():
    t = Thread(target=run_web)
    t.start()


# --- MA'LUMOTLAR BAZASI (SQLite) ---
def init_db():
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()

  # Foydalanuvchilar jadvali
  cursor.execute(
      "CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)"
  )

  # Kanallar jadvali
  cursor.execute(
      "CREATE TABLE IF NOT EXISTS channels (username TEXT PRIMARY KEY)"
  )

  # Animelar jadvali
  cursor.execute("""CREATE TABLE IF NOT EXISTS animes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        code TEXT,
        info TEXT,
        photo TEXT,
        views INTEGER DEFAULT 0
    )""")

  # Qismlar jadvali
  cursor.execute("""CREATE TABLE IF NOT EXISTS parts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        anime_id INTEGER,
        part_num INTEGER,
        video_id TEXT
    )""")

  conn.commit()
  conn.close()


init_db()

user_states = {}
temp_data = {}
user_last_messages = {}


# --- XABARLARNI TOZALASH ---
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

  msg = bot.send_message(
      chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode
  )
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

  msg = bot.send_photo(
      chat_id,
      photo,
      caption=caption,
      reply_markup=reply_markup,
      parse_mode=parse_mode,
  )
  user_last_messages[chat_id].append(msg.message_id)
  return msg


# --- MAJBURIY OBUNA ---
def check_sub(user_id):
  if user_id == ADMIN_ID:
    return True
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  cursor.execute("SELECT username FROM channels")
  channels = [row[0] for row in cursor.fetchall()]
  conn.close()

  unsubscribed = []
  for ch in channels:
    try:
      member = bot.get_chat_member(ch, user_id)
      if member.status in ["left", "kicked"]:
        unsubscribed.append(ch)
    except Exception:
      pass
  return unsubscribed


def get_sub_keyboard(unsubscribed_channels):
  markup = types.InlineKeyboardMarkup(row_width=1)
  for ch in unsubscribed_channels:
    url = f"https://t.me/{ch.replace('@', '')}"
    markup.add(
        types.InlineKeyboardButton(f"📢 Kanalga a'zo bo'lish", url=url)
    )
  markup.add(
      types.InlineKeyboardButton(
          "✅ Obunani tekshirish", callback_data="check_subscription"
      )
  )
  return markup


# --- KEYBOARDS ---
def get_main_keyboard(user_id):
  markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
  markup.row("🔍 Animelarni izlash", "📂 Mavjud animelar")
  markup.row("🔥 Tavsiya etiladigan animelar")

  if user_id == ADMIN_ID:
    markup.row("➕ Yangi anime qo'shish", "📢 Kanallarni boshqarish")
    markup.row("📊 Statistika", "⚙️ Animelarni boshqarish")
  return markup


def get_cancel_keyboard():
  markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
  markup.row("❌ Bekor qilish")
  return markup


def get_search_inline_keyboard():
  markup = types.InlineKeyboardMarkup(row_width=2)
  markup.add(
      types.InlineKeyboardButton("📝 Nomi orqali", callback_data="search_by_name"),
      types.InlineKeyboardButton("🔢 Kodi orqali", callback_data="search_by_code"),
  )
  return markup


def get_available_animes_keyboard(for_admin=False):
  markup = types.InlineKeyboardMarkup(row_width=1)
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  cursor.execute("SELECT id, name FROM animes")
  animes = cursor.fetchall()

  if not animes:
    markup.add(
        types.InlineKeyboardButton(
            "❌ Hozircha animelar yo'q", callback_data="none"
        )
    )
  else:
    for anime_id, name in animes:
      cursor.execute(
          "SELECT COUNT(*) FROM parts WHERE anime_id = ?", (anime_id,)
      )
      parts_count = cursor.fetchone()[0]
      prefix = "🗑 " if for_admin else "🎬 "
      cb_data = (
          f"delete_anime_{anime_id}" if for_admin else f"show_anime_{anime_id}"
      )
      btn_text = f"{prefix}{name} ({parts_count}-qism)"
      markup.add(types.InlineKeyboardButton(btn_text, callback_data=cb_data))

  conn.close()
  return markup


def get_recommended_animes_keyboard():
  markup = types.InlineKeyboardMarkup(row_width=1)
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  cursor.execute(
      "SELECT id, name, views FROM animes ORDER BY views DESC LIMIT 10"
  )
  animes = cursor.fetchall()
  conn.close()

  if not animes:
    markup.add(
        types.InlineKeyboardButton(
            "❌ Hozircha animelar yo'q", callback_data="none"
        )
    )
    return markup

  for rank, (anime_id, name, views) in enumerate(animes, start=1):
    btn_text = f"{rank}. 🎬 {name} — 👁 {views} ko'rilgan"
    markup.add(
        types.InlineKeyboardButton(
            btn_text, callback_data=f"show_anime_{anime_id}"
        )
    )
  return markup


def get_anime_folder_keyboard(anime_id):
  markup = types.InlineKeyboardMarkup(row_width=5)
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  cursor.execute(
      "SELECT part_num FROM parts WHERE anime_id = ? ORDER BY part_num ASC",
      (anime_id,),
  )
  parts = cursor.fetchall()
  conn.close()

  buttons = []
  for (p,) in parts:
    buttons.append(
        types.InlineKeyboardButton(
            text=str(p), callback_data=f"get_part_{anime_id}_{p}"
        )
    )

  if buttons:
    markup.add(*buttons)

  markup.add(
      types.InlineKeyboardButton(
          "⬅ Ortga", callback_data="back_to_available"
      )
  )
  return markup


def show_search_results(chat_id, results):
  if not results:
    send_clean_message(chat_id, "❌ Hech qanday anime topilmadi.")
    return
  markup = types.InlineKeyboardMarkup(row_width=1)
  for anime_id, name in results:
    markup.add(
        types.InlineKeyboardButton(
            f"🎬 {name}", callback_data=f"show_anime_{anime_id}"
        )
    )
  send_clean_message(chat_id, "🔎 Topilgan animelar:", reply_markup=markup)


# --- HANDLERLAR ---
@bot.message_handler(commands=["start"])
def start_cmd(message):
  user_id = message.from_user.id

  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
  conn.commit()
  conn.close()

  user_states.pop(user_id, None)
  temp_data.pop(user_id, None)

  try:
    bot.delete_message(message.chat.id, message.message_id)
  except:
    pass

  unsub = check_sub(user_id)
  if unsub is not True and unsub:
    text = "⚠️️ Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:"
    send_clean_message(
        message.chat.id, text, reply_markup=get_sub_keyboard(unsub)
    )
    return

  text = "👋 Xush kelibsiz! Kerakli bo'limni tanlang:"
  send_clean_message(
      message.chat.id, text, reply_markup=get_main_keyboard(user_id)
  )


@bot.message_handler(func=lambda msg: msg.text == "❌ Bekor qilish")
def cancel_process(message):
  user_id = message.from_user.id
  user_states.pop(user_id, None)
  temp_data.pop(user_id, None)
  send_clean_message(
      message.chat.id,
      "🚫 Amaliyot bekor qilindi.",
      reply_markup=get_main_keyboard(user_id),
  )


@bot.message_handler(func=lambda msg: True)
def main_messages(message):
  user_id = message.from_user.id
  try:
    bot.delete_message(message.chat.id, message.message_id)
  except:
    pass

  unsub = check_sub(user_id)
  if unsub is not True and unsub:
    text = "⚠️ Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:"
    send_clean_message(
        message.chat.id, text, reply_markup=get_sub_keyboard(unsub)
    )
    return

  state = user_states.get(user_id)

  # Admin: Kanal qo'shish
  if state == "ADD_CHANNEL_WAIT" and user_id == ADMIN_ID:
    ch = message.text.strip()
    if not ch.startswith("@"):
      ch = "@" + ch
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
      cursor.execute("INSERT INTO channels (username) VALUES (?)", (ch,))
      conn.commit()
      send_clean_message(
          message.chat.id,
          f"✅ {ch} kanali qo'shildi!",
          reply_markup=get_main_keyboard(user_id),
      )
    except sqlite3.IntegrityError:
      send_clean_message(
          message.chat.id,
          "⚠ Bu kanal allaqachon mavjud.",
          reply_markup=get_main_keyboard(user_id),
      )
    conn.close()
    user_states.pop(user_id, None)
    return

  # Qidiruvlar
  if state == "SEARCH_NAME_WAIT":
    query = f"%{message.text.strip().lower()}%"
    user_states.pop(user_id, None)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name FROM animes WHERE LOWER(name) LIKE ?", (query,)
    )
    results = cursor.fetchall()
    conn.close()
    show_search_results(message.chat.id, results)
    return

  if state == "SEARCH_CODE_WAIT":
    query = message.text.strip().lower()
    user_states.pop(user_id, None)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name FROM animes WHERE LOWER(code) = ?", (query,)
    )
    results = cursor.fetchall()
    conn.close()
    show_search_results(message.chat.id, results)
    return

  # Anime qo'shish bosqichlari (Admin)
  if state == "ADD_NAME" and user_id == ADMIN_ID:
    temp_data[user_id]["name"] = message.text.strip()
    user_states[user_id] = "ADD_CODE"
    send_clean_message(
        message.chat.id,
        "🔢 Anime uchun kod/yashirin nom kiriting:",
        reply_markup=get_cancel_keyboard(),
    )
    return

  if state == "ADD_CODE" and user_id == ADMIN_ID:
    temp_data[user_id]["code"] = message.text.strip().lower()
    user_states[user_id] = "ADD_INFO"
    send_clean_message(
        message.chat.id,
        "📖 Anime haqida ma'lumot kiriting (o'tkazib yuborish uchun /skip):",
        reply_markup=get_cancel_keyboard(),
    )
    return

  if state == "ADD_INFO" and user_id == ADMIN_ID:
    info_text = (
        message.text.strip()
        if message.text != "/skip"
        else "Ma'lumot mavjud emas"
    )
    temp_data[user_id]["info"] = info_text
    user_states[user_id] = "ADD_PHOTO"
    send_clean_message(
        message.chat.id,
        "🖼 Muqova rasmini yuboring (o'tkazib yuborish uchun /skip):",
        reply_markup=get_cancel_keyboard(),
    )
    return

  if state == "ADD_PHOTO" and user_id == ADMIN_ID and message.text == "/skip":
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO animes (name, code, info, photo) VALUES (?, ?, ?, ?)",
        (
            temp_data[user_id]["name"],
            temp_data[user_id]["code"],
            temp_data[user_id]["info"],
            None,
        ),
    )
    anime_id = cursor.lastrowid
    conn.commit()
    conn.close()

    temp_data[user_id]["anime_id"] = anime_id
    user_states[user_id] = "ADD_VIDEO"
    send_clean_message(
        message.chat.id,
        (
            "✅ Jild yaratildi! Endi 1-qism uchun **video faylini**"
            " yuboring:"
        ),
        reply_markup=get_cancel_keyboard(),
    )
    return

  if state == "ADD_PART_NUM" and user_id == ADMIN_ID:
    part_num = message.text.strip()
    if not part_num.isdigit():
      send_clean_message(
          message.chat.id,
          "⚠️ Faqat musbat raqam kiriting:",
          reply_markup=get_cancel_keyboard(),
      )
      return

    anime_id = temp_data[user_id]["anime_id"]
    video_id = temp_data[user_id]["last_video_id"]

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO parts (anime_id, part_num, video_id) VALUES (?, ?, ?)",
        (anime_id, int(part_num), video_id),
    )
    conn.commit()
    conn.close()

    user_states.pop(user_id, None)

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(
            "➕ Yana qism qo'shish", callback_data=f"add_more_{anime_id}"
        ),
        types.InlineKeyboardButton("✅ Tamomlash", callback_data="finish_add"),
    )
    send_clean_message(
        message.chat.id,
        f"✅ {part_num}-qism saqlandi! Yana qism qo'shasizmi?",
        reply_markup=markup,
    )
    return

  # Asosiy Menyu Tugmalari
  if message.text == "🔍 Animelarni izlash":
    send_clean_message(
        message.chat.id,
        "🔍 Izlash usulini tanlang:",
        reply_markup=get_search_inline_keyboard(),
    )
  elif message.text == "📂 Mavjud animelar":
    send_clean_message(
        message.chat.id,
        "📂 Mavjud anime jildlari:",
        reply_markup=get_available_animes_keyboard(),
    )
  elif message.text == "🔥 Tavsiya etiladigan animelar":
    send_clean_message(
        message.chat.id,
        "🔥 Eng ko'p ko'rilgan animelar:",
        reply_markup=get_recommended_animes_keyboard(),
    )
  elif message.text == "➕ Yangi anime qo'shish" and user_id == ADMIN_ID:
    user_states[user_id] = "ADD_NAME"
    temp_data[user_id] = {}
    send_clean_message(
        message.chat.id,
        "📝 Yangi anime nomini kiriting:",
        reply_markup=get_cancel_keyboard(),
    )
  elif message.text == "⚙️ Animelarni boshqarish" and user_id == ADMIN_ID:
    send_clean_message(
        message.chat.id,
        "🗑 O'chirmoqchi bo'lgan animengizni tanlang:",
        reply_markup=get_available_animes_keyboard(for_admin=True),
    )
  elif message.text == "📢 Kanallarni boshqarish" and user_id == ADMIN_ID:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM channels")
    channels = [row[0] for row in cursor.fetchall()]
    conn.close()

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("➕ Kanal qo'shish", callback_data="add_channel")
    )
    for ch in channels:
      markup.add(
          types.InlineKeyboardButton(
              f"❌ O'chirish: {ch}", callback_data=f"del_ch_{ch}"
          )
      )

    ch_text = "\n".join(channels) if channels else "Hozircha kanallar yo'q"
    send_clean_message(
        message.chat.id,
        f"📢 **Ulangan kanallar:**\n\n{ch_text}",
        reply_markup=markup,
        parse_mode="Markdown",
    )
  elif message.text == "📊 Statistika" and user_id == ADMIN_ID:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM animes")
    total_animes = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM parts")
    total_parts = cursor.fetchone()[0]
    cursor.execute("SELECT SUM(views) FROM animes")
    total_views = cursor.fetchone()[0] or 0
    conn.close()

    text = (
        f"📊 <b>Bot Statistikasi:</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{total_users} ta</b>\n"
        f"🎬 Jami anime jildlari: <b>{total_animes} ta</b>\n"
        f"🎞 Jami qismlar: <b>{total_parts} ta</b>\n"
        f"👁 Jami ko'rishlar: <b>{total_views} marta</b>"
    )
    send_clean_message(message.chat.id, text, parse_mode="HTML")


# --- MEDIALAR HANDLER ---
@bot.message_handler(content_types=["photo", "video"])
def handle_media(message):
  user_id = message.from_user.id
  try:
    bot.delete_message(message.chat.id, message.message_id)
  except:
    pass

  state = user_states.get(user_id)

  if state == "ADD_PHOTO" and user_id == ADMIN_ID:
    if message.content_type != "photo":
      send_clean_message(
          message.chat.id, "⚠️ Iltimos, rasm yuboring yoki /skip bosing:"
      )
      return

    photo_id = message.photo[-1].file_id
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO animes (name, code, info, photo) VALUES (?, ?, ?, ?)",
        (
            temp_data[user_id]["name"],
            temp_data[user_id]["code"],
            temp_data[user_id]["info"],
            photo_id,
        ),
    )
    anime_id = cursor.lastrowid
    conn.commit()
    conn.close()

    temp_data[user_id]["anime_id"] = anime_id
    user_states[user_id] = "ADD_VIDEO"
    send_clean_message(
        message.chat.id,
        "✅ Jild yaratildi! Endi 1-qism uchun **video faylini** yuboring:",
        reply_markup=get_cancel_keyboard(),
    )
    return

  if state == "ADD_VIDEO" and user_id == ADMIN_ID:
    if message.content_type != "video":
      send_clean_message(
          message.chat.id, "⚠️ Iltimos, faqat video fayl yuboring:"
      )
      return

    temp_data[user_id]["last_video_id"] = message.video.file_id
    user_states[user_id] = "ADD_PART_NUM"
    send_clean_message(
        message.chat.id,
        "🔢 Ushbu video nechanchi qism? Raqamini kiriting:",
        reply_markup=get_cancel_keyboard(),
    )
    return


# --- CALLBACK QUERY HANDLER ---
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
  user_id = call.from_user.id
  data = call.data

  if data == "check_subscription":
    unsub = check_sub(user_id)
    if unsub is not True and unsub:
      bot.answer_callback_query(
          call.id, "❌ Hali hamma kanallarga a'zo bo'lmadingiz!", show_alert=True
      )
    else:
      bot.answer_callback_query(call.id, "✅ Obuna tasdiqlandi!")
      send_clean_message(
          call.message.chat.id,
          "👋 Xush kelibsiz! Kerakli bo'limni tanlang:",
          reply_markup=get_main_keyboard(user_id),
      )

  elif data == "add_channel" and user_id == ADMIN_ID:
    user_states[user_id] = "ADD_CHANNEL_WAIT"
    send_clean_message(
        call.message.chat.id,
        "📢 Kanal username-ini yuboring (Masalan: @kanal_username):",
        reply_markup=get_cancel_keyboard(),
    )
    bot.answer_callback_query(call.id)

  elif data.startswith("del_ch_") and user_id == ADMIN_ID:
    ch_name = data.replace("del_ch_", "")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM channels WHERE username = ?", (ch_name,))
    conn.commit()
    conn.close()
    send_clean_message(
        call.message.chat.id,
        f"✅ {ch_name} kanali o'chirildi!",
        reply_markup=get_main_keyboard(user_id),
    )
    bot.answer_callback_query(call.id)

  elif data == "search_by_name":
    user_states[user_id] = "SEARCH_NAME_WAIT"
    send_clean_message(
        call.message.chat.id,
        "📝 Anime nomini yozing:",
        reply_markup=get_cancel_keyboard(),
    )
    bot.answer_callback_query(call.id)

  elif data == "search_by_code":
    user_states[user_id] = "SEARCH_CODE_WAIT"
    send_clean_message(
        call.message.chat.id,
        "🔢 Anime kodini yozing:",
        reply_markup=get_cancel_keyboard(),
    )
    bot.answer_callback_query(call.id)

  elif data.startswith("delete_anime_") and user_id == ADMIN_ID:
    anime_id = int(data.replace("delete_anime_", ""))
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM parts WHERE anime_id = ?", (anime_id,))
    cursor.execute("DELETE FROM animes WHERE id = ?", (anime_id,))
    conn.commit()
    conn.close()
    bot.answer_callback_query(call.id)
    send_clean_message(
        call.message.chat.id,
        "🗑 Anime muvaffaqiyatli o'chirildi.",
        reply_markup=get_main_keyboard(user_id),
    )
    import threading
import os

# Botni alohida fonda ishga tushiruvchi funksiya
def start_bot():
    bot.infinity_polling(skip_pending=True)

if __name__ == "__main__":
    # 1. Telegram bot uchun alohida oqim ochamiz
    bot_thread = threading.Thread(target=start_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # 2. Flask veb-serverini Render talab qiladigan portda ishga tushiramiz
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
