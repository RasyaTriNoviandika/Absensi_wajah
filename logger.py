# =================== LOGGER.PY - LOGGING SYSTEM ===================
import logging
import os
from logging.handlers import RotatingFileHandler
from pythonjsonlogger import jsonlogger
from datetime import datetime

def setup_logger(app):
    """Setup application logger with rotation and JSON format"""
    
    # Create logs directory
    log_dir = 'logs'
    os.makedirs(log_dir, exist_ok=True)
    
    # Get log level from config
    log_level = getattr(logging, app.config.get('LOG_LEVEL', 'INFO'))
    
    # Configure app logger
    app.logger.setLevel(log_level)
    
    # Remove default handlers
    app.logger.handlers.clear()
    
    # Console Handler (Human Readable)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    
    # File Handler (JSON Format for parsing)
    log_file = os.path.join(log_dir, app.config.get('LOG_FILE', 'app.log'))
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10485760,  # 10MB
        backupCount=10
    )
    file_handler.setLevel(log_level)
    
    # JSON Formatter
    json_formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(levelname)s %(name)s %(message)s'
    )
    file_handler.setFormatter(json_formatter)
    
    # Add handlers
    app.logger.addHandler(console_handler)
    app.logger.addHandler(file_handler)
    
    # Log startup
    app.logger.info(f"Application started - Environment: {app.config.get('FLASK_ENV', 'development')}")
    
    return app.logger

def log_user_action(logger, action, user_type, username, details=None):
    """Log user actions for audit trail"""
    log_data = {
        'timestamp': datetime.utcnow().isoformat(),
        'action': action,
        'user_type': user_type,
        'username': username,
        'details': details or {}
    }
    logger.info(f"USER_ACTION: {log_data}")

def log_security_event(logger, event_type, details):
    """Log security-related events"""
    log_data = {
        'timestamp': datetime.utcnow().isoformat(),
        'event_type': event_type,
        'details': details
    }
    logger.warning(f"SECURITY_EVENT: {log_data}")

def log_error(logger, error_type, error_message, traceback_info=None):
    """Log errors with context"""
    log_data = {
        'timestamp': datetime.utcnow().isoformat(),
        'error_type': error_type,
        'error_message': str(error_message),
        'traceback': traceback_info
    }
    logger.error(f"ERROR: {log_data}")