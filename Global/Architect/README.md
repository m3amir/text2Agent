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

## Requirements

- Python 3.8+
- LangGraph
- MCP tool support
- Custom logging utilities
- Colleague analysis system

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
🔧 Added microsoft_sharepoint_search_files to executed tools
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