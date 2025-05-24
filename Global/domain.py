import sys
import os
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import json
# from Global.States.state import Domain
from Global.llm import LLM
from Prompts.Domain import prompt as domain_prompt
from langgraph.graph import END, StateGraph
from langchain_core.tools import StructuredTool
import os
import importlib
from Global.Judge.judge import Judge
from pydantic import BaseModel, Field
from utils.messages import messages_to_string
class ResponseFormatter(BaseModel):
    """Always use this tool to structure your response to the user."""
    Route: str = Field(description="The formatted response of the connector route")
    Category: str = Field(description="The formatted response of the connector category")

class Domain:

    def __init__(self, MCP_tools=None):
        self.dir = './Tools/'
        self.connectors = []
        self.connectors = [
            d for d in os.listdir(self.dir)
            if os.path.isdir(os.path.join(self.dir, d)) and not d.startswith('__')]
        self.connector_descriptions = {}
        self.connector_descriptions = {
            k: v for k, v in self.get_variable_from_tool('description').items() if k != 'Analyst'
        }
        self.connector_descriptions.update(MCP_tools)
        self.connector_descriptions = "\n\n".join(f"{k}: {v}" for k, v in self.connector_descriptions.items())
        self.model = LLM(
                profile_name="prof",
                model_kwargs={"temperature": 0.1, "max_tokens": 4096, "top_p": 0.3},
            ).get_model().bind_tools([ResponseFormatter])
        self.judge = Judge()

    async def route(self, state, task, prompt_type):
        print("state", state)
        print(state['messages'][-1])
        if prompt_type == 'history':
            prompt = domain_prompt.system_marketing_history
        elif prompt_type == 'current':
            prompt = domain_prompt.system_marketing_current
        elif prompt_type == 'comparable':
            prompt = domain_prompt.system_marketing_comparable
        else:
            prompt = domain_prompt.system

        try:
            summary = messages_to_string(state['messages'])
            
            reflection = await self.judge.judge(summary, self.connector_descriptions)
            messages = [
                ("system", prompt),
                (
                    "human",
                    domain_prompt.user.format(previous_steps=summary, routes=self.connector_descriptions, task=task, current_best_course_of_action=reflection.content)
                ),
            ]
            response = self.model.invoke(messages)
            return response
        except Exception as e:
            print("Encountered error in Domain.route: ", e)
    
    def extract_json(self, response):
        json_start = response.content.find("```json") + len("```json")
        json_end = response.content.rfind("```")
        if json_start != -1 and json_end != -1 and json_end > json_start:
            json_string = response.content[json_start:json_end].strip()
            try:
                return json.loads(json_string)
            except json.JSONDecodeError:
                print("Encountered JSON error in extract_json: ", e)
                return None
        return None

    def get_variable_from_tool(self, variable_name):
        values = {}
        try:
            for folder in self.connectors:
                tool_path = os.path.join(self.dir, folder, 'tool.py')
                if os.path.exists(tool_path):
                    # Add the tool's directory to sys.path temporarily
                    tool_dir = os.path.dirname(tool_path)
                    sys.path.insert(0, os.path.dirname(os.path.dirname(tool_dir)))
                    
                    try:
                        spec = importlib.util.spec_from_file_location(
                            f'Tools.{folder}.tool',
                            tool_path
                        )
                        tool_module = importlib.util.module_from_spec(spec)
                        sys.modules[spec.name] = tool_module
                        spec.loader.exec_module(tool_module)
                        # Get the variable if it exists in the module
                        if hasattr(tool_module, variable_name):
                            values[folder] = getattr(tool_module, variable_name)
                    except Exception as e:
                        print(f"Error loading tool {folder}: {str(e)}")
                    finally:
                        # Remove the temporarily added path
                        if sys.path[0] == os.path.dirname(os.path.dirname(tool_dir)):
                            sys.path.pop(0)
        except Exception as e:
            print(f"Error in get_variable_from_tool: {str(e)}")
        return values


# d = domain()
# d.route({'messages': ['I have saved the files in the directory and it appears the task has been completed.']})