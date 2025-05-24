import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "")))
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from utils.parser import parser, load_config

# creds = load_config()

class Slack:
    def __init__(self, credentials):
        self.client = WebClient(token=credentials.get('token', ''))
    
    def send_message(self, user_id, message):
        try:
            response = self.client.conversations_open(users=[user_id])
        except SlackApiError as e:
            assert e.response["ok"] is False
            assert e.response["error"]
            print(f"Got an error: {e.response['error']}")
            assert isinstance(e.response.status_code, int)
            print(f"Received a response status_code: {e.response.status_code}")
    
    def send_channel_message(self, channel, message):
        try:
            response = self.client.chat_postMessage(channel='#random', text="Hello world!")
            assert response["message"]["text"] == "Hello world!"
        except SlackApiError as e:
            assert e.response["ok"] is False
            assert e.response["error"]
            print(f"Got an error: {e.response['error']}")
            assert isinstance(e.response.status_code, int)
            print(f"Received a response status_code: {e.response.status_code}")

    def find_user_id(self, user):
        try:
            response = self.client.conversations_list()
            return response["user"]["id"]
        except SlackApiError as e:
            assert e.response["ok"] is False
            assert e.response["error"]
            print(f"Got an error: {e.response['error']}")
            assert isinstance(e.response.status_code, int)
            print(f"Received a response status_code: {e.response.status_code}")

    async def list_permissions(self):
        try:
            response = self.client.auth_test()
            scopes_list = response.headers['x-oauth-scopes'].split(",")
            return scopes_list
        except SlackApiError as e:
            print(f"Error: {e}")

# slack = Slack(creds['slack_creds'])
# slack.list_permissions()
#id = slack.find_user_id('amir@m3labs.co.uk')
# slack.send_message(id, "Hello world!")