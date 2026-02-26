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

## Trigger Types

NextGenMUD supports the following trigger types:

### `catch_any`

Responds to any game event that matches the criteria.

```yaml
- type: catch_any
  criteria: 
    - subject: "%*%"
      operator: contains
      predicate: "arrives."
  script: |
    echoto %S% You trip as you enter.
    echoexcept %S% $cap(%s%) trips as %q% enters.
```

### `catch_say`

Responds when a character says something matching the criteria.

```yaml
- type: catch_say
  criteria: 
    - subject: "%*%"
      operator: contains
      predicate: "hello"
  script: |
    emote waves hello in return.
```

### `catch_look`

Responds when a character looks at something matching the criteria.

```yaml
- type: catch_look
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
- `contains` - String contains
- `matches` - Regular expression match
- `true` - Always true
- `false` - Always false

> **Note:** The shorthand aliases (`gt`, `lt`, `gte`, `lte`, `eq`, `neq`) are used interchangeably with the `num`-prefixed forms throughout both standard scripts and the Quest Engine's YAML condition blocks.

### Special Variables in Criteria

- `%*%` - The current message or event text
- `%time_elapsed%` - Time elapsed since the last trigger execution (for timer_tick triggers)

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
- `move [direction]` - Move in a direction
- `attack [character]` - Attack a character
- `give [object] [character]` - Give an object to a character
- `get [object]` - Pick up an object
- `drop [object]` - Drop an object

## Script Functions

Functions can be used within scripts to perform calculations, manipulate strings, and access game state information. Functions are called using the syntax `$function_name(arg1, arg2, ...)`.

### String Functions

- `$cap(text)` - Capitalize the first letter of a string

### Numeric Functions

- `$random(min, max)` - Generate a random number between min and max
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

The following system variables are available in scripts:

- `%a%` - The actor's name with article
- `%A%` - The actor's reference number with reference symbol
- `%p%` - The actor's subject pronoun (he, she, it)
- `%P%` - The actor's object pronoun (him, her, it)
- `%s%` - The subject's name with article (usually the triggering character)
- `%S%` - The subject's reference number with reference symbol
- `%q%` - The subject's subject pronoun
- `%Q%` - The subject's object pronoun
- `%t%` - The target's name with article (if applicable)
- `%T%` - The target's reference number with reference symbol
- `%r%` - The target's subject pronoun
- `%R%` - The target's object pronoun
- `%*%` - The current message or event text

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
    - type: catch_say
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
    - type: catch_look
      criteria:
        - subject: "%*%"
          operator: true
          predicate: ""
      script: |
        echoto %S% The orb pulses briefly as you look at it.
    - type: catch_any
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
    - type: catch_any
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
- type: catch_say
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
- type: catch_say
  criteria:
    - subject: "%*%"
      operator: contains
      predicate: "my name is"
  script: |
    settempvar char %a% player_name $replace(%*%, "my name is ", "")
    setpermvar char %a% knows_%S%_name $tempvar(%a%, player_name)
    sayto %S% Nice to meet you, $tempvar(%a%, player_name)!

- type: catch_any
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
