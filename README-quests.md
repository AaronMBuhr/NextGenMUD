
# NextGenMUD Quest System Documentation

The NextGenMUD Quest System is a **stateless, data-driven engine**. Unlike traditional MUDs that track "Quest ID: Step 5" on the player object, this system evaluates the player's current variables against a set of logic rules to determine *where* they are in a quest at any given moment.

This system is tightly integrated with the **LLM NPC Engine**. Changing a quest variable can automatically update the "World Knowledge" prompt for NPCs, allowing them to react dynamically to your progress without hardcoded dialogue trees.

---

## 1. Core Concepts

### A. Quests are "Viewers"
A `Quest` object does not store data on the player. It only *views* the player's `perm_variables`.
* **Concept:** You don't "advance" a quest directly. You change the world state (e.g., set `found_body = true`), and the Quest System calculates that you are now in the "Investigation" stage.

### B. Stages & Sequences
A quest is composed of **Stages**. Each stage has:
* **Conditions:** Logic checks (e.g., `wolves_killed >= 10`).
* **Description:** Text shown to the player via the `quests` command.
* **Sequence ID:** An integer (10, 20, 30...) used to prioritize stages.

**Evaluation Order:**
The system checks stages in **Descending Sequence Order** (Highest first). The *first* stage whose conditions are met is considered the **Active Stage**.
1.  Check Stage 100 (Complete). Met? -> Player is done. Stop.
2.  Check Stage 50 (In Progress). Met? -> Player is here. Stop.
3.  Check Stage 10 (Start). Met? -> Player is here. Stop.

### C. Quest Variables (The Schema)
Variables are named using dot-notation: `zone_id.quest_id.variable_name`.
You define these variables in the YAML to give them types, defaults, and **LLM triggers**.

---

## 2. YAML Structure

Quests are defined inside your Zone YAML files (e.g., `gloomy_graveyard.yaml`) under the `quests` key.

### Text Formatting Standard (Consistency + WYSIWYG)

We standardize YAML text scalars to avoid having the *same key* sometimes be inline and sometimes be a block.

#### 1) One-line label fields: INLINE ONLY
These fields are treated as labels and must be one line (no embedded newlines). Use inline YAML scalars (plain or quoted).

Examples of label fields:
- `quests.<quest_id>.title`
- `quests.<quest_id>.quest_variables.<var>.description`
- `stages[*].name` (and other identifiers/labels)

✅ Good:
```yaml
title: "The Mystery of the Crypt"
description: "Has the player found the body?"
````

❌ Not allowed (don’t use `|` / `|-` for label fields):

```yaml
title: |-
  The Mystery of the Crypt
```

#### 2) Multi-line-capable player-facing text: `|-` ALWAYS

If a field is allowed to be more than one line, it MUST always use a literal block scalar with strip chomping: `|-`
(even when it is currently a single line).

This guarantees:

* consistency (no “inline vs block” for the same key)
* WYSIWYG formatting (YAML looks like the player output)
* no accidental whitespace artifacts from wrapped quoted strings

Fields that MUST use `|-`:

* `quests.<quest_id>.stages[*].description`
* `quests.<quest_id>.quest_variables.<var>.knowledge_updates[*].updates.<any_key>`
* Any “world knowledge” / journal / narrative text intended for players or NPC prompt injection

✅ Good (single line but still block because the field can be multi-line):

```yaml
description: |-
  Rumors of a murder are circulating. Search the graveyard.
```

✅ Good (multi-line exactly as it should appear):

```yaml
murder_case: |-
  You found a torn note on the body:

  "Meet me by the old oak... bring the key...
  E."
```

❌ Not allowed (multi-line quoted strings create indentation/trailing-whitespace surprises):

```yaml
murder_case: "Line 1
Line 2"
```

**Note:** Always use `|-` (not `|`) to avoid an extra trailing newline appearing in output.

### Example Structure

```yaml
quests:
  # The Quest ID (this becomes the namespace for variables)
  murder_mystery:
    title: "The Mystery of the Crypt"
    
    # --- PART 1: VARIABLE SCHEMA ---
    # Define variables used by this quest here.
    variables:
      found_body:
        type: boolean
        default: false
        description: "Has the player found the body?"
        # LLM INTEGRATION:
        # When this variable becomes 'true', inject this text into NPC prompts.
        knowledge_updates:
          - condition: true
            updates:
              known_crimes: "A body was found near the old crypt."
      
      killer_status:
        type: string
        default: "unknown"
        # You can have multiple updates for different values
        knowledge_updates:
          - condition: "caught"
            updates:
              news: "The killer has been caught!"

    # --- PART 2: STAGES ---
    # Define the progression logic.
    stages:
      # STAGE: COMPLETED (Highest Priority)
      - name: solved
        sequence: 30
        description: "You have identified the killer and saved the village."
        conditions:
          murder_mystery.killer_status: "caught"

      # STAGE: INVESTIGATION (Mid-point)
      - name: investigate
        sequence: 20
        description: "You found a body. Ask the Groundskeeper what he saw."
        conditions:
          # Implicitly checks: zone_id.murder_mystery.found_body == true
          murder_mystery.found_body: true

      # STAGE: START (Entry point)
      # Usually triggered by a simple flag set by an NPC greet script.
      - name: start
        sequence: 10
        description: "Rumors of a murder are circulating. Search the graveyard."
        conditions:
          murder_mystery.started: true

```

---

## 3. Scripting Reference

### The `setquestvar` Command

Use this in your script lines (triggers) to update quest progress.

**Syntax:** `setquestvar <target> <variable_path> <value>`

* **`<target>`**: Usually `%s%` (the player triggering the script) or `me`.
* **`<variable_path>`**:
* *Short form:* `quest_id.var_name` (assumes current zone).
* *Long form:* `zone_id.quest_id.var_name` (cross-zone).


* **`<value>`**: `true`, `false`, an integer, or a string.

### Script Functions

You can use these functions within scripts (e.g., inside `$if()` or `setquestvar`).

| Function | Syntax | Description |
| --- | --- | --- |
| **Get Var** | `$questvar(target, var_id)` | Returns the current value of a quest variable. |
| **Add** | `$add(a, b)` | Returns `a + b` (integers). |
| **Subtract** | `$sub(a, b)` | Returns `a - b`. |
| **Multiply** | `$mul(a, b)` | Returns `a * b`. |
| **Divide** | `$div(a, b)` | Returns `a / b` (integer division). |
| **Modulo** | `$mod(a, b)` | Returns remainder of `a / b`. |

### Logic Operators (for Conditions)

Used in `$if()` or YAML `conditions`.

| Operator | Usage |
| --- | --- |
| `eq` / `numeq` | Equal to |
| `neq` / `numneq` | Not equal to |
| `numgt` | Greater than |
| `numlt` | Less than |
| `numgte` | Greater than or equal |
| `numlte` | Less than or equal |

---

## 4. Examples

### A. Incrementing a Kill Counter

Use `$add` and `$questvar` together to increment a value.

```yaml
# In an NPC or Mob definition
triggers:
  on_death:
    - script: |
        # target = %s% (the killer)
        # 1. Get current kills
        # 2. Add 1
        # 3. Save back to variable
        setquestvar %s% wolf_quest.kills $add($questvar(%s%, wolf_quest.kills), 1)
        
        # Optional: Feedback logic
        $if($numgte($questvar(%s%, wolf_quest.kills), 10), {
             echo "You have killed enough wolves. Return to the Mayor."
        })

```

### B. Starting a Quest via NPC Greet

```yaml
old_tom:
  triggers:
    on_greet:
      - criteria:
          subject: "$questvar(%s%, fishing_quest.started)"
          operator: "neq"
          predicate: "true"
        script: |
          say "Hello there! Could you help an old man catch some fish?"
          setquestvar %s% fishing_quest.started true

```

### C. Advanced YAML Condition

Using dictionaries for complex checks in the Quest definition.

```yaml
stages:
  - name: collecting
    sequence: 15
    description: "Keep collecting wolf pelts."
    conditions:
      # Check if started AND kills are less than 10
      wolf_quest.started: true
      wolf_quest.kills: { op: lt, val: 10 }

```

---

## 5. Player & Admin Commands

### Player Commands

* **`quests`**
* Lists the titles and descriptions of all currently *active* quest stages.
* If a player doesn't meet the conditions for *any* stage of a quest, that quest is hidden.
* If a player matches a "Completed" stage, it shows that status.



### Admin Commands

* **`getquestvar <target> <var>`**
* *Example:* `getquestvar me murder_mystery.found_body`
* Displays the raw value of the variable.


* **`setquestvar <target> <var> <value>`**
* *Example:* `setquestvar me murder_mystery.found_body true`
* Forces a variable change. This **will** trigger LLM knowledge updates if the variable is defined in the schema.



---

## 6. Troubleshooting

1. **Quest not showing up?**
* Type `getquestvar me your_quest.var_name` to see if the variable is actually set.
* Check your YAML indentation. `variables` and `stages` must be children of the specific quest ID (e.g., `murder_mystery`).


2. **NPC not reacting?**
* Check the `knowledge_updates` block in the YAML.
* Ensure the variable value matches the `condition` exactly (e.g., `true` vs `"true"`).


3. **Variable not found?**
* Remember scoping. If you are in zone `city`, referring to `rats.count` looks for `city.rats.count`. If the quest is in `dungeon`, you must use the fully qualified ID: `dungeon.rats.count`.


## Specific Variable Absence Handling Addendum

For quests that start because of absence of a variable, these will work but will not be shown to the player in the "quests" command. What should be done in this case is that immediately following the quest stage that checks for non-existence it should then set a "quest started" variable or some such to associate with the quest.
