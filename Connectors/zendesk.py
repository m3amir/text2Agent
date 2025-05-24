import os
import sys
from zenpy import Zenpy
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.imports import *


class ZendeskError(Exception):
    """Custom exception for Zendesk-related errors"""
    pass

class Zendesk:
    """
    A wrapper class for Zendesk API interactions using the Zenpy library.
    
    Attributes:
        credentials (dict): Zendesk API credentials containing email, token, and subdomain
        client: Zenpy client instance for API interactions
    """
    
    def __init__(self, credentials: dict):
        """
        Initialize the Zendesk client with provided credentials.
        
        Args:
            credentials (dict): Dictionary containing 'email', 'token', and 'subdomain'
        
        Raises:
            ZendeskError: If connection fails or credentials are invalid
        """
        self.credentials = credentials
        try:
            # Create a clean dict with only the params that Zenpy expects
            zenpy_creds = {}
            
            # Required fields for Zenpy
            if 'email' in credentials:
                zenpy_creds['email'] = credentials['email']
            if 'token' in credentials:
                zenpy_creds['token'] = credentials['token']
            if 'subdomain' in credentials:
                zenpy_creds['subdomain'] = credentials['subdomain']
                
            self.client = Zenpy(**zenpy_creds)
        except Exception as e:
            print(f"Failed to initialize Zendesk client: {str(e)}")
            raise ZendeskError(f"Failed to initialize Zendesk client: {str(e)}")
    