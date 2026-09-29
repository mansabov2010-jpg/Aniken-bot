import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

# Token va Admin ID
TOKEN = "8981883684:AAEj9PzhB0LbPsMY0AJP68byGb7KS47Xs_M"
ADMIN_ID = 7986354170

# Majburiy kanal username'i
REQUIRED_CHANNEL = "@kanal_username"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Vaqtinchalik bazamiz (animelarni saqlash uchun: code -> data)
anime_database = {}

# FSM holatlari
class AnimeState(StatesGroup):
    waiting_for_video = State()
    waiting_for_part = State()
    waiting_for_code = State()
    waiting_for_name = State()
    waiting_for_hidden_name = State()

class ChannelState(StatesGroup):
    waiting_for_channel = State()

# 7 ta asosiy admin menyu tugmasi
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

# Obunani tekshirish funksiyasi
async def check_sub_channel(user_id):
    try:
        member = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=user_id)
        if member.status in ["member", "creator", "administrator"]:
            return True
    except Exception:
        pass
    return False

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    if REQUIRED_CHANNEL and not await check_sub_channel(message.from_user.id):
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("Kanalga a'zo bo'lish 🔗", url=f"https://t.me/{REQUIRED_CHANNEL.replace('@', '')}"))
        keyboard.add(InlineKeyboardButton("Tekshirish ✅", callback_data="check_sub"))
        await message.answer("Botdan foydalanish uchun quyidagi kanalga a'zo bo'lishingiz kerak:", reply_markup=keyboard)
        return

    if message.from_user.id == ADMIN_ID:
        await message.answer("Assalomu alaykum, Admin! Kerakli bo'limni tanlang:", reply_markup=admin_menu())
    else:
        await message.answer("Xush kelibsiz! Ko'rish uchun anime **kodini** yuboring:")

@dp.callback_query_handler(text="check_sub")
async def callback_check_sub(call: types.CallbackQuery):
    if await check_sub_channel(call.from_user.id):
        await call.message.delete()
        await call.message.answer("Rahmat! Endi botdan foydalanishingiz mumkin.", reply_markup=admin_menu() if call.from_user.id == ADMIN_ID else None)
    else:
        await call.answer("Siz hali kanalga a'zo bo'lmadingiz!", show_alert=True)

# 1. Anime qo'shish tartibi: Avval video, keyin qismi, kodi, nomi va yashirin nomi
@dp.message_handler(lambda message: message.text == "➕ Yeni anime bo'limi", user_id=ADMIN_ID)
async def add_anime_start(message: types.Message):
    await message.answer("Iltimos, avval anime uchun **video faylni** yuboring:")
    await AnimeState.waiting_for_video.set()

@dp.message_handler(content_types=['video', 'document'], state=AnimeState.waiting_for_video, user_id=ADMIN_ID)
async def process_anime_video(message: types.Message, state: FSMContext):
    file_id = message.video.file_id if message.video else message.document.file_id
    await state.update_data(file_id=file_id)
    await message.answer("Video qabul qilindi. Endi anime **qismini** kiriting (masalan: 1-qism):")
    await AnimeState.waiting_for_part.set()

@dp.message_handler(state=AnimeState.waiting_for_part, user_id=ADMIN_ID)
async def process_anime_part(message: types.Message, state: FSMContext):
    await state.update_data(part=message.text)
    await message.answer("Endi anime **kodini** kiriting (masalan: 01):")
    await AnimeState.waiting_for_code.set()

@dp.message_handler(state=AnimeState.waiting_for_code, user_id=ADMIN_ID)
async def process_anime_code(message: types.Message, state: FSMContext):
    await state.update_data(code=message.text)
    await message.answer("Endi anime **nomini** kiriting:")
    await AnimeState.waiting_for_name.set()

@dp.message_handler(state=AnimeState.waiting_for_name, user_id=ADMIN_ID)
async def process_anime_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Endi anime uchun **yashirin nomini** kiriting:")
    await AnimeState.waiting_for_hidden_name.set()

@dp.message_handler(state=AnimeState.waiting_for_hidden_name, user_id=ADMIN_ID)
async def process_anime_hidden_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    code = data.get('code')
    
    # Bazaga saqlab qo'yamiz
    anime_database[code] = {
        'file_id': data.get('file_id'),
        'part': data.get('part'),
        'code': code,
        'name': data.get('name'),
        'hidden_name': message.text
    }
    
    await message.answer(
        f"✅ Anime muvaffaqiyatli saqlandi!\n\n"
        f"📌 Nomi: {data.get('name')}\n"
        f"🕶 Yashirin nomi: {message.text}\n"
        f"🔢 Kodi: {code}\n"
        f"🎬 Qismi: {data.get('part')}", 
        reply_markup=admin_menu()
    )
    await state.finish()

# 2. Majburiy kanalni sozlash
@dp.message_handler(lambda message: message.text == "📢 Majburiy kanal", user_id=ADMIN_ID)
async def set_mandatory_channel(message: types.Message):
    await message.answer(f"Hozirgi majburiy kanal: {REQUIRED_CHANNEL}\n\nYangi kanal username'ini kiriting (masalan: @kanal_nomi):", reply_markup=admin_menu())
    await ChannelState.waiting_for_channel.set()

@dp.message_handler(state=ChannelState.waiting_for_channel, user_id=ADMIN_ID)
async def save_mandatory_channel(message: types.Message, state: FSMContext):
    global REQUIRED_CHANNEL
    REQUIRED_CHANNEL = message.text.strip()
    await message.answer(f"✅ Majburiy kanal muvaffaqiyatli o'zgartirildi: {REQUIRED_CHANNEL}", reply_markup=admin_menu())
    await state.finish()

# 3, 4, 5, 6, 7. Qolgan menyu tugmalari
@dp.message_handler(lambda message: message.text == "🔄 Mavjud animeni almashtirish", user_id=ADMIN_ID)
async def change_anime(message: types.Message):
    await message.answer("Almashtirmoqchi bo'lgan animening kodi yoki nomini kiriting:", reply_markup=admin_menu())

@dp.message_handler(lambda message: message.text == "📅 Jadvalni yangilash", user_id=ADMIN_ID)
async def update_schedule(message: types.Message):
    await message.answer("Jadvalni yangilash uchun yangi ma'lumotlarni yuboring:", reply_markup=admin_menu())

@dp.message_handler(lambda message: message.text == "📁 Animelar ro'yxati", user_id=ADMIN_ID)
async def list_anime(message: types.Message):
    count = len(anime_database)
    await message.answer(f"📁 Bazadagi animelar soni: {count} ta.", reply_markup=admin_menu())

@dp.message_handler(lambda message: message.text == "📊 Statistika", user_id=ADMIN_ID)
async def bot_statistics(message: types.Message):
    await message.answer(f"📊 Bot statistikasi:\nSaqlangan animelar: {len(anime_database)} ta", reply_markup=admin_menu())

@dp.message_handler(lambda message: message.text == "🚀 Start (Asosiy menyu)", user_id=ADMIN_ID)
async def back_to_main(message: types.Message):
    await message.answer("Asosiy menyu:", reply_markup=admin_menu())

# Oddiy foydalanuvchi anime kodini yuborganda qism va nomi bilan yuborish
@dp.message_handler()
async def send_anime_to_user(message: types.Message):
    code = message.text.strip()
    if code in anime_database:
        anime = anime_database[code]
        caption = (
            f"🎬 **Nomi:** {anime['name']}\n"
            f"📌 **Qismi:** {anime['part']}\n"
            f"🕶 **Yashirin nomi:** {anime['hidden_name']}\n"
            f"🔢 **Kodi:** {anime['code']}"
        )
        await message.answer_video(video=anime['file_id'], caption=caption, parse_mode="Markdown")
    else:
        await message.answer("❌ Bunday kodli anime topilmadi. Iltimos, to'g'ri kod kiriting:")

if __name__ == '__main__':
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True)
