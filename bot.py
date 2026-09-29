import json
import os
import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

TOKEN = "8845458932:AAHDQOxJN_LVVaqDw1iur0nKWNAbFjhSp1w"
ADMIN_ID = 7986354170

bot = telebot.TeleBot(TOKEN)
DB_FILE = "anime_db.json"
CONFIG_FILE = "config.json"


def load_db():
  if os.path.exists(DB_FILE):
    try:
      with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)
    except Exception:
      return {}
  return {}


def save_db(data):
  with open(DB_FILE, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=4)


def load_config():
  if os.path.exists(CONFIG_FILE):
    try:
      with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)
    except Exception:
      return {}
  return {"required_channel": ""}


def save_config(config):
  with open(CONFIG_FILE, "w", encoding="utf-8") as f:
    json.dump(config, f, ensure_ascii=False, indent=4)


admin_state = {}


# --- MAJBURIY OBUNANI TEKSHIRISH ---
def check_subscription(user_id):
  config = load_config()
  channel = config.get("required_channel")
  if not channel:
    return True
  try:
    member = bot.get_chat_member(channel, user_id)
    if member.status in ["member", "administrator", "creator"]:
      return True
  except Exception:
    pass
  return False


# --- CHATNI TOZALASH (Faqat oxirgi xabar va videolar qoladi) ---
def safe_delete_message(chat_id, message_id):
  try:
    bot.delete_message(chat_id, message_id)
  except Exception:
    pass


@bot.message_handler(commands=["start"])
def start_command(message):
  user_id = message.from_user.id

  # Majburiy obuna tekshiruvi
  if not check_subscription(user_id):
    config = load_config()
    channel = config.get("required_channel")
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton(
            "📢 Kanalga a'zo bo'lish",
            url=f"https://t.me/{channel.replace('@', '')}",
        ),
        InlineKeyboardButton("✅ Obunani tekshirish", callback_data="check_sub"),
    )
    bot.send_message(
        message.chat.id,
        "⚠️ Botdan foydalanish uchun avval quyidagi kanalimizga a'zo bo'lishingiz"
        " kerak:",
        reply_markup=markup,
    )
    return

  if user_id in admin_state:
    del admin_state[user_id]

  intro_text = (
      "✨ **AniKen dunyosiga xush kelibsiz!** ✨\n\n"
      "🎬 Bu yerda siz eng sara anime va animatsion filmlarni eng yuqori sifatda"
      " topishingiz mumkin.\n"
      "💖 Sizning har bir tashrifingiz biz uchun katta quvonch, har doim biz"
      " bilan birga bo'ling!\n\n"
      "Botdan foydalanishni boshlash uchun pastdagi tugmani bosing:"
  )
  markup = InlineKeyboardMarkup(row_width=1)
  markup.add(
      InlineKeyboardButton(
          "🚀 Start (Asosiy menyu)", callback_data="main_menu"
      )
  )
  bot.send_message(
      message.chat.id, intro_text, reply_markup=markup, parse_mode="Markdown"
  )


@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
  user_id = call.from_user.id
  data = call.data
  db = load_db()

  if data == "check_sub":
    if check_subscription(user_id):
      safe_delete_message(call.message.chat.id, call.message.message_id)
      bot.answer_callback_query(call.id, "Rahmat! Obuna tasdiqlandi.")
      # Obunadan keyin bosh menyuni ochamiz
      fake_msg = call.message
      start_command(fake_msg)
    else:
      bot.answer_callback_query(
          call.id,
          "Siz hali kanalga to'liq a'zo bo'lmadingiz!",
          show_alert=True,
      )
    return

  # Qolgan barcha menyular uchun ham majburiy obunani tekshiramiz
  if not check_subscription(user_id):
    bot.answer_callback_query(
        call.id,
        "Botdan foydalanish uchun avval kanalga a'zo bo'ling!",
        show_alert=True,
    )
    return

  if data == "main_menu":
    bot.answer_callback_query(call.id)
    markup = InlineKeyboardMarkup(row_width=1)
    if user_id == ADMIN_ID:
      markup.add(
          InlineKeyboardButton(
              "➕ Yangi anime bo'limi", callback_data="admin_anime_menu"
          ),
          InlineKeyboardButton(
              "🔄 Mavjud animeni almashtirish", callback_data="admin_replace"
          ),
          InlineKeyboardButton(
              "📁 Jildlar bo'yicha ko'rish", callback_data="user_view_folders"
          ),
          InlineKeyboardButton(
              "🔍 Nomi orqali qidirish", callback_data="user_search_name"
          ),
          InlineKeyboardButton(
              "🔢 Kod orqali qidirish", callback_data="user_search_code"
          ),
          InlineKeyboardButton(
              "📢 Majburiy kanalni sozlash", callback_data="admin_set_channel"
          ),
      )
      bot.send_message(
          call.message.chat.id,
          "Salom Admin! Kerakli bo'limni tanlang:",
          reply_markup=markup,
      )
    else:
      markup.add(
          InlineKeyboardButton(
              "📁 Jildlar bo'yicha ko'rish", callback_data="user_view_folders"
          ),
          InlineKeyboardButton(
              "🔍 Nomi orqali qidirish", callback_data="user_search_name"
          ),
          InlineKeyboardButton(
              "🔢 Kod orqali qidirish", callback_data="user_search_code"
          ),
      )
      bot.send_message(
          call.message.chat.id,
          "Salom! Kerakli qidiruv turini tanlang:",
          reply_markup=markup,
      )

  elif data == "admin_set_channel" and user_id == ADMIN_ID:
    bot.answer_callback_query(call.id)
    admin_state[user_id] = {"step": "waiting_channel_username"}
    bot.send_message(
        call.message.chat.id,
        "📢 Majburiy kanal username'ini yuboring (masalan: @kanal_nomi):",
    )

  elif data == "admin_anime_menu" and user_id == ADMIN_ID:
    bot.answer_callback_query(call.id)
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton(
            "📁 Yangi jild yaratish", callback_data="create_new_folder"
        ),
        InlineKeyboardButton(
            "📂 Mavjud jildga anime qo'shish",
            callback_data="add_to_existing_folder",
        ),
    )
    bot.send_message(
        call.message.chat.id, "Kerakli amalni tanlang:", reply_markup=markup
    )

  elif data == "create_new_folder" and user_id == ADMIN_ID:
    bot.answer_callback_query(call.id)
    admin_state[user_id] = {"step": "waiting_new_folder_name"}
    bot.send_message(
        call.message.chat.id,
        "📁 Yangi jild nomini kiriting (masalan: Death note):",
    )

  elif data == "add_to_existing_folder" and user_id == ADMIN_ID:
    bot.answer_callback_query(call.id)
    if not db:
      bot.send_message(
          call.message.chat.id,
          "❌ Hozircha hech qanday jild yo'q. Avval 'Yangi jild yaratish'"
          " orqali jild oching.",
      )
      return

    markup = InlineKeyboardMarkup(row_width=1)
    for folder_name in db.keys():
      anime_count = len(db[folder_name])
      markup.add(
          InlineKeyboardButton(
              f"📁 {folder_name} ({anime_count} ta anime)",
              callback_data=f"sel_folder_{folder_name}",
          )
      )
    bot.send_message(
        call.message.chat.id,
        "Qaysi jildga anime qo'shmoqchisiz? Tanlang:",
        reply_markup=markup,
    )

  elif data.startswith("sel_folder_") and user_id == ADMIN_ID:
    bot.answer_callback_query(call.id)
    folder_name = data.replace("sel_folder_", "")
    admin_state[user_id] = {"step": "waiting_video", "folder_name": folder_name}
    bot.send_message(
        call.message.chat.id,
        f"📁 Jild: **{folder_name}**\n\n🎬 1-qadam: Anime **videosini**"
        " yuboring:",
        parse_mode="Markdown",
    )

  elif data == "admin_replace" and user_id == ADMIN_ID:
    bot.answer_callback_query(call.id)
    admin_state[user_id] = {"step": "waiting_replace_code"}
    bot.send_message(
        call.message.chat.id,
        "🔄 Almashtirmoqchi bo'lgan anime **kodini** kiriting:",
    )

  # --- JILDLAR BO'YICHA NAVIGATSIYA (Foydalanuvchi uchun) ---
  elif data == "user_view_folders":
    bot.answer_callback_query(call.id)
    if not db:
      bot.send_message(call.message.chat.id, "❌ Hozircha animelar mavjud emas.")
      return
    markup = InlineKeyboardMarkup(row_width=1)
    for folder_name in db.keys():
      markup.add(
          InlineKeyboardButton(
              f"📁 {folder_name}", callback_data=f"view_f_{folder_name}"
          )
      )
    bot.send_message(
        call.message.chat.id,
        "📂 Mavjud jildlardan birini tanlang:",
        reply_markup=markup,
    )

  elif data.startswith("view_f_"):
    bot.answer_callback_query(call.id)
    folder_name = data.replace("view_f_", "")
    animes = db.get(folder_name, [])
    if not animes:
      bot.send_message(
          call.message.chat.id,
          f"❌ '{folder_name}' jildida hozircha animelar yo'q.",
      )
      return
    markup = InlineKeyboardMarkup(row_width=1)
    for anime in animes:
      markup.add(
          InlineKeyboardButton(
              f"🎬 {anime['name']} (Kod: {anime['code']})",
              callback_data=f"view_anime_{folder_name}_{anime['code']}",
          )
      )
    markup.add(
        InlineKeyboardButton("⬅️ Orqaga", callback_data="user_view_folders")
    )
    bot.send_message(
        call.message.chat.id,
        f"📁 **{folder_name}** jildidagi animelar:",
        reply_markup=markup,
        parse_mode="Markdown",
    )

  elif data.startswith("view_anime_"):
    bot.answer_callback_query(call.id)
    parts_data = data.replace("view_anime_", "").split("_", 1)
    folder_name = parts_data[0]
    anime_code = parts_data[1]

    found_anime = None
    for anime in db.get(folder_name, []):
      if anime["code"] == anime_code:
        found_anime = anime
        break

    if found_anime:
      bot.send_message(
          call.message.chat.id,
          f"🎬 Nomi: {found_anime['name']}\n🔢 Kodi: {found_anime['code']}\n\nQismlar"
          " yuborilmoqda...",
      )
      for p_num, v_id in found_anime["parts"].items():
        bot.send_video(
            call.message.chat.id,
            v_id,
            caption=f"{found_anime['name']} — {p_num}-qism",
        )
    else:
      bot.send_message(call.message.chat.id, "❌ Anime topilmadi.")

  elif data == "user_search_name":
    bot.answer_callback_query(call.id)
    bot.send_message(
        call.message.chat.id, "✍️ Anime nomining bir qismini yuboring:"
    )

  elif data == "user_search_code":
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, "🔢 Anime kodini yuboring:")


@bot.message_handler(content_types=["video", "text"])
def all_messages_handler(message):
  user_id = message.from_user.id

  # Har bir xabarda obunani tekshirish
  if not check_subscription(user_id):
    config = load_config()
    channel = config.get("required_channel")
    if channel:
      markup = InlineKeyboardMarkup(row_width=1)
      markup.add(
          InlineKeyboardButton(
              "📢 Kanalga a'zo bo'lish",
              url=f"https://t.me/{channel.replace('@', '')}",
          ),
          InlineKeyboardButton(
              "✅ Obunani tekshirish", callback_data="check_sub"
          ),
      )
      bot.send_message(
          message.chat.id,
          "⚠️ Botdan foydalanish uchun kanalimizga a'zo bo'lishingiz shart!",
          reply_markup=markup,
      )
      return

  text = message.text.strip() if message.text else ""
  db = load_db()

  if user_id == ADMIN_ID and user_id in admin_state:
    state = admin_state[user_id]
    step = state["step"]

    if step == "waiting_channel_username":
      if not text:
        bot.reply_to(message, "❌ Iltimos, kanal username'ini yuboring:")
        return
      config = load_config()
      config["required_channel"] = text
      save_config(config)
      del admin_state[user_id]
      bot.reply_to(
          message,
          f"✅ Majburiy kanal muvaffaqiyatli o'rnatildi: {text}",
      )
      return

    elif step == "waiting_new_folder_name":
      if not text:
        bot.reply_to(message, "❌ Iltimos, jild nomini matn ko'rinishida yuboring:")
        return
      folder_name = text
      if folder_name not in db:
        db[folder_name] = []
        save_db(db)
      state["folder_name"] = folder_name
      state["step"] = "waiting_video"
      bot.reply_to(
          message,
          f"📁 Jild yaratildi: **{folder_name}**\n\n🎬 1-qadam: Anime"
          " **videosini** yuboring:",
          parse_mode="Markdown",
      )
      return

    elif step == "waiting_video" or step == "waiting_replace_video":
      if not message.video:
        bot.reply_to(message, "❌ Iltimos, video yuboring:")
        return

      if step == "waiting_video":
        state["video"] = message.video.file_id
        state["step"] = "waiting_part"
        bot.reply_to(
            message,
            "✅ Video qabul qilindi!\n\nNechanchi **qism** ekanini yuboring"
            " (masalan: 1):",
        )
      else:
        code = state["target_code"]
        part = state["target_part"]
        found = False
        for f_name, animes in db.items():
          for anime in animes:
            if anime["code"] == code:
              anime["parts"][str(part)] = message.video.file_id
              found = True
              break
        if found:
          save_db(db)
          bot.reply_to(
              message,
              f"🔄 Muvaffaqiyatli almashtirildi! Kod: {code}, Qism: {part}",
          )
        else:
          bot.reply_to(message, "❌ Bunday kod topilmadi.")
        del admin_state[user_id]
      return

    elif step == "waiting_part":
      if not text.isdigit():
        bot.reply_to(message, "❌ Iltimos, faqat raqam kiriting (masalan: 1):")
        return
      state["part"] = int(text)
      state["step"] = "waiting_code"
      bot.reply_to(
          message, "Anime uchun maxsus **kod** kiriting (masalan: 101):"
      )
      return

    elif step == "waiting_code":
      if not text:
        bot.reply_to(message, "❌ Iltimos, kod kiriting:")
        return
      state["code"] = text
      state["step"] = "waiting_name"
      bot.reply_to(message, "Anime **to'liq nomini** kiriting:")
      return

    elif step == "waiting_name":
      if not text:
        bot.reply_to(message, "❌ Iltimos, nom kiriting:")
        return
      state["name"] = text
      state["step"] = "waiting_keywords"
      bot.reply_to(
          message,
          "Yashirin kalit so'zlarni vergul bilan kiriting (masalan: death,"
          " note, olim):",
      )
      return

    elif step == "waiting_keywords":
      if not text:
        bot.reply_to(message, "❌ Iltimos, kalit so'zlarni kiriting:")
        return
      keywords = [k.strip().lower() for k in text.split(",")]
      folder_name = state["folder_name"]

      new_anime = {
          "code": state["code"],
          "name": state["name"],
          "keywords": keywords,
          "parts": {str(state["part"]): state["video"]},
      }

      if folder_name not in db:
        db[folder_name] = []
      db[folder_name].append(new_anime)
      save_db(db)

      del admin_state[user_id]
      bot.reply_to(
          message,
          f"🎉 Muvaffaqiyatli saqlandi!\nJild: {folder_name}\nNomi:"
          f" {state['name']}\nKodi: {state['code']}",
      )
      return

    elif step == "waiting_replace_code":
      if not text:
        bot.reply_to(message, "❌ Iltimos, kod kiriting:")
        return
      found = False
      for f_name, animes in db.items():
        for anime in animes:
          if anime["code"] == text:
            found = True
            break
      if found:
        state["target_code"] = text
        state["step"] = "waiting_replace_part"
        bot.reply_to(
            message, "Nechanchi qismini almashtirmoqchisiz? (Masalan: 1):"
        )
      else:
        bot.reply_to(
            message, "❌ Bunday kodli anime topilmadi. Qaytadan kiriting:"
        )
      return

    elif step == "waiting_replace_part":
      if not text.isdigit():
        bot.reply_to(message, "❌ Iltimos, raqam kiriting:")
        return
      state["target_part"] = int(text)
      state["step"] = "waiting_replace_video"
      bot.reply_to(message, "Endi yangi **videoni** yuboring:")
      return

  if text:
    if text.isdigit():
      found_anime = None
      for f_name, animes in db.items():
        for anime in animes:
          if anime["code"] == text:
            found_anime = anime
            break

      if found_anime:
        bot.reply_to(
            message,
            f"🎬 Nomi: {found_anime['name']}\n🔢 Kodi: {text}\n\nMavjud qismlar"
            " yuborilmoqda...",
        )
        for p_num, v_id in found_anime["parts"].items():
          bot.send_video(
              message.chat.id,
              v_id,
              caption=f"{found_anime['name']} — {p_num}-qism",
          )
      else:
        bot.reply_to(message, "❌ Bu kod bo'yicha hech qanday anime topilmadi.")
    else:
      query = text.lower()
      found = []
      for f_name, animes in db.items():
        for anime in animes:
          if (
              query in anime["name"].lower()
              or any(query in kw for kw in anime["keywords"])
              or query in f_name.lower()
          ):
            found.append(anime)

      if found:
        res_text = "🔍 Topilgan animelar:\n\n"
        for anime in found:
          res_text += f"• **{anime['name']}** (Kod: `{anime['code']}`)\n"
        bot.reply_to(message, res_text, parse_mode="Markdown")
      else:
        bot.reply_to(
            message, "❌ Hech qanday anime topilmadi. Boshqa so'z yozib ko'ring."
        )


print("Bot ishga tushdi...")
bot.infinity_polling()
  
