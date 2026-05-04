import asyncio
import logging
from src.main import main
from src.core.config import Config
from src.services.notifier import TelegramNotifier

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nMonitoring app stopped.")
    except Exception as e:
        error_msg = f"💀 <b>FATAL ERROR: Application Crashed</b>\n\n<code>{str(e)}</code>"
        logging.exception(f"Fatal error in main entry point: {e}")
        TelegramNotifier.send_alert(error_msg, Config.TG_CHAT_ID_ERROR)
