"""Main entry point for UAM Agentic AI System"""
import sys
from pathlib import Path

# Add the project root to Python path to ensure imports work
PROJECT_ROOT = Path(__file__).parent.absolute()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.logger import logger
from config import LOGS_DIR, MASTER_TRACKER_PATH, OPENAI_API_KEY
from database.models import init_database
from excel_parser.master_tracker import MasterTrackerParser
from agents.uam_agent import UAMAgent
from setup.trainer import SetupTrainer

# Configure logging
logger.add(LOGS_DIR / "uam_{time}.log", rotation="10 MB", retention="10 days")

def check_and_run_setup():
    """Check if setup is needed and run it if required"""
    # Initialize database first
    init_database()
    
    trainer = SetupTrainer()
    
    # Check if already trained
    if trainer.is_trained():
        logger.info("System already trained, skipping setup")
        print("\n✅ System already trained. Loading configuration...")
        return True
    
    # Check prerequisites
    print("\n" + "="*70)
    print("  UAM Agentic AI System - Initial Setup Required")
    print("="*70 + "\n")
    
    # Check .env
    if not OPENAI_API_KEY or OPENAI_API_KEY == "":
        print("❌ ERROR: OPENAI_API_KEY not found in .env file")
        print("   Please create a .env file with your OpenAI API key.")
        print("   See .env.example for reference.\n")
        return False
    
    # Check master tracker
    if not MASTER_TRACKER_PATH.exists():
        print(f"❌ ERROR: Master tracker not found at: {MASTER_TRACKER_PATH}")
        print(f"   Please place your master_tracker.xlsx file in: {MASTER_TRACKER_PATH.parent}\n")
        return False
    
    print("✅ Prerequisites check passed")
    print("   - .env file found with API key")
    print(f"   - Master tracker found: {MASTER_TRACKER_PATH}\n")
    
    # Import and run terminal setup
    try:
        from setup_terminal import (
            load_and_analyze_master_tracker,
            ask_questions,
            train_system
        )
        
        # Load master tracker
        result = load_and_analyze_master_tracker(trainer)
        if not result:
            print("\n❌ Failed to load master tracker. Exiting.")
            return False
        
        # Ask questions
        analysis = result["analysis"]
        questions = trainer.generate_questions(analysis)
        responses = ask_questions(trainer, analysis)
        
        # Train system
        if train_system(trainer, questions, responses):
            print("\n" + "="*70)
            print("  ✅ Setup Complete! System is now ready.")
            print("="*70 + "\n")
            return True
        else:
            print("\n❌ Training failed. Please check the errors above.")
            return False
            
    except Exception as e:
        logger.error(f"Setup error: {e}")
        print(f"\n❌ An error occurred during setup: {e}")
        import traceback
        traceback.print_exc()
        return False

def initialize_system():
    """Initialize the UAM system"""
    logger.info("Initializing UAM Agentic AI System...")
    
    # Check and run setup if needed (this also initializes database)
    if not check_and_run_setup():
        logger.error("Setup failed or prerequisites not met")
        sys.exit(1)
    
    logger.info("Database initialized")
    
    # Load and sync master tracker
    parser = MasterTrackerParser()
    try:
        parser.sync_to_database()
        logger.info("Master tracker synced to database")
    except Exception as e:
        logger.error(f"Error syncing master tracker: {e}")
        logger.warning("Continuing with empty rules - please check master_tracker.xlsx")
    
    logger.info("System initialization complete")

def main():
    """Main function with example usage"""
    initialize_system()
    
    # Create UAM agent
    agent = UAMAgent()
    
    print("\n" + "="*60)
    print("UAM Agentic AI System - Test Interface")
    print("="*60 + "\n")
    
    try:
        # Example 1: Request with high priority (should auto-grant if pre-requisites met)
        print("Example 1: User requesting Salesforce Access")
        print("-" * 60)
        result1 = agent.process_request(
            user_id="EMP001",
            request_type="application_access",
            requested_permission="Salesforce Access",
            description="Need access to Salesforce for sales operations",
            user_info={
                "username": "john.doe",
                "email": "john.doe@company.com",
                "department": "Sales",
                "role": "Sales Representative",
                "context_data": {
                    "completed_trainings": ["Security Training", "Salesforce Basics"],
                    "security_clearance_level": 1
                }
            }
        )
        print(f"Decision: {result1['decision']}")
        print(f"Status: {result1['status']}")
        print(f"Priority Score: {result1['priority_score']}")
        print(f"Reasoning: {result1['reasoning']}")
        print(f"Confidence: {result1['confidence']}")
        print()
        
        # Example 2: Request with missing pre-requisites (should create ticket)
        print("Example 2: User requesting Production DB Access")
        print("-" * 60)
        result2 = agent.process_request(
            user_id="EMP002",
            request_type="database_access",
            requested_permission="Production DB Read Access",
            description="Need read access to production database for analysis",
            user_info={
                "username": "jane.smith",
                "email": "jane.smith@company.com",
                "department": "IT",
                "role": "Developer",
                "context_data": {
                    "completed_trainings": ["Database Basics"],
                    "security_clearance_level": 1
                }
            }
        )
        print(f"Decision: {result2['decision']}")
        print(f"Status: {result2['status']}")
        print(f"Priority Score: {result2['priority_score']}")
        print(f"Reasoning: {result2['reasoning']}")
        if result2.get('ticket_id'):
            print(f"Ticket ID: {result2['ticket_id']}")
        print()
        
        # Example 3: Get user summary
        print("Example 3: User Access Summary")
        print("-" * 60)
        summary = agent.get_user_access_summary("EMP001")
        print(f"User: {summary.get('username')} ({summary.get('user_id')})")
        print(f"Department: {summary.get('department')}")
        print(f"Total Permissions: {summary.get('total_permissions')}")
        print(f"Total Requests: {summary.get('total_requests')}")
        print()
        
    except Exception as e:
        logger.error(f"Error in main execution: {e}")
        print(f"Error: {e}")
    finally:
        agent.close()
    
    print("\n" + "="*60)
    print("UAM System ready for integration")
    print("="*60)

if __name__ == "__main__":
    main()

