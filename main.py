# --- 1-QISM: KUTUBXONALAR, BAZA SXEMASI VA ASOSIY SOZLAMALAR ---
import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web
import aiosqlite

# Loglar sozlamasi
logging.basicConfig(level=logging.INFO)
BOT_TOKEN = "SIZNING_BOT_TOKENINGIZ"
WEBAPP_URL = "https://aniken-bot-1.onrender.com"
DB_NAME = "grab_character.db"
ADMIN_IDS = [123456789]  # Admin ID'lar ro'yxati

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Bazani ishga tushirish va jadvallarni yaratish
async def db_start():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance_gc INTEGER DEFAULT 0,
                diamonds INTEGER DEFAULT 0,
                ref_count INTEGER DEFAULT 0,
                is_banned INTEGER DEFAULT 0,
                registration_date DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS waifus (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                anime_name TEXT,
                description TEXT,
                rarity TEXT,
                gc_price INTEGER,
                diamond_price INTEGER,
                l1_img TEXT, l1_proj TEXT,
                l2_img TEXT, l2_proj TEXT,
                l3_img TEXT, l3_proj TEXT,
                l4_img TEXT, l4_proj TEXT,
                l5_img TEXT, l5_proj TEXT,
                l6_img TEXT, l6_proj TEXT,
                team_view TEXT,
                is_active INTEGER DEFAULT 1,
                drop_rate REAL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_waifus (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                waifu_id INTEGER,
                level INTEGER DEFAULT 1,
                count INTEGER DEFAULT 1,
                FOREIGN KEY(user_id) REFERENCES users(user_id),
                FOREIGN KEY(waifu_id) REFERENCES waifus(id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS promo_codes (
                code TEXT PRIMARY KEY,
                reward_type TEXT,
                reward_value INTEGER,
                max_uses INTEGER,
                uses_count INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS daily_rewards (
                day_number INTEGER PRIMARY KEY,
                reward_type TEXT,
                reward_amount INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_dailies (
                user_id INTEGER,
                last_claim_date TEXT,
                current_streak INTEGER,
                PRIMARY KEY(user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sound_settings (
                action TEXT PRIMARY KEY,
                file_id TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS friends_link (
                user1_id INTEGER,
                user2_id INTEGER,
                relation_type TEXT,
                PRIMARY KEY(user1_id, user2_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS task_rewards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_link TEXT,
                reward_amount INTEGER,
                is_active INTEGER DEFAULT 1
            )
        """)
        await db.commit()

# Holatlar mashinasi (FSM States)
class BroadcastState(StatesGroup):
    waiting_for_message = State()

class DesignSettingsState(StatesGroup):
    bg_image = State()

class WaifuCreationState(StatesGroup):
    waiting_for_name = State()
    waiting_for_anime = State()
    waiting_for_desc = State()
    waiting_for_rarity = State()
    waiting_for_prices = State()
    waiting_for_media = State()

# --- 2-QISM: PERSONAJ QO'SHISH (FSM) VA OVOZ SOZLAMALARI ---

class WaifuAddSequenceState(StatesGroup):
    waiting_for_name = State()
    waiting_for_anime = State()
    waiting_for_desc = State()
    waiting_for_rarity = State()
    waiting_for_gc_price = State()
    waiting_for_diamond_price = State()
    waiting_for_ad_info = State()
    # L1 dan L6 gacha ketma-ket rasm va proeksiya yuklash holatlari
    waiting_for_l1_img = State()
    waiting_for_l1_proj = State()
    waiting_for_l2_img = State()
    waiting_for_l2_proj = State()
    waiting_for_l3_img = State()
    waiting_for_l3_proj = State()
    waiting_for_l4_img = State()
    waiting_for_l4_proj = State()
    waiting_for_l5_img = State()
    waiting_for_l5_proj = State()
    waiting_for_l6_img = State()
    waiting_for_l6_proj = State()

class SoundSettingsState(StatesGroup):
    waiting_for_sound = State()

# Admin uchun ovoz yuklash va sozlash handlerlari
@dp.message(F.text == "🔊 Ovoz sozlash (Admin)")
async def admin_sound_menu(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer(
        "🔊 **Ovoz sozlamalari**\n\n"
        "Tugmalar va tanga bosilganda chiqadigan 'ting-ting', 'piq' kabi tovush effektini o'rnatish uchun audio fayl yoki ovozli xabar yuboring:"
    )
    await state.set_state(SoundSettingsState.waiting_for_sound)

@dp.message(SoundSettingsState.waiting_for_sound, F.audio | F.voice)
async def save_sound_file(message: types.Message, state: FSMContext):
    file_id = message.audio.file_id if message.audio else message.voice.file_id
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO sound_settings (action, file_id) VALUES ('click', ?)", (file_id,))
        await db.commit()
    await message.answer("✅ Tovush muvaffaqiyatli saqlandi! Endi barcha bosishlarda shu ovoz ishlatiladi.")
    await state.clear()

# Yangi personaj qo'shishni boshlash (Admin uchun)
@dp.message(F.text == "➕ Yangi personaj qo'shish")
async def start_adding_waifu(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("Personaj qo'shish jarayoni boshlandi.\n\n1️⃣ Personajning **ismini** kiriting:")
    await state.set_state(WaifuAddSequenceState.waiting_for_name)

@dp.message(WaifuAddSequenceState.waiting_for_name)
async def process_waifu_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("2️⃣ Qaysi **animedan** ekanligini kiriting:")
    await state.set_state(WaifuAddSequenceState.waiting_for_anime)

@dp.message(WaifuAddSequenceState.waiting_for_anime)
async def process_waifu_anime(message: types.Message, state: FSMContext):
    await state.update_data(anime=message.text)
    await message.answer("3️⃣ Personaj haqida **ma'lumot (tavsif)** kiriting:")
    await state.set_state(WaifuAddSequenceState.waiting_for_desc)

@dp.message(WaifuAddSequenceState.waiting_for_desc)
async def process_waifu_desc(message: types.Message, state: FSMContext):
    await state.update_data(desc=message.text)
    await message.answer("4️⃣ **Rarity (darajasi/kamyobligi)** ni kiriting (masalan: Epic, Legendary):")
    await state.set_state(WaifuAddSequenceState.waiting_for_rarity)

@dp.message(WaifuAddSequenceState.waiting_for_rarity)
async def process_waifu_rarity(message: types.Message, state: FSMContext):
    await state.update_data(rarity=message.text)
    await message.answer("5️⃣ Sotuv narxini **GameCoin (tangada)** kiriting (faqat raqam):")
    await state.set_state(WaifuAddSequenceState.waiting_for_gc_price)

@dp.message(WaifuAddSequenceState.waiting_for_gc_price)
async def process_waifu_gc_price(message: types.Message, state: FSMContext):
    await state.update_data(gc_price=message.text)
    await message.answer("6️⃣ Sotuv narxini **Olmosda** kiriting (faqat raqam):")
    await state.set_state(WaifuAddSequenceState.waiting_for_diamond_price)

@dp.message(WaifuAddSequenceState.waiting_for_diamond_price)
async def process_waifu_diamond_price(message: types.Message, state: FSMContext):
    await state.update_data(diamond_price=message.text)
    await message.answer("7️⃣ Guruh va kanallarga **reklama berishlik** haqidagi ma'lumotlarni kiriting:")
    await state.set_state(WaifuAddSequenceState.waiting_for_ad_info)

@dp.message(WaifuAddSequenceState.waiting_for_ad_info)
async def process_waifu_ad_info(message: types.Message, state: FSMContext):
    await state.update_data(ad_info=message.text)
    await message.answer("✅ Umumiy ma'lumotlar qabul qilindi!\n\nEndi bosqichma-bosqich rasmlar va proeksiyalarni kiriting:\n\n📸 1-darajali personajning **rasmini** yuboring:")
    await state.set_state(WaifuAddSequenceState.waiting_for_l1_img)
# --- 3-QISM: KETMA-KET DARAJALAR, ONBOARDING VA NAVIGATSIYA ---

@dp.message(WaifuAddSequenceState.waiting_for_l1_img, F.photo)
async def process_l1_img(message: types.Message, state: FSMContext):
    await state.update_data(l1_img=message.photo[-1].file_id)
    await message.answer("🖼️ 1-darajali personajning **proyeksiyasini** yuboring:")
    await state.set_state(WaifuAddSequenceState.waiting_for_l1_proj)

@dp.message(WaifuAddSequenceState.waiting_for_l1_proj, F.photo)
async def process_l1_proj(message: types.Message, state: FSMContext):
    await state.update_data(l1_proj=message.photo[-1].file_id)
    await message.answer("📸 Ajoyib! Endi avtomatik ravishda **2-darajali personajning rasmini** kiriting:")
    await state.set_state(WaifuAddSequenceState.waiting_for_l2_img)

@dp.message(WaifuAddSequenceState.waiting_for_l2_img, F.photo)
async def process_l2_img(message: types.Message, state: FSMContext):
    await state.update_data(l2_img=message.photo[-1].file_id)
    await message.answer("🖼️ 2-darajali personajning **proyeksiyasini** yuboring:")
    await state.set_state(WaifuAddSequenceState.waiting_for_l2_proj)

@dp.message(WaifuAddSequenceState.waiting_for_l2_proj, F.photo)
async def process_l2_proj(message: types.Message, state: FSMContext):
    await state.update_data(l2_proj=message.photo[-1].file_id)
    await message.answer("📸 Navbatdagisi: **3-darajali personajning rasmini** kiriting:")
    await state.set_state(WaifuAddSequenceState.waiting_for_l3_img)

@dp.message(WaifuAddSequenceState.waiting_for_l3_img, F.photo)
async def process_l3_img(message: types.Message, state: FSMContext):
    await state.update_data(l3_img=message.photo[-1].file_id)
    await message.answer("🖼️ 3-darajali personajning **proyeksiyasini** yuboring:")
    await state.set_state(WaifuAddSequenceState.waiting_for_l3_proj)

@dp.message(WaifuAddSequenceState.waiting_for_l3_proj, F.photo)
async def process_l3_proj(message: types.Message, state: FSMContext):
    await state.update_data(l3_proj=message.photo[-1].file_id)
    await message.answer("📸 Navbatdagisi: **4-darajali personajning rasmini** kiriting:")
    await state.set_state(WaifuAddSequenceState.waiting_for_l4_img)

@dp.message(WaifuAddSequenceState.waiting_for_l4_img, F.photo)
async def process_l4_img(message: types.Message, state: FSMContext):
    await state.update_data(l4_img=message.photo[-1].file_id)
    await message.answer("🖼️ 4-darajali personajning **proyeksiyasini** yuboring:")
    await state.set_state(WaifuAddSequenceState.waiting_for_l4_proj)

@dp.message(WaifuAddSequenceState.waiting_for_l4_proj, F.photo)
async def process_l4_proj(message: types.Message, state: FSMContext):
    await state.update_data(l4_proj=message.photo[-1].file_id)
    await message.answer("📸 Navbatdagisi: **5-darajali personajning rasmini** kiriting:")
    await state.set_state(WaifuAddSequenceState.waiting_for_l5_img)

@dp.message(WaifuAddSequenceState.waiting_for_l5_img, F.photo)
async def process_l5_img(message: types.Message, state: FSMContext):
    await state.update_data(l5_img=message.photo[-1].file_id)
    await message.answer("🖼️ 5-darajali personajning **proyeksiyasini** yuboring:")
    await state.set_state(WaifuAddSequenceState.waiting_for_l5_proj)

@dp.message(WaifuAddSequenceState.waiting_for_l5_proj, F.photo)
async def process_l5_proj(message: types.Message, state: FSMContext):
    await state.update_data(l5_proj=message.photo[-1].file_id)
    await message.answer("📸 Oxirgisi: **6-darajali personajning rasmini** kiriting:")
    await state.set_state(WaifuAddSequenceState.waiting_for_l6_img)

@dp.message(WaifuAddSequenceState.waiting_for_l6_img, F.photo)
async def process_l6_img(message: types.Message, state: FSMContext):
    await state.update_data(l6_img=message.photo[-1].file_id)
    await message.answer("🖼️ 6-darajali personajning oxirgi **proyeksiyasini** yuboring:")
    await state.set_state(WaifuAddSequenceState.waiting_for_l6_proj)

@dp.message(WaifuAddSequenceState.waiting_for_l6_proj, F.photo)
async def process_l6_proj(message: types.Message, state: FSMContext, state_data=None):
    data = await state.get_data()
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT INTO waifus (name, anime_name, description, rarity, gc_price, diamond_price, 
                               l1_img, l1_proj, l2_img, l2_proj, l3_img, l3_proj, 
                               l4_img, l4_proj, l5_img, l5_proj, l6_img, l6_proj, team_view)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data['name'], data['anime'], data['desc'], data['rarity'], 
            int(data['gc_price']), int(data['diamond_price']),
            data['l1_img'], data['l1_proj'], data['l2_img'], data['l2_proj'],
            data['l3_img'], data['l3_proj'], data['l4_img'], data['l4_proj'],
            data['l5_img'], data['l5_proj'], message.photo[-1].file_id, data['l6_proj']
        ))
        await db.commit()
    await message.answer("🎉 Personaj barcha 6 ta darajasi va ma'lumotlari bilan bazaga muvaffaqiyatli qo'shildi!")
    await state.clear()


# --- YANGI FOYDALANUVCHILAR UCHUN ONBOARDING (O'QITISH) ---

@dp.message(F.text == "/start")
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user = await cursor.fetchone()
        
        if not user:
            await db.execute("INSERT INTO users (user_id, username, balance_gc) VALUES (?, ?, ?)",
                             (user_id, message.from_user.username, 100))
            await db.commit()
            
            # Faqat shu maxsus tugma bosilishi shart bo'lgan birinchi qadam
            keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="👆 Mana bu sening profiling (Bos!)", callback_data="onboard_profile")]
            ])
            await message.answer(
                "👋 Botimizga xush kelibsiz!\n\n"
                "💡 **O'qitish (Onboarding)**:\n"
                "Bu yerda boshqa joylarga bosib bo'lmaydi. Faqat ko'rsatilgan qismni bosib davom etasiz.\n\n"
                "Marhamat, tepadagi profilingiz haqidagi bo'limni bosing:",
                reply_markup=keyboard
            )
        else:
            kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="🎮 O'yinni ochish (Mini App)", web_app=types.WebAppInfo(url=WEBAPP_URL))]
            ])
            await message.answer("Asosiy menyuga xush kelibsiz!", reply_markup=kb)

@dp.callback_query(F.data == "onboard_profile")
async def onboarding_profile(callback: types.CallbackQuery):
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="➡️ Keyingi (Personajlar)", callback_data="onboard_waifus")]
    ])
    await callback.message.edit_text(
        "👤 **Sening profiling**:\n"
        "Mana bu yerda sening yig'gan tangalaring, olmoslaring va umumiy darajang ko'rsatiladi.\n\n"
        "Ekranning xohlagan joyiga emas, faqat shu tugmani bosib keyingisiga o'tamiz:",
        reply_markup=keyboard
    )
    await callback.answer()

@dp.callback_query(F.data == "onboard_waifus")
async def onboarding_waifus(callback: types.CallbackQuery):
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="➡️ Tanga bosishga o'tish", callback_data="onboard_coins")]
    ])
    await callback.message.edit_text(
        "🖼️ **Personajlar bo'limi**:\n"
        "Mana bu yerga sen o'zingning personajingni qo'ysang bo'ladi va ularni rivojlantirasan.\n\n"
        "Davom etish uchun bosing:",
        reply_markup=keyboard
    )
    await callback.answer()

@dp.callback_query(F.data == "onboard_coins")
async def onboarding_coins(callback: types.CallbackQuery):
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🪙 Tanga bosish (+1)", callback_data="tap_coin_tutorial")],
        [types.InlineKeyboardButton(text="🔙 Orqaga", callback_data="onboard_waifus"),
         types.InlineKeyboardButton(text="✅ Tugatish", callback_data="onboard_finish")]
    ])
    await callback.message.edit_text(
        "🪙 **Tanga ishlash va limit**:\n"
        "Katta tangani 2-3 marta bosib ko'ring, so'ngra bir kunlik limitni olish uchun mo'ljallangan joyga kirasiz.",
        reply_markup=kb
    )
    await callback.answer()

@dp.callback_query(F.data == "tap_coin_tutorial")
async def tap_coin_tut(callback: types.CallbackQuery):
    await callback.answer("+1 Tanga qo'shildi! 🪙 (Ting-ting!)", show_alert=False)

@dp.callback_query(F.data == "onboard_finish")
async def onboarding_finish(callback: types.CallbackQuery):
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🎮 Mini App O'yinni Ochish", web_app=types.WebAppInfo(url=WEBAPP_URL))]
    ])
    await callback.message.edit_text(
        "🎉 Tabriklayman! Boshlang'ich yo'riqnomadan o'tdingiz. Endi asosiy menyuga qaytdingiz va o'yinga kirishingiz mumkin!",
        reply_markup=kb
    )
    await callback.answer()

# --- 4-QISM: MINI APP WEBSERVER VA FRONTEND INTERFEYS ---

async def handle_webapp(request):
    html_content = """
    <!DOCTYPE html>
    <html lang="uz">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Grab Character Mini App</title>
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            :root {
                --bg-glass: rgba(255, 255, 255, 0.1);
                --border-glass: rgba(255, 255, 255, 0.2);
                --text-color: #ffffff;
            }
            body {
                margin: 0;
                padding: 0;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #1a1a2e, #16213e, #0f3460);
                color: var(--text-color);
                height: 100vh;
                display: flex;
                flex-direction: column;
                overflow: hidden;
            }
            /* Yuqori chap burchakdagi doimiy orqaga qaytish tugmasi */
            .back-btn {
                position: absolute;
                top: 10px;
                left: 10px;
                background: var(--bg-glass);
                border: 1px solid var(--border-glass);
                padding: 8px 14px;
                border-radius: 12px;
                color: #fff;
                cursor: pointer;
                backdrop-filter: blur(10px);
                z-index: 100;
                font-weight: bold;
                transition: 0.2s;
            }
            .back-btn:active {
                transform: scale(0.95);
            }
            .main-container {
                display: flex;
                flex: 1;
                margin-top: 55px;
                padding: 10px;
                gap: 10px;
                box-sizing: border-box;
            }
            /* Chap taraf: Proeksiya */
            .left-projection {
                flex: 1;
                background: var(--bg-glass);
                border: 1px solid var(--border-glass);
                border-radius: 20px;
                backdrop-filter: blur(15px);
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
                position: relative;
                padding: 10px;
                text-align: center;
            }
            /* O'ng taraf: Personajlar ro'yxati (yuqoridan pastga juda ko'p) */
            .right-characters {
                flex: 1;
                background: var(--bg-glass);
                border: 1px solid var(--border-glass);
                border-radius: 20px;
                backdrop-filter: blur(15px);
                overflow-y: auto;
                padding: 10px;
                display: flex;
                flex-direction: column;
                gap: 10px;
                box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
            }
            .char-card {
                background: rgba(255, 255, 255, 0.05);
                padding: 12px;
                border-radius: 12px;
                border: 1px solid rgba(255, 255, 255, 0.1);
                text-align: center;
                cursor: pointer;
                transition: 0.2s;
            }
            .char-card:hover {
                background: rgba(255, 255, 255, 0.15);
            }
            /* Eng pastda: Sotuv va reklama qilingan yangi personajlar bo'limi (asosiy bo'limdan yuqorida, aralashmagan) */
            .bottom-market {
                height: 110px;
                background: var(--bg-glass);
                border-top: 1px solid var(--border-glass);
                backdrop-filter: blur(15px);
                display: flex;
                align-items: center;
                overflow-x: auto;
                padding: 10px;
                gap: 12px;
                box-sizing: border-box;
            }
            .market-item {
                min-width: 85px;
                height: 100%;
                background: rgba(255, 255, 255, 0.12);
                border-radius: 12px;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                border: 1px solid rgba(255, 255, 255, 0.25);
                cursor: pointer;
                font-size: 12px;
                font-weight: bold;
                text-align: center;
                flex-shrink: 0;
            }
        </style>
    </head>
    <body>
        <!-- Chap yuqori burchakdagi orqaga qaytish tugmasi -->
        <button class="back-btn" onclick="goBack()">← Orqaga</button>
        
        <div class="main-container">
            <!-- Chap taraf: Proeksiya -->
            <div class="left-projection">
                <h3>Proeksiya</h3>
                <p>Character oyog'i tagidagi zona</p>
            </div>
            
            <!-- O'ng taraf: Barcha personajlar ro'yxati (yuqoridan pastga) -->
            <div class="right-characters">
                <h3>Mening Personajlarim</h3>
                <div class="char-card">Miku Nakano (L1)</div>
                <div class="char-card">Character 2 (L2)</div>
                <div class="char-card">Character 3 (L1)</div>
                <div class="char-card">Character 4 (L3)</div>
                <div class="char-card">Character 5 (L4)</div>
            </div>
        </div>

        <!-- Eng pastdagi sotuv va yangi personajlar reklamasi bo'limi -->
        <div class="bottom-market">
            <div class="market-item">🔥 Yangi 1<br><small>150 🪙</small></div>
            <div class="market-item">✨ Yangi 2<br><small>300 🪙</small></div>
            <div class="market-item">💎 Yangi 3<br><small>50 💎</small></div>
            <div class="market-item">🌟 Yangi 4<br><small>500 🪙</small></div>
        </div>

        <script>
            let tg = window.Telegram.WebApp;
            tg.expand();

            function playClickSound() {
                // Har bir bosganda chiqadigan maxsus tovush (ting-ting / piq)
                let audio = new Audio('https://actions.google.com/sounds/v1/ui/button_click.ogg');
                audio.play().catch(e => console.log(e));
            }

            function goBack() {
                playClickSound();
                window.history.back();
            }

            // Sahifadagi istalgan joyga/tugmaga bosganda tovush chiqarish
            document.addEventListener('click', () => {
                playClickSound();
            });
        </script>
    </body>
    </html>
    """
    return web.Response(text=html_content, content_type='text/html')

# Bot va Serverni ishga tushiruvchi asosiy qism
async def main():
    await db_start()
    app = web.Application()
    app.router.add_get('/', handle_webapp)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    
    print("Mini App Server muvaffaqiyatli ishga tushdi: http://0.0.0.0:8080")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
  
