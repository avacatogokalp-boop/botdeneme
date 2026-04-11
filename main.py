import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
import threading
import os
import time
import json
from flask import Flask, send_from_directory

TOKEN = os.environ.get("BOT_TOKEN")
SITE_LINKI = "https://cutt.ly/deoKNC0g"
GIF_URL = "https://i.ibb.co/QvJ5mZCY/14-07-25-Bonus-Gif-Betor-Spin-250x250.gif"

# Render otomatik olarak servis adını bu env variable ile verir
# Örnek: https://botdeneme.onrender.com
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://botdeneme.onrender.com")
MINI_APP_URL = f"{RENDER_URL}/wheel"

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# ── Ana sayfa (health check) ──────────────────────────────────────────
@app.route('/')
def home():
    return "Bot Aktif!", 200

# ── Şans Çarkı Mini App sayfası ───────────────────────────────────────
@app.route('/wheel')
def wheel():
    return send_from_directory('.', 'index.html')

# ── /start komutu ────────────────────────────────────────────────────
@bot.message_handler(commands=['start'])
def start(message):
    try:
        markup = InlineKeyboardMarkup(row_width=1)

        btn_wheel = InlineKeyboardButton(
            text="🎰 Şans Çarkını Çevir!",
            web_app=WebAppInfo(url=MINI_APP_URL)
        )
        btn_play = InlineKeyboardButton(text="🔥 Hemen Oyna & Kazan 🎰", url=SITE_LINKI)
        btn_site = InlineKeyboardButton(text="🌐 Siteye Git", url=SITE_LINKI)

        markup.add(btn_wheel)
        markup.row(btn_play, btn_site)

        text = (
            "🎰 *Hoş Geldin!*\n\n"
            "🎡 *Şans Çarkını Çevir, Ödülünü Kap!*\n"
            "🎁 *%300 Hoş Geldin Bonusu*\n\n"
            "👇 Şans çarkını çevirmek için butona tıkla!"
        )

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
        bot.send_message(message.chat.id, "Teknik bir sorun var, logları kontrol et.")

# ── Mini App'ten gelen spin sonucu ───────────────────────────────────
@bot.message_handler(content_types=['web_app_data'])
def handle_web_app_data(message):
    try:
        data = json.loads(message.web_app_data.data)
        user = message.from_user
        name = user.first_name or "Kullanıcı"

        if data.get("win") and data.get("prize"):
            prize = data["prize"]
            bot.send_message(
                message.chat.id,
                f"🎉 *Tebrikler {name}!*\n\n"
                f"🏆 Kazandığın ödül: *{prize}*\n\n"
                f"👇 Ödülünü almak için siteye gir!",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup().add(
                    InlineKeyboardButton("🎁 Ödülü Al!", url=SITE_LINKI)
                )
            )
        else:
            bot.send_message(
                message.chat.id,
                f"😔 *Bu sefer olmadı {name}!*\n\n"
                f"Siteye girerek yeni spin hakkı kazanabilirsin 🎰",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup().add(
                    InlineKeyboardButton("🔥 Tekrar Dene!", url=SITE_LINKI)
                )
            )

        print(f"🎡 Spin sonucu: {user.id} -> {data}")

    except Exception as e:
        print(f"❌ WebApp data hatası: {e}")

# ── Diğer mesajlar ───────────────────────────────────────────────────
@bot.message_handler(func=lambda m: True)
def fallback(message):
    bot.reply_to(message, "Lütfen /start yazın. 🎰")

# ── Bot polling (ayrı thread) ────────────────────────────────────────
def run_bot():
    bot.remove_webhook()
    print("🤖 Bot başlatıldı, polling başlıyor...")
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
