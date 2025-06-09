import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from langgraph.graph import END, StateGraph, MessagesState, START
from utils.core import setup_logging, sync_logs_to_s3
from Logs.log_manager import LogManager

class Skeleton:
    def __init__(self, user_email: str = ""):
        self.log_manager = LogManager(user_email)
        self.user_email = user_email
        self.logger = setup_logging(user_email, 'AI_Skeleton', self.log_manager)
        self.workflow = StateGraph(MessagesState)

    def create_skeleton(self, task: str, blueprint: dict):
        """Create a skeleton workflow from a blueprint."""
        self.logger.info(f"Creating skeleton for task: {task}")
        
        # Add nodes (handle duplicates)
        added_nodes = set()
        for node in blueprint["nodes"]:
            if node not in added_nodes:
                self.workflow.add_node(node, self._create_node_function(node))
                added_nodes.add(node)
                self.logger.info(f"Added node: {node}")
        
        # Add START edge to first node
        if blueprint["nodes"]:
            first_node = blueprint["nodes"][0]
            self.workflow.add_edge(START, first_node)
            self.logger.info(f"Added START edge: START -> {first_node}")
        
        # Add edges from blueprint
        for edge in blueprint["edges"]:
            from_node, to_node = edge
            self.workflow.add_edge(from_node, to_node)
            self.logger.info(f"Added edge: {from_node} -> {to_node}")
        
        # Add END edges for terminal nodes
        nodes_with_outgoing = {edge[0] for edge in blueprint["edges"]}
        terminal_nodes = set(blueprint["nodes"]) - nodes_with_outgoing
        for terminal_node in terminal_nodes:
            self.workflow.add_edge(terminal_node, END)
            self.logger.info(f"Added END edge: {terminal_node} -> END")
        
        self.logger.info("Skeleton workflow created successfully")
        return self.workflow
    
    def compile_graph(self):
        """Compile the workflow into an executable graph."""
        compiled_graph = self.workflow.compile()
        self.logger.info("Workflow compiled successfully")
        return compiled_graph
    
    def _create_node_function(self, node_name: str):
        """Create a placeholder function for each node."""
        def node_function(state):
            self.logger.info(f"Executing node: {node_name}")
            return state
        return node_function


# Example usage
if __name__ == "__main__":
    blueprint = {
        "nodes": ['STR', 'Colleagues', 'Orchestration', 'Execution', 'Review', 'Feedback', 'Summary'],
        "edges": [
            ('STR', 'Colleagues'),
            ('Colleagues', 'Orchestration'),
            ('Orchestration', 'Execution'),
            ('Execution', 'Review'),
            ('Review', 'Feedback'),
            ('Feedback', 'Summary'),
            ('Summary', 'Feedback'),
        ]
    }
    
    skeleton = Skeleton(user_email="amir@m3labs.co.uk")
    skeleton.create_skeleton("build rest api to retrieve customer data", blueprint)
    compiled_graph = skeleton.compile_graph()
    print(f"✅ Graph created with {len(blueprint['nodes'])} nodes and {len(blueprint['edges'])} edges")