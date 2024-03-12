from dotenv import load_dotenv
import os

load_dotenv()


def get_env_int(var_name, default=0):
    value = os.getenv(var_name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


DB_PORT = get_env_int("DB_PORT", 3306)
DB_POOL_SIZE = get_env_int("DB_POOL_SIZE", 10)
USER_SUBSCRIPTION_LIMIT = get_env_int("USER_SUBSCRIPTION_LIMIT", 4)
UPDATE_INTERVAL = get_env_int("UPDATE_INTERVAL", 5)
NOTIFY_INTERVAL = get_env_int("NOTIFY_INTERVAL", 5)

DB_CONFIG = {
    'user': os.getenv('DB_USER', 'default_user'),
    'password': os.getenv('DB_PASSWORD', 'default_password'),
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': DB_PORT,
    'database': os.getenv('DB_NAME', 'your_database'),
    'charset': os.getenv('DB_CHARSET', 'utf8mb4'),
    'collation': os.getenv('DB_COLLATION', 'utf8mb4_unicode_ci'),
}

NAMADA_RPC_URL = os.getenv("NAMADA_RPC_URL")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
