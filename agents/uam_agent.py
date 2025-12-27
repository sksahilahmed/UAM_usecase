"""Main UAM Agentic AI Agent"""
from typing import Dict, Optional
from utils.logger import logger
from agents.decision_engine import DecisionEngine
from database.user_context import UserContextManager
from database.audit_log import AuditLogger

class UAMAgent:
    """Main UAM Agent that orchestrates the access management process"""
    
    def __init__(self):
        self.decision_engine = DecisionEngine()
        self.user_context_manager = UserContextManager()
        self.audit_logger = AuditLogger()
    
    def process_request(self, user_id: str, request_type: str,
                       requested_permission: str, description: str,
                       user_info: Optional[Dict] = None) -> Dict:
        """
        Process a user access request
        
        Args:
            user_id: Unique user identifier
            request_type: Type of request (e.g., "application_access")
            requested_permission: Specific permission requested
            description: Description of the request
            user_info: Optional user information (username, email, department, role)
        
        Returns:
            dict with processing result including decision, ticket info, etc.
        """
        logger.info(f"Processing request from user {user_id}: {requested_permission}")
        
        # Ensure user exists in database
        if user_info:
            self.user_context_manager.get_or_create_user(user_id, **user_info)
        
        # Evaluate request
        evaluation = self.decision_engine.evaluate_request(
            user_id, request_type, requested_permission, description
        )
        
        # Create request record
        request = self.user_context_manager.add_request(
            user_id=user_id,
            request_type=request_type,
            requested_permission=requested_permission,
            description=description,
            priority_score=evaluation["priority_score"],
            status=evaluation["decision"]
        )
        
        # Execute decision
        result = self._execute_decision(request.id, evaluation)
        
        # Update request with final status
        self.user_context_manager.update_request(
            request.id,
            status=result["status"],
            auto_granted=result.get("auto_granted", False),
            decision_reason=evaluation["reasoning"],
            pre_requisites_met=evaluation["pre_requisites_status"],
            ticket_id=result.get("ticket_id")
        )
        
        # Log audit
        master_tracker_context = {}
        if evaluation.get("rule_id"):
            from database.models import PermissionRule, get_db_session
            db = get_db_session()
            rule = db.query(PermissionRule).filter(PermissionRule.id == evaluation["rule_id"]).first()
            if rule:
                master_tracker_context = {
                    "permission_type": rule.permission_type,
                    "permission_name": rule.permission_name,
                    "priority_level": rule.priority_level,
                    "auto_grant_enabled": rule.auto_grant_enabled
                }
            db.close()
        
        self.audit_logger.log_request_decision(
            request_id=request.id,
            user_id=user_id,
            decision=result["status"],
            details={
                "requested_permission": requested_permission,
                "request_type": request_type,
                "priority_score": evaluation["priority_score"],
                "confidence": evaluation["confidence"],
                "auto_granted": result.get("auto_granted", False),
                "ticket_id": result.get("ticket_id")
            },
            reasoning=evaluation["reasoning"],
            master_tracker_context=master_tracker_context
        )
        
        return {
            "request_id": request.id,
            "user_id": user_id,
            "requested_permission": requested_permission,
            "decision": evaluation["decision"],
            "status": result["status"],
            "priority_score": evaluation["priority_score"],
            "reasoning": evaluation["reasoning"],
            "confidence": evaluation["confidence"],
            "pre_requisites_status": evaluation["pre_requisites_status"],
            **result
        }
    
    def _execute_decision(self, request_id: int, evaluation: Dict) -> Dict:
        """Execute the decision (grant access, create ticket, reject, or ask for more info)"""
        decision = evaluation["decision"]
        
        if decision == "grant":
            # Auto-grant access
            # In a real system, this would call the actual access management system
            logger.info(f"Auto-granting access for request {request_id}")
            return {
                "status": "granted",
                "auto_granted": True,
                "message": "Access has been automatically granted"
            }
        
        elif decision == "reject":
            # Reject the request
            logger.info(f"Rejecting request {request_id}")
            return {
                "status": "rejected",
                "auto_granted": False,
                "message": "Request has been rejected based on validation rules"
            }
        
        elif decision == "ask_for_more_info":
            # Request more information
            logger.info(f"Requesting more information for request {request_id}")
            return {
                "status": "needs_more_info",
                "auto_granted": False,
                "message": "Additional information required to process this request"
            }
        
        elif decision == "create_ticket":
            # Create ticket (currently simulated, will integrate with ServiceNow later)
            ticket_id = self._create_ticket(request_id, evaluation)
            return {
                "status": "ticket_created",
                "auto_granted": False,
                "ticket_id": ticket_id,
                "message": f"Ticket created for manual review: {ticket_id}"
            }
        
        else:
            return {
                "status": "pending_review",
                "auto_granted": False,
                "message": "Request requires manual review"
            }
    
    def _create_ticket(self, request_id: int, evaluation: Dict) -> str:
        """
        Create a ticket in ServiceNow
        
        Tries to create a real ServiceNow ticket if configured,
        otherwise falls back to simulated ticket ID
        """
        from integrations.servicenow_client import get_servicenow_client
        from database.user_context import UserContextManager
        
        servicenow_client = get_servicenow_client()
        
        # Try to create real ServiceNow ticket
        if servicenow_client:
            try:
                # Get request details
                ucm = UserContextManager()
                request = ucm.get_request(request_id)
                
                if request:
                    result = servicenow_client.create_access_request(
                        user_id=request.user_id,
                        request_type=request.request_type,
                        requested_permission=request.requested_permission,
                        description=request.description,
                        priority_score=evaluation.get("priority_score", 0),
                        ai_decision=evaluation.get("decision", "create_ticket"),
                        ai_reasoning=evaluation.get("reasoning", "")
                    )
                    
                    if result.get("success") and result.get("ticket_number"):
                        ticket_id = result.get("ticket_number")
                        logger.info(f"Created ServiceNow ticket {ticket_id} for request {request_id}")
                        return ticket_id
            except Exception as e:
                logger.warning(f"Failed to create ServiceNow ticket, using fallback: {str(e)}")
        
        # Fallback to simulated ticket ID
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        ticket_id = f"TKT-{timestamp}-{request_id}"
        logger.info(f"Created simulated ticket {ticket_id} for request {request_id}")
        
        return ticket_id
    
    def get_user_access_summary(self, user_id: str) -> Dict:
        """Get summary of user's access and request history"""
        context = self.user_context_manager.get_user_context(user_id)
        if not context:
            return {"error": "User not found"}
        
        return {
            "user_id": context["user_id"],
            "username": context.get("username"),
            "department": context.get("department"),
            "role": context.get("role"),
            "current_permissions": context.get("current_permissions", {}),
            "recent_requests": context.get("recent_requests", []),
            "total_permissions": len(context.get("current_permissions", {})),
            "total_requests": len(context.get("recent_requests", []))
        }
    
    def close(self):
        """Cleanup resources"""
        self.decision_engine.close()
        self.user_context_manager.close()
        if hasattr(self, 'audit_logger'):
            self.audit_logger.close()

