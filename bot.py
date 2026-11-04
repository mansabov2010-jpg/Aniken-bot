import logging
import random
import aiosqlite
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# Bot tokeningizni kiriting
TOKEN = "8638595606:AAHdvOE6usBtdekTtqbtGjEEYqhFljqK6gM"
ADMIN_ID = 7986354170  # O'z Telegram ID raqamingizni yozing

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

DB_NAME = "grab_garden_exact.db"

# Admin waifu qo'shishi uchun holatlar (FSM)
class AddWaifuState(StatesGroup):
    waiting_for_name = State()
    waiting_for_rarity = State()
    waiting_for_image = State()

# Bazani yaratish
async def db_start():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance INTEGER DEFAULT 100
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS waifus (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                rarity TEXT,
                image_url TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_waifus (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                waifu_name TEXT,
                rarity TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS group_messages (
                chat_id INTEGER PRIMARY KEY,
                msg_count INTEGER DEFAULT 0
            )
        """)
        await db.commit()
        
        # Agar bazada waifular bo'lmasa, boshlang'ich namunalar qo'shamiz
        async with db.execute("SELECT COUNT(*) FROM waifus") as cursor:
            count = (await cursor.fetchone())[0]
            if count == 0:
                await db.executemany(
                    "INSERT INTO waifus (name, rarity, image_url) VALUES (?, ?, ?)",
                    [
                        ("Miku Nakano", "🌟 Afsonaviy", "https://i.imgur.com/4M129Uz.jpeg"),
                        ("Zero Two", "💎 Nodir", "https://i.imgur.com/1Z178Z5.jpeg"),
                        ("Rem", "⭐ Oddiy", "https://i.imgur.com/38178Z5.jpeg")
                    ]
                )
                await db.commit()

# ==========================================
# 1. SHAXSIY CHAT VA OBUNACHILAR UCHUN PANEL
# ==========================================
@dp.message_handler(commands=['start'], chat_type=[types.ChatType.PRIVATE])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user = await cursor.fetchone()
        if not user:
            await db.execute("INSERT INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
            await db.commit()
            
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("🎒 Mening kolleksiyam (@WAIFUXGRAB_DAT)", callback_data="my_collection"),
        InlineKeyboardButton("📢 Yangiliklar kanali", url="https://t.me/GRAB_GARDEN_NEWS"),
        InlineKeyboardButton("👥 Asosiy guruh", url="https://t.me/Grab_Garden")
    )
    
    text = (
        f"🌸 Salom, **{message.from_user.first_name}**!\n\n"
        "Botanika xush kelibsiz! **Grab Garden** — anime qahramonlarini yig'ish, guruhlarda ov qilish va o'z bazangizni boyitish uchun eng yaxshi maskan[span_1](start_span)[span_1](end_span).\n\n"
        "📌 Guruhimizga qo'shiling va 100 ta xabardan so'ng chiqadigan waifularni birinchilardan bo'lib tutib oling!"
    )
    await message.answer(text, reply_markup=markup, parse_mode="Markdown")

@dp.callback_query_handler(text="my_collection", chat_type=[types.ChatType.PRIVATE])
async def process_collection(call: types.CallbackQuery):
    user_id = call.from_user.id
    
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT waifu_name, rarity FROM user_waifus WHERE user_id = ?", (user_id,)) as cursor:
            rows = await cursor.fetchall()
            
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("« Ortga", callback_data="back_home"))
    
    if not rows:
        await call.message.edit_text(
            "🎒 Kolleksiyangiz (@WAIFUXGRAB_DAT) hozircha bo'sh[span_2](start_span)[span_2](end_span).\nGuruhlarda bot tashlaydigan waifularni tutib oling!", 
            reply_markup=markup
        )
        await call.answer()
        return
        
    collection_text = "🎒 **Sizning Waifular Kolleksiyangiz (@WAIFUXGRAB_DAT):**[span_3](start_span)[span_3](end_span)\n\n"
    for idx, (name, rarity) in enumerate(rows, 1):
        collection_text += f"{idx}. {name} — {rarity}\n"
        
    await call.message.edit_text(collection_text, reply_markup=markup, parse_mode="Markdown")
    await call.answer()

@dp.callback_query_handler(text="back_home", chat_type=[types.ChatType.PRIVATE])
async def process_home(call: types.CallbackQuery):
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("🎒 Mening kolleksiyam", callback_data="my_collection"),
        InlineKeyboardButton("📢 Yangiliklar kanali", url="https://t.me/GRAB_GARDEN_NEWS"),
        InlineKeyboardButton("👥 Asosiy guruh", url="https://t.me/Grab_Garden")
    )
    await call.message.edit_text("🌸 **Grab Garden Bot Menyusi:**", reply_markup=markup, parse_mode="Markdown")
    await call.answer()


# ==========================================
# 2. GURUHLARDA 100 TA XABAR QOIDASI VA SPAWN
# ==========================================
@dp.message_handler(chat_type=[types.ChatType.SUPERGROUP, types.ChatType.GROUP])
async def group_message_handler(message: types.Message):
    chat_id = message.chat.id
    
    async with aiosqlite.connect(DB_NAME) as db:
        # Guruhdagi xabarlar sonini tekshirish va oshirish
        async with db.execute("SELECT msg_count FROM group_messages WHERE chat_id = ?", (chat_id,)) as cursor:
            res = await cursor.fetchone()
            
        if not res:
            await db.execute("INSERT INTO group_messages (chat_id, msg_count) VALUES (?, 1)", (chat_id,))
            current_count = 1
        else:
            current_count = res[0] + 1
            await db.execute("UPDATE group_messages SET msg_count = ? WHERE chat_id = ?", (current_count, chat_id))
        await db.commit()
        
        # HAR 100 TA XABARDA BIR WAIFU CHIQISHI
        if current_count >= 100:
            # Xabarlar sonini noldan boshlaymiz
            await db.execute("UPDATE group_messages SET msg_count = 0 WHERE chat_id = ?", (chat_id,))
            await db.commit()
            
            # Bazadan tasodifiy waifu tanlaymiz
            async with db.execute("SELECT name, rarity, image_url FROM waifus") as cursor:
                waifus = await cursor.fetchall()
                
            if waifus:
                w_name, w_rarity, w_image = random.choice(waifus)
                
                markup = InlineKeyboardMarkup().add(
                    InlineKeyboardButton("🎣 Tutib olish", callback_data=f"grab_{w_name}")
                )
                
                text = (
                    f"✨ **Grab Garden | Diqqat! Yangi Waifu paydo bo'ldi!**[span_4](start_span)[span_4](end_span)\n\n"
                    f"👤 **Ismi:** {w_name}\n"
                    f"🌟 **Darajasi:** {w_rarity}\n\n"
                    f"👇 Uni birinchilardan bo'lib o'z kolleksiyangizga qo'shish uchun tugmani bosing!"
                )
                
                await message.answer_photo(photo=w_image, caption=text, reply_markup=markup, parse_mode="Markdown")

# Waifuni tutib qolish tugmasi
@dp.callback_query_handler(text_startswith="grab_")
async def process_grab(call: types.CallbackQuery):
    user_id = call.from_user.id
    waifu_name = call.data.split("_", 1)[1]
    
    rarity = "⭐ Oddiy"
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT rarity FROM waifus WHERE name = ?", (waifu_name,)) as cursor:
            res = await cursor.fetchone()
            if res:
                rarity = res[0]
                
        # Foydalanuvchini bazaga kiritish
        async with db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user = await cursor.fetchone()
        if not user:
            await db.execute("INSERT INTO users (user_id, username) VALUES (?, ?)", (user_id, call.from_user.username))
            
        # Kolleksiyaga qo'shish
        await db.execute(
            "INSERT INTO user_waifus (user_id, waifu_name, rarity) VALUES (?, ?, ?)",
            (user_id, waifu_name, rarity)
        )
        await db.commit()
        
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except:
        pass
        
    await call.answer(f"🎉 Tabriklaymiz! Siz {waifu_name} ni tutib oldingiz!", show_alert=True)
    await call.message.reply(
        f"🏆 **{call.from_user.first_name}** bu safargi **{waifu_name}** ({rarity}) qahramonini muvaffaqiyatli tutib oldi va `@WAIFUXGRAB_DAT` bazasiga yozdirdi! 🌸",
        parse_mode="Markdown"
    )


# ==========================================
# 3. ADMIN PANEL (WAIFU QO'SHISH VA BOSHQARUV)
# ==========================================
@dp.message_handler(commands=['admin'])
async def cmd_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
        
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            users_count = (await cursor.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM waifus") as cursor:
            waifus_count = (await cursor.fetchone())[0]
            
    text = (
        f"👑 **Grab Garden — Admin Boshqaruv Paneli:**\n\n"
        f"👥 Jami foydalanuvchilar: {users_count} ta\n"
        f"✨ Bazadagi waifular soni: {waifus_count} ta"
    )
    
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("➕ Yangi Waifu qo'shish", callback_data="admin_add_waifu")
    )
    await message.answer(text, reply_markup=markup, parse_mode="Markdown")

@dp.callback_query_handler(text="admin_add_waifu")
async def admin_add_waifu_start(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    await AddWaifuState.waiting_for_name.set()
    await call.message.answer("📝 Yangi waifuning **ismini** kiriting:")
    await call.answer()

@dp.message_handler(state=AddWaifuState.waiting_for_name)
async def process_waifu_name(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.update_data(name=message.text)
    await AddWaifuState.next()
    await message.answer("✨ Waifuning **darajasini** kiriting (masalan: *🌟 Afsonaviy* yoki *💎 Nodir*):")

@dp.message_handler(state=AddWaifuState.waiting_for_rarity)
async def process_waifu_rarity(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.update_data(rarity=message.text)
    await AddWaifuState.next()
    await message.answer("🖼 Waifuning **rasm havolasini (URL)** yuboring (masalan: *https://i.imgur.com/...*):")

@dp.message_handler(state=AddWaifuState.waiting_for_image)
async def process_waifu_image(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    image_url = message.text
    data = await state.get_data()
    name = data['name']
    rarity = data['rarity']
    
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO waifus (name, rarity, image_url) VALUES (?, ?, ?)",
            (name, rarity, image_url)
        )
        await db.commit()
        
    await state.finish()
    await message.answer(f"✅ Muvaffaqiyatli qo'shildi!\n\n👤 Ismi: {name}\n✨ Darajasi: {rarity}\n🖼 Rasm: {image_url}")

if __name__ == '__main__':
    executor.start_polling(dp, on_startup=lambda x: db_start())
            
