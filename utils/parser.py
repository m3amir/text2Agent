import os
import yaml
import argparse
from dotenv import load_dotenv

# Setup argument parsing
parser = argparse.ArgumentParser(description='A script to demonstrate command line argument parsing.')
parser.add_argument('--profile_name', type=str, required=True, help='The name of the AWS profile.')
parser.add_argument('--debug', action='store_true', help='Enable debug mode.')

def load_config(test: bool = False):
    load_dotenv()

    # If test mode is enabled, dynamically load all `_creds` prefixed environment variables
    if test:
        print("Running in test mode, loading credentials from environment variables...")
        creds = {}
        for key, value in os.environ.items():
            creds[key.lower()] = {subkey.lower(): os.getenv(f"{key}_{subkey}", '') for subkey in os.environ if subkey.startswith(key)}
        return creds | {"guarded_tools": os.getenv("GUARDED_TOOLS", "").split(",")}

    # Load YAML file
    try:
        print("Loading configuration from YAML file...")
        with open("./Config/config.yml", "r") as file:
            config = yaml.safe_load(file) or {}
    except FileNotFoundError:
        print("Error: The configuration file was not found.")
        return {}
    except yaml.YAMLError as e:
        print(f"Error: Failed to parse the YAML file: {e}")
        return {}

    # Dynamically extract all credential keys ending in `_creds`
    credentials = {key: value for key, value in config.items()}

    # Process guarded tools
    guarded_tools = config.get("guarded_tools", [])
    if isinstance(guarded_tools, list):
        credentials["guarded_tools"] = {tool["name"] for tool in guarded_tools if isinstance(tool, dict) and "name" in tool}
    else:
        print(f"Warning: 'guarded_tools' is not a list. Found type: {type(guarded_tools)}")
        credentials["guarded_tools"] = set()
    return credentials