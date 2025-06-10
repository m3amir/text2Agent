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
        self.logger.info("Starting tool loading process...")
        
        if not MCP_AVAILABLE:
            self.logger.warning("MCP not available, using placeholder tools")
            return
        
        try:
            if tool_names:
                self.logger.info(f"Loading {len(tool_names)} specific tools: {tool_names}")
                # Load specific tools by name
                for i, tool_name in enumerate(tool_names, 1):
                    self.logger.debug(f"[{i}/{len(tool_names)}] Requesting tool: {tool_name}")
                    tool = await get_specific_tool(tool_name)
                    if tool:
                        self.available_tools[tool_name] = tool
                        tool_desc = getattr(tool, 'description', 'No description')[:100]
                        self.logger.info(f"[{i}/{len(tool_names)}] Loaded: {tool_name}")
                        self.logger.debug(f"   Description: {tool_desc}...")
                        self.logger.debug(f"   Type: {type(tool).__name__}")
                    else:
                        self.logger.warning(f"[{i}/{len(tool_names)}] Tool not found: {tool_name}")
            else:
                self.logger.info("Loading all available tools from MCP...")
                # Load all available tools
                all_tools = await convert_mcp_to_langchain()
                self.logger.info(f"Received {len(all_tools)} tools from MCP")
                
                for i, tool in enumerate(all_tools, 1):
                    tool_name = getattr(tool, 'name', getattr(tool, '_name', str(tool)))
                    self.available_tools[tool_name] = tool
                    self.logger.debug(f"[{i}/{len(all_tools)}] Loaded: {tool_name}")
                
            self.logger.info(f"Tool loading complete! Total tools loaded: {len(self.available_tools)}")
            if self.available_tools:
                tool_list = ', '.join(self.available_tools.keys())
                self.logger.info(f"Available tools: {tool_list}")
            
        except Exception as e:
            self.logger.error(f"Error loading tools: {str(e)}")
            self.logger.exception("Full error details:")

    def create_skeleton(self, task: str, blueprint: dict):
        """Create a skeleton workflow from a blueprint with optional tool assignments."""
        self.logger.info(f"Creating skeleton workflow for task: '{task}'")
        
        # Get node tools from blueprint
        node_tools = blueprint.get("node_tools", {})
        self.logger.info(f"Blueprint analysis:")
        self.logger.info(f"   Nodes: {len(blueprint['nodes'])} - {blueprint['nodes']}")
        self.logger.info(f"   Edges: {len(blueprint['edges'])} connections")
        if node_tools:
            self.logger.info(f"   Tool assignments: {len(node_tools)} nodes have tools")
            for node, tools in node_tools.items():
                self.logger.debug(f"      {node}: {tools}")
        else:
            self.logger.info(f"   Tool assignments: None")
        
        # Add nodes (handle duplicates)
        self.logger.info("Building workflow nodes...")
        added_nodes = set()
        for i, node in enumerate(blueprint["nodes"], 1):
            if node not in added_nodes:
                # Determine tools for this node
                tools_for_node = None
                if node_tools and node in node_tools:
                    tools_for_node = node_tools[node]
                    self.logger.info(f"   [{i}/{len(blueprint['nodes'])}] Adding node '{node}' with {len(tools_for_node)} tools: {tools_for_node}")
                else:
                    self.logger.info(f"   [{i}/{len(blueprint['nodes'])}] Adding node '{node}' (no tools)")
                
                self.workflow.add_node(node, self._create_node_function(node, tools_for_node))
                added_nodes.add(node)
                self.logger.debug(f"      Node '{node}' successfully added to workflow")
            else:
                self.logger.warning(f"   Skipping duplicate node: '{node}'")
        
        # Add START edge to first node
        self.logger.info("Configuring workflow edges...")
        if blueprint["nodes"]:
            first_node = blueprint["nodes"][0]
            self.workflow.add_edge(START, first_node)
            self.logger.info(f"   Entry point: START → '{first_node}'")
        else:
            self.logger.warning("   No nodes found - cannot create entry point")
        
        # Add edges from blueprint
        self.logger.info(f"   Adding {len(blueprint['edges'])} workflow connections:")
        for i, edge in enumerate(blueprint["edges"], 1):
            from_node, to_node = edge
            self.workflow.add_edge(from_node, to_node)
            self.logger.info(f"      [{i}/{len(blueprint['edges'])}] '{from_node}' → '{to_node}'")
        
        # Add END edges for terminal nodes
        nodes_with_outgoing = {edge[0] for edge in blueprint["edges"]}
        terminal_nodes = set(blueprint["nodes"]) - nodes_with_outgoing
        
        if terminal_nodes:
            self.logger.info(f"   Adding exit points for {len(terminal_nodes)} terminal nodes:")
            for terminal_node in terminal_nodes:
                self.workflow.add_edge(terminal_node, END)
                self.logger.info(f"      '{terminal_node}' → END")
        else:
            self.logger.info("   No terminal nodes found - workflow may be cyclical")
        
        self.logger.info("Workflow structure completed successfully!")
        
        # Summary
        total_edges = len(blueprint["edges"]) + 1 + len(terminal_nodes)  # blueprint edges + START edge + END edges
        self.logger.info(f"Workflow Summary:")
        self.logger.info(f"   Total nodes: {len(added_nodes)}")
        self.logger.info(f"   Total edges: {total_edges}")
        self.logger.info(f"   Nodes with tools: {len(node_tools)}")
        self.logger.info(f"   Total tools available: {len(self.available_tools)}")
        
        # Push logs to S3
        self.logger.info("Syncing logs to S3...")
        sync_logs_to_s3(self.logger, self.log_manager)
        return self.workflow
    
    def compile_graph(self):
        """Compile the workflow into an executable graph."""
        self.logger.info("Compiling workflow into executable graph...")
        
        try:
            compiled_graph = self.workflow.compile()
            self.logger.info("Graph compilation successful!")
            self.logger.debug(f"   Compiled graph type: {type(compiled_graph).__name__}")
            return compiled_graph
        except Exception as e:
            self.logger.error(f"Graph compilation failed: {str(e)}")
            self.logger.exception("Full compilation error details:")
            raise
    
    def _create_node_function(self, node_name: str, tool_names=None):
        """Create a function for each node with optional tool integration."""
        def node_function(state):
            self.logger.debug(f"Executing node: '{node_name}'")
            
            # If tools are specified for this node, use them
            if tool_names and self.available_tools:
                self.logger.debug(f"   Loading {len(tool_names)} tools for node '{node_name}': {tool_names}")
                available_node_tools = []
                
                for tool_name in tool_names:
                    if tool_name in self.available_tools:
                        available_node_tools.append(self.available_tools[tool_name])
                        self.logger.debug(f"      Tool '{tool_name}' available")
                    else:
                        self.logger.warning(f"      Tool '{tool_name}' not found in available tools")
                
                if available_node_tools:
                    self.logger.debug(f"   Node '{node_name}' equipped with {len(available_node_tools)} tools")
                    
                    # Add tool information to state
                    if hasattr(state, 'get') and 'tools' not in state:
                        state['tools'] = available_node_tools
                        self.logger.debug(f"      Added tools to state dict")
                    elif hasattr(state, 'tools'):
                        state.tools = available_node_tools
                        self.logger.debug(f"      Updated state.tools attribute")
                else:
                    self.logger.warning(f"   No tools successfully loaded for node '{node_name}'")
            else:
                if tool_names:
                    self.logger.debug(f"   Tools requested for '{node_name}' but none available: {tool_names}")
                else:
                    self.logger.debug(f"   Node '{node_name}' running without tools")
            
            self.logger.debug(f"   Node '{node_name}' execution completed")
            return state
        return node_function

    def get_available_tools(self):
        """Get list of available tool names."""
        tool_list = list(self.available_tools.keys())
        self.logger.debug(f"Requested available tools list: {len(tool_list)} tools")
        return tool_list

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