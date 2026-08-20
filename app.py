import os
import uuid
from flask import Flask, request, jsonify, render_template_string, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

users_db = {}
messages_db = {}
groups_db = {}          # group_id -> {"name": str, "owner": str, "members": [usernames]}
group_messages_db = {}  # group_id -> [{"from": username, "text": str}]

peer_ids = {}    # username -> latest PeerJS peer id
dm_calls = {}    # call_id -> {"from", "to", "participants": {username: peer_id}, "status": "ringing"|"active"}
group_calls = {} # group_id -> {"participants": {username: peer_id}}   (room only exists while non-empty)

def conv_key(a, b):
    return "|".join(sorted([a, b]))

def is_user_busy(username):
    for c in dm_calls.values():
        if username in c["participants"]:
            return True
    for c in group_calls.values():
        if username in c["participants"]:
            return True
    return False

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>NOPROF</title>
    <link rel="icon" type="image/png" href="/noprof.png">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/peerjs/1.5.2/peerjs.min.js"></script>
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
        .sidebar { width: 300px; max-width: 300px; background: var(--surface); border-right: 1px solid var(--border); padding: 15px; display: flex; flex-direction: column; gap: 10px; position: relative; overflow-x: hidden; box-sizing: border-box; }
        .chat-main { flex: 1; display: flex; flex-direction: column; }
        #chat-header { display: flex; align-items: center; gap: 10px; padding: 12px 20px; border-bottom: 1px solid var(--border); font-weight: bold; font-size: 14px; }
        #chat-box { flex: 1; padding: 20px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; color: #555; }
        #chat-box.empty { align-items: center; justify-content: center; }
        .msg-row { display: flex; width: 100%; }
        .msg-row.sent { justify-content: flex-end; }
        .msg-row.received { justify-content: flex-start; }
        .msg-bubble { max-width: 75%; padding: 12px 18px; border-radius: 18px; font-size: 16px; line-height: 1.4; word-wrap: break-word; }
        .msg-row.sent .msg-bubble { background: #2b6cb0; color: #fff; border-bottom-right-radius: 3px; }
        .msg-row.received .msg-bubble { background: var(--accent); color: var(--text); border-bottom-left-radius: 3px; }
        .msg-input-area { padding: 20px; border-top: 1px solid var(--border); display: flex; gap: 10px; }
        .friend-avatar { width: 30px; height: 30px; border-radius: 50%; object-fit: cover; flex-shrink: 0; }
        .friend-avatar-placeholder { width: 30px; height: 30px; background: #333; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; flex-shrink: 0; }
        .req-item { display: flex; justify-content: space-between; align-items: center; padding: 8px 4px; border-bottom: 1px solid var(--border); font-size: 12px; gap: 8px; }
        .req-actions { display: flex; gap: 8px; }
        .req-btn { width: 34px; height: 34px; border-radius: 50%; display: flex; align-items: center; justify-content: center; padding: 0; font-size: 17px; font-weight: bold; border: 1px solid transparent; line-height: 1; }
        .req-btn-accept { background: rgba(59,165,93,0.15); color: #3ba55d; border-color: rgba(59,165,93,0.4); }
        .req-btn-accept:hover { background: #3ba55d; color: #fff; transform: translateY(-1px) scale(1.05); }
        .req-btn-reject { background: rgba(237,66,69,0.12); color: #ed4245; border-color: rgba(237,66,69,0.35); }
        .req-btn-reject:hover { background: #ed4245; color: #fff; transform: translateY(-1px) scale(1.05); }
        .req-btn:active { transform: scale(0.92); }
        .self-info { display: flex; align-items: center; gap: 6px; min-width: 0; flex-shrink: 0; }
        #self-username { font-size: 12px; font-weight: bold; max-width: 80px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .sidebar-header-row { display: flex; justify-content: space-between; align-items: center; min-width: 0; gap: 8px; }
        .sidebar-header-row h3 { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex-shrink: 1; }
        #action-row { min-width: 0; flex-wrap: wrap; }
        #action-row input { min-width: 0; flex: 1 1 80px; }
        #action-row button, #action-row .bell-container { flex-shrink: 0; }
        #requests-dropdown, #group-create-dropdown { position: absolute; top: 120px; left: 15px; width: 270px; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 10px; z-index: 100; box-shadow: 0 4px 12px rgba(0,0,0,0.5); }
        .group-member-row { display: flex; align-items: center; gap: 8px; font-size: 12px; padding: 4px 2px; cursor: pointer; }
        .group-member-row input { cursor: pointer; }
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

        /* Arama / Çağrı */
        #chat-header-actions { margin-left: auto; display: flex; gap: 6px; }
        .header-icon-btn { width: 32px; height: 32px; border-radius: 50%; padding: 0; display: flex; align-items: center; justify-content: center; font-size: 14px; }
        .header-icon-btn.leave-btn { color: #ed4245; border-color: rgba(237,66,69,0.35); }

        #incoming-call-modal, #call-overlay { position: fixed; z-index: 1000; background: var(--surface); border: 1px solid var(--border); box-shadow: 0 10px 30px rgba(0,0,0,0.6); }
        #incoming-call-modal { top: 20px; right: 20px; width: 240px; border-radius: 12px; padding: 16px; text-align: center; }
        #incoming-call-modal .ic-caller { font-size: 13px; font-weight: bold; margin-bottom: 4px; }
        #incoming-call-modal .ic-sub { font-size: 11px; color: #888; margin-bottom: 12px; }
        #incoming-call-modal .ic-actions { display: flex; gap: 10px; justify-content: center; }

        #call-overlay { bottom: 20px; right: 20px; width: 250px; border-radius: 14px; padding: 14px; }
        #call-overlay .call-title { font-size: 12px; font-weight: bold; margin-bottom: 10px; display: flex; align-items: center; gap: 6px; color: #888; }
        #call-overlay .call-title .dot { width: 7px; height: 7px; border-radius: 50%; background: #3ba55d; }
        #call-participants { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 14px; min-height: 46px; }
        .call-avatar-wrap { display: flex; flex-direction: column; align-items: center; gap: 4px; width: 52px; }
        .call-avatar { width: 46px; height: 46px; border-radius: 50%; background: var(--accent); display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 15px; border: 2px solid transparent; }
        .call-avatar.speaking { border-color: #3ba55d; }
        .call-avatar.self-muted { opacity: 0.5; }
        .call-avatar-name { font-size: 9px; color: #888; max-width: 52px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .call-controls { display: flex; gap: 10px; justify-content: center; }
        .call-ctrl-btn { width: 42px; height: 42px; border-radius: 50%; padding: 0; display: flex; align-items: center; justify-content: center; font-size: 17px; }
        .call-ctrl-btn.hangup { background: #ed4245; color: #fff; border-color: #ed4245; }
        .call-ctrl-btn.muted { background: #ed4245; color: #fff; border-color: #ed4245; }
    </style>
</head>
<body data-theme="dark">
    <div id="login-screen">
        <div class="logo-title">NOPROF</div>
        <div class="logo-subtitle">(made by hudisey)</div>
        <input type="text" id="username-input" placeholder="Kullanıcı adı..." style="width: 220px; margin-top: 10px;">
        <input type="password" id="password-input" placeholder="Şifre..." style="width: 220px;" onkeydown="if(event.key==='Enter') login();">
        <button onclick="login()" style="width: 220px;">GİRİŞ YAP</button>
    </div>
    <div id="app-screen" class="hidden">
        <div id="incoming-call-modal" class="hidden">
            <div class="ic-caller" id="ic-caller-name"></div>
            <div class="ic-sub" id="ic-sub-text"></div>
            <div class="ic-actions">
                <button class="call-ctrl-btn req-btn-accept" style="background:#3ba55d;color:#fff;border-color:#3ba55d;" onclick="acceptDmCall()">📞</button>
                <button class="call-ctrl-btn hangup" onclick="declineDmCall()">✕</button>
            </div>
        </div>
        <div id="call-overlay" class="hidden">
            <div class="call-title"><span class="dot"></span><span id="call-title-text"></span></div>
            <div id="call-participants"></div>
            <div class="call-controls">
                <button class="call-ctrl-btn" id="call-mute-btn" onclick="toggleMute()" title="Mikrofonu kapat">🎙️</button>
                <button class="call-ctrl-btn hangup" onclick="leaveCall()" title="Aramadan ayrıl">📵</button>
            </div>
        </div>
        <div id="remote-audio-container" class="hidden"></div>
        <div class="sidebar">
            <div class="sidebar-header-row">
                <h3 id="sidebar-title" style="font-size: 14px;">SOHBETLER</h3>
                <div class="self-info">
                    <div id="self-avatar" class="friend-avatar-placeholder" style="width:26px; height:26px; font-size:11px;">?</div>
                    <span id="self-username"></span>
                </div>
            </div>
            <div id="action-row" style="display: flex; gap: 5px;">
                <input type="text" id="friend-input" placeholder="Arkadaş ekle..." style="flex:1;">
                <button onclick="sendFriendRequest()">+</button>
                <button onclick="toggleGroupCreate()" id="group-create-btn" title="Grup oluştur">👥</button>
                <div class="bell-container">
                    <button onclick="toggleRequests()">🔔</button>
                    <span id="req-badge" class="discord-badge hidden">0</span>
                </div>
            </div>
            <div id="requests-dropdown" class="hidden">
                <div id="req-title" style="font-size: 10px; color: #888; margin-bottom: 6px;">GELEN İSTEKLER</div>
                <div id="requests-list"></div>
            </div>
            <div id="group-create-dropdown" class="hidden">
                <div id="group-create-title" style="font-size: 10px; color: #888; margin-bottom: 6px;">GRUP OLUŞTUR</div>
                <input type="text" id="group-name-input" placeholder="Grup adı..." style="width:100%; margin-bottom:8px;">
                <div id="group-member-list" style="max-height:150px; overflow-y:auto; display:flex; flex-direction:column; margin-bottom:8px;"></div>
                <button onclick="createGroup()" style="width:100%;" id="group-create-submit">Oluştur</button>
            </div>
            <div id="chats-container" style="flex:1; overflow-y: auto; margin-top: 5px; display: flex; flex-direction: column; gap: 4px;">
                <div id="friend-box"></div>
                <div id="group-section-title" class="hidden" style="font-size:10px; color:#888; margin-top:10px;">GRUPLAR</div>
                <div id="group-box" style="display:flex; flex-direction:column; gap:4px;"></div>
            </div>
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
            <div id="chat-header" class="hidden"></div>
            <div id="chat-box" class="empty">Bir sohbet seçin</div>
            <div class="msg-input-area hidden" id="msg-area">
                <input type="text" id="msg-input" style="flex:1" placeholder="Mesaj yaz..." onkeydown="if(event.key==='Enter') sendMessage();">
                <button onclick="sendMessage()">GÖNDER</button>
            </div>
        </div>
    </div>
    <script>
        let currentUser = localStorage.getItem('noprof_user');
        let currentChat = null;
        let isTr = true;
        let pollingStarted = false;
        let friendsData = {};
        let chatPollInterval = null;
        let currentFriendsList = [];
        let groupsData = {};

        // --- Arama (PeerJS) durumu ---
        let peer = null;
        let localStream = null;
        let peerConnections = {};   // username -> MediaConnection
        let peerIdToUser = {};      // peer_id -> username
        let inCall = false;
        let currentCallId = null;   // dm call_id OR group_id
        let currentCallType = null; // 'dm' | 'group'
        let isMuted = false;
        let callPollInterval = null;      // global poll for incoming dm calls
        let groupCallPollInterval = null; // active while in a group call
        let incomingCall = null;    // {call_id, from}

        function escapeHtml(str) {
            const div = document.createElement('div');
            div.innerText = str;
            return div.innerHTML;
        }

        function updateSelfAvatar(avatarData) {
            const el = document.getElementById('self-avatar');
            if(!el) return;
            if(avatarData) {
                el.innerHTML = `<img src="${avatarData}" style="width:100%;height:100%;border-radius:50%;object-fit:cover;">`;
            } else {
                el.innerText = currentUser ? currentUser[0].toUpperCase() : '?';
            }
        }

        function setSelfUsername() {
            const el = document.getElementById('self-username');
            if(el) el.innerText = currentUser || '';
        }

        function resizeImage(file, maxSize) {
            maxSize = maxSize || 128;
            return new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = (e) => {
                    const img = new Image();
                    img.onload = () => {
                        let w = img.width, h = img.height;
                        if(w > h) { if(w > maxSize) { h = Math.round(h * maxSize / w); w = maxSize; } }
                        else { if(h > maxSize) { w = Math.round(w * maxSize / h); h = maxSize; } }
                        const canvas = document.createElement('canvas');
                        canvas.width = w; canvas.height = h;
                        canvas.getContext('2d').drawImage(img, 0, 0, w, h);
                        resolve(canvas.toDataURL('image/jpeg', 0.85));
                    };
                    img.onerror = reject;
                    img.src = e.target.result;
                };
                reader.onerror = reject;
                reader.readAsDataURL(file);
            });
        }

        function login() {
            const usernameInput = document.getElementById('username-input').value.trim();
            const passwordInput = document.getElementById('password-input').value;
            if(!usernameInput || !passwordInput) return;
            fetch('/api/login', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username: usernameInput, password: passwordInput})
            }).then(r => r.json()).then(data => {
                if(data.success) {
                    currentUser = data.username;
                    localStorage.setItem('noprof_user', currentUser);
                    document.getElementById('login-screen').classList.add('hidden');
                    document.getElementById('app-screen').classList.remove('hidden');
                    setSelfUsername();
                    initPeer();
                    startPolling();
                } else {
                    alert(data.error || (isTr ? "Giriş başarısız!" : "Login failed!"));
                }
            });
        }

        function startPolling() {
            loadData();
            if(!pollingStarted) {
                pollingStarted = true;
                setInterval(loadData, 3000);
                callPollInterval = setInterval(pollDmCallState, 2000);
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

        // Dropdown'ların (istekler / grup oluştur) dikey konumunu, üstündeki
        // satırın gerçek yüksekliğine göre hesaplar. Sabit "top: 120px" değeri
        // içerik (rozet, uzun kullanıcı adı vb.) satırı büyüttüğünde dropdown'ın
        // yanlış yerde/çakışık görünmesine sebep oluyordu.
        function positionDropdowns() {
            const row = document.getElementById('action-row');
            if(!row) return;
            const top = row.offsetTop + row.offsetHeight + 8;
            document.getElementById('requests-dropdown').style.top = top + 'px';
            document.getElementById('group-create-dropdown').style.top = top + 'px';
        }
        window.addEventListener('resize', positionDropdowns);

        function toggleRequests() {
            document.getElementById('group-create-dropdown').classList.add('hidden');
            positionDropdowns();
            document.getElementById('requests-dropdown').classList.toggle('hidden');
        }

        function toggleGroupCreate() {
            document.getElementById('requests-dropdown').classList.add('hidden');
            positionDropdowns();
            const dd = document.getElementById('group-create-dropdown');
            const opening = dd.classList.contains('hidden');
            dd.classList.toggle('hidden');
            if(opening) renderGroupMemberChoices();
        }

        function renderGroupMemberChoices() {
            const list = document.getElementById('group-member-list');
            if(currentFriendsList.length === 0) {
                list.innerHTML = `<div style="font-size:11px; color:#737373;">${isTr ? 'Gruba eklemek için önce arkadaş edinmelisin.' : 'Add friends first to add them to a group.'}</div>`;
                return;
            }
            list.innerHTML = currentFriendsList.map(u => `
                <label class="group-member-row">
                    <input type="checkbox" class="group-member-checkbox" value="${u}">
                    ${u}
                </label>
            `).join('');
        }

        async function createGroup() {
            const name = document.getElementById('group-name-input').value.trim();
            const checked = Array.from(document.querySelectorAll('.group-member-checkbox:checked')).map(cb => cb.value);
            if(!name) { alert(isTr ? "Grup adı gir!" : "Enter a group name!"); return; }
            if(checked.length === 0) { alert(isTr ? "En az bir arkadaş seç!" : "Select at least one friend!"); return; }

            const res = await fetch('/api/group-create', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username: currentUser, name, members: checked})
            });
            const resData = await res.json();
            if(res.ok && resData.success) {
                document.getElementById('group-name-input').value = '';
                document.getElementById('group-create-dropdown').classList.add('hidden');
                loadData();
            } else {
                alert(resData.error || (isTr ? "Grup oluşturulamadı!" : "Failed to create group!"));
            }
        }
        
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

        function closeChat() {
            currentChat = null;
            if(chatPollInterval) { clearInterval(chatPollInterval); chatPollInterval = null; }
            document.getElementById('chat-header').classList.add('hidden');
            document.getElementById('chat-header').innerHTML = '';
            document.getElementById('msg-area').classList.add('hidden');
            const box = document.getElementById('chat-box');
            box.classList.add('empty');
            box.innerHTML = isTr ? 'Bir sohbet seçin' : 'Select a chat';
        }

        function openChat(username) {
            currentChat = username;
            const avatar = friendsData[username] || '';
            const header = document.getElementById('chat-header');
            header.classList.remove('hidden');
            const avatarHtml = avatar
                ? `<img class="friend-avatar" src="${avatar}">`
                : `<div class="friend-avatar-placeholder">${username[0].toUpperCase()}</div>`;
            header.innerHTML = `${avatarHtml}<span>${username}</span>
                <div id="chat-header-actions">
                    <button class="header-icon-btn" onclick="startDmCall('${username}')" title="${isTr ? 'Sesli ara' : 'Voice call'}">📞</button>
                </div>`;
            document.getElementById('msg-area').classList.remove('hidden');

            loadMessages();
            if(chatPollInterval) clearInterval(chatPollInterval);
            chatPollInterval = setInterval(loadMessages, 2000);
        }

        function openGroupChat(groupId) {
            currentChat = 'group:' + groupId;
            const g = groupsData[groupId] || {name: groupId};
            const header = document.getElementById('chat-header');
            header.classList.remove('hidden');
            header.innerHTML = `<div class="friend-avatar-placeholder">👥</div><span>${escapeHtml(g.name)}</span>
                <div id="chat-header-actions">
                    <button class="header-icon-btn" onclick="joinGroupCall('${groupId}')" title="${isTr ? 'Sesli sohbete katıl' : 'Join voice chat'}">📞</button>
                    <button class="header-icon-btn leave-btn" onclick="leaveGroup('${groupId}')" title="${isTr ? 'Gruptan ayrıl' : 'Leave group'}">🚪</button>
                </div>`;
            document.getElementById('msg-area').classList.remove('hidden');

            loadMessages();
            if(chatPollInterval) clearInterval(chatPollInterval);
            chatPollInterval = setInterval(loadMessages, 2000);
        }

        async function leaveGroup(groupId) {
            if(!confirm(isTr ? "Bu gruptan ayrılmak istediğine emin misin?" : "Are you sure you want to leave this group?")) return;
            await fetch('/api/group-leave', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username: currentUser, group_id: groupId})
            });
            closeChat();
            loadData();
        }

        async function loadMessages() {
            if(!currentChat || !currentUser) return;
            const isGroup = currentChat.startsWith('group:');
            const groupId = isGroup ? currentChat.slice(6) : null;

            if(!isGroup) {
                try {
                    const existsRes = await fetch(`/api/exists?username=${encodeURIComponent(currentChat)}`);
                    const existsData = await existsRes.json();
                    if(!existsData.exists) {
                        closeChat();
                        return;
                    }
                } catch(e) {}
            }

            try {
                const url = isGroup
                    ? `/api/group-message?group_id=${encodeURIComponent(groupId)}&username=${encodeURIComponent(currentUser)}`
                    : `/api/message?username=${encodeURIComponent(currentUser)}&with=${encodeURIComponent(currentChat)}`;
                const res = await fetch(url);
                if(isGroup && (res.status === 403 || res.status === 404)) {
                    closeChat();
                    return;
                }
                const data = await res.json();
                const box = document.getElementById('chat-box');
                if(data.messages && data.messages.length > 0) {
                    box.classList.remove('empty');
                    box.innerHTML = data.messages.map(m => `
                        <div class="msg-row ${m.from === currentUser ? 'sent' : 'received'}">
                            <div class="msg-bubble">${(isGroup && m.from !== currentUser) ? `<div style="font-size:10px; opacity:0.7; margin-bottom:2px;">${escapeHtml(m.from)}</div>` : ''}${escapeHtml(m.text)}</div>
                        </div>
                    `).join('');
                    box.scrollTop = box.scrollHeight;
                } else {
                    box.classList.add('empty');
                    box.innerHTML = isGroup
                        ? `<div style="color:#888; font-size:13px;">${isTr ? 'Grup sohbeti başlıyor...' : 'Group chat starting...'}</div>`
                        : `<div style="color:#888; font-size:13px;">${currentChat} ile sohbet başlıyor...</div>`;
                }
            } catch(e) {}
        }

        async function uploadAvatar(input) {
            const file = input.files[0];
            if(!file || !currentUser) return;
            try {
                const avatarData = await resizeImage(file);
                const res = await fetch('/api/avatar', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({username: currentUser, avatar: avatarData})
                });
                const resData = await res.json();
                if(res.ok && resData.success) {
                    updateSelfAvatar(avatarData);
                    loadData();
                    alert(isTr ? "Profil güncellendi!" : "Profile updated!");
                } else {
                    alert(isTr ? "Profil güncellenemedi!" : "Failed to update profile!");
                }
            } catch(e) {
                alert(isTr ? "Resim yüklenirken hata oluştu!" : "Error uploading image!");
            }
            input.value = '';
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
                const badge = document.getElementById('req-badge');
                if (data.pending && data.pending.length > 0) {
                    badge.classList.remove('hidden');
                    badge.innerText = data.pending.length;
                    reqList.innerHTML = data.pending.map(p => `
                        <div class="req-item">
                            <span style="font-weight:bold;">${p.username}</span>
                            <div class="req-actions">
                                <button class="req-btn req-btn-accept" onclick="respondRequest('${p.username}', 'accept')" title="${isTr ? 'Kabul et' : 'Accept'}">✓</button>
                                <button class="req-btn req-btn-reject" onclick="respondRequest('${p.username}', 'reject')" title="${isTr ? 'Reddet' : 'Reject'}">✕</button>
                            </div>
                        </div>
                    `).join('');
                } else {
                    badge.classList.add('hidden');
                    reqList.innerHTML = `<div style="font-size:11px; color:#737373; text-align:center; padding: 6px;">${isTr ? 'İstek yok.' : 'No requests.'}</div>`;
                }

                const friendBox = document.getElementById('friend-box');
                currentFriendsList = (data.friends || []).map(f => f.username);
                if (data.friends && data.friends.length > 0) {
                    friendBox.innerHTML = data.friends.map(f => {
                        friendsData[f.username] = f.avatar || '';
                        const avatarHtml = f.avatar
                            ? `<img class="friend-avatar" src="${f.avatar}">`
                            : `<div class="friend-avatar-placeholder">${f.username[0].toUpperCase()}</div>`;
                        return `
                        <div class="friend-item" onclick="openChat('${f.username}')">
                            ${avatarHtml}
                            <span style="font-size:13px; font-weight:bold;">${f.username}</span>
                        </div>`;
                    }).join('');
                } else {
                    friendBox.innerHTML = `<div style="font-size:11px; color:#737373; text-align:center; padding: 10px;">${isTr ? 'Henüz arkadaşın yok.' : 'No friends yet.'}</div>`;
                }

                // Groups
                const gRes = await fetch(`/api/groups?username=${encodeURIComponent(currentUser)}`);
                const gData = await gRes.json();
                const groupBox = document.getElementById('group-box');
                const groupTitle = document.getElementById('group-section-title');
                if (gData.groups && gData.groups.length > 0) {
                    groupTitle.classList.remove('hidden');
                    groupBox.innerHTML = gData.groups.map(g => {
                        groupsData[g.id] = g;
                        return `
                        <div class="friend-item" onclick="openGroupChat('${g.id}')">
                            <div class="friend-avatar-placeholder">👥</div>
                            <span style="font-size:13px; font-weight:bold;">${escapeHtml(g.name)}</span>
                        </div>`;
                    }).join('');
                } else {
                    groupTitle.classList.add('hidden');
                    groupBox.innerHTML = '';
                }

                // If the chat currently open belongs to someone who is no longer
                // a friend (their account was deleted, or they were unfriended),
                // close the chat panel instead of leaving it open with stale data.
                // Group chats are checked separately against the live groups list.
                if(currentChat && currentChat.startsWith('group:')) {
                    const gid = currentChat.slice(6);
                    const stillMember = (gData.groups || []).some(g => g.id === gid);
                    if(!stillMember) closeChat();
                } else if(currentChat) {
                    const stillFriends = currentFriendsList.includes(currentChat);
                    if(!stillFriends) closeChat();
                }

                updateSelfAvatar(data.avatar || '');
            } catch(e) {}
        }

        async function sendMessage() {
            const input = document.getElementById('msg-input');
            const msg = input.value.trim();
            if(!msg || !currentChat || !currentUser) return;
            input.value = '';
            const isGroup = currentChat.startsWith('group:');
            try {
                const res = isGroup
                    ? await fetch('/api/group-message', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({username: currentUser, group_id: currentChat.slice(6), text: msg})
                    })
                    : await fetch('/api/message', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({username: currentUser, to: currentChat, text: msg})
                    });
                const resData = await res.json();
                if(!res.ok && (resData.receiver_missing || resData.not_member)) {
                    closeChat();
                    return;
                }
            } catch(e) {}
            loadMessages();
        }

        // ==================== ARAMA (PeerJS) ====================

        function initPeer() {
            if(peer) return;
            peer = new Peer();
            peer.on('open', (id) => { registerPeerId(id); });
            peer.on('call', (call) => {
                if(!localStream) { call.close(); return; }
                call.answer(localStream);
                const uname = peerIdToUser[call.peer] || call.peer;
                attachMediaConnection(call, uname);
            });
            peer.on('error', (err) => console.error('Peer hatası:', err));
            peer.on('disconnected', () => { try { peer.reconnect(); } catch(e) {} });
        }

        async function registerPeerId(id) {
            if(!currentUser) return;
            try {
                await fetch('/api/peer/register', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({username: currentUser, peer_id: id})
                });
            } catch(e) {}
        }

        function updatePeerIdMap(participants) {
            for(const [uname, pid] of Object.entries(participants || {})) peerIdToUser[pid] = uname;
        }

        function attachMediaConnection(call, uname) {
            call.on('stream', (remoteStream) => {
                let audioEl = document.getElementById('audio-' + uname);
                if(!audioEl) {
                    audioEl = document.createElement('audio');
                    audioEl.id = 'audio-' + uname;
                    audioEl.autoplay = true;
                    document.getElementById('remote-audio-container').appendChild(audioEl);
                }
                audioEl.srcObject = remoteStream;
            });
            call.on('close', () => cleanupParticipantAudio(uname));
        }

        function cleanupParticipantAudio(uname) {
            const audioEl = document.getElementById('audio-' + uname);
            if(audioEl) audioEl.remove();
            delete peerConnections[uname];
        }

        // participants: {username: peer_id} - dial anyone new we're not connected to yet.
        // Only the alphabetically-lower username initiates, so each pair connects once.
        function syncMeshConnections(participants) {
            updatePeerIdMap(participants);
            for(const [uname, pid] of Object.entries(participants || {})) {
                if(uname === currentUser || peerConnections[uname] || !localStream) continue;
                if(currentUser < uname) {
                    const call = peer.call(pid, localStream);
                    peerConnections[uname] = call;
                    attachMediaConnection(call, uname);
                }
            }
        }

        function removeStaleConnections(participants) {
            const stillHere = new Set(Object.keys(participants || {}));
            for(const uname of Object.keys(peerConnections)) {
                if(!stillHere.has(uname)) {
                    try { peerConnections[uname].close(); } catch(e) {}
                    cleanupParticipantAudio(uname);
                }
            }
        }

        function renderCallParticipants(participants, title) {
            document.getElementById('call-title-text').innerText = title;
            const box = document.getElementById('call-participants');
            const names = Object.keys(participants || {});
            box.innerHTML = names.map(uname => `
                <div class="call-avatar-wrap">
                    <div class="call-avatar ${uname === currentUser && isMuted ? 'self-muted' : ''}" id="call-avatar-${uname}">${uname[0].toUpperCase()}</div>
                    <div class="call-avatar-name">${escapeHtml(uname === currentUser ? (isTr ? 'Sen' : 'You') : uname)}</div>
                </div>
            `).join('');
        }

        function showCallOverlay(title, participants) {
            document.getElementById('call-overlay').classList.remove('hidden');
            document.getElementById('remote-audio-container').classList.remove('hidden');
            renderCallParticipants(participants || {[currentUser]: peer && peer.id}, title);
        }

        function hideCallOverlay() {
            document.getElementById('call-overlay').classList.add('hidden');
        }

        async function getMic() {
            try {
                localStream = await navigator.mediaDevices.getUserMedia({audio: true});
                return true;
            } catch(e) {
                alert(isTr ? "Mikrofon izni gerekli!" : "Microphone permission required!");
                return false;
            }
        }

        // ---- Özel (DM) arama ----
        async function startDmCall(target) {
            if(inCall) { alert(isTr ? "Zaten bir aramadasın!" : "You're already in a call!"); return; }
            if(!peer || !peer.id) { alert(isTr ? "Bağlantı hazırlanıyor, birazdan tekrar dene." : "Still connecting, try again shortly."); return; }
            if(!(await getMic())) return;
            const res = await fetch('/api/call/dm/start', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username: currentUser, to: target})
            });
            const data = await res.json();
            if(!res.ok || !data.success) {
                alert(data.error || (isTr ? "Arama başlatılamadı." : "Could not start call."));
                localStream.getTracks().forEach(t => t.stop()); localStream = null;
                return;
            }
            currentCallId = data.call_id;
            currentCallType = 'dm';
            inCall = true;
            showCallOverlay(isTr ? `${target} aranıyor...` : `Calling ${target}...`, {[currentUser]: peer.id});
        }

        function showIncomingCall(callId, fromUser) {
            incomingCall = {call_id: callId, from: fromUser};
            document.getElementById('ic-caller-name').innerText = fromUser;
            document.getElementById('ic-sub-text').innerText = isTr ? 'Sesli arama...' : 'Voice call...';
            document.getElementById('incoming-call-modal').classList.remove('hidden');
        }

        function hideIncomingCall() {
            incomingCall = null;
            document.getElementById('incoming-call-modal').classList.add('hidden');
        }

        async function acceptDmCall() {
            if(!incomingCall) return;
            const {call_id, from} = incomingCall;
            hideIncomingCall();
            if(!(await getMic())) return;
            const res = await fetch('/api/call/dm/respond', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username: currentUser, call_id, action: 'accept', peer_id: peer.id})
            });
            const data = await res.json();
            if(!res.ok || !data.success) {
                localStream.getTracks().forEach(t => t.stop()); localStream = null;
                return;
            }
            currentCallId = call_id;
            currentCallType = 'dm';
            inCall = true;
            syncMeshConnections(data.participants);
            showCallOverlay(from, data.participants);
        }

        async function declineDmCall() {
            if(!incomingCall) return;
            const {call_id} = incomingCall;
            hideIncomingCall();
            try {
                await fetch('/api/call/dm/respond', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({username: currentUser, call_id, action: 'decline'})
                });
            } catch(e) {}
        }

        async function pollDmCallState() {
            if(!currentUser) return;
            try {
                const res = await fetch(`/api/call/poll?username=${encodeURIComponent(currentUser)}`);
                const data = await res.json();
                if(data.state === 'incoming' && !inCall && !incomingCall) {
                    showIncomingCall(data.call_id, data.from);
                } else if(data.state === 'active' && currentCallType === 'dm' && data.call_id === currentCallId) {
                    updatePeerIdMap(data.participants);
                    syncMeshConnections(data.participants);
                    const otherName = Object.keys(data.participants).find(u => u !== currentUser) || '';
                    renderCallParticipants(data.participants, otherName);
                } else if(data.state === 'idle') {
                    if(incomingCall) hideIncomingCall();
                    if(currentCallType === 'dm' && currentCallId) {
                        // Karşı taraf reddetti ya da görüşme sona erdi.
                        leaveCall(true);
                    }
                }
            } catch(e) {}
        }

        // ---- Grup sesli sohbeti ----
        async function joinGroupCall(groupId) {
            if(inCall) { alert(isTr ? "Zaten bir aramadasın!" : "You're already in a call!"); return; }
            if(!peer || !peer.id) { alert(isTr ? "Bağlantı hazırlanıyor, birazdan tekrar dene." : "Still connecting, try again shortly."); return; }
            if(!(await getMic())) return;
            const res = await fetch('/api/call/group/join', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username: currentUser, group_id: groupId, peer_id: peer.id})
            });
            const data = await res.json();
            if(!res.ok || !data.success) {
                alert(data.error || (isTr ? "Sesli sohbete katılamadın." : "Could not join voice chat."));
                localStream.getTracks().forEach(t => t.stop()); localStream = null;
                return;
            }
            currentCallId = groupId;
            currentCallType = 'group';
            inCall = true;
            syncMeshConnections(data.participants);
            const gName = (groupsData[groupId] && groupsData[groupId].name) || groupId;
            showCallOverlay(gName, data.participants);

            if(groupCallPollInterval) clearInterval(groupCallPollInterval);
            groupCallPollInterval = setInterval(async () => {
                try {
                    const r = await fetch(`/api/call/group/state?group_id=${encodeURIComponent(groupId)}`);
                    const d = await r.json();
                    syncMeshConnections(d.participants || {});
                    removeStaleConnections(d.participants || {});
                    renderCallParticipants(d.participants || {}, gName);
                } catch(e) {}
            }, 2000);
        }

        function toggleMute() {
            if(!localStream) return;
            isMuted = !isMuted;
            localStream.getAudioTracks().forEach(t => t.enabled = !isMuted);
            const btn = document.getElementById('call-mute-btn');
            btn.innerText = isMuted ? '🔇' : '🎙️';
            btn.classList.toggle('muted', isMuted);
            const avatar = document.getElementById('call-avatar-' + currentUser);
            if(avatar) avatar.classList.toggle('self-muted', isMuted);
        }

        async function leaveCall(skipServerNotify) {
            const wasType = currentCallType, wasId = currentCallId;
            Object.values(peerConnections).forEach(c => { try { c.close(); } catch(e) {} });
            peerConnections = {};
            document.getElementById('remote-audio-container').innerHTML = '';
            document.getElementById('remote-audio-container').classList.add('hidden');
            if(localStream) { localStream.getTracks().forEach(t => t.stop()); localStream = null; }
            if(groupCallPollInterval) { clearInterval(groupCallPollInterval); groupCallPollInterval = null; }
            hideCallOverlay();
            isMuted = false;
            inCall = false; currentCallId = null; currentCallType = null;

            if(!skipServerNotify && wasType && wasId) {
                try {
                    if(wasType === 'dm') {
                        await fetch('/api/call/dm/leave', {
                            method: 'POST', headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({username: currentUser, call_id: wasId})
                        });
                    } else if(wasType === 'group') {
                        await fetch('/api/call/group/leave', {
                            method: 'POST', headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({username: currentUser, group_id: wasId})
                        });
                    }
                } catch(e) {}
            }
        }

        if(currentUser) {
            document.getElementById('login-screen').classList.add('hidden');
            document.getElementById('app-screen').classList.remove('hidden');
            setSelfUsername();
            initPeer();
            startPolling();
        }
    </script>
</body>
</html>"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/noprof.png')
def favicon_png():
    return send_from_directory(BASE_DIR, 'noprof.png', mimetype='image/png')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(BASE_DIR, 'noprof.png', mimetype='image/png')

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json or {}
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"success": False, "error": "Kullanıcı adı ve şifre gerekli!"}), 400

    if username not in users_db:
        users_db[username] = {
            "avatar": "", "pending": [], "friends": [],
            "password_hash": generate_password_hash(password)
        }
    else:
        existing = users_db[username]
        stored_hash = existing.get("password_hash")
        if not stored_hash:
            # Account only existed as a stub (e.g. someone sent them a friend
            # request before they ever signed up) - this login claims it.
            existing["password_hash"] = generate_password_hash(password)
        elif not check_password_hash(stored_hash, password):
            return jsonify({"success": False, "error": "Şifre yanlış!"}), 401

    return jsonify({"success": True, "username": username})

@app.route('/api/user-data', methods=['GET'])
def user_data():
    username = request.args.get('username')
    if not username or username not in users_db:
        return jsonify({"pending": [], "friends": [], "avatar": ""})
    u = users_db[username]
    friends = [
        {"username": f, "avatar": users_db.get(f, {}).get("avatar", "")}
        for f in u.get("friends", [])
    ]
    return jsonify({"pending": u.get("pending", []), "friends": friends, "avatar": u.get("avatar", "")})

@app.route('/api/exists', methods=['GET'])
def user_exists():
    username = request.args.get('username')
    return jsonify({"exists": bool(username) and username in users_db})

@app.route('/api/message', methods=['GET'])
def get_messages():
    username = request.args.get('username')
    other = request.args.get('with')
    if not username or not other:
        return jsonify({"messages": []})
    key = conv_key(username, other)
    return jsonify({"messages": messages_db.get(key, [])})

@app.route('/api/message', methods=['POST'])
def send_message():
    data = request.json or {}
    sender = data.get('username')
    receiver = data.get('to')
    text = (data.get('text') or '').strip()

    if not sender or not receiver or not text:
        return jsonify({"success": False, "error": "Eksik parametre!"}), 400

    if receiver not in users_db:
        return jsonify({"success": False, "error": "Kullanıcı artık mevcut değil.", "receiver_missing": True}), 404

    key = conv_key(sender, receiver)
    if key not in messages_db:
        messages_db[key] = []
    messages_db[key].append({"from": sender, "text": text})
    return jsonify({"success": True})

@app.route('/api/group-create', methods=['POST'])
def group_create():
    data = request.json or {}
    username = data.get('username')
    name = (data.get('name') or '').strip()
    members = data.get('members') or []

    if not username or username not in users_db:
        return jsonify({"success": False, "error": "Geçersiz kullanıcı!"}), 400
    if not name:
        return jsonify({"success": False, "error": "Grup adı gerekli!"}), 400

    # Only people who are actually friends of the creator can be added -
    # never arbitrary usernames passed in from the client.
    friends = set(users_db[username].get("friends", []))
    valid_members = [m for m in members if m in friends]

    if not valid_members:
        return jsonify({"success": False, "error": "Geçerli arkadaş seçilmedi!"}), 400

    group_id = uuid.uuid4().hex[:10]
    all_members = list(dict.fromkeys([username] + valid_members))  # de-dupe, preserve order
    groups_db[group_id] = {"name": name, "owner": username, "members": all_members}
    group_messages_db[group_id] = []

    return jsonify({"success": True, "id": group_id})

@app.route('/api/groups', methods=['GET'])
def list_groups():
    username = request.args.get('username')
    if not username:
        return jsonify({"groups": []})
    result = [
        {"id": gid, "name": g["name"], "members": g["members"]}
        for gid, g in groups_db.items()
        if username in g["members"]
    ]
    return jsonify({"groups": result})

@app.route('/api/group-message', methods=['GET'])
def get_group_messages():
    group_id = request.args.get('group_id')
    username = request.args.get('username')
    if not group_id or group_id not in groups_db:
        return jsonify({"messages": [], "error": "Grup bulunamadı."}), 404
    if not username or username not in groups_db[group_id]["members"]:
        return jsonify({"messages": [], "error": "Bu grubun üyesi değilsin."}), 403
    return jsonify({"messages": group_messages_db.get(group_id, [])})

@app.route('/api/group-message', methods=['POST'])
def send_group_message():
    data = request.json or {}
    username = data.get('username')
    group_id = data.get('group_id')
    text = (data.get('text') or '').strip()

    if not username or not group_id or not text:
        return jsonify({"success": False, "error": "Eksik parametre!"}), 400
    if group_id not in groups_db:
        return jsonify({"success": False, "error": "Grup bulunamadı.", "not_member": True}), 404
    if username not in groups_db[group_id]["members"]:
        return jsonify({"success": False, "error": "Bu grubun üyesi değilsin.", "not_member": True}), 403

    group_messages_db.setdefault(group_id, []).append({"from": username, "text": text})
    return jsonify({"success": True})

@app.route('/api/friend-request', methods=['POST'])
def friend_request():
    data = request.json or {}
    sender = data.get('username')
    receiver = data.get('friend_username')
    
    if not sender or not receiver:
        return jsonify({"success": False, "error": "Eksik parametre!"}), 400
        
    if sender not in users_db:
        users_db[sender] = {"avatar": "", "pending": [], "friends": []}
    if receiver not in users_db:
        users_db[receiver] = {"avatar": "", "pending": [], "friends": []}
        
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
    action = data.get('action')
    
    if username in users_db:
        users_db[username]["pending"] = [p for p in users_db[username]["pending"] if p["username"] != friend_username]
        if action == 'accept':
            if friend_username not in users_db[username]["friends"]:
                users_db[username]["friends"].append(friend_username)
            if friend_username in users_db:
                if username not in users_db[friend_username]["friends"]:
                    users_db[friend_username]["friends"].append(username)
                    
    return jsonify({"success": True})

@app.route('/api/avatar', methods=['POST'])
def avatar():
    data = request.json or {}
    username = data.get('username')
    avatar_data = data.get('avatar')
    
    if username in users_db:
        users_db[username]["avatar"] = avatar_data
        return jsonify({"success": True})
    return jsonify({"success": False}), 404

@app.route('/api/reset', methods=['POST'])
def reset():
    data = request.json or {}
    username = data.get('username')

    if not username:
        return jsonify({"success": False, "error": "Eksik parametre!"}), 400

    # 1) Remove this user's account entirely
    if username in users_db:
        del users_db[username]

    # 2) Strip this user out of every other account's friends/pending lists
    #    so no trace of the relationship remains on either side
    for other_username, other_data in users_db.items():
        other_data["friends"] = [f for f in other_data.get("friends", []) if f != username]
        other_data["pending"] = [p for p in other_data.get("pending", []) if p.get("username") != username]

    # 3) Delete every conversation this user was part of, for both sides
    keys_to_delete = [key for key in messages_db.keys() if username in key.split("|")]
    for key in keys_to_delete:
        del messages_db[key]

    # 4) Any group this user belonged to is deleted entirely, for every
    #    member - not just for this user. Deleting your account wipes the
    #    whole group, unlike leaving it voluntarily (/api/group-leave),
    #    which only removes you and keeps the group for everyone else.
    own_group_ids = [gid for gid, g in groups_db.items() if username in g["members"]]
    for gid in own_group_ids:
        del groups_db[gid]
        group_messages_db.pop(gid, None)
        group_calls.pop(gid, None)

    # 5) Clear any call/peer state so a deleted account can't linger in a
    #    ringing call or a voice room.
    peer_ids.pop(username, None)
    for call_id in [cid for cid, c in dm_calls.items() if username in (c["from"], c["to"])]:
        del dm_calls[call_id]
    for gid, room in list(group_calls.items()):
        if username in room["participants"]:
            del room["participants"][username]
            if not room["participants"]:
                del group_calls[gid]

    return jsonify({"success": True})

@app.route('/api/group-leave', methods=['POST'])
def group_leave():
    data = request.json or {}
    username = data.get('username')
    group_id = data.get('group_id')

    if not username or not group_id:
        return jsonify({"success": False, "error": "Eksik parametre!"}), 400
    if group_id not in groups_db:
        return jsonify({"success": False, "error": "Grup bulunamadı."}), 404

    g = groups_db[group_id]
    if username not in g["members"]:
        return jsonify({"success": False, "error": "Bu grubun üyesi değilsin."}), 403

    g["members"] = [m for m in g["members"] if m != username]
    if not g["members"]:
        del groups_db[group_id]
        group_messages_db.pop(group_id, None)
        group_calls.pop(group_id, None)
    else:
        # Kişi sesli sohbetteyse aramadan da çıkar.
        gc = group_calls.get(group_id)
        if gc and username in gc["participants"]:
            del gc["participants"][username]
            if not gc["participants"]:
                del group_calls[group_id]

    return jsonify({"success": True})

# ==================== ARAMA (PeerJS sinyalleşme) ====================

@app.route('/api/peer/register', methods=['POST'])
def peer_register():
    data = request.json or {}
    username = data.get('username')
    peer_id = data.get('peer_id')
    if not username or not peer_id:
        return jsonify({"success": False, "error": "Eksik parametre!"}), 400
    peer_ids[username] = peer_id
    return jsonify({"success": True})

@app.route('/api/call/dm/start', methods=['POST'])
def call_dm_start():
    data = request.json or {}
    username = data.get('username')
    to = data.get('to')

    if not username or not to:
        return jsonify({"success": False, "error": "Eksik parametre!"}), 400
    if to not in users_db:
        return jsonify({"success": False, "error": "Kullanıcı bulunamadı."}), 404
    if username not in peer_ids:
        return jsonify({"success": False, "error": "Bağlantı hazır değil, tekrar dene."}), 400
    if is_user_busy(username):
        return jsonify({"success": False, "error": "Zaten bir aramadasın."}), 409
    if is_user_busy(to):
        return jsonify({"success": False, "error": "Kullanıcı meşgul.", "busy": True}), 409

    call_id = uuid.uuid4().hex[:10]
    dm_calls[call_id] = {
        "from": username, "to": to,
        "participants": {username: peer_ids[username]},
        "status": "ringing",
    }
    return jsonify({"success": True, "call_id": call_id})

@app.route('/api/call/dm/respond', methods=['POST'])
def call_dm_respond():
    data = request.json or {}
    username = data.get('username')
    call_id = data.get('call_id')
    action = data.get('action')
    peer_id = data.get('peer_id')

    call = dm_calls.get(call_id)
    if not call or username != call["to"]:
        return jsonify({"success": False, "error": "Arama bulunamadı."}), 404

    if action == 'decline':
        del dm_calls[call_id]
        return jsonify({"success": True})

    if action == 'accept':
        if not peer_id:
            return jsonify({"success": False, "error": "Eksik parametre!"}), 400
        call["participants"][username] = peer_id
        call["status"] = "active"
        return jsonify({"success": True, "participants": call["participants"]})

    return jsonify({"success": False, "error": "Geçersiz aksiyon."}), 400

@app.route('/api/call/dm/leave', methods=['POST'])
def call_dm_leave():
    data = request.json or {}
    username = data.get('username')
    call_id = data.get('call_id')

    call = dm_calls.get(call_id)
    if call:
        call["participants"].pop(username, None)
        if not call["participants"] or call["status"] == "ringing":
            del dm_calls[call_id]
    return jsonify({"success": True})

@app.route('/api/call/poll', methods=['GET'])
def call_poll():
    username = request.args.get('username')
    if not username:
        return jsonify({"state": "idle"})

    for call_id, call in dm_calls.items():
        if username not in (call["from"], call["to"]):
            continue
        if username in call["participants"]:
            return jsonify({"state": "active", "call_id": call_id, "call_type": "dm", "participants": call["participants"]})
        if username == call["to"]:
            return jsonify({"state": "incoming", "call_id": call_id, "from": call["from"]})
        # username is the caller, still ringing
        return jsonify({"state": "calling", "call_id": call_id, "to": call["to"]})

    return jsonify({"state": "idle"})

@app.route('/api/call/group/join', methods=['POST'])
def call_group_join():
    data = request.json or {}
    username = data.get('username')
    group_id = data.get('group_id')
    peer_id = data.get('peer_id')

    if not username or not group_id or not peer_id:
        return jsonify({"success": False, "error": "Eksik parametre!"}), 400
    if group_id not in groups_db or username not in groups_db[group_id]["members"]:
        return jsonify({"success": False, "error": "Bu grubun üyesi değilsin."}), 403

    room = group_calls.setdefault(group_id, {"participants": {}})
    room["participants"][username] = peer_id
    return jsonify({"success": True, "participants": room["participants"]})

@app.route('/api/call/group/leave', methods=['POST'])
def call_group_leave():
    data = request.json or {}
    username = data.get('username')
    group_id = data.get('group_id')

    room = group_calls.get(group_id)
    if room:
        room["participants"].pop(username, None)
        if not room["participants"]:
            del group_calls[group_id]
    return jsonify({"success": True})

@app.route('/api/call/group/state', methods=['GET'])
def call_group_state():
    group_id = request.args.get('group_id')
    room = group_calls.get(group_id)
    return jsonify({"participants": room["participants"] if room else {}})

if __name__ == '__main__':
    app.run(debug=True)
