import os
import sqlite3
from flask import Flask, g, jsonify, render_template, request

app = Flask(__name__)
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
    db = get_db()
    db.execute("""CREATE TABLE IF NOT EXISTS users 
                  (username TEXT PRIMARY KEY)""")
    db.execute("""CREATE TABLE IF NOT EXISTS messages 
                  (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, message TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS friends 
                  (username TEXT, friend_username TEXT)""")
    db.commit()

# Her istekten önce veritabanı tablolarının olduğundan emin oluyoruz (Yoksa otomatik kurar)
@app.before_request
def before_request():
    init_db()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/login", methods=["POST"])
def login():
    data = request.json or {}
    username = data.get("username", "").strip()
    if not username:
        return jsonify({"success": False, "error": "Kullanıcı adı boş olamaz!"})

    db = get_db()
    db.execute("INSERT OR IGNORE INTO users (username) VALUES (?)", (username,))
    db.commit()
    return jsonify({"success": True, "username": username})

@app.route("/api/messages", methods=["GET", "POST"])
def handle_messages():
    db = get_db()
    if request.method == "POST":
        data = request.json or {}
        username = data.get("username")
        message = data.get("message")
        if username and message:
            db.execute(
                "INSERT INTO messages (username, message) VALUES (?, ?)",
                (username, message),
            )
            db.commit()
            return jsonify({"success": True})
        return jsonify({"success": False})
    else:
        cursor = db.execute("SELECT username, message FROM messages")
        messages = [
            {"username": row["username"], "message": row["message"]}
            for row in cursor.fetchall()
        ]
        return jsonify({"success": True, "messages": messages})

@app.route("/api/friends", methods=["GET", "POST"])
def handle_friends():
    db = get_db()
    if request.method == "POST":
        data = request.json or {}
        username = data.get("username")
        friend_username = data.get("friend_username")

        user_check = db.execute(
            "SELECT * FROM users WHERE username = ?", (friend_username,)
        ).fetchone()
        if not user_check:
            return jsonify({"success": False, "error": "Böyle bir kullanıcı yok!"})

        db.execute(
            "INSERT INTO friends (username, friend_username) VALUES (?, ?)",
            (username, friend_username),
        )
        db.commit()
        return jsonify({"success": True})
    else:
        username = request.args.get("username")
        cursor = db.execute(
            "SELECT friend_username FROM friends WHERE username = ?", (username,)
        )
        friends = [row["friend_username"] for row in cursor.fetchall()]
        return jsonify({"success": True, "friends": friends})

@app.route("/api/reset", methods=["POST"])
def reset_account():
    data = request.json or {}
    username = data.get("username")
    if username:
        db = get_db()
        db.execute("DELETE FROM users WHERE username = ?", (username,))
        db.execute("DELETE FROM messages WHERE username = ?", (username,))
        db.execute(
            "DELETE FROM friends WHERE username = ? OR friend_username = ?",
            (username, username),
        )
        db.commit()
        return jsonify({"success": True})
    return jsonify({"success": False})

if __name__ == "__main__":
    app.run(debug=True)
