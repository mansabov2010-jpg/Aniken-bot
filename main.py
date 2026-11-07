from aiogram import Bot, Dispatcher
from aiogram.utils import executor
from flask import Flask, render_template, request, redirect, g
import sqlite3
from handlers.user_handlers import register_handlers

API_TOKEN = 'TOKEN_SHU_YERGA'
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Handlerlarni ulash
register_handlers(dp)

app = Flask(__name__)
app.secret_key = 'secret_key'
DATABASE = 'bot_database.db'

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

@app.route('/app')
def web_app():
    return render_template('index.html')

@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    db = get_db()
    cursor = db.cursor()
    
    if request.method == 'POST':
        for key, value in request.form.items():
            cursor.execute("INSERT OR REPLACE INTO admin_settings (key, value) VALUES (?, ?)", (key, value))
        db.commit()
        return redirect('/admin')
        
    cursor.execute("SELECT * FROM admin_settings")
    settings = {row['key']: row['value'] for row in cursor.fetchall()}
    
    return f"""
    <h2>👑 Admin Sozlamalar Paneli</h2>
    <form method='POST'>
        E'lon berish narxi (Stars): <input type='text' name='listing_fee_stars' value='{settings.get('listing_fee_stars', 1)}'><br><br>
        Bot holati: <input type='text' name='bot_status' value='{settings.get('bot_status', 'active')}''><br><br>
        <button type='submit'>Saqlash</button>
    </form>
    """

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
    
