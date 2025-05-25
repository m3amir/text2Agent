import sys
import os
import asyncio

# Add the project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from MCP.langchain_converter import convert_mcp_to_langchain

async def router():
    """Connect to the universal MCP server and get all tools"""
    print("Connecting to universal MCP server...")
    
    # Connect to the universal tool server
    tools = await convert_mcp_to_langchain(
        server_command="python3",
        server_args=[os.path.join(os.path.dirname(__file__), "..", "..", "MCP", "tool_mcp_server.py")]
    )
    
    print(f"Total tools from universal server: {len(tools)}")
    print("-" * 60)
    
    # Print each tool on a new line
    for tool in tools:
        name = tool.name
        description = getattr(tool, 'description', 'No description')
        print(f"Tool: {name}")
        print(f"Description: {description}")
        print("-" * 60)
    
    # Return simplified tool info
    return [{"name": tool.name, "description": getattr(tool, 'description', 'No description')} 
            for tool in tools]

if __name__ == "__main__":
    result = asyncio.run(router())