import logging
import json
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot import types
import time

TOKEN = "8248154561:AAEm-5cEgfcbkQBwN59indBrZFMyuRuYo4Q"
ADMIN_ID = 7986354170
REQUIRED_CHANNEL = "@kanal_username"
DB_FILE = "anime_database.json"

logging.basicConfig(level=logging.INFO)
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running 24/7!")
    def log_message(self, format, *args):
        pass

def run_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

def load_database():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_database(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

anime_database = load_database()
user_states = {}

def start_keyboard(code_text=None):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    if code_text:
        btn_text = "🚀 Start (" + str(code_text) + ")"
    else:
        btn_text = "🚀 Start"
    keyboard.add(types.KeyboardButton(btn_text))
    return keyboard

def admin_inline_menu():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("➕ Yangi anime bo'limi", callback_data="admin_new_anime_menu"),
        types.InlineKeyboardButton("🔄 Animeni almashtirish", callback_data="admin_replace_anime"),
        types.InlineKeyboardButton("🗑 Animeni o'chirish", callback_data="admin_delete_anime"),
        types.InlineKeyboardButton("📢 Majburiy kanal", callback_data="admin_channel"),
        types.InlineKeyboardButton("📅 Jadvalni yangilash", callback_data="admin_schedule"),
        types.InlineKeyboardButton("📁 Animelar ro'yxati", callback_data="admin_list"),
        types.InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")
    )
    return keyboard

def check_sub_channel(user_id):
    global REQUIRED_CHANNEL
    if not REQUIRED_CHANNEL or REQUIRED_CHANNEL == "@kanal_username":
        return True
    try:
        member = bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=user_id)
        if member.status in ["member", "creator", "administrator"]:
            return True
    except Exception:
        pass
    return False

@bot.message_handler(commands=['start'])
def cmd_start(message: types.Message):
    user_id = message.from_user.id
    args = message.text.split()
    
    if len(args) > 1:
        code_arg = args[1].lower()
        found_anime = None
        for name_key, data in anime_database.items():
            if data.get('code', '').lower() == code_arg:
                found_anime = (name_key, data)
                break
        
        if found_anime:
            name_key, data = found_anime
            caption = "🎬 <b>" + str(data['name']) + "</b>\n\n📖 <b>Ma'lumot:</b> " + str(data.get('info', 'Mavjud emas')) + "\n📌 <b>Kodi:</b> " + str(data.get('code', 'Yo\'q'))
            
            keyboard = types.InlineKeyboardMarkup(row_width=5)
            buttons = [types.InlineKeyboardButton(text=str(p), callback_data="fldr_" + str(name_key) + "_" + str(p)) for p in sorted(data['parts'].keys(), key=lambda x: int(x) if x.isdigit() else x)]
            keyboard.add(*buttons)
            
            if data.get('photo'):
                bot.send_photo(user_id, photo=data['photo'], caption=caption, reply_markup=keyboard)
            else:
                bot.send_message(user_id, caption, reply_markup=keyboard)
            return

    user_states.pop(user_id, None)
    if not check_sub_channel(user_id):
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("Kanalga a'zo bo'lish 🔗", url="https://t.me/" + REQUIRED_CHANNEL.replace('@', '')))
        keyboard.add(types.InlineKeyboardButton("Tekshirish ✅", callback_data="check_sub"))
        bot.send_message(user_id, "Botdan foydalanish uchun quyidagi kanalga a'zo bo'lishingiz kerak:", reply_markup=keyboard)
        return

    if user_id == ADMIN_ID:
        bot.send_message(user_id, "Assalomu alaykum, Admin! Kerakli bo'limni tanlang:", reply_markup=admin_inline_menu())
    else:
        bot.send_message(user_id, "Xush kelibsiz! Qidirmoqchi bo'lgan anime nomini yoki kodini yuboring:", reply_markup=start_keyboard())

@bot.message_handler(commands=['anime'])
def cmd_anime_search(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(message, "Iltimos, anime nomi yoki kodini kiriting. Masalan: /anime Death note")
        return
    
    query = args[1].lower()
    found_anime = None
    for name_key, data in anime_database.items():
        if query in name_key or query in data['name'].lower() or query == data.get('code', '').lower():
            found_anime = (name_key, data)
            break
            
    if found_anime:
        name_key, data = found_anime
        bot_info = bot.get_me()
        bot_username = bot_info.username
        code = data.get('code', '')
        
        caption = "🎬 <b>" + str(data['name']) + "</b>\n📦 Qismlar soni: " + str(len(data['parts'])) + " ta\n📌 Kodi: " + str(code)
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("🎬 Animeni ko'rish", url="https://t.me/" + str(bot_username) + "?start=" + str(code)))
        
        if data.get('photo'):
            bot.send_photo(message.chat.id, photo=data['photo'], caption=caption, reply_markup=keyboard)
        else:
            bot.send_message(message.chat.id, caption, reply_markup=keyboard)
    else:
        bot.reply_to(message, "❌ Bunday anime topilmadi.")

@bot.message_handler(func=lambda msg: msg.text and msg.text.startswith("🚀 Start"))
def msg_start_text(message: types.Message):
    user_id = message.from_user.id
    user_states.pop(user_id, None)
    if not check_sub_channel(user_id):
        return
    if user_id == ADMIN_ID:
        bot.send_message(user_id, "Admin menyusi:", reply_markup=admin_inline_menu())
    else:
        bot.send_message(user_id, "Xush kelibsiz! Qidirmoqchi bo'lgan anime nomini yoki kodini yuboring:", reply_markup=start_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def callback_check_sub(call: types.CallbackQuery):
    if check_sub_channel(call.from_user.id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        if call.from_user.id == ADMIN_ID:
            bot.send_message(call.from_user.id, "Rahmat! Admin menyusi:", reply_markup=admin_inline_menu())
        else:
            bot.send_message(call.from_user.id, "Rahmat! Qidirmoqchi bo'lgan anime nomini yoki kodini yuboring:", reply_markup=start_keyboard())
    else:
        bot.answer_callback_query(call.id, "Siz hali kanalga a'zo bo'lmadingiz!", show_alert=True)

@bot.message_handler(func=lambda msg: True, content_types=['text', 'video', 'document', 'photo'])
def main_handler(message: types.Message):
    global REQUIRED_CHANNEL
    user_id = message.from_user.id
    text = message.text.strip() if message.text else ""
    state = user_states.get(user_id, {})
    step = state.get("step")

    if user_id == ADMIN_ID:
        if step == "waiting_for_channel":
            REQUIRED_CHANNEL = text
            user_states.pop(user_id, None)
            bot.send_message(user_id, "✅ Majburiy kanal o'zgartirildi: " + str(REQUIRED_CHANNEL), reply_markup=admin_inline_menu())
            return

        if step == "waiting_for_schedule":
            user_states.pop(user_id, None)
            bot.send_message(user_id, "✅ Jadval qabul qilindi va saqlandi!", reply_markup=admin_inline_menu())
            return

        if step == "waiting_for_delete_code":
            code_to_delete = text.lower()
            deleted = False
            for name_key, anime_data in list(anime_database.items()):
                if anime_data.get('code', '').lower() == code_to_delete:
                    del anime_database[name_key]
                    save_database(anime_database)
                    deleted = True
                    break

            user_states.pop(user_id, None)
            if deleted:
                bot.send_message(user_id, "✅ Kod '" + str(text) + "' bo'lgan anime papkasi muvaffaqiyatli o'chirib yuborildi!", reply_markup=admin_inline_menu())
            else:
                bot.send_message(user_id, "❌ '" + str(text) + "' kodli anime topilmadi. Qaytadan urinib ko'ring:", reply_markup=admin_inline_menu())
            return

        if step == "waiting_for_folder_name":
            state["name"] = text
            state["step"] = "waiting_for_folder_code"
            user_states[user_id] = state
            bot.send_message(user_id, "📌 Anime uchun **kod** kiriting (masalan: 1):")
            return

        if step == "waiting_for_folder_code":
            state["code"] = text
            state["step"] = "waiting_for_folder_photo"
            user_states[user_id] = state
            bot.send_message(user_id, "🖼 Anime uchun **rasm** yuboring:")
            return

        if step == "waiting_for_folder_photo":
            photo_id = message.photo[-1].file_id if message.photo else None
            if not photo_id:
                bot.send_message(user_id, "❌ Iltimos, rasm yuboring:")
                return
            state["photo"] = photo_id
            state["step"] = "waiting_for_folder_info"
            user_states[user_id] = state
            bot.send_message(user_id, "📖 Anime haqida **ma'lumot** kiriting:")
            return

        if step == "waiting_for_folder_info":
            state["info"] = text
            anime_name = state.get("name")
            code = state.get("code")
            photo = state.get("photo")
            info = state.get("info")
            
            name_key = anime_name.lower()
            anime_database[name_key] = {
                'name': anime_name,
                'code': code,
                'photo': photo,
                'info': info,
                'parts': {}
            }
            save_database(anime_database)
            
            state["name_key"] = name_key
            state["step"] = "waiting_for_part_video"
            user_states[user_id] = state
            bot.send_message(user_id, "✅ Jild ochildi! Endi 1-qism uchun **video faylni** yuboring:")
            return

        if step == "waiting_for_existing_folder_video":
            if message.video:
                file_id = message.video.file_id
            elif message.document:
                file_id = message.document.file_id
            else:
                file_id = None
            
            if not file_id:
                bot.send_message(user_id, "❌ Iltimos, video fayl yuboring:")
                return
            state["file_id"] = file_id
            state["step"] = "waiting_for_existing_folder_part_num"
            user_states[user_id] = state
            bot.send_message(user_id, "Video qabul qilindi. Ushbu qism raqamini kiriting (masalan: 1):")
            return

        if step == "waiting_for_existing_folder_part_num":
            name_key = state.get("name_key")
            file_id = state.get("file_id")
            part_num = text
            if name_key in anime_database:
                anime_database[name_key]['parts'][part_num] = {'file_id': file_id, 'part': part_num}
                save_database(anime_database)
                user_states.pop(user_id, None)
                bot.send_message(user_id, "✅ " + str(anime_database[name_key]['name']) + " uchun " + str(part_num) + "-qism muvaffaqiyatli qo'shildi!", reply_markup=admin_inline_menu())
                return

        if step == "waiting_for_part_video":
            if message.video:
                file_id = message.video.file_id
            elif message.document:
                file_id = message.document.file_id
            else:
                file_id = None
            
            if not file_id:
                bot.send_message(user_id, "❌ Iltimos, video fayl yuboring:")
                return
            state["file_id"] = file_id
            state["step"] = "waiting_for_part_num"
            user_states[user_id] = state
            bot.send_message(user_id, "Video qabul qilindi. Qism raqamini kiriting (masalan: 1):")
            return

        if step == "waiting_for_part_num":
            name_key = state.get("name_key")
            file_id = state.get("file_id")
            part_num = text
            if name_key in anime_database:
                anime_database[name_key]['parts'][part_num] = {'file_id': file_id, 'part': part_num}
                save_database(anime_database)
                
                keyboard = types.InlineKeyboardMarkup(row_width=2)
                keyboard.add(
                    types.InlineKeyboardButton("➕ Yana qism qo'shish", callback_data="add_more_part_" + str(name_key)),
                    types.InlineKeyboardButton("✅ Tamomlash", callback_data="admin_main_menu")
                )
                bot.send_message(user_id, "✅ " + str(part_num) + "-qism qo'shildi! Yana qism qo'shasizmi?", reply_markup=keyboard)
                user_states.pop(user_id, None)
                return

    if not check_sub_channel(user_id):
        return

    query_lower = text.lower()
    found_anime = None
    for name_key, data in anime_database.items():
        if query_lower in name_key or query_lower in data['name'].lower() or query_lower == data.get('code', '').lower():
            found_anime = (name_key, data)
            break
            
    if found_anime:
        name_key, data = found_anime
        code = data.get('code', '')
        caption = "🎬 <b>" + str(data['name']) + "</b>\n\n📖 <b>Ma'lumot:</b> " + str(data.get('info', 'Mavjud emas')) + "\n📌 <b>Kodi:</b> " + str(code)
        
        keyboard = types.InlineKeyboardMarkup(row_width=5)
        buttons = [types.InlineKeyboardButton(text=str(p), callback_data="fldr_" + str(name_key) + "_" + str(p)) for p in sorted(data['parts'].keys(), key=lambda x: int(x) if x.isdigit() else x)]
        keyboard.add(*buttons)
        
        if data.get('photo'):
            bot.send_photo(user_id, photo=data['photo'], caption=caption, reply_markup=keyboard)
        else:
            bot.send_message(user_id, caption, reply_markup=keyboard)
        
        bot.send_message(user_id, "⬇️ Shu anime uchun pastdagi Start tugmasidan foydalanishingiz mumkin:", reply_markup=start_keyboard(code))
    else:
        bot.send_message(user_id, "❌ Bunday nomdagi yoki kodli anime topilmadi. Qaytadan urinib ko'ring:")

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call: types.CallbackQuery):
    user_id = call.from_user.id
    data = call.data

    if data == "admin_new_anime_menu" and user_id == ADMIN_ID:
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            types.InlineKeyboardButton("✨ Yangi jild ochish", callback_data="anime_new_folder"),
            types.InlineKeyboardButton("📁 Mavjud jildga qism qo'shish", callback_data="anime_existing_folder"),
            types.InlineKeyboardButton("🔙 Ortga", callback_data="admin_main_menu")
        )
        bot.edit_message_text("➕ Anime qo'shish bo'limi. Kerakli harakatni tanlang:", call.message.chat.id, call.message.message_id, reply_markup=keyboard)
        bot.answer_callback_query(call.id)

    elif data == "anime_new_folder" and user_id == ADMIN_ID:
        user_states[user_id] = {"step": "waiting_for_folder_name"}
        bot.edit_message_text("✨ Yangi anime nomini kiriting:", call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id)

    elif data == "anime_existing_folder" and user_id == ADMIN_ID:
        if not anime_database:
            bot.answer_callback_query(call.id, "📁 Hali bazada jildlar mavjud emas!", show_alert=True)
            return
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        for name_key, d in anime_database.items():
            keyboard.add(types.InlineKeyboardButton(text=d['name'], callback_data="sel_fldr_" + str(name_key)))
        keyboard.add(types.InlineKeyboardButton(text="🔙 Ortga", callback_data="admin_new_anime_menu"))
        bot.edit_message_text("📁 Mavjud jildlardan birini tanlang:", call.message.chat.id, call.message.message_id, reply_markup=keyboard)
        bot.answer_callback_query(call.id)

    elif data.startswith("sel_fldr_") and user_id == ADMIN_ID:
        name_key = data.replace("sel_fldr_", "")
        if name_key in anime_database:
            folder_name = anime_database[name_key]['name']
            user_states[user_id] = {"step": "waiting_for_existing_folder_video", "name_key": name_key}
            bot.edit_message_text("📁 Tanlangan anime: " + str(folder_name) + "\n\nEndi yangi qism uchun video faylni yuboring:", call.message.chat.id, call.message.message_id)
            bot.answer_callback_query(call.id)

    elif data.startswith("add_more_part_") and user_id == ADMIN_ID:
        name_key = data.replace("add_more_part_", "")
        if name_key in anime_database:
            user_states[user_id] = {"step": "waiting_for_existing_folder_video", "name_key": name_key}
            bot.send_message(user_id, "📁 " + str(anime_database[name_key]['name']) + " uchun keyingi qismning video faylini yuboring:")
            bot.answer_callback_query(call.id)

    elif data == "admin_replace_anime" and user_id == ADMIN_ID:
        user_states[user_id] = {"step": "waiting_for_replace_name"}
        bot.edit_message_text("Almashtirmoqchi bo'lgan anime nomini kiriting:", call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id)

    elif data == "admin_delete_anime" and user_id == ADMIN_ID:
        user_states[user_id] = {"step": "waiting_for_delete_code"}
        bot.edit_message_text("O'chirmoqchi bo'lgan anime **kodini** kiriting:", call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id)

    elif data == "admin_channel" and user_id == ADMIN_ID:
        user_states[user_id] = {"step": "waiting_for_channel"}
        bot.edit_message_text("Hozirgi majburiy kanal: " + str(REQUIRED_CHANNEL) + "\n\nYangi kanal username'ini kiriting:", call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id)

    elif data == "admin_schedule" and user_id == ADMIN_ID:
        user_states[user_id] = {"step": "waiting_for_schedule"}
        bot.edit_message_text("Jadval uchun yangi rasm yoki matn yuboring:", call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id)

    elif data == "admin_list" and user_id == ADMIN_ID:
        user_states.pop(user_id, None)
        if not anime_database:
            bot.answer_callback_query(call.id, "📁 Bazada hali animelar yo'q.", show_alert=True)
        else:
            keyboard = types.InlineKeyboardMarkup(row_width=1)
            for name_key, data_item in anime_database.items():
                keyboard.add(types.InlineKeyboardButton(text="📁 " + str(data_item['name']), callback_data="open_folder_" + str(name_key)))
            keyboard.add(types.InlineKeyboardButton(text="🔙 Ortga", callback_data="admin_main_menu"))
            bot.edit_message_text("📁 **Bazadagi barcha jildlar va animelar:**", call.message.chat.id, call.message.message_id, reply_markup=keyboard)
            bot.answer_callback_query(call.id)

    elif data == "admin_stats" and user_id == ADMIN_ID:
        user_states.pop(user_id, None)
        total = len(anime_database)
        parts_total = sum(len(d['parts']) for d in anime_database.values())
   
