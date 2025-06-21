from fastapi import FastAPI, Request
from telegram import Bot
from database import (
    get_user_id_by_platform_username,
    get_order_notification_status,
    get_appeal_notification_status,
)
from handlers.user import send_platform_notification
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

    user = get_user_id_by_platform_username(platform_username)

    if not user:
        logger.warning(f"No user found for platform_username={platform_username}")
        return {"status": "no_user"}

    user_id = user  # предполагается, что user = Telegram ID

    status = data.get("status")

    if status == "order" and not get_order_notification_status(user_id):
        logger.info(f"Order notifications disabled for user {user_id}")
        return {"status": "notifications_off"}

    if status == "appeal" and not get_appeal_notification_status(user_id):
        logger.info(f"Appeal notifications disabled for user {user_id}")
    

        return {"status": "notifications_off"}

    try:
        await send_platform_notification(bot, user_id, data)
        return {"status": "sent"}
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")
        return {"status": "error", "detail": str(e)}
