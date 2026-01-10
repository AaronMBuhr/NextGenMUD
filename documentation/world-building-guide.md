# NextGenMUD World Building Guide

A comprehensive guide to creating zones, rooms, characters, objects, triggers, and quests for NextGenMUD.

---

## Table of Contents

1. [File Structure](#file-structure)
2. [Zone Definition](#zone-definition)
3. [Rooms](#rooms)
4. [Characters (NPCs)](#characters-npcs)
5. [Objects](#objects)
6. [Consumable Items](#consumable-items)
7. [Triggers](#triggers)
8. [LLM-Driven NPCs](#llm-driven-npcs)
9. [Quest System](#quest-system)
10. [Combat System](#combat-system)
11. [Resource System](#resource-system)
12. [Scripting Language](#scripting-language)
13. [Variable Reference](#variable-reference)
14. [Complete Examples](#complete-examples)

---

## File Structure

World data files are YAML files stored in the `world_data/` directory.

```
world_data/
├── central_city.yaml      # A zone file
├── enchanted_forest.yaml  # Another zone file
├── gloomy_graveyard.yaml  # Zone with quest example
└── debug_zone.yaml        # Testing zone
```

Each zone file contains all data for that zone: the zone definition, rooms, characters, and objects.

### File Organization Pattern

```yaml
ZONES:
  zone_id:
    name: Zone Name
    description: Zone description
    common_knowledge: {...}
    quest_variables: {...}
    rooms:
      room_id: {...}
      room_id2: {...}

CHARACTERS:
  - zone: zone_id
    characters:
      - id: char_id
        {...}

OBJECTS:
  - zone: zone_id
    objects:
      - id: obj_id
        {...}
```

---

## Zone Definition

The zone is the top-level container for a geographic area.

### Basic Zone Structure

```yaml
ZONES:
  gloomy_graveyard:                    # Zone ID (used in references)
    name: Gloomy Graveyard             # Display name
    description: >                      # Zone description (for builders)
      A gloomy graveyard and its surrounds, including a dark forest,
      a manor house, a crypt, and an inn.
```

### Common Knowledge

Zone-level information that NPCs can know about. Referenced by ID in NPC definitions.

```yaml
    common_knowledge:
      murder_case: >
        Lord Ashford was found murdered in the graveyard a few days ago.
        The gravedigger Old Tom is the prime suspect.
      village_mood: >
        Everyone is on edge since the murder. Strangers are viewed with suspicion.
      local_geography: >
        The Weary Traveler Inn sits on the forest road. The graveyard is to the 
        north and then east from the inn. Ashford Manor is east along the road.
```

NPCs reference common knowledge by ID:
```yaml
      common_knowledge_refs:
        - murder_case
        - village_mood
        - local_geography
```

### Quest Variables

Define quest-related variables with automatic knowledge updates.

```yaml
    quest_variables:
      murder_mystery:                    # Quest namespace
        found_body:                      # Variable name
          description: "Player has discovered Lord Ashford's body"
          type: boolean
          default: false
          knowledge_updates:             # When variable changes, update knowledge
            - condition: true            # When set to true
              updates:
                murder_case: >           # Override this common knowledge
                  You discovered Lord Ashford's body in the graveyard. He was
                  strangled, and his fine clothes were torn.
```

**Variable Types:**
- `boolean` - true/false
- `string` - text value
- `integer` - numeric value

---

## Rooms

Rooms are locations within a zone where players and NPCs can exist.

### Basic Room Structure

```yaml
    rooms:
      forest_road_s:                     # Room ID (unique within zone)
        name: South Dark Forest Road    # Display name
        description: >                   # Room description (shown on look)
          A narrow, winding path shrouded in shadows. The dense canopy 
          overhead allows only slivers of moonlight to penetrate.
          
          Exits: north, south
```

### Exits

Exits connect rooms. Can be simple strings or complex objects with doors.

#### Simple Exits

```yaml
        exits:
          north: forest_road_mid              # Same zone
          south: enchanted_forest.misty_copse # Different zone (zone.room)
```

#### Exits with Descriptions

```yaml
        exits:
          north:
            destination: forest_road_mid
            description: The path winds deeper into the dark forest.
          south:
            destination: enchanted_forest.misty_copse
            description: Through the trees, you glimpse a misty copse.
```

When players do `look north`, they see the description.

#### Exits with Doors

```yaml
        exits:
          south:
            destination: manor_house_kitchen
            description: A heavy door leads to the wine cellar.
            door:
              name: cellar door           # Door's display name
              keywords: [door, cellar]    # What players can call it
              is_closed: true             # Starts closed
              is_locked: true             # Starts locked
              key_id: cellar_key          # Object ID that unlocks it
              linked_exit: gloomy_graveyard.manor_house_kitchen.south
              # ^ When this door is unlocked, the linked door is too
```

**Door Properties:**
| Property | Type | Description |
|----------|------|-------------|
| name | string | Display name ("the cellar door") |
| keywords | list | Words players can use to reference it |
| is_closed | boolean | Whether door is currently closed |
| is_locked | boolean | Whether door is currently locked |
| key_id | string | Object ID required to unlock (optional) |
| linked_exit | string | Format: `zone.room.direction` - syncs lock state |

### Room Permanent Flags

```yaml
        permanent_flags:
          - dark           # Requires light to see
          - no_mob         # NPCs won't wander here
          - indoors        # Protected from weather
          - no_magic       # Magic doesn't work
          - no_summon      # Can't be summoned to/from
          - flight_needed  # Must be flying to enter
          - underwater     # Underwater room
```

### Spawning Characters in Rooms

```yaml
        characters:
          - id: zombie              # Character ID from CHARACTERS section
            quantity: 2             # Spawn 2 zombies
            respawn time min: 60    # Minimum seconds before respawn
            respawn time max: 90    # Maximum seconds before respawn
          
          - id: barkeep             # Unique NPC - no respawn
            quantity: 1             # Omit respawn times for permanent NPCs
```

**Respawn Rules:**
- NPCs with respawn times will respawn when killed
- NPCs without respawn times are permanent (and unkillable)
- Use for quest-critical NPCs like innkeepers, quest givers

### Spawning Objects in Rooms

```yaml
        objects:
          - id: torn_note
            quantity: 1
```

### Room Triggers

See [Triggers](#triggers) section for full details.

```yaml
        triggers:
          - id: catch_any_howl
            type: catch_any
            criteria:
              - subject: "%*%"
                operator: contains
                predicate: "howl"
            script: |
              echo A distant howl echoes through the trees.
```

---

## Characters (NPCs)

Characters are NPCs (non-player characters) that populate the world.

### Basic Character Structure

```yaml
CHARACTERS:
  - zone: gloomy_graveyard
    characters:
      - id: zombie                     # Unique ID within zone
        name: shambling zombie         # Display name
        article: a                     # "a", "an", or "" for named NPCs
        keywords:                      # Words players can use
          - zombie
          - undead
          - shambling
        description: >                 # Shown on "look zombie"
          A rotting corpse shambles about, its dead eyes staring blankly.
        pronoun_subject: it            # he/she/it/they
        pronoun_object: it             # him/her/it/them
        pronoun_possessive: its        # his/her/its/their
```

### Attributes

```yaml
        attributes:
          strength: 14       # Physical power, melee damage
          dexterity: 8       # Speed, accuracy, dodge
          constitution: 16   # Health, stamina
          intelligence: 4    # Magic power, learning
          wisdom: 4          # Perception, willpower
          charisma: 2        # Social influence
```

### Class and Level

```yaml
        class:
          Fighter:
            level: 3
          # Multi-classing:
          # Rogue:
          #   level: 2
```

**Available Classes:** Fighter, Mage, Cleric, Rogue

### Skills

NPCs automatically receive skills appropriate for their class and level. You can also explicitly specify skills or override auto-assigned ones.

#### Automatic Skill Assignment

When you specify a class and level, the NPC automatically gains all skills that class has access to at that level. For example, a level 5 Fighter gets all Tier 1 fighter skills.

#### Explicit Skill Specification

```yaml
        class:
          Fighter:
            level: 5
            skills:
              mighty_kick: 80          # Override skill level
              demoralizing_shout: 60   # Override skill level
              -cleave: 0               # Remove this skill (prefix with -)
```

#### Standalone Skills List

You can also use a flat skills list:

```yaml
        skills:
          - skill: mighty kick
            level: 80
          - skill: demoralizing shout
            level: 80
```

**Skill Level:** 1-100, representing proficiency. Higher levels improve success rates.

### NPC Guards

NPCs can guard specific rooms, blocking player access until certain conditions are met.

```yaml
        guards_rooms:
          - gloomy_graveyard.throne_room
          - gloomy_graveyard.treasure_vault
```

**Guard Behavior:**
- Guards check if they can see the player (invisibility matters)
- Incapacitated or dead guards cannot block
- Players can potentially talk their way past guards (via LLM conversations)
- Guards block entry from any direction, not just specific exits

### Combat Stats

```yaml
        hit_dice: 2d8+4          # Health = roll 2d8 + 4
        natural_attacks:         # Attacks without weapons
          - attack_noun: claw
            attack_verb: claws
            potential_damage:
              - damage_type: slashing
                damage_dice: 1d6
              - damage_type: poison    # Can have multiple damage types
                damage_dice: 1d4
        hit_modifier: 2          # Bonus to hit rolls
        dodge_dice: 2d20+10      # Defense roll
        critical_chance: 0.05    # 5% crit chance
        critical_multiplier: 2   # Double damage on crit
        experience_points: 50    # XP awarded when killed
```

**Damage Types:**
- Physical: `slashing`, `piercing`, `bludgeoning`
- Elemental: `fire`, `cold`, `lightning`, `acid`
- Magical: `arcane`, `holy`, `unholy`, `psychic`, `force`
- Special: `poison`, `necrotic`, `radiant`

### Permanent Flags

```yaml
        permanent_flags:
          - is_aggressive         # Attacks players on sight
          - can_dual_wield       # Can wield two weapons
          - is_invisible         # Hidden until player has see_invisible
          - see_invisible        # Can see invisible entities
          - darkvision           # Can see in dark rooms
          - is_undead            # Undead creature type
          - is_sentinel          # Guards a location
          - no_wander            # Won't wander between rooms
          - stationary           # Completely immobile
          - evasive              # Tends to flee from combat
          - quest_giver          # Offers quests to players
          - aggressive_if_attacked  # Attacks only if attacked first
          - mindless             # No intelligence, cannot be reasoned with
          - cowardly             # Tends to flee when wounded
          - protected            # Cannot be directly attacked
```

### Damage Multipliers

Specify damage multipliers. A value of `1` is normal damage, `0` is immune, `0.5` is 50% damage taken (resistant), `2` is double damage (vulnerable).

```yaml
        damage_multipliers:
          fire: 0.5       # Takes 50% fire damage (resistant)
          cold: 2         # Takes 200% cold damage (vulnerable)
          poison: 0       # Immune to poison damage
          slashing: 0.75  # 75% damage taken (25% reduction)
```

**Available Damage Types:**
- Physical: `slashing`, `piercing`, `bludgeoning`
- Elemental: `fire`, `cold`, `lightning`, `acid`
- Magical: `arcane`, `holy`, `unholy`, `psychic`, `force`
- Special: `poison`, `disease`, `necrotic`, `radiant`, `raw`

### Saving Throw Bonuses

Percentage bonuses applied to saving throws. These bonuses are applied AFTER the normal 5-95% clamping, allowing values to exceed the normal limits. A bonus of `100` means automatic success (immune to that save type).

```yaml
        saving_throw_bonuses:
          will: 100       # Immune to will saves (charm, fear, etc.)
          fortitude: 50   # +50% bonus to fortitude saves
          reflex: 25      # +25% bonus to reflex saves
```

**Saving Throw Types:**
| Save Type | Associated Attribute | Used Against |
|-----------|---------------------|--------------|
| `fortitude` | Constitution | Poison, disease, physical effects |
| `reflex` | Dexterity | Area effects, dodging |
| `will` | Wisdom | Charm, fear, mental effects |

**Example - Undead Construct:**
```yaml
        permanent_flags:
          - is_undead
          - is_aggressive
        damage_multipliers:
          poison: 0       # Immune to poison
          necrotic: 0.5   # Resistant to necrotic
          radiant: 2      # Vulnerable to radiant
        saving_throw_bonuses:
          will: 100       # Immune to charm/fear (mindless)
          fortitude: 50   # Bonus vs physical effects
```

### Attitude

Determines how the NPC behaves toward players.

```yaml
        attitude: NEUTRAL
```

**Attitude Values:**
| Attitude | Behavior |
|----------|----------|
| HOSTILE | Attacks players on sight |
| UNFRIENDLY | Won't attack first, won't help, may join against player |
| NEUTRAL | Default - no special behavior |
| FRIENDLY | Won't attack, may help player in combat |
| WARY | Cautious, may flee or refuse interaction |

### Group ID

NPCs with the same group_id will assist each other in combat.

```yaml
        group_id: graveyard_undead
```

### Starting Equipment

```yaml
        starting_equipment:
          main_hand: rusty_sword
          body: leather_armor
        starting_inventory:
          - health_potion
          - gold_coins
```

---

## Objects

Objects are items that can be picked up, used, or interacted with.

### Basic Object Structure

```yaml
OBJECTS:
  - zone: gloomy_graveyard
    objects:
      - id: torn_note                  # Unique ID within zone
        name: torn note                # Display name
        article: a                     # "a", "an", or "the"
        keywords:                      # Words to reference it
          - note
          - paper
          - letter
        description: >                 # Shown on "look note"
          A piece of expensive stationery, torn roughly.
        examine_text: >                # Additional detail on close examination
          The note reads: "...hereby dismiss you from service..."
```

### Object Permanent Flags

```yaml
        permanent_flags:
          - is_armor          # Wearable armor
          - is_weapon         # Usable as weapon
          - is_container      # Can hold other objects
          - no_take           # Cannot be picked up
          - is_static         # Part of the room, immovable
          - openable          # Can be opened/closed
          - closed            # Starts closed
          - lockable          # Can be locked/unlocked
          - locked            # Starts locked
          - hidden            # Hidden until found
          - door              # Is a door object
          - takeable          # Can be picked up
          - stationary        # Cannot be moved
          - container         # Alias for is_container
          - dangerous         # Potentially harmful to use
```

### Weapons

```yaml
      - id: rusty_sword
        name: rusty sword
        article: a
        keywords: [sword, rusty]
        description: A battered blade showing signs of neglect.
        permanent_flags:
          - is_weapon
        equip_location: main_hand
        damage_dice: 1d6
        damage_type: slashing
        attack_verb: slashes
        attack_noun: sword
```

**Equip Locations:**
- `main_hand`, `off_hand`, `both_hands` - Weapons
- `head`, `neck`, `shoulders`, `arms`, `wrists`, `hands` - Upper body
- `left_finger`, `right_finger` - Rings
- `waist`, `legs`, `feet` - Lower body
- `body`, `back` - Torso
- `eyes` - Eyewear

### Armor

```yaml
      - id: leather_armor
        name: leather armor
        article: ""
        keywords: [leather, armor]
        description: Simple but serviceable protection.
        permanent_flags:
          - is_armor
        equip_location: body
        armor_value: 2
        armor_type: light
```

### Containers

```yaml
      - id: old_chest
        name: old wooden chest
        article: an
        keywords: [chest, wooden]
        description: An old wooden chest with a heavy lock.
        permanent_flags:
          - is_container
          - openable
          - closed
          - lockable
          - locked
        key_id: chest_key            # Object ID that unlocks it
```

**Container Commands:**
- `open chest` / `close chest`
- `lock chest` / `unlock chest`
- `put item in chest` / `get item from chest`

### Usable Objects

Objects with `on_use` triggers:

```yaml
      - id: magic_wand
        name: magic wand
        article: a
        keywords: [wand, magic]
        description: A slender wand that crackles with energy.
        triggers:
          - id: use_wand
            type: on_use
            script: |
              echo The wand crackles and a bolt of energy shoots out!
              damage %T% 10 lightning
```

---

## Consumable Items

Consumable items are objects that can be used once (or a limited number of times) to provide healing, restore resources, or other effects. These use built-in mechanics rather than requiring custom triggers.

### Healing Potions

```yaml
      - id: healing_potion
        name: healing potion
        article: a
        keywords: [potion, healing, red]
        description: A red potion that smells of herbs.
        object_flags:
          - is_consumable
          - is_potion
        heal_amount: 25              # Fixed healing amount
        use_message: "You drink the healing potion and feel warmth spread through you."
```

### Dice-Based Healing

```yaml
      - id: greater_healing_potion
        name: greater healing potion
        article: a
        keywords: [potion, healing, greater]
        description: A larger vial of potent healing liquid.
        object_flags:
          - is_consumable
          - is_potion
        heal_dice: 4d8+4             # Roll for healing amount
        use_message: "You drink the greater healing potion!"
```

### Mana Potions

```yaml
      - id: mana_potion
        name: mana potion
        article: a
        keywords: [potion, mana, blue]
        description: A shimmering blue potion.
        object_flags:
          - is_consumable
          - is_potion
        mana_restore: 30             # Restores mana for casters
        use_message: "You drink the mana potion and feel your magical reserves replenish."
```

### Bandages

```yaml
      - id: bandage
        name: linen bandage
        article: a
        keywords: [bandage, linen]
        description: Clean linen strips for binding wounds.
        object_flags:
          - is_consumable
          - is_bandage
        heal_dice: 1d8+2
        use_message: "You carefully apply the bandage to your wounds."
```

### Multi-Use Items

```yaml
      - id: medkit
        name: medical kit
        article: a
        keywords: [medkit, kit, medical]
        description: A well-stocked medical kit.
        object_flags:
          - is_consumable
          - is_bandage
        heal_dice: 2d6+4
        charges: 5                   # Can be used 5 times
        use_message: "You treat your wounds with supplies from the medical kit."
```

### Food

```yaml
      - id: bread
        name: loaf of bread
        article: a
        keywords: [bread, loaf, food]
        description: A crusty loaf of fresh bread.
        object_flags:
          - is_consumable
          - is_food
        heal_amount: 5               # Minor healing from food
        stamina_restore: 10          # Restores stamina
        use_message: "You eat the bread, feeling somewhat restored."
```

### Consumable Object Flags

| Flag | Description |
|------|-------------|
| `is_consumable` | Item is consumed on use |
| `is_potion` | Used with `quaff` or `drink` command |
| `is_bandage` | Used with `apply` command |
| `is_food` | Used with `eat` command |

### Consumable Properties

| Property | Type | Description |
|----------|------|-------------|
| `heal_amount` | integer | Fixed HP healing |
| `heal_dice` | string | Dice roll for HP healing (e.g., "2d8+4") |
| `mana_restore` | integer | Mana points restored |
| `stamina_restore` | integer | Stamina points restored |
| `charges` | integer | Number of uses (default: 1) |
| `use_message` | string | Message shown when item is used |

**Player Commands:**
- `quaff potion` or `drink potion` - Use potions
- `apply bandage` - Use bandages
- `eat bread` - Consume food
- `use item` - Generic use (works for all types)

---

## Triggers

Triggers are event-driven scripts that execute when conditions are met.

### Trigger Structure

```yaml
        triggers:
          - id: unique_trigger_id      # Must be unique to this entity
            type: trigger_type         # See types below
            disabled: false            # Optional, default false
            flags:                      # Optional trigger execution flags
              - only_when_pc_room
            criteria:                   # Conditions to check
              - subject: "%value%"
                operator: eq
                predicate: "expected"
            script: |
              # Commands to execute
              say Hello there!
```

### Trigger Types

| Type | Fires When | Available On |
|------|------------|--------------|
| `on_enter` | Character enters room | Room, NPC, Object |
| `on_exit` | Character leaves room | Room, NPC, Object |
| `catch_say` | Someone speaks | Room, NPC |
| `catch_look` | Someone looks at entity | Object, NPC |
| `catch_any` | Any text matches criteria | Room, NPC |
| `timer_tick` | Periodic (every ~0.5 sec if conditions met) | Any |
| `on_receive` | NPC receives item via give | NPC |
| `on_get` | Object is picked up | Object |
| `on_drop` | Object is dropped | Object |
| `on_open` | Object is opened | Object |
| `on_close` | Object is closed | Object |
| `on_lock` | Object is locked | Object |
| `on_unlock` | Object is unlocked | Object |
| `on_use` | Object is used | Object |

### Trigger Flags

Trigger flags control when triggers can fire. Note: These are specific trigger execution flags, separate from permanent/temporary flags.

```yaml
            flags:
              - only_when_pc_room     # Only fires if a player is present in room
              - only_when_pc_zone     # Only fires if player is in zone
```

### Criteria

Criteria are conditions that must ALL be true for the trigger to fire.

```yaml
            criteria:
              - subject: "%*%"             # The text/value to check
                operator: contains         # How to compare
                predicate: "hello"         # What to compare against
```

**Operators:**

| Operator | Description | Example |
|----------|-------------|---------|
| `eq` | Equals (string) | `subject: "hello"` eq `predicate: "hello"` |
| `neq` or `!=` | Not equals | `subject: "a"` != `predicate: "b"` |
| `contains` | Subject contains predicate | `"hello world"` contains `"world"` |
| `numeq` | Numeric equals | `5` numeq `5` |
| `numneq` | Numeric not equals | `5` numneq `3` |
| `numlt` | Less than | `3` numlt `5` |
| `numgt` | Greater than | `5` numgt `3` |
| `numlte` | Less than or equal | `5` numlte `5` |
| `numgte` | Greater than or equal | `5` numgte `5` |
| `between` | Value between two numbers | Requires 3-part check |

### Trigger Examples

#### On Enter - NPC Greets Player

```yaml
          - id: greet_player
            type: on_enter
            criteria:
              - subject: "$permvar(%S%,has_been_greeted)"
                operator: "!="
                predicate: "true"
            script: |
              setpermvar char %S% has_been_greeted true
              pause 0.5
              echo The innkeeper waves at you warmly.
              say Welcome, traveler! What can I get you?
```

#### Timer Tick - Ambient Events

```yaml
          - id: ambient_wind
            type: timer_tick
            criteria:
              - subject: "%time_elapsed%"
                operator: "numgte"
                predicate: 30          # At least 30 seconds since last tick
            script: |
              echo A cold wind whistles through the trees.
```

#### Catch Say - React to Keywords

```yaml
          - id: react_to_murder
            type: catch_say
            criteria:
              - subject: "%*%"
                operator: contains
                predicate: "murder"
            script: |
              pause 0.3
              echo The innkeeper's face grows serious.
              say Terrible business, that. Just terrible.
```

#### On Get - React to Pickup

```yaml
          - id: pickup_evidence
            type: on_get
            script: |
              echo The cold metal feels significant in your hand.
              setquestvar %S% murder_mystery.has_evidence true
```

#### On Receive - NPC Gets Item

```yaml
          - id: receive_cufflink
            type: on_receive
            criteria:
              - subject: "%item_id%"
                operator: "eq"
                predicate: "butler_cufflink"
            script: |
              echo Maggie's eyes widen as she examines the cufflink.
              say This... this is Edmund's! Where did you find this?
              setquestvar %S% murder_mystery.exposed_butler true
```

---

## LLM-Driven NPCs

NPCs can have LLM-powered conversations for dynamic, natural dialogue.

### LLM Configuration

```yaml
        llm_conversation:
          personality: >
            You are Maggie, the barkeep of the Weary Traveler inn. You're 
            friendly but shrewd. You're worried about Old Tom and don't
            believe he's the murderer.
          speaking_style: >
            Speaks with warmth but also directness. Uses colorful expressions.
            Sometimes lowers voice conspiratorially when sharing rumors.
          
          knowledge:                      # Things this NPC knows
            - id: murder_details
              content: >
                Lord Ashford was found in the graveyard, strangled.
              reveal_threshold: 30        # Disposition needed to share
              is_secret: false            # If true, only reveals at threshold
            
            - id: butler_argument
              content: >
                The butler Edmund argued with Lord Ashford about money.
              reveal_threshold: 60
              is_secret: true             # Won't share unless trusted
          
          goals:                          # What NPC is trying to accomplish
            - id: point_to_tom
              description: "Suggest the player talk to Old Tom"
              condition: "Player asks about the murder"
              on_achieve_set_vars:
                gloomy_graveyard.murder_mystery.heard_about_murder: true
              on_achieve_message: "You've learned about the murder."
            
            - id: reveal_butler_secret
              description: "Hint about the butler"
              condition: "Player gains trust and asks probing questions"
              disposition_required: 65    # Must reach this disposition first
              on_achieve_set_vars:
                gloomy_graveyard.murder_mystery.suspects_butler: true
          
          will_discuss:                   # Topics NPC will talk about
            - the murder
            - Old Tom
            - local gossip
            - drinks and food
          
          will_not_discuss:               # Topics NPC refuses to discuss
            - her own past
            - prices of secrets
          
          common_knowledge_refs:          # References to zone common knowledge
            - murder_case
            - village_mood
            - local_geography
```

### LLM Disposition System

- Disposition ranges from 0-100
- 0 = hostile, 50 = neutral, 100 = devoted
- Disposition changes based on player interactions
- Higher disposition unlocks secret knowledge and goals

### Player Commands for LLM NPCs

```
sayto maggie hello          # Start/continue conversation
tell maggie about the murder  # Same effect if in same room
ask maggie where is the graveyard  # Same effect with different message
```

---

## Quest System

Quests are built using quest variables, triggers, and LLM goals.

### Quest Variable Flow

1. Define variables in zone `quest_variables`
2. Set variables via triggers or LLM goals
3. Variables can update common knowledge automatically
4. Check variables in trigger criteria

### Example Quest Setup

```yaml
    quest_variables:
      murder_mystery:
        found_body:
          description: "Player discovered the body"
          type: boolean
          default: false
          knowledge_updates:
            - condition: true
              updates:
                murder_case: >
                  You discovered Lord Ashford's body...
```

```yaml
    # In object triggers:
          - id: discover_body
            type: catch_look
            script: |
              setquestvar %S% murder_mystery.found_body true
              echo You've found Lord Ashford's body!
```

```yaml
    # In NPC triggers - check quest state:
          - id: react_if_body_found
            type: on_enter
            criteria:
              - subject: "$questvar(%S%,murder_mystery.found_body)"
                operator: "eq"
                predicate: "true"
            script: |
              say I heard you found the body. Terrible...
```

---

## Combat System

### Flee Mechanics

Players can attempt to flee from combat using the `flee` command. Success depends on:

- **Dexterity** - Higher DEX improves flee chance
- **Rogue levels** - Rogues are better at escaping
- **Current HP** - Harder to flee when badly wounded
- **Number of attackers** - More enemies = harder to escape
- **Character state** - Cannot flee while stunned or sitting

When fleeing, the player exits through a random unguarded exit.

### Guard Blocking

NPCs designated as guards will block player movement into rooms they guard:

```yaml
        guards_rooms:
          - zone.throne_room
          - zone.treasure_vault
```

**Guard Checks:**
1. Can the guard see the player? (invisibility, darkness)
2. Is the guard incapacitated? (stunned, sleeping, dead)
3. Has the player been granted passage? (via LLM conversation)

Players can potentially convince guards to let them pass through roleplay with LLM-enabled NPCs. When a guard grants passage, a variable is set that persists.

### Player Death

When a player dies:

1. **Corpse Creation** - A corpse object is created in the room
2. **Inventory Transfer** - Non-equipped items drop to the corpse
3. **Equipment Retention** - Equipped gear stays on the player
4. **XP Penalty** - 5% XP loss (cannot cause de-leveling)
5. **Respawn** - Player respawns at the start room with full HP

**Corpse Properties:**
- Contains the player's dropped inventory
- Only the owner can loot their corpse
- Decays after 30 minutes (items are lost)

This creates meaningful death penalties while not being overly punishing.

### NPC Combat AI

NPCs with class levels will automatically use their skills in combat based on AI properties defined on each skill:

| Property | Description |
|----------|-------------|
| `ai_priority` | Base priority (0-100, higher = more likely to use) |
| `ai_condition` | When to consider using the skill |
| `skill_type` | Classification of the skill effect |
| `requires_target` | Whether a target is needed |

**AI Conditions:**
- `always` - Always consider this skill
- `self_hp<25` - Use when self HP below 25%
- `self_hp<50` - Use when self HP below 50%
- `target_hp<25` - Use when target HP below 25%
- `target_not_stunned` - Only if target isn't already stunned
- `in_combat` - Only while fighting

**Skill Types:**
- `damage` - Direct damage abilities
- `heal_self` - Self-healing
- `stun` - Stun/incapacitate effects
- `debuff` - Weakening effects
- `buff_self` - Self-enhancement
- `stance` - Combat stance changes

NPCs queue their actions through the command system, respecting action timing and cooldowns just like players.

---

## Resource System

### Mana

Mana is the resource used for magical abilities (Mage and Cleric spells).

**Calculation:**
- Mages: `MANA_PER_LEVEL_MAGE × Mage Level`
- Clerics: `MANA_PER_LEVEL_CLERIC × Cleric Level`
- Modified by Intelligence attribute

**Regeneration Rates:**
| State | Rate |
|-------|------|
| In Combat | Very slow (MANA_REGEN_COMBAT) |
| Walking | Moderate (MANA_REGEN_WALKING) |
| Resting/Sitting | Faster (MANA_REGEN_RESTING) |
| Meditating | Fastest (MANA_REGEN_MEDITATING) |

### Stamina

Stamina is the resource used for physical combat abilities (Fighter and Rogue skills).

**Calculation:**
- Fighters: `STAMINA_PER_LEVEL_FIGHTER × Fighter Level`
- Rogues: `STAMINA_PER_LEVEL_ROGUE × Rogue Level`
- Clerics also get some stamina
- Modified by Constitution attribute

**Regeneration Rates:**
| State | Rate |
|-------|------|
| In Combat | Moderate (STAMINA_REGEN_COMBAT) |
| Walking | Moderate (STAMINA_REGEN_WALKING) |
| Resting/Sitting | Faster (STAMINA_REGEN_RESTING) |

### HP Regeneration

Hit points regenerate based on character state:

| State | Rate |
|-------|------|
| In Combat | None (HP_REGEN_COMBAT = 0) |
| Walking | Slow (HP_REGEN_WALKING) |
| Resting/Sitting | Moderate (HP_REGEN_RESTING) |
| Sleeping | Fastest (HP_REGEN_SLEEPING) |

### Meditation

Players can enter a meditation state to regenerate mana faster:

```
meditate    # Begin meditating (must be sitting)
stand       # Interrupts meditation
```

Meditation provides the fastest mana regeneration but requires the player to be sitting and not in combat.

### Status Display

Players always see their current HP, Mana, and Stamina in a status bar at the top of their display. This updates in real-time as resources change.

---

## Scripting Language

Scripts are sequences of commands executed when triggers fire.

### Basic Commands

| Command | Description | Example |
|---------|-------------|---------|
| `echo` | Show text to room | `echo The wind howls.` |
| `echoto %S%` | Show text to specific character | `echoto %S% You feel cold.` |
| `say` | NPC speaks | `say Hello there!` |
| `emote` | NPC action | `emote waves hello.` |
| `pause` | Delay in seconds | `pause 0.5` |

### Variable Commands

| Command | Description | Example |
|---------|-------------|---------|
| `settempvar` | Set temporary variable | `settempvar char %S% key value` |
| `setpermvar` | Set permanent variable | `setpermvar char %S% visited true` |
| `setquestvar` | Set quest variable | `setquestvar %S% quest.var value` |
| `deltempvar` | Delete temp variable | `deltempvar %S% key` |
| `delpermvar` | Delete perm variable | `delpermvar %S% key` |

### Movement Commands

| Command | Description | Example |
|---------|-------------|---------|
| `transfer` | Move character | `transfer %S% zone.room` |
| `force` | Make character do command | `force %T% say I must go!` |

### Item Commands

| Command | Description | Example |
|---------|-------------|---------|
| `give` | Give item to character | `give gold_coins %S%` |
| `removeitem` | Remove item from inventory | `removeitem %S% old_key` |
| `spawn` | Spawn object | `spawn here treasure_chest` |

### Combat Commands

| Command | Description | Example |
|---------|-------------|---------|
| `damage` | Deal damage | `damage %S% 10 fire` |
| `heal` | Restore health | `heal %S% 20` |
| `attack` | Start combat | `attack %S%` |

### Conditionals

```yaml
script: |
  $if($questvar(%S%,murder.found_body), eq, true){
    say So you've seen the body...
  }
  else {
    say What brings you here, stranger?
  }
```

### Script Functions

Use `$function(args)` to evaluate values:

| Function | Description | Example |
|----------|-------------|---------|
| `$random(min,max)` | Random number | `$random(1,100)` |
| `$permvar(char,key)` | Get perm variable | `$permvar(%S%,visited)` |
| `$tempvar(char,key)` | Get temp variable | `$tempvar(%S%,mood)` |
| `$questvar(char,id)` | Get quest variable | `$questvar(%S%,murder.found_body)` |
| `$name(ref)` | Get entity name | `$name(%T%)` |

---

## Variable Reference

Variables in scripts use `%symbol%` format.

### Standard Variables

| Variable | Description |
|----------|-------------|
| `%S%` | Reference to triggering character (e.g., `\|C123`) |
| `%s%` | Name of triggering character |
| `%T%` | Reference to target character |
| `%t%` | Name of target |
| `%A%` | Reference to actor (script executor) |
| `%a%` | Name of actor |
| `%*%` | The text that triggered (for catch_say, etc.) |
| `%p%` | Subject pronoun (he/she/it) |
| `%P%` | Object pronoun (him/her/it) |
| `%q%` | Possessive pronoun (his/her/its) |

### Trigger-Specific Variables

**on_receive:**
- `%item%` - Item name
- `%item_id%` - Item ID
- `%giver%` - Giver name

**timer_tick:**
- `%time_elapsed%` - Seconds since last trigger

**on_get/on_drop:**
- `%item%` - Item name
- `%item_id%` - Item ID

---

## Complete Examples

### Combat NPC (Hostile Mob)

```yaml
      - id: werewolf
        name: savage werewolf
        article: a
        keywords: [werewolf, wolf, beast]
        description: >
          A massive wolf-man creature, foam dripping from its fangs.
        pronoun_subject: it
        pronoun_object: it
        pronoun_possessive: its
        group_id: forest_beasts
        attitude: HOSTILE
        attributes:
          strength: 16
          dexterity: 14
          constitution: 14
          intelligence: 6
          wisdom: 12
          charisma: 6
        permanent_flags:
          - is_aggressive
        class:
          Fighter:
            level: 4
            # Werewolf automatically gets all Tier 1 fighter skills
            # You can override or remove specific skills:
            skills:
              mighty_kick: 60     # Good at this skill
              -disarm: 0          # Remove this skill (wolves can't disarm!)
        hit_dice: 4d10+8
        natural_attacks:
          - attack_noun: bite
            attack_verb: bites
            potential_damage:
              - damage_type: piercing
                damage_dice: 2d6
          - attack_noun: claw
            attack_verb: claws
            potential_damage:
              - damage_type: slashing
                damage_dice: 1d8
        hit_modifier: 3
        dodge_dice: 2d20+15
        critical_chance: 0.10
        critical_multiplier: 2
        experience_points: 150
        triggers:
          - id: howl_on_combat
            type: timer_tick
            criteria:
              - subject: "%time_elapsed%"
                operator: numgte
                predicate: 20
            script: |
              $if($random(1,100), numlte, 30){
                echo The werewolf throws back its head and howls!
              }
```

### Guard NPC

```yaml
      - id: palace_guard
        name: palace guard
        article: a
        keywords: [guard, palace, soldier]
        description: >
          A stern-faced guard in polished armor, watching everyone carefully.
        pronoun_subject: he
        pronoun_object: him
        pronoun_possessive: his
        group_id: palace_guards
        attitude: NEUTRAL
        attributes:
          strength: 14
          dexterity: 12
          constitution: 14
          intelligence: 10
          wisdom: 12
          charisma: 10
        class:
          Fighter:
            level: 3
        guards_rooms:                    # Rooms this guard protects
          - central_city.throne_room
          - central_city.royal_treasury
        hit_dice: 3d10+6
        natural_attacks:
          - attack_noun: fist
            attack_verb: punches
            potential_damage:
              - damage_type: bludgeoning
                damage_dice: 1d4+2
        starting_equipment:
          main_hand: steel_longsword
          body: chainmail_armor
        llm_conversation:                # Can be talked to
          personality: >
            You are a palace guard. You take your duty seriously but can be
            reasoned with if someone has legitimate business.
          will_discuss:
            - palace rules
            - who is allowed inside
          will_not_discuss:
            - guard schedules
            - secret passages
```

### Quest NPC with LLM

```yaml
      - id: old_tom
        name: Old Tom
        article: ""
        description: >
          A weathered old man with dirt-stained clothes and a hunched posture.
        pronoun_subject: he
        pronoun_object: him
        pronoun_possessive: his
        group_id: graveyard_workers
        attitude: WARY
        attributes:
          strength: 8
          dexterity: 8
          constitution: 10
          intelligence: 10
          wisdom: 14
          charisma: 6
        class:
          Fighter:
            level: 1
        llm_conversation:
          personality: >
            You are Old Tom, the gravedigger. You're innocent but terrified.
            You saw a figure in dark clothes the night of the murder but
            you're scared to say anything.
          speaking_style: >
            Mumbles nervously. Looks over his shoulder. Uses "beggin' your pardon".
          knowledge:
            - id: saw_figure
              content: >
                You saw a tall figure in butler's clothes near the grave.
              reveal_threshold: 70
              is_secret: true
          goals:
            - id: trust_player
              description: "Gain enough trust to reveal what you saw"
              disposition_required: 70
              on_achieve_set_vars:
                gloomy_graveyard.murder_mystery.knows_about_figure: true
          common_knowledge_refs:
            - murder_case
        triggers:
          - id: nervous_reaction
            type: on_enter
            criteria:
              - subject: "$questvar(%S%,murder_mystery.tom_trusts_player)"
                operator: "!="
                predicate: "true"
            script: |
              pause 0.5
              echo Old Tom flinches as you approach.
              emote mutters nervously
```

### Quest Object

```yaml
      - id: bloody_candlestick
        name: bloodstained candlestick
        article: a
        keywords: [candlestick, bloody, weapon]
        description: >
          A heavy brass candlestick stained with dried blood.
        examine_text: >
          Old blood clings to the brass. Gray hair is caught in it.
        permanent_flags: []
        triggers:
          - id: find_weapon
            type: on_get
            script: |
              setquestvar %S% murder_mystery.found_murder_weapon true
              echo You've found what must be the murder weapon!
          - id: reveal_on_look
            type: catch_look
            criteria:
              - subject: "%*%"
                operator: contains
                predicate: "candlestick"
            script: |
              setquestvar %S% murder_mystery.found_murder_weapon true
```

### Consumable Items Set

```yaml
      - id: healing_potion
        name: healing potion
        article: a
        keywords: [potion, healing, red]
        description: A small vial of ruby-red liquid.
        object_flags:
          - is_consumable
          - is_potion
        heal_amount: 25
        use_message: "You drink the healing potion and wounds begin to close."

      - id: greater_healing_potion
        name: greater healing potion
        article: a
        keywords: [potion, healing, greater]
        description: A larger vial filled with glowing crimson liquid.
        object_flags:
          - is_consumable
          - is_potion
        heal_dice: 4d8+4
        use_message: "You drink the greater healing potion!"

      - id: mana_potion
        name: mana potion
        article: a
        keywords: [potion, mana, blue]
        description: An azure potion that seems to shimmer with inner light.
        object_flags:
          - is_consumable
          - is_potion
        mana_restore: 40
        use_message: "You drink the mana potion and feel arcane energy surge within."

      - id: field_rations
        name: field rations
        article: ""
        keywords: [rations, food, meal]
        description: Dried meat, hardtack, and preserved fruit.
        object_flags:
          - is_consumable
          - is_food
        heal_amount: 10
        stamina_restore: 20
        charges: 3
        use_message: "You eat some of the field rations."
```

### Locked Door with Container

```yaml
        exits:
          down:
            destination: wine_cellar
            description: Stone steps descend into darkness.
            door:
              name: heavy trapdoor
              keywords: [trapdoor, door, heavy]
              is_closed: true
              is_locked: true
              key_id: cellar_key
              linked_exit: gloomy_graveyard.wine_cellar.up
```

```yaml
      - id: cellar_key
        name: rusty iron key
        article: a
        keywords: [key, iron, rusty]
        description: A heavy iron key, rusted but functional.
        triggers:
          - id: key_use
            type: on_use
            script: |
              echo You should use this to unlock something.
```

---

## Best Practices

1. **Unique IDs**: All IDs must be unique within their scope (room IDs within zone, trigger IDs within entity)

2. **Zone References**: Always use `zone.room` format for cross-zone references

3. **Permanent NPCs**: Omit respawn times for quest-critical NPCs to make them unkillable

4. **LLM Knowledge**: Be specific about what NPCs know - vague knowledge leads to hallucination

5. **Quest Flow**: Design quests with multiple paths - not all players will find every clue

6. **Trigger Order**: Triggers fire in order defined - put most specific criteria first

7. **Common Knowledge**: Use for shared facts, reference in individual NPC configs

8. **Testing**: Use the debug_zone for testing new mechanics before adding to main zones

9. **NPC Skills**: Let the auto-population handle most skills. Only specify explicit skills when you want to override levels or remove inappropriate skills (e.g., remove "disarm" from animals)

10. **Consumables Balance**: Healing potions should be valuable but not trivialize combat. Use `heal_dice` for variable healing to add uncertainty

11. **Guard Placement**: Guards should protect logical chokepoints. Give them LLM personalities so players can roleplay their way past

12. **Resource Costs**: When designing content, remember that mages need mana recovery time. Place rest areas and mana potions accordingly

13. **Death Penalty Areas**: The corpse retrieval mechanic adds tension to dangerous areas. Design challenging areas with this in mind - dying deep in a dungeon should be meaningful

---

## Quick Reference

### Room Spawn Format
```yaml
characters:
  - id: npc_id
    quantity: 1
    respawn time min: 60    # Omit both for permanent/unkillable NPC
    respawn time max: 90
```

### Exit Format
```yaml
exits:
  direction: destination                    # Simple
  direction:                                # With description
    destination: zone.room
    description: What you see looking that way.
  direction:                                # With door
    destination: zone.room
    door:
      name: door name
      keywords: [door, keywords]
      is_closed: true
      is_locked: true
      key_id: key_object_id
      linked_exit: zone.room.direction
```

### Trigger Format
```yaml
triggers:
  - id: unique_id
    type: trigger_type
    criteria:
      - subject: "%var%"
        operator: eq
        predicate: "value"
    script: |
      command arg1 arg2
```

### LLM NPC Format
```yaml
llm_conversation:
  personality: Who you are...
  speaking_style: How you speak...
  knowledge:
    - id: knowledge_id
      content: What you know...
      reveal_threshold: 50
      is_secret: true/false
  goals:
    - id: goal_id
      description: What to achieve
      disposition_required: 60
      on_achieve_set_vars:
        zone.quest.var: value
  will_discuss: [topics]
  will_not_discuss: [topics]
  common_knowledge_refs: [ids]
```

### NPC with Skills and Guards
```yaml
        class:
          Fighter:
            level: 5
            skills:
              mighty_kick: 80          # Override skill level
              -cleave: 0               # Remove skill
        guards_rooms:
          - zone.protected_room
```

### Consumable Item Format
```yaml
      - id: item_id
        name: item name
        article: a
        keywords: [keywords]
        description: Description text.
        object_flags:
          - is_consumable
          - is_potion          # or is_bandage, is_food
        heal_amount: 25        # or heal_dice: 2d8+4
        mana_restore: 30       # optional
        stamina_restore: 20    # optional
        charges: 1             # default 1, increase for multi-use
        use_message: "Message when used."
```

### Resource Regeneration Summary
| State | HP | Mana | Stamina |
|-------|-----|------|---------|
| Combat | None | Very Slow | Moderate |
| Walking | Slow | Moderate | Moderate |
| Sitting/Resting | Moderate | Fast | Fast |
| Sleeping | Fast | Fast | Fast |
| Meditating | Moderate | Fastest | Fast |
