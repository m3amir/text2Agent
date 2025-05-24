import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../", "")))
from Global.runner import Runner
from Connectors import zendesk
from Prompts.Zendesk.System import system as article_system
from Tools._Tool import Tool
from utils.imports import *
from zenpy.lib.exception import RecordNotFoundException
from zenpy.lib.api_objects import Ticket, Comment
from typing import Dict, List, Optional, Union
import logging
import json
import re

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

# Get logger for this module
logger = logging.getLogger(__name__)

description = "This connector provides access to the customer service platform Zendesk. It is specifically designed to handle customer-initiated service tickets—enabling the creation, retrieval, and updating of tickets, as well as the addition of comments to those tickets. This ensures streamlined management of inquiries and support requests submitted directly by customers."

system = """
You are an AI assistant tasked with identifying the most relevant help articles based on a given support ticket. You will receive:

A support ticket containing a brief description of the issue.
Metadata and an excerpt from several candidate help articles.
Your goal is to determine which articles are relevant to the ticket and return a list of relevant article titles.

You must NOT rank the articles—only return a list of those that are directly relevant.
Articles should be considered relevant if they directly address the issue in the ticket.
If an article is not relevant, it should be excluded from the list, even if it shares some keywords.

Sample Output (Only Relevant Articles, No Ranking):
[
    "Article Title 1",
    "Article Title 2"
]
"""

class toolKit(Tool):
    def __init__(self, credentials, permissions=None):
        super().__init__(permissions=permissions)
        self.__name__ = "zendesk"
        
        # Log permissions received
        if permissions:
            print(f"Zendesk permissions: {permissions}")
        try:
            self.client = zendesk.Zendesk(credentials).client
        except Exception as fallback_error:
            print(f"ERROR: Both Zendesk client initialization methods failed: {fallback_error}")
            # Re-raise to allow proper error handling
            raise
                
        self.runner = Runner('', system)

    def _get_tickets(self, limit: Optional[int] = None):
        """
        Retrieve tickets from Zendesk with specific fields.

        Args:
            limit (int, optional): Maximum number of tickets to retrieve

        """
        try:
            tickets = []
            for idx, ticket in enumerate(self.client.tickets()):
                if limit and idx >= limit:
                    break

                # Create a structured dictionary with only the required fields
                ticket_data = {
                    'id': getattr(ticket, 'id', None),
                    'assignee_id': getattr(ticket, 'assignee_id', None),
                    'requester_id': getattr(ticket, 'requester_id', None),
                    'subject': getattr(ticket, 'subject', ''),
                    'description': getattr(ticket, 'description', ''),
                    'status': getattr(ticket, 'status', ''),
                    'priority': getattr(ticket, 'priority', None),
                    'tags': getattr(ticket, 'tags', []),
                    'updated_at': getattr(ticket, 'updated_at', ''),
                    'created_at': getattr(ticket, 'created_at', ''),
                    'url': getattr(ticket, 'url', ''),
                    'type': getattr(ticket, 'type', None)
                }
                tickets.append(ticket_data)

            return tickets
        except Exception as e:
            print(f"Failed to retrieve tickets: {str(e)}")

    def zendesk_create_ticket_creation(self, subject: str, description: str,
                      priority: str = "normal",
                      tags: List[str] = None):
        """
        Create a new ticket in Zendesk.

        Args:
            subject (str): Ticket subject
            description (str): Ticket description/body
            priority (str): Ticket priority (urgent, high, normal, low)
            tags (List[str], optional): List of tags to apply to the ticket

        Returns:
            Dict: Created ticket information

        Raises:
            ZendeskError: If ticket creation fails
        """
        try:
            ticket = Ticket(
                subject=subject,
                description=description,
                priority=priority,
                tags=tags or []
            )
            response = self.client.tickets.create(ticket)
            return response._to_dict()
        except Exception as e:
            print(f"Failed to create ticket: {str(e)}")
            
    def zendesk_add_comment_admin(self, ticket_id: Union[str, int], comment: str):
        """
        Add a comment to an existing ticket.

        Args:
            ticket_id (Union[str, int]): ID of the zendesk ticket
            comment (str): Comment text

        Returns:
            Dict: Updated ticket information

        Raises:
            ZendeskError: If comment addition fails
        """
        try:
            ticket = self.client.tickets(id=int(ticket_id))
            if not ticket:
                print(f"Ticket {ticket_id} not found")
            ticket.comment = Comment(
                body=comment,
            )
            response = self.client.tickets.update(ticket)
            return response._to_dict()
        except RecordNotFoundException:
            return f"I have not been able to add the comment to the ticket due to the following error: Ticket {ticket_id} not found"
            print(f"Ticket {ticket_id} not found")
        except Exception as e:
            return f"I have not been able to add the comment to the ticket due to the following error: {str(e)}"

    def zendesk_get_ticket_retrieval(self, ticket_id: Union[str, int]):
        """
        Retrieve a specific ticket by ID.

        Args:
            ticket_id (Union[str, int]): ID of the ticket to retrieve

        Returns:
            Dict: Ticket information

        Raises:
            ZendeskError: If ticket retrieval fails
        """
        try:
            ticket = self.client.tickets(id=ticket_id)
            ticket = {
                'id': getattr(ticket, 'id', None),
                'subject': getattr(ticket, 'subject', ''),
                'description': getattr(ticket, 'description', ''),
                'created_at': str(getattr(ticket, 'created_at', '')),
                'updated_at': str(getattr(ticket, 'updated_at', '')),
                'status': getattr(ticket, 'status', ''),
                'priority': getattr(ticket, 'priority', None),
                'tags': list(getattr(ticket, 'tags', []))
            }
            
            return ticket
        except RecordNotFoundException:
            print(f"Ticket {ticket_id} not found")
        except Exception as e:
            print(f"Failed to retrieve ticket: {str(e)}")

    def _get_users(self):
        """
        Retrieve all users from Zendesk.

        Returns:
            List[Dict]: List of user dictionaries

        """
        users = self.client.users()
        users_list = []
        for user in users:
            users_list.append(user._to_dict())
        return users

    def _get_user(self, user_id: Union[str, int]):
        """
        Retrieve a specific user by ID.

        Args:
            user_id (Union[str, int]): ID of the user to retrieve

        """
        return self.client.users(id=user_id)

    def zendesk_get_customer_tickets_retrieval(self, customer_identifier: Union[str, int]) -> List[Dict]:
        """
        Retrieve all historic tickets from a specific customer.

        Args:
            customer_identifier (Union[str, int]): Customer's email address or user ID

        Returns:
            List[Dict]: List of ticket dictionaries with full details

        Raises:
            ZendeskError: If ticket retrieval fails
        """
        try:
            # Determine if the identifier is an email or user ID
            if isinstance(customer_identifier, str) and '@' in customer_identifier:
                # Search for user by email
                user = None
                for u in self.client.users():
                    if getattr(u, 'email', '').lower() == customer_identifier.lower():
                        user = u
                        break
                
                if not user:
                    print(f"User with email {customer_identifier} not found")
                    return []
                
                customer_id = user.id
            else:
                # Assume it's a user ID
                try:
                    user = self.client.users(id=customer_identifier)
                    customer_id = user.id
                except RecordNotFoundException:
                    print(f"User with ID {customer_identifier} not found")
                    return []
            
            # Search for tickets where the user is the requester
            tickets = []
            for ticket in self.client.search(type='ticket', requester_id=customer_id):
                # Create a structured dictionary with only the required fields
                ticket_data = {
                    'id': getattr(ticket, 'id', None),
                    'assignee_id': getattr(ticket, 'assignee_id', None),
                    'requester_id': getattr(ticket, 'requester_id', None),
                    'subject': getattr(ticket, 'subject', ''),
                    'description': getattr(ticket, 'description', ''),
                    'status': getattr(ticket, 'status', ''),
                    'priority': getattr(ticket, 'priority', None),
                    'tags': getattr(ticket, 'tags', []),
                    'updated_at': getattr(ticket, 'updated_at', ''),
                    'created_at': getattr(ticket, 'created_at', ''),
                    'url': getattr(ticket, 'url', ''),
                    'type': getattr(ticket, 'type', None)
                }
                tickets.append(ticket_data)
            
            return tickets
            
        except Exception as e:
            print(f"Failed to retrieve customer tickets: {str(e)}")
            return []

    def _get_user_tickets(self, user: dict):
        """
        Retrieve all tickets assigned to a specific user.

        Args:
            user (dict): User dictionary containing user information

        """
        username = user._to_dict()['name']
        tickets = []
        for ticket in self.client.search(type='ticket', assignee=username):
            tickets.append(ticket._to_dict())
        return tickets

    def _update_ticket_status(self, ticket_id: Union[str, int],
                              status: str):
        """
        Update the status of a specific ticket.

        Args:
            ticket_id (Union[str, int]): ID of the ticket to update
            status (str): New status for the ticket
        """
        try:
            ticket = self.client.tickets(id=ticket_id)
            ticket.status = status
            response = self.client.tickets.update(ticket)
            return response._to_dict()
        except RecordNotFoundException:
            print(f"Ticket {ticket_id} not found")
        except Exception as e:
            print(f"Failed to update ticket status: {str(e)}")

    def _update_ticket_collaborators(self, ticket_id: Union[str, int],
                                     collaborator_ids: List[Union[str, int]]):
        """
        Update the collaborators of a specific ticket.

        Args:
            ticket_id (Union[str, int]): ID of the ticket to update
            collaborator_ids (List[Union[str, int]]): List of user IDs to add as collaborators
        """
        try:
            ticket = self.client.tickets(id=ticket_id)
            ticket.collaborator_ids = collaborator_ids
            response = self.client.tickets.update(ticket)
            return response._to_dict()
        except RecordNotFoundException:
            print(f"Ticket {ticket_id} not found")
        except Exception as e:
            print(f"Failed to update ticket collaborators: {str(e)}")

    def zendesk_upload_attachment_admin(self, ticket_id: Union[str, int], file_path: str, comment: str = "File attached"):
        """
        Upload a file attachment to a Zendesk ticket with an optional comment.

        Args:
            ticket_id (Union[str, int]): ID of the ticket to attach the file to
            file_path (str): Full path to the file to be uploaded
            comment (str, optional): Comment text to accompany the attachment. Defaults to "File attached"

        Returns:
            Dict: Updated ticket information with the attachment

        Raises:
            ZendeskError: If file upload or ticket update fails
            FileNotFoundError: If the specified file does not exist
        """
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")

            # Upload the file and get the upload instance
            upload_instance = self.client.attachments.upload(file_path)

            # Attach the file to the ticket with a comment
            ticket = self.client.tickets(id=ticket_id)
            ticket.comment = Comment(
                body=comment,
                uploads=[upload_instance.token]
            )

            # Update the ticket with the attachment
            response = self.client.tickets.update(ticket)
            return response._to_dict()

        except RecordNotFoundException:
            print(f"Ticket {ticket_id} not found")
        except FileNotFoundError as e:
            raise e
        except Exception as e:
            print(f"Failed to upload attachment: {str(e)}")

    def zendesk_get_help_center_categories_retrieval(self) -> List[Dict]:
        """
        Retrieve all categories from the Help Center.

        Returns:
            List[Dict]: List of category dictionaries

        Raises:
            ZendeskError: If category retrieval fails
        """
        try:
            categories = []
            for category in self.client.help_center.categories():
                categories.append(category._to_dict())
            return categories
        except Exception as e:
            print(f"Failed to retrieve help center categories: {str(e)}")

    def zendesk_get_category_sections_retrieval(self, category_id: Union[str, int]) -> List[Dict]:
        """
        Retrieve all sections in a specific category.

        Args:
            category_id (Union[str, int]): ID of the category

        Returns:
            List[Dict]: List of section dictionaries with full details

        Raises:
            ZendeskError: If section retrieval fails
        """
        try:
            sections = []
            category_sections = self.client.help_center.sections(
                category_id=category_id)
            for section in category_sections:
                section_data = {
                    'id': section.id,
                    'name': section.name,
                    'category_id': section.category_id
                }
                sections.append(section_data)
            return sections
        except Exception as e:
            print(f"Failed to retrieve sections: {str(e)}")

    def zendesk_get_section_articles_retrieval(self, section_id: Union[str, int]) -> List[Dict]:
        """
        Retrieve all articles in a specific section.

        Args:
            section_id (Union[str, int]): ID of the section

        Returns:
            List[Dict]: List of article dictionaries with first 2 sentences of body

        Raises:
            ZendeskError: If article retrieval fails
        """
        try:
            articles = []
            for article in self.client.help_center.articles():
                if str(article.section_id) == str(section_id):
                    article_data = {
                        'id': article.id,
                        'title': article.title,
                        'body': self._strip_html(article.body) if article.body else '',
                        'html_url': article.html_url,
                        'section_id': article.section_id,
                        'locale': article.locale
                    }
                    articles.append(article_data)
            return articles
        except Exception as e:
            print(f"Failed to retrieve articles: {str(e)}")

    def zendesk_get_article_content_retrieval(self, article_id: Union[str, int]) -> Dict:
        """
        Retrieve the full content of a specific article, including its body text and metadata.

        Args:
            article_id (Union[str, int]): ID of the article to retrieve

        Returns:
            Dict: Article information including title, body text, and comprehensive metadata

        Raises:
            ZendeskError: If article retrieval fails
        """
        try:
            article = self.client.help_center.articles(id=article_id)
            # Convert to dictionary and ensure all required fields are present with metadata
            article_dict = {
                'id': getattr(article, 'id', None),
                'title': getattr(article, 'title', ''),
                'body': getattr(article, 'body', ''),
                'html_url': getattr(article, 'html_url', ''),
                'section_id': getattr(article, 'section_id', None),
                'locale': getattr(article, 'locale', ''),
                'author_id': getattr(article, 'author_id', None),
                'comments_disabled': getattr(article, 'comments_disabled', False),
                'label_names': getattr(article, 'label_names', []),
                'draft': getattr(article, 'draft', False),
                'promoted': getattr(article, 'promoted', False),
                'position': getattr(article, 'position', 0),
                'vote_sum': getattr(article, 'vote_sum', 0),
                'vote_count': getattr(article, 'vote_count', 0),
                'created_at': getattr(article, 'created_at', ''),
                'updated_at': getattr(article, 'updated_at', ''),
                'edited_at': getattr(article, 'edited_at', ''),
                'name': getattr(article, 'name', ''),
                'source_locale': getattr(article, 'source_locale', ''),
                'outdated': getattr(article, 'outdated', False),
                'outdated_locales': getattr(article, 'outdated_locales', []),
                'permission_group_id': getattr(article, 'permission_group_id', None)
            }
            return article_dict
        except RecordNotFoundException:
            print(f"Article {article_id} not found")
        except Exception as e:
            print(f"Failed to retrieve article: {str(e)}")

    def zendesk_list_section_names_retrieval(self) -> List[str]:
        """
        Get a list of all section names.

        Returns:
            List[str]: List of section names
        """
        try:
            sections = set()
            categories = self.zendesk_get_help_center_categories_retrieval()
            for category in categories:
                category_sections = self.zendesk_get_category_sections_retrieval(category['id'])
                for section in category_sections:
                    sections.add(section['name'])
            return sorted(list(sections))
        except Exception as e:
            print(f"Failed to retrieve section names: {str(e)}")

    def zendesk_search_section_articles_retrieval(self, section_name: str) -> List[Dict]:
        """
        Search for relevant articles in a specific section.

        Args:
            section_name (str): Name of the section to search in

        Returns:
            List[Dict]: List of relevant articles with comprehensive metadata
        """
        try:
            # Step 1: Get all articles in the section
            matching_articles = []
            categories = self.zendesk_get_help_center_categories_retrieval()
            for category in categories:
                sections = self.zendesk_get_category_sections_retrieval(category['id'])
                for section in sections:
                    if section['name'].lower() == section_name.lower():
                        articles = self.zendesk_get_section_articles_retrieval(section['id'])
                        matching_articles.extend(articles)

            if not matching_articles:
                print(f"No articles found in section: {section_name}")
                return []

            # Step 2: Get AI recommendations for relevant articles
            # Format articles with metadata for AI evaluation
            articles_for_ai = []
            for article in matching_articles:
                article_info = {
                    'title': article.get('title', ''),
                    'body': article.get('body', ''),
                    'vote_sum': article.get('vote_sum', 0),
                    'vote_count': article.get('vote_count', 0),
                    'created_at': article.get('created_at', ''),
                    'updated_at': article.get('updated_at', ''),
                    'promoted': article.get('promoted', False),
                    'label_names': article.get('label_names', [])
                }
                articles_for_ai.append(article_info)

            human_message = f"Ticket: how can i return my purchase \n\nArticles (with metadata): {json.dumps(articles_for_ai, indent=2)}"
            relevant_titles = self._parse_runner_response(
                self.runner.start_runner(human_message=human_message))
            # Step 3: Parse AI response to get relevant article titles
            try:
                if isinstance(relevant_titles, str):
                    try:
                        relevant_titles = json.loads(
                            relevant_titles.replace("'", '"'))
                    except json.JSONDecodeError:
                        titles = re.findall(
                            r'["\'](.*?)[\'"]\s*,?|\[(.*?)\]', relevant_titles)
                        relevant_titles = [t[0] or t[1]
                                           for t in titles if t[0] or t[1]]

                if not isinstance(relevant_titles, list):
                    relevant_titles = [relevant_titles]

                if not relevant_titles:
                    print("No relevant articles identified by AI")
                    return []

            except Exception as e:
                print(f"Warning: Error parsing AI response: {str(e)}")
                return []

            # Step 4: Get full content for relevant articles
            relevant_articles = []
            for article in matching_articles:
                try:
                    if article.get('title') in relevant_titles:
                        # Get full article content and create standardized dictionary
                        full_article = self.get_article_content(article['id'])
                        # Include ALL metadata fields in the returned dictionary
                        article_dict = {
                            'id': full_article['id'],
                            'title': full_article['title'],
                            'body': self._strip_html(full_article['body']) if full_article.get('body') else '',
                            'html_url': full_article['html_url'],
                            'section_id': full_article['section_id'],
                            'locale': full_article['locale'],
                            'author_id': full_article['author_id'],
                            'comments_disabled': full_article['comments_disabled'],
                            'label_names': full_article['label_names'],
                            'draft': full_article['draft'],
                            'promoted': full_article['promoted'],
                            'position': full_article['position'],
                            'vote_sum': full_article['vote_sum'],
                            'vote_count': full_article['vote_count'],
                            'created_at': full_article['created_at'],
                            'updated_at': full_article['updated_at'],
                            'edited_at': full_article['edited_at'],
                            'name': full_article['name'],
                            'source_locale': full_article['source_locale'],
                            'outdated': full_article['outdated'],
                            'outdated_locales': full_article['outdated_locales'],
                            'permission_group_id': full_article['permission_group_id']
                        }

                        # Validate all required fields are present
                        required_fields = ['id', 'title', 'body', 'html_url', 'section_id', 'locale',
                                           'vote_sum', 'vote_count', 'created_at', 'updated_at']
                        if not all(key in article_dict for key in required_fields):
                            print(
                                f"Warning: Article {article['id']} is missing required fields")
                            continue

                        relevant_articles.append(article_dict)
                except (KeyError, AttributeError) as e:
                    print(f"Warning: Error processing article data: {str(e)}")
                    continue

            print(f"Found {len(relevant_articles)} relevant articles")
            return relevant_articles

        except Exception as e:
            print(f"⚠️  Error: {str(e)}")
            return []

    def _strip_html(self, html_content: str) -> str:
        """
        Strip HTML tags from a string.

        Args:
            html_content (str): String containing HTML tags

        """
        try:
            clean = re.compile('<.*?>')
            return re.sub(clean, '', html_content)
        except Exception:
            return html_content

    def zendesk_get_relevant_help_articles_retrieval(self, query: str) -> Dict[str, List[Dict]]:
        """
        Orchestrates the flow of searching for relevant help articles across all sections.

        Args:
            query (str): The search query/ticket description to find relevant articles for

        Returns:
            Dict[str, List[Dict]]: Dictionary mapping section names to lists of relevant articles.
            Each article is a dictionary containing:
                - id: Article ID
                - title: Article title
                - body: Article content (HTML stripped)
                - html_url: Article URL
                - section_id: Section ID
                - locale: Article language
        """
        try:
            sections = self.zendesk_list_section_names_retrieval()

            results = {}
            for section_name in sections:
                # Get relevant articles for this section
                articles = self.search_section_articles(section_name)
                if articles:
                    results[section_name] = articles
                else:
                    print(f"No relevant articles found in {section_name}")

            return results

        except Exception as e:
            print(f"⚠️  Error searching for help articles: {str(e)}")
            return {}

    def _parse_runner_response(self, response: str) -> Dict:
        """
        Parse a string response into a dictionary, handling cases with markdown code blocks.

        Args:
            response (str): String response that could be wrapped in markdown code blocks
                          (e.g. ```json {...} ```)
        """
        if not response:
            return {}

        # First, try to extract JSON content between curly braces
        json_pattern = re.compile(r'\{.*?\}', re.DOTALL)
        json_matches = json_pattern.findall(response)
        
        if json_matches:
            # Try each potential JSON match until one works
            for json_str in json_matches:
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    continue
        
        # If direct JSON extraction failed, try markdown extraction
        # Remove markdown code block formatting if present
        cleaned = response.strip()
        if cleaned.startswith('```json'):
            cleaned = cleaned[7:]  # Remove ```json prefix
        elif cleaned.startswith('```'):
            cleaned = cleaned[3:]  # Remove ``` prefix
        
        # Find the end of the code block if it exists
        code_end = cleaned.find('```')
        if code_end != -1:
            cleaned = cleaned[:code_end]  # Remove everything after the end marker
        
        cleaned = cleaned.strip()  # Remove any remaining whitespace

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Try one more approach - look for JSON-like structures with regex
            satisfaction_match = re.search(r'"satisfaction"\s*:\s*"([^"]+)"', response)
            if satisfaction_match:
                return {"satisfaction": satisfaction_match.group(1)}
            
            # If all else fails
            return {'error': 'Failed to parse response', 'raw': cleaned}

    def zendesk_generate_ticket_response_creation(self, ticket: dict, articles: List[Dict]) -> str:
        """
        Generate a response to a ticket based on relevant help articles.

        Args:
            ticket (dict): Ticket information
            articles (List[Dict]): List of relevant articles

        Returns:
            str: Generated response to the ticket
        """
        llm = Runner('', article_system)
        human_message = f"Ticket: {ticket.get('subject', '')} {ticket.get('description', '')} \n\nArticles: {json.dumps(articles, indent=2)}"
        response = self._parse_runner_response(
            llm.start_runner(human_message=human_message))
        return response

    def zendesk_get_help_articles_for_ticket_retrieval(self, ticket: dict) -> Dict:
        """
        Get relevant help articles based on a ticket's content.
        
        Args:
            ticket_id (Union[str, int]): ID of the ticket to find help articles for
            
        Returns:
            Dict: Dictionary containing:
                - response: Raw response with ticket analysis and help articles
                    - ticket: Dict with ticket info (id, customer, issue)
                    - context: String explaining the context/resolution
                    - Recommendation: String with specific recommendations
                    - help_article_url: URL of the relevant help article
                - formatted_comment: Pre-formatted comment text for display
                
        Raises:
            ZendeskError: If ticket retrieval fails or no relevant articles found
        """
        try:
            # Get the ticket
            ticket_id = ticket.get('id')
            ticket = self.zendesk_get_ticket_retrieval(ticket_id)
            if not ticket:
                print(f"Ticket {ticket_id} not found")
            
            # Extract ticket subject and description
            query = f"{ticket.get('subject', '')} {ticket.get('description', '')}"
            # Search for relevant articles
            results = self.zendesk_get_relevant_help_articles_retrieval(query)
            
            # Flatten results from all sections into a single list
            all_articles = []
            for articles in results.values():
                all_articles.extend(articles)
                
            if not all_articles:
                print(f"No relevant help articles found for ticket {ticket_id}")
                
            # Generate and parse response
            response = self.zendesk_generate_ticket_response_creation(ticket, all_articles)
            
            print({
                'response': response,
            })
            return {
                'response': response
            }
            
        except Exception as e:
            print(f"Failed to get help articles for ticket: {str(e)}")

    def get_requesters_tickets(self, requester_id: int) -> str:
        """
        Get all tickets for a specific requester and return them as a well-formatted string for AI processing.

        Args:
            requester_id (int): ID of the requester
            
        Returns:
            str: Well-formatted string containing all tickets for the requester
        """
        tickets_info = []
        for ticket in self.client.search(type='ticket', requester_id=requester_id):
            ticket_data = {
                'id': getattr(ticket, 'id', None),
                'title': getattr(ticket, 'title', ''),
                'subject': getattr(ticket, 'subject', ''),
                'description': getattr(ticket, 'description', ''),
                'created_at': str(getattr(ticket, 'created_at', '')),
                'updated_at': str(getattr(ticket, 'updated_at', '')),
                'status': getattr(ticket, 'status', ''),
                'priority': getattr(ticket, 'priority', None),
                'tags': list(getattr(ticket, 'tags', []))
            }
            tickets_info.append(ticket_data)
            
        return json.dumps(tickets_info, indent=2)
    
    async def get_customer_expectation(self, ticket: dict) -> str:
        """
        Analyze a ticket and determine the root cause of the issue.

        Args:
            ticket (dict): Ticket information
        """
        system = """
            You are a professional customer service and retention agent with expert knowledge in analyzing customer support tickets. Your task is to review the customer's current support ticket, paying close attention to the details, tone, and any specific issues mentioned by the customer. Based on this analysis, determine the customer's underlying expectations, concerns, and any unmet needs they may have.

            After analyzing the current ticket, output your final response in JSON format using the following structure:
            {
            "expectation": "<your comprehensive analysis and understanding of the customer's expectations>"
            }

            Your response should:
            - Demonstrate empathy and understanding of the customer's immediate concerns.
            - Identify key issues or patterns in the current ticket that reveal the underlying expectations and needs.
            - Tailor your communication to reassure the customer and provide clear, actionable solutions.
            - Maintain a respectful, professional, and friendly tone.
            - Propose next steps that may include proactive outreach, personalized solutions, or escalation to specialized teams if necessary.

            Remember, every customer interaction is an opportunity to build trust and enhance loyalty. Your goal is not only to resolve the current issue but also to create a lasting, positive impression that reinforces the customer's value to the company.

        """
        runner = Runner('', system)
        human_message = f"Ticket: {ticket.get('subject', '')} {ticket.get('description', '')}"
        response = await runner.start_runner(human_message=human_message)
        response = self._parse_runner_response(response)
        return response
    
    async def get_root_cause(self, ticket: dict) -> str:
        """
        Analyze a ticket and determine the root cause of the issue.

        Args:
            ticket (dict): Ticket information
        """
        system = """
        You are a professional customer service and retention agent with expert knowledge in analyzing customer support tickets. Your task is to review the customer's current ticket, carefully examining the details, context, and any specific issues mentioned by the customer. Based on this analysis, determine the root cause of the customer's complaint or issue by identifying the underlying problems that have contributed to their current situation.

        After analyzing the current ticket details, output your final response in JSON format using the following structure:
        {
        "root_cause": "<your detailed analysis and identification of the root cause of the customer's complaint/ticket>"
        }

        Your response should:
        - Demonstrate empathy and a clear understanding of the customer's immediate concerns.
        - Identify key issues or patterns in the ticket that reveal the underlying problem.
        - Provide actionable insights or recommendations to address the root cause.
        - Maintain a respectful, professional, and friendly tone.
        - Suggest next steps for resolution or further investigation if needed.

        """
        runner = Runner('', system)
        human_message = f"Ticket: {ticket}"
        response = await runner.start_runner(human_message=human_message)
        response = self._parse_runner_response(response)
        return response
    
    async def get_customer_sentiment(self, tickets: dict) -> str:
        """
        Analyze a customer's complete history of support tickets and determine the sentiment of the customer.

        Args:
            ticket (dict): Ticket information
    """
        system = """
        You are a professional customer service and retention agent with expert knowledge in analyzing customer support tickets. Your task is to review a customer's complete history of support tickets, including their latest ticket. Pay close attention to the tone, resolution of issues, and overall progression of their interactions with the company.

        Based on this analysis, determine the customer's overall level of satisfaction using the following five-word scale:
        - Very Unsatisfied
        - Unsatisfied
        - Neutral
        - Satisfied
        - Very Satisfied

        After analyzing the ticket history, output your final response in JSON format using the following structure:
        {
        "satisfaction": "<your determined level of satisfaction>"
        }

        Your response should:
        - Demonstrate empathy and understanding of the customer's journey.
        - Identify key issues, trends, or patterns that reflect the customer's satisfaction level.
        - Provide a clear rationale for the determined satisfaction level.
        - Maintain a respectful, professional, and friendly tone.
        - Propose actionable next steps if needed to improve or maintain customer satisfaction.

        """
        runner = Runner('', system)
        human_message = f"Ticket: {tickets}"
        response = await runner.start_runner(human_message=human_message)
        response = self._parse_runner_response(response)
        print("SENTIMENT", response)
        return response
    
    async def get_recurring(self, tickets: dict) -> str:
        """
        Analyze a customer's complete history of support tickets and determine if the customer has recurring issues.

        Args:
            ticket (dict): Ticket information
        """

        system = """
        You are a professional customer service and retention agent with expertise in analyzing customer support ticket histories. Your task is to review a customer's complete history of support tickets, including their latest ticket, to determine if the current issue is recurring.

        After analyzing the ticket history, output your final response in JSON format using the following structure:
        {
        "recurring_issue": <true or false>,
        "recurrence_count": <number of times the issue has occurred>,
        "first_occurrence_date": "<date of the first occurrence>",
        "latest_occurrence_date": "<date of the latest occurrence>"
        }

        Your response should:
        - Demonstrate attention to detail in identifying patterns or repeated issues within the ticket history.
        - Provide accurate counts and dates of the issue's occurrences.
        - Maintain a respectful, professional, and objective tone.
        - Suggest actionable insights or recommendations to address the recurring issue if applicable.

        Remember, identifying and addressing recurring issues is crucial for enhancing customer satisfaction and improving service efficiency.

        """
        runner = Runner('', system)
        human_message = f"Ticket: {tickets}"
        response = await runner.start_runner(human_message=human_message)
        response = self._parse_runner_response(response)
        return response

    def get_action_plan(self, meta: dict) -> str:
        """
        Generate an action plan based on the customer's expectations, root cause, sentiment, and recurring issues.

        Args:
            meta (dict): Dictionary containing customer analysis
        """
        pass

    async def get_fundamentals(self, requester_id: int, ticket_id: int) -> dict:
        """
        Analyze a customer's complete history of support tickets and determine the fundamentals of the customer.

        Args:
            id (dict): Customer ID

        Returns:
            dict: A dictionary containing customer expectation, root cause, sentiment, and recurrence info.
        """
        tickets_raw = self.get_requesters_tickets(requester_id)
        tickets = json.loads(tickets_raw)
        print("TICKETS", tickets)
        print("TICKET ID", ticket_id)
        latest_ticket = self.zendesk_get_ticket_retrieval(ticket_id)
        print("LATEST TICKET", latest_ticket)
        # Run all async calls concurrently
        expectation_task = self.get_customer_expectation(latest_ticket)
        root_cause_task = self.get_root_cause(latest_ticket)
        sentiment_task = self.get_customer_sentiment(tickets)
        recurring_task = self.get_recurring(tickets)

        expectation, root_cause, sentiment, recurring = await asyncio.gather(
            expectation_task, root_cause_task, sentiment_task, recurring_task
        )

        meta = {
            "expectation": expectation.get('expectation'),
            "root_cause": root_cause.get('root_cause'),
            "sentiment": sentiment.get('satisfaction'),
            "recurring": recurring.get('recurring_issue'),
        }

        print("META", meta)
        return meta
    
# if __name__ == "__main__":
#     credentials = load_config()['zendesk']
#     tool = toolKit(credentials)
#     try:

#         # Example: Get help articles for a specific ticket
#         # print(tool._get_tickets())
#         # t = tool._get_tickets()
#         # for ticket in t:
#         #     print("TICKET", ticket)
#         fundamentals = asyncio.run(tool.get_fundamentals(4706179207839, 2))
#         print("FUNDAMENTALS", fundamentals)
#         # print("ROOT CAUSE", tool.root_cause(latest_ticket))
#             # tool.zendesk_add_comment_admin('2', "We review shipping costs every 2 hours. Please let us know if you have any further questions or need assistance.")
#             # print(tool.get_tickets()[0])
#             # ticket_id = 1  # Replace with actual ticket ID
#         # articles = tool.get_help_articles_for_ticket(ticket_id)
#     except Exception as e:
#         print(f"Error: {str(e)}")


