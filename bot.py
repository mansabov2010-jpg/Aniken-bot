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
    bot.set_my_commands(commands, scope=types.BotCommandScopeAllGroupChats())
  except Exception:
    pass


# --- MA'LUMOTLAR BAZASI VA BOSHLANG'ICH ANIMELAR ---
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
        secret_name TEXT,
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


# --- INLINE MENYULAR ---
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
            "✏️ Anime jildlarini tahrirlash", callback_data="admin_edit_menu"
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
      types.InlineKeyboardButton(
          "🕵‍♂️ Yashirin nom orqali", callback_data="search_by_secret"
      ),
      types.InlineKeyboardButton("🔢 Kodi orqali", callback_data="search_by_code"),
  )
  markup.add(
      types.InlineKeyboardButton(
          "⬅ Asosiy menyu", callback_data="back_to_main"
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
      elif action_type == "edit_folder":
        cb = f"select_edit_folder_{anime_id}"
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


# --- QISMLARNI 15 TATADAN SAHIFALASH (PAGINATION) ---
def get_anime_folder_keyboard(anime_id, page=1):
  markup = types.InlineKeyboardMarkup(row_width=5)
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  cursor.execute(
      "SELECT part_num FROM parts WHERE anime_id = ? ORDER BY part_num ASC",
      (anime_id,),
  )
  parts = [row[0] for row in cursor.fetchall()]
  conn.close()

  items_per_page = 15
  total_pages = (len(parts) + items_per_page - 1) // items_per_page
  if total_pages == 0:
    total_pages = 1

  if page > total_pages:
    page = total_pages
  if page < 1:
    page = 1

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
            "⬅️", callback_data=f"page_{anime_id}_{page-1}"
        )
    )

  nav_buttons.append(
      types.InlineKeyboardButton("❌", callback_data="menu_available")
  )

  if page < total_pages:
    nav_buttons.append(
        types.InlineKeyboardButton(
            "➡️", callback_data=f"page_{anime_id}_{page+1}"
        )
    )

  markup.add(*nav_buttons)
  markup.add(
      types.InlineKeyboardButton(
          "🏠 Asosiy menyu", callback_data="back_to_main"
      )
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


# --- INLINE QUERY ---
@bot.inline_handler(func=lambda query: True)
def inline_query_handler(query):
  text = query.query.strip().lower()
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  if text:
    cursor.execute(
        "SELECT id, name, secret_name, info, photo, code FROM animes WHERE"
        " LOWER(name) LIKE ? OR LOWER(secret_name) LIKE ? OR LOWER(code) = ?",
        (f"%{text}%", f"%{text}%", text),
    )
  else:
    cursor.execute(
        "SELECT id, name, secret_name, info, photo, code FROM animes LIMIT 10"
    )
  animes = cursor.fetchall()
  conn.close()

  results = []
  bot_info = bot.get_me()
  bot_username = bot_info.username

  for anime_id, name, secret_name, info, photo, code in animes:
    deeplink_url = f"https://t.me/{bot_username}?start=anime_{anime_id}"

    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton(
            "📺 Anime tomosha qilish", url=deeplink_url
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
            title=f"🎬 {name} ({secret_name})",
            description=f"Kodi: {code} | {description}",
            thumb_url=thumb_url,
            input_message_content=types.InputTextMessageContent(
                message_text=(
                    f"🎬 <b>{name}</b>\n🕵️‍♂️ Yashirin nom: <i>{secret_name}</i>\n\n📖"
                    f" {info}\n\n🔑 Kodi: <code>{code}</code>\n\n⬇ Animeni"
                    " ko'rish uchun pastdagi tugmani bosing:"
                ),
                parse_mode="HTML",
            ),
            reply_markup=keyboard,
        )
    )

  bot.answer_inline_query(query.id, results, cache_time=1)


# --- /start VA DEEP-LINK ---
@bot.message_handler(commands=["start"])
def start_cmd(message):
  user_id = message.from_user.id
  chat_id = message.chat.id

  if chat_id < 0:
    bot.reply_to(
        message,
        "🤖 Bot faol holatda! Animelarni qidirish uchun /anime [Nomi] deb"
        " yozing yoki shaxsiy chatga o'ting.",
    )
    return

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
    bot.send_message(chat_id, text, reply_markup=get_sub_keyboard(unsub))
    return

  args = message.text.split()
  if len(args) > 1 and args[1].startswith("anime_"):
    try:
      anime_id = int(args[1].replace("anime_", ""))
      conn = sqlite3.connect(DB_FILE)
      cursor = conn.cursor()
      cursor.execute(
          "SELECT name, secret_name, info, photo, views, code FROM animes WHERE"
          " id = ?",
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
        name, secret_name, info, photo, views, code = anime
        text = (
            f"🎬 <b>{name}</b>\n🕵️‍♂️ Yashirin nom: <i>{secret_name}</i>\n\n📖"
            f" {info}\n\n🔑 Kodi: <code>{code}</code>\n\n👁 Ko'rildi:"
            f" {views+1} marta"
        )
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
  send_clean_message(
      chat_id, text, reply_markup=get_main_inline_menu(user_id)
  )


# --- GURUHDA QIDIRISH ---
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
    bot.reply_to(message, "⚠ Anime nomini yozing. Masalan: /anime Naruto")
    return

  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  cursor.execute(
      "SELECT id, name, secret_name, info, photo, code FROM animes WHERE"
      " LOWER(name) LIKE ? OR LOWER(secret_name) LIKE ? OR LOWER(code) = ?",
      (f"%{query}%", f"%{query}%", query),
  )
  animes = cursor.fetchall()
  conn.close()

  if not animes:
    bot.reply_to(message, "❌ Afsuski, bunday anime topilmadi.")
    return

  bot_info = bot.get_me()
  bot_username = bot_info.username

  for anime_id, name, secret_name, info, photo, code in animes:
    deeplink_url = f"https://t.me/{bot_username}?start=anime_{anime_id}"
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("📺 Anime tomosha qilish", url=deeplink_url)
    )

    desc = info[:150] if info else "Ma'lumot yo'q"
    caption = (
        f"🎬 <b>{name}</b>\n🕵️‍♂️ Yashirin nom: <i>{secret_name}</i>\n\n📖"
        f" {desc}\n\n🔑 Kodi: <code>{code}</code>\n\n⬇️ Animeni to'liq ko'rish"
        " uchun pastdagi tugmani bosing:"
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


# --- SHAXSIY CHATDAGI MULOQOT VA BARCHA PROCESSRLAR ---
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

  # 1. Kanal qo'shish
  if state == "ADD_CHANNEL_WAIT" and user_id == ADMIN_ID:
    ch = text_val
    if not ch.startswith("@"):
      ch = "@" + ch
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
      cursor.execute("INSERT INTO channels (username) VALUES (?)", (ch,))
      conn.commit()
      send_clean_message(
          chat_id,
          f"✅ {ch} kanali qo'shildi!",
          reply_markup=get_main_inline_menu(user_id),
      )
    except sqlite3.IntegrityError:
      send_clean_message(
          chat_id,
          "⚠ Bu kanal allaqachon mavjud.",
          reply_markup=get_main_inline_menu(user_id),
      )
    conn.close()
    user_states.pop(user_id, None)
    return

  # 2. Yangi anime qo'shish qadamlari
  if user_id == ADMIN_ID:
    if state == "ADD_NAME":
      temp_data[user_id]["name"] = text_val
      user_states[user_id] = "ADD_SECRET_NAME"
      send_clean_message(
          chat_id, "🕵️‍♂️ Anime uchun yashirin nom (kalit so'z) kiriting:"
      )
      return

    elif state == "ADD_SECRET_NAME":
      temp_data[user_id]["secret_name"] = text_val
      user_states[user_id] = "ADD_CODE"
      send_clean_message(
          chat_id, "🔢 Anime uchun maxsus raqamli kod kiriting (masalan: 12):"
      )
      return

    elif state == "ADD_CODE":
      temp_data[user_id]["code"] = text_lower
      user_states[user_id] = "ADD_INFO"
      send_clean_message(
          chat_id,
          "📖 Anime haqida qisqacha ma'lumot kiriting (o'tkazib yuborish uchun"
          " /skip):",
      )
      return

    elif state == "ADD_INFO":
      info_text = (
          text_val if text_val != "/skip" else "Ma'lumot mavjud emas"
      )
      temp_data[user_id]["info"] = info_text
      user_states[user_id] = "ADD_PHOTO"
      send_clean_message(
          chat_id, "🖼 Muqova rasmini yuboring (o'tkazib yuborish uchun /skip):"
      )
      return

    # JILD TAHRIRLASH QADAMLARI
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

      conn = sqlite3.connect(DB_FILE)
      cursor = conn.cursor()
      cursor.execute(
          "UPDATE animes SET name = ?, code = ?, photo = ? WHERE id = ?",
          (new_name, new_code, new_photo, anime_id),
      )
      conn.commit()
      conn.close()

      user_states.pop(user_id, None)
      temp_data.pop(user_id, None)
      send_clean_message(
          chat_id,
          "✅ Jild muvaffaqiyatli tahrirlandi!",
          reply_markup=get_main_inline_menu(user_id),
      )
      return

    # QISM TAHRIRLASH QADAMLARI
    elif state == "ADMIN_EDIT_PART_SEARCH":
      conn = sqlite3.connect(DB_FILE)
      cursor = conn.cursor()
      cursor.execute(
          "SELECT id, name FROM animes WHERE LOWER(name) LIKE ? OR LOWER(code)"
          " = ?",
          (f"%{text_lower}%", text_lower),
      )
      res = cursor.fetchone()
      conn.close()

    if res:
        temp_data[user_id] = {"anime_id": res[0], "anime_name": res[1]}
        user_states[user_id] = "ADMIN_EDIT_PART_NUM"
        send_clean_message(
            chat_id,
            f"✅ Anime topildi: **{res[1]}**\n\n🔢 Nechanchi"
            " qismni tahrirlamoqchisiz? (Faqat raqam kiriting):",
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
          chat_id, "🎬 Endi ushbu qism uchun yangi videoni yuboring:"
      )
      return

  # 3. Qidirish so'rovlari
  if state == "SEARCH_NAME_WAIT":
    user_states.pop(user_id, None)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name FROM animes WHERE LOWER(name) LIKE ?",
        (f"%{text_lower}%",),
    )
    results = cursor.fetchall()
    conn.close()
    show_search_results(chat_id, results)
    return

  if state == "SEARCH_SECRET_WAIT":
    user_states.pop(user_id, None)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name FROM animes WHERE LOWER(secret_name) LIKE ?",
        (f"%{text_lower}%",),
    )
    results = cursor.fetchall()
    conn.close()
    show_search_results(chat_id, results)
    return

  if state == "SEARCH_CODE_WAIT":
    user_states.pop(user_id, None)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name FROM animes WHERE LOWER(code) = ?", (text_lower,)
    )
    results = cursor.fetchall()
    conn.close()
    show_search_results(chat_id, results)
    return

  # 4. Kod orqali bevosita topish
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  cursor.execute(
      "SELECT id, name, secret_name, info, photo, views, code FROM animes WHERE"
      " LOWER(code) = ?",
      (text_lower,),
  )
  anime = cursor.fetchone()
  if anime:
    anime_id, name, secret_name, info, photo, views, code = anime
    cursor.execute(
        "UPDATE animes SET views = views + 1 WHERE id = ?", (anime_id,)
    )
    conn.commit()
    conn.close()

    text = (
        f"🎬 <b>{name}</b>\n🕵️‍♂️ Yashirin nom: <i>{secret_name}</i>\n\n📖"
        f" {info}\n\n🔑 Kodi: <code>{code}</code>\n\n👁 Ko'rildi:"
        f" {views+1} marta"
    )
    markup = get_anime_folder_keyboard(anime_id, page=1)
    if photo:
      send_clean_photo(
          chat_id, text, reply_markup=markup, parse_mode="HTML", protect=True
      )
    else:
      send_clean_message(
          chat_id, text, reply_markup=markup, parse_mode="HTML", protect=True
      )
    return
  conn.close()

  # Agar hech qaysi holatga tushmasa, bosh menyu
  send_clean_message(
      chat_id,
      "🤖 Kerakli bo'limni tanlang:",
      reply_markup=get_main_inline_menu(user_id),
  )


# --- MEDIA HANDLER (RASM VA VIDEO QABUL QILISH) ---
@bot.message_handler(content_types=["photo", "video", "document"])
def handle_media(message):
  user_id = message.from_user.id
  chat_id = message.chat.id
  if chat_id < 0:
    return

  state = user_states.get(user_id)

  # Rasmni qabul qilish (Yangi anime uchun)
  if state == "ADD_PHOTO" and user_id == ADMIN_ID:
    photo_id = ""
    if message.content_type == "photo":
      photo_id = message.photo[-1].file_id
    elif message.caption and message.caption.lower() == "/skip":
      photo_id = ""

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO animes (name, secret_name, code, info, photo) VALUES (?,"
        " ?, ?, ?, ?)",
        (
            temp_data[user_id]["name"],
            temp_data[user_id]["secret_name"],
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
        chat_id,
        "✅ Yangi anime yaratildi! Endi ushbu anime uchun **1-qism videosini**"
        " yuboring:",
    )
    return

  # Videoni qabul qilish (Yangi anime/qism uchun)
  if state == "ADD_AUTO_VIDEO" and user_id == ADMIN_ID:
    if message.content_type != "video":
      send_clean_message(
          chat_id, "⚠ Iltimos, anime uchun to'g'ri video fayl yuboring:"
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
        chat_id,
        f"✅ <b>{anime_name}</b> animasiga **{next_part}-qism** qo'shildi! 🎬\n\nYana"
        " qism qo'shasizmi?",
        reply_markup=markup,
        parse_mode="HTML",
    )
    return

  # Jild rasmini tahrirlash uchun qabul qilish
  if state == "ADMIN_EDIT_FOLDER_PHOTO" and user_id == ADMIN_ID:
    photo_id = ""
    if message.content_type == "photo":
      photo_id = message.photo[-1].file_id

    temp_data[user_id]["edit_photo"] = photo_id
    user_states[user_id] = "ADMIN_EDIT_FOLDER_NAME"
    send_clean_message(chat_id, "📝 Yangi jild nomini kiriting:")
    return

  # Qism videosini tahrirlash uchun qabul qilish
  if state == "ADMIN_EDIT_PART_VIDEO" and user_id == ADMIN_ID:
    if message.content_type != "video":
      send_clean_message(
          chat_id, "⚠️ Iltimos, anime uchun to'g'ri video fayl yuboring:"
      )
      return

    anime_id = temp_data[user_id]["anime_id"]
    part_num = temp_data[user_id]["part_num"]
    video_id = message.video.file_id

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM parts WHERE anime_id = ? AND part_num = ?",
        (anime_id, part_num),
    )
    if cursor.fetchone():
      cursor.execute(
          "UPDATE parts SET video_id = ? WHERE anime_id = ? AND part_num = ?",
          (video_id, anime_id, part_num),
      )
    else:
      cursor.execute(
          "INSERT INTO parts (anime_id, part_num, video_id) VALUES (?, ?, ?)",
          (anime_id, part_num, video_id),
      )

    conn.commit()
    conn.close()

    user_states.pop(user_id, None)
    temp_data.pop(user_id, None)
    send_clean_message(
        chat_id,
        f"✅ {part_num}-qism muvaffaqiyatli saqlandi!",
        reply_markup=get_main_inline_menu(user_id),
    )
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
      bot.answer_callback_query(
          call.id, "❌ Hali hamma kanallarga a'zo bo'lmadingiz!", show_alert=True
      )
    else:
      bot.answer_callback_query(call.id, "✅ Obuna tasdiqlandi!")
      send_clean_message(
          chat_id,
          "👋 Xush kelibsiz! Kerakli bo'limni tanlang:",
          reply_markup=get_main_inline_menu(user_id),
      )

  elif data == "back_to_main":
    user_states.pop(user_id, None)
    temp_data.pop(user_id, None)
    bot.answer_callback_query(call.id)
    send_clean_message(
        chat_id,
        "👋 Kerakli bo'limni tanlang:",
        reply_markup=get_main_inline_menu(user_id),
    )

  elif data == "menu_search":
    bot.answer_callback_query(call.id)
    send_clean_message(
        chat_id,
        "🔍 Izlash usulini tanlang:",
        reply_markup=get_search_inline_keyboard(),
    )

  elif data == "menu_available":
    bot.answer_callback_query(call.id)
    send_clean_message(
        chat_id,
        "📂 Mavjud anime jildlari:",
        reply_markup=get_available_animes_keyboard(action_type="show"),
    )

  elif data == "menu_recommended":
    bot.answer_callback_query(call.id)
    send_clean_message(
        chat_id,
        "🔥 Eng ko'p ko'rilgan animelar:",
        reply_markup=get_recommended_animes_keyboard(),
    )

  elif data == "admin_add_folder" and user_id == ADMIN_ID:
    user_states[user_id] = "ADD_NAME"
    temp_data[user_id] = {}
    bot.answer_callback_query(call.id)
    send_clean_message(chat_id, "📝 Yangi anime nomini kiriting:")

  elif data == "admin_add_part" and user_id == ADMIN_ID:
    bot.answer_callback_query(call.id)
    send_clean_message(
        chat_id,
        "📂 Qaysi anime jildiga yangi qism qo'shmoqchisiz? Tanlang:",
        reply_markup=get_available_animes_keyboard(action_type="add_part"),
    )

  # TAHRIRLASH MENYUSI
  elif data == "admin_edit_menu" and user_id == ADMIN_ID:
    bot.answer_callback_query(call.id)
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(
            "📁 Jild tahrirlash", callback_data="admin_edit_folder"
        ),
        types.InlineKeyboardButton(
            "🎬 Qism tahrirlash", callback_data="admin_edit_part"
        ),
        types.InlineKeyboardButton(
            "⬅️ Asosiy menyu", callback_data="back_to_main"
        ),
    )
    send_clean_message(
        chat_id, "✏️ Tahrirlash bo'limini tanlang:", reply_markup=markup
    )

  elif data == "admin_edit_folder" and user_id == ADMIN_ID:
    bot.answer_callback_query(call.id)
    send_clean_message(
        chat_id,
        "📁 Tahrirlash uchun animeni tanlang:",
        reply_markup=get_available_animes_keyboard(action_type="edit_folder"),
    )

  elif data.startswith("select_edit_folder_") and user_id == ADMIN_ID:
    anime_id = int(data.replace("select_edit_folder_", ""))
    bot.answer_callback_query(call.id)
    user_states[user_id] = "ADMIN_EDIT_FOLDER_PHOTO"
    temp_data[user_id] = {"anime_id": anime_id}
    send_clean_message(
        chat_id,
        "🖼 Yangi muqova rasmini yuboring (rasm kerak bo'lmasa /skip yuboring):",
    )

  elif data == "admin_edit_part" and user_id == ADMIN_ID:
    bot.answer_callback_query(call.id)
    user_states[user_id] = "ADMIN_EDIT_PART_SEARCH"
    send_clean_message(
        chat_id,
        "🎬 Tahrirlamoqchi bo'lgan animening kodi yoki nomini kiriting:",
    )

  elif data == "admin_manage" and user_id == ADMIN_ID:
    bot.answer_callback_query(call.id)
    send_clean_message(
        chat_id,
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

    bot_info = bot.get_me()
    add_group_url = f"https://t.me/{bot_info.username}?startgroup=true"

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(
            "➕ Kanal qo'shish", callback_data="add_channel"
        ),
        types.InlineKeyboardButton(
            "🤖 Botni guruhga qo'shish", url=add_group_url
        ),
    )
    for ch in channels:
      markup.add(
          types.InlineKeyboardButton(
              f"❌ O'chirish: {ch}", callback_data=f"del_ch_{ch}"
          )
      )
    markup.add(
        types.InlineKeyboardButton(
            "⬅ Asosiy menyu", callback_data="back_to_main"
        )
    )

    ch_text = "\n".join(channels) if channels else "Hozircha kanallar yo'q"
    send_clean_message(
        chat_id,
        f"📢 **Kanallarni boshqarish bo'limi:**\n\nUlangan"
        f" kanallar:\n{ch_text}",
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
    send_clean_message(chat_id, text, reply_markup=markup, parse_mode="HTML")

  elif data == "add_channel" and user_id == ADMIN_ID:
    user_states[user_id] = "ADD_CHANNEL_WAIT"
    bot.answer_callback_query(call.id)
    send_clean_message(
        chat_id, "📢 Kanal username-ini yuboring (Masalan: @kanal_username):"
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
        chat_id,
        f"✅ {ch_name} kanali o'chirildi!",
        reply_markup=get_main_inline_menu(user_id),
    )

  elif data == "search_by_name":
    user_states[user_id] = "SEARCH_NAME_WAIT"
    bot.answer_callback_query(call.id)
    send_clean_message(chat_id, "📝 Anime nomini yozing:")

  elif data == "search_by_secret":
    user_states[user_id] = "SEARCH_SECRET_WAIT"
    bot.answer_callback_query(call.id)
    send_clean_message(chat_id, "🕵️‍♂️️ Yashirin nomini yozing:")

  elif data == "search_by_code":
    user_states[user_id] = "SEARCH_CODE_WAIT"
    bot.answer_callback_query(call.id)
    send_clean_message(chat_id, "🔢 Anime kodini yozing:")

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
        chat_id,
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
            "🗑 Animeni butunlay o'chirish",
            callback_data=f"delete_anime_{anime_id}",
        ),
        types.InlineKeyboardButton("⬅ Ortga", callback_data="admin_manage"),
    )
    send_clean_message(chat_id, "Tanlang:", reply_markup=markup)

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
        chat_id,
        f"🎬 <b>{an_name}</b> uchun **{next_num}-qism** videosini yuboring:",
        parse_mode="HTML",
    )

  elif data == "finish_adding":
    bot.answer_callback_query(call.id, "Barcha qismlar saqlandi!")
    user_states.pop(user_id, None)
    temp_data.pop(user_id, None)
    send_clean_message(
        chat_id,
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
        chat_id,
        "🗑 Anime muvaffaqiyatli o'chirildi.",
        reply_markup=get_main_inline_menu(user_id),
    )

  elif data.startswith("show_anime_"):
    anime_id = int(data.replace("show_anime_", ""))
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name, secret_name, info, photo, views, code FROM animes WHERE"
        " id = ?",
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

    name, secret_name, info, photo, views, code = anime
    text = (
        f"🎬 <b>{name}</b>\n🕵️‍♂️ Yashirin nom: <i>{secret_name}</i>\n\n📖"
        f" {info}\n\n🔑 Kodi: <code>{code}</code>\n\n👁 Ko'rildi:"
        f" {views+1} marta"
    )

    markup = get_anime_folder_keyboard(anime_id, page=1)
    bot.answer_callback_query(call.id)

    if photo:
      send_clean_photo(
          chat_id, photo, text, reply_markup=markup, parse_mode="HTML", protect=True
      )
    else:
      send_clean_message(
          chat_id, text, reply_markup=markup, parse_mode="HTML", protect=True
      )

  # SAHIFALASH (PAGINATION) TUGMALARI HANDLERI
  elif data.startswith("page_"):
    parts_data = data.replace("page_", "").split("_")
    anime_id = int(parts_data[0])
    page = int(parts_data[1])
    bot.answer_callback_query(call.id)

    markup = get_anime_folder_keyboard(anime_id, page=page)
    try:
      bot.edit_message_reply_markup(
          chat_id=chat_id,
          message_id=call.message.message_id,
          reply_markup=markup,
      )
    except Exception:
      pass

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
      bot.send_video(chat_id, video_id, caption=f"🎬 {part_num}-qism")
    else:
      bot.answer_callback_query(
          call.id, "❌ Video topilmadi!", show_alert=True
      )


# --- BOTNI ISHGA TUSHIRISH ---
if __name__ == "__main__":
  keep_alive()
  bot.infinity_polling(skip_pending=True)
