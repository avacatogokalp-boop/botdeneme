import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
import threading
import os
import time
import json
from datetime import datetime, timezone, timedelta
import sqlite3
import random
from flask import Flask, send_from_directory, request, jsonify

TOKEN = os.environ.get("BOT_TOKEN")
SITE_LINKI = "https://cutt.ly/7tF5Ow3K"
GIF_URL = "https://i.ibb.co/jPtFMZJC/0414.gif"
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://botdeneme.onrender.com")
MINI_APP_URL = f"{RENDER_URL}/wheel"
ADMIN_IDS = [6943377103]  # Şefin ID'sini eklemek için: [6943377103, SEFİN_ID]

db_lock = threading.Lock()

def get_db():
    conn = sqlite3.connect("database.sqlite", check_same_thread=False)
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
            invite_count INTEGER DEFAULT 0
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS wins (
            prize TEXT PRIMARY KEY,
            count INTEGER DEFAULT 0
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

@app.route('/wheel')
def wheel():
    return send_from_directory('.', 'index.html')

@app.route('/api/check_spin')
def check_spin():
    user_id = request.args.get('user_id', type=int)
    if not user_id:
        return jsonify({"allowed": False, "reason": "no_id"})
    
    with db_lock:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE id = ?", (user_id,))
        if not c.fetchone():
            c.execute("INSERT INTO users (id, name, username) VALUES (?, ?, ?)", (user_id, 'Bilinmiyor', ''))
            conn.commit()
        conn.close()

    spins = available_spins(user_id)
    return jsonify({"allowed": spins > 0, "spins": spins})

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
        {"win": True, "prize": "100 Freespin"},
        {"win": True, "prize": "Özel Yatırım Bonusu"},
        {"win": True, "prize": "100₺ Bakiye"},
        {"win": False, "prize": None},
        {"win": True, "prize": "100₺ Bonus Buy"},
        {"win": True, "prize": "200 Freespin"},
        {"win": True, "prize": "VİP Hediye"},
        {"win": True, "prize": "200₺ Bonus Buy"},
        {"win": False, "prize": None},
        {"win": True, "prize": "+1 Spin"},
    ]
    
    index = random.randint(0, 9)
    result = PRIZES[index]
    prize = result["prize"]
    win = result["win"]

    if win and prize:
        with db_lock:
            conn = get_db()
            c = conn.cursor()
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
                        f"*Tebrikler {name}!*\n\n"
                        f"*+1 Spin* kazandın! Çarkı tekrar çevirebilirsin.",
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup().add(
                            InlineKeyboardButton("Şans Çarkını Tekrar Çevir", web_app=WebAppInfo(url=f"{MINI_APP_URL}?user_id={user_id}"))
                        )
                    )
                else:
                    bot.send_message(
                        user_id,
                        f"*Tebrikler {name}!*\n\n"
                        f"Kazandığın ödül: *{prize}*\n\n"
                        f"Ödülünü almak için siteye gir!",
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup().add(
                            InlineKeyboardButton("SİTEYE GİT VE OYNA", url=SITE_LINKI)
                        )
                    )
            else:
                bot.send_message(
                    user_id,
                    f"*Bu sefer olmadı {name}!*\n\n"
                    f"Arkadaşını davet et, *+1 Spin* kazan!",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup().add(
                        InlineKeyboardButton("Arkadaşını Davet Et +1 Spin", callback_data="get_invite_link")
                    ).add(
                        InlineKeyboardButton("SİTEYE GİT VE OYNA", url=SITE_LINKI)
                    )
                )
        except Exception as e:
            print(f"Hata: {e}")

    threading.Thread(target=delayed_message, daemon=True).start()

    return jsonify({
        "ok": True,
        "segment_index": index,
        "win": win,
        "prize": prize
    })

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
