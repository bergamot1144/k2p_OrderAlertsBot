from fastapi import FastAPI, Request
from telegram import Bot
from database import (
    get_user_ids_by_platform_username,
    get_order_notification_status,
    get_appeal_notification_status,
    is_user_authorized,
)
from handlers.user import send_platform_notification, notify_account_unfrozen
import os
import logging
from config import BOT_TOKEN as API_TOKEN

bot = Bot(token=API_TOKEN)

app = FastAPI()
logger = logging.getLogger(__name__)

@app.get("/")
async def root():
    return {"status": "FastAPI запущен"}

@app.post("/new_order")
async def new_order(request: Request):
    data = await request.json()

    platform_username = data.get("username")  # username трейдера на платформе

    users = get_user_ids_by_platform_username(platform_username)

    if not users:
        logger.warning(f"No user found for platform_username={platform_username}")
        return {"status": "no_user"}

    status = data.get("status")

    sent_any = False
    send_error = None
    for user_id in users:
        if not is_user_authorized(user_id):
            logger.warning(f"User {user_id} is not authorized to receive notifications")
            continue

        if status == "order" and not get_order_notification_status(user_id):
            logger.info(f"Order notifications disabled for user {user_id}")
            continue

        if status == "appeal" and not get_appeal_notification_status(user_id):
            logger.info(f"Appeal notifications disabled for user {user_id}")
            continue

        try:
            await send_platform_notification(bot, user_id, data)
            sent_any = True
        except Exception as e:
            logger.error(f"Failed to send notification to {user_id}: {e}")
            send_error = str(e)

    if sent_any:
        return {"status": "sent"}
    if send_error is not None:
        return {"status": "error", "detail": send_error}

    return {"status": "notifications_off"}


@app.post("/auth_status")
async def auth_status(request: Request):
    """Endpoint to handle account authentication freeze updates."""
    data = await request.json()
    username = data.get("username")
    freeze = str(data.get("authentication_freeze")).lower()
    if username is None:
        return {"status": "no_username"}

    if freeze == "false":
        users = get_user_ids_by_platform_username(username)
        if not users:
            logger.warning(f"No user found for platform_username={username}")
            return {"status": "no_user"}

        for user_id in users:
            await notify_account_unfrozen(bot, user_id)

        return {"status": "unfrozen_notified"}

    return {"status": "ignored"}
