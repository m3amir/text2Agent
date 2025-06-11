import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import asyncio
from datetime import datetime
from typing import Dict, List, Any, TypedDict
from typing_extensions import Annotated
import operator

from langgraph.graph import END, StateGraph, START
from langgraph.graph.message import add_messages
from Logs.log_manager import LogManager
from Global.Components.colleagues import Colleague
from Global.llm import LLM
from utils.core import setup_logging, sync_logs_to_s3

# Workflow state - using only built-in reducers
class WorkflowState(TypedDict, total=False):
    messages: Annotated[List[Any], add_messages]
    executed_tools: Annotated[List[str], operator.add]
    tool_execution_results: Annotated[List[Dict[str, Any]], operator.add]
    colleagues_analysis: str
    colleagues_score: int
    status: str
    task: str
    route: str
    current_node: Annotated[List[str], operator.add]
    current_node_tools: Annotated[List[str], operator.add]

# MCP tool loading
try:
    from MCP.langchain_converter import get_mcp_tools_with_session
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

class Skeleton:
    def __init__(self, user_email: str = ""):
        self.log_manager = LogManager(user_email)
        self.user_email = user_email
        self.logger = setup_logging(user_email, 'AI_Skeleton', self.log_manager)
        self.workflow = StateGraph(WorkflowState)
        self.available_tools = {}
        self._session_context = None

    async def load_tools(self, tool_names: List[str]):
        """Load MCP tools by name"""
        if not MCP_AVAILABLE:
            return
        
        self._session_context = get_mcp_tools_with_session()
        all_tools = await self._session_context.__aenter__()
        
        for tool_name in tool_names:
            for tool in all_tools:
                if (hasattr(tool, 'name') and tool.name == tool_name) or \
                   (hasattr(tool, '_name') and tool._name == tool_name):
                    self.available_tools[tool_name] = tool
                    break

    async def cleanup_tools(self):
        """Clean up MCP session"""
        if self._session_context:
            try:
                await self._session_context.__aexit__(None, None, None)
            except Exception:
                pass
            finally:
                self._session_context = None

    def colleagues_node(self, state):
        """AI colleagues analysis of tool results"""
        tool_results = state.get('tool_execution_results', [])
        
        if not tool_results:
            return {
                'colleagues_analysis': "No tool results to analyze",
                'colleagues_score': 0
            }
        
        # Build analysis text only for the latest result
        latest_result = tool_results[-1]  # Get the most recent tool execution
        tool_name = latest_result.get('tool', 'Unknown')
        tool_args = latest_result.get('args', {})
        tool_result = str(latest_result.get('result', ''))[:300]  # Truncate
        
        analysis_text = f"Tool Execution Analysis:\n--- {tool_name} ---\nArgs: {tool_args}\nResult: {tool_result}..."
        
        try:
            colleague = Colleague(user_email=self.user_email, log_manager=self.log_manager)
            analysis_result = colleague.update_message([analysis_text])
            
            score = 0
            if hasattr(colleague, 'reviews') and colleague.reviews:
                score = colleague.reviews[-1].get('score', 0)
            
            return {
                'colleagues_analysis': analysis_result,
                'colleagues_score': score
            }
            
        except Exception as e:
            return {
                'colleagues_analysis': f"Analysis failed: {str(e)}",
                'colleagues_score': 0
            }

    def colleagues_router_logic(self, state):
        """Conditional routing logic after colleagues analysis"""
        executed_tools = state.get('executed_tools', [])
        colleagues_score = state.get('colleagues_score', 0)
        current_node_tools = state.get('current_node_tools', [])
        current_node = state.get('current_node', [])
        current_node_name = current_node[-1] if current_node else ''
        
        print(f"🔀 Colleagues Router: Current node: {current_node_name}")
        print(f"🔀 Colleagues Router: Executed tools: {executed_tools}")
        print(f"🔀 Colleagues Router: Available tools in node: {current_node_tools}")
        print(f"🔀 Colleagues Router: Score: {colleagues_score}/10")
        
        # Check if there are more tools to execute in current node
        remaining_tools = [tool for tool in current_node_tools if tool not in executed_tools]
        
        # Routing decisions based on colleagues analysis
        if colleagues_score < 7:  # Low score - retry previous tool
            route = 'retry_previous'
            print(f"🔀 Router: Low score ({colleagues_score}/10) - retrying previous tool")
        elif remaining_tools:  # More tools to execute in current node
            route = 'retry_previous'  # Go back to same node to execute next tool
            print(f"🔀 Router: More tools to execute ({remaining_tools}) - continuing in current node")
        elif len(executed_tools) >= 2:  # All tools executed - proceed
            route = 'next_step'
            print(f"🔀 Router: All tools executed - proceeding to next step")
        else:  # Single tool executed with good score - proceed
            route = 'next_step'
            print(f"🔀 Router: Good score ({colleagues_score}/10) - proceeding to next step")
        
        return route

    def tool_node(self, tool_names: List[str], node_name: str = ""):
        """Tool execution node"""
        async def node_function(state):
            if 'executed_tools' not in state:
                state['executed_tools'] = []
            
            # Return new state values instead of modifying in place
            new_state = {
                'current_node_tools': tool_names,
                'current_node': [node_name]
            }
            
            # Get next unexecuted tool from this node
            executed_tools = state.get('executed_tools', [])
            tool_name = None
            for name in tool_names:
                if name in self.available_tools and name not in executed_tools:
                    tool_name = name
                    break
            
            print(f"🔧 Tool node ({node_name}): Available tools: {tool_names}")
            print(f"🔧 Tool node ({node_name}): Already executed: {executed_tools}")
            print(f"🔧 Tool node ({node_name}): Selected tool: {tool_name}")
            
            if not tool_name:
                print("❌ No unexecuted tools found!")
                return new_state
            
            # Execute tool with LLM
            llm = LLM()
            tool = self.available_tools[tool_name]
            bound_model = llm.get_model().bind_tools([tool])
            print(f"🔧 Toollllllllllllllllll: {tool}")
            
            # Better prompt to encourage tool usage with context from previous tool results
            task = state.get('task', 'complete the requested task')
            
            # Include previous tool results as context
            tool_results = state.get('tool_execution_results', [])
            context = ""
            if tool_results:
                context = "\n\nPrevious tool results for context:\n"
                for result in tool_results[-3:]:  # Show last 3 results
                    context += f"- {result.get('tool', 'Unknown')} tool returned: {str(result.get('result', ''))[:500]}...\n"
            
            prompt = f"You must use the {tool_name} tool to help progress the below task\n\nTask: {task} You have the following information from the previous tool results: {context}\n\n."
            print(f"🔧 Prompt: {prompt}")
            try:
                print(f"🔧 Invoking LLM with tool: {tool_name}")
                response = bound_model.invoke(prompt)
                print(f"🔧 LLM response type: {type(response)}")
                print(f"🔧 Has tool_calls: {hasattr(response, 'tool_calls')}")
                
                if hasattr(response, 'tool_calls') and response.tool_calls:
                    print(f"🔧 Tool calls found: {len(response.tool_calls)}")
                    tool_call = response.tool_calls[0]
                    tool_args = tool_call.get('args', {})
                    print(f"🔧 Tool args: {tool_args}")
                    
                    # Execute tool
                    tool_result = await self._execute_tool(tool_name, tool_args)
                    print(f"🔧 Tool result: {tool_result}")
                    
                    # Add results to new_state (will be merged by reducer)
                    new_state['tool_execution_results'] = [{
                        'tool': tool_name,
                        'args': tool_args,
                        'result': tool_result
                    }]
                    
                    # Add to executed tools (will be merged by reducer)
                    new_state['executed_tools'] = [tool_name]
                    print(f"🔧 Added {tool_name} to executed tools")
                else:
                    print("❌ No tool calls in LLM response")
                    print(f"🔧 Response content: {response}")
            
            except Exception as e:
                print(f"❌ Tool execution failed: {e}")
                new_state['tool_execution_results'] = [{
                    'tool': tool_name,
                    'error': str(e)
                }]
                new_state['executed_tools'] = [tool_name]
            
            return new_state
        
        return node_function

    async def _execute_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> Any:
        """Execute tool safely"""
        try:
            tool = self.available_tools[tool_name]
            if hasattr(tool, 'ainvoke'):
                return await tool.ainvoke(tool_args)
            else:
                return tool.invoke(tool_args)
        except Exception as e:
            return f"Error: {str(e)}"

    def finish_node(self, state):
        """Completion node"""
        state['status'] = 'completed'
        return state



    def _resolve_navigation_keywords(self, blueprint: Dict[str, Any]):
        """Resolve navigation keywords like NEXT, PREVIOUS, etc."""
        nodes = blueprint['nodes']
        edges = blueprint['edges']
        conditional_edges = blueprint.get('conditional_edges', {})
        
        # Build node sequence map from edges
        next_node_map = {}
        previous_node_map = {}
        
        for from_node, to_node in edges:
            next_node_map[from_node] = to_node
            previous_node_map[to_node] = from_node
        
        # Resolve keywords in conditional edges
        resolved_conditional_edges = {}
        for from_node, route_map in conditional_edges.items():
            resolved_route_map = {}
            for route_key, target_node in route_map.items():
                if target_node == 'NEXT':
                    # Find the next node after from_node
                    resolved_target = next_node_map.get(from_node, 'finish')
                elif target_node == 'PREVIOUS':
                    # Find the previous node before from_node
                    resolved_target = previous_node_map.get(from_node, nodes[0])
                elif target_node == 'END':
                    resolved_target = END
                elif target_node == 'FINISH':
                    resolved_target = 'finish'
                else:
                    # Use as-is (explicit node name)
                    resolved_target = target_node
                
                resolved_route_map[route_key] = resolved_target
                print(f"🔗 Resolved: {from_node}.{route_key} -> {target_node} becomes -> {resolved_target}")
            
            resolved_conditional_edges[from_node] = resolved_route_map
        
        return resolved_conditional_edges

    def create_skeleton(self, task: str, blueprint: Dict[str, Any]):
        """Build the workflow graph from blueprint"""
        nodes = blueprint['nodes']
        edges = blueprint['edges']  
        node_tools = blueprint.get('node_tools', {})
        
        # Resolve navigation keywords in conditional edges
        conditional_edges = self._resolve_navigation_keywords(blueprint)
        
        # Add nodes
        for node in nodes:
            if node.lower() == 'colleagues':
                self.workflow.add_node(node, self.colleagues_node)
            elif node.lower() == 'finish':
                self.workflow.add_node(node, self.finish_node)
            elif node in node_tools:
                # Node with specific tools
                self.workflow.add_node(node, self.tool_node(node_tools[node], node))
            else:
                # Default node (pass-through)
                self.workflow.add_node(node, lambda state: state)
        
        # Add regular edges
        if nodes:
            self.workflow.add_edge(START, nodes[0])
        
        for from_node, to_node in edges:
            self.workflow.add_edge(from_node, to_node)
        
        # Add conditional edges (especially for Colleagues routing)
        for from_node, route_map in conditional_edges.items():
            if from_node.lower() == 'colleagues':
                # Use colleagues-specific routing logic
                self.workflow.add_conditional_edges(from_node, self.colleagues_router_logic, route_map)
            else:
                # Generic conditional edge (if needed later)
                self.workflow.add_conditional_edges(from_node, lambda state: state.get('route', 'default'), route_map)
        
        # Add END edges for terminal nodes (nodes with no outgoing edges and no conditional edges)
        terminal_nodes = set(nodes) - {edge[0] for edge in edges} - set(conditional_edges.keys())
        for terminal in terminal_nodes:
            self.workflow.add_edge(terminal, END)
        
        sync_logs_to_s3(self.logger, self.log_manager)
        return self.workflow
    
    def compile_and_visualize(self, task_name: str = "workflow"):
        """Compile and create PNG"""
        compiled_graph = self.workflow.compile()
        
        # Create PNG
        os.makedirs('graph_images', exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        png_file = f"graph_images/{task_name}_{timestamp}.png"
        
        try:
            png_data = compiled_graph.get_graph().draw_mermaid_png()
            with open(png_file, 'wb') as f:
                f.write(png_data)
            return compiled_graph, [png_file]
        except Exception:
            return compiled_graph, []

async def run_skeleton(user_email: str, blueprint: Dict[str, Any], task_name: str = "workflow"):
    """Execute skeleton with blueprint"""
    skeleton = Skeleton(user_email=user_email)
    
    # Extract all tools from node_tools
    node_tools = blueprint.get('node_tools', {})
    all_tools = []
    for tools in node_tools.values():
        all_tools.extend(tools)
    
    try:
        await skeleton.load_tools(all_tools)
        skeleton.create_skeleton(task_name, blueprint)
        compiled_graph, viz_files = skeleton.compile_and_visualize(task_name)
        
        result = await compiled_graph.ainvoke({"messages": ["search for excel leads spreadsheet and send email to amir in the leads saying hello"], "task": task_name})
        return result, viz_files
        
    except Exception as e:
        print(f"Error: {e}")
        return None, []
    finally:
        await skeleton.cleanup_tools()



# if __name__ == "__main__":
#     # Skeleton is meant to be used as a library
#     # Example usage:
#     # from Global.Architect.skeleton import run_skeleton, create_default_config
#     # result, viz_files = await run_skeleton(user_email="...", tool_names=["..."])
    
#     print("Skeleton module loaded. Import and call run_skeleton() to use.")
#     print("Example:")
#     print("  from Global.Architect.skeleton import run_skeleton")
#     print("  result, viz = await run_skeleton(user_email='...', tool_names=['...'])")