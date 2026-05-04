import logging
from datetime import datetime
import zoneinfo

logger = logging.getLogger(__name__)

def get_ny_time() -> datetime:
    """Returns current time in New York timezone (EST/EDT)."""
    return datetime.now(zoneinfo.ZoneInfo("America/New_York"))

def get_astana_time() -> datetime:
    """Returns current time in Astana timezone (UTC+5)."""
    return datetime.now(zoneinfo.ZoneInfo("Asia/Almaty"))

def is_market_open() -> bool:
    """
    Checks if NASDAQ market is currently open.
    Regular trading hours: 09:30 - 16:00 New York time.
    Returns True if market is open, False otherwise.
    """
    ny_now = get_ny_time()
    
    # Weekends are closed
    if ny_now.weekday() >= 5:
        return False
        
    hour = ny_now.hour
    minute = ny_now.minute
    
    # 09:30 to 16:00
    is_open = (hour == 9 and minute >= 30) or (10 <= hour < 16)
    
    if is_open:
        logger.debug(f"Market OPEN: {ny_now.strftime('%H:%M')} NY time")
    return is_open

def is_pre_market_period() -> bool:
    """
    Checks if we're in pre-market period.
    Pre-market hours: 04:00 - 09:30 New York time.
    Returns True if in pre-market, False otherwise.
    """
    ny_now = get_ny_time()
    
    # Weekends don't have pre-market
    if ny_now.weekday() >= 5:
        return False
        
    hour = ny_now.hour
    minute = ny_now.minute
    
    # 04:00 to 09:29
    is_pre = (4 <= hour < 9) or (hour == 9 and minute < 30)
    
    if is_pre:
        logger.debug(f"PRE-MARKET period: {ny_now.strftime('%H:%M')} NY time")
    return is_pre

def is_post_market_period() -> bool:
    """
    Checks if we're in post-market period.
    Post-market hours: 16:00 - 20:00 New York time.
    Also returns True on weekends or closed hours (20:00-04:00) 
    to use post-market prices as a fallback.
    """
    ny_now = get_ny_time()
    
    # Weekends use post-market (Friday's close/post)
    if ny_now.weekday() >= 5:
        return True
        
    hour = ny_now.hour
    
    # 16:00 until 04:00 next day
    is_post = (hour >= 16) or (hour < 4)
    
    if is_post:
        logger.debug(f"POST-MARKET/CLOSED period: {ny_now.strftime('%H:%M')} NY time")
    return is_post

def is_night_window() -> bool:
    """
    Returns True between 01:00 and 05:00 Astana time (UTC+5),
    inclusive of 01:xx, exclusive of 05:00, any day of the week.
    """
    astana_now = get_astana_time()
    return 1 <= astana_now.hour < 5
