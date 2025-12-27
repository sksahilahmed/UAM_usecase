"""OpenAI client initialization - supports both OpenAI and Azure OpenAI"""
from typing import Optional
from utils.logger import logger

# Try to import openai
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    openai = None
    logger.warning("OpenAI package not installed. AI features will be disabled.")

def get_openai_client(api_key: Optional[str] = None, 
                     azure_endpoint: Optional[str] = None,
                     api_version: Optional[str] = None,
                     deployment_name: Optional[str] = None,
                     use_azure: bool = False):
    """
    Get OpenAI client - supports both regular OpenAI and Azure OpenAI
    
    Args:
        api_key: OpenAI API key or Azure OpenAI API key
        azure_endpoint: Azure OpenAI endpoint URL
        api_version: Azure API version
        deployment_name: Azure deployment name
        use_azure: Whether to use Azure OpenAI
    
    Returns:
        OpenAI client instance or None if not available
    """
    if not OPENAI_AVAILABLE or not openai:
        return None
    
    if not api_key:
        logger.warning("No API key provided for OpenAI client")
        return None
    
    try:
        if use_azure and azure_endpoint and deployment_name:
            # Initialize Azure OpenAI client
            # In OpenAI SDK 1.0+, deployment_name is not a constructor parameter
            # It's used as the model parameter when making API calls
            client = openai.AzureOpenAI(
                api_key=api_key,
                api_version=api_version or "2024-02-15-preview",
                azure_endpoint=azure_endpoint
            )
            # Store deployment name for use in API calls
            client._deployment_name = deployment_name
            logger.info(f"Azure OpenAI client initialized successfully (deployment: {deployment_name})")
            return client
        else:
            # Initialize regular OpenAI client
            client = openai.OpenAI(api_key=api_key)
            logger.info("OpenAI client initialized successfully")
            return client
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {e}")
        return None

