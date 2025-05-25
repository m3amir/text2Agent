"""
Dynamic MCP Connector Discovery
Reads MCP server configuration and provides connector information
"""
import json
import os
import sys
import glob
import importlib.util
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

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
    
    try:
        for tool_file in glob.glob(os.path.join(tools_dir, "*/tool.py")):
            connector_name = os.path.basename(os.path.dirname(tool_file)).lower()
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