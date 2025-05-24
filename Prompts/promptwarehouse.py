import boto3
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Prompts.master_prompts import *

class PromptWarehouse:
    def __init__(self, profile_name):
        self.session = boto3.Session(profile_name=profile_name, region_name='eu-west-2')
        self.client = self.session.client("bedrock-agent", region_name='eu-west-2')

    def create_prompt(self, name: str, description: str, prompt: str, input_vars: list=[]):
        response = self.client.create_prompt(
            name=name,
            description=description,
            defaultVariant=name,
            variants=[{
                "name": name,
                "templateConfiguration": {
                    "text": {
                        "inputVariables": [{"name": var} for var in input_vars],
                        "text": prompt,
                    }
                },
                "templateType": "TEXT",
            }]
        )
        version = self.client.create_prompt_version(promptIdentifier=response['id'])
        return version

    def list_prompts(self):
        response = self.client.list_prompts(maxResults=100)
        prompts_dict = {}
        for prompt in response["promptSummaries"]:
            prompts_dict[prompt['name']] = {
                'id': prompt['id'],
                'description': prompt['description'],
                'last_updated': prompt['updatedAt'].strftime('%Y-%m-%d %H:%M:%S'),
                'arn': prompt['arn']
            }
        return prompts_dict
    
    def get_prompt_versions(self, prompt_id: str):
        response = self.client.list_prompts(promptIdentifier=prompt_id)
        
        # Check if 'promptSummaries' exists in the response and is a list
        if 'promptSummaries' in response and isinstance(response['promptSummaries'], list):
            versions_dict = {}
            
            # Iterate through the list of prompt summaries and clean up the data
            for prompt in response['promptSummaries']:
                version = prompt.get('version')
                if version:
                    # Store version info (arn, createdAt, etc.) in a dictionary
                    versions_dict[version] = {
                        'arn': prompt.get('arn'),
                        'createdAt': prompt.get('createdAt'),
                        'updatedAt': prompt.get('updatedAt'),
                        'description': prompt.get('description'),
                        'id': prompt.get('id'),
                        'name': prompt.get('name')
                    }
            return versions_dict
        else:
            print("No prompt versions found.")
            return {}

    def get_prompt(self, prompt_id: str):
        prompt_id = self.get_prompt_id('colleagueJudgeSystem')
        prompts = self.get_prompt_versions(prompt_id)
        
        # Filter out non-numeric keys and convert valid ones to integers
        numeric_keys = [key for key in prompts.keys() if key.isdigit()]
        
        if numeric_keys:  # Check if we have valid numeric keys
            latest_version = max(map(int, numeric_keys))
            prompt = self.client.get_prompt(promptIdentifier=prompt_id, promptVersion=str(latest_version))
            return prompt['variants'][0]['templateConfiguration']['text']['text']
        else:
            print("No numeric versions found.")

    def get_prompt_id(self, prompt_name):
        response = self.client.list_prompts(
            maxResults=100)
        for prompt in response["promptSummaries"]:
            if prompt["name"] == prompt_name:
                return prompt["id"]
        return None