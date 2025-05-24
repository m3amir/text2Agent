import boto3
import json


def get_secret(secret_name, region_name):
    # Create a Secrets Manager client
    client = boto3.client(service_name="secretsmanager", region_name=region_name)

    try:
        # Retrieve the secret value
        response = client.get_secret_value(SecretId=secret_name)
        
        # Check if the secret is stored as plaintext or JSON
        if "SecretString" in response:
            secret = response["SecretString"]
        else:
            # Secret is stored as binary
            secret = response["SecretBinary"].decode("utf-8")
        
        # Return the secret (e.g., as a dictionary if JSON)
        return json.loads(secret) if secret.startswith("{") else secret

    except Exception as e:
        print(f"Error retrieving secret: {e}")
        return None
    
def put_secret(secret_name, region_name, secret_data):
    print(f"\n=== PUT SECRET OPERATION ===")
    print(f"1. Secret Name: {secret_name}")
    print(f"2. Region: {region_name}")
    
    # Debug print credentials (with sensitive data masked)
    debug_data = {}
    for key, value in secret_data.items():
        if any(sensitive in key.lower() for sensitive in ['password', 'secret', 'token']):
            debug_data[key] = '****'
        else:
            debug_data[key] = value
    print(f"3. Secret Data to store (sensitive data masked):")
    print(json.dumps(debug_data, indent=2))

    try:
        print(f"4. Initializing AWS Secrets Manager client...")
        client = boto3.client('secretsmanager', region_name=region_name)
        print(f"5. Client initialized successfully")

        # Convert secret data to JSON string
        print(f"6. Converting secret data to JSON string...")
        secret_value = json.dumps(secret_data)
        print(f"7. JSON conversion successful")

        print(f"8. Attempting to create secret in AWS...")
        try:
            response = client.create_secret(
                Name=secret_name,
                SecretString=secret_value
            )
            print(f"9. SUCCESS: Secret created successfully!")
            print(f"   Response ARN: {response.get('ARN', 'N/A')}")
            return True
            
        except client.exceptions.ResourceExistsException:
            print(f"9. Secret already exists. Skipping creation.")
            return False

    except Exception as e:
        print(f"\nERROR in put_secret:")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        import traceback
        print(traceback.format_exc())
        raise e


if __name__ == "__main__":
    put_secret("test", "eu-west-2", {"zendesk_username": "admin", "zendesk_password": "mypassword123"})