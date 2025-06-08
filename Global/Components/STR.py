import logging
import boto3
import json
from typing import Optional, Dict, Any
import sys
import os
import time
import random

# Add the Prompts directory to the path to import PromptWarehouse
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'Prompts'))
from promptwarehouse import PromptWarehouse

class STR:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(logging.StreamHandler())
        self.logger.addHandler(logging.FileHandler('STR.log'))
        self.logger.info("STR initialized")
        
        # Initialize Bedrock Agent Runtime client with session
        self.session = boto3.Session(profile_name='m3', region_name='eu-west-2')
        
        # Create client with minimal retry config to see what's happening
        from botocore.config import Config
        config = Config(
            retries={'max_attempts': 1, 'mode': 'standard'}
        )
        self.bedrock_agent_client = self.session.client('bedrock-agent-runtime', config=config)
        
        # Initialize Prompt Warehouse
        self.prompt_warehouse = PromptWarehouse('m3')
        
        # Knowledge base configuration
        self.knowledge_base_id = "G6KEPIWDE2"
        self.model_arn = "anthropic.claude-3-sonnet-20240229-v1:0"  # Default model
        
        # Load prompts from warehouse
        self._load_prompts_from_warehouse()

    def _load_prompts_from_warehouse(self):
        """Load orchestration and generation prompts from the prompt warehouse"""
        try:
            self.logger.info("🏪 Loading prompts from warehouse...")
            
            # Get orchestrator prompt
            self.orchestration_prompt = self.prompt_warehouse.get_prompt('orchestrator')
            if self.orchestration_prompt:
                self.logger.info("✅ Orchestrator prompt loaded from warehouse")
            else:
                raise ValueError("Orchestrator prompt 'orchestrator' not found in warehouse")
            
            # Get generation prompt
            self.generation_prompt = self.prompt_warehouse.get_prompt('generation')
            if self.generation_prompt:
                self.logger.info("✅ Generation prompt loaded from warehouse")
            else:
                raise ValueError("Generation prompt 'generation' not found in warehouse")
                
        except Exception as e:
            self.logger.error(f"❌ Failed to load prompts from warehouse: {e}")
            raise RuntimeError(f"STR initialization failed - required prompts not available: {e}")

    def query_knowledge_base(self, query: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Query the knowledge base and return SimilarTasks list"""
        try:
            # Prepare the request
            request_params = {
                'input': {'text': query},
                'retrieveAndGenerateConfiguration': {
                    'type': 'KNOWLEDGE_BASE',
                    'knowledgeBaseConfiguration': {
                        'knowledgeBaseId': self.knowledge_base_id,
                        'modelArn': self.model_arn,
                        'orchestrationConfiguration': {
                            'promptTemplate': {
                                'textPromptTemplate': self.orchestration_prompt
                            }
                        },
                        'generationConfiguration': {
                            'promptTemplate': {
                                'textPromptTemplate': self.generation_prompt
                            }
                        }
                    }
                }
            }
            
            if session_id:
                request_params['sessionId'] = session_id
            
            # Call Bedrock
            response = self.bedrock_agent_client.retrieve_and_generate(**request_params)
            raw_answer = response.get('output', {}).get('text', '')
            
            # Parse JSON and extract SimilarTasks
            parsed_json = json.loads(raw_answer)
            similar_tasks = parsed_json.get('SimilarTasks', [])
            
            return {
                'SimilarTasks': similar_tasks,
                'session_id': response.get('sessionId', ''),
                'success': True
            }
            
        except json.JSONDecodeError:
            return {
                'SimilarTasks': [],
                'session_id': session_id or '',
                'success': False,
                'error': 'Could not parse response as JSON'
            }
        except Exception as e:
            return {
                'SimilarTasks': [],
                'session_id': session_id or '',
                'success': False,
                'error': str(e)
            }



if __name__ == "__main__":
    print("🧪 Testing STR with Orchestration Configuration...")
    
    try:
        str_component = STR()
                
        # Test the knowledge base query which now includes orchestration configuration
        result = str_component.query_knowledge_base("build rest api to retrueve customer data from mysql instance erret123")
        print(result)
        if result['success']:
            print(f"✅ Success! Found {len(result['SimilarTasks'])} similar tasks")
            print(f"📊 SimilarTasks: {result['SimilarTasks']}")
        else:
            print(f"❌ Error: {result.get('error', 'Unknown error')}")
            
        print(f"🔗 Session ID: {result['session_id']}")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        