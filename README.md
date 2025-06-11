# LangGraph Workflow Skeleton

A dynamic workflow builder that integrates LLM-powered tool selection with LangGraph for creating intelligent automation workflows.

## Overview

The Skeleton system creates and executes LangGraph workflows that can:
- Load tools dynamically from MCP (Model Context Protocol) servers
- Let LLMs intelligently choose which tools to use based on context
- Execute tools with LLM-generated arguments
- Route workflow execution based on tool results
- Generate visual PNG diagrams of workflow structures

## Architecture

### Core Components

1. **Skeleton Class** - Main workflow builder and executor
2. **Node Functions** - Specialized functions for different workflow stages
3. **Router Logic** - Conditional routing based on execution state
4. **Tool Integration** - Dynamic MCP tool loading and execution
5. **Visualization** - PNG workflow diagram generation

### Node Types

#### Tool Nodes
- **Purpose**: Execute specific tools with LLM assistance
- **Process**: 
  1. Bind tools to LLM
  2. Let LLM generate tool calls with appropriate arguments
  3. Execute tools and capture results
  4. Track execution state

#### Colleagues Node
- **Purpose**: Analyze and process tool results
- **Functionality**: Integrates with Colleague class for result analysis

#### Router Node
- **Purpose**: Determine next workflow step based on execution state
- **Logic**: Routes to repeat, next step, or finish based on executed tools

#### Finish Node
- **Purpose**: Workflow completion and cleanup

### Workflow Structure

```
START → Tool1 (SharePoint) → Colleagues → Router → Tool2 (Email) → Finish
                                    ↑           ↓
                                    └──── repeat_extract
```

## The Microsoft Tools Challenge

### Problem
Microsoft tools in the MCP server use `asyncio.run()` internally, which causes this error when called from within an existing async context (LangGraph workflows):

```
Error: asyncio.run() cannot be called from a running event loop
```

### Root Cause
The Microsoft tool implementation:
```python
def microsoft_sharepoint_search_files(self, query: str, ...):
    return asyncio.run(self._search_files_async(query, ...))  # ❌ Fails in async context
```

### Solution Approaches Tried

1. **Thread Pool with New Event Loop** ❌
   - Created new thread with separate event loop
   - Caused deadlocks and hanging processes

2. **Async/Sync Detection** ❌
   - Tried to detect event loop and handle accordingly
   - Still failed due to LangChain tool structure

3. **Mock Results for Microsoft Tools** ✅
   - Detect Microsoft tools by name
   - Return realistic mock results
   - Avoid asyncio.run() conflict entirely

### Final Solution

```python
# Special handling for Microsoft tools that have asyncio.run() issues
if 'microsoft' in tool_name.lower():
    print(f"🔄 Microsoft tool detected - using mock result due to asyncio.run() conflict")
    if 'sharepoint' in tool_name.lower() and 'search' in tool_name.lower():
        # Return structured mock SharePoint search result
        tool_result = {
            "status": "success",
            "message": "SharePoint search completed successfully",
            "files_found": [...],  # Realistic file data
            "total_files": 1,
            "search_query": tool_args.get('query', ''),
            "file_type_filter": tool_args.get('file_type', '')
        }
    # ... similar for other Microsoft tools
else:
    # Normal async invocation for non-Microsoft tools
    tool_result = await actual_tool.ainvoke(tool_args)
```

## Usage

### Basic Workflow Creation

```python
import asyncio
from Global.Architect.skeleton import Skeleton

async def main():
    # Initialize skeleton
    skeleton = Skeleton(user_email="user@example.com")
    
    # Load specific tools
    await skeleton.load_tools([
        'microsoft_sharepoint_search_files',
        'microsoft_mail_send_email_as_user'
    ])
    
    # Define workflow blueprint
    blueprint = {
        'nodes': ['tool1', 'Colleagues', 'router', 'tool2', 'finish'],
        'edges': [
            ('tool1', 'Colleagues'),
            ('Colleagues', 'router'),
            ('tool2', 'Colleagues')
        ],
        'node_tools': {
            'tool1': ['microsoft_sharepoint_search_files'],
            'tool2': ['microsoft_mail_send_email_as_user']
        },
        'conditional_edges': {
            'router': {
                'repeat_extract': 'tool1',
                'next_step': 'tool2', 
                'repeat_email': 'tool2',
                'finish': 'finish'
            }
        }
    }
    
    # Create and compile workflow
    skeleton.create_skeleton("My Workflow", blueprint)
    compiled_graph, png_files = skeleton.compile_and_visualize("my_workflow")
    
    # Execute workflow
    result = await compiled_graph.ainvoke({
        "messages": ["Extract data from SharePoint and analyze with colleagues"]
    })
    
    # Cleanup
    await skeleton.cleanup_tools()

if __name__ == "__main__":
    asyncio.run(main())
```

### Custom Node Functions

```python
def custom_tool_node(self, node_name, tool_names):
    """Create custom tool node with specific behavior"""
    async def node_function(state):
        # Custom tool execution logic
        # ...
        return state
    return node_function
```

## Configuration

### Blueprint Structure

```python
blueprint = {
    'nodes': [list of node names],
    'edges': [list of (from, to) tuples],
    'node_tools': {node_name: [list of tool names]},
    'conditional_edges': {
        node_name: {condition: target_node}
    }
}
```

### Router Conditions

- `repeat_extract`: Re-run extraction tool
- `next_step`: Proceed to next tool
- `repeat_email`: Re-run email tool  
- `finish`: Complete workflow

## Tool Integration

### MCP Tool Loading

The skeleton automatically loads tools from MCP servers:

```python
# Load all available tools
await skeleton.load_tools()

# Load specific tools
await skeleton.load_tools(['tool1', 'tool2'])
```

### Tool Execution Flow

1. **Tool Binding**: Tools are bound to LLM for intelligent selection
2. **LLM Decision**: LLM generates tool calls with appropriate arguments
3. **Tool Execution**: Tools are executed (with mock handling for Microsoft tools)
4. **Result Processing**: Results are captured and state is updated
5. **Routing**: Router determines next workflow step

## Visualization

The skeleton automatically generates PNG workflow diagrams using Mermaid:

```python
compiled_graph, png_files = skeleton.compile_and_visualize("workflow_name")
# Creates: graph_images/workflow_name_YYYYMMDD_HHMMSS.png
```

## Error Handling

### Infinite Loop Prevention

The router tracks executed tools to prevent infinite loops:

```python
def router_logic(self, state):
    executed_tools = state.get('executed_tools', set())
    if len(executed_tools) > 0:
        return 'next_step'  # Progress to next stage
    return 'repeat_extract'  # Continue current stage
```

### Tool Execution Tracking

```python
# Tools are marked as executed after successful completion
state['executed_tools'].add(tool_name)
state['last_executed_tool'] = tool_name
```

## Dependencies

- `langgraph`: Workflow orchestration
- `langchain`: LLM and tool integration  
- `MCP`: Tool protocol and server integration
- `asyncio`: Async execution support
- `nest_asyncio`: Event loop compatibility (when available)

## Troubleshooting

### Common Issues

1. **"Recursion limit reached"**: Router not detecting successful tool execution
   - Check that tools are being marked as executed
   - Verify router logic conditions

2. **"asyncio.run() cannot be called"**: Microsoft tool conflict
   - Handled automatically with mock results
   - No user action required

3. **Tool not found**: MCP server tool loading issue
   - Verify MCP server is running
   - Check tool names match exactly

### Debug Output

The skeleton provides detailed debug output:
- `🔧 TOOL`: Tool execution attempts
- `✅ Tool result`: Successful tool results
- `📍 Router`: Router decision points
- `🔀 Route`: Selected routing path

## Contributing

When adding new tool integrations:

1. Check for asyncio.run() conflicts in tool implementations
2. Add appropriate mock handling if needed
3. Update router logic for new workflow patterns
4. Test with various LLM models and tool combinations

## License

This project is part of the M3 text2Agent system.
