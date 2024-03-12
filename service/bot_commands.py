import re

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from config.settings import DB_CONFIG, USER_SUBSCRIPTION_LIMIT
from db.database_manager import *
from nam_lib.result import *

logger = logging.getLogger(__name__)


def check_address_format(address: str):
    if len(address) > 45:
        return Result(
            success=False,
            error="Address length exceeds the maximum allowed. Please provide a valid Tendermint or Namada address."
        )

    # Defining patterns for address validation
    namada_pattern = re.compile(r'^tnam[0-9a-zA-Z]{41}$')
    tendermint_pattern = re.compile(r'^[0-9A-F]{40}$')

    # Checking if the address matches Namada pattern
    if namada_pattern.match(address):
        return Result(True, "Namada")
    # Checking if the address matches Tendermint pattern
    elif tendermint_pattern.match(address):
        return Result(True, "Tendermint")
    else:
        return Result(
            success=False,
            error="The provided address does not match the expected formats for Namada or Tendermint addresses."
        )


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.edited_message if update.edited_message else update.message
    if update.effective_chat.type == 'group':
        user_status = await context.bot.get_chat_member(chat_id=update.effective_chat.id,
                                                        user_id=update.effective_user.id)
        if user_status.status not in ('administrator', 'creator'):
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                           text="Sorry, only group admins can query this bot.")
            return
    welcome_msg = """
    Hello👋 <b>Welcome to Namada Validator Bot</b>.

    <b>Commands:</b>
    - <code>/status [address]</code>: Check a validator's current status.
    
    - <code>/monitor [address]</code>: Start monitoring a validator. Notifies on state and fee change. Max 5.
    
    - <code>/view </code>: View status of monitored validators.
    
    - <code>/stop [address|all]</code>: Stop monitoring a validator. Use 'all' to stop all.

    Replace [address] with the validator's address. Use without brackets. You can use tendermint address or namada address.
        """
    await message.reply_text(welcome_msg, parse_mode='HTML')


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.edited_message if update.edited_message else update.message
    user_input = context.args
    if not user_input:
        await message.reply_text("❌ Please provide an address.")
        return

    address = user_input[0].replace(" ", "")
    check_result = check_address_format(address)
    if not check_result.success:
        await message.reply_text("❌ " + check_result.error)
        return

    if check_result.data == 'Namada':
        query_column = "validator_address"
    else:
        query_column = "tendermint_address"

    query_sql = f"SELECT validator_address, tendermint_address, voting_power, state, commission_rate, email, website, discord_handle FROM validators WHERE {query_column} = %s"
    db_manager = DatabaseManager(DB_CONFIG)

    try:
        validator_info = db_manager.execute_query(query_sql, (address,), commit=False)
    except Exception as e:
        logger.error(f"Failed to query validator info: {e}")
        await message.reply_text("❌ An error occurred while fetching the validator info. Please try again.")
        return

    if validator_info:
        info = validator_info[0]
        reply_msg = (f"🌟 <b>Validator Info</b> 🌟\n\n"
                     f"🔹 <b>Address:</b> {info['validator_address']}\n"
                     f"🔹 <b>TM Address:</b> {info['tendermint_address']}\n"
                     f"🔹 <b>Voting Power:</b> {info['voting_power']}\n"
                     f"🔹 <b>State:</b> {info['state']}\n"
                     f"🔹 <b>Commission Rate:</b> {info['commission_rate']}\n"
                     f"🔹 <b>Email:</b> {info['email']}\n")

        if info.get('website'):
            reply_msg += f"🔹 <b>Website:</b> <a href='{info['website']}'>{info['website']}</a>\n"
        if info.get('discord_handle'):
            reply_msg += f"🔹 <b>Discord:</b> {info['discord_handle']}\n"
    else:
        reply_msg = "❌ No Consensus validator found with the provided address."

    await message.reply_text(reply_msg, parse_mode='HTML', disable_web_page_preview=True)


async def monitor_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.edited_message if update.edited_message else update.message

    user_input = context.args
    if not user_input:
        await message.reply_text("❌ Please provide an address.")
        return

    address = user_input[0].replace(" ", "")
    check_result = check_address_format(address)
    if not check_result.success:
        await message.reply_text("❌ " + check_result.error)
        return

    db_manager = DatabaseManager(DB_CONFIG)

    try:
        validator_id = ensure_validator_exists(db_manager, address, check_result.data)

        if validator_id is None:
            await message.reply_text("❌ No Consensus validator found with the provided address.")
            return

        user_id = ensure_user_exists(db_manager, update.effective_user.id, update.effective_user.username)
        if not check_subscription_limit(db_manager, user_id):
            await message.reply_text(
                "❌ You've reached the maximum number of subscriptions (4). Please stop monitoring a validator to add a new one.")
            return

        if create_subscription(db_manager, user_id, validator_id):
            await message.reply_text("✅ You're now monitoring the validator.")
        else:
            await message.reply_text("🔔 You're already monitoring this validator.")
    except Exception as e:
        logger.error(f"Failed to monitor validator: {e}")
        await message.reply_text("❌ An error occurred. Please try again.")


async def view_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.edited_message if update.edited_message else update.message

    db_manager = DatabaseManager(DB_CONFIG)
    user_id = ensure_user_exists(db_manager, update.effective_user.id, update.effective_user.username)

    query = """
    SELECT v.validator_address, v.tendermint_address, v.state, v.commission_rate, v.website, v.email, v.discord_handle, v.voting_power 
    FROM subscriptions s
    JOIN validators v ON s.validator_id = v.validator_id
    WHERE s.user_id = %s
    ORDER BY s.created_at DESC
    """
    try:
        subscriptions = db_manager.execute_query(query, (user_id,))
    except Exception as e:
        logger.error(f"Failed to fetch subscription data: {e}")
        await message.reply_text("❌ An error occurred while fetching your subscriptions. Please try again later.")
        return

    if not subscriptions:
        await message.reply_text("❌ You are not monitoring any validators.")
        return

    reply_msg = "<b>🔎 Your Monitored Validators</b>\n\n"
    for sub in subscriptions:
        reply_msg += "─────────────────────────────────\n"
        reply_msg += (
            f"🔹 <b>Address:</b> {sub['validator_address']}\n"
            f"🔹 <b>TM Address:</b> {sub['tendermint_address']}\n"
            f"🔹 <b>State:</b> {sub['state']}\n"
            f"🔹 <b>Voting Power:</b> {sub['voting_power']}\n"
            f"🔹 <b>Commission Rate:</b> {sub['commission_rate']}\n"
            f"🔹 <b>Email:</b> {sub['email']}\n"
        )

        if sub.get('discord_handle'):
            reply_msg += f"🔹 <b>Discord:</b> {sub['discord_handle']}\n"
        if sub.get('website'):
            reply_msg += f"🔹 <b>Website:</b> <a href='{sub['website']}'>{sub['website']}</a>\n"

    reply_msg = reply_msg.rstrip('\n')
    await message.reply_text(reply_msg, parse_mode='HTML', disable_web_page_preview=True)


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message or update.edited_message
    if message is None:
        logger.error("Message object is None. This operation is not supported on edited messages.")
        return

    user_input = context.args
    if not user_input:
        await message.reply_text("❌ Please provide an address or 'all' to stop monitoring.")
        return

    db_manager = DatabaseManager(DB_CONFIG)
    telegram_user_id = update.effective_user.id
    user_id = ensure_user_exists(db_manager, telegram_user_id, update.effective_user.username)

    if user_input[0].lower() == "all":
        try:
            db_manager.delete_data('subscriptions', {'user_id': user_id})
            await update.message.reply_text("✅ Stopped monitoring all validators.")
        except Exception as e:
            logger.error(f"Failed to stop monitoring all validators: {e}")
            await update.message.reply_text("❌ An error occurred. Please try again.")
    else:
        address = user_input[0].replace(" ", "")
        check_result = check_address_format(address)
        if not check_result.success:
            await update.message.reply_text("❌ " + check_result.error)
            return

        validator_id = ensure_validator_exists(db_manager, address, check_result.data)
        if validator_id is None:
            await update.message.reply_text("❌ No Consensus validator found with the provided address.")
            return

        # Attempt to delete the specific subscription
        try:
            subscription_exists = db_manager.execute_query(
                "SELECT id FROM subscriptions WHERE user_id = %s AND validator_id = %s",
                (user_id, validator_id),
                commit=False
            )
            if subscription_exists:
                db_manager.delete_data('subscriptions', {'user_id': user_id, 'validator_id': validator_id})
                await update.message.reply_text("✅ Stopped monitoring the validator.")
            else:
                await update.message.reply_text("🔔 You are not monitoring this validator.")
        except Exception as e:
            logger.error(f"Failed to stop monitoring validator: {e}")
            await update.message.reply_text("❌ An error occurred. Please try again.")


def ensure_validator_exists(db_manager, address, address_type):
    query_column = "validator_address" if address_type == 'Namada' else "tendermint_address"
    query_sql = f"SELECT validator_id FROM validators WHERE {query_column} = %s"
    validator_info = db_manager.execute_query(query_sql, (address,))
    return validator_info[0]['validator_id'] if validator_info else None


def ensure_user_exists(db_manager, telegram_id, telegram_name):
    user_query_sql = "SELECT user_id FROM users WHERE telegram_id = %s"
    # Attempt to fetch the existing user by telegram_id
    user_info = db_manager.execute_query(user_query_sql, (str(telegram_id),))

    if user_info:
        # User already exists, return the existing user_id
        return user_info[0]['user_id']
    else:
        # User does not exist, insert new user and return the new user_id
        user_data = {'telegram_id': str(telegram_id), 'telegram_name': telegram_name or ''}
        new_user_id = db_manager.insert_data_and_get_id('users', user_data)
        return new_user_id


def check_subscription_limit(db_manager, user_id, limit=USER_SUBSCRIPTION_LIMIT):
    subscription_count_query = "SELECT COUNT(*) as count FROM subscriptions WHERE user_id = %s"

    count_result = db_manager.execute_query(subscription_count_query, (user_id,))
    if count_result and count_result[0]['count'] >= limit:
        return False
    return True


def create_subscription(db_manager, user_id, validator_id):
    subscription_exists = db_manager.execute_query(
        "SELECT id FROM subscriptions WHERE user_id = %s AND validator_id = %s", (user_id, validator_id))
    if not subscription_exists:
        db_manager.insert_data('subscriptions', {'user_id': user_id, 'validator_id': validator_id})
        return True
    return False


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.warning(f"Update {update} caused error {context.error}")


def setup_handlers(application):
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("monitor", monitor_command))
    application.add_handler(CommandHandler("view", view_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_error_handler(error_handler)




