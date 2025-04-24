from collections import defaultdict
import copy
import fnmatch
from .structured_logger import StructuredLogger
from django.conf import settings
import json
import os
from typing import List, Dict, Optional, Callable, Any
import yaml
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
from .constants import Constants
from .communication import Connection
from .comprehensive_game_state_interface import GameStateInterface, ScheduledEvent, EventType
from .config import Config, default_app_config
from .core_actions_interface import CoreActionsInterface
from .utility import article_plus_name
# from .consumers import MyWebsocketConsumerStateHandlerInterface
from .nondb_models.world import Zone

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
        # MyWebsocketConsumerStateHandlerInterface.game_state_handler = self


    def Initialize(self):
        logger = StructuredLogger(__name__, prefix="Initialize()> ")

        self.world_definition.zones = {}

        self.xp_progression = Constants.XP_PROGRESSION   

        file_found = False
        logger.info(f"Loading world files (*.yaml) from [{self.app_config.WORLD_DATA_DIR}]...")
        for yaml_file in find_yaml_files(self.app_config.WORLD_DATA_DIR):
            logger.info(f"Loading world file {yaml_file}")
            with open(yaml_file, "r") as yf:
                yaml_data = yaml.safe_load(yf)
                file_found = True
            if yaml_data == None:
                logger.warning(f"YAML file {yaml_file} is empty.")
                continue
            # try:
            if 'ZONES' in yaml_data:
                logger.debug("Loading zones...")
                for zone_id, zone_info in yaml_data['ZONES'].items():
                    logger.info(f"Loading zone_id: {zone_id}")
                    new_zone = Zone(zone_id)
                    new_zone.name = zone_info['name']
                    # logger.debug(f"new_zone.name: {new_zone.name}")
                    new_zone.description = zone_info['description']
                    self.world_definition.zones[zone_id] = new_zone
                    logger.debug(f"Loading rooms...")
                    if 'rooms' in zone_info:  # Check if rooms key exists
                        for room_id, room_info in zone_info['rooms'].items():
                            logger.debug2(f"Loading room_id: {room_id}")
                            new_room = Room(room_id, self.world_definition.zones[zone_id])
                            new_room.from_yaml(new_zone, room_info)
                            new_zone.rooms[room_id] = new_room
                        logger.debug("Rooms loaded")
                    else:
                        logger.warning(f"Zone {zone_id} has no rooms defined")
                logger.debug("Zones loaded")

            if "CHARACTERS" in yaml_data:
                logger.debug("Loading characters...")
                # print(yaml_data)
                # for charzone in yaml_data["ZONES"]:
                #     for chardef in yaml_data["ZONES"]["CHARACTERS"]:
                #         ch = Character(chardef["id"], charzone)
                #         ch.from_yaml(chardef)
                #         self.world_definition_.characters_[ch.id] = ch
                for zonedef in yaml_data["CHARACTERS"]:
                    for chardef in zonedef["characters"]:
                        ch = Character(chardef["id"], self.world_definition.zones[zonedef["zone"]], create_reference=False)
                        ch.from_yaml(chardef, zonedef["zone"])
                        ch.game_permission_flags = ch.game_permission_flags.add_flags(GamePermissionFlags.IS_ADMIN)
                        logger.debug(f"loaded character: {ch.id}")
                        self.world_definition.characters[ch.id] = ch

                logger.debug("Characters loaded")

            if "OBJECTS" in yaml_data:
                # Objects
                logger.debug("Loading objects...")
                # print(yaml_data)
                # for charzone in yaml_data["ZONES"]:
                #     for chardef in yaml_data["ZONES"]["CHARACTERS"]:
                #         ch = Character(chardef["id"], charzone)
                #         ch.from_yaml(chardef)
                #         self.world_definition_.characters_[ch.id] = ch
                for zonedef in yaml_data["OBJECTS"]:
                    for objdef in zonedef["objects"]:
                        obj = Object(objdef["id"], zonedef["zone"], create_reference=False)
                        obj.from_yaml(objdef, self)
                        self.world_definition.objects[zonedef["zone"] + "." + obj.id] = obj
                logger.debug("Objects loaded")
            # except Exception as e:
            #     logger.error(f"Error loading yaml file {yaml_file}: {e}")

        if not file_found:
            raise Exception(f"No world files found in {self.app_config.WORLD_DATA_DIR}.")
        if self.world_definition.zones == {}:
            raise Exception("No zones loaded.")
        if self.world_definition.zones == None:
            raise Exception("Zones is NONE.")
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
        for zone_id, zone_data in self.zones.items():
            room_count = len(zone_data.rooms)
            
            # Count characters in this zone
            char_count = 0
            for room in zone_data.rooms.values():
                char_count += len(room.get_characters())
            
            # Count objects in this zone
            obj_count = 0
            for room in zone_data.rooms.values():
                obj_count += len(room.contents)
                # Also count objects carried by characters
                for char in room.get_characters():
                    obj_count += len(char.contents)
                    # Count equipped items
                    for item in char.equipped.values():
                        if item:
                            obj_count += 1
            
            print(f"Zone '{zone_id}': {room_count} rooms, {char_count} characters, {obj_count} objects")
        print("===============================\n")
    

    def find_target_character(self, actor: Actor, target_name: str, search_zone=False, search_world=False) -> Character:
        logger = StructuredLogger(__name__, prefix="find_target_character()> ")
        # search_world automatically turns on search_zone
        if target_name[0] == Constants.REFERENCE_SYMBOL:
            return Actor.get_reference(target_name[1:])
        if target_name[0].lower() == 'me':
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

        # Helper function to add candidates from a room
        def add_candidates_from_room(actor, room):
            for char in room.get_characters():
                if char.id.startswith(target_name) and self.can_see(char, actor):
                    candidates.append(char)
                else:
                    namepieces = char.name.split(' ')
                    for piece in namepieces:
                        if piece.startswith(target_name) and self.can_see(char, actor):
                            candidates.append(char)

        # Search in the current room
        add_candidates_from_room(actor, start_room)

        if search_zone or search_world:
            # If not found in the current room, search in the current zone
            if len(candidates) < target_number and isinstance(start_room, Room) and start_room.zone_:
                for room in start_room.zone_.rooms.values():
                    add_candidates_from_room(actor, room)

        if search_world:
            # If still not found, search across all zones
            if len(candidates) < target_number:
                for zone in self.zones.values():
                    for room in zone.rooms.values():
                        add_candidates_from_room(actor, room)

        # Return the target character
        logger.critical(f"candidates: {candidates}")
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

        # Helper function to add matching characters from a room
        def add_matching_characters_from_room(room):
            for char in room.characters_:
                if char.id.startswith(target_name):
                    matching_characters.append(f"{article_plus_name(char.article_, char.name, cap=True)} in {room.name}")
                else:
                    namepieces = char.name.split(' ')
                    for piece in namepieces:
                        if piece.startswith(target_name):
                            matching_characters.append(f"{article_plus_name(char.article_, char.name, cap=True)} in {room.name}")
                            break

        # Search in the current room
        add_matching_characters_from_room(start_room)

        # Search in the current zone
        if isinstance(start_room, Room) and start_room.zone_:
            for room in start_room.zone_.rooms.values():
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
        if target_name[0].lower() == 'me':
            return actor
        for room in start_zone.rooms.values():
            if room.name.startswith(target_name) or room.id.startswith(target_name):
                return room
        for zone in self.zones:
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
        if target_name[0].lower() == 'me':
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
        logger.critical(f"candidates: {candidates}")
        if 0 < target_number <= len(candidates):
            return candidates[target_number - 1]
        return None
    

    
    async def start_connection(self, consumer: 'MyWebsocketConsumer'):
        logger = StructuredLogger(__name__, prefix="startConnection()> ")
        logger.debug("init new connection")
        await consumer.send(text_data=json.dumps({ 
            'text_type': 'dynamic',
            'text': 'Connection accepted!'
        }))

        new_connection = Connection(consumer)
        # await new_connection.send("static", "Welcome to NextGenMUD!")
        self.connections.append(new_connection)
        await self.load_in_character(new_connection)
        return new_connection


    async def load_in_character(self, connection: Connection):
        logger = StructuredLogger(__name__, prefix="loadInCharacter()> ")
        logger.debug("loading in character")
        chardef = self.world_definition.find_character_definition("test_player")
        if not chardef:
            raise Exception("Character definition for 'test_player' not found.")
        new_player = Character.create_from_definition(chardef)
        new_player.connection = connection
        new_player.connection.character = new_player
        new_player.name = "Test Player"
        new_player.description_ = "A test player."
        new_player.pronoun_subject_ = "he"
        new_player.pronoun_object_ = "him"
        self.players.append(new_player)
        # print(YamlDumper.to_yaml_compatible_str(operating_state.zones_))
        first_zone = self.zones[list(self.zones.keys())[0]]
        # print(YamlDumper.to_yaml_compatible_str(first_zone))
        logger.debug3(f"first_zone: {first_zone}")
        first_room = first_zone.rooms[list(first_zone.rooms.keys())[0]]
        logger.debug3(f"first_room: {first_room}")
        logger.info(f"New player arriving: {new_player.name}")
        await CoreActionsInterface.get_instance().arrive_room(new_player, first_room)


    def remove_connection(self, consumer: 'MyWebsocketConsumer'):
        for c in self.connections:
            if c.consumer_ == consumer:
                self.remove_character(c)
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

    def perform_scheduled_events(self, tick: int):
        logger = StructuredLogger(__name__, prefix="perform_scheduled_events()> ")
        if tick in self.scheduled_events:
            for event in self.scheduled_events[tick]:
                # we'll pass through dead ppl in case the event needs it
                # if event.actor_ and Actor.is_deleted(event.actor_):
                #     event.actor_ = None
                #     continue
                logger.debug(f"performing scheduled action {event.name}")
                event.run(event.actor, tick, self, event.vars)
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
        self.characters_fighting.remove(character)

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
        return source_actor.get_permvar(var_name, "")
    
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
                    
                    # Combat stats
                    'hit_modifier': target_player.hit_modifier,
                    'dodge_dice_number': target_player.dodge_dice_number,
                    'dodge_dice_size': target_player.dodge_dice_size,
                    'dodge_modifier': target_player.dodge_modifier,
                    'critical_chance': target_player.critical_chance,
                    'critical_multiplier': target_player.critical_multiplier,
                    'num_main_hand_attacks': target_player.num_main_hand_attacks,
                    'num_off_hand_attacks': target_player.num_off_hand_attacks,
                    
                    # Resistances and reductions
                    'damage_resistances': {
                        dt.name: value for dt, value in target_player.damage_resistances.profile.items()
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
                        'damage_resistances': {
                            dt.name: value for dt, value in obj.damage_resistances.profile.items()
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
                            'damage_resistances': {
                                dt.name: value for dt, value in content.damage_resistances.profile.items()
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
                            'damage_resistances': {
                                dt.name: value for dt, value in obj.damage_resistances.profile.items()
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
                                'damage_resistances': {
                                    dt.name: value for dt, value in content.damage_resistances.profile.items()
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
                
                # Load combat stats
                target_player.hit_modifier = player_data['hit_modifier']
                target_player.dodge_dice_number = player_data['dodge_dice_number']
                target_player.dodge_dice_size = player_data['dodge_dice_size']
                target_player.dodge_modifier = player_data['dodge_modifier']
                target_player.critical_chance = player_data['critical_chance']
                target_player.critical_multiplier = player_data['critical_multiplier']
                target_player.num_main_hand_attacks = player_data['num_main_hand_attacks']
                target_player.num_off_hand_attacks = player_data['num_off_hand_attacks']
                
                # Load resistances and reductions
                target_player.damage_resistances = DamageResistances()
                for dt_name, value in player_data['damage_resistances'].items():
                    target_player.damage_resistances.profile[DamageType[dt_name]] = value
                    
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
                    obj.damage_resistances = DamageResistances()
                    for dt_name, value in obj_data['damage_resistances'].items():
                        obj.damage_resistances.profile[DamageType[dt_name]] = value
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

