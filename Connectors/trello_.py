import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".")))
from utils.parser import parser, load_config
from trello import TrelloClient


# sharepoint_creds, jira_creds, tools, slack_creds, trello_creds = load_config()

# class Trello:
#     def __init__(self):
#         self.client = client = TrelloClient(
#         api_key=trello_creds['api_key'],
#         api_secret=trello_creds['api_secret'],
# )
        

# trello = Trello()



# # all_boards = trello.client.list_boards()
# # last_board = all_boards[-1]
# # print(last_board.name)