import logging
import sys
import json

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_obj={
            "level": record.levelname,
            "timestamp":self.formatTime(record),
            "module": record.module,
        }

    #if the record is already in json, must be ingested directly, to avoid nested json

        if isinstance(record.msg, dict):
            log_obj.update(record.msg)
        else:
            log_obj["message"]=record.getMessage()

        if hasattr(record, "props"):
            log_obj.update(record.props)
        
        return json.dumps(log_obj)
    
def setup_logging():
    logger = logging.getLogger("json_logger")

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        logger.propagate= False #clash with logs from cloud service can lead to duplicates

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    return logger

        
    
logger = setup_logging()


