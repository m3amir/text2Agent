from simple_salesforce import Salesforce
import os
import sys
import traceback
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../", "")))
from utils.parser import load_config

# creds = load_config()['salesforce_creds']

# print(creds)
class SF:
    def __init__(self, credentials):
        try:
            self.conn = Salesforce(
                password=credentials['SF_PASSWORD'], 
                username=credentials['SF_EMAIL'], 
                security_token=credentials['SF_TOKEN'])
        except Exception as e:
            print(f"Error connecting to Salesforce: {e}")
            print(f"Full traceback: {traceback.format_exc()}")
            raise
    
    def __repr__(self):
        return "Salesforce"