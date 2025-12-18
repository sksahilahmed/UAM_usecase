"""Example test script to demonstrate UAM agent functionality"""
from agents.uam_agent import UAMAgent
from database.models import init_database
from excel_parser.master_tracker import MasterTrackerParser
from loguru import logger

def setup():
    """Initialize the system"""
    logger.info("Setting up UAM system...")
    init_database()
    
    # Sync master tracker
    parser = MasterTrackerParser()
    parser.sync_to_database()
    logger.info("Setup complete!")

def test_scenarios():
    """Test various scenarios"""
    agent = UAMAgent()
    
    print("\n" + "="*70)
    print("UAM AGENTIC AI - TEST SCENARIOS")
    print("="*70)
    
    # Scenario 1: High priority, all pre-requisites met
    print("\n[SCENARIO 1] High Priority Request - All Pre-requisites Met")
    print("-" * 70)
    result = agent.process_request(
        user_id="EMP001",
        request_type="application_access",
        requested_permission="Salesforce Access",
        description="Need Salesforce access for managing customer accounts",
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
    print_result(result)
    
    # Scenario 2: High priority but missing pre-requisites
    print("\n[SCENARIO 2] High Priority - Missing Critical Pre-requisites")
    print("-" * 70)
    result = agent.process_request(
        user_id="EMP002",
        request_type="database_access",
        requested_permission="Production DB Read Access",
        description="Need read access to production database",
        user_info={
            "username": "jane.smith",
            "email": "jane.smith@company.com",
            "department": "IT",
            "role": "Developer",
            "context_data": {
                "completed_trainings": ["Database Basics"],
                "security_clearance_level": 1  # Needs level 2+
            }
        }
    )
    print_result(result)
    
    # Scenario 3: Medium priority
    print("\n[SCENARIO 3] Medium Priority Request")
    print("-" * 70)
    result = agent.process_request(
        user_id="EMP003",
        request_type="application_access",
        requested_permission="ServiceNow Access",
        description="Need ServiceNow access for ticket management",
        user_info={
            "username": "bob.jones",
            "email": "bob.jones@company.com",
            "department": "Support",
            "role": "Support Engineer"
        }
    )
    print_result(result)
    
    # Scenario 4: Get user summary
    print("\n[SCENARIO 4] User Access Summary")
    print("-" * 70)
    summary = agent.get_user_access_summary("EMP001")
    print(f"User ID: {summary.get('user_id')}")
    print(f"Username: {summary.get('username')}")
    print(f"Department: {summary.get('department')}")
    print(f"Role: {summary.get('role')}")
    print(f"Current Permissions: {len(summary.get('current_permissions', {}))}")
    print(f"Total Requests: {summary.get('total_requests')}")
    if summary.get('recent_requests'):
        print("\nRecent Requests:")
        for req in summary['recent_requests'][:3]:
            print(f"  - {req['requested_permission']}: {req['status']}")
    
    agent.close()

def print_result(result):
    """Pretty print result"""
    print(f"Request ID: {result.get('request_id')}")
    print(f"Decision: {result.get('decision').upper()}")
    print(f"Status: {result.get('status').upper()}")
    print(f"Priority Score: {result.get('priority_score')}/100")
    print(f"Confidence: {result.get('confidence'):.2%}")
    print(f"\nReasoning:")
    print(f"  {result.get('reasoning')}")
    
    if result.get('ticket_id'):
        print(f"\nTicket ID: {result['ticket_id']}")
    
    if result.get('pre_requisites_status'):
        print(f"\nPre-requisites Status:")
        for prereq, status in result['pre_requisites_status'].items():
            status_icon = "✓" if status['met'] else "✗"
            print(f"  {status_icon} {prereq}")
            if status.get('details'):
                print(f"    → {status['details']}")

if __name__ == "__main__":
    setup()
    test_scenarios()
    print("\n" + "="*70)
    print("Testing complete!")
    print("="*70 + "\n")

