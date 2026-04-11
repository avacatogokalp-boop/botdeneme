import telebot
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import time
import os
import threading
from telebot import types

# 🛠️ AYARLAR (Render Panelinden Çekiliyor)
BOT_TOKEN = os.environ.get('BOT_TOKEN') 
ADMIN_ID = os.environ.get('6943377103')
WEBAPP_URL = "https://botdeneme.onrender.com" 

# Güvenlik Kontrolü
if not BOT_TOKEN or not ADMIN_ID:
    print("⚠️ HATA: BOT_TOKEN veya ADMIN_ID Render panelinde bulunamadı!")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)
CORS(app)

# Kullanıcı verilerini tutan geçici hafıza (24 saat takibi için)
user_spins = {}
COOLDOWN_MS = 24 * 60 * 60 * 1000 

# --- 🤖 TELEGRAM BOT KISMI ---

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.InlineKeyboardMarkup()
    # Mini App'i açacak olan buton ayarı
    web_app = types.WebAppInfo(WEBAPP_URL)
    btn_spin = types.InlineKeyboardButton("🎡 Şans Çarkını Çevir!", web_app=web_app)
    markup.add(btn_spin)
    
    # Altına bir de site butonu ekleyelim
    btn_site = types.InlineKeyboardButton("🌐 Siteye Git", url="https://cutt.ly/deoKNC0g")
    markup.add(btn_site)

    bot.send_message(
        message.chat.id, 
        "🎰 **Betorspin Şans Çarkına Hoş Geldin!**\n\nHer 24 saatte bir çarkı çevirerek efsane ödüller kazanabilirsin.\n\n👇 Çevirmek için aşağıdaki butona bas!", 
        reply_markup=markup, 
        parse_mode="Markdown"
    )

# --- 🌐 WEB / API KISMI ---

@app.route('/')
@app.route('/wheel')
def serve_index():
    # index.html dosyasını ana dizinden sunar
    return send_from_directory('.', 'index.html')

@app.route('/api/check', methods=['GET'])
def check_spin():
    user_id = request.args.get('user_id')
    
    # 👑 Admin (Sen) isen her zaman True döner
    if str(user_id) == str(ADMIN_ID):
        return jsonify({"can_spin": True, "is_admin": True})
    
    last_spin = user_spins.get(str(user_id))
    
    # Daha önce hiç çevirmemişse
    if not last_spin:
        return jsonify({"can_spin": True, "is_admin": False})

    # Süre kontrolü
    passed = (time.time() * 1000) - last_spin
    if passed >= COOLDOWN_MS:
        return jsonify({"can_spin": True, "is_admin": False})
    else:
        remaining = COOLDOWN_MS - passed
        hours = int(remaining // (1000 * 60 * 60))
        minutes = int((remaining % (1000 * 60 * 60)) // (1000 * 60))
        return jsonify({
            "can_spin": False, 
            "is_admin": False, 
            "remaining_hours": hours, 
            "remaining_minutes": minutes
        })

@app.route('/api/spin', methods=['POST'])
def record_spin():
    data = request.get_json()
    user_id = data.get('user_id')
    if user_id:
        # Çevirme zamanını milisaniye olarak kaydet
        user_spins[str(user_id)] = time.time() * 1000
        return jsonify({"success": True})
    return jsonify({"error": "User ID missing"}), 400

# --- 🚀 ÇALIŞTIRICI SİSTEM ---

def run_bot():
    # Botu sonsuz döngüde dinlemeye al
    try:
        bot.infinity_polling()
    except Exception as e:
        print(f"Bot hatası: {e}")

if __name__ == '__main__':
    # Botu ayrı bir kolda (thread) başlat ki Flask'ı engellemesin
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Flask sunucusunu ana kolda başlat
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
