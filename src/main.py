import asyncio
import os
import logging
import inspect
import cv2
import zoneinfo
from datetime import datetime, timedelta

from src.core.config import Config
from src.database.repository import DatabaseRepository
from src.services.scraper import ScraperService
from src.services.vision_service import VisionService
from src.services.notifier import TelegramNotifier
from src.services.business_logger import BusinessLogger

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize services
vision_service = VisionService()

# ---------------------------------------------------------------------------
# Night-window state (01:00 – 05:00 Astana time, UTC+5)
# Baseline OCR price captured at 01:00, reset every morning.
# ---------------------------------------------------------------------------
_night_baseline_price: float | None = None
_night_baseline_date: object | None = None   # date on which baseline was set
_night_signal_sent_today: bool = False        # rate-limit: one BUY signal per night
_night_prev_ocr_price: float | None = None    # for volatility check (current vs previous)
_last_ocr_error_notify_time: datetime | None = None
_last_task_error_notify_time: datetime | None = None

def get_ny_time():
    """Returns current time in New York timezone (EST/EDT)."""
    return datetime.now(zoneinfo.ZoneInfo("America/New_York"))

def get_astana_time():
    """Returns current time in Astana timezone (UTC+5)."""
    return datetime.now(zoneinfo.ZoneInfo("Asia/Almaty"))

def is_market_open():
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

def is_pre_market_period():
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

def is_post_market_period():
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

# ---------------------------------------------------------------------------
# Night-window helpers (01:00 – 05:00 Astana time, UTC+5)
# ---------------------------------------------------------------------------
def _is_night_window() -> bool:
    """
    Returns True between 01:00 and 05:00 Astana time (UTC+5),
    inclusive of 01:xx, exclusive of 05:00, any day of the week.
    """
    astana_now = get_astana_time()
    return 1 <= astana_now.hour < 5


def _should_capture_night_baseline() -> bool:
    """
    Returns True during the first minute of the 01:00 hour (01:00–01:00:59)
    Astana time, and only if we haven't captured a baseline for today yet.
    """
    global _night_baseline_date
    astana_now = get_astana_time()
    today = astana_now.date()
    return astana_now.hour == 1 and astana_now.minute == 0 and _night_baseline_date != today


def _try_capture_night_baseline(ocr_price: float | None) -> None:
    """If conditions are met, store the current OCR price as the night baseline."""
    global _night_baseline_price, _night_baseline_date, _night_signal_sent_today
    if ocr_price is None:
        return
    if _should_capture_night_baseline():
        astana_now = get_astana_time()
        _night_baseline_price = ocr_price
        _night_baseline_date = astana_now.date()
        _night_signal_sent_today = False
        logger.info(
            f"🌙 Night baseline captured at {astana_now.strftime('%H:%M')} Astana: "
            f"baseline OCR price = {ocr_price:.4f}"
        )


def _check_night_window_signal(ocr_price: float | None) -> None:
    """
    During 01:00–05:00 Astana time (UTC+5), compare real-time OCR price to
    the night baseline.  If the difference exceeds 1%, send a BUY signal to
    TG_CHAT_ID_BUY (once per night).
    """
    global _night_signal_sent_today, _night_baseline_price, _night_baseline_date
    
    if not _is_night_window():
        return
        
    # If baseline is missing in memory, try to recover it from the database
    if _night_baseline_price is None:
        db_baseline = DatabaseRepository.get_night_baseline_from_db()
        if db_baseline:
            _night_baseline_price = db_baseline
            # Mark it as captured for today so we don't try to capture it again at 01:00
            _night_baseline_date = get_astana_time().date()
            logger.info(f"🌙 Night baseline recovered from DB: {db_baseline:.4f}")
        else:
            return # Still no baseline available

    if ocr_price is None:
        return
        
    if _night_signal_sent_today:
        return

    diff_pct = abs(ocr_price - _night_baseline_price) / _night_baseline_price * 100
    logger.info(
        f"🌙 Night check — baseline: {_night_baseline_price:.4f}, "
        f"current OCR: {ocr_price:.4f}, diff: {diff_pct:.2f}%"
    )

    if diff_pct >= 1.0:
        astana_now = get_astana_time()
        direction = "вверх 📈" if ocr_price > _night_baseline_price else "вниз 📉"
        
        history = DatabaseRepository.get_last_ocr_prices(10)
        history_text = "\n".join([f"{i+1}. {p:.4f}" for i, p in enumerate(history)])
        
        msg = (
            "🌙 <b>Ночной сигнал (КУПИТЬ)</b> 🌙\n\n"
            "Цена на Freedom значительно изменилась в ночное время.\n\n"
            f"🕐 Базовая цена (01:00 Астана): <code>{_night_baseline_price:.4f}</code>\n"
            f"📷 Текущая цена ({astana_now.strftime('%H:%M')} Астана): <code>{ocr_price:.4f}</code>\n"
            f"⚠️ Разница: <b>{diff_pct:.2f}%</b> {direction}\n\n"
            f"<blockquote expandable><b>Extraction History:</b>\n{history_text}</blockquote>"
        )
        logger.info(
            f"🌙 Night window BUY signal triggered: diff={diff_pct:.2f}%, "
            f"sending to TG_CHAT_ID_BUY"
        )
        # The user requested to stop sending signals during the night window 
        # except for _check_night_volatility_signal. 
        # So we skip sending the 'Night baseline' signal.
        # TelegramNotifier.send_alert(msg, Config.TG_CHAT_ID_BUY)
        logger.info(
            f"🌙 Night window BUY signal suppressed (only volatility allowed): diff={diff_pct:.2f}%"
        )
        _night_signal_sent_today = True


def _check_night_volatility_signal(ocr_price: float | None) -> None:
    """
    During 01:00–05:00 Astana time, compare real-time OCR price to the 
    PREVIOUS cycle's OCR price. If diff > 0.8%, notify all subscribers.
    """
    global _night_prev_ocr_price
    
    # If not in window or price missing, just update the reference and exit
    if not _is_night_window() or ocr_price is None or _night_prev_ocr_price is None:
        _night_prev_ocr_price = ocr_price
        return

    diff_pct = abs(ocr_price - _night_prev_ocr_price) / _night_prev_ocr_price * 100
    
    if diff_pct >= 0.8:
        astana_now = get_astana_time()
        direction = "вверх 🚀" if ocr_price > _night_prev_ocr_price else "вниз 📉"
        
        history = DatabaseRepository.get_last_ocr_prices(10)
        history_text = "\n".join([f"{i+1}. {p:.4f}" for i, p in enumerate(history)])
        
        msg = (
            "⚡️ <b>Ночной скачок волатильности!</b> ⚡️\n\n"
            "Обнаружено резкое изменение цены между замерами.\n\n"
            f"⬅️ Было: <code>{_night_prev_ocr_price:.4f}</code>\n"
            f"➡️ Стало: <code>{ocr_price:.4f}</code>\n"
            f"⚠️ Изменение: <b>{diff_pct:.2f}%</b> {direction}\n"
            f"⏰ Время: {astana_now.strftime('%H:%M:%S')} Астана\n\n"
            f"<blockquote expandable><b>Extraction History:</b>\n{history_text}</blockquote>"
        )
        # Check if this volatility signal is a duplicate
        is_duplicate = DatabaseRepository.is_signal_duplicate("NIGHT_VOLATILITY", ocr_price, _night_prev_ocr_price)
        DatabaseRepository.save_signal("NIGHT_VOLATILITY", ocr_price, _night_prev_ocr_price, diff_pct)

        if not is_duplicate:
            logger.info(f"🌙 Night volatility detected: {diff_pct:.2f}%. Notifying subscribers...")
            for sub_chat_id, platform in DatabaseRepository.get_active_subscribers():
                if platform == 'telegram':
                    TelegramNotifier.send_alert(msg, sub_chat_id)
        else:
            logger.info(f"🌙 Night volatility detected: {diff_pct:.2f}%, but it is a DUPLICATE. Skipping notification.")

    # Update previous price for next cycle
    _night_prev_ocr_price = ocr_price


def check_subscriptions_and_notify():
    """Checks for expired users and sends a one-time notification."""
    expired_users = DatabaseRepository.get_expired_users_to_notify()
    for chat_id, platform in expired_users:
        if platform == 'telegram':
            msg = (
                "⚠️ <b>Ваша подписка истекла!</b>\n\n"
                "Вы больше не будете получать сигналы. Для продления подписки обратитесь к администратору."
            )
            TelegramNotifier.send_alert(msg, chat_id)
            DatabaseRepository.mark_user_notified(chat_id)
            logger.info(f"Notification sent to expired user {chat_id}.")

async def monitoring_cycle():
    logger.info("--- Starting Monitoring Cycle ---")
    
    # 1. Scrape FRHC
    frhc_data = await ScraperService.fetch_frhc_data()
    if frhc_data:
        DatabaseRepository.save_equities(
            frhc_data.get('pre_market'), 
            frhc_data.get('post_market'), 
            frhc_data.get('live_price'),
            frhc_data.get('volume'),
            frhc_data.get('high'),
            frhc_data.get('low')
        )
    else:
        logger.error("Failed to scrape FRHC data.")
    
    # 2. Scrape USD/KZT
    usd_kzt = await ScraperService.fetch_usd_kzt()
    if usd_kzt:
        DatabaseRepository.save_currency(usd_kzt)
    else:
        logger.error("Failed to scrape USD/KZT data.")
    
    # 3. Camera & OCR
    snapshot_path = vision_service.capture_snapshot()
    ocr_price = None
    if snapshot_path:
        img = cv2.imread(snapshot_path)
        if img is not None:
            cropped = img[1972:2032, 291:470]
            if cropped.size > 0:
                # Save cropped image for debugging in identical location
                cropped_path = snapshot_path.replace(".png", "_cropped.png").replace(".jpg", "_cropped.jpg")
                cv2.imwrite(cropped_path, cropped)
                logger.info(f"Cropped image saved to: {cropped_path}")
                
                ocr_price = vision_service.extract_freedom_price(cropped)
                if ocr_price:
                    logger.info(f"OCR Extracted Price: {ocr_price}")
                    DatabaseRepository.save_ocr(ocr_price, snapshot_path)
                else:
                    logger.warning("OCR failed to extract logic or price was out of bounds.")
                    
                    # Notify once every 30 minutes to prevent spam
                    global _last_ocr_error_notify_time
                    now = datetime.now()
                    if _last_ocr_error_notify_time is None or (now - _last_ocr_error_notify_time) > timedelta(minutes=30):
                        msg = "⚠️ <b>OCR Warning:</b> Failed to extract price or logic. Check screen orientation/resolution."
                        TelegramNotifier.send_alert(msg, Config.TG_CHAT_ID_ERROR)
                        _last_ocr_error_notify_time = now
            else:
                logger.error("Cropped image is empty. Check screen resolution/rotation.")
        else:
            logger.error("Snapshot failed to load via OpenCV.")
    else:
        logger.error("Camera capture failed.")

    # 4. Math and Comparisons
    if frhc_data and usd_kzt:
        live = frhc_data.get('live_price')
        pre = frhc_data.get('pre_market')
        post = frhc_data.get('post_market')
        
        logger.info(f"Available prices - Live: {live}, Pre: {pre}, Post: {post}")
        logger.info(f"Market status - Open: {is_market_open()}, Pre: {is_pre_market_period()}, Post: {is_post_market_period()}")
        
        equities_price = None
        price_source = "N/A"
        
        # MARKET OPEN (09:30 - 16:00): Use live price
        if is_market_open():
            # Clear session caches when market opens as they are now stale
            DatabaseRepository.clear_pre_market_cache()
            DatabaseRepository.clear_post_market_cache()
            equities_price = live
            price_source = "Live"
            logger.info(f"✓ MARKET OPEN: Using LIVE price: {live}")
        
        # PRE-MARKET PERIOD (04:00 - 09:30): Use pre-market if available, cache it
        elif is_pre_market_period():
            if pre is not None:
                DatabaseRepository.cache_pre_market_price(pre)
                equities_price = pre
                price_source = "Pre"
                logger.info(f"✓ PRE-MARKET PERIOD: Using fresh PRE-MARKET price: {pre}")
            else:
                # No fresh pre-market, try cached version
                cached_pre = DatabaseRepository.get_cached_pre_market_price()
                if cached_pre is not None:
                    equities_price = cached_pre
                    price_source = "Pre (Cached)"
                    logger.info(f"✓ PRE-MARKET PERIOD: Using CACHED PRE-MARKET price: {cached_pre}")
                else:
                    # No pre-market, use post-market as fallback instead of live
                    if post is not None:
                        DatabaseRepository.cache_post_market_price(post)
                        equities_price = post
                        price_source = "Post (Pre Fallback)"
                        logger.info(f"✓ PRE-MARKET PERIOD: No pre-market, using fresh POST-MARKET price: {post}")
                    else:
                        cached_post = DatabaseRepository.get_cached_post_market_price()
                        if cached_post is not None:
                            equities_price = cached_post
                            price_source = "Post (Cached - Pre Fallback)"
                            logger.info(f"✓ PRE-MARKET PERIOD: No pre-market, using CACHED POST-MARKET price: {cached_post}")
                        else:
                            # Final fallback to live
                            equities_price = live
                            price_source = "Live (Pre Fallback)"
                            logger.warning(f"⚠️ PRE-MARKET PERIOD: No cached pre or post, using LIVE: {live}")
        
        # POST-MARKET PERIOD (16:00 - 04:00): Use post-market if available, cache it
        elif is_post_market_period():
            # Clear pre-market cache when entering post-market/closed
            DatabaseRepository.clear_pre_market_cache()
            if post is not None:
                DatabaseRepository.cache_post_market_price(post)
                equities_price = post
                price_source = "Post"
                logger.info(f"✓ POST-MARKET PERIOD: Using fresh POST-MARKET price: {post}")
            else:
                # No fresh post-market, try cached version
                cached_post = DatabaseRepository.get_cached_post_market_price()
                if cached_post is not None:
                    equities_price = cached_post
                    price_source = "Post (Cached)"
                    logger.info(f"✓ POST-MARKET PERIOD: Using CACHED POST-MARKET price: {cached_post}")
                else:
                    # No cached post, use live as fallback
                    equities_price = live
                    price_source = "Live (Post Fallback)"
                    logger.warning(f"⚠️ POST-MARKET PERIOD: No cached post-market, using LIVE: {live}")
        
        if equities_price is not None:
            calculated_rate = (usd_kzt * equities_price) / 10000
            diff_pct = None
            if ocr_price is not None:
                diff_pct = abs(ocr_price - calculated_rate) / calculated_rate * 100
                logger.info(f"Calculated: {calculated_rate:.4f}, OCR: {ocr_price:.4f}, Diff: {diff_pct:.2f}%")
            
            DatabaseRepository.save_calculation(calculated_rate, ocr_price or 0.0, diff_pct or 0.0)
            
            if diff_pct is not None and diff_pct >= Config.DIFFERENCE_THRESHOLD_PERCENT:
                logger.info(f"Difference ({diff_pct:.2f}%) exceeds threshold, sending alerts...")
                
                if ocr_price < calculated_rate:
                    signal = "🟢 <b>ЗЕЛЕНЫЙ СИГНАЛ (КУПИТЬ)</b>"
                    signal_type = "GREEN"
                    target_chat_id = Config.TG_CHAT_ID_BUY
                elif ocr_price > calculated_rate:
                    signal = "🔴 <b>КРАСНЫЙ СИГНАЛ (ПРОДАТЬ)</b>"
                    signal_type = "RED"
                    target_chat_id = Config.TG_CHAT_ID_SELL
                else:
                    signal = "⚪ <b>НЕЙТРАЛЬНО</b>"
                    signal_type = "NEUTRAL"
                    target_chat_id = Config.TG_CHAT_ID_BUY

                # Check if this signal is a duplicate of the last one
                is_duplicate = DatabaseRepository.is_signal_duplicate(signal_type, ocr_price, calculated_rate)
                
                # Save signal to history
                DatabaseRepository.save_signal(signal_type, ocr_price, calculated_rate, diff_pct)

                history = DatabaseRepository.get_last_ocr_prices(10)
                history_text = "\n".join([f"{i+1}. {p:.4f}" for i, p in enumerate(history)])

                msg = (
                    f"{signal}\n\n"
                    "🚨 <b>Freedom Arbitrage Alert</b> 🚨\n\n"
                    f"📈 FRHC ({price_source}): <code>{equities_price:.2f}</code> $\n"
                    f"💱 USD/KZT (Yahoo): <code>{usd_kzt:.2f}</code> ₸\n\n"
                    f"🧮 Calculated Rate: <code>{calculated_rate:.4f}</code>\n"
                    f"📷 Extracted Rate: <code>{ocr_price:.4f}</code>\n"
                    f"⚠️ Difference: <b>{diff_pct:.2f}%</b>\n\n"
                    f"<blockquote expandable><b>Extraction History:</b>\n{history_text}</blockquote>"
                )
                
                # Skip sending if it's the night window (except for volatility signals)
                if _is_night_window():
                    logger.info(f"Signal suppressed: night window active (01:00-05:00 Astana).")
                elif is_duplicate:
                    logger.info(f"Signal suppressed: duplicate signal (Type: {signal_type}, OCR: {ocr_price}).")
                else:
                    logger.info(f"Signal type: {signal_type}, Sending alert...")
                    # Send to main target channel/chat
                    TelegramNotifier.send_alert(msg, target_chat_id)
                    
                    # Send to all active subscribers
                    for sub_chat_id, platform in DatabaseRepository.get_active_subscribers():
                        if platform == 'telegram':
                            TelegramNotifier.send_alert(msg, sub_chat_id)

        # Log cycle data to the daily file
        BusinessLogger.log_cycle(
            snapshot_price=ocr_price,
            usd_kzt=usd_kzt,
            live=live,
            pre=pre,
            post=post,
            calculated_rate=calculated_rate if equities_price is not None else None,
            difference_pct=diff_pct if 'diff_pct' in locals() else None
        )

    # ---------------------------------------------------------------------------
    # Night-window logic (01:00 – 05:00 Astana time)
    # ---------------------------------------------------------------------------
    _try_capture_night_baseline(ocr_price)
    _check_night_window_signal(ocr_price)
    _check_night_volatility_signal(ocr_price)

    if not _is_night_window():
        check_subscriptions_and_notify()

async def post_market_cycle():
    ny_now = get_ny_time()
    # Post-market runs from 16:00 to 20:00 NY Time
    if ny_now.weekday() >= 5 or ny_now.hour < 16 or ny_now.hour >= 20:
        return

    logger.info("--- Starting Post-Market Monitoring ---")
    frhc_data = await ScraperService.fetch_frhc_data()
    if not frhc_data:
        return

    close = frhc_data.get('closing_price')
    post = frhc_data.get('post_market')

    if close is not None and post is not None:
        diff_pct = abs(post - close) / close * 100
        if diff_pct >= Config.DIFFERENCE_THRESHOLD_PERCENT:
            logger.info("Post-market difference exceeds threshold, sending alert...")
            
            signal_type = "POST_MARKET"
            is_duplicate = DatabaseRepository.is_signal_duplicate(signal_type, post, close)
            DatabaseRepository.save_signal(signal_type, post, close, diff_pct)
            
            history = DatabaseRepository.get_last_ocr_prices(10)
            history_text = "\n".join([f"{i+1}. {p:.4f}" for i, p in enumerate(history)])

            msg = (
                "🌙 <b>Post-Market Price Alert</b> 🌙\n\n"
                f"📈 FRHC Closing: <code>{close:.2f}</code> $\n"
                f"🌒 FRHC Post-Market: <code>{post:.2f}</code> $\n"
                f"⚠️ Difference: <b>{diff_pct:.2f}%</b>\n\n"
                f"<blockquote expandable><b>Extraction History:</b>\n{history_text}</blockquote>"
            )
            
            # Skip sending if it's the night window or a duplicate
            if _is_night_window():
                logger.info(f"Post-market signal suppressed: night window active.")
            elif is_duplicate:
                logger.info(f"Post-market signal suppressed: duplicate signal.")
            else:
                logger.info(f"Post-market signal, Sending alert...")
                TelegramNotifier.send_alert(msg, Config.TG_CHAT_ID_POST_MARKET)
                for sub_chat_id, platform in DatabaseRepository.get_active_subscribers():
                    if platform == 'telegram':
                        TelegramNotifier.send_alert(msg, sub_chat_id)
                    
    check_subscriptions_and_notify()

async def cleanup_snapshots():
    logger.info("--- Cleaning up snapshots folder ---")
    if os.path.exists(Config.SNAPSHOTS_DIR):
        count = 0
        for filename in os.listdir(Config.SNAPSHOTS_DIR):
            filepath = os.path.join(Config.SNAPSHOTS_DIR, filename)
            try:
                if os.path.isfile(filepath):
                    os.remove(filepath)
                    count += 1
            except Exception as e:
                logger.error(f"Error deleting file {filepath}: {e}")
        logger.info(f"Deleted {count} files from snapshots.")
        
    # Cleanup old logs (weekly retention)
    deleted_logs = BusinessLogger.cleanup_old_logs()
    if deleted_logs > 0:
        logger.info(f"Cleaned up {deleted_logs} obsolete weekly logs.")

async def schedule_task(interval_seconds, task_func):
    """Run a task continuously every N seconds."""
    while True:
        try:
            if inspect.iscoroutinefunction(task_func):
                await task_func()
            else:
                task_func()
        except Exception as e:
            logger.exception(f"Error in scheduled task {task_func.__name__}: {e}")
            
            # Notify once every 30 minutes to prevent spam
            global _last_task_error_notify_time
            now = datetime.now()
            if _last_task_error_notify_time is None or (now - _last_task_error_notify_time) > timedelta(minutes=30):
                error_msg = f"❌ <b>Error in task {task_func.__name__}:</b>\n\n<code>{str(e)}</code>"
                TelegramNotifier.send_alert(error_msg, Config.TG_CHAT_ID_ERROR)
                _last_task_error_notify_time = now
        await asyncio.sleep(interval_seconds)

async def main():
    Config.validate()
    DatabaseRepository.init_db()
    logger.info("Freedom Finance Monitoring App Started.")
    
    # Schedule tasks concurrently
    task1 = asyncio.create_task(schedule_task(20, monitoring_cycle))
    task2 = asyncio.create_task(schedule_task(30, post_market_cycle))
    task3 = asyncio.create_task(schedule_task(3600, cleanup_snapshots))
    
    await asyncio.gather(task1, task2, task3)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Monitoring App Stopped.")
    except Exception as e:
        error_msg = f"💀 <b>FATAL ERROR: Application Crashed</b>\n\n<code>{str(e)}</code>"
        logger.exception(f"Fatal error in main entry point: {e}")
        TelegramNotifier.send_alert(error_msg, Config.TG_CHAT_ID_ERROR)
