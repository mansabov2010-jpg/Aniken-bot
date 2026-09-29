import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

TOKEN = "8845458932:AAHDQOxJN_LVVaqDw1iur0nKWNAbFjhSp1w"
ADMIN_ID = 7986354170

bot = telebot.TeleBot(TOKEN)

# Vaqtinchalik ma'lumotlar bazasi (xotirada saqlash uchun)
database = {}
users_list = set()

def main_admin_menu():
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("➕ Anime qo'shish", callback_data="add_anime"),
        InlineKeyboardButton("📋 Ro'yxat", callback_data="list_anime")
    )
    markup.row(
        InlineKeyboardButton("📊 Statistika", callback_data="stats")
    )
    return markup

def main_user_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("🎬 Animelar ro'yxati"), KeyboardButton("ℹ️ Bot haqida"))
    return markup

@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    users_list.add(user_id)
    
    if user_id == ADMIN_ID:
        bot.send_message(
            message.chat.id, 
            "Assalomu alaykum, Admin! Boshqaruv paneli:", 
            reply_markup=main_admin_menu()
        )
    else:
        bot.send_message(
            message.chat.id,
            "👋 Assalomu alaykum! Anime qismlarini ko'rish uchun pastdagi tugmani bosing:",
            reply_markup=main_user_menu()
        )
        show_animes_to_user(message.chat.id)

@bot.message_handler(func=lambda m: m.text == "🎬 Animelar ro'yxati")
def text_anime_list(message):
    show_animes_to_user(message.chat.id)

@bot.message_handler(func=lambda m: m.text == "ℹ️ Bot haqida")
def text_about(message):
    bot.send_message(message.chat.id, "🤖 Bu bot orqali sevimli animelaringizni qismma-qism tomosha qilishingiz mumkin.")

def show_animes_to_user(chat_id):
    if not database:
        bot.send_message(chat_id, "Hozircha animelar mavjud emas.")
        return
    
    markup = InlineKeyboardMarkup(row_width=1)
    for anime in database.keys():
        markup.add(InlineKeyboardButton(f"🎬 {anime}", callback_data=f"watch_{anime}"))
    bot.send_message(chat_id, "📺 Mavjud animelar:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    user_id = call.from_user.id
    data = call.data
    
    if data == "add_anime" and user_id == ADMIN_ID:
        msg = bot.send_message(call.message.chat.id, "Anime nomini kiriting:")
        bot.register_next_step_handler(msg, step_anime_name)
        
    elif data == "list_anime" and user_id == ADMIN_ID:
        if not database:
            bot.answer_callback_query(call.id, "Animelar yo'q.")
            return
        markup = InlineKeyboardMarkup(row_width=1)
        for anime in database.keys():
            markup.add(InlineKeyboardButton(f"❌ O'chirish: {anime}", callback_data=f"del_{anime}"))
        markup.add(InlineKeyboardButton("⬅️ Orqaga", callback_data="back_home"))
        bot.edit_message_text("O'chirmoqchi bo'lgan animeni tanlang:", call.message.chat.id, call.message.message_id, reply_markup=markup)
        
    elif data == "stats" and user_id == ADMIN_ID:
        text = f"📊 Statistika:\n\n👥 Foydalanuvchilar: {len(users_list)} ta\n🎬 Animelar: {len(database)} ta"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⬅️ Orqaga", callback_data="back_home"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
        
    elif data == "back_home" and user_id == ADMIN_ID:
        bot.edit_message_text("Boshqaruv paneli:", call.message.chat.id, call.message.message_id, reply_markup=main_admin_menu())
        
    elif data.startswith("del_") and user_id == ADMIN_ID:
        anime = data.replace("del_", "")
        if anime in database:
            del database[anime]
        bot.answer_callback_query(call.id, f"{anime} o'chirildi!")
        bot.edit_message_text("Boshqaruv paneli:", call.message.chat.id, call.message.message_id, reply_markup=main_admin_menu())
        
    elif data.startswith("watch_"):
        anime = data.replace("watch_", "")
        if anime in database:
            markup = InlineKeyboardMarkup(row_width=2)
            for part in database[anime].keys():
                markup.add(InlineKeyboardButton(f"{part}-qism", callback_data=f"getvid_{anime}_{part}"))
            markup.add(InlineKeyboardButton("⬅️ Orqaga", callback_data="user_back"))
            bot.edit_message_text(f"📺 {anime} - Qismni tanlang:", call.message.chat.id, call.message.message_id, reply_markup=markup)
            
    elif data.startswith("getvid_"):
        parts = data.replace("getvid_", "").split("_", 1)
        anime, part = parts[0], parts[1]
        if anime in database and part in database[anime]:
            file_id = database[anime][part]
            bot.send_video(call.message.chat.id, file_id, caption=f"🎬 {anime} ({part}-qism)")
            
    elif data == "user_back":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        show_animes_to_user(call.message.chat.id)

def step_anime_name(message):
    anime_name = message.text.strip()
    msg = bot.send_message(message.chat.id, f"'{anime_name}' uchun qism raqamini yozing (masalan: 1):")
    bot.register_next_step_handler(msg, step_part_num, anime_name)

def step_part_num(message, anime_name):
    part = message.text.strip()
    msg = bot.send_message(message.chat.id, f"'{anime_name}' ning {part}-qismining **VIDEOSINI** yuboring:")
    bot.register_next_step_handler(msg, step_save_video, anime_name, part)

def step_save_video(message, anime_name, part):
    if message.video:
        file_id = message.video.file_id
        if anime_name not in database:
            database[anime_name] = {}
        database[anime_name][part] = file_id
        bot.send_message(message.chat.id, "✅ Muvaffaqiyatli saqlandi!", reply_markup=main_admin_menu())
    else:
        bot.send_message(message.chat.id, "⚠️ Bu video emas! Iltimos, qaytadan video yuboring.")

print("Bot ishga tushdi...")
bot.infinity_polling()
      
