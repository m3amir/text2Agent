"""
Dynamic MCP Connector Discovery
"""
import json
import os
import sys
import importlib.util
import asyncio
import inspect
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# Import MCP functionality
try:
    converter_path = os.path.join(os.path.dirname(__file__), '..', '..', 'MCP', 'langchain_converter.py')
    spec = importlib.util.spec_from_file_location("langchain_converter", converter_path)
    langchain_converter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(langchain_converter)
    get_mcp_tools_with_session = langchain_converter.get_mcp_tools_with_session
except Exception as e:
    print(f"Failed to import langchain_converter: {e}")
    get_mcp_tools_with_session = None

def _load_config():
    """Load MCP servers configuration from JSON file"""
    config_path = Path(__file__).parent.parent.parent / "MCP" / "Config" / "mcp_servers_config.json"
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Failed to load MCP config: {e}")
        return {}

def load_connectors():
    """Load connectors from MCP configuration"""
    config = _load_config()
    connectors = {}
    
    # Add remote MCP connectors
    for server_name, server_config in config.get("mcpServers", {}).items():
        prefix = server_config.get("prefix", server_name)
        description = server_config.get("description", f"Tools from {server_name}")
        connectors[prefix] = description
    
    # Add local connectors
    for connector_name, config_data in config.get("local", {}).items():
        description = config_data.get("description", f"Available tools for {connector_name}")
        tool_path = Path(__file__).parent.parent.parent / config_data.get("path", f"Tools/{connector_name.capitalize()}") / "tool.py"
        
        if tool_path.exists():
            connectors[connector_name] = description
        else:
            print(f"Warning: Tool file not found for {connector_name} at {tool_path}")
    
    return connectors

def _extract_tool_schema(func, tool_name):
    """Extract schema information from a function"""
    sig = inspect.signature(func)
    properties = {}
    required = []
    
    for param_name, param in sig.parameters.items():
        param_type = 'string'
        if param.annotation != inspect.Parameter.empty:
            if param.annotation == int:
                param_type = 'integer'
            elif param.annotation == bool:
                param_type = 'boolean'
            elif param.annotation == list:
                param_type = 'array'
        
        properties[param_name] = {
            'type': param_type,
            'description': f"Parameter {param_name}"
        }
        
        if param.default == inspect.Parameter.empty:
            required.append(param_name)
    
    return {
        'name': tool_name,
        'description': func.__doc__ or f"Local tool: {tool_name}",
        'args_schema': {
            'type': 'object',
            'properties': properties,
            'required': required,
            'description': f"Arguments for {tool_name}"
        } if properties else None
    }

def _load_local_tools(connector_name):
    """Load tools for a specific local connector"""
    config = _load_config()
    local_section = config.get("local", {})
    
    if connector_name not in local_section:
        return {}
    
    connector_config = local_section[connector_name]
    tool_path = Path(__file__).parent.parent.parent / connector_config.get("path", f"Tools/{connector_name.capitalize()}") / "tool.py"
    
    if not tool_path.exists():
        return {}
    
    try:
        # Import the tool module
        spec = importlib.util.spec_from_file_location(f"{connector_name}_tool", tool_path)
        module = importlib.util.module_from_spec(spec)
        
        tool_dir = os.path.dirname(tool_path)
        sys.path.insert(0, tool_dir)
        spec.loader.exec_module(module)
        sys.path.remove(tool_dir)
        
        # Find all functions that start with connector_name_
        tool_schemas = {}
        for attr_name in dir(module):
            if attr_name.startswith(f"{connector_name}_") and callable(getattr(module, attr_name)):
                func = getattr(module, attr_name)
                tool_schemas[attr_name] = _extract_tool_schema(func, attr_name)
        
        return tool_schemas
        
    except Exception as e:
        print(f"❌ Error loading local tools for connector '{connector_name}': {e}")
        return {}

async def get_multiple_connector_tools(connector_names):
    """Get tools for multiple connectors in a single MCP session"""
    all_connector_tools = {}
    
    # Initialize results
    for connector_name in connector_names:
        all_connector_tools[connector_name] = {
            'tools': [],
            'tool_schemas': {},
            'tool_count': 0
        }
    
    # Load MCP tools once for all connectors
    if get_mcp_tools_with_session is not None:
        try:
            async with get_mcp_tools_with_session() as session_tools:
                for tool in session_tools:
                    tool_name = getattr(tool, 'name', getattr(tool, '_name', str(tool)))
                    
                    for connector_name in connector_names:
                        if tool_name.lower().startswith(f"{connector_name.lower()}_"):
                            all_connector_tools[connector_name]['tools'].append(tool)
                            
                            tool_schema = {
                                'name': tool_name,
                                'description': getattr(tool, 'description', 'No description available'),
                                'args_schema': None
                            }
                            
                            if hasattr(tool, 'args_schema') and tool.args_schema:
                                schema = tool.args_schema
                                tool_schema['args_schema'] = {
                                    'type': schema.get('type', 'object'),
                                    'properties': schema.get('properties', {}),
                                    'required': schema.get('required', []),
                                    'description': schema.get('description', '')
                                }
                            
                            all_connector_tools[connector_name]['tool_schemas'][tool_name] = tool_schema
                            break
        except Exception as e:
            print(f"❌ Error getting MCP tools: {e}")
    
    # Load local tools for each connector
    for connector_name in connector_names:
        local_tools = _load_local_tools(connector_name)
        all_connector_tools[connector_name]['tool_schemas'].update(local_tools)
        all_connector_tools[connector_name]['tool_count'] = len(all_connector_tools[connector_name]['tool_schemas'])
    
    return all_connector_tools

def get_multiple_connector_tools_sync(connector_names):
    """Synchronous wrapper for get_multiple_connector_tools"""
    return asyncio.run(get_multiple_connector_tools(connector_names))

def get_connector_tools_sync(connector_name):
    """Get tools for a single connector"""
    result = get_multiple_connector_tools_sync([connector_name])
    return result.get(connector_name, {'tools': [], 'tool_schemas': {}, 'tool_count': 0})

def print_connector_tools(connector_names):
    """
    Print detailed information about tools for specific connector(s)
    
    Args:
        connector_names (str or list): Name(s) of the connector(s) - can be a single string or list of strings
    """
    # Handle both string and list inputs
    if isinstance(connector_names, str):
        connectors_to_process = [connector_names]
    elif isinstance(connector_names, list):
        connectors_to_process = connector_names
    else:
        print(f"❌ Invalid input type. Expected string or list, got {type(connector_names)}")
        return
    
    # Process each connector
    for i, connector_name in enumerate(connectors_to_process):
        if i > 0:  # Add separator between multiple connectors
            print("\n" + "="*80 + "\n")
        
        result = get_connector_tools_sync(connector_name)
        
        if result['tool_count'] == 0:
            print(f"❌ No tools found for connector '{connector_name}'")
            continue
        
        print(f"🔧 Tools for connector '{connector_name}' ({result['tool_count']} tools):")
        print("=" * 60)
        
        for tool_name, schema in result['tool_schemas'].items():
            print(f"\n📋 {tool_name}")
            print(f"   📝 Description: {schema['description']}")
            
            if schema['args_schema']:
                args_schema = schema['args_schema']
                properties = args_schema.get('properties', {})
                required = args_schema.get('required', [])
                
                if properties:
                    print(f"   🔧 Parameters:")
                    for param_name, param_info in properties.items():
                        is_required = param_name in required
                        required_text = "✅ REQUIRED" if is_required else "⚪ Optional"
                        param_type = param_info.get('type', 'unknown')
                        param_desc = param_info.get('description', 'No description')
                        
                        print(f"      • {param_name} ({param_type}) - {required_text}")
                        print(f"        └─ {param_desc}")
                else:
                    print(f"   🔧 No parameters required")
            else:
                print(f"   ⚠️  No schema information available")
            
            print("-" * 40)

# # Export the connectors dictionary
# connectors = get_connectors()

# if __name__ == "__main__":
#     print("Discovered connectors:")
#     result = get_connectors()
#     if result:
#         for name, description in result.items():
#             print(f"  {name}: {description}")
#     else:
#         print("  No connectors discovered")