import logging
import json
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot import types

TOKEN = "8248154561:AAGACWf3CEHoIcR84lPt9WECKKRRHe5WI-4"
ADMIN_ID = 7986354170
REQUIRED_CHANNEL = "@kanal_username"
DB_FILE = "anime_database.json"

logging.basicConfig(level=logging.INFO)
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# Render uxlab qolmasligi uchun oddiy veb-server
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

def admin_menu():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        types.KeyboardButton("➕ Yeni anime bo'limi"),
        types.KeyboardButton("🔄 Mavjud animeni almashtirish"),
        types.KeyboardButton("🗑 Mavjud animeni o'chirish"),
        types.KeyboardButton("📢 Majburiy kanal"),
        types.KeyboardButton("📅 Jadvalni yangilash"),
        types.KeyboardButton("📁 Animelar ro'yxati"),
        types.KeyboardButton("📊 Statistika"),
        types.KeyboardButton("🚀 Start (Asosiy menyu)")
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
    user_states.pop(user_id, None)
    
    if not check_sub_channel(user_id):
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("Kanalga a'zo bo'lish 🔗", url=f"https://t.me/{REQUIRED_CHANNEL.replace('@', '')}"))
        keyboard.add(types.InlineKeyboardButton("Tekshirish ✅", callback_data="check_sub"))
        bot.send_message(user_id, "Botdan foydalanish uchun quyidagi kanalga a'zo bo'lishingiz kerak:", reply_markup=keyboard)
        return

    if user_id == ADMIN_ID:
        bot.send_message(user_id, "Assalomu alaykum, Admin! Kerakli bo'limni tanlang:", reply_markup=admin_menu())
    else:
        bot.send_message(user_id, "Xush kelibsiz! Qidirmoqchi bo'lgan anime nomini yuboring (masalan: Death note, Naruto):")

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def callback_check_sub(call: types.CallbackQuery):
    if check_sub_channel(call.from_user.id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        if call.from_user.id == ADMIN_ID:
            bot.send_message(call.from_user.id, "Rahmat! Admin menyusi:", reply_markup=admin_menu())
        else:
            bot.send_message(call.from_user.id, "Rahmat! Qidirmoqchi bo'lgan anime nomini yuboring:")
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
        if text == "➕ Yeni anime bo'limi":
            user_states[user_id] = {"step": "choosing_action"}
            keyboard = types.InlineKeyboardMarkup(row_width=1)
            keyboard.add(
                types.InlineKeyboardButton("✨ Yangi jild ochish", callback_data="anime_new_folder"),
                types.InlineKeyboardButton("📁 Mavjud jildga anime qo'shish", callback_data="anime_existing_folder")
            )
            bot.send_message(user_id, "Anime qo'shish bo'limi. Kerakli harakatni tanlang:", reply_markup=keyboard)
            return

        elif text == "🔄 Mavjud animeni almashtirish":
            user_states[user_id] = {"step": "waiting_for_replace_name"}
            bot.send_message(user_id, "Almashtirmoqchi (o'zgartirmoqchi) bo'lgan anime nomini kiriting:", reply_markup=admin_menu())
            return

        elif text == "🗑 Mavjud animeni o'chirish":
            user_states[user_id] = {"step": "waiting_for_delete_code"}
            bot.send_message(user_id, "O'chirmoqchi bo'lgan anime qismining **kodini** kiriting:", reply_markup=admin_menu())
            return

        elif text == "📢 Majburiy kanal":
            user_states[user_id] = {"step": "waiting_for_channel"}
            bot.send_message(user_id, f"Hozirgi majburiy kanal: {REQUIRED_CHANNEL}\n\nYangi kanal username'ini kiriting:", reply_markup=admin_menu())
            return

        elif text == "📅 Jadvalni yangilash":
            user_states[user_id] = {"step": "waiting_for_schedule"}
            bot.send_message(user_id, "Jadval uchun yangi rasm yoki matn yuboring:", reply_markup=admin_menu())
            return

        elif text == "📁 Animelar ro'yxati":
            user_states.pop(user_id, None)
            if not anime_database:
                bot.send_message(user_id, "📁 Bazada hali animelar yo'q.", reply_markup=admin_menu())
            else:
                keyboard = types.InlineKeyboardMarkup(row_width=1)
                for name_key, data in anime_database.items():
                    keyboard.add(types.InlineKeyboardButton(text=f"📁 {data['name']}", callback_data=f"open_folder_{name_key}"))
                bot.send_message(user_id, "📁 **Bazadagi barcha jildlar va animelar:**", reply_markup=keyboard)
            return

        elif text == "📊 Statistika":
            user_states.pop(user_id, None)
            total = len(anime_database)
            parts_total = sum(len(d['parts']) for d in anime_database.values())
            bot.send_message(user_id, f"📊 Statistika:\nJildlar soni: {total}\nUmumiy qismlar soni: {parts_total}", reply_markup=admin_menu())
            return

        elif text == "🚀 Start (Asosiy menyu)":
            user_states.pop(user_id, None)
            bot.send_message(user_id, "Asosiy menyu:", reply_markup=admin_menu())
            return

        # FSM qadamlarini bajarish
        if step == "waiting_for_channel":
            REQUIRED_CHANNEL = text
            user_states.pop(user_id, None)
            bot.send_message(user_id, f"✅ Majburiy kanal o'zgartirildi: {REQUIRED_CHANNEL}", reply_markup=admin_menu())
            return

        if step == "waiting_for_schedule":
            user_states.pop(user_id, None)
            bot.send_message(user_id, "✅ Jadval qabul qilindi va saqlandi!", reply_markup=admin_menu())
            return

        if step == "waiting_for_delete_code":
            code_to_delete = text.lower()
            deleted = False
            for name_key, anime_data in list(anime_database.items()):
                parts = anime_data['parts']
                for part_num, p_data in list(parts.items()):
                    if p_data['code'].lower() == code_to_delete:
                        anime_title = anime_data['name']
                        del parts[part_num]
                        # Agar jildda boshqa qism qolmasa, jildning o'zini ham o'chirib yuboramiz
                        if not parts:
                            del anime_database[name_key]
                        save_database(anime_database)
                        deleted = True
                        break
                if deleted:
                    break

            user_states.pop(user_id, None)
            if deleted:
                bot.send_message(user_id, f"✅ Kod '{text}' bo'lgan anime qismi muvaffaqiyatli o'chirib yuborildi!", reply_markup=admin_menu())
            else:
                bot.send_message(user_id, f"❌ '{text}' kodli anime topilmadi. Qaytadan urinib ko'ring:", reply_markup=admin_menu())
            return

        if step == "waiting_for_replace_name":
            name_key = text.lower()
            if name_key in anime_database:
                user_states[user_id] = {"step": "waiting_for_replace_video", "name_key": name_key}
                bot.send_message(user_id, f"🎬 '{anime_database[name_key]['name']}' topildi. Endi yangi video faylni yuboring:")
            else:
                bot.send_message(user_id, "❌ Bunday nomdagi anime topilmadi. Qaytadan urinib ko'ring:")
            return

        if step == "waiting_for_replace_video":
            file_id = message.video.file_id if message.video else (message.document.file_id if message.document else None)
            if not file_id:
                bot.send_message(user_id, "❌ Iltimos, video fayl yuboring:")
                return
            state["file_id"] = file_id
            state["step"] = "waiting_for_replace_part"
            user_states[user_id] = state
            bot.send_message(user_id, "Video qabul qilindi. Qaysi qismini almashtirmoqchisiz (qism raqamini kiriting):")
            return

        if step == "waiting_for_replace_part":
            name_key = state.get("name_key")
            file_id = state.get("file_id")
            part_num = text
            if name_key in anime_database:
                if part_num in anime_database[name_key]['parts']:
                    anime_database[name_key]['parts'][part_num]['file_id'] = file_id
                    save_database(anime_database)
                    user_states.pop(user_id, None)
                    bot.send_message(user_id, f"✅ {anime_database[name_key]['name']} — {part_num}-qism videosi muvaffaqiyatli almashtirildi!", reply_markup=admin_menu())
                    return
                else:
                    bot.send_message(user_id, f"❌ Bu animeda {part_num}-qism mavjud emas. Mavjud qism raqamini kiriting:")
                    return

        if step == "waiting_for_folder_name":
            user_states[user_id] = {"step": "waiting_for_video", "name": text}
            bot.send_message(user_id, f"📂 Jild: <b>{text}</b>\n\nEndi animening **video faylini** yuboring:")
            return

        if step == "waiting_for_video":
            file_id = message.video.file_id if message.video else (message.document.file_id if message.document else None)
            if not file_id:
                bot.send_message(user_id, "❌ Iltimos, video fayl yuboring:")
                return
            state["file_id"] = file_id
            state["step"] = "waiting_for_part"
            user_states[user_id] = state
            bot.send_message(user_id, "Video qabul qilindi. Endi anime qism raqamini kiriting:")
            return

        if step == "waiting_for_part":
            state["part"] = text
            state["step"] = "waiting_for_code"
            user_states[user_id] = state
            bot.send_message(user_id, "Anime kodini kiriting (masalan: 01):")
            return

        if step == "waiting_for_code":
            state["code"] = text
            state["step"] = "waiting_for_hidden_name"
            user_states[user_id] = state
            bot.send_message(user_id, "Ushbu qism uchun yashirin nomni (ovoz berganlar yoki studiya) kiriting:")
            return

        if step == "waiting_for_hidden_name":
            anime_name = state.get('name')
            part = state.get('part')
            code = state.get('code')
            file_id = state.get('file_id')
            hidden_name = text
            
            name_key = anime_name.lower()
            if name_key not in anime_database:
                anime_database[name_key] = {'name': anime_name, 'parts': {}}
            
            anime_database[name_key]['parts'][part] = {
                'file_id': file_id,
                'code': code,
                'part': part,
                'hidden_name': hidden_name
            }
            save_database(anime_database)
            user_states.pop(user_id, None)
            
            bot.send_message(user_id, f"✅ Muvaffaqiyatli saqlandi!\n\n📁 Papka: {anime_name}\n🔢 Qism: {part}\n📌 Kod: {code}", reply_markup=admin_menu())
            return

    if not check_sub_channel(user_id):
        return

    query_lower = text.lower()
    matched_animes = []
    for name_key, anime_data in anime_database.items():
        if query_lower in name_key or query_lower in anime_data['name'].lower():
            matched_animes.append((name_key, anime_data['name']))
            
    if matched_animes:
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        for name_key, anime_title in matched_animes:
            keyboard.add(types.InlineKeyboardButton(text=f"📁 {anime_title}", callback_data=f"open_folder_{name_key}"))
        bot.send_message(user_id, "🎬 Topilgan animelar:", reply_markup=keyboard)
        return

    found_part = None
    for name_key, data in anime_database.items():
        for part_num, p_data in data['parts'].items():
            if p_data['code'].lower() == query_lower:
                found_part = (data['name'], p_data)
                break
        if found_part:
            break
            
    if found_part:
        anime_name, p_data = found_part
        caption = f"🎬 {anime_name} — {p_data['part']}-qism\n📌 Kodi: {p_data['code']}\n🎙 Ovoz berdi: {p_data['hidden_name']}"
        bot.send_video(user_id, video=p_data['file_id'], caption=caption)
    else:
        bot.send_message(user_id, "❌ Bunday kod yoki anime topilmadi. Qaytadan urinib ko'ring:")

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call: types.CallbackQuery):
    user_id = call.from_user.id
    data = call.data

    if data == "anime_new_folder" and user_id == ADMIN_ID:
        user_states[user_id] = {"step": "waiting_for_folder_name"}
        bot.edit_message_text("✨ Yangi anime uchun papka nomini kiriting:", call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id)
    elif data == "anime_existing_folder" and user_id == ADMIN_ID:
        if not anime_database:
            bot.answer_callback_query(call.id, "📁 Hali bazada jildlar mavjud emas!", show_alert=True)
            return
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        for name_key, d in anime_database.items():
            keyboard.add(types.InlineKeyboardButton(text=d['name'], callback_data=f"sel_fldr_{name_key}"))
        bot.edit_message_text("📁 Mavjud jildlardan birini tanlang:", call.message.chat.id, call.message.message_id, reply_markup=keyboard)
        bot.answer_callback_query(call.id)
    elif data.startswith("sel_fldr_") and user_id == ADMIN_ID:
        name_key = data.replace("sel_fldr_", "")
        if name_key in anime_database:
            folder_name = anime_database[name_key]['name']
            user_states[user_id] = {"step": "waiting_for_video", "name": folder_name}
            bot.edit_message_text(f"📁 Tanlangan jild: {folder_name}\n\nEndi animening video faylini yuboring:", call.message.chat.id, call.message.message_id)
            bot.answer_callback_query(call.id)
    elif data.startswith("open_folder_"):
        name_key = data.replace("open_folder_", "")
        if name_key in anime_database:
            anime_data = anime_database[name_key]
            keyboard = types.InlineKeyboardMarkup(row_width=5)
            buttons = [types.InlineKeyboardButton(text=str(p), callback_data=f"fldr_{name_key}_{p}") for p in sorted(anime_data['parts'].keys())]
            keyboard.add(*buttons)
            keyboard.add(types.InlineKeyboardButton(text="🔙 Ortga", callback_data="main_menu_back"))
            bot.edit_message_text(f"🎬 {anime_data['name']}\n📦 Jami qismlar: {len(anime_data['parts'])} ta\n\nKerakli qismni tanlang:", call.message.chat.id, call.message.message_id, reply_markup=keyboard)
            bot.answer_callback_query(call.id)
    elif data == "main_menu_back":
        bot.edit_message_text("✨ Anime nomini yuboring:", call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id)
    elif data.startswith("fldr_"):
        parts = data.split("_")
        if len(parts) >= 3:
            name_key, part_num = parts[1], parts[2]
            if name_key in anime_database and part_num in anime_database[name_key]['parts']:
                p_data = anime_database[name_key]['parts'][part_num]
                caption = f"🎬 {anime_database[name_key]['name']} — {p_data['part']}-qism\n📌 Kodi: {p_data['code']}\n🎙 Ovoz berdi: {p_data['hidden_name']}"
                bot.send_video(call.message.chat.id, video=p_data['file_id'], caption=caption)
                bot.answer_callback_query(call.id)

if __name__ == '__main__':
    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()

    bot.infinity_polling(skip_pending=True)
    
