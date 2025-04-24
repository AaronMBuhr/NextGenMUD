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
    # Get the caller's frame
    frame = inspect.currentframe()
    
    # Go back until we find a frame that's not from the logging infrastructure
    # Skip frames from structlog, logging, and this module
    internal_modules = ['structlog', 'logging', 'structured_logger.py']
    
    while frame:
        frame = frame.f_back
        if not frame:
            break
            
        # Get the module name from the frame
        module_name = frame.f_code.co_filename
        
        # Check if this is not an internal logging module
        is_internal = any(internal in module_name for internal in internal_modules)
        
        if not is_internal:
            # Found the actual caller
            event_dict["function"] = frame.f_code.co_name
            event_dict["file"] = frame.f_code.co_filename.split("\\")[-1]
            event_dict["line"] = frame.f_lineno
            break
    
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
        
        # For debug messages, filter based on hierarchy:
        # debug (1) < debug2 (2) < debug3 (3)
        # If level=debug3, show all debug levels
        # If level=debug2, show debug and debug2 (not debug3)
        # If level=debug, show only debug (not debug2 or debug3)
        if method_name == "debug" and detail_level > 0:
            if detail_level > current_level:
                # Drop more detailed debug messages than current level
                raise structlog.DropEvent
                
        # For non-debug messages, allow them regardless of the detail level
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

def chunk_by_length(s: str, length: int) -> list[str]:
    return [s[i:i+length] for i in range(0, len(s), length)]

# Create a processor for text wrapping
def wrap_text(_, __, event_dict):
    """Wrap text in log messages at a specified column width."""
    # Get the wrap settings from the event dict or use defaults
    wrap_width = event_dict.pop("_wrap_width", None)
    
    # If no wrap width specified or invalid, return unchanged
    if wrap_width is None or wrap_width <= 0:
        return event_dict
    
    # Get the message
    msg = str(event_dict.get("event", ""))
    
    # Calculate timestamp and level lengths to account for in first line
    timestamp_len = 17  # "04-24 17:22:45 "
    level_len = 6      # "[WRN] "
    first_line_offset = timestamp_len + level_len
    
    # Adjust wrap_width to account for indentation
    # For subsequent lines, we need to account for the indentation that will be applied
    # by the renderer (which is typically the same as the first_line_offset)
    content_wrap_width = wrap_width - first_line_offset
    
    # Build a combined message with all metadata
    metadata_parts = []
    for key, value in list(event_dict.items()):
        if key not in ("event", "timestamp", "level", "logger", "logger_name"):
            metadata_parts.append(f"{key}={value}")
            # Remove the key to prevent it from being rendered separately later
            event_dict.pop(key)
    
    # Combine main message with metadata
    if metadata_parts:
        full_msg = f"{msg} {' '.join(metadata_parts)}"
    else:
        full_msg = msg
    
    # Process each line independently (in case message already has newlines)
    result_lines = []
    
    for line in full_msg.split('\n'):
        # For all lines, we use the content_wrap_width since the offset 
        # is already accounted for in that calculation
        is_first_line = (not result_lines)
        
        # Process this line
        current_pos = 0
        
        while current_pos < len(line):
            # If remaining text fits in available width
            if current_pos + content_wrap_width >= len(line):
                result_lines.append(line[current_pos:])
                break
            
            # Find a good breaking point
            break_pos = current_pos + content_wrap_width
            
            # Look for last space before width limit
            while break_pos > current_pos and not line[break_pos-1].isspace():
                break_pos -= 1
                
            # If no space found, force break at width
            if break_pos <= current_pos:
                break_pos = current_pos + content_wrap_width
            
            # Add this segment
            result_lines.append(line[current_pos:break_pos].rstrip())
            
            # Move past the space
            current_pos = break_pos
            while current_pos < len(line) and line[current_pos].isspace():
                current_pos += 1
    
    # Join the lines with newlines and set as the event
    event_dict["event"] = '\n'.join(result_lines)
    return event_dict

# Create global instances
message_store = MessageStore()
detail_filter = DetailLevelFilter()
prefix_filter = PrefixFilter()
progress_handler = ProgressHandler()

# Global log width setting (None means no wrapping)
global_log_width = None

def set_global_log_width(width: int):
    """Set the global log width for all loggers."""
    global global_log_width
    global_log_width = width

# Create a global flag to track if the year has been logged
year_has_been_logged = False

class CustomConsoleRenderer:
    """Custom console renderer that handles each line separately and respects our wrapping."""
    
    def __init__(self, colors=True):
        self.colors = colors
        # Color mappings similar to structlog's ConsoleRenderer
        self.level_to_color = {
            'critical': '\x1b[31;1m',  # bright red
            'exception': '\x1b[31;1m',  # bright red
            'error': '\x1b[31m',      # red
            'warning': '\x1b[33m',    # yellow
            'info': '\x1b[32m',       # green
            'debug': '\x1b[34m',      # blue
            'notset': '\x1b[37m',     # white
        }
        self.reset_color = '\x1b[0m'
        
        # Abbreviation mapping for log levels
        self.level_abbrevs = {
            'debug': 'DBG',
            'debug2': 'DB2',
            'debug3': 'DB3',
            'info': 'INF',
            'warning': 'WRN',
            'error': 'ERR',
            'critical': 'CRT',
            'exception': 'EXC',
            'fatal': 'FTL',
            'verbose': 'VRB',
        }
        
        # Year tracking for log session
        self.current_year = None
        
        # List of keys to filter from being shown in extra fields
        self.filtered_keys = set(['logger', 'logger_name'])

    def __call__(self, logger, method_name, event_dict):
        """Render the event dictionary into colored output."""
        global year_has_been_logged
        # print("test")
        # print(event_dict)
        
        # Extract standard fields
        timestamp = event_dict.pop('timestamp', '')
        level = event_dict.pop('level', 'info')
        event = event_dict.pop('event', '')
        
        # Explicitly remove logger-related keys we don't want to display
        event_dict.pop('logger', None)
        event_dict.pop('logger_name', None)
        
        # Handle year logging
        if timestamp and not year_has_been_logged:
            try:
                # Extract year from timestamp (format: "2025-04-24 08:13:03")
                year = timestamp[:4]
                self.current_year = year
                # We'll handle logging the year separately
            except (IndexError, ValueError):
                pass  # Use original timestamp if parsing fails
        
        # Remove year from timestamp regardless of whether we've logged it
        if timestamp and len(timestamp) > 10:  # Only if it has enough characters
            timestamp = timestamp[5:]  # "04-24 08:13:03"

        # Get level abbreviation
        level_abbrev = self.level_abbrevs.get(level, level[:3].upper())
        
        # Format the level field with consistent width and abbreviation
        level_str = f"[{level_abbrev}]"

        # Apply colors if enabled
        if self.colors:
            color = self.level_to_color.get(level, self.reset_color)
            level_str = f"{color}{level_str}{self.reset_color}"

        # Build the prefix (timestamp and level)
        prefix = f"{timestamp} {level_str} "

        # Split the event into lines and handle each separately
        lines = str(event).split('\n')
        final_lines = []

        # Handle the first line
        if lines:
            final_lines.append(f"{prefix}{lines[0]}")
            # For subsequent lines, align with the content start
            content_start = len(timestamp) + len(" [") + 3 + len("] ")  # Calculate alignment
            space_prefix = " " * content_start
            final_lines.extend(f"{space_prefix}{line}" for line in lines[1:])

        # Filter out repetitive keys and add remaining event_dict items as extra fields
        if event_dict:
            # Filter out keys we don't want to show
            filtered_dict = {k: v for k, v in sorted(event_dict.items()) 
                            if k not in self.filtered_keys}
            
            if filtered_dict:
                extra = " ".join(f"{key}={value}" for key, value in sorted(filtered_dict.items()))
                if extra:
                    final_lines.append(f"{space_prefix}{extra}")
                
        return "\n".join(final_lines)

# Create a global renderer instance to track year state
global_renderer = CustomConsoleRenderer(colors=True)

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
        wrap_text,
        global_renderer  # Use our global renderer instance
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

# Add initialization function to log the year
def initialize_logger():
    """Initialize the logger and log the current year."""
    logger = get_logger("logger_init")
    logger.info(f"Log year is {global_renderer.current_year}")

# Create our structured logger class
class StructuredLogger:
    """Enhanced structured logger with detail levels and prefixes."""
    
    def __init__(self, name, prefix=""):
        self.logger = structlog.get_logger(name)
        self.prefix = prefix
        self.detail_level = 1  # Default detail level
        self.wrap_width = global_log_width  # Use global log width (None means no wrapping)
    
    def _log(self, method, msg, detail_level=1, **kwargs):
        """Internal method to handle logging with detail level and prefix."""
        global year_has_been_logged
        
        # Check if we need to log the year first - do this only once globally
        if not year_has_been_logged and global_renderer.current_year:
            # Log the year info first
            year_logger = structlog.get_logger("logger_init")
            year_logger.info(f"Log year is {global_renderer.current_year}")
            # Set the global flag to indicate year has been logged
            year_has_been_logged = True
            
            # If this log message isn't already about the year, proceed with original log
            if not msg.startswith("Log year is"):
                kwargs["_detail_level"] = detail_level
                kwargs["_prefix"] = self.prefix
                kwargs["_wrap_width"] = self.wrap_width
                getattr(self.logger, method)(msg, **kwargs)
                return
        
        # Normal logging path for all other cases
        kwargs["_detail_level"] = detail_level
        kwargs["_prefix"] = self.prefix
        kwargs["_wrap_width"] = self.wrap_width
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
    
    def set_wrap_settings(self, width=80):
        """Set the text wrapping settings for this logger."""
        self.wrap_width = width

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
