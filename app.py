import os
import sqlite3
from flask import Flask, g, jsonify, render_template, request

app = Flask(__name__, template_folder='.')
DATABASE = "noprof.db"

def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        db.execute("""CREATE TABLE IF NOT EXISTS users 
                      (username TEXT PRIMARY KEY, avatar TEXT)""")
        db.execute("""CREATE TABLE IF NOT EXISTS messages 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, friend_username TEXT, message TEXT)""")
        db.execute("""CREATE TABLE IF NOT EXISTS friends 
                      (username TEXT, friend_username TEXT)""")
        db.commit()

init_db()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    if not username:
        return jsonify({"success": False, "error": "Kullanıcı adı boş olamaz!"})

    db = get_db()
    # Kullanıcı yoksa varsayılan avatar ile oluştur, varsa güncelleme yapma
    db.execute("INSERT OR IGNORE INTO users (username, avatar) VALUES (?, ?)", 
               (username, "https://api.dicebear.com/7.x/identicon/svg?seed=" + username))
    db.commit()
    
    user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    return jsonify({"success": True, "username": user["username"], "avatar": user["avatar"]})

@app.route("/api/avatar", methods=["POST"])
def update_avatar():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    avatar = data.get("avatar", "").strip()
    if username and avatar:
        db = get_db()
        db.execute("UPDATE users SET avatar = ? WHERE username = ?", (avatar, username))
        db.commit()
        return jsonify({"success": True})
    return jsonify({"success": False})

@app.route("/api/friends", methods=["GET", "POST"])
def handle_friends():
    db = get_db()
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        username = data.get("username")
        friend_username = data.get("friend_username", "").strip()

        if not friend_username:
            return jsonify({"success": False, "error": "Boş olamaz"})

        user_check = db.execute("SELECT * FROM users WHERE username = ?", (friend_username,)).fetchone()
        if not user_check:
            return jsonify({"success": False, "error": "Böyle bir kullanıcı yok!"})

        existing = db.execute("SELECT * FROM friends WHERE username = ? AND friend_username = ?", (username, friend_username)).fetchone()
        if not existing:
            db.execute("INSERT INTO friends (username, friend_username) VALUES (?, ?)", (username, friend_username))
            db.commit()

        return jsonify({"success": True})
    else:
        username = request.args.get("username")
        cursor = db.execute("""
            SELECT f.friend_username, u.avatar 
            FROM friends f 
            LEFT JOIN users u ON f.friend_username = u.username 
            WHERE f.username = ?
        """, (username,))
        friends = [{"friend_username": row["friend_username"], "avatar": row["avatar"] or ""} for row in cursor.fetchall()]
        return jsonify({"success": True, "friends": friends})

@app.route("/api/messages", methods=["GET", "POST"])
def handle_messages():
    db = get_db()
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        username = data.get("username")
        friend_username = data.get("friend_username")
        message = data.get("message")
        if username and message:
            db.execute(
                "INSERT INTO messages (username, friend_username, message) VALUES (?, ?, ?)",
                (username, friend_username, message),
            )
            db.commit()
            return jsonify({"success": True})
        return jsonify({"success": False})
    else:
        username = request.args.get("username")
        friend_username = request.args.get("friend_username")
        cursor = db.execute("""
            SELECT m.username, m.message, u.avatar 
            FROM messages m 
            LEFT JOIN users u ON m.username = u.username 
            WHERE (m.username = ? AND m.friend_username = ?) OR (m.username = ? AND m.friend_username = ?)
        """, (username, friend_username, friend_username, username))
        messages = [{"username": row["username"], "message": row["message"], "avatar": row["avatar"]} for row in cursor.fetchall()]
        return jsonify({"success": True, "messages": messages})

@app.route("/api/reset", methods=["POST"])
def reset_account():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    if username:
        db = get_db()
        db.execute("DELETE FROM users WHERE username = ?", (username,))
        db.execute("DELETE FROM messages WHERE username = ? OR friend_username = ?", (username, username))
        db.execute("DELETE FROM friends WHERE username = ? OR friend_username = ?", (username, username))
        db.commit()
        return jsonify({"success": True})
    return jsonify({"success": False})

if __name__ == "__main__":
    app.run(debug=True)
