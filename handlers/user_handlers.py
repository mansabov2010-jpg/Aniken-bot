from aiogram import types, Dispatcher
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3

DATABASE = 'bot_database.db'

async def send_welcome(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    full_name = message.from_user.full_name
    
    db = sqlite3.connect(DATABASE)
    cursor = db.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, full_name, diamonds) VALUES (?, ?, ?, ?)",
                   (user_id, username, full_name, 100))
    db.commit()
    db.close()
    
    keyboard = InlineKeyboardMarkup()
    web_app = WebAppInfo(url="https://domen.uz/app")
    keyboard.add(InlineKeyboardButton("🌸 Grab Garden'ni ochish", web_app=web_app))
    
    await message.answer("Xush kelibsiz! Mini-ilovaga kiring:", reply_markup=keyboard)

def register_handlers(dp: Dispatcher):
    dp.register_message_handler(send_welcome, commands=['start'])
    
