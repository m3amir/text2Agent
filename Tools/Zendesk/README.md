# Zendesk Tool

A comprehensive Zendesk tool using the zenpy library that provides ticket management, user management, organization handling, and analytics functionality.

## Features

- **Ticket Management**: Create, read, update tickets with full comment support
- **User Management**: Manage users, roles, and get user details
- **Search Functionality**: Advanced ticket and user search with filters
- **Organization Management**: Handle organizations and their relationships
- **Analytics**: Get ticket statistics and insights
- **Real-time Updates**: Direct integration with Zendesk API

## Setup

### Prerequisites

1. Zendesk account with API access
2. API token generated from Zendesk Admin settings
3. Agent or Admin role for full functionality

### Installation

```bash
pip install zenpy
```

### Configuration

Add your Zendesk credentials to `MCP/Config/config.json`:

```json
{
  "zendesk_creds": {
    "subdomain": "your-company",
    "email": "your-email@company.com", 
    "token": "your-api-token"
  }
}
```

**How to get your API token:**
1. Go to Zendesk Admin Center
2. Navigate to Apps and integrations > APIs > Zendesk API
3. Enable Token Access
4. Generate a new API token
5. Copy the token to your config

## Usage

### Initialize the Tool

```python
from Tools.Zendesk.tool import ZendeskToolkit
import json

# Load credentials
with open('MCP/Config/config.json', 'r') as f:
    config = json.load(f)
    
creds = config['zendesk_creds']
zd_tool = ZendeskToolkit(creds)
```

## Available Methods

### 1. Ticket Management

#### Get Tickets

```python
# Get recent tickets
result = zd_tool.zendesk_get_tickets()

# Filter by status
result = zd_tool.zendesk_get_tickets(status="open")

# Filter by priority
result = zd_tool.zendesk_get_tickets(priority="high")

# Combine filters
result = zd_tool.zendesk_get_tickets(status="open", priority="urgent", limit=10)
```

**Response Format:**
```json
{
  "success": true,
  "filters": {
    "status": "open",
    "priority": "high",
    "limit": 25
  },
  "tickets": [
    {
      "id": 12345,
      "subject": "Login issues",
      "description": "User cannot login to the system",
      "status": "open",
      "priority": "high",
      "type": "incident",
      "requester_id": 67890,
      "assignee_id": 54321,
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-20T14:45:00Z",
      "tags": ["login", "urgent"],
      "url": "https://company.zendesk.com/api/v2/tickets/12345.json"
    }
  ],
  "count": 1
}
```

#### Get Ticket Details

```python
result = zd_tool.zendesk_get_ticket_details(ticket_id=12345)
```

**Response includes:**
- Full ticket information
- All comments and their authors
- Requester and assignee details
- Comment count and history

#### Create Ticket

```python
result = zd_tool.zendesk_create_ticket(
    subject="New Issue",
    description="Detailed description of the issue",
    requester_email="user@company.com",
    priority="normal",
    ticket_type="question",
    tags=["api", "integration"]
)
```

#### Update Ticket

```python
result = zd_tool.zendesk_update_ticket(
    ticket_id=12345,
    status="pending",
    priority="high",
    assignee_email="agent@company.com",
    comment="Working on this issue now",
    public_comment=True
)
```

#### Search Tickets

```python
# Basic search
result = zd_tool.zendesk_search_tickets("login error")

# Advanced search with Zendesk query syntax
result = zd_tool.zendesk_search_tickets("status:open priority:high")

# Search by requester
result = zd_tool.zendesk_search_tickets("requester:user@company.com")

# Date range search
result = zd_tool.zendesk_search_tickets("created>2024-01-01")
```

### 2. User Management

#### Get Users

```python
# Get all users
result = zd_tool.zendesk_get_users()

# Filter by role
result = zd_tool.zendesk_get_users(role="agent")
result = zd_tool.zendesk_get_users(role="admin")
result = zd_tool.zendesk_get_users(role="end-user")
```

#### Get User Details

```python
result = zd_tool.zendesk_get_user_details(user_id=67890)
```

**Response includes:**
- Full user information
- Recent tickets submitted by user
- User activity summary

#### Create User

```python
result = zd_tool.zendesk_create_user(
    name="John Doe",
    email="john.doe@company.com",
    role="end-user",
    phone="+1-555-123-4567",
    organization_id=12345
)
```

### 3. Organization Management

#### Get Organizations

```python
result = zd_tool.zendesk_get_organizations(limit=50)
```

**Response Format:**
```json
{
  "success": true,
  "organizations": [
    {
      "id": 12345,
      "name": "Acme Corporation",
      "domain_names": ["acme.com"],
      "details": "Large enterprise client",
      "notes": "VIP customer",
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-15T10:30:00Z",
      "url": "https://company.zendesk.com/api/v2/organizations/12345.json"
    }
  ],
  "count": 1
}
```

### 4. Analytics and Reporting

#### Get Ticket Statistics

```python
# Last 30 days (default)
result = zd_tool.zendesk_get_ticket_stats()

# Last 7 days
result = zd_tool.zendesk_get_ticket_stats(days=7)

# Last 90 days
result = zd_tool.zendesk_get_ticket_stats(days=90)
```

**Response Format:**
```json
{
  "success": true,
  "date_range": {
    "start_date": "2024-01-01",
    "end_date": "2024-01-31",
    "days": 30
  },
  "statistics": {
    "total_tickets": 150,
    "by_status": {
      "open": 45,
      "pending": 20,
      "solved": 75,
      "closed": 10
    },
    "by_priority": {
      "low": 30,
      "normal": 80,
      "high": 25,
      "urgent": 15
    },
    "by_type": {
      "question": 60,
      "incident": 40,
      "problem": 25,
      "task": 25
    },
    "by_assignee": {
      "John Agent": 35,
      "Jane Smith": 40,
      "unassigned": 75
    }
  }
}
```

## Advanced Search Queries

Zendesk supports powerful search syntax:

```python
# Combine multiple criteria
zd_tool.zendesk_search_tickets("status:open priority:urgent assignee:agent@company.com")

# Date ranges
zd_tool.zendesk_search_tickets("created>2024-01-01 created<2024-01-31")

# Tags
zd_tool.zendesk_search_tickets("tags:bug tags:critical")

# Organization
zd_tool.zendesk_search_tickets("organization:'Acme Corp'")

# Custom fields (replace 12345 with actual field ID)
zd_tool.zendesk_search_tickets("custom_field_12345:value")
```

## Error Handling

All methods return JSON responses with error information when failures occur:

```json
{
  "error": "Failed to get tickets: Authentication failed"
}
```

## Authentication

The tool uses Zendesk API token authentication:

1. **API Token**: Generated from Zendesk Admin settings
2. **Email + Token**: Used for API authentication
3. **Automatic Connection Testing**: Validates credentials on initialization

## Rate Limiting

Zendesk API has rate limits:
- **700 requests per minute** for most endpoints
- The tool doesn't implement rate limiting - consider adding delays for bulk operations

## Supported Operations

### Tickets
- ✅ List tickets with filtering
- ✅ Get ticket details with comments
- ✅ Create new tickets
- ✅ Update tickets (status, priority, assignee)
- ✅ Add comments to tickets
- ✅ Search tickets with advanced queries

### Users  
- ✅ List users with role filtering
- ✅ Get user details with ticket history
- ✅ Create new users
- ✅ Search users

### Organizations
- ✅ List organizations
- ✅ Get organization details

### Analytics
- ✅ Ticket statistics by status, priority, type
- ✅ Assignee workload analysis
- ✅ Time-based reporting

## Limitations

- **Bulk Operations**: No built-in bulk update functionality
- **File Attachments**: Not currently supported
- **Webhooks**: Not implemented
- **Advanced Triggers**: Not supported
- **SLA Policies**: Not directly managed

## Testing

Create a test script to verify functionality:

```python
# Test basic connection
result = zd_tool.zendesk_get_tickets(limit=5)
print(json.dumps(json.loads(result), indent=2))

# Test user management  
result = zd_tool.zendesk_get_users(limit=5)
print(json.dumps(json.loads(result), indent=2))

# Test statistics
result = zd_tool.zendesk_get_ticket_stats(days=7)
print(json.dumps(json.loads(result), indent=2))
```

## Troubleshooting

### Common Issues

1. **Authentication Errors**: 
   - Verify subdomain, email, and token
   - Check if API access is enabled
   - Ensure user has appropriate permissions

2. **Permission Denied**:
   - Verify user role (Agent/Admin required for most operations)
   - Check organization permissions

3. **Rate Limiting**:
   - Add delays between requests
   - Implement exponential backoff

4. **Invalid Ticket ID**:
   - Verify ticket exists and is accessible
   - Check user permissions for the ticket

### Debug Mode

Enable debug output by modifying the tool:

```python
# Add this to see raw API responses
import logging
logging.basicConfig(level=logging.DEBUG)
``` 