"""Logging utility with fallback to standard logging if loguru is not available"""
import sys
from pathlib import Path

try:
    from loguru import logger as _loguru_logger
    
    # Configure loguru logger
    class Logger:
        """Wrapper for loguru logger"""
        def __init__(self):
            self.logger = _loguru_logger
        
        def add(self, *args, **kwargs):
            """Add log handler"""
            return self.logger.add(*args, **kwargs)
        
        def info(self, *args, **kwargs):
            """Log info message"""
            return self.logger.info(*args, **kwargs)
        
        def error(self, *args, **kwargs):
            """Log error message"""
            return self.logger.error(*args, **kwargs)
        
        def warning(self, *args, **kwargs):
            """Log warning message"""
            return self.logger.warning(*args, **kwargs)
        
        def debug(self, *args, **kwargs):
            """Log debug message"""
            return self.logger.debug(*args, **kwargs)
        
        def success(self, *args, **kwargs):
            """Log success message"""
            return self.logger.success(*args, **kwargs)
    
    logger = Logger()
    LOGURU_AVAILABLE = True
    
except ImportError:
    # Fallback to standard logging
    import logging
    from logging import getLogger
    
    # Configure standard logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    class Logger:
        """Fallback logger using standard logging"""
        def __init__(self):
            self.logger = getLogger('uam_system')
        
        def add(self, *args, **kwargs):
            """Add log handler (for compatibility)"""
            # Try to add file handler if path provided
            if args:
                log_path = args[0]
                if isinstance(log_path, Path):
                    try:
                        # Create directory if it doesn't exist
                        log_path.parent.mkdir(parents=True, exist_ok=True)
                        file_handler = logging.FileHandler(log_path)
                        file_handler.setFormatter(
                            logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                        )
                        self.logger.addHandler(file_handler)
                    except Exception as e:
                        # If file logging fails, just use console logging
                        pass
            return None
        
        def info(self, *args, **kwargs):
            """Log info message"""
            return self.logger.info(*args, **kwargs)
        
        def error(self, *args, **kwargs):
            """Log error message"""
            return self.logger.error(*args, **kwargs)
        
        def warning(self, *args, **kwargs):
            """Log warning message"""
            return self.logger.warning(*args, **kwargs)
        
        def debug(self, *args, **kwargs):
            """Log debug message"""
            return self.logger.debug(*args, **kwargs)
        
        def success(self, *args, **kwargs):
            """Log success message"""
            return self.logger.info(*args, **kwargs)  # Use info for success
    
    logger = Logger()
    LOGURU_AVAILABLE = False
    
    # Print warning
    print("[WARNING] loguru not installed. Using standard logging instead.")
    print("   To install loguru, run: pip install loguru")
    print("   Or install all dependencies: pip install -r requirements.txt\n")

