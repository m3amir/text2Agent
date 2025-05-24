import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "")))
import mysql.connector
import pandas as pd
from utils.parser import parser, load_config

class Sqlite:

    def __init__(self, credentials):
        self.connection = mysql.connector.connect(
            user=credentials.get('username'),
            password=credentials.get('password'),
            host=credentials.get('host'),
            database=credentials.get('database')
        )

    def select(self, table: str, columns: list = '*'):
        cursor = self.connection.cursor()
        cursor.execute(f"SELECT {columns} FROM {table}")
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        df = pd.DataFrame(rows, columns=columns)
        return df

    def list_tables(self):
        cursor = self.connection.cursor()
        # Query to get all tables in the database
        cursor.execute("SHOW TABLES")
        tables = [table[0] for table in cursor.fetchall()]
        print("Tables in the database:", tables)
        return tables

    def is_root_user(self):
        """Check if the connected user is root."""
        try:
            cursor = self.connection.cursor()
            # Query to get the current user
            cursor.execute("SELECT USER();")
            current_user = cursor.fetchone()[0]
            cursor.close()
            print(f"Connected as: {current_user}")
            # Check if the user is root
            if current_user.startswith('root@'):
                return True
            else:
                return False
        except mysql.connector.Error as e:
            print(f"Error while checking user: {e}")
            return False