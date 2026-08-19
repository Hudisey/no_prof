from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

# Bellek tabanlı veritabanı
users_db = {}

@app.route('/')
def index():
    try:
        return render_template('index.html')
    except Exception as e:
        return f"Template hatası: {str(e)}", 500

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.json or {}
        username = data.get('username')
        if not username:
            return jsonify({"success": False, "error": "Kullanıcı adı gerekli!"}), 400
        
        if username not in users_db:
            users_db[username] = {
                "avatar": "",
                "pending": [],
                "friends": []
            }
        return jsonify({"success": True, "username": username})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/friend-request', methods=['GET', 'POST'])
def friend_request():
    try:
        if request.method == 'GET':
            username = request.args.get('username')
            user_data = users_db.get(username, {"pending": []})
            return jsonify({"pending": user_data.get("pending", [])})
        
        data = request.json or {}
        sender = data.get('username')
        receiver = data.get('friend_username')
        
        if not receiver or receiver not in users_db:
            return jsonify({"success": False, "error": "Kullanıcı bulunamadı!"}), 404
            
        if sender == receiver:
            return jsonify({"success": False, "error": "Kendine istek atamazsın!"}), 400
            
        receiver_data = users_db[receiver]
        if "pending" not in receiver_data:
            receiver_data["pending"] = []
            
        existing_senders = [p["username"] for p in receiver_data["pending"]]
        if sender in existing_senders:
            return jsonify({"success": False, "error": "Zaten istek atılmış!"}), 400
            
        receiver_data["pending"].append({"username": sender})
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/friend-action', methods=['POST'])
def friend_action():
    try:
        data = request.json or {}
        username = data.get('username')
        friend_username = data.get('friend_username')
        
        if username in users_db and "pending" in users_db[username]:
            users_db[username]["pending"] = [p for p in users_db[username]["pending"] if p["username"] != friend_username]
            
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/avatar', methods=['POST'])
def avatar():
    try:
        data = request.json or {}
        username = data.get('username')
        avatar_data = data.get('avatar')
        
        if username in users_db:
            users_db[username]["avatar"] = avatar_data
            return jsonify({"success": True})
        return jsonify({"success": False}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/reset', methods=['POST'])
def reset():
    try:
        data = request.json or {}
        username = data.get('username')
        if username in users_db:
            del users_db[username]
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
