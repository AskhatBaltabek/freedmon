import asyncio
import os
import cv2
import logging
from datetime import datetime, timedelta

from src.core.config import Config
from src.database.repository import DatabaseRepository
from src.services.scraper import ScraperService
from src.services.vision_service import VisionService
from src.services.notifier import TelegramNotifier
from src.services.business_logger import BusinessLogger
from src.core.time_utils import get_ny_time, is_market_open, is_pre_market_period, is_post_market_period, is_night_window
from src.services.night_service import NightService

logger = logging.getLogger(__name__)

class MonitoringController:
    """Controller to manage the main loops of the application."""
    
    _last_ocr_error_notify_time: datetime | None = None
    
    def __init__(self):
        self.vision_service = VisionService()

    @classmethod
    def check_subscriptions_and_notify(cls):
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

    async def monitoring_cycle(self):
        """
        Executes the main monitoring workflow. This cycle runs periodically (e.g., every 20 seconds).
        
        The cycle performs the following steps:
        1. Scrapes the latest FRHC market prices (Live, Pre, Post).
        2. Scrapes the current USD/KZT exchange rate.
        3. Captures a screenshot from the Android device via ADB and extracts the Freedom Finance app price using OCR.
        4. Compares the OCR price against a calculated base rate ((FRHC * USD_KZT) / 10000).
        5. Sends Telegram alerts if the discrepancy exceeds the configured threshold, respecting market session logic and duplicate suppression.
        6. Processes Astana night-window specific logic (volatility signals, baseline capture).
        """
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
        snapshot_path = self.vision_service.capture_snapshot()
        ocr_price = None
        if snapshot_path:
            img = cv2.imread(snapshot_path)
            if img is not None:
                cropped = img[1972:2032, 291:470]
                if cropped.size > 0:
                    cropped_path = snapshot_path.replace(".png", "_cropped.png").replace(".jpg", "_cropped.jpg")
                    cv2.imwrite(cropped_path, cropped)
                    logger.info(f"Cropped image saved to: {cropped_path}")
                    
                    ocr_price = self.vision_service.extract_freedom_price(cropped)
                    if ocr_price:
                        logger.info(f"OCR Extracted Price: {ocr_price}")
                        DatabaseRepository.save_ocr(ocr_price, snapshot_path)
                    else:
                        logger.warning("OCR failed to extract logic or price was out of bounds.")
                        
                        now = datetime.now()
                        if self._last_ocr_error_notify_time is None or (now - self._last_ocr_error_notify_time) > timedelta(minutes=30):
                            msg = "⚠️ <b>OCR Warning:</b> Failed to extract price or logic. Check screen orientation/resolution."
                            TelegramNotifier.send_alert(msg, Config.TG_CHAT_ID_ERROR)
                            self.__class__._last_ocr_error_notify_time = now
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
            
            if is_market_open():
                DatabaseRepository.clear_pre_market_cache()
                DatabaseRepository.clear_post_market_cache()
                equities_price = live
                price_source = "Live"
                logger.info(f"✓ MARKET OPEN: Using LIVE price: {live}")
            
            elif is_pre_market_period():
                if pre is not None:
                    DatabaseRepository.cache_pre_market_price(pre)
                    equities_price = pre
                    price_source = "Pre"
                    logger.info(f"✓ PRE-MARKET PERIOD: Using fresh PRE-MARKET price: {pre}")
                else:
                    cached_pre = DatabaseRepository.get_cached_pre_market_price()
                    if cached_pre is not None:
                        equities_price = cached_pre
                        price_source = "Pre (Cached)"
                        logger.info(f"✓ PRE-MARKET PERIOD: Using CACHED PRE-MARKET price: {cached_pre}")
                    else:
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
                                equities_price = live
                                price_source = "Live (Pre Fallback)"
                                logger.warning(f"⚠️ PRE-MARKET PERIOD: No cached pre or post, using LIVE: {live}")
            
            elif is_post_market_period():
                DatabaseRepository.clear_pre_market_cache()
                if post is not None:
                    DatabaseRepository.cache_post_market_price(post)
                    equities_price = post
                    price_source = "Post"
                    logger.info(f"✓ POST-MARKET PERIOD: Using fresh POST-MARKET price: {post}")
                else:
                    cached_post = DatabaseRepository.get_cached_post_market_price()
                    if cached_post is not None:
                        equities_price = cached_post
                        price_source = "Post (Cached)"
                        logger.info(f"✓ POST-MARKET PERIOD: Using CACHED POST-MARKET price: {cached_post}")
                    else:
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

                    is_duplicate = DatabaseRepository.is_signal_duplicate(signal_type, ocr_price, calculated_rate)
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
                    
                    if is_night_window():
                        logger.info(f"Signal suppressed: night window active (01:00-05:00 Astana).")
                    elif is_duplicate:
                        logger.info(f"Signal suppressed: duplicate signal (Type: {signal_type}, OCR: {ocr_price}).")
                    else:
                        logger.info(f"Signal type: {signal_type}, Sending alert...")
                        TelegramNotifier.send_alert(msg, target_chat_id)
                        for sub_chat_id, platform in DatabaseRepository.get_active_subscribers():
                            if platform == 'telegram':
                                TelegramNotifier.send_alert(msg, sub_chat_id)

            BusinessLogger.log_cycle(
                snapshot_price=ocr_price,
                usd_kzt=usd_kzt,
                live=live,
                pre=pre,
                post=post,
                calculated_rate=calculated_rate if equities_price is not None else None,
                difference_pct=diff_pct if 'diff_pct' in locals() else None
            )

        # Night window logic
        NightService.try_capture_night_baseline(ocr_price)
        NightService.check_night_window_signal(ocr_price)
        NightService.check_night_volatility_signal(ocr_price)

        if not is_night_window():
            self.check_subscriptions_and_notify()

    async def post_market_cycle(self):
        """
        Executes the post-market monitoring workflow. This cycle runs periodically (e.g., every 30 seconds)
        but only actively executes between 16:00 and 20:00 New York time on weekdays.
        
        It compares the official Market Close price against the active Post-Market price.
        If the discrepancy exceeds the threshold, it alerts subscribers of post-market volatility.
        """
        ny_now = get_ny_time()
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
                
                if is_night_window():
                    logger.info(f"Post-market signal suppressed: night window active.")
                elif is_duplicate:
                    logger.info(f"Post-market signal suppressed: duplicate signal.")
                else:
                    logger.info(f"Post-market signal, Sending alert...")
                    TelegramNotifier.send_alert(msg, Config.TG_CHAT_ID_POST_MARKET)
                    for sub_chat_id, platform in DatabaseRepository.get_active_subscribers():
                        if platform == 'telegram':
                            TelegramNotifier.send_alert(msg, sub_chat_id)
                        
        self.check_subscriptions_and_notify()

    async def cleanup_snapshots(self):
        """
        Periodic cleanup task (e.g., runs hourly).
        Deletes old screenshot images from the snapshots directory and trims obsolete log files
        to prevent the server from running out of disk space.
        """
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
            
        deleted_logs = BusinessLogger.cleanup_old_logs()
        if deleted_logs > 0:
            logger.info(f"Cleaned up {deleted_logs} obsolete weekly logs.")
