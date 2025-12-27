"""Configuration settings for UAM Agentic AI System"""
import os
from pathlib import Path

# Try to load dotenv, but don't fail if it's not installed
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # If dotenv is not installed, just use environment variables directly
    # User can set them in system environment or .env file manually
    pass

# Base paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DB_DIR = BASE_DIR / "database"
LOGS_DIR = BASE_DIR / "logs"

# Create directories if they don't exist
DATA_DIR.mkdir(exist_ok=True)
DB_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# Excel Master Tracker
MASTER_TRACKER_PATH = DATA_DIR / "master_tracker.xlsx"

# Database
DATABASE_PATH = DB_DIR / "uam_database.db"

# AI/LLM Configuration - Support both OpenAI and Azure OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4")
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.3"))

# Azure OpenAI Configuration
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", os.getenv("OPENAI_API_VERSION", "2024-02-15-preview"))
AZURE_OPENAI_CHAT_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME", os.getenv("DEPLOYMENT_NAME_EMBEDDING", ""))
AZURE_API_TYPE = os.getenv("AZURE_API_TYPE", "azure")

# Determine which API to use (Azure takes precedence if configured)
USE_AZURE_OPENAI = bool(AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_CHAT_DEPLOYMENT_NAME)
# Use Azure key as fallback for OPENAI_API_KEY if using Azure
if USE_AZURE_OPENAI and not OPENAI_API_KEY:
    OPENAI_API_KEY = AZURE_OPENAI_API_KEY

# CrewAI Configuration
CREWAI_OPENAI_API_KEY = os.getenv("CREWAI_OPENAI_API_KEY", OPENAI_API_KEY)
USE_CREWAI = os.getenv("USE_CREWAI", "false").lower() == "true"

# AI Reasoning (use OpenAI for enhanced decision making)
USE_AI_REASONING = os.getenv("USE_AI_REASONING", "true").lower() == "true"

# Priority thresholds (0-100 scale)
AUTO_GRANT_THRESHOLD = int(os.getenv("AUTO_GRANT_THRESHOLD", "80"))
REQUIRE_APPROVAL_THRESHOLD = int(os.getenv("REQUIRE_APPROVAL_THRESHOLD", "50"))

# ServiceNow Configuration
SERVICENOW_INSTANCE = os.getenv("SERVICENOW_INSTANCE", "")
SERVICENOW_USERNAME = os.getenv("SERVICENOW_USERNAME", "")
SERVICENOW_PASSWORD = os.getenv("SERVICENOW_PASSWORD", "")
SERVICENOW_API_BASE = os.getenv("SERVICENOW_API_BASE", "/api/x/agentic_ai")
SERVICENOW_TABLE_NAME = os.getenv("SERVICENOW_TABLE_NAME", "u_access_request")
SERVICENOW_ENABLED = bool(SERVICENOW_INSTANCE and SERVICENOW_USERNAME and SERVICENOW_PASSWORD)

