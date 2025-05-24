import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "")))
import psycopg2
import pandas as pd
from utils.parser import parser, load_config

class Postgres:

    def __init__(self, credentials):
        self.connection = psycopg2.connect(
            user=credentials.get('username'),
            password=credentials.get('password'),
            host=credentials.get('host'),
            database=credentials.get('database')
        )

    def is_superuser(self):
        """Check if the connected user is a superuser."""
        try:
            cursor = self.connection.cursor()
            # Query to check if the user has superuser privileges
            cursor.execute("SELECT rolsuper FROM pg_roles WHERE rolname = CURRENT_USER;")
            is_superuser = cursor.fetchone()[0]
            cursor.close()
            print(f"Connected user is superuser: {is_superuser}")
            return is_superuser
        except psycopg2.Error as e:
            print(f"Error while checking superuser status: {e}")
            return False
