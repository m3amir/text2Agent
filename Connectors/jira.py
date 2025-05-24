import base64
import json
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "")))
import requests
from langchain_core.tools import StructuredTool

class Jira:
    def __init__(self, credentials):
        self.email = credentials.get('email')
        self.api_key = credentials.get('api_key')
        self.domain = credentials.get('domain')
        self.base_url = f"https://{self.domain}.atlassian.net/rest/api/3/search"
        self.session = requests.Session()
        self.credentials = self._encode_credentials()
        self.headers = {
            "Authorization": f"Basic {self.credentials}",
            "Accept": "application/json"
        }

    def _encode_credentials(self):
        credentials = base64.b64encode(f"{self.email}:{self.api_key}".encode('utf-8')).decode('utf-8')
        return credentials
    
    async def list_permissions(self):
        params = {
        'permissions': 'BROWSE_PROJECTS,EDIT_ISSUES'
        }
        permissions = self.session.get(f"https://{self.domain}.atlassian.net/rest/api/3/permissions", headers=self.headers, params=params).json()
        permissions = [
            perm["name"]
            for perm in permissions["permissions"].values()
        ]
        return permissions


    # def _fetch_tickets(self, max_results=50):
    #     params = {
    #         "expand": "renderedFields",
    #         "maxResults": max_results,
    #         "startAt": 0
    #     }
    #     tickets = []

    #     while True:
    #         response = self.session.get(self.base_url, headers=self.headers, params=params)
    #         response.raise_for_status()  # Raises an HTTPError for bad responses
    #         data = response.json()

    #         tickets.extend(data.get('issues', []))

    #         if 'startAt' in data and data['startAt'] + data['maxResults'] < data['total']:
    #             params['startAt'] = data['startAt'] + data['maxResults']
    #         else:
    #             break
    #     #print(tickets)
    #     return self.extract_essential_data(tickets)

    # def extract_essential_data(self, tickets):
    #     essential_keys = ['id', 'key', 'summary', 'description', 'status', 'priority', 'assignee', 'reporter']
    #     essential_data = {}
    #     for ticket in tickets:
    #         fields = ticket.get('fields', {})
    #         if not fields.get('description') == None:
    #             description_content = fields.get('description', {}).get('content', [])
    #             description_text = ' '.join(
    #                 content.get('content', [{}])[0].get('text', '') 
    #                 for content in description_content
    #             )
    #         else:
    #             description_text = None
    #         ticket_data = {
    #             'id': ticket.get('id'),
    #             'key': ticket.get('key'),
    #             'summary': fields.get('summary'),
    #             'description': description_text,
    #             'status': fields.get('status', {}).get('name'),
    #             'priority': fields.get('priority', {}).get('name'),
    #             'assignee': fields.get('assignee', {}).get('displayName') if fields.get('assignee') else None,
    #             'reporter': fields.get('reporter', {}).get('displayName') if fields.get('reporter') else None
    #         }
            
    #         # Add the ticket data to the dictionary with the 'id' as the key
    #         ticket_id = ticket_data['id']
    #         if ticket_id:
    #             essential_data[ticket_id] = ticket_data

    #     return essential_data
    
    # def complete_task(self, ticket):
    #     issue_key = ticket.get('key')  # Replace with your issue key
    #     transition_url = f"https://{self.domain}.atlassian.net/rest/api/3/issue/{issue_key}/transitions"
    #     response = self.session.get(transition_url, headers=self.headers)
    #     transitions = response.json()['transitions']
    #     transition_id = None
    #     for transition in transitions:
    #         if transition['name'].lower() == 'done':
    #             transition_id = transition['id']
    #             break
    #     if not transition_id:
    #         raise Exception("Transition to 'Done' not found.")
    #     transition_data = {
    #         "transition": {
    #             "id": transition_id
    #         }
    #     }
    #     response = self.session.post(transition_url, headers=self.headers, json=transition_data)
    #     if response.status_code == 204:
    #         print("Issue transitioned to 'Done'.")
    #     else:
    #         print(f"Failed to transition issue: {response.status_code}")
    #         print(response.json())
"""
    def get_tool(self, func, name, description):
        return StructuredTool.from_function(func=func, name=name, description=description)

    def get_tickets(self):
        return self.get_tool(self._fetch_tickets, "FetchTickets", "Retrieve all jira tickets for a particular user.")

    def get_all_tools(self):
        return [
            self.get_tickets()
        ]
"""

# if __name__ == "__main__":
#     # Example usage
#     email = "amir@m3labs.co.uk"
#     api_key = "ATATT3xFfGF0ZzU33N7bNJhejbauYM_MQS_MIoRClxZk3rtfOFjJvyN4M7VXBo_HJrgLZN-uQ1xJaY8flbaV7T18yukAtIOQWPFBN_fVlMa1H5kMFTrBnZ34Q2RlTHAUyXGp_JQA8Z3BAtBzQVbAYHlz5pUb_Bd4sFvwn6zA-GU05QBGp7nU8jU=075C6E23"
#     domain = "m3labs"

#     creds = {'email' : email, 'api_key' : api_key, 'domain' : domain}

#     client = Jira(creds)
#     print(client.session)