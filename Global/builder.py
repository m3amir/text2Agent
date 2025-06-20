import sys
import os
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Global.Collector.agent import Collector
from Global.Architect.skeleton import Skeleton

class PipelineBuilder:
    """Simple pipeline builder that combines collector and architect"""
    
    def __init__(self, agent_description: str, user_email: str = ""):
        self.agent_description = agent_description
        self.user_email = user_email
        
        # Initialize components
        self.collector = Collector(agent_description, user_email)
        self.skeleton = Skeleton(user_email)
        
        # Results
        self.connectors = []
        self.tools = {}
        self.blueprint = None
        self.workflow = None
        
    async def build_pipeline(self) -> Dict[str, Any]:
        """Build the complete pipeline"""
        try:
            # Phase 1: Run collector to get connectors and tools
            await self._run_collector()
            
            # Phase 2: Build skeleton workflow
            # await self._run_skeleton()
            
            return {
                'success': True,
                'connectors': self.connectors,
                'tools': self.tools,
                'blueprint': self.blueprint,
                'workflow': self.workflow
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
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
            'connector_tools': {}
        }
        
        thread_id = f"collector_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        config = {"configurable": {"thread_id": thread_id}}
        
        # Execute collector workflow
        final_state = None
        async for step in collector_workflow.astream(initial_state, config=config):
            # Handle interrupts by asking user for feedback
            if '__interrupt__' in step:
                interrupt_data = step['__interrupt__'][0]
                if 'questions' in interrupt_data.value:
                    questions = interrupt_data.value['questions']
                    
                    print("\n" + "="*60)
                    print("📋 FEEDBACK QUESTIONS - Please provide your answers:")
                    print("="*60)
                    
                    answers = {}
                    for i, question in enumerate(questions, 1):
                        print(f"\n🔸 Question {i}: {question}")
                        print("-" * 50)
                        while True:
                            answer = input("Your answer: ").strip()
                            if answer:
                                answers[question] = answer
                                break
                            print("⚠️  Please provide a non-empty answer.")
                    
                    print("\n✅ All questions answered! Processing your responses...")
                    
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
    
    async def _run_skeleton(self):
        """Run skeleton to build workflow"""
        # Generate simple blueprint
        self.blueprint = {
            "nodes": ["gather_input", "process_with_tools", "provide_output"],
            "edges": [
                ("gather_input", "process_with_tools"),
                ("process_with_tools", "provide_output")
            ],
            "node_tools": {}
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
        self.workflow = self.skeleton.compile_graph()

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
        result = await build_agent_pipeline(
            "Send emails to amir in our leads excel spreadsheet you will find his email", 'amir@m3labs.co.uk'
        )
        
        if result['success']:
            print(f"✅ Pipeline built successfully!")
            print(f"📦 Connectors: {result['connectors']}")
            print(f"🔧 Tools: {len(result['tools'])} connectors")
        else:
            print(f"❌ Pipeline failed: {result['error']}")
    
    asyncio.run(main())