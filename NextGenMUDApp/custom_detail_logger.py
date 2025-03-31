import  inspect
import  io
import  logging
import  sys
import  traceback
from    typing import List, Optional


class YamlMultilineFormatter(logging.Formatter):
    def __init__(self, fmt=None, datefmt=None):
        super().__init__(fmt, datefmt)

    def format(self, record):
        original_message = record.msg
        if '\n' in original_message:
            first_line, remaining_lines = original_message.split('\n', 1)
            record.msg = f"{first_line} |\n  " + '\n  '.join(remaining_lines.split('\n'))
        return super().format(record)


class BreakException(Exception):
    """Custom exception to signal a break condition."""
    def __init__(self, message="Break condition occurred"):
        self.message = message
        super().__init__(self.message)


class DetailedException(Exception):
    def __init__(self, message="An error occurred", frame_info=None):
        self.message = message
        if frame_info:
            self.file_name, self.line_number, self.func_name, _, _ = frame_info
        else:
            frame = inspect.currentframe().f_back.f_back
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
        return module.split('/')[-1]  # Get just the file name without path

    def _from(self):
        return self.module, self.func_name, self.file_name, self.line_number
    
    def _from_str(self):
        return f"{self.module}:{self.func_name}(){{{self.file_name}#{self.line_number}}}"
    
    def __str__(self):
        return (f"{self.__class__.__name__} from: {self._from_str()}>>\n{self.message}")

# Example usage
class MessageStoreHandler(logging.Handler):
    def emit(self, record):
        if CustomDetailLogger.message_store is not None:
            formatted_message = self.format(record)
            CustomDetailLogger.message_store.append(formatted_message)


class CustomDetailLogger(logging.Logger):
    _progress_empty: bool = True
    _cached_output_stream: Optional[io.TextIOBase] = None  # Cache for output stream
    _default_format: str = '%(asctime)s | %(name)s | %(levelname)s | %(message)s'
    message_store = None

    def __init__(self, name, prefix="", level=logging.NOTSET):
        super().__init__(name, level)
        self.prefix = prefix
        self.detail_level = 0

        # Create a new handler with the specific formatter
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(self._default_format))
        self.addHandler(handler)

        self.setLevel(level)

    @classmethod
    def change_default_logger(cls, new_logger_class=None, new_format=None):
        """
        Change the global logger class and optionally set a new format.
        Returns a tuple: (previous_logger_class, previous_format).

        Arguments:
            new_logger_class (type): The new logger class to set. Defaults to `cls`.
            new_format (str): The new logging format to set. If None, format is unchanged.
        """
        # Get the current logger class
        previous_logger_class = logging.getLoggerClass()

        # Get the current logging format if any handlers exist
        root_logger = logging.getLogger()
        previous_format = None
        if root_logger.handlers:
            # Assuming the first handler's formatter represents the current format
            previous_format = root_logger.handlers[0].formatter._fmt

        # Update the logger class if a new one is provided
        logging.setLoggerClass(new_logger_class or cls)

        # Update the logging format if a new one is provided
        if new_format is not None:
            logging.basicConfig(format=new_format)

        return previous_logger_class, previous_format
    
    @classmethod
    def start_message_capture(cls):
        """Start capturing log messages."""
        cls.message_store = []

    @classmethod
    def get_stored_messages(cls):
        """Get the currently stored messages."""
        return cls.message_store
    
    @classmethod
    def clear_stored_messages(cls):
        """Clear the stored messages."""
        if cls.message_store is not None:
            cls.message_store.clear()
    
    @classmethod
    def stop_message_capture(cls):
        """Stop capturing log messages and return the captured messages."""
        messages = cls.message_store
        cls.message_store = None
        return messages

    def inspect_handlers(self):
        """Inspect handlers and determine their output streams."""
        output_destinations = []
        for handler in self.handlers:
            if isinstance(handler, logging.StreamHandler):
                stream = handler.stream
                if stream == sys.stdout:
                    output_destinations.append('stdout')
                elif stream == sys.stderr:
                    output_destinations.append('stderr')
                else:
                    output_destinations.append(str(stream))
            elif isinstance(handler, logging.FileHandler):
                output_destinations.append(f"File: {handler.baseFilename}")
            else:
                output_destinations.append(f"Unknown: {type(handler).__name__}")
        return output_destinations

    def get_output_stream(self):
        """Determine and cache the appropriate output stream for progress."""
        if CustomDetailLogger._cached_output_stream is not None:
            return CustomDetailLogger._cached_output_stream

        # Default to stderr if no specific handler is found
        output_stream = sys.stderr

        for handler in self.handlers:
            if isinstance(handler, logging.StreamHandler):
                # Prefer stdout over stderr
                if handler.stream == sys.stdout:
                    output_stream = sys.stdout
                    break
                elif handler.stream == sys.stderr:
                    output_stream = sys.stderr

        # Cache the result
        CustomDetailLogger._cached_output_stream = output_stream
        return output_stream

    def _progress(self, log_msg: str, progress_char: str, level: int):
        """Shared logic for progress methods."""
        if self.getEffectiveLevel() > level:
            return  # Only proceed if the log level is enabled

        output_stream = self.get_output_stream()

        if CustomDetailLogger._progress_empty:
            # Log the message at the specified level
            self.log(level, log_msg)
            CustomDetailLogger._progress_empty = False  # Mark progress as started

        # Print the progress character
        output_stream.write(progress_char)
        output_stream.flush()

    def progress_debug(self, log_msg: str, progress_char: str):
        """Logs a progress character for DEBUG level."""
        self._progress(log_msg, progress_char, logging.DEBUG)

    def progress_info(self, log_msg: str, progress_char: str):
        """Logs a progress character for INFO level."""
        self._progress(log_msg, progress_char, logging.INFO)

    def progress_warning(self, log_msg: str, progress_char: str):
        """Logs a progress character for WARNING level."""
        self._progress(log_msg, progress_char, logging.WARNING)

    def progress_error(self, log_msg: str, progress_char: str):
        """Logs a progress character for ERROR level."""
        self._progress(log_msg, progress_char, logging.ERROR)

    def progress_critical(self, log_msg: str, progress_char: str):
        """Logs a progress character for CRITICAL level."""
        self._progress(log_msg, progress_char, logging.CRITICAL)

    def _check_and_reset_progress(self):
        """Check if progress is ongoing, print a newline, and reset."""
        if not CustomDetailLogger._progress_empty:
            output_stream = self.get_output_stream()
            output_stream.write("\n")
            output_stream.flush()
            CustomDetailLogger._progress_empty = True

    # Override log methods to handle progress resetting
    def debug(self, msg, *args, **kwargs):
        self._check_and_reset_progress()
        super().debug(self.prefix + str(msg), *args, **kwargs)

    def debug2(self, msg, *args, **kwargs):
        if self.detail_level >= 2:
            self.debug(msg, *args, **kwargs)

    def debug3(self, msg, *args, **kwargs):
        if self.detail_level >= 3:
            self.debug(msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        self._check_and_reset_progress()
        super().info(self.prefix + str(msg), *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self._check_and_reset_progress()
        super().warning(self.prefix + str(msg), *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self._check_and_reset_progress()
        super().error(self.prefix + str(msg), *args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        self._check_and_reset_progress()
        super().critical(self.prefix + str(msg), *args, **kwargs)

    def set_allowed_prefixes(self, prefixes=None):
        """
        Set allowed prefixes for messages. 
        If prefixes is None, enable all messages.
        If prefixes is a string, convert it to a list.
        If prefixes is an empty string, enable all messages.
        """
        # Convert handlers to FilterHandlers
        if isinstance(prefixes, str):
            if not prefixes:  # Empty string means allow all
                prefixes = None
            else:
                prefixes = [prefixes]  # Single prefix
        
        for handler in list(self.handlers):
            # Only process StreamHandlers (which includes FileHandlers)
            if isinstance(handler, logging.StreamHandler):
                # Remove any existing filters
                handler.filters = [f for f in handler.filters if not isinstance(f, PrefixFilter)]
                
                # Add a new filter if prefixes are specified
                if prefixes is not None:
                    handler.addFilter(PrefixFilter(prefixes))
                    
    def get_allowed_prefixes(self):
        """
        Return the currently allowed prefixes.
        Returns an empty list if all prefixes are allowed.
        """
        for handler in self.handlers:
            for f in handler.filters:
                if isinstance(f, PrefixFilter):
                    return f.allowed_prefixes
        return []  # No filter found, meaning all prefixes are allowed

class PrefixFilter(logging.Filter):
    """Filter that only allows log messages with specific prefixes."""
    
    def __init__(self, allowed_prefixes):
        super().__init__()
        self.allowed_prefixes = allowed_prefixes
        
    def filter(self, record):
        # If no allowed prefixes are specified, allow all messages
        if not self.allowed_prefixes:
            return True
            
        # Check if the message has any of the allowed prefixes
        message = record.getMessage()
        return any(message.startswith(prefix) for prefix in self.allowed_prefixes)


class BreakAndLogException(DetailedException):
    """Custom exception to signal a break condition and provide the current log as the message"""
    @classmethod
    def raise_from_here(cls, message: str = None):
        frame = inspect.currentframe().f_back
        frame_info = inspect.getframeinfo(frame)
        log_messages = CustomDetailLogger.get_stored_messages()
        full_message = "Break condition occurred, log:\n" + '\n'.join(log_messages) if log_messages else "Break condition occurred"
        if message:
            full_message += f"\nAdditional message: {message}"
        raise cls(full_message, frame_info)

# Make CustomDetailLogger the default logger class
logging.setLoggerClass(CustomDetailLogger)
