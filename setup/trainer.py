"""Setup and Training Module - AI learns from master tracker and user input"""
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional
from utils.logger import logger
# Try to import OpenAI, but handle gracefully if not available
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None
from config import OPENAI_API_KEY, MODEL_NAME, TEMPERATURE, MASTER_TRACKER_PATH
from excel_parser.master_tracker import MasterTrackerParser
from database.models import get_db_session, PermissionRule
from database.audit_log import AuditLogger
import json

class SetupTrainer:
    """Trains AI system based on master tracker and user configuration"""
    
    def __init__(self):
        self.parser = MasterTrackerParser()
        self.audit_logger = AuditLogger()
        if OPENAI_AVAILABLE and OPENAI_API_KEY:
            try:
                self.client = OpenAI(api_key=OPENAI_API_KEY)
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI client: {e}")
                self.client = None
        else:
            self.client = None
        self.training_config = {}
        self.master_tracker_data = None
    
    def load_master_tracker(self, excel_path: Optional[Path] = None) -> Dict:
        """Load and analyze master tracker Excel file"""
        try:
            if excel_path:
                self.parser.excel_path = excel_path
            
            # Load Excel
            df = self.parser.load_excel()
            self.master_tracker_data = df
            
            # Parse rules
            rules = self.parser.parse_permission_rules()
            
            # Analyze structure
            analysis = self._analyze_master_tracker(df, rules)
            
            logger.info(f"Master tracker loaded: {len(rules)} rules found")
            return {
                "success": True,
                "rules_count": len(rules),
                "analysis": analysis,
                "rules": rules[:10]  # First 10 for preview
            }
        except Exception as e:
            logger.error(f"Error loading master tracker: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _analyze_master_tracker(self, df: pd.DataFrame, rules: List[Dict]) -> Dict:
        """Analyze master tracker structure and content"""
        analysis = {
            "columns": list(df.columns),
            "total_rows": len(df),
            "permission_types": {},
            "common_prerequisites": {},
            "auto_grant_enabled_count": 0,
            "priority_distribution": {}
        }
        
        # Analyze permission types
        for rule in rules:
            perm_type = rule.get("permission_type", "Unknown")
            analysis["permission_types"][perm_type] = analysis["permission_types"].get(perm_type, 0) + 1
            
            # Count prerequisites
            prereqs = rule.get("pre_requisites", [])
            for prereq in prereqs:
                analysis["common_prerequisites"][prereq] = analysis["common_prerequisites"].get(prereq, 0) + 1
            
            # Count auto-grant enabled
            if rule.get("auto_grant_enabled"):
                analysis["auto_grant_enabled_count"] += 1
            
            # Priority distribution
            priority = rule.get("priority_level", "medium")
            analysis["priority_distribution"][priority] = analysis["priority_distribution"].get(priority, 0) + 1
        
        return analysis
    
    def generate_questions(self, analysis: Dict) -> List[Dict]:
        """Generate questions for user based on master tracker analysis"""
        questions = []
        
        # Question 1: Forms identification
        questions.append({
            "id": "forms_identification",
            "type": "text",
            "question": "Based on the master tracker, I've identified several permission types. What forms or documents are typically required for these requests? (e.g., 'Access Request Form', 'Manager Approval Form', etc.)",
            "help_text": "List the forms that users need to submit for access requests. This helps me validate requests properly.",
            "required": True
        })
        
        # Question 2: Validation rules
        questions.append({
            "id": "validation_rules",
            "type": "textarea",
            "question": "What are the key validation rules I should follow? (e.g., 'Always require manager approval for high-priority access', 'Reject if security clearance is below level 2', etc.)",
            "help_text": "Describe the business rules that should guide accept/reject decisions.",
            "required": True
        })
        
        # Question 3: Auto-approval criteria
        questions.append({
            "id": "auto_approval_criteria",
            "type": "textarea",
            "question": "When should I automatically approve requests? (e.g., 'Auto-approve if all prerequisites are met and priority is medium or low', 'Auto-approve for users in Sales department with completed training', etc.)",
            "help_text": "Define clear criteria for automatic approval.",
            "required": True
        })
        
        # Question 4: Rejection criteria
        questions.append({
            "id": "rejection_criteria",
            "type": "textarea",
            "question": "When should I automatically reject requests? (e.g., 'Reject if missing critical prerequisites', 'Reject if user has security violations', etc.)",
            "help_text": "Define clear criteria for automatic rejection.",
            "required": True
        })
        
        # Question 5: Special cases
        questions.append({
            "id": "special_cases",
            "type": "textarea",
            "question": "Are there any special cases or exceptions I should be aware of?",
            "help_text": "Any edge cases or special handling rules.",
            "required": False
        })
        
        return questions
    
    def train_with_user_responses(self, questions: List[Dict], responses: Dict[str, str]) -> Dict:
        """Train the system based on user responses"""
        try:
            # Store training configuration
            self.training_config = {
                "forms": responses.get("forms_identification", "").split(",") if responses.get("forms_identification") else [],
                "validation_rules": responses.get("validation_rules", ""),
                "auto_approval_criteria": responses.get("auto_approval_criteria", ""),
                "rejection_criteria": responses.get("rejection_criteria", ""),
                "special_cases": responses.get("special_cases", ""),
                "master_tracker_analysis": self._analyze_master_tracker(
                    self.master_tracker_data, 
                    self.parser.parse_permission_rules()
                ) if self.master_tracker_data is not None else {}
            }
            
            # Generate AI training prompt
            training_prompt = self._generate_training_prompt()
            
            # Store training configuration
            self._save_training_config()
            
            # Sync master tracker to database
            self.parser.sync_to_database()
            
            # Log training
            self.audit_logger.log_setup_action("training_completed", {
                "rules_count": len(self.parser.parse_permission_rules()),
                "forms_identified": len(self.training_config["forms"]),
                "training_date": pd.Timestamp.now().isoformat()
            })
            
            logger.info("Training completed successfully")
            return {
                "success": True,
                "message": "Training completed successfully",
                "config": self.training_config
            }
        except Exception as e:
            logger.error(f"Error during training: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _generate_training_prompt(self) -> str:
        """Generate comprehensive training prompt for AI"""
        rules = self.parser.parse_permission_rules()
        
        prompt = f"""You are an AI assistant for User Access Management (UAM). You have been trained on the following:

MASTER TRACKER RULES:
{json.dumps(rules[:20], indent=2)}

FORMS REQUIRED:
{', '.join(self.training_config.get('forms', []))}

VALIDATION RULES:
{self.training_config.get('validation_rules', '')}

AUTO-APPROVAL CRITERIA:
{self.training_config.get('auto_approval_criteria', '')}

REJECTION CRITERIA:
{self.training_config.get('rejection_criteria', '')}

SPECIAL CASES:
{self.training_config.get('special_cases', 'None')}

When evaluating requests:
1. Check against master tracker rules
2. Validate required forms are mentioned/submitted
3. Apply validation rules
4. Use auto-approval criteria for quick decisions
5. Use rejection criteria to immediately reject invalid requests
6. Consider special cases
7. Always provide clear reasoning for your decisions
"""
        return prompt
    
    def _save_training_config(self):
        """Save training configuration to file"""
        from config import BASE_DIR
        config_file = BASE_DIR / "data" / "training_config.json"
        config_file.parent.mkdir(exist_ok=True)
        
        with open(config_file, 'w') as f:
            json.dump(self.training_config, f, indent=2)
        
        logger.info(f"Training config saved to {config_file}")
    
    def load_training_config(self) -> Dict:
        """Load saved training configuration"""
        from config import BASE_DIR
        config_file = BASE_DIR / "data" / "training_config.json"
        
        if config_file.exists():
            with open(config_file, 'r') as f:
                self.training_config = json.load(f)
            return self.training_config
        return {}
    
    def is_trained(self) -> bool:
        """Check if system has been trained"""
        config = self.load_training_config()
        return bool(config.get("validation_rules") and config.get("auto_approval_criteria"))
    
    def get_training_summary(self) -> Dict:
        """Get summary of training status"""
        config = self.load_training_config()
        db = get_db_session()
        rule_count = db.query(PermissionRule).count()
        db.close()
        
        return {
            "trained": self.is_trained(),
            "rules_loaded": rule_count,
            "forms_configured": len(config.get("forms", [])),
            "has_validation_rules": bool(config.get("validation_rules")),
            "has_approval_criteria": bool(config.get("auto_approval_criteria")),
            "has_rejection_criteria": bool(config.get("rejection_criteria"))
        }

