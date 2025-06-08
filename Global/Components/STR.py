import boto3
import json
import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional
import sys
import time

# Add the Prompts directory to the path to import PromptWarehouse
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from Prompts.promptwarehouse import PromptWarehouse

# Import LogManager
try:
    from Logs.log_manager import LogManager
except ImportError:
    LogManager = None

def setup_logging(user_email: str, log_manager=None):
    """Simple logging setup"""
    # Use LogManager's organized directory if available
    if log_manager and hasattr(log_manager, 'logs_dir'):
        logs_dir = log_manager.logs_dir
    else:
        logs_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'Logs')
        os.makedirs(logs_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(logs_dir, f"STR_{timestamp}.log")
    
    # Get the specific logger for STR
    logger = logging.getLogger('STR')
    logger.setLevel(logging.INFO)
    
    # Clear existing handlers to prevent duplicates
    if logger.handlers:
        logger.handlers.clear()
    
    # File handler
    file_handler = logging.FileHandler(log_file, mode='w')
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # Prevent propagation to avoid duplicate messages
    logger.propagate = False
    
    logger.info(f"📝 Log file: {log_file}")
    logger.info(f"👤 User: {user_email}")
    
    if log_manager:
        logger.info(f"🔄 LogManager ready for sync")
    
    return logger

class STR:
    def __init__(self, user_email: str = "amir@m3labs.co.uk"):
        """Initialize STR component"""
        self.user_email = user_email
        
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
        self.logger = setup_logging(user_email, self.log_manager)
        
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

    def _log_similar_tasks(self, similar_tasks: list):
        """Log detailed information about each similar task"""
        if not similar_tasks:
            self.logger.info("📝 No similar tasks found")
            return
        
        self.logger.info(f"📝 === SIMILAR TASKS DETAILS ===")
        for i, task in enumerate(similar_tasks, 1):
            self.logger.info(f"📝 Task {i}:")
            self.logger.info(f"   └─ ID: {task.get('TaskID', 'N/A')}")
            self.logger.info(f"   └─ Description: {task.get('TaskDescription', 'N/A')}")
            self.logger.info(f"   └─ Tools Used: {task.get('ToolsUsed', 'N/A')}")
            self.logger.info(f"   └─ Performance Score: {task.get('PerformanceScore', 'N/A')}")
            self.logger.info(f"   └─ Reflection Steps: {task.get('ReflectionSteps', 'N/A')}")
            self.logger.info(f"   └─ AI Description: {task.get('AIDescription', 'N/A')}")
            
            # Log details if present
            if 'Details' in task and task['Details']:
                details = task['Details'][:200] + "..." if len(task['Details']) > 200 else task['Details']
                self.logger.info(f"   └─ Details: {details}")
        
        self.logger.info(f"📝 === END SIMILAR TASKS ===")

    def sync_logs(self):
        """Force upload current log file to S3"""
        if self.log_manager:
            try:
                self.logger.info("☁️ Force uploading current log to S3...")
                
                # Flush all handlers to ensure log is written
                for handler in self.logger.handlers:
                    if hasattr(handler, 'flush'):
                        handler.flush()
                
                time.sleep(0.1)
                
                # Get current log file name
                current_log_filename = None
                for handler in self.logger.handlers:
                    if isinstance(handler, logging.FileHandler):
                        current_log_filename = os.path.basename(handler.baseFilename)
                        break
                
                if current_log_filename:
                    success = self.log_manager.force_upload_current_log(current_log_filename)
                    if success:
                        print(f"✅ Current log file uploaded successfully: {current_log_filename}")
                    else:
                        print(f"❌ Failed to upload current log file: {current_log_filename}")
                else:
                    print("⚠️ Could not determine current log file name")
                    
            except Exception as e:
                print(f"❌ Log upload failed: {e}")

# if __name__ == "__main__":
#     print("🧪 Testing STR with Orchestration Configuration...")
    
#     try:
#         str_component = STR()
        
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
        