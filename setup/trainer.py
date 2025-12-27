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
from config import (
    OPENAI_API_KEY, MODEL_NAME, TEMPERATURE, MASTER_TRACKER_PATH,
    USE_AZURE_OPENAI, AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_API_VERSION, AZURE_OPENAI_CHAT_DEPLOYMENT_NAME
)
from utils.openai_client import get_openai_client
from excel_parser.master_tracker import MasterTrackerParser
from database.models import get_db_session, PermissionRule
from database.audit_log import AuditLogger
import json

class SetupTrainer:
    """Trains AI system based on master tracker and user configuration"""
    
    def __init__(self):
        self.parser = MasterTrackerParser()
        self.audit_logger = AuditLogger()
        self.client = None
        self.client_error = None
        
        if not OPENAI_AVAILABLE:
            logger.warning("OpenAI package not installed. Install with: pip install openai")
            self.client_error = "OpenAI package not installed"
        else:
            api_key = AZURE_OPENAI_API_KEY if USE_AZURE_OPENAI else OPENAI_API_KEY
            api_key = api_key or OPENAI_API_KEY  # Fallback
            
            if not api_key or api_key.strip() == "":
                logger.warning("OpenAI API key not found in .env file. Set OPENAI_API_KEY or AZURE_OPENAI_API_KEY")
                self.client_error = "API key not configured"
            else:
                try:
                    self.client = get_openai_client(
                        api_key=api_key,
                        azure_endpoint=AZURE_OPENAI_ENDPOINT if USE_AZURE_OPENAI else None,
                        api_version=AZURE_OPENAI_API_VERSION if USE_AZURE_OPENAI else None,
                        deployment_name=AZURE_OPENAI_CHAT_DEPLOYMENT_NAME if USE_AZURE_OPENAI else None,
                        use_azure=USE_AZURE_OPENAI
                    )
                    if not self.client:
                        self.client_error = "Failed to initialize OpenAI client"
                        logger.warning("OpenAI client initialization failed. Check your API key and configuration.")
                    else:
                        logger.info("OpenAI client initialized successfully for AI-powered question generation")
                except Exception as e:
                    logger.error(f"Error initializing OpenAI client: {e}")
                    self.client_error = str(e)
        
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
        """Generate questions for user using AI based on master tracker analysis"""
        if not self.client:
            if self.client_error:
                logger.warning(f"OpenAI client not available ({self.client_error}), using default questions")
            else:
                logger.warning("OpenAI client not available, using default questions")
            return self._generate_default_questions()
        
        try:
            # Prepare master tracker content for AI
            rules = self.parser.parse_permission_rules()
            master_tracker_summary = self._prepare_master_tracker_summary(analysis, rules)
            
            # Use AI to generate intelligent questions
            prompt = f"""You are an AI assistant helping to set up a User Access Management system. 

I have analyzed a master tracker Excel file with the following information:

MASTER TRACKER SUMMARY:
{master_tracker_summary}

ANALYSIS DETAILS:
- Total Rules: {analysis.get('total_rows', 0)}
- Permission Types: {list(analysis.get('permission_types', {}).keys())}
- Common Pre-requisites: {list(analysis.get('common_prerequisites', {}).keys())[:10]}
- Auto-grant Enabled: {analysis.get('auto_grant_enabled_count', 0)} rules

Based on this master tracker, I need you to:
1. Identify what forms/documents are typically needed for these access requests
2. Generate intelligent questions to understand the validation rules, approval criteria, and rejection criteria

Please return a JSON object with this structure:
{{
    "identified_forms": ["Form 1", "Form 2", ...],
    "questions": [
        {{
            "id": "question_id",
            "type": "text" or "textarea",
            "question": "The question text",
            "help_text": "Helpful guidance",
            "required": true or false
        }}
    ]
}}

Focus on generating questions that will help the system understand:
- What forms are required for different permission types
- Validation rules based on the prerequisites and permission types found
- When to auto-approve based on the auto-grant patterns in the tracker
- When to reject based on missing prerequisites
- Any special cases or exceptions

Return ONLY valid JSON, no additional text."""

            # Use deployment name for Azure, model name for regular OpenAI
            from config import USE_AZURE_OPENAI, AZURE_OPENAI_CHAT_DEPLOYMENT_NAME, MODEL_NAME
            model_or_deployment = AZURE_OPENAI_CHAT_DEPLOYMENT_NAME if USE_AZURE_OPENAI else MODEL_NAME
            
            response = self.client.chat.completions.create(
                model=model_or_deployment,
                messages=[
                    {"role": "system", "content": "You are an expert at analyzing access management requirements and generating intelligent questions. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            ai_response = json.loads(response.choices[0].message.content)
            
            # Extract identified forms and store them
            identified_forms = ai_response.get("identified_forms", [])
            if identified_forms:
                logger.info(f"AI identified {len(identified_forms)} forms: {identified_forms}")
                # Store forms for later use in UI
                if not hasattr(self, 'identified_forms'):
                    self.identified_forms = []
                self.identified_forms = identified_forms
            
            # Use AI-generated questions
            questions = ai_response.get("questions", [])
            
            # Ensure we have at least the essential questions
            if not questions or len(questions) < 3:
                logger.warning("AI generated insufficient questions, using defaults")
                return self._generate_default_questions()
            
            logger.info(f"AI generated {len(questions)} questions")
            return questions
            
        except Exception as e:
            logger.error(f"Error generating AI questions: {e}")
            logger.info("Falling back to default questions")
            return self._generate_default_questions()
    
    def _generate_default_questions(self) -> List[Dict]:
        """Generate default questions if AI is not available"""
        questions = []
        
        questions.append({
            "id": "forms_identification",
            "type": "text",
            "question": "Based on the master tracker, I've identified several permission types. What forms or documents are typically required for these requests? (e.g., 'Access Request Form', 'Manager Approval Form', etc.)",
            "help_text": "List the forms that users need to submit for access requests. This helps me validate requests properly.",
            "required": True
        })
        
        questions.append({
            "id": "validation_rules",
            "type": "textarea",
            "question": "What are the key validation rules I should follow? (e.g., 'Always require manager approval for high-priority access', 'Reject if security clearance is below level 2', etc.)",
            "help_text": "Describe the business rules that should guide accept/reject decisions.",
            "required": True
        })
        
        questions.append({
            "id": "auto_approval_criteria",
            "type": "textarea",
            "question": "When should I automatically approve requests? (e.g., 'Auto-approve if all prerequisites are met and priority is medium or low', 'Auto-approve for users in Sales department with completed training', etc.)",
            "help_text": "Define clear criteria for automatic approval.",
            "required": True
        })
        
        questions.append({
            "id": "rejection_criteria",
            "type": "textarea",
            "question": "When should I automatically reject requests? (e.g., 'Reject if missing critical prerequisites', 'Reject if user has security violations', etc.)",
            "help_text": "Define clear criteria for automatic rejection.",
            "required": True
        })
        
        questions.append({
            "id": "special_cases",
            "type": "textarea",
            "question": "Are there any special cases or exceptions I should be aware of?",
            "help_text": "Any edge cases or special handling rules.",
            "required": False
        })
        
        return questions
    
    def _prepare_master_tracker_summary(self, analysis: Dict, rules: List[Dict]) -> str:
        """Prepare a summary of master tracker for AI"""
        summary_parts = []
        
        # Column headers
        summary_parts.append(f"Columns: {', '.join(analysis.get('columns', []))}")
        
        # Permission types
        perm_types = analysis.get('permission_types', {})
        if perm_types:
            summary_parts.append(f"\nPermission Types Found:")
            for ptype, count in list(perm_types.items())[:10]:
                summary_parts.append(f"  - {ptype}: {count} rules")
        
        # Sample rules
        summary_parts.append(f"\nSample Rules (first 5):")
        for i, rule in enumerate(rules[:5], 1):
            summary_parts.append(f"\nRule {i}:")
            summary_parts.append(f"  Permission: {rule.get('permission_name', 'N/A')}")
            summary_parts.append(f"  Type: {rule.get('permission_type', 'N/A')}")
            summary_parts.append(f"  Pre-requisites: {', '.join(rule.get('pre_requisites', [])[:5])}")
            summary_parts.append(f"  Auto-grant: {rule.get('auto_grant_enabled', False)}")
            summary_parts.append(f"  Priority: {rule.get('priority_level', 'N/A')}")
        
        # Common prerequisites
        common_prereqs = analysis.get('common_prerequisites', {})
        if common_prereqs:
            summary_parts.append(f"\nMost Common Pre-requisites:")
            for prereq, count in list(sorted(common_prereqs.items(), key=lambda x: x[1], reverse=True)[:10]):
                summary_parts.append(f"  - {prereq}: appears in {count} rules")
        
        return "\n".join(summary_parts)
    
    def get_identified_forms(self) -> List[str]:
        """Get forms identified by AI during question generation"""
        return getattr(self, 'identified_forms', [])
    
    def is_ai_available(self) -> bool:
        """Check if AI client is available"""
        return self.client is not None
    
    def get_ai_status(self) -> Dict:
        """Get status of AI configuration"""
        status = {
            "ai_available": self.is_ai_available(),
            "openai_package_installed": OPENAI_AVAILABLE,
            "api_key_configured": bool(OPENAI_API_KEY or AZURE_OPENAI_API_KEY),
            "using_azure": USE_AZURE_OPENAI,
            "error": self.client_error
        }
        return status
    
    def train_with_user_responses(self, questions: List[Dict], responses: Dict[str, str]) -> Dict:
        """Train the system based on user responses"""
        try:
            # Get AI-identified forms if available, otherwise use user input
            ai_forms = self.get_identified_forms()
            user_forms = responses.get("forms_identification", "").strip()
            
            # Combine AI-identified forms with user-provided forms
            if user_forms:
                user_forms_list = [f.strip() for f in user_forms.split(",") if f.strip()]
                all_forms = list(set(ai_forms + user_forms_list))  # Remove duplicates
            else:
                all_forms = ai_forms
            
            # Store training configuration
            self.training_config = {
                "forms": all_forms,
                "ai_identified_forms": ai_forms,
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

