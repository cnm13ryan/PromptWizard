import os
from ..utils.logging import get_glue_logger

logger = get_glue_logger(__name__)

def use_openai_api_key() -> bool:
    """
    Returns True if we should use an OpenAI API key flow,
    according to environment variable USE_OPENAI_API_KEY.
    """
    return os.environ.get("USE_OPENAI_API_KEY", "False") == "True"


def get_openai_config() -> dict:
    """
    Returns a dictionary of settings for OpenAI calls.
    Expects environment variables: OPENAI_API_KEY, OPENAI_MODEL_NAME.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    model_name = os.environ.get("OPENAI_MODEL_NAME", "")
    temperature = 0.0

    if not api_key:
        logger.warning("OPENAI_API_KEY is not set or empty.")

    return {
        "api_key": api_key,
        "model_name": model_name,
        "temperature": temperature,
    }


def get_azure_config() -> dict:
    """
    Returns a dictionary of settings for Azure OpenAI calls.
    Expects environment variables: OPENAI_API_VERSION,
    AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT_NAME.
    """
    api_version = os.environ.get("OPENAI_API_VERSION", "")
    azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
    deployment_name = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "")
    temperature = 0.0

    if not azure_endpoint:
        logger.warning("AZURE_OPENAI_ENDPOINT is not set or empty.")
    if not deployment_name:
        logger.warning("AZURE_OPENAI_DEPLOYMENT_NAME is not set or empty.")

    return {
        "api_version": api_version,
        "azure_endpoint": azure_endpoint, 
        "deployment_name": deployment_name, 
        "temperature": temperature,
    }


def get_model_type() -> str:
    """
    Returns the string describing the model type, default to 'AzureOpenAI'.
    e.g. 'AzureOpenAI', 'LLamaAML', etc.
    """
    return os.environ.get("MODEL_TYPE", "AzureOpenAI")
