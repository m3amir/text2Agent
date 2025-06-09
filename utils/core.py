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
SECRET_NAME = 'rds!db-0534ea7e-2933-421d-96a0-c6d80af7fdc4'
DB_HOST = 'text2agent-db.cluqugi4urqi.eu-west-2.rds.amazonaws.com'
DB_PORT = 5432
DB_NAME = 'postgres'

# Global session and credentials cache
_aws_session = None
_db_credentials = None

def setup_logging(user_email: str, component_name: str, log_manager=None):
    """
    Centralized logging setup for all components
    
    Args:
        user_email (str): User's email address
        component_name (str): Name of the component (e.g., 'AI_Colleagues', 'STR')
        log_manager: Optional LogManager instance for organized directory structure
    
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
        
        # Console handler
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
        SELECT uid 
        FROM "Tenants".users 
        WHERE email = %s
        """
        results = execute_query(query, (email,))
        
        if results:
            uid = results[0]['uid']
            logger.info(f"✅ Found uid for email: {email}")
            return uid
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

# if __name__ == "__main__":
#     # Test the add_str_record method with 20 AI agent task records
#     print("🧪 Testing add_str_record method with 20 AI agent tasks...")
    
#     # Define 20 realistic AI agent tasks
#     test_records = [
#         {
#             "task_desc": "Summarize research papers from arXiv on machine learning",
#             "tools": "transformers,nltk,spacy,requests,beautifulsoup",
#             "score": 0.87,
#             "record_id": "agent_001",
#             "reflection_steps": 3,
#             "ai_desc": "Multi-document summarization with domain-specific terminology handling"
#         },
#         {
#             "task_desc": "Analyze sales data and generate monthly performance reports",
#             "tools": "pandas,numpy,matplotlib,seaborn,openpyxl",
#             "score": 0.92,
#             "record_id": "agent_002",
#             "reflection_steps": 2,
#             "ai_desc": "Automated business intelligence with visualization and trend analysis"
#         },
#         {
#             "task_desc": "Monitor competitor pricing from e-commerce websites",
#             "tools": "requests,beautifulsoup,selenium,pandas,schedule",
#             "score": 0.78,
#             "record_id": "agent_003",
#             "reflection_steps": 4,
#             "ai_desc": "Web scraping with anti-bot detection and data validation"
#         },
#         {
#             "task_desc": "Process and classify customer support images",
#             "tools": "opencv,pillow,tensorflow,scikit-learn,numpy",
#             "score": 0.89,
#             "record_id": "agent_004",
#             "reflection_steps": 3,
#             "ai_desc": "Computer vision pipeline for automated ticket categorization"
#         },
#         {
#             "task_desc": "Generate personalized email marketing content",
#             "tools": "openai,transformers,langchain,jinja2,smtplib",
#             "score": 0.85,
#             "record_id": "agent_005",
#             "reflection_steps": 2,
#             "ai_desc": "Natural language generation with customer segmentation integration"
#         },
#         {
#             "task_desc": "Sync data between multiple databases and APIs",
#             "tools": "sqlalchemy,psycopg2,pymongo,requests,celery",
#             "score": 0.94,
#             "record_id": "agent_006",
#             "reflection_steps": 1,
#             "ai_desc": "Real-time data synchronization with conflict resolution"
#         },
#         {
#             "task_desc": "Build and deploy REST API for customer analytics",
#             "tools": "fastapi,uvicorn,pydantic,sqlalchemy,redis",
#             "score": 0.91,
#             "record_id": "agent_007",
#             "reflection_steps": 2,
#             "ai_desc": "High-performance API with caching and authentication"
#         },
#         {
#             "task_desc": "Train and deploy fraud detection model",
#             "tools": "scikit-learn,xgboost,pandas,mlflow,docker",
#             "score": 0.96,
#             "record_id": "agent_008",
#             "reflection_steps": 5,
#             "ai_desc": "End-to-end ML pipeline with model versioning and monitoring"
#         },
#         {
#             "task_desc": "Extract and analyze data from PDF financial reports",
#             "tools": "pdfplumber,tabula,pandas,regex,openpyxl",
#             "score": 0.83,
#             "record_id": "agent_009",
#             "reflection_steps": 4,
#             "ai_desc": "Document processing with table extraction and data validation"
#         },
#         {
#             "task_desc": "Automate customer onboarding email sequences",
#             "tools": "smtplib,email,jinja2,schedule,sqlite3",
#             "score": 0.88,
#             "record_id": "agent_010",
#             "reflection_steps": 2,
#             "ai_desc": "Event-driven email automation with personalization and tracking"
#         },
#         {
#             "task_desc": "Build real-time chat moderation system for social platforms",
#             "tools": "transformers,torch,redis,fastapi,websockets",
#             "score": 0.93,
#             "record_id": "agent_011",
#             "reflection_steps": 3,
#             "ai_desc": "NLP-based content filtering with real-time processing and alerts"
#         },
#         {
#             "task_desc": "Create automated code review assistant for pull requests",
#             "tools": "github,pygithub,ast,pylint,transformers",
#             "score": 0.86,
#             "record_id": "agent_012",
#             "reflection_steps": 4,
#             "ai_desc": "Static analysis and AI-powered code quality assessment"
#         },
#         {
#             "task_desc": "Deploy smart inventory management with demand forecasting",
#             "tools": "pandas,scikit-learn,prophet,sqlite3,matplotlib",
#             "score": 0.91,
#             "record_id": "agent_013",
#             "reflection_steps": 3,
#             "ai_desc": "Time series forecasting with automated reordering triggers"
#         },
#         {
#             "task_desc": "Build voice-to-text meeting transcription service",
#             "tools": "whisper,pyaudio,flask,celery,postgresql",
#             "score": 0.89,
#             "record_id": "agent_014",
#             "reflection_steps": 2,
#             "ai_desc": "Speech recognition with speaker identification and summarization"
#         },
#         {
#             "task_desc": "Implement dynamic pricing optimization for e-commerce",
#             "tools": "scipy,numpy,requests,mongodb,plotly",
#             "score": 0.95,
#             "record_id": "agent_015",
#             "reflection_steps": 4,
#             "ai_desc": "Market-based pricing with competitor analysis and profit optimization"
#         },
#         {
#             "task_desc": "Create automated social media content scheduler",
#             "tools": "tweepy,facebook-sdk,pillow,schedule,mysql",
#             "score": 0.84,
#             "record_id": "agent_016",
#             "reflection_steps": 2,
#             "ai_desc": "Multi-platform posting with optimal timing and engagement tracking"
#         },
#         {
#             "task_desc": "Build document similarity search engine",
#             "tools": "elasticsearch,sentence-transformers,faiss,fastapi,docker",
#             "score": 0.92,
#             "record_id": "agent_017",
#             "reflection_steps": 3,
#             "ai_desc": "Semantic search with vector embeddings and relevance ranking"
#         },
#         {
#             "task_desc": "Deploy automated log analysis and anomaly detection",
#             "tools": "elasticsearch,logstash,kibana,scikit-learn,kafka",
#             "score": 0.90,
#             "record_id": "agent_018",
#             "reflection_steps": 5,
#             "ai_desc": "Real-time log processing with ML-based anomaly detection"
#         },
#         {
#             "task_desc": "Create intelligent resume screening system",
#             "tools": "spacy,nltk,pandas,scikit-learn,streamlit",
#             "score": 0.87,
#             "record_id": "agent_019",
#             "reflection_steps": 3,
#             "ai_desc": "NLP-based candidate matching with bias detection and ranking"
#         },
#         {
#             "task_desc": "Build automated financial portfolio rebalancing tool",
#             "tools": "yfinance,numpy,scipy,matplotlib,postgresql",
#             "score": 0.94,
#             "record_id": "agent_020",
#             "reflection_steps": 4,
#             "ai_desc": "Risk-adjusted portfolio optimization with automated trading signals"
#         }
#     ]
    
#     # Insert all test records to database
#     print("\n💾 Inserting records to database...")
#     success_count = 0
#     for i, record in enumerate(test_records, 1):
#         print(f"\n📝 Inserting record {i}/20: {record['task_desc'][:50]}...")
        
#         success = add_str_record(
#             task_desc=record["task_desc"],
#             tools=record["tools"],
#             score=record["score"],
#             record_id=record["record_id"],
#             reflection_steps=record["reflection_steps"],
#             ai_desc=record["ai_desc"]
#         )
        
#         if success:
#             success_count += 1
#             print(f"✅ Record {i} inserted successfully!")
#         else:
#             print(f"❌ Failed to insert record {i}")
    
#     print(f"\n🏁 Database insertion completed: {success_count}/20 records inserted successfully.")
    
#     # Create separate PDF for each test record
#     print("\n📄 Creating PDF files for each agent task...")
#     pdf_success_count = 0
    
#     for i, record in enumerate(test_records, 1):
#         print(f"\n📄 Creating PDF {i}/20: {record['record_id']}")
        
#         # Create formatted text content for each record
#         text_content = f"""AI Agent Task Record

# Task ID: {record['record_id']}
# Task Description: {record['task_desc']}
# Tools Used: {record['tools']}
# Performance Score: {record['score']}
# Reflection Steps: {record['reflection_steps']}
# AI Description: {record['ai_desc']}

# Details:
# This task demonstrates the capabilities of an AI agent system designed to handle complex automation challenges. The agent successfully completed the task using a combination of specialized tools and iterative refinement through reflection steps.

# Key components:
# - Task-specific tool integration: {record['tools'].replace(',', ', ')}
# - Performance optimization achieving {record['score']:.1%} success rate
# - Iterative improvement through {record['reflection_steps']} reflection cycles
# - Advanced AI capabilities: {record['ai_desc']}

# The agent's performance was evaluated based on task completion accuracy, tool utilization efficiency, and overall system reliability. The reflection steps allowed for continuous improvement and adaptation to task-specific requirements."""
        
#         # Create unique filename for each record
#         filename = f"{record['record_id']}_analysis_report.pdf"
        
#         # Upload to S3
#         pdf_success = upload_text_as_pdf_to_s3(text_content, "amir@m3labs.co.uk", filename)
        
#         if pdf_success:
#             pdf_success_count += 1
#             print(f"✅ PDF {i} created and uploaded successfully!")
#         else:
#             print(f"❌ Failed to create PDF {i}")
    
#     print(f"\n🏁 PDF creation completed: {pdf_success_count}/20 PDFs created successfully.")
    
#     print("🏁 All tests completed.")