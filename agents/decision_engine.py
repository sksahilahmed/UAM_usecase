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
        
        # Find matching permission rule
        rule = self._find_permission_rule(requested_permission, request_type)
        if not rule:
            logger.warning(f"No rule found for {requested_permission}")
            return {
                "decision": "create_ticket",
                "priority_score": 50.0,
                "pre_requisites_status": {},
                "reasoning": "No matching rule found. Ticket required for manual review.",
                "confidence": 0.5
            }
        
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
        
        # Make decision
        decision, reasoning, confidence = self._make_decision(
            rule, priority_score, pre_requisites_status, 
            user_context, similar_requests, requested_permission
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
            prereq_lower = prereq.lower()
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
                completed_trainings = context_data.get("completed_trainings", [])
                training_type = prereq_lower.replace("training", "").strip()
                met = any(training_type in t.lower() for t in completed_trainings) if training_type else len(completed_trainings) > 0
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
        score += priority_bonus.get(rule.priority_level.lower(), 0)
        
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
                      similar_requests: List[Dict], requested_permission: str = "") -> Tuple[str, str, float]:
        """
        Make final decision: grant, create_ticket, or reject
        
        Returns: (decision, reasoning, confidence)
        """
        from config import AUTO_GRANT_THRESHOLD, REQUIRE_APPROVAL_THRESHOLD
        
        # Calculate how many pre-requisites are met
        prereq_met_count = sum(1 for s in pre_requisites_status.values() if s["met"])
        prereq_total = len(pre_requisites_status)
        
        reasoning_parts = []
        confidence = 0.5
        
        # Decision logic
        if priority_score >= AUTO_GRANT_THRESHOLD and rule.auto_grant_enabled:
            # Check if critical pre-requisites are met
            critical_prereqs = ["manager approval", "security clearance"]
            has_critical = any(
                any(cp in k.lower() for cp in critical_prereqs)
                for k, v in pre_requisites_status.items() if v["met"]
            )
            
            if prereq_met_count >= prereq_total * 0.8:  # 80% of pre-requisites met
                decision = "grant"
                confidence = 0.85
                reasoning_parts.append(f"High priority score ({priority_score}) and most pre-requisites met ({prereq_met_count}/{prereq_total})")
                reasoning_parts.append(f"Rule allows auto-grant")
            else:
                decision = "create_ticket"
                confidence = 0.7
                reasoning_parts.append(f"High priority but missing critical pre-requisites ({prereq_met_count}/{prereq_total} met)")
        
        elif priority_score >= REQUIRE_APPROVAL_THRESHOLD:
            decision = "create_ticket"
            confidence = 0.75
            reasoning_parts.append(f"Moderate priority ({priority_score}) requires review")
            if prereq_met_count < prereq_total:
                reasoning_parts.append(f"Some pre-requisites not met ({prereq_met_count}/{prereq_total})")
        
        else:
            decision = "create_ticket"  # Low priority, always create ticket
            confidence = 0.8
            reasoning_parts.append(f"Low priority score ({priority_score}) requires manual review")
        
        # Add similar request patterns
        if similar_requests:
            auto_granted_count = sum(1 for r in similar_requests if r.get("auto_granted"))
            if auto_granted_count > len(similar_requests) * 0.7:
                if decision == "grant":
                    confidence += 0.1
                reasoning_parts.append(f"Similar requests historically auto-granted ({auto_granted_count}/{len(similar_requests)})")
        
        base_reasoning = ". ".join(reasoning_parts)
        confidence = min(1.0, confidence)
        
        # Enhance reasoning with AI if available
        enhanced_reasoning = None
        if self.ai_enhancer:
            enhanced_reasoning = self.ai_enhancer.enhance_reasoning(
                user_context, 
                requested_permission,
                pre_requisites_status,
                priority_score,
                decision
            )
        
        # Use AI-enhanced reasoning if available, otherwise use base reasoning
        final_reasoning = enhanced_reasoning if enhanced_reasoning else base_reasoning
        
        return decision, final_reasoning, confidence
    
    def close(self):
        """Close database sessions"""
        if self.db:
            self.db.close()
        if self.user_context_manager:
            self.user_context_manager.close()

