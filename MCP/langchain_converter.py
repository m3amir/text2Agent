"""
Simple MCP to LangChain Converter
"""
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from contextlib import asynccontextmanager

try:
    from langchain_mcp_adapters.tools import load_mcp_tools
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

async def convert_mcp_to_langchain(server_command="python", server_args=["MCP/tool_mcp_server.py"]):
    """Convert MCP tools to LangChain format"""
    
    if not LANGCHAIN_AVAILABLE:
        return []
    
    if not server_command or not server_args:
        return []
    
    server_params = StdioServerParameters(command=server_command, args=server_args)
    
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await load_mcp_tools(session)
    except Exception:
        return []

@asynccontextmanager
async def get_mcp_tools_with_session(server_command="python", server_args=["MCP/tool_mcp_server.py"]):
    """Get MCP tools with an active session context"""
    if not LANGCHAIN_AVAILABLE:
        yield []
        return
    
    if not server_command or not server_args:
        yield []
        return
    
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

async def get_specific_tool(tool_name, server_command="python", server_args=["MCP/tool_mcp_server.py"]):
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

def print_tool_arguments(tool):
    """Print tool arguments in a readable format"""
    if not tool:
        print("No tool provided")
        return
    
    print(f"\n📋 Tool: {tool.name}")
    print(f"📝 Description: {tool.description}")
    
    if hasattr(tool, 'args_schema') and tool.args_schema:
        schema = tool.args_schema
        print(f"\n🔧 Arguments Schema:")
        print(f"   Type: {schema.get('type', 'unknown')}")
        
        properties = schema.get('properties', {})
        required = schema.get('required', [])
        
        if properties:
            print(f"\n📥 Parameters:")
            for param_name, param_info in properties.items():
                is_required = param_name in required
                required_text = "✅ REQUIRED" if is_required else "⚪ Optional"
                param_type = param_info.get('type', 'unknown')
                description = param_info.get('description', 'No description')
                
                print(f"   • {param_name} ({param_type}) - {required_text}")
                print(f"     └─ {description}")
                
                # Show additional constraints
                if 'minimum' in param_info:
                    print(f"     └─ Minimum: {param_info['minimum']}")
                if 'items' in param_info:
                    print(f"     └─ Items type: {param_info['items'].get('type', 'unknown')}")
        
        if required:
            print(f"\n✅ Required Parameters: {', '.join(required)}")
        
        print(f"\n🔄 Response Format: {getattr(tool, 'response_format', 'unknown')}")
    else:
        print("No argument schema available")

async def main():
    """Convert and return LangChain tools, specifically looking for SharePoint tools"""
    # Get all tools first (just to count them)
    tools = await convert_mcp_to_langchain()
    print(f"Converted {len(tools)} tools")
    
    # Now use the session context manager to actually use the tools
    async with get_mcp_tools_with_session() as session_tools:
        # Find the SharePoint tool
        sharepoint_tool = None
        
        print(f"\n🔍 Available tools:")
        for tool in session_tools:
            tool_name = getattr(tool, 'name', getattr(tool, '_name', str(tool)))
            print(f"   • {tool_name}")
            
            # Look for SharePoint tool
            if "sharepoint_List_SharePoint_Folders" in tool_name:
                sharepoint_tool = tool
                print(f"✅ Found SharePoint tool: {tool_name}")
        
        # Return the SharePoint tool if found
        if sharepoint_tool:
            print(f"\n📋 SharePoint Tool Details:")
            print_tool_arguments(sharepoint_tool)
            
            # Try to invoke the tool
            try:
                print(f"\n🚀 Invoking SharePoint tool...")
                result = await sharepoint_tool.ainvoke({})
                print(f"Result: {result}")
            except Exception as e:
                print(f"❌ Error invoking tool: {e}")
            
            return sharepoint_tool
        else:
            print(f"\n❌ No SharePoint folder tool found")
            return None

if __name__ == "__main__":
    asyncio.run(main()) 