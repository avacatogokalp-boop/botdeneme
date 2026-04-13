import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
import threading
import os
import time
import json
from datetime import datetime, timezone
from flask import Flask, send_from_directory, request, jsonify

TOKEN = os.environ.get("BOT_TOKEN")
SITE_LINKI = "https://cutt.ly/deoKNC0g"
GIF_URL = "https://i.ibb.co/QvJ5mZCY/14-07-25-Bonus-Gif-Betor-Spin-250x250.gif"
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://botdeneme.onrender.com")
MINI_APP_URL = f"{RENDER_URL}/wheel"
ADMIN_IDS = [6943377103]  # Buraya şefin ID'sini de ekleyebilirsin: [6943377103, SEFİN_ID]

spin_log     = {}
bonus_spins  = {}
invite_map   = {}
invite_count = {}
user_info    = {}
total_wins   = {}
spin_lock    = threading.Lock()

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# ── Yardımcı ─────────────────────────────────────────────────────────
def is_admin(user_id: int) -> bool:
    return int(user_id) in ADMIN_IDS

def get_today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def can_spin(user_id: int) -> bool:
    if is_admin(user_id):
        return True
    if bonus_spins.get(user_id, 0) > 0:
        return True
    today = get_today()
    with spin_lock:
        return spin_log.get(user_id) != today

def use_spin(user_id: int):
    if is_admin(user_id):
        return
    if bonus_spins.get(user_id, 0) > 0:
        with spin_lock:
            bonus_spins[user_id] -= 1
        return
    today = get_today()
    with spin_lock:
        spin_log[user_id] = today

def available_spins(user_id: int) -> int:
    if is_admin(user_id):
        return 99
    today = get_today()
    with spin_lock:
        daily = 0 if spin_log.get(user_id) == today else 1
        bonus = bonus_spins.get(user_id, 0)
    return daily + bonus

def add_bonus_spin(user_id: int, amount: int = 1):
    with spin_lock:
        bonus_spins[user_id] = bonus_spins.get(user_id, 0) + amount

def today_spin_users():
    today = get_today()
    with spin_lock:
        return [uid for uid, date in spin_log.items() if date == today]

def send_stats(chat_id):
    today_users   = today_spin_users()
    total_users   = len(user_info)
    total_invites = sum(invite_count.values())

    win_lines = "\n".join(
        [f"• {k}: *{v}* kez" for k, v in sorted(total_wins.items(), key=lambda x: -x[1])]
    ) or "_Henüz veri yok_"

    user_lines = []
    for uid in today_users[:20]:
        info  = user_info.get(uid, {})
        name  = info.get("name", "?")
        uname = f" @{info['username']}" if info.get("username") else ""
        bonus = bonus_spins.get(uid, 0)
        bonus_str = f" (+{bonus}🎡)" if bonus else ""
        user_lines.append(f"• {name}{uname}{bonus_str} `{uid}`")

    user_list = "\n".join(user_lines) if user_lines else "_Henüz kimse çevirmedi_"
    if len(today_users) > 20:
        user_list += f"\n_... ve {len(today_users)-20} kişi daha_"

    bot.send_message(
        chat_id,
        f"📊 *Bot İstatistikleri*\n\n"
        f"👥 Toplam kullanıcı: *{total_users}*\n"
        f"🎡 Bugün spin: *{len(today_users)}*\n"
        f"📤 Toplam davet: *{total_invites}*\n\n"
        f"🏆 *Kazanılan Ödüller:*\n{win_lines}\n\n"
        f"📅 *Bugün Çevirenler:*\n{user_list}",
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
    spins = available_spins(user_id)
    return jsonify({"allowed": spins > 0, "spins": spins})

@app.route('/api/use_spin', methods=['POST'])
def api_use_spin():
    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')
    if not user_id:
        return jsonify({"ok": False})
    use_spin(int(user_id))
    return jsonify({"ok": True})

# ── /start ────────────────────────────────────────────────────────────
@bot.message_handler(commands=['start'])
def start(message):
    try:
        user_id   = message.from_user.id
        args      = message.text.split()
        ref_param = args[1] if len(args) > 1 else None

        if ref_param and ref_param.startswith("ref_"):
            try:
                inviter_id = int(ref_param.split("_")[1])
                if inviter_id != user_id and user_id not in invite_map:
                    invite_map[user_id] = inviter_id
                    with spin_lock:
                        invite_count[inviter_id] = invite_count.get(inviter_id, 0) + 1
                    add_bonus_spin(inviter_id, 1)
                    try:
                        new_name = message.from_user.first_name or "Biri"
                        bot.send_message(
                            inviter_id,
                            f"🎉 *Tebrikler!*\n\n"
                            f"👤 *{new_name}* davet linkinle katıldı!\n"
                            f"🎡 *+1 Ekstra Spin Hakkı* kazandın!\n\n"
                            f"Toplam davet: *{invite_count.get(inviter_id, 0)}*",
                            parse_mode="Markdown"
                        )
                    except:
                        pass
            except:
                pass

        user_info[user_id] = {
            "name": message.from_user.first_name or "Bilinmiyor",
            "username": message.from_user.username or ""
        }

        spins = available_spins(user_id)
        spin_status = f"🎡 *{spins} spin hakkın seni bekliyor!*" if spins > 0 else "⏳ *Bugünkü spin hakkını kullandın. Yarın tekrar gel!*"

        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(InlineKeyboardButton(
            text="🎰 Şans Çarkını Çevir!",
            web_app=WebAppInfo(url=f"{MINI_APP_URL}?user_id={user_id}")
        ))
        markup.add(InlineKeyboardButton(
            text="👥 Arkadaşını Davet Et → +1 Spin",
            callback_data="get_invite_link"
        ))
        markup.row(
            InlineKeyboardButton(text="🔥 Hemen Oyna & Kazan 🎰", url=SITE_LINKI),
            InlineKeyboardButton(text="🌐 Siteye Git", url=SITE_LINKI)
        )

        text = (
            "🎰 *Hoş Geldin!*\n\n"
            f"{spin_status}\n"
            "🎁 *%300 Hoş Geldin Bonusu*\n\n"
            "👇 Şans çarkını çevirmek için butona tıkla!"
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
    count = invite_count.get(user_id, 0)
    bonus = bonus_spins.get(user_id, 0)

    bot.send_message(
        message.chat.id,
        f"👥 *Arkadaşını Davet Et, Spin Kazan!*\n\n"
        f"Her davet ettiğin kişi bota katılınca *+1 Spin* hakkı kazanırsın!\n\n"
        f"🔗 *Davet Linkin:*\n`{invite_link}`\n\n"
        f"📊 *İstatistiklerin:*\n"
        f"• Davet ettiğin kişi: *{count}*\n"
        f"• Mevcut bonus spin: *{bonus}*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("📤 Linki Paylaş", switch_inline_query=f"Betorspin Şans Çarkı'nı dene! {invite_link}")
        )
    )

# ── Davet callback ────────────────────────────────────────────────────
@bot.callback_query_handler(func=lambda c: c.data == "get_invite_link")
def send_invite_link(call):
    user_id = call.from_user.id
    bot_info = bot.get_me()
    invite_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
    count = invite_count.get(user_id, 0)
    bonus = bonus_spins.get(user_id, 0)

    bot.answer_callback_query(call.id)
    bot.send_message(
        call.message.chat.id,
        f"👥 *Davet Linkin Hazır!*\n\n"
        f"Arkadaşın bu linkle katılınca *+1 Spin* kazanırsın 🎡\n\n"
        f"🔗 *Linkin:*\n`{invite_link}`\n\n"
        f"• Davet sayın: *{count}*\n"
        f"• Bonus spin: *{bonus}*",
        parse_mode="Markdown"
    )

# ── /stats ve /admin — ikisi de aynı fonksiyonu çağırır ──────────────
@bot.message_handler(commands=['stats', 'admin'])
def admin_stats(message):
    user_id = message.from_user.id
    print(f"📊 /{message.text.split()[0][1:]} komutu: {user_id} | Admin listesi: {ADMIN_IDS}")
    if not is_admin(user_id):
        bot.reply_to(message, "⛔ Yetkisiz erişim.")
        return
    send_stats(message.chat.id)

# ── Web app data ──────────────────────────────────────────────────────
@bot.message_handler(content_types=['web_app_data'])
def handle_web_app_data(message):
    try:
        data  = json.loads(message.web_app_data.data)
        user  = message.from_user
        name  = user.first_name or "Kullanıcı"

        if data.get("win") and data.get("prize"):
            prize = data["prize"]
            with spin_lock:
                total_wins[prize] = total_wins.get(prize, 0) + 1
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
                f"Arkadaşını davet et, *+1 Spin* kazan! 👇",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup().add(
                    InlineKeyboardButton("👥 Arkadaşını Davet Et → +1 Spin", callback_data="get_invite_link")
                ).add(
                    InlineKeyboardButton("🔥 Siteye Git", url=SITE_LINKI)
                )
            )
        print(f"🎡 Spin sonucu: {user.id} -> {data}")
    except Exception as e:
        print(f"❌ WebApp data hatası: {e}")

# ── Diğer mesajlar ────────────────────────────────────────────────────
@bot.message_handler(func=lambda m: m.text and not m.text.startswith('/'))
def fallback(message):
    bot.reply_to(message, "Lütfen /start yazın. 🎰")

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
