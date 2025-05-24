from langgraph.graph import END, StateGraph

class Collector:
    def __init__(self):
        self.workflow = StateGraph()

    def setup_workflow(self):
        self.workflow.add_node("agent", self.router)

    def collect(self):
        pass