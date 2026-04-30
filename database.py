import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
import bcrypt

DATABASE_NAME = "mood.db"


@contextmanager
def get_db():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS moods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                score INTEGER NOT NULL,
                note TEXT,
                tags TEXT,
                image_path TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alert_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                min_score INTEGER NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        print("✅ База данных инициализирована")


def create_user(username: str, password: str):
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, password_hash))
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None


def verify_user(username: str, password: str):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, password_hash FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        if user and bcrypt.checkpw(password.encode('utf-8'), user['password_hash']):
            return user['id']
        return None


def get_user_by_id(user_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, username FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def add_mood_to_db(user_id: int, score: int, date: str, note: str = None, tags: list = None, image_path: str = None):
    with get_db() as conn:
        cursor = conn.cursor()
        tags_str = ",".join(tags) if tags else ""
        cursor.execute("""
            INSERT INTO moods (user_id, date, score, note, tags, image_path)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, date, score, note, tags_str, image_path))
        return cursor.lastrowid


def get_moods_by_user(user_id: int, start_date: str = None, end_date: str = None):
    with get_db() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM moods WHERE user_id = ?"
        params = [user_id]
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        query += " ORDER BY date DESC"
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def get_mood_by_date(user_id: int, date: str):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM moods WHERE user_id = ? AND date = ?", (user_id, date))
        row = cursor.fetchone()
        return dict(row) if row else None


def update_mood(user_id: int, date: str, score: int, note: str = None, tags: list = None, image_path: str = None):
    with get_db() as conn:
        cursor = conn.cursor()
        tags_str = ",".join(tags) if tags else ""
        cursor.execute("""
            UPDATE moods SET score = ?, note = ?, tags = ?, image_path = ?
            WHERE user_id = ? AND date = ?
        """, (score, note, tags_str, image_path, user_id, date))
        return cursor.rowcount > 0


def delete_mood(user_id: int, mood_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM moods WHERE id = ? AND user_id = ?", (mood_id, user_id))
        return cursor.rowcount > 0


def get_mood_stats(user_id: int):
    moods = get_moods_by_user(user_id)
    if not moods:
        return None
    scores = [m['score'] for m in moods]
    return {'average': round(sum(scores) / len(scores), 1), 'max': max(scores), 'min': min(scores),
            'total': len(scores)}


def get_monthly_comparison(user_id: int):
    now = datetime.now()
    current_month = now.strftime("%Y-%m")
    last_month = (now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")

    current_moods = get_moods_by_user(user_id, f"{current_month}-01", f"{current_month}-31")
    last_moods = get_moods_by_user(user_id, f"{last_month}-01", f"{last_month}-31")

    def avg_score(moods):
        if not moods:
            return None
        return sum(m['score'] for m in moods) / len(moods)

    current_avg = avg_score(current_moods)
    last_avg = avg_score(last_moods)

    if current_avg is None or last_avg is None or last_avg == 0:
        return None

    percent_change = ((current_avg - last_avg) / last_avg) * 100
    return {'current_avg': round(current_avg, 1), 'last_avg': round(last_avg, 1),
            'percent_change': round(percent_change, 1), 'happier': percent_change > 0}


def analyze_tags(user_id: int):
    moods = get_moods_by_user(user_id)
    tag_scores = {}
    for mood in moods:
        if mood['tags']:
            for tag in mood['tags'].split(','):
                tag = tag.strip()
                if tag not in tag_scores:
                    tag_scores[tag] = {'total': 0, 'count': 0}
                tag_scores[tag]['total'] += mood['score']
                tag_scores[tag]['count'] += 1
    result = [{'tag': tag, 'avg_score': round(data['total'] / data['count'], 1), 'count': data['count']} for tag, data
              in tag_scores.items()]
    result.sort(key=lambda x: x['avg_score'])
    return result


def add_alert_rule_to_db(user_id: int, min_score: int, message: str):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO alert_rules (user_id, min_score, message) VALUES (?, ?, ?)",
                       (user_id, min_score, message))
        return cursor.lastrowid


def get_alert_rules_from_db(user_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM alert_rules WHERE user_id = ? ORDER BY min_score ASC", (user_id,))
        return [dict(row) for row in cursor.fetchall()]


def check_and_trigger_alerts(user_id: int, score: int):
    rules = get_alert_rules_from_db(user_id)
    return [rule['message'] for rule in rules if score <= rule['min_score']]