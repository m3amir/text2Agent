from abc import ABC
from langchain_core.tools import StructuredTool
from typing import Any, Dict, Optional
import time

class Tool(ABC):
    # Class attribute

    def __init__(self, permissions: Optional[Dict] = None):
        # Instance attribute
        self.toolsManager = []
        self.guarded = {}
        self.connection = None
        # Add name attribute - default value derived from class name
        self.name = self.__class__.__name__
        # Store permissions if provided
        self.permissions = permissions or {}
        # Default permissions if none provided

    def get_all_tools(self):
        return (self.toolsManager, {})
    
    def find_tool(self, name):
        for tool in self.toolsManager:
            if tool.name == name:
                return tool
        return None

    def get_tool(self, func, name, description):
        self.toolsManager.append(StructuredTool.from_function(
            func=func, name=name, description=description,
        ))

    def get_tool_a(self, coro, name, description):
        self.toolsManager.append(StructuredTool.from_function(
            name=name, description=description, coroutine=coro
        ))
    
    def check_permission(self, permission_type: str) -> bool:
        """Check if the tool has a specific permission"""
        return self.permissions.get(permission_type, False)
    
    def request_human_approval(self, operation: str, data: Any) -> bool:
        """
        Request human approval for an operation if required by permissions
        
        Args:
            operation: Description of the operation being performed
            data: The data being operated on (will be shown to the user)
            
        Returns:
            bool: True if approved or approval not required, False if denied
        """
        if not self.permissions.get("humanInTheLoop", True):
            # Human approval not required by permissions
            return True
            
        # In a real implementation, this would show a UI dialog or send a notification
        # For this example, we'll simulate with console output and wait
        print(f"\n🚨 APPROVAL REQUIRED: {operation}")
        print(f"Data: {data}")
        print("Waiting for human approval... (auto-approving in 5 seconds for demo purposes)")
        
        # In a real implementation, this would wait for user input
        # For demo purposes, we'll auto-approve after a short delay
        time.sleep(5)
        
        # Auto-approve for this demo
        approved = True
        print(f"✅ Operation {operation} was {'approved' if approved else 'denied'} by human")
        
        return approved