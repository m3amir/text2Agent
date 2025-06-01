#!/usr/bin/env python3
"""Simple Universal Tool MCP Server"""

import os, sys, json, asyncio, importlib.util, inspect, glob
from typing import Dict, Any

try:
    from mcp.server import Server, NotificationOptions
    from mcp.server.models import InitializationOptions
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:
    print("MCP library not available. Install with: pip install mcp")
    sys.exit(1)

class SimpleMCPServer:
    def __init__(self):
        self.server = Server("universal-tool-server")
        self.tools = []
        self.handlers = {}
        self.credentials = self._load_credentials()
        self._load_local_tools()
        self._setup_handlers()
    
    def _load_credentials(self):
        """Load credentials from config"""
        config_path = os.path.join(os.path.dirname(__file__), "Config", "config.json")
        try:
            with open(config_path) as f:
                return json.load(f)
        except:
            return {}
    
    def _load_local_tools(self):
        """Load tools from Tools directory"""
        tools_dir = os.path.join(os.path.dirname(__file__), "..", "Tools")
        for tool_file in glob.glob(os.path.join(tools_dir, "*/tool.py")):
            self._load_tool_file(tool_file)
    
    def _load_tool_file(self, tool_file):
        """Load a single tool file"""
        try:
            connector_name = os.path.basename(os.path.dirname(tool_file))
            spec = importlib.util.spec_from_file_location(f"{connector_name}_tool", tool_file)
            module = importlib.util.module_from_spec(spec)
            
            # Add tool directory to path temporarily
            tool_dir = os.path.dirname(tool_file)
            sys.path.insert(0, tool_dir)
            spec.loader.exec_module(module)
            sys.path.remove(tool_dir)
            
            # Find toolkit class
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if obj.__module__ == module.__name__ and not name.startswith('_'):
                    self._register_toolkit(obj, connector_name)
                    break
        except Exception as e:
            print(f"Failed to load {tool_file}: {e}")
    
    def _register_toolkit(self, toolkit_class, connector_name):
        """Register all tools from a toolkit"""
        try:
            connector_key = connector_name.lower()
            creds = self.credentials.get(f"{connector_key}_creds", {})
            
            # Initialize toolkit
            sig = inspect.signature(toolkit_class.__init__)
            if len(sig.parameters) > 1:  # Needs credentials
                if not creds:
                    print(f"Skipping {connector_name} - no credentials provided")
                    return
                toolkit = toolkit_class(creds)
            else:
                toolkit = toolkit_class()
            
            # Register methods as tools
            methods_registered = 0
            for method_name, method in inspect.getmembers(toolkit, inspect.ismethod):
                if method_name.lower().startswith(f"{connector_key}_"):
                    self._register_method(method_name, method, toolkit)
                    methods_registered += 1
            
            if methods_registered > 0:
                print(f"✅ Registered {methods_registered} tools from {connector_name}")
        except Exception as e:
            print(f"❌ Failed to register {connector_name}: {e}")
    
    def _register_method(self, method_name, method, toolkit):
        """Register a single method as a tool"""
        # Get parameters
        sig = inspect.signature(method)
        properties = {}
        required = []
        
        for param_name, param in sig.parameters.items():
            if param_name not in ['self', 'cls']:
                properties[param_name] = {"type": "string", "description": f"Parameter {param_name}"}
                if param.default == inspect.Parameter.empty:
                    required.append(param_name)
        
        # Create tool
        tool = Tool(
            name=method_name,
            description=inspect.getdoc(method) or f"Execute {method_name}",
            inputSchema={
                "type": "object",
                "properties": properties,
                "required": required
            }
        )
        
        self.tools.append(tool)
        self.handlers[method_name] = lambda args, t=toolkit, m=method_name: self._call_method(t, m, args)
    
    async def _call_method(self, toolkit, method_name, arguments):
        """Call a toolkit method"""
        try:
            method = getattr(toolkit, method_name)
            result = await method(**arguments) if asyncio.iscoroutinefunction(method) else method(**arguments)
            return [TextContent(type="text", text=json.dumps(result, default=str) if isinstance(result, (dict, list)) else str(result or "Done"))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    async def _load_remote_tools(self):
        """Load remote MCP server tools"""
        config_path = os.path.join(os.path.dirname(__file__), "Config", "mcp_servers_config.json")
        try:
            with open(config_path) as f:
                config = json.load(f)
            
            for server_name, server_config in config.get("mcpServers", {}).items():
                await self._load_remote_server(server_name, server_config)
        except Exception as e:
            print(f"Failed to load remote servers: {e}")
    
    async def _load_remote_server(self, server_name, config):
        """Load tools from a remote server"""
        try:
            # Prepare environment variables
            env_vars = config.get("env", {})
            current_env = os.environ.copy()
            if env_vars:
                current_env.update({k: str(v) for k, v in env_vars.items()})
            
            params = StdioServerParameters(
                command=config["command"], 
                args=config.get("args", []),
                env=current_env
            )
            
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools_result = await session.list_tools()
                    
                    for tool in tools_result.tools:
                        prefix = config.get("prefix", server_name)
                        tool_name = tool.name if config.get("no_prefix") else f"{prefix}_{tool.name}"
                        
                        remote_tool = Tool(
                            name=tool_name,
                            description=f"[{server_name}] {tool.description}",
                            inputSchema=tool.inputSchema
                        )
                        
                        self.tools.append(remote_tool)
                        self.handlers[tool_name] = lambda args, cfg=config, orig=tool.name: self._call_remote(cfg, orig, args)
                        
            print(f"✅ Loaded {len(tools_result.tools)} tools from {server_name}")
        except Exception as e:
            print(f"❌ Failed to load {server_name}: {e}")
    
    async def _call_remote(self, config, original_name, arguments):
        """Call a remote tool"""
        try:
            # Prepare environment variables
            env_vars = config.get("env", {})
            current_env = os.environ.copy()
            if env_vars:
                current_env.update({k: str(v) for k, v in env_vars.items()})
            
            params = StdioServerParameters(
                command=config["command"], 
                args=config.get("args", []),
                env=current_env
            )
            
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(original_name, arguments)
                    return result if isinstance(result, list) else [TextContent(type="text", text=str(result))]
        except Exception as e:
            return [TextContent(type="text", text=f"Remote error: {str(e)}")]
    
    def _setup_handlers(self):
        """Setup MCP server handlers"""
        @self.server.list_tools()
        async def list_tools():
            return self.tools
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]):
            if name in self.handlers:
                return await self.handlers[name](arguments)
            return [TextContent(type="text", text=f"Tool {name} not found")]
    
    async def run(self):
        """Run the server"""
        # Load remote tools
        await self._load_remote_tools()
        
        print(f"\n🛠️  Simple MCP Server - {len(self.tools)} tools loaded")
        
        # Print all tools in a clear list
        print("\n📋 Available Tools:")
        print("=" * 50)
        for i, tool in enumerate(self.tools, 1):
            print(f"{i:2d}. {tool.name}")
        print("=" * 50)
        
        print("\n🚀 Server starting and ready to accept connections...")
        async with stdio_server() as (read, write):
            print("✅ MCP Server is now running!")
            await self.server.run(read, write, InitializationOptions(
                server_name="universal-tool-server",
                server_version="1.0.0",
                capabilities=self.server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={}
                )
            ))

if __name__ == "__main__":
    asyncio.run(SimpleMCPServer().run()) 