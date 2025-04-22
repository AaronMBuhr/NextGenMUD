from collections import defaultdict
import copy
import fnmatch
from .structured_logger import StructuredLogger
from django.conf import settings
import json
import os
from typing import List, Dict, Optional
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
from .comprehensive_game_state_interface import GameStateInterface, ScheduledAction
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
                    for room_id, room_info in zone_info['rooms'].items():
                        logger.debug2(f"Loading room_id: {room_id}")
                        new_room = Room(room_id, self.world_definition.zones[zone_id])
                        new_room.from_yaml(new_zone, room_info)
                        new_zone.rooms[room_id] = new_room
                    logger.debug("Rooms loaded")
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
        logger.critical("init zones")
        for zone, zone_data in self.zones.items():
            logger.critical("init rooms")
            for room, room_data in zone_data.rooms.items():
                room_data.create_reference()
                # print(f"room_data: {room_data}")
                logger.debug3("init spawndata")
                for spawndata in room_data.spawn_data:
                    logger.critical(f"spawndata: {spawndata}")
                    spawndata.owner = room_data
                    logger.critical(f"spawndata.actor_type: {spawndata.actor_type}")
                    if spawndata.actor_type == ActorType.CHARACTER:
                        logger.critical("spawndata is character")
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
                            logger.critical(f"new_character: {new_character} added to room {new_character._location_room.rid}")
                for trig_type in room_data.triggers_by_type:
                    for trig in room_data.triggers_by_type[trig_type]:
                        logger.debug3("enabling trigger")
                        trig.enable()

        logger.info("World prepared")
    

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

    def add_scheduled_event(self, actor: Actor, name: str, scheduled_tick: int = None, in_ticks: int = None, 
                             vars: Dict[str, Any]=None, func: callable['Actor', int, 'ComprehensiveGameState', Dict[str, Any]] = None):
        logger = StructuredLogger(__name__, prefix="add_scheduled_task()> ")
        if not scheduled_tick and not in_ticks:
            raise Exception("Must specify either scheduled_tick or in_ticks.")
        elif scheduled_tick and in_ticks:
            raise Exception("Must specify either scheduled_tick or in_ticks, but not both.")
        if in_ticks:
            scheduled_tick = self.world_clock_tick + in_ticks
        action = ScheduledAction(scheduled_tick, actor, name, vars, func)
        if not scheduled_tick in self.scheduled_events:
            self.scheduled_events[scheduled_tick] = []
        self.scheduled_events[scheduled_tick].append(action)

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
            # Create a dictionary representation of the game state
            game_state = {
                'world_clock_tick': self.world_clock_tick,
                'players': [{
                    'id': player.id,
                    'name': player.name,
                    'description': player.description_,
                    'location': player._location_room.rid if player._location_room else None,
                    'attributes': {
                        'strength': player.attributes.strength,
                        'dexterity': player.attributes.dexterity,
                        'constitution': player.attributes.constitution,
                        'intelligence': player.attributes.intelligence,
                        'wisdom': player.attributes.wisdom,
                        'charisma': player.attributes.charisma
                    },
                    'stats': {
                        'level': player.level_,
                        'experience': player.experience_,
                        'health': player.health_,
                        'max_health': player.max_health_,
                        'mana': player.mana_,
                        'max_mana': player.max_mana_
                    },
                    'inventory': [{
                        'id': obj.id,
                        'name': obj.name,
                        'description': obj.description_
                    } for obj in player.contents],
                    'equipment': {
                        str(loc.name): {
                            'id': obj.id,
                            'name': obj.name
                        } if obj else None for loc, obj in player.equipment_.items()
                    }
                } for player in self.players if player.name == player_name],
                # Add other state you want to save
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
                
                # Set attributes
                if 'attributes' in player_data:
                    attrs = player_data['attributes']
                    target_player.attributes.strength = attrs.get('strength', target_player.attributes.strength)
                    target_player.attributes.dexterity = attrs.get('dexterity', target_player.attributes.dexterity)
                    target_player.attributes.constitution = attrs.get('constitution', target_player.attributes.constitution)
                    target_player.attributes.intelligence = attrs.get('intelligence', target_player.attributes.intelligence)
                    target_player.attributes.wisdom = attrs.get('wisdom', target_player.attributes.wisdom)
                    target_player.attributes.charisma = attrs.get('charisma', target_player.attributes.charisma)
                
                # Set stats
                if 'stats' in player_data:
                    stats = player_data['stats']
                    target_player.level_ = stats.get('level', target_player.level_)
                    target_player.experience_ = stats.get('experience', target_player.experience_)
                    target_player.health_ = stats.get('health', target_player.health_)
                    target_player.max_health_ = stats.get('max_health', target_player.max_health_)
                    target_player.mana_ = stats.get('mana', target_player.mana_)
                    target_player.max_mana_ = stats.get('max_mana', target_player.max_mana_)
                
                # TODO: Handle inventory and equipment loading
            
            # Set world clock if needed
            if 'world_clock_tick' in game_state:
                self.world_clock_tick = game_state['world_clock_tick']
                
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


live_game_state = ComprehensiveGameState()
GameStateInterface.set_instance(live_game_state)

