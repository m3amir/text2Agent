import json
import boto3
import uuid
import os
import time
from datetime import datetime

def lambda_handler(event, context):
    """
    Cognito Post Confirmation Lambda Trigger
    Creates tenant buckets and user folder structure after user confirmation
    """
    try:
        # Log the entire event for debugging
        print(f"Post confirmation event received: {json.dumps(event, indent=2)}")
        
        # Extract user information from the event
        user_pool_id = event.get('userPoolId', '')
        user_name = event.get('userName', '')
        user_attributes = event.get('request', {}).get('userAttributes', {})
        
        email = user_attributes.get('email', '')
        name = user_attributes.get('name', '')
        email_verified = user_attributes.get('email_verified', 'false')
        
        print(f"Processing post-confirmation for user: {user_name}")
        print(f"Name: {name}, Email: {email}, Verified: {email_verified}")
        print(f"User Pool ID: {user_pool_id}")
        
        # Validate required fields
        if not email:
            print("ERROR: No email found in user attributes")
            return event  # Don't block user registration
            
        domain = email.split('@')[1] if '@' in email else 'unknown'
        print(f"User domain: {domain}")

        # Check if tenant bucket exists, if not create it
        tenant_id = get_or_create_tenant(domain)
        
        # Create a safe bucket name (S3 bucket names must be globally unique and follow strict rules)
        import re
        safe_domain = re.sub(r'[^a-z0-9-]', '-', domain.lower())
        safe_domain = re.sub(r'-+', '-', safe_domain).strip('-')
        
        # Shorten if too long (S3 bucket names max 63 chars)
        tenant_bucket = f"text2agent-{tenant_id}-{safe_domain}"
        if len(tenant_bucket) > 63:
            tenant_bucket = f"text2agent-{tenant_id}"[:63]
        
        # Ensure bucket name ends with alphanumeric (not hyphen)
        tenant_bucket = tenant_bucket.rstrip('-')
        
        # Validate bucket name
        if len(tenant_bucket) < 3:
            tenant_bucket = f"text2agent-{tenant_id}"
        
        print(f"Using tenant bucket: {tenant_bucket} (length: {len(tenant_bucket)})")
        print(f"Bucket name validation: starts_with_letter={tenant_bucket[0].isalpha()}, ends_with_alnum={tenant_bucket[-1].isalnum()}")
        
        # Create user folders in the tenant bucket
        create_user_folders(tenant_bucket, email)
        
        print(f"Post-confirmation processing completed successfully for {email}")
        
        # Return the event unchanged (required for Cognito triggers)
        return event
        
    except Exception as e:
        print(f"ERROR in post-confirmation Lambda: {str(e)}")
        print(f"Event that caused error: {json.dumps(event, indent=2)}")
        # Don't raise the exception - we don't want to block user registration
        return event

def get_or_create_tenant(domain):
    """
    Get existing tenant ID for domain or create a new one
    Since we don't have database, we'll use a simple mapping approach
    """
    try:
        # For now, create a deterministic UUID based on domain
        # In production, this would check the database first
        import hashlib
        import re
        
        # Clean domain name for bucket naming (remove dots, make lowercase)
        clean_domain = re.sub(r'[^a-z0-9-]', '-', domain.lower())
        clean_domain = re.sub(r'-+', '-', clean_domain)  # Remove multiple hyphens
        clean_domain = clean_domain.strip('-')  # Remove leading/trailing hyphens
        
        # Create a deterministic hash based on domain (shorter)
        domain_hash = hashlib.md5(domain.encode()).hexdigest()[:6]
        
        # Create shorter, more reliable tenant ID
        tenant_id = f"{domain_hash}-{str(uuid.uuid4())[:6]}"
        
        print(f"Generated tenant ID {tenant_id} for domain {domain} (cleaned: {clean_domain})")
        return tenant_id
        
    except Exception as e:
        print(f"ERROR generating tenant ID: {e}")
        # Fallback to simple UUID
        return str(uuid.uuid4())[:8]

def create_tenant_bucket(bucket_name):
    """
    Create S3 bucket for tenant
    """
    s3 = boto3.client('s3')
    try:
        # Check if bucket already exists
        try:
            s3.head_bucket(Bucket=bucket_name)
            print(f"Bucket '{bucket_name}' already exists.")
            return True
        except Exception as e:
            error_code = getattr(e.response, 'Error', {}).get('Code', 'Unknown') if hasattr(e, 'response') else 'Unknown'
            if error_code == 'NoSuchBucket' or '404' in str(e):
                print(f"Bucket '{bucket_name}' doesn't exist, will create it.")
                pass  # Bucket doesn't exist, create it
            elif error_code == 'Forbidden' or '403' in str(e):
                print(f"ERROR: No permission to access bucket '{bucket_name}': {e}")
                return False
            else:
                print(f"ERROR checking bucket existence: {e} (Code: {error_code})")
                return False
            
        # Create bucket with proper region configuration
        region = os.environ.get('AWS_REGION', 'eu-west-2')
        print(f"Creating bucket '{bucket_name}' in region '{region}'")
        
        try:
            if region == 'us-east-1':
                s3.create_bucket(Bucket=bucket_name)
            else:
                s3.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={'LocationConstraint': region}
                )
                
            print(f"Bucket '{bucket_name}' created successfully.")
        except Exception as create_error:
            error_code = getattr(create_error.response, 'Error', {}).get('Code', 'Unknown') if hasattr(create_error, 'response') else 'Unknown'
            print(f"ERROR creating bucket '{bucket_name}': {create_error}")
            print(f"Error code: {error_code}")
            print(f"Full error details: {str(create_error)}")
            
            # Check if it's a bucket name issue
            if 'InvalidBucketName' in str(create_error):
                print(f"Bucket name '{bucket_name}' is invalid. Length: {len(bucket_name)}")
                print("S3 bucket naming rules: 3-63 chars, lowercase, no spaces, no dots at start/end")
            
            raise create_error
        
        # Add bucket policy for security
        add_bucket_security_policy(bucket_name)
        
        return True
        
    except Exception as e:
        print(f"ERROR creating bucket '{bucket_name}': {e}")
        return False

def add_bucket_security_policy(bucket_name):
    """
    Add security policy to the bucket
    """
    s3 = boto3.client('s3')
    try:
        # Block public access
        s3.put_public_access_block(
            Bucket=bucket_name,
            PublicAccessBlockConfiguration={
                'BlockPublicAcls': True,
                'IgnorePublicAcls': True,
                'BlockPublicPolicy': True,
                'RestrictPublicBuckets': True
            }
        )
        
        # Enable versioning
        s3.put_bucket_versioning(
            Bucket=bucket_name,
            VersioningConfiguration={'Status': 'Enabled'}
        )
        
        print(f"Security policies applied to bucket '{bucket_name}'")
        
    except Exception as e:
        print(f"ERROR applying security policies to bucket '{bucket_name}': {e}")

def create_user_folders(bucket_name, email):
    """
    Create user folder structure in S3 bucket
    """
    s3 = boto3.client('s3')
    
    # First ensure the bucket exists
    if not create_tenant_bucket(bucket_name):
        print(f"ERROR: Failed to create/access bucket {bucket_name}")
        return False
    
    user_folder = f"users/{email}/"
    folders = [
        f"{user_folder}data/",
        f"{user_folder}logs/",
        f"{user_folder}uploads/",
        f"{user_folder}processed/"
    ]

    # Wait a moment for bucket to be fully ready
    retries = 3
    for attempt in range(retries):
        try:
            s3.head_bucket(Bucket=bucket_name)
            print(f"Bucket '{bucket_name}' is accessible. Creating user folders.")
            break
        except Exception as e:
            if attempt < retries - 1:
                print(f"Attempt {attempt + 1}: Bucket '{bucket_name}' not ready yet. Retrying...")
                time.sleep(2)
            else:
                print(f"ERROR: Bucket '{bucket_name}' not accessible after retries. Error: {e}")
                return False

    # Create folder structure
    try:
        for folder in folders:
            s3.put_object(
                Bucket=bucket_name, 
                Key=folder,
                Body='',
                Metadata={
                    'created-by': 'post-confirmation-lambda',
                    'user-email': email,
                    'created-at': datetime.utcnow().isoformat()
                }
            )
            print(f"Created folder: {folder}")
            
        # Create a welcome file
        welcome_content = f"""Welcome to your tenant space!

User: {email}
Created: {datetime.utcnow().isoformat()}
Bucket: {bucket_name}

Your folder structure:
- data/: Store your data files here
- logs/: Application logs will be stored here  
- uploads/: Temporary upload area
- processed/: Processed files will be moved here
"""
        
        s3.put_object(
            Bucket=bucket_name,
            Key=f"{user_folder}README.txt",
            Body=welcome_content,
            Metadata={
                'created-by': 'post-confirmation-lambda',
                'user-email': email
            }
        )
        
        print(f"User folder structure created successfully for {email} in bucket {bucket_name}")
        return True
        
    except Exception as e:
        print(f"ERROR creating user folders: {e}")
        return False 