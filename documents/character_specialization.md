# Character Specialization System

## Overview

The NextGenMUD character progression system uses a 7-tier skill structure with specializations unlocking at level 20. Characters progress through a base class before choosing a specialization that defines their later development.

## Skill Tiers

| Tier | Level Range | Description |
|------|-------------|-------------|
| 1    | 1-9         | Basic abilities common to all specializations |
| 2    | 10-19       | Advanced abilities common to all specializations |
| 3    | 20-29       | Basic specialization-specific abilities |
| 4    | 30-39       | Intermediate specialization-specific abilities |
| 5    | 40-49       | Advanced specialization-specific abilities |
| 6    | 50-59       | Master-level specialization-specific abilities |
| 7    | 60          | Ultimate specialization-specific ability |

## Base Classes and Specializations

Characters begin as one of four base classes. At level 20, they choose one of three specializations for their class.

### Wizard
- **Base Skills**: Tiers 1-2 (Levels 1-19)
- **Specializations** (chosen at Level 20):
  - **Evoker**: Focused on offensive damage spells
  - **Conjurer**: Focused on summoning and creation
  - **Enchanter**: Focused on mind control and enhancement

### Fighter
- **Base Skills**: Tiers 1-2 (Levels 1-19)
- **Specializations** (chosen at Level 20):
  - **Berserker**: Focused on offensive damage and rage
  - **Guardian**: Focused on defense and protection
  - **Reaver**: Focused on area attacks and battlefield control

### Rogue
- **Base Skills**: Tiers 1-2 (Levels 1-19)
- **Specializations** (chosen at Level 20):
  - **Duelist**: Focused on single-target combat
  - **Assassin**: Focused on stealth and critical strikes
  - **Infiltrator**: Focused on traps, locks, and evasion

### Cleric
- **Base Skills**: Tiers 1-2 (Levels 1-19)
- **Specializations** (chosen at Level 20):
  - **Warpriest**: Focused on combat and divine wrath
  - **Restorer**: Focused on healing and protection
  - **Ritualist**: Focused on buffs and battlefield control

## Implementation Notes

1. Characters gain access to all skills in tiers 1-2 by leveling up their base class
2. At level 20, players must choose a specialization
3. After choosing a specialization, characters gain access to new skills from tiers 3-7 as they level up
4. Specialization choice is permanent
5. Skills from tiers 1-2 remain available after specializing
6. Each tier contains multiple skills/abilities
7. XP requirements follow the global progression table for all classes 