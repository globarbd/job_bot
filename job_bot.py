import requests
import telebot
from urllib.parse import quote, urlencode
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import base64
import time
import threading
from telebot import types

# Configuration
USER_INFO_API = "https://w8job.cyou/api/user/userInfo"
SEND_CODE_API = "https://w8job.cyou/api/task/send_code"
GET_CODE_API = "https://w8job.cyou/api/task/get_code"
PHONE_LIST_API = "https://w8job.cyou/api/task/phone_list"
TELEGRAM_BOT_TOKEN = "7627569338:AAEsI7Gorv6D8mp_M0HuxfsjuXM4jcWhRCM"

# AES Encryption
SECRET_KEY = b"djchdnfkxnjhgvuy"
IV = b"ayghjuiklobghfrt"
MODE = AES.MODE_CBC

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# Admin and access control
ADMINS = [6860725184, 7936173004]  # Admin user IDs
allowed_users = set(ADMINS)  # Initially only admins are allowed
user_tokens = {}  # {chat_id: token}
pending_confirmations = {}  # {chat_id: {'phone': phone, 'message_id': message_id}}

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

def validate_token(token):
    try:
        response = requests.get(USER_INFO_API, headers=get_headers(token), timeout=10)
        return response.status_code == 200 and response.json().get('code') == 1
    except:
        return False

def check_phone_binding(token, phone):
    """Check if phone is successfully bound using phone_list API"""
    try:
        response = requests.post(
            PHONE_LIST_API,
            headers=get_headers(token),
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json().get('data', [])
            for item in data:
                if str(item.get('phone')) == str(phone):
                    return True
        return False
    except:
        return False

def process_verification(phone, chat_id):
    if not is_user_allowed(chat_id):
        bot.send_message(chat_id, "You don't have access to use this bot")
        return
        
    token = user_tokens.get(chat_id)
    if not token:
        bot.send_message(chat_id, "Login first")
        return
    
    try:
        # Step 1: Send encrypted phone with + sign
        encrypted = encrypt_phone(phone)
        send_response = requests.post(
            SEND_CODE_API,
            headers=get_headers(token),
            data=f"phone={quote(encrypted)}",
            timeout=10
        )
        
        if not (send_response.status_code == 200 and send_response.json().get('code') == 1):
            bot.send_message(chat_id, "Failed to send code")
            return

        # Step 2: Get decoded number (should include + sign)
        decoded = send_response.json().get('data', {}).get('phone')
        if not decoded:
            bot.send_message(chat_id, "Failed to decode phone")
            return

        # Step 3: Get verification code with original phone (including +)
        for attempt in range(5):
            try:
                get_response = requests.post(
                    GET_CODE_API,
                    headers=get_headers(token),
                    data=urlencode({'is_agree': 1, 'phone': phone}),
                    timeout=10
                )
                
                if get_response.status_code == 200:
                    response_data = get_response.json()
                    if response_data.get('code') == 1:
                        if code := response_data.get('data', {}).get('code'):
                            markup = types.InlineKeyboardMarkup()
                            confirm_btn = types.InlineKeyboardButton("Confirm", callback_data="confirm_binding")
                            markup.add(confirm_btn)
                            
                            sent_msg = bot.send_message(
                                chat_id, 
                                f"Code: {code}\n\nConfirm binding?", 
                                reply_markup=markup
                            )
                            
                            pending_confirmations[chat_id] = {
                                'phone': phone,
                                'message_id': sent_msg.message_id
                            }
                            return
                
                time.sleep(3 + attempt)
                
            except requests.exceptions.RequestException:
                time.sleep(3 + attempt)
                continue

        bot.send_message(chat_id, "Code not ready")

    except Exception as e:
        bot.send_message(chat_id, f"Error: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data == "confirm_binding")
def handle_confirmation(call):
    chat_id = call.message.chat.id
    if not is_user_allowed(chat_id):
        bot.answer_callback_query(call.id, "Access denied")
        return
        
    token = user_tokens.get(chat_id)
    pending_data = pending_confirmations.get(chat_id)
    
    if not token or not pending_data:
        bot.answer_callback_query(call.id, "Session expired")
        return
    
    phone = pending_data['phone']
    message_id = pending_data['message_id']
    
    for attempt in range(3):
        if check_phone_binding(token, phone):
            try:
                bot.delete_message(chat_id, message_id)
            except:
                pass
                
            bot.answer_callback_query(call.id, "Success")
            bot.send_message(chat_id, "Success")
            pending_confirmations.pop(chat_id, None)
            return
        
        time.sleep(1)
    
    try:
        bot.delete_message(chat_id, message_id)
    except:
        pass
        
    bot.answer_callback_query(call.id, "Rejected")
    bot.send_message(chat_id, "Rejected")
    pending_confirmations.pop(chat_id, None)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    if not is_user_allowed(message.chat.id):
        bot.send_message(message.chat.id, "You don't have access to use this bot")
        return
        
    bot.send_message(message.chat.id, "Send your token (must contain 4 hyphens) or phone number starting with +")

@bot.message_handler(commands=['access'])
def handle_access_command(message):
    if message.from_user.id not in ADMINS:
        bot.send_message(message.chat.id, "You are not authorized to use this command")
        return
    
    try:
        # Command format: /access 738737837
        user_id = int(message.text.split()[1])
        allowed_users.add(user_id)
        bot.send_message(message.chat.id, f"User {user_id} has been granted access")
    except (IndexError, ValueError):
        bot.send_message(message.chat.id, "Invalid format. Use: /access USER_ID")

@bot.message_handler(func=lambda message: message.text.count('-') == 4)
def handle_token(message):
    if not is_user_allowed(message.chat.id):
        bot.send_message(message.chat.id, "You don't have access to use this bot")
        return
        
    token = message.text.strip()
    if validate_token(token):
        user_tokens[message.chat.id] = token
        bot.send_message(message.chat.id, "Success")
    else:
        bot.send_message(message.chat.id, "Rejected")

@bot.message_handler(func=lambda message: message.text.startswith('+'))
def handle_phone(message):
    if not is_user_allowed(message.chat.id):
        bot.send_message(message.chat.id, "You don't have access to use this bot")
        return
        
    phone = message.text.strip()
    threading.Thread(target=process_verification, args=(phone, message.chat.id)).start()

@bot.message_handler(func=lambda message: True)
def handle_invalid(message):
    if not is_user_allowed(message.chat.id):
        return
        
    bot.send_message(message.chat.id, "Invalid format. Send token (with 4 hyphens) or phone number starting with +")

if __name__ == '__main__':
    print("Bot is running...")
    bot.polling(none_stop=True)
