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
from datetime import datetime

# Load environment variables
load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)

# AWS Configuration
AWS_PROFILE = 'm3'
AWS_REGION = 'eu-west-2'
SECRET_NAME = 'text2agent-dev-db-credentials-v2'
DB_HOST = 'text2agent-dev-cluster.cluster-cluqugi4urqi.eu-west-2.rds.amazonaws.com'
DB_PORT = 5432
DB_NAME = 'text2AgentTenants'

# NOTE: The Aurora cluster is deployed in a private VPC and only accessible from:
# 1. Lambda functions (within VPC)
# 2. EC2 instances in the same VPC
# 3. Local development with VPN/bastion host access
# For local testing without VPC access, use AWS RDS Data API instead

# Global session and credentials cache
_aws_session = None
_db_credentials = None

def setup_logging(user_email: str, component_name: str, log_manager=None, enable_console=True):
    """
    Centralized logging setup for all components
    
    Args:
        user_email (str): User's email address
        component_name (str): Name of the component (e.g., 'AI_Colleagues', 'STR')
        log_manager: Optional LogManager instance for organized directory structure
        enable_console (bool): Whether to enable console logging (default: True)
    
    Returns:
        logging.Logger: Configured logger instance
    """
    # Determine logs directory
    if log_manager and hasattr(log_manager, 'logs_dir'):
        logs_dir = log_manager.logs_dir
    else:
        logs_dir = os.path.join(os.path.dirname(__file__), '..', 'Logs')
        os.makedirs(logs_dir, exist_ok=True)
    
    # Create log filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"{component_name.lower()}_{timestamp}.log"
    log_file = os.path.join(logs_dir, log_filename)
    
    # Get component-specific logger
    logger = logging.getLogger(component_name)
    logger.setLevel(logging.INFO)
    
    # Clear existing handlers to prevent duplicates
    if logger.handlers:
        logger.handlers.clear()
    
    # Only add handlers if none exist
    if not logger.handlers:
        # File handler
        file_handler = logging.FileHandler(log_file, mode='w')
        file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        # Console handler (optional)
        if enable_console:
            console_handler = logging.StreamHandler()
            console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)
    
    # Prevent propagation to avoid duplicate messages from root logger
    logger.propagate = False
    
    logger.info(f"📝 Log file: {log_file}")
    logger.info(f"👤 User: {user_email}")
    
    if log_manager:
        logger.info(f"🔄 LogManager ready for sync")
    
    return logger

def sync_logs_to_s3(logger, log_manager, force_current=True):
    """
    Centralized log syncing function for all components
    
    Args:
        logger: The component's logger instance
        log_manager: The LogManager instance 
        force_current (bool): If True, force upload current log file immediately
    
    Returns:
        bool: True if sync was successful, False otherwise
    """
    if not log_manager:
        print("⚠️ No LogManager - local only")
        return False
        
    try:
        logger.info("☁️ Syncing logs to S3...")
        
        # Flush all handlers to ensure logs are written
        for handler in logger.handlers:
            if hasattr(handler, 'flush'):
                handler.flush()
                if isinstance(handler, logging.FileHandler) and hasattr(handler, 'close'):
                    # Close file handlers to release file locks for sync
                    handler.close()
        
        # Small delay to ensure file system updates
        import time
        time.sleep(0.5)
        
        if force_current:
            # Get current log file name and force upload
            current_log_filename = None
            for handler in logger.handlers:
                if isinstance(handler, logging.FileHandler):
                    current_log_filename = os.path.basename(handler.baseFilename)
                    break
            
            if current_log_filename:
                success = log_manager.force_upload_current_log(current_log_filename)
                if success:
                    print(f"✅ Current log uploaded: {current_log_filename}")
                    return True
                else:
                    print(f"❌ Failed to upload: {current_log_filename}")
                    return False
            else:
                print("⚠️ Could not determine current log file name")
                return False
        else:
            # Regular sync (older files)
            sync_results = log_manager.sync_logs(older_than_hours=0)
            synced_count = len(sync_results.get('synced', []))
            print(f"✅ Synced {synced_count} files")
            return True
            
    except Exception as e:
        print(f"❌ Sync failed: {e}")
        return False

def get_aws_session():
    """Get or create AWS session"""
    global _aws_session
    if not _aws_session:
        try:
            # Try to use AWS profile first (for local development)
            _aws_session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
        except Exception:
            # Fall back to environment variables (for GitHub Actions/CI)
            _aws_session = boto3.Session(region_name=AWS_REGION)
    return _aws_session

def get_secret(secret_name: str, region: str = AWS_REGION) -> Dict[str, Any]:
    """Get secret from AWS Secrets Manager"""
    try:
        print(f"Getting secret {secret_name} from AWS Secrets Manager")
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
                'dbname': secret_data.get('dbname', DB_NAME),
                'cluster_arn': f"arn:aws:rds:{AWS_REGION}:994626600571:cluster:text2agent-dev-cluster",
                'secret_arn': f"arn:aws:secretsmanager:{AWS_REGION}:994626600571:secret:{SECRET_NAME}"
            }
            logger.info(f"✅ Successfully retrieved credentials for user: {_db_credentials['username']}")
        except Exception as e:
            logger.error(f"❌ Failed to retrieve credentials: {e}")
            raise
    return _db_credentials

def execute_rds_data_api(sql: str, database: str = 'text2AgentTenants') -> list:
    """
    Execute SQL using AWS RDS Data API (works without VPC access)
    
    Args:
        sql (str): SQL query to execute
        database (str): Database name (defaults to text2AgentTenants)
        
    Returns:
        list: Query results
    """
    try:
        session = get_aws_session()
        rds_data = session.client('rds-data')
        creds = get_db_credentials()
        
        response = rds_data.execute_statement(
            resourceArn=creds['cluster_arn'],
            secretArn=creds['secret_arn'],
            database=database,
            sql=sql,
            includeResultMetadata=True
        )
        
        # Convert RDS Data API response to standard format
        results = []
        if 'records' in response:
            column_metadata = response.get('columnMetadata', [])
            for record in response['records']:
                row = {}
                for i, field in enumerate(record):
                    # Get column name from metadata or use default
                    if i < len(column_metadata):
                        column_name = column_metadata[i].get('name', f'col_{i}')
                    else:
                        column_name = f'col_{i}'
                    
                    # Extract value based on type
                    if 'stringValue' in field:
                        row[column_name] = field['stringValue']
                    elif 'longValue' in field:
                        row[column_name] = field['longValue']
                    elif 'doubleValue' in field:
                        row[column_name] = field['doubleValue']
                    elif 'booleanValue' in field:
                        row[column_name] = field['booleanValue']
                    elif 'isNull' in field and field['isNull']:
                        row[column_name] = None
                    else:
                        # Handle any other case
                        row[column_name] = str(field)
                results.append(row)
        
        logger.info(f"✅ RDS Data API query executed, returned {len(results)} rows")
        print(f"🔍 RDS Data API results: {results}")  # Debug print
        return results
        
    except Exception as e:
        logger.error(f"❌ RDS Data API query failed: {e}")
        raise

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
        # Try direct connection first
        query = """
        SELECT t.tenant_id as tenant, t.domain 
        FROM tenantmappings t
        JOIN users u ON t.tenant_id = u.tenant_id
        WHERE u.email = %s
        """
        try:
            results = execute_query(query, (email,))
        except Exception as conn_error:
            logger.warning(f"⚠️ Direct DB connection failed, trying RDS Data API: {conn_error}")
            # Fallback to RDS Data API
            sql = f"""
            SELECT t.tenant_id as tenant, t.domain 
            FROM tenantmappings t
            JOIN users u ON t.tenant_id = u.tenant_id
            WHERE u.email = '{email}'
            """
            results = execute_rds_data_api(sql)
        
        if results:
            tenant_data = dict(results[0])
            print(f"🔍 Retrieved tenant data: {tenant_data}")  # Debug print
            logger.info(f"✅ Found tenant mapping for email: {email}")
            return tenant_data
        else:
            print(f"🔍 No rows returned for email: {email}")  # Debug print
            logger.warning(f"⚠️ No tenant mapping found for email: {email}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Failed to get tenant mapping for {email}: {e}")
        raise

def get_tenant_domain_by_email(email: str) -> Optional[str]:
    """Get actual bucket name from database for email (handles bucket recreation)"""
    try:
        # First try to get the actual bucket name from database
        bucket_name = get_actual_bucket_name_by_email(email)
        if bucket_name:
            logger.info(f"✅ Found actual bucket name for {email}: {bucket_name}")
            return bucket_name
            
        # Fallback: construct from tenant mapping if no bucket name found
        tenant_mapping = get_tenant_mapping_by_email(email)
        if tenant_mapping:
            domain_string = f"tenant-{tenant_mapping['tenant']}-{tenant_mapping['domain']}"
            logger.info(f"✅ Fallback constructed tenant domain for {email}: {domain_string}")
            return domain_string
        return None
    except Exception as e:
        logger.error(f"❌ Failed to get tenant domain for {email}: {e}")
        raise

def get_actual_bucket_name_by_email(email: str) -> Optional[str]:
    """Get the actual bucket name from tenantmappings table by email"""
    try:
        # Try direct connection first
        query = """
        SELECT t.bucket_name 
        FROM tenantmappings t
        JOIN users u ON t.tenant_id = u.tenant_id
        WHERE u.email = %s
        """
        try:
            results = execute_query(query, (email,))
        except Exception as conn_error:
            logger.warning(f"⚠️ Direct DB connection failed, trying RDS Data API: {conn_error}")
            # Fallback to RDS Data API
            sql = f"""
            SELECT t.bucket_name 
            FROM tenantmappings t
            JOIN users u ON t.tenant_id = u.tenant_id
            WHERE u.email = '{email}'
            """
            results = execute_rds_data_api(sql)
        
        if results:
            bucket_name = results[0].get('bucket_name')
            if bucket_name:
                print(f"🔍 Retrieved actual bucket name from DB: {bucket_name}")
                logger.info(f"✅ Found actual bucket name for email: {email}")
                return bucket_name
        
        print(f"🔍 No bucket name found in database for email: {email}")
        logger.warning(f"⚠️ No bucket name found in database for email: {email}")
        return None
            
    except Exception as e:
        logger.error(f"❌ Failed to get actual bucket name for {email}: {e}")
        return None

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

def add_str_record(task_desc: str, tools: str, score: float, record_id: str, 
                   reflection_steps: int = None, ai_desc: str = None) -> bool:
    """
    Add a record to the strbase.str table
    
    Args:
        task_desc (str): Task description
        tools (str): Comma-separated string of tools used (e.g., "sharepoint,slack,email")
        score (float): Score value
        record_id (str): Unique identifier for the record
        reflection_steps (int, optional): Number of reflection steps
        ai_desc (str, optional): AI description
        
    Returns:
        bool: True if insertion was successful, False otherwise
    """
    try:
        query = """
        INSERT INTO strbase.str (task_desc, tools, score, id, reflection_steps, ai_desc)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        
        with get_db_cursor() as cursor:
            cursor.execute(query, (task_desc, tools, score, record_id, reflection_steps, ai_desc))
            logger.info(f"✅ Successfully inserted record with ID: {record_id}")
            return True
            
    except Exception as e:
        logger.error(f"❌ Failed to insert record into strbase.str: {e}")
        return False

def get_user_uid_by_email(email: str) -> Optional[str]:
    """Get user uid from users table by email address"""
    try:
        query = """
        SELECT user_id 
        FROM users 
        WHERE email = %s
        """
        results = execute_query(query, (email,))
        
        if results:
            user_id = results[0]['user_id']
            logger.info(f"✅ Found user_id for email: {email}")
            return user_id
        else:
            logger.warning(f"⚠️ No user found with email: {email}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Failed to get uid for email {email}: {e}")
        raise

def upload_text_as_pdf_to_s3(text_content: str, user_email: str, filename: str = "document.pdf") -> bool:
    """Convert text to PDF and upload to str-data-store-bucket organized by user uid and date"""
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        import tempfile
        from datetime import datetime
        
        # Create temporary PDF file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            temp_path = temp_file.name
        
        # Create PDF from text
        c = canvas.Canvas(temp_path, pagesize=letter)
        width, height = letter
        
        # Add text to PDF (simple text wrapping)
        lines = text_content.split('\n')
        y_position = height - 50
        
        for line in lines:
            if y_position < 50:  # Start new page if needed
                c.showPage()
                y_position = height - 50
            c.drawString(50, y_position, line[:80])  # Limit line length
            y_position -= 20
        
        c.save()
        
        # Get user uid
        user_uid = get_user_uid_by_email(user_email)
        if not user_uid:
            user_uid = "default-user"
            logger.warning(f"⚠️ No user uid found for {user_email}, using default-user")
        
        # Upload to S3
        session = get_aws_session()
        s3_client = session.client('s3')
        
        now = datetime.now()
        year = now.strftime("%Y")
        month = now.strftime("%m")
        day = now.strftime("%d")
        time_prefix = now.strftime("%H%M%S")
        
        s3_key = f"{user_uid}/{year}/{month}/{day}/{time_prefix}_{filename}"
        
        s3_client.upload_file(temp_path, "str-data-store-bucket", s3_key)
        
        # Clean up temp file
        os.unlink(temp_path)
        
        logger.info(f"✅ Text converted to PDF and uploaded: s3://str-data-store-bucket/{s3_key}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Text to PDF upload failed: {e}")
        return False

def save_file_to_s3(file_path: str, user_email: str, s3_path: str, metadata: Dict[str, str] = None) -> bool:
    """
    Save any file to tenant-specific S3 bucket with flexible path structure
    Following the same pattern as the LogManager for tenant-specific uploads
    
    Args:
        file_path (str): Local path to the file to upload
        user_email (str): User's email address for tenant lookup
        s3_path (str): S3 path where the file should be saved (e.g., "cognito/{email}/Data/{run_id}/test_results.json")
        metadata (Dict[str, str], optional): Additional metadata for the S3 object
        
    Returns:
        bool: True if upload was successful, False otherwise
    """
    try:
        from pathlib import Path
        
        # Get tenant-specific bucket name using the same logic as LogManager
        try:
            tenant_domain = get_tenant_domain_by_email(user_email)
            if tenant_domain:
                bucket_name = tenant_domain
            else:
                bucket_name = 'ai-colleagues-logs-default'
        except Exception as e:
            bucket_name = 'ai-colleagues-logs-default'
            logger.warning(f"⚠️ Failed to get tenant bucket, using default: {e}")
        
        # Set up AWS session and S3 client
        session = get_aws_session()
        s3_client = session.client('s3')
        
        # Ensure bucket exists (same logic as LogManager)
        try:
            s3_client.head_bucket(Bucket=bucket_name)
            logger.info(f"✅ Bucket {bucket_name} exists")
        except s3_client.exceptions.NoSuchBucket:
            try:
                logger.info(f"🔧 Creating tenant bucket {bucket_name}...")
                if AWS_REGION == 'us-east-1':
                    s3_client.create_bucket(Bucket=bucket_name)
                else:
                    s3_client.create_bucket(
                        Bucket=bucket_name,
                        CreateBucketConfiguration={'LocationConstraint': AWS_REGION}
                    )
                logger.info(f"✅ Created tenant bucket {bucket_name}")
            except Exception as create_error:
                logger.warning(f"⚠️ Cannot create bucket {bucket_name} (likely permissions): {create_error}")
                logger.info(f"📝 Upload failed - bucket creation required")
                return False
        except Exception as e:
            logger.warning(f"⚠️ Error checking bucket {bucket_name}: {e}")
            return False
        
        # Use the provided S3 path directly
        s3_key = s3_path
        
        # Check if file already exists in S3
        try:
            s3_client.head_object(Bucket=bucket_name, Key=s3_key)
            logger.info(f"⏭️ File already exists in S3, overwriting: {Path(file_path).name}")
        except s3_client.exceptions.NoSuchKey:
            # File doesn't exist, proceed with upload
            pass
        except Exception as e:
            logger.warning(f"⚠️ Could not check if file exists in S3: {e}")
            # Proceed with upload anyway
            pass
        
        # Prepare default metadata
        default_metadata = {
            'source': 'text2agent-system',
            'user_email': user_email,
            'upload_time': datetime.now().isoformat()
        }
        
        # Merge with provided metadata
        if metadata:
            default_metadata.update(metadata)
        
        # Upload file
        s3_client.upload_file(
            file_path,
            bucket_name,
            s3_key,
            ExtraArgs={
                'StorageClass': 'STANDARD_IA',  # Infrequent Access for cost savings
                'Metadata': default_metadata
            }
        )
        
        logger.info(f"☁️ Uploaded file to s3://{bucket_name}/{s3_key}")
        print(f"☁️ File saved to S3: s3://{bucket_name}/{s3_key}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to upload file to S3: {e}")
        print(f"❌ Failed to upload file to S3: {e}")
        return False

def list_database_structure():
    """List all schemas and tables in the database for debugging"""
    try:
        # Get all schemas
        schema_query = """
        SELECT schema_name 
        FROM information_schema.schemata 
        WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
        ORDER BY schema_name
        """
        schemas = execute_query(schema_query)
        print("\n📊 Available Schemas:")
        for schema in schemas:
            print(f"  - {schema['schema_name']}")
        
        # Get all tables with their schemas
        table_query = """
        SELECT table_schema, table_name 
        FROM information_schema.tables 
        WHERE table_schema NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
        ORDER BY table_schema, table_name
        """
        tables = execute_query(table_query)
        print("\n📋 Available Tables:")
        for table in tables:
            print(f"  - {table['table_schema']}.{table['table_name']}")
            
        return {"schemas": schemas, "tables": tables}
        
    except Exception as e:
        logger.error(f"❌ Failed to list database structure: {e}")
        raise

def get_user_secret_name_by_email(email: str) -> Optional[str]:
    """Get user-specific secret name from AWS Secrets Manager based on email"""
    try:
        # First try to get tenant-specific secret name
        tenant_domain = get_tenant_domain_by_email(email)
        if tenant_domain:
            # Use tenant domain as secret name pattern
            secret_name = f"{tenant_domain}-credentials"
            logger.info(f"✅ Generated secret name for {email}: {secret_name}")
            return secret_name
        
        # Fallback: use user uid as secret name
        user_uid = get_user_uid_by_email(email)
        if user_uid:
            secret_name = f"user-{user_uid}-credentials"
            logger.info(f"✅ Generated fallback secret name for {email}: {secret_name}")
            return secret_name
        
        # Ultimate fallback: use email domain
        domain = email.split('@')[1].replace('.', '-')
        secret_name = f"{domain}-credentials"
        logger.warning(f"⚠️ Using domain-based secret name for {email}: {secret_name}")
        return secret_name
        
    except Exception as e:
        logger.error(f"❌ Failed to get secret name for {email}: {e}")
        return None

def get_user_credentials_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Get user-specific credentials from AWS Secrets Manager"""
    try:
        secret_name = get_user_secret_name_by_email(email)
        if not secret_name:
            logger.error(f"❌ Could not determine secret name for {email}")
            return None
        
        logger.info(f"🔐 Retrieving credentials for {email} from secret: {secret_name}")
        credentials = get_secret(secret_name)
        logger.info(f"✅ Successfully retrieved credentials for {email}")
        return credentials
        
    except Exception as e:
        logger.error(f"❌ Failed to retrieve credentials for {email}: {e}")
        return None