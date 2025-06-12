import logging
import html
import requests
import re
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from telegram.helpers import escape_markdown
from config import (
    USE_MOCK, AUTH_ENDPOINT, SUPPORT_CONTACT, USERNAME, PASSWORD, MAIN_MENU, 
    PROFILE_VIEW, INFO_VIEW, LOGOUT_CONFIRM, PROFILE_BTN, INFO_BTN, 
    ACTIVATE_BTN, DEACTIVATE_BTN, LOGOUT_BTN, BACK_BTN, ADMIN_BTN, 
    CANCEL_LOGOUT, WAITING_INFO_TEXT, DEFAULT_INFO
)
from database import (
    add_user, get_user_by_id, get_notification_status, set_notification_status, 
    is_admin, is_user_banned, delete_user, get_platform_username, promote_to_admin
)
from utils import load_info_text, save_info_text
# from states import INFO_VIEW, user_states
logger = logging.getLogger(__name__)

# Temporary storage (for conversation state)
user_data_temp = {}
password_attempts = {}
user_states = {}  # Track user states

# Функция для экранирования Markdown-символов
def escape_markdown(text: str) -> str:
    return re.sub(r'([*_`\[\]()])', r'\\\1', text)

# Старт бота
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    raw_username = f"@{user.username}" if user.username else user.first_name
    username = escape_markdown(raw_username)

    logger.info(f"User {user_id} started the bot")

    # Проверка блокировки
    if is_user_banned(user_id):
        await update.message.reply_text(
            "❌ *Ваш аккаунт заблокирован*\n\n"
            f"Пожалуйста, свяжитесь со службой поддержки: {SUPPORT_CONTACT}",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    # Полный сброс состояния
    user_states.pop(user_id, None)
    user_data_temp.pop(user_id, None)

    # Установка нового состояния
    user_states[user_id] = USERNAME

    # Приветственное сообщение
    await update.message.reply_text(
        f"Привет, {username} 👋🏻\n\n"
        "Этот Бот поможет Трейдерам Платформы *Konvert2pay* получать оповещения об открытых ордерах.",
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardRemove()
    )

    # Запрос логина
    await update.message.reply_text("👤 Введите логин Трейдера:")

    return USERNAME

# Get username
async def receive_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data_temp[user_id] = {"username": update.message.text}
    password_attempts[user_id] = 0
    
    # Update user state
    user_states[user_id] = PASSWORD
    
    logger.info(f"User {user_id} entered username: {update.message.text}")
    
    await update.message.reply_text("🔢 Введите пароль:")
    return PASSWORD

# Get password
async def receive_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    password = update.message.text
    entered_username = user_data_temp[user_id]["username"]
    tg_username = user.username if user.username else user.first_name

    logger.info(f"User {user_id} entered password")

    payload = {
        "username": entered_username,
        "password": password,
        "tg_username": tg_username
    }

    if USE_MOCK:
        # Используем введённое имя, потому что нет API
        add_user(user_id, tg_username, entered_username)
        if entered_username == "admin":
            promote_to_admin(user_id)
        return await show_main_menu(update, context, suppress_text=True)

    try:
        response = requests.post(AUTH_ENDPOINT, json=payload, timeout=10)
        data = response.json()

        if response.status_code == 200 and data.get("Success"):
            # Получаем username из ответа сервера
            actual_username = data.get("username", entered_username)

            add_user(user_id, tg_username, actual_username)

            # Только tg_username @ddenuxe получает роль админа
            if tg_username == "Konvert_support_Di":
                promote_to_admin(user_id)

            return await show_main_menu(update, context, suppress_text=True)

        else:
            await update.message.reply_text(
                "❌ Пользователь не найден\n\nПожалуйста, проверьте логин и попробуйте снова."
            )
            return USERNAME

    except Exception as e:
        logger.error(f"Error during auth request: {e}")
        await update.message.reply_text(
            "⚠️ Ошибка при попытке входа. Пожалуйста, попробуйте позже."
        )
        return USERNAME



# Show main menu with keyboard buttons
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, suppress_text: str | bool = False):
    user_id = update.effective_user.id
    is_notifications_active = get_notification_status(user_id)

    user_states[user_id] = MAIN_MENU
    logger.info(f"User {user_id} is now in MAIN_MENU state")

    keyboard = [
        [PROFILE_BTN, INFO_BTN],
        [DEACTIVATE_BTN if is_notifications_active else ACTIVATE_BTN]
    ]

    if is_admin(user_id):
        keyboard.append([ADMIN_BTN])

    reply_markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=False
    )

    # Выбираем, какой текст показывать
    if suppress_text == "enabled":
        text = (
            "✅ Оповещения об активных ордерах успешно включены\n\n"
            "Теперь вы будете получать уведомления при создании новых платежей на ваши реквизиты."
        )
    elif suppress_text == "disabled":
        text = (
            "📵 Оповещения об активных ордерах успешно отключены\n\n"
            "Теперь вы не будете получать уведомления при создании новых платежей на ваши реквизиты."
        )
    elif suppress_text:
        text = "✅ Вы успешно авторизовались."
    else:
        text = "Главное меню"

    try:
        if hasattr(update, 'callback_query') and update.callback_query:
            await context.bot.send_message(
                chat_id=user_id,
                text=text,
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                text,
                reply_markup=reply_markup
            )
    except Exception as e:
        logger.error(f"Error showing menu: {e}")
        return ConversationHandler.END

    return MAIN_MENU




# Handle main menu button presses
async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    # Check if user is banned
    if is_user_banned(user_id):
        await update.message.reply_text(
            "❌ *Ваш аккаунт заблокирован*\n\n"
            f"Пожалуйста, свяжитесь со службой поддержки: {SUPPORT_CONTACT}",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    
    # Check if user exists in database
    user = get_user_by_id(user_id)
    if not user:
        await update.message.reply_text(
            "⚠️ *Сессия истекла*\n\n"
            "Пожалуйста, авторизуйтесь снова, используя команду /start",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    
    # Check current state
    current_state = user_states.get(user_id, MAIN_MENU)
    logger.info(f"User {user_id} in state {current_state} pressed: {text}")
    
    # If we're not in the main menu state, force return to main menu
    if current_state != MAIN_MENU:
        logger.warning(f"User {user_id} was in wrong state {current_state}, forcing to MAIN_MENU")
        return await show_main_menu(update, context)
    
    if text == PROFILE_BTN:
        return await show_profile(update, context)
    elif text == INFO_BTN:
        return await show_info(update, context)
    elif text == ACTIVATE_BTN:
        return await activate_notifications(update, context)
    elif text == DEACTIVATE_BTN:
        return await deactivate_notifications(update, context)
    elif text == ADMIN_BTN and is_admin(user_id):
        from handlers.admin import show_admin_menu
        return await show_admin_menu(update, context)
    else:
        # Unknown command, show menu again
        return await show_main_menu(update, context)

# Активировать уведомления
async def activate_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    set_notification_status(user_id, True)
    
    logger.info(f"User {user_id} activated notifications")

    # Возврат в меню с уведомлением
    return await show_main_menu(update, context, suppress_text="enabled")


# Деактивировать уведомления
async def deactivate_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    set_notification_status(user_id, False)
    
    logger.info(f"User {user_id} deactivated notifications")

    # Возврат в меню с уведомлением
    return await show_main_menu(update, context, suppress_text="disabled")


# Show profile information
async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Get user data from database
    user = get_user_by_id(user_id)
    if not user:
        await update.message.reply_text(
            "⚠️ *Сессия истекла*\n\n"
            "Пожалуйста, авторизуйтесь снова, используя команду /start",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    
    # Extract user data
    platform_username = user[3]  # platform_username is at index 3
    is_notifications_active = bool(user[4])  # notifications_enabled is at index 4
    
    # Update user state
    user_states[user_id] = PROFILE_VIEW
    logger.info(f"User {user_id} is now in PROFILE_VIEW state")
    
    # Create profile keyboard - FIXED: Put Back button first, then Logout button
    keyboard = [
        [BACK_BTN],
        [LOGOUT_BTN]
    ]
    
    reply_markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=False
    )
    
    await update.message.reply_text(
        f"👤 *Профиль*\n\n"
        f"Логин: `{platform_username}`\n"
        f"Статус оповещений: {'✅ Включены' if is_notifications_active else '❌ Отключены'}",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    
    return PROFILE_VIEW

# Handle profile view buttons
async def handle_profile_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    # Check current state
    current_state = user_states.get(user_id, PROFILE_VIEW)
    logger.info(f"User {user_id} in state {current_state} pressed: {text}")
    
    # If we're not in the profile view state, force return to main menu
    if current_state != PROFILE_VIEW:
        logger.warning(f"User {user_id} was in wrong state {current_state}, forcing to MAIN_MENU")
        return await show_main_menu(update, context)
    
    if text == BACK_BTN:
        logger.info(f"User {user_id} pressed Back button in profile view")
        
        # Update user state
        user_states[user_id] = MAIN_MENU
        
        # Show main menu directly
        return await show_main_menu(update, context)
    elif text == LOGOUT_BTN:
        logger.info(f"User {user_id} pressed Logout button in profile view")
        return await logout_confirmation(update, context)
    else:
        # Unknown command, stay in profile view
        return await show_profile(update, context)

# Logout confirmation
async def logout_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Get platform username from database
    platform_username = get_platform_username(user_id)
    if not platform_username:
        await update.message.reply_text(
            "⚠️ *Сессия истекла*\n\n"
            "Пожалуйста, авторизуйтесь снова, используя команду /start",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    
    # Update user state
    user_states[user_id] = LOGOUT_CONFIRM
    logger.info(f"User {user_id} is now in LOGOUT_CONFIRM state")
    
    # Store username in context for verification
    context.user_data["logout_username"] = platform_username
    
    # Create inline keyboard with cancel button
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Отмена", callback_data=CANCEL_LOGOUT)]
    ])
    
    # Remove the keyboard when showing logout confirmation
    await update.message.reply_text(
        "❌ Вы действительно хотите отвязать аккаунт Трейдера от Бота?\n\n"
        "Чтобы подтвердить действие, отправьте логин пользователя в следующем сообщении.",
        reply_markup=ReplyKeyboardRemove()  # Remove the keyboard first
    )
    
    # Then send the inline button in a separate message
    await update.message.reply_text(
        "Для отмены нажмите кнопку ниже:",
        reply_markup=keyboard
    )
    
    return LOGOUT_CONFIRM

# Handle logout confirmation
async def handle_logout_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    entered_username = update.message.text
    correct_username = context.user_data.get("logout_username", "")
    
    # Check current state
    current_state = user_states.get(user_id, LOGOUT_CONFIRM)
    logger.info(f"User {user_id} in state {current_state} entered: {entered_username}")
    
    # If we're not in the logout confirm state, force return to main menu
    if current_state != LOGOUT_CONFIRM:
        logger.warning(f"User {user_id} was in wrong state {current_state}, forcing to MAIN_MENU")
        return await show_main_menu(update, context)
    
    # Check if username matches
    if entered_username == correct_username:
        # Username matches, proceed with logout
        delete_user(user_id)
        
        # Clear user state
        if user_id in user_states:
            del user_states[user_id]
        
        logger.info(f"User {user_id} logged out")
        
        await update.message.reply_text(
            "👋 *Вы вышли из аккаунта*\n\n"
            "Для повторной авторизации используйте команду /start",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardRemove()
        )
        
        return ConversationHandler.END
    else:
        # Username doesn't match, show error
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Отмена", callback_data=CANCEL_LOGOUT)]
        ])
        
        await update.message.reply_text(
            "❌ Неверный логин\n\n"
            "Пожалуйста, введите правильный логин, чтобы удалить связь аккаунта Трейдера с этим Ботом.",
            reply_markup=keyboard
        )
        
        return LOGOUT_CONFIRM

# Handle cancel logout button
async def cancel_logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    # Get platform username from database
    platform_username = get_platform_username(user_id)
    if not platform_username:
        await context.bot.send_message(
            chat_id=user_id,
            text="⚠️ *Сессия истекла*\n\n"
            "Пожалуйста, авторизуйтесь снова, используя команду /start",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    
    # Get notification status from database
    is_notifications_active = get_notification_status(user_id)
    
    logger.info(f"User {user_id} canceled logout")
    
    # Update user state back to profile view
    user_states[user_id] = PROFILE_VIEW
    logger.info(f"User {user_id} is now in PROFILE_VIEW state after canceling logout")
    
    # Create profile keyboard
    keyboard = [
        [BACK_BTN],
        [LOGOUT_BTN]
    ]
    
    reply_markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=False
    )
    
    # Delete the confirmation message with inline button
    try:
        await query.message.delete()
    except Exception as e:
        logger.error(f"Error deleting message: {e}")
    
    # Try to delete the previous message too if possible
    try:
        await context.bot.delete_message(
            chat_id=user_id,
            message_id=query.message.message_id - 1
        )
    except Exception as e:
        logger.error(f"Error deleting previous message: {e}")
    
    # Send the profile view again with keyboard
    await context.bot.send_message(
        chat_id=user_id,
        text=f"👤 *Профиль*\n\n"
             f"Логин: `{platform_username}`\n"
             f"Статус оповещений: {'✅ Включены' if is_notifications_active else '❌ Отключены'}",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    
    return PROFILE_VIEW

# Show information
async def show_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Обновляем состояние
    user_states[user_id] = INFO_VIEW
    logger.info(f"User {user_id} is now in INFO_VIEW state")

    # Загружаем текст из базы / json
    info_data = load_info_text()
    info_text = info_data.get("text", DEFAULT_INFO["text"])

    # Экранируем для HTML
    safe_info = html.escape(info_text)
    safe_support = html.escape(SUPPORT_CONTACT)

    # Кнопки
    keyboard = [[BACK_BTN]]
    if is_admin(user_id):
        keyboard.append(["✏️ Изменить информацию"])

    reply_markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=False
    )

    await update.message.reply_text(
        f"ℹ️ <b>Информация</b>\n\n"
        f"{safe_info}\n\n"
        f"По всем вопросам обращайтесь: {safe_support}",
        parse_mode='HTML',
        reply_markup=reply_markup
    )

    return INFO_VIEW# Handle info view buttons


async def handle_info_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    # Check current state
    current_state = user_states.get(user_id, INFO_VIEW)
    logger.info(f"User {user_id} in state {current_state} pressed: {text}")
    
    # If we're not in the info view state, force return to main menu
    if current_state != INFO_VIEW:
        logger.warning(f"User {user_id} was in wrong state {current_state}, forcing to MAIN_MENU")
        return await show_main_menu(update, context)
    
    if text == BACK_BTN:
        logger.info(f"User {user_id} pressed Back button in info view")
        
        # Update user state
        user_states[user_id] = MAIN_MENU
        
        # Show main menu directly
        return await show_main_menu(update, context)
    elif text == "✏️ Изменить информацию" and is_admin(user_id):
        logger.info(f"Admin {user_id} pressed Edit info button in info view")
        
        # Update user state
        user_states[user_id] = WAITING_INFO_TEXT
        
        # Load current info
        info_data = load_info_text()
        current_text = info_data.get("text", DEFAULT_INFO["text"])
        
        await update.message.reply_text(
            "✏️ *Редактирование информационного блока*\n\n"
            f"Текущий текст:\n\n{current_text}\n\n"
            "Отправьте новый текст для информационного блока или нажмите кнопку Назад для отмены:",
            parse_mode='Markdown'
        )
        
        return WAITING_INFO_TEXT
    else:
        # Unknown command, stay in info view
        return await show_info(update, context)

# Receive new info text
async def receive_info_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    new_text = update.message.text
    
    # Check if user is admin
    if not is_admin(user_id):
        await update.message.reply_text("⛔ У вас нет прав администратора для выполнения этой команды.")
        return ConversationHandler.END
    
    # Check if user wants to cancel
    if new_text == BACK_BTN:
        logger.info(f"Admin {user_id} canceled info editing")
        
        # Update user state
        user_states[user_id] = INFO_VIEW
        
        # Return to info view
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
    user_states[user_id] = INFO_VIEW
    return await show_info(update, context)

# Cancel
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"User {user_id} canceled the conversation")
    
    await update.message.reply_text("❌ Операция отменена.")
    
    # Check if user exists in database
    user = get_user_by_id(user_id)
    if user:
        # Check if user is admin
        if is_admin(user_id):
            # Update user state
            user_states[user_id] = MAIN_MENU
            # Import here to avoid circular imports
            from handlers.admin import show_admin_menu
            return await show_admin_menu(update, context)
        else:
            # Update user state
            user_states[user_id] = MAIN_MENU
            return await show_main_menu(update, context)
    else:
        # Clear user state
        if user_id in user_states:
            del user_states[user_id]
        return ConversationHandler.END

# 👇 This function is called externally (via webhook from the platform) when access is unblocked
async def unlock_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # This can be connected via webhook or scheduler
    user_id = update.message.chat_id
    logger.info(f"Account unlocked for user {user_id}")
    
    # Update user state
    user_states[user_id] = USERNAME
    
    await context.bot.send_message(
        chat_id=user_id, 
        text="🔓 Доступ к аккаунту восстановлен."
    )
    
    await context.bot.send_message(
        chat_id=user_id, 
        text="👤 Введите логин Трейдера:"
    )
    
    return USERNAME

# Function to handle incoming order notifications (called by your API)
async def send_order_notification(bot, user_id, order_data):
    """
    Send notification about new order to the user
    
    :param bot: Bot instance
    :param user_id: Telegram user ID
    :param order_data: Dictionary with order information
    """
    # Check if user exists and has notifications enabled
    if not get_notification_status(user_id):
        logger.info(f"Notification not sent to user {user_id} (notifications disabled)")
        return
    
    # Check if user is banned
    if is_user_banned(user_id):
        logger.info(f"Notification not sent to user {user_id} (user banned)")
        return
    
    order_id = order_data.get("order_id", "Unknown")
    amount = order_data.get("amount", "0")
    currency = order_data.get("currency", "USD")
    
    # Create inline keyboard for the notification
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Детали ордера", callback_data=f"order_{order_id}")]
    ])
    
    message = (
        f"🔔 *Новый ордер!*\n\n"
        f"ID ордера: `{order_id}`\n"
        f"Сумма: *{amount} {currency}*\n\n"
        f"Проверьте детали в личном кабинете."
    )
    
    try:
        await bot.send_message(
            chat_id=user_id, 
            text=message, 
            parse_mode='Markdown',
            reply_markup=keyboard
        )
        logger.info(f"Notification sent to user {user_id} for order {order_id}")
    except Exception as e:
        logger.error(f"Failed to send notification to user {user_id}: {e}")

# Handle order details button
async def order_details_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Extract order ID from callback data
    order_id = query.data.split('_')[1]
    
    # Here you would fetch order details from your API
    # For now, we'll just show a placeholder message
    
    await query.edit_message_text(
        f"📋 *Детали ордера*\n\n"
        f"ID: `{order_id}`\n"
        f"Статус: В обработке\n\n"
        f"Для получения полной информации перейдите в личный кабинет.",
        parse_mode='Markdown'
    )
