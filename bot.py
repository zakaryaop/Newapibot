# ========================================
# TELEGRAM BOT FOR KEY GENERATION
# Deployed on Railway with Server
# ========================================

import telebot
import requests
import json
import os
import time
from datetime import datetime

# ========================================
# CONFIGURATION - SET THESE IN RAILWAY
# ========================================

BOT_TOKEN = os.environ.get('BOT_TOKEN', 'YOUR_BOT_TOKEN')
API_URL = os.environ.get('API_URL', 'http://localhost:8080')
SECRET_KEY = os.environ.get('SECRET_KEY', 'ZAKPUBG_SECRET_KEY_2026')

# Admin user IDs (who can generate keys)
# Get your user ID from @userinfobot on Telegram
ADMINS = [int(id.strip()) for id in os.environ.get('ADMINS', '123456789').split(',')]

bot = telebot.TeleBot(BOT_TOKEN)

# ========================================
# HELPER FUNCTIONS
# ========================================

def call_api(endpoint, data=None, method='POST'):
    """Helper to call the API"""
    try:
        url = f"{API_URL}/{endpoint}"
        headers = {
            'Content-Type': 'application/json',
            'X-Secret': SECRET_KEY
        }
        
        if method.upper() == 'POST':
            response = requests.post(url, json=data, headers=headers)
        else:
            response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            return {'success': False, 'error': f'API Error: {response.status_code}'}
            
    except Exception as e:
        return {'success': False, 'error': str(e)}

# ========================================
# BOT COMMANDS
# ========================================

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    username = message.from_user.username or 'No username'
    
    welcome_text = f"""
🔑 <b>ZAKPUBGSKIN KEY BOT</b>

Welcome to the key generation bot!

<b>Your Info:</b>
🆔 User ID: <code>{user_id}</code>
👤 Username: @{username}

📌 <b>Commands:</b>
/generate - Generate a new key
/status KEY - Check key status
/help - Show help
/list - List all keys (Admin only)
/revoke KEY - Revoke a key (Admin only)
/stats - Show statistics (Admin only)

🔒 Keys are verified online and work instantly.

💬 Contact @ZAKPUBGSKIN for support
"""
    bot.reply_to(message, welcome_text, parse_mode='HTML')

@bot.message_handler(commands=['help'])
def send_help(message):
    help_text = """
📖 <b>Help Guide</b>

🔑 <b>How to get a key:</b>
1. Contact @ZAKPUBGSKIN
2. Get authorization
3. Use /generate command

📌 <b>Key Format:</b>
KEY|DURATION|EXPIRY|MAX_USES|MAX_DEVICES

Example: ABC123|30|2026-12-31|0|1

⚙️ <b>Commands:</b>
/generate - Generate new key
/status KEY - Check key status
/revoke KEY - Revoke a key (Admin only)
/list - List all keys (Admin only)
/stats - Show statistics (Admin only)

💬 Support: @ZAKPUBGSKIN
"""
    bot.reply_to(message, help_text, parse_mode='HTML')

@bot.message_handler(commands=['generate'])
def generate_key(message):
    user_id = message.from_user.id
    
    if user_id not in ADMINS:
        bot.reply_to(message, "❌ You are not authorized to generate keys.\nContact @ZAKPUBGSKIN")
        return
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, """
❌ <b>Usage:</b> /generate <options>

<b>Options:</b>
/duration: 3, 7, 30, permanent, single
/expiry: YYYY-MM-DD (optional)
/uses: number of uses (0 = unlimited)
/devices: max devices (0 = unlimited)

<b>Examples:</b>
/generate /duration:30 /uses:0 /devices:1
/generate /duration:permanent /devices:5
/generate /duration:single
""", parse_mode='HTML')
        return
    
    duration = "permanent"
    expiry = None
    max_uses = 0
    max_devices = 0
    
    for arg in args[1:]:
        if arg.startswith('/duration:'):
            duration = arg.split(':')[1]
        elif arg.startswith('/expiry:'):
            expiry = arg.split(':')[1]
        elif arg.startswith('/uses:'):
            max_uses = int(arg.split(':')[1])
        elif arg.startswith('/devices:'):
            max_devices = int(arg.split(':')[1])
    
    # Send typing indicator
    bot.send_chat_action(message.chat.id, 'typing')
    
    result = call_api('generate', {
        'duration': duration,
        'expiry': expiry,
        'max_uses': max_uses,
        'max_devices': max_devices,
        'owner_id': str(user_id)
    })
    
    if result.get('success'):
        key = result['key']
        
        key_message = f"""
✅ <b>Key Generated Successfully!</b>

🔑 <b>Your Key:</b>
<code>{key}</code>

📌 <b>Instructions:</b>
1. Copy the key above
2. Create a file named <b>mod_key.txt</b>
3. Paste the key in the file
4. Place the file in game folder
5. Start the game

<b>Details:</b>
📅 Duration: {duration}
📅 Expires: {expiry or 'never'}
📊 Uses: {max_uses if max_uses > 0 else 'unlimited'}
📱 Devices: {max_devices if max_devices > 0 else 'unlimited'}

💬 Support: @ZAKPUBGSKIN
"""
        bot.reply_to(message, key_message, parse_mode='HTML')
    else:
        bot.reply_to(message, f"❌ Error: {result.get('error', 'Unknown error')}")

@bot.message_handler(commands=['status'])
def check_status(message):
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "❌ Usage: /status KEY")
        return
    
    key = args[1]
    
    bot.send_chat_action(message.chat.id, 'typing')
    
    result = call_api('verify', {'key': key, 'device': 'check'})
    
    if result.get('valid', False):
        status_text = f"""
✅ <b>Key is VALID</b>

🔑 Key: {key[:4]}****
📅 Duration: {result.get('duration', 'unknown')}
📅 Expires: {result.get('expiry', 'never')}
📊 Uses: {result.get('used_count', 0)}/{result.get('max_uses', 0)}
📱 Devices: {result.get('max_devices', 0)} max
⏰ Days Left: {result.get('days_remaining', -1)}
"""
        bot.reply_to(message, status_text, parse_mode='HTML')
    else:
        bot.reply_to(message, f"❌ Key is INVALID\n{result.get('error', '')}")

@bot.message_handler(commands=['revoke'])
def revoke_key(message):
    user_id = message.from_user.id
    
    if user_id not in ADMINS:
        bot.reply_to(message, "❌ Admin only")
        return
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "❌ Usage: /revoke KEY")
        return
    
    key = args[1]
    
    result = call_api('revoke', {'key': key})
    
    if result.get('success'):
        bot.reply_to(message, f"✅ Key revoked: {key}")
    else:
        bot.reply_to(message, f"❌ Failed to revoke key\n{result.get('error', '')}")

@bot.message_handler(commands=['list'])
def list_keys(message):
    user_id = message.from_user.id
    
    if user_id not in ADMINS:
        bot.reply_to(message, "❌ Admin only")
        return
    
    result = call_api('list', method='GET')
    
    if result.get('success'):
        keys = result.get('keys', [])
        if not keys:
            bot.reply_to(message, "📭 No keys found")
            return
        
        text = "📋 <b>All Keys:</b>\n\n"
        for k in keys[:15]:
            status = "✅" if k['is_active'] else "❌"
            owner = k.get('owner_id', 'unknown')[:6]
            text += f"{status} <code>{k['key'][:8]}...</code> | {k['duration']} | Uses: {k['used_count']}/{k['max_uses']} | Owner: {owner}\n"
        
        if len(keys) > 15:
            text += f"\n... and {len(keys) - 15} more"
        
        text += f"\n\n📊 Total: {len(keys)} keys"
        
        bot.reply_to(message, text, parse_mode='HTML')
    else:
        bot.reply_to(message, f"❌ Failed to list keys\n{result.get('error', '')}")

@bot.message_handler(commands=['stats'])
def show_stats(message):
    user_id = message.from_user.id
    
    if user_id not in ADMINS:
        bot.reply_to(message, "❌ Admin only")
        return
    
    result = call_api('stats', method='GET')
    
    if result.get('success'):
        stats = result.get('stats', {})
        stats_text = f"""
📊 <b>System Statistics</b>

🔑 Active Keys: {stats.get('active_keys', 0)}
📋 Total Keys: {stats.get('total_keys', 0)}
📱 Registered Devices: {stats.get('total_devices', 0)}

🕐 Server Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        bot.reply_to(message, stats_text, parse_mode='HTML')
    else:
        bot.reply_to(message, f"❌ Failed to get stats\n{result.get('error', '')}")

@bot.message_handler(commands=['ping'])
def ping(message):
    """Check if bot is alive"""
    bot.reply_to(message, "🏓 Pong! Bot is alive!")

@bot.message_handler(func=lambda m: True)
def echo_all(message):
    """Handle unknown commands"""
    if message.text and message.text.startswith('/'):
        bot.reply_to(message, "❌ Unknown command. Use /help for available commands.")

# ========================================
# START THE BOT
# ========================================

if __name__ == '__main__':
    print("=" * 60)
    print("🤖 TELEGRAM BOT STARTED")
    print(f"🔑 Bot Token: {BOT_TOKEN[:10]}...")
    print(f"🌐 API URL: {API_URL}")
    print(f"👤 Admins: {ADMINS}")
    print("=" * 60)
    
    # Test API connection
    try:
        response = requests.get(API_URL)
        print(f"✅ API Connection: {response.status_code}")
    except:
        print("⚠️ API not reachable - make sure server is running")
    
    bot.polling(none_stop=True, interval=1)
