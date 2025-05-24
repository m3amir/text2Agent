"""
Simple MCP to LangChain Converter
"""
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

try:
    from langchain_mcp_adapters.tools import load_mcp_tools
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

async def convert_mcp_to_langchain(server_command="python", server_args=["tool_mcp_server.py"]):
    """Convert MCP tools to LangChain format"""
    
    if not LANGCHAIN_AVAILABLE:
        return []
    
    server_params = StdioServerParameters(command=server_command, args=server_args)
    
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await load_mcp_tools(session)
    except Exception:
        return []

async def main():
    """Convert and return LangChain tools"""
    tools = await convert_mcp_to_langchain()
    print(f"Converted {len(tools)} tools")
    print(tools)
    return tools

if __name__ == "__main__":
    asyncio.run(main()) 