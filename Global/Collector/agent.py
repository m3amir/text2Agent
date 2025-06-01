import sys
import os
import asyncio
# Add the project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from Global.Collector.connectors import load_connectors
from Global.llm import LLM
from pydantic import BaseModel, Field
from langgraph.graph import END, StateGraph
from typing import TypedDict, List
from langgraph.types import interrupt, Command
from langgraph.constants import START, END
from langgraph.checkpoint.memory import MemorySaver
from Prompts.promptwarehouse import PromptWarehouse
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
    feedback_questions: List[str]
    answered_questions: List[str]
    reviewed: bool

class Collector:
    def __init__(self, agent_description: str):
        self.agent_description = agent_description
        self.warehouse = PromptWarehouse('m3')

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
        workflow.add_node("validate_connectors", self.validate_connectors)
        
        workflow.add_edge(START, "collect")
        workflow.add_edge("collect", "feedback")
        workflow.add_edge("feedback", "human_approval")
        def route_after_approval(state):
            # If we have answered questions and haven't collected new connectors yet, continue
            if state['reviewed']:
                return "validate_connectors"
            else:
                return "collect"
        
        workflow.add_conditional_edges(
            "human_approval",
            route_after_approval,
            {
                "collect": "collect",
                "validate_connectors": "validate_connectors",
            }
        )
        # workflow.add_edge("human_approval", "output_components")
        workflow.add_edge("validate_connectors", END)

        checkpointer = MemorySaver()
        graph = workflow.compile(checkpointer=checkpointer)
        return graph


    def validate_connectors(self, state: State) -> State:        
        # Validate connectors exist in available connectors        
        valid_connectors = []
        for connector in state['connectors']:
            
            if isinstance(connector, str) and connector in self.connectors:
                valid_connectors.append(connector)
        
        if len(valid_connectors) != len(state['connectors']):
            print(f"⚠️  Filtered to {len(valid_connectors)}/{len(state['connectors'])} valid connectors")
            
        state['connectors'] = valid_connectors
        return state
    
    async def collect(self, state):
        """Connect to the universal MCP server and get all tools"""
        agent_description = state["input"]
        llm = LLM()
        self.connectors = load_connectors()
        
        # Build connector info
        connector_info = "\n\nAvailable Connectors:\n" + "="*50 + "\n"
        for connector, description in self.connectors.items():
            connector_info += f"{connector}: {description}\n"
        
        # Build base prompt


        collector_prompt = self.warehouse.get_prompt('collector')
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
        feedback_prompt = self.warehouse.get_prompt('feedback')
        prompt = feedback_prompt + '\n\n' + 'User Agent Description: ' + state['input'] + '\n\n' + 'Connectors:\n' + formatted_connectors
        prompt += "\n\n" + "User Agent Description: " + state['input']
        feedback = llm.formatted(prompt, feedbackResponse)
        state['feedback_questions'] = feedback.feedback  # Assign directly instead of append
        return state

         
if __name__ == "__main__":
    agent_description = "I want an agent that takes emails from the emailtork file in our sharepoint and sends cold emails to the people in the file about a new product we are launching."
    collector = Collector(agent_description)
    graph = collector.init_agent(agent_description)
    config = {"configurable": {"thread_id": uuid.uuid4()}}
    result = asyncio.run(graph.ainvoke({"input": agent_description, "connectors": [], "feedback_questions": [], "answered_questions": [], "reviewed": False}, config=config))
    
    # Check if there's an interrupt with questions
    if '__interrupt__' in result and result['__interrupt__']:
        questions = result['__interrupt__'][0].value['questions']
        response = {}
        
        print("\n" + "="*60)
        print("📋 FEEDBACK QUESTIONS - Please provide your answers:")
        print("="*60)
        
        for i, question in enumerate(questions, 1):
            print(f"\n🔸 Question {i}:")
            print(f"   {question}")
            print("-" * 50)
            
            # Get user input for each question
            while True:
                answer = input(f"Your answer: ").strip()
                if answer:  # Ensure non-empty answer
                    response[question] = answer
                    break
                else:
                    print("⚠️  Please provide a non-empty answer.")
        
        print("\n✅ All questions answered! Processing your responses...")
        print("="*60)
        
        # Resume the graph with user responses
        connectors = asyncio.run(graph.ainvoke(
            Command(resume={"questions": response}),
            config=config
        ))['connectors']
        
        print(f"\n🎯 Final connectors selected: {connectors}")
    else:
        print("No interrupt occurred - process completed without feedback questions.")