"""
SharePoint Tool using Microsoft Graph API
Provides folder listing and file search functionality
"""
import requests
import json
import asyncio
from typing import Optional, Dict, List, Any

class SharepointToolkit:
    """SharePoint toolkit using Microsoft Graph API"""
    
    def __init__(self, credentials: Dict[str, str]):
        """Initialize with credentials"""
        self.tenant_id = credentials.get('tenant_id')
        self.client_id = credentials.get('client_id') 
        self.client_secret = credentials.get('client_secret')
        self.site_url = credentials.get('site_url')
        
        self.access_token = None
        self.site_id = None
        self.drives = {}
        
        # Validate required credentials
        if not all([self.tenant_id, self.client_id, self.client_secret, self.site_url]):
            raise ValueError("Missing required SharePoint credentials")
    
    async def _authenticate(self):
        """Get access token for Microsoft Graph"""
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
                token_data = response.json()
                self.access_token = token_data.get('access_token')
                return True
            else:
                print(f"Authentication failed: {response.text}")
                return False
        except Exception as e:
            print(f"Authentication error: {e}")
            return False
    
    async def _get_site_info(self):
        """Get SharePoint site information"""
        if not await self._authenticate():
            return None
            
        if self.site_id:
            return self.site_id
        
        # Extract hostname and site path
        site_parts = self.site_url.replace('https://', '').split('/')
        hostname = site_parts[0]
        site_path = '/'.join(site_parts[1:])
        
        graph_url = f"https://graph.microsoft.com/v1.0/sites/{hostname}:/{site_path}"
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.get(graph_url, headers=headers)
            if response.status_code == 200:
                site_data = response.json()
                self.site_id = site_data.get('id')
                return self.site_id
            else:
                print(f"Site lookup failed: {response.text}")
                return None
        except Exception as e:
            print(f"Site lookup error: {e}")
            return None
    
    async def _get_drives(self):
        """Get all drives (document libraries) in the site"""
        if not self.site_id:
            await self._get_site_info()
        
        if not self.site_id:
            return []
        
        drives_url = f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/drives"
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.get(drives_url, headers=headers)
            if response.status_code == 200:
                drives_data = response.json()
                drives = drives_data.get('value', [])
                
                # Cache drives for easy lookup
                for drive in drives:
                    self.drives[drive.get('name')] = drive.get('id')
                
                return drives
            else:
                print(f"Drives lookup failed: {response.text}")
                return []
        except Exception as e:
            print(f"Drives lookup error: {e}")
            return []
    
    def sharepoint_list_folders(self, parent_folder: str = None, drive_name: str = "Documents") -> str:
        """
        List folders in SharePoint
        
        Args:
            parent_folder: Parent folder path (optional)
            drive_name: Name of the drive/library (default: Documents)
        
        Returns:
            JSON string with folder information
        """
        return asyncio.run(self._list_folders_async(parent_folder, drive_name))
    
    async def _list_folders_async(self, parent_folder: str = None, drive_name: str = "Documents") -> str:
        """Async implementation of folder listing"""
        try:
            # Get drives if not already loaded
            if not self.drives:
                await self._get_drives()
            
            # Get the specified drive
            drive_id = self.drives.get(drive_name)
            if not drive_id:
                return json.dumps({
                    "error": f"Drive '{drive_name}' not found",
                    "available_drives": list(self.drives.keys())
                })
            
            # Build URL for folder contents
            if parent_folder:
                folders_url = f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/drives/{drive_id}/root:/{parent_folder}:/children"
            else:
                folders_url = f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/drives/{drive_id}/root/children"
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(folders_url, headers=headers)
            
            if response.status_code == 200:
                items_data = response.json()
                items = items_data.get('value', [])
                
                # Filter only folders
                folders = []
                for item in items:
                    if 'folder' in item:
                        folders.append({
                            'name': item.get('name'),
                            'path': f"/{parent_folder}/{item.get('name')}" if parent_folder else f"/{item.get('name')}",
                            'created': item.get('createdDateTime'),
                            'modified': item.get('lastModifiedDateTime'),
                            'id': item.get('id'),
                            'childCount': item.get('folder', {}).get('childCount', 0)
                        })
                
                return json.dumps({
                    'success': True,
                    'drive': drive_name,
                    'parent_folder': parent_folder or 'root',
                    'folders': folders,
                    'count': len(folders)
                }, indent=2)
            else:
                return json.dumps({
                    'error': f"Failed to list folders: {response.status_code}",
                    'details': response.text
                })
                
        except Exception as e:
            return json.dumps({
                'error': f"Exception in list_folders: {str(e)}"
            })
    
    def sharepoint_search_files(self, query: str, drive_name: str = "Documents", file_type: str = None) -> str:
        """
        Search for files in SharePoint
        
        Args:
            query: Search query string
            drive_name: Name of the drive/library (default: Documents)
            file_type: File extension filter (e.g., 'pdf', 'docx')
        
        Returns:
            JSON string with search results
        """
        return asyncio.run(self._search_files_async(query, drive_name, file_type))
    
    async def _search_files_async(self, query: str, drive_name: str = "Documents", file_type: str = None) -> str:
        """Async implementation of file search"""
        try:
            # Get drives if not already loaded
            if not self.drives:
                await self._get_drives()
            
            # Get the specified drive
            drive_id = self.drives.get(drive_name)
            if not drive_id:
                return json.dumps({
                    "error": f"Drive '{drive_name}' not found",
                    "available_drives": list(self.drives.keys())
                })
            
            # Build search URL
            search_url = f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/drives/{drive_id}/root/search(q='{query}')"
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(search_url, headers=headers)
            
            if response.status_code == 200:
                items_data = response.json()
                items = items_data.get('value', [])
                
                # Filter files (not folders) and by file type if specified
                files = []
                for item in items:
                    if 'file' in item:  # Only files, not folders
                        file_name = item.get('name', '')
                        
                        # Apply file type filter if specified
                        if file_type:
                            if not file_name.lower().endswith(f'.{file_type.lower()}'):
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
                
                return json.dumps({
                    'success': True,
                    'query': query,
                    'drive': drive_name,
                    'file_type_filter': file_type,
                    'files': files,
                    'count': len(files)
                }, indent=2)
            else:
                return json.dumps({
                    'error': f"Search failed: {response.status_code}",
                    'details': response.text
                })
                
        except Exception as e:
            return json.dumps({
                'error': f"Exception in search_files: {str(e)}"
            })
    
    def sharepoint_get_drives(self) -> str:
        """
        Get all available drives/document libraries
        
        Returns:
            JSON string with drive information
        """
        return asyncio.run(self._get_drives_async())
    
    async def _get_drives_async(self) -> str:
        """Async implementation of get drives"""
        try:
            drives = await self._get_drives()
            
            drive_info = []
            for drive in drives:
                drive_info.append({
                    'name': drive.get('name'),
                    'id': drive.get('id'),
                    'description': drive.get('description'),
                    'driveType': drive.get('driveType'),
                    'webUrl': drive.get('webUrl')
                })
            
            return json.dumps({
                'success': True,
                'drives': drive_info,
                'count': len(drive_info)
            }, indent=2)
            
        except Exception as e:
            return json.dumps({
                'error': f"Exception in get_drives: {str(e)}"
            })
    
    def sharepoint_get_file_content(self, file_id: str, drive_name: str = "Documents") -> str:
        """
        Get file content/metadata
        
        Args:
            file_id: ID of the file
            drive_name: Name of the drive/library (default: Documents)
        
        Returns:
            JSON string with file information
        """
        return asyncio.run(self._get_file_content_async(file_id, drive_name))
    
    async def _get_file_content_async(self, file_id: str, drive_name: str = "Documents") -> str:
        """Async implementation of get file content"""
        try:
            # Get drives if not already loaded
            if not self.drives:
                await self._get_drives()
            
            # Get the specified drive
            drive_id = self.drives.get(drive_name)
            if not drive_id:
                return json.dumps({
                    "error": f"Drive '{drive_name}' not found",
                    "available_drives": list(self.drives.keys())
                })
            
            # Get file metadata
            file_url = f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/drives/{drive_id}/items/{file_id}"
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(file_url, headers=headers)
            
            if response.status_code == 200:
                file_data = response.json()
                
                file_info = {
                    'name': file_data.get('name'),
                    'size': file_data.get('size'),
                    'created': file_data.get('createdDateTime'),
                    'modified': file_data.get('lastModifiedDateTime'),
                    'id': file_data.get('id'),
                    'downloadUrl': file_data.get('@microsoft.graph.downloadUrl'),
                    'webUrl': file_data.get('webUrl'),
                    'mimeType': file_data.get('file', {}).get('mimeType'),
                    'path': file_data.get('parentReference', {}).get('path', '')
                }
                
                return json.dumps({
                    'success': True,
                    'file': file_info
                }, indent=2)
            else:
                return json.dumps({
                    'error': f"File lookup failed: {response.status_code}",
                    'details': response.text
                })
                
        except Exception as e:
            return json.dumps({
                'error': f"Exception in get_file_content: {str(e)}"
            }) 