import json
import boto3
import psycopg2
import uuid
import os
import time

def lambda_handler(event, context):
    print(event)
    # Get User Pool ID from the event context instead of environment variable
    user_pool_id = event.get('userPoolId', '')

    email = event['request']['userAttributes']['email']
    domain = email.split('@')[1]

    existing_tenant_id = tenant_exists(domain)
    
    if existing_tenant_id:
        print(f"Tenant already exists with ID: {existing_tenant_id}")
        tenant_bucket = f"tenant-{existing_tenant_id}-{domain}"

        if not tenant_mapping_exists(email):
            save_tenant_to_db(domain, email, existing_tenant_id)
            insert_user_to_db(email, existing_tenant_id)
    else:
        generated_uuid = str(uuid.uuid4())
        tenant_bucket = f"tenant-{generated_uuid}-{domain}"
        print(f"Creating new tenant with ID: {generated_uuid}")
        create_tenant_bucket(tenant_bucket)
        save_tenant_to_db(domain, email, generated_uuid)
        insert_user_to_db(email, generated_uuid)

    create_user_folders(tenant_bucket, email)

    return event

def tenant_exists(domain):
    try:
        username, password = getCredentials()
        connection = psycopg2.connect(user=username, password=password, host=os.getenv('Tenent_db', ''), database='postgres')
        cursor = connection.cursor()

        query = "SELECT tenant FROM \"Tenants\".tenantmappings WHERE domain = %s LIMIT 1;"
        cursor.execute(query, (domain,))
        result = cursor.fetchone()

        cursor.close()
        connection.close()
        return result[0] if result else None
    except Exception as e:
        print(f"Error checking tenant existence: {e}")
        return None

def tenant_mapping_exists(email):
    try:
        username, password = getCredentials()
        connection = psycopg2.connect(user=username, password=password, host=os.getenv('Tenent_db', ''), database='postgres')
        cursor = connection.cursor()

        query = "SELECT 1 FROM \"Tenants\".tenantmappings WHERE email = %s;"
        cursor.execute(query, (email,))
        result = cursor.fetchone()

        cursor.close()
        connection.close()
        return True if result else False
    except Exception as e:
        print(f"Error checking tenant mapping for email {email}: {e}")
        return False

def create_tenant_bucket(bucket_name):
    s3 = boto3.client('s3')
    try:
        s3.create_bucket(Bucket=bucket_name, CreateBucketConfiguration={'LocationConstraint': 'eu-west-2'})
        print(f"Bucket '{bucket_name}' created successfully.")
    except Exception as e:
        print(f"Error creating bucket: {e}")

def save_tenant_to_db(domain, email, tenant_id):
    try:
        username, password = getCredentials()
        connection = psycopg2.connect(user=username, password=password, host=os.getenv('Tenent_db', ''), database='postgres')
        cursor = connection.cursor()

        insert_query = """
            INSERT INTO "Tenants".tenantmappings (domain, email, tenant)
            VALUES (%s, %s, %s);
        """
        cursor.execute(insert_query, (domain, email, tenant_id))
        connection.commit()

        print(f"Record for email '{email}' inserted successfully with tenant ID '{tenant_id}'.")
        cursor.close()
        connection.close()
    except Exception as e:
        print(f"Error inserting record for email '{email}': {e}")

def insert_user_to_db(email, tenant_id):
    try:
        username, password = getCredentials()
        connection = psycopg2.connect(user=username, password=password, host=os.getenv('Tenent_db', ''), database='postgres')
        cursor = connection.cursor()

        email_prefix = email.split('@')[0]
        uid = f"{email_prefix}_{tenant_id}"

        insert_query = """
            INSERT INTO "Tenants".users (uid, email)
            VALUES (%s, %s)
            ON CONFLICT (uid) DO NOTHING;
        """
        cursor.execute(insert_query, (uid, email))
        connection.commit()

        print(f"User record inserted: UID='{uid}', Email='{email}'")
        cursor.close()
        connection.close()
    except Exception as e:
        print(f"Error inserting user '{email}': {e}")

def create_user_folders(bucket_name, email):
    s3 = boto3.client('s3')
    user_folder = f"cognito/{email}/"
    data_folder = f"{user_folder}Data/"
    logs_folder = f"{user_folder}Logs/"

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
                print(f"Bucket '{bucket_name}' does not exist. Error: {e}")
                return

    try:
        s3.put_object(Bucket=bucket_name, Key=user_folder)
        print(f"User folder '{user_folder}' created successfully in bucket '{bucket_name}'.")
        s3.put_object(Bucket=bucket_name, Key=data_folder)
        print(f"Sub-folder 'Data' created successfully in '{user_folder}'.")
        s3.put_object(Bucket=bucket_name, Key=logs_folder)
        print(f"Sub-folder 'Logs' created successfully in '{user_folder}'.")
    except Exception as e:
        print(f"Error creating user folders: {e}")

def getCredentials():
    secret_name = "rds!db-0534ea7e-2933-421d-96a0-c6d80af7fdc4"
    region_name = "eu-west-2"
    client = boto3.client(service_name='secretsmanager', region_name=region_name)
    get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    secret = json.loads(get_secret_value_response['SecretString'])
    return secret['username'], secret['password'] 