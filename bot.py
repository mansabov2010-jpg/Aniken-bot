import asyncio
import logging
import random
import aiosqlite
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web

# Bot tokeni va Adminlar ro'yxati
TOKEN = "8987164421:AAFBaDaWN2R1pobYVpEeULF4PfV7yHp-6Q"
ADMIN_IDS = [7986354170, 7637155944]
BOT_USERNAME = "AniREM_bot"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

DB_NAME = "grab_garden_exact.db"

class AddWaifuState(StatesGroup):
    waiting_for_name = State()
    waiting_for_rarity = State()
    waiting_for_image = State()

class BroadcastState(StatesGroup):
    waiting_for_message = State()

class SettingsState(StatesGroup):
    waiting_for_channel = State()
    waiting_for_group = State()

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
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await db.commit()
        
        # Standart havolalarni o'rnatish
        async with db.execute("SELECT value FROM bot_settings WHERE key = 'channel_url'") as cursor:
            if not await cursor.fetchone():
                await db.execute("INSERT INTO bot_settings (key, value) VALUES ('channel_url', 'https://t.me/channel_soon')")
        async with db.execute("SELECT value FROM bot_settings WHERE key = 'group_url'") as cursor:
            if not await cursor.fetchone():
                await db.execute("INSERT INTO bot_settings (key, value) VALUES ('group_url', 'https://t.me/group_soon')")
        await db.commit()
        
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

async def get_setting(key):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT value FROM bot_settings WHERE key = ?", (key,)) as cursor:
            res = await cursor.fetchone()
            return res[0] if res else ""

# ==========================================
# 1. /start VA ASOSIY MENYU (ANIMEKU)
# ==========================================
@dp.message(Command("start"), F.chat.type == "private")
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user = await cursor.fetchone()
        if not user:
            await db.execute("INSERT INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
            await db.commit()
            
    channel_url = await get_setting("channel_url")
    group_url = await get_setting("group_url")
            
    markup_rows = [
        [InlineKeyboardButton(text="➕ Botni guruhga qo'shish", url=f"https://t.me/{BOT_USERNAME}?startgroup=true")],
        [InlineKeyboardButton(text="🎒 Mening kolleksiyam", callback_data="my_collection")],
        [InlineKeyboardButton(text="📢 Yangiliklar kanali", url=channel_url)],
        [InlineKeyboardButton(text="👥 Asosiy guruh", url=group_url)]
    ]
    
    if user_id in ADMIN_IDS:
        markup_rows.insert(0, [InlineKeyboardButton(text="👑 Admin Panel", callback_data="admin_panel_main")])

    markup = InlineKeyboardMarkup(inline_keyboard=markup_rows)
    
    text = (
        f"🌸 Salom, **{message.from_user.first_name}**!\n\n"
        "✨ **Animeku** olamiga xush kelibsiz! Bu yerda anime qahramonlarini yig'ishingiz, guruhlarda ov qilishingiz va o'z bazangizni boyitishingiz mumkin.\n\n"
        "📌 Botni guruhga qo'shing va 100 ta xabardan so'ng chiqadigan qahramonlarni tutib oling!"
    )
    await message.answer(text, reply_markup=markup, parse_mode="Markdown")

@dp.callback_query(F.data == "my_collection")
async def process_collection(call: types.CallbackQuery):
    user_id = call.from_user.id
    
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT waifu_name, rarity FROM user_waifus WHERE user_id = ?", (user_id,)) as cursor:
            rows = await cursor.fetchall()
            
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="« Ortga", callback_data="back_home")]
    ])
    
    if not rows:
        await call.message.edit_text(
            "🎒 Kolleksiyangiz hozircha bo'sh.\nGuruhlarda bot tashlaydigan qahramonlarni tutib oling!", 
            reply_markup=markup
        )
        await call.answer()
        return
        
    collection_text = "🎒 **Sizning Animeku Kolleksiyangiz:**\n\n"
    for idx, (name, rarity) in enumerate(rows, 1):
        collection_text += f"{idx}. {name} — {rarity}\n"
        
    await call.message.edit_text(collection_text, reply_markup=markup, parse_mode="Markdown")
    await call.answer()

@dp.callback_query(F.data == "back_home")
async def process_home(call: types.CallbackQuery):
    user_id = call.from_user.id
    channel_url = await get_setting("channel_url")
    group_url = await get_setting("group_url")
    
    markup_rows = [
        [InlineKeyboardButton(text="➕ Botni guruhga qo'shish", url=f"https://t.me/{BOT_USERNAME}?startgroup=true")],
        [InlineKeyboardButton(text="🎒 Mening kolleksiyam", callback_data="my_collection")],
        [InlineKeyboardButton(text="📢 Yangiliklar kanali", url=channel_url)],
        [InlineKeyboardButton(text="👥 Asosiy guruh", url=group_url)]
    ]
    if user_id in ADMIN_IDS:
        markup_rows.insert(0, [InlineKeyboardButton(text="👑 Admin Panel", callback_data="admin_panel_main")])
        
    markup = InlineKeyboardMarkup(inline_keyboard=markup_rows)
    await call.message.edit_text("🌸 **Animeku Bosh Menyu:**", reply_markup=markup, parse_mode="Markdown")
    await call.answer()


# ==========================================
# 2. GURUHLARDA 100 XABAR VA QAHRAMON CHIQISHI
# ==========================================
@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def group_message_handler(message: types.Message):
    chat_id = message.chat.id
    
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT msg_count FROM group_messages WHERE chat_id = ?", (chat_id,)) as cursor:
            res = await cursor.fetchone()
            
        if not res:
            await db.execute("INSERT INTO group_messages (chat_id, msg_count) VALUES (?, 1)", (chat_id,))
            current_count = 1
        else:
            current_count = res[0] + 1
            await db.execute("UPDATE group_messages SET msg_count = ? WHERE chat_id = ?", (current_count, chat_id))
        await db.commit()
        
        if current_count >= 100:
            await db.execute("UPDATE group_messages SET msg_count = 0 WHERE chat_id = ?", (chat_id,))
            await db.commit()
            
            async with db.execute("SELECT name, rarity, image_url FROM waifus") as cursor:
                waifus = await cursor.fetchall()
                
            if waifus:
                w_name, w_rarity, w_image = random.choice(waifus)
                
                markup = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🎣 Tutib olish", callback_data=f"grab_{w_name}")]
                ])
                
                text = (
                    f"⚡ **Animeku | Diqqat! Yangi qahramon paydo bo'ldi!**\n\n"
                    f"👤 **Ismi:** {w_name}\n"
                    f"🌟 **Darajasi:** {w_rarity}\n\n"
                    f"👇 Uni birinchilardan bo'lib o'z kolleksiyangizga qo'shish uchun bosing!"
                )
                
                await message.answer_photo(photo=w_image, caption=text, reply_markup=markup, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("grab_"))
async def process_grab(call: types.CallbackQuery):
    user_id = call.from_user.id
    waifu_name = call.data.split("_", 1)[1]
    
    rarity = "⭐ Oddiy"
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT rarity FROM waifus WHERE name = ?", (waifu_name,)) as cursor:
            res = await cursor.fetchone()
            if res:
                rarity = res[0]
                
        async with db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user = await cursor.fetchone()
        if not user:
            await db.execute("INSERT INTO users (user_id, username) VALUES (?, ?)", (user_id, call.from_user.username))
            
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
        f"🏆 **{call.from_user.first_name}** bu safargi **{waifu_name}** ({rarity}) qahramonini muvaffaqiyatli tutib oldi! 🌸",
        parse_mode="Markdown"
    )


# ==========================================
# 3. KENGAYTIRILGAN ADMIN PANEL & HAVOLALAR
# ==========================================
@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
        
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            users_count = (await cursor.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM waifus") as cursor:
            waifus_count = (await cursor.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM group_messages") as cursor:
            groups_count = (await cursor.fetchone())[0]
            
    text = (
        f"👑 **Animeku Admin Boshqaruv Paneli:**\n\n"
        f"👥 Jami foydalanuvchilar: **{users_count}** ta\n"
        f"✨ Bazadagi qahramonlar: **{waifus_count}** ta\n"
        f"💬 Faol guruhlar soni: **{groups_count}** ta\n\n"
        f"Kerakli bo'limni tanlang:"
    )
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Qahramon qo'shish", callback_data="admin_add_waifu")],
        [InlineKeyboardButton(text="📋 Qahramonlar ro'yxati", callback_data="admin_list_waifus")],
        [InlineKeyboardButton(text="📢 Reklama tarqatish (Rassilka)", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🔗 Kanal/Guruh havolasini o'zgartirish", callback_data="admin_links")],
        [InlineKeyboardButton(text="« Asosiy menyu", callback_data="back_home")]
    ])
    await message.answer(text, reply_markup=markup, parse_mode="Markdown")

@dp.callback_query(F.data == "admin_panel_main")
async def admin_panel_callback(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("Sizda bu huquq yo'q!", show_alert=True)
        return
        
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            users_count = (await cursor.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM waifus") as cursor:
            waifus_count = (await cursor.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM group_messages") as cursor:
            groups_count = (await cursor.fetchone())[0]
            
    text = (
        f"👑 **Animeku Admin Boshqaruv Paneli:**\n\n"
        f"👥 Jami foydalanuvchilar: **{users_count}** ta\n"
        f"✨ Bazadagi qahramonlar: **{waifus_count}** ta\n"
        f"💬 Faol guruhlar soni: **{groups_count}** ta\n\n"
        f"Kerakli bo'limni tanlang:"
    )
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Qahramon qo'shish", callback_data="admin_add_waifu")],
        [InlineKeyboardButton(text="📋 Qahramonlar ro'yxati", callback_data="admin_list_waifus")],
        [InlineKeyboardButton(text="📢 Reklama tarqatish (Rassilka)", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🔗 Kanal/Guruh havolasini o'zgartirish", callback_data="admin_links")],
        [InlineKeyboardButton(text="« Asosiy menyu", callback_data="back_home")]
    ])
    await call.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
    await call.answer()

# Kanal va guruh havolalarini boshqarish menyusi
@dp.callback_query(F.data == "admin_links")
async def admin_links_menu(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    channel_url = await get_setting("channel_url")
    group_url = await get_setting("group_url")
    
    text = (
        f"🔗 **Kanal va Guruh havolalarini boshqarish:**\n\n"
        f"📢 Hozirgi kanal: `{channel_url}`\n"
        f"👥 Hozirgi guruh: `{group_url}`\n\n"
        f"O'zgartirish uchun tugmani bosing:"
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Kanal havolasini o'zgartirish", callback_data="set_channel")],
        [InlineKeyboardButton(text="👥 Guruh havolasini o'zgartirish", callback_data="set_group")],
        [InlineKeyboardButton(text="« Admin Panelga qaytish", callback_data="admin_panel_main")]
    ])
    await call.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
    await call.answer()

@dp.callback_query(F.data == "set_channel")
async def set_channel_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return
    await state.set_state(SettingsState.waiting_for_channel)
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_links")]])
    await call.message.edit_text("📢 Yangi **kanal havolasini** yuboring (masalan: *https://t.me/kanal_nomi*):", reply_markup=markup)
    await call.answer()

@dp.message(SettingsState.waiting_for_channel)
async def save_channel(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    new_url = message.text.strip()
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE bot_settings SET value = ? WHERE key = 'channel_url'", (new_url,))
        await db.commit()
    await state.clear()
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="« Havolalar bo'limiga qaytish", callback_data="admin_links")]])
    await message.answer(f"✅ Kanal havolasi muvaffaqiyatli yangilandi:\n`{new_url}`", reply_markup=markup, parse_mode="Markdown")

@dp.callback_query(F.data == "set_group")
async def set_group_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return
    await state.set_state(SettingsState.waiting_for_group)
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_links")]])
    await call.message.edit_text("👥 Yangi **guruh havolasini** yuboring (masalan: *https://t.me/guruh_nomi*):", reply_markup=markup)
    await call.answer()

@dp.message(SettingsState.waiting_for_group)
async def save_group(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    new_url = message.text.strip()
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE bot_settings SET value = ? WHERE key = 'group_url'", (new_url,))
        await db.commit()
    await state.clear()
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="« Havolalar bo'limiga qaytish", callback_data="admin_links")]])
    await message.answer(f"✅ Guruh havolasi muvaffaqiyatli yangilandi:\n`{new_url}`", reply_markup=markup, parse_mode="Markdown")

@dp.callback_query(F.data == "admin_add_waifu")
async def admin_add_waifu_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return
    await state.set_state(AddWaifuState.waiting_for_name)
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_panel_main")]])
    await call.message.edit_text("📝 Yangi qahramonning **ismini** kiriting:", reply_markup=markup)
    await call.answer()

@dp.message(AddWaifuState.waiting_for_name)
async def process_waifu_name(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    await state.update_data(name=message.text)
    await state.set_state(AddWaifuState.waiting_for_rarity)
    await message.answer("✨ Qahramonning **darajasini** kiriting (masalan: *🌟 2 Yulduzcha*):")

@dp.message(AddWaifuState.waiting_for_rarity)
async def process_waifu_rarity(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    await state.update_data(rarity=message.text)
    await state.set_state(AddWaifuState.waiting_for_image)
    await message.answer("🖼 Qahramonning **rasm havolasini (URL)** yuboring (masalan: *https://i.imgur.com/...*):")

@dp.message(AddWaifuState.waiting_for_image)
async def process_waifu_image(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
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
        
    await state.clear()
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="👑 Admin Panelga qaytish", callback_data="admin_panel_main")]])
    await message.answer(f"✅ Qahramon muvaffaqiyatli qo'shildi!\n\n👤 Ismi: {name}\n✨ Darajasi: {rarity}\n🖼 Rasm: {image_url}", reply_markup=markup)

@dp.callback_query(F.data == "admin_list_waifus")
async def admin_list_waifus(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
        
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT id, name, rarity FROM waifus") as cursor:
            waifus = await cursor.fetchall()
