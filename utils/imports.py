import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pathlib import Path
from azure.identity import ClientSecretCredential, InteractiveBrowserCredential, DeviceCodeCredential
from msgraph import GraphServiceClient
import requests
import argparse
import boto3
import yaml
import shutil
from dotenv import load_dotenv
import zipfile
from datetime import datetime
from bs4 import BeautifulSoup
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import CharacterTextSplitter
from langchain_community.document_loaders import Docx2txtLoader
from docx import Document
import time
import logging
import re
import json
import io
import re
import uuid
import threading
import asyncio
import traceback
import asyncio
import Tools
import copy
from zenpy import Zenpy
from langchain_core.tools import StructuredTool
from typing import Annotated, Literal, TypedDict
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage, ToolMessage
from langgraph.graph import END, StateGraph
from langgraph.graph import MessagesState, START
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode
from langgraph.graph.message import add_messages
from typing import TypedDict, Annotated
from pydantic import ValidationError
from utils.parser import load_config
from Prompts import master_prompts
from Connectors import *
from typing import Optional, Dict, Any, List, AsyncGenerator, Union
from ollama import AsyncClient, ResponseError