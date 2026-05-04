import asyncio
import logging
import inspect
from datetime import datetime, timedelta

from src.core.config import Config
from src.database.repository import DatabaseRepository
from src.services.notifier import TelegramNotifier
from src.controllers.monitoring_controller import MonitoringController

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

_last_task_error_notify_time: datetime | None = None

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
    
    controller = MonitoringController()
    
    logger.info("Freedom Finance Monitoring App Started.")
    
    # Schedule tasks concurrently
    task1 = asyncio.create_task(schedule_task(20, controller.monitoring_cycle))
    task2 = asyncio.create_task(schedule_task(30, controller.post_market_cycle))
    task3 = asyncio.create_task(schedule_task(3600, controller.cleanup_snapshots))
    
    await asyncio.gather(task1, task2, task3)


