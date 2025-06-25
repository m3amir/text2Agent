import json
import boto3
import psycopg2
import uuid
import os
import time
import re
from datetime import datetime

def lambda_handler(event, context):
    """
    Cognito Post Confirmation Lambda Trigger
    Creates tenant buckets, user folder structure, and manages tenant/user data in PostgreSQL
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

        # Check if tenant already exists in database
        existing_tenant_id = tenant_exists(domain)
        
        if existing_tenant_id:
            print(f"Tenant already exists with ID: {existing_tenant_id}")
            tenant_bucket = generate_bucket_name(existing_tenant_id, domain)
            
            # Only add user if user doesn't already exist
            if not user_exists(email):
                insert_user_to_db(email, name, existing_tenant_id)
            else:
                print(f"User {email} already exists in tenant {existing_tenant_id}")
        else:
            # Create new tenant
            generated_uuid = str(uuid.uuid4())
            tenant_bucket = generate_bucket_name(generated_uuid, domain)
            print(f"Creating new tenant with ID: {generated_uuid}")
            
            # Create bucket first
            if create_tenant_bucket(tenant_bucket):
                # Only save to DB if bucket creation succeeded
                save_tenant_to_db(domain, generated_uuid)
                insert_user_to_db(email, name, generated_uuid)
            else:
                print(f"ERROR: Failed to create bucket {tenant_bucket}, skipping DB operations")
                return event
        
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

def generate_bucket_name(tenant_id, domain):
    """
    Generate a valid S3 bucket name
    """
    # Create a safe bucket name (S3 bucket names must be globally unique and follow strict rules)
    safe_domain = re.sub(r'[^a-z0-9-]', '-', domain.lower())
    safe_domain = re.sub(r'-+', '-', safe_domain).strip('-')
    
    # Shorten if too long (S3 bucket names max 63 chars)
    tenant_bucket = f"tenant-{tenant_id}-{safe_domain}"
    if len(tenant_bucket) > 63:
        tenant_bucket = f"tenant-{tenant_id}"[:63]
    
    # Ensure bucket name ends with alphanumeric (not hyphen)
    tenant_bucket = tenant_bucket.rstrip('-')
    
    # Validate bucket name
    if len(tenant_bucket) < 3:
        tenant_bucket = f"tenant-{tenant_id}"
    
    return tenant_bucket

def tenant_exists(domain):
    """
    Check if a tenant already exists for the given domain
    """
    try:
        username, password = getCredentials()
        connection = psycopg2.connect(
            user=username, 
            password=password, 
            host=os.getenv('Tenent_db', ''), 
            database='postgres'
        )
        cursor = connection.cursor()

        query = "SELECT tenant_id FROM \"Tenants\".tenantmappings WHERE domain = %s LIMIT 1;"
        cursor.execute(query, (domain,))
        result = cursor.fetchone()

        cursor.close()
        connection.close()
        return result[0] if result else None
    except Exception as e:
        print(f"Error checking tenant existence: {e}")
        return None

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
            database='postgres'
        )
        cursor = connection.cursor()

        query = "SELECT 1 FROM \"Tenants\".users WHERE email = %s;"
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
        print(f"Using tenant bucket: {bucket_name} (length: {len(bucket_name)})")
        print(f"Bucket name validation: starts_with_letter={bucket_name[0].isalpha()}, ends_with_alnum={bucket_name[-1].isalnum()}")
        
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
        
        print(f"Security policies applied to bucket '{bucket_name}'")
        
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
            database='postgres'
        )
        cursor = connection.cursor()

        # Generate bucket name for this tenant
        tenant_bucket = generate_bucket_name(tenant_id, domain)
        
        insert_query = """
            INSERT INTO "Tenants".tenantmappings (tenant_id, domain, bucket_name)
            VALUES (%s, %s, %s);
        """
        cursor.execute(insert_query, (tenant_id, domain, tenant_bucket))
        connection.commit()

        print(f"Tenant mapping inserted successfully: tenant_id='{tenant_id}', domain='{domain}', bucket='{tenant_bucket}'")
        cursor.close()
        connection.close()
    except Exception as e:
        print(f"Error inserting record for email '{email}': {e}")

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
            database='postgres'
        )
        cursor = connection.cursor()

        # Generate user_id (UUID format)
        user_id = str(uuid.uuid4())
        
        insert_query = """
            INSERT INTO "Tenants".users (user_id, email, name, tenant_id)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (email) DO NOTHING;
        """
        cursor.execute(insert_query, (user_id, email, name or email.split('@')[0], tenant_id))
        connection.commit()

        print(f"User record inserted: user_id='{user_id}', email='{email}', tenant_id='{tenant_id}'")
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
            print(f"Bucket '{bucket_name}' exists. Proceeding to create user folders.")
            break
        except Exception as e:
            if attempt < retries - 1:
                print(f"Attempt {attempt + 1}: Bucket '{bucket_name}' not accessible yet. Retrying...")
                time.sleep(2)
            else:
                print(f"ERROR: Bucket '{bucket_name}' does not exist. Error: {e}")
                return False

    # Create folder structure
    try:
        s3.put_object(Bucket=bucket_name, Key=user_folder)
        print(f"User folder '{user_folder}' created successfully in bucket '{bucket_name}'.")
        
        s3.put_object(Bucket=bucket_name, Key=data_folder)
        print(f"Sub-folder 'Data' created successfully in '{user_folder}'.")
        
        s3.put_object(Bucket=bucket_name, Key=logs_folder)
        print(f"Sub-folder 'Logs' created successfully in '{user_folder}'.")
        
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
    
    print(f"🔍 DEBUG: Attempting to retrieve secret...")
    print(f"🔑 Secret Name: {secret_name}")
    print(f"🌍 Region: {region_name}")
    print(f"📋 Environment Variables:")
    print(f"   - DB_SECRET_NAME = {os.getenv('DB_SECRET_NAME', 'NOT_SET')}")
    print(f"   - DB_REGION = {os.getenv('DB_REGION', 'NOT_SET')}")
    print(f"   - Tenent_db = {os.getenv('Tenent_db', 'NOT_SET')}")
    
    try:
        client = boto3.client(service_name='secretsmanager', region_name=region_name)
        
        # List available secrets for debugging
        try:
            response = client.list_secrets(MaxResults=20)
            print(f"📝 Available secrets in region {region_name}:")
            for secret in response.get('SecretList', []):
                print(f"   - {secret['Name']}")
        except Exception as list_error:
            print(f"⚠️  Could not list secrets: {list_error}")
        
        # Try to get the secret
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        secret = json.loads(get_secret_value_response['SecretString'])
        
        print(f"✅ Successfully retrieved credentials from secret: {secret_name}")
        return secret['username'], secret['password']
    except Exception as e:
        print(f"❌ Error retrieving credentials from secret '{secret_name}': {e}")
        print(f"🔧 Check if secret exists and Lambda has proper permissions")
        raise 