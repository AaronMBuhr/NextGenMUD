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

- `eq` - Equal to (string comparison)
- `numeq` - Numerically equal to
- `numneq` - Numerically not equal to
- `numgt` - Numerically greater than
- `numlt` - Numerically less than
- `numgte` - Numerically greater than or equal to
- `numlte` - Numerically less than or equal to
- `between` - Numerically between two values
- `contains` - String contains
- `matches` - Regular expression match
- `true` - Always true
- `false` - Always false

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

### Variable Access Functions

- `$tempvar(target, name)` - Get the value of a temporary variable
- `$permvar(target, name)` - Get the value of a permanent variable

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

## Conclusion

The NextGenMUD scripting system offers powerful tools for creating dynamic, interactive game worlds. By mastering triggers, criteria, and scripts, you can build rich environments that respond intelligently to player actions and create memorable gaming experiences.
