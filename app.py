"""
MoodMagic API — Полная версия
С регистрацией, фото, аналитикой тегов, сравнением месяцев, календарём, сменой темы
Запуск: py app.py
"""

import os
from flask import Flask, request, jsonify, render_template, session
from flask_cors import CORS
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import uuid

from database import (
    init_db, create_user, verify_user, get_user_by_id,
    add_mood_to_db, get_moods_by_user, get_mood_by_date, update_mood, delete_mood,
    get_mood_stats, get_monthly_comparison, analyze_tags,
    add_alert_rule_to_db, get_alert_rules_from_db, check_and_trigger_alerts
)

app = Flask(__name__)
app.secret_key = "moodmagic_secret_key_2025"
CORS(app)

# ========== НАСТРОЙКИ ЗАГРУЗКИ ФОТО ==========
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# БД
init_db()

# ========== ВЕБ-ИНТЕРФЕЙС ==========
@app.route('/')
def index():
    return render_template('index.html')

# ========== АВТОРИЗАЦИЯ ==========
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'error': 'Логин и пароль обязательны'}), 400

    user_id = create_user(username, password)
    if user_id:
        session['user_id'] = user_id
        session['username'] = username
        return jsonify({'success': True, 'user_id': user_id, 'username': username})
    else:
        return jsonify({'error': 'Пользователь уже существует'}), 400

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    user_id = verify_user(username, password)
    if user_id:
        session['user_id'] = user_id
        session['username'] = username
        return jsonify({'success': True, 'user_id': user_id, 'username': username})
    else:
        return jsonify({'error': 'Неверный логин или пароль'}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})

@app.route('/api/me', methods=['GET'])
def me():
    if 'user_id' in session:
        return jsonify({'user_id': session['user_id'], 'username': session['username']})
    return jsonify({'error': 'Не авторизован'}), 401

# ========== ЗАПИСИ НАСТРОЕНИЙ ==========
@app.route('/api/mood', methods=['POST'])
def add_or_update_mood():
    if 'user_id' not in session:
        return jsonify({'error': 'Авторизуйтесь'}), 401

    data = request.get_json()
    date = data.get('date', datetime.now().strftime('%Y-%m-%d'))
    score = data.get('score')
    note = data.get('note')
    tags = data.get('tags', [])
    image_path = data.get('image_path')

    if not score or not 1 <= score <= 6:
        return jsonify({'error': 'Оценка от 1 до 6'}), 400

    existing = get_mood_by_date(session['user_id'], date)

    if existing:
        update_mood(session['user_id'], date, score, note, tags, image_path)
        msg = "обновлена"
    else:
        add_mood_to_db(session['user_id'], score, date, note, tags, image_path)
        msg = "добавлена"

    # Умные магические сообщения (1-6)
    if score <= 2:
        magic = "💜 Держись! Я рядом. Ты не одна 💜"
    elif score == 3:
        magic = "🍵 Выпей чай, обними кота. Всё наладится 🌙"
    elif score == 4:
        magic = "🌿 Хороший день. Завтра будет ещё лучше 🌿"
    elif score == 5:
        magic = "🌸 Отличный день! Запомни это чувство 🌸"
    else:
        magic = "✨ Ты сегодня суперзвезда! Так держать ✨"

    triggered = check_and_trigger_alerts(session['user_id'], score)
    # Оставляем все правила для интерфейса, но для уведомления возьмём одно случайное
    import random
    if triggered:
        triggered = [random.choice(triggered)]

    return jsonify({
        'status': 'success',
        'message': f'Запись {msg}',
        'magic_message': magic,
        'triggered_alerts': triggered
    })

@app.route('/api/mood/upload-photo', methods=['POST'])
def upload_photo():
    if 'user_id' not in session:
        return jsonify({'error': 'Авторизуйтесь'}), 401

    if 'photo' not in request.files:
        return jsonify({'error': 'Нет файла'}), 400

    file = request.files['photo']
    date = request.form.get('date', datetime.now().strftime('%Y-%m-%d'))

    if file.filename == '':
        return jsonify({'error': 'Файл не выбран'}), 400

    if file and allowed_file(file.filename):
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{session['user_id']}_{date}_{uuid.uuid4().hex[:6]}.{ext}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        return jsonify({'image_path': filename, 'message': 'Фото загружено'})

    return jsonify({'error': 'Недопустимый формат'}), 400

@app.route('/api/mood/all', methods=['GET'])
def get_all_moods():
    if 'user_id' not in session:
        return jsonify({'error': 'Авторизуйтесь'}), 401

    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    moods = get_moods_by_user(session['user_id'], start_date, end_date)
    return jsonify({'entries': moods, 'total': len(moods)})

@app.route('/api/mood/<int:mood_id>', methods=['DELETE'])
def delete_mood_entry(mood_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Авторизуйтесь'}), 401

    if delete_mood(session['user_id'], mood_id):
        return jsonify({'success': True})
    return jsonify({'error': 'Не найдено'}), 404

# ========== АНАЛИТИКА ==========
@app.route('/api/stats', methods=['GET'])
def stats():
    if 'user_id' not in session:
        return jsonify({'error': 'Авторизуйтесь'}), 401

    stats = get_mood_stats(session['user_id'])
    return jsonify(stats or {})

@app.route('/api/monthly-comparison', methods=['GET'])
def monthly_comparison():
    if 'user_id' not in session:
        return jsonify({'error': 'Авторизуйтесь'}), 401

    comp = get_monthly_comparison(session['user_id'])
    return jsonify(comp or {})

@app.route('/api/tag-analysis', methods=['GET'])
def tag_analysis():
    if 'user_id' not in session:
        return jsonify({'error': 'Авторизуйтесь'}), 401

    tags = analyze_tags(session['user_id'])
    return jsonify({'tags': tags})

# ========== ПРАВИЛА ==========
@app.route('/api/alert/rule', methods=['POST'])
def add_rule():
    if 'user_id' not in session:
        return jsonify({'error': 'Авторизуйтесь'}), 401

    data = request.get_json()
    min_score = data.get('min_score')
    message = data.get('message')

    if not min_score or not message:
        return jsonify({'error': 'Поля обязательны'}), 400

    rule_id = add_alert_rule_to_db(session['user_id'], min_score, message)
    return jsonify({'success': True, 'id': rule_id})

@app.route('/api/alert/rules', methods=['GET'])
def get_rules():
    if 'user_id' not in session:
        return jsonify({'error': 'Авторизуйтесь'}), 401

    rules = get_alert_rules_from_db(session['user_id'])
    return jsonify({'rules': rules})


@app.route('/static/uploads/<filename>')
def uploaded_file(filename):
    from flask import send_from_directory
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ========== ЗАПУСК ==========
if __name__ == '__main__':
    print("🌸 MoodMagic запущен с поддержкой пользователей и фото!")
    print("📱 Открой в браузере: http://127.0.0.1:5000")
    print("🔐 Не забудь зарегистрироваться!")
    app.run(debug=True, host='127.0.0.1', port=5000)