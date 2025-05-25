import ast
import os
import asyncio
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../", "")))
from Global.runner import Runner
from Prompts import master_prompts, documents_prompt, coding_prompt
from utils.imports import *
from Tools._Tool import Tool
from Connectors.sharepoint import SharePoint
from htmldocx import HtmlToDocx
from msgraph.generated.models.event import Event
from msgraph.generated.models.date_time_time_zone import DateTimeTimeZone
from msgraph.generated.models.attendee import Attendee
from msgraph.generated.models.email_address import EmailAddress
from msgraph.generated.models.attendee_type import AttendeeType
from msgraph.generated.models.online_meeting_provider_type import (
    OnlineMeetingProviderType,
)
from msgraph.generated.models.item_body import ItemBody
import base64
from msgraph.generated.users.item.send_mail.send_mail_post_request_body import (
    SendMailPostRequestBody,
)
from msgraph.generated.models.message import Message
from msgraph.generated.models.body_type import BodyType
from msgraph.generated.models.recipient import Recipient
from msgraph.generated.models.file_attachment import FileAttachment
from msgraph.generated.models.task_status import TaskStatus
from msgraph.generated.models.todo_task import TodoTask
from kiota_abstractions.base_request_configuration import RequestConfiguration
from functools import wraps

description = "This is a connector that provides access to various Microsoft 365 softwares. There are a multitude of tools related to productivity, documents and communication accessible from here. For example, you can send emails, get users information, schedule meetings, retrieve documents, create documents, etc."

def tool_wrapper(func):
    @wraps(func)
    def wrapped(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapped

class toolKit(Tool):
    def __init__(self, credentials, loop=None):
        """Initialize the SharePoint connector without making any async calls."""
        try:
            # Initialize base class with permissions
            super().__init__()
            self.__name__ = "sharepoint"
            self.loop = loop or asyncio.get_event_loop()

            # Store credentials
            self.credentials = credentials
            self.tenant = credentials.get('tenant_id')
            self.username = credentials.get('email', '')
            self.user = self.username.split('@')[0]

            credential_sp = ClientSecretCredential(
            tenant_id=self.credentials['tenant_id'],
            client_id=self.credentials['client_id'],
            client_secret=self.credentials['client_secret'],
            )
            scopes = ["https://graph.microsoft.com/.default",]

            # Create credential
            self._credential = ClientSecretCredential(
                tenant_id=self.credentials['tenant_id'],
                client_id=self.credentials['client_id'],
                client_secret=self.credentials['client_secret']
            )
            
            # Create client
            # self.client = SharePoint(self.credentials, loop=self.loop)
            self.sp = GraphServiceClient(credentials=credential_sp, scopes=scopes)

            # Use the email from credentials
            if not self.username and 'email' in self.credentials:
                self.username = self.credentials['email']
            
            # Create credential
            self._credential = ClientSecretCredential(
                tenant_id=self.credentials['tenant_id'],
                client_id=self.credentials['client_id'],
                client_secret=self.credentials['client_secret']
            )
            
            # Create client
            self.client = SharePoint(self.credentials)
            
        except Exception as e:
            print(f"Error initializing SharePoint tool: {e}")
            import traceback
            print(traceback.format_exc())
            self.client = None
            self._credential = None

    def refresh_client(self):
        return SharePoint(self.credentials)

    def _access_sharepoint_resource(self):
        access_token = self.get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        response = requests.get("https://graph.microsoft.com/v1.0/me", headers=headers)
        if response.status_code == 200:
            print("Successfully accessed resource:", response.json())
        else:
            print("Failed to access resource:", response.status_code, response.text)

    async def _get_user_id(self, username):
        client = self.refresh_client()
        response = await client.account.users.get()
        for user in response.value:
            if user.mail == username:
                return user.id
    
    async def _get_tasks(self, username):
        try:
            self.username = username
            try:
                client = self.refresh_client()
                response = await client.account.users.get()
            except AttributeError as e:
                print(f"SharePoint client is not properly initialized: {e}")
                return {}
            except Exception as e:
                print(f"Failed to get users: {e}")
                return {}
            
            # Get user ID
            user_id = None
            for user in response.value:
                if user.mail == username:
                    user_id = user.id
                    break
            
            if not user_id:
                print("Could not get user ID for username:", username)
                return {}
            # Get task lists - use self.loop for this API call too
            fetch_lists_coro = client.account.users.by_user_id(user_id).todo.lists.get()
            lists = await asyncio.wait_for(fetch_lists_coro, timeout=30.0)
            if not lists or not lists.value:
                print("No task lists found")
                return {}                
            # Get tasks
            tasks_dict = {}
            for lst in lists.value:
                if lst.display_name == "Tasks":
                    # Ensure client is still initialized before getting tasks
                    fetch_tasks_coro = client.account.users.by_user_id(user_id).todo.lists.by_todo_task_list_id(lst.id).tasks.get()
                    tasks = await asyncio.wait_for(fetch_tasks_coro, timeout=30.0)
                    if tasks and tasks.value:
                        tasks_dict.update({
                            task.id: {
                                "title": task.title, 
                                "description": task.body.content if task.body else "",
                                "id": task.id,
                                "ticket": task,
                                "list_id": lst.id,
                                "completed": None,
                                "timestamp": task.created_date_time
                            }
                            for task in tasks.value
                            if not task.completed_date_time
                        })
            return tasks_dict
        except asyncio.TimeoutError:
            print("API call timed out!")
            return {}
        except Exception as e:
            print("Error getting tasks:", e)
            import traceback
            print("Traceback:", traceback.format_exc())
            return {}
        # Fetch chats and extract tasks from Teams messages
        # chats = await self.client.account.users.by_user_id(id).chats.get()
        # tenant = self.client.tenant
        # for chat in chats.value:
        #     if chat.tenant_id == tenant:
        #         #a = await self.client.account.users.by_user_id(id).chats.by_chat_id(chat.id).messages.get()
        #         #print(a.value)
        #         # Retrieve the messages for the chat
        #         messages = [
        #             {
        #                 'id': msg.id,
        #                 'user': msg.from_.user.display_name,
        #                 'content': re.sub(r'<[^>]+>', '', msg.body.content),
        #                 'timestamp' : msg.created_date_time.strftime("%Y-%m-%d %H:%M:%S")
        #             }
        #             for msg in (await self.client.account.users.by_user_id(id).chats.by_chat_id(chat.id).messages.get()).value[:20]
        #             if msg.deleted_date_time is None and hasattr(msg.from_, 'user')
        #         ]
        #         if messages:
        #             # Identify tasks using runner and update tasks_dict
        #             teams_tasks = json.loads(run.start_runner(
        #                 master_prompts.teams_messages_human_prompt.format(messages=json.dumps(messages[::-1])), 
        #                 ""
        #             ).strip())
        #             # Output messages for debugging        
        #             tasks_dict.update({
        #                 hash(task['timestamp']): {**task, "completed": None, "id" : hash(task['timestamp'])}
        #                 for task in teams_tasks
        #             })

    async def sharepoint_send_email_admin(self, recipient_address, subject, body, with_attachments=None, attachments=None):
        """
        Sends professional emails through Microsoft 365 with optional attachments.
        Handles authentication, attachment processing, and ensures proper email formatting.
        
        Args:
            recipient_address (str): Email address of the recipient
            subject (str): Subject line of the email
            body (str): Main content of the email message
            with_attachments (bool): Whether to attach files to the email
            attachments (list) Optional: List of file paths to attach to the email. Files should be in './Data/' directory
        
        Returns:
            str: Success message if email is sent, error message if sending fails
        """
        client = self.refresh_client()
        if with_attachments and attachments:
            for file_path in attachments:
                # Normalize and get absolute path
                full_path = os.path.abspath(file_path)
                data_dir = os.path.abspath('./Data')

                # Check that file exists
                if not os.path.exists(full_path):
                    return f"There is no valid attachment provided to attach to the email to the recipient. Please find the attachments, save them and then attempt to send the email again."

                # Check that file is inside the ./Data directory
                if not full_path.startswith(data_dir):
                    return "There is no valid attachment provided to attach to the email to the recipient. Please find the attachments, save them and then attempt to send the email again."
            if with_attachments:
                if not attachments:
                    return "There are no attachments provided to attach to the email to the recipient"
                # Ensure all attachments have the prefix './Data/'
                updated_attachments = [
                    attachment if attachment.startswith('./Data/') else f'./Data/{attachment}' 
                    for attachment in attachments
                ]

        # Find the user by email
        users_response = await client.account.users.get()
        user = next((user for user in users_response.value if user.mail == self.username), None)
        if not user:
            return "Sender address not found."

        # Process attachments if any
        if updated_attachments:
            # Check if attachments is a string representation and convert it to a list if necessary
            try:
                updated_attachments = ast.literal_eval(updated_attachments) if isinstance(updated_attachments, str) else updated_attachments
            except (ValueError, SyntaxError):
                return "Attachments should be a list or a valid string representation of a list."
            
            # Ensure all attachments exist before proceeding
            missing_attachments = [attachment for attachment in updated_attachments if not os.path.isfile(attachment)]
            if missing_attachments:
                return f"Error: Attachments have not been retrieved: {', '.join(missing_attachments)}"

            # Create a zip file of the attachments
            zip_filename = "./Data/attachments.zip"
            with zipfile.ZipFile(zip_filename, "w", zipfile.ZIP_DEFLATED) as zipf:
                for attachment in updated_attachments:
                    zipf.write(attachment, os.path.basename(attachment))

            # Read and encode the zip file
            with open(zip_filename, "rb") as f:
                encoded_zip = base64.urlsafe_b64encode(f.read()).decode('utf-8')

            # Prepare the email attachment object
            attachment_obj = FileAttachment(
                odata_type="#microsoft.graph.fileAttachment",
                name="attachments.zip",
                content_type="application/zip",
                content_bytes=base64.urlsafe_b64decode(encoded_zip),
            )
        else:
            attachment_obj = None

        if "{user_name}" in body:
            body = body.replace("{user_name}", self.user)
        
        # Create the email body
        request_body = SendMailPostRequestBody(
            message=Message(
                subject=subject,
                body=ItemBody(content_type=BodyType.Text, content=body),
                to_recipients=[Recipient(email_address=EmailAddress(address=recipient_address))],
                attachments=[attachment_obj] if attachment_obj else None,
            )
        )

        # Send the email
        user = client.account.users.by_user_id(user.id)
        response = await user.send_mail.post(request_body)
        return "Email has been successfully sent."
                    
    async def sharepoint_get_users_info_admin(self):
        """
        Retrieves comprehensive user information from the Microsoft 365 organization directory such as name, email, department, job title, mobile phone number and office location.
        Provides detailed user profiles including contact information and organizational roles.
        
        Args:
            None
            
        Returns:
            dict: Dictionary containing user information with the following structure:
                {
                    "display_name": {
                        "name": str,          # User's full display name
                        "email": str,         # User's email address
                        "department": str,     # User's department
                        "jobTitle": str,      # User's job title
                        "mobile": str,        # User's mobile phone number
                        "officeLocation": str  # User's office location
                    },
                    ...
                }
        """
        client = self.refresh_client()
        users = await client.account.users.get()
        return {
            user.display_name: {
                "name": user.display_name,
                "email": user.mail,
                "department": user.department,
                "jobTitle": user.job_title,
                "mobile": user.mobile_phone,
                "officeLocation": user.office_location,
            }
            for user in users.value
        }

    async def sharepoint_schedule_meeting_admin(
        self,
        start_time: str,
        end_time: str,
        meeting_description: str,
        subject: str,
        attendees: list[str],
    ) -> str:
        """
        Schedules a Teams meeting with specified participants and details.
        Creates a calendar event with online meeting capabilities through Microsoft Teams.
        
        Args:
            start_time (str): Meeting start time in format 'YYYY-MM-DD HH:MM:SS'
            end_time (str): Meeting end time in format 'YYYY-MM-DD HH:MM:SS'
            meeting_description (str): Detailed description or agenda of the meeting
            subject (str): Meeting title/subject line
            attendees (list[str]): List of attendee email addresses
            
        Returns:
            str: Success message if meeting is scheduled, error message if scheduling fails
        """
        try:
            client = self.refresh_client()
            print(start_time, end_time, meeting_description, subject, attendees)
            try:
                start = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
                end = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
                # Format it as 2017-08-29T04:00:00.0000000
                start_date = start.strftime('%Y-%m-%dT%H:%M:%S.%f') + '0000'
                end_date = end.strftime('%Y-%m-%dT%H:%M:%S.%f') + '0000'
                user_id = await self._get_user_id(self.username)
                user_timezone = await client.account.users.by_user_id(user_id).mailbox_settings.get()
                event = Event(
                    subject=subject,
                    body=ItemBody(content_type=BodyType.Html, content=meeting_description),
                    start=DateTimeTimeZone(
                        date_time=start_time, time_zone=user_timezone.time_zone
                    ),
                    end=DateTimeTimeZone(date_time=end_time, time_zone=user_timezone.time_zone),
                    attendees=[
                        Attendee(
                            email_address=EmailAddress(address=email),
                            type=AttendeeType.Required,
                        )
                        for email in attendees
                    ],
                    allow_new_time_proposals=True,
                    is_online_meeting=True,
                    online_meeting_provider=OnlineMeetingProviderType.TeamsForBusiness,
                )
                
                request_configuration = RequestConfiguration()
                request_configuration.headers.add(
                    "Prefer", f'outlook.timezone="{user_timezone.time_zone}"'
                )
                users_response = await client.account.users.get()
                user = next(
                    (user for user in users_response.value if user.mail == self.username), None
                )
            except Exception as e:
                print("Error encouneted: ", e)
                return f"Something went wrong. I'm sorry I couldn't schedule a meeting for you. Error: {str(e)}"
            if user:
                try:
                    a = await client.account.users.by_user_id(user_id).calendar.events.post(
                        event, request_configuration=request_configuration
                    )
                    return "I have successfully scheduled a meeting for you."
                except Exception as e:
                    print("Error encouneted: ", e, a)
                    return f"Something went wrong. I'm sorry I couldn't schedule a meeting for you. Error: {str(e)}"
            else:
                return "Meeting sender not found."
        except Exception as e:
            print("Error encouneted: ", e)
            return f"Something went wrong. I'm sorry I couldn't schedule a meeting for you. Error: {str(e)}"
        
    from typing import Dict, List, Tuple

    async def sharepoint_get_documents_retrieval(self, task_description: str, task_id: str) -> Tuple[Dict[str, List[str]], List[str]]:
        """
        Retrieves and downloads relevant documents from SharePoint based on a task description.
        Performs a depth-first search through SharePoint directories to find and download matching documents.
        
        Args:
            task_description (str): Description of the task to find relevant documents for
            task_id (str): Unique identifier for the task, used for organizing downloaded files
            
        Returns:
            Tuple[Dict[str, List[str]], List[str]]: A tuple containing:
                - Dict: Message about the operation result with structure:
                    {
                        "message": str  # Success/failure message with downloaded file information
                    }
                    or
                    {
                        "error": str    # Error message if operation failed
                    }
                - List[str]: List of names of successfully downloaded files
        """
        #SOMETIMES THERE ARE THE SAME FILE NAMES IN DIFF SUBDICRECTORIES SO DO CHECK AND IF SO PRE-PEND THEIR SUB DIR FOLDER NAME TO THEM EG. ACER/PROJECT_STATEMENT_OF_WORK.DOCX ETC
        run = Runner("prof", documents_prompt.system_done)
        downloaded_files = []

        async def depth_first_search(folder, current_files, searched_files, ssd) -> tuple[list[str], bool]:
            # Get all items (files and folders) in the current folder
            folder_items = await self.sp.drives.by_drive_id(ssd.id).items.by_drive_item_id(folder.id).children.get()
            files = [item for item in folder_items.value if item.file]  # Ensure it's a file
            subfolders = [item for item in folder_items.value if item.folder]  # Separate folders

            # Filter files to avoid duplicates
            unique_files = {file.name: file for file in files}.values()
            folder_path = folder.parent_reference.path.split("/root:/", 1)[-1] if "/root:/" in folder.parent_reference.path else folder.name
            # Only append folder.name if folder_path is not the same as folder.name
            if folder_path != folder.name:
                folder_path = folder_path + "/" + folder.name
            # Add files to the current folder's list
            current_files[folder_path] = [file.name for file in unique_files]
            while True:
                if current_files[folder_path]:
                    result = await run.start_runner(
                        documents_prompt.human_done.format(
                            task_description=task_description, file_names=current_files
                        )
                    )
                    result = result.strip()
                    searched_files.extend(unique_files)
                    try:
                        json_dict = json.loads(result)
                    except json.JSONDecodeError as e:
                        print(f"Error decoding JSON: {e}, continuing...")
                        continue
                    # Check if the runner indicates to stop searching
                    if json_dict.get("continue") == False or (isinstance(json_dict.get("continue"), str) and json_dict.get("continue").lower() == 'false'):
                        relevant_files = [
                            file
                            for folder in json_dict.get("folders", [])
                            for file in folder.get("files", [])
                        ]
                        file_names = [path.name.split("/")[-1] for path in searched_files]
                        for file in relevant_files:
                            if file in file_names:
                                matching_file = next(
                                    (f for f in searched_files if f.name == file), None
                                )
                                if matching_file:
                                    id = task_id[-10:]
                                    download_path = os.path.join(
                                        f"./Data/{id}/",
                                        os.path.basename(matching_file.name),
                                    )
                                    os.makedirs(os.path.dirname(download_path), exist_ok=True)
                                    with open(download_path, "wb") as local_file:
                                        s = await self.sp.drives.by_drive_id(ssd.id).items.by_drive_item_id(matching_file.id).content.get()                                        
                                        local_file.write(s)

                                        downloaded_files.append(matching_file.name)
                        return downloaded_files, True
                for subfolder in subfolders:
                    result_files, stop = await depth_first_search(subfolder, current_files, searched_files, ssd)
                    if stop:
                        return result_files, True
                return [], False

        sites = await self.sp.sites.get()
        site = next((i for i in sites.value if i.name == 'M3'), None)
        if not site:
            print("Site not found")
            return {"error": "Site not found"}, []

        ssd = await self.sp.sites.by_site_id(site.id).drive.get()
        root_folder = await self.sp.drives.by_drive_id(ssd.id).root.get()
        folders = await self.sp.drives.by_drive_id(ssd.id).items.by_drive_item_id(root_folder.id).children.get()

        current_files = {}
        searched_files = []

        for folder in folders.value:
            if folder.folder:
                result_files, stop = await depth_first_search(folder, current_files, searched_files, ssd)
                if stop:
                    return {"message": f"Found some documents called {result_files} and I have saved them in the dir ./Data/{task_id[-10:]}."}, downloaded_files
        return {"message": f"I couldn't find any relevent documents."}

    # def sharepoint_query_documents_retrieval(self, paths: list, query: str):
    #     """
    #     Performs semantic search across downloaded documents to extract relevant information.
    #     Uses OpenAI embeddings and FAISS for efficient similarity search within document contents.
        
    #     Args:
    #         paths (list): List of file paths to analyze. Paths should be relative to './Data/' directory
    #                      Can be provided as string representation of a list or actual list
    #         query (str): Search query to find relevant content within the documents
            
    #     Returns:
    #         str: Either:
    #             - Concatenated relevant passages from the documents matching the query
    #             - Error message if document processing fails
            
    #     """
    #     try:
    #         # If paths is a string representation of a list, convert it to a list
    #         if isinstance(paths, str) and paths.startswith("["):
    #             paths = ast.literal_eval(paths)
    #     except (SyntaxError, ValueError) as e:
    #         return f"Error in parsing paths: {e}"

    #     # Ensure all paths have the prefix './Data/'
    #     paths = [
    #         path if path.startswith('./Data/') else f'./Data/{path}' 
    #         for path in paths
    #     ]
    #     all_docs = []
    #     for path in paths:
    #         try:
    #             # Load documents from the specified path
    #             loader = Docx2txtLoader(path)
    #             documents = loader.load()
    #         except Exception as e:
    #             return f"Error loading document at {path}: {e}"
    #         try:
    #             # Split documents into chunks
    #             text_splitter = CharacterTextSplitter(chunk_size=512, chunk_overlap=100)
    #             all_docs.extend(text_splitter.split_documents(documents))
    #         except Exception as e:
    #             return f"Error splitting document at {path}: {e}"

    #     try:
    #         # Embedding the documents and performing similarity search
    #         embeddings = OpenAIEmbeddings()
    #         if not all_docs:
    #             return "The document appears to be empty."
    #         db = FAISS.from_documents(all_docs, embeddings)
    #         docs = db.similarity_search(query)
    #     except Exception as e:
    #         return f"Error during similarity search: {e}"

    #     try:
    #         # Concatenate and return relevant passages from the search
    #         relevant_passages = "\n".join(page.page_content for page in docs)
    #     except Exception as e:
    #         return f"Error concatenating search results: {e}"

    #     return relevant_passages

    def _parse_html(self, html_content: str, path: str):
        document = Document()
        new_parser = HtmlToDocx()
        soup = BeautifulSoup(html_content, "html.parser")
        body_content = soup.body if soup.body else soup
        cleaned_html_content = "".join(str(tag) for tag in body_content.children)
        cleaned_html_content = cleaned_html_content.strip()
        new_parser.add_html_to_document(cleaned_html_content, document)
        document.save(path)
        return document

    async def sharepoint_save_work_creation(self, work: str):
        """
        Saves generated content to files with appropriate formats based on content type.
        Automatically determines file format and handles different content types (documents, code, etc.).
        
        Args:
            work (str): Content to be saved. Can be document text, code, or other content types
                       The content type will be automatically detected and saved in appropriate format
            
        Returns:
            str: Either:
                - Success message with the path where the file was saved
                - Error message if saving fails
        """
        run = Runner("prof", coding_prompt.system_iscode)
        extension = await run.start_runner(
            coding_prompt.human_iscode.format(content=work)
        ).strip()
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        try:
            # Handle .docx extension
            if extension == ".docx":
                doc = Document()
                doc.add_paragraph(work)
                file_path = f"./data/task_{timestamp}.docx"
                doc.save(file_path)
                return f"I have saved my work at the directory {file_path}"
            # Handle .py extension
            elif extension == ".py":
                file_path = f"./data/task_{timestamp}.py"
                with open(file_path, "w") as file:
                    file.write(work)
                return f"I have saved my work at the directory {file_path}"
            # Handle other extensions (assuming parsing HTML for unknown extensions)
            else:
                try:
                    file_path = f"./data/task_{timestamp}{extension}"
                    self._parse_html(work, file_path)
                    return f"I have saved my work at the directory {file_path}"
                except Exception as e:
                    return f"Error saving file with extension {extension}: {e}"
        except Exception as e:
            return f"Encountered an error: {e}"

    async def _get_permissions(self, permission: str) -> bool:
        # Get all service principals
        client = self.refresh_client()
        service_principals = await client.account.service_principals.get()
        principal_id = next(
            (
                sp.id
                for sp in service_principals.value
                if sp.id == "35d4d73c-3e4d-4503-9d4f-9ac2ed592271"
            ),
            None,
        )
        if not principal_id:
            print("Principal ID not found")
            return False
        # Get all permission grants
        permission_grants = await client.account.oauth2_permission_grants.get()
        # Check for the required permission
        for grant in permission_grants.value:
            if (
                grant.client_id == principal_id
                and grant.consent_type == "AllPrincipals"
            ):
                if permission in grant.scope:
                    print("Permission is granted")
                    return True
        print("Permission is not granted")
        return False
    
    async def _read_teams(self): #fix teams need only tenant
        #chats = await self.client.account.me.chats.get()
        client = self.refresh_client()
        tenant = client.tenant
        user_id = await self._get_user_id(self.username)
        chats = await client.account.users.by_user_id(user_id).chats.get()
        for chat in chats.value:
            if chat.tenant_id == tenant:
                #chat_obj = await self.client.account.me.chats.by_chat_id(chat.id).messages.get()
                chat_obj = await client.account.users.by_user_id(user_id).messages.get()
                messages = []
                # Check if chat_obj.value is not None
                if chat_obj.value:                
                    # Iterate over reversed messages only if chat_obj.value is not None
                    filtered_msgs = [msg for msg in chat_obj.value if msg.deleted_date_time is None]
                    for msg in filtered_msgs[:20]:  # Use reversed() instead of .reverse() to avoid modifying the list in place
                        message = {}
                        clean_text = re.sub(r'<[^>]+>', '', msg.body.content)
                        if hasattr(msg.from_, 'user') and not msg.deleted_date_time:
                            message[msg.from_.user.display_name] = clean_text
                            messages.append(message)
                    messages.reverse()

    def _read_file(self, path):
        # Load the .docx file
        doc = Document(path)

        full_text = []

        # Iterate over elements in the document
        for element in doc.element.body:
            if element.tag.endswith("p"):
                # Handle paragraph
                for para in doc.paragraphs:
                    full_text.append(para.text)
            elif element.tag.endswith("tbl"):
                # Handle table
                for table in doc.tables:
                    for row in table.rows:
                        row_data = []
                        for cell in row.cells:
                            row_data.append(cell.text)
                        full_text.append("\t".join(row_data))
        print("\n".join(full_text))

    async def run_on_specific_loop(coro, timeout=30.0):
        """
        Safely run a coroutine with a timeout without closing the event loop.
        This avoids 'Event loop is closed' errors with background tasks.
        """
        try:
            # Use wait_for for timeout without manipulating event loops
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            # Handle timeout
            raise TimeoutError(f"Operation timed out after {timeout} seconds")
    
    import asyncio
    from datetime import datetime

    import asyncio
    from datetime import datetime

    async def _complete_task(self, ticket):
        client = self.refresh_client()
        if 'ticket' in ticket:
            request_body = TodoTask(status=TaskStatus.Completed
        )

            user_id = await self._get_user_id(self.username)

            
            user_id = await self._get_user_id(self.username)
            user = client.account.users.by_user_id(user_id).todo.lists.by_todo_task_list_id(ticket['list_id'])
            #user = self.client.account.me.todo.lists.by_todo_task_list_id(ticket['list_id'])
            result = await user.tasks.by_todo_task_id(ticket['id']).patch(request_body)
            ticket['completed'] = datetime.now()
        else:
            ticket['completed'] = datetime.now()

