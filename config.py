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

# AI/LLM Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4")
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.3"))

# CrewAI Configuration
CREWAI_OPENAI_API_KEY = os.getenv("CREWAI_OPENAI_API_KEY", OPENAI_API_KEY)
USE_CREWAI = os.getenv("USE_CREWAI", "false").lower() == "true"

# AI Reasoning (use OpenAI for enhanced decision making)
USE_AI_REASONING = os.getenv("USE_AI_REASONING", "true").lower() == "true"

# Priority thresholds (0-100 scale)
AUTO_GRANT_THRESHOLD = int(os.getenv("AUTO_GRANT_THRESHOLD", "80"))
REQUIRE_APPROVAL_THRESHOLD = int(os.getenv("REQUIRE_APPROVAL_THRESHOLD", "50"))

# ServiceNow (for future use)
SERVICENOW_INSTANCE = os.getenv("SERVICENOW_INSTANCE", "")
SERVICENOW_USERNAME = os.getenv("SERVICENOW_USERNAME", "")
SERVICENOW_PASSWORD = os.getenv("SERVICENOW_PASSWORD", "")

