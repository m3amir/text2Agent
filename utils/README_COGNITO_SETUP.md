# AWS Cognito Registration with Custom User Tier Attribute

This implementation provides a complete user registration system using AWS Cognito with a custom `user_tier` attribute that supports "standard" and "premium" tiers.

## 🚀 Features

- **User Registration** with email/username and password
- **Custom User Tier** attribute (standard/premium)
- **Email Verification** via Cognito confirmation codes
- **Admin Panel** for managing user tiers
- **Tier Validation** and default values
- **Beautiful Bootstrap UI** with responsive design

## 📋 Prerequisites

1. **AWS Account** with Cognito access
2. **Python 3.8+**
3. **AWS Credentials** configured (CLI or environment variables)

## 🔧 AWS Cognito Setup

### Step 1: Create User Pool

1. Go to AWS Cognito Console
2. Click "Create user pool"
3. Configure these settings:

**Authentication providers:**
- Cognito user pool sign-in options: ✅ Username, ✅ Email

**Password policy:**
- Minimum length: 8 characters
- Require uppercase, lowercase, numbers, special characters (as needed)

**Multi-factor authentication:**
- Optional or Required (as per your security needs)

**User account recovery:**
- ✅ Enable self-service account recovery
- ✅ Email only

### Step 2: Add Custom Attribute

In your User Pool settings:

1. Go to **Sign-up experience** → **Attributes**
2. Click **Add custom attribute**
3. Configure:
   - **Attribute name:** `user_tier`
   - **Attribute data type:** String
   - **Mutable:** Yes
   - **Required:** No (we'll set defaults)

### Step 3: Create App Client

1. Go to **App integration** → **App clients**
2. Click **Create app client**
3. Configure:
   - **App client name:** `text2agent-client`
   - **Authentication flows:** ✅ ALLOW_USER_PASSWORD_AUTH, ✅ ALLOW_REFRESH_TOKEN_AUTH
   - **Auth session validity:** 3 minutes
   - **Refresh token expiration:** 30 days
   - **Generate a client secret:** ✅ Yes (recommended)

### Step 4: Get Configuration Values

After creating your User Pool and App Client, collect these values:

- **User Pool ID:** `us-east-1_XXXXXXXXX`
- **App Client ID:** `xxxxxxxxxxxxxxxxxxxx`
- **App Client Secret:** `xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
- **Region:** `us-east-1` (or your chosen region)

## ⚙️ Environment Setup

### Step 1: Install Dependencies

```bash
pip install boto3 flask python-dotenv
```

### Step 2: Environment Variables

Create a `.env` file in your project root:

```env
# AWS Cognito Configuration
COGNITO_REGION=us-east-1
COGNITO_USER_POOL_ID=us-east-1_XXXXXXXXX
COGNITO_CLIENT_ID=xxxxxxxxxxxxxxxxxxxx
COGNITO_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Flask Configuration
FLASK_SECRET_KEY=your-super-secret-key-here

# AWS Credentials (if not using AWS CLI)
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
```

### Step 3: Run the Application

```bash
python app.py
```

The app will be available at `http://localhost:5000`

## 🎯 Usage Examples

### Basic Registration

```python
from utils.cognito import register_user

# Register a standard user
result = register_user(
    username="john_doe",
    email="john@example.com",
    password="SecurePass123!",
    user_tier="standard"
)

# Register a premium user
result = register_user(
    username="jane_premium",
    email="jane@example.com", 
    password="SecurePass123!",
    user_tier="premium"
)
```

### User Tier Management

```python
from utils.cognito import update_user_tier, get_user_info

# Update user tier
result = update_user_tier("john_doe", "premium")

# Get user information
user_info = get_user_info("john_doe")
print(f"User tier: {user_info['user_tier']}")
```

### Advanced Registration with Custom Attributes

```python
result = register_user(
    username="advanced_user",
    email="advanced@example.com",
    password="SecurePass123!",
    user_tier="premium",
    custom_attributes={
        "company": "TechCorp",
        "department": "Engineering",
        "role": "Developer"
    }
)
```

## 🛡️ Security Best Practices

### 1. Environment Variables
Always use environment variables for sensitive configuration:

```python
import os
from dotenv import load_dotenv

load_dotenv()

USER_POOL_ID = os.getenv('COGNITO_USER_POOL_ID')
CLIENT_SECRET = os.getenv('COGNITO_CLIENT_SECRET')
```

### 2. Input Validation
The system includes comprehensive validation:

- **User Tier Validation:** Only "standard" and "premium" are allowed
- **Password Requirements:** Configurable in Cognito
- **Email Format:** Validated by Cognito
- **Custom Attribute Sanitization:** Automatic prefix handling

### 3. Error Handling
Robust error handling for all Cognito operations:

```python
try:
    result = register_user(username, email, password, user_tier)
    if result['success']:
        print(f"User registered: {result['user_sub']}")
    else:
        print(f"Registration failed: {result['message']}")
except Exception as e:
    print(f"Unexpected error: {str(e)}")
```

## 🔄 User Tier Workflow

### Registration Flow
1. User selects tier during registration
2. System validates tier (defaults to "standard" if invalid)
3. Custom attribute `custom:user_tier` is set in Cognito
4. User receives confirmation email
5. Upon confirmation, user account is active with assigned tier

### Tier Management Flow
1. Admin can view user information via `/admin/user-info`
2. Admin can update user tier via `/admin/update-tier`
3. Changes are reflected immediately in Cognito
4. Applications can check user tier for feature access

## 📱 API Endpoints

### User Registration
- **POST** `/signup` - Register new user with tier selection
- **GET** `/confirm` - Confirmation code entry page
- **POST** `/confirm` - Process confirmation code

### Admin Management
- **GET** `/admin` - Admin panel interface
- **POST** `/admin/user-info` - Get user information
- **POST** `/admin/update-tier` - Update user tier

## 🎨 UI Features

- **Modern Bootstrap Design** with gradient backgrounds
- **Responsive Layout** for mobile and desktop
- **Real-time Validation** feedback
- **Flash Messages** for user feedback
- **Tier Selection Dropdown** with clear pricing

## 🔍 Troubleshooting

### Common Issues

**1. "User pool does not exist" error:**
- Verify `COGNITO_USER_POOL_ID` is correct
- Check the region matches your User Pool region

**2. "Invalid client" error:**
- Verify `COGNITO_CLIENT_ID` and `COGNITO_CLIENT_SECRET`
- Ensure app client has correct authentication flows enabled

**3. "Custom attribute not found" error:**
- Verify custom attribute `user_tier` is created in User Pool
- Check attribute name is exactly `user_tier` (case-sensitive)

**4. "Password does not conform to policy" error:**
- Check your User Pool password policy
- Ensure passwords meet minimum requirements

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 🚀 Production Deployment

### 1. Security Enhancements
- Use AWS IAM roles instead of access keys
- Enable AWS CloudTrail for audit logging
- Set up proper VPC and security groups
- Use AWS Secrets Manager for sensitive config

### 2. Scalability
- Use AWS Lambda for serverless deployment
- Implement API Gateway for REST endpoints
- Add CloudWatch monitoring and alarms

### 3. Environment Configuration
- Use separate Cognito User Pools for dev/staging/prod
- Implement proper CI/CD pipelines
- Use infrastructure as code (Terraform/CloudFormation)

## 📊 Monitoring User Tiers

Query user tiers programmatically:

```python
def get_tier_statistics():
    """Get user tier distribution"""
    # This would require admin permissions and pagination
    standard_count = 0
    premium_count = 0
    
    # Implementation would use list_users with filters
    # and count users by custom:user_tier attribute
    
    return {
        'standard': standard_count,
        'premium': premium_count,
        'total': standard_count + premium_count
    }
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License. 