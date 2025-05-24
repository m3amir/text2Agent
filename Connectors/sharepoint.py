import asyncio
from typing import Optional
from azure.identity.aio import ClientSecretCredential
from kiota_authentication_azure.azure_identity_authentication_provider import (
    AzureIdentityAuthenticationProvider,
)
from kiota_http.kiota_client_factory import KiotaClientFactory
from msgraph.graph_request_adapter import GraphRequestAdapter, options
from msgraph.graph_service_client import GraphServiceClient
from msgraph_core import GraphClientFactory

class SharePoint:
    def __init__(self, credentials, loop=None):
        """Initialize the SharePoint connector without making any async calls."""
        try:
            # Ensure the credentials dictionary contains required keys
            if not all(key in credentials for key in ['tenant_id', 'client_id', 'client_secret']):
                raise ValueError("Missing required credentials: 'tenant_id', 'client_id', or 'client_secret'.")
            
            self.credentials = credentials
            self.tenant = credentials['tenant_id']
            self.loop = loop or asyncio.get_event_loop()
            
            self._credential = ClientSecretCredential(
                tenant_id=self.credentials['tenant_id'],
                client_id=self.credentials['client_id'],
                client_secret=self.credentials['client_secret']
            )
            # Initialize the client here, but avoid immediate async call in constructor
            self.account = self.create_client()

        except Exception as e:
            print(f"Error initializing SharePoint connector: {e}")
            raise

    def get_request_adapter(self, credentials: ClientSecretCredential, scopes: Optional[list[str]] = None) -> GraphRequestAdapter:
        if scopes:
            auth_provider = AzureIdentityAuthenticationProvider(credentials=credentials, scopes=scopes)
        else:
            auth_provider = AzureIdentityAuthenticationProvider(credentials=credentials)

        return GraphRequestAdapter(
            auth_provider=auth_provider,
            client=GraphClientFactory.create_with_default_middleware(
                options=options, client=KiotaClientFactory.get_default_client()
            ),
        )

    def create_client(self) -> GraphServiceClient:
        """Create a new client with a new event loop if needed."""
        return GraphServiceClient(
            request_adapter=self.get_request_adapter(
                credentials=self._credential, scopes=['https://graph.microsoft.com/.default']
            )
        )

    async def me(self):
        """Get the me endpoint."""
        try:
            # Ensure we're using a valid event loop
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                print("Creating new event loop for SharePoint me() operation")
                asyncio.set_event_loop(asyncio.new_event_loop())
            
            # Initialize the account client dynamically for the async context
            self.account = self.create_client()

            # Fetch 'me' endpoint
            me_info = await self.account.me.get()
            return me_info
        except Exception as e:
            print(f"Error in me() operation: {e}")
            return None

    async def list_permissions(self):
        """List permissions for SharePoint."""
        try:
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                print("Creating new event loop for SharePoint operation")
                asyncio.set_event_loop(asyncio.new_event_loop())
            
            # Initialize the account client dynamically for the async context
            self.account = self.create_client()

            # Fetch permissions
            response = await self.account.oauth2_permission_grants.get()
            if not hasattr(response, 'value') or not response.value:
                print("No permission grants found.")
                return []

            all_scopes = []
            for grant in response.value:
                if grant.scope:
                    all_scopes.extend(grant.scope.split())

            # Filter unique permissions and relevant scopes
            unique_scopes = list(set(all_scopes))
            filtered_permissions = [
                permission for permission in unique_scopes
                if len(permission.split('.')) > 1 and permission.split('.')[1] in ['Read', 'Write']
            ]

            return filtered_permissions

        except Exception as e:
            print(f"Error fetching permissions: {e}")
            return []

# # Usage Example
# async def main():
#     credentials = {
#         'tenant_id': "your-tenant-id",
#         'client_id': "your-client-id",
#         'client_secret': "your-client-secret",
#     }

#     try:
#         sp = SharePoint(credentials)
        
#         # List permissions within a new event loop context
#         permissions = await sp.list_permissions()
#         print("Permissions:", permissions)

#     except Exception as e:
#         print("Exception during execution:", e)

# # Run the main async function
# if __name__ == "__main__":
#     asyncio.run(main())
