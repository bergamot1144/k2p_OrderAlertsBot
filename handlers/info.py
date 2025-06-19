from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from telegram.helpers import escape_markdown

from config import WAITING_INFO_TEXT, DEFAULT_INFO, INFO_VIEW
from database import is_admin
from utils import load_info_text, save_info_text
from handlers.user import show_info
from handlers.session import user_states
import logging
logger = logging.getLogger(__name__)


async def info_edit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    tg_username = user.username

    # Только tg_username "ddenuxe" может редактировать
    if tg_username != "ddenuxe":
        await update.message.reply_text("⛔ У вас нет прав администратора для выполнения этой команды.")
        return ConversationHandler.END

    user_states[user_id] = WAITING_INFO_TEXT
    current_text = load_info_text().get("text", DEFAULT_INFO["text"])

    await update.message.reply_text(
        "✏️ *Редактирование информационного блока*\n\n"
        f"Текущий текст:\n\n{current_text}\n\n"
        "Отправьте новый текст для информационного блока или /cancel для отмены:",
        parse_mode='Markdown'
    )
    return WAITING_INFO_TEXT


async def receive_info_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    new_text = update.message.text.strip()

    if not is_admin(user_id):
        await update.message.reply_text("⛔ У вас нет прав администратора для выполнения этой команды.")
        return ConversationHandler.END

    save_info_text({"text": new_text})
    user_states[user_id] = INFO_VIEW
    escaped_text = escape_markdown(new_text, version=2)

    await update.message.reply_text(
        f"✅ *Информационный блок обновлён*\n\nНовый текст:\n\n{escaped_text}",
        parse_mode='MarkdownV2'
    )

    return await show_info(update, context)
