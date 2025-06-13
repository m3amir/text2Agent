# Skeleton Workflow System

A simplified, efficient workflow system for executing tools with AI analysis using LangGraph.

## Overview

The `Skeleton` class creates streamlined workflows that execute tools, analyze results with AI colleagues, and generate visualizations. Simplified from 449 lines to 230 lines while maintaining all core functionality.

## Features

✅ **Tool Execution** - Seamless MCP tool integration and execution  
✅ **AI Colleagues Analysis** - Automated analysis and scoring of tool results  
✅ **Linear Workflow** - Simple tool1 → colleagues → finish flow  
✅ **PNG Visualization** - Automatic workflow diagram generation  
✅ **Real Tool Results** - Executes actual tools with real data  
✅ **Clean Logging** - Comprehensive S3 logging and tracking  
✅ **Minimal Code** - 50% smaller codebase, easier to maintain  
✅ **🚨 Interrupt System** - User confirmation for sensitive operations  

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

### Benefits

1. **Security**: Prevents accidental execution of sensitive operations
2. **Transparency**: User sees exactly what will be executed before it happens
3. **Control**: User has full control over sensitive tool execution
4. **Audit Trail**: All approvals and executions are logged
5. **Flexibility**: Easy to add/remove tools from the guarded list
6. **Seamless**: Workflow continues naturally after approval

### Technical Notes

- **LangGraph Integration**: Uses LangGraph's native interrupt system
- **State Persistence**: All workflow state is preserved during interrupts
- **Flexible Matching**: Handles cases where LLM generates slightly different arguments on resume
- **Thread Safety**: Uses consistent thread IDs for state management
- **Error Handling**: Graceful fallbacks if interrupt/resume fails

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
START → Microsoft → Colleagues → Email → finish → END
                        ↓
                   (conditional routing based on score)
                        ↓
            retry_previous / next_step / finish
```

1. **Tool Nodes**: Execute specified tools from node_tools
2. **Colleagues**: AI analysis with conditional routing based on score
3. **Conditional Edges**: Route to retry, proceed, or finish based on analysis

## Real Example

```python
#!/usr/bin/env python3
import asyncio
from Global.Architect.skeleton import run_skeleton

async def test_skeleton():
    # Test with Microsoft tools
    user_email = "amir@m3labs.co.uk"
    tool_names = ['microsoft_sharepoint_search_files', 'microsoft_mail_send_email_as_user']
    
    result, viz_files = await run_skeleton(user_email, tool_names, "test_workflow")
    
    if result:
        print(f"✅ Status: {result['status']}")
        print(f"🔧 Executed: {result['executed_tools']}")
        print(f"🤝 Analysis: {result['colleagues_analysis'][:100]}...")
        print(f"🎯 Score: {result['colleagues_score']}/10")
        print(f"📁 Files: {viz_files}")

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
- `user_email` (str): User email for logging
- `blueprint` (Dict[str, Any]): Blueprint defining nodes, edges, node_tools, and conditional_edges
- `task_name` (str): Name for the workflow task

**Returns:**
- `result` (dict): Workflow execution results with status, executed_tools, colleagues_analysis, etc.
- `viz_files` (List[str]): Paths to generated PNG visualization files

### `Skeleton(user_email="")`
Core skeleton class for advanced usage.

**Key Methods:**
- `load_tools(tool_names)`: Load MCP tools by name
- `create_skeleton(task, tool_names)`: Build the workflow graph  
- `compile_and_visualize(task_name)`: Compile and generate PNG
- `cleanup_tools()`: Clean up MCP session

## State Schema

```python
class WorkflowState(TypedDict, total=False):
    messages: List[Any]                    # Workflow messages
    executed_tools: List[str]              # Tools that have been executed
    tool_execution_results: List[Dict]     # Detailed tool results
    colleagues_analysis: str               # AI analysis of execution
    colleagues_score: int                  # Quality score (0-10)
    status: str                           # Workflow status
    approved_tools: set                    # User-approved tool executions (interrupt system)
    tool_sequence_index: int               # Current tool position in node
    current_node_tools: str                # JSON string of available tools in current node
```

## File Structure

```
Global/Architect/
├── skeleton.py          # Main Skeleton class (230 lines)
├── README.md           # This file
└── graph_images/       # Auto-generated PNG visualizations
```

## Tool Integration

The skeleton automatically:
- Loads MCP tools by name
- Binds tools to LLM with specific prompts
- Executes tools with generated arguments
- Captures real tool results
- Handles both sync and async tool execution

## AI Colleagues Analysis

After tool execution:
- Analyzes tool results for quality and effectiveness
- Provides detailed written analysis
- Assigns numerical scores (0-10)
- Logs analysis to S3 for tracking

## Simplifications Made

**Removed (from 449 → 230 lines):**
- Complex configuration system
- Verbose debug output  
- Complex routing/conditional edges
- Redundant state fields
- Blueprint parsing complexity

**Kept:**
- Core tool execution
- Colleagues AI analysis
- PNG visualization
- Error handling
- S3 logging
- All essential features

## Error Handling

The system gracefully handles:
- Tool execution failures
- MCP session errors
- Colleagues analysis failures
- PNG generation issues
- Missing tools

## Logging

Comprehensive logging includes:
- Tool loading and execution
- LLM interactions
- Colleagues analysis
- S3 sync operations
- Error tracking

Logs saved to: `Logs/{session_id}/{user_email}/ai_skeleton_{timestamp}.log`

## Contributing

1. Keep the linear workflow simple
2. Maintain tool execution functionality
3. Preserve colleagues analysis integration
4. Update README for changes

## License

Internal use for M3 Labs projects. 