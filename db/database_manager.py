import logging
import threading
import mysql.connector
from mysql.connector import pooling
from config.settings import DB_POOL_SIZE

logger = logging.getLogger(__name__)


class DatabaseManager:
    _instance = None
    _lock = threading.Lock()
    _pool = None
    _charset = 'utf8mb4'
    _collation = 'utf8mb4_unicode_ci'

    def __new__(cls, db_config=None, pool_name="mypool", pool_size=DB_POOL_SIZE):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(DatabaseManager, cls).__new__(cls)
                    cls._initialize_pool(db_config, pool_name, pool_size)
        return cls._instance

    @classmethod
    def _initialize_pool(cls, db_config, pool_name, pool_size):
        """
        Initialize the connection pool after ensuring the database exists.
        """
        cls._charset = db_config.get('charset', cls._charset)
        cls._collation = db_config.get('collation', cls._collation)
        temp_config = db_config.copy()
        database = temp_config.pop('database', None)

        # Connect without specifying the database to check existence / create it
        cls.create_database(temp_config, database)

        # Adjust db_config to include the database for connection pooling
        db_config_with_db = temp_config.copy()
        db_config_with_db['database'] = database
        try:
            cls._pool = pooling.MySQLConnectionPool(pool_name=pool_name, pool_size=pool_size, **db_config_with_db)
            logger.info("Database connection pool created successfully.")
        except mysql.connector.Error as err:
            logger.error(f"Error creating database connection pool: {err}")
            raise

    @staticmethod
    def create_database(db_config, database_name):
        """
        Ensure the target database exists, creating it if necessary.
        """
        charset = db_config.get('charset', 'utf8mb4')
        collation = db_config.get('collation', 'utf8mb4_unicode_ci')

        try:
            temp_config = db_config.copy()
            temp_config.pop('database', None)
            with mysql.connector.connect(**temp_config) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        f"CREATE DATABASE IF NOT EXISTS `{database_name}` CHARACTER SET = '{charset}' COLLATE = '{collation}'")
                    logger.info(
                        f"Database `{database_name}` created or already exists.")
        except mysql.connector.Error as err:
            logger.error(f"Failed to ensure database exists: {err}")
            raise

    def execute_query(self, query, params=None, commit=False):
        """
        Execute a SQL query with the given parameters.
        """
        try:
            with self._pool.get_connection() as conn:
                with conn.cursor(dictionary=True) as cursor:
                    cursor.execute(query, params)
                    if commit:
                        conn.commit()
                        return cursor.rowcount
                    else:
                        return cursor.fetchall()
        except mysql.connector.Error as err:
            logger.error(f"Error executing query: {err}")
            if commit:
                conn.rollback()
            raise

    def create_table(self, table_name, columns, constraints=None):
        """
        Create a new table with the given name, columns, and optional constraints.
        """
        columns_definitions = ", ".join([f"`{column}` {properties}" for column, properties in columns.items()])
        constraints_definitions = ", ".join(constraints) if constraints else ""
        query = f"CREATE TABLE IF NOT EXISTS `{table_name}` ({columns_definitions}" \
                f"{', ' + constraints_definitions if constraints_definitions else ''}) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"
        try:
            self.execute_query(query, commit=True)
            logger.info(f"Table `{table_name}` created successfully.")
        except mysql.connector.Error as err:
            logger.error(f"Failed to create table `{table_name}`: {err}")
            raise

    def insert_data(self, table_name, data):
        """
        Insert a new record into the specified table.
        """
        columns = ", ".join([f"`{column}`" for column in data.keys()])
        placeholders = ", ".join(["%s"] * len(data))
        query = f"INSERT INTO `{table_name}` ({columns}) VALUES ({placeholders})"
        try:
            self.execute_query(query, tuple(data.values()), commit=True)
            logger.info(f"Data inserted into table `{table_name}` successfully.")
        except mysql.connector.Error as err:
            logger.error(f"Failed to insert data into table `{table_name}`: {err}")
            raise

    def insert_data_and_get_id(self, table_name, data):
        """
        Insert a new record into the specified table and return the ID of the new record.
        """
        columns = ", ".join([f"`{column}`" for column in data.keys()])
        placeholders = ", ".join(["%s"] * len(data))
        query = f"INSERT INTO `{table_name}` ({columns}) VALUES ({placeholders})"
        try:
            with self._pool.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, tuple(data.values()))
                    conn.commit()
                    cursor.execute("SELECT LAST_INSERT_ID()")
                    last_id = cursor.fetchone()[0]  # Assuming LAST_INSERT_ID() returns a single value
                    return last_id
        except mysql.connector.Error as err:
            logger.error(f"Failed to insert data into table `{table_name}` and get ID: {err}")
            conn.rollback()
            raise

    def update_data(self, table_name, data, conditions):
        """
        Update records in the specified table that meet the given conditions.
        """
        set_clause = ", ".join([f"`{column}` = %s" for column in data.keys()])
        where_clause = " AND ".join([f"`{column}` = %s" for column in conditions.keys()])
        query = f"UPDATE `{table_name}` SET {set_clause} WHERE {where_clause}"
        params = tuple(data.values()) + tuple(conditions.values())
        try:
            rows_affected = self.execute_query(query, params, commit=True)
            logger.info(f"Updated {rows_affected} row(s) in table `{table_name}` successfully.")
        except mysql.connector.Error as err:
            logger.error(f"Failed to update table `{table_name}`: {err}")
            raise

    def delete_data(self, table_name, conditions):
        """
        Delete records from the specified table that meet the given conditions.
        """
        where_clause = " AND ".join([f"`{column}` = %s" for column in conditions.keys()])
        query = f"DELETE FROM `{table_name}` WHERE {where_clause}"
        try:
            rows_affected = self.execute_query(query, tuple(conditions.values()), commit=True)
            logger.info(f"Deleted {rows_affected} row(s) from table `{table_name}` successfully.")
        except mysql.connector.Error as err:
            logger.error(f"Failed to delete from table `{table_name}`: {err}")
            raise
