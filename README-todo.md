# README-todo

## Pre-release

Checklist before letting players in.

### Critical (fix before any players)

| Item | Where | Notes |
|------|--------|------|
| **Admin flag default** | `comprehensive_game_state.py` ~199 | All loaded characters get admin flags by default. Remove so only intended admins have admin. |
| **Start location / template** | `constants.py` | `DEFAULT_START_LOCATION` and `DEFAULT_CHARACTER_TEMPLATE = "master_zone.test_player"` reference zone data. Use real starting zone and character template as needed. |
| **Stealth isinstance bug** | `comprehensive_game_state.py` ~1455 | `isinstance(s) == CharacterStateStealthed` is wrong (and crashes). Use `isinstance(s, CharacterStateStealthed)`. |
| **Save file corruption** | Load path for player saves | No validation of save file integrity; corrupted YAML can crash load. Add try/except and graceful fallback. |

### Important (strongly recommended)

| Item | Notes |
|------|--------|
| **Trading / economy** | No buy/sell commands or visible currency tracking. Add if the world has vendors. |
| **Status effects** | Burning, poisoned, etc. are not implemented (TODOs in code). Add if content expects them. |
| **Stealth / perception** | Stealth exists but detection is not actually calculated (stub). |
| **Group / party commands** | `group_id` exists in model but no commands to form/leave groups. |
| **Quest log** | Quest variables exist but no command for players to see their quest state. |
| **OOC / global chat** | No cross-zone channel; only say/tell in room. |
| **HP/mana/stamina regen: all-character vs scheduled** | Regen currently runs for all characters each tick (`main_process.py`). `EventType.HP_REGEN` / `STAMINA_REGEN` exist but are unused. Decide: keep global tick regen, or switch to per-character scheduled events (and document/remove unused event types). |

### Production cleanup

| Item | Notes |
|------|--------|
| **LLM NPC marker** | NPCs with LLM conversations get `*` appended in `core_actions.py`. Remove for release. |
| **Configurable values** | Move to config: `BASE_STARTING_HP = 20`, corpse decay (30 min), etc. |
| **Debug logging** | Many `logger.debug3()` calls; consider gating or reducing for production. |

---

## Code TODOs

Collected from the codebase (excluding abstract interface stubs).

### NextGenMUDApp/nondb_models/characters.py

- **715** — `TODO:L: added statuses for burning, poisoned, etc.`
- **764** — `TODO:M: Add perception vs stealth skill check`
- **837** — `TODO:M: add status effects`
- **1689** — `TODO:M: add status effects`

### NextGenMUDApp/comprehensive_game_state.py

- **199** — `TODO: Remove admin default` (also in pre-release)
- **380** — `TODO:L: should we limit these to can-see?` (find_all_characters visibility)
- **1448** — `TODO:L: maybe handle invisible objects`
- **1457** — `TODO:L: this probably should log an error message` (stealth state check)

### NextGenMUDApp/command_handler.py

- **661** — `TODO: Integrate with your combat system`
- **679** — `TODO: Actually move the NPC to another room`
- **683** — `TODO: Implement item giving logic`
- **1027** — `TODO:L: add additional logic for no args, for "me", for objects`
- **1076** — `TODO:M: add targeting objects and rooms`
- **2926** — `TODO:L: maybe some situations where target doesn't retaliate?`
- **3083** — `TODO:L: fighting who / fought by?`
- **3084** — `TODO:H: classes`
- **3085** — `TODO:H: inventory`
- **3086** — `TODO:H: equipment`
- **3087** — `TODO:M: dmg resist & reduct`
- **3088** — `TODO:M: natural attacks`
- **3183** — `TODO:M: add max carry weight`
- **3622** — `TODO:M: add targeting objects and rooms`
- **3820** — `TODO: In final version, players will only get one save slot`
- **3839** — `TODO: In final version, players will only get one save slot`

### NextGenMUDApp/core_actions.py

- **82** — `TODO:M: handle batching multiples`
- **246** — `# TODO:L: figure out what direction "from" based upon back-path` (commented out; flee)
- **389** — `TODO: maybe switch command, or just allow bringing someone else into the fight`
- **840** — `TODO:M: figure out weapons`
- **841** — `TODO:L: deal with nouns and verbs correctly`

### NextGenMUDApp/llm_npc_conversation.py

- **962** — `TODO: Integrate with combat system`
- **967** — `TODO: Integrate with movement system`
- **971** — `TODO: Integrate with inventory system`

### NextGenMUDApp/utility.py

- **315** — `TODO:M: make these handle containers`
- **178** — `NotImplementedError` for unsupported operator in `evaluate_condition()`

---

## documents/TODO.md (legacy)

- Finish frozen state
- Finish "state ok to act"
- Figure out for burn etc how to check damage first, then message if appropriate, then apply damage
- Finish converting skills to new code architecture

---

## Abstract interfaces

These modules use `raise NotImplementedError` in abstract base classes; concrete implementations exist elsewhere. No action unless adding a new implementation.

- `comprehensive_game_state_interface.py` — interface; implemented in `ComprehensiveGameState`
- `skills_interface.py` — interface; implemented in skill modules
- `nondb_models/character_interface.py` — interface; implemented in `Character`
- `nondb_models/room_interface.py`, `object_interface.py`, `actor_interface.py` — interfaces
- `core_actions_interface.py` — interface
- `llm_client.py` — only Gemini client implemented; other methods are stubs for other LLM backends
- `basic_types.py` — override in child class
- `command_handler.py` — `NotImplementedError` for unimplemented `ActorType` values (intentional)
