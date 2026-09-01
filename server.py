# ========================================
# TELEGRAM BOT KEY API SERVER
# For Railway Deployment
# ========================================

from flask import Flask, request, jsonify
import json
import hashlib
import time
import os
from datetime import datetime, timedelta
import sqlite3

app = Flask(__name__)

# ========================================
# CONFIGURATION - EDIT THESE
# ========================================

SECRET_KEY = os.environ.get('SECRET_KEY', 'ZAKPUBG_SECRET_KEY_2026')
DB_FILE = "keys.db"

# ========================================
# DATABASE SETUP
# ========================================

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Keys table
    c.execute('''CREATE TABLE IF NOT EXISTS keys (
        key_id TEXT PRIMARY KEY,
        duration TEXT,
        expiry_date TEXT,
        max_uses INTEGER,
        max_devices INTEGER,
        used_count INTEGER DEFAULT 0,
        created_at TEXT,
        is_active INTEGER DEFAULT 1,
        owner_id TEXT DEFAULT ''
    )''')
    
    # Devices table
    c.execute('''CREATE TABLE IF NOT EXISTS devices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key_id TEXT,
        device_id TEXT,
        activated_at TEXT,
        FOREIGN KEY (key_id) REFERENCES keys(key_id)
    )''')
    
    # Users table (for tracking who requested keys)
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        keys_generated INTEGER DEFAULT 0,
        last_key_at TEXT,
        created_at TEXT
    )''')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized")

# ========================================
# KEY GENERATION
# ========================================

def generate_key_id():
    """Generate a unique key ID"""
    import random
    import string
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))

def create_key(duration, expiry_date=None, max_uses=0, max_devices=0, owner_id=""):
    """Create a new key"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    key_id = generate_key_id()
    
    # Calculate expiry if not provided
    if expiry_date is None and duration not in ["permanent", "single"]:
        try:
            days = int(duration)
            expiry_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
        except:
            expiry_date = "never"
    elif expiry_date is None:
        expiry_date = "never"
    
    # Format the key (matches Lua parser expected format)
    formatted_key = f"{key_id}|{duration}|{expiry_date}|{max_uses}|{max_devices}"
    
    c.execute('''INSERT INTO keys 
        (key_id, duration, expiry_date, max_uses, max_devices, created_at, owner_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (formatted_key, duration, expiry_date, max_uses, max_devices, 
         datetime.now().isoformat(), owner_id))
    
    # Update user stats
    if owner_id:
        c.execute('''INSERT INTO users (user_id, created_at) 
                     VALUES (?, ?) 
                     ON CONFLICT(user_id) DO UPDATE SET 
                     keys_generated = keys_generated + 1,
                     last_key_at = ?''',
                  (owner_id, datetime.now().isoformat(), datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    
    return formatted_key

def get_key_data(key):
    """Get key data from database"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute('SELECT * FROM keys WHERE key_id = ? AND is_active = 1', (key,))
    row = c.fetchone()
    
    conn.close()
    
    if row:
        return {
            'key_id': row[0],
            'duration': row[1],
            'expiry_date': row[2],
            'max_uses': row[3],
            'max_devices': row[4],
            'used_count': row[5],
            'created_at': row[6],
            'is_active': row[7],
            'owner_id': row[8]
        }
    return None

def get_device_count(key_id):
    """Get number of devices using this key"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute('SELECT COUNT(*) FROM devices WHERE key_id = ?', (key_id,))
    count = c.fetchone()[0]
    
    conn.close()
    return count

def register_device(key_id, device_id):
    """Register a device for a key"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Check if device already registered
    c.execute('SELECT * FROM devices WHERE key_id = ? AND device_id = ?', (key_id, device_id))
    if c.fetchone():
        conn.close()
        return True
    
    # Register device
    c.execute('INSERT INTO devices (key_id, device_id, activated_at) VALUES (?, ?, ?)',
        (key_id, device_id, datetime.now().isoformat()))
    
    # Increment used count
    c.execute('UPDATE keys SET used_count = used_count + 1 WHERE key_id = ?', (key_id,))
    
    conn.commit()
    conn.close()
    return True

def calculate_days_remaining(expiry_date):
    if expiry_date == "never":
        return -1
    try:
        expiry = datetime.strptime(expiry_date, '%Y-%m-%d')
        remaining = (expiry - datetime.now()).days
        return max(0, remaining)
    except:
        return -1

# ========================================
# API ENDPOINTS
# ========================================

@app.route('/')
def home():
    return jsonify({
        'status': 'running',
        'service': 'ZAKPUBGSKIN Key API',
        'version': '1.0',
        'endpoints': {
            '/verify': 'POST - Verify a key',
            '/register': 'POST - Register a device',
            '/generate': 'POST - Generate a new key',
            '/revoke': 'POST - Revoke a key',
            '/list': 'GET - List all keys',
            '/stats': 'GET - Get statistics'
        }
    })

@app.route('/verify', methods=['POST'])
def verify_key():
    """Verify a key - Main endpoint used by the mod"""
    try:
        data = request.get_json()
        
        # Get authentication
        device_id = request.headers.get('X-Device-ID', '')
        secret = request.headers.get('X-Secret', '')
        
        if secret != SECRET_KEY:
            return jsonify({'valid': False, 'error': 'Invalid secret'}), 401
        
        key = data.get('key', '')
        device = data.get('device', '')
        
        if not key:
            return jsonify({'valid': False, 'error': 'No key provided'}), 400
        
        # Get key data from database
        key_data = get_key_data(key)
        
        if not key_data:
            return jsonify({'valid': False, 'error': 'Key not found'}), 404
        
        # Check if expired
        if key_data['duration'] not in ['permanent', 'single']:
            try:
                expiry_date = datetime.strptime(key_data['expiry_date'], '%Y-%m-%d')
                if datetime.now() > expiry_date:
                    return jsonify({'valid': False, 'error': 'Key expired'}), 403
            except:
                pass
        
        # Check max uses
        if key_data['max_uses'] > 0 and key_data['used_count'] >= key_data['max_uses']:
            return jsonify({'valid': False, 'error': 'Key usage exhausted'}), 403
        
        # Check max devices
        if key_data['max_devices'] > 0:
            device_count = get_device_count(key)
            if device_count >= key_data['max_devices']:
                return jsonify({'valid': False, 'error': 'Device limit reached'}), 403
        
        # Register device
        if device:
            register_device(key, device)
        
        # Prepare response for Lua
        response = {
            'valid': True,
            'key': key_data['key_id'],
            'duration': key_data['duration'],
            'expiry': key_data['expiry_date'],
            'max_uses': key_data['max_uses'],
            'max_devices': key_data['max_devices'],
            'is_permanent': key_data['duration'] == 'permanent',
            'is_single_use': key_data['duration'] == 'single',
            'used_count': key_data['used_count'],
            'remaining_uses': key_data['max_uses'] - key_data['used_count'] if key_data['max_uses'] > 0 else -1,
            'days_remaining': calculate_days_remaining(key_data['expiry_date'])
        }
        
        print(f"✅ Key verified: {key[:4]}**** by device: {device[:8] if device else 'unknown'}")
        return jsonify(response), 200
        
    except Exception as e:
        print(f"❌ Verify error: {str(e)}")
        return jsonify({'valid': False, 'error': str(e)}), 500

@app.route('/register', methods=['POST'])
def register_device_endpoint():
    """Register a device for a key"""
    try:
        data = request.get_json()
        secret = request.headers.get('X-Secret', '')
        
        if secret != SECRET_KEY:
            return jsonify({'success': False, 'error': 'Invalid secret'}), 401
        
        key = data.get('key', '')
        device = data.get('device', '')
        
        if not key or not device:
            return jsonify({'success': False, 'error': 'Missing data'}), 400
        
        success = register_device(key, device)
        return jsonify({'success': success}), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/generate', methods=['POST'])
def generate_key_endpoint():
    """Generate a new key - For bot use"""
    try:
        data = request.get_json()
        secret = request.headers.get('X-Secret', '')
        
        if secret != SECRET_KEY:
            return jsonify({'success': False, 'error': 'Invalid secret'}), 401
        
        duration = data.get('duration', 'permanent')
        expiry = data.get('expiry', None)
        max_uses = int(data.get('max_uses', 0))
        max_devices = int(data.get('max_devices', 0))
        owner_id = data.get('owner_id', '')
        
        key = create_key(duration, expiry, max_uses, max_devices, owner_id)
        
        print(f"✅ Generated key: {key[:4]}**** for user: {owner_id or 'unknown'}")
        return jsonify({'success': True, 'key': key}), 200
        
    except Exception as e:
        print(f"❌ Generate error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/revoke', methods=['POST'])
def revoke_key_endpoint():
    """Revoke a key - For bot use"""
    try:
        data = request.get_json()
        secret = request.headers.get('X-Secret', '')
        
        if secret != SECRET_KEY:
            return jsonify({'success': False, 'error': 'Invalid secret'}), 401
        
        key = data.get('key', '')
        
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('UPDATE keys SET is_active = 0 WHERE key_id = ?', (key,))
        conn.commit()
        conn.close()
        
        print(f"✅ Key revoked: {key[:4]}****")
        return jsonify({'success': True}), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/list', methods=['GET'])
def list_keys_endpoint():
    """List all keys - For bot use"""
    try:
        secret = request.headers.get('X-Secret', '')
        
        if secret != SECRET_KEY:
            return jsonify({'success': False, 'error': 'Invalid secret'}), 401
        
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT key_id, duration, expiry_date, max_uses, max_devices, used_count, created_at, is_active, owner_id FROM keys ORDER BY created_at DESC')
        rows = c.fetchall()
        conn.close()
        
        keys = []
        for row in rows:
            keys.append({
                'key': row[0],
                'duration': row[1],
                'expiry': row[2],
                'max_uses': row[3],
                'max_devices': row[4],
                'used_count': row[5],
                'created_at': row[6],
                'is_active': row[7] == 1,
                'owner_id': row[8]
            })
        
        return jsonify({'success': True, 'keys': keys}), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/stats', methods=['GET'])
def stats_endpoint():
    """Get statistics - For bot use"""
    try:
        secret = request.headers.get('X-Secret', '')
        
        if secret != SECRET_KEY:
            return jsonify({'success': False, 'error': 'Invalid secret'}), 401
        
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        c.execute('SELECT COUNT(*) FROM keys WHERE is_active = 1')
        active_keys = c.fetchone()[0]
        
        c.execute('SELECT COUNT(*) FROM keys')
        total_keys = c.fetchone()[0]
        
        c.execute('SELECT COUNT(*) FROM devices')
        total_devices = c.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'success': True,
            'stats': {
                'active_keys': active_keys,
                'total_keys': total_keys,
                'total_devices': total_devices
            }
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ========================================
# START THE SERVER
# ========================================

if __name__ == '__main__':
    init_db()
    
    port = int(os.environ.get('PORT', 8080))
    
    print("=" * 60)
    print("🔑 ZAKPUBGSKIN KEY API SERVER")
    print(f"🔐 Secret: {SECRET_KEY[:10]}...")
    print(f"🌐 Port: {port}")
    print("=" * 60)
    print("📌 Endpoints:")
    print("  POST /verify  - Verify a key")
    print("  POST /generate - Generate a key")
    print("  POST /revoke  - Revoke a key")
    print("  GET  /list    - List all keys")
    print("  GET  /stats   - Get statistics")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=port)        max_uses INTEGER,
        max_devices INTEGER,
        used_count INTEGER DEFAULT 0,
        created_at TEXT,
        is_active INTEGER DEFAULT 1
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS devices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key_id TEXT,
        device_id TEXT,
        activated_at TEXT,
        FOREIGN KEY (key_id) REFERENCES keys(key_id)
    )''')
    
    conn.commit()
    conn.close()

# ========================================
# KEY GENERATION FUNCTIONS (For Bot)
# ========================================

def generate_key_id():
    """Generate a unique key ID"""
    import random
    import string
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))

def create_key(duration, expiry_date=None, max_uses=0, max_devices=0):
    """Create a new key"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    key_id = generate_key_id()
    
    # If expiry_date is not provided, calculate it
    if expiry_date is None and duration not in ["permanent", "single"]:
        days = int(duration)
        expiry_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    elif expiry_date is None:
        expiry_date = "never"
    
    # Format the key
    formatted_key = f"{key_id}|{duration}|{expiry_date}|{max_uses}|{max_devices}"
    
    c.execute('''INSERT INTO keys 
        (key_id, duration, expiry_date, max_uses, max_devices, created_at)
        VALUES (?, ?, ?, ?, ?, ?)''',
        (formatted_key, duration, expiry_date, max_uses, max_devices, datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    
    return formatted_key

def get_key_data(key):
    """Get key data from database"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute('SELECT * FROM keys WHERE key_id = ? AND is_active = 1', (key,))
    row = c.fetchone()
    
    conn.close()
    
    if row:
        return {
            'key_id': row[0],
            'duration': row[1],
            'expiry_date': row[2],
            'max_uses': row[3],
            'max_devices': row[4],
            'used_count': row[5],
            'created_at': row[6],
            'is_active': row[7]
        }
    return None

def get_device_count(key_id):
    """Get number of devices using this key"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute('SELECT COUNT(*) FROM devices WHERE key_id = ?', (key_id,))
    count = c.fetchone()[0]
    
    conn.close()
    return count

def register_device(key_id, device_id):
    """Register a device for a key"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Check if device already registered
    c.execute('SELECT * FROM devices WHERE key_id = ? AND device_id = ?', (key_id, device_id))
    if c.fetchone():
        conn.close()
        return True
    
    # Register device
    c.execute('INSERT INTO devices (key_id, device_id, activated_at) VALUES (?, ?, ?)',
        (key_id, device_id, datetime.now().isoformat()))
    
    # Increment used count
    c.execute('UPDATE keys SET used_count = used_count + 1 WHERE key_id = ?', (key_id,))
    
    conn.commit()
    conn.close()
    return True

# ========================================
# API ENDPOINTS
# ========================================

@app.route('/verify', methods=['POST'])
def verify_key():
    """Verify a key"""
    try:
        data = request.get_json()
        
        # Check authentication
        device_id = request.headers.get('X-Device-ID', '')
        secret = request.headers.get('X-Secret', '')
        
        if secret != SECRET_KEY:
            return jsonify({'valid': False, 'error': 'Invalid secret'}), 401
        
        key = data.get('key', '')
        device = data.get('device', '')
        
        if not key:
            return jsonify({'valid': False, 'error': 'No key provided'}), 400
        
        # Get key data from database
        key_data = get_key_data(key)
        
        if not key_data:
            return jsonify({'valid': False, 'error': 'Key not found'}), 404
        
        # Check expiry
        if key_data['duration'] not in ['permanent', 'single']:
            expiry_date = datetime.strptime(key_data['expiry_date'], '%Y-%m-%d')
            if datetime.now() > expiry_date:
                return jsonify({'valid': False, 'error': 'Key expired'}), 403
        
        # Check max uses
        if key_data['max_uses'] > 0 and key_data['used_count'] >= key_data['max_uses']:
            return jsonify({'valid': False, 'error': 'Key usage exhausted'}), 403
        
        # Check max devices
        if key_data['max_devices'] > 0:
            device_count = get_device_count(key)
            if device_count >= key_data['max_devices']:
                return jsonify({'valid': False, 'error': 'Device limit reached'}), 403
        
        # Register device
        if device:
            register_device(key, device)
        
        # Prepare response
        response = {
            'valid': True,
            'key': key,
            'duration': key_data['duration'],
            'expiry': key_data['expiry_date'],
            'max_uses': key_data['max_uses'],
            'max_devices': key_data['max_devices'],
            'is_permanent': key_data['duration'] == 'permanent',
            'is_single_use': key_data['duration'] == 'single',
            'used_count': key_data['used_count'],
            'remaining_uses': key_data['max_uses'] - key_data['used_count'] if key_data['max_uses'] > 0 else -1,
            'days_remaining': calculate_days_remaining(key_data['expiry_date']) if key_data['duration'] not in ['permanent', 'single'] else -1
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        return jsonify({'valid': False, 'error': str(e)}), 500

@app.route('/register', methods=['POST'])
def register_device_endpoint():
    """Register a device"""
    try:
        data = request.get_json()
        secret = request.headers.get('X-Secret', '')
        
        if secret != SECRET_KEY:
            return jsonify({'success': False, 'error': 'Invalid secret'}), 401
        
        key = data.get('key', '')
        device = data.get('device', '')
        
        if not key or not device:
            return jsonify({'success': False, 'error': 'Missing data'}), 400
        
        success = register_device(key, device)
        return jsonify({'success': success}), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/generate', methods=['POST'])
def generate_key_endpoint():
    """Generate a new key (for bot use)"""
    try:
        data = request.get_json()
        secret = request.headers.get('X-Secret', '')
        
        if secret != SECRET_KEY:
            return jsonify({'success': False, 'error': 'Invalid secret'}), 401
        
        duration = data.get('duration', 'permanent')
        expiry = data.get('expiry', None)
        max_uses = int(data.get('max_uses', 0))
        max_devices = int(data.get('max_devices', 0))
        
        key = create_key(duration, expiry, max_uses, max_devices)
        
        return jsonify({'success': True, 'key': key}), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/revoke', methods=['POST'])
def revoke_key_endpoint():
    """Revoke a key (for bot use)"""
    try:
        data = request.get_json()
        secret = request.headers.get('X-Secret', '')
        
        if secret != SECRET_KEY:
            return jsonify({'success': False, 'error': 'Invalid secret'}), 401
        
        key = data.get('key', '')
        
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('UPDATE keys SET is_active = 0 WHERE key_id = ?', (key,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True}), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/list', methods=['GET'])
def list_keys_endpoint():
    """List all keys (for bot use)"""
    try:
        secret = request.headers.get('X-Secret', '')
        
        if secret != SECRET_KEY:
            return jsonify({'success': False, 'error': 'Invalid secret'}), 401
        
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT key_id, duration, expiry_date, max_uses, max_devices, used_count, created_at, is_active FROM keys')
        rows = c.fetchall()
        conn.close()
        
        keys = []
        for row in rows:
            keys.append({
                'key': row[0],
                'duration': row[1],
                'expiry': row[2],
                'max_uses': row[3],
                'max_devices': row[4],
                'used_count': row[5],
                'created_at': row[6],
                'is_active': row[7] == 1
            })
        
        return jsonify({'success': True, 'keys': keys}), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ========================================
# HELPER FUNCTIONS
# ========================================

def calculate_days_remaining(expiry_date):
    if expiry_date == "never":
        return -1
    try:
        expiry = datetime.strptime(expiry_date, '%Y-%m-%d')
        remaining = (expiry - datetime.now()).days
        return max(0, remaining)
    except:
        return -1

# ========================================
# START THE SERVER
# ========================================

if __name__ == '__main__':
    init_db()
    print("=" * 60)
    print("🤖 BOT KEY API SERVER")
    print(f"🔑 Secret: {SECRET_KEY}")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=True)
