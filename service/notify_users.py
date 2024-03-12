import asyncio
import logging

from telegram import Bot

from config.settings import DB_CONFIG, TELEGRAM_BOT_TOKEN
from db.database_manager import DatabaseManager

logger = logging.getLogger(__name__)

bot = Bot(token=TELEGRAM_BOT_TOKEN)
db_manager = DatabaseManager(DB_CONFIG)


async def run_in_executor(func, *args, **kwargs):
    """Run synchronous functions in the default Executor (thread pool) to make them compatible with asynchronous calls"""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: func(*args, **kwargs))


async def send_telegram_message(chat_id, text, parse_mode='HTML', retries=3, delay=5):
    for attempt in range(retries):
        try:
            await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
            return True
        except Exception as e:
            logger.error(f"Attempt {attempt + 1}: Error sending message to {chat_id}, retrying in {delay} seconds...")
            await asyncio.sleep(delay)
    return False


async def get_subscribers(validator_id):
    query = """
    SELECT u.telegram_id
    FROM subscriptions s
    JOIN users u ON s.user_id = u.user_id
    WHERE s.validator_id = %s
    """
    # Adapting synchronous database operations to an asynchronous environment
    return await run_in_executor(db_manager.execute_query, query, (validator_id,))


async def update_notifications_sent(table_name, change_id):
    await run_in_executor(db_manager.update_data, table_name, {'notifications_sent': 1}, {'change_id': change_id})


async def notify_state_changes():
    query = """
    SELECT sc.*, v.validator_address, v.tendermint_address, v.validator_id
    FROM validator_state_changes sc
    JOIN validators v ON sc.validator_id = v.validator_id
    WHERE sc.notifications_sent = 0
    """
    changes = await run_in_executor(db_manager.execute_query, query)
    for change in changes:
        subscribers = await get_subscribers(change['validator_id'])
        all_sent = True
        if not subscribers:
            logger.info(f"No subscribers for validator {change['validator_id']}, no messages sent.")
        else:
            message = format_state_change_message(change['validator_address'], change['tendermint_address'],
                                                  change['previous_state'], change['new_state'], change['change_id'],
                                                  change['change_timestamp'].strftime("%Y-%m-%d %H:%M:%S"))
            for subscriber in subscribers:
                if not await send_telegram_message(subscriber['telegram_id'], message):
                    all_sent = False
                    break
        if all_sent:
            await update_notifications_sent('validator_state_changes', change['change_id'])


async def notify_commission_changes():
    query = """
    SELECT cc.*, v.validator_address, v.tendermint_address, v.validator_id
    FROM commission_rate_changes cc
    JOIN validators v ON cc.validator_id = v.validator_id
    WHERE cc.notifications_sent = 0
    """
    changes = await run_in_executor(db_manager.execute_query, query)
    for change in changes:
        subscribers = await get_subscribers(change['validator_id'])
        all_sent = True
        if not subscribers:
            logger.info(f"No subscribers for validator {change['validator_id']}, no messages sent.")
        else:
            message = format_commission_change_message(change['validator_address'], change['tendermint_address'],
                                                       change['previous_rate'], change['new_rate'], change['change_id'],
                                                       change['change_timestamp'].strftime("%Y-%m-%d %H:%M:%S"))
            for subscriber in subscribers:
                if not await send_telegram_message(subscriber['telegram_id'], message, parse_mode='HTML'):
                    all_sent = False
                    break
        if all_sent:
            await update_notifications_sent('commission_rate_changes', change['change_id'])


def format_state_change_message(validator_address, tendermint_address, previous_state, new_state, change_id,
                                change_timestamp):
    """Format the message for state change notifications using HTML."""
    return (f"🔔 <b>Validator State Change Alert</b>\n\n"
            f"🆔 Change ID: {change_id}\n"
            f"🔹 Address: <code>{validator_address}</code>\n"
            f"🔹 TM Address: <code>{tendermint_address}</code>\n"
            f"🔹 State Change: <b>⚠️{previous_state} ➔ {new_state}⚠️</b>\n"
            f"🔹 Detected At: 🕒{change_timestamp}\n\n"
            f"Please ignore this message if you have received it before.\n"
            f"Stay tuned for more updates.")


def format_commission_change_message(validator_address, tendermint_address, previous_rate, new_rate, change_id,
                                     change_timestamp):
    """Format the message for commission rate change notifications using HTML."""
    return (f"🔔 <b>Validator Commission Change Alert</b>\n\n"
            f"🆔 Change ID: {change_id}\n"
            f"🔹 Address: <code>{validator_address}</code>\n"
            f"🔹 TM Address: <code>{tendermint_address}</code>\n"
            f"🔹 Commission Rate: <b>⚠️{previous_rate}% ➔ {new_rate}⚠️</b>\n"
            f"🔹 Detected At: 🕒{change_timestamp}\n\n"
            f"Please ignore this message if you have received it before.\n"
            f"Keep an eye on your validators' performance.")


async def notify_users():
    await notify_state_changes()
    await notify_commission_changes()
