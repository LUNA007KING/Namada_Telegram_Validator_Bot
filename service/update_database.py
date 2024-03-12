import logging
from config.settings import DB_CONFIG, NAMADA_RPC_URL
from db.database_manager import DatabaseManager
from nam_lib.namada_api import NamadaAPI

logger = logging.getLogger(__name__)

namada_api = NamadaAPI(NAMADA_RPC_URL)
db_manager = DatabaseManager(DB_CONFIG)


def update_database():
    logger.info("Starting to update database with Namada Validator Info...")

    # Fetch latest block height
    height_result = namada_api.get_latest_height()
    if not height_result.success:
        logger.error(f"Failed to get latest block height: {height_result.error}")
        return
    latest_height = height_result.data
    logger.info(f"Latest block height: {latest_height}.")

    validators_result = namada_api.get_validators(latest_height)
    if not validators_result.success:
        logger.error(f"Failed to get validators: {validators_result.error}")
        return

    for tm_addr, voting_power in validators_result.data:
        validator_info = fetch_validator_info(tm_addr)
        if not validator_info:
            continue

        validator_address, metadata, commission_rate, max_commission_change, state = validator_info

        existing_validator = db_manager.execute_query(
            "SELECT validator_id, state, commission_rate FROM validators WHERE tendermint_address = %s",
            (tm_addr,),
            commit=False
        )

        data = {
            'validator_address': validator_address,
            'tendermint_address': tm_addr,
            'voting_power': voting_power,
            'email': metadata.get('email', ''),
            'description': metadata.get('description', ''),
            'website': metadata.get('website', ''),
            'discord_handle': metadata.get('discord_handle', ''),
            'avatar': metadata.get('avatar', ''),
            'commission_rate': commission_rate,
            'max_commission_change': max_commission_change,
            'state': state
        }

        if existing_validator:
            validator_id = existing_validator[0]['validator_id']
            previous_state = existing_validator[0]['state']
            previous_rate = existing_validator[0]['commission_rate']
            db_manager.update_data('validators', data, {'validator_id': validator_id})
            record_changes(validator_id, previous_state, state, previous_rate, commission_rate)
        else:
            db_manager.insert_data('validators', data)
        logger.info(
            f"Validator data for {tm_addr} has been {'updated' if existing_validator else 'inserted'} successfully.")


def fetch_validator_info(tm_addr):
    tm_result = namada_api.get_validator_from_tm(tm_addr)
    if not tm_result.success:
        logger.error(f"Error parsing {tm_addr}: {tm_result.error}")
        return None

    validator_address = tm_result.data
    metadata_result = namada_api.get_validator_metadata(validator_address)
    commission_result = namada_api.get_validator_commission(validator_address)
    state_result = namada_api.get_validator_state(validator_address)

    if not (metadata_result.success and commission_result.success and state_result.success):
        log_error_details(validator_address, metadata_result, commission_result, state_result)
        return None

    commission_rate, max_commission_change = commission_result.data
    return validator_address, metadata_result.data, commission_rate, max_commission_change, state_result.data


def log_error_details(validator_address, metadata_result, commission_result, state_result):
    if not metadata_result.success:
        logger.error(f"Metadata error for {validator_address}: {metadata_result.error}")
    if not commission_result.success:
        logger.error(f"Commission error for {validator_address}: {commission_result.error}")
    if not state_result.success:
        logger.error(f"State error for {validator_address}: {state_result.error}")


def record_changes(validator_id, previous_state, new_state, previous_rate, new_rate):
    # Check if any user has subscribed to changes for this validator
    subscriptions_query = """
    SELECT COUNT(*) as subscription_count
    FROM subscriptions
    WHERE validator_id = %s
    """
    subscription_result = db_manager.execute_query(subscriptions_query, (validator_id,))
    if subscription_result[0]['subscription_count'] == 0:
        return

    if previous_state != new_state:
        db_manager.insert_data('validator_state_changes', {
            'validator_id': validator_id,
            'previous_state': previous_state,
            'new_state': new_state
        })

    if previous_rate != new_rate:
        db_manager.insert_data('commission_rate_changes', {
            'validator_id': validator_id,
            'previous_rate': previous_rate,
            'new_rate': new_rate
        })
