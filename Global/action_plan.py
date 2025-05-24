import os
from runner import Runner
# from backend.routes.auth import _get_tenant_and_credentials
from Prompts.ActionPlan.prompt import *
from langchain_core.messages import AIMessage
# from Global.agent import Agent
from uuid import uuid4
import re
import json
from Global.agent import Agent
# from entry import criticism
from Global.tasks import tasks
import os
import importlib
import asyncio
from Global.guard_mappings import guard_mappings
from Global.llm import LLM
from Global.reflection import CriticismSchema
from Tools.Salesforce.tool import toolKit
from datetime import datetime

criticism = LLM(
        profile_name="prof",
        model_kwargs={
            "temperature": 0.3,
            "max_tokens": 4096,
            "top_p": 0.8
        }
    ).get_model().bind_tools([CriticismSchema])

def load_credentials():
    """Load credentials from environment variables"""
    return {
        'sharepoint': {
            'tenant_id': os.getenv('SHAREPOINT_TENANT_ID'),
            'client_id': os.getenv('SHAREPOINT_CLIENT_ID'),
            'client_secret': os.getenv('SHAREPOINT_CLIENT_SECRET'),
            'email': os.getenv('SHAREPOINT_EMAIL')
        },
        'salesforce': {
            'SF_EMAIL': os.getenv('SF_EMAIL'),
            'SF_PASSWORD': os.getenv('SF_PASSWORD'),
            'SF_TOKEN': os.getenv('SF_TOKEN')
        },
        'zendesk': {
            'subdomain': os.getenv('ZENDESK_SUBDOMAIN'),
            'email': os.getenv('ZENDESK_EMAIL'),
            'token': os.getenv('ZENDESK_TOKEN')
        }
    }

class ActionPlan:
    def __init__(self, agent, credentials, storage_layer):
        self.agent = agent
        self.tools = self.agent.categorized_tool_lists
        # self.email = _get_validated_credentials()
        self.email = "amiromar1996@hotmail.co.uk"
        # self.credentials = _get_tenant_and_credentials(self.email)
        self.credentials = credentials
        self.tool_nodes = self.agent.tool_nodes
        self.MAX_RETRIES = 10
        self.action_plans = {}
        self.storage_layer = storage_layer
        self.permissions = {'sharepoint': {'canRead': True, 'readEnabled': True, 'humanInTheLoop': True, 'writeEnabled': True, 'createDocuments': True, 'updateDocuments': False, 'canSend': False}, 'salesforce': {'humanInTheLoop': True, 'readEnabled': True, 'writeEnabled': False, 'modifyLeads': False, 'modifyOpportunities': False, 'modifyAccounts': False, 'modifyContacts': False}, 'zendesk': {'humanInTheLoop': True, 'readEnabled': True, 'writeEnabled': False, 'createTickets': False, 'updateTicketStatus': False, 'addComments': False}}
        
    async def get_tools(self):
        # tools_list = [name for name in os.listdir(os.path.dirname(importlib.import_module("Tools").__file__)) 
        #       if os.path.isfile(os.path.join(os.path.dirname(importlib.import_module("Tools").__file__), name, "tool.py"))]
        # self.tools, clients = process_tools(tools_list, self.credentials)
        # tools_list = ''
        for tool in self.tools:
            tool_methods = tool.get_all_tools()[0]
            for method in tool_methods:
                tools_list += method.name + ': ' + 'Tool description: ' + method.description + '\n\n'
        return tools_list
    
    def get_permission(self, tool_name):
        for connector, tools in guard_mappings.items():
            if tool_name in tools:
                return connector, tools[tool_name]
        return None, None
    
    async def parse_response(self, input_str):
        try:            
            # If input_str is already a dict, return it directly
            if isinstance(input_str, dict):
                return input_str

            # If input_str is not a string, handle accordingly.
            if not isinstance(input_str, str):
                if isinstance(input_str, tuple):
                    if len(input_str) > 0 and isinstance(input_str[0], dict):
                        return input_str[0]
                    elif len(input_str) > 0 and isinstance(input_str[0], str):
                        input_str = input_str[0]
                    else:
                        input_str = str(input_str)
                else:
                    input_str = str(input_str)
            
            # Remove any surrounding backticks or triple backticks (optionally with 'json')
            input_str = re.sub(
                r'^\s*`{3}json\s*|\s*`{3}\s*$', 
                '', 
                input_str.strip(), 
                flags=re.MULTILINE
            )

            # Remove everything before the first '{'
            input_str = re.sub(r'^[^{]*', '', input_str)
            # Remove any trailing characters after the last '}'
            input_str = re.sub(r'}[^}]*$', '}', input_str)
            
            # Replace Python-style booleans with JSON booleans
            input_str = re.sub(r'\bTrue\b', 'true', input_str)
            input_str = re.sub(r'\bFalse\b', 'false', input_str)
            
            # Load the JSON. If the JSON string uses single quotes, replace them with double quotes.
            if "'" in input_str and '"' not in input_str:
                input_str = input_str.replace("'", '"')

            data = json.loads(input_str)
            return data

        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            return None

    async def clear_tool_args(self, data):
        for item in data.get("action_plan", []):
            if "tool_args" in item:
                for key in item["tool_args"]:
                    item["tool_args"][key] = ""
        return data
    
    async def get_args(self, response, payload):
        runner = Runner(
            system_prompt=system_args,
        )
        prompt = user_args.format(payload=payload,trajectory=response, available_tools=self.tools)
        response = await runner.start_runner(prompt)
        return response
    
    async def get_direction(self, payload):
        runner = Runner(
            system_prompt=system_direction,
        )
        prompt = user_direction.format(task_information=payload)
        response = await runner.start_runner(prompt)
        return response
    
    async def create_action_plan(self, id, payload, task_type):
        id = payload['opportunity_id']
        self.action_plans[id] = None
        print(f"===========CREATING ACTION PLAN FOR payload ===========")
        # Now directly await the async methods
        while True:
            print("Creating action plan.........")
            direction = await self.get_direction(payload)
            
            runner = Runner(
                system_prompt=system,
            )
            prompt = user.format(task_information=direction, available_tools=self.tools)

            # Directly await all operations
            response_str = await runner.start_runner(prompt)
            response = await self.parse_response(response_str)
            response = await self.clear_tool_args(response)
            
            action_plan_args_str = await self.get_args(response, payload)
            action_plan_with_args = await self.parse_response(action_plan_args_str)
            if not action_plan_with_args:
                continue
            self.action_plans[id] = action_plan_with_args
            self.action_plans[id]['task_type'] = task_type
            self.action_plans[id]['payload'] = payload
            return self.action_plans[id]
    
    async def resume_action_plan(self, id, action_plan_with_args, resume):
        return await self.run_action_plan(id, action_plan_with_args, resume=resume)
    
    async def get_tool_payload(self, tool, tool_args):
        message = AIMessage(
            content='',
            tool_calls=[
                {
                    "name": tool,
                    "args": tool_args,
                    "id": str(uuid4()),
                    "type": "tool_call",
                }
            ],
        )
        return message

    async def revise_action_plan(self, id, action_plan_with_args, tool_message):
        runner = Runner(system_prompt=system_revise)
        prompt = user_revise.format(action_plan=action_plan_with_args, tool_message=tool_message)
        response = await self.parse_response(await runner.start_runner(prompt))
        
        change = response.pop('change', None)
        current_step = int(response['step'])
        index = current_step - 1

        if change == 'REMOVE':
            action_plan_with_args['action_plan'].pop(index)
        elif change == 'ADD':
            action_plan_with_args['action_plan'].insert(index, response)
        elif change == 'MODIFY':
            print("Modifying step -->", response['step'])
            action_plan_with_args['action_plan'][index] = response

        # Reassign step numbers for all actions
        action_plan_with_args['action_plan'] = [
            {**action, 'step': i + 1} for i, action in enumerate(action_plan_with_args['action_plan'])
        ]
        
        return action_plan_with_args, current_step

    async def update_action_plan(self, id, action_plan_with_args, current_step):
        for step in action_plan_with_args['action_plan']:
            if step['step'] == str(current_step):
                step['status'] = 'completed'
                return
            
    async def get_last_step(self, id, resume):        
        if not resume:
            print("DEBUG: resume is empty, returning default step 1")
            return 1
        
        plan = self.action_plans[id]
        
        try:
            steps = [
                int(step['step'])
                for entry in resume
                if len(entry) >= 2 and isinstance(entry[0], dict) and 'name' in entry[0]
                for step in plan['action_plan']
                if step['tool'] == entry[0]['name'] and step.get('status') == 'pending'
            ]
            return max(steps) if steps else 1
        except Exception:
            return 1

    async def run_action_plan(self, id, action_plan_with_args, resume=None):
        retries = 0
        current_step = 1
        guarded = {}
        tasks = []

        async def invoke_tool(node, msg):
            before = set(asyncio.all_tasks())
            resp = await node.ainvoke({"messages": [msg]})
            for t in set(asyncio.all_tasks()) - before:
                if not t.done() and t not in tasks:
                    tasks.append(t)
            return resp

        resume_entries = {}
        if resume:
            current_step = await self.get_last_step(id, resume)
            for tup in resume:
                if len(tup) < 2:
                    continue
                entry, status = tup[0], tup[1]
                if isinstance(entry, dict) and (name := entry.get('name')):
                    resume_entries[name] = (entry, status)
                    if 'args' in entry:
                        for i, act in enumerate(action_plan_with_args['action_plan']):
                            if act['tool'] == name:
                                print(f"DEBUG: Updating tool_args for step {i+1}")
                                action_plan_with_args['action_plan'][i]['tool_args'] = entry['args']
            if any(s == 'reject' for _, s in resume_entries.values()):
                for name, (_, s) in resume_entries.items():
                    if s == 'reject':
                        for i, act in enumerate(action_plan_with_args['action_plan']):
                            if act['tool'] == name:
                                print(f"DEBUG: Marking action plan step {i+1} as rejected")
                                self.action_plans[id]['action_plan'][i]['status'] = 'reject'
                return "Tool not allowed. Unable to continue."
            if all(s != 'continue' for _, s in resume_entries.values()):
                return "Tools not approved. Unable to continue."

        try:
            while retries < self.MAX_RETRIES:
                for action in action_plan_with_args['action_plan'][current_step - 1:]:
                    tool_name = action['tool']
                    parts = tool_name.split('_')
                    category = '_'.join([parts[0], parts[-1]])
                    current_step = int(action['step'])
                    tool_node = self.tool_nodes[category]
                    message = await self.get_tool_payload(tool_name, action['tool_args'])
                    resume_entry, resume_status = resume_entries.get(tool_name, (None, None))
                    if resume_status == 'reject':
                        continue
                    if resume_status != 'continue':
                        connector, permission = self.get_permission(tool_name)
                        perm = self.permissions[connector][permission]
                        guarded[tool_name] = perm
                        if not perm:
                            self.action_plans[id]['action_plan'][current_step - 1]['status'] = 'pending'
                            disallowed = [(tn, 'Pending') for tn, allowed in guarded.items() if not allowed]
                            return disallowed, action['reasoning'], action['tool_args']
                    response = await invoke_tool(tool_node, message)
                    if 'error:' in response['messages'][-1].content.lower():
                        action_plan_with_args, current_step = await self.revise_action_plan(
                            id, action_plan_with_args, response['messages'][-1].content
                        )
                        action_plan_with_args = await self.get_args(action_plan_with_args, self.action_plans[id]['payload'])
                        action_plan_with_args = await self.parse_response(action_plan_with_args)
                        self.action_plans[id] = action_plan_with_args 
                        retries += 1
                        break
                    await self.update_action_plan(id, action_plan_with_args, current_step)
                else:
                    self.agent.task_list[id]['completed'] = datetime.now()
                    plan_payload = action_plan_with_args.copy()
                    plan_payload["action_plan"] = [
                        {k: v for k, v in step.items() if k != "status"}
                        for step in plan_payload["action_plan"]
                    ]
                    with open('./Data/Action-Plans/{task_id}.json', 'w') as f:
                        json.dump(plan_payload, f, indent=4)
                    now = datetime.now()
                    dfolder, tfolder = now.strftime("%m-%d-%y"), now.strftime("%H:%M:%S")
                    self.storage_layer.save(
                        f'Data/Action-Plans/{plan_payload["task_type"]}/{id}/{dfolder}/{tfolder}',
                        "action_plan.json",
                        './Data/Action-Plans/{task_id}.json'
                    )
                    resume = (task := action).get('pending', [])
                    if not isinstance(resume, list):
                        resume = list(resume) if isinstance(resume, tuple) else []
                    if tasks:
                        done, pending = await asyncio.wait([t for t in tasks if not t.done()],
                                                        timeout=10, return_when=asyncio.ALL_COMPLETED)
                        if pending:
                            print(f"DEBUG: Warning: {len(pending)} tasks still pending after timeout")
                    return True
            return False
        except Exception:
            return False
        finally:
            if tasks:
                try:
                    done, pending = await asyncio.wait(
                        [t for t in tasks if not t.done() and not t.cancelled()],
                        timeout=5, return_when=asyncio.ALL_COMPLETED
                    )
                    for t in done:
                        if t.done() and not t.cancelled():
                            try:
                                if t.exception():
                                    print(f"DEBUG: Unhandled task exception: {t.exception()}")
                            except asyncio.InvalidStateError:
                                pass
                    if pending:
                        print(f"DEBUG: Warning: {len(pending)} tasks still pending after cleanup timeout")
                except Exception as e:
                    print(f"DEBUG: Error during task cleanup: {e}")



# tools_list = [name for name in os.listdir(os.path.dirname(importlib.import_module("Tools").__file__)) 
#               if os.path.isfile(os.path.join(os.path.dirname(importlib.import_module("Tools").__file__), name, "tool.py"))]


# def process_tools(tools, credentials):
#     """Process tools and credentials to create tool instances."""
#     processed_clients, processed_tools = {}, []
#     if isinstance(credentials.get('services'), dict):
#         credentials.update({f"{k}_creds": v for k, v in credentials['services'].items()})

#     tools = [t for t in tools if t != "_Tool"]

#     for tool_name in tools:
#         try:
#             module_path = f"Tools.{tool_name}.tool"
            
#             try:
#                 tool_module = importlib.import_module(module_path)
#             except ImportError as e:
#                 continue
#             tool_class = getattr(tool_module, 'toolKit', None)
#             if not tool_class:
#                 continue

#             base_name = tool_name.lower().replace('tool', '')
#             tool_creds = credentials.get('salesforce') if base_name == 'analyst' else credentials.get(base_name)
#             tool_instance = None
#             if hasattr(tool_class, '__init__'):
#                 init_params = tool_class.__init__.__code__.co_varnames
#                 if 'credentials' in init_params:
#                     tool_instance = tool_class(credentials=tool_creds)
#                 else:
#                     tool_instance = tool_class()
#             else:
#                 continue

#             if tool_instance:
#                 processed_tools.append(tool_instance)
#                 processed_clients[base_name] = tool_instance

#         except AttributeError as e:
#             print(f"Error: {tool_name} not found in Tools. AttributeError: {e}")
#         except Exception as e:
#             print(f"Unexpected error with tool {tool_name}: {e}")

#     return processed_tools, processed_clients


# processed_tools, clients = process_tools(tools_list, credentials)

# # cred, perms = _get_tenant_and_credentials('amiromar1996@hotmail.co.uk')

# task_store = tasks(
#                 task_list={},
#                 sharepoint=clients.get('sharepoint'),
#                 jira=clients.get('jira'),
#                 credentials=credentials,
#                 user_email=''
#             )
# async def get_instance():
#     return await Agent.create(
#                     criticism=criticism,
#                     tools=processed_tools,
#                     guarded={},
#                     tasks=task_store,
#                     config='',
#                     storage_layer={},
#                     business_logic="Process tasks efficiently",
#                     clients=clients,
#                     user_email=''
#                 )

# import asyncio

# payload = {
#     'type': 'opportunities',
#     'contact': {
#         'elis Ddde': {
#             'name': 'elis Ddde',
#             'email': 'elis.ddde@nextek.com',
#             'phone': '+1234567890',
#             'company': 'NexTek Inc.',
#             'title': 'Software Engineer',
#             'linkedin': 'https://www.linkedin.com/in/johndoe',
#         },
#         'Rosie erhe': {
#             'name': 'Rosie erhe',
#             'email': 'rosie.erhe@nextek.com',
#             'phone': '+1234567890',
#             'company': 'NexTek Inc.',
#             'title': 'Software Engineer',
#         }
#     },
#     'summary': """
#     NexTek's journey began in 2010, initially focusing on providing software solutions for small and medium-sized enterprises. By 2012, they introduced an innovative inventory management system, gaining strong traction in the regional retail sector.

#     Key Milestones:
#     In 2014, they formed a partnership with a leading logistics firm to offer advanced supply chain solutions. This partnership laid the groundwork for further expansions into larger industries. By 2016, NexTek launched a cloud-based accounting platform, which attracted a diverse range of businesses.

#     Strategic Acquisition (2018):
#     In 2018, NexTek acquired NextGen Analytics, which allowed them to integrate advanced data analytics into their solutions, greatly enhancing their product offerings and opening doors to new markets.

#     Current Opportunities:
#     Renewable Energy Solutions (2023-Present):
#     NexTek is actively engaging with energy providers to develop software platforms for renewable energy management, including solar and wind energy solutions.

#     Retail Analytics (2023):
#     NexTek is partnering with major retail chains to offer AI-driven analytics for customer behavior, inventory management, and sales forecasting.

#     Cybersecurity Solutions (2023):
#     NexTek is in talks with large enterprises to deliver cutting-edge cybersecurity solutions, helping protect against evolving threats in industries such as finance and healthcare.

#     Future Focus:
#     International Expansion (2025):
#     NexTek plans to increase its presence in Europe and the Middle East by establishing new offices and focusing on regional business development.

#     AI-Driven Healthcare Solutions (2025-2030):
#     They are working on creating AI-driven healthcare platforms to improve diagnostics and patient care management for hospitals and clinics.

#     Autonomous Logistics (2030):
#     NexTek is exploring the development of autonomous logistics systems using AI and robotics to revolutionize supply chain operations.
#     """,
#     'metrics': [
#         {
#             'name': 'Opportunities',
#             'description': 'Number of opportunities in the pipeline',
#             'value': 12
#         },
#         {
#             'name': 'Closed Deals',
#             'description': 'Number of closed deals in the pipeline',
#             'value': 8
#         },
#         {
#             'name': 'avg_deal_size',
#             'description': 'Average deal size',
#             'value': 1200000
#         },
#         {
#             'name': 'avg_closed_deals',
#             'description': 'Average closed deal percentage',
#             'value': '75%'
#         }
#     ]
# }

# # a.create_action_plan(payload)
# d = {
#     "action_plan": [
#         {
#             "step": "1",
#             "action": "Create a new account for a potential energy provider interested in renewable energy solutions.",
#             "tool": "salesforce_create_account_creation",
#             "tool_args": {
#                 "account_name": "NexTek Inc.",
#                 "industry": "Energy",
#                 "description": "Potential energy provider interested in renewable energy solutions."
#             }
#         },
#         {
#             "step": "2",
#             "action": "Create a contact for the new account to facilitate communication.",
#             "tool": "salesforce_create_contact_creation",
#             "tool_args": {
#                 "last_name": "Ddde",
#                 "email": "elis.ddde@nextek.com"
#             }
#         },
#         {
#             "step": "3",
#             "action": "Create an opportunity for the renewable energy management software with the new account.",
#             "tool": "salesforce_create_opportunity_creation",
#             "tool_args": {
#                 "account": "NexTek Inc.",
#                 "opportunity_name": "Renewable Energy Management Software",
#                 "amount": 1200000,
#                 "close_date": "2023-12-31",
#                 "stage_name": "Prospecting",
#                 "type": "New Business",
#                 "description": "Opportunity for renewable energy management software."
#             }
#         },
#         {
#             "step": "4",
#             "action": "Retrieve documents related to renewable energy solutions from SharePoint.",
#             "tool": "sharepoint_get_documents_retrieval",
#             "tool_args": {
#                 "task_description": "Renewable energy solutions",
#                 "task_id": "12345"
#             }
#         },
#         {
#             "step": "5",
#             "action": "Schedule a meeting with the potential client to discuss the renewable energy solutions.",
#             "tool": "sharepoint_schedule_meeting_admin",
#             "tool_args": {
#                 "start_time": "2023-11-01 10:00:00",
#                 "end_time": "2023-11-01 11:00:00",
#                 "meeting_description": "Discussion on renewable energy solutions.",
#                 "subject": "Renewable Energy Solutions Meeting",
#                 "attendees": ["elis.ddde@nextek.com"]
#             }
#         }
#     ]
# }

# asyncio.run(a.run_action_plan(d))

# c = {'action_plan': [{'step': '1', 'action': 'Create a new account for a potential energy provider interested in renewable energy solutions.', 'tool': 'salesforce_create_account_creation', 'tool_args': {'account_name': 'NexTek Inc.', 'industry': 'Energy', 'description': 'Potential energy provider interested in renewable energy solutions.'}}, {'step': '3', 'action': 'Create an opportunity for the renewable energy management software with the new account.', 'tool': 'salesforce_create_opportunity_creation', 'tool_args': {'account': 'NexTek Inc.', 'opportunity_name': 'Renewable Energy Management Software', 'amount': 1200000, 'close_date': '2023-12-31', 'stage_name': 'Prospecting', 'type': 'New Business', 'description': 'Opportunity for renewable energy management software.'}}, {'step': '4', 'action': 'Retrieve documents related to renewable energy solutions from SharePoint.', 'tool': 'sharepoint_get_documents_retrieval', 'tool_args': {'task_description': 'Renewable energy solutions', 'task_id': '12345'}}, {'step': '5', 'action': 'Schedule a meeting with the potential client to discuss the renewable energy solutions.', 'tool': 'sharepoint_schedule_meeting_admin', 'tool_args': {'start_time': '2023-11-01 10:00:00', 'end_time': '2023-11-01 11:00:00', 'meeting_description': 'Discussion on renewable energy solutions.', 'subject': 'Renewable Energy Solutions Meeting', 'attendees': ['elis.ddde@nextek.com']}}]}

# a.revise_action_plan(c, "Exception: Account already exists on salesforce.")


# payload = [{'opportunity_id': '006gK0000000eC0QAI', 'name': 'GenePoint Standby Generator', 'stage': 'Closed Won', 'amount': 85000.0, 'probability': 100.0, 'closeDate': '2024-12-23', 'category': 'Infrastructure', 'priority': 'High', 'expectedROI': '34000%'}, {'id': '006gK0000000eC9QAI', 'name': 'GenePoint Lab Generators', 'stage': 'Id. Decision Makers', 'amount': 60000.0, 'probability': 60.0, 'closeDate': '2025-02-12', 'category': 'Infrastructure', 'priority': 'Medium', 'expectedROI': '24000%'}, {'id': '006gK0000000eCAQAY', 'name': 'GenePoint SLA', 'stage': 'Closed Won', 'amount': 30000.0, 'probability': 100.0, 'closeDate': '2025-02-15', 'category': 'Infrastructure', 'priority': 'High', 'expectedROI': '12000%'}]
# async def main():
#     # Get a single agent instance to be shared
#     agent = await get_instance()

#     a = ActionPlan(agent, credentials)
#     print(a.agent.permissions)
#     toolkit = toolKit(credentials['salesforce'])
#     deets = toolkit.salesforce_get_account_details_retrieval('001gK0000004Y3HQAU')
#     contacts = toolkit.salesforce_get_contacts_retrieval(deets.get('Id'))
#     contacts_data = []
#     for contact in contacts:
#         contact_info = {
#             'Id': contact.get('Id'),
#             'FirstName': contact.get('FirstName'),
#             'LastName': contact.get('LastName'),
#             'Email': contact.get('Email'),
#             'Phone': contact.get('Phone'),
#             'MobilePhone': contact.get('MobilePhone'),
#             'Title': contact.get('Title'),
#             'Department': contact.get('Department'),
#     }
#         contacts_data.append(contact_info)
#     payload[0].update({
#         'Contacts': contacts_data
#     })
#     account_id = deets.get('Id')
#     name = deets.get('Name')
#     industry = deets.get('Industry')
#     phone = deets.get('Phone')
#     website = deets.get('Website')
#     rating = deets.get('Rating')
#     annual_revenue = deets.get('AnnualRevenue')
#     num_employees = deets.get('NumberOfEmployees')
#     description = deets.get('Description')

#     payload[0].update({
#     'Industry': deets.get('Industry'),
#     'Phone': deets.get('Phone'),
#     'Website': deets.get('Website'),
#     'Rating': deets.get('Rating'),
#     'AnnualRevenue': deets.get('AnnualRevenue'),
#     'NumberOfEmployees': deets.get('NumberOfEmployees'),
#     'Description': deets.get('Description')
#     })
#     print("payload -->sss ", payload)
#     resume = {
#         '006gK0000000eBxQAI': [('sharepoint_send_email_admin', 'continue')],
#     }
#     a.action_plans['006gK0000000eBxQAI'] = {'action_plan': [{'step': '1', 'action': 'Retrieve account details for Dickenson Mobile Generators from Salesforce', 'reasoning': "Understanding the account details will provide insights into the company's background, which is essential for tailoring our approach to their specific needs and building a strong relationship.", 'tool': 'salesforce_get_account_details_retrieval', 'status' : 'pending', 'tool_args': {'account_id': '001gK0000004Y3AQAU'}}, {'step': '2', 'action': 'Retrieve contact information for Andy Young from Salesforce', 'reasoning': 'Having detailed contact information for Andy Young, the SVP of Operations, will facilitate direct communication and help in understanding his role and influence in decision-making.', 'status': 'pending', 'tool': 'salesforce_get_contacts_retrieval', 'tool_args': {'account_id': '001gK0000004Y3AQAU'}}, {'step': '3', 'action': 'Schedule a meeting with Andy Young to discuss their specific needs and pain points', 'status': 'pending', 'reasoning': 'A direct conversation with Andy Young will allow us to understand their specific requirements and pain points, enabling us to present a tailored solution that highlights the high ROI potential.', 'tool': 'sharepoint_schedule_meeting_admin', 'tool_args': {'start_time': '2023-11-01 10:00:00', 'end_time': '2023-11-01 11:00:00', 'meeting_description': 'Discussion on specific needs and pain points of Dickenson Mobile Generators to tailor our solutions for high ROI.', 'subject': 'Meeting with Andy Young - Dickenson Mobile Generators', 'attendees': ['a_young@dickenson.com']}}, {'step': '4', 'action': 'Send a follow-up email to Andy Young summarizing the meeting and proposed solutions', 'status': 'pending', 'reasoning': 'A follow-up email will reinforce the discussion points and proposed solutions, ensuring clarity and demonstrating our commitment to addressing their needs effectively.', 'tool': 'sharepoint_send_email_admin', 'tool_args': {'recipient_address': 'a_young@dickenson.com', 'subject': 'Follow-up: Meeting Summary and Proposed Solutions', 'body': 'Dear Andy,\n\nThank you for meeting with us to discuss the specific needs and pain points of Dickenson Mobile Generators. We are excited about the opportunity to work together and provide solutions that offer a high ROI.\n\nPlease find below a summary of our discussion and the proposed solutions:\n\n- [Summary of discussion points]\n- [Proposed solutions]\n\nWe look forward to your feedback and are eager to move forward.\n\nBest regards,\n\n{user_name}\n{user_email}', 'attachments': []}}]}
#     # Create two different payloads
#     payloads = [payload]  # list of payloads
#     # Create tasks for concurrent execution
#     tasks = []

#     # for p in payloads:
#     # task = await a.run_action_plan('006gK0000000eBxQAI', a.action_plans['006gK0000000eBxQAI'])
#     # task = await a.run_action_plan('006gK0000000eBxQAI', a.action_plans['006gK0000000eBxQAI'], resume)
#     task = await a.create_action_plan('006gK0000000eBxQAI', payload[0], 'Opportunity')
#     # tasks.append(task)
    
#     # # Run all tasks concurrently
#     # response = await asyncio.gather(*tasks)
#     # print("response --> ", response)

# # Run the main function
# if __name__ == "__main__":
#     asyncio.run(main())