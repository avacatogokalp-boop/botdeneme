import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
import threading
import os
import time
import json
from datetime import datetime, timezone, timedelta
import sqlite3
import random
import csv
import io
from flask import Flask, send_from_directory, request, jsonify, Response

TOKEN = os.environ.get("BOT_TOKEN")
SITE_LINKI = "https://cutt.ly/7tF5Ow3K"
GIF_URL = "https://i.ibb.co/jPtFMZJC/0414.gif"
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://botdeneme.onrender.com")
MINI_APP_URL = f"{RENDER_URL}/wheel"
ADMIN_IDS = [6943377103]  # Şefin ID'sini eklemek için: [6943377103, SEFİN_ID]

db_lock = threading.Lock()

DB_PATH = "/var/data/database.sqlite" if os.path.isdir("/var/data") else "database.sqlite"

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db_lock:
        conn = get_db()
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            name TEXT,
            username TEXT,
            last_spin_date TEXT,
            bonus_spins INTEGER DEFAULT 0,
            inviter_id INTEGER,
            invite_count INTEGER DEFAULT 0,
            boscoin INTEGER DEFAULT 0
        )''')
        try:
            c.execute("ALTER TABLE users ADD COLUMN boscoin INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass # Sütun zaten varsa hata vermeden devam et
        
        c.execute('''CREATE TABLE IF NOT EXISTS wins (
            prize TEXT PRIMARY KEY,
            count INTEGER DEFAULT 0
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS spin_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            prize TEXT,
            date_time TEXT
        )''')
        conn.commit()
        conn.close()

init_db()

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# ── Yardımcı ─────────────────────────────────────────────────────────
def is_admin(user_id: int) -> bool:
    return int(user_id) in ADMIN_IDS

def get_today():
    return datetime.now(timezone(timedelta(hours=3))).strftime("%Y-%m-%d")

def register_user(user_id: int, name: str, username: str):
    with db_lock:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE id = ?", (user_id,))
        if not c.fetchone():
            c.execute("INSERT INTO users (id, name, username) VALUES (?, ?, ?)", (user_id, name, username))
        else:
            c.execute("UPDATE users SET name = ?, username = ? WHERE id = ?", (name, username, user_id))
        conn.commit()
        conn.close()

def available_spins(user_id: int) -> int:
    if is_admin(user_id): return 99
    today = get_today()
    with db_lock:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT last_spin_date, bonus_spins FROM users WHERE id = ?", (user_id,))
        row = c.fetchone()
        conn.close()
        
    if not row:
        return 1
    
    daily = 0 if row["last_spin_date"] == today else 1
    bonus = row["bonus_spins"]
    return daily + bonus

def use_spin(user_id: int):
    if is_admin(user_id): return
    today = get_today()
    with db_lock:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT last_spin_date, bonus_spins FROM users WHERE id = ?", (user_id,))
        row = c.fetchone()
        
        if row:
            if row["bonus_spins"] > 0:
                c.execute("UPDATE users SET bonus_spins = bonus_spins - 1 WHERE id = ?", (user_id,))
            else:
                c.execute("UPDATE users SET last_spin_date = ? WHERE id = ?", (today, user_id))
        conn.commit()
        conn.close()

def add_bonus_spin(user_id: int, amount: int = 1):
    with db_lock:
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE users SET bonus_spins = bonus_spins + ? WHERE id = ?", (amount, user_id))
        conn.commit()
        conn.close()

def send_stats(chat_id):
    today = get_today()
    with db_lock:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        
        c.execute("SELECT SUM(invite_count) FROM users")
        total_invites_row = c.fetchone()
        total_invites = total_invites_row[0] if total_invites_row[0] else 0
        
        c.execute("SELECT prize, count FROM wins ORDER BY count DESC")
        win_rows = c.fetchall()
        win_lines = "\n".join([f"• {r['prize']}: *{r['count']}* kez" for r in win_rows]) or "_Henüz veri yok_"
        
        c.execute("SELECT id, name, username, bonus_spins FROM users WHERE last_spin_date = ?", (today,))
        today_rows = c.fetchall()
        conn.close()

    user_lines = []
    for r in today_rows[:20]:
        name  = r["name"] or "?"
        uname = f" @{r['username']}" if r["username"] else ""
        bonus = r["bonus_spins"]
        bonus_str = f" (+{bonus})" if bonus > 0 else ""
        user_lines.append(f"• {name}{uname}{bonus_str} `{r['id']}`")

    user_list = "\n".join(user_lines) if user_lines else "_Henüz kimse çevirmedi_"
    if len(today_rows) > 20:
        user_list += f"\n_... ve {len(today_rows)-20} kişi daha_"

    bot.send_message(
        chat_id,
        f"*Bot İstatistikleri*\n\n"
        f"Toplam kullanıcı: *{total_users}*\n"
        f"Bugün spin: *{len(today_rows)}*\n"
        f"Toplam davet: *{total_invites}*\n\n"
        f"*Kazanılan Ödüller:*\n{win_lines}\n\n"
        f"*Bugün Çevirenler:*\n{user_list}",
        parse_mode="Markdown"
    )

# ── Flask rotaları ────────────────────────────────────────────────────
@app.route('/')
def home():
    return "Bot Aktif!", 200

@app.route('/admin/rapor_indir')
def excel_indir():
    secret = request.args.get('sifre')
    if secret != "VIP_MUDUR_2026":
        return "Yetkisiz Erisim", 403

    with db_lock:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT user_id, name, prize, date_time FROM spin_logs ORDER BY id DESC")
        rows = c.fetchall()
        conn.close()

    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['Kullanici ID', 'Isim Soyisim', 'Kazanilan Odul', 'Tarih'])
    for r in rows:
        cw.writerow([r['user_id'], r['name'], r['prize'], r['date_time']])
    
    # utf-8-sig kullanıyoruz ki Excel Türkçe karakterleri ve verileri düzgün okusun
    return Response(
        si.getvalue().encode('utf-8-sig'),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=BetorSpin_Rapor_2026.csv"}
    )

@app.route('/wheel')
def wheel():
    return send_from_directory('.', 'index.html')

@app.route('/api/get_user_data')
def api_get_user_data():
    user_id = request.args.get('user_id', type=int)
    if not user_id:
        return jsonify({"allowed": False, "reason": "no_id"})
    
    with db_lock:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, boscoin FROM users WHERE id = ?", (user_id,))
        row = c.fetchone()
        if not row:
            c.execute("INSERT INTO users (id, name, username, boscoin) VALUES (?, ?, ?, 0)", (user_id, 'Bilinmiyor', ''))
            conn.commit()
            boscoin = 0
        else:
            boscoin = row["boscoin"]
        conn.close()

    spins = available_spins(user_id)
    return jsonify({"allowed": spins > 0, "spins": spins, "boscoin": boscoin})

@app.route('/api/use_spin', methods=['POST'])
def api_use_spin():
    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')
    if not user_id:
        return jsonify({"ok": False, "reason": "no_user_id"})
    user_id = int(user_id)
    
    name = data.get('name') or 'Bilinmiyor'
    username = data.get('username') or ''
    register_user(user_id, name, username)

    if available_spins(user_id) <= 0:
        return jsonify({"ok": False, "reason": "no_spins"})

    use_spin(user_id)

    PRIZES = [
        {"win": True, "prize": "10 BOSCOIN", "amount": 10},
        {"win": True, "prize": "50 BOSCOIN", "amount": 50},
        {"win": True, "prize": "5 BOSCOIN", "amount": 5},
        {"win": False, "prize": None, "amount": 0},
        {"win": True, "prize": "100 BOSCOIN", "amount": 100},
        {"win": True, "prize": "+1 Spin", "amount": 0},
        {"win": True, "prize": "10 BOSCOIN", "amount": 10},
        {"win": True, "prize": "200 BOSCOIN (VİP)", "amount": 200},
        {"win": False, "prize": None, "amount": 0},
    ]
    
    index = random.randint(0, 8)
    result = PRIZES[index]
    prize = result["prize"]
    win = result["win"]
    amount = result["amount"]

    current_time = datetime.now(timezone(timedelta(hours=3))).strftime("%Y-%m-%d %H:%M:%S")

    with db_lock:
        conn = get_db()
        c = conn.cursor()
        
        if amount > 0:
            c.execute("UPDATE users SET boscoin = boscoin + ? WHERE id = ?", (amount, user_id))
            
        c.execute("SELECT boscoin FROM users WHERE id = ?", (user_id,))
        current_boscoin = c.fetchone()["boscoin"]
        
        # Log Kaydı
        log_prize = prize if prize else "KAYBETTİN"
        c.execute("INSERT INTO spin_logs (user_id, name, prize, date_time) VALUES (?, ?, ?, ?)", 
                 (user_id, name, log_prize, current_time))

        if win and prize:
            c.execute("SELECT count FROM wins WHERE prize = ?", (prize,))
            if c.fetchone():
                c.execute("UPDATE wins SET count = count + 1 WHERE prize = ?", (prize,))
            else:
                c.execute("INSERT INTO wins (prize, count) VALUES (?, 1)", (prize,))
        
        conn.commit()
        conn.close()
        
        if prize == "+1 Spin":
            add_bonus_spin(user_id, 1)

    def delayed_message():
        time.sleep(8.5)
        try:
            if win and prize:
                if prize == "+1 Spin":
                    bot.send_message(
                        user_id,
                        f"*Tebrikler {name}!*\n\n*+1 Spin* kazandın! Çarkı tekrar çevirebilirsin.",
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("Şans Çarkını Tekrar Çevir", web_app=WebAppInfo(url=f"{MINI_APP_URL}?user_id={user_id}")))
                    )
                else:
                    bot.send_message(
                        user_id,
                        f"*Tebrikler {name}!*\n\nÇarktan *{prize}* kazandın! Puan cüzdanına başarıyla yüklendi.\nMağazaya uğrayıp hediyeni almayı unutma!",
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("Uygulamaya Dön ve Mağazaya Gir", web_app=WebAppInfo(url=f"{MINI_APP_URL}?user_id={user_id}")))
                    )
            else:
                bot.send_message(
                    user_id,
                    f"*Bu sefer olmadı {name}!*\n\nArkadaşını davet et, *+1 Spin* kazan!",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("Arkadaşını Davet Et +1 Spin", callback_data="get_invite_link"))
                )
        except Exception as e:
            print(f"Hata: {e}")

    threading.Thread(target=delayed_message, daemon=True).start()

    return jsonify({
        "ok": True,
        "segment_index": index,
        "win": win,
        "prize": prize,
        "boscoin": current_boscoin
    })

@app.route('/api/buy_item', methods=['POST'])
def api_buy_item():
    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')
    item_id = data.get('item_id')
    
    STORE = {
        "freespin": {"price": 300, "name": "100 Freespin", "code": "BOSFS100GO"},
        "bonusbuy": {"price": 500, "name": "100₺ Bonus Buy", "code": "BOSBYB"},
        "vip": {"price": 1000, "name": "VİP Hediye", "code": "BOSBBH"}
    }
    
    if not user_id or item_id not in STORE:
        return jsonify({"ok": False, "reason": "invalid_request"})
        
    item = STORE[item_id]
    
    with db_lock:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT boscoin, name FROM users WHERE id = ?", (user_id,))
        row = c.fetchone()
        
        if not row or row["boscoin"] < item["price"]:
            conn.close()
            return jsonify({"ok": False, "reason": "insufficient_funds"})
            
        new_balance = row["boscoin"] - item["price"]
        c.execute("UPDATE users SET boscoin = ? WHERE id = ?", (new_balance, user_id))
        
        c.execute("INSERT INTO spin_logs (user_id, name, prize, date_time) VALUES (?, ?, ?, ?)", 
                 (user_id, row["name"], f"SATIN ALIM: {item['name']}", datetime.now(timezone(timedelta(hours=3))).strftime("%Y-%m-%d %H:%M:%S")))
                 
        conn.commit()
        conn.close()
        
    return jsonify({"ok": True, "code": item["code"], "new_balance": new_balance})

# ── /start ────────────────────────────────────────────────────────────
@bot.message_handler(commands=['start'])
def start(message):
    try:
        user_id   = message.from_user.id
        args      = message.text.split()
        ref_param = args[1] if len(args) > 1 else None

        name = message.from_user.first_name or "Bilinmiyor"
        username = message.from_user.username or ""

        with db_lock:
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT inviter_id FROM users WHERE id = ?", (user_id,))
            row = c.fetchone()
            is_new_user = row is None

            # Yeni kullanıcı referans ile gelmişse
            if ref_param and ref_param.startswith("ref_"):
                try:
                    inviter_id = int(ref_param.split("_")[1])
                    if inviter_id != user_id and is_new_user:
                        c.execute("SELECT id, invite_count FROM users WHERE id = ?", (inviter_id,))
                        inviter_row = c.fetchone()
                        if inviter_row:
                            c.execute("UPDATE users SET invite_count = invite_count + 1, bonus_spins = bonus_spins + 1 WHERE id = ?", (inviter_id,))
                            try:
                                inviter_count = inviter_row["invite_count"] + 1
                                bot.send_message(
                                    inviter_id,
                                    f"*Tebrikler!*\n\n"
                                    f"*{name}* davet linkinle katıldı!\n"
                                    f"*+1 Ekstra Spin Hakkı* kazandın!\n\n"
                                    f"Toplam davet: *{inviter_count}*",
                                    parse_mode="Markdown"
                                )
                            except:
                                pass
                        
                        c.execute("INSERT INTO users (id, name, username, inviter_id) VALUES (?, ?, ?, ?)", (user_id, name, username, inviter_id))
                    else:
                        if is_new_user:
                            c.execute("INSERT INTO users (id, name, username) VALUES (?, ?, ?)", (user_id, name, username))
                        else:
                            c.execute("UPDATE users SET name = ?, username = ? WHERE id = ?", (name, username, user_id))
                except:
                    if is_new_user:
                        c.execute("INSERT INTO users (id, name, username) VALUES (?, ?, ?)", (user_id, name, username))
            else:
                if is_new_user:
                    c.execute("INSERT INTO users (id, name, username) VALUES (?, ?, ?)", (user_id, name, username))
                else:
                    c.execute("UPDATE users SET name = ?, username = ? WHERE id = ?", (name, username, user_id))
            
            conn.commit()
            conn.close()

        spins = available_spins(user_id)
        spin_status = f"*{spins} spin hakkın seni bekliyor!*" if spins > 0 else "*Bugünkü spin hakkını kullandın. Yarın tekrar gel!*"

        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(InlineKeyboardButton(
            text="Şans Çarkını Çevir",
            web_app=WebAppInfo(url=f"{MINI_APP_URL}?user_id={user_id}")
        ))

        text = (
            "*HOŞ GELDİN, KAZANMAYA HAZIR MISIN?*\n\n"
            f"{spin_status}\n\n"
            "*BetorSpin* çarkına adım attın, şansını deneme zamanı!\n\n"
            "*Şans Çarkın seni bekliyor:*\n"
            "• 500 TL Bonus\n"
            "• 100 Freespin\n"
            "• Büyük Ödül\n"
            "• ve daha fazlası...\n\n"
            "Gecikmeden çevir, kazanmaya hemen başla!\n"
            "Aşağıdaki butona bas ve ilk spini ücretsiz kazan!"
        )

        try:
            bot.send_animation(chat_id=message.chat.id, animation=GIF_URL, caption=text, reply_markup=markup, parse_mode="Markdown")
        except:
            bot.send_message(chat_id=message.chat.id, text=text, reply_markup=markup, parse_mode="Markdown")

        print(f"✅ /start: {user_id}")
    except Exception as e:
        print(f"❌ HATA: {e}")
        bot.send_message(message.chat.id, "Teknik bir sorun var.")

# ── /davet ────────────────────────────────────────────────────────────
@bot.message_handler(commands=['davet'])
def davet(message):
    user_id = message.from_user.id
    bot_info = bot.get_me()
    invite_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
    
    with db_lock:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT invite_count, bonus_spins FROM users WHERE id = ?", (user_id,))
        row = c.fetchone()
        conn.close()
        
    count = row["invite_count"] if row else 0
    bonus = row["bonus_spins"] if row else 0

    bot.send_message(
        message.chat.id,
        f"*Arkadaşını Davet Et, Spin Kazan!*\n\n"
        f"Her davet ettiğin kişi bota katılınca *+1 Spin* hakkı kazanırsın!\n\n"
        f"*Davet Linkin:*\n`{invite_link}`\n\n"
        f"*İstatistiklerin:*\n"
        f"• Davet ettiğin kişi: *{count}*\n"
        f"• Mevcut bonus spin: *{bonus}*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("Linki Paylaş", switch_inline_query=f"Betorspin Şans Çarkı'nı dene! {invite_link}")
        )
    )

# ── Davet callback ────────────────────────────────────────────────────
@bot.callback_query_handler(func=lambda c: c.data == "get_invite_link")
def send_invite_link(call):
    user_id = call.from_user.id
    bot_info = bot.get_me()
    invite_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
    
    with db_lock:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT invite_count, bonus_spins FROM users WHERE id = ?", (user_id,))
        row = c.fetchone()
        conn.close()
        
    count = row["invite_count"] if row else 0
    bonus = row["bonus_spins"] if row else 0

    bot.answer_callback_query(call.id)
    bot.send_message(
        call.message.chat.id,
        f"*Davet Linkin Hazır!*\n\n"
        f"Arkadaşın bu linkle katılınca *+1 Spin* kazanırsın\n\n"
        f"*Linkin:*\n`{invite_link}`\n\n"
        f"• Davet sayın: *{count}*\n"
        f"• Bonus spin: *{bonus}*",
        parse_mode="Markdown"
    )

# ── /stats ve /admin ──────────────────────────────────────────────────
@bot.message_handler(commands=['stats', 'admin'])
def admin_stats(message):
    user_id = message.from_user.id
    print(f"/{message.text.split()[0][1:]} komutu: {user_id} | Adminler: {ADMIN_IDS}")
    if not is_admin(user_id):
        bot.reply_to(message, "Yetkisiz erişim.")
        return
    send_stats(message.chat.id)

@bot.message_handler(commands=['logs'])
def admin_logs(message):
    user_id = message.from_user.id
    if not is_admin(user_id): return
    
    args = message.text.split()
    page = 1
    if len(args) > 1 and args[1].isdigit():
        page = int(args[1])
        if page < 1: page = 1
        
    limit = 50
    offset = (page - 1) * limit
    
    with db_lock:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT name, prize, date_time FROM spin_logs ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset))
        rows = c.fetchall()
        
        c.execute("SELECT COUNT(*) as total FROM spin_logs")
        total_logs = c.fetchone()["total"]
        conn.close()
    
    if not rows:
        bot.reply_to(message, f"Sayfa {page}'de henüz hiç kayıt yok.")
        return
        
    total_pages = (total_logs + limit - 1) // limit
    lines = [f"📋 *Çevirme Kayıtları (Sayfa {page}/{total_pages})*"]
    for r in rows:
        dt = r['date_time'][5:16]
        lines.append(f"• *{r['name']}* ➜ {r['prize']} ({dt})")
        
    if page < total_pages:
        lines.append(f"\n_Sonraki sayfa için komut: /logs {page+1}_")
        
    bot.reply_to(message, "\n".join(lines), parse_mode="Markdown")

# ── Diğer mesajlar ────────────────────────────────────────────────────
@bot.message_handler(func=lambda m: m.text and not m.text.startswith('/'))
def fallback(message):
    bot.reply_to(message, "Lütfen /start yazın.")

# ── Bot polling ───────────────────────────────────────────────────────
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
    app.run(host="0.0.0.0", port=port)
