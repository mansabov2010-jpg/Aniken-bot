import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage

# Logging sozlamalari
logging.basicConfig(level=logging.INFO)

# Token va Admin ID (o'zingizning ma'lumotlaringizni kiriting)
TOKEN = "YOUR_BOT_TOKEN_HERE"
ADMIN_IDS = [123456789]  # Adminlar ID ro'yxati

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Ma'lumotlar bazasini yaratish va sozlash
def init_db():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    
    # Foydalanuvchilar jadvali
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            age INTEGER,
            location TEXT,
            bio TEXT,
            coins INTEGER DEFAULT 0,
            stars INTEGER DEFAULT 0,
            message_count INTEGER DEFAULT 0,
            last_bonus_date TEXT,
            bonus_streak INTEGER DEFAULT 0
        )
    ''')
    
    # Xarakterlar jadvali
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS characters (
            char_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            level INTEGER,
            image_url TEXT,
            price INTEGER,
            is_new INTEGER DEFAULT 1
        )
    ''')
    
    # Foydalanuvchiga tegishli xarakterlar
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            char_id INTEGER,
            count INTEGER DEFAULT 1,
            equipped_slot INTEGER DEFAULT 0
        )
    ''')
    
    # Do'stlar / Bog'langan profillar
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS friendships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id_1 INTEGER,
            user_id_2 INTEGER,
            status TEXT DEFAULT 'pending', -- pending, accepted
            relation_type TEXT DEFAULT 'friend' -- friend, couple, best_friend
        )
    ''')

    # Admin vazifalari va kanallar/guruhlar jadvali
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            task_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            url TEXT,
            reward INTEGER,
            task_type TEXT -- channel, group, video
        )
    ''')

    conn.commit()
    conn.close()

async def main():
    init_db()
    logging.info("Ma'lumotlar bazasi muvaffaqiyatli ishga tushdi.")
    
    # Routerni ulash va ishga tushirish
    from handlers import register_handlers
    register_handlers(dp)
    
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
    
