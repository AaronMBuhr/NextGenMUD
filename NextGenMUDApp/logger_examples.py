"""
Examples of how to use the new structured logger system.
This file demonstrates the various features of the structured logger,
including multiple debug levels, context binding, progress indicators,
message capturing, and exception handling.
"""

from NextGenMUDApp.structured_logger import (
    get_logger, 
    start_message_capture, 
    stop_message_capture,
    DetailedException,
    BreakAndLogException
)

def basic_logging_example():
    """Demonstrate basic logging functionality."""
    print("\n=== Basic Logging Example ===")
    
    # Create a logger with a prefix
    logger = get_logger("example", prefix="EXAMPLE: ")
    
    # Log at different levels
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    logger.critical("This is a critical message")
    
    # Add structured data to log messages
    logger.info("User action", action="login", user_id=123, status="success")

def multiple_debug_levels_example():
    """Demonstrate multiple debug levels."""
    print("\n=== Multiple Debug Levels Example ===")
    
    logger = get_logger("debug_levels", prefix="DEBUG-LEVELS: ")
    
    # Set the global detail level
    logger.set_detail_level(3)  # Show all debug levels
    
    # Log at different debug levels
    logger.debug("Debug level 1 message")
    logger.debug2("Debug level 2 message")
    logger.debug3("Debug level 3 message")
    
    # Change the detail level
    print("\nChanging detail level to 2:")
    logger.set_detail_level(2)
    
    # Log again
    logger.debug("Debug level 1 message")
    logger.debug2("Debug level 2 message")
    logger.debug3("Debug level 3 message (this should not appear)")
    
    # Set a module-specific detail level
    print("\nSetting module-specific detail level:")
    logger.set_detail_level(1, module="other_module")
    logger = get_logger("other_module", prefix="OTHER-MODULE: ")
    
    # Log from the other module
    logger.debug("Debug level 1 message")
    logger.debug2("Debug level 2 message (this should not appear)")

def progress_indicator_example():
    """Demonstrate progress indicators."""
    print("\n=== Progress Indicator Example ===")
    
    logger = get_logger("progress", prefix="PROGRESS: ")
    
    # Log with progress indicators
    logger.progress_info("Starting a long operation", ".")
    for i in range(20):
        # Simulate work
        import time
        time.sleep(0.1)
        logger.progress_info("", ".")
    
    # Regular log message will automatically add a newline
    logger.info("Operation completed")

def message_capture_example():
    """Demonstrate message capturing."""
    print("\n=== Message Capture Example ===")
    
    logger = get_logger("capture", prefix="CAPTURE: ")
    
    # Start message capture
    start_message_capture()
    
    # Log some messages
    logger.info("First captured message")
    logger.warning("Second captured message")
    logger.error("Third captured message")
    
    # Stop message capture and get the messages
    messages = stop_message_capture()
    
    # Display the captured messages
    print("Captured messages:")
    for msg in messages:
        print(f"  - {msg}")

def exception_handling_example():
    """Demonstrate exception handling."""
    print("\n=== Exception Handling Example ===")
    
    logger = get_logger("exceptions", prefix="EXCEPTION: ")
    
    # Log regular messages
    logger.info("About to try something risky")
    
    try:
        # Start message capture
        start_message_capture()
        
        # Log before the error
        logger.debug("First step completed")
        logger.debug("Second step started")
        
        # Simulate an error
        raise ValueError("Something went wrong!")
    except Exception as e:
        # Log the exception with context
        logger.error(f"Caught an error: {str(e)}")
        
        # Show captured messages
        messages = stop_message_capture()
        print("Messages captured before the error:")
        for msg in messages:
            print(f"  - {msg}")
        
        # Demonstrate raising a DetailedException
        try:
            DetailedException.raise_from_here("This is a detailed exception")
        except DetailedException as de:
            print(f"\nDetailed exception caught: {de}")

def prefix_filtering_example():
    """Demonstrate prefix filtering."""
    print("\n=== Prefix Filtering Example ===")
    
    # Create loggers with different prefixes
    logger1 = get_logger("filter1", prefix="SYSTEM: ")
    logger2 = get_logger("filter2", prefix="DATABASE: ")
    logger3 = get_logger("filter3", prefix="NETWORK: ")
    
    # Log messages from all loggers
    print("All messages:")
    logger1.info("System initialized")
    logger2.info("Database connected")
    logger3.info("Network ready")
    
    # Set allowed prefixes to only show SYSTEM messages
    print("\nFiltering to only show SYSTEM messages:")
    logger1.set_allowed_prefixes("SYSTEM: ")
    
    # Log messages again
    logger1.info("System message (should appear)")
    logger2.info("Database message (should be filtered out)")
    logger3.info("Network message (should be filtered out)")
    
    # Reset to show all messages
    print("\nResetting to show all messages:")
    logger1.set_allowed_prefixes(None)
    
    # Log messages one more time
    logger1.info("System message")
    logger2.info("Database message")
    logger3.info("Network message")

def yaml_formatting_example():
    """Demonstrate YAML formatting of complex objects."""
    print("\n=== YAML Formatting Example ===")
    
    logger = get_logger("yaml", prefix="YAML: ")
    
    # Create a complex object
    complex_object = {
        "name": "Test Object",
        "attributes": {
            "strength": 10,
            "dexterity": 15,
            "intelligence": 12
        },
        "inventory": [
            {"name": "Sword", "damage": 5},
            {"name": "Shield", "defense": 3},
            {"name": "Potion", "effect": "Healing"}
        ]
    }
    
    # Log the complex object
    logger.info("Complex object", data=complex_object)

def run_all_examples():
    """Run all logger examples."""
    basic_logging_example()
    multiple_debug_levels_example()
    progress_indicator_example()
    message_capture_example()
    exception_handling_example()
    prefix_filtering_example()
    yaml_formatting_example()
    
    print("\n=== All Examples Completed ===")

if __name__ == "__main__":
    run_all_examples()
