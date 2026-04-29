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
from concurrent.futures import ThreadPoolExecutor

TOKEN = os.environ.get("BOT_TOKEN")
SITE_LINKI = "https://cutt.ly/7tF5Ow3K"
GIF_URL = 
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://botdeneme.onrender.com")
MINI_APP_URL = f"{RENDER_URL}/wheel"
ADMIN_IDS = [6943377103, 8284892694, 6659874588]  # Şefin ve ekibin ID'leri
message_executor = ThreadPoolExecutor(max_workers=20)

db_lock = threading.Lock()

DB_PATH = "/var/data/database.sqlite" if os.path.isdir("/var/data") else "database.sqlite"

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=2000")
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
        
        try:
            c.execute("ALTER TABLE spin_logs ADD COLUMN status TEXT DEFAULT 'processed'")
        except sqlite3.OperationalError:
            pass
            
        try:
            c.execute("ALTER TABLE users ADD COLUMN last_harvest_time TEXT DEFAULT '2026-01-01 00:00:00'")
        except sqlite3.OperationalError:
            pass
            
        c.execute('''CREATE TABLE IF NOT EXISTS user_quests (
            user_id INTEGER,
            quest_id TEXT,
            date_time TEXT,
            PRIMARY KEY (user_id, quest_id)
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
        headers={"Content-Disposition": "attachment; filename=FarmSpin_Rapor_2026.csv"}
    )

@app.route('/admin/kullanici_raporu')
def kullanici_excel_indir():
    secret = request.args.get('sifre')
    if secret != "VIP_MUDUR_2026":
        return "Yetkisiz Erisim", 403

    with db_lock:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, name, username, invite_count, boscoin, last_spin_date FROM users ORDER BY boscoin DESC")
        rows = c.fetchall()
        conn.close()

    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['Kullanici ID', 'Isim Soyisim', 'Kullanici Adi', 'Davet Sayisi', 'Cuzdan (COIN)', 'Son Spin'])
    for r in rows:
        cw.writerow([r['id'], r['name'], r['username'], r['invite_count'], r['boscoin'], r['last_spin_date']])
    
    return Response(
        si.getvalue().encode('utf-8-sig'),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=Kullanici_Cuzdanlari_Rapor.csv"}
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
            
        if is_admin(user_id) and boscoin < 900000:
            c.execute("UPDATE users SET boscoin = 999999 WHERE id = ?", (user_id,))
            conn.commit()
            boscoin = 999999
            
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
        {"win": True, "prize": "+1 Spin", "amount": 0},   # %10
        {"win": True, "prize": "200 COIN", "amount": 200},    # %10
        {"win": True, "prize": "150 COIN", "amount": 150},    # %30
        {"win": True, "prize": "100 COIN", "amount": 100},    # %30
        {"win": True, "prize": "75 COIN", "amount": 75},      # %10
        {"win": True, "prize": "50 COIN", "amount": 50},      # %5
        {"win": False, "prize": "TİLKİ!", "amount": -50},     # %5 (Was 25 COIN)
    ]
    
    # RTP Olasılıkları (Toplam 100): 
    # [+1 FS: 10, 200: 10, 150: 30, 100: 30, 75: 10, 50: 5, 25: 5]
    weights = [10, 10, 30, 30, 10, 5, 5]
    
    # Ağırlıklı seçim yapalım
    indices = list(range(len(PRIZES)))
    index = random.choices(indices, weights=weights, k=1)[0]
    result = PRIZES[index]
    prize = result["prize"]
    win = result["win"]
    amount = result["amount"]

    current_time = datetime.now(timezone(timedelta(hours=3))).strftime("%Y-%m-%d %H:%M:%S")

    with db_lock:
        conn = get_db()
        c = conn.cursor()
        
        c.execute("SELECT boscoin FROM users WHERE id = ?", (user_id,))
        current_boscoin = c.fetchone()["boscoin"]
        
        if amount > 0:
            c.execute("UPDATE users SET boscoin = boscoin + ? WHERE id = ?", (amount, user_id))
            current_boscoin += amount
        elif amount < 0:
            new_amount = max(0, current_boscoin + amount)
            c.execute("UPDATE users SET boscoin = ? WHERE id = ?", (new_amount, user_id))
            current_boscoin = new_amount
        
        # Log Kaydı
        log_prize = prize if prize else "KAYBETTİN"
        c.execute("INSERT INTO spin_logs (user_id, name, prize, date_time, status) VALUES (?, ?, ?, ?, ?)", 
                 (user_id, name, log_prize, current_time, 'processed'))

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
        time.sleep(12.5)
        try:
            if win and prize:
                if prize == "+1 Spin":
                    bot.send_message(
                        user_id,
                        f"*Tebrikler {name}!*\n\n*+1 Spin* kazandın! Çarkı tekrar çevirebilirsin.",
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("Çarkı Tekrar Çevir", web_app=WebAppInfo(url=f"{MINI_APP_URL}?user_id={user_id}")))
                    )
                else:
                    bot.send_message(
                        user_id,
                        f"*Tebrikler {name}!*\n\nÇarktan *{prize}* kazandın! Coin cüzdanına başarıyla yüklendi.\nMağazaya uğrayıp çiftliğin için hayvan almayı unutma!",
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("Çiftliğe Dön ve Mağazaya Gir", web_app=WebAppInfo(url=f"{MINI_APP_URL}?user_id={user_id}")))
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

    message_executor.submit(delayed_message)

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
    farm_name = data.get('farm_name', 'Bilinmiyor')
    
    STORE = {
        "at":    {"price": 3000, "name": "At (Çiftlik Hayvanı)", "code": "FARM_AT"},
        "inek":    {"price": 2000, "name": "İnek (Çiftlik Hayvanı)", "code": "FARM_INEK"},
        "kopek": {"price": 1500, "name": "Köpek (Çiftlik Hayvanı)", "code": "FARM_KOPEK"},
        "domuz": {"price": 1000, "name": "Domuz (Çiftlik Hayvanı)", "code": "FARM_DOMUZ"},
        "koyun": {"price": 750,  "name": "Koyun (Çiftlik Hayvanı)", "code": "FARM_KOYUN"},
        "tavuk": {"price": 500,  "name": "Tavuk (Çiftlik Hayvanı)", "code": "FARM_TAVUK"}
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
        user_name_val = row["name"] or "Bilinmiyor"
        
        c.execute("UPDATE users SET boscoin = ? WHERE id = ?", (new_balance, user_id))
        
        c.execute("INSERT INTO spin_logs (user_id, name, prize, date_time, status) VALUES (?, ?, ?, ?, ?)", 
                 (user_id, user_name_val, f"SİPARİŞ (Çiftlik: {farm_name}): {item['name']}", datetime.now(timezone(timedelta(hours=3))).strftime("%Y-%m-%d %H:%M:%S"), 'pending'))
                 
        conn.commit()
        conn.close()
        
    try:
        if ADMIN_IDS:
            admin_msg = (
                f"🚨 *YENİ MAĞAZA SİPARİŞİ*\n\n"
                f"👤 *Telegram İsim:* {user_name_val} (`{user_id}`)\n"
                f"🚜 *Çiftlik Adı:* `{farm_name}`\n"
                f"🎁 *Sipariş:* {item['name']}\n"
                f"💰 *Kalan Cüzdan:* {new_balance} COIN\n\n"
                f"_(Kullanıcının hayvanını çiftliğine tanımlayabilirsiniz)_"
            )
            bot.send_message(ADMIN_IDS[0], admin_msg, parse_mode="Markdown")
    except Exception as e:
        print(f"Admin mesaj hatası: {e}")
        
    return jsonify({"ok": True, "new_balance": new_balance})

@app.route('/<path:filename>')
def serve_static(filename):
    if filename.endswith(('.wav', '.mp3', '.flac', '.png', '.jpg', '.gif')):
        return send_from_directory('.', filename)
    return "Erişim Engellendi", 403

@app.route('/api/get_history', methods=['GET'])
def api_get_history():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify([])
        
    with db_lock:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT prize, date_time, status FROM spin_logs WHERE user_id = ? AND prize LIKE 'SİPARİŞ%' ORDER BY id DESC LIMIT 10", (user_id,))
        rows = c.fetchall()
        conn.close()
        
    history = []
    for r in rows:
        raw_prize = r["prize"]
        site_user = "Bilinmiyor"
        if "Çiftlik: " in raw_prize and "): " in raw_prize:
            site_user = raw_prize.split("Çiftlik: ", 1)[1].split("):", 1)[0]
            contents = raw_prize.split("): ", 1)[-1]
        elif ": " in raw_prize:
            contents = raw_prize.split(": ", 1)[-1]
        else:
            contents = raw_prize
            
        history.append({
            "content": contents,
            "site_user": site_user,
            "date": r["date_time"][:16],
            "status": "Beklemede" if r["status"] == "pending" else "Onaylandı"
        })
        
    return jsonify(history)

@app.route('/api/get_farm', methods=['GET'])
def api_get_farm():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({})
        
    with db_lock:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT prize FROM spin_logs WHERE user_id = ? AND prize LIKE 'SİPARİŞ%'", (user_id,))
        rows = c.fetchall()
        c.execute("SELECT name FROM users WHERE id = ?", (user_id,))
        user_row = c.fetchone()
        conn.close()
        
    farm_inventory = {
        "At": 0, "İnek": 0, "Köpek": 0, "Domuz": 0, "Koyun": 0, "Tavuk": 0
    }
    
    farm_name = user_row["name"] if user_row else "Çiftliğim"
    for r in rows:
        raw_prize = r["prize"]
        if "): " in raw_prize:
            animal_prize = raw_prize.split("): ", 1)[-1]
            animal_name = animal_prize.split(" (")[0]
            if animal_name in farm_inventory:
                farm_inventory[animal_name] += 1
            elif animal_prize in farm_inventory:
                farm_inventory[animal_prize] += 1
                
        if "Çiftlik: " in raw_prize and "): " in raw_prize:
            farm_name = raw_prize.split("Çiftlik: ", 1)[1].split("):", 1)[0]
            
    return jsonify({
        "farm_name": farm_name,
        "inventory": farm_inventory
    })

@app.route('/api/get_leaderboard', methods=['GET'])
def api_get_leaderboard():
    with db_lock:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT user_id, name, prize FROM spin_logs WHERE prize LIKE 'SİPARİŞ%'")
        rows = c.fetchall()
        conn.close()
        
    prices = { "At": 3000, "İnek": 2000, "Köpek": 1500, "Domuz": 1000, "Koyun": 750, "Tavuk": 500 }
    
    user_powers = {}
    for r in rows:
        uid = r["user_id"]
        uname = r["name"]
        raw_prize = r["prize"]
        
        animal_name = None
        if "): " in raw_prize:
            animal_prize = raw_prize.split("): ", 1)[-1]
            animal_name = animal_prize.split(" (")[0]
            
        power = prices.get(animal_name, 0) if animal_name else 0
        
        if uid not in user_powers:
            user_powers[uid] = {"name": uname, "power": 0}
        user_powers[uid]["power"] += power
        
    sorted_users = sorted(user_powers.values(), key=lambda x: x["power"], reverse=True)
    top_5 = sorted_users[:5]
    
    return jsonify(top_5)

@app.route('/api/harvest', methods=['POST'])
def api_harvest():
    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')
    if not user_id: return jsonify({"ok": False})
    
    with db_lock:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT last_harvest_time, boscoin FROM users WHERE id = ?", (user_id,))
        user_row = c.fetchone()
        
        if not user_row:
            conn.close()
            return jsonify({"ok": False})
            
        last_harvest_str = user_row["last_harvest_time"] or "2026-01-01 00:00:00"
        try:
            last_harvest_dt = datetime.strptime(last_harvest_str, "%Y-%m-%d %H:%M:%S")
            last_harvest_dt = last_harvest_dt.replace(tzinfo=timezone(timedelta(hours=3)))
        except:
            last_harvest_dt = datetime.now(timezone(timedelta(hours=3)))
            
        now_dt = datetime.now(timezone(timedelta(hours=3)))
        diff_hours = (now_dt - last_harvest_dt).total_seconds() / 3600.0
        
        # Max 24 saat birikebilir
        if diff_hours > 24: diff_hours = 24
        elif diff_hours < 0: diff_hours = 0
        
        # Get Animals
        c.execute("SELECT prize FROM spin_logs WHERE user_id = ? AND prize LIKE 'SİPARİŞ%'", (user_id,))
        rows = c.fetchall()
        
        rates = { "At": 30, "İnek": 20, "Köpek": 15, "Domuz": 10, "Koyun": 7.5, "Tavuk": 5 }
        hourly_rate = 0
        for r in rows:
            raw_prize = r["prize"]
            animal_name = None
            if "): " in raw_prize:
                animal_prize = raw_prize.split("): ", 1)[-1]
                animal_name = animal_prize.split(" (")[0]
            hourly_rate += rates.get(animal_name, 0) if animal_name else 0
            
        generated_coin = int(hourly_rate * diff_hours)
        
        if generated_coin > 0:
            new_boscoin = user_row["boscoin"] + generated_coin
            new_time_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")
            c.execute("UPDATE users SET boscoin = ?, last_harvest_time = ? WHERE id = ?", (new_boscoin, new_time_str, user_id))
            conn.commit()
            
        conn.close()
        
    return jsonify({"ok": True, "earned": generated_coin, "rate": hourly_rate})

@app.route('/api/get_quests', methods=['GET'])
def api_get_quests():
    user_id = request.args.get('user_id')
    if not user_id: return jsonify([])
    
    with db_lock:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT quest_id FROM user_quests WHERE user_id = ?", (user_id,))
        completed_quests = {row["quest_id"] for row in c.fetchall()}
        
        c.execute("SELECT prize FROM spin_logs WHERE user_id = ? AND prize LIKE 'SİPARİŞ%'", (user_id,))
        bought_animals_count = len(c.fetchall())
        
        c.execute("SELECT COUNT(*) as spins FROM spin_logs WHERE user_id = ? AND prize NOT LIKE 'SİPARİŞ%'", (user_id,))
        spin_count = c.fetchone()["spins"]
        conn.close()
        
    quests = [
        {"id": "q1", "title": "İlk Hayvanı Al", "desc": "Çiftliğine ilk hayvanını satın al.", "target": 1, "progress": bought_animals_count, "reward": "+1 SPİN"},
        {"id": "q2", "title": "Acemi Çiftçi", "desc": "Çarkı toplam 5 kez çevir.", "target": 5, "progress": spin_count, "reward": "500 COIN"},
        {"id": "q3", "title": "Büyük Çiftlik", "desc": "Çiftliğinde 5 hayvan barındır.", "target": 5, "progress": bought_animals_count, "reward": "+2 SPİN"}
    ]
    
    for q in quests:
        q["completed"] = q["id"] in completed_quests
        q["can_claim"] = (not q["completed"]) and (q["progress"] >= q["target"])
        
    return jsonify(quests)

@app.route('/api/claim_quest', methods=['POST'])
def api_claim_quest():
    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')
    quest_id = data.get('quest_id')
    if not user_id or not quest_id: return jsonify({"ok": False})
    
    with db_lock:
        conn = get_db()
        c = conn.cursor()
        
        c.execute("SELECT 1 FROM user_quests WHERE user_id = ? AND quest_id = ?", (user_id, quest_id))
        if c.fetchone():
            conn.close()
            return jsonify({"ok": False, "reason": "already_claimed"})
            
        c.execute("INSERT INTO user_quests (user_id, quest_id, date_time) VALUES (?, ?, ?)", 
                 (user_id, quest_id, datetime.now(timezone(timedelta(hours=3))).strftime("%Y-%m-%d %H:%M:%S")))
                 
        if quest_id == "q1":
            c.execute("UPDATE users SET bonus_spins = bonus_spins + 1 WHERE id = ?", (user_id,))
        elif quest_id == "q2":
            c.execute("UPDATE users SET boscoin = boscoin + 500 WHERE id = ?", (user_id,))
        elif quest_id == "q3":
            c.execute("UPDATE users SET bonus_spins = bonus_spins + 2 WHERE id = ?", (user_id,))
            
        conn.commit()
        conn.close()
        
    return jsonify({"ok": True})

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
            "🚜 *FarmSpin Çiftlik Dünyasına Hoş Geldiniz!*\n\n"
            f"{spin_status}\n\n"
            "Her gün çarkı çevirin, COIN biriktirin ve mağazadan çiftliğiniz için hayvanlar alın. "
            "Kazandığınız hayvanlar en kısa sürede çiftliğinize teslim edilir!"
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
            InlineKeyboardButton("Linki Paylaş", switch_inline_query=f"FarmSpin Çiftlik Çarkı'nı dene! {invite_link}")
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
        bot.reply_to(message, f"Son işlemler (Sayfa {page}): Kayıt yok.")
        return
        
    msg_lines = [f"*Son İşlemler (Sayfa {page})*"]
    for r in rows:
        msg_lines.append(f"• `{r['date_time'][:16]}` | {r['name']} | {r['prize']}")
        
    bot.reply_to(message, "\n".join(msg_lines), parse_mode="Markdown")

@bot.message_handler(commands=['bekleyenler'])
def admin_bekleyenler(message):
    user_id = message.from_user.id
    if not is_admin(user_id): return
    
    with db_lock:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, user_id, name, prize, date_time FROM spin_logs WHERE status = 'pending' ORDER BY id ASC")
        rows = c.fetchall()
        
        if not rows:
            conn.close()
            bot.reply_to(message, "✅ Şu an bekleyen/aktarılmamış hiçbir mağaza siparişi bulunmuyor.")
            return
            
        si = io.StringIO()
        cw = csv.writer(si)
        cw.writerow(["Kayit ID", "Kullanici ID", "Telegram Isim", "Siparis ve Ciftlik Adi", "Tarih"])
        for r in rows:
            cw.writerow([r['id'], r['user_id'], r['name'], r['prize'], r['date_time']])
            
        # Hepsini processed'e çevir
        c.execute("UPDATE spin_logs SET status = 'processed' WHERE status = 'pending'")
        conn.commit()
        conn.close()
        
    file_data = io.BytesIO(si.getvalue().encode('utf-8-sig'))
    file_data.name = f"Bekleyen_Siparisler_{datetime.now(timezone(timedelta(hours=3))).strftime('%d_%m_%H%M')}.csv"
    
    bot.send_document(
        message.chat.id, 
        file_data, 
        caption=f"📦 *Toplam {len(rows)} beklemedeki mağaza siparişi dışarı aktarıldı.*\n\n_Bu dosyadaki tüm işlemler otomatik olarak 'İşlendi (Processed)' durumuna getirildi ve bir daha listelenmeyecek._", 
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['siparisleri_onayla'])
def admin_siparis_onayla(message):
    user_id = message.from_user.id
    if not is_admin(user_id): return
    
    with db_lock:
        conn = get_db()
        c = conn.cursor()
        # Sadece bekleyen (pending) siparişleri bul
        c.execute("SELECT DISTINCT user_id, name FROM spin_logs WHERE status = 'pending'")
        users_to_notify = c.fetchall()
        
        if not users_to_notify:
            conn.close()
            bot.reply_to(message, "✅ Bildirim gönderilecek bekleyen sipariş bulunamadı.")
            return
            
        success_count = 0
        fail_count = 0
        
        # Site linkini buton olarak ekle
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Çiftliğine Git ve Kontrol Et", url=SITE_LINKI))
        
        msg_text = (
            "🎁 *Müjde! Bekleyen hayvanlarınız çiftliğinize ulaştı.*\n\n"
            "Hemen çiftliğinize giriş yaparak kontrol edebilirsiniz. Bol şanslar dileriz! 🚜"
        )
        
        for u in users_to_notify:
            try:
                bot.send_message(u['user_id'], msg_text, parse_mode="Markdown", reply_markup=markup)
                success_count += 1
            except Exception as e:
                print(f"Bildirim hatası ({u['user_id']}): {e}")
                fail_count += 1
        
        # Tüm bekleyenleri 'approved' yap
        c.execute("UPDATE spin_logs SET status = 'approved' WHERE status = 'pending'")
        conn.commit()
        conn.close()
        
    bot.reply_to(message, f"✅ *İşlem Tamamlandı!*\n\n• Başarıyla iletilen: *{success_count}*\n• İletilemeyen: *{fail_count}*\n\n_Sistemdeki tüm bekleyen siparişler 'İşlendi' olarak işaretlendi._", parse_mode="Markdown")

@bot.message_handler(commands=['coin_bas'])
def admin_coin_bas(message):
    user_id = message.from_user.id
    if not is_admin(user_id): return
    
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        bot.reply_to(message, "Kullanım: `/coin_bas 100` (Herkese 100 COIN ekler)", parse_mode="Markdown")
        return
        
    miktar = int(args[1])
    
    with db_lock:
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE users SET boscoin = boscoin + ?", (miktar,))
        conn.commit()
        
        c.execute("SELECT COUNT(id) as total FROM users")
        total_users = c.fetchone()["total"]
        conn.close()
        
    bot.reply_to(message, f"💸 Başarılı! Veritabanındaki tüm ({total_users}) üyelerin cüzdanına *{miktar} COIN* eklendi.", parse_mode="Markdown")

# ── Webhook / Polling ────────────────────────────────────────────────────
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
    app.run(host="0.0.0.0", port=port, threaded=True)
