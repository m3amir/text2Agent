"""
Dynamic MCP Connector Discovery
Reads MCP server configuration and provides connector information
"""
import json
import os
import sys
import glob
import importlib.util
import asyncio
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# Import MCP functionality
try:
    # Import get_mcp_tools_with_session from langchain_converter
    converter_path = os.path.join(os.path.dirname(__file__), '..', '..', 'MCP', 'langchain_converter.py')
    spec = importlib.util.spec_from_file_location("langchain_converter", converter_path)
    langchain_converter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(langchain_converter)
    get_mcp_tools_with_session = langchain_converter.get_mcp_tools_with_session
except Exception as e:
    print(f"Failed to import langchain_converter: {e}")
    get_mcp_tools_with_session = None

def load_mcp_servers_config():
    """Load MCP servers configuration from JSON file"""
    config_path = Path(__file__).parent.parent.parent / "MCP" / "Config" / "mcp_servers_config.json"
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        return config.get("mcpServers", {})
    except Exception as e:
        print(f"Failed to load MCP config: {e}")
        return {}

def discover_connectors_from_config():
    """Discover connectors from MCP configuration file"""
    servers_config = load_mcp_servers_config()
    connectors_dict = {}
    
    for server_name, server_config in servers_config.items():
        # Extract prefix for this server
        prefix = server_config.get("prefix", server_name)
        description = server_config.get("description", f"Tools from {server_name}")
        
        connectors_dict[prefix] = description
    
    return connectors_dict

def get_local_tool_description(connector_name, tool_path):
    """Get description from local tool.py file"""
    try:
        if os.path.exists(tool_path):
            # Import the tool module
            spec = importlib.util.spec_from_file_location(f"{connector_name}_tool", tool_path)
            module = importlib.util.module_from_spec(spec)
            
            # Add tool directory to path temporarily
            tool_dir = os.path.dirname(tool_path)
            sys.path.insert(0, tool_dir)
            spec.loader.exec_module(module)
            sys.path.remove(tool_dir)
            
            # Get description variable if it exists
            if hasattr(module, 'description'):
                return module.description
        
        return f"Available tools for {connector_name}"
    except Exception as e:
        print(f"Failed to load description for {connector_name}: {e}")
        return f"Available tools for {connector_name}"

def discover_local_tools():
    """Discover local tools from Tools directory"""
    local_connectors = {}
    tools_dir = Path(__file__).parent.parent.parent / "Tools"
    
    # Also load local config descriptions
    config_path = Path(__file__).parent.parent.parent / "MCP" / "Config" / "mcp_servers_config.json"
    local_config_descriptions = {}
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            local_section = config.get("local", {})
            for name, config_data in local_section.items():
                local_config_descriptions[name] = config_data.get("description", f"Available tools for {name}")
    except Exception as e:
        print(f"Failed to load local descriptions from config: {e}")
    
    try:
        for tool_file in glob.glob(os.path.join(tools_dir, "*/tool.py")):
            connector_name = os.path.basename(os.path.dirname(tool_file)).lower()
            
            # Use config description if available, otherwise get from tool file
            if connector_name in local_config_descriptions:
                description = local_config_descriptions[connector_name]
            else:
                description = get_local_tool_description(connector_name, tool_file)
                
            local_connectors[connector_name] = description
            
        return local_connectors
    except Exception as e:
        print(f"Failed to discover local tools: {e}")
        return {}

def load_connectors():
    """Load connectors from MCP configuration and local tools"""
    try:
        # Load remote MCP connectors from config
        remote_connectors = discover_connectors_from_config()
        
        # Load local tools from Tools directory
        local_connectors = discover_local_tools()
        
        # Combine both (local tools take precedence for descriptions)
        all_connectors = {**remote_connectors, **local_connectors}
        
        return all_connectors
    except Exception as e:
        print(f"Failed to discover connectors: {e}")
        return {}

def get_connectors():
    """Get the discovered connectors dictionary"""
    return load_connectors()

async def get_connector_tools(connector_name):
    """
    Get tools associated with a specific connector name from the MCP server
    
    Args:
        connector_name (str): Name of the connector (e.g., 'sharepoint', 'ms365')
    
    Returns:
        dict: Dictionary containing:
            - 'tools': List of tool objects
            - 'tool_schemas': Dictionary mapping tool names to their argument schemas
            - 'tool_count': Number of tools found
    """
    if get_mcp_tools_with_session is None:
        print("❌ MCP tools not available - langchain_converter import failed")
        return {'tools': [], 'tool_schemas': {}, 'tool_count': 0}
        
    try:
        async with get_mcp_tools_with_session() as session_tools:
            connector_tools = []
            tool_schemas = {}
            
            # Filter tools that match the connector name
            for tool in session_tools:
                tool_name = getattr(tool, 'name', getattr(tool, '_name', str(tool)))
                
                # Check if tool belongs to this connector (starts with connector_name_)
                if tool_name.lower().startswith(f"{connector_name.lower()}_"):
                    connector_tools.append(tool)
                    
                    # Extract tool argument schema
                    tool_schema = {
                        'name': tool_name,
                        'description': getattr(tool, 'description', 'No description available'),
                        'args_schema': None
                    }
                    
                    # Get argument schema if available
                    if hasattr(tool, 'args_schema') and tool.args_schema:
                        schema = tool.args_schema
                        tool_schema['args_schema'] = {
                            'type': schema.get('type', 'object'),
                            'properties': schema.get('properties', {}),
                            'required': schema.get('required', []),
                            'description': schema.get('description', '')
                        }
                    
                    tool_schemas[tool_name] = tool_schema
            
            return {
                'tools': connector_tools,
                'tool_schemas': tool_schemas,
                'tool_count': len(connector_tools)
            }
            
    except Exception as e:
        print(f"❌ Error getting tools for connector '{connector_name}': {e}")
        return {
            'tools': [],
            'tool_schemas': {},
            'tool_count': 0
        }

def get_connector_tools_sync(connector_name):
    """
    Synchronous wrapper for get_connector_tools
    
    Args:
        connector_name (str): Name of the connector
    
    Returns:
        dict: Same as get_connector_tools
    """
    return asyncio.run(get_connector_tools(connector_name))

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