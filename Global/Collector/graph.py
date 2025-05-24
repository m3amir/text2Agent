from Global.llm import LLM
from Prompts.collector.prompt import template
from pydantic import BaseModel, Field
from Global.Collector.connectors import connectors

user = "I want an agent that takes emails from the emailtork file in our sharepoint and sends cold emails to the people in the file about a new product we are launching."

def router():
    class connectorResponse(BaseModel):
        """Always use this tool to structure your response to the user."""
        connectors: list = Field(description="The formatted list of connectors")
    required_connectors = {}
    llm = LLM()
    prompt = template + "\n\n" + "\n".join([f"{connector}: {connectors[connector]}" for connector in connectors])
    prompt += "\n\n" + "User Agent Description: " + user
    response = llm.formatted(prompt, connectorResponse)
    for connector in response.connectors:
        required_connectors[connector['name']] = connector['justification']
    return required_connectors

print(router())