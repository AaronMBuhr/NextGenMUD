This project aims to implement a **Universal Gold-Sink Blessing System** that is architecturally clean, economically scalable, and class-neutral. By leveraging your existing `Actor` and `ActorState` hierarchy, we are moving toward a system where blessings are physically tied to gear but balanced through a "Complexity Tax" (scaling costs).

---

## 1. The End-State Specification

### A. Architectural Integration

* **Actor-State Unified Model:** All entities (Characters, Rooms, Items) are `Actors`. A "Blessing" is a specialized `ActorState` instance.
* **Non-Mutating Bonuses:** Blessings do **not** change base stats in the database. Instead, they provide "Attribute Modifiers" that the engine calculates on the fly.
* **Attribute Key Mapping:** States identify their benefits by field name (e.g., `max_mana`, `damage_low`), making the system infinitely extensible to new stats.

### B. Player Experience & Mechanics

* **The "Equipped Only" Ritual:** Players must equip gear to have it blessed by an NPC. This ensures targeting precision and immersion.
* **Benefit Scaling:** Benefits are percentage-based (e.g., +10%), ensuring they remain valuable as players acquire better gear.
* **Economic Scaling:** Costs are calculated as a percentage of the item's total `value`. High-level players with legendary gear pay a "Maintenance Tax" appropriate to their higher income.
* **Class Neutrality:** Different "Rites" have different cost multipliers. High-value Mage stats (Mana) cost more per ritual than Fighter stats (Stamina), ensuring a Fighter blessing 5 items and a Mage blessing 2 items arrive at a similar total gold spend.

---

## 2. Implementation Task Breakout

### Phase 1: Core Architecture Refinement

Standardizing the `ActorState` and `Actor` relationship to support dynamic attribute lookups.

* **Task 1.1: Define `StatModifierState` subclass.**
* Inherit from `ActorState`.
* Add a `modifiers` dictionary: `{"field_name": value}`.
* Implement `get_modifier(field_name)`.


* **Task 1.2: Implement `Actor.get_effective_stat(field_name)`.**
* Logic: `Base Value + Sum(Active States[field_name])`.
* Ensure it handles both flat additions and percentage multipliers.


* **Task 1.3: Update Character Stat Properties.**
* Modify `Character.max_mana` and `Character.max_stamina` to include bonuses from **both** the character's own states and all currently equipped `GameItem` states.



### Phase 2: NPC & Scripting Logic

Building the "Enchanter" interface in `central_city.yaml` and potentially `shattered_dominion.yaml`.

* **Task 2.1: Add `$item_value` and `$is_equipped` script helpers.**
* Expose these Python methods to the YAML script interpreter.


* **Task 2.2: Implement the "Rite of the Sun King" (Elias).**
* Create the `sayto elias bless <item> <rite>` trigger.
* Logic: Identify item → Calculate fee (20% of value) → Apply `StatModifierState`.


* **Task 2.3: Implement Cost/Benefit Tiers.**
* "Fortitude" (Stamina): Low cost multiplier.
* "Astral" (Mana/Spell): High cost multiplier.



### Phase 3: Duration & Task Scheduling

Ensuring the "Gold Sink" is recurring and persists correctly.

* **Task 3.1: Implement State Expiration Task.**
* When a blessing is added, schedule a task in the "Bucket" to remove the state after `X` minutes.


* **Task 3.2: Add "Faded" Notifications.**
* The expiration task should send a message to the owner: *"The holy light fades from your [Item]."*


* **Task 3.3: Serialization (Optional but Recommended).**
* Ensure that if an object with a state is saved/loaded, the state (and its remaining duration) is preserved.



### Phase 4: UI & Polish

Giving the player feedback so they know the gold was well spent.

* **Task 4.1: Update `examine` command.**
* Append `(Blessed)` or show the specific stat bonuses when a player looks at their gear.


* **Task 4.2: Combat "Proc" Messages.**
* Add a logic hook so that when a blessed weapon is used, the player occasionally sees: *"Your blade flares with holy light!"*



---

## 3. The "Next Step"

The most critical "Day 1" task is **Task 1.1 and 1.2**: creating the logic that allows an `Actor` to actually "see" the modifiers stored in its `ActorStates`. Without this, the blessings will exist in memory but won't affect gameplay.

