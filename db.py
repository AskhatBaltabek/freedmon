import sqlite3
from datetime import datetime, timedelta
import os

DB_PATH = "freedmon.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Equities table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS equities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pre_market REAL,
            post_market REAL,
            live_price REAL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Currencies table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS currencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rate REAL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # OCR Data table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ocr_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rate REAL,
            snapshot_path TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Calculations table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS calculations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            calculated_rate REAL,
            ocr_rate REAL,
            difference_percent REAL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Users table for subscriptions
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT UNIQUE,
            platform TEXT,
            username TEXT,
            expiry_date DATETIME,
            expiry_notified INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Safely add new columns to equities table if they don't exist
    for col in ['volume', 'high', 'low']:
        try:
            cursor.execute(f'ALTER TABLE equities ADD COLUMN {col} REAL')
        except sqlite3.OperationalError:
            pass # Column already exists
            
    conn.commit()
    conn.close()

def save_equities(pre_market, post_market, live_price, volume=None, high=None, low=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO equities (pre_market, post_market, live_price, volume, high, low)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (pre_market, post_market, live_price, volume, high, low))
    conn.commit()
    conn.close()

def save_currency(rate):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO currencies (rate)
        VALUES (?)
    ''', (rate,))
    conn.commit()
    conn.close()

def save_ocr(rate, snapshot_path):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO ocr_data (rate, snapshot_path)
        VALUES (?, ?)
    ''', (rate, snapshot_path))
    conn.commit()
    conn.close()

def save_calculation(calculated_rate, ocr_rate, difference_percent):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO calculations (calculated_rate, ocr_rate, difference_percent)
        VALUES (?, ?, ?)
    ''', (calculated_rate, ocr_rate, difference_percent))
    conn.commit()
    conn.close()

def get_last_ocr_prices(n=10):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT rate FROM ocr_data
        ORDER BY created_at DESC
        LIMIT ?
    ''', (n,))
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]

def register_user(chat_id, platform, username, trial_days=7):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    expiry_date = (datetime.now() + timedelta(days=trial_days)).strftime("%Y-%m-%d %H:%M:%S")
    
    # Use REPLACE to handle re-registration (resetting trial)
    cursor.execute('''
        INSERT OR REPLACE INTO users (chat_id, platform, username, expiry_date, expiry_notified)
        VALUES (?, ?, ?, ?, 0)
    ''', (str(chat_id), platform, username, expiry_date))
    
    conn.commit()
    conn.close()
    return expiry_date

def get_active_subscribers():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        SELECT chat_id, platform FROM users
        WHERE expiry_date > ?
    ''', (now,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_expired_users_to_notify():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        SELECT chat_id, platform FROM users
        WHERE expiry_date <= ? AND expiry_notified = 0
    ''', (now,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def mark_user_notified(chat_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users SET expiry_notified = 1
        WHERE chat_id = ?
    ''', (str(chat_id),))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized.")
