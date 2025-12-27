"""AI-powered reasoning enhancement using OpenAI"""
from typing import Dict, Optional
from utils.logger import logger

# Try to import openai, but handle gracefully if not available
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI package not installed. AI reasoning will be disabled.")

from config import (
    OPENAI_API_KEY, MODEL_NAME, TEMPERATURE, USE_AI_REASONING,
    USE_AZURE_OPENAI, AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_API_VERSION, AZURE_OPENAI_CHAT_DEPLOYMENT_NAME
)
from utils.openai_client import get_openai_client

class AIReasoningEnhancer:
    """Uses OpenAI to enhance decision reasoning - supports both OpenAI and Azure OpenAI"""
    
    def __init__(self):
        if not OPENAI_AVAILABLE:
            self.client = None
            self.enabled = False
            logger.warning("OpenAI package not available. AI reasoning disabled.")
        else:
            # Try to initialize client (Azure or regular OpenAI)
            api_key = AZURE_OPENAI_API_KEY if USE_AZURE_OPENAI else OPENAI_API_KEY
            api_key = api_key or OPENAI_API_KEY  # Fallback to regular key
            
            if not api_key or api_key == "your-openai-api-key-here":
                self.client = None
                self.enabled = False
                logger.warning("OpenAI API key not configured. AI reasoning disabled.")
            else:
                self.client = get_openai_client(
                    api_key=api_key,
                    azure_endpoint=AZURE_OPENAI_ENDPOINT if USE_AZURE_OPENAI else None,
                    api_version=AZURE_OPENAI_API_VERSION if USE_AZURE_OPENAI else None,
                    deployment_name=AZURE_OPENAI_CHAT_DEPLOYMENT_NAME if USE_AZURE_OPENAI else None,
                    use_azure=USE_AZURE_OPENAI
                )
                self.enabled = USE_AI_REASONING if self.client else False
                if not self.client:
                    logger.warning("Failed to initialize OpenAI client. AI reasoning disabled.")
    
    def enhance_reasoning(self, user_context: Dict, requested_permission: str,
                         pre_requisites_status: Dict, priority_score: float,
                         decision: str) -> Optional[str]:
        """
        Use AI to generate enhanced reasoning for the decision
        
        Returns enhanced reasoning text or None if AI not available
        """
        if not self.enabled or not self.client:
            return None
        
        try:
            # Prepare context for AI
            user_info = f"""
            User ID: {user_context.get('user_id', 'N/A')}
            Department: {user_context.get('department', 'N/A')}
            Role: {user_context.get('role', 'N/A')}
            Current Permissions: {len(user_context.get('current_permissions', {}))} active
            Recent Requests: {len(user_context.get('recent_requests', []))} in history
            """
            
            prereqs_summary = "\n".join([
                f"- {prereq}: {'✓ Met' if status['met'] else '✗ Not Met'} ({status.get('details', '')})"
                for prereq, status in pre_requisites_status.items()
            ])
            
            prompt = f"""You are an access management AI assistant. Analyze this access request decision and provide clear, professional reasoning.

REQUESTED PERMISSION: {requested_permission}

USER CONTEXT:
{user_info}

PRE-REQUISITES STATUS:
{prereqs_summary}

DECISION: {decision.upper()}
PRIORITY SCORE: {priority_score}/100

Provide a concise, professional explanation (2-3 sentences) for why this decision was made, focusing on:
1. Key factors that influenced the decision
2. Pre-requisites status
3. Risk assessment if relevant

Keep it clear and suitable for audit logs."""
            
            # Use deployment name for Azure, model name for regular OpenAI
            model_or_deployment = AZURE_OPENAI_CHAT_DEPLOYMENT_NAME if USE_AZURE_OPENAI else MODEL_NAME
            response = self.client.chat.completions.create(
                model=model_or_deployment,
                messages=[
                    {"role": "system", "content": "You are a security and access management expert. Provide clear, professional explanations for access decisions."},
                    {"role": "user", "content": prompt}
                ],
                temperature=TEMPERATURE,
                max_tokens=200
            )
            
            enhanced_reasoning = response.choices[0].message.content.strip()
            logger.info("AI reasoning generated successfully")
            return enhanced_reasoning
            
        except Exception as e:
            logger.error(f"Error generating AI reasoning: {e}")
            return None
    
    def analyze_request_description(self, description: str) -> Optional[Dict]:
        """
        Use AI to analyze request description and extract insights
        Returns dict with extracted information
        """
        if not self.enabled or not self.client:
            return None
        
        try:
            prompt = f"""Analyze this access request description and extract key information.

DESCRIPTION: {description}

Extract and return JSON with:
- urgency: "high", "medium", or "low"
- business_justification: brief summary
- risk_level: "high", "medium", or "low"
- key_keywords: array of important terms

Return only valid JSON, no additional text."""
            
            # Use deployment name for Azure, model name for regular OpenAI
            model_or_deployment = AZURE_OPENAI_CHAT_DEPLOYMENT_NAME if USE_AZURE_OPENAI else MODEL_NAME
            response = self.client.chat.completions.create(
                model=model_or_deployment,
                messages=[
                    {"role": "system", "content": "You are an expert at analyzing access requests. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=TEMPERATURE,
                response_format={"type": "json_object"}
            )
            
            import json
            analysis = json.loads(response.choices[0].message.content)
            logger.info("Request description analyzed by AI")
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing request description: {e}")
            return None

