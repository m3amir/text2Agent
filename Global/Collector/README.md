# Collector Module

The Collector module is responsible for analyzing user descriptions of AI agents and automatically identifying the necessary connectors and tools required to build those agents. It consists of two main components: `agent.py` and `connectors.py`.

## Overview

### `agent.py` - Main Collector Agent
The main orchestrator that uses a LangGraph workflow to process user requests through multiple stages:
1. **Collect** - Identify necessary connectors based on user description
2. **Feedback** - Generate clarifying questions if needed
3. **Human Approval** - Interactive Q&A with the user
4. **Validate Connectors** - Load tools and select the most relevant ones

### `connectors.py` - Dynamic Connector Discovery
Handles the discovery and loading of available connectors and their tools from both:
- **Remote MCP Servers** (Microsoft, Atlassian, etc.)
- **Local Tool Modules** (Custom Python tools)

## Quick Start

### Basic Usage of Collector Agent

```python
import asyncio
from Global.Collector.agent import Collector

# 1. Create a collector with your agent description and user email
agent_description = "I want an agent that takes emails from a file in our document storage and sends cold emails to the people in the file about a new product we are launching."

collector = Collector(agent_description, user_email="user@example.com")

# 2. Initialize the workflow
graph = collector.init_agent()

# 3. Run the collector
config = {"configurable": {"thread_id": "unique-thread-id"}}
result = asyncio.run(graph.ainvoke({
    "input": agent_description,
    "connectors": [],
    "feedback_questions": [],
    "answered_questions": [],
    "reviewed": False,
    "connector_tools": {},
    "final_result": {}
}, config=config))
```

### Using Connectors Discovery

```python
from Global.Collector.connectors import (
    load_connectors,
    print_connector_tools,
    get_connector_tools_sync
)

# 1. Load all available connectors
connectors = load_connectors()
print("Available connectors:", connectors)

# 2. Get detailed tool information for specific connectors
tools_data = get_connector_tools_sync("microsoft")
print(f"Microsoft tools: {tools_data['tool_count']} available")

# 3. Print detailed tool documentation
print_connector_tools(["microsoft", "atlassian"])
```

## Detailed Documentation

### Agent.py - Collector Workflow

#### Main Classes

##### `Collector`
The main agent class that orchestrates the entire collection process.

**Constructor:**
```python
collector = Collector(agent_description: str, user_email: str)
```

**Key Methods:**
- `init_agent()` - Creates and returns the LangGraph workflow
- `expand_task_description(task_description)` - Uses LLM to create verbose task explanation
- `validate_connectors(state)` - Validates connectors and selects relevant tools
- `load_connector_tools(valid_connectors)` - Loads tools for validated connectors
- `format_tools(connector_tools)` - Formats tools for LLM consumption
- `format_connectors(connector_tools)` - Formats connector tools with detailed argument schemas

##### Response Models
- `connectorResponse` - Structured output for connector identification
- `feedbackResponse` - Structured output for feedback questions  
- `toolsResponse` - Structured output for tool selection (includes names + descriptions)

##### State Class
The workflow state includes these fields:
- `input: str` - Original user description
- `connectors: List[str]` - Identified connectors
- `feedback_questions: List[str]` - Generated clarifying questions
- `answered_questions: List[str]` - User responses to questions
- `reviewed: bool` - Whether user has completed Q&A
- `connector_tools: dict` - Loaded tool schemas for connectors
- `final_result: dict` - Final output with task description and selected tools

#### Workflow Stages

1. **Task Expansion** (during initialization)
   - Uses LLM to create a verbose and detailed explanation of the user's task
   - Provides richer context for connector identification and tool selection

2. **Collect Stage**
   - Analyzes user description and expanded task analysis
   - Identifies required connectors based on capabilities
   - Uses AI to match requirements with available connectors

3. **Feedback Stage**
   - Generates clarifying questions if description lacks detail
   - Only runs if no previous questions have been answered
   - Ensures all necessary information is gathered

4. **Human Approval Stage**
   - Interactive Q&A session with user via interrupts
   - Collects additional context and requirements
   - Sets reviewed flag to true when complete

5. **Validate Connectors Stage**
   - Validates identified connectors against available ones
   - Loads tools for validated connectors using `get_multiple_connector_tools_sync`
   - Uses AI to select most relevant tools from available options
   - Returns final result with expanded task description and selected tools with descriptions

#### Example Output

```python
# Final result output format:
{
    "task_description": "A comprehensive email marketing agent that...",
    "tools": {
        "microsoft_sharepoint_download_and_extract_text": "Download a file from SharePoint and extract its text content for analysis.",
        "microsoft_mail_send_email_as_user": "Send an email through Microsoft Graph API on behalf of a specified user."
    }
}
```

### Connectors.py - Dynamic Discovery

#### Main Functions

##### `load_connectors()`
Discovers all available connectors from MCP configuration.

```python
connectors = load_connectors()
# Returns: {'microsoft': 'Microsoft 365 tools', 'atlassian': 'Atlassian tools', ...}
```

##### `get_connector_tools_sync(connector_name)`
Get detailed tool information for a single connector.

```python
tools_data = get_connector_tools_sync("microsoft")
# Returns:
{
    'tools': [...],  # Raw tool objects
    'tool_schemas': {...},  # Detailed schemas
    'tool_count': 6
}
```

##### `get_multiple_connector_tools_sync(connector_names)`
Efficiently load tools for multiple connectors in a single operation.

```python
all_tools = get_multiple_connector_tools_sync(["microsoft", "atlassian"])
# Returns data for all specified connectors
```

##### `print_connector_tools(connector_names)`
Print detailed, human-readable tool documentation.

```python
print_connector_tools("microsoft")
# or for multiple:
print_connector_tools(["microsoft", "atlassian"])
```

#### Configuration

The module reads from `MCP/Config/mcp_servers_config.json`:

```json
{
  "mcpServers": {
    "microsoft": {
      "prefix": "microsoft",
      "description": "Microsoft 365 tools",
      "command": "...",
      "args": ["..."]
    }
  },
  "local": {
    "custom_connector": {
      "description": "Custom local tools",
      "path": "Tools/CustomConnector"
    }
  }
}
```

## Advanced Usage

### Custom Tool Integration

To add custom local tools:

1. Create a tool file: `Tools/YourConnector/tool.py`
2. Define functions with prefix: `yourconnector_function_name`
3. Add to MCP config under "local" section
4. The connector will be automatically discovered

### Interactive Workflow

The agent supports interactive feedback collection using LangGraph interrupts:

```python
# The workflow will automatically interrupt for user input
# when clarifying questions are needed
if '__interrupt__' in result:
    questions = result['__interrupt__'][0].value['questions']
    
    # Collect answers from user
    responses = {}
    for question in questions:
        answer = input(f"{question}: ")
        responses[question] = answer
    
    # Resume workflow with answers using Command.resume
    final_result = asyncio.run(
        graph.ainvoke(Command(resume={"questions": responses}), config=config)
    )
```

#### Human Approval Method
The `human_approval` method uses LangGraph's `interrupt()` function to pause execution and collect user input. It requires at least 3 non-empty answers before proceeding to ensure adequate context is gathered.

### Tool Schema Information

Each tool includes comprehensive schema information:

```python
tool_schema = {
    'name': 'microsoft_mail_send_email_as_user',
    'description': 'Send an email through Microsoft Graph API...',
    'args_schema': {
        'type': 'object',
        'properties': {
            'sender_email': {
                'type': 'string',
                'description': 'Email address of the sender'
            },
            'recipients': {
                'type': 'array',
                'description': 'List of recipient email addresses'
            }
        },
        'required': ['sender_email', 'recipients']
    }
}
```

## Dependencies

### Required Packages
- `langgraph` - Workflow orchestration with StateGraph and interrupts
- `pydantic` - Data validation and structured response models
- `boto3` - AWS integration for prompt warehouse
- `asyncio` - Asynchronous operations
- `uuid` - Unique identifier generation for thread IDs

### External Dependencies
- **MCP Servers** - For remote tool access via MCP protocol
- **Prompt Warehouse** - AWS Bedrock prompts (collector, tools, feedback, expansion)
- **LLM Module** - AI model integration with formatted response support
- **Global.Collector.connectors** - Connector discovery and tool loading
- **Global.Components.STR** - String processing utilities

## Error Handling

The module includes comprehensive error handling:

- **MCP Connection Failures** - Falls back to local tools only
- **Tool Loading Errors** - Continues with available tools
- **Prompt Warehouse Issues** - Uses fallback prompts
- **User Input Validation** - Ensures required answers

## Troubleshooting

### Common Issues

1. **"No tools found for connector"**
   - Check MCP server configuration
   - Verify server is running
   - Check network connectivity

2. **"Failed to import MCP tools"**
   - Ensure MCP module is properly installed
   - Check Python path configuration

3. **Prompt warehouse errors**
   - Verify AWS credentials
   - Check Bedrock service availability
   - Ensure prompt exists in warehouse

### Debug Mode

Enable detailed logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Run collector with detailed output
collector = Collector(agent_description)
```

## Examples

### Complete Example: Email Campaign Agent

```python
import asyncio
import uuid
from Global.Collector.agent import Collector

async def create_email_agent():
    # Define what you want the agent to do
    description = """
    I want an agent that:
    1. Reads email addresses from a SharePoint document
    2. Extracts contact information 
    3. Sends personalized cold emails about our new product
    4. Tracks email delivery status
    """
    
    # Create and run collector
    collector = Collector(description, user_email="user@example.com")
    graph = collector.init_agent()
    
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    
    result = await graph.ainvoke({
        "input": description,
        "connectors": [],
        "feedback_questions": [],
        "answered_questions": [],
        "reviewed": False,
        "connector_tools": {},
        "final_result": {}
    }, config=config)
    
    # Handle interactive feedback if needed
    if '__interrupt__' in result:
        print("Collector needs more information...")
        # Handle user input here
    
    return result

# Run the example
result = asyncio.run(create_email_agent())
```

This will automatically identify Microsoft connectors and select tools like:
- `microsoft_sharepoint_download_and_extract_text`
- `microsoft_mail_send_email_as_user`

The final result will include both the expanded task description and the selected tools with their descriptions.

## Integration with Other Modules

The Collector integrates seamlessly with:

- **Skeleton Module** - Uses selected tools to build workflow graphs
- **LLM Module** - AI-powered analysis and selection
- **MCP Module** - Tool discovery and loading
- **Prompt Warehouse** - Standardized AI prompts

The output format is specifically designed for direct use with the Skeleton module for automated workflow generation. 