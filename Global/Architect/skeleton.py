import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from langgraph.graph import END, StateGraph, MessagesState, START
from utils.core import setup_logging, sync_logs_to_s3
from Logs.log_manager import LogManager

# Import MCP tool functionality
try:
    from MCP.langchain_converter import get_specific_tool, convert_mcp_to_langchain
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

class Skeleton:
    def __init__(self, user_email: str = ""):
        self.log_manager = LogManager(user_email)
        self.user_email = user_email
        self.logger = setup_logging(user_email, 'AI_Skeleton', self.log_manager)
        self.workflow = StateGraph(MessagesState)
        self.available_tools = {}

    async def load_tools(self, tool_names=None):
        """Load tools from MCP by name or load all available tools."""
        if not MCP_AVAILABLE:
            self.logger.warning("MCP not available, using placeholder tools")
            return
        
        try:
            if tool_names:
                # Load specific tools by name
                for tool_name in tool_names:
                    tool = await get_specific_tool(tool_name)
                    if tool:
                        self.available_tools[tool_name] = tool
                        self.logger.info(f"Loaded tool: {tool_name}")
                    else:
                        self.logger.warning(f"Tool not found: {tool_name}")
            else:
                # Load all available tools
                all_tools = await convert_mcp_to_langchain()
                for tool in all_tools:
                    tool_name = getattr(tool, 'name', getattr(tool, '_name', str(tool)))
                    self.available_tools[tool_name] = tool
                    self.logger.info(f"Loaded tool: {tool_name}")
                
            self.logger.info(f"Total tools loaded: {len(self.available_tools)}")
            
        except Exception as e:
            self.logger.error(f"Error loading tools: {str(e)}")

    def create_skeleton(self, task: str, blueprint: dict):
        """Create a skeleton workflow from a blueprint with optional tool assignments."""
        self.logger.info(f"Creating skeleton for task: {task}")
        
        # Get node tools from blueprint
        node_tools = blueprint.get("node_tools", {})
        
        # Add nodes (handle duplicates)
        added_nodes = set()
        for node in blueprint["nodes"]:
            if node not in added_nodes:
                # Determine tools for this node
                tools_for_node = None
                if node_tools and node in node_tools:
                    tools_for_node = node_tools[node]
                
                self.workflow.add_node(node, self._create_node_function(node, tools_for_node))
                added_nodes.add(node)
        
        # Add START edge to first node
        if blueprint["nodes"]:
            first_node = blueprint["nodes"][0]
            self.workflow.add_edge(START, first_node)
        
        # Add edges from blueprint
        for edge in blueprint["edges"]:
            from_node, to_node = edge
            self.workflow.add_edge(from_node, to_node)
        
        # Add END edges for terminal nodes
        nodes_with_outgoing = {edge[0] for edge in blueprint["edges"]}
        terminal_nodes = set(blueprint["nodes"]) - nodes_with_outgoing
        for terminal_node in terminal_nodes:
            self.workflow.add_edge(terminal_node, END)
        
        # Push logs to S3
        sync_logs_to_s3(self.user_email)
        return self.workflow
    
    def compile_graph(self):
        """Compile the workflow into an executable graph."""
        return self.workflow.compile()
    
    def _create_node_function(self, node_name: str, tool_names=None):
        """Create a function for each node with optional tool integration."""
        def node_function(state):
            # If tools are specified for this node, use them
            if tool_names and self.available_tools:
                available_node_tools = []
                for tool_name in tool_names:
                    if tool_name in self.available_tools:
                        available_node_tools.append(self.available_tools[tool_name])
                
                # Add tool information to state
                if hasattr(state, 'get') and 'tools' not in state:
                    state['tools'] = available_node_tools
                elif hasattr(state, 'tools'):
                    state.tools = available_node_tools
            
            return state
        return node_function

    def get_available_tools(self):
        """Get list of available tool names."""
        return list(self.available_tools.keys())

# Example usage
async def main():
    blueprint = {
        "nodes": ['STR', 'Colleagues', 'Orchestration', 'Execution', 'Review', 'Feedback', 'Summary'],
        "edges": [
            ('STR', 'Colleagues'),
            ('Colleagues', 'Orchestration'),
            ('Orchestration', 'Execution'),
            ('Execution', 'Review'),
            ('Review', 'Feedback'),
            ('Feedback', 'Summary'),
            ('Summary', 'Feedback'),
        ],
        "node_tools": {
            'STR': ['search', 'analyze'],
            'Execution': ['microsoft_calendar_create_event', 'microsoft_sharepoint_search_files'],
            'Review': ['code_analyzer', 'quality_checker']
        }
    }
    
    skeleton = Skeleton(user_email="amir@m3labs.co.uk")
    await skeleton.load_tools(['microsoft_calendar_create_event', 'microsoft_sharepoint_search_files'])
    skeleton.create_skeleton("build rest api to retrieve customer data", blueprint)
    compiled_graph = skeleton.compile_graph()
    print(f"✅ Graph created successfully")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())