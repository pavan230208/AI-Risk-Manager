import logging
import json
import traceback
from datetime import datetime, timezone
from app.core.config import settings

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage()
        }
        
        # Avoid logging sensitive things like JWT in standard records (they shouldn't be there anyway)
        if "secret" in log_data["message"].lower() or "jwt" in log_data["message"].lower() or "password" in log_data["message"].lower():
            if "key" in log_data["message"].lower() or "groq" in log_data["message"].lower():
                log_data["message"] = "[REDACTED POTENTIALLY SENSITIVE INFORMATION]"
        
        if record.exc_info:
            log_data["exception"] = "".join(traceback.format_exception(*record.exc_info))
            
        return json.dumps(log_data)

def setup_logging():
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Remove existing handlers to avoid duplicates
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        
    handler = logging.StreamHandler()
    
    if settings.ENVIRONMENT == "production":
        handler.setFormatter(JSONFormatter())
    else:
        # Development mode uses standard text formatting
        formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s")
        handler.setFormatter(formatter)
        
    root_logger.addHandler(handler)
