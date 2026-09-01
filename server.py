# ========================================
# TELEGRAM BOT KEY API SERVER
# ========================================
# Host this on a server (VPS, Replit, etc.)
# ========================================

from flask import Flask, request, jsonify
import json
import hashlib
import time
from datetime import datetime, timedelta
import sqlite3
import os

app = Flask(__name__)

# ========================================
# CONFIGURATION
# ========================================

SECRET_KEY = "zakpubgskin_2029_key_@@1122"  # Same as in Lua config
DB_FILE = "keys.db"

# ========================================
# DATABASE SETUP
# ========================================

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Create tables
    c.execute('''CREATE TABLE IF NOT EXISTS keys (
        key_id TEXT PRIMARY KEY,
        duration TEXT,
        expiry_date TEXT,
        max_uses INTEGER,
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