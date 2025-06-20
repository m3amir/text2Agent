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
        if agent_run_id:
            self.agent_run_id = agent_run_id
        else:
            from datetime import datetime
            import uuid
            self.agent_run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
        
        # Initialize logging
        self.logger = setup_logging(user_email, "Test_System", log_manager)
        self.logger.info("Initializing Test System...")
        self.logger.info(f"Secret: {secret_name}")
        self.logger.info(f"Task: {task_description}")
        self.logger.info("System ready!")
        
        # Set up test results storage
        self.test_results = {}
        self.tool_questions = {}
        
        # Create results folder
        self.test_results_folder = Path("tmp/Tests") / self.agent_run_id
        self.test_results_folder.mkdir(parents=True, exist_ok=True)
        
        # Initialize prompt warehouse (using the correct import already at top of file)
        self.prompt_warehouse = PromptWarehouse('m3')
        
        # Available tools for testing - focusing on email only
        self.available_tools = [
            'microsoft_mail_send_email_as_user'
        ]

    async def test_tools(self, tools_to_test=None):
        """Test specified tools using MCP server credential handling"""
        if not tools_to_test:
            tools_to_test = self.available_tools

        self.logger.info(f"Testing {len(tools_to_test)} tools with secret: {self.secret_name}")
        
        # Initialize skeleton
        skeleton = Skeleton(user_email=self.user_email)
        
        try:
            await skeleton.load_tools(tools_to_test)
            
            if not skeleton.available_tools:
                self.logger.warning("No tools loaded (MCP might not be available)")
                return False
            
            # Generate questions for all tools first
            self.logger.info(f"Generating testing questions based on task: '{self.task_description}'")
            for tool_name in tools_to_test:
                if tool_name in skeleton.available_tools:
                    await self._generate_tool_question(skeleton, tool_name)
                
            # Test each tool
            for tool_name in tools_to_test:
                if tool_name not in skeleton.available_tools:
                    self.logger.warning(f"Tool '{tool_name}' not available, skipping...")
                    continue
                    
                self.logger.info(f"Testing: {tool_name}")
                await self._test_single_tool(skeleton, tool_name)
                
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
                return f"How should the {tool_name} tool be tested effectively?"
            
            llm = LLM()
            model = llm.get_model()
            
            tool = skeleton.available_tools[tool_name]
            tool_description = self._get_tool_description(tool)
            
            prompt = self.prompt_warehouse.get_prompt("tool_question").format(
                task_description=self.task_description,
                tool_name=tool_name,
                tool_description=tool_description
            )
            response = model.invoke(prompt)
            question = response.content.strip()
            
            # Store the question for this tool
            self.tool_questions[tool_name] = question
            self.logger.info(f"Generated question for {tool_name}: {question}")
            
            return question
            
        except Exception as e:
            self.logger.error(f"Error generating question for {tool_name}: {e}")
            default_question = f"How should the {tool_name} tool be tested for the task: {self.task_description}?"
            self.tool_questions[tool_name] = default_question
            return default_question

    async def _test_single_tool(self, skeleton, tool_name):
        """Test a single tool with generated arguments"""
        try:
            # Generate test arguments
            args = await self._generate_tool_args(skeleton, tool_name)
            
            # Add secret name for credential lookup for Microsoft tools
            if 'microsoft' in tool_name.lower() or 'mail' in tool_name.lower():
                args['secret_name'] = self.secret_name
                
            self.logger.info(f"Generated args: {args}")
            
            # Execute tool
            tool = skeleton.available_tools[tool_name]
            
            if hasattr(tool, 'ainvoke'):
                result = await tool.ainvoke(args)
            else:
                result = tool.invoke(args)
                
            result_str = self._format_result(result)
            self.logger.info(f"Result: {result_str}")
            
            # Store in dictionary with tool name as key and formatted string as value
            self.test_results[tool_name] = result_str
            
            return result_str
            
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            self.logger.error(f"{error_msg}")
            return error_msg

    async def _generate_tool_args(self, skeleton, tool_name):
        """Generate arguments dynamically based on tool schema"""
        try:
            llm = LLM()
            tool = skeleton.available_tools[tool_name]
            bound_model = llm.get_model().bind_tools([tool])
            
            # Get tool description and schema dynamically
            tool_description = self._get_tool_description(tool)
            tool_schema = self._get_tool_schema(tool)
            
            # Get today's date for context
            from datetime import datetime
            today = datetime.now().strftime("%Y-%m-%d")
            
            # Get the generated question for this tool
            tool_question = self.tool_questions.get(tool_name, f"How should the {tool_name} tool be tested effectively?")
            
            # Get the arguments prompt from warehouse and format it with dynamic values
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
            
            if hasattr(response, 'tool_calls') and response.tool_calls:
                return response.tool_calls[0].get('args', {})
            else:
                return {}
                
        except Exception as e:
            self.logger.error(f"Error generating args for {tool_name}: {e}")
            return {}
    
    def _get_tool_description(self, tool):
        """Extract tool description dynamically"""
        description = ""
        
        if hasattr(tool, 'description'):
            description = tool.description
        elif hasattr(tool, '__doc__') and tool.__doc__:
            description = tool.__doc__
        elif hasattr(tool, 'func') and hasattr(tool.func, '__doc__') and tool.func.__doc__:
            description = tool.func.__doc__
        
        return description or f"Tool: {tool.__class__.__name__}"
    
    def _get_tool_schema(self, tool):
        """Extract tool input schema dynamically"""
        schema = {}
        
        try:
            if hasattr(tool, 'args_schema') and tool.args_schema:
                schema = tool.args_schema
            elif hasattr(tool, 'input_schema'):
                schema = tool.input_schema
            elif hasattr(tool, 'func'):
                import inspect
                sig = inspect.signature(tool.func)
                schema = {
                    "parameters": {param.name: {"type": str(param.annotation.__name__ if param.annotation != inspect.Parameter.empty else "any")} 
                                 for param in sig.parameters.values()}
                }
        except:
            pass
            
        return schema

    def _format_result(self, result):
        """Format tool response to readable string"""
        result_str = str(result)
        
        try:
            if result_str.startswith('{') and result_str.endswith('}'):
                parsed = json.loads(result_str)
                formatted_parts = []
                
                for key, value in parsed.items():
                    if isinstance(value, list) and len(value) == 0:
                        formatted_parts.append(f"{key.title()}: Empty")
                    elif isinstance(value, list) and len(value) <= 3:
                        formatted_parts.append(f"{key.title()}: {value}")
                    else:
                        formatted_parts.append(f"{key.title()}: {value}")
                
                return " | ".join(formatted_parts)
        except:
            pass
            
        return result_str

    def export_results(self, filename="test_results.json"):
        """Export test results to JSON file in the tmp/Tests/{run_id}/ directory and upload to S3"""
        try:
            filepath = self.test_results_folder / filename
            
            # Save locally first
            with open(filepath, 'w') as f:
                json.dump({
                    'agent_run_id': self.agent_run_id,
                    'secret_name': self.secret_name,
                    'user_email': self.user_email,
                    'recipient': self.recipient,
                    'task_description': self.task_description,
                    'tool_questions': self.tool_questions,
                    'results': self.test_results  # Dict with tool_name: formatted_string_response
                }, f, indent=2)
            self.logger.info(f"Results exported locally: {filepath.absolute()}")
            
            # Upload to S3 using the flexible function
            try:
                s3_path = f"cognito/{self.user_email}/Data/{self.agent_run_id}/{filename}"
                metadata = {
                    'category': 'test_results',
                    'agent_run_id': self.agent_run_id,
                    'secret_name': self.secret_name
                }
                
                success = save_file_to_s3(
                    file_path=str(filepath.absolute()),
                    user_email=self.user_email,
                    s3_path=s3_path,
                    metadata=metadata
                )
                if success:
                    self.logger.info(f"Results also saved to S3 under {s3_path}")
                else:
                    self.logger.warning(f"S3 upload failed, but local file saved successfully")
            except Exception as s3_error:
                self.logger.warning(f"S3 upload failed: {s3_error}, but local file saved successfully")
                
        except Exception as e:
            self.logger.error(f"Failed to export results: {e}")



async def main():
    """Main test execution"""
    # Initialize LogManager
    log_manager = LogManager("amir@m3labs.co.uk") if LogManager else None
    
    # Initialize test with configurable parameters
    test = Test(
        secret_name="test_",  # Change this to test different secrets
        user_email="amir@m3labs.co.uk",
        recipient="info@m3labs.co.uk",  # Recipient email - DO NOT change, this is the designated recipient
        task_description="Send a professional email notification about the latest M3 Labs product updates to stakeholders",
        agent_run_id=None,  # Set to None to auto-generate, or provide a specific ID like "run_20231215_143022_a1b2c3d4"
        log_manager=log_manager
    )
    
    test.logger.info("Starting AWS Secrets Manager Tool Tests")
    
    try:
        # Run tests
        success = await test.test_tools()
        
        if success:
            test.export_results()
            test.logger.info("✓ All tests completed successfully!")
        else:
            test.logger.error("❌ Tests failed!")
            
    finally:
        # S3 sync - only current session to avoid massive log spam  
        sync_logs_to_s3(test.logger, test.log_manager, force_current=True)
        test.logger.info(f"Final test results: {test.test_results}")

if __name__ == "__main__":
    asyncio.run(main())