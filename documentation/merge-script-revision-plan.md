# Plan: Revise merge_mud_files.py to ZONES-Only Format

## Goal

Change `merge_mud_files.py` so that:

1. **Only ZONES is at top level** — no CHARACTERS or OBJECTS at the root.
2. **ROOMS, CHARACTERS, and OBJECTS live under each zone** — `ZONES.<zone_id>.ROOMS`, `ZONES.<zone_id>.CHARACTERS`, `ZONES.<zone_id>.OBJECTS`.
3. **Section names are capitalized** — ROOMS, CHARACTERS, OBJECTS (not `rooms`, `characters`, `objects`).

This matches the format already documented in the READMEs and what the game loader expects under the zone (with one caveat: see “Output key casing” below).

---

## Current State

### Merge script (`merge_mud_files.py`)

- **Revisions**: Accepts top-level `ZONES` and also top-level `CHARACTERS` and `OBJECTS`.
- **CHARACTERS/OBJECTS format**: List of `{ zone: "zone_id", characters: [...] }` or `{ zone: "zone_id", objects: [...] }`.
- **ZONES**: Under each zone it only explicitly merges `common_knowledge`, `variables`, `rooms` (lowercase), `quests`. The “merge any other zone-level fields” loop would merge `characters`/`objects` if present under the zone, but the script never *writes* per-zone characters/objects; it only merges top-level CHARACTERS/OBJECTS into `base["CHARACTERS"]` and `base["OBJECTS"]`.
- **Output**: Can contain top-level `ZONES`, `CHARACTERS`, and `OBJECTS`.

### Game loader (`comprehensive_game_state.py`)

- **Expects**: Single top-level key `ZONES`; under each zone it reads `zone_info['rooms']`, `zone_info['characters']`, `zone_info['objects']` (lowercase).
- **Rejects**: Top-level `CHARACTERS`, `OBJECTS`, `rooms`, `quests`, etc. (logs error and continues).

### World file (`world_data/gloomy_graveyard.yaml`)

- **Already ZONES-only**: Only `ZONES` at top level.
- Under zone: `rooms`, `characters`, `objects` (lowercase).

### Revision file (`revisions_graveyard_actions.yaml`)

- **Mixed**: Has `ZONES` (with quests and rooms), then top-level `CHARACTERS` and `OBJECTS` in the old format.

**Consequence**: If you merge that revision into the base today, the merged file gets top-level `CHARACTERS` and `OBJECTS`. The game loader would then reject that file. So the current merge script output format is already incompatible with the loader for any revision that adds CHARACTERS or OBJECTS.

---

## Implementation Plan

### 1. Normalize revision input (support both formats)

- **When loading a revision**: If it has top-level `CHARACTERS` or `OBJECTS`, “fold” them into `ZONES` before merging:
  - For each `{ zone: "zone_id", characters: [...] }` in `CHARACTERS`, set `ZONES[zone_id]["CHARACTERS"] = merge_with_existing(ZONES[zone_id].get("CHARACTERS"), list)` (and same for OBJECTS).
  - Then drop top-level `CHARACTERS` and `OBJECTS` from the revision dict so the rest of the pipeline only sees ZONES.
- **Canonical revision format**: ZONES only; under each zone, keys `ROOMS`, `CHARACTERS`, `OBJECTS` (capitalized). Accept lowercase `rooms`/`characters`/`objects` as aliases when reading.

This keeps existing revision files (with top-level CHARACTERS/OBJECTS) working.

### 2. Normalize base input (support both formats)

- **When loading the base file**: If it has top-level `CHARACTERS` or `OBJECTS`, fold them into the corresponding zone the same way (by `zone` → `ZONES[zone_id]["CHARACTERS"]` or `OBJECTS`). After normalization, the in-memory base has only `ZONES`, with per-zone ROOMS/CHARACTERS/OBJECTS (use one canonical key for storage, e.g. always `rooms`/`characters`/`objects` internally for merging).

### 3. Merge logic (ZONES only)

- **Remove** merging of top-level `CHARACTERS` and `OBJECTS` in `apply_single_revision()`.
- **Inside `merge_zones()`** (per zone):
  - **Rooms**: Merge `rev_zone["ROOMS"]` or `rev_zone["rooms"]` into `base_zone["rooms"]` (reuse existing `merge_rooms()`). Prefer capitalized key when reading from revision, fall back to lowercase.
  - **Characters**: Merge `rev_zone["CHARACTERS"]` or `rev_zone["characters"]` into `base_zone["characters"]` using the same ID-based list merge as today (`merge_character_or_object_list`). If the revision has a list of character dicts (no `zone` wrapper), merge that list directly.
  - **Objects**: Same idea for `rev_zone["OBJECTS"]` or `rev_zone["objects"]` into `base_zone["objects"]`.
- **Explicit zone keys**: In the “merge any other zone-level fields” loop, include `"CHARACTERS"`, `"OBJECTS"`, `"ROOMS"`, `"rooms"`, `"characters"`, `"objects"` in the exclusion list so they are only merged by the dedicated logic above (to avoid double-merge or wrong structure).

### 4. Output format

- **Only ZONES** at top level.
- Under each zone, write three sections. **Casing choice**:
  - **Option A (recommended for minimal game impact)**: Write **lowercase** `rooms`, `characters`, `objects` so existing game loader works unchanged. Docs already say “CHARACTERS, OBJECTS, ROOMS” as the *canonical names*; the script can accept both when reading but emit lowercase for compatibility.
  - **Option B**: Write **capitalized** `ROOMS`, `CHARACTERS`, `OBJECTS` and update the game loader to accept both (e.g. `zone_info.get("ROOMS") or zone_info.get("rooms")`). Then merged files are strictly as in the README.

Recommendation: **Option A** for the first revision (no loader change), with a short comment in the script and in the README that “canonical names in revision files are ROOMS/CHARACTERS/OBJECTS; merged output uses lowercase for game compatibility.” Option B can be a follow-up.

### 5. Key normalization helper

- Add a small helper, e.g. `_zone_section(zone_dict, *keys)`, that returns `zone_dict.get("ROOMS") or zone_dict.get("rooms")` (and similarly for CHARACTERS/characters, OBJECTS/objects). Use it when reading from base and revision so both casings work.

### 6. Preserve comments and order

- When folding top-level CHARACTERS/OBJECTS into ZONES, copy structure with the same copy/commented types used elsewhere (e.g. `copy_item`) so ruamel comment preservation still applies where possible. When writing, preserve key order: e.g. name, description, common_knowledge, variables, quests, ROOMS (or rooms), CHARACTERS (or characters), OBJECTS (or objects).

---

## Step-by-step code changes

1. **Add `normalize_revision_to_zones_only(revisions: dict) -> dict`**
   - If `CHARACTERS` in revisions: for each `{ zone: z, characters: L }`, set `ZONES[z]["CHARACTERS"] = L` (or merge into existing if multiple blocks for same zone). Remove `CHARACTERS` from revisions.
   - If `OBJECTS` in revisions: same for OBJECTS. Remove `OBJECTS` from revisions.
   - Return revisions (only ZONES at top level).

2. **Add `normalize_base_to_zones_only(base: dict) -> dict`**
   - Same folding for base: if base has top-level CHARACTERS/OBJECTS, fold into ZONES by zone id, then remove them.

3. **In `merge_zones()`**
   - For each zone, resolve revision sections with `_zone_section(rev_zone, "ROOMS", "rooms")` etc.
   - Merge rooms: `base_zone["rooms"] = merge_rooms(base_zone.get("rooms"), rev_rooms)` (rev_rooms from helper).
   - Merge characters: `base_zone["characters"] = merge_character_or_object_list(base_zone.get("characters"), rev_characters)` (rev_characters from helper; expect a list of dicts with `id`).
   - Merge objects: same for objects.
   - In “any other zone-level fields” loop, exclude: `"ROOMS","rooms","CHARACTERS","characters","OBJECTS","objects"` (and existing ones).

4. **In `apply_single_revision()`**
   - First call `revisions = normalize_revision_to_zones_only(revisions)`.
   - Remove the block that merges top-level `CHARACTERS` and `OBJECTS`.
   - Keep only ZONES merge.

5. **On load (start of merge_mud_files())**
   - After loading base: `base = normalize_base_to_zones_only(base)` so base is always ZONES-only in memory.

6. **On save**
   - Ensure output has only `ZONES`. Under each zone write `rooms`, `characters`, `objects` (Option A). Do not write any top-level CHARACTERS/OBJECTS.

7. **Docstring and comments**
   - Update module docstring and any inline comments to state that revision and base can use either format (top-level CHARACTERS/OBJECTS or per-zone ROOMS/CHARACTERS/OBJECTS), but output is always ZONES-only with per-zone rooms/characters/objects (lowercase for game compatibility).

---

## Adverse consequences and mitigations

| Issue | Impact | Mitigation |
|-------|--------|------------|
| **Existing revision files** (e.g. with top-level CHARACTERS/OBJECTS) | Could break if we only accepted the new format. | Normalize on read: fold top-level CHARACTERS/OBJECTS into ZONES by zone id so old revisions still work. |
| **Existing base files** with top-level CHARACTERS/OBJECTS | Some legacy base files might have that format. | Normalize base on read the same way; after load, base is ZONES-only in memory. |
| **Game loader expects lowercase** `rooms`/`characters`/`objects` | If we output ROOMS/CHARACTERS/OBJECTS, loader would not find them without a code change. | Option A: merge script outputs lowercase so no loader change. Option B: update loader to accept both casings. |
| **Multi-section revisions** (`# ===`) | Each section is applied in order; sections might mix old and new format. | Normalize each revision section before applying; no change in behavior. |
| **Comment preservation** | Folding STRUCTURE could alter key order or attach comments to wrong keys. | Use same copy_item/CommentedMap handling when building folded structure; prefer merging into existing zone key when both base and revision have it. |
| **New zone in revision** | If revision adds a zone that only has CHARACTERS (no ROOMS), that’s valid. | `merge_zones` already supports “zone_id not in result” → copy full rev_zone; ensure normalized revision has CHARACTERS/OBJECTS under that zone so they get copied. |

---

## Testing

1. **Unit tests**
   - Normalize: revision with top-level CHARACTERS/OBJECTS → after normalize, only ZONES, and each zone has CHARACTERS/OBJECTS (or characters/objects) filled.
   - Merge: revision with ZONES.gloomy_graveyard.CHARACTERS only → base zone ends up with merged characters.
   - Merge: revision with old-style top-level CHARACTERS → same result as above (after normalize).
   - Output: merged result has no top-level CHARACTERS/OBJECTS; each zone has rooms, characters, objects (or ROOMS/CHARACTERS/OBJECTS if Option B).

2. **Integration**
   - Run merge on `world_data/gloomy_graveyard.yaml` with `revisions_graveyard_actions.yaml`; confirm output is ZONES-only and loads in the game (e.g. `Initialize()` or a small load test).

3. **Regression**
   - If any tests currently expect top-level CHARACTERS/OBJECTS in the output, update them to expect ZONES-only and per-zone sections.

---

## Summary

- **Revise merge script** to: (1) accept only ZONES at top level in the *canonical* format, (2) accept legacy revision/base with top-level CHARACTERS/OBJECTS by normalizing into ZONES on read, (3) merge only ZONES (with per-zone ROOMS/CHARACTERS/OBJECTS), (4) write only ZONES with per-zone rooms/characters/objects (lowercase for Option A). This aligns the script with the README and the game loader, fixes the current incompatibility when revisions add CHARACTERS/OBJECTS, and avoids breaking existing revision or base files.
