# NextGenMUD

NextGenMUD is a modern Multi-User Dungeon (MUD) engine built with Django and WebSockets, combining classic text-based adventure gameplay with modern web technologies.

## Overview

NextGenMUD provides a flexible foundation for creating and running text-based multiplayer worlds. Featuring a rich YAML-based world definition system, dynamic trigger system, and comprehensive game state management, it allows for the creation of complex, interactive environments.

Key features include:
- Real-time player interactions via WebSockets
- Comprehensive command system with extensive built-in commands
- Event-driven trigger system for rich, dynamic environments
- YAML-based world definitions for easy world building
- Flexible character, object, and room models
- Combat system with support for NPCs and player battles
- Inventory and equipment systems

## Architecture

NextGenMUD is built on the following architecture:

- **Django Framework**: Provides the web foundation, user management, and admin interface
- **WebSockets**: Handles real-time communication between players and the game server
- **Comprehensive Game State**: Central manager for all game elements and interactions
- **Command Handler**: Processes player inputs and manages command execution
- **World Definition**: YAML-based system for defining game worlds, characters, and objects
- **Trigger System**: Event-driven system for creating interactive environments
- **Structured Logging**: Advanced logging system with context tracking and multiple debug levels

## Getting Started

### Prerequisites

- Python 3.8+
- Django 5.0+
- Channels 4.0+ (for WebSockets)
- Structlog 23.2.0+ (for structured logging)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/NextGenMUD.git
cd NextGenMUD
```

2. Set up a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows, use venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run migrations:
```bash
python manage.py migrate
```

5. Start the server:
```bash
./run.sh
```

Or manually:
```bash
uvicorn NextGenMUD.asgi:application --host 0.0.0.0 --port 8000
```

### Creating a World

NextGenMUD uses YAML files for world definitions. Example world files are provided in the `world_data` directory. 

A basic world file structure:

```yaml
name: Example Zone
description: A sample zone for demonstration purposes.
rooms:
  starting_room:
    name: Starting Point
    description: The beginning of your adventure.
    exits:
      north:
        destination: second_room
    triggers:
      - type: timer_tick
        criteria: 
          - subject: "%time_elapsed%"
            operator: "numgte"
            predicate: 10
        script: |
          echo A gentle breeze passes through the room.
```

## Command System

NextGenMUD provides a wide range of built-in commands for players to interact with the world:

### Basic Movement
- `north`, `south`, `east`, `west` - Navigate between rooms

### Communication
- `say [text]` - Speak to everyone in the room
- `sayto [character] [text]` - Speak to a specific character
- `tell [character] [text]` - Send a private message
- `emote [text]` - Perform an action

### Character Actions
- `look` - View your surroundings
- `look [target]` - Examine something or someone
- `inventory` or `inv` - View your carried items
- `get [item]` - Pick up an item
- `drop [item]` - Drop an item
- `equip [item]` - Equip an item
- `unequip [item]` - Unequip an item

### Combat
- `attack [character]` or `kill [character]` - Initiate combat

### Admin Commands
- `spawn char/obj [id]` - Create a character or object
- `goto char/room [target]` - Teleport to a character or room
- `at char/room [target] [command]` - Execute a command as if at another location
- `echo [text]` - Display a message to the room
- `show zones/zone/characters/objects` - Display game information

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Structured Logging System

NextGenMUD includes a powerful structured logging system based on the `structlog` library. This system provides:

- **Structured data** - Include key-value pairs in log messages for better filtering and analysis
- **Multiple debug levels** - Use debug(), debug2(), and debug3() for fine-grained control
- **Source context** - Automatic inclusion of source file, function name, and line number
- **Progress indicators** - Visual indicators for long-running operations
- **Message capturing** - Ability to capture and replay log messages
- **Prefix filtering** - Filter log messages based on prefixes
- **Exception handling** - Detailed exceptions with source information

For more information, see the [logger_readme.md](NextGenMUDApp/logger_readme.md) file.

## Acknowledgments

- Inspired by classic MUDs like DikuMUD, LPMud, and CircleMUD
- Built with Django and modern Python best practices
- Made with love for the text-based adventure community