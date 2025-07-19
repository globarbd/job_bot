import os
import requests
import telebot
from urllib.parse import quote, urlencode
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import base64
import time
import threading
from telebot import types
from flask import Flask, request, jsonify

# Configuration
USER_INFO_API = "https://w8job.cyou/api/user/userInfo"
SEND_CODE_API = "https://w8job.cyou/api/task/send_code"
GET_CODE_API = "https://w8job.cyou/api/task/get_code"
PHONE_LIST_API = "https://w8job.cyou/api/task/phone_list"
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '7627569338:AAEsI7Gorv6D8mp_M0HuxfsjuXM4jcWhRCM')

# Initialize Flask app for webhook
app = Flask(__name__)
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# Admin and access control
ADMINS = [6860725184, 7936173004]  # Admin user IDs
allowed_users = set(ADMINS)  # Initially only admins are allowed
user_tokens = {}  # {chat_id: token}
pending_confirmations = {}  # {chat_id: {'phone': phone, 'message_id': message_id}}

# Webhook route
@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    return 'Invalid content type', 403

def is_user_allowed(chat_id):
    return chat_id in allowed_users

def encrypt_phone(phone):
    cipher = AES.new(SECRET_KEY, MODE, IV)
    padded_data = pad(phone.encode('utf-8'), AES.block_size)
    encrypted = cipher.encrypt(padded_data)
    return base64.b64encode(encrypted).decode('utf-8')

def get_headers(token):
    return {
        'Host': 'w8job.cyou',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Token': token,
        'Origin': 'https://www.w8job.club',
        'Referer': 'https://www.w8job.club/',
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; SM-G960F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Mobile Safari/537.36',
        'X-Requested-With': 'mark.via.gp'
    }

# ... [Rest of your existing functions remain the same] ...

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    if not is_user_allowed(message.chat.id):
        bot.send_message(message.chat.id, "You don't have access to use this bot")
        return
        
    bot.send_message(message.chat.id, "Send your token (must contain 4 hyphens) or phone number starting with +")

# ... [Keep all your existing message handlers] ...

def run_bot():
    # Remove any existing webhook
    bot.remove_webhook()
    
    # Set webhook for production
    if os.getenv('ENVIRONMENT') == 'production':
        webhook_url = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/webhook"
        bot.set_webhook(url=webhook_url)
        app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
    else:
        # Local development with polling
        bot.polling(none_stop=True)

if __name__ == '__main__':
    run_bot()
