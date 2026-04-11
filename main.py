import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime
import threading
from flask import Flask

# --- TOKEN ---
TOKEN = "8789404565:AAGNIIxwsx5p_9sPLBzZ7caEEJsKELo32ks"

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# --- AYARLAR ---
SITE_LINKI = "https://cutt.ly/deoKNC0g"
GIF_URL = "<a href="https://imgbb.com/"><img src="https://i.ibb.co/QvJ5mZCY/14-07-25-Bonus-Gif-Betor-Spin-250x250.gif" alt="14 07 25 Bonus Gif Betor Spin 250x250" border="0"></a>"

# --- FLASK HEALTH CHECK ---
@app.route('/')
def home():
    return "Bot aktif!", 200

@app.route('/health')
def health():
    return "OK", 200

# --- USER LOG ---
def log_user(user):
    try:
        with open("users.txt", "a", encoding="utf-8") as f:
            f.write(f"{user.id} | {user.username} | {datetime.now()}\n")
    except:
        pass

# --- START KOMUTU ---
@bot.message_handler(commands=['start'])
def start(message):
    try:
        user = message.from_user
        log_user(user)

        markup = InlineKeyboardMarkup()

        btn1 = InlineKeyboardButton(
            text="🔥 Hemen Oyna & Kazan 🎰",
            url=SITE_LINKI
        )
        btn2 = InlineKeyboardButton(
            text="🌐 Siteye Git",
            url=SITE_LINKI
        )

        markup.add(btn1)
        markup.add(btn2)

        text = (
            "🎰 *Hoş Geldin!*\n\n"
            "💸 En yüksek oranlar burada!\n"
            "⚡ Anında çekim fırsatı\n"
            "🎁 *%300 Hoş Geldin Bonusu*\n\n"
            "👇 Hemen başlamak için tıkla!"
        )

        bot.send_animation(
            chat_id=message.chat.id,
            animation=GIF_URL,
            caption=text,
            reply_markup=markup,
            parse_mode="Markdown"
        )

    except Exception as e:
        print("HATA:", e)
        bot.send_message(message.chat.id, "Bir hata oluştu, tekrar /start yaz.")

# --- FALLBACK ---
@bot.message_handler(func=lambda m: True)
def fallback(message):
    bot.send_message(message.chat.id, "Komut için /start yaz. 🎰")

# --- BOT THREAD ---
def run_bot():
    print("🤖 Bot polling başlatıldı...")
    bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)

# --- MAIN ---
if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    print("🚀 Flask sunucusu başlatılıyor...")
    app.run(host="0.0.0.0", port=10000)
