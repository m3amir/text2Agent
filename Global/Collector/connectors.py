"""
Dynamic MCP Connector Discovery
Reads MCP server configuration and provides connector information
"""
import json
import os
import sys
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

def get_static_fallback_connectors():
    """Fallback static connectors in case config loading fails"""
    return {
        "sequential": "Advanced sequential reasoning tools",
        "atlassian": "Atlassian tools for Jira and Confluence integration",
        "clickup": "ClickUp project management and task tracking tools",
        "google": "Google Workspace integration tools",
        "slack": "Slack team communication platform integration",
        "microsoft_teams": "Microsoft Teams communication platform integration",
        "zendesk": "Zendesk customer service platform integration",
        "intercom": "Intercom customer service platform integration",
        "salesforce": "Salesforce CRM platform integration",
        "hubspot": "HubSpot CRM platform integration",
        "mysql": "MySQL database integration",
        "mongodb": "MongoDB NoSQL database integration",
        "notion": "Notion productivity and collaboration tools",
        "google_calendar": "Google Calendar integration",
        "google_docs": "Google Docs integration",
    }

def load_connectors():
    """Load connectors from MCP configuration"""
    try:
        # Try to load from MCP config
        connectors_dict = discover_connectors_from_config()
        
        # If no connectors discovered, use fallback
        if not connectors_dict:
            print("No MCP connectors found in config, using static fallback")
            connectors_dict = get_static_fallback_connectors()
             
        return connectors_dict
    except Exception as e:
        print(f"Failed to discover connectors: {e}")
        print("Using static fallback connectors")
        return get_static_fallback_connectors()

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