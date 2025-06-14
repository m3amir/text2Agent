#!/usr/bin/env python3
"""Universal Tool MCP Server - Stdio"""

import os, sys, json, asyncio, importlib.util, inspect
from typing import Dict, Any

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not available, skip loading
    pass

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
        self.shared_agent_run_id = None  # Shared run ID for all tools
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
                
                # Add tool directory to path temporarily
                tool_dir = os.path.dirname(tool_file)
                sys.path.insert(0, tool_dir)
                spec.loader.exec_module(module)
                sys.path.remove(tool_dir)
                
                methods_found = 0
                
                # Look for standalone functions with tool name prefix
                for attr_name in dir(module):
                    if attr_name.startswith(f"{tool_name}_") and callable(getattr(module, attr_name)) and not attr_name.startswith('_'):
                        func = getattr(module, attr_name)
                        
                        # Get function signature for input schema
                        sig = inspect.signature(func)
                        properties = {}
                        required = []
                        
                        for param_name, param in sig.parameters.items():
                            param_type = 'string'  # Default type
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
                        
                        input_schema = {
                            "type": "object",
                            "properties": properties,
                            "required": required
                        }
                        
                        self.tools.append(Tool(
                            name=attr_name,
                            description=func.__doc__ or f"Tool function: {attr_name}",
                            inputSchema=input_schema
                        ))
                        self.handlers[attr_name] = self._make_function_handler(func)
                        methods_found += 1
                
                # Also check for tool class methods (legacy support)
                all_classes = [(name, obj) for name, obj in inspect.getmembers(module) if inspect.isclass(obj)]
                tool_classes = [(name, obj) for name, obj in all_classes if 'Tool' in name and name != 'Tool']
                tool_class = tool_classes[0][1] if tool_classes else None
                
                if tool_class:
                    class_methods = [name for name in dir(tool_class) 
                                   if name.startswith(f"{tool_name}_") and not name.startswith('_')]
                    
                    # Register class methods
                    for method_name in class_methods:
                        self.tools.append(Tool(
                            name=method_name,
                            description=inspect.getdoc(getattr(tool_class, method_name)) or method_name,
                            inputSchema={"type": "object", "properties": {}, "required": []}
                        ))
                        self.handlers[method_name] = self._make_handler(tool_class, method_name)
                        methods_found += 1
                
                print(f"📁 {tool_name} ({methods_found} methods)", file=sys.stderr)
                
            except Exception as e:
                print(f"❌ {tool_name}: {e}", file=sys.stderr)
    
    def _make_handler(self, tool_class, method_name):
        """Create handler for tool method"""
        async def handler(arguments: Dict[str, Any]):
            try:
                print(f"🔧 Instantiating {tool_class.__name__} for {method_name}", file=sys.stderr, flush=True)
                print(f"📋 Arguments received: {arguments}", file=sys.stderr, flush=True)
                credentials = self._get_credentials(tool_class.__name__)
                
                # Ensure all tools use the same agent run ID
                if not self.shared_agent_run_id:
                    from datetime import datetime
                    import uuid
                    self.shared_agent_run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
                    print(f"🆔 Using shared agent run ID: {self.shared_agent_run_id}", file=sys.stderr, flush=True)
                
                # Initialize tool with shared agent run ID
                if credentials:
                    instance = tool_class(credentials, agent_run_id=self.shared_agent_run_id)
                else:
                    instance = tool_class(agent_run_id=self.shared_agent_run_id)
                print(f"✅ {tool_class.__name__} instantiated, calling {method_name}", file=sys.stderr, flush=True)
                
                result = getattr(instance, method_name)(**arguments)
                
                if inspect.iscoroutine(result):
                    result = await result
                
                # Special debugging for PDF tools
                if method_name.startswith('pdf_') and hasattr(instance, 'charts_folder'):
                    import os
                    if os.path.exists(instance.charts_folder):
                        chart_files = os.listdir(instance.charts_folder)
                        print(f"🗂️  Charts folder contains: {chart_files}", file=sys.stderr, flush=True)
                    else:
                        print(f"📁 Charts folder does not exist: {instance.charts_folder}", file=sys.stderr, flush=True)
                
                print(f"✅ Tool result: {result}", file=sys.stderr, flush=True)
                return [TextContent(type="text", text=str(result))]
            except Exception as e:
                print(f"❌ Tool execution error: {str(e)}", file=sys.stderr, flush=True)
                import traceback
                traceback.print_exc(file=sys.stderr)
                return [TextContent(type="text", text=f"Error: {str(e)}")]
        return handler
    
    def _get_credentials(self, class_name):
        """Get credentials for tool class from config file"""
        config = self._load_config()
        for tool_name, tool_config in config.get("local", {}).items():
            if tool_name.lower() in class_name.lower():
                credentials = tool_config.get("credentials")
                if credentials:
                    # Substitute environment variables
                    processed_creds = {}
                    for key, value in credentials.items():
                        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                            env_var = value[2:-1]  # Remove ${ and }
                            processed_creds[key] = os.environ.get(env_var, value)
                        else:
                            processed_creds[key] = value
                    return processed_creds
                return None
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

    def _make_function_handler(self, func):
        """Create handler for standalone function"""
        async def handler(arguments: Dict[str, Any]):
            try:
                result = func(**arguments)
                
                if inspect.iscoroutine(result):
                    result = await result
                
                return [TextContent(type="text", text=str(result))]
            except Exception as e:
                return [TextContent(type="text", text=f"Error: {str(e)}")]
        return handler

async def main():
    """Run the MCP server"""
    server = UniversalToolServer()
    await server.initialize()
    async with stdio_server() as (read_stream, write_stream):
        await server.server.run(read_stream, write_stream, server.server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main()) 