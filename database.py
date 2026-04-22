"""
Модуль для работы с SQLite базой данных
"""

import sqlite3
from contextlib import contextmanager

DATABASE_NAME = "mood.db"


@contextmanager
def get_db():
    """Контекстный менеджер для подключения к БД"""
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Создание таблицы"""
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS moods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                score INTEGER NOT NULL,
                note TEXT,
                tags TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alert_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                min_score INTEGER NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        print("✅ База данных инициализирована")


def add_mood_to_db(score: int, note: str = None, tags: list = None):
    """Добавить запись настроения"""
    with get_db() as conn:
        cursor = conn.cursor()
        tags_str = ",".join(tags) if tags else ""
        cursor.execute("""
            INSERT INTO moods (date, score, note, tags)
            VALUES (date('now'), ?, ?, ?)
        """, (score, note, tags_str))
        return cursor.lastrowid


def get_today_mood_from_db():
    """Получить запись за сегодня"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM moods 
            WHERE date = date('now')
            ORDER BY id DESC LIMIT 1
        """)
        row = cursor.fetchone()
        return dict(row) if row else None


def get_week_mood_from_db():
    """Получить записи за последние 7 дней"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM moods 
            WHERE date >= date('now', '-7 days')
            ORDER BY date DESC
        """)
        return [dict(row) for row in cursor.fetchall()]


def get_all_moods_from_db():
    """Получить все записи настроения"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM moods ORDER BY date DESC")
        return [dict(row) for row in cursor.fetchall()]


def add_alert_rule_to_db(min_score: int, message: str):
    """Добавить правило уведомления"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO alert_rules (min_score, message)
            VALUES (?, ?)
        """, (min_score, message))
        return cursor.lastrowid


def get_alert_rules_from_db():
    """Получить все правила уведомлений"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM alert_rules ORDER BY min_score ASC")
        return [dict(row) for row in cursor.fetchall()]


def check_and_trigger_alerts(score: int):
    """Проверить, нужно ли сработать уведомлениям"""
    rules = get_alert_rules_from_db()
    triggered = []
    for rule in rules:
        if score <= rule["min_score"]:
            triggered.append(rule["message"])
    return triggered


def delete_mood_from_db(mood_id: int):
    """Удалить запись настроения по ID"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM moods WHERE id = ?", (mood_id,))
        return cursor.rowcount > 0

def get_mood_by_id(mood_id: int):
    """Получить запись по ID"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM moods WHERE id = ?", (mood_id,))
        row = cursor.fetchone()
        return dict(row) if row else None