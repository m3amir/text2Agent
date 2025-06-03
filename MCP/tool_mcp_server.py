#!/usr/bin/env python3
"""Universal Tool MCP Server - Stdio"""

import os, sys, json, asyncio, importlib.util, inspect
from typing import Dict, Any

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:
    print("MCP library required: pip install mcp")
    sys.exit(1)

class UniversalToolServer:
    def __init__(self):
        self.server = Server("universal-tool-server")
        self.tools = []
        self.handlers = {}
        self.config = None  # Cache config
        self._setup_handlers()
    
    def _setup_handlers(self):
        @self.server.list_tools()
        async def list_tools():
            return self.tools
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]):
            return await self.handlers.get(name, lambda _: [TextContent(type="text", text="Tool not found")])(arguments)
    
    def _load_config(self):
        """Load and cache config file"""
        if not self.config:
            config_path = os.path.join(os.path.dirname(__file__), "Config", "mcp_servers_config.json")
            with open(config_path) as f:
                self.config = json.load(f)
        return self.config
    
    async def initialize(self):
        """Initialize server with local and remote tools"""
        await self._load_local_tools()
        await self._load_remote_tools()
        print(f"🚀 Server ready with {len(self.tools)} tools", file=sys.stderr)
    
    async def _load_local_tools(self):
        """Load tools from Tools directory"""
        config = self._load_config()
        base_dir = os.path.dirname(os.path.dirname(__file__))
        
        for tool_name, tool_config in config.get("local", {}).items():
            try:
                # Import tool module
                tool_file = os.path.join(base_dir, tool_config["path"], "tool.py")
                spec = importlib.util.spec_from_file_location(f"{tool_name}_tool", tool_file)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Find tool class and methods
                tool_class = next((obj for name, obj in inspect.getmembers(module) 
                                 if inspect.isclass(obj) and 'Tool' in name and name != 'Tool'), None)
                
                if tool_class:
                    methods = [name for name in dir(tool_class) 
                             if name.startswith(f"{tool_name}_") and not name.startswith('_')]
                    
                    # Register methods
                    for method_name in methods:
                        self.tools.append(Tool(
                            name=method_name,
                            description=inspect.getdoc(getattr(tool_class, method_name)) or method_name,
                            inputSchema={"type": "object", "properties": {}, "required": []}
                        ))
                        self.handlers[method_name] = self._make_handler(tool_class, method_name)
                    
                    print(f"📁 {tool_name} ({len(methods)} methods)", file=sys.stderr)
            except Exception as e:
                print(f"❌ {tool_name}: {e}", file=sys.stderr)
    
    def _make_handler(self, tool_class, method_name):
        """Create handler for tool method"""
        async def handler(arguments: Dict[str, Any]):
            try:
                credentials = self._get_credentials(tool_class.__name__)
                instance = tool_class(credentials) if credentials else tool_class()
                result = getattr(instance, method_name)(**arguments)
                
                if inspect.iscoroutine(result):
                    result = await result
                
                return [TextContent(type="text", text=str(result))]
            except Exception as e:
                return [TextContent(type="text", text=f"Error: {str(e)}")]
        return handler
    
    def _get_credentials(self, class_name):
        """Get credentials for tool class from config file"""
        config = self._load_config()
        for tool_name, tool_config in config.get("local", {}).items():
            if tool_name.lower() in class_name.lower():
                return tool_config.get("credentials")
        return None
    
    async def _load_remote_tools(self):
        """Load remote MCP server tools"""
        config = self._load_config()
        
        for server_name, server_config in config.get("mcpServers", {}).items():
            try:
                await asyncio.wait_for(self._load_remote_server(server_name, server_config), timeout=10.0)
            except:
                pass  # Silent fail for remote servers
    
    async def _load_remote_server(self, server_name, config):
        """Load tools from remote server"""
        params = StdioServerParameters(
            command=config["command"],
            args=config.get("args", []),
            env={**os.environ, **config.get("env", {})}
        )
        
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools_result = await session.list_tools()
                
                for tool in tools_result.tools:
                    tool_name = f"{config.get('prefix', server_name)}_{tool.name}"
                    self.tools.append(Tool(
                        name=tool_name,
                        description=f"[{server_name}] {tool.description}",
                        inputSchema=tool.inputSchema
                    ))
                    self.handlers[tool_name] = lambda args, cfg=config, orig=tool.name: self._call_remote(cfg, orig, args)
                
                print(f"🔌 {server_name} ({len(tools_result.tools)} tools)", file=sys.stderr)
    
    async def _call_remote(self, config, original_name, arguments):
        """Call remote tool"""
        params = StdioServerParameters(
            command=config["command"],
            args=config.get("args", []),
            env={**os.environ, **config.get("env", {})}
        )
        
        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(original_name, arguments)
                    return result if isinstance(result, list) else [TextContent(type="text", text=str(result))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

async def main():
    """Run the MCP server"""
    server = UniversalToolServer()
    await server.initialize()
    async with stdio_server() as (read_stream, write_stream):
        await server.server.run(read_stream, write_stream, server.server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main()) 