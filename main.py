import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from datetime import datetime
import os
from flask import Flask
from threading import Thread

# --- FLASK AYARI (Render için) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    # Render genelde 10000 portunu kullanır
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- TOKEN ---
TOKEN = "8789404565:AAGIjHVpJDrxvLeeCPSjqgUbtJ_zFGxqHH8"
bot = telebot.TeleBot(TOKEN)

# --- AYARLAR ---
SITE_LINKI = "https://cutt.ly/deoKNC0g"
GIF_URL = "https://i.ibb.co/v4mK7P3/bonus-gif.gif"

# --- USER LOG ---
def log_user(user):
    try:
        with open("users.txt", "a", encoding="utf-8") as f:
            f.write(f"{user.id} | {user.username} | {datetime.now()}\n")
    except:
        pass

# --- START ---
@bot.message_handler(commands=['start'])
def start(message):
    try:
        user = message.from_user
        log_user(user)

        markup = InlineKeyboardMarkup()
        web_app = WebAppInfo(url=SITE_LINKI)
        button = InlineKeyboardButton(text="🔥 Hemen Oyna & Kazan 🎰", web_app=web_app)
        markup.add(button)

        text = ("🎰 *Hoş Geldin!*\n\n💸 En yüksek oranlar burada!\n"
                "⚡ Anında çekim fırsatı\n🎁 *%300 Hoş Geldin Bonusu*\n\n"
                "👇 Hemen başlamak için tıkla!")

        bot.send_animation(chat_id=message.chat.id, animation=GIF_URL, 
                          caption=text, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        print("HATA:", e)

# --- RUN ---
if __name__ == "__main__":
    print("🚀 Web sunucusu başlatılıyor...")
    keep_alive() # Flask'ı arka planda başlatır
    print("🚀 Bot aktif çalışıyor...")
    bot.infinity_polling(skip_pending=True)
