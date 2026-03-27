# NextGenMUD Zone Design Reference

This README is a practical builder reference with complete YAML examples for:

- a full `ZONES.<zone_id>` block
- one `ROOM`
- one `CHARACTER`
- one `OBJECT`

It also explains what each field means and common/valid values.

---

## 1) File Shape (Required)

World files must use a single top-level key: `ZONES`.

```yaml
ZONES:
  my_zone_id:
    name: My Zone
    description: Builder-facing description
    common_knowledge: {}
    variables: {}
    quests: {}
    ROOMS: {}
    CHARACTERS: []
    OBJECTS: []
    LOOT_TABLES: []
```

Notes:
- Use uppercase section keys directly under a zone: `ROOMS`, `CHARACTERS`, `OBJECTS`, `LOOT_TABLES`.
- Use lowercase keys everywhere else (for example inside room and character definitions: `characters`, `objects`, `inventory`, `equipment`).
- Character/object references can be local (`guard`) or fully qualified (`central_city.guard`).

---

## 2) Complete Zone Example

```yaml
ZONES:
  oakhaven:
    name: Oakhaven
    description: >-
      A trade town built around an old shrine. The square is lively by day,
      tense by night.

    common_knowledge:
      town_mood: "Merchants are nervous after recent caravan raids."
      old_shrine: "Locals believe the eastern shrine protects the town."

    variables:
      town_story:
        shrine_repaired:
          description: "Whether the old shrine has been restored."
          type: boolean
          default: false
          knowledge_updates:
            - condition: true
              updates:
                town_mood: "Trade confidence has returned after the shrine restoration."
        captain_trust:
          description: "How much the watch captain trusts the player."
          type: integer
          default: 0

    ROOMS:
      town_square:
        name: Oakhaven Square
        subzone: market_district
        description: >-
          A broad cobbled square with market stalls and a weathered statue.
          Exits: north, east, west
        perm_variables:
          square_state: normal
        exits:
          north:
            destination: north_gate
            description: A guarded archway opens toward the northern road.
          east:
            destination: old_shrine
            description: Lanterns mark the path to the old shrine.
          west:
            destination: oakhaven_inn
            description: A warm light spills from the inn door.
        characters:
          - id: watch_captain
            quantity: 1
            respawn time min: 120
            respawn time max: 240
          - id: street_vendor
            quantity: 2
            respawn time min: 45
            respawn time max: 90
        flags: [outdoors, busy, safe]
        objects:
          - id: market_notice_board
            quantity: 1
        triggers:
          - id: on_say_help_square
            type: on_say
            criteria:
              - subject: "%*%"
                operator: contains
                predicate: "help,where,directions"
            script: |
              echo A passerby points out the inn to the west and the shrine to the east.

    CHARACTERS:
      - id: watch_captain
        name: Watch Captain Rellan
        article: ""
        description: >-
          A scarred veteran in polished scale armor, always scanning the crowd.
        keywords: [captain, watch, rellan]
        pronoun_subject: he
        pronoun_object: him
        pronoun_possessive: his
        type: humanoid
        race: human
        group_id: city_watch
        attitude: friendly
        attributes:
          strength: 15
          dexterity: 12
          constitution: 14
          intelligence: 11
          wisdom: 13
          charisma: 12
        class:
          fighter:
            level: 8
            skills:
              mighty_kick:
                level: 45
                cap: 60
        class_priority: [fighter]
        hit_dice: 8d10+24
        experience_points: 2500
        permanent_flags: [darkvision, aggressive_if_attacked]
        natural_attacks:
          - attack_noun: gauntlet
            attack_verb: strikes
            potential_damage:
              - damage_type: bludgeoning
                damage_dice: 1d6+2
        hit_modifier: 58
        dodge_dice: 1d50+8
        critical_chance: 5
        critical_multiplier: 200
        equipment: [captain_scale_armor, captain_sword]
        inventory: [healing_potion]
        loot:
          - table: watch_captain_loot
            chance_percent: 50
            quantity_percent_chances:
              1: 70
              2: 30
        saving_throw_bonuses:
          fortitude: 15
          will: 10
        damage_multipliers:
          fire: 0.8
          psychic: 1.25
        guards_rooms: [oakhaven.old_shrine]
        perm_variables:
          rank: captain
        triggers:
          - id: on_tell_help_captain
            type: on_tell
            criteria:
              - subject: "%*%"
                operator: contains
                predicate: "help,raids"
            script: |
              echoto %S% Keep your eyes open near the north road.

    OBJECTS:
      - id: captain_sword
        name: captain's longsword
        article: a
        description: A well-maintained longsword with a bright edge.
        keywords: [sword, longsword, captain]
        type: weapon
        value: 120
        weight: 8
        equip_locations: [main hand, off hand]
        attack_bonus: 4
        damage_type: slashing
        damage: 1d8+3
        permanent_flags: [weapon]
```

---

## 3) Field-by-Field Reference

## Zone Fields

- `name`: display name for the zone.
- `description`: builder-facing long description.
- `common_knowledge`: map of knowledge id -> text.
- `variables`: zone quest/state vars.
  - variable `type`: `boolean`, `integer`, `string`.
  - `default`: initial value.
  - optional `knowledge_updates`: conditional text updates.
  - `knowledge_updates` is a list of rules. Each rule has:
    - `condition`: value or expression to match
    - `updates`: map of knowledge keys to new values
  - `updates` can set text blocks or structured values (including booleans/ints) used by scripts/LLM context.
- `ROOMS`: map of room id -> room definition.
- `CHARACTERS`: list of NPC definitions.
- `OBJECTS`: list of object definitions.
- `LOOT_TABLES`: list of loot table definitions (see Loot Tables section below).
- `quests`: map of quest id -> quest definition (see Quests section below).
- `common_knowledge`: can be flat strings or grouped dictionaries.
  - For large zones, group by topic (`history`, `religion`, `politics`, `technical`, `hidden`) to keep prompts coherent.
  - NPC `llm_conversation.common_knowledge_refs` should reference the specific keys the NPC should know.

## Room Fields

- `name`: room display name.
- `subzone`: optional grouping tag used by content designers.
- `description`: text shown on room look.
- `perm_variables`: persistent variables attached to room instances.
- `flags`: builder/runtime room tags used in many existing zones (for example: `outdoors`, `hot`, `dangerous`).
  - These are typically consumed by scripts/content logic.
  - Engine-level movement/combat restrictions should still use supported mechanics (room exits, triggers, checks).
- `exits`: direction map (`north`, `south`, `east`, `west`, `up`, `down`, etc.).
  - simple value: `north: other_room`
  - object form:
    - `destination`: `room_id` or `zone.room_id`
    - `description`: shown on `look <direction>`
    - `door` (optional):
      - `name`, `keywords` (list), `is_closed`, `is_locked`, `key_id`
      - `linked_exit` format: `zone.room.direction`
- `characters`: room spawn entries:
  - fields: `id`, `quantity`, and respawn fields
  - respawn fields accepted in both naming styles:
    - `respawn time min` / `respawn time max` (preferred)
    - `respawn_time_min` / `respawn_time_max` (also accepted)
- `objects`: room spawn entries:
  - `id`, `quantity`
- `triggers`: list of trigger dicts.

### Placement Quick Reference

Use these patterns to control where objects begin the game:

```yaml
ROOMS:
  town_square:
    objects:
      - id: market_notice_board
        quantity: 1
```

- Put objects in a room with `ROOMS.<room_id>.objects`.
- `quantity` is how many instances to place at zone/runtime build time.

```yaml
CHARACTERS:
  - id: watch_captain
    equipment: [captain_scale_armor, captain_sword]
    inventory: [healing_potion, bandage]
```

- Put objects into a character's inventory with `inventory` (list of object ids).
- Start a character with items already equipped using `equipment` (list of object ids).
- Equipped items must be valid for one of that object's `equip_locations`.

## Character Fields

- `id`: unique in zone.
- `name`, `article`, `description`.
- `short_description`: optional brief display string (used in place of name in some contexts).
- `long_description`: optional extended description (shown on detailed inspect).
- `keywords`: list used for matching target names.
- pronouns:
  - `pronoun_subject`, `pronoun_object`, `pronoun_possessive`
- taxonomy:
  - `type`: broad creature category (free-form string)
  - `race`: specific lineage/category (free-form string)
- `group_id`: optional grouping key for AI/coordination.
- `attitude`: common values are `friendly`, `neutral`, `unfriendly`, `hostile`.
- `alignment`: optional moral/ethical alignment (free-form string, e.g. `neutral`, `evil`).
- `attributes`: required stats
  - `strength`, `dexterity`, `constitution`, `intelligence`, `wisdom`, `charisma`
- `class`: class map with per-class settings
  - base classes: `fighter`, `rogue`, `mage`, `cleric`
  - each class entry supports:
    - `level`
    - optional `skills`
- `class_priority`: ordered class list (important for multiclass behavior).
  - first item is primary class; order affects class-based calculations and presentation.
- `hit_dice`: dice expression (example `6d10+12`).
- `max_hit_points`: optional fixed cap; if set, HP from `hit_dice` will not exceed this value.
- `experience_points`: starting XP.
- `permanent_flags`: list of flags. Common ones:
  - `is_pc`, `darkvision`, `see_invisible`, `is_invisible`, `is_undead`
  - `is_sentinel`, `no_wander`, `stationary`, `evasive`, `quest_giver`
  - `aggressive_if_attacked`, `mindless`, `cowardly`, `protected`, `humanoid`
- combat fields:
  - `natural_attacks`, `hit_modifier`, `dodge_dice`
  - `critical_chance`, `critical_multiplier`, `critical_damage_bonus`
- progression/support:
  - `skills`, `skill_cap_overrides`, `saving_throw_bonuses`, `damage_multipliers`
- inventory/setup:
  - `equipment`, `inventory`, `loot`
  - `inventory`: object ids created on the character and carried in inventory at spawn/init.
  - `equipment`: object ids created on the character and auto-equipped at valid slots.
- behavior/scripting:
  - `guards_rooms`, `perm_variables`, `triggers`
  - optional `llm_conversation` block for LLM NPCs:
    - `personality`, `speaking_style`
    - `knowledge` entries (`id`, `content`, `reveal_threshold`, `is_secret`)
    - `goals` entries (`id`, `description`, optional condition/disposition fields)
    - `conversation_results` (condition -> set vars)
    - `actions` (`id`, `description`, `script`)
    - `will_discuss`, `will_not_discuss`, `special_instructions`
    - `common_knowledge_refs`

## Object Fields

- identity/display:
  - `id`, `name`, `article`, `description`, `keywords`
  - `examine_text`: optional extended text shown when a player inspects the object closely
- economy/weight:
  - `value`, `weight`
- equip/combat:
  - `equip_locations` (examples: `main hand`, `off hand`, `head`, `body`, `legs`)
  - `attack_bonus`
  - `damage_type` + `damage` dice expression (for simple weapons)
  - `weapon_attacks`: list of attack entries for multi-damage weapons (each entry has `attack_noun`, `attack_verb`, `potential_damage` with `damage_type` + `damage_dice`)
  - `dodge_penalty`
  - `armor_class_bonus`
  - `damage_multipliers`, `damage_reduction`
- container/use:
  - `contents` (list of object ids contained initially)
  - `charges` (`-1` single-use consumed; `0+` remaining uses)
- flags:
  - use `permanent_flags` (or legacy `flags`)
  - supported values include:
    - `armor`, `weapon`, `container`
    - `no-take`, `static`
    - `openable`, `closed`, `lockable`, `locked`
    - `hidden`, `door`
    - `consumable`, `potion`, `bandage`, `food`
- scripting:
  - `perm_variables`, `triggers`

---

## 4) Trigger Reference (Used by Rooms, Characters, Objects)

Trigger entry shape:

```yaml
- id: unique_trigger_id
  type: on_say
  criteria:
    - subject: "%*%"
      operator: contains
      predicate: "help,guide"
  flags: [only_when_pc_room]   # optional
  script: |
    echo Example response.
```

Common `type` values:
- `on_see`, `on_say`, `on_tell`, `timer_tick`
- `catch_inspect`, `on_look`
- `on_arrive`, `on_leave`, `on_receive`
- `on_get`, `on_drop`, `on_open`, `on_close`, `on_lock`, `on_unlock`, `on_use`
- `on_attacked`, `catch_go`, `on_enter`, `catch_zerohp`, `on_signal`, `catch_command`

Common `operator` values in criteria:
- string: `eq`, `neq`, `contains`, `oneof`
- numeric: `numgt`, `numlt`, `numeq`, `numgte`, `numlte`

Useful notes:
- For `contains`, comma-separated predicate values are treated as OR.
- `flags` supports `only_when_pc_room`, `only_when_pc_zone`.
- Subject patterns seen in production:
  - `%*%` freeform input text
  - `%S%`, `%A%`, `%T%` common actor refs
  - `%time_elapsed%` timer criteria
  - function expressions in subject/predicate, for example `$random(1,100)` or `$permvar(%S%,rank)`
- Script condition style:
  - `$if(<subject>,<operator>,<predicate>){...} else {...}`
  - Example: `$if($random(1,2),eq,1){ ... } else { ... }`
  - Numeric/string operators are the same as criteria operators listed above.
  - If a zone uses custom helpers/macros not in core docs, document them in-zone near the trigger for maintainers.

---

## 5) Loot Tables

Define loot tables at the zone level under `LOOT_TABLES`. Characters reference them via their `loot` field.

```yaml
LOOT_TABLES:
- id: minor_loot
  items:
  - master_zone.healing_potion
  - master_zone.greater_healing_potion
- id: items_loot
  items:
  - plusone_sword
  - plustwo_dagger
```

Character loot reference:

```yaml
loot:
  - table: minor_loot
    chance_percent: 50
    quantity_percent_chances:
      1: 70
      2: 30
```

- `table`: id of a `LOOT_TABLES` entry (local or fully qualified).
- `chance_percent`: probability (0-100) that anything drops at all.
- `quantity_percent_chances`: map of item count -> percent chance for that count.

---

## 6) Quests

Define quests at the zone level under `quests`. Quest state is tracked via quest variables that scripts read and write with `setquestvar` / `$questvar()`.

```yaml
quests:
  sun_king_legacy:
    title: The Sun King's Legacy
    description: Restore the Solar Lens and reactivate the Apex Shrine.
    objectives:
    - Locate the Solar Lens within the Ossuary.
    - Find the alignment calculation in the Scriptorium.
    - Ascend the Great Pyramid to the Apex Shrine.
    stages:
    - name: The Glassed Expanse
      sequence: 10
      description: Find a way into the Ossuary.
      conditions:
        sun_king_legacy.status: "not_started"
    - name: Heart of Refraction
      sequence: 20
      description: Locate the Solar Lens.
      conditions:
        sun_king_legacy.status: "started"
        sun_king_legacy.has_lens: false
    variables:
      status:
        type: string
        default: "not_started"
        description: Main progression state.
      has_lens:
        type: boolean
        default: false
        description: Player has the Solar Lens.
        knowledge_updates:
        - condition: true
          updates:
            lens_recovered: true
```

Quest fields:

- `title`, `description`: display text.
- `objectives`: ordered list of goal descriptions.
- `stages`: progression stages, each with `name`, `sequence` (sort order), `description`, and `conditions` (map of quest variable -> required value).
- `variables`: quest-scoped variables with `type`, `default`, `description`, and optional `knowledge_updates`.
- `__replace__: true`: when present, a zone merge replaces the entire quest block rather than merging fields.

---

## 7) Scripting

Trigger scripts are documented in detail in [README-SCRIPTING.md](README-SCRIPTING.md), which covers:

- All trigger types (`on_say`, `on_tell`, `on_use`, `timer_tick`, `catch_zerohp`, `catch_command`, `on_signal`, etc.)
- Trigger criteria and operators
- Script commands (output, entity management, state/combat, variables, flow control)
- Script functions (string, numeric, math, variable access, game state)
- System variables (`%S%`, `%A%`, `%T%`, `%*%`, etc.)
- Conditional logic (`$if`/`else`)
- Quest system integration and evaluation order
- YAML formatting standards for scripts

---

## 8) Authoring Tips

- Keep ids stable; reference by id everywhere.
- Prefer fully qualified ids (`zone.id`) in cross-zone links.
- Start simple, then add triggers and LLM behavior in small passes.
- Validate by loading game and smoke-testing room movement, spawn, and trigger responses.
