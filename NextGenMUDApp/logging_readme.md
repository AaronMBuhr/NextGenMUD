# NextGenMUD Logging System

## Overview

NextGenMUD uses a structured logging system based on the `structlog` library. This system provides hierarchical debug levels, contextual information, and flexible filtering options.

## Log Levels

The logging system uses the following levels, in order from most detailed to most severe:

### `DEBUG3`
Most detailed level, showing fine-grained logging within methods. For development use only.
- Includes details of internal method execution
- Shows variable states, decision points, and algorithm steps
- Not intended for customer-facing environments

### `DEBUG2`
Detailed logging within particular operations, showing intermediate steps.
- Can be enabled in customer environments at developer direction
- Useful for diagnosing specific subsystem issues
- Shows detailed operation progress and state transitions

### `DEBUG`
Standard debug level focusing on what operations are being performed and with what parameters.
- Shows method entry/exit and major function calls
- Logs operation parameters and return values
- Provides a high-level view of program execution flow

### `INFO`
General operational and status messages indicating normal operation.
- System startup/shutdown
- Configuration loading
- Connection establishment/termination
- Scheduled tasks execution
- Normal state changes

### `WARN`
Information that should be brought to the attention of an administrator eventually.
- Issues that are not yet problems but may become one
- Operations not proceeding as presumably desired but not failing
- Resource usage approaching limits
- Deprecated feature usage
- Unexpected but handled conditions

### `ERR` (ERROR)
A recoverable error that should never happen under normal conditions.
- May abort the current operation but will not affect ongoing operation of the program
- Of certain interest to administrators
- Will likely require attention, but not necessarily urgent
- Examples: failed connections, timeouts, invalid input

### `CRT` (CRITICAL)
A non-recoverable error requiring administrative intervention.
- Something that should never happen has occurred
- Of immediate interest to an administrator
- Manual intervention likely required to correct
- Program will continue in a degraded state up to and including halting operations
- Can be manually corrected without restarting the entire system

### `FTL` (FATAL)
Catastrophic failure requiring immediate program termination.
- Program cannot continue and must exit immediately
- Data corruption is possible
- Immediate administrator notification required
- May require system restore or data recovery procedures

## Setting Log Levels

### Command Line

Set the log level when running the application:

```
run.bat --log-level debug3    # Most verbose, shows all messages
run.bat --log-level debug2    # Shows debug2, debug, and all higher levels
run.bat --log-level debug     # Shows debug and all higher levels
run.bat --log-level info      # Default - shows info and higher
```

### In-Game Commands

Log level can be changed at runtime using in-game commands:

```
setloglevel debug3
setloglevel debug2
setloglevel debug
setloglevel info
```

### Programmatically

```python
from NextGenMUDApp.structured_logger import set_detail_level

# Set global log level
set_detail_level(3)  # debug3 - most verbose
set_detail_level(2)  # debug2
set_detail_level(1)  # debug

# Set log level for a specific module
set_detail_level(3, module="combat_system")
```

## Usage Examples

```python
from NextGenMUDApp.structured_logger import StructuredLogger

# Create a logger with a prefix
logger = StructuredLogger(__name__, prefix="CombatSystem> ")

# Different log levels
logger.debug3(f"Detailed calculation: damage_roll={roll}, modifier={mod}, total={total}")
logger.debug2(f"Processing attack from {attacker} to {defender}")
logger.debug(f"Combat round {round} started with {num_participants} participants")
logger.info(f"Combat between {player} and {monster} started")
logger.warning(f"Player {player} attempting to attack in non-combat zone")
logger.error(f"Failed to calculate damage: {e}")
logger.critical(f"Combat system stuck in infinite loop, forcing termination")
# Fatal errors typically lead to program termination
logger.critical(f"FATAL: Database corruption detected in combat logs")
```

## Filtering by Prefix

You can filter logs by prefix to focus on specific components:

```
setlogfilter CombatSystem>
setlogfilter RoomSystem>
setlogfilter CharacterSystem>
setlogfilter all    # Show all logs
``` 