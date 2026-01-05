# MUD Zone File Merger

A tool for managing incremental updates to MUD zone files using revision files. This allows you to maintain a clean base zone file while tracking changes, additions, and modifications in separate revision files.

**Key Feature**: Uses `ruamel.yaml` to preserve all comments in your YAML files!

## Table of Contents

- [Installation](#installation)
- [Overview](#overview)
- [Quick Start](#quick-start)
- [File Structure](#file-structure)
- [Revision Syntax](#revision-syntax)
  - [Adding New Content](#adding-new-content)
  - [Updating Existing Content](#updating-existing-content)
  - [Removing Content](#removing-content)
  - [Special Markers](#special-markers)
- [Section-by-Section Guide](#section-by-section-guide)
  - [ZONES Section](#zones-section)
  - [CHARACTERS Section](#characters-section)
  - [OBJECTS Section](#objects-section)
- [Examples](#examples)
- [Command Line Usage](#command-line-usage)
- [Best Practices](#best-practices)

---

## Installation

The merge tool requires `ruamel.yaml` for comment preservation:

```bash
pip install ruamel.yaml
```

Or install all project dependencies:

```bash
pip install -r requirements.txt
```

> **Note**: The tool will fall back to standard PyYAML if ruamel.yaml is not installed, but **comments will be lost**. You'll see a warning if this happens.

---

## Overview

The merge system allows you to:

1. **Keep base zone files clean** - Your original zone files remain readable and maintainable
2. **Track changes separately** - Revisions document what's been added or modified
3. **Merge incrementally** - Apply revisions to generate final zone files
4. **Support partial updates** - Only specify fields you want to change

### How It Works

```
┌─────────────────────┐     ┌─────────────────────┐
│   Base Zone File    │     │   Revisions File    │
│  (gloomy_graveyard  │  +  │  (revisions_gloomy  │
│      .yaml)         │     │   _graveyard.yaml)  │
└──────────┬──────────┘     └──────────┬──────────┘
           │                           │
           └───────────┬───────────────┘
                       ▼
              ┌────────────────┐
              │ merge_mud_files│
              │      .py       │
              └────────┬───────┘
                       ▼
           ┌───────────────────────┐
           │  Merged Output File   │
           │ (gloomy_graveyard_    │
           │    merged.yaml)       │
           └───────────────────────┘
```

---

## Quick Start

### 1. Create a Revision File

Create a new YAML file with only the changes you want to make:

```yaml
# revisions_my_zone.yaml
ZONES:
  my_zone:
    rooms:
      existing_room:
        # Add a new exit to an existing room
        exits:
          secret: { destination: hidden_chamber }
      
      # Add an entirely new room
      hidden_chamber:
        name: Hidden Chamber
        description: "A secret room behind the bookshelf."
        exits: { west: { destination: existing_room } }

CHARACTERS:
  - zone: my_zone
    characters:
      # Add a new NPC
      - id: mysterious_stranger
        name: Mysterious Stranger
        description: "A cloaked figure lurking in the shadows."
```

### 2. Run the Merger

```bash
cd NextGenMUDApp
python merge_mud_files.py ../world_data/my_zone.yaml revisions_my_zone.yaml ../world_data/my_zone_merged.yaml
```

### 3. Review and Replace

Check the merged output, then replace your original if satisfied:

```bash
# After reviewing my_zone_merged.yaml
mv ../world_data/my_zone_merged.yaml ../world_data/my_zone.yaml
```

---

## File Structure

### Base Zone File Structure

```yaml
ZONES:
  zone_id:
    name: Zone Name
    description: Zone description
    rooms:
      room_id:
        name: Room Name
        description: Room description
        exits:
          direction: { destination: other_room }
        triggers: [...]
        characters: [...]
        objects: [...]

CHARACTERS:
  - zone: zone_id
    characters:
      - id: character_id
        name: Character Name
        # ... other fields

OBJECTS:
  - zone: zone_id
    objects:
      - id: object_id
        name: Object Name
        # ... other fields
```

### Revision File Structure

Revision files follow the **exact same structure** but only include the parts you want to add or modify:

```yaml
ZONES:
  zone_id:
    # Only include sections you're changing
    rooms:
      room_id:
        # Only include fields you're adding/updating

CHARACTERS:
  - zone: zone_id
    characters:
      # Only include characters you're adding/updating
```

---

## Revision Syntax

### Adding New Content

Simply include the new content with a unique ID:

```yaml
# Add a new room
ZONES:
  my_zone:
    rooms:
      new_room:
        name: New Room
        description: "A freshly added room."
        exits:
          south: { destination: existing_room }

# Add a new character
CHARACTERS:
  - zone: my_zone
    characters:
      - id: new_npc
        name: New NPC
        description: "A brand new character."
        attributes:
          strength: 12
          dexterity: 14
```

### Updating Existing Content

Reference the existing ID and only specify fields to change:

```yaml
# Update an existing character (partial update)
CHARACTERS:
  - zone: my_zone
    characters:
      - id: existing_character
        # Only these fields will be updated:
        class:
          Fighter:
            level: 5          # Was level 2
            skills:
              power_attack: 80  # Add new skill
        permanent_flags:
          - new_flag          # Extends existing flags list
```

**Key behaviors:**
- **Dictionaries**: Deep merged (nested fields are merged recursively)
- **Lists**: Extended by default (new items added to end)
- **Scalars**: Replaced with new value

### Removing Content

Use the `-` prefix to remove fields, or `__remove__: true` to remove entire entries:

```yaml
# Remove a field from a character
CHARACTERS:
  - zone: my_zone
    characters:
      - id: existing_character
        class:
          Fighter:
            skills:
              -disarm: 0      # Remove the "disarm" skill (note the - prefix)

# Remove an entire character
CHARACTERS:
  - zone: my_zone
    characters:
      - id: character_to_delete
        __remove__: true

# Remove a room
ZONES:
  my_zone:
    rooms:
      room_to_delete:
        __remove__: true
```

### Special Markers

| Marker | Location | Effect |
|--------|----------|--------|
| `-fieldname` | Dict key | Removes `fieldname` from the dict |
| `__remove__: true` | Any dict with `id` | Removes that entire entry |
| `__replace__: true` | Any dict | Replaces entire dict instead of merging |
| `__list_strategy__: replace` | Dict containing lists | Child lists replace instead of extend |

#### Example: Replace Instead of Extend

```yaml
# Replace all triggers instead of adding to them
ZONES:
  my_zone:
    rooms:
      some_room:
        __list_strategy__: replace
        triggers:
          - id: only_trigger
            type: timer_tick
            # This will be the ONLY trigger, not added to existing
```

---

## Section-by-Section Guide

### ZONES Section

#### Adding Zone-Level Data

```yaml
ZONES:
  gloomy_graveyard:
    # Add common knowledge (merged with existing)
    common_knowledge:
      new_rumor: "Villagers speak of a hidden treasure."
    
    # Add quest variables (merged with existing)
    quest_variables:
      new_quest:
        found_treasure: { type: boolean, default: false }
```

#### Adding/Modifying Rooms

```yaml
ZONES:
  gloomy_graveyard:
    rooms:
      # Modify existing room - add new exit
      forest_road_s:
        exits:
          hidden: { destination: secret_grove, description: "A hidden path." }
        triggers:
          - id: new_trigger
            type: catch_any
            criteria: [{ subject: "%*%", operator: contains, predicate: "search" }]
            script: |
              echo You find something interesting!
      
      # Add new room
      secret_grove:
        name: Secret Grove
        description: "A hidden clearing in the forest."
        exits:
          east: { destination: forest_road_s }
```

#### Adding Characters/Objects to Rooms

```yaml
ZONES:
  gloomy_graveyard:
    rooms:
      existing_room:
        characters:
          - id: wandering_merchant
            quantity: 1
            respawn time min: 60
            respawn time max: 120
        objects:
          - id: treasure_chest
            quantity: 1
```

### CHARACTERS Section

#### Full New Character

```yaml
CHARACTERS:
  - zone: gloomy_graveyard
    characters:
      - id: grave_keeper
        name: Old Gregory
        article: ""
        description: "An ancient man with knowing eyes who tends the graves."
        group_id: graveyard_npcs
        attributes:
          strength: 8
          dexterity: 10
          constitution: 12
          intelligence: 14
          wisdom: 16
          charisma: 10
        class:
          Cleric:
            level: 3
        hit_dice: 3d8
        natural_attacks:
          - attack_noun: staff
            attack_verb: strikes
            potential_damage:
              - damage_type: bludgeoning
                damage_dice: 1d6
        hit_modifier: 1
        dodge_dice: 2d10+15
        experience_points: 75
```

#### Partial Character Update

```yaml
CHARACTERS:
  - zone: gloomy_graveyard
    characters:
      - id: werewolf
        # Update class level and add skills
        class:
          Fighter:
            level: 4
            skills:
              mighty_kick: 80
              -disarm: 0           # Remove disarm skill
        # Add new flags (extends existing list)
        permanent_flags:
          - darkvision
        # Update stats
        attributes:
          strength: 18            # Increase from 15
```

#### Character with LLM Conversation

```yaml
CHARACTERS:
  - zone: gloomy_graveyard
    characters:
      - id: lady_isabella
        name: Lady Isabella
        description: "A woman in black mourning clothes."
        attitude: WARY
        llm_conversation:
          personality: "You are grieving and suspicious of strangers."
          knowledge:
            - id: family_secret
              content: "Your uncle was murdered by someone in the household."
              reveal_threshold: 70
              is_secret: true
          goals:
            - id: find_ally
              condition: "Player offers to help find the killer"
              on_achieve_set_vars:
                gloomy_graveyard.murder_mystery.has_ally: true
```

### OBJECTS Section

#### Full New Object

```yaml
OBJECTS:
  - zone: gloomy_graveyard
    objects:
      - id: ancient_key
        name: ancient brass key
        article: an
        description: "A tarnished brass key with strange symbols."
        examine_text: "The symbols appear to be some kind of ward."
        object_flags:
          - is_key
        triggers:
          - id: use_on_crypt
            type: on_use
            criteria:
              - subject: "%target%"
                operator: eq
                predicate: "crypt_door"
            script: |
              echo The key turns with a grinding sound!
              unlock crypt_door
```

#### Object with Quest Integration

```yaml
OBJECTS:
  - zone: gloomy_graveyard
    objects:
      - id: lords_diary
        name: Lord Ashford's Diary
        description: "A leather-bound journal with a broken clasp."
        examine_text: "The final entry speaks of betrayal and a hidden will."
        triggers:
          - id: read_diary
            type: on_examine
            script: |
              setquestvar %S% murder_mystery.read_diary true
              echo You learn disturbing secrets about the Ashford family...
```

---

## Examples

### Example 1: Adding a Quest Line

```yaml
# revisions_murder_mystery.yaml
ZONES:
  gloomy_graveyard:
    quest_variables:
      murder_mystery:
        talked_to_witness: { type: boolean, default: false }
        found_evidence: { type: boolean, default: false }
        accused_butler: { type: boolean, default: false }
    
    rooms:
      inn_common_room:
        characters:
          - id: barnaby_witness
            quantity: 1

CHARACTERS:
  - zone: gloomy_graveyard
    characters:
      - id: barnaby_witness
        name: Barnaby
        description: "The town drunk, nursing a mug of ale."
        llm_conversation:
          personality: "Drunk and rambling, but you saw something important."
          knowledge:
            - id: saw_butler
              content: "Saw a tall man in butler's uniform at the graveyard at midnight."
              reveal_threshold: 30
```

### Example 2: Buffing Enemies

```yaml
# revisions_difficulty_increase.yaml
CHARACTERS:
  - zone: gloomy_graveyard
    characters:
      - id: werewolf
        class:
          Fighter:
            level: 4
        hit_dice: 4d8+4
        natural_attacks:
          - attack_noun: bite
            attack_verb: savages
            potential_damage:
              - damage_type: piercing
                damage_dice: 2d6+2
        experience_points: 100
      
      - id: vampire
        class:
          Fighter:
            level: 4
        permanent_flags:
          - regenerates
        experience_points: 120
```

### Example 3: Adding Secret Areas

```yaml
# revisions_secret_areas.yaml
ZONES:
  gloomy_graveyard:
    rooms:
      manor_house_library:
        triggers:
          - id: find_secret_door
            type: catch_any
            criteria:
              - subject: "%*%"
                operator: contains
                predicate: "bookshelf"
            script: |
              $if($questvar(%S%,secrets.found_library_door), !=, true){
                echo You notice one book doesn't quite fit...
                setquestvar %S% secrets.found_library_door true
              }
        exits:
          secret:
            destination: hidden_study
            description: "A gap behind the bookshelf leads to darkness."
      
      hidden_study:
        name: Hidden Study
        description: >
          A small, dusty room hidden behind the library bookshelf. 
          Ancient texts and forbidden tomes line the walls.
        exits:
          out: { destination: manor_house_library }
        objects:
          - id: forbidden_tome
            quantity: 1

OBJECTS:
  - zone: gloomy_graveyard
    objects:
      - id: forbidden_tome
        name: forbidden tome
        article: a
        description: "A book bound in suspicious leather."
        examine_text: "The pages contain dark rituals..."
```

---

## Command Line Usage

```bash
# Basic usage
python merge_mud_files.py <base_file> <revisions_file> [output_file]

# Examples:
# Merge and create new file
python merge_mud_files.py ../world_data/gloomy_graveyard.yaml revisions_gloomy_graveyard.yaml ../world_data/gloomy_graveyard_merged.yaml

# Auto-generate output name (creates gloomy_graveyard_merged.yaml)
python merge_mud_files.py ../world_data/gloomy_graveyard.yaml revisions_gloomy_graveyard.yaml

# Modify in place (dangerous - no backup!)
python merge_mud_files.py ../world_data/gloomy_graveyard.yaml revisions_gloomy_graveyard.yaml --in-place
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `base_file` | Yes | Path to the original zone YAML file |
| `revisions_file` | Yes | Path to the revisions YAML file |
| `output_file` | No | Output path (default: `{base}_merged.yaml`) |
| `--in-place, -i` | No | Modify base file directly (use with caution!) |

---

## Comment Preservation

This tool uses `ruamel.yaml` to preserve all comments from your base file:

```yaml
# Zone-level comment about the graveyard theme
ZONES:
  gloomy_graveyard:
    rooms:
      forest_road_s:
        name: South Dark Forest Road
        description: >
          A narrow path...  # Inline comments preserved too
        triggers:
          # This trigger fires when player howls
          - id: catch_any_howl
            type: catch_any
```

**What gets preserved:**
- Block comments (`# comment on its own line`)
- Inline comments (`field: value  # comment after value`)
- Comment positioning and alignment
- Blank lines between sections

**What gets added from revisions:**
- New content is inserted without comments (add them to the merged file afterward)
- The revision file's comments are NOT transferred to the output

---

## Best Practices

### 1. One Revision File Per Feature

Keep revisions organized by feature or quest:
```
revisions_murder_mystery.yaml
revisions_hidden_areas.yaml
revisions_npc_dialogue.yaml
revisions_difficulty_balance.yaml
```

### 2. Always Review Before Replacing

```bash
# Generate merged file
python merge_mud_files.py base.yaml revisions.yaml merged.yaml

# Review the changes
diff base.yaml merged.yaml

# Only then replace
mv merged.yaml base.yaml
```

### 3. Use Version Control

Commit both base files AND revision files to git:
```bash
git add world_data/gloomy_graveyard.yaml
git add NextGenMUDApp/revisions_gloomy_graveyard.yaml
git commit -m "Add murder mystery quest to graveyard"
```

### 4. Keep Base Files Clean

After merging, you can either:
- **Keep revisions separate**: Useful during development
- **Consolidate into base**: After feature is stable, merge and delete revision file

### 5. Use Meaningful IDs

```yaml
# Good - descriptive IDs
- id: murder_mystery_clue_01
- id: lady_isabella_mourner
- id: secret_passage_trigger

# Bad - generic IDs
- id: trigger1
- id: npc2
- id: item_new
```

### 6. Document Complex Triggers

```yaml
triggers:
  - id: quest_completion_check
    # This trigger fires when player has all evidence
    # and accuses the butler in the dining room
    type: catch_any
    criteria:
      - subject: "%*%"
        operator: contains
        predicate: "accuse butler"
      - subject: "$questvar(%S%,murder_mystery.found_evidence)"
        operator: eq
        predicate: "true"
    script: |
      echo Edmund's face goes pale...
```

---

## Troubleshooting

### Common Issues

**Problem**: Duplicate entries after merge
**Cause**: Item doesn't have an `id` field
**Solution**: Ensure all characters, objects, and triggers have unique `id` fields

**Problem**: Fields not being removed
**Cause**: Wrong syntax for removal
**Solution**: Use `-fieldname: 0` (note the hyphen prefix)

**Problem**: List being extended when you want replacement
**Solution**: Add `__list_strategy__: replace` to the parent dict

**Problem**: YAML parsing errors
**Solution**: Validate your YAML at https://yamlvalidator.com/ before merging

---

## See Also

- [README-SCRIPTING.md](README-SCRIPTING.md) - Trigger scripting reference
- [documentation/character_yaml_template.md](documentation/character_yaml_template.md) - Character definition reference
