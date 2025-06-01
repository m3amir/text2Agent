import sys
import os
import asyncio
# Add the project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from Global.Collector.connectors import load_connectors
from Prompts.collector.prompt import collector_prompt, feedback_prompt
from Global.llm import LLM
from pydantic import BaseModel, Field
from langgraph.graph import END, StateGraph
from typing import TypedDict, Annotated, List, Literal
import operator
from langgraph.types import interrupt, Command
from langgraph.constants import START, END
from langgraph.checkpoint.memory import MemorySaver
import uuid

class connectorResponse(BaseModel):
    """Always use this tool to structure your response to the user."""
    connectors: list = Field(description="The formatted list of connectors")

class feedbackResponse(BaseModel):
    """Always use this tool to structure your response to the user."""
    feedback: list = Field(description="The formatted list of feedback")

class State(TypedDict):
    input: str
    connectors: List[str]
    feedback_questions: List[str]  # Remove operator.add to prevent accumulation
    answered_questions: List[str]
    reviewed: bool

class Collector:
    def __init__(self, agent_description: str):
        self.agent_description = agent_description

    def human_approval(self, state: State):
        if len(state['answered_questions']) > 0:
            return state
        answered_questions = interrupt({
            "questions": state["feedback_questions"],
        })
        if isinstance(answered_questions, dict) and "questions" in answered_questions:
            actual_answers = answered_questions["questions"]
            non_empty_answers = [ans for ans in actual_answers.values() if ans and str(ans).strip() != ""]
            if len(non_empty_answers) >= 3 and len(state['answered_questions']) == 0:
                state['answered_questions'].append(actual_answers)
                return state
            else:
                return state
            
    def init_agent(self, agent_description: str):
        workflow = StateGraph(State)
        workflow.add_node("collect", self.collect)
        workflow.add_node("feedback", self.feedback)
        workflow.add_node("human_approval", self.human_approval)
        workflow.add_node("output_components", self.output_components)
        
        workflow.add_edge(START, "collect")
        workflow.add_edge("collect", "feedback")
        workflow.add_edge("feedback", "human_approval")
        def route_after_approval(state):
            # If we have answered questions and haven't collected new connectors yet, continue
            if state['reviewed']:
                return "output_components"
            else:
                return "collect"
        
        workflow.add_conditional_edges(
            "human_approval",
            route_after_approval,
            {
                "collect": "collect",
                "output_components": "output_components",
            }
        )
        # workflow.add_edge("human_approval", "output_components")
        workflow.add_edge("output_components", END)

        checkpointer = MemorySaver()
        graph = workflow.compile(checkpointer=checkpointer)
        return graph


    def output_components(self, state: State) -> State:
        print("✅ Approved path taken.")
        return state
    
    async def collect(self, state):
        """Connect to the universal MCP server and get all tools"""
        agent_description = state["input"]
        llm = LLM()
        all_connectors = load_connectors()
        
        # Build connector info
        connector_info = "\n\nAvailable Connectors:\n" + "="*50 + "\n"
        for connector, description in all_connectors.items():
            connector_info += f"{connector}: {description}\n"
        
        # Build base prompt
        prompt = collector_prompt + connector_info + f"\n\nUser Agent Description: {agent_description}"
        
        # Add answered questions if available (use only the latest set to avoid duplicates)
        if state['answered_questions']:
            prompt += "\n\nAdditional Context from User Answers:\n" + "="*40 + "\n"
            latest_qa = state['answered_questions'][-1]  # Get the most recent answers
            if isinstance(latest_qa, dict):
                state['reviewed'] = True
                for question, answer in latest_qa.items():
                    prompt += f"Q: {question}\nA: {answer}\n\n"
        connectors = llm.formatted(prompt, connectorResponse)
        state['connectors'] = connectors.connectors
        return state
    
    async def feedback(self, state):
        # Skip feedback generation if we already have questions or if questions have been answered
        if state['answered_questions'] or state['feedback_questions']:
            return state
        llm = LLM()
        # Flatten and filter connectors in one step
        valid_connectors = [
            connector for item in state['connectors']
            for connector in (item if isinstance(item, list) else [item])
            if isinstance(connector, dict) and 'name' in connector and 'justification' in connector
        ]
        
        formatted_connectors = "\n".join([
            f"- {connector['name']}: {connector['justification']}"
            for connector in valid_connectors
        ])
        prompt = feedback_prompt + '\n\n' + 'User Agent Description: ' + state['input'] + '\n\n' + 'Connectors:\n' + formatted_connectors
        prompt += "\n\n" + "User Agent Description: " + state['input']
        feedback = llm.formatted(prompt, feedbackResponse)
        state['feedback_questions'] = feedback.feedback  # Assign directly instead of append
        return state

         
# if __name__ == "__main__":
#     agent_description = "I want an agent that takes emails from the emailtork file in our sharepoint and sends cold emails to the people in the file about a new product we are launching."
#     collector = Collector(agent_description)
#     graph = collector.init_agent(agent_description)
#     config = {"configurable": {"thread_id": uuid.uuid4()}}
#     result = asyncio.run(graph.ainvoke({"input": agent_description, "connectors": [], "feedback_questions": [], "answered_questions": [], "reviewed": False}, config=config))
#     response = {}
#     for question in result['__interrupt__'][0].value['questions']:
#         response[question] = 'dffddfdf'
#     connectors = asyncio.run(graph.ainvoke(
#         Command(resume={"questions": response}),
#         config=config
#     ))['connectors']