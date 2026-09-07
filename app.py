import os
import uvicorn
import requests
import json
from pydantic import BaseModel, Field
from fastapi import FastAPI
from langserve import add_routes

from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda
from langchain_google_genai import ChatGoogleGenerativeAI

# Robust Agent imports for current LangChain versions
try:
    from langchain.agents import create_tool_calling_agent, AgentExecutor
except ImportError:
    from langchain.agents import create_tool_calling_agent
    from langchain_classic.agents import AgentExecutor
