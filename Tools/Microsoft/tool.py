import requests
import json
import asyncio
import io
import sys
import os
from typing import Dict, List

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from Global.llm import LLM

try:
    import docx2txt
    from PyPDF2 import PdfReader
    EXTRACTION_AVAILABLE = True
except ImportError:
    EXTRACTION_AVAILABLE = False

class MicrosoftToolkit:
    def __init__(self, credentials: Dict[str, str]):
        self.tenant_id = credentials.get('tenant_id')
        self.client_id = credentials.get('client_id') 
        self.client_secret = credentials.get('client_secret')
        self.site_url = credentials.get('site_url')
        
        self.access_token = None
        self.site_id = None
        self.drives = {}
        
        if not all([self.tenant_id, self.client_id, self.client_secret]):
            raise ValueError("Missing required credentials: tenant_id, client_id, client_secret")
    
    async def _authenticate(self):
        if self.access_token:
            return True
            
        token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        data = {
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'scope': 'https://graph.microsoft.com/.default'
        }
        
        try:
            response = requests.post(token_url, data=data)
            if response.status_code == 200:
                self.access_token = response.json().get('access_token')
                return True
            return False
        except:
            return False
    
    def _get_headers(self):
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }

    # EMAIL OPERATIONS
    def microsoft_mail_send_email_as_user(self, sender_email: str, recipients: List[str], subject: str, body: str,
                               body_type: str = "HTML", cc_emails: List[str] = None, bcc_emails: List[str] = None,
                               attachments: List[Dict] = None) -> str:
        """
        Send an email through Microsoft Graph API on behalf of a specified user.
        
        This tool automatically formats plain text into beautiful HTML using AI if the body_type is HTML.
        It handles authentication, email composition, and delivery through Microsoft 365.
        
        Args:
            sender_email (str): Email address of the user sending the email
            recipients (List[str]): List of recipient email addresses
            subject (str): Subject line of the email
            body (str): Email body content (plain text or HTML)
            body_type (str, optional): Content type - "HTML" or "Text". Defaults to "HTML"
            cc_emails (List[str], optional): List of CC email addresses
            bcc_emails (List[str], optional): List of BCC email addresses
            attachments (List[Dict], optional): List of attachment objects
            
        Returns:
            str: JSON string with success status and email details or error information
        """
        return asyncio.run(self._send_email_as_user_async(sender_email, recipients, subject, body, body_type, cc_emails, bcc_emails, attachments))
    
    async def _send_email_as_user_async(self, sender_email: str, recipients: List[str], subject: str, body: str,
                                       body_type: str = "HTML", cc_emails: List[str] = None, bcc_emails: List[str] = None,
                                       attachments: List[Dict] = None) -> str:
        try:
            if not await self._authenticate():
                return json.dumps({"error": "Authentication failed", "success": False})
            
            # Use LLM to format the body into pretty HTML
            if body_type == "HTML" and not body.strip().startswith('<'):
                llm = LLM()
                formatting_prompt = f"""Convert the following email content into beautifully formatted HTML. 
                Use inline CSS for styling. Keep it clean and professional.
                Return ONLY the HTML body content suitable for email.
                
                Email content:
                {body}
                
                Return only the HTML content without explanations or markdown:"""
                
                formatted_response = await llm.ainvoke(formatting_prompt)
                
                # Extract and clean HTML content
                if hasattr(formatted_response, 'content'):
                    formatted_body = formatted_response.content
                else:
                    formatted_body = str(formatted_response)
                
                # Simple cleaning
                if formatted_body.startswith('```html'):
                    formatted_body = formatted_body.replace('```html', '').replace('```', '').strip()
                elif formatted_body.startswith('```'):
                    formatted_body = formatted_body.replace('```', '').strip()
                
                # Extract body content if full HTML document
                import re
                if '<!DOCTYPE' in formatted_body:
                    body_match = re.search(r'<body[^>]*>(.*?)</body>', formatted_body, re.DOTALL)
                    if body_match:
                        formatted_body = body_match.group(1).strip()
                
                body = formatted_body
            
            email_payload = {
                "message": {
                    "subject": subject,
                    "body": {"contentType": body_type, "content": body},
                    "toRecipients": [{"emailAddress": {"address": email}} for email in recipients]
                },
                "saveToSentItems": True
            }
            
            if cc_emails:
                email_payload["message"]["ccRecipients"] = [{"emailAddress": {"address": email}} for email in cc_emails]
            if bcc_emails:
                email_payload["message"]["bccRecipients"] = [{"emailAddress": {"address": email}} for email in bcc_emails]
            if attachments:
                email_payload["message"]["attachments"] = attachments
            
            send_url = f"https://graph.microsoft.com/v1.0/users/{sender_email}/sendMail"
            response = requests.post(send_url, headers=self._get_headers(), json=email_payload)
            
            if response.status_code == 202:
                return json.dumps({
                    "success": True,
                    "message": "Email sent successfully",
                    "sender": sender_email,
                    "recipients": recipients,
                    "subject": subject
                })
            else:
                return json.dumps({"error": f"Failed to send email: {response.status_code}", "success": False})
                
        except Exception as e:
            return json.dumps({"error": f"Exception: {str(e)}", "success": False})

    # CALENDAR OPERATIONS
    def microsoft_calendar_create_event(self, user_email: str, subject: str, start_time: str, end_time: str, 
                            location: str = "", body: str = "", attendees: List[str] = None, 
                            create_teams_meeting: bool = False) -> str:
        """
        Create a calendar event in Microsoft Outlook calendar for a specified user.
        
        This tool creates calendar events with support for Teams meetings, attendees, and location details.
        It integrates with Microsoft Graph API to schedule meetings and send invitations.
        
        Args:
            user_email (str): Email address of the user whose calendar to create the event in
            subject (str): Title/subject of the calendar event
            start_time (str): Start date and time in ISO format (e.g., "2024-01-15T10:00:00")
            end_time (str): End date and time in ISO format (e.g., "2024-01-15T11:00:00")
            location (str, optional): Meeting location or room name
            body (str, optional): Event description or agenda
            attendees (List[str], optional): List of attendee email addresses
            create_teams_meeting (bool, optional): Whether to create a Teams online meeting. Defaults to False
            
        Returns:
            str: JSON string with event details including ID, web link, and Teams join URL (if applicable)
        """
        return asyncio.run(self._create_event_async(user_email, subject, start_time, end_time, location, body, attendees, create_teams_meeting))
    
    async def _create_event_async(self, user_email: str, subject: str, start_time: str, end_time: str,
                                location: str = "", body: str = "", attendees: List[str] = None, 
                                create_teams_meeting: bool = False) -> str:
        try:
            if not await self._authenticate():
                return json.dumps({"error": "Authentication failed", "success": False})
            
            event_payload = {
                "subject": subject,
                "body": {"contentType": "Text", "content": body},
                "start": {"dateTime": start_time, "timeZone": "UTC"},
                "end": {"dateTime": end_time, "timeZone": "UTC"},
                "location": {"displayName": location}
            }
            
            if create_teams_meeting:
                event_payload.update({"isOnlineMeeting": True, "onlineMeetingProvider": "teamsForBusiness"})
            
            if attendees:
                event_payload["attendees"] = [{"emailAddress": {"address": email, "name": email}, "type": "required"} for email in attendees]
            
            create_url = f"https://graph.microsoft.com/v1.0/users/{user_email}/events"
            response = requests.post(create_url, headers=self._get_headers(), json=event_payload)
            
            if response.status_code == 201:
                event_data = response.json()
                result = {
                    "success": True,
                    "message": "Event created successfully",
                    "event": {
                        "id": event_data.get("id"),
                        "subject": event_data.get("subject"),
                        "start": event_data.get("start"),
                        "end": event_data.get("end"),
                        "webLink": event_data.get("webLink")
                    }
                }
                
                if event_data.get("isOnlineMeeting") and event_data.get("onlineMeeting"):
                    online_meeting = event_data.get("onlineMeeting")
                    result["event"]["teams_join_url"] = online_meeting.get("joinUrl")
                
                return json.dumps(result)
            else:
                return json.dumps({"error": f"Failed to create event: {response.status_code}", "success": False})
                
        except Exception as e:
            return json.dumps({"error": f"Exception: {str(e)}", "success": False})
    
    def microsoft_calendar_list_events(self, user_email: str, start_date: str = None, end_date: str = None, limit: int = 10) -> str:
        """
        Retrieve and list calendar events from a user's Microsoft Outlook calendar.
        
        This tool fetches calendar events within a specified date range, providing details about
        meetings, appointments, and scheduled activities. Useful for checking availability and 
        viewing upcoming events.
        
        Args:
            user_email (str): Email address of the user whose calendar events to retrieve
            start_date (str, optional): Start date filter in ISO format (e.g., "2024-01-15T00:00:00")
            end_date (str, optional): End date filter in ISO format (e.g., "2024-01-20T23:59:59")
            limit (int, optional): Maximum number of events to return. Defaults to 10
            
        Returns:
            str: JSON string with list of events including details like subject, time, location, 
                 attendees, organizer, and web links
        """
        return asyncio.run(self._list_events_async(user_email, start_date, end_date, limit))
    
    async def _list_events_async(self, user_email: str, start_date: str = None, end_date: str = None, limit: int = 10) -> str:
        try:
            if not await self._authenticate():
                return json.dumps({"error": "Authentication failed", "success": False})
            
            events_url = f"https://graph.microsoft.com/v1.0/users/{user_email}/events"
            params = {'$top': limit, '$select': 'id,subject,start,end,location,attendees,organizer,webLink', '$orderby': 'start/dateTime'}
            
            if start_date and end_date:
                params['$filter'] = f"start/dateTime ge '{start_date}' and end/dateTime le '{end_date}'"
            elif start_date:
                params['$filter'] = f"start/dateTime ge '{start_date}'"
            elif end_date:
                params['$filter'] = f"end/dateTime le '{end_date}'"
            
            response = requests.get(events_url, headers=self._get_headers(), params=params)
            
            if response.status_code == 200:
                events_data = response.json()
                events = events_data.get('value', [])
                
                formatted_events = []
                for event in events:
                    formatted_events.append({
                        'id': event.get('id'),
                        'subject': event.get('subject'),
                        'start': event.get('start'),
                        'end': event.get('end'),
                        'location': event.get('location', {}).get('displayName'),
                        'organizer': event.get('organizer', {}).get('emailAddress', {}),
                        'attendees': [att.get('emailAddress', {}) for att in event.get('attendees', [])],
                        'webLink': event.get('webLink')
                    })
                
                return json.dumps({'success': True, 'user_email': user_email, 'events': formatted_events, 'count': len(formatted_events)})
            else:
                return json.dumps({'error': f"Failed to list events: {response.status_code}", 'success': False})
                
        except Exception as e:
            return json.dumps({'error': f"Exception: {str(e)}", 'success': False})
    
    def microsoft_calendar_delete_event(self, user_email: str, event_id: str) -> str:
        """
        Delete a specific calendar event from a user's Microsoft Outlook calendar.
        
        This tool permanently removes a calendar event using its unique event ID. Use with caution
        as deleted events cannot be recovered. Useful for canceling meetings or removing outdated
        appointments.
        
        Args:
            user_email (str): Email address of the user whose calendar event to delete
            event_id (str): Unique identifier of the event to delete (obtained from list_events)
            
        Returns:
            str: JSON string confirming successful deletion or error information
        """
        return asyncio.run(self._delete_event_async(user_email, event_id))
    
    async def _delete_event_async(self, user_email: str, event_id: str) -> str:
        try:
            if not await self._authenticate():
                return json.dumps({"error": "Authentication failed", "success": False})
            
            delete_url = f"https://graph.microsoft.com/v1.0/users/{user_email}/events/{event_id}"
            response = requests.delete(delete_url, headers=self._get_headers())
            
            if response.status_code == 204:
                return json.dumps({"success": True, "message": f"Event {event_id} deleted successfully"})
            else:
                return json.dumps({"error": f"Failed to delete event: {response.status_code}", "success": False})
                
        except Exception as e:
            return json.dumps({"error": f"Exception: {str(e)}", "success": False})

    # SHAREPOINT OPERATIONS
    async def _get_site_info(self):
        if not await self._authenticate():
            return None
        if not self.site_url:
            return None
        if self.site_id:
            return self.site_id
        
        site_parts = self.site_url.replace('https://', '').split('/')
        hostname = site_parts[0]
        site_path = '/'.join(site_parts[1:])
        
        graph_url = f"https://graph.microsoft.com/v1.0/sites/{hostname}:/{site_path}"
        
        try:
            response = requests.get(graph_url, headers=self._get_headers())
            if response.status_code == 200:
                self.site_id = response.json().get('id')
                return self.site_id
            return None
        except:
            return None
    
    async def _get_drives(self):
        if not self.site_id:
            await self._get_site_info()
        if not self.site_id:
            return []
        
        drives_url = f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/drives"
        
        try:
            response = requests.get(drives_url, headers=self._get_headers())
            if response.status_code == 200:
                drives = response.json().get('value', [])
                for drive in drives:
                    self.drives[drive.get('name')] = drive.get('id')
                return drives
            return []
        except:
            return []
    
    def microsoft_sharepoint_search_files(self, query: str, drive_name: str = "Documents", file_type: str = None) -> str:
        """
        Search for files in Microsoft SharePoint document libraries using keyword queries.
        
        This tool searches through SharePoint sites and document libraries to find files matching
        your search criteria. It can filter by file type and search within specific drives/libraries.
        Returns detailed file information including download URLs and metadata.
        
        Args:
            query (str): Search keywords or terms to find in file names and content
            drive_name (str, optional): Name of the SharePoint drive/library to search. Defaults to "Documents"
            file_type (str, optional): File extension to filter results (e.g., "pdf", "docx", "xlsx")
            
        Returns:
            str: JSON string with matching files including name, path, size, creation date, 
                 modification date, download URL, web URL, and MIME type
        """
        return asyncio.run(self._search_files_async(query, drive_name, file_type))
    
    async def _search_files_async(self, query: str, drive_name: str = "Documents", file_type: str = None) -> str:
        try:
            if not self.drives:
                await self._get_drives()
            
            drive_id = self.drives.get(drive_name)
            if not drive_id:
                return json.dumps({"error": f"Drive '{drive_name}' not found", "available_drives": list(self.drives.keys())})
            
            search_url = f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/drives/{drive_id}/root/search(q='{query}')"
            response = requests.get(search_url, headers=self._get_headers())
            
            if response.status_code == 200:
                items = response.json().get('value', [])
                files = []
                for item in items:
                    if 'file' in item:
                        file_name = item.get('name', '')
                        if file_type and not file_name.lower().endswith(f'.{file_type.lower()}'):
                            continue
                        
                        files.append({
                            'name': file_name,
                            'path': item.get('parentReference', {}).get('path', ''),
                            'size': item.get('size', 0),
                            'created': item.get('createdDateTime'),
                            'modified': item.get('lastModifiedDateTime'),
                            'id': item.get('id'),
                            'downloadUrl': item.get('@microsoft.graph.downloadUrl'),
                            'webUrl': item.get('webUrl'),
                            'mimeType': item.get('file', {}).get('mimeType')
                        })
                
                return json.dumps({'success': True, 'query': query, 'drive': drive_name, 'files': files, 'count': len(files)})
            else:
                return json.dumps({'error': f"Search failed: {response.status_code}"})
                
        except Exception as e:
            return json.dumps({'error': f"Exception: {str(e)}"})
    
    def microsoft_sharepoint_download_and_extract_text(self, file_id: str, drive_name: str = "Documents") -> str:
        """
        Download a file from SharePoint and extract its text content for analysis.
        
        This tool downloads files from SharePoint and extracts readable text from various formats
        including Word documents (.docx), PDFs (.pdf), and plain text files (.txt). Perfect for
        content analysis, document processing, and information extraction workflows.
        
        Args:
            file_id (str): Unique identifier of the file to download (obtained from search_files)
            drive_name (str, optional): Name of the SharePoint drive/library containing the file. 
                                      Defaults to "Documents"
            
        Returns:
            str: JSON string with extracted text content, file metadata, extraction method used,
                 and a preview of the content. Supports .docx, .pdf, and .txt files
        """
        return asyncio.run(self._download_and_extract_text_async(file_id, drive_name))
    
    async def _download_and_extract_text_async(self, file_id: str, drive_name: str = "Documents") -> str:
        try:
            if not EXTRACTION_AVAILABLE:
                return json.dumps({'error': 'Text extraction libraries not available', 'success': False})
            
            # Get file metadata
            if not self.drives:
                await self._get_drives()
            
            drive_id = self.drives.get(drive_name)
            if not drive_id:
                return json.dumps({"error": f"Drive '{drive_name}' not found"})
            
            file_url = f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/drives/{drive_id}/items/{file_id}"
            response = requests.get(file_url, headers=self._get_headers())
            
            if response.status_code != 200:
                return json.dumps({'error': f"File lookup failed: {response.status_code}", 'success': False})
            
            file_data = response.json()
            download_url = file_data.get('@microsoft.graph.downloadUrl')
            
            if not download_url:
                return json.dumps({'error': 'No download URL available', 'success': False})
            
            # Download the file
            response = requests.get(download_url, headers={'Authorization': f'Bearer {self.access_token}'})
            
            if response.status_code != 200:
                return json.dumps({'error': f"Failed to download file: {response.status_code}", 'success': False})
            
            # Extract text based on file type
            file_name = file_data.get('name', '').lower()
            mime_type = file_data.get('file', {}).get('mimeType', '')
            
            extracted_text = ""
            extraction_method = ""
            
            try:
                if file_name.endswith('.docx') or 'wordprocessingml' in mime_type:
                    file_stream = io.BytesIO(response.content)
                    extracted_text = docx2txt.process(file_stream)
                    extraction_method = "docx2txt"
                    
                elif file_name.endswith('.pdf') or mime_type == 'application/pdf':
                    file_stream = io.BytesIO(response.content)
                    pdf_reader = PdfReader(file_stream)
                    extracted_text = ""
                    for page_num, page in enumerate(pdf_reader.pages):
                        extracted_text += f"\n--- Page {page_num + 1} ---\n"
                        extracted_text += page.extract_text()
                    extraction_method = "PyPDF2"
                    
                elif file_name.endswith('.txt') or mime_type == 'text/plain':
                    extracted_text = response.content.decode('utf-8')
                    extraction_method = "plain text"
                    
                else:
                    return json.dumps({'error': f"Unsupported file type: {file_name}", 'supported_types': ['.docx', '.pdf', '.txt'], 'success': False})
                
                extracted_text = extracted_text.strip()
                
                return json.dumps({
                    'success': True,
                    'file_info': {'name': file_data.get('name'), 'size': file_data.get('size'), 'id': file_id},
                    'extraction': {'method': extraction_method, 'text_length': len(extracted_text), 'text': extracted_text},
                    'preview': extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text
                })
                
            except Exception as extraction_error:
                return json.dumps({'error': f"Text extraction failed: {str(extraction_error)}", 'success': False})
                
        except Exception as e:
            return json.dumps({'error': f"Exception: {str(e)}", 'success': False}) 