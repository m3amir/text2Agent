import boto3
import os
import importlib.util

class PromptWarehouse:
    def __init__(self, profile_name):
        self.session = boto3.Session(profile_name=profile_name, region_name='eu-west-2')
        self.client = self.session.client("bedrock-agent", region_name='eu-west-2')

    def create_prompt(self, name: str, description: str, prompt: str):
        response = self.client.create_prompt(
            name=name,
            description=description,
            defaultVariant=name,
            variants=[{
                "name": name,
                "templateConfiguration": {
                    "text": {
                        "inputVariables": [],
                        "text": prompt,
                    }
                },
                "templateType": "TEXT",
            }]
        )
        self.client.create_prompt_version(promptIdentifier=response['id'])
        return response['id']

    def sync_prompts_from_files(self):
        """Sync prompts from all prompt.py files in subdirectories"""
        prompts_dir = os.path.dirname(__file__)
        
        for root, dirs, files in os.walk(prompts_dir):
            if root == prompts_dir or 'prompt.py' not in files:
                continue
                
            try:
                # Load the prompt.py file
                spec = importlib.util.spec_from_file_location("prompt_module", os.path.join(root, 'prompt.py'))
                prompt_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(prompt_module)
                
                subdir_name = os.path.basename(root)
                existing_prompts = self._get_existing_prompts()
                
                # Find all variables ending with '_prompt'
                for attr_name in dir(prompt_module):
                    if attr_name.endswith('_prompt') and not attr_name.startswith('_'):
                        prompt_content = getattr(prompt_module, attr_name)
                        
                        if isinstance(prompt_content, str):
                            prompt_name = attr_name[:-7]  # Just the variable name without "_prompt"
                            
                            if prompt_name not in existing_prompts:
                                self.create_prompt(prompt_name, f"Prompt from {subdir_name}/{attr_name}", prompt_content)
                                print(f"✓ Created: {prompt_name}")
                            else:
                                print(f"- Exists: {prompt_name}")
                                
            except Exception as e:
                print(f"✗ Error in {root}: {e}")

    def list_prompts(self):
        """List all prompts in a nice format"""
        response = self.client.list_prompts(maxResults=100)
        prompts = response.get("promptSummaries", [])
        
        if not prompts:
            return "No prompts found."
        
        output = ["=" * 60, f"PROMPT WAREHOUSE ({len(prompts)} prompts)", "=" * 60]
        
        for prompt in prompts:
            output.append(f"📝 {prompt['name']}")
            output.append(f"   {prompt['description']}")
            output.append(f"   Updated: {prompt['updatedAt'].strftime('%Y-%m-%d %H:%M')}")
            output.append(f"   ID: {prompt['id']}")
            output.append("-" * 60)
        
        return "\n".join(output)

    def get_prompt(self, prompt_name):
        """Get the latest version of a prompt by name"""
        try:
            # Find the prompt ID
            response = self.client.list_prompts(maxResults=100)
            prompt_id = None
            for prompt in response.get("promptSummaries", []):
                if prompt['name'] == prompt_name:
                    prompt_id = prompt['id']
                    break
            
            if not prompt_id:
                return None
            
            # Get the prompt content (latest version by default)
            prompt_response = self.client.get_prompt(promptIdentifier=prompt_id)
            return prompt_response['variants'][0]['templateConfiguration']['text']['text']
            
        except Exception as e:
            print(f"Error getting prompt {prompt_name}: {e}")
            return None

    def _get_existing_prompts(self):
        """Get list of existing prompt names"""
        response = self.client.list_prompts(maxResults=100)
        return {prompt['name'] for prompt in response.get("promptSummaries", [])}


# # Run sync
# warehouse = PromptWarehouse('m3')
# results = warehouse.sync_prompts_from_files()
# print(warehouse.list_prompts())

# # # Example: Get a specific prompt
# prompt = warehouse.get_prompt('collector')
# print(prompt)