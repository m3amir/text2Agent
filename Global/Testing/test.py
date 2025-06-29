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
        
        # Initialize logging (disable console output)
        self.logger = setup_logging(user_email, "Test_System", log_manager, enable_console=False)
        self.logger.info(f"Initializing Test System - Secret: {secret_name}, Task: {task_description}")
        
        self.test_results = {}
        self.tool_questions = {}
        self.previous_tool_results = {}  # Track results from previous tools for context
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
        
        # Return unique tools while preserving order
        return list(dict.fromkeys(all_tools))

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
        self.previous_tool_results.clear()  # Clear context for next blueprint
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
                
                # Create a more focused prompt that requests only a single question
                focused_prompt = self.prompt_warehouse.get_prompt("focus").format(
                    task_description=self.task_description,
                    tool_name=tool_name,
                    tool_description=tool_description
                )
                
                response = llm.get_model().invoke(focused_prompt)
                raw_question = response.content.strip()
                
                # Extract just the core question from the response
                question = self._extract_core_question(raw_question)
            
            self.tool_questions[tool_name] = question
            self.logger.info(f"Generated question for {tool_name}: {question}")
            

            
        except Exception as e:
            self.logger.error(f"Error generating question for {tool_name}: {e}")
            self.tool_questions[tool_name] = f"How should the {tool_name} tool be tested for the task: {self.task_description}?"

    def _extract_core_question(self, raw_response):
        """Extract the core question from LLM response, removing commentary and formatting"""
        import re
        
        try:
            # Remove common formatting and commentary patterns
            lines = raw_response.split('\n')
            question_candidates = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                # Skip obvious commentary lines
                if line.startswith(('Certainly!', 'Here\'s', 'Testing Question:', '**', 'Scenarios to Test:', 'The question')):
                    continue
                    
                # Skip numbered lists
                if re.match(r'^\d+\.', line):
                    continue
                    
                # Skip bullet points
                if line.startswith(('-', '*', '•')):
                    continue
                    
                # Look for lines that end with question marks
                if line.endswith('?'):
                    # Remove any markdown formatting
                    clean_line = re.sub(r'\*\*([^*]+)\*\*', r'\1', line)  # Remove **bold**
                    clean_line = re.sub(r'`([^`]+)`', r'\1', clean_line)  # Remove `code`
                    clean_line = clean_line.strip('"\'')  # Remove quotes
                    question_candidates.append(clean_line)
            
            # Return the first good question found, or the first line if no question marks
            if question_candidates:
                return question_candidates[0]
            else:
                # Fallback: return the first substantial line
                for line in lines:
                    line = line.strip()
                    if len(line) > 20 and not line.startswith(('Certainly!', 'Here\'s', '**')):
                        return line
                        
                # Ultimate fallback
                return raw_response.split('\n')[0].strip()
                
        except Exception as e:
            self.logger.warning(f"Error extracting core question: {e}")
            return raw_response.strip()

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
            
            # Store raw result for use by subsequent tools
            self.previous_tool_results[tool_name] = {
                'raw_result': result,
                'formatted_result': result_str,
                'tool_args': args
            }
            

            
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
            
            tool_description = self._get_tool_description(tool)
            tool_schema = self._get_tool_schema(tool)
            
            # DEBUG: Check tool's args_schema after our modification
            self.logger.info(f"🔍 DEBUG - Tool's args_schema after _get_tool_schema: {getattr(tool, 'args_schema', 'No args_schema')}")
            
            # Check if the tool has a proper schema before binding
            if not tool_schema or not tool_schema.get('properties'):
                self.logger.warning(f"⚠️ Tool {tool_name} has no valid schema - this may cause argument generation to fail")
                self.logger.info(f"🔍 DEBUG - Tool attributes: {dir(tool)}")
                if hasattr(tool, 'func'):
                    self.logger.info(f"🔍 DEBUG - Tool func: {tool.func}")
                    if hasattr(tool.func, '__annotations__'):
                        self.logger.info(f"🔍 DEBUG - Tool func annotations: {tool.func.__annotations__}")
            
            bound_model = llm.get_model().bind_tools([tool])
            
            today = datetime.now().strftime("%Y-%m-%d")
            tool_question = self.tool_questions.get(tool_name, f"How should the {tool_name} tool be tested effectively?")
            
            # Build context from previous tool results
            previous_context = self._build_previous_context()
            
            # DEBUG: Log the extracted information
            self.logger.info(f"🔍 DEBUG - Tool description: {tool_description}")
            self.logger.info(f"🔍 DEBUG - Tool schema: {tool_schema}")
            self.logger.info(f"🔍 DEBUG - Previous context: {previous_context}")
            
            prompt = self.prompt_warehouse.get_prompt("arguments").format(
                tool_name=tool_name,
                tool_description=tool_description,
                tool_question=tool_question,
                user_email=self.user_email,
                recipient=self.recipient,
                today=today,
                previous_context=previous_context
            )
            
            # DEBUG: Log the formatted prompt
            self.logger.info(f"🔍 DEBUG - Formatted prompt ==========>>>>>>>>>>>>>>> {prompt}")
            
            response = bound_model.invoke(prompt)
            
            # DEBUG: Log the LLM response
            self.logger.info(f"🔍 DEBUG - LLM response type: {type(response)}")
            self.logger.info(f"🔍 DEBUG - LLM response content: {response.content if hasattr(response, 'content') else 'No content'}")
            self.logger.info(f"🔍 DEBUG - LLM response hasattr tool_calls: {hasattr(response, 'tool_calls')}")
            if hasattr(response, 'tool_calls'):
                self.logger.info(f"🔍 DEBUG - Tool calls: {response.tool_calls}")
                if response.tool_calls:
                    self.logger.info(f"🔍 DEBUG - First tool call: {response.tool_calls[0]}")
            
            args = response.tool_calls[0].get('args', {}) if hasattr(response, 'tool_calls') and response.tool_calls else {}
            

            
            # If LLM generates arguments, use them
            if args:
                self.logger.info(f"✅ LLM generated args successfully: {args}")
                return args
            else:
                self.logger.warning(f"⚠️ LLM did not generate any arguments for {tool_name}")
                
                # FALLBACK: Generate reasonable default arguments based on tool schema
                fallback_args = self._generate_fallback_args(tool_name, tool_schema, previous_context)
                if fallback_args:
                    self.logger.info(f"🔄 Using fallback arguments: {fallback_args}")
                    return fallback_args
                
                return {}
                
        except Exception as e:
            self.logger.error(f"Error generating args for {tool_name}: {e}")
            return {}

    def _generate_fallback_args(self, tool_name: str, tool_schema: dict, previous_context: str) -> dict:
        """Generate fallback arguments when LLM fails to generate tool calls"""
        try:
            fallback_args = {}
            properties = tool_schema.get('properties', {})
            
            for param_name, param_info in properties.items():
                param_type = param_info.get('type', 'string')
                description = param_info.get('description', '')
                
                # Generate fallback values based on parameter name and type
                if param_name.lower() == 'file_id':
                    # Try to extract file_id from previous context
                    if 'file IDs' in previous_context and 'Use these exact file IDs' in previous_context:
                        import re
                        file_ids = re.findall(r"'([^']+)'", previous_context)
                        if file_ids:
                            fallback_args[param_name] = file_ids[0]
                        else:
                            fallback_args[param_name] = "test-file-id-123"
                    else:
                        fallback_args[param_name] = "test-file-id-123"
                
                elif param_name.lower() == 'query':
                    # Use task description or default query
                    if self.task_description and 'xen' in self.task_description.lower():
                        fallback_args[param_name] = "xen project"
                    else:
                        fallback_args[param_name] = "test query"
                
                elif param_name.lower() == 'run_id':
                    # Generate a test run ID
                    from datetime import datetime
                    fallback_args[param_name] = f"test_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                
                elif param_name.lower() in ['email', 'user_email', 'sender_email']:
                    fallback_args[param_name] = self.user_email
                
                elif param_name.lower() in ['recipient', 'recipients']:
                    fallback_args[param_name] = [self.recipient] if param_type == 'array' else self.recipient
                
                elif param_name.lower() == 'subject':
                    fallback_args[param_name] = f"Test Subject - {tool_name}"
                
                elif param_name.lower() == 'body':
                    fallback_args[param_name] = f"Test body content for {tool_name}"
                
                elif param_name.lower() in ['file_type', 'filetype']:
                    fallback_args[param_name] = "docx"
                
                elif param_type == 'string':
                    fallback_args[param_name] = f"test_{param_name}"
                
                elif param_type == 'integer':
                    fallback_args[param_name] = 10
                
                elif param_type == 'boolean':
                    fallback_args[param_name] = False
                
                elif param_type == 'array':
                    fallback_args[param_name] = [f"test_{param_name}_item"]
            
            # Only return fallback args if we have at least the required parameters
            required_params = tool_schema.get('required', [])
            if required_params:
                missing_required = [p for p in required_params if p not in fallback_args]
                if missing_required:
                    self.logger.warning(f"⚠️ Missing required parameters for fallback: {missing_required}")
                    return {}
            
            if fallback_args:
                self.logger.info(f"✅ Generated fallback args for {tool_name}: {fallback_args}")
                return fallback_args
            
        except Exception as e:
            self.logger.error(f"Error generating fallback args: {e}")
            
        return {}
    
    def _build_previous_context(self):
        """Build context string from previous tool results for use in argument generation"""
        if not self.previous_tool_results:
            return "No previous tool results available."
        
        context_parts = []
        context_parts.append("Previous tool results that can be used for context:")
        
        for tool_name, result_data in self.previous_tool_results.items():
            context_parts.append(f"\n--- {tool_name.upper()} RESULT ---")
            context_parts.append(f"Arguments used: {result_data['tool_args']}")
            context_parts.append(f"Result: {result_data['formatted_result']}")
            
            # Extract useful data for subsequent tools
            raw_result = result_data['raw_result']
            if isinstance(raw_result, str):
                try:
                    import json
                    parsed_result = json.loads(raw_result)
                    if isinstance(parsed_result, dict):
                        # Look for common patterns that subsequent tools might need
                        if 'files' in parsed_result and parsed_result['files']:
                            files = parsed_result['files']
                            context_parts.append(f"Available files: {files}")
                            # Extract file IDs specifically for download tools
                            file_ids = [f"'{file.get('id')}'" for file in files if file.get('id')]
                            if file_ids:
                                context_parts.append(f"🎯 IMPORTANT - Use these exact file IDs for download: {', '.join(file_ids)}")
                        if 'file_id' in parsed_result:
                            context_parts.append(f"File ID available: {parsed_result['file_id']}")
                        if 'drive_name' in parsed_result:
                            context_parts.append(f"Drive name: {parsed_result['drive_name']}")
                except:
                    pass  # If parsing fails, just use the formatted result
            
        return "\n".join(context_parts)
    
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
        """Extract tool input schema dynamically from tool description"""
        self.logger.info(f"🔍 DEBUG - Starting schema extraction for tool: {tool.__class__.__name__}")
        
        try:
            # First try built-in schema methods
            if hasattr(tool, 'get_input_jsonschema'):
                try:
                    schema = tool.get_input_jsonschema()
                    if schema and schema.get('properties'):
                        self.logger.info(f"🔍 DEBUG - Found schema via get_input_jsonschema: {schema}")
                        return schema
                except Exception as e:
                    self.logger.info(f"🔍 DEBUG - get_input_jsonschema failed: {e}")
            
            if hasattr(tool, 'get_input_schema'):
                try:
                    schema = tool.get_input_schema()
                    if schema and hasattr(schema, 'model_json_schema'):
                        json_schema = schema.model_json_schema()
                        if json_schema and json_schema.get('properties'):
                            self.logger.info(f"🔍 DEBUG - Found schema via get_input_schema: {json_schema}")
                            return json_schema
                except Exception as e:
                    self.logger.info(f"🔍 DEBUG - get_input_schema failed: {e}")
            
            # Check if args_schema already has properties
            if hasattr(tool, 'args_schema') and tool.args_schema:
                schema = tool.args_schema
                if schema.get('properties'):
                    self.logger.info(f"🔍 DEBUG - Found non-empty args_schema: {schema}")
                    return schema
                else:
                    self.logger.info(f"🔍 DEBUG - args_schema is empty: {schema}")
            
            # GENERIC APPROACH: Parse tool description to extract schema
            self.logger.info("🔧 Attempting to parse schema from tool description")
            description = self._get_tool_description(tool)
            
            if description:
                parsed_schema = self._parse_schema_from_description(description)
                if parsed_schema and parsed_schema.get('properties'):
                    self.logger.info(f"✅ Successfully parsed schema from description: {parsed_schema}")
                    
                    # CRITICAL: Update the tool's args_schema so bind_tools() uses it
                    if hasattr(tool, 'args_schema'):
                        tool.args_schema = parsed_schema
                        self.logger.info("✅ Updated tool.args_schema with parsed schema")
                    
                    return parsed_schema
            
            # Try function signature as last resort
            if hasattr(tool, 'func') and tool.func:
                self.logger.info(f"🔍 DEBUG - Extracting schema from function signature")
                import inspect
                sig = inspect.signature(tool.func)
                schema = {
                    "type": "object",
                    "properties": {param.name: {"type": str(param.annotation.__name__ if param.annotation != inspect.Parameter.empty else "string")} 
                                 for param in sig.parameters.values() if param.name != 'self'},
                    "required": [param.name for param in sig.parameters.values() 
                               if param.name != 'self' and param.default == inspect.Parameter.empty]
                }
                if schema.get('properties'):
                    self.logger.info(f"🔍 DEBUG - Generated schema from function: {schema}")
                    return schema
                
        except Exception as e:
            self.logger.error(f"Error extracting tool schema: {e}")
            
        self.logger.warning("🚨 No schema found, returning empty dict")
        return {}

    def _parse_schema_from_description(self, description):
        """Parse parameter schema from tool description text"""
        import re
        
        try:
            # Look for Args: section in description
            args_match = re.search(r'Args:\s*(.*?)(?=Returns:|$)', description, re.DOTALL | re.IGNORECASE)
            if not args_match:
                self.logger.info("🔍 No Args section found in description")
                return {}
            
            args_text = args_match.group(1).strip()
            self.logger.info(f"🔍 Found Args section: {args_text[:200]}...")
            
            # Parse individual parameters
            # Pattern: param_name (type, optional): description
            param_pattern = r'(\w+)\s*\(([^)]+)\):\s*([^\n]+)'
            matches = re.findall(param_pattern, args_text)
            
            if not matches:
                self.logger.info("🔍 No parameter patterns found")
                return {}
            
            properties = {}
            required = []
            
            for param_name, type_info, param_desc in matches:
                param_name = param_name.strip()
                type_info = type_info.strip().lower()
                param_desc = param_desc.strip()
                
                # Determine if required (not marked as optional)
                is_optional = 'optional' in type_info
                if not is_optional:
                    required.append(param_name)
                
                # Determine type
                if 'str' in type_info:
                    param_type = "string"
                elif 'int' in type_info:
                    param_type = "integer"
                elif 'bool' in type_info:
                    param_type = "boolean"
                elif 'list' in type_info or 'array' in type_info:
                    param_type = "array"
                    properties[param_name] = {
                        "type": param_type,
                        "items": {"type": "string"},
                        "description": param_desc
                    }
                    continue
                else:
                    param_type = "string"  # Default to string
                
                properties[param_name] = {
                    "type": param_type,
                    "description": param_desc
                }
            
            schema = {
                "type": "object",
                "properties": properties,
                "required": required
            }
            
            self.logger.info(f"🔍 Parsed {len(properties)} parameters, {len(required)} required")
            return schema
            
        except Exception as e:
            self.logger.error(f"Error parsing schema from description: {e}")
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

    async def analyze_question_coverage(self):
        """Use LLM to analyze whether each question was answered by the tool results"""
        try:
            from Global.llm import LLM
            llm = LLM()
            
            analysis_results = {}
            

            
            for tool_name in self.tool_questions.keys():
                question = self.tool_questions.get(tool_name, "")
                result = self.test_results.get(tool_name, "")
                
                if not question or not result:
                    continue
                
                # Create analysis prompt
                analysis_prompt = self.prompt_warehouse.get_prompt("analysis").format(
                    question=question,
                    result=result
                )
                
                try:
                    response = llm.get_model().invoke(analysis_prompt)
                    analysis_text = response.content.strip()
                    
                    # Try to parse the JSON response
                    try:
                        analysis_json = json.loads(analysis_text)
                        analysis_results[tool_name] = {
                            "question": question,
                            "tool_result": result,
                            "question_answered": analysis_json.get("question_answered", False),
                            "explanation": analysis_json.get("explanation", "Analysis failed"),
                            "relevant_information": analysis_json.get("relevant_information", "None")
                        }
                    except json.JSONDecodeError:
                        # Fallback if LLM doesn't return valid JSON
                        analysis_results[tool_name] = {
                            "question": question,
                            "tool_result": result,
                            "question_answered": "error" not in result.lower(),
                            "explanation": "LLM analysis failed, using simple error detection",
                            "relevant_information": "Analysis unavailable"
                        }
                    

                    
                except Exception as e:
                    self.logger.error(f"Error analyzing {tool_name}: {e}")
                    analysis_results[tool_name] = {
                        "question": question,
                        "tool_result": result,
                        "question_answered": False,
                        "explanation": f"Analysis error: {str(e)}",
                        "relevant_information": "Analysis failed"
                    }
            

            
            return analysis_results
            
        except Exception as e:
            self.logger.error(f"Error in question coverage analysis: {e}")
            return {}

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

    async def export_results_with_analysis(self, filename="comprehensive_test_results.json"):
        """Export test results with LLM analysis of question coverage"""
        try:
            # Get the question coverage analysis
            analysis_results = await self.analyze_question_coverage()
            
            filepath = self.test_results_folder / filename
            
            with open(filepath, 'w') as f:
                json.dump({
                    'agent_run_id': self.agent_run_id,
                    'secret_name': self.secret_name,
                    'user_email': self.user_email,
                    'recipient': self.recipient,
                    'task_description': self.task_description,
                    'tool_questions': self.tool_questions,
                    'results': self.test_results,
                    'question_coverage_analysis': analysis_results,
                    'summary': {
                        'total_tools_tested': len(self.test_results),
                        'questions_answered': sum(1 for r in analysis_results.values() if r.get("question_answered", False)),
                        'questions_not_answered': sum(1 for r in analysis_results.values() if not r.get("question_answered", False)),
                        'coverage_percentage': round((sum(1 for r in analysis_results.values() if r.get("question_answered", False)) / len(analysis_results) * 100) if analysis_results else 0, 2)
                    }
                }, f, indent=2)
            self.logger.info(f"Comprehensive results with analysis exported locally: {filepath.absolute()}")
            
            try:
                s3_path = f"cognito/{self.user_email}/Data/{self.agent_run_id}/{filename}"
                metadata = {'category': 'comprehensive_test_results', 'agent_run_id': self.agent_run_id, 'secret_name': self.secret_name}
                
                if save_file_to_s3(str(filepath.absolute()), self.user_email, s3_path, metadata):
                    self.logger.info(f"Comprehensive results also saved to S3 under {s3_path}")
                else:
                    self.logger.warning("S3 upload failed, but local file saved successfully")
            except Exception as s3_error:
                self.logger.warning(f"S3 upload failed: {s3_error}, but local file saved successfully")
                
        except Exception as e:
            self.logger.error(f"Failed to export comprehensive results: {e}")



async def main():
    """Main test execution"""
    log_manager = LogManager("amir@m3labs.co.uk") if LogManager else None
    
    # Example blueprint structure - modify this according to your needs
    example_blueprints = [
    {
        "nodes": ["search_node", "colleagues", "finish"],
        "edges": [
            ("search_node", "colleagues"),
            ("colleagues", "finish")
        ],
        "node_tools": {
            "search_node": ["microsoft_sharepoint_search_files", "microsoft_sharepoint_download_and_extract_text"]
        },
        "conditional_edges": {
            "colleagues": {
                "next_tool": "search_node",
                "next_step": "finish",
                "retry_same": "search_node"
            }
        }
    }]
    

    
    all_results = {}
    
    for i, blueprint in enumerate(example_blueprints, 1):

        
        # Determine task description based on blueprint tools
        all_tools = []
        for tools in blueprint.get('node_tools', {}).values():
            if isinstance(tools, list):
                all_tools.extend(tools)
            elif isinstance(tools, str):
                all_tools.append(tools)
        
        if any('mail' in tool.lower() for tool in all_tools):
            task_description = "Send a professional email notification about the latest M3 Labs product updates to stakeholders"
        elif any('sharepoint' in tool.lower() or 'search' in tool.lower() for tool in all_tools):
            task_description = "find sow for our new xen project"
        else:
            task_description = "Test the tools in this blueprint to ensure they work correctly"
        
        test = Test(
            blueprint=blueprint,
            secret_name="test_",
            user_email="amir@m3labs.co.uk",
            recipient="info@m3labs.co.uk",
            task_description=task_description,
            agent_run_id=f"blueprint_{i}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            log_manager=log_manager
        )
        
        test.logger.info(f"Starting Blueprint {i} Tests")
        
        try:
            success = await test.test_tools()
            
            if success:
                # Export regular results
                test.export_results(f"blueprint_{i}_test_results.json")
                
                # Export comprehensive results with LLM analysis
                await test.export_results_with_analysis(f"blueprint_{i}_comprehensive_results.json")
                
                test.logger.info(f"✓ Blueprint {i} tests completed successfully!")
            else:
                test.logger.error(f"❌ Blueprint {i} tests failed!")
            
            # Store results for summary
            all_results[f"blueprint_{i}"] = {
                "success": success,
                "results": test.test_results,
                "tools_tested": all_tools
            }
                
        except Exception as e:
            test.logger.error(f"❌ Blueprint {i} failed with exception: {e}")
            all_results[f"blueprint_{i}"] = {
                "success": False,
                "error": str(e),
                "tools_tested": all_tools
            }
        
        finally:
            sync_logs_to_s3(test.logger, test.log_manager, force_current=True)
    
    # Generate comprehensive test results JSON
    test_summary = {
        "timestamp": datetime.now().isoformat(),
        "total_blueprints": len(example_blueprints),
        "successful_blueprints": sum(1 for r in all_results.values() if r.get("success", False)),
        "failed_blueprints": sum(1 for r in all_results.values() if not r.get("success", False)),
        "blueprints": {}
    }
    
    # Add detailed results for each blueprint
    for blueprint_name, result in all_results.items():
        test_summary["blueprints"][blueprint_name] = {
            "success": result.get("success", False),
            "tools_tested": result.get("tools_tested", []),
            "total_tools": len(result.get("tools_tested", [])),
            "error": result.get("error") if not result.get("success", False) else None
        }
    
    # Calculate overall statistics
    all_tool_results = {}
    for blueprint_result in all_results.values():
        if "results" in blueprint_result:
            all_tool_results.update(blueprint_result["results"])
    
    successful_tools = sum(1 for result in all_tool_results.values() if "Error" not in str(result))
    failed_tools = len(all_tool_results) - successful_tools
    
    test_summary["overall_statistics"] = {
        "total_tools_tested": len(all_tool_results),
        "successful_tools": successful_tools,
        "failed_tools": failed_tools,
        "success_rate": round((successful_tools / len(all_tool_results) * 100) if all_tool_results else 0, 2)
    }
    
    # Print the final comprehensive JSON result
    print(json.dumps(test_summary, indent=2, ensure_ascii=False))
    
    return all_results

if __name__ == "__main__":
    asyncio.run(main())