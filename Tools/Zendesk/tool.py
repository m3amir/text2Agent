"""
Zendesk Tool using zenpy library
Provides ticket management, user management, and search functionality
"""
import json
from typing import Optional, Dict, List, Any, Union
from datetime import datetime, timedelta

try:
    from zenpy import Zenpy
    from zenpy.lib.api_objects import Ticket, User, Organization, Comment
    from zenpy.lib.exception import ZenpyException
except ImportError:
    print("zenpy library not installed. Run: pip install zenpy")
    Zenpy = None

class ZendeskToolkit:
    """Zendesk toolkit using zenpy library"""
    
    def __init__(self, credentials: Dict[str, str]):
        """Initialize with credentials"""
        if not Zenpy:
            raise ImportError("zenpy library is required. Install with: pip install zenpy")
        
        self.subdomain = credentials.get('subdomain')
        self.email = credentials.get('email')
        self.token = credentials.get('token')
        
        # Validate required credentials
        if not all([self.subdomain, self.email, self.token]):
            raise ValueError("Missing required Zendesk credentials: subdomain, email, token")
        
        # Initialize Zenpy client
        try:
            self.zenpy_client = Zenpy(
                subdomain=self.subdomain,
                email=self.email,
                token=self.token
            )
            
            # Test connection
            self.zenpy_client.users.me()
            
        except Exception as e:
            raise ValueError(f"Failed to connect to Zendesk: {str(e)}")
    
    def zendesk_get_tickets(self, status: str = None, priority: str = None, limit: int = 25) -> str:
        """
        Get tickets with optional filtering
        
        Args:
            status: Filter by ticket status (new, open, pending, hold, solved, closed)
            priority: Filter by priority (low, normal, high, urgent)
            limit: Maximum number of tickets to return (default: 25)
        
        Returns:
            JSON string with ticket information
        """
        try:
            # Build search query
            query_parts = []
            if status:
                query_parts.append(f"status:{status}")
            if priority:
                query_parts.append(f"priority:{priority}")
            
            tickets = []
            
            if query_parts:
                # Use search API for filtered results
                query = " ".join(query_parts)
                search_results = self.zenpy_client.search(type='ticket', query=query)
                for i, ticket in enumerate(search_results):
                    if i >= limit:
                        break
                    tickets.append(self._format_ticket(ticket))
            else:
                # Get recent tickets
                for i, ticket in enumerate(self.zenpy_client.tickets()):
                    if i >= limit:
                        break
                    tickets.append(self._format_ticket(ticket))
            
            return json.dumps({
                'success': True,
                'filters': {
                    'status': status,
                    'priority': priority,
                    'limit': limit
                },
                'tickets': tickets,
                'count': len(tickets)
            }, indent=2)
            
        except Exception as e:
            return json.dumps({
                'error': f"Failed to get tickets: {str(e)}"
            })
    
    def zendesk_get_ticket_details(self, ticket_id: int) -> str:
        """
        Get detailed information about a specific ticket
        
        Args:
            ticket_id: ID of the ticket
        
        Returns:
            JSON string with detailed ticket information
        """
        try:
            ticket = self.zenpy_client.tickets(id=ticket_id)
            
            # Get comments
            comments = []
            for comment in self.zenpy_client.tickets.comments(ticket=ticket):
                comments.append({
                    'id': comment.id,
                    'author_id': comment.author_id,
                    'body': comment.body,
                    'created_at': str(comment.created_at),
                    'public': comment.public,
                    'type': comment.type
                })
            
            # Get requester info
            requester = None
            if ticket.requester_id:
                try:
                    user = self.zenpy_client.users(id=ticket.requester_id)
                    requester = self._format_user(user)
                except:
                    requester = {'id': ticket.requester_id, 'name': 'Unknown'}
            
            # Get assignee info
            assignee = None
            if ticket.assignee_id:
                try:
                    user = self.zenpy_client.users(id=ticket.assignee_id)
                    assignee = self._format_user(user)
                except:
                    assignee = {'id': ticket.assignee_id, 'name': 'Unknown'}
            
            ticket_details = self._format_ticket(ticket)
            ticket_details.update({
                'comments': comments,
                'comments_count': len(comments),
                'requester': requester,
                'assignee': assignee
            })
            
            return json.dumps({
                'success': True,
                'ticket': ticket_details
            }, indent=2)
            
        except Exception as e:
            return json.dumps({
                'error': f"Failed to get ticket details: {str(e)}"
            })
    
    def zendesk_create_ticket(self, subject: str, description: str, requester_email: str = None, 
                            priority: str = "normal", ticket_type: str = "question", 
                            tags: List[str] = None) -> str:
        """
        Create a new ticket
        
        Args:
            subject: Ticket subject
            description: Ticket description
            requester_email: Email of the requester (optional)
            priority: Ticket priority (low, normal, high, urgent)
            ticket_type: Ticket type (problem, incident, question, task)
            tags: List of tags to add to the ticket
        
        Returns:
            JSON string with created ticket information
        """
        try:
            # Create ticket object
            ticket_data = {
                'subject': subject,
                'description': description,
                'priority': priority,
                'type': ticket_type
            }
            
            if requester_email:
                ticket_data['requester'] = {'email': requester_email}
            
            if tags:
                ticket_data['tags'] = tags
            
            ticket = Ticket(**ticket_data)
            
            # Create the ticket
            created_ticket = self.zenpy_client.tickets.create(ticket)
            
            return json.dumps({
                'success': True,
                'ticket': self._format_ticket(created_ticket)
            }, indent=2)
            
        except Exception as e:
            return json.dumps({
                'error': f"Failed to create ticket: {str(e)}"
            })
    
    def zendesk_update_ticket(self, ticket_id: int, status: str = None, priority: str = None, 
                            assignee_email: str = None, comment: str = None, 
                            public_comment: bool = True) -> str:
        """
        Update a ticket
        
        Args:
            ticket_id: ID of the ticket to update
            status: New status (new, open, pending, hold, solved, closed)
            priority: New priority (low, normal, high, urgent)
            assignee_email: Email of the user to assign the ticket to
            comment: Comment to add to the ticket
            public_comment: Whether the comment should be public
        
        Returns:
            JSON string with updated ticket information
        """
        try:
            # Get the ticket
            ticket = self.zenpy_client.tickets(id=ticket_id)
            
            # Update fields
            if status:
                ticket.status = status
            if priority:
                ticket.priority = priority
            
            if assignee_email:
                # Find user by email
                users = self.zenpy_client.search(type='user', query=f"email:{assignee_email}")
                user_list = list(users)
                if user_list:
                    ticket.assignee_id = user_list[0].id
                else:
                    return json.dumps({
                        'error': f"User with email {assignee_email} not found"
                    })
            
            if comment:
                ticket.comment = Comment(body=comment, public=public_comment)
            
            # Update the ticket
            updated_ticket = self.zenpy_client.tickets.update(ticket)
            
            return json.dumps({
                'success': True,
                'ticket': self._format_ticket(updated_ticket)
            }, indent=2)
            
        except Exception as e:
            return json.dumps({
                'error': f"Failed to update ticket: {str(e)}"
            })
    
    def zendesk_search_tickets(self, query: str, limit: int = 25) -> str:
        """
        Search tickets using Zendesk search API
        
        Args:
            query: Search query (can include various filters)
            limit: Maximum number of results to return
        
        Returns:
            JSON string with search results
        """
        try:
            search_results = self.zenpy_client.search(type='ticket', query=query)
            
            tickets = []
            for i, ticket in enumerate(search_results):
                if i >= limit:
                    break
                tickets.append(self._format_ticket(ticket))
            
            return json.dumps({
                'success': True,
                'query': query,
                'tickets': tickets,
                'count': len(tickets)
            }, indent=2)
            
        except Exception as e:
            return json.dumps({
                'error': f"Search failed: {str(e)}"
            })
    
    def zendesk_get_users(self, role: str = None, limit: int = 25) -> str:
        """
        Get users with optional role filtering
        
        Args:
            role: Filter by user role (end-user, agent, admin)
            limit: Maximum number of users to return
        
        Returns:
            JSON string with user information
        """
        try:
            users = []
            
            if role:
                # Search users by role
                search_results = self.zenpy_client.search(type='user', query=f"role:{role}")
                for i, user in enumerate(search_results):
                    if i >= limit:
                        break
                    users.append(self._format_user(user))
            else:
                # Get all users
                for i, user in enumerate(self.zenpy_client.users()):
                    if i >= limit:
                        break
                    users.append(self._format_user(user))
            
            return json.dumps({
                'success': True,
                'filters': {'role': role, 'limit': limit},
                'users': users,
                'count': len(users)
            }, indent=2)
            
        except Exception as e:
            return json.dumps({
                'error': f"Failed to get users: {str(e)}"
            })
    
    def zendesk_get_user_details(self, user_id: int) -> str:
        """
        Get detailed information about a specific user
        
        Args:
            user_id: ID of the user
        
        Returns:
            JSON string with detailed user information
        """
        try:
            user = self.zenpy_client.users(id=user_id)
            
            # Get user's tickets
            user_tickets = []
            tickets = self.zenpy_client.search(type='ticket', query=f"requester:{user.email}")
            for i, ticket in enumerate(tickets):
                if i >= 10:  # Limit to 10 recent tickets
                    break
                user_tickets.append(self._format_ticket(ticket))
            
            user_details = self._format_user(user)
            user_details.update({
                'recent_tickets': user_tickets,
                'ticket_count': len(user_tickets)
            })
            
            return json.dumps({
                'success': True,
                'user': user_details
            }, indent=2)
            
        except Exception as e:
            return json.dumps({
                'error': f"Failed to get user details: {str(e)}"
            })
    
    def zendesk_create_user(self, name: str, email: str, role: str = "end-user", 
                          phone: str = None, organization_id: int = None) -> str:
        """
        Create a new user
        
        Args:
            name: User's name
            email: User's email address
            role: User role (end-user, agent, admin)
            phone: User's phone number (optional)
            organization_id: ID of the organization (optional)
        
        Returns:
            JSON string with created user information
        """
        try:
            user_data = {
                'name': name,
                'email': email,
                'role': role
            }
            
            if phone:
                user_data['phone'] = phone
            if organization_id:
                user_data['organization_id'] = organization_id
            
            user = User(**user_data)
            created_user = self.zenpy_client.users.create(user)
            
            return json.dumps({
                'success': True,
                'user': self._format_user(created_user)
            }, indent=2)
            
        except Exception as e:
            return json.dumps({
                'error': f"Failed to create user: {str(e)}"
            })
    
    def zendesk_get_organizations(self, limit: int = 25) -> str:
        """
        Get organizations
        
        Args:
            limit: Maximum number of organizations to return
        
        Returns:
            JSON string with organization information
        """
        try:
            organizations = []
            
            for i, org in enumerate(self.zenpy_client.organizations()):
                if i >= limit:
                    break
                organizations.append(self._format_organization(org))
            
            return json.dumps({
                'success': True,
                'organizations': organizations,
                'count': len(organizations)
            }, indent=2)
            
        except Exception as e:
            return json.dumps({
                'error': f"Failed to get organizations: {str(e)}"
            })
    
    def zendesk_get_ticket_stats(self, days: int = 30) -> str:
        """
        Get ticket statistics for the specified number of days
        
        Args:
            days: Number of days to look back for statistics
        
        Returns:
            JSON string with ticket statistics
        """
        try:
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Search for tickets in date range
            query = f"created>={start_date.strftime('%Y-%m-%d')}"
            tickets = list(self.zenpy_client.search(type='ticket', query=query))
            
            # Calculate statistics
            stats = {
                'total_tickets': len(tickets),
                'by_status': {},
                'by_priority': {},
                'by_type': {},
                'by_assignee': {}
            }
            
            for ticket in tickets:
                # Count by status
                status = ticket.status or 'unknown'
                stats['by_status'][status] = stats['by_status'].get(status, 0) + 1
                
                # Count by priority
                priority = ticket.priority or 'unknown'
                stats['by_priority'][priority] = stats['by_priority'].get(priority, 0) + 1
                
                # Count by type
                ticket_type = ticket.type or 'unknown'
                stats['by_type'][ticket_type] = stats['by_type'].get(ticket_type, 0) + 1
                
                # Count by assignee
                assignee = 'unassigned'
                if ticket.assignee_id:
                    try:
                        user = self.zenpy_client.users(id=ticket.assignee_id)
                        assignee = user.name
                    except:
                        assignee = f"User {ticket.assignee_id}"
                
                stats['by_assignee'][assignee] = stats['by_assignee'].get(assignee, 0) + 1
            
            return json.dumps({
                'success': True,
                'date_range': {
                    'start_date': start_date.strftime('%Y-%m-%d'),
                    'end_date': end_date.strftime('%Y-%m-%d'),
                    'days': days
                },
                'statistics': stats
            }, indent=2)
            
        except Exception as e:
            return json.dumps({
                'error': f"Failed to get ticket statistics: {str(e)}"
            })
    
    def _format_ticket(self, ticket) -> Dict[str, Any]:
        """Format ticket object for JSON serialization"""
        return {
            'id': ticket.id,
            'subject': ticket.subject,
            'description': ticket.description,
            'status': ticket.status,
            'priority': ticket.priority,
            'type': ticket.type,
            'requester_id': ticket.requester_id,
            'assignee_id': ticket.assignee_id,
            'organization_id': ticket.organization_id,
            'created_at': str(ticket.created_at) if ticket.created_at else None,
            'updated_at': str(ticket.updated_at) if ticket.updated_at else None,
            'tags': ticket.tags,
            'url': ticket.url
        }
    
    def _format_user(self, user) -> Dict[str, Any]:
        """Format user object for JSON serialization"""
        return {
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'role': user.role,
            'phone': user.phone,
            'organization_id': user.organization_id,
            'created_at': str(user.created_at) if user.created_at else None,
            'updated_at': str(user.updated_at) if user.updated_at else None,
            'active': user.active,
            'time_zone': user.time_zone,
            'url': user.url
        }
    
    def _format_organization(self, org) -> Dict[str, Any]:
        """Format organization object for JSON serialization"""
        return {
            'id': org.id,
            'name': org.name,
            'domain_names': org.domain_names,
            'details': org.details,
            'notes': org.notes,
            'created_at': str(org.created_at) if org.created_at else None,
            'updated_at': str(org.updated_at) if org.updated_at else None,
            'url': org.url
        } 