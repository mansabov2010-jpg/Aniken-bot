import logging
import asyncio
import json
import os
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiohttp import web

# --- RENDER UCHUN FLASK/AIOHTTP WEB SERVER (Uxlab qolmasligi uchun) ---
async def handle(request):
    return web.Response(text="Bot is running 24/7!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
# ---------------------------------------------------------------------

TOKEN = "8248154561:AAGACWf3CEHoIcR84lPt9WECKKRRHe5WI-4"
ADMIN_ID = 7986354170
REQUIRED_CHANNEL = "@kanal_username"
DB_FILE = "anime_database.json"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

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

class AnimeState(StatesGroup):
    choosing_action = State()
    waiting_for_folder_name = State()
    waiting_for_video = State()
    waiting_for_part = State()
    waiting_for_code = State()
    waiting_for_hidden_name = State()

class ChannelState(StatesGroup):
    waiting_for_channel = State()

def admin_menu():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        KeyboardButton("➕ Yeni anime bo'limi"),
        KeyboardButton("🔄 Mavjud animeni almashtirish"),
        KeyboardButton("📢 Majburiy kanal"),
        KeyboardButton("📅 Jadvalni yangilash"),
        KeyboardButton("📁 Animelar ro'yxati"),
        KeyboardButton("📊 Statistika"),
        KeyboardButton("🚀 Start (Asosiy menyu)")
    )
    return keyboard

async def check_sub_channel(user_id):
    global REQUIRED_CHANNEL
    if not REQUIRED_CHANNEL or REQUIRED_CHANNEL == "@kanal_username":
        return True
    try:
        member = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=user_id)
        if member.status in ["member", "creator", "administrator"]:
            return True
    except Exception:
        pass
    return False

@dp.message_handler(commands=['start'], state='*')
async def cmd_start(message: types.Message, state: FSMContext):
    await state.finish()
    if not await check_sub_channel(message.from_user.id):
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("Kanalga a'zo bo'lish 🔗", url=f"https://t.me/{REQUIRED_CHANNEL.replace('@', '')}"))
        keyboard.add(InlineKeyboardButton("Tekshirish ✅", callback_data="check_sub"))
        await message.answer("Botdan foydalanish uchun quyidagi kanalga a'zo bo'lishingiz kerak:", reply_markup=keyboard)
        return

    if message.from_user.id == ADMIN_ID:
        await message.answer("Assalomu alaykum, Admin! Kerakli bo'limni tanlang:", reply_markup=admin_menu())
    else:
        await message.answer("Xush kelibsiz! Qidirmoqchi bo'lgan anime nomini yuboring (masalan: Death note, Naruto):")

@dp.callback_query_handler(text="check_sub")
async def callback_check_sub(call: types.CallbackQuery):
    if await check_sub_channel(call.from_user.id):
        await call.message.delete()
        if call.from_user.id == ADMIN_ID:
            await call.message.answer("Rahmat! Admin menyusi:", reply_markup=admin_menu())
        else:
            await call.message.answer("Rahmat! Qidirmoqchi bo'lgan anime nomini yuboring:")
    else:
        await call.answer("Siz hali kanalga a'zo bo'lmadingiz!", show_alert=True)

@dp.message_handler(state='*', content_types=types.ContentType.TEXT)
async def main_text_handler(message: types.Message, state: FSMContext):
    global REQUIRED_CHANNEL
    text = message.text.strip()
    user_id = message.from_user.id
    
    if user_id == ADMIN_ID:
        if text == "➕ Yeni anime bo'limi":
            await state.finish()
            keyboard = InlineKeyboardMarkup(row_width=1)
            keyboard.add(
                InlineKeyboardButton("✨ Yangi jild ochish", callback_data="anime_new_folder"),
                InlineKeyboardButton("📁 Mavjud jildga anime qo'shish", callback_data="anime_existing_folder")
            )
            await message.answer("Anime qo'shish bo'limi. Kerakli harakatni tanlang:", reply_markup=keyboard)
            await AnimeState.choosing_action.set()
            return

        elif text == "📢 Majburiy kanal":
            await state.finish()
            await message.answer(f"Hozirgi majburiy kanal: {REQUIRED_CHANNEL}\n\nYangi kanal username'ini kiriting:", reply_markup=admin_menu())
            await ChannelState.waiting_for_channel.set()
            return

        elif text == "🔄 Mavjud animeni almashtirish":
            await state.finish()
            await message.answer("Almashtirmoqchi bo'lgan anime nomini kiriting:", reply_markup=admin_menu())
            return

        elif text == "📅 Jadvalni yangilash":
            await state.finish()
            await message.answer("Jadval bo'limi.", reply_markup=admin_menu())
            return

        elif text == "📁 Animelar ro'yxati":
            await state.finish()
            if not anime_database:
                await message.answer("📁 Bazada hali animelar yo'q.", reply_markup=admin_menu())
            else:
                keyboard = InlineKeyboardMarkup(row_width=1)
                for name_key, data in anime_database.items():
                    keyboard.add(InlineKeyboardButton(text=f"📁 {data['name']}", callback_data=f"open_folder_{name_key}"))
                await message.answer("📁 **Bazadagi barcha jildlar va animelar:**", parse_mode="Markdown", reply_markup=keyboard)
            return

        elif text == "📊 Statistika":
            await state.finish()
            total = len(anime_database)
            parts_total = sum(len(d['parts']) for d in anime_database.values())
            await message.answer(f"📊 Statistika:\nJildlar soni: {total}\nUmumiy qismlar soni: {parts_total}", reply_markup=admin_menu())
            return

        elif text == "🚀 Start (Asosiy menyu)":
            await state.finish()
            await message.answer("Asosiy menyu:", reply_markup=admin_menu())
            return

    current_state = await state.get_state()
    
    if current_state == ChannelState.waiting_for_channel.state and user_id == ADMIN_ID:
        REQUIRED_CHANNEL = text
        await message.answer(f"✅ Majburiy kanal o'zgartirildi: {REQUIRED_CHANNEL}", reply_markup=admin_menu())
        await state.finish()
        return

    if current_state == AnimeState.waiting_for_folder_name.state and user_id == ADMIN_ID:
        await state.update_data(name=text)
        await message.answer(f"📂 Jild: <b>{text}</b>\n\nEndi animening **video faylini** yuboring:", parse_mode="HTML")
        await AnimeState.waiting_for_video.set()
        return

    if current_state == AnimeState.waiting_for_part.state and user_id == ADMIN_ID:
        await state.update_data(part=text)
        await message.answer("Anime kodini kiriting (masalan: 01):")
        await AnimeState.waiting_for_code.set()
        return

    if current_state == AnimeState.waiting_for_code.state and user_id == ADMIN_ID:
        await state.update_data(code=text)
        await message.answer("Ushbu qism uchun yashirin nomni (ovoz berganlar yoki studiya) kiriting:")
        await AnimeState.waiting_for_hidden_name.set()
        return

    if current_state == AnimeState.waiting_for_hidden_name.state and user_id == ADMIN_ID:
        data = await state.get_data()
        code = data.get('code')
        anime_name = data.get('name')
        part = data.get('part')
        file_id = data.get('file_id')
        hidden_name = text
        
        name_key = anime_name.lower()
        
        if name_key not in anime_database:
            anime_database[name_key] = {
                'name': anime_name,
                'parts': {}
            }
        
        anime_database[name_key]['parts'][part] = {
            'file_id': file_id,
            'code': code,
            'part': part,
            'hidden_name': hidden_name
        }
        
        save_database(anime_database)
        
        await message.answer(
            f"✅ Muvaffaqiyatli saqlandi va faylga yozildi!\n\n"
            f"📁 Papka: {anime_name}\n"
            f"🔢 Qism raqami: {part}\n"
            f"📌 Kodi: {code}",
            reply_markup=admin_menu()
        )
        await state.finish()
        return

    await state.finish()
    if not await check_sub_channel(user_id):
        return
        
    query_lower = text.lower()
    
    matched_animes = []
    for name_key, anime_data in anime_database.items():
        if query_lower in name_key or query_lower in anime_data['name'].lower():
            matched_animes.append((name_key, anime_data['name']))
            
    if matched_animes:
        text_msg = "🎬 Topilgan animelar:"
        keyboard = InlineKeyboardMarkup(row_width=1)
        for name_key, anime_title in matched_animes:
            keyboard.add(InlineKeyboardButton(text=f"📁 {anime_title}", callback_data=f"open_folder_{name_key}"))

        await message.answer(text_msg, reply_markup=keyboard)
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
        await message.answer_video(video=p_data['file_id'], caption=caption, parse_mode="Markdown")
    else:
        await message.answer("❌ Bunday kod yoki anime topilmadi. Qaytadan urinib ko'ring:")

@dp.message_handler(state=AnimeState.waiting_for_video, content_types=['video', 'document'], user_id=ADMIN_ID)
async def process_anime_video(message: types.Message, state: FSMContext):
    file_id = message.video.file_id if message.video else message.document.file_id
    await state.update_data(file_id=file_id)
    await message.answer("Video qabul qilindi. Endi anime qism raqamini kiriting:")
    await AnimeState.waiting_for_part.set()

@dp.callback_query_handler(state=AnimeState.choosing_action, user_id=ADMIN_ID)
async def process_anime_action_choice(call: types.CallbackQuery, state: FSMContext):
    action = call.data
    if action == "anime_new_folder":
        await call.message.edit_text("✨ Yangi anime uchun papka nomini kiriting:")
        await AnimeState.waiting_for_folder_name.set()
        await call.answer()
    elif action == "anime_existing_folder":
        if not anime_database:
            await call.answer("📁 Hali bazada jildlar mavjud emas!", show_alert=True)
            return
        keyboard = InlineKeyboardMarkup(row_width=2)
        for name_key, data in anime_database.items():
            keyboard.insert(InlineKeyboardButton(text=data['name'], callback_data=f"sel_fldr_{name_key}"))
        await call.message.edit_text("📁 Mavjud jildlardan birini tanlang:", reply_markup=keyboard)
        await AnimeState.waiting_for_folder_name.set()
        await call.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("sel_fldr_"), state=AnimeState.waiting_for_folder_name, user_id=ADMIN_ID)
async def process_existing_folder_selection(call: types.CallbackQuery, state: FSMContext):
    name_key = call.data.replace("sel_fldr_", "")
    if name_key in anime_database:
        folder_name = anime_database[name_key]['name']
        await state.update_data(name=folder_name)
        await call.message.edit_text(f"📁 Tanlangan jild: {folder_name}\n\nEndi animening video faylini yuboring:")
        await AnimeState.waiting_for_video.set()
        await call.answer()
    else:
        await call.answer("❌ Jild topilmadi!", show_alert=True)

@dp.callback_query_handler(lambda c: c.data.startswith("open_folder_"))
async def open_anime_folder(call: types.CallbackQuery):
    name_key = call.data.replace("open_folder_", "")
    if name_key in anime_database:
        anime_data = anime_database[name_key]
        parts_count = len(anime_data['parts'])
        
        text = f"🎬 {anime_data['name']}\n📦 Jami qismlar soni: {parts_count} ta\n\nKerakli qismni tanlang:"
        
        keyboard = InlineKeyboardMarkup(row_width=5)
        buttons = []
        for part_num in sorted(anime_data['parts'].keys(), key=lambda x: int(x) if x.isdigit() else x):
            buttons.append(InlineKeyboardButton(text=str(part_num), callback_data=f"fldr_{name_key}_{part_num}"))
        
        keyboard.add(*buttons)
        keyboard.add(InlineKeyboardButton(text="🔙 Ortga", callback_data="main_menu_back"))
        
        await call.message.edit_text(text, reply_markup=keyboard)
        await call.answer()
    else:
        await call.answer("❌ Jild topilmadi!", show_alert=True)

@dp.callback_query_handler(lambda c: c.data == "main_menu_back")
async def process_main_menu_back(call: types.CallbackQuery):
    await call.message.edit_text("✨ Anime nomini yuboring:")
    await call.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("fldr_"))
async def send_selected_folder_part(call: types.CallbackQuery):
    data_parts = call.data.split("_")
    if len(data_parts) >= 3:
        name_key = data_parts[1]
        part_num = data_parts[2]
        
        if name_key in anime_database and part_num in anime_database[name_key]['parts']:
            anime_data = anime_database[name_key]
            p_data = anime_data['parts'][part_num]
            
            caption = f"🎬 {anime_data['name']} — {p_data['part']}-qism\n📌 Kodi: {p_data['code']}\n🎙 Ovoz berdi: {p_data['hidden_name']}"
            
            await bot.send_video(
                chat_id=call.message.chat.id,
                video=p_data['file_id'],
                caption=caption,
                parse_mode="Markdown"
            )
            await call.answer()
        else:
            await call.answer("❌ Bu qism topilmadi!", show_alert=True)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_web_server())
    
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True)
    
