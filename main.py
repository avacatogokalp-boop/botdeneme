import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import threading
import os
import time
from flask import Flask

TOKEN = os.environ.get("BOT_TOKEN")
SITE_LINKI = "https://cutt.ly/deoKNC0g"
# GIF linkini test etmek için geçici olarak değiştirebilirsin veya bunu dene
GIF_URL = "https://i.ibb.co/QvJ5mZCY/14-07-25-Bonus-Gif-Betor-Spin-250x250.gif"

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Aktif!", 200

@bot.message_handler(commands=['start'])
def start(message):
    try:
        markup = InlineKeyboardMarkup()
        btn1 = InlineKeyboardButton(text="🔥 Hemen Oyna & Kazan 🎰", url=SITE_LINKI)
        btn2 = InlineKeyboardButton(text="🌐 Siteye Git", url=SITE_LINKI)
        markup.add(btn1, btn2)

        text = (
            "🎰 *Hoş Geldin!*\n\n"
            "🎁 *%300 Hoş Geldin Bonusu*\n"
            "👇 Hemen başlamak için tıkla!"
        )

        # Önce GIF'i dene, olmazsa düz mesaj atar
        try:
            bot.send_animation(
                chat_id=message.chat.id,
                animation=GIF_URL,
                caption=text,
                reply_markup=markup,
                parse_mode="Markdown"
            )
        except:
            bot.send_message(
                chat_id=message.chat.id,
                text=text,
                reply_markup=markup,
                parse_mode="Markdown"
            )
        
        print(f"✅ Mesaj gönderildi: {message.from_user.id}")

    except Exception as e:
        print(f"❌ HATA: {e}")
        bot.send_message(message.chat.id, "Botta bir teknik sorun var, logları kontrol et.")

@bot.message_handler(func=lambda m: True)
def fallback(message):
    bot.reply_to(message, "Lütfen /start yazın. 🎰")

def run_bot():
    # Eski bağlantıları temizle (Kritik nokta)
    bot.remove_webhook()
    print("🤖 Bot bağlantısı tazelendi, polling başlıyor...")
    while True:
        try:
            bot.infinity_polling(skip_pending=True, timeout=90)
        except Exception as e:
            print(f"🔄 Bağlantı koptu, tekrar deneniyor: {e}")
            time.sleep(5)

if __name__ == "__main__":
    t = threading.Thread(target=run_bot, daemon=True)
    t.start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
