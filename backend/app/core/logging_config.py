"""
Enhanced Logging Configuration for Music Discovery System
Filters out noise and enhances agentic workflow visibility
"""

import logging
import logging.config
import os
from pathlib import Path
from typing import Dict, Any

class SupabaseFilter(logging.Filter):
    """Filter out Supabase HTTP requests for cleaner logs"""
    
    def filter(self, record):
        # Filter out httpx requests to Supabase
        if record.name == 'httpx' and hasattr(record, 'getMessage'):
            message = record.getMessage()
            if 'supabase.co' in message:
                return False
        return True

class AgenticWorkflowFormatter(logging.Formatter):
    """Enhanced formatter for agentic workflows with timing and progress"""
    
    def format(self, record):
        # Add timing information for key operations
        if hasattr(record, 'operation_time'):
            record.msg = f"{record.msg} ⏱️ {record.operation_time:.2f}s"
        
        # Add progress indicators
        if hasattr(record, 'progress'):
            record.msg = f"[{record.progress}] {record.msg}"
        
        return super().format(record)

def setup_enhanced_logging():
    """Setup enhanced logging configuration"""
    
    # Create logs directory first - handle both local and Docker paths
    log_dir = Path("/app/logs")
    if not log_dir.exists():
        # Try relative path for local development
        log_dir = Path("logs")
    
    # Ensure the directory exists
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file_path = log_dir / "agentic_workflows.log"
    except (PermissionError, OSError) as e:
        # Fallback to console-only logging if we can't create log files
        print(f"Warning: Could not create log directory {log_dir}: {e}")
        log_file_path = None
    
    # Build handlers dynamically based on what's available
    handlers = {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
            'formatter': 'agentic_workflow',
            'filters': ['supabase_filter'],
            'stream': 'ext://sys.stdout'
        }
    }
    
    # Only add file handler if we can create the log file
    if log_file_path:
        handlers['file'] = {
            'class': 'logging.FileHandler',
            'level': 'DEBUG',
            'formatter': 'agentic_workflow',
            'filters': ['supabase_filter'],
            'filename': str(log_file_path),
            'mode': 'a'
        }
    
    # Determine which handlers to use
    agent_handlers = ['console']
    httpx_handlers = ['console']
    if log_file_path:
        agent_handlers.append('file')
        httpx_handlers = ['file']
    
    config: Dict[str, Any] = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'agentic_workflow': {
                '()': AgenticWorkflowFormatter,
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            },
            'standard': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            }
        },
        'filters': {
            'supabase_filter': {
                '()': SupabaseFilter
            }
        },
        'handlers': handlers,
        'loggers': {
            'app.agents': {
                'level': 'DEBUG',
                'handlers': agent_handlers,
                'propagate': False
            },
            'app.api': {
                'level': 'INFO',
                'handlers': ['console'],
                'propagate': False
            },
            'httpx': {
                'level': 'WARNING',  # Reduce httpx noise
                'handlers': httpx_handlers,
                'propagate': False
            }
        },
        'root': {
            'level': 'INFO',
            'handlers': ['console']
        }
    }
    
    logging.config.dictConfig(config)
    
    logger = logging.getLogger(__name__)
    if log_file_path:
        logger.info(f"Enhanced logging configured. Log file: {log_file_path}")
    else:
        logger.warning("File logging disabled - using console only")
    
    return logger

def get_progress_logger(name: str, total_items: int = None):
    """Get a logger with progress tracking capabilities"""
    logger = logging.getLogger(name)
    
    class ProgressLogger:
        def __init__(self, logger, total):
            self.logger = logger
            self.total = total
            self.current = 0
        
        def step(self, message: str, **kwargs):
            self.current += 1
            progress = f"{self.current}/{self.total}" if self.total else str(self.current)
            extra = {'progress': progress}
            extra.update(kwargs)
            self.logger.info(message, extra=extra)
        
        def error(self, message: str, **kwargs):
            progress = f"{self.current}/{self.total}" if self.total else str(self.current)
            extra = {'progress': progress}
            extra.update(kwargs)
            self.logger.error(message, extra=extra)
        
        def debug(self, message: str, **kwargs):
            extra = kwargs
            self.logger.debug(message, extra=extra)
    
    return ProgressLogger(logger, total_items) 