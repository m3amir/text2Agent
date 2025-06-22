# text2Agent - Intelligent Workflow Automation Platform

A comprehensive AI-powered automation platform that combines LangGraph workflows, Model Context Protocol (MCP) servers, prompt management, and multi-service integrations to create intelligent automation solutions.

## 🎯 Overview

text2Agent is an enterprise-grade platform that enables the creation and execution of intelligent workflows through:

- **Dynamic Workflow Creation**: LangGraph-based workflows with intelligent tool selection
- **Multi-Service Integration**: Microsoft Graph, AWS services, chart generation, PDF creation
- **Prompt Management**: Centralized prompt warehouse with AWS Bedrock integration
- **MCP Protocol**: Standardized tool integration via Model Context Protocol servers
- **Real-time Analytics**: Comprehensive logging, monitoring, and performance tracking
- **Scalable Architecture**: Docker-based deployment with CI/CD pipeline

## 🏗️ Architecture

### Core Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   LangGraph     │    │   MCP Servers   │    │ Prompt Warehouse│
│   Workflows     │◄──►│   (Tools)       │◄──►│  (AWS Bedrock)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Skeleton      │    │   Connectors    │    │   Global        │
│   Orchestrator  │◄──►│   (Microsoft,   │◄──►│   Components    │
│                 │    │    Charts, etc) │    │   (LLM, STR)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Database      │    │   File Storage  │    │   Monitoring    │
│   (PostgreSQL)  │    │   (AWS S3)      │    │   & Logging     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🚀 Key Features

### 1. **Intelligent Workflow Orchestration**
- **LangGraph Integration**: State-based workflow execution with conditional routing
- **Dynamic Tool Selection**: LLM-powered tool selection based on context
- **Adaptive Routing**: Quality-based workflow navigation with retry logic
- **Visual Workflow Designer**: Automatic PNG diagram generation

### 2. **Multi-Service Connectors**
- **Microsoft Graph API**: SharePoint, Outlook, Teams integration
- **AWS Services**: S3, Secrets Manager, RDS, Bedrock
- **Chart Generation**: Dynamic chart creation with matplotlib/seaborn
- **PDF Generation**: Automated report creation with ReportLab
- **Database Operations**: PostgreSQL integration with connection pooling

### 3. **Prompt Management System**
- **Centralized Warehouse**: AWS Bedrock Prompt Management integration
- **Version Control**: Automatic prompt versioning and deployment
- **File Synchronization**: Auto-sync from `prompt.py` files to AWS
- **Template Management**: Reusable prompt templates across workflows

### 4. **MCP Server Ecosystem**
- **Standardized Protocol**: Model Context Protocol for tool integration
- **Docker Deployment**: Containerized MCP servers for scalability
- **Tool Discovery**: Automatic tool loading and capability detection
- **Error Handling**: Robust error handling with fallback mechanisms

### 5. **Enterprise Features**
- **Multi-Tenant Support**: User-based isolation and resource management
- **Comprehensive Logging**: Structured logging with S3 synchronization
- **Performance Monitoring**: Real-time metrics and analytics
- **Security**: AWS IAM integration with credential management

## 📁 Project Structure

```
text2Agent/
├── 🔧 Global/                    # Core platform components
│   ├── Architect/                # Workflow orchestration
│   │   └── skeleton.py          # Main workflow builder
│   ├── Components/              # Reusable components
│   │   ├── STR.py              # Structured Task Reasoning
│   │   └── colleagues.py       # AI analysis and scoring
│   ├── llm.py                  # LLM abstraction layer
│   └── runner.py               # Workflow execution engine
│
├── 🔌 Connectors/               # Service integrations
│   ├── microsoft.py            # Microsoft Graph API
│   ├── charts.py               # Chart generation
│   └── pdf_generator.py        # PDF creation
│
├── 🛠️ MCP/                      # Model Context Protocol
│   ├── Config/                 # MCP server configurations
│   ├── Servers/                # MCP server implementations
│   └── Tools/                  # Tool definitions
│
├── 📝 Prompts/                  # Prompt management
│   ├── promptwarehouse.py      # AWS Bedrock integration
│   ├── collector/              # Agent prompts
│   ├── STR/                    # STR prompts
│   └── poolOfColleagues/       # Analysis prompts
│
├── 🧪 Tests/                    # Comprehensive test suite
│   ├── skeleton/               # Workflow tests
│   ├── MCP/                    # MCP server tests
│   └── prompts/                # Prompt warehouse tests
│
├── 🗄️ utils/                    # Utility functions
│   └── core.py                 # Database, AWS, logging utilities
│
├── 📊 Charts/                   # Generated charts
├── 📄 Reports/                  # Generated reports
├── 📋 Logs/                     # Application logs
└── 🔧 Tools/                    # Additional tools
```

## 🛠️ Installation & Setup

### Prerequisites

- Python 3.12+
- Node.js 18+ (for MCP servers)
- Docker (for containerized deployment)
- AWS Account (for cloud services)
- PostgreSQL database

### Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd text2Agent
   ```

2. **Set up Python environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

4. **Set up MCP servers**
   ```bash
   cd MCP/Servers
   npm install
   ```

5. **Initialize database**
   ```bash
   python utils/setup_database.py
   ```

6. **Run the application**
   ```bash
   python main.py
   ```

### Environment Configuration

Create a `.env` file with the following variables:

```env
# Microsoft Graph API
MICROSOFT_TENANT_ID=your_tenant_id
MICROSOFT_CLIENT_ID=your_client_id
MICROSOFT_CLIENT_SECRET=your_client_secret
MICROSOFT_SITE_URL=your_sharepoint_site
MICROSOFT_EMAIL=your_email

# AWS Configuration
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=us-east-1

# Database
DB_HOST=your_db_host
DB_PORT=5432
DB_NAME=text2agent
DB_USER=your_db_user
DB_PASSWORD=your_db_password
```

## 🎮 Usage Examples

### 1. Basic Workflow Creation

```python
import asyncio
from Global.Architect.skeleton import Skeleton

async def create_data_analysis_workflow():
    # Initialize skeleton
    skeleton = Skeleton(user_email="analyst@company.com")
    
    # Load required tools
    await skeleton.load_tools([
        'microsoft_sharepoint_search_files',
        'microsoft_excel_read_data',
        'charts_create_chart',
        'pdf_generate_report'
    ])
    
    # Define workflow blueprint
    blueprint = {
        'nodes': ['data_extraction', 'colleagues', 'router', 'analysis', 'reporting', 'finish'],
        'edges': [
            ('data_extraction', 'colleagues'),
            ('colleagues', 'router'),
            ('analysis', 'colleagues'),
            ('reporting', 'finish')
        ],
        'node_tools': {
            'data_extraction': ['microsoft_sharepoint_search_files', 'microsoft_excel_read_data'],
            'analysis': ['charts_create_chart'],
            'reporting': ['pdf_generate_report']
        },
        'conditional_edges': {
            'router': {
                'retry_previous': 'data_extraction',
                'next_step': 'analysis',
                'finish': 'finish'
            }
        }
    }
    
    # Create and execute workflow
    skeleton.create_skeleton("Data Analysis Pipeline", blueprint)
    compiled_graph, png_files = skeleton.compile_and_visualize("data_analysis")
    
    result = await compiled_graph.ainvoke({
        "messages": ["Extract Q4 sales data from SharePoint and create analysis report"]
    })
    
    await skeleton.cleanup_tools()
    return result

# Run the workflow
asyncio.run(create_data_analysis_workflow())
```

### 2. Prompt Management

```python
from Prompts.promptwarehouse import PromptWarehouse

# Initialize prompt warehouse
warehouse = PromptWarehouse('m3')

# Sync prompts from files to AWS Bedrock
warehouse.sync_prompts_from_files()

# List all available prompts
print(warehouse.list_prompts())

# Get a specific prompt
collector_prompt = warehouse.get_prompt('collector')
print(collector_prompt)
```

### 3. MCP Server Integration

```python
from MCP.mcp_client import MCPClient

# Connect to MCP server
client = MCPClient()
await client.connect("microsoft-server")

# List available tools
tools = await client.list_tools()
print(f"Available tools: {[tool.name for tool in tools]}")

# Execute a tool
result = await client.call_tool("microsoft_sharepoint_search_files", {
    "query": "budget 2024",
    "file_type": "xlsx"
})
```

## 🧪 Testing

The project includes a comprehensive test suite covering all major components:

### Test Categories

1. **Unit Tests**: Individual component testing with mocks
2. **Integration Tests**: Real service integration testing
3. **End-to-End Tests**: Complete workflow execution testing

### Running Tests

```bash
# Run all tests
python -m pytest Tests/ -v

# Run specific test suites
python -m pytest Tests/skeleton/ -v          # Workflow tests
python -m pytest Tests/MCP/ -v              # MCP server tests
python -m pytest Tests/prompts/ -v          # Prompt warehouse tests

# Run with coverage
python -m pytest Tests/ --cov=. --cov-report=html
```

### Test Coverage

- ✅ **23 total tests** across all components
- ✅ **Real AWS integration** (when credentials available)
- ✅ **Microsoft Graph API** testing
- ✅ **Docker-based MCP servers**
- ✅ **Prompt validation** (9 real prompts)
- ✅ **Error handling** and edge cases

## 🚀 Deployment

### Docker Deployment

```bash
# Build the application
docker build -t text2agent .

# Run with docker-compose
docker-compose up -d
```

### AWS Deployment

The platform is designed for AWS deployment with:
- **ECS/Fargate**: Container orchestration
- **RDS**: PostgreSQL database
- **S3**: File storage and logging
- **Bedrock**: Prompt management
- **Secrets Manager**: Credential management

### CI/CD Pipeline

GitHub Actions workflow provides:
- **Automated Testing**: All test suites on every push
- **Security Scanning**: Dependency and code analysis
- **Multi-Environment**: Staging and production deployments
- **Performance Monitoring**: Test execution metrics

## 📊 Monitoring & Analytics

### Logging System

- **Structured Logging**: JSON-formatted logs with context
- **S3 Synchronization**: Automatic log backup to AWS S3
- **Multi-Level**: Debug, info, warning, error levels
- **Component Tracking**: Per-component log isolation

### Performance Metrics

- **Workflow Execution**: Timing and success rates
- **Tool Performance**: Individual tool execution metrics
- **Resource Usage**: Memory, CPU, and network monitoring
- **Error Tracking**: Comprehensive error analysis

### Database Analytics

```python
from utils.core import execute_query

# Get workflow performance metrics
metrics = execute_query("""
    SELECT 
        task_description,
        AVG(score) as avg_score,
        COUNT(*) as execution_count
    FROM str_records 
    GROUP BY task_description
    ORDER BY avg_score DESC
""")
```

## 🔧 Configuration

### MCP Server Configuration

```json
{
  "mcpServers": {
    "microsoft": {
      "command": "node",
      "args": ["MCP/Servers/microsoft/index.js"],
      "env": {
        "MICROSOFT_TENANT_ID": "${MICROSOFT_TENANT_ID}",
        "MICROSOFT_CLIENT_ID": "${MICROSOFT_CLIENT_ID}"
      }
    },
    "charts": {
      "command": "node", 
      "args": ["MCP/Servers/charts/index.js"]
    }
  }
}
```

### Workflow Configuration

```yaml
# Config/config.yml
workflows:
  default_threshold: 7
  max_retries: 3
  timeout_seconds: 300

database:
  pool_size: 10
  max_overflow: 20
  pool_timeout: 30

logging:
  level: INFO
  sync_interval: 300
  retention_days: 30
```

## 🤝 Contributing

### Development Setup

1. **Fork the repository**
2. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Install development dependencies**
   ```bash
   pip install -r requirements-dev.txt
   ```
4. **Run tests**
   ```bash
   python -m pytest Tests/ -v
   ```
5. **Submit a pull request**

### Code Standards

- **Python**: Follow PEP 8 with Black formatting
- **TypeScript**: ESLint configuration for MCP servers
- **Documentation**: Comprehensive docstrings and comments
- **Testing**: Minimum 80% test coverage for new features

### Architecture Guidelines

- **Modularity**: Keep components loosely coupled
- **Error Handling**: Comprehensive error handling with graceful degradation
- **Performance**: Async/await patterns for I/O operations
- **Security**: Never commit credentials or sensitive data

## 📚 Documentation

### API Documentation

- **Workflow API**: Complete workflow creation and execution guide
- **MCP Protocol**: Tool integration and server development
- **Prompt Management**: Prompt creation and deployment
- **Database Schema**: Complete database structure documentation

### Tutorials

- **Getting Started**: Step-by-step setup and first workflow
- **Advanced Workflows**: Complex routing and conditional logic
- **Custom Tools**: Creating and integrating custom MCP tools
- **Deployment Guide**: Production deployment best practices

## 🔒 Security

### Security Features

- **AWS IAM**: Role-based access control
- **Credential Management**: AWS Secrets Manager integration
- **Data Encryption**: At-rest and in-transit encryption
- **Audit Logging**: Comprehensive security event logging

### Security Best Practices

- **Environment Variables**: Never hardcode credentials
- **Least Privilege**: Minimal required permissions
- **Regular Updates**: Keep dependencies updated
- **Security Scanning**: Automated vulnerability detection

## 📄 License

This project is part of the M3 text2Agent system. All rights reserved.

## 🆘 Support

### Getting Help

- **Documentation**: Check the `/docs` directory for detailed guides
- **Issues**: Report bugs and feature requests via GitHub Issues
- **Discussions**: Join community discussions for questions and ideas

### Troubleshooting

#### Common Issues

1. **"asyncio.run() cannot be called"**: Microsoft tool conflict
   - **Solution**: Handled automatically with mock results

2. **MCP server connection failed**
   - **Solution**: Check server configuration and Docker status

3. **AWS credentials not found**
   - **Solution**: Verify environment variables or AWS profile setup

4. **Database connection timeout**
   - **Solution**: Check database configuration and network connectivity

### Performance Optimization

- **Connection Pooling**: Use database connection pools
- **Async Operations**: Leverage async/await for I/O
- **Caching**: Implement caching for frequently accessed data
- **Resource Monitoring**: Monitor memory and CPU usage

---

**text2Agent** - Transforming business processes through intelligent automation 🚀
