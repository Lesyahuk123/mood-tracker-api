"""
MoodMagic API — трекер настроения с магическими уведомлениями
Версия на Flask с веб-интерфейсом + Telegram бот
Запуск: python app.py
"""

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from database import (
    init_db, add_mood_to_db, get_today_mood_from_db,
    get_week_mood_from_db, get_all_moods_from_db,
    add_alert_rule_to_db, get_alert_rules_from_db,
    check_and_trigger_alerts, delete_mood_from_db, get_mood_by_id
)
import threading
import time
import requests
from datetime import datetime, time as dt_time
import json

app = Flask(__name__)
CORS(app)

# НАСТРОЙКИ TELEGRAM
TELEGRAM_BOT_TOKEN = "8784241074:AAEtDPQmXeHfNND3zjIH7Mv8qi_SFLtOeDg"
TELEGRAM_CHAT_ID = "6563472240"

def send_telegram_message(message):
    """Отправка сообщения в Telegram"""
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print(f"📱 [TELEGRAM_DEBUG] {message}")
        return False

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        response = requests.post(url, json=payload)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Ошибка отправки в Telegram: {e}")
        return False

# ========== ФОНОВЫЙ ПОТОК ДЛЯ НАПОМИНАНИЙ ==========
reminder_sent_today = False

def reminder_worker():
    """Фоновый поток, который проверяет время и отправляет напоминание в 20:00"""
    global reminder_sent_today
    while True:
        now = datetime.now()
        target_time = dt_time(20, 0)  # 20:00

        # Если время совпадает и напоминание ещё не отправлено сегодня
        if now.time().hour == target_time.hour and now.time().minute == target_time.minute:
            if not reminder_sent_today:
                message = "🌸 Привет! Как твоё настроение сегодня?\n\nНапиши /mood или зайди в трекер, чтобы записать свои эмоции. Я рядом! 💕"
                send_telegram_message(message)
                reminder_sent_today = True
        else:
            # Сброс флага в полночь
            if now.time().hour == 0 and now.time().minute == 0:
                reminder_sent_today = False

        time.sleep(30)  # Проверяем каждые 30 секунд

# Запускаем фоновый поток
reminder_thread = threading.Thread(target=reminder_worker, daemon=True)
reminder_thread.start()

# Инициализируем базу данных
init_db()

# ========== ВЕБ-ИНТЕРФЕЙС ==========
@app.route('/')
def index():
    """Главная страница с веб-интерфейсом"""
    return render_template('index.html')

# ========== API ЭНДПОИНТЫ ==========

@app.route('/api/mood', methods=['POST'])
def add_mood():
    """Записать настроение за сегодня"""
    data = request.get_json()

    score = data.get('score')
    note = data.get('note')
    tags = data.get('tags', [])

    if not score or not 1 <= score <= 10:
        return jsonify({'error': 'Оценка должна быть от 1 до 10'}), 400

    mood_id = add_mood_to_db(score, note, tags)

    if score <= 3:
        magic_msg = "💜 Держись! Я рядом. Хочешь обнимемся? 💜"
        # Отправляем уведомление в Telegram при плохом настроении
        send_telegram_message(f"🌧️ Я заметила, что тебе грустно (оценка: {score}/10).\n\n{magic_msg}\n\nТы не одна! ❤️")
    elif score <= 6:
        magic_msg = "🌙 Всё будет хорошо. Сегодня просто такой день. 🌙"
    else:
        magic_msg = "✨ Ты сегодня сияешь! Сохрани эту искру! ✨"
        send_telegram_message(f"☀️ У тебя отличное настроение ({score}/10)! Рада за тебя! Продолжай в том же духе! 🎉")

    triggered_alerts = check_and_trigger_alerts(score)
    if triggered_alerts:
        for alert in triggered_alerts:
            send_telegram_message(f"🔔 {alert}")

    return jsonify({
        'status': 'success',
        'id': mood_id,
        'score': score,
        'magic_message': magic_msg,
        'triggered_alerts': triggered_alerts if triggered_alerts else None
    })

@app.route('/api/mood/today', methods=['GET'])
def get_today_mood():
    entry = get_today_mood_from_db()
    if entry:
        return jsonify({'found': True, 'entry': entry})
    return jsonify({'found': False, 'message': 'Сегодня ещё нет записей 💕'})

@app.route('/api/mood/week', methods=['GET'])
def get_week_mood():
    entries = get_week_mood_from_db()
    if not entries:
        return jsonify({'message': 'Нет данных за эту неделю'})
    avg_score = sum(e["score"] for e in entries) / len(entries)
    return jsonify({
        'total_entries': len(entries),
        'average_mood': round(avg_score, 1),
        'entries': entries
    })

@app.route('/api/mood/all', methods=['GET'])
def get_all_moods():
    entries = get_all_moods_from_db()
    if not entries:
        return jsonify({'message': 'История пуста'})
    return jsonify({'total_entries': len(entries), 'entries': entries})

@app.route('/api/mood/<int:mood_id>', methods=['DELETE'])
def delete_mood(mood_id):
    """Удалить запись о настроении"""
    success = delete_mood_from_db(mood_id)
    if success:
        return jsonify({'status': 'success', 'message': f'Запись {mood_id} удалена'})
    return jsonify({'error': 'Запись не найдена'}), 404

@app.route('/api/alert/rule', methods=['POST'])
def add_alert_rule():
    data = request.get_json()
    min_score = data.get('min_score')
    message = data.get('message')

    if not min_score or not 1 <= min_score <= 10:
        return jsonify({'error': 'min_score должен быть от 1 до 10'}), 400
    if not message:
        return jsonify({'error': 'message не может быть пустым'}), 400

    rule_id = add_alert_rule_to_db(min_score, message)
    return jsonify({'status': 'success', 'id': rule_id, 'message': f'✅ Правило добавлено!'})

@app.route('/api/alert/rules', methods=['GET'])
def get_alert_rules():
    rules = get_alert_rules_from_db()
    if not rules:
        return jsonify({'message': 'Пока нет правил'})
    return jsonify({'rules': rules})

# ========== ЗАПУСК ==========
if __name__ == '__main__':
    print("🌸 MoodMagic запущен!")
    print("📱 Открой в браузере: http://127.0.0.1:5000")
    print("🤖 Telegram бот активен (если настроен)")
    print("⏰ Напоминания в 20:00 активны")
    app.run(debug=True, host='127.0.0.1', port=5000)