# Setup Instructions

## Environment Variables Required

Create a `.env` file in the root directory with the following variables:

```bash
# OpenAI API Key
OPENAI_API_KEY=your_openai_api_key_here

# SharePoint Credentials
SHAREPOINT_TENANT_ID=your_tenant_id
SHAREPOINT_CLIENT_ID=your_client_id
SHAREPOINT_CLIENT_SECRET=your_client_secret
SHAREPOINT_EMAIL=your_email@domain.com

# Salesforce Credentials
SF_EMAIL=your_salesforce_email
SF_PASSWORD=your_salesforce_password
SF_TOKEN=your_salesforce_token

# Zendesk Credentials
ZENDESK_SUBDOMAIN=your_subdomain
ZENDESK_EMAIL=your_zendesk_email
ZENDESK_TOKEN=your_zendesk_token
```

## Configuration Files

1. Copy `MCP/Config/config.json.example` to `MCP/Config/config.json` and fill in your values
2. Copy `Connectors/.gdrive-server-credentials.json.example` to `Connectors/.gdrive-server-credentials.json` and add your Google service account credentials

## Security Note

Never commit actual credentials or API keys to version control. Use environment variables or secure credential storage systems. 