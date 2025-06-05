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
        
        # Merge with provided model_kwargs if any
        if model_kwargs:
            default_model_kwargs.update(model_kwargs)
        
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
        import json
        import re
        
        for attempt in range(MAX_RETRIES + 1):
            model = self.model.bind_tools([format])
            unparsed = model.invoke(input)
            
            # Check if we have tool calls (successful tool use)
            if unparsed.tool_calls:
                parsed = format.model_validate(unparsed.tool_calls[0]["args"])
                return parsed
            
            # If no tool calls, try to extract JSON from the content
            if unparsed.content:
                try:
                    # Remove thinking tags and other markdown/XML tags
                    cleaned_content = re.sub(r'<thinking>.*?</thinking>', '', unparsed.content, flags=re.DOTALL)
                    cleaned_content = re.sub(r'```(?:json)?\s*', '', cleaned_content)
                    cleaned_content = re.sub(r'```\s*$', '', cleaned_content)
                    cleaned_content = cleaned_content.strip()
                    
                    # Try to find JSON in the content
                    json_match = re.search(r'\{.*\}', cleaned_content, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(0)
                        parsed_json = json.loads(json_str)
                        parsed = format.model_validate(parsed_json)
                        return parsed
                except (json.JSONDecodeError, ValueError, Exception):
                    # If JSON parsing fails, continue to next attempt
                    pass
            
            # If this is the last attempt, break out of the loop
            if attempt == MAX_RETRIES:
                break
        
        # If we've exhausted all retries and still no tool calls, raise an error
        raise Exception(f"Failed to get proper tool call response after {MAX_RETRIES + 1} attempts. Last content: {unparsed.content}")

    async def ainvoke(self, messages):
        return await self.model.ainvoke(messages)