# NextGenMUD Scripting System

## Overview

The NextGenMUD scripting system provides a powerful way to add dynamic behavior to NPCs, rooms, and objects in your game world. Through a combination of triggers and scripts, you can create responsive environments that react to player actions, timed events, and other game conditions.

## Core Concepts

### Triggers

Triggers are the foundation of the scripting system. They define when a script should execute based on specific events or conditions. Each trigger consists of:

1. **Type**: Defines what kind of event activates the trigger
2. **Criteria**: One or more conditions that must be met for the trigger to fire
3. **Script**: The code that runs when the trigger is activated

### Script Execution

When a trigger's criteria are met, the associated script is executed by the ScriptHandler, which processes the script line by line. Scripts can:

- Perform game actions
- Modify variables
- Make conditional decisions with if/else blocks
- Use built-in functions for various operations

### Variables

Scripts can access and manipulate various variables:

- **System Variables**: Pre-defined variables that provide information about the current context
- **Temporary Variables**: Short-term storage for values during script execution
- **Permanent Variables**: Long-term storage for persistent data

### Definition `perm_variables` (YAML)

You can define persistent variables directly in character, object, and room YAML definitions.
These are copied into the instance's `perm_variables` when the world is loaded / instantiated.

```yaml
# Character / NPC definition
perm_variables:
  faction: city_watch
  greeting_count: 0

# Object definition
perm_variables:
  inspected: false
  owner_tag: vault_master

# Room definition
perm_variables:
  alarm_state: idle
  shrine_blessed: true
```

## Trigger Types

NextGenMUD supports the following trigger types:

### `on_see`

Fires when the room sees text that matches the criteria (e.g. when someone arrives, says something, or performs an action that produces room output).

```yaml
- type: on_see
  criteria: 
    - subject: "%*%"
      operator: contains
      predicate: "arrives."
  script: |
    echoto %S% You trip as you enter.
    echoexcept %S% $cap(%s%) trips as %q% enters.
```

### `on_say`

Fires when someone uses **say** in the room — i.e. speech that the whole room (and everyone in it) hears. Use on **rooms** or **characters** in the room. The said text is in `%*%`; `%s%`/`%S%` is the speaker.

```yaml
- type: on_say
  criteria: 
    - subject: "%*%"
      operator: contains
      predicate: "hello"
  script: |
    emote waves hello in return.
```

### `on_tell`

Fires when someone **directs speech at this actor** via **sayto**, **tell**, **whisper**, or **ask** — i.e. only when the player explicitly targets this NPC. Does **not** fire on plain **say** (room speech); use `on_say` for that.

Use on **characters** (NPCs) that should react only when spoken to directly. Variables: **%s%/%S%** = the speaker (who said to you), **%a%/%A%** = this actor (the recipient), **%*%** = the text that was said.

```yaml
- type: on_tell
  criteria:
    - subject: "%*%"
      operator: contains
      predicate: "hello,hi,hey"
  script: |
    sayto %S% Hello to you too, traveler.
```

### `on_use`

Fires when a character **uses**, **drinks**, or **reads** the object (e.g. potions, scrolls, keys). Use on **objects** that have a use/drink/read effect.

**Variable semantics:** **Actor** = trigger owner (the item); **subject** = the character using the item (initiator); **target** = the thing acted upon (the item when using or reading without "on X", or the specified target when "use X on Y"). So for **read scroll**: actor = scroll, subject = player, target = scroll. Use `%S%` to target the player in scripts (e.g. `applystate %S% experiencemodifier 3600 100`).

**Extra variables:** `%use_type%` = the command that fired the trigger: `"use"`, `"drink"`, or `"read"`. When the command was "use X on Y", `%target%` and `%target_id%` are the target's name and id.

```yaml
- type: on_use
  criteria: []
  script: |
    echo A halo of light surrounds your head.
    applystate %S% experiencemodifier 3600 100
```

### `on_look`

**Replaces** the normal description when present. Use on **rooms**, **objects**, or **characters**. When a player looks at the room (plain `look`) or looks at that object/character, the default description is **not** shown; instead this trigger’s script runs. The script should echo the appropriate description (e.g. with `echoto %S% ...`). This allows descriptions to vary by var state.

```yaml
# Room: dynamic description based on var
- type: on_look
  script: |
    $if($permvar(zone,gate_open), eq, 1){
      echoto %S% The gate stands open. Beyond lies the road north.
    }{
      echoto %S% A heavy iron gate blocks the way. It is closed.
    }
# Object: script provides the only description
- type: on_look
  script: |
    echoto %S% The mirror shows your reflection, but its surface ripples oddly.
```

### `catch_inspect`

Fires **in addition to** the normal description when someone looks at something matching the criteria. Use when you want the default description plus extra flavor (e.g. “The statue seems to watch you”). The look keyword is in `%*%`.

```yaml
- type: catch_inspect
  criteria: 
    - subject: "%*%"
      operator: contains
      predicate: "statue"
  script: |
    echoto %S% The statue seems to watch you with its stone eyes.
```

### `timer_tick`

Executes periodically based on time elapsed.

```yaml
- type: timer_tick
  criteria:
    - subject: "%time_elapsed%"
      operator: "numgte"
      predicate: 60
  script: |
    emote shifts slightly.
```

### `on_arrive`

Fires when **someone arrives** at the room, NPC, or object where this trigger is attached. From the room’s perspective: someone else arrives. Use on **rooms**, **NPCs**, or **objects**. The arriving character is `%S%` / `%s%`; the script runs as the room/NPC/object.

```yaml
# On a room: greet anyone who arrives
- type: on_arrive
  script: |
    echoto %S% A cool draft washes over you as you step inside.
# On an NPC: greet the arriving player
- type: on_arrive
  script: |
    sayto %S% Welcome, traveler. Have a look at my wares.
```

### `on_enter`

Fires when **this actor enters** a room (by any means: walking, teleport, etc.). Use on **characters** (e.g. PCs). From the mover’s perspective: I enter. Variables: `%room_id%` is the full id of the room just entered (`zone_id.subzone_id.room_id` or `zone_id.room_id`); `%S%` / `%s%` are this actor. **No criteria** = fires on every room entry. **With criteria** you can restrict by room: e.g. subject `%room_id%`, operator `contains`, predicate `sunken_citadel` (zone), `sunken_citadel.depths` (subzone), or the full room id.

```yaml
# On a character: every room
- type: on_enter
  script: |
    emote glances around.
# Only when entering a specific zone
- type: on_enter
  criteria:
    - subject: "%room_id%"
      operator: contains
      predicate: "sunken_citadel"
  script: |
    echoto %S% The pressure of the deep weighs on you.
```

### `catch_zerohp`

Fires when **damage** reduces this actor's HP to 0 or less. The script runs before death is applied. If the script sets this actor's HP above 0 (e.g. via `setstat %A% hp 5` or a heal), **death is cancelled** and the actor is treated as still alive (combat continues, no corpse, no room/state changes). If HP is still 0 or less when the script finishes, normal death proceeds.

Use on **characters** (e.g. for "second wind", divine intervention, or one-time survival). Variables: **%a%/%A%** = this actor (script owner, the one who hit 0 HP), **%s%/%S%** = the actor who did the damage, **%t%/%T%** = this actor (same as a/A).

```yaml
# One-time survival when reduced to 0 HP (e.g. second wind)
- type: catch_zerohp
  script: |
    setstat %A% hp 5
    echo $cap(%a%) gasps and staggers back to %q% feet!

```

### `catch_command`

Fires when the **player types a command** whose first word is in this trigger's comma-separated list of command words. Use on **rooms**, **objects**, **characters**, or **inventory items** to intercept commands before normal handling.

**Check order:** The command handler looks for matching `catch_command` triggers in this order: (1) the current room, (2) objects in the room, (3) NPCs/characters in the room, (4) each character's top-level inventory (items inside containers are not checked). The first trigger that matches and runs **stops** command processing; no normal command or "Unknown command" runs.

**Criteria:** Use one criterion with **subject** `%*%`, **operator** `oneof`, and **predicate** a comma-separated list of command words (e.g. `get,take,grab`). The command word is compared case-insensitively.

**Variables:** `%text%` = the **complete** command input (including the command word and any arguments). `%*%` is also set to the full input. Actor/subject is the player who typed the command.

```yaml
# On a room: intercept "rub" / "polish" before default handling
- type: catch_command
  id: altar_rub
  criteria:
    - subject: "%*%"
      operator: oneof
      predicate: "rub,polish,shine"
  script: |
    echoto %S% You rub the altar; it warms beneath your hand.
    echoexcept %S% $cap(%s%) rubs the altar thoughtfully.
```

### `on_signal`

Fires when a **signal** is sent to this receiver's scope (room, subzone, zone, or world). The **signal** command sends to all registered `on_signal` triggers whose location matches the scope. Use on **rooms**, **characters**, or **objects** that should react to signals.

**Variables:** **actor** = trigger owner (this receiver): `%a%`/`%A%`; **subject** = who ran the signal command: `%s%`/`%S%`, `%p%`/`%P%`; **target** = the third argument of the signal command (usually a reference): `%t%`/`%T%`, `%r%`/`%R%`; `%signal%` = the signal name; `%text%` = the message (fourth and later words).

**Criteria:** Use subject `%signal%` with operator `eq` and predicate the signal name to only fire for that signal (e.g. `subject: "%signal%"`, `operator: "eq"`, `predicate: "alarm"`). No criteria = fires for any signal in scope.

**Registry:** When the trigger is **enabled** it registers in a global list; when **disabled** it unregisters. Invalid receivers (e.g. dead, no location, dereferenced) are **automatically pruned** when signals are sent—creators do not need to manually deregister in `catch_zerohp`. Use **deregistersignals** only when you want an actor to stay in the world but stop receiving signals ("deaf").

```yaml
# React only to "alarm" signals in this zone
- type: on_signal
  criteria:
    - subject: "%signal%"
      operator: eq
      predicate: "alarm"
  script: |
    echo A distant alarm echoes through the area. %text%
```

## Trigger Criteria

Each trigger contains one or more criteria that determine when it should activate. Criteria have three components:

1. **Subject**: The value to be evaluated
2. **Operator**: How to compare the subject and predicate
3. **Predicate**: The value to compare against

### Available Operators

- `eq` / `numeq` - Equal to (string / numeric)
- `neq` / `numneq` - Not equal to (string / numeric)
- `gt` / `numgt` - Greater than (numeric)
- `lt` / `numlt` - Less than (numeric)
- `gte` / `numgte` - Greater than or equal to (numeric)
- `lte` / `numlte` - Less than or equal to (numeric)
- `between` - Numerically between two values
- `contains` - Subject string contains the predicate. If the **predicate is a comma-separated list** (e.g. `"xp,scroll,learning"`), the condition is true if the subject contains **any** of those words (case-insensitive). Useful for activation-word lists on `on_say` and `on_tell` triggers.
- `oneof` - Subject (single value) equals one of the comma-separated list in the predicate (e.g. subject `%*%`, predicate `"get,take,grab"`). Case-insensitive. Used by `catch_command` for command-word lists.
- `matches` - Regular expression match
- `true` - Always true
- `false` - Always false

> **Note:** The shorthand aliases (`gt`, `lt`, `gte`, `lte`, `eq`, `neq`) are used interchangeably with the `num`-prefixed forms throughout both standard scripts and the Quest Engine's YAML condition blocks.

### Special Variables in Criteria

- `%*%` - The current message or event text (e.g. said text for `on_say` / `on_tell`, command input for `catch_command`, keyword for `catch_inspect`)
- `%time_elapsed%` - Time elapsed since the last trigger execution (for timer_tick triggers)
- `%room_id%` - Full id of the room being entered (for `on_enter` triggers); use with `contains` to match zone, subzone, or full room id
- `%signal%` - The signal name (for `on_signal` triggers); use with `eq` to match a specific signal

For **on_tell** triggers only: **%s%/%S%** is the **speaker** (who said to you), **%a%/%A%** is **this actor** (the recipient). Use **%S%** in scripts to target the speaker (e.g. `give item %S%`).

## Script Commands

Scripts can use a variety of commands to create dynamic behaviors:

### Basic Output Commands

- `echo [text]` - Display a message to everyone in the room
- `echoto [character] [text]` - Display a message only to the specified character
- `echoexcept [character] [text]` - Display a message to everyone except the specified character
- `emote [text]` - Perform an emote action

### Variable Management

- `settempvar [target_type] [target] [var_name] [value]` - Set a temporary variable
- `deltempvar [target_type] [target] [var_name]` - Delete a temporary variable
- `setpermvar [target_type] [target] [var_name] [value]` - Set a permanent variable
- `delpermvar [target_type] [target] [var_name]` - Delete a permanent variable

Where:
- `target_type` can be: char, obj, room, or zone
- `target` is the reference to the target (name, ID, or reference symbol)

#### Quest Variables

- `setquestvar [target] [variable_path] [value]` - Set a quest variable and trigger Quest Engine evaluation

**Syntax:** `setquestvar <target> <variable_path> <value>`

- **`<target>`**: Usually `%s%` (the triggering player) or `me`.
- **`<variable_path>`**: Uses dot-notation to scope the variable to a specific quest:
  - *Short form:* `quest_id.var_name` — assumes the current zone.
  - *Long form:* `zone_id.quest_id.var_name` — fully qualified cross-zone reference.
- **`<value>`**: `true`, `false`, an integer, or a string.

> **Important:** `setquestvar` is distinct from `setpermvar`. When `setquestvar` is used and the variable is defined in the Quest YAML schema, it **automatically triggers stateless Quest Engine re-evaluation** and **updates NPC "World Knowledge" prompts** for any LLM-driven NPCs that have `knowledge_updates` configured for that variable. Standard `setpermvar` calls do **not** produce these side effects.

**Example:**
```
setquestvar %s% murder_mystery.found_body true
```

**Variable scoping reminder:** Quest variables are distinguished from plain permanent variables by their dot-notation path. A variable named `found_body` stored via `setpermvar` has no relation to `murder_mystery.found_body` set via `setquestvar`.

### Game Actions

- `say [text]` - Make the actor say something
- `tell [character] [text]` - Send a private message
- `sayto [character] [text]` - Say something to a specific character (directed speech; triggers `on_tell` on that character)
- `move [direction]` - Move in a direction
- `damage <target(s)> <amount> <damage_type>` - Deal damage to one or more targets (see **damage command** below)
- `heal <target(s)> <amount>` - Heal one or more targets (see **heal command** below)
- `attack [character]` - Attack a character
- `give [item] [target]` - Give an item to a character or to a room (see **Give command** below)
- `spawnobj [target] [object_id]` - Create an instance of an object and put it somewhere (see **spawnobj** below)
- `spawn here [zone.char_id]` - Spawn a character in the current room (see **spawn command** below)
- `applystate [target] [state_name] [duration_seconds] [state args...]` - Apply a timed state to a target (see **applystate** below)
- `setstat [target] [stat] [value]` - Set or adjust a character stat (see **setstat command** below)
- `transfer [target] [zone.room_id]` - Teleport an actor to a room (see **transfer command** below)
- `force [target] [command]` - Force an actor to execute a command as if they typed it (see **force command** below)
- `leaverandom` - Trigger owner leaves through a random available exit
- `pause [seconds]` - Pause script execution for the given number of seconds before continuing
- `signal [scope] [signal_name] [target] [message...]` - Send a signal to on_signal receivers (see **Signal command** below)
- `deregistersignals [target]` - Disable all on_signal triggers for the target (default: me), so that actor no longer receives signals until re-enabled. Optional; invalid receivers (dead, no location, etc.) are pruned automatically. Target can be a reference (e.g. `@C123`).
- `get [object]` - Pick up an object
- `drop [object]` - Drop an object

#### spawnobj command

**Syntax:** `spawnobj <target> <object_id>`

Creates an instance of the object identified by `object_id` (e.g. `master_zone.savant_scroll_of_learning`) and places it according to **target**:

- **Character** (e.g. `me`, `%S%`, or a reference) — object is added to that character's inventory.
- **Room** (e.g. `here` or a room id) — object is added to that room.
- **Object** — if the object is a container, the new object is placed inside it; otherwise the command fails with "Couldn't figure out where to put it."

If `object_id` has no zone prefix (no dot), the zone is inferred from the script context (e.g. the trigger owner's zone or start zone).

#### applystate command

**Syntax:** `applystate <target> <state_name> <duration_seconds> [state-specific args...]`

Applies a timed state to a target. **Target** is resolved like other script commands (reference, character name, `here` for room, etc.). **duration_seconds** is the state duration in seconds (converted to game ticks internally). Only the **applier** (the actor running the script) receives confirmation or error messages; the target does not get a message from the command itself (the state may have its own apply/remove messages).

**States:**

- **experiencemodifier** — (target must be a character.) One extra arg: **xp multiplier** (e.g. `0.75` for penalty, `1.25` for bonus). Multiplies experience gained while the state is active. Example: `applystate %S% experiencemodifier 3600 100` grants 100× XP for 3600 seconds (1 hour).
- **damagemultiplier** — (target must be a character.) Two extra args: **damage type** and **multiplier**. Example: `applystate %S% damagemultiplier 300 fire 0.5` grants 50% fire resistance for 5 minutes.
- **maxhp** — (target must be a character.) One extra arg: **flat max HP bonus**. Example: `applystate %S% maxhp 300 20` grants +20 max HP for 5 minutes. This raises max HP only; it does not heal current HP, and current HP is clamped back down if needed when the state expires.
- **shielded** — (target must be a character.) One extra arg: **multiplier** applied to all incoming damage types. Example: `applystate %S% shielded 180 0.8` grants 20% resistance to all damage for 3 minutes.
- **dodgebonus** — (target must be a character.) One extra arg: **flat dodge bonus**. Example: `applystate %S% dodgebonus 180 15` grants +15 dodge for 3 minutes.
- **damagebonus** — (target must be a character.) One extra arg: **flat damage bonus**. Example: `applystate %S% damagebonus 180 5` grants +5 damage for 3 minutes.
- **regenerating** — (target must be a character.) One required extra arg: **heal amount**. Optional second extra arg: **pulse seconds**. Example: `applystate %S% regenerating 60 5 6` heals 5 HP every 6 seconds for 1 minute.

#### Give command

**Syntax:** `give <item> <target>`

Give works when the script runs as a **character**, **room**, or **object**. The item can be in the actor’s inventory or in the room (including inside containers); it is **automatically removed from any container** when given.

- **Targeting (room-first):** By default, the target is resolved **room-only** (same room as the initiator). So `give sword guard` finds “guard” in the current room.
- **Room as target:** A **room** is a valid target. Use `here` for the current room, or a **room_id** (e.g. `zone_id.room_id` or `zone_id.subzone_id.room_id`) to give to a specific room. Example: an object script can do `give me here` to put itself in the room when picked up.
- **Reference override:** If the target is a **reference** (e.g. `@C123`, `@R456`), room-only is overridden: give can target that character or room **anywhere in the world** and succeeds regardless of location.
- **Rooms/objects giving:** When the script runs as a room or object, the **item** can be an existing object (by keyword, or `me`/`self` for the object itself) or an object **spawned from the zone** by id (e.g. `give rusty_key guard` spawns the zone’s `rusty_key` and gives it to “guard” in the room).

#### Signal command

**Syntax:** `signal <scope> <signal_name> <target> <message...>`

Sends a signal to all **on_signal** triggers whose receiver is in the given scope (relative to the signaler's location).

- **scope:** `room` (same room only), `subzone` (same zone and subzone), `zone` (same zone), or `world` (everywhere).
- **signal_name:** Name of the signal (e.g. `alarm`, `help`). Receivers can filter by this using criteria `%signal%` eq `alarm`.
- **target:** Any actor (typically a reference like `@C123`). Available in on_signal scripts as `%t%`/`%T%`.
- **message:** Fourth and later words; available in on_signal scripts as `%text%`.

Example: `signal zone alarm @C455 The gates are under attack!` notifies all on_signal receivers in the same zone; their scripts see actor = trigger owner (me), subject = signaler, target = @C455, `%signal%` = "alarm", `%text%` = "The gates are under attack!".

#### damage command

**Syntax:**
- `damage <target>[,target2,...] <amount> <damage_type>` — damage one or more named targets
- `damage all <amount> <damage_type>` — damage every character in the room
- `damage allexcept <exclude1>[,exclude2,...] <amount> <damage_type>` — damage everyone except the listed characters

Targets can be names, references (`%S%`, `@C123`), or `me`/`self`. Multiple targets are comma-separated (no spaces around commas). The amount supports constants (`10`) or dice notation (`2d6+5`). When using dice notation directly in the amount, each target gets an independent roll. To give everyone the same roll, pre-resolve with `$random()`: e.g. `damage all $random(3d6+6) fire`.

**Damage types:** `slashing`, `piercing`, `bludgeoning`, `fire`, `cold`, `lightning`, `poison`, `acid`, `necrotic`, `radiant`, `force`, `psychic`, `divine`, `nature`, `unholy`

**Examples:**
```
damage %S% 10 fire
damage guard,bandit 2d6+5 slashing
damage me,guard 5 cold
damage all 3d8 fire
damage all $random(3d6+6) fire
damage allexcept me 10 holy
damage allexcept me,guard 2d6 slashing
```

#### heal command

**Syntax:**
- `heal <target>[,target2,...] <amount>` — heal one or more named targets
- `heal all <amount>` — heal every character in the room
- `heal allexcept <exclude1>[,exclude2,...] <amount>` — heal everyone except the listed characters

Targets follow the same rules as `damage` (names, references, `me`/`self`, comma-separated). The amount supports constants (`20`) or dice notation (`2d6+5`). Dice are rolled independently per target; use `$random()` for a shared roll.

**Examples:**
```
heal %S% 20
heal guard,bandit 3d8+10
heal all 2d6+5
heal all $random(2d8+4)
heal allexcept me 20
heal allexcept me,guard 3d8
```

#### spawn command

**Syntax:** `spawn here <char_id>`

Spawns a new instance of a character definition in the current room. The `char_id` can be a local id (resolved to the current zone) or fully qualified (`zone_id.char_id`). The spawned character is independent of any room spawn data and will not respawn automatically when killed.

**Examples:**
```
spawn here goblin_warrior
spawn here shattered_dominion.dust_guardian
```

#### setstat command

**Syntax:** `setstat <target> <stat> <value>`

Sets or adjusts a stat on a character. The target is resolved like other commands (`%S%`, `me`, character name, reference). The value can be an absolute number or prefixed with `+` or `-` for relative adjustment.

**Stats:** `hp`, `mana`, `stamina`, and base attributes (`strength`, `dexterity`, `constitution`, `intelligence`, `wisdom`, `charisma`).

**Examples:**
```
setstat %S% hp 50
setstat %S% mana +25
setstat %S% stamina +10
setstat %A% hp 5
```

#### transfer command

**Syntax:** `transfer <target> <room_id>`

Teleports the target actor to the specified room. The room id can be local (same zone) or fully qualified (`zone_id.room_id`). The actor is silently removed from their current room and placed in the destination.

**Examples:**
```
transfer %S% shattered_dominion.room_pyr_apex_shrine
transfer me starting_room
```

#### force command

**Syntax:** `force <target> <command>`

Forces the target actor to execute a command as if they typed it. The target is resolved like other commands. The forced command goes through normal command processing including trigger checks.

**Examples:**
```
force %S% drop sword
force %S% say I surrender!
force me stop
```

## Script Functions

Functions can be used within scripts to perform calculations, manipulate strings, and access game state information. Functions are called using the syntax `$function_name(arg1, arg2, ...)`.

### String Functions

- `$cap(text)` - Capitalize the first letter of a string
- `$words(text, first, last)` - Extract a range of words from **text**. Punctuation (e.g. `, . ! ?`) is stripped from word boundaries and ignored when determining words (e.g. "Hello, world!" is two words). Word numbering is **1-based** (the first word is 1). Returns words from index **first** through **last** (inclusive). If **last** is less than 1 or greater than the number of words, returns from **first** through the end of the text. Examples: `$words(my name is bob, 2, 2)` → `"name"`; `$words(my name is bob, 2, 0)` → `"name is bob"`.

### Numeric Functions

- `$random(min, max)` - Generate a random number between min and max (inclusive)
- `$random(NdS+B)` - Roll dice notation (e.g. `$random(3d6+6)` rolls 3d6 and adds 6)
- `$numeq(a, b)` - Returns "true" if a equals b numerically, otherwise "false"
- `$numneq(a, b)` - Returns "true" if a does not equal b numerically, otherwise "false"
- `$numgt(a, b)` - Returns "true" if a is greater than b numerically, otherwise "false"
- `$numlt(a, b)` - Returns "true" if a is less than b numerically, otherwise "false"
- `$numgte(a, b)` - Returns "true" if a is greater than or equal to b numerically, otherwise "false"
- `$numlte(a, b)` - Returns "true" if a is less than or equal to b numerically, otherwise "false"
- `$between(a, b, c)` - Returns "true" if b is between a and c numerically, otherwise "false"

### Math Functions

- `$add(a, b)` - Returns `a + b` (integer addition)
- `$sub(a, b)` - Returns `a - b` (integer subtraction)
- `$mul(a, b)` - Returns `a * b` (integer multiplication)
- `$div(a, b)` - Returns `a / b` (integer division)
- `$mod(a, b)` - Returns the remainder of `a / b`

These are especially useful for incrementing quest counters. For example, to add 1 to a kill count:
```
setquestvar %s% wolf_quest.kills $add($questvar(%s%, wolf_quest.kills), 1)
```

### Variable Access Functions

- `$tempvar(target, name)` - Get the value of a temporary variable
- `$permvar(target, name)` - Get the value of a permanent variable
- `$questvar(target, var_id)` - Get the value of a quest variable (dot-notation path)

`$questvar` reads from the same scoped namespace as `setquestvar`. Use the short form (`quest_id.var_name`) within the same zone, or the fully-qualified form (`zone_id.quest_id.var_name`) for cross-zone access. This function can be used in `$if()` conditions or as an argument to math functions.

### Game State Functions

- `$name(target)` - Get the name of a character, object, room, or zone
- `$equipped(character, slot)` - Get the equipped item in the specified slot
- `$hasitem(character, item)` - Check if a character has an item anywhere (inventory or equipped)
- `$hasiteminv(character, item)` - Check if a character has an item in their inventory
- `$hasitemeq(character, item)` - Check if a character has an item equipped
- `$locroom(character)` - Get the name of the room where the character is located
- `$loczone(character)` - Get the name of the zone where the character is located
- `$olocroom(object)` - Get the name of the room where the object is located
- `$oloczone(object)` - Get the name of the zone where the object is located

## Conditional Logic

Scripts can use conditional logic to execute different actions based on conditions:

```
$if(condition_subject, condition_operator, condition_predicate){
  # Code to execute if condition is true
}
else {
  # Code to execute if condition is false
}
```

For example:

```
$if($random(1,100), numlte, 50){
  echo The coin lands on heads.
}
else {
  echo The coin lands on tails.
}
```

## System Variables

**Actor, subject, and target (general rule):** In trigger scripts, the same three roles are used consistently:

- **Actor** (`%a%` / `%A%`) — the **trigger owner**: the room, character, or object the trigger is on. The script runs “as” this actor.
- **Subject** (`%s%` / `%S%`) — the **initiator** of the action: whoever or whatever caused the trigger to fire (e.g. the player who said something, who used the item, who arrived).
- **Target** (`%t%` / `%T%`) — the **thing acted upon** (if any): e.g. the character being spoken to, the object being used on someone, or the item being used/read.

Examples: For **read scroll**, actor = the scroll (trigger owner), subject = the player (who read it), target = the scroll (thing acted upon). For **on_tell**, actor = the NPC (trigger owner), subject = the speaker, target = that same NPC.

The following system variables are available in scripts:

- `%a%` - The actor's name with article (trigger owner)
- `%A%` - The actor's reference number with reference symbol
- `%p%` - The actor's subject pronoun (he, she, it)
- `%P%` - The actor's object pronoun (him, her, it)
- `%s%` - The subject's name with article (initiator of the action)
- `%S%` - The subject's reference number with reference symbol (use for `give`, `echoto`, `applystate`, etc. to target the initiator)
- `%q%` - The subject's subject pronoun
- `%Q%` - The subject's object pronoun
- `%t%` - The target's name with article (thing acted upon, if applicable)
- `%T%` - The target's reference number with reference symbol
- `%r%` - The target's subject pronoun
- `%R%` - The target's object pronoun
- `%*%` - The current message or event text (e.g. the said line for **on_say** / **on_tell**)
- `%room_id%` - Full id of the room just entered (for `on_enter` triggers): `zone_id.subzone_id.room_id` or `zone_id.room_id`
- `%signal%` - Signal name (for `on_signal` triggers)
- `%text%` - Message text from the signal command (fourth and later words)

## Special Trigger Flags

Triggers can have optional flags that modify when they can execute:

- `ONLY_WHEN_PC_ROOM` - Only execute when a player character is in the same room
- `ONLY_WHEN_PC_ZONE` - Only execute when a player character is in the same zone

## Examples

### NPC That Responds to Greetings

```yaml
- id: shopkeeper
  name: shopkeeper
  article: the
  description: A friendly shopkeeper.
  triggers:
    - type: on_say
      criteria:
        - subject: "%*%"
          operator: contains
          predicate: "hello"
      script: |
        sayto %S% Hello there! Welcome to my shop.
    - type: timer_tick
      criteria:
        - subject: "%time_elapsed%"
          operator: "numgte"
          predicate: 300
        - subject: "$random(1,100)"
          operator: "numlte"
          predicate: 25
      script: |
        emote straightens some merchandise on the shelves.
```

### Object With Interactive Behavior

```yaml
- id: magical_orb
  name: magical orb
  article: a
  description: A glowing magical orb.
  triggers:
    - type: catch_inspect
      criteria:
        - subject: "%*%"
          operator: true
          predicate: ""
      script: |
        echoto %S% The orb pulses briefly as you look at it.
    - type: on_see
      criteria:
        - subject: "%*%"
          operator: contains
          predicate: "picks you up"
      script: |
        echo The orb glows brightly!
        settempvar char %S% orb_glow_level $random(1,10)
        $if($numgte($tempvar(%S%,orb_glow_level), 8), eq, true){
          echoto %S% You feel a surge of energy!
        }
```

### Room With Environmental Effects

```yaml
starting_room:
  name: Forest Clearing
  description: A peaceful clearing in the forest.
  triggers:
    - type: timer_tick
      criteria:
        - subject: "%time_elapsed%"
          operator: "numgte"
          predicate: 60
        - subject: "$random(1,100)"
          operator: "numlte"
          predicate: 20
      script: |
        echo A gentle breeze rustles the leaves around you.
    - type: on_see
      criteria:
        - subject: "%*%"
          operator: contains
          predicate: "arrives"
      script: |
        echoto %S% The birds briefly stop singing as you enter the clearing.
```

## YAML Formatting Standards

To ensure consistency and WYSIWYG fidelity across world files, the following conventions apply to all YAML text fields.

### Label Fields — Inline Only

Fields that serve as identifiers, titles, or short descriptions must remain on a single line. Do **not** use block scalars (`|`, `|-`, `>`) for these.

Label fields include:
- `quests.<quest_id>.title`
- `quests.<quest_id>.quest_variables.<var>.description`
- `stages[*].name`
- Any other short identifier or one-line label

```yaml
# Correct
title: "The Mystery of the Crypt"
description: "Has the player found the body?"

# Incorrect — do not use block scalars for labels
title: |-
  The Mystery of the Crypt
```

### Player-Facing / Narrative Text — Always Use `|-`

Any field that may contain multiple lines of text shown to players or injected into NPC prompts **must always** use a literal block scalar with strip chomping: `|-`.

This rule applies **even when the current value is a single line**, to guarantee:
- Consistent representation (no "inline vs. block" ambiguity for the same key)
- WYSIWYG formatting (the YAML source looks exactly like the output)
- No accidental trailing newline (use `|-` not `|`)

Fields that must use `|-`:
- `quests.<quest_id>.stages[*].description`
- `quests.<quest_id>.quest_variables.<var>.knowledge_updates[*].updates.<key>`
- Any world knowledge, journal, or narrative text intended for players or NPC prompt injection
- Room and NPC `description` fields intended for player display

```yaml
# Correct — single line but uses |- because the field can be multi-line
description: |-
  Rumors of a murder are circulating. Search the graveyard.

# Correct — multi-line, formatted exactly as it will appear
murder_case: |-
  You found a torn note on the body:

  "Meet me by the old oak... bring the key...
  E."

# Incorrect — quoted multi-line strings produce indentation surprises
murder_case: "Line 1
Line 2"
```

---

## Best Practices

1. **Use Specific Criteria**: Make your trigger criteria as specific as possible to avoid unintended executions.

2. **Script Efficiency**: Keep scripts concise and focused on specific tasks. Complex behavior can be achieved through multiple triggers working together.

3. **Variable Management**: Clean up temporary variables when you're done with them using `deltempvar`.

4. **Testing**: Test your scripts thoroughly with different inputs and edge cases.

5. **Documentation**: Comment complex scripts to explain what they do for future reference.

## Troubleshooting

### Common Issues

1. **Trigger Not Firing**: Check that the criteria exactly match what you're expecting. Use the "contains" operator for partial matches.

2. **Variable Not Available**: Make sure you're using the correct variable format (`%variable%`) and that the variable exists in the current context.

3. **Function Not Working**: Ensure function arguments are of the correct type. Most numeric functions require numeric inputs.

4. **Infinite Loops**: Be cautious with triggers that can activate each other, which might create infinite loops.

5. **Performance Issues**: Too many timer_tick triggers with short intervals can impact game performance.

## Advanced Techniques

### Chaining Triggers

You can create complex behaviors by having one trigger set variables that another trigger checks for:

```yaml
# First trigger sets a state
- type: on_say
  criteria:
    - subject: "%*%"
      operator: contains
      predicate: "open sesame"
  script: |
    setpermvar room %a% door_state open
    echo The stone door rumbles and slowly slides open.

# Second trigger reacts to the state
- type: timer_tick
  criteria:
    - subject: "%time_elapsed%"
      operator: "numgte"
      predicate: 30
    - subject: "$permvar(%a%, door_state)"
      operator: "eq"
      predicate: "open"
  script: |
    setpermvar room %a% door_state closed
    echo The stone door slowly closes.
```

### Creating NPCs with Memory

Use permanent variables to give NPCs memory of past interactions:

```yaml
- type: on_say
  criteria:
    - subject: "%*%"
      operator: contains
      predicate: "my name is"
  script: |
    settempvar char %a% player_name $replace(%*%, "my name is ", "")
    setpermvar char %a% knows_%S%_name $tempvar(%a%, player_name)
    sayto %S% Nice to meet you, $tempvar(%a%, player_name)!

- type: on_see
  criteria:
    - subject: "%*%"
      operator: contains
      predicate: "arrives"
    - subject: "$permvar(%a%, knows_%S%_name)"
      operator: "neq"
      predicate: ""
  script: |
    sayto %S% Welcome back, $permvar(%a%, knows_%S%_name)!
```

## Quest System Integration

### LLM Knowledge Updates via `setquestvar`

When a quest variable is modified through `setquestvar` and that variable is declared in the quest's `quest_variables` schema with a `knowledge_updates` block, the engine automatically updates the "World Knowledge" prompt injected into any LLM-driven NPC.

This means NPCs can react to quest progress dynamically without hardcoded dialogue trees. For example, if a player sets `murder_mystery.found_body` to `true`, an NPC whose prompt includes a `known_crimes` knowledge field will immediately reflect that update in subsequent conversations.

```yaml
# In quest YAML schema:
quest_variables:
  found_body:
    type: boolean
    default: false
    description: "Has the player found the body?"
    knowledge_updates:
      - condition: true
        updates:
          known_crimes: |-
            A body was found near the old crypt.
```

```
# In a trigger script:
setquestvar %s% murder_mystery.found_body true
# ^ This triggers Quest Engine evaluation AND injects the knowledge_updates text
#   into NPC prompts for any NPC that references "known_crimes".
```

> **Key distinction:** `setpermvar` stores a value but does **not** trigger Quest Engine evaluation or LLM knowledge updates. Always use `setquestvar` when the change should be visible to the Quest System or to LLM NPCs.

### Quest Engine Evaluation Order

The Quest System is **stateless**: it does not store a "current step" on the player. Instead, every time a quest variable changes, it re-evaluates all stages to determine the player's current position.

Stages are evaluated in **Descending Sequence Order** — highest sequence ID first. The first stage whose conditions are fully satisfied becomes the **Active Stage**:

```
Evaluate Stage 100 (Complete)  → Met? Active. Stop.
Evaluate Stage  50 (In Progress) → Met? Active. Stop.
Evaluate Stage  10 (Start)     → Met? Active. Stop.
(No stage matched → quest not yet started / hidden)
```

This is the opposite of standard top-down script execution. Placing "completion" stages at high sequence numbers ensures they take priority over earlier progress stages, even if those earlier conditions also happen to be true.

**Practical implication:** When writing quest stages, assign higher sequence IDs to more-advanced stages so that a player who has completed the quest is never incorrectly shown an earlier in-progress description.

---

## Conclusion

The NextGenMUD scripting system offers powerful tools for creating dynamic, interactive game worlds. By mastering triggers, criteria, and scripts, you can build rich environments that respond intelligently to player actions and create memorable gaming experiences.
