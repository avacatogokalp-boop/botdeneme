import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
import threading
import os
import time
import json
import sqlite3
import hmac
import hashlib
from datetime import datetime, timezone
from flask import Flask, send_from_directory, request, jsonify
from collections import defaultdict

TOKEN = os.environ.get("BOT_TOKEN")
SITE_LINKI = "https://cutt.ly/7tF5Ow3K"
GIF_URL = "https://i.ibb.co/jPtFMZJC/0414.gif"
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://botdeneme.onrender.com")
MINI_APP_URL = f"{RENDER_URL}/wheel"
ADMIN_ID = 6943377103  # AYNI ID FRONTEND'DEKİ ADMIN_ID İLE MATCH ETMELI!

# ── DATABASE SETUP ────────────────────────────────────────────────────
db_lock = threading.Lock()

def init_db():
    with db_lock:
        conn = sqlite3.connect('betorspin.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            name TEXT,
            username TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS spin_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            date TEXT,
            UNIQUE(user_id, date)
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS bonus_spins (
            user_id INTEGER PRIMARY KEY,
            amount INTEGER DEFAULT 0
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS invites (
            referrer_id INTEGER,
            referred_id INTEGER,
            UNIQUE(referred_id)
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS wins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            prize TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS api_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            endpoint TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        conn.commit()
        conn.close()

init_db()

# ── RATE LIMITING ────────────────────────────────────────────────────
api_calls = defaultdict(list)  # user_id -> [timestamps]

def check_rate_limit(user_id, max_calls=5, window=60):
    """Max 5 çağrı 60 saniyede"""
    now = time.time()
    api_calls[user_id] = [t for t in api_calls[user_id] if now - t < window]

    if len(api_calls[user_id]) >= max_calls:
        return False

    api_calls[user_id].append(now)
    return True

# ── TELEGRAM MINI APP DOĞRULAMA ────────────────────────────────────────
def validate_telegram_data(init_data: str) -> dict:
    """Telegram Mini App'den gelen data'yı doğrula"""
    try:
        if not init_data:
            return None

        # Data parse et
        data_check_string = "\n".join(
            f"{k}={v}" for k, v in sorted(
                [item.split("=") for item in init_data.split("&") if item != "hash"],
                key=lambda x: x[0]
            )
        )

        # Hash doğrula
        secret_key = hashlib.sha256(TOKEN.encode()).digest()
        computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

        # URL'den hash'i al
        hash_value = None
        for item in init_data.split("&"):
            if item.startswith("hash="):
                hash_value = item.split("=")[1]
                break

        if not hash_value or computed_hash != hash_value:
            return None

        # User data'yı çıkar
        user_data = None
        for item in init_data.split("&"):
            if item.startswith("user="):
                user_json = item.split("=", 1)[1]
                user_data = json.loads(user_json.replace("%7B", "{").replace("%7D", "}"))
                break

        return user_data
    except:
        return None

# ── YARDIMCI FONKSİYONLAR ────────────────────────────────────────────
def is_admin(user_id: int) -> bool:
    return int(user_id) == ADMIN_ID

def get_today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def get_user_info(user_id: int) -> dict:
    with db_lock:
        conn = sqlite3.connect('betorspin.db')
        c = conn.cursor()
        c.execute('SELECT name, username FROM users WHERE user_id = ?', (user_id,))
        row = c.fetchone()
        conn.close()
    return {"name": row[0], "username": row[1]} if row else {}

def save_user(user_id: int, name: str, username: str):
    with db_lock:
        conn = sqlite3.connect('betorspin.db')
        c = conn.cursor()
        c.execute(
            'INSERT OR REPLACE INTO users (user_id, name, username) VALUES (?, ?, ?)',
            (user_id, name, username)
        )
        conn.commit()
        conn.close()

def can_spin(user_id: int) -> bool:
    if is_admin(user_id):
        return True

    today = get_today()
    with db_lock:
        conn = sqlite3.connect('betorspin.db')
        c = conn.cursor()

        # Bonus spin kontrolü
        c.execute('SELECT amount FROM bonus_spins WHERE user_id = ?', (user_id,))
        bonus_row = c.fetchone()
        if bonus_row and bonus_row[0] > 0:
            conn.close()
            return True

        # Daily limit kontrolü
        c.execute('SELECT 1 FROM spin_log WHERE user_id = ? AND date = ?', (user_id, today))
        daily_row = c.fetchone()
        conn.close()

        return not daily_row

def use_spin(user_id: int):
    if is_admin(user_id):
        return

    with db_lock:
        conn = sqlite3.connect('betorspin.db')
        c = conn.cursor()

        # Bonus spin kontrol et
        c.execute('SELECT amount FROM bonus_spins WHERE user_id = ?', (user_id,))
        bonus_row = c.fetchone()

        if bonus_row and bonus_row[0] > 0:
            c.execute('UPDATE bonus_spins SET amount = amount - 1 WHERE user_id = ?', (user_id,))
        else:
            today = get_today()
            c.execute('INSERT OR IGNORE INTO spin_log (user_id, date) VALUES (?, ?)', (user_id, today))

        conn.commit()
        conn.close()

def available_spins(user_id: int) -> int:
    if is_admin(user_id):
        return 99

    today = get_today()
    with db_lock:
        conn = sqlite3.connect('betorspin.db')
        c = conn.cursor()

        # Daily spin
        c.execute('SELECT 1 FROM spin_log WHERE user_id = ? AND date = ?', (user_id, today))
        daily = 0 if c.fetchone() else 1

        # Bonus spin
        c.execute('SELECT amount FROM bonus_spins WHERE user_id = ?', (user_id,))
        bonus_row = c.fetchone()
        bonus = bonus_row[0] if bonus_row else 0

        conn.close()

    return daily + bonus

def add_bonus_spin(user_id: int, amount: int = 1):
    with db_lock:
        conn = sqlite3.connect('betorspin.db')
        c = conn.cursor()
        c.execute('INSERT INTO bonus_spins VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET amount = amount + ?',
                  (user_id, amount, amount))
        conn.commit()
        conn.close()

def record_win(user_id: int, prize: str):
    with db_lock:
        conn = sqlite3.connect('betorspin.db')
        c = conn.cursor()
        c.execute('INSERT INTO wins (user_id, prize) VALUES (?, ?)', (user_id, prize))
        conn.commit()
        conn.close()

def get_stats():
    today = get_today()
    with db_lock:
        conn = sqlite3.connect('betorspin.db')
        c = conn.cursor()

        # Bugün çevirenler
        c.execute('SELECT COUNT(DISTINCT user_id) FROM spin_log WHERE date = ?', (today,))
        today_count = c.fetchone()[0]

        # Toplam kullanıcı
        c.execute('SELECT COUNT(*) FROM users')
        total_users = c.fetchone()[0]

        # Toplam davetler
        c.execute('SELECT COUNT(*) FROM invites')
        total_invites = c.fetchone()[0]

        # Ödül istatistikleri
        c.execute('SELECT prize, COUNT(*) as cnt FROM wins GROUP BY prize ORDER BY cnt DESC')
        wins = c.fetchall()

        # Bugün çevirenler (top 20)
        c.execute('''SELECT DISTINCT u.user_id, u.name, u.username, COALESCE(b.amount, 0) as bonus
                     FROM spin_log s
                     JOIN users u ON s.user_id = u.user_id
                     LEFT JOIN bonus_spins b ON u.user_id = b.user_id
                     WHERE s.date = ?
                     LIMIT 20''', (today,))
        today_users = c.fetchall()

        conn.close()

    return {
        "today_count": today_count,
        "total_users": total_users,
        "total_invites": total_invites,
        "wins": wins,
        "today_users": today_users
    }

# ── BOTUN ÖN KONTROLÜ ─────────────────────────────────────────────────
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# ── FLASK ROUTES ──────────────────────────────────────────────────────
@app.route('/')
def home():
    return "Bot Aktif!", 200

@app.route('/wheel')
def wheel():
    return send_from_directory('.', 'index.html')

@app.route('/api/check_spin')
def check_spin():
    user_id = request.args.get('user_id', type=int)
    if not user_id:
        return jsonify({"allowed": False, "reason": "no_id"}), 400

    spins = available_spins(user_id)
    return jsonify({"allowed": spins > 0, "spins": spins})

@app.route('/api/use_spin', methods=['POST'])
def api_use_spin():
    # Rate limiting
    user_id = request.form.get('user_id', type=int)
    if not user_id or not check_rate_limit(user_id):
        return jsonify({"ok": False, "reason": "rate_limited"}), 429

    # Spin hakkı kontrol
    if not can_spin(user_id):
        return jsonify({"ok": False, "reason": "no_spins"}), 403

    # Kullanıcı bilgisi kaydet
    name = request.form.get('name', 'Bilinmiyor')
    username = request.form.get('username', '')
    save_user(user_id, name, username)

    # Spin'i kaydet
    use_spin(user_id)

    return jsonify({"ok": True})

@app.route('/api/spin_result', methods=['POST'])
def api_spin_result():
    """Spin sonucunu gönder ve doğrula"""
    try:
        data = request.get_json()
        user_id = data.get('user_id', type=int)
        init_data = data.get('init_data')

        # Rate limit
        if not user_id or not check_rate_limit(user_id, max_calls=1, window=30):
            return jsonify({"ok": False}), 429

        # Telegram data doğrulama (optional, çok katı olmak istersen aç)
        # user_data = validate_telegram_data(init_data)
        # if not user_data or user_data['id'] != user_id:
        #     return jsonify({"ok": False}), 401

        # Backend'de çevir (frontend'i bypass etme)
        SEGMENTS = [
            {"name": "KAYBETTİN", "win": False, "prize": None},
            {"name": "200 Bonus Buy", "win": True, "prize": "200 Bonus Buy"},
            {"name": "+1 Spin", "win": True, "prize": "+1 Spin", "extra": True},
            {"name": "100 Freespin", "win": True, "prize": "100 Freespin"},
            {"name": "Yatırım Bonusu", "win": True, "prize": "Yatırım Bonusu"},
            {"name": "100₺ Bakiye", "win": True, "prize": "100₺ Bakiye"},
            {"name": "VIP Gift", "win": True, "prize": "VIP Gift"},
            {"name": "KAYBETTİN", "win": False, "prize": None},
            {"name": "200 Bonus Buy", "win": True, "prize": "200 Bonus Buy"},
            {"name": "100 Freespin", "win": True, "prize": "100 Freespin"},
        ]

        # Random çevir
        import random
        result = random.choice(SEGMENTS)

        # Eğer +1 Spin ise bonus ekle
        if result.get("extra"):
            add_bonus_spin(user_id, 1)

        # Kazanıysa kaydet
        if result["win"]:
            record_win(user_id, result["prize"])

        return jsonify({
            "ok": True,
            "win": result["win"],
            "prize": result.get("prize"),
            "extra": result.get("extra", False)
        })

    except Exception as e:
        print(f"❌ Spin result error: {e}")
        return jsonify({"ok": False}), 500

@app.route('/api/stats')
def api_stats():
    """Admin için istatistikler"""
    admin_key = request.args.get('key')
    if admin_key != os.environ.get("ADMIN_KEY", ""):
        return jsonify({"error": "Unauthorized"}), 401

    stats = get_stats()
    return jsonify(stats)

# ── BOT COMMANDS ──────────────────────────────────────────────────────
@bot.message_handler(commands=['start'])
def start(message):
    try:
        user_id = message.from_user.id
        args = message.text.split()
        ref_param = args[1] if len(args) > 1 else None

        # Kullanıcı bilgisini kaydet
        name = message.from_user.first_name or "Kullanıcı"
        username = message.from_user.username or ""
        save_user(user_id, name, username)

        # Referral kontrol
        if ref_param and ref_param.startswith("ref_"):
            try:
                inviter_id = int(ref_param.split("_")[1])
                with db_lock:
                    conn = sqlite3.connect('betorspin.db')
                    c = conn.cursor()
                    c.execute('INSERT INTO invites (referrer_id, referred_id) VALUES (?, ?)',
                              (inviter_id, user_id))
                    conn.commit()
                    conn.close()

                add_bonus_spin(inviter_id, 1)

                try:
                    bot.send_message(
                        inviter_id,
                        f"🎉 *Tebrikler!*\n\n"
                        f"👤 *{name}* davet linkinle katıldı!\n"
                        f"🎡 *+1 Ekstra Spin Hakkı* kazandın!",
                        parse_mode="Markdown"
                    )
                except:
                    pass
            except:
                pass

        # Spin hakkını kontrol et
        spins = available_spins(user_id)
        spin_status = f"🎡 *{spins} spin hakkın seni bekliyor!*" if spins > 0 else "⏳ *Bugünkü spin hakkını kullandın. Yarın tekrar gel!*"

        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(InlineKeyboardButton(
            text="🎰 Şans Çarkını Çevir!",
            web_app=WebAppInfo(url=f"{MINI_APP_URL}?user_id={user_id}")
        ))

        text = (
            "🎰 *HOŞ GELDİN, KAZANMAYA HAZIR MISIN?*\n\n"
            f"{spin_status}\n\n"
            "✨ *BetorSpin* çarkına adım attın, şansını deneme zamanı!\n\n"
            "🎡 *Şans Çarkın seni bekliyor:*\n"
            "• 500 TL Bonus\n"
            "• 100 Freespin\n"
            "• Büyük Ödül\n"
            "• ve daha fazlası...\n\n"
            "⚡ Gecikmeden çevir, kazanmaya hemen başla!"
        )

        try:
            bot.send_animation(chat_id=message.chat.id, animation=GIF_URL, caption=text,
                             reply_markup=markup, parse_mode="Markdown")
        except:
            bot.send_message(chat_id=message.chat.id, text=text, reply_markup=markup,
                           parse_mode="Markdown")

        print(f"✅ /start: {user_id}")
    except Exception as e:
        print(f"❌ HATA: {e}")
        bot.send_message(message.chat.id, "Teknik bir sorun var.")

@bot.message_handler(commands=['davet'])
def davet(message):
    user_id = message.from_user.id
    bot_info = bot.get_me()
    invite_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"

    with db_lock:
        conn = sqlite3.connect('betorspin.db')
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM invites WHERE referrer_id = ?', (user_id,))
        invite_count = c.fetchone()[0]
        c.execute('SELECT amount FROM bonus_spins WHERE user_id = ?', (user_id,))
        bonus_row = c.fetchone()
        bonus = bonus_row[0] if bonus_row else 0
        conn.close()

    bot.send_message(
        message.chat.id,
        f"👥 *Arkadaşını Davet Et, Spin Kazan!*\n\n"
        f"Her davet ettiğin kişi bota katılınca *+1 Spin* hakkı kazanırsın!\n\n"
        f"🔗 *Davet Linkin:*\n`{invite_link}`\n\n"
        f"📊 *İstatistiklerin:*\n"
        f"• Davet ettiğin kişi: *{invite_count}*\n"
        f"• Mevcut bonus spin: *{bonus}*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("📤 Linki Paylaş",
                               switch_inline_query=f"Betorspin Şans Çarkı'nı dene! {invite_link}")
        )
    )

@bot.message_handler(commands=['stats', 'admin'])
def admin_stats(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "⛔ Yetkisiz erişim.")
        return

    stats = get_stats()

    win_lines = "\n".join(
        [f"• {prize}: *{count}* kez" for prize, count in stats["wins"]]
    ) or "_Henüz veri yok_"

    user_lines = []
    for uid, name, uname, bonus in stats["today_users"][:20]:
        uname_str = f" @{uname}" if uname else ""
        bonus_str = f" (+{bonus}🎡)" if bonus else ""
        user_lines.append(f"• {name}{uname_str}{bonus_str} `{uid}`")

    user_list = "\n".join(user_lines) if user_lines else "_Henüz kimse çevirmedi_"

    bot.send_message(
        message.chat.id,
        f"📊 *Bot İstatistikleri*\n\n"
        f"👥 Toplam kullanıcı: *{stats['total_users']}*\n"
        f"🎡 Bugün spin: *{stats['today_count']}*\n"
        f"📤 Toplam davet: *{stats['total_invites']}*\n\n"
        f"🏆 *Kazanılan Ödüller:*\n{win_lines}\n\n"
        f"📅 *Bugün Çevirenler:*\n{user_list}",
        parse_mode="Markdown"
    )

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
                    InlineKeyboardButton("SİTEYE GİT VE OYNA", url=SITE_LINKI)
                )
            )
        else:
            bot.send_message(
                message.chat.id,
                f"😔 *Bu sefer olmadı {name}!*\n\n"
                f"Arkadaşını davet et, *+1 Spin* kazan! 👇",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup().add(
                    InlineKeyboardButton("👥 Arkadaşını Davet Et → +1 Spin",
                                        callback_data="get_invite_link")
                ).add(
                    InlineKeyboardButton("SİTEYE GİT VE OYNA", url=SITE_LINKI)
                )
            )

        print(f"🎡 Spin sonucu: {user.id} -> {data}")
    except Exception as e:
        print(f"❌ WebApp data hatası: {e}")

@bot.message_handler(func=lambda m: True)
def fallback(message):
    bot.reply_to(message, "Lütfen /start yazın. 🎰")

# ── BOT POLLING ───────────────────────────────────────────────────────
def run_bot():
    bot.remove_webhook()
    print("🤖 Bot başlatıldı, polling başlıyor...")
    while True:
        try:
            bot.infinity_polling(skip_pending=True, timeout=90)
        except Exception as e:
            print(f"🔄 Bağlantı koptu: {e}")
            time.sleep(5)

if __name__ == "__main__":
    t = threading.Thread(target=run_bot, daemon=True)
    t.start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
