import logging
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    ConversationHandler, filters, CallbackQueryHandler
)
from database import init_db, add_test_users
from config import (
    BOT_TOKEN, USERNAME, PASSWORD, MAIN_MENU, PROFILE_VIEW, 
    INFO_VIEW, LOGOUT_CONFIRM, ADMIN_MENU, ADMIN_BROADCAST, 
    ADMIN_USER_LIST, WAITING_INFO_TEXT, CANCEL_LOGOUT, BAN_USER_PREFIX
)
# from database import init_db, add_test_users
from handlers.user import (
    start, receive_username, receive_password, handle_main_menu, 
    handle_profile_view, handle_info_view, handle_logout_confirmation, 
    cancel_logout, cancel, unlock_callback, order_details_callback
)
from handlers.admin import (
    handle_admin_menu, handle_broadcast, handle_user_list, 
    handle_ban_user, info_edit_command, receive_info_text
)
from handlers.admin_commands import (
    add_user_command, delete_user_command, make_admin_command, 
    list_users_command, admin_help_command
)

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    # Initialize database
    init_db()
    
    # Add test users (uncomment to add test users)
    add_test_users()
    
    # Create the Application
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Add conversation handler for authentication
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
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    # Add conversation handler for info editing
    info_edit_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("infoedit", info_edit_command)],
        states={
            WAITING_INFO_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_info_text)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    # Add handlers
    app.add_handler(auth_conv_handler)
    app.add_handler(CommandHandler("infoedit", info_edit_command))
    app.add_handler(CommandHandler("unlock", unlock_callback))
    
    # Add admin command handlers
    app.add_handler(CommandHandler("adduser", add_user_command))
    app.add_handler(CommandHandler("deleteuser", delete_user_command))
    app.add_handler(CommandHandler("makeadmin", make_admin_command))
    app.add_handler(CommandHandler("listusers", list_users_command))
    app.add_handler(CommandHandler("adminhelp", admin_help_command))
    
    # Add callback query handlers
    app.add_handler(CallbackQueryHandler(cancel_logout, pattern=f"^{CANCEL_LOGOUT}$"))
    app.add_handler(CallbackQueryHandler(handle_ban_user, pattern=f"^{BAN_USER_PREFIX}"))
    app.add_handler(CallbackQueryHandler(order_details_callback, pattern=r"^order_"))
    
    # Start the Bot
    logger.info("Bot started...")
    app.run_polling()



if __name__ == '__main__':
    main()
