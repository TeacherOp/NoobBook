import logging
from functools import wraps

logger = logging.getLogger(__name__)

def safe_tool_handler(default_message="Tool execution failed"):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                logger.exception(f"{default_message}: {e}")
                return {
                    "success": False,
                    "error": f"{default_message}: {str(e)}"
                }
        return wrapper
    return decorator
