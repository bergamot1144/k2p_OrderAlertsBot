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
