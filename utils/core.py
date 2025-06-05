"""
Core utilities for the text2Agent application
Consolidated database, secrets, and configuration utilities
"""

import boto3
import json
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
import os
from typing import Optional, Dict, Any
from contextlib import contextmanager
from dotenv import load_dotenv
import yaml

# Load environment variables
load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)

# AWS Configuration
AWS_PROFILE = 'm3'
AWS_REGION = 'eu-west-2'
SECRET_NAME = 'rds!db-ca208747-bb10-416f-99f3-68306eef15a3'
DB_HOST = 'text2agenttenant.cluqugi4urqi.eu-west-2.rds.amazonaws.com'
DB_PORT = 5432
DB_NAME = 'postgres'

# Global session and credentials cache
_aws_session = None
_db_credentials = None

def get_aws_session():
    """Get or create AWS session"""
    global _aws_session
    if not _aws_session:
        _aws_session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
    return _aws_session

def get_secret(secret_name: str, region: str = AWS_REGION) -> Dict[str, Any]:
    """Get secret from AWS Secrets Manager"""
    try:
        session = get_aws_session()
        client = session.client('secretsmanager')
        response = client.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    except Exception as e:
        logger.error(f"Failed to get secret {secret_name}: {e}")
        raise

def get_db_credentials() -> Dict[str, str]:
    """Get database credentials from AWS Secrets Manager (cached)"""
    global _db_credentials
    if not _db_credentials:
        try:
            logger.info(f"🔐 Retrieving credentials from Secrets Manager: {SECRET_NAME}")
            secret_data = get_secret(SECRET_NAME)
            _db_credentials = {
                'username': secret_data.get('username', 'postgres'),
                'password': secret_data.get('password'),
                'host': secret_data.get('host', DB_HOST),
                'port': secret_data.get('port', DB_PORT),
                'dbname': secret_data.get('dbname', DB_NAME)
            }
            logger.info(f"✅ Successfully retrieved credentials for user: {_db_credentials['username']}")
        except Exception as e:
            logger.error(f"❌ Failed to retrieve credentials: {e}")
            raise
    return _db_credentials

@contextmanager
def get_db_cursor():
    """Context manager for database operations"""
    connection = None
    cursor = None
    
    try:
        creds = get_db_credentials()
        logger.info(f"🔌 Connecting to database: {creds['host']}:{creds['port']}/{creds['dbname']}")
        
        connection = psycopg2.connect(
            host=creds['host'],
            port=creds['port'],
            database=creds['dbname'],
            user=creds['username'],
            password=creds['password'],
            cursor_factory=RealDictCursor
        )
        
        logger.info("✅ Database connection established")
        cursor = connection.cursor()
        yield cursor
        connection.commit()
        
    except Exception as e:
        if connection:
            connection.rollback()
        logger.error(f"❌ Database operation failed: {e}")
        raise
        
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def execute_query(query: str, params: Optional[tuple] = None) -> list:
    """Execute a SELECT query and return results"""
    try:
        with get_db_cursor() as cursor:
            cursor.execute(query, params)
            results = cursor.fetchall()
            logger.info(f"📊 Query executed successfully, returned {len(results)} rows")
            return results
    except Exception as e:
        logger.error(f"❌ Query execution failed: {e}")
        raise

def get_tenant_mapping_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Get tenant mapping by email address"""
    try:
        query = """
        SELECT tenant, domain 
        FROM "Tenants".tenantmappings 
        WHERE email = %s
        """
        results = execute_query(query, (email,))
        
        if results:
            tenant_data = dict(results[0])
            logger.info(f"✅ Found tenant mapping for email: {email}")
            return tenant_data
        else:
            logger.warning(f"⚠️ No tenant mapping found for email: {email}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Failed to get tenant mapping for {email}: {e}")
        raise

def get_tenant_domain_by_email(email: str) -> Optional[str]:
    """Construct tenant domain string from email"""
    try:
        tenant_mapping = get_tenant_mapping_by_email(email)
        if tenant_mapping:
            domain_string = f"tenant-{tenant_mapping['tenant']}-{tenant_mapping['domain']}"
            logger.info(f"✅ Constructed tenant domain for {email}: {domain_string}")
            return domain_string
        return None
    except Exception as e:
        logger.error(f"❌ Failed to construct tenant domain for {email}: {e}")
        raise

def load_config(config_file: str = "./Config/config.yml") -> Dict[str, Any]:
    """Load configuration from YAML file"""
    try:
        with open(config_file, "r") as file:
            config = yaml.safe_load(file) or {}
        logger.info("✅ Configuration loaded from YAML file")
        return config
    except FileNotFoundError:
        logger.error("❌ Configuration file not found")
        return {}
    except yaml.YAMLError as e:
        logger.error(f"❌ Failed to parse YAML file: {e}")
        return {} 