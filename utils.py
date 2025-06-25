import json
import logging
from config import INFO_FILE, DEFAULT_INFO

logger = logging.getLogger(__name__)

# Load or create info text file
def load_info_text():
    try:
        with open(INFO_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Create default file if not exists or corrupted
        save_info_text(DEFAULT_INFO)
        return DEFAULT_INFO

# Save info text to file
def save_info_text(info_data):
    with open(INFO_FILE, 'w', encoding='utf-8') as f:
        json.dump(info_data, f, ensure_ascii=False, indent=2)


# Для простоты — временно в памяти, можно подключить SQLite
alert_flags = {}  # user_id: bool
user_map = {}     # trader_username: user_id

def is_notifications_enabled(user_id: int) -> bool:
    return alert_flags.get(user_id, False)

def set_notifications(user_id: int, enabled: bool):
    alert_flags[user_id] = enabled

def get_user_id_by_trader_username(username: str) -> int:
    return user_map.get(username)

def register_trader(username: str, user_id: int):
    user_map[username] = user_id

def format_pay_type(pay_type: str) -> str:
    """Return payment type in strict Card/OneClick/IBAN format."""
    mapping = {
        "card": "Card",
        "oneclick": "OneClick",
        "iban": "IBAN",
    }
    return mapping.get(pay_type.lower(), pay_type)

def format_order_message(data: dict) -> str:
    return (
        f"🔹 Сумма, фиат: {data['fiat_amount']} {data['currency']}\n"
        f"🔹 Реквизиты: {data['requisites_name']} "
        f"{str(data.get('requisites_cardNumber', ''))[-4:]}, "
        f"{data.get('requisites_cardholderName', '')} {data.get('requisites_cardholderSurname', '')[0]}.\n"
        f"🔹 Способ оплаты: {format_pay_type(data['type'])}\n\n"
        f"▫️ ID сделки: {data['order_id']}\n"
        f"▫️ Создана: время {data['date_created']} (UTC+{data['UTC']}), дата {data['date_created']}\n"
        f"▫️ Время закрытия: время+{data['timer']} минут {data['date_created']} (UTC+{data['UTC']}), дата {data['date_created']}\n\n"
        f"🔸 Мой курс: {data['trader_rate']} ({data['trader_fee']}%)\n"
        f"🔸 Курс биржи: {data['exchange_rate']}"
    )
