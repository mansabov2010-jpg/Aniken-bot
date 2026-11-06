import asyncio
import logging
import random
import os
import aiosqlite
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiohttp import web

# ==========================================
# ⚙️ ASOSIY SOZLAR VA KONFIGURATSIYA
# ==========================================
TOKEN = "9111857366:AAGYcgVef3m2KTbQgMayoYRcgYcv7V08Foc"
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

# ==========================================
# 🗂 FSM HOLATLARI (STATES)
# ==========================================
class AddWaifuState(StatesGroup):
    name = State()
    rarity = State()
    image_url = State()
    front_view = State()
    back_view = State()
    side_view = State()
    animated_view = State()
    gc_price = State()
    diamond_price = State()

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

class ShopItemState(StatesGroup):
    title = State()
    diamond_cost = State()
    amount = State()

class DesignSettingsState(StatesGroup):
    border_radius = State()
    glass_opacity = State()
    bg_image = State()

class AddAdState(StatesGroup):
    media = State()
    reward = State()

# ==========================================
# 💾 TO'LIQ MA'LUMOTLAR BAZASI (YANGILANGAN)
# ==========================================
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
        # Yangi rakurslar va animatsion vizuallar qo'shilgan waifus jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS waifus (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                rarity TEXT,
                image_url TEXT,
                front_view TEXT,
                back_view TEXT,
                side_view TEXT,
                animated_view TEXT,
                gc_price INTEGER DEFAULT 0,
                diamond_price INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_waifus (
                user_id INTEGER,
                waifu_id INTEGER,
                count INTEGER DEFAULT 1,
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
        await db.execute("""
            CREATE TABLE IF NOT EXISTS active_trades (
                trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER,
                owner_items TEXT,
                partner_id INTEGER,
                partner_items TEXT,
                status TEXT DEFAULT 'pending'
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS shop_packages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                diamonds INTEGER,
                price_text TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                url TEXT,
                reward_gc INTEGER
            )
        """)
        await db.commit()
        
        defaults = [
            ('channel_url', 'https://t.me/channel_soon'),
            ('group_url', 'https://t.me/group_soon'),
            ('bg_color', '#121212'),
            ('button_color', '#1E88E5'),
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

# ==========================================
# 🌸 2. ASOSIY MENYU, START VA GURUH MEXANIKASI
# ==========================================
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
        [InlineKeyboardButton(text="🎮 Mini Ilovani Ochish", web_app=WebAppInfo(url=WEBAPP_URL))],
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
        "✨ **GrabCharakter** olamiga xush kelibsiz! Pastdagi tugmalar orqali Mini Ilovaga o'ting yoki guruhlarda qahramonlar ovlang, tanga ishlang va bitimlar tuzing."
    )
    await message.answer(text, reply_markup=markup, parse_mode="Markdown")

@dp.callback_query(F.data == "my_collection")
async def process_collection(call: types.CallbackQuery):
    user_id = call.from_user.id
    
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("""
            SELECT w.name, w.rarity, uw.count, w.id 
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
    for idx, (name, rarity, count, w_id) in enumerate(rows, 1):
        collection_text += f"{idx}. [ID: {w_id}] {name} ({rarity}) — **x{count}**\n"
        
    await call.message.edit_text(collection_text, reply_markup=markup, parse_mode="Markdown")
    await call.answer()

@dp.callback_query(F.data == "trade_info")
async def trade_info_callback(call: types.CallbackQuery):
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="« Bosh menyu", callback_data="back_home")]
    ])
    await call.message.edit_text(
        "🔄 **Bitim (Trade) Tizimi:**\n\n"
        "Guruhlarda o'zaro qahramonlarni ayirboshlash uchun guruh ichida `/bitim` buyrug'ini yuboring. "
        "Shuningdek, to'liq vizual savdo jarayonini Mini Ilova orqali ham boshqarishingiz mumkin!",
        reply_markup=markup,
        parse_mode="Markdown"
    )
    await call.answer()

@dp.callback_query(F.data == "back_home")
async def process_home(call: types.CallbackQuery):
    user_id = call.from_user.id
    channel_url = await get_setting("channel_url")
    group_url = await get_setting("group_url")
    
    markup_rows = [
        [InlineKeyboardButton(text="🎮 Mini Ilovani Ochish", web_app=WebAppInfo(url=WEBAPP_URL))],
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

# ==========================================
# ⚡ GURUHLARDA SPAWN VA TUTIB OLISH
# ==========================================
@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def group_message_handler(message: types.Message):
    if message.text and message.text.startswith("/bitim"):
        await handle_group_trade(message)
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
            
            async with db.execute("SELECT id, name, rarity, image_url FROM waifus") as cursor:
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
                await message.answer_photo(photo=w_image, caption=text, reply_markup=markup, parse_mode="Markdown")

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
            
        async with db.execute("SELECT count FROM user_waifus WHERE user_id = ? AND waifu_id = ?", (user_id, w_id)) as cursor:
            row = await cursor.fetchone()
            if row:
                new_count = row[0] + 1
                await db.execute("UPDATE user_waifus SET count = ? WHERE user_id = ? AND waifu_id = ?", (new_count, user_id, w_id))
                msg_suffix = f"(Takroriy! Hozirda jami: **x{new_count}**)"
            else:
                await db.execute("INSERT INTO user_waifus (user_id, waifu_id, count) VALUES (?, ?, 1)", (user_id, w_id))
                msg_suffix = "(Yangi qahramon kolleksiyaga qo'shildi!)"
        await db.commit()
        
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except:
        pass
        
    await call.answer(f"🎉 Tabriklaymiz! Siz {w_name} ni qo'lga kiritdingiz!", show_alert=True)
    await call.message.reply(f"🏆 **{call.from_user.first_name}** — {w_name} ({w_rarity}) qahramonini tutdi! {msg_suffix}", parse_mode="Markdown")

async def handle_group_trade(message: types.Message):
    await message.answer(
        "🔄 **Guruhdagi Bitim (Trade):**\n"
        "O'zaro personajlar ayirboshlash uchun to'liq interaktiv oynani ochish uchun Mini Ilovadan foydalaning!",
        parse_mode="Markdown"
        )

# ==========================================
# 👑 3. ADMIN PANEL VA KO'P RAKURSLI QAHRAMONLAR
# ==========================================
@dp.callback_query(F.data == "admin_panel_main")
async def admin_panel_callback(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
        
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor: u_cnt = (await cursor.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM waifus") as cursor: w_cnt = (await cursor.fetchone())[0]
            
    text = (
        f"👑 **Admin Boshqaruv Paneli:**\n\n"
        f"👥 Foydalanuvchilar: {u_cnt}\n"
        f"✨ Qahramonlar bazasi: {w_cnt}\n\n"
        "Kerakli bo'limni tanlang:"
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Qahramon qo'shish (Multi-View)", callback_data="admin_add_waifu")],
        [InlineKeyboardButton(text="🎟 Promokod yaratish", callback_data="admin_add_promo")],
        [InlineKeyboardButton(text="💳 Karta va To'lovlar", callback_data="admin_payment_settings")],
        [InlineKeyboardButton(text="🔗 Havolalarni sozlash", callback_data="admin_links")],
        [InlineKeyboardButton(text="🎨 Mini App Dizayni", callback_data="admin_design_menu")],
        [InlineKeyboardButton(text="📢 Barchaga xabar yuborish", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="« Bosh menyu", callback_data="back_home")]
    ])
    await call.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
    await call.answer()

# Qahramon qo'shish FSM (Multi-View: Old, Orqa, Yonbosh va Animatsion)
@dp.callback_query(F.data == "admin_add_waifu")
async def add_waifu_step1(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS: return
    await state.set_state(AddWaifuState.name)
    await call.message.edit_text("📝 Yangi qahramon nomini kiriting:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_panel_main")]]))
    await call.answer()

@dp.message(AddWaifuState.name)
async def add_waifu_step2(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddWaifuState.rarity)
    await message.answer("✨ Darajasini kiriting (masalan: 🌟 Afsonaviy, 💎 Nodir, ⭐ Oddiy):")

@dp.message(AddWaifuState.rarity)
async def add_waifu_step3(message: types.Message, state: FSMContext):
    await state.update_data(rarity=message.text)
    await state.set_state(AddWaifuState.image_url)
    await message.answer("🖼 Qahramonning asosiy rasm URL manzilini yuboring:")

@dp.message(AddWaifuState.image_url)
async def add_waifu_step4(message: types.Message, state: FSMContext):
    await state.update_data(image_url=message.text)
    await state.set_state(AddWaifuState.front_view)
    await message.answer("📸 Qahramonning **old tarafdan** ko'rinish rasmini yuboring (havola):")

@dp.message(AddWaifuState.front_view)
async def add_waifu_step_front(message: types.Message, state: FSMContext):
    await state.update_data(front_view=message.text)
    await state.set_state(AddWaifuState.back_view)
    await message.answer("🔄 Qahramonning **orqadan** ko'rinish rasmini yuboring (havola):")

@dp.message(AddWaifuState.back_view)
async def add_waifu_step_back(message: types.Message, state: FSMContext):
    await state.update_data(back_view=message.text)
    await state.set_state(AddWaifuState.side_view)
    await message.answer("📐 Qahramonning **yonboshdan** ko'rinish rasmini yuboring (havola):")

@dp.message(AddWaifuState.side_view)
async def add_waifu_step_side(message: types.Message, state: FSMContext):
    await state.update_data(side_view=message.text)
    await state.set_state(AddWaifuState.animated_view)
    await message.answer("✨ Qahramonning **sal-sal qimirlaydigan (animatsion/Live2D)** formatdagi rasmini yuboring:")

@dp.message(AddWaifuState.animated_view)
async def add_waifu_step_animated(message: types.Message, state: FSMContext):
    await state.update_data(animated_view=message.text)
    await state.set_state(AddWaifuState.gc_price)
    await message.answer("💰 Mini Ilovada sotish uchun GC (tanga) narxini kiriting (faqat raqam):")

@dp.message(AddWaifuState.gc_price)
async def add_waifu_step5(message: types.Message, state: FSMContext):
    await state.update_data(gc_price=int(message.text))
    await state.set_state(AddWaifuState.diamond_price)
    await message.answer("💎 Olmos narxini kiriting (faqat raqam):")

@dp.message(AddWaifuState.diamond_price)
async def add_waifu_save(message: types.Message, state: FSMContext):
    data = await state.get_data()
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """INSERT INTO waifus (name, rarity, image_url, front_view, back_view, side_view, animated_view, gc_price, diamond_price) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data['name'], data['rarity'], data['image_url'], 
                data['front_view'], data['back_view'], data['side_view'], 
                data['animated_view'], data['gc_price'], int(message.text)
            )
        )
        await db.commit()
    await state.clear()
    await message.answer("✅ Qahramon barcha rakurslari va animatsion proyektlari bilan bazaga muvaffaqiyatli qo'shildi!", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="👑 Panelga qaytish", callback_data="admin_panel_main")]]))

# Promokod qo'shish FSM
@dp.callback_query(F.data == "admin_add_promo")
async def promo_step1(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS: return
    await state.set_state(PromoState.code)
    await call.message.edit_text("🎟 Promokod so'zini kiriting (masalan: GRAB2026):", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_panel_main")]]))
    await call.answer()

@dp.message(PromoState.code)
async def promo_step2(message: types.Message, state: FSMContext):
    await state.update_data(code=message.text)
    await state.set_state(PromoState.waifu_id)
    await message.answer("🆔 Beriladigan qahramonning ID raqamini kiriting:")

@dp.message(PromoState.waifu_id)
async def promo_step3(message: types.Message, state: FSMContext):
    await state.update_data(waifu_id=int(message.text))
    await state.set_state(PromoState.limit)
    await message.answer("🔢 Promokod necha marta ishlatilishi mumkinligini (limitini) kiriting:")

@dp.message(PromoState.limit)
async def promo_save(message: types.Message, state: FSMContext):
    data = await state.get_data()
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO promo_codes (code, waifu_id, uses_left) VALUES (?, ?, ?)", (data['code'], data['waifu_id'], int(message.text)))
        await db.commit()
    await state.clear()
    await message.answer("✅ Promokod muvaffaqiyatli yaratildi va faollashdi!", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="👑 Panelga qaytish", callback_data="admin_panel_main")]]))

# Karta va to'lov rekvizitlarini boshqarish
@dp.callback_query(F.data == "admin_payment_settings")
async def payment_settings_menu(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS: return
    card_num = await get_setting("card_number")
    card_holder = await get_setting("card_holder")
    
    text = (
        f"💳 **To'lov Rekvizitlarini Sozlash:**\n\n"
        f"Hozirgi karta: `{card_num}`\n"
        f"Karta egasi: `{card_holder}`"
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Karta raqamini o'zgartirish", callback_data="set_card_num")],
        [InlineKeyboardButton(text="👤 Karta egasini o'zgartirish", callback_data="set_card_holder")],
        [InlineKeyboardButton(text="« Orqaga", callback_data="admin_panel_main")]
    ])
    await call.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
    await call.answer()

@dp.callback_query(F.data == "set_card_num")
async def set_card_num_start(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(SettingsState.card_number)
    await call.message.edit_text("Yangi karta raqamini kiriting (masalan: 8600 ...):")
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
    await call.message.edit_text("Yangi karta egasining F.I.O. ni kiriting:")
    await call.answer()

@dp.message(SettingsState.card_holder)
async def save_card_holder(message: types.Message, state: FSMContext):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO bot_settings (key, value) VALUES ('card_holder', ?)", (message.text,))
        await db.commit()
    await state.clear()
    await message.answer("✅ Karta egasi ismi yangilandi!")

# Havolalar menyusi
@dp.callback_query(F.data == "admin_links")
async def link_menu(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS: return
    ch = await get_setting("channel_url")
    gr = await get_setting("group_url")
    text = f"🔗 **Havolalar:**\n\nKanal: {ch}\nGuruh: {gr}"
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
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

# Mini App Dizaynini Boshqarish Menu
@dp.callback_query(F.data == "admin_design_menu")
async def admin_design_menu(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS: return
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔲 Qirralilikni o'zgartirish (%)", callback_data="set_border")],
        [InlineKeyboardButton(text="🪞 Shaffoflikni o'zgartirish (%)", callback_data="set_opacity")],
        [InlineKeyboardButton(text="🖼 Orqa fon rasmini o'rnatish", callback_data="set_bg")],
        [InlineKeyboardButton(text="« Orqaga", callback_data="admin_panel_main")]
    ])
    await call.message.edit_text("🎨 **Mini App Dizayn Sozlamalari:**\n\nBu yerda barcha elementlarning ko'rinishini foizlar orqali boshqarasiz.", reply_markup=markup, parse_mode="Markdown")
    await call.answer()

@dp.callback_query(F.data == "set_border")
async def set_border_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS: return
    await state.set_state(DesignSettingsState.border_radius)
    await call.message.edit_text("🔲 Elementlar qirraliligini foizda kiriting (0% dan 100% gacha, masalan: `15`):", parse_mode="Markdown")
    await call.answer()

@dp.message(DesignSettingsState.border_radius)
async def save_border_radius(message: types.Message, state: FSMContext):
    val = message.text.strip()
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO bot_settings (key, value) VALUES ('border_radius', ?)", (val,))
        await db.commit()
    await state.clear()
    await message.answer(f"✅ Qirralilik muvaffaqiyatli **{val}%** qilib belgilandi!")

@dp.callback_query(F.data == "set_opacity")
async def set_opacity_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS: return
    await state.set_state(DesignSettingsState.glass_opacity)
    await call.message.edit_text("🪞 Shaffoflik darajasini foizda kiriting (0% dan 100% gacha, masalan: `85`):", parse_mode="Markdown")
    await call.answer()

@dp.message(DesignSettingsState.glass_opacity)
async def save_glass_opacity(message: types.Message, state: FSMContext):
    val = message.text.strip()
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO bot_settings (key, value) VALUES ('glass_opacity', ?)", (val,))
        await db.commit()
    await state.clear()
    await message.answer(f"✅ Shaffoflik muvaffaqiyatli **{val}%** qilib belgilandi!")

@dp.callback_query(F.data == "set_bg")
async def set_bg_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS: return
    await state.set_state(DesignSettingsState.bg_image)
    await call.message.edit_text("🖼 Mini App orqa foni uchun rasm yuboring:", parse_mode="Markdown")
    await call.answer()

@dp.message(DesignSettingsState.bg_image)
async def save_bg_image(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id if message.photo else ""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO bot_settings (key, value) VALUES ('bg_image', ?)", (photo_id,))
        await db.commit()
    await state.clear()
    await message.answer("✅ Orqa fon rasmi muvaffaqiyatli yangilandi!")

# Rassilka
@dp.callback_query(F.data == "admin_broadcast")
async def broadcast_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS: return
    await state.set_state(BroadcastState.waiting_for_message)
    await call.message.edit_text("📢 Barcha foydalanuvchilarga yuboriladigan xabarni (matn, rasm yoki video) yuboring:")
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
    await message.answer(f"✅ Xabar tarqatildi!\n\nMuvaffaqiyatli: {success}\nXato (bloklagan): {failed}")

# ==========================================
# 🌐 4. MINI ILOVA API SERVERI VA ISHGA TUSHIRISH
# ==========================================
async def handle_home(request):
    return web.Response(text="GrabCharakter & Mini App Ultimate Server is running 24/7!", content_type='text/html')

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
            
        # Multi-view va animatsion ko'rinishlar bilan birga ma'lumot olish
        async with db.execute("""
            SELECT w.id, w.name, w.rarity, w.image_url, w.front_view, w.back_view, w.side_view, w.animated_view, uw.count, w.gc_price, w.diamond_price 
            FROM user_waifus uw 
            JOIN waifus w ON uw.waifu_id = w.id 
            WHERE uw.user_id = ?
        """, (user_id,)) as cursor:
            waifus_rows = await cursor.fetchall()
            
    waifus_list = []
    for w in waifus_rows:
        waifus_list.append({
            "id": w[0],
            "name": w[1],
            "rarity": w[2],
            "image_url": w[3],
            "front_view": w[4],
            "back_view": w[5],
            "side_view": w[6],
            "animated_view": w[7],
            "count": w[8],
            "gc_price": w[9],
            "diamond_price": w[10]
        })
        
    return web.json_response({
        "status": "success",
        "profile": {
            "username": user[0],
            "balance_gc": user[1],
            "diamonds": user[2]
        },
        "waifus": waifus_list
    })

async def web_server():
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

    app = web.Application(middlewares=[cors_middleware])
    app.router.add_get("/", handle_home)
    app.router.add_get("/api/settings", handle_api_settings)
    app.router.add_get("/api/user", handle_api_user_profile)
    
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    await db_start()
    print("🚀 GrabCharakter Bot va Mini App Server muvaffaqiyatli ishga tushdi!")
    await asyncio.gather(
        web_server(),
        dp.start_polling(bot, drop_pending_updates=True)
    )

# ==========================================
# 📢 REKLAMA VA VAZIFALAR (REWARDED ADS) TIZIMI
# ==========================================
@dp.callback_query(F.data == "admin_add_ad")
async def admin_add_ad_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS: return
    await state.set_state(AddAdState.media)
    await call.message.edit_text("📢 Reklama uchun video yoki rasm yuboring:")
    await call.answer()

@dp.message(AddAdState.media)
async def admin_add_ad_media(message: types.Message, state: FSMContext):
    media_id = message.video.file_id if message.video else message.photo[-1].file_id
    await state.update_data(media_id=media_id)
    await state.set_state(AddAdState.reward)
    await message.answer("💰 Ushbu reklamani ko'rgani uchun beriladigan GC (tanga) miqdorini kiriting (faqat raqam):")

@dp.message(AddAdState.reward)
async def admin_add_ad_save(message: types.Message, state: FSMContext):
    data = await state.get_data()
    reward = int(message.text)
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO tasks (title, url, reward_gc) VALUES (?, ?, ?)", ("Reklama ko'rish", data['media_id'], reward))
        await db.commit()
    await state.clear()
    await message.answer("✅ Reklama bazaga qo'shildi va foydalanuvchilarga ko'rinishni boshladi!")

# ==========================================
# 🚀 24/7 XAVFSIZ ISHGA TUSHIRISH BLOKI
# ==========================================
if __name__ == '__main__':
    try:
        print("==========================================")
        print("🌟 GRABCHARAKTER BOT & MINI APP STARTING 24/7...")
        print("⚙️ Loading configuration and database...")
        print("🚀 Bot is running successfully!")
        print("==========================================")
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("🛑 Bot manually stopped.")
    except Exception as e:
        logging.error(f"Critical error occurred while running bot: {e}")
        
