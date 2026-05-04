import logging
from src.core.config import Config
from src.database.repository import DatabaseRepository
from src.services.notifier import TelegramNotifier
from src.core.time_utils import get_astana_time, is_night_window

logger = logging.getLogger(__name__)

class NightService:
    """
    Service to handle night-window specific logic for Astana Time (01:00-05:00 UTC+5).
    During this window, standard arbitrage signals are suppressed, and specific 'Night Baseline'
    and 'Volatility' tracking mechanics are activated to monitor unusual price movements.
    """
    
    _night_baseline_price: float | None = None
    _night_baseline_date: object | None = None   # date on which baseline was set
    _night_signal_sent_today: bool = False       # rate-limit: one BUY signal per night
    _night_prev_ocr_price: float | None = None   # for volatility check (current vs previous)
    
    @classmethod
    def should_capture_night_baseline(cls) -> bool:
        """
        Returns True during the first minute of the 01:00 hour (01:00–01:00:59)
        Astana time, and only if we haven't captured a baseline for today yet.
        """
        astana_now = get_astana_time()
        today = astana_now.date()
        return astana_now.hour == 1 and astana_now.minute == 0 and cls._night_baseline_date != today

    @classmethod
    def try_capture_night_baseline(cls, ocr_price: float | None) -> None:
        """
        Attempts to store the current OCR price as the night baseline.
        
        This only occurs once per night, strictly during the first minute of the 01:00 hour.
        The captured baseline is later used to measure overall nightly drift.
        
        Args:
            ocr_price (float | None): The current price extracted via OCR.
        """
        if ocr_price is None:
            return
        if cls.should_capture_night_baseline():
            astana_now = get_astana_time()
            cls._night_baseline_price = ocr_price
            cls._night_baseline_date = astana_now.date()
            cls._night_signal_sent_today = False
            logger.info(
                f"🌙 Night baseline captured at {astana_now.strftime('%H:%M')} Astana: "
                f"baseline OCR price = {ocr_price:.4f}"
            )

    @classmethod
    def check_night_window_signal(cls, ocr_price: float | None) -> None:
        """
        Monitors the real-time OCR price against the captured night baseline (01:00 price).
        
        If the price drifts by more than 1% from the baseline, a signal is logged. 
        Note: Currently, these signals are suppressed from being sent to Telegram 
        to avoid spam during inactive market hours, as requested by the business rules.
        
        Args:
            ocr_price (float | None): The current price extracted via OCR.
        """
        if not is_night_window():
            return
            
        # If baseline is missing in memory, try to recover it from the database
        if cls._night_baseline_price is None:
            db_baseline = DatabaseRepository.get_night_baseline_from_db()
            if db_baseline:
                cls._night_baseline_price = db_baseline
                cls._night_baseline_date = get_astana_time().date()
                logger.info(f"🌙 Night baseline recovered from DB: {db_baseline:.4f}")
            else:
                return # Still no baseline available

        if ocr_price is None:
            return
            
        if cls._night_signal_sent_today:
            return

        diff_pct = abs(ocr_price - cls._night_baseline_price) / cls._night_baseline_price * 100
        logger.info(
            f"🌙 Night check — baseline: {cls._night_baseline_price:.4f}, "
            f"current OCR: {ocr_price:.4f}, diff: {diff_pct:.2f}%"
        )

        if diff_pct >= 1.0:
            astana_now = get_astana_time()
            direction = "вверх 📈" if ocr_price > cls._night_baseline_price else "вниз 📉"
            
            history = DatabaseRepository.get_last_ocr_prices(10)
            history_text = "\n".join([f"{i+1}. {p:.4f}" for i, p in enumerate(history)])
            
            msg = (
                "🌙 <b>Ночной сигнал (КУПИТЬ)</b> 🌙\n\n"
                "Цена на Freedom значительно изменилась в ночное время.\n\n"
                f"🕐 Базовая цена (01:00 Астана): <code>{cls._night_baseline_price:.4f}</code>\n"
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
            logger.info(
                f"🌙 Night window BUY signal suppressed (only volatility allowed): diff={diff_pct:.2f}%"
            )
            cls._night_signal_sent_today = True

    @classmethod
    def check_night_volatility_signal(cls, ocr_price: float | None) -> None:
        """
        Monitors short-term price volatility exclusively during the Astana night window (01:00-05:00).
        
        It compares the current OCR price against the OCR price from the *previous* cycle 
        (roughly 20 seconds ago). If the difference exceeds 0.8%, it instantly alerts all 
        subscribers of a "Volatility Spike", ensuring users don't miss sudden night-time movements.
        
        Args:
            ocr_price (float | None): The current price extracted via OCR.
        """
        # If not in window or price missing, just update the reference and exit
        if not is_night_window() or ocr_price is None or cls._night_prev_ocr_price is None:
            if ocr_price is not None:
                cls._night_prev_ocr_price = ocr_price
            return

        diff_pct = abs(ocr_price - cls._night_prev_ocr_price) / cls._night_prev_ocr_price * 100
        
        if diff_pct >= 0.8:
            astana_now = get_astana_time()
            direction = "вверх 🚀" if ocr_price > cls._night_prev_ocr_price else "вниз 📉"
            
            history = DatabaseRepository.get_last_ocr_prices(10)
            history_text = "\n".join([f"{i+1}. {p:.4f}" for i, p in enumerate(history)])
            
            msg = (
                "⚡️ <b>Ночной скачок волатильности!</b> ⚡️\n\n"
                "Обнаружено резкое изменение цены между замерами.\n\n"
                f"⬅️ Было: <code>{cls._night_prev_ocr_price:.4f}</code>\n"
                f"➡️ Стало: <code>{ocr_price:.4f}</code>\n"
                f"⚠️ Изменение: <b>{diff_pct:.2f}%</b> {direction}\n"
                f"⏰ Время: {astana_now.strftime('%H:%M:%S')} Астана\n\n"
                f"<blockquote expandable><b>Extraction History:</b>\n{history_text}</blockquote>"
            )
            # Check if this volatility signal is a duplicate
            is_duplicate = DatabaseRepository.is_signal_duplicate("NIGHT_VOLATILITY", ocr_price, cls._night_prev_ocr_price)
            DatabaseRepository.save_signal("NIGHT_VOLATILITY", ocr_price, cls._night_prev_ocr_price, diff_pct)

            if not is_duplicate:
                logger.info(f"🌙 Night volatility detected: {diff_pct:.2f}%. Notifying subscribers...")
                for sub_chat_id, platform in DatabaseRepository.get_active_subscribers():
                    if platform == 'telegram':
                        TelegramNotifier.send_alert(msg, sub_chat_id)
            else:
                logger.info(f"🌙 Night volatility detected: {diff_pct:.2f}%, but it is a DUPLICATE. Skipping notification.")

        # Update previous price for next cycle
        cls._night_prev_ocr_price = ocr_price
