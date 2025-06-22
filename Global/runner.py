import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Global.llm import LLM

class Runner(LLM):

    def __init__(self, profile_name='m3', system_prompt='', model_kwargs=None):
        # Set model_kwargs to an empty dictionary if it's None
        if model_kwargs is None:
            model_kwargs = {}

        super().__init__(profile_name, model_kwargs)
        self.model = self.get_model()  # Access the model from LLM
        self.system_prompt = system_prompt
        self.messages = [("system", self.system_prompt)]

    def invoke(self, human_message):
        """Synchronous invoke method for direct message processing"""
        self.messages.append(("human", human_message))
        response = self.model.invoke(self.messages)
        return response.content

    async def start_runner(self, human_message):
        self.messages.append(human_message)
        response = await self.ainvoke(self.messages)
        return response.content
