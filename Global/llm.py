from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from dotenv import load_dotenv
from langchain_aws import ChatBedrock

load_dotenv()

MAX_RETRIES = 5

class LLM:
    def __init__(self, profile_name = 'm3', model_kwargs=None, provider='bedrock'):
        # Default model kwargs
        default_model_kwargs = {
            'temperature': 0.5,
            'max_tokens': 4096,
            'top_p': 0.1,
        }
        
        # Initialize ChatOpenAI with the updated model_kwargs
        if provider == 'bedrock':
            # Set up AWS session with proper region and profile
            self.model = ChatBedrock(
                credentials_profile_name=profile_name,
                model_id="us.amazon.nova-pro-v1:0",
                region_name="us-east-1",  # Use the configured region
                temperature=default_model_kwargs['temperature'],
                max_tokens=default_model_kwargs['max_tokens'],
            )
        else:
            self.model = ChatOpenAI(
                model_name="gpt-4o",
                default_headers={
                    "Connection": "close",
                },
                **default_model_kwargs
            )

    def get_model(self):
        return self.model
    
    def formatted(self, input: str, format: BaseModel):
        for attempt in range(MAX_RETRIES + 1):
            model = self.model.bind_tools([format])
            unparsed = model.invoke(input)
            
            # Check if we have tool calls (successful tool use)
            if unparsed.tool_calls:
                parsed = format.model_validate(unparsed.tool_calls[0]["args"])
                return parsed
            
            # If this is the last attempt, break out of the loop
            if attempt == MAX_RETRIES:
                break
        
        # If we've exhausted all retries and still no tool calls, raise an error
        raise Exception(f"Failed to get proper tool call response after {MAX_RETRIES + 1} attempts. Last content: {unparsed.content}")

    async def ainvoke(self, messages):
        return await self.model.ainvoke(messages)