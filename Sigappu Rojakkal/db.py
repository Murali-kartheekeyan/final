import pymysql
import os

def get_db_connection():
    """
    Establishes a connection to the MySQL database.
    UPDATED to connect to the 'learning_path_db'.
    """
    return pymysql.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD', '1234'),
        database=os.getenv('DB_NAME', 'learning_path_db'), # Corrected database name
        cursorclass=pymysql.cursors.DictCursor
    )
