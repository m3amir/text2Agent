from langchain_openai import ChatOpenAI
import os
import boto3
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

class LLM:
    def __init__(self, profile_name = '', model_kwargs=None):
        # Default model kwargs
        default_model_kwargs = {
            'temperature': 0.5,
            'max_tokens': 4096,
            'top_p': 0.1,
        }

        # Check if OPENAI_API_KEY is set in environment variables
        if "OPENAI_API_KEY" not in os.environ:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        # If model_kwargs is provided, update default_model_kwargs with provided kwargs
        if model_kwargs is not None:
            default_model_kwargs.update(model_kwargs)
        
        # Initialize ChatOpenAI with the updated model_kwargs
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
        max_retries = 3
        
        for attempt in range(max_retries + 1):
            model = self.model.bind_tools([format])
            print(input)
            unparsed = model.invoke(input)
            print(unparsed)
            
            # Check if content is empty and we have tool calls (successful tool use)
            if unparsed.content == "" and unparsed.tool_calls:
                parsed = format.model_validate(unparsed.tool_calls[0]["args"])
                print(parsed)
                return parsed
            
            # If this is the last attempt, break out of the loop
            if attempt == max_retries:
                break
        
        # If we've exhausted all retries, try to parse what we have or raise an error
        if unparsed.tool_calls:
            # Try to parse even if content wasn't empty
            parsed = format.model_validate(unparsed.tool_calls[0]["args"])
            return parsed
        else:
            raise Exception(f"Failed to get proper tool call response after {max_retries + 1} attempts. Last content: {unparsed.content}")

    async def ainvoke(self, messages):
        return await self.model.ainvoke(messages)

# Initialize boto3 session and client
#self.session = boto3.Session(profile_name=profile_name)
#self.client = self.session.client("bedrock-runtime", region_name="us-east-1")

# Initialize ChatBedrock with the updated model_kwargs
# self.bedrock = ChatBedrock(
#     client=self.client,
#     model_id="us.anthropic.claude-3-opus-20240229-v1:0",
#     region_name="eu-west-2",
#     model_kwargs=default_model_kwargs
# )