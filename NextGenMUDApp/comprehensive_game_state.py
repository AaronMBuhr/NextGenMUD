from collections import defaultdict
import bisect
import copy
import fnmatch
import time
from .structured_logger import StructuredLogger
from django.conf import settings
import json
import os
import sys
from typing import List, Dict, Optional, Callable, Any, TYPE_CHECKING
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError
from .game_save_utils import save_game, load_game, list_saves, delete_save, create_player
from .nondb_models.actor_interface import ActorType, ActorSpawnData
from .nondb_models.actor_states import ActorState, CharacterStateStealthed
from .nondb_models.actors import Actor
from .nondb_models.character_interface import CharacterInterface, EquipLocation, \
    GamePermissionFlags, TemporaryCharacterFlags, PermanentCharacterFlags
from .nondb_models.character_interface import CharacterAttributes
from .nondb_models.characters import Character
from .nondb_models.objects import Object, ObjectFlags
from .nondb_models.room_interface import RoomInterface
from .nondb_models.rooms import Room
from .nondb_models.world import WorldDefinition, Zone
from .constants import Constants, CharacterClassRole
from .communication import Connection, CommTypes
from .comprehensive_game_state_interface import GameStateInterface, ScheduledEvent, EventType
from .config import Config, default_app_config
from .core_actions_interface import CoreActionsInterface
from .utility import article_plus_name
from .player_save_manager import player_save_manager
# from .consumers import MyWebsocketConsumerStateHandlerInterface
from .nondb_models.world import Zone
from .nondb_models.triggers import TriggerTimerTick, TriggerType


class LinkdeadCharacter:
    """Tracks a character that has disconnected but may reconnect."""
    def __init__(self, character: Character, disconnect_time: float):
        self.character = character
        self.disconnect_time = disconnect_time
        self.was_in_combat = character.fighting_whom is not None

class LiveGameStateContextManager:
    def __init__(self, **live_game_states):
        self.original_live_game_states = {}
        self.new_live_game_states = live_game_states

    def __enter__(self):
        # Store the original configurations and apply new ones
        for class_name, new_state in self.new_live_game_states.items():
            self.original_live_game_states[class_name] = class_name.live_game_state
            class_name.live_game_state = new_state

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore the original configurations
        for class_name, original_live_game_state in self.original_live_game_states.items():
            class_name.live_game_state = original_live_game_state


def find_yaml_files(directory):
    # print(f"------------------ {directory}")
    for root, dirs, files in os.walk(directory):
        # print("***************")
        # print(root,dirs,files)
        for file in files:
            # print(file)
            if fnmatch.fnmatch(file, '*.yaml') or fnmatch.fnmatch(file, '*.yml'):
                yield os.path.join(root, file)


class ComprehensiveGameState:

    def __init__(self, app_config: Config = default_app_config):
        self.app_config: Config = app_config
        self.world_definition: WorldDefinition = WorldDefinition()
        self.characters: List[Character] = []
        self.players : List[Character] = []
        self.connections : List[Connection] = []
        self.characters_fighting : List[Character] = []
        self.zones = {}
        self.quest_index = {}  # Maps variable_name -> list of Quest objects
        self.world_clock_tick: int = 0
        self.scheduled_events = defaultdict(list)
        self.xp_progression: List[int] = []
        self.linkdead_characters: Dict[str, LinkdeadCharacter] = {}  # name -> LinkdeadCharacter
        self.shutting_down: bool = False  # Flag to indicate server is stopping
        self.is_fully_loaded: bool = False  # True only after Initialize() completes; blocks gameplay until then
        # Debug section name -> player name who toggled it (for in-game output routing)
        self.active_debug: Dict[str, str] = {}
        # MyWebsocketConsumerStateHandlerInterface.game_state_handler = self

    def is_debug_enabled(self, name: str) -> bool:
        """Return True if the given debug section is currently turned on."""
        return name in self.active_debug

    def get_debug_activator_character(self, section: str):
        """Return the Character who turned on the given debug section, or None."""
        name = self.active_debug.get(section)
        if not name:
            return None
        return next((p for p in self.players if p.name == name), None)

    def _load_world_from_yaml(self, target_wd: WorldDefinition, load_quest_variables: bool = True) -> bool:
        """Load all YAML world files into target_wd. Returns True if at least one file was loaded and zones exist."""
        logger = StructuredLogger(__name__, prefix="_load_world_from_yaml()> ")
        file_found = False
        yaml_loader = YAML(typ='safe')
        for yaml_file in find_yaml_files(self.app_config.WORLD_DATA_DIR):
            logger.info(f"Loading world file {yaml_file}")
            try:
                with open(yaml_file, "r", encoding='utf-8') as yf:
                    yaml_data = yaml_loader.load(yf)
                    file_found = True
                if yaml_data is None or not isinstance(yaml_data, dict):
                    if yaml_data is None:
                        logger.warning(f"YAML file {yaml_file} is empty or contains only comments.")
                    else:
                        logger.error(f"YAML file {yaml_file} does not contain a valid dictionary structure.")
                    continue
                # Process ZONES
                if 'ZONES' in yaml_data and isinstance(yaml_data['ZONES'], dict):
                    for zone_id, zone_info in yaml_data['ZONES'].items():
                        if not isinstance(zone_info, dict):
                            continue

                        new_zone = Zone(zone_id)
                        new_zone.name = zone_info.get('name', f"Unnamed Zone {zone_id}")
                        new_zone.description = zone_info.get('description', "")

                        if 'common_knowledge' in zone_info and isinstance(zone_info['common_knowledge'], dict):
                            new_zone.common_knowledge = zone_info['common_knowledge']
                        if load_quest_variables and 'variables' in zone_info:
                            from .nondb_models.quests import QuestSchemaRegistry
                            registry = QuestSchemaRegistry.get_instance()
                            quest_vars = zone_info['variables']
                            if isinstance(quest_vars, dict):
                                registry.load_from_dict(quest_vars, zone_id=zone_id)

                        # 1. Load Quests & Variables
                        if 'quests' in zone_info and isinstance(zone_info['quests'], dict):
                            new_zone.load_quests(zone_info['quests'])

                        # 2. Load Rooms (canonical key ROOMS; accept lowercase 'rooms' for backward compatibility)
                        rooms_data = zone_info.get('ROOMS') or zone_info.get('rooms')
                        if isinstance(rooms_data, dict):
                            for room_id, room_info in rooms_data.items():
                                if not isinstance(room_info, dict):
                                    continue
                                new_room = Room(room_id, new_zone, create_reference=True)
                                new_room.from_yaml(new_zone, room_info)
                                new_zone.rooms[room_id] = new_room

                        # 3. Load Characters belonging to this zone (canonical CHARACTERS; accept 'characters')
                        characters_data = zone_info.get('CHARACTERS') or zone_info.get('characters')
                        if isinstance(characters_data, list):
                            for chardef in characters_data:
                                if not isinstance(chardef, dict) or 'id' not in chardef:
                                    continue
                                char_id = chardef['id']
                                ch = Character(char_id, zone_id, create_reference=False)
                                ch.from_yaml(chardef, zone_id)
                                target_wd.characters[f"{zone_id}.{ch.id}"] = ch

                        # 4. Load Objects belonging to this zone (canonical OBJECTS; accept 'objects')
                        objects_data = zone_info.get('OBJECTS') or zone_info.get('objects')
                        if isinstance(objects_data, list):
                            for objdef in objects_data:
                                if not isinstance(objdef, dict) or 'id' not in objdef:
                                    continue
                                obj_id = objdef['id']
                                obj = Object(obj_id, zone_id, create_reference=False)
                                obj.from_yaml(objdef, zone_id, self)
                                target_wd.objects[f"{zone_id}.{obj.id}"] = obj

                        # 5. Load Loot Tables belonging to this zone
                        loot_tables_data = zone_info.get('LOOT_TABLES') or zone_info.get('loot_tables')
                        if isinstance(loot_tables_data, list):
                            for lt in loot_tables_data:
                                if not isinstance(lt, dict) or 'id' not in lt:
                                    continue
                                table_id = lt['id']
                                items = lt.get('items', [])
                                target_wd.loot_tables[f"{zone_id}.{table_id}"] = items

                        target_wd.zones[zone_id] = new_zone

                # Reject top-level zone content: everything must be under ZONES.<zone_id>
                for bad_key in ("CHARACTERS", "OBJECTS", "rooms", "quests", "characters", "objects", "common_knowledge", "variables"):
                    if bad_key in yaml_data:
                        logger.error(
                            f"Invalid world file {yaml_file}: top-level '{bad_key}' is not allowed. "
                            f"All world data must be under ZONES.<zone_id>."
                        )
            except FileNotFoundError:
                logger.error(f"World file not found: {yaml_file}")
            except YAMLError as e:
                logger.error(f"Error parsing world YAML file: {yaml_file}: {e}")
            except Exception as e:
                logger.exception(f"Error loading world file {yaml_file}: {e}")
        return file_found and bool(target_wd.zones)

    def Initialize(self):
        logger = StructuredLogger(__name__, prefix="Initialize()> ")
        self.world_definition.zones = {}
        self.world_definition.characters = {}
        self.world_definition.objects = {}
        self.xp_progression = Constants.XP_PROGRESSION
        logger.info(f"Loading world files (*.yaml) from [{self.app_config.WORLD_DATA_DIR}]...")
        if not self._load_world_from_yaml(self.world_definition, load_quest_variables=True):
            raise Exception(f"No world files (*.yaml) found or no zones loaded in [{self.app_config.WORLD_DATA_DIR}].")
        logger.info(f"World files finished loading, from [{self.app_config.WORLD_DATA_DIR}].")

        logger.info("Preparing world...")
        self.zones = {}
        logger.info("Initializing zones...")
        for zone_id in list(self.world_definition.zones.keys()):
            self._build_zone_runtime(zone_id, spawn_npcs=True)

        logger.info("World prepared")
        # Print zone statistics
        print("\n=== WORLD LOADING STATISTICS ===")
        for zid, zdata in self.world_definition.zones.items():
            room_count = len(zdata.rooms)
            char_count = sum(1 for cid, cdef in self.world_definition.characters.items() if cdef.definition_zone_id == zid)
            obj_count = sum(1 for ok, od in self.world_definition.objects.items() if ok.startswith(f"{zid}."))
            print(f"Zone '{zid}': {room_count} room definitions, {char_count} character definitions, {obj_count} object definitions")
        print("===============================\n")

        self.build_quest_index()
        self.is_fully_loaded = True
        logger.info("World fully loaded; game ready for connections.")

    def _build_zone_runtime(self, zone_id: str, spawn_npcs: bool = True):
        """Build or rebuild runtime state for one zone from world_definition. Creates room refs, wires spawn_data, enables triggers; optionally spawns NPCs."""
        logger = StructuredLogger(__name__, prefix="_build_zone_runtime()> ")
        if zone_id not in self.world_definition.zones:
            raise Exception(f"Zone '{zone_id}' not in world_definition.")
        self.zones[zone_id] = copy.deepcopy(self.world_definition.zones[zone_id])
        zone_data = self.zones[zone_id]
        npc_count = 0
        for room_id, room_data in zone_data.rooms.items():
            room_data.create_reference()
            logger.debug3("init spawndata")
            for spawndata in room_data.spawn_data:
                spawndata.owner = room_data
                if spawndata.actor_type == ActorType.CHARACTER and spawn_npcs:
                    character_def = self.world_definition.find_character_definition(spawndata.id)
                    if not character_def:
                        logger.warning(f"Character definition for {spawndata.id} not found.")
                        raise Exception(f"Character definition for {spawndata.id} not found.")
                    for i in range(spawndata.desired_quantity):
                        if len(spawndata.spawned) >= spawndata.desired_quantity:
                            logger.debug3(f"Spawn cap already met for {spawndata.id} in room {spawndata.owner.rid}, skipping")
                            break
                        new_character = Character.create_from_definition(character_def, self)
                        new_character.spawned_from = spawndata
                        self.characters.append(new_character)
                        spawndata.owner.add_character(new_character)
                        spawndata.spawned.append(new_character)
                        npc_count += 1
                        logger.debug3(f"new_character: {new_character} added to room {new_character.location_room.rid}")
                elif spawndata.actor_type == ActorType.OBJECT:
                    object_def = self.world_definition.find_object_definition(spawndata.id)
                    if not object_def:
                        logger.warning(f"Object definition for {spawndata.id} not found.")
                        continue
                    for i in range(spawndata.desired_quantity):
                        new_obj = Object.create_from_definition(object_def)
                        new_obj.zone = zone_data
                        room_data.add_object(new_obj)
                        self._populate_container_contents(new_obj, zone_id)
                        spawndata.spawned.append(new_obj)
            for trig_type in room_data.triggers_by_type:
                for trig in room_data.triggers_by_type[trig_type]:
                    logger.debug3("enabling trigger")
                    trig.enable()
        logger.info(f"Zone '{zone_id}' built: {len(zone_data.rooms)} rooms" + (f", {npc_count} NPCs spawned" if spawn_npcs else " (no NPC spawn)") + ".")

    def _populate_container_contents(self, container, zone_id: str):
        """Instantiate objects from a container's initial_contents_ids (object def ids; each can have own contents)."""
        for content_id in getattr(container, 'initial_contents_ids', []):
            resolved_id = content_id if "." in content_id else f"{zone_id}.{content_id}"
            obj_def = self.world_definition.find_object_definition(resolved_id)
            if not obj_def:
                logger = StructuredLogger(__name__, prefix="_populate_container_contents()> ")
                logger.warning(f"Object definition for {resolved_id} not found (contents of {getattr(container, 'id', container)}).")
                continue
            child = Object.create_from_definition(obj_def)
            child.zone = getattr(container, 'zone', None)
            container.add_object(child)
            self._populate_container_contents(child, child.definition_zone_id)

    def build_quest_index(self):
        """
        Scans all quests in all zones and builds a hash table mapping
        variable names to the quests that check them.
        """
        self.quest_index = {}

        for zone in self.zones.values():
            if not getattr(zone, 'quests', None):
                continue

            for quest in zone.quests.values():
                vars_of_interest = set()
                for stage in quest.stages:
                    if not stage.conditions:
                        continue
                    for cond in stage.conditions:
                        var_name = cond.variable
                        vars_of_interest.add(var_name)
                        # Also index zone-qualified name so player perm_variables (e.g. zone.quest.var) match
                        qualified = f"{quest.zone_id}.{var_name}"
                        vars_of_interest.add(qualified)

                for var_name in vars_of_interest:
                    if var_name not in self.quest_index:
                        self.quest_index[var_name] = []
                    if quest not in self.quest_index[var_name]:
                        self.quest_index[var_name].append(quest)

        print(f"[GameState] Quest index built. Indexed {len(self.quest_index)} variables.")

    def _teardown_zone_runtime(self, zone_id: str, full: bool = True):
        """Stop combat, purge scheduled events (and optionally dereference NPCs/objects), dereference rooms. full=True: purge all zone actor events and remove NPCs/objects; full=False: purge only room-level events."""
        logger = StructuredLogger(__name__, prefix="_teardown_zone_runtime()> ")
        zone = self.zones[zone_id]
        zone_rooms = set(zone.rooms.values())
        zone_actors = set(zone_rooms)
        if full:
            for room in zone_rooms:
                zone_actors.update(room.characters)
                zone_actors.update(room.contents)
        # Stop combat for anyone in zone rooms
        combat_stopped = 0
        for room in zone_rooms:
            for char in room.characters[:]:
                if getattr(char, 'fighting_whom', None):
                    char.fighting_whom = None
                    if char in self.characters_fighting:
                        self.characters_fighting.remove(char)
                    combat_stopped += 1
        if combat_stopped:
            logger.info(f"Stopped combat for {combat_stopped} character(s) in zone '{zone_id}'.")
        # Purge scheduled events
        actors_to_purge = zone_actors if full else zone_rooms
        events_removed = 0
        for tick in list(self.scheduled_events.keys()):
            for event in self.scheduled_events[tick][:]:
                if (event.subject in actors_to_purge or
                        (event.attach_to_actor is not None and event.attach_to_actor in actors_to_purge)):
                    self.remove_scheduled_event(event)
                    events_removed += 1
        # Disable timer triggers so they remove themselves from TriggerTimerTick.timer_tick_triggers_
        for actor in (zone_actors if full else zone_rooms):
            for trig in getattr(actor, 'triggers_by_type', {}).get(TriggerType.TIMER_TICK, []):
                if hasattr(trig, 'disable'):
                    trig.disable()
        # If full: remove and dereference NPCs and objects
        npcs_removed = 0
        objects_derefed = 0
        if full:
            for room in zone_rooms:
                for char in room.characters[:]:
                    if char in self.players:
                        continue
                    room.remove_character(char)
                    if char in self.characters:
                        self.characters.remove(char)
                    for obj in list(getattr(char, 'contents', [])):
                        char.remove_object(obj)
                        if obj.reference_number:
                            Actor.dereference_(obj.reference_number)
                        objects_derefed += 1
                    for loc, obj in list(getattr(char, 'equipped', {}).items()):
                        if obj is not None:
                            try:
                                char.unequip_location(loc)
                            except Exception:
                                pass
                            if obj and obj.reference_number:
                                Actor.dereference_(obj.reference_number)
                            objects_derefed += 1
                    if char.reference_number:
                        Actor.dereference_(char.reference_number)
                    npcs_removed += 1
                for obj in room.contents[:]:
                    room.remove_object(obj)
                    if obj.reference_number:
                        Actor.dereference_(obj.reference_number)
                    objects_derefed += 1
        # Dereference rooms
        rooms_derefed = 0
        for room in zone_rooms:
            if room.reference_number:
                Actor.dereference_(room.reference_number)
            rooms_derefed += 1
        logger.info(f"Teardown zone '{zone_id}': {rooms_derefed} rooms dereferenced" +
                    (f", {npcs_removed} NPCs removed, {objects_derefed} objects dereferenced" if full else "") +
                    f", {events_removed} scheduled events purged.")

    def _purge_actor_events(self, actor: Actor):
        """Remove all scheduled events for this actor, for any of the actor's states, and disable their timer triggers."""
        actor_states = getattr(actor, 'states', [])[:]
        for tick in list(self.scheduled_events.keys()):
            for event in self.scheduled_events[tick][:]:
                if event.subject is actor or event.attach_to_actor is actor:
                    self.remove_scheduled_event(event)
                elif event.subject in actor_states:
                    self.remove_scheduled_event(event)
        for trig in getattr(actor, 'triggers_by_type', {}).get(TriggerType.TIMER_TICK, []):
            if hasattr(trig, 'disable'):
                trig.disable()

    def _reload_zone_definitions(self, zone_id: str):
        """Re-read all YAML from disk and replace one zone's definitions in world_definition. Returns (success, room_ids_set or error_message)."""
        logger = StructuredLogger(__name__, prefix="_reload_zone_definitions()> ")
        temp_wd = WorldDefinition()
        temp_wd.zones = {}
        temp_wd.characters = {}
        temp_wd.objects = {}
        if not self._load_world_from_yaml(temp_wd, load_quest_variables=False):
            return (False, "No world files or zones loaded from YAML.")
        if zone_id not in temp_wd.zones:
            return (False, f"Zone '{zone_id}' not found in YAML.")
        new_zone = temp_wd.zones[zone_id]
        room_ids = set(new_zone.rooms.keys())
        # Replace zone template
        self.world_definition.zones[zone_id] = new_zone
        # Replace character definitions for this zone
        to_remove = [k for k, c in self.world_definition.characters.items() if c.definition_zone_id == zone_id]
        for k in to_remove:
            del self.world_definition.characters[k]
        for k, c in temp_wd.characters.items():
            if c.definition_zone_id == zone_id:
                self.world_definition.characters[k] = c
        # Replace object definitions for this zone
        to_remove = [k for k in self.world_definition.objects if k.startswith(f"{zone_id}.")]
        for k in to_remove:
            del self.world_definition.objects[k]
        for k, o in temp_wd.objects.items():
            if k.startswith(f"{zone_id}."):
                self.world_definition.objects[k] = o
        logger.info(f"Zone '{zone_id}' definitions reloaded from YAML: {len(room_ids)} rooms.")
        return (True, room_ids)

    def _get_start_room(self) -> Optional[Room]:
        """Return the room for DEFAULT_START_LOCATION, or first room in first zone if not found."""
        start_location = Constants.DEFAULT_START_LOCATION
        if "." in start_location:
            zone_id, room_id = start_location.split(".", 1)
        else:
            zone_id = start_location
            room_id = None
        start_zone = self.get_zone_by_id(zone_id)
        if not start_zone:
            return None
        start_room = start_zone.rooms.get(room_id) if room_id else None
        if not start_room and start_zone.rooms:
            start_room = start_zone.rooms[list(start_zone.rooms.keys())[0]]
        return start_room

    async def reload_zone(self, zone_id: str) -> str:
        """Full zone reload: re-read YAML, tear down zone, rebuild, restore players to rooms or start."""
        logger = StructuredLogger(__name__, prefix="reload_zone()> ")
        if zone_id not in self.zones:
            return f"Zone '{zone_id}' not found."
        logger.info(f"Reloading zone '{zone_id}'...")
        ok, result = self._reload_zone_definitions(zone_id)
        if not ok:
            logger.warning(f"Zone reload aborted: {result}")
            return f"Reload aborted: {result}"
        room_ids = result
        zone = self.zones[zone_id]
        player_locations = []
        for room in zone.rooms.values():
            for char in list(room.characters):
                is_player = char in self.players
                is_linkdead = bool(self.linkdead_characters and any(getattr(lc, 'character', None) == char for lc in self.linkdead_characters.values()))
                if is_player or is_linkdead:
                    player_locations.append((char, room.id))
                    room.remove_character(char)
        logger.info(f"Snapshotted {len(player_locations)} player(s) in zone '{zone_id}'.")
        self._teardown_zone_runtime(zone_id, full=True)
        del self.zones[zone_id]
        self._build_zone_runtime(zone_id, spawn_npcs=True)
        zone = self.zones[zone_id]
        start_room = self._get_start_room()
        core = CoreActionsInterface.get_instance()
        restored = 0
        moved_start = 0
        for player, old_room_id in player_locations:
            if old_room_id in zone.rooms:
                new_room = zone.rooms[old_room_id]
                new_room.add_character(player)
                restored += 1
                logger.info(f"Restored {player.name} to room {old_room_id}.")
            else:
                if start_room:
                    await core.arrive_room(player, start_room)
                    moved_start += 1
                    logger.info(f"Moved {player.name} to start room (room {old_room_id} no longer exists).")
            if player in self.players:
                try:
                    await player.echo(CommTypes.DYNAMIC, "The world around you shimmers and reforms...", game_state=self)
                except Exception:
                    pass
        summary = f"Zone '{zone_id}' reloaded: {len(zone.rooms)} rooms, {len(player_locations)} player(s) processed ({restored} restored, {moved_start} to start)."
        logger.info(summary)
        self.build_quest_index()
        return summary

    async def reload_rooms(self, zone_id: str) -> str:
        """Rooms-only reload: re-read YAML, rebuild room defs, keep occupants; discard NPCs/objects in vanished rooms."""
        logger = StructuredLogger(__name__, prefix="reload_rooms()> ")
        if zone_id not in self.zones:
            return f"Zone '{zone_id}' not found."
        logger.info(f"Reloading rooms for zone '{zone_id}'...")
        ok, result = self._reload_zone_definitions(zone_id)
        if not ok:
            logger.warning(f"Rooms reload aborted: {result}")
            return f"Reload aborted: {result}"
        room_ids = result
        zone = self.zones[zone_id]
        occupants_by_room = {}
        for room in zone.rooms.values():
            occupants_by_room[room.id] = (list(room.characters), list(room.contents))
        for room_id, (chars, objs) in occupants_by_room.items():
            room = zone.rooms[room_id]
            for c in chars:
                room.remove_character(c)
            for o in objs:
                room.remove_object(o)
        self._teardown_zone_runtime(zone_id, full=False)
        del self.zones[zone_id]
        self._build_zone_runtime(zone_id, spawn_npcs=False)
        zone = self.zones[zone_id]
        start_room = self._get_start_room()
        core = CoreActionsInterface.get_instance()
        restored_rooms = 0
        vanished_players = 0
        vanished_npcs = 0
        vanished_objs = 0
        for room_id, (chars, objs) in occupants_by_room.items():
            if room_id not in zone.rooms:
                for c in chars:
                    is_player = c in self.players
                    is_linkdead = bool(self.linkdead_characters and any(getattr(lc, 'character', None) == c for lc in self.linkdead_characters.values()))
                    if is_player or is_linkdead:
                        if start_room:
                            await core.arrive_room(c, start_room)
                        vanished_players += 1
                        logger.info(f"Moved {c.name} to start room (room {room_id} vanished).")
                    else:
                        if c in self.characters:
                            self.characters.remove(c)
                        self._purge_actor_events(c)
                        if c.reference_number:
                            Actor.dereference_(c.reference_number)
                        vanished_npcs += 1
                for o in objs:
                    self._purge_actor_events(o)
                    if o.reference_number:
                        Actor.dereference_(o.reference_number)
                    vanished_objs += 1
            else:
                new_room = zone.rooms[room_id]
                for c in chars:
                    new_room.add_character(c)
                for o in objs:
                    new_room.add_object(o)
                restored_rooms += 1
                logger.info(f"Restored {len(chars)} character(s), {len(objs)} object(s) to room {room_id}.")
        summary = f"Rooms for zone '{zone_id}' reloaded: {restored_rooms} rooms with occupants restored, {vanished_players} player(s) moved to start, {vanished_npcs} NPC(s) and {vanished_objs} object(s) discarded from vanished rooms."
        logger.info(summary)
        self.build_quest_index()
        return summary

    @staticmethod
    def _normalize_reference_key(ref_str: str) -> str:
        """Identity pass-through (UUIDs need no normalization). Kept for call-site compatibility."""
        return ref_str

    def find_target_characters(self, actor: Actor, target_name: str, first_match: int = 1, last_match: int = 0,
                                search_scope: str = None, search_zone: bool = False, search_world: bool = False,
                                exclude_initiator: bool = True) -> List[Character]:
        """
        Find characters matching target_name. Returns a list.
        first_match, last_match: 1-based indices; last_match < 1 means return all from first_match on.
        E.g. guard#4 → first=4, last=4 (single item at index 4). Use first_match=1, last_match=0 for all.
        search_scope: 'room' | 'subzone' | 'zone' | 'world' to limit search; None = use search_zone/search_world.
        Stops collecting once last_match items are in the list (when last_match >= 1).
        """
        logger = StructuredLogger(__name__, prefix="find_target_characters()> ")
        if not target_name:
            return []
        if target_name[0] == Constants.REFERENCE_SYMBOL:
            ref_key = self._normalize_reference_key(target_name[1:])
            resolved = Actor.get_reference(ref_key)
            if resolved is not None and isinstance(resolved, Character):
                return [resolved]
            return []
        if target_name.lower() == 'me' or target_name.lower() == 'self':
            return [actor] if isinstance(actor, Character) else []

        start_room = None
        if isinstance(actor, Character):
            start_room = actor.location_room
        elif isinstance(actor, Room):
            start_room = actor
        elif isinstance(actor, Object) and actor.location_room:
            start_room = actor.location_room
        if not start_room:
            return []

        if search_scope == 'zone':
            search_zone = True
        if search_scope == 'world' or search_world:
            search_zone = True
            search_world = True

        first_match = max(1, first_match)
        if '#' in target_name:
            parts = target_name.split('#')
            target_name = parts[0]
            try:
                first_match = int(parts[1])
                last_match = first_match
            except (ValueError, IndexError):
                pass

        candidates: List[Character] = []
        target_lower = target_name.lower()
        stop_at = last_match if last_match >= 1 else None

        def add_candidates_from_room(act, room):
            for char in room.get_characters():
                if exclude_initiator and char == act:
                    continue
                if char.matches_keyword(target_lower) and self.can_see(char, act):
                    candidates.append(char)
                    if stop_at is not None and len(candidates) >= stop_at:
                        return True
            return False

        def rooms_for_scope():
            yield start_room
            if search_scope == 'room':
                return
            if not isinstance(start_room, Room) or not start_room.zone:
                return
            if search_scope == 'subzone':
                sub_id = getattr(start_room, 'subzone_id', None)
                for room in start_room.zone.rooms.values():
                    if room is not start_room and getattr(room, 'subzone_id', None) == sub_id:
                        yield room
                return
            if search_zone or search_scope == 'zone':
                for room in start_room.zone.rooms.values():
                    if room is not start_room:
                        yield room
            if search_world or search_scope == 'world':
                for zone in self.zones.values():
                    for room in zone.rooms.values():
                        if zone is not start_room.zone or room is not start_room:
                            yield room

        for room in rooms_for_scope():
            if add_candidates_from_room(actor, room):
                break
            if stop_at is not None and len(candidates) >= stop_at:
                break

        logger.debug3(f"candidates: {len(candidates)}")
        if last_match >= 1:
            return candidates[first_match - 1:last_match] if first_match <= len(candidates) else []
        return candidates[first_match - 1:] if first_match <= len(candidates) else []

    def find_target_character(self, actor: Actor, target_name: str, search_zone=False, search_world=False, exclude_initiator=True) -> Optional[Character]:
        """Return the first matching character, or None. Wrapper around find_target_characters(..., first_match=1, last_match=1)."""
        lst = self.find_target_characters(actor, target_name, first_match=1, last_match=1, search_zone=search_zone, search_world=search_world, exclude_initiator=exclude_initiator)
        return lst[0] if lst else None


    def find_all_characters(self, actor: Actor, target_name: str) -> str:
        # TODO:L: should we limit these to can-see?
        # Determine the starting point
        start_room = None
        if isinstance(actor, Character):
            start_room = actor.location_room
        elif isinstance(actor, Room):
            start_room = actor
        elif isinstance(actor, Object) and actor.location_room:
            start_room = actor.location_room

        if not start_room:
            return ""

        matching_characters = []
        target_lower = target_name.lower()

        # Helper function to add matching characters from a room
        def add_matching_characters_from_room(room):
            for char in room.characters_:
                if char.matches_keyword(target_lower):
                    matching_characters.append(f"{article_plus_name(char.article_, char.name, cap=True)} in {room.name}")

        # Search in the current room
        add_matching_characters_from_room(start_room)

        # Search in the current zone
        if isinstance(start_room, Room) and start_room.zone:
            for room in start_room.zone.rooms.values():
                add_matching_characters_from_room(room)

        # Search across all zones
        for zone in self.zones.values():
            for room in zone.rooms.values():
                add_matching_characters_from_room(room)

        # Format and return the results
        return "\n".join(matching_characters)


    def find_target_room(self, actor: Actor, target_name: str, start_zone: Zone) -> 'Room':
        if not target_name:
            return None
        if target_name[0] == Constants.REFERENCE_SYMBOL:
            ref_key = self._normalize_reference_key(target_name[1:])
            resolved = Actor.get_reference(ref_key)
            if resolved is not None and isinstance(resolved, Room):
                return resolved
            return None
        if target_name.lower() == 'me' or target_name.lower() == 'self' or target_name.lower() == 'here':
            return actor
        
        # Handle zone.room_id format (e.g., "gloomy_graveyard.forest_road_s")
        # If zone is specified, ONLY search in that zone
        if "." in target_name:
            zone_id, room_id = target_name.split(".", 1)
            if zone_id in self.zones:
                zone = self.zones[zone_id]
                # Exact match first
                if room_id in zone.rooms:
                    return zone.rooms[room_id]
                # Try partial match on room_id within the specified zone only
                for rid, room in zone.rooms.items():
                    if rid.startswith(room_id):
                        return room
            # Zone specified but not found, or room not in that zone - return None
            return None
        
        # No zone specified - search in start_zone first (if actor is in a room)
        if start_zone is not None:
            for room in start_zone.rooms.values():
                if room.name.startswith(target_name) or room.id.startswith(target_name):
                    return room
        
        # Then search all zones
        for zone in self.zones.values():
            for room in zone.rooms.values():
                if room.id.startswith(target_name):
                    return room
                for pieces in room.name.split(' '):
                    if pieces.startswith(target_name):
                        return room
        return None
    

    def find_target_objects(self, target_name: str, actor: Actor = None, equipped: Dict[EquipLocation, Object] = None,
                            start_room: 'Room' = None, start_zone: Zone = None, first_match: int = 1, last_match: int = 0,
                            search_scope: str = None, search_world: bool = False,
                            search_list: list = None) -> List[Object]:
        """
        Find objects matching target_name. Returns a list.
        first_match, last_match: 1-based; last_match < 1 means return all from first_match on.
        search_scope: 'room' | 'subzone' | 'zone' | 'world' to limit search; None = use start_zone/search_world.
        Stops collecting once last_match items are in the list (when last_match >= 1).
        """
        logger = StructuredLogger(__name__, prefix="find_target_objects()> ")
        if not target_name:
            return []
        if target_name[0] == Constants.REFERENCE_SYMBOL:
            ref_key = self._normalize_reference_key(target_name[1:])
            resolved = Actor.get_reference(ref_key)
            if resolved is not None and isinstance(resolved, Object):
                return [resolved]
            return []
        if target_name.lower() in ('me', 'self'):
            return [actor] if isinstance(actor, Object) else []

        if start_room is None and actor is not None:
            start_room = getattr(actor, 'location_room', None)

        first_match = max(1, first_match)
        if '#' in target_name:
            parts = target_name.split('#')
            target_name = parts[0]
            try:
                first_match = int(parts[1])
                last_match = first_match
            except (ValueError, IndexError):
                pass

        target_lower = target_name.lower()
        candidates: List[Object] = []
        stop_at = last_match if last_match >= 1 else None

        def maybe_append(obj):
            if obj and obj.matches_keyword(target_lower):
                candidates.append(obj)
                return stop_at is not None and len(candidates) >= stop_at
            return False

        if search_list is not None:
            for obj in search_list:
                if maybe_append(obj):
                    return candidates[first_match - 1:last_match] if first_match <= len(candidates) else []
        if equipped:
            for obj in equipped.values():
                if maybe_append(obj):
                    return candidates[first_match - 1:last_match] if first_match <= len(candidates) else []
        if actor and hasattr(actor, 'contents'):
            for obj in actor.contents:
                if maybe_append(obj):
                    return candidates[first_match - 1:last_match] if first_match <= len(candidates) else []

        if not start_room:
            return candidates[first_match - 1:] if last_match < 1 and first_match <= len(candidates) else (candidates[first_match - 1:last_match] if first_match <= len(candidates) else [])

        if stop_at is not None and len(candidates) >= stop_at:
            logger.debug3(f"candidates: {len(candidates)} (early exit before rooms)")
            return candidates[first_match - 1:last_match] if first_match <= len(candidates) else []

        use_zone = start_zone if search_scope is None else None
        use_world = search_world if search_scope is None else False
        if search_scope == 'room':
            use_zone = None
            use_world = False
        elif search_scope == 'subzone':
            use_zone = None
            use_world = False
        elif search_scope == 'zone':
            use_zone = start_room.zone if start_room and getattr(start_room, 'zone', None) else start_zone
            use_world = False
        elif search_scope == 'world':
            use_zone = start_room.zone if start_room and getattr(start_room, 'zone', None) else start_zone
            use_world = True

        def rooms_for_scope():
            yield start_room
            if search_scope == 'room':
                return
            zone = getattr(start_room, 'zone', None) if start_room else None
            if search_scope == 'subzone' and zone:
                sub_id = getattr(start_room, 'subzone_id', None)
                for room in zone.rooms.values():
                    if room is not start_room and getattr(room, 'subzone_id', None) == sub_id:
                        yield room
                return
            if use_zone:
                for room in use_zone.rooms.values():
                    if room is not start_room:
                        yield room
            if use_world:
                for z in self.zones.values():
                    for room in z.rooms.values():
                        if z is not zone or room is not start_room:
                            yield room

        for room in rooms_for_scope():
            for obj in room.contents:
                if maybe_append(obj):
                    logger.debug3(f"candidates: {len(candidates)}")
                    return candidates[first_match - 1:last_match] if first_match <= len(candidates) else []
        logger.debug3(f"candidates: {len(candidates)}")
        if last_match >= 1:
            return candidates[first_match - 1:last_match] if first_match <= len(candidates) else []
        return candidates[first_match - 1:] if first_match <= len(candidates) else []

    def find_target_object(self, target_name: str, actor: Actor = None, equipped: Dict[EquipLocation, Object] = None,
                           start_room: 'Room' = None, start_zone: Zone = None, search_world=False,
                           search_list: list = None) -> Optional[Object]:
        """Return the first matching object, or None. Wrapper around find_target_objects(..., first_match=1, last_match=1)."""
        lst = self.find_target_objects(target_name, actor=actor, equipped=equipped, start_room=start_room, start_zone=start_zone, first_match=1, last_match=1, search_world=search_world, search_list=search_list)
        return lst[0] if lst else None

    def find_target_objects_with_parent(self, target_name: str, actor: Actor = None,
                                         start_room: 'Room' = None,
                                         first_match: int = 1, last_match: int = 0) -> List[tuple]:
        """
        Find objects by keyword in actor inventory and/or room, including inside containers.
        Returns list of (object, parent). last_match < 1 means return all from first_match on.
        """
        logger = StructuredLogger(__name__, prefix="find_target_objects_with_parent()> ")
        if not target_name:
            return []
        if target_name[0] == Constants.REFERENCE_SYMBOL:
            ref_key = self._normalize_reference_key(target_name[1:])
            resolved = Actor.get_reference(ref_key)
            if resolved is not None and isinstance(resolved, Object):
                parent = getattr(resolved, 'in_actor', None)
                return [(resolved, parent)]
            return []
        if target_name.lower() in ('me', 'self'):
            return [(actor, None)] if isinstance(actor, Object) else []
        first_match = max(1, first_match)
        if '#' in target_name:
            parts = target_name.split('#')
            target_name = parts[0]
            try:
                first_match = int(parts[1])
                last_match = first_match
            except (ValueError, IndexError):
                pass
        target_lower = target_name.lower()
        candidates: List[tuple] = []
        stop_at = last_match if last_match >= 1 else None

        def collect_with_parent(container, parent_actor):
            if not hasattr(container, 'contents'):
                return False
            for obj in container.contents:
                if obj.matches_keyword(target_lower):
                    candidates.append((obj, parent_actor))
                    if stop_at is not None and len(candidates) >= stop_at:
                        return True
                if collect_with_parent(obj, obj):
                    return True
            return False

        if actor and hasattr(actor, 'contents'):
            if collect_with_parent(actor, actor):
                logger.debug3(f"candidates: {len(candidates)} (early exit after actor)")
                if last_match >= 1:
                    return candidates[first_match - 1:last_match] if first_match <= len(candidates) else []
                return candidates[first_match - 1:] if first_match <= len(candidates) else []
        if (stop_at is None or len(candidates) < stop_at) and start_room and hasattr(start_room, 'contents'):
            collect_with_parent(start_room, start_room)

        logger.debug3(f"candidates: {len(candidates)}")
        if last_match >= 1:
            return candidates[first_match - 1:last_match] if first_match <= len(candidates) else []
        return candidates[first_match - 1:] if first_match <= len(candidates) else []

    def find_target_object_with_parent(self, target_name: str, actor: Actor = None,
                                       start_room: 'Room' = None,
                                       target_number: int = 1) -> tuple:
        """Return (object, parent) for the first match, or (None, None). Wrapper around find_target_objects_with_parent(..., first_match=target_number, last_match=target_number)."""
        lst = self.find_target_objects_with_parent(target_name, actor=actor, start_room=start_room, first_match=max(1, target_number), last_match=max(1, target_number))
        return lst[0] if lst else (None, None)

    
    async def start_connection(self, consumer: 'MyWebsocketConsumer'):
        """Legacy method - now handled by login flow in consumers.py"""
        logger = StructuredLogger(__name__, prefix="startConnection()> ")
        logger.debug("init new connection - waiting for login")
        # Login is now handled in consumers.py


    async def complete_login(self, consumer: 'MyWebsocketConsumer', character_name: str, is_new: bool = False, selected_class: str = None):
        """
        Complete the login process after successful authentication.
        
        Args:
            consumer: The websocket consumer
            character_name: Name of the character logging in
            is_new: Whether this is a newly created character
            selected_class: The class selected by the player (for new characters)
        """
        logger = StructuredLogger(__name__, prefix="complete_login()> ")
        logger.info(f"Completing login for {character_name} (is_new={is_new}, class={selected_class})")
        
        # Create connection object
        new_connection = Connection(consumer)
        consumer.connection_obj = new_connection
        self.connections.append(new_connection)
        
        # Check if this character is linkdead (reconnecting)
        if character_name.lower() in self.linkdead_characters:
            await self._handle_reconnect(new_connection, character_name)
            return
        
        # Load or create the character
        if is_new:
            await self._create_new_character(new_connection, character_name, selected_class)
        else:
            await self._load_existing_character(new_connection, character_name)
    
    async def _handle_reconnect(self, connection: Connection, character_name: str):
        """Handle a player reconnecting to a linkdead character."""
        logger = StructuredLogger(__name__, prefix="_handle_reconnect()> ")
        logger.info(f"Player reconnecting to linkdead character: {character_name}")
        
        linkdead = self.linkdead_characters.pop(character_name.lower())
        character = linkdead.character
        
        # Reconnect the character
        character.connection = connection
        connection.character = character
        
        # Check if character is dead - if so, respawn them at start room
        if character.is_dead():
            logger.info(f"Character {character_name} is dead on reconnect - respawning at start room")
            await CoreActionsInterface.get_instance()._respawn_player(character)
            return
        
        await connection.send(CommTypes.DYNAMIC, "You reconnect to your character.")
        
        # Notify the room
        if character.location_room:
            msg = f"{character.art_name_cap} has reconnected."
            await character.location_room.echo(CommTypes.DYNAMIC, msg, exceptions=[character], game_state=self)
            
            # Show the room
            await CoreActionsInterface.get_instance().do_look_room(character, character.location_room)
        
        logger.info(f"Player {character_name} reconnected successfully")
    
    async def _create_new_character(self, connection: Connection, character_name: str, selected_class: str = None):
        """Create a new character from class template."""
        from .nondb_models.character_interface import CharacterAttributes
        from .nondb_models.attacks_and_damage import AttackData, PotentialDamage, DamageType, DamageMultipliers
        from .utility import get_dice_parts, roll_dice
        
        logger = StructuredLogger(__name__, prefix="_create_new_character()> ")
        
        # Get selected class from save file if not provided
        if not selected_class:
            selected_class = player_save_manager.get_selected_class(character_name) or 'fighter'
        
        logger.debug(f"Creating new character: {character_name} as {selected_class}")
        
        # Get class template from config
        class_template = Constants.CHARACTER_CLASS_TEMPLATES.get(selected_class.lower())
        if not class_template:
            logger.warning(f"Class template for '{selected_class}' not found, using fighter")
            class_template = Constants.CHARACTER_CLASS_TEMPLATES.get('fighter', {})
        
        # Create a new character directly (not from definition)
        new_player = Character(f"player_{character_name}", "system", name=character_name)
        new_player.article = ""
        new_player.pronoun_subject = "they"
        new_player.pronoun_object = "them"
        new_player.pronoun_possessive = "their"
        
        # Set up class
        role = CharacterClassRole.from_field_name(selected_class.upper())
        new_player.class_priority = [role]
        new_player.levels_by_role = {role: 1}
        new_player.skill_levels_by_role = {role: {}}
        
        # Apply attributes - use player-allocated stats if available, otherwise use template
        allocated_stats = player_save_manager.get_allocated_stats(character_name)
        if allocated_stats:
            logger.debug(f"Using player-allocated stats: {allocated_stats}")
            new_player.attributes = {
                CharacterAttributes.STRENGTH: allocated_stats.get('STRENGTH', 10),
                CharacterAttributes.DEXTERITY: allocated_stats.get('DEXTERITY', 10),
                CharacterAttributes.CONSTITUTION: allocated_stats.get('CONSTITUTION', 10),
                CharacterAttributes.INTELLIGENCE: allocated_stats.get('INTELLIGENCE', 10),
                CharacterAttributes.WISDOM: allocated_stats.get('WISDOM', 10),
                CharacterAttributes.CHARISMA: allocated_stats.get('CHARISMA', 10),
            }
        else:
            # Fallback to template defaults
            attrs = class_template.get('attributes', {})
            new_player.attributes = {
                CharacterAttributes.STRENGTH: attrs.get('strength', 10),
                CharacterAttributes.DEXTERITY: attrs.get('dexterity', 10),
                CharacterAttributes.CONSTITUTION: attrs.get('constitution', 10),
                CharacterAttributes.INTELLIGENCE: attrs.get('intelligence', 10),
                CharacterAttributes.WISDOM: attrs.get('wisdom', 10),
                CharacterAttributes.CHARISMA: attrs.get('charisma', 10),
            }
        
        # Set HP from hit_dice in template + Constitution bonus (class-modified)
        # Constitution bonus = (CON - 10) * class multiplier
        # Fighter: 2.0x, Cleric: 1.5x, Rogue: 1.0x, Mage: 0.5x
        hit_dice_str = class_template.get('hit_dice', '1d10+0')
        dice_parts = get_dice_parts(hit_dice_str)
        new_player.hit_dice = dice_parts[0]
        new_player.hit_dice_size = dice_parts[1]
        new_player.hit_point_bonus = dice_parts[2]
        base_hp = roll_dice(new_player.hit_dice, new_player.hit_dice_size, new_player.hit_point_bonus)
        con_value = new_player.attributes.get(CharacterAttributes.CONSTITUTION, 10)
        con_multiplier = Constants.CON_HP_MULTIPLIER_BY_CLASS.get(role, 1.0)
        con_bonus = int((con_value - 10) * con_multiplier)
        BASE_STARTING_HP = 20  # All new characters start with 20 base HP
        new_player.max_hit_points = max(1, BASE_STARTING_HP + base_hp + con_bonus)  # 20 base + class HP + constitution bonus
        new_player.set_hp_to_max()
        logger.debug(f"HP calculation: base_starting=20, class_hp={base_hp}, CON={con_value}, mult={con_multiplier}, bonus={con_bonus}, total={new_player.max_hit_points}")
        
        # Combat stats from template
        new_player.base_hit_modifier = class_template.get('base_hit_modifier', 50)
        new_player.hit_modifier = new_player.base_hit_modifier
        
        # Dodge from template + Dexterity bonus (class-modified)
        # Dexterity bonus = (DEX - 10) * class multiplier
        # Rogue: 2.0x, Fighter: 1.5x, Cleric: 1.0x, Mage: 0.5x
        dodge_str = class_template.get('dodge_dice', '1d50+0')
        dodge_parts = get_dice_parts(dodge_str)
        new_player.dodge_dice_number = dodge_parts[0]
        new_player.dodge_dice_size = dodge_parts[1]
        dex_value = new_player.attributes.get(CharacterAttributes.DEXTERITY, 10)
        dex_multiplier = Constants.DEX_DODGE_MULTIPLIER_BY_CLASS.get(role, 1.0)
        dex_bonus = int((dex_value - 10) * dex_multiplier)
        new_player.base_dodge_modifier = dodge_parts[2] + dex_bonus
        new_player.dodge_modifier = new_player.base_dodge_modifier
        logger.debug(f"Dodge calculation: base={dodge_parts[2]}, DEX={dex_value}, mult={dex_multiplier}, bonus={dex_bonus}, total={new_player.base_dodge_modifier}")
        
        new_player.critical_chance = class_template.get('critical_chance', 5)
        new_player.critical_multiplier = class_template.get('critical_multiplier', 100)
        
        # Natural attack from template
        attack_def = class_template.get('natural_attack', {})
        if attack_def:
            attack = AttackData()
            attack.attack_noun = attack_def.get('noun', 'punch')
            attack.attack_verb = attack_def.get('verb', 'punch')
            dmg_type_str = attack_def.get('damage_type', 'bludgeoning').upper()
            dmg_dice_str = attack_def.get('damage_dice', '1d4+0')
            dmg_parts = get_dice_parts(dmg_dice_str)
            attack.potential_damage_.append(PotentialDamage(
                DamageType[dmg_type_str], dmg_parts[0], dmg_parts[1], dmg_parts[2]
            ))
            new_player.natural_attacks = [attack]
        
        # Connect player
        new_player.connection = connection
        connection.character = new_player
        new_player.permanent_character_flags = new_player.permanent_character_flags.add_flags(PermanentCharacterFlags.IS_PC)
        
        # Calculate mana/stamina based on class
        new_player.calculate_max_mana()
        new_player.calculate_max_stamina()
        new_player.set_mana_to_max()
        new_player.set_stamina_to_max()
        
        # Unlock level 1 skills for the class
        new_player._unlock_skills_for_level(role, 1)
        
        # Grant starting skill points (3 levels worth)
        starting_levels = Constants.STARTING_SKILL_POINTS_LEVELS
        skill_points_per_level = Constants.SKILL_POINTS_PER_LEVEL_BY_CLASS.get(role, 3)
        new_player.skill_points_available = starting_levels * skill_points_per_level
        
        # Calculate level bonuses
        new_player._update_class_features()
        
        self.players.append(new_player)
        
        # Start in default room (format: zone.room)
        start_location = Constants.DEFAULT_START_LOCATION
        if "." in start_location:
            zone_id, room_id = start_location.split(".", 1)
        else:
            zone_id = start_location
            room_id = None
            
        start_zone = self.zones.get(zone_id)
        if not start_zone:
            start_zone = self.zones[list(self.zones.keys())[0]]
            logger.warning(f"Default start zone '{zone_id}' not found, using first zone")
            
        start_room = start_zone.rooms.get(room_id) if room_id else None
        if not start_room:
            start_room = start_zone.rooms[list(start_zone.rooms.keys())[0]]
            if room_id:
                logger.warning(f"Default start room '{room_id}' not found, using first room")
        
        logger.info(f"New player {character_name} ({selected_class}) arriving in {start_room.name}")
        
        # Send starting skill points message
        await connection.send(CommTypes.DYNAMIC, f"You have {new_player.skill_points_available} skill points to distribute!")
        await connection.send(CommTypes.DYNAMIC, "Use 'skills' to see your available skills and 'skillup <skill> <points>' to train them.")
        await connection.send(CommTypes.DYNAMIC, "")
        
        await CoreActionsInterface.get_instance().arrive_room(new_player, start_room)
    
    async def _load_existing_character(self, connection: Connection, character_name: str):
        """Load an existing character from their save file."""
        logger = StructuredLogger(__name__, prefix="_load_existing_character()> ")
        logger.debug(f"Loading existing character: {character_name}")
        
        # Check if save file is a stub (only has name/password/class, not fully created yet)
        if player_save_manager.is_stub_save(character_name):
            selected_class = player_save_manager.get_selected_class(character_name)
            await self._create_new_character(connection, character_name, selected_class)
            return
        
        # Get the character template to start with
        template_id = Constants.DEFAULT_CHARACTER_TEMPLATE
        chardef = self.world_definition.find_character_definition(template_id)
        if not chardef:
            chardef = self.world_definition.find_character_definition("test_player")
            if not chardef:
                raise Exception(f"Character template '{template_id}' not found and no fallback available.")
        
        # Create character from template first
        new_player = Character.create_from_definition(chardef, self, include_items=False)
        new_player.connection = connection
        connection.character = new_player
        new_player.permanent_character_flags = new_player.permanent_character_flags.add_flags(PermanentCharacterFlags.IS_PC)
        
        # Load save data and apply it to the character
        # For now, always start at default location (not combat reconnect scenario)
        save_data = await player_save_manager.load_character(
            character_name, new_player, restore_location=False,
            world_definition=self.world_definition, game_state=self
        )
        
        if not save_data:
            # Save file exists but couldn't be loaded - treat as new character
            logger.warning(f"Could not load save data for {character_name}, treating as new character")
            new_player.name = character_name
        
        self.players.append(new_player)
        
        # Check if character is dead - if so, respawn them at start room
        if new_player.is_dead():
            logger.info(f"Character {character_name} is dead on login - respawning at start room")
            await CoreActionsInterface.get_instance()._respawn_player(new_player)
            return
        
        # Determine starting room
        # Check for combat reconnection scenario
        was_in_combat = save_data.get('was_in_combat', False) if save_data else False
        restore_location = was_in_combat  # Restore location only for combat reconnection
        
        start_room = None
        if restore_location and save_data and 'location' in save_data:
            loc = save_data['location']
            if loc.get('zone') and loc.get('room'):
                zone = self.zones.get(loc['zone'])
                if zone:
                    start_room = zone.rooms.get(loc['room'])
                    if start_room:
                        logger.info(f"Restoring {character_name} to combat location: {start_room.name}")
        
        # Fall back to default start room (format: zone.room)
        if not start_room:
            start_location = Constants.DEFAULT_START_LOCATION
            if "." in start_location:
                zone_id, room_id = start_location.split(".", 1)
            else:
                zone_id = start_location
                room_id = None
            start_zone = self.zones.get(zone_id)
            if not start_zone:
                start_zone = self.zones[list(self.zones.keys())[0]]
            start_room = start_zone.rooms.get(room_id) if room_id else None
            if not start_room:
                start_room = start_zone.rooms[list(start_zone.rooms.keys())[0]]
        
        logger.info(f"Player {character_name} arriving in {start_room.name}")
        await CoreActionsInterface.get_instance().arrive_room(new_player, start_room)


    async def handle_disconnect(self, consumer: 'MyWebsocketConsumer', close_code: int = None):
        """
        Handle a player disconnecting.
        Starts the linkdead grace period if configured.
        
        Args:
            consumer: The WebSocket consumer that disconnected
            close_code: WebSocket close code (1001=Going Away, 1012=Service Restart indicate server shutdown)
        """
        logger = StructuredLogger(__name__, prefix="handle_disconnect()> ")
        
        # Find the connection
        connection = None
        for c in self.connections:
            if c.consumer_ == consumer:
                connection = c
                break
        
        if not connection or not connection.character:
            logger.debug("No character associated with disconnecting consumer")
            return
        
        character = connection.character
        logger.info(f"Player {character.name} disconnected")
        
        # Remove connection from list
        self.connections.remove(connection)
        
        # Clear the connection reference but keep the character
        character.connection = None
        connection.character = None
        
        # If server is shutting down, skip linkdead and complete logoff immediately
        # Detect shutdown via:
        # 1. Our shutting_down flag
        # 2. WebSocket close codes: 1001 (Going Away) or 1012 (Service Restart)
        #    These indicate the server is closing the connection, not the client
        server_initiated_close = close_code in (1001, 1012)
        if self.shutting_down or server_initiated_close:
            self.shutting_down = True  # Ensure flag is set for other checks
            logger.info(f"Server shutting down (close_code={close_code}), skipping linkdead for {character.name}")
            await self._complete_logoff(character)
            return
        
        grace_period = Constants.DISCONNECT_GRACE_PERIOD_SECONDS
        
        if grace_period > 0:
            # Start linkdead period
            logger.info(f"Starting {grace_period}s linkdead period for {character.name}")
            self.linkdead_characters[character.name.lower()] = LinkdeadCharacter(character, time.time())
            
            # Notify the room
            if character.location_room:
                msg = f"{character.art_name_cap} has lost their connection."
                await character.location_room.echo(CommTypes.DYNAMIC, msg, exceptions=[character], game_state=self)
        else:
            # No grace period - immediate logoff
            await self._complete_logoff(character)
    
    async def _complete_logoff(self, character: Character):
        """
        Complete the logoff process - save character and remove from game.
        """
        logger = StructuredLogger(__name__, prefix="_complete_logoff()> ")
        logger.info(f"Completing logoff for {character.name}")
        
        # Save the character
        self._save_character(character)
        
        # Remove from combat
        if character.fighting_whom:
            character.fighting_whom = None
            if character in self.characters_fighting:
                self.characters_fighting.remove(character)
        
        # Notify room and remove from it
        if character.location_room:
            msg = f"{character.art_name_cap} has left the game."
            await character.location_room.echo(CommTypes.DYNAMIC, msg, exceptions=[character], game_state=self)
            character.location_room.remove_character(character)
            character.location_room = None
        
        # Remove from players list
        if character in self.players:
            self.players.remove(character)
        
        # Clean up linkdead entry if present
        if character.name.lower() in self.linkdead_characters:
            del self.linkdead_characters[character.name.lower()]
        
        logger.info(f"Player {character.name} logged off")
    
    def _save_character(self, character: Character):
        """Save a character to their YAML file."""
        logger = StructuredLogger(__name__, prefix="_save_character()> ")
        try:
            success = player_save_manager.save_character(
                character,
                save_states=Constants.SAVE_CHARACTER_STATES,
                save_cooldowns=Constants.SAVE_CHARACTER_COOLDOWNS
            )
            if success:
                logger.info(f"Character {character.name} saved successfully")
            else:
                logger.error(f"Failed to save character {character.name}")
        except Exception as e:
            logger.error(f"Error saving character {character.name}: {e}")
            import traceback
            traceback.print_exc()
    
    async def check_linkdead_timeouts(self):
        """
        Check for linkdead characters whose grace period has expired.
        Should be called periodically from the main game loop.
        """
        logger = StructuredLogger(__name__, prefix="check_linkdead_timeouts()> ")
        
        current_time = time.time()
        grace_period = Constants.DISCONNECT_GRACE_PERIOD_SECONDS
        
        # Find expired linkdead characters
        expired = []
        for name, linkdead in self.linkdead_characters.items():
            elapsed = current_time - linkdead.disconnect_time
            
            if elapsed >= grace_period:
                # Grace period expired
                character = linkdead.character
                
                # If still in combat, don't log them off yet
                if character.fighting_whom is not None:
                    logger.debug(f"Linkdead {name} still in combat, deferring logoff")
                    continue
                
                # If they were in combat but combat ended, now we can log them off
                expired.append(name)
        
        # Process expired characters
        for name in expired:
            linkdead = self.linkdead_characters[name]
            logger.info(f"Linkdead grace period expired for {name}")
            await self._complete_logoff(linkdead.character)


    def remove_connection(self, consumer: 'MyWebsocketConsumer'):
        """Legacy method - disconnect handling now done via handle_disconnect."""
        for c in self.connections:
            if c.consumer_ == consumer:
                if hasattr(c, 'character') and c.character:
                    self.remove_character(c.character)
                self.connections.remove(c)
                return

    def remove_player_by_connection(self, connection: Connection):
        if connection.character in self.players:
            self.players.remove(connection.character)
        else:
            logger = StructuredLogger(__name__, prefix="remove_player_by_connection()> ")
            logger.warning(f"Removing player by connection, but player not found in players list: {connection.character}.")

    def remove_player_by_character(self, character: Character):
        if character in self.players:
            self.players.remove(character)
        else:
            logger = StructuredLogger(__name__, prefix="remove_player_by_character()> ")
            logger.warning(f"Removing player by character, but player not found in players list: {character}.")

    def remove_character(self, character: Character):
        if character in self.characters:
            self.characters.remove(character)
        else:
            logger = StructuredLogger(__name__, prefix="remove_character()> ")
            logger.warning(f"Removing character, but character not found in characters list: {character}.")

    def add_scheduled_event(self, type: EventType, subject: Any, name: str, scheduled_tick: int = None, in_ticks: int = None,
                             vars: Dict[str, Any] = None, func: Callable[[Any, int, 'ComprehensiveGameState', Dict[str, Any]], None] = None,
                             attach_to_actor: Optional[Any] = None):
        logger = StructuredLogger(__name__, prefix="add_scheduled_event()> ")
        if not scheduled_tick and not in_ticks:
            raise Exception("Must specify either scheduled_tick or in_ticks.")
        elif scheduled_tick and in_ticks:
            if scheduled_tick != self.world_clock_tick + in_ticks:
                raise Exception("If both scheduled_tick and in_ticks provided, scheduled_tick must be the current tick plus in_ticks.")
        if in_ticks:
            scheduled_tick = self.world_clock_tick + in_ticks
        event = ScheduledEvent(scheduled_tick, type, subject, name, vars or {}, func, attach_to_actor=attach_to_actor)
        self.scheduled_events[scheduled_tick].append(event)
        if attach_to_actor is not None:
            # Keep actor's list chronological by on_tick
            ticks = [e.on_tick for e in attach_to_actor._scheduled_events]
            idx = bisect.bisect_right(ticks, scheduled_tick)
            attach_to_actor._scheduled_events.insert(idx, event)

    async def perform_scheduled_events(self, tick: int):
        logger = StructuredLogger(__name__, prefix="perform_scheduled_events()> ")
        if tick in self.scheduled_events:
            for event in self.scheduled_events[tick]:
                logger.debug(f"performing scheduled action {event.name}")
                await event.run(tick, self)
                if event.attach_to_actor is not None:
                    try:
                        event.attach_to_actor._scheduled_events.remove(event)
                    except ValueError:
                        pass
            del self.scheduled_events[tick]

    def remove_scheduled_event(self, scheduled_event: ScheduledEvent) -> None:
        """Remove a scheduled event from the global list and from its attach_to_actor's list if set."""
        tick = scheduled_event.on_tick
        if tick in self.scheduled_events:
            try:
                self.scheduled_events[tick].remove(scheduled_event)
            except ValueError:
                pass
        if scheduled_event.attach_to_actor is not None:
            try:
                scheduled_event.attach_to_actor._scheduled_events.remove(scheduled_event)
            except ValueError:
                pass

    def get_scheduled_events_for_actor(self, actor: Any):
        """Return read-only view of scheduled events for this actor (tuple)."""
        return actor.scheduled_events

    def spawn_character(self, character_def: Actor, room: 'Room', spawned_by: ActorSpawnData = None):
        logger = StructuredLogger(__name__, prefix="spawn_character()> ")
        if spawned_by and len(spawned_by.spawned) >= spawned_by.desired_quantity:
            logger.debug3(f"Spawn cap reached for {spawned_by.id} in room {room.rid}, skipping spawn")
            return
        new_character = Character.create_from_definition(character_def, self)
        new_character.spawned_from = spawned_by
        self.characters.append(new_character)
        room.add_character(new_character)
        if spawned_by:
            spawned_by.spawned.append(new_character)
        logger.debug3(f"Spawning {new_character.rid} added to room {new_character.location_room.rid}")

    def respawn_character(self, owner: Actor, vars: dict):
        logger = StructuredLogger(__name__, prefix="respawn_character()> ")
        spawn_data = vars.get('spawned_from') or vars.get('spawn_data')
        if not spawn_data:
            logger.warning("respawn_character called without spawned_from/spawn_data in vars")
            return
        if spawn_data.current_quantity >= spawn_data.desired_quantity:
            logger.debug3(f"Respawn cap already met for {spawn_data.id}, skipping")
            return
        character_def = self.world_definition.find_character_definition(spawn_data.id)
        if character_def is None:
            raise Exception(f"Character definition for {spawn_data.id} not found.")
        self.spawn_character(character_def, owner, spawn_data)

    def get_zone_by_id(self, zone_id: str) -> Zone:
        return self.zones[zone_id] if zone_id in self.zones else None
    
    def add_character_fighting(self, character: Character):
        if character not in self.characters_fighting:
            self.characters_fighting.append(character)

    def get_characters_fighting(self) -> List[Character]:
        return self.characters_fighting
    
    def remove_character_fighting(self, character: Character):
        if character in self.characters_fighting:
            self.characters_fighting.remove(character)
        else:
            logger = StructuredLogger(__name__, prefix="remove_character_fighting()> ")
            logger.warning(f"Removing character {character.rid} from characters_fighting, but not found.")

    def get_world_definition(self) -> WorldDefinition:
        return self.world_definition
    
    def get_xp_progression(self) -> List[int]:
        return self.xp_progression
    
    def get_temp_var(cls, source_actor_ptr: str, var_name: str) -> str:
        if source_actor_ptr[0] == Constants.REFERENCE_SYMBOL:
            source_actor_ptr = source_actor_ptr[1:]
        source_actor = Actor.get_reference(source_actor_ptr)
        if not source_actor:
            return ""
        return source_actor.get_temp_var(var_name, "")

    def get_perm_var(cls, source_actor_ptr: str, var_name: str) -> str:
        if source_actor_ptr[0] == Constants.REFERENCE_SYMBOL:
            source_actor_ptr = source_actor_ptr[1:]
        source_actor = Actor.get_reference(source_actor_ptr)
        if not source_actor:
            return ""
        return source_actor.get_perm_var(var_name, "")
    
    def get_world_definition(self) -> WorldDefinition:
        return self.world_definition
        
    def save_game_state(self, player_name: str, save_name: str) -> bool:
        """Save the current game state to the database"""
        logger = StructuredLogger(__name__, prefix="save_game_state()> ")
        try:
            # Find the player to save
            target_player = None
            for player in self.players:
                if player.name == player_name:
                    target_player = player
                    break
                    
            if not target_player:
                logger.warning(f"Player {player_name} not found in current game state")
                return False

            # Create a dictionary representation of the game state
            game_state = {
                'players': [{
                    'id': target_player.id,
                    'name': target_player.name,
                    'description': target_player.description,
                    'location': target_player.location_room.rid if target_player.location_room else None,
                    
                    # Class and level information
                    'class_priority': [role.name for role in target_player.class_priority],
                    'levels_by_role': {role.name: level for role, level in target_player.levels_by_role.items()},
                    'specializations': {base.name: spec.name for base, spec in target_player.specializations.items()},
                    
                    # Skills: in-game format is Dict[CharacterClassRole, Dict[str, int]] (inner keys normalized: lowercase, underscores)
                    'skill_levels_by_role': {
                        role.name: {(s.lower().replace(' ', '_').replace('-', '_') if isinstance(s, str) else str(s)): level for s, level in skills.items()}
                        for role, skills in target_player.skill_levels_by_role.items()
                    },
                    'skill_points_available': target_player.skill_points_available,
                    
                    # Permanent attributes
                    'attributes': {
                        'strength': target_player.attributes.get(CharacterAttributes.STRENGTH, 10),
                        'dexterity': target_player.attributes.get(CharacterAttributes.DEXTERITY, 10),
                        'constitution': target_player.attributes.get(CharacterAttributes.CONSTITUTION, 10),
                        'intelligence': target_player.attributes.get(CharacterAttributes.INTELLIGENCE, 10),
                        'wisdom': target_player.attributes.get(CharacterAttributes.WISDOM, 10),
                        'charisma': target_player.attributes.get(CharacterAttributes.CHARISMA, 10)
                    },
                    
                    # Permanent flags
                    'permanent_flags': [flag.name for flag in target_player.permanent_character_flags],
                    'game_permission_flags': [flag.name for flag in target_player.game_permission_flags],

                    'perm_variables': target_player.perm_variables,

                    # Base stats
                    'experience_points': target_player.experience_points,
                    'hit_dice': target_player.hit_dice,
                    'hit_dice_size': target_player.hit_dice_size,
                    'hit_point_bonus': target_player.hit_point_bonus,
                    'max_hit_points': target_player.max_hit_points,
                    'max_carrying_capacity': target_player.max_carrying_capacity,
                    
                    # Combat stats (base values - level bonuses recalculated on load)
                    'base_hit_modifier': target_player.base_hit_modifier,
                    'base_dodge_modifier': target_player.base_dodge_modifier,
                    'dodge_dice_number': target_player.dodge_dice_number,
                    'dodge_dice_size': target_player.dodge_dice_size,
                    'critical_chance': target_player.critical_chance,
                    'critical_multiplier': target_player.critical_multiplier,
                    'num_main_hand_attacks': target_player.num_main_hand_attacks,
                    'num_off_hand_attacks': target_player.num_off_hand_attacks,
                    
                    # Resistances and reductions
                    'damage_multipliers': {
                        dt.name: value for dt, value in target_player.damage_multipliers.profile.items()
                    },
                    'damage_reductions': {
                        dt.name: value for dt, value in target_player.damage_reduction.items()
                    },
                    
                    # Inventory and equipment
                    'inventory': [{
                        'id': obj.id,
                        'name': obj.name,
                        'description': obj.description,
                        'weight': obj.weight,
                        'value': obj.value,
                        'object_flags': [flag.name for flag in obj.object_flags],
                        'equip_locations': [loc.name for loc in obj.equip_locations],
                        'damage_multipliers': {
                            dt.name: value for dt, value in obj.damage_multipliers.profile.items()
                        },
                        'damage_reductions': {
                            dt.name: value for dt, value in obj.damage_reduction.items()
                        },
                        'damage_type': obj.damage_type.name if obj.damage_type else None,
                        'damage_num_dice': obj.damage_num_dice,
                        'damage_dice_size': obj.damage_dice_size,
                        'damage_bonus': obj.damage_bonus,
                        'attack_bonus': obj.attack_bonus,
                        'dodge_penalty': obj.dodge_penalty,
                        'contents': [{
                            'id': content.id,
                            'name': content.name,
                            'description': content.description,
                            'weight': content.weight,
                            'value': content.value,
                            'object_flags': [flag.name for flag in content.object_flags],
                            'equip_locations': [loc.name for loc in content.equip_locations],
                            'damage_multipliers': {
                                dt.name: value for dt, value in content.damage_multipliers.profile.items()
                            },
                            'damage_reductions': {
                                dt.name: value for dt, value in content.damage_reduction.items()
                            },
                            'damage_type': content.damage_type.name if content.damage_type else None,
                            'damage_num_dice': content.damage_num_dice,
                            'damage_dice_size': content.damage_dice_size,
                            'damage_bonus': content.damage_bonus,
                            'attack_bonus': content.attack_bonus,
                            'dodge_penalty': content.dodge_penalty
                        } for content in obj.contents] if obj.has_flags(ObjectFlags.IS_CONTAINER) else []
                    } for obj in target_player.contents],
                    
                    'equipment': {
                        loc.name: {
                            'id': obj.id,
                            'name': obj.name,
                            'description': obj.description,
                            'weight': obj.weight,
                            'value': obj.value,
                            'object_flags': [flag.name for flag in obj.object_flags],
                            'equip_locations': [loc.name for loc in obj.equip_locations],
                            'damage_multipliers': {
                                dt.name: value for dt, value in obj.damage_multipliers.profile.items()
                            },
                            'damage_reductions': {
                                dt.name: value for dt, value in obj.damage_reduction.items()
                            },
                            'damage_type': obj.damage_type.name if obj.damage_type else None,
                            'damage_num_dice': obj.damage_num_dice,
                            'damage_dice_size': obj.damage_dice_size,
                            'damage_bonus': obj.damage_bonus,
                            'attack_bonus': obj.attack_bonus,
                            'dodge_penalty': obj.dodge_penalty,
                            'contents': [{
                                'id': content.id,
                                'name': content.name,
                                'description': content.description,
                                'weight': content.weight,
                                'value': content.value,
                                'object_flags': [flag.name for flag in content.object_flags],
                                'equip_locations': [loc.name for loc in content.equip_locations],
                                'damage_multipliers': {
                                    dt.name: value for dt, value in content.damage_multipliers.profile.items()
                                },
                                'damage_reductions': {
                                    dt.name: value for dt, value in content.damage_reduction.items()
                                },
                                'damage_type': content.damage_type.name if content.damage_type else None,
                                'damage_num_dice': content.damage_num_dice,
                                'damage_dice_size': content.damage_dice_size,
                                'damage_bonus': content.damage_bonus,
                                'attack_bonus': content.attack_bonus,
                                'dodge_penalty': content.dodge_penalty
                            } for content in obj.contents] if obj.has_flags(ObjectFlags.IS_CONTAINER) else []
                        } if obj else None for loc, obj in target_player.equipped.items()
                    }
                }]
            }
            
            # Use the save_game utility to store in the database
            save_game(player_name, save_name, game_state)
            logger.info(f"Game saved for player {player_name} as '{save_name}'")
            return True
        except Exception as e:
            logger.error(f"Error saving game state: {e}")
            return False
    
    def load_game_state(self, player_name: str, save_name: str) -> bool:
        """Load a game state from the database"""
        logger = StructuredLogger(__name__, prefix="load_game_state()> ")
        try:
            # Load the game state from database
            game_state = load_game(player_name, save_name)
            if not game_state:
                logger.warning(f"No save found for player {player_name} with name '{save_name}'")
                return False
                
            # Find the player to load the data into
            target_player = None
            for player in self.players:
                if player.name == player_name:
                    target_player = player
                    break
                    
            if not target_player:
                logger.warning(f"Player {player_name} not found in current game state")
                return False
                
            # Load player data from the saved state
            if 'players' in game_state and len(game_state['players']) > 0:
                player_data = game_state['players'][0]
                
                # Set basic attributes
                target_player.name = player_data['name']
                target_player.description_ = player_data['description']
                
                # Load player location if needed
                if player_data['location']:
                    # Parse the location format (zone.room_id)
                    parts = player_data['location'].split('.')
                    if len(parts) >= 2:
                        zone_id = parts[0]
                        room_id = '.'.join(parts[1:])
                        
                        # Find the target room
                        zone = self.get_zone_by_id(zone_id)
                        if zone and room_id in zone.rooms:
                            # Move player to the room
                            if target_player.location_room:
                                target_player.location_room.remove_character(target_player)
                            zone.rooms[room_id].add_character(target_player)
                
                # Load class and level information
                target_player.class_priority = [CharacterClassRole[role] for role in player_data['class_priority']]
                target_player.levels_by_role = {CharacterClassRole[role]: level for role, level in player_data['levels_by_role'].items()}
                target_player.specializations = {CharacterClassRole[base]: CharacterClassRole[spec] for base, spec in player_data['specializations'].items()}
                
                # Load skills: restore to Dict[CharacterClassRole, Dict[str, int]] (inner keys normalized for skills*.py / ClassSkillsProxy)
                def _normalize_skill_key(s: str) -> str:
                    return s.lower().replace(' ', '_').replace('-', '_') if isinstance(s, str) else str(s).lower().replace(' ', '_').replace('-', '_')
                target_player.skill_levels_by_role = {
                    CharacterClassRole[role]: {_normalize_skill_key(skill): level for skill, level in skills.items()}
                    for role, skills in player_data['skill_levels_by_role'].items()
                }
                target_player.skill_points_available = player_data['skill_points_available']
                
                # Load attributes
                if 'attributes' in player_data:
                    attrs = player_data['attributes']
                    target_player.attributes[CharacterAttributes.STRENGTH] = attrs.get('strength', target_player.attributes.get(CharacterAttributes.STRENGTH, 10))
                    target_player.attributes[CharacterAttributes.DEXTERITY] = attrs.get('dexterity', target_player.attributes.get(CharacterAttributes.DEXTERITY, 10))
                    target_player.attributes[CharacterAttributes.CONSTITUTION] = attrs.get('constitution', target_player.attributes.get(CharacterAttributes.CONSTITUTION, 10))
                    target_player.attributes[CharacterAttributes.INTELLIGENCE] = attrs.get('intelligence', target_player.attributes.get(CharacterAttributes.INTELLIGENCE, 10))
                    target_player.attributes[CharacterAttributes.WISDOM] = attrs.get('wisdom', target_player.attributes.get(CharacterAttributes.WISDOM, 10))
                    target_player.attributes[CharacterAttributes.CHARISMA] = attrs.get('charisma', target_player.attributes.get(CharacterAttributes.CHARISMA, 10))
                
                # Load permanent flags
                target_player.permanent_character_flags = PermanentCharacterFlags(0)
                for flag in player_data['permanent_flags']:
                    target_player.permanent_character_flags = target_player.permanent_character_flags.add_flag_name(flag)
                    
                target_player.game_permission_flags = GamePermissionFlags(0)
                for flag in player_data['game_permission_flags']:
                    target_player.game_permission_flags = target_player.game_permission_flags.add_flag_name(flag)

                if 'perm_variables' in player_data:
                    target_player.perm_variables = player_data['perm_variables']
                else:
                    target_player.perm_variables = {}

                # Load base stats
                target_player.experience_points = player_data['experience_points']
                target_player.hit_dice = player_data['hit_dice']
                target_player.hit_dice_size = player_data['hit_dice_size']
                target_player.hit_point_bonus = player_data['hit_point_bonus']
                target_player.max_hit_points = player_data['max_hit_points']
                target_player.max_carrying_capacity = player_data['max_carrying_capacity']
                
                # Load combat stats (base values - level bonuses calculated after)
                # Support loading old saves that had hit_modifier instead of base_hit_modifier
                target_player.base_hit_modifier = player_data.get('base_hit_modifier', player_data.get('hit_modifier', 50))
                target_player.base_dodge_modifier = player_data.get('base_dodge_modifier', player_data.get('dodge_modifier', 0))
                target_player.dodge_dice_number = player_data['dodge_dice_number']
                target_player.dodge_dice_size = player_data['dodge_dice_size']
                target_player.critical_chance = player_data['critical_chance']
                target_player.critical_multiplier = player_data['critical_multiplier']
                target_player.num_main_hand_attacks = player_data['num_main_hand_attacks']
                target_player.num_off_hand_attacks = player_data['num_off_hand_attacks']
                
                # Recalculate level-based combat bonuses
                target_player.calculate_combat_bonuses()
                
                # Load multipliers and reductions
                target_player.damage_multipliers = DamageMultipliers()
                for dt_name, value in player_data['damage_multipliers'].items():
                    target_player.damage_multipliers.profile[DamageType[dt_name]] = value
                    
                target_player.damage_reduction = {DamageType[dt_name]: value for dt_name, value in player_data['damage_reductions'].items()}
                
                # Clear existing inventory and equipment
                target_player.contents = []
                target_player.equipped = {loc: None for loc in EquipLocation}
                
                # Helper function to create an object from saved data.
                # When a world definition exists for this object, create from definition so triggers (e.g. catch_inspect) are preserved.
                def create_object_from_save(obj_data):
                    definition_zone_id = obj_data.get('definition_zone_id')
                    obj_id = obj_data['id']
                    obj_def = None
                    if definition_zone_id:
                        def_key = f"{definition_zone_id}.{obj_id}"
                        obj_def = self.world_definition.find_object_definition(def_key)
                    if obj_def is None and obj_id:
                        # Fallback: look up by id only so triggers (e.g. catch_inspect) are preserved
                        obj_def = self.world_definition.find_object_definition(obj_id)
                    if obj_def is not None:
                        obj = Object.create_from_definition(obj_def)
                        if obj.has_flags(ObjectFlags.IS_CONTAINER) and obj_data.get('contents'):
                            for content_data in obj_data['contents']:
                                content = create_object_from_save(content_data)
                                obj.add_object(content)
                        return obj
                    # Fallback: build from saved data only (no triggers)
                    obj = Object(obj_data['id'], target_player.definition_zone_id, obj_data['name'])
                    obj.description_ = obj_data['description']
                    obj.weight = obj_data['weight']
                    obj.value = obj_data['value']
                    if isinstance(obj_data.get('object_flags'), int):
                        obj.object_flags = ObjectFlags(obj_data['object_flags'])
                    else:
                        obj.object_flags = ObjectFlags(0)
                        for flag in obj_data.get('object_flags', []):
                            obj.object_flags = obj.object_flags.add_flag_name(flag)
                    obj.equip_locations = [EquipLocation[loc] for loc in obj_data.get('equip_locations', [])]
                    obj.damage_multipliers = DamageMultipliers()
                    for dt_name, value in obj_data.get('damage_multipliers', {}).items():
                        obj.damage_multipliers.profile[DamageType[dt_name]] = value
                    obj.damage_reduction = DamageReduction()
                    for dt_name, value in obj_data.get('damage_reduction', {}).items():
                        obj.damage_reduction.profile[DamageType[dt_name]] = value
                    obj.damage_type = DamageType[obj_data['damage_type']] if obj_data.get('damage_type') else None
                    obj.damage_num_dice = obj_data.get('damage_num_dice', 0)
                    obj.damage_dice_size = obj_data.get('damage_dice_size', 0)
                    obj.damage_bonus = obj_data.get('damage_bonus', 0)
                    obj.attack_bonus = obj_data.get('attack_bonus', 0)
                    obj.dodge_penalty = obj_data.get('dodge_penalty', 0)
                    
                    # Handle container contents
                    if obj.has_flags(ObjectFlags.IS_CONTAINER):
                        for content_data in obj_data.get('contents', []):
                            content = create_object_from_save(content_data)
                            obj.add_object(content)
                            
                    return obj
                
                # Load inventory
                for obj_data in player_data['inventory']:
                    obj = create_object_from_save(obj_data)
                    target_player.add_object(obj)
                
                # Load equipment
                for loc_name, obj_data in player_data['equipment'].items():
                    if obj_data:
                        obj = create_object_from_save(obj_data)
                        target_player.equip_item(EquipLocation[loc_name], obj)
                
                # Update class features based on loaded data
                target_player._update_class_features()
                
            logger.info(f"Game loaded for player {player_name} from save '{save_name}'")
            return True
        except Exception as e:
            logger.error(f"Error loading game state: {e}")
            return False
    
    def list_game_saves(self, player_name: str) -> List[tuple]:
        """List all save games for a player"""
        return list_saves(player_name)
    
    def delete_game_save(self, player_name: str, save_name: str) -> bool:
        """Delete a save game"""
        return delete_save(player_name, save_name)

    def can_see(self, char: Character, target: Character) -> bool:
        if char == target:
            return True
        if char.actor_type != ActorType.CHARACTER or target.actor_type != ActorType.CHARACTER:
            return True
        # TODO:L: maybe handle invisible objects
        if target.has_temp_flags(TemporaryCharacterFlags.IS_INVISIBLE) \
        or target.has_perm_flags(PermanentCharacterFlags.IS_INVISIBLE):
            if not char.has_temp_flags(TemporaryCharacterFlags.SEE_INVISIBLE) \
            and not char.has_perm_flags(PermanentCharacterFlags.SEE_INVISIBLE):
                return False
        if target.has_temp_flags(TemporaryCharacterFlags.IS_STEALTHED):
            stealth_states = [s for s in target.get_states() if isinstance(s) == CharacterStateStealthed]
            if len(stealth_states) == 0:
                # TODO:L: this probably should log an error message
                return False
            if not char in stealth_states[0].vars_['seen_by']:
                return False
        return True
    
    def handle_scheduled_events(self, event: ScheduledEvent):
        for scheduled_event in self.scheduled_events[self.world_clock_tick]:
            scheduled_event.run(self.world_clock_tick, self)
            
    def get_current_tick(self) -> int:
        return self.world_clock_tick


live_game_state = ComprehensiveGameState()
GameStateInterface.set_instance(live_game_state)