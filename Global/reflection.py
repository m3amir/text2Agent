from pydantic import BaseModel, Field

class CriticismSchema(BaseModel):
    """Always use this tool to structure your reflection to the user."""
    ticket: str = Field(description="Description of the ticket you are currently working on.")
    steps_summary: str = Field(description="Detailed breakdown of all the steps you have taken so far. Include specific aspects for instance, the whole paths where items have been saved etc.")
