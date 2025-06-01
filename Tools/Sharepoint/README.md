# SharePoint Tool

A custom SharePoint tool using Microsoft Graph API that provides folder listing and file search functionality.

## Features

- **List Folders**: Browse SharePoint document library folders
- **Search Files**: Search for files across SharePoint with optional file type filtering
- **Get Drives**: List all available document libraries/drives
- **File Metadata**: Get detailed file information including download URLs

## Setup

### Prerequisites

1. Microsoft Azure App Registration with the following permissions:
   - `Sites.FullControl.All`
   - `Sites.ReadWrite.All`
   - `Files.ReadWrite.All`

2. Required credentials in `MCP/Config/config.json`:
```json
{
  "sharepoint_creds": {
    "tenant_id": "your-tenant-id",
    "client_id": "your-client-id",
    "client_secret": "your-client-secret",
    "site_url": "https://yourcompany.sharepoint.com/sites/yoursite"
  }
}
```

### Installation

```bash
pip install requests
```

## Usage

### Initialize the Tool

```python
from Tools.Sharepoint.tool import SharepointToolkit
import json

# Load credentials
with open('MCP/Config/config.json', 'r') as f:
    config = json.load(f)
    
creds = config['sharepoint_creds']
sp_tool = SharepointToolkit(creds)
```

### Available Methods

#### 1. List Folders

```python
# List folders in root of Documents library
result = sp_tool.sharepoint_list_folders()

# List folders in a specific parent folder
result = sp_tool.sharepoint_list_folders(parent_folder="projects")

# List folders in a different drive
result = sp_tool.sharepoint_list_folders(drive_name="Shared Documents")
```

**Response Format:**
```json
{
  "success": true,
  "drive": "Documents",
  "parent_folder": "root",
  "folders": [
    {
      "name": "Detail",
      "path": "/Detail",
      "created": "2024-01-15T10:30:00Z",
      "modified": "2024-01-20T14:45:00Z",
      "id": "folder-id-123",
      "childCount": 5
    }
  ],
  "count": 1
}
```

#### 2. Search Files

```python
# Basic file search
result = sp_tool.sharepoint_search_files("invoice")

# Search with file type filter
result = sp_tool.sharepoint_search_files("report", file_type="pdf")

# Search in specific drive
result = sp_tool.sharepoint_search_files("contract", drive_name="Legal")
```

**Response Format:**
```json
{
  "success": true,
  "query": "invoice",
  "drive": "Documents",
  "file_type_filter": null,
  "files": [
    {
      "name": "invoice_2024.pdf",
      "path": "/Shared Documents/Invoices",
      "size": 245760,
      "created": "2024-01-15T10:30:00Z",
      "modified": "2024-01-20T14:45:00Z",
      "id": "file-id-456",
      "downloadUrl": "https://...",
      "webUrl": "https://...",
      "mimeType": "application/pdf"
    }
  ],
  "count": 1
}
```

#### 3. Get Available Drives

```python
result = sp_tool.sharepoint_get_drives()
```

**Response Format:**
```json
{
  "success": true,
  "drives": [
    {
      "name": "Documents",
      "id": "drive-id-789",
      "description": "Document Library",
      "driveType": "documentLibrary",
      "webUrl": "https://..."
    }
  ],
  "count": 1
}
```

#### 4. Get File Content/Metadata

```python
result = sp_tool.sharepoint_get_file_content("file-id-456")
```

**Response Format:**
```json
{
  "success": true,
  "file": {
    "name": "document.pdf",
    "size": 245760,
    "created": "2024-01-15T10:30:00Z",
    "modified": "2024-01-20T14:45:00Z",
    "id": "file-id-456",
    "downloadUrl": "https://...",
    "webUrl": "https://...",
    "mimeType": "application/pdf",
    "path": "/Shared Documents/Folder"
  }
}
```

## Testing

Run the test script to verify functionality:

```bash
python Tools/Sharepoint/test_sharepoint_tool.py
```

## Error Handling

All methods return JSON responses with error information when failures occur:

```json
{
  "error": "Drive 'NonExistent' not found",
  "available_drives": ["Documents", "Shared Documents"]
}
```

## Authentication

The tool uses Microsoft Graph API with OAuth 2.0 client credentials flow. It automatically:

1. Authenticates with Azure AD
2. Retrieves access tokens
3. Caches tokens for subsequent requests
4. Handles token refresh automatically

## Supported File Operations

- **Folder Navigation**: Browse folder hierarchies
- **File Search**: Full-text search across all files
- **File Type Filtering**: Filter search results by extension
- **Metadata Retrieval**: Get file properties and URLs
- **Multi-Drive Support**: Work with multiple document libraries

## Limitations

- Uses app-only authentication (no user context)
- Requires appropriate Microsoft Graph permissions
- Search is limited to file names and content indexed by SharePoint
- Large result sets may be paginated (not currently handled)

## Troubleshooting

### Common Issues

1. **Authentication Errors**: Verify credentials and permissions
2. **Drive Not Found**: Check available drives using `sharepoint_get_drives()`
3. **Folder Not Found**: Verify folder path and permissions
4. **Empty Results**: Check if files/folders exist and are accessible

### Debug Mode

Enable debug output by modifying the tool to print response details:

```python
# Add this to see raw API responses
print(f"API Response: {response.text}")
``` 