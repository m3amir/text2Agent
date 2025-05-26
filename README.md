# text2Agent

An AI agent building system that leverages AWS Bedrock for prompt management and agent orchestration.

## 🏗️ Project Structure

```
text2Agent/
├── README.md                 # This file
├── Prompts/                  # Prompt management system
│   ├── README.md            # Prompt warehouse documentation
│   ├── promptwarehouse.py   # AWS Bedrock prompt sync tool
│   └── collector/           # Example prompt collection
│       ├── __init__.py
│       └── prompt.py        # Collector and feedback prompts
└── [other components...]     # Additional agent components
```

## 🚀 Overview

text2Agent is designed to build intelligent AI agents that can understand natural language descriptions and automatically configure the necessary components and connectors. The system uses AWS Bedrock as the primary AI service for:

- **Prompt Management**: Centralized storage and versioning of AI prompts
- **Agent Orchestration**: Coordinating multiple AI agents for complex tasks
- **Model Access**: Leveraging various foundation models through Bedrock

## ⚙️ AWS Setup Requirements

### 1. AWS Credentials Configuration

You **must** configure AWS credentials under the profile name `m3` locally:

```bash
# Configure AWS credentials
aws configure --profile m3
```

**Required Information:**
- AWS Access Key ID
- AWS Secret Access Key  
- Default region: `eu-west-2`
- Default output format: `json`

### 2. Alternative: Manual Credentials File

Edit `~/.aws/credentials`:

```ini
[m3]
aws_access_key_id = YOUR_ACCESS_KEY_ID
aws_secret_access_key = YOUR_SECRET_ACCESS_KEY
region = eu-west-2
```

Edit `~/.aws/config`:

```ini
[profile m3]
region = eu-west-2
output = json
```
