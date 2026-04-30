import requests
from src.core.config import Config
import logging

logger = logging.getLogger(__name__)

class TelegramNotifier:
    """Service for sending messages via Telegram Bot API."""
    
    @staticmethod
    def send_alert(message: str, chat_id: str, silent: bool = False) -> bool:
        if not Config.TG_BOT_TOKEN or not chat_id:
            logger.warning(f"Telegram configuration missing (Chat ID: {chat_id}). Cannot send alert.")
            return False
            
        url = f"https://api.telegram.org/bot{Config.TG_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id, 
            "text": message, 
            "parse_mode": "HTML",
            "disable_notification": silent
        }
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code != 200:
                logger.error(f"Failed to send Telegram alert to {chat_id}: {response.text}")
                return False
            else:
                logger.info(f"Telegram alert sent successfully to {chat_id} (Silent: {silent}).")
                return True
        except Exception as e:
            logger.error(f"Error sending Telegram alert to {chat_id}: {e}")
            return False
