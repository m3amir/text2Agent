#!/usr/bin/env python3
"""
Universal Tool MCP Server
Serves tools from local tool.py files and remote MCP servers
"""

import os, sys, json, asyncio, importlib.util, inspect, argparse, glob
from typing import Dict, Any, List, Optional, Callable
import logging

logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

try:
    from mcp.server import Server, NotificationOptions
    from mcp.server.models import InitializationOptions
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    MCP_AVAILABLE = True
except ImportError:
    logger.error("MCP library not available. Install with: pip install mcp")
    MCP_AVAILABLE = False

class UniversalMCPServer:
    def __init__(self, tools_dir: str = "Tools", config_file: str = "mcp_servers_config.json"):
        if not MCP_AVAILABLE:
            raise ImportError("MCP library not available")
            
        self.tools_dir = os.path.abspath(tools_dir)
        self.config_file = config_file
        self.server = Server("universal-tool-server")
        self.tools: List[Tool] = []
        self.tool_handlers: Dict[str, Callable] = {}
        self.tool_instances: Dict[str, Any] = {}
        self.remote_servers: Dict[str, Dict] = {}
        self.credentials = self._load_json("config.json")
        
        self._load_remote_server_config()
        self._discover_and_load_local_tools()
        self._register_handlers()
    
    def _load_json(self, filename: str) -> Dict[str, Any]:
        """Load JSON file with error handling"""
        try:
            if os.path.exists(filename):
                with open(filename, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load {filename}: {e}")
        return {}
    
    def _load_remote_server_config(self):
        """Load remote MCP server configurations"""
        config = self._load_json(self.config_file)
        self.remote_servers = config.get("mcpServers", {})
    
    def _discover_and_load_local_tools(self):
        """Discover and load local tools"""
        tool_files = glob.glob(os.path.join(self.tools_dir, "*/tool.py"))
        
        for tool_file in tool_files:
            try:
                self._load_local_tool_file(tool_file)
            except Exception as e:
                logger.error(f"Failed to load {tool_file}: {e}")
    
    async def _load_remote_tools(self):
        """Load tools from remote MCP servers"""
        for server_name, server_config in self.remote_servers.items():
            try:
                await self._load_remote_server_tools(server_name, server_config)
            except Exception as e:
                logger.error(f"Failed to load remote server {server_name}: {e}")
    
    async def _load_remote_server_tools(self, server_name: str, server_config: Dict):
        """Load tools from a single remote MCP server"""
        command = server_config.get("command")
        args = server_config.get("args", [])
        
        # Get custom prefix or use server name
        custom_prefix = server_config.get("prefix", server_name)
        server_description = server_config.get("description", server_name)
        
        server_params = StdioServerParameters(command=command, args=args)
        
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools_result = await session.list_tools()
                remote_tools = tools_result.tools
                
                for tool in remote_tools:
                    # Get naming configuration
                    custom_prefix = server_config.get("prefix", server_name)
                    no_prefix = server_config.get("no_prefix", False)
                    
                    # Determine final tool name
                    if no_prefix:
                        final_name = tool.name
                    else:
                        final_name = f"{custom_prefix}_{tool.name}"
                    
                    prefixed_tool = Tool(
                        name=final_name,
                        description=f"[{server_description}] {tool.description}",
                        inputSchema=tool.inputSchema
                    )
                    self.tools.append(prefixed_tool)
                    self.tool_handlers[final_name] = self._create_remote_handler(
                        server_name, server_config, tool.name
                    )
    
    def _create_remote_handler(self, server_name: str, server_config: Dict, original_tool_name: str):
        """Create handler for remote tool"""
        async def handler(arguments: Dict[str, Any]) -> List[TextContent]:
            try:
                command = server_config.get("command")
                args = server_config.get("args", [])
                server_params = StdioServerParameters(command=command, args=args)
                
                async with stdio_client(server_params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        result = await session.call_tool(original_tool_name, arguments)
                        return result if isinstance(result, list) else [TextContent(type="text", text=str(result))]
            except Exception as e:
                error_msg = f"Error calling remote tool {server_name}.{original_tool_name}: {str(e)}"
                logger.error(error_msg)
                return [TextContent(type="text", text=error_msg)]
        return handler
    
    def _load_local_tool_file(self, tool_file_path: str):
        """Load a single local tool file"""
        connector_name = os.path.basename(os.path.dirname(tool_file_path)).lower()
        
        # Import module
        spec = importlib.util.spec_from_file_location(f"{connector_name}_tool", tool_file_path)
        module = importlib.util.module_from_spec(spec)
        
        tool_dir = os.path.dirname(tool_file_path)
        if tool_dir not in sys.path:
            sys.path.insert(0, tool_dir)
        
        try:
            spec.loader.exec_module(module)
        finally:
            if tool_dir in sys.path:
                sys.path.remove(tool_dir)
        
        # Find toolkit class
        toolkit_class = None
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if obj.__module__ == module.__name__ and not name.startswith('_'):
                toolkit_class = obj
                break
        
        if not toolkit_class:
            return
        
        # Initialize toolkit
        try:
            creds = self.credentials.get(f"{connector_name}_creds", self.credentials)
            tool_instance = toolkit_class(creds)
        except:
            try:
                tool_instance = toolkit_class()
            except Exception as e:
                logger.error(f"Failed to initialize {connector_name} toolkit: {e}")
                return
        
        self.tool_instances[connector_name] = tool_instance
        self._register_local_toolkit_tools(toolkit_class, tool_instance, connector_name)
    
    def _register_local_toolkit_tools(self, toolkit_class, tool_instance, connector_name):
        """Register all tools from a local toolkit"""
        tool_prefix = f"{connector_name}_"
        
        for method_name, method in inspect.getmembers(toolkit_class, inspect.isfunction):
            if not method_name.startswith(tool_prefix):
                continue
            
            # Get method signature
            sig = inspect.signature(method)
            parameters = {}
            required_params = []
            
            for param_name, param in sig.parameters.items():
                if param_name not in ['self', 'cls']:
                    parameters[param_name] = {"type": "string", "description": f"Parameter {param_name}"}
                    if param.default == inspect.Parameter.empty:
                        required_params.append(param_name)
            
            tool = Tool(
                name=method_name,
                description=f"[Local] {inspect.getdoc(method) or f'Execute {method_name}'}",
                inputSchema={
                    "type": "object",
                    "properties": parameters,
                    "required": required_params
                }
            )
            
            self.tools.append(tool)
            self.tool_handlers[method_name] = self._create_local_handler(method_name, tool_instance)
    
    def _create_local_handler(self, method_name: str, tool_instance):
        """Create handler for local tool"""
        async def handler(arguments: Dict[str, Any]) -> List[TextContent]:
            try:
                method = getattr(tool_instance, method_name)
                result = await method(**arguments) if asyncio.iscoroutinefunction(method) else method(**arguments)
                result_text = json.dumps(result, indent=2, default=str) if isinstance(result, (dict, list)) else str(result) if result is not None else "Operation completed"
                return [TextContent(type="text", text=result_text)]
            except Exception as e:
                error_msg = f"Error in {method_name}: {str(e)}"
                logger.error(error_msg)
                return [TextContent(type="text", text=error_msg)]
        return handler
    
    def _register_handlers(self):
        """Register MCP server handlers"""
        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            return self.tools
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            if name in self.tool_handlers:
                return await self.tool_handlers[name](arguments)
            else:
                return [TextContent(type="text", text=f"Tool {name} not found")]
    
    def print_summary(self):
        """Print summary of loaded tools"""
        local_tools = [t for t in self.tools if t.description.startswith("[Local]")]
        remote_tools = [t for t in self.tools if not t.description.startswith("[Local]")]
        
        print(f"\n🛠️  Universal MCP Server")
        print(f"🔧 Total Tools: {len(self.tools)} (Local: {len(local_tools)}, Remote: {len(remote_tools)})")
        print(f"💡 For LangChain conversion: python langchain_converter.py")
        print()
    
    def find_tools(self, search_term: str = "", connector: str = "", server: str = "") -> List[Tool]:
        """Find tools by search term, connector, or server"""
        results = []
        
        for tool in self.tools:
            # Check connector filter (local tools)
            if connector and tool.description.startswith("[Local]"):
                if not tool.name.startswith(f"{connector.lower()}_"):
                    continue
            
            # Check server filter (remote tools)
            if server and not tool.description.startswith("[Local]"):
                if not tool.name.startswith(f"{server.lower()}_"):
                    continue
            
            # Check search term in name or description
            if search_term:
                search_lower = search_term.lower()
                if (search_lower not in tool.name.lower() and 
                    search_lower not in tool.description.lower()):
                    continue
            
            results.append(tool)
        
        return results
    
    async def run(self):
        """Run the MCP server"""
        # Load all tools
        await self._load_remote_tools()
        
        # Print summary
        self.print_summary()
        
        # Start MCP server
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream, 
                write_stream, 
                InitializationOptions(
                    server_name="universal-tool-server",
                    server_version="1.0.0",
                    capabilities=self.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={}
                    )
                )
            )

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Universal Tool MCP Server")
    parser.add_argument("--tools-dir", "-d", default="Tools", help="Local tools directory")
    parser.add_argument("--config", "-c", default="mcp_servers_config.json", help="Remote servers config")
    parser.add_argument("--list", "-l", action="store_true", help="List tools and exit")
    parser.add_argument("--search", "-s", help="Search tools by name or description")
    
    args = parser.parse_args()
    
    try:
        server = UniversalMCPServer(args.tools_dir, args.config)
        
        if args.list or args.search:
            async def list_tools():
                await server._load_remote_tools()
                server.print_summary()
                
                if args.search:
                    results = server.find_tools(search_term=args.search)
                    print(f"🔍 Search results for '{args.search}': {len(results)} tools")
                    for tool in results:
                        print(f"  • {tool.name}")
            
            asyncio.run(list_tools())
        else:
            asyncio.run(server.run())
        
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 