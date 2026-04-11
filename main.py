import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
import threading
import os
import time
import json
from datetime import datetime
from flask import Flask, send_from_directory, request, jsonify

TOKEN = os.environ.get("BOT_TOKEN")
SITE_LINKI = "https://cutt.ly/deoKNC0g"
GIF_URL = "https://i.ibb.co/QvJ5mZCY/14-07-25-Bonus-Gif-Betor-Spin-250x250.gif"
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://botdeneme.onrender.com")
MINI_APP_URL = f"{RENDER_URL}/wheel"

ADMIN_ID = 6943377103

# Günlük spin takibi: { user_id: "YYYY-MM-DD" }
spin_log = {}
spin_lock = threading.Lock()

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# ── Spin hakkı kontrol / kullan ───────────────────────────────────────
def can_spin(user_id: int) -> bool:
    if user_id == ADMIN_ID:
        return True
    today = datetime.utcnow().strftime("%Y-%m-%d")
    with spin_lock:
        return spin_log.get(user_id) != today

def use_spin(user_id: int):
    if user_id == ADMIN_ID:
        return
    today = datetime.utcnow().strftime("%Y-%m-%d")
    with spin_lock:
        spin_log[user_id] = today

# ── Flask rotaları ────────────────────────────────────────────────────
@app.route('/')
def home():
    return "Bot Aktif!", 200

@app.route('/wheel')
def wheel():
    return send_from_directory('.', 'index.html')

# Mini App spin başlamadan önce kontrol eder
@app.route('/api/check_spin')
def check_spin():
    user_id = request.args.get('user_id', type=int)
    if not user_id:
        return jsonify({"allowed": False, "reason": "no_id"})
    allowed = can_spin(user_id)
    return jsonify({"allowed": allowed})

# Mini App spin kullandığında çağırır
@app.route('/api/use_spin', methods=['POST'])
def api_use_spin():
    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')
    if not user_id:
        return jsonify({"ok": False})
    use_spin(int(user_id))
    return jsonify({"ok": True})

# ── /start komutu ─────────────────────────────────────────────────────
@bot.message_handler(commands=['start'])
def start(message):
    try:
        user_id = message.from_user.id
        markup = InlineKeyboardMarkup(row_width=1)

        btn_wheel = InlineKeyboardButton(
            text="🎰 Şans Çarkını Çevir!",
            web_app=WebAppInfo(url=f"{MINI_APP_URL}?user_id={user_id}")
        )
        btn_play = InlineKeyboardButton(text="🔥 Hemen Oyna & Kazan 🎰", url=SITE_LINKI)
        btn_site = InlineKeyboardButton(text="🌐 Siteye Git", url=SITE_LINKI)

        markup.add(btn_wheel)
        markup.row(btn_play, btn_site)

        if can_spin(user_id):
            spin_status = "🎡 *Bugünkü spin hakkın seni bekliyor!*"
        else:
            spin_status = "⏳ *Bugünkü spin hakkını kullandın. Yarın tekrar gel!*"

        text = (
            "🎰 *Hoş Geldin!*\n\n"
            f"{spin_status}\n"
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

        print(f"✅ Mesaj gönderildi: {user_id}")

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

# ── Admin komutu: spin logunu gör ────────────────────────────────────
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        return
    with spin_lock:
        count = len(spin_log)
    bot.send_message(
        message.chat.id,
        f"👑 *Admin Panel*\n\n"
        f"📊 Bugün spin kullanan kişi: *{count}*\n"
        f"🔓 Senin spin hakkın: *Sınırsız*",
        parse_mode="Markdown"
    )

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
