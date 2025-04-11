import inspect
import logging
import structlog
import sys
import traceback
import yaml
from typing import Dict, Any, Optional, List, Callable

# Configure the standard Python logging to work with structlog
logging.basicConfig(
    format="%(message)s",
    level=logging.INFO,
)

# Create a custom processor that adds caller information
def add_caller_info(_, __, event_dict):
    """Add the caller's function name and line number to the log entry."""
    # Get the caller's frame (skip structlog and this processor)
    frame = inspect.currentframe()
    # Go back multiple frames to get to the actual caller
    for _ in range(3):  # Adjust this number if needed
        if frame is None:
            break
        frame = frame.f_back
    
    if frame:
        event_dict["function"] = frame.f_code.co_name
        event_dict["file"] = frame.f_code.co_filename.split("\\")[-1]
        event_dict["line"] = frame.f_lineno
    
    return event_dict

# Create a processor for detail level filtering
class DetailLevelFilter:
    """Filter log events based on their detail level."""
    
    def __init__(self, default_level=1):
        self.default_level = default_level
        self.module_levels = {}
    
    def set_level(self, module=None, level=1):
        """Set the detail level for a specific module or globally."""
        if module:
            self.module_levels[module] = level
        else:
            self.default_level = level
    
    def get_level(self, module=None):
        """Get the detail level for a module or the default level."""
        if module and module in self.module_levels:
            return self.module_levels[module]
        return self.default_level
    
    def __call__(self, logger, method_name, event_dict):
        # Extract and remove our custom level if present
        detail_level = event_dict.pop("_detail_level", 1)
        module = event_dict.get("module", None)
        
        # Get the appropriate level for this module
        current_level = self.get_level(module)
        
        # Filter out messages with higher detail level than configured
        if detail_level > current_level:
            raise structlog.DropEvent
        
        return event_dict

# Create a processor for adding prefixes
def add_prefix(_, __, event_dict):
    """Add prefix to the log message."""
    prefix = event_dict.pop("_prefix", "")
    if prefix and "event" in event_dict:
        event_dict["event"] = f"{prefix}{event_dict['event']}"
    return event_dict

# Create a processor for filtering by prefix
class PrefixFilter:
    """Filter log events by prefix."""
    
    def __init__(self):
        self.allowed_prefixes = None  # None means allow all
    
    def set_allowed_prefixes(self, prefixes=None):
        """Set the allowed prefixes."""
        self.allowed_prefixes = prefixes
    
    def get_allowed_prefixes(self):
        """Get the currently allowed prefixes."""
        return self.allowed_prefixes
    
    def __call__(self, logger, method_name, event_dict):
        # If no allowed prefixes are specified, allow all messages
        if not self.allowed_prefixes:
            return event_dict
        
        # Check if the message has any of the allowed prefixes
        message = event_dict.get("event", "")
        if any(message.startswith(prefix) for prefix in self.allowed_prefixes):
            return event_dict
        
        # Drop messages without an allowed prefix
        raise structlog.DropEvent

# Create a processor for YAML formatting of complex objects
def format_yaml_values(_, __, event_dict):
    """Format complex values as YAML for better readability."""
    for key, value in list(event_dict.items()):
        if not isinstance(value, (str, int, float, bool, type(None))):
            try:
                yaml_str = yaml.dump(value, default_flow_style=False)
                if '\n' in yaml_str:
                    # Format multi-line YAML with proper indentation
                    lines = yaml_str.strip().split('\n')
                    yaml_str = lines[0] + ' |\n  ' + '\n  '.join(lines[1:])
                event_dict[key] = yaml_str
            except Exception:
                # If YAML conversion fails, fall back to str()
                event_dict[key] = str(value)
    return event_dict

# Create a class for the message store
class MessageStore:
    """Store log messages for later retrieval."""
    
    def __init__(self):
        self.messages = []
        self.active = False
    
    def start_capture(self):
        """Start capturing log messages."""
        self.messages = []
        self.active = True
    
    def stop_capture(self):
        """Stop capturing log messages and return them."""
        self.active = False
        return list(self.messages)
    
    def get_messages(self):
        """Get the current messages."""
        return list(self.messages)
    
    def clear(self):
        """Clear the message store."""
        self.messages = []
    
    def __call__(self, logger, method_name, event_dict):
        """Process the log event by storing it if capturing is active."""
        if self.active:
            # Create a simple string representation of the event
            msg = f"{event_dict.get('level', 'INFO').upper()} "
            if "function" in event_dict:
                msg += f"[{event_dict.get('file', '')}:{event_dict.get('function', '')}:{event_dict.get('line', '')}] "
            msg += str(event_dict.get("event", ""))
            
            # Add any additional context
            for key, value in event_dict.items():
                if key not in ("level", "function", "file", "line", "event"):
                    msg += f" {key}={value}"
            
            self.messages.append(msg)
        
        return event_dict

# Create a processor for progress indicators
class ProgressHandler:
    """Handle progress indicators in logs."""
    
    def __init__(self):
        self.progress_empty = True
        self.cached_output_stream = None
    
    def get_output_stream(self):
        """Determine and cache the appropriate output stream for progress."""
        if self.cached_output_stream is not None:
            return self.cached_output_stream
        
        # Default to stderr if no specific handler is found
        self.cached_output_stream = sys.stderr
        return self.cached_output_stream
    
    def progress(self, msg, progress_char):
        """Write a progress character to the output stream."""
        output_stream = self.get_output_stream()
        
        if self.progress_empty:
            # Log the initial message
            # Instead of using the logger directly, print to maintain compatibility
            print(msg, file=output_stream)
            self.progress_empty = False
        
        # Print the progress character
        output_stream.write(progress_char)
        output_stream.flush()
    
    def check_and_reset_progress(self):
        """Check if progress is ongoing, print a newline, and reset."""
        if not self.progress_empty:
            output_stream = self.get_output_stream()
            output_stream.write("\n")
            output_stream.flush()
            self.progress_empty = True
    
    def __call__(self, logger, method_name, event_dict):
        """Process the log event, handling progress indicators if needed."""
        # Check if this is a progress indicator
        if "_progress_char" in event_dict:
            progress_char = event_dict.pop("_progress_char")
            self.progress(event_dict.get("event", ""), progress_char)
            return event_dict
        
        # Regular log message, check and reset progress
        self.check_and_reset_progress()
        return event_dict

# Create global instances
message_store = MessageStore()
detail_filter = DetailLevelFilter()
prefix_filter = PrefixFilter()
progress_handler = ProgressHandler()

# Configure structlog
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
        add_prefix,
        add_caller_info,
        detail_filter,
        prefix_filter,
        progress_handler,
        message_store,
        format_yaml_values,
        structlog.dev.ConsoleRenderer(colors=True)
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

# Create our structured logger class
class StructuredLogger:
    """Enhanced structured logger with detail levels and prefixes."""
    
    def __init__(self, name, prefix=""):
        self.logger = structlog.get_logger(name)
        self.prefix = prefix
        self.detail_level = 1  # Default detail level
    
    def _log(self, method, msg, detail_level=1, **kwargs):
        """Internal method to handle logging with detail level and prefix."""
        kwargs["_detail_level"] = detail_level
        kwargs["_prefix"] = self.prefix
        getattr(self.logger, method)(msg, **kwargs)
    
    def debug(self, msg, **kwargs):
        """Log at debug level with detail level 1."""
        self._log("debug", msg, detail_level=1, **kwargs)
    
    def debug2(self, msg, **kwargs):
        """Log at debug level with detail level 2."""
        self._log("debug", msg, detail_level=2, **kwargs)
    
    def debug3(self, msg, **kwargs):
        """Log at debug level with detail level 3."""
        self._log("debug", msg, detail_level=3, **kwargs)
    
    def info(self, msg, **kwargs):
        """Log at info level."""
        self._log("info", msg, **kwargs)
    
    def warning(self, msg, **kwargs):
        """Log at warning level."""
        self._log("warning", msg, **kwargs)
    
    def error(self, msg, **kwargs):
        """Log at error level."""
        self._log("error", msg, **kwargs)
    
    def critical(self, msg, **kwargs):
        """Log at critical level."""
        self._log("critical", msg, **kwargs)
    
    def exception(self, msg, **kwargs):
        """Log an exception."""
        self._log("exception", msg, **kwargs)
    
    def progress_debug(self, msg, progress_char):
        """Log a debug progress indicator."""
        self._log("debug", msg, _progress_char=progress_char)
    
    def progress_info(self, msg, progress_char):
        """Log an info progress indicator."""
        self._log("info", msg, _progress_char=progress_char)
    
    def progress_warning(self, msg, progress_char):
        """Log a warning progress indicator."""
        self._log("warning", msg, _progress_char=progress_char)
    
    def progress_error(self, msg, progress_char):
        """Log an error progress indicator."""
        self._log("error", msg, _progress_char=progress_char)
    
    def progress_critical(self, msg, progress_char):
        """Log a critical progress indicator."""
        self._log("critical", msg, _progress_char=progress_char)
    
    def set_allowed_prefixes(self, prefixes=None):
        """
        Set allowed prefixes for messages. 
        If prefixes is None, enable all messages.
        If prefixes is a string, convert it to a list.
        If prefixes is an empty string, enable all messages.
        """
        if isinstance(prefixes, str):
            if not prefixes:  # Empty string means allow all
                prefixes = None
            else:
                prefixes = [prefixes]  # Single prefix
        
        prefix_filter.set_allowed_prefixes(prefixes)
    
    def get_allowed_prefixes(self):
        """Return the currently allowed prefixes."""
        return prefix_filter.get_allowed_prefixes()
    
    def set_detail_level(self, level, module=None):
        """Set the detail level for this logger or a specific module."""
        if module:
            detail_filter.set_level(module, level)
        else:
            self.detail_level = level
            detail_filter.set_level(None, level)
    
    def get_detail_level(self, module=None):
        """Get the detail level for this logger or a specific module."""
        if module:
            return detail_filter.get_level(module)
        return self.detail_level

# Module-level functions for message capture
def start_message_capture():
    """Start capturing log messages."""
    message_store.start_capture()

def stop_message_capture():
    """Stop capturing log messages and return them."""
    return message_store.stop_capture()

def get_stored_messages():
    """Get the currently stored messages."""
    return message_store.get_messages()

def clear_stored_messages():
    """Clear the stored messages."""
    message_store.clear()

# Module-level functions for detail level
def set_detail_level(level, module=None):
    """Set the detail level for a module or globally."""
    detail_filter.set_level(module, level)

def get_detail_level(module=None):
    """Get the detail level for a module."""
    return detail_filter.get_level(module)

# Exception class with contextual information
class DetailedException(Exception):
    """Exception with detailed context information."""
    
    def __init__(self, message="An error occurred", frame_info=None):
        self.message = message
        if frame_info:
            self.file_name, self.line_number, self.func_name, _, _ = frame_info
        else:
            frame = inspect.currentframe().f_back
            self.file_name = frame.f_code.co_filename
            self.line_number = frame.f_lineno
            self.func_name = frame.f_code.co_name
        self.module = self.__get_module_name()
        super().__init__(self.message)
    
    @classmethod
    def raise_from_here(cls, message="An error occurred"):
        frame = inspect.currentframe().f_back
        frame_info = inspect.getframeinfo(frame)
        raise cls(message, frame_info)
    
    def __get_module_name(self):
        module = self.file_name
        if module.endswith('.py'):
            module = module[:-3]  # Remove .py extension
        return module.split('\\')[-1]  # Get just the file name without path
    
    def _from(self):
        return self.module, self.func_name, self.file_name, self.line_number
    
    def _from_str(self):
        return f"{self.module}:{self.func_name}(){{{self.file_name}#{self.line_number}}}"
    
    def __str__(self):
        return f"{self.__class__.__name__} from: {self._from_str()}>>\n{self.message}"

class BreakException(Exception):
    """Custom exception to signal a break condition."""
    def __init__(self, message="Break condition occurred"):
        self.message = message
        super().__init__(self.message)

class BreakAndLogException(DetailedException):
    """Exception that includes the current log messages."""
    
    @classmethod
    def raise_from_here(cls, message=None):
        frame = inspect.currentframe().f_back
        frame_info = inspect.getframeinfo(frame)
        log_messages = get_stored_messages()
        full_message = "Break condition occurred, log:\n" + '\n'.join(log_messages) if log_messages else "Break condition occurred"
        if message:
            full_message += f"\nAdditional message: {message}"
        raise cls(full_message, frame_info)

# Create a get_logger function for backward compatibility with the old API
def get_logger(name, prefix="", level=logging.INFO):
    """Get a structured logger with the given name and prefix."""
    logger = StructuredLogger(name, prefix)
    # Set the level if it's different from the default
    if level != logging.INFO:
        logger.logger = logger.logger.bind(level=level)
    return logger
