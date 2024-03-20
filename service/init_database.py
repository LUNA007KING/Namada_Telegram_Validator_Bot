import logging

from config.settings import DB_CONFIG, DB_POOL_SIZE
from db.database_manager import DatabaseManager

logger = logging.getLogger(__name__)


def init_database():
    db_manager = DatabaseManager(DB_CONFIG, pool_name='namada_notify_pool', pool_size=DB_POOL_SIZE)

    tables = {
        'users': {
            'user_id': 'INT AUTO_INCREMENT PRIMARY KEY',
            'telegram_id': 'VARCHAR(12) NOT NULL',
            'telegram_name': 'VARCHAR(32)'
        },
        'validators': {
            'validator_id': 'INT AUTO_INCREMENT PRIMARY KEY',
            'validator_address': 'VARCHAR(45)',
            'tendermint_address': 'VARCHAR(40) NOT NULL',
            'voting_power': 'BIGINT',
            'email': 'VARCHAR(255)',
            'description': 'TEXT',
            'website': 'VARCHAR(255)',
            'discord_handle': 'VARCHAR(255)',
            'avatar': 'TEXT',
            'commission_rate': 'FLOAT',
            'max_commission_change': 'FLOAT',
            'state': 'VARCHAR(16)'
        },
        'subscriptions': {
            'id': 'INT AUTO_INCREMENT PRIMARY KEY',
            'user_id': 'INT NOT NULL',
            'validator_id': 'INT NOT NULL',
            'created_at': 'DATETIME DEFAULT CURRENT_TIMESTAMP'
        }
    }

    foreign_keys = {
        'subscriptions': [
            'FOREIGN KEY(user_id) REFERENCES users(user_id)',
            'FOREIGN KEY(validator_id) REFERENCES validators(validator_id)'
        ]
    }
    for table_name, columns in tables.items():
        fk_constraints = foreign_keys.get(table_name, [])
        db_manager.create_table(table_name, columns, fk_constraints)

    create_change_tables(db_manager)


def create_change_tables(db_manager):
    state_changes_table = {
        'change_id': 'INT AUTO_INCREMENT PRIMARY KEY',
        'validator_id': 'INT NOT NULL',
        'previous_state': 'VARCHAR(16)',
        'new_state': 'VARCHAR(16)',
        'change_timestamp': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
        'notifications_sent': 'TINYINT(1) DEFAULT 0'
    }

    commission_changes_table = {
        'change_id': 'INT AUTO_INCREMENT PRIMARY KEY',
        'validator_id': 'INT NOT NULL',
        'previous_rate': 'FLOAT',
        'new_rate': 'FLOAT',
        'change_timestamp': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
        'notifications_sent': 'TINYINT(1) DEFAULT 0'
    }

    foreign_keys_state = ['FOREIGN KEY(validator_id) REFERENCES validators(validator_id)']
    foreign_keys_commission = ['FOREIGN KEY(validator_id) REFERENCES validators(validator_id)']

    db_manager.create_table('validator_state_changes', state_changes_table, foreign_keys_state)
    db_manager.create_table('commission_rate_changes', commission_changes_table, foreign_keys_commission)
