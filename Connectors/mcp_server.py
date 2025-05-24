import os
import sys
import json
import asyncio
import importlib.util
import inspect
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
import logging

# Add parent directory to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "")))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    # Try to import MCP server components
    from mcp.server import Server
    from mcp.server.models import InitializationOptions
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    MCP_AVAILABLE = True
except ImportError:
    logger.warning("MCP library not available. Please install with: pip install mcp")
    MCP_AVAILABLE = False

@dataclass
class ConnectorInfo:
    """Information about a loaded connector"""
    name: str
    class_obj: type
    module: Any
    filename: str
    instance: Any = None
    initialized: bool = False

class ConnectorMCPServer:
    """
    A dynamic MCP server that loads and serves tools from custom connectors
    in the Connectors folder.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        if not MCP_AVAILABLE:
            raise ImportError("MCP library not available. Please install with: pip install mcp")
            
        self.server = Server("connector-mcp-server")
        self.connectors: Dict[str, ConnectorInfo] = {}
        self.tools: List[Tool] = []
        self.tool_handlers: Dict[str, Callable] = {}
        
        self.config_path = config_path or os.path.join(os.path.dirname(__file__), "..", "config.json")
        self.credentials = self._load_credentials()
        
        # Auto-discover and load connectors
        self._discover_connectors()
        
        # Register server handlers
        self._register_handlers()
    
    def _load_credentials(self) -> Dict[str, Any]:
        """Load credentials from configuration file"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            else:
                logger.warning(f"Config file not found at {self.config_path}")
                return {}
        except Exception as e:
            logger.error(f"Error loading credentials: {e}")
            return {}
    
    def _discover_connectors(self):
        """Automatically discover connector classes in the Connectors folder"""
        connectors_dir = os.path.dirname(__file__)
        
        # Define the connector files and their expected class names
        connector_mappings = {
            'jira.py': 'Jira',
            'slack.py': 'Slack', 
            'salesforce.py': 'SF',
            'zendesk.py': 'Zendesk',
            'sharepoint.py': 'SharePoint',
            'trello_.py': 'Trello',
            'tasks.py': 'Tasks',
            'sqlite.py': 'SQLite',
            '_postgres.py': 'PostgresConnector'
        }
        
        for filename, class_name in connector_mappings.items():
            filepath = os.path.join(connectors_dir, filename)
            if os.path.exists(filepath):
                try:
                    self._load_connector(filename, class_name)
                except Exception as e:
                    logger.error(f"Failed to load connector {filename}: {e}")
    
    def _load_connector(self, filename: str, class_name: str):
        """Load a specific connector class"""
        try:
            # Import the module
            module_name = filename.replace('.py', '')
            spec = importlib.util.spec_from_file_location(
                module_name, 
                os.path.join(os.path.dirname(__file__), filename)
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Get the connector class
            connector_class = getattr(module, class_name)
            
            # Store connector info
            connector_info = ConnectorInfo(
                name=module_name,
                class_obj=connector_class,
                module=module,
                filename=filename
            )
            
            self.connectors[module_name] = connector_info
            
            # Pre-register tools for this connector (without initializing)
            self._pre_register_tools(module_name, connector_class)
            
            logger.info(f"Successfully loaded connector: {class_name} from {filename}")
            
        except Exception as e:
            logger.error(f"Error loading connector {filename}: {e}")
            raise
    
    def _pre_register_tools(self, connector_name: str, connector_class: type):
        """Pre-register tools from a connector class without initializing"""
        try:
            # Get all methods from the connector class
            methods = inspect.getmembers(connector_class, predicate=inspect.isfunction)
            
            for method_name, method in methods:
                # Skip private methods and special methods
                if method_name.startswith('_'):
                    continue
                
                # Create tool definition
                tool_name = f"{connector_name}_{method_name}"
                
                # Get method signature for parameters
                sig = inspect.signature(method)
                parameters = {}
                required_params = []
                
                for param_name, param in sig.parameters.items():
                    if param_name == 'self':
                        continue
                    
                    param_type = "string"  # Default type
                    if param.annotation != inspect.Parameter.empty:
                        if param.annotation == int:
                            param_type = "integer"
                        elif param.annotation == bool:
                            param_type = "boolean"
                        elif param.annotation == list:
                            param_type = "array"
                    
                    parameters[param_name] = {
                        "type": param_type,
                        "description": f"Parameter {param_name} for {method_name}"
                    }
                    
                    # Check if parameter is required
                    if param.default == inspect.Parameter.empty:
                        required_params.append(param_name)
                
                # Create the tool
                tool = Tool(
                    name=tool_name,
                    description=f"{connector_name} connector: {method_name}",
                    inputSchema={
                        "type": "object",
                        "properties": parameters,
                        "required": required_params
                    }
                )
                
                self.tools.append(tool)
                
                # Create a handler for this tool
                self.tool_handlers[tool_name] = self._create_tool_handler(connector_name, method_name)
                
                logger.info(f"Pre-registered tool: {tool_name}")
                
        except Exception as e:
            logger.error(f"Error pre-registering tools for {connector_name}: {e}")
    
    def _create_tool_handler(self, connector_name: str, method_name: str):
        """Create a handler function for a specific tool"""
        async def handler(arguments: Dict[str, Any]) -> List[TextContent]:
            try:
                # Initialize connector if not already done
                if not self.connectors[connector_name].initialized:
                    await self._initialize_connector(connector_name)
                
                # Get the connector instance
                instance = self.connectors[connector_name].instance
                
                # Get the method
                if not hasattr(instance, method_name):
                    raise ValueError(f"Method {method_name} not found in connector {connector_name}")
                
                method = getattr(instance, method_name)
                
                # Call the method
                if asyncio.iscoroutinefunction(method):
                    result = await method(**arguments)
                else:
                    result = method(**arguments)
                
                # Format the result
                if isinstance(result, (dict, list)):
                    result_text = json.dumps(result, indent=2)
                else:
                    result_text = str(result)
                
                return [TextContent(type="text", text=result_text)]
                
            except Exception as e:
                error_msg = f"Error executing {connector_name}.{method_name}: {str(e)}"
                logger.error(error_msg)
                return [TextContent(type="text", text=error_msg)]
        
        return handler
    
    async def _initialize_connector(self, connector_name: str):
        """Initialize a connector instance with credentials"""
        if connector_name not in self.connectors:
            raise ValueError(f"Connector {connector_name} not found")
        
        connector_info = self.connectors[connector_name]
        if connector_info.initialized:
            return connector_info.instance
        
        try:
            # Get credentials for this connector
            connector_creds = self.credentials.get(f"{connector_name}_creds", {})
            if not connector_creds:
                raise ValueError(f"No credentials found for connector: {connector_name}")
            
            # Initialize the connector
            instance = connector_info.class_obj(connector_creds)
            connector_info.instance = instance
            connector_info.initialized = True
            
            logger.info(f"Initialized connector: {connector_name}")
            return instance
            
        except Exception as e:
            logger.error(f"Error initializing connector {connector_name}: {e}")
            raise
    
    def _register_handlers(self):
        """Register MCP server handlers"""
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """List all available tools from connectors"""
            return self.tools
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool execution"""
            if name in self.tool_handlers:
                return await self.tool_handlers[name](arguments)
            else:
                error_msg = f"Tool {name} not found"
                logger.error(error_msg)
                return [TextContent(type="text", text=error_msg)]
    
    def add_connector(self, name: str, connector_class, credentials: Dict[str, Any]):
        """Manually add a connector"""
        connector_info = ConnectorInfo(
            name=name,
            class_obj=connector_class,
            module=None,
            filename='manual'
        )
        
        self.connectors[name] = connector_info
        
        # Store credentials
        self.credentials[f"{name}_creds"] = credentials
        
        # Pre-register tools
        self._pre_register_tools(name, connector_class)
    
    def remove_connector(self, name: str):
        """Remove a connector"""
        if name in self.connectors:
            del self.connectors[name]
        
        # Remove tools and handlers associated with this connector
        self.tools = [tool for tool in self.tools if not tool.name.startswith(f"{name}_")]
        self.tool_handlers = {k: v for k, v in self.tool_handlers.items() if not k.startswith(f"{name}_")}
    
    def list_connectors(self) -> List[str]:
        """List all available connectors"""
        return list(self.connectors.keys())
    
    def list_active_connectors(self) -> List[str]:
        """List all initialized connectors"""
        return [name for name, info in self.connectors.items() if info.initialized]
    
    async def run(self):
        """Run the MCP server"""
        logger.info("Starting Connector MCP Server...")
        logger.info(f"Available connectors: {self.list_connectors()}")
        logger.info(f"Total tools registered: {len(self.tools)}")
        
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream, 
                write_stream, 
                InitializationOptions(
                    server_name="connector-mcp-server",
                    server_version="1.0.0",
                    capabilities=self.server.get_capabilities()
                )
            )

# Example usage and main function
async def main():
    """Main function to run the server"""
    try:
        server = ConnectorMCPServer()
        await server.run()
    except ImportError as e:
        print(f"Error: {e}")
        print("Please install the MCP library: pip install mcp")
    except Exception as e:
        logger.error(f"Server error: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 

