import json
import boto3
import psycopg2
import uuid
import os
import time
import re
from datetime import datetime

# UPDATED VERSION - Fixed database schema compatibility and secret retrieval - 2025-06-25

def lambda_handler(event, context):
    """
    Cognito Post Confirmation Lambda Trigger
    Creates tenant buckets, user folder structure, and manages tenant/user data in PostgreSQL
    """
    try:
        # Extract user information from the event
        user_pool_id = event.get('userPoolId', '')
        user_name = event.get('userName', '')
        user_attributes = event.get('request', {}).get('userAttributes', {})
        
        email = user_attributes.get('email', '')
        name = user_attributes.get('name', '')
        email_verified = user_attributes.get('email_verified', 'false')
        
        print(f"Processing post-confirmation for user: {email}")
        
        # Validate required fields
        if not email:
            print("ERROR: No email found in user attributes")
            return event  # Don't block user registration
            
        domain = email.split('@')[1] if '@' in email else 'unknown'

        # Check if tenant already exists in database
        existing_tenant_id = tenant_exists(domain)
        
        if existing_tenant_id:
            print(f"Existing tenant found for domain {domain}: {existing_tenant_id}")
            tenant_bucket = generate_bucket_name(existing_tenant_id, domain)
            
            # Check if bucket exists, recreate if needed (resilience to bucket deletion)
            if not bucket_exists(tenant_bucket):
                print(f"Bucket {tenant_bucket} was deleted/missing, recreating with original name...")
                
                if create_tenant_bucket(tenant_bucket):
                    # Update database with the correct bucket name (removes any old timestamp suffixes)
                    update_tenant_bucket(existing_tenant_id, tenant_bucket)
                    print(f"Successfully recreated bucket and updated database: {tenant_bucket}")
                else:
                    print(f"ERROR: Failed to recreate bucket for tenant {existing_tenant_id}")
                    return event
            else:
                print(f"Bucket {tenant_bucket} exists and is accessible")
            
            # Only add user if user doesn't already exist
            if not user_exists(email):
                insert_user_to_db(email, name, existing_tenant_id)
                print(f"User {email} added to existing tenant")
            else:
                print(f"User {email} already exists in tenant")
        else:
            # Create new tenant
            generated_uuid = str(uuid.uuid4())
            tenant_bucket = generate_bucket_name(generated_uuid, domain)
            print(f"Creating new tenant for domain {domain}")
            
            # Create bucket first
            if create_tenant_bucket(tenant_bucket):
                # Only save to DB if bucket creation succeeded
                save_tenant_to_db(domain, generated_uuid)
                insert_user_to_db(email, name, generated_uuid)
                print(f"New tenant created with ID: {generated_uuid}")
            else:
                print(f"ERROR: Failed to create bucket {tenant_bucket}")
                return event
        
        # Create user folders in the tenant bucket
        create_user_folders(tenant_bucket, email)
        
        print(f"Post-confirmation completed successfully for {email}")
        
        # Return the event unchanged (required for Cognito triggers)
        return event
        
    except Exception as e:
        print(f"ERROR in post-confirmation Lambda: {str(e)}")
        # Don't raise the exception - we don't want to block user registration
        return event

def generate_bucket_name(tenant_id, domain):
    """
    Generate a valid S3 bucket name (old format - preserving dots)
    """
    # Use the original format that preserves dots in domain
    tenant_bucket = f"tenant-{tenant_id}-{domain.lower()}"
    
    # Ensure bucket name is within limits
    if len(tenant_bucket) > 63:
        tenant_bucket = f"tenant-{tenant_id}"[:63]
    
    return tenant_bucket

def tenant_exists(domain):
    """
    Check if a tenant already exists for the given domain
    Returns tenant_id if exists, None otherwise
    """
    try:
        username, password = getCredentials()
        connection = psycopg2.connect(
            user=username, 
            password=password, 
            host=os.getenv('Tenent_db', ''), 
            database='text2AgentTenants'
        )
        cursor = connection.cursor()

        query = "SELECT tenant_id FROM tenantmappings WHERE domain = %s LIMIT 1;"
        cursor.execute(query, (domain,))
        result = cursor.fetchone()

        cursor.close()
        connection.close()
        return result[0] if result else None
    except Exception as e:
        print(f"Error checking tenant existence: {e}")
        return None

def bucket_exists(bucket_name):
    """
    Check if an S3 bucket exists and is accessible
    """
    if not bucket_name:
        return False
        
    s3 = boto3.client('s3')
    try:
        s3.head_bucket(Bucket=bucket_name)
        print(f"Bucket '{bucket_name}' exists and is accessible")
        return True
    except Exception as e:
        error_code = getattr(e.response, 'Error', {}).get('Code', 'Unknown') if hasattr(e, 'response') else 'Unknown'
        if error_code == 'NoSuchBucket' or '404' in str(e):
            print(f"Bucket '{bucket_name}' does not exist")
        elif error_code == 'Forbidden' or '403' in str(e):
            print(f"No permission to access bucket '{bucket_name}'")
        else:
            print(f"Error checking bucket '{bucket_name}': {e}")
        return False

def update_tenant_bucket(tenant_id, new_bucket_name):
    """
    Update the bucket name for an existing tenant in the database
    """
    try:
        username, password = getCredentials()
        connection = psycopg2.connect(
            user=username, 
            password=password, 
            host=os.getenv('Tenent_db', ''), 
            database='text2AgentTenants'
        )
        cursor = connection.cursor()

        update_query = """
            UPDATE tenantmappings 
            SET bucket_name = %s
            WHERE tenant_id = %s;
        """
        cursor.execute(update_query, (new_bucket_name, tenant_id))
        connection.commit()

        if cursor.rowcount > 0:
            print(f"Updated bucket name for tenant {tenant_id} to {new_bucket_name}")
        else:
            print(f"Warning: No tenant found with ID {tenant_id} to update")

        cursor.close()
        connection.close()
        return True
    except Exception as e:
        print(f"Error updating bucket name for tenant {tenant_id}: {e}")
        return False

def user_exists(email):
    """
    Check if a user already exists in the users table
    """
    try:
        username, password = getCredentials()
        connection = psycopg2.connect(
            user=username, 
            password=password, 
            host=os.getenv('Tenent_db', ''), 
            database='text2AgentTenants'
        )
        cursor = connection.cursor()

        query = "SELECT 1 FROM users WHERE email = %s;"
        cursor.execute(query, (email,))
        result = cursor.fetchone()

        cursor.close()
        connection.close()
        return True if result else False
    except Exception as e:
        print(f"Error checking user existence for email {email}: {e}")
        return False

def create_tenant_bucket(bucket_name):
    """
    Create S3 bucket for tenant with enhanced error handling
    """
    s3 = boto3.client('s3')
    try:
        # Check if bucket already exists
        try:
            s3.head_bucket(Bucket=bucket_name)
            return True  # Bucket already exists
        except Exception as e:
            error_code = getattr(e.response, 'Error', {}).get('Code', 'Unknown') if hasattr(e, 'response') else 'Unknown'
            if error_code == 'NoSuchBucket' or '404' in str(e):
                pass  # Bucket doesn't exist, create it
            elif error_code == 'Forbidden' or '403' in str(e):
                print(f"ERROR: No permission to access bucket '{bucket_name}': {e}")
                return False
            else:
                print(f"ERROR checking bucket existence: {e}")
                return False
            
        # Create bucket with proper region configuration
        region = os.environ.get('AWS_REGION', 'eu-west-2')
        
        try:
            if region == 'us-east-1':
                s3.create_bucket(Bucket=bucket_name)
            else:
                s3.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={'LocationConstraint': region}
                )
                
            print(f"Bucket '{bucket_name}' created successfully")
        except Exception as create_error:
            error_code = getattr(create_error.response, 'Error', {}).get('Code', 'Unknown') if hasattr(create_error, 'response') else 'Unknown'
            
            # Handle race condition where another Lambda created the bucket
            if error_code == 'BucketAlreadyExists' or 'BucketAlreadyExists' in str(create_error):
                print(f"Bucket '{bucket_name}' already exists (created by another process)")
                # Check if we can access it
                if bucket_exists(bucket_name):
                    print(f"Bucket '{bucket_name}' is accessible, proceeding")
                    return True
                else:
                    print(f"Bucket '{bucket_name}' exists but not accessible")
                    return False
            elif error_code == 'BucketAlreadyOwnedByYou' or 'BucketAlreadyOwnedByYou' in str(create_error):
                print(f"Bucket '{bucket_name}' already owned by us")
                return True
            else:
                print(f"ERROR creating bucket '{bucket_name}': {create_error}")
                
                # Check if it's a bucket name issue
                if 'InvalidBucketName' in str(create_error):
                    print(f"Bucket name '{bucket_name}' is invalid. Length: {len(bucket_name)}")
                
                return False
        
        # Add bucket policy for security
        add_bucket_security_policy(bucket_name)
        
        return True
        
    except Exception as e:
        print(f"ERROR in create_tenant_bucket: {e}")
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
        
    except Exception as e:
        print(f"ERROR applying security policies to bucket '{bucket_name}': {e}")

def save_tenant_to_db(domain, tenant_id):
    """
    Save tenant mapping to database
    """
    try:
        username, password = getCredentials()
        connection = psycopg2.connect(
            user=username, 
            password=password, 
            host=os.getenv('Tenent_db', ''), 
            database='text2AgentTenants'
        )
        cursor = connection.cursor()

        # Generate bucket name for this tenant
        tenant_bucket = generate_bucket_name(tenant_id, domain)
        
        insert_query = """
            INSERT INTO tenantmappings (tenant_id, domain, bucket_name)
            VALUES (%s, %s, %s);
        """
        cursor.execute(insert_query, (tenant_id, domain, tenant_bucket))
        connection.commit()

        cursor.close()
        connection.close()
    except Exception as e:
        print(f"Error inserting tenant record for domain '{domain}': {e}")

def insert_user_to_db(email, name, tenant_id):
    """
    Insert user record to database
    """
    try:
        username, password = getCredentials()
        connection = psycopg2.connect(
            user=username, 
            password=password, 
            host=os.getenv('Tenent_db', ''), 
            database='text2AgentTenants'
        )
        cursor = connection.cursor()

        # Generate user_id (UUID format)
        user_id = str(uuid.uuid4())
        
        insert_query = """
            INSERT INTO users (user_id, email, name, tenant_id)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (email) DO NOTHING;
        """
        cursor.execute(insert_query, (user_id, email, name or email.split('@')[0], tenant_id))
        connection.commit()

        cursor.close()
        connection.close()
    except Exception as e:
        print(f"Error inserting user '{email}': {e}")

def create_user_folders(bucket_name, email):
    """
    Create user folder structure in S3 bucket (original structure)
    """
    s3 = boto3.client('s3')
    user_folder = f"cognito/{email}/"
    data_folder = f"{user_folder}Data/"
    logs_folder = f"{user_folder}Logs/"

    # Wait for bucket to be ready
    retries = 3
    for attempt in range(retries):
        try:
            s3.head_bucket(Bucket=bucket_name)
            break
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2)
            else:
                print(f"ERROR: Bucket '{bucket_name}' not accessible: {e}")
                return False

    # Create folder structure
    try:
        s3.put_object(Bucket=bucket_name, Key=user_folder)
        s3.put_object(Bucket=bucket_name, Key=data_folder)
        s3.put_object(Bucket=bucket_name, Key=logs_folder)
        
        return True
        
    except Exception as e:
        print(f"Error creating user folders: {e}")
        return False

def getCredentials():
    """
    Get database credentials from AWS Secrets Manager
    """
    secret_name = os.getenv('DB_SECRET_NAME', 'text2agent-dev-db-credentials-v2')
    region_name = os.getenv('DB_REGION', 'eu-west-2')
    
    try:
        client = boto3.client(service_name='secretsmanager', region_name=region_name)
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        secret = json.loads(get_secret_value_response['SecretString'])
        
        return secret['username'], secret['password']
    except Exception as e:
        print(f"ERROR retrieving credentials from secret '{secret_name}': {e}")
        raise 