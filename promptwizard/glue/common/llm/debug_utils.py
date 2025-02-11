import os
import logging

from ..utils.logging import get_glue_logger

logger = get_glue_logger(__name__)

DEBUG_MODE = os.environ.get("LLM_DEBUG", "False").lower() == "true"

if DEBUG_MODE:
    logger.setLevel(logging.DEBUG)

def debug_log(message: str):
    """
    Logs debug messages only if DEBUG_MODE is True.
    """
    if DEBUG_MODE:
        logger.debug(message)
