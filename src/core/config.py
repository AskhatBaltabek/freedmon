import os
from dotenv import load_dotenv

# Load variables from .env file at the project root
# Using os.path.dirname to travel up from src/core to the root folder
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
env_path = os.path.join(root_dir, '.env')

if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path)
else:
    # Fallback to current working directory
    load_dotenv()

class Config:
    """Centralized configuration for the application."""
    
    # Telegram Bot
    TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
    
    # Telegram Chat IDs
    TG_CHAT_ID_BUY = os.environ.get("TG_CHAT_ID_BUY", "")
    TG_CHAT_ID_SELL = os.environ.get("TG_CHAT_ID_SELL", "")
    TG_CHAT_ID_POST_MARKET = os.environ.get("TG_CHAT_ID_POST_MARKET", "")
    TG_CHAT_ID_ERROR = os.environ.get("TG_CHAT_ID_ERROR", "288485936")

    # Database
    DB_PATH = os.environ.get("DB_PATH", os.path.join(root_dir, "freedmon.db"))
    
    # Alerts setup
    DIFFERENCE_THRESHOLD_PERCENT = float(os.environ.get("DIFFERENCE_THRESHOLD_PERCENT", "1.0"))
    
    # ADB WiFi connection
    DEVICE_IP = os.environ.get("DEVICE_IP", "")
    DEVICE_PORT = os.environ.get("DEVICE_PORT", "5555")

    # Application Paths
    ROOT_DIR = root_dir
    SNAPSHOTS_DIR = os.path.join(root_dir, "snapshots")

    @classmethod
    def validate(cls):
        """Prints warnings for missing critical configurations."""
        if not cls.TG_BOT_TOKEN:
            print("Warning: TG_BOT_TOKEN is not set. Telegram alerts will not function.")
