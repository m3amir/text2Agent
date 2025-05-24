import mysql.connector
import os
from dotenv import load_dotenv

class DatabaseManager:
    def __init__(self):
        load_dotenv()
        self.dbpass = os.getenv("db_pass")
        self.mydb = mysql.connector.connect(
            host="localhost",
            user="root",
            password=self.dbpass,
            database="agent_workflow"
        )
        self.mycursor = self.mydb.cursor()
        self.tasks_table = 'tasks'
        self.sales_table = 'sales'
        self.holidays_table = 'employee_holidays'

    def get_schema(self):
        self.mycursor.execute(f"DESCRIBE {self.tasks_table};")
        return self.mycursor.fetchall()

    
    def fetch_joined_data(self):
        # Query to join tasks and sales
        query_tasks_sales = f"""
            SELECT t.*, s.*
            FROM {self.tasks_table} t
            JOIN {self.sales_table} s ON t.t_id = s.sale_id
        """
        
        # Query to join tasks and holidays
        query_tasks_holidays = f"""
            SELECT t.*, h.*
            FROM {self.tasks_table} t
            JOIN {self.holidays_table} h ON t.t_id = h.holiday_id
        """
        
        # Execute query for tasks and sales
        self.mycursor.execute(query_tasks_sales)
        results_tasks_sales = self.mycursor.fetchall()

        column_names_tasks_sales = [desc[0] for desc in self.mycursor.description]
        tasks_sales = [dict(zip(column_names_tasks_sales, row)) for row in results_tasks_sales]

        # Execute query for tasks and holidays
        self.mycursor.execute(query_tasks_holidays)
        results_tasks_holidays = self.mycursor.fetchall()
        column_names_tasks_holidays = [desc[0] for desc in self.mycursor.description]
        tasks_holidays = [dict(zip(column_names_tasks_holidays, row)) for row in results_tasks_holidays]
        
        # Optionally return the data and schemas
        schema_tasks_sales = column_names_tasks_sales
        schema_tasks_holidays = column_names_tasks_holidays

        return {
        'sales': tasks_sales,
        'tasks_sales_schema': schema_tasks_sales,
        'holidays': tasks_holidays,
        'tasks_holidays_schema': schema_tasks_holidays}

    def close_connection(self):
        self.mycursor.close()
        self.mydb.close()