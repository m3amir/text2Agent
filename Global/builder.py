import sys
import os
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Global.Collector.agent import Collector
from Global.Architect.skeleton import Skeleton
from utils.core import get_secret

# Import MCP tools function
try:
    import importlib.util
    converter_path = os.path.join(os.path.dirname(__file__), '..', 'MCP', 'langchain_converter.py')
    spec = importlib.util.spec_from_file_location("langchain_converter", converter_path)
    langchain_converter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(langchain_converter)
    get_mcp_tools_with_session = langchain_converter.get_mcp_tools_with_session
except Exception as e:
    print(f"Failed to import MCP tools: {e}")
    get_mcp_tools_with_session = None

class PipelineBuilder:
    """Simple pipeline builder that combines collector and architect"""
    
    def __init__(self, agent_description: str, user_email: str = ""):
        self.agent_description = agent_description
        self.user_email = user_email
        
        # Initialize user credentials
        self.user_credentials = None
        self.user_secret_name = "test_"  # Default to test_ for now
        
        # Load user credentials if email provided
        if user_email:
            self._load_user_credentials()
        
        # Initialize components
        self.collector = Collector(agent_description, user_email)
        self.skeleton = Skeleton(user_email)
        
        # Results
        self.connectors = []
        self.tools = {}
        self.blueprint = None
        self.workflow = None
        
    def _load_user_credentials(self):
        """Load user-specific credentials from secret manager"""
        try:
            print(f"🔐 Loading credentials for user: {self.user_email}")
            self.user_credentials = get_secret(self.user_secret_name)
            
            if self.user_credentials:
                print(f"✅ Successfully loaded credentials")
                print(f"Secret name: {self.user_secret_name}")
                self._print_credential_summary(self.user_credentials)
            else:
                print(f"❌ Failed to load credentials for {self.user_email}")
                
        except Exception as e:
            print(f"❌ Error loading user credentials: {e}")
            self.user_credentials = None
    
    def _print_credential_summary(self, data):
        """Print a safe summary of credential structure"""
        print("\nCREDENTIAL SUMMARY:")
        print("=" * 30)
        
        if isinstance(data, dict):
            for key, value in data.items():
                if any(sensitive in key.lower() for sensitive in ['password', 'secret', 'key', 'token']):
                    if isinstance(value, str) and len(value) > 0:
                        print(f"  {key}: *** ({len(value)} chars)")
                    else:
                        print(f"  {key}: *** ({type(value).__name__})")
                else:
                    print(f"  {key}: {value}")
        print("=" * 30)
    
    def get_user_credentials(self) -> Optional[Dict[str, Any]]:
        """Get the loaded user credentials"""
        return self.user_credentials
    
    def get_user_secret_name(self) -> Optional[str]:
        """Get the user's secret name"""
        return self.user_secret_name

    async def build_pipeline(self) -> Dict[str, Any]:
        """Build the complete pipeline"""
        try:
            # Use MCP session context manager (like Test class)
            if get_mcp_tools_with_session is None:
                print("⚠️ MCP not available")
                return {
                    'success': False,
                    'error': 'MCP tools not available',
                    'user_credentials_loaded': self.user_credentials is not None,
                    'user_secret_name': self.user_secret_name,
                    'mcp_session_active': False
                }
            
            async with get_mcp_tools_with_session() as mcp_tools:
                print("🔌 MCP session active for pipeline")
                
                # Phase 1: Run collector to get connectors and tools
                await self._run_collector()
                
                # Phase 2: Build skeleton workflow  
                await self._run_skeleton(mcp_tools)
                
                return {
                    'success': True,
                    'connectors': self.connectors,
                    'tools': self.tools,
                    'blueprint': self.blueprint,
                    'workflow': self.workflow,
                    'user_credentials_loaded': self.user_credentials is not None,
                    'user_secret_name': self.user_secret_name,
                    'mcp_session_active': True
                }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'user_credentials_loaded': self.user_credentials is not None,
                'user_secret_name': self.user_secret_name,
                'mcp_session_active': False
            }
    
    async def _run_collector(self):
        """Run collector to gather requirements and select tools"""
        collector_workflow = self.collector.init_agent()
        
        initial_state = {
            'input': self.agent_description,
            'connectors': [],
            'feedback_questions': [],
            'answered_questions': [],
            'reviewed': False,
            'connector_tools': {},
            'user_secret_name': self.user_secret_name
        }
        
        thread_id = f"collector_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        config = {"configurable": {"thread_id": thread_id}}
        
        # Execute collector workflow
        final_state = None
        async for step in collector_workflow.astream(initial_state, config=config):
            if '__interrupt__' in step:
                interrupt_data = step['__interrupt__'][0]
                if 'questions' in interrupt_data.value:
                    questions = interrupt_data.value['questions']
                    
                    print("\nFEEDBACK QUESTIONS:")
                    print("=" * 40)
                    
                    answers = {}
                    for i, question in enumerate(questions, 1):
                        print(f"\nQuestion {i}: {question}")
                        while True:
                            answer = input("Your answer: ").strip()
                            if answer:
                                answers[question] = answer
                                break
                            print("Please provide a non-empty answer.")
                    
                    print("\n✅ Processing your responses...")
                    
                    await collector_workflow.aupdate_state(
                        config, 
                        {"answered_questions": [answers], "reviewed": True}
                    )
                    
                    # Continue execution
                    async for resume_step in collector_workflow.astream(None, config=config):
                        final_state = resume_step
            else:
                final_state = step
        
        if final_state:
            state_data = list(final_state.values())[0]
            self.connectors = state_data.get('connectors', [])
            self.tools = state_data.get('connector_tools', {})
    
    async def _run_skeleton(self, mcp_tools):
        """Run skeleton to build workflow"""
        # Generate simple blueprint
        self.blueprint = {
            "nodes": ["gather_input", "process_with_tools", "provide_output"],
            "edges": [
                ("gather_input", "process_with_tools"),
                ("process_with_tools", "provide_output")
            ],
            "node_tools": {},
            "user_secret_name": self.user_secret_name
        }
        
        # Assign tools to processing node
        if self.tools:
            processing_tools = []
            for connector_name, tools in self.tools.items():
                processing_tools.extend(list(tools.keys())[:3])  # Max 3 tools per connector
            
            self.blueprint["node_tools"]["process_with_tools"] = processing_tools
        
        # Load tools and create workflow
        all_tool_names = []
        for tools in self.tools.values():
            all_tool_names.extend(tools.keys())
        
        await self.skeleton.load_tools(all_tool_names)
        
        task_description = f"Agent: {self.agent_description}"
        self.skeleton.create_skeleton(task_description, self.blueprint)
        self.workflow, viz_files = self.skeleton.compile_and_visualize(task_description)

# Simple function to build pipeline
async def build_agent_pipeline(agent_description: str, user_email: str = "") -> Dict[str, Any]:
    """Build a complete agent pipeline"""
    builder = PipelineBuilder(agent_description, user_email)
    return await builder.build_pipeline()

# Sync wrapper
def build_agent_pipeline_sync(agent_description: str, user_email: str = "") -> Dict[str, Any]:
    """Synchronous wrapper for build_agent_pipeline"""
    return asyncio.run(build_agent_pipeline(agent_description, user_email))

if __name__ == "__main__":
    async def main():
        print("Starting Pipeline Builder")
        print("=" * 40)
        
        # Build first pipeline
        print("\nBuilding Pipeline 1...")
        result1 = await build_agent_pipeline(
            "Send emails to amir in our leads excel spreadsheet you will find his email", 
            'amir@m3labs.co.uk'
        )
        
        print(f"✅ Pipeline 1: {'Success' if result1['success'] else 'Failed'}")
        if result1['success']:
            print(f"Connectors: {result1['connectors']}")
            print(f"Tools: {len(result1['tools'])} connectors")
        
        # Build second pipeline
        print("\nBuilding Pipeline 2...")
        result2 = await build_agent_pipeline(
            "Generate charts and create PDF reports with analysis", 
            'amir@m3labs.co.uk'
        )
        
        print(f"✅ Pipeline 2: {'Success' if result2['success'] else 'Failed'}")
        if result2['success']:
            print(f"Connectors: {result2['connectors']}")
            print(f"Tools: {len(result2['tools'])} connectors")
    
    asyncio.run(main())