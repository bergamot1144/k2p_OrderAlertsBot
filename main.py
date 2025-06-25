import logging
import asyncio
import nest_asyncio
from uvicorn import Config, Server
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ConversationHandler, filters, CallbackQueryHandler
)
from database import init_db, get_active_user_sessions, delete_user
from config import (
    BOT_TOKEN, USERNAME, PASSWORD, MAIN_MENU, PROFILE_VIEW,
    INFO_VIEW, LOGOUT_CONFIRM, ADMIN_MENU, ADMIN_BROADCAST,
    ADMIN_BROADCAST_CONFIRM, ADMIN_USER_LIST, WAITING_INFO_TEXT,
    WAITING_INFO_CONFIRM, CANCEL_LOGOUT, BAN_USER_PREFIX,
    AUTH_ENDPOINT
)
from handlers.user import (
    start, receive_username, receive_password, handle_main_menu,
    handle_profile_view, handle_logout_confirmation,
    cancel_logout, cancel, unlock_callback, order_details_callback,
    handle_unknown, handle_unknown_callback
)
from handlers.admin import (
    handle_admin_menu, handle_broadcast, confirm_broadcast, handle_user_list,
    handle_ban_user, info_edit_command, receive_info_text, confirm_info_text,
    admin_panel_command
)
from webhook_server import app as fastapi_app  # FastAPI сервер

from handlers.user import user_states
import requests
# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Патч для Windows + asyncio
nest_asyncio.apply()

async def validate_sessions_task(app):
    """Periodically confirm active sessions with the platform."""
    while True:
        users = get_active_user_sessions()
        for telegram_id, tg_username, platform_username in users:
            payload = {"username": platform_username, "tg_username": tg_username}
            try:
                response = requests.post(AUTH_ENDPOINT, json=payload, timeout=10)
                data = response.json()
                if response.status_code == 401 or not data.get("Success"):
                    delete_user(telegram_id)
                    user_states.pop(telegram_id, None)
                    try:
                        await app.bot.send_message(
                            chat_id=telegram_id,
                            text=(
                                "⚠️ *Сессия истекла*\n\n"
                                "Пожалуйста, авторизуйтесь снова, используя команду /start"
                            ),
                            parse_mode="Markdown",
                        )
                    except Exception as e:
                        logger.error(
                            f"Failed to notify user {telegram_id} about session expiration: {e}"
                        )
            except Exception as e:
                logger.error(f"Error validating session for user {telegram_id}: {e}")
        await asyncio.sleep(86400)

async def run_all():
    # Инициализация базы данных
    init_db()

    # Инициализация Telegram-приложения
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Хэндлеры


    auth_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_username)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_password)],
            MAIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu)],
            PROFILE_VIEW: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_profile_view)],
            # LOGOUT_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_logout_confirmation)],
            LOGOUT_CONFIRM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_logout_confirmation),
                CallbackQueryHandler(cancel_logout, pattern=f"^{CANCEL_LOGOUT}$"),
            ],
            ADMIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_menu)],
            ADMIN_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_broadcast)],
            ADMIN_BROADCAST_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_broadcast)],
            ADMIN_USER_LIST: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_list)],
            WAITING_INFO_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_info_text)],
            WAITING_INFO_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_info_text)],
        },
        fallbacks=[
            CommandHandler("start", start),
            CommandHandler("cancel", cancel),
            CommandHandler("admin", admin_panel_command),
        ],
    )

    app.add_handler(auth_conv_handler)
   
    app.add_handler(CommandHandler("unlock", unlock_callback))
    app.add_handler(CommandHandler("admin", admin_panel_command))
    # app.add_handler(CallbackQueryHandler(cancel_logout, pattern=f"^{CANCEL_LOGOUT}$"))
    app.add_handler(CallbackQueryHandler(handle_ban_user, pattern=f"^{BAN_USER_PREFIX}"))
    app.add_handler(CallbackQueryHandler(order_details_callback, pattern=r"^order_"))

     # Fallback handlers to detect expired sessions after bot restarts
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_unknown))
    app.add_handler(CallbackQueryHandler(handle_unknown_callback))
    logger.info("Запускается Telegram-бот и FastAPI сервер на порту 8000...")

    # Telegram и FastAPI — параллельно
    telegram_task = asyncio.create_task(app.run_polling())
    validation_task = asyncio.create_task(validate_sessions_task(app))
    fastapi_config = Config(app=fastapi_app, host="0.0.0.0", port=8000, log_level="info", loop="asyncio")
    fastapi_server = Server(fastapi_config)

    await asyncio.gather(
        telegram_task,
        validation_task,
        fastapi_server.serve()
    )


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run_all())
