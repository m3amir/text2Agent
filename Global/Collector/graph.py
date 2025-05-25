import sys
import os
import asyncio

# Add the project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from MCP.langchain_converter import convert_mcp_to_langchain
from Global.Collector.connectors import load_connectors
from Prompts.collector.prompt import collector_prompt, feedback_prompt
from Global.llm import LLM
from pydantic import BaseModel, Field

class connectorResponse(BaseModel):
        """Always use this tool to structure your response to the user."""
        connectors: list = Field(description="The formatted list of connectors")

class Collector:
    def __init__(self, agent_description: str):
        self.agent_description = agent_description

    async def collect(agent_description: str):
        """Connect to the universal MCP server and get all tools"""
        print("Connecting to universal MCP server...")
        llm = LLM()
        # Connect to the universal tool server
        tools = await convert_mcp_to_langchain(
            server_command="python3",
            server_args=[os.path.join(os.path.dirname(__file__), "..", "..", "MCP", "tool_mcp_server.py")]
        )

        # Get all connectors (both local and remote)
        all_connectors = load_connectors()    
        # Create enhanced prompt with connectors
        connector_info = "\n\nAvailable Connectors:\n" + "="*50 + "\n"
        for connector, description in all_connectors.items():
            connector_info += f"{connector}: {description}\n"
        
        prompt = template + connector_info
        prompt += "\n\n" + "User Agent Description: " + agent_description
        conectors = llm.formatted(prompt, connectorResponse)
        print(conectors)
        # Return all available connectors
        return [{"name": connector, "description": description} 
                for connector, description in all_connectors.items()]
    
    async def feedback(agent_description: str, connectors: list):
        llm = LLM()

         
if __name__ == "__main__":
    result = asyncio.run(router("I want an agent that takes emails from the emailtork file in our sharepoint and sends cold emails to the people in the file about a new product we are launching."))