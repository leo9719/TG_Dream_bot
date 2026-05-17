import sqlite3
from datetime import datetime

def init_db():
    """Инициализирует базу данных"""
    conn = sqlite3.connect('sonnik.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS dreams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            symbol TEXT,
            interpretation TEXT,
            timestamp DATETIME
        )
    ''')
    conn.commit()
    conn.close()

def save_interpretation(user_id: int, symbol: str, interpretation: str):
    """Сохраняет интерпретацию в базу данных"""
    conn = sqlite3.connect('sonnik.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO dreams (user_id, symbol, interpretation, timestamp)
        VALUES (?, ?, ?, ?)
    ''', (user_id, symbol, interpretation, datetime.now()))
    conn.commit()
    conn.close()

def get_cached_interpretation(symbol: str) -> str:
    """Проверяет наличие интерпретации в кеше"""
    conn = sqlite3.connect('sonnik.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT interpretation FROM dreams 
        WHERE symbol = ? 
        ORDER BY timestamp DESC 
        LIMIT 1
    ''', (symbol,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None
