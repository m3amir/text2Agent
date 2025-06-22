import os
import sys
from pydantic import BaseModel, Field

# Fix the path to point to the root project directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from Prompts.poolOfColleagues.prompt import poc_prompt, poc_judge_prompt
from Global.llm import LLM
from utils.core import setup_logging, sync_logs_to_s3
from Prompts.promptwarehouse import PromptWarehouse

# Import LogManager
try:
    from Logs.log_manager import LogManager
except ImportError:
    LogManager = None

THRESHOLD_SCORE = 7.0

class analysisResponse(BaseModel):
    analysis: str = Field(description="The detailed analysis from the employee")

class judgementResponse(BaseModel):
    final_score: float = Field(description="The final score from 1-10")
    recommendations: str = Field(description="The detailed recommendations")

class Colleague:
    def __init__(self, user_email: str = "", log_manager=None):        
        self.user_email = user_email
        self.log_manager = log_manager
        self.logger = setup_logging(user_email, 'AI_Colleagues', self.log_manager)
        self.warehouse = PromptWarehouse('m3')
        self.logger.info("🔧 Initializing AI Colleagues...")
        self.max_depth = 1
        self.level = 1
        self.reviews = []
        self.logger.info("✅ System ready!")

    def _analyze_with_employees(self, num_colleagues: int, message: str) -> list:
        """Run parallel analysis with multiple AI colleagues"""
        # Add previous context if available
        if self.reviews:
            previous_reviews = " ".join(str(msg['recommendations']) for msg in self.reviews)
            message = f"Previous feedback: {previous_reviews}\nTask: {message}"
        
        # Configure temperature based on iteration level
        temperature = self.level / self.max_depth if self.max_depth > 0 else 0.5
        analyze_llm = LLM('m3', model_kwargs={'temperature': temperature, 'max_tokens': 4096, 'top_p': 0.3})
        
        # Run analysis with multiple colleagues
        analyses = []
        for i in range(num_colleagues):
            full_message = f"{self.warehouse.get_prompt('poc')}\n\nTask to analyze: {message}"
            analysis = analyze_llm.formatted(full_message, analysisResponse)
            analyses.append(analysis.analysis)
            self.logger.info(f"✅ Colleague {i+1}/{num_colleagues} analysis complete")
        
        return analyses
    
    def _judge_analyses(self, analyses: list) -> dict:
        """Judge evaluates all colleague analyses"""
        # Combine all analyses
        message_parts = [f"Employee{i + 1}: {analysis}" for i, analysis in enumerate(analyses)]
        combined_message = "\n\n".join(message_parts)
        
        # Configure judge with lower temperature for consistency
        temperature = self.level / self.max_depth if self.max_depth > 0 else 0.1
        judge_llm = LLM('m3', model_kwargs={'temperature': temperature, 'max_tokens': 4096, 'top_p': 0.3})
        
        # Get final judgment
        full_message = f"{poc_judge_prompt}\n\nEmployee analyses to evaluate:\n{combined_message}"
        final_review = judge_llm.formatted(full_message, judgementResponse)
        
        self.logger.info(f"📊 Score: {final_review.final_score}/10")
        
        return {
            'score': final_review.final_score,
            'recommendations': final_review.recommendations
        }

    def update_message(self, message):
        """Main analysis method - simplified without nested functions"""
        self.logger.info(f"🚀 Starting analysis: {message[-1]}")
        
        num_colleagues = 2
        message = message[-1]
        
        try:
            while True:
                self.logger.info(f"🔄 Iteration {self.level} - {num_colleagues} colleagues")
                
                # Check max depth
                if self.level > self.max_depth:
                    result = self.reviews[-1]['recommendations'] if self.reviews else "No analysis completed"
                    self.logger.info("🏁 Max depth reached")
                    return result
                
                # Run analysis with colleagues
                analyses = self._analyze_with_employees(num_colleagues, message)
                
                # Get judgment
                judgment = self._judge_analyses(analyses)
                self.reviews.append(judgment)
                
                # Check threshold
                avg_score = sum(r['score'] for r in self.reviews) / len(self.reviews)
                self.logger.info(f"📈 Average Score: {avg_score:.1f}/10")
                
                if avg_score >= THRESHOLD_SCORE:
                    self.logger.info("🎯 Threshold met!")
                    return judgment['recommendations']
                    
                # Scale up and continue
                num_colleagues *= 2
                self.level += 1
        
        finally:
            # S3 sync - only current session to avoid massive log spam  
            sync_logs_to_s3(self.logger, self.log_manager, force_current=True)
            self.logger.info(f"📊 Final reviews: {self.reviews}")