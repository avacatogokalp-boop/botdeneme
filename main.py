import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime
import threading
import os
from flask import Flask

# --- AYARLAR ---
# Tokenini buraya güvenli bir şekilde koyduğundan emin ol
TOKEN = "8789404565:AAH2i-If4502k7o2pzYuKar4cN38eRKPlTE"
SITE_LINKI = "https://cutt.ly/deoKNC0g"
GIF_URL = "https://i.ibb.co/QvJ5mZCY/14-07-25-Bonus-Gif-Betor-Spin-250x250.gif"

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# --- FLASK YOLLARI ---
@app.route('/')
def home():
    return "Bot ve Web Sunucusu Aktif!", 200

@app.route('/health')
def health():
    return "OK", 200

# --- KULLANICI KAYDI (NOT: Render'da geçicidir) ---
def log_user(user):
    try:
        with open("users.txt", "a", encoding="utf-8") as f:
            log_data = f"{user.id} | {user.username} | {datetime.now()}\n"
            f.write(log_data)
            print(f"👤 Yeni Kullanıcı: {user.username}")
    except Exception as e:
        print(f"Kayıt Hatası: {e}")

# --- START KOMUTU ---
@bot.message_handler(commands=['start'])
def start(message):
    try:
        user = message.from_user
        log_user(user)

        markup = InlineKeyboardMarkup()
        btn1 = InlineKeyboardButton(text="🔥 Hemen Oyna & Kazan 🎰", url=SITE_LINKI)
        btn2 = InlineKeyboardButton(text="🌐 Siteye Git", url=SITE_LINKI)
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
        print(f"✅ Start mesajı gönderildi: {user.id}")

    except Exception as e:
        print(f"⚠️ Start Hatası: {e}")
        bot.send_message(message.chat.id, "Bir hata oluştu, lütfen tekrar deneyin.")

# --- HERHANGİ BİR MESAJ ---
@bot.message_handler(func=lambda m: True)
def fallback(message):
    bot.reply_to(message, "Lütfen menüye ulaşmak için /start komutunu kullanın. 🎰")

# --- BOTU ÇALIŞTIRMA FONKSİYONU ---
def run_bot():
    print("🤖 Telegram Bot Polling başlatılıyor...")
    try:
        # skip_pending=True eski mesajları görmezden gelmesini sağlar
        bot.infinity_polling(skip_pending=True, timeout=60, long_polling_timeout=60)
    except Exception as e:
        print(f"❌ Bot Polling Hatası: {e}")

# --- ANA ÇALIŞTIRICI ---
if __name__ == "__main__":
    # 1. Botu ayrı bir thread (iş parçacığı) olarak başlat
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()

    # 2. Flask sunucusunu başlat (Render PORT'u otomatik verir)
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Flask {port} portunda çalışıyor...")
    app.run(host="0.0.0.0", port=port)
