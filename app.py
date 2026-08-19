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
        db.execute("""CREATE TABLE IF NOT EXISTS friendships 
                      (username TEXT, friend_username TEXT, status TEXT)""")
        db.execute("""CREATE TABLE IF NOT EXISTS messages 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, receiver TEXT, is_group INTEGER, message TEXT)""")
        db.execute("""CREATE TABLE IF NOT EXISTS groups 
                      (group_name TEXT, username TEXT)""")
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

@app.route("/api/friend-request", methods=["POST", "GET"])
def handle_friend_requests():
    db = get_db()
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        username = data.get("username")
        friend_username = data.get("friend_username", "").strip()

        if not friend_username or username == friend_username:
            return jsonify({"success": False, "error": "Geçersiz kullanıcı adı!"})

        user_check = db.execute("SELECT * FROM users WHERE username = ?", (friend_username,)).fetchone()
        if not user_check:
            return jsonify({"success": False, "error": "Böyle bir kullanıcı yok!"})

        existing = db.execute("SELECT * FROM friendships WHERE (username = ? AND friend_username = ?) OR (username = ? AND friend_username = ?)", 
                              (username, friend_username, friend_username, username)).fetchone()
        if existing:
            return jsonify({"success": False, "error": "Zaten istek atılmış veya arkadaşsınız!"})

        db.execute("INSERT INTO friendships (username, friend_username, status) VALUES (?, ?, ?)", (username, friend_username, 'pending'))
        db.commit()
        return jsonify({"success": True})
    else:
        username = request.args.get("username")
        pending = db.execute("SELECT f.username, u.avatar FROM friendships f LEFT JOIN users u ON f.username = u.username WHERE f.friend_username = ? AND f.status = 'pending'", (username,)).fetchall()
        
        friends_cursor = db.execute("""
            SELECT CASE WHEN username = ? THEN friend_username ELSE username END as fname, u.avatar 
            FROM friendships f 
            LEFT JOIN users u ON u.username = CASE WHEN username = ? THEN friend_username ELSE username END
            WHERE (username = ? OR friend_username = ?) AND status = 'accepted'
        """, (username, username, username, username))

        friends = []
        for row in friends_cursor.fetchall():
            if row["fname"]:
                friends.append({"friend_username": row["fname"], "avatar": row["avatar"] or ""})

        return jsonify({
            "success": True, 
            "pending": [{"username": r["username"], "avatar": r["avatar"] or ""} for r in pending],
            "friends": friends
        })

@app.route("/api/friend-action", methods=["POST"])
def friend_action():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    friend_username = data.get("friend_username")
    action = data.get("action")

    db = get_db()
    if action == "accept":
        db.execute("UPDATE friendships SET status = 'accepted' WHERE username = ? AND friend_username = ?", (friend_username, username))
    else:
        db.execute("DELETE FROM friendships WHERE username = ? AND friend_username = ?", (friend_username, username))
    db.commit()
    return jsonify({"success": True})

@app.route("/api/groups", methods=["POST", "GET"])
def handle_groups():
    db = get_db()
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        group_name = data.get("group_name", "").strip()
        members = data.get("members", [])
        if not group_name:
            return jsonify({"success": False, "error": "Grup adı boş olamaz!"})
        
        for m in members:
            db.execute("INSERT INTO groups (group_name, username) VALUES (?, ?)", (group_name, m))
        db.commit()
        return jsonify({"success": True})
    else:
        username = request.args.get("username")
        cursor = db.execute("SELECT DISTINCT group_name FROM groups WHERE username = ?", (username,))
        groups = [{"group_name": row["group_name"]} for row in cursor.fetchall()]
        return jsonify({"success": True, "groups": groups})

@app.route("/api/messages", methods=["GET", "POST"])
def handle_messages():
    db = get_db()
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        username = data.get("username")
        receiver = data.get("receiver")
        is_group = data.get("is_group", 0)
        message = data.get("message")
        if username and message:
            db.execute(
                "INSERT INTO messages (username, receiver, is_group, message) VALUES (?, ?, ?, ?)",
                (username, receiver, is_group, message),
            )
            db.commit()
            return jsonify({"success": True})
        return jsonify({"success": False})
    else:
        username = request.args.get("username")
        receiver = request.args.get("receiver")
        is_group = int(request.args.get("is_group", 0))

        if is_group:
            cursor = db.execute("""
                SELECT m.username, m.message, u.avatar 
                FROM messages m 
                LEFT JOIN users u ON m.username = u.username 
                WHERE m.receiver = ? AND m.is_group = 1
            """, (receiver,))
        else:
            cursor = db.execute("""
                SELECT m.username, m.message, u.avatar 
                FROM messages m 
                LEFT JOIN users u ON m.username = u.username 
                WHERE (m.username = ? AND m.receiver = ?) OR (m.username = ? AND m.receiver = ?)
            """, (username, receiver, receiver, username))

        messages = [{"username": row["username"], "message": row["message"], "avatar": row["avatar"]} for row in cursor.fetchall()]
        return jsonify({"success": True, "messages": messages})

@app.route("/api/reset", methods=["POST"])
def reset_account():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    if username:
        db = get_db()
        db.execute("DELETE FROM users WHERE username = ?", (username,))
        db.execute("DELETE FROM messages WHERE username = ? OR receiver = ?", (username, username))
        db.execute("DELETE FROM friendships WHERE username = ? OR friend_username = ?", (username, username))
        db.execute("DELETE FROM groups WHERE username = ?", (username,))
        db.commit()
        return jsonify({"success": True})
    return jsonify({"success": False})

if __name__ == "__main__":
    app.run(debug=True)
