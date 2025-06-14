import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from datetime import datetime
from typing import Dict, List, Any, TypedDict
from typing_extensions import Annotated
import operator
from functools import partial
import json
import glob
import uuid

from langgraph.graph import END, StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.types import interrupt
from Logs.log_manager import LogManager
from Global.Components.colleagues import Colleague
from Global.llm import LLM
from utils.core import setup_logging, sync_logs_to_s3
from Prompts.promptwarehouse import PromptWarehouse

THRESHOLD_SCORE = 7

def replace_value(existing, new):
    return new

class WorkflowState(TypedDict, total=False):
    messages: Annotated[List[Any], add_messages]
    executed_tools: Annotated[List[str], operator.add]
    tool_execution_results: Annotated[List[Dict[str, Any]], operator.add]
    colleagues_analysis: str
    colleagues_score: float
    status: str
    task: str
    route: str
    current_node: Annotated[str, replace_value]
    current_node_tools: Annotated[str, replace_value]
    tool_sequence_index: Annotated[int, replace_value]
    approved_tools: Annotated[set, replace_value]

try:
    from MCP.langchain_converter import get_mcp_tools_with_session
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

class Skeleton:
    def __init__(self, user_email: str = "", agent_run_id: str = None):
        self.log_manager = LogManager(user_email)
        self.user_email = user_email
        self.logger = setup_logging(user_email, 'AI_Skeleton', self.log_manager)
        self.workflow = StateGraph(WorkflowState)
        self.available_tools = {}
        self._session_context = None
        self.guarded = {'microsoft_mail_send_email_as_user', 'microsoft_send_email_as_user'}
        self.prompt_warehouse = PromptWarehouse(profile_name='m3')
        
        # Generate agent_run_id if not provided
        if agent_run_id is None:
            agent_run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
        
        self.agent_run_id = agent_run_id

    def _get_generated_charts(self) -> List[str]:
        """Get list of generated chart files from the current agent run directory"""
        charts_base_dir = "tmp/Charts"
        if not os.path.exists(charts_base_dir) or not self.agent_run_id:
            return []
        
        current_run_dir = os.path.join(charts_base_dir, self.agent_run_id)
        if not os.path.exists(current_run_dir):
            return []
        
        # Look for chart files
        chart_patterns = [
            os.path.join(current_run_dir, "*.png"),
            os.path.join(current_run_dir, "*.jpg"),
            os.path.join(current_run_dir, "*.jpeg"),
            os.path.join(current_run_dir, "*.svg")
        ]
        
        chart_files = []
        for pattern in chart_patterns:
            chart_files.extend(glob.glob(pattern))
        
        return [os.path.basename(chart_file) for chart_file in chart_files]

    async def load_tools(self, tool_names: List[str]):
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
        if self._session_context:
            try:
                await self._session_context.__aexit__(None, None, None)
            except Exception:
                pass
            finally:
                self._session_context = None

    def colleagues_node(self, state):
        tool_results = state.get('tool_execution_results', [])
        if not tool_results:
            return {'colleagues_analysis': "No tool results", 'colleagues_score': 0}
        
        latest_result = tool_results[-1]
        analysis_text = f"Tool: {latest_result.get('tool')}\nArgs: {latest_result.get('args')}\nResult: {latest_result.get('result')}"
        
        try:
            colleague = Colleague(user_email=self.user_email, log_manager=self.log_manager)
            analysis_result = colleague.update_message([analysis_text])
            score = colleague.reviews[-1].get('score', 0) if colleague.reviews else 0
            
            return {
                'colleagues_analysis': analysis_result,
                'colleagues_score': score,
                'route': self.colleagues_router_logic({**state, 'colleagues_score': score})
            }
            
        except Exception:
            return {'colleagues_analysis': "Analysis failed", 'colleagues_score': 0, 'route': 'next_step'}

    def colleagues_router_logic(self, state):
        colleagues_score = state.get('colleagues_score', 0)
        tool_sequence_index = state.get('tool_sequence_index', 0)
        
        # Get current tools
        current_node_tools = []
        try:
            current_node_tools = json.loads(state.get('current_node_tools', '[]'))
        except:
            pass
        
        # Emergency stop for loops
        executed_tools = state.get('executed_tools', [])
        if executed_tools and executed_tools.count(executed_tools[-1]) >= 3:
            return 'next_tool' if tool_sequence_index < len(current_node_tools) - 1 else 'next_step'
        
        # Check if we've completed all tools
        if tool_sequence_index >= len(current_node_tools) - 1:
            return 'next_step'
        
        # Check if the next tool has already been executed
        if tool_sequence_index + 1 < len(current_node_tools):
            next_tool_name = current_node_tools[tool_sequence_index + 1]
            if executed_tools and executed_tools.count(next_tool_name) >= 1:
                return 'next_step'
        
        has_next_tool = tool_sequence_index < len(current_node_tools) - 1
        
        if colleagues_score >= THRESHOLD_SCORE:
            return 'next_tool' if has_next_tool else 'next_step'
        else:
            return 'retry_same'

    async def tool_node_execute(self, state, tool_names: List[str], node_name: str = ""):
        new_state = {
            'current_node_tools': json.dumps(tool_names),
            'current_node': node_name
        }
        
        # Determine which tool to execute
        route = state.get('route', '')
        tool_sequence_index = state.get('tool_sequence_index', 0)
        
        if 'tool_sequence_index' not in state:
            new_state['tool_sequence_index'] = 0
            tool_sequence_index = 0
        
        if route == 'next_tool':
            tool_sequence_index += 1
            new_state['tool_sequence_index'] = tool_sequence_index
        
        # Get tool name
        tool_name = tool_names[tool_sequence_index] if tool_sequence_index < len(tool_names) else None
        
        if not tool_name or tool_name not in self.available_tools:
            tool_name = next((name for name in tool_names if name in self.available_tools), None)
        
        if not tool_name:
            return new_state

        # Generate tool arguments
        llm = LLM()
        tool = self.available_tools[tool_name]
        bound_model = llm.get_model().bind_tools([tool])
        
        task = state.get('task', 'complete the task')
        context = self._build_context(state.get('tool_execution_results', []))
        
        # Generate prompt based on tool type
        prompt = self._generate_prompt(tool_name, task, context)
        
        tool_args = {}
        try:
            response = bound_model.invoke(prompt)
            if hasattr(response, 'tool_calls') and response.tool_calls:
                tool_args = response.tool_calls[0].get('args', {})
        except Exception:
            pass

        # Check for interrupt
        if self._should_interrupt(tool_name, tool_args, state):
            return interrupt({
                "message": f"Confirmation required for executing {tool_name}",
                "tool_name": tool_name,
                "tool_args": tool_args,
                "task": task,
                "context": context,
                "tool_execution_key": f"{tool_name}:{hash(str(tool_args))}"
            })
        
        # Execute tool
        try:
            # Inject agent_run_id for chart and PDF tools
            if (tool_name.startswith('chart_') or tool_name.startswith('pdf_')) and tool_args:
                tool_args['agent_run_id'] = self.agent_run_id
            
            tool_result = await self._execute_tool(tool_name, tool_args) if tool_args else "No arguments generated"
            new_state['tool_execution_results'] = [{'tool': tool_name, 'args': tool_args, 'result': tool_result}]
            new_state['executed_tools'] = [tool_name]
        except Exception as e:
            new_state['tool_execution_results'] = [{'tool': tool_name, 'args': tool_args, 'result': f"Error: {str(e)}"}]
            new_state['executed_tools'] = [tool_name]
        
        return new_state

    def _generate_prompt(self, tool_name: str, task: str, context: str) -> str:
        """Generate appropriate prompt based on tool type"""
        if tool_name.startswith('chart_'):
            prompt = self.prompt_warehouse.get_prompt('chart')
            return prompt.format(
                tool_name=tool_name, 
                task=task, 
                context="our rolling 30 day sales is 1000000, our 30 day leads is 100000, our 30 day deals is 100000, our 30 day revenue is 1000000"
            )
        elif tool_name.startswith('pdf_'):
            prompt = self.prompt_warehouse.get_prompt('pdf')
            return prompt.format(tool_name=tool_name, task=task, context=context)
        elif 'report' in tool_name.lower():
            # Get generated charts for report prompts
            generated_charts = self._get_generated_charts()
            charts_info = ""
            if generated_charts:
                charts_info = f"\n\nGenerated charts available for inclusion in the report:\n- " + "\n- ".join(generated_charts)
            
            prompt = self.prompt_warehouse.get_prompt('report')
            return prompt.format(tool_name=tool_name, task=task, context=context, charts_info=charts_info)
        else:
            return f"Use the {tool_name} tool for: {task}{context}\nIMPORTANT: Call the {tool_name} tool with appropriate arguments."

    def _build_context(self, tool_results: List[Dict]) -> str:
        if not tool_results:
            return ""
        context = "\nPrevious results:\n"
        for result in tool_results[-2:]:
            context += f"- {result.get('tool')}: {str(result.get('result', ''))}\n"
        return context

    def _should_interrupt(self, tool_name: str, tool_args: Dict, state: Dict) -> bool:
        if tool_name not in self.guarded:
            return False
        
        approved_tools = state.get('approved_tools', set()) or set()
        tool_execution_key = f"{tool_name}:{hash(str(tool_args))}"
        
        # Check if exact tool execution key is approved
        if tool_execution_key in approved_tools:
            return False
            
        # Check if any approval exists for this tool name
        for approved_key in approved_tools:
            if approved_key.startswith(f"{tool_name}:"):
                return False
        
        return True

    async def _execute_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> Any:
        tool = self.available_tools[tool_name]
        try:
            return await tool.ainvoke(tool_args) if hasattr(tool, 'ainvoke') else tool.invoke(tool_args)
        except Exception as e:
            return f"Error: {str(e)}"

    def finish_node(self, state):
        state['status'] = 'completed'
        return state

    def create_skeleton(self, task: str, blueprint: Dict[str, Any]):
        nodes = blueprint['nodes']
        edges = blueprint['edges']
        node_tools = blueprint.get('node_tools', {})
        conditional_edges = blueprint.get('conditional_edges', {})
        
        # Add nodes
        for node in nodes:
            if node.lower() == 'colleagues':
                self.workflow.add_node(node, self.colleagues_node)
            elif node.lower() == 'finish':
                self.workflow.add_node(node, self.finish_node)
            elif node in node_tools:
                self.workflow.add_node(node, partial(self.tool_node_execute, tool_names=node_tools[node], node_name=node))
            else:
                self.workflow.add_node(node, lambda state: state)
        
        # Add edges
        if nodes:
            self.workflow.add_edge(START, nodes[0])
        
        for from_node, to_node in edges:
            self.workflow.add_edge(from_node, to_node)
        
        # Add conditional edges
        for from_node, route_map in conditional_edges.items():
            if from_node.lower() == 'colleagues':
                self.workflow.add_conditional_edges(from_node, self.colleagues_router_logic, route_map)
            else:
                self.workflow.add_conditional_edges(from_node, lambda state: state.get('route', 'default'), route_map)
        
        # Add END edges for terminal nodes
        terminal_nodes = set(nodes) - {edge[0] for edge in edges} - set(conditional_edges.keys())
        for terminal in terminal_nodes:
            self.workflow.add_edge(terminal, END)
        
        sync_logs_to_s3(self.logger, self.log_manager)
        return self.workflow
    
    def compile_and_visualize(self, task_name: str = "workflow"):
        from langgraph.checkpoint.memory import MemorySaver
        compiled_graph = self.workflow.compile(checkpointer=MemorySaver())
        
        # Create PNG visualization
        os.makedirs('graph_images', exist_ok=True)
        png_file = f"graph_images/{task_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        
        try:
            with open(png_file, 'wb') as f:
                f.write(compiled_graph.get_graph().draw_mermaid_png())
            return compiled_graph, [png_file]
        except Exception:
            return compiled_graph, []

async def run_skeleton(user_email: str, blueprint: Dict[str, Any], task_name: str = "workflow", agent_run_id: str = None):
    # Generate agent_run_id if not provided
    if agent_run_id is None:
        agent_run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
    
    skeleton = Skeleton(user_email=user_email, agent_run_id=agent_run_id)
    
    # Extract and load tools
    all_tools = [tool for tools in blueprint.get('node_tools', {}).values() for tool in tools]
    
    try:
        await skeleton.load_tools(all_tools)
        skeleton.create_skeleton(task_name, blueprint)
        compiled_graph, viz_files = skeleton.compile_and_visualize(task_name)
        
        initial_state = {"messages": ["search for excel leads spreadsheet and send email to amir in the leads saying hello"], "task": task_name}
        config = {"configurable": {"thread_id": "workflow_thread"}}
        result = await compiled_graph.ainvoke(initial_state, config=config)
        
        return result, viz_files, compiled_graph, skeleton
        
    except Exception as e:
        print(f"Error: {e}")
        return None, [], None, None