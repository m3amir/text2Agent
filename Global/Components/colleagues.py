import operator
import logging
import os
from datetime import datetime
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import END, START, StateGraph
import sys
from pydantic import BaseModel, Field
import time

# Fix the path to point to the root project directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from Prompts.poolOfColleagues.prompt import poc_prompt, poc_judge_prompt
from Prompts.promptwarehouse import PromptWarehouse
from Global.llm import LLM

# Import LogManager
try:
    from Logs.log_manager import LogManager
except ImportError:
    LogManager = None

def setup_logging(user_email: str, log_manager=None):
    """Simple logging setup"""
    logs_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'Logs')
    os.makedirs(logs_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(logs_dir, f"colleagues_{timestamp}.log")
    
    # Get the specific logger for AI_Colleagues, don't mess with root logger
    logger = logging.getLogger('AI_Colleagues')
    logger.setLevel(logging.INFO)
    
    # Clear existing handlers to prevent duplicates
    if logger.handlers:
        logger.handlers.clear()
    
    # Only add handlers if none exist
    if not logger.handlers:
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
    
    # Prevent propagation to avoid duplicate messages from root logger
    logger.propagate = False
    
    logger.info(f"📝 Log file: {log_file}")
    logger.info(f"👤 User: {user_email}")
    
    # Setup auto-sync - moved to main.py for better control
    if log_manager:
        logger.info(f"🔄 LogManager ready for sync")
    
    return logger

class analysisResponse(BaseModel):
    analysis: str = Field(description="The detailed analysis from the employee")

class judgementResponse(BaseModel):
    final_score: int = Field(description="The final score from 1-10")
    recommendations: str = Field(description="The detailed recommendations")

class State(TypedDict):
    aggregate: Annotated[list, operator.add]
    route: Annotated[list, operator.add]
    level: Annotated[list, operator.add]
    temperature: Annotated[list, operator.add]
    max_depth: Annotated[list, operator.add]
    reviews: Annotated[list, operator.add]

class Colleague:
    def __init__(self, user_email: str = "amir@m3labs.co.uk", log_manager=None):        
        self.user_email = user_email
        self.log_manager = log_manager
        self.logger = setup_logging(user_email, self.log_manager)
        
        self.logger.info("🔧 Initializing AI Colleagues...")
        self.warehouse = PromptWarehouse('m3')
        self.analyse = LLM('m3', model_kwargs={'temperature': 0.9, 'max_tokens': 4096, 'top_p': 0.3})
        self.judge = LLM('m3', model_kwargs={'temperature': 0.1, 'max_tokens': 4096, 'top_p': 0.3})
        self.max_depth = 1
        self.node_counter = 1 
        self.level = 1
        self.reviews = []
        self.logger.info("✅ System ready!")

    def create_employee_node(self, employee_id):
        def employee_function(state: State) -> State:
            message = getattr(self, '_current_message', '')
            full_message = f"{poc_prompt}\n\nTask to analyze: {message}"
            analysis = self.analyse.formatted(full_message, analysisResponse)
            return {"aggregate": [analysis.analysis]}
        return employee_function

    def judgement(self, state):
        message_parts = [f"Employee{i + 1}: {entry}" for i, entry in enumerate(state['aggregate'])]
        message = "\n\n".join(message_parts)
        full_message = f"{poc_judge_prompt}\n\nEmployee analyses to evaluate:\n{message}"
        
        final_review = self.judge.formatted(full_message, judgementResponse)
        self.logger.info(f"📊 Score: {final_review.final_score}/10")
        
        return {"reviews": [{'score': final_review.final_score, 'recommendations': final_review.recommendations}]}
    
    def _build_graph(self, num_nodes: int, message: str):
        self._current_message = str(message)
        self.node_counter = 1
        self.builder = StateGraph(State)
        
        # Add previous context if available
        if self.reviews:
            previous_reviews = " ".join(str(msg['recommendations']) for msg in self.reviews)
            message = f"Previous feedback: {previous_reviews}\nTask: {message}"
            
        # Create employee nodes
        employee_nodes = []
        for i in range(num_nodes):
            node_name = f"employee{self.node_counter}"
            employee_func = self.create_employee_node(f"Employee-{self.node_counter}")
            self.node_counter += 1
            self.builder.add_node(node_name, employee_func)
            employee_nodes.append(node_name)
            self.builder.add_edge(START, node_name)

        # Add judge node
        self.builder.add_node("judgement", self.judgement)
        for node in employee_nodes:
            self.builder.add_edge(node, "judgement")
        self.builder.add_edge("judgement", END)
        
        # Execute
        self.graph = self.builder.compile()
        initial_state = {
            "aggregate": [], "route": [], "max_depth": [self.max_depth],
            "level": [self.level], "reviews": [], "temperature": []
        }
        
        return self.graph.invoke(initial_state)['reviews'][0]

    def update_message(self, message):
        self.logger.info(f"🚀 Starting analysis: {message[-1]}")
        
        num_nodes = 2
        message = message[-1]
        
        try:
            while True:
                self.logger.info(f"🔄 Iteration {self.level} - {num_nodes} colleagues")
                
                # Check max depth
                if self.level > self.max_depth:
                    result = self.reviews[-1]['recommendations'] if self.reviews else "No analysis completed"
                    self.logger.info("🏁 Max depth reached")
                    return result
                    
                # Configure models
                temperature = self.level / self.max_depth
                self.analyse = LLM('m3', model_kwargs={'temperature': temperature, 'max_tokens': 4096, 'top_p': 0.3})
                self.judge = LLM('m3', model_kwargs={'temperature': temperature, 'max_tokens': 4096, 'top_p': 0.3})
                
                # Execute analysis
                judgement = self._build_graph(num_nodes, message)
                self.reviews.append(judgement)
                
                # Check threshold
                avg_score = sum(r['score'] for r in self.reviews) / len(self.reviews)
                self.logger.info(f"📈 Score: {avg_score:.1f}/10")
                
                if avg_score >= 7.0:
                    self.logger.info("🎯 Threshold met!")
                    return judgement['recommendations']
                    
                # Scale up
                num_nodes *= 2
                self.level += 1
        
        finally:
            # S3 sync - close log handlers first to ensure file is available
            self.logger.info("☁️ Syncing logs...")
            if self.log_manager:
                try:
                    # Flush and close file handlers to release file locks
                    for handler in self.logger.handlers:
                        if isinstance(handler, logging.FileHandler):
                            handler.flush()
                            if hasattr(handler, 'close'):
                                handler.close()
                    
                    # Small delay to ensure file system updates
                    time.sleep(0.5)
                    
                    sync_results = self.log_manager.sync_logs(older_than_hours=0, delete_after_sync=False)
                    
                    self.logger.info(f"✅ Synced {len(sync_results['synced'])} files")
                except Exception as e:
                    print(f"❌ Sync failed: {e}")
            else:
                print("⚠️ No LogManager - local only")