import sys
import os
import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from Global.llm import LLM
from utils.core import get_secret, save_file_to_s3, setup_logging, sync_logs_to_s3
from Prompts.promptwarehouse import PromptWarehouse

# Import LogManager
try:
    from Logs.log_manager import LogManager
except ImportError:
    LogManager = None

# Import MCP tools
try:
    from MCP.langchain_converter import get_mcp_tools_with_session
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

class Test:
    def __init__(self, blueprint: Dict[str, Any], secret_name="test_", user_email="amir@m3labs.co.uk", recipient="info@m3labs.co.uk", task_description="", agent_run_id=None, log_manager=None):
        """
        Initialize Test class
        
        Args:
            blueprint: Blueprint dictionary containing nodes, edges, and node_tools
            secret_name: Name of the AWS secret to retrieve credentials from
            user_email: User's email address
            recipient: Email recipient for testing
            task_description: Description of the testing task
            agent_run_id: Unique identifier for this test run
            log_manager: Optional LogManager instance for organized logging
        """
        self.blueprint = blueprint
        self.secret_name = secret_name
        self.user_email = user_email
        self.recipient = recipient
        self.task_description = task_description
        self.log_manager = log_manager
        
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
        
        # Extract tools from blueprint
        self.available_tools_from_blueprint = self._extract_tools_from_blueprint()
        self.available_tools = {}  # Will be populated when loading tools
        self._mcp_session_tools = None  # Store MCP session tools
        
        self.logger.info(f"Extracted {len(self.available_tools_from_blueprint)} unique tools from blueprint: {self.available_tools_from_blueprint}")

    def _extract_tools_from_blueprint(self) -> List[str]:
        """Extract all unique tools from the blueprint"""
        all_tools = []
        node_tools = self.blueprint.get('node_tools', {})
        
        for node_name, tools in node_tools.items():
            if isinstance(tools, list):
                all_tools.extend(tools)
            elif isinstance(tools, str):
                all_tools.append(tools)
        
        # Return unique tools
        return list(set(all_tools))

    async def test_tools(self, tools_to_test=None):
        """Test specified tools using MCP server credential handling with persistent session"""
        tools_to_test = tools_to_test or self.available_tools_from_blueprint
        self.logger.info(f"Testing {len(tools_to_test)} tools with secret: {self.secret_name}")
        
        if not MCP_AVAILABLE:
            self.logger.warning("MCP not available - no tools will be loaded")
            return False
        
        try:
            # Use persistent MCP session
            async with get_mcp_tools_with_session() as session_tools:
                self._mcp_session_tools = session_tools
                await self._load_tools_from_session(tools_to_test)
                
                if not self.available_tools:
                    self.logger.warning("No tools loaded (MCP might not be available)")
                    return False
                
                # Generate questions and test tools
                for tool_name in tools_to_test:
                    if tool_name in self.available_tools:
                        await self._generate_tool_question(tool_name)
                        self.logger.info(f"Testing: {tool_name}")
                        await self._test_single_tool(tool_name)
                    else:
                        self.logger.warning(f"Tool '{tool_name}' not available, skipping...")
                
        except Exception as e:
            self.logger.error(f"❌ Error during tool testing: {e}")
            return False
        finally:
            await self._cleanup_tools()
            
        return True

    async def _load_tools_from_session(self, tool_names: List[str]):
        """Load tools from the active MCP session"""
        try:
            if not self._mcp_session_tools:
                self.logger.warning("No MCP session tools available")
                return
                
            for tool_name in tool_names:
                for tool in self._mcp_session_tools:
                    if (hasattr(tool, 'name') and tool.name == tool_name) or \
                       (hasattr(tool, '_name') and tool._name == tool_name):
                        self.available_tools[tool_name] = tool
                        break
            
            self.logger.info(f"Loaded {len(self.available_tools)} tools: {list(self.available_tools.keys())}")
            
        except Exception as e:
            self.logger.warning(f"Failed to load tools from session: {e}")

    async def _cleanup_tools(self):
        """Clean up tools after testing"""
        self.available_tools.clear()
        self._mcp_session_tools = None

    async def _generate_tool_question(self, tool_name):
        """Generate a specific question for testing this tool based on task description"""
        try:
            if not self.task_description:
                question = f"How should the {tool_name} tool be tested effectively?"
            else:
                llm = LLM()
                tool = self.available_tools[tool_name]
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

    async def _test_single_tool(self, tool_name):
        """Test a single tool with generated arguments"""
        try:
            args = await self._generate_tool_args(tool_name)
            
            if 'microsoft' in tool_name.lower() or 'mail' in tool_name.lower():
                args['secret_name'] = self.secret_name
                
            self.logger.info(f"Generated args: {args}")
            
            tool = self.available_tools[tool_name]
            result = await tool.ainvoke(args) if hasattr(tool, 'ainvoke') else tool.invoke(args)
                
            result_str = self._format_result(result)
            self.logger.info(f"Result: {result_str}")
            self.test_results[tool_name] = result_str
            
            return result_str
            
        except Exception as e:
            import traceback
            error_details = {
                'error_type': type(e).__name__,
                'error_message': str(e),
                'traceback': traceback.format_exc()
            }
            error_msg = f"Error ({error_details['error_type']}): {error_details['error_message']}"
            
            self.logger.error(f"❌ Tool execution failed: {error_msg}")
            self.logger.debug(f"Full traceback: {error_details['traceback']}")
            
            # Store the error in test results for export
            self.test_results[tool_name] = error_msg
            
            return error_msg

    async def _generate_tool_args(self, tool_name):
        """Generate arguments dynamically based on tool schema"""
        try:
            llm = LLM()
            tool = self.available_tools[tool_name]
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
    
    # Example blueprint structure - modify this according to your needs
    example_blueprint = {
        "nodes": ["email_node", "colleagues", "finish"],
        "edges": [
            ("email_node", "colleagues"),
            ("colleagues", "finish")
        ],
        "node_tools": {
            "email_node": ["microsoft_mail_send_email_as_user"]
        },
        "conditional_edges": {
            "colleagues": {
                "next_tool": "email_node",
                "next_step": "finish",
                "retry_same": "email_node"
            }
        }
    }
    
    test = Test(
        blueprint=example_blueprint,
        secret_name="test_",
        user_email="amir@m3labs.co.uk",
        recipient="info@m3labs.co.uk",
        task_description="Send a professional email notification about the latest M3 Labs product updates to stakeholders",
        agent_run_id=None,
        log_manager=log_manager
    )
    
    test.logger.info("Starting Blueprint-based Tool Tests")
    
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