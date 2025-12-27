"""Agentic AI Testing Portal - FastAPI Gateway for ServiceNow Integration"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, List
import uvicorn
from datetime import datetime

from agents.uam_agent import UAMAgent
from integrations.servicenow_client import get_servicenow_client
from utils.logger import logger
import config

app = FastAPI(
    title="Agentic AI Testing Portal",
    description="Portal for testing Agentic AI with ServiceNow integration",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize UAM Agent
uam_agent = UAMAgent()
servicenow_client = get_servicenow_client()


# Request Models
class AccessRequest(BaseModel):
    user_id: str = Field(..., description="User identifier (e.g., EMP001)")
    request_type: str = Field(..., description="Type of request (e.g., application_access)")
    requested_permission: str = Field(..., description="Permission being requested")
    description: str = Field(..., description="Description of the request")
    username: Optional[str] = Field(None, description="Username")
    email: Optional[str] = Field(None, description="Email address")
    department: Optional[str] = Field(None, description="Department")
    role: Optional[str] = Field(None, description="Role")


class ServiceNowTestRequest(BaseModel):
    user_id: str
    request_type: str
    requested_permission: str
    description: str


class ServiceNowConnectionTest(BaseModel):
    instance: str
    username: str
    password: str


# Root endpoint
@app.get("/", response_class=HTMLResponse)
async def root():
    """Home page with API documentation"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Agentic AI Testing Portal</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            h1 { color: #333; }
            h2 { color: #555; margin-top: 30px; }
            .endpoint { background: #f9f9f9; padding: 15px; margin: 10px 0; border-left: 4px solid #007bff; }
            .method { display: inline-block; padding: 4px 8px; background: #007bff; color: white; border-radius: 4px; font-size: 12px; margin-right: 10px; }
            .method.get { background: #28a745; }
            .method.post { background: #007bff; }
            code { background: #f4f4f4; padding: 2px 6px; border-radius: 3px; }
            .status { padding: 10px; margin: 10px 0; border-radius: 4px; }
            .status.success { background: #d4edda; color: #155724; }
            .status.error { background: #f8d7da; color: #721c24; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 Agentic AI Testing Portal</h1>
            <p>Portal for testing Agentic AI use cases with ServiceNow integration</p>
            
            <h2>📡 API Endpoints</h2>
            
            <div class="endpoint">
                <span class="method post">POST</span>
                <code>/api/access-request</code>
                <p>Submit an access request and test Agentic AI decision making</p>
            </div>
            
            <div class="endpoint">
                <span class="method get">GET</span>
                <code>/api/access-request/{request_id}</code>
                <p>Get details of a processed access request</p>
            </div>
            
            <div class="endpoint">
                <span class="method post">POST</span>
                <code>/api/servicenow/test-connection</code>
                <p>Test ServiceNow connection</p>
            </div>
            
            <div class="endpoint">
                <span class="method get">GET</span>
                <code>/api/servicenow/tickets</code>
                <p>List all ServiceNow tickets created</p>
            </div>
            
            <div class="endpoint">
                <span class="method get">GET</span>
                <code>/api/status</code>
                <p>Get system status and configuration</p>
            </div>
            
            <div class="endpoint">
                <span class="method get">GET</span>
                <code>/docs</code>
                <p>Interactive API documentation (Swagger UI)</p>
            </div>
            
            <h2>🔧 System Status</h2>
            <div id="status"></div>
            
            <script>
                fetch('/api/status')
                    .then(r => r.json())
                    .then(data => {
                        const statusDiv = document.getElementById('status');
                        const servicenowStatus = data.servicenow_configured 
                            ? '<div class="status success">✅ ServiceNow: Configured</div>'
                            : '<div class="status error">❌ ServiceNow: Not Configured</div>';
                        const aiStatus = data.ai_configured
                            ? '<div class="status success">✅ AI: Configured</div>'
                            : '<div class="status error">❌ AI: Not Configured</div>';
                        statusDiv.innerHTML = servicenowStatus + aiStatus;
                    });
            </script>
        </div>
    </body>
    </html>
    """
    return html_content


# Status endpoint
@app.get("/api/status")
async def get_status():
    """Get system status and configuration"""
    return {
        "status": "operational",
        "servicenow_configured": config.SERVICENOW_ENABLED,
        "servicenow_instance": config.SERVICENOW_INSTANCE if config.SERVICENOW_ENABLED else None,
        "ai_configured": bool(config.OPENAI_API_KEY),
        "ai_model": config.MODEL_NAME if config.OPENAI_API_KEY else None,
        "timestamp": datetime.now().isoformat()
    }


# Access Request Endpoint
@app.post("/api/access-request")
async def create_access_request(request: AccessRequest):
    """
    Submit an access request and test Agentic AI decision making
    
    This endpoint:
    1. Processes the request through the Agentic AI system
    2. Makes an intelligent decision (grant/create_ticket/reject)
    3. Creates a ServiceNow ticket if needed
    4. Returns the complete decision with reasoning
    """
    try:
        logger.info(f"Received access request from {request.user_id}: {request.requested_permission}")
        
        # Prepare user info
        user_info = {}
        if request.username:
            user_info["username"] = request.username
        if request.email:
            user_info["email"] = request.email
        if request.department:
            user_info["department"] = request.department
        if request.role:
            user_info["role"] = request.role
        
        # Process request through Agentic AI
        result = uam_agent.process_request(
            user_id=request.user_id,
            request_type=request.request_type,
            requested_permission=request.requested_permission,
            description=request.description,
            user_info=user_info if user_info else None
        )
        
        # If decision is to create ticket, create it in ServiceNow
        servicenow_ticket = None
        if result.get("status") == "ticket_created" and servicenow_client:
            try:
                sn_result = servicenow_client.create_access_request(
                    user_id=request.user_id,
                    request_type=request.request_type,
                    requested_permission=request.requested_permission,
                    description=request.description,
                    priority_score=result.get("priority_score", 0),
                    ai_decision=result.get("decision", "create_ticket"),
                    ai_reasoning=result.get("reasoning", "")
                )
                
                if sn_result.get("success"):
                    servicenow_ticket = {
                        "ticket_number": sn_result.get("ticket_number"),
                        "sys_id": sn_result.get("sys_id"),
                        "message": sn_result.get("message")
                    }
                    result["servicenow_ticket"] = servicenow_ticket
                    logger.info(f"ServiceNow ticket created: {sn_result.get('ticket_number')}")
            except Exception as e:
                logger.error(f"Failed to create ServiceNow ticket: {str(e)}")
                result["servicenow_error"] = str(e)
        
        return {
            "success": True,
            "request_id": result.get("request_id"),
            "decision": result.get("decision"),
            "status": result.get("status"),
            "priority_score": result.get("priority_score"),
            "reasoning": result.get("reasoning"),
            "confidence": result.get("confidence"),
            "pre_requisites_status": result.get("pre_requisites_status"),
            "servicenow_ticket": servicenow_ticket,
            "message": result.get("message", "Request processed successfully"),
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error processing access request: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")


# Get Request Details
@app.get("/api/access-request/{request_id}")
async def get_access_request(request_id: int):
    """Get details of a processed access request"""
    try:
        from database.user_context import UserContextManager
        ucm = UserContextManager()
        request = ucm.get_request(request_id)
        
        if not request:
            raise HTTPException(status_code=404, detail="Request not found")
        
        return {
            "success": True,
            "request_id": request.id,
            "user_id": request.user_id,
            "request_type": request.request_type,
            "requested_permission": request.requested_permission,
            "description": request.description,
            "priority_score": request.priority_score,
            "status": request.status,
            "decision_reason": request.decision_reason,
            "auto_granted": request.auto_granted,
            "ticket_id": request.ticket_id,
            "created_at": request.created_at.isoformat() if request.created_at else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching request {request_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ServiceNow Connection Test
@app.post("/api/servicenow/test-connection")
async def test_servicenow_connection(test: ServiceNowConnectionTest):
    """Test connection to ServiceNow instance"""
    try:
        from integrations.servicenow_client import ServiceNowClient
        
        # Create temporary client with test credentials
        test_client = ServiceNowClient()
        test_client.instance = test.instance.rstrip('/')
        test_client.username = test.username
        test_client.password = test.password
        
        success = test_client.test_connection()
        
        return {
            "success": success,
            "message": "Connection successful" if success else "Connection failed",
            "instance": test.instance
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Connection error: {str(e)}",
            "instance": test.instance
        }


# ServiceNow Tickets List
@app.get("/api/servicenow/tickets")
async def list_servicenow_tickets(user_id: Optional[str] = None):
    """List ServiceNow tickets (optionally filtered by user_id)"""
    if not servicenow_client:
        raise HTTPException(status_code=503, detail="ServiceNow not configured")
    
    try:
        query_params = {}
        if user_id:
            query_params["u_user_id"] = user_id
        
        tickets = servicenow_client.query_access_requests(query_params if query_params else None)
        
        return {
            "success": True,
            "count": len(tickets),
            "tickets": tickets
        }
    except Exception as e:
        logger.error(f"Error fetching ServiceNow tickets: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ServiceNow Ticket Details
@app.get("/api/servicenow/ticket/{sys_id}")
async def get_servicenow_ticket(sys_id: str):
    """Get details of a specific ServiceNow ticket"""
    if not servicenow_client:
        raise HTTPException(status_code=503, detail="ServiceNow not configured")
    
    try:
        ticket = servicenow_client.get_access_request(sys_id)
        
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")
        
        return {
            "success": True,
            "ticket": ticket
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching ServiceNow ticket {sys_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Health Check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

