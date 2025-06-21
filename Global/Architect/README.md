# Skeleton Workflow System

A comprehensive workflow system for executing tools with AI analysis using LangGraph.

## Overview

The `Skeleton` class creates intelligent workflows that execute tools, analyze results with AI colleagues, and generate visualizations. Features sophisticated tool sequencing, context-aware prompting, and interrupt handling for sensitive operations.

## Features

✅ **Tool Execution** - Seamless MCP tool integration and execution  
✅ **AI Colleagues Analysis** - Automated analysis and scoring of tool results  
✅ **Blueprint-Based Workflow** - Flexible workflow definition with nodes, edges, and conditional routing  
✅ **PNG Visualization** - Automatic workflow diagram generation  
✅ **Real Tool Results** - Executes actual tools with real data  
✅ **Clean Logging** - Comprehensive S3 logging and tracking  
✅ **Context-Aware Prompting** - Builds context from previous tool results  
✅ **🚨 Interrupt System** - User confirmation for sensitive operations  
✅ **Special Tool Support** - Custom prompting for chart and PDF generation tools  
✅ **Tool Sequencing** - Intelligent tool ordering with retry logic  
✅ **State Management** - Comprehensive state tracking with LangGraph  

## 🚨 Interrupt System

The Skeleton system includes a powerful interrupt mechanism that pauses workflow execution before sensitive tools (like email sending) to require user confirmation.

### How It Works

1. **Automatic Detection**: Workflow automatically detects when a "guarded" tool is about to execute
2. **LangGraph Interrupt**: Uses LangGraph's built-in `interrupt()` function to pause execution
3. **User Confirmation**: Shows complete tool details and asks for user approval
4. **Seamless Resume**: After approval, workflow continues from exactly where it left off
5. **State Persistence**: All workflow state is preserved during the interrupt

### Guarded Tools

By default, these tools require user confirmation:
- `microsoft_mail_send_email_as_user`
- `microsoft_send_email_as_user`

### Configuration

```python
# In Skeleton class initialization
self.guarded = {
    'microsoft_mail_send_email_as_user', 
    'microsoft_send_email_as_user'
}

# Add more tools to require confirmation
skeleton.guarded.add('dangerous_tool_name')
```

### Interrupt Flow Example

```python
# Normal execution until email tool
🔧 tool_node_execute: microsoft_sharepoint_search_files ✅
🔧 colleagues_analysis: Score 9.5/10 ✅  
🔧 tool_node_execute: microsoft_sharepoint_download_and_extract_text ✅
🔧 colleagues_analysis: Score 9.5/10 ✅
🔧 tool_node_execute: microsoft_mail_send_email_as_user 🚨

# Workflow pauses and shows details:
🔴 WORKFLOW INTERRUPTED!
📧 About to execute: microsoft_mail_send_email_as_user
Recipients: ['user@example.com']
Subject: Lead Information  
Body: Hello! We have some lead information for you...

Do you want to continue? (y/n): y

# After approval, workflow resumes automatically:
✅ User approved - resuming workflow...
🔧 tool_node_execute: microsoft_mail_send_email_as_user ✅
✅ SUCCESS - Email sent after user approval!
```

### Implementation Details

#### Interrupt Detection
```python
def _should_interrupt(self, tool_name: str, tool_args: Dict, state: Dict) -> bool:
    if tool_name not in self.guarded:
        return False
    
    # Check if tool was already approved
    approved_tools = state.get('approved_tools', set()) or set()
    
    # Flexible approval checking - handles LLM argument variations
    for approved_key in approved_tools:
        if approved_key.startswith(f"{tool_name}:"):
            return False
    
    return True
```

#### State Management
```python
class WorkflowState(TypedDict, total=False):
    # ... existing fields ...
    approved_tools: Annotated[set, replace_value]  # Tracks user approvals
```

#### Resume Logic
```python
# After user approval:
compiled_graph.update_state(config, {"approved_tools": approved_tools})

# Workflow continues automatically using stream
async for chunk in compiled_graph.astream(None, config=config):
    result = chunk
```

### Complete Example with Interrupt

```python
import asyncio
from Global.Architect.skeleton import run_skeleton

async def test_with_interrupt():
    blueprint = {
        'nodes': ['Microsoft', 'Colleagues', 'finish'],
        'edges': [('Microsoft', 'Colleagues')],
        'conditional_edges': {
            'Colleagues': {
                'retry_same': 'Microsoft',
                'next_tool': 'Microsoft', 
                'next_step': 'finish'
            }
        },
        'node_tools': {
            'Microsoft': [
                'microsoft_sharepoint_search_files',
                'microsoft_sharepoint_download_and_extract_text', 
                'microsoft_mail_send_email_as_user'  # This will trigger interrupt
            ]
        }
    }
    
    try:
        result, viz_files, compiled_graph, skeleton = await run_skeleton(
            user_email='user@example.com',
            blueprint=blueprint,
            task_name='Send email from leads file'
        )
        
        # Check if workflow was interrupted
        if '__interrupt__' in result and result['__interrupt__']:
            interrupt_info = result['__interrupt__'][0].value
            
            print(f"\n🔴 WORKFLOW INTERRUPTED!")
            print(f"📧 About to execute: {interrupt_info.get('tool_name')}")
            print(f"Recipients: {interrupt_info.get('tool_args', {}).get('recipients', [])}")
            print(f"Subject: {interrupt_info.get('tool_args', {}).get('subject', 'No subject')}")
            print(f"Body: {interrupt_info.get('tool_args', {}).get('body', 'No body')[:200]}...")
            
            # Get user confirmation
            user_response = input("\nDo you want to continue? (y/n): ").lower().strip()
            
            if user_response in ['y', 'yes']:
                print("✅ User approved - resuming workflow...")
                
                # Resume workflow
                config = {"configurable": {"thread_id": "workflow_thread"}}
                current_state = compiled_graph.get_state(config)
                tool_execution_key = interrupt_info.get('tool_execution_key')
                
                approved_tools = current_state.values.get('approved_tools', set()) or set()
                approved_tools.add(tool_execution_key)
                
                # Update state and resume
                compiled_graph.update_state(config, {"approved_tools": approved_tools})
                
                result = None
                async for chunk in compiled_graph.astream(None, config=config):
                    result = chunk
                
                final_state = compiled_graph.get_state(config)
                result = final_state.values
                
                print("✅ SUCCESS - Email sent after user approval!")
            else:
                print("❌ User declined - workflow cancelled")
                return None
        
        return result
        
    finally:
        if skeleton:
            await skeleton.cleanup_tools()

if __name__ == "__main__":
    asyncio.run(test_with_interrupt())
```

## 🎯 Special Tool Support

The Skeleton system includes intelligent, context-aware prompting for specific tool types that require special handling.

### Chart Tools

Tools starting with `chart_` receive specialized prompting to ensure proper data formatting:

```python
# Automatic detection and custom prompting for chart tools
if tool_name.startswith('chart_'):
    prompt = f"""You need to generate a chart. Use the {tool_name} tool for: {task}{context}

CRITICAL: Chart tools require a 'data' parameter with a list of dictionaries. You MUST provide sample data in the correct format.

Examples of proper data formats:
- For bar/line charts: [{{"category": "Q1", "sales": 120000}}, {{"category": "Q2", "sales": 150000}}]
- For pie charts: [{{"product": "Product A", "sales": 45000}}, {{"product": "Product B", "sales": 30000}}]

Generate realistic sample data and call the {tool_name} tool with proper arguments including 'data', 'title', and appropriate labels."""
```

**Features:**
- **Automatic Data Generation**: Creates realistic sample data in correct format
- **Format Validation**: Ensures data structure matches chart tool requirements  
- **Context Integration**: Uses task description and previous results for relevant data
- **Multiple Chart Types**: Supports bar, line, pie, and other chart formats

### PDF Tools

Tools starting with `pdf_` receive specialized prompting for report generation:

```python
# Automatic detection and custom prompting for PDF tools
if tool_name.startswith('pdf_'):
    prompt = f"""You need to generate a PDF report. Use the {tool_name} tool for: {task}{context}

CRITICAL: PDF report tools require 'report_content' parameter with text content. To include charts, use placeholder format {{chart_name}} NOT markdown syntax.

For pdf_generate_report:
- report_content: Text content with sections and chart placeholders
- title: Report title  
- author: Report author
- include_header: true/false
- include_footer: true/false

IMPORTANT: To include charts in the report, use simple chart placeholders like {{bar_chart}} or {{pie_chart}} that will match any chart of that type. Do NOT use markdown ![](path) syntax."""
```

**Features:**
- **Chart Integration**: Uses `{{chart_name}}` placeholders instead of markdown syntax
- **Structured Content**: Generates proper report sections and formatting
- **Context-Aware**: Incorporates previous tool results into report content
- **Flexible Templating**: Supports various report structures and layouts

### Context Building

The system builds intelligent context from previous tool results:

```python
def _build_context(self, tool_results: List[Dict]) -> str:
    if not tool_results:
        return ""
    context = "\nPrevious results:\n"
    for result in tool_results[-2:]:  # Uses last 2 results
        context += f"- {result.get('tool')}: {str(result.get('result', ''))}\n"
    return context
```

**Benefits:**
- **Tool Chaining**: Later tools can use results from earlier tools
- **Intelligent Prompting**: LLM gets context about what has already been accomplished
- **Result Integration**: Charts can include data from previous analysis
- **Workflow Continuity**: Maintains coherent workflow narrative

## Quick Start

```python
from Global.Architect.skeleton import run_skeleton

# Blueprint-based execution
blueprint = {
    "nodes": ['Microsoft', 'Colleagues', 'Email', 'finish'],
    "edges": [('Microsoft', 'Colleagues')],
    "conditional_edges": {
        'Colleagues': {
            'retry_previous': 'Microsoft',
            'next_step': 'Email', 
            'finish': 'finish'
        }
    },
    "node_tools": {
        'Microsoft': ['microsoft_sharepoint_search_files'],
        'Email': ['microsoft_mail_send_email_as_user']
    }
}

result, viz_files = await run_skeleton(
    user_email="user@example.com",
    blueprint=blueprint,
    task_name="workflow"
)

print(f"Status: {result['status']}")
print(f"Executed tools: {result['executed_tools']}")
print(f"Colleagues score: {result['colleagues_score']}/10")
print(f"Generated files: {viz_files}")
```

## Workflow Structure

The skeleton builds custom workflows from blueprints with conditional routing:

```
START → Tool Node → Colleagues → Next Tool Node → finish → END
                        ↓
                   (conditional routing based on score)
                        ↓
            retry_same / next_tool / next_step
```

### Node Types

1. **Tool Nodes**: Execute specified tools from `node_tools` with intelligent sequencing
2. **Colleagues Node**: AI analysis with conditional routing based on score
3. **Finish Node**: Marks workflow as completed
4. **Conditional Edges**: Route based on colleagues analysis and tool sequence state

### Colleagues Routing Logic

The colleagues node uses sophisticated routing logic:

```python
def colleagues_router_logic(self, state):
    colleagues_score = state.get('colleagues_score', 0)
    tool_sequence_index = state.get('tool_sequence_index', 0)
    current_node_tools = json.loads(state.get('current_node_tools', '[]'))
    
    # Emergency stop for loops - prevent infinite retries
    executed_tools = state.get('executed_tools', [])
    if executed_tools and executed_tools.count(executed_tools[-1]) >= 3:
        return 'next_tool' if tool_sequence_index < len(current_node_tools) - 1 else 'next_step'
    
    # Check if all tools in current node are complete
    if tool_sequence_index >= len(current_node_tools) - 1:
        return 'next_step'
    
    # Prevent duplicate tool execution
    if tool_sequence_index + 1 < len(current_node_tools):
        next_tool_name = current_node_tools[tool_sequence_index + 1]
        if executed_tools and executed_tools.count(next_tool_name) >= 1:
            return 'next_step'
    
    # Score-based routing
    if colleagues_score >= THRESHOLD_SCORE:  # THRESHOLD_SCORE = 7
        return 'next_tool' if tool_sequence_index < len(current_node_tools) - 1 else 'next_step'
    else:
        return 'retry_same'  # Retry current tool if score too low
```

**Routing Options:**
- `retry_same`: Re-execute the current tool (score < 7)
- `next_tool`: Move to next tool in current node (score ≥ 7, more tools available)
- `next_step`: Move to next workflow node (score ≥ 7, no more tools in current node)

**Safety Features:**
- **Loop Prevention**: Stops infinite retries after 3 attempts of same tool
- **Duplicate Prevention**: Avoids executing the same tool multiple times
- **Bounds Checking**: Ensures tool sequence index stays within valid range

## Blueprint Structure

The blueprint defines the workflow structure using a dictionary format:

```python
blueprint = {
    "nodes": ['DataNode', 'Colleagues', 'EmailNode', 'finish'],
    "edges": [('DataNode', 'Colleagues')],
    "conditional_edges": {
        'Colleagues': {
            'retry_same': 'DataNode',      # Retry current tool if score < 7
            'next_tool': 'DataNode',       # Next tool in current node
            'next_step': 'EmailNode'       # Move to next workflow node
        }
    },
    "node_tools": {
        'DataNode': ['microsoft_sharepoint_search_files', 'microsoft_sharepoint_download_and_extract_text'],
        'EmailNode': ['microsoft_mail_send_email_as_user']
    }
}
```

**Blueprint Components:**
- `nodes`: List of workflow nodes (order matters for START connection)
- `edges`: Static edges between nodes as (from_node, to_node) tuples
- `conditional_edges`: Dynamic routing based on conditions (usually from Colleagues node)
- `node_tools`: Tools available to each node (executed in sequence)

## Real Example

```python
#!/usr/bin/env python3
import asyncio
from Global.Architect.skeleton import run_skeleton

async def test_skeleton():
    # Define workflow blueprint
    blueprint = {
        "nodes": ['Microsoft', 'Colleagues', 'Email', 'finish'],
        "edges": [('Microsoft', 'Colleagues')],
        "conditional_edges": {
            'Colleagues': {
                'retry_same': 'Microsoft',
                'next_tool': 'Microsoft', 
                'next_step': 'Email'
            }
        },
        "node_tools": {
            'Microsoft': ['microsoft_sharepoint_search_files', 'microsoft_sharepoint_download_and_extract_text'],
            'Email': ['microsoft_mail_send_email_as_user']  # This will trigger interrupt
        }
    }
    
    user_email = "amir@m3labs.co.uk"
    
    try:
        result, viz_files, compiled_graph, skeleton = await run_skeleton(
            user_email, blueprint, "test_workflow"
        )
        
        if result:
            print(f"✅ Status: {result['status']}")
            print(f"🔧 Executed: {result['executed_tools']}")
            print(f"🤝 Analysis: {result['colleagues_analysis'][:100]}...")
            print(f"🎯 Score: {result['colleagues_score']}/10")
            print(f"📁 Files: {viz_files}")
            
        # Handle interrupts (if any)
        if '__interrupt__' in result and result['__interrupt__']:
            print("🔴 Workflow interrupted for user approval")
            
    finally:
        # Always cleanup
        if skeleton:
            await skeleton.cleanup_tools()

if __name__ == "__main__":
    asyncio.run(test_skeleton())
```

## Example Output

```bash
🚀 Running skeleton with tools: ['microsoft_sharepoint_search_files', 'microsoft_mail_send_email_as_user']
🔧 Tool node: Available tools: ['microsoft_sharepoint_search_files', 'microsoft_mail_send_email_as_user']
🔧 Tool node: Selected tool: microsoft_sharepoint_search_files
🔧 Tool result: {"success": true, "query": "leads", "files": [{"name": "lead.xlsx", ...}]}
🔧 Added m
icrosoft_sharepoint_search_files to executed tools
✅ Skeleton execution completed!
📊 Status: completed
🔧 Executed tools: ['microsoft_sharepoint_search_files']
🤝 Analysis: Both employees have demonstrated a high level of proficiency...
🎯 Score: 9/10
📁 Generated files: ['graph_images/test_workflow_20250610_231529.png']
```

## API Reference

### `run_skeleton(user_email, blueprint, task_name="workflow")`
Main function to execute a skeleton workflow from blueprint.

**Parameters:**
- `user_email` (str): User email for logging and session management
- `blueprint` (Dict[str, Any]): Blueprint defining nodes, edges, node_tools, and conditional_edges
- `task_name` (str): Name for the workflow task (used for visualization files)

**Returns:**
- `result` (dict): Workflow execution results with status, executed_tools, colleagues_analysis, etc.
- `viz_files` (List[str]): Paths to generated PNG visualization files
- `compiled_graph`: LangGraph compiled workflow for advanced usage
- `skeleton`: Skeleton instance for cleanup and extended operations

**Example:**
```python
result, viz_files, compiled_graph, skeleton = await run_skeleton(
    user_email="user@example.com",
    blueprint=my_blueprint, 
    task_name="data_analysis"
)

# Always cleanup after use
await skeleton.cleanup_tools()
```

### `Skeleton(user_email="")`
Core skeleton class for advanced usage.

**Constructor:**
```python
skeleton = Skeleton(user_email="user@example.com")
```

**Key Methods:**
- `load_tools(tool_names: List[str])`: Load MCP tools by name asynchronously
- `create_skeleton(task: str, blueprint: Dict[str, Any])`: Build the workflow graph from blueprint
- `compile_and_visualize(task_name: str)`: Compile graph and generate PNG visualization
- `cleanup_tools()`: Clean up MCP session and resources
- `colleagues_node(state: WorkflowState)`: Execute colleagues analysis on tool results
- `colleagues_router_logic(state: WorkflowState)`: Determine routing based on colleagues score
- `tool_node_execute(state, tool_names, node_name)`: Execute tools in a workflow node
- `finish_node(state: WorkflowState)`: Mark workflow as completed

**Advanced Properties:**
- `guarded` (set): Set of tool names requiring user approval before execution
- `available_tools` (dict): Dictionary of loaded MCP tools by name
- `THRESHOLD_SCORE` (int): Score threshold for colleagues routing (default: 7)

## State Schema

```python
class WorkflowState(TypedDict, total=False):
    messages: Annotated[List[Any], add_messages]                    # Workflow messages with LangGraph message handling
    executed_tools: Annotated[List[str], operator.add]             # Tools that have been executed (cumulative)
    tool_execution_results: Annotated[List[Dict[str, Any]], operator.add]  # Detailed tool results (cumulative)
    colleagues_analysis: str                                        # AI analysis of execution
    colleagues_score: float                                         # Quality score (0-10, float precision)
    status: str                                                     # Workflow status (e.g., 'completed')
    task: str                                                       # Current task description
    route: str                                                      # Routing decision for conditional edges
    current_node: Annotated[str, replace_value]                    # Currently executing node name
    current_node_tools: Annotated[str, replace_value]              # JSON string of available tools in current node
    tool_sequence_index: Annotated[int, replace_value]             # Current tool position in node sequence
    approved_tools: Annotated[set, replace_value]                  # User-approved tool executions (interrupt system)
```

### State Management Functions

The state uses custom reduction functions for different field types:

```python
def replace_value(existing, new):
    """Replace existing value entirely (for single-value fields)"""
    return new

# Used with Annotated types:
# - add_messages: LangGraph built-in for message handling
# - operator.add: Appends new items to existing lists
# - replace_value: Replaces entire value for single-value fields
```

## File Structure

```
Global/Architect/
├── skeleton.py          # Main Skeleton class (342 lines)
├── README.md           # This file
└── graph_images/       # Auto-generated PNG visualizations
```

## Tool Integration

The skeleton provides comprehensive tool integration:
- **MCP Loading**: Loads MCP tools by name using `get_mcp_tools_with_session`
- **Dynamic Binding**: Binds tools to LLM with context-aware prompts
- **Intelligent Execution**: Executes tools with AI-generated arguments
- **Result Capture**: Captures and stores detailed tool results
- **Async Support**: Handles both sync and async tool execution seamlessly
- **Error Handling**: Graceful fallbacks for tool execution failures
- **Session Management**: Proper cleanup of MCP sessions

## AI Colleagues Analysis

The colleagues system provides intelligent analysis:
- **Result Analysis**: Analyzes tool results for quality and effectiveness
- **Detailed Feedback**: Provides comprehensive written analysis
- **Numerical Scoring**: Assigns precision scores (0-10, float values)
- **Context Integration**: Considers previous results and workflow context
- **Routing Decisions**: Makes intelligent routing decisions based on analysis
- **S3 Logging**: Logs all analysis to S3 for tracking and improvement

## Error Handling

The system provides robust error handling:
- **Tool Execution**: Graceful fallbacks when tools fail, capturing error messages
- **MCP Sessions**: Proper session cleanup even when errors occur
- **Colleagues Analysis**: Default scoring when analysis fails
- **PNG Generation**: Continues workflow execution even if visualization fails
- **Missing Tools**: Skips unavailable tools and continues with available ones
- **State Management**: Preserves workflow state during error conditions
- **Interrupt Recovery**: Handles interrupt/resume cycles with error protection

## Logging

Comprehensive logging system using LogManager:
- **Tool Operations**: Loading, binding, and execution of all tools
- **LLM Interactions**: Model invocations and responses
- **Colleagues Analysis**: Detailed analysis results and scoring
- **Workflow State**: State transitions and routing decisions
- **S3 Sync**: Automatic log synchronization to S3 storage
- **Error Tracking**: Detailed error logs with stack traces
- **Session Management**: MCP session lifecycle events

**Log Structure:**
```
Logs/
└── {session_id}/
    └── {user_email}/
        └── ai_skeleton_{timestamp}.log
```

**Dependencies:**
- `LogManager`: Session-based logging with S3 sync
- `setup_logging`: Configures logging infrastructure
- `sync_logs_to_s3`: Automatic S3 synchronization