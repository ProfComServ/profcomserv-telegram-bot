import os
import json
from flask import Flask, request
import requests

app = Flask(__name__)

# Токены трёх ботов (замените при необходимости)
TOKEN1 = os.environ.get('BOT_TOKEN_1', '8684012503:AAHcBc1ggVUGEHv7dY1M-YcGIuxviWwTLh0')
TOKEN2 = os.environ.get('BOT_TOKEN_2', '8223022364:AAEu31BylYStpxHxg06yyW_JY2NX32WgEPo')
TOKEN3 = os.environ.get('BOT_TOKEN_3', '8764025967:AAFS_kgxV6y9Zcg3THrrG-JNb6nErL3KrA4')
OPERATOR_ID = int(os.environ.get('OPERATOR_ID', 7137220733))

active_chats = {}  # user_id -> True

def send_message(chat_id, text, token, reply_markup=None):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': text}
    if reply_markup:
        payload['reply_markup'] = json.dumps(reply_markup)
    try:
        r = requests.post(url, json=payload, timeout=5)
        if not r.ok:
            print(f"Ошибка отправки {chat_id}: {r.status_code} {r.text}")
    except Exception as e:
        print(f"Ошибка: {e}")

def process_update(update, token, bot_num):
    # 1. Игнорируем сообщения от ботов (чтобы не зацикливаться)
    if update.get('message', {}).get('from', {}).get('is_bot', False):
        print(f"Bot {bot_num}: игнорирую сообщение от бота")
        return

    if not update:
        return

    print(f"Bot {bot_num} получил: {json.dumps(update)[:200]}")

    # Обработка обычных сообщений
    if 'message' in update:
        msg = update['message']
        chat_id = msg['chat']['id']
        user = msg['chat'].get('username', '')
        text = msg.get('text')

        # 2. Если сообщение от оператора – это ответ клиенту (формат: ID текст)
        if chat_id == OPERATOR_ID:
            if text and not text.startswith('/'):  # не команда
                parts = text.split(maxsplit=1)
                if len(parts) >= 2:
                    try:
                        target_id = int(parts[0])
                        reply_text = parts[1]
                        # Отправляем ответ клиенту через того же бота (используем текущий token)
                        send_message(target_id, f"👨‍💼 Оператор: {reply_text}", token)
                        # Подтверждение оператору
                        send_message(OPERATOR_ID, f"✅ Ответ отправлен пользователю {target_id}", token)
                    except ValueError:
                        send_message(OPERATOR_ID, "❌ Ошибка: ID пользователя должен быть числом. Пример: `123456789 Привет`", token)
                else:
                    send_message(OPERATOR_ID, "❌ Формат: `ID_пользователя текст`\nПример: `123456789 Привет`", token)
            return  # не пересылаем сообщения оператора дальше

        # Обычный пользователь
        if text == '/start':
            keyboard = {
                'inline_keyboard': [[{'text': '📞 Связаться с оператором', 'callback_data': 'operator'}]]
            }
            send_message(chat_id, 'Привет! Нажми кнопку, чтобы связаться с оператором.', token, keyboard)
        elif chat_id in active_chats:
            send_message(OPERATOR_ID, f"📩 От @{user} (id:{chat_id}): {text}", token)
            send_message(chat_id, '✉️ Сообщение отправлено оператору. Ожидайте ответа.', token)
        elif text and text != '/start':
            send_message(chat_id, 'Сначала нажмите /start и кнопку.', token)

    # Обработка нажатий кнопок
    elif 'callback_query' in update:
        query = update['callback_query']
        user_id = query['from']['id']
        if query['data'] == 'operator':
            active_chats[user_id] = True
            requests.post(f"https://api.telegram.org/bot{token}/answerCallbackQuery",
                          json={'callback_query_id': query['id']})
            edit_url = f"https://api.telegram.org/bot{token}/editMessageText"
            payload = {
                'chat_id': query['message']['chat']['id'],
                'message_id': query['message']['message_id'],
                'text': '✅ Вы переведены на оператора. Напишите сообщение.'
            }
            requests.post(edit_url, json=payload)
            send_message(OPERATOR_ID, f"🆕 Новый клиент @{query['from'].get('username', '')} (id:{user_id})", token)

# Вебхуки для трёх ботов
@app.route('/webhook/1', methods=['POST'])
def webhook1():
    process_update(request.get_json(), TOKEN1, 1)
    return 'OK', 200

@app.route('/webhook/2', methods=['POST'])
def webhook2():
    process_update(request.get_json(), TOKEN2, 2)
    return 'OK', 200

@app.route('/webhook/3', methods=['POST'])
def webhook3():
    process_update(request.get_json(), TOKEN3, 3)
    return 'OK', 200

# Альтернативный маршрут для ответов (POST /reply) – если нужно
@app.route('/reply', methods=['POST'])
def reply():
    data = request.get_json()
    if not data or 'user_id' not in data or 'text' not in data:
        return 'Bad request', 400
    send_message(data['user_id'], f"👨‍💼 Оператор: {data['text']}", TOKEN1)
    return 'OK', 200

@app.route('/')
def health():
    return 'OK', 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
