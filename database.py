import sqlite3
import logging
from config import DB_NAME

logger = logging.getLogger(__name__)

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE,
                tg_username TEXT,
                platform_username TEXT,
                notifications_enabled INTEGER DEFAULT 0,
                role TEXT DEFAULT 'user',
                banned INTEGER DEFAULT 0
            )
        ''')
        # На случай, если обновляем старую БД
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN banned INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        conn.commit()

def add_user(telegram_id, tg_username, platform_username):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (telegram_id, tg_username, platform_username, role)
            VALUES (?, ?, ?, 'user')
            ON CONFLICT(telegram_id) DO UPDATE SET 
                tg_username = excluded.tg_username,
                platform_username = excluded.platform_username
        ''', (telegram_id, tg_username, platform_username))
        conn.commit()


def is_admin(telegram_id):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT role FROM users WHERE telegram_id = ?', (telegram_id,))
        row = cursor.fetchone()
        return row and row[0] == 'admin'

def get_all_users():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT telegram_id, tg_username, role, banned FROM users")
        return cursor.fetchall()

def get_user_by_id(telegram_id):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        return cursor.fetchone()

def ban_user_by_id(telegram_id):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET banned = 1 WHERE telegram_id = ?", (telegram_id,))
        conn.commit()

def unban_user_by_id(telegram_id):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET banned = 0 WHERE telegram_id = ?", (telegram_id,))
        conn.commit()

def update_platform_username(telegram_id, new_username):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET platform_username = ? WHERE telegram_id = ?", (new_username, telegram_id))
        conn.commit()

def promote_to_admin(telegram_id):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET role = 'admin' WHERE telegram_id = ?", (telegram_id,))
        conn.commit()

def set_notification_status(telegram_id, status):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET notifications_enabled = ? WHERE telegram_id = ?", (1 if status else 0, telegram_id))
        conn.commit()

def get_notification_status(telegram_id):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT notifications_enabled FROM users WHERE telegram_id = ?", (telegram_id,))
        row = cursor.fetchone()
        return bool(row[0]) if row else False

def is_user_banned(telegram_id):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT banned FROM users WHERE telegram_id = ?", (telegram_id,))
        row = cursor.fetchone()
        return bool(row[0]) if row else False

def delete_user(telegram_id):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE telegram_id = ?", (telegram_id,))
        conn.commit()

def get_platform_username(telegram_id):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT platform_username FROM users WHERE telegram_id = ?", (telegram_id,))
        row = cursor.fetchone()
        return row[0] if row else None

def get_user_stats():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        
        # Total users
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        # Active users (not banned)
        cursor.execute("SELECT COUNT(*) FROM users WHERE banned = 0")
        active_users = cursor.fetchone()[0]
        
        # Banned users
        cursor.execute("SELECT COUNT(*) FROM users WHERE banned = 1")
        banned_users = cursor.fetchone()[0]
        
        # Admin users
        cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
        admin_users = cursor.fetchone()[0]
        
        # Users with notifications enabled
        cursor.execute("SELECT COUNT(*) FROM users WHERE notifications_enabled = 1")
        notifications_enabled = cursor.fetchone()[0]
        
        return {
            "total": total_users,
            "active": active_users,
            "banned": banned_users,
            "admin": admin_users,
            "notifications_enabled": notifications_enabled
        }

# Функция для добавления тестовых пользователей
def add_test_users():
    # Добавляем тестового админа
    add_user(123456789, "test_admin", "admin")
    promote_to_admin(123456789)
    
    # Добавляем обычного пользователя
    add_user(987654321, "test_user", "user")
    
    logger.info("Test users added successfully")
