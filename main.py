from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import time
import os

app = Flask(__name__)
CORS(app)

# 👑 SENİN TELEGRAM ID'N
ADMIN_ID = "6943377103" 

user_spins = {}
COOLDOWN_MS = 24 * 60 * 60 * 1000 

# --- SAYFAYI GÖSTEREN KISIM ---
@app.route('/')
@app.route('/wheel')
def serve_index():
    # index.html dosyasını ana dizinden okuyup tarayıcıya gönderir
    return send_from_directory('.', 'index.html')

# --- API KISIMLARI ---
@app.route('/api/check', methods=['GET'])
def check_spin():
    user_id = request.args.get('user_id')
    if str(user_id) == ADMIN_ID:
        return jsonify({"can_spin": True, "is_admin": True})

    last_spin = user_spins.get(user_id)
    if not last_spin:
        return jsonify({"can_spin": True, "is_admin": False})

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
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
