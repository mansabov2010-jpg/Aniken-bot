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

TOKEN = os.environ.get('BOT_TOKEN', '8987164421:AAEQwE3A2Fghdj75Gkto0bJlRo1IJA14LKU')

ADMIN_ID = int(os.environ.get('ADMIN_ID', '7986354170'))
DATABASE_URL = os.environ.get('DATABASE_URL', None)
DB_FILE = "bot_data.db"

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)


@app.route('/')
def home():       
  return 'Bot is running and alive!'


def run_web():  
  app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))


def keep_alive():
  t = threading.Thread(target=run_web)
  t.daemon = True
  t.start()


def set_bot_commands():
  commands = [
      types.BotCommand('start', 'Botni ishga tushirish va asosiy menyu'),
      types.BotCommand('anime', 'Anime qidirish'),
  ]
  try:
    bot.set_my_commands(
        commands, scope=types.BotCommandScopeAllPrivateChats()
    )
    bot.set_my_commands(commands, scope=types.BotCommandScopeAllGroupChats())
  except Exception:
    pass


def get_db_connection():
  if DATABASE_URL and psycopg2:
    parsed_url = urlparse(DATABASE_URL)
    return psycopg2.connect(
        database=parsed_url.path[1:],
        user=parsed_url.username,
        password=parsed_url.password,
        host=parsed_url.hostname,
        port=parsed_url.port,
        sslmode='require',
    )
  else:
    return sqlite3.connect(DB_FILE)


def init_db():
  conn = get_db_connection()
  cursor = conn.cursor()
  is_postgres = DATABASE_URL and psycopg2

  if is_postgres:
    cursor.execute(
        'CREATE TABLE IF NOT EXISTS users (user_id BIGINT PRIMARY KEY)'
    )
    cursor.execute(
        'CREATE TABLE IF NOT EXISTS channels (username TEXT PRIMARY KEY)'
    )
    cursor.execute("""
            CREATE TABLE IF NOT EXISTS animes (
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
    cursor.execute(
        'CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)'
    )
    cursor.execute(
        'CREATE TABLE IF NOT EXISTS channels (username TEXT PRIMARY KEY)'
    )
    cursor.execute("""
            CREATE TABLE IF NOT EXISTS animes (
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
  conn.close()


def execute_query(
    query, params=(), fetchone=False, fetchall=False, commit=False
):
  conn = get_db_connection()
  cursor = conn.cursor()
  if DATABASE_URL and psycopg2:
    query = query.replace('?', '%s')
  else:
    query = query.replace('%s', '?')

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
user_last_messages = {}


def add_bot_message_to_history(chat_id, msg_id, protect=False):
  if chat_id == 0:
    return
  if chat_id not in user_last_messages:
    user_last_messages[chat_id] = []
  user_last_messages[chat_id].append({'msg_id': msg_id, 'protect': protect})

  unprotected = [
      m for m in user_last_messages[chat_id] if not m.get('protect')
  ]
  while len(unprotected) > 2:
    old_item = unprotected.pop(0)
    user_last_messages[chat_id].remove(old_item)
    try:
      bot.delete_message(chat_id, old_item['msg_id'])
    except Exception:
      pass

    old_item = unprotected.pop(0)
    user_last_messages[chat_id].remove(old_item)
    try:
      bot.delete_message(chat_id, old_item['msg_id'])
    except Exception:
      pass


def send_clean_message(
    chat_id, text, reply_markup=None, parse_mode=None, protect=False
):
  msg = bot.send_message(
      chat_id,
      text,
      reply_markup=reply_markup,
      parse_mode=parse_mode,
      protect_content=protect,
  )
  add_bot_message_to_history(chat_id, msg.message_id, protect=protect)
  return msg


def send_clean_photo(
    chat_id,
    photo,
    caption=None,
    reply_markup=None,
    parse_mode=None,
    protect=False,
):
  msg = bot.send_photo(
      chat_id,
      photo,
      caption=caption,
      reply_markup=reply_markup,
      parse_mode=parse_mode,
      protect_content=protect,
  )
  add_bot_message_to_history(chat_id, msg.message_id, protect=protect)
  return msg


def check_sub(user_id):
  if user_id == ADMIN_ID:
    return True
  channels = []
  row = execute_query('SELECT username FROM channels', fetchall=True)
  if row:
    channels = [r[0] for r in row]

  if not channels:
    return True
  unsubscribed = []
  for ch in channels:
    try:
      member = bot.get_chat_member(ch, user_id)
      if member.status in ['left', 'kicked']:
        unsubscribed.append(ch)
    except Exception:
      pass
  return unsubscribed if unsubscribed else True


def get_sub_keyboard(unsubscribed_channels):
  markup = types.InlineKeyboardMarkup(row_width=1)
  for ch in unsubscribed_channels:
    clean_ch = ch.replace('@', '')
    url = f'https://t.me/{clean_ch}'
    markup.add(types.InlineKeyboardButton(f"📢 Kanalga a'zo bo'lish", url=url))
  markup.add(
      types.InlineKeyboardButton(
          "✅ Obunani tekshirish", callback_data='check_subscription'
      )
  )
  return markup


def get_main_inline_menu(user_id):
  markup = types.InlineKeyboardMarkup(row_width=1)
  markup.add(
      types.InlineKeyboardButton(
          "🔍 Animelarni izlash", callback_data='menu_search'
      ),
      types.InlineKeyboardButton(
          "📁 Mavjud animelar", callback_data='menu_available_page_1'
      ),
      types.InlineKeyboardButton(
          "🔥 Tavsiya etiladigan animelar", callback_data='menu_recommended'
      ),
  )
  if user_id == ADMIN_ID:
    markup.add(
        types.InlineKeyboardButton(
            "➕ Yangi anime qo'shish", callback_data='admin_add_folder'
        ),
        types.InlineKeyboardButton(
            "➕ Mavjud jildga qism qo'shish", callback_data='admin_add_part'
        ),
        types.InlineKeyboardButton(
            "✏️ Anime jildlarini tahrirlash", callback_data='admin_edit_menu'
        ),
        types.InlineKeyboardButton(
            "⚙️ Kanallarni boshqarish", callback_data='admin_channels'
        ),
        types.InlineKeyboardButton(
            "📊 Statistika", callback_data='admin_stats'
        ),
        types.InlineKeyboardButton(
            "🗑 Animelarni boshqarish", callback_data='admin_manage'
        ),
    )
  return markup


def get_search_inline_keyboard():
  markup = types.InlineKeyboardMarkup(row_width=1)
  markup.add(
      types.InlineKeyboardButton(
          "🔤 Nomi orqali", callback_data='search_by_name'
      ),
      types.InlineKeyboardButton("🔢 Kodi orqali", callback_data='search_by_code'),
      types.InlineKeyboardButton(
          "🔙 Asosiy menyu", callback_data='back_to_main'
      ),
  )
  return markup
def get_available_animes_keyboard(page=1, action_type='show'):
  markup = types.InlineKeyboardMarkup(row_width=1)
  animes = (
      execute_query(
          'SELECT id, name FROM animes ORDER BY id DESC', fetchall=True
      )
      or []
  )

  if not animes:
    markup.add(
        types.InlineKeyboardButton(
            "❌ Hozircha animelar yo'q", callback_data='none'
        )
    )
    markup.add(
        types.InlineKeyboardButton(
            "🔙 Asosiy menyu", callback_data='back_to_main'
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
            'SELECT COUNT(*) FROM parts WHERE anime_id = ?',
            (anime_id,),
            fetchone=True,
        )[0]
        or 0
    )
    btn_text = f'📁 {name} ({parts_count}-qism)'

    if action_type == 'add_part':
      cb = f'select_anime_for_part_{anime_id}'
    elif action_type == 'admin_opt':
      cb = f'admin_anime_opt_{anime_id}'
    elif action_type == 'edit_folder':
      cb = f'select_edit_folder_{anime_id}'
    else:
      cb = f'show_anime_{anime_id}'

    markup.add(types.InlineKeyboardButton(btn_text, callback_data=cb))

  nav_buttons = []
  if page > 1:
    nav_buttons.append(
        types.InlineKeyboardButton(
            '◀️', callback_data=f'menu_available_page_{page-1}'
        )
    )
  nav_buttons.append(
      types.InlineKeyboardButton(f'{page}/{total_pages}', callback_data='none')
  )
  if page < total_pages:
    nav_buttons.append(
        types.InlineKeyboardButton(
            '▶️', callback_data=f'menu_available_page_{page+1}'
        )
    )

  if nav_buttons:
    markup.row(*nav_buttons)
  markup.add(
      types.InlineKeyboardButton(
          "🔙 Asosiy menyu", callback_data='back_to_main'
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
            "❌ Hozircha animelar yo'q", callback_data='none'
        )
    )
    markup.add(
        types.InlineKeyboardButton(
            "🔙 Asosiy menyu", callback_data='back_to_main'
        )
    )
    return markup

  for rank, (anime_id, name, views) in enumerate(animes, start=1):
    btn_text = f"#{rank}. 🎬 {name} - {views} ko'rilgan"
    markup.add(
        types.InlineKeyboardButton(
            btn_text, callback_data=f'show_anime_{anime_id}'
        )
    )

  markup.add(
      types.InlineKeyboardButton(
          "🔙 Asosiy menyu", callback_data='back_to_main'
      )
  )
  return markup


def get_anime_folder_keyboard(anime_id, page=1):
  markup = types.InlineKeyboardMarkup(row_width=1)
  parts_res = (
      execute_query(
          'SELECT part_num FROM parts WHERE anime_id = ? ORDER BY part_num ASC',
          (anime_id,),
          fetchall=True,
      )
      or []
  )
  parts = [row[0] for row in parts_res]

  item_per_page = 15
  total_pages = (len(parts) + item_per_page - 1) // item_per_page
  page = max(1, min(page, total_pages))

  start_idx = (page - 1) * item_per_page
  end_idx = start_idx + item_per_page
  current_parts = parts[start_idx:end_idx]

  buttons = []
  for p in current_parts:
    buttons.append(
        types.InlineKeyboardButton(
            f'{p}-qism', callback_data=f'get_part_{anime_id}_{p}'
        )
    )

  if buttons:
    markup.add(*buttons)

  nav_buttons = []
  if page > 1:
    nav_buttons.append(
        types.InlineKeyboardButton(
            '◀️', callback_data=f'page_{anime_id}_{page-1}'
        )
    )
  nav_buttons.append(types.InlineKeyboardButton('❌', callback_data='none'))
  if page < total_pages:
    nav_buttons.append(
        types.InlineKeyboardButton(
            '▶️', callback_data=f'page_{anime_id}_{page+1}'
        )
    )

  if nav_buttons:
    markup.row(*nav_buttons)

  markup.add(
      types.InlineKeyboardButton(
          "🔙 Asosiy menyu", callback_data='back_to_main'
      )
  )
  return markup


def format_anime_text(anime_data, bot_username=''):
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
      f'<b>🎞 {name}</b>\n\n'
      f'┣ 🎬 Qism: {episodes_count}\n'
      f'┣ 🌐 Holati: {status}\n'
      f'┣ 💻 Sifat: {quality}\n'
      f'┣ 🎭 Janrlari: {genre}\n'
      f'┗ 📢 Kanal: {channel_name}\n\n'
      f'📖 <b>Mazmuni:</b>\n{info}\n\n'
      f'🔥 Botimiz: @{bot_username}\n'
      f'🔥 Anime ID: {code}\n'
      f'🔥 Reyting: ⭐️ 5/5\n\n'
      f'✨ **YUKLAB OLISH** ✨'
      f"✨ **YUKLAB OLISH** ✨"
  )
  return formatted_text


@bot.message_handler(commands=['start'])
def send_start(message):
  user_id = message.from_user.id
  user_states.pop(user_id, None)
  temp_data.pop(user_id, None)

  execute_query(
      'INSERT INTO users (user_id) VALUES (?)',
      (user_id,),
      commit=True,
  )

  args = message.text.split()
  if len(args) > 1 and args[1].startswith('anime_'):
    try:
      code = args[1].split('_')[1]
      anime = execute_query(
          'SELECT id, name, secret_name, info, views, code, episodes_count,'
          ' status, quality, genre, channel_name, photo FROM animes WHERE code'
          ' = ?',
          (code,),
          fetchone=True,
      )
      if anime:
        anime_id = anime[0]
        execute_query(
            'UPDATE animes SET views = views + 1 WHERE id = ?',
            (anime_id,),
            commit=True,
        )
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton(
                '✨ TOMOSHA QILISH ✨',
                callback_data=f'watch_anime_{anime_id}',
            )
        )
        bot_username = bot.get_me().username
        anime_data = anime[1:11]
        text = format_anime_text(anime_data, bot_username)
        photo = anime[11]

        if photo:
          send_clean_photo(
              message.chat.id,
              photo,
              caption=text,
              reply_markup=markup,
              parse_mode='HTML',
              protect=True,
          )
        else:
          send_clean_message(
              message.chat.id,
              text,
              reply_markup=markup,
              parse_mode='HTML',
              protect=True,
          )
        return
    except Exception:
      pass

  sub_res = check_sub(user_id)
  if sub_res != True:
    markup = get_sub_keyboard(sub_res)
    send_clean_message(
        message.chat.id,
        "⚠️ Botdan foydalanish uchun quyidagi kanallarga obuna bo'lishingiz"
        " kerak:",
        reply_markup=markup,
    )
    return

  markup = get_main_inline_menu(user_id)
  send_clean_message(
      message.chat.id,
      "🏠 **Asosiy menyu**\n\nKerakli bo'limni tanlang:",
      reply_markup=markup,
      parse_mode='Markdown',
  )


@bot.message_handler(commands=['anime'])
def cmd_anime(message):
  user_id = message.from_user.id
  sub_res = check_sub(user_id)
  if sub_res != True:
    markup = get_sub_keyboard(sub_res)
    send_clean_message(
        message.chat.id,
        "⚠️ Botdan foydalanish uchun quyidagi kanallarga obuna bo'lishingiz"
        " kerak:",
        reply_markup=markup,
    )
    return

  markup = get_search_inline_keyboard()
  send_clean_message(
      message.chat.id,
      "🔍 **Anime qidirish usulini tanlang:**",
      reply_markup=markup,
      parse_mode='Markdown',
  )
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
  user_id = call.from_user.id
  chat_id = call.message.chat.id
  data = call.data

  if data == 'none':
    bot.answer_callback_query(call.id)
    return

  if data == 'check_subscription':
    sub_res = check_sub(user_id)
    if sub_res == True:
      bot.answer_callback_query(call.id, "✅ Obuna tasdiqlandi!")
      try:
        bot.delete_message(chat_id, call.message.message_id)
      except Exception:
        pass
      markup = get_main_inline_menu(user_id)
      send_clean_message(
          chat_id,
          "🏠 **Asosiy menyu**\n\nKerakli bo'limni tanlang:",
          reply_markup=markup,
          parse_mode='Markdown',
      )
    else:
      bot.answer_callback_query(
          call.id,
          "❌ Siz hali barcha kanallarga obuna bo'lmadingiz!",
          show_alert=True,
      )
    return

  sub_res = check_sub(user_id)
  if sub_res != True:
    markup = get_sub_keyboard(sub_res)
    try:
      bot.edit_message_text(
          "⚠️ Botdan foydalanish uchun quyidagi kanallarga obuna bo'lishingiz"
          " kerak:",
          chat_id,
          call.message.message_id,
          reply_markup=markup,
      )
    except Exception:
      pass
    return

  if data == 'back_to_main':
    user_states.pop(user_id, None)
    temp_data.pop(user_id, None)
    bot.answer_callback_query(call.id)
    try:
      bot.delete_message(chat_id, call.message.message_id)
    except Exception:
      pass
    markup = get_main_inline_menu(user_id)
    send_clean_message(
        chat_id,
        "🏠 **Asosiy menyu**\n\nKerakli bo'limni tanlang:",
        reply_markup=markup,
        parse_mode='Markdown',
    )

  elif data == 'menu_search':
    bot.answer_callback_query(call.id)
    markup = get_search_inline_keyboard()
    try:
      bot.edit_message_text(
          "🔍 **Anime qidirish usulini tanlang:**",
          chat_id,
          call.message.message_id,
          reply_markup=markup,
          parse_mode='Markdown',
      )
    except Exception:
      pass

  elif data == 'menu_recommended':
    bot.answer_callback_query(call.id)
    markup = get_recommended_animes_keyboard()
    try:
      bot.edit_message_text(
          "🔥 **Tavsiya etiladigan top animelar:**",
          chat_id,
          call.message.message_id,
          reply_markup=markup,
          parse_mode='Markdown',
      )
    except Exception:
      pass

  elif data.startswith('menu_available_page_'):
    page = int(data.split('_')[3])
    bot.answer_callback_query(call.id)
    markup = get_available_animes_keyboard(page, action_type='show')
    try:
      bot.edit_message_text(
          "📁 **Mavjud animelar ro'yxati:**",
          chat_id,
          call.message.message_id,
          reply_markup=markup,
          parse_mode='Markdown',
      )
    except Exception:
      pass

  elif data.startswith('show_anime_'):
    anime_id = int(data.split('_')[2])
    bot.answer_callback_query(call.id)
    anime = execute_query(
        'SELECT id, name, secret_name, info, views, code, episodes_count,'
        ' status, quality, genre, channel_name, photo FROM animes WHERE id = ?',
        (anime_id,),
        fetchone=True,
    )
    if anime:
      execute_query(
          'UPDATE animes SET views = views + 1 WHERE id = ?',
          (anime_id,),
          commit=True,
      )
      markup = types.InlineKeyboardMarkup(row_width=1)
      markup.add(
          types.InlineKeyboardButton(
              '✨ TOMOSHA QILISH ✨', callback_data=f'watch_anime_{anime_id}'
          )
      )
      bot_username = bot.get_me().username
      anime_data = anime[1:11]
      text = format_anime_text(anime_data, bot_username)
      photo = anime[11]

      try:
        bot.delete_message(chat_id, call.message.message_id)
      except Exception:
        pass

      if photo:
        send_clean_photo(
            chat_id,
            photo,
            caption=text,
            reply_markup=markup,
            parse_mode='HTML',
            protect=True,
        )
      else:
        send_clean_message(
            chat_id,
            text,
            reply_markup=markup,
            parse_mode='HTML',
            protect=True,
        )

  elif data.startswith('watch_anime_'):
    anime_id = int(data.split('_')[2])
    bot.answer_callback_query(call.id)
    markup = get_anime_folder_keyboard(anime_id, page=1)
    try:
      bot.edit_message_reply_markup(
          chat_id, call.message.message_id, reply_markup=markup
      )
    except Exception:
      pass

  elif data.startswith('page_'):
    parts = data.split('_')
    anime_id = int(parts[1])
    page = int(parts[2])
    bot.answer_callback_query(call.id)
    markup = get_anime_folder_keyboard(anime_id, page=page)
    try:
      bot.edit_message_reply_markup(
          chat_id, call.message.message_id, reply_markup=markup
      )
    except Exception:
      pass

  elif data.startswith('get_part_'):
    parts = data.split('_')
    anime_id = int(parts[2])
    part_num = int(parts[3])
    bot.answer_callback_query(call.id)
    part = execute_query(
        'SELECT video_id FROM parts WHERE anime_id = ? AND part_num = ?',
        (anime_id, part_num),
        fetchone=True,
    )
    if part and part[0]:
      try:
        bot.send_video(
            chat_id, part[0], caption=f'{part_num}-qism', protect_content=True
        )
      except Exception:
        bot.send_message(
            chat_id,
            f"❌ {part_num}-qism videosini yuborishda xatolik yuz berdi.",
        )
    else:
      bot.answer_callback_query(
          call.id, "❌ Bu qism topilmadi!", show_alert=True
      )
  elif data == 'search_by_name':
    bot.answer_callback_query(call.id)
    user_states[user_id] = 'WAITING_SEARCH_NAME'
    try:
      bot.edit_message_text(
          "🔤 Qidirilayotgan anime nomini kiriting:",
          chat_id,
          call.message.message_id,
      )
    except Exception:
      pass

  elif data == 'search_by_code':
    bot.answer_callback_query(call.id)
    user_states[user_id] = 'WAITING_SEARCH_CODE'
    try:
      bot.edit_message_text(
          "🔢 Qidirilayotgan anime kodini kiriting:",
          chat_id,
          call.message.message_id,
      )
    except Exception:
      pass

  elif data == 'admin_add_folder' and user_id == ADMIN_ID:
    bot.answer_callback_query(call.id)
    user_states[user_id] = 'ADD_NAME'
    temp_data[user_id] = {}
    send_clean_message(
        chat_id,
        "🎬 **Anime nomini kiriting** (Masalan: Re:rezo hayotni noldan boshlash):",
        parse_mode='Markdown',
    )

  elif data == 'admin_add_part' and user_id == ADMIN_ID:
    bot.answer_callback_query(call.id)
    markup = get_available_animes_keyboard(page=1, action_type='add_part')
    try:
      bot.edit_message_text(
          "📁 Qaysi animega qism qo'shmoqchisiz? Animeyni tanlang:",
          chat_id,
          call.message.message_id,
          reply_markup=markup,
      )
    except Exception:
      pass

  elif data.startswith('select_anime_for_part_') and user_id == ADMIN_ID:
    anime_id = int(data.split('_')[4])
    bot.answer_callback_query(call.id)
    user_states[user_id] = 'ADD_PART_NUM'
    temp_data[user_id] = {'anime_id': anime_id}
    send_clean_message(
        chat_id,
        "🔢 Qo'shilayotgan qism raqamini kiriting (Masalan: 86):",
    )

  elif data == 'admin_channels' and user_id == ADMIN_ID:
    bot.answer_callback_query(call.id)
    rows = execute_query('SELECT username FROM channels', fetchall=True)
    ch_list = (
        '\n'.join([r[0] for r in rows])
        if rows
        else "Hozircha kanallar yo'q."
    )
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(
            "➕ Kanal qo'shish", callback_data='admin_add_channel'
        ),
        types.InlineKeyboardButton(
            "🗑 Kanalni o'chirish", callback_data='admin_del_channel'
        ),
        types.InlineKeyboardButton(
            "🔙 Asosiy menyu", callback_data='back_to_main'
        ),
    )
    try:
      bot.edit_message_text(
          f"📢 **Majburiy obuna kanallari:**\n\n{ch_list}",
          chat_id,
          call.message.message_id,
          reply_markup=markup,
          parse_mode='Markdown',
      )
    except Exception:
      pass

  elif data == 'admin_add_channel' and user_id == ADMIN_ID:
    bot.answer_callback_query(call.id)
    user_states[user_id] = 'ADD_CHANNEL'
    send_clean_message(
        chat_id,
        "📢 Qo'shiladigan kanal username'ini yuboring (Masalan: @AnimeKanal):",
    )

  elif data == 'admin_del_channel' and user_id == ADMIN_ID:
    bot.answer_callback_query(call.id)
    user_states[user_id] = 'DEL_CHANNEL'
    send_clean_message(
        chat_id,
        "🗑 O'chiriladigan kanal username'ini yuboring (Masalan: @AnimeKanal):",
    )

  elif data == 'admin_stats' and user_id == ADMIN_ID:
    bot.answer_callback_query(call.id)
    users_count = (
        execute_query('SELECT COUNT(*) FROM users', fetchone=True)[0] or 0
    )
    animes_count = (
        execute_query('SELECT COUNT(*) FROM animes', fetchone=True)[0] or 0
    )
    parts_count = (
        execute_query('SELECT COUNT(*) FROM parts', fetchone=True)[0] or 0
    )
    text = (
        f"📊 **Bot statistikasi:**\n\n👥 Foydalanuvchilar: {users_count}\n🎬"
        f" Animelar jildlari: {animes_count}\n📁 Jami qismlar: {parts_count}"
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            "🔙 Asosiy menyu", callback_data='back_to_main'
        )
    )
    try:
      bot.edit_message_text(
          text, chat_id, call.message.message_id, reply_markup=markup
      )
    except Exception:
      pass
  elif data == 'admin_manage' and user_id == ADMIN_ID:
    bot.answer_callback_query(call.id)
    markup = get_available_animes_keyboard(page=1, action_type='admin_opt')
    try:
      bot.edit_message_text(
          "🗑 Boshqarish yoki o'chirish uchun animeyni tanlang:",
          chat_id,
          call.message.message_id,
          reply_markup=markup,
      )
    except Exception:
      pass

  elif data.startswith('admin_anime_opt_') and user_id == ADMIN_ID:
    anime_id = int(data.split('_')[3])
    bot.answer_callback_query(call.id)
    anime = execute_query(
        'SELECT name FROM animes WHERE id = ?', (anime_id,), fetchone=True
    )
    anime_name = anime[0] if anime else 'Anime'
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(
            "🗑 Animeni to'liq o'chirish",
            callback_data=f'confirm_del_anime_{anime_id}',
        ),
        types.InlineKeyboardButton(
            "🔙 Orqaga", callback_data='admin_manage'
        ),
    )
    try:
      bot.edit_message_text(
          f"⚙️ **{anime_name}** bo'yicha amalni tanlang:",
          chat_id,
          call.message.message_id,
          reply_markup=markup,
          parse_mode='Markdown',
      )
    except Exception:
      pass

  elif data.startswith('confirm_del_anime_') and user_id == ADMIN_ID:
    anime_id = int(data.split('_')[3])
    bot.answer_callback_query(call.id)
    execute_query('DELETE FROM parts WHERE anime_id = ?', (anime_id,), commit=True)
    execute_query('DELETE FROM animes WHERE id = ?', (anime_id,), commit=True)
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            "🔙 Animelar ro'yxatiga qaytish", callback_data='admin_manage'
        )
    )
    try:
      bot.edit_message_text(
          "✅ Anime va uning barcha qismlari muvaffaqiyatli o'chirib yuborildi!",
          chat_id,
          call.message.message_id,
          reply_markup=markup,
      )
    except Exception:
      pass


@bot.message_handler(func=lambda message: True)
def message_handler(message):
  user_id = message.from_user.id
  state = user_states.get(user_id)
  text = message.text

  if not state:
    return

  if state == 'WAITING_SEARCH_NAME':
    user_states.pop(user_id, None)
    animes = (
        execute_query(
            'SELECT id, name FROM animes WHERE name LIKE ? ORDER BY id DESC',
            (f'%{text}%',),
            fetchall=True,
        )
        or []
    )
    if not animes:
      send_clean_message(
          message.chat.id, "❌ Hech qanday anime topilmadi."
      )
      return
    markup = types.InlineKeyboardMarkup(row_width=1)
    for anime_id, name in animes:
      markup.add(
          types.InlineKeyboardButton(
              f'🎬 {name}', callback_data=f'show_anime_{anime_id}'
          )
      )
    send_clean_message(
        message.chat.id,
        "🔍 **Topilgan animelar:**",
        reply_markup=markup,
        parse_mode='Markdown',
    )

  elif state == 'WAITING_SEARCH_CODE':
    user_states.pop(user_id, None)
    anime = execute_query(
        'SELECT id, name, secret_name, info, views, code, episodes_count,'
        ' status, quality, genre, channel_name, photo FROM animes WHERE code'
        ' = ?',
        (text.strip(),),
        fetchone=True,
    )
    if not anime:
      send_clean_message(
          message.chat.id,
          "❌ Bu kod bo'yicha hech qanday anime topilmadi.",
      )
      return
    anime_id = anime[0]
    execute_query(
        'UPDATE animes SET views = views + 1 WHERE id = ?',
        (anime_id,),
        commit=True,
    )
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(
            '✨ TOMOSHA QILISH ✨', callback_data=f'watch_anime_{anime_id}'
        )
    )
    bot_username = bot.get_me().username
    anime_data = anime[1:11]
    formatted_text = format_anime_text(anime_data, bot_username)
    photo = anime[11]

    if photo:
      send_clean_photo(
          message.chat.id,
          photo,
          caption=formatted_text,
          reply_markup=markup,
          parse_mode='HTML',
          protect=True,
      )
    else:
      send_clean_message(
          message.chat.id,
          formatted_text,
          reply_markup=markup,
          parse_mode='HTML',
          protect=True,
      )

  elif user_id == ADMIN_ID:
    if state == 'ADD_NAME':
      temp_data[user_id]['name'] = text
      user_states[user_id] = 'ADD_SECRET_NAME'
      send_clean_message(
          message.chat.id,
          "🔑 **Anime uchun maxfiy/qidiruv kalit so'zini kiriting** (Masalan:"
          " rezero):",
          parse_mode='Markdown',
      )

    elif state == 'ADD_SECRET_NAME':
      temp_data[user_id]['secret_name'] = text
      user_states[user_id] = 'ADD_CODE'
      send_clean_message(
          message.chat.id,
          "🔢 **Anime kodini kiriting** (Unikal raqam yoki harf, masalan: 1):",
          parse_mode='Markdown',
      )

    elif state == 'ADD_CODE':
      temp_data[user_id]['code'] = text
      user_states[user_id] = 'ADD_EPISODES'
      send_clean_message(
          message.chat.id,
          "🎬 **Qism sonini kiriting** (Masalan: 25 / 85 / Tamom):",
          parse_mode='Markdown',
      )

elif state == 'ADD_EPISODES': # <--- Boshidan boshlanadi (chapda)
  if not text.isdigit():  # <--- Biroz o'ngga surib (4 ta probel tashlab) yoziladi
    send_clean_message(
        message.chat.id,
        '❌ Iltimos, faqat raqam kiriting (masalan: 25 / 85):',
        parse_mode='Markdown',
    )
    return

  temp_data[user_id]['episodes_count'] = text
  user_states[user_id] = 'ADD_STATUS'
    send_clean_message(
        message.chat.id,
        "🌐 **Anime statusini kiriting** (Masalan: Davom etmoqda / Tugallangan):",
        parse_mode='Markdown'
    )


    elif state == 'ADD_STATUS':
      temp_data[user_id]['status'] = text
      user_states[user_id] = 'ADD_QUALITY'
      send_clean_message(
          message.chat.id,
          "💻 **Video sifatini kiriting** (Masalan: 720p, 1080p):",
          parse_mode='Markdown',
      )

    elif state == 'ADD_QUALITY':
      temp_data[user_id]['quality'] = text
      user_states[user_id] = 'ADD_GENRE'
      send_clean_message(
          message.chat.id,
          "🎭 **Anime janrini kiriting** (Masalan: Jangari, Sarguzasht):",
          parse_mode='Markdown',
      )

    elif state == 'ADD_GENRE':
      temp_data[user_id]['genre'] = text
      user_states[user_id] = 'ADD_CHANNEL'
      send_clean_message(
          message.chat.id,
          "📢 **Kanal nomini kiriting** (Masalan: @AnimeKanal):",
          parse_mode='Markdown',
      )

    elif state == 'ADD_CHANNEL':
      temp_data[user_id]['channel_name'] = text
      user_states[user_id] = 'ADD_INFO'
      send_clean_message(
          message.chat.id,
          "📖 **Anime haqida qisqacha ma'lumot kiriting** (o'tkazib yuborish"
          " uchun /skip):",
          parse_mode='Markdown',
      )

    elif state == 'ADD_INFO':
      info_text = "Ma'lumot mavjud emas" if text == '/skip' else text
      temp_data[user_id]['info'] = info_text
      user_states[user_id] = 'ADD_PHOTO'
      send_clean_message(
          message.chat.id,
          "🖼 **Anime uchun rasm yuboring** (Rasm yoki poster):",
          parse_mode='Markdown',
      )

    elif state == 'ADD_PART_NUM':
      try:
        part_num = int(text)
        temp_data[user_id]['part_num'] = part_num
        user_states[user_id] = 'ADD_PART_VIDEO'
        send_clean_message(
            message.chat.id,
            f"🎥 {part_num}-qism uchun **videoni** yuboring:",
            parse_mode='Markdown',
        )
      except ValueError:
        send_clean_message(
            message.chat.id, "❌ Iltimos, qism raqamini faqat raqamda kiriting!"
        )


@bot.message_handler(content_types=['photo', 'video'])
def handle_media(message):
  user_id = message.from_user.id
  state = user_states.get(user_id)

  if user_id == ADMIN_ID and state == 'ADD_PHOTO':
    photo_id = message.photo[-1].file_id
    d = temp_data.get(user_id, {})

    execute_query(
        'INSERT INTO animes (name, secret_name, code, info, photo,'
        ' episodes_count, status, quality, genre, channel_name, views) VALUES'
        ' (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)',
        (
            d.get('name'),
            d.get('secret_name'),
            d.get('code'),
            d.get('info'),
            photo_id,
            d.get('episodes_count', 'Noma\'lum'),
            d.get('status', 'Davom etmoqda'),
            d.get('quality', '720p'),
            d.get('genre', 'Noma\'lum'),
            d.get('channel_name', 'Noma\'lum'),
        ),
        commit=True,
    )

    user_states.pop(user_id, None)
    temp_data.pop(user_id, None)
    send_clean_message(
        message.chat.id,
        "✅ **Anime muvaffaqiyatli bazaga qo'shildi!**",
        parse_mode='Markdown',
    )

  elif user_id == ADMIN_ID and state == 'ADD_PART_VIDEO' and message.video:
    video_id = message.video.file_id
    d = temp_data.get(user_id, {})
    anime_id = d.get('anime_id')
    part_num = d.get('part_num')

    execute_query(
        'INSERT INTO parts (anime_id, part_num, video_id) VALUES (?, ?, ?)',
        (anime_id, part_num, video_id),
        commit=True,
    )

    user_states.pop(user_id, None)
    temp_data.pop(user_id, None)
    send_clean_message(
        message.chat.id,
        f"✅ **{part_num}-qism muvaffaqiyatli qo'shildi!**",
        parse_mode='Markdown',
    )


if __name__ == '__main__':
  keep_alive()
  print('Bot ishga tushmoqda...')
  time.sleep(5)  # Render to'liq o'rnashib olishi uchun biroz ko'proq kutamiz
  try:
    bot.remove_webhook()
    time.sleep(1)
    bot.polling(none_stop=True, interval=3, timeout=30, skip_pending=True)
  except Exception as e:
    print(f'Polling xatoligi: {e}')
