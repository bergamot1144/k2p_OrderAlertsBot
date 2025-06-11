import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Bot configuration
BOT_TOKEN = os.getenv("BOT_TOKEN", "7849702905:AAFtPFdHubbBA-x8zgXs6q-fb0t8As9hfA0")
ADMIN_IDS = [int(id) for id in os.getenv("ADMIN_IDS", "").split(",") if id]
USE_MOCK = False  # True — use mock data, False — real API requests
AUTH_ENDPOINT = os.getenv("AUTH_ENDPOINT", "https://tradeacclogin.click/api/v1/telegram/trader/orderalert/AuthHandler.ashx")


SUPPORT_CONTACT = "@konvert_pm"


# Temporary storage (for conversation state)
user_data_temp = {}
password_attempts = {}
user_states = {}  # Track user states

# Database configuration
DB_NAME = "users.db"

# Information file
INFO_FILE = "bot_info.json"

# Default info text
DEFAULT_INFO = {
    "text": "Этот бот предназначен для получения оповещений об открытых ордерах на платформе Konvert2pay."
}

# Constants for conversation states
(
    USERNAME, 
    PASSWORD, 
    WAITING_INFO_TEXT, 
    MAIN_MENU, 
    PROFILE_VIEW, 
    INFO_VIEW, 
    LOGOUT_CONFIRM,
    ADMIN_MENU,
    ADMIN_BROADCAST,
    ADMIN_USER_LIST,
    ADMIN_BAN_USER
) = range(11)

# Menu button texts
PROFILE_BTN = "👤 Профиль"
INFO_BTN = "ℹ️ Информация"
ACTIVATE_BTN = "🔔 Активировать оповещения"
DEACTIVATE_BTN = "🔕 Деактивировать оповещения"
LOGOUT_BTN = "❌ Выйти из аккаунта"
BACK_BTN = "◀️ Назад"
ADMIN_BTN = "🔐 Админ-панель"

# Admin menu buttons
ADMIN_BROADCAST_BTN = "📢 Рассылка"
ADMIN_USERS_BTN = "👥 Список пользователей"
ADMIN_STATS_BTN = "📊 Статистика"
ADMIN_INFO_EDIT_BTN = "✏️ Изменить информацию"

# Callback data constants
CANCEL_LOGOUT = "cancel_logout"
BACK_TO_MAIN = "back_to_main"
BACK_TO_PROFILE = "back_to_profile"
BAN_USER_PREFIX = "ban_user_"
PROMOTE_USER_PREFIX = "promote_user_"
