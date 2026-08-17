from flask import Flask, render_template, request, session, redirect, url_for
from flask_socketio import SocketIO, emit, join_room
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24).hex()
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

users = {}

@app.route('/', methods=['GET', 'POST'])
def index():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if not username or not password:
            error = "Kullanici adi ve sifre bos olamaz."
        else:
            if username in users:
                if users[username] != password:
                    error = "Hatali sifre!"
            else:
                users[username] = password
            
            if not error:
                session['username'] = username
                return redirect(url_for('chat'))
                
    return render_template('index.html', error=error)

@app.route('/chat')
def chat():
    if 'username' not in session:
        return redirect(url_for('index'))
    return render_template('chat.html', username=session['username'])

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('index'))

@socketio.on('join')
def on_join(data):
    room = data.get('room', 'genel')
    username = session.get('username')
    if username:
        join_room(room)
        emit('status', {'msg': f'{username} odaya katildi.'}, room=room)

@socketio.on('send_message')
def handle_message(data):
    room = data.get('room', 'genel')
    msg_id = data.get('msg_id')
    message = data.get('message')
    username = session.get('username')
    
    if username and message:
        emit('receive_message', {
            'msg_id': msg_id,
            'username': username,
            'message': message
        }, room=room)

@socketio.on('delete_message')
def handle_delete(data):
    room = data.get('room', 'genel')
    msg_id = data.get('msg_id')
    emit('remove_message', {'msg_id': msg_id}, room=room)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port)