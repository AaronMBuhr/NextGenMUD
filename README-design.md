# NextGenMUD Scripting System - Technical Design Document

## Overview

NextGenMUD features a custom Domain-Specific Language (DSL) and interpreter system for game scripting. This document details the architecture, implementation decisions, and technical components of the scripting system.

### Historical Context

The scripting architecture in NextGenMUD is a modern evolution of the **MobProg** system, which I (Aaron Buhr, known as "Dimwit Flathead the First") originally invented for **Worlds of Carnage** in the early 1990s. MobProgs became the foundation for embedded scripting in MUD development and were adopted across the Merc/ROM/Circle MUD codebases that powered thousands of games.

From Raph Koster (Lead Designer, Ultima Online & Star Wars Galaxies):

> "Worlds of Carnage, first Diku with embedded scripting."

From the Merc MUD source code CREDITS:

> "The original idea for this type of MOB PROGRAM came from playing on: WORLDS of CARNAGE, a DIKU MUD implemented by Robbie Roberts and Aaron Buhr. Aaron (known as Dimwit Flathead the First) was the original author..."

NextGenMUD represents a ground-up reimagining of that original concept with modern language features, async execution, and integration with LLM-powered NPCs.

---

## Architecture Overview

The scripting system consists of five major components:

```
┌─────────────────────────────────────────────────────────────────┐
│                        YAML Zone Files                          │
│         (triggers, criteria, scripts defined declaratively)     │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      YAML Loader / Parser                       │
│            (from_dict() methods on entity classes)              │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Trigger Dispatch System                     │
│     (event-driven: CATCH_SAY, TIMER_TICK, ON_ENTER, etc.)      │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Script Interpreter                         │
│   (variable substitution → function evaluation → execution)     │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Command Runtime Engine                      │
│        (70+ commands, privilege separation, tick-based)         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component 1: Custom Parser & Tokenizer

### Variable Substitution Parser

**Location:** `utility.py` - `replace_vars()`

A regex-based variable substitution system that replaces `%variable%` tokens with runtime values.

```python
# Compiled regex for performance
variable_replacement_regex = re.compile(r"%[A-Za-z_*#$][A-Za-z_*#$0-9]*%")

def replace_vars(script, vars: dict) -> str:
    return variable_replacement_regex.sub(
        lambda match: str(vars.get(match.group()[1:-1], match.group())), 
        script
    )
```

**Design Decision:** Variables use `%` delimiters (e.g., `%S%`, `%actor_name%`) for clarity in YAML files and to avoid conflicts with shell/string interpolation. Undefined variables pass through unchanged, allowing graceful degradation.

### Text Pattern Matching Grammar

**Location:** `utility.py` - `parse_text_pattern_tokens()`, `matches_text_pattern()`

A custom grammar for flexible text matching in trigger criteria, designed to be intuitive for non-technical world builders:

```
Grammar:
  pattern     := term (SPACE term)*           # AND: all terms must match
  term        := group | word
  group       := '(' alternative ('|' alternative)* ')'  # OR: any alternative
  alternative := text
  word        := text (no spaces, parens, or pipes)
```

**Examples:**
```yaml
# Simple substring (backward compatible)
predicate: "hello"

# OR matching - any alternative triggers
predicate: "(travel|guide|directions)"

# AND + OR - must match one from each group
predicate: "(travel|guide) (oasis|water)"

# Mixed
predicate: "cave (dark|dim|shadowy)"
```

**Implementation:**
```python
def parse_text_pattern_tokens(pattern: str) -> List[Tuple[str, any]]:
    """Parse pattern into tokens: ('word', 'text') or ('group', ['alt1', 'alt2'])"""
    tokens = []
    i = 0
    while i < len(pattern):
        if pattern[i] == '(':
            # Find matching paren, extract alternatives
            # ... balanced parenthesis tracking ...
            alternatives = [alt.strip() for alt in group_content.split('|')]
            tokens.append(('group', alternatives))
        elif pattern[i] == '|':
            # Standalone pipe without parens
            alternatives = [alt.strip() for alt in word.split('|')]
            tokens.append(('group', alternatives))
        else:
            tokens.append(('word', word))
    return tokens
```

### Conditional Block Parser

**Location:** `utility.py` - `parse_blocks()`, `find_matching_parenthesis()`

Parses `$if(condition){true_block}else{false_block}` syntax with proper brace balancing:

```python
def parse_blocks(text):
    """
    Parse conditional blocks with balanced brace tracking.
    Returns: {'true_block': str, 'false_block': str, 'remainder': str}
    """
    stack = []
    true_block, false_block, remainder = [], [], []
    # ... tracks brace depth, detects 'else' keyword ...
```

**Design Decision:** The `$if(subject, operator, predicate){}` syntax was designed to be readable by non-programmers while still being unambiguous to parse. The comma-separated arguments inside parentheses avoid the complexity of infix operators.

---

## Component 2: Function Evaluator

**Location:** `utility.py` - `evaluate_functions_in_line()`, `SCRIPT_FUNCTIONS`

A recursive function evaluator that processes `$function(args)` calls embedded in script text.

### Function Registry

```python
SCRIPT_FUNCTIONS = {
    # String functions
    "cap": lambda a,b,c,gs: firstcap(a),
    
    # Numeric comparisons (return "true"/"false" strings)
    "numeq":  lambda a,b,c,gs: "true" if to_int(a) == to_int(b) else "false",
    "numgt":  lambda a,b,c,gs: "true" if to_int(a) > to_int(b) else "false",
    "numlt":  lambda a,b,c,gs: "true" if to_int(a) < to_int(b) else "false",
    "numgte": lambda a,b,c,gs: "true" if to_int(a) >= to_int(b) else "false",
    "numlte": lambda a,b,c,gs: "true" if to_int(a) <= to_int(b) else "false",
    "between": lambda a,b,c,gs: "true" if to_int(a) <= to_int(b) <= to_int(c) else "false",
    
    # Randomness
    "random": lambda a,b,c,gs: str(random.randint(to_int(a), to_int(b))),
    
    # Variable access
    "tempvar":  lambda a,b,c,gs: gs.get_temp_var(a, b),
    "permvar":  lambda a,b,c,gs: gs.get_perm_var(a, b),
    "questvar": lambda a,b,c,gs: get_quest_var_wrapper(a, b, gs),
    
    # Inventory queries
    "hasitem":    lambda a,b,c,gs: does_char_have_item_anywhere(a, b, gs),
    "hasiteminv": lambda a,b,c,gs: does_char_have_item_inv(a, b, gs),
    "hasitemeq":  lambda a,b,c,gs: does_char_have_item_equipped(a, b, gs),
    
    # Location queries
    "locroom": lambda a,b,c,gs: gs.find_target_character(a).current_room_.name_,
    "loczone": lambda a,b,c,gs: gs.find_target_character(a).current_room_.zone_.name_,
}
```

### Recursive Evaluation

The evaluator handles nested function calls:

```python
def evaluate_functions_in_line(line: str, vars: dict, game_state) -> str:
    """
    Recursively evaluate all $function() calls in a line.
    Handles nesting: $cap($locroom(%S%)) → "Town Square"
    """
    result_parts = []
    start = 0
    
    while (next := line.find('$', start)) > -1:
        result_parts.append(line[start:next])
        
        # Extract function name and find matching parenthesis
        fn_end = line.find('(', next + 1)
        func_name = line[next+1:fn_end]
        args_end = find_matching_parenthesis(line, fn_end)
        
        # Parse arguments (respecting nested parens)
        args_str = line[fn_end+1:args_end]
        arg_parts = split_string_honoring_parentheses(args_str)
        
        # Recursive evaluation of arguments
        args = [evaluate_functions_in_line(ap, vars, game_state) for ap in arg_parts]
        
        # Execute function
        result = SCRIPT_FUNCTIONS[func_name](args[0], args[1], args[2], game_state)
        result_parts.append(result)
        start = args_end + 1
    
    return ''.join(result_parts)
```

---

## Component 3: Trigger Dispatch System

**Location:** `nondb_models/triggers.py`, `nondb_models/trigger_interface.py`

### Trigger Type Enumeration

```python
class TriggerType(Enum):
    CATCH_ANY = 1      # Fires on any game event matching criteria
    CATCH_SAY = 2      # Fires when someone speaks
    CATCH_TELL = 3     # Fires on private messages
    TIMER_TICK = 4     # Fires periodically based on elapsed time
    CATCH_LOOK = 5     # Fires when someone looks at something
    ON_ENTER = 6       # Fires when character enters room
    ON_EXIT = 7        # Fires when character exits room
    ON_RECEIVE = 8     # Fires when NPC receives item via give
    ON_GET = 9         # Fires when object is picked up
    ON_DROP = 10       # Fires when object is dropped
    ON_OPEN = 11       # Fires when container/door opened
    ON_CLOSE = 12      # Fires when container/door closed
    ON_LOCK = 13       # Fires when something is locked
    ON_UNLOCK = 14     # Fires when something is unlocked
    ON_USE = 15        # Fires when object is used
    ON_ATTACKED = 16   # Fires when actor is attacked
```

### Class Hierarchy

```
TriggerInterface (abstract)
    │
    └── Trigger (base implementation)
            │
            ├── TriggerCatchAny
            ├── TriggerCatchSay
            ├── TriggerCatchLook
            ├── TriggerTimerTick    # Special: maintains class-level registry
            ├── TriggerOnEnter
            ├── TriggerOnExit
            ├── TriggerOnReceive
            ├── TriggerOnGet
            ├── TriggerOnDrop
            ├── TriggerOnOpen
            ├── TriggerOnClose
            ├── TriggerOnLock
            ├── TriggerOnUnlock
            ├── TriggerOnUse
            └── TriggerOnAttacked
```

### Factory Pattern for Trigger Creation

```python
@classmethod
def new_trigger(cls, trigger_type, actor: 'Actor', disabled=False):
    """Factory method creates appropriate trigger subclass."""
    if trigger_type_enum == TriggerType.CATCH_SAY:
        return TriggerCatchSay(trigger_id, actor, disabled)
    elif trigger_type_enum == TriggerType.TIMER_TICK:
        return TriggerTimerTick(trigger_id, actor, disabled)
    # ... etc for all types
```

### Timer Tick Optimization

Timer triggers use a class-level set for O(1) access during the game loop:

```python
class TriggerTimerTick(Trigger):
    timer_tick_triggers_ = set()  # Class-level registry
    
    def enable(self):
        super().enable()
        TriggerTimerTick.timer_tick_triggers_.add(self)
    
    def disable(self):
        super().disable()
        TriggerTimerTick.timer_tick_triggers_.discard(self)
```

### Criteria Evaluation

Each trigger has criteria that must all pass (AND logic):

```python
class TriggerCriteria:
    def evaluate(self, vars: dict, game_state) -> bool:
        # Variable substitution and function evaluation
        subject = evaluate_functions_in_line(replace_vars(self.subject, vars), vars, game_state)
        predicate = evaluate_functions_in_line(replace_vars(self.predicate, vars), vars, game_state)
        
        # Delegate to condition evaluator
        return evaluate_if_condition(subject, self.operator, predicate)
```

### Condition Operators

```python
IF_CONDITIONS = {
    "eq":       lambda a,b,c: a == b,
    "neq":      lambda a,b,c: a != b,
    "!=":       lambda a,b,c: a != b,
    "numeq":    lambda a,b,c: to_int(a) == to_int(b),
    "numneq":   lambda a,b,c: to_int(a) != to_int(b),
    "numgt":    lambda a,b,c: to_int(a) > to_int(b),
    "numlt":    lambda a,b,c: to_int(a) < to_int(b),
    "numgte":   lambda a,b,c: to_int(a) >= to_int(b),
    "numlte":   lambda a,b,c: to_int(a) <= to_int(b),
    "between":  lambda a,b,c: to_int(a) <= to_int(b) <= to_int(c),
    "contains": lambda a,b,c: matches_text_pattern(a, b),  # Custom grammar
    "matches":  lambda a,b,c: re.match(b, a),              # Regex
    "true":     lambda a,b,c: True,
    "false":    lambda a,b,c: False,
}
```

---

## Component 4: Runtime Engine

**Location:** `scripts.py` - `ScriptHandler`

### Script Execution Flow

```python
class ScriptHandler:
    @classmethod
    async def run_script(cls, actor, script, vars, game_state):
        # Phase 1: Variable substitution
        script = replace_vars(script, vars).strip()
        
        while script:
            # Phase 2: Conditional handling
            if script.startswith("$if("):
                # Parse condition
                condition = script[4:end_of_condition]
                condition_parts = split_string_honoring_parentheses(condition)
                
                # Evaluate each part (with function calls)
                if_subject = evaluate_functions_in_line(condition_parts[0], vars, game_state)
                if_operator = evaluate_functions_in_line(condition_parts[1], vars, game_state)
                if_predicate = evaluate_functions_in_line(condition_parts[2], vars, game_state)
                
                # Choose branch
                condition_result = evaluate_condition(if_subject, if_operator, if_predicate)
                blocks = parse_blocks(after_condition)
                script = blocks['true_block'] if condition_result else blocks['false_block']
                script += '\n' + blocks['remainder']
            else:
                # Phase 3: Process single command line
                script = await cls.process_line(actor, script, vars, game_state)
    
    @classmethod
    async def process_line(cls, actor, script, vars, game_state):
        line = script[:script.find('\n')].strip()
        
        # Function evaluation on command line
        line = evaluate_functions_in_line(line, vars, game_state)
        
        # Queue command for tick-based execution (Characters)
        # or execute immediately (Rooms, Objects)
        if actor.actor_type == ActorType.CHARACTER:
            actor.command_queue.append(line)
        else:
            await CommandHandler.process_command(actor, line, vars, from_script=True)
```

### Tick-Based Command Execution

**Location:** `main_process.py`, `command_handler.py`

Characters don't execute commands immediately - they queue them for natural timing:

```python
# Main game loop (runs every 0.5 seconds)
async def main_game_loop(cls):
    while not shutdown:
        # Process timer tick triggers
        for trig in TriggerTimerTick.timer_tick_triggers_:
            await trig.run(trig.actor_, "", {}, game_state)
        
        # Process command queues (tick-based execution)
        for ref_id, actor in Actor.references_.items():
            if actor.actor_type == ActorType.CHARACTER and actor.command_queue:
                if not actor.is_busy(world_clock_tick):
                    await CommandHandler.process_command_queue(actor, game_state)
        
        await asyncio.sleep(GAME_TICK_SEC)  # 0.5 seconds
```

**Design Decision:** This creates natural reaction timing - NPCs don't respond instantly but over ~0.5s intervals, making interactions feel more realistic. It also prevents script loops from blocking the game.

### Instant Commands

Some commands bypass the tick system for immediate execution:

```python
instant_commands = {
    "_trigger_start", "_trigger_end",
    "settempvar", "setpermvar", "deltempvar", "delpermvar",
    "setquestvar", "getquestvar"
}
```

---

## Component 5: Command Runtime

**Location:** `command_handler.py`

### Command Registration

70+ commands registered via dictionary dispatch:

```python
command_handlers = {
    # Privileged (script-only) commands
    "echo":       lambda cmd, char, input: cls.cmd_echo(char, input),
    "echoto":     lambda cmd, char, input: cls.cmd_echoto(char, input),
    "spawn":      lambda cmd, char, input: cls.cmd_spawn(char, input),
    "damage":     lambda cmd, char, input: cls.cmd_damage(char, input),
    "heal":       lambda cmd, char, input: cls.cmd_heal(char, input),
    "transfer":   lambda cmd, char, input: cls.cmd_transfer(char, input),
    "force":      lambda cmd, char, input: cls.cmd_force(char, input),
    "pause":      lambda cmd, char, input: cls.cmd_pause(char, input),
    "walkto":     lambda cmd, char, input: cls.cmd_walkto(char, input),
    
    # Player commands
    "say":        lambda cmd, char, input: cls.cmd_say(char, input),
    "look":       lambda cmd, char, input: cls.cmd_look(char, input),
    "get":        lambda cmd, char, input: cls.cmd_get(char, input),
    "attack":     lambda cmd, char, input: cls.cmd_attack(cmd, char, input),
    # ... etc
}
```

### Privilege Separation (Sandboxing)

Scripts can execute privileged commands that players cannot:

```python
privileged_commands = {
    "echo", "echoto", "echoexcept",
    "settempvar", "setpermvar", "deltempvar", "delpermvar",
    "spawn", "spawnobj", "damage", "heal", "removeitem",
    "transfer", "teleport", "force", "pause", "delay",
    "setquestvar", "getquestvar", "walkto", "stop",
    # ... admin commands
}

async def process_command(cls, actor, input, vars=None, from_script=False):
    command = input.split()[0].lower()
    
    # Block privileged commands from player input
    if not from_script and command in cls.privileged_commands:
        if not actor.has_game_permissions(GamePermissionFlags.IS_ADMIN):
            await actor.send_text("Unknown command.")
            return
    
    # Dispatch to handler
    await cls.command_handlers[command](command, actor, args)
```

---

## Component 6: YAML Loading & Entity Hydration

**Location:** Various `from_dict()` and `from_yaml()` methods

### Zone File Structure

```yaml
zone_id: enchanted_forest
zone_name: The Enchanted Forest

variables:
  forest_quest:
    found_fairy:
      type: boolean
      default: false
      knowledge_updates:
        - condition: true
          updates:
            fairy_knowledge: "You've met the forest fairy."

rooms:
  glade:
    name: Mystical Glade
    description: A peaceful clearing bathed in ethereal light.
    exits:
      north: deep_woods
    triggers:
      - id: ambient_sparkles
        type: timer_tick
        flags: [only_when_pc_room]
        criteria:
          - subject: "%time_elapsed%"
            operator: numgte
            predicate: 30
        script: |
          echo Tiny sparkles dance through the air.

characters:
  - id: fairy
    name: forest fairy
    triggers:
      - id: greet_visitor
        type: catch_say
        criteria:
          - subject: "%*%"
            operator: contains
            predicate: "hello"
        script: |
          sayto %S% Welcome to my forest, traveler!
          setquestvar %S% forest_quest.found_fairy true
```

### Trigger Loading

```python
# In Character.from_dict()
for trigger_data in values.get('triggers', []):
    trigger_type_str = trigger_data.get('type', 'catch_any')
    trigger = Trigger.new_trigger(trigger_type_str, self, disabled=True)
    trigger.from_dict(trigger_data)
    
    # Index by type for efficient dispatch
    if trigger.trigger_type_ not in self.triggers_by_type:
        self.triggers_by_type[trigger.trigger_type_] = []
    self.triggers_by_type[trigger.trigger_type_].append(trigger)
    trigger.enable()
```

---

## Event Flow Example

When a player says "hello" to an NPC:

```
1. Player input: "say hello"
                    │
                    ▼
2. CommandHandler.cmd_say()
   - Broadcasts message to room
   - Iterates characters in room
                    │
                    ▼
3. For each NPC with CATCH_SAY triggers:
   for trig in npc.triggers_by_type[TriggerType.CATCH_SAY]:
       await trig.run(npc, "hello", vars, game_state)
                    │
                    ▼
4. TriggerCatchSay.run()
   - Builds vars: %S% = player ref, %*% = "hello", etc.
   - Evaluates all criteria:
     - subject: "%*%" → "hello"  
     - operator: "contains"
     - predicate: "hello"
     - Result: True (matches)
                    │
                    ▼
5. Trigger.execute_trigger_script()
   - Calls ScriptHandler.run_script()
                    │
                    ▼
6. ScriptHandler.run_script()
   - Variable substitution: "sayto %S%" → "sayto |C507"
   - Queues commands to NPC's command_queue:
     ["sayto |C507 Welcome to my forest!", "setquestvar |C507 ..."]
                    │
                    ▼
7. Next game tick (0.5s later):
   - MainProcess processes NPC command queue
   - Commands execute with natural timing
                    │
                    ▼
8. Player sees: "The forest fairy says to you, 'Welcome to my forest!'"
```

---

## Design Philosophy

### For Non-Technical World Builders

The scripting language prioritizes readability and approachability:

- **YAML format**: Familiar, indentation-based, no special syntax to learn
- **Natural operators**: `contains`, `numgte` instead of symbols
- **Pattern grammar**: `(travel|guide) (oasis|water)` reads like English
- **Clear variable names**: `%actor_name%`, `%time_elapsed%`
- **Declarative triggers**: Define "when" separately from "what"

### Performance Considerations

- **Compiled regex** for variable substitution
- **Class-level trigger registry** for O(1) timer tick access
- **Indexed triggers by type** on each actor
- **Tick-based batching** prevents script spam

### Safety & Sandboxing

- **Privileged command separation**: Players can't `spawn`, `damage`, `force`
- **No arbitrary code execution**: Fixed function set, no eval()
- **Timeout on pause**: Maximum 60 second pause to prevent hangs
- **Deleted actor checks**: Triggers auto-cleanup when actors removed

---

## Summary: What I Implemented

| Component | Implementation |
|-----------|---------------|
| **DSL Design** | Complete language specification: triggers, criteria, scripts, variables, functions, conditionals |
| **Parser/Tokenizer** | Variable regex parser, text pattern grammar tokenizer, conditional block parser |
| **Function Evaluator** | Recursive `$function()` evaluator with 20+ built-in functions |
| **Trigger System** | Event-driven dispatch with 16 trigger types, factory pattern, criteria evaluation |
| **Runtime Engine** | Async script interpreter with tick-based command queuing |
| **Command System** | 70+ commands with privilege separation and sandboxing |
| **YAML Loader** | Entity hydration from declarative zone files |
| **Quest System** | Variable schema with automatic world knowledge updates |

This represents a complete, production-ready scripting system - a modern evolution of the MobProg concept I originally invented for Worlds of Carnage, now with async Python, LLM integration, and a syntax designed for accessibility.
