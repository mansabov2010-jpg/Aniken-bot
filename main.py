import asyncio
import logging
import random
import os
import aiosqlite
import warnings
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, MenuButtonWebApp
from aiohttp import web
warnings.filterwarnings("ignore", category=ResourceWarning)

TOKEN = "9111857366:AAFwGLEkXzTvaFzLB01aHtDeM4JzoEsDO_4"
ADMIN_IDS = [7986354170, 7637155944]
BOT_USERNAME = "AniREM_bot"
WEBAPP_URL = "https://aniken-bot-1.onrender.com"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

DB_NAME = "grabcharakter_ultimate_full.db"
MESSAGES_FOR_SPAWN = 100

RARITY_CHANCES = {
    "🌟 Afsonaviy": 5,
    "💎 Nodir": 25,
    "⭐ Oddiy": 70
}

async def db_start():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance_gc INTEGER DEFAULT 0,
                diamonds INTEGER DEFAULT 0,
                daily_claimed TEXT,
                last_tap_time TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS waifus (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                anime_name TEXT,
                description TEXT,
                rarity TEXT,
                promo_limit INTEGER DEFAULT 10,
                gc_price INTEGER DEFAULT 0,
                diamond_price INTEGER DEFAULT 0,
                l1_img TEXT, l1_proj TEXT,
                l2_img TEXT, l2_proj TEXT,
                l3_img TEXT, l3_proj TEXT,
                l4_img TEXT, l4_proj TEXT,
                l5_img TEXT, l5_proj TEXT,
                l6_img TEXT, l6_proj TEXT,
                team_view TEXT,
                image_url TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_waifus (
                user_id INTEGER,
                waifu_id INTEGER,
                count INTEGER DEFAULT 1,
                level INTEGER DEFAULT 1,
                PRIMARY KEY (user_id, waifu_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS group_messages (
                chat_id INTEGER PRIMARY KEY,
                msg_count INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS connected_chats (
                chat_id INTEGER PRIMARY KEY,
                chat_type TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS promo_codes (
                code TEXT PRIMARY KEY,
                waifu_id INTEGER,
                uses_left INTEGER
            )
        """)
        await db.commit()
        
        defaults = [
            ('channel_url', 'https://t.me/channel_soon'),
            ('group_url', 'https://t.me/group_soon'),
            ('card_number', '8600 0000 0000 0000'),
            ('card_holder', 'Firdavs T.'),
            ('exchange_rate_gc_to_diamond', '100'),
            ('border_radius', '15'),
            ('glass_opacity', '85'),
            ('bg_image', '')
        ]
        for key, val in defaults:
            async with db.execute("SELECT value FROM bot_settings WHERE key = ?", (key,)) as cursor:
                if not await cursor.fetchone():
                    await db.execute("INSERT INTO bot_settings (key, value) VALUES (?, ?)", (key, val))
        await db.commit()

async def get_setting(key):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT value FROM bot_settings WHERE key = ?", (key,)) as cursor:
            res = await cursor.fetchone()
            return res[0] if res else ""

@dp.message(F.chat.type.in_({"group", "supergroup", "channel"}))
async def track_chats(message: types.Message):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR IGNORE INTO connected_chats (chat_id, chat_type) VALUES (?, ?)",
            (message.chat.id, message.chat.type)
        )
        await db.commit()
    
    if message.chat.type in {"group", "supergroup"}:
        if message.text and message.text.startswith("/bitim"):
            await message.answer("🔄 **Guruhdagi Bitim (Trade):** Mini Ilovadan foydalaning!", parse_mode="Markdown")
            return

        chat_id = message.chat.id
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT msg_count FROM group_messages WHERE chat_id = ?", (chat_id,)) as cursor:
                res = await cursor.fetchone()
                current_count = res[0] + 1 if res else 1
                await db.execute("INSERT OR REPLACE INTO group_messages (chat_id, msg_count) VALUES (?, ?)", (chat_id, current_count))
                await db.commit()
            
            if current_count >= MESSAGES_FOR_SPAWN:
                await db.execute("UPDATE group_messages SET msg_count = 0 WHERE chat_id = ?", (chat_id,))
                await db.commit()
                
                async with db.execute("SELECT id, name, rarity, l1_img FROM waifus") as cursor:
                    waifus = await cursor.fetchall()
                    
                if waifus:
                    rand_val = random.randint(1, 100)
                    if rand_val <= RARITY_CHANCES["🌟 Afsonaviy"]:
                        target_rarity = "🌟 Afsonaviy"
                    elif rand_val <= (RARITY_CHANCES["🌟 Afsonaviy"] + RARITY_CHANCES["💎 Nodir"]):
                        target_rarity = "💎 Nodir"
                    else:
                        target_rarity = "⭐ Oddiy"
                    
                    filtered = [w for w in waifus if w[2] == target_rarity]
                    selected = random.choice(filtered) if filtered else random.choice(waifus)
                    w_id, w_name, w_rarity, w_image = selected
                    
                    markup = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🎣 Tutib olish", callback_data=f"grab_{w_id}")],
                        [InlineKeyboardButton(text="🎒 Kolleksiyani ko'rish", callback_data="my_collection")]
                    ])
                    
                    text = (
                        f"⚡ **Diqqat! Guruhda yangi qahramon paydo bo'ldi!**\n\n"
                        f"👤 **Ismi:** {w_name}\n"
                        f"🌟 **Darajasi:** {w_rarity}\n"
                        f"👇 Uni birinchilardan bo'lib tutib qoling!"
                    )
                    await message.answer_photo(photo=w_image if w_image else "https://via.placeholder.com/300", caption=text, reply_markup=markup, parse_mode="Markdown")

@dp.message(Command("start"), F.chat.type == "private")
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
        await db.commit()
            
    channel_url = await get_setting("channel_url")
    group_url = await get_setting("group_url")
            
    markup_rows = [
        [InlineKeyboardButton(text="➕ Botni guruhga qo'shish", url=f"https://t.me/{BOT_USERNAME}?startgroup=true")],
        [InlineKeyboardButton(text="🎒 Mening kolleksiyam", callback_data="my_collection")],
        [InlineKeyboardButton(text="🔄 Bitimlar bo'limi", callback_data="trade_info")],
        [InlineKeyboardButton(text="📢 Yangiliklar kanali", url=channel_url)],
        [InlineKeyboardButton(text="👥 Asosiy guruh", url=group_url)]
    ]
    
    if user_id in ADMIN_IDS:
        markup_rows.insert(0, [InlineKeyboardButton(text="👑 Admin Panel", callback_data="admin_panel_main")])

    markup = InlineKeyboardMarkup(inline_keyboard=markup_rows)
    text = (
        f"🌸 Salom, **{message.from_user.first_name}**!\n\n"
        "✨ **GrabCharakter** olamiga xush kelibsiz!\n"
        "Pastdagi chap tarafda joylashgan **'GrabCharakter'** maxsus tugmasi orqali Mini Ilovaga kiring, "
        "yoki guruhlarda qahramonlar ovlang."
    )
    await message.answer(text, reply_markup=markup, parse_mode="Markdown")

@dp.callback_query(F.data == "my_collection")
async def process_collection(call: types.CallbackQuery):
    user_id = call.from_user.id
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("""
            SELECT w.name, w.rarity, uw.count, uw.level, w.id 
            FROM user_waifus uw 
            JOIN waifus w ON uw.waifu_id = w.id 
            WHERE uw.user_id = ?
        """, (user_id,)) as cursor:
            rows = await cursor.fetchall()
            
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="« Bosh menyu", callback_data="back_home")]
    ])
    if not rows:
        await call.message.edit_text("🎒 Kolleksiyangiz hozircha bo'sh. Guruhlarda qahramonlar ovlang!", reply_markup=markup)
        await call.answer()
        return
        
    collection_text = "🎒 **Sizning Qahramonlar Kolleksiyangiz:**\n\n"
    for idx, (name, rarity, count, level, w_id) in enumerate(rows, 1):
        stars = "⭐" * level
        collection_text += f"{idx}. [ID: {w_id}] {name} ({rarity}) | Daraja: {stars} — **x{count}**\n"
        
    await call.message.edit_text(collection_text, reply_markup=markup, parse_mode="Markdown")
    await call.answer()

@dp.callback_query(F.data == "trade_info")
async def trade_info_callback(call: types.CallbackQuery):
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="« Bosh menyu", callback_data="back_home")]
    ])
    await call.message.edit_text(
        "🔄 **Bitim (Trade) Tizimi:**\n\nGuruhlarda o'zaro qahramonlarni ayirboshlash uchun guruh ichida `/bitim` buyrug'ini yuboring.",
        reply_markup=markup, parse_mode="Markdown"
    )
    await call.answer()

@dp.callback_query(F.data == "back_home")
async def process_home(call: types.CallbackQuery):
    user_id = call.from_user.id
    channel_url = await get_setting("channel_url")
    group_url = await get_setting("group_url")
    markup_rows = [
        [InlineKeyboardButton(text="➕ Botni guruhga qo'shish", url=f"https://t.me/{BOT_USERNAME}?startgroup=true")],
        [InlineKeyboardButton(text="🎒 Mening kolleksiyam", callback_data="my_collection")],
        [InlineKeyboardButton(text="🔄 Bitimlar bo'limi", callback_data="trade_info")],
        [InlineKeyboardButton(text="📢 Yangiliklar kanali", url=channel_url)],
        [InlineKeyboardButton(text="👥 Asosiy guruh", url=group_url)]
    ]
    if user_id in ADMIN_IDS:
        markup_rows.insert(0, [InlineKeyboardButton(text="👑 Admin Panel", callback_data="admin_panel_main")])
    markup = InlineKeyboardMarkup(inline_keyboard=markup_rows)
    await call.message.edit_text("🌸 **Bosh Menyu:**", reply_markup=markup, parse_mode="Markdown")
    await call.answer()

@dp.callback_query(F.data.startswith("grab_"))
async def process_grab(call: types.CallbackQuery):
    user_id = call.from_user.id
    w_id = int(call.data.split("_")[1])
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT name, rarity FROM waifus WHERE id = ?", (w_id,)) as cursor:
            w_info = await cursor.fetchone()
            if not w_info:
                await call.answer("Xatolik yuz berdi!", show_alert=True)
                return
            w_name, w_rarity = w_info
            
        async with db.execute("SELECT count, level FROM user_waifus WHERE user_id = ? AND waifu_id = ?", (user_id, w_id)) as cursor:
            row = await cursor.fetchone()
            if row:
                count, level = row
                new_count = count + 1
                if new_count >= 2 and level < 6:
                    new_count -= 2
                    level += 1
                    await db.execute("UPDATE user_waifus SET count = ?, level = ? WHERE user_id = ? AND waifu_id = ?", (new_count, level, user_id, w_id))
                    msg_suffix = f"(Takroriy! Birlashtirilib **{level}-darajaga** ko'tarildi!)"
                else:
                    await db.execute("UPDATE user_waifus SET count = ? WHERE user_id = ? AND waifu_id = ?", (new_count, level, user_id, w_id))
                    msg_suffix = f"(Takroriy! Jami: **x{new_count}**)"
            else:
                await db.execute("INSERT INTO user_waifus (user_id, waifu_id, count, level) VALUES (?, ?, 1, 1)", (user_id, w_id))
                msg_suffix = "(Yangi qahramon qo'shildi!)"
        await db.commit()
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except:
        pass
    await call.answer(f"🎉 Tabriklaymiz! Siz {w_name} ni qo'lga kiritdingiz!", show_alert=True)
    await call.message.reply(f"🏆 **{call.from_user.first_name}** — {w_name} ({w_rarity}) qahramonini tutdi! {msg_suffix}", parse_mode="Markdown")


class AddWaifuState(StatesGroup):
    name = State()
    anime_name = State()
    description = State()
    rarity = State()
    promo_limit = State()
    gc_price = State()
    diamond_price = State()
    l1_img = State()
    l1_proj = State()
    l2_img = State()
    l2_proj = State()
    l3_img = State()
    l3_proj = State()
    l4_img = State()
    l4_proj = State()
    l5_img = State()
    l5_proj = State()
    l6_img = State()
    l6_proj = State()
    team_view = State()

class BroadcastState(StatesGroup):
    waiting_for_message = State()

class SettingsState(StatesGroup):
    channel_url = State()
    group_url = State()
    card_number = State()
    card_holder = State()

class PromoState(StatesGroup):
    code = State()
    waifu_id = State()
    limit = State()

class DesignSettingsState(StatesGroup):
    border_radius = State()
    glass_opacity = State()
    bg_image = State()

@dp.callback_query(F.data == "admin_panel_main")
async def admin_panel_callback(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
        
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor: u_cnt = (await cursor.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM waifus") as cursor: w_cnt = (await cursor.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM connected_chats") as cursor: c_cnt = (await cursor.fetchone())[0]
            
    text = (
        f"👑 **Admin Boshqaruv Paneli:**\n\n"
        f"👥 Foydalanuvchilar: {u_cnt}\n"
        f"✨ Qahramonlar bazasi: {w_cnt}\n"
        f"📡 Ulangan Chatlar/Kanallar: {c_cnt}\n\n"
        "Kerakli bo'limni tanlang:"
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Qahramon qo'shish (6-Level & Multi-View)", callback_data="admin_add_waifu")],
        [InlineKeyboardButton(text="📋 Personajlarni boshqarish / O'chirish", callback_data="admin_manage_waifus")],
        [InlineKeyboardButton(text="🎟 Promokod yaratish", callback_data="admin_add_promo")],
        [InlineKeyboardButton(text="💳 Karta va To'lovlar", callback_data="admin_payment_settings")],
        [InlineKeyboardButton(text="🔗 Havolalarni sozlash", callback_data="admin_links")],
        [InlineKeyboardButton(text="🎨 Mini App Dizayni", callback_data="admin_design_menu")],
        [InlineKeyboardButton(text="📢 Barchaga xabar yuborish", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="« Bosh menyu", callback_data="back_home")]
    ])
    await call.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
    await call.answer()

@dp.callback_query(F.data == "admin_manage_waifus")
async def admin_manage_waifus(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS: return
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT id, name, rarity FROM waifus") as cursor:
            waifus = await cursor.fetchall()
            
    if not waifus:
        await call.message.edit_text(
            "📭 Bazada hozircha qahramonlar yo'q.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="« Orqaga", callback_data="admin_panel_main")]])
        )
        await call.answer()
        return
        
    buttons = []
    for w in waifus:
        buttons.append([InlineKeyboardButton(text=f"❌ O'chirish: {w[1]} (ID: {w[0]})", callback_data=f"admin_del_waifu_{w[0]}")])
    buttons.append([InlineKeyboardButton(text="« Orqaga", callback_data="admin_panel_main")])
    
    await call.message.edit_text("📋 **Qahramonlarni O'chirish / Boshqarish:**", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")
    await call.answer()

@dp.callback_query(F.data.startswith("admin_del_waifu_"))
async def admin_delete_waifu_exec(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS: return
    w_id = int(call.data.split("_")[3])
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT name FROM waifus WHERE id = ?", (w_id,)) as cursor:
            res = await cursor.fetchone()
            w_name = res[0] if res else "Noma'lum"
        await db.execute("DELETE FROM waifus WHERE id = ?", (w_id,))
        await db.execute("DELETE FROM user_waifus WHERE waifu_id = ?", (w_id,))
        await db.commit()
    await call.message.edit_text(
        f"✅ **{w_name}** (ID: {w_id}) muvaffaqiyatli o'chirib tashlandi!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="« Orqaga", callback_data="admin_manage_waifus")]])
    )
    await call.answer()

@dp.callback_query(F.data == "admin_add_waifu")
async def add_waifu_step1(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS: return
    await state.set_state(AddWaifuState.name)
    await call.message.edit_text("📝 Yangi qahramon nomini kiriting:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_panel_main")]]))
    await call.answer()

@dp.message(AddWaifuState.name)
async def add_waifu_step_anime(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddWaifuState.anime_name)
    await message.answer("🎬 Qahramon qaysi animedan ekanligini kiriting:")

@dp.message(AddWaifuState.anime_name)
async def add_waifu_step_desc(message: types.Message, state: FSMContext):
    await state.update_data(anime_name=message.text)
    await state.set_state(AddWaifuState.description)
    await message.answer("📄 Qahramon haqida qisqacha ma'lumot kiriting:")

@dp.message(AddWaifuState.description)
async def add_waifu_step_rarity(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(AddWaifuState.rarity)
    await message.answer("✨ Darajasini kiriting (masalan: 🌟 Afsonaviy, 💎 Nodir, ⭐ Oddiy):")

@dp.message(AddWaifuState.rarity)
async def add_waifu_step_limit(message: types.Message, state: FSMContext):
    await state.update_data(rarity=message.text)
    await state.set_state(AddWaifuState.promo_limit)
    await message.answer("🔢 Promokod limitini kiriting:")

@dp.message(AddWaifuState.promo_limit)
async def add_waifu_step_gc(message: types.Message, state: FSMContext):
    await state.update_data(promo_limit=int(message.text))
    await state.set_state(AddWaifuState.gc_price)
    await message.answer("🪙 Tanga (GC) narxini kiriting:")

@dp.message(AddWaifuState.gc_price)
async def add_waifu_step_diamond(message: types.Message, state: FSMContext):
    await state.update_data(gc_price=int(message.text))
    await state.set_state(AddWaifuState.diamond_price)
    await message.answer("💎 Olmos narxini kiriting (yo'q bo'lsa 0):")

@dp.message(AddWaifuState.diamond_price)
async def add_waifu_step_l1_img(message: types.Message, state: FSMContext):
    await state.update_data(diamond_price=int(message.text))
    await state.set_state(AddWaifuState.l1_img)
    await message.answer("⭐ **1-Daraja:** Profil rasmi havolasini yuboring:")

@dp.message(AddWaifuState.l1_img)
async def add_waifu_step_l1_proj(message: types.Message, state: FSMContext):
    await state.update_data(l1_img=message.text)
    await state.set_state(AddWaifuState.l1_proj)
    await message.answer("⭐ **1-Daraja:** Proyekti havolasini yuboring:")

@dp.message(AddWaifuState.l1_proj)
async def add_waifu_step_l2_img(message: types.Message, state: FSMContext):
    await state.update_data(l1_proj=message.text)
    await state.set_state(AddWaifuState.l2_img)
    await message.answer("⭐⭐ **2-Daraja:** Profil rasmi havolasini yuboring:")

@dp.message(AddWaifuState.l2_img)
async def add_waifu_step_l2_proj(message: types.Message, state: FSMContext):
    await state.update_data(l2_img=message.text)
    await state.set_state(AddWaifuState.l2_proj)
    await message.answer("⭐⭐ **2-Daraja:** Proyekti havolasini yuboring:")

@dp.message(AddWaifuState.l2_proj)
async def add_waifu_step_l3_img(message: types.Message, state: FSMContext):
    await state.update_data(l2_proj=message.text)
    await state.set_state(AddWaifuState.l3_img)
    await message.answer("⭐⭐⭐ **3-Daraja:** Profil rasmi havolasini yuboring:")

@dp.message(AddWaifuState.l3_img)
async def add_waifu_step_l3_proj(message: types.Message, state: FSMContext):
    await state.update_data(l3_img=message.text)
    await state.set_state(AddWaifuState.l3_proj)
    await message.answer("⭐⭐⭐ **3-Daraja:** Proyekti havolasini yuboring:")

@dp.message(AddWaifuState.l3_proj)
async def add_waifu_step_l4_img(message: types.Message, state: FSMContext):
    await state.update_data(l3_proj=message.text)
    await state.set_state(AddWaifuState.l4_img)
    await message.answer("⭐⭐⭐⭐ **4-Daraja:** Profil rasmi havolasini yuboring:")

@dp.message(AddWaifuState.l4_img)
async def add_waifu_step_l4_proj(message: types.Message, state: FSMContext):
    await state.update_data(l4_img=message.text)
    await state.set_state(AddWaifuState.l4_proj)
    await message.answer("⭐⭐⭐⭐ **4-Daraja:** Proyekti havolasini yuboring:")

@dp.message(AddWaifuState.l4_proj)
async def add_waifu_step_l5_img(message: types.Message, state: FSMContext):
    await state.update_data(l4_proj=message.text)
    await state.set_state(AddWaifuState.l5_img)
    await message.answer("⭐⭐⭐⭐⭐ **5-Daraja:** Profil rasmi havolasini yuboring:")

@dp.message(AddWaifuState.l5_img)
async def add_waifu_step_l5_proj(message: types.Message, state: FSMContext):
    await state.update_data(l5_img=message.text)
    await state.set_state(AddWaifuState.l5_proj)
    await message.answer("⭐⭐⭐⭐⭐ **5-Daraja:** Proyekti havolasini yuboring:")

@dp.message(AddWaifuState.l5_proj)
async def add_waifu_step_l6_img(message: types.Message, state: FSMContext):
    await state.update_data(l5_proj=message.text)
    await state.set_state(AddWaifuState.l6_img)
    await message.answer("⭐⭐⭐⭐⭐⭐ **6-Daraja:** Profil rasmi havolasini yuboring:")

@dp.message(AddWaifuState.l6_img)
async def add_waifu_step_l6_proj(message: types.Message, state: FSMContext):
    await state.update_data(l6_img=message.text)
    await state.set_state(AddWaifuState.l6_proj)
    await message.answer("⭐⭐⭐⭐⭐⭐ **6-Daraja:** Proyekti havolasini yuboring:")

@dp.message(AddWaifuState.l6_proj)
async def add_waifu_step_team_view(message: types.Message, state: FSMContext):
    await state.update_data(l6_proj=message.text)
    await state.set_state(AddWaifuState.team_view)
    await message.answer("👥 Jamoaviy proyekt (Team View) rasmi havolasini yuboring:")

@dp.message(AddWaifuState.team_view)
async def add_waifu_final_save(message: types.Message, state: FSMContext):
    data = await state.get_data()
    team_view_link = message.text
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            """INSERT INTO waifus (
                name, anime_name, description, rarity, promo_limit, gc_price, diamond_price,
                l1_img, l1_proj, l2_img, l2_proj, l3_img, l3_proj, 
                l4_img, l4_proj, l5_img, l5_proj, l6_img, l6_proj, team_view, image_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data['name'], data['anime_name'], data['description'], data['rarity'], 
                data['promo_limit'], data['gc_price'], data['diamond_price'],
                data['l1_img'], data['l1_proj'], data['l2_img'], data['l2_proj'], 
                data['l3_img'], data['l3_proj'], data['l4_img'], data['l4_proj'], 
                data['l5_img'], data['l5_proj'], data['l6_img'], data['l6_proj'], 
                team_view_link, data['l1_img']
            )
        )
        new_waifu_id = cursor.lastrowid
        await db.commit()
    await state.clear()
    
    broadcast_text = (
        f"📢 **Diqqat! Yangi qahramon qo'shildi!**\n\n"
        f"👤 **Ismi:** {data['name']}\n"
        f"🎬 **Anime:** {data['anime_name']}\n"
        f"✨ **Daraja:** {data['rarity']}\n"
        f"🆔 **ID:** `{new_waifu_id}`\n\n"
        f"🎮 Mini Ilovada qo'lga kiriting!"
    )
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT chat_id, chat_type FROM connected_chats") as cursor:
            chats = await cursor.fetchall()
            
    for chat_id, chat_type in chats:
        try:
            if chat_type == "channel":
                await bot.send_photo(chat_id=chat_id, photo=data['l6_img'], caption=broadcast_text, parse_mode="Markdown")
            else:
                markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎮 Mini Ilovani Ochish", web_app=WebAppInfo(url=WEBAPP_URL))]])
                await bot.send_photo(chat_id=chat_id, photo=data['l6_img'], caption=broadcast_text, reply_markup=markup, parse_mode="Markdown")
        except Exception as e:
            logging.error(f"Xabar yuborish xatosi ({chat_id}): {e}")

    await message.answer("✅ Qahramon qo'shildi va barcha chatlarga tarqatildi!", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="👑 Panelga qaytish", callback_data="admin_panel_main")]]))

@dp.callback_query(F.data == "admin_add_promo")
async def promo_step1(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS: return
    await state.set_state(PromoState.code)
    await call.message.edit_text("🎟 Promokod so'zini kiriting:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_panel_main")]]))
    await call.answer()

@dp.message(PromoState.code)
async def promo_step2(message: types.Message, state: FSMContext):
    await state.update_data(code=message.text)
    await state.set_state(PromoState.waifu_id)
    await message.answer("🆔 Qahramon ID raqamini kiriting:")

@dp.message(PromoState.waifu_id)
async def promo_step3(message: types.Message, state: FSMContext):
    await state.update_data(waifu_id=int(message.text))
    await state.set_state(PromoState.limit)
    await message.answer("🔢 Limitini kiriting:")

@dp.message(PromoState.limit)
async def promo_save(message: types.Message, state: FSMContext):
    data = await state.get_data()
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO promo_codes (code, waifu_id, uses_left) VALUES (?, ?, ?)", (data['code'], data['waifu_id'], int(message.text)))
        await db.commit()
    await state.clear()
    await message.answer("✅ Promokod yaratildi!", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="👑 Panelga qaytish", callback_data="admin_panel_main")]]))

@dp.callback_query(F.data == "admin_payment_settings")
async def payment_settings_menu(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS: return
    card_num = await get_setting("card_number")
    card_holder = await get_setting("card_holder")
    await call.message.edit_text(f"💳 Karta: `{card_num}`\nEgasi: `{card_holder}`", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Karta raqamini o'zgartirish", callback_data="set_card_num")],
        [InlineKeyboardButton(text="👤 Egasini o'zgartirish", callback_data="set_card_holder")],
        [InlineKeyboardButton(text="« Orqaga", callback_data="admin_panel_main")]
    ]), parse_mode="Markdown")
    await call.answer()

@dp.callback_query(F.data == "set_card_num")
async def set_card_num_start(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(SettingsState.card_number)
    await call.message.edit_text("Yangi karta raqamini yuboring:")
    await call.answer()

@dp.message(SettingsState.card_number)
async def save_card_num(message: types.Message, state: FSMContext):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO bot_settings (key, value) VALUES ('card_number', ?)", (message.text,))
        await db.commit()
    await state.clear()
    await message.answer("✅ Karta raqami yangilandi!")

@dp.callback_query(F.data == "set_card_holder")
async def set_card_holder_start(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(SettingsState.card_holder)
    await call.message.edit_text("Yangi karta egasini yuboring:")
    await call.answer()

@dp.message(SettingsState.card_holder)
async def save_card_holder(message: types.Message, state: FSMContext):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO bot_settings (key, value) VALUES ('card_holder', ?)", (message.text,))
        await db.commit()
    await state.clear()
    await message.answer("✅ Karta egasi yangilandi!")

@dp.callback_query(F.data == "admin_links")
async def link_menu(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS: return
    ch = await get_setting("channel_url")
    gr = await get_setting("group_url")
    await call.message.edit_text(f"🔗 Kanal: {ch}\nGuruh: {gr}", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Kanalni o'zgartirish", callback_data="set_ch")],
        [InlineKeyboardButton(text="👥 Guruhni o'zgartirish", callback_data="set_gr")],
        [InlineKeyboardButton(text="« Orqaga", callback_data="admin_panel_main")]
    ]), parse_mode="Markdown")
    await call.answer()

@dp.callback_query(F.data == "set_ch")
async def set_ch_start(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(SettingsState.channel_url)
    await call.message.edit_text("Yangi kanal havolasini yuboring:")
    await call.answer()

@dp.message(SettingsState.channel_url)
async def save_ch(message: types.Message, state: FSMContext):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO bot_settings (key, value) VALUES ('channel_url', ?)", (message.text,))
        await db.commit()
    await state.clear()
    await message.answer("✅ Kanal havolasi saqlandi!")

@dp.callback_query(F.data == "set_gr")
async def set_gr_start(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(SettingsState.group_url)
    await call.message.edit_text("Yangi guruh havolasini yuboring:")
    await call.answer()

@dp.message(SettingsState.group_url)
async def save_gr(message: types.Message, state: FSMContext):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO bot_settings (key, value) VALUES ('group_url', ?)", (message.text,))
        await db.commit()
    await state.clear()
    await message.answer("✅ Guruh havolasi saqlandi!")

@dp.callback_query(F.data == "admin_design_menu")
async def admin_design_menu(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS: return
    await call.message.edit_text("🎨 Dizayn sozlamalari:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔲 Qirralilik (%)", callback_data="set_border")],
        [InlineKeyboardButton(text="🪞 Shaffoflik (%)", callback_data="set_opacity")],
        [InlineKeyboardButton(text="🖼 Orqa fon", callback_data="set_bg")],
        [InlineKeyboardButton(text="« Orqaga", callback_data="admin_panel_main")]
    ]), parse_mode="Markdown")
    await call.answer()

@dp.callback_query(F.data == "set_border")
async def set_border_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS: return
    await state.set_state(DesignSettingsState.border_radius)
    await call.message.edit_text("Qirralilik foizini kiriting:")
    await call.answer()

@dp.message(DesignSettingsState.border_radius)
async def save_border_radius(message: types.Message, state: FSMContext):
    val = message.text.strip()
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO bot_settings (key, value) VALUES ('border_radius', ?)", (val,))
        await db.commit()
    await state.clear()
    await message.answer(f"✅ Qirralilik {val}% qilindi!")

@dp.callback_query(F.data == "set_opacity")
async def set_opacity_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS: return
    await state.set_state(DesignSettingsState.glass_opacity)
    await call.message.edit_text("Shaffoflik foizini kiriting:")
    await call.answer()

@dp.message(DesignSettingsState.glass_opacity)
async def save_glass_opacity(message: types.Message, state: FSMContext):
    val = message.text.strip()
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO bot_settings (key, value) VALUES ('glass_opacity', ?)", (val,))
        await db.commit()
    await state.clear()
    await message.answer(f"✅ Shaffoflik {val}% qilindi!")

@dp.callback_query(F.data == "set_bg")
async def set_bg_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS: return
    await state.set_state(DesignSettingsState.bg_image)
    await call.message.edit_text("Orqa fon rasm havolasini yuboring:")
    await call.answer()

@dp.message(DesignSettingsState.bg_image)
async def save_bg_image(message: types.Message, state: FSMContext):
    link = message.text.strip()
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO bot_settings (key, value) VALUES ('bg_image', ?)", (link,))
        await db.commit()
    await state.clear()
    await message.answer("✅ Orqa fon yangilandi!")

@dp.callback_query(F.data == "admin_broadcast")
async def broadcast_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS: return
    await state.set_state(BroadcastState.waiting_for_message)
    await call.message.edit_text("📢 Xabarni yuboring:")
    await call.answer()

@dp.message(BroadcastState.waiting_for_message)
async def broadcast_exec(message: types.Message, state: FSMContext):
    await state.clear()
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id FROM users") as cursor:
            users = await cursor.fetchall()
    success, failed = 0, 0
    for (uid,) in users:
        try:
            await message.send_copy(chat_id=uid)
            success += 1
            await asyncio.sleep(0.05)
        except:
            failed += 1
    await message.answer(f"✅ Tarqatildi! Muvaffaqiyatli: {success}, Xato: {failed}")

async def handle_home(request):
    html_content = """
    <!DOCTYPE html>
    <html lang="uz">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>GrabCharacter Mini App</title>
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            :root {
                --bg-glass: rgba(255, 255, 255, 0.08);
                --border-glass: rgba(255, 255, 255, 0.15);
                --text-color: #ffffff;
                --accent-color: #a855f7;
            }
            body {
                margin: 0;
                padding: 0;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #0f172a, #1e1b4b, #311042);
                color: var(--text-color);
                height: 100vh;
                display: flex;
                flex-direction: column;
                overflow: hidden;
            }
            .content-area {
                flex: 1;
                position: relative;
                overflow-y: auto;
                padding: 15px;
                padding-bottom: 70px;
            }
            .section {
                display: none;
                animation: fadeIn 0.3s ease-in-out;
            }
            .section.active {
                display: block;
            }
            @keyframes fadeIn {
                from { opacity: 0; transform: translateY(5px); }
                to { opacity: 1; transform: translateY(0); }
            }
            .glass-card {
                background: var(--bg-glass);
                border: 1px solid var(--border-glass);
                border-radius: 16px;
                backdrop-filter: blur(12px);
                padding: 15px;
                margin-bottom: 12px;
                box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
            }
            .grid-2 {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 10px;
            }
            .bottom-nav {
                position: fixed;
                bottom: 0;
                left: 0;
                width: 100%;
                height: 60px;
                background: rgba(15, 23, 42, 0.9);
                backdrop-filter: blur(15px);
                border-top: 1px solid var(--border-glass);
                display: flex;
                justify-content: space-around;
                align-items: center;
                z-index: 1000;
                box-sizing: border-box;
                padding: 0 5px;
            }
            .nav-item {
                background: none;
                border: none;
                color: #94a3b8;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                flex: 1;
                cursor: pointer;
                transition: 0.2s;
                font-size: 10px;
                font-weight: 600;
            }
            .nav-item span.icon {
                font-size: 20px;
                margin-bottom: 2px;
            }
            .nav-item.active {
                color: #ffffff;
                transform: scale(1.05);
            }
            .nav-item.active span.icon {
                filter: drop-shadow(0 0 6px rgba(168, 85, 247, 0.8));
            }
            #onboarding-modal {
                position: fixed;
                top: 0; left: 0; width: 100%; height: 100%;
                background: rgba(0, 0, 0, 0.85);
                backdrop-filter: blur(10px);
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                z-index: 9999;
                padding: 20px;
                box-sizing: border-box;
                text-align: center;
            }
            .onboard-box {
                background: rgba(255, 255, 255, 0.1);
                border: 1px solid var(--border-glass);
                padding: 25px;
                border-radius: 20px;
                max-width: 320px;
            }
            .onboard-btn {
                background: #a855f7;
                color: #fff;
                border: none;
                padding: 10px 20px;
                border-radius: 12px;
                font-weight: bold;
                margin-top: 15px;
                cursor: pointer;
            }
        </style>
    </head>
    <body>

        <div id="onboarding-modal">
            <div class="onboard-box">
                <h2>🌸 Xush kelibsiz!</h2>
                <p id="onboard-text">GrabCharakter ilovasiga xush kelibsiz! Bu yerda siz o'z qahramonlaringizni boshqarasiz va darajalarini oshirasiz.</p>
                <button class="onboard-btn" onclick="nextOnboardStep()">Tushunarli ➡️</button>
            </div>
        </div>

        <div class="content-area">
            <div id="section-1" class="section active">
                <h2>Proeksiya Markazi</h2>
                <div class="glass-card" style="text-align: center; min-height: 220px; display: flex; flex-direction: column; justify-content: center; align-items: center;">
                    <div id="active-projection-view">
                        <p>Qahramon oyog'i tagidagi 3D zona va daraja assetlari</p>
                    </div>
                </div>
            </div>

            <div id="section-2" class="section">
                <h2>Mening Kolleksiyam</h2>
                <div id="collection-list">
                    <div class="glass-card">Ma'lumotlar yuklanmoqda...</div>
                </div>
            </div>

            <div id="section-3" class="section">
                <h2>Market va Savdo</h2>
                <div class="grid-2">
                    <div class="glass-card" style="text-align: center;">🔥 Yangi Qahramon<br><small>150 🪙</small></div>
                    <div class="glass-card" style="text-align: center;">✨ Afsonaviy Case<br><small>300 🪙</small></div>
                </div>
            </div>

            <div id="section-4" class="section">
                <h2>Bitimlar (Trade)</h2>
                <div class="glass-card">
                    <p>O'zaro ayirboshlash va savdo markazi.</p>
                </div>
            </div>

            <div id="section-5" class="section">
                <h2>Profil va Sozlamari</h2>
                <div class="glass-card" id="user-profile-card">
                    <p>Foydalanuvchi ma'lumotlari yuklanmoqda...</p>
                </div>
            </div>
        </div>

        <nav class="bottom-nav">
            <button class="nav-item active" onclick="switchSection(1, this)">
                <span class="icon">🏠</span>
                <span>Asosiy</span>
            </button>
            <button class="nav-item" onclick="switchSection(2, this)">
                <span class="icon">🎒</span>
                <span>Kolleksiya</span>
            </button>
            <button class="nav-item" onclick="switchSection(3, this)">
                <span class="icon">🛒</span>
                <span>Market</span>
            </button>
            <button class="nav-item" onclick="switchSection(4, this)">
                <span class="icon">🔄</span>
                <span>Bitim</span>
            </button>
            <button class="nav-item" onclick="switchSection(5, this)">
                <span class="icon">⚙️</span>
                <span>Profil</span>
            </button>
        </nav>

        <script>
            let tg = window.Telegram.WebApp;
            tg.expand();

            const userId = tg.initDataUnsafe?.user?.id || 7986354170;

            let onboardStep = 1;
            function nextOnboardStep() {
                playClickSound();
                let textEl = document.getElementById('onboard-text');
                if(onboardStep === 1) {
                    textEl.innerText = "Pastdagi 5 ta bo'lim orqali Kolleksiya, Market va Profilingizni boshqarishingiz mumkin.";
                    onboardStep++;
                } else if(onboardStep === 2) {
                    textEl.innerText = "Tayyorsiz! Boshlaymiz!";
                    onboardStep++;
                } else {
                    document.getElementById('onboarding-modal').style.display = 'none';
                }
            }

            function playClickSound() {
                let audio = new Audio('https://actions.google.com/sounds/v1/ui/button_click.ogg');
                audio.play().catch(e => console.log(e));
            }

            function switchSection(sectionNumber, btnElement) {
                playClickSound();
                document.querySelectorAll('.section').forEach(sec => {
                    sec.classList.remove('active');
                });
                document.getElementById(`section-${sectionNumber}`).classList.add('active');

                document.querySelectorAll('.nav-item').forEach(btn => {
                    btn.classList.remove('active');
                });
                btnElement.classList.add('active');

                if(sectionNumber === 2 || sectionNumber === 5) {
                    loadUserData();
                }
            }

            async function loadUserData() {
                try {
                    let res = await fetch(`/api/user?user_id=${userId}`);
                    let data = await res.json();
                    if(data.status === 'success') {
                        let profile = data.profile;
                        document.getElementById('user-profile-card').innerHTML = `
                            <p><b>Foydalanuvchi:</b> @${profile.username || 'Noma\'lum'}</p>
                            <p>🪙 GC Balans: <b>${profile.balance_gc}</b></p>
                            <p>💎 Olmoslar: <b>${profile.diamonds}</b></p>
                        `;

                        let colList = document.getElementById('collection-list');
                        if(data.waifus.length === 0) {
                            colList.innerHTML = `<div class="glass-card">Kolleksiyangiz hozircha bo'sh.</div>`;
                        } else {
                            let html = '';
                            data.waifus.forEach(w => {
                                let currentImg = w[`l${w.level}_img`] || w.l1_img;
                                html += `
                                    <div class="glass-card" style="display: flex; align-items: center; gap: 15px;">
                                        <img src="${currentImg}" style="width: 50px; height: 50px; border-radius: 10px; object-fit: cover;">
                                        <div style="text-align: left;">
                                            <b>${w.name}</b> (${w.rarity})<br>
                                            <small>Daraja: Level ${w.level} — x${w.count}</small>
                                        </div>
                                    </div>
                                `;
                            });
                            colList.innerHTML = html;
                        }
                    }
                } catch(e) {
                    console.log("Xatolik:", e);
                }
            }

            loadUserData();
        </script>
    </body>
    </html>
    """
    return web.Response(text=html_content, content_type='text/html')

async def handle_api_settings(request):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT key, value FROM bot_settings") as cursor:
            rows = await cursor.fetchall()
            settings = {k: v for k, v in rows}
    return web.json_response({"status": "success", "settings": settings})

async def handle_api_user_profile(request):
    user_id = request.query.get("user_id")
    if not user_id:
        return web.json_response({"status": "error", "message": "user_id required"}, status=400)
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT username, balance_gc, diamonds FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user = await cursor.fetchone()
            if not user:
                return web.json_response({"status": "error", "message": "User not found"}, status=404)
        async with db.execute("""
            SELECT w.id, w.name, w.anime_name, w.description, w.rarity, w.gc_price, w.diamond_price,
                   w.l1_img, w.l1_proj, w.l2_img, w.l2_proj, w.l3_img, w.l3_proj, 
                   w.l4_img, w.l4_proj, w.l5_img, w.l5_proj, w.l6_img, w.l6_proj, w.team_view, 
                   uw.count, uw.level 
            FROM user_waifus uw 
            JOIN waifus w ON uw.waifu_id = w.id 
            WHERE uw.user_id = ?
        """, (user_id,)) as cursor:
            waifus_rows = await cursor.fetchall()
            
    waifus_list = []
    for w in waifus_rows:
        waifus_list.append({
            "id": w[0], "name": w[1], "anime_name": w[2], "description": w[3], "rarity": w[4],
            "gc_price": w[5], "diamond_price": w[6], "l1_img": w[7], "l1_proj": w[8],
            "l2_img": w[9], "l2_proj": w[10], "l3_img": w[11], "l3_proj": w[12],
            "l4_img": w[13], "l4_proj": w[14], "l5_img": w[15], "l5_proj": w[16],
            "l6_img": w[17], "l6_proj": w[18], "team_view": w[19], "count": w[20], "level": w[21]
        })
    return web.json_response({"status": "success", "profile": {"username": user[0], "balance_gc": user[1], "diamonds": user[2]}, "waifus": waifus_list})

async def handle_buy_waifu(request):
    return web.json_response({"success": True, "message": "Sotib olindi!"})

async def handle_sell_waifu(request):
    return web.json_response({"success": True, "message": "Sotildi!"})

@web.middleware
async def cors_middleware(request, handler):
    if request.method == "OPTIONS":
        return web.Response(status=200, headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        })
    response = await handler(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response

async def main():
    try:
        await db_start()
        print("🤖 Bot va server Webhook rejimida ishga tushirilmoqda...")
        
        webapp_button = MenuButtonWebApp(text="GrabCharakter", web_app=WebAppInfo(url=WEBAPP_URL))
        await bot.set_chat_menu_button(menu_button=webapp_button)
        
        app = web.Application(middlewares=[cors_middleware])
        app.router.add_get("/", handle_home)
        app.router.add_get("/api/settings", handle_api_settings)
        app.router.add_get("/api/user", handle_api_user_profile)
        app.router.add_post("/api/buy", handle_buy_waifu)
        app.router.add_post("/api/sell", handle_sell_waifu)
        
        WEBHOOK_PATH = "/webhook"
        WEBHOOK_URL = f"{WEBAPP_URL}{WEBHOOK_PATH}"
        
        from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
        
        await bot.set_webhook(url=WEBHOOK_URL, drop_pending_updates=True)
        
        webhook_requests_handler = SimpleRequestHandler(
            dispatcher=dp,
            bot=bot,
        )
        webhook_requests_handler.register(app, path=WEBHOOK_PATH)
        setup_application(app, dp, bot=bot)
        
        runner = web.AppRunner(app)
        await runner.setup()
        
        port = int(os.environ.get("PORT", 10000))
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        print(f"🌐 Webhook server {port}-portda ishga tushdi!")

        await asyncio.Event().wait()
        
    finally:
        await bot.delete_webhook()
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot to'xtatildi.")
        
