import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime
import threading
import os
import time
from flask import Flask

# --- AYARLAR ---
# Render Environment Variables'dan çekiyoruz
TOKEN = os.environ.get("BOT_TOKEN")
SITE_LINKI = "https://cutt.ly/deoKNC0g"
GIF_URL = "https://i.ibb.co/QvJ5mZCY/14-07-25-Bonus-Gif-Betor-Spin-250x250.gif"

# Token Kontrolü (Loglarda hata varsa görelim)
if not TOKEN:
    print("❌ HATA: BOT_TOKEN bulunamadı! Render panelinden Environment Variables kısmını kontrol et.")
else:
    print(f"✅ Token başarıyla yüklendi: {TOKEN[:5]}***")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# --- FLASK YOLLARI (Render'ı uyanık tutmak için) ---
@app.route('/')
def home():
    return "Bot ve Web Sunucusu Aktif!", 200

@app.route('/health')
def health():
    return "OK", 200

# --- KULLANICI KAYDI ---
def log_user(user):
    try:
        # Render'da dosyalar geçicidir, loglarda görmeni sağlar
        log_data = f"{user.id} | {user.username} | {datetime.now()}"
        print(f"👤 Yeni Kullanıcı Girişi: {log_data}")
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
        print(f"🚀 {user.username} için Start mesajı başarıyla gönderildi.")

    except Exception as e:
        print(f"⚠️ Start Mesajı Gönderilemedi: {e}")

# --- DİĞER MESAJLAR ---
@bot.message_handler(func=lambda m: True)
def fallback(message):
    bot.reply_to(message, "Lütfen menüye ulaşmak için /start komutunu kullanın. 🎰")

# --- BOTU ÇALIŞTIRMA (Hata Alırsa Kapanmayan Versiyon) ---
def run_bot():
    print("🤖 Telegram Bot Polling döngüsü başlıyor...")
    while True:
        try:
            bot.infinity_polling(skip_pending=True, timeout=90, long_polling_timeout=90)
        except Exception as e:
            print(f"❌ Bot bağlantısı koptu, 5 saniye sonra tekrar denenecek: {e}")
            time.sleep(5)

# --- ANA ÇALIŞTIRICI ---
if __name__ == "__main__":
    # 1. Botu arka planda başlat
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()

    # 2. Flask sunucusunu başlat
    port = int(os.environ.get("PORT", 10000))
    print(f"🌐 Flask sunucusu {port} portunda ayağa kalkıyor...")
    
    # Render üzerinde debug=False olmalı
    app.run(host="0.0.0.0", port=port, debug=False)
