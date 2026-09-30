import os
import sqlite3
import threading
from flask import Flask
import telebot
from telebot import types

# --- SOZLAMALAR ---
TOKEN = "8987164421:AAE6XMCpHqNRIzio-xfp2IueJoKtQK_ZIbc"
ADMIN_ID = 7986354170

bot = telebot.TeleBot(TOKEN)
DB_FILE = "bot_data.db"

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


# --- MA'LUMOTLAR BAZASI ---
def init_db():
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  cursor.execute(
      "CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)"
  )
  cursor.execute(
      "CREATE TABLE IF NOT EXISTS channels (username TEXT PRIMARY KEY)"
  )
  cursor.execute("""CREATE TABLE IF NOT EXISTS animes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        code TEXT,
        info TEXT,
        photo TEXT,
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


init_db()

user_states = {}
temp_data = {}
user_last_messages = {}


# --- XABARLARNI TOZALASH MANTIG'I ---
def add_bot_message_to_history(chat_id, msg_id, protect=False):
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


# --- INLINE ASOSIY MENYU (FAQAT SHARCHA ICHIDA) ---
def get_main_inline_menu(user_id):
  markup = types.InlineKeyboardMarkup(row_width=1)
  markup.add(
      types.InlineKeyboardButton(
          "🔍 Animelarni izlash", callback_data="menu_search"
      ),
      types.InlineKeyboardButton(
          "📂 Mavjud animelar", callback_data="menu_available"
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
            "📂 Mavjud jildga qism qo'shish", callback_data="admin_add_part"
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
  markup = types.InlineKeyboardMarkup(row_width=2)
  markup.add(
      types.InlineKeyboardButton(
          "📝 Nomi orqali", callback_data="search_by_name"
      ),
      types.InlineKeyboardButton("🔢 Kodi orqali", callback_data="search_by_code"),
  )
  markup.add(
      types.InlineKeyboardButton(
          "⬅️ Asosiy menyu", callback_data="back_to_main"
      )
  )
  return markup


def get_available_animes_keyboard(action_type="show"):
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
      btn_text = f"🎬 {name} ({parts_count}-qism)"

      if action_type == "add_part":
        cb = f"select_anime_for_part_{anime_id}"
      elif action_type == "admin_opt":
        cb = f"admin_anime_opt_{anime_id}"
      else:
        cb = f"show_anime_{anime_id}"

      markup.add(types.InlineKeyboardButton(btn_text, callback_data=cb))

  markup.add(
      types.InlineKeyboardButton("⬅ Asosiy menyu", callback_data="back_to_main")
  )
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
    markup.add(
        types.InlineKeyboardButton(
            "⬅️ Asosiy menyu", callback_data="back_to_main"
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
  markup.add(
      types.InlineKeyboardButton("⬅️ Asosiy menyu", callback_data="back_to_main")
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
          "⬅️ Orqaga", callback_data="menu_available"
      ),
      types.InlineKeyboardButton(
          "🏠 Asosiy menyu", callback_data="back_to_main"
      ),
  )
  return markup


def show_search_results(chat_id, results):
  if not results:
    send_clean_message(chat_id, "❌ Afsuski, bunday anime topilmadi.")
    return
  markup = types.InlineKeyboardMarkup(row_width=1)
  for anime_id, name in results:
    markup.add(
        types.InlineKeyboardButton(
            "🎬 " + name, callback_data=f"show_anime_{anime_id}"
        )
    )
  markup.add(
      types.InlineKeyboardButton("⬅️ Asosiy menyu", callback_data="back_to_main")
  )
  send_clean_message(chat_id, "🔎 Topilgan animelar:", reply_markup=markup)


# --- 🌐 INLINE QUERY (GURUHDA QIDIRISH) ---
@bot.inline_handler(func=lambda query: True)
def inline_query_handler(query):
  query_text = query.query.strip().lower()
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()

  if query_text:
    cursor.execute(
        "SELECT id, name, info, photo, code FROM animes WHERE LOWER(name) LIKE"
        " ? LIMIT 10",
        (f"%{query_text}%",),
    )
  else:
    cursor.execute(
        "SELECT id, name, info, photo, code FROM animes ORDER BY id DESC LIMIT 10"
    )

  animes = cursor.fetchall()
  conn.close()

  results = []
  bot_username = bot.get_me().username

  for anime_id, name, info, photo, code in animes:
    desc = info if info else "Ma'lumot mavjud emas"
    text = (
        f"🎬 <b>{name}</b>\n\n📖 {desc}\n\n🔑 <b>Kod:</b> <code>{code}</code>"
    )
    bot_link = f"https://t.me/{bot_username}?start=anime_{anime_id}"

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("👀 Animeni ko'rish", url=bot_link)
    )

    if photo:
      results.append(
          types.InlineQueryResultPhoto(
              id=str(anime_id),
              photo_url=photo,
              thumb_url=photo,
              title=name,
              description=desc[:100],
              caption=text,
              parse_mode="HTML",
              reply_markup=markup,
          )
      )
    else:
      results.append(
          types.InlineQueryResultArticle(
              id=str(anime_id),
              title=name,
              description=desc[:100],
              input_message_content=types.InputTextMessageContent(
                  message_text=text, parse_mode="HTML"
              ),
              reply_markup=markup,
          )
      )

  bot.answer_inline_query(query.id, results, cache_time=1)


# --- /start VA DEEP-LINK ---
@bot.message_handler(commands=["start"])
def start_cmd(message):
  user_id = message.from_user.id

  # Pastki menyuni (Reply Keyboard) tozalash uchun bo'sh obyekt beramiz
  remove_markup = types.ReplyKeyboardRemove()

  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
  conn.commit()
  conn.close()

  user_states.pop(user_id, None)
  temp_data.pop(user_id, None)

  unsub = check_sub(user_id)
  if unsub is not True and unsub:
    text = "⚠ Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:"
    bot.send_message(
        message.chat.id, text, reply_markup=get_sub_keyboard(unsub)
    )
    return

  args = message.text.split()
  if len(args) > 1 and args[1].startswith("anime_"):
    try:
      anime_id = int(args[1].replace("anime_", ""))
      conn = sqlite3.connect(DB_FILE)
      cursor = conn.cursor()
      cursor.execute(
          "SELECT name, info, photo, views, code FROM animes WHERE id = ?",
          (anime_id,),
      )
      anime = cursor.fetchone()

      if anime:
        cursor.execute(
            "UPDATE animes SET views = views + 1 WHERE id = ?", (anime_id,)
        )
        conn.commit()
      conn.close()

      if anime:
        name, info, photo, views, code = anime
        text = (
            f"🎬 <b>{name}</b>\n\n📖 {info}\n\n🔑 Kodi: <code>{code}</code>\n\n👁"
            f" Ko'rildi: {views+1} marta"
        )
        markup = get_anime_folder_keyboard(anime_id)

        # Reply menyuni yashirish uchun avval xabar yuboramiz
        bot.send_message(
            message.chat.id, "⬇️ Menyuni yopdim", reply_markup=remove_markup
        )
        if photo:
          send_clean_photo(
              message.chat.id,
              photo,
              text,
              reply_markup=markup,
              parse_mode="HTML",
              protect=True,
          )
        else:
          send_clean_message(
              message.chat.id,
              text,
              reply_markup=markup,
              parse_mode="HTML",
              protect=True,
          )
        return
    except Exception:
      pass

  text = "👋 Xush kelibsiz! Kerakli bo'limni tanlang:"
  bot.send_message(
      message.chat.id, "⬇️ Menyuni yopdim", reply_markup=remove_markup
  )
  send_clean_message(
      message.chat.id, text, reply_markup=get_main_inline_menu(user_id)
  )


@bot.message_handler(func=lambda msg: True)
def main_messages(message):
  user_id = message.from_user.id

  unsub = check_sub(user_id)
  if unsub is not True and unsub:
    text = "⚠️ Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:"
    send_clean_message(
        message.chat.id, text, reply_markup=get_sub_keyboard(unsub)
    )
    return

  state = user_states.get(user_id)

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
          reply_markup=get_main_inline_menu(user_id),
      )
    except sqlite3.IntegrityError:
      send_clean_message(
          message.chat.id,
          "⚠ Bu kanal allaqachon mavjud.",
          reply_markup=get_main_inline_menu(user_id),
      )
    conn.close()
    user_states.pop(user_id, None)
    return

  text_val = message.text.strip().lower()
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  cursor.execute(
      "SELECT id, name, info, photo, views, code FROM animes WHERE LOWER(code)"
      " = ?",
      (text_val,),
  )
  anime = cursor.fetchone()
  if anime:
    anime_id, name, info, photo, views, code = anime
    cursor.execute(
        "UPDATE animes SET views = views + 1 WHERE id = ?", (anime_id,)
    )
    conn.commit()
    conn.close()

    text = (
        f"🎬 <b>{name}</b>\n\n📖 {info}\n\n🔑 Kodi: <code>{code}</code>\n\n👁"
        f" Ko'rildi: {views+1} marta"
    )
    markup = get_anime_folder_keyboard(anime_id)
    if photo:
      send_clean_photo(
          message.chat.id,
          photo,
          text,
          reply_markup=markup,
          parse_mode="HTML",
          protect=True,
      )
    else:
      send_clean_message(
          message.chat.id,
          text,
          reply_markup=markup,
          parse_mode="HTML",
          protect=True,
      )
    return
  conn.close()

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

  if state == "ADD_NAME" and user_id == ADMIN_ID:
    temp_data[user_id]["name"] = message.text.strip()
    user_states[user_id] = "ADD_CODE"
    send_clean_message(
        message.chat.id, "🔢 Anime uchun kod/yashirin nom kiriting:"
    )
    return

  if state == "ADD_CODE" and user_id == ADMIN_ID:
    temp_data[user_id]["code"] = message.text.strip().lower()
    user_states[user_id] = "ADD_INFO"
    send_clean_message(
        message.chat.id,
        "📖 Anime haqida ma'lumot kiriting (o'tkazib yuborish uchun /skip):",
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
    user_states[user_id] = "ADD_AUTO_VIDEO"
    send_clean_message(
        message.chat.id,
        "✅ Yangi anime yaratildi! Endi **1-qism videosini** yuboring:",
    )
    return


# --- MEDIA HANDLER ---
@bot.message_handler(content_types=["photo", "video"])
def handle_media(message):
  user_id = message.from_user.id
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
    user_states[user_id] = "ADD_AUTO_VIDEO"
    send_clean_message(
        message.chat.id,
        "✅ Yangi anime yaratildi! Endi **1-qism videosini** yuboring:",
    )
    return

  if state == "ADD_AUTO_VIDEO" and user_id == ADMIN_ID:
    if message.content_type != "video":
      send_clean_message(
          message.chat.id, "⚠ Iltimos, faqat video fayl yuboring:"
      )
      return

    anime_id = temp_data[user_id]["anime_id"]
    video_id = message.video.file_id

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT MAX(part_num) FROM parts WHERE anime_id = ?", (anime_id,)
    )
    res = cursor.fetchone()[0]
    next_part = 1 if res is None else res + 1

    cursor.execute(
        "INSERT INTO parts (anime_id, part_num, video_id) VALUES (?, ?, ?)",
        (anime_id, next_part, video_id),
    )
    conn.commit()

    cursor.execute("SELECT name FROM animes WHERE id = ?", (anime_id,))
    anime_name = cursor.fetchone()[0]
    conn.close()

    temp_data[user_id]["anime_id"] = anime_id

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(
            "➕ Yana qism qo'shish", callback_data=f"add_next_auto_{anime_id}"
        ),
        types.InlineKeyboardButton("✅ Tamomlash", callback_data="finish_adding"),
    )

    send_clean_message(
        message.chat.id,
        f"✅ <b>{anime_name}</b> animasiga **{next_part}-qism** qo'shildi! 🎬\n\nYana"
        " qism qo'shasizmi?",
        reply_markup=markup,
        parse_mode="HTML",
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
          reply_markup=get_main_inline_menu(user_id),
      )

  elif data == "back_to_main":
    bot.answer_callback_query(call.id)
    send_clean_message(
        call.message.chat.id,
        "👋 Kerakli bo'limni tanlang:",
        reply_markup=get_main_inline_menu(user_id),
    )

  elif data == "menu_search":
    bot.answer_callback_query(call.id)
    send_clean_message(
        call.message.chat.id,
        "🔍 Izlash usulini tanlang:",
        reply_markup=get_search_inline_keyboard(),
    )

  elif data == "menu_available":
    bot.answer_callback_query(call.id)
    send_clean_message(
        call.message.chat.id,
        "📂 Mavjud anime jildlari:",
        reply_markup=get_available_animes_keyboard(action_type="show"),
    )

  elif data == "menu_recommended":
    bot.answer_callback_query(call.id)
    send_clean_message(
        call.message.chat.id,
        "🔥 Eng ko'p ko'rilgan animelar:",
        reply_markup=get_recommended_animes_keyboard(),
    )

  elif data == "admin_add_folder" and user_id == ADMIN_ID:
    user_states[user_id] = "ADD_NAME"
    temp_data[user_id] = {}
    bot.answer_callback_query(call.id)
    send_clean_message(
        call.message.chat.id, "📝 Yangi anime (papka) nomini kiriting:"
    )

  elif data == "admin_add_part" and user_id == ADMIN_ID:
    bot.answer_callback_query(call.id)
    send_clean_message(
        call.message.chat.id,
        "📂 Qaysi anime jildiga yangi qism qo'shmoqchisiz? Tanlang:",
        reply_markup=get_available_animes_keyboard(action_type="add_part"),
    )

  elif data == "admin_manage" and user_id == ADMIN_ID:
    bot.answer_callback_query(call.id)
    send_clean_message(
        call.message.chat.id,
        "⚙ Boshqarish uchun animeni tanlang:",
        reply_markup=get_available_animes_keyboard(action_type="admin_opt"),
    )

  elif data == "admin_channels" and user_id == ADMIN_ID:
    bot.answer_callback_query(call.id)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM channels")
    channels = [row[0] for row in cursor.fetchall()]
    conn.close()

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(
            "➕ Kanal qo'shish", callback_data="add_channel"
        )
    )
    for ch in channels:
      markup.add(
          types.InlineKeyboardButton(
              f"❌ O'chirish: {ch}", callback_data=f"del_ch_{ch}"
          )
      )
    markup.add(
        types.InlineKeyboardButton(
            "⬅️️ Asosiy menyu", callback_data="back_to_main"
        )
    )

    ch_text = "\n".join(channels) if channels else "Hozircha kanallar yo'q"
    send_clean_message(
        call.message.chat.id,
        f"📢 **Ulangan kanallar:**\n\n{ch_text}",
        reply_markup=markup,
        parse_mode="Markdown",
    )

  elif data == "admin_stats" and user_id == ADMIN_ID:
    bot.answer_callback_query(call.id)
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

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            "⬅️ Asosiy menyu", callback_data="back_to_main"
        )
    )

    text = (
        f"📊 <b>Bot Statistikasi:</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{total_users} ta</b>\n"
        f"🎬 Jami anime jildlari: <b>{total_animes} ta</b>\n"
        f"🎞 Jami qismlar: <b>{total_parts} ta</b>\n"
        f"👁 Jami ko'rishlar: <b>{total_views} marta</b>"
    )
    send_clean_message(
        call.message.chat.id, text, reply_markup=markup, parse_mode="HTML"
    )

  elif data == "add_channel" and user_id == ADMIN_ID:
    user_states[user_id] = "ADD_CHANNEL_WAIT"
    bot.answer_callback_query(call.id)
    send_clean_message(
        call.message.chat.id,
        "📢 Kanal username-ini yuboring (Masalan: @kanal_username):",
    )

  elif data.startswith("del_ch_") and user_id == ADMIN_ID:
    ch_name = data.replace("del_ch_", "")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM channels WHERE username = ?", (ch_name,))
    conn.commit()
    conn.close()
    bot.answer_callback_query(call.id, f"{ch_name} o'chirildi!")
    send_clean_message(
        call.message.chat.id,
        f"✅ {ch_name} kanali o'chirildi!",
        reply_markup=get_main_inline_menu(user_id),
    )

  elif data == "search_by_name":
    user_states[user_id] = "SEARCH_NAME_WAIT"
    bot.answer_callback_query(call.id)
    send_clean_message(call.message.chat.id, "📝 Anime nomini yozing:")

  elif data == "search_by_code":
    user_states[user_id] = "SEARCH_CODE_WAIT"
    bot.answer_callback_query(call.id)
    send_clean_message(call.message.chat.id, "🔢 Anime kodini yozing:")

  elif data.startswith("select_anime_for_part_") and user_id == ADMIN_ID:
    anime_id = int(data.replace("select_anime_for_part_", ""))
    user_states[user_id] = "ADD_AUTO_VIDEO"
    temp_data[user_id] = {"anime_id": anime_id}
    bot.answer_callback_query(call.id)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT MAX(part_num) FROM parts WHERE anime_id = ?", (anime_id,)
    )
    res = cursor.fetchone()[0]
    next_num = 1 if res is None else res + 1
    cursor.execute("SELECT name FROM animes WHERE id = ?", (anime_id,))
    an_name = cursor.fetchone()[0]
    conn.close()

    send_clean_message(
        call.message.chat.id,
        f"🎬 <b>{an_name}</b> uchun **{next_num}-qism** videosini yuboring:",
        parse_mode="HTML",
    )

  elif data.startswith("admin_anime_opt_") and user_id == ADMIN_ID:
    anime_id = int(data.replace("admin_anime_opt_", ""))
    bot.answer_callback_query(call.id)

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(
            "➕ Keyingi qismni qo'shish",
            callback_data=f"add_next_auto_{anime_id}",
        ),
        types.InlineKeyboardButton(
            "🗑 Animeniki butunlay o'chirish",
            callback_data=f"delete_anime_{anime_id}",
        ),
        types.InlineKeyboardButton("⬅ Ortga", callback_data="admin_manage"),
    )
    send_clean_message(call.message.chat.id, "Tanlang:", reply_markup=markup)

  elif data.startswith("add_next_auto_") and user_id == ADMIN_ID:
    anime_id = int(data.replace("add_next_auto_", ""))
    user_states[user_id] = "ADD_AUTO_VIDEO"
    temp_data[user_id] = {"anime_id": anime_id}
    bot.answer_callback_query(call.id)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT MAX(part_num) FROM parts WHERE anime_id = ?", (anime_id,)
    )
    res = cursor.fetchone()[0]
    next_num = 1 if res is None else res + 1
    cursor.execute("SELECT name FROM animes WHERE id = ?", (anime_id,))
    an_name = cursor.fetchone()[0]
    conn.close()

    send_clean_message(
        call.message.chat.id,
        f"🎬 <b>{an_name}</b> uchun **{next_num}-qism** videosini yuboring:",
        parse_mode="HTML",
    )

  elif data == "finish_adding":
    bot.answer_callback_query(call.id, "Barcha qismlar saqlandi!")
    user_states.pop(user_id, None)
    temp_data.pop(user_id, None)
    send_clean_message(
        call.message.chat.id,
        "✅ Jarayon yakunlandi. Kerakli bo'limni tanlang:",
        reply_markup=get_main_inline_menu(user_id),
    )

  elif data.startswith("delete_anime_") and user_id == ADMIN_ID:
    anime_id = int(data.replace("delete_anime_", ""))
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM parts WHERE anime_id = ?", (anime_id,))
    cursor.execute("DELETE FROM animes WHERE id = ?", (anime_id,))
    conn.commit()
    conn.close()
    bot.answer_callback_query(call.id, "Anime o'chirildi!")
    send_clean_message(
        call.message.chat.id,
        "🗑 Anime muvaffaqiyatli o'chirildi.",
        reply_markup=get_main_inline_menu(user_id),
    )

  elif data.startswith("show_anime_"):
    anime_id = int(data.replace("show_anime_", ""))
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name, info, photo, views, code FROM animes WHERE id = ?",
        (anime_id,),
    )
    anime = cursor.fetchone()

    cursor.execute(
        "UPDATE animes SET views = views + 1 WHERE id = ?", (anime_id,)
    )
    conn.commit()
    conn.close()

    if not anime:
      bot.answer_callback_query(call.id, "❌ Anime topilmadi!", show_alert=True)
      return

    name, info, photo, views, code = anime
    text = (
        f"🎬 <b>{name}</b>\n\n📖 {info}\n\n🔑 Kodi: <code>{code}</code>\n\n👁"
        f" Ko'rildi: {views+1} marta"
    )

    markup = get_anime_folder_keyboard(anime_id)
    bot.answer_callback_query(call.id)

    if photo:
      send_clean_photo(
          call.message.chat.id,
          photo,
          text,
          reply_markup=markup,
          parse_mode="HTML",
          protect=True,
      )
    else:
      send_clean_message(
          call.message.chat.id,
          text,
          reply_markup=markup,
          parse_mode="HTML",
          protect=True,
      )

  elif data.startswith("get_part_"):
    parts_data = data.replace("get_part_", "").split("_")
    anime_id = int(parts_data[0])
    part_num = int(parts_data[1])

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT video_id FROM parts WHERE anime_id = ? AND part_num = ?",
        (anime_id, part_num),
    )
    part = cursor.fetchone()
    conn.close()

    bot.answer_callback_query(call.id)
    if part:
      video_id = part[0]
      bot.send_video(
          call.message.chat.id, video_id, caption=f"🎬 {part_num}-qism"
      )
    else:
      bot.answer_callback_query(
          call.id, "❌ Video topilmadi!", show_alert=True
      )


# --- BOTNI ISHGA TUSHIRISH ---
if __name__ == "__main__":
  keep_alive()
  bot.infinity_polling(skip_pending=True)
