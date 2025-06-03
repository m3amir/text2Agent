"""
Simple MCP to LangChain Converter - Connects to stdio server
"""
import asyncio
import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from contextlib import asynccontextmanager

# Import server functionality
try:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(__file__))
    from tool_mcp_server import get_server
    SERVER_AVAILABLE = True
except ImportError:
    SERVER_AVAILABLE = False

try:
    from langchain_mcp_adapters.tools import load_mcp_tools
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

# Server parameters for our universal tool server
TOOL_SERVER_COMMAND = "python"
TOOL_SERVER_ARGS = [os.path.join(os.path.dirname(__file__), "tool_mcp_server.py")]

async def convert_mcp_to_langchain(server_command=None, server_args=None):
    """Convert MCP tools to LangChain format"""
    
    if not LANGCHAIN_AVAILABLE:
        return []
    
    # Use default server if none specified
    if not server_command:
        server_command = TOOL_SERVER_COMMAND
    if not server_args:
        server_args = TOOL_SERVER_ARGS
    
    server_params = StdioServerParameters(command=server_command, args=server_args)
    
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await load_mcp_tools(session)
    except Exception as e:
        print(f"Error connecting to MCP server: {e}")
        return []

@asynccontextmanager
async def get_mcp_tools_with_session(server_command=None, server_args=None):
    """Get MCP tools with an active session context"""
    if not LANGCHAIN_AVAILABLE:
        yield []
        return
    
    # Use default server if none specified
    if not server_command:
        server_command = TOOL_SERVER_COMMAND
    if not server_args:
        server_args = TOOL_SERVER_ARGS
    
    server_params = StdioServerParameters(command=server_command, args=server_args)
    
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await load_mcp_tools(session)
                yield tools
    except Exception as e:
        print(f"Error creating MCP session: {e}")
        yield []

async def get_specific_tool(tool_name, server_command=None, server_args=None):
    """Get a specific tool by name"""
    tools = await convert_mcp_to_langchain(server_command, server_args)
    
    for tool in tools:
        if hasattr(tool, 'name') and tool.name == tool_name:
            return tool
        elif hasattr(tool, '_name') and tool._name == tool_name:
            return tool
        elif str(tool).find(tool_name) != -1:
            return tool
    
    return None

async def get_connectors_tools_formatted(connector_names, tools=None):
    """
    Get formatted string of tools for a list of connectors
    
    Args:
        connector_names (list): List of connector names (e.g., ['sharepoint', 'ms365'])
        tools (list, optional): Pre-loaded tools list to avoid reconnecting
    
    Returns:
        str: Formatted string with tools, descriptions, and argument schemas
    """
    if not isinstance(connector_names, list):
        connector_names = [connector_names]
    
    result_parts = []
    
    try:
        # Use provided tools or connect to get them
        if tools is None:
            async with get_mcp_tools_with_session() as session_tools:
                tools = session_tools
        
        for connector_name in connector_names:
            connector_tools = []
            
            # Filter tools for this connector
            for tool in tools:
                tool_name = getattr(tool, 'name', getattr(tool, '_name', str(tool)))
                if tool_name.lower().startswith(f"{connector_name.lower()}_"):
                    connector_tools.append(tool)
            
            if connector_tools:
                # Format this connector's section
                connector_section = f"\n🔧 **{connector_name.upper()} CONNECTOR** ({len(connector_tools)} tools)\n" + "="*60 + "\n"
                
                for i, tool in enumerate(connector_tools, 1):
                    tool_name = getattr(tool, 'name', str(tool))
                    description = getattr(tool, 'description', 'No description available')
                    
                    tool_section = f"\n{i:2d}. **{tool_name}**\n"
                    tool_section += f"    📝 Description: {description}\n"
                    
                    # Add argument schema if available
                    if hasattr(tool, 'args_schema') and tool.args_schema:
                        schema = tool.args_schema
                        properties = schema.get('properties', {})
                        required = schema.get('required', [])
                        
                        if properties:
                            tool_section += "    🔧 Parameters:\n"
                            for param_name, param_info in properties.items():
                                is_required = param_name in required
                                required_text = "✅ REQUIRED" if is_required else "⚪ Optional"
                                param_type = param_info.get('type', 'unknown')
                                param_desc = param_info.get('description', 'No description')
                                
                                tool_section += f"       • {param_name} ({param_type}) - {required_text}\n"
                                tool_section += f"         └─ {param_desc}\n"
                        else:
                            tool_section += "    🔧 No parameters required\n"
                    else:
                        tool_section += "    ⚠️  No schema information available\n"
                    
                    tool_section += "    " + "-"*50 + "\n"
                    connector_section += tool_section
                
                result_parts.append(connector_section)
            else:
                result_parts.append(f"\n❌ **{connector_name.upper()} CONNECTOR** - No tools found\n")
        
        return "\n".join(result_parts) if result_parts else "❌ No tools found for any connector"
        
    except Exception as e:
        return f"❌ Error retrieving tools: {str(e)}"

async def main():
    """Test the get_connectors_tools_formatted function with debugging"""
    print("🧪 Testing get_connectors_tools_formatted function...\n")
    
    try:
        # Connect once and reuse the tools
        print("🔌 Testing basic MCP connection...")
        async with get_mcp_tools_with_session() as tools:
            print(f"✅ Connected! Found {len(tools)} tools")
            
            # Show first few tool names
            print("\n📋 First 5 tools:")
            for i, tool in enumerate(tools[:5]):
                tool_name = getattr(tool, 'name', str(tool))
                print(f"  {i+1}. {tool_name}")
            
            print("\n" + "-"*50)
            print("🧪 Testing formatter with SharePoint connector...")
            
            # Test with tools already loaded
            formatted_output = await get_connectors_tools_formatted(['sharepoint'], tools)
            print(formatted_output)
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()

# if __name__ == "__main__":
#     asyncio.run(main())