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

# Bot tokeningiz va Admin ID
TOKEN = "8987164421:AAGynHKb4lN8jtGNSkCPHmqqeDR7N555DTc"
ADMIN_ID = 7986354170,7637155944

# Havolalar va Bot username
BOT_USERNAME = "AniREM_bot"  # Botingizning username'ini yozing
NEWS_CHANNEL_URL = "https://t.me/GRAB_GARDEN_NEWS"
GROUP_CHAT_URL = "https://t.me/Grab_Garden"

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
# 1. /start VA ASOSIY MENYU
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
            
    # Asosiy menyu (Guruhga qo'shish tugmasi qo'shildi)
    markup_rows = [
        [InlineKeyboardButton(text="➕ Botni guruhga qo'shish", url=f"https://t.me/{BOT_USERNAME}?startgroup=true")],
        [InlineKeyboardButton(text="🎒 Mening kolleksiyam", callback_data="my_collection")],
        [InlineKeyboardButton(text="📢 Yangiliklar kanali", url=NEWS_CHANNEL_URL)],
        [InlineKeyboardButton(text="👥 Asosiy guruh", url=GROUP_CHAT_URL)]
    ]
    
    # Faqat admin uchun
    if user_id == ADMIN_ID:
        markup_rows.insert(0, [InlineKeyboardButton(text="👑 Admin Panel", callback_data="admin_panel_main")])

    markup = InlineKeyboardMarkup(inline_keyboard=markup_rows)
    
    text = (
        f"🌸 Salom, **{message.from_user.first_name}**!\n\n"
        "Botanika xush kelibsiz! **Grab Garden** — anime qahramonlarini yig'ish, guruhlarda ov qilish va o'z bazangizni boyitish uchun eng yaxshi maskan.\n\n"
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
        
    collection_text = "🎒 **Sizning Qahramonlar Kolleksiyangiz:**\n\n"
    for idx, (name, rarity) in enumerate(rows, 1):
        collection_text += f"{idx}. {name} — {rarity}\n"
        
    await call.message.edit_text(collection_text, reply_markup=markup, parse_mode="Markdown")
    await call.answer()

@dp.callback_query(F.data == "back_home")
async def process_home(call: types.CallbackQuery):
    user_id = call.from_user.id
    markup_rows = [
        [InlineKeyboardButton(text="➕ Botni guruhga qo'shish", url=f"https://t.me/{BOT_USERNAME}?startgroup=true")],
        [InlineKeyboardButton(text="🎒 Mening kolleksiyam", callback_data="my_collection")],
        [InlineKeyboardButton(text="📢 Yangiliklar kanali", url=NEWS_CHANNEL_URL)],
        [InlineKeyboardButton(text="👥 Asosiy guruh", url=GROUP_CHAT_URL)]
    ]
    if user_id == ADMIN_ID:
        markup_rows.insert(0, [InlineKeyboardButton(text="👑 Admin Panel", callback_data="admin_panel_main")])
        
    markup = InlineKeyboardMarkup(inline_keyboard=markup_rows)
    await call.message.edit_text("🌸 **Asosiy Menyu:**", reply_markup=markup, parse_mode="Markdown")
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
                    f"✨ **Grab Garden | Diqqat! Yangi qahramon paydo bo'ldi!**\n\n"
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
# 3. KENGAYTIRILGAN ADMIN PANEL (FAQAT SIZ UCHUN)
# ==========================================
@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
        
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            users_count = (await cursor.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM waifus") as cursor:
            waifus_count = (await cursor.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM group_messages") as cursor:
            groups_count = (await cursor.fetchone())[0]
            
    text = (
        f"👑 **Admin Boshqaruv Paneli:**\n\n"
        f"👥 Jami foydalanuvchilar: **{users_count}** ta\n"
        f"✨ Bazadagi qahramonlar: **{waifus_count}** ta\n"
        f"💬 Faol guruhlar soni: **{groups_count}** ta\n\n"
        f"Kerakli bo'limni tanlang:"
    )
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Qahramon qo'shish", callback_data="admin_add_waifu")],
        [InlineKeyboardButton(text="📋 Qahramonlar ro'yxati", callback_data="admin_list_waifus")],
        [InlineKeyboardButton(text="📢 Reklama tarqatish (Rassilka)", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="« Asosiy menyu", callback_data="back_home")]
    ])
    await message.answer(text, reply_markup=markup, parse_mode="Markdown")

@dp.callback_query(F.data == "admin_panel_main")
async def admin_panel_callback(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
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
        f"👑 **Admin Boshqaruv Paneli:**\n\n"
        f"👥 Jami foydalanuvchilar: **{users_count}** ta\n"
        f"✨ Bazadagi qahramonlar: **{waifus_count}** ta\n"
        f"💬 Faol guruhlar soni: **{groups_count}** ta\n\n"
        f"Kerakli bo'limni tanlang:"
    )
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Qahramon qo'shish", callback_data="admin_add_waifu")],
        [InlineKeyboardButton(text="📋 Qahramonlar ro'yxati", callback_data="admin_list_waifus")],
        [InlineKeyboardButton(text="📢 Reklama tarqatish (Rassilka)", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="« Asosiy menyu", callback_data="back_home")]
    ])
    await call.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
    await call.answer()

@dp.callback_query(F.data == "admin_add_waifu")
async def admin_add_waifu_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    await state.set_state(AddWaifuState.waiting_for_name)
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_panel_main")]])
    await call.message.edit_text("📝 Yangi qahramonning **ismini** kiriting:", reply_markup=markup)
    await call.answer()

@dp.message(AddWaifuState.waiting_for_name)
async def process_waifu_name(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.update_data(name=message.text)
    await state.set_state(AddWaifuState.waiting_for_rarity)
    await message.answer("✨ Qahramonning **darajasini** kiriting (masalan: *🌟 2 Yulduzcha*):")

@dp.message(AddWaifuState.waiting_for_rarity)
async def process_waifu_rarity(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.update_data(rarity=message.text)
    await state.set_state(AddWaifuState.waiting_for_image)
    await message.answer("🖼 Qahramonning **rasm havolasini (URL)** yuboring (masalan: *https://i.imgur.com/...*):")

@dp.message(AddWaifuState.waiting_for_image)
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
        
    await state.clear()
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="👑 Admin Panelga qaytish", callback_data="admin_panel_main")]])
    await message.answer(f"✅ Qahramon muvaffaqiyatli qo'shildi!\n\n👤 Ismi: {name}\n✨ Darajasi: {rarity}\n🖼 Rasm: {image_url}", reply_markup=markup)

@dp.callback_query(F.data == "admin_list_waifus")
async def admin_list_waifus(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
        
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT id, name, rarity FROM waifus") as cursor:
            waifus = await cursor.fetchall()
            
    text = "📋 **Bazadagi barcha qahramonlar:**\n\n"
    for w_id, w_name, w_rarity in waifus:
        text += f"ID: {w_id} | {w_name} — {w_rarity}\n"
        
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="« Admin Panelga qaytish", callback_data="admin_panel_main")]
    ])
    await call.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
    await call.answer()

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    await state.set_state(BroadcastState.waiting_for_message)
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_panel_main")]])
    await call.message.edit_text("📢 Barcha foydalanuvchilarga yubormoqchi bo'lgan **xabaringizni yuboring**:", reply_markup=markup)
    await call.answer()

@dp.message(BroadcastState.waiting_for_message)
async def process_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
        
    await state.clear()
    sent_count = 0
    fail_count = 0
    
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id FROM users") as cursor:
            users = await cursor.fetchall()
            
    status_msg = await message.answer("⏳ Reklama tarqatish boshlandi...")
    
    for (uid,) in users:
        try:
            await message.send_copy(chat_id=uid)
            sent_count += 1
            await asyncio.sleep(0.05)
        except:
            fail_count += 1
            
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="👑 Admin Panelga qaytish", callback_data="admin_panel_main")]])
    await status_msg.edit_text(f"✅ **Reklama tarqatish yakunlandi!**\n\n📤 Muvaffaqiyatli: {sent_count} ta\n❌ Xatolik: {fail_count} ta", reply_markup=markup, parse_mode="Markdown")

async def main():
    await db_start()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
    
