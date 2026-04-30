import telebot
import logging
from src.core.config import Config
from src.database.repository import DatabaseRepository

logger = logging.getLogger(__name__)

if not Config.TG_BOT_TOKEN:
    logger.error("Error: TG_BOT_TOKEN not found in configuration.")
    exit(1)

bot = telebot.TeleBot(Config.TG_BOT_TOKEN)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    chat_id = message.chat.id
    username = message.from_user.username or message.from_user.first_name
    
    # Register user with a 7-day trial via Database Repository
    expiry_date = DatabaseRepository.register_user(str(chat_id), 'telegram', username, trial_days=7)
    
    welcome_text = (
        f"👋 Привет, {username}!\n\n"
        f"Добро пожаловать в систему мониторинга Freedmon.\n"
        f"Ваша подписка активирована до: <b>{expiry_date}</b> (7 дней пробного периода).\n\n"
        f"Вы будете получать сигналы об арбитражных возможностях прямо здесь."
    )
    bot.reply_to(message, welcome_text, parse_mode='HTML')
    logger.info(f"New user registered: {username} ({chat_id})")

def run_bot():
    DatabaseRepository.init_db()
    logger.info("Registration bot is running...")
    bot.infinity_polling()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_bot()
