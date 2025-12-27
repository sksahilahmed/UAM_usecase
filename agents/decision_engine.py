"""Decision Engine for evaluating access requests"""
from typing import Dict, List, Tuple, Optional
from utils.logger import logger
from database.models import PermissionRule, get_db_session
from database.user_context import UserContextManager
from agents.ai_enhancer import AIReasoningEnhancer

class DecisionEngine:
    """Evaluates requests against rules and pre-requisites"""
    
    def __init__(self):
        self.db = get_db_session()
        self.user_context_manager = UserContextManager()
        try:
            from agents.ai_enhancer import AIReasoningEnhancer
            self.ai_enhancer = AIReasoningEnhancer()
        except ImportError:
            self.ai_enhancer = None
    
    def evaluate_request(self, user_id: str, request_type: str, 
                        requested_permission: str, description: str) -> Dict:
        """
        Evaluate a request and determine action (grant, ticket, or reject)
        
        Returns:
            dict with keys:
            - decision: "grant", "create_ticket", or "reject"
            - priority_score: float (0-100)
            - pre_requisites_status: dict of pre-requisite checks
            - reasoning: explanation
            - confidence: float (0-1)
        """
        logger.info(f"Evaluating request: {requested_permission} for user {user_id}")
        
        # Get user context
        user_context = self.user_context_manager.get_user_context(user_id)
        if not user_context:
            user_context = self.user_context_manager.get_or_create_user(user_id).__dict__
        
        # Use AI to understand context and extract intent (what user is actually asking for)
        contextual_understanding = self._understand_request_context(requested_permission, description, user_context)
        
        # Enhance requested_permission with contextual understanding
        if contextual_understanding:
            # Update user context with extracted information if not explicitly provided
            if contextual_understanding.get('extracted_role') and not user_context.get('role'):
                user_context['role'] = contextual_understanding['extracted_role']
            if contextual_understanding.get('extracted_application') and requested_permission:
                # Enhance requested_permission with extracted application if missing
                if contextual_understanding['extracted_application'].lower() not in requested_permission.lower():
                    requested_permission = f"{contextual_understanding['extracted_application']} - {requested_permission}"
        
        # Store contextual understanding in user_context for later use
        if 'context_data' not in user_context:
            user_context['context_data'] = {}
        user_context['context_data']['contextual_understanding'] = contextual_understanding
        
        # Find matching permission rule
        rule = self._find_permission_rule(requested_permission, request_type)
        
        # Create a dummy rule if none found, so AI can still use master tracker context
        if not rule:
            logger.warning(f"No rule found for {requested_permission}, creating temporary rule for AI decision")
            from database.models import PermissionRule
            rule = PermissionRule(
                permission_name=requested_permission,
                permission_type=request_type,
                priority_level="medium",
                auto_grant_enabled=False,
                pre_requisites=[]
            )
        
        # Check pre-requisites
        pre_requisites_status = self._check_pre_requisites(
            rule.pre_requisites or [], 
            user_context
        )
        
        # Calculate priority score
        priority_score = self._calculate_priority_score(
            rule, user_context, pre_requisites_status
        )
        
        # Get similar historical requests for pattern analysis
        similar_requests = self.user_context_manager.get_similar_requests(requested_permission)
        
        # Make decision (pass description for contextual understanding)
        decision, reasoning, confidence = self._make_decision(
            rule, priority_score, pre_requisites_status, 
            user_context, similar_requests, requested_permission, description
        )
        
        return {
            "decision": decision,
            "priority_score": priority_score,
            "pre_requisites_status": pre_requisites_status,
            "reasoning": reasoning,
            "confidence": confidence,
            "rule_id": rule.id,
            "similar_requests_count": len(similar_requests)
        }
    
    def _find_permission_rule(self, permission_name: str, request_type: str) -> Optional[PermissionRule]:
        """Find matching permission rule from database"""
        # Try exact match first
        rule = self.db.query(PermissionRule).filter(
            PermissionRule.permission_name.ilike(f"%{permission_name}%")
        ).first()
        
        if not rule:
            # Try by type
            rule = self.db.query(PermissionRule).filter(
                PermissionRule.permission_type.ilike(f"%{request_type}%")
            ).first()
        
        return rule
    
    def _check_pre_requisites(self, pre_requisites: List[str], user_context: Dict) -> Dict:
        """Check which pre-requisites are met"""
        status = {}
        
        for prereq in pre_requisites:
            if not prereq:
                continue
            prereq_lower = str(prereq).lower()
            met = False
            details = ""
            
            # Check common pre-requisites
            if "valid employee id" in prereq_lower or "employee id" in prereq_lower:
                met = bool(user_context.get("user_id"))
                details = "User ID present" if met else "User ID missing"
            
            elif "department" in prereq_lower:
                met = bool(user_context.get("department"))
                details = f"Department: {user_context.get('department')}" if met else "Department not set"
            
            elif "manager approval" in prereq_lower or "approval" in prereq_lower:
                # For now, assume approval needed (would check approval system)
                met = False  # Typically requires manual approval
                details = "Requires manager approval"
            
            elif "security" in prereq_lower and "clearance" in prereq_lower:
                # Check security clearance level
                context_data = user_context.get("context_data", {})
                clearance_level = context_data.get("security_clearance_level", 0)
                met = clearance_level >= 2
                details = f"Security clearance level: {clearance_level}"
            
            elif "training" in prereq_lower:
                context_data = user_context.get("context_data", {})
                completed_trainings = [t for t in context_data.get("completed_trainings", []) if t]
                training_type = prereq_lower.replace("training", "").strip()
                met = any(training_type in str(t).lower() for t in completed_trainings) if training_type and completed_trainings else len(completed_trainings) > 0
                details = f"Trainings: {completed_trainings}" if met else "Training not completed"
            
            elif "role" in prereq_lower:
                role = user_context.get("role", "")
                met = bool(role)
                details = f"Role: {role}" if met else "Role not set"
            
            else:
                # Generic check - check if mentioned in context
                context_str = str(user_context).lower()
                met = prereq_lower in context_str
                details = "Found in context" if met else "Not found in context"
            
            status[prereq] = {
                "met": met,
                "details": details
            }
        
        return status
    
    def _calculate_priority_score(self, rule: PermissionRule, 
                                 user_context: Dict, 
                                 pre_requisites_status: Dict) -> float:
        """Calculate priority score (0-100) based on various factors"""
        score = 50.0  # Base score
        
        # Adjust based on pre-requisites met
        total_prereqs = len(pre_requisites_status)
        met_prereqs = sum(1 for status in pre_requisites_status.values() if status["met"])
        if total_prereqs > 0:
            prereq_ratio = met_prereqs / total_prereqs
            score += prereq_ratio * 30  # Up to +30 for all pre-requisites met
        
        # Adjust based on priority level
        priority_bonus = {
            "high": 20,
            "medium": 10,
            "low": 0
        }
        priority_level = rule.priority_level.lower() if rule.priority_level else "medium"
        score += priority_bonus.get(priority_level, 0)
        
        # Adjust based on user history (if has previous similar permissions)
        current_perms = user_context.get("current_permissions", {})
        if current_perms:
            score += 10  # Bonus for existing user
        
        # Adjust based on auto_grant capability
        if rule.auto_grant_enabled:
            score += 10
        
        # Ensure score is within 0-100
        score = max(0, min(100, score))
        
        return round(score, 2)
    
    def _make_decision(self, rule: PermissionRule, priority_score: float,
                      pre_requisites_status: Dict, user_context: Dict,
                      similar_requests: List[Dict], requested_permission: str = "", description: str = "") -> Tuple[str, str, float]:
        """
        Make final decision using AI: grant, create_ticket, reject, or ask_for_more_info
        
        Returns: (decision, reasoning, confidence)
        """
        from config import USE_AI_REASONING
        
        # FIRST: Always check master tracker validation (training, exceptions, etc.)
        # This must happen regardless of AI or rule-based decision
        # Use contextual understanding to enhance matching
        contextual_understanding = user_context.get('context_data', {}).get('contextual_understanding')
        validation_rejection = self._check_master_tracker_validation(requested_permission, user_context, description)
        if validation_rejection:
            return validation_rejection  # Early rejection based on validation
        
        # Use AI for decision-making if available
        if self.ai_enhancer and USE_AI_REASONING:
            return self._make_ai_decision(rule, priority_score, pre_requisites_status, 
                                        user_context, similar_requests, requested_permission, description)
        else:
            # Fallback to rule-based logic if AI not available
            return self._make_rule_based_decision(rule, priority_score, pre_requisites_status, 
                                                  user_context, similar_requests, requested_permission, description)
    
    def _extract_master_tracker_row_context(self, requested_permission: str, user_context: Dict) -> Tuple[List[Dict], Dict]:
        """
        Extract full row context from master tracker that matches the requested permission.
        Returns tuple of (matching_rows_data, column_mapping)
        Each row_data contains ALL fields from that row.
        """
        import pandas as pd
        from config import MASTER_TRACKER_PATH
        
        matching_rows_data = []
        column_mapping = {}
        
        try:
            if not MASTER_TRACKER_PATH.exists():
                return matching_rows_data, column_mapping
                
            df = pd.read_excel(MASTER_TRACKER_PATH, sheet_name=0)
            
            # Get header row (row 0) to map column names
            headers = {}
            for col in df.columns:
                if len(df) > 0:
                    header_value = df.iloc[0][col]
                    if pd.notna(header_value):
                        headers[col] = str(header_value).strip()
            
            # Map column indices to meaningful names
            role_col = None
            app_col = None
            training_col = None
            approval_col = None
            exception_col = None
            notes_col = None
            access_level_col = None
            env_col = None
            manager_col = None
            
            for col in df.columns:
                col_str = str(col).lower()
                header_str = str(headers.get(col, '')).lower()
                
                if 'role' in header_str:
                    role_col = col
                    column_mapping['role'] = col
                elif 'application' in header_str or 'application name' in header_str:
                    app_col = col
                    column_mapping['application'] = col
                elif 'training' in header_str or 'pre-requisite' in header_str:
                    training_col = col
                    column_mapping['training'] = col
                elif 'approval required' in header_str or 'approval' in header_str:
                    approval_col = col
                    column_mapping['approval'] = col
                elif 'exception' in header_str:
                    exception_col = col
                    column_mapping['exception'] = col
                elif 'note' in header_str and 'unnamed' not in col_str:
                    notes_col = col
                    column_mapping['notes'] = col
                elif 'access level' in header_str:
                    access_level_col = col
                    column_mapping['access_level'] = col
                elif 'environment' in header_str:
                    env_col = col
                    column_mapping['environment'] = col
                elif 'manager' in header_str or 'authorizing' in header_str:
                    manager_col = col
                    column_mapping['manager'] = col
            
            # Find matching rows (skip header row 0)
            requested_permission_str = str(requested_permission) if requested_permission else ""
            requested_lower = requested_permission_str.lower()
            request_words = [w for w in requested_lower.split() if len(w) > 3]
            
            for idx in range(1, len(df)):  # Start from row 1, skip header
                row = df.iloc[idx]
                row_data = {}
                match_score = 0
                
                # Extract all fields from this row
                if role_col and pd.notna(row[role_col]):
                    role_value = str(row[role_col]).strip()
                    row_data['role'] = role_value
                    # Check if role matches requested permission
                    if any(word in role_value.lower() for word in request_words) or \
                       any(word in requested_lower for word in role_value.lower().split()):
                        match_score += 3
                
                if app_col and pd.notna(row[app_col]):
                    app_value = str(row[app_col]).strip()
                    row_data['application'] = app_value
                    if any(word in app_value.lower() for word in request_words):
                        match_score += 2
                
                if training_col and pd.notna(row[training_col]):
                    training_val = str(row[training_col]).strip()
                    if training_val and training_val.lower() not in ['nan', 'none', '']:
                        row_data['training_required'] = training_val
                
                if approval_col and pd.notna(row[approval_col]):
                    approval_val = str(row[approval_col]).strip()
                    if approval_val and approval_val.lower() not in ['nan', 'none', '']:
                        row_data['approval_required'] = approval_val
                
                if exception_col and pd.notna(row[exception_col]):
                    exception_val = str(row[exception_col]).strip()
                    if exception_val and exception_val.lower() not in ['nan', 'none', '']:
                        row_data['exception_scenario'] = exception_val
                
                if notes_col and pd.notna(row[notes_col]):
                    notes_val = str(row[notes_col]).strip()
                    if notes_val and notes_val.lower() not in ['nan', 'none', '']:
                        row_data['notes'] = notes_val
                
                if access_level_col and pd.notna(row[access_level_col]):
                    access_val = str(row[access_level_col]).strip()
                    if access_val and access_val.lower() not in ['nan', 'none', '']:
                        row_data['access_level'] = access_val
                
                if env_col and pd.notna(row[env_col]):
                    env_val = str(row[env_col]).strip()
                    if env_val and env_val.lower() not in ['nan', 'none', '']:
                        row_data['environment'] = env_val
                
                if manager_col and pd.notna(row[manager_col]):
                    manager_val = str(row[manager_col]).strip()
                    if manager_val and manager_val.lower() not in ['nan', 'none', '']:
                        row_data['authorizing_manager'] = manager_val
                
                row_data['row_index'] = idx
                row_data['match_score'] = match_score
                
                # Only include rows that have some match or at least have a role
                if match_score > 0 or row_data.get('role'):
                    matching_rows_data.append(row_data)
            
            # Sort by match score (highest first)
            matching_rows_data.sort(key=lambda x: x.get('match_score', 0), reverse=True)
            
        except Exception as e:
            logger.warning(f"Error extracting master tracker context: {e}")
            import traceback
            logger.debug(traceback.format_exc())
        
        return matching_rows_data, column_mapping
    
    def _validate_row_against_user_context(self, row_data: Dict, user_context: Dict) -> Dict:
        """
        Validate a master tracker row against user context.
        Returns dict with validation results:
        - is_valid: bool
        - validation_issues: List[str]
        - training_match: bool
        - exception_violated: bool
        """
        validation_result = {
            'is_valid': True,
            'validation_issues': [],
            'training_match': False,
            'exception_violated': False,
            'all_fields_match': True
        }
        
        context_data = user_context.get('context_data', {})
        completed_trainings = [t.lower() for t in context_data.get('completed_trainings', []) if t]
        user_department = (user_context.get('department') or '').lower()
        employee_type = (context_data.get('employee_type') or 'Full-time').lower()
        user_role = (user_context.get('role') or '').lower()
        
        # 1. Check Training Match (CRITICAL - MUST BE EXACT OR CLOSE MATCH)
        # If training is required, user MUST have completed it - NO EXCEPTIONS
        required_training_raw = row_data.get('training_required', '')
        required_training = str(required_training_raw).strip() if required_training_raw else ''
        if required_training and required_training.lower() not in ['nan', 'none', '']:
            required_training_lower = required_training.lower()
            training_match = False
            
            # If user has no completed trainings, training_match stays False
            if not completed_trainings:
                validation_result['training_match'] = False
                validation_result['is_valid'] = False
                validation_result['all_fields_match'] = False
                validation_result['validation_issues'].append(
                    f"REQUIRED TRAINING NOT COMPLETED: Role requires '{required_training}' "
                    f"but user has completed NO TRAININGS. This is a mandatory requirement - access cannot be granted."
                )
            else:
                # Check if user has the EXACT required training
                for user_training in completed_trainings:
                    user_training_lower = user_training.lower()
                    # Exact match (case-insensitive)
                    if required_training_lower == user_training_lower:
                        training_match = True
                        break
                    # Check if one contains the other (for variations like "CRM Analytics Training" vs "CRM Analytics")
                    if required_training_lower in user_training_lower or user_training_lower in required_training_lower:
                        training_match = True
                        break
                    # Check if key meaningful words match (at least 2 significant words must match)
                    required_words = set([w for w in required_training_lower.split() if len(w) > 3 and w not in ['training', 'course', 'certification']])
                    user_words = set([w for w in user_training_lower.split() if len(w) > 3 and w not in ['training', 'course', 'certification']])
                    if required_words and user_words:
                        matching_words = required_words.intersection(user_words)
                        # If at least 2 significant words match, consider it a match
                        if len(matching_words) >= 2:
                            training_match = True
                            break
                        # If all required words are present in user's training, it's a match
                        if required_words.issubset(user_words):
                            training_match = True
                            break
                
                validation_result['training_match'] = training_match
                if not training_match:
                    validation_result['is_valid'] = False
                    validation_result['all_fields_match'] = False
                    validation_result['validation_issues'].append(
                        f"REQUIRED TRAINING MISMATCH: Role requires '{required_training}' "
                        f"but user has completed: {', '.join(context_data.get('completed_trainings', []))}. "
                        f"These are DIFFERENT trainings - access cannot be granted without the required training."
                    )
        
        # 2. Check Exception Scenarios (CRITICAL - should REJECT)
        exception_scenario_raw = row_data.get('exception_scenario')
        exception_scenario = str(exception_scenario_raw).strip() if exception_scenario_raw else ''
        if exception_scenario and exception_scenario.lower() not in ['nan', 'none', '']:
            exception_lower = exception_scenario.lower()
            
            # Check for contractor restriction
            if 'contractor' in exception_lower and ('contractor' in employee_type or 'external' in employee_type):
                validation_result['exception_violated'] = True
                validation_result['is_valid'] = False
                validation_result['validation_issues'].append(
                    f"EXCEPTION VIOLATION: {row_data.get('exception_scenario')} - User is a {context_data.get('employee_type')}"
                )
            
            # Check for intern restriction
            if 'intern' in exception_lower and 'intern' in employee_type:
                validation_result['exception_violated'] = True
                validation_result['is_valid'] = False
                validation_result['validation_issues'].append(
                    f"EXCEPTION VIOLATION: {row_data.get('exception_scenario')} - User is an {context_data.get('employee_type')}"
                )
            
            # Check for external user restriction
            if 'external' in exception_lower and ('external' in employee_type or 'contractor' in employee_type):
                validation_result['exception_violated'] = True
                validation_result['is_valid'] = False
                validation_result['validation_issues'].append(
                    f"EXCEPTION VIOLATION: {row_data.get('exception_scenario')} - User is {context_data.get('employee_type')}"
                )
            
            # Check for department restrictions (e.g., "Non Finance resources")
            if 'non finance' in exception_lower and 'finance' not in user_department:
                # This is tricky - if it says "not permitted for Non Finance", it means Finance is required
                if 'finance' not in user_department:
                    validation_result['exception_violated'] = True
                    validation_result['is_valid'] = False
                    validation_result['validation_issues'].append(
                        f"EXCEPTION VIOLATION: {row_data.get('exception_scenario')} - User department is {user_context.get('department')}"
                    )
        
        # 3. Check Role Match
        required_role_raw = row_data.get('role')
        required_role = str(required_role_raw).strip().lower() if required_role_raw and str(required_role_raw).lower() not in ['nan', 'none', ''] else ''
        if required_role and user_role:
            # Allow partial matches but log if exact match fails
            if required_role not in user_role and user_role not in required_role:
                # Check if key words match
                required_words = set([w for w in required_role.split() if len(w) > 3])
                user_words = set([w for w in user_role.split() if len(w) > 3])
                if not required_words.intersection(user_words):
                    validation_result['validation_issues'].append(
                        f"ROLE MISMATCH: Required role is '{row_data.get('role')}' but user role is '{user_context.get('role')}'"
                    )
        
        return validation_result
    
    def _understand_request_context(self, requested_permission: str, description: str, user_context: Dict) -> Optional[Dict]:
        """
        Use AI to understand the request context and extract what the user is actually asking for.
        This helps handle incomplete, incorrect, or extra information intelligently.
        
        Returns:
            Dict with extracted information: role, application, access_level, intent, etc.
        """
        if not self.ai_enhancer or not self.ai_enhancer.client:
            return None
        
        try:
            import json
            from config import USE_AZURE_OPENAI, AZURE_OPENAI_CHAT_DEPLOYMENT_NAME, MODEL_NAME
            
            # Load master tracker to understand available options
            import pandas as pd
            from config import MASTER_TRACKER_PATH
            
            available_roles = []
            available_apps = []
            available_trainings = []
            
            try:
                if MASTER_TRACKER_PATH.exists():
                    df = pd.read_excel(MASTER_TRACKER_PATH, sheet_name=0)
                    headers = {}
                    for col in df.columns:
                        if len(df) > 0:
                            header_value = df.iloc[0][col]
                            if pd.notna(header_value):
                                headers[col] = str(header_value).strip()
                    
                    # Extract available roles and apps
                    for col in df.columns:
                        header_str = str(headers.get(col, '')).lower()
                        if 'role' in header_str:
                            for idx in range(1, len(df)):
                                val = df.iloc[idx][col]
                                if pd.notna(val) and str(val).strip():
                                    available_roles.append(str(val).strip())
                        elif 'application' in header_str or 'application name' in header_str:
                            for idx in range(1, len(df)):
                                val = df.iloc[idx][col]
                                if pd.notna(val) and str(val).strip():
                                    available_apps.append(str(val).strip())
                        elif 'training' in header_str:
                            for idx in range(1, len(df)):
                                val = df.iloc[idx][col]
                                if pd.notna(val) and str(val).strip():
                                    available_trainings.append(str(val).strip())
            except Exception as e:
                logger.warning(f"Could not load master tracker for context understanding: {e}")
            
            user_role = user_context.get('role', '')
            user_department = user_context.get('department', '')
            context_data = user_context.get('context_data', {})
            completed_trainings = context_data.get('completed_trainings', [])
            
            prompt = f"""You are an intelligent access management assistant. Analyze this access request and extract what the user is actually asking for, even if the information is incomplete, incorrect, or has extra details.

REQUESTED PERMISSION: {requested_permission}
DESCRIPTION: {description}

USER CONTEXT:
- Role: {user_role if user_role else 'Not specified'}
- Department: {user_department if user_department else 'Not specified'}
- Completed Trainings: {', '.join(completed_trainings) if completed_trainings else 'None'}

AVAILABLE OPTIONS FROM MASTER TRACKER:
- Available Roles: {', '.join(set(available_roles[:20])) if available_roles else 'None'}
- Available Applications: {', '.join(set(available_apps[:20])) if available_apps else 'None'}
- Available Trainings: {', '.join(set(available_trainings[:20])) if available_trainings else 'None'}

Your task:
1. Understand what role the user is requesting (extract from description if not clear in requested_permission)
2. Understand what application they want access to (extract from description if not clear)
3. Understand the access level needed (read-only, read/write, full, restricted)
4. Understand the environment if mentioned (QA, Prod, Dev, Test)
5. Identify any mismatches or missing information
6. Suggest the most likely correct request based on context

Return JSON with:
{{
    "extracted_role": "the role user is requesting (best match from available roles or from description)",
    "extracted_application": "the application name (best match from available apps or from description)",
    "extracted_access_level": "read-only, read/write, full, or restricted",
    "extracted_environment": "QA, Prod, Dev, Test, or null",
    "intent_confidence": 0.0 to 1.0,
    "missing_information": ["list of missing critical information"],
    "potential_issues": ["list of potential mismatches or incorrect information"],
    "recommended_action": "what the user likely meant to request"
}}

Return ONLY valid JSON, no additional text."""

            model_or_deployment = AZURE_OPENAI_CHAT_DEPLOYMENT_NAME if USE_AZURE_OPENAI else MODEL_NAME
            
            response = self.ai_enhancer.client.chat.completions.create(
                model=model_or_deployment,
                messages=[
                    {"role": "system", "content": "You are an expert at understanding access requests and extracting intent from context. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            contextual_data = json.loads(response.choices[0].message.content)
            logger.info(f"Contextual understanding extracted: role={contextual_data.get('extracted_role')}, app={contextual_data.get('extracted_application')}")
            return contextual_data
            
        except Exception as e:
            logger.warning(f"Error in contextual understanding: {e}")
            return None
    
    def _check_master_tracker_validation(self, requested_permission: str, user_context: Dict, description: str = "") -> Optional[Tuple[str, str, float]]:
        """
        Check master tracker validation rules and return rejection if critical issues found.
        This runs BEFORE AI or rule-based decision to enforce strict rules.
        
        Returns: None if validation passes, or (decision, reasoning, confidence) tuple if must reject
        """
        try:
            # Use contextual understanding to improve matching
            contextual_understanding = user_context.get('context_data', {}).get('contextual_understanding')
            
            # Enhance requested_permission with contextual understanding if available
            enhanced_permission = requested_permission
            if contextual_understanding:
                extracted_role = contextual_understanding.get('extracted_role', '')
                extracted_app = contextual_understanding.get('extracted_application', '')
                
                # If we extracted role/app from context, use them for better matching
                if extracted_role and extracted_app:
                    # Build a more precise permission string
                    if extracted_app.lower() not in requested_permission.lower():
                        enhanced_permission = f"{extracted_app} - {extracted_role} - {requested_permission}"
                    elif extracted_role.lower() not in requested_permission.lower():
                        enhanced_permission = f"{requested_permission} - {extracted_role}"
            
            # Extract full row context from master tracker
            matching_rows_data, column_mapping = self._extract_master_tracker_row_context(enhanced_permission, user_context)
            
            if not matching_rows_data:
                # No matching rows found - let AI/rule-based handle it
                return None
            
            # Extract role and application from user context or requested_permission
            # Format of requested_permission: "Application Name - Role - (Access Level)"
            user_role_from_context = user_context.get('role', '').strip() if user_context.get('role') else ''
            user_role_lower = user_role_from_context.lower() if user_role_from_context else ''
            
            # Parse requested_permission to extract application and role
            # Format: "Medidata - Data Analyst - (Read-Only)"
            requested_parts = [p.strip() for p in str(requested_permission).split('-')] if requested_permission else []
            requested_app = requested_parts[0].lower() if len(requested_parts) > 0 else ''
            requested_role_from_permission = requested_parts[1].lower() if len(requested_parts) > 1 else ''
            
            # Determine the role we're looking for (prioritize user context)
            target_role = user_role_lower if user_role_lower else requested_role_from_permission
            
            # Filter to only the BEST matching row - must match BOTH role AND application
            best_matching_row = None
            best_match_score = -1
            
            for row_data in matching_rows_data:
                row_role = str(row_data.get('role', '')).lower().strip() if row_data.get('role') else ''
                row_app = str(row_data.get('application', '')).lower().strip() if row_data.get('application') else ''
                match_score = row_data.get('match_score', 0)
                
                # Check role match
                role_exact_match = target_role == row_role
                role_partial_match = target_role in row_role or row_role in target_role if target_role and row_role else False
                role_matches = role_exact_match or role_partial_match
                
                # Check application match
                app_exact_match = requested_app == row_app
                app_partial_match = requested_app in row_app or row_app in requested_app if requested_app and row_app else False
                app_matches = app_exact_match or app_partial_match if requested_app else True  # If no app specified, don't filter
                
                # Calculate a combined score
                combined_score = match_score
                if role_exact_match:
                    combined_score += 10  # Exact role match is best
                elif role_partial_match:
                    combined_score += 5
                if app_exact_match:
                    combined_score += 10  # Exact app match is best
                elif app_partial_match:
                    combined_score += 5
                
                # Prefer rows that match BOTH role AND application
                if role_matches and app_matches and combined_score > best_match_score:
                    best_matching_row = row_data
                    best_match_score = combined_score
                elif not best_matching_row and role_matches and combined_score > best_match_score:
                    # Fallback: if no perfect match, use best role match
                    best_matching_row = row_data
                    best_match_score = combined_score
            
            # If we found a good match, use it; otherwise use the first one (highest match_score from original logic)
            if not best_matching_row and matching_rows_data:
                best_matching_row = matching_rows_data[0]  # Fallback to first (highest original match_score)
            
            # Only validate the BEST matching row
            rows_to_validate = [best_matching_row] if best_matching_row else []
            
            critical_rejection_reasons = []
            must_reject = False
            
            for row_data in rows_to_validate:
                validation = self._validate_row_against_user_context(row_data, user_context)
                
                # CRITICAL: If training is required but doesn't match, MUST REJECT
                required_training = str(row_data.get('training_required', '')).strip() if row_data.get('training_required') else ''
                if required_training and required_training.lower() not in ['nan', 'none', '']:
                    if not validation['training_match']:
                        must_reject = True
                        context_data = user_context.get('context_data', {})
                        completed_trainings = context_data.get('completed_trainings', [])
                        critical_rejection_reasons.append(
                            f"Required training '{required_training}' has not been completed. "
                            f"User has completed: {', '.join(completed_trainings) if completed_trainings else 'no trainings'}. "
                            f"Access cannot be granted without the required training."
                        )
                
                # CRITICAL: Exception violations MUST REJECT
                if validation['exception_violated']:
                    must_reject = True
                    exception_scenario = row_data.get('exception_scenario', 'N/A')
                    critical_rejection_reasons.append(
                        f"EXCEPTION VIOLATION: {exception_scenario}"
                    )
            
            # If critical validations fail, reject immediately
            if must_reject and critical_rejection_reasons:
                # Use only the first (most relevant) rejection reason
                rejection_reason = critical_rejection_reasons[0] if len(critical_rejection_reasons) == 1 else critical_rejection_reasons[0]
                logger.warning(f"MASTER TRACKER VALIDATION FAILED - Auto-rejecting: {rejection_reason}")
                return ("reject", rejection_reason, 0.95)
            
            return None  # Validation passed, continue with normal decision flow
            
        except Exception as e:
            logger.error(f"Error in master tracker validation: {e}")
            # Don't block decision if validation check fails
            return None
    
    def _make_ai_decision(self, rule: PermissionRule, priority_score: float,
                          pre_requisites_status: Dict, user_context: Dict,
                          similar_requests: List[Dict], requested_permission: str = "", description: str = "") -> Tuple[str, str, float]:
        """Use AI to make the decision"""
        try:
            # Load training configuration
            from pathlib import Path
            import json
            import pandas as pd
            from config import BASE_DIR, MASTER_TRACKER_PATH
            
            training_config_path = BASE_DIR / "data" / "training_config.json"
            training_config = {}
            if training_config_path.exists():
                with open(training_config_path, 'r') as f:
                    training_config = json.load(f)
            
            # Extract full row context from master tracker
            matching_rows_data, column_mapping = self._extract_master_tracker_row_context(requested_permission, user_context)
            
            # Validate each matching row against user context (for AI context, validation already checked earlier)
            validation_results = []
            for row_data in matching_rows_data:
                validation = self._validate_row_against_user_context(row_data, user_context)
                validation['row_data'] = row_data
                validation_results.append(validation)
            
            # Build comprehensive master tracker context with validation results
            master_tracker_context = ""
            if matching_rows_data:
                master_tracker_context = "\n=== MASTER TRACKER ROW ANALYSIS (Full Context) ===\n"
                for idx, validation in enumerate(validation_results):
                    row_data = validation['row_data']
                    master_tracker_context += f"\n--- MATCHING ROW {row_data.get('row_index', idx)} (Match Score: {row_data.get('match_score', 0)}) ---\n"
                    master_tracker_context += f"FULL ROW DATA:\n"
                    
                    if row_data.get('application'):
                        master_tracker_context += f"  • Application: {row_data['application']}\n"
                    if row_data.get('role'):
                        master_tracker_context += f"  • Role: {row_data['role']}\n"
                    if row_data.get('access_level'):
                        master_tracker_context += f"  • Access Level: {row_data['access_level']}\n"
                    if row_data.get('environment'):
                        master_tracker_context += f"  • Environment: {row_data['environment']}\n"
                    if row_data.get('training_required'):
                        master_tracker_context += f"  • Training Required: {row_data['training_required']}\n"
                    if row_data.get('approval_required'):
                        master_tracker_context += f"  • Approval Required: {row_data['approval_required']}\n"
                    if row_data.get('exception_scenario'):
                        master_tracker_context += f"  • Exception Scenario: {row_data['exception_scenario']}\n"
                    if row_data.get('notes'):
                        master_tracker_context += f"  • Notes: {row_data['notes']}\n"
                    if row_data.get('authorizing_manager'):
                        master_tracker_context += f"  • Authorizing Manager: {row_data['authorizing_manager']}\n"
                    
                    master_tracker_context += f"\nVALIDATION RESULTS:\n"
                    master_tracker_context += f"  • Training Match: {'✓ YES' if validation['training_match'] else '✗ NO'}\n"
                    master_tracker_context += f"  • Exception Violated: {'✗ YES (MUST REJECT)' if validation['exception_violated'] else '✓ NO'}\n"
                    master_tracker_context += f"  • Overall Valid: {'✓ YES' if validation['is_valid'] else '✗ NO'}\n"
                    
                    if validation['validation_issues']:
                        master_tracker_context += f"  • Issues Found:\n"
                        for issue in validation['validation_issues']:
                            master_tracker_context += f"    - {issue}\n"
            else:
                master_tracker_context = "\n=== MASTER TRACKER: No matching rows found ===\n"
            
            # Prepare context for AI
            prereq_met_count = sum(1 for s in pre_requisites_status.values() if s["met"])
            prereq_total = len(pre_requisites_status)
            
            prereqs_summary = "\n".join([
                f"- {prereq}: {'✓ Met' if status['met'] else '✗ Not Met'} ({status.get('details', '')})"
                for prereq, status in pre_requisites_status.items()
            ])
            
            # Get user's completed trainings and employee type
            context_data = user_context.get('context_data', {})
            completed_trainings = context_data.get('completed_trainings', [])
            employee_type = context_data.get('employee_type', 'Full-time')
            security_clearance = context_data.get('security_clearance_level', 0)
            
            # Get contextual understanding if available
            contextual_understanding = user_context.get('context_data', {}).get('contextual_understanding')
            contextual_info = ""
            if contextual_understanding:
                contextual_info = f"""
CONTEXTUAL UNDERSTANDING (Extracted from request description):
- Extracted Role: {contextual_understanding.get('extracted_role', 'N/A')}
- Extracted Application: {contextual_understanding.get('extracted_application', 'N/A')}
- Extracted Access Level: {contextual_understanding.get('extracted_access_level', 'N/A')}
- Intent Confidence: {contextual_understanding.get('intent_confidence', 'N/A')}
- Recommended Action: {contextual_understanding.get('recommended_action', 'N/A')}
- Potential Issues: {', '.join(contextual_understanding.get('potential_issues', [])) if contextual_understanding.get('potential_issues') else 'None'}
- Missing Information: {', '.join(contextual_understanding.get('missing_information', [])) if contextual_understanding.get('missing_information') else 'None'}

REQUEST DESCRIPTION: {description}

"""
            
            user_info = f"""
User ID: {user_context.get('user_id', 'N/A')}
Department: {user_context.get('department', 'N/A')}
Role: {user_context.get('role', 'N/A')}
Employee Type: {employee_type}
Security Clearance Level: {security_clearance}
Completed Trainings: {', '.join(completed_trainings) if completed_trainings else 'None'}
Current Permissions: {len(user_context.get('current_permissions', {}))} active
Recent Requests: {len(user_context.get('recent_requests', []))} in history
{contextual_info}
"""
            
            similar_requests_summary = ""
            if similar_requests:
                auto_granted = sum(1 for r in similar_requests if r.get("auto_granted"))
                similar_requests_summary = f"\nSimilar Historical Requests: {len(similar_requests)} found, {auto_granted} were auto-granted"
            
            rule_info = f"""
Permission Rule:
- Name: {rule.permission_name}
- Type: {rule.permission_type}
- Priority Level: {rule.priority_level}
- Auto-grant Enabled: {rule.auto_grant_enabled}
- Pre-requisites Required: {len(rule.pre_requisites or [])}
"""
            
            # Build validation summary
            validation_summary = ""
            if validation_results:
                validation_summary = "\n=== VALIDATION SUMMARY (CRITICAL) ===\n"
                for idx, validation in enumerate(validation_results):
                    row_data = validation['row_data']
                    validation_summary += f"\nRow {row_data.get('row_index', idx)} - {row_data.get('role', 'N/A')}:\n"
                    if validation['exception_violated']:
                        validation_summary += "  ✗ MUST REJECT: Exception scenario violated\n"
                    if row_data.get('training_required'):
                        if validation['training_match']:
                            validation_summary += f"  ✓ Training Match: User has required '{row_data.get('training_required')}'\n"
                        else:
                            context_data = user_context.get('context_data', {})
                            completed_trainings = context_data.get('completed_trainings', [])
                            validation_summary += f"  ✗ MUST REJECT: Training mismatch - Required '{row_data.get('training_required')}' but user has: {', '.join(completed_trainings) if completed_trainings else 'NO TRAININGS'}\n"
                    if validation['is_valid']:
                        validation_summary += "  ✓ All validations passed\n"
                    else:
                        validation_summary += f"  ✗ Issues: {len(validation['validation_issues'])} found\n"
            
            prompt = f"""You are an AI assistant for User Access Management. Analyze this access request and make a decision.

CRITICAL INSTRUCTIONS - READ CAREFULLY:
========================================
1. The Master Tracker shows FULL ROW CONTEXT - ALL fields in each row are RELATED and must be considered TOGETHER.
2. When a role is requested, you MUST check ALL fields in that row:
   - If the row says "Training Required: X Training" but user has completed "Y Training", this is a MISMATCH and should be REJECTED.
   - If the row has an Exception Scenario that matches the user (e.g., "Role not permitted for contractors" and user is a contractor), you MUST REJECT.
   - If the role, training, environment, and other fields don't match together, you should REJECT.
3. Training matching is CRITICAL - if role requires Training X but user completed Training Y, they are DIFFERENT and should be rejected.
4. Exception scenarios are HARD REJECTION CRITERIA - if any exception matches, decision MUST be "reject".

REQUEST DETAILS:
- Requested Permission: {requested_permission}
- Priority Score: {priority_score}/100

{rule_info}

{master_tracker_context}

{validation_summary}

USER CONTEXT:
{user_info}

PRE-REQUISITES STATUS ({prereq_met_count}/{prereq_total} met):
{prereqs_summary}
{similar_requests_summary}

TRAINING CONFIGURATION:
- Validation Rules: {training_config.get('validation_rules', 'Not specified')[:200]}
- Auto-approval Criteria: {training_config.get('auto_approval_criteria', 'Not specified')[:200]}
- Rejection Criteria: {training_config.get('rejection_criteria', 'Not specified')[:200]}

DECISION LOGIC - STRICT ENFORCEMENT:
=====================================
CRITICAL RULES (These MUST result in "reject"):
1. If ANY validation shows "Exception Violated: YES", decision MUST be "reject" - NO EXCEPTIONS
2. If training required in row doesn't match user's completed trainings, decision MUST be "reject" - NO EXCEPTIONS
   - If row requires "X Training" but user has "Y Training", REJECT
   - If row requires training but user has NO trainings, REJECT
   - Training is MANDATORY - cannot grant access without the exact required training
3. If role doesn't match and other fields also don't align, decision should be "reject"

ONLY approve ("grant") if ALL of these are true:
- Training matches exactly (or very close match)
- No exception violations
- Role aligns with request
- All other fields align

Return a JSON object with:
{{
    "decision": "grant" OR "create_ticket" OR "reject" OR "ask_for_more_info",
    "reasoning": "Clear explanation (2-3 sentences) for the decision. MUST reference specific fields from master tracker row if rejecting.",
    "confidence": 0.0 to 1.0,
    "missing_info": ["list of missing information if decision is ask_for_more_info", ...]
}}

Decision guidelines:
- "grant": Only if ALL row fields match user context AND no exceptions violated AND training matches
- "create_ticket": Send for manual review when uncertain or if some fields match but others need verification
- "reject": If training mismatch, exception violated, or role/fields don't align
- "ask_for_more_info": Request additional information if key details are missing

Return ONLY valid JSON, no additional text."""

            # Use AI enhancer's client
            if not self.ai_enhancer or not self.ai_enhancer.client:
                return self._make_rule_based_decision(rule, priority_score, pre_requisites_status, 
                                                     user_context, similar_requests, requested_permission)
            
            from config import USE_AZURE_OPENAI, AZURE_OPENAI_CHAT_DEPLOYMENT_NAME, MODEL_NAME
            model_or_deployment = AZURE_OPENAI_CHAT_DEPLOYMENT_NAME if USE_AZURE_OPENAI else MODEL_NAME
            
            response = self.ai_enhancer.client.chat.completions.create(
                model=model_or_deployment,
                messages=[
                    {"role": "system", "content": "You are an expert access management AI. Analyze requests and make decisions based on rules, context, and best practices. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,  # Lower temperature for more consistent decisions
                response_format={"type": "json_object"}
            )
            
            import json
            ai_decision = json.loads(response.choices[0].message.content)
            
            decision = ai_decision.get("decision", "create_ticket")
            reasoning = ai_decision.get("reasoning", "AI decision made")
            confidence = float(ai_decision.get("confidence", 0.7))
            
            # Store missing info if decision is ask_for_more_info
            if decision == "ask_for_more_info":
                missing_info = ai_decision.get("missing_info", [])
                reasoning += f"\n\nMissing Information Required: {', '.join(missing_info)}"
            
            logger.info(f"AI decision: {decision} (confidence: {confidence:.2f})")
            return decision, reasoning, min(1.0, max(0.0, confidence))
            
        except Exception as e:
            logger.error(f"Error in AI decision-making: {e}")
            # Fallback to rule-based
            return self._make_rule_based_decision(rule, priority_score, pre_requisites_status, 
                                                 user_context, similar_requests, requested_permission, description)
    
    def _make_rule_based_decision(self, rule: PermissionRule, priority_score: float,
                                  pre_requisites_status: Dict, user_context: Dict,
                                  similar_requests: List[Dict], requested_permission: str = "", description: str = "") -> Tuple[str, str, float]:
        """Fallback rule-based decision logic"""
        from config import AUTO_GRANT_THRESHOLD, REQUIRE_APPROVAL_THRESHOLD
        
        prereq_met_count = sum(1 for s in pre_requisites_status.values() if s["met"])
        prereq_total = len(pre_requisites_status)
        
        reasoning_parts = []
        confidence = 0.5
        
        if priority_score >= AUTO_GRANT_THRESHOLD and rule.auto_grant_enabled:
            if prereq_met_count >= prereq_total * 0.8:
                decision = "grant"
                confidence = 0.85
                reasoning_parts.append(f"High priority score ({priority_score}) and most pre-requisites met ({prereq_met_count}/{prereq_total})")
            else:
                decision = "create_ticket"
                confidence = 0.7
                reasoning_parts.append(f"High priority but missing pre-requisites ({prereq_met_count}/{prereq_total} met)")
        elif priority_score >= REQUIRE_APPROVAL_THRESHOLD:
            decision = "create_ticket"
            confidence = 0.75
            reasoning_parts.append(f"Moderate priority ({priority_score}) requires review")
        else:
            decision = "create_ticket"
            confidence = 0.8
            reasoning_parts.append(f"Low priority score ({priority_score}) requires manual review")
        
        if similar_requests:
            auto_granted_count = sum(1 for r in similar_requests if r.get("auto_granted"))
            if auto_granted_count > len(similar_requests) * 0.7:
                if decision == "grant":
                    confidence += 0.1
                reasoning_parts.append(f"Similar requests historically auto-granted ({auto_granted_count}/{len(similar_requests)})")
        
        base_reasoning = ". ".join(reasoning_parts)
        confidence = min(1.0, confidence)
        
        # Enhance reasoning with AI if available
        if self.ai_enhancer:
            enhanced_reasoning = self.ai_enhancer.enhance_reasoning(
                user_context, requested_permission, pre_requisites_status, priority_score, decision
            )
            final_reasoning = enhanced_reasoning if enhanced_reasoning else base_reasoning
        else:
            final_reasoning = base_reasoning
        
        return decision, final_reasoning, confidence
    
    def close(self):
        """Close database sessions"""
        if self.db:
            self.db.close()
        if self.user_context_manager:
            self.user_context_manager.close()

