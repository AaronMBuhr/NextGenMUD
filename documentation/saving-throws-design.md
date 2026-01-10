
# Saving Throws & Character Growth

**Functional Specification (v1.0)**

## Design Goals

* Support **multiclass characters** cleanly
* Prevent saving throws from becoming trivial at high level
* Ensure **same-level parity**:

  * L10 vs L10 ≈ L50 vs L50
* Avoid NPC-specific tuning or hidden penalties
* Give players **meaningful agency** and visible progression
* Keep calculations simple and inspectable

---

## Core Concepts

### 1. Saving Throws Are Opposed Checks

Saving throws are **not static DCs**.
They are resolved as **opposed values** between attacker and defender.

Only **relative power** matters.

---

## Saving Throw Resolution

### Final Save Chance

```
SaveChance =
  clamp(
    50
    + (Defender_Save - Attacker_Penetration)
    + situational_modifiers,
    5,
    95
  )
```

* `50` = baseline parity
* Result is a **percentage roll**
* Absolute bounds: **5% min, 95% max**

---

## Defender Save Calculation

```
Defender_Save =
  Save_Skill
+ (Relevant_Attribute × Attribute_Modifier)
+ gear_bonuses
+ buffs/debuffs
```

### Notes

* `Save_Skill` is a 0–100 value
* Attributes contribute modestly and slowly
* Gear and buffs are additive

---

## Attacker Penetration Calculation

```
Attacker_Penetration =
  Spell_or_Ability_Skill
+ (Relevant_Attribute × Attribute_Modifier)
+ spell_mastery
+ penetration_bonuses
```

### Notes

* Penetration mirrors saves numerically
* Keeps same-level difficulty consistent
* Prevents save trivialization at high levels

---

## Attribute Contribution

### Attribute Modifier

* **Default:** `Attribute × 2`
* Tunable later if needed

### Attribute → Save Mapping (Initial)

| Save Type                        | Attribute              |
| -------------------------------- | ---------------------- |
| Fortitude                        | Constitution           |
| Reflex                           | Dexterity              |
| Will                             | Wisdom                 |
| Reason                           | Intelligence           |

*(Exact mappings may be adjusted later without breaking the system.)*

---

## Character Growth Model

### Level Progression

* **Max Level:** 50
* Leveling grants:

  * Skill points (primary growth axis)
  * Occasional attribute choice (secondary axis)

---

### Attribute Advancement

* Characters gain **+1 attribute point every 10 levels**

  * Base attribute points to be selected by player at creation range from 1 to 20
  * Increase one point of player choice at Levels: 10, 20, 30, 40, 50
  * **Maximum: +5 total attributes**
* Player chooses where to assign each point
* Attributes are **not** automatically increased on level-up

#### Optional Constraints (Not Required for v1.0)

* This is for future reference only, left here for future reference and discussion.
* Soft cap (e.g., 22–24)
* Racial maximums
* Narrative or feat gating after a threshold

---

### Skills

* Save skills and offensive skills:

  * Scale from **0–100**
  * Increase through level-up allocation, training, or use
* Skills are the **primary determinant** of save effectiveness

---

## Multiclass Behavior

* No class-based save tables
* All classes contribute via:

  * Skill access
  * Attribute synergies
  * Passive modifiers (optional later)

Multiclass characters:

* Gain flexibility
* Sacrifice ceilings
* Require no special-case logic

---

## Outcome Resolution (Future Reference)

This is also for future reference only, left here for future reference and discussion.
Saving throws should support **graded outcomes**:

| Result               | Effect         |
| -------------------- | -------------- |
| Fail by large margin | Full effect    |
| Narrow failure       | Partial effect |
| Narrow success       | Reduced effect |
| Clear success        | Negated        |

*(Exact thresholds may be defined per ability.)*

---

## What This System Guarantees

* L10 vs L10 ≈ L50 vs L50
* High-level characters resist low-level threats naturally
* No NPC tuning required
* Player choices matter, but never dominate
* Long-term balance stability

---

## Future Extension Points (Out of Scope for Now)

* Dual-attribute saves
* Save rerolls / advantage mechanics
* Resistance layers and immunities
* Conditional penetration types
* Attribute growth via world events

---

## Summary

> **Saving throws are opposed, skill-driven, and level-relative.
> Attributes grow slowly, by player choice, and tilt outcomes rather than deciding them.**

This system is intentionally simple, robust, and extensible—appropriate for early testing and long-term evolution.

