import sys
import os
import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from Global.Architect.skeleton import Skeleton
from Global.llm import LLM
from utils.core import get_secret, save_file_to_s3, setup_logging, sync_logs_to_s3
from Prompts.promptwarehouse import PromptWarehouse

# Import LogManager
try:
    from Logs.log_manager import LogManager
except ImportError:
    LogManager = None

class Test:
    def __init__(self, secret_name="test_", user_email="amir@m3labs.co.uk", recipient="info@m3labs.co.uk", task_description="", agent_run_id=None, log_manager=None):
        """
        Initialize Test class
        
        Args:
            secret_name: Name of the AWS secret to retrieve credentials from
            user_email: User's email address
            recipient: Email recipient for testing
            task_description: Description of the testing task
            agent_run_id: Unique identifier for this test run
            log_manager: Optional LogManager instance for organized logging
        """
        self.secret_name = secret_name
        self.user_email = user_email
        self.recipient = recipient
        self.task_description = task_description
        self.log_manager = log_manager
        
        # No longer need to store credentials - MCP server handles this
        
        # Set up agent run ID
        self.agent_run_id = agent_run_id or f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
        
        # Initialize logging
        self.logger = setup_logging(user_email, "Test_System", log_manager)
        self.logger.info(f"Initializing Test System - Secret: {secret_name}, Task: {task_description}")
        
        self.test_results = {}
        self.tool_questions = {}
        self.test_results_folder = Path("tmp/Tests") / self.agent_run_id
        self.test_results_folder.mkdir(parents=True, exist_ok=True)
        self.prompt_warehouse = PromptWarehouse('m3')
        self.available_tools = ['microsoft_mail_send_email_as_user']

    async def test_tools(self, tools_to_test=None):
        """Test specified tools using MCP server credential handling"""
        tools_to_test = tools_to_test or self.available_tools
        self.logger.info(f"Testing {len(tools_to_test)} tools with secret: {self.secret_name}")
        
        # Initialize skeleton
        skeleton = Skeleton(user_email=self.user_email)
        
        try:
            await skeleton.load_tools(tools_to_test)
            
            if not skeleton.available_tools:
                self.logger.warning("No tools loaded (MCP might not be available)")
                return False
            
            # Generate questions and test tools
            for tool_name in tools_to_test:
                if tool_name in skeleton.available_tools:
                    await self._generate_tool_question(skeleton, tool_name)
                    self.logger.info(f"Testing: {tool_name}")
                    await self._test_single_tool(skeleton, tool_name)
                else:
                    self.logger.warning(f"Tool '{tool_name}' not available, skipping...")
                
        except Exception as e:
            self.logger.error(f"❌ Error during tool testing: {e}")
            return False
        finally:
            await skeleton.cleanup_tools()
            
        return True

    async def _generate_tool_question(self, skeleton, tool_name):
        """Generate a specific question for testing this tool based on task description"""
        try:
            if not self.task_description:
                question = f"How should the {tool_name} tool be tested effectively?"
            else:
                llm = LLM()
                tool = skeleton.available_tools[tool_name]
                tool_description = self._get_tool_description(tool)
                
                prompt = self.prompt_warehouse.get_prompt("tool_question").format(
                    task_description=self.task_description,
                    tool_name=tool_name,
                    tool_description=tool_description
                )
                response = llm.get_model().invoke(prompt)
                question = response.content.strip()
            
            self.tool_questions[tool_name] = question
            self.logger.info(f"Generated question for {tool_name}: {question}")
            
        except Exception as e:
            self.logger.error(f"Error generating question for {tool_name}: {e}")
            self.tool_questions[tool_name] = f"How should the {tool_name} tool be tested for the task: {self.task_description}?"

    async def _test_single_tool(self, skeleton, tool_name):
        """Test a single tool with generated arguments"""
        try:
            args = await self._generate_tool_args(skeleton, tool_name)
            
            if 'microsoft' in tool_name.lower() or 'mail' in tool_name.lower():
                args['secret_name'] = self.secret_name
                
            self.logger.info(f"Generated args: {args}")
            
            tool = skeleton.available_tools[tool_name]
            result = await tool.ainvoke(args) if hasattr(tool, 'ainvoke') else tool.invoke(args)
                
            result_str = self._format_result(result)
            self.logger.info(f"Result: {result_str}")
            self.test_results[tool_name] = result_str
            
            return result_str
            
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            self.logger.error(error_msg)
            return error_msg

    async def _generate_tool_args(self, skeleton, tool_name):
        """Generate arguments dynamically based on tool schema"""
        try:
            llm = LLM()
            tool = skeleton.available_tools[tool_name]
            bound_model = llm.get_model().bind_tools([tool])
            
            tool_description = self._get_tool_description(tool)
            tool_schema = self._get_tool_schema(tool)
            today = datetime.now().strftime("%Y-%m-%d")
            tool_question = self.tool_questions.get(tool_name, f"How should the {tool_name} tool be tested effectively?")
            
            prompt = self.prompt_warehouse.get_prompt("arguments").format(
                tool_name=tool_name,
                tool_description=tool_description,
                tool_schema=tool_schema,
                tool_question=tool_question,
                user_email=self.user_email,
                recipient=self.recipient,
                today=today
            )
            
            response = bound_model.invoke(prompt)
            return response.tool_calls[0].get('args', {}) if hasattr(response, 'tool_calls') and response.tool_calls else {}
                
        except Exception as e:
            self.logger.error(f"Error generating args for {tool_name}: {e}")
            return {}
    
    def _get_tool_description(self, tool):
        """Extract tool description dynamically"""
        if hasattr(tool, 'description'):
            return tool.description
        elif hasattr(tool, '__doc__') and tool.__doc__:
            return tool.__doc__
        elif hasattr(tool, 'func') and hasattr(tool.func, '__doc__') and tool.func.__doc__:
            return tool.func.__doc__
        return f"Tool: {tool.__class__.__name__}"
    
    def _get_tool_schema(self, tool):
        """Extract tool input schema dynamically"""
        try:
            if hasattr(tool, 'args_schema') and tool.args_schema:
                return tool.args_schema
            elif hasattr(tool, 'input_schema'):
                return tool.input_schema
            elif hasattr(tool, 'func'):
                import inspect
                sig = inspect.signature(tool.func)
                return {
                    "parameters": {param.name: {"type": str(param.annotation.__name__ if param.annotation != inspect.Parameter.empty else "any")} 
                                 for param in sig.parameters.values()}
                }
        except:
            pass
        return {}

    def _format_result(self, result):
        """Format tool response to readable string"""
        result_str = str(result)
        
        try:
            if result_str.startswith('{') and result_str.endswith('}'):
                parsed = json.loads(result_str)
                formatted_parts = [f"{key.title()}: {'Empty' if isinstance(value, list) and len(value) == 0 else value}" 
                                 for key, value in parsed.items()]
                return " | ".join(formatted_parts)
        except:
            pass
            
        return result_str

    def export_results(self, filename="test_results.json"):
        """Export test results to JSON file and upload to S3"""
        try:
            filepath = self.test_results_folder / filename
            
            with open(filepath, 'w') as f:
                json.dump({
                    'agent_run_id': self.agent_run_id,
                    'secret_name': self.secret_name,
                    'user_email': self.user_email,
                    'recipient': self.recipient,
                    'task_description': self.task_description,
                    'tool_questions': self.tool_questions,
                    'results': self.test_results
                }, f, indent=2)
            self.logger.info(f"Results exported locally: {filepath.absolute()}")
            
            try:
                s3_path = f"cognito/{self.user_email}/Data/{self.agent_run_id}/{filename}"
                metadata = {'category': 'test_results', 'agent_run_id': self.agent_run_id, 'secret_name': self.secret_name}
                
                if save_file_to_s3(str(filepath.absolute()), self.user_email, s3_path, metadata):
                    self.logger.info(f"Results also saved to S3 under {s3_path}")
                else:
                    self.logger.warning("S3 upload failed, but local file saved successfully")
            except Exception as s3_error:
                self.logger.warning(f"S3 upload failed: {s3_error}, but local file saved successfully")
                
        except Exception as e:
            self.logger.error(f"Failed to export results: {e}")



async def main():
    """Main test execution"""
    log_manager = LogManager("amir@m3labs.co.uk") if LogManager else None
    
    test = Test(
        secret_name="test_",
        user_email="amir@m3labs.co.uk",
        recipient="info@m3labs.co.uk",
        task_description="Send a professional email notification about the latest M3 Labs product updates to stakeholders",
        agent_run_id=None,
        log_manager=log_manager
    )
    
    test.logger.info("Starting AWS Secrets Manager Tool Tests")
    
    try:
        success = await test.test_tools()
        
        if success:
            test.export_results()
            test.logger.info("✓ All tests completed successfully!")
        else:
            test.logger.error("❌ Tests failed!")
            
    finally:
        sync_logs_to_s3(test.logger, test.log_manager, force_current=True)
        test.logger.info(f"Final test results: {test.test_results}")

if __name__ == "__main__":
    asyncio.run(main())