import boto3
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from pathlib import Path
# Import database function for tenant mapping
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils.core import get_tenant_domain_by_email

class LogManager:
    """Manages logging and syncing to tenant-specific S3 buckets"""
    
    def __init__(self, email: str, profile_name: str = 'm3', region_name: str = 'us-east-1'):
        self.email = email
        self.profile_name = profile_name
        self.region_name = region_name
        
        try:
            # Try to use AWS profile first (for local development)
            self.session = boto3.Session(profile_name=profile_name, region_name=region_name)
        except Exception:
            # Fall back to environment variables (for GitHub Actions/CI)
            self.session = boto3.Session(region_name=region_name)
            
        self.s3_client = self.session.client('s3')
        
        # Get tenant-specific bucket name
        self.tenant_bucket = self._get_tenant_bucket_name()
        
        # Create organized local directory structure: Logs/tenant/email/
        base_logs_dir = Path(__file__).parent
        self.tenant_name = self.tenant_bucket.replace('tenant-', '').split('-m3labs')[0]  # Extract clean tenant name
        
        # Create the organized directory structure - keep original email format
        self.logs_dir = base_logs_dir / self.tenant_name / email
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        # S3 path structure: cognito/{email}/Logs/
        self.base_s3_path = f"cognito/{email}/Logs"
        
        self.logger = self._setup_manager_logging()
    
    def _get_tenant_bucket_name(self) -> str:
        """Get the tenant-specific bucket name based on email"""
        try:
            tenant_domain = get_tenant_domain_by_email(self.email)
            if tenant_domain:
                return tenant_domain
            else:
                return 'ai-colleagues-logs-default'
        except Exception as e:
            return 'ai-colleagues-logs-default'
    
    def _setup_manager_logging(self) -> logging.Logger:
        """Set up logging for the LogManager itself"""
        logger = logging.getLogger('LogManager')
        logger.setLevel(logging.INFO)
        
        # Clear existing handlers to prevent duplicates
        if logger.handlers:
            logger.handlers.clear()
        
        # Only add handler if none exist
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        # Prevent propagation to avoid duplicate messages from root logger
        logger.propagate = False
        
        return logger
    
    def ensure_bucket_exists(self) -> bool:
        """Ensure the tenant-specific S3 bucket exists, create if it doesn't"""
        try:
            bucket_name = self.tenant_bucket
            
            try:
                self.s3_client.head_bucket(Bucket=bucket_name)
                self.logger.info(f"✅ Bucket {bucket_name} exists")
                return True
            except self.s3_client.exceptions.NoSuchBucket:
                self.logger.info(f"🔧 Creating tenant bucket {bucket_name}...")
                if self.region_name == 'us-east-1':
                    self.s3_client.create_bucket(Bucket=bucket_name)
                else:
                    self.s3_client.create_bucket(
                        Bucket=bucket_name,
                        CreateBucketConfiguration={'LocationConstraint': self.region_name}
                    )
                self.logger.info(f"✅ Created tenant bucket {bucket_name}")
                return True
            except Exception as e:
                self.logger.error(f"❌ Error checking bucket {bucket_name}: {e}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error ensuring bucket exists: {e}")
            return False
    
    def categorize_log_file(self, log_file_path: Path) -> str:
        """Categorize log file based on its name"""
        filename = log_file_path.name.lower()
        
        if 'colleagues' in filename:
            return 'ai_colleagues'
        elif 'skeleton' in filename:
            return 'ai_skeleton'
        elif 'str' in filename:
            return 'str'
        elif 'llm' in filename or 'bedrock' in filename:
            return 'llm_interactions'
        elif 'error' in filename or 'exception' in filename:
            return 'system_errors'
        else:
            return 'ai_colleagues'  # Default category
    
    def upload_to_s3(self, local_file_path: Path, category: str) -> bool:
        """Upload log file to tenant-specific S3 bucket"""
        try:
            bucket_name = self.tenant_bucket
            
            # Create S3 key with organized structure: cognito/{email}/Logs/{category}/{date}/{filename}
            timestamp = datetime.now().strftime("%Y/%m/%d")
            s3_key = f"{self.base_s3_path}/{category}/{timestamp}/{local_file_path.name}"
            
            # Check if file already exists in S3
            try:
                self.s3_client.head_object(Bucket=bucket_name, Key=s3_key)
                self.logger.info(f"⏭️  File already exists in S3, skipping: {local_file_path.name}")
                return True  # Consider this a success since file is already there
                
            except self.s3_client.exceptions.NoSuchKey:
                # File doesn't exist, proceed with upload
                pass
            except Exception as e:
                self.logger.warning(f"⚠️  Could not check if file exists in S3: {e}")
                # Proceed with upload anyway
                pass
            
            # Upload file
            self.s3_client.upload_file(
                str(local_file_path), 
                bucket_name, 
                s3_key,
                ExtraArgs={
                    'StorageClass': 'STANDARD_IA',  # Infrequent Access for cost savings
                    'Metadata': {
                        'source': 'ai-colleagues-system',
                        'category': category,
                        'user_email': self.email,
                        'upload_time': datetime.now().isoformat()
                    }
                }
            )
            
            self.logger.info(f"☁️  Uploaded {local_file_path.name} to s3://{bucket_name}/{s3_key}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to upload {local_file_path.name}: {e}")
            return False
    
    def sync_logs(self, older_than_hours: int = 1) -> Dict[str, List[str]]:
        """Sync logs to tenant-specific S3 bucket that are older than specified hours"""
        results = {
            'synced': [],
            'failed': [],
            'skipped': [],
            'already_exists': []
        }
        
        if not self.ensure_bucket_exists():
            self.logger.error("❌ Cannot sync - bucket setup failed")
            return results
        
        cutoff_time = datetime.now() - timedelta(hours=older_than_hours)
        # Add safety buffer - don't sync files newer than 2 minutes to avoid interfering with active logging
        safety_buffer_time = datetime.now() - timedelta(minutes=2)
        
        # Find all log files in the logs directory
        log_files = list(self.logs_dir.glob('*.log'))
        
        for log_file in log_files:
            try:
                # Check if file is old enough
                file_time = datetime.fromtimestamp(log_file.stat().st_mtime)
                if file_time > cutoff_time:
                    results['skipped'].append(log_file.name)
                    continue
                
                # Safety check - don't sync very recent files (they might be actively written to)
                if file_time > safety_buffer_time:
                    results['skipped'].append(log_file.name)
                    self.logger.info(f"⏰ Skipping recent file (active logging): {log_file.name}")
                    continue
                
                # Skip empty files
                if log_file.stat().st_size == 0:
                    self.logger.info(f"⚠️  Skipping empty file: {log_file.name}")
                    results['skipped'].append(log_file.name)
                    continue
                
                # Categorize and upload
                category = self.categorize_log_file(log_file)
                
                if self.upload_to_s3(log_file, category):
                    results['synced'].append(log_file.name)
                else:
                    results['failed'].append(log_file.name)
                    
            except Exception as e:
                self.logger.error(f"❌ Error processing {log_file.name}: {e}")
                results['failed'].append(log_file.name)
        
        # Log summary
        self.logger.info(f"📊 Sync Summary - Synced: {len(results['synced'])}, Failed: {len(results['failed'])}, Skipped: {len(results['skipped'])}, Already Exists: {len(results['already_exists'])}")
        
        return results
    
    def force_upload_current_log(self, log_filename: str) -> bool:
        """Force upload a specific log file to S3, bypassing safety buffer"""
        try:
            log_file = self.logs_dir / log_filename
            
            if not log_file.exists():
                self.logger.warning(f"⚠️  Log file not found: {log_filename}")
                return False
                
            # Skip empty files
            if log_file.stat().st_size == 0:
                self.logger.warning(f"⚠️  Skipping empty file: {log_filename}")
                return False
            
            # Ensure bucket exists
            if not self.ensure_bucket_exists():
                self.logger.error("❌ Cannot upload - bucket setup failed")
                return False
            
            # Categorize and upload immediately (bypass safety buffer)
            category = self.categorize_log_file(log_file)
            
            # Force upload
            if self.upload_to_s3(log_file, category):
                self.logger.info(f"🚀 Force uploaded: {log_filename}")
                return True
            else:
                self.logger.error(f"❌ Failed to force upload: {log_filename}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error force uploading {log_filename}: {e}")
            return False
        