# World File Merge Format Guide

A complete reference for constructing revision YAML files to be merged with existing NextGenMUD world files using the `merge_mud_files.py` tool.

---

## Table of Contents

1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
3. [Critical Format Rules](#critical-format-rules)
4. [Merge Behavior Rules](#merge-behavior-rules)
5. [World File Structure](#world-file-structure)
6. [Revision File Syntax](#revision-file-syntax)
7. [ZONES Section](#zones-section)
8. [CHARACTERS Section](#characters-section)
9. [OBJECTS Section](#objects-section)
10. [Special Markers Reference](#special-markers-reference)
11. [Complete Field Reference](#complete-field-reference)
12. [Common Patterns](#common-patterns)
13. [Command Line Usage](#command-line-usage)
14. [Troubleshooting](#troubleshooting)

---

## Introduction

The merge system allows you to maintain zone files through incremental revision files. Instead of editing massive zone files directly, you create small, focused revision files that document exactly what you're changing.

### Benefits

- **Clean base files**: Original zone files remain readable
- **Trackable changes**: Revisions serve as documentation
- **Safe updates**: Review merged output before replacing
- **Partial updates**: Only specify what changes, not entire files
- **Comment preservation**: Base file comments are retained

### How Merging Works

```
┌────────────────────┐    ┌────────────────────┐
│   Base Zone File   │    │   Revision File    │
│  (world_data/      │ +  │  (my_revisions     │
│   zone.yaml)       │    │   .yaml)           │
└─────────┬──────────┘    └─────────┬──────────┘
          │                         │
          └────────────┬────────────┘
                       ▼
           ┌─────────────────────┐
           │  merge_mud_files.py │
           └──────────┬──────────┘
                      ▼
          ┌────────────────────────┐
          │   Merged Output File   │
          │  (zone_merged.yaml)    │
          └────────────────────────┘
```

---

## Getting Started

### Prerequisites

Install `ruamel.yaml` for comment preservation:

```bash
pip install ruamel.yaml
```

### Basic Workflow

1. **Create a revision file** with only the changes you want
2. **Run the merge tool** to combine base + revisions
3. **Review the output** for correctness
4. **Replace the base file** if satisfied

### Minimal Example

**Base file** (`world_data/my_zone.yaml`):
```yaml
ZONES:
  my_zone:
    name: My Zone
    rooms:
      town_square:
        name: Town Square
        description: The center of town.
        exits:
          north: { destination: shop }
```

**Revision file** (`revisions.yaml`):
```yaml
ZONES:
  my_zone:
    rooms:
      town_square:
        # Add a new exit
        exits:
          south: { destination: tavern }
      
      # Add a new room
      tavern:
        name: The Rusty Tankard
        description: A cozy tavern.
        exits:
          north: { destination: town_square }
```

**Run merge**:
```bash
python merge_mud_files.py world_data/my_zone.yaml revisions.yaml output.yaml
```

**Result** (`output.yaml`):
```yaml
ZONES:
  my_zone:
    name: My Zone
    rooms:
      town_square:
        name: Town Square
        description: The center of town.
        exits:
          north: { destination: shop }
          south: { destination: tavern }  # NEW
      
      tavern:                              # NEW
        name: The Rusty Tankard
        description: A cozy tavern.
        exits:
          north: { destination: town_square }
```

---

## Critical Format Rules

**These rules are mandatory. Violating them will cause parse errors.**

### Rule: Single Document Only

Revision files must be a single YAML document. **NEVER use `---` document separators.**

```yaml
# WRONG - creates multiple documents, will fail to parse
COMMON_KNOWLEDGE:
  - id: some_knowledge
    description: Info here.

---

ROOMS:
  - id: some_room

# CORRECT - single document, sections follow each other
COMMON_KNOWLEDGE:
  - id: some_knowledge
    description: Info here.

ROOMS:
  - id: some_room
```

### Rule: `__list_strategy__` Placement

When using `__list_strategy__: replace`, place it on the **parent item** that contains the list, NOT inside the list's value.

```yaml
# WRONG - __list_strategy__ inside the triggers mapping
- id: some_room
  triggers:
    __list_strategy__: replace
    - id: my_trigger
      type: on_enter

# CORRECT - __list_strategy__ on the parent item
- id: some_room
  __list_strategy__: replace
  triggers:
    - id: my_trigger
      type: on_enter
```

For nested structures like `llm_conversation.knowledge`:

```yaml
# WRONG - __list_strategy__ inside knowledge
- id: some_npc
  llm_conversation:
    knowledge:
      __list_strategy__: replace
      - id: knowledge_piece

# CORRECT - __list_strategy__ on llm_conversation
- id: some_npc
  llm_conversation:
    __list_strategy__: replace
    knowledge:
      - id: knowledge_piece
```

### Rule: Use Spaces, Not Tabs

YAML requires spaces for indentation. Use 2 spaces per indent level. Never use tab characters.

### Rule: All List Items Need IDs

Every character, object, trigger, and knowledge item must have a unique `id` field for proper merge matching.

---

## Merge Behavior Rules

Understanding these rules is critical for constructing correct revision files.

### Rule 1: Dictionaries Are Deep Merged

When both base and revision have a dictionary at the same path, they are recursively merged:

```yaml
# Base
character:
  attributes:
    strength: 10
    dexterity: 12

# Revision
character:
  attributes:
    strength: 14      # Updated
    wisdom: 15        # Added

# Result
character:
  attributes:
    strength: 14      # Updated from revision
    dexterity: 12     # Kept from base
    wisdom: 15        # Added from revision
```

### Rule 2: Lists Are Extended By Default

When both have a list, revision items are appended (duplicates skipped):

```yaml
# Base
permanent_flags:
  - is_aggressive
  - no_flee

# Revision
permanent_flags:
  - regenerates
  - is_aggressive   # Already exists, skipped

# Result
permanent_flags:
  - is_aggressive
  - no_flee
  - regenerates     # Added
```

### Rule 3: Scalars Are Replaced

Simple values (strings, numbers, booleans) are replaced entirely:

```yaml
# Base
description: An old description.
level: 3

# Revision
description: A brand new description.
level: 5

# Result
description: A brand new description.
level: 5
```

### Rule 4: Missing Keys Are Added

Keys in the revision that don't exist in base are simply added:

```yaml
# Base
room:
  name: Cave
  description: Dark cave.

# Revision
room:
  triggers:         # Not in base, added entirely
    - id: drip
      type: timer_tick
      script: echo Drip... drip...

# Result
room:
  name: Cave
  description: Dark cave.
  triggers:
    - id: drip
      type: timer_tick
      script: echo Drip... drip...
```

### Rule 5: ID-Based Matching for Character/Object/Trigger Lists

Lists containing items with `id` fields are matched by ID, not position:

```yaml
# Base
triggers:
  - id: greet_player
    type: catch_say
    script: say Hello!

# Revision
triggers:
  - id: greet_player      # Matches existing by ID
    script: say Greetings! # Updates the script field only

# Result
triggers:
  - id: greet_player
    type: catch_say       # Kept from base
    script: say Greetings! # Updated from revision
```

---

## World File Structure

A complete world file has three main sections:

```yaml
ZONES:
  zone_id:
    name: Zone Name
    description: Zone description text.
    common_knowledge:
      knowledge_id: Knowledge content.
    quest_variables:
      quest_name:
        var_name: { type: boolean, default: false }
    rooms:
      room_id:
        name: Room Name
        description: Room description.
        flags: [flag1, flag2]
        exits:
          direction: { destination: other_room, description: Exit desc. }
        triggers: [...]
        characters: [{ id: npc_id, quantity: 1 }]
        objects: [{ id: obj_id, quantity: 1 }]

CHARACTERS:
  - zone: zone_id
    characters:
      - id: character_id
        name: Character Name
        # ... full character definition

OBJECTS:
  - zone: zone_id
    objects:
      - id: object_id
        name: Object Name
        # ... full object definition
```

---

## Revision File Syntax

Revision files use the **exact same structure** as world files but only include what you want to change.

### Adding Content

Include the new content with a unique ID:

```yaml
# Add a new room
ZONES:
  my_zone:
    rooms:
      new_room_id:
        name: New Room
        description: A new room.
        exits:
          west: { destination: existing_room }

# Add a new NPC
CHARACTERS:
  - zone: my_zone
    characters:
      - id: new_npc
        name: New NPC
        description: A new character.
```

### Updating Content

Reference the existing ID and specify only fields to change:

```yaml
# Update existing room - add exit
ZONES:
  my_zone:
    rooms:
      existing_room:
        exits:
          secret: { destination: hidden_room }

# Update existing character - change level
CHARACTERS:
  - zone: my_zone
    characters:
      - id: existing_npc
        class:
          Fighter:
            level: 5  # Was 3
```

### Removing Content

Use special syntax to remove fields or entries:

```yaml
# Remove a field: prefix with -
CHARACTERS:
  - zone: my_zone
    characters:
      - id: some_npc
        class:
          Fighter:
            skills:
              -power_attack: 0  # Removes power_attack skill

# Remove entire entry: use __remove__
CHARACTERS:
  - zone: my_zone
    characters:
      - id: npc_to_delete
        __remove__: true

# Remove a room
ZONES:
  my_zone:
    rooms:
      room_to_delete:
        __remove__: true
```

---

## ZONES Section

### Zone-Level Fields

```yaml
ZONES:
  zone_id:
    name: "Zone Display Name"         # Shown to players
    description: |                     # Zone description
      Multi-line description text.
    
    common_knowledge:                  # Knowledge for NPCs
      knowledge_id: >
        Information that NPCs know about.
    
    quest_variables:                   # Quest tracking
      quest_name:
        variable_name:
          description: "What this tracks"
          type: boolean                # boolean, string, integer
          default: false
          knowledge_updates:           # Auto-update NPC knowledge
            - condition: true
              updates:
                knowledge_id: "Updated knowledge text."
    
    rooms:
      # Room definitions...
```

### Room Fields

```yaml
rooms:
  room_id:
    name: "Room Display Name"
    description: |
      Detailed room description shown to players.
      Can be multi-line.
    
    flags:                    # Optional room flags
      - indoors
      - no_magic
      - safe_room
    
    exits:
      north:
        destination: other_room_id    # Required
        description: "Exit description." # Optional
      east:
        destination: other_zone.room_id  # Cross-zone exits
      secret:
        destination: hidden_room
        hidden: true                   # Optional: not shown in normal exit list
    
    triggers:
      - id: trigger_id
        type: timer_tick               # Trigger type
        flags:
          - only_when_pc_room
        criteria:
          - subject: "%time_elapsed%"
            operator: numgte
            predicate: 30
        script: |
          echo Something happens.
    
    characters:                        # NPCs to spawn here
      - id: npc_id
        quantity: 1
        respawn_time_min: 60           # Optional
        respawn_time_max: 120
    
    objects:                           # Objects to spawn here
      - id: object_id
        quantity: 1
```

### Adding/Modifying Rooms

```yaml
ZONES:
  my_zone:
    rooms:
      # Modify existing room - adds to what's there
      existing_room:
        exits:
          secret: { destination: hidden_area }
        triggers:
          - id: new_ambient_trigger
            type: timer_tick
            flags: [only_when_pc_room]
            criteria:
              - subject: "%time_elapsed%"
                operator: numgte
                predicate: 20
            script: echo A breeze whispers through.
      
      # Add new room - entirely new entry
      hidden_area:
        name: Hidden Area
        description: A secret place.
        exits:
          out: { destination: existing_room }
```

### Adding Common Knowledge

```yaml
ZONES:
  my_zone:
    common_knowledge:
      new_rumor: >
        Villagers whisper about strange lights in the forest.
      updated_info: >
        This replaces any existing 'updated_info' entry.
```

### Adding Quest Variables

```yaml
ZONES:
  my_zone:
    quest_variables:
      treasure_hunt:
        found_map:
          description: "Player found the treasure map"
          type: boolean
          default: false
        treasure_location:
          description: "Which location the player checked"
          type: string
          default: ""
          knowledge_updates:
            - condition: "cave"
              updates:
                treasure_status: "The cave holds ancient secrets."
```

---

## CHARACTERS Section

Characters are defined separately and referenced in rooms by ID.

### Full Character Definition

```yaml
CHARACTERS:
  - zone: zone_id
    characters:
      - id: unique_character_id
        name: Display Name
        article: the                    # "", "a", "an", "the"
        keywords:                       # Words that target this NPC
          - keyword1
          - keyword2
        description: >
          Full description shown when looking at character.
        examine_text: >                 # Optional detailed examination
          Additional detail when examined closely.
        
        # Pronouns
        pronoun_subject: he             # he, she, it, they
        pronoun_object: him             # him, her, it, them
        pronoun_possessive: his         # his, her, its, their
        
        # Grouping
        group_id: npc_group             # For faction/group behavior
        
        # Disposition
        attitude: NEUTRAL               # FRIENDLY, NEUTRAL, WARY, UNFRIENDLY, HOSTILE
        
        # Stats
        attributes:
          strength: 10
          dexterity: 10
          constitution: 10
          intelligence: 10
          wisdom: 10
          charisma: 10
        
        # Class and level
        class:
          Fighter:                      # Fighter, Rogue, Mage, Cleric
            level: 3
            skills:                     # Optional class skills
              power_attack: 50
        
        # Combat stats
        hit_dice: 3d8+6                 # HP calculation
        hit_modifier: 2                 # Attack bonus
        dodge_dice: 2d20+15             # Dodge calculation
        armor_class: 12                 # AC
        damage_reduction: 2             # Flat damage reduction
        critical_chance: 0.05           # Crit chance (0.0-1.0)
        critical_multiplier: 2          # Crit damage multiplier
        
        # Natural attacks (for NPCs without weapons)
        natural_attacks:
          - attack_noun: claw
            attack_verb: claws
            potential_damage:
              - damage_type: slashing
                damage_dice: 1d6+2
              - damage_type: poison      # Multiple damage types
                damage_dice: 1d4
        
        # Experience reward
        experience_points: 100
        
        # Flags
        permanent_flags:
          - is_aggressive
          - is_sentinel                 # Won't leave room
          - no_flee
          - is_undead
          - regenerates
        
        # LLM Conversation (for quest NPCs)
        llm_conversation:
          personality: >
            Description of how this NPC thinks and behaves.
          speaking_style: >
            How they talk - accent, vocabulary, mannerisms.
          knowledge:
            - id: knowledge_piece_id
              content: What they know.
              reveal_threshold: 50      # Disposition needed to share
              is_secret: true           # Reluctant to share
          goals:
            - id: goal_id
              description: What triggers this goal
              condition: "Condition description"
              disposition_required: 60
              on_achieve_set_vars:
                zone.quest.variable: true
              on_achieve_message: "Message shown to player"
          will_discuss:
            - topic1
            - topic2
          will_not_discuss:
            - forbidden_topic
          common_knowledge_refs:        # Zone knowledge they can access
            - knowledge_id1
            - knowledge_id2
        
        # Triggers
        triggers:
          - id: trigger_id
            type: on_enter
            script: echo NPC notices you.
```

### Partial Character Update

Only specify the fields you're changing:

```yaml
CHARACTERS:
  - zone: my_zone
    characters:
      - id: existing_npc
        # Update level
        class:
          Fighter:
            level: 5
        # Add new flag (extends list)
        permanent_flags:
          - darkvision
        # Update single attribute
        attributes:
          strength: 16
```

### Adding Character Triggers

```yaml
CHARACTERS:
  - zone: my_zone
    characters:
      - id: shopkeeper
        triggers:
          - id: greet_first_time
            type: on_enter
            criteria:
              - subject: "$permvar(%S%, met_shopkeeper)"
                operator: "!="
                predicate: "true"
            script: |
              setpermvar char %S% met_shopkeeper true
              pause 0.3
              say Welcome to my shop, traveler!
          
          - id: receive_gem
            type: on_receive
            criteria:
              - subject: "%item_id%"
                operator: eq
                predicate: "rare_gem"
            script: |
              echo The shopkeeper's eyes widen.
              say My word! A flawless gem!
```

### Updating Character LLM Knowledge

```yaml
CHARACTERS:
  - zone: my_zone
    characters:
      - id: quest_npc
        llm_conversation:
          knowledge:
            - id: new_secret
              content: "A new piece of information."
              reveal_threshold: 70
              is_secret: true
          goals:
            - id: new_goal
              description: "New objective"
              condition: "When player does X"
              on_achieve_set_vars:
                my_zone.quest.step2: true
```

---

## OBJECTS Section

Objects are defined separately and referenced in rooms or given to NPCs.

### Full Object Definition

```yaml
OBJECTS:
  - zone: zone_id
    objects:
      - id: unique_object_id
        name: Display Name
        article: a                      # "", "a", "an", "the"
        keywords:
          - sword
          - blade
        description: >
          Description when looking at object.
        examine_text: >
          Detailed examination text.
        
        # Object flags
        object_flags:
          - is_container
          - is_locked
          - is_key
          - is_weapon
          - is_armor
          - is_consumable
          - is_quest_item
        
        # Key for locks
        key_id: matching_key_id         # What key opens this
        
        # Container properties
        container_capacity: 10          # How many items it holds
        
        # Equipment properties
        equip_location: main_hand       # Where it's worn/held
        
        # Weapon properties
        weapon_attacks:
          - attack_noun: blade
            attack_verb: slashes
            potential_damage:
              - damage_type: slashing
                damage_dice: 1d8+1
        attack_speed: 1.0
        
        # Armor properties
        armor_class_bonus: 2
        
        # Consumable properties
        uses: 3                         # Number of uses
        effects:
          - type: heal
            value: 2d4+2
        
        # Triggers
        triggers:
          - id: use_trigger
            type: on_use
            script: echo You use the item.
```

### Partial Object Update

```yaml
OBJECTS:
  - zone: my_zone
    objects:
      - id: existing_sword
        # Update damage
        weapon_attacks:
          - attack_noun: blade
            attack_verb: slashes
            potential_damage:
              - damage_type: slashing
                damage_dice: 2d6+3      # Upgraded from 1d8+1
```

### Object with Quest Trigger

```yaml
OBJECTS:
  - zone: my_zone
    objects:
      - id: ancient_tome
        name: ancient tome
        article: an
        description: A dusty leather-bound book.
        examine_text: |
          The pages contain cryptic writings about a hidden treasure.
        triggers:
          - id: read_tome
            type: on_use
            script: |
              $if($questvar(%S%, treasure_hunt.read_tome), !=, true){
                setquestvar %S% treasure_hunt.read_tome true
                echo You decipher the ancient text...
                pause 1
                echo It speaks of treasure hidden beneath the old oak!
              }
              else {
                echo You've already read this tome.
              }
```

---

## Special Markers Reference

| Marker | Syntax | Effect |
|--------|--------|--------|
| Remove field | `-fieldname: any` | Removes `fieldname` from parent dict |
| Remove entry | `__remove__: true` | Removes this entire entry (by ID) |
| Replace dict | `__replace__: true` | Replaces entire dict instead of merging |
| Replace lists | `__list_strategy__: replace` | Child lists replace instead of extend |

### Remove Field Example

```yaml
CHARACTERS:
  - zone: my_zone
    characters:
      - id: npc
        class:
          Fighter:
            skills:
              -power_attack: 0     # Removes power_attack
              -disarm: 0           # Removes disarm
```

### Remove Entry Example

```yaml
# Remove a character
CHARACTERS:
  - zone: my_zone
    characters:
      - id: obsolete_npc
        __remove__: true

# Remove a room
ZONES:
  my_zone:
    rooms:
      old_room:
        __remove__: true

# Remove a trigger
ZONES:
  my_zone:
    rooms:
      some_room:
        triggers:
          - id: old_trigger
            __remove__: true
```

### Replace Dict Example

```yaml
# Replace entire natural_attacks instead of merging
CHARACTERS:
  - zone: my_zone
    characters:
      - id: monster
        natural_attacks:
          __replace__: true        # Clear and replace
          - attack_noun: bite
            attack_verb: bites
            potential_damage:
              - damage_type: piercing
                damage_dice: 2d8+4
```

### Replace Lists Example

```yaml
# Replace all triggers instead of extending
ZONES:
  my_zone:
    rooms:
      some_room:
        __list_strategy__: replace
        triggers:                   # These replace existing triggers
          - id: only_trigger
            type: timer_tick
            script: echo This is now the only trigger.
```

---

## Complete Field Reference

### Room Flags

| Flag | Description |
|------|-------------|
| `indoors` | Room is inside a building |
| `no_magic` | Magic cannot be used |
| `safe_room` | PvP disabled |
| `dark` | Requires light source |
| `underwater` | Requires water breathing |

### Character Flags

| Flag | Description |
|------|-------------|
| `is_aggressive` | Attacks players on sight |
| `is_sentinel` | Never leaves room |
| `no_flee` | Cannot flee from combat |
| `is_undead` | Undead creature type |
| `regenerates` | Regenerates health |
| `is_pc` | Is a player character |
| `is_shopkeeper` | Can trade items |
| `immune_charm` | Immune to charm effects |

### Object Flags

| Flag | Description |
|------|-------------|
| `is_container` | Can hold other items |
| `is_locked` | Requires key to open |
| `is_key` | Can unlock things |
| `is_weapon` | Can be equipped as weapon |
| `is_armor` | Can be equipped as armor |
| `is_consumable` | Has limited uses |
| `is_quest_item` | Cannot be dropped/sold |
| `is_hidden` | Not visible in room |

### Damage Types

| Type | Description |
|------|-------------|
| `slashing` | Bladed weapons |
| `piercing` | Pointed weapons |
| `bludgeoning` | Blunt weapons |
| `fire` | Fire damage |
| `cold` | Ice/cold damage |
| `lightning` | Electric damage |
| `poison` | Poison damage |
| `acid` | Acidic damage |
| `necrotic` | Death/decay damage |
| `radiant` | Holy light damage |
| `force` | Pure magical force |
| `psychic` | Mental damage |
| `divine` | Divine power |
| `nature` | Natural/druidic |
| `unholy` | Unholy/evil |

### Attitudes

| Attitude | Description |
|----------|-------------|
| `FRIENDLY` | Helpful, open to conversation |
| `NEUTRAL` | Neither helpful nor hostile |
| `WARY` | Suspicious, guarded |
| `UNFRIENDLY` | Cold, unhelpful |
| `HOSTILE` | May attack |

---

## Common Patterns

### Adding a Quest Line

```yaml
ZONES:
  my_zone:
    quest_variables:
      treasure_hunt:
        talked_to_old_man: { type: boolean, default: false }
        found_map: { type: boolean, default: false }
        found_treasure: { type: boolean, default: false }
    
    rooms:
      village_square:
        characters:
          - id: old_hermit
            quantity: 1

CHARACTERS:
  - zone: my_zone
    characters:
      - id: old_hermit
        name: Old Hermit
        description: A weathered old man mumbling about treasure.
        attitude: WARY
        triggers:
          - id: hermit_greet
            type: on_enter
            criteria:
              - subject: "$questvar(%S%, treasure_hunt.talked_to_old_man)"
                operator: "!="
                predicate: "true"
            script: |
              pause 0.5
              echo The old hermit eyes you suspiciously.
              emote mutters about lost treasures
```

### Adding Hidden Areas

```yaml
ZONES:
  my_zone:
    rooms:
      library:
        triggers:
          - id: find_secret
            type: catch_any
            criteria:
              - subject: "%*%"
                operator: contains
                predicate: "bookshelf"
            script: |
              $if($permvar(%S%, found_secret), !=, true){
                setpermvar char %S% found_secret true
                echo You notice a book that doesn't quite fit...
              }
        exits:
          secret:
            destination: hidden_study
            description: A gap behind the bookshelf.
      
      hidden_study:
        name: Hidden Study
        description: A dusty secret room.
        exits:
          out: { destination: library }
```

### Buffing Enemies

```yaml
CHARACTERS:
  - zone: my_zone
    characters:
      - id: boss_monster
        class:
          Fighter:
            level: 8
        hit_dice: 8d10+24
        natural_attacks:
          - attack_noun: claw
            attack_verb: rends
            potential_damage:
              - damage_type: slashing
                damage_dice: 2d8+5
        permanent_flags:
          - regenerates
          - immune_charm
        experience_points: 500
```

### Adding Ambient Triggers

```yaml
ZONES:
  my_zone:
    rooms:
      spooky_forest:
        triggers:
          - id: ambient_1
            type: timer_tick
            flags: [only_when_pc_room]
            criteria:
              - subject: "%time_elapsed%"
                operator: numgte
                predicate: 30
              - subject: "$random(1,100)"
                operator: numlte
                predicate: 25
            script: |
              echo A cold wind whispers through the trees.
          
          - id: ambient_2
            type: timer_tick
            flags: [only_when_pc_room]
            criteria:
              - subject: "%time_elapsed%"
                operator: numgte
                predicate: 45
              - subject: "$random(1,100)"
                operator: numlte
                predicate: 15
            script: |
              echo You hear a distant howl.
```

---

## Command Line Usage

```bash
python merge_mud_files.py <base_file> <revisions_file> [output_file]
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `base_file` | Yes | Path to the base zone YAML |
| `revisions_file` | Yes | Path to the revision YAML |
| `output_file` | No | Output path (default: `base_merged.yaml`) |
| `--in-place`, `-i` | No | Modify base file directly (dangerous) |

### Examples

```bash
# Merge with explicit output
python merge_mud_files.py world_data/zone.yaml revisions.yaml world_data/zone_new.yaml

# Auto-generate output name (creates zone_merged.yaml)
python merge_mud_files.py world_data/zone.yaml revisions.yaml

# Modify in place (creates backup first!)
cp world_data/zone.yaml world_data/zone.yaml.bak
python merge_mud_files.py world_data/zone.yaml revisions.yaml --in-place
```

---

## Troubleshooting

### Problem: Entries Are Duplicated

**Cause**: Items don't have unique `id` fields.

**Solution**: Ensure all characters, objects, triggers have `id`:
```yaml
triggers:
  - id: unique_trigger_id    # Required!
    type: timer_tick
```

### Problem: Field Not Being Removed

**Cause**: Wrong removal syntax.

**Solution**: Use hyphen prefix:
```yaml
-fieldname: 0    # Correct - removes 'fieldname'
fieldname: null  # Wrong - sets fieldname to null
```

### Problem: List Keeps Extending

**Cause**: Default behavior extends lists.

**Solution**: Use `__list_strategy__: replace`:
```yaml
room:
  __list_strategy__: replace
  triggers:
    - id: only_trigger
```

### Problem: YAML Parse Error

**Cause**: Invalid YAML syntax.

**Solution**: 
- Validate at https://yamlvalidator.com/
- Check for tab characters (use spaces)
- Check for unquoted special characters
- Ensure consistent indentation (2 spaces)

### Problem: Comments Lost

**Cause**: `ruamel.yaml` not installed.

**Solution**: `pip install ruamel.yaml`

### Problem: Cross-Zone Reference Not Working

**Cause**: Incorrect syntax for cross-zone exits.

**Solution**: Use `zone_id.room_id` format:
```yaml
exits:
  north:
    destination: other_zone.target_room
```

---

## See Also

- [scripting-guide.md](scripting-guide.md) - Trigger scripting reference
- [character_yaml_template.md](character_yaml_template.md) - Character field reference
- [world_building_guide.md](world_building_guide.md) - Zone design guide
