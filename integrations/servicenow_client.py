"""ServiceNow REST API Client for Agentic AI Integration"""
import requests
import base64
from typing import Dict, Optional, List
from utils.logger import logger
import config


class ServiceNowClient:
    """Client for interacting with ServiceNow REST API"""
    
    def __init__(self):
        self.instance = config.SERVICENOW_INSTANCE.rstrip('/')
        self.username = config.SERVICENOW_USERNAME
        self.password = config.SERVICENOW_PASSWORD
        self.api_base = config.SERVICENOW_API_BASE if hasattr(config, 'SERVICENOW_API_BASE') else '/api/x/agentic_ai'
        self.table_name = config.SERVICENOW_TABLE_NAME if hasattr(config, 'SERVICENOW_TABLE_NAME') else 'u_access_request'
        
        # Validate configuration
        if not self.instance:
            raise ValueError("SERVICENOW_INSTANCE not configured in .env file")
        if not self.username or not self.password:
            raise ValueError("SERVICENOW_USERNAME and SERVICENOW_PASSWORD required in .env file")
        
        # Setup authentication
        self.auth = (self.username, self.password)
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """Make HTTP request to ServiceNow API"""
        url = f"{self.instance}{endpoint}"
        
        try:
            if method.upper() == 'GET':
                response = requests.get(url, auth=self.auth, headers=self.headers, params=data)
            elif method.upper() == 'POST':
                response = requests.post(url, auth=self.auth, headers=self.headers, json=data)
            elif method.upper() == 'PUT':
                response = requests.put(url, auth=self.auth, headers=self.headers, json=data)
            elif method.upper() == 'PATCH':
                response = requests.patch(url, auth=self.auth, headers=self.headers, json=data)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, auth=self.auth, headers=self.headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.HTTPError as e:
            logger.error(f"ServiceNow API error: {e.response.status_code} - {e.response.text}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"ServiceNow connection error: {str(e)}")
            raise
    
    def test_connection(self) -> bool:
        """Test connection to ServiceNow instance"""
        try:
            # Try to access a basic endpoint
            endpoint = '/api/now/table/sys_user?sysparm_limit=1'
            self._make_request('GET', endpoint)
            logger.info("ServiceNow connection test successful")
            return True
        except Exception as e:
            logger.error(f"ServiceNow connection test failed: {str(e)}")
            return False
    
    def create_access_request(self, user_id: str, request_type: str, 
                             requested_permission: str, description: str,
                             priority_score: float, ai_decision: str, 
                             ai_reasoning: str) -> Dict:
        """
        Create an access request ticket in ServiceNow
        
        Args:
            user_id: User identifier
            request_type: Type of request
            requested_permission: Permission being requested
            description: Request description
            priority_score: AI-calculated priority score
            ai_decision: AI decision (grant/create_ticket/reject)
            ai_reasoning: AI reasoning explanation
        
        Returns:
            dict with ticket information
        """
        endpoint = f"{self.api_base}/access-request"
        
        payload = {
            'user_id': user_id,
            'request_type': request_type,
            'requested_permission': requested_permission,
            'description': description,
            'priority_score': int(priority_score),
            'ai_decision': ai_decision,
            'ai_reasoning': ai_reasoning
        }
        
        logger.info(f"Creating ServiceNow ticket for user {user_id}: {requested_permission}")
        result = self._make_request('POST', endpoint, data=payload)
        
        return {
            'success': result.get('success', False),
            'ticket_number': result.get('ticket_number'),
            'sys_id': result.get('sys_id'),
            'message': result.get('message', 'Ticket created')
        }
    
    def get_access_request(self, sys_id: str) -> Optional[Dict]:
        """
        Get access request details from ServiceNow
        
        Args:
            sys_id: ServiceNow system ID
        
        Returns:
            dict with ticket details or None if not found
        """
        endpoint = f"{self.api_base}/access-request/{sys_id}"
        
        try:
            result = self._make_request('GET', endpoint)
            if result.get('success'):
                return result.get('data')
            return None
        except Exception as e:
            logger.error(f"Error fetching access request {sys_id}: {str(e)}")
            return None
    
    def update_access_request(self, sys_id: str, updates: Dict) -> bool:
        """
        Update an access request in ServiceNow
        
        Args:
            sys_id: ServiceNow system ID
            updates: Dictionary of fields to update
        
        Returns:
            bool indicating success
        """
        endpoint = f"{self.api_base}/access-request/{sys_id}"
        
        try:
            result = self._make_request('PATCH', endpoint, data=updates)
            return result.get('success', False)
        except Exception as e:
            logger.error(f"Error updating access request {sys_id}: {str(e)}")
            return False
    
    def query_access_requests(self, query_params: Optional[Dict] = None) -> List[Dict]:
        """
        Query access requests from ServiceNow
        
        Args:
            query_params: Query parameters (e.g., {'user_id': 'EMP001'})
        
        Returns:
            List of access request records
        """
        endpoint = f"/api/now/table/{self.table_name}"
        
        params = {'sysparm_limit': 100}
        if query_params:
            # Build encoded query string
            query_parts = [f"{k}={v}" for k, v in query_params.items()]
            params['sysparm_query'] = '^'.join(query_parts)
        
        try:
            result = self._make_request('GET', endpoint, data=params)
            return result.get('result', [])
        except Exception as e:
            logger.error(f"Error querying access requests: {str(e)}")
            return []


# Singleton instance
_service_now_client = None

def get_servicenow_client() -> Optional[ServiceNowClient]:
    """Get or create ServiceNow client instance"""
    global _service_now_client
    
    if _service_now_client is None:
        try:
            _service_now_client = ServiceNowClient()
        except ValueError as e:
            logger.warning(f"ServiceNow not configured: {str(e)}")
            return None
    
    return _service_now_client

