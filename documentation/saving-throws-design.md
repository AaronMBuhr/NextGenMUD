
# Saving Throws

**Class-Based Percentage System (v2.0)**

## Design Goals

* Saves determined by **class, ability scores, and level difference**
* No progression with character level (no trainable save skills)
* Same-level parity: class base save is the baseline
* Per-skill tuning via `save_difficulty` on each Skill definition
* Simple, inspectable formula

---

## Formula

```
SaveChance = clamp(
    ClassBaseSave
    + (DefenderAttribute - AttackerAttribute) × ATTRIBUTE_SAVE_MULTIPLIER
    + (DefenderBestLevel - AttackerClassLevel) × LEVEL_DIFF_MULTIPLIER
    - SkillSaveDifficulty
    + SavingThrowBonus,
    5,
    95
)
```

* Roll 1-100; if roll <= SaveChance, the target **saves** (resists the effect)
* Absolute bounds: **5% min, 95% max**

---

## Term Definitions

### ClassBaseSave

Looked up from `Constants.SAVING_THROW_BASES` by the defender's best class for that save type.

| Class | Fortitude | Reflex | Will |
|-------|-----------|--------|------|
| Fighter | 50 | 35 | 30 |
| Rogue | 30 | 50 | 35 |
| Mage | 30 | 35 | 50 |
| Cleric | 40 | 30 | 50 |

For multiclass characters, the best base save across all classes is used.

### Attribute Modifier

`(DefenderAttribute - AttackerAttribute) × ATTRIBUTE_SAVE_MULTIPLIER`

* `ATTRIBUTE_SAVE_MULTIPLIER = 2` (default, configurable)
* Attribute mapping: Fortitude → CON, Reflex → DEX, Will → WIS
* Attacker attribute depends on the skill's class: STR for Fighter, DEX for Rogue, INT for Mage, WIS for Cleric
* Example: Defender CON 16 vs Attacker STR 12 = +8 to save chance

### Level Difference

`(DefenderBestLevel - AttackerClassLevel) × LEVEL_DIFF_MULTIPLIER`

* `LEVEL_DIFF_MULTIPLIER = 3` (default, configurable)
* Defender uses their highest single-class level
* Attacker uses their level in the skill's base class
* Example: Defender level 15 vs Attacker Fighter level 10 = +15 to save chance

### SkillSaveDifficulty

Per-skill tuning on the `Skill` data object. Positive values make the save harder (subtracted from save chance).

* Charm: `save_difficulty: -10` (easy to resist)
* Fireball: `save_difficulty: 0` (standard)
* Power Word Stun: `save_difficulty: 15` (hard to resist)

### SavingThrowBonus

From the character's `saving_throw_bonuses` dict. A value of 100 means immune (automatic save). Used for special resistances (e.g., undead immune to charm = `will: 100`).

---

## Save Types

| Save Type | Attribute | Resists |
|-----------|-----------|---------|
| Fortitude | Constitution | Physical effects: stun, knockdown, poison, forced movement |
| Reflex | Dexterity | Area effects: fireballs, traps, backstab, disarm |
| Will | Wisdom | Mental effects: charm, fear, intimidation, holy damage |

---

## Skill Save Assignments

Each skill's `Skill(...)` definition includes `save_type` and `save_difficulty`:

**Fighter:** Mighty Kick (fort/0), Demoralizing Shout (will/0), Intimidate (will/-5), Slam (fort/0), Bash (fort/5), Disarm (ref/0), Rend (fort/0), Shield Sweep (ref/0)

**Mage:** Magic Missile (ref/-10), Fireball (ref/0), Ignite (ref/0), Mana Burn (will/5)

**Cleric:** Smite (will/0), Judgment (will/5), Divine Reckoning (will/10)

**Rogue:** Backstab (ref/0)

Skills without `save_type` (buffs, heals, utility, pure damage) skip the save check entirely.

---

## Examples

**Level 10 Fighter (STR 16) uses Bash (fort, difficulty 5) on Level 10 Mage (CON 10):**
* Base: 30 (Mage Fortitude)
* Attr: (10 - 16) × 2 = -12
* Level: (10 - 10) × 3 = 0
* Difficulty: -5
* Result: 30 - 12 - 5 = **13% save chance** (Mage gets wrecked by physical CC)

**Level 10 Mage (INT 16) uses Fireball (ref, difficulty 0) on Level 10 Rogue (DEX 16):**
* Base: 50 (Rogue Reflex)
* Attr: (16 - 16) × 2 = 0
* Level: (10 - 10) × 3 = 0
* Result: **50% save chance** (Rogue's specialty)

**Level 15 Mage vs Level 10 Fighter, Fireball:**
* Base: 35 (Fighter Reflex)
* Attr: (12 - 16) × 2 = -8
* Level: (10 - 15) × 3 = -15
* Result: 35 - 8 - 15 = **12% save chance** (level advantage is devastating)

---

## Configuration

All values are configurable in `app_config.yaml` / `Constants`:

```yaml
ATTRIBUTE_SAVE_MULTIPLIER: 2
LEVEL_DIFF_MULTIPLIER: 3
SAVE_CHANCE_MIN: 5
SAVE_CHANCE_MAX: 95
SAVING_THROW_BASES:
  fighter: { fortitude: 50, reflex: 35, will: 30 }
  rogue:   { fortitude: 30, reflex: 50, will: 35 }
  mage:    { fortitude: 30, reflex: 35, will: 50 }
  cleric:  { fortitude: 40, reflex: 30, will: 50 }
```
