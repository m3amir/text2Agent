import traceback
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../", ".")))
from utils.imports import *
from utils.summarise import summarize_conversation
from Global.States.state import AgentState
from Global.llm import LLM
from Global.domain import Domain
from Prompts.Judge import judge
from Prompts.Tasks import prompt as task_prompt
from Global.Cache.cache import cache
from Global.Pool.colleagues import Colleague
from Global.domain_tools import toolMapper
from Global.guard_mappings import guard_mappings
from langgraph.prebuilt import ToolNode
import asyncio
from datetime import datetime
import time
from langgraph.types import Command, interrupt
from Connectors.MCP_constructor import ToolCategoriser
from pydantic import BaseModel, Field
from guardrails import Guard
from guardrails.types import OnFailAction
from Global.Guardrails.guard import GuardOutput, Guard

class ResponseFormatter(BaseModel):
    """Always use this tool to structure your response to the user."""
    Route: str = Field(description="The formatted response of the connector route")
    Category: str = Field(description="The formatted response of the connector category")

class TerminalFormatter(BaseModel):
    """Always use this tool to structure your response to if a task is completed or not."""
    status: str = Field(description="The status of the task that you are responding to")
    reasoning: str = Field(description="The reasoning for the status of the task that you are responding to. This should be the message that you would like to give to the user.")
    terminal: str = Field(description="The terminal status of the task that you are responding to. This should be the word 'tickets'")

class Agent:
    def __init__(self, criticism, tools, guarded, task_store, tasks_list, config, storage, business_logic, clients, user_email):
        self.criticism = criticism
        self.clients = clients
        self.storage = storage
        self.permissions = guarded
        self.tasks = task_store
        self.task_list = tasks_list
        self._is_running = True
        self.memory = MemorySaver()
        self.loggers = None
        self.init_logger()
        self.app = None
        self.config = config
        self.summary = None
        self.cache = cache()
        self.task_trace = {}
        self.business_logic = business_logic
        self.pool_of_colleagues = Colleague()
        self.on_lunch = None
        self.history = {}
        self.domain_mapper = Domain(MCP_tools={"server-filesystem": "This is a tool that allows you to interact with the file system.", "server-postgres": "This is a tool that allows you to interact with the postgres database."})
        self.credentials = {}
        self.task_loop = None
        self.user_email = user_email
        self.tool_calls = {}
        self.tool_nodes = {}
        self.categorized_tool_lists = {}
        self.guard = Guard().use(
            GuardOutput(threshold=80, on_fail=OnFailAction.FIX),
        )
        
    async def initialize(self, tools):
        """Async initialization of tools and workflow setup."""
        await self.init_tools(tools)
        self.setup_workflow()
        return self

    @property
    def is_running(self):
        """Get the running state of the agent."""
        return self._is_running
        
    @is_running.setter
    def is_running(self, value):
        """Set the running state of the agent."""
        if not isinstance(value, bool):
            print(f"Warning: is_running must be a boolean, got {type(value)} - {value}")
            # Convert to boolean
            value = bool(value)
        print(f"Setting agent.is_running to {value}")
        self._is_running = value

    def init_logger(self):
        os.makedirs("Logs/Back-end/", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.loggers = {}

        for task in self.task_list:
            backend_logger = logging.getLogger(task[-10:])
            backend_logger.setLevel(logging.DEBUG)
            backend_logger.propagate = False
            log_file_path = os.path.join("Logs/Back-end/", f"backend_{timestamp}_{task[-10:]}.log")
            file_handler = logging.FileHandler(log_file_path)
            file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
            backend_logger.addHandler(file_handler)
            self.loggers[task] = backend_logger

    def log(self, *messages, level="info", task_id=None):
        # Log to all task logs if no specific task_id is provided

        if task_id is None:
            loggers_to_use = self.loggers
        else:
            loggers_to_use = {task_id: self.loggers.get(task_id)}
        
        for logger_id, logger in loggers_to_use.items():
            if logger:
                for message in messages:
                    if level == 'info':
                        logger.info(message)
                    elif level == 'error':
                        logger.error(message)
                    elif level == 'warning':
                        logger.warning(message)
                    else:
                        logger.debug(f"Unknown log level: {level}. Message: {message}")

    @classmethod
    async def create(cls, criticism, tools, guarded, tasks, config, storage_layer, business_logic, clients, user_email):
        """Create an Agent instance, fetch tasks asynchronously."""
        try:
            # Check if tasks is properly initialized
            if not tasks or not hasattr(tasks, 'get_tasks'):
                print("Warning: tasks object doesn't have get_tasks method. Using empty dict for tasks_data.")
                tasks_data = {}
            else:
                try:
                    tasks_data = await tasks.get_tasks()
                    # Ensure tasks_data is a dictionary even if get_tasks returns a list
                    if isinstance(tasks_data, list):
                        print("Warning: get_tasks returned a list instead of a dictionary. Converting to dict.")
                        tasks_data = {str(i): task for i, task in enumerate(tasks_data)}
                except Exception as e:
                    print(f"Error calling get_tasks: {e}. Using empty dict.")
                    tasks_data = {}
            
            # Create the instance using regular __init__
            instance = cls(criticism, tools, guarded, tasks, tasks_data, config, storage_layer, business_logic, clients, user_email)
            # Initialize the instance asynchronously
            await instance.initialize(tools)
            return instance
        except Exception as e:
            print(f"Error creating agent instance: {e}")
            return None
        
    def get_runner(self, tools):
        runner = LLM(
                profile_name="prof",
                model_kwargs={"temperature": 0.5, "max_tokens": 4096, "top_p": 0.2},
            ).get_model()
        if tools:
            runner.bind_tools(tools)
            print("runner.bind_tools(tools) -->  ", runner)
            return runner
        else:
            return runner
        
    async def init_tools(self, tools):
        """Initialize and categorize tools based on their names."""
        try:
            categoriser = ToolCategoriser(connectors=["server-filesystem", "server-postgres"])
            MCP_tools = await categoriser.categorize()
            # Initialize tool categories
            self.tool_groups = {
                "admin": "admin_tools",
                "retrieval": "retrieval_tools",
                "creation": "creation_tools",
            }
            
            # Initialize categorized tool lists
            self.categorized_tool_lists = {}
            
            # Initialize permissions and domains
            self._init_domains(tools)
            #use the clients
            # Process tools if they're class definitions
            for tool in tools:
                
                # Initialize the dictionary for this tool's methods
                self.categorized_tool_lists[tool.__name__] = {
                    "admin": [],
                    "retrieval": [],
                    "creation": []
                }

                tool_methods = tool.get_all_tools()[0]
                # print("tool_methodsssss", tool_methods)
                if not tool_methods:
                    print("No tools found for ", tool.__name__)
                    continue
                                
                # Categorize each method based on its name containing admin, retrieval, or creation
                for method in tool_methods:
                    name = method.name.lower()                    
                    # Check if method name contains any of the category names
                    if 'admin' in name:
                        self.categorized_tool_lists[tool.__name__]["admin"].append((name, method))
                    elif 'retrieval' in name:
                        self.categorized_tool_lists[tool.__name__]["retrieval"].append((name, method))
                    elif 'creation' in name:
                        self.categorized_tool_lists[tool.__name__]["creation"].append((name, method))
                    else:
                        # If no category found in name, default to retrieval
                        self.categorized_tool_lists[tool.__name__]["retrieval"].append((name, method))
                        
            self.categorized_tool_lists.update(MCP_tools)
            self.tools_mapper = toolMapper(self.categorized_tool_lists)
        except Exception as e:
            print(f"Error in init_tools: {e}")

    def _init_domains(self, tools):
        """Initialize domain-specific tool groups and connectors."""
        try:
            # Get list of connectors from Tools directory
            tools_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'Tools'))
            if not os.path.exists(tools_dir):
                print(f"Tools directory not found at {tools_dir}")
                self.connector_tools = {}
                return
                
            # Get connectors from directory structure
            connectors = [
                d for d in os.listdir(tools_dir) 
                if os.path.isdir(os.path.join(tools_dir, d)) and not d.startswith('__')
            ]            
            # Initialize connector_tools dictionary
            self.connector_tools = {}
            
            # Initialize structure for each connector
            for connector in connectors:
                connector = connector.lower()
                self.connector_tools[connector] = {
                    "admin": [],
                    "retrieval": [],
                    "creation": []
                }
            
            # Initialize categorized_tool_lists
            self.categorized_tool_lists = {}
            
            # Process tools if they're class definitions rather than instances
            processed_tools = []
            for tool in tools:
                if hasattr(tool, 'connector_tools'):
                    self.categorized_tool_lists.update(tool.connector_tools)

            self.tools_mapper = toolMapper(self.categorized_tool_lists)

        except Exception as e:
            print("Encountered error in init_tools: ", e)

    def get_permission(self, tool_name):
        for connector, tools in guard_mappings.items():
            if tool_name in tools:
                return connector, tools[tool_name]
        return None, None

    def update_prompt(self, task):
        """Update the prompt and task list based on new tasks."""
        self.log("Updating prompt with new tasks.", level="info")
        self.messages = self._generate_messages(task)

    def _generate_messages(self, task):
        self.log(f"Generating messages for tasks: {task}", level="info")
        return [
            ("system", master_prompts.tasks_executer_prompt),
            (
                "human",
                f"""Begin completing my tasks. My username is {self.user_email}. You are currently assisting me. Sign off any communications with my name. Emails should be in plain text.\n\nTasks:\n{str(task)}\n\nDo not output any commentary or explanations. Your first step should be to output a single word corresponding to the best tool category you need to begin your tasks, if you have not already completed all your tasks or there are tasks available.""",
            ),
        ]

    async def update_tickets(self, state):
        """This updates the tasks that were assigned to you when they have been completed."""
        try:
            task_id = state.get('task_id')
            last_message = state.get('messages', [])[-1]
            if last_message.content:
                last_message = self.parse_response(last_message)
                output_message = self.guard.validate(last_message)
            elif not last_message.content and last_message.tool_calls:
                last_message = TerminalFormatter.model_validate(last_message.tool_calls[0]['args'])
                terminal = {}
                terminal[task_id] = {}
                terminal[task_id]['status'] = last_message.status
                terminal[task_id]['reasoning'] = last_message.reasoning
                terminal[task_id]['terminal'] = last_message.terminal
                last_message = terminal
                self.task_list, results = await self.tasks.update_tasks(terminal)
                if results:
                    self.task_list = results
                    self.log(f"Task list successfully updated with {len(results)} tasks.", level="info", task_id=task_id)
                    return state
                else:
                    print("Update returned empty results")
                    self.log(f"Task update returned empty results.", level="warning", task_id=task_id)
                    return state
        except Exception as e:
            self.log(f"Error in update_tickets: {e}", level="error", task_id=task_id)
            print(f"Error in update_tickets: {e}")
            return state
    
    async def connectors(self, state):

        task_id = state.get('task_id')
        self.history[task_id].append(['router'])
        try:
            # Safely get the task by ID with error handling
            if not task_id or task_id not in self.task_list:
                self.log(f"Task ID {task_id} not found in task_list in connectors. Using default task.", level="warning")
                # Use a default empty task if task_id is not found
                task = {'title': 'Task not found', 'description': 'The requested task could not be found.'}
            else:
                task = self.task_list[task_id]
                
            # Format the task for processing
            task_text = task.get('title', '') + '\n\n' + task.get('description', '')            
            # Route the task
            response = await self.domain_mapper.route(state, task_text, 'retrieval, creation, admin')
            state['messages'].append(response)
            return state
            
        except Exception as e:
            self.log(f"Error in connectors method: {e}", level="error", task_id=state.get('task_id'))
            print(f"Error in connectors method: {e}")
            # Return the state unmodified to avoid breaking the workflow
            return state

    async def tool_mapper(self, state):
        task_id = state.get('task_id')
        self.history[task_id].append(['tool_mapper'])
        last_message = state['messages'][-1]
        try:
            # Safely get the task by ID with error handling
            if not task_id:
                self.log(f"Task ID {task_id} not found in task_list in tool_mapper. Using default task.", level="warning")
                # Use a default empty task if task_id is not found
                task = {'title': 'Task not found', 'description': 'The requested task could not be found.'}
            else:
                task = self.task_list[task_id]

            # Format the task for processing
            task_text = task.get('title', '') + '\n\n' + task.get('description', '')
            
            # Get messages and route the task
            response = await self.tools_mapper.route(state, task_text, 'history')
            if (not last_message.content) and last_message.tool_calls:
                connector_route = ResponseFormatter.model_validate(last_message.tool_calls[0]["args"])
                connector = connector_route.Route.lower()
                category = connector_route.Category.lower()
                state['messages'][-1] = AIMessage(content="Connector: " + connector + " Category: " + category)
            
            state['messages'].append(response)
            return state
            
        except Exception as e:
            self.log(f"Error in tool_mapper method: {e}", level="error", task_id=state.get('task_id'))
            print(f"Error in tool_mapper method: {e}")
            # Return the state unmodified to avoid breaking the workflow
            return state

    def setup_workflow(self):
        """Set up the workflow with nodes and edges."""
        self.log("Setting up the workflow.", "info")
        workflow = StateGraph(AgentState)

        try:
            # Create ToolNodes for each connector-category pair
            connector_category_routes = {}
            
            for tool_name, categories in self.categorized_tool_lists.items():
                for category, tools in categories.items():
                    if tools:  # Only create nodes for non-empty tool lists
                        node_name = f"{tool_name.lower()}_{category}"
                        # Create ToolNode with the tools list
                        tool_node = ToolNode(
                            tools=[tool[1] for tool in tools],  # Extract the actual tool objects
                        )
                        # Store the node in the instance
                        self.tool_nodes[node_name] = tool_node
                        # Add to routes for conditional edges
                        connector_category_routes[node_name] = node_name
                        workflow.add_node(node_name, tool_node)
                        workflow.add_edge(node_name, "revise")
                        self.log(f"Added node '{node_name}' to workflow", "info")
            
            # Add basic nodes
            workflow.add_node("agent", self.router)
            workflow.add_node("connector", self.connectors)
            workflow.add_node("update_tickets", self.update_tickets)
            workflow.add_node("revise", self.revision)
            workflow.add_node("tool_mapper", self.tool_mapper)
            workflow.add_node("execute_tool", self.execute_tool)
            workflow.add_node("HIL", self.HIL)
            self.log("Nodes added to the workflow.", "info")

            # Add basic edges with proper flow
            workflow.add_edge(START, "agent")
            workflow.add_edge("agent", "connector")
            workflow.add_edge("connector", "tool_mapper")
            # Add edge from tool_mapper to revise to make revise node reachable
            workflow.add_conditional_edges("tool_mapper", self.route_after_llm)
            # workflow.add_edge("human_review_node", "execute_tool")
            workflow.add_edge("HIL", "execute_tool")
            workflow.add_edge("execute_tool", "revise")
            self.log("Edges added to the workflow.", "info")
            
            workflow.add_conditional_edges(
                "revise",
                self.revision_mapper,
                {
                    "tools": "tool_mapper",
                    "tickets": "update_tickets",
                    "agent": "connector",
                    "end": END
                }
            )
            self.log("Conditional edges added to the workflow.", "info")

            workflow.add_edge("update_tickets", END)
            self.log("Edge from 'update_tickets' to END added.", "info")

            # Compile with memory checkpointer for interrupt support
            self.app = workflow.compile(checkpointer=self.memory)
            self.log("Workflow successfully compiled.", "info")

        except Exception as e:
            self.log(f"Error during workflow setup: {e}", "error")
            print("Encountered error in setup_workflow: ", e)
            raise
    
    def check_if_insufficient(self, state, last_message):
        if isinstance(last_message, dict):
            # Convert all keys to lowercase in a new dictionary
            last_message = {k.lower(): v for k, v in last_message.items()}
            if last_message.get('terminal', '').lower() == 'tickets':
                return True
            if last_message.get('status', '').lower() == 'insufficient':
                return True

    async def revision_mapper(self, state):
        print("Checking if done..............")
        # if state['remaining_steps'] <= 10:
        #     return 'end' bring backkkkkkkkkkk
        task_id = state['task_id']
        messages = state.get("messages", [])
        last_message = messages[-1] if messages else None
        if last_message.content:
            last_message = self.parse_response(last_message)
        elif not last_message.content and last_message.tool_calls:
            last_message = TerminalFormatter.model_validate(last_message.tool_calls[0]['args'])
            terminal = {}
            terminal['status'] = last_message.status
            terminal['reasoning'] = last_message.reasoning
            terminal['terminal'] = last_message.terminal
            last_message = terminal
            state['messages'][-1] = AIMessage(content="Status: " + last_message['status'] + " Reasoning: " + last_message['reasoning'] + " Terminal: " + last_message['terminal'])
        if self.check_if_insufficient(state, last_message):
            self.log("Terminal found in response: 'tickets'", "info", task_id=task_id)
            print("going to tickets....... ")
            return 'tickets'
        self.log(f"Last message: {last_message}", "info", task_id=task_id)
        last_message = messages[-1]
        if type(last_message) == AIMessage and last_message.tool_calls:
            tool_name = last_message.tool_calls[0]['name']
            self.log(f"Tool name found: {tool_name}", "info", task_id=task_id)
            
            # Build a mapping of all tools to their connector-category nodes
            tool_routes = {'tickets': 'tickets'}  # Start with tickets route
            
            for connector, categories in self.connector_tools.items():
                for category, tools_list in categories.items():
                    node_name = f"{connector}_{category}"
                    if hasattr(self, f"{node_name}_by_name"):
                        # Get the tool names from the by_name dictionary
                        tool_names = getattr(self, f"{node_name}_by_name").keys()
                        # Add mapping for each tool name to this node
                        for name in tool_names:
                            tool_routes[name] = 'tools'  # Route back to tool_mapper
            
            route = tool_routes.get(tool_name, 'agent')
            self.log(f"Route mapped for tool {tool_name}: {route}", "info", task_id=task_id)
            return route
            
        self.log("no explicit route found, defaulting to 'agent'", "info", task_id=task_id)
        return 'agent'

    async def revision(self, state: list):
        task_id = state['task_id']
        self.history[task_id].append(['revision'])
        self.log("Entering revision method.", "info", task_id=task_id)
        response = []        
        # Check if the last message is an AIMessage without tool_calls
        if type(state["messages"][-1]) == AIMessage and not hasattr(state["messages"][-1], "tool_calls"):
            self.log("Last message is an AIMessage without tool calls.", "warning", task_id=task_id)
            return state

        self.log("Adding step evaluation messages.", "info", task_id=task_id)

        for _ in range(3):
            state["messages"] += [
                HumanMessage(
                    content="Retrieve all of your previously taken steps to evaluate what type of tool is the next optimal step. Output your steps summaries now..."
                )
            ]
            response = await self.critique(state)
            self.log(f"Critique response: {response}", "info", task_id=task_id)
            try:
                self.log("Validation passed for critique response.", "info", task_id=task_id)
                return state
            except ValidationError as e:
                self.log(f"Validation failed: {repr(e)}", "error", task_id=task_id)
                state["messages"] = state["messages"] + [
                    response,
                    ToolMessage(
                        content=f"{repr(e)}\n\nPay close attention to the function schema.\n\n"
                        + self.validator.schema_json()
                        + " Respond by fixing all validation errors.",
                        tool_call_id=response.tool_calls[0]["id"],
                    ),
                ]

        self.log("Exiting revision method with response.", level="info", task_id=task_id)
        return response

    async def router(self, state):
        task_id = state['task_id']
        self.history[task_id].append(['start'])
        tools = []
        try:
            tools.append(
                StructuredTool.from_function(
                    name="tickets",
                    description="If you have no further tasks to complete, or your task list is empty, you must mark the tasks you have approached as either completed or incomplete using this tool.",
                    coroutine=self.update_tickets,
                )
            )
            self.log(f"Tools prepared: {tools}", level="info", task_id=task_id)
            model = self.get_runner(tools=None)            
            self.log(f"State messages: {state['messages']}", level="info", task_id=task_id)
            response = await model.ainvoke(state["messages"])
            self.log(f"Response: {response}", "info", task_id=task_id)
            state["messages"].append(response)
            if isinstance(response, AIMessage) and response.content in self.tool_groups:
                self.log(f"Response content '{response.content}' is valid and part of tool groups.", level="info", task_id=task_id)
                return state
        except Exception as e:
            self.log(f"An error occurred in the router method: {e}", level="error", task_id=task_id)
        return state

    def parse_response(self, message):
        content = message.content.strip()
        json_start = content.find("```json")
        json_end = content.rfind("```")

        if json_start != -1 and json_end != -1 and json_end > json_start:
            json_string = content[json_start + len("```json"):json_end].strip()
        else:
            json_string = content
        if json_string.startswith("{"):
            try:
                response = json.loads(json_string)
                return response
            except Exception as e:
                return "Unable to parse this message"
        else:
            return json_string

    def get_previous_steps(self, messages):
        
        combined_content = ""
        for message in messages:
            if message.content:
                message_type = message.__class__.__name__
                combined_content += f"{message_type}: {message.content}\n\n"
        return combined_content
    
    async def critique(self, state):
        task_id = state['task_id']
        self.log("Entering critique method.", level="info", task_id=task_id)
        
        try:
            messages = state["messages"]
            # model = self.get_runner(tools=tools)
            model = LLM(
                profile_name="prof",
                model_kwargs={"temperature": 0.1, "max_tokens": 4096, "top_p": 0.3},
            ).get_model().bind_tools([TerminalFormatter])
            self.log(f"Messages after applying cache: {messages}", level="info", task_id=task_id)
            response = await self.criticism.ainvoke(messages)
            self.log(f"Criticism response: {response}", level="info", task_id=task_id)
            
            # Check if response has valid tool_calls with needed arguments
            has_valid_args = False
            try:
                if (isinstance(response, AIMessage) and 
                    not response.content and
                    response.tool_calls and 
                    "args" in response.tool_calls[0] and
                    "steps_summary" in response.tool_calls[0]["args"]):
                    has_valid_args = True
                else:
                    self.log("Response missing valid tool_calls with steps_summary", level="warning", task_id=task_id)
            except (IndexError, KeyError, AttributeError) as e:
                self.log(f"Error validating tool calls: {e}", level="error", task_id=task_id)
            
            if not has_valid_args:
                self.log("Response does not contain valid tool_calls with steps_summary, returning state.", level="info", task_id=task_id)
                return state
            
            # Get args safely now that we've validated
            args = response.tool_calls[0]["args"]
            
            routes = {'admin': 'Tools that manage scheduling, invoicing, emailing or task tracking to streamline daily operations and administrative processes.',
                      'content': 'Tools that assist with generating text, reports, images, video, or designs to create engaging media for various platforms.',
                      'retrieval': 'Tools that gather, search, and retrieve information from databases or the web to provide relevant, up-to-date content or insights.'}
            route_descriptions = "; ".join([f"{route}: {description}" for route, description in routes.items()])
            
            # Check that required keys exist in args
            if "steps_summary" not in args or "ticket" not in args:
                self.log("Missing required args (steps_summary or ticket)", level="error", task_id=task_id)
                state['messages'].append(AIMessage(content=f"Steps Summary: {args['steps_summary']} Ticket: {args['ticket']}"))
                return state
            
            self.summary = args['steps_summary']
            
            # Format message content safely
            try:
                formatted_content = master_prompts.revision.format(
                    route_descriptions=route_descriptions,
                    summary=args["steps_summary"],
                    ticket=args["ticket"]
                )
                state["messages"][-1].content = formatted_content
                state["messages"][-1].content += '\n\n' + task_prompt.task
                self.log("Updated state message content with revision format.", level="info", task_id=task_id)
            except Exception as format_error:
                self.log(f"Error formatting content: {format_error}", level="error", task_id=task_id)
                return state

            # Get reflection
            try:
                reflection = await model.ainvoke(master_prompts.revision.format(
                    route_descriptions=route_descriptions,
                    summary=args["steps_summary"],
                    ticket=args["ticket"]
                ))
                self.log(f"Reflection response: {reflection}", level="info", task_id=task_id)
            except Exception as reflection_error:
                self.log(f"Error getting reflection: {reflection_error}", level="error", task_id=task_id)
                state["messages"].append(response)
                return state
            
            # Update history
            if task_id in self.history:
                self.history[task_id].append(['reflection'])
                self.history[task_id].append(['colleagues'])
            
            # Get recommendation
            try:
                task_info = ""
                if task_id in self.task_list and isinstance(self.task_list[task_id], dict):
                    title = self.task_list[task_id].get('title', '')
                    description = self.task_list[task_id].get('description', '')
                    task_info = f"{title} {description}"
                
                recommendation = await model.ainvoke(judge.system.format(
                    reflection=reflection.content, 
                    colleagues='', 
                    task=task_info
                ))

                if not recommendation.content and recommendation.tool_calls and recommendation.tool_calls[0].get('name') == 'TerminalFormatter':
                    state['messages'].append(response)
                    state['messages'].append(recommendation)
                    summary = summarize_conversation(state)
                    state['summary'] = summary['summary']
                    return state
                self.log(f"Recommendation response: {recommendation.content}", level="info", task_id=task_id)
            except Exception as recommendation_error:
                print("recommendation_error ..... ", recommendation_error)
                self.log(f"Error getting recommendation: {recommendation_error}", level="error", task_id=task_id)
                state["messages"].append(response)
                return state

            # Update state and trace
            summary = summarize_conversation(state)
            state['summary'] = summary['summary']
            state['messages'] = state['messages'].clear()
            state['messages'] = []
            state["messages"].append(recommendation)
            state['messages'].append(AIMessage(content=summary['summary']))

            if task_id not in self.task_trace:
                self.task_trace[task_id] = []
            self.task_trace[task_id].append(recommendation.content)
            self.log("Critique process completed.", level="info", task_id=task_id)
            return state
            
        except Exception as e:
            self.log(f"Unhandled error in critique: {e}", level="error", task_id=task_id)
            print(f"Unhandled error in critique for task {task_id}: {e}")
            # Return state unchanged if there was an error
            return state

    def checkCache(self, state):
        task_id = state['task_id']
        self.log("Entering checkCache method.", level="info", task_id=task_id)

        # id = self.config['configurable']['thread_id']
        id = state['task_id']
        self.log(f"Current state['messages'] length: {len(state['messages'])}", level="info", task_id=task_id)
        
        if len(state['messages']) > 3:
            # state['messages'] = self.cache.countTokens(str(id), state['messages'])
            self.log(f"State after cache countTokens: {state['messages']}", level="info", task_id=task_id)
            return state
        
        self.log("State['messages'] length <= 3, returning without cache update.", level="info", task_id=task_id)
        return state
    
    def format_terminal(self, message):
        object = TerminalFormatter.model_validate(message.tool_calls[0]['args'])
        terminal = {}
        terminal['Status'] = object.status
        terminal['Reasoning'] = object.reasoning
        terminal['Terminal'] = object.terminal
        return terminal
            
    async def start_agent(self, task: dict, config: dict, task_dict):
        try:                
            # Safely get task_id - task is now guaranteed to be a dictionary
            try:
                if not task or not isinstance(task, dict):
                    print(f"Invalid task format: {type(task)}, expected dictionary. Task: {task}")
                    return None
                
                # Get first key as task_id
                task_id = next(iter(task))
                self.task_trace[task_id] = []
                print(f"Starting agent with task_id: {task_id}")
            except Exception as id_error:
                print(f"Error getting task_id: {id_error}, task: {task}")
                return None
                
            self.log(f"Starting agent with task: {task}", level="info", task_id=task_id)
            
            # Validate task
            if not task:
                self.log("No task provided, returning from start_agent.", level="warning", task_id=task_id)
                print(f"Task {task_id} is empty, aborting")
                return None
                
            # Ensure task_id is in task_list with proper completion status
            if task_id not in self.task_list:
                print(f"Task {task_id} not in task_list, adding it now")
                # Extract task data from input and add to task_list
                self.task_list[task_id] = task.get(task_id, {})
            
            # IMPORTANT: Ensure task is marked as not completed until update_tickets processes it
            if task_id in self.task_list and isinstance(self.task_list[task_id], dict):
                # Set to None instead of removing, to preserve other task data
                self.task_list[task_id]['completed'] = None
                print(f"Task {task_id} explicitly marked as not completed (None)")
            print(f"====================START {task_id[:10]}======================")
            # Update prompt if agent is available
            if not self.on_lunch:
                try:
                    self.update_prompt(task)
                except Exception as prompt_error:
                    print(f"Error updating prompt: {prompt_error}")
                    # Continue even if prompt update fails

            # Initialize history and task_dict
            self.log(f"Using task_id: {task_id}", level="info", task_id=task_id)
            
            if task_id not in self.history:
                print("task_id not in history")
                self.history[task_id] = []
                
            if task_id not in task_dict:
                task_dict[task_id] = list()
                self.log(f"Initializing task_dict for task_id: {task_id}", level="info", task_id=task_id)
                
            # Get messages for the task
            task_messages = self.messages
            self.log(f"Initial task messages: {task_messages}", level="info", task_id=task_id)
            # Stream through the agent app
            output = None

            # Use a variable to store the async generator so we can properly close it
            stream = self.app.astream(
                {"messages": task_messages, "task_id": task_id, "current": []}, config, stream_mode="values"
            )
            
            # Use try-finally to ensure proper cleanup
            try:
                async for output in stream:
                    message = output["messages"][-1]
                    self.log(f"Received message for task {task_id}", level="info", task_id=task_id)
                    print(f"\n{'='*25} MESSAGE {task_id[:10]} {'='*25}\n {message}\n{'='*25} MESSAGE {'='*25}")
            except Exception as e:
                print(f"Error during task streaming: {e}")
                self.log(f"Error during task streaming: {e}", level="error", task_id=task_id)
            self.on_lunch = True
            self.log(f"Agent process completed for task {task_id}.", level="info", task_id=task_id)
            # await self.resume_agent(config, "continue")
            # Safe way to return the last message
            guarded = []
            if output["messages"][-1].tool_calls:
                for tool_call in output["messages"][-1].tool_calls:
                    if tool_call.get('name') == 'TerminalFormatter':
                        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!.... ")
                        terminal = self.format_terminal(output["messages"][-1])
                        return terminal
                    tool_name = tool_call.get('name')
                    connector, permission = self.get_permission(tool_name)
                    perm = self.permissions[connector][permission]
                    tool_call = {
                        "name": tool_name,
                        "description": '',
                        "args": tool_call.get('args'),
                        "connector": connector,
                        "permission": permission,
                        "perm": perm
                    }
                    guarded.append(tool_call)

                # Return tools with False permissions as tuples
                disallowed_tools = [(tool, 'Pending') for tool in guarded]
                if disallowed_tools:
                    # await self.resume_agent(config, "continue")
                    self.task_list[task_id]['pending'] = disallowed_tools
                    return {task_id: disallowed_tools}
                else:
                    completed = await self.resume_agent(config, "continue")
                    validated_result = self.guard.validate(completed)
                    return validated_result
                
        except Exception as e:

            print(f"Unexpected error in start_agent: {e}")
            self.log(f"Unexpected error in start_agent: {e}", level="error", task_id=task_id if 'task_id' in locals() else None)
            return None
        return self.app.get_state(config=config).values["messages"]

        
    def route_after_llm(self, state):
            return "HIL"
    
    def HIL(self, state: AgentState):
        task_id = state['task_id']
        self.history[task_id].append(['HIL'])
        last_message = state["messages"][-1]
        tool_calls = last_message.tool_calls
        guarded = []

        cached = self.task_list.get(task_id, {}).get('cached_perms', [])

        for tool_call in tool_calls:
            tool_name = tool_call.get('name')

            # Skip permission check if tool already approved before
            if tool_name in cached:
                print(f"Skipping permission check for cached tool: {tool_name}")
                continue

            connector, permission = self.get_permission(tool_name)
            if not connector or not permission:
                print(f"Skipping permission check for tool: {tool_name} because connector or permission is not found or the tool does not exist, choose another tool")
                return Command(goto='revise')
            perm = self.permissions.get(connector, {}).get(permission, False)

            tool_call_guard = {
                "name": tool_name,
                "permission": permission,
                "perm": perm
            }
            guarded.append(tool_call_guard)

        # If any tool not previously cached is denied, interrupt
        if any(not tool["perm"] for tool in guarded):
            print("Interrupting due to denied permissions")

            human_review = interrupt(
                {
                    "question": "A tool call has been denied due to permissions. Please review.",
                    "guarded": guarded,
                }
            )
            review_action = human_review.get("action")

            if review_action == "continue":
                # Optionally cache newly approved tools
                for tool in guarded:
                    if tool["perm"]:
                        self.task_list[task_id].setdefault("cached_perms", []).append(tool["name"])
                return Command(goto='execute_tool')
            elif review_action == "deny":
                return Command(goto='revise')
        else:
            return Command(goto='execute_tool')


    def check_all_guards(self, config, response):
        thread_id = config['configurable']['thread_id']
        if 'pending' not in self.task_list[thread_id]:
            return True

        pending_tools = self.task_list[thread_id]['pending']
        completed_tools = [tool_name for tool_name, status in pending_tools if status == 'continue']
        all_continue = len(completed_tools) == len(pending_tools)
        if not all_continue:
            print("Not all tools have 'continue' status in response.")
            return False
        print("All tools have 'continue' status in response. Completed tools:")
        for tool in completed_tools:
            self.task_list[thread_id]['cached_perms'].append(tool['name'])

        return True
    
    def get_guarded(self, message):
        guarded = []
        if message.tool_calls:
            for tool_call in message.tool_calls:
                tool_name = tool_call.get('name')
                connector, permission = self.get_permission(tool_name)
                perm = self.permissions[connector][permission]
                tool_call = {
                    "name": tool_name,
                    "description": '',
                    "args": tool_call.get('args'),
                    "connector": connector,
                    "permission": permission,
                    "perm": perm
                }
                guarded.append(tool_call)
            # Return tools with False permissions as tuples
            disallowed_tools = [(tool, 'Pending') for tool in guarded]
            return disallowed_tools
        return None
    
    async def resume_agent(self, thread: dict, status):
        task_id = thread['configurable']['thread_id']
        if self.check_all_guards(thread, status):
            async for event in self.app.astream(
                # provide value
                Command(resume={"action": status}),
                thread,
                stream_mode="events",
            ):
                message = event["messages"][-1]
                self.log(f"Received message for task {thread['configurable']['task_id']}", level="info", task_id=thread['configurable']['task_id'])
                print(f"\n{'='*25} MESSAGE {task_id[:10]} {'='*25}\n {message}\n{'='*25} MESSAGE {'='*25}")
                disallowed_tools = self.get_guarded(message)
                if disallowed_tools:
                    print("Disallowed tool call, immediately stopping....")
                    # await self.resume_agent(config, "continue")
                    self.task_list[task_id]['pending'] = disallowed_tools
                    # self.task_list[task_id]['cached_perms'] djkndkjdsnjkdsnkjndskjskdjksnjdksndksjdsdskjndksjndkjsndkjsk
                    return {task_id: disallowed_tools}
        else:
            return self.app.get_state(config=thread).values["messages"]
        last_message = self.app.get_state(config=thread).values["messages"][-1]
        if not last_message.content and last_message.tool_calls:
            if last_message.tool_calls[0].get('name') == 'TerminalFormatter':
                last_message = self.format_terminal(last_message)
                return last_message
        if (disallowed_tools := self.get_guarded(last_message)):
            print("Disallowed tool call, immediately stopping....0000", disallowed_tools)
            self.task_list[task_id]['pending'] = disallowed_tools
            return {task_id: disallowed_tools}
        
        return self.app.get_state(config=thread).values["messages"]

    async def run_agents_in_parallel(self, agent, tasks: dict):
        """
        Run tasks sequentially to avoid overloading the system.
        """
        self.log("Starting run_agents_in_parallel method.", level="info")
        print(f"Starting to process {len(tasks)} tasks: {list(tasks.keys())}")
        result = None

        # If there's no work to do, return early
        if not self.task_list:
            return self.task_trace, None

        for task_id, task_data in tasks.items():
            self.log(f"Starting task {task_id}", level="info")
            start_time = time.time()

            # Ensure the task exists in our list
            if task_id not in self.task_list:
                self.log(f"Adding missing task {task_id}", level="warning")
                self.task_list[task_id] = task_data

            # Mark as not completed
            if isinstance(self.task_list[task_id], dict):
                self.task_list[task_id]['completed'] = None

            config = {"configurable": {"thread_id": task_id}, "recursion_limit": 5}
            task_dict = {task_id: task_data}

            try:
                # Resume if pending tasks are ready
                pending = self.task_list[task_id].get('pending')
                if pending:
                    if all(status == 'continue' for _, status in pending):
                        response = await self.resume_agent(config, "continue")
                        validated_result = self.guard.validate(response)
                        return response
                    
                    print("Not all tasks ready to continue. Skipping resume.")
                    continue

                # Fresh start of the agent
                self.task_list[task_id]['cached_perms'] = []
                timeout = 300.0
                result = await asyncio.wait_for(
                    agent.start_agent(task_dict, config, self.task_trace),
                    timeout=timeout
                )
                validated_result = self.guard.validate(result)

                print(f"Task {task_id} completed in {time.time() - start_time:.2f}s")
                self.log(f"Task {task_id} completed successfully.", level="info")

            except asyncio.TimeoutError:
                self.log(f"Timeout for task {task_id} after {timeout}s", level="warning")
                print(f"Timeout for task {task_id} - skipping.")

            except Exception as e:
                self.log(f"Error in task {task_id}: {e}", level="error")
                print(f"Error in task {task_id}: {e}")

            # Throttle between tasks
            await asyncio.sleep(0.5)

        self.log("All tasks done.", level="info")
        print("run_agents_in_parallel completed.")
        return validated_result

        
    def get_tool_call(self, response, index=0):
        # Update tool_calls inside additional_kwargs if it exists
        if 'additional_kwargs' in response and 'tool_calls' in response['additional_kwargs']:
            t_calls = response['additional_kwargs']['tool_calls']
            if 0 <= index < len(t_calls):
                response['additional_kwargs']['tool_calls'] = [t_calls[index]]
            else:
                response['additional_kwargs']['tool_calls'] = []
        
        # Update top-level tool_calls if it exists
        if 'tool_calls' in response:
            t_calls = response['tool_calls']
            if 0 <= index < len(t_calls):
                response['tool_calls'] = [t_calls[index]]
            else:
                response['tool_calls'] = []
        return response
    
    def extract_tools(self, tools):
        tools_list = []
        for tool in tools.tools_by_name:
            t = tools.tools_by_name[tool]
            tools_list.append(t)
        return tools_list

    async def execute_tool(self, state):
        """Choose which connector-category node to route to based on the tool mapping."""
        task_id = state.get('task_id')
        self.history[task_id].append(['tool'])
        try:
            # Get the last message which should contain the tool mapping result
            messages = state.get("messages", [])
            if not messages:
                return "revise"
                
            last_message = messages[-1]
            if hasattr(last_message, 'tool_calls'):
                tool_call_names = [tool_call['name'] for tool_call in last_message.tool_calls]
                tool_methods = []
                for tool_call_name in tool_call_names:
                    connector = tool_call_name.split('_')[0]
                    category = tool_call_name.split('_')[-1]
                    if all(connector not in tool.name.lower() for tool in tool_methods):
                        key = f"{connector}_{category}"
                        tool_node = self.tool_nodes[key]
                        methods = self.extract_tools(tool_node)
                        tool_methods.extend(methods)
                tool_node = ToolNode(tool_methods)
                tool_response = await tool_node.ainvoke({"messages": [last_message]})
                messages = tool_response['messages']
                state['messages'].extend(messages)
                # Remove all tool calls from the pending list
                self.task_list[task_id]['pending'] = [
                    t for t in self.task_list[task_id]['pending'] if t[0]['name'] not in tool_call_names
                ]
                # state['messages'] = state['messages'].extend(tool_response)
            else:
                tool_call_name = None
                # If no match found, return revise as default
                self.log("No matching connector-category found, routing to revise", level="info")
            return state
            
        except Exception as e:
            self.log(f"Error in choose_connector_category: {e}", level="error")
            return state
    
    def get_connector_permissions(self, user_email, tenant_id):
        """Get connector permissions for a user from the database."""
        try:
            # Check if we have the required database connection
            if not hasattr(self, 'db') or not self.db:
                print("Database connection not available. Skipping permission retrieval.")
                return {}
            # Check if we have the required parameters
            if not user_email or not tenant_id:
                print("User email or tenant_id not found in config. Skipping permission retrieval.")
                return {}
                
            # First try to get the user's role
            role_query = """
                SELECT role 
                FROM "Users"."users" 
                WHERE email = %s AND tenant_id = %s
            """
            role_result = self.db.execute_query(role_query, (user_email, tenant_id))
            
            if not role_result or not role_result[0]:
                print(f"No role found for user {user_email}. Skipping permission retrieval.")
                return {}
                
            role = role_result[0][0]
            print(f"Found role: {role} for user {user_email}")
            
            # Try to get permissions for the role
            try:
                permissions_query = f"""
                    SELECT connector, permissions 
                    FROM "Permissions"."{role}"
                    WHERE tenant_id = %s
                """
                permissions_result = self.db.execute_query(permissions_query, (tenant_id,))
                
                if not permissions_result:
                    print(f"No permissions found for role {role}. Skipping permission retrieval.")
                    return {}
                    
                # Convert to dictionary format
                permissions = {}
                for row in permissions_result:
                    connector, perms = row
                    permissions[connector] = perms
                    
                print(f"Retrieved permissions for role {role}: {permissions}")
                return permissions
                
            except Exception as e:
                # If the table doesn't exist or there's an error, just print a message and continue
                print(f"No permissions table found for role {role}. Continuing with next connector.")
                return {}
                
        except Exception as e:
            print(f"Error in get_connector_permissions: {str(e)}")
            return {}
        
    async def initialize(self, tools):
        """Async initialization of tools and workflow setup."""
        await self.init_tools(tools)
        self.setup_workflow()
        return self

async def main():
    print("\n=== Loading Configuration ===")
    try:
        from utils.parser import load_config
        from entry import process_tools
        from backend.process_credentials import process_credentials
        import Tools
        from Global.tasks import tasks
        
        # Load configuration
        credentials = load_config()
        print(f"Loaded credentials for: {[k for k in credentials.keys() if k != 'guarded_tools']}")
        print(f"Guarded tools: {credentials.get('guarded_tools', set())}")
        
        # Process credentials
        user_email = 'amiromar1996@hotmail.co.uk'  # Replace with your email
        creds = [
            {'tenent': '8f729f2c-aa28-4145-a949-2ffae34ea635', 'connector': 'sharepoint', 'credential': 'sharepoint-8f729f2c-aa28-4145-a949-2ffae34ea635-cjLqPe'}, 
            {'tenent': '3eb69db0-aa31-49c6-9f17-c3ed7fe715eb', 'connector': 'salesforce', 'credential': 'salesforce-8f729f2c-aa28-4145-a949-2ffae34ea635-1AGfbB'}, 
            {'tenent': '3eb69db0-aa31-49c6-9f17-c3ed7fe715eb', 'connector': 'zendesk', 'credential': 'zendesk-8f729f2c-aa28-4145-a949-2ffae34ea635-vZZYtf'}
        ]
        processed_credentials, permissions = process_credentials(creds, user_email=user_email, region='eu-west-2')
        print("Processed credentials:", processed_credentials)
        
        # Get available tools
        print("\n=== Getting Available Tools ===")
        tools_list = [name for name in dir(Tools) if name.endswith("Tool") and name != "_Tool"]
        print(f"Found tools: {tools_list}")
        
        # Fix: Add await here for the async process_tools function
        processed_tools, clients = await process_tools(tools_list, processed_credentials)
        
        if not processed_tools:
            print("Error: No tools were successfully initialized")
            return
        
        # Create task store
        task_store = tasks(
            credentials=processed_credentials,
            task_list={},
            sharepoint=clients.get('sharepoint'),
            jira=clients.get('jira'),
            user_email=user_email
        )
        
        # Set up permissions
        guarded = {
            'sharepoint': {'humanInTheLoop': True, 'readEnabled': True, 'canRead': True, 'writeEnabled': True, 'createDocuments': True, 'updateDocuments': False, 'canSend': False}, 
            'salesforce': {'humanInTheLoop': True, 'readEnabled': True, 'canRead': True, 'writeEnabled': False, 'modifyLeads': False, 'modifyOpportunities': False, 'modifyAccounts': False, 'modifyContacts': False}, 
            'zendesk': {'humanInTheLoop': True, 'readEnabled': True, 'canRead': True, 'writeEnabled': False, 'createTickets': False, 'updateTicketStatus': False, 'addComments': False}
        }
        
        # Create criticism model
        from Global.reflection import CriticismSchema
        def get_criticism_model():
            from Global.llm import LLM
            return LLM(
                profile_name="prof",
                model_kwargs={
                    "temperature": 0.7,
                    "max_tokens": 4096,
                    "top_p": 0.1
                }
            ).get_model().bind_tools([CriticismSchema])
        
        criticism = get_criticism_model()
        
        # Create Agent instance
        print("\n=== Creating Agent ===")
        agent_instance = await Agent.create(
            criticism=criticism,
            tools=processed_tools,
            guarded=guarded,
            tasks=task_store,
            config=processed_credentials,
            storage_layer={},
            business_logic="Process tasks efficiently",
            clients=clients,
            user_email=user_email
        )
        
        if agent_instance:
            print("Agent initialization successful")
            setattr(agent_instance, 'is_running', True)
            setattr(agent_instance, 'credentials', processed_credentials)
            
            # Test task processing
            try:
                # Get tasks from task store
                task_trace = {}
                t = await task_store.get_tasks()
                print("Tasks from task store:", t)
                
                if t:
                    task_id = next(iter(t))
                    print("Processing task ID:", task_id)
                    
                    # Run the agent with the task
                    result = await agent_instance.start_agent(
                        task=t,
                        config={"configurable": {"thread_id": task_id}, "recursion_limit": 100},
                        task_dict=task_trace
                    )

                    print("\n=== Task Result ===")
                    print(result)
                    return result
                else:
                    print("No tasks found in task store")
            except Exception as e:
                print(f"\nError running agent: {e}")
        else:
            print("Failed to create agent instance")
    except Exception as e:
        print(f"Error in main function: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import asyncio
    result = asyncio.run(main())
    print("result ---> ", result)
