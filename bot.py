import telebot
import os
from dotenv import load_dotenv
from db import register_user, init_db

# Load environment variables
load_dotenv()

TOKEN = os.environ.get("TG_BOT_TOKEN")
if not TOKEN:
    print("Error: TG_BOT_TOKEN not found in .env")
    exit(1)

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    chat_id = message.chat.id
    username = message.from_user.username or message.from_user.first_name
    
    # Register user with a 7-day trial
    expiry_date = register_user(chat_id, 'telegram', username, trial_days=7)
    
    welcome_text = (
        f"👋 Привет, {username}!\n\n"
        f"Добро пожаловать в систему мониторинга Freedmon.\n"
        f"Ваша подписка активирована до: <b>{expiry_date}</b> (7 дней пробного периода).\n\n"
        f"Вы будете получать сигналы об арбитражных возможностях прямо здесь."
    )
    bot.reply_to(message, welcome_text, parse_mode='HTML')

if __name__ == "__main__":
    init_db()
    print("Registration bot is running...")
    bot.infinity_polling()
