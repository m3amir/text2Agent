import boto3
import json
import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional
import sys
from pydantic import BaseModel, Field

# Add the Prompts directory to the path to import PromptWarehouse
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from Prompts.promptwarehouse import PromptWarehouse
from Global.llm import LLM
from utils.core import setup_logging, sync_logs_to_s3

# Import LogManager
try:
    from Logs.log_manager import LogManager
except ImportError:
    LogManager = None

class FormatResponse(BaseModel):
    similar_tasks: str = Field(description="The formatted response detailing similar tasks we have previously completed.")

class STR:
    def __init__(self, user_email: str = ""):
        """Initialize STR component"""
        self.user_email = user_email
        self.warehouse = PromptWarehouse('m3')
        
        # Initialize LogManager
        if LogManager is not None:
            try:
                self.log_manager = LogManager(user_email)
            except Exception as e:
                self.log_manager = None
                print(f"⚠️ Could not initialize LogManager: {e}")
        else:
            self.log_manager = None
        
        # Setup logging
        self.logger = setup_logging(user_email, 'STR', self.log_manager)
        
        if self.log_manager:
            self.logger.info("✅ LogManager initialized")
        
        self.logger.info("🔧 Initializing STR...")
        
        # AWS configuration
        self.knowledge_base_id = os.getenv('KNOWLEDGE_BASE_ID', 'G6KEPIWDE2')
        self.model_arn = "anthropic.claude-3-sonnet-20240229-v1:0"
        
        # Initialize Bedrock client
        self.session = boto3.Session(profile_name='m3', region_name='eu-west-2')
        from botocore.config import Config
        config = Config(retries={'max_attempts': 1, 'mode': 'standard'})
        self.bedrock_agent_client = self.session.client('bedrock-agent-runtime', config=config)
        
        # Load prompts from warehouse
        self.logger.info("🏪 Loading prompts from warehouse...")
        self._load_prompts_from_warehouse()
        self.logger.info("✅ STR ready!")

    def _load_prompts_from_warehouse(self):
        """Load orchestrator and generation prompts from warehouse"""
        try:
            warehouse = PromptWarehouse('m3')
            
            # Load orchestrator prompt
            self.orchestration_prompt = warehouse.get_prompt('orchestrator')
            self.logger.info("✅ Orchestrator prompt loaded from warehouse")
            
            # Load generation prompt  
            self.generation_prompt = warehouse.get_prompt('generation')
            self.logger.info("✅ Generation prompt loaded from warehouse")
            
        except Exception as e:
            self.logger.error(f"❌ Error loading prompts: {str(e)}")
            # Fallback to default prompts
            self.orchestration_prompt = "You are an AI assistant that helps optimize search queries."
            self.generation_prompt = "Generate a helpful response based on the retrieved information."

    def query_knowledge_base(self, query: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Query the knowledge base and return SimilarTasks list"""
        self.logger.info(f"🚀 Starting query: {query[:100]}...")
        
        try:
            # Prepare the request
            self.logger.info("📋 Preparing request with orchestration configuration...")
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
                self.logger.info(f"📎 Using session: {session_id}")
            
            # Call Bedrock
            self.logger.info("🤖 Calling Bedrock Agent...")
            response = self.bedrock_agent_client.retrieve_and_generate(**request_params)
            raw_answer = response.get('output', {}).get('text', '')
            
            self.logger.info(f"📄 Received response: {len(raw_answer)} characters")
            
            # Parse JSON and extract SimilarTasks
            self.logger.info("🔍 Parsing JSON response...")
            parsed_json = json.loads(raw_answer)
            similar_tasks = parsed_json.get('SimilarTasks', [])
            
            self.logger.info(f"✅ Extracted {len(similar_tasks)} similar tasks")
            similar_tasks = self._format(similar_tasks)
            # Log each similar task in detail
            self._log_similar_tasks(similar_tasks)
            self.sync_logs()

            return {
                'SimilarTasks': similar_tasks,
                'session_id': response.get('sessionId', ''),
                'success': True
            }
            
        except json.JSONDecodeError as e:
            self.logger.error(f"❌ JSON parsing failed: {str(e)}")
            return {
                'SimilarTasks': [],
                'session_id': session_id or '',
                'success': False,
                'error': 'Could not parse response as JSON'
            }
        except Exception as e:
            self.logger.error(f"❌ Query failed: {str(e)}")
            return {
                'SimilarTasks': [],
                'session_id': session_id or '',
                'success': False,
                'error': str(e)
            }
        
    def _format(self, similar_tasks: list):
        """Format the similar tasks"""
        llm = LLM()
        prompt = self.warehouse.get_prompt('format_str')
        prompt = f"{prompt}\n\nSimilar Tasks: \n\n{similar_tasks}"
        response = llm.formatted(prompt, FormatResponse)
        return response.similar_tasks

    def _log_similar_tasks(self, similar_tasks):
        """Log detailed information about similar tasks (now formatted as string)"""
        if not similar_tasks:
            self.logger.info("📝 No similar tasks found")
            return
        
        self.logger.info(f"📝 === FORMATTED SIMILAR TASKS ===")
        # Log the formatted string response
        for line in similar_tasks.split('\n'):
            if line.strip():  # Only log non-empty lines
                self.logger.info(f"📝 {line}")
        
        self.logger.info(f"📝 === END SIMILAR TASKS ===")

    def sync_logs(self):
        """Force upload current log file to S3"""
        return sync_logs_to_s3(self.logger, self.log_manager, force_current=True)

# if __name__ == "__main__":
#     print("🧪 Testing STR with Orchestration Configuration...")
    
#     try:
#         str_component = STR(user_email="amir@m3labs.co.uk")
        
#         # Test the knowledge base query
#         result = str_component.query_knowledge_base("build rest api to retrueve customer data from mysql instance erret123")
        
#         if result['success']:
#             print(f"✅ Success! Found {len(result['SimilarTasks'])} similar tasks")
#             print(f"🔗 Session ID: {result['session_id']}")
#         else:
#             print(f"❌ Error: {result.get('error', 'Unknown error')}")
        
#     except Exception as e:
#         print(f"❌ Test failed: {e}")
#         import traceback
#         traceback.print_exc()
        