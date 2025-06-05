"""
Essential Cognito authentication utilities
"""

import boto3
import json
import hashlib
import hmac
import base64
import os
from typing import Dict, Optional
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Cognito Configuration
COGNITO_REGION = os.getenv('COGNITO_REGION', 'eu-west-2')
USER_POOL_ID = os.getenv('COGNITO_USER_POOL_ID', 'eu-west-2_MbS1w2AZW')
CLIENT_ID = os.getenv('COGNITO_CLIENT_ID', '399p06atd6g2lu57h3kt0lgog8')
CLIENT_SECRET = os.getenv('COGNITO_CLIENT_SECRET')

class CognitoAuth:
    """Simple Cognito authentication manager"""
    
    def __init__(self, user_pool_id: str = USER_POOL_ID, client_id: str = CLIENT_ID, 
                 client_secret: str = CLIENT_SECRET, region: str = COGNITO_REGION):
        self.user_pool_id = user_pool_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.region = region
        self.client = boto3.client('cognito-idp', region_name=region)
    
    def _calculate_secret_hash(self, username: str) -> Optional[str]:
        """Calculate secret hash for Cognito authentication"""
        if not self.client_secret:
            return None
        
        message = username + self.client_id
        dig = hmac.new(
            str(self.client_secret).encode('utf-8'),
            msg=str(message).encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        return base64.b64encode(dig).decode()
    
    def sign_up(self, username: str, email: str, password: str) -> Dict:
        """Register a new user"""
        try:
            params = {
                'ClientId': self.client_id,
                'Username': username,
                'Password': password,
                'UserAttributes': [
                    {'Name': 'email', 'Value': email}
                ]
            }
            
            if self.client_secret:
                params['SecretHash'] = self._calculate_secret_hash(username)
            
            response = self.client.sign_up(**params)
            
            return {
                'success': True,
                'message': 'User registered successfully',
                'user_sub': response['UserSub'],
                'username': username,
                'email': email,
                'confirmation_required': not response.get('UserConfirmed', False)
            }
            
        except ClientError as e:
            return {
                'success': False,
                'error': e.response['Error']['Code'],
                'message': e.response['Error']['Message']
            }
    
    def confirm_sign_up(self, username: str, confirmation_code: str) -> Dict:
        """Confirm user registration with verification code"""
        try:
            params = {
                'ClientId': self.client_id,
                'Username': username,
                'ConfirmationCode': confirmation_code
            }
            
            if self.client_secret:
                params['SecretHash'] = self._calculate_secret_hash(username)
            
            self.client.confirm_sign_up(**params)
            
            return {
                'success': True,
                'message': 'User confirmed successfully',
                'username': username
            }
            
        except ClientError as e:
            return {
                'success': False,
                'error': e.response['Error']['Code'],
                'message': e.response['Error']['Message']
            }
    
    def sign_in(self, username: str, password: str) -> Dict:
        """Sign in user and get tokens"""
        try:
            params = {
                'ClientId': self.client_id,
                'AuthFlow': 'USER_PASSWORD_AUTH',
                'AuthParameters': {
                    'USERNAME': username,
                    'PASSWORD': password
                }
            }
            
            if self.client_secret:
                params['AuthParameters']['SECRET_HASH'] = self._calculate_secret_hash(username)
            
            response = self.client.initiate_auth(**params)
            
            return {
                'success': True,
                'message': 'Sign in successful',
                'tokens': response['AuthenticationResult'],
                'username': username
            }
            
        except ClientError as e:
            return {
                'success': False,
                'error': e.response['Error']['Code'],
                'message': e.response['Error']['Message']
            }
    
    def resend_confirmation_code(self, username: str) -> Dict:
        """Resend confirmation code"""
        try:
            params = {
                'ClientId': self.client_id,
                'Username': username
            }
            
            if self.client_secret:
                params['SecretHash'] = self._calculate_secret_hash(username)
            
            response = self.client.resend_confirmation_code(**params)
            
            return {
                'success': True,
                'message': 'Confirmation code resent successfully'
            }
            
        except ClientError as e:
            return {
                'success': False,
                'error': e.response['Error']['Code'],
                'message': e.response['Error']['Message']
            }

# Convenience functions
def register_user(username: str, email: str, password: str) -> Dict:
    """Quick user registration"""
    auth = CognitoAuth()
    return auth.sign_up(username, email, password)

def confirm_user(username: str, confirmation_code: str) -> Dict:
    """Quick user confirmation"""
    auth = CognitoAuth()
    return auth.confirm_sign_up(username, confirmation_code)

def login_user(username: str, password: str) -> Dict:
    """Quick user login"""
    auth = CognitoAuth()
    return auth.sign_in(username, password) 