import sys
import os
import asyncio
# Add the project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from Global.Collector.connectors import load_connectors
from Prompts.collector.prompt import collector_prompt, feedback_prompt
from Global.llm import LLM
from pydantic import BaseModel, Field

class connectorResponse(BaseModel):
        """Always use this tool to structure your response to the user."""
        connectors: list = Field(description="The formatted list of connectors")

class feedbackResponse(BaseModel):
        """Always use this tool to structure your response to the user."""
        feedback: list = Field(description="The formatted list of feedback")

class Collector:
    def __init__(self, agent_description: str):
        self.agent_description = agent_description

    async def collect(self, agent_description: str):
        """Connect to the universal MCP server and get all tools"""
        print("Connecting to universal MCP server...")
        llm = LLM()
        all_connectors = load_connectors()    
        connector_info = "\n\nAvailable Connectors:\n" + "="*50 + "\n"
        for connector, description in all_connectors.items():
            connector_info += f"{connector}: {description}\n"
        
        prompt = collector_prompt + connector_info
        prompt += "\n\n" + "User Agent Description: " + agent_description
        conectors = llm.formatted(prompt, connectorResponse)
        return conectors
    
    async def feedback(self, agent_description: str, connectors: list):
        llm = LLM()
        formatted_connectors = "\n".join([
            f"- {connector['name']}: {connector['justification']}"
            for connector in connectors
        ])
        prompt = feedback_prompt + '\n\n' + 'User Agent Description: ' + agent_description + '\n\n' + 'Connectors:\n' + formatted_connectors
        prompt += "\n\n" + "User Agent Description: " + agent_description
        feedback = llm.formatted(prompt, feedbackResponse)
        for question in feedback.feedback:
            print(question)
            print("-"*50)
        return feedback

         
if __name__ == "__main__":
    agent_description = "I want an agent that takes emails from the emailtork file in our sharepoint and sends cold emails to the people in the file about a new product we are launching."
    collector = Collector(agent_description)
    connectors_response = asyncio.run(collector.collect(agent_description))
    # Extract the actual connectors list from the response object
    connectors = connectors_response.connectors
    print("Extracted connectors:", connectors)
    feedback = asyncio.run(collector.feedback(agent_description, connectors))
    # result = asyncio.run(router("I want an agent that takes emails from the emailtork file in our sharepoint and sends cold emails to the people in the file about a new product we are launching."))