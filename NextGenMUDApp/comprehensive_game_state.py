from collections import defaultdict
import copy
import fnmatch
import time
from .structured_logger import StructuredLogger
from django.conf import settings
import json
import os
import sys
from typing import List, Dict, Optional, Callable, Any
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
        self.world_clock_tick: int = 0
        self.scheduled_events = defaultdict(list)
        self.xp_progression: List[int] = []
        self.linkdead_characters: Dict[str, LinkdeadCharacter] = {}  # name -> LinkdeadCharacter
        self.shutting_down: bool = False  # Flag to indicate server is stopping
        # MyWebsocketConsumerStateHandlerInterface.game_state_handler = self


    def Initialize(self):
        logger = StructuredLogger(__name__, prefix="Initialize()> ")

        self.world_definition.zones = {}

        self.xp_progression = Constants.XP_PROGRESSION

        file_found = False
        logger.info(f"Loading world files (*.yaml) from [{self.app_config.WORLD_DATA_DIR}]...")
        yaml_loader = YAML(typ='safe')  # Use safe loader

        for yaml_file in find_yaml_files(self.app_config.WORLD_DATA_DIR):
            logger.info(f"Loading world file {yaml_file}")
            try:
                with open(yaml_file, "r", encoding='utf-8') as yf:
                    # yaml_data = yaml.safe_load(yf)
                    yaml_data = yaml_loader.load(yf)
                    file_found = True
                
                if yaml_data is None:
                    logger.warning(f"YAML file {yaml_file} is empty or contains only comments.")
                    continue
                
                if not isinstance(yaml_data, dict):
                    logger.error(f"YAML file {yaml_file} does not contain a valid dictionary structure.")
                    continue # Skip this file

                # Process ZONES
                if 'ZONES' in yaml_data:
                    logger.debug("Loading zones...")
                    if not isinstance(yaml_data['ZONES'], dict):
                        logger.error(f"'ZONES' section in {yaml_file} is not a dictionary.")
                    else:
                        for zone_id, zone_info in yaml_data['ZONES'].items():
                            if not isinstance(zone_info, dict):
                                logger.error(f"Zone definition '{zone_id}' in {yaml_file} is not a dictionary.")
                                continue
                            logger.info(f"Loading zone_id: {zone_id}")
                            new_zone = Zone(zone_id)
                            new_zone.name = zone_info.get('name', f"Unnamed Zone {zone_id}") # Use .get for safety
                            new_zone.description = zone_info.get('description', "")
                            
                            # Load common knowledge for LLM NPC conversations
                            if 'common_knowledge' in zone_info:
                                common_k = zone_info['common_knowledge']
                                if isinstance(common_k, dict):
                                    new_zone.common_knowledge = common_k
                                    logger.debug(f"Loaded {len(common_k)} common knowledge entries for zone {zone_id}")
                                else:
                                    logger.warning(f"common_knowledge in zone {zone_id} is not a dictionary, ignoring")
                            
                            # Load quest variable schema
                            if 'quest_variables' in zone_info:
                                from .quest_schema import QuestSchemaRegistry
                                registry = QuestSchemaRegistry.get_instance()
                                quest_vars = zone_info['quest_variables']
                                if isinstance(quest_vars, dict):
                                    count = registry.load_from_dict(quest_vars, zone_id=zone_id)
                                    logger.debug(f"Loaded {count} quest variables for zone {zone_id}")
                                else:
                                    logger.warning(f"quest_variables in zone {zone_id} is not a dictionary, ignoring")
                            
                            self.world_definition.zones[zone_id] = new_zone
                            logger.debug(f"Loading rooms for zone {zone_id}...")
                            if 'rooms' in zone_info:  # Check if rooms key exists
                                if not isinstance(zone_info['rooms'], dict):
                                     logger.error(f"'rooms' section in zone '{zone_id}' ({yaml_file}) is not a dictionary.")
                                else:
                                    for room_id, room_info in zone_info['rooms'].items():
                                        if not isinstance(room_info, dict):
                                            logger.error(f"Room definition '{room_id}' in zone '{zone_id}' ({yaml_file}) is not a dictionary.")
                                            continue
                                        logger.debug2(f"Loading room_id: {room_id}")
                                        new_room = Room(room_id, new_zone, create_reference=True)
                                        new_room.from_yaml(new_zone, room_info)
                                        new_zone.rooms[room_id] = new_room
                                    logger.debug(f"Rooms loaded for zone {zone_id}")
                            else:
                                logger.warning(f"Zone {zone_id} in {yaml_file} has no rooms defined")
                    logger.debug("Zones processing complete for this file")

                # Process CHARACTERS
                if "CHARACTERS" in yaml_data:
                    logger.debug("Loading characters...")
                    if not isinstance(yaml_data["CHARACTERS"], list):
                        logger.error(f"'CHARACTERS' section in {yaml_file} is not a list.")
                    else:
                        for zonedef in yaml_data["CHARACTERS"]:
                            if not isinstance(zonedef, dict) or 'zone' not in zonedef or 'characters' not in zonedef:
                                logger.error(f"Invalid character zone definition in {yaml_file}: {zonedef}")
                                continue
                            zone_id = zonedef['zone']
                            if not isinstance(zonedef["characters"], list):
                                logger.error(f"'characters' key in zone '{zone_id}' ({yaml_file}) is not a list.")
                                continue
                                
                            logger.debug(f"Loading characters for zone: {zone_id}")
                            if zone_id not in self.world_definition.zones:
                                logger.error(f"Character zone '{zone_id}' defined in {yaml_file} does not exist. Skipping characters.")
                                continue
                                
                            for chardef in zonedef["characters"]:
                                if not isinstance(chardef, dict) or 'id' not in chardef:
                                    logger.error(f"Invalid character definition in zone '{zone_id}' ({yaml_file}): {chardef}")
                                    continue
                                char_id = chardef['id']
                                logger.debug2(f"Loading character definition: {char_id}")
                                ch = Character(char_id, zone_id, create_reference=False)
                                ch.from_yaml(chardef, zone_id)
                                ch.game_permission_flags = ch.game_permission_flags.add_flags(GamePermissionFlags.IS_ADMIN) # TODO: Remove admin default
                                logger.debug3(f"Loaded character definition: {char_id} for zone {zone_id}")
                                self.world_definition.characters[f"{zone_id}.{ch.id}"] = ch
                    logger.debug("Characters processing complete for this file")

                # Process OBJECTS
                if "OBJECTS" in yaml_data:
                    logger.debug("Loading objects...")
                    if not isinstance(yaml_data["OBJECTS"], list):
                        logger.error(f"'OBJECTS' section in {yaml_file} is not a list.")
                    else:
                        for zonedef in yaml_data["OBJECTS"]:
                            if not isinstance(zonedef, dict) or 'zone' not in zonedef or 'objects' not in zonedef:
                                logger.error(f"Invalid object zone definition in {yaml_file}: {zonedef}")
                                continue
                            zone_id = zonedef['zone']
                            if not isinstance(zonedef["objects"], list):
                                logger.error(f"'objects' key in zone '{zone_id}' ({yaml_file}) is not a list.")
                                continue
                                
                            logger.debug(f"Loading objects for zone: {zone_id}")
                            if zone_id not in self.world_definition.zones:
                                logger.error(f"Object zone '{zone_id}' defined in {yaml_file} does not exist. Skipping objects.")
                                continue

                            for objdef in zonedef["objects"]:
                                if not isinstance(objdef, dict) or 'id' not in objdef:
                                    logger.error(f"Invalid object definition in zone '{zone_id}' ({yaml_file}): {objdef}")
                                    continue
                                obj_id = objdef['id']
                                logger.debug2(f"Loading object definition: {obj_id}")
                                obj = Object(obj_id, zone_id, create_reference=False)
                                obj.from_yaml(objdef, zone_id,self)
                                self.world_definition.objects[f"{zone_id}.{obj.id}"] = obj
                    logger.debug("Objects processing complete for this file")

            except FileNotFoundError:
                 logger.error(f"World file not found: {yaml_file}")
            except YAMLError as e:
                logger.error(f"Error parsing world YAML file: {yaml_file}")
                if hasattr(e, 'problem_mark'):
                    mark = e.problem_mark
                    logger.error(f"  Error occurred at line {mark.line + 1}, column {mark.column + 1}")
                if hasattr(e, 'problem'):
                    logger.error(f"  Problem: {e.problem}")
                if hasattr(e, 'context') and e.context:
                     logger.error(f"  Context: {e.context}")
                # Continue loading other files, but maybe add a flag to indicate errors?
            except Exception as e:
                 logger.exception(f"An unexpected error occurred loading world file {yaml_file}: {e}")

        if not file_found:
            raise Exception(f"No world files (*.yaml) found in {self.app_config.WORLD_DATA_DIR}.")
        if not self.world_definition.zones:
            raise Exception("No zones were successfully loaded. Check YAML files and logs.")

        logger.info(f"World files finished loading, from [{self.app_config.WORLD_DATA_DIR}].")

        logger.info("Preparing world...")
        # copy to operating data
        self.zones = copy.deepcopy(self.world_definition.zones)
        # print("init zones")
        logger.info("Initializing zones...")
        for zone, zone_data in self.zones.items():
            logger.debug(f"init rooms for zone: {zone}")
            for room, room_data in zone_data.rooms.items():
                room_data.create_reference()
                # print(f"room_data: {room_data}")
                logger.debug3("init spawndata")
                for spawndata in room_data.spawn_data:
                    logger.debug3(f"spawndata: {spawndata}")
                    spawndata.owner = room_data
                    logger.debug3(f"spawndata.actor_type: {spawndata.actor_type}")
                    if spawndata.actor_type == ActorType.CHARACTER:
                        logger.debug3("spawndata is character")
                        character_def = self.world_definition.find_character_definition(spawndata.id)
                        if not character_def:
                            logger.warning(f"Character definition for {spawndata.id} not found.")
                            raise Exception(f"Character definition for {spawndata.id} not found.")
                        # DEBUGGING:
                        for i in range(spawndata.desired_quantity):
                            new_character = Character.create_from_definition(character_def, self)
                            new_character.spawned_by = spawndata
                            self.characters.append(new_character)
                            spawndata.owner.add_character(new_character)
                            spawndata.spawned.append(new_character)
                            logger.debug3(f"new_character: {new_character} added to room {new_character._location_room.rid}")
                for trig_type in room_data.triggers_by_type:
                    for trig in room_data.triggers_by_type[trig_type]:
                        logger.debug3("enabling trigger")
                        trig.enable()

        logger.info("World prepared")
        
        # Print zone statistics
        print("\n=== WORLD LOADING STATISTICS ===")
        for zone_id, zone_data in self.world_definition.zones.items():
            room_count = len(zone_data.rooms)
            
            # Count character definitions for this zone
            char_count = 0
            for char_id, char_def in self.world_definition.characters.items():
                if char_def.definition_zone_id == zone_id:
                    char_count += 1
            
            # Count object definitions for this zone
            obj_count = 0
            for obj_key, obj_def in self.world_definition.objects.items():
                if obj_key.startswith(f"{zone_id}."):
                    obj_count += 1
            
            print(f"Zone '{zone_id}': {room_count} room definitions, {char_count} character definitions, {obj_count} object definitions")
        print("===============================\n")
    

    def find_target_character(self, actor: Actor, target_name: str, search_zone=False, search_world=False, exclude_initiator=True) -> Character:
        logger = StructuredLogger(__name__, prefix="find_target_character()> ")
        # search_world automatically turns on search_zone
        if target_name[0] == Constants.REFERENCE_SYMBOL:
            return Actor.get_reference(target_name[1:])
        if target_name.lower() == 'me' or target_name.lower() == 'self':
            return actor
                
        # Determine the starting point
        start_room = None
        if isinstance(actor, Character):
            start_room = actor._location_room
        elif isinstance(actor, Room):
            start_room = actor
        elif isinstance(actor, Object) and actor._location_room:
            start_room = actor._location_room

        if not start_room:
            return None

        # Parse the target name and target number
        target_number = 1
        if '#' in target_name:
            parts = target_name.split('#')
            target_name = parts[0]
            try:
                target_number = int(parts[1])
            except:
                return None

        candidates = []
        target_lower = target_name.lower()

        # Helper function to add candidates from a room
        def add_candidates_from_room(actor, room):
            for char in room.get_characters():
                # Skip the initiating actor if exclude_initiator is True
                if exclude_initiator and char == actor:
                    continue
                
                # Case-insensitive matching on id and name
                if char.id.lower().startswith(target_lower) and self.can_see(char, actor):
                    candidates.append(char)
                else:
                    namepieces = char.name.lower().split(' ')
                    for piece in namepieces:
                        if piece.startswith(target_lower) and self.can_see(char, actor):
                            candidates.append(char)
                            break

        # Search in the current room
        add_candidates_from_room(actor, start_room)

        if search_zone or search_world:
            # If not found in the current room, search in the current zone
            if len(candidates) < target_number and isinstance(start_room, Room) and start_room.zone:
                for room in start_room.zone.rooms.values():
                    add_candidates_from_room(actor, room)

        if search_world:
            # If still not found, search across all zones
            if len(candidates) < target_number:
                for zone in self.zones.values():
                    for room in zone.rooms.values():
                        add_candidates_from_room(actor, room)

        # Return the target character
        logger.debug3(f"candidates: {candidates}")
        if 0 < target_number <= len(candidates):
            return candidates[target_number - 1]

        return None


    def find_all_characters(self, actor: Actor, target_name: str) -> str:
        # TODO:L: should we limit these to can-see?
        # Determine the starting point
        start_room = None
        if isinstance(actor, Character):
            start_room = actor._location_room
        elif isinstance(actor, Room):
            start_room = actor
        elif isinstance(actor, Object) and actor._location_room:
            start_room = actor._location_room

        if not start_room:
            return ""

        matching_characters = []
        target_lower = target_name.lower()

        # Helper function to add matching characters from a room
        def add_matching_characters_from_room(room):
            for char in room.characters_:
                # Case-insensitive matching
                if char.id.lower().startswith(target_lower):
                    matching_characters.append(f"{article_plus_name(char.article_, char.name, cap=True)} in {room.name}")
                else:
                    namepieces = char.name.lower().split(' ')
                    for piece in namepieces:
                        if piece.startswith(target_lower):
                            matching_characters.append(f"{article_plus_name(char.article_, char.name, cap=True)} in {room.name}")
                            break

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
        if target_name[0] == Constants.REFERENCE_SYMBOL:
            return Actor.get_reference(target_name[1:])
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
        
        # No zone specified - search in start_zone first
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
    

    def find_target_object(self, target_name: str, actor: Actor = None, equipped: Dict[EquipLocation, Object] = None, 
                           start_room: 'Room' = None, start_zone: Zone = None, search_world=False) -> Object:
        logger = StructuredLogger(__name__, prefix="find_target_object()> ")

        if target_name[0] == Constants.REFERENCE_SYMBOL:
            return Actor.get_reference(target_name[1:])
        if target_name.lower() == 'me' or target_name.lower() == "self":
            return actor

        def check_object(obj) -> bool:
            logger = StructuredLogger(__name__, prefix="find_target_object.check_object()> ")
            if obj.id.startswith(target_name):
                return True
            for pieces in obj.name.split(' '):
                logger.debug3(f"pieces: {pieces} ? {target_name}")
                if pieces.startswith(target_name):
                    return True
            return False

        target_number = 1
        if '#' in target_name:
            parts = target_name.split('#')
            target_name = parts[0]
            try:
                target_number = int(parts[1])
            except:
                return None

        candidates: List[Object] = []

        if equipped:
            for obj in equipped.values():
                if obj and check_object(obj):
                    candidates.append(obj)
        if actor:
            for obj in actor.contents:
                if check_object(obj):
                    candidates.append(obj)
        if start_room:
            for obj in start_room.contents:
                if check_object(obj):
                    candidates.append(obj)
        if start_zone:
            for room in start_zone.rooms.values():
                for obj in room.contents:
                    if check_object(obj):
                        candidates.append(obj)
        if search_world:
            for zone in self.zones.values():
                for room in zone.rooms.values():
                    for obj in room.contents:
                        if check_object(obj):
                            candidates.append(obj)
        
        # Return the target object
        logger.debug3(f"candidates: {candidates}")
        if 0 < target_number <= len(candidates):
            return candidates[target_number - 1]
        return None
    

    
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
        new_player.current_hit_points = new_player.max_hit_points
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
            attack.attack_verb = attack_def.get('verb', 'punches')
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
        new_player.current_mana = new_player.max_mana
        new_player.current_stamina = new_player.max_stamina
        
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
        save_data = player_save_manager.load_character(character_name, new_player, restore_location=False)
        
        if not save_data:
            # Save file exists but couldn't be loaded - treat as new character
            logger.warning(f"Could not load save data for {character_name}, treating as new character")
            new_player.name = character_name
        
        self.players.append(new_player)
        
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
                             vars: Dict[str, Any]=None, func: Callable[[Any, int, 'ComprehensiveGameState', Dict[str, Any]], None] = None):
        logger = StructuredLogger(__name__, prefix="add_scheduled_event()> ")
        if not scheduled_tick and not in_ticks:
            raise Exception("Must specify either scheduled_tick or in_ticks.")
        elif scheduled_tick and in_ticks:
            if scheduled_tick != self.world_clock_tick + in_ticks:
                raise Exception("If both scheduled_tick and in_ticks provided, scheduled_tick must be the current tick plus in_ticks.")
        if in_ticks:
            scheduled_tick = self.world_clock_tick + in_ticks
        event = ScheduledEvent(scheduled_tick, type, subject, name, vars, func)
        self.scheduled_events[scheduled_tick].append(event)

    async def perform_scheduled_events(self, tick: int):
        logger = StructuredLogger(__name__, prefix="perform_scheduled_events()> ")
        if tick in self.scheduled_events:
            for event in self.scheduled_events[tick]:
                # we'll pass through dead ppl in case the event needs it
                # if event.actor_ and Actor.is_deleted(event.actor_):
                #     event.actor_ = None
                #     continue
                logger.debug(f"performing scheduled action {event.name}")
                await event.run(tick, self)
            del self.scheduled_events[tick]

    def spawn_character(self, character_def: Actor, room: 'Room', spawned_by: ActorSpawnData = None):
        logger = StructuredLogger(__name__, prefix="spawn_character()> ")
        new_character = Character.create_from_definition(character_def)
        new_character.spawned_by = spawned_by
        self.characters.append(new_character)
        room.add_character(new_character)
        if spawned_by:
            spawned_by.spawned.append(new_character)
        logger.debug3(f"Spawning {new_character.rid} added to room {new_character._location_room.rid}")

    def respawn_character(self, owner: Actor, vars: dict):
        logger = StructuredLogger(__name__, prefix="respawn_character()> ")
        spawn_data = vars['spawned_from']
        character_def = self.world_definition.find_character_definition(spawn_data.id)
        if character_def == None:
            raise Exception(f"Character definition for {spawn_data.id} not found.")
        self.spawn_character(character_def, owner, spawn_data)

    def get_zone_by_id(self, zone_id: str) -> Zone:
        return self.zones[zone_id] if zone_id in self.zones else None
    
    def add_character_fighting(self, character: Character):
        if character in self.characters_fighting:
            raise Exception(f"Character {character.rid} already in characters_fighting.")
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
                    'description': target_player.description_,
                    'location': target_player._location_room.rid if target_player._location_room else None,
                    
                    # Class and level information
                    'class_priority': [role.name for role in target_player.class_priority],
                    'levels_by_role': {role.name: level for role, level in target_player.levels_by_role.items()},
                    'specializations': {base.name: spec.name for base, spec in target_player.specializations.items()},
                    
                    # Skills
                    'skill_levels_by_role': {
                        role.name: {skill.name: level for skill, level in skills.items()}
                        for role, skills in target_player.skill_levels_by_role.items()
                    },
                    'skill_points_available': target_player.skill_points_available,
                    
                    # Permanent attributes
                    'attributes': {
                        'strength': target_player.attributes.strength,
                        'dexterity': target_player.attributes.dexterity,
                        'constitution': target_player.attributes.constitution,
                        'intelligence': target_player.attributes.intelligence,
                        'wisdom': target_player.attributes.wisdom,
                        'charisma': target_player.attributes.charisma
                    },
                    
                    # Permanent flags
                    'permanent_flags': [flag.name for flag in target_player.permanent_character_flags],
                    'game_permission_flags': [flag.name for flag in target_player.game_permission_flags],
                    
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
                        'description': obj.description_,
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
                            'description': content.description_,
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
                            'description': obj.description_,
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
                                'description': content.description_,
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
                            if target_player._location_room:
                                target_player._location_room.remove_character(target_player)
                            zone.rooms[room_id].add_character(target_player)
                
                # Load class and level information
                target_player.class_priority = [CharacterClassRole[role] for role in player_data['class_priority']]
                target_player.levels_by_role = {CharacterClassRole[role]: level for role, level in player_data['levels_by_role'].items()}
                target_player.specializations = {CharacterClassRole[base]: CharacterClassRole[spec] for base, spec in player_data['specializations'].items()}
                
                # Load skills
                target_player.skill_levels_by_role = {
                    CharacterClassRole[role]: {skill: level for skill, level in skills.items()}
                    for role, skills in player_data['skill_levels_by_role'].items()
                }
                target_player.skill_points_available = player_data['skill_points_available']
                
                # Load attributes
                if 'attributes' in player_data:
                    attrs = player_data['attributes']
                    target_player.attributes.strength = attrs.get('strength', target_player.attributes.strength)
                    target_player.attributes.dexterity = attrs.get('dexterity', target_player.attributes.dexterity)
                    target_player.attributes.constitution = attrs.get('constitution', target_player.attributes.constitution)
                    target_player.attributes.intelligence = attrs.get('intelligence', target_player.attributes.intelligence)
                    target_player.attributes.wisdom = attrs.get('wisdom', target_player.attributes.wisdom)
                    target_player.attributes.charisma = attrs.get('charisma', target_player.attributes.charisma)
                
                # Load permanent flags
                target_player.permanent_character_flags = PermanentCharacterFlags(0)
                for flag in player_data['permanent_flags']:
                    target_player.permanent_character_flags = target_player.permanent_character_flags.add_flag_name(flag)
                    
                target_player.game_permission_flags = GamePermissionFlags(0)
                for flag in player_data['game_permission_flags']:
                    target_player.game_permission_flags = target_player.game_permission_flags.add_flag_name(flag)
                
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
                
                # Helper function to create an object from saved data
                def create_object_from_save(obj_data):
                    obj = Object(obj_data['id'], target_player.definition_zone_id, obj_data['name'])
                    obj.description_ = obj_data['description']
                    obj.weight = obj_data['weight']
                    obj.value = obj_data['value']
                    obj.object_flags = ObjectFlags(0)
                    for flag in obj_data['object_flags']:
                        obj.object_flags = obj.object_flags.add_flag_name(flag)
                    obj.equip_locations = [EquipLocation[loc] for loc in obj_data['equip_locations']]
                    obj.damage_multipliers = DamageMultipliers()
                    for dt_name, value in obj_data['damage_multipliers'].items():
                        obj.damage_multipliers.profile[DamageType[dt_name]] = value
                    obj.damage_reduction = {DamageType[dt_name]: value for dt_name, value in obj_data['damage_reductions'].items()}
                    obj.damage_type = DamageType[obj_data['damage_type']] if obj_data['damage_type'] else None
                    obj.damage_num_dice = obj_data['damage_num_dice']
                    obj.damage_dice_size = obj_data['damage_dice_size']
                    obj.damage_bonus = obj_data['damage_bonus']
                    obj.attack_bonus = obj_data['attack_bonus']
                    obj.dodge_penalty = obj_data['dodge_penalty']
                    
                    # Handle container contents
                    if obj.has_flags(ObjectFlags.IS_CONTAINER):
                        for content_data in obj_data['contents']:
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