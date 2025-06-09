# Skeleton Graph Builder

A simple, clean utility for creating LangGraph workflows from blueprint configurations.

## Overview

The `Skeleton` class automatically builds LangGraph workflows from simple blueprint dictionaries containing nodes and edges. It handles all the boilerplate of creating nodes, adding edges, and setting up proper START/END connections.

## Features

✅ **Simple Blueprint Input** - Define your workflow with just nodes and edges  
✅ **Automatic START/END Handling** - No need to manually wire entry/exit points  
✅ **Duplicate Node Prevention** - Safely handles blueprint duplicates  
✅ **Clean Logging** - Track workflow creation with detailed logs  
✅ **Minimal Code** - Focus on workflow logic, not LangGraph boilerplate  

## Requirements

- Python 3.8+
- LangGraph
- Custom logging utilities (`utils.core`, `Logs.log_manager`)

## Quick Start

```python
from skeleton import Skeleton

# Define your workflow blueprint
blueprint = {
    "nodes": ['Start', 'Process', 'Review', 'Finish'],
    "edges": [
        ('Start', 'Process'),
        ('Process', 'Review'), 
        ('Review', 'Finish')
    ]
}

# Create and compile the workflow
skeleton = Skeleton(user_email="user@example.com")
skeleton.create_skeleton("My workflow task", blueprint)
compiled_graph = skeleton.compile_graph()

# Your workflow is ready to use!
```

## Blueprint Format

The blueprint is a simple dictionary with two keys:

```python
blueprint = {
    "nodes": [
        "node1",      # List of node names (strings)
        "node2", 
        "node3"
    ],
    "edges": [
        ("node1", "node2"),    # Tuples of (from_node, to_node)
        ("node2", "node3")
    ]
}
```

### Automatic Connections

The Skeleton automatically adds:
- **START edge**: From `START` to the first node in your blueprint
- **END edges**: From terminal nodes (nodes with no outgoing edges) to `END`

## Example Workflow

```python
# Example: AI Agent Pipeline
blueprint = {
    "nodes": [
        'STR',           # Strategic Thinking & Reasoning  
        'Colleagues',    # Colleague Consultation
        'Orchestration', # Task Orchestration
        'Execution',     # Task Execution
        'Review',        # Review Results
        'Feedback',      # Gather Feedback
        'Summary'        # Final Summary
    ],
    "edges": [
        ('STR', 'Colleagues'),
        ('Colleagues', 'Orchestration'),
        ('Orchestration', 'Execution'),
        ('Execution', 'Review'),
        ('Review', 'Feedback'),
        ('Feedback', 'Summary'),
        ('Summary', 'Feedback'),  # Feedback loop
    ]
}

skeleton = Skeleton(user_email="amir@m3labs.co.uk")
skeleton.create_skeleton("Build REST API", blueprint)
graph = skeleton.compile_graph()
```

This creates the flow:
```
START → STR → Colleagues → Orchestration → Execution → Review → Feedback → Summary
                                                                    ↑         ↓
                                                                    ← ← ← ← ← ←
```

## API Reference

### `Skeleton(user_email="")`
Initialize a new skeleton builder.

**Parameters:**
- `user_email` (str): User email for logging purposes

### `create_skeleton(task, blueprint)`
Build a workflow from a blueprint.

**Parameters:**
- `task` (str): Description of the task/workflow
- `blueprint` (dict): Dictionary with 'nodes' and 'edges' keys

**Returns:**
- `StateGraph`: The constructed workflow (pre-compilation)

### `compile_graph()`
Compile the workflow into an executable graph.

**Returns:**
- `CompiledGraph`: Ready-to-execute LangGraph

## File Structure

```
Global/Architect/
├── skeleton.py          # Main Skeleton class
├── README.md           # This file
└── graph_images/       # Generated graph visualizations (if created)
```

## Logging

The Skeleton automatically logs:
- Node creation
- Edge addition  
- START/END connections
- Compilation status
- Workflow completion

Logs are saved to: `Logs/{session_id}/{user_email}/ai_skeleton_{timestamp}.log`

## Error Handling

The class gracefully handles:
- Duplicate nodes (skips with logging)
- Missing START connections (auto-added)
- Missing END connections (auto-added)
- Compilation errors (logged and re-raised)

## Advanced Usage

### Custom Node Functions

By default, nodes use placeholder functions. To customize:

```python
# Override the node function creation
def my_custom_node(state):
    # Your custom logic here
    return modified_state

# Replace the placeholder after creation
skeleton.workflow.nodes['MyNode'] = my_custom_node
```

### Multiple Workflows

```python
# Create multiple workflows from different blueprints
skeleton = Skeleton(user_email="user@example.com")

# Workflow 1
skeleton.create_skeleton("Task 1", blueprint1)
graph1 = skeleton.compile_graph()

# Reset for new workflow
skeleton.workflow = StateGraph(MessagesState)
skeleton.create_skeleton("Task 2", blueprint2) 
graph2 = skeleton.compile_graph()
```

## Contributing

1. Keep the code simple and focused
2. Maintain comprehensive logging
3. Handle edge cases gracefully
4. Update this README for new features

## License

Internal use for M3 Labs projects. 