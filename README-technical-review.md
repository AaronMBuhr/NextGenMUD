# NextGenMUD -- Technical Review

## Project Summary

NextGenMUD is a modern Multi-User Dungeon engine built on Django Channels and WebSockets. It replaces the traditional telnet-based MUD architecture with a browser-accessible, async-first design while preserving the deep gameplay systems (scripting, triggers, combat, quests) characteristic of classic MUDs like DikuMUD and CircleMUD.

| Metric | Value |
|---|---|
| Language | Python 3.8+ |
| Framework | Django 5.0.1 + Channels 4.0.0 |
| Server | Uvicorn 0.27.1 (ASGI) |
| Protocol | WebSocket (`/nextgenmud/ws/`) |
| Codebase | ~86 Python files, ~32,000 lines |
| World Data | 8 YAML zone files |
| Test Suite | 17 pytest modules |
| License | MIT |

---

## Architecture Overview

```
                    +-----------+
                    |  Browser  |
                    +-----+-----+
                          | WebSocket
                          v
                   +------+------+
                   |   Uvicorn   |
                   |   (ASGI)    |
                   +------+------+
                          |
            +-------------+-------------+
            |                           |
   +--------v--------+        +--------v--------+
   | Django Channels  |        |   Django HTTP   |
   | (WebSocket)      |        |   (Admin/Static)|
   +--------+---------+        +-----------------+
            |
   +--------v---------+
   | MyWebsocketConsumer|  <-- per-connection login state machine
   +--------+----------+
            |
   +--------v----------+
   |    Connection      |  <-- wraps consumer, holds character ref
   +--------+-----------+
            |
   +--------v----------+
   |  CommandHandler    |  <-- 70+ commands, privilege separation
   +--------+-----------+
            |
   +--------v-----------+
   |   CoreActions       |  <-- combat, movement, interaction logic
   +--------+------------+
            |
   +--------v-----------+     +-----------------+
   | ComprehensiveGame  |<--->|  MainProcess    |
   | State (singleton)  |     |  (game loop)    |
   +--------+-----------+     +--------+--------+
            |                          |
   +--------v-----------+     +--------v--------+
   |  World Definition   |     | Tick Processing |
   |  (YAML-loaded)      |     | (0.5s interval) |
   +---------------------+     +-----------------+
```

### Key Architectural Decisions

1. **In-memory game state** -- All entities live in Python objects, not in a database. YAML is the persistence format for both world definitions and player saves. The Django ORM is present but used minimally (auth/admin only).

2. **Tick-based game loop** -- A background daemon thread runs the game loop at 0.5-second intervals (configurable via `Constants.GAME_TICK_SEC`). Combat rounds occur every 8 ticks (4 seconds). This provides deterministic timing for all game events.

3. **Async throughout** -- The game loop, command processing, and all I/O use `async`/`await`. The main loop runs in its own asyncio event loop on a dedicated thread to avoid blocking the ASGI server.

4. **Reference system** -- Actors are tracked by reference number (`|C123`, `|O456`, `|R789`) via `Actor.references_` dictionary, enabling cross-referencing without direct object pointers.

5. **Template-instance separation** -- World definitions (templates) are loaded once from YAML. Operating copies are deep-copied for the live game, allowing respawn from templates.

---

## Module Breakdown

### Core Runtime

| Module | Responsibility |
|---|---|
| `NextGenMUD/asgi.py` | ASGI entrypoint. Registers SIGINT handler, manages lifespan (startup/shutdown). Forces `os._exit(0)` on shutdown to work around Gemini/httpx thread pool hang. |
| `NextGenMUDApp/apps.py` | Django `AppConfig.ready()` -- loads config, initializes game state, starts game loop thread. |
| `NextGenMUDApp/main_process.py` | Main game loop. Processes input queues, timer tick triggers, command queues, combat rounds, resource regeneration, linkdead checks, scheduled events, aggressive NPC checks. |
| `NextGenMUDApp/comprehensive_game_state.py` | Singleton game state manager. Holds all zones, characters, players, connections. Loads world YAML, manages spawn/despawn, linkdead tracking. |
| `NextGenMUDApp/consumers.py` | `MyWebsocketConsumer` -- WebSocket consumer with login state machine (name -> password -> class selection -> stat allocation). Queues input to `Connection.input_queue`. |
| `NextGenMUDApp/command_handler.py` | Command dispatch. 70+ commands with privilege separation (player vs. script-only). Handles command queuing for tick-based execution. |
| `NextGenMUDApp/core_actions.py` | Core game logic -- combat initiation, movement, item manipulation, death handling, XP/leveling. |
| `NextGenMUDApp/communication.py` | `Connection` class and `CommTypes` enum (`DYNAMIC`, `STATIC`, `STATUS`, `CLEARSTATIC`, `CLEARDYNAMIC`). Manages WebSocket message routing. |

### Data Models (`nondb_models/`)

All game entities are non-database Python classes. No Django models are used for game data.

| Module | Responsibility |
|---|---|
| `actors.py` | Base `Actor` class -- reference tracking, flag system, variable storage (temp/perm), room location. |
| `characters.py` | `Character` extends Actor -- attributes (STR/DEX/CON/INT/WIS/CHA), multi-class levels, HP/mana/stamina, equipment slots, inventory, combat state, command queue, resource regeneration. |
| `rooms.py` | `Room` -- exits (with doors/locks), character/object containment, room echo broadcasting. |
| `objects.py` | `Object` -- items with properties, equip locations, triggers. |
| `world.py` | `WorldDefinition`, `Zone` -- template structures loaded from YAML. Zones contain room/char/object definitions. |
| `triggers.py` | 16 trigger types (see Trigger System below). Factory pattern via `Trigger.new_trigger()`. |
| `attacks_and_damage.py` | Damage types, hit/dodge calculations, critical hits, damage reduction. |
| `actor_states.py` | Temporary character states (Stunned, Bleeding, Shielded, etc.) with tick-based durations. |
| `actor_attitudes.py` | NPC disposition system: HOSTILE, UNFRIENDLY, NEUTRAL, FRIENDLY, CHARMED, DOMINATED. |

### Skills System

Skills are organized by class in separate modules with auto-registration into a global skills registry.

| Module | Classes Covered |
|---|---|
| `skills_fighter.py` | Fighter + specializations (Berserker, Guardian, Reaver) |
| `skills_rogue.py` | Rogue + specializations (Duelist, Assassin, Infiltrator) |
| `skills_mage.py` | Mage + specializations (Evoker, Conjurer, Enchanter) |
| `skills_cleric.py` | Cleric + specializations (Warpriest, Restorer, Ritualist) |
| `skills_core.py` | Skill registry, base classes, skill point allocation logic |

Skills have: cooldowns, resource costs (mana/stamina), cast times, level requirements, and scaling formulas. Skill points are allocated per level based on class.

### Scripting & Triggers

| Module | Responsibility |
|---|---|
| `scripts.py` | Custom DSL interpreter. Executes command sequences with variable substitution (`%s%`, `%t%`), conditional blocks (`$if()`), function evaluation (`$random()`, `$tempvar()`, `$permvar()`). |
| `utility.py` | Variable/function parser. Recursive substitution engine for `%variable%` and `$function()` syntax. |
| `nondb_models/triggers.py` | Event-driven trigger dispatch. Criteria evaluation with subject/operator/predicate matching. |

**Trigger Types:**
`CATCH_ANY`, `CATCH_SAY`, `CATCH_LOOK`, `ON_ENTER`, `ON_EXIT`, `ON_ATTACKED`, `ON_DEATH`, `ON_GET`, `ON_DROP`, `ON_USE`, `ON_EQUIP`, `ON_UNEQUIP`, `TIMER_TICK`, `ON_RECEIVE`, `ON_RESET`, `ON_GREET`

### AI Integration

| Module | Responsibility |
|---|---|
| `llm_npc_conversation.py` | Google Gemini integration for NPC conversations. Personality-driven responses, knowledge system with reveal thresholds, quest goal tracking. |
| `combat_ai.py` | Deterministic NPC combat AI -- skill selection, target prioritization. |

### Persistence

| Module | Responsibility |
|---|---|
| `player_save_manager.py` | Player character serialization to/from YAML. Password hashing (PBKDF2-SHA256). Saves attributes, levels, skills, inventory, equipment, location, states, cooldowns. |
| `game_save_utils.py` | Database save utilities (legacy). |

Player saves are stored as individual YAML files in `player_saves/`. Linkdead characters persist in memory for 60 seconds before being saved and removed.

### Configuration

| File | Purpose |
|---|---|
| `NextGenMUDApp/app_config.yaml` | Master configuration -- world data path, LLM provider, save directory, class templates, XP tables, skill point allocations, regeneration rates, combat progression tables. |
| `NextGenMUDApp/config_data/classes.yaml` | Character class definitions. |
| `NextGenMUDApp/constants.py` | `Constants` class with `ClassVar` fields. Loaded from `app_config.yaml` at startup. Covers tick rates, level caps, resource scaling, combat formulas, save settings. |

---

## Character Class System

4 base classes, each with 3 specializations unlocked at level 20:

```
Fighter ──> Berserker | Guardian | Reaver
Rogue   ──> Duelist   | Assassin | Infiltrator
Mage    ──> Evoker    | Conjurer | Enchanter
Cleric  ──> Warpriest | Restorer | Ritualist
```

- **Multiclassing** is supported -- characters maintain a `class_priority` list with per-class levels.
- **Level cap:** 50
- **Attributes:** STR, DEX, CON, INT, WIS, CHA (point-buy at creation, +1 every 10 levels)
- **Resources:** HP, Mana, Stamina -- each with class-based scaling and context-dependent regeneration rates (combat/walking/resting/meditating/sleeping)

---

## Combat System

- **Round-based:** 8 ticks per round (4 seconds)
- **Hit calculation:** Base modifier + level progression + attribute bonuses vs. dodge roll + DEX modifier
- **Multi-attack:** Main hand and off hand attack progression tables per class/level
- **Damage types:** Multiple types with per-type multipliers and reductions
- **Critical hits:** Chance-based with multiplier
- **States:** Stunned, Bleeding, Shielded, and others with tick-based durations
- **Saving throws:** Skill-based with attribute scaling, clamped to 5-95% range

---

## World Data Format

Zones are defined in YAML files under `world_data/`. Each file contains three top-level sections:

```yaml
ZONES:
  zone_id:
    name: "Zone Name"
    rooms:
      room_id:
        name: "Room Name"
        description: "Room description text"
        exits:
          north:
            destination: "other_zone.room_id"
        triggers:
          - type: timer_tick
            criteria:
              - subject: "%time_elapsed%"
                operator: "numgte"
                predicate: 10
            script: |
              echo A gentle breeze passes through.
        characters:
          - id: guard_01
            spawn_time_min: 60
            spawn_time_max: 120

CHARACTERS:
  - zone: zone_id
    characters:
      - id: guard_01
        name: "City Guard"
        level: 5
        class: fighter
        # ... attributes, equipment, triggers, LLM config

OBJECTS:
  - zone: zone_id
    objects:
      - id: iron_sword
        name: "Iron Sword"
        # ... properties, triggers
```

**Current zones:** `central_city`, `enchanted_forest`, `gloomy_graveyard`, `sunken_citadel`, `city_sewers`, `shattered_dominion`, `debug_zone`, `example_attitudes`

---

## Networking & Communication

- **Protocol:** WebSocket over ASGI (Django Channels + Uvicorn)
- **Endpoint:** `/nextgenmud/ws/`
- **Message types sent to client:**
  - `STATIC` -- Persistent display (room descriptions, inventory panels)
  - `DYNAMIC` -- Transient event feed (combat messages, movement, speech)
  - `STATUS` -- HUD vital stats (HP/mana/stamina bars)
  - `CLEARSTATIC` / `CLEARDYNAMIC` -- Clear respective display areas
- **Message routing:** `Actor.echo()` sends to individual, `Room.echo()` broadcasts to all occupants

---

## Startup Flow

1. Uvicorn starts ASGI application (`NextGenMUD/asgi.py`)
2. Django app config `ready()` fires (`NextGenMUDApp/apps.py`)
3. `app_config.yaml` loaded, `Constants` populated
4. `ComprehensiveGameState.Initialize()` scans `world_data/*.yaml`, loads all zones/rooms/characters/objects into memory
5. Operating copies deep-copied from world definitions
6. NPCs spawned into rooms per spawn data
7. `MainProcess` game loop thread started (daemon)
8. SIGINT handler registered for graceful shutdown
9. Server accepts WebSocket connections

**Startup command:**
```
uvicorn NextGenMUD.asgi:application --host 0.0.0.0 --port 8000
```

Or via `run.bat` (Windows):
```
run.bat [--log-width N] [--log-level LEVEL]
```

---

## Graceful Shutdown

Shutdown is carefully orchestrated to handle a known issue with Google Gemini's httpx client:

1. SIGINT sets `MainProcess._shutdown_flag` and `game_state.shutting_down`
2. Game loop exits, linkdead characters are saved
3. Uvicorn closes WebSocket connections (consumers see `shutting_down=True` and skip linkdead timers)
4. ASGI lifespan shutdown shuts down asyncio executor and all `ThreadPoolExecutor` instances
5. `os._exit(0)` forces process termination (required because httpx non-daemon threads hang indefinitely)

---

## Testing

**Framework:** pytest (17 test modules in `tests/`)

| Test Module | Coverage Area |
|---|---|
| `test_utility.py` | Variable substitution, parsing |
| `test_character.py` | Character model, attributes, leveling |
| `test_skills.py` | Skill registry, allocation |
| `test_combat_ai.py` | NPC combat decision-making |
| `test_mage_spells.py` | Mage spell mechanics |
| `test_cleric_spells.py` | Cleric spell mechanics |
| `test_npc_behavior.py` | NPC behavior patterns |
| `test_trigger_llm.py` | LLM trigger integration |
| `test_multiclass.py` | Multi-class mechanics |
| `test_player_death.py` | Death and respawn |
| `test_healing.py` | Healing mechanics |
| `test_resources.py` | HP/mana/stamina system |
| `test_flee_and_guards.py` | Flee mechanics, guard behavior |
| `test_actor_states.py` | State system (stun, bleed, etc.) |
| `test_on_attacked_trigger.py` | Combat trigger system |
| `test_status_bar.py` | HUD status updates |
| `test_route.py` | WebSocket routing |

Shared fixtures in `conftest.py` provide mock game state, test characters (fighter/mage/rogue), mock rooms, and mock connections.

---

## Dependencies

```
django==5.0.1              # Web framework, admin, ORM (minimal use)
channels==4.0.0            # WebSocket support via ASGI
structlog==23.2.0          # Structured logging with context tracking
pyyaml==6.0.2              # YAML parsing
ruamel.yaml>=0.18.0        # YAML round-trip editing (preserves comments)
uvicorn[standard]==0.27.1  # ASGI server
whitenoise==6.6.0          # Static file serving
python-dotenv==1.0.0       # Environment variable loading
google-genai>=1.0.0        # Google Gemini LLM integration
```

---

## Design Patterns

| Pattern | Usage |
|---|---|
| **Singleton** | `ComprehensiveGameState` (`live_game_state`), `CommandHandlerInterface.get_instance()` |
| **Factory** | `Trigger.new_trigger()` creates typed trigger subclasses |
| **Command** | Command handler dictionary dispatch |
| **Observer** | Room echo broadcasting to all occupants |
| **State** | `ActorState` objects with tick-based durations |
| **Strategy** | Class-specific skill modules, combat AI |
| **Template Method** | Script execution with pluggable variable substitution |
| **Interface Segregation** | `*_interface.py` modules define abstract contracts for characters, actors, rooms, objects, triggers |

---

## Project Structure

```
NextGenMUD/
|-- NextGenMUD/                    # Django project config
|   |-- asgi.py                    # ASGI entrypoint + shutdown handling
|   |-- settings.py                # Django settings
|   |-- urls.py                    # HTTP URL routing
|   +-- wsgi.py                    # WSGI fallback
|
|-- NextGenMUDApp/                 # Main application (Django app)
|   |-- apps.py                    # App initialization
|   |-- main_process.py            # Game loop
|   |-- comprehensive_game_state.py# Central game state
|   |-- command_handler.py         # Command dispatch (70+ commands)
|   |-- consumers.py               # WebSocket consumer
|   |-- core_actions.py            # Game action logic
|   |-- scripts.py                 # DSL script interpreter
|   |-- utility.py                 # Variable substitution engine
|   |-- combat_ai.py               # NPC combat AI
|   |-- llm_npc_conversation.py    # Gemini NPC conversations
|   |-- structured_logger.py       # Logging system
|   |-- constants.py               # Game constants + class system
|   |-- config.py                  # Config loader
|   |-- app_config.yaml            # Master configuration
|   |-- player_save_manager.py     # Player persistence
|   |-- skills_core.py             # Skill registry
|   |-- skills_fighter.py          # Fighter skills
|   |-- skills_mage.py             # Mage spells
|   |-- skills_rogue.py            # Rogue skills
|   |-- skills_cleric.py           # Cleric spells
|   |-- handlers/
|   |   +-- level_up_handler.py    # Level-up logic
|   |-- config_data/
|   |   +-- classes.yaml           # Class definitions
|   +-- nondb_models/              # In-memory game entities
|       |-- actors.py              # Base actor
|       |-- characters.py          # Characters/NPCs
|       |-- rooms.py               # Rooms + exits
|       |-- objects.py             # Items/objects
|       |-- world.py               # Zone/world templates
|       |-- triggers.py            # 16 trigger types
|       |-- attacks_and_damage.py  # Combat math
|       |-- actor_states.py        # Temporary states
|       |-- actor_attitudes.py     # NPC dispositions
|       +-- *_interface.py         # Abstract interfaces
|
|-- world_data/                    # YAML zone definitions
|   |-- central_city.yaml
|   |-- enchanted_forest.yaml
|   |-- gloomy_graveyard.yaml
|   |-- sunken_citadel.yaml
|   |-- city_sewers.yaml
|   |-- shattered_dominion.yaml
|   |-- debug_zone.yaml
|   +-- example_attitudes.yaml
|
|-- player_saves/                  # Per-character YAML saves
|-- tests/                         # pytest suite (17 modules)
|-- documentation/                 # Guides & design docs
|   |-- world-building-guide.md
|   |-- scripting-guide.md
|   |-- character_yaml_template.md
|   |-- saving-throws-design.md
|   +-- world-merge-format.md
|
|-- requirements.txt
|-- manage.py
|-- run.bat                        # Windows launcher
+-- run.sh                         # Unix launcher
```

---

## Documentation Index

| Document | Description |
|---|---|
| `README.md` | Project overview, getting started, command reference |
| `README-design.md` | Scripting system technical design (MobProg evolution) |
| `README-SCRIPTING.md` | Scripting reference (triggers, variables, functions) |
| `README-merge-mud-files.md` | Zone file merger tool and revision syntax |
| `README-ai-zone-design.md` | AI-assisted zone building methodology |
| `documentation/world-building-guide.md` | Zone, room, NPC, object, quest creation guide |
| `documentation/scripting-guide.md` | Script variable/function reference |
| `documentation/character_yaml_template.md` | Character YAML template reference |
| `documentation/saving-throws-design.md` | Saving throw system design |
| `documentation/world-merge-format.md` | World merge format specification |

---

## Notable Technical Observations

1. **No ORM for game data** -- The project uses Django but intentionally avoids the ORM for all game entities. This trades ACID guarantees for simplicity and performance in a real-time context. Player saves are YAML files, not database rows.

2. **Forced process exit** -- The shutdown path uses `os._exit(0)` because Google Gemini's httpx client creates non-daemon threads that prevent clean Python exit. This is documented extensively in `asgi.py`.

3. **Dual signal handling** -- SIGINT is handled in both `main_process.py` (sets shutdown flags before Uvicorn tears down connections) and `asgi.py` (lifespan handler). The ordering is critical to ensure `handle_disconnect` sees `shutting_down=True`.

4. **Windows-specific event loop** -- `WindowsSelectorEventLoopPolicy` is used to avoid Proactor event loop issues on Windows.

5. **Tick-based command queuing** -- Player commands execute on ticks rather than immediately, providing natural pacing. Instant commands (e.g., `settempvar`) bypass the queue.

6. **Custom DSL over embedded language** -- The scripting system uses a custom DSL (evolved from MobProg) rather than embedding Python/Lua. This provides sandboxing but limits expressiveness. Recursive variable/function parsing handles nested expressions like `$if($tempvar(%S%, wounded), gt, 0) { ... }`.

7. **LLM integration is optional** -- NPC conversations with Gemini are configured per-NPC in zone YAML. NPCs without LLM config fall back to trigger-based scripted responses.

8. **Interface segregation** -- The `nondb_models/` package uses `*_interface.py` files to define abstract contracts, reducing circular import issues between characters, rooms, actors, and triggers.
