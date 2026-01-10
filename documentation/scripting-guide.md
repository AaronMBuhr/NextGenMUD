# NextGenMUD Scripting Guide

A comprehensive reference for the NextGenMUD scripting system, covering triggers, variable substitution, functions, and script commands.

---

## Table of Contents

1. [Overview](#overview)
2. [Variable Substitution (% Variables)](#variable-substitution--variables)
3. [Script Functions ($ Functions)](#script-functions--functions)
4. [Triggers](#triggers)
5. [Script Commands](#script-commands)
6. [Conditional Logic](#conditional-logic)
7. [Operators](#operators)
8. [Quest Variables](#quest-variables)
9. [Game Commands Reference](#game-commands-reference)
10. [Examples](#examples)
11. [Best Practices](#best-practices)
12. [Troubleshooting](#troubleshooting)

---

## Overview

The NextGenMUD scripting system allows you to create dynamic, interactive game content through **triggers** and **scripts**. Triggers define *when* something happens (based on events and conditions), while scripts define *what* happens (a series of commands to execute).

### Core Concepts

- **Triggers**: Event listeners attached to rooms, NPCs, or objects
- **Criteria**: Conditions that must be met for a trigger to fire
- **Scripts**: Sequences of commands that execute when a trigger fires
- **Variables**: Dynamic values that can be substituted into scripts
- **Functions**: Built-in operations for calculations and game state queries

---

## Variable Substitution (% Variables)

Variables are enclosed in `%` signs and are replaced with their values before script execution. The pattern is `%variable_name%`.

### Core Variables

These are automatically available in all trigger contexts:

| Variable | Description | Example Value |
|----------|-------------|---------------|
| `%a%` | Actor's name with article | "the shopkeeper" |
| `%A%` | Actor's reference (for targeting) | "\|C507" |
| `%p%` | Actor's subject pronoun | "he", "she", "it" |
| `%P%` | Actor's object pronoun | "him", "her", "it" |
| `%s%` | Subject's name with article | "a player" |
| `%S%` | Subject's reference | "\|C123" |
| `%q%` | Subject's subject pronoun | "he", "she", "they" |
| `%Q%` | Subject's object pronoun | "him", "her", "them" |
| `%t%` | Target's name with article | "the sword" |
| `%T%` | Target's reference | "\|O456" |
| `%r%` | Target's subject pronoun | "it" |
| `%R%` | Target's object pronoun | "it" |
| `%*%` | The current message/event text | "player says hello" |

### Context-Specific Variables

| Variable | Context | Description |
|----------|---------|-------------|
| `%time_elapsed%` | `timer_tick` triggers | Seconds since last trigger execution |
| `%item%` | `on_receive`, `on_get`, `on_drop` | The item involved |
| `%item_id%` | `on_receive`, `on_get`, `on_drop` | The item's ID |
| `%item_name%` | `on_receive` | The item's display name |
| `%target%` | `on_use` | Target of "use X on Y" |
| `%target_id%` | `on_use` | Target's ID |
| `%attack_noun%` | `on_attacked` | The attack noun (e.g., "sword", "claws") |
| `%attack_verb%` | `on_attacked` | The attack verb (e.g., "slashes", "bites") |

### Actor vs Subject vs Target

Understanding the difference is crucial:

- **Actor (`%a%`, `%A%`)**: The entity that owns the trigger (the NPC, room, or object with the trigger)
- **Subject (`%s%`, `%S%`)**: Usually the character who caused the trigger to fire (e.g., the player who entered a room)
- **Target (`%t%`, `%T%`)**: An optional third party (e.g., in "give sword to guard", the guard is the target)

### Using References for Commands

The uppercase reference variables (`%A%`, `%S%`, `%T%`) are essential for targeting in commands:

```yaml
script: |
  echoto %S% You feel a chill run down your spine.
  echoexcept %S% $cap(%s%) shivers uncontrollably.
```

The reference format (e.g., `|C507`) ensures you're targeting the exact entity, not just any entity with the same name.

### Variable Syntax Notes

- Variables must be alphanumeric with underscores: `%my_var%`
- Variables are case-sensitive: `%s%` ≠ `%S%`
- Undefined variables are left as-is in the output
- Curly braces may appear in some older zone files: `%{*}` (same as `%*%`)

---

## Script Functions ($ Functions)

Functions are called with the syntax `$function_name(arg1, arg2, ...)` and return a value that replaces the function call in the script.

### String Functions

| Function | Description | Example |
|----------|-------------|---------|
| `$cap(text)` | Capitalize first letter | `$cap(the guard)` → "The guard" |

### Numeric Functions

| Function | Description | Example |
|----------|-------------|---------|
| `$random(min, max)` | Random integer between min and max | `$random(1, 100)` |
| `$numeq(a, b)` | Returns "true" if a == b | `$numeq(5, 5)` → "true" |
| `$numneq(a, b)` | Returns "true" if a != b | `$numneq(5, 3)` → "true" |
| `$numgt(a, b)` | Returns "true" if a > b | `$numgt(10, 5)` → "true" |
| `$numlt(a, b)` | Returns "true" if a < b | `$numlt(3, 10)` → "true" |
| `$numgte(a, b)` | Returns "true" if a >= b | `$numgte(5, 5)` → "true" |
| `$numlte(a, b)` | Returns "true" if a <= b | `$numlte(5, 10)` → "true" |
| `$between(a, b, c)` | Returns "true" if a <= b <= c | `$between(1, 5, 10)` → "true" |

### Variable Access Functions

| Function | Description | Example |
|----------|-------------|---------|
| `$tempvar(target, name)` | Get temporary variable value | `$tempvar(%S%, orb_glow)` |
| `$permvar(target, name)` | Get permanent variable value | `$permvar(%S%, visited_inn)` |
| `$questvar(target, var_id)` | Get quest variable value | `$questvar(%S%, murder_mystery.found_body)` |

### Inventory/Equipment Functions

| Function | Description | Returns |
|----------|-------------|---------|
| `$hasitem(char, item)` | Check if character has item anywhere | "true" or "false" |
| `$hasiteminv(char, item)` | Check if item is in inventory | "true" or "false" |
| `$hasitemeq(char, item)` | Check if item is equipped | "true" or "false" |
| `$equipped(char, slot)` | Get equipped item in slot | Item reference |

### Location Functions

| Function | Description | Example Result |
|----------|-------------|----------------|
| `$locroom(char)` | Room name where character is | "Mystical Glade" |
| `$loczone(char)` | Zone name where character is | "Enchanted Forest" |
| `$olocroom(obj)` | Room name where object is | "Town Square" |
| `$oloczone(obj)` | Zone name where object is | "Central City" |

### Using Functions in Scripts

Functions can be nested and combined:

```yaml
script: |
  # Chance-based event
  $if($random(1,100), numlte, 25){
    echo A shooting star streaks across the sky!
  }
  
  # Check player state
  $if($hasitem(%S%, ancient_key), eq, true){
    echo The door clicks open.
  }
  
  # Dynamic message
  echoto %S% You are in $locroom(%S%) of the $loczone(%S%).
```

---

## Triggers

Triggers are event listeners that execute scripts when specific conditions are met.

### Trigger Structure (YAML)

```yaml
triggers:
  - id: unique_trigger_id
    type: trigger_type
    flags:                    # Optional
      - only_when_pc_room
    criteria:
      - subject: "%*%"
        operator: contains
        predicate: "hello"
    script: |
      say Hello there!
```

### Trigger Types

#### `catch_any`

Fires on any game event matching the criteria. This is the most general-purpose trigger.

```yaml
- id: catch_singing
  type: catch_any
  criteria:
    - subject: "%*%"
      operator: contains
      predicate: "sing"
  script: |
    echo Your singing echoes through the chamber.
```

#### `catch_say`

Fires when someone says something matching the criteria.

```yaml
- id: respond_to_greeting
  type: catch_say
  criteria:
    - subject: "%*%"
      operator: contains
      predicate: "hello"
  script: |
    sayto %S% Hello, traveler! Welcome to my shop.
```

#### `catch_look`

Fires when someone looks at something matching the criteria.

```yaml
- id: look_at_statue
  type: catch_look
  criteria:
    - subject: "%*%"
      operator: contains
      predicate: "statue"
  script: |
    echoto %S% The statue's eyes seem to follow your gaze.
```

#### `timer_tick`

Fires periodically based on elapsed time. Useful for ambient effects and patrol behaviors.

```yaml
- id: ambient_breeze
  type: timer_tick
  flags:
    - only_when_pc_room
  criteria:
    - subject: "%time_elapsed%"
      operator: numgte
      predicate: 30
    - subject: "$random(1,100)"
      operator: numlte
      predicate: 25
  script: |
    echo A gentle breeze rustles the leaves.
```

#### `on_enter`

Fires when a character enters the room/area where the trigger is attached.

```yaml
- id: greet_on_enter
  type: on_enter
  criteria:
    - subject: "$permvar(%S%, visited_inn)"
      operator: "!="
      predicate: "true"
  script: |
    setpermvar char %S% visited_inn true
    echo The innkeeper waves as you enter.
```

#### `on_exit`

Fires when a character exits the room/area.

```yaml
- id: farewell
  type: on_exit
  script: |
    echo "Safe travels!" calls out the shopkeeper.
```

#### `on_receive`

Fires when an NPC receives an item via the `give` command.

```yaml
- id: receive_quest_item
  type: on_receive
  criteria:
    - subject: "%item_id%"
      operator: eq
      predicate: "golden_amulet"
  script: |
    echo The sage's eyes widen with recognition.
    say The Golden Amulet! You found it!
    setquestvar %S% main_quest.delivered_amulet true
```

#### `on_get`

Fires when an object is picked up.

```yaml
- id: pick_up_warning
  type: on_get
  script: |
    echoto %S% The sword feels unusually heavy in your hands.
```

#### `on_drop`

Fires when an object is dropped.

```yaml
- id: drop_reaction
  type: on_drop
  script: |
    echo The cursed ring clatters ominously on the ground.
```

#### `on_open` / `on_close`

Fire when a container or door is opened/closed.

```yaml
- id: open_chest
  type: on_open
  script: |
    echo Dust billows from the ancient chest.
```

#### `on_lock` / `on_unlock`

Fire when something is locked/unlocked.

```yaml
- id: unlock_secret
  type: on_unlock
  script: |
    echo A hidden mechanism clicks into place.
```

#### `on_use`

Fires when an object is used (optionally on a target).

```yaml
- id: use_tuning_fork
  type: on_use
  criteria:
    - subject: "%item_id%"
      operator: eq
      predicate: "arcane_tuning_fork"
  script: |
    echo The construct shudders as the frequency resonates.
    settempvar char %A% reprogrammed true
```

#### `on_attacked`

Fires when an attack is attempted against the trigger owner (NPC or character), regardless of whether it hits or misses. This allows NPCs to react to being attacked, such as calling for help, fleeing, or using special abilities.

**Variables available:**
- `%S%` - The character who was attacked (trigger owner)
- `%a%` / `%A%` - The attacker's name / reference
- `%attack_noun%` - The attack noun (e.g., "sword", "claws")
- `%attack_verb%` - The attack verb (e.g., "slashes", "bites")

```yaml
- id: call_for_help
  type: on_attacked
  criteria:
    - subject: "$random(1,100)"
      operator: numlte
      predicate: 25
  script: |
    yell Guards! I'm being attacked!
```

```yaml
- id: guard_retaliation
  type: on_attacked
  script: |
    say You dare attack me?!
    emote draws their weapon!
```

### Trigger Flags

| Flag | Description |
|------|-------------|
| `ONLY_WHEN_PC_ROOM` | Only execute if a player is in the same room |
| `ONLY_WHEN_PC_ZONE` | Only execute if a player is in the same zone |

These flags are essential for `timer_tick` triggers to prevent NPCs from acting when no players are around.

```yaml
- id: npc_idle_action
  type: timer_tick
  flags:
    - only_when_pc_room
  criteria:
    - subject: "%time_elapsed%"
      operator: numgte
      predicate: 45
  script: |
    emote straightens some merchandise.
```

---

## Script Commands

### Output Commands

| Command | Syntax | Description |
|---------|--------|-------------|
| `echo` | `echo <text>` | Display text to everyone in the room |
| `echoto` | `echoto <target> <text>` | Display text only to target |
| `echoexcept` | `echoexcept <target> <text>` | Display text to everyone except target |
| `emote` | `emote <action>` | Actor performs an emote |
| `say` | `say <text>` | Actor says something |
| `sayto` | `sayto <target> <text>` | Actor says something to a specific target |
| `tell` | `tell <target> <text>` | Send private message |

### Variable Management

| Command | Syntax | Description |
|---------|--------|-------------|
| `settempvar` | `settempvar char <target> <name> <value>` | Set temporary variable |
| `deltempvar` | `deltempvar char <target> <name>` | Delete temporary variable |
| `setpermvar` | `setpermvar char <target> <name> <value>` | Set permanent variable |
| `delpermvar` | `delpermvar char <target> <name>` | Delete permanent variable |
| `setquestvar` | `setquestvar <target> <var_id> <value>` | Set quest variable (with auto-knowledge) |

### Movement and Positioning

| Command | Syntax | Description |
|---------|--------|-------------|
| `transfer` | `transfer <target> <zone.room>` | Teleport target to a room |
| `teleport` | `teleport <who> <target>` | Teleport to room, NPC, or object |
| `walkto` | `walkto <zone.room>` | Pathfind to destination |
| `north/south/east/west/up/down` | Direction command | Move in direction |

### Combat and Effects

| Command | Syntax | Description |
|---------|--------|-------------|
| `damage` | `damage <target> <amount> <type>` | Apply damage (dice notation supported) |
| `heal` | `heal <target> <amount>` | Heal target (dice notation supported) |
| `attack` | `attack <target>` | Initiate combat |

Damage types: `SLASHING`, `PIERCING`, `BLUDGEONING`, `FIRE`, `COLD`, `LIGHTNING`, `POISON`, `ACID`, `NECROTIC`, `RADIANT`, `FORCE`, `PSYCHIC`, `DIVINE`, `NATURE`

```yaml
# Examples
damage %S% 10 fire
damage guard 2d6+5 slashing
heal %S% 3d8+10
```

### Item Management

| Command | Syntax | Description |
|---------|--------|-------------|
| `give` | `give <item> <target>` | Give item to target |
| `removeitem` | `removeitem <target> <item>` | Remove item (destroy it) |
| `spawn` | `spawn <npc_id>` | Spawn NPC from definition |
| `spawnobj` | `spawnobj <object_id>` | Spawn object from definition |

### Flow Control

| Command | Syntax | Description |
|---------|--------|-------------|
| `pause` | `pause <seconds>` | Pause script execution (max 60s) |
| `delay` | `delay <ticks> <command>` | Execute command after delay |
| `force` | `force <target> <command>` | Force target to execute command |
| `stop` | `stop` | Stop NPC's current route/action |

### Force Command with Multiple Actions

The `force` command can include semicolons to execute multiple commands:

```yaml
script: |
  force guard emote draws his sword; say Halt, intruder!; attack %S%
```

---

## Conditional Logic

Use `$if()` for branching logic in scripts.

### Syntax

```
$if(subject, operator, predicate){
  # Commands if condition is true
}
else {
  # Commands if condition is false
}
```

### Examples

```yaml
# Simple condition
$if($random(1,100), numlte, 50){
  echo The coin lands on heads.
}
else {
  echo The coin lands on tails.
}

# Check item possession
$if($hasitem(%S%, ancient_key), eq, true){
  echo The door unlocks with a click.
}
else {
  echo The door is locked. You need a key.
}

# Check quest progress
$if($questvar(%S%, murder_mystery.found_body), eq, true){
  say So you've seen the body. Terrible business.
}

# Nested conditions
$if($hasitem(%S%, imperial_diadem), eq, true){
  pause 0.5
  emote bows gracefully
  say Your Grace. Her Majesty awaits.
}
else {
  $if($hasitem(%S%, maintenance_sigil_token), eq, true){
    say Maintenance personnel. Proceed.
  }
  else {
    say Halt! You are not authorized.
  }
}
```

---

## Operators

### Comparison Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `eq` | String equality | `"hello" eq "hello"` |
| `neq` or `!=` | String inequality | `"a" != "b"` |
| `numeq` | Numeric equality | `5 numeq 5` |
| `numneq` | Numeric inequality | `5 numneq 3` |
| `numgt` | Greater than | `10 numgt 5` |
| `numlt` | Less than | `3 numlt 10` |
| `numgte` | Greater than or equal | `5 numgte 5` |
| `numlte` | Less than or equal | `5 numlte 10` |
| `between` | Value in range | `5 between 1,10` (middle value is tested) |
| `contains` | String contains with pattern grammar (case-insensitive) | `"hello world" contains "hello"` |
| `matches` | Regex match | `"test123" matches "test\d+"` |
| `true` | Always true | Used for catch-all triggers |
| `false` | Always false | Used to disable triggers |

### Criteria Examples

```yaml
# Check for keyword in message
criteria:
  - subject: "%*%"
    operator: contains
    predicate: "hello"

# Timer check
criteria:
  - subject: "%time_elapsed%"
    operator: numgte
    predicate: 30

# Random chance (25%)
criteria:
  - subject: "$random(1,100)"
    operator: numlte
    predicate: 25

# Check variable
criteria:
  - subject: "$permvar(%S%, visited_before)"
    operator: "!="
    predicate: "true"

# Check quest state
criteria:
  - subject: "$questvar(%S%, murder_mystery.found_body)"
    operator: eq
    predicate: "true"

# Always trigger
criteria:
  - subject: ""
    operator: true
    predicate: ""
```

### Text Pattern Matching Grammar (contains operator)

The `contains` operator supports a powerful pattern matching grammar using grouping and alternation:

#### Basic Syntax

| Pattern | Description | Example |
|---------|-------------|---------|
| `word` | Simple substring match | `"hello"` matches text containing "hello" |
| `(a\|b\|c)` | Match any alternative (OR) | `"(travel\|guide)"` matches "travel" OR "guide" |
| `a\|b\|c` | Same as above, parens optional | `"travel\|guide"` matches "travel" OR "guide" |
| `pattern1 pattern2` | All patterns must match (AND) | `"cave dark"` requires both "cave" AND "dark" |

#### Pattern Examples

```yaml
# Match any of several keywords
criteria:
  - subject: "%*%"
    operator: contains
    predicate: "(travel|guide|directions)"

# Match multiple conditions (AND logic)
# Must mention travel/guide AND oasis/water
criteria:
  - subject: "%*%"
    operator: contains
    predicate: "(travel|guide) (oasis|fresh water)"

# Mix plain words with groups
criteria:
  - subject: "%*%"
    operator: contains
    predicate: "cave (dark|dim|shadowy)"

# Multi-word alternatives
criteria:
  - subject: "%*%"
    operator: contains
    predicate: "(fresh water|clean water|drinking water)"

# Complex pattern: asking for directions to a location
criteria:
  - subject: "%*%"
    operator: contains
    predicate: "(tell|show|guide) (way|path|route) (village|town|city)"
```

#### How It Works

1. **Groups `(a|b|c)`**: At least ONE alternative must be found in the text (OR logic)
2. **Multiple patterns**: ALL patterns must match (AND logic)
3. **Case-insensitive**: All matching is case-insensitive
4. **Backward compatible**: Simple patterns without `()` or `|` work exactly as before

#### Real-World Example

```yaml
# NPC guide responds to travel requests
- id: guide_travel_request
  type: catch_say
  criteria:
    - subject: "%*%"
      operator: contains
      predicate: "(travel|guide|take|lead) (oasis|water|spring|well)"
  script: |
    sayto %S% Ah, you seek water! I can guide you to the hidden oasis.
    sayto %S% It will cost you 10 gold coins. Say 'agree' if you accept.
```

This trigger fires when someone says something like:
- "Can you guide me to the oasis?"
- "I need to travel to find water"
- "Please lead me to the spring"
- "Take me to the well"

But NOT for:
- "Where is the oasis?" (missing travel/guide/take/lead)
- "Can you guide me to the city?" (missing oasis/water/spring/well)

---

## Quest Variables

Quest variables are a special system that combines permanent variables with automatic world knowledge updates.

### Setting Quest Variables

```yaml
setquestvar %S% murder_mystery.found_body true
```

### Variable ID Formats

- **Local** (2 parts): `murder_mystery.found_body` - uses target's current zone
- **Full** (3 parts): `gloomy_graveyard.murder_mystery.found_body`

### Checking Quest Variables

```yaml
$if($questvar(%S%, murder_mystery.found_body), eq, true){
  say I heard you found the body.
}
```

### Defining Quest Variables (Zone YAML)

Quest variables can be defined with automatic knowledge updates:

```yaml
quest_variables:
  murder_mystery:
    found_body:
      description: "Player has discovered Lord Ashford's body"
      type: boolean
      default: false
      knowledge_updates:
        - condition: true
          updates:
            murder_case: >
              You discovered Lord Ashford's body in the graveyard.
              The gravedigger Old Tom is the prime suspect.
```

When `murder_mystery.found_body` is set to `true`, the `murder_case` world knowledge is automatically updated for that player.

---

## Game Commands Reference

A complete list of all available game commands.

### Communication Commands

| Command | Syntax | Description |
|---------|--------|-------------|
| `say` | `say <message>` | Speak aloud to everyone in the room |
| `sayto` | `sayto <target> <message>` | Speak directly to a specific character |
| `ask` | `ask <target> <question>` | Ask a character a question |
| `tell` | `tell <target> <message>` | Send a private message to anyone in the world |
| `whisper` | `whisper <target> <message>` | Whisper to someone in the same room |
| `emote` | `emote <action>` | Perform a custom emote/action |

### Movement Commands

| Command | Syntax | Description |
|---------|--------|-------------|
| `north` / `n` | `north` | Move north |
| `south` / `s` | `south` | Move south |
| `east` / `e` | `east` | Move east |
| `west` / `w` | `west` | Move west |
| `up` / `u` | `up` | Move up |
| `down` / `d` | `down` | Move down |
| `in` | `in` | Enter a location |
| `out` | `out` | Exit a location |
| `flee` | `flee` | Attempt to flee from combat in a random direction |

### Looking & Information Commands

| Command | Syntax | Description |
|---------|--------|-------------|
| `look` / `l` | `look [target]` | Look at the room or a specific target |
| `examine` / `ex` | `examine <target>` | Examine something closely (same as look) |
| `inspect` | `inspect <target>` | Get detailed information about an item or character |
| `inventory` / `inv` / `i` | `inventory` | List items in your inventory |
| `character` / `char` | `character` | Display your character sheet |
| `skills` | `skills` | Display your skills and abilities |
| `level` | `level` | Show level and experience information |
| `triggers` | `triggers` | Show active triggers on your character |

### Item Commands

| Command | Syntax | Description |
|---------|--------|-------------|
| `get` / `take` | `get <item> [from container]` | Pick up an item |
| `drop` | `drop <item>` | Drop an item from inventory |
| `put` | `put <item> in <container>` | Place an item in a container |
| `give` | `give <item> to <target>` | Give an item to a character |
| `equip` / `eq` | `equip <item>` | Equip an item (or show equipped items) |
| `unequip` | `unequip <item>` | Remove an equipped item |

### Object Interaction Commands

| Command | Syntax | Description |
|---------|--------|-------------|
| `open` | `open <target>` | Open a door or container |
| `close` | `close <target>` | Close a door or container |
| `lock` | `lock <target>` | Lock a door or container |
| `unlock` | `unlock <target>` | Unlock a door or container |
| `use` | `use <item> [on target]` | Use an item or device |

### Consumable Commands

| Command | Syntax | Description |
|---------|--------|-------------|
| `quaff` | `quaff <potion>` | Drink a potion |
| `drink` | `drink <liquid>` | Drink a beverage |
| `eat` | `eat <food>` | Eat a food item |
| `apply` | `apply <item> [to target]` | Apply an item (salve, bandage, etc.) |

### Combat Commands

| Command | Syntax | Description |
|---------|--------|-------------|
| `attack` / `kill` | `attack <target>` | Attack a target to initiate combat |
| `flee` | `flee` | Attempt to escape from combat |

### Position Commands

| Command | Syntax | Description |
|---------|--------|-------------|
| `stand` | `stand` | Stand up |
| `sit` | `sit` | Sit down (faster HP/resource regeneration) |
| `sleep` | `sleep` | Go to sleep (fastest HP regeneration) |
| `meditate` / `med` | `meditate` | Enter meditation (fastest mana regeneration) |

### Character Progression Commands

| Command | Syntax | Description |
|---------|--------|-------------|
| `levelup` | `levelup` | Level up when you have enough experience |
| `skillup` | `skillup <skill>` | Spend skill points to improve a skill |

### Session Commands

| Command | Syntax | Description |
|---------|--------|-------------|
| `quit` / `logout` | `quit` | Log out and save your character |
| `savegame` | `savegame` | Manually save your character |

### Script-Only Commands (Privileged)

These commands are only available in scripts, not for players:

| Command | Syntax | Description |
|---------|--------|-------------|
| `echo` | `echo <text>` | Display text to everyone in the room |
| `echoto` | `echoto <target> <text>` | Display text only to a specific character |
| `echoexcept` | `echoexcept <target> <text>` | Display text to everyone except target |
| `settempvar` | `settempvar char <target> <name> <value>` | Set a temporary variable |
| `deltempvar` | `deltempvar char <target> <name>` | Delete a temporary variable |
| `setpermvar` | `setpermvar char <target> <name> <value>` | Set a permanent variable |
| `delpermvar` | `delpermvar char <target> <name>` | Delete a permanent variable |
| `setquestvar` | `setquestvar <target> <var_id> <value>` | Set a quest variable with auto-knowledge |
| `getquestvar` | `getquestvar <target> <var_id>` | Get a quest variable value |
| `spawn` | `spawn <npc_id>` | Spawn an NPC from a zone definition |
| `spawnobj` | `spawnobj <object_id>` | Spawn an object from a zone definition |
| `damage` | `damage <target> <amount> <type>` | Apply damage (supports dice notation) |
| `heal` | `heal <target> <amount>` | Heal a target (supports dice notation) |
| `removeitem` | `removeitem <target> <item>` | Remove and destroy an item |
| `transfer` | `transfer <target> <zone.room>` | Teleport a character to a room |
| `teleport` | `teleport <who> <target>` | Teleport to a room, NPC, or object location |
| `force` | `force <target> <command>` | Force a character to execute a command |
| `pause` | `pause <seconds>` | Pause script execution (max 60s) |
| `delay` | `delay <ticks> <command>` | Schedule a command after a delay |
| `stop` | `stop` | Stop an NPC's current route/behavior |
| `walkto` | `walkto <zone.room>` | Pathfind to a destination |
| `interrupt` | `interrupt <target>` | Interrupt a character's current action |

### Emote Commands

Built-in social emotes that can optionally target another character:

`bow`, `cheer`, `clap`, `congratulate`, `cry`, `dance`, `frown`, `gaze`, `glare`, `kick`, `kiss`, `laugh`, `lick`, `nod`, `shrug`, `sigh`, `sing`, `smile`, `thank`, `think`, `touch`, `wave`, `wink`, `yawn`

---

Here is a drop-in Markdown section for your `scripting-guide.md` or `world-building-guide.md`. It documents the two-layer prompt architecture we developed.

---

## LLM NPC Prompt Architecture

To ensure consistent gameplay behavior while maintaining unique character voices, NextGenMUD uses a **Two-Layer Prompt System**.

1. **The Base System Prompt:** Global instructions that enforce game mechanics (formatting, command teaching, and gating).
2. **The Character Profile:** The specific lore and logic defined in your zone YAML files.

The system concatenates these two text blocks before sending the context to the LLM: `Full Prompt = Base System Prompt + Character Profile`.

### 1. The Base System Prompt

*This text is hard-coded globally. You do not need to repeat it in individual NPC files. It ensures NPCs stop acting like AI assistants and start acting like game interfaces.*

```text
[SYSTEM: MUD_NPC_PROTOCOL_V1]
You are a character in a text-based Multiplayer Dungeon (MUD). Your goal is to provide immersive roleplay while guiding the player toward gameplay content.

1. FORMATTING PROTOCOLS (Default):
   - Output must be RAW TEXT only. 
   - Do NOT use Markdown (no **bold**, *italics*, or bulleted lists).
   - Keep responses conversational and natural. Avoid robotic lists.
   - **EXCEPTION:** If your specific Character Profile instructs you to use a specific format (like poetry, lists, or ancient runes), you may override these formatting rules.

2. CONVERSATIONAL LOGIC:
   - Do not offer a "menu" of options (e.g., "I can tell you about A, B, or C"). Instead, weave keywords into observation.
   - **The "Flavor-to-Location" Rule:** If you mention a flavor element (e.g., wind, smell, sound), you must immediately link it to a specific Location or Game Mechanic (e.g., "The wind smells of rot... coming from the Barracks.").

3. ACTION HANDOFF:
   - You cannot physically move the player or execute code yourself.
   - If the player agrees to an action (like traveling), you must explicitly tell them the **Command Phrase** to use.
   - Example: "If you are ready to die, tell me to 'open the gate'."

4. HIERARCHY OF INSTRUCTION:
   - The specific [CHARACTER PROFILE] provided below is your primary truth. 
   - If the Character Profile contradicts these System Instructions (e.g., a character who speaks in verse or uses Markdown for emphasis), **follow the Character Profile.**

[CHARACTER PROFILE STARTS HERE]

```

### 2. The Character Profile (YAML)

*This is the `personality` field in your Zone YAML. Focus purely on Lore and Directive Logic.*

Use the **Directive Format** to structure how the NPC manages information flow.

#### Structure

* **[DIRECTIVE: INITIAL GREETING]**: What specific keywords or services must be mentioned in the first sentence?
* **[DIRECTIVE: TOPIC LINKING]**: Logic trees. "If Player asks X, mention Location Y."
* **[DIRECTIVE: CLOSING/ACTION]**: The specific phrase the player must say to trigger a `catch_say` script.

#### Example: The Wind-Marked Guide

```yaml
llm_conversation:
  personality: |
    You are a mercenary guide. You are gritty, impatient, and transactional.
    
    [DIRECTIVE: INITIAL GREETING]
    State clearly that you know the Routes, understand the Dangers, and work for Coin.
    
    [DIRECTIVE: TOPIC LINKING]
    - If asked about Dangers (Spirits, Heat, Glass), tell them which Location contains that danger.
    - If asked about Routes, describe the Oasis (water), Barracks (soldiers), or Expanse (crater).
    
    [DIRECTIVE: CLOSING]
    If they seem interested in a location, tell them the specific command to give you: 
    "If you want to go, just tell me to 'lead you to the [Location]'."

```

### Best Practices

1. **No Markdown Instructions:** Do not tell individual NPCs "Don't use bold." The Base Prompt handles this.
2. **Teach the Trigger:** If you have a `catch_say` trigger for `"travel to oasis"`, the LLM must instruct the player to say exactly that.
* *Bad:* "I can take you there." (Player says "Okay", nothing happens).
* *Good:* "Tell me to 'travel to the oasis' and we will leave." (Player repeats phrase, script fires).


3. **Link Fluff to Mechanics:** Never let an NPC complain about a problem (e.g., "The spirits are restless") without linking it to a place the player can visit (e.g., "...in the Salt-Choked Barracks").

---

## Examples

### NPC Shopkeeper

```yaml
characters:
  - id: shopkeeper
    name: shopkeeper
    article: the
    description: A friendly merchant with a warm smile.
    triggers:
      - id: greet_customer
        type: catch_say
        criteria:
          - subject: "%*%"
            operator: contains
            predicate: "hello"
        script: |
          sayto %S% Welcome, welcome! Take a look at my wares.
      
      - id: idle_behavior
        type: timer_tick
        flags:
          - only_when_pc_room
        criteria:
          - subject: "%time_elapsed%"
            operator: numgte
            predicate: 60
          - subject: "$random(1,100)"
            operator: numlte
            predicate: 30
        script: |
          emote polishes a trinket behind the counter.
```

### Room with Atmospheric Effects

```yaml
rooms:
  haunted_chamber:
    name: Haunted Chamber
    description: An eerie room with flickering torches.
    triggers:
      - id: ambient_cold
        type: timer_tick
        flags:
          - only_when_pc_room
        criteria:
          - subject: "%time_elapsed%"
            operator: numgte
            predicate: 20
        script: |
          echo A supernatural cold passes through the room.
      
      - id: first_visit
        type: on_enter
        criteria:
          - subject: "$permvar(%S%, visited_haunted_chamber)"
            operator: "!="
            predicate: "true"
        script: |
          setpermvar char %S% visited_haunted_chamber true
          pause 0.5
          echo As you enter, the temperature drops sharply.
          echo You feel as though you're being watched...
```

### Quest Item Interaction

```yaml
characters:
  - id: quest_giver
    name: Elder Sage
    triggers:
      - id: receive_amulet
        type: on_receive
        criteria:
          - subject: "%item_id%"
            operator: eq
            predicate: "golden_amulet"
        script: |
          pause 0.5
          echo The Elder Sage examines the amulet, eyes widening.
          say By the gods... you've actually found it!
          setquestvar %S% main_quest.delivered_amulet true
          removeitem me golden_amulet
          spawn quest_reward_chest
          
      - id: receive_junk
        type: on_receive
        criteria:
          - subject: "%item_id%"
            operator: "!="
            predicate: "golden_amulet"
        script: |
          say Thank you, but this isn't what I seek.
          give %item_id% %S%
```

### Conditional NPC Behavior

```yaml
- id: guard_challenge
  type: on_enter
  script: |
    $if($hasitem(%S%, royal_signet), eq, true){
      pause 0.3
      emote snaps to attention
      say Your Lordship! Please, proceed.
    }
    else {
      $if($questvar(%S%, palace.has_permission), eq, true){
        pause 0.3
        say You may pass. The Captain vouched for you.
      }
      else {
        pause 0.3
        emote steps forward, hand on sword
        say Halt! State your business.
      }
    }
```

### Combat Trigger

```yaml
- id: trap_trigger
  type: on_enter
  criteria:
    - subject: "$permvar(%S%, trap_disarmed)"
      operator: "!="
      predicate: "true"
  script: |
    echo A hidden pressure plate clicks beneath your feet!
    pause 0.3
    echo Poison darts shoot from the walls!
    damage %S% 2d6+4 poison
```

---

## Best Practices

### 1. Use Specific Trigger IDs

Always give triggers unique, descriptive IDs:

```yaml
# Good
- id: shopkeeper_greet_first_time
- id: shopkeeper_idle_organize_goods

# Bad
- id: trigger1
- id: a
```

### 2. Use `only_when_pc_room` for Timer Triggers

Prevents NPCs from acting when no players are present:

```yaml
- id: npc_patrol
  type: timer_tick
  flags:
    - only_when_pc_room  # Essential!
  criteria:
    - subject: "%time_elapsed%"
      operator: numgte
      predicate: 30
```

### 3. Clean Up Temporary Variables

Don't leave unnecessary temp vars around:

```yaml
script: |
  settempvar char %S% quest_step 1
  # ... later when done ...
  deltempvar char %S% quest_step
```

### 4. Use Quest Variables for Important State

For any story/quest progression, use quest variables:

```yaml
# Instead of:
setpermvar char %S% found_the_key true

# Use:
setquestvar %S% dungeon_quest.found_key true
```

### 5. Add Pauses for Dramatic Effect

Brief pauses make scripts feel more natural:

```yaml
script: |
  pause 0.5
  echo The door slowly creaks open...
  pause 1
  echo Revealing a chamber filled with treasure!
```

### 6. Use Multiple Criteria for Precision

Combine criteria to be specific:

```yaml
criteria:
  - subject: "%time_elapsed%"
    operator: numgte
    predicate: 60
  - subject: "$random(1,100)"
    operator: numlte
    predicate: 25
  - subject: "$questvar(%S%, quest.is_active)"
    operator: eq
    predicate: "true"
```

### 7. Handle Edge Cases

Consider what happens if conditions aren't met:

```yaml
- id: npc_receive_wrong_item
  type: on_receive
  criteria:
    - subject: "%item_id%"
      operator: "!="
      predicate: "expected_item"
  script: |
    say I don't think I need this...
    give %item_id% %S%
```

---

## Troubleshooting

### Common Issues

#### Trigger Not Firing

1. **Check criteria specificity**: Use `contains` for partial matches
2. **Verify variable names**: Case matters! `%s%` ≠ `%S%`
3. **Check timer values**: `%time_elapsed%` is in seconds
4. **Verify flags**: For `timer_tick`, is a PC actually in range?

#### Variable Not Substituting

1. **Check syntax**: Variables need `%` on both sides: `%variable%`
2. **Verify variable exists**: Undefined variables stay as-is
3. **Check context**: Some variables only exist in certain trigger types

#### Function Returns Wrong Value

1. **Check argument types**: Most numeric functions need numbers
2. **Verify target references**: Use `%S%` not `%s%` for targeting
3. **Check return format**: Functions return strings ("true"/"false")

#### Script Executing Partially

1. **Check for syntax errors**: Unmatched braces break `$if()` blocks
2. **Look for errors in log**: Enable debug logging
3. **Test individual commands**: Simplify to find the problem

### Debugging Tips

1. Use `echo` to output variable values during testing
2. Start with simple criteria and add complexity gradually
3. Test triggers in isolation before combining
4. Check the server log for error messages
5. Use the `triggers` command in-game to see active triggers

### Reference Symbol

The reference symbol `|` is used for entity targeting. When you see `|C507`, this means:
- `|` = reference prefix
- `C` = character type (could also be `O` for object, `R` for room)
- `507` = unique reference number

Always use `%S%`, `%A%`, `%T%` to get proper references for commands.

---

## Quick Reference

### Essential Variable Patterns

```yaml
# Echo to triggering player
echoto %S% You hear a whisper...

# Echo to room except triggering player  
echoexcept %S% $cap(%s%) looks around nervously.

# Set variable on triggering player
setpermvar char %S% has_visited true

# Check if player has item
$if($hasitem(%S%, key), eq, true){ ... }

# Random chance
$if($random(1,100), numlte, 25){ ... }

# Quest progress
setquestvar %S% quest_name.step_id true
$if($questvar(%S%, quest_name.step_id), eq, true){ ... }
```

### Common Trigger Templates

```yaml
# First-time visitor greeting
- id: first_visit
  type: on_enter
  criteria:
    - subject: "$permvar(%S%, visited_location)"
      operator: "!="
      predicate: "true"
  script: |
    setpermvar char %S% visited_location true
    echo Welcome message here...

# Random ambient effect
- id: ambient_effect
  type: timer_tick
  flags:
    - only_when_pc_room
  criteria:
    - subject: "%time_elapsed%"
      operator: numgte
      predicate: 30
    - subject: "$random(1,100)"
      operator: numlte
      predicate: 20
  script: |
    echo Atmospheric description here...

# Respond to keywords
- id: keyword_response
  type: catch_say
  criteria:
    - subject: "%*%"
      operator: contains
      predicate: "keyword"
  script: |
    sayto %S% Response to keyword...
```
