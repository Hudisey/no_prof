import os
from flask import Flask, jsonify, render_template, request

# HTML dosyalarının app.py ile aynı klasörde olduğunu belirtiyoruz
app = Flask(__name__, template_folder='.')

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    if not username:
        return jsonify({"success": False, "error": "Kullanıcı adı boş olamaz!"})
    return jsonify({"success": True, "username": username})

@app.route("/api/messages", methods=["GET", "POST"])
def handle_messages():
    if request.method == "POST":
        return jsonify({"success": True})
    return jsonify({"success": True, "messages": []})

@app.route("/api/friends", methods=["GET", "POST"])
def handle_friends():
    if request.method == "POST":
        return jsonify({"success": True})
    return jsonify({"success": True, "friends": []})

@app.route("/api/reset", methods=["POST"])
def reset_account():
    return jsonify({"success": True})

if __name__ == "__main__":
    app.run(debug=True)
