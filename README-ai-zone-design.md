# 📜 NextGenMUD Methodology Cheat Sheet

**Strategy:** Core-and-Plugin (Modular Assembly)
**Goal:** Build 3,000+ line zones by generating high-density "Feature Packs" to be merged via the Python utility.

### 1. The Build Workflow

1. **Phase 1: The Skeleton:** Define the `ZONES` metadata, `common_knowledge`, `quest_variables`, and a central hub of 5–10 rooms.
2. **Phase 2: Regional Blocks:** Provide 10–15 rooms per prompt to maintain descriptive quality and exit-logic integrity.
3. **Phase 3: Populate Layers:** Generate `CHARACTERS` and `OBJECTS` lists. Use full attribute blocks, class levels, and natural attacks.
4. **Phase 4: Logic Wiring:** Inject the `triggers` and `scripts` into existing entities using the ID-based merge syntax.

### 2. Revision Syntax (The "Patch" Rules)

Use these specialized markers in the revision YAML files to modify the base world:

* **Update/Merge:** Provide an `id` that already exists in the base file. The script will deep-merge dictionaries and extend lists by default.
* **Remove Field:** Use `-keyname: 0` to delete a specific field (e.g., `-is_aggressive: 0`).
* **Remove Entry:** Use `__remove__: true` within a dictionary to delete the entire room, character, or object.
* **Full Replace:** Use `__replace__: true` to overwrite a dictionary entirely instead of merging.
* **List Strategy:** Use `__list_strategy__: replace` to make child lists (like `triggers` or `permanent_flags`) overwrite the base list instead of appending to it.

### 3. Standards Checklist

* **Characters:** Must include `attributes`, `class` (Fighter, Mage, Cleric, Rogue), `hit_dice`, and `experience_points`.
* **LLM NPCs:** Must include `personality`, `speaking_style`, `knowledge` (with `reveal_threshold`), and `goals`.
* **Rooms:** Utilize `flags` (dark, indoors, no_mob) and descriptive `exits`.
* **Characters, Rooms, and Objects** Use extensive triggers scripting.

---

Initial Prompt:

> **Role:** You are an expert MUD World Builder and AI thought partner. We are building a massive, 3,000+ line zone for NextGenMUD using the **Core-and-Plugin (Modular)** methodology.
> **Task:** Generate **Phase 1: The Skeleton** for a new zone.
> **Zone Theme:** "The Sunken Citadel of Aethelgard"
> **Requirements for this phase:**
> 1. **Zone Metadata:** Name and a high-level description for builders.
> 2. **Common Knowledge:** Define 5–8 key lore points and geographic facts that NPCs in this zone will know.
> 3. **Quest Variables:** Establish the initial state machine (booleans/integers) for the zone's primary narrative arcs.
> 4. **Core Hub Rooms:** Provide the YAML for the central hub (5–10 rooms) that connects the major regions. Include detailed descriptions and initial exits.
> 
> 
> **Format:** Provide the output in a clean YAML block compatible with my `merge_mud_files.py` utility. Ensure all IDs are unique and follow the standards in the `world_building_guide.md`.


---
Revised methodology:

- first, all of the below until indicated otherwise is in concepts and descriptions
  rather than the raw yaml data
- devise the overarching concepts, which we've been talking about.
- design a rough zone map, breaking the zone into multiple sub-zones
  and indicating how they connect and relate.
- determine major npcs (people and creatures) for each zone, so that we have a zone-wide cast
- determine some quests or other multi-step-interaction-sequences, that may span sub-zones
- develop zone-wide common knowledge
- develop each sub-zone one at a time:
  - determine for each first the detailed map
  - then the sub-zone npcs with their associated objects, and npc groups
  - then how the sub-zone NPCs interact with the zone-wide quests
    (just descriptions, intended for both triggers and llm parameters)
  - then the sub-zone specific common knowledge (which may be multiple
    "common knowledge" items, so that not every character in the sub-zone
	has the same common knowledge but subsets of them do)

- now we start constructing the yaml in detail:
- first, the structural details for zone-spanning npcs
- then, for each sub-zone:
  - full sub-zone room detail, with triggers
  - full sub-zone npc list, without triggers or llm parameters
  - full sub-zone object list, with triggers, (whether held or in a room)
  - come back and add triggers and llm parameters to sub-zone npcs,
    over multiple responses as necessary for context limits
  - revise any of the above, and common knowledge, as appropriate
    after everything here has been detailed
- last, come back and add triggers and llm parameters to zone-spanning npcs
