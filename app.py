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
    if db is not None: db.close()

def init_db():
    with app.app_context():
        db = get_db()
        db.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY)")
        db.execute("CREATE TABLE IF NOT EXISTS friendships (username TEXT, friend_username TEXT, status TEXT)")
        db.execute("CREATE TABLE IF NOT EXISTS messages (username TEXT, receiver TEXT, message TEXT)")
        db.commit()

init_db()

@app.route("/")
def index(): return render_template("index.html")

@app.route("/api/login", methods=["POST"])
def login():
    u = request.get_json()["username"]
    db = get_db()
    db.execute("INSERT OR IGNORE INTO users (username) VALUES (?)", (u,))
    db.commit()
    return jsonify({"success": True})

@app.route("/api/friends", methods=["GET", "POST"])
def friends():
    db = get_db()
    if request.method == "POST":
        data = request.get_json()
        if data["action"] == "add":
            db.execute("INSERT INTO friendships (username, friend_username, status) VALUES (?, ?, 'pending')", 
                       (data["u"], data["target"]))
        elif data["action"] == "accept":
            db.execute("UPDATE friendships SET status = 'accepted' WHERE username = ? AND friend_username = ?", 
                       (data["target"], data["u"]))
        else: # reject
            db.execute("DELETE FROM friendships WHERE username = ? AND friend_username = ?", 
                       (data["target"], data["u"]))
        db.commit()
        return jsonify({"success": True})
    else:
        u = request.args.get("u")
        pending = db.execute("SELECT username FROM friendships WHERE friend_username = ? AND status = 'pending'", (u,)).fetchall()
        accepted = db.execute("""
            SELECT friend_username as name FROM friendships WHERE username = ? AND status = 'accepted'
            UNION SELECT username FROM friendships WHERE friend_username = ? AND status = 'accepted'
        """, (u, u)).fetchall()
        return jsonify({"pending": [r["username"] for r in pending], "accepted": [r["name"] for r in accepted]})

@app.route("/api/messages", methods=["GET", "POST"])
def messages():
    db = get_db()
    if request.method == "POST":
        data = request.get_json()
        db.execute("INSERT INTO messages VALUES (?, ?, ?)", (data["u"], data["rec"], data["msg"]))
        db.commit()
        return jsonify({"success": True})
    u, rec = request.args.get("u"), request.args.get("rec")
    msgs = db.execute("SELECT * FROM messages WHERE (username=? AND receiver=?) OR (username=? AND receiver=?)", (u, rec, rec, u)).fetchall()
    return jsonify([dict(m) for m in msgs])

if __name__ == "__main__": app.run(debug=True)
