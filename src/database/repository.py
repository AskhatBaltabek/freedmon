import sqlite3
import os
import logging
from datetime import datetime, timedelta
from contextlib import contextmanager
from typing import List, Tuple, Optional

# Import the centralized DB path
from src.core.config import Config

logger = logging.getLogger(__name__)

@contextmanager
def get_db_connection():
    """Provides a safe, auto-closing database connection."""
    conn = sqlite3.connect(Config.DB_PATH)
    try:
        yield conn
    finally:
        conn.close()

class DatabaseRepository:
    """
    Encapsulates all SQLite database queries using safe context managers.
    Handles persistence of market data, OCR snapshots, calculated signals, 
    duplicate detection mechanisms, market period caching, and user subscriptions.
    """
    
    @staticmethod
    def init_db():
        """Initializes tables if they do not exist."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Equities table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS equities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pre_market REAL,
                    post_market REAL,
                    live_price REAL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    volume REAL,
                    high REAL,
                    low REAL
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
            
            # Signals history table (для отслеживания повторяющихся сигналов)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS signals_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    signal_type TEXT,
                    ocr_rate REAL,
                    calculated_rate REAL,
                    difference_percent REAL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Post-market price cache (для закрепления постмаркет цены на период отсутствия)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS post_market_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    price REAL,
                    captured_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Pre-market price cache (для закрепления премаркет цены до открытия рынка)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pre_market_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    price REAL,
                    captured_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Safely add columns (legacy support)
            for col in ['volume', 'high', 'low']:
                try:
                    cursor.execute(f'ALTER TABLE equities ADD COLUMN {col} REAL')
                except sqlite3.OperationalError:
                    pass # Column already exists
                    
            conn.commit()

    @staticmethod
    def save_equities(pre_market: Optional[float], post_market: Optional[float], 
                      live_price: Optional[float], volume: Optional[float] = None, 
                      high: Optional[float] = None, low: Optional[float] = None):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO equities (pre_market, post_market, live_price, volume, high, low)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (pre_market, post_market, live_price, volume, high, low))
            conn.commit()

    @staticmethod
    def save_currency(rate: float):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO currencies (rate) VALUES (?)', (rate,))
            conn.commit()

    @staticmethod
    def save_ocr(rate: float, snapshot_path: str):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO ocr_data (rate, snapshot_path) VALUES (?, ?)', (rate, snapshot_path))
            conn.commit()

    @staticmethod
    def save_calculation(calculated_rate: float, ocr_rate: float, difference_percent: float):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO calculations (calculated_rate, ocr_rate, difference_percent)
                VALUES (?, ?, ?)
            ''', (calculated_rate, ocr_rate, difference_percent))
            conn.commit()

    @staticmethod
    def get_last_ocr_prices(n: int = 10) -> List[float]:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT rate FROM ocr_data ORDER BY created_at DESC LIMIT ?', (n,))
            rows = cursor.fetchall()
            return [row[0] for row in rows]

    @staticmethod
    def get_night_baseline_from_db() -> Optional[float]:
        """
        Fetches the first OCR price recorded after 01:00 Astana time (20:00 UTC).
        Used as a recovery baseline for night-window logic.
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # 01:00 Astana is 20:00 UTC.
            # If it's currently 02:00 AM Astana (Wed), 20:00 UTC was Tue evening.
            # If it's currently 10:00 PM Astana (Wed), 20:00 UTC was Wed evening.
            now_utc = datetime.utcnow()
            today_20_utc = now_utc.replace(hour=20, minute=0, second=0, microsecond=0)
            
            if now_utc < today_20_utc:
                # 20:00 UTC hasn't happened today yet, so the relevant 01:00 Astana
                # belongs to the start of "today" in Astana, which was 20:00 UTC yesterday.
                target_time = today_20_utc - timedelta(days=1)
            else:
                # 20:00 UTC already happened today, so we are looking for signals 
                # after this time (which will be 01:00 Astana tomorrow).
                target_time = today_20_utc
            
            target_str = target_time.strftime("%Y-%m-%d %H:%M:%S")
            
            cursor.execute('''
                SELECT rate FROM ocr_data 
                WHERE created_at >= ? 
                ORDER BY created_at ASC LIMIT 1
            ''', (target_str,))
            
            result = cursor.fetchone()
            if result:
                return result[0]
            return None

    @staticmethod
    def register_user(chat_id: str, platform: str, username: str, trial_days: int = 7) -> str:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            expiry_date = (datetime.now() + timedelta(days=trial_days)).strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute('''
                INSERT OR REPLACE INTO users (chat_id, platform, username, expiry_date, expiry_notified)
                VALUES (?, ?, ?, ?, 0)
            ''', (str(chat_id), platform, username, expiry_date))
            conn.commit()
            return expiry_date

    @staticmethod
    def get_active_subscribers() -> List[Tuple[str, str]]:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute('SELECT chat_id, platform FROM users WHERE expiry_date > ?', (now,))
            return cursor.fetchall()

    @staticmethod
    def get_expired_users_to_notify() -> List[Tuple[str, str]]:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute('SELECT chat_id, platform FROM users WHERE expiry_date <= ? AND expiry_notified = 0', (now,))
            return cursor.fetchall()

    @staticmethod
    def mark_user_notified(chat_id: str):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET expiry_notified = 1 WHERE chat_id = ?', (str(chat_id),))
            conn.commit()

    @staticmethod
    def save_signal(signal_type: str, ocr_rate: float, calculated_rate: float, difference_percent: float):
        """Saves signal info to history for duplicate detection."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO signals_history (signal_type, ocr_rate, calculated_rate, difference_percent)
                VALUES (?, ?, ?, ?)
            ''', (signal_type, ocr_rate, calculated_rate, difference_percent))
            conn.commit()

    @staticmethod
    def get_last_signal(signal_type: str) -> Optional[Tuple[float, float, float]]:
        """Gets last signal of given type. Returns (ocr_rate, calculated_rate, difference_percent) or None."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT ocr_rate, calculated_rate, difference_percent 
                FROM signals_history 
                WHERE signal_type = ?
                ORDER BY created_at DESC 
                LIMIT 1
            ''', (signal_type,))
            result = cursor.fetchone()
            return result if result else None

    @staticmethod
    def is_signal_duplicate(signal_type: str, ocr_rate: float, calculated_rate: float, tolerance: float = 0.01) -> bool:
        """
        Checks if the current signal is duplicate of the last one.
        Uses tolerance to account for minor fluctuations.
        tolerance: difference in rates to consider signals duplicate (default 0.01 = 1 cent)
        """
        last_signal = DatabaseRepository.get_last_signal(signal_type)
        if not last_signal:
            return False
        
        last_ocr, last_calculated, _ = last_signal
        # Compare if both rates are within tolerance
        ocr_diff = abs(ocr_rate - last_ocr)
        calc_diff = abs(calculated_rate - last_calculated)
        
        return ocr_diff <= tolerance and calc_diff <= tolerance

    @staticmethod
    def cache_post_market_price(price: float):
        """Saves post-market price to cache for use during unavailable periods."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Delete old entries, keep only the latest
            cursor.execute('DELETE FROM post_market_cache WHERE id NOT IN (SELECT id FROM post_market_cache ORDER BY captured_at DESC LIMIT 1)')
            cursor.execute('INSERT INTO post_market_cache (price) VALUES (?)', (price,))
            conn.commit()
            logger.info(f"Post-market price cached: {price}")

    @staticmethod
    def get_cached_post_market_price() -> Optional[float]:
        """Gets the last cached post-market price, only if it's not older than 24 hours."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Only get prices captured within the last 24 hours
            cursor.execute('''
                SELECT price, captured_at FROM post_market_cache 
                WHERE captured_at > datetime('now', '-24 hours')
                ORDER BY captured_at DESC LIMIT 1
            ''')
            result = cursor.fetchone()
            if result:
                return result[0]
            
            # Check if there's any record at all to log expiration
            cursor.execute('SELECT captured_at FROM post_market_cache ORDER BY captured_at DESC LIMIT 1')
            any_res = cursor.fetchone()
            if any_res:
                logger.warning(f"Cached post-market price expired (Captured at: {any_res[0]})")
            return None

    @staticmethod
    def clear_post_market_cache():
        """Clears the post-market price cache."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM post_market_cache')
            conn.commit()
            logger.info("Post-market cache cleared")

    @staticmethod
    def cache_pre_market_price(price: float):
        """Saves pre-market price to cache for use during unavailable periods (before market open)."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Delete old entries, keep only the latest
            cursor.execute('DELETE FROM pre_market_cache WHERE id NOT IN (SELECT id FROM pre_market_cache ORDER BY captured_at DESC LIMIT 1)')
            cursor.execute('INSERT INTO pre_market_cache (price) VALUES (?)', (price,))
            conn.commit()
            logger.info(f"Pre-market price cached: {price}")

    @staticmethod
    def get_cached_pre_market_price() -> Optional[float]:
        """Gets the last cached pre-market price, only if it's not older than 24 hours."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Only get prices captured within the last 24 hours
            cursor.execute('''
                SELECT price, captured_at FROM pre_market_cache 
                WHERE captured_at > datetime('now', '-24 hours')
                ORDER BY captured_at DESC LIMIT 1
            ''')
            result = cursor.fetchone()
            if result:
                return result[0]
            
            # Check if there's any record at all to log expiration
            cursor.execute('SELECT captured_at FROM pre_market_cache ORDER BY captured_at DESC LIMIT 1')
            any_res = cursor.fetchone()
            if any_res:
                logger.warning(f"Cached pre-market price expired (Captured at: {any_res[0]})")
            return None

    @staticmethod
    def clear_pre_market_cache():
        """Clears the pre-market price cache."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM pre_market_cache')
            conn.commit()
            logger.info("Pre-market cache cleared")
