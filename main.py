from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from flask import Flask, render_template, request, redirect, g
import sqlite3
from handlers.user_handlers import register_handlers
import threading
import os

API_TOKEN = '9111857366:AAFwGLEkXzTvaFzLB01aHtDeM4JzoEsDO_4'
ADMIN_IDS = [7986354170, 7637155944]  # Boshlang'ich adminlar

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

register_handlers(dp)

app = Flask(__name__)
app.secret_key = 'secret_key'
DATABASE = 'bot_database.db'

@app.route('/')
def home():
    return redirect('/app')

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# Bazada adminlar jadvali yo'q bo'lsa yaratish va bosh adminlarni qo'shish
def init_admins_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY
        )
    ''')
    for admin_id in ADMIN_IDS:
        cursor.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (admin_id,))
    conn.commit()
    conn.close()

init_admins_db()

# Telegram orqali yangi admin qo'shish buyrug'i: /addadmin <user_id>
@dp.message_handler(commands=['addadmin'])
async def add_admin_command(message: types.Message):
    user_id = message.from_user.id
    
    # Faqat mavjud adminlar yangi admin qo'sha oladi
    db = sqlite3.connect(DATABASE)
    cursor = db.cursor()
    cursor.execute("SELECT user_id FROM admins WHERE user_id = ?", (user_id,))
    is_admin = cursor.fetchone()
    
    if not is_admin:
        db.close()
        await message.answer("Kechirasiz, bu buyruqni faqat adminlar ishlata oladi.")
        return
        
    args = message.get_args()
    if not args.isdigit():
        db.close()
        await message.answer("Noto'g'ri format! Ishlatish: /addadmin <Telegram_User_ID>")
        return
        
    new_admin_id = int(args)
    cursor.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (new_admin_id,))
    db.commit()
    db.close()
    
    await message.answer(f"Muvaffaqiyatli! {new_admin_id} ID raqamli foydalanuvchi admin qilindi.")

@app.route('/app')
def web_app():
    return render_template('index.html')

@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    db = get_db()
    cursor = db.cursor()
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'update_settings':
            for key, value in request.form.items():
                if key != 'action':
                    cursor.execute("INSERT OR REPLACE INTO admin_settings (key, value) VALUES (?, ?)", (key, value))
            db.commit()
            
        elif action == 'approve_item':
            item_id = request.form.get('item_id')
            price = request.form.get('price', 10)
            cursor.execute("UPDATE marketplace SET status = 'active', price = ? WHERE id = ?", (price, item_id))
            db.commit()
            
        elif action == 'reject_item':
            item_id = request.form.get('item_id')
            cursor.execute("DELETE FROM marketplace WHERE id = ?", (item_id,))
            db.commit()
            
        return redirect('/admin')
        
    cursor.execute("SELECT * FROM admin_settings")
    settings = {row['key']: row['value'] for row in cursor.fetchall()}
    
    cursor.execute("SELECT * FROM marketplace WHERE status = 'pending'")
    pending_items = cursor.fetchall()
    
    pending_html = ""
    for item in pending_items:
        pending_html += f"""
        <div style="border: 1px solid #ccc; padding: 10px; margin-bottom: 10px;">
            <p>Xarakter: <b>{item['char_name']}</b> (Sotuvchi ID: {item['seller_id']})</p>
            <form method='POST' style="display:inline;">
                <input type='hidden' name='action' value='approve_item'>
                <input type='hidden' name='item_id' value='{item['id']}'>
                Narx (Diamond): <input type='text' name='price' value='50' style='width: 60px;'>
                <button type='submit' style='background:green; color:white;'>Tasdiqlash</button>
            </form>
            <form method='POST' style="display:inline; margin-left: 10px;">
                <input type='hidden' name='action' value='reject_item'>
                <input type='hidden' name='item_id' value='{item['id']}'>
                <button type='submit' style='background:red; color:white;'>Rad etish</button>
            </form>
        </div>
        """
        
    if not pending_html:
        pending_html = "<p>Hozircha moderatsiyadagi e'lonlar yo'q.</p>"
    
    return f"""
    <h2>👑 Grab Garden Admin Paneli</h2>
    <h3>Bot Sozlamalari</h3>
    <form method='POST'>
        <input type='hidden' name='action' value='update_settings'>
        E'lon berish narxi (Stars): <input type='text' name='listing_fee_stars' value='{settings.get('listing_fee_stars', 1)}'><br><br>
        Bot holati: <input type='text' name='bot_status' value='{settings.get('bot_status', 'active')}'><br><br>
        <button type='submit'>Sozlamalarni Saqlash</button>
    </form>
    <hr>
    <h3>Kutilayotgan E'lonlar (Moderatsiya)</h3>
    {pending_html}
    """

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

if __name__ == '__main__':
    # Flask serverni alohida oqimda ishga tushiramiz
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # Telegram botni ishga tushiramiz
    executor.start_polling(dp, skip_updates=True)
