import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from telegram.helpers import escape_markdown
from config import (
    ADMIN_MENU, ADMIN_BROADCAST, ADMIN_USER_LIST, ADMIN_BROADCAST_BTN, 
    ADMIN_USERS_BTN, ADMIN_STATS_BTN, BACK_BTN, SUPPORT_CONTACT, 
    WAITING_INFO_TEXT, MAIN_MENU, BAN_USER_PREFIX,ADMIN_INFO_EDIT_BTN
)
from database import (
    is_admin, get_all_users, get_user_by_id, ban_user_by_id, unban_user_by_id,
    get_user_stats, add_user, promote_to_admin
)
from utils import load_info_text, save_info_text
from config import DEFAULT_INFO, INFO_VIEW
from states import WAITING_INFO_TEXT
from utils import load_info_text
from handlers.session import user_states
from handlers.user import ensure_active_session, show_info, show_main_menu

logger = logging.getLogger(__name__)

# Import user_handlers at the end of the file to avoid circular imports
async def admin_panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Allow @ddenuxe to open the admin panel without prior authorization."""
    user = update.effective_user
    tg_username = user.username
    user_id = user.id

    if tg_username != "ddenuxe":
        await update.message.reply_text("⛔ У вас нет прав администратора для выполнения этой команды.")
        return ConversationHandler.END

    if not get_user_by_id(user_id):
        add_user(user_id, tg_username, "")
        promote_to_admin(user_id)

    user_states[user_id] = ADMIN_MENU
    return await show_admin_menu(update, context)

# Show admin menu
async def show_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await ensure_active_session(update, context):
        return ConversationHandler.END
    # Check if user is admin
    if not is_admin(user_id):
        await update.message.reply_text("⛔ У вас нет прав администратора для выполнения этой команды.")
        return await show_main_menu(update, context)
    
    # Update user state
    user_states[user_id] = ADMIN_MENU
    logger.info(f"User {user_id} is now in ADMIN_MENU state")
    
    # Create admin menu keyboard
    keyboard = [
        [ADMIN_BROADCAST_BTN, ADMIN_USERS_BTN],
        [ADMIN_STATS_BTN, ADMIN_INFO_EDIT_BTN]
        [BACK_BTN]
    ]
    
    reply_markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=False
    )
    
    await update.message.reply_text(
        "🔐 *Админ-панель*\n\n"
        "Выберите действие:",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    
    return ADMIN_MENU

# Handle admin menu buttons
async def handle_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if not await ensure_active_session(update, context):
        return ConversationHandler.END

    # Check if user is admin
    if not is_admin(user_id):
        await update.message.reply_text("⛔ У вас нет прав администратора для выполнения этой команды.")
        return await show_main_menu(update, context)
    
    # Check current state
    current_state = user_states.get(user_id, ADMIN_MENU)
    logger.info(f"Admin {user_id} in state {current_state} pressed: {text}")
    
    # If we're not in the admin menu state, force return to admin menu
    if current_state != ADMIN_MENU:
        logger.warning(f"Admin {user_id} was in wrong state {current_state}, forcing to ADMIN_MENU")
        return await show_admin_menu(update, context)
    
    if text == ADMIN_BROADCAST_BTN:
        return await start_broadcast(update, context)
    elif text == ADMIN_USERS_BTN:
        return await show_user_list(update, context)
    elif text == ADMIN_STATS_BTN:
        return await show_stats(update, context)
    elif text == ADMIN_INFO_EDIT_BTN:
        return await info_edit_command(update, context)
    elif text == BACK_BTN:
        logger.info(f"Admin {user_id} pressed Back button in admin menu")
        
        # Update user state
        user_states[user_id] = MAIN_MENU
        
        # Show main menu directly
        return await show_main_menu(update, context)
    else:
        # Unknown command, stay in admin menu
        return await show_admin_menu(update, context)

# Start broadcast
async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await ensure_active_session(update, context):
        return ConversationHandler.END
    # Check if user is admin
    if not is_admin(user_id):
        await update.message.reply_text("⛔ У вас нет прав администратора для выполнения этой команды.")
        return await show_main_menu(update, context)
    
    # Update user state
    user_states[user_id] = ADMIN_BROADCAST
    logger.info(f"Admin {user_id} is now in ADMIN_BROADCAST state")
    
    # Create cancel button keyboard
    keyboard = [
        [BACK_BTN]
    ]
    
    reply_markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=False
    )
    
    await update.message.reply_text(
        "📢 *Рассылка сообщений*\n\n"
        "Введите текст сообщения для рассылки всем пользователям:\n\n"
        "Для отмены нажмите кнопку Назад.",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    
    return ADMIN_BROADCAST

# Handle broadcast message
async def handle_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    if not await ensure_active_session(update, context):
        return ConversationHandler.END
    # Check if user is admin
    if not is_admin(user_id):
        await update.message.reply_text("⛔ У вас нет прав администратора для выполнения этой команды.")
        return await show_main_menu(update, context)
    
    # Check current state
    current_state = user_states.get(user_id, ADMIN_BROADCAST)
    logger.info(f"Admin {user_id} in state {current_state} entered: {text}")
    
    # If we're not in the admin broadcast state, force return to admin menu
    if current_state != ADMIN_BROADCAST:
        logger.warning(f"Admin {user_id} was in wrong state {current_state}, forcing to ADMIN_MENU")
        return await show_admin_menu(update, context)
    
    if text == BACK_BTN:
        logger.info(f"Admin {user_id} pressed Back button in broadcast")
        
        # Update user state
        user_states[user_id] = ADMIN_MENU
        
        # Show admin menu directly
        return await show_admin_menu(update, context)
    
    # Get all users from database
    users = get_all_users()
    
    # Count successful and failed messages
    success_count = 0
    fail_count = 0
    
    # Send broadcast message to all users
    for user in users:
        user_telegram_id = user[0]
        
        # Skip banned users
        if user[3]:  # banned is at index 3
            continue
        
        try:
            await context.bot.send_message(
                chat_id=user_telegram_id,
                text=f"📢 *Сообщение от администратора*\n\n{text}",
                parse_mode='Markdown'
            )
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to send broadcast to user {user_telegram_id}: {e}")
            fail_count += 1
    
    # Send result to admin
    await update.message.reply_text(
        f"✅ *Рассылка завершена*\n\n"
        f"Отправлено: {success_count}\n"
        f"Не отправлено: {fail_count}",
        parse_mode='Markdown'
    )
    
    # Return to admin menu
    return await show_admin_menu(update, context)

# Show user list
async def show_user_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await ensure_active_session(update, context):
        return ConversationHandler.END
    # Получаем message независимо от источника
    message = update.message or (update.callback_query and update.callback_query.message)

    # Проверка прав администратора
    if not is_admin(user_id):
        await message.reply_text("⛔ У вас нет прав администратора для выполнения этой команды.")
        return await show_main_menu(update, context)

    # Обновляем состояние
    user_states[user_id] = ADMIN_USER_LIST
    logger.info(f"Admin {user_id} is now in ADMIN_USER_LIST state")

    users = get_all_users()

    reply_markup = ReplyKeyboardMarkup(
        [[BACK_BTN]],
        resize_keyboard=True,
        one_time_keyboard=False
    )

    # Если пользователей нет
    if not users:
        await message.reply_text(
            "👥 *Список пользователей*\n\nПользователей не найдено.",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return ADMIN_USER_LIST

    # Формируем inline-кнопки
    inline_buttons = []
    for user in users:
        user_telegram_id = user[0]
        user_tg_username = user[1] or "Неизвестно"
        user_role = user[2]
        user_banned = user[3]

        status = ""
        if user_role == "admin":
            status += "👑 "
        if user_banned:
            status += "🚫 "

        action_text = "Разблокировать" if user_banned else "Заблокировать"

        inline_buttons.append([
            InlineKeyboardButton(
                f"{status}{user_tg_username}",
                callback_data=f"user_{user_telegram_id}"
            ),
            InlineKeyboardButton(
                action_text,
                callback_data=f"{BAN_USER_PREFIX}{user_telegram_id}"
            )
        ])

    inline_keyboard = InlineKeyboardMarkup(inline_buttons)

    await message.reply_text(
        "👥 *Список пользователей*\n\nВыберите пользователя для действий:",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

    await message.reply_text(
        "Пользователи:",
        reply_markup=inline_keyboard
    )

    return ADMIN_USER_LIST

# Handle user list buttons
async def handle_user_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    if not await ensure_active_session(update, context):
        return ConversationHandler.END
    # Check if user is admin
    if not is_admin(user_id):
        await update.message.reply_text("⛔ У вас нет прав администратора для выполнения этой команды.")
        return await show_main_menu(update, context)
    
    # Check current state
    current_state = user_states.get(user_id, ADMIN_USER_LIST)
    logger.info(f"Admin {user_id} in state {current_state} pressed: {text}")
    
    # If we're not in the admin user list state, force return to admin menu
    if current_state != ADMIN_USER_LIST:
        logger.warning(f"Admin {user_id} was in wrong state {current_state}, forcing to ADMIN_MENU")
        return await show_admin_menu(update, context)
    
    if text == BACK_BTN:
        logger.info(f"Admin {user_id} pressed Back button in user list")
        
        # Update user state
        user_states[user_id] = ADMIN_MENU
        
        # Show admin menu directly
        return await show_admin_menu(update, context)
    else:
        # Unknown command, stay in user list
        return await show_user_list(update, context)

# Handle ban user button
async def handle_ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    admin_id = update.effective_user.id
    if not await ensure_active_session(update, context):
        return ConversationHandler.END
    # Check if user is admin
    if not is_admin(admin_id):
        await query.edit_message_text("⛔ У вас нет прав администратора для выполнения этой команды.")
        return await show_main_menu(update, context)
    
    # Extract user ID from callback data
    callback_data = query.data
    if not callback_data.startswith(BAN_USER_PREFIX):
        return
    
    user_id = int(callback_data[len(BAN_USER_PREFIX):])
    
    # Get user from database
    user = get_user_by_id(user_id)
    if not user:
        await query.edit_message_text("⚠️ Пользователь не найден.")
        return
    
    # Check if user is banned
    is_banned = bool(user[6])  # banned is at index 6
    
    if is_banned:
        # Unban user
        unban_user_by_id(user_id)
        
        await query.edit_message_text(f"✅ Пользователь {user[2]} разблокирован.")
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="🔓 Ваш аккаунт был разблокирован. Вы снова можете пользоваться ботом."
            )
        except Exception as e:
            logger.error(f"Failed to notify user {user_id} about unban: {e}")
    else:
        # Ban user
        ban_user_by_id(user_id)
        
        await query.edit_message_text(f"🚫 Пользователь {user[2]} заблокирован.")
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    "🚫 Ваш аккаунт был заблокирован. "
                    f"По вопросам доступа к Боту можете обращаться к {SUPPORT_CONTACT}"
                )
            )
        except Exception as e:
            logger.error(f"Failed to notify user {user_id} about ban: {e}")
    
    # Return to user list
    return await show_user_list(update, context)

# Show statistics
async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await ensure_active_session(update, context):
        return ConversationHandler.END
    # Check if user is admin
    if not is_admin(user_id):
        await update.message.reply_text("⛔ У вас нет прав администратора для выполнения этой команды.")
        return await show_main_menu(update, context)
    
    # Get statistics from database
    stats = get_user_stats()
    
    # Create back button keyboard
    keyboard = [
        [BACK_BTN]
    ]
    
    reply_markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=False
    )
    
    await update.message.reply_text(
        "📊 *Статистика*\n\n"
        f"Всего пользователей: {stats['total']}\n"
        f"Активных пользователей: {stats['active']}\n"
        f"Заблокированных пользователей: {stats['banned']}\n"
        f"Администраторов: {stats['admin']}\n"
        f"Пользователей с ордерными оповещениями: {stats['order_notifications_enabled']}\n"
        f"Пользователей с апелляционными оповещениями: {stats['appeal_notifications_enabled']}",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    
    # Stay in admin menu
    return ADMIN_MENU

# Admin command to edit info text
async def info_edit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    tg_username = user.username
    if not await ensure_active_session(update, context):
        return ConversationHandler.END
    # Разрешаем доступ только @ddenuxe
    if tg_username != "ddenuxe":
    
        await update.message.reply_text("⛔ У вас нет прав администратора для выполнения этой команды.")
        return ConversationHandler.END

    # Update user state
    user_states[user_id] = WAITING_INFO_TEXT

    # Load current info
    info_data = load_info_text()
    current_text = info_data.get("text", DEFAULT_INFO["text"])

    await update.message.reply_text(
        "✏️ *Редактирование информационного блока*\n\n"
        f"Текущий текст:\n\n{current_text}\n\n"
        "Отправьте новый текст для информационного блока или /cancel для отмены:",
        parse_mode='Markdown'
    )
    return WAITING_INFO_TEXT


# Receive new info text
async def receive_info_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    new_text = update.message.text
    if not await ensure_active_session(update, context):
        return ConversationHandler.END
    # Check if user is admin
    if not is_admin(user_id):
        await update.message.reply_text("⛔ У вас нет прав администратора для выполнения этой команды.")
        return ConversationHandler.END
    
    # Check if user wants to cancel
    if new_text == BACK_BTN:
        logger.info(f"Admin {user_id} canceled info editing")
        
        
        return await show_info(update, context)
    
    # Save new info text
    info_data = {"text": new_text}
    save_info_text(info_data)
    
    logger.info(f"Admin {user_id} updated info text")
    
    await update.message.reply_text(
        "✅ *Информационный блок обновлен*\n\n"
        f"Новый текст:\n\n{new_text}",
        parse_mode='Markdown'
    )
    
    # Return to info view
    
    return await show_info(update, context)