# Structured Logging System for NextGenMUD

This document explains the new structured logging system implemented in NextGenMUD, which is based on the `structlog` library. This system replaces the previous custom logging implementation while maintaining backward compatibility.

## Overview

The new logging system provides several advantages:

1. **Structured logging** - Log messages can include structured data (key-value pairs) for better filtering and analysis
2. **Multiple debug levels** - Support for debug, debug2, and debug3 levels for fine-grained control
3. **Contextual information** - Automatic inclusion of source file, function name, and line number
4. **Progress indicators** - Visual indicators for long-running operations
5. **Message capturing** - Ability to capture and replay log messages
6. **Prefix support and filtering** - Filter log messages based on prefixes
7. **Exception handling with context** - Detailed exceptions with source information
8. **YAML formatting** - Pretty formatting of complex objects in log messages

## Logging Levels

The system supports the following logging levels in order of increasing severity:

1. **debug** - Top-level debugging progress and state messages. Customer-facing when enabled by a developer request.
2. **debug2** - More detailed progress and state messages. Also potentially customer-facing when enabled by a developer request.
3. **debug3** - Fine-grained debugging of specific processes. For developer eyes only, not intended for customers.
4. **info** - General operational information (successful initialization, connections established, etc.)
5. **warning** - Potential issues that aren't errors but might need attention
6. **error** - Something that should never happen and may cause the current operation to fail, but won't affect the ongoing operation of the program.
7. **critical** - Critical errors that may affect or halt ongoing operations and require immediate administrator attention. Potentially recoverable with human intervention.
8. **fatal** - Catastrophic errors so severe that the program must immediately exit.

## Special Logging Settings

1. **none** - No logs whatsoever, complete silence.
2. **always** - Messages that should be logged regardless of the current logging level setting (except when set to "none").
3. **force** - The highest priority; these messages will be logged even when the logging level is set to "none".

## Migration Guide

### Basic Usage

```python
# Old way
from NextGenMUDApp.custom_detail_logger import CustomDetailLogger
logger = CustomDetailLogger("my_module", prefix="MODULE: ")
logger.debug("Debug message")

# New way (compatible with old way)
from NextGenMUDApp.structured_logger import get_logger
logger = get_logger("my_module", prefix="MODULE: ")
logger.debug("Debug message")
```

### Structured Data

The new system allows adding structured data to log messages:

```python
# Structured logging with additional context
logger.info("User logged in", user_id=123, ip_address="192.168.1.1")
```

### Multiple Debug Levels

```python
# Set the detail level (1-3)
logger.set_detail_level(2)

# Log at different debug levels
logger.debug("Always visible at level 1+")
logger.debug2("Only visible at level 2+")
logger.debug3("Only visible at level 3")
```

### Progress Indicators

```python
# Start a progress indicator
logger.progress_info("Processing items", ".")

# Update the progress
for item in items:
    process(item)
    logger.progress_info("", ".")

# End the progress indicator (any log message will add a newline)
logger.info("Processing completed")
```

### Message Capturing

```python
# Start capturing messages
from NextGenMUDApp.structured_logger import start_message_capture, stop_message_capture

start_message_capture()

# Log some messages
logger.debug("Message 1")
logger.info("Message 2")

# Stop and get the captured messages
messages = stop_message_capture()
```

### Prefix Filtering

```python
# Set allowed prefixes
logger.set_allowed_prefixes(["SYSTEM: ", "NETWORK: "])

# Only messages with these prefixes will be shown
logger.info("This will be shown if it has the right prefix")
```

### Exception Handling

```python
# Custom exceptions with source information
from NextGenMUDApp.structured_logger import DetailedException

try:
    # Some code that might fail
    ...
except Exception as e:
    # Either re-raise as a DetailedException
    DetailedException.raise_from_here(f"Failed: {str(e)}")
    
    # Or log the exception
    logger.exception("An error occurred", exc_info=e)
```

### YAML Formatting

Complex objects are automatically formatted as YAML for better readability:

```python
complex_data = {
    "users": [
        {"id": 1, "name": "Alice"},
        {"id": 2, "name": "Bob"}
    ],
    "stats": {
        "active": 42,
        "inactive": 15
    }
}

# The complex data will be automatically formatted as YAML
logger.info("User statistics", data=complex_data)
```

## Examples

For more examples, see the `logger_examples.py` file, which demonstrates all features of the new logging system.

## Backward Compatibility

The new system maintains backward compatibility with the old custom logging system. The `custom_detail_logger.py` module now re-exports all functionality from the new `structured_logger.py` module, so existing imports will continue to work.

Similarly, the `yaml_dumper.py` module is preserved for backward compatibility, although its functionality is now integrated into the structured logger.

## Requirements

- `structlog==23.2.0`
- `pyyaml==6.0`
