import logging
import asyncio
import nest_asyncio
from uvicorn import Config, Server
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ConversationHandler, filters, CallbackQueryHandler
)
from database import init_db
from config import (
    BOT_TOKEN, USERNAME, PASSWORD, MAIN_MENU, PROFILE_VIEW,
    INFO_VIEW, LOGOUT_CONFIRM, ADMIN_MENU, ADMIN_BROADCAST,
    ADMIN_USER_LIST, WAITING_INFO_TEXT, CANCEL_LOGOUT, BAN_USER_PREFIX
)
from handlers.user import (
    start, receive_username, receive_password, handle_main_menu,
    handle_profile_view, handle_info_view, handle_logout_confirmation,
    cancel_logout, cancel, unlock_callback, order_details_callback
)
from handlers.admin import (
    handle_admin_menu, handle_broadcast, handle_user_list,
    handle_ban_user, info_edit_command, receive_info_text
)
from webhook_server import app as fastapi_app  # FastAPI сервер

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Патч для Windows + asyncio
nest_asyncio.apply()


async def run_all():
    # Инициализация базы данных
    init_db()

    # Инициализация Telegram-приложения
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Хэндлеры
    info_edit_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("infoedit", info_edit_command)],
        states={
            WAITING_INFO_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_info_text)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    auth_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_username)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_password)],
            MAIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu)],
            PROFILE_VIEW: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_profile_view)],
            INFO_VIEW: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_info_view)],
            LOGOUT_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_logout_confirmation)],
            ADMIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_menu)],
            ADMIN_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_broadcast)],
            ADMIN_USER_LIST: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_list)],
            WAITING_INFO_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_info_text)],
        },
        fallbacks=[CommandHandler("start", start), CommandHandler("cancel", cancel)],
    )

    app.add_handler(auth_conv_handler)
    app.add_handler(info_edit_conv_handler)
    app.add_handler(CommandHandler("unlock", unlock_callback))
    app.add_handler(CallbackQueryHandler(cancel_logout, pattern=f"^{CANCEL_LOGOUT}$"))
    app.add_handler(CallbackQueryHandler(handle_ban_user, pattern=f"^{BAN_USER_PREFIX}"))
    app.add_handler(CallbackQueryHandler(order_details_callback, pattern=r"^order_"))

    logger.info("Запускается Telegram-бот и FastAPI сервер на порту 8000...")

    # Telegram и FastAPI — параллельно
    telegram_task = asyncio.create_task(app.run_polling())

    fastapi_config = Config(app=fastapi_app, host="0.0.0.0", port=8000, log_level="info", loop="asyncio")
    fastapi_server = Server(fastapi_config)

    await asyncio.gather(
        telegram_task,
        fastapi_server.serve()
    )


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run_all())
