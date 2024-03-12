import asyncio
import logging
from telegram.ext import Application
from config.settings import TELEGRAM_BOT_TOKEN, UPDATE_INTERVAL, NOTIFY_INTERVAL
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from service.notify_users import notify_users
from service.update_database import update_database
from service.init_database import init_database
from service.bot_commands import setup_handlers

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)


async def schedule_jobs():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(update_database, "interval", minutes=UPDATE_INTERVAL)
    scheduler.add_job(notify_users, "interval", minutes=NOTIFY_INTERVAL)
    scheduler.start()


def main():
    loop = asyncio.get_event_loop()
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    setup_handlers(application)
    loop.run_until_complete(schedule_jobs())
    application.run_polling()


if __name__ == "__main__":
    init_database()
    main()
