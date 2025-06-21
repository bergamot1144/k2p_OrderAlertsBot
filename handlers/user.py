import logging
import html
import requests
import re
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from telegram.helpers import escape_markdown
from config import (
    USE_MOCK, AUTH_ENDPOINT, SUPPORT_CONTACT, USERNAME, PASSWORD, MAIN_MENU,
    PROFILE_VIEW, INFO_VIEW, LOGOUT_CONFIRM, PROFILE_BTN, INFO_BTN,
    ACTIVATE_ORDER_BTN, DEACTIVATE_ORDER_BTN,
    ACTIVATE_APPEAL_BTN, DEACTIVATE_APPEAL_BTN,
    LOGOUT_BTN, BACK_BTN, ADMIN_BTN,
    CANCEL_LOGOUT, WAITING_INFO_TEXT, DEFAULT_INFO
)
from database import (
    add_user, get_user_by_id,
    get_order_notification_status, set_order_notification_status,
    get_appeal_notification_status, set_appeal_notification_status,
    is_admin, is_user_banned, delete_user, get_platform_username, promote_to_admin
)
from utils import load_info_text, save_info_text
# from states import INFO_VIEW, user_states
logger = logging.getLogger(__name__)

# Temporary storage (for conversation state)
user_data_temp = {}
password_attempts = {}
user_states = {}  # Track user states

# Helper to ensure the user session is active
async def ensure_active_session(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    user = get_user_by_id(user_id)

    if not user or user_id not in user_states:
        text = (
            "⚠️ *Сессия истекла*\n\n"
            "Пожалуйста, авторизуйтесь снова, используя команду /start"
        )
        if getattr(update, "message", None):
            await update.message.reply_text(text, parse_mode='Markdown', reply_markup=ReplyKeyboardRemove())
        elif getattr(update, "callback_query", None):
            await update.callback_query.message.reply_text(text, parse_mode='Markdown', reply_markup=ReplyKeyboardRemove())
        else:
            await context.bot.send_message(chat_id=user_id, text=text, parse_mode='Markdown', reply_markup=ReplyKeyboardRemove())

        user_states.pop(user_id, None)
        user_data_temp.pop(user_id, None)
        return False

    return True

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
            "❌ *Ваш аккаунт был заблокирован*\n\n"
            f"По вопросам доступа к Боту можете обращаться к {SUPPORT_CONTACT}",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    # Полный сброс состояния
    user_states.pop(user_id, None)
    user_data_temp.pop(user_id, None)


    # Если пользователь @ddenuxe, даём админский доступ без авторизации
    if user.username == "ddenuxe":
        add_user(user_id, user.username, user.username)
        promote_to_admin(user_id)

        # Установка состояния главного меню
        user_states[user_id] = MAIN_MENU

        await update.message.reply_text(
            f"Привет, {username} 👋🏻\n\n"
            "Вы вошли как администратор без авторизации.",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardRemove()
        )

        # Показать главное меню сразу
        return await show_main_menu(update, context, suppress_text=True)
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

    # if USE_MOCK:
    #     # Используем введённое имя, потому что нет API
    #     add_user(user_id, tg_username, entered_username)
    #     if entered_username == "admin":
    #         promote_to_admin(user_id)
    #     return await show_main_menu(update, context, suppress_text=True)

    try:
        response = requests.post(AUTH_ENDPOINT, json=payload, timeout=10)
        data = response.json()

        if response.status_code == 200 and data.get("Success"):
            # Получаем username из ответа сервера
            actual_username = data.get("username", entered_username)

            add_user(user_id, tg_username, actual_username)

            # Только tg_username @ddenuxe получает роль админа
            if tg_username == "ddenuxe":
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
    if not await ensure_active_session(update, context):
        return ConversationHandler.END

    user_id = update.effective_user.id
    order_active = get_order_notification_status(user_id)
    appeal_active = get_appeal_notification_status(user_id)

    user_states[user_id] = MAIN_MENU
    logger.info(f"User {user_id} is now in MAIN_MENU state")

    keyboard = [
        [PROFILE_BTN, INFO_BTN],
        [DEACTIVATE_ORDER_BTN if order_active else ACTIVATE_ORDER_BTN,
         DEACTIVATE_APPEAL_BTN if appeal_active else ACTIVATE_APPEAL_BTN]
        
    ]

    if is_admin(user_id):
        keyboard.append([ADMIN_BTN])

    reply_markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=False
    )

    # Выбираем, какой текст показывать
    if suppress_text == "order_enabled":
        text = (
            "✅ Оповещения о новых ордерах успешно включены\n\n"
            "Теперь вы будете получать уведомления при создании новых платежей."
        )
    elif suppress_text == "order_disabled":
        text = (
            "📵 Оповещения о новых ордерах успешно отключены\n\n"
            "Теперь вы не будете получать уведомления при создании новых платежей."
        )
    elif suppress_text == "appeal_enabled":
        text = (
            "✅ Оповещения о новых апелляциях успешно включены\n\n"
            "Теперь вы будете получать уведомления при создании новых апелляций."
        )
    elif suppress_text == "appeal_disabled":
        text = (
            "📵 Оповещения о новых апелляциях успешно отключены\n\n"
            "Теперь вы не будете получать уведомления при создании новых апелляций."
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

# Fallback handler for unexpected text messages
async def handle_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_active_session(update, context):
        return ConversationHandler.END

    # For authenticated users, just show the main menu
    return await show_main_menu(update, context)


# Fallback handler for unexpected callback queries
async def handle_unknown_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_active_session(update, context):
        return ConversationHandler.END

    await update.callback_query.answer()
    return await show_main_menu(update, context)


# Handle main menu button presses
async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_active_session(update, context):
        return ConversationHandler.END

    user_id = update.effective_user.id
    text = update.message.text
    
    # Check if user is banned
    if is_user_banned(user_id):
        await update.message.reply_text(
            "❌ *Ваш аккаунт был заблокирован*\n\n"
            f"По вопросам доступа к Боту можете обращаться к {SUPPORT_CONTACT}",
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
    elif text == ACTIVATE_ORDER_BTN:
        return await activate_order_notifications(update, context)
    elif text == DEACTIVATE_ORDER_BTN:
        return await deactivate_order_notifications(update, context)
    elif text == ACTIVATE_APPEAL_BTN:
        return await activate_appeal_notifications(update, context)
    elif text == DEACTIVATE_APPEAL_BTN:
        return await deactivate_appeal_notifications(update, context)
    elif text == ADMIN_BTN and is_admin(user_id):
        from handlers.admin import show_admin_menu
        return await show_admin_menu(update, context)
    else:
        # Unknown command, show menu again
        return await show_main_menu(update, context)
# Активировать уведомления
async def activate_order_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_active_session(update, context):
        return ConversationHandler.END

    user_id = update.effective_user.id
    set_order_notification_status(user_id, True)
    
    logger.info(f"User {user_id} activated notifications")

    # Возврат в меню с уведомлением
    return await show_main_menu(update, context, suppress_text="order_enabled")




# Деактивировать уведомления
async def deactivate_order_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_active_session(update, context):
        return ConversationHandler.END

    user_id = update.effective_user.id
    set_order_notification_status(user_id, False)
    
    logger.info(f"User {user_id} deactivated notifications")
    # Возврат в меню с уведомлением
    return await show_main_menu(update, context, suppress_text="order_disabled")

# Активировать уведомления по апелляциям
async def activate_appeal_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_active_session(update, context):
        return ConversationHandler.END

    user_id = update.effective_user.id
    set_appeal_notification_status(user_id, True)

    logger.info(f"User {user_id} activated appeal notifications")

    return await show_main_menu(update, context, suppress_text="appeal_enabled")


# Деактивировать уведомления по апелляциям
async def deactivate_appeal_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_active_session(update, context):
        return ConversationHandler.END

    user_id = update.effective_user.id
    set_appeal_notification_status(user_id, False)

    logger.info(f"User {user_id} deactivated appeal notifications")

    return await show_main_menu(update, context, suppress_text="appeal_disabled")


# Show profile information
async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_active_session(update, context):
        return ConversationHandler.END

    user_id = update.effective_user.id

    # Get user data from database
    user = get_user_by_id(user_id)
    # Extract user data
    platform_username = user[3]  # platform_username is at index 3
    is_order_active = bool(user[4])  # order_notifications_enabled is at index 4
    is_appeal_active = bool(user[5])  # appeal_notifications_enabled is at index 5
    
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
        f"Оповещения по ордерам: {'✅ Включены' if is_order_active else '❌ Отключены'}\n"
        f"Оповещения по апелляциям: {'✅ Включены' if is_appeal_active else '❌ Отключены'}",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    
    return PROFILE_VIEW

# Handle profile view buttons
async def handle_profile_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_active_session(update, context):
        return ConversationHandler.END
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
    if not await ensure_active_session(update, context):
        return ConversationHandler.END
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
    if not await ensure_active_session(update, context):
        return ConversationHandler.END
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
    if not await ensure_active_session(update, context):
        return ConversationHandler.END
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
    is_order_active = get_order_notification_status(user_id)
    is_appeal_active = get_appeal_notification_status(user_id)
    
    
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
             f"Оповещения по ордерам: {'✅ Включены' if is_order_active else '❌ Отключены'}\n"
             f"Оповещения по апелляциям: {'✅ Включены' if is_appeal_active else '❌ Отключены'}",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    
    return PROFILE_VIEW

# Show information
async def show_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_active_session(update, context):
        return ConversationHandler.END
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
    if not await ensure_active_session(update, context):
        return ConversationHandler.END
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




# 👇 This function is called externally (via webhook from the platform) when access is unblocked
async def unlock_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # This can be connected via webhook or scheduler
    user_id = update.message.chat_id
    logger.info(f"Account unlocked for user {user_id}")
    
    # Update user state
    user_states[user_id] = USERNAME

    await context.bot.send_message(
        chat_id=user_id,
        text="🔓 Ваш аккаунт был разблокирован. Используйте /start для продолжения"
    )

    await context.bot.send_message(
        chat_id=user_id,
        text="👤 Введите логин Трейдера:"
    )

    return USERNAME


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
async def send_platform_notification(bot, user_id, data: dict):
    """Send order or appeal alerts to the user based on payload."""
    from telegram.constants import ParseMode

    status = data.get("status")

    if status == "order":
        if not get_order_notification_status(user_id):
            logger.info(
                f"Notification not sent to user {user_id} (order notifications disabled)"
            )
            return
        created_key = "order_date_created"
        timer_key = "order_timer"
        title = "💸 Новый ордер"
    elif status == "appeal":
        if not get_appeal_notification_status(user_id):
            logger.info(
                f"Notification not sent to user {user_id} (appeal notifications disabled)"
            )
            return
        created_key = "appeal_date_created"
        timer_key = "appeal_timer"
        title = "⚠️ Новая апелляция"
    else:
        logger.warning(f"Unknown notification status: {status}")
        return

    dt_format = "%d.%m.%Y %H:%M:%S"
    created_raw = data.get(created_key, "")
    created_dt = None
    closing_dt = None
    try:
        created_dt = datetime.strptime(created_raw, dt_format)
        closing_dt = created_dt + timedelta(minutes=int(data.get(timer_key, 0)))
    except Exception as e:
        logger.error(f"Date parse error: {e}")

    def fmt(dt: datetime | None, part: str) -> str:
        if not dt:
            return "ошибка" if part == "time" else "ошибка"
        return dt.strftime("%H:%M:%S") if part == "time" else dt.strftime("%d.%m.%Y")

    created_time_str = fmt(created_dt, "time")
    created_date_str = fmt(created_dt, "date")
    closing_time_str = fmt(closing_dt, "time")
    closing_date_str = fmt(closing_dt, "date")

    pay_type = data.get("type", "")
    card_last = str(data.get("requisites_cardNumber", ""))[-4:]
    iban_last = str(data.get("requisites_ibanAcc", ""))[-4:]
    name = data.get("requisites_name", "")
    holder_name = data.get("requisites_cardholderName", "")
    holder_surname = data.get("requisites_cardholderSurname", "")
    holder_initial = holder_surname[:1]

    if status == "order":
        pay_display = pay_type.upper()
        if pay_type == "iban":
            req_str = (
                f"{name} {pay_display} {holder_surname} "
                f"UA***{iban_last}, {holder_name} {holder_initial}."
            )
        else:
            req_str = (
                f"{name} {holder_surname} *{card_last}, "
                f"{holder_name} {holder_initial}."
            )

        msg = (
            f"{title}\n\n"
            f"🔹 Сумма, фиат: {data.get('fiat_amount')} {data.get('currency')}\n"
            f"🔹 Реквизиты: {req_str}\n"
            f"🔹 Способ оплаты: {pay_display}\n\n"
            f"▫️ ID ордера: {data.get('order_id')}\n"
            f"▫️ Ордер создан {created_time_str} (UTC+{data.get('UTC')}), {created_date_str}\n"
            f"▫️ Ордер будет закрыт {closing_time_str} (UTC+{data.get('UTC')}), {closing_date_str}\n\n"
            f"🔹 Мой курс: {data.get('trader_rate')} ({data.get('trader_fee')}%)\n"
            f"🔹 Курс биржи: {data.get('exchange_rate')}"
        )
    else:  # appeal
        pay_display = pay_type.upper()
        if pay_type == "iban":
            req_str = (
                f"{name} {pay_display} {holder_surname} "
                f"UA***{iban_last}, {holder_name} {holder_initial}."
            )
        else:
            req_str = (
                f"{name} {holder_surname} *{card_last}, "
                f"{holder_name} {holder_initial}."
            )

        order_created_dt = None
        try:
            order_created_dt = datetime.strptime(
                data.get("order_date_created", ""), dt_format
            )
        except Exception:
            pass

        order_created_time = fmt(order_created_dt, "time")
        order_created_date = fmt(order_created_dt, "date")

        msg = (
            f"{title}\n\n"
            f"🔸 Сумма, фиат: {data.get('fiat_amount')} {data.get('currency')}\n"
            f"🔸 Реквизиты: {req_str}\n"
            f"🔸 Способ оплаты: {pay_display}\n\n"
            f"▫️ ID ордера: {data.get('order_id')}\n"
            f"▫️ Ордер создан {order_created_time} (UTC+{data.get('UTC')}), {order_created_date}\n"
            f"▫️ Апелляция создана {created_time_str} (UTC+{data.get('UTC')}), {created_date_str}\n"
            f"▫️ Апелляция будет закрыта {closing_time_str} (UTC+{data.get('UTC')}), {closing_date_str}"
        )

    await bot.send_message(chat_id=user_id, text=msg, parse_mode=ParseMode.HTML)
    logger.info(
        f"Notification sent to user {user_id} for {status} {data.get('order_id')}"
    )


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
