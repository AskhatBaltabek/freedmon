import sqlite3
from datetime import datetime
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
    
    conn.commit()
    conn.close()

def save_equities(pre_market, post_market, live_price):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO equities (pre_market, post_market, live_price)
        VALUES (?, ?, ?)
    ''', (pre_market, post_market, live_price))
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

if __name__ == "__main__":
    init_db()
    print("Database initialized.")
