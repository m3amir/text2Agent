"""
Essential Cognito authentication utilities
"""

import boto3
import json
import hashlib
import hmac
import base64
import os
from typing import Dict, Optional, List
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Cognito Configuration
COGNITO_REGION = os.getenv('COGNITO_REGION', 'eu-west-2')
USER_POOL_ID = os.getenv('COGNITO_USER_POOL_ID', 'eu-west-2_MbS1w2AZW')
CLIENT_ID = os.getenv('COGNITO_CLIENT_ID', '399p06atd6g2lu57h3kt0lgog8')
CLIENT_SECRET = os.getenv('COGNITO_CLIENT_SECRET')

# User tier constants
VALID_USER_TIERS = ['standard', 'premium']
DEFAULT_USER_TIER = 'standard'

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
    
    def _validate_user_tier(self, user_tier: str) -> str:
        """Validate and normalize user tier"""
        if not user_tier or user_tier.lower() not in VALID_USER_TIERS:
            return DEFAULT_USER_TIER
        return user_tier.lower()
    
    def _handle_cognito_error(self, e: ClientError) -> Dict:
        """Handle Cognito client errors consistently"""
        return {
            'success': False,
            'error': e.response['Error']['Code'],
            'message': e.response['Error']['Message']
        }
    
    def sign_up(self, username: str, email: str, password: str, user_tier: str = None, 
                custom_attributes: Optional[Dict[str, str]] = None) -> Dict:
        """Register a new user with custom attributes including user_tier"""
        try:
            validated_tier = self._validate_user_tier(user_tier)
            
            user_attributes = [
                {'Name': 'email', 'Value': email},
                {'Name': 'custom:user_tier', 'Value': validated_tier}
            ]
            
            if custom_attributes:
                for attr_name, attr_value in custom_attributes.items():
                    if not attr_name.startswith('custom:') and attr_name not in ['email', 'phone_number', 'given_name', 'family_name']:
                        attr_name = f'custom:{attr_name}'
                    user_attributes.append({'Name': attr_name, 'Value': str(attr_value)})
            
            params = {
                'ClientId': self.client_id,
                'Username': username,
                'Password': password,
                'UserAttributes': user_attributes
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
                'user_tier': validated_tier,
                'confirmation_required': not response.get('UserConfirmed', False)
            }
            
        except ClientError as e:
            return self._handle_cognito_error(e)
    
    def update_user_tier(self, username: str, new_tier: str) -> Dict:
        """Update user's tier (requires admin privileges)"""
        try:
            validated_tier = self._validate_user_tier(new_tier)
            
            self.client.admin_update_user_attributes(
                UserPoolId=self.user_pool_id,
                Username=username,
                UserAttributes=[
                    {'Name': 'custom:user_tier', 'Value': validated_tier}
                ]
            )
            
            return {
                'success': True,
                'message': f'User tier updated to {validated_tier}',
                'username': username,
                'new_tier': validated_tier
            }
            
        except ClientError as e:
            return self._handle_cognito_error(e)
    
    def get_user_attributes(self, username: str) -> Dict:
        """Get user attributes including user_tier"""
        try:
            response = self.client.admin_get_user(
                UserPoolId=self.user_pool_id,
                Username=username
            )
            
            attributes = {}
            for attr in response.get('UserAttributes', []):
                attributes[attr['Name']] = attr['Value']
            
            return {
                'success': True,
                'username': username,
                'attributes': attributes,
                'user_tier': attributes.get('custom:user_tier', DEFAULT_USER_TIER),
                'email': attributes.get('email', ''),
                'user_status': response.get('UserStatus', 'UNKNOWN')
            }
            
        except ClientError as e:
            return self._handle_cognito_error(e)
    
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
            return self._handle_cognito_error(e)
    
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
            return self._handle_cognito_error(e)
    
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
            return self._handle_cognito_error(e) 