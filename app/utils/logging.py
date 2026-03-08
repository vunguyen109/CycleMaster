import logging
from .config import settings


def setup_logging():
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    
    handlers = [
        logging.StreamHandler()
    ]
    
    if settings.log_file:
        handlers.append(logging.FileHandler(settings.log_file, encoding='utf-8'))
        
    logging.basicConfig(
        level=level,
        format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
        handlers=handlers
    )
