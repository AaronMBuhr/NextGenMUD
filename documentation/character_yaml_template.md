# Character YAML Specification with Multiclassing Support

This document provides templates and examples for defining characters with multiple classes in NextGenMUD.

## Basic Structure

```yaml
name: Character Name
article: a                        # article to use (a, an, the)
description: Character description
pronoun_subject: he               # he/she/it/they
pronoun_object: him               # him/her/it/them  
pronoun_possessive: his           # his/her/its/their
group_id: group_name              # optional, for grouping NPCs
attitude: neutral                 # hostile, neutral, friendly

# Define class priority (primary, secondary, tertiary)
# This controls which class is considered primary/secondary/tertiary
# If not specified, classes are prioritized in the order they appear in the 'class' section
class_priority:
  - fighter      # Primary class
  - mage         # Secondary class
  - rogue        # Tertiary class

# Define classes and levels
class:
  fighter:
    level: 5
    skills:
      cleave:
        level: 2
      shield_bash:
        level: 1
  mage:
    level: 3
    skills:
      magic_missile:
        level: 2
      fireball:
        level: 1
  rogue:
    level: 2
    skills:
      backstab:
        level: 1

# Other character attributes
permanent_flags:
  - can_cast_spells

experience_points: 5000

damage_multipliers:
  physical: 0.8
  fire: 0.9
  cold: 1.1

damage_reductions:
  physical: 2
  fire: 1

attributes:
  strength: 16
  intelligence: 14
  wisdom: 10
  dexterity: 12
  constitution: 15
  charisma: 8

hit_dice: 5d10+15
dodge_dice: 1d50+10
hit_modifier: 90
critical_chance: 5
critical_multiplier: 150

natural_attacks:
  - attack_noun: fist
    attack_verb: punches
    potential_damage:
      - damage_type: physical
        damage_dice: 1d6+3

equipment:
  - longsword
  - shield
  - leather_armor

inventory:
  - healing_potion
  - torch
```

## Multiclass Character Examples

### Fighter/Mage Character

```yaml
name: Elric the Spellblade
article: a
description: A warrior skilled in both combat and arcane arts
pronoun_subject: he
pronoun_object: him
pronoun_possessive: his

class_priority:
  - fighter  # Primary class
  - mage     # Secondary class

class:
  fighter:
    level: 6
    skills:
      cleave:
        level: 2
      disarm:
        level: 1
  mage:
    level: 4
    skills:
      magic_missile:
        level: 2
      fireball:
        level: 1

hit_dice: 6d10+18
dodge_dice: 1d60+12
hit_modifier: 95
critical_chance: 5
critical_multiplier: 150

natural_attacks:
  - attack_noun: fist
    attack_verb: punches
    potential_damage:
      - damage_type: physical
        damage_dice: 1d6+3

equipment:
  - enchanted_longsword
  - mage_robe
```

### Rogue/Cleric Character

```yaml
name: Serena the Shadow Priest
article: a
description: A stealthy follower of the dark gods
pronoun_subject: she
pronoun_object: her
pronoun_possessive: her

class_priority:
  - rogue    # Primary class
  - cleric   # Secondary class

class:
  rogue:
    level: 5
    skills:
      backstab:
        level: 3
      hide:
        level: 2
  cleric:
    level: 3
    skills:
      cure_light_wounds:
        level: 2
      bless:
        level: 1

hit_dice: 5d8+10
dodge_dice: 1d70+15
hit_modifier: 85
critical_chance: 10
critical_multiplier: 200

natural_attacks:
  - attack_noun: dagger
    attack_verb: stabs
    potential_damage:
      - damage_type: physical
        damage_dice: 1d4+2

equipment:
  - shadow_dagger
  - dark_robes
  - holy_symbol
```

## Notes on Multiclassing

1. Characters can have up to 3 classes (primary, secondary, tertiary)
2. Each class has independent level progression
3. Class priority determines which class benefits apply at full strength vs. reduced strength
4. Some skills and abilities may require a class to be the primary class to function at full effectiveness
5. XP is shared across all classes, but each class levels independently 