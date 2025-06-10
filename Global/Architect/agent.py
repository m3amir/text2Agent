"""architect.py – LangGraph workflow architect (fully commented)

This agent designs a LangGraph configuration (Python code) for a new agent
based on (1) a plain‑language goal provided by the user and (2) a catalogue of
available MCP connector tools.  It follows a Collector‑style interrupt/feedback
loop so a human can fill in clarifying answers before code generation.
"""

# ────────────────────────────────────────────────────────────────────────────────
# Standard library imports
# ────────────────────────────────────────────────────────────────────────────────
import sys      # Access to Python runtime environment variables and import hooks
import os       # OS‑level utilities for path manipulation
import asyncio  # Core async/await functionality for running the LangGraph
import uuid     # Generation of unique IDs for thread/session contexts

from typing import TypedDict, List, Dict, Any  # Static typing helpers

# Ensure project‑root modules (e.g. Global.llm) resolve when this file is run
# We walk two directories up from this file and prepend that path to sys.path.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# ────────────────────────────────────────────────────────────────────────────────
# Third‑party / project‑specific utilities
# ────────────────────────────────────────────────────────────────────────────────
from pydantic import BaseModel, Field                     # Data validation / schema
from langgraph.graph import StateGraph                   # Core LangGraph builder
from langgraph.constants import START, END               # Sentinel node names
from langgraph.types import interrupt, Command           # Human‑in‑the‑loop helpers
from langgraph.checkpoint.memory import MemorySaver      # In‑memory checkpointing

from Global.llm import LLM                               # Project‑wrapper around an LLM
from Global.Collector.connectors import load_connectors  # Dynamic connector discovery

# ────────────────────────────────────────────────────────────────────────────────
# Pydantic response models – structured LLM outputs
# ────────────────────────────────────────────────────────────────────────────────

class ToolAnalysisResponse(BaseModel):
    """LLM‑structured response listing tool clusters and insights."""

    workflow_components: Dict[str, Any] = Field(
        description="Mapping of node names → details such as purpose and tools used"
    )


class WorkflowDraftResponse(BaseModel):
    """LLM‑formatted skeleton of the LangGraph state graph."""

    graph_skeleton: Dict[str, Any] = Field(
        description="JSON describing nodes, edges and conditional routing"
    )


class LangGraphCodeResponse(BaseModel):
    """Final Python code for the generated LangGraph workflow."""

    code: list[dict] = Field(description="Complete, JSON mapping out the nodes and edges of the Agent")


class FeedbackResponse(BaseModel):
    """Always use this model to structure feedback questions that need human answers."""

    feedback: List[str] = Field(description="A list of clarifying questions for the human")

# ────────────────────────────────────────────────────────────────────────────────
# State schema – the single mutable object that travels through the graph
# ────────────────────────────────────────────────────────────────────────────────

class State(TypedDict):
    input: str                         # The user‑supplied goal or agent description
    tools: List[Dict[str, str]]        # List of tool dicts: {name, description}
    draft_workflow: Dict[str, Any]     # Intermediate design artefact from LLM
    langgraph_architecture: str                # Final generated Python code
    feedback_questions: List[str]      # Questions the LLM wants the human to answer
    answered_questions: List[Dict[str, str]]  # Answers collected via interrupt
    reviewed: bool                     # Flag set to True once answers are received

# ────────────────────────────────────────────────────────────────────────────────
# Architect agent implementation
# ────────────────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT="""
You are **Architect**, a senior LangGraph‑design assistant.

Your mission
------------
Take a set of tools together with a plain‑language *agent goal* you must create a *LangGraph definition* (nodes + edges + state schema)  
and return a **single JSON object** that fully describes the workflow.

Input
~~~~~
1. `agent_goal` – a short description of what the agent should accomplish.
2. A JSON snippet showing:
   • The tools and their uses

Output
~~~~~~
Return **only** valid JSON with these top‑level keys:
```json
{{
  "state_schema": {{"field_name": "type_or_reducer", ...}},
  "nodes": [
    {{"name": "...", "purpose": "...", "reads": ["..."], "writes": ["..."], "tools": ["..."]}},
    ...
  ],
  "edges": [
    {{"source": "...", "target": "...", "edge_type": "normal|conditional|command", "condition": "..." | null}},
    ...
  ],
  "entry_node": "START" | "<first_node>",
  "end_node": "END"
}}
```
Style rules
~~~~~~~~~~~
* **JSON output format only** – no extra keys, comments, or prose.
* Use snake_case for all keys.
* Keep every string ≤ 120 characters.
* Do not include the backticks shown in the examples.

Helpful LangGraph reminders (do not repeat in output)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* Nodes are added via `add_node(name, func)`.
* Normal edges use `add_edge(source, target)`.
* Conditional routing uses `add_conditional_edges(source, router, mapping)`.
* Returning `Command(goto=...)` from a node also causes a jump.
* The graph starts at `START` and ends at `END` sentinel nodes.
* State keys merge via reducers like `operator.add` unless overridden.

The goal of the agent you will define is {goal}
"""

class Architect:
    """Architect agent that maps tools + goal → LangGraph configuration."""

    # ─────────────────────────────── init ────────────────────────────────
    def __init__(self, agent_description: str):
        self.agent_description = agent_description  # Persisted for prompts

    # ───────────────────────────── graph nodes ───────────────────────────

    async def collect_tools(self, state: State) -> State:
        """Populate `state["tools"]` by loading MCP connectors if none are supplied."""
        if state["tools"]:                      # Respect pre‑supplied tool list
            return state
        # Fallback: discover connectors dynamically via MCP config
        state["tools"] = [
            {"name": key, "description": desc} for key, desc in load_connectors().items()
        ]
        return state

    async def analyse_tools(self, state: State) -> State:
        """Cluster tools and propose logical workflow components via the LLM."""
        llm = LLM()  # Initialise LLM helper

        # Build descriptive prompt listing each tool for the LLM to analyse
        prompt = (SYSTEM_PROMPT.format(goal=f"{state['input']}\n\n"),
            "Here is the list of available tools (name – description):\n"
            + "\n".join(f"- {t['name']}: {t['description']}" for t in state["tools"])
        )
        # Try look at langgraph documentation to explain the definition of a logical node

        # Use the Pydantic model to coerce/validate the LLM output
        response = llm.formatted(prompt, ToolAnalysisResponse)
        state["draft_workflow"] = response.workflow_components  # Persist result
        return state

    async def draft_workflow(self, state: State) -> State:
        """Convert components into LangGraph skeleton unless waiting for answers."""
        # Skip if already awaiting or have collected human answers
        if state["feedback_questions"] or state["answered_questions"]:
            return state

        llm = LLM()
        prompt = (
            "Design a LangGraph based on these components. Return JSON under 'graph_skeleton' "
            "describing nodes (function, inputs), edges, and conditional routing.\n\nComponents:\n",
            f"{state['draft_workflow']}"
            "Ensure that you are using the appropriate inputs for each tool you have access to"
        )
        response = llm.formatted(prompt, WorkflowDraftResponse)
        state["draft_workflow"] = response.graph_skeleton  # Overwrite with skeleton
        return state

    async def generate_config(self, state: State) -> State:
        """Ask the LLM to produce a JSON for the designed LangGraph."""
        llm = LLM()
        prompt = (
            "Convert the following LangGraph design spec into a JSON format.\n"
            "It must import all necessary nodes and edges and compile without modification.\n\n"
            f"Spec:\n{state['draft_workflow']}"
        )
        response = llm.formatted(prompt, LangGraphCodeResponse)
        state["langgraph_architecture"] = response.code  # Save code for final output
        return state

    # def human_approval(self, state: State) -> State:
    #     """Interrupt execution to retrieve answers to feedback questions if needed."""
    #     # If answers already collected, continue without new interrupt
    #     if state["answered_questions"]:
    #         return state

    #     # Request answers from the human user
    #     answered = interrupt({"questions": state["feedback_questions"]})

    #     # Validate structure of the returned dict and persist if non‑empty
    #     if isinstance(answered, dict) and "questions" in answered:
    #         non_empty = [a for a in answered["questions"].values() if a and str(a).strip()]
    #         if non_empty and not state["answered_questions"]:
    #             state["answered_questions"].append(answered["questions"])
    #             state["reviewed"] = True  # Mark reviewed so we can exit loop
    #     return state

    def output_config(self, state: State) -> State:
        """Final node – simply return the enriched state (code is printed in __main__)."""
        print("✅ Architect approved – returning code.")
        return state

    # ─────────────────────────── graph assembly ──────────────────────────

    def init_agent(self) -> StateGraph:
        """Construct and compile the LangGraph for this Architect agent."""
        workflow = StateGraph(State)                         # Start new graph

        # Register node functions
        workflow.add_node("collect_tools", self.collect_tools)
        workflow.add_node("analyse_tools", self.analyse_tools)
        workflow.add_node("design_workflow", self.draft_workflow)
        workflow.add_node("generate_config", self.generate_config)
        # workflow.add_node("human_approval", self.human_approval)
        workflow.add_node("output_config", self.output_config)

        # Define linear progression
        workflow.add_edge(START, "collect_tools")
        workflow.add_edge("collect_tools", "analyse_tools")
        workflow.add_edge("analyse_tools", "design_workflow")
        workflow.add_edge("design_workflow", "generate_config")
        # workflow.add_edge("generate_config", "human_approval")

        # # Conditional routing based on whether human answers are now present
        # def route_after_approval(s: State):
        #     return "output_config" if s["reviewed"] else "analyse_tools"

        # workflow.add_conditional_edges(
        #     "human_approval",
        #     route_after_approval,
        #     {"analyse_tools": "analyse_tools", "output_config": "output_config"},
        # )

        workflow.add_edge("output_config", END)  # Terminate graph

        # Compile graph with a simple in‑memory checkpoint mechanism
        return workflow.compile(checkpointer=MemorySaver())

# ────────────────────────────────────────────────────────────────────────────────
# Demo / CLI entry‑point – allows running this file directly
# ────────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Human‑readable description of the agent to be created
    agent_description = (
        "Design an outreach agent that fetches high‑priority leads from Salesforce, "
        "generates personalised Google Docs proposals, and sends a Slack DM with the "
        "proposal link to each contact."
    )

    # Pre‑fab list of tools (emulating Collector output).
    sample_tools = [
        {"name": "salesforce.query_contacts", "description": "Fetch contacts using a SOQL query"},
        {"name": "salesforce.update_contact", "description": "Update a contact record in Salesforce"},
        {"name": "google_docs.create_document", "description": "Create a Google Doc from a template"},
        {"name": "google_docs.share_document", "description": "Share a document with specific users"},
        {"name": "slack.post_message", "description": "Post a real‑time message to a Slack channel"},
        {"name": "slack.schedule_message", "description": "Schedule a Slack message for later"},
        {"name": "zendesk.create_ticket", "description": "Create a support ticket in Zendesk"},
        {"name": "mysql.query", "description": "Execute a SQL query on a MySQL database"},
    ]

    # Instantiate and compile the Architect graph
    architect = Architect(agent_description)
    graph = architect.init_agent()

    # Seed state object
    initial_state: State = {
        "input": agent_description,
        "tools": sample_tools,            # Provide tools directly
        "draft_workflow": {},
        "feedback_questions": [],
        "answered_questions": [],
        "reviewed": False,
    }

    # Configuration for async graph – ensure separate thread context via UUID
    config = {"configurable": {"thread_id": uuid.uuid4()}}

    # Execute the graph asynchronously and capture final state
    result = asyncio.run(graph.ainvoke(initial_state, config=config))

    # Pretty‑print the generated LangGraph Python code
    print(result["langgraph_architecture"])