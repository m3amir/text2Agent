import sys
import os
import asyncio
# Add the project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from Global.Collector.connectors import load_connectors
from Global.llm import LLM
from pydantic import BaseModel, Field
from langgraph.graph import END, StateGraph
from typing import TypedDict, List
from langgraph.types import interrupt, Command
from langgraph.constants import START
from langgraph.checkpoint.memory import MemorySaver
from Prompts.promptwarehouse import PromptWarehouse
from Prompts.collector.prompt import tools_prompt
import uuid

# Import MCP tools function for direct access
try:
    import importlib.util
    converter_path = os.path.join(os.path.dirname(__file__), '..', '..', 'MCP', 'langchain_converter.py')
    spec = importlib.util.spec_from_file_location("langchain_converter", converter_path)
    langchain_converter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(langchain_converter)
    get_mcp_tools_with_session = langchain_converter.get_mcp_tools_with_session
except Exception as e:
    print(f"Failed to import MCP tools: {e}")
    get_mcp_tools_with_session = None

class connectorResponse(BaseModel):
    """Always use this tool to structure your response to the user."""
    connectors: list = Field(description="The formatted list of connectors")

class feedbackResponse(BaseModel):
    """Always use this tool to structure your response to the user."""
    feedback: list = Field(description="The formatted list of feedback")

class toolsResponse(BaseModel):
    """Always use this tool to structure your response to the user."""
    tools: dict = Field(description="Dictionary with connector names as keys and lists of selected tool names as values, e.g. {'connector1': ['tool1', 'tool2'], 'connector2': ['tool3']}")

class State(TypedDict):
    input: str
    connectors: List[str]
    feedback_questions: List[str]
    answered_questions: List[str]
    reviewed: bool
    connector_tools: dict

class Collector:
    def __init__(self, agent_description: str):
        self.agent_description = agent_description
        self.warehouse = PromptWarehouse('m3')
        self.connectors = load_connectors()

    def human_approval(self, state: State):
        if state['answered_questions']:
            return state
        answered_questions = interrupt({"questions": state["feedback_questions"]})
        if isinstance(answered_questions, dict) and "questions" in answered_questions:
            actual_answers = answered_questions["questions"]
            non_empty_answers = [ans for ans in actual_answers.values() if ans and str(ans).strip()]
            if len(non_empty_answers) >= 3:
                state['answered_questions'].append(actual_answers)
        return state
            
    def format_connectors(self, connector_tools):
        formatted_tools = ""
        for connector_name, tools in connector_tools.items():
            formatted_tools += f"\n🔌 {connector_name.upper()} CONNECTOR ({len(tools)} tools):\n"
            
            for tool_name, tool_info in tools.items():
                description = tool_info['description']
                if len(description) > 100:
                    description = description[:97] + "..."
                formatted_tools += f"  • {tool_name}: {description}\n"
                
                if tool_info.get('argument_schema') and tool_info['argument_schema'].get('properties'):
                    args_schema = tool_info['argument_schema']
                    formatted_tools += f"\n    Args:\n"
                    for arg_name, arg_info in args_schema['properties'].items():
                        arg_type = arg_info.get('type', 'unknown')
                        arg_desc = arg_info.get('description', 'No description')
                        required = '(required)' if arg_name in args_schema.get('required', []) else '(optional)'
                        formatted_tools += f"      {arg_name} ({arg_type}) {required}: {arg_desc}\n"
                    formatted_tools += "\n"
            formatted_tools += "\n"
        return formatted_tools
            
    def init_agent(self) -> StateGraph:
        workflow = StateGraph(State)
        workflow.add_node("collect", self.collect)
        workflow.add_node("feedback", self.feedback)
        workflow.add_node("human_approval", self.human_approval)
        workflow.add_node("validate_connectors", self.validate_connectors)
        
        workflow.add_edge(START, "collect")
        workflow.add_edge("collect", "feedback")
        workflow.add_edge("feedback", "human_approval")
        
        workflow.add_conditional_edges(
            "human_approval",
            lambda state: "validate_connectors" if state['reviewed'] else "collect",
            {"collect": "collect", "validate_connectors": "validate_connectors"}
        )
        workflow.add_edge("validate_connectors", END)
        return workflow.compile(checkpointer=MemorySaver())

    def validate_connectors(self, state: State) -> State:        
        valid_connectors = []
        seen_connectors = set()
        llm = LLM()
        
        for connector in state['connectors']:
            connector_name = connector['name'] if isinstance(connector, dict) and 'name' in connector else str(connector)
            connector_name = connector_name.split('(')[0].strip()
            
            if connector_name not in seen_connectors and connector_name in self.connectors:
                valid_connectors.append(connector_name)
                seen_connectors.add(connector_name)
        
        state['connectors'] = valid_connectors
        state['connector_tools'] = self.load_connector_tools(valid_connectors)
        tools = self.format_tools(state['connector_tools'])
        prompt = self.warehouse.get_prompt('tools') + "\n\n" + "User Agent Description: " + state['input'] + "\n\n" + "Available Tools: " + tools
        print("prompt", prompt)
        chosen_tools = llm.formatted(prompt, toolsResponse)
        print("chosen_tools", chosen_tools)
        return state

    def load_connector_tools(self, valid_connectors):
        import sys
        import os
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
        from Global.Collector.connectors import get_multiple_connector_tools_sync
        
        # Use batch loading to avoid multiple MCP session initializations
        try:
            all_tools_data = get_multiple_connector_tools_sync(valid_connectors)
            connector_tools = {}
            
            for connector_name in valid_connectors:
                tools_data = all_tools_data.get(connector_name, {})
                if tools_data and tools_data.get('tool_count', 0) > 0:
                    # Convert the tool format to the expected format
                    formatted_tools = {}
                    for tool_name, tool_info in tools_data.get('tool_schemas', {}).items():
                        formatted_tools[tool_name] = {
                            'description': tool_info.get('description', 'No description available'),
                            'argument_schema': tool_info.get('args_schema', None)
                        }
                    connector_tools[connector_name] = formatted_tools
                else:
                    # Add placeholder if no tools found
                    connector_tools[connector_name] = {
                        f"{connector_name}_placeholder": {
                            'description': f"Tools from {connector_name} connector",
                            'argument_schema': None
                        }
                    }
            
            return connector_tools
            
        except Exception as e:
            print(f"Error loading tools in batch: {e}")
            # Fallback to individual loading if batch fails
            from Global.Collector.connectors import get_connector_tools_sync
            connector_tools = {}
            
            for connector_name in valid_connectors:
                try:
                    tools_data = get_connector_tools_sync(connector_name)
                    if tools_data and tools_data.get('tool_count', 0) > 0:
                        formatted_tools = {}
                        for tool_name, tool_info in tools_data.get('tool_schemas', {}).items():
                            formatted_tools[tool_name] = {
                                'description': tool_info.get('description', 'No description available'),
                                'argument_schema': tool_info.get('args_schema', None)
                            }
                        connector_tools[connector_name] = formatted_tools
                    else:
                        connector_tools[connector_name] = {
                            f"{connector_name}_placeholder": {
                                'description': f"Tools from {connector_name} connector",
                                'argument_schema': None
                            }
                        }
                except Exception as e:
                    print(f"Error loading tools for {connector_name}: {e}")
                    connector_tools[connector_name] = {
                        f"{connector_name}_placeholder": {
                            'description': f"Tools from {connector_name} connector (error: {str(e)})",
                            'argument_schema': None
                        }
                    }
            
            return connector_tools
    
    async def collect(self, state):
        llm = LLM()
        connector_info = "\n\nAvailable Connectors:\n" + "="*50 + "\n"
        for connector, description in self.connectors.items():
            connector_info += f"{connector}: {description}\n"

        prompt = self.warehouse.get_prompt('collector') + connector_info + f"\n\nUser Agent Description: {state['input']}"
        
        if state['answered_questions']:
            prompt += "\n\nAdditional Context from User Answers:\n" + "="*40 + "\n"
            latest_qa = state['answered_questions'][-1]
            state['reviewed'] = True
            for question, answer in latest_qa.items():
                prompt += f"Q: {question}\nA: {answer}\n\n"
        
        connectors = llm.formatted(prompt, connectorResponse)
        state['connectors'] = connectors.connectors
        return state
    
    async def feedback(self, state):
        if state['answered_questions'] or state['feedback_questions']:
            return state
        
        valid_connectors = [
            connector for item in state['connectors']
            for connector in ([item] if not isinstance(item, list) else item)
            if isinstance(connector, dict) and 'name' in connector and 'justification' in connector
        ]
        
        formatted_connectors = "\n".join([f"- {c['name']}: {c['justification']}" for c in valid_connectors])
        
        prompt = (self.warehouse.get_prompt('feedback') + '\n\n' + 
                 'User Agent Description: ' + state['input'] + '\n\n' + 
                 'Connectors:\n' + formatted_connectors)
        
        llm = LLM()
        feedback = llm.formatted(prompt, feedbackResponse)
        state['feedback_questions'] = feedback.feedback
        return state

    def format_tools(self, connector_tools):
        """Format connector tools into a clear string for LLM understanding"""
        if not connector_tools:
            return "No tools available."
        
        formatted = "Available Tools:\n"
        
        for connector_name, tools in connector_tools.items():
            formatted += f"\n{connector_name.upper()}:\n"
            
            for tool_name, tool_info in tools.items():
                # Skip if tool_info is None
                if not tool_info:
                    continue
                    
                desc = tool_info['description'][:100] + "..." if len(tool_info['description']) > 100 else tool_info['description']
                formatted += f"• {tool_name}: {desc}\n"
                
                if tool_info.get('argument_schema') and tool_info['argument_schema'].get('properties'):
                    args = tool_info['argument_schema']
                    for arg_name, arg_info in args['properties'].items():
                        req = "●" if arg_name in args.get('required', []) else "○"
                        formatted += f"  {req} {arg_name} ({arg_info.get('type', 'any')}): {arg_info.get('description', 'No desc')}\n"
                formatted += "\n"
        
        return formatted + "● Required, ○ Optional"

if __name__ == "__main__":
    agent_description = "I want an agent that takes emails from a file in our document storage and sends cold emails to the people in the file about a new product we are launching."
    collector = Collector(agent_description)
    graph = collector.init_agent()
    config = {"configurable": {"thread_id": uuid.uuid4()}}
    result = asyncio.run(graph.ainvoke({"input": agent_description, "connectors": [], "feedback_questions": [], "answered_questions": [], "reviewed": False, "connector_tools": {}}, config=config))
    
    if '__interrupt__' in result and result['__interrupt__']:
        questions = result['__interrupt__'][0].value['questions']
        response = {}
        
        print("\n" + "="*60)
        print("📋 FEEDBACK QUESTIONS - Please provide your answers:")
        print("="*60)
        
        for i, question in enumerate(questions, 1):
            print(f"\n🔸 Question {i}: {question}")
            print("-" * 50)
            while True:
                answer = input("Your answer: ").strip()
                if answer:
                    response[question] = answer
                    break
                print("⚠️  Please provide a non-empty answer.")
        
        print("\n✅ All questions answered! Processing your responses...")
        connectors = asyncio.run(graph.ainvoke(Command(resume={"questions": response}), config=config))['connectors']
    else:
        print("No interrupt occurred - process completed without feedback questions.")