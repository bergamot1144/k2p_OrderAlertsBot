import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from database import (
    add_user, delete_user, promote_to_admin, is_admin, 
    get_user_by_id, get_all_users
)

logger = logging.getLogger(__name__)

# Команда для добавления пользователя
async def add_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Проверяем, является ли пользователь администратором
    if not is_admin(user_id):
        await update.message.reply_text("⛔ У вас нет прав администратора для выполнения этой команды.")
        return
    
    # Проверяем аргументы команды
    if len(context.args) < 3:
        await update.message.reply_text(
            "❌ *Недостаточно аргументов*\n\n"
            "Использование: /adduser <telegram_id> <tg_username> <platform_username>\n\n"
            "Пример: `/adduser 123456789 @username user123`",
            parse_mode='Markdown'
        )
        return
    
    try:
        # Парсим аргументы
        telegram_id = int(context.args[0])
        tg_username = context.args[1]
        platform_username = context.args[2]
        
        # Проверяем, существует ли пользователь
        existing_user = get_user_by_id(telegram_id)
        if existing_user:
            await update.message.reply_text(
                f"⚠️ Пользователь с ID {telegram_id} уже существует в базе данных."
            )
            return
        
        # Добавляем пользователя
        add_user(telegram_id, tg_username, platform_username)
        
        logger.info(f"Admin {user_id} added user {telegram_id} ({tg_username}, {platform_username})")
        
        await update.message.reply_text(
            f"✅ *Пользователь успешно добавлен*\n\n"
            f"Telegram ID: `{telegram_id}`\n"
            f"Telegram Username: {tg_username}\n"
            f"Platform Username: {platform_username}",
            parse_mode='Markdown'
        )
    
    except ValueError:
        await update.message.reply_text(
            "❌ *Ошибка*\n\n"
            "Telegram ID должен быть числом.",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error adding user: {e}")
        await update.message.reply_text(
            f"❌ *Ошибка при добавлении пользователя*\n\n"
            f"Подробности: {str(e)}",
            parse_mode='Markdown'
        )

# Команда для удаления пользователя
async def delete_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Проверяем, является ли пользователь администратором
    if not is_admin(user_id):
        await update.message.reply_text("⛔ У вас нет прав администратора для выполнения этой команды.")
        return
    
    # Проверяем аргументы команды
    if len(context.args) < 1:
        await update.message.reply_text(
            "❌ *Недостаточно аргументов*\n\n"
            "Использование: /deleteuser <telegram_id>\n\n"
            "Пример: `/deleteuser 123456789`",
            parse_mode='Markdown'
        )
        return
    
    try:
        # Парсим аргументы
        telegram_id = int(context.args[0])
        
        # Проверяем, существует ли пользователь
        existing_user = get_user_by_id(telegram_id)
        if not existing_user:
            await update.message.reply_text(
                f"⚠️ Пользователь с ID {telegram_id} не найден в базе данных."
            )
            return
        
        # Проверяем, не пытается ли админ удалить самого себя
        if telegram_id == user_id:
            await update.message.reply_text(
                "⚠️ Вы не можете удалить самого себя."
            )
            return
        
        # Удаляем пользователя
        delete_user(telegram_id)
        
        logger.info(f"Admin {user_id} deleted user {telegram_id}")
        
        await update.message.reply_text(
            f"✅ *Пользователь успешно удален*\n\n"
            f"Telegram ID: `{telegram_id}`",
            parse_mode='Markdown'
        )
    
    except ValueError:
        await update.message.reply_text(
            "❌ *Ошибка*\n\n"
            "Telegram ID должен быть числом.",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        await update.message.reply_text(
            f"❌ *Ошибка при удалении пользователя*\n\n"
            f"Подробности: {str(e)}",
            parse_mode='Markdown'
        )

# Команда для повышения пользователя до администратора
async def make_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Проверяем, является ли пользователь администратором
    if not is_admin(user_id):
        await update.message.reply_text("⛔ У вас нет прав администратора для выполнения этой команды.")
        return
    
    # Проверяем аргументы команды
    if len(context.args) < 1:
        await update.message.reply_text(
            "❌ *Недостаточно аргументов*\n\n"
            "Использование: /makeadmin <telegram_id>\n\n"
            "Пример: `/makeadmin 123456789`",
            parse_mode='Markdown'
        )
        return
    
    try:
        # Парсим аргументы
        telegram_id = int(context.args[0])
        
        # Проверяем, существует ли пользователь
        existing_user = get_user_by_id(telegram_id)
        if not existing_user:
            await update.message.reply_text(
                f"⚠️ Пользователь с ID {telegram_id} не найден в базе данных."
            )
            return
        
        # Проверяем, не является ли пользователь уже администратором
        if is_admin(telegram_id):
            await update.message.reply_text(
                f"⚠️ Пользователь с ID {telegram_id} уже является администратором."
            )
            return
        
        # Повышаем пользователя до администратора
        promote_to_admin(telegram_id)
        
        logger.info(f"Admin {user_id} promoted user {telegram_id} to admin")
        
        await update.message.reply_text(
            f"✅ *Пользователь повышен до администратора*\n\n"
            f"Telegram ID: `{telegram_id}`",
            parse_mode='Markdown'
        )
    
    except ValueError:
        await update.message.reply_text(
            "❌ *Ошибка*\n\n"
            "Telegram ID должен быть числом.",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error promoting user to admin: {e}")
        await update.message.reply_text(
            f"❌ *Ошибка при повышении пользователя до администратора*\n\n"
            f"Подробности: {str(e)}",
            parse_mode='Markdown'
        )

# Команда для просмотра списка пользователей
async def list_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Проверяем, является ли пользователь администратором
    if not is_admin(user_id):
        await update.message.reply_text("⛔ У вас нет прав администратора для выполнения этой команды.")
        return
    
    try:
        # Получаем список всех пользователей
        users = get_all_users()
        
        if not users:
            await update.message.reply_text("📋 *Список пользователей пуст*", parse_mode='Markdown')
            return
        
        # Формируем сообщение со списком пользователей
        message = "📋 *Список пользователей*\n\n"
        message += "ID | Username | Role | Banned\n"
        message += "---|----------|------|-------\n"
        
        for user in users:
            telegram_id, tg_username, role, banned = user
            message += f"`{telegram_id}` | {tg_username or 'N/A'} | {role} | {'✅' if banned else '❌'}\n"
        
        # Отправляем сообщение
        await update.message.reply_text(message, parse_mode='Markdown')
    
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        await update.message.reply_text(
            f"❌ *Ошибка при получении списка пользователей*\n\n"
            f"Подробности: {str(e)}",
            parse_mode='Markdown'
        )

# Команда для помощи по админ-командам
async def admin_help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Проверяем, является ли пользователь администратором
    if not is_admin(user_id):
        await update.message.reply_text("⛔ У вас нет прав администратора для выполнения этой команды.")
        return
    
    help_text = (
        "🔐 *Команды администратора*\n\n"
        "/adduser <telegram_id> <tg_username> <platform_username> - Добавить пользователя\n"
        "/deleteuser <telegram_id> - Удалить пользователя\n"
        "/makeadmin <telegram_id> - Повысить пользователя до администратора\n"
        "/listusers - Показать список всех пользователей\n"
        "/adminhelp - Показать эту справку\n\n"
        "Примеры:\n"
        "`/adduser 123456789 @username user123`\n"
        "`/deleteuser 123456789`\n"
        "`/makeadmin 123456789`"
    )
    
    await update.message.reply_text(help_text, parse_mode='Markdown')
