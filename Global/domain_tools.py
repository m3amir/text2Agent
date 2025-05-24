import sys
import os
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import json
from Global.llm import LLM
from Prompts.Tools import prompt as tools_prompt
import os
import importlib
from langchain_core.messages import HumanMessage
from langchain_core.messages import AIMessage
from Global.Judge.judge import Judge
from pydantic import BaseModel, Field
from utils.messages import messages_to_string

class ResponseFormatter(BaseModel):
    """Always use this tool to structure your response to the user."""
    Route: str = Field(description="The formatted response of the connector route")
    Category: str = Field(description="The formatted response of the connector category")


class toolMapper:

    def __init__(self, tools):
        self.dir = './Tools/'
        self.model = LLM(
                profile_name="prof",
                model_kwargs={"temperature": 0.1, "max_tokens": 4096, "top_p": 0.2},
            ).get_model()
        self.tools = tools
        self.judge = Judge()

    def extract_json(self, response):        
        # Check if response or response.content is None or empty
        if not response or not hasattr(response, 'content') or not response.content:
            print("Empty or invalid response content")
            return None
            
        content = response.content.strip()
        
        # If content is empty after stripping, return None
        if not content:
            print("Empty content after stripping")
            return None
        
        # Check if the content contains code block delimiters
        json_start = content.find("```json")
        json_end = content.rfind("```")

        if json_start != -1 and json_end != -1 and json_end > json_start:
            json_string = content[json_start + len("```json"):json_end].strip()
        else:
            # If no code block found, try to parse the entire response
            json_string = content
        
        try:
            return json.loads(json_string)
        except json.JSONDecodeError:
            print("Failed to parse JSON from content")
            return None

    async def route(self, state, task, current=None):
        try:
            if current == 'history':
                prompt = tools_prompt.system_marketing_history
            elif current == 'current':
                prompt = tools_prompt.system_marketing_current
            elif current == 'comparable':
                prompt = tools_prompt.system_marketing_comparable
            else:
                prompt = tools_prompt.system
            last_message = state['messages'][-1]
            if not last_message.content and last_message.tool_calls:
                response = ResponseFormatter.model_validate(last_message.tool_calls[0]["args"])
                connector = response.Route.lower()
                category = response.Category.lower()
            else:
                last_message = self.extract_json(last_message)
                category = last_message['Category'].lower()
                connector = last_message['Route'].lower()

            if connector in self.tools:
                tools = self.tools[connector][category]
                tools_list = [x[1] for x in tools if x[0]]
                self.model = self.model.bind_tools(tools_list, tool_choice='any')
                tool_descriptions = []
                for tool in tools_list:
                    tool_descriptions.append(tool.name + ': ' + tool.description + '\n\n')
                
                formatted_descriptions = "\n".join(y for x in tool_descriptions for y in x.split("\n"))
                summary = messages_to_string(state['messages'])
                    
                reflection = await self.judge.judge(summary, formatted_descriptions)
                response = self.model.invoke(prompt + '\n\n' +
                    tools_prompt.user.format(
                        previous_steps=summary,
                        available_tools=tool_descriptions,
                        task=task,
                        current_best_course_of_action=reflection.content))
            else:
                return HumanMessage(content="There is no tools for this connector. I need to try to use another connector and tool category")
            
            return response
        
        except Exception as e:
            print("Encountered error in route: ", e)
            return None

    def get_variable_from_tool(self, variable_name):
        values = {}
        try:
            for folder in self.connectors:
                tool_path = os.path.join(self.dir, folder, 'tool.py')
                if os.path.exists(tool_path):
                    spec = importlib.util.spec_from_file_location('tool', tool_path)
                    tool_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(tool_module)
                    if hasattr(tool_module, variable_name):
                        if getattr(tool_module, variable_name):
                            values[folder] = getattr(tool_module, variable_name)
                    else:
                        print(f"Variable '{variable_name}' not found in {tool_path}")
                else:
                    print(f"File not found: {tool_path}")
            return values
        except Exception as e:
            print("Encountered error in domain: ", e)