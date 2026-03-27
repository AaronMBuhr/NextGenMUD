# NextGenMUD Game Mechanics Reference

This document is a comprehensive reference for all game mechanics in NextGenMUD, covering character creation, combat, skills, world definitions, scripting, and more.

---

## Table of Contents

- [Character Attributes](#character-attributes)
- [Character Classes](#character-classes)
- [Class Specializations](#class-specializations)
- [Multiclassing](#multiclassing)
- [Experience and Leveling](#experience-and-leveling)
- [Resource Pools (HP, Mana, Stamina)](#resource-pools)
- [Regeneration](#regeneration)
- [Combat System](#combat-system)
- [Saving Throws](#saving-throws)
- [Skills and Spells](#skills-and-spells)
  - [Fighter Skills](#fighter-skills)
  - [Rogue Skills](#rogue-skills)
  - [Mage Spells](#mage-spells)
  - [Cleric Spells](#cleric-spells)
- [Actor States and Buffs](#actor-states-and-buffs)
- [Equipment System](#equipment-system)
- [Damage Types](#damage-types)
- [Death and Respawn](#death-and-respawn)
- [Player Commands](#player-commands)
- [Character Attitudes](#character-attitudes)
- [Room Definitions](#room-definitions)
- [Object Definitions](#object-definitions)
- [Character / NPC Definitions](#character--npc-definitions)
- [Triggers and Scripting](#triggers-and-scripting)
  - [Trigger Types](#trigger-types)
  - [Trigger Criteria](#trigger-criteria)
  - [Script Commands](#script-commands)
  - [Script Variables](#script-variables)
  - [Script Functions](#script-functions)
  - [Conditional Logic](#conditional-logic)
- [Quest System](#quest-system)
- [LLM NPC Conversations](#llm-npc-conversations)
- [Player Saving and Loading](#player-saving-and-loading)

---

## Character Attributes

Every character has six core attributes, starting from class-defined defaults and improvable every 10 levels:

| Attribute | Abbreviation | Primary Effects |
|-----------|-------------|-----------------|
| **Strength** | STR | Melee presence (allocation/templates) |
| **Dexterity** | DEX | Dodge modifier, Reflex saves, stealth/backstab checks |
| **Constitution** | CON | Max HP bonus, max stamina bonus, Fortitude saves |
| **Intelligence** | INT | Max mana bonus (Mage), spell checks and save difficulty |
| **Wisdom** | WIS | Max mana bonus (Cleric), Will saves |
| **Charisma** | CHA | Social skills, certain fighter abilities (rally) |

Attributes contribute to saves as: `(attribute_value - opponent_attribute) * 2` added to save chance.

Every **10 total levels**, characters gain **+1 unspent attribute point** to allocate freely.

---

## Character Classes

Four base classes are available at character creation, each with distinct strengths:

### Fighter

> *A master of martial combat, strong and resilient.*

| Stat | Value |
|------|-------|
| Starting Attributes | STR 14, DEX 12, CON 14, INT 8, WIS 10, CHA 10 |
| Hit Dice | 1d10+4 |
| HP per Level | 10 |
| Stamina per Level | 15 |
| Mana per Level | 0 |
| Skill Points per Level | 25 |
| Base Hit Modifier | 55 |
| Dodge Dice | 1d50+5 |
| Critical Chance | 5% |
| Critical Multiplier | 150% |
| Hit Bonus Growth | +1 per level (best) |
| Dodge Bonus Growth | +0.5 per level |
| Save Strengths | Fortitude 50%, Reflex 35%, Will 30% |

### Rogue

> *A cunning trickster, quick and deadly.*

| Stat | Value |
|------|-------|
| Starting Attributes | STR 10, DEX 16, CON 10, INT 12, WIS 10, CHA 12 |
| Hit Dice | 1d6+0 |
| HP per Level | 6 |
| Stamina per Level | 12 |
| Mana per Level | 0 |
| Skill Points per Level | 22 |
| Base Hit Modifier | 50 |
| Dodge Dice | 1d50+15 |
| Critical Chance | 10% |
| Critical Multiplier | 200% |
| Hit Bonus Growth | +0.75 per level |
| Dodge Bonus Growth | +0.75 per level (best) |
| Save Strengths | Fortitude 30%, Reflex 50%, Will 35% |

Rogues are the only class with an **off-hand attack progression** and gain **CAN_DUAL_WIELD** as a class feature.

### Mage

> *A wielder of arcane power, fragile but devastating.*

| Stat | Value |
|------|-------|
| Starting Attributes | STR 8, DEX 12, CON 10, INT 16, WIS 12, CHA 10 |
| Hit Dice | 1d4+0 |
| HP per Level | 4 |
| Stamina per Level | 0 |
| Mana per Level | 15 |
| Skill Points per Level | 20 |
| Base Hit Modifier | 40 |
| Dodge Dice | 1d50+5 |
| Critical Chance | 5% |
| Critical Multiplier | 100% |
| Hit Bonus Growth | +0.25 per level |
| Dodge Bonus Growth | +0.25 per level |
| Spell Power Growth | +1 per level (best) |
| Save Strengths | Fortitude 30%, Reflex 35%, Will 50% |

Mana scales with Intelligence: `+2 max mana per point of INT above 10, per mage level`.

### Cleric

> *A divine servant, healer and protector.*

| Stat | Value |
|------|-------|
| Starting Attributes | STR 12, DEX 10, CON 12, INT 10, WIS 16, CHA 12 |
| Hit Dice | 1d8+1 |
| HP per Level | 8 |
| Stamina per Level | 5 |
| Mana per Level | 12 |
| Skill Points per Level | 20 |
| Base Hit Modifier | 50 |
| Dodge Dice | 1d50+5 |
| Critical Chance | 5% |
| Critical Multiplier | 100% |
| Hit Bonus Growth | +0.5 per level |
| Dodge Bonus Growth | +0.25 per level |
| Spell Power Growth | +0.75 per level |
| Save Strengths | Fortitude 40%, Reflex 30%, Will 50% |

Mana scales with Wisdom: `+2 max mana per point of WIS above 10, per cleric level`.

---

## Class Specializations

At **level 20**, characters may choose a specialization for their base class:

| Base Class | Specializations |
|------------|----------------|
| Fighter | **Berserker**, **Guardian**, **Reaver** |
| Rogue | **Duelist**, **Assassin**, **Infiltrator** |
| Mage | **Evoker**, **Conjurer**, **Enchanter** |
| Cleric | **Warpriest**, **Restorer**, **Ritualist** |

---

## Multiclassing

Characters may have up to **2 classes**. A second class is chosen through the multiclass flow when the XP threshold is met. Total level is the sum of levels across all classes, capped at **50**.

---

## Experience and Leveling

XP is gained by killing NPCs. The killed NPC's `experience_points` value is split among all attackers proportional to their total level.

To level up, a character must have spent all unspent skill points first.

**XP Progression Table** (selected milestones):

| Level | XP Required | Level | XP Required |
|-------|------------|-------|------------|
| 1 | 0 | 10 | 64,000 |
| 2 | 1,000 | 15 | 169,000 |
| 3 | 2,000 | 20 | 324,000 |
| 4 | 4,000 | 25 | 529,000 |
| 5 | 8,000 | 30 | 784,000 |
| 6 | 16,000 | 40 | 1,444,000 |
| 7 | 25,000 | 50 | 2,304,000 |

New characters receive **3 levels worth** of starting skill points.

---

## Resource Pools

| Resource | Used By | Scaling |
|----------|---------|---------|
| **Hit Points** | All classes | `HP_per_level + (CON - 10) * class_multiplier` per level |
| **Mana** | Mage, Cleric | `mana_per_level + (INT_or_WIS - 10) * 2` per caster level |
| **Stamina** | Fighter, Rogue, Cleric | `stamina_per_level + (CON - 10) * 2` per physical level |

CON HP multipliers by class: Fighter 2.0, Cleric 1.6, Rogue 1.2, Mage 0.8.

DEX dodge multipliers by class: Rogue 2.0, Fighter 1.6, Cleric 1.2, Mage 0.8.

---

## Regeneration

Resources regenerate passively based on character activity state. Regen pulses run once per second for mana/stamina and every 8 seconds for HP.

| State | HP/pulse | Mana/sec | Stamina/sec |
|-------|---------|----------|-------------|
| **Combat** | 0 | 1 | 1 |
| **Walking** | 1 | 2 | 2 |
| **Resting** | 2 | 4 | 4 |
| **Sleeping** | 4 | -- | -- |
| **Meditating** | -- | 8 | -- |

---

## Combat System

Combat is **tick-based**. The game world runs at **0.5 seconds per tick**, with a fighting round every **8 ticks (4 seconds)**. Combat is not turn-based; all combatants act each round.

### Initiating Combat

Players use `attack <target>` or `kill <target>`. Movement is blocked while in combat; use `flee` to attempt escape.

### Auto-Attacks per Round

Each round, a combatant performs automatic weapon strikes. The number of attacks per round depends on class and level:

- **Main hand attacks**: Fighters gain extra main hand attacks fastest (up to 5 at level 50). Rogues and clerics gain them more slowly. Mages gain a second attack at level 25.
- **Off hand attacks**: Only rogues have an off-hand attack progression (up to 3 at level 50), requiring dual-wielded weapons and the `CAN_DUAL_WIELD` flag.
- **Natural attacks**: If a character has `natural_attacks` defined and has no weapon (or in addition to weapons for NPCs), those are rolled as extra strikes.

### Hit Determination

For each attack swing:

1. Roll `hit_roll` = random 1..100
2. Calculate `hit_modifier` = character's hit modifier + weapon's attack bonus
3. Roll `dodge_roll` = roll target's dodge dice + target's dodge modifier
4. **Hit** if `hit_roll + hit_modifier >= dodge_roll`
5. **Critical hit** check: separate roll, `random(1..100) < critical_chance`

### Damage Calculation

Each weapon or natural attack defines one or more `PotentialDamage` entries with a damage type and dice (e.g., `2d6+3 slashing`). On hit, each damage component is rolled.

On critical hit, damage is scaled by `(100 + critical_damage_bonus) / 100`.

### Damage Mitigation

When damage is applied to a target:

1. **Damage Multiplier**: `damage = raw * (1 - target_multiplier)` where multiplier comes from equipment + class bonuses + buffs (a multiplier of 0.5 means 50% resistance; 0 means immune)
2. **Damage Reduction**: `damage = damage - flat_reduction` per damage type
3. Minimum effective damage is 1 (if any raw damage was dealt); 0 means fully absorbed

### NPC Combat AI

NPCs have a `CombatAI` that can queue skill commands alongside their auto-attacks. Skills do not replace basic attacks.

---

## Saving Throws

Many skills and spells allow a saving throw. There are three save categories:

| Save | Key Attribute | Strongest Class |
|------|--------------|-----------------|
| **Fortitude** | Constitution | Fighter (50% base) |
| **Reflex** | Dexterity | Rogue (50% base) |
| **Will** | Wisdom | Mage / Cleric (50% base) |

### Save Formula

```
save_chance = clamp(
    class_base
    + (defender_attribute - attacker_attribute) * 2
    + (defender_best_level - attacker_class_level) * 3
    - skill_save_difficulty
    + save_bonus,
    5, 95
)
```

Roll 1..100; saved if roll <= save_chance. Minimum save chance is always 5%, maximum 95%.

### Skill Checks

Some abilities require a skill check to activate: roll 1..100, succeed if `roll <= skill_level + difficulty_modifier`.

---

## Skills and Spells

Skills are trained using skill points gained on level-up. Each skill ranges from 0 to 100. Skills are unlocked at tier-appropriate levels for the class. The `skillup <skill>` command spends points to train a skill, subject to a level-dependent cap.

### Fighter Skills

| Skill | Resource | Mechanic |
|-------|----------|----------|
| **Normal Stance** | -- | Clears active stances |
| **Mighty Kick** | 15 stamina | Fort save or stun/knockdown |
| **Demoralizing Shout** | 20 stamina | Will save or debuff |
| **Intimidate** | -- | Will save (easy, -5 difficulty) or debuff |
| **Disarm** | -- | Reflex save or disarmed |
| **Slam** | -- | Fort save or physical CC |
| **Bash** | -- | Fort save (+5 difficulty), physical CC |
| **Rally** | -- | Group damage bonus buff |
| **Rend** | -- | Fort save or bleed DoT |
| **Cleave** | -- | Multi-target weapon attack (2 targets) |
| **Whirlwind** | -- | Multi-target weapon attack (all enemies in room) |
| **Execute** | -- | High-damage finishing attack |
| **Massacre** | -- | AoE-style high-damage attack |
| **Enrage** | -- | Self-buff stance (increased damage) |
| **Shield Block** | -- | Defensive dodge buff |
| **Shield Sweep** | -- | Reflex save, damage + control |
| **Berserker Stance** | -- | Stance: increased offense, reduced defense |
| **Defensive Stance** | -- | Stance: increased defense, reduced offense |

### Rogue Skills

| Skill | Resource | Mechanic |
|-------|----------|----------|
| **Stealth** | -- | Enter stealth mode (hidden from view) |
| **Backstab** | -- | High-damage attack from stealth |
| **Pick Lock** | -- | Attempt to unlock locked doors/containers |
| **Detect Traps** | -- | Detect hidden traps |

### Mage Spells

All mage spells cost **mana** and many have a **cast time** (in ticks).

| Spell | Mana | Save | Effect |
|-------|------|------|--------|
| **Magic Missile** | 8 | None | Always hits on successful cast; arcane damage |
| **Fireball** | 25 | Reflex | AoE fire damage to primary target + all others in room; scales with mage level (level/4 d6) and INT |
| **Ignite** | 12 | Reflex | Fire damage-over-time (burning state) |
| **Mana Burn** | 20 | Will (+5) | Drains target's mana and deals damage |
| **Shield** | 20 | -- | Arcane shield buff on self |
| **Arcane Barrier** | 25 | -- | Defensive barrier buff |
| **Blur** | 15 | -- | Dodge bonus buff |
| **Animate Dead** | 40 | -- | Raises an undead minion from a corpse |

### Cleric Spells

All cleric spells cost **mana**.

| Spell | Mana | Save | Effect |
|-------|------|------|--------|
| **Heal** | 15 | -- | Heals `2d8 + 5 + 1.5 * cleric_level` HP; self or ally target |
| **Smite** | 10 | Will | Holy damage; bonus damage vs undead |
| **Bless** | 15 | -- | Hit + damage bonus buff |
| **Armor of Faith** | 20 | -- | Physical damage reduction buff |
| **Regeneration** | 25 | -- | Heal-over-time (regenerating state) |
| **Zealotry** | 20 | -- | Damage buff that reduces healing received |
| **Consecrate** | 25 | -- | Holy AoE ground effect (damages enemies in room over time) |
| **Judgment** | 30 | Will (+5) | Strong single-target holy nuke; extra vs undead |
| **Divine Reckoning** | 60 | Will (+10) | Ultimate: room-wide AoE holy damage + stun; long cooldown |

---

## Actor States and Buffs

States are timed effects applied to characters. They schedule their own expiration and optional periodic pulses on the game clock. States can add or remove temporary flags for their duration.

### State Types

| State | Effect |
|-------|--------|
| **Stunned** | Cannot act |
| **Frozen** | Cannot act |
| **ForcedSitting** | Forced into sitting position |
| **ForcedSleeping** | Forced into sleeping position |
| **HitBonus / HitPenalty** | Modifies hit chance |
| **DodgeBonus / DodgePenalty** | Modifies dodge |
| **DamageBonus** | Increases damage dealt |
| **DamageMultipliers** | Modifies damage type resistances |
| **ArmorBonus** | Reduces incoming damage |
| **Bleeding** | Periodic damage (bleed DoT) |
| **Burning** | Periodic fire damage |
| **Ignited** | Fire DoT state |
| **Regenerating** | Periodic healing |
| **Shielded** | Damage absorption shield |
| **Stealthed** | Hidden from view |
| **Disarmed** | Cannot use weapon attacks |
| **Charmed** | Attitude change toward charmer |
| **BerserkerStance** | Offense up, defense down |
| **DefensiveStance** | Defense up, offense down |
| **Zealotry** | Damage up, healing received down |
| **Consecrated** | Holy ground AoE effect |
| **Casting** | Currently casting a spell (interruptible) |
| **ExperienceModifier** | Modifies XP gain rate |
| **RecoveryModifier** | Modifies recovery speed |

States are typically applied by skills, spells, or script commands (`applystate`). Each has a defined duration in ticks.

---

## Equipment System

### Equipment Slots

Characters can equip items in the following slots:

| Slot | Notes |
|------|-------|
| `main_hand` | Primary weapon |
| `off_hand` | Shield or second weapon (rogues with CAN_DUAL_WIELD) |
| `both_hands` | Two-handed weapons (occupies both hand slots) |
| `head` | Helmets, hats |
| `neck` | Necklaces, amulets |
| `shoulders` | Shoulder armor, cloaks |
| `arms` | Arm guards |
| `wrists` | Bracers, bracelets |
| `hands` | Gloves, gauntlets |
| `left_finger` / `right_finger` | Rings |
| `waist` | Belts |
| `legs` | Leg armor, pants |
| `feet` | Boots, shoes |
| `body` | Body armor, robes |
| `back` | Capes, backpacks |
| `eyes` | Goggles, eyewear |

When equipment is changed, damage multipliers and combat stats are recalculated from the base character values plus all equipped items.

---

## Damage Types

The game supports 17 damage types:

| Physical | Elemental | Magical | Other |
|----------|-----------|---------|-------|
| `slashing` | `fire` | `arcane` | `poison` |
| `piercing` | `cold` | `holy` | `disease` |
| `bludgeoning` | `lightning` | `unholy` | `raw` |
| | `acid` | `psychic` | |
| | | `force` | |
| | | `necrotic` | |
| | | `radiant` | |

Objects, characters, and NPCs can define per-type **damage multipliers** (resistance/vulnerability) and **damage reduction** (flat subtraction).

---

## Death and Respawn

### When a character reaches 0 HP:

1. **`catch_zerohp` triggers** fire first -- scripts can heal the character to cancel death
2. If still at 0 HP, death proceeds

### NPC Death:
- Corpse is created containing the NPC's full inventory
- NPC is marked deleted and scheduled for respawn (if spawn data exists with respawn timers)
- NPCs without respawn timers are treated as "unkillable" (they do not stay dead)

### Player Death:
- Corpse is created containing inventory items only (not equipped gear -- equipment stays on character)
- Corpse decays after **30 minutes**
- **XP penalty**: lose **5%** of XP above the current level threshold (cannot de-level)
- Player respawns at the **default start location** (`central_city.city_gates`) with full HP/mana/stamina
- All states, cooldowns, stuns, and combat flags are cleared

---

## Player Commands

### Movement
`north`/`n`, `south`/`s`, `east`/`e`, `west`/`w`, `up`/`u`, `down`/`d`, `out`, `in`, `go <keyword>`, `enter <keyword>`, `flee`, `leaverandom`

### Communication
`say`, `sayto <target>`, `ask <target>`, `tell <target>`, `whisper <target>`, `emote`

### Perception
`look`/`l`, `examine`/`ex`, `inspect`

### Items
`get`/`take`, `drop`, `put`, `give`, `open`, `close`, `lock`, `unlock`, `use`, `quaff`, `drink`, `eat`, `read`, `apply`

### Equipment
`inventory`/`inv`/`i`, `equip`/`eq`, `unequip`

### Character State
`stand`, `sit`, `rest`, `sleep`, `meditate`/`med`

### Combat
`attack`/`kill`, `flee`

### Character Info
`character`/`char`, `self`, `status`, `skills`, `level`, `quests`, `triggers`

### Progression
`levelup`, `skillup`, `improvestat`

### Meta
`commands`, `savegame`, `quit`/`logout`

### Social Emotes
`kick`, `kiss`, `lick`, `congratulate`, `bow`, `thank`, `sing`, `dance`, `touch`, `wink`, `laugh`, `sigh`, `nod`, `shrug`, `cheer`, `frown`, `wave`, `clap`, `gaze`, `smile`, `glare`, `cry`, `yawn`, `think`

### Admin / Privileged Commands
Available to admins and scripts: `echo`, `echoto`, `echoexcept`, `spawn`, `spawnobj`, `teleport`, `transfer`, `force`, `command`, `damage`, `heal`, `applystate`, `setstat`, `getstat`, `settempvar`, `setpermvar`, `deltempvar`, `delpermvar`, `setquestvar`, `getquestvar`, `showvars`, `goto`, `where`, `reload`, `possess`, `debug`, `show`, `list`, `at`, `walkto`, `route`, `signal`, `pause`, `delay`, `interrupt`, `stop`, `makeadmin`, `save`, `load`, and more.

---

## Character Attitudes

NPCs have an attitude toward players that affects behavior:

| Attitude | Behavior |
|----------|----------|
| `HOSTILE` | Attacks on sight |
| `UNFRIENDLY` | Will not help, may attack if provoked |
| `NEUTRAL` | Default; indifferent |
| `FRIENDLY` | Helpful, will not attack |
| `CHARMED` | Magically compelled friendliness |
| `DOMINATED` | Magically controlled |

---

## Room Definitions

Rooms are defined in zone YAML files under `ZONES.<zone_id>.ROOMS.<room_id>`:

```yaml
ROOMS:
  town_square:
    name: "Town Square"
    description: "A bustling town square with a fountain in the center."
    subzone: "downtown"          # optional grouping
    exits:
      north: market_street       # simple: just destination room id
      south:                     # full exit with door
        destination: residential_area
        description: "A wooden gate leads south."
        door:
          name: "wooden gate"
          keywords: [gate, wooden]
          is_closed: true
          is_locked: false
          key_id: null
          linked_exit: "zone.room.direction"  # syncs door state
    characters:                  # NPCs to spawn in this room
      - id: town_guard
        quantity: 2
        respawn time min: 300    # seconds; omit both for unkillable
        respawn time max: 600
    objects:                     # items on the floor
      - id: fountain
        quantity: 1
    triggers:                    # room triggers
      - type: on_say
        criteria:
          - subject: "%*%"
            operator: contains
            predicate: "help"
        script: |
          echo A helpful sign lights up nearby.
```

### Room Flags

`DARK`, `NO_MOB`, `INDOORS`, `NO_MAGIC`, `NO_SUMMON`, `FLIGHT_NEEDED`, `UNDERWATER`

---

## Object Definitions

Objects are defined under `ZONES.<zone_id>.OBJECTS`:

```yaml
OBJECTS:
  - id: iron_sword
    name: "an iron sword"
    article: "an"
    description: "A sturdy iron sword with a leather-wrapped hilt."
    keywords: [iron, sword]
    weight: 5
    value: 50
    equip_locations: [main hand]
    attack_bonus: 5
    damage_type: slashing
    damage: 2d6+1
    dodge_penalty: 0
    critical_chance: 5
    critical_multiplier: 150
    permanent_flags: [IS_WEAPON]
    triggers: []
```

### Object Properties

| Field | Description |
|-------|-------------|
| `id`, `name`, `description` | Identity and display text |
| `article` | Article ("a", "an", "the", "some") |
| `keywords` | Words players can use to target the object |
| `weight`, `value` | Physical weight and monetary value |
| `equip_locations` | List of valid equipment slots |
| `attack_bonus` | Bonus to hit when wielded |
| `damage_type` | Damage type when wielded |
| `damage` | Dice string (NdS+B) for weapon damage |
| `dodge_penalty` | Penalty to dodge when equipped |
| `damage_multipliers` | Map of damage type to resistance multiplier |
| `damage_reduction` | Map of damage type to flat reduction |
| `heal_amount`, `heal_dice` | Fixed or dice-based healing for consumables |
| `mana_restore`, `stamina_restore` | Resource restoration for consumables |
| `use_message` | Message displayed when item is used |
| `charges` | Number of uses (-1 = single-use, destroyed on use) |
| `contents` | List of object IDs contained within (containers) |
| `pronoun_subject/object/possessive` | Custom pronouns |

### Object Flags

`IS_ARMOR`, `IS_WEAPON`, `IS_CONTAINER`, `NO_TAKE`, `IS_STATIC`, `IS_OPENABLE`, `IS_CLOSED`, `IS_LOCKABLE`, `IS_LOCKED`, `IS_HIDDEN`, `IS_DOOR`, `IS_CONSUMABLE`, `IS_POTION`, `IS_BANDAGE`, `IS_FOOD`

---

## Character / NPC Definitions

Characters are defined under `ZONES.<zone_id>.CHARACTERS`:

```yaml
CHARACTERS:
  - id: town_guard
    name: "a town guard"
    article: "a"
    long_description: "A sturdy guard patrols here, watching for trouble."
    keywords: [guard, town]
    attitude: NEUTRAL
    permanent_flags: [HUMANOID, IS_SENTINEL, AGGRESSIVE_IF_ATTACKED]
    attributes:
      strength: 14
      dexterity: 12
      constitution: 14
      intelligence: 10
      wisdom: 10
      charisma: 10
    class:
      fighter:
        level: 5
        skills:
          mighty kick: 30
          bash: 25
    hit_dice: 3d10+10
    natural_attacks:
      - attack_noun: "sword slash"
        attack_verb: "slashes"
        potential_damage:
          - damage_type: slashing
            damage_dice: 2d6+3
    hit_modifier: 60
    dodge_dice: 1d50+10
    critical_chance: 5
    critical_multiplier: 150
    experience_points: 500
    equipment: [iron_sword, chain_armor]
    inventory: [health_potion]
    saving_throw_bonuses:
      fortitude: 10
      reflex: 5
      will: 5
    damage_multipliers:
      fire: 1.0        # normal damage
      poison: 0.5      # 50% resistance
    guards_rooms: [zone.restricted_area]
    triggers: []
```

### Character Properties

| Field | Description |
|-------|-------------|
| `id`, `name`, `long_description` | Identity and room description |
| `keywords` | Words players can use to target the NPC |
| `attitude` | Starting attitude toward players |
| `class` | Map of class roles to `{level, skills}` |
| `class_priority` | Ordered list for multiclass NPCs |
| `attributes` | Six core attributes |
| `hit_dice` | Dice string for max HP calculation |
| `natural_attacks` | Unarmed/special attack definitions |
| `hit_modifier` | Base hit bonus |
| `dodge_dice` | Base dodge dice |
| `critical_chance`, `critical_multiplier`, `critical_damage_bonus` | Crit stats |
| `experience_points` | XP awarded on kill |
| `equipment` | List of object IDs to equip on spawn |
| `inventory` | List of object IDs to place in inventory on spawn |
| `saving_throw_bonuses` | Bonus to fortitude/reflex/will |
| `damage_multipliers` | Per-type damage resistance |
| `damage_reductions` | Per-type flat damage reduction |
| `guards_rooms` | List of room IDs this NPC blocks access to |
| `group_id` | Optional group identifier |
| `llm_conversation` | LLM personality/goals configuration for AI-driven conversation |

### Character Permanent Flags

`IS_PC`, `CAN_DUAL_WIELD`, `IS_INVISIBLE`, `SEE_INVISIBLE`, `DARKVISION`, `IS_UNDEAD`, `IS_SENTINEL`, `NO_WANDER`, `STATIONARY`, `EVASIVE`, `QUEST_GIVER`, `AGGRESSIVE_IF_ATTACKED`, `MINDLESS`, `COWARDLY`, `PROTECTED`, `HUMANOID`

Special legacy strings: `is_aggressive` / `aggressive` set attitude to `HOSTILE`; `immune_poison` sets poison multiplier to 0; `immune_charm` / `immune_fear` set will save bonus to 100.

---

## Triggers and Scripting

Triggers are the event-driven scripting system that brings the world to life. They can be attached to **rooms**, **objects**, or **characters**. When an event fires, matching triggers evaluate their criteria and, if all criteria pass, execute their script.

### Trigger Types

| Trigger | Fires When | Owner |
|---------|------------|-------|
| `on_say` | Someone uses `say` in the room | Room, Character |
| `on_tell` | Directed speech (`sayto`, `tell`, `whisper`, `ask`) to the owner | Character |
| `on_see` | Room-visible text is displayed (arrivals, says, echoes) | Room |
| `on_arrive` | Someone arrives at the room | Room, Character, Object |
| `on_leave` | A character leaves the room | Room, Character, Object |
| `on_enter` | The owning character enters any room | Character |
| `on_receive` | NPC receives an item via `give` | Character |
| `on_get` | Object is picked up | Object |
| `on_drop` | Object is dropped | Object |
| `on_open` | Door/container opened | Object, Room exit |
| `on_close` | Door/container closed | Object, Room exit |
| `on_lock` | Door/container locked | Object, Room exit |
| `on_unlock` | Door/container unlocked | Object, Room exit |
| `on_use` | Object is used/drunk/read | Object |
| `on_attacked` | Attack attempted against the defender (hit or miss) | Character |
| `catch_zerohp` | HP would go to 0; script can heal to cancel death | Character |
| `catch_go` | Player uses `go`/`enter` keyword; checked before exit resolution | Room |
| `catch_command` | First word of input matches `oneof` list; stops normal command | Room, Character, Object |
| `catch_inspect` | Someone looks at something matching criteria; adds to description | Room, Character, Object |
| `on_look` | Replaces default description; script should output description | Room, Character, Object |
| `timer_tick` | Periodic tick; can use `%time_elapsed%` for timing | Any |
| `on_signal` | A `signal` command is received | Any |

### Trigger Flags

- `only_when_pc_room` -- timer_tick only fires when a player is in the room
- `only_when_pc_zone` -- timer_tick only fires when a player is in the zone

### Trigger Criteria

Each trigger has a list of criteria, all of which must pass (AND logic):

```yaml
criteria:
  - subject: "%*%"
    operator: contains
    predicate: "hello, hi, greetings"
```

**Operators:**

| Operator | Behavior |
|----------|----------|
| `eq` | Exact string equality |
| `neq` | Not equal |
| `contains` | Substring match (case-insensitive); comma-separated predicate = any match (OR) |
| `oneof` | Subject matches one of comma-separated values |
| `numgt` | Numeric greater than |
| `numlt` | Numeric less than |
| `numeq` | Numeric equal |
| `numgte` | Numeric greater or equal |
| `numlte` | Numeric less or equal |

### Script Commands

Script lines are executed as game commands after variable substitution. Character-owned triggers queue commands with pacing; room/object-owned triggers execute immediately.

**Multiple commands** can be placed on one line separated by semicolons.

#### Privileged Script Commands

| Command | Purpose |
|---------|---------|
| `echo <text>` | Send text to everyone in the room |
| `echoto <target> <text>` | Send text to a specific character |
| `echoexcept <target> <text>` | Send text to everyone in room except target |
| `spawn <char_id>` | Spawn an NPC in the room |
| `spawnobj <obj_id>` | Spawn an object in the room |
| `teleport <target> <zone.room>` | Move a character to a specific room |
| `transfer <target> <zone.room>` | Transfer a character to a room |
| `force <target> <command>` | Force a character to execute a command |
| `command <target> <command>` | Issue a command as a character |
| `damage <target> <amount> <type>` | Deal damage to a target |
| `heal <target> <amount>` | Heal a target |
| `applystate <target> <state> <args>` | Apply a timed state/buff/debuff |
| `setstat <target> <stat> <value>` | Set a character stat |
| `getstat <target> <stat>` | Get a character stat value |
| `settempvar <name> <value>` | Set a temporary variable on the actor |
| `setpermvar <name> <value>` | Set a persistent variable on the actor |
| `deltempvar <name>` | Delete a temporary variable |
| `delpermvar <name>` | Delete a persistent variable |
| `setquestvar <name> <value>` | Set a quest variable |
| `getquestvar <name>` | Get a quest variable |
| `removeitem <target> <item_id>` | Remove an item from a character |
| `pause <ticks>` | Pause script execution for N ticks |
| `delay <ticks>` | Delay before next command |
| `walkto <room_id>` | Pathfind and walk to a room |
| `route <room_list>` | Walk a specific route |
| `signal <scope> <message>` | Send a signal to registered listeners |
| `interrupt` | Interrupt current casting/action |
| `stop` | Stop command queue processing |

Scripts can also use any normal player command: `say`, `give`, `attack`, `north`, `open`, `close`, etc.

#### Instant Commands

These execute without consuming a tick: `settempvar`, `setpermvar`, `deltempvar`, `delpermvar`, `showvars`, `setquestvar`, `getquestvar`, `setstat`, `getstat`, `signal`, `deregistersignals`.

### Script Variables

Variables use `%name%` substitution. Available variables depend on the trigger type:

| Variable | Meaning |
|----------|---------|
| `%s%` / `%S%` | Source/subject character (lowercase name / capitalized) |
| `%a%` / `%A%` | Actor/owner character |
| `%t%` / `%T%` | Target character |
| `%*%` | Full text of the triggering input |
| `%room_id%` | Current room ID (for `on_enter`) |
| `%use_type%` | How an object was used (for `on_use`) |
| `%target%` / `%target_id%` | Target of "use on" actions |
| `%time_elapsed%` | Ticks since trigger was enabled (for `timer_tick`) |

Pronoun variables are also available: `%he%`/`%she%`, `%him%`/`%her%`, `%his%`/`%hers%`, etc.

Variable mappings vary by trigger type (e.g., `on_tell` maps `%s%` to the speaker and `%a%` to the NPC recipient; `on_attacked` maps `%a%` to the attacker and `%s%` to the defender).

### Script Functions

Inline functions use `$function(args)` syntax and are evaluated before command execution:

| Function | Purpose |
|----------|---------|
| `$cap(text)` | Capitalize first letter |
| `$name(id)` | Get actor name from ID |
| `$add(a, b)`, `$sub`, `$mul`, `$div`, `$mod` | Arithmetic |
| `$random(min, max)` | Random integer in range |
| `$random(NdS+B)` | Roll dice notation (e.g. `$random(3d6+6)`) |
| `$numeq(a, b)`, `$numgt`, `$numlt`, `$numgte`, `$numlte` | Numeric comparisons (return true/false) |
| `$between(value, min, max)` | Range check |
| `$tempvar(name)` | Get temporary variable value |
| `$permvar(name)` | Get persistent variable value |
| `$questvar(name)` | Get quest variable value |
| `$hasitem(target, item_id)` | Check if target has item (any slot) |
| `$hasiteminv(target, item_id)` | Check if target has item in inventory |
| `$hasitemeq(target, item_id)` | Check if target has item equipped |
| `$equipped(target, slot)` | Check what is equipped in a slot |
| `$locroom(target)` | Get target's current room ID |
| `$loczone(target)` | Get target's current zone ID |
| `$olocroom(object)` | Get object's room ID |
| `$oloczone(object)` | Get object's zone ID |
| `$words(text, index)` | Extract word at index from text |

### Conditional Logic

Scripts support `$if` blocks for branching:

```
$if(%*%, contains, keyword){
  say I heard you say the keyword!
} else {
  say I didn't catch that.
}
```

Conditions use the same operators as trigger criteria. Blocks can be nested.

### Trigger Attachment

- **Rooms**: Triggers defined under room YAML, enabled when the zone is built
- **Objects**: Triggers defined under object YAML, enabled when an instance is created from the definition
- **Characters**: Triggers defined under character YAML, enabled when an instance is created from the definition

### Trigger Evaluation Order (for `catch_command`)

1. Room triggers
2. Object triggers (objects in the room)
3. Character triggers (characters in the room)
4. Inventory object triggers (top-level inventory only)

If any `catch_command` trigger fires, normal command processing is halted.

---

## Quest System

Quests are defined in zone YAML under `ZONES.<zone_id>.quests` and tracked through quest variables (`setquestvar` / `getquestvar`). Quest schemas define:

- Variable names and descriptions
- Progression stages
- Completion conditions

Quest variables can trigger re-evaluation and LLM knowledge updates when defined in quest YAML. Players can view active quests with the `quests` command.

---

## LLM NPC Conversations

NPCs can be configured with AI-driven conversation via the `llm_conversation` field in character YAML. This includes:

- **Personality**: How the NPC speaks and behaves
- **Goals**: What the NPC is trying to accomplish
- **Knowledge**: What the NPC knows about the world
- **Actions**: What commands the NPC can invoke in response to conversation

When a player uses `tell`, `sayto`, or `ask` directed at an NPC, and no trigger handles the input, the conversation is optionally routed to the LLM system for a contextual AI response. The LLM provider is configurable (Gemini, OpenAI, Claude, Grok, or local).

---

## Player Saving and Loading

Player characters are saved as individual YAML files in the `player_saves/` directory.

### Saved Data Includes:
- Character identity (name, class, level, attributes)
- Current location (zone and room)
- Skills and skill levels
- HP, mana, stamina (current and max)
- Combat stats (hit modifier, dodge, crit, damage multipliers)
- Full inventory and equipment (with recursive object serialization)
- Permanent and temporary flags
- Character states and cooldowns (configurable)
- Quest variables

### Password Security
Passwords are hashed using PBKDF2-SHA256. Stub saves are created at character creation with name, password hash, selected class, and allocated stats.

### Linkdead Handling
If a player disconnects, there is a **60-second grace period** during which they can reconnect and resume their session.
