import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from datetime import datetime
import os
from flask import Flask
from threading import Thread

# --- RENDER'I MUTLU ETMEK İÇİN WEB SUNUCUSU ---
app = Flask('')

@app.route('/')
def home():
    return "Bot aktif ve Render ile konuşuyor!"

def run():
    # Render'ın beklediği portu otomatik ayarlar
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- BOT AYARLARI ---
TOKEN = os.environ.get('TOKEN', '8789404565:AAGIjHVpJDrxvLeeCPSjqgUbtJ_zFGxqHH8')
bot = telebot.TeleBot(TOKEN)

SITE_LINKI = "https://cutt.ly/deoKNC0g"
GIF_URL = "https://i.ibb.co/v4mK7P3/bonus-gif.gif"

def log_user(user):
    try:
        with open("users.txt", "a", encoding="utf-8") as f:
            f.write(f"{user.id} | {user.username} | {datetime.now()}\n")
    except:
        pass

@bot.message_handler(commands=['start'])
def start(message):
    try:
        user = message.from_user
        log_user(user)
        markup = InlineKeyboardMarkup()
        web_app = WebAppInfo(url=SITE_LINKI)
        button = InlineKeyboardButton(text="🔥 Hemen Oyna & Kazan 🎰", web_app=web_app)
        markup.add(button)
        text = ("🎰 *Hoş Geldin!*\n\n"
                "💸 En yüksek oranlar burada!\n"
                "⚡ Anında çekim fırsatı\n"
                "🎁 *%300 Hoş Geldin Bonusu*\n\n"
                "👇 Hemen başlamak için tıkla!")
        bot.send_animation(chat_id=message.chat.id, animation=GIF_URL, caption=text, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        print("HATA:", e)

@bot.message_handler(func=lambda m: True)
def fallback(message):
    bot.send_message(message.chat.id, "Komut için /start yaz kanka.")

if __name__ == "__main__":
    print("🚀 Bot ve Web Sunucu ateşleniyor...")
    keep_alive()  # Web sunucusunu başlatır (Render bunu bekliyor)
    bot.infinity_polling(skip_pending=True) # Botu çalıştırır
