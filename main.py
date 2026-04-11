from flask import Flask, request, jsonify
from flask_cors import CORS
import time

app = Flask(__name__)
CORS(app) # Telegram Web App izinleri

# 👑 BURASI SENİN SINIRSIZ GÜCÜN
# Kendi Telegram ID'ni tırnak içine yaz (Örn: "123456789")
ADMIN_ID = "6943377103" 

# Geçici hafıza (Kullanıcı ID -> Çevirme Zamanı)
user_spins = {}
COOLDOWN_MS = 24 * 60 * 60 * 1000 # 24 Saat

@app.route('/api/check', methods=['GET'])
def check_spin():
    user_id = request.args.get('user_id')
    
    # EĞER GELEN KİŞİ SENSEN, BEKLEME SÜRESİNİ SIFIRLA VE ONAY VER!
    if str(user_id) == ADMIN_ID:
        return jsonify({"can_spin": True, "is_admin": True})

    last_spin = user_spins.get(user_id)

    # Hiç çevirmediyse hak ver
    if not last_spin:
        return jsonify({"can_spin": True, "is_admin": False})

    # Çevirdiyse süreyi kontrol et
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
        user_spins[user_id] = time.time() * 1000
        return jsonify({"success": True})
    
    return jsonify({"error": "User ID required"}), 400

if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
