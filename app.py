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
        #chat-box { flex: 1; padding: 20px; overflow-y: auto; display: flex; flex-direction: column; gap: 6px; color: #555; }
        #chat-box.empty { align-items: center; justify-content: center; }
        .msg-row { display: flex; width: 100%; }
        .msg-row.sent { justify-content: flex-end; }
        .msg-row.received { justify-content: flex-start; }
        .msg-bubble { max-width: 60%; padding: 8px 12px; border-radius: 12px; font-size: 13px; word-wrap: break-word; }
        .msg-row.sent .msg-bubble { background: #2b6cb0; color: #fff; border-bottom-right-radius: 2px; }
        .msg-row.received .msg-bubble { background: var(--accent); color: var(--text); border-bottom-left-radius: 2px; }
        .msg-input-area { padding: 20px; border-top: 1px solid var(--border); display: flex; gap: 10px; }
        #requests-dropdown { position: absolute; top: 120px; left: 15px; width: 270px; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 10px; z-index: 100; box-shadow: 0 4px 12px rgba(0,0,0,0.5); }
        .req-item { display: flex; justify-content: space-between; align-items: center; padding: 6px 0; border-bottom: 1px solid var(--border); font-size: 12px; }
        .friend-item { display: flex; align-items: center; gap: 10px; padding: 8px; border-radius: 6px; cursor: pointer; border: 1px solid transparent; }
        .friend-item:hover { background: var(--accent); border-color: var(--border); }
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
            <div id="friend-box" style="flex:1; overflow-y: auto; margin-top: 5px; display: flex; flex-direction: column; gap: 4px;"></div>
            <button onclick="toggleSettings()" class="settings-btn" style="justify-content: center; font-weight: bold;">⚙️ AYARLAR</button>
            <div id="settings-menu" class="hidden">
                <button onclick="toggleTheme()" class="settings-btn">🌓 Tema Değiştir</button>
                <button onclick="toggleLang()" class="settings-btn">🌍 Dil Değiştir (TR/EN)</button>
                <button onclick="document.getElementById('avatar-input').click()" class="settings-btn">🖼️ Profil Resmi Ekle</button>
                <button onclick="deleteAccount()" class="settings-btn danger">❌ Hesabı Sil</button>
                <input type="file" id="avatar-input" class="hidden" onchange="uploadAvatar(this)">
            </div>
        </div>
        <div class="chat-main">
            <div id="chat-box">Bir sohbet seçin</div>
            <div class="msg-input-area hidden" id="msg-area">
                <input type="text" id="msg-input" style="flex:1" placeholder="Mesaj yaz...">
                <button onclick="sendMessage()">GÖNDER</button>
            </div>
        </div>
    </div>
    <script>
        let currentUser = localStorage.getItem('noprof_user');
        let currentChat = null;
        let isTr = true;
        let pollingStarted = false;

        function login() {
            const usernameInput = document.getElementById('username-input').value.trim();
            if(!usernameInput) return;
            fetch('/api/login', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username: usernameInput})
            }).then(r => r.json()).then(data => {
                if(data.success) {
                    currentUser = data.username;
                    localStorage.setItem('noprof_user', currentUser);
                    document.getElementById('login-screen').classList.add('hidden');
                    document.getElementById('app-screen').classList.remove('hidden');
                    startPolling();
                }
            });
        }

        function startPolling() {
            loadData();
            if(!pollingStarted) {
                pollingStarted = true;
                setInterval(loadData, 3000);
            }
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
            if(!friend_username || !currentUser) return;
            
            const res = await fetch('/api/friend-request', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username: currentUser, friend_username: friend_username})
            });
            const resData = await res.json();
            if(res.ok && resData.success) {
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

        function openChat(username) {
            currentChat = username;
            const box = document.getElementById('chat-box');
            box.classList.add('empty');
            box.innerHTML = `<div style="color:#888; font-size:13px;">${username} ile sohbet başlıyor...</div>`;
            document.getElementById('msg-area').classList.remove('hidden');
        }

        async function uploadAvatar(input) {
            const file = input.files[0];
            if(!file) return;
            const reader = new FileReader();
            reader.onload = async (e) => {
                await fetch('/api/avatar', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({username: currentUser, avatar: e.target.result})
                });
                alert(isTr ? "Profil güncellendi!" : "Profile updated!");
            };
            reader.readAsDataURL(file);
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
                const res = await fetch(`/api/user-data?username=${encodeURIComponent(currentUser)}`);
                const data = await res.json();
                
                const reqList = document.getElementById('requests-list');
                const badge =
