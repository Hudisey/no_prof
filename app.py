from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

users_db = {}

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>NOPROF</title>
    <style>
        :root { --bg: #000; --surface: #111; --border: #222; --text: #eee; --accent: #222; --accent-hover: #333; }
        [data-theme="light"] { --bg: #f4f4f4; --surface: #fff; --border: #ddd; --text: #111; --accent: #e4e4e4; --accent-hover: #d4d4d4; }
        * { box-sizing: border-box; margin: 0; padding: 0; transition: background 0.2s ease, color 0.2s ease, border 0.2s ease, transform 0.1s ease; }
        body { background: var(--bg); color: var(--text); font-family: monospace; height: 100vh; display: flex; overflow: hidden; }
        .hidden { display: none !important; }
        #login-screen { display: flex; flex-direction: column; justify-content: center; align-items: center; width: 100%; height: 100%; gap: 12px; }
        .logo-title { font-size: 32px; font-weight: bold; letter-spacing: 2px; }
        .logo-subtitle { font-size: 11px; color: #737373; margin-top: -8px; }
        #app-screen { display: flex; width: 100%; height: 100%; }
        .sidebar { width: 300px; background: var(--surface); border-right: 1px solid var(--border); padding: 15px; display: flex; flex-direction: column; gap: 10px; position: relative; }
        .chat-main { flex: 1; display: flex; flex-direction: column; }
        #chat-box { flex: 1; padding: 20px; overflow-y: auto; }
        .msg-input-area { padding: 20px; border-top: 1px solid var(--border); display: flex; gap: 10px; }
        #requests-dropdown { position: absolute; top: 120px; left: 15px; width: 270px; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 10px; z-index: 100; box-shadow: 0 4px 12px rgba(0,0,0,0.5); }
        .req-item { display: flex; justify-content: space-between; align-items: center; padding: 6px 0; border-bottom: 1px solid var(--border); font-size: 12px; }
        .bell-container { position: relative; display: inline-block; }
        .discord-badge { background: #ed4245; color: white; font-size: 9px; width: 15px; height: 15px; border-radius: 50%; display: flex; align-items: center; justify-content: center; position: absolute; top: -4px; right: -4px; font-weight: bold; }
        #settings-menu { position: absolute; bottom: 65px; left: 15px; right: 15px; background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 10px; z-index: 100; display: flex; flex-direction: column; gap: 6px; box-shadow: 0 8px 24px rgba(0,0,0,0.6); }
        .settings-btn { background: var(--accent); border: 1px solid var(--border); color: var(--text); padding: 8px 12px; border-radius: 6px; cursor: pointer; text-align: left; font-family: monospace; font-size: 12px; display: flex; align-items: center; gap: 8px; }
        .settings-btn:hover { background: var(--accent-hover); transform: translateY(-1px); }
        .settings-btn.danger { color: #ed4245; border-color: rgba(237,66,69,0.3); }
        .settings-btn.danger:hover { background: rgba(237,66,69,0.1); }
        input, button { background: var(--accent); border: 1px solid var(--border); color: var(--text); padding: 8px 12px; border-radius: 6px; font-family: monospace; cursor: pointer; }
        input:focus { outline: none; border-color: #555; }
        button:hover { background: var(--accent-hover); }
        button:active { transform: scale(0.98); }
    </style>
</head>
<body data-theme="dark">
    <div id="login-screen">
        <div class="logo-title">NOPROF</div>
        <div class="logo-subtitle">(made by hudisey)</div>
        <input type="text" id="username-input" placeholder="Kullanıcı adı..." style="width: 220px; margin-top: 10px;">
        <button onclick="login()" style="width: 220px;">GİRİŞ YAP</button>
    </div>
    <div id="app-screen" class="hidden">
        <div class="sidebar">
            <h3 id="sidebar-title" style="font-size: 14px;">SOHBETLER</h3>
            <div style="display: flex; gap: 5px;">
                <input type="text" id="friend-input" placeholder="Arkadaş ekle..." style="flex:1;">
                <button onclick="sendFriendRequest()">+</button>
                <div class="bell-container">
                    <button onclick="toggleRequests()">🔔</button>
                    <span id="req-badge" class="discord-badge hidden">0</span>
                </div>
            </div>
            <div id="requests-dropdown" class="hidden">
                <div id="req-title" style="font-size: 10px; color: #888; margin-bottom: 6px;">GELEN İSTEKLER</div>
                <div id="requests-list"></div>
            </div>
            <div id="friend-box" style="flex:1; overflow-y: auto; margin-top: 5px;"></div>
            <button onclick="toggleSettings()" class="settings-btn" style="justify-content: center; font-weight: bold;">⚙️ AYARLAR</button>
            <div id="settings-menu" class="hidden">
                <button onclick="toggleTheme()" class="settings-btn">🌓 Tema Değiştir</button>
                <button onclick="toggleLang()" class="settings-btn">🌍 Dil Değiştir (TR/EN)</button>
                <button onclick="deleteAccount()" class="settings-btn danger">❌ Hesabı Sil</button>
            </div>
        </div>
        <div class="chat-main">
            <div id="chat-box"></div>
            <div class="msg-input-area">
                <input type="text" id="msg-input" style="flex:1" placeholder="Mesaj yaz...">
                <button onclick="sendMessage()">GÖNDER</button>
            </div>
        </div>
    </div>
    <script>
        let currentUser = localStorage.getItem('noprof_user');
        let isTr = true;
        function login() {
            const usernameInput = document.getElementById('username-input').value.trim();
            if(!usernameInput) return;
            fetch('/api/login', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username: usernameInput})
            }).then(r => r.json()).then(data => {
                currentUser = data.username || usernameInput;
                localStorage.setItem('noprof_user', currentUser);
                document.getElementById('login-screen').classList.add('hidden');
                document.getElementById('app-screen').classList.remove('hidden');
                loadData();
            });
        }
        function toggleLang() {
            isTr = !isTr;
            document.getElementById('sidebar-title').innerText = isTr ? "SOHBETLER" : "CHATS";
            document.getElementById('req-title').innerText = isTr ? "GELEN İSTEKLER" : "FRIEND REQUESTS";
            document.getElementById('friend-input').placeholder = isTr ? "Arkadaş ekle..." : "Add friend...";
            loadData();
        }
        function toggleTheme() {
            const current = document.body.getAttribute('data-theme');
            document.body.setAttribute('data-theme', current === 'dark' ? 'light' : 'dark');
        }
        function toggleSettings() { document.getElementById('settings-menu').classList.toggle('hidden'); }
        function toggleRequests() { document.getElementById('requests-dropdown').classList.toggle('hidden'); }
        async function sendFriendRequest() {
            const friend_username = document.getElementById('friend-input').value.trim();
            if(!friend_username) return;
            const res = await fetch('/api/friend-request', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username: currentUser, friend_username})
            });
            const resData = await res.json();
            if(res.ok) {
                alert(isTr ? "İstek başarıyla gönderildi!" : "Request sent successfully!");
                document.getElementById('friend-input').value = '';
            } else {
                alert(resData.error || (isTr ? "İstek gönderilemedi!" : "Failed to send request!"));
            }
        }
        async function respondRequest(friend_username, action) {
            await fetch('/api/friend-action', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username: currentUser, friend_username, action})
            });
            loadData();
        }
        async function deleteAccount() {
            if(confirm(isTr ? "Hesabını silmek istediğine emin misin?" : "Are you sure you want to delete your account?")) {
                await fetch('/api/reset', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({username: currentUser})});
                localStorage.removeItem('noprof_user');
                location.reload();
            }
        }
        async function loadData() {
            if(!currentUser) return;
            try {
                const reqRes = await fetch(`/api/friend-request?username=${encodeURIComponent(currentUser)}`);
                const data = await reqRes.json();
                const reqList = document.getElementById('requests-list');
                const badge = document.getElementById('req-badge');
                if (data.pending && data.pending.length > 0) {
                    badge.classList.remove('hidden');
                    badge.innerText = data.pending.length;
                    reqList.innerHTML = data.pending.map(p => `
                        <div class="req-item">
                            <span style="font-weight:bold;">${p.username}</span>
                            <div style="display:flex; gap:4px;">
                                <button onclick="respondRequest('${p.username}', 'accept')" style="padding:2px 6px; font-size:11px;">✓</button>
                                <button onclick="respondRequest('${p.username}', 'reject')" style="padding:2px 6px; font-size:11px; color:#ed4245;">✕</button>
                            </div>
                        </div>
                    `).join('');
                } else {
                    badge.classList.add('hidden');
                    reqList.innerHTML = `<div style="font-size:11px; color:#737373; text-align:center; padding: 6px;">${isTr ? 'İstek yok.' : 'No requests.'}</div>`;
                }
            } catch(e) {}
        }
        function sendMessage() {
            const msg = document.getElementById('msg-input').value.trim();
            if(!msg) return;
            document.getElementById('msg-input').value = '';
        }
        if(currentUser) {
            document.getElementById('login-screen').classList.add('hidden');
            document.getElementById('app-screen').classList.remove('hidden');
            loadData();
            setInterval(loadData, 4000);
        }
    </script>
</body>
</html>"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json or {}
    username = data.get('username')
    if not username:
        return jsonify({"success": False, "error": "Kullanıcı adı gerekli!"}), 400
    if username not in users_db:
        users_db[username] = {"pending": [], "friends": []}
    return jsonify({"success": True, "username": username})

@app.route('/api/friend-request', methods=['GET', 'POST'])
def friend_request():
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

@app.route('/api/friend-action', methods=['POST'])
def friend_action():
    data = request.json or {}
    username = data.get('username')
    friend_username = data.get('friend_username')
    
    if username in users_db and "pending" in users_db[username]:
        users_db[username]["pending"] = [p for p in users_db[username]["pending"] if p["username"] != friend_username]
    return jsonify({"success": True})

@app.route('/api/reset', methods=['POST'])
def reset():
    data = request.json or {}
    username = data.get('username')
    if username in users_db:
        del users_db[username]
    return jsonify({"success": True})

if __name__ == '__main__':
    app.run(debug=True)
