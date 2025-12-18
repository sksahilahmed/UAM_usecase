"""Terminal-based setup and training for UAM System"""
import sys
from pathlib import Path

# Add the project root to Python path
PROJECT_ROOT = Path(__file__).parent.absolute()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.logger import logger
from setup.trainer import SetupTrainer
from database.models import init_database
from config import MASTER_TRACKER_PATH, DATA_DIR, OPENAI_API_KEY

def print_header(text):
    """Print formatted header"""
    print("\n" + "="*70)
    print(f"  {text}")
    print("="*70 + "\n")

def print_section(text):
    """Print formatted section"""
    print(f"\n{'─'*70}")
    print(f"  {text}")
    print(f"{'─'*70}\n")

def check_prerequisites():
    """Check if prerequisites are met"""
    print_header("UAM Agentic AI System - Setup Check")
    
    issues = []
    
    # Check .env file
    env_file = Path(".env")
    if not env_file.exists():
        issues.append("❌ .env file not found. Please create it with your OpenAI API key.")
    else:
        if not OPENAI_API_KEY or OPENAI_API_KEY == "":
            issues.append("⚠️  OPENAI_API_KEY not set in .env file")
        else:
            print("✅ .env file found and OPENAI_API_KEY is set")
    
    # Check master tracker
    if not MASTER_TRACKER_PATH.exists():
        issues.append(f"❌ Master tracker not found at: {MASTER_TRACKER_PATH}")
        print(f"   Please place your master_tracker.xlsx file in: {DATA_DIR}")
    else:
        print(f"✅ Master tracker found: {MASTER_TRACKER_PATH}")
    
    if issues:
        print("\n⚠️  Issues found:")
        for issue in issues:
            print(f"   {issue}")
        return False
    
    print("\n✅ All prerequisites met!")
    return True

def load_and_analyze_master_tracker(trainer):
    """Load and analyze master tracker"""
    print("\n" + "─"*70)
    print("  Step 1: Loading Master Tracker")
    print("─"*70 + "\n")
    
    print(f"📁 Loading master tracker from: {MASTER_TRACKER_PATH}")
    result = trainer.load_master_tracker()
    
    if not result["success"]:
        print(f"❌ Error loading master tracker: {result.get('error')}")
        return None
    
    print(f"✅ Master tracker loaded successfully!")
    print(f"   - Total rules found: {result['rules_count']}")
    
    analysis = result["analysis"]
    print(f"\n📊 Analysis Summary:")
    print(f"   - Permission types: {len(analysis.get('permission_types', {}))}")
    print(f"   - Auto-grant enabled: {analysis.get('auto_grant_enabled_count', 0)}")
    print(f"   - Common prerequisites: {len(analysis.get('common_prerequisites', {}))}")
    
    # Show sample rules
    if result.get("rules"):
        print(f"\n📋 Sample Rules (first 3):")
        for i, rule in enumerate(result["rules"][:3], 1):
            print(f"   {i}. {rule.get('permission_name', 'N/A')} ({rule.get('permission_type', 'N/A')})")
    
    return result

def ask_questions(trainer, analysis):
    """Ask training questions in terminal"""
    print("\n" + "─"*70)
    print("  Step 2: Training Configuration")
    print("─"*70 + "\n")
    
    print("The AI needs to understand your validation rules and processes.")
    print("Please answer the following questions:\n")
    
    questions = trainer.generate_questions(analysis)
    responses = {}
    
    for i, q in enumerate(questions, 1):
        print(f"\n{'='*70}")
        print(f"Question {i}/{len(questions)}")
        print(f"{'='*70}")
        print(f"\n{q['question']}")
        if q.get('help_text'):
            print(f"\n💡 Help: {q['help_text']}")
        
        required = q.get('required', False)
        required_text = " (Required)" if required else " (Optional)"
        
        if q["type"] == "text":
            while True:
                response = input(f"\nYour answer{required_text}: ").strip()
                if response or not required:
                    responses[q["id"]] = response
                    break
                print("⚠️  This field is required. Please provide an answer.")
        
        elif q["type"] == "textarea":
            print(f"\nEnter your answer{required_text} (press Enter twice when done):")
            lines = []
            empty_count = 0
            while True:
                line = input()
                if line.strip() == "":
                    empty_count += 1
                    if empty_count >= 2:
                        break
                else:
                    empty_count = 0
                    lines.append(line)
            
            response = "\n".join(lines).strip()
            if not response and required:
                print("⚠️  This field is required. Please provide an answer.")
                continue
            
            responses[q["id"]] = response
        
        print(f"\n✅ Answer saved.")
    
    return responses

def train_system(trainer, questions, responses):
    """Train the system with user responses"""
    print("\n" + "─"*70)
    print("  Step 3: Training AI System")
    print("─"*70 + "\n")
    
    print("🤖 Training AI system with your responses...")
    print("   This may take a moment...\n")
    
    result = trainer.train_with_user_responses(questions, responses)
    
    if not result["success"]:
        print(f"❌ Error during training: {result.get('error')}")
        return False
    
    print("✅ Training completed successfully!")
    print("\n📝 Training Summary:")
    config = result["config"]
    print(f"   - Forms configured: {len(config.get('forms', []))}")
    print(f"   - Validation rules: {'✅ Set' if config.get('validation_rules') else '❌ Not set'}")
    print(f"   - Auto-approval criteria: {'✅ Set' if config.get('auto_approval_criteria') else '❌ Not set'}")
    print(f"   - Rejection criteria: {'✅ Set' if config.get('rejection_criteria') else '❌ Not set'}")
    
    return True

def main():
    """Main setup function"""
    try:
        # Initialize database
        init_database()
        
        # Check prerequisites
        if not check_prerequisites():
            print("\n❌ Please fix the issues above and try again.")
            sys.exit(1)
        
        # Initialize trainer
        trainer = SetupTrainer()
        
        # Check if already trained
        if trainer.is_trained():
            print_header("System Already Trained")
            summary = trainer.get_training_summary()
            print("✅ The system has already been trained.")
            print(f"\n📊 Training Status:")
            print(f"   - Rules loaded: {summary['rules_loaded']}")
            print(f"   - Forms configured: {summary['forms_configured']}")
            print(f"   - Validation rules: {'✅' if summary['has_validation_rules'] else '❌'}")
            print(f"   - Approval criteria: {'✅' if summary['has_approval_criteria'] else '❌'}")
            print(f"   - Rejection criteria: {'✅' if summary['has_rejection_criteria'] else '❌'}")
            print("\n✅ System is ready to use!")
            print("\nYou can now run the UI with: python run_ui.py")
            print("Or use the main script: python main.py")
            return
        
        # Load master tracker
        result = load_and_analyze_master_tracker(trainer)
        if not result:
            print("\n❌ Failed to load master tracker. Exiting.")
            sys.exit(1)
        
        # Ask questions
        analysis = result["analysis"]
        questions = trainer.generate_questions(analysis)
        responses = ask_questions(trainer, analysis)
        
        # Train system
        if train_system(trainer, questions, responses):
            print_header("Setup Complete!")
            print("✅ The UAM Agentic AI system has been successfully set up and trained.")
            print("\n📋 Next Steps:")
            print("   1. Run the UI: python run_ui.py")
            print("   2. Or use the main script: python main.py")
            print("\n🎉 You're all set! The system is ready to process access requests.")
        else:
            print("\n❌ Training failed. Please check the errors above.")
            sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Setup interrupted by user.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Setup error: {e}")
        print(f"\n❌ An error occurred during setup: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

